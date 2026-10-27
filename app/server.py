"""The aiohttp application for the Open Cinema director app."""

import asyncio
import json
import logging
import mimetypes
import re
import secrets
import signal
import sys
from pathlib import Path

from aiohttp import web

from app import graphs, preflight
from app.cli import DEFAULT_DATA_DIR, parse_args
from app.comfy_health import check_health
from app.proxy import start_proxy, stop_proxy, use_proxy
from app.record import new_record, public_record
from app.runner import ShotRunner
from app.shot import (
    APERTURES, CAMERAS, FRAMINGS, LENSES, SUBJECT_HEIGHT_FRACTION, ShotError,
    build_prompt, subject_distance, validate_shot,
)
from open_optics.framing import sensor_height_mm
from app.store import ShotStore, new_shot_id, replace_with_retry, seed_samples as seed_sample_shots

log = logging.getLogger("app")

mimetypes.add_type("video/webm", ".webm")
mimetypes.add_type("video/mp4", ".mp4")

STATIC_DIR = Path(__file__).parent / "static"
KEEPALIVE_S = 15
MAX_IMPORT_BYTES = 200 * 1024 * 1024
IMPORT_SUFFIXES = (".mp4", ".webm")
MEDIA_NAME = re.compile(r"^[A-Za-z0-9_.-]+\.(mp4|webm)$")

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


async def options(request):
    """Return JSON with the choices (cameras, lenses in mm, apertures as f-numbers, framings) and the defaults."""
    return web.json_response(
        {
            "cameras": CAMERAS,
            "lenses": LENSES,
            "apertures": APERTURES,
            "framings": FRAMINGS,
            "defaults": {
                "camera": "static",
                "lens_mm": 50,
                "aperture": 2.8,
                "framing": "full-body",
            },
        }
    )


async def estimate(request):
    """Return JSON subject_distance_m (metres), sensor_height_mm, subject_height_fraction and real_height_m (metres) for query ``lens_mm`` and ``framing`` (400 ``invalid_shot`` if invalid)."""
    lens_message = "The lens must be one of: 24, 35, 50, 85 mm."
    framing_message = f"The framing must be one of: {', '.join(SUBJECT_HEIGHT_FRACTION)}."
    raw_lens = request.query.get("lens_mm")
    try:
        lens_mm = int(raw_lens)
    except (TypeError, ValueError):
        return error_response(400, "invalid_shot", lens_message, "lens_mm")
    if lens_mm not in LENSES:
        return error_response(400, "invalid_shot", lens_message, "lens_mm")
    framing = request.query.get("framing")
    if framing not in SUBJECT_HEIGHT_FRACTION:
        return error_response(400, "invalid_shot", framing_message, "framing")
    try:
        distance = subject_distance(lens_mm, framing)
    except ValueError:
        return error_response(400, "invalid_shot", lens_message, "lens_mm")
    return web.json_response(
        {
            "subject_distance_m": round(distance, 4),
            "sensor_height_mm": sensor_height_mm(36, 1280, 704),
            "subject_height_fraction": SUBJECT_HEIGHT_FRACTION[framing],
            "real_height_m": 1.7,
        }
    )


async def preflight_refusal(url, graph_list):
    """Ask ComfyUI whether it can run ``graph_list``; return the error response to send if not, else None.

    503 ``comfy_unreachable`` if ComfyUI cannot be asked, 503 ``comfy_nodes_missing`` naming the nodes it lacks,
    503 ``comfy_models_missing`` naming the model files it does not list.
    """
    unreachable = error_response(503, "comfy_unreachable", f"Can't reach ComfyUI at {url}. Start ComfyUI, then retry.")
    try:
        missing = await preflight.missing_nodes(url, preflight.graph_class_types(*graph_list))
    except preflight.ObjectInfoUnreachable:
        return unreachable
    if missing:
        return error_response(503, "comfy_nodes_missing", preflight.nodes_missing_message(missing))
    try:
        items = await preflight.missing_choices(url, graph_list)
    except preflight.ObjectInfoUnreachable:
        return unreachable
    if items:
        return error_response(503, "comfy_models_missing", preflight.models_missing_message(items))
    return None


