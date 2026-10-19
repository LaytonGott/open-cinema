# Open Cinema

An open rebuild of Higgsfield Cinema Studio for Comfy's "Open Source Higgsfield" challenge. Its angle is physically based optics: the Open Optics node pack. Background and sources are in `docs/research.md` (reference only; do not edit it).

## Project rules

- Python 3.12. The lens math core, the package `open_optics/`, is standard library only (`math`, `dataclasses`, `unittest`, `json`). Torch is allowed for the ComfyUI nodes, as described in docs/spec.md, and only in the node pack package `open_optics_nodes/`. `tests/test_core_stdlib_only.py` fails if a core module imports anything else, even inside a function.
- Core code goes in `open_optics/`, one module per topic. Node code goes in `open_optics_nodes/` and calls the core for every optics formula; it does not copy formulas. Tests go in `tests/`, one `test_<module>.py` per module, written with `unittest`.
- ComfyUI nodes use the classic registration: classes with `INPUT_TYPES`, `RETURN_TYPES`, `FUNCTION` and `CATEGORY = "Open Optics"`, listed in `NODE_CLASS_MAPPINGS` and `NODE_DISPLAY_NAME_MAPPINGS` in `open_optics_nodes/__init__.py`, which a root-level `__init__.py` re-exports so ComfyUI finds them when the repository is a custom node folder. `IMAGE` is a float32 torch tensor `[B, H, W, C]` in 0 to 1; `MASK` is `[B, H, W]`. Node tests import the package directly and never import ComfyUI.
- Device: node code runs on `open_optics_nodes.device.get_device()` and nowhere else decides the device: `OPEN_OPTICS_DEVICE` (`cpu`, `cuda` or `auto`, read on every call) overrides; in `auto`, ComfyUI's own device (`comfy.model_management.get_torch_device()`) when ComfyUI is loaded, else CUDA when available, else the CPU. Never hard-code `.cuda()`, `device="cuda"` or `torch.device("cuda")`, and never use `torch.compile`. Nodes take their inputs and return their outputs on the CPU, as ComfyUI passes tensors between nodes. The GPU (an RTX 3090) is free for tests and benchmarks; ComfyUI is not running. Keep GPU memory under 8 GiB and release it after a test (`torch.cuda.empty_cache()`).
- Tests use images of at most 64 x 64 pixels, except the benchmark tests, which are skipped unless `OPEN_OPTICS_BENCH=1` and are run with `npm run test:bench` (their names contain "bench"; start them with `@unittest.skipUnless(os.environ.get("OPEN_OPTICS_BENCH") == "1", "set by npm run test:bench")`). Every node test must pass on the CPU (`OPEN_OPTICS_DEVICE=cpu`) and on the GPU.
- Run the tests with `npm test` (it runs `scripts/run-tests.js`, which runs `python -m unittest discover -s tests -t .` with the project's Python: `OPEN_OPTICS_PYTHON` if set, else `.venv`, which has CUDA torch and numpy; the system Python has neither). Run it before you finish and fix every failure. Torch tests import torch directly and must not skip when it is missing.
- You cannot install packages or use the network. ComfyUI is installed at `D:\OpenCinema\ComfyUI_windows_portable\ComfyUI`; read it for the node API if you need to, never edit it. The only ComfyUI import allowed in this repository is the guarded, optional `import comfy.model_management` inside `get_device()` in `open_optics_nodes/device.py`; tests never import ComfyUI.
- Every public function has a docstring that states its units (millimetres, metres, degrees or radians) and what it returns. Tests check known values with a stated tolerance (`assertAlmostEqual` with `places` or `delta`), taken from a formula worked by hand or a published figure, not from the function itself.
- Do not edit `docs/research.md`, `docs/spec.md`, `docs/benchmarks.md`, `bench/`, `CLAUDE.md`, `.claude/`, `scripts/run-tests.js`, `scripts/py.js`, `scripts/run-py.js`, `scripts/accept_*.py` (the goal checks) or `.beads/`.

## Delegating coding

You plan and review. A worker model codes.

If you are the worker (your task starts "You are working on bead ..."), ignore this section and do the coding yourself with your own tools.

The loop's worker is Sonnet 5.5 through `claude -p`, started from the harness folder `C:\Users\97lay\Desktop\REA DeepSeek` with this repository as its target: `node run-night.js --repo "C:\Users\97lay\Desktop\Open Cinema"` loops over goals.md, `node preflight.js --repo "..."` checks the setup first. A separate, fresh Sonnet session reviews each result.

- Give one small, specific task per prompt.
- After each task, check `git diff` and run `npm test`. Then accept, fix up or revert.
- After 3 failed attempts at a task, do it yourself.
- File any new work you discover as a bead with a discovered-from link to the bead you're working on: `bd create "<title>" --deps discovered-from:<current-bead-id>`.

## Changing code

Before changing a function, data shape or stored value, search the whole repo for every place that calls, reads or writes it, and update them all.
