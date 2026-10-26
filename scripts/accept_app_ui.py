"""Goal check: the interface, form to generation to status. Run with: node scripts/run-py.js scripts/accept_app_ui.py

Opens the app in Chromium (Playwright) against the fake ComfyUI and clicks through docs/app-spec.md section 5: the controls,
the live subject distance, generating a shot with progress and stages, cancelling, failures, ComfyUI not running, reloading in the
middle of a run, and the history. Prints one line per problem and exits 1 if there is any.
"""
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _app_accept import Page, Report, browser, choose, make_shot_in_ui, protected_files_unchanged, set_range  # noqa: E402

report = Report("app interface")
protected_files_unchanged(report)
if report.problems:
    report.finish()

from tests.app_harness import AppHarness  # noqa: E402

DESC = "A woman in a red coat crosses a rainy street at night."


def visible(p, test_id):
    return p.t(test_id).count() > 0 and p.t(test_id).first.is_visible()


def state_of(p, test_id):
    loc = p.t(test_id)
    return loc.first.get_attribute("data-state") if loc.count() else None


def wait_state(p, test_id, want, timeout=30, attr="data-state"):
    """Wait until the element's attribute equals want (str or tuple of str). Returns the value or None on timeout."""
    wants = want if isinstance(want, tuple) else (want,)
    end = time.time() + timeout
    value = None
    while time.time() < end:
        loc = p.t(test_id)
        value = loc.first.get_attribute(attr) if loc.count() else None
        if value in wants:
            return value
        p.page.wait_for_timeout(60)
    return value


def checked_values(p, group):
    return p.t(group).locator('[role="radio"]').evaluate_all("els => els.map(e => [e.dataset.value, e.getAttribute('aria-checked')])")


