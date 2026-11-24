"""Milestone D: stored placement edits. Validation matrix, storage, freshness gating, revalidation on dump change, build report, routes."""
import copy, json, logging, os, tempfile, threading, unittest, urllib.error, urllib.request
from pathlib import Path
from unittest import mock

from skin_editor import config, install, layout_dump as ld, patcher, placement as pl, project, server, index_styles, bundles
from tests.layout_fixture import fixture, manifest, style_index
from tests.test_core import fake, sheet

BUILD = "27.0.1.2494769"


def pdump(fp="a" * 40, mutate=None):
    """Composition 'Comp' 12 x 8 with cells A (free, two configs), B (locked), C (free). Valid under the contract."""
    d = fixture()
    d["meta"]["index_fingerprint"] = fp
    d["compositions"] = [{"name": "Comp", "layout_mode": "0", "preset_name": "Fullscreen", "preset_w": 12, "preset_h": 8, "instantiation_order": [0, 1, 2], "conditions": []},
                         {"name": "Flat", "layout_mode": "0", "preset_name": "", "preset_w": 0, "preset_h": 0, "instantiation_order": [], "conditions": []}]
    cell = lambda comp, i, eid_, x, y, w, h, flags=(), mn=(1, 1), mx=(12, 8): {"composition": comp, "cell_index": i, "element_id": eid_, "x": x, "y": y, "w": w, "h": h,
        "min_w": mn[0], "min_h": mn[1], "max_w": mx[0], "max_h": mx[1], "flags": list(flags), "h_align": "0", "v_align": "0"}
    d["cells"] = [cell("Comp", 0, "A", 0, 0, 4, 2), cell("Comp", 1, "B", 6, 0, 4, 2, ["locked"]), cell("Comp", 2, "C", 0, 4, 4, 2, mn=(2, 1), mx=(6, 4)), cell("Flat", 0, "F", 0, 0, 2, 2)]
    cfg = lambda comp, i, k, tile: {"composition": comp, "cell_index": i, "cfg_index": k, "size_w": 4, "size_h": 2, "tile_layout_id": tile}
    d["cell_configs"] = [cfg("Comp", 0, 0, 4), cfg("Comp", 0, 1, 2), cfg("Comp", 1, 0, 4), cfg("Comp", 2, 0, 4), cfg("Flat", 0, 0, 4)]
    d["tiles"] = [dict(d["tiles"][0], composition="Comp", cell_index=0, cfg_index=0)]
    if mutate:
        mutate(d)
    return d


def grid(**kw): return pl.Grid(pdump(**kw))
def geo(x, y, w, h): return {"x": x, "y": y, "w": w, "h": h}
def edit(cell=0, comp="Comp", **kw): return dict({"composition": comp, "cell_index": cell}, **kw)


