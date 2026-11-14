"""M5: the project overlay of the render (render/overlay.py) and the `render.invalidate` notifications (changes.py)."""
import copy
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from skin_editor import changes, config, project as project_mod, projfmt
from skin_editor.api import rpc
from skin_editor.render import overlay
from skin_editor.render.sheets import ROOT_SHEETS

from test_api import close_logs, engine

AA = Path(r"C:\Program Files (x86)\Steam\steamapps\common\Football Manager 27\fm_Data\StreamingAssets\aa\StandaloneWindows64")


class FakeBank:
    """Two root sheets: `default` defines a token and a rule; AlwaysAppliedStyleSheet uses the token."""
    def __init__(self):
        self.sheets = {
            "default": {"bundle": "d.bundle", "name": "default", "rules": [
                {"i": 0, "s": [":root"], "t": True, "p": [["--accent", "#112233ff", []], ["--other", "#445566ff", []]]}]},
            "AlwaysAppliedStyleSheet": {"bundle": "d.bundle", "name": "AlwaysAppliedStyleSheet", "rules": [
                {"i": 0, "s": [".card"], "t": False, "p": [["background-color", "var(--accent)", []], ["color", "#112233cc", []], ["opacity", "0.5", []]]},
                {"i": 1, "s": [".title"], "t": False, "p": [["font-size", "16px", []]]}]}}

    def entry(self, bundle, name):
        return self.sheets[name]


ORDER = [("d.bundle", "default", ""), ("d.bundle", "AlwaysAppliedStyleSheet", "")]


def proj(**kw):
    p = project_mod.new("t")
    p.update(kw)
    return project_mod.validate(project_mod.migrate(p))


def rules_of(sheets, name):
    return next(s for s in sheets if s.name == name).rules


class Sheets(unittest.TestCase):
    def test_a_token_override_replaces_the_definition_and_leaves_the_bank_untouched(self):
        bank = FakeBank()
        before = copy.deepcopy(bank.sheets)
        sheets, notes = overlay.build_sheets(bank, proj(token_overrides=[{"token": "--accent", "value": {"rgb": "#FF0000", "a": 1.0}}]), ORDER)
        self.assertEqual(rules_of(sheets, "default")[0]["props"][0][1].upper(), "#FF0000")
        self.assertEqual(bank.sheets, before)                                   # vanilla is never modified: the overlay works on copies
        self.assertEqual(notes, [])

    def test_a_token_with_no_definition_is_reported_not_silently_dropped(self):
        _, notes = overlay.build_sheets(FakeBank(), proj(token_overrides=[{"token": "--nope", "value": {"rgb": "#FF0000", "a": 1.0}}]), ORDER)
        self.assertTrue(any("--nope" in n for n in notes))

    def test_literal_swaps_keep_alpha_in_rgb_mode_and_match_exactly_in_rgba_mode(self):
        c = lambda h, a=1.0: {"rgb": h, "a": a}
        p = proj(literal_swaps=[{"from": c("#112233"), "to": c("#AA0000"), "mode": "rgb-keep-alpha"}])
        sheets, _ = overlay.build_sheets(FakeBank(), p, ORDER)
        texts = [pr[1].upper() for s in sheets for r in s.rules for pr in r["props"]]
        self.assertIn("#AA0000CC", texts)                                        # the cc alpha byte stays
        self.assertNotIn("#112233CC", texts)

    def test_appended_replaced_and_removed_rules_on_a_game_sheet(self):
        p = proj(scoped_rules=[
            {"sheet": "AlwaysAppliedStyleSheet", "selector": ".card", "props": {"padding-left": "4px"}},
            {"sheet": "AlwaysAppliedStyleSheet", "selector": ".title", "props": {"font-size": "20px"}, "op": "replace"},
            {"sheet": "AlwaysAppliedStyleSheet", "selector": ".card", "props": {}, "op": "remove", "remove": ["opacity"]}])
        sheets, notes = overlay.build_sheets(FakeBank(), p, ORDER)
        rs = rules_of(sheets, "AlwaysAppliedStyleSheet")
        self.assertEqual(rs[-1]["chains"][0][2], ".card")                        # appended last: it wins at equal specificity
        title = next(r for r in rs if r["props"] and r["props"][0][0] == "font-size" and r["props"][0][1] == "20px")
        self.assertTrue(title)
        card = rs[0]["props"]
        self.assertNotIn("opacity", [x[0] for x in card])                        # removed in place

    def test_native_output_adds_one_author_sheet_last_and_reports_edits_it_cannot_make(self):
        p = proj(token_overrides=[{"token": "--accent", "value": {"rgb": "#FF0000", "a": 1.0}}],
                 scoped_rules=[{"sheet": "AlwaysAppliedStyleSheet", "selector": ".title", "props": {"font-size": "20px"}, "op": "replace"},
                               {"sheet": "AlwaysAppliedStyleSheet", "selector": ".card", "props": {"padding-left": "4px"}}])
        p["options"]["output"] = "native"
        sheets, notes = overlay.build_sheets(FakeBank(), p, ORDER)
        self.assertEqual(len(sheets), 3)
        self.assertEqual(sheets[-1].name, "t (project)")
        self.assertEqual(rules_of(sheets, "default")[0]["props"][0][1].upper(), "#112233FF")      # the game's own definition is untouched
        self.assertTrue(any("do not exist in a native skin" in n for n in notes))

    def test_skipped_sheets_are_dropped_and_said(self):
        p = proj()
        p["options"]["skip_sheets"] = ["default"]
        sheets, notes = overlay.build_sheets(FakeBank(), p, ORDER)
        self.assertEqual([s.name for s in sheets], ["AlwaysAppliedStyleSheet"])
        self.assertTrue(any("default" in n for n in notes))

    def test_the_project_hash_changes_with_an_edit_and_not_with_a_rename(self):
        a = proj(token_overrides=[{"token": "--accent", "value": {"rgb": "#FF0000", "a": 1.0}}])
        b = copy.deepcopy(a)
        b["name"] = "renamed"
        c = copy.deepcopy(a)
        c["token_overrides"][0]["value"]["rgb"] = "#00FF00"
        self.assertEqual(overlay.project_hash(a), overlay.project_hash(b))
        self.assertNotEqual(overlay.project_hash(a), overlay.project_hash(c))


