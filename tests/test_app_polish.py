"""Browser tests of visual polish details in the director app."""
import time
import unittest

from playwright.sync_api import sync_playwright

from tests.app_harness import SHOT, AppHarness

STATUS = "[data-testid=comfy-status]"

JS_ACCENT = """() => {
  const probe = document.createElement('span');
  probe.style.color = getComputedStyle(document.documentElement).getPropertyValue('--accent').trim();
  document.body.appendChild(probe);
  const accent = getComputedStyle(probe).color;
  probe.remove();
  return accent;
}"""

JS_BORDER = "s => getComputedStyle(document.querySelector(s)).borderTopColor"


class PolishTests(unittest.TestCase):
    harness = None
    pw = None
    browser = None

    @classmethod
    def setUpClass(cls):
        try:
            cls.harness = AppHarness().start()
            cls.pw = sync_playwright().start()
            cls.browser = cls.pw.chromium.launch(headless=True)
        except BaseException:
            cls.tearDownClass()
            raise

    @classmethod
    def tearDownClass(cls):
        for closer in (
            lambda: cls.browser and cls.browser.close(),
            lambda: cls.pw and cls.pw.stop(),
            lambda: cls.harness and cls.harness.stop(),
        ):
            try:
                closer()
            except Exception:
                pass
        cls.browser = cls.pw = cls.harness = None

    def setUp(self):
        self.harness.fake.release()
        self.harness.reset()
        self.page = self.browser.new_page(viewport={"width": 1280, "height": 720})
        self.addCleanup(self.page.close)
        self.page.set_default_timeout(15000)
        self.page.goto(self.harness.url)
        self.page.wait_for_function(
            "s => document.querySelector(s) && document.querySelector(s).dataset.state === 'ok'", arg=STATUS
        )

    def test_selected_camera_and_framing_have_accent_border(self):
        page = self.page
        accent = page.evaluate(JS_ACCENT)
        for group, value in (("camera-group", "dolly-in"), ("framing-group", "close-up")):
            with self.subTest(group=group):
                base = f"[data-testid={group}] button[role=radio]"
                selected = f"{base}[data-value='{value}']"
                page.locator(selected).click()
                page.wait_for_function(
                    "s => document.querySelector(s).getAttribute('aria-checked') === 'true'", arg=selected
                )
                unselected = f"{base}[aria-checked=false]"
                page.wait_for_function(
                    "([s, c]) => getComputedStyle(document.querySelector(s)).borderTopColor === c",
                    arg=[selected, accent],
                )
                self.assertEqual(page.evaluate(JS_BORDER, selected), accent)
                self.assertNotEqual(page.evaluate(JS_BORDER, unselected), accent)
                self.assertNotEqual(page.evaluate(JS_BORDER, unselected), page.evaluate(JS_BORDER, selected))

    def start_running_shot(self):
        page, fake = self.page, self.harness.fake
        fake.reset_cache()
        fake.hold_at("SamplerCustomAdvanced")
        self.addCleanup(fake.release)
        page.locator("[data-testid=shot-description]").fill("A rider crosses a foggy salt flat at dawn.")
        page.locator("[data-testid=generate-button]").click()
        page.wait_for_function(
            "() => document.querySelector('[data-testid=status-panel]').dataset.status === 'generating'"
        )

    def test_focus_kept_during_running_shot(self):
        page = self.page
        self.start_running_shot()
        page.evaluate(
            """() => { const lens = document.querySelector('[data-testid=lens-group] [role=radio][data-value="35"]');
                lens.focus(); lens.setAttribute('data-polish-marker', '1'); }"""
        )
        page.wait_for_timeout(1500)  # several progress frames and history refreshes arrive meanwhile
        kept = page.evaluate(
            "() => document.activeElement.getAttribute('data-polish-marker') === '1'"
            " && document.activeElement.matches('[data-testid=lens-group] [role=radio]')"
        )
        self.assertTrue(kept, "the focused lens button must stay the same element with the focus while a shot runs")

    def test_failed_lookup_keeps_following(self):
        page, harness = self.page, self.harness
        _, rec = harness.post("/api/shots", {**SHOT, "description": "An earlier shot, finished.", "seed": 21})
        done_id = rec["id"]
        harness.wait_for_shot(done_id, "done", timeout=90)
        page.reload()
        page.wait_for_function(
            "s => document.querySelector(s) && document.querySelector(s).dataset.state === 'ok'", arg=STATUS
        )
        page.locator("[data-testid=history-new]").click()
        self.start_running_shot()
        page.route(f"**/api/shots/{done_id}", lambda route: route.abort("aborted"))
        page.evaluate(
            f"() => document.querySelector('[data-testid=history-item][data-shot-id=\"{done_id}\"]').click()"
        )
        page.wait_for_timeout(800)
        page.unroute(f"**/api/shots/{done_id}")
        harness.fake.release()
        page.wait_for_function(
            "() => document.querySelector('[data-testid=viewport]').dataset.state === 'result'", timeout=60000
        )

    def test_videos_released_while_new_shot_runs(self):
        page, harness = self.page, self.harness
        _, rec = harness.post("/api/shots", {**SHOT, "description": "A finished shot to show first.", "seed": 22})
        harness.wait_for_shot(rec["id"], "done", timeout=90)
        page.reload()
        page.wait_for_function(
            "() => document.querySelector('[data-testid=viewport]').dataset.state === 'result'", timeout=60000
        )
        page.locator("[data-testid=history-new]").click()
        self.start_running_shot()
        page.wait_for_function("() => document.querySelector('[data-testid=viewport]').dataset.state !== 'result'")
        released = page.evaluate(
            "() => Array.from(document.querySelectorAll('video')).every(v => !v.hasAttribute('src') && v.paused)"
        )
        self.assertTrue(released, "every video must have no src attribute and be paused while a shot runs")

    def test_unmute_toggle_unmutes_only_the_after_video(self):
        page, harness = self.page, self.harness
        _, rec = harness.post("/api/shots", {**SHOT, "description": "A finished shot to unmute.", "seed": 23})
        harness.wait_for_shot(rec["id"], "done", timeout=90)
        page.reload()
        page.wait_for_function(
            "() => document.querySelector('[data-testid=viewport]').dataset.state === 'result'", timeout=60000
        )
        toggle = page.locator("[data-testid=unmute-toggle]")
        toggle.wait_for(state="attached")
        js_muted = (
            "() => ['before-video', 'after-video'].map("
            "n => document.querySelector('[data-testid=' + n + ']').muted)"
        )
        self.assertEqual(page.evaluate(js_muted), [True, True])
        toggle.click()
        page.wait_for_function(
            "() => document.querySelector('[data-testid=unmute-toggle]').getAttribute('aria-pressed') === 'true'"
        )
        self.assertEqual(page.evaluate(js_muted), [True, False])
        toggle.click()
        page.wait_for_function(
            "() => document.querySelector('[data-testid=unmute-toggle]').getAttribute('aria-pressed') === 'false'"
        )
        self.assertEqual(page.evaluate(js_muted), [True, True])

    def test_autoplay_muted_play_causes_no_console_errors(self):
        page, harness = self.page, self.harness
        errors = []
        page.on("console", lambda msg: errors.append(msg.text) if msg.type == "error" else None)
        page.on("pageerror", lambda exc: errors.append(str(exc)))
        _, rec = harness.post("/api/shots", {**SHOT, "description": "A finished shot to autoplay.", "seed": 24})
        harness.wait_for_shot(rec["id"], "done", timeout=90)
        page.reload()
        page.wait_for_function(
            "() => document.querySelector('[data-testid=viewport]').dataset.state === 'result'", timeout=60000
        )
        page.wait_for_function(
            "() => document.querySelector('[data-testid=after-video]').readyState >= 2", timeout=30000
        )
        self.assertEqual(errors, [])
        self.assertTrue(page.locator("[data-testid=player-error]").is_hidden())

    def test_try_again_sends_one_request(self):
        page, harness = self.page, self.harness
        harness.fake.reset_cache()
        harness.fake.fail("SamplerCustomAdvanced", "CUDA out of memory")
        page.locator("[data-testid=shot-description]").fill("A shot that fails in generation.")
        page.locator("[data-testid=generate-button]").click()
        page.wait_for_function(
            "() => document.querySelector('[data-testid=viewport]').dataset.state === 'failed'", timeout=40000
        )
        harness.fake.clear_failures()
        count = len(harness.get("/api/shots")[1]["shots"])
        posts = []
        page.on(
            "request",
            lambda r: posts.append(r.url) if r.method == "POST" and r.url.rstrip("/").endswith("/api/shots") else None,
        )
        page.locator("[data-testid=retry-button]").dblclick()
        deadline = time.time() + 30
        while time.time() < deadline and len(harness.get("/api/shots")[1]["shots"]) < count + 1:
            time.sleep(0.1)
        page.wait_for_timeout(500)
        self.assertEqual(len(posts), 1)
        self.assertEqual(len(harness.get("/api/shots")[1]["shots"]), count + 1)

    def test_hud_reads_lens_aperture_distance_framing(self):
        page = self.page
        pattern = r"^\d+ mm\s+f/\d+(\.\d)?\s+\d+(\.\d)? m\s+[A-Z ]+$"
        js_text = "() => document.querySelector('[data-testid=hud]').textContent.trim()"
        page.wait_for_function(
            "([s, p]) => { const el = document.querySelector(s); return !!el && new RegExp(p).test(el.textContent.trim()); }",
            arg=["[data-testid=hud]", pattern],
        )
        js_tail = r"() => document.querySelector('[data-testid=hud]').textContent.trim().replace(/^.*? m\s+/, '')"
        before = page.evaluate(js_tail)
        page.locator("[data-testid=framing-group] button[role=radio][aria-checked=false]:not([data-value*='-'])").first.click()
        page.wait_for_function(
            "b => document.querySelector('[data-testid=hud]').textContent.trim().replace(/^.*? m\\s+/, '') !== b",
            arg=before,
        )
        self.assertRegex(page.evaluate(js_text), pattern)

    def test_progress_restarts_after_a_finished_shot(self):
        js = """async ([first, second]) => {
          const { setShot, getState } = await import('/static/js/state.js');
          setShot(first);
          setShot(second);
          return getState().shot.progress;
        }"""
        restarted = self.page.evaluate(
            js, [{"id": "a", "status": "done", "progress": 1}, {"id": "a", "status": "optics", "progress": 0.1}]
        )
        self.assertAlmostEqual(restarted, 0.1, places=6)
        clamped = self.page.evaluate(
            js, [{"id": "b", "status": "generating", "progress": 0.5}, {"id": "b", "status": "generating", "progress": 0.3}]
        )
        self.assertAlmostEqual(clamped, 0.5, places=6)

    def test_polling_stops_after_404_not_found(self):
        page, h = self.page, self.harness
        page.route("**/api/shots/*/events", lambda route: route.abort())
        page.reload()
        page.wait_for_function(
            "s => document.querySelector(s) && document.querySelector(s).dataset.state === 'ok'", arg=STATUS
        )
        h.fake.hold_at("SamplerCustomAdvanced")
        shot_id = None
        try:
            page.locator("[data-testid=shot-description]").fill("A rider crosses a foggy salt flat at dawn.")
            page.locator("[data-testid=generate-button]").click()
            page.wait_for_function(
                "() => document.querySelector('[data-testid=viewport]').dataset.state === 'working'"
            )
            shot_id = h.get("/api/shots")[1]["shots"][0]["id"]
            requests = []

            def not_found(route):
                if route.request.method == "GET":
                    requests.append(route.request.url)
                    route.fulfill(
                        status=404,
                        content_type="application/json",
                        body='{"error":{"code":"not_found","message":"Shot not found"}}',
                    )
                else:
                    route.continue_()

            page.route(f"**/api/shots/{shot_id}", not_found)
            page.wait_for_function("() => document.body.innerText.includes('no longer exists')", timeout=8000)
            n = len(requests)
            deadline = time.time() + 2.5
            while time.time() < deadline:
                page.wait_for_timeout(100)
                self.assertEqual(len(requests), n, "the app kept polling after the 404")
        finally:
            h.fake.release()
            if shot_id:
                h.wait_for_shot(shot_id, "done")


if __name__ == "__main__":
    unittest.main()
