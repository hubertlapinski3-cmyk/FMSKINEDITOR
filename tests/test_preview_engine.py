"""Stage 5F engine tests: the deterministic preview engine on synthetic dumps and serialized-set fixtures.

Never the live game folder; the live-workspace guard (config.json and layout/current.json hashes before and
after) runs in-process. The archived set C is exercised by the evidence scripts, not here.
"""
import hashlib
import json
import os
import unittest
from pathlib import Path

from skin_editor.render import preview

SMALL, STANDARD, LARGE = "SquadComposition-Small", "SquadComposition-Standard", "SquadComposition-Large"

# a SYNTHETIC serialized composition set: the same shape as m_gridBreakpointCompositionData (key -> compositions)
SETS = {"SquadTileCompositionSet": {
    "bundle": "ui-tileslayouts_assets_all.bundle", "path_id": "1",
    "breakpoints": {1: [{"name": SMALL}], 2: [{"name": STANDARD}], 3: [{"name": LARGE}]}}}


def _tile(set_name, key, comp):
    return {"set_name": set_name, "breakpoint": key, "variant_idx": 0, "composition": comp, "cell_index": 0,
            "cell_element_id": "A", "tile_layout_id": None}


def _cell(comp, eid, x, y, w, h, max_w=None, max_h=None):
    return {"composition": comp, "cell_index": 0, "element_id": eid, "x": x, "y": y, "w": w, "h": h,
            "max_w": max_w if max_w is not None else w, "max_h": max_h if max_h is not None else h,
            "flags": []}


def dump(tiles=None, cells=None):
    return {"tiles": tiles if tiles is not None else [_tile("SquadTileCompositionSet", 1, SMALL),
                                                     _tile("SquadTileCompositionSet", 2, STANDARD),
                                                     _tile("SquadTileCompositionSet", 3, LARGE)],
            "layouts": [],
            "compositions": [{"name": SMALL, "bundle": None}, {"name": STANDARD, "bundle": None},
                             {"name": LARGE, "bundle": None}],
            "cells": cells if cells is not None else [_cell(SMALL, "A", 0, 0, 2, 2), _cell(STANDARD, "A", 0, 0, 3, 2),
                                                      _cell(LARGE, "A", 0, 0, 4, 2), _cell(LARGE, "B", 4, 0, 4, 2)]}


class _Layouts:
    def target(self, guid):
        return None


class _RD:
    layouts = _Layouts()


class _Cascade:
    state_entries = []

    def __init__(self):
        self.calls = []

    def state_declarations(self, path, props=None):
        self.calls.append((list(path), list(props or [])))
        return {"color": {"value": "#fff", "source": {"sheet": "s", "rule": 1, "selector": ":hover",
                                                      "specificity": 10}}}


class _StateRD:
    def __init__(self):
        self._c = _Cascade()

    def cascade(self):
        return self._c


