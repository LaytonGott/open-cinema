"""Open Optics: physically based lens math for the Open Cinema node pack.

Pure Python (standard library only). The ComfyUI node wrappers come later and live elsewhere.

Units:
    All lengths (focal length, sensor size, focus and subject distance, circle of
    confusion) are in millimetres. Angles are in degrees at the public surface;
    radians appear only via the open_optics.units helpers. Every public function's
    docstring states its units and what it returns.

Where to find things:
    fov          field of view and angle of view from focal length and sensor size
    crop         crop factor and full-frame equivalent focal length and f-number
    anamorphic   squeeze and desqueeze of sizes and points, delivered aspect, bokeh shape
    coc          circle of confusion and blur diameter in mm and pixels
    dof          hyperfocal distance, focus for a range, depth-of-field limits
    pixels       conversion between pixel coordinates and lens (angle) coordinates
    distortion   radial lens distortion of points
    chromatic    lateral chromatic aberration
    vignetting   light falloff towards the corners
    color        colour helpers for the optical effects
    breathing    focus breathing (field of view change with focus distance)
    focus_pull   focus distance changes over a shot
    dolly        dolly and dolly-zoom camera moves
    exposure     exposure maths (f-number, shutter, ISO)
    presets      named sensor and lens presets
    temporal     smoothing of depth maps over a frame sequence
    summary      one-call shot summary combining the other modules
    sensor       the Sensor dataclass
    lens         the Lens dataclass

Needs no third-party software. Importing the package prints nothing, and all
results are deterministic.
"""

from .units import deg_to_rad, rad_to_deg
from .validation import require_positive, require_positive_or_inf, require_finite
from .sensor import Sensor
from .lens import Lens
from .fov import FieldOfView, angle_of_view, sensor_angles, focal_from_angle, field_of_view
from .crop import crop_factor, equivalent_focal_mm, equivalent_f_number
from .anamorphic import (
    desqueeze_size,
    squeeze_size,
    desqueeze_point,
    squeeze_point,
    delivered_aspect_ratio,
    bokeh_aspect,
)
from .coc import (
    coc_for_sensor,
    coc_for_sensor_obj,
    blur_diameter_mm,
    blur_diameter_px,
    blur_radius_px,
)
from .dof import (
    hyperfocal_mm,
    hyperfocal_focus_mm,
    focus_for_range_mm,
    dof_limits_mm,
    dof_summary,
)
from .pixels import focal_length_px, pixel_to_lens, lens_to_pixel
from .distortion import (
    DistortionError,
    distort_point,
    undistort_point,
    distort_pixel,
    undistort_pixel,
    border_free_zoom,
    classify_distortion,
    straight_line_deviation,
)
from .chromatic import channel_scales, fringe_shift_px
from .vignetting import (
    natural_vignette,
    natural_vignette_px,
    brightness_to_stops,
    aperture_vignette,
    combined_vignette,
)
from .color import srgb_to_linear, linear_to_srgb, apply_vignette_linear
from .breathing import focus_magnification, breathing_scale
from .focus_pull import focus_at_frame
from .dolly import dolly_zoom_focal, dolly_zoom_path
from .exposure import (
    f_number_to_stops,
    stops_to_f_number,
    stop_difference,
    t_stop_from_f,
    f_from_t_stop,
)
from .presets import sensor_names, get_sensor, squeeze_names, get_squeeze
from .summary import shot_summary
from .temporal import smooth_depth_sequence

__all__ = [
    "deg_to_rad", "rad_to_deg",
    "require_positive", "require_positive_or_inf", "require_finite",
    "Sensor", "Lens",
    "FieldOfView", "angle_of_view", "sensor_angles", "focal_from_angle", "field_of_view",
    "crop_factor", "equivalent_focal_mm", "equivalent_f_number",
    "desqueeze_size", "squeeze_size", "desqueeze_point", "squeeze_point",
    "delivered_aspect_ratio", "bokeh_aspect",
    "coc_for_sensor", "coc_for_sensor_obj", "blur_diameter_mm", "blur_diameter_px",
    "blur_radius_px",
    "hyperfocal_mm", "hyperfocal_focus_mm", "focus_for_range_mm", "dof_limits_mm",
    "dof_summary",
    "focal_length_px", "pixel_to_lens", "lens_to_pixel",
    "DistortionError", "distort_point", "undistort_point", "distort_pixel",
    "undistort_pixel", "border_free_zoom", "classify_distortion",
    "straight_line_deviation",
    "channel_scales", "fringe_shift_px",
    "natural_vignette", "natural_vignette_px", "brightness_to_stops",
    "aperture_vignette", "combined_vignette",
    "srgb_to_linear", "linear_to_srgb", "apply_vignette_linear",
    "focus_magnification", "breathing_scale",
    "focus_at_frame",
    "dolly_zoom_focal", "dolly_zoom_path",
    "f_number_to_stops", "stops_to_f_number", "stop_difference", "t_stop_from_f",
    "f_from_t_stop",
    "sensor_names", "get_sensor", "squeeze_names", "get_squeeze",
    "shot_summary",
    "smooth_depth_sequence",
]
