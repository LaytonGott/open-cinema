"""API-format ComfyUI graphs for the LTX benchmarks.

Both graphs follow ComfyUI's bundled templates (comfyui_workflow_templates_json:
ltxv_text_to_video.json and video_ltx2_t2v_distilled.json), with the model
loaders swapped for the files we benchmark.
"""

PROMPT = (
    "A slow dolly-in on a woman reading a handwritten letter beside a rain-streaked "
    "window at night. A warm tungsten desk lamp lights her face from the left, cool "
    "blue city light spills through the glass behind her. Raindrops run down the "
    "window, her eyes move along the lines, and she exhales softly. Shallow depth of "
    "field, the background city lights fall into soft bokeh. Cinematic 35mm film look."
)
NEGATIVE = "low quality, worst quality, deformed, distorted, disfigured, motion smear, motion artifacts, fused fingers, bad anatomy, weird hand, ugly"

DISTILLED_SIGMAS = "1., 0.99375, 0.9875, 0.98125, 0.975, 0.909375, 0.725, 0.421875, 0.0"
REFINE_SIGMAS = "0.909375, 0.725, 0.421875, 0.0"

WIDTH, HEIGHT, FRAMES, FPS = 1280, 704, 121, 24  # LTX needs /32; 720 -> 704. 121 frames = 5.04 s


def ltxv_098_13b(seed: int, prefix: str) -> dict:
    """LTX-Video 0.9.8 13B distilled (fp8 weights), single pass at full resolution."""
    return {
        "1": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": "ltxv-13b-0.9.8-distilled-fp8.safetensors"}},
        "2": {"class_type": "CLIPLoader", "inputs": {"clip_name": "t5xxl_fp16.safetensors", "type": "ltxv", "device": "default"}},
        "3": {"class_type": "CLIPTextEncode", "inputs": {"text": PROMPT, "clip": ["2", 0]}},
        "4": {"class_type": "CLIPTextEncode", "inputs": {"text": NEGATIVE, "clip": ["2", 0]}},
        "5": {"class_type": "LTXVConditioning", "inputs": {"positive": ["3", 0], "negative": ["4", 0], "frame_rate": FPS}},
        "6": {"class_type": "EmptyLTXVLatentVideo", "inputs": {"width": WIDTH, "height": HEIGHT, "length": FRAMES, "batch_size": 1}},
        "7": {"class_type": "ManualSigmas", "inputs": {"sigmas": DISTILLED_SIGMAS}},
        "8": {"class_type": "KSamplerSelect", "inputs": {"sampler_name": "euler"}},
        "9": {"class_type": "RandomNoise", "inputs": {"noise_seed": seed}},
        "10": {"class_type": "CFGGuider", "inputs": {"model": ["1", 0], "positive": ["5", 0], "negative": ["5", 1], "cfg": 1.0}},
        "11": {"class_type": "SamplerCustomAdvanced", "inputs": {"noise": ["9", 0], "guider": ["10", 0], "sampler": ["8", 0], "sigmas": ["7", 0], "latent_image": ["6", 0]}},
        "12": {"class_type": "VAEDecodeTiled", "inputs": {"samples": ["11", 0], "vae": ["1", 2], "tile_size": 512, "overlap": 64, "temporal_size": 4096, "temporal_overlap": 8}},
        "13": {"class_type": "CreateVideo", "inputs": {"images": ["12", 0], "fps": float(FPS)}},
        "14": {"class_type": "SaveVideo", "inputs": {"video": ["13", 0], "filename_prefix": prefix, "format": "auto", "codec": "auto"}},
    }


