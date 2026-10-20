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
    a 1.7 m tall subject. Raises ValueError if lens_mm is not an int in LENSES
    or framing is not a key of SUBJECT_HEIGHT_FRACTION.
    """
    if type(lens_mm) is not int or lens_mm not in LENSES:
        raise ValueError(f"lens_mm must be one of {LENSES} mm, got {lens_mm!r}")
    if not isinstance(framing, str) or framing not in SUBJECT_HEIGHT_FRACTION:
        raise ValueError(
            f"framing must be one of {list(SUBJECT_HEIGHT_FRACTION)}, got {framing!r}")
    sensor_h = framing_helpers.sensor_height_mm(36, 1280, 704)
    return framing_helpers.subject_distance_m(
        lens_mm, sensor_h, SUBJECT_HEIGHT_FRACTION[framing] * 704, 704, 1.7)


FRAMING_PHRASES = {
    "close-up": "Close-up shot of the subject's face and shoulders",
    "waist-up": "Waist-up medium shot",
    "full-body": "Full-body shot, the whole figure visible head to toe",
    "wide": "Wide establishing shot, the figure small in a large scene",
}

CAMERA_PHRASES = {
    "static": "The camera is locked off and does not move",
    "dolly-in": "Slow dolly-in toward the subject",
    "dolly-out": "Slow dolly-out away from the subject",
    "pan-left": "Smooth pan to the left",
    "pan-right": "Smooth pan to the right",
    "tilt-up": "Slow tilt up",
    "orbit": "The camera orbits slowly around the subject",
    "handheld": "Handheld camera with subtle natural movement",
}


def build_prompt(params):
    """Return the LTX-2 text prompt (str) for the shot dict `params`.

    params has description, camera (id), lens_mm (millimetres) and framing (id).
    The description is stripped and gets a final '.' unless it already ends in
    '.', '!' or '?'.
    """
    description = params["description"].strip()
    if not description.endswith((".", "!", "?")):
        description += "."
    return (
        f"{FRAMING_PHRASES[params['framing']]}. {description} "
        f"{CAMERA_PHRASES[params['camera']]}. {params['lens_mm']} mm lens look, "
        "deep focus with everything sharp from the foreground to the far background, "
        "cinematic lighting, 35mm film."
    )


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
