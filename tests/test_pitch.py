"""Phase 9 M3 data: the measured pitch of SquadComposition-Large reproduces the boxes the inspector captured; other compositions are flagged estimates."""
import unittest

from skin_editor.render import pitch

# world bounds measured by capture-0.3.0, Squad > Overview, 2026-11-14 (width, height) of the fixed-size cells
MEASURED = {"Atmosphere": (4, 2, 311.5, 147.5), "Tactics": (4, 4, 311.5, 311.5), "Training": (4, 4, 311.5, 311.5)}


class Pitch(unittest.TestCase):
    def test_measured_pitch_reproduces_the_captured_fixed_cells(self):
        p = pitch.lookup("SquadComposition-Large")
        self.assertTrue(p["measured"])
        for name, (w, h, mw, mh) in MEASURED.items():
            self.assertAlmostEqual(pitch.extent(w, p), mw, delta=0.05, msg=name)
            self.assertAlmostEqual(pitch.extent(h, p), mh, delta=0.05, msg=name)

    def test_stacked_cells_start_a_stride_apart(self):
        p = pitch.lookup("SquadComposition-Large")
        self.assertAlmostEqual(4 * pitch.stride(p), 328.0, delta=0.2)           # Tactics y 97.7 -> Training y 425.8 = 328.1 measured

    def test_an_unmeasured_composition_is_a_flagged_estimate_never_silent(self):
        p = pitch.lookup("TacticalPlannerTeamInstructionsTabComposition-Standard")
        self.assertFalse(p["measured"])
        self.assertIn("ESTIMATE", p["flag"])
        self.assertIn("TacticalPlannerTeamInstructionsTabComposition-Standard", p["flag"])


if __name__ == "__main__":
    unittest.main()

