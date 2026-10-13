"""MongoDB read model for the Drive Studio catalogue and validated study content."""

from __future__ import annotations

from functools import lru_cache
import os
import re
from threading import Lock
import time


DATABASE = "tool_driver_summary"
SCHEMA_VERSION = 1
PAGE_SIZE = 200
ALLOWED_KINDS = {"", "video", "document", "transcript", "folder"}
_RETRY_LOCK = Lock()
_retry_after = 0.0


@lru_cache(maxsize=1)
def database_from_env():
    uri = os.environ.get("MONGODB_URI")
    if not uri:
        raise ValueError("Thiếu MONGODB_URI trong môi trường")
    try:
        from pymongo import MongoClient
        client = MongoClient(uri, serverSelectionTimeoutMS=5000, connectTimeoutMS=5000,
                             timeoutMS=8000)
        client.admin.command("ping")
        return client[os.environ.get("MONGODB_DATABASE", DATABASE)]
    except ImportError as exc:
        raise RuntimeError("Thiếu PyMongo; cài requirements.txt") from exc
    except Exception as exc:
        raise RuntimeError("Không kết nối được MongoDB; kiểm tra URI và Atlas Network Access") from exc


def optional_database():
    """Return None briefly after a connection error so local reads stay responsive."""
    global _retry_after
    if not os.environ.get("MONGODB_URI") or time.monotonic() < _retry_after:
        return None
    try:
        return database_from_env()
    except (ValueError, RuntimeError):
        with _RETRY_LOCK:
            _retry_after = time.monotonic() + 30
        return None


def library_from_db(db) -> dict | None:
    row = db.library_snapshots.find_one({"_id": "main"}, {"payload": 1})
    return row.get("payload") if row else None


def course_search_from_db(db, query: str) -> dict | None:
    needle = query.casefold().strip()
    if len(needle) < 2 or len(needle) > 100:
        return None
    pattern = re.escape(needle)
    matches = []
    for meta in db.source_meta.find({}, {"folder": 1, "generation": 1}):
        source_id = meta["_id"]
        folder = meta["folder"]
        if needle in folder["name"].casefold():
            matches.append({"source_id": source_id, "id": source_id,
                            "name": folder["name"], "path": folder["name"]})
        selector = {"source_id": source_id, "generation": meta["generation"],
                    "kind": "folder", "name": {"$regex": pattern, "$options": "i"}}
        for row in db.source_items.find(selector, {"id": 1, "name": 1, "path": 1}):
            matches.append({"source_id": source_id, "id": row["id"],
                            "name": row["name"], "path": row["path"]})
    matches.sort(key=lambda row: (not row["name"].casefold().startswith(needle),
                                  row["path"].count("/"), row["name"].casefold()))
    return {"query": query.strip(), "total": len(matches), "items": matches[:80]}


def recent_lessons_from_db(db, username: str) -> list:
    row = db.user_preferences.find_one({"_id": username}, {"recent_lessons": 1})
    return row.get("recent_lessons", []) if row else []


def save_recent_lessons(db, username: str, lessons: list) -> list:
    if not isinstance(lessons, list) or len(lessons) > 16:
        raise ValueError("Danh sách bài học gần đây không hợp lệ")
    clean = []
    for row in lessons:
        if not isinstance(row, dict) or row.get("kind") not in {"video", "source_video"}:
            raise ValueError("Bài học gần đây không hợp lệ")
        file_id = row.get("id")
        source_id = row.get("source_id", "")
        if not isinstance(file_id, str) or not re.fullmatch(r"[A-Za-z0-9_-]{10,}", file_id):
            raise ValueError("ID bài học không hợp lệ")
        if row["kind"] == "source_video" and (not isinstance(source_id, str) or
            not re.fullmatch(r"[A-Za-z0-9_-]{10,}", source_id)):
            raise ValueError("ID nguồn không hợp lệ")
        if not isinstance(row.get("name"), str) or not isinstance(row.get("path"), str):
            raise ValueError("Tên bài học không hợp lệ")
        clean.append({"kind": row["kind"], "id": file_id,
                      "source_id": source_id if row["kind"] == "source_video" else "",
                      "name": row["name"][:300], "path": row["path"][:700]})
        if row["kind"] == "source_video":
            item = row.get("item")
            if not isinstance(item, dict) or item.get("id") != file_id or item.get("kind") != "video":
                raise ValueError("Metadata bài học không hợp lệ")
            clean[-1]["item"] = {key: item.get(key) for key in
                                 ("id", "kind", "name", "path", "url", "ui_transcript",
                                  "progressive_note", "caption_id")}
    db.user_preferences.update_one({"_id": username}, {"$set": {
        "recent_lessons": clean, "schema_version": SCHEMA_VERSION}}, upsert=True)
    return clean


