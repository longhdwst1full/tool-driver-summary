#!/usr/bin/env python3
"""Resume transcript checks and cited summaries for every IT/business/investing video."""

from __future__ import annotations

import argparse
from collections import deque
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from datetime import datetime, timezone
import importlib.util
import json
import os
from pathlib import Path
import sqlite3
import sys
import threading

from batch_ui_lessons import quota_limited, readable_ui
from getsub_demo import format_time, parse_captions
from import_ui_transcript import make_srt, validate_export
from llm_client import CodexCLIClient, find_codex
from output_layout import safe_output_file, video_title
from priority_courses import SOURCE_A, SOURCE_B, TARGETS
from progressive_demo import build_progressive, render_markdown
from web_app import source_note_path, source_video_status


ROOT = Path(__file__).resolve().parent
REPORTS = ROOT / "drive-reports"
DB = REPORTS / "full-priority-queue.sqlite"
GROUPS = ("công nghệ thông tin", "kinh doanh", "đầu tư")


def source_videos() -> tuple[dict[str, dict], list[tuple[str, dict, str, int]]]:
    scans = {}
    videos = []
    targets = {(source, folder) for source, folder, _ in TARGETS}
    for source_id in (SOURCE_A, SOURCE_B):
        source_dir = REPORTS / "new-sources" / source_id
        scan = json.loads((source_dir / "scan.json").read_text(encoding="utf-8"))
        scans[source_id] = scan
        folders = {item["id"]: item["path"] for item in scan["items"] if item["kind"] == "folder"}
        priority_paths = [folders[folder] + "/" for sid, folder in targets if sid == source_id]
        for video in scan["items"]:
            if video["kind"] != "video":
                continue
            parts = video["path"].split("/")
            category = parts[1] if len(parts) > 1 else ""
            if not any(group in category.casefold() for group in GROUPS):
                continue
            priority = 0 if any(video["path"].startswith(path) for path in priority_paths) else 1
            videos.append((source_id, video, category, priority))
    videos.sort(key=lambda entry: (entry[3], entry[0], entry[1]["path"].casefold()))
    # Rotate categories, sources, and courses independently so a large course
    # cannot hold every browser worker while other categories wait.
    def interleave(streams):
        pending = deque(iter(stream) for stream in streams)
        while pending:
            stream = pending.popleft()
            try:
                yield next(stream)
            except StopIteration:
                continue
            pending.append(stream)

    ordered = []
    for priority in sorted({entry[3] for entry in videos}):
        category_streams = []
        for group in GROUPS:
            source_streams = []
            for source_id in (SOURCE_A, SOURCE_B):
                courses = {}
                for entry in videos:
                    if entry[3] != priority or entry[0] != source_id or group not in entry[2].casefold():
                        continue
                    # Inventory paths contain root/category/subcategory/course.
                    course = "/".join(entry[1]["path"].split("/")[:4])
                    courses.setdefault(course, []).append(entry)
                source_streams.append(interleave(courses.values()))
            category_streams.append(interleave(source_streams))
        ordered.extend(interleave(category_streams))
    return scans, ordered


def connect() -> sqlite3.Connection:
    DB.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(DB)
    db.execute("PRAGMA journal_mode=WAL")
    # WAL + NORMAL keeps the database consistent after a crash; only skips fsync per commit.
    db.execute("PRAGMA synchronous=NORMAL")
    db.execute("""CREATE TABLE IF NOT EXISTS work (
        source_id TEXT NOT NULL, video_id TEXT NOT NULL, category TEXT NOT NULL,
        priority INTEGER NOT NULL, capture_status TEXT NOT NULL DEFAULT 'queued',
        summary_status TEXT NOT NULL DEFAULT 'queued', rows INTEGER NOT NULL DEFAULT 0,
        attempts INTEGER NOT NULL DEFAULT 0, error TEXT NOT NULL DEFAULT '',
        updated_at TEXT NOT NULL DEFAULT '', PRIMARY KEY (source_id, video_id))""")
    return db


def initialize(db: sqlite3.Connection, videos: list[tuple[str, dict, str, int]]) -> None:
    with db:
        db.executemany("""INSERT OR IGNORE INTO work
            (source_id, video_id, category, priority) VALUES (?, ?, ?, ?)""",
            ((source, video["id"], category, priority)
             for source, video, category, priority in videos))


def mark(db: sqlite3.Connection, source: str, video_id: str, *, capture: str | None = None,
         summary: str | None = None, rows: int | None = None, error: str = "",
         attempt: bool = False) -> None:
    fields = ["updated_at=?", "error=?"]
    values: list[object] = [datetime.now(timezone.utc).isoformat(), error[:800]]
    if capture is not None:
        fields.append("capture_status=?")
        values.append(capture)
    if summary is not None:
        fields.append("summary_status=?")
        values.append(summary)
    if rows is not None:
        fields.append("rows=?")
        values.append(rows)
    if attempt:
        fields.append("attempts=attempts+1")
    with db:
        db.execute(f"UPDATE work SET {', '.join(fields)} WHERE source_id=? AND video_id=?",
                   (*values, source, video_id))


