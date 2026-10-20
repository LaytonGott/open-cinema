import asyncio
import unittest

from app.runner import ShotRunner


class StubRunner(ShotRunner):
    def __init__(self):
        super().__init__(store=None)
        self.calls = []

    async def run_shot(self, shot_id):
        self.calls.append(("run_shot", shot_id))

    async def run_reapply(self, shot_id, aperture):
        self.calls.append(("run_reapply", shot_id, aperture))


class QueueItemsTest(unittest.TestCase):
    def run_with(self, setup):
        runner = StubRunner()

        async def main():
            runner.start()
            setup(runner)
            await runner.queue.join()
            await runner.stop()

        asyncio.run(main())
        return runner

    def test_enqueue_without_aperture_calls_run_shot(self):
        runner = self.run_with(lambda r: r.enqueue("a"))
        self.assertEqual(runner.calls, [("run_shot", "a")])

    def test_enqueue_with_aperture_calls_run_reapply(self):
        runner = self.run_with(lambda r: r.enqueue("a", 2.8))
        self.assertEqual(runner.calls, [("run_reapply", "a", 2.8)])

    def test_cancelled_item_is_skipped(self):
        def setup(r):
            r.enqueue("a")
            r.items["a"]["cancelled"] = True
        runner = self.run_with(setup)
        self.assertEqual(runner.calls, [])
        self.assertEqual(runner.items, {})

    def test_items_removed_after_finish(self):
        def setup(r):
            r.enqueue("a")
            self.assertIn("a", r.items)
            self.assertFalse(r.items["a"]["started"])
        runner = self.run_with(setup)
        self.assertEqual(runner.items, {})


if __name__ == "__main__":
    unittest.main()
