"""Stage 5B (revised by the owner findings of 2026-11-18): the Skin Operation model (skin_editor/playops.py).
Pure model tests on synthetic records - no game file is read or written. Every kind either translates onto an
existing writer or is refused with the precise reason; a scoped rule without a MEASURED reach is never a value
edit; visibility is runtime-dependent; moves are composition-scoped with a cell guard; rebase resolves in tiers
and reports matched / ambiguous / unresolved separately; rule provenance is keyed (bundle, sheet, selector,
occurrence), never by index."""
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from skin_editor import playops


def target(**over):
    t = {"screen": "SquadScreen", "logical_id": "guid1/VisualElement~Content/VisualElement~Header",
         "structural_key": "guid1/VisualElement/VisualElement/Header",
         "locator": {"bundle": "ui-styles_assets_common.bundle", "bundle_sha256": "ab" * 32, "cab": "CAB-1",
                     "path_id": "123", "m_id": "1039390893"},
         "guard": {"type": "VisualElement", "name": "Header", "classes": ["dashboard-tile"]},
         "render_pos": "0/2/1"}
    t.update(over)
    return t


def original(value, evidence="directly serialized", provenance=None):
    return {"value": value, "evidence": evidence, "provenance": provenance or {"bundle": "ui-styles_assets_common.bundle",
            "sheet": "AlwaysAppliedStyleSheet", "selector": ".dashboard-tile", "occurrence": 0,
            "field": "background-color"}}


def reach(elements=1, layouts=1, screens=1, measured_by="layout.reach"):
    return {"elements": elements, "layouts": layouts, "screens": screens, "measured_by": measured_by}


def style_new(kind, props, sheet="AlwaysAppliedStyleSheet", selector=".dashboard-tile", r=None, route=None):
    new = {"rule": {"sheet": {"bundle": "ui-styles_assets_common.bundle", "name": sheet}, "selector": selector,
                    "props": props, "reach": r if r is not None else reach()}}
    if route:
        new["route"] = route
    return new


