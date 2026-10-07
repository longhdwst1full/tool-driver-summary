#!/usr/bin/env python3
"""Download and parse separate caption files discovered by drive_scan.py."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import sys

from drive_scan import google_service
from getsub_demo import markdown, parse_captions


MAX_CAPTION_BYTES = 2_000_000


def process_captions(service, scan: dict, output_dir: Path) -> dict:
    output_dir.mkdir(parents=True, exist_ok=True)
    results = []
    for item in scan["items"]:
        if item["kind"] != "transcript":
            continue
        entry = {"id": item["id"], "name": item["name"], "path": item["path"]}
        try:
            if not re.fullmatch(r"[A-Za-z0-9_-]+", item["id"]):
                raise ValueError("ID file không hợp lệ")
            if item.get("can_download") is False:
                raise ValueError("Tài khoản không có quyền tải file")
            if item.get("size") and item["size"] > MAX_CAPTION_BYTES:
                raise ValueError("File vượt giới hạn 2 MB cho bản thử")
            raw = service.files().get_media(fileId=item["id"], supportsAllDrives=True).execute()
            if len(raw) > MAX_CAPTION_BYTES:
                raise ValueError("File vượt giới hạn 2 MB cho bản thử")
            decoded = raw.decode("utf-8-sig")
            cues = parse_captions(decoded)
            output_name = item["id"] + ".md"
            (output_dir / output_name).write_text(markdown(item["name"], cues), encoding="utf-8")
            entry.update({
                "status": "ok",
                "cue_count": len(cues),
                "duration_ms": cues[-1].end_ms,
                "bytes": len(raw),
                "output": output_name,
            })
        except (OSError, UnicodeError, ValueError) as exc:
            entry.update({"status": "error", "error": str(exc)})
        except Exception as exc:
            entry.update({"status": "error", "error": f"Drive: {exc}"})
        results.append(entry)
    return {
        "folder_id": scan["folder"]["id"],
        "total": len(results),
        "ok": sum(x["status"] == "ok" for x in results),
        "errors": sum(x["status"] == "error" for x in results),
        "files": results,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Đọc các file phụ đề riêng từ báo cáo quét Drive")
    parser.add_argument("--scan", type=Path, default=Path("drive-reports/scan.json"))
    parser.add_argument("--credentials", type=Path, default=Path("credentials.json"))
    parser.add_argument("--token", type=Path, default=Path("token.json"))
    parser.add_argument("--output-dir", type=Path, default=Path("drive-reports/transcripts"))
    args = parser.parse_args()
    try:
        scan = json.loads(args.scan.read_text(encoding="utf-8"))
        service = google_service(args.credentials, args.token)
        result = process_captions(service, scan, args.output_dir)
        (args.output_dir / "manifest.json").write_text(
            json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        print(f"Đã đọc {result['ok']}/{result['total']} file phụ đề; lỗi: {result['errors']}")
        return 0 if result["errors"] == 0 else 1
    except (OSError, ValueError) as exc:
        print(f"Lỗi xử lý phụ đề: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
