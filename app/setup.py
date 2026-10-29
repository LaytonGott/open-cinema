"""Model setup for the director app: the files ComfyUI needs and where to get them.

MODELS lists every file as a dict with name, folder (under ComfyUI's models/),
url, size (bytes) and required. It equals the table in docs/app-spec.md 7.1.
Run: python -m app.setup --comfyui-dir <ComfyUI folder> [--download] [--only-required]
"""

import argparse
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

_REQUIRED = [
    ("ltx-2-19b-distilled_Q4_K_M.gguf", "diffusion_models",
     "https://huggingface.co/Kijai/LTXV2_comfy/resolve/main/diffusion_models/ltx-2-19b-distilled_Q4_K_M.gguf", 12651789536),
    ("gemma_3_12B_it_fp8_scaled.safetensors", "text_encoders",
     "https://huggingface.co/Comfy-Org/ltx-2/resolve/main/split_files/text_encoders/gemma_3_12B_it_fp8_scaled.safetensors", 13205434827),
    ("ltx-2-19b-embeddings_connector_distill_bf16.safetensors", "checkpoints",
     "https://huggingface.co/Kijai/LTXV2_comfy/resolve/main/text_encoders/ltx-2-19b-embeddings_connector_distill_bf16.safetensors", 2862983784),
    ("LTX2_audio_vae_bf16.safetensors", "checkpoints",
     "https://huggingface.co/Kijai/LTXV2_comfy/resolve/main/VAE/LTX2_audio_vae_bf16.safetensors", 217740136),
    ("LTX2_video_vae_bf16.safetensors", "vae",
     "https://huggingface.co/Kijai/LTXV2_comfy/resolve/main/VAE/LTX2_video_vae_bf16.safetensors", 2445008522),
    ("ltx-2-spatial-upscaler-x2-1.0.safetensors", "latent_upscale_models",
     "https://huggingface.co/Lightricks/LTX-2/resolve/main/ltx-2-spatial-upscaler-x2-1.0.safetensors", 995765578),
    ("depth_anything_3_mono_large.safetensors", "geometry_estimation",
     "https://huggingface.co/Comfy-Org/Depth-Anything-3/resolve/main/geometry_estimation/depth_anything_3_mono_large.safetensors", 1336748056),
]

_LORA_MOVES = ["dolly-in", "dolly-out", "dolly-left", "dolly-right", "jib-up", "jib-down", "static"]

MODELS = [
    {"name": name, "folder": folder, "url": url, "size": size, "required": True}
    for name, folder, url, size in _REQUIRED
]

for _move in _LORA_MOVES:
    _title = "-".join(word.capitalize() for word in _move.split("-"))
    MODELS.append({
        "name": f"ltx-2-19b-lora-camera-control-{_move}.safetensors",
        "folder": "loras",
        "url": (f"https://huggingface.co/Lightricks/LTX-2-19b-LoRA-Camera-Control-{_title}"
                f"/resolve/main/ltx-2-19b-lora-camera-control-{_move}.safetensors"),
        "size": 327309208 if _move.startswith("dolly") else 2214978664,
        "required": False,
    })

CHUNK = 1024 * 1024
CUSTOM_NODE_HINTS = {
    "open-cinema": "the Open Cinema pack: clone this repository into ComfyUI/custom_nodes (see the README, Install)",
    "ComfyUI-GGUF": "git clone https://github.com/city96/ComfyUI-GGUF into ComfyUI/custom_nodes",
}


def _gb(size):
    """Return size (bytes) as gigabytes (10^9 bytes) with 2 decimals."""
    return f"{size / 1e9:.2f}"


def check_model(models_dir, model):
    """Return (state, line) for one MODELS entry under models_dir (a Path to ComfyUI's models/).

    state is "ok", "missing" or "wrong-size"; line is the text printed for it.
    """
    rel = f"models/{model['folder']}/{model['name']}"
    path = Path(models_dir) / model["folder"] / model["name"]
    if not path.is_file():
        tail = " (optional)" if not model["required"] else ""
        return "missing", f"MISSING  {rel}  ({_gb(model['size'])} GB, {model['url']}){tail}"
    actual = path.stat().st_size
    if actual != model["size"]:
        return "wrong-size", f"WRONG SIZE {rel}  ({actual} bytes, expected {model['size']})"
    return "ok", f"OK       {rel}"


