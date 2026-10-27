"""Goal check: the app's shot model and ComfyUI graphs. Run with: node scripts/run-py.js scripts/accept_app_shot.py

Checks app/shot.py and app/graphs.py against docs/app-spec.md sections 2 and 3: parameter validation, the subject distance
from the framing helper (hand-checked table), the LTX-2 prompt text, and that both ComfyUI graphs pass the fake server's
validation against the recorded real node definitions. Prints one line per problem and exits 1 if there is any.
"""
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _app_accept import Report, ROOT, protected_files_unchanged  # noqa: E402

report = Report("app shot model and graphs")
protected_files_unchanged(report)
if report.problems:
    report.finish()

try:
    from app import graphs, shot
except Exception as exc:
    print(f"cannot import app.shot / app.graphs: {type(exc).__name__}: {exc}")
    sys.exit(1)
from tests.fake_comfy import validate_prompt  # noqa: E402

DISTANCES = {  # docs/app-spec.md 2.1, hand-checked
    24: {"close-up": 0.7599, "waist-up": 1.3119, "full-body": 2.4482, "wide": 5.9114},
    35: {"close-up": 1.1082, "waist-up": 1.9132, "full-body": 3.5704, "wide": 8.6209},
    50: {"close-up": 1.5832, "waist-up": 2.7331, "full-body": 5.1005, "wide": 12.3155},
    85: {"close-up": 2.6914, "waist-up": 4.6462, "full-body": 8.6709, "wide": 20.9364},
}
FRAMING_PHRASE = {"close-up": "Close-up shot of the subject's face and shoulders", "waist-up": "Waist-up medium shot",
                  "full-body": "Full-body shot, the whole figure visible head to toe", "wide": "Wide establishing shot, the figure small in a large scene"}
CAMERA_PHRASE = {"static": "The camera is locked off and does not move", "dolly-in": "Slow dolly-in toward the subject", "dolly-out": "Slow dolly-out away from the subject",
                 "pan-left": "Smooth pan to the left", "pan-right": "Smooth pan to the right", "tilt-up": "Slow tilt up",
                 "orbit": "The camera orbits slowly around the subject", "handheld": "Handheld camera with subtle natural movement"}
APERTURES = [1.4, 2, 2.8, 4, 5.6, 8, 11, 16]

# ---- constants
report.check(dict(shot.SUBJECT_HEIGHT_FRACTION) == {"close-up": 2.8, "waist-up": 1.6, "full-body": 0.85, "wide": 0.35}, f"SUBJECT_HEIGHT_FRACTION must be the table in section 2.1; got {getattr(shot, 'SUBJECT_HEIGHT_FRACTION', None)}")
report.check(list(shot.LENSES) == [24, 35, 50, 85], f"LENSES must be [24, 35, 50, 85]; got {list(shot.LENSES)}")
report.check([float(a) for a in shot.APERTURES] == [float(a) for a in APERTURES], f"APERTURES must be {APERTURES}; got {list(shot.APERTURES)}")
_camera_ids = [c["id"] if isinstance(c, dict) else c for c in shot.CAMERAS]
report.check(_camera_ids in (list(CAMERA_PHRASE), ["static", "dolly-in", "dolly-out", "truck-left", "truck-right", "crane-up", "crane-down", "pan-left", "pan-right", "tilt-up", "orbit", "handheld"]), f"CAMERAS must list the camera ids in order: the eight {list(CAMERA_PHRASE)}, or the twelve of docs/app-spec.md section 7.3")
report.check([f["id"] if isinstance(f, dict) else f for f in shot.FRAMINGS] == list(FRAMING_PHRASE), f"FRAMINGS must list {list(FRAMING_PHRASE)}")

# ---- distances
for lens, row in DISTANCES.items():
    for framing, want in row.items():
        try:
            got = shot.subject_distance(lens, framing)
        except Exception as exc:
            report.problems.append(f"subject_distance({lens}, {framing!r}) raised {type(exc).__name__}: {exc}")
            continue
        report.check(abs(got - want) < 6e-5, f"subject_distance({lens}, {framing!r}) = {got:.5f} m, expected {want} m")
for bad in ((28, "wide"), (50, "head"), ("50", "wide")):
    try:
        shot.subject_distance(*bad)
        report.problems.append(f"subject_distance{bad} must raise ValueError (or ShotError)")
    except (ValueError, shot.ShotError):
        pass
    except Exception as exc:
        report.problems.append(f"subject_distance{bad} raised {type(exc).__name__}, expected ValueError or ShotError")

# ---- the helper is the library's, not a copy
source = (ROOT / "app" / "shot.py").read_text(encoding="utf-8")
report.check("open_optics" in source and "subject_distance_m" in source, "app/shot.py must call open_optics.framing.subject_distance_m")
report.check("1700" not in source and "* 1000" not in source and "1000 *" not in source,"app/shot.py must not re-implement the thin-lens formula (no 1.7 m times 1000 arithmetic)")

