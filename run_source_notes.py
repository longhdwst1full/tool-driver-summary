#!/usr/bin/env python3
"""Generate cited AI notes from verified Drive UI transcripts without touching capture state."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys

from batch_ui_lessons import quota_limited, readable_ui
from web_app import NEW_SOURCE_FOLDERS, source_video_status


ROOT = Path(__file__).resolve().parent


def main() -> int:
    parser = argparse.ArgumentParser(description="Tạo bài học AI từ bản chép lời Drive đã thu")
    parser.add_argument("--source-id", required=True, choices=NEW_SOURCE_FOLDERS)
    parser.add_argument("--course", help="Chỉ xử lý video thuộc thư mục khóa hoặc chương này")
    parser.add_argument("--limit", type=int)
    args = parser.parse_args()
    if args.limit is not None and args.limit < 1:
        parser.error("--limit phải lớn hơn 0")

    source_dir = ROOT / "drive-reports/new-sources" / args.source_id
    scan_path = source_dir / "scan.json"
    scan = json.loads(scan_path.read_text(encoding="utf-8"))
    videos = [item for item in scan["items"] if item.get("kind") == "video"
              and (not args.course or args.course in item["path"].split("/"))]
    if args.limit:
        videos = videos[:args.limit]

    counts = {"ready": 0, "already": 0, "created": 0, "unavailable": 0, "failed": 0}
    for video in videos:
        video_id = video["id"]
        cues = readable_ui(scan, video, source_dir / "ui-transcripts")
        if cues is None:
            counts["unavailable"] += 1
            continue
        counts["ready"] += 1
        if source_video_status(args.source_id, video_id, scan, video)[1]:
            counts["already"] += 1
            continue
        command = [sys.executable, str(ROOT / "progressive_demo.py"),
                   "--ui-video-id", video_id, "--scan", str(scan_path),
                   "--ui-dir", str(source_dir / "ui-transcripts"),
                   "--output-dir", str(source_dir / "progressive-demo")]
        result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, check=False)
        if result.returncode == 0 and source_video_status(args.source_id, video_id, scan, video)[1]:
            counts["created"] += 1
            print(f"{video_id}: tóm tắt xong", flush=True)
            continue
        counts["failed"] += 1
        output = (result.stderr or result.stdout)[-500:]
        if quota_limited(output):
            print(f"{video_id}: hết hạn mức AI; dừng để thử lại sau", flush=True)
            break
        print(f"{video_id}: tạo tóm tắt lỗi: {output.strip()}", flush=True)
    print(json.dumps(counts, ensure_ascii=False), flush=True)
    return 2 if counts["failed"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