def n(i, layout, type_="VisualElement", name="", classes=(), inline=()):
    return {"id": i, "layout": layout, "type": type_, "name": name, "classes": list(classes), "inline": list(inline), "attrs": {}, "children": []}


class LayoutPatches(unittest.TestCase):
    def doc(self, *ops):
        return {"schema": 1, "layout": {"bundle": "ui-visualtreeassets_assets_x.bundle", "name": "L"}, "ops": list(ops)}

    def test_class_inline_and_attribute_ops_reach_the_node_by_id_and_layout(self):
        a, b = n(5, "L", name="card", classes=["x", "y"]), n(5, "Other", name="card", classes=["x"])
        top = [dict(n(1, "L"), children=[a, b])]
        g = {"type": "VisualElement", "name": "card"}
        applied, notes = overlay.apply_layout_patches(top, [self.doc(
            {"op": "set-classes", "id": 5, "guard": g, "add": ["z"], "remove": ["x"]},
            {"op": "set-inline", "id": 5, "guard": g, "props": {"height": "20px"}},
            {"op": "set-attr", "id": 5, "guard": g, "name": "tooltip", "value": "hi"})])
        self.assertEqual((applied, notes), (3, []))
        self.assertEqual(a["classes"], ["y", "z"])
        self.assertEqual(a["inline"], [("height", "20px")])
        self.assertEqual(a["attrs"]["tooltip"], "hi")
        self.assertEqual(b["classes"], ["x"])                                    # the same id in another layout is another element

    def test_a_guard_mismatch_and_a_missing_element_are_skipped_and_reported(self):
        top = [dict(n(1, "L"), children=[n(5, "L", name="card")])]
        applied, notes = overlay.apply_layout_patches(top, [self.doc(
            {"op": "set-classes", "id": 5, "guard": {"type": "SIText", "name": "card"}, "add": ["z"]},
            {"op": "set-classes", "id": 99, "guard": {"type": "VisualElement"}, "add": ["z"]})])
        self.assertEqual(applied, 0)
        self.assertEqual(len(notes), 2)
        self.assertIn("skipped", notes[0])
        self.assertIn("no element 99", notes[1])


