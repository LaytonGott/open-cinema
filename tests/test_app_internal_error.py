import tempfile
import unittest
from unittest import mock

from aiohttp.test_utils import TestClient, TestServer

from app.server import create_app
from app.store import ShotStore


class InternalErrorTest(unittest.IsolatedAsyncioTestCase):
    async def _client(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        client = TestClient(TestServer(create_app("http://127.0.0.1:1", tmp.name)))
        await client.start_server()
        self.addAsyncCleanup(client.close)
        return client

    def _assert_shape(self, body, code):
        self.assertEqual(set(body), {"error"})
        error = body["error"]
        self.assertEqual(set(error), {"code", "message", "field"})
        self.assertEqual(error["code"], code)
        self.assertIsInstance(error["message"], str)
        self.assertTrue(error["message"].strip())
        self.assertIsNone(error["field"])

    async def test_forced_500_is_json_internal_without_traceback(self):
        client = await self._client()
        with mock.patch.object(ShotStore, "list", side_effect=RuntimeError("secret boom detail")):
            with self.assertLogs("app", level="ERROR") as logs:
                resp = await client.get("/api/shots")
                text = await resp.text()
        self.assertEqual(resp.status, 500)
        self._assert_shape(await resp.json(), "internal")
        for word in ("Traceback", "RuntimeError", "secret boom detail"):
            self.assertNotIn(word, text)
        output = "\n".join(logs.output)
        self.assertIn("Traceback", output)
        self.assertIn("secret boom detail", output)

    async def test_unknown_path_has_same_shape(self):
        client = await self._client()
        resp = await client.get("/api/nope")
        self.assertEqual(resp.status, 404)
        self._assert_shape(await resp.json(), "not_found")

    async def test_wrong_method_has_same_shape(self):
        client = await self._client()
        resp = await client.post("/api/health")
        self.assertEqual(resp.status, 405)
        self._assert_shape(await resp.json(), "method_not_allowed")