def load_capture():
    path = ROOT / "browser-demo/background_capture.py"
    spec = importlib.util.spec_from_file_location("getsub_background_capture", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module.capture


def write_transcript(source: str, video: dict, data: dict) -> int:
    video_id, rows = validate_export(data, {"items": [video]})
    srt = make_srt(rows)
    ui_dir = REPORTS / "new-sources" / source / "ui-transcripts"
    ui_dir.mkdir(parents=True, exist_ok=True)
    for extension, content in ((".srt", srt),
                               (".json", json.dumps(data, ensure_ascii=False) + "\n")):
        target = safe_output_file(ui_dir, video_id + extension, extension)
        temporary = target.with_name(target.name + ".tmp")
        temporary.write_text(content, encoding="utf-8")
        temporary.replace(target)
    return len(rows)


def capture_all(db: sqlite3.Connection, videos: list[tuple[str, dict, str, int]],
                limit: int | None, retry_unavailable: bool, workers: int = 2) -> None:
    capture = None
    submitted = 0
    pending = {}
    video_iter = iter(videos)
    # One read instead of a SELECT per video; each video is visited once per run.
    known = {(row[0], row[1]): (row[2], row[3]) for row in db.execute(
        "SELECT source_id, video_id, capture_status, attempts FROM work")}
    local = threading.local()
    sessions = []
    sessions_lock = threading.Lock()

    def new_session(factory):
        session = factory(Path.home() / ".config/google-chrome", "Default")
        local.capture_session = session
        with sessions_lock:
            sessions.append(session)
        return session

    def capture_one(source: str, video: dict) -> int:
        factory = getattr(capture, "session_factory", None)
        if factory is None:
            data = capture(video["id"], Path.home() / ".config/google-chrome", "Default")
            return write_transcript(source, video, data)
        session = getattr(local, "capture_session", None)
        if session is None:
            session = new_session(factory)
        try:
            data = session.capture(video["id"])
        except Exception as exc:
            reset_errors = getattr(capture, "reset_session_errors", ())
            if reset_errors and isinstance(exc, reset_errors):
                session.close()
                local.capture_session = None
                session = new_session(factory)
                try:
                    data = session.capture(video["id"])
                except Exception:
                    session.close()
                    local.capture_session = None
                    raise
                return write_transcript(source, video, data)
            # These failures describe the current Drive video, not the Chrome
            # process. Reuse the authenticated session for the next item.
            if isinstance(exc, (TimeoutError, ValueError)):
                raise
            session.close()
            local.capture_session = None
            raise
        return write_transcript(source, video, data)

    def submit_next(pool: ThreadPoolExecutor) -> bool:
        nonlocal capture, submitted
        for source, video, _, _ in video_iter:
            if limit is not None and submitted >= limit:
                return False
            status, attempts = known[(source, video["id"])]
            if "suno" in video.get("path", "").casefold():
                if status != "excluded":
                    mark(db, source, video["id"], capture="excluded", summary="excluded",
                         error="Bỏ qua nội dung Suno/âm nhạc theo yêu cầu")
                continue
            if status == "excluded":
                continue
            if status == "access_denied":
                continue
            if status in {"captured", "caption_ready"}:
                continue
            if status in {"panel_unavailable", "failed"} and not (retry_unavailable and attempts < 2):
                continue
            source_dir = REPORTS / "new-sources" / source
            cues = readable_ui({"items": [video]}, video, source_dir / "ui-transcripts")
            if cues:
                mark(db, source, video["id"], capture="captured", rows=len(cues))
                continue
            if capture is None:
                capture = load_capture()
            mark(db, source, video["id"], capture="running", attempt=True)
            pending[pool.submit(capture_one, source, video)] = (source, video)
            submitted += 1
            return True
        return False

    with ThreadPoolExecutor(max_workers=workers) as pool:
        for _ in range(workers):
            if not submit_next(pool):
                break
        while pending:
            finished, _ = wait(pending, return_when=FIRST_COMPLETED)
            for future in finished:
                source, video = pending.pop(future)
                try:
                    rows = future.result()
                    mark(db, source, video["id"], capture="captured", rows=rows)
                    print(f"{source[:8]} {video['id']}: captured ({rows} dòng)", flush=True)
                except Exception as exc:
                    error = str(exc)
                    unavailable = "Bản chép lời không khả dụng" in error
                    access_denied_errors = getattr(capture, "access_denied_errors", ())
                    mark(db, source, video["id"],
                         capture=("access_denied" if access_denied_errors
                                  and isinstance(exc, access_denied_errors)
                                  else "panel_unavailable" if unavailable else "failed"),
                         error=error)
                    print(f"{source[:8]} {video['id']}: {error[:180]}", flush=True)
                submit_next(pool)
    for session in sessions:
        session.close()


def summarize_all(db: sqlite3.Connection, videos: list[tuple[str, dict, str, int]],
                  limit: int | None, extract_workers: int = 1) -> None:
    client = None
    completed = 0
    for source, video, _, _ in videos:
        capture_status, summary_status = db.execute(
            "SELECT capture_status, summary_status FROM work WHERE source_id=? AND video_id=?",
            (source, video["id"])).fetchone()
        if capture_status != "captured" or summary_status == "done":
            continue
        if limit is not None and completed >= limit:
            break
        source_dir = REPORTS / "new-sources" / source
        mini_scan = {"folder": source_videos_folder(source), "items": [video]}
        transcript, note = source_video_status(source, video["id"], mini_scan, video)
        if note:
            mark(db, source, video["id"], summary="done")
            continue
        if not transcript:
            mark(db, source, video["id"], capture="failed", error="Bản chép lời lưu trên máy không hợp lệ")
            continue
        srt = safe_output_file(source_dir / "ui-transcripts", video["id"] + ".srt", ".srt")
        parsed = parse_captions(srt.read_text(encoding="utf-8"))
        cues = [(format_time(c.start_ms), format_time(c.end_ms), c.text) for c in parsed]
        if client is None:
            client = CodexCLIClient(find_codex(None))
        mark(db, source, video["id"], summary="running")
        try:
            result = build_progressive(client, video_title(video["name"]), video["id"], cues,
                                       workers=extract_workers)
            result["source_kind"] = "drive_ui_transcript"
            output = source_note_path(source_dir, mini_scan, video, ".md")
            data_output = source_note_path(source_dir, mini_scan, video, ".json")
            assert output and data_output
            output.parent.mkdir(parents=True, exist_ok=True)
            link = os.path.relpath(srt, output.parent)
            data_output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            output.write_text(render_markdown(result, video["url"], link), encoding="utf-8")
            if not source_video_status(source, video["id"], mini_scan, video)[1]:
                raise ValueError("Tóm tắt không qua kiểm tra nguồn")
            mark(db, source, video["id"], summary="done")
            print(f"{source[:8]} {video['id']}: summary done", flush=True)
        except Exception as exc:
            error = str(exc)
            mark(db, source, video["id"], summary="failed", error=error)
            print(f"{source[:8]} {video['id']}: summary failed: {error[:180]}", flush=True)
            if quota_limited(error):
                print("Hết hạn mức Codex CLI; dừng để chạy tiếp khi có hạn mức.", flush=True)
                break
        completed += 1


def source_videos_folder(source: str) -> dict:
    return {"id": source, "name": "Khóa Học Giá Hời 2026" if source == SOURCE_A else "Khóa Học Giá Hời 2026 2"}


def status(db: sqlite3.Connection) -> dict:
    return {
        "capture": dict(db.execute("SELECT capture_status, COUNT(*) FROM work GROUP BY capture_status")),
        "summary": dict(db.execute("SELECT summary_status, COUNT(*) FROM work GROUP BY summary_status")),
        "total": db.execute("SELECT COUNT(*) FROM work").fetchone()[0],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Check 25.517 video và tạo tóm tắt có dẫn nguồn")
    parser.add_argument("--phase", choices=("capture", "summary", "all", "status"), default="all")
    parser.add_argument("--limit", type=int, help="Giới hạn số video mới trong mỗi pha để thử")
    parser.add_argument("--retry-unavailable", action="store_true")
    parser.add_argument("--workers", type=int, default=3,
                        help="Số Chrome thu lời đồng thời (mặc định: 3, tối đa: 6)")
    parser.add_argument("--extract-workers", type=int, default=4, choices=range(1, 7),
                        help="Số đoạn của một video gửi Codex song song (1 = tuần tự)")
    args = parser.parse_args()
    if args.limit is not None and args.limit < 1:
        parser.error("--limit phải dương")
    if not 1 <= args.workers <= 6:
        parser.error("--workers phải từ 1 đến 6")
    db = connect()
    scans, videos = source_videos() if args.phase != "status" else ({}, [])
    if videos:
        initialize(db, videos)
        if len(videos) != 25517:
            raise RuntimeError(f"Số video ưu tiên thay đổi: {len(videos)}; cần kiểm tra nguồn")
    if args.phase == "status":
        print(json.dumps(status(db), ensure_ascii=False), flush=True)
        db.close()
        return 0
    print(json.dumps(status(db), ensure_ascii=False), flush=True)
    if args.phase in {"capture", "all"}:
        capture_all(db, videos, args.limit, args.retry_unavailable, args.workers)
    if args.phase in {"summary", "all"}:
        summarize_all(db, videos, args.limit, args.extract_workers)
    print(json.dumps(status(db), ensure_ascii=False), flush=True)
    db.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
