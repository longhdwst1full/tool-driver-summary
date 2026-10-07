#!/usr/bin/env python3
"""LLM backends returning schema-shaped JSON, plus versioned prompt templates."""

from __future__ import annotations

from dataclasses import dataclass
import json
import os
from pathlib import Path
import shutil
import subprocess
from tempfile import TemporaryDirectory
from typing import Protocol


class LLMClient(Protocol):
    name: str

    def generate(self, prompt: str, schema: dict) -> dict: ...


@dataclass(frozen=True)
class Prompt:
    """Template filled with str.format; bump version whenever the wording changes."""
    name: str
    version: str
    template: str

    @property
    def prompt_id(self) -> str:
        return f"{self.name}@{self.version}"

    def render(self, **values: str) -> str:
        return self.template.format(**values)


def find_codex(explicit: Path | None = None, home: Path | None = None) -> str:
    """Find CLI in PATH or in the installed VS Code Codex extension."""
    if explicit is not None:
        candidate = explicit.expanduser()
        if candidate.is_file() and os.access(candidate, os.X_OK):
            return str(candidate.resolve())
        raise ValueError(f"Codex CLI không tồn tại hoặc không chạy được: {candidate}")
    command = shutil.which("codex")
    if command:
        return command
    home = home or Path.home()
    candidates = []
    for extension_root in (home / ".vscode/extensions", home / ".vscode-insiders/extensions"):
        candidates.extend(path for path in extension_root.glob("openai.chatgpt-*/bin/*/codex")
                          if path.is_file() and os.access(path, os.X_OK))
    if candidates:
        return str(max(candidates, key=lambda path: path.stat().st_mtime).resolve())
    raise ValueError("Không tìm thấy Codex CLI. Hãy chỉ định đường dẫn bằng --codex /duong/dan/toi/codex")


class CodexCLIClient:
    """Runs `codex exec` read-only in an empty temp folder with an output schema."""

    def __init__(self, codex: str, timeout: int = 900, model: str | None = None):
        self.codex = codex
        self.timeout = timeout
        self.model = model
        self.name = f"codex-cli:{model}" if model else "codex-cli"

    def command(self, folder: Path) -> list[str]:
        command = [self.codex, "exec", "--ephemeral", "--ignore-user-config", "--skip-git-repo-check",
                   "--sandbox", "read-only", "-C", str(folder),
                   "--output-schema", str(folder / "schema.json"),
                   "--output-last-message", str(folder / "result.json")]
        if self.model:
            command.extend(["--model", self.model])
        return command + ["-"]

    def generate(self, prompt: str, schema: dict) -> dict:
        with TemporaryDirectory(prefix="codex-llm-") as temp:
            folder = Path(temp)
            (folder / "schema.json").write_text(json.dumps(schema, ensure_ascii=False), encoding="utf-8")
            output = folder / "result.json"
            run = subprocess.run(self.command(folder), input=prompt, text=True, capture_output=True,
                                 timeout=self.timeout)
            if run.returncode != 0 or not output.is_file():
                raise RuntimeError(f"Codex CLI lỗi (mã {run.returncode}): {run.stderr[-1000:]}")
            try:
                return json.loads(output.read_text(encoding="utf-8"))
            except json.JSONDecodeError as exc:
                raise RuntimeError(f"Codex CLI trả về JSON không hợp lệ: {exc}") from exc
