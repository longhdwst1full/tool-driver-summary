import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from web_app import file_content, library


class CourseWebTests(unittest.TestCase):
    def test_course_summary_is_listed_and_other_paths_are_rejected(self):
        with TemporaryDirectory() as folder, patch("web_app.REPORTS", Path(folder)):
            root = Path(folder)
            (root / "scan.json").write_text(json.dumps({"folder": {"id": "root", "name": "Root"},
                "items": [{"id": "video1", "kind": "video", "name": "Bài 1.mp4",
                           "path": "Root/Course/Bài 1.mp4", "url": "https://drive.google.com/video1",
                           "transcript_files": []}], "counts": {"video": 1}, "total": 1}), encoding="utf-8")
            path = root / "courses/Course/course_summary.md"
            path.parent.mkdir(parents=True)
            path.write_text("# Tóm tắt khóa", encoding="utf-8")
            notes = [note for note in library()["notes"] if note["type"] == "course_summary"]
            self.assertEqual(len(notes), 1)
            self.assertEqual(file_content("course_summary", notes[0]["id"])["content"], "# Tóm tắt khóa")
            self.assertIsNone(file_content("course_summary", "course_unknown"))
            self.assertIsNone(file_content("course_summary", "../../token.json"))


if __name__ == "__main__":
    unittest.main()
