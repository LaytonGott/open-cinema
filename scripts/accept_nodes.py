"""Goal check: the ComfyUI node pack. Run with: node scripts/run-py.js scripts/accept_nodes.py

Checks the registration (classic NODE_CLASS_MAPPINGS) and then runs every registered node on a small CPU image with
default or synthesised inputs: outputs must be finite, IMAGE outputs float32 [B, H, W, C] in 0..1, MASK outputs
float32 [B, H, W], and two runs give identical results.

Depth inputs: a node that takes depth as either an IMAGE or a MASK declares them as two optional inputs (a MASK one and an
IMAGE one whose names contain "depth"). Such a node is run once with each of them alone, must give the same result for the
same data in either form, and must raise ValueError when neither or both are connected.

It does not check the optics; the unit tests do that. Prints one line per problem and exits 1 if there is any.
"""
import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

REQUIRED = {
    "OpenOptics_FocalCrop": "crop",
    "OpenOptics_DepthOfField": "depth of field",
    "OpenOptics_DepthToMetric": "depth to metric",
    "OpenOptics_LensDistortion": "distortion",
    "OpenOptics_Vignette": "vignette",
    "OpenOptics_ChromaticAberration": "chromatic",
    "OpenOptics_Anamorphic": "anamorphic",
}

problems = []


def check(ok, message):
    if not ok:
        problems.append(message)


try:
    import torch
    import open_optics_nodes as pack
except Exception as exc:
    print(f"cannot import torch / open_optics_nodes: {exc}")
    sys.exit(1)

classes = getattr(pack, "NODE_CLASS_MAPPINGS", None)
names = getattr(pack, "NODE_DISPLAY_NAME_MAPPINGS", None)
check(isinstance(classes, dict) and classes, "open_optics_nodes.NODE_CLASS_MAPPINGS is missing or empty")
check(isinstance(names, dict), "open_optics_nodes.NODE_DISPLAY_NAME_MAPPINGS is missing")
classes = classes if isinstance(classes, dict) else {}
names = names if isinstance(names, dict) else {}
for key in REQUIRED:
    check(key in classes, f"node {key} is not registered ({REQUIRED[key]})")
for key in classes:
    check(key in names, f"node {key} has no display name")

# The repository root must work as a ComfyUI custom node folder.
root_init = ROOT / "__init__.py"
check(root_init.exists(), "the repository root has no __init__.py re-exporting the node mappings")
if root_init.exists():
    try:
        spec = importlib.util.spec_from_file_location("open_optics_pack_root", root_init, submodule_search_locations=[str(ROOT)])
        module = importlib.util.module_from_spec(spec)
        sys.modules["open_optics_pack_root"] = module
        spec.loader.exec_module(module)
        check(set(getattr(module, "NODE_CLASS_MAPPINGS", {})) == set(classes), "the root __init__.py does not export the same NODE_CLASS_MAPPINGS")
        check(set(getattr(module, "NODE_DISPLAY_NAME_MAPPINGS", {})) == set(names), "the root __init__.py does not export the same NODE_DISPLAY_NAME_MAPPINGS")
    except Exception as exc:
        problems.append(f"the root __init__.py cannot be imported as a package: {exc}")

torch.manual_seed(0)
IMAGE = torch.rand(2, 16, 16, 3, dtype=torch.float32)
METRES = (torch.rand(2, 16, 16, dtype=torch.float32) * 4.0 + 1.0)  # metric depth, 1 to 5 m
RELATIVE = torch.rand(2, 16, 16, dtype=torch.float32)  # relative or inverse depth, 0 to 1 (what a depth estimator outputs)


def depth_data(key):
    return RELATIVE if key == "OpenOptics_DepthToMetric" else METRES


def as_image(mask):
    return mask.unsqueeze(-1).repeat(1, 1, 1, 3).contiguous()


def synth(key, name, spec):
    kind = spec[0]
    options = spec[1] if len(spec) > 1 and isinstance(spec[1], dict) else {}
    if isinstance(kind, (list, tuple)):
        return kind[0]
    if kind == "IMAGE":
        return as_image(depth_data(key)) if "depth" in name.lower() else IMAGE.clone()
    if kind == "MASK":
        return depth_data(key).clone()
    if kind in ("FLOAT", "INT", "BOOLEAN", "STRING"):
        if "default" in options:
            return options["default"]
        return {"FLOAT": 1.0, "INT": 1, "BOOLEAN": False, "STRING": ""}[kind]
    raise ValueError(f"cannot synthesise an input of type {kind} for {name}")


def depth_options(inputs):
    """The optional IMAGE / MASK inputs that carry depth (a node that offers a choice has at least two)."""
    optional = inputs.get("optional", {}) or {}
    return {name: spec for name, spec in optional.items() if spec and spec[0] in ("IMAGE", "MASK") and "depth" in name.lower()}


