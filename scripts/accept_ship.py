"""Goal check: the app is ready to ship (docs/app-spec.md section 7.1). Run with: node scripts/run-py.js scripts/accept_ship.py

Checks the download header and link, the same-origin refusal, the hardened upload route, the committed workflow files and
the model setup command (against a local HTTP server, never the internet). Prints one line per problem and exits 1 if
there is any.
"""
import contextlib
import http.server
import io
import json
import os
import re
import shutil
import socketserver
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _app_accept import ROOT, Page, Report, browser, protected_files_unchanged, set_range  # noqa: E402

report = Report("ship")
protected_files_unchanged(report)
if report.problems:
    report.finish()

from tests.app_harness import SHOT, AppHarness  # noqa: E402
from tests.fake_comfy import validate_prompt  # noqa: E402

CLIP = ROOT / "app" / "samples" / "sample-red-coat" / "before.mp4"


def raw(url, method="GET", body=None, headers=None, timeout=30):
    req = urllib.request.Request(url, data=body, method=method, headers=headers or {})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, dict(r.headers), r.read()
    except urllib.error.HTTPError as e:
        return e.code, dict(e.headers), e.read()


def jbody(data):
    try:
        return json.loads(data)
    except ValueError:
        return None


def multipart(parts, boundary="----accept"):
    """parts: list of (name, value bytes|str, filename or None)."""
    out = b""
    for name, value, filename in parts:
        disp = f'form-data; name="{name}"' + (f'; filename="{filename}"' if filename else "")
        head = f"--{boundary}\r\nContent-Disposition: {disp}\r\n" + ("Content-Type: video/mp4\r\n" if filename else "") + "\r\n"
        out += head.encode() + (value if isinstance(value, bytes) else value.encode()) + b"\r\n"
    out += f"--{boundary}--\r\n".encode()
    return out, {"Content-Type": f"multipart/form-data; boundary={boundary}"}


FORM = [("lens_mm", "50", None), ("aperture", "2.8", None), ("framing", "waist-up", None)]


