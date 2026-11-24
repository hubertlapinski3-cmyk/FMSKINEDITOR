"""Stage 4D: typed asset adapters (adapters.py), the build plan and the D1/D2 policy (buildplan.py), the schema 2
build manifest (manifest.py) and the structural diff (bundlediff.py). Logic tests use synthetic geometry, synthetic
registry content and the committed synthetic bundle (data/selftest/roundtrip.unity3d): no game file is read or
written. The Stage 3 regression scenarios (a real composition edit through the whole build path) run on copies of the
archived set-C bundles plus the imported layout dump and skip when either is absent."""
import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from skin_editor import adapters, buildplan, bundles, config, layout_dump, manifest as manifest_mod, bundlediff, placement
from skin_editor import project as project_mod
from skin_editor import registry as registry_mod
from skin_editor.api import rpc

from test_api import close_logs, engine
from test_inventory import FIXTURE, SETC

REAL_DUMP = Path.home() / "AppData" / "Local" / "FM27SkinEditor" / "layout" / "current.json"


def cell(comp, idx, eid, x, y, w=4, h=2):
    return {"composition": comp, "cell_index": idx, "element_id": eid, "x": x, "y": y, "w": w, "h": h,
            "flags": [], "min_w": 1, "max_w": 0, "min_h": 1, "max_h": 0}


def dump(comp_rec, cells):
    return {"meta": {"index_fingerprint": "fp1", "game_build": "27.test"}, "compositions": [comp_rec], "cells": cells,
            "cell_configs": [], "tiles": []}


def grid(comp_rec, cells):
    return placement.Grid(dump(comp_rec, cells))


COMP = {"name": "C", "preset_w": 30, "preset_h": 16, "bundle": "ui-tileslayouts_assets_all.bundle", "path_id": 123}


def move(idx, cell_id, to, comp="C", path_id="123"):
    return {"op": "move-cell", "bundle": "ui-tileslayouts_assets_all.bundle", "path_id": str(path_id),
            "composition": comp, "cell_index": idx, "cell_id": cell_id,
            "from": {"x": 0, "y": 0}, "to": dict(to)}


class TestAdapterFramework(unittest.TestCase):
    def test_identify_is_structural_never_a_name(self):
        f = adapters.find
        self.assertIsInstance(f("MonoBehaviour", {"m_Rules": []}), adapters.StyleSheetAdapter)
        self.assertIsInstance(f("MonoBehaviour", {"m_gridComponents": []}), adapters.CompositionAdapter)
        self.assertIsInstance(f("Texture2D", {}), adapters.TextureAdapter)
        self.assertIsInstance(f("Sprite", {}), adapters.SpriteAdapter)
        self.assertIsInstance(f("Font", {}), adapters.FontAdapter)
        self.assertIsNone(f("MonoBehaviour", {"m_Name": "SquadComposition-Standard"}))       # a name is never an identity
        self.assertIsNone(f("TextAsset", {}))

    def test_every_adapter_declares_its_surface_and_its_limits(self):
        for a in adapters.all_adapters():
            info = a.info()
            self.assertIn(info["evidence"]["status"], ("Confirmed", "Partial", "Unsupported", "Runtime-proven (position edits)"), a.name)
            self.assertTrue(info["evidence"]["basis"] and info["evidence"]["stages"], a.name)
            self.assertTrue(info["limitations"], a.name)
            for p in info["properties"]:
                self.assertTrue(p["name"] and p["evidence"], (a.name, p))

    def test_no_adapter_can_apply_a_reference_or_identity_edit_today(self):
        for a in adapters.all_adapters():
            self.assertEqual(a.edit_kind, "value", a.name)

    def test_by_name(self):
        self.assertEqual(adapters.by_name("composition").name, "composition")
        with self.assertRaises(KeyError):
            adapters.by_name("nope")

    def test_findings_reject_a_bad_level(self):
        with self.assertRaises(ValueError):
            adapters.finding("bang", "x", "y")


