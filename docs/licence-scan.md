# Licence scan: ComfyUI imports

## Method

Every Python file of the pack (root `__init__.py`, `open_optics/`, `open_optics_nodes/`) was searched for imports of `comfy`, `comfy_api`, `comfy_extras`, `comfy_execution`, `folder_paths`, `nodes`, `server`, `execution`, `latent_preview` and `node_helpers`, including guarded and lazy (in-function) imports.

## Result

- The only hit is `import comfy.model_management` inside `get_device()` in `open_optics_nodes/device.py`. It is guarded by `try/except ImportError` and used only when `OPEN_OPTICS_DEVICE=auto`.
- No other pack file imports ComfyUI.

## Other points

- No code was copied from other packs. `docs/research.md` lists packs that have no licence; none of them were copied.
- torch and numpy are installed by ComfyUI, not bundled with the pack.

## Consequence

The pack is used as a combined work with ComfyUI (GPL-3.0), so GPL-3.0 is chosen.
