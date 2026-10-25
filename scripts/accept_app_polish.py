"""Goal check: the interface behaves and looks right for a person using it. Run with: node scripts/run-py.js scripts/accept_app_polish.py

Opens the app in Chromium (Playwright) against the fake ComfyUI behaving like a real one (ws progress_state frames) and checks the
things a person notices that the earlier checks did not: the selected camera, lens and framing are visible, the controls keep
keyboard focus and are not rebuilt while a shot runs, a failed lookup does not freeze the running shot, the monitor is never
clipped, the HUD reads as docs/app-spec.md says, Retry cannot start two shots, long messages do not overflow, a cancelled shot has
no active stage, and a re-apply shows its own progress. Prints one line per problem and exits 1 if there is any.
"""
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _app_accept import ROOT, Page, Report, browser, choose, protected_files_unchanged, set_range  # noqa: E402

report = Report("app polish")
protected_files_unchanged(report)
if report.problems:
    report.finish()

from tests.app_harness import SHOT, AppHarness  # noqa: E402

DESC = "A rider crosses a foggy salt flat at dawn, the horse breathing steam."
ACCENT = "rgb(245, 165, 36)"


def wait(p, predicate, timeout=20):
    end = time.time() + timeout
    while time.time() < end:
        try:
            if predicate():
                return True
        except Exception:  # noqa: BLE001
            pass
        p.page.wait_for_timeout(80)
    return False


def attr(p, test_id, name):
    loc = p.t(test_id)
    return loc.first.get_attribute(name) if loc.count() else None


def norm(text):
    return re.sub(r"\s+", " ", text or "").strip()


