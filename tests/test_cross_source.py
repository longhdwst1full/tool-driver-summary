import unittest

from cross_source import verify


class CrossSourceTests(unittest.TestCase):
    def test_two_sided_quotes_must_match_correct_kinds(self):
        chunks = [{"chunk_id": "caption:c001", "kind": "caption", "text": "Video dạy cách viết prompt rõ ràng"},
                  {"chunk_id": "document:d001", "kind": "document", "text": "Tài liệu thêm một ví dụ cụ thể"}]
        valid = {"matches": [{"type": "complement", "explanation": "Tài liệu thêm ví dụ",
                              "caption_ref": {"chunk_id": "caption:c001", "quote": "viết prompt rõ ràng"},
                              "document_ref": {"chunk_id": "document:d001", "quote": "thêm một ví dụ cụ thể"}}]}
        self.assertEqual(verify(valid, chunks), [])
        invalid = {"matches": [{**valid["matches"][0],
                                "document_ref": {"chunk_id": "caption:c001", "quote": "viết prompt rõ ràng"}}]}
        self.assertTrue(verify(invalid, chunks))


if __name__ == "__main__":
    unittest.main()
