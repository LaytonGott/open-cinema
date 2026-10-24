"""Take screenshots of the director app (empty and form states) at two viewport sizes.

Usage: python scripts/app_screenshots.py [--out DIR]   (default: app/screenshots under the repo root)
"""
import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from tests.app_harness import SHOT, AppHarness  # noqa: E402

SIZES = [(1280, 720), (1366, 768)]
SENTENCE = "A woman in a red coat crosses a rainy street at night."


def shoot_size(h, browser, fake, w, ht, out):
    """Write empty-WxH.png and form-WxH.png (viewport only) for a viewport of w x ht pixels into the folder `out`."""
    context = browser.new_context(viewport={"width": w, "height": ht})
    try:
        page = context.new_page()
        page.set_default_timeout(15000)
        page.goto(h.url + "/")
        page.get_by_test_id("history-new").click()
        page.screenshot(path=str(Path(out) / f"empty-{w}x{ht}.png"))
        page.get_by_test_id("shot-description").fill(SENTENCE)
        page.screenshot(path=str(Path(out) / f"form-{w}x{ht}.png"))
        fake.reset_cache()  # identical fixture videos: without this ComfyUI serves the nodes from its cache
        fake.hold_at("SamplerCustomAdvanced")
        page.get_by_test_id("generate-button").click()
        page.wait_for_selector('[data-testid="status-panel"][data-status="generating"]', timeout=15000)
        page.screenshot(path=str(Path(out) / f"working-{w}x{ht}.png"))
        fake.release()
        page.wait_for_selector('[data-testid="viewport"][data-state="result"]', timeout=40000)
        page.wait_for_timeout(300)
        page.screenshot(path=str(Path(out) / f"result-{w}x{ht}.png"))
        fake.reset_cache()
        fake.fail("OpenOptics_DepthOfField", "Out of memory in Depth of Field")
        try:
            page.get_by_test_id("history-new").click()
            page.get_by_test_id("shot-description").fill(SENTENCE)
            page.get_by_test_id("generate-button").click()
            page.wait_for_selector('[data-testid="viewport"][data-state="failed"]', timeout=40000)
            page.screenshot(path=str(Path(out) / f"failed-{w}x{ht}.png"))
        finally:
            fake.clear_failures()
    finally:
        context.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", default=str(ROOT / "app" / "screenshots"))
    args = parser.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    from playwright.sync_api import sync_playwright
    with AppHarness() as h:
        status, rec = h.post("/api/shots", {**SHOT, "description": "An earlier shot for the history strip.", "seed": 3})
        h.wait_for_shot(rec["id"], "done")
        with sync_playwright() as pw:
            browser = pw.chromium.launch()
            try:
                for w, ht in SIZES:
                    shoot_size(h, browser, getattr(h, "fake", None), w, ht, out)
            finally:
                browser.close()


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # noqa: BLE001
        print(f"app_screenshots: {exc}", file=sys.stderr)
        sys.exit(1)
    sys.exit(0)
