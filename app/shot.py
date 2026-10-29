"""The shot: the allowed option lists and the error type for shot parameters.

See docs/app-spec.md section 2. Lens focal lengths are in millimetres,
apertures are f-numbers. Standard library only.
"""

import random

from open_optics import framing as framing_helpers

# Camera moves offered in the UI, in display order.
CAMERAS = [
    {"id": "static", "label": "Static"},
    {"id": "dolly-in", "label": "Dolly in"},
    {"id": "dolly-out", "label": "Dolly out"},
    {"id": "truck-left", "label": "Truck left"},
    {"id": "truck-right", "label": "Truck right"},
    {"id": "crane-up", "label": "Crane up"},
    {"id": "crane-down", "label": "Crane down"},
    {"id": "pan-left", "label": "Pan left"},
    {"id": "pan-right", "label": "Pan right"},
    {"id": "tilt-up", "label": "Tilt up"},
    {"id": "orbit", "label": "Orbit"},
    {"id": "handheld", "label": "Handheld"},
]

# LTX-2 camera-control LoRA file per camera move (docs/app-spec.md 7.3); other moves have none.
CAMERA_LORAS = {
    "static": "ltx-2-19b-lora-camera-control-static.safetensors",
    "dolly-in": "ltx-2-19b-lora-camera-control-dolly-in.safetensors",
    "dolly-out": "ltx-2-19b-lora-camera-control-dolly-out.safetensors",
    "truck-left": "ltx-2-19b-lora-camera-control-dolly-left.safetensors",
    "truck-right": "ltx-2-19b-lora-camera-control-dolly-right.safetensors",
    "crane-up": "ltx-2-19b-lora-camera-control-jib-up.safetensors",
    "crane-down": "ltx-2-19b-lora-camera-control-jib-down.safetensors",
}

# Framings offered in the UI, in display order.
FRAMINGS = [
    {"id": "close-up", "label": "Close-up"},
    {"id": "waist-up", "label": "Waist-up"},
    {"id": "full-body", "label": "Full body"},
    {"id": "wide", "label": "Wide"},
]

# Lens looks (docs/app-spec.md 7.4), in display order; the optics graph adds the matching Open Optics nodes.
LOOKS = [
    {"id": "clean", "label": "Clean"},
    {"id": "vintage", "label": "Vintage"},
    {"id": "anamorphic", "label": "Anamorphic"},
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
    "truck-left": "The camera trucks to the left, moving sideways parallel to the subject",
    "truck-right": "The camera trucks to the right, moving sideways parallel to the subject",
    "crane-up": "The camera cranes up, rising smoothly",
    "crane-down": "The camera cranes down, descending smoothly",
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
    """Validate the request dict `data` and return the cleaned shot parameters.

    `lens_mm` is the focal length in millimetres (an int from LENSES);
    `aperture` is an f-number (an int or float from APERTURES). `camera` and
    `framing` are ids from CAMERAS and FRAMINGS.

    Returns a new dict with the keys description (stripped str), camera,
    lens_mm, aperture, framing and seed. `seed` is an int from 0 to
    2147483647: the value from `data`, or a random one when it is absent.

    Raises ShotError(field, message), with `.field` the name of the invalid
    or missing field and `.message` the text for the user, for the first
    problem found. Required fields are checked first, in the order
    description, camera, lens_mm, aperture, framing: a missing one gives
    "The <name> is required." Then each field is checked in turn: the
    description must be a str of 3 to 1000 characters once stripped, camera
    and framing must be known ids, lens_mm and aperture must be allowed
    values, and seed, if present, must be an int from 0 to 2147483647.
    `look` is optional (an id from LOOKS, default "clean") and always in the result.
    """
    for name in ("description", "camera", "lens_mm", "aperture", "framing"):
        if name not in data:
            raise ShotError(name, f"The {name} is required.")

    camera_ids = [c["id"] for c in CAMERAS]
    framing_ids = [f["id"] for f in FRAMINGS]

    description = data["description"]
    if not isinstance(description, str):
        raise ShotError("description", "The description must be text.")
    description = description.strip()
    if len(description) < 3:
        raise ShotError(
            "description", "The description must be at least 3 characters long."
        )
    if len(description) > 1000:
        raise ShotError(
            "description", "The description must be at most 1000 characters long."
        )

    camera = data["camera"]
    if not isinstance(camera, str) or camera not in camera_ids:
        raise ShotError(
            "camera", f"The camera must be one of: {', '.join(camera_ids)}."
        )

    lens_mm = data["lens_mm"]
    if type(lens_mm) is not int or lens_mm not in LENSES:
        raise ShotError(
            "lens_mm",
            f"The lens must be one of: {', '.join(str(l) for l in LENSES)} mm.",
        )

    aperture = data["aperture"]
    if type(aperture) not in (int, float) or aperture not in APERTURES:
        raise ShotError(
            "aperture",
            f"The aperture must be one of: {', '.join(str(a) for a in APERTURES)}.",
        )

    framing = data["framing"]
    if not isinstance(framing, str) or framing not in framing_ids:
        raise ShotError(
            "framing", f"The framing must be one of: {', '.join(framing_ids)}."
        )

    shot = {
        "description": description,
        "camera": camera,
        "lens_mm": lens_mm,
        "aperture": aperture,
        "framing": framing,
    }
    look = data.get("look", "clean")
    look_ids = [entry["id"] for entry in LOOKS]
    if not isinstance(look, str) or look not in look_ids:
        raise ShotError("look", f"The look must be one of: {', '.join(look_ids)}.")
    shot["look"] = look
    if "seed" not in data:
        shot["seed"] = random.randint(0, 2147483647)
    else:
        seed = data["seed"]
        if type(seed) is not int or not 0 <= seed <= 2147483647:
            raise ShotError(
                "seed", "The seed must be a whole number from 0 to 2147483647."
            )
        shot["seed"] = seed
    return shot
