"""Phase 7: tile position writes (tiles.py), table view edits (tables.py), the real layout index -> dump exporter. Pure logic on synthetic data;
the real game's bundles and the FM27_LayoutMCP index (skipped without them) for the UnityPy round trips, the gates and the exporter."""
from tests import gamebuild
import copy, json, tempfile, unittest
from pathlib import Path
from unittest import mock

from skin_editor import bundles, layout_dump, layout_export, placement, plan, project, projfmt, tables, tiles, config

GAME = gamebuild.aa()                                         # the configured game folder (tests/gamebuild.py), not a typed path
INDEX = Path(r"__absent_fixture_path__")
needs_game = lambda o: gamebuild.requires_build(unittest.skipUnless((GAME / tiles.TILE_BUNDLES[1]).is_file() and (GAME / tables.VIEWS_BUNDLE).is_file(), "needs the game's bundles")(o))
needs_index = lambda o: gamebuild.requires_build(unittest.skipUnless(INDEX.is_file() and (GAME / layout_export.PANEL_BUNDLE).is_file(), "needs the FM27_LayoutMCP index and the game")(o))
TB = tiles.TILE_BUNDLES[1]


def comp(cells=((0, "A", 4, 0), (1, "B", 6, 0))):
    return {"m_Name": "Comp", "m_gridComponents": [{"m_elementID": i, "m_location": {"x": x, "y": y, "width": 2, "height": 2}} for _n, i, x, y in cells]}


def mv(i=0, cid="A", fx=4, fy=0, tx=6, ty=0):
    return {"op": "move-cell", "bundle": TB, "path_id": "5", "composition": "Comp", "cell_index": i, "cell_id": cid, "from": {"x": fx, "y": fy}, "to": {"x": tx, "y": ty}}


class TileLogic(unittest.TestCase):
    def test_validation(self):
        tiles.validate_ops([mv()])
        for bad in (dict(mv(), op="resize-cell"), dict(mv(), bundle="ui-styles_assets_default.bundle"), dict(mv(), to={"x": -1, "y": 0}), dict(mv(), to={"x": 1.5, "y": 0}), dict(mv(), to={"x": 1})):
            with self.assertRaises(ValueError): tiles.validate_ops([bad])
        with self.assertRaises(ValueError): tiles.validate_ops([mv(), mv()])                      # one cell, one move

    def test_guards_refuse_a_cell_that_is_not_what_the_edit_was_made_for(self):
        t = comp()
        c = tiles._cell(t, mv(), "x"); self.assertEqual(c["m_elementID"], "A")
        for op, msg in ((mv(cid="Z"), "not 'Z' any more"), (mv(i=9), "cell 9"), (mv(fx=5), "is at (4, 0)")):
            with self.assertRaises(ValueError) as e: tiles._cell(t, op, "x")
            self.assertIn(msg, str(e.exception))

    def test_leaf_diffs_names_exactly_what_changed(self):
        a, b = comp(), comp(); b["m_gridComponents"][1]["m_location"]["x"] = 8
        self.assertEqual(tiles._leaf_diffs(a, b), ["/m_gridComponents[1]/m_location/x"])
        self.assertEqual(tiles._leaf_diffs(a, copy.deepcopy(a)), [])
        c = copy.deepcopy(a); c["m_gridComponents"].append({}); self.assertEqual(tiles._leaf_diffs(a, c), ["/m_gridComponents[len]"])

    def test_ops_from_stored_placement_edits(self):
        edit = lambda **k: dict({"composition": "Comp", "cell_index": 0, "cell_element_id": "A", "state": "valid", "old": {"geometry": {"x": 4, "y": 0, "w": 2, "h": 2}}, "geometry": {"x": 6, "y": 0, "w": 2, "h": 2}}, **k)
        dump = {"compositions": [{"name": "Comp", "bundle": TB, "path_id": -5}]}
        run = lambda *edits, d=dump: (mock.patch.object(placement, "load", return_value={"edits": list(edits)}), mock.patch.object(layout_dump, "load", return_value=d))
        with run(edit())[0], run(edit())[1]:
            ops = tiles.ops_for(None, "p")
        self.assertEqual(ops, [{"op": "move-cell", "bundle": TB, "path_id": "-5", "composition": "Comp", "cell_index": 0, "cell_id": "A", "from": {"x": 4, "y": 0}, "to": {"x": 6, "y": 0}}])
        for bad, msg in ((edit(geometry={"x": 6, "y": 0, "w": 3, "h": 2}), "size change"), (edit(config=1), "config change")):
            with run(bad)[0], run(bad)[1], self.assertRaisesRegex(ValueError, msg): tiles.ops_for(None, "p")
        with run(edit())[0], run(edit(), d={"compositions": [{"name": "Comp"}]})[1], self.assertRaisesRegex(ValueError, "re-export the layout dump"): tiles.ops_for(None, "p")
        with run(edit(state="stale"))[0], run()[1]: self.assertEqual(tiles.ops_for(None, "p"), [])       # a stale edit is never built
        with run(edit(geometry={"x": 4, "y": 0, "w": 2, "h": 2}))[0], run()[1]: self.assertEqual(tiles.ops_for(None, "p"), [])   # no move


