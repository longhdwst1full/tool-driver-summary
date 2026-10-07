#!/usr/bin/env python3
"""Read-only inventory of one Google Drive folder and its subfolders."""

from __future__ import annotations

import argparse
from collections import Counter, deque
import json
import os
from pathlib import Path
import re
import sys
from urllib.parse import parse_qs, urlparse


FOLDER_MIME = "application/vnd.google-apps.folder"
SHORTCUT_MIME = "application/vnd.google-apps.shortcut"
VIDEO_EXT = {".mp4", ".mov", ".mkv", ".webm", ".avi", ".m4v"}
TRANSCRIPT_EXT = {".srt", ".vtt"}
TEXT_EXT = {".txt", ".md"}
DOCUMENT_EXT = {".pdf", ".doc", ".docx", ".ppt", ".pptx", ".odt", ".rtf"} | TEXT_EXT
GOOGLE_DOCUMENT_MIME = {
    "application/vnd.google-apps.document",
    "application/vnd.google-apps.presentation",
    "application/vnd.google-apps.spreadsheet",
}
ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{10,}$")
FIELDS = (
    "nextPageToken,incompleteSearch,"
    "files(id,name,mimeType,size,modifiedTime,webViewLink,description,"
    "capabilities(canDownload),shortcutDetails(targetId,targetMimeType))"
)


def folder_id_from(value: str) -> str:
    value = value.strip()
    if ID_PATTERN.fullmatch(value):
        return value
    url = urlparse(value)
    if url.netloc not in {"drive.google.com", "www.drive.google.com"}:
        raise ValueError("Cần link thư mục drive.google.com hoặc ID thư mục")
    match = re.search(r"/folders/([A-Za-z0-9_-]+)", url.path)
    candidate = match.group(1) if match else parse_qs(url.query).get("id", [""])[0]
    if not ID_PATTERN.fullmatch(candidate):
        raise ValueError("Không tìm thấy ID thư mục hợp lệ trong link")
    return candidate


def file_kind(item: dict) -> str:
    mime = item.get("mimeType", "")
    suffix = Path(item.get("name", "")).suffix.lower()
    if mime == FOLDER_MIME:
        return "folder"
    if mime == SHORTCUT_MIME:
        return "shortcut"
    if mime.startswith("video/") or suffix in VIDEO_EXT:
        return "video"
    if suffix in TRANSCRIPT_EXT:
        return "transcript"
    if mime in GOOGLE_DOCUMENT_MIME or suffix in DOCUMENT_EXT:
        return "document"
    return "other"


def transcript_key(name: str) -> str:
    stem = Path(name).stem.casefold()
    stem = re.sub(r"\s*\([^)]*\)\s*$", "", stem)
    stem = re.sub(r"[ _.-]+(?:vi(?:[_-]vn)?|en(?:[_-]us)?|vietnamese|english)$", "", stem)
    stem = re.sub(r"[ _.-]+(?:subtitles?|captions?|transcripts?|phu[ _.-]?de)$", "", stem)
    return re.sub(r"[^\w]+", "", stem)


def scan_folder(service, folder_id: str, max_files: int = 500) -> dict:
    root = service.files().get(
        fileId=folder_id, fields="id,name,mimeType,webViewLink", supportsAllDrives=True
    ).execute()
    if root.get("mimeType") != FOLDER_MIME:
        raise ValueError("ID đã cho không phải thư mục Google Drive")

    queue = deque([(folder_id, root["name"])])
    visited = set()
    items = []
    while queue:
        parent_id, parent_path = queue.popleft()
        if parent_id in visited:
            continue
        visited.add(parent_id)
        page_token = None
        while True:
            response = service.files().list(
                q=f"'{parent_id}' in parents and trashed = false",
                fields=FIELDS,
                pageSize=1000,
                pageToken=page_token,
                supportsAllDrives=True,
                includeItemsFromAllDrives=True,
            ).execute()
            if response.get("incompleteSearch"):
                raise RuntimeError("Drive báo tìm kiếm chưa đầy đủ; dừng để tránh báo cáo thiếu file")
            for item in response.get("files", []):
                if len(items) >= max_files:
                    raise RuntimeError(f"Đã chạm giới hạn {max_files} file; tăng --max-files để quét đủ")
                row = {
                    "id": item["id"],
                    "name": item.get("name", ""),
                    "path": f"{parent_path}/{item.get('name', '')}",
                    "parent_id": parent_id,
                    "mime_type": item.get("mimeType", ""),
                    "kind": file_kind(item),
                    "size": int(item["size"]) if item.get("size") else None,
                    "modified_time": item.get("modifiedTime"),
                    "url": item.get("webViewLink") or f"https://drive.google.com/open?id={item['id']}",
                    "can_download": item.get("capabilities", {}).get("canDownload"),
                }
                items.append(row)
                if row["kind"] == "folder":
                    queue.append((row["id"], row["path"]))
            page_token = response.get("nextPageToken")
            if not page_token:
                break

    video_keys = {(row["parent_id"], transcript_key(row["name"])) for row in items if row["kind"] == "video"}
    for row in items:
        if Path(row["name"]).suffix.lower() in TEXT_EXT:
            key = (row["parent_id"], transcript_key(row["name"]))
            if key in video_keys or re.search(r"(?:subtitle|caption|transcript|phu[ _.-]?de)", row["name"], re.I):
                row["kind"] = "transcript"

    by_parent_and_key = {}
    for row in items:
        if row["kind"] == "transcript":
            by_parent_and_key.setdefault((row["parent_id"], transcript_key(row["name"])), []).append(row)
    for row in items:
        if row["kind"] == "video":
            companions = by_parent_and_key.get((row["parent_id"], transcript_key(row["name"])), [])
            row["transcript_files"] = [{"id": x["id"], "name": x["name"]} for x in companions]
            row["embedded_transcript"] = "chưa thể xác định qua Drive API"

    items.sort(key=lambda row: row["path"].casefold())
    counts = Counter(row["kind"] for row in items)
    return {
        "folder": {"id": folder_id, "name": root["name"], "url": root.get("webViewLink")},
        "counts": dict(sorted(counts.items())),
        "total": len(items),
        "items": items,
    }