async def create_shot(request):
    """Create a shot from the JSON body and return its public record with status 201 (400 ``invalid_shot`` if invalid, 503 ``comfy_unreachable`` if ComfyUI is down)."""
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
    comfy = await check_health(request.app[COMFYUI_URL])
    if not comfy["reachable"]:
        return error_response(503, "comfy_unreachable", comfy["message"])
    # a node or model ComfyUI lacks is reported now, not after ten minutes of generating
    lens, aperture = params["lens_mm"], params["aperture"]
    distance = subject_distance(lens, params["framing"])
    refusal = await preflight_refusal(request.app[COMFYUI_URL], [
        graphs.build_generation_graph(build_prompt(params), params["seed"], "opencinema/check"),
        graphs.build_optics_graph("check.mp4", lens, aperture, distance, "opencinema/check"),
    ])
    if refusal is not None:
        return refusal
    store = request.app[STORE]
    record = new_record(new_shot_id({r["id"] for r in store.list()}), params)
    store.add(record)
    request.app[RUNNER].enqueue(record["id"])
    return web.json_response(public_record(record), status=201)


async def read_import(request):
    """Read the multipart body of an import into ``(fields, temp_path, filename)``.

    ``fields`` maps the text parts (``lens_mm``, ``aperture``, ``framing``, ``name``) to strings. The ``file`` part is
    streamed to a ``.import-*`` file in the shots folder (``temp_path``, a Path; ``filename`` its original name) and
    stops with 413 ``too_large`` past ``MAX_IMPORT_BYTES``. ``temp_path`` and ``filename`` are None without a file part.
    Raises ``ValueError`` if the body is not multipart.
    """
    if not request.content_type.startswith("multipart/"):
        raise ValueError("not multipart")
    reader = await request.multipart()
    fields, temp, filename = {}, None, None
    store = request.app[STORE]
    store.root.mkdir(parents=True, exist_ok=True)
    try:
        while True:
            part = await reader.next()
            if part is None:
                break
            if part.name == "file":
                filename = part.filename or ""
                temp = store.root / f".import-{secrets.token_hex(4)}.part"
                size = 0
                with open(temp, "wb") as out:
                    while True:
                        chunk = await part.read_chunk(1024 * 1024)
                        if not chunk:
                            break
                        size += len(chunk)
                        if size > MAX_IMPORT_BYTES:
                            raise web.HTTPRequestEntityTooLarge(max_size=MAX_IMPORT_BYTES, actual_size=size)
                        out.write(chunk)
            elif part.name:
                fields[part.name] = (await part.text())[:1000]
    except BaseException:
        if temp is not None:
            temp.unlink(missing_ok=True)
        raise
    return fields, temp, filename