# ---- validate_shot
GOOD = {"description": "  A woman in a red coat crosses a street.  ", "camera": "dolly-in", "lens_mm": 50, "aperture": 2.8, "framing": "full-body", "seed": 5}
try:
    cleaned = shot.validate_shot(dict(GOOD))
    report.check(cleaned["description"] == "A woman in a red coat crosses a street.", f"validate_shot must trim the description; got {cleaned.get('description')!r}")
    report.check(all(cleaned.get(k) == GOOD[k] for k in ("camera", "lens_mm", "aperture", "framing", "seed")), f"validate_shot changed valid values: {cleaned}")
    without_seed = shot.validate_shot({k: v for k, v in GOOD.items() if k != "seed"})
    report.check(isinstance(without_seed.get("seed"), int) and 0 <= without_seed["seed"] <= 2147483647, f"a missing seed must become a random integer 0..2147483647; got {without_seed.get('seed')!r}")
    report.check(shot.validate_shot({**GOOD, "aperture": 2})["aperture"] == 2, "aperture 2 (the f/2 stop) must be accepted")
except Exception as exc:
    report.problems.append(f"validate_shot rejected a valid shot: {type(exc).__name__}: {exc}")

BAD = [
    ("description", {"description": "ab"}), ("description", {"description": "   "}), ("description", {"description": "x" * 1001}), ("description", {"description": 5}),
    ("camera", {"camera": "zoom"}), ("camera", {"camera": None}),
    ("lens_mm", {"lens_mm": 28}), ("lens_mm", {"lens_mm": "50"}), ("lens_mm", {"lens_mm": True}),
    ("aperture", {"aperture": 3}), ("aperture", {"aperture": 0}), ("aperture", {"aperture": "f/2.8"}),
    ("framing", {"framing": "head"}),
    ("seed", {"seed": -1}), ("seed", {"seed": 2147483648}), ("seed", {"seed": 1.5}), ("seed", {"seed": "7"}), ("seed", {"seed": True}),
]
for field, patch in BAD:
    try:
        shot.validate_shot({**GOOD, **patch})
        report.problems.append(f"validate_shot must reject {patch}")
    except shot.ShotError as exc:
        report.check(getattr(exc, "field", None) == field, f"ShotError for {patch} must have .field == {field!r}; got {getattr(exc, 'field', None)!r}")
        report.check(bool(getattr(exc, "message", "")) and len(exc.message) > 12, f"ShotError for {patch} needs a readable .message")
    except Exception as exc:
        report.problems.append(f"validate_shot({patch}) raised {type(exc).__name__}, expected ShotError")
for missing in ("description", "camera", "lens_mm", "aperture", "framing"):
    try:
        shot.validate_shot({k: v for k, v in GOOD.items() if k != missing})
        report.problems.append(f"validate_shot must reject a shot without {missing}")
    except shot.ShotError as exc:
        report.check(exc.field == missing, f"ShotError for a missing {missing} must have .field == {missing!r}; got {exc.field!r}")
    except Exception as exc:
        report.problems.append(f"validate_shot without {missing} raised {type(exc).__name__}, expected ShotError")

# ---- the prompt
for camera, cphrase in CAMERA_PHRASE.items():
    for framing, fphrase in FRAMING_PHRASE.items():
        for desc, shown in (("A man waits at a bus stop", "A man waits at a bus stop."), ("Is it raining?", "Is it raining?"), ("He runs!", "He runs!"), ("Quiet harbour.", "Quiet harbour.")):
            params = {**GOOD, "description": desc, "camera": camera, "framing": framing, "lens_mm": 85}
            want = (f"{fphrase}. {shown} {cphrase}. 85 mm lens look, deep focus with everything sharp from the foreground to the far background, "
                    "cinematic lighting, 35mm film.")
            try:
                got = shot.build_prompt(params)
            except Exception as exc:
                report.problems.append(f"build_prompt raised {type(exc).__name__}: {exc}")
                break
            if got != want:
                report.problems.append(f"build_prompt({camera}, {framing}, {desc!r}) =\n  {got!r}\nexpected\n  {want!r}")
                break
        else:
            continue
        break

