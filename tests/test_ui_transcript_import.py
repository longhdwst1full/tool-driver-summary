import unittest

from getsub_demo import parse_captions
from import_ui_transcript import make_srt, validate_export


class UiTranscriptImportTests(unittest.TestCase):
    VIDEO_ID = "1az6YoUwufRY3Ch5EgHn4J0XAtQM-9W11"

    def sample(self):
        video_id = self.VIDEO_ID
        scan = {"items": [{"id": video_id, "kind": "video"}]}
        export = {
            "source": "drive_ui",
            "videoId": video_id,
            "url": f"https://drive.google.com/file/d/{video_id}/view",
            "rowCount": 3,
            "atBottom": True,
            "startsNearZero": True,
            "rows": [
                {"at": "0:00", "text": "Bài học bắt đầu."},
                {"at": "0:06", "text": "Một ví dụ của bài học."},
                {"at": "0:11", "text": "Kết luận của bài học."},
            ],
        }
        return scan, export

    def test_complete_visible_rows_round_trip_to_captions(self):
        scan, export = self.sample()
        video_id, rows = validate_export(export, scan)
        self.assertEqual(self.VIDEO_ID, video_id)
        cues = parse_captions(make_srt(rows))
        self.assertEqual(3, len(cues))
        self.assertEqual(6000, cues[1].start_ms)
        self.assertEqual("Một ví dụ của bài học.", cues[1].text)

    def test_reject_incomplete_or_unlisted_video(self):
        scan, export = self.sample()
        export["atBottom"] = False
        with self.assertRaisesRegex(ValueError, "đầu/cuối"):
            validate_export(export, scan)
        export["atBottom"] = True
        with self.assertRaisesRegex(ValueError, "không thuộc"):
            validate_export(export, {"items": []})


if __name__ == "__main__":
    unittest.main()
