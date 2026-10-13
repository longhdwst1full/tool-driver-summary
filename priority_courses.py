#!/usr/bin/env python3
"""Process a balanced first wave of IT, business, and investing courses."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import sys

from batch_ui_lessons import quota_limited


ROOT = Path(__file__).resolve().parent
REPORT = ROOT / "drive-reports/priority-courses.json"
SOURCE_A = "1GwuGmZuGk04LuvgwLUl9ahdZ1NW-2xqF"
SOURCE_B = "1pjNn2Wc_f5dLEfF023m5jvMEyF2s2fWj"
# Stable Drive folder IDs avoid changes in spelling, punctuation, or lesson order.
TARGETS = [
    (SOURCE_A, "11IYRLrh2xGujIr-W6n0b65qyPlkBnaQ1", "công nghệ thông tin"),
    (SOURCE_A, "12tDuiLHgVF0tMnFAv79mSgjW_XrCHrI8", "kinh doanh"),
    (SOURCE_A, "1mqjhhQ6po3mqKrxBw67pkefxT2RQ096x", "đầu tư"),
    (SOURCE_B, "1CVn5CzZ-fJX-trh_EIFAbkYcp125BECb", "công nghệ thông tin"),
    (SOURCE_B, "1AVKPy83HET3s19Zk_owUHNyJPye76JdG", "kinh doanh"),
    (SOURCE_B, "1uVncNut4PcwubGNBIo-Nha09crBDlF1J", "đầu tư"),
    (SOURCE_A, "17vOVAxavlwtYFZuJYlzpOfAfPh2_q-Es", "công nghệ thông tin"),
    (SOURCE_A, "1fBsB6orbh-VWtZ8XyZqAeAfmTrImbyOm", "kinh doanh"),
    (SOURCE_A, "12_DnNT0m5u_yn56611obSsxPcH825j-E", "đầu tư"),
    (SOURCE_B, "1mXFTfFK8s5ShmQV1Dlg9FY40PrE1bBJU", "công nghệ thông tin"),
    (SOURCE_B, "1k81yyhUg8SslgLqDtLly4RrMlptFWnt9", "đầu tư"),
    (SOURCE_A, "1dORqUabjOfG1RKU0wwL1Eu9KLRzeO5AC", "công nghệ thông tin / đầu tư"),
]


def selected_courses() -> list[dict]:
    result = []
    for source_id in (SOURCE_A, SOURCE_B):
        path = ROOT / "drive-reports/new-sources" / source_id / "scan.json"
        scan = json.loads(path.read_text(encoding="utf-8"))
        folders = {row["id"]: row for row in scan["items"] if row["kind"] == "folder"}
        for sid, folder_id, category in TARGETS:
            if sid != source_id:
                continue
            folder = folders[folder_id]
            if not any(part in folder["path"].casefold() for part in
                       ("công nghệ thông tin", "đầu tư", "kinh doanh")):
                raise ValueError(f"Thư mục {folder_id} nằm ngoài nhóm ưu tiên")
            videos = sum(row["kind"] == "video" and row["path"].startswith(folder["path"] + "/")
                         for row in scan["items"])
            result.append({"source_id": source_id, "folder_id": folder_id,
                           "category": category, "name": folder["name"], "videos": videos})
    by_id = {row["folder_id"]: row for row in result}
    return [by_id[folder_id] for _, folder_id, _ in TARGETS]


def save_report(rows: list[dict]) -> None:
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    temp = REPORT.with_suffix(".tmp")
    temp.write_text(json.dumps({"updated_at": datetime.now(timezone.utc).isoformat(),
                                "courses": rows}, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8")
    temp.replace(REPORT)


def main() -> int:
    parser = argparse.ArgumentParser(description="Ưu tiên khóa IT, kinh doanh và đầu tư")
    parser.add_argument("--limit-per-course", type=int, default=2)
    parser.add_argument("--phase", choices=("all", "capture", "summary"), default="all")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    if args.limit_per_course < 1:
        parser.error("--limit-per-course phải lớn hơn 0")
    courses = selected_courses()
    if args.dry_run:
        print(json.dumps(courses, ensure_ascii=False, indent=2))
        return 0
    previous = json.loads(REPORT.read_text(encoding="utf-8")) if REPORT.is_file() else {}
    old_rows = {row["folder_id"]: row for row in previous.get("courses", [])}
    for row in courses:
        row.update({key: value for key, value in old_rows.get(row["folder_id"], {}).items()
                    if key in {"capture_exit", "summary_exit", "summary_error"}})
    save_report(courses)
    if args.phase in {"all", "capture"}:
        for row in courses:
            print(f"Kiểm tra bản chép lời [{row['category']}]: {row['name']}", flush=True)
            capture = subprocess.run([sys.executable, str(ROOT / "batch_ui_lessons.py"),
                                      "--source-id", row["source_id"], "--course", row["name"],
                                      "--limit", str(args.limit_per_course), "--workers", "1"],
                                     cwd=ROOT, check=False)
            row["capture_exit"] = capture.returncode
            save_report(courses)
    if args.phase in {"all", "summary"}:
        for row in courses:
            print(f"Tóm tắt [{row['category']}]: {row['name']}", flush=True)
            summary = subprocess.run([sys.executable, str(ROOT / "run_source_notes.py"),
                                      "--source-id", row["source_id"], "--course", row["name"],
                                      "--limit", str(args.limit_per_course)], cwd=ROOT, check=False,
                                     capture_output=True, text=True)
            output = (summary.stdout + "\n" + summary.stderr).strip()
            if output:
                print(output[-1200:], flush=True)
            row["summary_exit"] = summary.returncode
            row["summary_error"] = summary.stderr.strip()[-400:] if summary.returncode else ""
            save_report(courses)
            if summary.returncode and quota_limited(output):
                print("Đã hết hạn mức Codex CLI; dừng gọi AI, giữ bản chép lời để chạy tiếp.", flush=True)
                return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
