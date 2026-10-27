"""Goal check: lens looks (docs/app-spec.md section 7.4). Run with: node scripts/run-py.js scripts/accept_looks.py

Checks the Depth of Field node's bokeh_squeeze (an elliptical, taller-than-wide bokeh; 1.0 changes nothing), the optics
graphs for clean, vintage and anamorphic, the shot and re-apply API, and the interface (look-group, reapply-look,
chips). Prints one line per problem and exits 1 if there is any.
"""
import os
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _app_accept import Page, Report, browser, choose, protected_files_unchanged  # noqa: E402

report = Report("looks")
protected_files_unchanged(report)
if report.problems:
    report.finish()

os.environ.setdefault("OPEN_OPTICS_DEVICE", "cpu")

from tests.app_harness import SHOT, AppHarness  # noqa: E402
from tests.fake_comfy import validate_prompt  # noqa: E402


def check_node():
    import torch
    from open_optics_nodes import NODE_CLASS_MAPPINGS
    cls = NODE_CLASS_MAPPINGS["OpenOptics_DepthOfField"]
    opt = list(cls.INPUT_TYPES().get("optional", {}))
    report.check(opt[-1:] == ["bokeh_squeeze"] and "rack_end" in opt and opt.index("bokeh_squeeze") == opt.index("rack_end") + 1, f"bokeh_squeeze must be the last optional input, right after rack_end; got {opt}")
    d = cls.INPUT_TYPES()["optional"].get("bokeh_squeeze")
    report.check(bool(d) and d[0] == "FLOAT" and d[1].get("default") == 1.0 and d[1].get("min") == 1.0 and d[1].get("max") == 2.0 and d[1].get("step") == 0.05, f"bokeh_squeeze must be FLOAT default 1.0 min 1.0 max 2.0 step 0.05; got {d}")
    node = cls()
    g = torch.Generator().manual_seed(3)
    img = torch.rand((2, 40, 48, 3), generator=g)
    depth = torch.linspace(1.0, 30.0, 48).repeat(2, 40, 1)
    base = dict(image=img, focal_mm=50.0, f_number=1.4, focus_m=2.0, sensor_width_mm=36.0, quality="normal", max_radius_px=8, colorspace="srgb", depth_mask=depth)
    report.check(torch.equal(node.apply(**base)[0], node.apply(**base, bokeh_squeeze=1.0)[0]), "bokeh_squeeze 1.0 must give exactly the output without it")

    dot = torch.zeros((1, 61, 61, 3))
    dot[0, 30, 30, :] = 1.0
    far = torch.full((1, 61, 61), 1000.0)
    spot = dict(image=dot, focal_mm=50.0, f_number=1.4, focus_m=1.0, sensor_width_mm=36.0, quality="normal", max_radius_px=12, colorspace="linear", depth_mask=far)

    def extent(out):
        m = out[0, :, :, 0] > 1e-6
        rows = torch.nonzero(m.any(dim=1)).flatten()
        cols = torch.nonzero(m.any(dim=0)).flatten()
        return (int(rows.max() - rows.min() + 1), int(cols.max() - cols.min() + 1)) if len(rows) else (0, 0)

    h1, w1 = extent(node.apply(**spot)[0])
    h2, w2 = extent(node.apply(**spot, bokeh_squeeze=2.0)[0])
    report.check(abs(h1 - w1) <= 1 and h1 >= 15, f"a defocused point with squeeze 1.0 must be round; extent {h1}x{w1}")
    report.check(abs(h2 - h1) <= 1 and 1.7 <= h2 / max(w2, 1) <= 2.3, f"with bokeh_squeeze 2.0 the bokeh must be about twice as tall as wide and as tall as before; extent {h2}x{w2} (round {h1}x{w1})")
    total1 = float(node.apply(**spot)[0].sum())
    total2 = float(node.apply(**spot, bokeh_squeeze=2.0)[0].sum())
    report.check(abs(total1 - total2) < 0.02 * total1, f"the squeezed kernel must keep the energy (normalised); sums {total1} vs {total2}")


