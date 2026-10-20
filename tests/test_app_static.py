import tempfile
import unittest

from aiohttp.test_utils import TestClient, TestServer
from yarl import URL

from app.server import create_app


class StaticTest(unittest.IsolatedAsyncioTestCase):
    async def _client(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        app = create_app("http://127.0.0.1:1", tmp.name)
        client = TestClient(TestServer(app))
        await client.start_server()
        self.addAsyncCleanup(client.close)
        return client

    async def test_index_page(self):
        client = await self._client()
        resp = await client.get("/")
        self.assertEqual(resp.status, 200)
        self.assertTrue(resp.content_type.startswith("text/html"))
        self.assertIn("<title>Open Cinema</title>", await resp.text())

    async def test_static_index(self):
        client = await self._client()
        resp = await client.get("/static/index.html")
        self.assertEqual(resp.status, 200)
        self.assertTrue(resp.content_type.startswith("text/html"))

    async def test_traversal_is_refused(self):
        client = await self._client()
        for path in ("/static/../server.py", "/static/%2e%2e/server.py"):
            with self.subTest(path=path):
                resp = await client.get(URL(path, encoded=True))
                self.assertIn(resp.status, (403, 404))
                self.assertNotIn("create_app", await resp.text())

    async def test_missing_static_file_is_json_404(self):
        client = await self._client()
        resp = await client.get("/static/missing.js")
        self.assertEqual(resp.status, 404)
        self.assertEqual((await resp.json())["error"]["code"], "not_found")
