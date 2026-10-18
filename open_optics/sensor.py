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

    @property
    def diagonal_mm(self):
        """Sensor diagonal in millimetres, returned as a float."""
        return math.hypot(self.width_mm, self.height_mm)

    @property
    def aspect_ratio(self):
        """Width divided by height (unitless), returned as a float."""
        return self.width_mm / self.height_mm
