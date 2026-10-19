"""Goal check: subject-anchored depth. Run with: node scripts/run-py.js scripts/accept_subject.py

Runs OpenOptics_DepthToMetric on small hand-worked inputs (9 x 9 depth maps) and compares with values worked by hand, in the
default mode (the existing near/far behaviour must not change) and in the new "subject" mode.
Prints one line per problem and exits 1 if there is any.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

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

cls = pack.NODE_CLASS_MAPPINGS.get("OpenOptics_DepthToMetric")
if cls is None:
    print("OpenOptics_DepthToMetric is not registered")
    sys.exit(1)

types = cls.INPUT_TYPES()
all_inputs = {**types.get("required", {}), **(types.get("optional", {}) or {})}
for name in ("mode", "subject_m", "subject_x", "subject_y", "subject_radius_px", "anchor_scope", "subject_mask", "near_m", "far_m", "inverse_depth"):
    check(name in all_inputs, f"DepthToMetric has no input {name}")
if problems:
    for p in problems:
        print(p)
    sys.exit(1)
check(list(all_inputs["mode"][0]) == ["near_far", "subject"], f"mode must offer exactly ['near_far', 'subject'] in that order; got {list(all_inputs['mode'][0])}")
check(list(all_inputs["anchor_scope"][0]) == ["batch", "frame"], f"anchor_scope must offer exactly ['batch', 'frame'] in that order; got {list(all_inputs['anchor_scope'][0])}")
check(all_inputs["mode"][1].get("default") == "near_far", "mode must default to near_far")

node = cls()
call = getattr(node, cls.FUNCTION)


def run(depth, **kw):
    """Calls the node with the depth as a MASK; returns the metres MASK (the first output)."""
    out = call(depth_mask=depth, **kw)
    check(isinstance(out, tuple) and isinstance(out[0], torch.Tensor), "the node must return a tuple whose first item is the depth in metres (a tensor)")
    return out[0]


def close(a, b, tol=1e-5):
    return abs(float(a) - float(b)) <= tol


# 9 x 9 map: base 0.4, a 3 x 3 subject window (rows 3 to 5, columns 3 to 5) at 0.8, a bright pixel 1.6 at (0, 0), a dark one 0.1 at (8, 8)
D = torch.full((1, 9, 9), 0.4)
D[:, 3:6, 3:6] = 0.8
D[:, 0, 0] = 1.6
D[:, 8, 8] = 0.1
window = torch.zeros(1, 9, 9)
window[:, 3:6, 3:6] = 1.0
base_only = torch.zeros(1, 9, 9)
base_only[:, 6:8, 0:3] = 1.0

# The default mode is unchanged: near_m = 1, far_m = 5, percentiles 0 and 100, inverse depth, d = 0, 0.5, 1 -> 5, 1.666667, 1 m
ramp = torch.tensor([[[0.0, 0.5, 1.0]]])
out = run(ramp, near_m=1.0, far_m=5.0, inverse_depth=True, low_percentile=0.0, high_percentile=100.0)
check(all(close(out[0, 0, i], v) for i, v in enumerate([5.0, 1.666667, 1.0])), f"default mode changed: inverse ramp gave {out.flatten().tolist()}, expected [5.0, 1.666667, 1.0]")

# Subject mode, inverse depth (large = near): Z = subject_m * d_s / d, then clamped to [near_m, far_m]
common = dict(mode="subject", subject_m=2.0, near_m=0.5, far_m=10.0, subject_x=0.5, subject_y=0.5, subject_radius_px=1, anchor_scope="batch")
out = run(D, inverse_depth=True, **common)
expect = {(4, 4): 2.0, (0, 1): 4.0, (0, 0): 1.0, (8, 8): 10.0}
for (r, c), v in expect.items():
    check(close(out[0, r, c], v), f"subject mode, inverse depth, point (0.5, 0.5): pixel ({r}, {c}) is {float(out[0, r, c]):.5f} m, expected {v}")
# Not inverse (large = far): Z = subject_m * d / d_s
out = run(D, inverse_depth=False, **common)
expect = {(4, 4): 2.0, (0, 1): 1.0, (0, 0): 4.0, (8, 8): 0.5}
for (r, c), v in expect.items():
    check(close(out[0, r, c], v), f"subject mode, depth-like input, point (0.5, 0.5): pixel ({r}, {c}) is {float(out[0, r, c]):.5f} m, expected {v}")
# The subject pixel is exactly at the subject distance
check(close(run(D, inverse_depth=True, **common)[0, 3:6, 3:6].mean(), 2.0), "the subject window must come out at subject_m")

# A mask gives the same result as the point when it covers the same window; the mask takes the place of the point
common_mask = {k: v for k, v in common.items() if k not in ("subject_x", "subject_y", "subject_radius_px")}
out_mask = call(depth_mask=D, subject_mask=window, inverse_depth=True, **common_mask)[0]
check(torch.allclose(out_mask, run(D, inverse_depth=True, **common), atol=1e-5), "a subject_mask covering the 3 x 3 window must give the same result as the point with radius 1")
# A mask somewhere else: that region (value 0.4) becomes subject_m, so the old subject window (0.8) is nearer
out_other = call(depth_mask=D, subject_mask=base_only, inverse_depth=True, **common_mask)[0]
check(close(out_other[0, 7, 1], 2.0) and close(out_other[0, 4, 4], 1.0), f"subject_mask on the 0.4 region: expected 2.0 m there and 1.0 m on the 0.8 window; got {float(out_other[0, 7, 1]):.4f} and {float(out_other[0, 4, 4]):.4f}")

# The same data as an IMAGE
out_img = call(depth_image=D.unsqueeze(-1).repeat(1, 1, 1, 3), inverse_depth=True, **common)[0]
check(torch.allclose(out_img, run(D, inverse_depth=True, **common), atol=1e-5), "depth given as an IMAGE must give the same result as a MASK in subject mode")

# Two frames: the subject is 0.8 in frame 0 and 0.4 in frame 1
two = torch.cat([D, D * 0.5], dim=0)
batch = run(two, inverse_depth=True, **common)  # anchor_scope batch: d_s is the median of all 18 subject-window values = (0.4 + 0.8) / 2 = 0.6
check(close(batch[0, 4, 4], 1.5) and close(batch[1, 4, 4], 3.0), f"anchor_scope batch: subject pixels should be 1.5 m and 3.0 m (d_s = 0.6, the mean of the two middle values); got {float(batch[0, 4, 4]):.4f} and {float(batch[1, 4, 4]):.4f}")
frame = run(two, inverse_depth=True, **{**common, "anchor_scope": "frame"})
check(close(frame[0, 4, 4], 2.0) and close(frame[1, 4, 4], 2.0), f"anchor_scope frame: the subject must be 2.0 m in both frames; got {float(frame[0, 4, 4]):.4f} and {float(frame[1, 4, 4]):.4f}")

# Validation
def raises(**kw):
    kwargs = {**common, "inverse_depth": True, **kw}
    try:
        call(depth_mask=D, **kwargs)
    except ValueError:
        return True
    except Exception:
        return False
    return False


check(raises(subject_m=0.0), "subject_m = 0 must raise ValueError")
check(raises(subject_m=0.2), "subject_m below near_m must raise ValueError")
check(raises(subject_m=20.0), "subject_m above far_m must raise ValueError")
check(raises(subject_x=1.5), "subject_x outside 0..1 must raise ValueError")
check(raises(subject_y=-0.1), "subject_y outside 0..1 must raise ValueError")
check(raises(subject_radius_px=-1), "a negative subject_radius_px must raise ValueError")
check(raises(mode="nonsense"), "an unknown mode must raise ValueError")
try:
    call(depth_mask=D, subject_mask=torch.zeros(1, 9, 9), inverse_depth=True, **common_mask)
    problems.append("an empty subject_mask must raise ValueError")
except ValueError:
    pass
try:
    call(depth_mask=torch.zeros(1, 9, 9), inverse_depth=True, **common)
    problems.append("a subject region with no valid depth (all zeros) must raise ValueError")
except ValueError:
    pass
try:
    call(**common, inverse_depth=True)
    problems.append("no depth connected must raise ValueError")
except ValueError:
    pass

# The result feeds Depth of Field: the subject is in focus when focus_m equals subject_m
dof = pack.NODE_CLASS_MAPPINGS.get("OpenOptics_DepthOfField")
if dof is not None:
    metres = run(D, inverse_depth=True, **common)
    img = torch.rand(1, 9, 9, 3)
    result = getattr(dof(), dof.FUNCTION)(image=img, depth_mask=metres, focal_mm=50.0, f_number=2.0, focus_m=2.0, sensor_width_mm=36.0, quality="normal", max_radius_px=8, colorspace="srgb")
    coc = result[1]
    check(float(coc[0, 4, 4]) < 1e-3, f"with focus_m = subject_m the subject pixel must have no blur; its coc_px is {float(coc[0, 4, 4]):.4f}")
    check(float(coc[0, 0, 1]) > float(coc[0, 4, 4]), "a pixel 2 m behind the subject must be blurrier than the subject")

for p in problems:
    print(p)
print("subject depth: OK" if not problems else f"subject depth: {len(problems)} problem(s)")
sys.exit(1 if problems else 0)
