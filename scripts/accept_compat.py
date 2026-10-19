"""Goal check: workflow compatibility. Run with: node scripts/run-py.js scripts/accept_compat.py

The nodes must keep working with workflows saved against older versions of the pack. A workflow is a saved graph; when ComfyUI
loads it, an input that did not exist yet is missing from the graph, and ComfyUI refuses ("Required input is missing") when a
missing input is required. So every input added after the first release must be optional with a default.

  first release = the pack as it was when it was first run in ComfyUI (commit eb10871); its INPUT_TYPES are in
  tests/fixtures/first_release_inputs.json.
Checks:
  1. Every node still has every first-release input (same type) and output, and every input added since is in INPUT_TYPES
     "optional" with a default (a combo may default to its first choice), is listed after the old inputs (saved UI workflows store widget
     values by position), and every added output comes after the old ones.
  2. The saved workflows in tests/fixtures/legacy_workflows (API-format graphs from the end-to-end ComfyUI test, and the demo workflow as
     released in UI format), and the demo workflow in workflows/, validate like ComfyUI validates them and their Open Optics
     nodes run, called with exactly the inputs the workflow has, on small synthetic images.
  3. The legacy files are the files they were: their content hashes are checked.
Prints one line per problem and exits 1 if there is any.
"""
import hashlib
import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
FIXTURES = ROOT / "tests" / "fixtures"

# sha256 of each fixture's canonical JSON (keys sorted, no spaces): the files must not be edited to make a check pass
EXPECTED = {
    "first_release_inputs.json": "b970d8c065d2467b2ba730774e09b4afc46aa9757d1e4e68fde54dcf8088bc36",
    "legacy_workflows/open_optics_demo_release_ui.json": "7fefe5dcd074912ad0c54c01ed5373fd6b6b1528e2e3baa7c478ca67c5087397",
    "legacy_workflows/pipeline_depth_api.json": "2bddcbecdf45f8f86ea787060f0edae5814a2d6210ad4abb8b2c1ef21a128d69",
    "legacy_workflows/pipeline_dof_api.json": "70d31d5164cc05df211ad1b691ba780067c734b929a9509ab6e97587be8ae889",
    "legacy_workflows/pipeline_full_api.json": "5d1c26ae8368adf078825973e44e42293923279952d2cfac74b40c81246619a9",
}
WIDGET_TYPES = ("FLOAT", "INT", "BOOLEAN", "STRING")

problems = []


def check(ok, message):
    if not ok:
        problems.append(message)


def finish():
    for p in problems:
        print(p)
    print("workflow compatibility: OK" if not problems else f"workflow compatibility: {len(problems)} problem(s)")
    sys.exit(1 if problems else 0)


try:
    import torch
    import open_optics_nodes as pack
except Exception as exc:
    print(f"cannot import torch / open_optics_nodes: {exc}")
    sys.exit(1)

