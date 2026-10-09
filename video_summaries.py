#!/usr/bin/env python3
"""Collect verified lesson packs into one readable course and chapter report."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import re

from output_layout import natural_key, output_paths, safe_output_file, video_title


HEADING = re.compile(r"^(#{2,5}) (.+)$", re.MULTILINE)


def build_report(scan: dict, reports: Path) -> tuple[str, int]:
    paths = output_paths(scan, "ai_note")
    entries = []
    for video in scan["items"]:
        if video.get("kind") != "video":
            continue
        for caption in video.get("transcript_files", []):
            relative = paths.get(caption["id"])
            if relative is None:
                continue
            json_path = safe_output_file(reports / "lesson-packs", relative.with_suffix(".json"), ".json")
            markdown_path = safe_output_file(reports / "lesson-packs", relative, ".md")
            if not json_path.is_file() or not markdown_path.is_file():
                continue
            pack = json.loads(json_path.read_text(encoding="utf-8"))
            if pack.get("qa", {}).get("status") != "ok":
                continue
            source = markdown_path.read_text(encoding="utf-8")
            marker = "\n## Tóm tắt\n"
            if marker not in source:
                raise ValueError(f"Gói bài học thiếu phần tóm tắt: {markdown_path}")
            body = "## Tóm tắt\n" + source.split(marker, 1)[1]
            body = HEADING.sub(lambda match: f"{'#' * min(len(match[1]) + 3, 6)} {match[2]}", body)
            entries.append((video, body.strip()))

    entries.sort(key=lambda pair: natural_key(pair[0]["path"]))
    total_videos = sum(item.get("kind") == "video" for item in scan["items"])
    lines = ["# Nội dung chi tiết các video đã xử lý", "",
             "Tài liệu này tổng hợp các gói bài học đã qua kiểm tra tự động. "
             "Mốc thời gian dựa trên phụ đề riêng; thuật ngữ và nội dung quan trọng vẫn cần đối chiếu video gốc.", "",
             f"**{len(entries)}/{total_videos} video** có nội dung đã xử lý. "
             f"{total_videos - len(entries)} video còn lại chưa có gói bài học đạt QA; "
             "không suy ra nội dung từ tên video.", ""]
    last_course = last_chapter = None
    for video, body in entries:
        parts = video["path"].split("/")
        course = parts[1] if len(parts) > 2 else "Ngoài khóa học"
        chapter = " / ".join(parts[2:-1]) or "Không có chương"
        if course != last_course:
            lines.extend([f"## {course}", ""])
            last_course, last_chapter = course, None
        if chapter != last_chapter:
            lines.extend([f"### {chapter}", ""])
            last_chapter = chapter
        lines.extend([f"#### {video_title(video['name'])}", "",
                      f"[Mở video gốc]({video['url']}) · Gói bài học: đã qua QA", "",
                      body, ""])
    return "\n".join(lines), len(entries)


def main() -> None:
    parser = argparse.ArgumentParser(description="Gộp gói bài học đã kiểm tra thành báo cáo video chi tiết")
    parser.add_argument("--reports", type=Path, default=Path("drive-reports"))
    args = parser.parse_args()
    scan = json.loads((args.reports / "scan.json").read_text(encoding="utf-8"))
    content, count = build_report(scan, args.reports)
    output = args.reports / "video-summaries.md"
    output.write_text(content, encoding="utf-8")
    print(json.dumps({"videos": count, "output": str(output)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
