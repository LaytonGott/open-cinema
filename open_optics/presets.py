"""Sensor preset catalogue (dimensions in millimetres)."""

from open_optics.sensor import Sensor

SENSOR_PRESETS = {
    "full frame": Sensor(36.0, 24.0, name="Full Frame"),
    "super 35": Sensor(24.89, 18.66, name="Super 35"),
    "aps-c": Sensor(23.6, 15.7, name="APS-C"),
    "micro four thirds": Sensor(17.3, 13.0, name="Micro Four Thirds"),
    "medium format": Sensor(43.8, 32.9, name="Medium Format"),
    "super 16": Sensor(12.52, 7.41, name="Super 16"),
}


def sensor_names():
    """Return the sorted list of lowercase preset sensor names (strings)."""
    return sorted(SENSOR_PRESETS)


def get_sensor(name):
    """Look up a preset Sensor (width and height in millimetres) by name.

    The name is stripped and lowercased first. Returns the Sensor. Raises
    TypeError if name is not a str, and ValueError listing all available
    names if it is unknown.
    """
    if not isinstance(name, str):
        raise TypeError(f"name must be a str, got {type(name).__name__}")
    key = name.strip().lower()
    if key not in SENSOR_PRESETS:
        raise ValueError(
            f"unknown sensor {name!r}; available: {', '.join(sensor_names())}"
        )
    return SENSOR_PRESETS[key]
