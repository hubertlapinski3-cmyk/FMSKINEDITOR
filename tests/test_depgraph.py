"""Stage 4C: asset dependency graph (skin_editor/depgraph.py, graphview.py, the registry's graph tables). Logic tests use synthetic registry content and the committed synthetic
bundle (no game file); the Stage 2D / Stage 3 relationship tests copy a few archived set-C bundles into a temp folder and skip when the archive is absent."""
import json
import os
import shutil
import sqlite3
import tempfile
import threading
import unittest
from pathlib import Path

from skin_editor import config, depgraph, gameinstall, graphview, inventory, registry
from tests.test_inventory import FIXTURE, make_install, tree_hashes

SETC = Path(os.environ.get("FM27SE_SETC", r"__absent_fixture_path__"))


# ---------------------------------------------------------------- synthetic registry content
def rec(rel, cab, deps=(), externals=(), kind="ui-x", sha=None, state="valid"):
    return {"rel_path": rel, "abs_path": rel, "filename": rel, "size": 1, "mtime_ns": 1, "sha256": sha or ("sha-" + rel), "crc32": "0", "cab": cab, "unity_version": "t", "kind": kind,
            "object_count": 1, "type_counts": {}, "dependencies": list(deps), "externals": list(externals), "state": state, "error": None, "scanned_utc": "t", "verified_utc": "t"}


def asset(cab, pid, typ="MonoBehaviour", name=None, guid=None):
    return {"cab": cab, "path_id": str(pid), "class_id": 114, "type": typ, "name": name or "a%s" % pid, "guid": guid}


def E(bundle, cab, pid, kind, **kw):
    e = {"src_bundle": bundle, "src_cab": cab, "src_path_id": str(pid), "kind": kind, "relation": None, "t_file_id": -1, "t_path_id": "", "t_guid": "", "t_cab": "", "direct": 1, "count": 1,
         "provenance": kw.pop("prov", "f"), "samples": None}
    e.update(kw)
    e["samples"] = json.dumps([e["provenance"]])
    return e


def pptr(bundle, cab, pid, file_id, target_pid, prov="ref"):
    return E(bundle, cab, pid, "pptr", t_file_id=file_id, t_path_id=str(target_pid), prov=prov)


def guid(bundle, cab, pid, g, prov="ref"):
    return E(bundle, cab, pid, "guid_reference", t_guid=g, prov=prov)


class Reg(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="fm27se-graph-"))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.reg = registry.Registry(self.tmp / "r.sqlite", "iid")

    def add(self, r, assets=(), edges=None, roles=None, state="built"):
        self.reg.put_bundle(r, list(assets))
        if edges is not None:
            self.reg.replace_bundle_graph(r["rel_path"], r["sha256"], edges, roles or {}, state)

    def edges(self, **where):
        with self.reg._db() as db:
            q = "SELECT * FROM edges" + (" WHERE " + " AND ".join("%s=?" % k for k in where) if where else "")
            return [dict(r) for r in db.execute(q, list(where.values()))]


class TestExtraction(unittest.TestCase):
    def test_pptr_and_guid_with_provenance_and_collapse(self):
        tree = {"m_Script": {"m_FileID": 1, "m_PathID": 77}, "m_GameObject": {"m_FileID": 0, "m_PathID": 0}, "m_Name": "x",
                "a": {"m_FileID": 0, "m_PathID": 5}, "b": [{"m_FileID": 2, "m_PathID": 9}, {"m_FileID": 2, "m_PathID": 9}, {"m_FileID": 0, "m_PathID": 0}],
                "ref": {"m_AssetGUID": "ABCDEF00000000000000000000000001", "m_SubObjectName": "", "m_SubObjectType": ""},
                "empty": {"m_AssetGUID": ""}, "zero": {"m_AssetGUID": "0" * 32}, "deep": {"x": [{"y": {"m_FileID": 0, "m_PathID": 5}}]}}
        refs, trunc = depgraph.extract_refs(tree)
        self.assertFalse(trunc)
        self.assertEqual(set(refs), {("pptr", 0, "5", ""), ("pptr", 2, "9", ""), ("guid_reference", -1, "", "abcdef00000000000000000000000001")})   # script, owner, null, empty and zero GUID skipped
        self.assertEqual(refs[("pptr", 2, "9", "")]["count"], 2)                       # identical references in one asset collapse into one edge with a count
        self.assertEqual(sorted(refs[("pptr", 0, "5", "")]["samples"]), ["a", "deep/x[0]/y"])
        self.assertEqual(refs[("guid_reference", -1, "", "abcdef00000000000000000000000001")]["samples"], ["ref"])

    def test_the_reference_limit_is_reported(self):
        tree = {"l": [{"m_FileID": 0, "m_PathID": i} for i in range(1, 30)]}
        refs, trunc = depgraph.extract_refs(tree, max_refs=10)
        self.assertTrue(trunc)
        self.assertEqual(len(refs), 10)

    def test_roles_come_from_the_object_own_fields(self):
        c = depgraph.classify_role
        self.assertEqual(c("MonoBehaviour", {"m_VisualTree": {}}), "VisualTreeAsset")
        self.assertEqual(c("MonoBehaviour", {"m_Rules": []}), "StyleSheet")
        self.assertEqual(c("MonoBehaviour", {"m_gridBreakpointCompositionData": {}}), "TileCompositionSet")
        self.assertEqual(c("MonoBehaviour", {"m_gridComponents": []}), "GridComposition")
        self.assertEqual(c("MonoBehaviour", {"m_panelDescription": {}}), "PanelDescription")
        self.assertIsNone(c("MonoBehaviour", {"m_Name": "SquadScreen"}))               # a name alone never gives a role
        self.assertEqual(c("Sprite", {}), "Sprite")

    def test_cab_names(self):
        self.assertEqual(depgraph.cab_of("archive:/CAB-EE9FB57EE732C9ABD565F5C4171F2BAD/CAB-ee9fb57ee732c9abd565f5c4171f2bad"), "cab-ee9fb57ee732c9abd565f5c4171f2bad")
        self.assertEqual(depgraph.cab_of("cab-3334bbe2d7ac7af32e86413e81ff46ff"), "cab-3334bbe2d7ac7af32e86413e81ff46ff")
        self.assertEqual(depgraph.cab_of("Library/unity default resources"), "")

    def test_the_field_role_hint_needs_a_known_field(self):
        self.assertEqual(depgraph.expected_role(["m_gridComponents[0]/m_gridElementConfigs[0]/AssetRef"]), "VisualTreeAsset")
        self.assertIsNone(depgraph.expected_role(["m_items[3]/Asset", "m_inputActionAsset"]))


