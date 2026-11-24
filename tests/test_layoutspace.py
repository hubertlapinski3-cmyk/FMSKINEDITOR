"""UI4: the three coordinate spaces, per-space overlap, and the UI3 replay."""
import glob
import unittest
from pathlib import Path

from skin_editor import custom_layouts as cl, layoutspace as ls

SQUAD = next(iter(sorted(glob.glob(
    r"__absent_fixture_path__"))), None)


class Spaces(unittest.TestCase):
    def test_bottom_slot_converts_both_ways(self):
        # Squad: design 20x10, pinned measured runtime 30x16 (2560x1440 windowed, Small, Larger).
        # PrepareContent layout-rule / GetSliceZoneOffset layout-rule:
        # bottom X = (gridWidth - mandatoryWidth) + stored x = 10 + 16 = 26;
        # bottom Y = mandatory height + stored y = 10 + 0 = 10.
        self.assertEqual(ls.slot_to_runtime("m_bottom", {"x": 16, "y": 0, "width": 4, "height": 2},
                                            (20, 10), (30, 16)), {"x": 26, "y": 10, "w": 4, "h": 2})
        self.assertEqual(ls.runtime_to_slot("m_bottom", {"x": 26, "y": 10}, (20, 10), (30, 16)), {"x": 16, "y": 0})
        self.assertEqual(ls.runtime_to_slot("m_bottom", {"x": 26, "y": 14}, (20, 10), (30, 16)), {"x": 16, "y": 4})

    def test_right_slot_uses_mandatory_width(self):
        # right zone: base = mandatory width + stored x; accumulator is zero (GetSliceZoneOffset).
        self.assertEqual(ls.slot_to_runtime("m_right", {"x": 0, "y": 2, "width": 4, "height": 2},
                                            (20, 10), (30, 16)), {"x": 20, "y": 2, "w": 4, "h": 2})
        self.assertEqual(ls.runtime_to_slot("m_right", {"x": 20, "y": 2}, (20, 10), (30, 16)), {"x": 0, "y": 2})

    def test_main_right_strip_shifts_by_the_growth_surplus(self):
        self.assertEqual(ls.main_to_runtime({"x": 16, "y": 0, "width": 4, "height": 4}, (20, 10), (30, 16)),
                         {"x": 26, "y": 0, "w": 4, "h": 4})
        self.assertEqual(ls.runtime_to_main({"x": 26, "y": 0}, (20, 10), (30, 16)), {"x": 16, "y": 0})


class PerSpace(unittest.TestCase):
    def setUp(self):
        if not SQUAD:
            self.skipTest("no Squad copy")
        self.obj = cl.read(Path(SQUAD))

    def test_slot_move_is_judged_only_within_its_zone(self):
        # SquadHierachy stored x 16 -> 15 would sit over FirstTeamOverview if the two
        # spaces were mixed; per zone it is legal and must not be refused.
        n = cl.apply_canvas_edits(self.obj, [{"space": "m_bottom", "element_id": "SquadHierachy",
                                              "x": 15, "y": 0}], runtime={"cols": 31, "rows": 17})
        self.assertEqual(n, 1)
        self.assertEqual(cl.validate_before_write(self.obj, "SquadComposition-Large"), [])

    def test_a_legal_slot_drag_is_accepted(self):
        drows = cl.grid_extent(self.obj)[1]          # this copy grew Atmosphere to h4 -> design rows 12
        n = cl.apply_canvas_edits(self.obj, [{"space": "m_bottom", "element_id": "MedicalCentre",
                                              "x": 15, "y": 2}], runtime={"cols": 31, "rows": 17})
        self.assertEqual(n, 1)
        mc = next(e for e in self.obj["m_optionalSlices"]["m_bottom"] if e["m_elementID"] == "MedicalCentre")
        self.assertEqual((mc["m_location"]["x"], mc["m_location"]["y"]), (15, 2))
        self.assertLessEqual(drows + 2 + 2, 17)      # runtime row stays inside 17
        self.assertEqual(cl.validate_before_write(self.obj, "SquadComposition-Large"), [])

    def test_main_overlap_is_still_refused_and_is_called_design(self):
        cl.apply_canvas_edits(self.obj, [{"space": "main", "element_id": "Atmosphere", "x": 15, "y": 8},
                                         {"space": "main", "element_id": "Training", "x": 15, "y": 6}],
                              runtime={"cols": 31, "rows": 17})
        probs = cl.validate_before_write(self.obj, "SquadComposition-Large")
        overlap = [p for p in probs if "overlaps" in p]
        self.assertTrue(overlap)
        self.assertTrue(all(p.startswith("design:") for p in overlap))


