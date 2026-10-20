"""Goal check: design, layout at laptop sizes and accessibility. Run with: node scripts/run-py.js scripts/accept_app_design.py

Opens the app in Chromium (Playwright) in every state (empty, filled form, working, result, failed, ComfyUI down) at 1280x720,
1366x768, 1440x900 and 1536x864 and checks docs/app-spec.md section 5.3: no page scrolling, key controls on screen, the colour
tokens, text contrast, fonts, focus rings and tab order, accessible names, reduced motion, nothing loaded from other hosts, no
console errors; then narrow widths (no horizontal scroll) and scripts/app_screenshots.py (writes PNGs for review).
Prints one line per problem and exits 1 if there is any.
"""
import io
import subprocess
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _app_accept import ROOT, VIEWPORTS, Page, Report, browser, protected_files_unchanged  # noqa: E402

report = Report("app design")
protected_files_unchanged(report)
if report.problems:
    report.finish()

import numpy as np  # noqa: E402
from PIL import Image  # noqa: E402

from tests.app_harness import SHOT, AppHarness  # noqa: E402

TOKENS = {"--bg": "#0b0c0e", "--surface": "#14161a", "--raised": "#1b1e24", "--line": "#262a31", "--text": "#e9e6df", "--muted": "#9097a2", "--accent": "#f5a524", "--ok": "#5ad19a", "--danger": "#ff6b6b"}

JS_LAYOUT = """() => {
  const r = id => { const e = document.querySelector(`[data-testid="${id}"]`); if (!e) return null; const b = e.getBoundingClientRect(); const s = getComputedStyle(e);
    return {x: b.x, y: b.y, w: b.width, h: b.height, bottom: b.bottom, right: b.right, shown: s.display !== 'none' && s.visibility !== 'hidden' && b.width > 0 && b.height > 0}; };
  const de = document.documentElement;
  return {iw: innerWidth, ih: innerHeight, sw: de.scrollWidth, sh: de.scrollHeight, bw: document.body.scrollWidth, bh: document.body.scrollHeight,
          generate: r('generate-button'), viewport: r('viewport'), history: r('history-list'), description: r('shot-description')};
}"""

JS_CONTRAST = """() => {
  const parse = c => { const m = c.match(/rgba?\\(([^)]+)\\)/); if (!m) return null; const p = m[1].split(/[ ,\\/]+/).filter(Boolean).map(Number); return {r: p[0], g: p[1], b: p[2], a: p.length > 3 ? p[3] : 1}; };
  const lum = c => { const f = v => { v /= 255; return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4); }; return 0.2126 * f(c.r) + 0.7152 * f(c.g) + 0.0722 * f(c.b); };
  const blend = (top, bottom) => ({r: top.r * top.a + bottom.r * (1 - top.a), g: top.g * top.a + bottom.g * (1 - top.a), b: top.b * top.a + bottom.b * (1 - top.a), a: 1});
  const bgOf = el => { const layers = []; for (let e = el; e; e = e.parentElement) { const s = getComputedStyle(e); if (s.backgroundImage !== 'none') return null; const c = parse(s.backgroundColor); if (c && c.a > 0) { layers.push(c); if (c.a >= 0.999) break; } }
    let base = {r: 255, g: 255, b: 255, a: 1}; for (let i = layers.length - 1; i >= 0; i--) base = blend(layers[i], base); return base; };
  const out = [];
  const skip = e => e.closest('[data-testid="hud"], [data-testid="player"] [data-testid="label-before"], [data-testid="player"] [data-testid="label-after"], video');
  const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  const seen = new Set();
  while (walker.nextNode()) {
    const t = walker.currentNode; if (!t.textContent.trim()) continue; const el = t.parentElement; if (!el || seen.has(el) || skip(el)) continue; seen.add(el);
    const s = getComputedStyle(el); const b = el.getBoundingClientRect();
    if (s.display === 'none' || s.visibility === 'hidden' || b.width === 0 || b.height === 0 || el.closest('[disabled]') || el.closest('[aria-disabled="true"]') || ['SCRIPT', 'STYLE', 'TITLE'].includes(el.tagName)) continue;
    const bg = bgOf(el); if (!bg) continue; let fg = parse(s.color); if (!fg) continue; fg = blend({...fg, a: fg.a * parseFloat(s.opacity || 1)}, bg);
    const l1 = lum(fg) + 0.05, l2 = lum(bg) + 0.05; const ratio = Math.max(l1, l2) / Math.min(l1, l2);
    out.push({text: t.textContent.trim().slice(0, 40), testid: (el.closest('[data-testid]') || {getAttribute: () => null}).getAttribute('data-testid'), ratio: Math.round(ratio * 100) / 100, size: parseFloat(s.fontSize)});
  }
  return out;
}"""

