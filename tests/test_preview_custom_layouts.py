"""CL3 part C: rule V5+C2 wired into the preview for every composition (C1) and the preview reading the game's custom-layout files (C2)."""
import copy
import json
import unittest
from pathlib import Path

from skin_editor import custom_layouts as cl
from skin_editor.render import one_rule, preview, screen

DUMP = Path(r"__absent_fixture_path__")
COPIES = Path(r"__absent_fixture_path__")
PROFILE = "PlayerReportOverviewComposition-Large"
ORDER = ["TacticalEffectiveness", "FItness", "PlayerForm", "PlayerTrainingOverview", "PlayerSeasonStats", "CareerStats"]


@unittest.skipUnless(DUMP.is_file(), "needs the archived set-C layout dump")
class WiredRule(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dump = json.loads(DUMP.read_text(encoding="utf-8-sig"))

    def test_rule_place_is_the_frozen_rule_for_any_composition(self):
        a = screen.Assembler(self.dump)
        for comp, grid, reflow in (("SquadComposition-Large", (30, 16), 1), (PROFILE, (30, 13), 0), ("PlayerReportPersonal-Large", (30, 13), 0)):
            got = preview.rule_place(a, comp, grid[0], grid[1], reflow)
            want = one_rule.place_rule(a, comp, grid, "V5", reflow, None, "equal")
            self.assertEqual(got, want, comp)

    def test_the_label_names_the_rule_and_its_evidence(self):
        self.assertEqual(preview.RULE_LABEL, "rule V5+C2: fitted on 10 screens, passed 6 out of sample including one growth test")
        self.assertEqual(preview.profile_hosts(self.dump)["label"], preview.RULE_LABEL)

    def test_apply_max_sizes_and_rule_work_on_the_squad(self):
        a = screen.Assembler(self.dump)
        base = preview.rule_place(a, "SquadComposition-Large", 30, 16, 1)
        preview.apply_max_sizes(a, "SquadComposition-Large", [{"composition": "SquadComposition-Large", "cell_element_id": "Atmosphere", "max_size": {"x": 4, "y": 6}}])
        self.assertNotEqual(preview.rule_place(a, "SquadComposition-Large", 30, 16, 1), base)


@unittest.skipUnless(DUMP.is_file() and (COPIES / PROFILE).is_file(), "needs the layout dump and the copied real file")
class CustomFile(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dump = json.loads(DUMP.read_text(encoding="utf-8-sig"))
        cls.real = cl.read(COPIES / PROFILE)

    def band(self, out):
        return {h["element_id"]: h for h in out["hosts"] if h["element_id"] != "PlayerAttributesBlock"}

    def test_the_real_custom_file_previews_as_measured_in_cl_part_b_c(self):
        out = preview.profile_hosts(self.dump, show_tactical_effectiveness=True, custom=self.real)
        self.assertEqual([self.band(out)[e]["col"] for e in ORDER], [0, 4, 8, 12, 16, 24])
        self.assertIn(preview.CUSTOM_LABEL, out["label"])

    def test_the_one_byte_edit_of_part_b_previews_as_measured(self):
        edited = copy.deepcopy(self.real)
        cl.set_max_size(edited, "FItness", 6, 4)
        out = preview.profile_hosts(self.dump, show_tactical_effectiveness=True, custom=edited)
        b = self.band(out)
        self.assertEqual([b[e]["col"] for e in ORDER], [0, 4, 10, 14, 18, 26])
        self.assertEqual(b["FItness"]["rect"][2], 82 * 6 - 16)

    def test_a_file_that_does_not_fit_the_bundle_cells_is_not_used(self):
        a = screen.Assembler(self.dump)
        bad = copy.deepcopy(self.real)
        bad["m_gridComponents"].pop()                     # fewer cells than the bundle has
        before = copy.deepcopy(a.cells[PROFILE])
        self.assertIsNone(preview.apply_custom(a, PROFILE, bad))
        self.assertEqual(a.cells[PROFILE], before)
        self.assertEqual(preview.apply_custom(a, PROFILE, self.real), {"swapped": [("Happiness", "TacticalEffectiveness")], "added": []})

    def test_added_cells_in_a_file_are_added_to_the_preview(self):
        a = screen.Assembler(self.dump)
        more = copy.deepcopy(self.real)
        extra = copy.deepcopy(more["m_gridComponents"][-1])
        extra["m_elementID"] = "Extra"
        extra["m_location"].update({"x": 20, "y": 6})
        more["m_gridComponents"].append(extra)
        self.assertEqual(preview.apply_custom(a, PROFILE, more)["added"], ["Extra"])
        self.assertEqual(len(a.cells[PROFILE]), 8)


if __name__ == "__main__":
    unittest.main()
