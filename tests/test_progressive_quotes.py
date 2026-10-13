import unittest

from progressive_demo import (FINAL_PROMPT, build_progressive, exact_points,
                              render_markdown, validate_final, validate_points)


class ProgressiveQuoteTests(unittest.TestCase):
    def test_short_outro_is_merged_before_cited_summary(self):
        class Client:
            extracts = 0

            def generate(self, prompt, schema):
                if "points" in schema["properties"]:
                    self.extracts += 1
                    return {"points": [{"kind": "concept", "text": "Giải thích tác vụ tự động hóa",
                                        "quote": "Đây là phần giải thích về tác vụ tự động hóa"}]}
                return {"summary": "Bài giải thích tác vụ tự động hóa.",
                        "summary_point_ids": ["video123456:c001:p01"],
                        "sections": [{"title": "Nội dung", "body": "Tác vụ tự động hóa.",
                                      "point_ids": ["video123456:c001:p01"]}],
                        "questions": ["Tác vụ tự động hóa là gì?"]}

        client = Client()
        cues = [("00:00", "06:01", "Đây là phần giải thích về tác vụ tự động hóa. " + "Nội dung bài học. " * 30),
                ("06:02", "06:05", "Cảm ơn các bạn đã xem video và hẹn gặp lại ở bài học tiếp theo.")]
        result = build_progressive(client, "Bài thử", "video123456", cues)
        self.assertEqual(client.extracts, 1)
        self.assertEqual(result["qa"]["total_chunks"], 1)
        self.assertEqual(result["points"][0]["end"], "06:05")

    def test_restore_only_source_whitespace(self):
        source = "Dữ liệu bán hàng\nđược phân tích theo từng tháng."
        points = [{"kind": "concept", "text": "Phân tích theo tháng",
                   "quote": "Dữ liệu bán hàng được phân tích theo từng tháng."},
                  {"kind": "concept", "text": "Ý không có bằng chứng",
                   "quote": "Một nội dung hoàn toàn không hề có trong phụ đề."}]
        accepted = exact_points(points, source)
        self.assertEqual(len(accepted), 1)
        self.assertIn("\n", accepted[0]["quote"])
        validate_points(accepted, source)

    def test_summary_references_cover_distinct_chunks(self):
        points = [{"point_id": f"chunk-{i}:p01", "chunk_id": f"chunk-{i}",
                   "start": f"0{i}:00", "end": f"0{i}:30", "text": f"Ý {i}",
                   "quote": f"Trích dẫn phần {i}"} for i in range(3)]
        note = {"summary": "Ba phần chính của bài học.",
                "summary_point_ids": [point["point_id"] for point in points],
                "sections": [{"title": "Nội dung", "body": "Ba phần theo trình tự.",
                              "point_ids": [point["point_id"] for point in points]}],
                "questions": ["Bài học gồm những gì?"]}
        validate_final(note, points)
        result = {"title": "Bài thử", "note": note, "points": points}
        markdown = render_markdown(result, "https://drive.google.com/video",
                                   "caption.md")
        self.assertIn("Nguồn tóm tắt: [00:00–00:30] · [01:00–01:30] · [02:00–02:30]", markdown)
        self.assertNotIn("chunk-0", markdown)
        self.assertIn("Trích dẫn phần 0", markdown)
        self.assertEqual(FINAL_PROMPT.prompt_id, "progressive_finalize@3")
        note["summary_point_ids"] = [points[0]["point_id"]]
        with self.assertRaisesRegex(ValueError, "chưa đại diện đủ"):
            validate_final(note, points)
        note["summary_point_ids"] = ["không-tồn-tại"]
        with self.assertRaisesRegex(ValueError, "thiếu point_id"):
            validate_final(note, points)

    def test_long_summary_represents_each_quarter(self):
        points = [{"point_id": f"c{i}:p01", "chunk_id": f"c{i}"} for i in range(8)]
        note = {"summary": "Tổng quan bài học", "summary_point_ids": ["c0:p01", "c2:p01", "c6:p01"],
                "sections": [{"title": "Nội dung", "body": "Theo bài học",
                              "point_ids": [point["point_id"] for point in points]}]}
        with self.assertRaisesRegex(ValueError, "một phần tư"):
            validate_final(note, points)
        note["summary_point_ids"].append("c4:p01")
        validate_final(note, points)


if __name__ == "__main__":
    unittest.main()
