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
                "folder": {"id": "folder1", "name": "Khóa học"}, "total": 4,
                "counts": {"folder": 1, "video": 1, "document": 1, "transcript": 1},
                "items": [
                    {"id": "course1", "parent_id": "folder1", "name": "Course",
                     "path": "Khóa học/Course", "kind": "folder"},
                    {"id": "video1", "name": "Bài 1.mp4", "path": "Khóa học/Course/Bài 1.mp4",
                     "parent_id": "course1", "kind": "video", "url": "https://drive.google.com/video1", "size": 100,
                     "transcript_files": [{"id": "caption1"}]},
                    {"id": "caption1", "name": "Bài 1.srt", "path": "Khóa học/Course/Bài 1.srt",
                     "parent_id": "course1", "kind": "transcript"},
                    {"id": "doc1", "name": "Tài liệu.pdf", "path": "Khóa học/Course/Tài liệu.pdf",
                     "parent_id": "course1", "kind": "document", "url": "https://drive.google.com/doc1", "size": 200},
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
            self.assertEqual(data["videos"][0]["source_status"], "caption_file")
            self.assertEqual(data["processed"]["sources"], {"caption_file": 1, "asr_ready": 0, "no_source": 0})
            self.assertNotIn("token", json.dumps(data))
            self.assertEqual(file_content("transcript", "caption1")["content"], "# Timeline")
            self.assertIsNone(data["videos"][0]["lesson_pack"])
            pack_dir = report / "lesson-packs/Course"
            pack_dir.mkdir(parents=True)
            (pack_dir / "Bài 1.json").write_text(json.dumps({
                "pack": {"summary": "Tóm tắt"}, "qa": {"status": "needs_review", "coverage": 0.5},
                "meta": {"prompt_id": "lesson_pack@1"},
                "chunks": [{"chunk_id": "caption1:c001", "start": "00:00", "end": "00:10", "text": "dài"}],
            }), encoding="utf-8")
            data = library()
            self.assertEqual(data["videos"][0]["lesson_pack"], {"status": "needs_review", "coverage": 0.5})
            self.assertEqual(data["processed"]["lesson_packs"], 1)
            self.assertIn("lesson_pack", [row["type"] for row in data["notes"]])
            pack = file_content("lesson_pack", "caption1")
            self.assertEqual(pack["pack"]["summary"], "Tóm tắt")
            self.assertNotIn("text", pack["chunks"][0])
            self.assertIsNone(file_content("lesson_pack", "doc1"))
            self.assertEqual(command_for("lesson_pack", "caption1")[-3:], ["lesson_pack.py", "--id", "caption1"])

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
        with self.assertRaises(ValueError):
            command_for("lesson_pack", "../../token.json")


if __name__ == "__main__":
    unittest.main()
