"""Goal check: the whole app end to end, and how to run it. Run with: node scripts/run-py.js scripts/accept_app_flow.py

Walks the complete flow a director follows in Chromium (Playwright) against the fake ComfyUI, from a cold start with ComfyUI
not running to a shot with two apertures compared, and checks that the README tells how to start the app with a real ComfyUI,
that `npm run app` works, that the app talks to ComfyUI only through the Comfy SDK, and that the dependencies are listed.
Prints one line per problem and exits 1 if there is any.
"""
import json
import re
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _app_accept import ROOT, Page, Report, browser, choose, protected_files_unchanged, set_range  # noqa: E402

report = Report("app end to end")
protected_files_unchanged(report)
if report.problems:
    report.finish()

from tests.app_harness import AppHarness  # noqa: E402
from tests.fake_comfy import FakeComfy  # noqa: E402

# ---------------------------------------------------------------- how to run it
readme = (ROOT / "README.md").read_text(encoding="utf-8")
match = re.search(r"^(#{2,3})\s+[^\n]*Run the director app[^\n]*\n(.*?)(?=^#{1,%d}\s|\Z)" % 3, readme, re.M | re.S)
if not match:
    report.problems.append("README.md needs a heading (## or ###) containing 'Run the director app'")
else:
    section = match.group(2)
    for needle in ("python -m app", "--comfyui", "http://127.0.0.1:8000", "run_nvidia_gpu.bat", "custom_nodes", "ComfyUI-GGUF", "pip install", "comfy-sdk", "comfy-api-proxy",
                   "npm run app", "playwright install chromium", "npm test",
                   "ltx-2-19b-distilled_Q4_K_M.gguf", "gemma_3_12B_it_fp8_scaled.safetensors", "ltx-2-19b-embeddings_connector_distill_bf16.safetensors",
                   "LTX2_video_vae_bf16.safetensors", "LTX2_audio_vae_bf16.safetensors", "ltx-2-spatial-upscaler-x2-1.0.safetensors", "depth_anything_3_mono_large.safetensors",
                   "models", "diffusion_models", "text_encoders", "latent_upscale_models", "geometry_estimation"):
        report.check(needle in section, f"the README section 'Run the director app' must mention {needle!r}")
    report.check(len(re.findall(r"^\s*[1-9]\.\s", section, re.M)) >= 5, "the README section must give numbered steps (at least 5)")
    report.check(re.search(r"```(bash|powershell|bat|cmd|sh)?\n[^`]*python -m app[^`]*```", section) is not None, "the README section must show the start command in a code block")
    report.check("TODO" not in section and "XXX" not in section, "the README section must be finished (no TODO)")
    for needle in ("isn't running", "Retry"):
        report.check(needle in section, f"the README section must explain what the app shows when ComfyUI is not running ({needle!r})")

package = json.loads((ROOT / "package.json").read_text(encoding="utf-8"))
report.check("app" in package.get("scripts", {}), "package.json needs an 'app' script (npm run app)")
run_help = subprocess.run(["node", str(ROOT / "scripts" / "run-app.js"), "--help"], cwd=str(ROOT), capture_output=True, text=True, timeout=60)
report.check(run_help.returncode == 0 and "--comfyui" in run_help.stdout, f"`node scripts/run-app.js --help` must exit 0 and list --comfyui; got {run_help.returncode}: {(run_help.stdout + run_help.stderr)[-300:]}")
for name in ("app/requirements.txt", "requirements-test.txt"):
    path = ROOT / name
    report.check(path.exists(), f"{name} is missing")
    if path.exists():
        text = path.read_text(encoding="utf-8").lower()
        wanted = ("comfy-sdk", "comfy-api-proxy") if name.startswith("app") else ("playwright", "pillow", "numpy")
        for w in wanted:
            report.check(w in text, f"{name} must list {w}")