class TestCompositionValidation(unittest.TestCase):
    """D2: overlap is an error by default, names both tiles and the region, and only an explicit recorded override
    passes it. The existing bounds and grid checks (placement.py) keep running unchanged."""

    def setUp(self):
        self.g = grid(COMP, [cell("C", 0, "A", 0, 0), cell("C", 1, "B", 11, 0), cell("C", 2, "Free", 20, 0)])

    def v(self, moves, **ctx):
        return adapters.by_name("composition").validate(
            {"composition": "C", "bundle": "ui-tileslayouts_assets_all.bundle", "path_id": "123", "moves": moves},
            dict({"grid": self.g, "confirmed": set(), "allow_overlap": False}, **ctx))

    def test_a_clean_move_has_no_findings(self):
        self.assertEqual(self.v([move(0, "A", {"x": 5, "y": 0})]), [])

    def test_an_overlap_is_an_error_that_names_both_tiles_and_the_region(self):
        f = self.v([move(0, "A", {"x": 10, "y": 0})])                       # A at 10..14 overlaps B at 11..15
        self.assertEqual(len(f), 1)
        self.assertEqual(f[0]["code"], "tile_overlap")
        self.assertEqual(f[0]["level"], "error")
        self.assertEqual(f[0]["region"], {"x": 11, "y": 0, "w": 3, "h": 2})
        self.assertEqual([t["cell_index"] for t in f[0]["tiles"]], [0, 1])
        self.assertFalse(f[0]["override"])

    def test_two_edited_cells_colliding_report_the_pair_once(self):
        f = self.v([move(0, "A", {"x": 10, "y": 0}), move(1, "B", {"x": 10, "y": 0})])
        self.assertEqual([x["code"] for x in f], ["tile_overlap"])          # one finding per pair, not two

    def test_the_build_parameter_override_is_recorded(self):
        f = self.v([move(0, "A", {"x": 10, "y": 0})], allow_overlap=True)
        self.assertEqual((f[0]["level"], f[0]["override"], f[0]["override_source"]), ("warning", True, "build_parameter"))

    def test_an_edit_time_confirmation_is_an_override_too_and_says_so(self):
        f = self.v([move(0, "A", {"x": 10, "y": 0})], confirmed={("C#0", "C#1")})
        self.assertEqual((f[0]["level"], f[0]["override"], f[0]["override_source"]), ("warning", True, "edit_time_confirmation"))

    def test_the_existing_bounds_checks_still_block(self):
        f = self.v([move(0, "A", {"x": 27, "y": 0})])                      # x+w=31 exceeds the 30-wide grid
        self.assertEqual([x["code"] for x in f], ["cell_invalid"])
        self.assertIn("exceed the composition grid", f[0]["message"])
        self.assertEqual(self.v([move(0, "A", {"x": -1, "y": 0})])[0]["code"], "cell_invalid")

    def test_a_missing_composition_or_geometry_is_an_error_never_a_silent_pass(self):
        self.assertEqual(self.v([move(0, "A", {"x": 5, "y": 0})], grid=None)[0]["code"], "no_geometry")
        f = adapters.by_name("composition").validate({"composition": "Gone", "path_id": "9", "moves": [move(0, "A", {"x": 5, "y": 0})]},
                                                    {"grid": self.g, "confirmed": set(), "allow_overlap": False})
        self.assertEqual(f[0]["code"], "cell_invalid")
        self.assertIn("is not in the dump", f[0]["message"])

    def test_describe_lists_positions_and_says_sizes_come_from_the_dump(self):
        d = adapters.by_name("composition").describe("MonoBehaviour",
                                                    {"m_Name": "C", "m_gridComponents": [
                                                        {"m_elementID": "A", "m_location": {"x": 1, "y": 2}}]})
        self.assertEqual((d["cells"], d["positions"][0]["x"], d["positions"][0]["element_id"]), (1, 1, "A"))
        self.assertIn("sizes derive", d["note"])


