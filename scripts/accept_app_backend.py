"""Goal check: the app server (backend). Run with: node scripts/run-py.js scripts/accept_app_backend.py

Starts the real app (`python -m app`) against the fake ComfyUI server (tests/fake_comfy.py) and drives the whole HTTP API of
docs/app-spec.md section 4: health, options, estimate, shots, events, media, re-apply, cancel, failures, ComfyUI going away
and coming back, restart, delete. Prints one line per problem and exits 1 if there is any.
"""
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _app_accept import ROOT, Report, SseCollector, protected_files_unchanged  # noqa: E402

report = Report("app backend")
protected_files_unchanged(report)
if report.problems:
    report.finish()

try:
    from app import shot as shotmod
except Exception as exc:
    print(f"cannot import app.shot: {type(exc).__name__}: {exc}")
    sys.exit(1)
from tests.app_harness import SHOT, AppHarness  # noqa: E402
from tests.fake_comfy import FIXTURES, validate_prompt  # noqa: E402

help_run = subprocess.run([sys.executable, "-m", "app", "--help"], cwd=str(ROOT), capture_output=True, text=True, timeout=60)
report.check(help_run.returncode == 0, f"`python -m app --help` must exit 0; got {help_run.returncode}: {help_run.stderr[-300:]}")
for flag in ("--comfyui", "--port", "--host", "--proxy-port", "--proxy-url", "--data-dir"):
    report.check(flag in help_run.stdout, f"`python -m app --help` must list {flag}")
if report.problems:
    report.finish()


def err(h, status_body, code, status):
    got_status, body = status_body
    ok = got_status == status and isinstance(body, dict) and isinstance(body.get("error"), dict) and body["error"].get("code") == code
    return ok, f"expected HTTP {status} with error.code {code!r}; got HTTP {got_status} {str(body)[:200]}"


