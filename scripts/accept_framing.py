"""Goal check: framing-consistent distance. Run with: node scripts/run-py.js scripts/accept_framing.py

open_optics/framing.py estimates how far away a subject is from how big it is in the frame. The values below were worked by
hand with the thin-lens relation u = f * (1 + H / h), where u is the distance to the subject, f the focal length, H the
subject's real height and h the height of its image on the sensor (h = sensor height * subject height in pixels / image height in
pixels). Prints one line per problem and exits 1 if there is any.
"""
import inspect
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

problems = []


def check(ok, message):
    if not ok:
        problems.append(message)


try:
    from open_optics import framing
except Exception as exc:
    print(f"cannot import open_optics.framing: {exc}")
    sys.exit(1)

for name in ("sensor_height_mm", "subject_distance_m", "subject_height_px"):
    check(callable(getattr(framing, name, None)), f"open_optics.framing.{name} does not exist")
if problems:
    for p in problems:
        print(p)
    sys.exit(1)


def close(got, want, tol=1e-6):
    return abs(got - want) <= tol * max(1.0, abs(want))


# sensor height from the width and the image shape: 36 mm wide, 1280 x 704 pixels -> 19.8 mm
check(close(framing.sensor_height_mm(36.0, 1280, 704), 19.8), f"sensor_height_mm(36, 1280, 704) should be 19.8; got {framing.sensor_height_mm(36.0, 1280, 704)}")

# distance from the framing: (focal_mm, sensor_height_mm, subject_height_px, image_height_px[, real_height_m]) -> metres
CASES = [
    ((50.0, 24.0, 600.0, 1200.0), 7.133333333, "50 mm, a 1.7 m person filling half the frame height of a 24 mm sensor: h = 12 mm, u = 50 * (1 + 1700/12) = 7133.33 mm"),
    ((50.0, 19.8, 422.4, 704.0), 7.204882155, "50 mm on the 19.8 mm sensor height of a 1280 x 704 frame, the person 422.4 px (60 %) tall: h = 11.88 mm, u = 7204.88 mm"),
    ((24.0, 19.8, 422.4, 704.0), 3.458343434, "the same framing with a 24 mm lens: u = 24 * (1 + 1700/11.88) = 3458.34 mm"),
    ((50.0, 24.0, 1200.0, 1200.0), 3.591666667, "the person fills the whole frame height: h = 24 mm, u = 50 * (1 + 1700/24) = 3591.67 mm"),
    ((85.0, 24.0, 600.0, 1200.0, 0.3), 2.21, "an object 0.3 m tall filling half the height: h = 12 mm, u = 85 * (1 + 300/12) = 2210 mm"),
    ((50.0, 19.8, 422.4, 704.0, 1.65), 6.994444444, "a 1.65 m person in the 60 % framing: u = 50 * (1 + 1650/11.88) = 6994.44 mm"),
    ((50.0, 24.0, 300.0, 1200.0), 14.216666667, "a quarter of the frame height: h = 6 mm, u = 50 * (1 + 1700/6) = 14216.67 mm"),
    ((100.0, 24.0, 300.0, 1200.0), 28.433333333, "the same framing with a 100 mm lens is exactly twice as far: 28433.33 mm"),
]
for args, want, why in CASES:
    try:
        got = framing.subject_distance_m(*args)
    except Exception as exc:
        problems.append(f"subject_distance_m{args} raised {type(exc).__name__}: {exc} (expected {want}: {why})")
        continue
    check(close(got, want), f"subject_distance_m{args} = {got:.9f} m, expected {want} m ({why})")
try:
    check(close(framing.subject_distance_m(focal_mm=50.0, sensor_height_mm=24.0, subject_height_px=600.0, image_height_px=1200.0), 7.133333333), "keyword arguments focal_mm, sensor_height_mm, subject_height_px, image_height_px must work")
    check(close(framing.subject_distance_m(50.0, 24.0, 600.0, 1200.0, real_height_m=1.7), framing.subject_distance_m(50.0, 24.0, 600.0, 1200.0)), "the default real_height_m must be 1.7")
