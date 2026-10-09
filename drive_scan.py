#!/usr/bin/env python3
"""Read-only inventory of one Google Drive folder and its subfolders."""

from __future__ import annotations

import argparse
from collections import Counter, deque
from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
import re
import sys
from threading import local
import unicodedata
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


def video_source_status(item: dict, has_caption: bool | None = None) -> str:
    """Text source available for a video: caption file, downloadable for ASR, or none."""
    if has_caption is None:
        has_caption = bool(item.get("transcript_files"))
    if has_caption:
        return "caption_file"
    return "asr_ready" if item.get("can_download") is True else "no_source"


def transcript_key(name: str) -> str:
    stem = Path(name).stem.casefold()
    stem = re.sub(r"\s*\([^)]*\)\s*$", "", stem)
    stem = re.sub(r"[ _.-]+(?:vi(?:[_-]vn)?|en(?:[_-]us)?|vietnamese|english)$", "", stem)
    stem = re.sub(r"[ _.-]+(?:subtitles?|captions?|transcripts?|phu[ _.-]?de)$", "", stem)
    return re.sub(r"[^\w]+", "", stem)


def normalized_label(value: str) -> str:
    value = unicodedata.normalize("NFKD", value.casefold().replace("đ", "d"))
    return " ".join(re.sub(r"[^a-z0-9]+", " ",
                           "".join(char for char in value if not unicodedata.combining(char))).split())


def curated_exclusion(name: str, kind: str, parent_path: str, root_path: str) -> str | None:
    """Skip requested course branches and promotional files before traversing them."""
    label = normalized_label(name)
    if kind == "folder":
        if parent_path == root_path:
            if any(term in label for term in ("dung phim va nhiep anh", "thiet ke do hoa",
                                               "tin hoc van phong")):
                return "Nhóm khóa học được loại trừ"
            if re.match(r"^15\b", label) and "qua tang" in label and "tai nguyen" in label:
                return "Quà tặng tài nguyên"
        ancestors = [normalized_label(part) for part in parent_path.split("/")]
        if any("khoa hoc khac" in part for part in ancestors) and any(
                term in label for term in ("am nhac", "guitar", "lam nhac", "piano",
                                            "suc khoe", "lam dep")):
            return "Chủ đề loại trừ trong Khóa học khác"
    elif ("nhom zalo" in label
          or "cac khoa hoc thuoc ve khoa hoc gia hoi" in label
          or label.startswith("0 khoahocgiahoi com")):
        return "File quảng bá/hỗ trợ"
    return None


