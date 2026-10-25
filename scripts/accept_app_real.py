"""Goal check: the backend survives what a real ComfyUI does. Run with: node scripts/run-py.js scripts/accept_app_real.py

The fake ComfyUI (tests/fake_comfy.py) can behave like a real one: ws `progress_state` frames, a busy ComfyUI that answers
slowly, dropped connections, a missing custom node. This check runs the app against those and requires that a good shot is
never lost, the progress and status text are right, a missing node or model is reported before anything is generated, and the
public record and the media route are exactly what docs/app-spec.md and docs/app-hardening.md say.
Prints one line per problem and exits 1 if there is any.
"""
import copy
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _app_accept import Report, protected_files_unchanged  # noqa: E402

report = Report("app real-run hardening")
protected_files_unchanged(report)
if report.problems:
    report.finish()

from tests.app_harness import SHOT, AppHarness  # noqa: E402

RECORD_KEYS = {"id", "created_at", "params", "derived", "status", "progress", "message", "stages", "elapsed_s", "error", "reapply_error", "before_url", "versions", "current_version"}
ISO_Z = re.compile(r"^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ$")


def make(h, n, hold=None, **patch):
    status, rec = h.post("/api/shots", {**SHOT, "description": f"Real-run check number {n}, a rider on a salt flat.", "seed": 100 + n, **patch})
    assert status == 201, (status, rec)
    return rec["id"]


def wait_message(h, sid, predicate, timeout=20):
    end = time.time() + timeout
    record = None
    while time.time() < end:
        record = h.get(f"/api/shots/{sid}")[1]
        if predicate(record):
            return record
        time.sleep(0.2)
    return record