class TestResolution(Reg):
    def setUp(self):
        super().setUp()
        self.A = "CAB-" + "a" * 32
        self.B = "CAB-" + "b" * 32
        self.add(rec("a.bundle", self.A, externals=["Library/unity default resources", "archive:/%s/%s" % (self.B, self.B)], deps=[self.B.lower()]),
                 [asset(self.A, 1), asset(self.A, 2)],
                 [pptr("a.bundle", self.A, 1, 0, 2, "same"), pptr("a.bundle", self.A, 1, 2, 10, "ext"), pptr("a.bundle", self.A, 1, 1, 99, "builtin"),
                  pptr("a.bundle", self.A, 1, 3, 5, "bad"), pptr("a.bundle", self.A, 1, 2, 777, "missing")] + depgraph.bundle_level_edges(rec("a.bundle", self.A, [self.B.lower()], ["Library/unity default resources", "archive:/%s/%s" % (self.B, self.B)])))
        self.add(rec("b.bundle", self.B), [asset(self.B, 10, name="target")], [])
        depgraph.resolve(self.reg)

    def by(self, prov):
        return [e for e in self.edges(src_bundle="a.bundle") if e["provenance"] == prov][0]

    def test_same_file_external_builtin_and_failures(self):
        s, x, b, bad, miss = self.by("same"), self.by("ext"), self.by("builtin"), self.by("bad"), self.by("missing")
        self.assertEqual((s["resolution"], s["dst_bundle"], s["dst_path_id"]), ("resolved", "a.bundle", "2"))
        self.assertEqual((x["resolution"], x["dst_bundle"], x["dst_cab"], x["dst_path_id"]), ("resolved", "b.bundle", self.B, "10"))      # file id 2 = externals[1]
        self.assertEqual((b["resolution"], b["reason"]), ("unresolved", "builtin_resource"))
        self.assertEqual((bad["resolution"], bad["reason"]), ("unresolved", "bad_file_id"))
        self.assertEqual((miss["resolution"], miss["reason"]), ("unresolved", "object_not_in_inventory"))     # the CAB is known, the object is not

    def test_unresolved_and_direct_flags_are_kept_not_dropped(self):
        self.assertEqual(len(self.edges(src_bundle="a.bundle", resolution="unresolved")), 4)         # 3 asset edges + the builtin external
        self.assertTrue(all(e["direct"] == 1 for e in self.edges()))

    def test_bundle_level_edges(self):
        d = [e for e in self.edges(src_bundle="a.bundle") if e["kind"] == "bundle_dependency"][0]
        self.assertEqual((d["resolution"], d["dst_bundle"], d["relation"]), ("resolved", "b.bundle", "bundle_dependency"))
        self.assertEqual(len([e for e in self.edges() if e["kind"] == "external_file" and e["resolution"] == "unresolved"]), 1)

    def test_missing_cab_is_unresolved_with_its_reason(self):
        self.add(rec("c.bundle", "CAB-" + "c" * 32, externals=["archive:/CAB-%s/CAB-%s" % ("d" * 32, "d" * 32)]), [asset("CAB-" + "c" * 32, 1)],
                 [pptr("c.bundle", "CAB-" + "c" * 32, 1, 1, 5, "gone")])
        depgraph.resolve(self.reg)
        e = [x for x in self.edges(src_bundle="c.bundle")][0]
        self.assertEqual((e["resolution"], e["reason"]), ("unresolved", "cab_not_in_inventory"))

    def test_the_same_cab_in_two_bundles_is_ambiguous_with_both_candidates(self):
        self.add(rec("b2.bundle", self.B), [asset(self.B, 10, name="twin")], [])
        depgraph.resolve(self.reg)
        x = self.by("ext")
        self.assertEqual(x["resolution"], "ambiguous")
        with self.reg._db() as db:
            c = sorted(r["bundle"] for r in db.execute("SELECT * FROM edge_candidates WHERE edge_id=?", (x["id"],)))
        self.assertEqual(c, ["b.bundle", "b2.bundle"])
        self.assertIsNone(x["dst_bundle"])                                                           # nothing is guessed

    def test_resolution_follows_the_inventory_without_rereading_bundles(self):
        self.reg.put_bundle(rec("b.bundle", self.B, state="valid"), [])                              # the target's assets vanish from the inventory
        counts = depgraph.resolve(self.reg)
        self.assertEqual(self.by("ext")["reason"], "cab_not_in_inventory")
        self.assertGreater(counts["unresolved"], 4)