class ResolutionSwitch(unittest.TestCase):
    def test_the_measured_points_and_their_recorded_settings(self):
        cases = ((1024, 768, "Large UI", SMALL, "ESTIMATE"),     # setting not recorded at 1024 -> never measured
                 (1440, 900, "Large UI", STANDARD, "MEASURED"),
                 (1920, 1080, "Large UI", LARGE, "MEASURED"))
        for w, h, setting, comp, evidence in cases:
            sel = preview.select_breakpoint(dump(), "SquadTileCompositionSet", w, setting, sets=SETS)
            self.assertEqual(sel["composition"], comp, (w, setting))
            self.assertEqual(sel["evidence"], evidence, (w, setting, sel["label"]))

    def test_a_different_ui_setting_is_an_estimate_even_at_a_measured_width(self):
        sel = preview.select_breakpoint(dump(), "SquadTileCompositionSet", 1440, "Small UI", sets=SETS)
        self.assertEqual(sel["evidence"], "ESTIMATE")
        self.assertIn("Large UI", sel["label"])                  # names the setting actually observed
        self.assertIn("Small UI", sel["label"])

    def test_a_measured_point_with_an_unrecorded_window_mode_says_so(self):
        sel = preview.select_breakpoint(dump(), "SquadTileCompositionSet", 1920, "Large UI", sets=SETS)
        self.assertEqual(sel["evidence"], "MEASURED")
        self.assertIn("window mode was not recorded", sel["label"])
        self.assertIn("1920x1080", sel["label"])
        self.assertIn("Large UI", sel["label"])

    def test_the_measured_points_carry_window_mode_and_setting(self):
        pts = {p["width"]: p for p in preview._public_points()}
        self.assertEqual(pts[1440]["window_mode"], "windowed")
        self.assertEqual(pts[1440]["ui_setting"], "Large UI")
        self.assertIsNone(pts[1024]["ui_setting"])
        self.assertIsNone(pts[1024]["window_mode"])
        self.assertEqual(pts[1920]["ui_setting"], "Large UI")

    def test_between_the_points_is_an_estimate_naming_them(self):
        sel = preview.select_breakpoint(dump(), "SquadTileCompositionSet", 1600, "Large UI", sets=SETS)
        self.assertEqual(sel["composition"], STANDARD)
        self.assertEqual(sel["evidence"], "ESTIMATE")
        self.assertIn("1440", sel["label"])
        self.assertIn("1920", sel["label"])

    def test_breakpoint_keys_come_from_the_serialized_set(self):
        # the dump's rows are WRONG; the serialized mapping wins and the disagreement is a named gap
        bad = [_tile("SquadTileCompositionSet", 1, SMALL), _tile("SquadTileCompositionSet", 2, LARGE),
               _tile("SquadTileCompositionSet", 3, LARGE)]
        sel = preview.select_breakpoint(dump(tiles=bad), "SquadTileCompositionSet", 1440, "Large UI", sets=SETS)
        self.assertEqual(sel["breakpoint"], 2)
        self.assertEqual(sel["composition"], STANDARD)           # serialized, not the dump's Large
        self.assertEqual(sel["source"]["asset"], "m_gridBreakpointCompositionData")
        self.assertEqual(sel["cross_check"]["status"], "MISMATCH")
        gap = sel["cross_check"]["gaps"][0]
        self.assertEqual(gap["code"], "G21")
        self.assertEqual(gap["kind"], "composition_mismatch")

    def test_the_dump_agreeing_is_recorded(self):
        sel = preview.select_breakpoint(dump(), "SquadTileCompositionSet", 1440, "Large UI", sets=SETS)
        self.assertEqual(sel["cross_check"]["status"], "AGREE")
        self.assertEqual(sel["gaps"], [])

    def test_without_the_serialized_set_the_keys_are_an_estimate_and_a_named_gap(self):
        sel = preview.select_breakpoint(dump(), "SquadTileCompositionSet", 1440, "Large UI", sets=None)
        self.assertEqual(sel["evidence"], "ESTIMATE")
        self.assertEqual(sel["cross_check"]["gaps"][0]["kind"], "serialized_missing")


class Conditions(unittest.TestCase):
    def test_the_serialized_condition_dicts_are_read_as_their_paths(self):
        comp = {"m_placementBindings": [{"m_elementID": "ClubTeamReport",
                                         "m_optionalConditions": [{"m_path": {"m_path": "game.IsFantasyDraftGame"},
                                                                   "m_inverseCheck": 1}],
                                         "m_optionalConfigConditions": []}],
                "m_optionalSlices": {}}
        slots = preview.extract_slots(comp)
        self.assertEqual(len(slots), 1)
        self.assertEqual(slots[0]["conditions"], ["game.IsFantasyDraftGame (inverse check)"])
        self.assertEqual(slots[0]["condition_data"],
                         [{"path": "game.IsFantasyDraftGame", "inverse": True}])
        # DEFAULT SCENARIO: an ordinary career game, where IsFantasyDraftGame is FALSE - the inverse condition
        # is therefore TRUE and the slot is visible
        self.assertTrue(preview._effective_slots(slots, None)[0]["default"])
        self.assertTrue(preview._effective_slots(slots, None)[0]["visible"])
        self.assertFalse(preview._effective_slots(slots, {"game.IsFantasyDraftGame": True})[0]["visible"])

    def test_the_summary_counts_both_fields(self):
        comp = {"m_optionalConditions": [], "m_optionalConfigConditions": [],
                "m_placementBindings": [{"m_elementID": "A", "m_optionalConditions": [
                    {"m_path": {"m_path": "game.IsDuringMatch"}, "m_inverseCheck": 1}],
                    "m_optionalConfigConditions": [{"m_path": {"m_path": "game.IsFantasyDraftGame"},
                                                    "m_inverseCheck": 0}]}],
                "m_optionalSlices": {"m_bottom": [{"m_elementID": "B",
                                                   "m_optionalConditions": [
                                                       {"m_path": {"m_path": "game.IsDuringMatch"},
                                                        "m_inverseCheck": 0}]}]}}
        slots = preview.extract_slots(comp)
        self.assertEqual({s["element_id"] for s in slots}, {"A", "B"})
        a = next(s for s in slots if s["element_id"] == "A")
        self.assertEqual(a["conditions"], ["game.IsDuringMatch (inverse check)"])
        self.assertEqual(a["config_conditions"], ["game.IsFantasyDraftGame"])


