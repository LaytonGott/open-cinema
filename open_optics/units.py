"""Unit conversions and the unit convention for Open Optics.

Convention: all lengths are in millimetres (including focus distance and
circle of confusion). Angles are in degrees at the public surface; radians
are used only internally.
"""

import math


def deg_to_rad(degrees):
    """Convert an angle from degrees to radians.

    Args:
        degrees: angle in degrees.

    Returns:
        The angle in radians, as a float.
    """
    return math.radians(degrees)


def rad_to_deg(radians):
    """Convert an angle from radians to degrees.

    Args:
        radians: angle in radians.

    Returns:
        The angle in degrees, as a float.
    """
    return math.degrees(radians)
