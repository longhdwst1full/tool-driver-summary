import unittest

from getsub_demo import NO_EVIDENCE, answer, citation, parse_captions


SAMPLE = """1
00:00:00,000 --> 00:00:35,000
Agent loop gồm ba bước: quan sát thông tin, suy luận việc cần làm, rồi thực hiện hành động.

2
00:00:35,000 --> 00:01:10,000
Khi được hỏi thời tiết, agent gọi công cụ thời tiết trước khi trả lời.

3
00:01:10,000 --> 00:01:40,000
Nếu công cụ lỗi, agent cần báo không lấy được dữ liệu thay vì đoán thời tiết.
"""


class DemoTests(unittest.TestCase):
    def test_source_backed_answer_keeps_timestamp(self):
        result = answer("Khi công cụ thời tiết lỗi, agent nên làm gì?", parse_captions(SAMPLE))
        self.assertIn("01:10–01:40", result)
        self.assertIn("báo không lấy được dữ liệu", result)

    def test_out_of_source_question_abstains(self):
        self.assertEqual(answer("Bài giảng dùng API thời tiết nào?", parse_captions(SAMPLE)), NO_EVIDENCE)

    def test_vtt_and_srt_timing(self):
        vtt = "WEBVTT\n\n00:00:01.000 --> 00:00:02.500\nXin chào"
        self.assertEqual(citation(parse_captions(vtt)[0]), "00:01–00:02")

    def test_malformed_caption_fails(self):
        with self.assertRaisesRegex(ValueError, "Mốc kết thúc"):
            parse_captions("1\n00:00:05,000 --> 00:00:02,000\nSai thứ tự")


if __name__ == "__main__":
    unittest.main()