def report_markdown(report: dict) -> str:
    folder = report["folder"]
    counts = report["counts"]
    lines = [
        f"# Quét Google Drive: {folder['name']}",
        "",
        f"Thư mục: `{folder['id']}` · Tổng: {report['total']} mục · "
        f"Video: {counts.get('video', 0)} · Tài liệu: {counts.get('document', 0)} · "
        f"Phụ đề riêng: {counts.get('transcript', 0)}",
        "",
        "| Loại | Đường dẫn | Trạng thái phụ đề |",
        "|---|---|---|",
    ]
    for row in report["items"]:
        path = row["path"].replace("|", "\\|").replace("\n", " ")
        status = ""
        if row["kind"] == "video":
            names = ", ".join(x["name"] for x in row["transcript_files"])
            status = f"File riêng: {names}" if names else "Chưa thấy file phụ đề riêng"
            status += "; transcript trong video: chưa xác định"
        lines.append(f"| {row['kind']} | [{path}]({row['url']}) | {status} |")
    lines.extend([
        "",
        "> Báo cáo chỉ đọc metadata. Video chưa được tải xuống; transcript hiển thị trong trình phát Drive chưa được lấy qua API.",
        "",
    ])
    return "\n".join(lines)


def google_service(credentials_path: Path, token_path: Path):
    try:
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials
        from google_auth_httplib2 import AuthorizedHttp
        from google_auth_oauthlib.flow import InstalledAppFlow
        from googleapiclient.discovery import build
        from httplib2 import Http
    except ImportError as exc:
        raise RuntimeError("Thiếu thư viện Google; chạy: python3 -m pip install --target .deps -r requirements.txt rồi đặt PYTHONPATH=.deps") from exc

    if not credentials_path.is_file():
        raise RuntimeError(f"Thiếu OAuth Desktop credentials: {credentials_path}")
    scope = ["https://www.googleapis.com/auth/drive.readonly"]
    creds = Credentials.from_authorized_user_file(str(token_path), scope) if token_path.exists() else None
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            creds = InstalledAppFlow.from_client_secrets_file(str(credentials_path), scope).run_local_server(port=0)
        token_path.write_text(creds.to_json(), encoding="utf-8")
        os.chmod(token_path, 0o600)
    return build("drive", "v3", http=AuthorizedHttp(creds, http=Http(timeout=30)), cache_discovery=False)


def main() -> int:
    parser = argparse.ArgumentParser(description="Quét một thư mục Drive và các thư mục con, chỉ đọc")
    parser.add_argument("folder", help="Link hoặc ID thư mục Google Drive")
    parser.add_argument("--credentials", type=Path, default=Path("credentials.json"))
    parser.add_argument("--token", type=Path, default=Path("token.json"))
    parser.add_argument("--output-dir", type=Path, default=Path("drive-reports"))
    parser.add_argument("--max-files", type=int, default=500)
    args = parser.parse_args()
    try:
        if args.max_files < 1:
            raise ValueError("--max-files phải lớn hơn 0")
        folder_id = folder_id_from(args.folder)
        service = google_service(args.credentials, args.token)
        report = scan_folder(service, folder_id, args.max_files)
        args.output_dir.mkdir(parents=True, exist_ok=True)
        (args.output_dir / "scan.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        (args.output_dir / "scan.md").write_text(report_markdown(report), encoding="utf-8")
        print(f"Đã quét {report['total']} mục; báo cáo: {args.output_dir / 'scan.md'}")
        return 0
    except Exception as exc:
        print(f"Lỗi quét Drive: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
