#!/usr/bin/env python3
"""Build traceable course material from lesson packs that passed QA."""

from __future__ import annotations

import argparse
from collections import defaultdict
import json
from pathlib import Path

from output_layout import natural_key, safe_output_file


OUTPUTS = ("course_summary.md", "course_map.json", "concept_graph.json",
           "learning_path.md", "master_notes.md", "course_quiz.json")


def collect_lessons(pack_dir: Path) -> dict[str, list[dict]]:
    courses: dict[str, list[dict]] = defaultdict(list)
    for path in sorted(pack_dir.rglob("*.json")):
        relative = path.relative_to(pack_dir)
        if len(relative.parts) < 2:
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if data.get("qa", {}).get("status") != "ok" or not data.get("meta", {}).get("video_id"):
            continue
        course = relative.parts[0]
        courses[course].append({"title": path.stem, "chapter": " / ".join(relative.parts[1:-1]),
                                "path": path, "relative": relative, "data": data})
    return dict(courses)


def _citation(ref: dict, lesson: dict) -> dict:
    chunk_id = ref.get("chunk_id", "")
    source_id = chunk_id.split(":", 1)[0]
    meta = lesson["data"]["meta"]
    return {"lesson": lesson["title"], "video_id": meta["video_id"], "source_id": source_id,
            "chunk_id": chunk_id, "at": ref.get("at", ""), "quote": ref.get("quote", "")}


def synthesize_course(course: str, lessons: list[dict], output_dir: Path) -> dict:
    """Synthesize only verified claims, retaining source references in JSON artifacts."""
    lessons = sorted(lessons, key=lambda row: (natural_key(row["chapter"]), natural_key(row["title"])))
    target = output_dir / course
    target.mkdir(parents=True, exist_ok=True)
    overview = [f"# {course}", "", f"{len(lessons)} bài đã qua kiểm tra nguồn.", ""]
    learning = [f"# Lộ trình học · {course}", ""]
    master = [f"# Ghi chú tổng hợp · {course}", ""]
    course_map = {"course": course, "lessons": []}
    concepts: dict[str, dict] = {}
    questions = []
    previous_chapter = None
    for index, lesson in enumerate(lessons, 1):
        pack = lesson["data"]["pack"]
        meta = lesson["data"]["meta"]
        rel_md = lesson["relative"].with_suffix(".md")
        link = (Path("../../lesson-packs") / rel_md).as_posix()
        label = lesson["title"]
        chapter = lesson["chapter"]
        if chapter != previous_chapter:
            heading = chapter or "Các bài học"
            overview += [f"## {heading}", ""]
            learning += [f"## {heading}", ""]
            master += [f"## {heading}", ""]
            previous_chapter = chapter
        overview += [f"### {index}. [{label}](<{link}>)", "", pack["summary"], ""]
        learning += [f"### {index}. [{label}](<{link}>)", ""]
        learning += [f"- {objective}" for objective in pack.get("objectives", [])]
        learning.append("")
        master += [f"### [{label}](<{link}>)", "", pack["summary"], ""]
        for section in pack.get("sections", []):
            at = ", ".join(ref.get("at", ref.get("chunk_id", "")) for ref in section["source_refs"])
            master += [f"#### {section['heading']}", "", section["body"], "",
                       f"Nguồn: [{label}](<{link}>) · {at}", ""]
        course_map["lessons"].append({"title": label, "chapter": chapter, "video_id": meta["video_id"],
                                      "caption_id": meta["caption_id"], "lesson_pack": rel_md.as_posix(),
                                      "objectives": pack.get("objectives", []),
                                      "concepts": [c["name"] for c in pack.get("concepts", [])]})
        for concept in pack.get("concepts", []):
            key = concept["name"].casefold().strip()
            if not key:
                continue
            node = concepts.setdefault(key, {"id": key, "name": concept["name"], "definitions": [],
                                             "lessons": [], "sources": []})
            if concept["definition"] not in node["definitions"]:
                node["definitions"].append(concept["definition"])
            if label not in node["lessons"]:
                node["lessons"].append(label)
            node["sources"].extend(_citation(ref, lesson) for ref in concept["source_refs"])
        for question in pack.get("quiz", []):
            questions.append({"lesson": label, "video_id": meta["video_id"],
                              **question, "citations": [_citation(ref, lesson)
                                                        for ref in question["source_refs"]]})
    edges = []
    for lesson in lessons:
        names = sorted({item["name"].casefold().strip() for item in lesson["data"]["pack"].get("concepts", [])
                        if item["name"].casefold().strip() in concepts})
        for left_index, left in enumerate(names):
            for right in names[left_index + 1:]:
                edges.append({"from": left, "to": right, "relation": "co_occurs_in_lesson",
                              "lesson": lesson["title"]})
    graph = {"course": course, "nodes": list(concepts.values()), "edges": edges}
    for node in graph["nodes"]:
        node["possible_conflict"] = len(node["definitions"]) > 1
    quiz = {"course": course, "questions": questions}
    files = {"course_summary.md": "\n".join(overview), "course_map.json": course_map,
             "concept_graph.json": graph, "learning_path.md": "\n".join(learning),
             "master_notes.md": "\n".join(master), "course_quiz.json": quiz}
    for name, value in files.items():
        path = safe_output_file(target, name, Path(name).suffix)
        path.write_text((json.dumps(value, ensure_ascii=False, indent=2) if isinstance(value, dict) else value)
                        + "\n", encoding="utf-8")
    return {"course": course, "lessons": len(lessons), "concepts": len(concepts),
            "questions": len(questions), "output": str(target)}


def main() -> int:
    parser = argparse.ArgumentParser(description="Tổng hợp khóa học từ gói bài đã qua QA")
    parser.add_argument("--packs", type=Path, default=Path("drive-reports/lesson-packs"))
    parser.add_argument("--output", type=Path, default=Path("drive-reports/courses"))
    parser.add_argument("--course", help="Tên thư mục khóa học; bỏ trống để xử lý tất cả")
    args = parser.parse_args()
    courses = collect_lessons(args.packs)
    selected = {k: v for k, v in courses.items() if not args.course or k == args.course}
    if not selected:
        parser.error("Chưa có bài học QA ok cho khóa được chọn")
    for course, lessons in selected.items():
        print(json.dumps(synthesize_course(course, lessons, args.output), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
