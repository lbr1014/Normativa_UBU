import time
import unittest
from concurrent.futures import ThreadPoolExecutor

from app.async_tasks import executor

class AsyncTasksTest(unittest.TestCase):
    def test_executor(self):
        self.assertIsInstance(executor, ThreadPoolExecutor)
        
    def test_executor_max_workers(self):
        self.assertTrue(hasattr(executor, "_max_workers"))
        self.assertEqual(executor._max_workers, 1)
        
    def test_executor_runs(self):
        def work():
            return 123

        fut = executor.submit(work)
        self.assertEqual(fut.result(timeout=2), 123)
        
    def test_executor_serializes(self):
        started = []
        finished = []

        def long_task():
            started.append("long")
            time.sleep(0.3)
            finished.append("long")
            return "A"

        def short_task():
            started.append("short")
            finished.append("short")
            return "B"

        f1 = executor.submit(long_task)
        f2 = executor.submit(short_task)

        r1 = f1.result(timeout=2)
        r2 = f2.result(timeout=2)

        self.assertEqual((r1, r2), ("A", "B"))
        self.assertEqual(finished, ["long", "short"])