def _custom_nodes(comfy_dir):
    """Return a list of (name, present) for the custom node folders the app needs."""
    nodes = Path(comfy_dir) / "custom_nodes"
    pack = nodes.is_dir() and any((d / "open_optics_nodes").is_dir() for d in nodes.iterdir() if d.is_dir())
    return [("open-cinema", pack), ("ComfyUI-GGUF", (nodes / "ComfyUI-GGUF").is_dir())]


def download(model, models_dir, out=print):
    """Download one MODELS entry into models_dir via a .part file; return True when it ends with the right size.

    Resumes an existing .part with an HTTP Range request when the server answers 206.
    Prints progress at most once a second. A size mismatch deletes the .part.
    """
    folder = Path(models_dir) / model["folder"]
    folder.mkdir(parents=True, exist_ok=True)
    final = folder / model["name"]
    part = folder / (model["name"] + ".part")
    have = part.stat().st_size if part.exists() else 0
    req = urllib.request.Request(model["url"], headers={"Range": f"bytes={have}-"} if have else {})
    rel = f"models/{model['folder']}/{model['name']}"
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            mode = "ab" if have and resp.status == 206 else "wb"
            done = have if mode == "ab" else 0
            last = 0.0
            with open(part, mode) as fh:
                while True:
                    chunk = resp.read(CHUNK)
                    if not chunk:
                        break
                    fh.write(chunk)
                    done += len(chunk)
                    now = time.monotonic()
                    if now - last >= 1.0:
                        last = now
                        out(f"  {model['name']}: {_gb(done)} of {_gb(model['size'])} GB")
    except (urllib.error.URLError, OSError) as exc:
        out(f"FAILED   {rel}  ({exc})")
        return False
    got = part.stat().st_size
    if got != model["size"]:
        out(f"FAILED   {rel}  (downloaded {got} bytes, expected {model['size']})")
        part.unlink()
        return False
    os.replace(part, final)
    out(f"OK       {rel}  (downloaded)")
    return True


def main(argv=None, models=None):
    """Check (and with --download fetch) the files the app needs; return the exit code.

    0: every required item is present with the right size; 1: something required is missing;
    2: --comfyui-dir is not a ComfyUI folder with models/. models defaults to MODELS.
    """
    models = MODELS if models is None else models
    parser = argparse.ArgumentParser(prog="python -m app.setup", description="Check and download the models Open Cinema needs.")
    parser.add_argument("--comfyui-dir", required=True, help="the ComfyUI folder (it contains models/ and custom_nodes/)")
    parser.add_argument("--download", action="store_true", help="download missing or wrong-size model files")
    parser.add_argument("--only-required", action="store_true", help="skip the optional camera LoRAs")
    args = parser.parse_args(argv)
    comfy = Path(args.comfyui_dir)
    models_dir = comfy / "models"
    if not models_dir.is_dir():
        print(f"{comfy} is not a ComfyUI folder: it has no models/ folder.")
        return 2
    wanted = [m for m in models if m["required"] or not args.only_required]
    if args.download:
        for m in wanted:
            if check_model(models_dir, m)[0] != "ok":
                download(m, models_dir)
    missing = 0
    for m in wanted:
        state, line = check_model(models_dir, m)
        print(line)
        if state != "ok" and m["required"]:
            missing += 1
    for name, present in _custom_nodes(comfy):
        if present:
            print(f"OK       custom_nodes/{name}")
        else:
            print(f"MISSING  custom_nodes/{name}  ({CUSTOM_NODE_HINTS[name]})")
            missing += 1
    print("All required files are in place." if not missing else f"{missing} required item(s) missing.")
    return 0 if not missing else 1


if __name__ == "__main__":
    sys.exit(main())