class _StateEntry:
    def __init__(self, pseudo):
        self.rule = {"chains": [([(0, [(preview.P_PSEUDO, pseudo)])], 10, ":%s" % pseudo)], "props": [], "i": 0}


class _StateCascade:
    def __init__(self, *pseudos):
        self.state_entries = [_StateEntry(p) for p in pseudos]


class _OptionsRD:
    def __init__(self, *pseudos):
        self._c = _StateCascade(*pseudos)

    def cascade(self):
        return self._c


class TeamInstructionsSlots(unittest.TestCase):
    COMP = {"m_optionalSlices": {},
            "m_placementBindings": [
                {"m_elementID": "ClubTeamReport",
                 "m_optionalConditions": [{"m_path": {"m_path": "game.IsFantasyDraftGame"}, "m_inverseCheck": 1}],
                 "m_optionalConfigConditions": []},
                {"m_elementID": "DataHub",
                 "m_optionalConditions": [{"m_path": {"m_path": "game.IsFantasyDraftGame"}, "m_inverseCheck": 1}],
                 "m_optionalConfigConditions": []}]}

    def test_ordinary_career_visible_fantasy_draft_hidden(self):
        slots = preview._effective_slots(preview.extract_slots(self.COMP), None)
        self.assertEqual([s["element_id"] for s in slots if s["visible"]], ["ClubTeamReport", "DataHub"],
                         "ordinary career: IsFantasyDraftGame false + inverse check -> visible")
        draft = preview._effective_slots(preview.extract_slots(self.COMP), {"game.IsFantasyDraftGame": True})
        self.assertEqual([s["element_id"] for s in draft if s["visible"]], [],
                         "fantasy draft: IsFantasyDraftGame true + inverse check -> hidden")


class StateOptions(unittest.TestCase):
    def test_declared_states_are_offered_only_where_a_rule_exists(self):
        opts = preview.state_options(_OptionsRD("checked"), [{"type": "Label", "children": []}], {})
        states = [o["state"] for o in opts]
        self.assertIn("checked", states)                        # the sheets declare :checked
        self.assertNotIn("selected", states)                    # no :selected rule
        self.assertNotIn("focus", states)
        self.assertEqual(states[:3], ["normal", "hover", "pressed"])

    def test_a_runtime_state_is_offered_only_when_the_tree_holds_its_type(self):
        tree = [{"type": "VisualElement", "children": []}]
        with_drag = preview.state_options(_OptionsRD(), tree, {"VisualElement": ["drag"]})
        self.assertIn("drag", [o["state"] for o in with_drag])
        plain = preview.state_options(_OptionsRD(), tree, {})
        self.assertNotIn("drag", [o["state"] for o in plain])


class InformationDisplayLock(unittest.TestCase):
    def test_the_locked_combination_is_shown_locked(self):
        lock = preview._lock_for("Large UI", 1024)
        self.assertTrue(lock["locked"])
        self.assertIn("game runtime", lock["reason"])
        self.assertIn("per resolution", lock["reason"])

    def test_the_measured_combinations_are_available(self):
        lock = preview._lock_for("Large UI", 1440)
        self.assertFalse(lock["locked"])
        self.assertIn("MEASURED", lock["evidence"])

    def test_an_untested_combination_says_so(self):
        lock = preview._lock_for("Small UI", 1600)
        self.assertFalse(lock["locked"])
        self.assertTrue(lock["evidence"].startswith("UNKNOWN"))


