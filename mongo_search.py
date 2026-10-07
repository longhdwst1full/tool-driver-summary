"""MongoDB-backed source chunk index. Credentials come only from the environment."""

from __future__ import annotations

from hashlib import sha256
import os

from course_synthesis import collect_lessons


PROJECT = "tool-driver-summary"


def collection_from_env():
    uri = os.environ.get("MONGODB_URI")
    if not uri:
        raise ValueError("Thiếu MONGODB_URI trong môi trường")
    try:
        from pymongo import MongoClient
        client = MongoClient(uri, serverSelectionTimeoutMS=8000, connectTimeoutMS=8000)
        client.admin.command("ping")
        return client[os.environ.get("MONGODB_DATABASE", "tool_driver_summary")]["source_chunks"]
    except ImportError as exc:
        raise RuntimeError("Thiếu PyMongo; cài thư viện từ requirements.txt") from exc
    except Exception as exc:
        raise RuntimeError("Không kết nối được MongoDB; kiểm tra URI, mật khẩu và Atlas Network Access") from exc


def build_mongo_index(packs, collection=None) -> dict:
    """Replace project-owned chunks and remove stale records after a complete scan."""
    collection = collection if collection is not None else collection_from_env()
    courses = collect_lessons(packs)
    generation = sha256("|".join(sorted(str(lesson["path"]) for rows in courses.values()
                                     for lesson in rows)).encode()).hexdigest()
    count = 0
    collection.create_index([("project", 1), ("text", "text")], default_language="none")
    collection.create_index([("project", 1), ("course", 1)])
    for course, lessons in courses.items():
        for lesson in lessons:
            for chunk in lesson["data"].get("chunks", []):
                at = (f"{chunk['start']}–{chunk['end']}" if chunk["kind"] == "caption"
                      else f"đoạn {chunk['para_start']}–{chunk['para_end']}")
                record = {"project": PROJECT, "chunk_id": chunk["chunk_id"], "course": course,
                          "lesson": lesson["title"], "source_id": chunk["source_id"],
                          "kind": chunk["kind"], "at": at, "text": chunk["text"],
                          "generation": generation}
                collection.replace_one({"_id": f"{PROJECT}:{chunk['chunk_id']}"},
                                       {"_id": f"{PROJECT}:{chunk['chunk_id']}", **record}, upsert=True)
                count += 1
    collection.delete_many({"project": PROJECT, "generation": {"$ne": generation}})
    return {"courses": len(courses), "chunks": count, "backend": "mongodb"}


def search_mongo(query: str, limit: int = 8, course: str | None = None, collection=None) -> list[dict]:
    collection = collection if collection is not None else collection_from_env()
    if not query.strip():
        return []
    selector = {"project": PROJECT, "$text": {"$search": query}}
    if course:
        selector["course"] = course
    fields = {key: 1 for key in ("chunk_id", "course", "lesson", "source_id", "kind", "at", "text")}
    fields["score"] = {"$meta": "textScore"}
    cursor = collection.find(selector, fields).sort([("score", {"$meta": "textScore"})]).limit(limit)
    return [{key: value for key, value in row.items() if key != "_id"} for row in cursor]