class Moves(unittest.TestCase):
    def setUp(self):
        from skin_editor.render import screen
        self.screen = screen
        cells = [dict(composition="C", element_id="banner", x=0, y=0, w=16, h=1, min_w=16, max_w=100, min_h=1, max_h=100),
                 dict(composition="C", element_id="t1", x=16, y=0, w=4, h=4, min_w=4, max_w=4, min_h=4, max_h=4),
                 dict(composition="C", element_id="t2", x=16, y=4, w=4, h=4, min_w=4, max_w=4, min_h=4, max_h=4)]
        self.a = screen.Assembler({"layouts": [], "cells": cells, "tiles": []})

    def test_a_tile_move_changes_the_cell_position_and_says_so(self):
        move = {"op": "move-cell", "composition": "C", "cell_id": "t2", "to": {"x": 16, "y": 6}}
        base = self.a.place("C", 20, 8)
        moved = self.a.place("C", 20, 8, moves=[move])
        self.assertEqual((base["t2"]["col"], base["t2"]["row"]), (16, 4))
        self.assertEqual((moved["t2"]["col"], moved["t2"]["row"]), (16, 6))
        self.assertIn("moved by the project", moved["t2"]["mode"])
        self.assertEqual(moved["t1"], base["t1"])                                # the other cells do not change

    def test_a_moved_cell_keeps_its_anchoring_on_a_bigger_grid(self):
        move = {"op": "move-cell", "composition": "C", "cell_id": "t1", "to": {"x": 12, "y": 0}}
        g = self.a.place("C", 30, 8, moves=[move])
        self.assertEqual(g["t1"]["col"], 12 + 10)                                # right-anchored by its design position (the right edge it had), moved in design space

    def test_moves_of_another_composition_are_ignored(self):
        move = {"op": "move-cell", "composition": "Other", "cell_id": "t2", "to": {"x": 0, "y": 0}}
        self.assertEqual(self.a.place("C", 20, 8, moves=[move]), self.a.place("C", 20, 8))


@unittest.skipUnless(AA.is_dir(), "needs the game install")
class RealTables(unittest.TestCase):
    def test_a_column_edit_changes_the_placeholder_header_row_and_vanilla_keeps_it(self):
        from skin_editor import tables
        T = tables.Tables(AA).load()
        view = next(v for v in T._views.values() if len(v["tree"]["m_tableView"]["m_tableConfig"]) >= 4
                    and any(not c["m_columnMetadata"]["m_required"] for c in v["tree"]["m_tableView"]["m_tableConfig"]))
        cols = view["tree"]["m_tableView"]["m_tableConfig"]
        hide = next(c["m_columnID"] for c in cols if not c["m_columnMetadata"]["m_required"])
        doc = {"schema": 1, "view": {"bundle": view["bundle"], "name": view["name"], "path_id": view["path_id"]}, "ops": [{"op": "hide-column", "column": hide}]}
        p = proj(table_patches=[doc])
        vanilla = overlay.table_placeholder(T, view["path_id"])
        skin = overlay.table_placeholder(T, view["path_id"], p)
        self.assertIn(hide, [c["id"] for c in vanilla["columns"]])
        self.assertNotIn(hide, [c["id"] for c in skin["columns"]])
        self.assertEqual(len(skin["columns"]), len(vanilla["columns"]) - 1)
        self.assertTrue(skin["edited"])
        self.assertIn("placeholder", skin["label"])


class Changes(unittest.TestCase):
    def test_a_batch_emits_one_event_per_project_with_every_reason(self):
        got = []
        changes.set_sink(got.append)
        self.addCleanup(changes.set_sink, None)
        with changes.batch():
            changes.record("a", "tokens")
            changes.record("a", "rules", ["x.uss"])
            changes.record("b", "file", ["f"])
            with changes.batch():                                               # nested: folded into the outer batch
                changes.record("a", "tokens")
        self.assertEqual(len(got), 2)
        a = next(e for e in got if e["project"] == "a")
        self.assertEqual((a["reason"], a["reasons"], a["scope"]), ("multiple", ["tokens", "rules"], ["x.uss"]))
        self.assertEqual(next(e for e in got if e["project"] == "b")["reason"], "file")

    def test_outside_a_batch_a_record_is_emitted_at_once_and_an_empty_batch_emits_nothing(self):
        got = []
        changes.set_sink(got.append)
        self.addCleanup(changes.set_sink, None)
        with changes.batch():
            pass
        self.assertEqual(got, [])
        changes.record("a", "tile-move")
        self.assertEqual([e["reason"] for e in got], ["tile-move"])

    def test_diff_reasons_names_what_changed_and_nothing_for_an_identical_model(self):
        old = proj()
        new = copy.deepcopy(old)
        self.assertEqual(changes.diff_reasons(old, new), [])
        new["token_overrides"] = [{"token": "--a", "value": {"rgb": "#FF0000", "a": 1.0}}]
        new["scoped_rules"] = [{"sheet": "s", "selector": ".a", "props": {"color": "red"}}]
        new["table_patches"] = []
        self.assertEqual([r for r, _ in changes.diff_reasons(old, new)], ["tokens", "rules"])