class Slots(unittest.TestCase):
    COMP = {"m_optionalSlices": {
                "m_bottom": [{"m_elementID": "Always", "m_location": {"x": 0, "y": 0, "width": 4, "height": 2}}],
                "m_top": [{"m_elementID": "MatchOnly", "m_location": {"x": 8, "y": 0, "width": 4, "height": 2},
                           "m_optionalConditions": ["game.IsDuringMatch"]}]},
            "m_placementBindings": []}

    def test_the_default_scenario_is_an_ordinary_career_game(self):
        slots = {s["id"]: s for s in preview._effective_slots(preview.extract_slots(self.COMP), None)}
        self.assertTrue(slots["m_bottom:Always"]["visible"])       # no condition -> visible
        self.assertFalse(slots["m_top:MatchOnly"]["visible"])      # not in a match -> IsDuringMatch false
        self.assertEqual(slots["m_top:MatchOnly"]["conditions"], ["game.IsDuringMatch"])

    def test_in_a_match_the_conditional_slot_is_visible(self):
        slots = {s["id"]: s for s in preview._effective_slots(preview.extract_slots(self.COMP),
                                                             {"game.IsDuringMatch": True})}
        self.assertTrue(slots["m_top:MatchOnly"]["visible"])
        self.assertTrue(slots["m_bottom:Always"]["visible"])

    def test_the_game_state_drives_the_host_and_the_slots_are_preview_data(self):
        d = dump()
        base = preview.build_preview(d, _RD(), "SquadTileCompositionSet", 1440, 900, "Large UI", [], "s",
                                     sets=SETS, composition_data=self.COMP)
        names = [h["host"]["element_id"] for h in base["hosts"]]
        self.assertIn("Always", names)
        self.assertNotIn("MatchOnly", names)                      # ordinary career: not in a match
        in_match = preview.build_preview(d, _RD(), "SquadTileCompositionSet", 1440, 900, "Large UI", [], "s",
                                         sets=SETS, composition_data=self.COMP,
                                         game_states={"game.IsDuringMatch": True})
        self.assertIn("Always", [h["host"]["element_id"] for h in in_match["hosts"]])
        self.assertIn("MatchOnly", [h["host"]["element_id"] for h in in_match["hosts"]])
        option = {o["state"]: o for o in base["game_states"]["options"]}
        self.assertIn("game.IsDuringMatch", option)
        self.assertFalse(option["game.IsDuringMatch"]["default"])
        self.assertIn("preview data", base["slots"][0]["label"])

    def test_the_bundesliga_competition_context_is_preview_data_off_by_default(self):
        base = preview.build_preview(dump(), _RD(), "SquadTileCompositionSet", 1440, 900, "Large UI", [], "s",
                                     sets=SETS, composition_data=self.COMP)
        self.assertFalse(base["competition"]["bundesliga"])
        self.assertFalse(base["competition"]["default"])
        self.assertEqual(base["competition"]["label"], "preview data")
        self.assertEqual(base["competition"]["sheet"], "Bundesliga")
        self.assertEqual(base["competition"]["rules"], 22)
        self.assertIn("off by default", base["competition"]["note"])
        on = preview.build_preview(dump(), _RD(), "SquadTileCompositionSet", 1440, 900, "Large UI", [], "s",
                                   sets=SETS, composition_data=self.COMP, competition=True)
        self.assertTrue(on["competition"]["bundesliga"])
        cmp_ = preview.compare_preview(dump(), _RD(), "SquadTileCompositionSet", (1024, 768), (1920, 1080),
                                       "Large UI", "s", sets=SETS, competition=True)
        self.assertTrue(cmp_["a"]["competition"]["bundesliga"])


class States(unittest.TestCase):
    def test_offered_declared_and_runtime_states(self):
        st, labels = preview._state_names(["normal", "hover", "pressed", "checked", "selected", "focus", "drag"],
                                          [], "VisualElement", {"VisualElement": ["drag"]})
        self.assertIn("hover", st)
        self.assertIn("active", st)                        # pressed -> active
        self.assertIn("checked", st)
        self.assertIn("drag", st)                          # in the measured runtime classes for this type
        self.assertTrue(any("offered" in l for _, l in labels))

    def test_a_code_set_state_not_in_the_runtime_classes_is_not_offered(self):
        st, labels = preview._state_names(["drag"], [], "VisualElement", {})
        self.assertNotIn("drag", st)
        self.assertTrue(any("NOT offered" in l for _, l in labels))

    def test_each_state_reaches_the_cascade_with_enabled_carried(self):
        rd = _StateRD()
        node = {"type": "VisualElement", "name": "x", "children": []}
        preview.state_tree(rd, [node], ["hover"])
        self.assertEqual(node["_states"], {"hover", "enabled"})
        self.assertEqual(len(rd._c.calls), 1)
        self.assertIn("color", node["state_computed"])
        self.assertEqual(node["state_computed"]["color"]["source"]["selector"], ":hover")

    def test_the_default_computed_values_are_not_touched_by_the_state_pass(self):
        rd = _StateRD()
        node = {"type": "VisualElement", "name": "x", "computed": {"color": {"value": "#000"}}, "children": []}
        before = json.dumps(node["computed"], sort_keys=True)
        preview.state_tree(rd, [node], ["hover"])
        self.assertEqual(json.dumps(node["computed"], sort_keys=True), before)


class Determinism(unittest.TestCase):
    def test_same_seed_same_content(self):
        a = preview._placeholder_text("player", "seed-1", "host/path")
        b = preview._placeholder_text("player", "seed-1", "host/path")
        self.assertEqual(a, b)
        self.assertNotEqual(a, "")

    def test_different_seeds_differ_for_the_same_path(self):
        texts = {preview._placeholder_text("player", s, "host/path") for s in ("seed-1", "seed-2", "seed-3")}
        self.assertGreater(len(texts), 1)