class TestPolicy(unittest.TestCase):
    """D1 exactly as approved: value edits build and are reported; identity/reference block until resolved (an
    explicit override passes and is recorded); an unclassifiable edit blocks with no override; buildability and
    installation readiness are separate states."""

    def row(self, kind, status):
        return {"asset": {"bundle": "b.bundle"}, "edit_kind": kind, "status": status, "unknown": [], "reason": None}

    def test_a_value_edit_with_an_unknown_graph_still_builds_with_uncertain_readiness(self):
        p = buildplan.policy([], [self.row("value", "unknown")])
        self.assertEqual((p["buildable"], p["installation_readiness"]), (True, "uncertain"))
        p = buildplan.policy([], [self.row("value", "not_evaluated")])
        self.assertEqual((p["buildable"], p["installation_readiness"]), (True, "uncertain"))

    def test_a_value_edit_with_a_complete_graph_is_ready(self):
        p = buildplan.policy([], [self.row("value", "complete")])
        self.assertEqual((p["buildable"], p["installation_readiness"]), (True, "ready"))

    def test_identity_and_reference_block_until_resolved(self):
        for kind in ("identity", "reference"):
            p = buildplan.policy([], [self.row(kind, "unknown")])
            self.assertFalse(p["buildable"])
            self.assertEqual(p["blocked"][0]["code"], "impact_unresolved")
            p = buildplan.policy([], [self.row(kind, "not_evaluated")])
            self.assertFalse(p["buildable"])

    def test_a_resolved_identity_or_reference_edit_is_not_blocked_by_the_policy(self):
        for kind in ("identity", "reference"):
            p = buildplan.policy([], [self.row(kind, "complete")])
            self.assertTrue(p["buildable"], kind)

    def test_the_explicit_override_passes_a_blocked_impact_and_is_recorded(self):
        p = buildplan.policy([], [self.row("identity", "unknown")], allow_unknown_impact=True)
        self.assertTrue(p["buildable"])
        self.assertTrue(p["overrides"]["allow_unknown_impact"])

    def test_an_unclassifiable_edit_blocks_with_no_override(self):
        p = buildplan.policy([], [self.row("nonsense", "complete")], allow_unknown_impact=True)
        self.assertFalse(p["buildable"])
        self.assertEqual(p["blocked"][0]["code"], "unknown_edit_kind")

    def test_an_adapter_error_blocks_and_ready_becomes_blocked(self):
        f = [adapters.finding("error", "tile_overlap", "tiles would overlap")]
        p = buildplan.policy(f, [self.row("value", "complete")])
        self.assertEqual((p["buildable"], p["installation_readiness"]), (False, "blocked"))


