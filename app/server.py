"""The aiohttp application for the Open Cinema director app."""

import asyncio
import logging
import mimetypes
import signal
import sys
from pathlib import Path

from aiohttp import web

from app.cli import parse_args
from app.comfy_health import check_health
from app.proxy import start_proxy, stop_proxy, use_proxy
from app.record import new_record, public_record
from app.runner import ShotRunner
from app.shot import ShotError, validate_shot
from app.store import ShotStore, new_shot_id

log = logging.getLogger("app")

mimetypes.add_type("video/webm", ".webm")
mimetypes.add_type("video/mp4", ".mp4")

STATIC_DIR = Path(__file__).parent / "static"

COMFYUI_URL = web.AppKey("comfyui_url", str)
STORE = web.AppKey("store", ShotStore)
RUNNER = web.AppKey("runner", ShotRunner)


def error_response(status, code, message, field=None):
    """Return a JSON response ``{"error": {"code", "message", "field"}}`` with HTTP ``status``."""
    return web.json_response(
        {"error": {"code": code, "message": message, "field": field}}, status=status
    )


@web.middleware
async def error_middleware(request, handler):
    """Turn HTTP errors and unexpected exceptions into JSON error responses (no tracebacks in bodies)."""
    try:
        response = await handler(request)
        # Newer aiohttp checks a FileResponse's file only when it is sent, so look first.
        if isinstance(response, web.FileResponse) and not Path(response._path).is_file():
            raise web.HTTPNotFound()
        return response
    except web.HTTPNotFound:
        return error_response(404, "not_found", f"Nothing exists at {request.path}.")
    except web.HTTPMethodNotAllowed:
        return error_response(
            405, "method_not_allowed", f"{request.method} is not allowed at {request.path}."
        )
    except web.HTTPException as exc:
        if exc.status < 400:
            raise
        return error_response(
            exc.status, "http_error", f"The request failed with status {exc.status} ({exc.reason})."
        )
    except asyncio.CancelledError:
        raise
    except Exception:
        log.exception("Unhandled error handling %s %s", request.method, request.path)
        return error_response(
            500,
            "internal",
            "Something went wrong inside Open Cinema. Check the console for details.",
        )


async def health(request):
    """Return JSON ``{"app": "ok", "comfyui": {...}}`` with status 200."""
    comfy = await check_health(request.app[COMFYUI_URL])
    return web.json_response({"app": "ok", "comfyui": comfy})


async def create_shot(request):
    """Create a shot from the JSON body and return its public record with status 201 (400 ``invalid_shot`` if invalid)."""
    try:
        data = await request.json()
    except ValueError:
        return error_response(400, "invalid_shot", "The request body must be valid JSON.")
    if not isinstance(data, dict):
        return error_response(400, "invalid_shot", "The request body must be a JSON object.")
    try:
        params = validate_shot(data)
    except ShotError as exc:
        return error_response(400, "invalid_shot", exc.message, exc.field)
    store = request.app[STORE]
    record = new_record(new_shot_id({r["id"] for r in store.list()}), params)
    store.add(record)
    request.app[RUNNER].enqueue(record["id"])
    return web.json_response(public_record(record), status=201)


async def list_shots(request):
    """Return JSON ``{"shots": [...]}`` of public records, newest first."""
    records = reversed(request.app[STORE].list())
    return web.json_response({"shots": [public_record(r) for r in records]})


async def get_shot(request):
    """Return the public record of the shot in the path, or 404 ``not_found``."""
    shot_id = request.match_info["id"]
    for record in request.app[STORE].list():
        if record["id"] == shot_id:
            return web.json_response(public_record(record))
    return error_response(404, "not_found", f"There is no shot with id {shot_id}.")


async def get_media(request):
    """Serve the file ``name`` from the folder of shot ``id`` (Range supported), or 404 ``not_found``."""
    shot_id = request.match_info["id"]
    name = request.match_info["name"]
    message = f"There is no media {name} for shot {shot_id}."
    if not name or "/" in name or "\\" in name or ".." in name:
        return error_response(404, "not_found", message)
    if request.app[STORE].get(shot_id) is None:
        return error_response(404, "not_found", message)
    path = request.app[STORE].shot_dir(shot_id) / name
    if not path.is_file():
        return error_response(404, "not_found", message)
    return web.FileResponse(path)


async def index(request):
    """Return the frontend page ``app/static/index.html``."""
    return web.FileResponse(STATIC_DIR / "index.html")


def create_app(comfyui_url, data_dir):
    """Build the aiohttp Application for ComfyUI at ``comfyui_url`` and shots in ``data_dir``.

    Returns the configured ``aiohttp.web.Application``.
    """
    app = web.Application(middlewares=[error_middleware])
    app[COMFYUI_URL] = comfyui_url
    store = ShotStore(data_dir)
    store.load_all()
    app[STORE] = store
    runner = ShotRunner(store)
    app[RUNNER] = runner

    async def start_runner(app):
        runner.start()

    async def stop_runner(app):
        await runner.stop()

    app.on_startup.append(start_runner)
    app.on_cleanup.append(stop_runner)
    app.router.add_get("/api/health", health)
    app.router.add_post("/api/shots", create_shot)
    app.router.add_get("/api/shots", list_shots)
    app.router.add_get("/api/shots/{id}", get_shot)
    app.router.add_get("/media/{id}/{name}", get_media)
    app.router.add_get("/", index)
    app.router.add_static("/static/", STATIC_DIR, show_index=False)
    return app


def _install_stop_handlers(loop, stop):
    """Make SIGINT, SIGTERM (and SIGBREAK on Windows) set the asyncio.Event ``stop``."""
    if sys.platform == "win32":
        def handler(signum, frame):
            loop.call_soon_threadsafe(stop.set)

        for name in ("SIGTERM", "SIGBREAK"):
            signal.signal(getattr(signal, name), handler)
        return
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, stop.set)


async def _serve(args):
    """Start the proxy (unless ``args.proxy_url`` is given) and the app, then serve until stopped.

    Returns 0 after SIGINT/SIGTERM/SIGBREAK (runners cleaned up), or 1 if the port cannot be bound.
    """
    proxy_runner = None
    runner = None
    stop = asyncio.Event()
    _install_stop_handlers(asyncio.get_running_loop(), stop)
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
        await stop.wait()
        return 0
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