gitignore = (ROOT / ".gitignore").read_text(encoding="utf-8")
report.check("app/data" in gitignore and "app/screenshots" in gitignore, ".gitignore must list app/data and app/screenshots")

# ---------------------------------------------------------------- only the Comfy SDK talks to ComfyUI
app_sources = {p: p.read_text(encoding="utf-8") for p in (ROOT / "app").rglob("*.py")}
all_text = "\n".join(app_sources.values())
report.check("comfy_sdk" in all_text, "the app must use the Comfy SDK (import comfy_sdk)")
report.check("comfy_api_proxy" in all_text, "the app must start comfy-api-proxy (import comfy_api_proxy)")
report.check(not re.search(r"""["'](/prompt|/history|/upload/image|/ws|/view)["'?/]""", all_text), "the app must not call ComfyUI's own /prompt, /history, /upload, /ws or /view endpoints; use the Comfy SDK")
report.check(len([p for p in (ROOT / "tests").glob("test_app_*.py")]) >= 4, "tests/ needs at least four app test files (test_app_*.py): shot, graphs, backend, interface")


def wait_attr(p, test_id, name, want, timeout=40):
    wants = want if isinstance(want, tuple) else (want,)
    end = time.time() + timeout
    value = None
    while time.time() < end:
        loc = p.t(test_id)
        value = loc.first.get_attribute(name) if loc.count() else None
        if value in wants:
            return value
        p.page.wait_for_timeout(60)
    return value


def attr_is(p, test_id, name, want):
    loc = p.t(test_id)
    return loc.count() > 0 and loc.first.get_attribute(name) == want


