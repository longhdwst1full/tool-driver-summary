import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from drive_documents import process_documents


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
