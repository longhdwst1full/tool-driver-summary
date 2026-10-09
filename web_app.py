#!/usr/bin/env python3
"""Local management UI for the Google Drive study demo."""

from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
from hashlib import sha1, sha256
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import re
import secrets
import subprocess
import sys
from threading import Lock, Thread
from urllib.parse import parse_qs, urlparse

from drive_scan import video_source_status
from getsub_demo import format_time, parse_captions
from import_ui_transcript import validate_export
from output_layout import (is_promotional_document, natural_key, output_paths,
                           safe_output_file, safe_segment, video_title)
from study_pack import manual_note_paths


ROOT = Path(__file__).resolve().parent
REPORTS = ROOT / "drive-reports"
WEB = ROOT / "web"
SAFE_ID = re.compile(r"^[A-Za-z0-9_-]+$")
TOKEN = secrets.token_urlsafe(32)
JOBS: list[dict] = []
JOBS_LOCK = Lock()
NEW_SOURCE_FOLDERS = {
    "1GwuGmZuGk04LuvgwLUl9ahdZ1NW-2xqF": "Khóa Học Giá Hời 2026",
    "1pjNn2Wc_f5dLEfF023m5jvMEyF2s2fWj": "Khóa Học Giá Hời 2026 2",
}
SOURCE_CACHE: dict[str, tuple] = {}


def read_json(path: Path, fallback: dict | None = None) -> dict:
    if not path.is_file():
        return fallback if fallback is not None else {}
    return json.loads(path.read_text(encoding="utf-8"))


def lesson_pack_file(scan: dict, caption_id: str, extension: str) -> Path | None:
    relative = output_paths(scan, "ai_note").get(caption_id)
    if relative is None:
        return None
    return safe_output_file(REPORTS / "lesson-packs", relative.with_suffix(extension), extension)


def lesson_pack_summary(scan: dict, caption_id: str) -> dict | None:
    path = lesson_pack_file(scan, caption_id, ".json")
    if path is None or not path.is_file():
        return None
    try:
        qa = json.loads(path.read_text(encoding="utf-8")).get("qa", {})
    except (OSError, ValueError):
        return {"status": "error", "coverage": None}
    return {"status": qa.get("status", "error"), "coverage": qa.get("coverage")}


def configured_folder_id() -> str:
    scan = read_json(REPORTS / "scan.json")
    folder_id = scan.get("folder", {}).get("id") or os.environ.get("DRIVE_FOLDER_ID", "")
    if not SAFE_ID.fullmatch(folder_id):
        raise ValueError("Chưa có ID thư mục Drive; chạy drive_scan.py hoặc đặt DRIVE_FOLDER_ID")
    return folder_id


def course_name(path: str) -> str:
    parts = path.split("/")
    return parts[1] if len(parts) > 1 else "Ngoài khóa học"


def display_name(name: str) -> str:
    clean = re.sub(r"\s*\(khoahocgiahoi\.com[^)]*\)(?=\.[^.]+$)", "", name, flags=re.I)
    return re.sub(r"\.(mp4|mov|mkv|webm|avi|m4v)$", "", clean, flags=re.I)


def document_type(name: str, mime_type: str | None = None) -> str:
    """Describe the source format, not the normalized .txt extraction file."""
    suffix = Path(name.lower()).suffix
    if mime_type == "application/pdf" or suffix == ".pdf":
        return "pdf"
    if mime_type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document" or suffix in {".doc", ".docx"}:
        return "docx"
    if mime_type == "application/vnd.openxmlformats-officedocument.presentationml.presentation" or suffix in {".ppt", ".pptx"}:
        return "pptx"
    if suffix in {".md", ".markdown"}:
        return "markdown"
    if suffix == ".txt" and Path(name[:-4].lower()).suffix in {".yml", ".yaml", ".json", ".py", ".js", ".ts", ".sh", ".xml", ".html", ".css"}:
        return "code"
    return "text"


def course_note_id(course: str) -> str:
    return "course_" + sha1(course.encode("utf-8")).hexdigest()[:16]


