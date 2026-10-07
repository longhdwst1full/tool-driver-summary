#!/usr/bin/env python3
"""Split caption timelines and document text into stable, citable chunks."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import re


SENTENCE_END = re.compile(r"[.!?…:;]\s*$")


@dataclass(frozen=True)
class Chunk:
    chunk_id: str
    source_id: str
    kind: str
    text: str
    start: str | None = None
    end: str | None = None
    para_start: int | None = None
    para_end: int | None = None

    def to_dict(self) -> dict:
        return asdict(self)


def seconds(value: str) -> int:
    """Convert 'MM:SS' or 'HH:MM:SS' (as written by read_cues) to seconds."""
    parts = [int(part) for part in value.split(":")]
    if len(parts) == 2:
        parts.insert(0, 0)
    if len(parts) != 3:
        raise ValueError(f"Mốc thời gian không hợp lệ: {value}")
    hours, minutes, secs = parts
    return hours * 3600 + minutes * 60 + secs


def chunk_cues(source_id: str, cues: list[tuple[str, str, str]],
               window_s: int = 360, max_s: int = 480) -> list[Chunk]:
    """Group cues into time windows; close a window at a sentence end after window_s, always by max_s."""
    if not cues:
        raise ValueError("Không có đoạn phụ đề để chia")
    if not 0 < window_s <= max_s:
        raise ValueError("Cần 0 < window_s <= max_s")
    chunks = []
    group: list[tuple[str, str, str]] = []

    def close() -> None:
        chunks.append(Chunk(
            chunk_id=f"{source_id}:c{len(chunks) + 1:03d}", source_id=source_id, kind="caption",
            text="\n".join(cue[2] for cue in group), start=group[0][0], end=group[-1][1],
        ))
        group.clear()

    for cue in cues:
        if group and seconds(cue[1]) - seconds(group[0][0]) > max_s:
            close()
        group.append(cue)
        span = seconds(cue[1]) - seconds(group[0][0])
        if span >= window_s and SENTENCE_END.search(cue[2]):
            close()
    if group:
        close()
    return chunks


def chunk_document(source_id: str, text: str, max_chars: int = 4000) -> list[Chunk]:
    """Pack paragraphs into chunks up to max_chars; a longer paragraph becomes its own chunk."""
    if max_chars <= 0:
        raise ValueError("max_chars phải lớn hơn 0")
    paragraphs = [part.strip() for part in re.split(r"\n\s*\n", text) if part.strip()]
    if not paragraphs:
        raise ValueError("Tài liệu không có văn bản để chia")
    chunks = []
    group: list[tuple[int, str]] = []
    size = 0

    def close() -> None:
        chunks.append(Chunk(
            chunk_id=f"{source_id}:d{len(chunks) + 1:03d}", source_id=source_id, kind="document",
            text="\n\n".join(part for _, part in group),
            para_start=group[0][0], para_end=group[-1][0],
        ))
        group.clear()

    for number, paragraph in enumerate(paragraphs, start=1):
        if group and size + len(paragraph) > max_chars:
            close()
            size = 0
        group.append((number, paragraph))
        size += len(paragraph)
    if group:
        close()
    return chunks
