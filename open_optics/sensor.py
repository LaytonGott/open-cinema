"""Camera sensor description (dimensions in millimetres)."""

import math
from dataclasses import dataclass
from typing import Optional

from open_optics.validation import require_positive


@dataclass(frozen=True)
class Sensor:
    """A camera sensor.

    width_mm and height_mm are the active area in millimetres. name is an
    optional label. coc_mm is an optional circle-of-confusion (blur tolerance)
    override in millimetres.
    """

    width_mm: float
    height_mm: float
    name: Optional[str] = None
    coc_mm: Optional[float] = None

    def __post_init__(self):
        """Validate that sizes (and coc_mm, if given) are positive and finite."""
        require_positive("width_mm", self.width_mm)
        require_positive("height_mm", self.height_mm)
        if self.coc_mm is not None:
            require_positive("coc_mm", self.coc_mm)

    def to_dict(self):
        """Return a JSON-compatible dict with keys width_mm, height_mm, name, coc_mm (sizes in millimetres)."""
        return {
            "width_mm": self.width_mm,
            "height_mm": self.height_mm,
            "name": self.name,
            "coc_mm": self.coc_mm,
        }

    @classmethod
    def from_dict(cls, data):
        """Build a Sensor from a dict as made by to_dict (sizes in millimetres).

        name and coc_mm are optional. Raises ValueError naming a missing
        width_mm or height_mm key; invalid values raise the constructor's
        ValueError. Returns a Sensor.
        """
        for key in ("width_mm", "height_mm"):
            if key not in data:
                raise ValueError(f"missing required key: {key}")
        return cls(
            data["width_mm"],
            data["height_mm"],
            name=data.get("name"),
            coc_mm=data.get("coc_mm"),
        )

    @property
    def diagonal_mm(self):
        """Sensor diagonal in millimetres, returned as a float."""
        return math.hypot(self.width_mm, self.height_mm)

    @property
    def aspect_ratio(self):
        """Width divided by height (unitless), returned as a float."""
        return self.width_mm / self.height_mm