class TestPlan(unittest.TestCase):
    """The typed plan over a synthetic workspace: collection per section, adapter validation wired in, the impact
    rows against a real registry (graph unbuilt -> honest 'unknown'), and the review's separate states."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="fm27se-plan-"))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.ws = config.Workspace(self.tmp / "ws")
        self.ws.vanilla.mkdir(parents=True, exist_ok=True)
        for n in list(bundles.STYLE_BUNDLES) + ["ui-tileslayouts_assets_all.bundle"]:
            shutil.copyfile(FIXTURE, self.ws.vanilla / n)
        (self.ws.vanilla / "manifest.json").write_text(json.dumps(
            {"schema": 1, "game_build": "27.test", "source": "test",
             "files": {n: {"sha256": bundles.sha256(self.ws.vanilla / n)} for n in bundles.STYLE_BUNDLES},
             "image_files": {"ui-tileslayouts_assets_all.bundle": {"sha256": bundles.sha256(self.ws.vanilla / "ui-tileslayouts_assets_all.bundle")}},
             "reference": {"bundles": {}, "catalog_hash": "c"}}), encoding="utf-8")
        self.p = project_mod.new("demo", "27.test")

    def grid_and_placements(self):
        g = grid(COMP, [cell("C", 0, "A", 0, 0), cell("C", 1, "B", 11, 0)])
        return mock.patch("skin_editor.placement._grid", return_value=g), \
               mock.patch("skin_editor.placement._read", return_value={"edits": []})

    def test_sheet_ops_cover_the_snapshot_and_report_a_missing_sheet(self):
        self.p["scoped_rules"] = [{"sheet": "Nope", "selector": ".x", "props": {"color": "#112233"}}]
        g = buildplan.collect(self.ws, self.p)
        missing = g[bundles.STYLE_BUNDLES[0]]["sections"]["sheet_spec"]["missing"]
        self.assertEqual(missing, ["Nope"])                                 # reported, never silently dropped
        p1, p2 = self.grid_and_placements()
        with p1, p2:
            plan = buildplan.review(self.ws, self.p)
        self.assertEqual([f["code"] for f in plan["findings"]], ["sheet_not_in_bundle"] * 2)
        self.assertEqual(plan["findings"][0]["level"], "warning")
        self.assertTrue(plan["impact"]["buildable"])                        # the old build behaviour: a warning, not a refusal
        self.p["scoped_rules"] = []
        self.p["token_overrides"] = [{"token": "--x", "value": {"rgb": "#112233", "a": 1.0}}]
        g = buildplan.collect(self.ws, self.p)
        self.assertEqual(sorted(g), sorted(bundles.STYLE_BUNDLES))
        self.assertTrue(g[bundles.STYLE_BUNDLES[0]]["sections"]["sheet_spec"]["touched_all"])

    def test_a_tile_move_is_collected_and_validated(self):
        p1, p2 = self.grid_and_placements()
        with p1, p2:
            plan = buildplan.review(self.ws, self.p, tile_ops=[move(0, "A", {"x": 5, "y": 0})])
        b = plan["bundles"]["ui-tileslayouts_assets_all.bundle"]
        self.assertEqual(b["adapter"], "composition")
        self.assertEqual(b["sections"], ["tile_moves"])
        self.assertEqual(b["ops"][0]["ops"]["moves"], [{"cell_index": 0, "cell_id": "A", "to": {"x": 5, "y": 0}}])
        self.assertEqual(b["ops"][0]["build_step"], "tiles.apply_ops")
        self.assertEqual(b["ops"][0]["evidence"]["status"], "Runtime-proven (position edits)")
        self.assertTrue(plan["impact"]["buildable"])
        self.assertEqual(plan["findings"], [])

    def test_an_overlapping_tile_move_blocks_the_review(self):
        p1, p2 = self.grid_and_placements()
        with p1, p2:
            plan = buildplan.review(self.ws, self.p, tile_ops=[move(0, "A", {"x": 10, "y": 0})])
        self.assertFalse(plan["impact"]["buildable"])
        self.assertEqual(plan["blocked"][0]["code"], "tile_overlap")
        with p1, p2:
            plan = buildplan.review(self.ws, self.p, tile_ops=[move(0, "A", {"x": 10, "y": 0})], allow_overlap=True)
        self.assertTrue(plan["impact"]["buildable"])
        self.assertTrue(plan["overrides"]["allow_overlap"])
        self.assertEqual(plan["overrides"]["allow_overlap_source"], "build_parameter")

    def test_the_impact_rows_use_the_registry_and_never_guess(self):
        reg = registry_mod.Registry(self.tmp / "r.sqlite", "iid")
        rec = {"rel_path": "ui-tileslayouts_assets_all.bundle", "abs_path": "x", "filename": "b", "size": 1, "mtime_ns": 1,
               "sha256": "s", "crc32": "0", "cab": "CAB-" + "a" * 32, "unity_version": "t", "kind": "ui-tiles", "object_count": 1,
               "type_counts": {}, "dependencies": [], "externals": [], "state": "valid", "error": None,
               "scanned_utc": "t", "verified_utc": "t"}
        reg.put_bundle(rec, [{"cab": rec["cab"], "path_id": "123", "class_id": 114, "type": "MonoBehaviour",
                              "name": "C", "guid": None, "role": "GridComposition"}])
        p1, p2 = self.grid_and_placements()
        with p1, p2:
            plan = buildplan.review(self.ws, self.p, reg=reg, tile_ops=[move(0, "A", {"x": 5, "y": 0})])
        row = plan["impact"]["per_asset"][0]
        self.assertEqual(row["asset"]["cab"], rec["cab"])                       # the CAB came from the inventory, not a guess
        self.assertEqual(row["edit_kind"], "value")
        self.assertEqual(row["status"], "complete")                            # a 1-bundle inventory: nothing can be unknown, and it still builds
        self.assertEqual(plan["impact"]["installation_readiness"], "ready")
        self.assertTrue(plan["impact"]["buildable"])

    def test_without_a_registry_the_impact_is_reported_not_evaluated(self):
        p1, p2 = self.grid_and_placements()
        with p1, p2:
            plan = buildplan.review(self.ws, self.p, tile_ops=[move(0, "A", {"x": 5, "y": 0})])
        row = plan["impact"]["per_asset"][0]
        self.assertEqual((row["status"], row["asset"]["cab"]), ("not_evaluated", None))
        self.assertIn("no installation inventory", row["reason"])
        self.assertFalse(plan["impact"]["evaluated"])

    def test_an_empty_project_reviews_to_an_empty_ready_plan(self):
        plan = buildplan.review(self.ws, self.p)
        self.assertEqual((plan["bundles"], plan["blocked"]), ({}, []))
        self.assertEqual((plan["impact"]["buildable"], plan["impact"]["installation_readiness"]), (True, "ready"))


class TestDiffAndManifest(unittest.TestCase):
    """bundlediff over the synthetic bundle, and the schema 2 manifest: schema 1 keys unchanged, schema 1 packages
    still readable, every output carrying hashes, CRC-32 and the three difference layers."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="fm27se-man-"))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)

    def modified(self):
        import UnityPy
        env = UnityPy.load(str(FIXTURE))
        obj = next(o for o in env.objects)
        t = obj.read_typetree()
        t["m_Script"] = b"changed".decode("latin1")
        obj.save_typetree(t)
        out = self.tmp / "modified.unity3d"
        out.write_bytes(env.file.save(packer="original"))
        return out

    def test_pptr_multiset(self):
        tree = {"a": {"m_FileID": 0, "m_PathID": 5}, "b": [{"m_FileID": 1, "m_PathID": 9}, {"m_FileID": 1, "m_PathID": 9}]}
        self.assertEqual(bundlediff.pptr_multiset(tree), [(0, 5), (1, 9), (1, 9)])

    def test_compare_separates_the_three_layers(self):
        out = self.modified()
        d = bundlediff.compare(FIXTURE, out)
        self.assertFalse(d["byte"]["identical"])
        self.assertIn("byte identity is not required", d["byte"]["note"])
        self.assertEqual(len(d["object"]["changed_objects"]), 1)
        self.assertEqual(d["object"]["changed_objects"][0]["path_id"], "1")
        self.assertTrue(d["object"]["object_set_equal"])
        self.assertTrue(d["structure"]["type_counts_equal"])
        self.assertEqual(d["structure"]["pptr_multiset"]["objects_with_mismatch"], [])
        self.assertEqual(d["structure"]["deserialisation_errors_output"], [])
        self.assertEqual(d["structure"]["assetbundle_object"], "not readable in both files")   # the synthetic bundle has no AssetBundle object

    def test_an_output_record_carries_hashes_crc_and_diff(self):
        out = self.modified()
        rec = manifest_mod.output_record(FIXTURE, out, {"adapter": "texture"})
        self.assertEqual(rec["rel_path"], "modified.unity3d")
        self.assertNotEqual(rec["source_crc32"], rec["output_crc32"])
        self.assertEqual(len(rec["source_crc32"]), 8)
        self.assertEqual(rec["semantic"], {"adapter": "texture"})
        self.assertIsNone(rec["catalog_crc_status"])                        # no registry: not evaluated, never guessed

    def test_schema2_package_keeps_every_schema1_key_and_adds_the_sections(self):
        pkg1 = {"schema": 1, "id": "t", "project": "demo", "files": {"x.bundle": {"sha256": "a", "vanilla_sha256": "b"}},
                "gate": {"passed": True, "failures": [], "checked": {}}, "installable": True, "plan_digest": "d"}
        m = manifest_mod.build_manifest(self.ws_like(), project_mod.new("demo"),
                                        {"bundles": {}, "findings": [], "overrides": {}, "impact": {}},
                                        {"files": {}}, self.tmp, "t")
        m["impact"] = dict(m["impact"], buildable=True, installation_readiness="uncertain", evaluated=False)
        pkg2 = manifest_mod.schema2_package(pkg1, m)
        for k in pkg1:
            if k != "schema":                                                # schema is the one field that changes
                self.assertEqual(pkg2[k], pkg1[k], k)
        self.assertEqual(pkg2["schema"], 2)
        self.assertEqual(pkg2["manifest_file"], "build-manifest.json")
        self.assertIn("installation_readiness", pkg2["impact"])

    def test_read_package_accepts_schema_1_and_2_and_refuses_anything_else(self):
        p = self.tmp / "p.json"
        p.write_text(json.dumps({"schema": 1, "id": "x"}), encoding="utf-8")
        self.assertEqual(manifest_mod.read_package(p)["schema"], 1)
        p.write_text(json.dumps({"schema": 2, "id": "x"}), encoding="utf-8")
        self.assertEqual(manifest_mod.read_package(p)["schema"], 2)
        p.write_text(json.dumps({"schema": 3}), encoding="utf-8")
        with self.assertRaises(ValueError):
            manifest_mod.read_package(p)

    def ws_like(self):
        ws = mock.Mock()
        ws.vanilla = FIXTURE.parent
        ws.vanilla_manifest = lambda: {"game_build": "27.test", "reference": {"catalog_hash": "c"}}
        return ws