# ---- 3. the legacy files are untouched
for name, want in EXPECTED.items():
    path = FIXTURES / name
    if not path.exists():
        problems.append(f"tests/fixtures/{name} is missing")
        continue
    got = hashlib.sha256(json.dumps(json.loads(path.read_text(encoding="utf-8")), sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    check(got == want, f"tests/fixtures/{name} has been changed (its content hash differs); legacy workflows must stay as they were saved")
if problems:
    finish()

snapshot = json.loads((FIXTURES / "first_release_inputs.json").read_text(encoding="utf-8"))
classes = pack.NODE_CLASS_MAPPINGS


def is_widget(spec):
    return isinstance(spec[0], (list, tuple)) or spec[0] in WIDGET_TYPES


def widget_names(types):
    return [n for n, s in list(types.get("required", {}).items()) + list((types.get("optional") or {}).items()) if is_widget(s)]


def same_type(old, new):
    if isinstance(old, list) or isinstance(new, (list, tuple)):
        return isinstance(old, list) and isinstance(new, (list, tuple)) and set(old) <= set(new)
    return old == new


# ---- 1. the first-release inputs and outputs are still there; additions are optional, with defaults, and last
for key, old in sorted(snapshot.items()):
    cls = classes.get(key)
    if cls is None:
        problems.append(f"{key} existed in the first release but is no longer registered")
        continue
    types = cls.INPUT_TYPES()
    required, optional = types.get("required", {}), types.get("optional") or {}
    both = {**required, **optional}
    old_names = [n for n, *_ in old["required"]] + [n for n, *_ in old["optional"]]
    for name, kind, opts in old["required"] + old["optional"]:
        if name not in both:
            problems.append(f"{key}: the first-release input {name} is gone")
        else:
            check(same_type(kind, both[name][0]), f"{key}: the type of the first-release input {name} changed from {kind} to {both[name][0]}")
    for name, spec in both.items():
        if name in old_names:
            continue
        check(name in optional, f"{key}: {name} was added after the first release, so it must be in INPUT_TYPES 'optional' (an old workflow does not have it), not 'required'")
        if is_widget(spec) and not isinstance(spec[0], (list, tuple)):
            check(len(spec) > 1 and isinstance(spec[1], dict) and "default" in spec[1], f"{key}: the added input {name} has no default")
    old_widgets = [n for n, kind, _ in old["required"] + old["optional"] if isinstance(kind, list) or kind in WIDGET_TYPES]
    check(widget_names(types)[:len(old_widgets)] == old_widgets, f"{key}: the widgets must keep their first-release order with new ones after them (saved workflows store widget values by position); first-release {old_widgets}, now {widget_names(types)}")
    check(list(cls.RETURN_TYPES)[:len(old["return_types"])] == old["return_types"], f"{key}: RETURN_TYPES must start with the first-release outputs {old['return_types']}; now {list(cls.RETURN_TYPES)}")

# ---- 2. saved workflows validate and run
torch.manual_seed(0)


def synth(want, consumer, name):
    if want == "IMAGE":
        if "depth" in name.lower():
            data = torch.rand(2, 16, 24) if consumer == "OpenOptics_DepthToMetric" else torch.rand(2, 16, 24) * 8.0 + 1.0
            return data.unsqueeze(-1).repeat(1, 1, 1, 3).contiguous()
        return torch.rand(2, 16, 24, 3)
    if want == "MASK":
        if "subject" in name.lower():
            m = torch.zeros(2, 16, 24)
            m[:, 6:10, 10:14] = 1.0
            return m
        return torch.rand(2, 16, 24) if consumer == "OpenOptics_DepthToMetric" else torch.rand(2, 16, 24) * 8.0 + 1.0
    raise ValueError(f"cannot synthesise an input of type {want} for {name}")


def validate_values(label, key, provided):
    """ComfyUI's check: every required input is present, and the values that were given are of the right kind and within range."""
    types = classes[key].INPUT_TYPES()
    for name, spec in types.get("required", {}).items():
        check(name in provided, f"{label}: {key}: Required input is missing: {name}")
    for name, value in provided.items():
        spec = {**types.get("required", {}), **(types.get("optional") or {})}.get(name)
        if spec is None or isinstance(value, list):
            continue
        kind, opts = spec[0], (spec[1] if len(spec) > 1 and isinstance(spec[1], dict) else {})
        if isinstance(kind, (list, tuple)):
            check(value in kind, f"{label}: {key}.{name}={value!r} is not one of {list(kind)}")
        elif kind in ("FLOAT", "INT"):
            ok = isinstance(value, (int, float)) and not isinstance(value, bool) and opts.get("min", -math.inf) <= value <= opts.get("max", math.inf)
            check(ok, f"{label}: {key}.{name}={value!r} is not a number within its range")


def run_node(label, key, kwargs):
    cls = classes[key]
    try:
        out = getattr(cls(), cls.FUNCTION)(**kwargs)
    except Exception as exc:
        problems.append(f"{label}: {key} failed with the workflow's inputs {sorted(kwargs)}: {type(exc).__name__}: {exc}")
        return None
    ok = isinstance(out, tuple) and all(bool(torch.isfinite(t).all()) for t in out if isinstance(t, torch.Tensor))
    check(ok, f"{label}: {key} returned something that is not a tuple of finite tensors")
    return out if ok else None


def run_api_graph(label, graph):
    cache = {}

    def resolve(node_id, slot, want, consumer, name):
        node = graph.get(str(node_id))
        if node is None or node["class_type"] not in classes:
            return synth(want, consumer, name)
        if node_id not in cache:
            cache[node_id] = run_api_node(str(node_id))
        out = cache[node_id]
        return None if out is None else out[slot]

    def run_api_node(node_id):
        node = graph[node_id]
        key = node["class_type"]
        types = classes[key].INPUT_TYPES()
        spec = {**types.get("required", {}), **(types.get("optional") or {})}
        kwargs = {}
        for name, value in node["inputs"].items():
            if isinstance(value, list) and len(value) == 2:
                kwargs[name] = resolve(value[0], value[1], spec[name][0] if name in spec else "IMAGE", key, name)
            else:
                kwargs[name] = value
        validate_values(label, key, node["inputs"])
        return None if any(v is None for v in kwargs.values()) else run_node(label, key, kwargs)

    for node_id, node in graph.items():
        if node["class_type"] in classes and node_id not in cache:
            cache[node_id] = run_api_node(node_id)
    return sum(1 for n in graph.values() if n["class_type"] in classes)


def run_ui_workflow(label, wf):
    nodes = {n["id"]: n for n in wf["nodes"]}
    by_target = {}
    for lid, a, a_slot, b, b_slot, kind in wf["links"]:
        by_target[(b, b_slot)] = (a, a_slot, kind)
    cache = {}

    def run_ui_node(nid):
        n = nodes[nid]
        key = n["type"]
        types = classes[key].INPUT_TYPES()
        spec = {**types.get("required", {}), **(types.get("optional") or {})}
        names = widget_names(types)
        values = n.get("widgets_values", [])
        check(len(values) <= len(names), f"{label}: node {nid} ({key}) has {len(values)} widget values but the node now has only {len(names)} widgets")
        provided = dict(zip(names, values))
        kwargs = dict(provided)
        for slot, inp in enumerate(n.get("inputs", [])):
            link = by_target.get((nid, slot))
            if link is None:
                continue
            src, src_slot, kind = link
            if nodes[src]["type"] in classes:
                if src not in cache:
                    cache[src] = run_ui_node(src)
                kwargs[inp["name"]] = None if cache[src] is None else cache[src][src_slot]
            else:
                kwargs[inp["name"]] = synth(kind, key, inp["name"])
            provided[inp["name"]] = [src, src_slot]
        validate_values(label, key, provided)
        return None if any(v is None for v in kwargs.values()) else run_node(label, key, kwargs)

    for nid, n in nodes.items():
        if n["type"] in classes and nid not in cache:
            cache[nid] = run_ui_node(nid)
    return sum(1 for n in nodes.values() if n["type"] in classes)


for path in sorted((FIXTURES / "legacy_workflows").glob("*.json")) + [ROOT / "workflows" / "open_optics_demo.json"]:
    label = path.relative_to(ROOT).as_posix()
    if not path.exists():
        problems.append(f"{label} is missing")
        continue
    data = json.loads(path.read_text(encoding="utf-8"))
    try:
        count = run_ui_workflow(label, data) if "nodes" in data and "links" in data else run_api_graph(label, data)
    except Exception as exc:
        problems.append(f"{label}: could not be run: {type(exc).__name__}: {exc}")
        continue
    check(count > 0, f"{label} contains no Open Optics nodes, so it proves nothing")

finish()
