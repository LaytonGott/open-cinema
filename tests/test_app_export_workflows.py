"""Tests for app.export_workflows: the example prompt and the exported JSON bytes."""

import json
import tempfile
import unittest
from pathlib import Path

from app import export_workflows, graphs


class ExportWorkflowsTest(unittest.TestCase):
    def test_example_prompt_literal(self):
        expected = (
            "Waist-up medium shot. "
            "A saxophone player on a rain-wet night street, neon reflections in the puddles. "
            "Slow dolly-in toward the subject. 50 mm lens look, "
            "deep focus with everything sharp from the foreground to the far background, "
            "cinematic lighting, 35mm film."
        )
        self.assertEqual(export_workflows.EXAMPLE_PROMPT, expected)

    def _expected_bytes(self, graph):
        return (json.dumps(graph, indent=2) + "\n").encode("utf-8")

    def test_export_names_and_bytes(self):
        generate = graphs.build_generation_graph(
            export_workflows.EXAMPLE_PROMPT, 42, "opencinema/example/before"
        )
        optics = graphs.build_optics_graph(
            "example.mp4", 50, 2.8, 5.1005, "opencinema/example/after"
        )
        with tempfile.TemporaryDirectory() as tmp:
            paths = export_workflows.export(tmp)
            self.assertEqual(len(paths), 2)
            self.assertEqual(
                [Path(p).name for p in paths],
                ["open_cinema_generate.json", "open_cinema_optics.json"],
            )
            data = [Path(p).read_bytes() for p in paths]
        self.assertEqual(data[0], self._expected_bytes(generate))
        self.assertEqual(data[1], self._expected_bytes(optics))

    def test_no_carriage_returns(self):
        with tempfile.TemporaryDirectory() as tmp:
            for path in export_workflows.export(tmp):
                self.assertNotIn(b"\r", Path(path).read_bytes())

    def test_export_to_new_nested_folder(self):
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp) / "a" / "b" / "workflows"
            self.assertFalse(dest.exists())
            paths = export_workflows.export(dest)
            self.assertEqual(len(paths), 2)
            for path in paths:
                self.assertTrue(Path(path).is_file())
                self.assertEqual(Path(path).parent, dest)


if __name__ == "__main__":
    unittest.main()