def ui_transcript_data(scan: dict, video: dict) -> tuple[dict, list] | None:
    video_id = video["id"]
    if not SAFE_ID.fullmatch(video_id):
        return None
    json_path = safe_output_file(REPORTS / "ui-transcripts", video_id + ".json", ".json")
    srt_path = safe_output_file(REPORTS / "ui-transcripts", video_id + ".srt", ".srt")
    if not json_path.is_file() or not srt_path.is_file() or json_path.stat().st_size > 5_000_000:
        return None
    try:
        data = json.loads(json_path.read_text(encoding="utf-8"))
        _, rows = validate_export(data, scan)
        cues = parse_captions(srt_path.read_text(encoding="utf-8"))
    except (OSError, ValueError, KeyError, TypeError):
        return None
    if len(cues) != len(rows):
        return None
    return data, cues


def progressive_note_file(scan: dict, video: dict, extension: str) -> Path | None:
    prefix = scan["folder"]["name"] + "/"
    if not video["path"].startswith(prefix):
        return None
    within = video["path"][len(prefix):].split("/")
    relative = Path(*(safe_segment(part) for part in within[:-1]),
                    safe_segment(video_title(video["name"])) + f"-{video['id'][:8]}{extension}")
    return safe_output_file(REPORTS / "progressive-demo", relative, extension)


def progressive_note_summary(scan: dict, video: dict, cues: list) -> dict | None:
    json_path = progressive_note_file(scan, video, ".json")
    md_path = progressive_note_file(scan, video, ".md")
    if (json_path is None or md_path is None or not json_path.is_file() or not md_path.is_file()
            or json_path.stat().st_size > 2_000_000 or md_path.stat().st_size > 2_000_000):
        return None
    try:
        data = json.loads(json_path.read_text(encoding="utf-8"))
        qa = data["qa"]
        current_hash = sha256("\n".join(str((format_time(cue.start_ms),
                                              format_time(cue.end_ms), cue.text)) for cue in cues).encode()).hexdigest()
    except (OSError, ValueError, KeyError, TypeError):
        return None
    if (data.get("caption_id") != video["id"] or data.get("source_kind") != "drive_ui_transcript"
            or data.get("source_sha256") != current_hash or qa.get("status") != "ok"
            or not isinstance(qa.get("total_chunks"), int) or qa["total_chunks"] < 1
            or qa.get("covered_chunks") != qa["total_chunks"]):
        return None
    return {"status": "ok", "covered_chunks": qa["covered_chunks"],
            "total_chunks": qa["total_chunks"]}


