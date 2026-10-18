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

    def to_dict(self):
        """Return a JSON-compatible dict with keys focal_mm (millimetres), f_number_min, f_number_max, squeeze (unitless)."""
        return {
            "focal_mm": self.focal_mm,
            "f_number_min": self.f_number_min,
            "f_number_max": self.f_number_max,
            "squeeze": self.squeeze,
        }

    @classmethod
    def from_dict(cls, data):
        """Build a Lens from a dict as made by to_dict (focal_mm in millimetres).

        squeeze is optional and defaults to 1.0. Raises ValueError naming a
        missing focal_mm, f_number_min or f_number_max key; invalid values
        raise the constructor's ValueError. Returns a Lens.
        """
        for key in ("focal_mm", "f_number_min", "f_number_max"):
            if key not in data:
                raise ValueError(f"missing required key: {key}")
        return cls(
            data["focal_mm"],
            data["f_number_min"],
            data["f_number_max"],
            data.get("squeeze", 1.0),
        )
