import unittest

from drive_scan import file_kind, folder_id_from, report_markdown, scan_folder, transcript_key


ROOT = "1FolderRoot12345"
CHILD = "1ChildFolder1234"


class Response:
    def __init__(self, value):
        self.value = value

    def execute(self):
        return self.value


class Files:
    def __init__(self, pages):
        self.pages = pages
        self.queries = []

    def get(self, **kwargs):
        return Response({"id": ROOT, "name": "Khóa học", "mimeType": "application/vnd.google-apps.folder"})

    def list(self, **kwargs):
        self.queries.append(kwargs)
        return Response(self.pages[(kwargs["q"], kwargs.get("pageToken"))])


class Service:
    def __init__(self, pages):
        self.api = Files(pages)

    def files(self):
        return self.api


class DriveScanTests(unittest.TestCase):
    def test_folder_link_and_id(self):
        self.assertEqual(folder_id_from(f"https://drive.google.com/drive/u/0/folders/{ROOT}?usp=sharing"), ROOT)
        self.assertEqual(folder_id_from(ROOT), ROOT)
        with self.assertRaises(ValueError):
            folder_id_from("https://example.com/folders/1FolderRoot12345")

    def test_recursive_scan_pagination_and_caption_pair(self):
        pages = {
            (f"'{ROOT}' in parents and trashed = false", None): {
                "files": [
                    {"id": CHILD, "name": "Bài 1", "mimeType": "application/vnd.google-apps.folder"},
                    {"id": "1SlidesFile12345", "name": "Slides.pdf", "mimeType": "application/pdf"},
                ],
                "nextPageToken": "next",
            },
            (f"'{ROOT}' in parents and trashed = false", "next"): {"files": []},
            (f"'{CHILD}' in parents and trashed = false", None): {
                "files": [
                    {"id": "1VideoFile12345", "name": "Agent_Loop.mp4", "mimeType": "video/mp4"},
                    {"id": "1CaptionFile123", "name": "Agent_Loop.srt", "mimeType": "text/plain"},
                ]
            },
        }
        service = Service(pages)
        report = scan_folder(service, ROOT)
        self.assertEqual(report["counts"], {"document": 1, "folder": 1, "transcript": 1, "video": 1})
        video = next(row for row in report["items"] if row["kind"] == "video")
        self.assertEqual(video["transcript_files"], [{"id": "1CaptionFile123", "name": "Agent_Loop.srt"}])
        self.assertEqual(video["embedded_transcript"], "chưa thể xác định qua Drive API")
        self.assertIn("Bài 1/Agent_Loop.mp4", report_markdown(report))
        self.assertTrue(all(call["supportsAllDrives"] for call in service.api.queries))

    def test_scan_limit_fails_instead_of_silent_truncation(self):
        pages = {(f"'{ROOT}' in parents and trashed = false", None): {
            "files": [
                {"id": "1File000000001", "name": "A.pdf", "mimeType": "application/pdf"},
                {"id": "1File000000002", "name": "B.pdf", "mimeType": "application/pdf"},
            ]
        }}
        with self.assertRaisesRegex(RuntimeError, "giới hạn"):
            scan_folder(Service(pages), ROOT, max_files=1)

    def test_file_classification(self):
        self.assertEqual(file_kind({"name": "lecture.mp4", "mimeType": "application/octet-stream"}), "video")
        self.assertEqual(file_kind({"name": "note", "mimeType": "application/vnd.google-apps.document"}), "document")
        self.assertEqual(file_kind({"name": "caption.vtt", "mimeType": "text/vtt"}), "transcript")
        self.assertEqual(file_kind({"name": "notes.md", "mimeType": "text/markdown"}), "document")

    def test_locale_suffix_and_video_watermark_pair(self):
        self.assertEqual(
            transcript_key("1. Giới thiệu (example.com zalo 123).mp4"),
            transcript_key("1. Giới thiệu.vi_VN.srt"),
        )


if __name__ == "__main__":
    unittest.main()