def library() -> dict:
    scan = read_json(REPORTS / "scan.json", {"folder": {"id": "", "name": "Google Drive"}, "items": [], "counts": {}, "total": 0})
    captions = read_json(REPORTS / "transcripts/manifest.json", {"files": [], "ok": 0})
    documents = read_json(REPORTS / "documents/manifest.json", {"files": [], "ok": 0, "needs_ocr": 0})
    ui_batch = read_json(REPORTS / "ui-transcripts/batch-manifest.json", {"videos": {}, "counts": {}})
    if ui_batch.get("folder_id") != scan["folder"].get("id"):
        ui_batch = {"videos": {}, "counts": {}}
    caption_by_id = {row["id"]: row for row in captions.get("files", [])}
    doc_by_id = {row["id"]: row for row in documents.get("files", [])}
    ai_paths = output_paths(scan, "ai_note")
    manual_paths = manual_note_paths(scan)
    videos = []
    docs = []
    courses: dict[str, dict] = {}
    notes = []
    for item in scan.get("items", []):
        course = course_name(item["path"])
        if item["kind"] not in {"video", "document"}:
            continue
        if is_promotional_document(item) or doc_by_id.get(item["id"], {}).get("status") == "excluded":
            continue
        bucket = courses.setdefault(course, {"name": course, "videos": 0, "documents": 0, "captions": 0})
        path_parts = item["path"].split("/")
        chapter = " / ".join(path_parts[2:-1]) or "Bài học chưa chia chương"
        base = {"id": item["id"], "name": display_name(item["name"]), "path": item["path"],
                "course": course, "chapter": chapter, "url": item["url"], "size": item.get("size")}
        if item["kind"] == "video":
            bucket["videos"] += 1
            ui_result = ui_transcript_data(scan, item)
            ui_transcript = ({"row_count": ui_result[0]["rowCount"],
                              "last_at": ui_result[0]["rows"][-1]["at"]} if ui_result else None)
            progressive_note = progressive_note_summary(scan, item, ui_result[1]) if ui_result else None
            companion = item.get("transcript_files", [])
            transcript = next((caption_by_id.get(row["id"]) for row in companion
                               if caption_by_id.get(row["id"], {}).get("status") == "ok"), None)
            if transcript:
                bucket["captions"] += 1
            video = {**base, "caption_id": transcript["id"] if transcript else None,
                     "ui_transcript": ui_transcript, "progressive_note": progressive_note,
                     "processing_status": ("done" if progressive_note else
                                           "captured" if ui_transcript and not ui_batch.get("videos", {}).get(item["id"], {}).get("status")
                                           else ui_batch.get("videos", {}).get(item["id"], {}).get("status")),
                     "source_status": video_source_status(item, has_caption=transcript is not None),
                     "lesson_pack": lesson_pack_summary(scan, transcript["id"]) if transcript else None,
                     "cue_count": transcript.get("cue_count") if transcript else None,
                     "duration_ms": transcript.get("duration_ms") if transcript else None,
                     "has_ai_note": bool(transcript and (
                         safe_output_file(REPORTS / "ai-notes", ai_paths[transcript["id"]], ".md").is_file()
                         or (REPORTS / "ai-notes" / f"{transcript['id']}.md").is_file())),
                     "has_manual_note": bool(transcript and transcript["name"].startswith("14.")
                                             and ("14-admin" in manual_paths)
                                             and (safe_output_file(REPORTS / "study-notes", manual_paths["14-admin"], ".md").is_file()
                                                  or (REPORTS / "study-notes/14-admin.md").is_file()))}
            videos.append(video)
            if video["lesson_pack"]:
                notes.append({"id": transcript["id"], "name": base["name"], "course": course,
                              "chapter": chapter,
                              "type": "lesson_pack", "source": "video", "status": video["lesson_pack"]["status"]})
            if video["has_ai_note"]:
                notes.append({"id": transcript["id"], "name": base["name"], "course": course,
                              "chapter": chapter,
                              "type": "ai_note", "source": "video"})
            if progressive_note:
                notes.append({"id": item["id"], "name": base["name"], "course": course,
                              "chapter": chapter, "type": "progressive_note", "source": "video",
                              "status": "ok", "covered_chunks": progressive_note["covered_chunks"]})
            if ui_transcript:
                notes.append({"id": item["id"], "name": base["name"], "course": course,
                              "chapter": chapter, "type": "ui_transcript", "source": "video",
                              "url": base["url"], "row_count": ui_transcript["row_count"]})
        else:
            bucket["documents"] += 1
            result = doc_by_id.get(item["id"], {})
            docs.append({**base, "status": result.get("status", "pending"),
                         "document_type": document_type(item["name"], item.get("mime_type")),
                         "characters": result.get("characters")})
    for slug, title, source, course in (
        ("14-admin", "Bài 14 · Tạo dự án Admin bằng prompt", "video", "Vibe Coding 2026 Fullstack"),
        ("claude-ai-hieu-qua", "Hướng dẫn sử dụng Claude AI hiệu quả", "document", "Tài liệu Claude AI"),
    ):
        target = manual_paths.get(slug)
        if target and (safe_output_file(REPORTS / "study-notes", target, ".md").is_file()
                       or (REPORTS / "study-notes" / f"{slug}.md").is_file()):
            notes.append({"id": slug, "name": title, "course": course,
                          "type": "study_note", "source": source})
    if (REPORTS / "study-notes/index.md").is_file():
        notes.append({"id": "index", "name": "Chỉ mục toàn bộ khóa học", "course": "Tất cả khóa học",
                      "type": "study_index", "source": "index"})
    if (REPORTS / "video-summaries.md").is_file():
        notes.append({"id": "video-summaries", "name": "Nội dung chi tiết video đã xử lý",
                      "course": "Tất cả khóa học", "type": "video_summaries", "source": "video"})
    if (REPORTS / "cross-source/review.md").is_file():
        notes.append({"id": "cross-source-review", "name": "Cần xem lại giữa phụ đề và tài liệu",
                      "course": "Tất cả khóa học", "type": "cross_source_review", "source": "review"})
    for course in courses:
        summary = safe_output_file(REPORTS / "courses", Path(course) / "course_summary.md", ".md")
        if summary.is_file():
            notes.append({"id": course_note_id(course), "name": f"Tổng hợp · {course}",
                          "course": course, "type": "course_summary", "source": "course"})
    videos.sort(key=lambda row: natural_key(row["path"]))
    docs.sort(key=lambda row: natural_key(row["path"]))
    notes.sort(key=lambda row: (row["type"] != "video_summaries", row["name"].casefold()))
    counts = dict(scan.get("counts", {}))
    counts["document"] = len(docs)
    return {"folder": scan["folder"], "total": scan.get("total", 0),
            "counts": counts, "videos": videos, "documents": docs,
            "notes": notes, "courses": sorted(courses.values(), key=lambda row: row["name"].casefold()),
            "processed": {"captions": captions.get("ok", 0),
                          "ui_transcripts": sum(bool(row["ui_transcript"]) for row in videos),
                          "progressive_notes": sum(bool(row["progressive_note"]) for row in videos),
                          "ui_batch": ui_batch.get("counts", {}),
                          "documents": sum(row["status"] == "ok" for row in docs),
                          "excluded": documents.get("excluded", 0),
                          "sources": {status: sum(row["source_status"] == status
                                                  and (status != "no_source" or not row["ui_transcript"])
                                                  for row in videos)
                                      for status in ("caption_file", "asr_ready", "no_source")},
                          "needs_ocr": sum(row["status"] == "needs_ocr" for row in docs),
                          "lesson_packs": sum(bool(row["lesson_pack"]) for row in videos)}}


