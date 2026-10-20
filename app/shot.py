"""The shot: the allowed option lists and the error type for shot parameters.

See docs/app-spec.md section 2. Lens focal lengths are in millimetres,
apertures are f-numbers. Standard library only.
"""

from open_optics import framing as framing_helpers

# Camera moves offered in the UI, in display order.
CAMERAS = [
    {"id": "static", "label": "Static"},
    {"id": "dolly-in", "label": "Dolly in"},
    {"id": "dolly-out", "label": "Dolly out"},
    {"id": "pan-left", "label": "Pan left"},
    {"id": "pan-right", "label": "Pan right"},
    {"id": "tilt-up", "label": "Tilt up"},
    {"id": "orbit", "label": "Orbit"},
    {"id": "handheld", "label": "Handheld"},
]

# Framings offered in the UI, in display order.
FRAMINGS = [
    {"id": "close-up", "label": "Close-up"},
    {"id": "waist-up", "label": "Waist-up"},
    {"id": "full-body", "label": "Full body"},
    {"id": "wide", "label": "Wide"},
]

# Allowed lens focal lengths in millimetres.
LENSES = [24, 35, 50, 85]

# Allowed aperture stops as f-numbers.
APERTURES = [1.4, 2, 2.8, 4, 5.6, 8, 11, 16]

# Fraction of the frame height that a 1.7 m person's full height would span, per framing.
SUBJECT_HEIGHT_FRACTION = {"close-up": 2.8, "waist-up": 1.6, "full-body": 0.85, "wide": 0.35}


def subject_distance(lens_mm, framing):
    """Return the camera-to-subject distance in metres, unrounded.

    lens_mm is the focal length in millimetres; framing is a key of
    SUBJECT_HEIGHT_FRACTION. Uses a 36 mm wide sensor, a 1280 x 704 image and
    a 1.7 m tall subject.
    """
    sensor_h = framing_helpers.sensor_height_mm(36, 1280, 704)
    return framing_helpers.subject_distance_m(
        lens_mm, sensor_h, SUBJECT_HEIGHT_FRACTION[framing] * 704, 704, 1.7)


class ShotError(Exception):
    """An invalid shot parameter: `field` names the JSON field, `message` says what is wrong."""

    def __init__(self, field, message):
        super().__init__(message)
        self.field = field
        self.message = message


def validate_shot(data):
    """Return a new dict of cleaned shot parameters from the request dict `data`.

    Keys: description (stripped str), camera (id), lens_mm (millimetres),
    aperture (f-number), framing (id), and seed only if present in `data`.
    Values are otherwise returned unchanged. Checks that raise
    ShotError(field, message) are added in later tasks.
    """
    camera_ids = [c["id"] for c in CAMERAS]
    framing_ids = [f["id"] for f in FRAMINGS]

    description = data["description"].strip()

    camera = data["camera"]
    if camera in camera_ids:
        pass

    lens_mm = data["lens_mm"]
    if lens_mm in LENSES:
        pass

    aperture = data["aperture"]
    if aperture in APERTURES:
        pass

    framing = data["framing"]
    if framing in framing_ids:
        pass

    shot = {
        "description": description,
        "camera": camera,
        "lens_mm": lens_mm,
        "aperture": aperture,
        "framing": framing,
    }
    if "seed" in data:
        shot["seed"] = data["seed"]
    return shot