except TypeError as exc:
    problems.append(f"subject_distance_m has the wrong parameters: {exc}")

# the inverse: height in pixels from the distance. h = f * H / (u - f)
try:
    got = framing.subject_height_px(35.0, 24.0, 704.0, 5.0)
    check(close(got, 351.527358), f"subject_height_px(35, 24, 704, 5.0) = {got:.6f} px, expected 351.527358 (h = 35 * 1700 / (5000 - 35) = 11.98389 mm, times 704 / 24)")
    got = framing.subject_height_px(50.0, 19.8, 704.0, 7.204882155)
    check(close(got, 422.4, 1e-6), f"subject_height_px(50, 19.8, 704, 7.204882155) = {got:.6f} px, expected 422.4 (the first case run backwards)")
    got = framing.subject_height_px(85.0, 24.0, 1200.0, 2.21, 0.3)
    check(close(got, 600.0, 1e-6), f"subject_height_px(85, 24, 1200, 2.21, 0.3) = {got:.6f} px, expected 600")
except Exception as exc:
    problems.append(f"subject_height_px failed: {type(exc).__name__}: {exc}")
for f, sh, hp, ih, hr in ((50.0, 24.0, 333.0, 1080.0, 1.7), (24.0, 13.0, 90.0, 720.0, 1.2), (135.0, 24.0, 1000.0, 1080.0, 1.8)):
    try:
        d = framing.subject_distance_m(f, sh, hp, ih, hr)
        back = framing.subject_height_px(f, sh, ih, d, hr)
        check(close(back, hp, 1e-9), f"round trip failed for {(f, sh, hp, ih, hr)}: {back} px")
    except Exception as exc:
        problems.append(f"round trip for {(f, sh, hp, ih, hr)} raised {type(exc).__name__}: {exc}")


def raises(fn, *args):
    try:
        fn(*args)
    except ValueError:
        return True
    except Exception:
        return False
    return False


bad_values = (0.0, -1.0, math.nan, math.inf)
for position, label in enumerate(("focal_mm", "sensor_height_mm", "subject_height_px", "image_height_px", "real_height_m")):
    for bad in bad_values:
        args = [50.0, 24.0, 600.0, 1200.0, 1.7]
        args[position] = bad
        check(raises(framing.subject_distance_m, *args), f"subject_distance_m with {label}={bad} must raise ValueError")
check(raises(framing.subject_distance_m, 50.0, 24.0, "600", 1200.0), "a string for subject_height_px must raise ValueError")
check(raises(framing.subject_distance_m, 50.0, 24.0, True, 1200.0), "a bool for subject_height_px must raise ValueError")
check(raises(framing.subject_height_px, 50.0, 24.0, 1200.0, 0.05), "a distance of 0.05 m with a 50 mm lens (not beyond the focal length) must raise ValueError")
check(raises(framing.subject_height_px, 50.0, 24.0, 1200.0, 0.0), "a distance of 0 must raise ValueError")
check(raises(framing.sensor_height_mm, 36.0, 0, 704), "sensor_height_mm with a zero image width must raise ValueError")

for name in ("sensor_height_mm", "subject_distance_m", "subject_height_px"):
    doc = (inspect.getdoc(getattr(framing, name)) or "").lower()
    check("millimetre" in doc and ("metre" in doc) and "pixel" in doc or name == "sensor_height_mm" and "millimetre" in doc, f"the docstring of {name} must state its units (millimetres, metres, pixels)")
    check("thin" in doc or name == "sensor_height_mm", f"the docstring of {name} must say that it uses the thin-lens relation")

for p in problems:
    print(p)
print("framing distance: OK" if not problems else f"framing distance: {len(problems)} problem(s)")
sys.exit(1 if problems else 0)
