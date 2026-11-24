"""UI1 step 1: generated engine parity, preview confidence labels, and the new default engine.

Static only: the generated data file is read (and rebuilt into a temporary file), never the game.
"""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from skin_editor import project
from skin_editor.render import preview

from tests.test_preview_engine import SETS, _RD, dump

ROOT = Path(__file__).resolve().parent.parent
GENERATOR = ROOT / "tools" / "build_layout_parity.py"

def _full_dump():
    """The synthetic preview dump with the min/max fields the REA engine's graph needs."""
    d = dump()
    for cell in d["cells"]:
        cell.update(min_w=cell["w"], min_h=cell["h"], max_w=cell["w"], max_h=cell["h"])
    return d


MEASURED_COMP = "SquadComposition-Large"            # in the 27 measured cases, parity agrees
MEASURED_ONLY_COMP = "InjuryHistoryCardGridComposition"   # measured, outside the 412 Large set
COMPUTED_COMP = "2_Tiles_4x4_8x4-Large"             # parity agrees, not measured
DISAGREE_COMP = "4_Tiles_2x4x4_2x4x2-Large"         # one of the 65 parity disagreements


class GeneratedData(unittest.TestCase):
    def test_the_generated_parity_file_exists_with_expected_counts(self):
        path = preview.parity_path()
        self.assertTrue(path.is_file(), "run tools/build_layout_parity.py")
        data = json.loads(path.read_text(encoding="utf-8-sig"))
        self.assertEqual(data["counts"]["compositions"], 412)
        self.assertEqual(data["counts"]["agree"], 347)
        self.assertEqual(data["counts"]["disagree"], 65)
        self.assertEqual(data["counts"]["disagree_cells"], 240)
        self.assertEqual(len(data["measured_cases"]), 27)
        self.assertEqual(len(data["compositions"]), 412)
        self.assertEqual(sum(1 for row in data["compositions"] for cell in row["deltas"]
                             if not cell["agree"]), 240)
        self.assertEqual(data["counts"]["confidence_labels"],
                         {"measured": 17, "computed": 330, "unverified": 65})
        self.assertEqual(sum(data["counts"]["confidence_labels"].values()), 412)
        self.assertEqual(data["counts"]["measured_compositions"], 18)

    @unittest.skipUnless(GENERATOR.is_file(), "needs development tools")
    def test_the_generator_rebuilds_the_checked_in_file_byte_for_byte(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "layout-parity.json"
            subprocess.run([sys.executable, str(GENERATOR), "--out", str(out)],
                           cwd=str(ROOT), check=True, capture_output=True, text=True)
            self.assertEqual(out.read_bytes(), preview.parity_path().read_bytes())


class Classifier(unittest.TestCase):
    def test_known_samples_get_the_right_label(self):
        self.assertEqual(preview.confidence_for(MEASURED_COMP)["label"], "measured")
        self.assertEqual(preview.confidence_for(MEASURED_ONLY_COMP)["label"], "measured")
        self.assertEqual(preview.confidence_for(COMPUTED_COMP)["label"], "computed")
        self.assertEqual(preview.confidence_for(DISAGREE_COMP)["label"], "unverified")
        self.assertEqual(preview.confidence_for("NoSuchComposition-Large")["label"], "unverified")

    def test_label_counts_cover_the_parity_set_and_the_measured_only_composition(self):
        self.assertEqual(preview.confidence_summary(),
                         {"measured": 17, "computed": 330, "unverified": 65,
                          "total": 412, "measured_compositions": 18})

    def test_squad_player_report_overview_portal_and_all_27_measured_cases_show_measured(self):
        """UI5 step 1: Squad, PlayerReportOverview, Portal and every composition in the 27 measured
        cases show 'measured' across all lookup forms (bare, screen suffix, .json)."""
        for name in ("SquadComposition-Large", "PlayerReportOverviewComposition-Large", "Portal-Large",
                     "Portal-Large (PortalScreen)", "SquadComposition-Large (SquadScreen)",
                     "SquadComposition-Large.json", "InjuryHistoryCardGridComposition",
                     "PlayerContractUserOwnedNoWorkPermitGridComposition-Large"):
            self.assertEqual(preview.confidence_for(name, "rea")["label"], "measured", name)
        data = json.loads(preview.parity_path().read_text(encoding="utf-8-sig"))
        self.assertEqual(len(data["measured_cases"]), 27)
        for case in data["measured_cases"]:
            comp = case["composition"]
            self.assertEqual(preview.confidence_for(comp, "rea")["label"], "measured", case)

    def test_the_wrong_engine_does_not_change_a_measured_label(self):
        for engine in ("rea", "one_rule"):
            out = preview.confidence_for(MEASURED_COMP, engine)
            self.assertEqual(out["label"], "measured")
            self.assertEqual(out["engine"], engine)
            self.assertIn("MEASURED", out["reason"])

    def test_the_tooltip_carries_the_other_engines_result_in_both_directions(self):
        rea = preview.confidence_for(DISAGREE_COMP, "rea")
        one = preview.confidence_for(DISAGREE_COMP, "one_rule")
        self.assertEqual(rea["other_engine"], "one_rule")
        self.assertEqual(one["other_engine"], "rea")
        self.assertTrue(rea["other_engine_result"]["available"])
        self.assertTrue(one["other_engine_result"]["available"])
        worst = rea["parity"]["worst_cell"]
        self.assertIn(worst, rea["other_engine_result"]["cells"])
        self.assertIn(worst, one["other_engine_result"]["cells"])
        self.assertNotEqual(rea["other_engine_result"]["cells"][worst],
                            one["other_engine_result"]["cells"][worst])
        self.assertIn(worst, rea["tooltip"])
        self.assertIn("UNVERIFIED", rea["tooltip"])

    def test_missing_data_degrades_to_unverified_instead_of_breaking(self):
        missing = Path(tempfile.gettempdir()) / "ui1-no-such-parity-file.json"
        with mock.patch.dict("os.environ", {preview.PARITY_PATH_ENV: str(missing)}):
            self.assertFalse(preview.layout_parity()["available"])
            out = preview.confidence_for(MEASURED_COMP)
        self.assertEqual(out["label"], "unverified")
        self.assertIsNone(out["source"])
        self.assertFalse(out["other_engine_result"]["available"])


class DefaultEngine(unittest.TestCase):
    def test_rea_is_the_default_and_one_rule_is_still_selectable(self):
        self.assertEqual(project.DEFAULT_LAYOUT_ENGINE, "rea")
        self.assertEqual(set(project.LAYOUT_ENGINES), {"rea", "one_rule"})
        p = project.new("engine-default", "27.1.0.2505117")
        self.assertEqual(project.layout_engine(p), "rea")
        project.set_layout_engine(p, "one_rule")
        self.assertTrue(p["options"]["layout_engine_explicit"])
        self.assertEqual(project.layout_engine(p), "one_rule")
        self.assertEqual(project.validate(project.migrate(p))["options"]["layout_engine"], "one_rule")
        project.set_layout_engine(p, "rea")
        self.assertEqual(project.layout_engine(project.validate(project.migrate(p))), "rea")
        with self.assertRaises(ValueError):
            project.set_layout_engine(p, "sideways")

    def test_the_labels_no_longer_call_one_rule_the_default(self):
        self.assertIn("27/27", preview.ENGINE_LABEL("rea"))
        self.assertNotIn("one_rule", preview.ENGINE_LABEL("rea"))
        self.assertIn("selectable", preview.ENGINE_LABEL("one_rule"))
        self.assertNotIn("(default)", preview.ENGINE_LABEL("one_rule"))


class PreviewResponse(unittest.TestCase):
    def test_confidence_is_additive_to_the_preview_and_comparison_responses(self):
        out = preview.build_preview(_full_dump(), _RD(), "SquadTileCompositionSet", 1920, 1080,
                                    "Large UI", [], "s", sets=SETS, engine="one_rule")
        for key in ("screen", "composition", "grid", "hosts", "cells", "measured", "estimated", "notice"):
            self.assertIn(key, out)
        self.assertEqual(out["composition"], MEASURED_COMP)
        self.assertEqual(out["confidence"]["label"], "measured")
        self.assertEqual(out["confidence"]["engine"], "one_rule")
        self.assertEqual(preview.build_preview(_full_dump(), _RD(), "SquadTileCompositionSet", 1920, 1080,
                                                "Large UI", [], "s", sets=SETS, engine="rea")
                         ["confidence"]["engine"], "rea")
        cmp_ = preview.compare_preview(_full_dump(), _RD(), "SquadTileCompositionSet", (1024, 768), (1920, 1080),
                                       "Large UI", "s", sets=SETS, engine="rea")
        for side in ("a", "b"):
            self.assertIn("confidence", cmp_[side])
            self.assertEqual(cmp_[side]["confidence"]["engine"], "rea")

    def test_all1_medium_and_large_profiles_expose_build_labelled_measurements(self):
        from skin_editor import layoutspace
        for prof, exp_grid in (
            (layoutspace.PROFILE_FULLSCREEN, (30, 16)),
            (layoutspace.PROFILE_FULLSCREEN_MEDIUM, (25, 13)),
            (layoutspace.PROFILE_FULLSCREEN_LARGE, (20, 11)),
        ):
            vp = layoutspace.viewport_profile(prof)
            self.assertEqual(vp["grid"], exp_grid)
            fs = preview.fullscreen_measurements(profile=prof)
            self.assertTrue(fs["available"], prof)
            self.assertIn("27.1.0.2505117", str(fs.get("build") or ""))
            conf = preview.confidence_for("SquadComposition-Large", "rea", profile=prof)
            self.assertEqual(conf["label"], "measured", prof)
            self.assertIn(prof, conf["reason"])
            self.assertIn("measured (27.1.0, carried over to 27.1.1)", conf["reason"])


if __name__ == "__main__":
    unittest.main()
