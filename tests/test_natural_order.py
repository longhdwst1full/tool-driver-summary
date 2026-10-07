import unittest

from output_layout import natural_key


class NaturalOrderTests(unittest.TestCase):
    def test_numbered_lessons_follow_learning_order(self):
        names = ["10. Tổng kết", "2. Thực hành", "1. Giới thiệu"]
        self.assertEqual(sorted(names, key=natural_key),
                         ["1. Giới thiệu", "2. Thực hành", "10. Tổng kết"])


if __name__ == "__main__":
    unittest.main()