# ---- generation graph
PROMPT = "Full-body shot, the whole figure visible head to toe. A test. Slow dolly-in toward the subject. 50 mm lens look."
try:
    g = graphs.build_generation_graph(PROMPT, 1234, "opencinema/test/before")
    problems = validate_prompt(g, input_files=[])
    report.check(not problems, "build_generation_graph does not validate against the real node definitions:\n  " + "\n  ".join(problems[:8]))
    by_type = {}
    for node_id, node in g.items():
        by_type.setdefault(node["class_type"], []).append((node_id, node["inputs"]))
    report.check([i["text"] for _, i in by_type.get("CLIPTextEncode", [])] == [PROMPT], "exactly one CLIPTextEncode must carry the prompt")
    report.check(sorted(i["noise_seed"] for _, i in by_type.get("RandomNoise", [])) == [1234, 1234 + 378], "RandomNoise seeds must be seed and seed + 378")
    report.check(len(by_type.get("SamplerCustomAdvanced", [])) == 2, "two SamplerCustomAdvanced nodes (distilled pass and refine pass) are required")
    latent = by_type.get("EmptyLTXVLatentVideo", [{}])[0][1] if by_type.get("EmptyLTXVLatentVideo") else {}
    report.check((latent.get("width"), latent.get("height"), latent.get("length")) == (640, 352, 121), f"the first stage must be 640x352 and 121 frames; got {latent}")
    report.check(len(by_type.get("LTXVLatentUpsampler", [])) == 1, "one LTXVLatentUpsampler (x2) is required")
    report.check(by_type.get("UnetLoaderGGUF", [(0, {})])[0][1].get("unet_name") == "ltx-2-19b-distilled_Q4_K_M.gguf", "the model must be ltx-2-19b-distilled_Q4_K_M.gguf")
    out = g.get(graphs.GENERATION_OUTPUT_NODE, {})
    report.check(out.get("class_type") == "SaveVideo" and out["inputs"].get("filename_prefix") == "opencinema/test/before", "GENERATION_OUTPUT_NODE must be a SaveVideo with the given prefix")
    report.check(len(by_type.get("SaveVideo", [])) == 1, "the generation graph must have exactly one SaveVideo")
    json.dumps(g)
except Exception as exc:
    report.problems.append(f"build_generation_graph failed: {type(exc).__name__}: {exc}")

# ---- optics graph
try:
    a = graphs.build_optics_graph("clip.webm", 50.0, 2.8, 5.1005, "opencinema/test/after_1")
    b = graphs.build_optics_graph("clip.webm", 50.0, 8.0, 5.1005, "opencinema/test/after_2")
    problems = validate_prompt(a, input_files=["clip.webm"])
    report.check(not problems, "build_optics_graph does not validate against the real node definitions:\n  " + "\n  ".join(problems[:8]))
    by_type = {}
    for node_id, node in a.items():
        by_type.setdefault(node["class_type"], []).append((node_id, node["inputs"]))
    for ctype in ("LoadVideo", "GetVideoComponents", "LoadDA3Model", "DA3Inference", "DA3Render", "OpenOptics_DepthToMetric", "OpenOptics_DepthTemporalSmooth", "OpenOptics_DepthOfField", "CreateVideo", "SaveVideo"):
        report.check(len(by_type.get(ctype, [])) == 1, f"the optics graph needs exactly one {ctype}; has {len(by_type.get(ctype, []))}")
    if not report.problems:
        d2m = by_type["OpenOptics_DepthToMetric"][0][1]
        report.check(d2m.get("mode") == "subject" and d2m.get("subject_m") == 5.1005 and d2m.get("inverse_depth") is False, f"DepthToMetric must use subject mode with subject_m=5.1005, inverse_depth false; got {d2m}")
        report.check((d2m.get("subject_x"), d2m.get("subject_y"), d2m.get("near_m"), d2m.get("far_m")) == (0.5, 0.5, 0.3, 80.0), f"DepthToMetric subject point and range wrong: {d2m}")
        dof = by_type["OpenOptics_DepthOfField"][0][1]
        report.check(dof.get("focal_mm") == 50.0 and dof.get("f_number") == 2.8 and dof.get("focus_m") == 5.1005, f"DepthOfField must get focal_mm 50, f_number 2.8, focus_m = subject_m; got {dof}")
        report.check((dof.get("sensor_width_mm"), dof.get("max_radius_px"), dof.get("quality"), dof.get("colorspace")) == (36.0, 24, "normal", "srgb"), f"DepthOfField fixed settings wrong: {dof}")
        report.check(by_type["LoadVideo"][0][1].get("file") == "clip.webm", "LoadVideo.file must be the video_file argument")
        out = a.get(graphs.OPTICS_OUTPUT_NODE, {})
        report.check(out.get("class_type") == "SaveVideo" and out["inputs"].get("filename_prefix") == "opencinema/test/after_1", "OPTICS_OUTPUT_NODE must be a SaveVideo with the given prefix")
        differing = sorted(k for k in set(a) | set(b) if a.get(k) != b.get(k))
        names = sorted(a[k]["class_type"] for k in differing)
        report.check(set(a) == set(b), "the two optics graphs must use the same node ids")
        report.check(set(names) <= {"OpenOptics_DepthOfField", "CreateVideo", "SaveVideo"} and "OpenOptics_DepthOfField" in names,
                     f"graphs for two apertures may differ only in OpenOptics_DepthOfField, CreateVideo and SaveVideo (so ComfyUI's cache reuses the depth); differing: {names}")
        report.check(a == graphs.build_optics_graph("clip.webm", 50.0, 2.8, 5.1005, "opencinema/test/after_1"), "build_optics_graph must be deterministic")
except Exception as exc:
    report.problems.append(f"build_optics_graph failed: {type(exc).__name__}: {exc}")

# ---- no dependency on the benchmark scripts
for path in (ROOT / "app").rglob("*.py"):
    text = path.read_text(encoding="utf-8")
    report.check(not re.search(r"^\s*(from|import)\s+bench\b", text, re.M), f"{path.relative_to(ROOT)} imports bench; the app must have its own graph code")

report.finish()
