"""Model setup for the director app: the files ComfyUI needs and where to get them.

MODELS lists every file as a dict with name, folder (under ComfyUI's models/),
url, size (bytes) and required. It equals the table in docs/app-spec.md 7.1.
"""

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