class TestEngineMethods(unittest.TestCase):
    """The API surface: the adapter table, a read through an adapter (read only), a review without writing."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.addCleanup(self.tmp.cleanup)
        self.addCleanup(close_logs)
        self.e = engine(self.tmp.name)
        shutil.copyfile(FIXTURE, self.e.ws.vanilla / "x.bundle")

    def call(self, method, params=None):
        r = json.loads(rpc.handle(self.e, json.dumps({"jsonrpc": "2.0", "method": method, "id": 1, "params": params or {}})))
        self.assertNotIn("error", r, r)
        return r["result"]

    def test_the_adapter_table_lists_all_five_with_their_evidence(self):
        a = self.call("edit.adapters")["adapters"]
        self.assertEqual([x["name"] for x in a], ["stylesheet", "composition", "texture", "sprite", "font"])
        self.assertTrue(all(x["limitations"] and x["evidence"]["stages"] for x in a))

    def test_a_read_is_read_only_and_says_when_no_adapter_owns_the_object(self):
        r = self.call("edit.read", {"bundle": "x.bundle", "path_id": "1"})
        self.assertIsNone(r["adapter"])
        self.assertIn("no adapter owns", r["note"])
        r = json.loads(rpc.handle(self.e, json.dumps({"jsonrpc": "2.0", "method": "edit.read", "id": 1,
                                                      "params": {"bundle": "x.bundle", "path_id": "999"}})))
        self.assertEqual(r["error"]["code"], -32004)
        self.assertIn("isn't in that file any more", r["error"]["data"]["plain"])

    def test_a_read_of_a_bundle_that_exists_nowhere_is_a_clean_not_found(self):
        r = json.loads(rpc.handle(self.e, json.dumps({"jsonrpc": "2.0", "method": "edit.read", "id": 1,
                                                      "params": {"bundle": "nope.bundle", "path_id": "1"}})))
        self.assertEqual(r["error"]["code"], -32004)
        self.assertIn("can't see that file", r["error"]["data"]["plain"])

    def test_an_empty_project_reviews_to_a_ready_plan(self):
        self.call("project.create_folder", {"name": "demo", "target": "bundles"})
        r = self.call("build.review", {"project": "demo"})
        self.assertEqual(r["bundles"], {})
        self.assertEqual((r["impact"]["buildable"], r["impact"]["installation_readiness"]), (True, "ready"))

    def test_the_build_method_accepts_the_two_recorded_overrides(self):
        m = [x for x in rpc.methods().values() if x.name == "build.bundles"][0]
        self.assertIn("allow_overlap", m.schema)
        self.assertIn("allow_unknown_impact", m.schema)


@unittest.skipUnless(SETC.is_dir() and REAL_DUMP.is_file(), "archived set-C bundles or the imported layout dump not present")
class TestStage3Regression(unittest.TestCase):
    """The Stage 3F-style scenario through the WHOLE build path on copies of the archived bundles: a real composition
    move from the real dump, stored as a placement edit, built by patcher.build; a colliding move is refused by the
    overlap gate and passes only through a recorded override (the build parameter, or the edit-time confirmation)."""

    NAME = "ui-tileslayouts_assets_all.bundle"

    def setUp(self):
        from skin_editor import index_styles, layout_dump
        self.tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.addCleanup(self.tmp.cleanup)
        self.addCleanup(close_logs)
        self.ws = config.Workspace(Path(self.tmp.name) / "ws")
        for n in list(bundles.STYLE_BUNDLES) + [self.NAME]:
            shutil.copyfile(SETC / n, self.ws.vanilla / n)
        (self.ws.vanilla / "manifest.json").write_text(json.dumps(
            {"schema": 1, "game_build": "27.1.0.2505117", "source": "test",
             "files": {n: {"sha256": bundles.sha256(self.ws.vanilla / n)} for n in bundles.STYLE_BUNDLES},
             "image_files": {self.NAME: {"sha256": bundles.sha256(self.ws.vanilla / self.NAME)}},
             "reference": {"bundles": {}, "catalog_hash": "c"}}), encoding="utf-8")
        layout_dump.import_dump(self.ws, str(REAL_DUMP))
        # the dump's freshness gate compares against the installed game's reference hashes; it guards WRITING to the
        # game, which this test never does, and a temporary workspace has no snapshot (as in test_tile_move_e2e)
        p = mock.patch("skin_editor.placement.can_edit", return_value={"ok": True, "why": ""})
        p.start()
        self.addCleanup(p.stop)
        self.index = index_styles.build(self.ws, lambda m, f: None)
        self.p = project_mod.new("demo", "27.1.0.2505117")
        project_mod.set_experimental_bundle_layout_edits(self.p, True)

    def find_move(self, want_collision):
        """A move of a real SquadComposition-Standard cell that either collides with a sibling or provably does not."""
        from skin_editor import layout_dump
        d = layout_dump.load(self.ws)
        g = placement.Grid(d)
        for c in (x for x in d["cells"] if x["composition"] == "SquadComposition-Standard"):
            for dx in (1, 2, 4, -1, -2, -4):
                to = {"x": c["x"] + dx, "y": c["y"]}
                if to["x"] < 0:
                    continue
                r = placement.check(g, {"composition": c["composition"], "cell_index": c["cell_index"],
                                        "geometry": {"x": to["x"], "y": to["y"], "w": c["w"], "h": c["h"]}}, [])
                if not r["blocks"] and bool(r["collisions"]) == want_collision:
                    return c, to, r["collisions"]
        return None, None, None

    def store(self, c, to, collisions, confirm):
        from skin_editor import placement as pl
        return pl.add(self.ws, "demo", {"composition": c["composition"], "cell_index": c["cell_index"],
                                        "geometry": {"x": to["x"], "y": to["y"], "w": c["w"], "h": c["h"]}},
                      confirm=confirm)

    def test_a_clean_real_move_builds_and_the_manifest_records_one_changed_object(self):
        from skin_editor import patcher, tiles
        c, to, _ = self.find_move(False)
        self.assertIsNotNone(c, "no collision-free move found in the dump")
        self.store(c, to, [], confirm=False)
        ops = tiles.ops_for(self.ws, "demo")
        self.assertEqual(len(ops), 1)
        plan = buildplan.review(self.ws, self.p)
        self.assertEqual(plan["findings"], [])
        rep = patcher.build(self.p, self.ws, self.index)
        self.assertEqual(sum(1 for f in rep["files"].values() if f["changed"]), 1)
        man = json.loads((Path(rep["dir"]) / "build-manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(man["schema"], 2)
        out = man["outputs"][0]
        self.assertEqual(out["rel_path"], self.NAME)
        self.assertEqual(len(out["diff"]["object"]["changed_objects"]), 1)       # only the composition object
        self.assertTrue(out["diff"]["object"]["object_set_equal"])
        self.assertEqual(len(out["diff"]["structure"]["pptr_multiset"]["objects_with_mismatch"]), 0)
        self.assertNotEqual(out["source_crc32"], out["output_crc32"])
        self.assertEqual(man["impact"]["installation_readiness"], "uncertain")   # no registry in the temp workspace: honest
        pkg = json.loads((Path(rep["dir"]) / "package.json").read_text(encoding="utf-8"))
        self.assertEqual(pkg["schema"], 2)
        self.assertIn("files", pkg)                                            # the schema 1 keys are still there
        self.assertTrue(pkg["installable"])

    def test_a_colliding_real_move_needs_a_recorded_override_to_build(self):
        from skin_editor import patcher, placement as pl, tiles
        c, to, coll = self.find_move(True)
        self.assertIsNotNone(c, "no colliding move found in the dump")
        # the raw op, validated on the real dump geometry without any confirmation, is blocked by the gate
        op = [{"op": "move-cell", "bundle": self.NAME, "path_id": str(next(x for x in layout_dump.load(self.ws)["compositions"]
                          if x["name"] == c["composition"])["path_id"]),
               "composition": c["composition"], "cell_index": c["cell_index"], "cell_id": c["element_id"],
               "from": {"x": c["x"], "y": c["y"]}, "to": dict(to)}]
        plan = buildplan.review(self.ws, self.p, tile_ops=tiles.validate_ops(op))
        self.assertEqual(plan["blocked"][0]["code"], "tile_overlap")
        self.assertEqual(plan["blocked"][0]["region"]["w"] > 0, True)
        # through the placement store the collision needs an explicit confirm to be stored at all; that confirmation
        # is the recorded override the build honours, and the manifest says where it came from
        self.store(c, to, coll, confirm=True)
        rep = patcher.build(self.p, self.ws, self.index)
        man = json.loads((Path(rep["dir"]) / "build-manifest.json").read_text(encoding="utf-8"))
        self.assertTrue(man["overrides"]["allow_overlap"])
        self.assertEqual(man["overrides"]["allow_overlap_source"], "edit_time_confirmation")
        f = [x for x in man["validation"] if x["code"] == "tile_overlap"][0]
        self.assertEqual(len(f["tiles"]), 2)
        self.assertIn("region", f)
        # the same collision, allowed by the build parameter instead, records that source
        pl.remove(self.ws, "demo", pl.load(self.ws, "demo")["edits"][0]["id"])
        self.store(c, to, coll, confirm=True)
        rep = patcher.build(self.p, self.ws, self.index, allow_overlap=True)
        man = json.loads((Path(rep["dir"]) / "build-manifest.json").read_text(encoding="utf-8"))
        self.assertTrue(man["overrides"]["allow_overlap"])
        self.assertEqual(man["overrides"]["allow_overlap_source"], "build_parameter")
        # a stored edit whose confirmation is taken away never silently builds: the placement revalidation marks it
        # stale first, and a stale edit is not built at all (that is the earlier line of defence, placement.py)
        doc = json.loads(Path(pl._path(self.ws, "demo")).read_text(encoding="utf-8"))
        doc["edits"][0]["confirmed_collisions"] = []
        Path(pl._path(self.ws, "demo")).write_text(json.dumps(doc), encoding="utf-8")
        loaded = pl.load(self.ws, "demo")
        self.assertEqual(loaded["edits"][0]["state"], "stale")
        self.assertEqual(tiles.ops_for(self.ws, "demo"), [])


if __name__ == "__main__":
    unittest.main()