class TestOperations(unittest.TestCase):
    def test_every_kind_serialises_and_round_trips(self):
        for kind in playops.KINDS:
            op = playops.new_operation(kind, target(), {"value": "#010203"})
            d = json.loads(json.dumps(op))
            self.assertEqual(d["kind"], kind)
            self.assertEqual(d["schema"], playops.OP_SCHEMA)
            self.assertTrue(d["id"])

    def test_the_translatable_kinds_translate_onto_existing_writers(self):
        cases = {
            "ReplaceToken": ({"token": "--accent", "value": {"rgb": "#010203", "a": 1.0},
                              "route": {"chosen": "token", "reason": "the colour comes from this token on every screen"}},
                             "token_overrides", "token_patch"),
            "SetColor": (style_new("SetColor", {"background-color": {"rgb": "#010203", "a": 1.0}}, r=reach(1, 1, 1),
                                   route={"chosen": "scoped_rule", "reason": "the selected element is the only match"}),
                         "scoped_rules", "patch_sheet"),
            "SetSpacing": (style_new("SetSpacing", {"padding": "12px"}), "scoped_rules", "patch_sheet"),
            "SetVisibility": (style_new("SetVisibility", {"visibility": "hidden"}), "scoped_rules", "patch_sheet"),
            "ReplaceAsset": ({"swap": {"kind": "texture", "source": "bg.png", "fit": "cover"}}, "image_swaps", "apply_swaps"),
        }
        for kind, (new, fragment, writer) in cases.items():
            v = playops.validate(playops.new_operation(kind, target(), new, original("#171717")))
            self.assertTrue(v["ok"], kind)
            self.assertEqual(v["translation"]["fragment"], fragment, kind)
            self.assertIn(writer, v["translation"]["writer"], kind)

    def test_a_measured_reach_above_one_is_a_scope_change_the_user_must_see(self):
        op = playops.new_operation("SetColor", target(), style_new("SetColor",
                    {"background-color": {"rgb": "#010203", "a": 1.0}}, r=reach(8, 4, 3),
                    route={"chosen": "scoped_rule", "reason": "class-based colour, scoped deliberately"}))
        v = playops.validate(op)
        self.assertEqual(v["safety"], "scope")                                  # never a plain value edit
        self.assertTrue(v["scope"]["scope_change"])
        self.assertEqual(v["scope"]["elements"], 8)
        self.assertTrue(any("scope change" in f for f in v["findings"]))

    def test_a_scoped_rule_without_a_measured_reach_is_refused(self):
        no_reach = style_new("SetColor", {"background-color": {"rgb": "#010203", "a": 1.0}})
        del no_reach["rule"]["reach"]
        with self.assertRaises(playops.OperationError) as c:
            playops.validate(playops.new_operation("SetColor", target(), no_reach))
        self.assertIn("reach was not measured", str(c.exception))
        self.assertIn("layout.reach", str(c.exception))
        partial = style_new("SetStyle", {"padding": "4px"}, r={"elements": 1, "layouts": 1})     # incomplete measurement
        with self.assertRaises(playops.OperationError) as c:
            playops.validate(playops.new_operation("SetStyle", target(), partial))
        self.assertIn("reach was not measured", str(c.exception))

    def test_a_colour_change_records_its_route_and_reason(self):
        with self.assertRaises(playops.OperationError) as c:
            playops.validate(playops.new_operation("SetColor", target(),
                        style_new("SetColor", {"background-color": {"rgb": "#010203", "a": 1.0}})))
        self.assertIn("needs its route recorded", str(c.exception))
        with self.assertRaises(playops.OperationError) as c:
            playops.validate(playops.new_operation("ReplaceToken", target(),
                        {"token": "--accent", "value": {"rgb": "#010203", "a": 1.0}}))
        self.assertIn("needs its route recorded", str(c.exception))
        v = playops.validate(playops.new_operation("ReplaceToken", target(),
                        {"token": "--accent", "value": {"rgb": "#010203", "a": 1.0},
                         "route": {"chosen": "token", "reason": "every screen uses this token for the accent"}}))
        self.assertIn("every rule that uses the token", v["findings"][0])
        self.assertTrue(v["scope"]["scope_change"])                             # a token route is always a scope

    def test_visibility_is_runtime_dependent_never_a_guaranteed_outcome(self):
        v = playops.validate(playops.new_operation("SetVisibility", target(),
                        style_new("SetVisibility", {"display": "none"})))
        self.assertEqual(v["translation"]["effect_evidence"], "runtime-dependent")
        self.assertTrue(any("RUNTIME-DEPENDENT" in f for f in v["findings"]))
        self.assertIn("26 of 58", " ".join(v["findings"]))                      # the measured runtime-class evidence

    def test_sheets_are_keyed_by_bundle_and_rules_by_selector_occurrence(self):
        with self.assertRaises(playops.OperationError) as c:                    # a bare sheet name is ambiguous
            playops.validate(playops.new_operation("SetColor", target(),
                        style_new("SetColor", {"color": {"rgb": "#010203", "a": 1.0}}) | {"rule": {"sheet": "AlwaysAppliedStyleSheet", "selector": ".x", "props": {"color": {"rgb": "#010203", "a": 1.0}}, "reach": reach()}}))
        self.assertIn("'default' exists in more than one bundle", str(c.exception))
        with self.assertRaises(playops.OperationError) as c:                    # a rule cited by index is refused
            playops.validate(playops.new_operation("SetColor", target(), style_new("SetColor", {"color": {"rgb": "#010203", "a": 1.0}}),
                        original("#fff", provenance={"bundle": "b", "sheet": "s", "rule": 12})))
        self.assertIn("rule by INDEX", str(c.exception))
        with self.assertRaises(playops.OperationError) as c:                    # a sheet cited without its bundle
            playops.validate(playops.new_operation("SetColor", target(), style_new("SetColor", {"color": {"rgb": "#010203", "a": 1.0}}),
                        original("#fff", provenance={"sheet": "default", "selector": ".x", "occurrence": 0})))
        self.assertIn("bundle too", str(c.exception))

    def test_a_target_without_a_guard_is_refused(self):
        with self.assertRaises(playops.OperationError) as c:
            playops.validate(playops.new_operation("ReplaceToken", {k: v for k, v in target().items() if k != "guard"},
                        {"token": "--accent", "value": {"rgb": "#010203", "a": 1.0},
                         "route": {"chosen": "token", "reason": "r"}}))
        self.assertIn("type/name guard", str(c.exception))
        with self.assertRaises(playops.OperationError) as c:
            playops.validate(playops.new_operation("ReplaceToken", {k: v for k, v in target().items() if k != "locator"},
                        {"token": "--accent", "value": {"rgb": "#010203", "a": 1.0},
                         "route": {"chosen": "token", "reason": "r"}}))
        self.assertIn("physical locator", str(c.exception))

    def test_move_node_translates_only_for_a_guarded_composition_cell(self):
        op = playops.new_operation("MoveNode", target(cell={"composition": "SquadComposition-Large", "cell_index": 0,
                                                           "cell_element_id": "Atmosphere",
                                                           "geometry": {"x": 12, "y": 8, "w": 4, "h": 2}}),
                                   {"x": 12, "y": 8})
        v = playops.validate(op)
        self.assertEqual(v["translation"]["fragment"], "placement")
        self.assertIn("tiles.apply_ops", v["translation"]["writer"])
        self.assertTrue(any("window width" in f for f in v["findings"]))         # the composition scope caveat
        self.assertTrue(any("optional slices" in f for f in v["findings"]))      # the runtime-slot gate limitation

    def test_the_candidate_kinds_validate_with_their_checks_and_the_refused_ones_stay_refused(self):
        # ADDENDUM (2026-11-18): ResizeNode and AddCell are CANDIDATES; ReorderNode and a generic move stay refused.
        with self.assertRaises(playops.OperationError) as c:
            playops.validate(playops.new_operation('ResizeNode', target(), {'width': '300px'}))
        self.assertIn('needs the cell it resizes', str(c.exception))
        with self.assertRaises(playops.OperationError) as c:
            playops.validate(playops.new_operation('ResizeNode', target(cell={'composition': 'C', 'cell_index': 0,
                                                                             'cell_element_id': 'Training',
                                                                             'geometry': {'x': 12, 'y': 4, 'w': 4, 'h': 2}}), {}))
        self.assertIn('m_maxSize as {x, y} integers', str(c.exception))
        v = playops.validate(playops.new_operation('ResizeNode', target(cell={'composition': 'C', 'cell_index': 0,
                                                                              'cell_element_id': 'Training',
                                                                              'geometry': {'x': 12, 'y': 4, 'w': 4, 'h': 3},
                                                                              'max_size': {'x': 4, 'y': 3},
                                                                              'config_size': {'x': 4, 'y': 2}}), {}))
        self.assertEqual(v['safety'], 'value')                       # promoted by Test C: enlargement is buildable
        self.assertFalse(v['translation']['candidate'])
        self.assertTrue(any('BUILDABLE enlargement' in f for f in v['findings']))
        self.assertTrue(any('only takes effect at window sizes' in f for f in v['findings']))
        self.assertTrue(any('overlap gate' in f for f in v['findings']))
        with self.assertRaises(playops.OperationError) as c:
            playops.validate(playops.new_operation('ResizeNode', target(cell={'composition': 'C', 'cell_index': 0,
                                                                              'cell_element_id': 'Training',
                                                                              'geometry': {'x': 12, 'y': 4, 'w': 4, 'h': 1},
                                                                              'max_size': {'x': 4, 'y': 1},
                                                                              'config_size': {'x': 4, 'y': 2}}), {}))
        self.assertIn("shrinking below the tile's configured size", str(c.exception))
        with self.assertRaises(playops.OperationError) as c:
            playops.validate(playops.new_operation('AddCell', target(cell={'composition': 'C', 'cell_index': 5,
                                                                           'geometry': {'x': 0, 'y': 0, 'w': 2, 'h': 2}}), {}))
        self.assertIn('NEW element id', str(c.exception))
        with self.assertRaises(playops.OperationError) as c:
            playops.validate(playops.new_operation('AddCell', target(cell={'composition': 'C', 'cell_index': 5,
                                                                           'cell_element_id': 'NewTile',
                                                                           'geometry': {'x': 0, 'y': 0, 'w': 2, 'h': 2}}), {}))
        self.assertIn('EXISTING tile description', str(c.exception))
        v = playops.validate(playops.new_operation('AddCell', target(cell={'composition': 'C', 'cell_index': 5,
                                                                           'cell_element_id': 'NewTile',
                                                                           'geometry': {'x': 0, 'y': 0, 'w': 2, 'h': 2},
                                                                           'description': {'id': 'TrainingTileDescription', 'config_index': 0}}), {}))
        self.assertEqual(v['safety'], 'value')
        self.assertFalse(v['translation']['candidate'])
        self.assertTrue(any('PACKING rule' in f for f in v['findings']))
        with self.assertRaises(playops.OperationError) as c:
            playops.validate(playops.new_operation('ReorderNode', target(), {'index': 2}))
        self.assertIn('sibling order', str(c.exception))
        with self.assertRaises(playops.OperationError) as c:
            playops.validate(playops.new_operation('MoveNode', target(), {'x': 5}))
        self.assertIn('only a composition CELL has a writer', str(c.exception))
        with self.assertRaises(playops.OperationError) as c:
            playops.validate(playops.new_operation('MoveNode', target(cell={'composition': 'C', 'cell_index': 0,
                                                                            'geometry': {'x': 1, 'y': 0, 'w': 4, 'h': 2}}), {}))
        self.assertIn('element id as a guard', str(c.exception))
        with self.assertRaises(playops.OperationError) as c:
            playops.new_operation('TeleportNode', target(), {})
        self.assertIn('unknown operation kind', str(c.exception))

    def test_bad_shapes_are_refused_never_repaired(self):
        with self.assertRaises(playops.OperationError) as c:
            playops.validate(playops.new_operation("ReplaceToken", target(),
                        {"token": "accent", "value": {"rgb": "#010203", "a": 1.0},
                         "route": {"chosen": "token", "reason": "r"}}))
        self.assertIn("--token", str(c.exception))
        with self.assertRaises(playops.OperationError) as c:
            playops.validate(playops.new_operation("SetColor", target(),
                        style_new("SetColor", {"width": "12px"})))
        self.assertIn("colour property", str(c.exception))
        with self.assertRaises(playops.OperationError) as c:
            playops.validate(playops.new_operation("SetSpacing", target(), style_new("SetSpacing", {"color": "#fff"})))
        self.assertIn("spacing property", str(c.exception))
        with self.assertRaises(playops.OperationError) as c:
            playops.validate(playops.new_operation("SetStyle", target(), style_new("SetStyle", {"not-a-game-prop": "1px"})))
        self.assertIn("verified property table", str(c.exception))
        with self.assertRaises(playops.OperationError) as c:
            playops.validate(playops.new_operation("MoveNode", target(cell={"composition": "C", "cell_index": 0,
                                                                           "cell_element_id": "T",
                                                                           "geometry": {"x": -1, "y": 0, "w": 4, "h": 2}}), {}))
        self.assertIn("negative position", str(c.exception))
        with self.assertRaises(playops.OperationError) as c:
            playops.validate(playops.new_operation("ReplaceAsset", target(), {"swap": {"kind": "font", "source": "f.ttf"}}))
        self.assertIn("texture, svg or icon", str(c.exception))


