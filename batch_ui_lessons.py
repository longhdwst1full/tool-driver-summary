#!/usr/bin/env python3
"""Resume capture and cited AI notes for scanned videos without caption files."""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import subprocess
import sys
from threading import Event, Lock

from getsub_demo import parse_captions
from import_ui_transcript import validate_export
from web_app import progressive_note_summary


ROOT = Path(__file__).resolve().parent
REPORTS = ROOT / "drive-reports"


def quota_limited(output: str) -> bool:
    return any(marker in output.casefold() for marker in
               ("you’ve hit your usage limit", "you've hit your usage limit",
                "usage limit", "rate limit exceeded", "insufficient_quota")) or bool(
                    re.search(r"(?:again|gain) at \d{1,2}:\d{2} [AP]M\.", output))


def readable_ui(scan: dict, video: dict) -> list | None:
    video_id = video["id"]
    source = REPORTS / "ui-transcripts"
    json_path = source / f"{video_id}.json"
    srt_path = source / f"{video_id}.srt"
    if not json_path.is_file() or not srt_path.is_file():
        return None
    try:
        data = json.loads(json_path.read_text(encoding="utf-8"))
        validate_export(data, scan)
        cues = parse_captions(srt_path.read_text(encoding="utf-8"))
        if len(cues) == data["rowCount"]:
            return cues
    except (OSError, ValueError, KeyError, TypeError):
        pass
    return None


