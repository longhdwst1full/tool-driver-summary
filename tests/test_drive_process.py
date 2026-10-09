import unittest

from drive_process import caption_video_key, parse_drive_caption, process_captions
from pathlib import Path
from tempfile import TemporaryDirectory


class DriveProcessTests(unittest.TestCase):
    def test_accepts_blank_line_between_srt_number_and_time(self):
        source = "1\n\n00:00:01,648  -->  00:00:02,472\nNội dung bài học\n"
        for newline in ("\n", "\r\n"):
            with self.subTest(newline=repr(newline)):
                cues = parse_drive_caption(source.replace("\n", newline), "Bài học.srt")
                self.assertEqual(len(cues), 1)
                self.assertEqual(cues[0].start_ms, 1648)
                self.assertEqual(cues[0].text, "Nội dung bài học")

    def test_does_not_treat_untimed_text_as_caption(self):
        with self.assertRaisesRegex(ValueError, "Thiếu mốc thời gian"):
            parse_drive_caption("Prompt đi kèm: ví dụ hình ảnh", "Bài học.txt")

    def test_pairs_only_unique_lesson_titles_in_same_chapter(self):
        self.assertEqual(caption_video_key("1. Flutter cho MacOS.srt"),
                         caption_video_key("Bài 01 Flutter cho MacOS (website.example).mp4"))
        root = "1RootFolder123456"
        chapter = "1Chapter12345678"
        video = "1Video1234567890"
        caption = "1Caption12345678"
        scan = {"folder": {"id": root, "name": "Khóa học"}, "items": [
            {"id": chapter, "parent_id": root, "kind": "folder", "name": "Chương 1",
             "path": "Khóa học/Chương 1"},
            {"id": video, "parent_id": chapter, "kind": "video",
             "name": "Bài 01 Flutter cho MacOS (website.example).mp4",
             "path": "Khóa học/Chương 1/Bài 01 Flutter cho MacOS.mp4"},
            {"id": caption, "parent_id": chapter, "kind": "transcript",
             "name": "1. Flutter cho MacOS.srt", "path": "Khóa học/Chương 1/1. Flutter cho MacOS.srt",
             "can_download": True},
        ]}

        class FileAPI:
            def __init__(self, owner):
                self.owner = owner

            def get_media(self, **kwargs):
                self.file_id = kwargs["fileId"]
                return self

            def execute(self):
                self.owner.download_count += 1
                return b"1\r\n\r\n00:00:01,000 --> 00:00:02,000\r\nNoi dung bai hoc\r\n"

        class Service:
            def __init__(self):
                self.download_count = 0

            def files(self):
                return FileAPI(self)

        with TemporaryDirectory() as folder:
            service = Service()
            result = process_captions(service, scan, Path(folder))
            self.assertEqual(result["ok"], 1)
            self.assertEqual(result["files"][0]["video_id"], video)
            self.assertEqual(process_captions(service, scan, Path(folder))["ok"], 1)
            self.assertEqual(service.download_count, 1)

    def test_untimed_txt_is_saved_without_claiming_video_transcript(self):
        root = "1RootFolder123456"
        caption = "1CaptionText12345"
        scan = {"folder": {"id": root, "name": "Khóa học"}, "items": [
            {"id": caption, "parent_id": root, "kind": "transcript", "name": "Bài đọc.txt",
             "path": "Khóa học/Bài đọc.txt", "can_download": True},
        ]}

        class FileAPI:
            def __init__(self, owner):
                self.owner = owner

            def get_media(self, **kwargs):
                return self

            def execute(self):
                self.owner.download_count += 1
                return "Đây là văn bản không có mốc thời gian.".encode()

        class Service:
            def __init__(self):
                self.download_count = 0

            def files(self):
                return FileAPI(self)

        with TemporaryDirectory() as folder:
            service = Service()
            output = Path(folder)
            first = process_captions(service, scan, output)
            self.assertEqual((first["ok"], first["untimed_text"], first["errors"]), (0, 1, 0))
            row = first["files"][0]
            self.assertIsNone(row["video_id"])
            self.assertEqual((output / row["output"]).suffix, ".txt")
            self.assertIn("không có mốc", (output / row["output"]).read_text())
            self.assertEqual(process_captions(service, scan, output)["untimed_text"], 1)
            self.assertEqual(service.download_count, 1)