def source_catalog(source_id: str | None = None, parent_id: str | None = None,
                   offset: int = 0, query: str = "", kind: str = "") -> dict | None:
    """Browse the two filtered scans without loading every video into the web page."""
    if source_id is not None and source_id not in NEW_SOURCE_FOLDERS:
        return None
    if offset < 0 or offset > 500_000 or len(query) > 100 or kind not in {"", "video", "document", "folder"}:
        return None

    def read_source(folder_id: str, summary_only: bool = False) -> dict:
        location = REPORTS / "new-sources" / folder_id
        final = location / "scan.json"
        checkpoint = location / "scan.checkpoint.json"
        path = final if final.is_file() else checkpoint
        signature = (str(path), path.stat().st_mtime_ns, path.stat().st_size) if path.is_file() else None
        cache_key = f"{REPORTS}:{folder_id}:{'summary' if summary_only else 'index'}"
        cached = SOURCE_CACHE.get(cache_key)
        if cached and cached[0] == signature:
            return cached[1]
        report = read_json(path) if signature else {}
        complete = path == final and bool(report)
        if complete:
            folder, items, visited, skipped = report["folder"], report["items"], set(), report.get("exclusions") or {}
        elif report.get("folder_id") == folder_id:
            folder = {"id": folder_id, "name": report.get("root_name", NEW_SOURCE_FOLDERS[folder_id])}
            items, visited, skipped = report["items"], set() if summary_only else set(report["visited"]), report.get("skipped", {})
        else:
            folder, items, visited, skipped = {"id": folder_id, "name": NEW_SOURCE_FOLDERS[folder_id]}, [], set(), {}
        counts = Counter(item["kind"] for item in items)
        summary = {"id": folder_id, "name": folder["name"], "complete": complete,
                   "total": len(items), "counts": dict(counts),
                   "excluded": {"folders": skipped.get("folders", 0),
                                "files": skipped.get("files", 0)}}
        if summary_only:
            snapshot = {"summary": summary}
            SOURCE_CACHE[cache_key] = (signature, snapshot)
            return snapshot
        children = {}
        folders = {}
        for item in items:
            children.setdefault(item["parent_id"], []).append(item)
            if item["kind"] == "folder":
                folders[item["id"]] = item
        for siblings in children.values():
            siblings.sort(key=lambda item: (item["kind"] != "folder", natural_key(item["name"])))
        snapshot = {"folder": folder, "items": items, "visited": visited,
                    "folders": folders, "children": children,
                    "summary": summary}
        SOURCE_CACHE[cache_key] = (signature, snapshot)
        return snapshot

    if source_id is None:
        return {"sources": [read_source(folder_id, summary_only=True)["summary"]
                            for folder_id in NEW_SOURCE_FOLDERS]}

    snapshot = read_source(source_id)
    folder, items, visited = snapshot["folder"], snapshot["items"], snapshot["visited"]
    folders = snapshot["folders"]
    parent_id = parent_id or source_id
    if parent_id != source_id and parent_id not in folders:
        return None
    ancestors = [{"id": source_id, "name": folder["name"]}]
    if parent_id != source_id:
        chain = []
        cursor = parent_id
        while cursor != source_id:
            node = folders.get(cursor)
            if node is None or len(chain) > 30:
                return None
            chain.append({"id": node["id"], "name": node["name"]})
            cursor = node["parent_id"]
        ancestors.extend(reversed(chain))
    if query.strip():
        needle = query.casefold().strip()
        matches = (item for item in items if needle in item["name"].casefold()
                   or needle in item["path"].casefold())
        children = [item for item in matches if not kind or item["kind"] == kind]
        children.sort(key=lambda item: (item["kind"] != "folder", natural_key(item["name"])))
    elif kind in {"video", "document"}:
        prefix = "" if parent_id == source_id else folders[parent_id]["path"] + "/"
        children = [item for item in items if item["kind"] == kind
                    and (not prefix or item["path"].startswith(prefix))]
        children.sort(key=lambda item: natural_key(item["path"]))
    else:
        siblings = snapshot["children"].get(parent_id, [])
        children = [item for item in siblings if item["kind"] == kind] if kind else siblings
    old_ids = {item["id"] for item in read_json(REPORTS / "scan.json", {"items": []})["items"]}
    source_dir = REPORTS / "new-sources" / source_id
    caption_rows = read_json(source_dir / "transcripts/manifest.json", {"files": []})["files"]
    captions_by_video = {row["video_id"]: row["id"] for row in caption_rows
                         if row.get("status") == "ok" and row.get("video_id")}
    transcript_status = {row["id"]: row["status"] for row in caption_rows}
    document_rows = read_json(source_dir / "documents/manifest.json", {"files": []})["files"]
    document_status = {row["id"]: row["status"] for row in document_rows}
    page = [{key: item.get(key) for key in ("id", "name", "kind", "url", "path", "size")}
            | {"already_indexed": item["id"] in old_ids,
               "caption_id": captions_by_video.get(item["id"]),
               "transcript_status": transcript_status.get(item["id"]),
               "document_status": document_status.get(item["id"])}
            for item in children[offset:offset + 200]]
    return {"source": snapshot["summary"],
            "parent_id": parent_id, "ancestors": ancestors, "items": page,
            "total_children": len(children), "offset": offset,
            "parent_scanned": snapshot["summary"]["complete"] or parent_id in visited,
            "query": query.strip(), "kind": kind}


