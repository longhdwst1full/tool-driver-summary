from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from output_layout import is_promotional_document, output_paths, safe_output_file, safe_segment


class OutputLayoutTests(unittest.TestCase):
    def test_names_follow_course_chapter_and_video(self):
        scan = {"folder": {"id": "root"}, "items": [
            {"id": "course", "parent_id": "root", "kind": "folder", "name": "Khóa học A"},
            {"id": "chapter", "parent_id": "course", "kind": "folder", "name": "Chương 01: Mở đầu"},
            {"id": "video", "parent_id": "chapter", "kind": "video",
             "name": "14. Tạo dự án Admin (khoahocgiahoi.com zalo).mp4",
             "transcript_files": [{"id": "caption"}]},
            {"id": "caption", "parent_id": "chapter", "kind": "transcript",
             "name": "14. Tạo dự án Admin.vi_VN.srt", "path": "root/Khóa học A/Chương 01/caption"},
            {"id": "doc", "parent_id": "chapter", "kind": "document",
             "name": "7. Prompt.docx", "path": "root/Khóa học A/Chương 01/doc"},
        ]}
        caption = output_paths(scan, "transcript")["caption"]
        document = output_paths(scan, "document")["doc"]
        self.assertEqual(caption.as_posix(), "Khóa học A/Chương 01- Mở đầu/14. Tạo dự án Admin.md")
        self.assertEqual(document.as_posix(), "Khóa học A/Chương 01- Mở đầu/7. Prompt.txt")

    def test_promotional_filter_and_safe_path(self):
        self.assertTrue(is_promotional_document({"kind": "document", "name": "0. khoahocgiahoi.com.txt"}))
        self.assertTrue(is_promotional_document({"kind": "document", "name": "other.txt"},
                                                "Các khóa học thuộc về Khóa học giá hời\nWebsite..."))
        self.assertFalse(is_promotional_document({"kind": "document", "name": "7. Prompt.docx"},
                                                 "Nội dung bài học"))
        self.assertFalse(is_promotional_document({"kind": "document", "name": "Tài liệu khoahocgiahoi.com.docx"},
                                                 "Nội dung bài học"))
        self.assertEqual(safe_segment("Chương 01: Mở đầu"), "Chương 01- Mở đầu")
        with TemporaryDirectory() as folder:
            with self.assertRaises(ValueError):
                safe_output_file(Path(folder), "../token.txt", ".txt")


if __name__ == "__main__":
    unittest.main()
