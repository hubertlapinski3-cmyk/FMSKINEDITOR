"""The in-app layout dump builder (skin_editor/layout_scan.py) on archived set C.

Read only: the archived set-C bundles, their MANIFEST.json, and the C dump produced by the old
FM27_LayoutMCP index (used only as an independent expectation in the evidence script). No live game path,
no writes into the archive.
"""
import json
import os
import tempfile
import unittest
from pathlib import Path

from skin_editor import bundles, config, layout_dump, layout_scan

ARCHIVE = Path(os.environ.get("UIDOC_ARCHIVE", r"__absent_fixture_path__"))
SETC = Path(os.environ.get("UIDOC_C_AA") or (next(iter(sorted(ARCHIVE.glob("set-C-*"))), Path("missing")) / "StandaloneWindows64"))
MANIFEST = SETC.parent / "MANIFEST.json"
BUILD = "27.1.0.2505117"

needs_setc = unittest.skipUnless(
    SETC.is_dir() and (SETC / "ui-tileslayouts_assets_all.bundle").is_file() and MANIFEST.is_file(),
    "archived set-C bundles or MANIFEST.json not present")


class ScanCancelledProgress:
    """A job progress whose cancel request is already set."""

    def __init__(self, after=0):
        self.calls, self.after = 0, after

    def __call__(self, message, fraction):
        self.calls += 1

    def cancelled(self):
        return self.calls >= self.after


