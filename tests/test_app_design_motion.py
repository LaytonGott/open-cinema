"""Browser test of motion durations and the reduced-motion setting."""
import unittest

from tests.test_app_design_rec import DOT, RecDotTest

DURATIONS = """() => {
  const out = [];
  for (const e of document.querySelectorAll('*')) {
    const s = getComputedStyle(e).transitionDuration;
    for (const d of s.split(',')) out.push(parseFloat(d));
  }
  return out;
}"""


class MotionTest(RecDotTest):
    def test_transition_durations_in_range(self):
        page = self.open_page()
        for v in page.evaluate(DURATIONS):
            if v != 0:
                self.assertGreaterEqual(v, 0.15)
                self.assertLessEqual(v, 0.25)

    def test_reduced_motion_stops_everything(self):
        page = self.open_page()
        page.emulate_media(reduced_motion="reduce")
        shot_id = self.start_held_shot(page)
        try:
            page.locator(DOT).wait_for(state="visible")
            infinite = page.evaluate(
                "() => document.getAnimations().filter(a => a.effect && "
                "a.effect.getComputedTiming().iterations === Infinity).length"
            )
            self.assertEqual(infinite, 0)
            for v in page.evaluate(DURATIONS):
                self.assertLessEqual(v, 0.01)
            self.assertEqual(page.locator(DOT).evaluate("e => getComputedStyle(e).opacity"), "1")
        finally:
            self.harness.fake.release()
        self.harness.wait_for_shot(shot_id, "done")


# Keep unittest from collecting the imported base class a second time.
del RecDotTest

# Inherited tests of the base class would run again here; drop them.
MotionTest.test_dot_visible_only_while_working = None
MotionTest.test_reduced_motion_turns_animation_off = None

if __name__ == "__main__":
    unittest.main()