class TestGuidResolution(Reg):
    def setUp(self):
        super().setUp()
        self.A, self.B = "CAB-" + "a" * 32, "CAB-" + "b" * 32
        g_pair, g_two, g_hint, g_one, g_none = ("%032x" % i for i in range(1, 6))
        # b.bundle: a layout (VTA 1) with its inline sheet (sheet 2) under one GUID; two unrelated MonoBehaviours under another; one single asset
        self.add(rec("b.bundle", self.B), [asset(self.B, 1, name="layout", guid=g_pair), asset(self.B, 2, name="inline", guid=g_pair),
                                          asset(self.B, 3, guid=g_two), asset(self.B, 4, guid=g_two), asset(self.B, 5, guid=g_hint), asset(self.B, 6, guid=g_hint), asset(self.B, 7, guid=g_one)],
                 [pptr("b.bundle", self.B, 1, 0, 2, "inlineSheet")], roles={(self.B, "1"): "VisualTreeAsset", (self.B, "2"): "StyleSheet", (self.B, "5"): "VisualTreeAsset", (self.B, "6"): "StyleSheet"})
        self.add(rec("a.bundle", self.A), [asset(self.A, 1)],
                 [guid("a.bundle", self.A, 1, g_pair, "m_panelDescription/uxml"), guid("a.bundle", self.A, 1, g_two, "x/Asset"), guid("a.bundle", self.A, 1, g_hint, "x/AssetRef"),
                  guid("a.bundle", self.A, 1, g_one, "x/y"), guid("a.bundle", self.A, 1, g_none, "x/z")])
        depgraph.resolve(self.reg)

    def e(self, prov):
        return [x for x in self.edges(src_bundle="a.bundle") if x["provenance"] == prov][0]

    def test_layout_pair_names_the_layout_from_the_inline_sheet_pointer(self):
        x = self.e("m_panelDescription/uxml")
        self.assertEqual((x["resolution"], x["dst_path_id"], x["basis"], x["relation"]), ("resolved", "1", "guid_container+layout_pair", "uxml_reference"))

    def test_two_unrelated_assets_stay_ambiguous_and_keep_candidates(self):
        x = self.e("x/Asset")
        self.assertEqual((x["resolution"], x["dst_bundle"]), ("ambiguous", None))
        with self.reg._db() as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM edge_candidates WHERE edge_id=?", (x["id"],)).fetchone()[0], 2)

    def test_a_field_hint_narrows_but_is_labelled_as_weaker(self):
        x = self.e("x/AssetRef")        # candidates 5 (VTA) and 6 (sheet), but 6 is NOT 5's inline sheet: no pair; the field says VisualTreeAsset
        self.assertEqual((x["resolution"], x["dst_path_id"], x["basis"]), ("resolved", "5", "guid_container+field_role_hint"))

    def test_single_and_missing_guid(self):
        self.assertEqual((self.e("x/y")["resolution"], self.e("x/y")["basis"]), ("resolved", "guid_container"))
        z = self.e("x/z")
        self.assertEqual((z["resolution"], z["reason"]), ("unresolved", "guid_not_in_inventory"))

    def test_ambiguous_referrers_are_found_by_used_by_through_their_candidates(self):
        r = depgraph.used_by(self.reg, "b.bundle", self.B, "3")["edges"]
        self.assertEqual([(e["resolution"], e.get("via_candidate")) for e in r], [("ambiguous", True)])


