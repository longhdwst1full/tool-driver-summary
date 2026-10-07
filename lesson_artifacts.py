#!/usr/bin/env python3
"""Export each verified lesson pack into the Phase 1 file layout."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import shutil

from course_synthesis import collect_lessons
from output_layout import safe_output_file, safe_segment


def export_lessons(packs: Path, transcript_manifest: Path, output_dir: Path) -> dict:
    manifest = json.loads(transcript_manifest.read_text(encoding="utf-8"))
    caption_paths = {row["id"]: row["output"] for row in manifest.get("files", [])
                     if row.get("status") == "ok" and row.get("output")}
    count = 0
    for course, lessons in collect_lessons(packs).items():
        for lesson in lessons:
            target = output_dir / course / Path(*lesson["relative"].parts[1:-1]) / safe_segment(lesson["title"])
            target.mkdir(parents=True, exist_ok=True)
            data = lesson["data"]
            pack = data["pack"]
            caption_id = data["meta"]["caption_id"]
            relative = caption_paths.get(caption_id)
            if relative:
                source = safe_output_file(transcript_manifest.parent, relative, ".md")
                if source.is_file():
                    shutil.copyfile(source, safe_output_file(target, "transcript.md", ".md"))
            safe_output_file(target, "summary.md", ".md").write_text(
                f"# {lesson['title']}\n\n{pack['summary']}\n", encoding="utf-8")
            notes = [f"# Ghi chú chi tiết · {lesson['title']}", ""]
            for section in pack.get("sections", []):
                notes += [f"## {section['heading']}", "", section["body"], "",
                          "Nguồn: " + ", ".join(ref.get("at", ref["chunk_id"])
                                               for ref in section["source_refs"]), ""]
            safe_output_file(target, "deep_notes.md", ".md").write_text("\n".join(notes), encoding="utf-8")
            values = {"concepts.json": pack.get("concepts", []), "timeline.json": pack.get("timeline", []),
                      "quiz.json": pack.get("quiz", []),
                      "metadata.json": {**data["meta"], "qa": data["qa"],
                                        "lesson": lesson["title"], "course": course,
                                        "chapter": lesson["chapter"]}}
            for name, value in values.items():
                safe_output_file(target, name, ".json").write_text(
                    json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            count += 1
    return {"lessons": count, "output": str(output_dir)}


def main() -> int:
    parser = argparse.ArgumentParser(description="Xuất gói bài học thành các tệp riêng")
    parser.add_argument("--packs", type=Path, default=Path("drive-reports/lesson-packs"))
    parser.add_argument("--transcripts", type=Path, default=Path("drive-reports/transcripts/manifest.json"))
    parser.add_argument("--output", type=Path, default=Path("drive-reports/lesson-artifacts"))
    args = parser.parse_args()
    print(json.dumps(export_lessons(args.packs, args.transcripts, args.output), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
