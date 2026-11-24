"""The AddCell placement writer on archived stock set C: one added cell, nothing else changed.

Read only on the archive (source); output goes to a temporary folder."""
import json
import os
import tempfile
import unittest
from pathlib import Path

from skin_editor import tiles

ARCHIVE = Path(os.environ.get("UIDOC_ARCHIVE", r"__absent_fixture_path__"))
SETC = Path(os.environ.get("UIDOC_C_AA") or (next(iter(sorted(ARCHIVE.glob("set-C-*"))), Path("missing")) / "StandaloneWindows64"))
TILES = SETC / "ui-tileslayouts_assets_all.bundle"
COMP_PATH_ID = "4181126630784745451"
HAPPINESS = {"path_id": "8895524265953504165", "config_index": 2}


@unittest.skipUnless(TILES.is_file(), "needs archived set C")
class AddCellWriter(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="fm27se-add-", ignore_cleanup_errors=True)
        self.addCleanup(self.tmp.cleanup)
        self.out = Path(self.tmp.name)

    def op(self, **over):
        op = {"op": "add-cell", "bundle": "ui-tileslayouts_assets_all.bundle", "path_id": COMP_PATH_ID,
              "composition": "SquadComposition-Large", "cell_index": 5, "cell_id": "Happiness",
              "geometry": {"x": 16, "y": 12, "w": 4, "h": 4}, "description": dict(HAPPINESS)}
        op.update(over)
        return op

    def test_one_cell_is_added_with_its_configuration_and_a_placement_binding_and_nothing_else_changes(self):
        op = self.op()
        changed, notes, done = tiles.apply_ops(TILES, self.out, [op])
        self.assertTrue(changed)
        self.assertEqual(done, [int(COMP_PATH_ID)])
        built = self.out / TILES.name
        self.assertEqual(tiles.check_ops(TILES, built, [op]), [])
        import UnityPy
        v = {o.path_id: o for o in UnityPy.load(str(TILES)).objects}[int(COMP_PATH_ID)].read_typetree()
        b = {o.path_id: o for o in UnityPy.load(str(built)).objects}[int(COMP_PATH_ID)].read_typetree()
        self.assertEqual(len(b["m_gridComponents"]), len(v["m_gridComponents"]) + 1)
        self.assertEqual(b["m_gridComponents"][:len(v["m_gridComponents"])], v["m_gridComponents"])
        cell = b["m_gridComponents"][-1]
        self.assertEqual(cell["m_elementID"], "Happiness")
        self.assertEqual(cell["m_location"], {"x": 16, "y": 12, "width": 4, "height": 4})
        self.assertEqual(cell["m_maxSize"], {"x": 4, "y": 4})
        self.assertEqual(cell["m_gridElementConfigs"][0]["Size"], {"x": 4, "y": 4})
        self.assertEqual(cell["m_gridElementConfigs"][0]["AssetRef"]["m_AssetGUID"], "ee9c1eef7befdb74d818d840506962b4")
        self.assertEqual(b["m_placementBindings"][-1]["m_elementID"], "Happiness")
        self.assertEqual(b["m_gridElementSet"], v["m_gridElementSet"])      # the description is already in the set
        self.assertEqual(len(b["m_optionalSlices"]["m_bottom"]), len(v["m_optionalSlices"]["m_bottom"]))

    def test_a_taken_element_id_is_refused(self):
        with self.assertRaises(ValueError) as e:
            tiles.apply_ops(TILES, self.out, [self.op(cell_id="Atmosphere")])
        self.assertIn("already used", str(e.exception))
        with self.assertRaises(ValueError) as e:
            tiles.apply_ops(TILES, self.out, [self.op(cell_id="Loans")])      # an optional-slice id
        self.assertIn("already used", str(e.exception))

    def test_the_geometry_must_be_the_configurations_own_size(self):
        with self.assertRaises(ValueError) as e:
            tiles.apply_ops(TILES, self.out, [self.op(geometry={"x": 16, "y": 12, "w": 4, "h": 2})])
        self.assertIn("configuration's own size", str(e.exception))

    def test_a_new_cell_goes_at_the_end_of_the_grid(self):
        with self.assertRaises(ValueError) as e:
            tiles.apply_ops(TILES, self.out, [self.op(cell_index=3)])
        self.assertIn("goes at index", str(e.exception))


    def test_reorder_reassigns_cumulative_offsets_for_mixed_heights(self):
        t = {"m_gridComponents": [], "m_optionalSlices": {
            "m_instantiationOrder": [0, 1],
            "m_bottom": [
                {"m_elementID": "Short", "m_location": {"x": 16, "y": 0, "width": 4, "height": 2}},
                {"m_elementID": "Tall", "m_location": {"x": 16, "y": 2, "width": 4, "height": 4}},
            ]}}
        tiles._apply_slot_op(t, {"op": "slot-reorder", "composition": "C", "direction": "m_bottom",
                                 "cell_id": "Tall", "order": ["Tall", "Short"]}, {})
        bottom = t["m_optionalSlices"]["m_bottom"]
        self.assertEqual([(e["m_elementID"], e["m_location"]["y"]) for e in bottom],
                         [("Tall", 0), ("Short", 4)])       # 4-row slot first, then the 2-row slot

    def test_reorder_rewrites_each_slices_location_y(self):
        t = {"m_gridComponents": [], "m_optionalSlices": {
            "m_instantiationOrder": [0, 1],
            "m_bottom": [
                {"m_elementID": "A", "m_location": {"x": 16, "y": 0, "width": 4, "height": 2}},
                {"m_elementID": "B", "m_location": {"x": 16, "y": 8, "width": 4, "height": 2}},
            ]}}
        tiles._apply_slot_op(t, {"op": "slot-reorder", "composition": "C", "direction": "m_bottom",
                                 "cell_id": "B", "order": ["A", "B"]}, {})
        self.assertEqual([e["m_location"]["y"] for e in t["m_optionalSlices"]["m_bottom"]], [0, 2])

    def test_launch_2_bundle_leaf_diff_is_only_the_swapped_slices(self):
        import hashlib
        import UnityPy
        built = Path(r"__absent_fixture_path__"
                     r"\20261120T161249Z\ui-tileslayouts_assets_all.bundle")
        h = hashlib.sha256(built.read_bytes()).hexdigest()
        self.assertEqual(h, "90cb8e4c0e30de4d603488ea04699d3c523afb0919cadca029bd0ccbfba63592")
        vt = {o.path_id: o for o in UnityPy.load(str(TILES)).objects}[4181126630784745451].read_typetree()
        bt = {o.path_id: o for o in UnityPy.load(str(built)).objects}[4181126630784745451].read_typetree()
        diffs = set(tiles._leaf_diffs(vt, bt))
        expected = {"/m_optionalSlices/m_bottom[%d]/%s" % (i, field)
                    for i in (0, 1)
                    for field in ("m_elementID", "m_configDescriptions[0]/m_PathID",
                                  "m_horizontalAlignment", "m_verticalAlignment")}
        self.assertEqual(diffs, expected)                     # both slots are 2 rows, so their y offsets stay 0/2


if __name__ == "__main__":
    unittest.main()
