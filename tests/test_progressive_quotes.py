import unittest

from progressive_demo import exact_points, validate_points


class ProgressiveQuoteTests(unittest.TestCase):
    def test_restore_only_source_whitespace(self):
        source = "Dữ liệu bán hàng\nđược phân tích theo từng tháng."
        points = [{"kind": "concept", "text": "Phân tích theo tháng",
                   "quote": "Dữ liệu bán hàng được phân tích theo từng tháng."},
                  {"kind": "concept", "text": "Ý không có bằng chứng",
                   "quote": "Một nội dung hoàn toàn không hề có trong phụ đề."}]
        accepted = exact_points(points, source)
        self.assertEqual(len(accepted), 1)
        self.assertIn("\n", accepted[0]["quote"])
        validate_points(accepted, source)


if __name__ == "__main__":
    unittest.main()
