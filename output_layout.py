"""Stable, readable local paths for files generated from a Drive scan."""

from __future__ import annotations

from hashlib import sha1
from pathlib import Path
import re
import unicodedata


PROMOTIONAL_NAME = re.compile(r"^0\.\s*khoahocgiahoi\.com\b", re.I)
PROMOTIONAL_TEXT = "các khóa học thuộc về khóa học giá hời"
VIDEO_WATERMARK = re.compile(r"\s*\(khoahocgiahoi\.com[^)]*\)\s*$", re.I)
LOCALE_SUFFIX = re.compile(r"[ _.-]+(?:vi(?:[_-]vn)?|en(?:[_-]us)?)$", re.I)
INVALID_CHARACTERS = re.compile(r"[\\/<>:\"|?*\x00-\x1f]")


def natural_key(value: str) -> tuple:
    """Sort numbered chapters and lessons as 1, 2, 10 instead of 1, 10, 2."""
    return tuple(int(part) if part.isdigit() else part.casefold() for part in re.split(r"(\d+)", value))


def is_promotional_document(item: dict, content: str | None = None) -> bool:
    if item.get("kind") != "document":
        return False
    if PROMOTIONAL_NAME.search(item.get("name", "")):
        return True
    return bool(content and content.lstrip().casefold().startswith(PROMOTIONAL_TEXT))


def safe_segment(value: str, max_bytes: int = 180) -> str:
    clean = unicodedata.normalize("NFC", value)
    clean = INVALID_CHARACTERS.sub("-", clean)
    clean = re.sub(r"\s+", " ", clean).strip(" .")
    if not clean or clean in {".", ".."}:
        clean = "Không tên"
    if len(clean.encode("utf-8")) <= max_bytes:
        return clean
    suffix = "-" + sha1(clean.encode("utf-8")).hexdigest()[:8]
    budget = max_bytes - len(suffix.encode("utf-8"))
    prefix = ""
    for char in clean:
        if len((prefix + char).encode("utf-8")) > budget:
            break
        prefix += char
    return prefix.rstrip(" .") + suffix


def video_title(name: str) -> str:
    return VIDEO_WATERMARK.sub("", name.rsplit(".", 1)[0]).strip()


def output_paths(scan: dict, kind: str) -> dict[str, Path]:
    """Map Drive IDs to paths relative to one output directory."""
    if kind not in {"transcript", "document", "ai_note"}:
        raise ValueError(f"Loại kết quả không hợp lệ: {kind}")
    folders = {row["id"]: row for row in scan["items"] if row["kind"] == "folder"}
    videos_by_caption = {caption["id"]: row for row in scan["items"] if row["kind"] == "video"
                         for caption in row.get("transcript_files", [])}
    source_kind = "document" if kind == "document" else "transcript"
    items = sorted((row for row in scan["items"] if row["kind"] == source_kind),
                   key=lambda row: (row["path"].casefold(), row["id"]))
    seen: set[str] = set()
    result: dict[str, Path] = {}
    for item in items:
        ancestors = []
        parent_id = item["parent_id"]
        visited = set()
        while parent_id != scan["folder"]["id"]:
            if parent_id in visited or parent_id not in folders:
                raise ValueError(f"Cấu trúc thư mục không hợp lệ cho {item['id']}")
            visited.add(parent_id)
            parent = folders[parent_id]
            ancestors.append(safe_segment(parent["name"]))
            parent_id = parent["parent_id"]
        ancestors.reverse()
        if kind == "document":
            title = item["name"].rsplit(".", 1)[0]
            extension = ".txt"
        else:
            video = videos_by_caption.get(item["id"])
            title = video_title(video["name"]) if video else LOCALE_SUFFIX.sub("", item["name"].rsplit(".", 1)[0])
            extension = ".md"
        stem = safe_segment(title, max_bytes=170)
        candidate = Path(*ancestors, stem + extension)
        key = candidate.as_posix().casefold()
        if key in seen:
            candidate = Path(*ancestors, f"{stem}-{item['id'][:8]}{extension}")
            key = candidate.as_posix().casefold()
        if key in seen:
            raise ValueError(f"Trùng đường dẫn kết quả: {candidate}")
        seen.add(key)
        result[item["id"]] = candidate
    return result


def safe_output_file(output_dir: Path, relative: str | Path, extension: str) -> Path:
    candidate = Path(relative)
    if candidate.is_absolute() or candidate.suffix != extension or any(part in {".", ".."} for part in candidate.parts):
        raise ValueError("Đường dẫn kết quả không hợp lệ")
    root = output_dir.resolve()
    full = (root / candidate).resolve()
    if not full.is_relative_to(root):
        raise ValueError("Đường dẫn kết quả nằm ngoài thư mục báo cáo")
    return full
