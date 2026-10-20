"""The aiohttp application for the Open Cinema director app."""

from pathlib import Path

from aiohttp import web

from app.comfy_health import check_health
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
