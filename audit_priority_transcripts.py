#!/usr/bin/env python3
"""Audit local transcript evidence for the three prioritized course groups."""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path

from batch_ui_lessons import readable_ui
from priority_courses import SOURCE_A, SOURCE_B
from web_app import source_video_status

ROOT = Path(__file__).resolve().parent
REPORTS = ROOT / "drive-reports"
GROUPS = ("công nghệ thông tin", "kinh doanh", "đầu tư")


def audit() -> dict:
    sections = []
    for source_id in (SOURCE_A, SOURCE_B):
        source_dir = REPORTS / "new-sources" / source_id
        scan = json.loads((source_dir / "scan.json").read_text(encoding="utf-8"))
        caption_manifest = source_dir / "transcripts/manifest.json"
        caption_rows = json.loads(caption_manifest.read_text(encoding="utf-8")).get("files", []) if caption_manifest.is_file() else []
        caption_ok = {row.get("id") for row in caption_rows if row.get("status") == "ok"}
        batch_path = source_dir / "ui-transcripts/batch-manifest.json"
        batch = json.loads(batch_path.read_text(encoding="utf-8")).get("videos", {}) if batch_path.is_file() else {}
        by_group: dict[str, Counter] = {}
        for video in scan["items"]:
            if video["kind"] != "video":
                continue
            parts = video["path"].split("/")
            category = parts[1] if len(parts) > 1 else ""
            if not any(name in category.casefold() for name in GROUPS):
                continue
            counts = by_group.setdefault(category, Counter())
            counts["videos"] += 1
            captions = video.get("transcript_files", [])
            counts["paired_caption"] += bool(captions)
            counts["caption_read"] += any(row.get("id") in caption_ok for row in captions)
            video_id = video["id"]
            ui_dir = source_dir / "ui-transcripts"
            if (ui_dir / f"{video_id}.srt").is_file():
                if readable_ui(scan, video, ui_dir):
                    counts["ui_verified"] += 1
                    if source_video_status(source_id, video_id, scan, video)[1]:
                        counts["ai_verified"] += 1
                else:
                    counts["ui_invalid"] += 1
            if video_id in batch:
                counts["attempted"] += 1
                if batch[video_id].get("status") == "no_transcript":
                    counts["drive_panel_unavailable"] += 1
                elif batch[video_id].get("status") == "failed":
                    counts["capture_failed"] += 1
        for category, counts in sorted(by_group.items()):
            counts["not_checked_on_drive"] = counts["videos"] - counts["attempted"]
            sections.append({"source_id": source_id, "category": category, **counts})
    return {"updated_at": datetime.now(timezone.utc).isoformat(), "sections": sections}


def main() -> None:
    result = audit()
    json_path = REPORTS / "priority-transcript-audit.json"
    md_path = REPORTS / "priority-transcript-audit.md"
    json_path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    fields = ("videos", "attempted", "ui_verified", "caption_read", "ai_verified",
              "drive_panel_unavailable", "capture_failed", "not_checked_on_drive")
    lines = ["# Kiểm tra bản chép lời của ba nhóm ưu tiên", "",
             "`Chưa mở trên Drive` nghĩa là chưa kiểm tra panel transcript; không kết luận video không có lời.",
             "", "| Nguồn | Nhóm | Video | Đã thử | Lời UI hợp lệ | Phụ đề riêng đã đọc | AI hợp lệ | Panel không khả dụng | Thu lỗi | Chưa mở trên Drive |",
             "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |"]
    for row in result["sections"]:
        values = " | ".join(f"{row.get(field, 0):,}" for field in fields)
        lines.append(f"| {row['source_id'][:8]}… | {row['category']} | {values} |")
    lines.append("")
    md_path.write_text("\n".join(lines), encoding="utf-8")
    print(md_path)


if __name__ == "__main__":
    main()