class TestQueries(Reg):
    def setUp(self):
        super().setUp()
        self.C = "CAB-" + "c" * 32
        c = self.C
        self.add(rec("g.bundle", c, deps=[]), [asset(c, i) for i in range(1, 6)],
                 [pptr("g.bundle", c, 1, 0, 2, "p"), pptr("g.bundle", c, 2, 0, 3, "p"), pptr("g.bundle", c, 3, 0, 1, "p"),      # cycle 1 -> 2 -> 3 -> 1
                  pptr("g.bundle", c, 4, 0, 4, "self"), pptr("g.bundle", c, 5, 0, 1, "p"), pptr("g.bundle", c, 5, 0, 2, "p")])
        depgraph.resolve(self.reg)

    def test_uses_and_used_by_are_the_same_edges(self):
        for src in "12345":
            for e in depgraph.uses(self.reg, "g.bundle", self.C, src)["edges"]:
                back = depgraph.used_by(self.reg, e["dst"]["bundle"], e["dst"]["cab"], e["dst"]["path_id"])["edges"]
                self.assertIn(e["id"], [b["id"] for b in back])

    def test_cycles_and_self_references_are_reported_not_followed_forever(self):
        r = depgraph.reachable(self.reg, "g.bundle", self.C, "5")
        self.assertEqual({n["path_id"] for n in r["nodes"]}, {"1", "2", "3", "5"})
        self.assertEqual(r["cycles"], [[("g.bundle", self.C, "1"), ("g.bundle", self.C, "2"), ("g.bundle", self.C, "3")]])
        s = depgraph.reachable(self.reg, "g.bundle", self.C, "4")
        self.assertEqual(s["cycles"], [[("g.bundle", self.C, "4")]])
        up = depgraph.reachable(self.reg, "g.bundle", self.C, "1", direction="used_by")
        self.assertIn(("g.bundle", self.C, "5"), [(n["bundle"], n["cab"], n["path_id"]) for n in up["nodes"]])

    def test_depth_and_node_limits_are_reported(self):
        r = depgraph.reachable(self.reg, "g.bundle", self.C, "5", max_depth=1)
        self.assertTrue(r["truncated"])
        r = depgraph.reachable(self.reg, "g.bundle", self.C, "5", max_nodes=2)
        self.assertTrue(r["truncated"])

    def test_the_unique_key_rejects_a_duplicate_and_the_bundle_keeps_its_previous_graph(self):
        before = len(self.edges(src_bundle="g.bundle"))
        dup = [pptr("g.bundle", self.C, 1, 0, 9, "x"), pptr("g.bundle", self.C, 1, 0, 9, "x")]
        with self.assertRaises(sqlite3.IntegrityError):
            self.reg.replace_bundle_graph("g.bundle", "sha-g.bundle", dup, {}, "built")
        self.assertEqual(len(self.edges(src_bundle="g.bundle")), before)       # one transaction: nothing was half replaced

    def test_derived_bundle_edges_are_marked_not_direct(self):
        D = "CAB-" + "d" * 32
        self.add(rec("h.bundle", D, externals=["archive:/%s/%s" % (self.C, self.C)]), [asset(D, 1)], [pptr("h.bundle", D, 1, 1, 1, "x")])
        depgraph.resolve(self.reg)
        out = depgraph.uses(self.reg, "h.bundle")["edges"]
        derived = [e for e in out if e["kind"] == "bundle_reference"]
        self.assertEqual([(e["direct"], e["dst"]["bundle"]) for e in derived], [(False, "g.bundle")])
        self.assertTrue(all(e["direct"] for e in out if e["kind"] != "bundle_reference"))
        up = depgraph.used_by(self.reg, "g.bundle")["edges"]
        self.assertEqual([(e["kind"], e["direct"], e["src"]["bundle"]) for e in up], [("bundle_reference", False, "h.bundle")])


class TestAffected(Reg):
    def setUp(self):
        super().setUp()
        self.A, self.B = "CAB-" + "a" * 32, "CAB-" + "b" * 32
        # target asset 1 in b.bundle (with a container GUID); a.bundle references it by PPtr (built); u.bundle names b's CAB but is unbuilt
        self.add(rec("b.bundle", self.B), [asset(self.B, 1, guid="%032x" % 9), asset(self.B, 2)], [])
        self.add(rec("a.bundle", self.A, externals=["archive:/%s/%s" % (self.B, self.B)]), [asset(self.A, 1)], [pptr("a.bundle", self.A, 1, 1, 1, "r")])
        self.add(rec("u.bundle", "CAB-" + "e" * 32, externals=["archive:/%s/%s" % (self.B, self.B)]), [asset("CAB-" + "e" * 32, 1)])
        depgraph.resolve(self.reg)

    def test_value_edit_rebuilds_only_the_own_bundle_and_lists_referrers_as_possible(self):
        r = depgraph.affected(self.reg, "b.bundle", self.B, "1", "value")
        self.assertEqual(r["rebuild_required"], ["b.bundle"])
        self.assertEqual(r["possibly_affected_at_runtime"], ["a.bundle"])
        self.assertEqual(r["unknown"], [])
        self.assertEqual(r["status"], "complete")

    def test_identity_edit_requires_the_resolved_referrers_and_names_what_is_unknown(self):
        r = depgraph.affected(self.reg, "b.bundle", self.B, "1", "identity")
        self.assertEqual(r["rebuild_required"], ["a.bundle", "b.bundle"])
        self.assertEqual(r["status"], "unknown")
        whats = {(u["what"], u.get("bundle")) for u in r["unknown"]}
        self.assertIn(("unread_bundle", "u.bundle"), whats)                                      # its externals name this CAB, its references were never read
        self.assertIn(("unread_bundles_for_guid_references", None), whats)                       # the asset has a container GUID and u.bundle is unbuilt

    def test_identity_is_complete_when_every_bundle_is_built_and_there_is_no_guid(self):
        self.reg.replace_bundle_graph("u.bundle", "sha-u.bundle", [], {}, "built")
        r = depgraph.affected(self.reg, "b.bundle", self.B, "2", "identity")               # asset 2 has no container GUID and nobody references it
        self.assertEqual((r["rebuild_required"], r["status"], r["unknown"]), (["b.bundle"], "complete", []))

    def test_ambiguous_referrers_are_unknown_never_assumed(self):
        g = "%032x" % 7
        self.add(rec("m.bundle", "CAB-" + "f" * 32), [asset("CAB-" + "f" * 32, 1, guid=g), asset("CAB-" + "f" * 32, 2, guid=g)], [])
        self.add(rec("n.bundle", "CAB-" + "9" * 32), [asset("CAB-" + "9" * 32, 1)], [guid("n.bundle", "CAB-" + "9" * 32, 1, g, "x/y")])
        depgraph.resolve(self.reg)
        r = depgraph.affected(self.reg, "m.bundle", "CAB-" + "f" * 32, "1", "identity")
        self.assertIn(("ambiguous_referrer", "n.bundle"), {(u["what"], u.get("bundle")) for u in r["unknown"]})
        self.assertNotIn("n.bundle", r["rebuild_required"])

    def test_reference_edit_needs_the_targets_to_decide_the_dependency_list(self):
        r = depgraph.affected(self.reg, "a.bundle", self.A, "1", "reference")
        self.assertEqual(r["unknown"][0]["what"], "new_targets_not_given")
        r = depgraph.affected(self.reg, "a.bundle", self.A, "1", "reference", [{"bundle": "b.bundle"}])
        self.assertEqual(r["rebuild_required"], ["a.bundle"])
        self.assertEqual(r["unknown"][0]["what"], "dependency_metadata_update")              # a.bundle's dependency list does not name b's CAB

    def test_input_checks(self):
        with self.assertRaises(ValueError):
            depgraph.affected(self.reg, "b.bundle", self.B, "1", "rename")
        with self.assertRaises(KeyError):
            depgraph.affected(self.reg, "b.bundle", self.B, "404", "value")


