import unittest

from chunking import chunk_cues, chunk_document, seconds


class ChunkingTests(unittest.TestCase):
    def test_seconds_accepts_both_formats(self):
        self.assertEqual(seconds("01:05"), 65)
        self.assertEqual(seconds("01:00:05"), 3605)
        with self.assertRaises(ValueError):
            seconds("5")

    def test_cues_close_at_sentence_end_after_window(self):
        cues = [("00:00", "02:00", "Mở đầu"), ("02:00", "04:00", "Agent loop."),
                ("04:00", "05:00", "Tool calling"), ("05:00", "06:00", "Kết thúc.")]
        chunks = chunk_cues("cap1", cues, window_s=200, max_s=400)
        self.assertEqual([c.chunk_id for c in chunks], ["cap1:c001", "cap1:c002"])
        self.assertEqual((chunks[0].start, chunks[0].end), ("00:00", "04:00"))
        self.assertEqual(chunks[0].text, "Mở đầu\nAgent loop.")
        self.assertEqual((chunks[1].start, chunks[1].end), ("04:00", "06:00"))

    def test_cues_force_split_at_max_without_sentence_end(self):
        cues = [(f"00:{m:02d}:00", f"00:{m + 1:02d}:00", "không chấm câu") for m in range(10)]
        chunks = chunk_cues("cap", cues, window_s=120, max_s=180)
        self.assertTrue(all(seconds(c.end) - seconds(c.start) <= 180 for c in chunks))
        self.assertEqual(sum(c.text.count("\n") + 1 for c in chunks), 10)

    def test_chunk_ids_are_stable(self):
        cues = [("00:00", "00:10", "A."), ("00:10", "00:20", "B.")]
        self.assertEqual(chunk_cues("x", cues), chunk_cues("x", cues))

    def test_document_packs_paragraphs(self):
        text = "Đoạn một.\n\nĐoạn hai.\n\n" + "x" * 50 + "\n\n  \n\nĐoạn cuối."
        chunks = chunk_document("doc1", text, max_chars=30)
        self.assertEqual([(c.para_start, c.para_end) for c in chunks], [(1, 2), (3, 3), (4, 4)])
        self.assertEqual(chunks[0].text, "Đoạn một.\n\nĐoạn hai.")
        self.assertEqual(chunks[0].to_dict()["kind"], "document")

    def test_empty_inputs_fail(self):
        with self.assertRaises(ValueError):
            chunk_cues("c", [])
        with self.assertRaises(ValueError):
            chunk_document("d", " \n\n ")


if __name__ == "__main__":
    unittest.main()