async def import_shot(request):
    """Create a shot from an uploaded video (multipart ``file`` plus ``lens_mm``, ``aperture``, ``framing``, optional ``name``) and return its public record with status 202.

    The video becomes the shot's "before"; only the optics run, as for a re-apply. 400 ``invalid_shot`` for a bad field or
    a file that is not .mp4 or .webm, 413 ``too_large`` past 200 MB, 503 for ComfyUI problems as for ``create_shot``.
    """
    try:
        fields, temp, filename = await read_import(request)
    except ValueError:
        return error_response(400, "invalid_shot", "The request must be a form upload with a video file.", "file")
    except web.HTTPRequestEntityTooLarge:
        return error_response(413, "too_large", "The video is larger than 200 MB. Use a shorter or smaller clip.", "file")
    try:
        suffix = Path(filename or "").suffix.lower()
        if temp is None or suffix not in IMPORT_SUFFIXES:
            return error_response(400, "invalid_shot", "Choose a video file (.mp4 or .webm).", "file")
        try:
            lens_mm = int(fields.get("lens_mm", ""))
            aperture = float(fields.get("aperture", ""))
        except ValueError:
            return error_response(400, "invalid_shot", "The lens and the aperture must be numbers.", "lens_mm")
        name = fields.get("name", "").strip() or Path(filename).stem[:80] or "clip"
        try:
            params = validate_shot({
                "description": f"Imported clip: {name}", "camera": "static", "lens_mm": lens_mm,
                "aperture": aperture, "framing": fields.get("framing", ""), "seed": 0})
        except ShotError as exc:
            return error_response(400, "invalid_shot", exc.message, exc.field)
        comfy = await check_health(request.app[COMFYUI_URL])
        if not comfy["reachable"]:
            return error_response(503, "comfy_unreachable", comfy["message"])
        distance = subject_distance(params["lens_mm"], params["framing"])
        refusal = await preflight_refusal(request.app[COMFYUI_URL], [
            graphs.build_optics_graph("check.mp4", params["lens_mm"], params["aperture"], distance, "opencinema/check")])
        if refusal is not None:
            return refusal
        store = request.app[STORE]
        record = new_record(new_shot_id({r["id"] for r in store.list()}), params)
        record["imported"] = True
        shot_dir = store.shot_dir(record["id"])
        shot_dir.mkdir(parents=True, exist_ok=True)
        replace_with_retry(temp, shot_dir / f"before{suffix}")
        temp = None
        record["before_url"] = f"/media/{record['id']}/before{suffix}"
        for stage in record["stages"]:
            if stage["id"] == "generate":
                stage["state"], stage["progress"] = "done", 1.0
        record["status"], record["progress"], record["message"] = "done", 1.0, "Done"
        store.add(record)
        runner = request.app[RUNNER]
        runner.begin_reapply(record, params["aperture"])
        runner.enqueue(record["id"], params["aperture"])
        return web.json_response(public_record(record), status=202)
    finally:
        if temp is not None:
            temp.unlink(missing_ok=True)


async def reapply_shot(request):
    """Re-apply the optics of the shot in the path with the body's ``aperture`` (f-number) and return its public record with status 202 (404 ``not_found``, 400 ``invalid_shot``, 409 ``not_ready`` or ``busy``, 503 ``comfy_nodes_missing`` if ComfyUI lacks a node the optics graph needs, 503 ``comfy_models_missing`` if ComfyUI does not list a model file it uses, 503 ``comfy_unreachable`` if ComfyUI cannot be asked)."""
    shot_id = request.match_info["id"]
    record = None
    for r in request.app[STORE].list():
        if r["id"] == shot_id:
            record = r
            break
    if record is None:
        return error_response(404, "not_found", f"There is no shot with id {shot_id}.")
    try:
        data = await request.json()
    except ValueError:
        return error_response(400, "invalid_shot", "The request body must be valid JSON.")
    if not isinstance(data, dict):
        return error_response(400, "invalid_shot", "The request body must be a JSON object.")
    aperture = data.get("aperture")
    if type(aperture) not in (int, float) or aperture not in APERTURES:
        return error_response(
            400,
            "invalid_shot",
            f"The aperture must be one of: {', '.join(str(a) for a in APERTURES)}.",
            "aperture",
        )
    if not record.get("before_url"):
        return error_response(409, "not_ready", "The shot has no image yet, so its optics cannot be re-applied.")
    if record["status"] in ("queued", "generating", "optics"):
        return error_response(409, "busy", "The shot is still being processed. Try again when it is finished.")
    graph = graphs.build_optics_graph(
        "check.mp4", record["params"]["lens_mm"], aperture,
        record["derived"]["subject_distance_m"], "opencinema/check")
    url = request.app[COMFYUI_URL]
    try:
        missing = await preflight.missing_nodes(url, preflight.graph_class_types(graph))
    except preflight.ObjectInfoUnreachable:
        return error_response(503, "comfy_unreachable", f"Can't reach ComfyUI at {url}. Start ComfyUI, then retry.")
    if missing:
        return error_response(503, "comfy_nodes_missing", preflight.nodes_missing_message(missing))
    try:
        items = await preflight.missing_choices(url, [graph])
    except preflight.ObjectInfoUnreachable:
        return error_response(503, "comfy_unreachable", f"Can't reach ComfyUI at {url}. Start ComfyUI, then retry.")
    if items:
        return error_response(503, "comfy_models_missing", preflight.models_missing_message(items))
    runner = request.app[RUNNER]
    runner.begin_reapply(record, aperture)
    runner.enqueue(shot_id, aperture)
    return web.json_response(public_record(record), status=202)


