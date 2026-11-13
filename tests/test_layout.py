"""Layout dump tests. Milestone A: contract validation, import, storage, staleness, CLI."""
import contextlib, copy, io, json, os, tempfile, threading, unittest, urllib.error, urllib.request
from pathlib import Path
from unittest import mock

from skin_editor import __main__ as cli, config, layout_dump as ld, layout_join as lj, layout_view as lv, server
from tests.layout_fixture import SOURCE, fixture, manifest, style_index


def good():
    """Smallest dump that exercises every section and every reference kind."""
    return {
        "meta": {"schema": "fmlayout-index/2", "game_build": "27.0.1.2494769", "index_fingerprint": "abcdef0123456789abcdef", "exported_at": "2026-11-12T10:00:00+01:00", "source": copy.deepcopy(SOURCE)},
        "areas": {"map": {"ScreenA": "tactics_panel", "TileA": "pitch_header"},
                  "anchors": [{"area": "pitch_header", "layout_name_suffix": "Header"}, {"area": "top_bar", "element_name": "MainNav"}, {"area": "x", "element_class": "c"}, {"area": "y", "layout_name": "ScreenA"}]},
        "layouts": [{"id": 1, "name": "ScreenA", "guid": "a" * 32, "bundle": "b1"}, {"id": 2, "name": "TileA", "guid": "b" * 32, "bundle": "b1"}],
        "elements": [{"layout_id": 1, "local_id": 10, "parent_local_id": None, "ord": 0, "type": "VisualElement", "name": "root", "classes": ["k1"]},
                     {"layout_id": 1, "local_id": 11, "parent_local_id": 10, "ord": 1, "type": "SIButton", "name": "", "classes": [], "runtime_classes": ["rt"]},
                     {"layout_id": 2, "local_id": 20, "parent_local_id": None, "ord": 0, "type": "VisualElement", "name": "", "classes": ["k2"]}],
        "includes": [{"from_layout_id": 1, "element_local_id": 11, "alias": "Tile", "to_layout_id": 2}],
        "panels": [{"panel_id": "PanelA", "layout_id": 1}],
        "tiles": [{"panel_layout_id": 1, "set_name": "SetA", "breakpoint": 1, "variant_idx": 0, "composition": "CompA", "cell_index": 0,
                   "cell_element_id": "Body", "cfg_index": 0, "size": {"w": 12, "h": 8}, "tile_layout_id": 2}],
        "compositions": [{"name": "CompA", "layout_mode": "0", "preset_name": "Fullscreen", "preset_w": 12, "preset_h": 8, "instantiation_order": [0], "conditions": ["isonmainscreen"]}],
        "cells": [{"composition": "CompA", "cell_index": 0, "element_id": "Body", "x": 0, "y": 0, "w": 12, "h": 8, "min_w": 4, "min_h": 2, "max_w": 100, "max_h": 100,
                   "flags": ["locked", "weird"], "h_align": "0", "v_align": "0"}],
        "cell_configs": [{"composition": "CompA", "cell_index": 0, "cfg_index": 0, "size_w": 12, "size_h": 8, "tile_layout_id": 2}],
        "x": None,
    }


def make():
    d = good(); del d["x"]
    d["meta"]["runtime_classes_provenance"] = "inspector 0.2.2, Tactics screen, game 27.0.1.2494769"
    return d


def write(tmp, d, name="dump.json"):
    p = Path(tmp) / name
    p.write_text(d if isinstance(d, str) else json.dumps(d), encoding="utf-8")
    return p


