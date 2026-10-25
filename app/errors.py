"""Map exceptions raised while talking to ComfyUI to the error dicts the app shows."""

import json

import httpx
from comfy_sdk.exceptions import ComfyError, InvalidWorkflow, JobFailed

UNREACHABLE_MESSAGE = "Lost the connection to ComfyUI. Start ComfyUI, then retry."
DOWNLOAD_MESSAGE = "Could not download the video from ComfyUI."
INTERNAL_MESSAGE = "Something went wrong inside Open Cinema. Check the console for details."


class ComfyUnreachable(Exception):
    """Raised when ComfyUI cannot be reached (for example a failed health check)."""


def _text(value):
    """Return `value` as text: strings as they are, dicts and lists as JSON."""
    if isinstance(value, str):
        return value
    try:
        return json.dumps(value, default=str)
    except (TypeError, ValueError):
        return str(value)


def map_error(exc, stage):
    """Map an exception to `{"code": str, "message": str, "stage": str}`.

    `stage` is 'generate' or 'optics' and is returned unchanged. The message of
    an 'internal' error never contains the exception text.
    """
    if isinstance(exc, InvalidWorkflow):
        message = "ComfyUI refused the request: " + str(exc)
        details = getattr(exc, "details", None)
        if details:
            message += " " + _text(details)
        return {"code": "comfy_rejected", "message": message, "stage": stage}
    if isinstance(exc, JobFailed):
        error = getattr(exc, "error", None)
        if error is not None:
            where = getattr(error, "class_type", None) or getattr(error, "node_id", None)
            detail = getattr(error, "message", None) or str(exc)
            message = f"Node {where} failed: {detail}" if where else f"A node failed: {detail}"
        else:
            message = str(exc)
        return {"code": "job_failed", "message": message, "stage": stage}
    if isinstance(exc, ComfyError):
        status = getattr(exc, "http_status", None)
        if status in (502, 503, 504):
            return {"code": "comfy_unreachable", "message": UNREACHABLE_MESSAGE, "stage": stage}
        code = getattr(exc, "code", None)
        if code == "output_unavailable" or (status == 404 and "output_unavailable" in _text(str(exc))):
            return {"code": "download_failed", "message": DOWNLOAD_MESSAGE, "stage": stage}
    if isinstance(exc, (httpx.TransportError, ConnectionError, TimeoutError, ComfyUnreachable)):
        return {"code": "comfy_unreachable", "message": UNREACHABLE_MESSAGE, "stage": stage}
    if isinstance(exc, (LookupError, OSError)):
        return {"code": "download_failed", "message": DOWNLOAD_MESSAGE, "stage": stage}
    return {"code": "internal", "message": INTERNAL_MESSAGE, "stage": stage}