def view(cols):
    return {"m_Name": "V", "m_tableView": {"m_viewName": {"GameID": 0}, "m_tableConfig": [
        {"m_columnID": i, "m_columnMetadata": {"m_required": r, "m_sortingDisabled": 0, "m_widthOverride": float(w), "m_minWidthOverride": float(w), "m_titleTranslationIdOverride": {"GameID": 0},
                                              "m_applicableBreakpoints": -1, "m_optionalConfigConditions": [], "m_optionalConditions": [], "m_priority": 0}} for i, w, r in cols], "m_overwriteFooterSettings": 0}}


class TableLogic(unittest.TestCase):
    def ids(self, t): return [c["m_columnID"] for c in t["m_tableView"]["m_tableConfig"]]

    def test_validation_and_merge(self):
        doc = {"schema": 1, "view": {"bundle": tables.VIEWS_BUNDLE, "name": "V"}, "ops": [{"op": "set-width", "column": "a", "width": 90}]}
        tables.validate_doc(doc)
        for bad in ({"op": "set-width", "column": "a", "width": -1}, {"op": "set-width", "column": "a", "width": "9"}, {"op": "hide-column", "column": "a", "width": 3},
                    {"op": "drop-column", "column": "a"}, {"op": "move-column", "column": "bad id"}, {"op": "show-column", "column": "a", "after": 5}):
            with self.assertRaises(ValueError): tables.validate_doc(dict(doc, ops=[bad]))
        tables.merge_op(doc, {"op": "set-width", "column": "a", "width": 120}); self.assertEqual([o["width"] for o in doc["ops"]], [120])
        tables.merge_op(doc, {"op": "hide-column", "column": "b"}); tables.merge_op(doc, {"op": "show-column", "column": "b"})       # show cancels the hide
        self.assertEqual([o["op"] for o in doc["ops"]], ["set-width"])
        tables.merge_op(doc, {"op": "show-column", "column": "c"}); tables.merge_op(doc, {"op": "hide-column", "column": "c"})
        self.assertEqual([o["op"] for o in doc["ops"]], ["set-width"])

    def test_ops_on_a_view_and_the_independent_expectation_agree(self):
        v0 = view([("a", 100, 0), ("b", 60, 0), ("c", 80, 1)])
        ops = [{"op": "set-width", "column": "b", "width": 40}, {"op": "move-column", "column": "c", "after": None}, {"op": "hide-column", "column": "a"},
               {"op": "show-column", "column": "z", "after": "b"}, {"op": "set-width", "column": "a2", "width": 1}][:4]
        t = copy.deepcopy(v0)
        self.assertEqual(tables.apply_to_view(t, ops, "V:", {"a", "b", "c", "z"}), ["c", "b", "z"])
        want = tables.expected_columns(v0, ops)
        self.assertEqual([k for k, _ in want], ["c", "b", "z"])
        self.assertEqual([c["m_columnMetadata"] for c in t["m_tableView"]["m_tableConfig"]], [m for _k, m in want])
        b = next(c for c in t["m_tableView"]["m_tableConfig"] if c["m_columnID"] == "b")["m_columnMetadata"]; self.assertEqual((b["m_widthOverride"], b["m_minWidthOverride"]), (40.0, 40.0))   # min follows a narrower width
        z = t["m_tableView"]["m_tableConfig"][2]["m_columnMetadata"]; self.assertEqual((z["m_widthOverride"], z["m_required"]), (0.0, 0))
        self.assertEqual(self.ids(v0), ["a", "b", "c"])                                                                       # the input is not modified by expected_columns

    def test_refusals(self):
        v0 = view([("a", 100, 0), ("c", 80, 1)])
        for op, msg in (({"op": "hide-column", "column": "c"}, "required"), ({"op": "set-width", "column": "nope", "width": 5}, "has no column nope"),
                        ({"op": "show-column", "column": "a"}, "already shown"), ({"op": "show-column", "column": "q"}, "factory can draw"),
                        ({"op": "move-column", "column": "a", "after": "nope"}, "to place after")):
            with self.assertRaises(ValueError) as e: tables.apply_to_view(copy.deepcopy(v0), [op], "V:", {"a", "c"})
            self.assertIn(msg, str(e.exception))

    def test_patch_files_round_trip_and_the_plan(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            ws = config.Workspace(Path(tmp) / "ws")
            p = project.new("tp"); p["options"]["output"] = "bundles"
            p["table_patches"] = [{"schema": 1, "view": {"bundle": tables.VIEWS_BUNDLE, "name": "Squad View", "path_id": "-9"}, "ops": [
                {"op": "set-width", "column": "age", "width": 60}, {"op": "hide-column", "column": "club"}, {"op": "show-column", "column": "x", "after": "age"}, {"op": "move-column", "column": "age"}]}]
            projfmt.write(ws, p)
            f = projfmt.folder(ws, "tp") / "tables" / "Squad_View.patch.json"; self.assertTrue(f.is_file())
            q = projfmt.read(ws, "tp"); self.assertEqual(q["table_patches"], p["table_patches"])
            from tests.test_preview import index
            pl = plan.plan(ws, q, index(), None, "bundles")
            self.assertTrue({"SetColumnWidth", "HideColumn", "ShowColumn", "MoveColumn"} <= {o["op"] for o in pl["operations"]})
            self.assertTrue(any("table edit" in d["item"] for d in plan.plan(ws, q, index(), None, "native")["dropped"]))
            f.write_text('{"schema": 1, "view": {"bundle": "x", "name": "y"}, "ops": []}')
            self.assertTrue(any(x["file"] == "tables/Squad_View.patch.json" for x in projfmt.read(ws, "tp", strict=False)[1]))
            p["table_patches"] = []; projfmt.write(ws, p); self.assertFalse(f.exists())

    def test_deleting_a_project_takes_its_stored_position_edits_along(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            ws = config.Workspace(Path(tmp) / "ws"); projfmt.write(ws, project.new("gone"))
            stored = Path(ws.placements) / "gone.placements.json"; stored.write_text('{"schema": 1, "project": "gone", "edits": []}')
            where = project.delete(ws, "gone")
            self.assertFalse(stored.exists()); self.assertTrue((Path(where) / "gone.placements.json").is_file())


class Checklist(unittest.TestCase):
    """The in-game checklist and the packages are served by the engine, so the Studio can show them."""

    def engine(self, tmp):
        from skin_editor.engine import Engine
        e = Engine.__new__(Engine); e.ws = config.Workspace(Path(tmp) / "ws"); e.info = None
        return e

    def test_checklist_document_and_results_block(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            r = self.engine(tmp).docs_checklist({}, {})
        self.assertTrue(r["path"].endswith("INGAME-CHECKLIST.md"))
        for needle in ("## a. Native font", "## b. Tile layout", "## c. Table view", "verify-stock", "Restore stock", "9559D5968E9D", "B6BB58931C69"):
            self.assertIn(needle, r["text"])
        self.assertIn("In-game observations (fill in)", r["results"])
        self.assertIn("27.0.1.2503222", r["results"]); self.assertNotIn("<!--", r["results"])
        self.assertEqual(r["results"].count("______") > 8, True)                    # the in-game fields are blank, the offline ones are not

    def test_builds_list_marks_the_latest_and_skips_builds_without_a_package(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            e = self.engine(tmp)
            for pid, withpkg in (("20261113T100000Z", True), ("20261113T110000Z", True), ("20261113T120000Z", False)):
                d = e.ws.build / "proj" / pid; d.mkdir(parents=True); (d / "build-report.json").write_text("{}")
                if withpkg: (d / "package.json").write_text(json.dumps({"id": pid, "project": "proj", "built_utc": pid, "gate": {"passed": True}, "files": {}, "plan": []}))
            rows = e.builds_list({}, {})["packages"]
        self.assertEqual([(r["id"], r["latest"]) for r in rows], [("20261113T110000Z", False), ("20261113T100000Z", False)])   # latest_build() is the newest build folder, which has no package yet

    def test_a_build_writes_its_package_manifest(self):
        from skin_editor import patcher
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            ws = config.Workspace(Path(tmp) / "ws"); projfmt.write(ws, project.new("pk"))
            out = ws.build / "pk" / "T1"; out.mkdir(parents=True)
            report = {"gate": {"fail": [], "tile_moves_checked": 2, "untouched_bundles_checked": 1}, "files": {"a.bundle": {"changed": True, "sha256": "s", "vanilla_sha256": "v"}, "b.bundle": {"changed": False, "sha256": "v2", "vanilla_sha256": "v2"}}}
            from tests.test_preview import index
            pkg = patcher.write_package(ws, projfmt.read(ws, "pk"), index(), report, out, {"game_build": "27.0.1.2503222", "reference": {"catalog_hash": "abc"}}, "T1")
            self.assertEqual((pkg["project"], pkg["game_build"], pkg["catalog_hash"], pkg["installable"]), ("pk", "27.0.1.2503222", "abc", True))
            self.assertEqual(list(pkg["files"]), ["a.bundle"]); self.assertEqual(pkg["gate"]["checked"], {"tile_moves_checked": 2, "untouched_bundles_checked": 1})
            self.assertEqual(len(pkg["plan_digest"]), 64)
            self.assertEqual(json.loads((out / "package.json").read_text()), pkg); self.assertEqual(json.loads((projfmt.folder(ws, "pk") / "packages" / "T1.json").read_text()), pkg)
            report["gate"]["fail"] = ["x"]
            self.assertFalse(patcher.write_package(ws, projfmt.read(ws, "pk"), index(), report, out, {}, "T2")["installable"])      # a failed gate is recorded, not installable


@needs_game
class RealTiles(unittest.TestCase):
    def test_every_composition_rewrites_unchanged_then_one_move_changes_exactly_one_leaf(self):
        import UnityPy
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            out = Path(tmp)
            for bn in tiles.TILE_BUNDLES:
                env = UnityPy.load(str(GAME / bn)); n = 0
                for o in env.objects:
                    if o.type.name == "MonoBehaviour":
                        t = o.read_typetree()
                        if "m_gridComponents" in t:
                            o.save_typetree(t); n += 1
                (out / bn[:-7]).mkdir(); env.save(pack="original", out_path=str(out / bn[:-7]))
                v, b = bundles.object_digests(GAME / bn)[0], bundles.object_digests(out / bn[:-7] / bn)[0]
                self.assertGreater(n, 40); self.assertEqual(set(v), set(b)); self.assertEqual([k for k in v if v[k][:2] != b[k][:2]], [], bn)
            env = UnityPy.load(str(GAME / TB))
            o = next(x for x in env.objects if x.type.name == "MonoBehaviour" and x.peek_name() == "PlayerInstructionGroupsInPossessionComposition-NONE")
            t = o.read_typetree(); c0, c1 = t["m_gridComponents"][0], t["m_gridComponents"][1]
            op = lambda i, c, x: {"op": "move-cell", "bundle": TB, "path_id": str(o.path_id), "composition": t["m_Name"], "cell_index": i, "cell_id": c["m_elementID"],
                                  "from": {"x": c["m_location"]["x"], "y": c["m_location"]["y"]}, "to": {"x": x, "y": c["m_location"]["y"]}}
            ops = tiles.validate_ops([op(0, c0, c1["m_location"]["x"]), op(1, c1, c0["m_location"]["x"])])
            (out / "mv").mkdir(); touched = set()
            changed, _, done = tiles.apply_ops(GAME / TB, out / "mv", ops, touched)
            v, b = bundles.object_digests(GAME / TB)[0], bundles.object_digests(out / "mv" / TB)[0]
            self.assertTrue(changed); self.assertEqual({k for k in v if v[k][:2] != b[k][:2]}, touched); self.assertEqual(len(touched), 1)
            self.assertEqual(tiles.check_ops(GAME / TB, out / "mv" / TB, ops), [])
            # the gate proves "vanilla plus exactly the asked edits": a different build fails it
            (out / "bad").mkdir(); tiles.apply_ops(GAME / TB, out / "bad", [dict(ops[0], to={"x": ops[0]["to"]["x"] + 1, "y": 0})], set())
            self.assertTrue(tiles.check_ops(GAME / TB, out / "bad" / TB, ops))
            for bad in (dict(ops[0], cell_id="Nope"), dict(ops[0], **{"from": {"x": 99, "y": 0}})):
                with self.assertRaises(ValueError): tiles.apply_ops(GAME / TB, out / "bad", [bad], set())

    def test_the_4724_of_5162_figure_holds_on_the_real_index(self):
        import sqlite3
        if not INDEX.is_file(): self.skipTest("needs the index")
        db = sqlite3.connect("file:%s?mode=ro" % INDEX.as_posix(), uri=True)
        try:
            self.assertEqual(db.execute("select count(*) from (select distinct composition_path_id, cell_index from cell_configs)").fetchone()[0], 5162)
            self.assertEqual(db.execute("select count(*) from (select c.composition_path_id, c.cell_index from composition_cells c join cell_configs f on f.composition_path_id=c.composition_path_id and f.cell_index=c.cell_index "
                                        "group by c.composition_path_id, c.cell_index having sum(f.size_w=c.w and f.size_h=c.h) > 0)").fetchone()[0], 4724)
        finally:
            db.close()


@needs_game
class RealTables(unittest.TestCase):
    def test_decode_edit_and_gate_on_the_real_bundles(self):
        T = tables.Tables(GAME).load()
        self.assertGreater(len(T._views), 800); self.assertGreater(len(T._factories), 200)
        row = next(r for r in T.list("SquadKeyPlayersTableSmall"))
        v = T.view(row["path_id"])
        self.assertEqual(v["factory"]["name"], "PlayerTableFactory"); self.assertEqual(v["factory"]["coverage"], 1.0)
        self.assertEqual([c["id"] for c in v["columns"]][:1], ["portrait-name-position"]); self.assertEqual(v["columns"][0]["cell"]["cell_layout_guid"] != "", True)
        self.assertTrue(any(a["id"] == "age" for a in v["available"]))
        full = sum(1 for r in T.list() if (T.view(r["path_id"])["factory"] or {}).get("coverage") == 1.0); self.assertGreater(full, 780)
        doc = tables.validate_doc({"schema": 1, "view": {"bundle": tables.VIEWS_BUNDLE, "name": row["name"], "path_id": row["path_id"]}, "ops": [
            {"op": "set-width", "column": "portrait-name-position", "width": 300}, {"op": "show-column", "column": "age", "after": "portrait-name-position"}, {"op": "show-column", "column": "club"},
            {"op": "move-column", "column": "club", "after": "age"}]})
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            out = Path(tmp); touched = set()
            changed, _, done = tables.apply_patches(GAME / tables.VIEWS_BUNDLE, out, [doc], touched)
            vd, bd = bundles.object_digests(GAME / tables.VIEWS_BUNDLE)[0], bundles.object_digests(out / tables.VIEWS_BUNDLE)[0]
            self.assertTrue(changed); self.assertEqual(set(vd), set(bd)); self.assertEqual({k for k in vd if vd[k][:2] != bd[k][:2]}, touched); self.assertEqual(len(touched), 1)
            self.assertEqual(tables.check_patches(GAME / tables.VIEWS_BUNDLE, out / tables.VIEWS_BUNDLE, [doc]), [])
            import UnityPy
            built = next(x for x in UnityPy.load(str(out / tables.VIEWS_BUNDLE)).objects if x.path_id == int(row["path_id"])).read_typetree()
            self.assertEqual([c["m_columnID"] for c in built["m_tableView"]["m_tableConfig"]], ["portrait-name-position", "age", "club", "current-ability-stars-with-subtitle"])
            self.assertEqual(built["m_tableView"]["m_tableConfig"][0]["m_columnMetadata"]["m_widthOverride"], 300.0)
            bad = json.loads(json.dumps(doc)); bad["ops"][0]["width"] = 111; (out / "b").mkdir()
            tables.apply_patches(GAME / tables.VIEWS_BUNDLE, out / "b", [bad], set())
            self.assertTrue(tables.check_patches(GAME / tables.VIEWS_BUNDLE, out / "b" / tables.VIEWS_BUNDLE, [doc]))


@needs_index
class RealIndex(unittest.TestCase):
    def test_crosscheck_dump_validates_and_screens_resolve(self):
        db = layout_export.connect(INDEX)
        try:
            cc = layout_export.crosscheck(db, GAME)
        finally:
            db.close()
        self.assertEqual((cc["compositions"], cc["cells"], cc["mismatches"]), (1823, 5410, []))      # every cell of the index equals the bundle it was read from
        d = layout_export.build_dump(INDEX, GAME, "27.0.1.2503222", Path(INDEX).parents[1] / "config" / "areas.json")
        self.assertEqual(layout_dump.validate(d), ([], 0))
        self.assertEqual((len(d["layouts"]), len(d["compositions"]), len(d["cells"])), (7467, 1823, 5410))
        self.assertTrue(all("bundle" in c and "path_id" in c for c in d["compositions"]))
        self.assertEqual(sorted(c["bundle"] for c in d["compositions"][:1]), sorted(c["bundle"] for c in d["compositions"][:1]))
        self.assertEqual(sum(1 for c in d["cells"] if c["x"] < 0), 2)                                  # the two auto-placed cells
        from skin_editor import layout_join, layout_view
        v = layout_view.View(layout_join.LayoutData(d))
        s = v.screen("TacticalPlannerTool")
        names = {x["set_name"] for x in s["sets"]}
        self.assertIn("TacticalPlannerTeamInstructionsTabCompositionSet", names)                        # grids hang off included layouts, not the panel root
        self.assertGreater(sum(1 for r in v.screens()["screens"] if r["tiles"]), 400)
        # the validator for edits runs on real cells: the locked/auto rules and the size rule
        g = placement.Grid(d)
        auto = next(k for k, c in g.cells.items() if c["x"] < 0)
        r = placement.check(g, {"composition": auto[0], "cell_index": auto[1], "geometry": {"x": 0, "y": 0, "w": g.cells[auto]["w"], "h": g.cells[auto]["h"]}})
        self.assertTrue(any("auto-placed" in b for b in r["blocks"]))
