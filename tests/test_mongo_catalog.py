import base64
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from mongo_catalog import (content_from_db, course_search_from_db,
                           recent_lessons_from_db, save_recent_lessons, source_catalog_from_db)
from mongo_migrate import sync_source
from web_auth import authorized, hash_password


try:
    import mongomock
except ImportError:
    mongomock = None


@unittest.skipUnless(mongomock, "mongomock chưa được cài")
class MongoCatalogTests(unittest.TestCase):
    def test_recent_lessons_and_course_search(self):
        db = mongomock.MongoClient().test
        sid = "1Q730gr6P3wX-PB_yO8E872_RajP-F85R"
        db.source_meta.insert_one({"_id": sid, "folder": {"id": sid, "name": "Khóa Product"},
                                   "generation": "g1"})
        db.source_items.insert_one({"_id": f"{sid}:g1:chapter", "source_id": sid,
                                    "generation": "g1", "kind": "folder", "id": "chapter",
                                    "name": "Product chương 1", "path": "Khóa Product/Product chương 1"})
        self.assertEqual(course_search_from_db(db, "product")["total"], 2)
        lesson = {"kind": "source_video", "source_id": sid, "id": "lesson123456",
                  "name": "Bài 1", "path": "Khóa Product/Bài 1",
                  "item": {"id": "lesson123456", "kind": "video", "name": "Bài 1",
                           "path": "Khóa Product/Bài 1", "url": "https://drive.google.com/"}}
        save_recent_lessons(db, "admin", [lesson])
        self.assertEqual(recent_lessons_from_db(db, "admin")[0]["item"]["id"], "lesson123456")
        with self.assertRaises(ValueError):
            save_recent_lessons(db, "admin", [{**lesson, "id": "../secret"}])

    def test_source_migration_is_idempotent_and_exposes_current_generation(self):
        import mongo_migrate

        sid = "1Q730gr6P3wX-PB_yO8E872_RajP-F85R"
        with TemporaryDirectory() as folder:
            reports = Path(folder)
            source = reports / "new-sources" / sid
            source.mkdir(parents=True)
            (reports / "scan.json").write_text(json.dumps({"items": []}), encoding="utf-8")
            (source / "scan.json").write_text(json.dumps({
                "folder": {"id": sid, "name": "Khóa mẫu"},
                "items": [{"id": "lesson123456", "kind": "video", "parent_id": sid,
                           "name": "Bài 1.mp4", "path": "Khóa mẫu/Bài 1.mp4",
                           "url": "https://drive.google.com/file/d/lesson123456/view", "size": 1}],
                "counts": {"video": 1},
            }), encoding="utf-8")
            db = mongomock.MongoClient().test

            def bulk_write(operations, ordered=False):
                for operation in operations:
                    db.source_items.replace_one(operation._filter, operation._doc,
                                                upsert=operation._upsert)

            db.source_items.bulk_write = bulk_write
            with patch.object(mongo_migrate, "REPORTS", reports), patch("web_app.REPORTS", reports):
                first = sync_source(db, sid, 0, "now", metadata_only=True)
                second = sync_source(db, sid, 0, "later", metadata_only=True)
            self.assertEqual(first["items"], 1)
            self.assertEqual(second["items"], 1)
            self.assertEqual(db.source_items.count_documents({}), 1)
            self.assertEqual(source_catalog_from_db(db, sid)["items"][0]["id"], "lesson123456")

    def test_catalog_uses_source_and_generation_and_keeps_content_private(self):
        db = mongomock.MongoClient().test
        sid = "1Q730gr6P3wX-PB_yO8E872_RajP-F85R"
        db.source_meta.insert_one({"_id": sid, "folder": {"id": sid, "name": "Khóa thử"},
                                   "summary": {"id": sid, "name": "Khóa thử", "complete": True},
                                   "generation": "g2", "order": 0})
        db.source_items.insert_many([
            {"_id": f"{sid}:g2:chapter", "source_id": sid, "generation": "g2",
             "id": "chapter", "name": "Chương 1", "kind": "folder", "parent_id": sid,
             "path": "Khóa thử/Chương 1", "kind_rank": 0, "sort_key": "chapter",
             "view": {"id": "chapter", "name": "Chương 1", "kind": "folder"}},
            {"_id": f"{sid}:g2:lesson", "source_id": sid, "generation": "g2",
             "id": "lesson", "name": "Bài 1.mp4", "kind": "video", "parent_id": "chapter",
             "path": "Khóa thử/Chương 1/Bài 1.mp4", "kind_rank": 1, "sort_key": "lesson",
             "view": {"id": "lesson", "name": "Bài 1.mp4", "kind": "video"}},
            {"_id": f"{sid}:g1:old", "source_id": sid, "generation": "g1",
             "id": "old", "name": "Cũ", "kind": "video", "parent_id": sid,
             "path": "Cũ", "kind_rank": 1, "sort_key": "old", "view": {"id": "old"}},
        ])
        root = source_catalog_from_db(db, sid)
        self.assertEqual([row["id"] for row in root["items"]], ["chapter"])
        chapter = source_catalog_from_db(db, sid, "chapter")
        self.assertEqual([row["name"] for row in chapter["items"]], ["Bài 1.mp4"])
        self.assertEqual([row["name"] for row in chapter["ancestors"]], ["Khóa thử", "Chương 1"])
        db.study_content.insert_one({"_id": f"source:{sid}:document:lesson",
                                     "payload": {"content": "Nội dung", "kind": "document"}})
        self.assertEqual(content_from_db(db, "document", "lesson", sid)["content"], "Nội dung")
        self.assertIsNone(content_from_db(db, "document", "../../token.json", sid))


class WebAuthTests(unittest.TestCase):
    def test_basic_login_checks_password_hash(self):
        encoded = hash_password("mat-khau-rieng-123", bytes.fromhex("11" * 16))
        with patch.dict(os.environ, {"WEB_USERNAME": "long", "WEB_PASSWORD_HASH": encoded}):
            good = "Basic " + base64.b64encode(b"long:mat-khau-rieng-123").decode()
            bad = "Basic " + base64.b64encode(b"long:sai-mat-khau-123").decode()
            self.assertTrue(authorized(good))
            self.assertFalse(authorized(bad))
            self.assertFalse(authorized("Basic !!!"))
            self.assertFalse(authorized(None))