class TestBuild(Reg):
    """The incremental build with an injected extractor (no file is read)."""

    def setUp(self):
        super().setUp()
        self.calls = []
        for n in ("ui-1", "ui-2", "ui-3"):
            self.add(rec(n + ".bundle", "CAB-" + n.ljust(32, "0"), kind="ui-x"), [asset("CAB-" + n.ljust(32, "0"), 1)])
        self.add(rec("art.bundle", "CAB-" + "9" * 32, kind="art-x"), [asset("CAB-" + "9" * 32, 1)])

    def ex(self, r):
        self.calls.append(r["rel_path"])
        cab = r["cab"]
        return depgraph.bundle_level_edges(r) + [pptr(r["rel_path"], cab, 1, 0, 1, "self")], {(cab, "1"): "StyleSheet"}, []

    def build(self, **kw):
        return depgraph.build(self.reg, extractor=self.ex, **kw)

    def test_scope_ui_builds_assets_only_for_ui_bundles(self):
        s = self.build()
        self.assertEqual((s["built"], s["bundle_only"], s["failed"]), (3, 1, 0))
        self.assertEqual(sorted(self.calls), ["ui-1.bundle", "ui-2.bundle", "ui-3.bundle"])
        st = self.reg.graph_states()
        self.assertEqual(st["art.bundle"]["state"], "bundle_only")
        self.assertEqual(self.reg.get_asset("ui-1.bundle", "CAB-" + "ui-1".ljust(32, "0"), 1)["role"], "StyleSheet")

    def test_second_build_skips_everything_and_a_changed_hash_rebuilds_only_that_bundle(self):
        self.build()
        self.calls.clear()
        s = self.build()
        self.assertEqual((s["skipped"], s["built"], self.calls), (4, 0, []))
        r = rec("ui-2.bundle", "CAB-" + "ui-2".ljust(32, "0"), sha="NEW")
        self.reg.put_bundle(r, [asset(r["cab"], 1)])
        self.calls.clear()
        s = self.build()
        self.assertEqual((s["built"], s["skipped"], self.calls), (1, 3, ["ui-2.bundle"]))
        self.assertEqual(self.reg.graph_states()["ui-2.bundle"]["sha256"], "NEW")

    def test_rebuild_flag_and_widening_the_scope(self):
        self.build()
        self.calls.clear()
        self.build(rebuild=True)
        self.assertEqual(len(self.calls), 3)
        self.calls.clear()
        s = self.build(scope="all")                    # art.bundle was bundle_only; now in scope: built; the ui bundles stay skipped
        self.assertEqual((s["built"], s["skipped"], self.calls), (1, 3, ["art.bundle"]))

    def test_a_failing_bundle_is_isolated_and_leaves_no_edges(self):
        self.build()
        def bad(r):
            if r["rel_path"] == "ui-2.bundle":
                raise RuntimeError("cannot parse")
            return self.ex(r)
        self.reg.put_bundle(rec("ui-2.bundle", "CAB-" + "ui-2".ljust(32, "0"), sha="CHANGED"), [asset("CAB-" + "ui-2".ljust(32, "0"), 1)])
        s = depgraph.build(self.reg, extractor=bad)
        self.assertEqual((s["failed"], s["built"]), (1, 0))
        st = self.reg.graph_states()["ui-2.bundle"]
        self.assertEqual(st["state"], "failed")
        self.assertIn("cannot parse", st["error"])
        self.assertEqual(self.edges(src_bundle="ui-2.bundle"), [])                    # the previous edges are gone too: no partial graph for a bundle that failed
        self.assertTrue(self.edges(src_bundle="ui-1.bundle"))                          # the others are untouched

    def test_a_stale_bundle_is_recorded_as_failed_stale(self):
        def stale(r):
            raise depgraph.Stale("size differs")
        s = depgraph.build(self.reg, extractor=stale)
        self.assertEqual((s["stale"], s["built"]), (3, 0))
        self.assertTrue(self.reg.graph_states()["ui-1.bundle"]["error"].startswith("stale:"))

    def test_cancel_keeps_finished_bundles_and_still_resolves(self):
        n = [0]
        def cancel():
            n[0] += 1
            return n[0] > 2
        with self.assertRaises(depgraph.GraphCancelled) as cm:
            depgraph.build(self.reg, extractor=self.ex, cancel=cancel)
        self.assertTrue(cm.exception.summary["cancelled"])
        self.assertEqual(len(self.reg.graph_states()), 2)
        s = self.build()
        self.assertEqual(s["built"] + s["bundle_only"] + s["skipped"], 4)

    def test_a_bundle_that_leaves_the_inventory_loses_its_edges(self):
        self.build()
        self.reg.put_bundle(rec("ui-3.bundle", "CAB-" + "ui-3".ljust(32, "0"), state="missing"), [])
        s = self.build()
        self.assertEqual(s["removed"], 1)
        self.assertEqual(self.edges(src_bundle="ui-3.bundle"), [])

    def test_progress_and_summary(self):
        seen = []
        s = self.build(progress=lambda m, f: seen.append(f))
        self.assertEqual(seen[-1], 1.0)
        self.assertEqual(s["edges"], len(self.edges()))