class Validate(unittest.TestCase):
    def errs(self, mutate):
        d = make(); mutate(d)
        e, total = ld.validate(d)
        return e, total

    def test_valid(self):
        self.assertEqual(ld.validate(make()), ([], 0))
        s = ld.summary(make())
        self.assertEqual((s["layouts"], s["elements"], s["cells"], s["areas.anchors"], s["elements_with_runtime_classes"]), (2, 3, 1, 4, 1))

    def rejected(self, mutate, needle):
        e, total = self.errs(mutate)
        self.assertTrue(total >= 1 and any(needle in x for x in e), (needle, e))

    def test_top_level(self):
        self.assertTrue(ld.validate([])[1])
        self.rejected(lambda d: d.pop("meta"), "meta")
        self.rejected(lambda d: d.pop("cells"), "missing section")
        self.rejected(lambda d: d.update(extra=[]), "unknown top-level key")
        self.rejected(lambda d: d.update(cells={}), "must be an array")

    def test_schema(self):
        for bad in ("fmlayout-index/1", "fmlayout-index/3", "fmlayout-index", "", None, 1):
            e, total = self.errs(lambda d, b=bad: d["meta"].update(schema=b))
            self.assertEqual(total, 1); self.assertIn("unsupported schema", e[0])
        e, _ = self.errs(lambda d: d["meta"].pop("schema")); self.assertIn("unsupported schema", e[0])

    def test_meta(self):
        for k in ("game_build", "index_fingerprint", "exported_at"):
            self.rejected(lambda d, k=k: d["meta"].update({k: ""}), "meta." + k)
            self.rejected(lambda d, k=k: d["meta"].pop(k), "meta." + k)
        self.rejected(lambda d: d["meta"].update(junk=1), "unknown key")
        self.rejected(lambda d: d["meta"].pop("runtime_classes_provenance"), "runtime_classes_provenance")
        d = make(); d["meta"].pop("runtime_classes_provenance"); d["elements"][1].pop("runtime_classes")
        self.assertEqual(ld.validate(d)[1], 0)          # provenance is optional when no element has runtime_classes

    def test_record_shapes(self):
        self.rejected(lambda d: d["layouts"][0].update(guid="XYZ"), "guid")
        self.rejected(lambda d: d["layouts"][0].update(id=True), "id")                  # bool is not an int
        self.rejected(lambda d: d["layouts"][0].update(id="1"), "id")
        self.rejected(lambda d: d["layouts"][0].update(extra=1), "unknown key")
        self.rejected(lambda d: d["layouts"][0].pop("bundle"), "missing key")
        self.rejected(lambda d: d["elements"][0].update(classes="k1"), "classes")
        self.rejected(lambda d: d["elements"][1].update(runtime_classes="rt"), "runtime_classes")
        self.rejected(lambda d: d["tiles"][0].update(size={"w": 0, "h": 8}), "size")
        self.rejected(lambda d: d["tiles"][0].update(size={"w": 1}), "size")
        self.rejected(lambda d: d["compositions"][0].update(conditions="x"), "conditions")
        self.rejected(lambda d: d["compositions"][0].update(preset_w=1.5), "preset_w")
        self.rejected(lambda d: d["cells"][0].update(w=0), "'w'")
        self.rejected(lambda d: d["cells"][0].update(x=-2), "'x'")                     # -1 is the game's own "placed by the grid" marker and is accepted
        d = make(); d["cells"][0].update(x=-1, y=-1, max_w=0, max_h=0); self.assertEqual(ld.validate(d)[1], 0)   # and a max of 0 means unlimited, not "below min"
        d = make(); d["compositions"][0].update(bundle="ui-tileslayouts_assets_all.bundle", path_id=-5); self.assertEqual(ld.validate(d)[1], 0)
        self.rejected(lambda d: d["compositions"][0].update(path_id="5"), "path_id")
        d = make(); d["areas"]["anchors"].append({"area": "a", "layout_name_regex": "^X"}); self.assertEqual(ld.validate(d)[1], 0)
        self.rejected(lambda d: d["cells"][0].update(flags="locked"), "flags")
        self.rejected(lambda d: d["cell_configs"][0].update(size_w=0), "size_w")
        self.rejected(lambda d: d["panels"][0].update(panel_id=""), "panel_id")
        self.rejected(lambda d: d["panels"].append("x"), "must be an object")

    def test_cells_values(self):
        self.rejected(lambda d: d["cells"][0].update(min_w=200), "min above max")
        self.rejected(lambda d: d["cells"][0].update(max_h=100001), "above")
        d = make(); d["cells"][0]["flags"] = ["whatever"]
        self.assertEqual(ld.validate(d)[1], 0)         # unknown flags are carried, not rejected

    def test_areas(self):
        self.rejected(lambda d: d["areas"].pop("anchors"), "areas")
        self.rejected(lambda d: d["areas"]["map"].update(Nope="x"), "not in layouts")
        self.rejected(lambda d: d["areas"]["map"].update(ScreenA=""), "area")
        self.rejected(lambda d: d["areas"]["anchors"].append({"area": "a", "layout_name": "x", "element_name": "y"}), "exactly one")
        self.rejected(lambda d: d["areas"]["anchors"].append({"area": "a", "bogus": "y"}), "exactly one")
        self.rejected(lambda d: d["areas"]["anchors"].append({"layout_name": "y"}), "exactly one")

    def test_duplicates(self):
        self.rejected(lambda d: d["layouts"].append(dict(d["layouts"][0])), "duplicate id")
        self.rejected(lambda d: d["elements"].append(dict(d["elements"][0])), "duplicate (layout_id, local_id)")
        self.rejected(lambda d: d["panels"].append(dict(d["panels"][0])), "duplicate panel_id")
        self.rejected(lambda d: d["compositions"].append(dict(d["compositions"][0])), "duplicate name")
        self.rejected(lambda d: d["cells"].append(dict(d["cells"][0])), "duplicate")
        self.rejected(lambda d: d["cell_configs"].append(dict(d["cell_configs"][0])), "duplicate")

    def test_references(self):
        self.rejected(lambda d: d["elements"][0].update(layout_id=99), "layout_id 99")
        self.rejected(lambda d: d["elements"][1].update(parent_local_id=99), "parent 99")
        self.rejected(lambda d: d["elements"][1].update(parent_local_id=20), "parent 20")      # an element of another layout
        self.rejected(lambda d: d["includes"][0].update(to_layout_id=99), "unknown layout id")
        self.rejected(lambda d: d["includes"][0].update(element_local_id=99), "element 99")
        self.rejected(lambda d: d["panels"][0].update(layout_id=99), "layout_id 99")
        self.rejected(lambda d: d["tiles"][0].update(tile_layout_id=99), "unknown layout id")
        self.rejected(lambda d: d["tiles"][0].update(composition="Nope"), "composition 'Nope'")
        self.rejected(lambda d: d["tiles"][0].update(cell_index=5), "does not exist")
        self.rejected(lambda d: d["cells"][0].update(composition="Nope"), "composition 'Nope'")
        self.rejected(lambda d: d["cell_configs"][0].update(cell_index=5), "does not exist")
        self.rejected(lambda d: d["cell_configs"][0].update(tile_layout_id=99), "tile_layout_id 99")

    def test_error_cap(self):
        d = make(); d["elements"] = d["elements"][:1] * 1
        for i in range(200): d["layouts"].append({"id": 1000 + i, "name": "n", "guid": "z"})
        e, total = ld.validate(d)
        self.assertEqual(len(e), ld.MAX_ERRORS); self.assertGreaterEqual(total, 200)


