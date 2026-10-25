"""A fake ComfyUI server for testing the Open Cinema app without ComfyUI, models or a GPU.

It speaks the part of ComfyUI's own API that comfy-api-proxy (and so the Comfy SDK) uses:
POST /prompt, GET /history/{id}, GET /queue, GET /ws, GET /view, POST /upload/image, GET /object_info,
GET /system_stats and POST /api/jobs/{id}/cancel.

A prompt is validated the way ComfyUI validates one, against a snapshot of the real node definitions
(tests/fixtures/app/comfy_object_info.json, recorded from ComfyUI 0.41.0 with the Open Optics pack): unknown node
types, missing required inputs, values outside min/max or not in a combo's list, links to missing nodes or to an
output of the wrong type, and a LoadVideo file that was never uploaded are all rejected with ComfyUI's error shape.
Unlike ComfyUI it also rejects an input name the node does not have, so a typo in a graph is caught.

It then "runs" the graph: nodes execute in dependency order, with ws progress messages, ComfyUI's execution cache
(a node whose inputs did not change is reported as cached and not run again), and a SaveVideo output that is a tiny real
WebM clip (a sharp one for graphs without Depth of Field, a soft one for graphs with it), so a browser can play it.

    fake = FakeComfy()
    url = fake.start()              # "http://127.0.0.1:<port>"
    fake.fail("DA3Inference", "CUDA out of memory")
    fake.hold_at("SamplerCustomAdvanced")   # wait there until fake.release()
    fake.stop()                     # the port now refuses connections, as when ComfyUI is not running
    fake.start()                    # same port again

Things a real ComfyUI does that tests can switch on:
    fake.real_progress = True             # ws `progress_state` frames (every node of the prompt with a state) next to `progress`,
                                          # and a held node keeps announcing itself, as ComfyUI does while it works
    fake.stall_health(20)                 # GET /system_stats answers only after 20 s (a busy ComfyUI: model load, swap, VAE decode)
    fake.drop_connections(["/history", "/queue"], 6)   # for 6 s those paths close the connection (the proxy then answers 503)
    fake.remove_node("DA3Inference")      # the custom node is not installed: /object_info lacks it, a graph with it is refused

Every executed node is recorded in `fake.executed` as {"prompt_id", "node_id", "class_type", "inputs"} (inputs are the
graph's inputs for that node, links as [node_id, slot]); every accepted graph is in `fake.prompts`.
This file is a test fixture: do not edit it to make a test pass.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import math
import shutil
import tempfile
import threading
import time
import uuid
from pathlib import Path

from aiohttp import web

HERE = Path(__file__).resolve().parent
FIXTURES = HERE / "fixtures" / "app"
OBJECT_INFO_PATH = FIXTURES / "comfy_object_info.json"

# nodes that report step-by-step progress over the websocket
STEPPED = {"SamplerCustomAdvanced", "VAEDecodeTiled", "DA3Inference", "OpenOptics_DepthOfField", "OpenOptics_DepthTemporalSmooth"}
OPTICS = "OpenOptics_DepthOfField"


def load_object_info():
    return json.loads(OBJECT_INFO_PATH.read_text(encoding="utf-8"))


def _is_link(value):
    return isinstance(value, list) and len(value) == 2 and isinstance(value[0], str) and isinstance(value[1], int)


def _spec_type(spec):
    kind = spec[0]
    return "COMBO_LIST" if isinstance(kind, list) else kind


def _combo_options(spec):
    kind, opts = spec[0], (spec[1] if len(spec) > 1 and isinstance(spec[1], dict) else {})
    if isinstance(kind, list):
        return kind
    return opts.get("options")


def validate_prompt(prompt, object_info=None, input_files=()):
    """Validate an API-format graph like ComfyUI does. Returns a list of problem strings (empty if it is valid).

    input_files are the names that exist in ComfyUI's input folder, for the LoadVideo / LoadImage `file` / `image` combos.
    """
    info = object_info if object_info is not None else load_object_info()
    problems = []
    if not isinstance(prompt, dict) or not prompt:
        return ["The prompt is empty"]
    outputs = 0
    for node_id, node in prompt.items():
        if not isinstance(node, dict) or "class_type" not in node or not isinstance(node.get("inputs"), dict):
            problems.append(f"node {node_id}: must have class_type and inputs")
            continue
        ctype = node["class_type"]
        definition = info.get(ctype)
        if definition is None:
            problems.append(f"node {node_id}: Node '{ctype}' not found. The custom node may not be installed.")
            continue
        if definition.get("output_node"):
            outputs += 1
        required = (definition["input"].get("required") or {})
        optional = (definition["input"].get("optional") or {})
        dynamic = any(_spec_type(s) == "COMFY_DYNAMICCOMBO_V3" for s in {**required, **optional}.values())
        inputs = node["inputs"]
        for name in required:
            if name not in inputs:
                problems.append(f"node {node_id} ({ctype}): Required input is missing: {name}")
        for name, value in inputs.items():
            spec = required.get(name) or optional.get(name)
            where = f"node {node_id} ({ctype}).{name}"
            if spec is None:
                if not dynamic:
                    problems.append(f"{where}: this node has no input called {name}")
                continue
            kind = _spec_type(spec)
            opts = spec[1] if len(spec) > 1 and isinstance(spec[1], dict) else {}
            if _is_link(value):
                source = prompt.get(value[0])
                if source is None:
                    problems.append(f"{where}: links to node {value[0]}, which is not in the prompt")
                    continue
                source_def = info.get(source.get("class_type"))
                if source_def is None:
                    continue
                if value[1] >= len(source_def["output"]):
                    problems.append(f"{where}: node {value[0]} has no output {value[1]}")
                    continue
                produced = source_def["output"][value[1]]
                if kind not in ("COMBO", "COMBO_LIST", "COMFY_DYNAMICCOMBO_V3", "FLOAT,INT") and produced != kind and kind != "*":
                    problems.append(f"{where}: needs {kind} but node {value[0]} output {value[1]} is {produced}")
                continue
            if kind in ("INT", "FLOAT", "FLOAT,INT"):
                if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
                    problems.append(f"{where}: {value!r} is not a number")
                    continue
                if "min" in opts and value < opts["min"]:
                    problems.append(f"{where}: value {value} smaller than min {opts['min']}")
                if "max" in opts and value > opts["max"]:
                    problems.append(f"{where}: value {value} bigger than max {opts['max']}")
            elif kind == "BOOLEAN":
                if not isinstance(value, bool):
                    problems.append(f"{where}: {value!r} is not a boolean")
            elif kind == "STRING":
                if not isinstance(value, str):
                    problems.append(f"{where}: {value!r} is not a string")
            elif kind in ("COMBO", "COMBO_LIST"):
                options = _combo_options(spec)
                if ctype in ("LoadVideo", "LoadImage") and name in ("file", "image"):
                    options = list(input_files)
                if options is not None and value not in options:
                    shown = ", ".join(str(o) for o in options[:6])
                    problems.append(f"{where}: Value not in list: {name}: '{value}' not in [{shown}]")
            elif kind == "COMFY_DYNAMICCOMBO_V3":
                keys = [o.get("key") for o in (opts.get("options") or [])]
                if keys and value not in keys:
                    problems.append(f"{where}: Value not in list: '{value}' not in {keys}")
            else:
                problems.append(f"{where}: needs a {kind} link, not a value")
    if outputs == 0 and not problems:
        problems.append("Prompt has no outputs")
    return problems


class FakeComfy:
    def __init__(self, delay=0.03, steps=4):
        self.object_info = load_object_info()
        self.delay = delay
        self.steps = steps
        self.root = Path(tempfile.mkdtemp(prefix="fake_comfy_"))
        self.input_dir = self.root / "input"
        self.output_dir = self.root / "output"
        self.input_dir.mkdir()
        self.output_dir.mkdir()
        self.prompts: list[dict] = []
        self.executed: list[dict] = []
        self.uploads: list[str] = []
        self.history: dict[str, dict] = {}
        self._failures: dict[str, str] = {}
        self._hold_at: str | None = None
        self._cache: dict[str, dict] = {}
        self._counters: dict[str, int] = {}
        self._port = 0
        self._thread: threading.Thread | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._runner: web.AppRunner | None = None
        self._ready = threading.Event()
        self._queue: asyncio.Queue | None = None
        self._pending: list[tuple[str, dict, dict]] = []
        self._running: tuple[str, dict, dict] | None = None
        self._ws: dict[str, set] = {}
        self._gate: asyncio.Event | None = None
        self._interrupt: set[str] = set()
        self._worker: asyncio.Task | None = None
        self.real_progress = False
        self._stall_until = 0.0
        self._drop: tuple | None = None

    # ---------------------------------------------------------------- control (thread-safe)
    @property
    def url(self):
        return f"http://127.0.0.1:{self._port}"

    def fail(self, class_type, message="Simulated failure"):
        self._failures[class_type] = message

    def clear_failures(self):
        self._failures.clear()

    def hold_at(self, class_type):
        """Pause execution just before the first node of this type runs, until release()."""
        self._hold_at = class_type
        self._call(self._arm_gate)

    def release(self):
        self._hold_at = None
        self._call(self._open_gate)

    def reset_cache(self):
        self._cache.clear()

    def stall_health(self, seconds):
        """GET /system_stats waits until `seconds` from now before it answers."""
        self._stall_until = time.time() + seconds

    def drop_connections(self, prefixes, seconds):
        """For `seconds`, a request whose path starts with one of `prefixes` gets its connection closed without an answer."""
        self._drop = (tuple(prefixes), time.time() + seconds)

    def remove_node(self, class_type):
        self.object_info.pop(class_type, None)

    def count(self, class_type):
        return sum(1 for e in self.executed if e["class_type"] == class_type)

    def start(self, port=None):
        """Start serving (in a thread). Returns the base URL. After stop(), start() reuses the same port."""
        if port is not None:
            self._port = port
        self._ready.clear()
        self._thread = threading.Thread(target=self._serve, daemon=True)
        self._thread.start()
        if not self._ready.wait(15):
            raise RuntimeError("the fake ComfyUI did not start")
        return self.url

    def stop(self):
        """Stop serving; the port refuses connections until start() is called again. Files are kept."""
        loop, thread = self._loop, self._thread
        if loop is None or thread is None:
            return
        fut = asyncio.run_coroutine_threadsafe(self._shutdown(), loop)
        try:
            fut.result(15)
        except Exception:
            pass
        thread.join(15)
        self._thread = None

    def close(self):
        self.stop()
        shutil.rmtree(self.root, ignore_errors=True)

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, *exc):
        self.close()

    def _call(self, fn):
        if self._loop is not None and self._thread is not None:
            self._loop.call_soon_threadsafe(fn)

    def _arm_gate(self):
        if self._gate is not None:
            self._gate.clear()

    def _open_gate(self):
        if self._gate is not None:
            self._gate.set()

    # ---------------------------------------------------------------- server
    def _serve(self):
        loop = asyncio.new_event_loop()
        self._loop = loop
        asyncio.set_event_loop(loop)
        loop.run_until_complete(self._startup())
        self._ready.set()
        loop.run_forever()
        loop.close()

    async def _startup(self):
        self._queue = asyncio.Queue()
        self._gate = asyncio.Event()
        self._gate.set()
        @web.middleware
        async def faults(request, handler):
            drop = self._drop
            if drop and time.time() < drop[1] and request.path.startswith(drop[0]):
                if request.transport is not None:
                    request.transport.close()
                raise web.HTTPServiceUnavailable()
            return await handler(request)

        app = web.Application(client_max_size=512 * 1024 * 1024, middlewares=[faults])
        app.add_routes([
            web.post("/prompt", self.post_prompt),
            web.get("/history/{id}", self.get_history),
            web.get("/history", self.get_history_all),
            web.get("/queue", self.get_queue),
            web.post("/queue", self.post_queue),
            web.post("/interrupt", self.post_interrupt),
            web.post("/api/jobs/{id}/cancel", self.post_cancel),
            web.get("/ws", self.ws),
            web.get("/view", self.view),
            web.post("/upload/image", self.upload),
            web.get("/object_info", self.get_object_info),
            web.get("/object_info/{node}", self.get_object_info_one),
            web.get("/system_stats", self.system_stats),
        ])
        self._runner = web.AppRunner(app, access_log=None)
        await self._runner.setup()
        site = web.TCPSite(self._runner, "127.0.0.1", self._port)
        await site.start()
        self._port = site._server.sockets[0].getsockname()[1]
        self._worker = asyncio.ensure_future(self._work())

    async def _shutdown(self):
        if self._worker:
            self._worker.cancel()
        for sockets in list(self._ws.values()):
            for ws in list(sockets):
                await ws.close()
        if self._runner:
            await self._runner.cleanup()
        self._pending.clear()
        self._running = None
        self._loop.call_soon(self._loop.stop)

    # ---------------------------------------------------------------- endpoints
    def _input_files(self):
        return [p.relative_to(self.input_dir).as_posix() for p in self.input_dir.rglob("*") if p.is_file()]

    async def post_prompt(self, request):
        try:
            body = await request.json()
        except Exception:
            return web.json_response({"error": {"type": "invalid_json", "message": "Body must be JSON"}, "node_errors": {}}, status=400)
        prompt = body.get("prompt")
        problems = validate_prompt(prompt, self.object_info, self._input_files())
        if problems:
            node_errors = {}
            for p in problems:
                node_id = p.split(" ")[1] if p.startswith("node ") else "0"
                node_errors.setdefault(node_id, {"errors": [], "dependent_outputs": [], "class_type": (prompt or {}).get(node_id, {}).get("class_type") if isinstance(prompt, dict) else None})["errors"].append(
                    {"type": "invalid_input", "message": p, "details": "", "extra_info": {}})
            return web.json_response({"error": {"type": "prompt_outputs_failed_validation", "message": "Prompt outputs failed validation: " + problems[0],
                                                "details": "\n".join(problems), "extra_info": {}}, "node_errors": node_errors}, status=400)
        prompt_id = body.get("prompt_id") or str(uuid.uuid4())
        client_id = body.get("client_id") or ""
        self.prompts.append(prompt)
        number = len(self.prompts)
        self._pending.append((prompt_id, prompt, {"client_id": client_id}))
        await self._queue.put(prompt_id)
        return web.json_response({"prompt_id": prompt_id, "number": number, "node_errors": {}})

    def _history_entry(self, prompt_id):
        return self.history.get(prompt_id)

    async def get_history(self, request):
        pid = request.match_info["id"]
        entry = self.history.get(pid)
        return web.json_response({pid: entry} if entry else {})

    async def get_history_all(self, request):
        return web.json_response(self.history)

    async def get_queue(self, request):
        def item(i, entry):
            return [i, entry[0], entry[1], entry[2], []]
        running = [item(0, self._running)] if self._running else []
        pending = [item(i + 1, e) for i, e in enumerate(self._pending)]
        return web.json_response({"queue_running": running, "queue_pending": pending})

    async def post_queue(self, request):
        return web.json_response({})

    async def post_interrupt(self, request):
        if self._running:
            self._interrupt.add(self._running[0])
        return web.json_response({})

    async def post_cancel(self, request):
        pid = request.match_info["id"]
        if self._running and self._running[0] == pid:
            self._interrupt.add(pid)
            self._gate.set()
        else:
            self._pending = [e for e in self._pending if e[0] != pid]
        return web.json_response({"id": pid})

    async def get_object_info(self, request):
        return web.json_response(self.object_info)

    async def get_object_info_one(self, request):
        name = request.match_info["node"]
        if name not in self.object_info:
            return web.json_response({}, status=404)
        return web.json_response({name: self.object_info[name]})

    async def system_stats(self, request):
        wait = self._stall_until - time.time()
        if wait > 0:
            await asyncio.sleep(wait)
        return web.json_response({"system": {"os": "fake", "comfyui_version": "fake-0.41.0", "python_version": "3.13", "ram_total": 1, "ram_free": 1},
                                  "devices": [{"name": "fake cuda:0 NVIDIA GeForce RTX 3090", "type": "cuda", "index": 0, "vram_total": 25769803776, "vram_free": 20000000000}]})

    async def ws(self, request):
        client_id = request.query.get("clientId", "")
        sock = web.WebSocketResponse()
        await sock.prepare(request)
        self._ws.setdefault(client_id, set()).add(sock)
        await sock.send_json({"type": "status", "data": {"status": {"exec_info": {"queue_remaining": len(self._pending)}}, "sid": client_id}})
        try:
            async for msg in sock:
                if msg.type == web.WSMsgType.TEXT:
                    try:
                        data = json.loads(msg.data)
                    except ValueError:
                        continue
                    if data.get("type") == "feature_flags":
                        await sock.send_json({"type": "feature_flags", "data": {"supports_preview_metadata": True, "max_upload_size": 104857600}})
        finally:
            self._ws.get(client_id, set()).discard(sock)
        return sock

    async def view(self, request):
        q = request.query
        base = self.output_dir if q.get("type", "output") == "output" else self.input_dir
        path = (base / q.get("subfolder", "") / q.get("filename", "")).resolve()
        if base.resolve() not in path.parents or not path.is_file():
            return web.Response(status=404, text="not found")
        return web.FileResponse(path)

    async def upload(self, request):
        reader = await request.multipart()
        fields, data, filename = {}, None, None
        async for part in reader:
            if part.name == "image":
                filename = part.filename
                data = await part.read()
            else:
                fields[part.name] = (await part.text())
        if data is None or not filename:
            return web.json_response({"error": "no file"}, status=400)
        sub = fields.get("subfolder", "")
        folder = self.input_dir / sub
        folder.mkdir(parents=True, exist_ok=True)
        name, n = filename, 0
        while (folder / name).exists() and fields.get("overwrite") not in ("true", "1"):
            n += 1
            stem, dot, ext = filename.rpartition(".")
            name = f"{stem} ({n}).{ext}" if dot else f"{filename} ({n})"
        (folder / name).write_bytes(data)
        self.uploads.append(name)
        return web.json_response({"name": name, "subfolder": sub, "type": fields.get("type", "input")})

    # ---------------------------------------------------------------- execution
    async def _send(self, client_id, kind, data):
        message = {"type": kind, "data": data}
        for sock in list(self._ws.get(client_id, ())):
            try:
                await sock.send_json(message)
            except Exception:
                pass

    async def _work(self):
        while True:
            pid = await self._queue.get()
            entry = next((e for e in self._pending if e[0] == pid), None)
            if entry is None:
                continue
            self._pending.remove(entry)
            self._running = entry
            try:
                await self._run(*entry)
            except asyncio.CancelledError:
                raise
            finally:
                self._running = None

    def _signature(self, prompt, node_id, memo):
        if node_id in memo:
            return memo[node_id]
        node = prompt[node_id]
        parts = {}
        for name, value in sorted(node["inputs"].items()):
            parts[name] = ["link", self._signature(prompt, value[0], memo), value[1]] if _is_link(value) else value
            if node["class_type"] in ("LoadVideo", "LoadImage") and name in ("file", "image"):
                path = self.input_dir / str(value)
                parts[name] = [value, hashlib.sha1(path.read_bytes()).hexdigest() if path.is_file() else None]
        memo[node_id] = hashlib.sha1(json.dumps([node["class_type"], parts], sort_keys=True).encode()).hexdigest()
        return memo[node_id]

    def _needed(self, prompt):
        needed, order = set(), []

        def visit(node_id):
            if node_id in needed:
                return
            needed.add(node_id)
            for value in prompt[node_id]["inputs"].values():
                if _is_link(value):
                    visit(value[0])
            order.append(node_id)
        for node_id, node in prompt.items():
            if self.object_info[node["class_type"]].get("output_node"):
                visit(node_id)
        return order

    def _has_optics(self, prompt, node_id, seen=None):
        seen = seen if seen is not None else set()
        if node_id in seen:
            return False
        seen.add(node_id)
        node = prompt[node_id]
        if node["class_type"] == OPTICS:
            return True
        return any(_is_link(v) and self._has_optics(prompt, v[0], seen) for v in node["inputs"].values())

    async def _wait_gate(self, prompt_id):
        while not self._gate.is_set() and prompt_id not in self._interrupt:
            await asyncio.sleep(0.02)

    async def _run(self, prompt_id, prompt, extra):
        client = extra["client_id"]
        messages = []

        async def emit(kind, data):
            data = {**data, "prompt_id": prompt_id}
            messages.append([kind, data])
            await self._send(client, kind, data)

        await emit("execution_start", {"timestamp": int(time.time() * 1000)})
        order = self._needed(prompt)
        memo = {}
        sigs = {n: self._signature(prompt, n, memo) for n in order}
        cached = [n for n in order if sigs[n] in self._cache]
        await emit("execution_cached", {"nodes": cached, "timestamp": int(time.time() * 1000)})
        outputs = {}
        executed_now = []
        states = {n: ("finished" if n in cached else "pending") for n in order}

        async def announce(current=None, value=0, maximum=1):
            """ComfyUI's `progress_state`: every node of the prompt with its state."""
            nodes = {}
            for nid in order:
                running = nid == current
                nodes[nid] = {"value": value if running else (1 if states[nid] == "finished" else 0), "max": maximum if running else 1,
                              "state": "running" if running else states[nid], "node_id": nid, "prompt_id": prompt_id,
                              "display_node_id": nid, "parent_node_id": None, "real_node_id": nid}
            await self._send(client, "progress_state", {"prompt_id": prompt_id, "nodes": nodes})

        try:
            for node_id in order:
                node = prompt[node_id]
                ctype = node["class_type"]
                if prompt_id in self._interrupt:
                    raise asyncio.CancelledError("interrupted")
                if node_id in cached:
                    if self.object_info[ctype].get("output_node") and self._cache[sigs[node_id]].get("ui"):
                        outputs[node_id] = self._cache[sigs[node_id]]["ui"]
                    continue
                if self.real_progress:
                    await emit("executing", {"node": node_id, "display_node": node_id})
                    await announce(node_id)
                    if self._hold_at == ctype:
                        self._gate.clear()
                        while not self._gate.is_set() and prompt_id not in self._interrupt:
                            await announce(node_id)
                            await asyncio.sleep(0.6)
                        if prompt_id in self._interrupt:
                            raise asyncio.CancelledError("interrupted")
                else:
                    if self._hold_at == ctype:
                        self._gate.clear()
                        await self._wait_gate(prompt_id)
                        if prompt_id in self._interrupt:
                            raise asyncio.CancelledError("interrupted")
                    await emit("executing", {"node": node_id, "display_node": node_id})
                if ctype in self._failures:
                    await emit("execution_error", {"node_id": node_id, "node_type": ctype, "executed": executed_now, "exception_message": self._failures[ctype],
                                                   "exception_type": "RuntimeError", "traceback": [], "current_inputs": {}, "current_outputs": [],
                                                   "timestamp": int(time.time() * 1000)})
                    self._finish(prompt_id, prompt, outputs, "error", messages)
                    return
                if ctype in STEPPED:
                    for step in range(1, self.steps + 1):
                        await asyncio.sleep(self.delay)
                        await emit("progress", {"value": step, "max": self.steps, "node": node_id})
                        if self.real_progress:
                            await announce(node_id, step, self.steps)
                else:
                    await asyncio.sleep(self.delay)
                self.executed.append({"prompt_id": prompt_id, "node_id": node_id, "class_type": ctype, "inputs": json.loads(json.dumps(node["inputs"]))})
                executed_now.append(node_id)
                states[node_id] = "finished"
                ui = None
                if self.object_info[ctype].get("output_node"):
                    ui = self._save_output(prompt, node_id, node)
                    outputs[node_id] = ui
                    await emit("executed", {"node": node_id, "display_node": node_id, "output": ui})
                self._cache[sigs[node_id]] = {"ui": ui}
            await emit("executing", {"node": None})
            await emit("execution_success", {"timestamp": int(time.time() * 1000)})
            self._finish(prompt_id, prompt, outputs, "success", messages)
        except asyncio.CancelledError:
            if prompt_id not in self._interrupt:
                raise
            await emit("execution_interrupted", {"node_id": order[len(executed_now)] if len(executed_now) < len(order) else order[-1], "node_type": "", "executed": executed_now})
            self._finish(prompt_id, prompt, outputs, "error", messages)
        finally:
            self._interrupt.discard(prompt_id)

    def _save_output(self, prompt, node_id, node):
        prefix = str(node["inputs"].get("filename_prefix", "ComfyUI"))
        sub, _, stem = prefix.rpartition("/")
        folder = self.output_dir / sub
        folder.mkdir(parents=True, exist_ok=True)
        n = self._counters[prefix] = self._counters.get(prefix, 0) + 1
        if node["class_type"] == "SaveVideo":
            name = f"{stem}_{n:05d}_.webm"
            fixture = "clip_soft.webm" if self._has_optics(prompt, node_id) else "clip_sharp.webm"
            shutil.copyfile(FIXTURES / fixture, folder / name)
            return {"images": [{"filename": name, "subfolder": sub, "type": "output"}], "animated": [True]}
        name = f"{stem}_{n:05d}_.png"
        (folder / name).write_bytes(bytes.fromhex("89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c4890000000d49444154789c6360f8cfc0f01f0005000201a5f645400000000049454e44ae426082"))
        return {"images": [{"filename": name, "subfolder": sub, "type": "output"}]}

    def _finish(self, prompt_id, prompt, outputs, status, messages):
        self.history[prompt_id] = {"prompt": [len(self.history), prompt_id, prompt, {}, list(outputs)], "outputs": outputs,
                                   "status": {"status_str": status, "completed": status == "success", "messages": messages}, "meta": {}}