class TestSession(unittest.TestCase):
    def setUp(self):
        self.s = playops.new_session("demo", "SquadScreen", game_build="27.1.0.2505117")

    def add_token(self, token="--accent", value=None):
        return playops.add(self.s, playops.new_operation("ReplaceToken", target(), {"token": token,
                        "value": value or {"rgb": "#010203", "a": 1.0},
                        "route": {"chosen": "token", "reason": "the token drives this colour everywhere"}},
                        original("#171717")))

    def test_add_validates_and_records_supersession_not_silent_conflict(self):
        a = self.add_token("--accent", {"rgb": "#010203", "a": 1.0})
        b = self.add_token("--accent", {"rgb": "#040506", "a": 1.0})
        self.assertEqual(a["state"], "superseded")
        self.assertEqual(a["superseded_by"], b["id"])
        self.assertEqual(len(playops.effective(self.s)), 1)

    def test_undo_redo_revert_all_keep_the_history(self):
        self.add_token()
        playops.add(self.s, playops.new_operation("SetColor", target(), style_new("SetColor",
                      {"color": {"rgb": "#ffffff", "a": 1.0}},
                      route={"chosen": "scoped_rule", "reason": "single-element selector"})))
        self.assertEqual(len(playops.effective(self.s)), 2)
        undone = playops.undo(self.s)
        self.assertEqual(undone["kind"], "SetColor")
        self.assertEqual(len(playops.effective(self.s)), 1)
        playops.redo(self.s, undone["id"])
        self.assertEqual(len(playops.effective(self.s)), 2)
        playops.add(self.s, playops.new_operation("SetColor", target(), style_new("SetColor",
                      {"color": {"rgb": "#000000", "a": 1.0}},
                      route={"chosen": "scoped_rule", "reason": "a darker variant of the same single-element selector"})))
        with self.assertRaises(playops.OperationError):
            playops.redo(self.s, self.s["operations"][1]["id"])               # superseded: redo the newer edit instead
        playops.revert_all(self.s)
        self.assertEqual(playops.effective(self.s), [])
        self.assertEqual(len(self.s["operations"]), 3)                       # nothing was deleted

    def test_the_projection_builds_the_existing_project_fragments(self):
        self.add_token()
        playops.add(self.s, playops.new_operation("SetColor", target(), style_new("SetColor",
                      {"background-color": {"rgb": "#010203", "a": 1.0}},
                      route={"chosen": "scoped_rule", "reason": "single-element class selector, measured"})))
        playops.add(self.s, playops.new_operation("MoveNode", target(cell={"composition": "C", "cell_index": 2,
                                                                         "cell_element_id": "Training",
                                                                         "geometry": {"x": 12, "y": 5, "w": 4, "h": 2}}), {}))
        playops.add(self.s, playops.new_operation("ReplaceAsset", target(locator={"bundle": "ui-prematch-backgrounds_assets_common.bundle",
                                                                                 "bundle_sha256": "cd" * 32, "cab": "CAB-2",
                                                                                 "path_id": "7406977133025223356", "m_id": "5"}),
                      {"swap": {"kind": "texture", "source": "bg.png"}}))
        from skin_editor import project as project_mod
        p = project_mod.new("projection-skin", "27.1.0")
        project_mod.set_route_preference(p, "skin_folder")
        frags = playops.project_onto(p, self.s)
        self.assertEqual(frags["token_overrides"], [{"token": "--accent", "value": {"rgb": "#010203", "a": 1.0}}])
        self.assertEqual(frags["scoped_rules"][0]["sheet"], "AlwaysAppliedStyleSheet")
        self.assertEqual(frags["scoped_rules"][0]["playground_bundle"], "ui-styles_assets_common.bundle")
        self.assertEqual(frags["placements"][0]["cell_element_id"], "Training")
        self.assertEqual(frags["image_swaps"][0]["bundle"], "ui-prematch-backgrounds_assets_common.bundle")
        self.assertEqual(playops.project_onto(p, self.s), frags)                # idempotent
        playops.undo(self.s)
        self.assertEqual(len(playops.project_onto(p, self.s)["image_swaps"]), 0)

    def test_the_session_round_trips_and_revalidates_on_load(self):
        self.add_token()
        tmp = Path(tempfile.mkdtemp(prefix="fm27se-play-"))
        self.addCleanup(shutil.rmtree, tmp, ignore_errors=True)
        playops.save(tmp, self.s)
        d = playops.load(tmp)
        self.assertEqual(d["schema"], playops.SCHEMA)
        self.assertEqual(len(d["operations"]), 1)
        self.assertEqual(d["operations"][0]["validation"]["translation"]["fragment"], "token_overrides")
        bad = json.loads(json.dumps(d))
        bad["operations"][0]["new"]["token"] = "not-a-token"
        playops.save(tmp, bad)
        with self.assertRaises(playops.OperationError) as c:
            playops.load(tmp)
        self.assertIn("no longer validates", str(c.exception))
        self.assertIn(bad["operations"][0]["id"], str(c.exception))

    def test_the_loader_never_reaches_the_deprecated_mark_stale_blanket(self):
        """Review point (2026-11-18): the session loader re-validates and never marks stale by build. Staleness is
        REBASE's job - tiered, caller-supplied resolver, per-operation report. This test fails the moment the loader
        path starts calling the deprecated blanket (a different recorded game_build would otherwise stale every
        applied operation without any per-target resolution)."""
        from unittest import mock
        self.add_token()
        tmp = Path(tempfile.mkdtemp(prefix="fm27se-play-"))
        self.addCleanup(shutil.rmtree, tmp, ignore_errors=True)
        playops.save(tmp, self.s)
        with mock.patch.object(playops, "mark_stale",
                               side_effect=AssertionError("mark_stale was reached from the session loader; "
                                                          "staleness belongs to rebase, never to load")):
            d = playops.load(tmp)                       # the session's game_build is recorded and different builds exist
        self.assertEqual(d["operations"][0]["state"], "applied")   # the operation was re-validated, not blanket-staled

    def test_rebase_resolves_in_tiers_and_reports_matched_ambiguous_unresolved_separately(self):
        a = self.add_token()                                                    # tier-1 match
        b = self.add_token("--other")                                          # tier-2 guard match
        c = self.add_token("--third")                                          # ambiguous
        d = self.add_token("--fourth")                                         # unresolved
        res = {
            a["id"]: {"status": "matched", "tier": 1, "logical_id": "guid2/VisualElement~Header"},
            b["id"]: {"status": "matched", "tier": 2, "logical_id": "guid2/VisualElement~Renamed"},
            c["id"]: {"status": "ambiguous", "tier": 2, "candidates": ["guid2/A~X", "guid2/B~X"]},
            d["id"]: {"status": "unresolved"},
        }
        rep = playops.rebase(self.s, lambda op: res[op["id"]], "27.2.0.9999999")
        self.assertEqual(len(rep["matched"]), 2)
        self.assertEqual(rep["matched"][0]["tier"], 1)
        self.assertEqual(len(rep["ambiguous"]), 1)
        self.assertEqual(len(rep["unresolved"]), 1)
        self.assertEqual(a["target"]["logical_id"], "guid2/VisualElement~Header")   # the matched op carries its new identity
        self.assertEqual(b["target"]["logical_id"], "guid2/VisualElement~Renamed")
        self.assertEqual(c["state"], "stale")
        self.assertIn("ambiguous", c["stale_reason"])
        self.assertEqual(d["state"], "stale")
        self.assertIn("unresolved", d["stale_reason"])
        self.assertEqual(len(playops.effective(self.s)), 2)                   # only the matched ops remain applied
        with self.assertRaises(playops.OperationError):
            playops.rebase(self.s, lambda op: {"status": "nope"}, "27.3")      # the resolver's contract is enforced

    def test_mark_stale_is_the_deprecated_blanket_a_rebase_replaces(self):
        self.add_token()
        stale = playops.mark_stale(self.s, "27.2.0.9999999")
        self.assertEqual(stale, [self.s["operations"][0]["id"]])
        self.assertEqual(playops.effective(self.s), [])
        same = playops.mark_stale(self.s, "27.1.0.2505117")
        self.assertEqual(same, [])

    def test_export_carries_provenance_validation_and_scope(self):
        self.add_token()
        d = json.loads(playops.export(self.s))
        op = d["operations"][0]
        self.assertEqual(op["original"]["evidence"], "directly serialized")
        self.assertTrue(op["validation"]["ok"])
        self.assertIn("scope", op["validation"])


if __name__ == "__main__":
    unittest.main()