def save_manifest(path: Path, scan: dict, entries: dict[str, dict]) -> None:
    counts = {status: sum(row["status"] == status for row in entries.values())
              for status in ("queued", "running", "done", "captured", "ai_waiting",
                             "no_transcript", "failed")}
    payload = {"folder_id": scan["folder"]["id"], "updated_at": datetime.now(timezone.utc).isoformat(),
               "counts": counts, "videos": entries}
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def main() -> int:
    parser = argparse.ArgumentParser(description="Đọc bản chép lời và tạo bài học AI theo toàn bộ video đã quét")
    parser.add_argument("--scan", type=Path, default=REPORTS / "scan.json")
    parser.add_argument("--manifest", type=Path, default=REPORTS / "ui-transcripts/batch-manifest.json")
    parser.add_argument("--workers", type=int, default=2)
    parser.add_argument("--limit", type=int)
    parser.add_argument("--course", help="Chỉ xử lý một khóa học")
    parser.add_argument("--ai", action="store_true", help="Tạo bài học bằng Codex CLI sau khi thu")
    parser.add_argument("--missing-only", action="store_true",
                        help="Chỉ thử lại video chưa có bản chép lời hợp lệ")
    parser.add_argument("--reconcile-only", action="store_true",
                        help="Cập nhật trạng thái từ file đã lưu, không gọi Chrome hoặc AI")
    args = parser.parse_args()
    if not 1 <= args.workers <= 3 or (args.limit is not None and args.limit < 1):
        parser.error("--workers phải từ 1 đến 3 và --limit phải lớn hơn 0")
    scan = json.loads(args.scan.read_text(encoding="utf-8"))
    caption_manifest = json.loads((REPORTS / "transcripts/manifest.json").read_text(encoding="utf-8"))
    caption_ids = {row["id"] for row in caption_manifest["files"] if row["status"] == "ok"}
    videos = [item for item in scan["items"] if item["kind"] == "video"
              and not any(row["id"] in caption_ids for row in item.get("transcript_files", []))
              and (not args.course or args.course in item["path"].split("/"))]
    if args.limit:
        videos = videos[:args.limit]
    if args.missing_only:
        videos = [video for video in videos if readable_ui(scan, video) is None]
    old = json.loads(args.manifest.read_text(encoding="utf-8")) if args.manifest.is_file() else {}
    entries = dict(old.get("videos", {})) if old.get("folder_id") == scan["folder"]["id"] else {}
    lock = Lock()
    quota_event = Event()
    for item in videos:
        entries.setdefault(item["id"], {"status": "queued", "rows": 0})

    def mark(video_id: str, status: str, **extra: object) -> None:
        with lock:
            row = {**entries.get(video_id, {}), "status": status, **extra,
                   "updated_at": datetime.now(timezone.utc).isoformat()}
            if status in {"done", "captured", "running"}:
                row.pop("error", None)
            entries[video_id] = row
            save_manifest(args.manifest, scan, entries)
        print(f"{video_id}: {status}", flush=True)

    for video in videos:
        video_id = video["id"]
        row = entries[video_id]
        if row["status"] == "failed" and quota_limited(row.get("error", "")):
            cues = readable_ui(scan, video)
            if cues:
                row.update(status="ai_waiting", rows=len(cues),
                           error="Đã có bản chép lời; chờ hạn mức Codex CLI để tạo bài học AI")
    save_manifest(args.manifest, scan, entries)
    if args.reconcile_only:
        print(json.dumps({"selected": len(videos), "counts": read_counts(args.manifest)},
                         ensure_ascii=False), flush=True)
        return 0

    def process(video: dict) -> None:
        video_id = video["id"]
        cues = readable_ui(scan, video)
        if cues and progressive_note_summary(scan, video, cues):
            mark(video_id, "done", rows=len(cues))
            return
        if cues and not args.ai:
            if entries[video_id]["status"] not in {"ai_waiting", "done"}:
                mark(video_id, "captured", rows=len(cues))
            return
        if cues is None:
            mark(video_id, "running")
        if cues is None:
            capture = subprocess.run([sys.executable, str(ROOT / "browser-demo/background_capture.py"),
                                      "--video-id", video_id], cwd=ROOT, capture_output=True,
                                     text=True, timeout=420, check=False)
            if capture.returncode:
                status = "no_transcript" if "Bản chép lời không khả dụng" in capture.stderr else "failed"
                mark(video_id, status, error=(capture.stderr or capture.stdout)[-300:].strip())
                return
            cues = readable_ui(scan, video)
            if cues is None:
                mark(video_id, "failed", error="Bản thu không vượt qua kiểm tra đầu/cuối")
                return
            mark(video_id, "captured", rows=len(cues))
        if not args.ai:
            return
        if quota_event.is_set():
            mark(video_id, "ai_waiting", rows=len(cues),
                 error="Đã có bản chép lời; chờ hạn mức Codex CLI để tạo bài học AI")
            return
        mark(video_id, "running", rows=len(cues))
        command = [sys.executable, str(ROOT / "progressive_demo.py"), "--ui-video-id", video_id]
        if not progressive_note_summary(scan, video, cues):
            command.append("--refresh")
        ai = subprocess.run(command, cwd=ROOT, capture_output=True, text=True,
                            timeout=2400, check=False)
        if ai.returncode and quota_limited(ai.stderr + "\n" + ai.stdout):
            quota_event.set()
            mark(video_id, "ai_waiting", rows=len(cues),
                 error="Đã có bản chép lời; chờ hạn mức Codex CLI để tạo bài học AI")
            return
        if ai.returncode or not progressive_note_summary(scan, video, cues):
            mark(video_id, "failed", rows=len(cues), error=(ai.stderr or ai.stdout)[-300:].strip())
            return
        mark(video_id, "done", rows=len(cues))

    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {pool.submit(process, video): video["id"] for video in videos}
        for future in as_completed(futures):
            try:
                future.result()
            except (OSError, ValueError, subprocess.TimeoutExpired) as exc:
                mark(futures[future], "failed", error=str(exc)[:300])
    counts = read_counts(args.manifest)
    print(json.dumps({"selected": len(videos), "counts": counts}, ensure_ascii=False), flush=True)
    return 0 if not counts["failed"] else 2


def read_counts(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))["counts"]


if __name__ == "__main__":
    raise SystemExit(main())
