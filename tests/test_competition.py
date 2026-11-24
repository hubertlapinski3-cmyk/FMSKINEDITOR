"""Competition-sheet reach warnings (Stage 5I part 2): Bundesliga only where its rules set colour/font/size on
an element an edit touches; competition sheets that redefine an edited token in that token's reach. The
competition sheet's own definitions are a separate per-project choice, OFF by default.

Synthetic style index: no game file is read; the live set C shape is covered by the evidence run."""
import unittest

from skin_editor import competition, playops
from skin_editor.index_styles import StyleIndex

BUNDLE = "ui-styles_assets_default.bundle"


def sheets():
    return [
        {"bundle": BUNDLE, "name": "Bundesliga", "failures": [], "rules": [
            {"i": 0, "s": [":root"], "t": True,
             "p": [["--bundesliga-size-card", "var(--typography-size-16)", []],
                   ["--bundesliga-family-bold", "asset(18:1)", []]]},
            {"i": 1, "s": [".prematch-table-bundesliga"], "t": False,
             "p": [["background-color", "var(--colours-bundesliga-prematch-dark)", []]]},
            {"i": 2, "s": [".prematch-lineup-bundesliga"], "t": False,
             "p": [["background-color", "var(--colours-bundesliga-prematch-dark)", []]]},
            {"i": 3, "s": [".bundesliga-font"], "t": False, "p": [["font", "asset(18:2)", []]]},
            {"i": 4, "s": [".bundesliga-table-text-scoreboard"], "t": False,
             "p": [["font-size", "18px", []], ["padding", "4px", []]]},
            {"i": 5, "s": [".layout-unrelated"], "t": False, "p": [["color", "#fff", []]]},
            {"i": 6, "s": [".bundesliga-layout-only"], "t": False, "p": [["padding", "4px", []]]},
        ]},
        {"bundle": BUNDLE, "name": "AlwaysAppliedStyleSheet", "failures": [], "rules": [
            {"i": 0, "s": [".tactics-tile"], "t": False, "p": [["color", "#fff", []]]},
        ]},
    ]


def style_op(kind, selector, props):
    target = {"screen": "SquadScreen", "logical_id": "joined/%s" % selector,
              "locator": {"bundle": BUNDLE, "path_id": "1"}, "guard": {"type": "VisualElement",
                                                                      "name": "joined", "classes": []}}
    return playops.new_operation(kind, target, {"rule": {"sheet": {"bundle": BUNDLE, "name": "Bundesliga"},
                                                         "selector": selector, "props": props,
                                                         "reach": {"elements": 1, "layouts": 1, "screens": 1,
                                                                   "measured_by": "layout.reach"}}})


def token_op(token):
    target = {"screen": "SquadScreen", "logical_id": "token", "locator": {"bundle": BUNDLE, "path_id": "1"},
              "guard": {"type": "VisualElement", "name": "x", "classes": []}}
    return playops.new_operation("ReplaceToken", target, {"token": token, "value": "#112233",
                                                          "route": {"chosen": "token", "reason": "x"}})


class BundesligaWarnings(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.index = StyleIndex(sheets())

    def test_warns_only_where_a_colour_font_or_size_rule_touches_the_edit(self):
        touching = competition.bundesliga_warnings(self.index, [style_op(
            "SetColor", ".prematch-table-bundesliga", {"background-color": "#112233"})])
        self.assertEqual(len(touching), 1)
        self.assertEqual(touching[0]["sheet"], "Bundesliga")
        self.assertEqual(touching[0]["properties"], ["background-color"])
        self.assertEqual(touching[0]["bundle"], BUNDLE)
        self.assertIn("competition", touching[0]["reason"])
        layout_only = competition.bundesliga_warnings(self.index, [style_op(
            "SetSpacing", ".bundesliga-layout-only", {"padding": "8px"})])
        self.assertEqual(layout_only, [])              # padding is not colour/font/size
        typography = competition.bundesliga_warnings(self.index, [style_op(
            "SetSpacing", ".bundesliga-table-text-scoreboard", {"padding": "8px"})])
        self.assertEqual(typography[0]["properties"], ["font-size"])   # the same rule sets a size
        no_match = competition.bundesliga_warnings(self.index, [style_op(
            "SetColor", ".layout-unrelated-x", {"color": "#112233"})])
        self.assertEqual(no_match, [])

    def test_lists_competition_sheets_that_redefine_the_edited_token(self):
        rows = competition.token_competition_sheets(self.index, [token_op("--bundesliga-size-card")])
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["redefined_by"][0]["sheet"], "Bundesliga")
        self.assertEqual(rows[0]["redefined_by"][0]["definitions"], 1)
        self.assertEqual(rows[0]["token"], "--bundesliga-size-card")
        self.assertEqual(competition.token_competition_sheets(self.index, [token_op("--not-competition")]), [])

    def test_the_warning_block_reports_the_project_choice_off_by_default(self):
        block = competition.warnings(self.index, [token_op("--bundesliga-size-card")])
        self.assertFalse(block["edit_competition_sheets"])
        self.assertEqual(block["default"], "off")
        self.assertIn("OFF by default", block["note"])
        on = competition.warnings(self.index, [], edit_competition_sheets=True)
        self.assertTrue(on["edit_competition_sheets"])
        self.assertEqual(competition.warnings(None, []), {"bundesliga_rules": [],
                                                          "token_competition_sheets": [],
                                                          "edit_competition_sheets": False,
                                                          "default": "off", "note": competition.NOTE})


if __name__ == "__main__":
    unittest.main()
