"""Tests for app.shot: the option lists and the subject height table."""

import unittest

from app import shot


class OptionListTests(unittest.TestCase):
    def test_cameras(self):
        self.assertEqual(shot.CAMERAS, [
            {"id": "static", "label": "Static"},
            {"id": "dolly-in", "label": "Dolly in"},
            {"id": "dolly-out", "label": "Dolly out"},
            {"id": "pan-left", "label": "Pan left"},
            {"id": "pan-right", "label": "Pan right"},
            {"id": "tilt-up", "label": "Tilt up"},
            {"id": "orbit", "label": "Orbit"},
            {"id": "handheld", "label": "Handheld"},
        ])

    def test_framings(self):
        self.assertEqual(shot.FRAMINGS, [
            {"id": "close-up", "label": "Close-up"},
            {"id": "waist-up", "label": "Waist-up"},
            {"id": "full-body", "label": "Full body"},
            {"id": "wide", "label": "Wide"},
        ])

    def test_lenses(self):
        self.assertEqual(shot.LENSES, [24, 35, 50, 85])

    def test_apertures(self):
        self.assertEqual(shot.APERTURES, [1.4, 2, 2.8, 4, 5.6, 8, 11, 16])

    def test_subject_height_fraction(self):
        self.assertEqual(
            shot.SUBJECT_HEIGHT_FRACTION,
            {"close-up": 2.8, "waist-up": 1.6, "full-body": 0.85, "wide": 0.35},
        )


class SubjectDistanceTests(unittest.TestCase):
    def test_table(self):
        # Hand-checked table from docs/app-spec.md section 2.1, in metres.
        framings = ["close-up", "waist-up", "full-body", "wide"]
        table = {
            24: [0.7599, 1.3119, 2.4482, 5.9114],
            35: [1.1082, 1.9132, 3.5704, 8.6209],
            50: [1.5832, 2.7331, 5.1005, 12.3155],
            85: [2.6914, 4.6462, 8.6709, 20.9364],
        }
        for lens, expected in table.items():
            for framing, value in zip(framings, expected):
                with self.subTest(lens=lens, framing=framing):
                    self.assertAlmostEqual(
                        shot.subject_distance(lens, framing), value, delta=0.00006)


class SubjectDistanceRejectTests(unittest.TestCase):
    def test_bad_lens_or_framing(self):
        for lens, framing in [(28, "wide"), (50, "head"), ("50", "wide"), (True, "wide")]:
            with self.subTest(lens=lens, framing=framing):
                with self.assertRaises(ValueError) as ctx:
                    shot.subject_distance(lens, framing)
                self.assertTrue(str(ctx.exception))


class ValidateValidTests(unittest.TestCase):
    def make(self, **changes):
        data = {"description": "A woman walks.", "camera": "static", "lens_mm": 50,
                "aperture": 2.8, "framing": "waist-up"}
        data.update(changes)
        return data

    def test_description_stripped(self):
        result = shot.validate_shot(self.make(description="  A woman walks.  "))
        self.assertEqual(result["description"], "A woman walks.")
        self.assertEqual(result["camera"], "static")
        self.assertEqual(result["lens_mm"], 50)
        self.assertEqual(result["aperture"], 2.8)
        self.assertEqual(result["framing"], "waist-up")

    def test_aperture_int_and_float(self):
        for aperture in (2, 2.0):
            with self.subTest(aperture=aperture):
                result = shot.validate_shot(self.make(aperture=aperture))
                self.assertEqual(result["aperture"], 2)

    def test_every_option_accepted(self):
        for lens in [24, 35, 50, 85]:
            with self.subTest(lens=lens):
                self.assertEqual(shot.validate_shot(self.make(lens_mm=lens))["lens_mm"], lens)
        cameras = ["static", "dolly-in", "dolly-out", "pan-left", "pan-right",
                   "tilt-up", "orbit", "handheld"]
        for camera in cameras:
            with self.subTest(camera=camera):
                self.assertEqual(shot.validate_shot(self.make(camera=camera))["camera"], camera)
        for framing in ["close-up", "waist-up", "full-body", "wide"]:
            with self.subTest(framing=framing):
                self.assertEqual(shot.validate_shot(self.make(framing=framing))["framing"], framing)
        for aperture in [1.4, 2, 2.8, 4, 5.6, 8, 11, 16]:
            with self.subTest(aperture=aperture):
                self.assertEqual(shot.validate_shot(self.make(aperture=aperture))["aperture"], aperture)


