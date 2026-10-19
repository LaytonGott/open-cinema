"""Device selection for the Open Optics nodes."""

import os

import torch

_VALID = "cpu, cuda, auto"


def get_device() -> torch.device:
    """Return the torch.device the node code runs on (no units).

    Reads OPEN_OPTICS_DEVICE on every call: 'cpu', 'cuda' or 'auto' (default).
    'auto' uses ComfyUI's device when ComfyUI is loaded, else CUDA when
    available, else the CPU. Raises ValueError for any other value, or for
    'cuda' when CUDA is not available.
    """
    value = os.environ.get("OPEN_OPTICS_DEVICE", "auto")
    if value == "cpu":
        return torch.device("cpu")
    if value == "cuda":
        if torch.cuda.is_available():
            return torch.device("cuda")
        raise ValueError(
            "CUDA was requested (OPEN_OPTICS_DEVICE=cuda) but is not available; "
            "use 'cpu' or 'auto' instead"
        )
    if value == "auto":
        try:
            import comfy.model_management
        except ImportError:
            comfy = None
        if comfy is not None:
            return comfy.model_management.get_torch_device()
        if torch.cuda.is_available():
            return torch.device("cuda")
        return torch.device("cpu")
    raise ValueError(
        f"Invalid OPEN_OPTICS_DEVICE value {value!r}; expected one of: {_VALID}"
    )