def source_file_content(source_id: str, kind: str, file_id: str) -> dict | None:
    """Read only extracted files listed by one of the approved source manifests."""
    if source_id not in NEW_SOURCE_FOLDERS or kind not in {"transcript", "document"} or not SAFE_ID.fullmatch(file_id):
        return None
    source_dir = REPORTS / "new-sources" / source_id
    section, extension = ("transcripts", ".md") if kind == "transcript" else ("documents", ".txt")
    manifest = read_json(source_dir / section / "manifest.json", {"files": []})
    row = next((entry for entry in manifest.get("files", [])
                if entry.get("id") == file_id and entry.get("status") == "ok"), None)
    if row is None:
        return None
    try:
        path = safe_output_file(source_dir / section, row["output"], extension)
        if not path.is_file():
            return None
        with path.open(encoding="utf-8") as stream:
            content = stream.read(1_000_001)
    except (OSError, KeyError, ValueError):
        return None
    truncated = len(content) > 1_000_000
    return {"title": row.get("name", ""), "kind": kind,
            "document_type": document_type(row.get("name", ""), row.get("mime_type")) if kind == "document" else None,
            "content": content[:1_000_000], "truncated": truncated}


def file_content(kind: str, file_id: str) -> dict | None:
    if not SAFE_ID.fullmatch(file_id):
        return None
    if kind == "ui_transcript":
        scan = read_json(REPORTS / "scan.json")
        video = next((row for row in scan.get("items", [])
                      if row.get("kind") == "video" and row.get("id") == file_id), None)
        result = ui_transcript_data(scan, video) if video else None
        if result is None:
            return None
        rows = result[0]["rows"]
        content = "\n".join([f"# Bản chép lời · {display_name(video['name'])}", "",
                             "> Thu từ giao diện Google Drive. Đối chiếu với video khi cần kiểm tra lời nói.", ""]
                            + [f"- **[{row['at']}]** {row['text']}" for row in rows]) + "\n"
        return {"title": display_name(video["name"]), "kind": kind, "content": content}
    if kind == "transcript":
        manifest = read_json(REPORTS / "transcripts/manifest.json")
        row = next((x for x in manifest.get("files", []) if x["id"] == file_id and x["status"] == "ok"), None)
        path = safe_output_file(REPORTS / "transcripts", row["output"], ".md") if row else None
        title = row["name"] if row else ""
    elif kind == "document":
        manifest = read_json(REPORTS / "documents/manifest.json")
        row = next((x for x in manifest.get("files", []) if x["id"] == file_id and x["status"] == "ok"), None)
        path = safe_output_file(REPORTS / "documents", row["output"], ".txt") if row else None
        title = row["name"] if row else ""
    elif kind == "ai_note":
        manifest = read_json(REPORTS / "transcripts/manifest.json")
        row = next((x for x in manifest.get("files", []) if x["id"] == file_id and x["status"] == "ok"), None)
        if row:
            scan = read_json(REPORTS / "scan.json")
            relative = output_paths(scan, "ai_note").get(file_id)
            path = safe_output_file(REPORTS / "ai-notes", relative, ".md") if relative else None
            if path and not path.is_file():
                path = REPORTS / "ai-notes" / f"{file_id}.md"
        else:
            path = None
        title = row["name"] if row else ""
    elif kind == "lesson_pack":
        manifest = read_json(REPORTS / "transcripts/manifest.json")
        row = next((x for x in manifest.get("files", []) if x["id"] == file_id and x["status"] == "ok"), None)
        path = lesson_pack_file(read_json(REPORTS / "scan.json"), file_id, ".json") if row else None
        if path is None or not path.is_file() or path.stat().st_size > 2_000_000:
            return None
        data = json.loads(path.read_text(encoding="utf-8"))
        chunks = [{key: chunk.get(key) for key in ("chunk_id", "start", "end")} for chunk in data.get("chunks", [])]
        return {"title": row["name"], "kind": kind, "pack": data.get("pack", {}), "qa": data.get("qa", {}),
                "meta": data.get("meta", {}), "chunks": chunks}
    elif kind == "study_note" and file_id in {"14-admin", "claude-ai-hieu-qua"}:
        scan = read_json(REPORTS / "scan.json")
        relative = manual_note_paths(scan).get(file_id)
        path = safe_output_file(REPORTS / "study-notes", relative, ".md") if relative else None
        if path and not path.is_file():
            path = REPORTS / "study-notes" / f"{file_id}.md"
        title = file_id
    elif kind == "study_index" and file_id == "index":
        path = REPORTS / "study-notes/index.md"
        title = "Chỉ mục toàn bộ khóa học"
    elif kind == "video_summaries" and file_id == "video-summaries":
        path = REPORTS / "video-summaries.md"
        title = "Nội dung chi tiết video đã xử lý"
    elif kind == "cross_source_review" and file_id == "cross-source-review":
        path = REPORTS / "cross-source/review.md"
        title = "Cần xem lại giữa phụ đề và tài liệu"
    elif kind == "course_summary":
        note = next((row for row in library()["notes"] if row["type"] == kind and row["id"] == file_id), None)
        path = safe_output_file(REPORTS / "courses", Path(note["course"]) / "course_summary.md", ".md") if note else None
        title = note["name"] if note else ""
    elif kind == "progressive_note":
        note = next((row for row in library()["notes"] if row["type"] == kind and row["id"] == file_id), None)
        scan = read_json(REPORTS / "scan.json")
        video = next((row for row in scan.get("items", [])
                      if row.get("kind") == "video" and row.get("id") == file_id), None)
        path = progressive_note_file(scan, video, ".md") if note and video else None
        title = note["name"] if note else ""
    else:
        return None
    if path is None or not path.is_file() or path.stat().st_size > 2_000_000:
        return None
    content = {"title": title, "kind": kind, "content": path.read_text(encoding="utf-8")}
    if kind == "document":
        content["document_type"] = document_type(row["name"], row.get("mime_type"))
    return content


