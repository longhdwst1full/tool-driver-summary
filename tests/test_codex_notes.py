from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from codex_notes import NOTE_PROMPT, check_note, find_codex, generate, read_cues, render_note


class CodexNotesTests(unittest.TestCase):
    def test_finds_vscode_cli_when_path_is_missing(self):
        with TemporaryDirectory() as folder:
            home = Path(folder)
            binary = home / ".vscode/extensions/openai.chatgpt-test/bin/linux-x86_64/codex"
            binary.parent.mkdir(parents=True)
            binary.write_text("#!/bin/sh\n", encoding="utf-8")
            binary.chmod(0o755)
            with patch("llm_client.shutil.which", return_value=None):
                self.assertEqual(find_codex(home=home), str(binary))

    def test_cue_bounds_are_checked_against_source(self):
        with TemporaryDirectory() as folder:
            path = Path(folder) / "caption.md"
            path.write_text("| Thời gian | Nội dung nguồn |\n| 00:00–00:05 | Bắt đầu |\n"
                            "| 00:05–00:12 | Tiếp theo |\n", encoding="utf-8")
            cues = read_cues(path)
            note = {"summary": "Bài mở đầu.", "sections": [{
                "title": "Giới thiệu", "description": "Bắt đầu rồi tiếp theo.",
                "start": "00:00", "end": "00:12",
            }], "caveats": []}
            check_note(note, cues)
            self.assertIn("00:00–00:12", render_note("Bài", "https://drive.google.com/video",
                                                    "caption.md", note))
            note["sections"][0]["end"] = "00:13"
            with self.assertRaisesRegex(ValueError, "không có trong nguồn"):
                check_note(note, cues)

    def test_generate_sends_versioned_prompt_through_client(self):
        class FakeClient:
            name = "fake"

            def generate(self, prompt, schema):
                self.prompt, self.schema = prompt, schema
                return {"ok": True}

        client = FakeClient()
        result = generate(client, "Bài {1}", [("00:00", "00:05", "Mở đầu {x}")])
        self.assertEqual(result, {"ok": True})
        self.assertEqual(NOTE_PROMPT.prompt_id, "lesson_note@1")
        self.assertIn("Tên bài: Bài {1}", client.prompt)
        self.assertIn("00:00–00:05 | Mở đầu {x}", client.prompt)
        self.assertIn("sections", client.schema["properties"])


if __name__ == "__main__":
    unittest.main()