class Ui3Replay(unittest.TestCase):
    def test_replay_ui3_intent_writes_its_values_and_is_refused(self):
        if not SQUAD:
            self.skipTest("no Squad copy")
        obj = cl.read(Path(SQUAD))
        # UI3 staged: Atmosphere one column left (x 16 -> 15); Training to row 6.
        n = cl.apply_canvas_edits(obj, [
            {"space": "main", "element_id": "Atmosphere", "x": 15, "y": 8},
            {"space": "main", "element_id": "Training", "x": 15, "y": 6}],
            runtime={"cols": 31, "rows": 17})
        self.assertEqual(n, 2)
        by = {c["m_elementID"]: c["m_location"] for c in obj["m_gridComponents"]}
        self.assertEqual((by["Atmosphere"]["x"], by["Atmosphere"]["y"]), (15, 8))
        self.assertEqual((by["Training"]["x"], by["Training"]["y"]), (15, 6))
        # Apply is refused: the two main cells now overlap FirstTeamOverview in DESIGN space,
        # and the runtime result places Atmosphere off-grid / over FirstTeamOverview.
        self.assertTrue([p for p in cl.validate_before_write(obj, "SquadComposition-Large") if "overlaps" in p])
        runtime = [{"element_id": "Atmosphere", "x": 15, "y": 17, "w": 4, "h": 2},
                   {"element_id": "FirstTeamOverview", "x": 0, "y": 1, "w": 27, "h": 16}]
        self.assertTrue(ls.runtime_problems(runtime, 31, 17))


