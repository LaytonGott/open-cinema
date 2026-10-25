"""Browser test of the director app's whole flow, one shared page."""
import unittest

from playwright.sync_api import sync_playwright

from tests.app_harness import AppHarness

STATUS = "[data-testid=comfy-status]"


class FlowTest(unittest.TestCase):
    harness = None
    pw = None
    browser = None
    page = None
    errors = []
    foreign = []

    @classmethod
    def setUpClass(cls):
        cls.errors = []
        cls.foreign = []
        try:
            cls.harness = AppHarness().start()
            cls.harness.reset()
            cls.pw = sync_playwright().start()
            cls.browser = cls.pw.chromium.launch(headless=True)
            cls.page = cls.browser.new_page(viewport={"width": 1366, "height": 768})
            cls.page.set_default_timeout(15000)
            cls.page.on("console", cls._on_console)
            cls.page.on("pageerror", lambda exc: cls.errors.append(f"pageerror: {exc}"))
            cls.page.on("requestfailed", cls._on_request_failed)
            cls.page.on("request", cls._on_request)
        except BaseException:
            cls.tearDownClass()
            raise

    @classmethod
    def tearDownClass(cls):
        for closer in (
            lambda: cls.page and cls.page.close(),
            lambda: cls.browser and cls.browser.close(),
            lambda: cls.pw and cls.pw.stop(),
            lambda: cls.harness and cls.harness.stop(),
        ):
            try:
                closer()
            except Exception:
                pass
        cls.page = cls.browser = cls.pw = cls.harness = None

    @classmethod
    def _on_console(cls, msg):
        if msg.type != "error":
            return
        if "Failed to load resource" in msg.text and "/api/" in (msg.location.get("url") or ""):
            return
        cls.errors.append(f"console: {msg.text}")

    @classmethod
    def _on_request_failed(cls, request):
        failure = request.failure or ""
        if "ERR_ABORTED" in failure or "/events" in request.url:
            return
        cls.errors.append(f"requestfailed: {request.url} {failure}")

    @classmethod
    def _on_request(cls, request):
        url = request.url
        if url.startswith(("data:", "blob:", "about:")):
            return
        if not url.startswith(f"http://127.0.0.1:{cls.harness.port}/"):
            cls.foreign.append(url)

    def choose(self, group_testid, value):
        self.page.locator(f"[data-testid={group_testid}] [role=radio][data-value={value}]").click()

    def set_range(self, testid, value):
        self.page.locator(f"[data-testid={testid}]").evaluate(
            "(el, v) => { el.value = v;"
            " el.dispatchEvent(new Event('input', {bubbles: true}));"
            " el.dispatchEvent(new Event('change', {bubbles: true})); }",
            value,
        )

    def wait_state(self, testid, state):
        self.page.wait_for_function(
            "([s, v]) => document.querySelector(s) && document.querySelector(s).dataset.state === v",
            arg=[f"[data-testid={testid}]", state],
        )

    def test_1a_open(self):
        self.page.goto(self.harness.url)
        self.wait_state("comfy-status", "ok")


if __name__ == "__main__":
    unittest.main()
