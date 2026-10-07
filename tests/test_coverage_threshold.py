import unittest

from chunking import Chunk
from lesson_pack import verify_pack


class CoverageThresholdTests(unittest.TestCase):
    def test_five_of_six_caption_chunks_requires_revision(self):
        chunks = [Chunk(chunk_id=f"c:c{i:03d}", source_id="c", kind="caption",
                        text=f"Nội dung bài học phần thứ {i} rõ ràng.", start=f"0{i}:00", end=f"0{i}:30")
                  for i in range(1, 7)]
        pack = {"summary": "Tóm tắt bài học", "concepts": [
            {"name": f"Phần {i}", "source_refs": [{"chunk_id": chunk.chunk_id,
               "quote": f"Nội dung bài học phần thứ {i} rõ ràng"}]} for i, chunk in enumerate(chunks[:5], 1)],
            "timeline": [{"chunk_id": chunk.chunk_id} for chunk in chunks]}
        errors, coverage = verify_pack(pack, chunks)
        self.assertAlmostEqual(coverage, 5 / 6)
        self.assertTrue(any("coverage" in error for error in errors))


if __name__ == "__main__":
    unittest.main()