def ltx2_19b_q4(seed: int, prefix: str, encoder_device: str = "cpu") -> dict:
    """LTX-2 19B distilled, Q4_K_M GGUF. Official two-stage pipeline:
    8 distilled steps at 640x352, x2 latent upscale, 3 refine steps at 1280x704.
    The Gemma 3 12B text encoder runs on `encoder_device` (cpu = offloaded)."""
    return {
        "1": {"class_type": "UnetLoaderGGUF", "inputs": {"unet_name": "ltx-2-19b-distilled_Q4_K_M.gguf"}},
        "2": {"class_type": "VAELoader", "inputs": {"vae_name": "LTX2_video_vae_bf16.safetensors"}},
        "3": {"class_type": "LTXVAudioVAELoader", "inputs": {"ckpt_name": "LTX2_audio_vae_bf16.safetensors"}},
        "4": {"class_type": "LTXAVTextEncoderLoader", "inputs": {
            "text_encoder": "gemma_3_12B_it_fp8_scaled.safetensors",
            "ckpt_name": "ltx-2-19b-embeddings_connector_distill_bf16.safetensors",
            "device": encoder_device}},
        "5": {"class_type": "CLIPTextEncode", "inputs": {"text": PROMPT, "clip": ["4", 0]}},
        "7": {"class_type": "LTXVConditioning", "inputs": {"positive": ["5", 0], "negative": ["5", 0], "frame_rate": FPS}},
        "8": {"class_type": "EmptyLTXVLatentVideo", "inputs": {"width": WIDTH // 2, "height": HEIGHT // 2, "length": FRAMES, "batch_size": 1}},
        "9": {"class_type": "LTXVEmptyLatentAudio", "inputs": {"audio_vae": ["3", 0], "frames_number": FRAMES, "frame_rate": FPS, "batch_size": 1}},
        "10": {"class_type": "LTXVConcatAVLatent", "inputs": {"video_latent": ["8", 0], "audio_latent": ["9", 0]}},
        "11": {"class_type": "RandomNoise", "inputs": {"noise_seed": seed}},
        "12": {"class_type": "KSamplerSelect", "inputs": {"sampler_name": "euler_ancestral"}},
        "13": {"class_type": "ManualSigmas", "inputs": {"sigmas": DISTILLED_SIGMAS}},
        "14": {"class_type": "CFGGuider", "inputs": {"model": ["1", 0], "positive": ["7", 0], "negative": ["7", 1], "cfg": 1.0}},
        "15": {"class_type": "SamplerCustomAdvanced", "inputs": {"noise": ["11", 0], "guider": ["14", 0], "sampler": ["12", 0], "sigmas": ["13", 0], "latent_image": ["10", 0]}},
        "16": {"class_type": "LTXVSeparateAVLatent", "inputs": {"av_latent": ["15", 1]}},
        "17": {"class_type": "LatentUpscaleModelLoader", "inputs": {"model_name": "ltx-2-spatial-upscaler-x2-1.0.safetensors"}},
        "18": {"class_type": "LTXVLatentUpsampler", "inputs": {"samples": ["16", 0], "upscale_model": ["17", 0], "vae": ["2", 0]}},
        "19": {"class_type": "LTXVConcatAVLatent", "inputs": {"video_latent": ["18", 0], "audio_latent": ["16", 1]}},
        "20": {"class_type": "RandomNoise", "inputs": {"noise_seed": seed + 378}},
        "21": {"class_type": "KSamplerSelect", "inputs": {"sampler_name": "euler_ancestral"}},
        "22": {"class_type": "ManualSigmas", "inputs": {"sigmas": REFINE_SIGMAS}},
        "23": {"class_type": "CFGGuider", "inputs": {"model": ["1", 0], "positive": ["7", 0], "negative": ["7", 1], "cfg": 1.0}},
        "24": {"class_type": "SamplerCustomAdvanced", "inputs": {"noise": ["20", 0], "guider": ["23", 0], "sampler": ["21", 0], "sigmas": ["22", 0], "latent_image": ["19", 0]}},
        "25": {"class_type": "LTXVSeparateAVLatent", "inputs": {"av_latent": ["24", 1]}},
        "26": {"class_type": "VAEDecodeTiled", "inputs": {"samples": ["25", 0], "vae": ["2", 0], "tile_size": 512, "overlap": 64, "temporal_size": 4096, "temporal_overlap": 8}},
        "27": {"class_type": "LTXVAudioVAEDecode", "inputs": {"samples": ["25", 1], "audio_vae": ["3", 0]}},
        "28": {"class_type": "CreateVideo", "inputs": {"images": ["26", 0], "audio": ["27", 0], "fps": float(FPS)}},
        "29": {"class_type": "SaveVideo", "inputs": {"video": ["28", 0], "filename_prefix": prefix, "format": "auto", "codec": "auto"}},
    }


WORKFLOWS = {"ltxv-0.9.8-13b": ltxv_098_13b, "ltx2-19b-q4": ltx2_19b_q4}
