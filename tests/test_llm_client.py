import json
from pathlib import Path
import subprocess
import unittest
from unittest.mock import patch

from llm_client import CodexCLIClient, Prompt


class LLMClientTests(unittest.TestCase):
    def test_prompt_render_keeps_braces_in_values(self):
        prompt = Prompt("p", "2", "A {name} B")
        self.assertEqual(prompt.prompt_id, "p@2")
        self.assertEqual(prompt.render(name="{x}"), "A {x} B")

    def test_codex_client_runs_read_only_with_schema(self):
        def fake_run(command, input, **kwargs):
            folder = Path(command[command.index("-C") + 1])
            self.assertEqual(json.loads((folder / "schema.json").read_text())["type"], "object")
            (folder / "result.json").write_text('{"summary": "ok"}', encoding="utf-8")
            return subprocess.CompletedProcess(command, 0, "", "")

        client = CodexCLIClient("/bin/codex", model="m1")
        with patch("llm_client.subprocess.run", side_effect=fake_run) as run:
            self.assertEqual(client.generate("hi", {"type": "object"}), {"summary": "ok"})
        command = run.call_args.args[0]
        self.assertIn("read-only", command)
        self.assertEqual(command[-3:], ["--model", "m1", "-"])
        self.assertEqual(run.call_args.kwargs["input"], "hi")
        self.assertEqual(client.name, "codex-cli:m1")

    def test_codex_client_reports_failure(self):
        failed = subprocess.CompletedProcess([], 2, "", "boom")
        with patch("llm_client.subprocess.run", return_value=failed):
            with self.assertRaisesRegex(RuntimeError, "mã 2"):
                CodexCLIClient("/bin/codex").generate("hi", {})


if __name__ == "__main__":
    unittest.main()
