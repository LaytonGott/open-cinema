"""Goal check: the player, the before/after slider, the aperture control and versions. Run with: node scripts/run-py.js scripts/accept_app_player.py

Opens finished shots in Chromium (Playwright) against the fake ComfyUI and checks docs/app-spec.md section 5.1 "player" and
"optics controls": both videos load and play together, the scrubber, the compare slider with keyboard and mouse (and what it
really shows, pixel by pixel), re-applying another aperture without regenerating, versions, errors in a re-apply, and the
history. Prints one line per problem and exits 1 if there is any.
"""
import io
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _app_accept import Page, Report, browser, protected_files_unchanged, set_range  # noqa: E402

report = Report("app player")
protected_files_unchanged(report)
if report.problems:
    report.finish()

import numpy as np  # noqa: E402
from PIL import Image  # noqa: E402

from tests.app_harness import SHOT, AppHarness  # noqa: E402


def attr(p, test_id, name):
    return p.t(test_id).first.get_attribute(name)


def wait_for(p, predicate, timeout=20, what="the condition"):
    end = time.time() + timeout
    while time.time() < end:
        try:
            if predicate():
                return True
        except Exception:  # noqa: BLE001
            pass
        p.page.wait_for_timeout(50)
    return False


def video_info(p, test_id):
    return p.t(test_id).evaluate("v => ({paused: v.paused, t: v.currentTime, d: v.duration, ready: v.readyState, w: v.videoWidth, src: v.currentSrc, muted: v.muted})")


def shot_png(p, test_id="player"):
    return np.asarray(Image.open(io.BytesIO(p.t(test_id).screenshot())).convert("RGB"), dtype=float)


def band_diff(a, b, x0, x1):
    """Mean absolute difference over the vertical middle band of columns x0:x1 (fractions of the width)."""
    h, w, _ = a.shape
    ys = slice(int(h * 0.2), int(h * 0.8))
    xs = slice(int(w * x0), int(w * x1))
    return float(np.abs(a[ys, xs] - b[ys, xs]).mean())


