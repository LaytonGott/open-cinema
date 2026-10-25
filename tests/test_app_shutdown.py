import argparse
import asyncio
import tempfile
import threading
import time
import unittest
from unittest import mock

from aiohttp import web

from app import server
from app.runner import ShotRunner
from app.store import ShotStore


class ShutdownTest(unittest.IsolatedAsyncioTestCase):
    async def test_stop_does_not_wait_for_blocked_sdk_thread(self):
        with tempfile.TemporaryDirectory() as tmp:
            runner = ShotRunner(ShotStore(tmp))
            entered = threading.Event()

            def blocked():
                entered.set()
                time.sleep(30)

            async def run_shot(shot_id):
                await runner._call(blocked)

            runner.run_shot = run_shot
            runner.start()
            runner.enqueue("s1")
            deadline = time.monotonic() + 5
            while not entered.is_set() and time.monotonic() < deadline:
                await asyncio.sleep(0.01)
            self.assertTrue(entered.is_set())
            started = time.monotonic()
            await runner.stop()
            self.assertLess(time.monotonic() - started, 2)

    async def test_serve_finishes_when_cleanup_hangs(self):
        stops = []

        def install(loop, stop):
            stops.append(stop)

        async def hang(self):
            await asyncio.sleep(30)

        with tempfile.TemporaryDirectory() as tmp:
            args = argparse.Namespace(
                proxy_url="http://127.0.0.1:1",
                proxy_port=0,
                comfyui="http://127.0.0.1:1",
                data_dir=tmp,
                host="127.0.0.1",
                port=0,
            )
            with mock.patch.object(server, "_install_stop_handlers", install), mock.patch.object(
                web.AppRunner, "cleanup", hang
            ):
                task = asyncio.ensure_future(server._serve(args))
                deadline = time.monotonic() + 5
                while time.monotonic() < deadline and not stops:
                    await asyncio.sleep(0.01)
                await asyncio.sleep(0.5)
                started = time.monotonic()
                stops[0].set()
                self.assertEqual(await asyncio.wait_for(task, 8), 0)
                self.assertLess(time.monotonic() - started, 8)


class MainInterruptTest(unittest.TestCase):
    def test_main_returns_zero_on_keyboard_interrupt(self):
        def interrupt(coro):
            coro.close()
            raise KeyboardInterrupt

        with mock.patch.object(asyncio, "run", interrupt):
            self.assertEqual(server.main([]), 0)


if __name__ == "__main__":
    unittest.main()