def command_for(action: str, caption_id: str | None = None) -> list[str]:
    base = [sys.executable]
    if action == "scan":
        return base + ["drive_scan.py", configured_folder_id()]
    if action == "captions":
        return base + ["drive_process.py"]
    if action == "documents":
        return base + ["drive_documents.py", "--max-mb", "30", "--ocr"]
    if action in {"note", "lesson_pack"} and isinstance(caption_id, str) and SAFE_ID.fullmatch(caption_id):
        manifest = read_json(REPORTS / "transcripts/manifest.json")
        if any(row["id"] == caption_id and row["status"] == "ok" for row in manifest.get("files", [])):
            script = "codex_notes.py" if action == "note" else "lesson_pack.py"
            return base + [script, "--id", caption_id]
    raise ValueError("Tác vụ hoặc ID phụ đề không hợp lệ")


def start_job(action: str, caption_id: str | None = None) -> dict:
    command = command_for(action, caption_id)
    with JOBS_LOCK:
        if any(row["status"] == "running" for row in JOBS):
            raise RuntimeError("Một tác vụ khác đang chạy. Hãy đợi tác vụ đó hoàn thành.")
        job = {"id": secrets.token_hex(6), "action": action, "caption_id": caption_id,
               "status": "running", "started": datetime.now(timezone.utc).isoformat(),
               "finished": None, "exit_code": None, "output": ""}
        JOBS.insert(0, job)
        del JOBS[20:]

    def run() -> None:
        env = os.environ.copy()
        env["PYTHONPATH"] = str(ROOT / ".deps") + os.pathsep + env.get("PYTHONPATH", "")
        try:
            result = subprocess.run(command, cwd=ROOT, env=env, text=True,
                                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                    timeout=1800, check=False)
            output = result.stdout[-6000:]
            exit_code = result.returncode
            if exit_code == 0 and action in {"captions", "documents", "note"} and all(
                (REPORTS / section / "manifest.json").is_file() for section in ("transcripts", "documents")
            ):
                index_result = subprocess.run([sys.executable, "study_pack.py"], cwd=ROOT,
                                              env=env, text=True, stdout=subprocess.PIPE,
                                              stderr=subprocess.STDOUT, timeout=120, check=False)
                output = (output + "\n" + index_result.stdout)[-6000:]
                exit_code = index_result.returncode
            # lesson_pack.py exits 2 when the pack was saved but still needs human review
            status = "done" if exit_code == 0 or (action == "lesson_pack" and exit_code == 2) else "failed"
        except subprocess.TimeoutExpired:
            output, status, exit_code = "Tác vụ vượt thời hạn 30 phút.", "failed", -1
        except OSError as exc:
            output, status, exit_code = str(exc), "failed", -1
        with JOBS_LOCK:
            job.update(status=status, finished=datetime.now(timezone.utc).isoformat(),
                       exit_code=exit_code, output=output)

    Thread(target=run, daemon=True).start()
    return dict(job)


