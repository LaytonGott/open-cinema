"""Browser test of keyboard use of the shot form."""
import time
import unittest

from playwright.sync_api import sync_playwright

from tests.app_harness import AppHarness

STATUS = "[data-testid=comfy-status]"
GENERATE = "[data-testid=generate-button]"


class FormKeyboardTest(unittest.TestCase):
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
        self.page = self.browser.new_page()
        self.addCleanup(self.page.close)
        self.page.set_default_timeout(15000)
        self.page.goto(self.harness.url)
        self.page.wait_for_function(
            "s => document.querySelector(s) && document.querySelector(s).dataset.state === 'ok'", arg=STATUS
        )

    def shot_ids(self):
        code, body = self.harness.get("/api/shots")
        self.assertEqual(code, 200)
        return [s["id"] for s in body["shots"]]

    def test_space_selects_focused_radio(self):
        radio = self.page.locator("[data-testid=lens-group] [role=radio][data-value='35']")
        radio.wait_for()
        # earlier tests leave shots behind; the HUD shows the restored shot until a new one is started
        self.page.locator("[data-testid=history-new]").click()
        self.page.wait_for_function(
            "() => document.querySelector('[data-testid=viewport]').dataset.state === 'empty'"
        )
        radio.focus()
        radio.press("Space")
        self.page.wait_for_function(
            "() => document.querySelector('[data-testid=lens-group] [data-value=\"35\"]')"
            ".getAttribute('aria-checked') === 'true'"
        )
        self.page.wait_for_function(
            "() => document.querySelector('[data-testid=hud]').textContent.includes('35 mm')"
        )

    def test_only_checked_radio_is_tab_stop(self):
        for name in ("camera-group", "lens-group", "framing-group"):
            with self.subTest(group=name):
                radios = self.page.locator(f"[data-testid={name}] [role=radio]")
                radios.first.wait_for()
                stops = [b for b in radios.all() if b.get_attribute("tabindex") == "0"]
                self.assertEqual(len(stops), 1)
                self.assertEqual(stops[0].get_attribute("aria-checked"), "true")

    def start_empty_viewport(self):
        self.page.locator("[data-testid=history-new]").click()
        self.page.wait_for_function(
            "() => document.querySelector('[data-testid=viewport]').dataset.state === 'empty'"
        )

    def group_values(self, group):
        return self.page.evaluate(
            "g => [...document.querySelectorAll(`[data-testid=${g}] [role=radio]`)].map(b => b.dataset.value)",
            group,
        )

    def checked_value(self, group):
        return self.page.evaluate(
            "g => document.querySelector(`[data-testid=${g}] [role=radio][aria-checked=true]`).dataset.value",
            group,
        )

    def wait_checked_and_focused(self, group, value):
        self.page.wait_for_function(
            "([g, v]) => { const b = document.querySelector(`[data-testid=${g}] [role=radio][data-value=\"${v}\"]`);"
            " return !!b && b.getAttribute('aria-checked') === 'true' && document.activeElement === b; }",
            arg=[group, value],
        )

    def arrow_from(self, group, start, key, target):
        """Make `start` checked and focused, press `key`, and wait for `target` to be checked and focused.

        The group re-renders on every state change, so the buttons can be replaced between focus and key press;
        retry the whole sequence until the target is reached.
        """
        sel = f"[data-testid={group}] [role=radio]"
        deadline = time.time() + 15
        while True:
            self.page.wait_for_function(
                "s => document.querySelectorAll(s).length > 0 && document.querySelector(s + '[aria-checked=true]')",
                arg=sel,
            )
            if self.checked_value(group) != start:
                self.page.locator(f"{sel}[data-value='{start}']").click()
            self.page.wait_for_function(
                "([s, v]) => { const b = document.querySelector(s + `[data-value=\"${v}\"]`);"
                " if (!b || b.getAttribute('aria-checked') !== 'true') return false;"
                " b.focus(); return document.activeElement === b; }",
                arg=[sel, start],
            )
            self.page.keyboard.press(key)
            try:
                self.page.wait_for_function(
                    "([g, v]) => { const b = document.querySelector(`[data-testid=${g}] [role=radio][data-value=\"${v}\"]`);"
                    " return !!b && b.getAttribute('aria-checked') === 'true' && document.activeElement === b; }",
                    arg=[group, target],
                    timeout=2000,
                )
                return
            except Exception:
                if time.time() > deadline:
                    raise

    def test_arrow_keys_move_between_lenses(self):
        self.page.locator("[data-testid=lens-group] [role=radio]").first.wait_for()
        self.start_empty_viewport()
        self.page.wait_for_function(
            "() => document.querySelector('[data-testid=lens-group] [aria-checked=true]')"
        )
        values = self.group_values("lens-group")
        start = self.checked_value("lens-group")
        nxt = values[(values.index(start) + 1) % len(values)]
        self.arrow_from("lens-group", start, "ArrowRight", nxt)
        self.arrow_from("lens-group", nxt, "ArrowLeft", start)

    def test_arrow_keys_wrap_in_framing_group(self):
        self.page.locator("[data-testid=framing-group] [role=radio]").first.wait_for()
        values = self.group_values("framing-group")
        self.assertGreater(len(values), 1)
        self.arrow_from("framing-group", values[-1], "ArrowRight", values[0])
        self.arrow_from("framing-group", values[0], "ArrowLeft", values[-1])

    def test_tab_leaves_group_after_arrow_movement(self):
        self.page.locator("[data-testid=camera-group] [role=radio]").first.wait_for()
        values = self.group_values("camera-group")
        start = self.checked_value("camera-group")
        nxt = values[(values.index(start) + 1) % len(values)]
        self.arrow_from("camera-group", start, "ArrowRight", nxt)
        self.assertEqual(
            self.page.evaluate(
                "() => [...document.querySelectorAll('[data-testid=camera-group] [role=radio]')]"
                ".filter(b => b.tabIndex === 0).length"
            ),
            1,
        )
        self.page.keyboard.press("Tab")
        self.page.wait_for_function(
            "() => !document.activeElement.closest('[data-testid=camera-group]')"
        )

    def test_generate_button_disabled_until_text_and_enter_key_submits(self):
        button = self.page.locator(GENERATE)
        self.assertTrue(button.is_disabled())
        before = self.shot_ids()
        self.page.locator("[data-testid=shot-description]").fill("A dog runs on a beach")
        self.page.wait_for_function("s => !document.querySelector(s).disabled", arg=GENERATE)
        button.focus()
        button.press("Enter")
        new = []
        try:
            deadline = time.time() + 15
            while time.time() < deadline and not new:
                new = [i for i in self.shot_ids() if i not in before]
                time.sleep(0.1)
            self.assertEqual(len(new), 1)
        finally:
            self.harness.fake.release()
        self.harness.wait_for_shot(new[0])


if __name__ == "__main__":
    unittest.main()
