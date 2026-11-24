"""Stage 5E, backend: the Playground session RPCs on the 5B model, and the tile-move gate run as the tile moves.

The engine runs entirely on a temporary FM27SE_WORKSPACE (nothing is ever written to the live workspace): the
project, the session and the operation records live there; the imported dump and the reference manifest are
COPIES of the real workspace's, so `playground.validate_move` can gate against a fresh dump. The game folder is
never read here: the session model tests run on synthetic records, and the move gate reads the dump only."""
import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path

COMPOSITION = "SquadComposition-Standard"


def _real_config():
    saved = os.environ.pop("FM27SE_WORKSPACE", None)
    try:
        from skin_editor import config
        return config.load()
    finally:
        if saved is not None:
            os.environ["FM27SE_WORKSPACE"] = saved


def _real_ws():
    from skin_editor import config
    return config.workspace(_real_config())


class EngineOnTempWorkspace(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from skin_editor import config, project as project_mod, projfmt
        cls.tmp = tempfile.TemporaryDirectory(prefix="fm27se-5e-", ignore_cleanup_errors=True)
        os.environ["FM27SE_WORKSPACE"] = cls.tmp.name
        try:
            from skin_editor.engine import Engine
            cls.eng = Engine()
        finally:
            os.environ.pop("FM27SE_WORKSPACE", None)
        real = _real_ws()
        real_cfg = _real_config()
        shutil.copyfile(real.layout / "current.json", cls.eng.ws.layout / "current.json")
        shutil.copyfile(real.vanilla / "manifest.json", cls.eng.ws.vanilla / "manifest.json")
        from skin_editor import detect
        cls.eng.info = detect.describe(real_cfg["game_dir"])     # read-only: the description reads go through the stock game folder
        cls.project = "pg-test"
        projfmt.write(cls.eng.ws, project_mod.validate(project_mod.new(cls.project)))

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def op(self, **over):
        """One fm-playop/1 record as uidoc.classify produces it (a SetColor on a scoped rule, measured reach)."""
        op = {"schema": "fm-playop/1", "id": "op-test-1", "kind": "SetColor",
              "target": {"screen": COMPOSITION, "logical_id": "guid1/VisualElement#Header",
                         "structural_key": "guid1/VisualElement/VisualElement/Header",
                         "locator": {"bundle": "ui-styles_assets_common.bundle", "bundle_sha256": "ab" * 32, "cab": None,
                                     "path_id": "123", "m_id": "1039390893"},
                         "guard": {"type": "VisualElement", "name": "Header", "classes": ["dashboard-tile"]},
                         "render_pos": "0/2/1"},
              "original": {"value": "#171717", "evidence": "mapped",
                           "provenance": {"bundle": "ui-styles_assets_default.bundle", "sheet": "AlwaysAppliedStyleSheet",
                                          "selector": ".dashboard-tile", "occurrence": 0, "field": "background-color"}},
              "new": {"rule": {"sheet": {"bundle": "ui-styles_assets_default.bundle", "name": "AlwaysAppliedStyleSheet"},
                               "selector": ".dashboard-tile", "props": {"background-color": {"rgb": "#112233", "a": 1.0}},
                               "reach": {"elements": 1, "layouts": 1, "screens": 1, "measured_by": "layout.reach (static lower bound)"}},
                      "route": {"chosen": "scoped_rule", "reason": "the scoped rule is the route the user chose"}},
              "note": "", "created_utc": "2026-11-18T00:00:00Z", "modified_utc": "2026-11-18T00:00:00Z",
              "state": "applied", "superseded_by": None, "validation": None}
        op.update(over)
        return op

    def test_the_session_starts_empty_and_records_an_operation_with_supersession(self):
        s0 = self.eng.playground_session({}, {"project": self.project})
        self.assertEqual(s0["counts"]["total"], 0)
        r1 = self.eng.playground_add_operation({}, {"project": self.project, "operation": self.op()})
        self.assertEqual(r1["counts"]["applied"], 1)
        self.assertTrue(r1["operation"]["validation"]["ok"])
        self.assertEqual(r1["projection"]["declaration_edits"][0]["sheet"], "AlwaysAppliedStyleSheet")
        r2 = self.eng.playground_add_operation({}, {"project": self.project, "operation": self.op(id="op-test-2")})
        self.assertEqual(r2["superseded"], ["op-test-1"])
        s = self.eng.playground_session({}, {"project": self.project})
        self.assertEqual(s["counts"], {"total": 2, "applied": 1, "superseded": 1})
        # the session file lives in the TEMP workspace's project folder
        p = Path(self.tmp.name) / "projects" / self.project / "edits" / "playground.json"
        self.assertTrue(p.is_file())

    def test_a_bad_operation_is_refused_and_never_stored(self):
        bad = self.op()
        del bad["new"]["rule"]["reach"]
        with self.assertRaises(Exception) as c:
            self.eng.playground_add_operation({}, {"project": self.project, "operation": bad})
        self.assertIn("reach was not measured", str(c.exception))
        s = self.eng.playground_session({}, {"project": self.project})
        self.assertNotIn("op-bad", [o["id"] for o in s["session"]["operations"]])

    def test_undo_redo_revert_use_the_5b_history(self):
        for i in (3, 4):
            try:
                self.eng.playground_add_operation({}, {"project": self.project, "operation": self.op(id="op-test-%d" % i)})
            except Exception:
                pass
        s = self.eng.playground_session({}, {"project": self.project})
        applied = [o["id"] for o in s["session"]["operations"] if o.get("state") == "applied"]
        undone = self.eng.playground_undo({}, {"project": self.project})
        self.assertEqual(undone["undone"], applied[-1])
        redone = self.eng.playground_redo({}, {"project": self.project, "op_id": applied[-1]})
        self.assertEqual(redone["redone"], applied[-1])
        self.eng.playground_revert({}, {"project": self.project})
        s = self.eng.playground_session({}, {"project": self.project})
        self.assertEqual(s["counts"].get("applied", 0), 0)
        self.assertEqual(s["counts"].get("reverted"), s["counts"]["total"] - s["counts"].get("superseded", 0))

    def test_build_operation_refuses_a_bad_geometry_and_a_duplicate_id_and_never_yields_an_operation(self):
        """The browser cannot get past the gate: build_operation runs the gate itself, builds NO operation on a
        refusal, and the record it does build takes the cell's element id FROM THE DUMP (a mismatched element id
        the browser might send for a move is ignored - there is nothing to match against). add_operation then
        validates the built record again. Runs on its OWN project so the shared one stays empty for the others."""
        from skin_editor import project as project_mod, projfmt
        projfmt.write(self.eng.ws, project_mod.validate(project_mod.new("pg-buildop")))
        project = "pg-buildop"
        # an overlapping move: refused, no operation
        r = self.eng.playground_build_operation({}, {"kind": "MoveNode", "composition": COMPOSITION, "cell_index": 0,
                                                     "geometry": {"x": 12, "y": 6, "w": 4, "h": 2}})
        self.assertIn("refused", r)
        self.assertFalse(r["gate"]["valid"])
        self.assertTrue(any(c["element_id"] == "Atmosphere" for c in r["gate"]["collisions"]))
        self.assertIsNone(r["operation"])
        # an add whose element id already exists: refused, no operation
        r2 = self.eng.playground_build_operation({}, {"kind": "AddCell", "composition": COMPOSITION, "cell_index": 5,
                                                      "element_id": "Training", "geometry": {"x": 0, "y": 9, "w": 2, "h": 2},
                                                      "description": {"path_id": self.any_description_path(), "config_index": 0}})
        self.assertIn("refused", r2)
        self.assertIsNone(r2["operation"])
        self.assertTrue(any("not unique" in blk for blk in r2["gate"]["blocks"]))
        # a valid move: the built record carries the DUMP's element id (the browser sent none), validates...
        r3 = self.eng.playground_build_operation({}, {"kind": "MoveNode", "composition": COMPOSITION, "cell_index": 0,
                                                      "geometry": {"x": 12, "y": 9, "w": 4, "h": 2}})
        self.assertNotIn("refused", r3)
        self.assertEqual(r3["operation"]["target"]["cell"]["cell_element_id"], "Training")
        self.assertTrue(r3["validation"]["ok"])
        # ...and passes add_operation, which validates it AGAIN
        self.eng.playground_add_operation({}, {"project": project, "operation": r3["operation"]})
        s = self.eng.playground_session({}, {"project": project})
        self.assertEqual(s["counts"]["applied"], 1)

    def test_the_move_gate_blocks_overlaps_and_locked_cells_and_passes_a_free_move(self):
        # SquadComposition-Standard, from the copied dump: Training (12,4), Atmosphere (12,6), Tactics (12,0),
        # HumanActionsControlPanelBlock (locked, 0,0), FirstTeamOverview (0,1)
        free = self.eng.playground_validate_move({}, {"composition": COMPOSITION, "cell_index": 0,
                                                      "geometry": {"x": 12, "y": 9, "w": 4, "h": 2}})
        self.assertTrue(free["valid"], free)
        self.assertEqual(free["cell_element_id"], "Training")
        overlap = self.eng.playground_validate_move({}, {"composition": COMPOSITION, "cell_index": 0,
                                                         "geometry": {"x": 12, "y": 6, "w": 4, "h": 2}})
        self.assertFalse(overlap["valid"])
        self.assertTrue(overlap["collisions"] and any(c["element_id"] == "Atmosphere" for c in overlap["collisions"]))
        self.assertEqual(overlap["collisions"][0]["geometry"], {"x": 12, "y": 6, "w": 4, "h": 2})
        locked = self.eng.playground_validate_move({}, {"composition": COMPOSITION, "cell_index": 3,
                                                        "geometry": {"x": 0, "y": 2, "w": 12, "h": 1}})
        self.assertFalse(locked["valid"])
        self.assertTrue(any("locked" in blk for blk in locked["blocks"]))
        same = self.eng.playground_validate_move({}, {"composition": COMPOSITION, "cell_index": 0,
                                                      "geometry": {"x": 12, "y": 4, "w": 4, "h": 2}})
        self.assertFalse(same["valid"])                                 # no change is a block, not a move

    def test_the_resize_gate_runs_the_overlap_and_limits_without_the_move_only_size_block(self):
        # ADDENDUM: a resize candidate shrinks FirstTeamOverview (0,1,12x7 -> 12x6): valid despite the size change,
        # with the dump's limits as a warning; a growth into Atmosphere's region is refused by the overlap gate.
        grown = self.eng.playground_validate_move({}, {"composition": COMPOSITION, "cell_index": 4, "resize": True,
                                                       "geometry": {"x": 0, "y": 1, "w": 12, "h": 6}})
        self.assertTrue(grown["valid"], grown)
        self.assertEqual(grown["cell_element_id"], "FirstTeamOverview")
        self.assertEqual(grown["blocks"], [])                          # the size change itself is no longer a block
        self.assertEqual(grown["warnings"], [])                        # 12x6 is within the dump's own limits here
        into = self.eng.playground_validate_move({}, {"composition": COMPOSITION, "cell_index": 0, "resize": True,
                                                      "geometry": {"x": 12, "y": 4, "w": 4, "h": 3}})   # reaches Atmosphere at (12,6,4x2)
        self.assertFalse(into["valid"])
        self.assertTrue(any(c["element_id"] == "Atmosphere" for c in into["collisions"]))

    def test_the_add_gate_checks_uniqueness_overlap_and_the_description(self):
        # ADDENDUM: an added cell reuses an existing description and configuration
        ok = self.eng.playground_validate_add({}, {"composition": COMPOSITION, "element_id": "AddedTile", "cell_index": 5,
                                                   "geometry": {"x": 0, "y": 9, "w": 2, "h": 2},
                                                   "description": {"path_id": self.any_description_path(), "config_index": 0}})
        self.assertTrue(ok["valid"], ok)
        self.assertTrue(ok["configuration"] and ok["configuration"]["description_id"])
        dup = self.eng.playground_validate_add({}, {"composition": COMPOSITION, "element_id": "Training", "cell_index": 5,
                                                    "geometry": {"x": 0, "y": 9, "w": 2, "h": 2},
                                                    "description": {"path_id": self.any_description_path(), "config_index": 0}})
        self.assertFalse(dup["valid"])
        self.assertTrue(any("not unique" in blk for blk in dup["blocks"]))
        overlap = self.eng.playground_validate_add({}, {"composition": COMPOSITION, "element_id": "AddedTile", "cell_index": 5,
                                                        "geometry": {"x": 12, "y": 4, "w": 2, "h": 2},
                                                        "description": {"path_id": self.any_description_path(), "config_index": 0}})
        self.assertFalse(overlap["valid"])
        self.assertTrue(overlap["collisions"])
        bad_cfg = self.eng.playground_validate_add({}, {"composition": COMPOSITION, "element_id": "AddedTile", "cell_index": 5,
                                                        "geometry": {"x": 0, "y": 9, "w": 2, "h": 2},
                                                        "description": {"path_id": self.any_description_path(), "config_index": 99}})
        self.assertFalse(bad_cfg["valid"])
        self.assertTrue(any("configuration index" in blk for blk in bad_cfg["blocks"]))

    def any_description_path(self):
        descs = self.eng._uidoc_descriptions(COMPOSITION) or []
        for rec in descs:
            for d in rec["descriptions"]:
                if d.get("read") and d.get("path_id"):
                    return str(d["path_id"])
        self.fail("the composition has no readable tile description")

    def test_a_legacy_single_file_project_is_refused_by_name(self):
        from skin_editor import project as project_mod
        project_mod.path(self.eng.ws, "legacy-pg").write_text(json.dumps(project_mod.new("legacy-pg")), encoding="utf-8")
        with self.assertRaises(RuntimeError) as c:
            self.eng.playground_session({}, {"project": "legacy-pg"})
        self.assertIn("legacy single-file project", str(c.exception))


if __name__ == "__main__":
    unittest.main()