class EachEditor(unittest.TestCase):
    """Every editor's own mutation raises its own reason (the M5 exit: each edit fires exactly one invalidate)."""

    def setUp(self):
        self.got = []
        changes.set_sink(self.got.append)
        self.addCleanup(changes.set_sink, None)

    def test_layout_table_font_and_image_edits_are_told_apart(self):
        old = proj()
        cases = {
            "layout-patch": {"layout_patches": [{"schema": 1, "layout": {"bundle": "ui-visualtreeassets_assets_x.bundle", "name": "L"}, "ops": [{"op": "set-classes", "id": 1, "guard": {"type": "VisualElement"}, "add": ["a"]}]}]},
            "table-edit": {"table_patches": [{"schema": 1, "view": {"bundle": "ui-tableviews_assets_all.bundle", "name": "V"}, "ops": [{"op": "hide-column", "column": "c"}]}]},
            "font": {"font_swaps": [{"token": "--typography-family-primary", "source": "f.ttf"}]},
            "tokens": {"token_overrides": [{"token": "--a", "value": {"rgb": "#FF0000", "a": 1.0}}]},
            "rules": {"scoped_rules": [{"sheet": "AlwaysAppliedStyleSheet", "selector": ".a", "props": {"color": "#FF0000"}}]},
            "options": {"options": dict(old["options"], flatten_gradients=True)},
        }
        for reason, change in cases.items():
            new = dict(copy.deepcopy(old), **change)
            self.assertEqual([r for r, _ in changes.diff_reasons(old, new)], [reason], reason)
        scope = changes.diff_reasons(old, dict(copy.deepcopy(old), **cases["layout-patch"]))[0][1]
        self.assertEqual(scope, ["L"])                                          # the page repaints only the layouts a patch can affect

    def test_a_stored_tile_move_raises_tile_move_once(self):
        from types import SimpleNamespace
        from skin_editor import placement
        tmp = tempfile.mkdtemp()
        ws = SimpleNamespace(placements=Path(tmp))
        with changes.batch():
            placement._write(ws, {"project": "demo", "edits": []})
        self.assertEqual([(e["project"], e["reason"]) for e in self.got], [("demo", "tile-move")])


