"""Goal check: release basics. Run with: node scripts/run-py.js scripts/accept_release.py

Checks that a licence was chosen consistently with what the code imports, that the README has what a user needs, and that the
example workflow is a well-formed ComfyUI workflow whose nodes, links and widget values match the registered nodes.
It does not decide which licence is right: it checks that the choice agrees with the rule in the goal. Prints one line per
problem and exits 1 if there is any.
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
COMFYUI_LICENSE = Path(r"D:\OpenCinema\ComfyUI_windows_portable\ComfyUI\LICENSE")

problems = []


def check(ok, message):
    if not ok:
        problems.append(message)


def norm(text):
    return re.sub(r"\s+", " ", text).strip()


# ---- imports of ComfyUI code anywhere in the repository's Python files (guarded or lazy imports count)
COMFY_IMPORT = re.compile(r"^\s*(?:from|import)\s+(comfy|comfy_api|comfy_extras|comfy_execution|folder_paths|nodes|server|execution|latent_preview|node_helpers)\b", re.M)
imports_comfy = []
for path in ROOT.rglob("*.py"):
    parts = path.relative_to(ROOT).parts
    if parts[0] in (".venv", "bench", "node_modules", "tests", "scripts") or "__pycache__" in parts:
        continue
    if path.relative_to(ROOT).as_posix() in ("__init__.py",) or parts[0] in ("open_optics", "open_optics_nodes"):
        for m in COMFY_IMPORT.finditer(path.read_text(encoding="utf-8")):
            imports_comfy.append(f"{path.relative_to(ROOT).as_posix()}: {m.group(0).strip()}")

# ---- LICENSE
license_path = ROOT / "LICENSE"
text = license_path.read_text(encoding="utf-8") if license_path.exists() else ""
check(license_path.exists(), "there is no LICENSE file at the repository root")
kind = None
if text:
    if re.match(r"\s*MIT License", text) and "Permission is hereby granted, free of charge" in text:
        kind = "MIT"
        check(re.search(r"Copyright \(c\) 20\d\d \S", text) is not None, "the MIT LICENSE has no 'Copyright (c) <year> <holder>' line")
    elif "GNU GENERAL PUBLIC LICENSE" in text and "Version 3, 29 June 2007" in text:
        kind = "GPL-3.0"
        if COMFYUI_LICENSE.exists():
            check(norm(text) == norm(COMFYUI_LICENSE.read_text(encoding="utf-8")), "the GPL-3.0 LICENSE text differs from the standard text (compare with ComfyUI's LICENSE)")
    elif "Apache License" in text and "Version 2.0, January 2004" in text:
        kind = "Apache-2.0"
    else:
        problems.append("LICENSE is not recognisably MIT, GPL-3.0 or Apache-2.0")
if imports_comfy:
    check(kind == "GPL-3.0", f"the code imports ComfyUI modules ({'; '.join(imports_comfy[:3])}) and ComfyUI is GPL-3.0, so the licence must be GPL-3.0; LICENSE is {kind}")

# ---- README
readme_path = ROOT / "README.md"
readme = readme_path.read_text(encoding="utf-8") if readme_path.exists() else ""
check(readme_path.exists(), "there is no README.md at the repository root")
if readme:
    headings = [h.strip().lower() for h in re.findall(r"^#{1,3}\s+(.+?)\s*$", readme, re.M)]
    for want in ("install", "nodes", "example workflow", "licen"):
        check(any(want in h for h in headings), f"README.md has no heading containing '{want}'")
    check("custom_nodes" in readme, "the install steps must say to put the folder in ComfyUI's custom_nodes folder")
    check("restart" in readme.lower(), "the install steps must say to restart ComfyUI")
    check("workflows/open_optics_demo.json" in readme, "README.md does not point to workflows/open_optics_demo.json")
    check("npm test" in readme, "README.md does not say how to run the tests (npm test)")
    check("GPU" in readme or "CUDA" in readme, "README.md does not say anything about the GPU / CPU behaviour")
    if kind:
        licence_section = readme.lower().split("licen", 1)[-1]
        names = {"MIT": "mit", "GPL-3.0": "gpl", "Apache-2.0": "apache"}
        check(names[kind] in licence_section, f"the README licence section does not name the licence in LICENSE ({kind})")
        if kind != "GPL-3.0":
            check("comfyui" in licence_section and ("not import" in licence_section or "does not import" in licence_section or "no comfyui code" in licence_section),
                  "with a non-GPL licence the README licence section must state that the pack imports no ComfyUI code")
        else:
            check("comfyui" in licence_section, "the README licence section must say why GPL-3.0 (ComfyUI is GPL-3.0)")

# ---- example workflow
try:
    import open_optics_nodes as pack
except Exception as exc:
    problems.append(f"cannot import open_optics_nodes to check the workflow: {exc}")
    pack = None

wf_path = ROOT / "workflows" / "open_optics_demo.json"
check(wf_path.exists(), "workflows/open_optics_demo.json does not exist")
if wf_path.exists() and pack is not None:
    try:
        wf = json.loads(wf_path.read_text(encoding="utf-8"))
    except Exception as exc:
        wf = None
        problems.append(f"workflows/open_optics_demo.json is not valid JSON: {exc}")
    if wf is not None:
        CORE_NODES = {"LoadImage", "PreviewImage", "SaveImage"}
        nodes = {n.get("id"): n for n in wf.get("nodes", [])}
        links = wf.get("links", [])
        check(isinstance(wf.get("nodes"), list) and nodes and len(nodes) == len(wf["nodes"]), "the workflow needs a 'nodes' list with unique ids")
        check(isinstance(links, list) and links, "the workflow needs a non-empty 'links' list")
        used = set()
        for nid, n in nodes.items():
            typ = n.get("type")
            if typ in pack.NODE_CLASS_MAPPINGS:
                used.add(typ)
                cls = pack.NODE_CLASS_MAPPINGS[typ]
                spec = cls.INPUT_TYPES()
                ordered = list((spec.get("required") or {}).items()) + list((spec.get("optional") or {}).items())
                widgets = [(name, s) for name, s in ordered if isinstance(s[0], (list, tuple)) or s[0] in ("FLOAT", "INT", "BOOLEAN", "STRING")]
                values = n.get("widgets_values", [])
                check(len(values) == len(widgets), f"node {nid} ({typ}): widgets_values has {len(values)} values but the node has {len(widgets)} widget inputs ({[w[0] for w in widgets]})")
                for (name, s), v in zip(widgets, values):
                    if isinstance(s[0], (list, tuple)):
                        check(v in s[0], f"node {nid} ({typ}): {name}={v!r} is not one of {list(s[0])}")
                    elif s[0] in ("FLOAT", "INT"):
                        opts = s[1] if len(s) > 1 and isinstance(s[1], dict) else {}
                        ok = isinstance(v, (int, float)) and not isinstance(v, bool) and opts.get("min", float("-inf")) <= v <= opts.get("max", float("inf"))
                        check(ok, f"node {nid} ({typ}): {name}={v!r} is not a number within its range")
            else:
                check(typ in CORE_NODES, f"node {nid} has type {typ!r}, which is neither an Open Optics node nor one of {sorted(CORE_NODES)}")
        for key in ("OpenOptics_DepthToMetric", "OpenOptics_DepthOfField", "OpenOptics_LensDistortion", "OpenOptics_Vignette",
                    "OpenOptics_ChromaticAberration", "OpenOptics_Anamorphic", "OpenOptics_FocalCrop"):
            check(key in used, f"the example workflow does not use {key}")
        check(any(n.get("type") == "LoadImage" for n in nodes.values()) and any(n.get("type") in ("PreviewImage", "SaveImage") for n in nodes.values()),
              "the example workflow needs a LoadImage node and a PreviewImage or SaveImage node")
        seen_links = set()
        for link in links:
            if not (isinstance(link, list) and len(link) == 6):
                problems.append(f"link {link!r} is not [id, from_node, from_slot, to_node, to_slot, type]")
                continue
            lid, a, a_slot, b, b_slot, typ = link
            seen_links.add(lid)
            check(a in nodes and b in nodes, f"link {lid} refers to a node that does not exist")
            if a in nodes and b in nodes:
                outs, ins = nodes[a].get("outputs", []), nodes[b].get("inputs", [])
                check(a_slot < len(outs) and outs[a_slot].get("type") == typ, f"link {lid}: output slot {a_slot} of node {a} is not of type {typ}")
                check(b_slot < len(ins) and ins[b_slot].get("type") == typ and ins[b_slot].get("link") == lid, f"link {lid}: input slot {b_slot} of node {b} is not of type {typ} or does not point back at the link")
        for nid, n in nodes.items():
            for i in n.get("inputs", []):
                if i.get("link") is not None:
                    check(i["link"] in seen_links, f"node {nid} input {i.get('name')} points at link {i['link']}, which is not in 'links'")
        # an Open Optics node's connected IMAGE / MASK inputs and its outputs must match the node definitions
        for nid, n in nodes.items():
            cls = pack.NODE_CLASS_MAPPINGS.get(n.get("type"))
            if cls is None:
                continue
            wanted = [t for t in cls.RETURN_TYPES]
            got = [o.get("type") for o in n.get("outputs", [])]
            check(got == wanted, f"node {nid} ({n['type']}): outputs {got} do not match RETURN_TYPES {wanted}")

for p in problems:
    print(p)
print(f"release basics: OK (licence {kind}, imports ComfyUI code: {bool(imports_comfy)})" if not problems else f"release basics: {len(problems)} problem(s)")
sys.exit(1 if problems else 0)
