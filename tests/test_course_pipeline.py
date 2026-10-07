import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from zipfile import ZipFile
from io import BytesIO

from course_synthesis import collect_lessons, synthesize_course
from drive_documents import PPTX_MIME, extract_text
from knowledge_search import answer, build_index, search
from notebook_export import export_course


class CoursePipelineTests(unittest.TestCase):
    def test_pptx_extracts_slides_in_numeric_order(self):
        buffer = BytesIO()
        with ZipFile(buffer, "w") as archive:
            for number, text in ((10, "Mười"), (2, "Hai"), (1, "Một")):
                archive.writestr(f"ppt/slides/slide{number}.xml",
                                 '<p:sld xmlns:p="p" xmlns:a="a"><a:t>' + text + '</a:t></p:sld>')
        result = extract_text(buffer.getvalue(), PPTX_MIME)
        self.assertLess(result.index("[Slide 1]"), result.index("[Slide 2]"))
        self.assertIn("Một", result)
        self.assertIn("Mười", result)

    def test_course_outputs_and_cited_search(self):
        with TemporaryDirectory() as folder:
            root = Path(folder)
            packs = root / "packs"
            path = packs / "Khóa A" / "Chương 1" / "Bài 1.json"
            path.parent.mkdir(parents=True)
            data = {"qa": {"status": "ok"},
                    "meta": {"video_id": "video_1", "caption_id": "caption_1"},
                    "pack": {"summary": "Bài nói về lập trình AI.", "objectives": ["Hiểu AI"],
                             "concepts": [{"name": "AI", "definition": "AI giúp xử lý thông tin.",
                                           "source_refs": [{"chunk_id": "caption_1:c001", "quote": "AI giúp xử lý thông tin", "at": "00:01"}]}],
                             "sections": [{"heading": "Giới thiệu", "body": "AI giúp xử lý thông tin.",
                                           "source_refs": [{"chunk_id": "caption_1:c001", "quote": "AI giúp xử lý thông tin", "at": "00:01"}]}],
                             "quiz": [{"question": "AI làm gì?", "source_refs": [{"chunk_id": "caption_1:c001",
                                       "quote": "AI giúp xử lý thông tin", "at": "00:01"}]}]},
                    "chunks": [{"chunk_id": "caption_1:c001", "source_id": "caption_1", "kind": "caption",
                                "text": "AI giúp xử lý thông tin", "start": "00:00", "end": "00:10"}]}
            path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
            path.with_suffix(".md").write_text("# Bài 1\n", encoding="utf-8")
            lessons = collect_lessons(packs)["Khóa A"]
            result = synthesize_course("Khóa A", lessons, root / "courses")
            self.assertEqual(result["concepts"], 1)
            graph = json.loads((root / "courses/Khóa A/concept_graph.json").read_text())
            self.assertEqual(graph["nodes"][0]["sources"][0]["chunk_id"], "caption_1:c001")
            exported = export_course("Khóa A", lessons, root / "courses", root / "export")
            self.assertEqual(exported["sources"], 4)
            db = root / "search.sqlite"
            self.assertEqual(build_index(packs, db)["chunks"], 1)
            hits = search(db, "xử lý thông tin")
            self.assertEqual(hits[0]["chunk_id"], "caption_1:c001")

    def test_answer_rejects_invented_citation(self):
        class Client:
            def generate(self, prompt, schema):
                return {"answer": "Sai", "citations": ["fake:c001"], "insufficient_evidence": False}

        with self.assertRaises(ValueError):
            answer(Client(), "AI là gì?", [{"chunk_id": "real:c001", "lesson": "Bài 1",
                                           "at": "00:01", "text": "AI là công cụ"}])


if __name__ == "__main__":
    unittest.main()
