import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from mongo_search import PROJECT, build_mongo_index, search_mongo


class Cursor(list):
    def sort(self, order):
        return self

    def limit(self, count):
        return self[:count]


class Collection:
    def __init__(self):
        self.rows = {}
        self.indexes = []

    def create_index(self, fields, **kwargs):
        self.indexes.append((fields, kwargs))

    def replace_one(self, selector, value, upsert=False):
        self.rows[selector["_id"]] = value

    def delete_many(self, selector):
        self.rows = {key: row for key, row in self.rows.items()
                     if row.get("project") != selector["project"] or
                     row.get("generation") == selector["generation"]["$ne"]}

    def find(self, selector, fields):
        phrase = selector["$text"]["$search"].casefold()
        return Cursor([{**row, "score": 1.0} for row in self.rows.values()
                       if row["project"] == selector["project"]
                       and phrase in row["text"].casefold()
                       and ("course" not in selector or row["course"] == selector["course"])])


class MongoSearchTests(unittest.TestCase):
    def test_index_and_retrieval_keep_source_id(self):
        with TemporaryDirectory() as folder:
            root = Path(folder)
            path = root / "Khóa A/Chương 1/Bài 1.json"
            path.parent.mkdir(parents=True)
            path.write_text(json.dumps({"qa": {"status": "ok"},
                "meta": {"video_id": "video_1", "caption_id": "caption_1"},
                "chunks": [{"chunk_id": "caption_1:c001", "source_id": "caption_1",
                            "kind": "caption", "start": "00:00", "end": "00:10",
                            "text": "Quản lý quyền người dùng"}]}), encoding="utf-8")
            collection = Collection()
            result = build_mongo_index(root, collection)
            self.assertEqual(result["chunks"], 1)
            self.assertIn(f"{PROJECT}:caption_1:c001", collection.rows)
            hits = search_mongo("quản lý quyền", collection=collection)
            self.assertEqual(hits[0]["chunk_id"], "caption_1:c001")
            self.assertEqual(hits[0]["at"], "00:00–00:10")


if __name__ == "__main__":
    unittest.main()
