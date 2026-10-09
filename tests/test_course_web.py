import json
from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from web_app import file_content, library, source_catalog, source_file_content
from getsub_demo import format_time, parse_captions
from import_ui_transcript import make_srt
from output_layout import safe_segment


class CourseWebTests(unittest.TestCase):
    def test_new_source_video_prefers_vietnamese_caption(self):
        source_id = "1pjNn2Wc_f5dLEfF023m5jvMEyF2s2fWj"
        video_id = "1VideoWithLanguages123"
        with TemporaryDirectory() as folder, patch("web_app.REPORTS", Path(folder)):
            source = Path(folder) / "new-sources" / source_id
            transcripts = source / "transcripts"
            transcripts.mkdir(parents=True)
            (source / "scan.json").write_text(json.dumps({
                "folder": {"id": source_id, "name": "Nguồn học"}, "items": [
                    {"id": video_id, "name": "Bài 1.mp4", "kind": "video",
                     "parent_id": source_id, "path": "Nguồn học/Bài 1.mp4"}]}), encoding="utf-8")
            (transcripts / "manifest.json").write_text(json.dumps({"files": [
                {"id": "1CaptionVi123456", "name": "Bài 1_vi.srt", "status": "ok", "video_id": video_id},
                {"id": "1CaptionEn123456", "name": "Bài 1_en.srt", "status": "ok", "video_id": video_id}]}), encoding="utf-8")
            row = source_catalog(source_id, kind="video")["items"][0]
            self.assertEqual(row["caption_id"], "1CaptionVi123456")

    def test_new_source_reader_only_opens_manifest_outputs(self):
        source_id = "1pjNn2Wc_f5dLEfF023m5jvMEyF2s2fWj"
        with TemporaryDirectory() as folder, patch("web_app.REPORTS", Path(folder)):
            source = Path(folder) / "new-sources" / source_id
            docs = source / "documents"
            transcripts = source / "transcripts"
            docs.mkdir(parents=True)
            transcripts.mkdir()
            (source / "scan.json").write_text(json.dumps({
                "folder": {"id": source_id, "name": "Nguồn học"},
                "items": [{"id": "1Document123456", "name": "Bài đọc.pdf", "kind": "document",
                           "parent_id": source_id, "path": "Nguồn học/Bài đọc.pdf", "url": "https://drive.google.com/doc"},
                          {"id": "1Caption1234567", "name": "Bài học.srt", "kind": "transcript",
                           "parent_id": source_id, "path": "Nguồn học/Bài học.srt", "url": "https://drive.google.com/caption"}]}), encoding="utf-8")
            (docs / "Bài đọc.txt").write_text("Văn bản bài học", encoding="utf-8")
            (transcripts / "Bài học.md").write_text("# Timeline\n\n00:00 mở đầu", encoding="utf-8")
            (docs / "manifest.json").write_text(json.dumps({"files": [
                {"id": "1Document123456", "name": "Bài đọc.pdf", "mime_type": "application/pdf",
                 "status": "ok", "output": "Bài đọc.txt"}]}), encoding="utf-8")
            (transcripts / "manifest.json").write_text(json.dumps({"files": [
                {"id": "1Caption1234567", "name": "Bài học.srt", "status": "ok",
                 "output": "Bài học.md"}]}), encoding="utf-8")
            rows = {row["kind"]: row for row in source_catalog(source_id)["items"]}
            self.assertEqual(rows["document"]["document_status"], "ok")
            self.assertEqual(rows["transcript"]["transcript_status"], "ok")
            self.assertEqual(source_file_content(source_id, "document", "1Document123456")["document_type"], "pdf")
            self.assertIn("00:00", source_file_content(source_id, "transcript", "1Caption1234567")["content"])
            self.assertIsNone(source_file_content(source_id, "document", "../../token.json"))
            self.assertIsNone(source_file_content("unknown", "document", "1Document123456"))
            self.assertIsNone(source_file_content(source_id, "document", "1Unlisted123456"))
            (docs / "manifest.json").write_text(json.dumps({"files": [
                {"id": "1Document123456", "status": "ok", "output": "../../token.txt"}]}), encoding="utf-8")
            self.assertIsNone(source_file_content(source_id, "document", "1Document123456"))

    def test_untimed_source_text_opens_as_document(self):
        source_id = "1pjNn2Wc_f5dLEfF023m5jvMEyF2s2fWj"
        file_id = "1UntimedCaption12345"
        with TemporaryDirectory() as folder, patch("web_app.REPORTS", Path(folder)):
            transcript_dir = Path(folder) / "new-sources" / source_id / "transcripts"
            transcript_dir.mkdir(parents=True)
            (transcript_dir / "Bài đọc.txt").write_text("Nội dung bài đọc", encoding="utf-8")
            (transcript_dir / "manifest.json").write_text(json.dumps({"files": [
                {"id": file_id, "name": "Bài đọc.txt", "status": "untimed_text",
                 "output": "Bài đọc.txt"}]}), encoding="utf-8")
            result = source_file_content(source_id, "transcript", file_id)
            self.assertEqual(result["document_type"], "text")
            self.assertEqual(result["content"], "Nội dung bài đọc")
            self.assertIsNone(source_file_content(source_id, "transcript", "../../token.json"))

    def test_new_source_catalog_is_scoped_and_marks_existing_videos(self):
        source_id = "1GwuGmZuGk04LuvgwLUl9ahdZ1NW-2xqF"
        video_id = "1VideoExisting123456789"
        with TemporaryDirectory() as folder, patch("web_app.REPORTS", Path(folder)):
            root = Path(folder)
            (root / "scan.json").write_text(json.dumps({"items": [{"id": video_id}]}), encoding="utf-8")
            target = root / "new-sources" / source_id
            target.mkdir(parents=True)
            report = {"folder": {"id": source_id, "name": "Nguồn mới"},
                      "exclusions": {"folders": 4, "files": 2},
                      "items": [
                          {"id": "1CourseFolder123456", "name": "Khóa học AI", "kind": "folder",
                           "parent_id": source_id, "path": "Nguồn mới/Khóa học AI", "url": "https://drive.google.com/folder"},
                          {"id": video_id, "name": "Bài 1.webm", "kind": "video",
                           "parent_id": "1CourseFolder123456", "path": "Nguồn mới/Khóa học AI/Bài 1.webm",
                           "url": f"https://drive.google.com/file/d/{video_id}/view"},
                      ]}
            (target / "scan.json").write_text(json.dumps(report), encoding="utf-8")
            result = source_catalog(source_id, "1CourseFolder123456")
            self.assertEqual(result["source"]["excluded"], {"folders": 4, "files": 2})
            self.assertEqual(result["ancestors"][-1]["name"], "Khóa học AI")
            self.assertTrue(result["items"][0]["already_indexed"])
            self.assertEqual(source_catalog(source_id, query="Bài 1")["total_children"], 1)
            self.assertEqual(source_catalog(source_id, kind="video")["total_children"], 1)
            self.assertEqual(source_catalog(source_id, "1CourseFolder123456", kind="video")["items"][0]["id"], video_id)
            self.assertEqual(source_catalog(source_id, kind="folder")["total_children"], 1)
            self.assertEqual(source_catalog(source_id, "1CourseFolder123456", kind="folder")["total_children"], 0)
            self.assertIsNone(source_catalog(source_id, kind="../../token.json"))
            self.assertIsNone(source_catalog(source_id, "../../token.json"))
            self.assertIsNone(source_catalog("unknown"))
            report["items"].append({"id": "1AnotherVideo123456", "name": "Bài 2.webm", "kind": "video",
                                    "parent_id": "1CourseFolder123456", "path": "Nguồn mới/Khóa học AI/Bài 2.webm",
                                    "url": "https://drive.google.com/file/d/1AnotherVideo123456/view"})
            (target / "scan.json").write_text(json.dumps(report), encoding="utf-8")
            self.assertEqual(source_catalog(source_id, "1CourseFolder123456", kind="video")["total_children"], 2)

    def test_ui_transcript_and_verified_note_appear_in_course(self):
        video_id = "1az6YoUwufRY3Ch5EgHn4J0XAtQM-9W11"
        with TemporaryDirectory() as folder, patch("web_app.REPORTS", Path(folder)):
            root = Path(folder)
            scan = {"folder": {"id": "root", "name": "Root"}, "counts": {"video": 1}, "total": 1,
                    "items": [{"id": video_id, "kind": "video", "name": "Buổi 3.mp4",
                               "path": "Root/Claude AI/Chương 1/Buổi 3.mp4",
                               "url": f"https://drive.google.com/file/d/{video_id}/view",
                               "transcript_files": []}]}
            (root / "scan.json").write_text(json.dumps(scan), encoding="utf-8")
            rows = [{"at": "0:00", "text": "Nội dung đầu bài"},
                    {"at": "0:10", "text": "Nội dung cuối bài"}]
            ui = {"source": "drive_ui", "videoId": video_id, "url": scan["items"][0]["url"],
                  "atBottom": True, "startsNearZero": True, "rowCount": 2, "rows": rows}
            transcript_dir = root / "ui-transcripts"
            transcript_dir.mkdir()
            (transcript_dir / f"{video_id}.json").write_text(json.dumps(ui), encoding="utf-8")
            srt = make_srt(rows)
            (transcript_dir / f"{video_id}.srt").write_text(srt, encoding="utf-8")
            (transcript_dir / "batch-manifest.json").write_text(json.dumps({
                "folder_id": "root", "counts": {"ai_waiting": 1},
                "videos": {video_id: {"status": "ai_waiting", "rows": 2}}}), encoding="utf-8")
            cues = parse_captions(srt)
            source_hash = sha256("\n".join(str((format_time(c.start_ms), format_time(c.end_ms), c.text))
                                           for c in cues).encode()).hexdigest()
            note_dir = root / "progressive-demo/Claude AI/Chương 1"
            note_dir.mkdir(parents=True)
            stem = safe_segment("Buổi 3") + f"-{video_id[:8]}"
            note = {"caption_id": video_id, "source_kind": "drive_ui_transcript",
                    "source_sha256": source_hash,
                    "qa": {"status": "ok", "covered_chunks": 1, "total_chunks": 1}}
            (note_dir / f"{stem}.json").write_text(json.dumps(note), encoding="utf-8")
            (note_dir / f"{stem}.md").write_text("# Bài học\n\nNội dung đã kiểm tra", encoding="utf-8")
            data = library()
            video = data["videos"][0]
            self.assertEqual(video["course"], "Claude AI")
            self.assertEqual(video["chapter"], "Chương 1")
            self.assertEqual(video["ui_transcript"]["row_count"], 2)
            self.assertEqual(video["progressive_note"]["status"], "ok")
            self.assertEqual(video["processing_status"], "done")
            transcript_note = next(row for row in data["notes"] if row["type"] == "ui_transcript")
            self.assertEqual((transcript_note["course"], transcript_note["chapter"]),
                             ("Claude AI", "Chương 1"))
            self.assertEqual(file_content("progressive_note", video_id)["content"],
                             "# Bài học\n\nNội dung đã kiểm tra")
            self.assertIn("Nội dung đầu bài", file_content("ui_transcript", video_id)["content"])
            self.assertIsNone(file_content("progressive_note", "../../token.json"))
            note["source_sha256"] = "outdated"
            (note_dir / f"{stem}.json").write_text(json.dumps(note), encoding="utf-8")
            self.assertIsNone(library()["videos"][0]["progressive_note"])
            self.assertEqual(library()["videos"][0]["processing_status"], "ai_waiting")
            self.assertIsNone(file_content("progressive_note", video_id))

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
