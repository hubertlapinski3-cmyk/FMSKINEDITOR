"""Unit tests for skin_editor/skin_diff.py (SKIN-RR1 C3)."""
import unittest

from skin_editor import skin_diff


class TestSkinDiffFixtures(unittest.TestCase):
    def test_noise_filter_ignores_build_noise_fields_and_pptr_shifts(self):
        stock_vta = {
            "m_Name": "PlayerTile",
            "m_ContentHash": 111111,
            "m_VisualElementAssets": [
                {
                    "m_Id": 100, "m_ParentId": 0, "m_OrderInDocument": 0, "m_RuleIndex": 1,
                    "m_FullTypeName": "UnityEngine.UIElements.VisualElement",
                    "m_Classes": ["card", "header"],
                    "m_SerializedData": {"m_Script": {"m_FileID": 1, "m_PathID": 555}},
                }
            ],
            "m_SerializedDataOverrides": [
                {"m_ElementId": 100, "uxmlAssetId": 42, "m_Value": "hello"}
            ],
        }
        rebuilt_vta = {
            "m_Name": "PlayerTile",
            "m_ContentHash": 999999,
            "m_VisualElementAssets": [
                {
                    "m_Id": 777, "m_ParentId": 12, "m_OrderInDocument": 5, "m_RuleIndex": 9,
                    "m_FullTypeName": "UnityEngine.UIElements.VisualElement",
                    "m_Classes": ["card", "header"],
                    "m_SerializedData": {"m_Script": {"m_FileID": 3, "m_PathID": 888}},
                }
            ],
            "m_SerializedDataOverrides": [
                {"m_ElementId": 777, "uxmlAssetId": 99, "m_Value": "hello"}
            ],
        }
        self.assertEqual(
            skin_diff.normalize_tree(stock_vta, "VisualTreeAsset"),
            skin_diff.normalize_tree(rebuilt_vta, "VisualTreeAsset"),
        )

    def test_diff_object_maps_detects_added_removed_changed_and_groups_by_category(self):
        stock_comp = {
            "m_Name": "SquadComposition-Large",
            "m_compositionVersion": 1,
            "m_gridComponents": [
                {"m_elementID": "Atmosphere", "m_location": {"x": 16, "y": 8, "width": 4, "height": 2}},
            ],
        }
        skin_comp = {
            "m_Name": "SquadComposition-Large",
            "m_compositionVersion": 2,
            "m_gridComponents": [
                {"m_elementID": "Atmosphere", "m_location": {"x": 16, "y": 4, "width": 4, "height": 2}},
            ],
        }
        new_comp = {
            "m_Name": "SquadComposition-Large-RR8",
            "m_compositionVersion": 1,
            "m_gridComponents": [
                {"m_elementID": "RR_Bottom1", "m_location": {"x": 0, "y": 0, "width": 4, "height": 2}},
            ],
        }
        stock_map = {
            ("MonoBehaviour", "SquadComposition-Large", 0): {
                "type": "MonoBehaviour", "name": "SquadComposition-Large", "index": 0,
                "category": "composition",
                "norm": skin_diff.normalize_tree(stock_comp, "MonoBehaviour"),
                "summary": skin_diff._summarize_composition(stock_comp),
            },
            ("MonoBehaviour", "OldRemovedTile", 0): {
                "type": "MonoBehaviour", "name": "OldRemovedTile", "index": 0,
                "category": "description",
                "norm": {"m_Name": "OldRemovedTile"},
            },
        }
        skin_map = {
            ("MonoBehaviour", "SquadComposition-Large", 0): {
                "type": "MonoBehaviour", "name": "SquadComposition-Large", "index": 0,
                "category": "composition",
                "norm": skin_diff.normalize_tree(skin_comp, "MonoBehaviour"),
                "summary": skin_diff._summarize_composition(skin_comp),
            },
            ("MonoBehaviour", "SquadComposition-Large-RR8", 0): {
                "type": "MonoBehaviour", "name": "SquadComposition-Large-RR8", "index": 0,
                "category": "composition",
                "norm": skin_diff.normalize_tree(new_comp, "MonoBehaviour"),
                "summary": skin_diff._summarize_composition(new_comp),
            },
        }
        rep = skin_diff.diff_object_maps("ui-tileslayouts_assets_all.bundle", stock_map, skin_map)
        self.assertEqual(rep["status"], "changed")
        self.assertEqual(rep["counts"], {"added": 1, "removed": 1, "changed": 1, "unchanged": 0})
        self.assertEqual(rep["by_category"]["composition"], {"added": 1, "removed": 0, "changed": 1})
        self.assertEqual(rep["by_category"]["description"], {"added": 0, "removed": 1, "changed": 0})
        paths = [f["path"] for f in rep["changed"][0]["fields"]]
        self.assertIn("m_compositionVersion", paths)
        self.assertIn("m_gridComponents[0].m_location.y", paths)

    def test_categorize_object_and_infer_screen_name(self):
        self.assertEqual(
            skin_diff.categorize_object("ui-tileslayouts_assets_all.bundle", "MonoBehaviour", "SquadComposition-Large", {"m_gridComponents": []}),
            "composition",
        )
        self.assertEqual(
            skin_diff.categorize_object("ui-tileslayouts_assets_all.bundle", "MonoBehaviour", "SquadTileCompositionSet", {"m_gridBreakpointCompositionData": []}),
            "composition_set",
        )
        self.assertEqual(
            skin_diff.categorize_object("ui-styles_assets_default.bundle", "StyleSheet", "AlwaysAppliedStyleSheet", {}),
            "style",
        )
        self.assertEqual(
            skin_diff.categorize_object("ui-visualtreeassets_assets_globalvisualtreeassetpreload.bundle", "VisualTreeAsset", "SquadTile", {}),
            "uxml",
        )
        self.assertEqual(skin_diff.infer_screen_name("SquadComposition-Large-RR8", "composition"), "Squad")
        self.assertEqual(skin_diff.infer_screen_name("PlayerReportOverviewComposition-Large", "composition"), "PlayerReportOverview")

    def test_engine_skin_inspect_and_preview_composition_rpcs_are_registered_and_read_only(self):
        import tempfile
        from pathlib import Path
        from unittest import mock
        from skin_editor import config
        from skin_editor.api import methods
        from skin_editor.engine import Engine

        m = methods.methods()
        self.assertIn("skin.inspect", m)
        self.assertIn("skin.preview_composition", m)
        with tempfile.TemporaryDirectory() as tmp:
            e = Engine.__new__(Engine)
            e.ws = config.Workspace(Path(tmp) / "ws")
            e.info = {"aa_dir": tmp}
            skin_dir = Path(tmp) / "fake_skin"
            skin_dir.mkdir()
            fake_comp = {
                "m_Name": "SquadComposition-Large-RR8",
                "m_reflowMode": 0,
                "m_gridComponents": [
                    {"m_elementID": "FirstTeamOverview", "m_location": {"x": 0, "y": 0, "width": 16, "height": 9},
                     "m_minSize": {"x": 16, "y": 9}, "m_maxSize": {"x": 100, "y": 100}},
                    {"m_elementID": "Tactics", "m_location": {"x": 16, "y": 0, "width": 4, "height": 4},
                     "m_minSize": {"x": 4, "y": 4}, "m_maxSize": {"x": 4, "y": 4}},
                ],
                "m_optionalSlices": {},
            }
            with mock.patch("skin_editor.skin_diff.read_skin_composition", return_value=fake_comp):
                res = e.skin_preview_composition({}, {"folder": str(skin_dir), "composition": "SquadComposition-Large-RR8"})
            self.assertEqual(res["source"], "skin_inspect")
            self.assertEqual(res["engine"], "rea")
            self.assertEqual(res["grid"], {"cols": 30, "rows": 16})
            self.assertEqual(res["cells"][1]["element_id"], "Tactics")
            self.assertEqual(res["cells"][1]["x"], 26)
            with self.assertRaises(ValueError):
                e.skin_inspect({}, {"folder": str(Path(tmp) / "missing")})

    def test_screen_resolver_variants_source_and_not_tied(self):
        import tempfile
        from pathlib import Path
        from unittest import mock

        dump = {
            "meta": {"schema": "fmlayout-index/2"},
            "areas": {"map": {}, "anchors": {}},
            "layouts": [
                {"id": 1, "name": "SquadRoot", "guid": "g1"},
                {"id": 2, "name": "SquadRowWidget", "guid": "g2"},
                {"id": 3, "name": "PlayerReportRoot", "guid": "g3"},
            ],
            "elements": [
                {"layout_id": 2, "local_id": 10, "name": "row", "type": "VisualElement", "ord": 0,
                 "parent_local_id": None, "classes": ["squad-badge"], "runtime_classes": []},
            ],
            "includes": [],
            "panels": [
                {"panel_id": "SquadScreen", "layout_id": 1},
                {"panel_id": "PlayerReport", "layout_id": 3},
            ],
            "tiles": [
                {"panel_layout_id": 1, "set_name": "SquadTileCompositionSet", "breakpoint": 3,
                 "variant_idx": 0, "composition": "SquadComposition-Large", "cell_index": 0,
                 "cell_element_id": "Squad", "cfg_index": 0, "size": {"w": 4, "h": 2}, "tile_layout_id": 2},
                {"panel_layout_id": 3, "set_name": "PlayerReportSet", "breakpoint": 3,
                 "variant_idx": 0, "composition": "PlayerReportOverviewComposition-Large", "cell_index": 0,
                 "cell_element_id": "Attr", "cfg_index": 0, "size": {"w": 4, "h": 2}, "tile_layout_id": 2},
            ],
            "compositions": [],
            "cells": [],
            "cell_configs": [],
        }
        tu = {
            "PlayerTableViewSettings": [
                {"layout": "SquadRowWidget", "element": "StreamedTable", "tiles": [{"description": "D", "size": [4, 2], "screens": ["SquadComposition-Large"]}]}
            ]
        }
        res = skin_diff.ScreenResolver(dump=dump, table_usage=tu)
        self.assertEqual(res.resolve_item("composition", "SquadComposition-Large")[0], ["SquadScreen"])
        self.assertEqual(res.resolve_item("composition", "PlayerReportOverviewComposition-Large-FMC-RR8")[0], ["PlayerReport"])
        self.assertEqual(res.resolve_item("uxml", "SquadRowWidget")[0], ["PlayerReport", "SquadScreen"])
        self.assertEqual(res.resolve_item("table_view", "PlayerTableViewSettings")[0], ["PlayerReport", "SquadScreen"])
        un_scr, _, un_why = res.resolve_item("navigation", "UnknownGlobalHelper")
        self.assertEqual(un_scr, [])
        self.assertIn("Global navigation", un_why)

        base, var = skin_diff.split_screen_variant("PlayerReportOverviewComposition-Large-FMC-RR8")
        self.assertEqual(base, "PlayerReportOverviewComposition")
        self.assertEqual(var, "Large · FMC · RR8")

        with tempfile.TemporaryDirectory() as tmp:
            sdir = Path(tmp) / "skin"
            sdir.mkdir()
            (sdir / "README_EN.txt").write_text("Sample-Skin for Football Manager 27 - Windows version 1.0.2\n", encoding="utf-8")
            (sdir / "Dummy.bundle").write_bytes(b"")
            src = skin_diff.detect_skin_source(sdir)
            self.assertEqual(src, {"name": "Sample-Skin", "version": "1.0.2", "label": "Sample-Skin v1.0.2"})
            fake_rep = {
                "bundle": "ui-tileslayouts_assets_all.bundle", "status": "changed",
                "counts": {"added": 1, "removed": 0, "changed": 2, "unchanged": 10},
                "by_category": {"composition": {"added": 1, "changed": 1}, "navigation": {"changed": 1}},
                "added": [{"type": "MonoBehaviour", "name": "PlayerReportOverviewComposition-Large-RR8", "category": "composition", "screen": "PlayerReportOverview"}],
                "removed": [],
                "changed": [
                    {"type": "MonoBehaviour", "name": "PlayerReportOverviewComposition-Standard", "category": "composition", "screen": "PlayerReportOverview", "field_count": 2},
                    {"type": "MonoBehaviour", "name": "GlobalCalendarHelper", "category": "navigation", "screen": "GlobalCalendarHelper", "field_count": 1},
                ],
            }
            with mock.patch("skin_editor.skin_diff.diff_bundle", return_value=fake_rep):
                out = skin_diff.diff_skin_folder(sdir, tmp, resolver=res)
            self.assertEqual(out["default_screen"], "PlayerReport")
            self.assertEqual(out["source"]["label"], "Sample-Skin v1.0.2")
            self.assertIn("PlayerReport", out["by_screen"])
            self.assertEqual(len(out["by_screen"]["PlayerReport"]["composition"]), 2)
            self.assertIn(skin_diff.NOT_TIED, out["by_screen"])
            self.assertEqual(out["by_screen"][skin_diff.NOT_TIED]["navigation"][0]["source_label"], "Sample-Skin v1.0.2")


if __name__ == "__main__":
    unittest.main()