def call(cls, key, extra=None, with_optional=()):
    inputs = cls.INPUT_TYPES()
    kwargs = {name: synth(key, name, spec) for name, spec in inputs.get("required", {}).items()}
    optional = inputs.get("optional", {}) or {}
    for name in with_optional:
        kwargs[name] = synth(key, name, optional[name])
    kwargs.update(extra or {})
    return getattr(cls(), cls.FUNCTION)(**kwargs)


def check_output(key, kind, value):
    check(isinstance(value, torch.Tensor), f"{key}: an output of type {kind} is not a torch tensor")
    if not isinstance(value, torch.Tensor):
        return
    check(bool(torch.isfinite(value).all()), f"{key}: an output of type {kind} has NaN or inf")
    check(value.dtype == torch.float32, f"{key}: an output of type {kind} is {value.dtype}, not float32")
    if kind == "IMAGE":
        check(value.dim() == 4 and value.shape[-1] in (1, 3, 4), f"{key}: IMAGE output has shape {tuple(value.shape)}, expected [B, H, W, C]")
        check(float(value.min()) >= -1e-5 and float(value.max()) <= 1.0 + 1e-5, f"{key}: IMAGE output is outside 0..1 ({float(value.min()):.4f}..{float(value.max()):.4f})")
    if kind == "MASK":
        check(value.dim() == 3, f"{key}: MASK output has shape {tuple(value.shape)}, expected [B, H, W]")


def check_results(key, cls, first, second, label):
    ok = isinstance(first, tuple) and len(first) == len(cls.RETURN_TYPES)
    check(ok, f"{key}{label}: the function must return a tuple with one item per RETURN_TYPES entry")
    if not ok:
        return
    for kind, value, again in zip(cls.RETURN_TYPES, first, second):
        if kind in ("IMAGE", "MASK"):
            check_output(key + label, kind, value)
            check(isinstance(again, torch.Tensor) and torch.equal(value, again), f"{key}{label}: two runs with the same input gave different {kind} outputs")


def raises_value_error(cls, key, with_optional):
    try:
        call(cls, key, with_optional=with_optional)
    except ValueError:
        return True
    except Exception:
        return False
    return False


for key, cls in sorted(classes.items()):
    for attr in ("INPUT_TYPES", "RETURN_TYPES", "FUNCTION", "CATEGORY"):
        check(hasattr(cls, attr), f"{key} has no {attr}")
    if not all(hasattr(cls, attr) for attr in ("INPUT_TYPES", "RETURN_TYPES", "FUNCTION", "CATEGORY")):
        continue
    check(str(cls.CATEGORY).startswith("Open Optics"), f"{key}: CATEGORY is {cls.CATEGORY!r}, expected it to start with 'Open Optics'")
    check(hasattr(cls, cls.FUNCTION), f"{key}: FUNCTION {cls.FUNCTION!r} is not a method")
    choices = depth_options(cls.INPUT_TYPES())
    try:
        if len(choices) >= 2:
            masks = [n for n, s in choices.items() if s[0] == "MASK"]
            images = [n for n, s in choices.items() if s[0] == "IMAGE"]
            check(bool(masks) and bool(images), f"{key}: depth must be offered both as a MASK input and as an IMAGE input (optional inputs with 'depth' in the name)")
            results = {}
            for name in choices:
                results[name] = (call(cls, key, with_optional=[name]), call(cls, key, with_optional=[name]))
                check_results(key, cls, results[name][0], results[name][1], f" (depth from {name})")
            if masks and images:
                a, b = results[masks[0]][0], results[images[0]][0]
                same = isinstance(a, tuple) and isinstance(b, tuple) and len(a) == len(b) and all(
                    torch.allclose(x, y, atol=1e-5, rtol=1e-5) for x, y in zip(a, b) if isinstance(x, torch.Tensor) and isinstance(y, torch.Tensor))
                check(same, f"{key}: the same depth data gave different results as a MASK and as an IMAGE (an IMAGE depth is read as the mean of its channels)")
            check(raises_value_error(cls, key, ()), f"{key}: with no depth connected it must raise ValueError")
            check(raises_value_error(cls, key, list(choices)), f"{key}: with both a MASK and an IMAGE depth connected it must raise ValueError")
        else:
            check_results(key, cls, call(cls, key), call(cls, key), "")
    except Exception as exc:
        problems.append(f"{key}: running on a 2x16x16 image failed: {type(exc).__name__}: {exc}")

for path in sorted((ROOT / "open_optics_nodes").glob("*.py")):
    text = path.read_text(encoding="utf-8")
    check(".cuda(" not in text and 'device="cuda"' not in text and "device='cuda'" not in text, f"{path.name} uses CUDA; everything must run on the CPU")

for p in problems:
    print(p)
print("node pack: OK" if not problems else f"node pack: {len(problems)} problem(s)")
sys.exit(1 if problems else 0)