JS_NAMES = """() => {
  const bad = [];
  const label = e => { const al = e.getAttribute('aria-label'); if (al && al.trim()) return al; const lb = e.getAttribute('aria-labelledby'); if (lb) { const t = lb.split(/\\s+/).map(i => (document.getElementById(i) || {}).textContent || '').join(' ').trim(); if (t) return t; }
    if (e.id) { const l = document.querySelector(`label[for="${e.id}"]`); if (l && l.textContent.trim()) return l.textContent; } const wrap = e.closest('label'); if (wrap && wrap.textContent.trim()) return wrap.textContent;
    if (e.getAttribute('title')) return e.getAttribute('title'); if (!['INPUT', 'TEXTAREA'].includes(e.tagName) && e.textContent.trim()) return e.textContent; return ''; };
  for (const e of document.querySelectorAll('button, input, textarea, select, [role="radio"], [role="slider"], [role="radiogroup"], [role="progressbar"], a[href]')) {
    const b = e.getBoundingClientRect(); if (b.width === 0 && b.height === 0) continue; if (!label(e).trim()) bad.push((e.getAttribute('data-testid') || e.tagName) + ' ' + (e.outerHTML || '').slice(0, 80)); }
  return bad;
}"""

JS_FOCUS = """() => { const e = document.activeElement; if (!e || e === document.body) return null; const s = getComputedStyle(e);
  return {testid: (e.closest('[data-testid]') || {getAttribute: () => null}).getAttribute('data-testid'), tag: e.tagName, ow: parseFloat(s.outlineWidth), os: s.outlineStyle, oc: s.outlineColor, bs: s.boxShadow}; }"""

JS_ANIMATIONS = "() => document.getAnimations().filter(a => a.playState === 'running' && a.effect && a.effect.getTiming().iterations === Infinity).length"


def layout_checks(p, state, vw, vh):
    lay = p.page.evaluate(JS_LAYOUT)
    tag = f"{state} at {vw}x{vh}"
    report.check(lay["sw"] <= lay["iw"] and lay["bw"] <= lay["iw"], f"{tag}: the page scrolls sideways (scrollWidth {lay['sw']} > {lay['iw']})")
    report.check(lay["sh"] <= lay["ih"], f"{tag}: the page scrolls vertically (scrollHeight {lay['sh']} > {lay['ih']}); only the panels may scroll")
    g = lay["generate"]
    report.check(g and g["shown"] and g["y"] >= 0 and g["bottom"] <= lay["ih"] and g["right"] <= lay["iw"], f"{tag}: the Generate button must be fully on screen; got {g}")
    v = lay["viewport"]
    report.check(v and v["shown"] and v["w"] >= 560 and 1.7 <= v["w"] / v["h"] <= 1.95, f"{tag}: the viewport must be at least 560 px wide and about 20:11; got {v and (round(v['w']), round(v['h']))}")
    hs = lay["history"]
    report.check(hs and hs["shown"] and hs["bottom"] <= lay["ih"] + 1 and hs["h"] >= 60, f"{tag}: the history strip must be on screen; got {hs}")
    d = lay["description"]
    report.check(d and d["shown"] and d["bottom"] <= lay["ih"], f"{tag}: the description box must be on screen; got {d}")


