import unittest

from batch_ui_lessons import quota_limited


class BatchUILessonsTests(unittest.TestCase):
    def test_recognizes_full_and_truncated_codex_quota_errors(self):
        self.assertTrue(quota_limited("ERROR: You’ve hit your usage limit. Try again at 3:13 PM."))
        self.assertTrue(quota_limited("gain at 3:13 PM.\nWARN shell_snapshot"))
        self.assertFalse(quota_limited("Trích dẫn không khớp nguyên văn đoạn nguồn"))
        self.assertFalse(quota_limited("Panel bản chép lời chưa đủ mốc đầu/cuối"))


if __name__ == "__main__":
    unittest.main()