def check_server():
    with AppHarness(delay=0.02) as h:
        status, rec = h.post("/api/shots", {**SHOT, "seed": 5})
        report.check(status == 201, f"POST /api/shots without an Origin header must still work; got {status} {rec}")
        done = h.wait_for_shot(rec["id"], "done", timeout=90)
        url = done["versions"][0]["url"]

        # ---- download header
        st, hd, _ = raw(h.url + url)
        report.check(st == 200 and not any(k.lower() == "content-disposition" for k in hd), f"GET {url} without download=1 must have no Content-Disposition; got {st} {hd}")
        st, hd, body = raw(h.url + url + "?download=1")
        cd = next((v for k, v in hd.items() if k.lower() == "content-disposition"), "")
        name = url.rsplit("/", 1)[1]
        report.check(st == 200 and len(body) > 0 and cd == f'attachment; filename="opencinema-{done["id"]}-{name}"', f"GET {url}?download=1 must send Content-Disposition attachment; filename=\"opencinema-{done['id']}-{name}\"; got {st} {cd!r}")

        # ---- same-origin
        evil = {"Content-Type": "application/json", "Origin": "http://evil.example"}
        st, _, b = raw(h.url + "/api/shots", "POST", json.dumps({**SHOT, "seed": 6}).encode(), evil)
        err = (jbody(b) or {}).get("error") or {}
        report.check(st == 403 and err.get("code") == "forbidden_origin" and err.get("message") == "Requests from other sites are not allowed.", f"a POST from another origin must be 403 forbidden_origin; got {st} {b[:200]!r}")
        _, listing = h.get("/api/shots")
        report.check(len(listing["shots"]) == 1, "a refused cross-origin POST must not create a shot")
        st, _, b = raw(h.url + f"/api/shots/{done['id']}", "DELETE", None, {"Origin": "http://evil.example"})
        report.check(st == 403, f"a DELETE from another origin must be 403; got {st}")
        st, _, b = raw(h.url + f"/api/shots/{done['id']}/reapply", "POST", json.dumps({"aperture": 8}).encode(), {"Content-Type": "application/json", "Origin": "http://localhost:1"})
        report.check(st == 403, f"a re-apply from another origin must be 403; got {st}")
        own = {"Content-Type": "application/json", "Origin": f"http://127.0.0.1:{h.port}"}
        st, _, b = raw(h.url + f"/api/shots/{done['id']}/reapply", "POST", json.dumps({"aperture": 8}).encode(), own)
        report.check(st == 202, f"a re-apply from the app's own origin must be accepted; got {st} {b[:200]!r}")
        h.wait_until(done["id"], lambda s: s["status"] == "done" and len(s["versions"]) == 2, what="the f/8 version")
        body, hdrs = multipart(FORM + [("file", CLIP.read_bytes(), "clip.mp4")])
        st, _, b = raw(h.url + "/api/shots/import", "POST", body, {**hdrs, "Origin": "http://evil.example"})
        report.check(st == 403, f"an upload from another origin must be 403; got {st}")

        # ---- upload hardening
        data_dir = h.data_dir

        def leftovers():
            return [p.name for p in Path(data_dir).rglob(".import-*")]

        body, hdrs = multipart(FORM + [("file", CLIP.read_bytes(), "a.mp4"), ("file", CLIP.read_bytes(), "b.mp4")])
        st, _, b = raw(h.url + "/api/shots/import", "POST", body, hdrs)
        err = (jbody(b) or {}).get("error") or {}
        report.check(st == 400 and err.get("field") == "file" and err.get("message") == "Send one video file.", f"two file parts must be 400 invalid_shot field file 'Send one video file.'; got {st} {err}")
        body, hdrs = multipart(FORM + [(f"x{i}", "1", None) for i in range(8)] + [("file", CLIP.read_bytes(), "a.mp4")])
        st, _, b = raw(h.url + "/api/shots/import", "POST", body, hdrs)
        report.check(st == 400, f"more than 10 parts must be 400; got {st} {b[:200]!r}")
        body, hdrs = multipart([("name", "n" * 5000, None)] + FORM + [("file", CLIP.read_bytes(), "a.mp4")])
        st, _, b = raw(h.url + "/api/shots/import", "POST", body, hdrs)
        err = (jbody(b) or {}).get("error") or {}
        report.check(st == 400 and err.get("field") == "name", f"a 5000-byte text part 'name' must be 400 with field 'name'; got {st} {err}")
        time.sleep(0.3)
        report.check(not leftovers(), f"refused uploads must leave no .import-* files; found {leftovers()}")
        _, listing = h.get("/api/shots")
        report.check(len(listing["shots"]) == 1, "refused uploads must not create shots")

        stale = Path(data_dir) / ".import-dead.part"
        stale.write_bytes(b"x" * 10)
        h.restart_app()
        report.check(not stale.exists(), "a leftover .import-*.part file in the data folder must be deleted on start-up")
        return h.data_dir


