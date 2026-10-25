import asyncio
import socket
import unittest

from aiohttp import web

from app.preflight import ObjectInfoUnreachable, missing_choices

INFO = {
    "ModelLoader": {"ModelLoader": {"input": {"required": {"name": [["a.safetensors", "b.safetensors"]]}}}},
    "Sampler": {"Sampler": {"input": {"required": {"mode": ["COMBO", {"options": ["fast", "slow"]}]}}}},
}


async def _handle(request):
    class_type = request.match_info["class_type"]
    if class_type == "Broken":
        return web.Response(status=503)
    if class_type not in INFO:
        return web.Response(status=404)
    return web.json_response(INFO[class_type])


def _graph(**nodes):
    return {str(i): {"class_type": c, "inputs": inputs} for i, (c, inputs) in enumerate(nodes.items())}


class MissingChoicesFetchTests(unittest.TestCase):
    def run_with_server(self, coro_fn):
        async def main():
            app = web.Application()
            app.router.add_get("/object_info/{class_type}", _handle)
            runner = web.AppRunner(app)
            await runner.setup()
            site = web.TCPSite(runner, "127.0.0.1", 0)
            await site.start()
            port = site._server.sockets[0].getsockname()[1]
            try:
                return await coro_fn(f"http://127.0.0.1:{port}")
            finally:
                await runner.cleanup()
        return asyncio.run(main())

    def test_union_over_graphs_sorted_and_unique(self):
        g1 = _graph(ModelLoader={"name": "z.safetensors"}, Sampler={"mode": "turbo"})
        g2 = _graph(ModelLoader={"name": "z.safetensors"}, Sampler={"mode": "fast"})
        g3 = _graph(Sampler={"mode": "medium"})
        result = self.run_with_server(lambda url: missing_choices(url, [g1, g2, g3]))
        self.assertEqual(result, [
            ("mode", "medium", "Sampler"),
            ("mode", "turbo", "Sampler"),
            ("name", "z.safetensors", "ModelLoader"),
        ])

    def test_404_class_left_out_without_raising(self):
        g = _graph(Unknown={"name": "x"}, ModelLoader={"name": "q.safetensors"})
        result = self.run_with_server(lambda url: missing_choices(url, [g]))
        self.assertEqual(result, [("name", "q.safetensors", "ModelLoader")])

    def test_503_raises_unreachable(self):
        g = _graph(Broken={"name": "x"})
        with self.assertRaises(ObjectInfoUnreachable):
            self.run_with_server(lambda url: missing_choices(url, [g]))

    def test_refused_connection_raises_unreachable(self):
        with socket.socket() as s:
            s.bind(("127.0.0.1", 0))
            port = s.getsockname()[1]
        g = _graph(ModelLoader={"name": "x"})
        with self.assertRaises(ObjectInfoUnreachable):
            asyncio.run(missing_choices(f"http://127.0.0.1:{port}", [g]))


if __name__ == "__main__":
    unittest.main()
