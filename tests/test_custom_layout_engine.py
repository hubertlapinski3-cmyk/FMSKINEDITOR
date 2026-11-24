"""ST1 parts A to C (backend): the engine endpoints of the custom-layout route, on a temporary workspace and a temporary folder (never the live CustomGridCompositions)."""
import hashlib
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from skin_editor import config, custom_layouts as cl, project
from skin_editor.api.methods import methods
from skin_editor.engine import Engine


def sha(b):
    return hashlib.sha256(b).hexdigest()


class EngineEndpoints(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix="fm27se-cle-"))
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)
        self.folder = self.root / "CustomGridCompositions"
        patcher = mock.patch.object(cl, "folder", lambda home=None: self.folder)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.e = Engine.__new__(Engine)
        self.e.ws = config.Workspace(self.root / "ws")
        self.e._running_override = False
        self.project = "demo"
        p = project.new(self.project, "27.1.0")
        project.save(self.e.ws, p)

    def build(self, files):
        d = self.e.ws.build / self.project / "20261121T000000Z"
        (d / "custom-layouts").mkdir(parents=True)
        rows = []
        for name, data in files.items():
            (d / "custom-layouts" / name).write_bytes(data)
            rows.append({"name": name, "composition": name, "size": len(data), "sha256": sha(data)})
        (d / "custom-layouts.json").write_text(json.dumps({"schema": "fm-customlayouts/1", "files": rows}), encoding="utf-8")
        (d / "build-report.json").write_text("{}", encoding="utf-8")

    def test_the_methods_are_in_the_api_table_and_point_at_engine_operations(self):
        for name in ("customlayout.list", "playground.tile_set", "customlayout.preflight", "customlayout.apply", "customlayout.rollback", "customlayout.recovery_scan"):
            self.assertIn(name, methods())
            self.assertTrue(callable(getattr(Engine, methods()[name].attr)))

    def test_the_rpc_schema_accepts_the_studio_swap_tile_and_move_calls_as_they_are_sent(self):
        """The Studio sends SwapTile without cell_index or geometry and with a tile object; the real RPC validation must accept it (found by the E2E1 chain)."""
        from skin_editor.api.schema import validate
        schema = methods()["playground.build_operation"].schema
        swap = {"kind": "SwapTile", "composition": "SquadComposition-Large", "element_id": "Atmosphere", "tile": {"name": "Happiness", "size": {"x": 4, "y": 4}}, "project": "pg"}
        self.assertEqual(validate(schema, swap)["tile"]["name"], "Happiness")
        move = {"kind": "MoveNode", "composition": "SquadComposition-Large", "cell_index": 0, "geometry": {"x": 16, "y": 4, "w": 4, "h": 2}, "project": "pg"}
        self.assertEqual(validate(schema, move)["cell_index"], 0)
        with mock.patch("skin_editor.engine.layout_dump.load", return_value={"cells": [], "compositions": []}):
            with self.assertRaises(ValueError):
                self.e.playground_build_operation({}, {"kind": "MoveNode", "composition": "SquadComposition-Large"})

    def test_the_layout_bundle_comes_from_the_stock_game_folder_and_a_modified_one_is_refused(self):
        """The vanilla snapshot holds the style bundles only; a layout session reads the target layout bundle from the game folder while it verifies as stock (E2E1)."""
        from skin_editor import install, playops
        aa = self.root / "aa"
        aa.mkdir()
        (aa / "ui-tileslayouts_assets_all.bundle").write_bytes(b"stock bytes")
        s = playops.new_session("pg", None)
        target = {"screen": "C", "logical_id": "C|host:X@0", "structural_key": "k", "locator": {"bundle": "ui-tileslayouts_assets_all.bundle", "bundle_sha256": None, "path_id": "1"},
                  "guard": {"type": "Host", "name": "X", "classes": []},
                  "cell": {"composition": "C", "cell_index": 0, "cell_element_id": "X", "geometry": {"x": 0, "y": 0, "w": 2, "h": 2}}}
        playops.add(s, playops.new_operation("MoveNode", target, {}, original={"value": {"x": 1, "y": 1, "w": 2, "h": 2}, "evidence": "directly serialized"}))
        self.e.need_info = lambda: {"aa_dir": str(aa)}
        identity = {"files": {}}
        with mock.patch.object(install, "refuse_if_updated"), mock.patch.object(install, "tamper_status", return_value={"files": {"ui-tileslayouts_assets_all.bundle": "stock"}}):
            self.assertEqual(self.e._layout_source_for(s, identity), aa)
        self.assertEqual(identity["files"], {"ui-tileslayouts_assets_all.bundle": sha(b"stock bytes")})
        with mock.patch.object(install, "refuse_if_updated"), mock.patch.object(install, "tamper_status", return_value={"files": {"ui-tileslayouts_assets_all.bundle": "modified"}}):
            with self.assertRaises(RuntimeError) as cm:
                self.e._layout_source_for(s, {"files": {}})
        self.assertIn("is not stock", str(cm.exception))
        self.assertIsNone(self.e._layout_source_for(s, {"files": {"ui-tileslayouts_assets_all.bundle": "ab"}}))       # already in the snapshot: nothing to read from the game folder

    def test_list_marks_the_customised_screens_with_the_badge_text(self):
        self.folder.mkdir()
        (self.folder / "PlayerReportOverviewComposition-Large").write_bytes(b"{}")
        r = self.e.custom_layouts_list({}, {})
        self.assertEqual([f["composition"] for f in r["files"]], ["PlayerReportOverviewComposition-Large"])
        self.assertEqual(r["badge"], "customised in the game: this file is used instead of the bundle")
        self.assertIn("will not show", r["warning"])
        self.assertEqual(self.e._customised_names(), ["PlayerReportOverviewComposition-Large"])
        self.assertEqual(shutil.rmtree(self.folder), None)
        self.assertEqual(self.e.custom_layouts_list({}, {})["files"], [])

    def test_routing_reports_and_stores_the_layout_route(self):
        self.assertEqual(self.e.project_routing({}, {"project": self.project})["layout_route"], "custom_layout")
        r = self.e.project_set_routing({}, {"project": self.project, "layout_route": "bundle"})
        self.assertEqual((r["layout_route"], r["layout_route_explicit"]), ("bundle", True))
        self.assertEqual(r["layout_route_default"], "custom_layout")

    def test_preflight_apply_rollback_and_recovery_through_the_engine(self):
        self.folder.mkdir()
        (self.folder / "Mine").write_bytes(b"user layout")
        self.build({"Mine": b"ours", "New": b"new"})
        pf = self.e.customlayout_preflight({}, {"project": self.project})
        self.assertEqual(pf["required_confirmations"], ["replace:Mine"])
        refused = self.e.customlayout_apply({}, {"project": self.project})
        self.assertEqual(refused["required_confirmations"], ["replace:Mine"])
        self.assertEqual((self.folder / "Mine").read_bytes(), b"user layout")             # nothing written without the confirmation
        tx = self.e.customlayout_apply({}, {"project": self.project, "confirmations": ["replace:Mine"]})
        self.assertEqual(tx["state"], "completed")
        self.assertEqual((self.folder / "Mine").read_bytes(), b"ours")
        self.assertEqual(self.e.customlayout_recovery_scan({}, {}), [])
        done = self.e.customlayout_rollback({}, {"tx_id": tx["tx_id"]})
        self.assertEqual(done["state"], "rolled_back")
        self.assertEqual({p.name: p.read_bytes() for p in self.folder.iterdir()}, {"Mine": b"user layout"})

    def test_the_game_running_refuses_the_apply(self):
        self.build({"A": b"a"})
        self.e._running_override = True
        r = self.e.customlayout_apply({}, {"project": self.project})
        self.assertIn("game is running", r["refused"])
        self.assertFalse(self.folder.exists())

    def test_a_build_without_custom_files_is_reported_plainly(self):
        with self.assertRaises(RuntimeError):
            self.e.customlayout_preflight({}, {"project": self.project})


if __name__ == "__main__":
    unittest.main()