def check_ui():
    with AppHarness(delay=0.02) as h, browser() as b:
        status, rec = h.post("/api/shots", {**SHOT, "aperture": 2.8, "seed": 9})
        done = h.wait_for_shot(rec["id"], "done", timeout=90)
        h.post(f"/api/shots/{rec['id']}/reapply", {"aperture": 8})
        done = h.wait_until(rec["id"], lambda s: s["status"] == "done" and len(s["versions"]) == 2, what="the f/8 version")
        p = Page(b, h, 1280, 720).open()
        end = time.time() + 20
        while time.time() < end and p.t("viewport").get_attribute("data-state") != "result":
            p.page.wait_for_timeout(100)
        link = p.t("download-link")
        report.check(link.count() == 1 and link.is_visible(), "download-link must be visible in result state")
        if link.count() == 1:
            v2 = done["versions"][1]["url"]
            report.check(link.evaluate("e => e.tagName") == "A" and link.get_attribute("download") is not None, "download-link must be an <a> with a download attribute")
            report.check((link.get_attribute("href") or "").endswith(v2 + "?download=1"), f"download-link must point at the shown (latest) version + ?download=1; got {link.get_attribute('href')!r}")
            report.check(link.inner_text().strip() == "Download" and link.get_attribute("aria-label") == "Download the f/8 version", f"download-link text 'Download' and aria-label 'Download the f/8 version'; got {link.inner_text()!r} {link.get_attribute('aria-label')!r}")
            p.t("version-chip").nth(0).click()
            p.page.wait_for_timeout(300)
            v1 = done["versions"][0]["url"]
            report.check((link.get_attribute("href") or "").endswith(v1 + "?download=1") and link.get_attribute("aria-label") == "Download the f/2.8 version", f"after clicking the first chip download-link must follow it; got {link.get_attribute('href')!r} {link.get_attribute('aria-label')!r}")
            st, hd, _ = raw(h.url + v1 + "?download=1")
            report.check(st == 200, "the download link must work")
        report.check(not p.errors, "the page must log no errors: " + "; ".join(p.errors[:5]))
        p.close()


def check_workflows():
    from app import graphs
    from app.shot import build_prompt
    try:
        from app import export_workflows as ew
    except Exception as exc:  # noqa: BLE001
        report.problems.append(f"app.export_workflows must import: {exc}")
        return
    shot = {"description": "A saxophone player on a rain-wet night street, neon reflections in the puddles", "camera": "dolly-in", "lens_mm": 50, "framing": "waist-up"}
    report.check(getattr(ew, "EXAMPLE_PROMPT", None) == build_prompt(shot), "EXAMPLE_PROMPT must be build_prompt of the example shot in section 7.1")
    want = {
        "open_cinema_generate.json": graphs.build_generation_graph(build_prompt(shot), 42, "opencinema/example/before"),
        "open_cinema_optics.json": graphs.build_optics_graph("example.mp4", 50, 2.8, 5.1005, "opencinema/example/after"),
    }
    for name, graph in want.items():
        path = ROOT / "workflows" / name
        text = json.dumps(graph, indent=2) + "\n"
        report.check(path.exists() and path.read_text(encoding="utf-8").replace("\r\n", "\n") == text, f"workflows/{name} must be exactly json.dumps(graph, indent=2) + newline of the current builder output")
        files = ["example.mp4"] if "optics" in name else []
        problems = validate_prompt(graph, input_files=files)
        report.check(not problems, f"{name} graph must validate against the node definitions: {problems[:3]}")
    tmp = Path(tempfile.mkdtemp(prefix="oc_wf_"))
    try:
        written = ew.export(tmp)
        report.check(sorted(Path(p).name for p in written) == sorted(want), f"export(dest) must return the two written paths; got {written}")
        for name in want:
            report.check((tmp / name).exists() and (tmp / name).read_text(encoding="utf-8").replace("\r\n", "\n") == (ROOT / "workflows" / name).read_text(encoding="utf-8").replace("\r\n", "\n"), f"export must write the same {name} as the committed one")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    report.check(re.search(r"^#+ .*Use the graphs in ComfyUI", readme, re.M) is not None, "README needs a section 'Use the graphs in ComfyUI'")
    report.check("python -m app.setup" in readme and "--download" in readme, "README must show python -m app.setup ... --download")


