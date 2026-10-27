"""Goal check: focus where you click, and rack focus (docs/app-spec.md section 7.2). Run with: node scripts/run-py.js scripts/accept_focus.py

Checks open_optics.focus_pull.rack_focus_m against hand-worked values, the Depth of Field node's new inputs (focus at a
point gives exactly the output of focus_m set to that point's depth; a rack gives, frame by frame, the output of the
eased diopter pull; chunking does not matter; defaults change nothing), the optics graph, the re-apply API and the
interface (pick a point, rack between two points, chips and labels). Prints one line per problem and exits 1 if any.
"""
import math
import os
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _app_accept import ROOT, Page, Report, browser, protected_files_unchanged  # noqa: E402

report = Report("focus")
protected_files_unchanged(report)
if report.problems:
    report.finish()

os.environ.setdefault("OPEN_OPTICS_DEVICE", "cpu")

from tests.app_harness import SHOT, AppHarness  # noqa: E402
from tests.fake_comfy import validate_prompt  # noqa: E402


def check_core():
    from open_optics import focus_pull
    f = getattr(focus_pull, "rack_focus_m", None)
    if f is None:
        report.problems.append("open_optics.focus_pull.rack_focus_m is missing")
        return
    for args, want in (((2, 8, 0.5), 3.2), ((2, 8, 0.2), 2.0), ((2, 8, 0.8), 8.0), ((2, 8, 0.35), 2.2654867), ((2, 8, 0.0), 2.0), ((2, 8, 1.0), 8.0),
                       ((5, 1, 0.5, 0.0, 1.0), 1 / (0.5 / 5 + 0.5 / 1))):
        got = f(*args)
        report.check(abs(got - want) < 1e-6, f"rack_focus_m{args} must be {want}; got {got}")
    for bad in ((0, 8, 0.5), (2, -1, 0.5), (2, math.inf, 0.5), (2, 8, 1.5), (2, 8, -0.1), (2, 8, 0.5, 0.6, 0.6), (2, 8, 0.5, 0.7, 0.3), (2, 8, 0.5, -0.1, 0.5)):
        try:
            f(*bad)
            report.problems.append(f"rack_focus_m{bad} must raise ValueError")
        except ValueError:
            pass


