#!/usr/bin/env python3
"""Download and parse separate caption files discovered by drive_scan.py."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import sys

from drive_scan import google_service, normalized_label
from getsub_demo import markdown, parse_captions
from output_layout import output_paths, safe_output_file, video_title


MAX_CAPTION_BYTES = 2_000_000


def parse_drive_caption(raw: str, name: str):
    """Accept two common SRT export quirks without changing cue text."""
    if name.casefold().endswith(".srt"):
        raw = raw.replace("\r\n", "\n").replace("\r", "\n")
        raw = re.sub(
            r"(?m)^(\d+)[ \t]*\n(?:[ \t]*\n)+(?=[ \t]*(?:\d{1,2}:)?\d{2}:\d{2}[,.]\d{3}[ \t]*-->)",
            r"\1\n", raw,
        )
        def extend_zero_length(match: re.Match) -> str:
            start, end = match.group(1), match.group(3)
            if start.replace(",", ".") != end.replace(",", "."):
                return end
            hours, minutes, rest = end.split(":")
            seconds, millis = re.split(r"[,.]", rest)
            total = ((int(hours) * 60 + int(minutes)) * 60 + int(seconds)) * 1000 + int(millis) + 1
            h, remainder = divmod(total, 3_600_000)
            m, remainder = divmod(remainder, 60_000)
            s, ms = divmod(remainder, 1000)
            separator = "," if "," in end else "."
            return f"{h:02d}:{m:02d}:{s:02d}{separator}{ms:03d}"

        raw = re.sub(
            r"(?m)^(\d{2}:\d{2}:\d{2}[,.]\d{3})([ \t]*-->[ \t]*)"
            r"(\d{2}:\d{2}:\d{2}[,.]\d{3})(?=[ \t]*$)",
            lambda match: match.group(1) + match.group(2) + extend_zero_length(match), raw,
        )
    return parse_captions(raw)


def caption_video_key(name: str) -> str:
    """Match numbered lessons within one chapter, ignoring a trailing watermark."""
    stem = re.sub(r"\s*\([^)]*\)\s*$", "", Path(name).stem)
    stem = re.sub(r"^\s*(?:Bài|Bai)?\s*0*(\d+)\s*[.\-:]?\s*",
                  lambda match: str(int(match.group(1))) + " ", stem, flags=re.I)
    return normalized_label(stem)


def caption_report(scan: dict, results: list[dict]) -> dict:
    return {
        "folder_id": scan["folder"]["id"],
        "total": len(results),
        "ok": sum(x["status"] == "ok" for x in results),
        "untimed_text": sum(x["status"] == "untimed_text" for x in results),
        "errors": sum(x["status"] == "error" for x in results),
        "files": results,
    }


def process_captions(service, scan: dict, output_dir: Path) -> dict:
    output_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = output_dir / "manifest.json"
    baseline_path = output_dir / "manifest.baseline.json"
    old = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.is_file() else {}
    baseline = json.loads(baseline_path.read_text(encoding="utf-8")) if baseline_path.is_file() else {}
    previous = {}
    for report in (baseline, old):
        if report.get("folder_id") == scan["folder"]["id"]:
            previous.update({row["id"]: row for row in report.get("files", [])})
    if old and not baseline_path.is_file():
        baseline_path.write_text(json.dumps(old, ensure_ascii=False) + "\n", encoding="utf-8")
    named_paths = output_paths(scan, "transcript")
    videos_by_caption = {caption["id"]: video for video in scan["items"] if video["kind"] == "video"
                         for caption in video.get("transcript_files", [])}
    videos_by_key = {}
    captions_by_key = {}
    for item in scan["items"]:
        if item["kind"] not in {"video", "transcript"}:
            continue
        key = (item["parent_id"], caption_video_key(item["name"]))
        (videos_by_key if item["kind"] == "video" else captions_by_key).setdefault(key, []).append(item)
    paired_video_ids = {video["id"] for video in videos_by_caption.values()}
    for key, captions in captions_by_key.items():
        matches = videos_by_key.get(key, [])
        if (len(captions) == len(matches) == 1 and key[1]
                and captions[0]["id"] not in videos_by_caption
                and matches[0]["id"] not in paired_video_ids):
            videos_by_caption[captions[0]["id"]] = matches[0]
            paired_video_ids.add(matches[0]["id"])
    results = []
    for item in scan["items"]:
        if item["kind"] != "transcript":
            continue
        video = videos_by_caption.get(item["id"])
        entry = {"id": item["id"], "name": item["name"], "path": item["path"],
                 "modified_time": item.get("modified_time"),
                 "video_id": video["id"] if video else None}
        try:
            if not re.fullmatch(r"[A-Za-z0-9_-]+", item["id"]):
                raise ValueError("ID file không hợp lệ")
            if item.get("can_download") is False:
                raise ValueError("Tài khoản không có quyền tải file")
            if item.get("size") and item["size"] > MAX_CAPTION_BYTES:
                raise ValueError("File vượt giới hạn 2 MB cho bản thử")
            output_name = named_paths[item["id"]].as_posix()
            output_path = safe_output_file(output_dir, output_name, ".md")
            prior = previous.get(item["id"])
            if (prior and prior.get("status") == "ok"
                    and prior.get("modified_time") == item.get("modified_time")
                    and prior.get("output") == output_name and output_path.is_file()):
                entry.update({key: prior[key] for key in ("status", "cue_count", "duration_ms", "bytes", "output")})
            elif (prior and prior.get("status") == "untimed_text" and item["name"].casefold().endswith(".txt")
                  and prior.get("modified_time") == item.get("modified_time")
                  and prior.get("output") == Path(output_name).with_suffix(".txt").as_posix()
                  and safe_output_file(output_dir, prior["output"], ".txt").is_file()):
                entry.update({key: prior[key] for key in ("status", "bytes", "characters", "output")})
            else:
                raw = service.files().get_media(fileId=item["id"], supportsAllDrives=True).execute()
                if len(raw) > MAX_CAPTION_BYTES:
                    raise ValueError("File vượt giới hạn 2 MB cho bản thử")
                decoded = raw.decode("utf-8-sig")
                try:
                    cues = parse_drive_caption(decoded, item["name"])
                except ValueError:
                    if not item["name"].casefold().endswith(".txt") or not decoded.strip():
                        raise
                    text_name = Path(output_name).with_suffix(".txt").as_posix()
                    text_path = safe_output_file(output_dir, text_name, ".txt")
                    text_path.parent.mkdir(parents=True, exist_ok=True)
                    text_path.write_text(decoded.strip() + "\n", encoding="utf-8")
                    entry.update({"status": "untimed_text", "bytes": len(raw),
                                  "characters": len(decoded.strip()), "output": text_name})
                else:
                    output_path.parent.mkdir(parents=True, exist_ok=True)
                    title = video_title(video["name"]) if video else item["name"]
                    output_path.write_text(markdown(title, cues), encoding="utf-8")
                    legacy_path = safe_output_file(output_dir, item["id"] + ".md", ".md")
                    if legacy_path != output_path and legacy_path.is_file():
                        legacy_path.unlink()
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
        if len(results) % 20 == 0:
            temporary = manifest_path.with_suffix(".tmp")
            temporary.write_text(json.dumps(caption_report(scan, results), ensure_ascii=False) + "\n", encoding="utf-8")
            temporary.replace(manifest_path)
    report = caption_report(scan, results)
    temporary = manifest_path.with_suffix(".tmp")
    temporary.write_text(json.dumps(report, ensure_ascii=False) + "\n", encoding="utf-8")
    temporary.replace(manifest_path)
    baseline_path.unlink(missing_ok=True)
    return report


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
        print(f"Đã đọc {result['ok']}/{result['total']} file phụ đề; "
              f"văn bản không mốc: {result['untimed_text']}; lỗi: {result['errors']}")
        return 0 if result["errors"] == 0 else 1
    except (OSError, ValueError) as exc:
        print(f"Lỗi xử lý phụ đề: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
