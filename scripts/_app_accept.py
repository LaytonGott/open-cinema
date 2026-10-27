"""Shared helpers for scripts/accept_app_*.py (not a check itself).

Report: collects problems; protected_files_unchanged: the fixtures and the spec must be the files they were;
sse_frames: read Server-Sent Events from the app; browser helpers for the Playwright checks.
"""
import hashlib
import http.client
import json
import sys
import threading
import time
from contextlib import contextmanager
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# sha256 of each file (text files with line endings normalised to \n); these must not be edited to make a check pass
PROTECTED = {
    "tests/fake_comfy.py": "e162f1a4aeba67388febe982c8bfa84db85b90264d7dbd08655ee1ffc3ce98fe",
    "tests/app_harness.py": "48f652ff38ade874c526e2c2f91ab82ad609fb7f3c029ecaa9646e311f8c5474",
    "tests/fixtures/app/comfy_object_info.json": "11cc785169676a730065b8d10e63c66e9e27e8c365c13978f43946f759d321ef",
    "tests/fixtures/app/clip_sharp.webm": "c3981c36d26ad2d91b865ebb2f5728484996f613891caa3f13eb76178bcd08d6",
    "tests/fixtures/app/clip_soft.webm": "42cfd2b3a8e3853cceee0192996b1b4d84dd9c2b2dfe9f9d4026a15be7e5e02a",
    "docs/app-spec.md": "ce57269cb0deaa7e30026094e4ba19322b3bb7ce991f46b905a50d1805d16f13",
}


def file_hash(path):
    data = Path(path).read_bytes()
    if Path(path).suffix in (".py", ".json", ".md"):
        data = data.replace(b"\r\n", b"\n")
    return hashlib.sha256(data).hexdigest()


class Report:
    def __init__(self, name):
        self.name = name
        self.problems = []

    def check(self, ok, message):
        if not ok:
            self.problems.append(message)
        return bool(ok)

    def finish(self):
        for p in self.problems:
            print(p)
        print(f"{self.name}: OK" if not self.problems else f"{self.name}: {len(self.problems)} problem(s)")
        sys.exit(1 if self.problems else 0)


def protected_files_unchanged(report):
    for rel, want in PROTECTED.items():
        path = ROOT / rel
        if not path.exists():
            report.problems.append(f"{rel} is missing")
        elif file_hash(path) != want:
            report.problems.append(f"{rel} has been changed; it is a fixed test fixture or the specification and must stay as it is")


def sse_frames(url, on_frame, stop, timeout=90):
    """Read an SSE stream until it ends (or `stop` is set, or timeout). Calls on_frame(event, data) for every frame."""
    parts = urlparse(url)
    conn = http.client.HTTPConnection(parts.hostname, parts.port, timeout=timeout)
    conn.request("GET", parts.path + (("?" + parts.query) if parts.query else ""), headers={"Accept": "text/event-stream"})
    resp = conn.getresponse()
    event, data = None, []
    try:
        while not stop.is_set():
            line = resp.readline()
            if not line:
                return resp.status
            line = line.decode("utf-8").rstrip("\r\n")
            if line == "":
                if event is not None or data:
                    try:
                        payload = json.loads("\n".join(data)) if data else None
                    except ValueError:
                        payload = None
                    on_frame(event or "message", payload)
                event, data = None, []
            elif line.startswith(":"):
                continue
            elif line.startswith("event:"):
                event = line[6:].strip()
            elif line.startswith("data:"):
                data.append(line[5:].lstrip(" "))
    finally:
        conn.close()
    return resp.status


class SseCollector:
    """Follow a shot's event stream in a thread and keep every record it sends."""

    def __init__(self, harness, shot_id):
        self.url = f"{harness.url}/api/shots/{shot_id}/events"
        self.records = []
        self.events = []
        self.stop = threading.Event()
        self.status = None
        self.error = None
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()

    def _run(self):
        try:
            self.status = sse_frames(self.url, self._frame, self.stop)
        except Exception as exc:  # noqa: BLE001
            self.error = exc
        self.finished = True

    finished = False

    def _frame(self, event, data):
        self.events.append(event)
        if event == "shot" and isinstance(data, dict):
            self.records.append(data)

    def join(self, timeout=60):
        self.thread.join(timeout)
        self.stop.set()
        return not self.thread.is_alive()


# ---------------------------------------------------------------- browser
VIEWPORTS = [(1280, 720), (1366, 768), (1440, 900), (1536, 864)]


@contextmanager
def browser():
    from playwright.sync_api import sync_playwright
    with sync_playwright() as pw:
        b = pw.chromium.launch()
        try:
            yield b
        finally:
            b.close()


class Page:
    """A Playwright page that records console errors, page errors, failed requests and requests to other hosts."""

    def __init__(self, browser_, harness, width=1280, height=720, reduced_motion=None):
        kwargs = {"viewport": {"width": width, "height": height}}
        if reduced_motion:
            kwargs["reduced_motion"] = "reduce"
        self.context = browser_.new_context(**kwargs)
        self.page = self.context.new_page()
        self.page.set_default_timeout(15000)
        self.harness = harness
        self.errors = []
        self.foreign = []
        host = f"127.0.0.1:{harness.port}"
        self.page.on("console", self._on_console)
        self.page.on("pageerror", lambda e: self.errors.append(f"pageerror: {e}"))
        self.page.on("requestfailed", self._on_failed)
        self.page.on("response", self._on_response)
        self.page.on("request", lambda r: self.foreign.append(r.url) if (urlparse(r.url).netloc != host and not r.url.startswith(("data:", "blob:", "about:"))) else None)

    def _on_console(self, m):
        if m.type != "error":
            return
        url = (m.location or {}).get("url", "")
        # the app's own API answering 4xx/5xx on purpose (ComfyUI down, busy shot ...) is logged by Chromium as a console error
        if m.text.startswith("Failed to load resource") and urlparse(url).path.startswith("/api/"):
            return
        self.errors.append(f"console.error: {m.text} ({url})")

    def _on_failed(self, r):
        failure = str(r.failure)
        if "ERR_ABORTED" in failure or "/events" in r.url or r.url.startswith("data:"):
            return
        self.errors.append(f"request failed: {r.url} {failure}")

    def _on_response(self, r):
        if r.status >= 400 and not urlparse(r.url).path.startswith("/api/"):
            self.errors.append(f"HTTP {r.status}: {r.url}")

    def open(self):
        self.page.goto(self.harness.url + "/")
        return self

    def t(self, test_id):
        return self.page.get_by_test_id(test_id)

    def close(self):
        self.context.close()


def stop_value(index):
    return [1.4, 2, 2.8, 4, 5.6, 8, 11, 16][index]


def set_range(page_, test_id, value):
    """Set an <input type=range> the way a user does: through the keyboard-independent value setter plus input/change events."""
    page_.t(test_id).evaluate(
        "(el, v) => { el.value = String(v); el.dispatchEvent(new Event('input', {bubbles: true})); el.dispatchEvent(new Event('change', {bubbles: true})); }", value)


def choose(page_, group_test_id, value):
    page_.t(group_test_id).locator(f'[role="radio"][data-value="{value}"]').click()


def make_shot_in_ui(page_, description="A woman in a red coat crosses a rainy street at night.", camera="dolly-in", lens=50, framing="full-body", aperture_index=2):
    page_.t("shot-description").fill(description)
    choose(page_, "camera-group", camera)
    choose(page_, "lens-group", lens)
    choose(page_, "framing-group", framing)
    set_range(page_, "aperture-slider", aperture_index)
    page_.t("generate-button").click()