class TestRegistryUpgrade(unittest.TestCase):
    def test_a_stage_4b_database_is_upgraded_in_place(self):
        d = Path(tempfile.mkdtemp(prefix="fm27se-up-"))
        self.addCleanup(shutil.rmtree, d, ignore_errors=True)
        con = sqlite3.connect(str(d / "r.sqlite"))
        con.executescript("CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT); INSERT INTO meta VALUES ('schema','1');"
                          "CREATE TABLE assets (bundle TEXT NOT NULL, cab TEXT NOT NULL, path_id TEXT NOT NULL, class_id INTEGER, type TEXT, name TEXT, guid TEXT, ref_guid TEXT, panel_id TEXT, container TEXT, PRIMARY KEY (bundle, cab, path_id));"
                          "INSERT INTO assets VALUES ('b','c','1',114,'MonoBehaviour','n',NULL,NULL,NULL,NULL);")
        con.commit()
        con.close()
        reg = registry.Registry(d / "r.sqlite", "iid")
        a = reg.get_asset("b", "c", "1")
        self.assertIn("role", a)
        self.assertEqual(reg.graph_summary()["edges"], 0)
        with reg._db() as db:
            self.assertEqual(db.execute("SELECT value FROM meta WHERE key='schema'").fetchone()[0], str(registry.SCHEMA_VERSION))


class TestRealExtractionAndEngine(unittest.TestCase):
    def setUp(self):
        from unittest import mock
        from skin_editor.engine import Engine
        self.tmp = Path(tempfile.mkdtemp(prefix="fm27se-g-eng-"))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.addCleanup(self._close_logs)
        self.game, self.plat = make_install(self.tmp)
        with mock.patch.dict(os.environ, {"FM27SE_WORKSPACE": str(self.tmp / "ws")}):
            self.e = Engine()

    @staticmethod
    def _close_logs():
        import logging
        for h in list(logging.getLogger("skin_editor").handlers):
            logging.getLogger("skin_editor").removeHandler(h)
            h.close()

    def call(self, name, params=None):
        from skin_editor.api.methods import call, methods
        return call(self.e, methods()[name], params or {})

    def test_extraction_from_a_real_bundle_file_and_stale_detection(self):
        self.call("install.profile_select", {"game_dir": str(self.game)})
        self.e.jobs.wait(self.call("inventory.scan", {})["job"], 60)
        p, reg = self.e._registry()
        r = reg.get_bundle("ui-tileslayouts_assets_all.bundle")
        edges, roles, notes = depgraph.extract_bundle(r)
        self.assertEqual((edges, roles, notes), ([], {}, []))                          # the synthetic bundle holds one TextAsset: no references
        os.utime(self.plat / "ui-tileslayouts_assets_all.bundle", ns=(1, 1))
        with self.assertRaises(depgraph.Stale):
            depgraph.extract_bundle(r)

    def test_graph_methods_through_the_engine_do_not_touch_the_game_folder(self):
        before = tree_hashes(self.game)
        self.call("install.profile_select", {"game_dir": str(self.game)})
        self.e.jobs.wait(self.call("inventory.scan", {})["job"], 60)
        done = self.e.jobs.wait(self.call("graph.build", {"scope": "all"})["job"], 60).view()
        self.assertEqual(done["state"], "done", done["error"])
        self.assertEqual(done["result"]["built"], 3)
        st = self.call("graph.status")
        self.assertEqual(st["bundles_by_state"], {"built": 3})
        a = self.call("registry.search", {"type": "TextAsset", "limit": 1})["assets"][0]
        key = {"bundle": a["bundle"], "cab": a["cab"], "path_id": a["path_id"]}
        self.assertEqual(self.call("graph.uses", key)["edges"], [])
        self.assertEqual(self.call("graph.used_by", key)["edges"], [])
        aff = self.call("graph.affected", dict(key, edit_kind="value"))
        self.assertEqual((aff["rebuild_required"], aff["status"]), ([a["bundle"]], "complete"))
        scr = self.call("graph.screen", key)
        self.assertEqual(scr["stats"]["gaps"], 0)
        self.assertIn(scr["root"], scr["graph"]["nodes"])
        with self.assertRaises(KeyError):
            self.call("graph.affected", dict(key, path_id="999", edit_kind="value"))
        with self.assertRaises(ValueError):
            self.call("graph.affected", dict(key, edit_kind="rename"))
        self.assertEqual(before, tree_hashes(self.game))

    def test_a_queued_graph_build_can_be_cancelled(self):
        self.call("install.profile_select", {"game_dir": str(self.game)})
        self.e.jobs.wait(self.call("inventory.scan", {})["job"], 60)
        gate = threading.Event()
        blocker = self.e.jobs.submit("hold", lambda prog: gate.wait(10))
        job = self.call("graph.build", {})
        self.assertTrue(self.call("jobs.cancel", {"id": job["job"]})["cancelled"])
        gate.set()
        self.e.jobs.wait(blocker.id, 10)
        self.assertEqual(self.e.jobs.get(job["job"]).state, "cancelled")


