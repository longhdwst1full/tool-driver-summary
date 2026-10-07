#!/usr/bin/env python3
"""Refresh all local knowledge outputs after lesson generation completes."""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys


STEPS = (("Đối chiếu nguồn", "cross_source.py"), ("QA", "qa_report.py"), ("Bài học", "lesson_artifacts.py"),
         ("Khóa học", "course_synthesis.py"), ("Tìm kiếm", "knowledge_search.py", "build"),
         ("NotebookLM", "notebook_export.py"))


def main() -> int:
    results = []
    for name, script, *args in STEPS:
        command = [sys.executable, str(Path(__file__).with_name(script)), *args]
        run = subprocess.run(command, check=False, text=True, capture_output=True)
        results.append({"step": name, "exit_code": run.returncode,
                        "output": run.stdout.strip() or run.stderr.strip()})
        print(f"{name}: {'ok' if run.returncode == 0 else 'cần xem lại'}", flush=True)
        if run.returncode not in (0, 2) or (run.returncode == 2 and script not in ("qa_report.py", "cross_source.py")):
            break
    print(json.dumps(results, ensure_ascii=False, indent=2))
    return 0 if all(row["exit_code"] == 0 for row in results) else 2


if __name__ == "__main__":
    raise SystemExit(main())
