#!/usr/bin/env python3
"""Prepare per-course Markdown sources for manual NotebookLM import."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import shutil

from course_synthesis import OUTPUTS, collect_lessons
from output_layout import safe_output_file


def export_course(course: str, lessons: list[dict], courses_dir: Path, output_dir: Path) -> dict:
    target = output_dir / course
    target.mkdir(parents=True, exist_ok=True)
    sources = []
    original_documents = {}
    for lesson in lessons:
        original = lesson["path"].with_suffix(".md")
        if not original.is_file():
            continue
        relative = Path("lessons") / lesson["relative"].relative_to(course).with_suffix(".md")
        destination = safe_output_file(target, relative, ".md")
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(original, destination)
        sources.append({"path": relative.as_posix(), "type": "lesson",
                        "video_id": lesson["data"]["meta"]["video_id"]})
        for document in lesson["data"]["meta"].get("documents", []):
            original_documents[document["id"]] = document
    for name in OUTPUTS:
        if not name.endswith(".md"):
            continue
        original = courses_dir / course / name
        if original.is_file():
            shutil.copyfile(original, safe_output_file(target, name, ".md"))
            sources.append({"path": name, "type": "course"})
    manifest = {"course": course, "sources": sources,
                "original_documents": list(original_documents.values()),
                "note": "Chỉ gồm bài có QA ok. Tải từng file Markdown lên NotebookLM theo quyền truy cập của bạn."}
    safe_output_file(target, "manifest.json", ".json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {"course": course, "sources": len(sources), "output": str(target)}


def main() -> int:
    parser = argparse.ArgumentParser(description="Xuất nguồn Markdown để nhập vào NotebookLM")
    parser.add_argument("--packs", type=Path, default=Path("drive-reports/lesson-packs"))
    parser.add_argument("--courses", type=Path, default=Path("drive-reports/courses"))
    parser.add_argument("--output", type=Path, default=Path("drive-reports/notebooklm-export"))
    parser.add_argument("--course")
    args = parser.parse_args()
    selected = {k: v for k, v in collect_lessons(args.packs).items()
                if not args.course or k == args.course}
    if not selected:
        parser.error("Chưa có bài học QA ok cho khóa được chọn")
    for course, lessons in selected.items():
        print(json.dumps(export_course(course, lessons, args.courses, args.output), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
