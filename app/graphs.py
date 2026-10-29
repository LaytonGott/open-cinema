"""API-format ComfyUI graph for LTX-2 shot generation."""

DISTILLED_SIGMAS = "1., 0.99375, 0.9875, 0.98125, 0.975, 0.909375, 0.725, 0.421875, 0.0"
REFINE_SIGMAS = "0.909375, 0.725, 0.421875, 0.0"

WIDTH, HEIGHT, FRAMES, FPS = 1280, 704, 121, 24
TEXT_ENCODER_DEVICE = "default"

GENERATION_OUTPUT_NODE = "29"
OPTICS_OUTPUT_NODE = "10"


def build_generation_graph(prompt: str, seed: int, prefix: str, camera_lora=None) -> dict:
    """Build the LTX-2 19B distilled two-stage text-to-video graph (ComfyUI API format).

    `prompt` is the positive text, `seed` the first-pass noise seed (the refine
    pass uses seed + 378), `prefix` the SaveVideo filename prefix. Output is
    1280x704 pixels, 121 frames at 24 frames per second. Returns a new
    JSON-serialisable dict of node id -> node; the video is saved by node
    GENERATION_OUTPUT_NODE.

    `camera_lora` is None or an LTX-2 camera LoRA file name (docs/app-spec.md
    7.3): with one, node "30" (LoraLoaderModelOnly, strength 1.0) loads it on
    the model and both CFGGuider nodes take the model from it.
    """
    graph = {
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
    if camera_lora:
        graph["30"] = {"class_type": "LoraLoaderModelOnly", "inputs": {
            "model": ["1", 0], "lora_name": camera_lora, "strength_model": 1.0}}
        graph["14"]["inputs"]["model"] = ["30", 0]
        graph["23"]["inputs"]["model"] = ["30", 0]
    return graph


LOOK_NODES = ("11", "12", "13")


def build_optics_graph(video_file: str, focal_mm: float, f_number: float, subject_m: float, prefix: str,
                       focus=None, rack=None, look: str = "clean") -> dict:
    """Build the depth-of-field graph (ComfyUI API format) for a generated video.

    `video_file` is the uploaded LoadVideo file name, `focal_mm` the focal length
    in millimetres, `f_number` the aperture (f-stop), `subject_m` the subject
    distance in metres (also the focus distance), `prefix` the SaveVideo filename
    prefix. Only DepthOfField, CreateVideo and SaveVideo depend on `f_number` and
    `prefix`, so changing them reuses the cached depth estimation. Returns a new
    JSON-serialisable dict of node id -> node; the video is saved by node
    OPTICS_OUTPUT_NODE.

    `focus` and `rack` are None or {"x", "y"} frame fractions (docs/app-spec.md
    7.2): a focus point focuses each frame at the depth found there, a rack
    point pulls focus to it between 20 % and 80 % of the clip. `look` is
    "clean", "vintage" or "anamorphic" (7.4). Without them the graph is the
    plain depth-of-field graph.
    """
    graph = {
        "1": {"class_type": "LoadVideo", "inputs": {"file": video_file}},
        "2": {"class_type": "GetVideoComponents", "inputs": {"video": ["1", 0]}},
        "3": {"class_type": "LoadDA3Model", "inputs": {"model_name": "depth_anything_3_mono_large.safetensors", "weight_dtype": "default"}},
        "4": {"class_type": "DA3Inference", "inputs": {"da3_model": ["3", 0], "image": ["2", 0], "resolution": 504, "resize_method": "upper_bound_resize", "mode": "mono"}},
        "5": {"class_type": "DA3Render", "inputs": {"da3_geometry": ["4", 0], "output": "depth", "output.normalization": "raw", "output.apply_sky_clip": False}},
        "6": {"class_type": "OpenOptics_DepthToMetric", "inputs": {
            "depth_image": ["5", 0], "mode": "subject", "subject_m": subject_m, "subject_x": 0.5, "subject_y": 0.5,
            "inverse_depth": False, "near_m": 0.3, "far_m": 80, "low_percentile": 2, "high_percentile": 98}},
        "7": {"class_type": "OpenOptics_DepthTemporalSmooth", "inputs": {"depth": ["6", 0], "strength": 0.7}},
        "8": {"class_type": "OpenOptics_DepthOfField", "inputs": {
            "image": ["2", 0], "depth_mask": ["7", 0], "focal_mm": focal_mm, "f_number": f_number, "focus_m": subject_m,
            "sensor_width_mm": 36, "max_radius_px": 24, "quality": "normal", "colorspace": "srgb"}},
        "9": {"class_type": "CreateVideo", "inputs": {"images": ["8", 0], "audio": ["2", 1], "fps": ["2", 2]}},
        "10": {"class_type": "SaveVideo", "inputs": {"video": ["9", 0], "filename_prefix": prefix, "format": "auto", "codec": "auto"}},
    }
    dof = graph["8"]["inputs"]
    if focus is not None:
        dof["focus_x"], dof["focus_y"] = focus["x"], focus["y"]
        if rack is not None:
            dof["rack_x"], dof["rack_y"] = rack["x"], rack["y"]
            dof["rack_start"], dof["rack_end"] = 0.2, 0.8
    if look == "vintage":
        graph["11"] = {"class_type": "OpenOptics_LensDistortion", "inputs": {
            "image": ["8", 0], "focal_mm": focal_mm, "sensor_width_mm": 36, "k1": -0.08, "k2": 0, "k3": 0,
            "p1": 0, "p2": 0, "direction": "apply", "fit": "crop"}}
        graph["12"] = {"class_type": "OpenOptics_ChromaticAberration", "inputs": {"image": ["11", 0], "ca_r": 0.0015, "ca_b": -0.0015}}
        graph["13"] = {"class_type": "OpenOptics_Vignette", "inputs": {
            "image": ["12", 0], "focal_mm": focal_mm, "sensor_width_mm": 36, "strength": 0.6, "colorspace": "srgb"}}
        graph["9"]["inputs"]["images"] = ["13", 0]
    elif look == "anamorphic":
        dof["bokeh_squeeze"] = 1.5
        graph["12"] = {"class_type": "OpenOptics_ChromaticAberration", "inputs": {"image": ["8", 0], "ca_r": 0.001, "ca_b": -0.001}}
        graph["13"] = {"class_type": "OpenOptics_Vignette", "inputs": {
            "image": ["12", 0], "focal_mm": focal_mm, "sensor_width_mm": 36, "strength": 0.35, "colorspace": "srgb"}}
        graph["9"]["inputs"]["images"] = ["13", 0]
    return graph
