import json
from io import BytesIO
import importlib.util
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from drive_documents import effective_document_mime, extract_text, process_documents


class Response:
    def __init__(self, raw):
        self.raw = raw

    def execute(self):
        return self.raw


class Files:
    def __init__(self):
        self.calls = []

    def get_media(self, **kwargs):
        self.calls.append(kwargs["fileId"])
        return Response(b"Noi dung tai lieu")


class Service:
    def __init__(self):
        self.api = Files()

    def files(self):
        return self.api


class DocumentTests(unittest.TestCase):
    def test_generic_mime_uses_known_document_extension(self):
        self.assertEqual(effective_document_mime("Bài học.pdf", "application/octetstream"),
                         "application/pdf")
        self.assertEqual(effective_document_mime("Bài học.pptx", "application/octetstream"),
                         "application/vnd.openxmlformats-officedocument.presentationml.presentation")
        self.assertEqual(effective_document_mime("archive.zip", "application/octetstream"),
                         "application/octetstream")
        self.assertEqual(effective_document_mime("bang-so.xlsx", "application/octetstream"),
                         "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

    def test_html_preview_extracts_visible_text_without_script(self):
        content = extract_text(b"<h1>Bai hoc</h1><script>secret()</script><p>Noi dung</p>",
                               "text/html")
        self.assertIn("Bai hoc", content)
        self.assertIn("Noi dung", content)
        self.assertNotIn("secret()", content)

    @unittest.skipUnless(importlib.util.find_spec("openpyxl"), "openpyxl chưa được cài")
    def test_excel_preview_keeps_sheet_and_cell_values(self):
        from openpyxl import Workbook

        workbook = Workbook()
        sheet = workbook.active
        sheet.title = "Kế hoạch"
        sheet.append(["Bài", "Giờ"])
        sheet.append(["Quản lý dự án", 12])
        output = BytesIO()
        workbook.save(output)
        content = extract_text(output.getvalue(),
                               "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        self.assertIn("[Trang tính Kế hoạch]", content)
        self.assertIn("Bài\tGiờ", content)
        self.assertIn("Quản lý dự án\t12", content)

    def test_office_lock_file_is_excluded_without_download(self):
        scan = {"folder": {"id": "root"}, "items": [{
            "kind": "document", "id": "office_lock_1", "parent_id": "root",
            "name": "~$Bài học.doc", "path": "~$Bài học.doc",
            "mime_type": "application/msword", "url": "https://drive.google.com/lock",
        }]}
        with TemporaryDirectory() as folder:
            service = Service()
            result = process_documents(service, scan, Path(folder))
            self.assertEqual(result["excluded"], 1)
            self.assertEqual(service.api.calls, [])

    def test_zero_byte_text_is_empty_without_download_or_ocr(self):
        scan = {"folder": {"id": "root"}, "items": [{
            "kind": "document", "id": "empty_text_1", "parent_id": "root",
            "name": "Bài học.txt", "path": "Bài học.txt", "size": 0,
            "mime_type": "text/plain", "url": "https://drive.google.com/empty",
        }]}
        with TemporaryDirectory() as folder:
            service = Service()
            result = process_documents(service, scan, Path(folder), ocr=True)
            self.assertEqual((result["empty"], result["needs_ocr"]), (1, 0))
            self.assertEqual(service.api.calls, [])

    def test_read_html_word_and_markdown_as_text(self):
        html = "<html><body><h1>Tiêu đề</h1><script>secret()</script><p>Nội dung &amp; bài học</p></body></html>"
        text = extract_text(html.encode("utf-16"), "application/msword")
        self.assertIn("Tiêu đề", text)
        self.assertIn("Nội dung & bài học", text)
        self.assertNotIn("secret", text)
        self.assertEqual(extract_text(b"# Bai hoc", "text/markdown"), "# Bai hoc")
        with self.assertRaisesRegex(ValueError, "cấu trúc"):
            extract_text(b"not a Word document", "application/msword")

    def test_google_doc_exports_text_instead_of_downloading_media(self):
        scan = {"folder": {"id": "root"}, "items": [{
            "kind": "document", "id": "google_doc_1", "parent_id": "root",
            "name": "Tài liệu học", "path": "Tài liệu học",
            "mime_type": "application/vnd.google-apps.document",
            "url": "https://drive.google.com/document/d/google_doc_1",
        }]}

        class ExportFiles(Files):
            def export_media(self, **kwargs):
                self.calls.append((kwargs["fileId"], kwargs["mimeType"]))
                return Response("Nội dung bài học".encode())

            def get_media(self, **kwargs):
                raise AssertionError("Google Docs phải dùng export_media")

        service = Service()
        service.api = ExportFiles()
        with TemporaryDirectory() as folder:
            result = process_documents(service, scan, Path(folder))
            self.assertEqual(result["ok"], 1)
            self.assertEqual(service.api.calls, [("google_doc_1", "text/plain")])

    def test_checkpoint_and_resume_skip_download(self):
        scan = {"folder": {"id": "root"}, "items": [{
            "kind": "document", "id": "file_1", "parent_id": "root", "name": "test.txt", "path": "test.txt",
            "mime_type": "text/plain", "url": "https://drive.google.com/open?id=file_1",
            "modified_time": "2026-01-01", "size": 17,
        }]}
        with TemporaryDirectory() as folder:
            output = Path(folder)
            service = Service()
            first = process_documents(service, scan, output)
            second = process_documents(service, scan, output)
            self.assertEqual(first["ok"], 1)
            self.assertEqual(second["ok"], 1)
            self.assertEqual(service.api.calls, ["file_1"])
            self.assertEqual(json.loads((output / "manifest.json").read_text())["total"], 1)

    def test_large_file_is_skipped_before_download(self):
        scan = {"folder": {"id": "root"}, "items": [{
            "kind": "document", "id": "file_2", "parent_id": "root", "name": "large.pdf", "path": "large.pdf",
            "mime_type": "application/pdf", "url": "https://drive.google.com/open?id=file_2",
            "size": 11_000_000,
        }]}
        with TemporaryDirectory() as folder:
            service = Service()
            result = process_documents(service, scan, Path(folder))
            self.assertEqual(result["too_large"], 1)
            self.assertEqual(service.api.calls, [])

    def test_promotional_file_is_excluded_without_download(self):
        scan = {"folder": {"id": "root"}, "items": [{
            "kind": "document", "id": "promo_1", "parent_id": "root",
            "name": "0. khoahocgiahoi.com.txt", "path": "0. khoahocgiahoi.com.txt",
            "mime_type": "text/plain", "url": "https://drive.google.com/promo_1",
        }]}
        with TemporaryDirectory() as folder:
            output = Path(folder)
            (output / "promo_1.txt").write_text("Các khóa học thuộc về Khóa học giá hời", encoding="utf-8")
            service = Service()
            result = process_documents(service, scan, output)
            self.assertEqual(result["excluded"], 1)
            self.assertEqual(service.api.calls, [])
            self.assertFalse((output / "promo_1.txt").exists())


if __name__ == "__main__":
    unittest.main()