def run():
    with AppHarness(delay=0.04) as h, browser() as b:
        fake = h.fake
        p = Page(b, h).open()

        # ---- the page and the header
        report.check("Open Cinema" in p.page.title(), f"the page <title> must contain 'Open Cinema'; got {p.page.title()!r}")
        report.check(p.page.locator("html").get_attribute("lang") == "en", "<html> needs lang='en'")
        report.check(wait_state(p, "comfy-status", "ok", 10) == "ok", f"comfy-status must turn 'ok' when ComfyUI answers; data-state is {state_of(p, 'comfy-status')!r}")
        text = p.t("comfy-status").inner_text()
        report.check("ComfyUI: connected" in text and "3090" in text, f"comfy-status text must say 'ComfyUI: connected' and name the device; got {text!r}")
        report.check(not visible(p, "comfy-banner"), "the ComfyUI banner must be hidden while ComfyUI is reachable")

        # ---- controls and their defaults
        for group, values, default in (("camera-group", ["static", "dolly-in", "dolly-out", "pan-left", "pan-right", "tilt-up", "orbit", "handheld"], "static"),
                                       ("lens-group", ["24", "35", "50", "85"], "50"),
                                       ("framing-group", ["close-up", "waist-up", "full-body", "wide"], "full-body")):
            got = checked_values(p, group)
            report.check([v for v, _ in got] == values, f"{group} must offer {values}; got {[v for v, _ in got]}")
            report.check([v for v, c in got if c == "true"] == [default], f"{group} must have exactly {default!r} checked by default; got {got}")
            report.check(p.t(group).get_attribute("role") == "radiogroup" and bool(p.t(group).get_attribute("aria-label") or p.t(group).get_attribute("aria-labelledby")), f"{group} needs role=radiogroup and an accessible name")
        report.check(p.t("lens-group").locator('[role="radio"][data-value="24"]').inner_text().replace(" ", " ").strip() == "24 mm", "the 24 lens button must be labelled '24 mm'")
        slider = p.t("aperture-slider")
        report.check((slider.get_attribute("min"), slider.get_attribute("max"), slider.get_attribute("step"), slider.input_value()) == ("0", "7", "1", "2"), "aperture-slider must be a range 0..7 step 1 starting at index 2 (f/2.8)")
        report.check(p.t("aperture-value").inner_text().strip() == "f/2.8" and slider.get_attribute("aria-valuetext") == "f/2.8", "the default aperture must read f/2.8")
        report.check(p.t("subject-distance").get_attribute("data-metres") is not None and abs(float(p.t("subject-distance").get_attribute("data-metres")) - 5.1005) < 6e-5, f"subject-distance data-metres must be 5.1005 for 50 mm full body; got {p.t('subject-distance').get_attribute('data-metres')}")
        report.check(p.t("subject-distance").inner_text().strip() == "Subject about 5.1 m", f"subject-distance text must be 'Subject about 5.1 m'; got {p.t('subject-distance').inner_text()!r}")
        hud = p.t("hud").inner_text()
        report.check(all(x in re.sub(r"\s+", " ", hud) for x in ("50 mm", "f/2.8", "5.1 m", "FULL BODY")), f"the HUD must show lens, aperture, distance and framing; got {hud!r}")
        report.check(state_of(p, "viewport") == "empty", f"viewport must start 'empty'; got {state_of(p, 'viewport')!r}")
        report.check(p.t("crop-mark").count() == 4, f"the viewport needs four crop-mark elements; found {p.t('crop-mark').count()}")
        report.check(p.t("generate-button").is_disabled() and p.t("generate-button").inner_text().strip() == "Generate shot", "Generate shot must be disabled while the description is empty")
        p.t("shot-description").fill("ab")
        report.check(p.t("generate-button").is_disabled(), "Generate shot must stay disabled for a description under 3 characters")
        p.t("shot-description").fill(DESC)
        report.check(p.t("generate-button").is_enabled(), "Generate shot must be enabled with a description")

        # ---- live subject distance and HUD follow the form
        for lens, framing, metres, shown in ((24, "wide", 5.9114, "5.9"), (85, "close-up", 2.6914, "2.7"), (35, "waist-up", 1.9132, "1.9"), (50, "wide", 12.3155, "12"), (24, "close-up", 0.7599, "0.8")):
            choose(p, "lens-group", lens)
            choose(p, "framing-group", framing)
            end = time.time() + 5
            while time.time() < end and abs(float(p.t("subject-distance").get_attribute("data-metres") or 0) - metres) > 6e-5:
                p.page.wait_for_timeout(50)
            report.check(abs(float(p.t("subject-distance").get_attribute("data-metres") or 0) - metres) < 6e-5, f"{lens} mm {framing}: data-metres must be {metres}; got {p.t('subject-distance').get_attribute('data-metres')}")
            report.check(p.t("subject-distance").inner_text().strip() == f"Subject about {shown} m", f"{lens} mm {framing}: text must be 'Subject about {shown} m'; got {p.t('subject-distance').inner_text()!r}")
            report.check(f"{lens} mm" in re.sub(r"\s+", " ", p.t("hud").inner_text()) and framing.replace("-", " ").upper() in re.sub(r"\s+", " ", p.t("hud").inner_text().replace("-", " ")), f"the HUD must follow the form; got {p.t('hud').inner_text()!r}")
        checked = checked_values(p, "lens-group")
        report.check([v for v, c in checked if c == "true"] == ["24"], f"after clicking 24 mm only it is checked; got {checked}")
        p.t("lens-group").locator('[role="radio"][aria-checked="true"]').focus()
        p.page.keyboard.press("ArrowRight")
        report.check([v for v, c in checked_values(p, "lens-group") if c == "true"] == ["35"], "ArrowRight must move the lens selection to the next option (35 mm)")
        set_range(p, "aperture-slider", 5)
        report.check(p.t("aperture-value").inner_text().strip() == "f/8" and "f/8" in re.sub(r"\s+", " ", p.t("hud").inner_text()), "moving the aperture slider to index 5 must show f/8 in the value and the HUD")
        set_range(p, "aperture-slider", 0)
        report.check(p.t("aperture-value").inner_text().strip() == "f/1.4", "aperture index 0 must read f/1.4")

        # ---- generate: working state, stages, progress, cancel
        fake.hold_at("SamplerCustomAdvanced")
        choose(p, "lens-group", 50)
        choose(p, "framing-group", "full-body")
        choose(p, "camera-group", "dolly-in")
        set_range(p, "aperture-slider", 2)
        p.t("generate-button").click()
        report.check(wait_state(p, "viewport", "working", 10) == "working", f"after Generate shot the viewport must be 'working'; got {state_of(p, 'viewport')!r}")
        report.check(wait_state(p, "status-panel", ("generating",), 15, "data-status") == "generating", f"the status panel must reach 'generating'; got {p.t('status-panel').first.get_attribute('data-status') if p.t('status-panel').count() else None!r}")
        report.check(visible(p, "status-panel") and bool(p.t("status-label").inner_text().strip()), "the status panel must be visible with a message")
        report.check(p.t("stage-generate").get_attribute("data-state") == "active" and p.t("stage-optics").get_attribute("data-state") == "pending", "stages must read generate active, optics pending")
        report.check(p.t("progress-bar").get_attribute("role") == "progressbar" and p.t("progress-bar").get_attribute("aria-valuenow") is not None, "progress-bar needs role=progressbar and aria-valuenow")
        report.check(re.fullmatch(r"\d+:\d\d", p.t("elapsed").inner_text().strip()) is not None, f"elapsed must read m:ss; got {p.t('elapsed').inner_text()!r}")
        report.check(p.t("generate-button").is_disabled(), "Generate shot must be disabled while a shot runs")
        report.check(visible(p, "record-dot"), "a record-dot must show while working")
        report.check(visible(p, "cancel-button"), "a Cancel button must show while a shot runs")
        report.check(p.t("shot-description").is_enabled(), "the form must stay editable while a shot runs")
        first_progress = int(p.t("progress-bar").get_attribute("aria-valuenow"))
        fake.release()
        seen = []
        end = time.time() + 60
        while time.time() < end:
            st = state_of(p, "viewport")
            if p.t("progress-bar").count() and p.t("progress-bar").first.is_visible():
                seen.append(int(p.t("progress-bar").first.get_attribute("aria-valuenow")))
            if st == "result":
                break
            p.page.wait_for_timeout(40)
        report.check(state_of(p, "viewport") == "result", f"the viewport must reach 'result' when the shot is done; it is {state_of(p, 'viewport')!r}")
        report.check(seen == sorted(seen) and (not seen or max(seen) > first_progress), f"the progress bar must only rise; saw {seen[:30]}")
        report.check(not visible(p, "status-panel"), "the status panel must be hidden in the result state")
        report.check(p.t("generate-button").is_enabled(), "Generate shot must be enabled again after the shot is done")
        report.check(p.t("history-item").count() == 1 and p.t("history-item").first.get_attribute("data-status") == "done", f"history must list the finished shot; got {p.t('history-item').count()} items")
        sent = fake.prompts[0]
        texts = [n["inputs"].get("text") for n in sent.values() if n["class_type"] == "CLIPTextEncode"]
        report.check(len(texts) == 1 and DESC in texts[0] and "Slow dolly-in toward the subject" in texts[0] and "Full-body shot" in texts[0] and "50 mm lens look" in texts[0], f"ComfyUI must receive the prompt built from the form; got {texts}")

        # ---- history: new shot, select the old one again
        p.t("history-new").click()
        report.check(state_of(p, "viewport") == "empty", "New shot must return the viewport to 'empty'")
        report.check(p.t("history-item").count() == 1, "New shot must keep the history")
        p.t("history-item").first.click()
        report.check(wait_state(p, "viewport", "result", 10) == "result", "clicking a finished history item must show it ('result')")

        # ---- keyboard: Ctrl+Enter generates; cancel a running shot
        p.t("history-new").click()
        fake.hold_at("SamplerCustomAdvanced")
        p.t("shot-description").fill("Second shot, started with the keyboard.")
        p.t("shot-description").press("Control+Enter")
        report.check(wait_state(p, "status-panel", ("generating",), 15, "data-status") == "generating", "Ctrl+Enter in the description must start a shot")
        p.t("cancel-button").click()
        report.check(wait_state(p, "viewport", "cancelled", 15) == "cancelled", f"Cancel must leave the viewport 'cancelled'; got {state_of(p, 'viewport')!r}")
        report.check(p.t("status-label").inner_text().strip() == "Cancelled." and p.t("retry-button").inner_text().strip() == "Try again", "a cancelled shot shows 'Cancelled.' and a 'Try again' button")
        fake.release()
        report.check(p.t("generate-button").is_enabled(), "Generate shot must be enabled after a cancel")

        # ---- a failure in the optics stage, and Retry optics
        fake.reset_cache()  # identical fixture videos: without this ComfyUI serves Depth of Field from its cache
        fake.fail("OpenOptics_DepthOfField", "Out of memory in Depth of Field")
        p.t("history-new").click()
        p.t("shot-description").fill("This one fails in the optics stage.")
        p.t("generate-button").click()
        report.check(wait_state(p, "viewport", "failed", 40) == "failed", f"a failing shot must leave the viewport 'failed'; got {state_of(p, 'viewport')!r}")
        err = p.t("error-message")
        report.check(err.count() == 1 and err.get_attribute("role") == "alert" and "Out of memory in Depth of Field" in err.inner_text() and "OpenOptics_DepthOfField" in err.inner_text(), f"error-message must show ComfyUI's text and the node; got {err.inner_text() if err.count() else None!r}")
        report.check(p.t("stage-generate").get_attribute("data-state") == "done" and p.t("stage-optics").get_attribute("data-state") == "failed", "stages must read generate done, optics failed")
        report.check(p.t("retry-button").inner_text().strip() == "Retry optics", "a failed optics stage offers 'Retry optics'")
        fake.clear_failures()
        runs_before = fake.count("SamplerCustomAdvanced")
        p.t("retry-button").click()
        report.check(wait_state(p, "viewport", "result", 40) == "result", "Retry optics must lead to a finished shot")
        report.check(fake.count("SamplerCustomAdvanced") == runs_before, "Retry optics must not generate the video again")

        # ---- a failure in generation: Try again submits a new shot
        fake.fail("SamplerCustomAdvanced", "The sampler exploded")
        p.t("history-new").click()
        p.t("shot-description").fill("This one fails while generating.")
        p.t("generate-button").click()
        report.check(wait_state(p, "viewport", "failed", 40) == "failed" and "The sampler exploded" in p.t("error-message").inner_text(), "a generation failure must show ComfyUI's text in the error message")
        report.check(p.t("retry-button").inner_text().strip() == "Try again", "a failed generation offers 'Try again'")
        fake.clear_failures()
        count_before = p.t("history-item").count()
        p.t("retry-button").click()
        report.check(wait_state(p, "viewport", "result", 60) == "result", "Try again must lead to a finished shot")
        report.check(p.t("history-item").count() == count_before + 1, "Try again must add a new shot to the history")

        # ---- reload in the middle of a run
        fake.hold_at("SamplerCustomAdvanced")
        p.t("history-new").click()
        p.t("shot-description").fill("The page is reloaded while this one runs.")
        p.t("generate-button").click()
        wait_state(p, "status-panel", ("generating",), 15, "data-status")
        p.page.reload()
        report.check(wait_state(p, "viewport", "working", 10) == "working", "after a reload the running shot must be shown again ('working')")
        report.check(wait_state(p, "status-panel", ("generating",), 10, "data-status") == "generating", "after a reload the shot must be followed live")
        fake.release()
        report.check(wait_state(p, "viewport", "result", 60) == "result", "the shot followed after a reload must finish")
        p.page.reload()
        report.check(wait_state(p, "viewport", "result", 10) == "result", "after a reload the latest shot must be shown")

        # ---- ComfyUI is not running
        fake.stop()
        p.t("history-new").click()
        p.t("shot-description").fill("ComfyUI was closed before this one.")
        p.page.evaluate("window.dispatchEvent(new Event('focus'))")
        report.check(wait_state(p, "comfy-status", "down", 10) == "down", "window focus must re-check ComfyUI; comfy-status must turn 'down'")
        banner = p.t("comfy-banner")
        report.check(banner.count() == 1 and banner.is_visible() and banner.get_attribute("role") == "alert" and f"Can't reach ComfyUI at {fake.url}" in banner.inner_text(), f"the banner must show the server's message with the ComfyUI address; got {banner.inner_text() if banner.count() else None!r}")
        report.check("ComfyUI: offline" in p.t("comfy-status").inner_text(), "comfy-status must read 'ComfyUI: offline'")
        report.check(p.t("generate-button").is_disabled(), "Generate shot must be disabled while ComfyUI is down")
        fake.start()
        p.t("comfy-retry").click()
        report.check(wait_state(p, "comfy-status", "ok", 10) == "ok" and not visible(p, "comfy-banner"), "Retry must clear the banner when ComfyUI is back")
        report.check(p.t("generate-button").is_enabled(), "Generate shot must be enabled again when ComfyUI is back")
        # the UI has not noticed yet when the submit fails: the server's 503 must show the banner
        fake.stop()
        p.t("generate-button").click()
        report.check(wait_state(p, "comfy-status", "down", 10) == "down" and visible(p, "comfy-banner"), "a submit that fails because ComfyUI is gone must turn the header 'down' and show the banner")
        fake.start()
        p.t("comfy-retry").click()
        wait_state(p, "comfy-status", "ok", 10)
        p.t("generate-button").click()
        report.check(wait_state(p, "viewport", "result", 60) == "result", "generating must work again once ComfyUI is back")

        # ---- the page stayed clean
        report.check(not p.errors, "console errors or failed requests:\n  " + "\n  ".join(p.errors[:8]))
        report.check(not p.foreign, f"the page must load nothing from other hosts: {p.foreign[:5]}")
        p.close()


try:
    run()
except Exception as exc:  # noqa: BLE001
    import traceback
    report.problems.append(f"the check itself stopped: {type(exc).__name__}: {exc}\n{traceback.format_exc()[-1500:]}")
report.finish()
