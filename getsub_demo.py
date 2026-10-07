#!/usr/bin/env python3
"""Small, offline transcript demo with timestamped, source-backed output."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
import re
import sys


TIME_RANGE = re.compile(
    r"^\s*((?:\d{1,2}:)?\d{2}:\d{2}[,.]\d{3})\s*-->\s*"
    r"((?:\d{1,2}:)?\d{2}:\d{2}[,.]\d{3})(?:\s+.*)?$"
)
STOP_WORDS = {
    "ai", "bạn", "cần", "cho", "có", "của", "đã", "để", "được",
    "gì", "hay", "khi", "là", "làm", "một", "nào", "nên", "những",
    "ở", "sao", "thế", "thì", "và", "với",
}
NO_EVIDENCE = "Transcript không có đủ thông tin để trả lời câu hỏi này."


@dataclass(frozen=True)
class Cue:
    start_ms: int
    end_ms: int
    text: str


def parse_time(value: str) -> int:
    parts = value.replace(",", ".").split(":")
    if len(parts) == 2:
        hours, minutes, seconds = 0, int(parts[0]), parts[1]
    else:
        hours, minutes, seconds = int(parts[0]), int(parts[1]), parts[2]
    sec, millis = seconds.split(".")
    if minutes > 59 or int(sec) > 59:
        raise ValueError(f"Mốc thời gian không hợp lệ: {value}")
    return ((hours * 60 + minutes) * 60 + int(sec)) * 1000 + int(millis)


def parse_captions(raw: str) -> list[Cue]:
    """Read ordinary SRT or WebVTT cues; fail clearly on malformed time ranges."""
    raw = raw.lstrip("\ufeff").replace("\r\n", "\n").replace("\r", "\n")
    blocks = re.split(r"\n\s*\n", raw.strip())
    cues: list[Cue] = []
    for block in blocks:
        lines = [line.strip() for line in block.splitlines() if line.strip()]
        if not lines or lines[0].upper() == "WEBVTT":
            continue
        time_index = next((i for i, line in enumerate(lines) if "-->" in line), None)
        if time_index is None:
            raise ValueError(f"Thiếu mốc thời gian trong đoạn: {lines[0][:60]}")
        match = TIME_RANGE.match(lines[time_index])
        if not match:
            raise ValueError(f"Mốc thời gian không hợp lệ: {lines[time_index]}")
        start, end = (parse_time(value) for value in match.groups())
        if end <= start:
            raise ValueError(f"Mốc kết thúc phải sau mốc bắt đầu: {lines[time_index]}")
        content = " ".join(lines[time_index + 1 :]).strip()
        content = re.sub(r"<[^>]+>", "", content)
        if not content:
            raise ValueError(f"Đoạn {lines[time_index]} không có nội dung")
        cues.append(Cue(start, end, content))
    if not cues:
        raise ValueError("Không tìm thấy phụ đề trong tệp")
    if any(a.start_ms > b.start_ms for a, b in zip(cues, cues[1:])):
        raise ValueError("Các đoạn phụ đề không theo thứ tự thời gian")
    return cues


def format_time(ms: int) -> str:
    seconds = ms // 1000
    hours, remainder = divmod(seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}" if hours else f"{minutes:02d}:{seconds:02d}"


def citation(cue: Cue) -> str:
    return f"{format_time(cue.start_ms)}–{format_time(cue.end_ms)}"


def tokens(text: str) -> set[str]:
    # Keep Vietnamese accents: "lỗi" and "lời" must remain different words.
    return {word for word in re.findall(r"[^\W_]+", text.lower(), re.UNICODE) if word not in STOP_WORDS}


def answer(question: str, cues: list[Cue]) -> str:
    """Return the best matching source line, never an invented answer."""
    query = tokens(question)
    corpus = set().union(*(tokens(cue.text) for cue in cues))
    if not query or not query.issubset(corpus):
        return NO_EVIDENCE
    best = max(cues, key=lambda cue: len(query & tokens(cue.text)))
    if len(query & tokens(best.text)) < max(2, (len(query) + 1) // 2):
        return NO_EVIDENCE
    return f"[{citation(best)}] {best.text}"


def markdown(source: str, cues: list[Cue]) -> str:
    lines = [
        f"# Bản thử nghiệm: {source}",
        "",
        "> Demo offline: trích ý trực tiếp từ phụ đề; chưa dùng AI để diễn giải.",
        "",
        "## Tóm tắt nhanh",
        "",
    ]
    for cue in cues[:5]:
        lines.append(f"- {cue.text} **[{citation(cue)}]**")
    lines.extend(["", "## Timeline", "", "| Thời gian | Nội dung nguồn |", "|---|---|"])
    for cue in cues:
        lines.append(f"| {citation(cue)} | {cue.text.replace('|', '\\|')} |")
    if source == "agent_loop.srt":
        lines.extend([
            "",
            "## Hỏi đáp thử",
            "",
            "**Khi công cụ thời tiết lỗi, agent nên làm gì?**",
            "",
            answer("Khi công cụ thời tiết lỗi, agent nên làm gì?", cues),
            "",
            "**Bài giảng dùng API thời tiết nào?**",
            "",
            answer("Bài giảng dùng API thời tiết nào?", cues),
        ])
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Demo xử lý phụ đề có mốc thời gian")
    parser.add_argument("input", nargs="?", default="examples/agent_loop.srt", help="Tệp .srt hoặc .vtt")
    parser.add_argument("--output", help="Ghi kết quả Markdown ra tệp")
    parser.add_argument("--ask", help="Tìm câu trả lời trong transcript")
    args = parser.parse_args()
    try:
        path = Path(args.input)
        cues = parse_captions(path.read_text(encoding="utf-8"))
        result = answer(args.ask, cues) if args.ask else markdown(path.name, cues)
        if args.output:
            Path(args.output).write_text(result + "\n", encoding="utf-8")
            print(f"Đã ghi: {args.output}")
        else:
            print(result)
        return 0
    except (OSError, ValueError) as exc:
        print(f"Lỗi: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
