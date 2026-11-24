"""J1: per-panel grid, expanding profile layout and the tactical-effectiveness tile swap."""
import json
import unittest
from pathlib import Path

from skin_editor.render import preview, screen

DUMP = Path(r"__absent_fixture_path__")

MEASURED = {
    "PlayerAttributesBlock": [28.3, 286.1, 2443.4, 803.7],
    "TacticalEffectiveness": [28.3, 1105.5, 311.5, 230.5],
    "FItness": [356.4, 1105.5, 311.5, 230.5],
    "PlayerForm": [683.6, 1105.5, 312.5, 230.5],
    "PlayerTrainingOverview": [1011.7, 1105.5, 312.5, 230.5],
    "PlayerSeasonStats": [1339.8, 1105.5, 640.6, 230.5],
    "CareerStats": [1996.1, 1105.5, 311.5, 230.5],
}


@unittest.skipUnless(DUMP.is_file(), "needs the archived set-C layout dump")
class ProfilePreview(unittest.TestCase):
    def test_profile_hosts_match_h2_i2_within_1_5_px(self):
        dump = json.loads(DUMP.read_text(encoding="utf-8-sig"))
        out = preview.profile_hosts(dump)
        self.assertEqual((out["cols"], out["rows"]), (30, 13))
        got = {h["element_id"]: h["rect"] for h in out["hosts"]}
        print("host, predicted, measured, delta")
        for name, measured in MEASURED.items():
            predicted = got[name]
            delta = max(abs(a - b) for a, b in zip(predicted, measured))
            print("%s, %s, %s, %.1f" % (name, predicted, measured, delta))
            self.assertLessEqual(delta, 1.5, "%s: %s vs %s" % (name, predicted, measured))
        self.assertEqual(set(got), set(MEASURED))

    def test_tile_swap_state(self):
        dump = json.loads(DUMP.read_text(encoding="utf-8-sig"))
        on = preview.profile_hosts(dump, show_tactical_effectiveness=True)
        off = preview.profile_hosts(dump, show_tactical_effectiveness=False)
        self.assertIn("TacticalEffectiveness", {h["element_id"] for h in on["hosts"]})
        self.assertIn("Happiness", {h["element_id"] for h in off["hosts"]})

    def test_grid_rule_on_both_screens(self):
        self.assertEqual(screen.grid_dims_content(2468.8, 1319.3), (30, 16))
        self.assertEqual(screen.grid_dims_content(2468.8, 1074.2), (30, 13))

    def test_squad_keeps_the_packing_rule(self):
        dump = json.loads(DUMP.read_text(encoding="utf-8-sig"))
        a = screen.Assembler(dump)
        placed = a.place("SquadComposition-Large", 30, 16)
        self.assertIn("FirstTeamOverview", placed)
        self.assertNotIn("expanding", " ".join(placed["FirstTeamOverview"]["mode"]))
        self.assertEqual(screen.grid_dims_content(2468.8, 1319.3), (30, 16))

    def test_assembler_place_for_standard_is_unchanged_pre_j2(self):
        dump = json.loads(DUMP.read_text(encoding="utf-8-sig"))
        self.assertTrue(preview.expands("SquadComposition-Standard"))        # CL3: rule V5+C2 is wired for every composition; Assembler.place itself is unchanged
        a = screen.Assembler(dump)
        placed = a.place("SquadComposition-Standard", 18, 11)
        expected = {"Tactics": (14, 0, 4, 4), "Training": (14, 4, 4, 2), "Atmosphere": (14, 6, 4, 2),
                    "HumanActionsControlPanelBlock": (0, 0, 14, 1), "FirstTeamOverview": (0, 1, 14, 10)}
        for name, (col, row, w, h) in expected.items():
            self.assertEqual((placed[name]["col"], placed[name]["row"], placed[name]["w"], placed[name]["h"]),
                             (col, row, w, h), name)
        for info in placed.values():
            self.assertNotIn("expanding", " ".join(info["mode"]))


if __name__ == "__main__":
    unittest.main()