class Store(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.ws = config.Workspace(Path(self.tmp.name) / "ws")

    def snapshot(self, build="27.0.1.2494769", **kw):
        (self.ws.vanilla / "manifest.json").write_text(json.dumps(manifest(build, **kw)))

    def test_file_level_refusals(self):
        with self.assertRaises(ld.LayoutError): ld.import_dump(self.ws, Path(self.tmp.name) / "missing.json")
        with self.assertRaises(ld.LayoutError) as c: ld.import_dump(self.ws, write(self.tmp.name, "{not json"))
        self.assertIn("not valid", str(c.exception))
        p = Path(self.tmp.name) / "bad.bin"; p.write_bytes(b"\xff\xfe\x00\x80")
        with self.assertRaises(ld.LayoutError): ld.import_dump(self.ws, p)
        with mock.patch.object(ld, "MAX_BYTES", 10), self.assertRaises(ld.LayoutError) as c:
            ld.import_dump(self.ws, write(self.tmp.name, make()))
        self.assertIn("larger", str(c.exception))
        self.assertFalse((self.ws.layout / "current.json").exists())

    def test_refusal_leaves_storage_untouched(self):
        ld.import_dump(self.ws, write(self.tmp.name, make(), "a.json"))
        before = (self.ws.layout / "current.json").read_bytes()
        bad = make(); bad["cells"][0]["w"] = 0
        with self.assertRaises(ld.LayoutError) as c: ld.import_dump(self.ws, write(self.tmp.name, bad, "b.json"))
        self.assertEqual(c.exception.total, 1); self.assertTrue(c.exception.errors)
        self.assertEqual((self.ws.layout / "current.json").read_bytes(), before)
        self.assertFalse((self.ws.layout / "previous.json").exists()); self.assertFalse(list(self.ws.layout.glob("*.tmp")))
        wrong = make(); wrong["meta"]["schema"] = "fmlayout-index/1"
        with self.assertRaises(ld.LayoutError): ld.import_dump(self.ws, write(self.tmp.name, wrong, "c.json"))
        self.assertEqual((self.ws.layout / "current.json").read_bytes(), before)

    def test_import_generations_and_changed(self):
        a, b = make(), make(); b["meta"]["index_fingerprint"] = "ffff" * 8
        s1 = ld.import_dump(self.ws, write(self.tmp.name, a, "a.json"))
        self.assertTrue(s1["present"]); self.assertIsNone(s1["changed_vs_previous"]); self.assertIsNone(s1["previous_fingerprint"])
        self.assertEqual(s1["fingerprint"], "abcdef012345")                   # short form, 12 chars
        s2 = ld.import_dump(self.ws, write(self.tmp.name, a, "a2.json"))
        self.assertFalse(s2["changed_vs_previous"])                            # same fingerprint: dump unchanged
        s3 = ld.import_dump(self.ws, write(self.tmp.name, b, "b.json"))
        self.assertTrue(s3["changed_vs_previous"]); self.assertEqual(s3["fingerprint"], "ffffffffffff"); self.assertEqual(s3["previous_fingerprint"], "abcdef012345")
        self.assertEqual(ld.load(self.ws)["meta"]["index_fingerprint"], "ffff" * 8)
        self.assertEqual(json.loads((self.ws.layout / "previous.json").read_text())["meta"]["index_fingerprint"], "abcdef0123456789abcdef")
        ld.import_dump(self.ws, write(self.tmp.name, a, "a3.json"))            # one generation only
        self.assertEqual(json.loads((self.ws.layout / "previous.json").read_text())["meta"]["index_fingerprint"], "ffff" * 8)
        self.assertEqual(sorted(p.name for p in self.ws.layout.iterdir()), ["current.json", "previous.json", "status.json"])

    def test_source_never_written(self):
        p = write(self.tmp.name, make(), "src.json"); before = p.read_bytes(); mtime = p.stat().st_mtime_ns
        ld.import_dump(self.ws, p)
        self.assertEqual(p.read_bytes(), before); self.assertEqual(p.stat().st_mtime_ns, mtime)
        self.assertEqual((self.ws.layout / "current.json").read_bytes(), before)

    def test_failed_swap_restores_current(self):
        ld.import_dump(self.ws, write(self.tmp.name, make(), "a.json"))
        keep = (self.ws.layout / "current.json").read_bytes(); real = os.replace; calls = []
        def flaky(src, dst):
            calls.append(Path(dst).name)
            if Path(dst).name == "current.json" and Path(src).name == "incoming.tmp": raise OSError("disk full")
            return real(src, dst)
        b = make(); b["meta"]["index_fingerprint"] = "e" * 20
        with mock.patch.object(ld.os, "replace", flaky), self.assertRaises(OSError): ld.import_dump(self.ws, write(self.tmp.name, b, "b.json"))
        self.assertEqual((self.ws.layout / "current.json").read_bytes(), keep)

    def test_staleness_compares_file_hashes_not_the_build_label(self):
        ld.import_dump(self.ws, write(self.tmp.name, make()))
        st = ld.state(self.ws)["staleness"]; self.assertEqual(st["status"], "unknown"); self.assertIn("no reference hashes", st["message"])
        self.snapshot(); self.assertEqual(ld.state(self.ws)["staleness"]["status"], "fresh")
        self.snapshot("27.0.2.9999999"); self.assertEqual(ld.state(self.ws)["staleness"]["status"], "fresh")        # the build label is display only
        self.snapshot(catalog="d" * 32); st = ld.state(self.ws)["staleness"]                                         # game updated
        self.assertEqual(st["status"], "stale"); self.assertIn("STALE LAYOUT DATA", st["message"])
        self.snapshot(bundles={"ui-a.bundle": "1" * 64, "ui-b.bundle": "9" * 64}); st = ld.state(self.ws)["staleness"]   # same catalog, another bundle hash
        self.assertEqual((st["status"], st["differing_bundles"]), ("contaminated", ["ui-b.bundle"])); self.assertIn("CONTAMINATED", st["message"])
        self.snapshot(bundles={"ui-a.bundle": "1" * 64}); st = ld.state(self.ws)["staleness"]                        # dump read a bundle with no reference
        self.assertEqual(st["status"], "unknown"); self.assertIn("ui-b.bundle", st["message"])
        self.snapshot(reference=False); self.assertEqual(ld.state(self.ws)["staleness"]["status"], "unknown")        # snapshot without reference hashes
        (self.ws.vanilla / "manifest.json").write_text(json.dumps({"files": {}}))
        self.assertEqual(ld.state(self.ws)["staleness"]["status"], "unknown")
        self.assertEqual(ld.state(self.ws)["runtime_classes_provenance"], make()["meta"]["runtime_classes_provenance"])
        self.assertEqual(ld.state(self.ws)["source"], {"platform_folder": SOURCE["platform_folder"], "catalog_hash": "c" * 12, "bundles": 2})

    def test_reference_hashes_recorded_by_snapshot_and_by_the_one_time_action(self):
        from skin_editor import install, bundles
        aa = Path(self.tmp.name) / "StreamingAssets" / "aa" / "StandaloneWindows64"; aa.mkdir(parents=True)
        for n in bundles.STYLE_BUNDLES: (aa / n).write_bytes(b"style " + n.encode())
        (aa / "ui-tactics_assets_all.bundle").write_bytes(b"tactics"); (aa.parent / "catalog.hash").write_text("abc123\n")
        man = install.snapshot_vanilla(self.ws, aa, "27.1")
        ref = man["reference"]; self.assertEqual((ref["platform_folder"], ref["catalog_hash"]), ("StandaloneWindows64", "abc123"))
        self.assertIn("ui-tactics_assets_all.bundle", ref["bundles"]); self.assertEqual(len(ref["bundles"]), 1 + len(bundles.STYLE_BUNDLES))
        self.assertEqual(ref["bundles"]["ui-tactics_assets_all.bundle"], bundles.sha256(aa / "ui-tactics_assets_all.bundle"))
        # an old snapshot (no reference) gets them through the action, with the same precondition as the snapshot: stock files
        old = json.loads((self.ws.vanilla / "manifest.json").read_text()); old.pop("reference")
        (self.ws.vanilla / "manifest.json").write_text(json.dumps(old))
        (aa / bundles.STYLE_BUNDLES[0]).write_bytes(b"skinned")
        with self.assertRaises(install.InstallError) as c: install.record_reference_hashes(self.ws, aa)
        self.assertIn("not the snapshot's stock file", str(c.exception)); self.assertNotIn("reference", self.ws.vanilla_manifest())
        (aa / bundles.STYLE_BUNDLES[0]).write_bytes(b"style " + bundles.STYLE_BUNDLES[0].encode())
        self.assertEqual(install.record_reference_hashes(self.ws, aa)["reference"]["catalog_hash"], "abc123")
        with self.assertRaises(install.InstallError): install.record_reference_hashes(self.ws, aa)              # already recorded
        (self.ws.vanilla / "manifest.json").unlink()
        with self.assertRaises(install.InstallError): install.record_reference_hashes(self.ws, aa)              # no snapshot

    def test_tamper_check_flags_a_modified_ui_bundle(self):
        from skin_editor import install, bundles
        aa = Path(self.tmp.name) / "StreamingAssets" / "aa" / "StandaloneWindows64"; aa.mkdir(parents=True)
        for n in bundles.STYLE_BUNDLES: (aa / n).write_bytes(b"style " + n.encode())
        tac = aa / "ui-tactics_assets_all.bundle"; tac.write_bytes(b"tactics"); (aa.parent / "catalog.hash").write_text("abc123")
        self.assertEqual(install.tamper_status(self.ws, aa)["state"], "no_reference")
        install.snapshot_vanilla(self.ws, aa, "27.1")
        st = install.tamper_status(self.ws, aa); self.assertEqual((st["state"], st["modified"], st["checked"]), ("clean", [], 3))
        tac.write_bytes(b"move build")                                                    # the spike's move build left in the game folder
        st = install.tamper_status(self.ws, aa)
        self.assertEqual((st["state"], st["modified"], st["files"]["ui-tactics_assets_all.bundle"]), ("modified", ["ui-tactics_assets_all.bundle"], "modified"))
        self.assertIn("ui-tactics_assets_all.bundle", st["message"])
        (aa / "ui-new.bundle").write_bytes(b"x"); self.assertEqual(install.tamper_status(self.ws, aa)["new"], ["ui-new.bundle"])
        tac.write_bytes(b"tactics"); self.assertEqual(install.tamper_status(self.ws, aa)["state"], "clean")
        (aa.parent / "catalog.hash").write_text("zzz999"); self.assertEqual(install.tamper_status(self.ws, aa)["state"], "game_updated")

    def test_contaminated_dump_is_refused_at_import_and_nothing_is_loaded(self):
        self.snapshot(bundles={"ui-a.bundle": "1" * 64, "ui-b.bundle": "9" * 64})
        with self.assertRaises(ld.LayoutError) as c: ld.import_dump(self.ws, write(self.tmp.name, make()))
        self.assertIn("CONTAMINATED", str(c.exception)); self.assertEqual(ld.state(self.ws), {"present": False})
        self.snapshot(catalog="d" * 32); ld.import_dump(self.ws, write(self.tmp.name, make()))                       # stale is accepted (shown, not editable)
        self.assertEqual(ld.state(self.ws)["staleness"]["status"], "stale")

    def test_source_contract(self):
        def bad(mutate, needle):
            e, total = ld.validate(self._mk(mutate)); self.assertTrue(total >= 1 and any(needle in x for x in e), (needle, e))
        bad(lambda d: d["meta"].pop("source"), "meta.source")
        bad(lambda d: d["meta"].update(source="x"), "meta.source")
        bad(lambda d: d["meta"]["source"].pop("catalog_hash"), "catalog_hash")
        bad(lambda d: d["meta"]["source"].update(platform_folder=""), "platform_folder")
        bad(lambda d: d["meta"]["source"].update(extra=1), "unknown key")
        bad(lambda d: d["meta"]["source"].update(bundles={}), "non-empty object")
        bad(lambda d: d["meta"]["source"]["bundles"].update({"ui-a.bundle": "ABC"}), "64 lowercase hex")
        bad(lambda d: d["meta"]["source"]["bundles"].update({"ui-a.bundle": "A" * 64}), "64 lowercase hex")
        e, _ = ld.validate(self._mk(lambda d: d["meta"].update(schema="fmlayout-index/1"))); self.assertIn("refused", e[0])

    def _mk(self, mutate):
        d = make(); mutate(d); return d

    def test_state_without_dump(self):
        self.assertEqual(ld.state(self.ws), {"present": False}); self.assertIsNone(ld.load(self.ws))


class Join(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ld, cls.ix = lj.LayoutData(fixture()), style_index()

    def ev(self, w, selector):
        return next(e for e in w["total"]["evidence"] if e["selector"] == selector)

    def test_fixture_cannot_drift_from_the_contract(self):
        self.assertEqual(ld.validate(fixture()), ([], 0))
        self.assertEqual(ld.validate(fixture(deep=50)), ([], 0))
        d = fixture(); d["cells"][0]["w"] = 0
        self.assertTrue(ld.validate(d)[1])                       # the validator really is what guards the fixture

    def test_chain_crosses_include_and_panel_registry(self):
        w = lj.where_token(self.ld, self.ix, "--t0")
        e = self.ev(w, ".cls-v")
        self.assertEqual(e["state"], lj.VERIFIED)
        self.assertEqual(e["layouts"][0]["layout"], "Leaf"); self.assertEqual(e["layouts"][0]["area"], "pitch_header")
        self.assertEqual(e["layouts"][0]["elements"], ["SIButton#leaf"])
        self.assertIn("PanelOne", w["alias_hops"][0]["screens"])               # Leaf -> (include) Mid -> (include) Screen -> (panel registry) PanelOne
        self.assertEqual(w["total"]["screens"]["PanelOne"]["areas"], ["pitch_header"])

    def test_alias_hop_with_cross_screen(self):
        w = lj.where_token(self.ld, self.ix, "--t0")
        hops = {h["token"]: h for h in w["alias_hops"]}
        self.assertEqual((hops["--t0"]["hop"], hops["--a1"]["hop"], hops["--a2"]["hop"]), (0, 1, 2))
        self.assertEqual(hops["--a1"]["via"], "--t0"); self.assertEqual(hops["--a2"]["via"], "--a1")
        self.assertEqual(hops["--a1"]["screens"], ["PanelTwo"])
        self.assertNotIn("PanelTwo", hops["--t0"]["screens"])
        self.assertEqual(w["cross_screen_via_alias"], {"--a1": ["PanelTwo"]})  # --a2 only reaches PanelOne, which hop 0 already reaches
        self.assertEqual(hops["--a2"]["new_screens_vs_hop0"], [])
        self.assertIn("PanelTwo", w["total"]["screens"])

    def test_runtime_observed_is_labelled_not_verified(self):
        w = lj.where_token(self.ld, self.ix, "--t0")
        e = self.ev(w, ".cls-rt")
        self.assertEqual(e["state"], lj.RUNTIME); self.assertIn("runtime", e["note"])
        self.assertEqual(e["layouts"][0]["layout"], "Leaf")
        leaf = next(l for l in w["total"]["layouts"] if l["layout"] == "Leaf")
        self.assertEqual(leaf["states"], [lj.RUNTIME, lj.VERIFIED])           # two rules reach Leaf: one verified, one runtime-observed
        self.assertEqual(w["total"]["by_state"][lj.RUNTIME], 1)
        self.assertNotIn(".cls-rt", [u["selector"] for u in w["total"]["unverified"]])

    def test_unverified_is_displayed_and_flagged_not_hidden(self):
        w = lj.where_token(self.ld, self.ix, "--t0")
        un = {u["selector"]: u for u in w["total"]["unverified"]}
        self.assertIn(".cls-none", un); self.assertIn("SIButton", un)
        self.assertIn("no element", un[".cls-none"]["reason"]); self.assertIn("no class or id", un["SIButton"]["reason"])
        self.assertEqual(self.ev(w, ".cls-none")["state"], lj.UNVERIFIED); self.assertEqual(self.ev(w, ".cls-none")["layouts"], [])
        self.assertEqual(w["total"]["by_state"][lj.UNVERIFIED], 3)           # .cls-none, SIButton, and .cls-deep (no deep chain in this fixture)
        self.assertEqual(w["total"]["unverified_total"], 3); self.assertIn(".cls-deep", un)
        self.assertIn("NOT COVERED", w["code_set_colours"]); self.assertIn("Lower bound", w["lower_bound"])

    def test_zero_hit_and_unknown(self):
        w = lj.where_token(self.ld, self.ix, "--lonely")
        self.assertTrue(w["zero_hit"]); self.assertEqual(w["total"]["layouts"], []); self.assertEqual(w["total"]["screens"], {})
        self.assertIn("NOT COVERED", w["code_set_colours"])                  # the discipline holds on empty results too
        with self.assertRaises(KeyError): lj.where_token(self.ld, self.ix, "--nope")
        s = lj.where_search(self.ld, self.ix, "zzz-nothing")
        self.assertTrue(s["zero_hit"]); self.assertIn("NOT COVERED", s["code_set_colours"])
        with self.assertRaises(ValueError): lj.where_search(self.ld, self.ix, "  ")

    def test_all_unverified_token_is_flagged(self):
        d = fixture(); d["elements"] = [e for e in d["elements"] if "cls-ph" not in e["classes"]]
        w = lj.where_token(lj.LayoutData(d), self.ix, "--a2")              # --a2 -> .cls-ph:hover, now without any element
        self.assertTrue(w["no_layout_evidence"]); self.assertFalse(w["zero_hit"]); self.assertEqual(w["total"]["unverified_total"], 1)
        self.assertEqual(w["total"]["evidence"][0]["pseudo"], ["hover"])

    def test_cycle_guard(self):
        w = lj.where_token(self.ld, self.ix, "--t0")
        cyc = next(l for l in w["total"]["layouts"] if l["layout"] == "CycB")
        self.assertEqual(cyc["screens"], ["PanelCycle"]); self.assertTrue(cyc["cycle"])      # A includes B includes A: terminates, flagged
        selfl = next(l for l in w["total"]["layouts"] if l["layout"] == "SelfInc")
        self.assertEqual(selfl["screens"], ["PanelSelf"]); self.assertTrue(selfl["cycle"])  # a layout that includes itself
        leaf = next(l for l in w["total"]["layouts"] if l["layout"] == "Leaf"); self.assertFalse(leaf["cycle"])

    def test_cycle_guard_boundaries(self):
        for deep in (0, 1, 5000):
            data = lj.LayoutData(fixture(deep=deep))
            if deep:
                lid = next(l["id"] for l in fixture(deep=deep)["layouts"] if l["name"] == "Deep0")
                panels, cyc = data.screens_of(lid)
                self.assertEqual(panels, ["PanelDeep"]); self.assertFalse(cyc)             # 5000 levels: iterative, no recursion limit
        top = lj.LayoutData(fixture(deep=5000)); lid = next(l["id"] for l in fixture(deep=5000)["layouts"] if l["name"] == "Deep5000")
        self.assertEqual(top.screens_of(lid), (["PanelDeep"], False))
        d = fixture(deep=3); d["includes"].append({"from_layout_id": 100, "element_local_id": 2, "alias": "Back", "to_layout_id": 103})   # closes a ring
        ring = lj.LayoutData(d); self.assertEqual(ring.screens_of(100)[0], ["PanelDeep"]); self.assertTrue(ring.screens_of(100)[1])

    def test_areas(self):
        self.assertEqual(self.ld.area_of(3), "pitch_header"); self.assertEqual(self.ld.area_of(7), lj.UNASSIGNED)
        w = lj.where_token(self.ld, self.ix, "--t0")
        self.assertEqual(w["total"]["by_area"]["unassigned"], 2)               # CycB and SelfInc are not in the map: unassigned, not hidden

    def test_literal(self):
        w = lj.where_literal(self.ld, self.ix, "#036150", 1.0)
        e = w["exact"]["evidence"][0]
        self.assertEqual((e["selector"], e["state"]), (".cls-ph", lj.VERIFIED)); self.assertEqual(e["layouts"][0]["area"], "pitch_header")
        self.assertEqual(sorted(w["exact"]["screens"]), ["PanelOne"])          # PitchHeader is a tile of Screen
        self.assertIn("NOT COVERED", w["code_set_colours"]); self.assertFalse(w["zero_hit"])

    def test_search(self):
        s = lj.where_search(self.ld, self.ix, "cls-v")
        self.assertEqual(s["rules_matched"], 2); self.assertEqual(s["tokens_read"], ["--t0"]); self.assertIn("PanelOne", s["total"]["screens"])
        sel = {e["selector"]: e for e in s["total"]["evidence"]}
        self.assertEqual(sel[".wrap .cls-v"]["state"], lj.VERIFIED)           # descendant selector: the subject (.cls-v) decides
        h = lj.where_search(self.ld, self.ix, ".cls-ph:hover")
        self.assertEqual(h["tokens_read"], ["--a2"]); self.assertEqual(h["total"]["evidence"][0]["pseudo"], ["hover"])
        d = fixture(); d["elements"][4]["classes"].append("cls-norule")
        r = lj.where_search(lj.LayoutData(d), self.ix, "norule")
        self.assertEqual(r["rules_matched"], 0); self.assertFalse(r["zero_hit"])
        self.assertEqual(r["classes_in_layouts_without_rules"]["cls-norule"]["screens"], ["PanelOne"])
        self.assertEqual(r["classes_in_layouts_without_rules"]["cls-norule"]["state"], lj.VERIFIED)

    def test_dump_round_trip_through_storage(self):
        with tempfile.TemporaryDirectory() as tmp:
            ws = config.Workspace(Path(tmp) / "ws")
            ld.import_dump(ws, write(tmp, fixture()))
            w = lj.where_token(lj.LayoutData(ld.load(ws)), self.ix, "--t0")
            self.assertIn("PanelOne", w["alias_hops"][0]["screens"])


class ViewTests(unittest.TestCase):
    """The Layout tab's data: read-only, from the dump, through the same join pipeline."""
    @classmethod
    def setUpClass(cls):
        cls.ld = lj.LayoutData(fixture()); cls.v = lv.View(cls.ld)

    def find(self, nodes, name):
        for n in nodes:
            if n["name"] == name: return n
            r = self.find(n["children"], name)
            if r: return r

    def test_screen_browser_and_areas(self):
        s = self.v.screens()
        self.assertEqual((s["total"], s["shown"]), (4, 4)); self.assertIn("no geometry", s["note"])
        by = {r["panel_id"]: r for r in s["screens"]}
        self.assertEqual(by["PanelOne"]["area"], "tactics_panel"); self.assertEqual(by["PanelCycle"]["area"], lj.UNASSIGNED)   # shown as such
        self.assertEqual((by["PanelOne"]["tiles"], by["PanelOne"]["sets"], by["PanelOne"]["elements"]), (1, 1, 2))
        self.assertEqual(s["by_area"], {"tactics_panel": 1, "training": 1, "unassigned": 2})
        self.assertEqual(s["layouts_by_area"]["unassigned"], 3)                       # CycA, CycB, SelfInc
        self.assertEqual([r["panel_id"] for r in self.v.screens(area="unassigned")["screens"]], ["PanelCycle", "PanelSelf"])
        self.assertEqual([r["panel_id"] for r in self.v.screens(q="two")["screens"]], ["PanelTwo"])
        self.assertEqual(self.v.screens(q="screen")["shown"], 1)                      # matches the layout name too

    def test_screen_reach_by_area(self):
        sc = self.v.screen("PanelOne")
        self.assertEqual(sc["reach"], {"layouts": 4, "by_area": {"pitch_header": 2, "tactics_panel": 2}})   # Screen, Mid, Leaf, tile PitchHeader
        self.assertEqual(self.v.screen("PanelSelf")["reach"]["layouts"], 1)           # self-include terminates
        self.assertEqual(self.v.screen("PanelCycle")["reach"]["layouts"], 2)
        with self.assertRaises(KeyError): self.v.screen("Nope")

    def test_outline_one_include_level_and_cycle_guard(self):
        o = self.v.outline(1)
        slot = self.find(o["tree"], "slot")
        self.assertEqual(slot["includes"], [{"layout_id": 2, "layout": "Mid", "area": "tactics_panel", "alias": "Mid", "cycle": False}])
        self.assertEqual(self.find(o["tree"], "slot")["children"], [])                # not expanded: one level per request
        o2 = self.v.outline(2, [1]); self.assertEqual(o2["ancestry"], [1])
        self.assertEqual(self.find(o2["tree"], "slot2")["includes"][0]["layout"], "Leaf")
        a = self.v.outline(7); self.assertFalse(self.find(a["tree"], "slotA")["includes"][0]["cycle"])
        b = self.v.outline(8, [7]); self.assertTrue(self.find(b["tree"], "slotB")["includes"][0]["cycle"])    # back to CycA: guarded
        s = self.v.outline(9); self.assertTrue(self.find(s["tree"], "slotS")["includes"][0]["cycle"])       # includes itself
        self.assertEqual(self.v.outline(8)["tree"][0]["includes"], [])

    def test_outline_evidence_states_and_areas(self):
        leaf = self.v.outline(3)["tree"][0]
        self.assertEqual(leaf["classes"], [{"name": "cls-v", "state": "verified"}])
        self.assertEqual(leaf["runtime_classes"], [{"name": "cls-rt", "state": "runtime-observed"}])      # labelled, not verified
        self.assertEqual(leaf["type"], "SIButton"); self.assertEqual(self.v.outline(7)["area"], lj.UNASSIGNED)

    def test_outline_search_cap_and_truncation(self):
        o = self.v.outline(3, q="cls-rt"); self.assertEqual((o["matches"], o["total"]), (1, 1))
        m = self.v.outline(1, q="slot"); self.assertEqual(m["matches"], 1); self.assertEqual([n["name"] for n in m["tree"]], ["root"])   # ancestors stay
        self.assertEqual(self.v.outline(1, q="zzz")["tree"], []); self.assertEqual(self.v.outline(1, q="zzz")["matches"], 0)
        d = fixture(); d["elements"] += [{"layout_id": 6, "local_id": 1000 + i, "parent_local_id": 60, "ord": i + 1, "type": "T", "name": "n%d" % i, "classes": []} for i in range(2000)]
        self.assertEqual(ld.validate(d), ([], 0))
        big = lv.View(lj.LayoutData(d)).outline(6)
        self.assertTrue(big["truncated"]); self.assertEqual((big["total"], big["shown"], big["cap"]), (2001, lv.OUTLINE_CAP, lv.OUTLINE_CAP))
        count = lambda ns: sum(1 + count(n["children"]) for n in ns)
        self.assertEqual(count(big["tree"]), lv.OUTLINE_CAP)
        with self.assertRaises(KeyError): self.v.outline(999)

    def test_compositions_and_cells_verbatim(self):
        d = fixture(); c = d["cells"][0]; c.update(flags=["locked", "weird flag"], h_align="Stretch", v_align="0")
        d["compositions"][0].update(layout_mode="4", preset_name="Fullscreen", conditions=["team.IsClub == 1", "opaque text"])
        d["cells"].append(dict(c, cell_index=1, element_id="Side", x=4, flags=[])); d["cell_configs"].append({"composition": "CompA" if False else "Comp", "cell_index": 1, "cfg_index": 0, "size_w": 4, "size_h": 2, "tile_layout_id": 4})
        self.assertEqual(ld.validate(d), ([], 0))
        sc = lv.View(lj.LayoutData(d)).screen("PanelOne")
        v = sc["sets"][0]["variants"][0]
        self.assertEqual((sc["sets"][0]["set_name"], v["breakpoint"], v["variant_idx"], v["composition"]), ("Set", 1, 0, "Comp"))
        self.assertEqual(v["composition_info"], {"layout_mode": "4", "preset_name": "Fullscreen", "preset_w": 12, "preset_h": 8, "instantiation_order": [0], "conditions": ["team.IsClub == 1", "opaque text"]})
        body, side = v["cells"]
        self.assertEqual((body["flags"], body["h_align"], body["v_align"]), (["locked", "weird flag"], "Stretch", "0"))   # displayed as given
        self.assertEqual((body["x"], body["y"], body["w"], body["h"], body["min_w"], body["max_h"]), (0, 0, 4, 2, 1, 8))
        self.assertEqual(body["placed"]["layout"], "PitchHeader"); self.assertEqual(body["placed"]["size"], {"w": 4, "h": 2})
        self.assertEqual(body["configs"][0]["area"], "pitch_header")
        self.assertIsNone(side["placed"]); self.assertEqual(side["configs"][0]["layout"], "PitchHeader")            # a cell with no tile for this variant

    def test_panel_without_tiles(self):
        self.assertEqual(self.v.screen("PanelTwo")["sets"], [])

    def test_read_only_enforced(self):
        from skin_editor import server
        layout_routes = {k: f for k, f in server.ROUTES.items() if "/layout/" in k[1] or "/where/" in k[1]}
        for (method, path) in layout_routes:
            if path != "/api/layout/import":                                   # the one write: importing the dump on the Setup tab
                self.assertEqual(method, "GET", path)
        for path in ("/api/layout/screens", "/api/layout/screen", "/api/layout/outline"):
            self.assertIn(("GET", path), layout_routes); self.assertNotIn(("POST", path), layout_routes)
        html = (Path(__file__).resolve().parent.parent / "frontend" / "index.html").read_text(encoding="utf-8")
        block = html.split("/* LAYOUT TAB BEGIN */")[1].split("/* LAYOUT TAB END */")[0]
        for banned in ("POST", "tile_placement", "placement", "saveProject", "P.", "<button class=\"pri\"", "contenteditable", "type=\"number\"", "textarea", "needProject"):
            self.assertNotIn(banned, block, banned)                            # no edit affordance may leak into C
        self.assertNotIn("api(path, body", block)
        self.assertIn("read-only", block.lower())
        # every request the tab makes is a GET: api() is only ever called with a single argument inside the block
        import re
        for call in re.findall(r"api\(([^)]*)\)", block):
            self.assertNotIn(",", call.split("?")[0], call)

class Http(unittest.TestCase):
    """The routes behind the Tokens and Literals panels and the search box, over a real localhost server."""
    def test_routes(self):
        import logging
        with tempfile.TemporaryDirectory() as tmp, mock.patch.dict(os.environ, {"FM27SE_WORKSPACE": tmp}):
            app = server.App(); app.index = style_index()
            httpd = server.ThreadingHTTPServer(("127.0.0.1", 0), server.make_handler(app, "tok", 0))
            port = httpd.server_address[1]
            th = threading.Thread(target=httpd.serve_forever, daemon=True); th.start()
            def call(path, body=None):
                req = urllib.request.Request("http://127.0.0.1:%d%s" % (port, path), data=body, headers={"X-Token": "tok", "Host": "127.0.0.1:0"})
                try:
                    r = urllib.request.urlopen(req); return r.status, json.loads(r.read())
                except urllib.error.HTTPError as e:
                    return e.code, json.loads(e.read())
            try:
                code, w = call("/api/where/token?name=--t0"); self.assertEqual((code, w["layout_present"]), (200, False)); self.assertIn("Import one", w["message"])
                code, j = call("/api/layout/import?name=fx.json", json.dumps(fixture()).encode()); self.assertEqual(code, 200); self.assertTrue(j["present"])
                bad = fixture(); bad["panels"][0]["layout_id"] = 99
                code, j = call("/api/layout/import", json.dumps(bad).encode()); self.assertEqual(code, 400); self.assertTrue(j["errors"]); self.assertEqual(j["total_errors"], 1)
                code, st = call("/api/state"); self.assertTrue(st["layout"]["present"]); self.assertEqual(st["layout"]["fingerprint"], "f" * 12)
                code, w = call("/api/where/token?name=--t0"); self.assertTrue(w["layout_present"]); self.assertEqual(w["cross_screen_via_alias"], {"--a1": ["PanelTwo"]}); self.assertIn("NOT COVERED", w["code_set_colours"])
                code, w = call("/api/where/literal?rgb=%23036150&a=1.0"); self.assertEqual(w["exact"]["evidence"][0]["state"], "verified")
                code, w = call("/api/where/search?q=cls-rt"); self.assertEqual(w["total"]["evidence"][0]["state"], "runtime-observed")
                code, sc = call("/api/layout/screen?panel=PanelOne"); self.assertEqual(sc["layout"], "Screen"); self.assertEqual(sc["dump"]["staleness"]["status"], "unknown")   # a name, not the dump state
                code, sc = call("/api/layout/screens"); self.assertEqual(sc["total"], 4); self.assertIn("dump", sc)
                code, o = call("/api/layout/outline?layout=1&anc="); self.assertEqual(o["layout"], "Screen")
                code, w = call("/api/where/token?name=--nope"); self.assertEqual(code, 400)
                code, w = call("/api/where/search?q=%20"); self.assertEqual(code, 400)
            finally:
                httpd.shutdown(); httpd.server_close(); th.join(5)
                lg = logging.getLogger("skin_editor")
                for h in list(lg.handlers): lg.removeHandler(h); h.close()

class Cli(unittest.TestCase):
    def run_cli(self, *argv, env=None):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = cli.main(list(argv))
        return code, out.getvalue(), err.getvalue()

    def test_check_layout(self):
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(config, "load", side_effect=AssertionError("must not load config")):
            code, out, _ = self.run_cli("check-layout", str(write(tmp, make())))
            r = json.loads(out); self.assertEqual(code, 0); self.assertTrue(r["valid"])
            self.assertEqual(r["counts"]["cells"], 1); self.assertEqual(r["fingerprint"], "abcdef012345")
            bad = make(); bad["cells"][0]["w"] = 0; bad["layouts"][0]["guid"] = "no"
            code, out, _ = self.run_cli("check-layout", str(write(tmp, bad, "bad.json")))
            r = json.loads(out); self.assertEqual(code, 1); self.assertFalse(r["valid"]); self.assertEqual(r["total_errors"], 2)
            code, out, _ = self.run_cli("check-layout", str(write(tmp, "{oops", "j.json")))
            self.assertEqual(code, 1); self.assertIn("not valid", out)
            code, out, _ = self.run_cli("check-layout", str(Path(tmp) / "nope.json")); self.assertEqual(code, 1)

    def test_import_layout(self):
        import logging
        def close_log():              # the app log handler keeps app.log open (matters on Windows when the temp dir is removed)
            lg = logging.getLogger("skin_editor")
            for h in list(lg.handlers): lg.removeHandler(h); h.close()
        self.addCleanup(close_log)
        with tempfile.TemporaryDirectory() as tmp, mock.patch.dict(os.environ, {"FM27SE_WORKSPACE": str(Path(tmp) / "ws")}):
            code, out, err = self.run_cli("import-layout", str(write(tmp, make())))
            self.assertEqual(code, 0); self.assertTrue(json.loads(out)["present"]); self.assertIn("WARNING", err)    # no snapshot: unknown
            bad = make(); bad["includes"][0]["to_layout_id"] = 99
            code, out, _ = self.run_cli("import-layout", str(write(tmp, bad, "bad.json")))
            r = json.loads(out); self.assertEqual(code, 1); self.assertFalse(r["imported"]); self.assertIn("nothing was loaded", r["message"])
            self.assertTrue((Path(tmp) / "ws" / "layout" / "current.json").is_file())
            close_log()


if __name__ == "__main__":
    unittest.main()
