"""Lens Distortion node: apply or remove Brown-Conrady lens distortion."""

import torch

from open_optics_nodes import common, distortion_grid
from open_optics_nodes.device import get_device


class OpenOptics_LensDistortion:
    """Apply or remove radial and tangential lens distortion."""

    @classmethod
    def INPUT_TYPES(cls):
        coeff = {"default": 0.0, "min": -10.0, "max": 10.0, "step": 0.001}
        return {
            "required": {
                "image": ("IMAGE",),
                "focal_mm": ("FLOAT", {"default": 35.0, "min": 0.1, "max": 2000.0, "step": 0.1}),
                "sensor_width_mm": ("FLOAT", {"default": 36.0, "min": 0.1, "max": 200.0, "step": 0.1}),
                "k1": ("FLOAT", dict(coeff)),
                "k2": ("FLOAT", dict(coeff)),
                "k3": ("FLOAT", dict(coeff)),
                "p1": ("FLOAT", dict(coeff)),
                "p2": ("FLOAT", dict(coeff)),
                "direction": (["apply", "remove"], {"default": "apply"}),
                "fit": (["keep", "crop"], {"default": "keep"}),
                "chunk_frames": common.CHUNK_FRAMES_INPUT,
            }
        }

    RETURN_TYPES = ("IMAGE",)
    FUNCTION = "apply"
    CATEGORY = "Open Optics"

    def apply(self, image, focal_mm=35.0, sensor_width_mm=36.0, k1=0.0, k2=0.0,
              k3=0.0, p1=0.0, p2=0.0, direction="apply", fit="keep",
              chunk_frames=8):
        """Resample the image through the Brown-Conrady distortion model.

        focal_mm and sensor_width_mm are in millimetres; k1, k2, k3, p1, p2
        are unitless. With direction 'apply' the output pixel (u, v) samples
        the source at undistort_point of its position (ideal to lens); with
        'remove' it samples at distort_point (lens to ideal). fit 'keep' fills
        areas that map outside the source with black; fit 'crop' zooms in to
        hide them. The output size equals the input size. chunk_frames (a count
        of frames, >= 1, default 8) is how many frames are processed at a time
        on get_device(); the result does not depend on it. Returns a 1-tuple
        with a CPU float32 IMAGE [B, H, W, C], 0-1.
        """
        common.check_chunk_frames(chunk_frames)
        common.check_image(image)
        device = get_device()
        common.require_positive("focal_mm", focal_mm)
        common.require_positive("sensor_width_mm", sensor_width_mm)
        common.require_choice("direction", direction, ("apply", "remove"))
        common.require_choice("fit", fit, ("keep", "crop"))
        h, w = image.shape[1], image.shape[2]
        zoom = 1.0
        outside = "black"
        if fit == "crop":
            outside = "border"
            crop = (distortion_grid.crop_zoom if direction == "remove"
                    else distortion_grid.crop_zoom_apply)
            zoom = crop(w, h, focal_mm, sensor_width_mm, k1, k2, k3, p1, p2)
        grid = distortion_grid.build_source_grid(
            w, h, focal_mm, sensor_width_mm, k1, k2, k3, p1, p2, direction, zoom)
        grid_t = torch.tensor(grid, dtype=torch.float32, device=device).reshape(h, w, 2)
        outs = []
        for start, stop in common.chunk_ranges(image.shape[0], chunk_frames):
            out = distortion_grid.sample_bilinear(
                image[start:stop].to(device), grid_t, outside=outside)
            outs.append(out.cpu().to(torch.float32))
        return (torch.cat(outs),)
