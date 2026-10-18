"""Goal check: the audit fixes. Run with: node scripts/run-py.js scripts/accept_audit_fixes.py

The OpenCV reference points were computed with OpenCV 5.0.0 (cv2.projectPoints with K = identity and
cv2.undistortPoints, coefficients in OpenCV's order k1, k2, p1, p2, k3), independently of this repository.
Prints one line per problem and exits 1 if there is any.
"""
import inspect
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

problems = []


def check(ok, message):
    if not ok:
        problems.append(message)


try:
    from open_optics import distortion
except Exception as exc:  # pragma: no cover
    print(f"cannot import open_optics.distortion: {exc}")
    sys.exit(1)

for name in ("opencv_to_library_coeffs", "distort_point_opencv", "undistort_point_opencv"):
    check(hasattr(distortion, name), f"open_optics.distortion.{name} does not exist")

# (x, y, k1, k2, p1, p2, k3) -> (x_d, y_d) from OpenCV
FORWARD = [
    ((0.05, 0.03, -0.2, 0.05, 0.005, -0.003, 0.01), (0.049955828919652, 0.029996617351791204)),
    ((0.2, -0.15, -0.2, 0.05, 0.005, -0.003, 0.01), (0.19681205078125005, -0.14743716308593752)),
    ((0.45, 0.3, -0.2, 0.05, 0.005, -0.003, 0.01), (0.4249701290390625, 0.285360919359375)),
    ((0.05, 0.03, -0.2, 0.0, 0.0, 0.0, 0.0), (0.049966, 0.0299796)),
]
INVERSE = [
    ((0.049955828919652, 0.029996617351791204, -0.2, 0.05, 0.005, -0.003, 0.01), (0.049999999999999684, 0.02999999999999996)),
    ((0.19681205078125005, -0.14743716308593752, -0.2, 0.05, 0.005, -0.003, 0.01), (0.19999999999999993, -0.14999999999999994)),
]

if hasattr(distortion, "opencv_to_library_coeffs"):
    got = tuple(distortion.opencv_to_library_coeffs(-0.2, 0.05, 0.005, -0.003, 0.01))
    check(got == (-0.2, 0.05, 0.01, 0.005, -0.003), f"opencv_to_library_coeffs(k1,k2,p1,p2,k3) must return (k1,k2,k3,p1,p2); got {got}")

if hasattr(distortion, "distort_point_opencv"):
    for args, want in FORWARD:
        got = distortion.distort_point_opencv(*args)
        err = max(abs(got[0] - want[0]), abs(got[1] - want[1]))
        check(err < 1e-9, f"distort_point_opencv{args} gave {got}, OpenCV gives {want}")
    check(list(inspect.signature(distortion.distort_point_opencv).parameters)[:7] == ["x", "y", "k1", "k2", "p1", "p2", "k3"],
          "distort_point_opencv must take (x, y, k1, k2, p1, p2, k3=0.0) in that order")

if hasattr(distortion, "undistort_point_opencv"):
    for args, want in INVERSE:
        got = distortion.undistort_point_opencv(*args)
        err = max(abs(got[0] - want[0]), abs(got[1] - want[1]))
        check(err < 1e-7, f"undistort_point_opencv{args} gave {got}, OpenCV gives {want}")

# The existing functions keep their order (k1, k2, k3, p1, p2) and their values.
want = FORWARD[0][1]
got = distortion.distort_point(0.05, 0.03, -0.2, 0.05, 0.01, 0.005, -0.003)
check(max(abs(got[0] - want[0]), abs(got[1] - want[1])) < 1e-9, f"distort_point(x, y, k1, k2, k3, p1, p2) changed: {got}")

# Docstrings: normalised image-plane coordinates, not "frame-fraction".
source = Path(distortion.__file__).read_text(encoding="utf-8")
check("frame-fraction" not in source.lower() and "frame fraction" not in source.lower(), "open_optics/distortion.py still says 'frame-fraction'")
for fn in ("distort_point", "undistort_point"):
    doc = (getattr(distortion, fn).__doc__ or "").lower()
    check("normalised image-plane" in doc or "normalized image-plane" in doc, f"{fn} docstring does not say 'normalised image-plane coordinates'")
    check("opencv" in doc or "k1, k2, k3, p1, p2" in doc or "order" in doc, f"{fn} docstring does not state the coefficient order")

for p in problems:
    print(p)
print("audit fixes: OK" if not problems else f"audit fixes: {len(problems)} problem(s)")
sys.exit(1 if problems else 0)