NEEDED = ["ui-panelids_assets_all.bundle", "ui-visualtreeassets_assets_gameworldvisualtreeassetpreload.bundle", "ui-visualtreeassets_assets_globalvisualtreeassetpreload.bundle",
          "ui-tileslayouts_assets_all.bundle", "ui-tactics_assets_all.bundle", "ui-icons_assets_common.bundle", "ui-textures_assets_all.bundle", "ui-tifo-icons-controller-keyboard_assets_all.bundle"]
PANEL = ("ui-panelids_assets_all.bundle", "CAB-e16c6056a53390e132761eee07a04286", "3231362464821714919")
GW = "ui-visualtreeassets_assets_gameworldvisualtreeassetpreload.bundle"
GW_CAB = "CAB-1ab8e16d7264cd64aba00192bdf91ea2"
TL = "ui-tileslayouts_assets_all.bundle"
TL_CAB = "CAB-ee9fb57ee732c9abd565f5c4171f2bad"


@unittest.skipUnless(all((SETC / n).is_file() for n in NEEDED), "archived set-C bundles not present")
class TestStage2DAndStage3Relationships(unittest.TestCase):
    """The chain of docs/rea/STAGE-2D-SQUADSCREEN-STYLING-MAP.md and the Stage 3 bundles, rebuilt from copies of the archived bundles."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp(prefix="fm27se-setc-"))
        plat = cls.tmp / "aa" / "StandaloneWindows64"
        plat.mkdir(parents=True)
        for n in NEEDED:
            shutil.copyfile(SETC / n, plat / n)
        cls.plat = plat
        cls.reg = registry.Registry(cls.tmp / "r.sqlite", "iid")
        inventory.scan(cls.reg, [plat])
        cls.summary = depgraph.build(cls.reg, scope="all")

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def test_the_build_is_clean(self):
        self.assertEqual((self.summary["failed"], self.summary["stale"]), (0, 0))
        self.assertEqual(self.summary["built"], len(NEEDED))

    def test_panel_squadscreen_reaches_its_layout_by_the_uxml_guid(self):
        (e,) = [x for x in depgraph.uses(self.reg, *PANEL)["edges"] if x["kind"] == "guid_reference"]
        self.assertEqual((e["resolution"], e["basis"], e["dst"]["path_id"], e["dst"]["bundle"]), ("resolved", "guid_container+layout_pair", "-8846846942422787309", GW))
        self.assertEqual(e["provenance"], "m_panelDescription/uxml")
        self.assertEqual(len(e["candidates"]), 2)                              # the layout and its inline sheet share the GUID container

    def test_layout_to_inline_sheet_and_to_the_composition_set_through_externals(self):
        out = {x["relation"]: x for x in depgraph.uses(self.reg, GW, GW_CAB, "-8846846942422787309")["edges"]}
        self.assertEqual((out["inline_stylesheet"]["dst"]["path_id"], out["inline_stylesheet"]["resolution"]), ("3611671695009618707", "resolved"))
        c = out["composition_set_reference"]
        self.assertEqual((c["dst"]["bundle"], c["dst"]["cab"], c["dst"]["path_id"]), (TL, TL_CAB, "2783768945364804139"))
        self.assertEqual(c["target"]["file_id"], 2)                           # Stage 2D: file id 2 resolves to the tileslayouts CAB
        self.assertTrue(c["provenance"].endswith("Bindings/m_gridCompositionSet"))      # down to the serialized field

    def test_composition_set_reaches_the_six_compositions(self):
        names = sorted(e["dst"]["name"] for e in depgraph.uses(self.reg, TL, TL_CAB, "2783768945364804139")["edges"] if e["relation"] == "composition_ref")
        self.assertEqual(names, ["SquadComposition-Large", "SquadComposition-Small", "SquadComposition-Standard", "SquadCompositionFMC-Large", "SquadCompositionFMC-Small", "SquadCompositionFMC-Standard"])

    def test_standard_composition_places_the_five_tile_layouts_by_guid(self):
        refs = {e["dst"]["name"]: e["dst"]["path_id"] for e in depgraph.uses(self.reg, TL, TL_CAB, "-8744014289983900540")["edges"] if e["relation"] == "uxml_reference"}
        self.assertEqual(refs["TrainingTile_4x2"], "-327648902542519771")        # the layout whose sheet Stage 3A edited the neighbour of
        self.assertEqual(refs["TacticsTile_4x4"], "3128036188561496966")
        self.assertEqual(refs["SquadAtmosphereTile_4x2"], "-8519129957244959712")
        self.assertEqual(len(refs), 5)

    def test_bundle_dependencies_of_the_gameworld_bundle(self):
        deps = {e["dst"]["bundle"] for e in depgraph.uses(self.reg, GW)["edges"] if e["kind"] == "bundle_dependency" and e["resolution"] == "resolved"}
        self.assertEqual(deps, {"ui-tactics_assets_all.bundle", "ui-icons_assets_common.bundle", "ui-textures_assets_all.bundle", "ui-tifo-icons-controller-keyboard_assets_all.bundle", TL})
        self.assertIn(GW, {e["src"]["bundle"] for e in depgraph.used_by(self.reg, TL)["edges"]})

    def test_stage3_composition_edit_is_a_value_edit_that_rebuilds_one_bundle(self):
        r = depgraph.affected(self.reg, TL, TL_CAB, "-8744014289983900540", "value")
        self.assertEqual((r["rebuild_required"], r["status"], r["unknown"]), ([TL], "complete", []))
        up = depgraph.used_by(self.reg, TL, TL_CAB, "-8744014289983900540")["edges"]
        self.assertEqual([e["src"]["name"] for e in up], ["SquadTileCompositionSet"])

    def test_identity_edit_of_the_composition_set_requires_the_gameworld_bundle(self):
        r = depgraph.affected(self.reg, TL, TL_CAB, "2783768945364804139", "identity")
        self.assertIn(GW, r["rebuild_required"])
        self.assertIn(TL, r["rebuild_required"])

    def test_a_missing_dependency_bundle_is_reported_unresolved_not_dropped(self):
        d = Path(tempfile.mkdtemp(prefix="fm27se-setc2-"))
        self.addCleanup(shutil.rmtree, d, ignore_errors=True)
        plat = d / "aa" / "p"
        plat.mkdir(parents=True)
        for n in NEEDED:
            if n != "ui-textures_assets_all.bundle":
                shutil.copyfile(SETC / n, plat / n)
        reg = registry.Registry(d / "r.sqlite", "iid")
        inventory.scan(reg, [plat])
        depgraph.build(reg, scope="all")
        miss = [e for e in depgraph.uses(reg, GW)["edges"] if e["kind"] == "bundle_dependency" and e["resolution"] == "unresolved"]
        self.assertEqual([(e["reason"], e["target"]["cab"]) for e in miss], [("cab_not_in_inventory", "cab-787be361157b246e30d1ff121b0849d1")])

    def test_the_screen_view_is_a_projection_of_the_registry_graph(self):
        r = graphview.project_panel(self.reg, "1355920640", max_depth=4)
        d = r["graph"].to_dict()
        kinds = {n["kind"] for n in d["nodes"].values()}
        self.assertTrue({"panel", "layout", "style_sheet", "composition_set", "composition", "bundle"} <= kinds)
        types = {e["type"] for e in d["edges"]}
        self.assertTrue({"references_layout", "has_inline_sheet", "uses_composition_set", "has_composition", "in_bundle"} <= types)
        layout = graphview.node_id(GW, GW_CAB, "-8846846942422787309")
        self.assertEqual(d["nodes"][layout]["locator"], {"bundle": GW, "file": GW_CAB, "path_id": "-8846846942422787309"})      # the UiDocument locator keys
        edge = [e for e in d["edges"] if e["type"] == "references_layout"][0]
        self.assertEqual(edge["read_from"]["field"], "m_panelDescription/uxml")
        self.assertFalse(edge["assumed"])
        self.assertFalse(d["nodes"][layout].get("assumed", False))

    def test_the_screen_view_shows_gaps_instead_of_hiding_them(self):
        g = graphview.project(self.reg, {"bundle": TL, "cab": TL_CAB, "path_id": "-8744014289983900540"}, max_depth=1)
        self.assertGreaterEqual(g["stats"]["assets"], 6)
        self.assertIn("gaps", g["stats"])

    def test_the_graph_view_is_rebuilt_from_the_same_data_not_a_second_copy(self):
        a = graphview.project_panel(self.reg, "1355920640", max_depth=3)["graph"].to_dict()
        b = graphview.project_panel(self.reg, "1355920640", max_depth=3)["graph"].to_dict()
        self.assertEqual(json.dumps(a, sort_keys=True), json.dumps(b, sort_keys=True))      # deterministic projection


if __name__ == "__main__":
    unittest.main()