class ValidateMissingTests(unittest.TestCase):
    def test_each_required_field_missing(self):
        for name in ["description", "camera", "lens_mm", "aperture", "framing"]:
            with self.subTest(field=name):
                data = {"description": "A woman walks.", "camera": "static", "lens_mm": 50,
                        "aperture": 2.8, "framing": "waist-up"}
                del data[name]
                with self.assertRaises(shot.ShotError) as ctx:
                    shot.validate_shot(data)
                self.assertEqual(ctx.exception.field, name)
                self.assertGreater(len(ctx.exception.message), 12)


class ValidateDescriptionTests(unittest.TestCase):
    def make(self, **changes):
        data = {"description": "A woman walks.", "camera": "static", "lens_mm": 50,
                "aperture": 2.8, "framing": "waist-up"}
        data.update(changes)
        return data

    def test_bad_descriptions(self):
        for value in ["ab", "   ", "a" * 1001, 5, None, " " * 1000 + "ab"]:
            with self.subTest(description=value if not isinstance(value, str) else len(value)):
                with self.assertRaises(shot.ShotError) as ctx:
                    shot.validate_shot(self.make(description=value))
                self.assertEqual(ctx.exception.field, "description")
                self.assertGreater(len(ctx.exception.message), 12)

    def test_description_limits(self):
        for value in ["abc", "a" * 1000]:
            with self.subTest(length=len(value)):
                self.assertEqual(shot.validate_shot(self.make(description=value))["description"], value)
        self.assertEqual(shot.validate_shot(self.make(description=" abc "))["description"], "abc")


class ValidateChoiceTests(unittest.TestCase):
    BAD = [("camera", "zoom"), ("camera", None),
           ("lens_mm", 28), ("lens_mm", "50"), ("lens_mm", True), ("lens_mm", None), ("lens_mm", 50.5),
           ("aperture", 3), ("aperture", 0), ("aperture", "f/2.8"), ("aperture", True), ("aperture", None),
           ("framing", "head"), ("framing", None), ("framing", 5)]

    def test_bad_choices(self):
        for field, value in self.BAD:
            with self.subTest(field=field, value=value):
                data = {"description": "A woman walks.", "camera": "static", "lens_mm": 50,
                        "aperture": 2.8, "framing": "waist-up"}
                data[field] = value
                with self.assertRaises(shot.ShotError) as ctx:
                    shot.validate_shot(data)
                self.assertEqual(ctx.exception.field, field)
                self.assertGreater(len(ctx.exception.message), 12)


class ValidateSeedTests(unittest.TestCase):
    def make(self, **changes):
        data = {"description": "A woman walks.", "camera": "static", "lens_mm": 50,
                "aperture": 2.8, "framing": "waist-up"}
        data.update(changes)
        return data

    def test_seed_kept(self):
        for seed in (5, 0, 2147483647):
            with self.subTest(seed=seed):
                self.assertEqual(shot.validate_shot(self.make(seed=seed))["seed"], seed)

    def test_seed_default(self):
        seed = shot.validate_shot(self.make())["seed"]
        self.assertIs(type(seed), int)
        self.assertGreaterEqual(seed, 0)
        self.assertLessEqual(seed, 2147483647)

    def test_bad_seeds(self):
        for seed in (-1, 2147483648, 1.5, "7", True, None):
            with self.subTest(seed=seed):
                with self.assertRaises(shot.ShotError) as ctx:
                    shot.validate_shot(self.make(seed=seed))
                self.assertEqual(ctx.exception.field, "seed")
                self.assertGreater(len(ctx.exception.message), 12)


