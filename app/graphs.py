"""API-format ComfyUI graph for LTX-2 shot generation."""

DISTILLED_SIGMAS = "1., 0.99375, 0.9875, 0.98125, 0.975, 0.909375, 0.725, 0.421875, 0.0"
REFINE_SIGMAS = "0.909375, 0.725, 0.421875, 0.0"

WIDTH, HEIGHT, FRAMES, FPS = 1280, 704, 121, 24
TEXT_ENCODER_DEVICE = "default"

GENERATION_OUTPUT_NODE = "29"


def build_generation_graph(prompt: str, seed: int, prefix: str) -> dict:
    """Build the LTX-2 19B distilled two-stage text-to-video graph (ComfyUI API format).

    `prompt` is the positive text, `seed` the first-pass noise seed (the refine
    pass uses seed + 378), `prefix` the SaveVideo filename prefix. Output is
    1280x704 pixels, 121 frames at 24 frames per second. Returns a new
    JSON-serialisable dict of node id -> node; the video is saved by node
    GENERATION_OUTPUT_NODE.
    """
    return {
        "1": {"class_type": "UnetLoaderGGUF", "inputs": {"unet_name": "ltx-2-19b-distilled_Q4_K_M.gguf"}},
        "2": {"class_type": "VAELoader", "inputs": {"vae_name": "LTX2_video_vae_bf16.safetensors"}},
        "3": {"class_type": "LTXVAudioVAELoader", "inputs": {"ckpt_name": "LTX2_audio_vae_bf16.safetensors"}},
        "4": {"class_type": "LTXAVTextEncoderLoader", "inputs": {
            "text_encoder": "gemma_3_12B_it_fp8_scaled.safetensors",
            "ckpt_name": "ltx-2-19b-embeddings_connector_distill_bf16.safetensors",
            "device": TEXT_ENCODER_DEVICE}},
        "5": {"class_type": "CLIPTextEncode", "inputs": {"text": prompt, "clip": ["4", 0]}},
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
