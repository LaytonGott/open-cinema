# Open Cinema

An open rebuild of Higgsfield Cinema Studio for Comfy's "Open Source Higgsfield" challenge. Its angle is physically based optics: the Open Optics node pack. Background and sources are in `docs/research.md` (reference only; do not edit it).

## Project rules

- Python 3.12, standard library only (`math`, `dataclasses`, `unittest`). No ComfyUI, torch or numpy imports yet.
- Code goes in `open_optics/`, one module per topic. Tests go in `tests/`, one `test_<module>.py` per module, written with `unittest`.
- Run the tests with `npm test` (it runs `python -m unittest discover -s tests -t .`). `package.json` exists only for that command. Run it before you finish and fix every failure.
- Every public function has a docstring that states its units (millimetres, metres, degrees or radians) and what it returns. Tests check known values with a stated tolerance (`assertAlmostEqual` with `places` or `delta`), taken from a formula worked by hand or a published figure, not from the function itself.
- Do not edit `docs/research.md`, `CLAUDE.md`, `.claude/` or `.beads/`.

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