@needs_setc
class LayoutScanOnSetC(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dump = layout_scan.build_dump(SETC, BUILD)

    def test_section_counts_match_the_archived_set(self):
        self.assertEqual(layout_dump.summary(self.dump), {
            "layouts": 7487, "elements": 134674, "includes": 14648, "panels": 624, "tiles": 5050,
            "compositions": 1834, "cells": 5439, "cell_configs": 5275, "areas.map": 0, "areas.anchors": 0,
            "elements_with_runtime_classes": 0})
        errs, total = layout_dump.validate(self.dump)
        self.assertEqual((errs, total), ([], 0))

    def test_guid_and_ord_are_resolved_from_the_bundles(self):
        by_guid = {l["guid"]: l for l in self.dump["layouts"]}
        # a layout whose GUID the old index published: the bundle's asset container carries the same value
        lay = by_guid["77a358bf1be7f46428e4951d612dc29e"]
        self.assertEqual(lay["name"], "ShuffleDraft_HelpPanel")
        self.assertEqual(lay["bundle"], "ui-visualtreeassets_assets_fantasydraftvisualtreeassetpreload.bundle")
        els = [e for e in self.dump["elements"] if e["layout_id"] == lay["id"]]
        self.assertEqual([e["ord"] for e in els], list(range(15)))          # pre-order over m_Children
        self.assertEqual([e["local_id"] for e in els][:3], [-824174065, 1767336568, -1457254390])
        self.assertEqual(els[0]["type"], "UnityEngine.UIElements.UXML")
        self.assertEqual(els[11]["type"], "Template:ShuffleDraft_HelpWelcomeToDraftBlock")
        self.assertIsNone(els[0]["parent_local_id"])

    def test_required_joins_are_closed(self):
        layout_ids = {l["id"] for l in self.dump["layouts"]}
        layout_name = {l["id"]: l["name"] for l in self.dump["layouts"]}
        comp_names = {c["name"] for c in self.dump["compositions"]}
        cell_keys = {(c["composition"], c["cell_index"]) for c in self.dump["cells"]}
        cfg_keys = {(c["composition"], c["cell_index"], c["cfg_index"]) for c in self.dump["cell_configs"]}
        for e in self.dump["elements"]:
            self.assertIn(e["layout_id"], layout_ids)
        for i in self.dump["includes"]:
            self.assertIn(i["from_layout_id"], layout_ids)
            self.assertIn(i["to_layout_id"], layout_ids)
            self.assertTrue(i["alias"])
        for p in self.dump["panels"]:
            self.assertIn(p["layout_id"], layout_ids)
        for c in self.dump["cells"]:
            self.assertIn(c["composition"], comp_names)
        for c in self.dump["cell_configs"]:
            self.assertIn((c["composition"], c["cell_index"]), cell_keys)
            self.assertIn(c["tile_layout_id"], layout_ids)
        for t in self.dump["tiles"]:
            self.assertIn(t["panel_layout_id"], layout_ids)
            self.assertIn(t["composition"], comp_names)
            self.assertIn((t["composition"], t["cell_index"], t["cfg_index"]), cfg_keys)
            self.assertIn(t["tile_layout_id"], layout_ids)
        # the Squad composition the later acceptance tests use: its cells and configs resolve to named tiles
        squad = [t for t in self.dump["tiles"] if t["composition"] == "SquadComposition-Standard"]
        self.assertEqual(len(squad), 5)
        self.assertEqual({t["set_name"] for t in squad}, {"SquadTileCompositionSet"})
        self.assertEqual({layout_name[t["tile_layout_id"]] for t in squad},
                         {"TrainingTile_4x2", "SquadAtmosphereTile_4x2", "TacticsTile_4x4",
                          "HumanActionsControlPanelBlock", "SquadOverviewTableBlock"})
        self.assertEqual({t["cell_element_id"] for t in squad},
                         {"Training", "Atmosphere", "Tactics", "HumanActionsControlPanelBlock", "FirstTeamOverview"})

    def test_source_hashes_cover_every_ui_bundle_the_build_read_and_match_the_archive_manifest(self):
        src = self.dump["meta"]["source"]
        files = sorted(p.name for p in SETC.glob("ui-*.bundle"))
        self.assertEqual(sorted(src["bundles"]), files)
        self.assertGreater(len(files), 60)
        self.assertEqual(src["catalog_hash"], (SETC.parent / "catalog.hash").read_text(encoding="utf-8").strip())
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))["bundles"]
        for name, digest in src["bundles"].items():
            self.assertEqual(digest, bundles.sha256(SETC / name), name)
            self.assertEqual(digest, manifest[name]["sha256"], name)

    def test_the_fingerprint_is_stable_across_two_runs(self):
        again = layout_scan.build_dump(SETC, BUILD)
        self.assertEqual(self.dump["meta"]["index_fingerprint"], again["meta"]["index_fingerprint"])
        for section in ("layouts", "elements", "includes", "panels", "tiles", "compositions", "cells", "cell_configs"):
            self.assertEqual(self.dump[section], again[section], section)
        self.assertEqual(self.dump["areas"], again["areas"])

    def test_cancel_before_the_import_leaves_no_dump(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            ws = config.Workspace(Path(tmp) / "ws")
            with self.assertRaises(layout_scan.ScanCancelled):
                layout_scan.read_and_import(ws, SETC, BUILD, progress=ScanCancelledProgress(after=0))
            self.assertFalse((ws.layout / "current.json").exists())
            self.assertFalse((ws.layout / "status.json").exists())

    def test_cancel_part_way_through_still_imports_nothing(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            ws = config.Workspace(Path(tmp) / "ws")
            with self.assertRaises(layout_scan.ScanCancelled):
                layout_scan.read_and_import(ws, SETC, BUILD, progress=ScanCancelledProgress(after=2))
            self.assertFalse((ws.layout / "current.json").exists())

    def test_a_changed_bundle_hash_makes_the_dump_contaminated(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            ws = config.Workspace(Path(tmp) / "ws")
            man = {"schema": 1, "game_build": BUILD, "reference": self.dump["meta"]["source"]}
            (ws.vanilla / "manifest.json").write_text(json.dumps(man), encoding="utf-8")
            self.assertEqual(layout_dump.staleness(self.dump["meta"], ws)["status"], "fresh")
            meta = json.loads(json.dumps(self.dump["meta"]))
            name = sorted(meta["source"]["bundles"])[0]
            meta["source"]["bundles"][name] = "0" * 64
            st = layout_dump.staleness(meta, ws)
            self.assertEqual(st["status"], "contaminated")
            self.assertIn(name, st["differing_bundles"])
            meta = json.loads(json.dumps(self.dump["meta"]))
            meta["source"]["catalog_hash"] = "0" * 32
            self.assertEqual(layout_dump.staleness(meta, ws)["status"], "stale")


if __name__ == "__main__":
    unittest.main()
