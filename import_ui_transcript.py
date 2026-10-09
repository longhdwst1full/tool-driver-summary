#!/usr/bin/env python3
"""Validate a browser-exported Drive UI transcript and write local JSON/SRT files."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import sys

from getsub_demo import parse_captions
from output_layout import safe_output_file


VIDEO_ID = re.compile(r"^[A-Za-z0-9_-]{10,}$")


def seconds(value: str) -> int:
    parts = [int(part) for part in value.split(":")]
    if len(parts) not in {2, 3} or any(part >= 60 for part in parts[-2:]):
        raise ValueError("Mốc thời gian không hợp lệ")
    return sum(part * 60 ** index for index, part in enumerate(reversed(parts)))


def stamp(value: int) -> str:
    hours, rest = divmod(value, 3600)
    minutes, secs = divmod(rest, 60)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},000"


def validate_export(data: dict, scan: dict) -> tuple[str, list[dict]]:
    video_id = data.get("videoId", "")
    if not isinstance(video_id, str) or not VIDEO_ID.fullmatch(video_id):
        raise ValueError("ID video không hợp lệ")
    if not any(row.get("kind") == "video" and row.get("id") == video_id for row in scan["items"]):
        raise ValueError("Video không thuộc thư mục đã quét")
    if data.get("source") != "drive_ui" or not data.get("url", "").startswith(
            f"https://drive.google.com/file/d/{video_id}/"):
        raise ValueError("Nguồn bản thu không khớp video")
    if not data.get("atBottom") or not data.get("startsNearZero"):
        raise ValueError("Bản thu chưa thấy đủ đầu/cuối panel")
    rows = data.get("rows")
    if not isinstance(rows, list) or not 2 <= len(rows) <= 20000 or data.get("rowCount") != len(rows):
        raise ValueError("Số dòng transcript không hợp lệ")
    previous = -1
    for row in rows:
        if not isinstance(row, dict) or not isinstance(row.get("at"), str) or not isinstance(row.get("text"), str):
            raise ValueError("Dòng transcript không hợp lệ")
        if not re.fullmatch(r"\d{1,2}:\d{2}(?::\d{2})?", row["at"]):
            raise ValueError("Mốc thời gian trong transcript không hợp lệ")
        position = seconds(row["at"])
        if position < previous or not row["text"].strip() or len(row["text"]) > 3000:
            raise ValueError("Dòng transcript rỗng, quá dài hoặc sai thứ tự")
        previous = position
    if seconds(rows[0]["at"]) > 5:
        raise ValueError("Bản thu thiếu mốc đầu")
    return video_id, rows


def make_srt(rows: list[dict]) -> str:
    blocks = []
    for index, row in enumerate(rows):
        start = seconds(row["at"])
        next_start = seconds(rows[index + 1]["at"]) if index + 1 < len(rows) else start + 5
        end = max(start + 1, next_start)
        blocks.append(f"{index + 1}\n{stamp(start)} --> {stamp(end)}\n{row['text'].strip()}\n")
    result = "\n".join(blocks)
    if len(parse_captions(result)) != len(rows):
        raise ValueError("SRT tạo ra không giữ đủ số dòng")
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Nhập JSON bản chép lời thu từ tab Drive")
    parser.add_argument("input", type=Path, help="File getsub-transcript-<video-id>.json từ Chrome")
    parser.add_argument("--scan", type=Path, default=Path("drive-reports/scan.json"))
    parser.add_argument("--output-dir", type=Path, default=Path("drive-reports/ui-transcripts"))
    args = parser.parse_args()
    try:
        if args.input.stat().st_size > 5_000_000:
            raise ValueError("Bản thu lớn hơn 5 MB")
        data = json.loads(args.input.read_text(encoding="utf-8"))
        scan = json.loads(args.scan.read_text(encoding="utf-8"))
        video_id, rows = validate_export(data, scan)
        srt = make_srt(rows)
        args.output_dir.mkdir(parents=True, exist_ok=True)
        json_path = safe_output_file(args.output_dir, video_id + ".json", ".json")
        srt_path = safe_output_file(args.output_dir, video_id + ".srt", ".srt")
        json_path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        srt_path.write_text(srt, encoding="utf-8")
        print(f"Đã nhập {len(rows)} dòng cho video {video_id}: {srt_path}")
        return 0
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(f"Lỗi nhập bản chép lời: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
