"""A second summary worker must not claim a video already in progress."""

import sqlite3
import tempfile
import threading
import time
from pathlib import Path
from unittest.mock import patch
import unittest

from run_priority_summaries import claim, ready_rows, process_ready


class PrioritySummaryWorkerTests(unittest.TestCase):
    def test_claim_once_and_defer_courses_owned_by_priority_service(self):
        db = sqlite3.connect(":memory:")
        db.execute("""CREATE TABLE work (
            source_id TEXT, video_id TEXT, priority INTEGER,
            capture_status TEXT, summary_status TEXT, updated_at TEXT, category TEXT DEFAULT 'IT')""")
        db.executemany("INSERT INTO work VALUES (?, ?, ?, 'captured', 'queued', '', 'IT')", [
            ("source", "priority-video", 0), ("source", "other-video", 1),
        ])
        self.assertEqual(ready_rows(db, include_priority=False), [("source", "other-video")])
        self.assertTrue(claim(db, "source", "other-video"))
        self.assertFalse(claim(db, "source", "other-video"))
        self.assertEqual(ready_rows(db, include_priority=True), [("source", "priority-video")])
        db.close()

    def test_ready_rows_interleaves_categories_before_it_backlog(self):
        db = sqlite3.connect(':memory:')
        db.execute("CREATE TABLE work (source_id TEXT, video_id TEXT, priority INTEGER, "
                   "capture_status TEXT, summary_status TEXT, updated_at TEXT, category TEXT)")
        videos = [('s', f'it-{i:02}', 1, 'captured', 'queued', 'old', 'IT') for i in range(60)]
        videos += [('s', 'business', 1, 'captured', 'queued', 'new', 'Business'),
                   ('s', 'investment', 1, 'captured', 'queued', 'new', 'Investment')]
        db.executemany('INSERT INTO work VALUES (?, ?, ?, ?, ?, ?, ?)', videos)
        rows = ready_rows(db, include_priority=True)
        self.assertEqual(len(rows), 50)
        self.assertEqual(set(rows[:3]), {('s', 'business'), ('s', 'investment'), ('s', 'it-00')})
        db.close()

    def test_bounded_parallel_work_and_max_new(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "queue.sqlite"
            db = sqlite3.connect(path)
            db.execute("CREATE TABLE work (source_id TEXT, video_id TEXT, priority INTEGER, "
                       "capture_status TEXT, summary_status TEXT, updated_at TEXT, error TEXT, category TEXT DEFAULT 'IT')")
            db.executemany("INSERT INTO work VALUES ('s', ?, 1, 'captured', 'queued', '', '', 'IT')",
                           [(str(i),) for i in range(5)])
            db.execute("UPDATE work SET category='Business' WHERE video_id='0'")
            db.execute("UPDATE work SET category='Investment' WHERE video_id='1'")
            db.commit()
            guard = threading.Lock()
            active = peak = 0
            calls = []
            def task(source, video):
                nonlocal active, peak
                with guard:
                    active += 1
                    peak = max(peak, active)
                    calls.append(video['id'])
                time.sleep(0.03)
                connection = sqlite3.connect(path)
                with connection:
                    connection.execute("UPDATE work SET summary_status='done' WHERE video_id=?",
                                       (video['id'],))
                connection.close()
                with guard:
                    active -= 1
                return 'created'
            videos = {('s', str(i)): {'id': str(i)} for i in range(5)}
            with patch('run_priority_summaries.priority_course_busy', return_value=False):
                self.assertEqual(process_ready(db, videos, workers=2, max_new=3,
                                               once=True, task=task), 3)
            self.assertEqual(peak, 2)
            self.assertEqual(len(calls), 3)
            self.assertEqual(set(calls), {'0', '1', '2'})
            self.assertEqual(db.execute("SELECT count(*) FROM work WHERE summary_status='running'").fetchone()[0], 0)
            db.close()

    def test_quota_stops_submissions_but_drains_active_video(self):
        db = sqlite3.connect(':memory:')
        db.execute("CREATE TABLE work (source_id TEXT, video_id TEXT, priority INTEGER, "
                   "capture_status TEXT, summary_status TEXT, updated_at TEXT, error TEXT, category TEXT DEFAULT 'IT')")
        db.executemany("INSERT INTO work VALUES ('s', ?, 1, 'captured', 'queued', '', '', 'IT')",
                       [('0',), ('1',), ('2',)])
        db.commit()
        calls = []
        drained = threading.Event()
        def task(source, video):
            calls.append(video['id'])
            if video['id'] == '0':
                raise RuntimeError("You've hit your usage limit")
            time.sleep(0.05)
            drained.set()
            return 'created'
        def mark_result(connection, source, video_id, **fields):
            with connection:
                connection.execute('UPDATE work SET summary_status=?, error=? WHERE video_id=?',
                                   (fields['summary'], fields['error'], video_id))
        with patch('run_priority_summaries.priority_course_busy', return_value=False), \
             patch('run_priority_summaries.mark', side_effect=mark_result):
            self.assertEqual(process_ready(db, {('s', str(i)): {'id': str(i)} for i in range(3)},
                                           workers=2, once=True, task=task), 1)
        self.assertTrue(drained.is_set())
        self.assertEqual(set(calls), {'0', '1'})
        self.assertEqual(db.execute("SELECT summary_status FROM work WHERE video_id='0'").fetchone()[0], 'queued')
        self.assertEqual(db.execute("SELECT summary_status FROM work WHERE video_id='2'").fetchone()[0], 'queued')
        db.close()


if __name__ == "__main__":
    unittest.main()
