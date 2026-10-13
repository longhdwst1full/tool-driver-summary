#!/usr/bin/env python3
"""Capture visible Drive transcripts for the five recently added courses."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parent
COURSE_IDS = (
    "1Q730gr6P3wX-PB_yO8E872_RajP-F85R",  # Afa Wealth Intelligence
    "1dFWmj2DQ8oSh4wN8gNLNz5amgAJ5HP7V",  # Product Management 101
    "1in6wYR7Bv3jvZ4Rs5lr9p_s5XTy3Pv74",  # CAPM
    "1gmPuPWfliG5Vbv86bX1dHMnLAXLl4ORB",  # AI For PM
    "1v4RV6kSdBIquRN-y23kPAEMQhiGABYMM",  # Software Project Manager
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Thu bản chép lời Drive cho năm khóa học mới")
    parser.add_argument("--workers", type=int, choices=(1, 2), default=2)
    parser.add_argument("--limit-per-source", type=int, help="Thử số video đầu mỗi khóa")
    parser.add_argument("--ai", action="store_true", help="Tạo bài AI bằng Codex sau khi thu")
    args = parser.parse_args()
    if args.limit_per_source is not None and args.limit_per_source < 1:
        parser.error("--limit-per-source phải lớn hơn 0")
    failures = 0
    for source_id in COURSE_IDS:
        print(f"\nĐang xử lý nguồn {source_id}", flush=True)
        command = [sys.executable, str(ROOT / "batch_ui_lessons.py"),
                   "--source-id", source_id, "--workers", str(args.workers)]
        if args.limit_per_source:
            command += ["--limit", str(args.limit_per_source)]
        if args.ai:
            command.append("--ai")
        result = subprocess.run(command, cwd=ROOT, check=False)
        failures += result.returncode != 0
    summary = {}
    for source_id in COURSE_IDS:
        path = ROOT / "drive-reports/new-sources" / source_id / "ui-transcripts/batch-manifest.json"
        if path.is_file():
            summary[source_id] = json.loads(path.read_text(encoding="utf-8")).get("counts", {})
    print(json.dumps(summary, ensure_ascii=False, indent=2), flush=True)
    return 2 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
