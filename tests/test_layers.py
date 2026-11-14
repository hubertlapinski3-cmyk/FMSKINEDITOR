"""The optional layers (skin_editor/render/layers.py): positions are stamped before the cascade, the class layer adds only missing classes, nothing else changes."""
import unittest

from skin_editor.render import layers


class Layers(unittest.TestCase):
    def test_apply_class_layer_adds_only_missing_classes_by_stamped_position(self):
        top = [{"classes": ["a"], "children": [{"classes": [], "children": []}, {"classes": ["x"], "children": [{"classes": [], "children": []}]}]}]
        layers.stamp_positions(top)
        self.assertEqual([top[0]["_pos"], top[0]["children"][1]["_pos"], top[0]["children"][1]["children"][0]["_pos"]], ["0", "0/1", "0/1/0"])
        n = layers.apply_class_layer(top, {"0/1": ["x", "sprite"], "0/1/0": ["y"], "9/9": ["z"]})
        self.assertEqual(n, 2)
        self.assertEqual(top[0]["children"][1]["classes"], ["x", "sprite"])
        self.assertEqual(top[0]["children"][1]["children"][0]["classes"], ["y"])
        self.assertEqual(top[0]["classes"], ["a"])

    def test_paths_of_reads_the_stamps_of_a_rendered_tree(self):
        top = [{"children": [{"children": []}]}]
        layers.stamp_positions(top)
        pos = layers.paths_of(top)
        self.assertEqual(sorted(pos.values()), ["0", "0/0"])


if __name__ == "__main__":
    unittest.main()