def check_graph():
    from app import graphs
    clean = graphs.build_optics_graph("clip.webm", 35.0, 2.8, 3.57, "p")
    report.check(clean == graphs.build_optics_graph("clip.webm", 35.0, 2.8, 3.57, "p", look="clean") and "bokeh_squeeze" not in clean["8"]["inputs"] and not {"11", "12", "13"} & set(clean), "look clean must be the plain graph without bokeh_squeeze or extra nodes")
    v = graphs.build_optics_graph("clip.webm", 35.0, 2.8, 3.57, "p", look="vintage")
    report.check(v.get("11") == {"class_type": "OpenOptics_LensDistortion", "inputs": {"image": ["8", 0], "focal_mm": 35.0, "sensor_width_mm": 36, "k1": -0.08, "k2": 0, "k3": 0, "p1": 0, "p2": 0, "direction": "apply", "fit": "crop"}}, f"vintage node 11 wrong: {v.get('11')}")
    report.check(v.get("12") == {"class_type": "OpenOptics_ChromaticAberration", "inputs": {"image": ["11", 0], "ca_r": 0.0015, "ca_b": -0.0015}}, f"vintage node 12 wrong: {v.get('12')}")
    report.check(v.get("13") == {"class_type": "OpenOptics_Vignette", "inputs": {"image": ["12", 0], "focal_mm": 35.0, "sensor_width_mm": 36, "strength": 0.6, "colorspace": "srgb"}}, f"vintage node 13 wrong: {v.get('13')}")
    report.check(v["9"]["inputs"]["images"] == ["13", 0] and "bokeh_squeeze" not in v["8"]["inputs"], "vintage: CreateVideo takes images from 13; no bokeh_squeeze")
    a = graphs.build_optics_graph("clip.webm", 35.0, 2.8, 3.57, "p", look="anamorphic")
    report.check(a["8"]["inputs"].get("bokeh_squeeze") == 1.5 and "11" not in a, "anamorphic sets bokeh_squeeze 1.5 and has no node 11")
    report.check(a.get("12") == {"class_type": "OpenOptics_ChromaticAberration", "inputs": {"image": ["8", 0], "ca_r": 0.001, "ca_b": -0.001}}, f"anamorphic node 12 wrong: {a.get('12')}")
    report.check(a.get("13") == {"class_type": "OpenOptics_Vignette", "inputs": {"image": ["12", 0], "focal_mm": 35.0, "sensor_width_mm": 36, "strength": 0.35, "colorspace": "srgb"}}, f"anamorphic node 13 wrong: {a.get('13')}")
    report.check(a["9"]["inputs"]["images"] == ["13", 0], "anamorphic: CreateVideo takes images from 13")
    for name, gr in (("vintage", v), ("anamorphic", a)):
        problems = validate_prompt(gr, input_files=["clip.webm"])
        report.check(not problems, f"the {name} graph must validate: {problems[:3]}")
        report.check(all(gr[k] == clean[k] for k in ("1", "2", "3", "4", "5", "6", "7")), f"the {name} look must not change the depth nodes")
    both = graphs.build_optics_graph("clip.webm", 35.0, 2.8, 3.57, "p", focus={"x": 0.3, "y": 0.3}, look="anamorphic")
    report.check(both["8"]["inputs"].get("focus_x") == 0.3 and both["8"]["inputs"].get("bokeh_squeeze") == 1.5, "focus and look must combine")


def runs(fake, since, cls):
    return [e for e in fake.executed[since:] if e["class_type"] == cls]


def check_api():
    with AppHarness(delay=0.02) as h:
        fake = h.fake
        _, o = h.get("/api/options")
        report.check(o.get("looks") == [{"id": "clean", "label": "Clean"}, {"id": "vintage", "label": "Vintage"}, {"id": "anamorphic", "label": "Anamorphic"}] and o.get("defaults", {}).get("look") == "clean", f"/api/options must list the looks and default clean; got {o.get('looks')} {o.get('defaults')}")
        st, rec = h.post("/api/shots", {**SHOT, "seed": 1})
        report.check(st == 201 and rec["params"].get("look") == "clean", f"a shot without look must get look clean; got {rec.get('params')}")
        h.wait_for_shot(rec["id"], "done", timeout=90)
        st, rec = h.post("/api/shots", {**SHOT, "seed": 2, "look": "sepia"})
        report.check(st == 400 and rec.get("error", {}).get("field") == "look", f"a bad look must be 400 field look; got {st} {rec}")
        mark = len(fake.executed)
        st, rec = h.post("/api/shots", {**SHOT, "seed": 3, "look": "vintage"})
        sid = rec["id"]
        done = h.wait_for_shot(sid, "done", timeout=90)
        report.check(done["params"].get("look") == "vintage" and done["versions"][0].get("look") == "vintage", f"a vintage shot's first version must be vintage; got {done['versions']}")
        report.check(len(runs(fake, mark, "OpenOptics_LensDistortion")) == 1 and len(runs(fake, mark, "OpenOptics_Vignette")) == 1, "a vintage shot must run LensDistortion and Vignette in ComfyUI")
        mark = len(fake.executed)
        h.post(f"/api/shots/{sid}/reapply", {"aperture": 8})
        rec = h.wait_until(sid, lambda r: r["status"] == "done" and len(r["versions"]) == 2, what="version 2")
        report.check(rec["versions"][1].get("look") == "vintage", "a re-apply without look keeps the latest version's look")
        mark = len(fake.executed)
        st, b = h.post(f"/api/shots/{sid}/reapply", {"aperture": 8, "look": "anamorphic"})
        report.check(st == 202, f"a re-apply with look anamorphic must be 202; got {st} {b}")
        rec = h.wait_until(sid, lambda r: r["status"] == "done" and len(r["versions"]) == 3, what="version 3")
        report.check(rec["versions"][2].get("look") == "anamorphic", "version 3 must be anamorphic")
        dof = runs(fake, mark, "OpenOptics_DepthOfField")
        report.check(bool(dof) and dof[-1]["inputs"].get("bokeh_squeeze") == 1.5, "the anamorphic re-apply must send bokeh_squeeze 1.5")
        report.check(not runs(fake, mark, "DA3Inference"), "a look change must reuse the cached depth")
        st, b = h.post(f"/api/shots/{sid}/reapply", {"aperture": 8, "look": "x"})
        report.check(st == 400 and b.get("error", {}).get("field") == "look", f"a bad re-apply look must be 400 field look; got {st} {b}")