class Ui5ViewportAndRuntime(unittest.TestCase):
    DUMP = Path(r"__absent_fixture_path__")
    AA = Path(r"__absent_fixture_path__")

    def _engine(self):
        import tempfile
        from skin_editor import config, layout_dump
        from skin_editor.engine import Engine
        tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.addCleanup(tmp.cleanup)
        e = Engine.__new__(Engine)
        e.ws = config.Workspace(Path(tmp.name) / "ws")
        e.cfg = dict(config.DEFAULTS, aa_dir=str(self.AA))
        e.info = {"game_dir": str(self.AA.parent), "aa_dir": str(self.AA)}
        e.index = None
        e._ld = (None, None)
        e._view = (None, None)
        layout_dump.import_dump(e.ws, str(self.DUMP))
        return e

    def test_stock_squad_renders_at_measured_grid_size_with_atmosphere_at_column_26(self):
        """FS1: default viewport profile is 2560x1440 fullscreen, Small, Larger (30x16 with
        Atmosphere at column 26), and 2560x1440 windowed, Small, Larger remains selectable."""
        if not self.DUMP.is_file() or not (self.AA / "ui-tileslayouts_assets_all.bundle").is_file():
            self.skipTest("needs archived set-C dump and tiles bundle")
        e = self._engine()
        rt = e.customlayout_runtime({}, {"composition": "SquadComposition-Large"})
        self.assertEqual(rt["viewport"]["profile"], ls.PROFILE_FULLSCREEN)
        self.assertEqual(rt["viewport"]["width"], 2560)
        self.assertEqual(rt["viewport"]["height"], 1440)
        self.assertEqual(rt["viewport"]["window_mode"], "fullscreen")
        self.assertEqual(rt["viewport"]["information_display"], "Small")
        self.assertEqual(rt["viewport"]["text_scaling"], "Larger")
        self.assertEqual((rt["grid"]["cols"], rt["grid"]["rows"]), (30, 16))
        self.assertEqual(rt["confidence"]["label"], "measured")
        atm = next(c for c in rt["cells"] if c["element_id"] == "Atmosphere")
        self.assertEqual((atm["x"], atm["y"], atm["w"], atm["h"]), (26, 8, 4, 2))
        self.assertEqual(rt["problems"], [])

        rt_win = e.customlayout_runtime({}, {"composition": "SquadComposition-Large", "profile": ls.PROFILE_WINDOWED})
        self.assertEqual(rt_win["viewport"]["profile"], ls.PROFILE_WINDOWED)
        self.assertEqual(rt_win["viewport"]["window_mode"], "windowed")
        self.assertEqual((rt_win["grid"]["cols"], rt_win["grid"]["rows"]), (30, 16))
        self.assertEqual(rt_win["confidence"]["label"], "measured")

    def test_profiles_keep_measurements_and_confidence_strictly_isolated(self):
        """FS1 step 2 & step 5: windowed measurements never count as measured in fullscreen,
        mismatched FS1 compositions carry 'measured mismatch', and all slice zones render."""
        if not self.DUMP.is_file() or not (self.AA / "ui-tileslayouts_assets_all.bundle").is_file():
            self.skipTest("needs archived set-C dump and tiles bundle")
        e = self._engine()
        # Windowed-only measured composition must NOT be 'measured' in fullscreen.
        inj_fs = e.customlayout_base({}, {"composition": "InjuryHistoryCardGridComposition", "profile": ls.PROFILE_FULLSCREEN})
        inj_win = e.customlayout_base({}, {"composition": "InjuryHistoryCardGridComposition", "profile": ls.PROFILE_WINDOWED})
        self.assertNotEqual(inj_fs["confidence"]["label"], "measured")
        self.assertEqual(inj_win["confidence"]["label"], "measured")

        # FS1 mismatch carries 'measured mismatch' and mismatch details in fullscreen.
        mm = e.customlayout_base({}, {"composition": "3_Tiles_8x4-Expandable_2x4x2", "profile": ls.PROFILE_FULLSCREEN})
        self.assertEqual(mm["confidence"]["label"], "measured mismatch")
        self.assertTrue(mm["confidence"]["mismatches"])

        # Step 6: compositions using m_left, m_top and m_bottomRight render every zone cleanly.
        for comp, expected_zone in (
            ("FullTimeTeamReportGridComposition-Large", "m_left"),
            ("MatchExperienceGridComposition-Large", "m_top"),
            ("TacticalPlannerTeamInstructionsTabComposition-Large", "m_bottomRight"),
        ):
            base = e.customlayout_base({}, {"composition": comp})
            self.assertTrue(any(c["space"] == expected_zone for c in base["cells"]), (comp, expected_zone))
            rt = e.customlayout_runtime({}, {"composition": comp})
            self.assertTrue(any(s["space"] == expected_zone for s in rt["slots"]), (comp, expected_zone))

    def test_confidence_is_measured_on_bundle_base_custom_file_and_staged_paths(self):
        """UI5 step 1: Squad, PlayerReportOverview and Portal show 'measured' across bundle base,
        custom file and staged paths."""
        if not self.DUMP.is_file() or not (self.AA / "ui-tileslayouts_assets_all.bundle").is_file():
            self.skipTest("needs archived set-C dump and tiles bundle")
        import tempfile
        from unittest import mock
        e = self._engine()
        for comp in ("SquadComposition-Large", "PlayerReportOverviewComposition-Large", "Portal-Large"):
            # 1. bundle base path
            with mock.patch("skin_editor.custom_layouts.folder", return_value=Path(tempfile.mkdtemp())):
                base = e.customlayout_base({}, {"composition": comp})
                self.assertEqual(base["source"], "bundle")
                self.assertEqual(base["confidence"]["label"], "measured", comp)
                rt_bundle = e.customlayout_runtime({}, {"composition": comp})
                self.assertEqual(rt_bundle["source"], "bundle")
                self.assertEqual(rt_bundle["confidence"]["label"], "measured", comp)
            # 2. custom file path
            import json
            custom_dir = Path(tempfile.mkdtemp())
            (custom_dir / comp).write_text(json.dumps(base["object"]), encoding="utf-8")
            with mock.patch("skin_editor.custom_layouts.folder", return_value=custom_dir):
                base_cf = e.customlayout_base({}, {"composition": comp})
                self.assertEqual(base_cf["source"], "game_folder")
                self.assertEqual(base_cf["confidence"]["label"], "measured", comp)
                rt_cf = e.customlayout_runtime({}, {"composition": comp})
                self.assertEqual(rt_cf["source"], "game_folder")
                self.assertEqual(rt_cf["confidence"]["label"], "measured", comp)
            # 3. staged object path
            rt_staged = e.customlayout_runtime({}, {"composition": comp, "object": base["object"]})
            self.assertEqual(rt_staged["source"], "staged")
            self.assertEqual(rt_staged["confidence"]["label"], "measured", comp)

    def test_legal_vertical_swap_of_training_and_atmosphere_passes_design_and_runtime_checks(self):
        """UI5 step 7: swapping Atmosphere (y4 h2) and Training (y6 h4) passes both design and runtime checks."""
        if not self.DUMP.is_file() or not (self.AA / "ui-tileslayouts_assets_all.bundle").is_file():
            self.skipTest("needs archived set-C dump and tiles bundle")
        e = self._engine()
        edits = [{"space": "main", "element_id": "Atmosphere", "x": 16, "y": 4, "w": 4, "h": 2},
                 {"space": "main", "element_id": "Training", "x": 16, "y": 6, "w": 4, "h": 4}]
        rt = e.customlayout_runtime({}, {"composition": "SquadComposition-Large", "edits": edits})
        self.assertEqual(rt["problems"], [])
        by = {c["element_id"]: c for c in rt["cells"]}
        self.assertEqual((by["Atmosphere"]["x"], by["Atmosphere"]["y"], by["Atmosphere"]["w"], by["Atmosphere"]["h"]), (26, 4, 4, 2))
        self.assertEqual(by["Atmosphere"]["rect"], [2159.6, 425.9, 312, 148])
        self.assertEqual((by["Training"]["x"], by["Training"]["y"], by["Training"]["w"], by["Training"]["h"]), (26, 6, 4, 4))
        self.assertEqual(by["Training"]["rect"], [2159.6, 589.9, 312, 312])

    def test_workspace_favourites_roundtrip(self):
        """FS2: pinned Game Layouts favourites persist in the workspace (favourites.json)."""
        import tempfile
        from skin_editor import engine as engine_mod
        with tempfile.TemporaryDirectory() as td:
            e = engine_mod.Engine()
            e.ws.root = Path(td)
            self.assertEqual(e.playground_favourites({}, {}), {"favourites": []})
            res = e.playground_set_favourites({}, {"favourites": ["SquadComposition-Large", "Portal-Large", "SquadComposition-Large"]})
            self.assertEqual(res, {"favourites": ["SquadComposition-Large", "Portal-Large"]})
            # Re-open a fresh Engine on the same workspace to verify persistence across sessions.
            e2 = engine_mod.Engine()
            e2.ws.root = Path(td)
            self.assertEqual(e2.playground_favourites({}, {}), {"favourites": ["SquadComposition-Large", "Portal-Large"]})

    def test_grid_dims_content_zero_padding(self):
        """FS2: 0 px padding grids (IgnoreOuterPadding=1 or nested) do not lose 24 px margin."""
        from skin_editor.render import screen as screen_mod
        self.assertEqual(screen_mod.grid_dims_content(2468.8, 1319.3, padding=12), (30, 16))
        self.assertEqual(screen_mod.grid_dims_content(2361.3, 1295.9, padding=0), (29, 16))
        self.assertEqual(screen_mod.grid_dims_content(2279.3, 147.5, padding=0), (28, 2))
