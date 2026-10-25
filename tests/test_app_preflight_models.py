import unittest

from app.preflight import find_missing_choices, models_missing_message


def info(definition, group="required", name="unet_name"):
    return {"input": {group: {name: definition}}}


class FindMissingChoicesTest(unittest.TestCase):
    def test_new_combo_form(self):
        graph = {"1": {"class_type": "UnetLoaderGGUF", "inputs": {"unet_name": "x.gguf"}}}
        oi = {"UnetLoaderGGUF": info(["COMBO", {"options": ["a.gguf"]}])}
        self.assertEqual(find_missing_choices(graph, oi), [("unet_name", "x.gguf", "UnetLoaderGGUF")])
        graph["1"]["inputs"]["unet_name"] = "a.gguf"
        self.assertEqual(find_missing_choices(graph, oi), [])

    def test_old_list_form(self):
        graph = {"1": {"class_type": "Loader", "inputs": {"unet_name": "x"}}}
        oi = {"Loader": info([["a", "b"]], group="optional")}
        self.assertEqual(find_missing_choices(graph, oi), [("unet_name", "x", "Loader")])

    def test_empty_options_skipped(self):
        graph = {"1": {"class_type": "Loader", "inputs": {"unet_name": "x"}}}
        oi = {"Loader": info(["COMBO", {"options": []}])}
        self.assertEqual(find_missing_choices(graph, oi), [])

    def test_load_video_file_skipped(self):
        graph = {"1": {"class_type": "LoadVideo", "inputs": {"file": "clip.mp4"}}}
        oi = {"LoadVideo": info(["COMBO", {"options": ["other.mp4"]}], name="file")}
        self.assertEqual(find_missing_choices(graph, oi), [])

    def test_save_video_skipped(self):
        graph = {"1": {"class_type": "SaveVideo", "inputs": {"codec": "h264"}}}
        oi = {"SaveVideo": info(["COMBO", {"options": ["auto"]}], name="codec")}
        self.assertEqual(find_missing_choices(graph, oi), [])

    def test_links_ignored_and_result_sorted_unique(self):
        graph = {
            "1": {"class_type": "Loader", "inputs": {"unet_name": ["2", 0]}},
            "2": {"class_type": "Loader", "inputs": {"unet_name": "z"}},
            "3": {"class_type": "Loader", "inputs": {"unet_name": "z"}},
        }
        oi = {"Loader": info(["COMBO", {"options": ["a"]}])}
        self.assertEqual(find_missing_choices(graph, oi), [("unet_name", "z", "Loader")])


class ModelsMissingMessageTest(unittest.TestCase):
    def test_exact_text(self):
        items = [("unet_name", "x", "UnetLoaderGGUF"), ("vae_name", "y", "VAELoader")]
        self.assertEqual(
            models_missing_message(items),
            "ComfyUI does not list these files: unet_name 'x' (UnetLoaderGGUF), "
            "vae_name 'y' (VAELoader). Put them in ComfyUI's models folders "
            "(see the README) and restart ComfyUI.")


if __name__ == "__main__":
    unittest.main()