class Handler(BaseHTTPRequestHandler):
    server_version = "DriveStudio/1.0"

    def log_message(self, format: str, *args) -> None:
        return

    def respond(self, status: int, body: bytes, content_type: str) -> None:
        try:
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Content-Security-Policy", "default-src 'self'; img-src 'self' data:; "
                             "style-src 'self'; script-src 'self'; connect-src 'self'; "
                             "frame-src https://drive.google.com; "
                             "base-uri 'none'; frame-ancestors 'none'")
            self.end_headers()
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError):
            # The browser left before receiving the response; the server can serve the next request.
            return

    def json_response(self, status: int, value: dict) -> None:
        self.respond(status, json.dumps(value, ensure_ascii=False).encode("utf-8"),
                     "application/json; charset=utf-8")

    def allowed_host(self) -> bool:
        return self.headers.get("Host", "").split(":")[0] in {"127.0.0.1", "localhost"}

    def do_GET(self) -> None:
        if not self.allowed_host():
            self.json_response(403, {"error": "Chỉ cho phép truy cập từ máy này"})
            return
        route = urlparse(self.path).path
        if route in {"/", "/styles.css", "/app.js"}:
            filename = "index.html" if route == "/" else route[1:]
            mime = "text/html" if filename.endswith(".html") else (
                "text/css" if filename.endswith(".css") else "text/javascript")
            self.respond(200, (WEB / filename).read_bytes(), mime + "; charset=utf-8")
            return
        if route == "/api/bootstrap":
            self.json_response(200, {"token": TOKEN})
        elif route == "/api/library":
            self.json_response(200, library())
        elif route == "/api/source-catalog":
            query = parse_qs(urlparse(self.path).query)
            try:
                offset = int(query.get("offset", ["0"])[0])
            except ValueError:
                offset = -1
            result = source_catalog(query.get("source", [None])[0],
                                    query.get("parent", [None])[0], offset,
                                    query.get("q", [""])[0], query.get("kind", [""])[0])
            self.json_response(200, result) if result else self.json_response(404, {"error": "Nguồn Drive không tồn tại"})
        elif route == "/api/source-file":
            query = parse_qs(urlparse(self.path).query)
            result = source_file_content(query.get("source", [""])[0],
                                         query.get("kind", [""])[0], query.get("id", [""])[0])
            self.json_response(200, result) if result else self.json_response(404, {"error": "Không tìm thấy nội dung"})
        elif route == "/api/jobs":
            with JOBS_LOCK:
                self.json_response(200, {"jobs": [dict(row) for row in JOBS]})
        elif route == "/api/file":
            query = parse_qs(urlparse(self.path).query)
            result = file_content(query.get("kind", [""])[0], query.get("id", [""])[0])
            self.json_response(200, result) if result else self.json_response(404, {"error": "Không tìm thấy nội dung"})
        else:
            self.json_response(404, {"error": "Đường dẫn không tồn tại"})

    def do_POST(self) -> None:
        if not self.allowed_host() or self.headers.get("X-Drive-Studio-Token") != TOKEN:
            self.json_response(403, {"error": "Yêu cầu không hợp lệ"})
            return
        if urlparse(self.path).path != "/api/jobs":
            self.json_response(404, {"error": "Đường dẫn không tồn tại"})
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length < 1 or length > 4096:
                raise ValueError("Kích thước yêu cầu không hợp lệ")
            data = json.loads(self.rfile.read(length))
            if not isinstance(data, dict):
                raise ValueError("Yêu cầu phải là một đối tượng JSON")
            job = start_job(data.get("action", ""), data.get("caption_id"))
            self.json_response(202, job)
        except (ValueError, json.JSONDecodeError) as exc:
            self.json_response(400, {"error": str(exc)})
        except RuntimeError as exc:
            self.json_response(409, {"error": str(exc)})


def main() -> None:
    parser = argparse.ArgumentParser(description="Giao diện quản lý Google Drive trên máy cá nhân")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    print(f"Drive Studio đang chạy tại http://127.0.0.1:{server.server_port}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
