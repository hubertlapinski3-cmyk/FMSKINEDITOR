"""BND1 Part B tests: B2 (tile sizes), B3 (allowed tiles), B4 (screen index), B5 (Standard/Small apply)."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from skin_editor import config as se_config, custom_layouts as cl, engine as engine_mod, project as project_mod, tiles as tiles_mod


class Bnd1PartBTests(unittest.TestCase):
    AA = Path((se_config.load().get("game_dir") or "")) / "fm_Data" / "StreamingAssets" / "aa" / "StandaloneWindows64"
    DUMP = Path(r"__absent_fixture_path__")

    def test_b2_add_size_reuses_guid_and_builds_and_apply_guards(self):
        bundle = self.AA / "ui-tileslayouts_assets_all.bundle"
        if not bundle.is_file():
            self.skipTest("needs game ui-tileslayouts_assets_all.bundle")
        descs = tiles_mod.list_tile_descriptions(bundle)
        atm = next(d for d in descs if d["name"] == "SquadAtmosphereTileDescription")
        guid = atm["configurations"][0]["guid"]
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as td:
            out_dir = Path(td)
            op = {
                "op": "add-tile-size",
                "bundle": "ui-tileslayouts_assets_all.bundle",
                "path_id": atm["path_id"],
                "description": atm["id"],
                "size": {"x": 4, "y": 6},
                "reuse_guid": guid,
            }
            changed, _notes, done = tiles_mod.apply_ops(bundle, out_dir, [op])
            self.assertTrue(changed)
            self.assertIn(int(atm["path_id"]), done)
            built = out_dir / "ui-tileslayouts_assets_all.bundle"
            self.assertEqual(tiles_mod.check_ops(bundle, built, [op]), [])

            # Never create a new GUID: bogus GUID must fail validate/apply.
            bad = dict(op, reuse_guid="0" * 32)
            with self.assertRaises(ValueError):
                tiles_mod.apply_ops(bundle, out_dir, [bad])

    def test_g1_tile_sizes_refused_unless_experimental_enabled(self):
        bundle = self.AA / "ui-tileslayouts_assets_all.bundle"
        if not bundle.is_file():
            self.skipTest("needs game ui-tileslayouts_assets_all.bundle")
        e = engine_mod.Engine()
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as td:
            e.ws.root = Path(td)
            e.ws.projects.mkdir(parents=True, exist_ok=True)
            p = project_mod.new("g1-tile-sizes")
            project_mod.save(e.ws, p)
            self.assertFalse(project_mod.experimental_tile_sizes(p))
            with self.assertRaises(ValueError) as ctx:
                e.tiles_add_size({}, {"project": "g1-tile-sizes", "description": "Atmosphere", "width": 4, "height": 6})
            self.assertIn("experimental", str(ctx.exception).lower())
            project_mod.set_experimental_tile_sizes(p, True)
            project_mod.save(e.ws, p)
            r = e.tiles_add_size({}, {"project": "g1-tile-sizes", "description": "Atmosphere", "width": 4, "height": 6})
            self.assertEqual(r["op"]["size"], {"x": 4, "y": 6})

    def test_b3_element_set_add_and_remove_builds_and_checks(self):
        bundle = self.AA / "ui-tileslayouts_assets_all.bundle"
        if not bundle.is_file():
            self.skipTest("needs game ui-tileslayouts_assets_all.bundle")
        sets = tiles_mod.list_element_sets(bundle)
        descs = tiles_mod.list_tile_descriptions(bundle)
        sq = next(s for s in sets if "Squad" in s["name"] and s["descriptions"])
        existing_pids = {d["path_id"] for d in sq["descriptions"]}
        cand = next(d for d in descs if d["path_id"] not in existing_pids)
        rem = sq["descriptions"][0]
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as td:
            out_dir = Path(td)
            add_op = {
                "op": "set-add-tile",
                "bundle": "ui-tileslayouts_assets_all.bundle",
                "path_id": sq["path_id"],
                "element_set": sq["name"],
                "description_path_id": cand["path_id"],
                "description_id": cand["id"],
            }
            rem_op = {
                "op": "set-remove-tile",
                "bundle": "ui-tileslayouts_assets_all.bundle",
                "path_id": sq["path_id"],
                "element_set": sq["name"],
                "description_path_id": rem["path_id"],
                "description_id": rem["id"],
            }
            changed, _notes, _done = tiles_mod.apply_ops(bundle, out_dir, [add_op, rem_op])
            self.assertTrue(changed)
            built = out_dir / "ui-tileslayouts_assets_all.bundle"
            self.assertEqual(tiles_mod.check_ops(bundle, built, [add_op, rem_op]), [])

    def test_b2_apply_guard_refuses_until_bundle_built_and_installed(self):
        e = engine_mod.Engine()
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as td:
            e.ws.root = Path(td)
            e.ws.projects.mkdir(parents=True, exist_ok=True)
            p = project_mod.new("bnd1-guard")
            p["tile_bundle_ops"] = [{
                "op": "add-tile-size",
                "bundle": "ui-tileslayouts_assets_all.bundle",
                "path_id": "919986441625255961",
                "description": "Atmosphere",
                "size": {"x": 4, "y": 6},
                "reuse_guid": "93be32b6a88b28f42b2281d945751019",
            }]
            project_mod.save(e.ws, p)
            fake_obj = {
                "m_gridComponents": [{
                    "m_elementID": "Atmosphere",
                    "m_configDescriptionKeys": ["Atmosphere"],
                    "m_location": {"x": 12, "y": 1, "width": 4, "height": 6},
                }]
            }
            msg = e._refuse_if_uninstalled_project_tile_ops("bnd1-guard", [fake_obj])
            self.assertIsNotNone(msg)
            self.assertIn("build and install the project's bundle build first", msg)

    def test_b4_screen_index_counts_editable_and_templates(self):
        e = engine_mod.Engine()
        if not e._preview_dump():
            self.skipTest("needs layout dump")
        res = e.playground_screen_index({}, {})
        counts = res["counts"]
        self.assertGreater(counts["screens"], 900)
        self.assertGreater(counts["editable"], 1800)
        self.assertGreater(counts["template"], 0)
        sample_tmpl = next(c for s in res["screens"] for c in s["compositions"] if not c["editable_by_file"])
        self.assertEqual(sample_tmpl["editability_label"], "template, not editable by file")

    def test_b5_apply_to_breakpoints_skips_unfitting_standard_or_small(self):
        e = engine_mod.Engine()
        if not e._preview_dump():
            self.skipTest("needs layout dump")
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as td:
            td_path = Path(td)
            e.ws.root = td_path
            e.ws.projects.mkdir(parents=True, exist_ok=True)
            e.ws.build.mkdir(parents=True, exist_ok=True)
            project_mod.save(e.ws, project_mod.new("bnd1-b5"))
            custom_dir = td_path / "CustomGridCompositions"
            custom_dir.mkdir()
            edits = [{"space": "main", "element_id": "Atmosphere", "x": 16, "y": 4, "w": 4, "h": 2},
                     {"space": "main", "element_id": "Training", "x": 16, "y": 6, "w": 4, "h": 4}]
            with mock.patch("skin_editor.custom_layouts.folder", return_value=custom_dir):
                res = e.customlayout_apply_edits({}, {
                    "project": "bnd1-b5",
                    "composition": "SquadComposition-Large",
                    "edits": edits,
                    "apply_to_breakpoints": True,
                })
                self.assertIn("tx_id", res)
                self.assertIn("breakpoint_applied", res)
                self.assertIn("breakpoint_skipped", res)
                # At least Standard or Small was processed (either applied or skipped with a reason).
                total_bp = len(res["breakpoint_applied"]) + len(res["breakpoint_skipped"])
                self.assertEqual(total_bp, 2)
                for sk in res["breakpoint_skipped"]:
                    self.assertTrue(sk["reason"])

    def test_rel15c_slot_edits_refused_unless_experimental_enabled(self):
        from tests.test_api import close_logs
        self.addCleanup(close_logs)
        e = engine_mod.Engine()
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as td:
            td_path = Path(td)
            e.ws.root = td_path
            e.ws.projects.mkdir(parents=True, exist_ok=True)
            p = project_mod.new("rel15c-slots")
            project_mod.save(e.ws, p)
            self.assertFalse(project_mod.experimental_slot_edits(p))
            refused = e.customlayout_apply_edits({}, {
                "project": "rel15c-slots",
                "composition": "SquadComposition-Large",
                "edits": [{"space": "m_bottom", "op": "add", "element_id": "Happiness", "x": 16, "y": 4, "w": 4, "h": 2}],
            })
            self.assertIn("refused", refused)
            self.assertIn("experimental", refused["refused"].lower())
            project_mod.set_experimental_slot_edits(p, True)
            project_mod.save(e.ws, p)
            self.assertTrue(project_mod.experimental_slot_edits(project_mod.load(e.ws, "rel15c-slots")))