def run():
    with AppHarness(delay=0.05) as h, browser() as b:
        fake = h.fake
        fake.real_progress = True
        status, rec = h.post("/api/shots", {**SHOT, "description": "An earlier shot, finished, for the history strip.", "seed": 21})
        done_id = rec["id"]
        h.wait_for_shot(done_id, "done", timeout=90)
        h.post(f"/api/shots/{done_id}/reapply", {"aperture": 8})
        h.wait_for_shot(done_id, "done", timeout=60)
        p = Page(b, h, 1280, 720).open()
        wait(p, lambda: attr(p, "viewport", "data-state") == "result")

        # ---- source checks
        sync_js = ROOT / "app" / "static" / "js"
        sources = {f.name: f.read_text(encoding="utf-8") for f in sync_js.rglob("*.js")}
        sync_src = next((t for n, t in sources.items() if n == "sync.js"), "")
        report.check("seeking" in sync_src, "the video sync must not issue a new seek while the follower is still seeking (check `.seeking` in sync.js): on H.264 files with sparse keyframes it would seek in a loop")
        player_src = sources.get("player.js", "")
        report.check("removeAttribute(\"src\")" in player_src.replace("'", '"') and ".load()" in player_src, "player.js must release the media of videos it replaces or hides (pause, removeAttribute('src'), load())")

        # ---- the page asks for dark scrollbars and controls
        report.check("dark" in p.page.evaluate("() => getComputedStyle(document.documentElement).colorScheme"), "the page must set color-scheme: dark on :root (light scrollbars and form controls otherwise)")
        report.check(p.page.evaluate("() => getComputedStyle(document.querySelector('button')).fontFamily") == p.page.evaluate("() => getComputedStyle(document.body).fontFamily"), "buttons and the textarea must use the page font (font: inherit)")

        # ---- the selected option is visible in every group
        for group in ("camera-group", "lens-group", "framing-group"):
            info = p.t(group).evaluate("""g => { const r = [...g.querySelectorAll('[role=radio]')]; const on = r.find(e => e.getAttribute('aria-checked') === 'true'); const off = r.find(e => e.getAttribute('aria-checked') !== 'true');
                const s = e => { const c = getComputedStyle(e); return [c.borderTopColor, c.backgroundColor, c.color]; }; return {on: s(on), off: s(off)}; }""")
            report.check(info["on"] != info["off"] and (group == "lens-group" or info["on"][0] == ACCENT),
                         f"{group}: the selected option must look different from the others (camera and framing: an accent border, #f5a524); selected {info['on']} others {info['off']}")

        # ---- the HUD follows the form and reads like the spec
        p.t("history-new").click()
        p.page.wait_for_timeout(200)
        report.check(norm(p.t("hud").inner_text()) == "50 mm f/2.8 5.1 m FULL BODY", f"the HUD while editing must read '50 mm  f/2.8  5.1 m  FULL BODY'; got {norm(p.t('hud').inner_text())!r}")
        choose(p, "lens-group", 24)
        choose(p, "framing-group", "wide")
        wait(p, lambda: "5.9" in (attr(p, "subject-distance", "data-metres") or ""))
        report.check(norm(p.t("hud").inner_text()) == "24 mm f/2.8 5.9 m WIDE", f"the HUD must follow the form; got {norm(p.t('hud').inner_text())!r}")
        choose(p, "lens-group", 50)
        choose(p, "framing-group", "full-body")

        # ---- a running shot: nothing the user is touching is rebuilt, the dot and the brief are in the right places
        fake.reset_cache()
        fake.hold_at("SamplerCustomAdvanced")
        p.t("shot-description").fill(DESC)
        p.t("generate-button").click()
        wait(p, lambda: attr(p, "status-panel", "data-status") == "generating")
        report.check(p.t("viewport").locator("[data-testid=record-dot]").count() == 1, "the record-dot must be inside the viewport while a shot runs")
        report.check(DESC in norm(p.t("shot-brief").inner_text()) if p.t("shot-brief").count() else False, f"a shot-brief element must show the full description of the shown shot; got {norm(p.t('shot-brief').inner_text()) if p.t('shot-brief').count() else None!r}")
        report.check(attr(p, "status-label", "role") == "status", "status-label needs role=status so changes are announced")
        p.page.evaluate("""() => { const lens = document.querySelector('[data-testid=lens-group] [role=radio][data-value="35"]'); lens.focus(); window.__lens = lens;
            window.__old = document.querySelector('[data-testid=history-item][data-status=done]'); }""")
        p.page.wait_for_timeout(3000)  # several progress frames and history refreshes arrive meanwhile
        same = p.page.evaluate("() => ({focus: document.activeElement === window.__lens, lens: document.body.contains(window.__lens), old: window.__old && document.body.contains(window.__old)})")
        report.check(same["lens"] and same["focus"], f"a lens button the user focused must stay the same element with the focus while a shot runs; got {same}")
        report.check(same["old"], "history items of other shots must not be rebuilt while a shot runs")

        # ---- a failed lookup must not freeze the running shot
        p.page.route(f"**/api/shots/{done_id}", lambda route: route.abort("aborted"))
        p.page.evaluate(f"() => document.querySelector('[data-testid=history-item][data-shot-id=\"{done_id}\"]').click()")
        p.page.wait_for_timeout(800)
        p.page.unroute(f"**/api/shots/{done_id}")
        fake.release()
        report.check(wait(p, lambda: attr(p, "viewport", "data-state") == "result", 60), f"after a failed lookup of another shot the running shot must still be followed to its end; the viewport is {attr(p, 'viewport', 'data-state')!r}")

        # ---- the compare slider speaks plainly
        report.check(attr(p, "compare-slider", "aria-valuetext") == "50% before / 50% after", f"compare-slider aria-valuetext must read '50% before / 50% after'; got {attr(p, 'compare-slider', 'aria-valuetext')!r}")

        # ---- a re-apply has its own progress
        p.page.reload()
        wait(p, lambda: attr(p, "viewport", "data-state") == "result" and p.t("reapply-slider").count() > 0, 20)
        fake.hold_at("OpenOptics_DepthOfField")
        set_range(p, "reapply-slider", 5)
        p.t("reapply-button").click()
        wait(p, lambda: "Applying" in (p.t("reapply-status").inner_text() or ""))
        p.page.wait_for_timeout(1500)
        value = int(attr(p, "progress-bar", "aria-valuenow") or 100)
        report.check(value < 95, f"during a re-apply the progress bar must show the re-apply's progress (below 95), not the finished shot's 100; got {value}")
        fake.release()
        wait(p, lambda: p.t("version-chip").count() >= 2 and "Applied" in p.t("reapply-status").inner_text(), 40)

        # ---- cancel leaves no active stage
        fake.reset_cache()
        fake.hold_at("SamplerCustomAdvanced")
        p.t("history-new").click()
        p.t("shot-description").fill("A shot that will be cancelled.")
        p.t("generate-button").click()
        wait(p, lambda: attr(p, "status-panel", "data-status") == "generating")
        p.t("cancel-button").click()
        wait(p, lambda: attr(p, "viewport", "data-state") == "cancelled")
        fake.release()
        states = [attr(p, "stage-generate", "data-state"), attr(p, "stage-optics", "data-state")]
        report.check("active" not in states, f"a cancelled shot must have no active stage; got {states}")

        # ---- a failed generation: long messages stay inside, and Try again starts exactly one shot even when double-clicked
        fake.reset_cache()
        fake.fail("SamplerCustomAdvanced", "CUDA out of memory at C:\\Users\\97lay\\Desktop\\OpenCinema\\ComfyUI_windows_portable\\ComfyUI\\comfy\\ldm\\modules\\diffusionmodules\\openaimodel.py_" + "x" * 200)
        p.t("history-new").click()
        p.t("shot-description").fill("A shot that fails in generation.")
        p.t("generate-button").click()
        wait(p, lambda: attr(p, "viewport", "data-state") == "failed", 40)
        overflow = p.page.evaluate("() => ['error-message', 'status-panel'].map(t => { const e = document.querySelector('[data-testid=' + t + ']'); return e ? e.scrollWidth - e.clientWidth : 0; })")
        report.check(all(x <= 1 for x in overflow), f"a long error message must wrap inside the status panel (overflow-wrap); horizontal overflow {overflow}")
        fake.clear_failures()
        count = len(h.get("/api/shots")[1]["shots"])
        p.t("retry-button").dblclick()
        p.page.wait_for_timeout(2500)
        now = len(h.get("/api/shots")[1]["shots"])
        report.check(now == count + 1, f"double-clicking Try again must start exactly one shot; shots went from {count} to {now}")
        wait(p, lambda: attr(p, "viewport", "data-state") == "result", 90)

        # ---- the monitor is never clipped, with the offline banner and several versions
        fake.stop()
        p.page.evaluate("window.dispatchEvent(new Event('focus'))")
        wait(p, lambda: p.t("comfy-banner").count() > 0 and p.t("comfy-banner").is_visible(), 10)
        p.page.wait_for_timeout(300)
        boxes = p.t("crop-mark").evaluate_all("els => els.map(e => { const b = e.getBoundingClientRect(); return [b.x, b.y, b.right, b.bottom]; })")
        win = p.page.evaluate("() => [innerWidth, innerHeight]")
        inside = all(x >= 0 and y >= 0 and r <= win[0] and bt <= win[1] for x, y, r, bt in boxes)
        report.check(len(boxes) == 4 and inside, f"all four crop marks must be fully on screen at 1280x720 with the offline banner showing; boxes {boxes} window {win}")
        gen = p.t("generate-button").bounding_box()
        report.check(gen and gen["y"] + gen["height"] <= win[1], "the Generate button must stay on screen with the banner showing")
        fake.start()

        report.check(not p.errors, "console errors or failed requests:\n  " + "\n  ".join(p.errors[:8]))
        p.close()


try:
    run()
except Exception as exc:  # noqa: BLE001
    import traceback
    report.problems.append(f"the check itself stopped: {type(exc).__name__}: {exc}\n{traceback.format_exc()[-1500:]}")
report.finish()
