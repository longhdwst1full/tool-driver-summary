import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from web_app import file_content, library


class CrossSourceWebTests(unittest.TestCase):
    def test_review_is_listed_and_only_fixed_id_can_open_it(self):
        with TemporaryDirectory() as folder, patch("web_app.REPORTS", Path(folder)):
            root = Path(folder)
            (root / "scan.json").write_text(json.dumps({"folder": {"id": "root"}, "items": [],
                                                         "counts": {}, "total": 0}), encoding="utf-8")
            review = root / "cross-source/review.md"
            review.parent.mkdir(parents=True)
            review.write_text("# Cần xem lại nguồn", encoding="utf-8")
            self.assertIn("cross_source_review", [row["type"] for row in library()["notes"]])
            self.assertEqual(file_content("cross_source_review", "cross-source-review")["content"],
                             "# Cần xem lại nguồn")
            self.assertIsNone(file_content("cross_source_review", "../../token.json"))


if __name__ == "__main__":
    unittest.main()
