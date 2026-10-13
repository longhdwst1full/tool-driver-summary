#!/usr/bin/env python3
"""Summarize verified priority transcripts as capture produces them.

Run beside ``full_priority_queue.py --phase capture``. A single process owns
the Codex queue; SQLite statuses allow restarting without repeating good notes.
"""

from __future__ import annotations

import argparse
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from collections import deque
import fcntl
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import time

from batch_ui_lessons import quota_limited
from full_priority_queue import DB, REPORTS, connect, mark, source_videos, source_videos_folder
from getsub_demo import format_time, parse_captions
from llm_client import CodexCLIClient, find_codex
from output_layout import safe_output_file, video_title
from progressive_demo import build_progressive, render_markdown
from web_app import source_note_path, source_video_status


LOCK = REPORTS / "priority-summary.lock"
PRIORITY_SERVICE = "tool-getsub-priority-verified.service"


def priority_course_busy() -> bool:
    return subprocess.run(
        ["systemctl", "--user", "is-active", "--quiet", PRIORITY_SERVICE],
        check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    ).returncode == 0


def ready_rows(db: sqlite3.Connection, *, include_priority: bool) -> list[tuple[str, str]]:
    priority_filter = "" if include_priority else " AND priority > 0"
    return db.execute(
        "SELECT source_id, video_id FROM ("
        "SELECT source_id, video_id, priority, category, "
        "ROW_NUMBER() OVER (PARTITION BY priority, category "
        "ORDER BY updated_at, source_id, video_id) AS category_rank FROM work "
        "WHERE capture_status='captured' AND summary_status='queued'"
        + priority_filter + ") ORDER BY priority, category_rank, category LIMIT 50"
    ).fetchall()


def claim(db: sqlite3.Connection, source: str, video_id: str) -> bool:
    with db:
        changed = db.execute(
            "UPDATE work SET summary_status='running' "
            "WHERE source_id=? AND video_id=? AND capture_status='captured' "
            "AND summary_status='queued'", (source, video_id),
        ).rowcount
    return bool(changed)


def summarize_one(db: sqlite3.Connection, source: str, video: dict,
                  client: CodexCLIClient) -> str:
    video_id = video["id"]
    source_dir = REPORTS / "new-sources" / source
    mini_scan = {"folder": source_videos_folder(source), "items": [video]}
    transcript, note = source_video_status(source, video_id, mini_scan, video)
    if note:
        mark(db, source, video_id, summary="done")
        return "already"
    if not transcript:
        mark(db, source, video_id, capture="failed", summary="failed",
             error="Bản chép lời đã lưu không còn hợp lệ")
        return "invalid_transcript"

    srt = safe_output_file(source_dir / "ui-transcripts", video_id + ".srt", ".srt")
    parsed = parse_captions(srt.read_text(encoding="utf-8"))
    cues = [(format_time(cue.start_ms), format_time(cue.end_ms), cue.text) for cue in parsed]
    result = build_progressive(client, video_title(video["name"]), video_id, cues)
    result["source_kind"] = "drive_ui_transcript"
    output = source_note_path(source_dir, mini_scan, video, ".md")
    data_output = source_note_path(source_dir, mini_scan, video, ".json")
    if output is None or data_output is None:
        raise ValueError("Không xác định được đường dẫn bài học")
    output.parent.mkdir(parents=True, exist_ok=True)
    link = os.path.relpath(srt, output.parent)
    for target, content in (
        (data_output, json.dumps(result, ensure_ascii=False, indent=2) + "\n"),
        (output, render_markdown(result, video["url"], link)),
    ):
        temporary = target.with_name(target.name + ".tmp")
        temporary.write_text(content, encoding="utf-8")
        temporary.replace(target)
    if not source_video_status(source, video_id, mini_scan, video)[1]:
        raise ValueError("Bài học không qua kiểm tra dẫn nguồn")
    mark(db, source, video_id, summary="done")
    return "created"


def summary_task(source: str, video: dict) -> str:
    """Each thread owns its connection and Codex client."""
    db = connect()
    try:
        return summarize_one(db, source, video, CodexCLIClient(find_codex(None)))
    finally:
        db.close()


def process_ready(db, video_map, *, workers=1, max_new=None, once=False,
                  poll_seconds=20, task=summary_task) -> int:
    """Bound submissions and drain active work before releasing the queue lock."""
    created = 0
    stopped = False
    pending = {}
    batch = deque()
    with ThreadPoolExecutor(max_workers=workers) as pool:
        while True:
            capacity = workers - len(pending)
            if max_new is not None:
                capacity = min(capacity, max_new - created - len(pending))
            if not stopped and capacity > 0:
                if not batch:
                    batch.extend(ready_rows(db, include_priority=not priority_course_busy()))
                while batch and capacity > 0:
                    source, video_id = batch.popleft()
                    video = video_map.get((source, video_id))
                    if video is None or not claim(db, source, video_id):
                        continue
                    pending[pool.submit(task, source, video)] = (source, video_id)
                    capacity -= 1
            if not pending:
                if stopped or (max_new is not None and created >= max_new) or once:
                    return created
                time.sleep(poll_seconds)
                continue
            completed, _ = wait(pending, return_when=FIRST_COMPLETED)
            for future in completed:
                source, video_id = pending.pop(future)
                try:
                    outcome = future.result()
                    if outcome == "created":
                        created += 1
                    print(f"{source[:8]} {video_id}: {outcome}", flush=True)
                except Exception as exc:
                    error = str(exc)
                    limited = quota_limited(error)
                    mark(db, source, video_id,
                         summary="queued" if limited else "failed", error=error)
                    print(f"{source[:8]} {video_id}: summary failed: {error[:180]}", flush=True)
                    if limited:
                        stopped = True
                        print("Hết hạn mức Codex CLI; chờ các lượt đang chạy kết thúc rồi dừng.", flush=True)


def main() -> int:
    parser = argparse.ArgumentParser(description="Tóm tắt liên tục các bản chép lời ưu tiên đã thu")
    parser.add_argument("--once", action="store_true", help="Xử lý mọi bản đã sẵn sàng rồi thoát")
    parser.add_argument("--max-new", type=int, help="Giới hạn lượt tạo AI để chạy thử")
    parser.add_argument("--poll-seconds", type=int, default=20)
    parser.add_argument("--workers", type=int, choices=(1, 2), default=1,
                        help="Số video tóm tắt song song (mặc định 1, tối đa 2)")
    args = parser.parse_args()
    if args.max_new is not None and args.max_new < 1:
        parser.error("--max-new phải dương")
    if args.poll_seconds < 1:
        parser.error("--poll-seconds phải dương")

    LOCK.parent.mkdir(parents=True, exist_ok=True)
    with LOCK.open("a+") as lock_file:
        try:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            print("Đã có worker tóm tắt ưu tiên đang chạy", flush=True)
            return 0
        db = connect()
        try:
            # A sole coordinator owns recovery, claims and scheduling.
            with db:
                db.execute("UPDATE work SET summary_status='queued' WHERE summary_status='running'")
            _, videos = source_videos()
            video_map = {(source, video["id"]): video for source, video, _, _ in videos}
            process_ready(db, video_map, workers=args.workers, max_new=args.max_new,
                          once=args.once, poll_seconds=args.poll_seconds)
        finally:
            db.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
