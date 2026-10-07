import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from web_app import command_for, file_content, library


class WebAppTests(unittest.TestCase):
    def test_library_reads_reports_without_exposing_credentials(self):
        with TemporaryDirectory() as folder, patch("web_app.REPORTS", Path(folder)):
            report = Path(folder)
            (report / "scan.json").write_text(json.dumps({
                "folder": {"id": "folder1", "name": "Khóa học"}, "total": 2,
                "counts": {"video": 1, "document": 1},
                "items": [
                    {"id": "video1", "name": "Bài 1.mp4", "path": "Khóa học/Course/Bài 1.mp4",
                     "kind": "video", "url": "https://drive.google.com/video1", "size": 100,
                     "transcript_files": [{"id": "caption1"}]},
                    {"id": "doc1", "name": "Tài liệu.pdf", "path": "Khóa học/Course/Tài liệu.pdf",
                     "kind": "document", "url": "https://drive.google.com/doc1", "size": 200},
                ],
            }), encoding="utf-8")
            (report / "transcripts").mkdir()
            (report / "transcripts/manifest.json").write_text(json.dumps({"ok": 1, "files": [{
                "id": "caption1", "name": "Bài 1.srt", "status": "ok", "cue_count": 2,
                "duration_ms": 10000, "output": "caption1.md",
            }]}), encoding="utf-8")
            (report / "transcripts/caption1.md").write_text("# Timeline", encoding="utf-8")
            data = library()
            self.assertEqual(len(data["videos"]), 1)
            self.assertEqual(len(data["documents"]), 1)
            self.assertEqual(data["videos"][0]["caption_id"], "caption1")
            self.assertNotIn("token", json.dumps(data))
            self.assertEqual(file_content("transcript", "caption1")["content"], "# Timeline")

    def test_file_reader_blocks_unlisted_paths(self):
        self.assertIsNone(file_content("document", "../../token.json"))
        self.assertIsNone(file_content("study_note", "token"))

    def test_jobs_are_whitelisted(self):
        with TemporaryDirectory() as folder, patch("web_app.REPORTS", Path(folder)):
            (Path(folder) / "scan.json").write_text(
                json.dumps({"folder": {"id": "folder1"}}), encoding="utf-8")
            self.assertIn("drive_scan.py", command_for("scan"))
        with self.assertRaises(ValueError):
            command_for("shell")
        with self.assertRaises(ValueError):
            command_for("note", "../../token.json")


if __name__ == "__main__":
    unittest.main()
