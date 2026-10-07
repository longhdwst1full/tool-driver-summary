#!/usr/bin/env python3
"""Resume lesson-pack generation for every extracted caption in a Drive scan."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys


def main() -> int:
    parser = argparse.ArgumentParser(description="Tạo gói bài học hàng loạt, tiếp tục được sau khi ngắt")
    parser.add_argument("--scan", type=Path, default=Path("drive-reports/scan.json"))
    parser.add_argument("--manifest", type=Path, default=Path("drive-reports/transcripts/manifest.json"))
    parser.add_argument("--course", help="Chỉ xử lý một tên khóa học")
    parser.add_argument("--limit", type=int, help="Giới hạn số bài trong lần chạy")
    parser.add_argument("--refresh", action="store_true")
    args = parser.parse_args()
    scan = json.loads(args.scan.read_text(encoding="utf-8"))
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    videos = {caption["id"]: row for row in scan["items"] if row["kind"] == "video"
              for caption in row.get("transcript_files", [])}
    entries = [entry for entry in manifest["files"] if entry["status"] == "ok"
               and entry["id"] in videos and (not args.course or args.course in videos[entry["id"]]["path"].split("/"))]
    if args.limit is not None:
        entries = entries[:args.limit]
    results = []
    for index, entry in enumerate(entries, 1):
        print(f"[{index}/{len(entries)}] {videos[entry['id']]['path']}", flush=True)
        command = [sys.executable, str(Path(__file__).with_name("lesson_pack.py")),
                   "--id", entry["id"], "--scan", str(args.scan), "--manifest", str(args.manifest)]
        if args.refresh:
            command.append("--refresh")
        run = subprocess.run(command, check=False)
        results.append({"caption_id": entry["id"], "exit_code": run.returncode})
        print(f"  exit={run.returncode}", flush=True)
    counts = {str(code): sum(item["exit_code"] == code for item in results)
              for code in sorted({item["exit_code"] for item in results})}
    print(json.dumps({"total": len(results), "exit_codes": counts}, ensure_ascii=False))
    return 0 if all(item["exit_code"] == 0 for item in results) else 2


if __name__ == "__main__":
    raise SystemExit(main())