async def cancel_shot(request):
    """Cancel the shot in the path, wait up to 5 s for the worker to finish the cancel and return its public record (404 ``not_found``, 409 ``not_running``)."""
    shot_id = request.match_info["id"]
    store = request.app[STORE]
    if store.get(shot_id) is None:
        return error_response(404, "not_found", f"There is no shot with id {shot_id}.")
    record = await request.app[RUNNER].cancel(shot_id)
    if record is None:
        return error_response(409, "not_running", "This shot is not running, so there is nothing to cancel.")
    for _ in range(100):
        record = store.get(shot_id)
        if record["status"] not in ("queued", "generating", "optics"):
            break
        await asyncio.sleep(0.05)
    return web.json_response(public_record(record))


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


async def delete_shot(request):
    """Delete the shot in the path with its whole folder and return 204.

    Status codes: 204 deleted, 404 ``not_found`` (unknown id), 409 ``busy`` (queued, generating or optics).
    """
    shot_id = request.match_info["id"]
    store = request.app[STORE]
    record = store.get(shot_id)
    if record is None:
        return error_response(404, "not_found", f"There is no shot with id {shot_id}.")
    if record["status"] in ("queued", "generating", "optics"):
        return error_response(409, "busy", "The shot is still being processed. Cancel it or wait until it is finished.")
    items = request.app[RUNNER].items
    item = items.get(shot_id)
    if item is not None and not item["started"]:
        items.pop(shot_id, None)
    store.remove(shot_id)
    return web.Response(status=204)


async def shot_events(request):
    """Stream server-sent events ``shot`` (the public record as JSON) for the shot in the path.

    Sends the current record first, then each change (at most about 5 frames per second),
    a ``: keep-alive`` comment every KEEPALIVE_S seconds, and closes once the shot is done,
    failed or cancelled. Unknown id: 404 ``not_found``.
    """
    shot_id = request.match_info["id"]
    store = request.app[STORE]
    runner = request.app[RUNNER]
    if store.get(shot_id) is None:
        return error_response(404, "not_found", f"There is no shot with id {shot_id}.")
    resp = web.StreamResponse(
        headers={"Content-Type": "text/event-stream", "Cache-Control": "no-cache"}
    )
    await resp.prepare(request)
    event = runner.watch(shot_id)
    last = None
    try:
        while True:
            event.clear()
            record = store.get(shot_id)
            payload = json.dumps(public_record(record))
            if payload != last:
                await resp.write(f"event: shot\ndata: {payload}\n\n".encode())
                last = payload
            if record["status"] in ("done", "failed", "cancelled"):
                break
            try:
                await asyncio.wait_for(event.wait(), KEEPALIVE_S)
            except asyncio.TimeoutError:
                await resp.write(b": keep-alive\n\n")
                continue
            await asyncio.sleep(0.2)
    except ConnectionResetError:
        pass
    finally:
        runner.unwatch(shot_id, event)
    try:
        await resp.write_eof()
    except ConnectionResetError:
        pass
    return resp