class ShotErrorMessageTests(unittest.TestCase):
    REQUIRED = ["description", "camera", "lens_mm", "aperture", "framing"]

    def base(self):
        return {"description": "A woman walks.", "camera": "static", "lens_mm": 50,
                "aperture": 2.8, "framing": "waist-up"}

    def cases(self):
        bad = [("description", "ab"), ("description", "a" * 1001), ("description", 5),
               ("camera", "zoom"), ("lens_mm", 28), ("aperture", 3),
               ("framing", "head"), ("seed", -1)]
        for field, value in bad:
            data = self.base()
            data[field] = value
            yield field, data
        for name in self.REQUIRED:
            data = self.base()
            del data[name]
            yield name, data

    def test_errors_are_readable(self):
        for field, data in self.cases():
            with self.subTest(field=field, data=data.get(field)):
                with self.assertRaises(shot.ShotError) as ctx:
                    shot.validate_shot(data)
                err = ctx.exception
                self.assertIsInstance(err, shot.ShotError)
                self.assertIsInstance(err.field, str)
                self.assertTrue(err.field)
                self.assertEqual(err.field, field)
                self.assertIsInstance(err.message, str)
                self.assertGreater(len(err.message), 12)
                self.assertTrue(err.message.endswith("."))
                self.assertEqual(str(err), err.message)


class BuildPromptTests(unittest.TestCase):
    FRAMING = {
        "close-up": "Close-up shot of the subject's face and shoulders",
        "waist-up": "Waist-up medium shot",
        "full-body": "Full-body shot, the whole figure visible head to toe",
        "wide": "Wide establishing shot, the figure small in a large scene",
    }
    CAMERA = {
        "static": "The camera is locked off and does not move",
        "dolly-in": "Slow dolly-in toward the subject",
        "dolly-out": "Slow dolly-out away from the subject",
        "pan-left": "Smooth pan to the left",
        "pan-right": "Smooth pan to the right",
        "tilt-up": "Slow tilt up",
        "orbit": "The camera orbits slowly around the subject",
        "handheld": "Handheld camera with subtle natural movement",
    }
    TAIL = ("85 mm lens look, deep focus with everything sharp from the foreground "
            "to the far background, cinematic lighting, 35mm film.")

    def params(self, camera, framing, description):
        return {"description": description, "camera": camera, "lens_mm": 85,
                "aperture": 2.8, "framing": framing}

    def test_all_32_pairs(self):
        count = 0
        for cam in shot.CAMERAS:
            for fr in shot.FRAMINGS:
                expected = (f"{self.FRAMING[fr['id']]}. A man waits at a bus stop. "
                            f"{self.CAMERA[cam['id']]}. {self.TAIL}")
                got = shot.build_prompt(
                    self.params(cam["id"], fr["id"], "A man waits at a bus stop"))
                self.assertEqual(got, expected)
                count += 1
        self.assertEqual(count, 32)

    def test_example_string(self):
        self.assertEqual(
            shot.build_prompt(self.params("static", "waist-up", "A man waits at a bus stop")),
            "Waist-up medium shot. A man waits at a bus stop. The camera is locked off "
            "and does not move. 85 mm lens look, deep focus with everything sharp from "
            "the foreground to the far background, cinematic lighting, 35mm film.")

    def test_no_extra_period(self):
        for end in (".", "!", "?"):
            with self.subTest(end=end):
                got = shot.build_prompt(self.params("orbit", "wide", "A man waits" + end))
                self.assertIn("A man waits" + end + " The camera orbits", got)

    def test_spaces_trimmed(self):
        got = shot.build_prompt(self.params("tilt-up", "close-up", "   A man waits  "))
        self.assertIn("shoulders. A man waits. Slow tilt up.", got)


class PromptEndingTests(unittest.TestCase):
    def prompt(self, description):
        return shot.build_prompt({"description": description, "camera": "static",
                                  "lens_mm": 85, "aperture": 2.8, "framing": "wide"})

    def test_full_stop_added(self):
        self.assertIn("A man waits at a bus stop. The camera",
                      self.prompt("A man waits at a bus stop"))

    def test_question_unchanged(self):
        got = self.prompt("Is it raining?")
        self.assertIn("Is it raining? The camera", got)
        self.assertNotIn("?.", got)

    def test_exclamation_unchanged(self):
        got = self.prompt("He runs!")
        self.assertIn("He runs! The camera", got)
        self.assertNotIn("!.", got)

    def test_full_stop_unchanged(self):
        got = self.prompt("Quiet harbour.")
        self.assertIn("Quiet harbour. The camera", got)
        self.assertNotIn("..", got)

    def test_padded_description(self):
        got = self.prompt("   Quiet harbour.   ")
        self.assertIn("Quiet harbour. The camera", got)
        self.assertNotIn("  ", got)


if __name__ == "__main__":
    unittest.main()
