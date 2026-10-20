"""The aiohttp application for the Open Cinema director app."""

import asyncio
import sys
from pathlib import Path

from aiohttp import web

from app.cli import parse_args
from app.comfy_health import check_health
from app.proxy import start_proxy, stop_proxy, use_proxy
from app.store import ShotStore

STATIC_DIR = Path(__file__).parent / "static"

COMFYUI_URL = web.AppKey("comfyui_url", str)
STORE = web.AppKey("store", ShotStore)


async def health(request):
    """Return JSON ``{"app": "ok", "comfyui": {...}}`` with status 200."""
    comfy = await check_health(request.app[COMFYUI_URL])
    return web.json_response({"app": "ok", "comfyui": comfy})


async def index(request):
    """Return the frontend page ``app/static/index.html``."""
    return web.FileResponse(STATIC_DIR / "index.html")


def create_app(comfyui_url, data_dir):
    """Build the aiohttp Application for ComfyUI at ``comfyui_url`` and shots in ``data_dir``.

    Returns the configured ``aiohttp.web.Application``.
    """
    app = web.Application()
    app[COMFYUI_URL] = comfyui_url
    store = ShotStore(data_dir)
    store.load_all()
    app[STORE] = store
    app.router.add_get("/api/health", health)
    app.router.add_get("/", index)
    app.router.add_static("/static/", STATIC_DIR, show_index=False)
    return app


async def _serve(args):
    """Start the proxy (unless ``args.proxy_url`` is given) and the app, then serve until cancelled.

    Returns 1 if the port cannot be bound (after cleaning up); otherwise only returns by raising.
    """
    proxy_runner = None
    runner = None
    try:
        if args.proxy_url:
            use_proxy(args.proxy_url)
        else:
            proxy_runner, proxy_url = await start_proxy(args.comfyui, args.proxy_port)
            use_proxy(proxy_url)
        runner = web.AppRunner(create_app(args.comfyui, args.data_dir))
        await runner.setup()
        try:
            await web.TCPSite(runner, args.host, args.port).start()
        except OSError as exc:
            reason = exc.strerror or str(exc)
            print(
                f"Open Cinema could not start: port {args.port} on {args.host} is not available ({reason}).",
                file=sys.stderr,
                flush=True,
            )
            return 1
        print(
            f"Open Cinema is running at http://{args.host}:{args.port} (ComfyUI at {args.comfyui})",
            flush=True,
        )
        await asyncio.Event().wait()
    finally:
        if runner is not None:
            await runner.cleanup()
        if proxy_runner is not None:
            await stop_proxy(proxy_runner)


def main(argv=None) -> int:
    """Run the director app until stopped. ``argv`` is a list of options (sys.argv when None).

    Returns the process exit code: 0 after a KeyboardInterrupt, 1 if the port is not available.
    """
    args = parse_args(argv)
    try:
        return asyncio.run(_serve(args))
    except KeyboardInterrupt:
        return 0
