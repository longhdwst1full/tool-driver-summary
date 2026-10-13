#!/usr/bin/env python3
"""Idempotently copy validated local catalogue and reading content to MongoDB."""

from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import re

from mongo_catalog import SCHEMA_VERSION, database_from_env
from web_app import (NEW_SOURCE_FOLDERS, REPORTS, file_content, library, read_json,
                     source_catalog, source_file_content, source_video_status)


def sort_key(value: str) -> str:
    return "".join(part.zfill(12) if part.isdigit() else part.casefold()
                   for part in re.split(r"(\d+)", value))


def save_content(db, key: str, payload: dict, updated_at: str) -> None:
    db.study_content.replace_one({"_id": key},
                                 {"_id": key, "payload": payload,
                                  "schema_version": SCHEMA_VERSION, "updated_at": updated_at},
                                 upsert=True)


def sync_library(db, updated_at: str) -> dict:
    snapshot = library()
    db.library_snapshots.replace_one({"_id": "main"},
                                     {"_id": "main", "payload": snapshot,
                                      "schema_version": SCHEMA_VERSION, "updated_at": updated_at},
                                     upsert=True)
    saved = 0
    for row in snapshot["documents"]:
        if row["status"] != "ok":
            continue
        payload = file_content("document", row["id"])
        if payload:
            save_content(db, f"library:document:{row['id']}", payload, updated_at)
            saved += 1
    for row in snapshot["videos"]:
        for kind, file_id in (("ui_transcript", row["id"]),
                              ("progressive_note", row["id"]),
                              ("transcript", row.get("caption_id"))):
            if not file_id:
                continue
            payload = file_content(kind, file_id)
            if payload:
                save_content(db, f"library:{kind}:{file_id}", payload, updated_at)
                saved += 1
    for row in snapshot["notes"]:
        if row["type"] in {"ui_transcript", "progressive_note"}:
            continue
        payload = file_content(row["type"], row["id"])
        if payload:
            save_content(db, f"library:{row['type']}:{row['id']}", payload, updated_at)
            saved += 1
    return {"videos": len(snapshot["videos"]), "documents": len(snapshot["documents"]),
            "content": saved}


def sync_source(db, source_id: str, order: int, updated_at: str,
                *, metadata_only: bool = False) -> dict:
    from pymongo import ReplaceOne

    source_dir = REPORTS / "new-sources" / source_id
    final = source_dir / "scan.json"
    checkpoint = source_dir / "scan.checkpoint.json"
    path = final if final.is_file() else checkpoint
    if not path.is_file():
        return {"items": 0, "content": 0, "skipped": "chưa có scan"}
    scan = read_json(path)
    if path == checkpoint:
        items = scan.get("items", [])
        folder = {"id": source_id, "name": scan.get("root_name", NEW_SOURCE_FOLDERS[source_id])}
        visited = scan.get("visited", [])
    else:
        items = scan["items"]
        folder = scan["folder"]
        visited = []
    generation = sha256(f"{path.stat().st_mtime_ns}:{path.stat().st_size}".encode()).hexdigest()[:16]
    summary = source_catalog(source_id)["source"]
    caption_rows = read_json(source_dir / "transcripts/manifest.json", {"files": []})["files"]
    document_rows = read_json(source_dir / "documents/manifest.json", {"files": []})["files"]
    caption_status = {row["id"]: row["status"] for row in caption_rows}
    document_status = {row["id"]: row["status"] for row in document_rows}
    caption_by_video = {row["video_id"]: row["id"] for row in caption_rows
                        if row.get("status") == "ok" and row.get("video_id")}
    old_ids = {row["id"] for row in read_json(REPORTS / "scan.json", {"items": []})["items"]}
    child_counts = Counter(row["parent_id"] for row in items)
    ui_dir = source_dir / "ui-transcripts"
    requests = []
    saved_content = 0
    for item in items:
        file_id = item["id"]
        kind = item["kind"]
        view = {key: item.get(key) for key in ("id", "name", "kind", "url", "path", "size")}
        view.update(already_indexed=file_id in old_ids,
                    children_count=child_counts[file_id] if kind == "folder" else None,
                    caption_id=caption_by_video.get(file_id),
                    transcript_status=caption_status.get(file_id),
                    document_status=document_status.get(file_id))
        if kind == "video" and (ui_dir / f"{file_id}.json").is_file():
            view["ui_transcript"], view["progressive_note"] = source_video_status(
                source_id, file_id, {"folder": folder, "items": [item]}, item)
        record_id = f"{source_id}:{generation}:{file_id}"
        record = {"_id": record_id, "source_id": source_id, "generation": generation,
                  "id": file_id, "name": item["name"], "path": item["path"],
                  "parent_id": item["parent_id"], "kind": kind,
                  "kind_rank": 0 if kind == "folder" else 1,
                  "sort_key": sort_key(item["path"] if kind != "folder" else item["name"]),
                  "view": view, "schema_version": SCHEMA_VERSION}
        requests.append(ReplaceOne({"_id": record_id}, record, upsert=True))
        if len(requests) >= 500:
            db.source_items.bulk_write(requests, ordered=False)
            requests.clear()
        if metadata_only:
            continue
        kinds = []
        if kind == "document" and document_status.get(file_id) == "ok":
            kinds.append("document")
        elif kind == "transcript" and caption_status.get(file_id) in {"ok", "untimed_text"}:
            kinds.append("transcript")
        elif kind == "video":
            if view.get("ui_transcript"):
                kinds.append("ui_transcript")
            if view.get("progressive_note"):
                kinds.append("progressive_note")
        for content_kind in kinds:
            payload = source_file_content(source_id, content_kind, file_id)
            if payload:
                save_content(db, f"source:{source_id}:{content_kind}:{file_id}",
                             payload, updated_at)
                saved_content += 1
    if requests:
        db.source_items.bulk_write(requests, ordered=False)
    db.source_meta.replace_one({"_id": source_id},
                               {"_id": source_id, "folder": folder, "summary": summary,
                                "generation": generation, "visited": visited, "order": order,
                                "schema_version": SCHEMA_VERSION, "updated_at": updated_at},
                               upsert=True)
    return {"items": len(items), "content": saved_content, "generation": generation}


def main() -> None:
    parser = argparse.ArgumentParser(description="Đưa dữ liệu học tập hợp lệ lên MongoDB")
    parser.add_argument("--source-id", action="append", choices=NEW_SOURCE_FOLDERS,
                        help="Chỉ đồng bộ nguồn này; có thể dùng nhiều lần")
    parser.add_argument("--metadata-only", action="store_true",
                        help="Chỉ đồng bộ danh mục, chưa tải nội dung trích xuất")
    args = parser.parse_args()
    db = database_from_env()
    db.source_items.create_index([("source_id", 1), ("generation", 1),
                                  ("parent_id", 1), ("kind_rank", 1), ("sort_key", 1)])
    db.source_items.create_index([("source_id", 1), ("generation", 1),
                                  ("kind", 1), ("sort_key", 1)])
    timestamp = datetime.now(timezone.utc).isoformat()
    result = {"library": sync_library(db, timestamp), "sources": {}}
    for order, source_id in enumerate(NEW_SOURCE_FOLDERS):
        if args.source_id and source_id not in args.source_id:
            continue
        result["sources"][source_id] = sync_source(db, source_id, order, timestamp,
                                                   metadata_only=args.metadata_only)
        print(f"{source_id}: {result['sources'][source_id]}", flush=True)
    print(json.dumps(result, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