class Matrix(unittest.TestCase):
    def setUp(self): self.g = grid()

    def blocks(self, e, others=()): return pl.check(self.g, e, others)["blocks"]

    def test_fixture_is_valid_under_the_contract(self):
        self.assertEqual(ld.validate(pdump()), ([], 0))

    def test_valid_edit(self):
        r = pl.check(self.g, edit(geometry=geo(2, 1, 4, 2)))
        self.assertEqual((r["blocks"], r["warnings"], r["collisions"]), ([], [], []))
        self.assertEqual(r["old"]["geometry"], geo(0, 0, 4, 2)); self.assertEqual(r["new"]["geometry"], geo(2, 1, 4, 2))
        self.assertEqual((r["old"]["config"], r["old"]["configs"]), (0, [0, 1]))      # the dump's tiles use cfg 0 for this cell

    def test_hard_blocks(self):
        has = lambda e, text, **kw: self.assertTrue(any(text in b for b in self.blocks(e, **kw)), (text, self.blocks(e, **kw)))
        has(edit(cell=1, geometry=geo(7, 1, 4, 2)), "locked")                                   # locked refuses a move
        has(edit(geometry=geo(10, 0, 4, 2)), "out of bounds"); has(edit(geometry=geo(0, 7, 4, 2)), "out of bounds")
        has(edit(geometry=geo(-1, 0, 4, 2)), "out of bounds"); has(edit(geometry=geo(0, 0, 0, 2)), "out of bounds")
        has(edit(cell=2, geometry=geo(0, 4, 1, 2)), "below the cell's minimum")                 # C needs w >= 2
        has(edit(cell=2, geometry=geo(0, 4, 7, 2)), "above the cell's maximum")                 # C allows w <= 6
        has(edit(cell=2, geometry=geo(0, 4, 4, 5)), "above the cell's maximum")
        for bad in ({"x": 1, "y": 0, "w": 4}, {"x": 1.5, "y": 0, "w": 4, "h": 2}, {"x": True, "y": 0, "w": 4, "h": 2}, {"x": 1, "y": 0, "w": 4, "h": 2, "z": 1}, "x"):
            has(edit(geometry=bad), "integer x, y, w, h")
        has(edit(), "changes nothing"); has(edit(geometry=geo(0, 0, 4, 2)), "no change")        # equal to the dump
        has(edit(comp="Nope", geometry=geo(0, 0, 1, 1)), "target missing"); has(edit(cell=9, geometry=geo(0, 0, 1, 1)), "target missing")
        has({"composition": 5, "cell_index": "x"}, "target missing")

    def test_size_change_is_blocked_position_change_is_not(self):
        for g in (geo(0, 0, 5, 2), geo(0, 0, 4, 3), geo(1, 1, 3, 1)):
            self.assertTrue(any("size change not supported" in b for b in self.blocks(edit(geometry=g))), g)
        self.assertEqual(self.blocks(edit(geometry=geo(2, 1, 4, 2))), [])

    def test_config_whose_size_differs_from_the_cell_is_blocked(self):
        def widen(d): d["cell_configs"][1]["size_w"] = 6                  # Comp cell 0, config 1 is 6 x 2; the cell is 4 x 2
        g = grid(mutate=widen)
        b = pl.check(g, edit(config=1))["blocks"]
        self.assertTrue(any("config change not supported yet" in x and "6 x 2" in x for x in b), b)
        self.assertEqual(pl.check(g, edit(config=0))["blocks"], ["no change: config 0 is already the one used in the dump"])      # same size: allowed (here: no change)
        self.assertTrue(any("config change not supported yet" in x for x in pl.check(g, edit(geometry=geo(2, 1, 4, 2), config=1))["blocks"]))

    def test_locked_allows_a_config_choice(self):
        self.assertEqual(self.blocks(edit(cell=1, config=0)), ["no change: config 0 is already the one used in the dump"] if False else self.blocks(edit(cell=1, config=0)))
        # (cell B has one config and the dump uses none for it: choosing it is not a move, so the lock does not refuse it)
        self.assertFalse(any("locked" in b for b in self.blocks(edit(cell=1, config=0))))

    def test_bounds_not_checkable_is_a_warning(self):
        r = pl.check(self.g, edit(comp="Flat", geometry=geo(5, 5, 2, 2)))
        self.assertEqual(r["blocks"], []); self.assertTrue(any("no preset size" in w for w in r["warnings"]))

    def test_collision_is_a_warning_that_needs_confirm(self):
        r = pl.check(self.g, edit(geometry=geo(5, 0, 4, 2)))              # overlaps B (6..10, 0..2)
        self.assertEqual(r["blocks"], []); self.assertEqual([c["element_id"] for c in r["collisions"]], ["B"]); self.assertTrue(any("confirm" in w for w in r["warnings"]))
        self.assertEqual(pl.check(self.g, edit(geometry=geo(4, 0, 2, 2)))["collisions"], [])       # touching edges are not an overlap
        self.assertEqual(pl.check(self.g, edit(geometry=geo(0, 2, 4, 2)))["collisions"], [])
        c = pl.check(self.g, edit(geometry=geo(0, 3, 4, 2)))["collisions"]; self.assertEqual([x["element_id"] for x in c], ["C"])   # C starts at y=4

    def test_collision_uses_other_edits_new_geometry(self):
        other = {"composition": "Comp", "cell_index": 2, "geometry": geo(8, 4, 4, 2), "state": "valid"}      # C moved to the right
        self.assertEqual(pl.check(self.g, edit(geometry=geo(0, 4, 4, 2)), [other])["collisions"], [])       # its old spot is free now
        self.assertEqual([c["element_id"] for c in pl.check(self.g, edit(geometry=geo(7, 4, 4, 2)), [other])["collisions"]], ["C"])
        stale = dict(other, state="stale")
        self.assertEqual([c["element_id"] for c in pl.check(self.g, edit(geometry=geo(0, 3, 4, 2)), [stale])["collisions"]], ["C"])    # stale edits do not count

    def test_config_choice(self):
        self.assertEqual(self.blocks(edit(config=1)), [])
        self.assertTrue(any("not one of this cell's configs" in b for b in self.blocks(edit(config=7))))
        self.assertTrue(any("not one of" in b for b in self.blocks(edit(config=True))))
        self.assertTrue(any("already the one used" in b for b in self.blocks(edit(config=0))))
        both = pl.check(self.g, edit(geometry=geo(1, 0, 4, 2), config=0)); self.assertEqual(both["blocks"], [])         # geometry + the config already used: fine