def check_node():
    import torch
    from open_optics_nodes import NODE_CLASS_MAPPINGS
    from open_optics.focus_pull import rack_focus_m
    node_cls = NODE_CLASS_MAPPINGS["OpenOptics_DepthOfField"]
    spec = node_cls.INPUT_TYPES()
    opt = list(spec.get("optional", {}))
    want = ["depth_mask", "depth_image", "chunk_frames", "max_layers", "focus_x", "focus_y", "rack_x", "rack_y", "rack_start", "rack_end"]
    report.check(opt[:len(want)] == want and all(k == "bokeh_squeeze" for k in opt[len(want):]), f"DepthOfField optional inputs must be {want} (then bokeh_squeeze, section 7.4); got {opt}")
    defs = {"focus_x": (-1.0, -1.0, 1.0, 0.001), "focus_y": (-1.0, -1.0, 1.0, 0.001), "rack_x": (-1.0, -1.0, 1.0, 0.001), "rack_y": (-1.0, -1.0, 1.0, 0.001),
            "rack_start": (0.2, 0.0, 1.0, 0.01), "rack_end": (0.8, 0.0, 1.0, 0.01)}
    for k, (d, lo, hi, st) in defs.items():
        v = spec.get("optional", {}).get(k)
        ok = bool(v) and v[0] == "FLOAT" and v[1].get("default") == d and v[1].get("min") == lo and v[1].get("max") == hi and v[1].get("step") == st
        report.check(ok, f"input {k} must be FLOAT default {d}, min {lo}, max {hi}, step {st}; got {v}")

    node = node_cls()
    g = torch.Generator().manual_seed(7)
    n, h, w = 6, 48, 64
    image = torch.rand((n, h, w, 3), generator=g)
    depth = torch.full((n, h, w), 2.0)
    depth[:, :, w // 2:] = 8.0
    depth[:, 0:3, 0:3] = float("nan")
    base = dict(image=image, focal_mm=50.0, f_number=1.4, focus_m=3.0, sensor_width_mm=36.0, quality="normal", max_radius_px=8, colorspace="srgb", depth_mask=depth)

    plain = node.apply(**base)[0]
    with_defaults = node.apply(**base, focus_x=-1.0, focus_y=-1.0, rack_x=-1.0, rack_y=-1.0, rack_start=0.2, rack_end=0.8)[0]
    report.check(torch.equal(plain, with_defaults), "with every new input at its default the output must be exactly as before")

    at2 = node.apply(**dict(base, focus_m=2.0))[0]
    at8 = node.apply(**dict(base, focus_m=8.0))[0]
    left = node.apply(**base, focus_x=0.25, focus_y=0.5)[0]
    right = node.apply(**base, focus_x=0.75, focus_y=0.5)[0]
    report.check(torch.allclose(left, at2, atol=1e-6), "focus at (0.25, 0.5) on a 2 m region must equal focus_m = 2.0")
    report.check(torch.allclose(right, at8, atol=1e-6), "focus at (0.75, 0.5) on an 8 m region must equal focus_m = 8.0")
    corner = node.apply(**dict(base, depth_mask=torch.where(torch.isnan(depth), depth, depth)), focus_x=0.0, focus_y=0.0)[0]
    report.check(torch.isfinite(corner).all(), "a focus window touching NaN depth must still give a finite image")

    racked = node.apply(**base, focus_x=0.25, focus_y=0.5, rack_x=0.75, rack_y=0.5, chunk_frames=8)[0]
    racked1 = node.apply(**base, focus_x=0.25, focus_y=0.5, rack_x=0.75, rack_y=0.5, chunk_frames=1)[0]
    report.check(torch.allclose(racked, racked1, atol=1e-6), "a rack must give the same result for chunk_frames 1 and 8")
    for i in range(n):
        d = rack_focus_m(2.0, 8.0, i / (n - 1), 0.2, 0.8)
        ref = node.apply(**dict(base, image=image[i:i + 1], depth_mask=depth[i:i + 1], focus_m=d))[0]
        report.check(torch.allclose(racked[i:i + 1], ref, atol=1e-5), f"rack frame {i} must equal focus_m = rack_focus_m(2, 8, {i}/{n - 1}) = {d:.4f}")
    custom = node.apply(**base, focus_x=0.25, focus_y=0.5, rack_x=0.75, rack_y=0.5, rack_start=0.0, rack_end=0.5)[0]
    ref_last = node.apply(**dict(base, image=image[-1:], depth_mask=depth[-1:], focus_m=8.0))[0]
    report.check(torch.allclose(custom[-1:], ref_last, atol=1e-5), "rack_end 0.5 must reach the second point by the last frame")

    for kwargs, what in (({"focus_x": 0.5, "focus_y": -1.0}, "one focus coordinate negative"),
                         ({"rack_x": 0.5, "rack_y": 0.5}, "a rack without a focus point"),
                         ({"focus_x": 0.2, "focus_y": 0.5, "rack_x": 0.8, "rack_y": 0.5, "rack_start": 0.6, "rack_end": 0.6}, "rack_start == rack_end"),
                         ({"focus_x": 0.2, "focus_y": 0.5, "rack_x": 0.8, "rack_y": -1.0}, "one rack coordinate negative")):
        try:
            node.apply(**base, **kwargs)
            report.problems.append(f"{what} must raise ValueError")
        except ValueError:
            pass


def check_graph():
    from app import graphs
    plain = graphs.build_optics_graph("clip.webm", 50.0, 2.8, 5.1005, "p")
    report.check("focus_x" not in plain["8"]["inputs"] and "rack_x" not in plain["8"]["inputs"], "without focus the DepthOfField inputs must be exactly as in section 3")
    pt = graphs.build_optics_graph("clip.webm", 50.0, 2.8, 5.1005, "q", focus={"x": 0.25, "y": 0.6})
    rk = graphs.build_optics_graph("clip.webm", 50.0, 4.0, 5.1005, "r", focus={"x": 0.25, "y": 0.6}, rack={"x": 0.7, "y": 0.4})
    dof = rk["8"]["inputs"]
    report.check((pt["8"]["inputs"].get("focus_x"), pt["8"]["inputs"].get("focus_y"), "rack_x" in pt["8"]["inputs"]) == (0.25, 0.6, False), "a focus point must add focus_x and focus_y only")
    report.check((dof.get("focus_x"), dof.get("focus_y"), dof.get("rack_x"), dof.get("rack_y"), dof.get("rack_start"), dof.get("rack_end")) == (0.25, 0.6, 0.7, 0.4, 0.2, 0.8), f"a rack must add rack_x, rack_y, rack_start 0.2, rack_end 0.8; got {dof}")
    for g in (pt, rk):
        report.check(not validate_prompt(g, input_files=["clip.webm"]), f"the focus graph must validate: {validate_prompt(g, input_files=['clip.webm'])[:3]}")
        changed = {k for k in g if g[k] != plain.get(k)}
        report.check(changed <= {"8", "9", "10"}, f"a focus change may only change DepthOfField, CreateVideo and SaveVideo; changed {sorted(changed)}")


def dof_runs(fake, since):
    return [e for e in fake.executed[since:] if e["class_type"] == "OpenOptics_DepthOfField"]


def check_api():
    with AppHarness(delay=0.02) as h:
        fake = h.fake
        st, rec = h.post("/api/shots", {**SHOT, "seed": 3})
        sid = rec["id"]
        done = h.wait_for_shot(sid, "done", timeout=90)
        v1 = done["versions"][0]
        report.check(v1.get("focus", "missing") is None and v1.get("rack", "missing") is None and v1.get("look") == "clean", f"the first version must have focus null, rack null, look 'clean'; got {v1}")
        bad = [({"aperture": 2.8, "focus": {"x": 1.2, "y": 0.5}}, "focus"), ({"aperture": 2.8, "focus": {"x": True, "y": 0.5}}, "focus"),
               ({"aperture": 2.8, "focus": {"x": 0.5}}, "focus"), ({"aperture": 2.8, "focus": [0.5, 0.5]}, "focus"),
               ({"aperture": 2.8, "focus": {"x": 0.5, "y": 0.5, "z": 1}}, "focus"),
               ({"aperture": 2.8, "focus": {"x": 0.5, "y": 0.5}, "rack": {"x": "a", "y": 0.5}}, "rack")]
        for body, field in bad:
            s, b = h.post(f"/api/shots/{sid}/reapply", body)
            report.check(s == 400 and (b or {}).get("error", {}).get("field") == field, f"reapply {body} must be 400 field {field}; got {s} {b}")
        s, b = h.post(f"/api/shots/{sid}/reapply", {"aperture": 2.8, "rack": {"x": 0.5, "y": 0.5}})
        err = (b or {}).get("error", {})
        report.check(s == 400 and err.get("field") == "rack" and err.get("message") == "Pick the first focus point before the rack point.", f"a rack without focus must be 400 field rack with the spec message; got {s} {b}")
        s, b = h.post("/api/shots/nope/reapply", {"aperture": 2.8, "focus": {"x": 3, "y": 3}})
        report.check(s == 404, f"404 must come before 400; got {s}")

        mark = len(fake.executed)
        s, b = h.post(f"/api/shots/{sid}/reapply", {"aperture": 2.8, "focus": {"x": 0.12345, "y": 0.6}})
        report.check(s == 202, f"reapply with a focus point must be 202; got {s} {b}")
        rec = h.wait_until(sid, lambda r: r["status"] == "done" and len(r["versions"]) == 2, what="the focus version")
        v2 = rec["versions"][1]
        report.check(v2.get("focus") == {"x": 0.123, "y": 0.6} and v2.get("rack") is None, f"version 2 must store focus rounded to 3 decimals and rack null; got {v2}")
        runs = dof_runs(fake, mark)
        report.check(bool(runs) and runs[-1]["inputs"].get("focus_x") == 0.123 and runs[-1]["inputs"].get("focus_y") == 0.6, f"ComfyUI's DepthOfField must get focus_x 0.123 and focus_y 0.6; got {runs[-1]['inputs'] if runs else None}")
        executed = {e["class_type"] for e in fake.executed[mark:]}
        report.check("DA3Inference" not in executed, f"a focus re-apply must reuse the cached depth (DA3Inference must not run again); ran {sorted(executed)}")

        mark = len(fake.executed)
        s, b = h.post(f"/api/shots/{sid}/reapply", {"aperture": 4, "focus": {"x": 0.2, "y": 0.5}, "rack": {"x": 0.8, "y": 0.4}})
        rec = h.wait_until(sid, lambda r: r["status"] == "done" and len(r["versions"]) == 3, what="the rack version")
        v3 = rec["versions"][2]
        report.check(v3.get("focus") == {"x": 0.2, "y": 0.5} and v3.get("rack") == {"x": 0.8, "y": 0.4} and v3.get("aperture") == 4, f"version 3 must store the rack; got {v3}")
        runs = dof_runs(fake, mark)
        i = runs[-1]["inputs"] if runs else {}
        report.check((i.get("rack_x"), i.get("rack_y"), i.get("rack_start"), i.get("rack_end")) == (0.8, 0.4, 0.2, 0.8), f"ComfyUI's DepthOfField must get the rack inputs; got {i}")
        mark = len(fake.executed)
        s, b = h.post(f"/api/shots/{sid}/reapply", {"aperture": 2.8})
        rec = h.wait_until(sid, lambda r: r["status"] == "done" and len(r["versions"]) == 4, what="the auto version")
        report.check(rec["versions"][3].get("focus") is None and rec["versions"][3].get("rack") is None, "a re-apply without focus must store focus and rack null")
        runs = dof_runs(fake, mark)
        report.check(not runs or "focus_x" not in runs[-1]["inputs"], "a re-apply without focus must not send focus_x")
        h.restart_app()
        s, rec = h.get(f"/api/shots/{sid}")
        report.check([(v.get("focus"), v.get("rack")) for v in rec["versions"]] == [(None, None), ({"x": 0.123, "y": 0.6}, None), ({"x": 0.2, "y": 0.5}, {"x": 0.8, "y": 0.4}), (None, None)], "versions' focus and rack must survive a restart")


def wait(p, pred, timeout=20):
    end = time.time() + timeout
    while time.time() < end:
        try:
            if pred():
                return True
        except Exception:  # noqa: BLE001
            pass
        p.page.wait_for_timeout(80)
    return False


def click_at(p, fx, fy):
    box = p.t("focus-layer").bounding_box()
    p.page.mouse.click(box["x"] + fx * box["width"], box["y"] + fy * box["height"])


def marker_pos(p, point):
    m = p.page.locator(f'[data-testid="focus-marker"][data-point="{point}"]:visible')
    if not m.count():
        return None
    mb, lb = m.first.bounding_box(), p.t("focus-layer").bounding_box()
    return ((mb["x"] + mb["width"] / 2 - lb["x"]) / lb["width"], (mb["y"] + mb["height"] / 2 - lb["y"]) / lb["height"])


def check_ui():
    with AppHarness(delay=0.02) as h, browser() as b:
        fake = h.fake
        st, rec = h.post("/api/shots", {**SHOT, "aperture": 2.8, "seed": 11})
        sid = rec["id"]
        h.wait_for_shot(sid, "done", timeout=90)
        p = Page(b, h, 1280, 720).open()
        wait(p, lambda: p.t("viewport").get_attribute("data-state") == "result")
        grp = p.t("focus-mode")
        report.check(grp.count() == 1 and grp.get_attribute("role") == "radiogroup" and (grp.get_attribute("aria-label") == "Focus" or grp.get_attribute("aria-labelledby")), "focus-mode must be a radiogroup named 'Focus'")
        radios = grp.locator('[role="radio"]')
        report.check([radios.nth(i).get_attribute("data-value") for i in range(radios.count())] == ["auto", "point", "rack"], "focus-mode must offer auto, point, rack")
        report.check([re.sub(r"\s+", " ", radios.nth(i).inner_text()).strip() for i in range(radios.count())] == ["Auto", "Pick point", "Rack focus"], "focus-mode labels must be Auto, Pick point, Rack focus")
        report.check(grp.locator('[role="radio"][data-value="auto"]').get_attribute("aria-checked") == "true", "focus-mode must start at auto for a version without focus")
        layer = p.t("focus-layer")
        report.check(layer.count() == 1 and layer.evaluate("e => getComputedStyle(e).pointerEvents") == "none", "focus-layer must exist and take no pointer events while not armed")
        # the compare slider still drags while the layer is not armed
        before = p.t("compare-slider").get_attribute("aria-valuenow")
        p.t("compare-slider").focus()
        p.page.keyboard.press("Home")
        report.check(p.t("compare-slider").get_attribute("aria-valuenow") == "0" and before is not None, "the compare slider must keep working while the focus layer is not armed")
        p.page.keyboard.press("End")

        grp.locator('[role="radio"][data-value="point"]').click()
        report.check(layer.evaluate("e => getComputedStyle(e).pointerEvents") != "none" and layer.get_attribute("role") == "button" and layer.get_attribute("aria-label") == "Choose the focus point", "choosing Pick point must arm focus-layer (role button, aria-label 'Choose the focus point')")
        lb, vb = layer.bounding_box(), p.t("after-video").bounding_box()
        report.check(lb and vb and all(abs(lb[k] - vb[k]) <= 2 for k in ("x", "y", "width", "height")), f"focus-layer must cover exactly the video box; layer {lb}, video {vb}")
        report.check(layer.evaluate("e => getComputedStyle(e).cursor") == "crosshair", "the armed focus-layer must show a crosshair cursor")
        click_at(p, 0.25, 0.6)
        pos = marker_pos(p, "a")
        report.check(pos is not None and abs(pos[0] - 0.25) < 0.02 and abs(pos[1] - 0.6) < 0.02, f"a focus-marker data-point=a must appear where clicked (0.25, 0.6); got {pos}")
        report.check(layer.evaluate("e => getComputedStyle(e).pointerEvents") == "none", "after one click in Pick point mode the layer must disarm")
        btn = p.t("reapply-button")
        report.check(btn.is_enabled() and btn.inner_text().strip() == "Apply focus", f"after picking a point reapply-button must read 'Apply focus' and be enabled; got {btn.inner_text()!r} enabled={btn.is_enabled()}")
        mark = len(fake.executed)
        btn.click()
        report.check(wait(p, lambda: p.t("version-chip").count() == 2, 30), "applying the focus point must add a version chip")
        chip = p.t("version-chip").nth(1)
        report.check(re.sub(r"\s+", " ", chip.inner_text()).strip() == "f/2.8 · focus" and chip.get_attribute("data-focus") == "point", f"the new chip must read 'f/2.8 · focus' with data-focus=point; got {chip.inner_text()!r} {chip.get_attribute('data-focus')}")
        report.check(wait(p, lambda: p.t("label-after").inner_text().strip() == "After f/2.8, focus point", 10), f"label-after must read 'After f/2.8, focus point'; got {p.t('label-after').inner_text()!r}")
        runs = dof_runs(fake, mark)
        i = runs[-1]["inputs"] if runs else {}
        report.check(abs(i.get("focus_x", -9) - 0.25) < 0.02 and abs(i.get("focus_y", -9) - 0.6) < 0.02, f"ComfyUI must get the clicked point; got {i}")
        report.check(btn.is_disabled() and btn.inner_text().strip() == "Apply aperture", "with nothing changed the button must be disabled and read 'Apply aperture'")

        grp.locator('[role="radio"][data-value="rack"]').click()
        click_at(p, 0.2, 0.5)
        report.check(layer.get_attribute("aria-label") == "Choose the point to rack focus to", "after point A in rack mode the layer's aria-label must ask for the rack point")
        report.check(btn.is_disabled() and "Click a second point to rack focus to." in p.t("reapply-status").inner_text(), "with only point A set the button must stay disabled and reapply-status must ask for the second point")
        click_at(p, 0.8, 0.4)
        report.check(marker_pos(p, "a") is not None and marker_pos(p, "b") is not None, "both focus markers a and b must be visible after two clicks in rack mode")
        report.check(btn.is_enabled() and btn.inner_text().strip() == "Apply focus", "after two points the button must read 'Apply focus' and be enabled")
        mark = len(fake.executed)
        btn.click()
        report.check(wait(p, lambda: p.t("version-chip").count() == 3, 30), "applying the rack must add a third chip")
        chip = p.t("version-chip").nth(2)
        report.check(re.sub(r"\s+", " ", chip.inner_text()).strip() == "f/2.8 · rack" and chip.get_attribute("data-focus") == "rack", f"the rack chip must read 'f/2.8 · rack'; got {chip.inner_text()!r}")
        report.check(wait(p, lambda: p.t("label-after").inner_text().strip() == "After f/2.8, rack focus", 10), "label-after must read 'After f/2.8, rack focus'")
        runs = dof_runs(fake, mark)
        i = runs[-1]["inputs"] if runs else {}
        report.check(abs(i.get("rack_x", -9) - 0.8) < 0.02 and abs(i.get("rack_y", -9) - 0.4) < 0.02, f"ComfyUI must get the rack point; got {i}")

        p.t("version-chip").nth(0).click()
        report.check(wait(p, lambda: grp.locator('[role="radio"][data-value="auto"]').get_attribute("aria-checked") == "true", 5), "clicking the first chip must set focus-mode back to auto")
        report.check(marker_pos(p, "a") is None, "a version without focus shows no focus marker")
        p.t("version-chip").nth(1).click()
        report.check(wait(p, lambda: grp.locator('[role="radio"][data-value="point"]').get_attribute("aria-checked") == "true", 5) and marker_pos(p, "a") is not None, "clicking the focus chip must show its point and set focus-mode to point")

        grp.locator('[role="radio"][data-value="point"]').click()
        layer.focus()
        p.page.keyboard.press("Enter")
        pos = marker_pos(p, "a")
        report.check(pos is not None and abs(pos[0] - 0.5) < 0.02 and abs(pos[1] - 0.5) < 0.02, f"Enter on the armed layer must set the point at the centre; got {pos}")
        report.check(not p.errors, "the page must log no errors: " + "; ".join(p.errors[:5]))
        p.close()


for step in (check_core, check_node, check_graph, check_api, check_ui):
    try:
        step()
    except Exception as exc:  # noqa: BLE001
        report.problems.append(f"{step.__name__} crashed: {type(exc).__name__}: {exc}")
report.finish()