def check_ui():
    with AppHarness(delay=0.02) as h, browser() as b:
        st, rec = h.post("/api/shots", {**SHOT, "aperture": 2.8, "seed": 7})
        h.wait_for_shot(rec["id"], "done", timeout=90)
        p = Page(b, h, 1280, 720).open()
        end = time.time() + 20
        while time.time() < end and p.t("viewport").get_attribute("data-state") != "result":
            p.page.wait_for_timeout(100)
        grp = p.t("look-group")
        radios = grp.locator('[role="radio"]')
        report.check(grp.get_attribute("role") == "radiogroup" and [radios.nth(i).get_attribute("data-value") for i in range(radios.count())] == ["clean", "vintage", "anamorphic"], "look-group must be a radiogroup of clean, vintage, anamorphic")
        report.check(grp.locator('[role="radio"][data-value="clean"]').get_attribute("aria-checked") == "true", "look-group defaults to clean")
        sel = p.t("reapply-look")
        report.check(sel.count() == 1 and sel.evaluate("e => e.tagName") == "SELECT" and sel.input_value() == "clean", "reapply-look must be a <select> starting at the shown version's look")
        report.check(p.t("reapply-button").is_disabled(), "nothing changed: reapply-button disabled")
        sel.select_option("vintage")
        btn = p.t("reapply-button")
        report.check(btn.is_enabled() and btn.inner_text().strip() == "Apply look", f"a different look must enable 'Apply look'; got {btn.inner_text()!r}")
        btn.click()
        ok = False
        end = time.time() + 30
        while time.time() < end and not ok:
            ok = p.t("version-chip").count() == 2
            p.page.wait_for_timeout(100)
        chip = p.t("version-chip").nth(1)
        report.check(ok and re.sub(r"\s+", " ", chip.inner_text()).strip() == "f/2.8 · Vintage" and chip.get_attribute("data-look") == "vintage", f"the new chip must read 'f/2.8 · Vintage' with data-look vintage; got {chip.inner_text() if ok else None!r}")
        choose(p, "look-group", "anamorphic")
        report.check("ANAMORPHIC" in p.t("hud").inner_text().upper() or "Anamorphic" in p.t("hud").inner_text(), "the HUD must mention a non-clean look while editing")
        sizes = p.page.evaluate("() => [document.scrollingElement.scrollWidth, document.scrollingElement.scrollHeight, innerWidth, innerHeight]")
        report.check(sizes[0] <= sizes[2] and sizes[1] <= sizes[3], f"no page scrolling at 1280x720; got {sizes}")
        gb = p.t("generate-button").bounding_box()
        report.check(gb is not None and 0 <= gb["y"] and gb["y"] + gb["height"] <= 720, f"generate-button must stay visible without scrolling; box {gb}")
        report.check(not p.errors, "the page must log no errors: " + "; ".join(p.errors[:5]))
        p.close()


for step in (check_node, check_graph, check_api, check_ui):
    try:
        step()
    except Exception as exc:  # noqa: BLE001
        report.problems.append(f"{step.__name__} crashed: {type(exc).__name__}: {exc}")
report.finish()