def run():
    with AppHarness() as h:
        fake = h.fake
        # ---- start-up, static page, health, options, estimate
        status, health = h.get("/api/health")
        report.check(status == 200 and health.get("app") == "ok", f"/api/health must answer 200 with app 'ok'; got {status} {health}")
        comfy = (health or {}).get("comfyui", {})
        report.check(comfy.get("reachable") is True and comfy.get("url") == fake.url and isinstance(comfy.get("device"), str) and comfy["device"], f"/api/health comfyui must say reachable true, the url {fake.url} and a device name; got {comfy}")
        status, page = h.request("GET", "/")
        report.check(status == 200, f"GET / must answer 200; got {status}")
        status, options = h.get("/api/options")
        report.check(status == 200 and options.get("lenses") == [24, 35, 50, 85] and [float(a) for a in options.get("apertures", [])] == [1.4, 2, 2.8, 4, 5.6, 8, 11, 16], f"/api/options wrong: {options}")
        report.check([c["id"] for c in options.get("cameras", [])] == ["static", "dolly-in", "dolly-out", "pan-left", "pan-right", "tilt-up", "orbit", "handheld"], "/api/options cameras must list the eight camera ids in order")
        report.check([f["id"] for f in options.get("framings", [])] == ["close-up", "waist-up", "full-body", "wide"], "/api/options framings must list the four framing ids in order")
        report.check([f["label"] for f in options.get("framings", [])] == ["Close-up", "Waist-up", "Full body", "Wide"], "/api/options framing labels must be Close-up, Waist-up, Full body, Wide")
        report.check(options.get("defaults") == {"camera": "static", "lens_mm": 50, "aperture": 2.8, "framing": "full-body"}, f"/api/options defaults wrong: {options.get('defaults')}")
        status, est = h.get("/api/estimate?lens_mm=50&framing=full-body")
        report.check(status == 200 and est == {"subject_distance_m": 5.1005, "sensor_height_mm": 19.8, "subject_height_fraction": 0.85, "real_height_m": 1.7}, f"/api/estimate wrong: {status} {est}")
        status, est = h.get("/api/estimate?lens_mm=24&framing=wide")
        report.check(status == 200 and est.get("subject_distance_m") == 5.9114, f"/api/estimate for 24 mm wide must be 5.9114; got {est}")
        ok, msg = err(h, h.get("/api/estimate?lens_mm=28&framing=wide"), "invalid_shot", 400)
        report.check(ok, "/api/estimate with lens 28: " + msg)
        ok, msg = err(h, h.get("/api/estimate?lens_mm=50"), "invalid_shot", 400)
        report.check(ok, "/api/estimate without framing: " + msg)

        # ---- invalid shots are refused before anything is created
        for patch, field in (({"description": "ab"}, "description"), ({"lens_mm": 30}, "lens_mm"), ({"aperture": 3}, "aperture"), ({"framing": "head"}, "framing"), ({"camera": "zoom"}, "camera")):
            status, body = h.post("/api/shots", {**SHOT, **patch})
            report.check(status == 400 and isinstance(body, dict) and body.get("error", {}).get("code") == "invalid_shot" and body["error"].get("field") == field and body["error"].get("message"),
                         f"POST /api/shots with {patch} must give 400 invalid_shot with field {field!r} and a message; got {status} {str(body)[:200]}")
        status, body = h.request("POST", "/api/shots", None)
        report.check(status == 400, f"POST /api/shots with no body must give 400; got {status}")
        status, listing = h.get("/api/shots")
        report.check(status == 200 and listing == {"shots": []}, f"no shot may exist after invalid requests; got {listing}")
        ok, msg = err(h, h.get("/api/shots/nope"), "not_found", 404)
        report.check(ok, "GET unknown shot: " + msg)

        # ---- a full run
        status, rec = h.post("/api/shots", SHOT)
        report.check(status == 201 and isinstance(rec, dict) and rec.get("id"), f"POST /api/shots must answer 201 with a record; got {status} {str(rec)[:300]}")
        if status != 201:
            return
        sid = rec["id"]
        report.check(rec["status"] in ("queued", "generating") and rec["params"] == {**SHOT}, f"new record: status must be queued or generating and params equal the request; got {rec['status']} {rec['params']}")
        report.check(rec["derived"]["subject_distance_m"] == 5.1005 or abs(rec["derived"]["subject_distance_m"] - 5.1005) < 6e-5, f"derived.subject_distance_m must be 5.1005; got {rec['derived']}")
        report.check(rec["derived"]["prompt"] == shotmod.build_prompt(rec["params"]), "derived.prompt must be build_prompt(params)")
        report.check([s["id"] for s in rec["stages"]] == ["generate", "optics"], f"stages must be generate, optics; got {rec['stages']}")
        collector = SseCollector(h, sid)
        final = h.wait_for_shot(sid, "done", timeout=90)
        report.check(collector.join(30), "the events stream must end after the shot is done")
        recs = collector.records
        report.check(len(recs) >= 3 and collector.events[0] == "shot", f"the events stream must start with a 'shot' frame and carry several updates; got {len(recs)} frames {collector.events[:5]}")
        order = ["queued", "generating", "optics", "done"]
        seen = [r["status"] for r in recs]
        ranks = [order.index(s) for s in seen if s in order]
        report.check(ranks == sorted(ranks) and seen and seen[-1] == "done" and "generating" in seen and "optics" in seen, f"statuses over SSE must go queued/generating/optics/done in order; got {seen}")
        progress = [r["progress"] for r in recs]
        report.check(all(0 <= p <= 1 for p in progress) and progress == sorted(progress) and progress[-1] == 1, f"progress must rise from 0 to 1 and never fall; got {progress}")
        report.check(any(0 < p < 1 for p in progress), "progress must be reported between 0 and 1 while running")
        report.check(any(r["message"] and r["status"] == "generating" for r in recs), "a generating update must carry a message")
        report.check(final["progress"] == 1 and [s["state"] for s in final["stages"]] == ["done", "done"] and final["error"] is None, f"final record wrong: {final}")
        report.check(final["elapsed_s"] > 0 and final["before_url"] and len(final["versions"]) == 1 and final["current_version"] == 1, f"final record wrong: {final}")
        v1 = final["versions"][0]
        report.check(v1["n"] == 1 and v1["aperture"] == 2.8 and v1["url"], f"first version wrong: {v1}")

        # ---- media
        import urllib.request
        before_bytes = urllib.request.urlopen(h.url + final["before_url"], timeout=15).read()
        after_bytes = urllib.request.urlopen(h.url + v1["url"], timeout=15).read()
        report.check(before_bytes == (FIXTURES / "clip_sharp.webm").read_bytes(), "the before video must be the file ComfyUI's generation produced (the sharp fixture)")
        report.check(after_bytes == (FIXTURES / "clip_soft.webm").read_bytes(), "the after video must be the file ComfyUI's optics run produced (the soft fixture)")
        req = urllib.request.Request(h.url + final["before_url"], headers={"Range": "bytes=0-99"})
        with urllib.request.urlopen(req, timeout=15) as r:
            body = r.read()
            report.check(r.status == 206 and len(body) == 100 and "bytes 0-99/" in (r.headers.get("Content-Range") or "") and (r.headers.get("Content-Type") or "").startswith("video/"),
                         f"a Range request must give 206 with 100 bytes, Content-Range and a video Content-Type; got {r.status} {len(body)} {r.headers.get('Content-Range')} {r.headers.get('Content-Type')}")
        report.check(h.request("GET", f"/media/{sid}/missing.webm")[0] == 404, "GET of a missing media file must answer 404")

        # ---- what the app sent to ComfyUI
        gen_graph, optics_graph = fake.prompts[0], fake.prompts[1] if len(fake.prompts) > 1 else {}
        report.check(len(fake.prompts) == 2, f"a shot must submit exactly two graphs (generation, optics); ComfyUI got {len(fake.prompts)}")
        problems = validate_prompt(gen_graph, input_files=fake._input_files())
        report.check(not problems, f"the generation graph is not valid for ComfyUI: {problems[:3]}")
        texts = [n["inputs"].get("text") for n in gen_graph.values() if n["class_type"] == "CLIPTextEncode"]
        report.check(texts == [final["derived"]["prompt"]], "the generation graph's CLIPTextEncode must carry derived.prompt")
        seeds = sorted(n["inputs"]["noise_seed"] for n in gen_graph.values() if n["class_type"] == "RandomNoise")
        report.check(seeds == [SHOT["seed"], SHOT["seed"] + 378], f"RandomNoise seeds must be the shot's seed and seed + 378; got {seeds}")
        prefixes = [n["inputs"]["filename_prefix"] for n in gen_graph.values() if n["class_type"] == "SaveVideo"]
        report.check(prefixes == [f"opencinema/{sid}/before"], f"generation SaveVideo prefix must be opencinema/<id>/before; got {prefixes}")
        report.check(len(fake.uploads) == 1, f"the before video must be uploaded to ComfyUI once; uploads: {fake.uploads}")
        load = [n["inputs"]["file"] for n in optics_graph.values() if n["class_type"] == "LoadVideo"]
        report.check(load == fake.uploads[:1], f"LoadVideo must read the uploaded file; LoadVideo {load}, uploads {fake.uploads}")
        d2m = [e["inputs"] for e in fake.executed if e["class_type"] == "OpenOptics_DepthToMetric"]
        dof = [e["inputs"] for e in fake.executed if e["class_type"] == "OpenOptics_DepthOfField"]
        report.check(len(d2m) == 1 and d2m[0].get("mode") == "subject" and abs(d2m[0].get("subject_m", 0) - 5.1005) < 6e-5, f"DepthToMetric must run in subject mode at the framing distance; got {d2m}")
        report.check(len(dof) == 1 and dof[0].get("focal_mm") == 50 and dof[0].get("f_number") == 2.8 and abs(dof[0].get("focus_m", 0) - 5.1005) < 6e-5, f"DepthOfField must get the lens, the aperture and focus_m = the subject distance; got {dof}")
        gen_count = fake.count("SamplerCustomAdvanced")
        report.check(gen_count == 2, f"generation must run the two LTX-2 sampler passes once; ran {gen_count}")

        # ---- re-apply: aperture change without regenerating
        before_counts = {t: fake.count(t) for t in ("SamplerCustomAdvanced", "DA3Inference", "OpenOptics_DepthOfField", "UnetLoaderGGUF")}
        for patch, code, st in (({"aperture": 3}, "invalid_shot", 400), ({}, "invalid_shot", 400)):
            ok, msg = err(h, h.post(f"/api/shots/{sid}/reapply", patch), code, st)
            report.check(ok, f"reapply with {patch}: " + msg)
        ok, msg = err(h, h.post("/api/shots/nope/reapply", {"aperture": 8}), "not_found", 404)
        report.check(ok, "reapply of an unknown shot: " + msg)
        fake.hold_at("OpenOptics_DepthOfField")
        status, rec2 = h.post(f"/api/shots/{sid}/reapply", {"aperture": 8})
        report.check(status == 202 and rec2.get("status") == "optics", f"reapply must answer 202 with status optics; got {status} {str(rec2)[:200]}")
        busy = h.wait_until(sid, lambda r: r["status"] == "optics" and r["stages"][1]["state"] == "active", what="the re-apply running")
        report.check(busy["stages"][0]["state"] == "done" and busy["before_url"] and len(busy["versions"]) == 1, f"during a re-apply the generate stage stays done and the old version stays available; got {busy['stages']} {busy['versions']}")
        ok, msg = err(h, h.post(f"/api/shots/{sid}/reapply", {"aperture": 4}), "busy", 409)
        report.check(ok, "reapply while a re-apply runs: " + msg)
        ok, msg = err(h, h.request("DELETE", f"/api/shots/{sid}"), "busy", 409)
        report.check(ok, "delete while a re-apply runs: " + msg)
        fake.release()
        redone = h.wait_for_shot(sid, "done")
        report.check([v["aperture"] for v in redone["versions"]] == [2.8, 8] and redone["current_version"] == 2 and [v["n"] for v in redone["versions"]] == [1, 2], f"versions after re-apply wrong: {redone['versions']} current {redone['current_version']}")
        after_counts = {t: fake.count(t) for t in before_counts}
        report.check(after_counts["SamplerCustomAdvanced"] == before_counts["SamplerCustomAdvanced"] and after_counts["UnetLoaderGGUF"] == before_counts["UnetLoaderGGUF"], f"a re-apply must not run LTX-2 again; counts before {before_counts} after {after_counts}")
        report.check(after_counts["DA3Inference"] == before_counts["DA3Inference"], "a re-apply must reuse ComfyUI's cached depth (the optics graph must be identical except for f_number); DA3Inference ran again")
        report.check(after_counts["OpenOptics_DepthOfField"] == before_counts["OpenOptics_DepthOfField"] + 1, "a re-apply must run Depth of Field once")
        last = [e["inputs"] for e in fake.executed if e["class_type"] == "OpenOptics_DepthOfField"][-1]
        report.check(last.get("f_number") == 8 and last.get("focal_mm") == 50 and abs(last.get("focus_m", 0) - 5.1005) < 6e-5, f"re-applied Depth of Field inputs wrong: {last}")
        report.check(len(fake.uploads) == 1, f"a re-apply must reuse the uploaded video (uploads: {fake.uploads})")

        # ---- busy shot: queue, 409s, cancel
        fake.hold_at("SamplerCustomAdvanced")
        status, second = h.post("/api/shots", {**SHOT, "description": "A second shot while the first holds.", "seed": 8})
        sid2 = second["id"]
        held = h.wait_until(sid2, lambda r: r["status"] == "generating" and r["progress"] >= 0, what="the second shot generating")
        report.check(bool(held["message"]) and held["stages"][0]["state"] == "active" and held["stages"][1]["state"] == "pending", f"a generating shot must have a message and stage states active/pending; got {held['message']!r} {held['stages']}")
        status, third = h.post("/api/shots", {**SHOT, "description": "A third shot waits in line.", "seed": 9})
        sid3 = third["id"]
        waiting = h.wait_until(sid3, lambda r: r["status"] == "queued", what="the third shot queued")
        report.check(waiting["progress"] == 0 and waiting["stages"][0]["state"] == "pending", f"a queued shot has progress 0 and pending stages; got {waiting}")
        ok, msg = err(h, h.post(f"/api/shots/{sid2}/reapply", {"aperture": 4}), "not_ready", 409)
        report.check(ok, "reapply of a shot without a before video: " + msg)
        ok, msg = err(h, h.request("DELETE", f"/api/shots/{sid2}"), "busy", 409)
        report.check(ok, "delete of a running shot: " + msg)
        status, cancelled = h.post(f"/api/shots/{sid3}/cancel")
        report.check(status == 200 and cancelled.get("status") == "cancelled", f"cancel of a queued shot must give 200 and status cancelled; got {status} {str(cancelled)[:200]}")
        ok, msg = err(h, h.post(f"/api/shots/{sid3}/cancel"), "not_running", 409)
        report.check(ok, "cancel of a cancelled shot: " + msg)
        status, cancelled2 = h.post(f"/api/shots/{sid2}/cancel")
        report.check(status == 200 and cancelled2.get("status") == "cancelled", f"cancel of a running shot must give 200 and status cancelled; got {status} {str(cancelled2)[:200]}")
        fake.release()
        time.sleep(0.5)
        status, after_cancel = h.get(f"/api/shots/{sid2}")
        report.check(after_cancel["status"] == "cancelled", f"a cancelled shot must stay cancelled; got {after_cancel['status']}")
        status, listing = h.get("/api/shots")
        report.check([s["id"] for s in listing["shots"]] == [sid3, sid2, sid], f"GET /api/shots must list newest first; got {[s['id'] for s in listing['shots']]}")

        # ---- a node fails in the optics stage; the before video is kept; retry with re-apply
        fake.reset_cache()  # the fixture videos are identical, so ComfyUI would serve depth from its cache and never reach the failing node
        fake.fail("DA3Inference", "CUDA out of memory")
        status, rec = h.post("/api/shots", {**SHOT, "description": "This one hits an out-of-memory error in depth.", "seed": 11})
        sid4 = rec["id"]
        failed = h.wait_for_shot(sid4, "failed")
        e = failed.get("error") or {}
        report.check(e.get("code") == "job_failed" and e.get("stage") == "optics" and "CUDA out of memory" in e.get("message", "") and "DA3Inference" in e.get("message", ""),
                     f"an optics failure must give error code job_failed, stage optics and a message with the node type and ComfyUI's text; got {e}")
        report.check(failed["before_url"] and not failed["versions"] and [s["state"] for s in failed["stages"]] == ["done", "failed"], f"a failed optics stage keeps the before video and marks the stage failed; got {failed['stages']} {failed['before_url']}")
        fake.clear_failures()
        status, retry = h.post(f"/api/shots/{sid4}/reapply", {"aperture": 4})
        report.check(status == 202, f"reapply on a failed shot with a before video must be accepted; got {status} {str(retry)[:200]}")
        recovered = h.wait_for_shot(sid4, "done")
        report.check(recovered["error"] is None and [v["aperture"] for v in recovered["versions"]] == [4], f"after a successful retry the error is cleared and version 1 has the new aperture; got {recovered['error']} {recovered['versions']}")

        # ---- a re-apply that fails on a shot with versions leaves the shot done
        fake.fail("OpenOptics_DepthOfField", "Out of memory in Depth of Field")
        status, _ = h.post(f"/api/shots/{sid}/reapply", {"aperture": 16})
        still = h.wait_until(sid, lambda r: r["status"] in ("done", "failed") and r.get("reapply_error"), what="the failed re-apply")
        report.check(still["status"] == "done" and still["reapply_error"].get("code") == "job_failed" and "Out of memory in Depth of Field" in still["reapply_error"].get("message", "") and len(still["versions"]) == 2,
                     f"a failed re-apply must leave status done, set reapply_error and add no version; got {still['status']} {still.get('reapply_error')} {len(still['versions'])} versions")
        fake.clear_failures()
        status, _ = h.post(f"/api/shots/{sid}/reapply", {"aperture": 16})
        cleared = h.wait_until(sid, lambda r: r["status"] == "done" and len(r["versions"]) == 3, what="the successful re-apply")
        report.check(cleared.get("reapply_error") is None, "the next successful re-apply must clear reapply_error")

        # ---- generation fails; ComfyUI rejects the graph
        fake.fail("SamplerCustomAdvanced", "The sampler exploded")
        status, rec = h.post("/api/shots", {**SHOT, "description": "This one fails during generation.", "seed": 12})
        failed = h.wait_for_shot(rec["id"], "failed")
        e = failed.get("error") or {}
        report.check(e.get("code") == "job_failed" and e.get("stage") == "generate" and "The sampler exploded" in e.get("message", "") and failed["before_url"] is None, f"a generation failure must give job_failed at stage generate and no before video; got {e} {failed['before_url']}")
        fake.clear_failures()
        original = fake.object_info["UnetLoaderGGUF"]["input"]["required"]["unet_name"]
        fake.object_info["UnetLoaderGGUF"]["input"]["required"]["unet_name"] = [["only-another-model.gguf"]]
        status, rec = h.post("/api/shots", {**SHOT, "description": "This one asks for a model that is missing.", "seed": 13})
        rejected = h.wait_for_shot(rec["id"], "failed")
        e = rejected.get("error") or {}
        report.check(e.get("code") == "comfy_rejected" and e.get("stage") == "generate" and "unet_name" in e.get("message", ""), f"a graph that ComfyUI refuses must give comfy_rejected with ComfyUI's text; got {e}")
        fake.object_info["UnetLoaderGGUF"]["input"]["required"]["unet_name"] = original

        # ---- ComfyUI is not running
        fake.stop()
        status, health = h.get("/api/health")
        comfy = (health or {}).get("comfyui", {})
        report.check(status == 200 and comfy.get("reachable") is False and comfy.get("message") == f"Can't reach ComfyUI at {fake.url}. Start ComfyUI, then retry.", f"health with ComfyUI stopped must say reachable false and the exact message; got {status} {comfy}")
        before_n = len(h.get("/api/shots")[1]["shots"])
        ok, msg = err(h, h.post("/api/shots", SHOT), "comfy_unreachable", 503)
        report.check(ok, "POST /api/shots with ComfyUI stopped: " + msg)
        report.check(len(h.get("/api/shots")[1]["shots"]) == before_n, "no shot may be created when ComfyUI cannot be reached")
        fake.start()
        status, health = h.get("/api/health")
        report.check(health["comfyui"]["reachable"] is True, "health must turn reachable again after ComfyUI is back")

        # ---- ComfyUI stops during a run
        fake.hold_at("SamplerCustomAdvanced")
        status, rec = h.post("/api/shots", {**SHOT, "description": "ComfyUI will be closed during this one.", "seed": 14})
        sid5 = rec["id"]
        h.wait_until(sid5, lambda r: r["status"] == "generating", what="the shot generating")
        time.sleep(0.5)
        fake.release()
        fake.stop()
        died = h.wait_for_shot(sid5, "failed", timeout=60)
        e = died.get("error") or {}
        report.check(e.get("code") == "comfy_unreachable" and e.get("stage") == "generate" and e.get("message"), f"ComfyUI stopping mid-run must give comfy_unreachable at stage generate within 30 s; got {e}")
        fake.start()

        # ---- restart keeps the shots; a shot that was running becomes interrupted
        fake.hold_at("SamplerCustomAdvanced")
        status, rec = h.post("/api/shots", {**SHOT, "description": "The app restarts during this one.", "seed": 15})
        sid6 = rec["id"]
        h.wait_until(sid6, lambda r: r["status"] == "generating", what="the shot generating")
        ids_before = [s["id"] for s in h.get("/api/shots")[1]["shots"]]
        h.restart_app()
        fake.release()
        status, listing = h.get("/api/shots")
        report.check([s["id"] for s in listing["shots"]] == ids_before, f"shots must survive a restart in the same order; before {ids_before} after {[s['id'] for s in listing['shots']]}")
        status, back = h.get(f"/api/shots/{sid6}")
        report.check(back["status"] == "failed" and (back.get("error") or {}).get("code") == "interrupted", f"a shot that was running when the app stopped must be failed/interrupted; got {back['status']} {back.get('error')}")
        status, old = h.get(f"/api/shots/{sid}")
        report.check(old["status"] == "done" and len(old["versions"]) == 3 and old["before_url"], "a finished shot must be unchanged after a restart")
        report.check(urllib.request.urlopen(h.url + old["versions"][2]["url"], timeout=15).read() == after_bytes, "stored videos must still be served after a restart")

        # ---- delete
        status, _ = h.request("DELETE", f"/api/shots/{sid6}")
        report.check(status == 204, f"DELETE of a finished shot must answer 204; got {status}")
        ok, msg = err(h, h.get(f"/api/shots/{sid6}"), "not_found", 404)
        report.check(ok, "GET of a deleted shot: " + msg)


try:
    run()
except Exception as exc:  # noqa: BLE001
    import traceback
    report.problems.append(f"the check itself stopped: {type(exc).__name__}: {exc}\n{traceback.format_exc()[-1200:]}")
report.finish()
