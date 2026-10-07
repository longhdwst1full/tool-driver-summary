#!/usr/bin/env python3
"""Rebuild a readable course index and migrate hand-written sample notes."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re

from output_layout import is_promotional_document, output_paths, safe_output_file, safe_segment, video_title


def manual_note_paths(scan: dict) -> dict[str, Path]:
    captions = output_paths(scan, "transcript")
    documents = output_paths(scan, "document")
    result = {}
    for item in scan["items"]:
        if item["kind"] == "transcript" and item["name"].startswith("14. Tạo dự án Admin"):
            result["14-admin"] = captions[item["id"]]
        elif item["kind"] == "document" and item["name"].casefold().startswith("huong-dan-su-dung-claude-ai-hieu-qua"):
            result["claude-ai-hieu-qua"] = documents[item["id"]].with_name(
                safe_segment("Hướng dẫn sử dụng Claude AI hiệu quả") + ".md")
    return result


def relative_link(from_dir: Path, target: Path) -> str:
    return Path(os.path.relpath(target, from_dir)).as_posix()


def migrate_manual_notes(scan: dict, reports: Path) -> dict[str, Path]:
    targets = manual_note_paths(scan)
    for slug, relative in targets.items():
        old = reports / "study-notes" / f"{slug}.md"
        target = safe_output_file(reports / "study-notes", relative, ".md")
        if target.is_file() or not old.is_file():
            continue
        content = old.read_text(encoding="utf-8")
        if slug == "14-admin":
            caption = next(row for row in scan["items"] if row["kind"] == "transcript"
                           and row["name"].startswith("14. Tạo dự án Admin"))
            source = safe_output_file(reports / "transcripts", output_paths(scan, "transcript")[caption["id"]], ".md")
            content = re.sub(r"\]\(\.\./transcripts/[A-Za-z0-9_-]+\.md\)",
                             f"](<{relative_link(target.parent, source)}>)", content)
        elif slug == "claude-ai-hieu-qua":
            document = next(row for row in scan["items"] if row["kind"] == "document"
                            and row["name"].casefold().startswith("huong-dan-su-dung-claude-ai-hieu-qua"))
            source = safe_output_file(reports / "documents", output_paths(scan, "document")[document["id"]], ".txt")
            content = re.sub(r"\]\(\.\./documents/[A-Za-z0-9_-]+\.txt\)",
                             f"](<{relative_link(target.parent, source)}>)", content)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        old.unlink()
    return targets


def natural_key(value: str) -> list:
    return [(1, int(part)) if part.isdigit() else (0, part.casefold())
            for part in re.split(r"(\d+)", value)]


def build_index(scan: dict, transcript_manifest: dict, document_manifest: dict,
                reports: Path) -> str:
    transcripts = {row["id"]: row for row in transcript_manifest.get("files", [])}
    documents = {row["id"]: row for row in document_manifest.get("files", [])}
    excluded_ids = {file_id for file_id, row in documents.items() if row.get("status") == "excluded"}
    ai_paths = output_paths(scan, "ai_note")
    manual_paths = manual_note_paths(scan)
    index_dir = reports / "study-notes"
    courses: dict[str, list[dict]] = {}
    for item in scan["items"]:
        if (item["kind"] not in {"video", "document"} or is_promotional_document(item)
                or item["id"] in excluded_ids):
            continue
        parts = item["path"].split("/")
        course = parts[1] if len(parts) > 1 else "Ngoài khóa học"
        courses.setdefault(course, []).append(item)
    kept_docs = sum(row["kind"] == "document" and not is_promotional_document(row)
                    and row["id"] not in excluded_ids
                    for row in scan["items"])
    lines = ["# Chỉ mục nội dung Drive", "",
             f"{len(courses)} khóa học · {scan['counts'].get('video', 0)} video · "
             f"{kept_docs} tài liệu học. File quảng cáo Khóa học giá hời đã được bỏ qua.", ""]
    for course, items in sorted(courses.items(), key=lambda pair: pair[0].casefold()):
        lines.extend([f"## {course}", "", "| Loại | Bài / tài liệu | Nguồn Drive | Kết quả cục bộ |",
                      "|---|---|---|---|"])
        for item in sorted(items, key=lambda row: natural_key(row["path"])):
            title = video_title(item["name"]) if item["kind"] == "video" else item["name"]
            source = f"[Mở Drive]({item['url']})"
            links = []
            if item["kind"] == "video":
                for companion in item.get("transcript_files", []):
                    entry = transcripts.get(companion["id"])
                    if not entry or entry.get("status") != "ok":
                        continue
                    transcript = safe_output_file(reports / "transcripts", entry["output"], ".md")
                    links.append(f"[Phụ đề](<{relative_link(index_dir, transcript)}>)")
                    ai = safe_output_file(reports / "ai-notes", ai_paths[companion["id"]], ".md")
                    if ai.is_file():
                        links.append(f"[Ghi chú AI](<{relative_link(index_dir, ai)}>)")
                    if companion["name"].startswith("14. Tạo dự án Admin") and "14-admin" in manual_paths:
                        note = safe_output_file(index_dir, manual_paths["14-admin"], ".md")
                        if note.is_file():
                            links.append(f"[Ghi chú mẫu](<{relative_link(index_dir, note)}>)")
            else:
                entry = documents.get(item["id"])
                if entry and entry.get("status") == "ok":
                    document = safe_output_file(reports / "documents", entry["output"], ".txt")
                    links.append(f"[Văn bản](<{relative_link(index_dir, document)}>)")
                elif entry and entry.get("status") == "needs_ocr":
                    links.append("Cần OCR")
                if item["name"].casefold().startswith("huong-dan-su-dung-claude-ai-hieu-qua") and "claude-ai-hieu-qua" in manual_paths:
                    note = safe_output_file(index_dir, manual_paths["claude-ai-hieu-qua"], ".md")
                    if note.is_file():
                        links.append(f"[Ghi chú mẫu](<{relative_link(index_dir, note)}>)")
            lines.append(f"| {item['kind']} | {title.replace('|', chr(92) + '|')} | {source} | {' · '.join(links) or 'Chưa có'} |")
        lines.append("")
    return "\n".join(lines)


def update_study_pack(scan: dict, reports: Path) -> Path:
    migrate_manual_notes(scan, reports)
    transcripts = json.loads((reports / "transcripts/manifest.json").read_text(encoding="utf-8"))
    documents = json.loads((reports / "documents/manifest.json").read_text(encoding="utf-8"))
    output = reports / "study-notes/index.md"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(build_index(scan, transcripts, documents, reports), encoding="utf-8")
    return output


def main() -> None:
    parser = argparse.ArgumentParser(description="Tạo chỉ mục học tập với tên file dễ đọc")
    parser.add_argument("--reports", type=Path, default=Path("drive-reports"))
    args = parser.parse_args()
    scan = json.loads((args.reports / "scan.json").read_text(encoding="utf-8"))
    print(f"Đã tạo: {update_study_pack(scan, args.reports)}")


if __name__ == "__main__":
    main()