async def get_media(request):
    """Serve the video ``name`` (matching ``MEDIA_NAME``) from the folder of shot ``id`` (Range supported).

    Answers 404 ``not_found`` for any other name, an unknown shot, a missing file or a path that leaves the shot folder.
    With the query parameter ``download=1`` the response also carries ``Content-Disposition: attachment; filename="opencinema-<shot id>-<name>"``; without it no such header is sent.
    """
    shot_id = request.match_info["id"]
    name = request.match_info["name"]
    message = f"There is no media {name} for shot {shot_id}."
    if not MEDIA_NAME.match(name) or ".." in name:
        return error_response(404, "not_found", message)
    if request.app[STORE].get(shot_id) is None:
        return error_response(404, "not_found", message)
    shot_dir = request.app[STORE].shot_dir(shot_id)
    path = shot_dir / name
    if not path.is_file() or path.resolve().parent != shot_dir.resolve():
        return error_response(404, "not_found", message)
    headers = None
    if request.query.get("download") == "1":
        headers = {"Content-Disposition": f'attachment; filename="opencinema-{shot_id}-{name}"'}
    return web.FileResponse(path, headers=headers)


async def index(request):
    """Return the frontend page ``app/static/index.html``."""
    return web.FileResponse(STATIC_DIR / "index.html")


def create_app(comfyui_url, data_dir, seed_samples=False):
    """Build the aiohttp Application for ComfyUI at ``comfyui_url`` and shots in ``data_dir``; with ``seed_samples`` true, a new ``data_dir`` first gets the bundled sample shots (see ``store.seed_samples``).

    Returns the configured ``aiohttp.web.Application``.
    """
    app = web.Application(middlewares=[error_middleware])
    app[COMFYUI_URL] = comfyui_url
    if seed_samples:
        seed_sample_shots(data_dir)
    store = ShotStore(data_dir)
    store.load_all()
    store.recover_interrupted()
    app[STORE] = store
    runner = ShotRunner(store, comfyui_url)
    app[RUNNER] = runner

    async def start_runner(app):
        runner.start()

    async def stop_runner(app):
        await runner.stop()

    app.on_startup.append(start_runner)
    app.on_cleanup.append(stop_runner)
    app.router.add_get("/api/health", health)
    app.router.add_get("/api/options", options)
    app.router.add_get("/api/estimate", estimate)
    app.router.add_post("/api/shots", create_shot)
    app.router.add_post("/api/shots/import", import_shot)
    app.router.add_get("/api/shots", list_shots)
    app.router.add_get("/api/shots/{id}", get_shot)
    app.router.add_delete("/api/shots/{id}", delete_shot)
    app.router.add_post("/api/shots/{id}/reapply", reapply_shot)
    app.router.add_post("/api/shots/{id}/cancel", cancel_shot)
    app.router.add_get("/api/shots/{id}/events", shot_events)
    app.router.add_get("/media/{id}/{name}", get_media)
    app.router.add_get("/", index)
    app.router.add_static("/static/", STATIC_DIR, show_index=False)

    async def revalidate_page_files(request, response):
        # the page and its scripts are checked with the server on every load (cheap: ETag), so an updated app is never shown stale
        if request.path == "/" or request.path.startswith("/static/"):
            response.headers["Cache-Control"] = "no-cache"

    app.on_response_prepare.append(revalidate_page_files)
    return app


def _install_stop_handlers(loop, stop):
    """Make SIGINT, SIGTERM (and SIGBREAK on Windows) set the asyncio.Event ``stop``."""
    if sys.platform == "win32":
        def handler(signum, frame):
            loop.call_soon_threadsafe(stop.set)

        for name in ("SIGINT", "SIGTERM", "SIGBREAK"):
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
        runner = web.AppRunner(create_app(args.comfyui, args.data_dir, seed_samples=args.data_dir == DEFAULT_DATA_DIR), shutdown_timeout=1.0)
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
            try:
                await asyncio.wait_for(runner.cleanup(), 4)
            except asyncio.TimeoutError:
                pass
        if proxy_runner is not None:
            try:
                await asyncio.wait_for(stop_proxy(proxy_runner), 4)
            except asyncio.TimeoutError:
                pass


def main(argv=None) -> int:
    """Run the director app until stopped. ``argv`` is a list of options (sys.argv when None).

    Returns the process exit code: 0 after a KeyboardInterrupt, 1 if the port is not available.
    """
    args = parse_args(argv)
    try:
        return asyncio.run(_serve(args))
    except KeyboardInterrupt:
        return 0