def scan_folder(service, folder_id: str, max_files: int = 500,
                curated_exclusions: bool = False, checkpoint_path: Path | None = None,
                workers: int = 1, service_factory=None) -> dict:
    if workers < 1 or (workers > 1 and service_factory is None):
        raise ValueError("Quét song song cần --workers >= 2 và kết nối Drive riêng cho mỗi luồng")
    root = service.files().get(
        fileId=folder_id, fields="id,name,mimeType,webViewLink", supportsAllDrives=True
    ).execute(num_retries=5)
    if root.get("mimeType") != FOLDER_MIME:
        raise ValueError("ID đã cho không phải thư mục Google Drive")

    queue = deque([(folder_id, root["name"])])
    visited = set()
    items = []
    skipped = {"folders": 0, "files": 0, "examples": []}
    if checkpoint_path and checkpoint_path.is_file():
        state = json.loads(checkpoint_path.read_text(encoding="utf-8"))
        if (state.get("folder_id") != folder_id or state.get("root_name") != root["name"]
                or state.get("curated_exclusions") != curated_exclusions):
            raise ValueError("Điểm tiếp tục không khớp thư mục hoặc bộ lọc")
        queue = deque((row[0], row[1]) for row in state["queue"])
        visited = set(state["visited"])
        items = state["items"]
        skipped = state["skipped"]

    def save_checkpoint() -> None:
        if checkpoint_path is None:
            return
        checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
        state = {"folder_id": folder_id, "root_name": root["name"],
                 "curated_exclusions": curated_exclusions, "queue": list(queue),
                 "visited": list(visited), "items": items, "skipped": skipped}
        temporary = checkpoint_path.with_suffix(".tmp")
        temporary.write_text(json.dumps(state, ensure_ascii=False, separators=(",", ":")),
                             encoding="utf-8")
        temporary.replace(checkpoint_path)

    worker_state = local()

    def list_children(parent_id: str) -> list[dict]:
        api_service = service
        if service_factory is not None:
            api_service = getattr(worker_state, "service", None)
            if api_service is None:
                api_service = service_factory()
                worker_state.service = api_service
        children = []
        page_token = None
        while True:
            response = api_service.files().list(
                q=f"'{parent_id}' in parents and trashed = false",
                fields=FIELDS,
                pageSize=1000,
                pageToken=page_token,
                supportsAllDrives=True,
                includeItemsFromAllDrives=True,
            ).execute(num_retries=5)
            if response.get("incompleteSearch"):
                raise RuntimeError("Drive báo tìm kiếm chưa đầy đủ; dừng để tránh báo cáo thiếu file")
            children.extend(response.get("files", []))
            page_token = response.get("nextPageToken")
            if not page_token:
                return children

    completed_since_checkpoint = 0
    executor = ThreadPoolExecutor(max_workers=workers) if workers > 1 else None
    try:
        while queue:
            batch = []
            while queue and len(batch) < workers:
                folder = queue.popleft()
                if folder[0] not in visited:
                    batch.append(folder)
            if not batch:
                continue
            try:
                if executor:
                    futures = [executor.submit(list_children, parent_id) for parent_id, _ in batch]
                    batch_items = [future.result() for future in futures]
                else:
                    batch_items = [list_children(batch[0][0])]
            except Exception:
                queue.extendleft(reversed(batch))
                save_checkpoint()
                raise
            for (parent_id, parent_path), children in zip(batch, batch_items):
                for item in children:
                    kind = file_kind(item)
                    reason = (curated_exclusion(item.get("name", ""), kind, parent_path, root["name"])
                              if curated_exclusions else None)
                    if reason:
                        skipped["folders" if kind == "folder" else "files"] += 1
                        if len(skipped["examples"]) < 30:
                            skipped["examples"].append({"path": f"{parent_path}/{item.get('name', '')}",
                                                        "reason": reason})
                        continue
                    if len(items) >= max_files:
                        raise RuntimeError(f"Đã chạm giới hạn {max_files} file; tăng --max-files để quét đủ")
                    row = {
                        "id": item["id"],
                        "name": item.get("name", ""),
                        "path": f"{parent_path}/{item.get('name', '')}",
                        "parent_id": parent_id,
                        "mime_type": item.get("mimeType", ""),
                        "kind": kind,
                        "size": int(item["size"]) if item.get("size") else None,
                        "modified_time": item.get("modifiedTime"),
                        "url": item.get("webViewLink") or f"https://drive.google.com/open?id={item['id']}",
                        "can_download": item.get("capabilities", {}).get("canDownload"),
                    }
                    items.append(row)
                    if row["kind"] == "folder":
                        queue.append((row["id"], row["path"]))
                visited.add(parent_id)
            completed_since_checkpoint += len(batch)
            if completed_since_checkpoint >= 20:
                save_checkpoint()
                if checkpoint_path:
                    print(f"Đã duyệt {len(visited)} thư mục; {len(items)} mục đã giữ",
                          file=sys.stderr, flush=True)
                completed_since_checkpoint = 0
    finally:
        if executor:
            executor.shutdown(wait=True)

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
            row["source_status"] = video_source_status(row)

    items.sort(key=lambda row: row["path"].casefold())
    counts = Counter(row["kind"] for row in items)
    return {
        "folder": {"id": folder_id, "name": root["name"], "url": root.get("webViewLink")},
        "counts": dict(sorted(counts.items())),
        "total": len(items),
        "items": items,
        "exclusions": skipped if curated_exclusions else None,
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
    if report.get("exclusions"):
        excluded = report["exclusions"]
        lines[3:3] = [f"Đã bỏ qua {excluded['folders']} nhánh thư mục và "
                      f"{excluded['files']} file theo bộ lọc yêu cầu.", ""]
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
    parser.add_argument("--curated-exclusions", action="store_true",
                        help="Bỏ qua các nhóm học và file quảng bá được chỉ định")
    parser.add_argument("--workers", type=int, default=1,
                        help="Số kết nối Drive song song; dùng 2-4 cho thư mục lớn")
    args = parser.parse_args()
    try:
        if args.max_files < 1:
            raise ValueError("--max-files phải lớn hơn 0")
        if args.workers < 1 or args.workers > 4:
            raise ValueError("--workers phải trong khoảng 1-4")
        folder_id = folder_id_from(args.folder)
        service = google_service(args.credentials, args.token)
        report = scan_folder(service, folder_id, args.max_files,
                             curated_exclusions=args.curated_exclusions,
                             checkpoint_path=args.output_dir / "scan.checkpoint.json",
                             workers=args.workers,
                             service_factory=(lambda: google_service(args.credentials, args.token))
                             if args.workers > 1 else None)
        args.output_dir.mkdir(parents=True, exist_ok=True)
        (args.output_dir / "scan.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        (args.output_dir / "scan.md").write_text(report_markdown(report), encoding="utf-8")
        (args.output_dir / "scan.checkpoint.json").unlink(missing_ok=True)
        print(f"Đã quét {report['total']} mục; báo cáo: {args.output_dir / 'scan.md'}")
        return 0
    except Exception as exc:
        print(f"Lỗi quét Drive: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
