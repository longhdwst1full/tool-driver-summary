#!/usr/bin/env python3
"""Recheck generated lesson packs and report source coverage across courses."""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path

from chunking import Chunk
from lesson_pack import verify_pack


def audit(packs: Path) -> dict:
    courses = defaultdict(list)
    for path in sorted(packs.rglob("*.json")):
        try:
            result = json.loads(path.read_text(encoding="utf-8"))
            if "pack" not in result:
                continue
            chunks = [Chunk(**row) for row in result["chunks"]]
            errors, coverage = verify_pack(result["pack"], chunks)
            status = "pass" if not errors and result.get("qa", {}).get("status") == "ok" else "review"
            courses[path.relative_to(packs).parts[0]].append({
                "lesson": path.stem, "status": status, "coverage": round(coverage, 3),
                "errors": errors, "caveats": result["pack"].get("caveats", []),
                "caption_id": result.get("meta", {}).get("caption_id")})
        except (OSError, ValueError, KeyError, TypeError) as exc:
            courses[path.relative_to(packs).parts[0]].append({
                "lesson": path.stem, "status": "review", "coverage": 0,
                "errors": [str(exc)], "caveats": []})
    all_rows = [row for rows in courses.values() for row in rows]
    comparisons = []
    comparison_root = packs.parent / "cross-source"
    if comparison_root.is_dir():
        for path in sorted(comparison_root.rglob("*.json")):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                comparisons.append({"lesson": path.stem, "status": data.get("status", "needs_review"),
                                    "matches": len(data.get("matches", [])),
                                    "conflicts": sum(row.get("type") == "conflict" for row in data.get("matches", [])),
                                    "caveats": data.get("caveats", [])})
            except (OSError, ValueError):
                comparisons.append({"lesson": path.stem, "status": "needs_review", "matches": 0,
                                    "conflicts": 0, "caveats": ["Không đọc được báo cáo đối chiếu"]})
    return {"total": len(all_rows), "status": dict(Counter(row["status"] for row in all_rows)),
            "courses": dict(courses), "cross_source": comparisons,
            "manual_review": "Độ chính xác ngữ nghĩa, mâu thuẫn nguồn và tính dễ đọc cần người kiểm tra."}


def main() -> int:
    parser = argparse.ArgumentParser(description="Kiểm toán lại gói bài học và trích dẫn")
    parser.add_argument("--packs", type=Path, default=Path("drive-reports/lesson-packs"))
    parser.add_argument("--output", type=Path, default=Path("drive-reports/qa-report.json"))
    args = parser.parse_args()
    report = audit(args.packs)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"total": report["total"], "status": report["status"],
                      "output": str(args.output)}, ensure_ascii=False))
    return 0 if not report["status"].get("review") else 2


if __name__ == "__main__":
    raise SystemExit(main())
