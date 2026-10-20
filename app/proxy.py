"""In-process ComfyUI proxy for the director app."""

import os

from aiohttp import web
from comfy_api_proxy.app import make_app


async def start_proxy(comfyui_url, port=0):
    """Start the Comfy API proxy for ``comfyui_url`` inside this process.

    Listens on 127.0.0.1 at ``port`` (0 picks a free port). Returns
    ``(runner, url)``: the ``aiohttp.web.AppRunner`` and the base URL
    ``http://127.0.0.1:<actual port>`` read from the bound socket.
    """
    runner = web.AppRunner(make_app(comfyui_url))
    await runner.setup()
    try:
        site = web.TCPSite(runner, "127.0.0.1", port)
        await site.start()
        actual = site._server.sockets[0].getsockname()[1]
    except BaseException:
        await runner.cleanup()
        raise
    return runner, f"http://127.0.0.1:{actual}"


async def stop_proxy(runner):
    """Stop the proxy started by ``start_proxy`` and free its port. Returns None."""
    await runner.cleanup()


def use_proxy(url):
    """Point the Comfy SDK at the proxy by setting ``COMFY_BASE_URL`` to ``url``."""
    os.environ["COMFY_BASE_URL"] = url
