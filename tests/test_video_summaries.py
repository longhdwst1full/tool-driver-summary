import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from video_summaries import build_report


class VideoSummariesTests(unittest.TestCase):
    def test_report_uses_only_verified_packs_and_preserves_detail(self):
        with TemporaryDirectory() as folder:
            reports = Path(folder)
            scan = {
                "folder": {"id": "root", "name": "Drive"},
                "items": [
                    {"id": "course", "kind": "folder", "name": "Khóa A", "parent_id": "root"},
                    {"id": "chapter", "kind": "folder", "name": "Chương 1", "parent_id": "course"},
                    {"id": "video1", "kind": "video", "name": "Bài 1.mp4", "parent_id": "chapter",
                     "path": "Drive/Khóa A/Chương 1/Bài 1.mp4", "url": "https://drive.google.com/video1",
                     "transcript_files": [{"id": "caption1"}]},
                    {"id": "caption1", "kind": "transcript", "name": "Bài 1.srt",
                     "parent_id": "chapter", "path": "Drive/Khóa A/Chương 1/Bài 1.srt"},
                    {"id": "video2", "kind": "video", "name": "Bài 2.mp4", "parent_id": "chapter",
                     "path": "Drive/Khóa A/Chương 1/Bài 2.mp4", "url": "https://drive.google.com/video2",
                     "transcript_files": []},
                ],
            }
            target = reports / "lesson-packs/Khóa A/Chương 1"
            target.mkdir(parents=True)
            (target / "Bài 1.json").write_text(json.dumps({"qa": {"status": "ok"}}), encoding="utf-8")
            (target / "Bài 1.md").write_text(
                "# Bài 1\n\nNguồn: video\n\n## Tóm tắt\n\nTóm tắt.\n\n## Các bước thực hành\n\n1. Bước có nguồn [00:01–00:05].\n",
                encoding="utf-8")
            report, count = build_report(scan, reports)
            self.assertEqual(count, 1)
            self.assertIn("1/2 video", report)
            self.assertIn("### Chương 1", report)
            self.assertIn("##### Các bước thực hành", report)
            self.assertIn("Bước có nguồn [00:01–00:05]", report)
            self.assertNotIn("#### Bài 2", report)


if __name__ == "__main__":
    unittest.main()