class Api(unittest.TestCase):
    """For each mutating API call exactly one render.invalidate event, and none for a call that changes nothing."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.addCleanup(self.tmp.cleanup)
        self.addCleanup(close_logs)
        self.addCleanup(changes.set_sink, None)
        self.e = engine(self.tmp.name)
        self.sub = self.e.events.subscribe()

    def call(self, method, params=None):
        r = json.loads(rpc.handle(self.e, json.dumps({"jsonrpc": "2.0", "method": method, "id": 1, "params": params or {}})))
        self.assertNotIn("error", r, r)
        return r["result"]

    def events(self):
        out = []
        while not self.sub.empty():
            ev = self.sub.get()
            if ev["type"] == "render.invalidate":
                out.append(ev["data"])
        return out

    def test_each_mutating_call_fires_exactly_one_event_and_a_no_op_none(self):
        self.call("project.create_folder", {"name": "demo", "target": "native"})
        ev = self.events()
        self.assertEqual([(e["project"], e["reason"]) for e in ev], [("demo", "options")])
        p = self.call("project.get", {"name": "demo"})
        self.events()
        p["token_overrides"] = [{"token": "--base", "value": "#AA0000"}]
        p["scoped_rules"] = [{"sheet": "AlwaysAppliedStyleSheet", "selector": ".a", "props": {"color": "#FF0000"}}]
        self.call("project.save", {"project": p})
        ev = self.events()
        self.assertEqual(len(ev), 1)                                             # tokens AND rules changed in one call: still one event
        self.assertEqual((ev[0]["reason"], ev[0]["reasons"]), ("multiple", ["tokens", "rules"]))
        saved = self.call("project.get", {"name": "demo"})
        self.call("project.save", {"project": saved})
        self.assertEqual(self.events(), [])                                      # saving the same model changes nothing
        self.call("project.write_file", {"project": "demo", "path": "styles/extra.uss", "text": "/* x */\n"})
        ev = self.events()
        self.assertEqual([(e["reason"], e["scope"]) for e in ev], [("file", ["styles/extra.uss"])])
        self.call("project.delete_file", {"project": "demo", "path": "styles/extra.uss"})
        self.assertEqual([e["reason"] for e in self.events()], ["file"])
        self.call("project.new_sheet", {"project": "demo", "sheet": "Mine"})
        self.assertEqual([e["reason"] for e in self.events()], ["file"])
        self.call("project.delete", {"project": "demo"})
        self.assertEqual([e["reason"] for e in self.events()], ["file"])


@unittest.skipUnless(AA.is_dir(), "needs the game install")
class Real(unittest.TestCase):
    def test_a_token_edit_repaints_the_loans_tile_and_the_vanilla_render_is_unchanged(self):
        from skin_editor import index_styles
        from skin_editor.render.service import Renderer
        ws = config.workspace(config.load())
        R = Renderer(AA, ws.cache, index_styles.load(ws))
        r = next(x for x in R.layouts.catalog() if x["name"] == "LoansTile_4x2")

        def button(res):
            stack = list(res["tree"])
            while stack:
                x = stack.pop()
                if x["name"] == "layout-tile-interaction-button":
                    return x
                stack.extend(x["children"])
        van = R.layout(r["bundle"], r["path_id"])
        base = button(van)["computed"]["background-color"]
        self.assertEqual(base["value"], "#1E2129")
        token = base["tokens"][-1]                                              # the token whose definition paints it (--colours-ui-soft)
        p = proj(token_overrides=[{"token": token, "value": {"rgb": "#FF0000", "a": 1.0}}])
        sk = R.layout(r["bundle"], r["path_id"], project=p)
        self.assertEqual(button(sk)["computed"]["background-color"]["value"], "#FF0000")
        self.assertEqual(sk["overlay"]["project"], "t")
        self.assertEqual(button(R.layout(r["bundle"], r["path_id"]))["computed"]["background-color"]["value"], "#1E2129")        # the toggle: no project, vanilla again
        R.invalidate("t")
        self.assertEqual(button(R.layout(r["bundle"], r["path_id"], project=p))["computed"]["background-color"]["value"], "#FF0000")


@unittest.skipUnless(AA.is_dir(), "needs the game install")
class RealPatches(unittest.TestCase):
    def test_a_class_patch_and_an_inline_patch_are_visible_from_their_own_edit(self):
        from skin_editor import index_styles
        from skin_editor.render.service import Renderer
        ws = config.workspace(config.load())
        R = Renderer(AA, ws.cache, index_styles.load(ws))
        r = next(x for x in R.layouts.catalog() if x["name"] == "LoansTile_4x2")

        def find(res, name):
            stack = list(res["tree"])
            while stack:
                x = stack.pop()
                if x["name"] == name:
                    return x
                stack.extend(x["children"])
        van = R.layout(r["bundle"], r["path_id"])
        node = find(van, "title area frame")
        self.assertNotIn("margin-top", node["computed"])
        g = {"type": node["type"], "name": node["name"]}
        doc = {"schema": 1, "layout": {"bundle": r["bundle"], "name": node["layout"]}, "ops": [                # the element lives in the included base template, so that is the layout the patch is made on
            {"op": "set-classes", "id": node["id"], "guard": g, "add": ["margin-top-global-gap-regular"]},
            {"op": "set-inline", "id": node["id"], "guard": g, "props": {"height": "77px"}}]}
        sk = R.layout(r["bundle"], r["path_id"], project=proj(layout_patches=[doc]))
        patched = find(sk, "title area frame")
        self.assertIn("margin-top", patched["computed"])                       # the class brings a rule from the game's sheets
        self.assertEqual(patched["computed"]["height"]["value"], "77px")
        self.assertTrue(patched["computed"]["height"]["source"].get("inline"))   # the inline value wins and says it is inline
        self.assertEqual(sk["overlay"]["layout_patch_ops_applied"], 2)
        self.assertNotIn("margin-top", find(R.layout(r["bundle"], r["path_id"]), "title area frame")["computed"])         # vanilla again without the project


if __name__ == "__main__":
    unittest.main()
