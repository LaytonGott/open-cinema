"""Build the shot record of docs/app-spec.md section 4.1."""

import copy

from app.shot import build_prompt, subject_distance


def new_record(shot_id, params):
    """Return a new shot record (dict) for the id `shot_id` and the cleaned `params`.

    `params` comes from app.shot.validate_shot (lens_mm in millimetres,
    aperture as an f-number). derived.subject_distance_m is in metres,
    rounded to 4 decimals. The record is queued, with progress 0.0 (0 to 1)
    and elapsed_s 0.0 (seconds). ShotStore.add adds created_at and seq.
    """
    params = dict(params)
    return {
        "id": shot_id,
        "params": params,
        "derived": {
            "subject_distance_m": round(
                subject_distance(params["lens_mm"], params["framing"]), 4),
            "prompt": build_prompt(params),
        },
        "status": "queued",
        "progress": 0.0,
        "message": "Waiting for ComfyUI",
        "stages": [
            {"id": "generate", "label": "Generate video", "state": "pending", "progress": 0.0},
            {"id": "optics", "label": "Apply optics", "state": "pending", "progress": 0.0},
        ],
        "elapsed_s": 0.0,
        "error": None,
        "reapply_error": None,
        "before_url": None,
        "versions": [],
        "current_version": None,
    }


def public_record(record):
    """Return a deep copy of the shot `record` without internal keys.

    Drops `seq` and every key starting with '_'. Values keep their units
    (metres, seconds, f-numbers).
    """
    return {k: copy.deepcopy(v) for k, v in record.items()
            if k != "seq" and not k.startswith("_")}