SPEC_MODELS = [
    ("ltx-2-19b-distilled_Q4_K_M.gguf", "diffusion_models", "https://huggingface.co/Kijai/LTXV2_comfy/resolve/main/diffusion_models/ltx-2-19b-distilled_Q4_K_M.gguf", 12651789536, True),
    ("gemma_3_12B_it_fp8_scaled.safetensors", "text_encoders", "https://huggingface.co/Comfy-Org/ltx-2/resolve/main/split_files/text_encoders/gemma_3_12B_it_fp8_scaled.safetensors", 13205434827, True),
    ("ltx-2-19b-embeddings_connector_distill_bf16.safetensors", "checkpoints", "https://huggingface.co/Kijai/LTXV2_comfy/resolve/main/text_encoders/ltx-2-19b-embeddings_connector_distill_bf16.safetensors", 2862983784, True),
    ("LTX2_audio_vae_bf16.safetensors", "checkpoints", "https://huggingface.co/Kijai/LTXV2_comfy/resolve/main/VAE/LTX2_audio_vae_bf16.safetensors", 217740136, True),
    ("LTX2_video_vae_bf16.safetensors", "vae", "https://huggingface.co/Kijai/LTXV2_comfy/resolve/main/VAE/LTX2_video_vae_bf16.safetensors", 2445008522, True),
    ("ltx-2-spatial-upscaler-x2-1.0.safetensors", "latent_upscale_models", "https://huggingface.co/Lightricks/LTX-2/resolve/main/ltx-2-spatial-upscaler-x2-1.0.safetensors", 995765578, True),
    ("depth_anything_3_mono_large.safetensors", "geometry_estimation", "https://huggingface.co/Comfy-Org/Depth-Anything-3/resolve/main/geometry_estimation/depth_anything_3_mono_large.safetensors", 1336748056, True),
] + [
    (f"ltx-2-19b-lora-camera-control-{m}.safetensors", "loras",
     f"https://huggingface.co/Lightricks/LTX-2-19b-LoRA-Camera-Control-{'-'.join(w.capitalize() for w in m.split('-'))}/resolve/main/ltx-2-19b-lora-camera-control-{m}.safetensors",
     327309208 if m.startswith("dolly") else 2214978664, False)
    for m in ["dolly-in", "dolly-out", "dolly-left", "dolly-right", "jib-up", "jib-down", "static"]
]


class _Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a):
        pass