def content_from_db(db, kind: str, file_id: str, source_id: str = "") -> dict | None:
    if not re.fullmatch(r"[A-Za-z0-9_-]+", file_id):
        return None
    if source_id and not re.fullmatch(r"[A-Za-z0-9_-]+", source_id):
        return None
    key = f"source:{source_id}:{kind}:{file_id}" if source_id else f"library:{kind}:{file_id}"
    row = db.study_content.find_one({"_id": key}, {"payload": 1})
    return row.get("payload") if row else None


def source_catalog_from_db(db, source_id: str | None = None, parent_id: str | None = None,
                           offset: int = 0, query: str = "", kind: str = "") -> dict | None:
    if offset < 0 or offset > 500_000 or len(query) > 100 or kind not in ALLOWED_KINDS:
        return None
    if source_id is None:
        return {"sources": [row["summary"] for row in db.source_meta.find({}, {"summary": 1, "order": 1})
                .sort("order", 1)]}
    if not re.fullmatch(r"[A-Za-z0-9_-]+", source_id):
        return None
    meta = db.source_meta.find_one({"_id": source_id})
    if not meta:
        return None
    parent_id = parent_id or source_id
    ancestors = [{"id": source_id, "name": meta["folder"]["name"]}]
    folder_path = ""
    if parent_id != source_id:
        chain = []
        cursor = parent_id
        while cursor != source_id:
            if len(chain) > 30:
                return None
            row = db.source_items.find_one({"_id": f"{source_id}:{meta['generation']}:{cursor}",
                                            "kind": "folder"},
                                           {"id": 1, "name": 1, "parent_id": 1, "path": 1})
            if not row:
                return None
            chain.append({"id": row["id"], "name": row["name"]})
            folder_path = folder_path or row["path"]
            cursor = row["parent_id"]
        ancestors.extend(reversed(chain))
    selector: dict = {"source_id": source_id, "generation": meta["generation"]}
    if query.strip():
        needle = re.escape(query.strip())
        selector["$or"] = [{"name": {"$regex": needle, "$options": "i"}},
                           {"path": {"$regex": needle, "$options": "i"}}]
        if kind:
            selector["kind"] = kind
    elif kind in {"video", "document", "transcript"}:
        selector["kind"] = kind
        if folder_path:
            selector["path"] = {"$regex": "^" + re.escape(folder_path + "/")}
    else:
        selector["parent_id"] = parent_id
        if kind:
            selector["kind"] = kind
    total = db.source_items.count_documents(selector)
    cursor = db.source_items.find(selector, {"view": 1}).sort([
        ("kind_rank", 1), ("sort_key", 1)]).skip(offset).limit(PAGE_SIZE)
    return {"source": meta["summary"], "parent_id": parent_id, "ancestors": ancestors,
            "items": [row["view"] for row in cursor], "total_children": total,
            "offset": offset, "parent_scanned": bool(meta["summary"]["complete"] or
                                               parent_id in meta.get("visited", [])),
            "query": query.strip(), "kind": kind}
