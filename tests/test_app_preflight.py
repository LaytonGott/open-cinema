import unittest

from app.preflight import graph_class_types, nodes_missing_message


class PreflightPureTests(unittest.TestCase):
    def test_graph_class_types_sorted_distinct(self):
        a = {"1": {"class_type": "LoadVideo", "inputs": {}}, "2": {"class_type": "DA3Inference", "inputs": {}}}
        b = {"1": {"class_type": "LoadVideo", "inputs": {}}, "5": {"class_type": "SaveVideo", "inputs": {}}}
        self.assertEqual(graph_class_types(a, b), ["DA3Inference", "LoadVideo", "SaveVideo"])

    def test_nodes_missing_message(self):
        self.assertEqual(
            nodes_missing_message(["LoadDA3Model", "DA3Inference"]),
            "ComfyUI is missing these nodes: DA3Inference, LoadDA3Model. "
            "Install the custom node pack that provides them and restart ComfyUI.")


if __name__ == "__main__":
    unittest.main()