def check_setup():
    try:
        from app import setup
    except Exception as exc:  # noqa: BLE001
        report.problems.append(f"app.setup must import: {exc}")
        return
    got = [(m.get("name"), m.get("folder"), m.get("url"), m.get("size"), m.get("required")) for m in getattr(setup, "MODELS", [])]
    report.check(got == SPEC_MODELS, "app.setup.MODELS must be exactly the table of section 7.1 (names, folders, urls, sizes, required) in order; first difference: "
                 + next((f"{a} != {b}" for a, b in zip(got, SPEC_MODELS) if a != b), f"length {len(got)} vs {len(SPEC_MODELS)}"))

    serve = Path(tempfile.mkdtemp(prefix="oc_srv_"))
    comfy = Path(tempfile.mkdtemp(prefix="oc_comfy_"))
    try:
        (serve / "a.bin").write_bytes(os.urandom(3_000_000))
        (serve / "b.bin").write_bytes(os.urandom(1000))
        (serve / "c.bin").write_bytes(os.urandom(500))
        handler = lambda *a, **k: _Quiet(*a, directory=str(serve), **k)  # noqa: E731
        httpd = socketserver.ThreadingTCPServer(("127.0.0.1", 0), handler)
        threading.Thread(target=httpd.serve_forever, daemon=True).start()
        base = f"http://127.0.0.1:{httpd.server_address[1]}"
        models = [
            {"name": "big.gguf", "folder": "diffusion_models", "url": f"{base}/a.bin", "size": 3_000_000, "required": True},
            {"name": "small.safetensors", "folder": "vae", "url": f"{base}/b.bin", "size": 1000, "required": True},
            {"name": "extra.safetensors", "folder": "loras", "url": f"{base}/c.bin", "size": 500, "required": False},
        ]

        def run(argv):
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                try:
                    code = setup.main(argv, models=models)
                except SystemExit as e:
                    code = e.code
            return code, buf.getvalue()

        code, out = run(["--comfyui-dir", str(comfy / "nope")])
        report.check(code == 2, f"a --comfyui-dir without models/ must exit 2; got {code}: {out[-200:]}")
        (comfy / "models").mkdir()
        (comfy / "custom_nodes" / "ComfyUI-GGUF").mkdir(parents=True)
        (comfy / "custom_nodes" / "open-cinema" / "open_optics_nodes").mkdir(parents=True)
        (comfy / "models" / "vae").mkdir()
        (comfy / "models" / "vae" / "small.safetensors").write_bytes(b"x" * 10)
        code, out = run(["--comfyui-dir", str(comfy)])
        report.check(code == 1, f"missing required files must exit 1; got {code}")
        report.check(re.search(r"^MISSING\s+models/diffusion_models/big\.gguf\s+\(0\.00 GB, " + re.escape(models[0]["url"]) + r"\)", out, re.M) is not None, f"a missing file must print 'MISSING  models/<folder>/<name>  (<GB> GB, <url>)'; got:\n{out}")
        report.check(re.search(r"^WRONG SIZE\s+models/vae/small\.safetensors\s+\(10 bytes, expected 1000\)", out, re.M) is not None, f"a wrong-size file must print 'WRONG SIZE ... (10 bytes, expected 1000)'; got:\n{out}")
        report.check(re.search(r"^MISSING\s+models/loras/extra\.safetensors.*\(optional\)\s*$", out, re.M) is not None, f"a missing optional file must end with (optional); got:\n{out}")
        report.check("2 required item(s) missing." in out, f"summary must be '2 required item(s) missing.'; got:\n{out}")
        report.check(not (comfy / "models" / "diffusion_models" / "big.gguf").exists(), "without --download nothing may be downloaded")
        code, out = run(["--comfyui-dir", str(comfy), "--download", "--only-required"])
        report.check(code == 0 and (comfy / "models" / "diffusion_models" / "big.gguf").read_bytes() == (serve / "a.bin").read_bytes(), f"--download must fetch the missing file and exit 0; got {code}:\n{out[-400:]}")
        report.check((comfy / "models" / "vae" / "small.safetensors").stat().st_size == 1000, "--download must replace a wrong-size file")
        report.check(not (comfy / "models" / "loras" / "extra.safetensors").exists(), "--only-required must skip optional files")
        report.check(not list(comfy.rglob("*.part")), "no .part files may be left behind")
        code, out = run(["--comfyui-dir", str(comfy)])
        report.check(code == 0 and "All required files are in place." in out and re.search(r"^OK\s+models/diffusion_models/big\.gguf", out, re.M), f"after downloading the check must say OK and 'All required files are in place.'; got {code}:\n{out}")
        shutil.rmtree(comfy / "custom_nodes" / "ComfyUI-GGUF")
        code, out = run(["--comfyui-dir", str(comfy)])
        report.check(code == 1 and re.search(r"^MISSING\s+custom_nodes/ComfyUI-GGUF", out, re.M), f"a missing ComfyUI-GGUF must print MISSING custom_nodes/ComfyUI-GGUF and exit 1; got {code}:\n{out}")
        bad = [dict(models[0], size=123)]
        (comfy / "custom_nodes" / "ComfyUI-GGUF").mkdir()
        os.remove(comfy / "models" / "diffusion_models" / "big.gguf")
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            try:
                code = setup.main(["--comfyui-dir", str(comfy), "--download"], models=bad)
            except SystemExit as e:
                code = e.code
        report.check(code == 1 and not (comfy / "models" / "diffusion_models" / "big.gguf").exists() and not list(comfy.rglob("*.part")), "a download whose size does not match must be deleted, reported and exit 1")
        httpd.shutdown()
    finally:
        shutil.rmtree(serve, ignore_errors=True)
        shutil.rmtree(comfy, ignore_errors=True)


for step in (check_workflows, check_setup, check_server, check_ui):
    try:
        step()
    except Exception as exc:  # noqa: BLE001
        report.problems.append(f"{step.__name__} crashed: {type(exc).__name__}: {exc}")
report.finish()
