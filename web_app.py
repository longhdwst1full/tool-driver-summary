#!/usr/bin/env python3
"""Local management UI for the Google Drive study demo."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import re
import secrets
import subprocess
import sys
from threading import Lock, Thread
from urllib.parse import parse_qs, urlparse

from drive_scan import video_source_status
from output_layout import is_promotional_document, output_paths, safe_output_file
from study_pack import manual_note_paths


ROOT = Path(__file__).resolve().parent
REPORTS = ROOT / "drive-reports"
WEB = ROOT / "web"
SAFE_ID = re.compile(r"^[A-Za-z0-9_-]+$")
TOKEN = secrets.token_urlsafe(32)
JOBS: list[dict] = []
JOBS_LOCK = Lock()


def read_json(path: Path, fallback: dict | None = None) -> dict:
    if not path.is_file():
        return fallback if fallback is not None else {}
    return json.loads(path.read_text(encoding="utf-8"))


def configured_folder_id() -> str:
    scan = read_json(REPORTS / "scan.json")
    folder_id = scan.get("folder", {}).get("id") or os.environ.get("DRIVE_FOLDER_ID", "")
    if not SAFE_ID.fullmatch(folder_id):
        raise ValueError("Chưa có ID thư mục Drive; chạy drive_scan.py hoặc đặt DRIVE_FOLDER_ID")
    return folder_id


def course_name(path: str) -> str:
    parts = path.split("/")
    return parts[1] if len(parts) > 1 else "Ngoài khóa học"


def display_name(name: str) -> str:
    clean = re.sub(r"\s*\(khoahocgiahoi\.com[^)]*\)(?=\.[^.]+$)", "", name, flags=re.I)
    return re.sub(r"\.(mp4|mov|mkv|webm|avi|m4v)$", "", clean, flags=re.I)


def library() -> dict:
    scan = read_json(REPORTS / "scan.json", {"folder": {"id": "", "name": "Google Drive"}, "items": [], "counts": {}, "total": 0})
    captions = read_json(REPORTS / "transcripts/manifest.json", {"files": [], "ok": 0})
    documents = read_json(REPORTS / "documents/manifest.json", {"files": [], "ok": 0, "needs_ocr": 0})
    caption_by_id = {row["id"]: row for row in captions.get("files", [])}
    doc_by_id = {row["id"]: row for row in documents.get("files", [])}
    ai_paths = output_paths(scan, "ai_note")
    manual_paths = manual_note_paths(scan)
    videos = []
    docs = []
    courses: dict[str, dict] = {}
    notes = []
    for item in scan.get("items", []):
        course = course_name(item["path"])
        if item["kind"] not in {"video", "document"}:
            continue
        if is_promotional_document(item) or doc_by_id.get(item["id"], {}).get("status") == "excluded":
            continue
        bucket = courses.setdefault(course, {"name": course, "videos": 0, "documents": 0, "captions": 0})
        base = {"id": item["id"], "name": display_name(item["name"]), "path": item["path"],
                "course": course, "url": item["url"], "size": item.get("size")}
        if item["kind"] == "video":
            bucket["videos"] += 1
            companion = item.get("transcript_files", [])
            transcript = next((caption_by_id.get(row["id"]) for row in companion
                               if caption_by_id.get(row["id"], {}).get("status") == "ok"), None)
            if transcript:
                bucket["captions"] += 1
            video = {**base, "caption_id": transcript["id"] if transcript else None,
                     "source_status": video_source_status(item, has_caption=transcript is not None),
                     "cue_count": transcript.get("cue_count") if transcript else None,
                     "duration_ms": transcript.get("duration_ms") if transcript else None,
                     "has_ai_note": bool(transcript and (
                         safe_output_file(REPORTS / "ai-notes", ai_paths[transcript["id"]], ".md").is_file()
                         or (REPORTS / "ai-notes" / f"{transcript['id']}.md").is_file())),
                     "has_manual_note": bool(transcript and transcript["name"].startswith("14.")
                                             and ("14-admin" in manual_paths)
                                             and (safe_output_file(REPORTS / "study-notes", manual_paths["14-admin"], ".md").is_file()
                                                  or (REPORTS / "study-notes/14-admin.md").is_file()))}
            videos.append(video)
            if video["has_ai_note"]:
                notes.append({"id": transcript["id"], "name": base["name"], "course": course,
                              "type": "ai_note", "source": "video"})
        else:
            bucket["documents"] += 1
            result = doc_by_id.get(item["id"], {})
            docs.append({**base, "status": result.get("status", "pending"),
                         "characters": result.get("characters")})
    for slug, title, source, course in (
        ("14-admin", "Bài 14 · Tạo dự án Admin bằng prompt", "video", "Vibe Coding 2026 Fullstack"),
        ("claude-ai-hieu-qua", "Hướng dẫn sử dụng Claude AI hiệu quả", "document", "Tài liệu Claude AI"),
    ):
        target = manual_paths.get(slug)
        if target and (safe_output_file(REPORTS / "study-notes", target, ".md").is_file()
                       or (REPORTS / "study-notes" / f"{slug}.md").is_file()):
            notes.append({"id": slug, "name": title, "course": course,
                          "type": "study_note", "source": source})
    videos.sort(key=lambda row: row["path"].casefold())
    docs.sort(key=lambda row: row["path"].casefold())
    notes.sort(key=lambda row: row["name"].casefold())
    counts = dict(scan.get("counts", {}))
    counts["document"] = len(docs)
    return {"folder": scan["folder"], "total": scan.get("total", 0),
            "counts": counts, "videos": videos, "documents": docs,
            "notes": notes, "courses": sorted(courses.values(), key=lambda row: row["name"].casefold()),
            "processed": {"captions": captions.get("ok", 0),
                          "documents": sum(row["status"] == "ok" for row in docs),
                          "excluded": documents.get("excluded", 0),
                          "sources": {status: sum(row["source_status"] == status for row in videos)
                                      for status in ("caption_file", "asr_ready", "no_source")},
                          "needs_ocr": sum(row["status"] == "needs_ocr" for row in docs)}}


def file_content(kind: str, file_id: str) -> dict | None:
    if not SAFE_ID.fullmatch(file_id):
        return None
    if kind == "transcript":
        manifest = read_json(REPORTS / "transcripts/manifest.json")
        row = next((x for x in manifest.get("files", []) if x["id"] == file_id and x["status"] == "ok"), None)
        path = safe_output_file(REPORTS / "transcripts", row["output"], ".md") if row else None
        title = row["name"] if row else ""
    elif kind == "document":
        manifest = read_json(REPORTS / "documents/manifest.json")
        row = next((x for x in manifest.get("files", []) if x["id"] == file_id and x["status"] == "ok"), None)
        path = safe_output_file(REPORTS / "documents", row["output"], ".txt") if row else None
        title = row["name"] if row else ""
    elif kind == "ai_note":
        manifest = read_json(REPORTS / "transcripts/manifest.json")
        row = next((x for x in manifest.get("files", []) if x["id"] == file_id and x["status"] == "ok"), None)
        if row:
            scan = read_json(REPORTS / "scan.json")
            relative = output_paths(scan, "ai_note").get(file_id)
            path = safe_output_file(REPORTS / "ai-notes", relative, ".md") if relative else None
            if path and not path.is_file():
                path = REPORTS / "ai-notes" / f"{file_id}.md"
        else:
            path = None
        title = row["name"] if row else ""
    elif kind == "study_note" and file_id in {"14-admin", "claude-ai-hieu-qua"}:
        scan = read_json(REPORTS / "scan.json")
        relative = manual_note_paths(scan).get(file_id)
        path = safe_output_file(REPORTS / "study-notes", relative, ".md") if relative else None
        if path and not path.is_file():
            path = REPORTS / "study-notes" / f"{file_id}.md"
        title = file_id
    else:
        return None
    if path is None or not path.is_file() or path.stat().st_size > 2_000_000:
        return None
    return {"title": title, "kind": kind, "content": path.read_text(encoding="utf-8")}


def command_for(action: str, caption_id: str | None = None) -> list[str]:
    base = [sys.executable]
    if action == "scan":
        return base + ["drive_scan.py", configured_folder_id()]
    if action == "captions":
        return base + ["drive_process.py"]
    if action == "documents":
        return base + ["drive_documents.py", "--max-mb", "30"]
    if action == "note" and isinstance(caption_id, str) and SAFE_ID.fullmatch(caption_id):
        manifest = read_json(REPORTS / "transcripts/manifest.json")
        if any(row["id"] == caption_id and row["status"] == "ok" for row in manifest.get("files", [])):
            return base + ["codex_notes.py", "--id", caption_id]
    raise ValueError("Tác vụ hoặc ID phụ đề không hợp lệ")


def start_job(action: str, caption_id: str | None = None) -> dict:
    command = command_for(action, caption_id)
    with JOBS_LOCK:
        if any(row["status"] == "running" for row in JOBS):
            raise RuntimeError("Một tác vụ khác đang chạy. Hãy đợi tác vụ đó hoàn thành.")
        job = {"id": secrets.token_hex(6), "action": action, "caption_id": caption_id,
               "status": "running", "started": datetime.now(timezone.utc).isoformat(),
               "finished": None, "exit_code": None, "output": ""}
        JOBS.insert(0, job)
        del JOBS[20:]

    def run() -> None:
        env = os.environ.copy()
        env["PYTHONPATH"] = str(ROOT / ".deps") + os.pathsep + env.get("PYTHONPATH", "")
        try:
            result = subprocess.run(command, cwd=ROOT, env=env, text=True,
                                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                    timeout=1800, check=False)
            output = result.stdout[-6000:]
            exit_code = result.returncode
            if exit_code == 0 and action in {"captions", "documents", "note"} and all(
                (REPORTS / section / "manifest.json").is_file() for section in ("transcripts", "documents")
            ):
                index_result = subprocess.run([sys.executable, "study_pack.py"], cwd=ROOT,
                                              env=env, text=True, stdout=subprocess.PIPE,
                                              stderr=subprocess.STDOUT, timeout=120, check=False)
                output = (output + "\n" + index_result.stdout)[-6000:]
                exit_code = index_result.returncode
            status = "done" if exit_code == 0 else "failed"
        except subprocess.TimeoutExpired:
            output, status, exit_code = "Tác vụ vượt thời hạn 30 phút.", "failed", -1
        except OSError as exc:
            output, status, exit_code = str(exc), "failed", -1
        with JOBS_LOCK:
            job.update(status=status, finished=datetime.now(timezone.utc).isoformat(),
                       exit_code=exit_code, output=output)

    Thread(target=run, daemon=True).start()
    return dict(job)


class Handler(BaseHTTPRequestHandler):
    server_version = "DriveStudio/1.0"

    def log_message(self, format: str, *args) -> None:
        return

    def respond(self, status: int, body: bytes, content_type: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Security-Policy", "default-src 'self'; img-src 'self' data:; "
                         "style-src 'self'; script-src 'self'; connect-src 'self'; "
                         "base-uri 'none'; frame-ancestors 'none'")
        self.end_headers()
        self.wfile.write(body)

    def json_response(self, status: int, value: dict) -> None:
        self.respond(status, json.dumps(value, ensure_ascii=False).encode("utf-8"),
                     "application/json; charset=utf-8")

    def allowed_host(self) -> bool:
        return self.headers.get("Host", "").split(":")[0] in {"127.0.0.1", "localhost"}

    def do_GET(self) -> None:
        if not self.allowed_host():
            self.json_response(403, {"error": "Chỉ cho phép truy cập từ máy này"})
            return
        route = urlparse(self.path).path
        if route in {"/", "/styles.css", "/app.js"}:
            filename = "index.html" if route == "/" else route[1:]
            mime = "text/html" if filename.endswith(".html") else (
                "text/css" if filename.endswith(".css") else "text/javascript")
            self.respond(200, (WEB / filename).read_bytes(), mime + "; charset=utf-8")
            return
        if route == "/api/bootstrap":
            self.json_response(200, {"token": TOKEN})
        elif route == "/api/library":
            self.json_response(200, library())
        elif route == "/api/jobs":
            with JOBS_LOCK:
                self.json_response(200, {"jobs": [dict(row) for row in JOBS]})
        elif route == "/api/file":
            query = parse_qs(urlparse(self.path).query)
            result = file_content(query.get("kind", [""])[0], query.get("id", [""])[0])
            self.json_response(200, result) if result else self.json_response(404, {"error": "Không tìm thấy nội dung"})
        else:
            self.json_response(404, {"error": "Đường dẫn không tồn tại"})

    def do_POST(self) -> None:
        if not self.allowed_host() or self.headers.get("X-Drive-Studio-Token") != TOKEN:
            self.json_response(403, {"error": "Yêu cầu không hợp lệ"})
            return
        if urlparse(self.path).path != "/api/jobs":
            self.json_response(404, {"error": "Đường dẫn không tồn tại"})
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length < 1 or length > 4096:
                raise ValueError("Kích thước yêu cầu không hợp lệ")
            data = json.loads(self.rfile.read(length))
            if not isinstance(data, dict):
                raise ValueError("Yêu cầu phải là một đối tượng JSON")
            job = start_job(data.get("action", ""), data.get("caption_id"))
            self.json_response(202, job)
        except (ValueError, json.JSONDecodeError) as exc:
            self.json_response(400, {"error": str(exc)})
        except RuntimeError as exc:
            self.json_response(409, {"error": str(exc)})


def main() -> None:
    parser = argparse.ArgumentParser(description="Giao diện quản lý Google Drive trên máy cá nhân")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    print(f"Drive Studio đang chạy tại http://127.0.0.1:{server.server_port}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
