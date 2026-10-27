"""Goal check: real camera moves with the LTX-2 camera LoRAs (docs/app-spec.md section 7.3). Run with: node scripts/run-py.js scripts/accept_camera.py

Checks the twelve camera moves, CAMERA_LORAS, the generation graph with and without a LoRA, that a shot uses a LoRA
only when ComfyUI lists the file (and is never refused for it), and the interface (LoRA tags, the layout at
1280 x 720, the shot brief). Prints one line per problem and exits 1 if there is any.
"""
import copy
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _app_accept import Page, Report, browser, choose, protected_files_unchanged  # noqa: E402

report = Report("camera")
protected_files_unchanged(report)
if report.problems:
    report.finish()

from tests.app_harness import SHOT, AppHarness  # noqa: E402
from tests.fake_comfy import validate_prompt  # noqa: E402

IDS = ["static", "dolly-in", "dolly-out", "truck-left", "truck-right", "crane-up", "crane-down", "pan-left", "pan-right", "tilt-up", "orbit", "handheld"]
LABELS = ["Static", "Dolly in", "Dolly out", "Truck left", "Truck right", "Crane up", "Crane down", "Pan left", "Pan right", "Tilt up", "Orbit", "Handheld"]
LORA = {c: f"ltx-2-19b-lora-camera-control-{m}.safetensors" for c, m in
        [("static", "static"), ("dolly-in", "dolly-in"), ("dolly-out", "dolly-out"), ("truck-left", "dolly-left"), ("truck-right", "dolly-right"), ("crane-up", "jib-up"), ("crane-down", "jib-down")]}
PHRASES = {"truck-left": "The camera trucks to the left, moving sideways parallel to the subject",
           "truck-right": "The camera trucks to the right, moving sideways parallel to the subject",
           "crane-up": "The camera cranes up, rising smoothly", "crane-down": "The camera cranes down, descending smoothly",
           "dolly-in": "Slow dolly-in toward the subject", "pan-left": "Smooth pan to the left"}


def check_module():
    from app import graphs, shot
    ids = [c["id"] for c in shot.CAMERAS]
    labels = [c["label"] for c in shot.CAMERAS]
    report.check(ids == IDS and labels == LABELS, f"CAMERAS must be {list(zip(IDS, LABELS))}; got {list(zip(ids, labels))}")
    report.check(getattr(shot, "CAMERA_LORAS", None) == LORA, f"CAMERA_LORAS must be {LORA}; got {getattr(shot, 'CAMERA_LORAS', None)}")
    for cam, phrase in PHRASES.items():
        prompt = shot.build_prompt({"description": "A man walks.", "camera": cam, "lens_mm": 50, "framing": "wide"})
        report.check(f" {phrase}. 50 mm lens look" in prompt, f"the prompt for {cam} must contain '{phrase}.'; got {prompt!r}")
    plain = graphs.build_generation_graph("p", 1, "x")
    report.check("30" not in plain and plain["14"]["inputs"]["model"] == ["1", 0] and plain["23"]["inputs"]["model"] == ["1", 0], "without a LoRA the generation graph must be exactly as in section 3")
    g = graphs.build_generation_graph("p", 1, "x", camera_lora=LORA["dolly-in"])
    n30 = g.get("30", {})
    report.check(n30.get("class_type") == "LoraLoaderModelOnly" and n30.get("inputs") == {"model": ["1", 0], "lora_name": LORA["dolly-in"], "strength_model": 1.0}, f"node 30 must be LoraLoaderModelOnly(model ['1', 0], lora_name, strength_model 1.0); got {n30}")
    report.check(g["14"]["inputs"]["model"] == ["30", 0] and g["23"]["inputs"]["model"] == ["30", 0], "both CFGGuider nodes must take the model from node 30")
    report.check({k for k in g if g[k] != plain.get(k)} == {"14", "23", "30"}, "only nodes 14, 23 and 30 may differ with a LoRA")
    problems = validate_prompt(g)
    report.check(not problems, f"the LoRA graph must validate against the node definitions: {problems[:3]}")


def gen_graph(fake, since):
    graphs_ = [g for g in fake.prompts[since:] if any(n.get("class_type") == "SamplerCustomAdvanced" for n in g.values())]
    return graphs_[-1] if graphs_ else None