class EvidenceFlags(unittest.TestCase):
    def test_exactly_one_flag_per_shape(self):
        node = {"type": "VisualElement", "name": "x", "style": {}, "computed": {}, "children": []}
        self.assertEqual(preview.evidence_flag(node, True), "reconstructed")
        self.assertEqual(preview.evidence_flag(node, False), "reconstructed with estimated geometry")
        self.assertEqual(preview.evidence_flag({**node, "_runtime_slot": True}, True),
                         "runtime-only (not from the bundles)")
        self.assertEqual(preview.evidence_flag({**node, "_placeholder_box": True}, True), "simulated")

    def test_every_node_in_a_decorated_tree_has_exactly_one_flag(self):
        node = {"type": "VisualElement", "name": "root", "children": [
            {"type": "Label", "name": "PlayerName", "text": "sample", "children": []},
            {"type": "PitchElement", "name": "pitch", "children": []}]}
        out = preview.decorate(node, "p", "seed", True)
        allowed = {"reconstructed", "reconstructed with estimated geometry", "simulated",
                   "runtime-only (not from the bundles)"}
        stack = [out]
        seen = 0
        while stack:
            u = stack.pop()
            self.assertIn(u["evidence"], allowed)
            seen += 1
            stack.extend(u.get("children") or [])
        self.assertEqual(seen, 3)

    def test_the_simulated_toggle_hides_placeholders(self):
        node = {"type": "Label", "name": "x", "text": None, "placeholder": "empty", "style": {}, "computed": {},
                "children": []}
        shown = preview.decorate(node, "p", "seed", True, simulated_visible=True)
        hidden = preview.decorate(node, "p", "seed", True, simulated_visible=False)
        self.assertEqual(shown["text"]["flag"], "simulated (seeded placeholder, no real data)")
        self.assertEqual(hidden["text"]["flag"], "simulated content hidden by the toggle")
        self.assertIsNone(hidden["text"]["value"])


class Operations(unittest.TestCase):
    def test_operations_are_unchanged_across_preview_switches_and_pending_elsewhere(self):
        ops = {"placements": [{"composition": STANDARD, "geometry": {"x": 1, "y": 1, "w": 2, "h": 2}}],
               "token_overrides": [], "scoped_rules": [], "image_swaps": []}
        base = preview.build_preview(dump(), _RD(), "SquadTileCompositionSet", 1440, 900, "Large UI", [],
                                     "s", session_operations=ops, sets=SETS)
        self.assertEqual(base["operations"]["applied"], ops["placements"])
        for width, seed in ((1920, "s"), (1440, "other"), (1024, "s")):
            other = preview.build_preview(dump(), _RD(), "SquadTileCompositionSet", width, 900, "Large UI", [],
                                          seed, session_operations=ops, sets=SETS)
            total = len(other["operations"]["applied"]) + len(other["operations"]["pending"])
            self.assertEqual(total, 1, (width, seed))
        at_large = preview.build_preview(dump(), _RD(), "SquadTileCompositionSet", 1920, 1080, "Large UI", [],
                                         "s", session_operations=ops, sets=SETS)
        self.assertEqual(at_large["operations"]["applied"], [])
        self.assertEqual(len(at_large["operations"]["pending"]), 1)   # pending, not lost


class Comparison(unittest.TestCase):
    def test_the_comparison_names_the_compositions_and_the_cell_changes(self):
        cmp_ = preview.compare_preview(dump(), _RD(), "SquadTileCompositionSet", (1024, 768), (1920, 1080),
                                       "Large UI", "s", sets=SETS)
        self.assertEqual(cmp_["a"]["composition"], SMALL)
        self.assertEqual(cmp_["b"]["composition"], LARGE)
        self.assertEqual([c["element_id"] for c in cmp_["cells"]["appear"]], ["B"])
        self.assertEqual([c["element_id"] for c in cmp_["cells"]["changed"]], ["A"])


class LiveWorkspaceGuard(unittest.TestCase):
    def test_the_live_workspace_files_are_unchanged_by_the_test_run(self):
        ws = Path(os.environ.get("FM27SE_WORKSPACE_REAL", "__absent_ws__"))
        targets = [ws / "config.json", ws / "layout" / "current.json"]

        def hashes():
            return {str(t): hashlib.sha256(t.read_bytes()).hexdigest() for t in targets if t.is_file()}
        before = hashes()
        after = hashes()
        self.assertEqual(before, after, "the live workspace changed during the test run")


if __name__ == "__main__":
    unittest.main()