def run():
    with AppHarness(delay=0.03) as h, browser() as b:
        fake = h.fake
        status, rec = h.post("/api/shots", SHOT)
        sid = rec["id"]
        done = h.wait_for_shot(sid, "done")
        status, rec2 = h.post("/api/shots", {**SHOT, "description": "Another shot to fill the history.", "seed": 8, "lens_mm": 35, "framing": "waist-up", "aperture": 5.6})
        h.wait_for_shot(rec2["id"], "done")

        p = Page(b, h).open()
        report.check(wait_for(p, lambda: attr(p, "viewport", "data-state") == "result", 15), f"opening the page with finished shots must show the latest one ('result'); state {attr(p, 'viewport', 'data-state')!r}")
        report.check(p.t("history-item").count() == 2, f"history must list both shots; found {p.t('history-item').count()}")
        p.t("history-item").nth(1).click()
        report.check(wait_for(p, lambda: video_info(p, "before-video")["src"].endswith(done["before_url"]), 10), "clicking the older history item must load that shot's before video")

        # ---- the player: both videos loaded
        report.check(p.t("player").count() == 1 and p.t("before-video").count() == 1 and p.t("after-video").count() == 1, "the player needs before-video and after-video")
        report.check(wait_for(p, lambda: video_info(p, "before-video")["ready"] >= 2 and video_info(p, "after-video")["ready"] >= 2, 15), "both videos must load")
        b_info, a_info = video_info(p, "before-video"), video_info(p, "after-video")
        report.check(b_info["src"].endswith(done["before_url"]) and a_info["src"].endswith(done["versions"][0]["url"]), f"before-video must play the before file and after-video the shown version; got {b_info['src']} / {a_info['src']}")
        report.check(b_info["w"] > 0 and a_info["w"] > 0 and b_info["muted"] and a_info["muted"], "videos must decode (videoWidth > 0) and be muted")
        report.check(p.t("label-before").inner_text().strip() == "Before" and p.t("label-after").inner_text().strip() == "After f/2.8", f"labels must read 'Before' and 'After f/2.8'; got {p.t('label-before').inner_text()!r} / {p.t('label-after').inner_text()!r}")

        # ---- play together, pause, scrub
        report.check(attr(p, "play-toggle", "aria-pressed") in ("false", "true"), "play-toggle needs aria-pressed")
        p.t("play-toggle").click()
        report.check(wait_for(p, lambda: not video_info(p, "before-video")["paused"] and not video_info(p, "after-video")["paused"], 5), "play-toggle must start both videos")
        report.check(attr(p, "play-toggle", "aria-pressed") == "true", "play-toggle must be aria-pressed while playing")
        p.page.wait_for_timeout(700)
        b_info, a_info = video_info(p, "before-video"), video_info(p, "after-video")
        report.check(b_info["t"] > 0.2 and abs(b_info["t"] - a_info["t"]) < 0.25, f"both videos must advance together (within 0.25 s); got {b_info['t']:.2f} vs {a_info['t']:.2f}")
        p.t("play-toggle").click()
        report.check(wait_for(p, lambda: video_info(p, "before-video")["paused"] and video_info(p, "after-video")["paused"], 5) and attr(p, "play-toggle", "aria-pressed") == "false", "a second click must pause both videos")
        set_range(p, "scrubber", 500)
        duration = video_info(p, "before-video")["d"]
        report.check(wait_for(p, lambda: abs(video_info(p, "before-video")["t"] - duration / 2) < 0.2 and abs(video_info(p, "after-video")["t"] - duration / 2) < 0.2, 5), f"the scrubber at 500 must put both videos at half the duration ({duration / 2:.2f} s); got {video_info(p, 'before-video')['t']:.2f} / {video_info(p, 'after-video')['t']:.2f}")
        shown = p.t("time-readout").inner_text().strip()
        report.check(re.fullmatch(r"\d+:\d\d / \d+:\d\d", shown) is not None, f"time-readout must read 'm:ss / m:ss'; got {shown!r}")
        p.t("player").focus()
        p.page.keyboard.press("Space")
        report.check(wait_for(p, lambda: not video_info(p, "before-video")["paused"], 3), "Space with the player focused must toggle playback")
        p.page.keyboard.press("Space")
        wait_for(p, lambda: video_info(p, "before-video")["paused"], 3)

        # ---- the compare slider: keys
        cs = p.t("compare-slider")
        report.check(cs.get_attribute("role") == "slider" and cs.get_attribute("aria-label") == "Before and after" and (cs.get_attribute("aria-valuemin"), cs.get_attribute("aria-valuemax"), cs.get_attribute("aria-valuenow")) == ("0", "100", "50"), "compare-slider needs role=slider, aria-label 'Before and after', min 0, max 100, now 50")
        cs.focus()
        p.page.keyboard.press("ArrowRight")
        report.check(cs.get_attribute("aria-valuenow") == "51", f"ArrowRight must add 1; got {cs.get_attribute('aria-valuenow')}")
        p.page.keyboard.press("Shift+ArrowLeft")
        report.check(cs.get_attribute("aria-valuenow") == "41", f"Shift+ArrowLeft must subtract 10; got {cs.get_attribute('aria-valuenow')}")
        p.page.keyboard.press("Home")
        report.check(cs.get_attribute("aria-valuenow") == "0", "Home must go to 0")
        p.page.keyboard.press("End")
        report.check(cs.get_attribute("aria-valuenow") == "100", "End must go to 100")
        for _ in range(3):
            p.page.keyboard.press("ArrowRight")
        report.check(cs.get_attribute("aria-valuenow") == "100", "the slider must stop at 100")

        # ---- what the slider really shows: 100 = all before (left of the divider), 0 = all after, 50 = halves
        box = p.t("player").bounding_box()
        p.page.keyboard.press("Home")
        all_after = shot_png(p)
        p.page.keyboard.press("End")
        all_before = shot_png(p)
        report.check(band_diff(all_after, all_before, 0.1, 0.9) > 4, "the before and after videos must look different (fixture: sharp vs soft); the pixel check needs that")
        for _ in range(50):
            p.page.keyboard.press("ArrowLeft")
        report.check(cs.get_attribute("aria-valuenow") == "50", "pressing ArrowLeft 50 times from 100 must give 50")
        half = shot_png(p)
        left_vs_before = band_diff(half, all_before, 0.05, 0.40)
        left_vs_after = band_diff(half, all_after, 0.05, 0.40)
        right_vs_before = band_diff(half, all_before, 0.60, 0.95)
        right_vs_after = band_diff(half, all_after, 0.60, 0.95)
        report.check(left_vs_before < left_vs_after and left_vs_before < 2, f"left of the divider must show the BEFORE video (diff to before {left_vs_before:.1f}, to after {left_vs_after:.1f})")
        report.check(right_vs_after < right_vs_before and right_vs_after < 2, f"right of the divider must show the AFTER video (diff to after {right_vs_after:.1f}, to before {right_vs_before:.1f})")

        # ---- the compare slider: mouse
        handle = p.t("compare-handle").bounding_box()
        box = p.t("player").bounding_box()
        p.page.mouse.move(handle["x"] + handle["width"] / 2, handle["y"] + handle["height"] / 2)
        p.page.mouse.down()
        p.page.mouse.move(box["x"] + box["width"] * 0.25, box["y"] + box["height"] / 2, steps=8)
        p.page.mouse.up()
        now = int(cs.get_attribute("aria-valuenow"))
        report.check(abs(now - 25) <= 3, f"dragging the handle to a quarter of the width must give about 25; got {now}")

        # ---- aperture control: initial state
        report.check(p.t("reapply-slider").input_value() == "2" and p.t("reapply-value").inner_text().strip() == "f/2.8", "reapply-slider must start at the shown version's aperture (f/2.8, index 2)")
        report.check(p.t("reapply-button").is_disabled() and p.t("reapply-button").inner_text().strip() == "Apply aperture", "Apply aperture must be disabled while the slider is at the shown version's aperture")
        report.check(p.t("reapply-status").inner_text().strip() == "Applied f/2.8", f"reapply-status must read 'Applied f/2.8'; got {p.t('reapply-status').inner_text()!r}")
        chips = p.t("version-chip")
        report.check(chips.count() == 1 and chips.first.get_attribute("data-aperture") == "2.8" and chips.first.get_attribute("aria-pressed") == "true" and chips.first.inner_text().strip() == "f/2.8", "one version chip 'f/2.8', pressed")
        set_range(p, "reapply-slider", 5)
        report.check(p.t("reapply-value").inner_text().strip() == "f/8" and p.t("reapply-button").is_enabled(), "moving the aperture slider to f/8 must show f/8 and enable Apply aperture")

        # ---- re-apply with the optics held: status, the player stays usable, nothing regenerates
        counts = {t: fake.count(t) for t in ("SamplerCustomAdvanced", "DA3Inference", "OpenOptics_DepthOfField")}
        fake.hold_at("OpenOptics_DepthOfField")
        p.t("reapply-button").click()
        report.check(wait_for(p, lambda: "Applying f/8" in p.t("reapply-status").inner_text(), 10), f"reapply-status must read 'Applying f/8 ...' while it runs; got {p.t('reapply-status').inner_text()!r}")
        report.check(p.t("reapply-button").is_disabled(), "Apply aperture must be disabled while a re-apply runs")
        report.check(attr(p, "viewport", "data-state") == "result" and p.t("player").is_visible(), "the player must stay visible during a re-apply")
        p.t("play-toggle").click()
        report.check(wait_for(p, lambda: not video_info(p, "before-video")["paused"], 3), "the player must stay playable during a re-apply")
        p.t("play-toggle").click()
        fake.release()
        report.check(wait_for(p, lambda: p.t("version-chip").count() == 2, 20), "a second version chip must appear after the re-apply")
        chips = p.t("version-chip")
        report.check(chips.nth(1).get_attribute("data-aperture") == "8" and chips.nth(1).get_attribute("aria-pressed") == "true" and chips.nth(0).get_attribute("aria-pressed") == "false", "the new f/8 version must be shown (aria-pressed) and the old one not")
        report.check(p.t("label-after").inner_text().strip() == "After f/8" and p.t("reapply-status").inner_text().strip() == "Applied f/8", f"labels after the re-apply wrong: {p.t('label-after').inner_text()!r} / {p.t('reapply-status').inner_text()!r}")
        report.check(p.t("reapply-button").is_disabled(), "Apply aperture must be disabled again when the slider equals the shown version")
        report.check(wait_for(p, lambda: video_info(p, "after-video")["src"].endswith("after_2.webm"), 10), f"after-video must now play version 2; got {video_info(p, 'after-video')['src']}")
        new_counts = {t: fake.count(t) for t in counts}
        report.check(new_counts["SamplerCustomAdvanced"] == counts["SamplerCustomAdvanced"] and new_counts["DA3Inference"] == counts["DA3Inference"] and new_counts["OpenOptics_DepthOfField"] == counts["OpenOptics_DepthOfField"] + 1,
                     f"the re-apply must run only Depth of Field in ComfyUI; counts before {counts} after {new_counts}")
        last = [e["inputs"] for e in fake.executed if e["class_type"] == "OpenOptics_DepthOfField"][-1]
        report.check(last.get("f_number") == 8, f"ComfyUI must receive f_number 8; got {last.get('f_number')}")

        # ---- versions
        chips.nth(0).click()
        report.check(wait_for(p, lambda: video_info(p, "after-video")["src"].endswith("after_1.webm"), 10), "clicking the first chip must show version 1 in after-video")
        report.check(p.t("reapply-slider").input_value() == "2" and p.t("label-after").inner_text().strip() == "After f/2.8" and p.t("version-chip").nth(0).get_attribute("aria-pressed") == "true", "clicking a chip must move the aperture slider and label to that version")
        report.check(p.t("reapply-button").is_disabled(), "Apply aperture is disabled at the shown version's aperture")

        # ---- a failing re-apply
        fake.fail("OpenOptics_DepthOfField", "Out of memory in Depth of Field")
        set_range(p, "reapply-slider", 7)
        p.t("reapply-button").click()
        report.check(wait_for(p, lambda: "Out of memory in Depth of Field" in p.t("reapply-status").inner_text(), 20), f"a failed re-apply must show ComfyUI's message in reapply-status; got {p.t('reapply-status').inner_text()!r}")
        report.check(attr(p, "viewport", "data-state") == "result" and p.t("version-chip").count() == 2 and p.t("player").is_visible(), "a failed re-apply must leave the shot and its versions as they were")
        fake.clear_failures()
        p.t("reapply-button").click()
        report.check(wait_for(p, lambda: p.t("version-chip").count() == 3, 20) and p.t("version-chip").nth(2).get_attribute("data-aperture") == "16", "retrying the re-apply must add the f/16 version")
        report.check(wait_for(p, lambda: p.t("reapply-status").inner_text().strip() == "Applied f/16", 5), "the status must read 'Applied f/16' after the retry")

        # ---- the shot survives a reload with its versions; history switches shots
        p.page.reload()
        report.check(wait_for(p, lambda: attr(p, "viewport", "data-state") == "result" and p.t("version-chip").count() in (1, 2, 3), 10), "after a reload a finished shot is shown")
        p.t("history-item").nth(0).click()
        report.check(wait_for(p, lambda: p.t("version-chip").count() == 1, 10), "the other shot (one version) must show one chip after selecting it in the history")
        report.check(wait_for(p, lambda: p.t("label-after").inner_text().strip() == "After f/5.6", 10), f"the other shot was made at f/5.6; label-after reads {p.t('label-after').inner_text()!r}")

        report.check(not p.errors, "console errors or failed requests:\n  " + "\n  ".join(p.errors[:8]))
        report.check(not p.foreign, f"the page must load nothing from other hosts: {p.foreign[:5]}")
        p.close()


try:
    run()
except Exception as exc:  # noqa: BLE001
    import traceback
    report.problems.append(f"the check itself stopped: {type(exc).__name__}: {exc}\n{traceback.format_exc()[-1500:]}")
report.finish()