def check_api():
    with AppHarness(delay=0.02) as h:
        fake = h.fake
        _, options = h.get("/api/options")
        cams = options.get("cameras", [])
        report.check([c.get("id") for c in cams] == IDS and [c.get("lora") for c in cams] == [c in LORA for c in IDS], f"/api/options cameras must carry lora flags; got {cams}")

        def make(camera, seed):
            mark = len(fake.prompts)
            st, rec = h.post("/api/shots", {**SHOT, "camera": camera, "seed": seed})
            report.check(st == 201, f"a {camera} shot must be created; got {st} {rec}")
            done = h.wait_for_shot(rec["id"], "done", timeout=90)
            return done, gen_graph(fake, mark)

        done, g = make("crane-up", 1)
        report.check(done["derived"].get("camera_control") == "lora", f"crane-up with the LoRA listed must have derived.camera_control 'lora'; got {done['derived']}")
        report.check(g is not None and g.get("30", {}).get("inputs", {}).get("lora_name") == LORA["crane-up"], "the crane-up graph sent to ComfyUI must load the jib-up LoRA")
        done, g = make("orbit", 2)
        report.check(done["derived"].get("camera_control") == "prompt" and g is not None and "30" not in g, "orbit has no LoRA: camera_control 'prompt' and no node 30")

        saved = copy.deepcopy(fake.object_info.get("LoraLoaderModelOnly"))
        fake.object_info["LoraLoaderModelOnly"]["input"]["required"]["lora_name"] = [[LORA["static"]]]
        done, g = make("dolly-in", 3)
        report.check(done["derived"].get("camera_control") == "prompt" and g is not None and "30" not in g, "dolly-in whose LoRA file ComfyUI does not list must fall back to the prompt (no node 30), not be refused")
        done, g = make("static", 4)
        report.check(done["derived"].get("camera_control") == "lora" and g is not None and g.get("30", {}).get("inputs", {}).get("lora_name") == LORA["static"], "static whose LoRA is listed must use it")
        fake.remove_node("LoraLoaderModelOnly")
        done, g = make("truck-left", 5)
        report.check(done["derived"].get("camera_control") == "prompt" and g is not None and "30" not in g, "without the LoraLoaderModelOnly node every move falls back to the prompt")
        fake.object_info["LoraLoaderModelOnly"] = saved
        _, listing = h.get("/api/shots")
        report.check(all(s.get("derived", {}).get("camera_control") in ("lora", "prompt") for s in listing["shots"]), "every listed shot must have derived.camera_control")


def check_ui():
    with AppHarness(delay=0.02) as h, browser() as b:
        p = Page(b, h, 1280, 720).open()
        p.page.wait_for_timeout(500)
        grp = p.t("camera-group")
        radios = grp.locator('[role="radio"]')
        vals = [radios.nth(i).get_attribute("data-value") for i in range(radios.count())]
        report.check(vals == IDS, f"camera-group must offer the twelve moves in order; got {vals}")
        for i, cam in enumerate(vals):
            text = re.sub(r"\s+", " ", radios.nth(i).inner_text()).strip()
            has_tag = "LoRA" in text
            report.check(has_tag == (cam in LORA), f"camera option {cam} must {'show' if cam in LORA else 'not show'} a 'LoRA' tag; text {text!r}")
            report.check(LABELS[i] in text, f"camera option {cam} must show its label {LABELS[i]!r}; got {text!r}")
        gb = p.t("generate-button").bounding_box()
        report.check(gb is not None and gb["y"] + gb["height"] <= 720 and gb["y"] >= 0, f"generate-button must be visible without scrolling at 1280x720; box {gb}")
        sizes = p.page.evaluate("() => [document.scrollingElement.scrollWidth, document.scrollingElement.scrollHeight, innerWidth, innerHeight]")
        report.check(sizes[0] <= sizes[2] and sizes[1] <= sizes[3], f"no page scrolling at 1280x720; got {sizes}")
        for i in range(radios.count()):
            bb = radios.nth(i).bounding_box()
            report.check(bb is not None and bb["width"] >= 40 and bb["height"] >= 24, f"camera option {vals[i]} must be at least 40x24 px; got {bb}")
        choose(p, "camera-group", "dolly-in")
        p.t("shot-description").fill("A cyclist rides through a tunnel of autumn trees.")
        p.t("generate-button").click()
        end = time.time() + 90
        while time.time() < end and p.t("viewport").get_attribute("data-state") != "result":
            p.page.wait_for_timeout(150)
        brief = re.sub(r"\s+", " ", p.t("shot-brief").inner_text())
        report.check("Dolly in (LoRA)" in brief, f"the shot brief must say 'Dolly in (LoRA)' for a LoRA shot; got {brief!r}")
        report.check(not p.errors, "the page must log no errors: " + "; ".join(p.errors[:5]))
        p.close()


for step in (check_module, check_api, check_ui):
    try:
        step()
    except Exception as exc:  # noqa: BLE001
        report.problems.append(f"{step.__name__} crashed: {type(exc).__name__}: {exc}")
report.finish()
