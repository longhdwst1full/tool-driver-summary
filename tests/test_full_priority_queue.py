"""Concurrency and checkpoint behavior of the full transcript queue."""

from pathlib import Path
import json
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

import full_priority_queue as queue


class CaptureQueueTests(unittest.TestCase):
    def test_fair_order_rotates_categories_sources_and_courses(self):
        with tempfile.TemporaryDirectory() as directory:
            reports = Path(directory)
            for source in (queue.SOURCE_A, queue.SOURCE_B):
                items = []
                for group in queue.GROUPS:
                    for course in ("Alpha", "Beta"):
                        for lesson in range(2):
                            items.append({"id": f"{source}-{group}-{course}-{lesson}",
                                          "kind": "video", "path": f"root/{group}/section/{course}/{lesson}"})
                target = reports / "new-sources" / source
                target.mkdir(parents=True)
                (target / "scan.json").write_text(json.dumps({"items": items}))
            with patch.object(queue, "REPORTS", reports), patch.object(queue, "TARGETS", []):
                _, videos = queue.source_videos()
            self.assertEqual(len(videos), 24)
            self.assertEqual([v[2] for v in videos[:6]], list(queue.GROUPS) * 2)
            self.assertEqual([v[0] for v in videos[:6]], [queue.SOURCE_A] * 3 + [queue.SOURCE_B] * 3)
            self.assertTrue(all("/Alpha/" in v[1]["path"] for v in videos[:6]))
            self.assertTrue(all("/Beta/" in v[1]["path"] for v in videos[6:12]))

    def test_suno_is_excluded_without_browser_or_summary(self):
        videos = [("source", {"id": "suno-video", "path": "root/IT/Khóa SUNO AI/video"}, "IT", 1)]
        with tempfile.TemporaryDirectory() as directory:
            with patch.object(queue, "DB", Path(directory) / "queue.sqlite"):
                db = queue.connect()
                queue.initialize(db, videos)
                with patch.object(queue, "load_capture") as browser:
                    queue.capture_all(db, videos, None, False)
                    queue.capture_all(db, videos, None, True)
                    browser.assert_not_called()
                self.assertEqual(queue.status(db)["capture"], {"excluded": 1})
                self.assertEqual(queue.status(db)["summary"], {"excluded": 1})
                db.close()

    def test_bounded_parallel_capture_and_resume(self):
        videos = [("source", {"id": f"video-{index:012d}", "name": str(index)}, "IT", 1)
                  for index in range(8)]
        with tempfile.TemporaryDirectory() as directory:
            with patch.object(queue, "DB", Path(directory) / "queue.sqlite"):
                db = queue.connect()
                queue.initialize(db, videos)
                state = {"active": 0, "peak": 0, "calls": 0}
                lock = threading.Lock()

                def fake_capture(video_id, profile_source, profile_name):
                    with lock:
                        state["active"] += 1
                        state["peak"] = max(state["peak"], state["active"])
                        state["calls"] += 1
                    time.sleep(0.02)
                    with lock:
                        state["active"] -= 1
                    return {"videoId": video_id}

                with patch.object(queue, "load_capture", return_value=fake_capture), \
                     patch.object(queue, "write_transcript", return_value=3), \
                     patch.object(queue, "readable_ui", return_value=None):
                    queue.capture_all(db, videos, limit=6, retry_unavailable=False, workers=3)
                    self.assertEqual(state["peak"], 3)
                    self.assertEqual(queue.status(db)["capture"], {"captured": 6, "queued": 2})
                    queue.capture_all(db, videos, limit=None, retry_unavailable=False, workers=2)
                    self.assertEqual(state["calls"], 8)
                    self.assertEqual(queue.status(db)["capture"], {"captured": 8})
                db.close()

    def test_reuses_one_browser_session_per_worker(self):
        videos = [("source", {"id": f"video-{index:012d}", "name": str(index)}, "IT", 1)
                  for index in range(6)]
        state = {"sessions": 0, "calls": 0, "closes": 0}
        lock = threading.Lock()

        class FakeSession:
            def __init__(self, *_):
                with lock:
                    state["sessions"] += 1

            def capture(self, video_id):
                time.sleep(0.01)
                with lock:
                    state["calls"] += 1
                return {"videoId": video_id}

            def close(self):
                with lock:
                    state["closes"] += 1

        def fake_capture(*_):
            raise AssertionError("Không được mở Chrome riêng cho từng video")

        fake_capture.session_factory = FakeSession
        with tempfile.TemporaryDirectory() as directory:
            with patch.object(queue, "DB", Path(directory) / "queue.sqlite"):
                db = queue.connect()
                queue.initialize(db, videos)
                with patch.object(queue, "load_capture", return_value=fake_capture), \
                     patch.object(queue, "write_transcript", return_value=3), \
                     patch.object(queue, "readable_ui", return_value=None):
                    queue.capture_all(db, videos, limit=None, retry_unavailable=False, workers=2)
                self.assertEqual(state["calls"], 6)
                self.assertEqual(state["sessions"], 2)
                self.assertEqual(state["closes"], 2)
                db.close()

    def test_video_level_failure_keeps_browser_session(self):
        videos = [("source", {"id": f"video-{index:012d}", "name": str(index)}, "IT", 1)
                  for index in range(2)]
        state = {"sessions": 0, "calls": 0, "closes": 0}

        class FakeSession:
            def __init__(self, *_):
                state["sessions"] += 1

            def capture(self, video_id):
                state["calls"] += 1
                if state["calls"] == 1:
                    raise TimeoutError("Bản chép lời không khả dụng trong phiên Chrome này")
                return {"videoId": video_id}

            def close(self):
                state["closes"] += 1

        def fake_capture(*_):
            raise AssertionError("Không được mở Chrome riêng cho từng video")

        fake_capture.session_factory = FakeSession
        with tempfile.TemporaryDirectory() as directory:
            with patch.object(queue, "DB", Path(directory) / "queue.sqlite"):
                db = queue.connect()
                queue.initialize(db, videos)
                with patch.object(queue, "load_capture", return_value=fake_capture), \
                     patch.object(queue, "write_transcript", return_value=3), \
                     patch.object(queue, "readable_ui", return_value=None):
                    queue.capture_all(db, videos, limit=None, retry_unavailable=False, workers=1)
                self.assertEqual(state, {"sessions": 1, "calls": 2, "closes": 1})
                self.assertEqual(queue.status(db)["capture"],
                                 {"captured": 1, "panel_unavailable": 1})
                db.close()

    def test_page_open_failure_restarts_browser_session(self):
        videos = [("source", {"id": f"video-{index:012d}", "name": str(index)}, "IT", 1)
                  for index in range(2)]
        state = {"sessions": 0, "calls": 0, "closes": 0}

        class PageOpenError(TimeoutError):
            pass

        class FakeSession:
            def __init__(self, *_):
                state["sessions"] += 1

            def capture(self, video_id):
                state["calls"] += 1
                if state["calls"] == 1:
                    raise PageOpenError("Video không mở được")
                return {"videoId": video_id}

            def close(self):
                state["closes"] += 1

        def fake_capture(*_):
            raise AssertionError("Không được gọi capture một lần")

        fake_capture.session_factory = FakeSession
        fake_capture.reset_session_errors = (PageOpenError,)
        with tempfile.TemporaryDirectory() as directory:
            with patch.object(queue, "DB", Path(directory) / "queue.sqlite"):
                db = queue.connect()
                queue.initialize(db, videos)
                with patch.object(queue, "load_capture", return_value=fake_capture), \
                     patch.object(queue, "write_transcript", return_value=3), \
                     patch.object(queue, "readable_ui", return_value=None):
                    queue.capture_all(db, videos, limit=None, retry_unavailable=False, workers=1)
                self.assertEqual(state["sessions"], 2)
                self.assertEqual(state["calls"], 3)
                self.assertGreaterEqual(state["closes"], 2)
                self.assertEqual(queue.status(db)["capture"], {"captured": 2})
                db.close()

    def test_access_denied_is_recorded_and_not_retried(self):
        video = ("source", {"id": "video-000000000000", "name": "private"}, "IT", 1)

        class AccessDeniedError(ValueError):
            pass

        class FakeSession:
            def __init__(self, *_):
                pass

            def capture(self, _video_id):
                raise AccessDeniedError("Tài khoản không có quyền xem video Drive")

            def close(self):
                pass

        def fake_capture(*_):
            raise AssertionError("Không được gọi capture một lần")

        fake_capture.session_factory = FakeSession
        fake_capture.access_denied_errors = (AccessDeniedError,)
        with tempfile.TemporaryDirectory() as directory:
            with patch.object(queue, "DB", Path(directory) / "queue.sqlite"):
                db = queue.connect()
                queue.initialize(db, [video])
                with patch.object(queue, "load_capture", return_value=fake_capture), \
                     patch.object(queue, "readable_ui", return_value=None):
                    queue.capture_all(db, [video], limit=None,
                                      retry_unavailable=False, workers=1)
                    queue.capture_all(db, [video], limit=None,
                                      retry_unavailable=True, workers=1)
                self.assertEqual(queue.status(db)["capture"], {"access_denied": 1})
                self.assertEqual(db.execute("SELECT attempts FROM work").fetchone()[0], 1)
                db.close()


if __name__ == "__main__":
    unittest.main()