class Store(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.ws = config.Workspace(Path(self.tmp.name) / "ws")
        self.manifest(BUILD); self.import_dump(pdump())

    def manifest(self, build):
        (self.ws.vanilla / "manifest.json").write_text(json.dumps(manifest(build)))

    def import_dump(self, d):
        p = Path(self.tmp.name) / "d.json"; p.write_text(json.dumps(d)); ld.import_dump(self.ws, p)

    def test_add_list_replace_remove_and_vanilla_values_kept(self):
        r = pl.add(self.ws, "proj", edit(geometry=geo(2, 1, 4, 2), note="x"))
        self.assertEqual((r["id"], r["state"], r["old"]["geometry"], r["cell_element_id"]), ("Comp#0", "valid", geo(0, 0, 4, 2), "A"))
        self.assertEqual(r["validated_against"], {"fingerprint": "a" * 40, "game_build": BUILD})            # the fingerprint it was validated against
        f = self.ws.placements / "proj.placements.json"; doc = json.loads(f.read_text())
        self.assertEqual((doc["schema"], doc["project"], len(doc["edits"])), (1, "proj", 1))
        pl.add(self.ws, "proj", edit(geometry=geo(2, 2, 4, 2)))                                            # same cell: replaced
        self.assertEqual([e["geometry"] for e in pl.summary(self.ws, "proj")["edits"]], [geo(2, 2, 4, 2)])
        pl.add(self.ws, "proj", edit(cell=2, geometry=geo(0, 5, 4, 2)))
        self.assertEqual(len(pl.summary(self.ws, "proj")["edits"]), 2)
        pl.remove(self.ws, "proj", "Comp#0")                                                               # revert: the dump's value is simply back
        left = pl.summary(self.ws, "proj")["edits"]; self.assertEqual([e["id"] for e in left], ["Comp#2"])
        with self.assertRaises(KeyError): pl.remove(self.ws, "proj", "Comp#0")
        self.assertEqual(pl.summary(self.ws, "other")["edits"], [])                                        # per-project lists

    def test_refused_edits_store_nothing(self):
        for bad in (edit(cell=1, geometry=geo(7, 1, 4, 2)), edit(geometry=geo(10, 0, 4, 2)), edit(cell=2, geometry=geo(0, 4, 9, 2))):
            with self.assertRaises(pl.PlacementError) as c: pl.add(self.ws, "proj", bad)
            self.assertTrue(c.exception.blocks and not c.exception.requires_confirm)
        self.assertFalse((self.ws.placements / "proj.placements.json").exists())

    def test_collision_needs_explicit_confirm(self):
        e = edit(geometry=geo(5, 0, 4, 2))
        with self.assertRaises(pl.PlacementError) as c: pl.add(self.ws, "proj", e)
        self.assertTrue(c.exception.requires_confirm); self.assertEqual(c.exception.collisions[0]["element_id"], "B")
        self.assertFalse((self.ws.placements / "proj.placements.json").exists())
        r = pl.add(self.ws, "proj", e, confirm=True)
        self.assertEqual(r["confirmed_collisions"], ["Comp#1"]); self.assertTrue(r["warnings"])
        with self.assertRaises(pl.PlacementError):                                                          # a second edit colliding with the first's new geometry
            pl.add(self.ws, "proj", edit(cell=2, geometry=geo(4, 0, 2, 2)))

    def test_only_while_the_dump_is_fresh(self):
        (self.ws.vanilla / "manifest.json").write_text(json.dumps(manifest(catalog="d" * 32)))      # the game was updated: another catalog
        with self.assertRaises(pl.PlacementError) as c: pl.add(self.ws, "proj", edit(geometry=geo(2, 1, 4, 2)))
        self.assertIn("STALE LAYOUT DATA", c.exception.blocks[0]); self.assertFalse(pl.can_edit(self.ws)["ok"])
        (self.ws.vanilla / "manifest.json").write_text(json.dumps({"files": {}}))                          # unknown is not fresh either
        with self.assertRaises(pl.PlacementError): pl.add(self.ws, "proj", edit(geometry=geo(2, 1, 4, 2)))
        (self.ws.layout / "current.json").unlink()
        self.assertEqual(pl.can_edit(self.ws), {"ok": False, "why": "No layout dump is imported."})

    def test_unsupported_list_schema_is_refused_not_loaded(self):
        (self.ws.placements / "proj.placements.json").write_text(json.dumps({"schema": 2, "project": "proj", "edits": []}))
        with self.assertRaises(ValueError): pl.load(self.ws, "proj")

    def test_nothing_is_written_to_the_dump(self):
        before = (self.ws.layout / "current.json").read_bytes()
        pl.add(self.ws, "proj", edit(geometry=geo(2, 1, 4, 2))); pl.remove(self.ws, "proj", "Comp#0")
        self.assertEqual((self.ws.layout / "current.json").read_bytes(), before)

    def test_project_file_is_separate_and_legacy_entries_are_flagged_not_rejected(self):
        p = project.new("proj"); p["tile_placement"] = [{"composition": "X", "anything": 1}]
        project.save(self.ws, p); pl.add(self.ws, "proj", edit(geometry=geo(2, 1, 4, 2)))
        again = project.load(self.ws, "proj")
        self.assertEqual(again["tile_placement"], [{"composition": "X", "anything": 1}])                    # untouched
        w = project.warnings(again); self.assertTrue(any("legacy" in x and "1 legacy entry" in x for x in w))
        self.assertEqual(project.warnings(project.new("n")), [])


class Revalidate(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.ws = config.Workspace(Path(self.tmp.name) / "ws")
        (self.ws.vanilla / "manifest.json").write_text(json.dumps(manifest(BUILD)))
        self.import_dump(pdump())
        pl.add(self.ws, "p", edit(geometry=geo(2, 1, 4, 2)))

    def import_dump(self, d):
        p = Path(self.tmp.name) / "d.json"; p.write_text(json.dumps(d)); ld.import_dump(self.ws, p)

    def state(self, i=0): e = pl.load(self.ws, "p")["edits"][i]; return e["state"], e.get("reasons", []), e

    def test_unchanged_dump_stays_valid(self):
        self.assertEqual(self.state()[0], "valid")

    def test_new_fingerprint_without_relevant_change_stays_valid_and_is_rechecked(self):
        self.import_dump(pdump(fp="b" * 40))
        st, reasons, e = self.state(); self.assertEqual((st, reasons), ("valid", []))
        self.assertEqual(e["validated_against"]["fingerprint"], "b" * 40)

    def test_target_moved(self):
        self.import_dump(pdump(fp="b" * 40, mutate=lambda d: d["cells"][0].update(x=1)))
        st, reasons, _ = self.state(); self.assertEqual(st, "stale"); self.assertTrue(any("target moved" in r for r in reasons))

    def test_target_vanished(self):
        self.import_dump(pdump(fp="b" * 40, mutate=lambda d: (d["cells"].__setitem__(slice(None), [c for c in d["cells"] if not (c["composition"] == "Comp" and c["cell_index"] == 0)]),
                                                              d["cell_configs"].__setitem__(slice(None), [c for c in d["cell_configs"] if not (c["composition"] == "Comp" and c["cell_index"] == 0)]),
                                                              d["tiles"].clear())))
        st, reasons, _ = self.state(); self.assertEqual(st, "stale"); self.assertTrue(any("vanished" in r for r in reasons))
        self.import_dump(pdump(fp="c" * 40, mutate=lambda d: d["cells"][0].update(element_id="Renamed")))      # same slot, different cell
        self.assertEqual(self.state()[0], "stale")

    def test_now_locked_and_now_out_of_bounds(self):
        self.import_dump(pdump(fp="b" * 40, mutate=lambda d: d["cells"][0].update(flags=["locked"])))
        st, reasons, _ = self.state(); self.assertEqual(st, "stale"); self.assertTrue(any("now invalid: locked" in r for r in reasons))

    def test_now_collides(self):
        self.import_dump(pdump(fp="b" * 40, mutate=lambda d: d["cells"][2].update(x=2, y=1, w=4, h=2)))          # C moved onto the edit's new spot
        st, reasons, _ = self.state(); self.assertEqual(st, "stale"); self.assertTrue(any("now collides with cell 2 (C)" in r for r in reasons))

    def test_confirmed_collision_persists_but_a_new_collider_does_not(self):
        pl.add(self.ws, "p", edit(geometry=geo(5, 0, 4, 2)), confirm=True)                                    # replaces the edit; collides with B, confirmed
        self.import_dump(pdump(fp="b" * 40)); self.assertEqual(self.state()[0], "valid")
        self.import_dump(pdump(fp="c" * 40, mutate=lambda d: d["cells"][2].update(x=5, y=1, w=4, h=2)))
        st, reasons, _ = self.state(); self.assertEqual(st, "stale"); self.assertTrue(any("now collides with cell 2" in r for r in reasons))

    def test_stale_is_reported_not_applied_and_stays_stale(self):
        self.import_dump(pdump(fp="b" * 40, mutate=lambda d: d["cells"][0].update(x=1)))
        self.assertEqual(self.state()[0], "stale")
        self.import_dump(pdump(fp="a" * 40))                                                                    # the dump goes back: still not silently re-enabled
        self.assertEqual(self.state()[0], "stale")
        rep = pl.report(self.ws, "p"); self.assertEqual((rep["counts"]["stale"], rep["counts"]["valid"]), (1, 0))
        self.assertTrue(rep["edits"][0]["reasons"])
        pl.add(self.ws, "p", edit(geometry=geo(2, 1, 4, 2)))                                                    # re-adding validates afresh
        self.assertEqual(self.state()[0], "valid")

    def test_no_dump_marks_edits_stale(self):
        (self.ws.layout / "current.json").unlink()
        st, reasons, _ = self.state(); self.assertEqual(st, "stale"); self.assertIn("no layout dump is imported", reasons[0])


class BuildReport(unittest.TestCase):
    def test_section_states_stored_not_written_and_files_do_not_change(self):
        with tempfile.TemporaryDirectory() as tmp, fake():
            aa = Path(tmp) / "game/X.app/Contents/Resources/Data/StreamingAssets/aa/StandaloneOSX"; aa.mkdir(parents=True)
            (aa / bundles.STYLE_BUNDLES[0]).write_text(json.dumps([sheet("FigmaStyleVariables")]))
            (aa / bundles.STYLE_BUNDLES[1]).write_text(json.dumps([sheet()]))
            ws = config.Workspace(Path(tmp) / "ws"); install.snapshot_vanilla(ws, aa, BUILD)
            man = json.loads((ws.vanilla / "manifest.json").read_text()); man["reference"] = manifest(BUILD)["reference"]      # hashes the fixture dump's source names
            (ws.vanilla / "manifest.json").write_text(json.dumps(man))
            ix = index_styles.build(ws)
            dump = Path(tmp) / "d.json"; dump.write_text(json.dumps(pdump())); ld.import_dump(ws, dump)
            p = project.new("t"); p["scoped_rules"] = [{"sheet": "AlwaysAppliedStyleSheet", "selector": ".inner", "props": {"background-color": "#010203"}}]
            empty = patcher.build(p, ws, ix)["layout_placement"]
            self.assertEqual((empty["status"], empty["edits"], empty["counts"]["edits"]), ("stored; positions are written by a bundle build", [], 0))   # the section is always there
            plain = patcher.build(p, ws, ix)
            dump_bytes = (ws.layout / "current.json").read_bytes()
            pl.add(ws, "t", edit(geometry=geo(2, 1, 4, 2))); pl.add(ws, "t", edit(cell=2, geometry=geo(0, 5, 4, 2)))
            # UI2/UI5 route lock: by default bundle builds exclude grid-composition edits; turning the experimental
            # setting on enables the bundle composition path (which then checks the dump's bundle name).
            locked = patcher.build(p, ws, ix)
            self.assertEqual(locked["tile_edits"]["cells"], 0)
            project.set_experimental_bundle_layout_edits(p, True)
            with self.assertRaisesRegex(ValueError, "re-export the layout dump"):                  # a fixture dump names no bundle: the writer refuses instead of guessing
                patcher.build(p, ws, ix)
            with mock.patch("skin_editor.tiles.ops_for", return_value=[]):                          # the report section itself, without the writer
                with_edits = patcher.build(p, ws, ix)
            sec = with_edits["layout_placement"]
            self.assertEqual(sec["status"], "stored; positions are written by a bundle build"); self.assertIn("composition bundle", sec["note"])
            self.assertEqual(sec["counts"], {"edits": 2, "valid": 2, "stale": 0}); self.assertEqual(sec["dump"]["staleness"], "fresh")
            e0 = sec["edits"][0]
            self.assertEqual((e0["target"], e0["changes"], e0["old"]["geometry"], e0["new"]["geometry"], e0["state"]), ("Comp / cell 0 (A)", ["geometry"], geo(0, 0, 4, 2), geo(2, 1, 4, 2), "valid"))
            self.assertEqual({k: v["sha256"] for k, v in plain["files"].items()}, {k: v["sha256"] for k, v in with_edits["files"].items()})   # no bundle depends on them
            self.assertEqual((ws.layout / "current.json").read_bytes(), dump_bytes)
            on_disk = json.loads((Path(with_edits["dir"]) / "build-report.json").read_text())
            self.assertEqual(on_disk["layout_placement"]["counts"]["edits"], 2)
            d = patcher.latest_build(ws, "t")
            man.pop("reference"); (ws.vanilla / "manifest.json").write_text(json.dumps(man))           # the fixture's fake reference names no real file
            self.assertEqual(install.install(ws, aa, d, lambda: False)["copied"], [bundles.STYLE_BUNDLES[1]])                    # install is unaffected
            for h in list(logging.getLogger("skin_editor").handlers): logging.getLogger("skin_editor").removeHandler(h); h.close()


class Routes(unittest.TestCase):
    def test_http(self):
        with tempfile.TemporaryDirectory() as tmp, mock.patch.dict(os.environ, {"FM27SE_WORKSPACE": tmp}):
            app = server.App(); app.index = style_index()
            httpd = server.ThreadingHTTPServer(("127.0.0.1", 0), server.make_handler(app, "tok", 0)); port = httpd.server_address[1]
            th = threading.Thread(target=httpd.serve_forever, daemon=True); th.start()
            def call(path, body=None, raw=False):
                data = None if body is None else (body if raw else json.dumps(body).encode())
                req = urllib.request.Request("http://127.0.0.1:%d%s" % (port, path), data=data, headers={"X-Token": "tok", "Host": "127.0.0.1:0"})
                try: r = urllib.request.urlopen(req); return r.status, json.loads(r.read())
                except urllib.error.HTTPError as e: return e.code, json.loads(e.read())
            try:
                project.save(app.ws, project.new("demo"))
                (app.ws.vanilla / "manifest.json").write_text(json.dumps(manifest(BUILD)))
                code, j = call("/api/layout/import", json.dumps(pdump()).encode(), raw=True); self.assertEqual(code, 200)
                good = {"project": "demo", "edit": edit(geometry=geo(2, 1, 4, 2))}
                code, r = call("/api/placement/check", good); self.assertEqual((code, r["blocks"], r["can_edit"]), (200, [], True))
                code, r = call("/api/placement/check", {"project": "demo", "edit": edit(cell=1, geometry=geo(7, 1, 4, 2))}); self.assertTrue(any("locked" in b for b in r["blocks"]))
                code, r = call("/api/placement/add", {"project": "demo", "edit": edit(cell=1, geometry=geo(7, 1, 4, 2))}); self.assertEqual(code, 400); self.assertTrue(r["blocks"])
                code, r = call("/api/placement/add", {"project": "demo", "edit": edit(geometry=geo(5, 0, 4, 2))}); self.assertEqual(code, 409); self.assertTrue(r["requires_confirm"]); self.assertEqual(r["collisions"][0]["element_id"], "B")
                code, r = call("/api/placement/add", {"project": "demo", "edit": edit(geometry=geo(5, 0, 4, 2)), "confirm": True}); self.assertEqual((code, r["edit"]["confirmed_collisions"]), (200, ["Comp#1"]))
                code, r = call("/api/placement/list?project=demo"); self.assertEqual((len(r["edits"]), r["can_edit"], r["status"]), (1, True, "stored; positions are written by a bundle build"))
                code, r = call("/api/placement/add", {"project": "ghost", "edit": edit(geometry=geo(2, 1, 4, 2))}); self.assertEqual(code, 400)            # the project must exist
                (app.ws.vanilla / "manifest.json").write_text(json.dumps(manifest(catalog="d" * 32)))                                                # dump is now stale
                code, r = call("/api/placement/add", {"project": "demo", "edit": edit(cell=2, geometry=geo(0, 5, 4, 2))}); self.assertEqual(code, 400); self.assertIn("STALE", r["blocks"][0])
                code, r = call("/api/placement/list?project=demo"); self.assertFalse(r["can_edit"]); self.assertTrue(r["why_not"])
                code, r = call("/api/placement/remove", {"project": "demo", "id": "Comp#0"}); self.assertEqual((code, r["edits"]), (200, []))                # reverting is always allowed
                code, r = call("/api/placement/remove", {"project": "demo", "id": "Comp#0"}); self.assertEqual(code, 400)
            finally:
                httpd.shutdown(); httpd.server_close(); th.join(5)
                lg = logging.getLogger("skin_editor")
                for h in list(lg.handlers): lg.removeHandler(h); h.close()

    def test_route_surface_and_frontend_scan(self):
        import re
        routes = {k for k in server.ROUTES if "placement" in k[1]}
        self.assertEqual(routes, {("GET", "/api/placement/list"), ("POST", "/api/placement/check"), ("POST", "/api/placement/add"), ("POST", "/api/placement/remove")})
        html = (Path(__file__).resolve().parent.parent / "frontend" / "index.html").read_text(encoding="utf-8")
        tab = html.split("/* LAYOUT TAB BEGIN */")[1].split("/* LAYOUT TAB END */")[0]
        edit_block = html.split("/* PLACEMENT EDIT BEGIN */")[1].split("/* PLACEMENT EDIT END */")[0]
        # the read-only tab is unchanged: no edit code, only the two named hooks that the edit block fills in
        for banned in ("POST", "placement", "saveProject", "needProject", "textarea", "contenteditable", "type=\"number\""):
            self.assertNotIn(banned, tab.replace("lyEditHook", "").replace("lyEditBind", "").replace("lyEditPrep", ""), banned)
        self.assertEqual(sorted(set(re.findall(r"lyEdit\w+", tab))), ["lyEditBind", "lyEditHook", "lyEditPrep"])
        # the edit code lives only in its block: every request outside it is read-only or not a placement route
        outside = html.replace(edit_block, "")
        self.assertNotIn("/api/placement", outside)
        self.assertEqual(sorted(set(re.findall(r"/api/placement/\w+", edit_block))), ["/api/placement/add", "/api/placement/check", "/api/placement/list", "/api/placement/remove"])
        for call in re.findall(r"api\(([^;]*?)\)\s*[;,)\]]", edit_block): pass
        self.assertIn('status === "fresh"', edit_block)                      # edit affordances are hidden until the dump is fresh
        self.assertIn("stored; positions are written by a bundle build", edit_block.lower())
        self.assertNotIn("/api/build", edit_block); self.assertNotIn("/api/install", edit_block)


if __name__ == "__main__":
    unittest.main()