def run():
    with AppHarness(delay=0.03) as h, browser() as b:
        fake = h.fake
        status, rec = h.post("/api/shots", {**SHOT, "description": "An earlier shot for the history strip.", "seed": 3})
        h.wait_for_shot(rec["id"], "done")

        # ---- every state at every laptop size
        for vw, vh in VIEWPORTS:
            p = Page(b, h, vw, vh).open()
            p.t("history-new").click()
            p.page.wait_for_timeout(150)
            layout_checks(p, "empty", vw, vh)
            p.t("shot-description").fill("A woman in a red coat crosses a rainy street at night, neon signs in the puddles.")
            layout_checks(p, "filled form", vw, vh)
            fake.hold_at("SamplerCustomAdvanced")
            p.t("generate-button").click()
            p.page.wait_for_selector('[data-testid="status-panel"][data-status="generating"]')
            layout_checks(p, "working", vw, vh)
            fake.release()
            p.page.wait_for_selector('[data-testid="viewport"][data-state="result"]', timeout=40000)
            p.page.wait_for_timeout(300)
            layout_checks(p, "result", vw, vh)
            fake.reset_cache()  # identical fixture videos: without this ComfyUI serves Depth of Field from its cache
            fake.fail("OpenOptics_DepthOfField", "Out of memory in Depth of Field")
            p.t("history-new").click()
            p.t("shot-description").fill("This one fails in optics.")
            p.t("generate-button").click()
            p.page.wait_for_selector('[data-testid="viewport"][data-state="failed"]', timeout=40000)
            layout_checks(p, "failed", vw, vh)
            fake.clear_failures()
            fake.stop()
            p.page.evaluate("window.dispatchEvent(new Event('focus'))")
            p.page.wait_for_selector('[data-testid="comfy-banner"]', timeout=10000)
            layout_checks(p, "ComfyUI down", vw, vh)
            fake.start()
            report.check(not p.errors, f"{vw}x{vh}: console errors or failed requests:\n  " + "\n  ".join(p.errors[:6]))
            report.check(not p.foreign, f"{vw}x{vh}: the page must load nothing from other hosts: {p.foreign[:4]}")
            p.close()

        # ---- tokens, fonts, contrast, focus, names, at 1280x720 in the main states
        p = Page(b, h, 1280, 720).open()
        p.t("history-new").click()
        p.t("shot-description").fill("Check the colours and the fonts.")
        root = p.page.evaluate("() => { const s = getComputedStyle(document.documentElement); const o = {}; for (const k of %s) o[k] = s.getPropertyValue(k).trim().toLowerCase(); return o; }" % list(TOKENS))
        for token, want in TOKENS.items():
            report.check(root.get(token) == want, f"CSS custom property {token} on :root must be {want}; got {root.get(token)!r}")
        bodybg = p.page.evaluate("() => getComputedStyle(document.body).backgroundColor")
        report.check(bodybg in ("rgb(11, 12, 14)",), f"the page background must be --bg (rgb(11, 12, 14)); got {bodybg}")
        fonts = p.page.evaluate("() => ({body: getComputedStyle(document.body).fontFamily, hud: getComputedStyle(document.querySelector('[data-testid=hud]')).fontFamily, ap: getComputedStyle(document.querySelector('[data-testid=aperture-value]')).fontFamily, sd: getComputedStyle(document.querySelector('[data-testid=subject-distance]')).fontFamily})")
        report.check("system-ui" in fonts["body"] and "Segoe UI" in fonts["body"], f"body font stack must be the system stack with Segoe UI and system-ui; got {fonts['body']}")
        for k in ("hud", "ap", "sd"):
            report.check("monospace" in fonts[k] and "Consolas" in fonts[k], f"the {k} readout must use the monospace stack; got {fonts[k]}")

        names = p.page.evaluate(JS_NAMES)
        report.check(not names, "controls without an accessible name: " + "; ".join(names[:5]))

        p.page.mouse.click(300, 26)  # click the header so the Tab sequence starts from the top of the page, not from the description
        order = []
        for _ in range(60):
            p.page.keyboard.press("Tab")
            f = p.page.evaluate(JS_FOCUS)
            if f is None:
                continue
            order.append(f)
            ow = f["ow"] if f["ow"] == f["ow"] else 0
            ring = (f["os"] not in ("none", "hidden") and ow >= 1.5 and "245, 165, 36" in f["oc"]) or "245, 165, 36" in f["bs"]
            report.check(ring, f"focus on {f['testid'] or f['tag']} must show an accent-coloured (#f5a524) focus ring (outline >= 1.5px or box-shadow); got outline {f['os']} {f['ow']}px {f['oc']}, shadow {f['bs'][:60]}")
            if len(order) >= 30 and f["testid"] in ("history-new",):
                break
        ids = [f["testid"] for f in order]
        want_order = ["shot-description", "camera-group", "lens-group", "framing-group", "aperture-slider", "generate-button"]
        positions = [ids.index(w) if w in ids else -1 for w in want_order]
        report.check(all(x >= 0 for x in positions) and positions == sorted(positions), f"Tab must visit description, camera, lens, framing, aperture, Generate in that order; got order {ids[:20]}")

        ratios = p.page.evaluate(JS_CONTRAST)
        low = [r for r in ratios if r["ratio"] < 4.5]
        report.check(len(ratios) >= 10, f"the contrast check found only {len(ratios)} text elements; text must sit on solid backgrounds")
        report.check(not low, "text with contrast below 4.5:1: " + "; ".join(f"{r['testid']} {r['text']!r} {r['ratio']}" for r in low[:6]))
        hudbg = p.page.evaluate("() => { const e = document.querySelector('[data-testid=hud]'); const c = getComputedStyle(e).backgroundColor; const m = c.match(/rgba?\\(([^)]+)\\)/); const v = m[1].split(/[ ,\\/]+/).map(Number); return v.length > 3 ? v[3] : 1; }")
        report.check(hudbg >= 0.35, f"the HUD sits on video, so it needs its own background (alpha >= 0.35); got {hudbg}")
        report.check(not p.errors and not p.foreign, f"errors or foreign requests: {p.errors[:4]} {p.foreign[:4]}")
        p.close()

        # ---- motion: the record dot blinks, but not under reduced motion
        p = Page(b, h, 1280, 720).open()
        p.t("history-new").click()
        fake.hold_at("SamplerCustomAdvanced")
        p.t("shot-description").fill("Motion check.")
        p.t("generate-button").click()
        p.page.wait_for_selector('[data-testid="record-dot"]')
        report.check(p.page.evaluate(JS_ANIMATIONS) >= 1, "the record dot must blink (an infinite CSS animation) while working")
        p.close()
        q = Page(b, h, 1280, 720, reduced_motion=True).open()
        q.page.wait_for_selector('[data-testid="record-dot"]', timeout=15000)
        report.check(q.page.evaluate(JS_ANIMATIONS) == 0, "under prefers-reduced-motion there must be no running infinite animation")
        q.close()
        fake.release()
        time.sleep(0.2)

        # ---- narrow screens: no horizontal scroll
        for vw, vh in ((900, 800), (768, 1024), (390, 844), (360, 740)):
            p = Page(b, h, vw, vh).open()
            lay = p.page.evaluate(JS_LAYOUT)
            report.check(lay["sw"] <= lay["iw"] and lay["bw"] <= lay["iw"], f"empty at {vw}x{vh}: horizontal scroll (scrollWidth {lay['sw']} > {lay['iw']})")
            report.check(lay["generate"] and lay["generate"]["shown"], f"empty at {vw}x{vh}: the Generate button must exist and be displayed")
            p.t("history-item").first.click()
            p.page.wait_for_selector('[data-testid="viewport"][data-state="result"]', timeout=15000)
            lay = p.page.evaluate(JS_LAYOUT)
            report.check(lay["sw"] <= lay["iw"] and lay["bw"] <= lay["iw"], f"result at {vw}x{vh}: horizontal scroll (scrollWidth {lay['sw']} > {lay['iw']})")
            report.check(not p.errors, f"{vw}x{vh}: console errors: {p.errors[:3]}")
            p.close()

    # ---- the screenshot script
    out = Path(tempfile.mkdtemp(prefix="opencinema_shots_"))
    run_ = subprocess.run([sys.executable, str(ROOT / "scripts" / "app_screenshots.py"), "--out", str(out)], cwd=str(ROOT), capture_output=True, text=True, timeout=240)
    report.check(run_.returncode == 0, f"scripts/app_screenshots.py --out DIR must exit 0; got {run_.returncode}: {(run_.stdout + run_.stderr)[-400:]}")
    for size in ("1280x720", "1366x768"):
        for state in ("empty", "form", "working", "result", "failed", "comfy-down"):
            f = out / f"{state}-{size}.png"
            if not f.exists():
                report.problems.append(f"app_screenshots.py must write {f.name}")
                continue
            img = np.asarray(Image.open(f).convert("RGB"), dtype=float)
            report.check(img.shape[1] == int(size.split("x")[0]) and img.shape[0] == int(size.split("x")[1]), f"{f.name} must be {size}; got {img.shape[1]}x{img.shape[0]}")
            report.check(img.std() > 6, f"{f.name} looks blank (pixel deviation {img.std():.1f})")
            report.check(img[:, :300].mean() < 60, f"{f.name} is not dark (mean brightness of the left panel {img[:, :300].mean():.0f}); the interface must be dark")


try:
    run()
except Exception as exc:  # noqa: BLE001
    import traceback
    report.problems.append(f"the check itself stopped: {type(exc).__name__}: {exc}\n{traceback.format_exc()[-1500:]}")
report.finish()
