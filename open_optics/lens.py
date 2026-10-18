"""Lens description (focal length in millimetres, f-numbers unitless)."""

from dataclasses import dataclass

from open_optics.validation import require_positive


@dataclass(frozen=True)
class Lens:
    """A camera lens.

    focal_mm is the focal length in millimetres. f_number_min is the widest
    aperture (smallest f-number) and f_number_max the narrowest, both
    unitless. squeeze is the anamorphic squeeze factor (unitless, 1.0 for
    spherical lenses).
    """

    focal_mm: float
    f_number_min: float
    f_number_max: float
    squeeze: float = 1.0

    def __post_init__(self):
        """Validate that all fields are positive and finite and f_number_min <= f_number_max."""
        require_positive("focal_mm", self.focal_mm)
        require_positive("f_number_min", self.f_number_min)
        require_positive("f_number_max", self.f_number_max)
        require_positive("squeeze", self.squeeze)
        if self.f_number_min > self.f_number_max:
            raise ValueError("f_number_min must not exceed f_number_max")
