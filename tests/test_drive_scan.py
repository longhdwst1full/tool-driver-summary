import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from drive_scan import (curated_exclusion, file_kind, folder_id_from, report_markdown, scan_folder, transcript_key,
                        video_source_status)


ROOT = "1FolderRoot12345"
CHILD = "1ChildFolder1234"


class Response:
    def __init__(self, value):
        self.value = value

    def execute(self, **kwargs):
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

    def test_curated_scan_prunes_excluded_branches_before_listing_children(self):
        def folder(file_id, name):
            return {"id": file_id, "name": name, "mimeType": "application/vnd.google-apps.folder"}

        pages = {
            (f"'{ROOT}' in parents and trashed = false", None): {"files": [
                folder("1Films123456789", "2. Dựng Phim và Nhiếp ảnh"),
                folder("1Graphics123456", "10. Thiết kế đồ họa"),
                folder("1Office12345678", "11. Tin học văn phòng"),
                folder("1Gift1234567890", "15. Quà tặng: tài nguyên"),
                folder("1Other123456789", "12. Khóa học khác"),
                folder("1Code1234567890", "1. Công nghệ thông tin"),
                {"id": "1Zalo1234567890", "name": "NHÓM ZALO HỖ TRỢ KHÁCH HÀNG.png", "mimeType": "image/png"},
                {"id": "1ZaloOther12345", "name": "NHÓM ZALO - QUÉT MÃ.png", "mimeType": "image/png"},
                {"id": "1Promo123456789", "name": "Các khóa học thuộc về Khóa học giá hời.txt", "mimeType": "text/plain"},
            ]},
            ("'1Other123456789' in parents and trashed = false", None): {"files": [
                folder("1Music123456789", "Âm nhạc - guitar"),
                folder("1Health12345678", "Sức khoẻ và làm đẹp"),
                folder("1Useful12345678", "Lập trình ứng dụng"),
            ]},
            ("'1Code1234567890' in parents and trashed = false", None): {"files": [
                {"id": "1Video123456789", "name": "Bài học.webm", "mimeType": "video/webm"},
            ]},
            ("'1Useful12345678' in parents and trashed = false", None): {"files": []},
        }
        report = scan_folder(Service(pages), ROOT, curated_exclusions=True)
        self.assertEqual(report["counts"], {"folder": 3, "video": 1})
        self.assertEqual(report["exclusions"]["folders"], 6)
        self.assertEqual(report["exclusions"]["files"], 3)
        self.assertIn("Đã bỏ qua 6 nhánh", report_markdown(report))

    def test_suno_course_is_removed_from_existing_checkpoint(self):
        title = "Khóa Học Suno AI – Biến Ý Tưởng Thành Âm Nhạc"
        other = "Khóa Học Sáng Tạo Âm Nhạc Thương Hiệu Với SUNO AI"
        self.assertIsNotNone(curated_exclusion(title, "folder", "Khóa học/AI Automation", "Khóa học"))
        self.assertIsNone(curated_exclusion(other, "folder", "Khóa học/AI Automation", "Khóa học"))
        with TemporaryDirectory() as folder:
            checkpoint = Path(folder) / "scan.checkpoint.json"
            suno_path = f"Khóa học/AI Automation/{title}"
            checkpoint.write_text(json.dumps({
                "folder_id": ROOT, "root_name": "Khóa học", "curated_exclusions": True,
                "queue": [["1SunoFolder12345", suno_path]], "visited": [ROOT],
                "items": [
                    {"id": "1SunoFolder12345", "name": title, "kind": "folder",
                     "parent_id": ROOT, "path": suno_path},
                    {"id": "1SunoVideo12345", "name": "Bài 1.mp4", "kind": "video",
                     "parent_id": "1SunoFolder12345", "path": suno_path + "/Bài 1.mp4"},
                ], "skipped": {"folders": 0, "files": 0, "examples": []},
            }), encoding="utf-8")
            service = Service({})
            report = scan_folder(service, ROOT, curated_exclusions=True, checkpoint_path=checkpoint)
            self.assertEqual(report["items"], [])
            self.assertEqual(report["exclusions"]["folders"], 1)
            self.assertEqual(service.api.queries, [])

    def test_parallel_scan_resumes_complete_batch_after_transient_error(self):
        second = "1OtherFolder1234"
        pages = {
            (f"'{ROOT}' in parents and trashed = false", None): {"files": [
                {"id": CHILD, "name": "Chương 1", "mimeType": "application/vnd.google-apps.folder"},
                {"id": second, "name": "Chương 2", "mimeType": "application/vnd.google-apps.folder"},
            ]},
            (f"'{CHILD}' in parents and trashed = false", None): {"files": [
                {"id": "1VideoFile12345", "name": "Bài 1.webm", "mimeType": "video/webm"},
            ]},
            (f"'{second}' in parents and trashed = false", None): {"files": []},
        }
        fail_once = [True]

        class FlakyFiles(Files):
            def list(self, **kwargs):
                if CHILD in kwargs["q"] and fail_once[0]:
                    fail_once[0] = False
                    raise RuntimeError("Drive temporarily unavailable")
                return super().list(**kwargs)

        class FlakyService(Service):
            def __init__(self):
                self.api = FlakyFiles(pages)

        with TemporaryDirectory() as folder:
            checkpoint = Path(folder) / "scan.checkpoint.json"
            with self.assertRaisesRegex(RuntimeError, "temporarily"):
                scan_folder(Service(pages), ROOT, checkpoint_path=checkpoint, workers=2,
                            service_factory=FlakyService)
            self.assertTrue(checkpoint.exists())
            report = scan_folder(Service(pages), ROOT, checkpoint_path=checkpoint, workers=2,
                                 service_factory=FlakyService)
            self.assertEqual(report["counts"], {"folder": 2, "video": 1})
            self.assertEqual(len({row["id"] for row in report["items"]}), report["total"])

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

    def test_video_source_status(self):
        self.assertEqual(video_source_status({"transcript_files": [{"id": "c"}], "can_download": False}),
                         "caption_file")
        self.assertEqual(video_source_status({"transcript_files": [], "can_download": True}), "asr_ready")
        self.assertEqual(video_source_status({"can_download": False}), "no_source")
        self.assertEqual(video_source_status({"can_download": None}), "no_source")
        self.assertEqual(video_source_status({"transcript_files": [{"id": "c"}]}, has_caption=False),
                         "no_source")


if __name__ == "__main__":
    unittest.main()
