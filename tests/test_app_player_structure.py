"""Browser test of the player's DOM structure."""
import unittest

from playwright.sync_api import sync_playwright

from tests.app_harness import AppHarness

DESCRIPTION = "A rider crosses a foggy salt flat at dawn."


def tid(name):
    return "[data-testid=%s]" % name


class PlayerStructureTest(unittest.TestCase):
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

    def open_page(self):
        h = self.harness
        h.reset()
        page = self.browser.new_page()
        self.addCleanup(page.close)
        page.set_default_timeout(15000)
        page.goto(h.url)
        return page

    def generate(self, page):
        page.locator(tid("shot-description")).fill(DESCRIPTION)
        page.locator(tid("generate-button")).click()
        page.wait_for_function(
            "s => document.querySelector(s) && document.querySelector(s).dataset.state === 'result'",
            arg=tid("viewport"),
        )

    def test_player_only_in_result_state(self):
        page = self.open_page()
        page.locator(tid("viewport")).wait_for(state="attached")
        self.assertNotEqual(page.locator(tid("viewport")).get_attribute("data-state"), "result")
        player = page.locator(tid("player"))
        self.assertTrue(player.count() == 0 or not player.first.is_visible())
        self.generate(page)
        player.first.wait_for(state="visible")

    def test_videos_stacked_and_muted(self):
        page = self.open_page()
        self.generate(page)
        page.wait_for_function(
            "() => ['before-video', 'after-video'].every(n => {"
            " const v = document.querySelector('[data-testid=' + n + ']');"
            " return v && v.readyState >= 2; })"
        )
        info = page.evaluate(
            """() => {
            const rect = e => { const r = e.getBoundingClientRect();
                return {x: r.x, y: r.y, width: r.width, height: r.height}; };
            const out = {viewport: rect(document.querySelector('[data-testid=viewport]'))};
            for (const n of ['before-video', 'after-video']) {
                const v = document.querySelector('[data-testid=' + n + ']');
                out[n] = {muted: v.muted, loop: v.loop, playsInline: v.playsInline,
                    videoWidth: v.videoWidth, rect: rect(v),
                    fit: getComputedStyle(v).objectFit, src: v.getAttribute('src')};
            }
            return out;
        }"""
        )
        vp = info["viewport"]
        rects = []
        for n in ("before-video", "after-video"):
            v = info[n]
            self.assertIs(v["muted"], True, n)
            self.assertIs(v["loop"], True, n)
            self.assertIs(v["playsInline"], True, n)
            self.assertGreater(v["videoWidth"], 0, n)
            self.assertEqual(v["fit"], "contain", n)
            r = v["rect"]
            rects.append(r)
            self.assertGreaterEqual(r["x"], vp["x"] - 0.5, n)
            self.assertGreaterEqual(r["y"], vp["y"] - 0.5, n)
            self.assertLessEqual(r["x"] + r["width"], vp["x"] + vp["width"] + 0.5, n)
            self.assertLessEqual(r["y"] + r["height"], vp["y"] + vp["height"] + 0.5, n)
        for key in ("x", "y", "width", "height"):
            self.assertAlmostEqual(rects[0][key], rects[1][key], delta=0.5, msg=key)
        resp = page.request.get(self.harness.url + "/api/shots")
        shot = resp.json()["shots"][0]
        self.assertTrue(info["before-video"]["src"].endswith(shot["before_url"]))
        self.assertTrue(info["after-video"]["src"].endswith(shot["versions"][-1]["url"]))


if __name__ == "__main__":
    unittest.main()
