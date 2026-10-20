"""Public functions in app/shot.py and app/graphs.py document their units and results."""
import inspect
import unittest

from app import graphs, shot


class PublicDocstringTest(unittest.TestCase):
    def doc(self, func):
        doc = inspect.getdoc(func)
        self.assertTrue(doc, f"{func.__name__} has no docstring")
        return doc

    def test_docstrings_state_results(self):
        for func in (shot.subject_distance, shot.validate_shot, shot.build_prompt,
                     graphs.build_generation_graph, graphs.build_optics_graph):
            with self.subTest(func=func.__name__):
                self.assertIn("return", self.doc(func).lower())

    def test_subject_distance_units(self):
        doc = self.doc(shot.subject_distance)
        self.assertIn("metres", doc)
        self.assertIn("millimetres", doc)

    def test_validate_shot_units(self):
        self.assertIn("millimetres", self.doc(shot.validate_shot))

    def test_build_optics_graph_units(self):
        doc = self.doc(graphs.build_optics_graph)
        self.assertIn("millimetres", doc)
        self.assertIn("metres", doc)


if __name__ == "__main__":
    unittest.main()
