#!/usr/bin/env python3
"""Read supported documents from an already-scanned Google Drive folder."""

from __future__ import annotations

import argparse
from hashlib import sha256
from io import BytesIO
import json
from pathlib import Path
import re
import sys

from drive_scan import google_service


MAX_DOCUMENT_BYTES = 10_000_000
PDF_MIME = "application/pdf"
DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
TEXT_MIME = "text/plain"


def extract_text(raw: bytes, mime_type: str) -> str:
    if mime_type == TEXT_MIME:
        try:
            return raw.decode("utf-8-sig")
        except UnicodeDecodeError:
            return raw.decode("utf-16")
    if mime_type == PDF_MIME:
        from pypdf import PdfReader

        reader = PdfReader(BytesIO(raw), strict=False)
        return "\n\n".join(page.extract_text() or "" for page in reader.pages)
    if mime_type == DOCX_MIME:
        from docx import Document

        document = Document(BytesIO(raw))
        parts = [paragraph.text for paragraph in document.paragraphs if paragraph.text.strip()]
        for table in document.tables:
            for row in table.rows:
                parts.append("\t".join(cell.text for cell in row.cells))
        return "\n".join(parts)
    raise ValueError(f"Chưa hỗ trợ trích văn bản từ MIME: {mime_type}")


def save_manifest(path: Path, scan: dict, results: list[dict]) -> dict:
    counts = {status: sum(x["status"] == status for x in results) for status in (
        "ok", "needs_ocr", "too_large", "unsupported", "no_access", "error"
    )}
    manifest = {"folder_id": scan["folder"]["id"], "total": len(results), **counts, "files": results}
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)
    return manifest


def download_media(service, file_id: str, size: int | None, max_bytes: int) -> bytes:
    request = service.files().get_media(fileId=file_id, supportsAllDrives=True)
    if not size or size <= 10_000_000:
        return request.execute()
    from googleapiclient.http import MediaIoBaseDownload

    stream = BytesIO()
    downloader = MediaIoBaseDownload(stream, request, chunksize=2_000_000)
    done = False
    while not done:
        status, done = downloader.next_chunk(num_retries=2)
        if status is not None:
            print(f"Đang tải tài liệu lớn {file_id}: {status.progress():.0%}",
                  file=sys.stderr, flush=True)
        if stream.tell() > max_bytes:
            raise ValueError(f"Tệp tải về vượt giới hạn {max_bytes} byte")
    return stream.getvalue()


def process_documents(service, scan: dict, output_dir: Path, max_bytes: int = MAX_DOCUMENT_BYTES,
                      refresh: bool = False) -> dict:
    output_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = output_dir / "manifest.json"
    previous = {}
    if manifest_path.is_file() and not refresh:
        old = json.loads(manifest_path.read_text(encoding="utf-8"))
        previous = {entry["id"]: entry for entry in old.get("files", [])}
    results = []
    for item in scan["items"]:
        if item["kind"] != "document":
            continue
        entry = {
            "id": item["id"],
            "name": item["name"],
            "path": item["path"],
            "mime_type": item["mime_type"],
            "url": item["url"],
            "modified_time": item.get("modified_time"),
        }
        try:
            if not re.fullmatch(r"[A-Za-z0-9_-]+", item["id"]):
                raise ValueError("ID file không hợp lệ")
            output_name = item["id"] + ".txt"
            output_path = output_dir / output_name
            prior = previous.get(item["id"])
            if (not refresh and prior and prior.get("modified_time") == item.get("modified_time")
                    and prior.get("status") in {"needs_ocr", "unsupported", "no_access"}):
                entry.update(prior)
                results.append(entry)
                save_manifest(manifest_path, scan, results)
                continue
            if (not refresh and prior and prior.get("status") == "ok"
                    and prior.get("modified_time") == item.get("modified_time")
                    and output_path.is_file()):
                content = output_path.read_text(encoding="utf-8").strip()
                if content and sha256(content.encode("utf-8")).hexdigest() == prior.get("sha256"):
                    entry.update(prior)
                    results.append(entry)
                    save_manifest(manifest_path, scan, results)
                    continue
            # A run interrupted before its first manifest can still reuse extracted text.
            if not refresh and not prior and output_path.is_file():
                content = output_path.read_text(encoding="utf-8").strip()
                if content:
                    entry.update({"status": "ok", "bytes": item.get("size"),
                                  "characters": len(content),
                                  "sha256": sha256(content.encode("utf-8")).hexdigest(),
                                  "output": output_name})
                    results.append(entry)
                    save_manifest(manifest_path, scan, results)
                    continue
            if item.get("can_download") is False:
                entry.update({"status": "no_access"})
            elif item.get("size") and item["size"] > max_bytes:
                entry.update({"status": "too_large", "bytes": item["size"]})
            elif item["mime_type"] not in {PDF_MIME, DOCX_MIME, TEXT_MIME}:
                entry.update({"status": "unsupported"})
            else:
                raw = download_media(service, item["id"], item.get("size"), max_bytes)
                if len(raw) > max_bytes:
                    entry.update({"status": "too_large", "bytes": len(raw)})
                elif item["mime_type"] == PDF_MIME and raw.startswith((b"\xff\xd8", b"\x89PNG")):
                    entry.update({"status": "needs_ocr", "bytes": len(raw),
                                  "reason": "Tệp có đuôi PDF nhưng chứa ảnh"})
                else:
                    content = extract_text(raw, item["mime_type"]).strip()
                    if not content:
                        entry.update({"status": "needs_ocr", "bytes": len(raw)})
                    else:
                        output_path.write_text(content + "\n", encoding="utf-8")
                        entry.update({
                            "status": "ok",
                            "bytes": len(raw),
                            "characters": len(content),
                            "sha256": sha256(content.encode("utf-8")).hexdigest(),
                            "output": output_name,
                        })
        except Exception as exc:
            entry.update({"status": "error", "error": str(exc)})
        results.append(entry)
        save_manifest(manifest_path, scan, results)
    return save_manifest(manifest_path, scan, results)


def main() -> int:
    parser = argparse.ArgumentParser(description="Trích xuất văn bản PDF, DOCX và TXT trong báo cáo quét Drive")
    parser.add_argument("--scan", type=Path, default=Path("drive-reports/scan.json"))
    parser.add_argument("--credentials", type=Path, default=Path("credentials.json"))
    parser.add_argument("--token", type=Path, default=Path("token.json"))
    parser.add_argument("--output-dir", type=Path, default=Path("drive-reports/documents"))
    parser.add_argument("--max-mb", type=int, default=10, help="Giới hạn tải từng tài liệu (MB)")
    parser.add_argument("--refresh", action="store_true", help="Tải và trích xuất lại mọi tài liệu")
    args = parser.parse_args()
    try:
        if args.max_mb < 1:
            raise ValueError("--max-mb phải lớn hơn 0")
        scan = json.loads(args.scan.read_text(encoding="utf-8"))
        service = google_service(args.credentials, args.token)
        result = process_documents(service, scan, args.output_dir,
                                   max_bytes=args.max_mb * 1_000_000, refresh=args.refresh)
        print(
            f"Tài liệu: {result['ok']}/{result['total']} đã đọc; "
            f"cần OCR: {result['needs_ocr']}; quá lớn: {result['too_large']}; "
            f"không hỗ trợ: {result['unsupported']}; lỗi: {result['error']}"
        )
        return 0 if result["error"] == 0 else 1
    except (OSError, ValueError) as exc:
        print(f"Lỗi xử lý tài liệu: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