def run():
    # ---- cold start with ComfyUI not running: the fake owns a port but is not serving
    fake2 = FakeComfy(delay=0.03)
    fake2.start()
    port = fake2._port
    fake2.stop()
    h = AppHarness(fake=fake2)
    try:
        h.start_app()
        line = h.log()
        report.check(f"Open Cinema is running at http://127.0.0.1:{h.port} (ComfyUI at http://127.0.0.1:{port})" in line, f"the app must print 'Open Cinema is running at http://HOST:PORT (ComfyUI at URL)' even when ComfyUI is down; log:\n{line[-400:]}")
        with browser() as b:
            p = Page(b, h, 1366, 768).open()
            report.check(wait_attr(p, "comfy-status", "data-state", "down", 10) == "down", "with ComfyUI not running the header must read 'down'")
            banner = p.t("comfy-banner")
            report.check(banner.count() == 1 and banner.is_visible() and f"Can't reach ComfyUI at http://127.0.0.1:{port}" in banner.inner_text(), f"the banner must tell where ComfyUI was expected; got {banner.inner_text() if banner.count() else None!r}")
            p.t("shot-description").fill("A lighthouse keeper climbs the stairs at dawn.")
            report.check(p.t("generate-button").is_disabled(), "Generate shot must be disabled while ComfyUI is down")
            fake2.start()
            p.t("comfy-retry").click()
            report.check(wait_attr(p, "comfy-status", "data-state", "ok", 10) == "ok", "Retry must reconnect once ComfyUI is started")
            report.check(p.t("comfy-banner").count() == 0 or not p.t("comfy-banner").first.is_visible(), "the banner must disappear once ComfyUI is reachable")

            # ---- the director's flow, with the mouse
            choose(p, "camera-group", "orbit")
            choose(p, "lens-group", 35)
            choose(p, "framing-group", "waist-up")
            set_range(p, "aperture-slider", 3)  # f/4
            hud = re.sub(r"\s+", " ", p.t("hud").inner_text())
            report.check("35 mm" in hud and "f/4" in hud and "1.9 m" in hud and "WAIST UP" in hud.replace("-", " "), f"the HUD must show the chosen look; got {hud!r}")
            p.t("generate-button").click()
            report.check(wait_attr(p, "viewport", "data-state", "result", 90) == "result", "the shot must finish ('result')")
            gen = fake2.prompts[0]
            text = [n["inputs"]["text"] for n in gen.values() if n["class_type"] == "CLIPTextEncode"][0]
            for part in ("Waist-up medium shot", "A lighthouse keeper climbs the stairs at dawn.", "The camera orbits slowly around the subject", "35 mm lens look"):
                report.check(part in text, f"the prompt sent to ComfyUI must contain {part!r}; got {text!r}")
            d2m = [e["inputs"] for e in fake2.executed if e["class_type"] == "OpenOptics_DepthToMetric"][-1]
            dof = [e["inputs"] for e in fake2.executed if e["class_type"] == "OpenOptics_DepthOfField"][-1]
            report.check(d2m["mode"] == "subject" and abs(d2m["subject_m"] - 1.9132) < 6e-5, f"DepthToMetric must anchor at the framing distance 1.9132 m (35 mm, waist-up); got {d2m}")
            report.check(dof["focal_mm"] == 35 and dof["f_number"] == 4 and abs(dof["focus_m"] - 1.9132) < 6e-5, f"Depth of Field must get 35 mm, f/4, focus 1.9132 m; got {dof}")
            report.check(p.t("label-after").inner_text().strip() == "After f/4", "the player must label the result 'After f/4'")

            # ---- compare apertures without regenerating
            gen_runs = fake2.count("SamplerCustomAdvanced")
            set_range(p, "reapply-slider", 0)
            p.t("reapply-button").click()
            end = time.time() + 40
            while time.time() < end and p.t("version-chip").count() < 2:
                p.page.wait_for_timeout(80)
            report.check(p.t("version-chip").count() == 2 and p.t("version-chip").nth(1).get_attribute("data-aperture") == "1.4", "applying f/1.4 must add a second version chip")
            report.check(fake2.count("SamplerCustomAdvanced") == gen_runs, "changing the aperture must not regenerate the video")
            p.t("compare-slider").focus()
            p.page.keyboard.press("Home")
            report.check(p.t("compare-slider").get_attribute("aria-valuenow") == "0", "the compare slider must move with the keyboard")
            p.t("version-chip").nth(0).click()
            report.check(p.t("label-after").inner_text().strip() == "After f/4", "choosing the first version shows 'After f/4' again")

            # ---- reload, second shot with the keyboard only, history
            p.page.reload()
            report.check(wait_attr(p, "viewport", "data-state", "result", 10) == "result" and p.t("version-chip").count() == 2, "after a reload the shot and both versions are back")
            p.t("history-new").click()
            p.t("shot-description").fill("A cat watches rain on a window sill.")
            choose(p, "framing-group", "close-up")
            p.t("shot-description").press("Control+Enter")
            report.check(wait_attr(p, "viewport", "data-state", "result", 90) == "result", "the second shot (started with Ctrl+Enter) must finish")
            report.check(p.t("history-item").count() == 2, f"history must list both shots; found {p.t('history-item').count()}")
            items = p.t("history-item")
            report.check("cat" in items.nth(0).inner_text().lower() and "lighthouse" in items.nth(1).inner_text().lower(), "history must list the newest shot first with the start of its description")
            items.nth(1).click()
            p.page.wait_for_timeout(300)
            report.check(p.t("version-chip").count() == 2 and attr_is(p, "viewport", "data-state", "result"), "selecting the older shot shows its two versions")
            report.check(not p.errors, "console errors or failed requests:\n  " + "\n  ".join(p.errors[:6]))
            report.check(not p.foreign, f"the page must load nothing from other hosts: {p.foreign[:4]}")
            p.close()
    finally:
        h.stop()
        fake2.close()


try:
    run()
except Exception as exc:  # noqa: BLE001
    import traceback
    report.problems.append(f"the check itself stopped: {type(exc).__name__}: {exc}\n{traceback.format_exc()[-1500:]}")
report.finish()