def run():
    with AppHarness(delay=0.05) as h:
        fake = h.fake
        fake.real_progress = True

        # ---- a missing custom node or model is reported before anything is generated
        saved = copy.deepcopy(fake.object_info["DA3Inference"])
        fake.remove_node("DA3Inference")
        before = len(h.get("/api/shots")[1]["shots"])
        status, body = h.post("/api/shots", SHOT)
        err = (body or {}).get("error", {}) if isinstance(body, dict) else {}
        report.check(status == 503 and err.get("code") == "comfy_nodes_missing" and "DA3Inference" in err.get("message", "") and "ComfyUI" in err.get("message", ""),
                     f"a graph whose custom node is not installed must be refused at once with 503 comfy_nodes_missing naming the node; got {status} {str(body)[:300]}")
        report.check(len(h.get("/api/shots")[1]["shots"]) == before, "no shot may be created when a node is missing")
        fake.object_info["DA3Inference"] = saved
        unet = fake.object_info["UnetLoaderGGUF"]["input"]["required"]["unet_name"]
        fake.object_info["UnetLoaderGGUF"]["input"]["required"]["unet_name"] = ["COMBO", {"options": ["only-another-model.gguf"], "multiselect": False}]
        status, body = h.post("/api/shots", SHOT)
        err = (body or {}).get("error", {}) if isinstance(body, dict) else {}
        report.check(status == 503 and err.get("code") == "comfy_models_missing" and "ltx-2-19b-distilled_Q4_K_M.gguf" in err.get("message", "") and "unet_name" in err.get("message", ""),
                     f"a model file that ComfyUI does not list must be refused at once with 503 comfy_models_missing naming file and input; got {status} {str(body)[:300]}")
        fake.object_info["UnetLoaderGGUF"]["input"]["required"]["unet_name"] = unet
        status, body = h.post("/api/shots", {**SHOT, "seed": 5})
        report.check(status == 201, f"with the nodes and models present the shot is accepted (the uploaded LoadVideo file is not checked); got {status} {str(body)[:200]}")
        if status == 201:
            h.wait_for_shot(body["id"], "done", timeout=90)

        # ---- a busy ComfyUI (slow to answer the health check) must not fail a healthy shot
        fake.reset_cache()
        fake.hold_at("SamplerCustomAdvanced")
        sid = make(h, 1)
        h.wait_until(sid, lambda r: r["status"] == "generating", what="the shot generating")
        fake.stall_health(24)
        time.sleep(26)
        rec = h.get(f"/api/shots/{sid}")[1]
        report.check(rec["status"] == "generating", f"ComfyUI answering the health check slowly for 24 s must not fail a running shot; the shot is {rec['status']} {rec.get('error')}")
        fake.release()
        try:
            h.wait_for_shot(sid, "done", timeout=90)
        except AssertionError as exc:
            report.problems.append(f"the shot that ran while ComfyUI was busy must finish: {exc}")

        # ---- transient errors while polling (the proxy answers 503) must not fail the shot
        fake.reset_cache()
        fake.hold_at("SamplerCustomAdvanced")
        sid = make(h, 2)
        h.wait_until(sid, lambda r: r["status"] == "generating", what="the shot generating")
        fake.drop_connections(["/history", "/queue"], 9)
        fake.release()
        try:
            rec = h.wait_for_shot(sid, "done", timeout=120)
            report.check(rec["error"] is None and rec["before_url"] and len(rec["versions"]) == 1, f"the shot must finish normally after a short ComfyUI hiccup; got {rec}")
        except AssertionError as exc:
            report.problems.append(f"a few seconds of dropped connections between the app and ComfyUI must not fail the shot: {exc}")

        time.sleep(10)  # the dropped-connection window of the last check is over

        # ---- real progress: the generation bar must not reach its end before the video is decoded
        fake.reset_cache()
        fake.hold_at("VAEDecodeTiled")
        sid = make(h, 3)
        rec = wait_message(h, sid, lambda r: r["status"] == "generating" and r["progress"] > 0.3, timeout=30)
        time.sleep(1.5)
        rec = h.get(f"/api/shots/{sid}")[1]
        stage = rec["stages"][0]
        report.check(0.3 < rec["progress"] < 0.85 and stage["progress"] < 1.0,
                     f"with both samplers finished and the decode still to do, the overall progress must be between 0.3 and 0.85 and the generate stage below 1 (real ComfyUI sends sampler-step frames of 1.0 after each sampler); got progress {rec['progress']}, stage {stage}")
        report.check(rec["message"] and rec["message"] != "Waiting for ComfyUI", f"the message must say what is happening; got {rec['message']!r}")
        fake.release()
        h.wait_for_shot(sid, "done", timeout=90)

        # ---- optics status text from the real node ids
        fake.reset_cache()
        fake.hold_at("DA3Inference")
        sid = make(h, 4)
        rec = wait_message(h, sid, lambda r: r["status"] == "optics" and r["message"] == "Estimating depth", timeout=30)
        report.check(rec["status"] == "optics" and rec["message"] == "Estimating depth", f"while ComfyUI runs the depth node the message must be 'Estimating depth'; got {rec['status']} {rec['message']!r}")
        fake.release()
        done = h.wait_for_shot(sid, "done", timeout=90)

        # ---- public record: exact keys and formats
        report.check(set(done) == RECORD_KEYS, f"the shot record must have exactly the keys of docs/app-spec.md 4.1; extra {sorted(set(done) - RECORD_KEYS)}, missing {sorted(RECORD_KEYS - set(done))}")
        report.check(ISO_Z.match(done["created_at"] or "") and all(ISO_Z.match(v["created_at"] or "") for v in done["versions"]), f"created_at must look like 2026-10-19T22:15:30Z; got {done['created_at']!r} / {[v['created_at'] for v in done['versions']]}")

        # ---- re-apply: elapsed time and the message of the depth-of-field node
        time.sleep(6)
        fake.hold_at("OpenOptics_DepthOfField")
        status, _ = h.post(f"/api/shots/{sid}/reapply", {"aperture": 8})
        rec = wait_message(h, sid, lambda r: r["status"] == "optics" and r["message"] == "Applying depth of field", timeout=30)
        report.check(rec["message"] == "Applying depth of field", f"while ComfyUI runs Depth of Field the message must be 'Applying depth of field'; got {rec['message']!r}")
        report.check(rec["elapsed_s"] < 5, f"a re-apply counts its own elapsed time (the shot is older than 6 s); got {rec['elapsed_s']}")
        report.check(rec["progress"] < 0.95 and rec["stages"][0]["state"] == "done" and rec["stages"][1]["state"] == "active", f"during a re-apply progress covers the optics stage only; got {rec['progress']} {rec['stages']}")
        fake.release()
        h.wait_for_shot(sid, "done", timeout=60)

        # ---- cancel leaves no stage active, a cancelled record has no error
        fake.reset_cache()
        fake.hold_at("SamplerCustomAdvanced")
        sid2 = make(h, 5)
        h.wait_until(sid2, lambda r: r["status"] == "generating", what="the shot generating")
        status, rec = h.post(f"/api/shots/{sid2}/cancel")
        rec = h.get(f"/api/shots/{sid2}")[1]
        report.check(rec["status"] == "cancelled" and not any(s["state"] == "active" for s in rec["stages"]) and rec["error"] is None,
                     f"a cancelled shot has no active stage and no error; got {rec['status']} {rec['stages']} {rec['error']}")
        fake.release()

        # ---- a restart: the interrupted shot reads as failed, nothing internal leaks
        fake.reset_cache()
        fake.hold_at("SamplerCustomAdvanced")
        sid3 = make(h, 6)
        h.wait_until(sid3, lambda r: r["status"] == "generating", what="the shot generating")
        h.restart_app()
        fake.release()
        rec = h.get(f"/api/shots/{sid3}")[1]
        report.check(rec["status"] == "failed" and (rec.get("error") or {}).get("code") == "interrupted" and rec["message"] == rec["error"]["message"],
                     f"after a restart the interrupted shot's message must be its error message (not the stale 'Generating video' line); got {rec['message']!r} / {rec.get('error')}")
        report.check(set(rec) == RECORD_KEYS, f"the interrupted record must have exactly the spec keys; extra {sorted(set(rec) - RECORD_KEYS)}")

        # ---- the media route serves only the videos
        done = h.get(f"/api/shots/{sid}")[1]
        name = done["before_url"].rsplit("/", 1)[-1]
        report.check(h.request("GET", f"/media/{sid}/{name}")[0] == 200, "the before video must be served")
        for bad in ("shot.json", "C:x", "C%3Ax", "..%5Cshot.json", "..%2Fshot.json", "after_1.webm.part", "before.exe"):
            code = h.request("GET", f"/media/{sid}/{bad}")[0]
            report.check(code in (400, 404), f"/media/{sid}/{bad} must not be served (400 or 404); got {code}")


try:
    run()
except Exception as exc:  # noqa: BLE001
    import traceback
    report.problems.append(f"the check itself stopped: {type(exc).__name__}: {exc}\n{traceback.format_exc()[-1500:]}")
report.finish()
