"""Open Optics ComfyUI node pack."""

from .anamorphic import OpenOptics_Anamorphic
from .chromatic_aberration import OpenOptics_ChromaticAberration
from .depth_of_field import OpenOptics_DepthOfField
from .depth_temporal_smooth import OpenOptics_DepthTemporalSmooth
from .depth_to_metric import OpenOptics_DepthToMetric
from .focal_crop import OpenOptics_FocalCrop
from .lens_distortion import OpenOptics_LensDistortion
from .vignette import OpenOptics_Vignette

NODE_CLASS_MAPPINGS = {
    "OpenOptics_Anamorphic": OpenOptics_Anamorphic,
    "OpenOptics_ChromaticAberration": OpenOptics_ChromaticAberration,
    "OpenOptics_DepthOfField": OpenOptics_DepthOfField,
    "OpenOptics_DepthTemporalSmooth": OpenOptics_DepthTemporalSmooth,
    "OpenOptics_DepthToMetric": OpenOptics_DepthToMetric,
    "OpenOptics_FocalCrop": OpenOptics_FocalCrop,
    "OpenOptics_LensDistortion": OpenOptics_LensDistortion,
    "OpenOptics_Vignette": OpenOptics_Vignette,
}
NODE_DISPLAY_NAME_MAPPINGS = {
    "OpenOptics_Anamorphic": "Open Optics: Anamorphic Squeeze",
    "OpenOptics_ChromaticAberration": "Open Optics: Chromatic Aberration",
    "OpenOptics_DepthOfField": "Open Optics: Depth of Field",
    "OpenOptics_DepthTemporalSmooth": "Open Optics: Depth Temporal Smooth",
    "OpenOptics_DepthToMetric": "Open Optics: Depth to Metric",
    "OpenOptics_FocalCrop": "Open Optics: Focal Crop",
    "OpenOptics_LensDistortion": "Open Optics: Lens Distortion",
    "OpenOptics_Vignette": "Open Optics: Vignette",
}

__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS"]
