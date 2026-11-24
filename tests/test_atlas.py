"""Atlas (docs/ATLAS-CONTRACT.md): the cascade extension, the evidence functions and the index validator, on synthetic sheets (no game files)."""
import json
import unittest

from skin_editor import atlas
from skin_editor.render import cascade as rc, sheets as rsheets


def rule(i, sel, props):
    return {"i": i, "s": [sel] if isinstance(sel, str) else sel, "t": False, "p": [[n, v, []] for n, v in props]}


def sheet_set(extra_rules=(), extra_sheets=()):
    """The 7 measured-root sheets (empty except AlwaysAppliedStyleSheet carrying extra_rules), then extra (bundle, name, rules) sheets."""
    out = []
    for k, (b, n, _w) in enumerate(atlas.ROOT_ORDER):
        out.append({"bundle": b, "name": n, "ordinal": k, "rules": list(extra_rules) if n == "AlwaysAppliedStyleSheet" else [], "failures": []})
    for k, (b, n, rules) in enumerate(extra_sheets):
        out.append({"bundle": b, "name": n, "ordinal": 100 + k, "rules": rules, "failures": []})
    return out


PATH = [{"type": "VisualElement", "name": "", "classes": ["panel"]}, {"type": "SIButton", "name": "go", "classes": ["btn"]}]


class CascadeExtension(unittest.TestCase):
    def test_matches_unchanged_and_states_added(self):
        sheets = sheet_set([rule(0, ".btn", [("background-color", "red")]), rule(1, ".btn:hover", [("background-color", "blue")])])
        casc = atlas.make_cascade(sheets)
        rest = casc.matches(atlas.nodes_from_path(PATH))
        self.assertEqual([e.text for e in rest], [".btn"])
        hov = [dict(n, states=["hover"]) for n in PATH]
        ent, resting_ids = casc.matches_with_states(atlas.nodes_from_path(hov))
        self.assertEqual([e.text for e in ent], [".btn", ".btn:hover"])
        self.assertEqual(len(resting_ids), 1)


class RuleEvidence(unittest.TestCase):
    def test_resting_winner_and_hover_only(self):
        sheets = sheet_set([rule(0, ".btn", [("background-color", "red")]), rule(1, ".btn:hover", [("background-color", "blue")]),
                            rule(2, ".panel .btn", [("color", "white")])])
        casc = atlas.make_cascade(sheets)
        rest = atlas.rule_evidence(casc, sheets, PATH, "background-color")
        self.assertEqual((rest["selector"], rest["rule"], rest["hover_only"], rest["active_pseudo_states"]), (".btn", 0, False, []))
        hov = atlas.rule_evidence(casc, sheets, [dict(n, states=["hover"]) for n in PATH], "background-color")
        self.assertEqual((hov["selector"], hov["hover_only"], hov["active_pseudo_states"]), (".btn:hover", True, ["hover"]))
        self.assertEqual(hov["resting_winner"]["selector"], ".btn")
        anc = atlas.rule_evidence(casc, sheets, PATH, "color")
        self.assertEqual(anc["selector"], ".panel .btn")                 # an ancestor selector matches through the path
        self.assertIsNone(atlas.rule_evidence(casc, sheets, PATH, "width"))

    def test_specificity_beats_later_rule(self):
        sheets = sheet_set([rule(0, "#go", [("background-color", "red")]), rule(1, ".btn", [("background-color", "blue")])])
        win = atlas.rule_evidence(atlas.make_cascade(sheets), sheets, PATH, "background-color")
        self.assertEqual((win["selector"], win["specificity"]), ("#go", 101))

    def test_sheet_outside_the_measured_root_does_not_apply(self):
        sheets = sheet_set(extra_sheets=[("ui-styles_assets_match.bundle", "Other", [rule(0, ".btn", [("background-color", "red")])])])
        self.assertIsNone(atlas.rule_evidence(atlas.make_cascade(sheets), sheets, PATH, "background-color"))

    def test_line_numbers_follow_the_printed_sheet(self):
        e = {"bundle": "b", "name": "n", "rules": [rule(0, ".a", [("x", "1"), ("y", "2")]), rule(1, ".b", [("z", "3")])]}
        self.assertEqual(atlas.rule_first_lines(e), [2, 6])             # header, then ".a {" at 2 (4 lines), ".b {" at 6
        from skin_editor import ussprint
        text = ussprint.print_sheet(e).splitlines()
        self.assertTrue(text[1].startswith(".a")) and self.assertTrue(text[5].startswith(".b"))


class CodeSearch(unittest.TestCase):
    def test_every_sheet_searched_and_hits_split(self):
        extra = [("ui-styles_assets_match.bundle", "Elsewhere", [rule(0, ".other", [("background-color", "#20665A")])])]
        sheets = sheet_set([rule(0, ".btn", [("--end-colour", "#20665a")]), rule(1, ".zzz", [("color", "rgb(32, 102, 90)")])], extra)
        forms = ["#20665a", "#20665A", "rgb(32, 102, 90)", "rgba(32, 102, 90, 1)"]
        ev = atlas.code_search(sheets, PATH, forms, "cmd")
        self.assertEqual(ev["sheets_searched"], len(sheets))
        self.assertEqual(len(ev["sheets"]), len(sheets))
        self.assertEqual(ev["matching_selector_hits"], 1)
        self.assertEqual(sorted(h["selector"] for h in ev["coincidental_hits"]), [".other", ".zzz"])
        self.assertTrue(ev["matching_hits"][0]["on_measured_root"])
        none = atlas.code_search(sheets, PATH, ["#010203"], "cmd")
        self.assertEqual((none["matching_selector_hits"], none["coincidental_hits"]), (0, []))
        self.assertEqual(none["sheets_searched"], len(sheets))          # a negative search still covers everything


class Markup(unittest.TestCase):
    def test_complete_and_assembled_tags(self):
        self.assertTrue(atlas.markup_lookup({"text": "<color=#20665a>Hi</color>"}, "text")["complete_tag"])
        quoted = atlas.markup_lookup({"text": '<color="#FFFFFF"><link="0">Bundesliga</link></color>'}, "text")   # the form the live game uses
        self.assertEqual((quoted["complete_tag"], quoted["tag"]), (True, '<color="#FFFFFF">'))
        part = atlas.markup_lookup({"text": "<color={0}>Hi</color>"}, "text")
        self.assertFalse(part["complete_tag"])                           # assembled at run time: the caller must say 'code'
        self.assertIsNone(atlas.markup_lookup({}, "text"))


class IndexValidation(unittest.TestCase):
    def minimal(self):
        return {"meta": {"schema": atlas.INDEX_SCHEMA, "sheet_count": 1}, "sheets": [{"bundle": "b", "name": "n", "ordinal": 0, "rules": 1}],
                "elements": {"e": [{"layout": "L", "guid": "g", "bundle": "b"}]}, "selectors": {".a": [{"sheet": "n", "sheet_ordinal": 0, "rule": 0, "bundle": "b"}]},
                "assets": {}, "gradients": {"g:1": {"holder": "L", "bundle": "b", "asset": "code"}}}

    def test_valid_and_broken(self):
        idx = self.minimal()
        self.assertEqual(atlas.validate_index(idx), [])
        idx["meta"]["sheet_count"] = 2
        self.assertTrue(atlas.validate_index(idx))
        idx = self.minimal()
        idx["selectors"][".a"][0]["sheet"] = "missing"
        self.assertTrue(atlas.validate_index(idx))
        idx = self.minimal()
        idx["gradients"]["g:1"]["asset"] = "nope"
        self.assertTrue(atlas.validate_index(idx))

    def test_dumps_is_deterministic_lf(self):
        a = atlas.dumps({"b": 1, "a": [1, 2]})
        self.assertEqual(a, '{"a":[1,2],"b":1}\n')
        self.assertNotIn("\r", a)


RULE_KEYS = {"selector", "sheet", "sheet_bundle", "sheet_ordinal", "rule", "line", "specificity", "active_pseudo_states", "resting_winner", "hover_only",
             "value", "value_rgba", "reproduce"}
CODE_KEYS = {"command", "sheets_searched", "sheets", "inline_sheets_searched", "needle_forms", "matching_selector_hits", "matching_hits", "coincidental_hits",
             "by_text_only", "by_colour_only"}
MARKUP_KEYS = {"key", "stored", "tag", "complete_tag", "reproduce"}


def rule_c(i, sel, props):
    """A rule with decoded colours for the colour values, as index_styles.sheet_entry makes them."""
    return {"i": i, "s": [sel], "t": False, "p": [[n, v, [[v, 1.0]] if v.startswith("#") else []] for n, v in props]}


class ContractShapes(unittest.TestCase):
    def test_output_keys_are_the_contracts(self):
        sheets = sheet_set([rule_c(0, ".btn", [("background-color", "#20665A")])])
        ev = atlas.rule_evidence(atlas.make_cascade(sheets), sheets, PATH, "background-color", reproduce="cmd")
        self.assertEqual(set(ev), RULE_KEYS)
        self.assertEqual(ev["value_rgba"], {"rgb": "#20665A", "a": 1.0})
        self.assertEqual(ev["sheet_bundle"], "ui-styles_assets_default.bundle")
        code = atlas.code_search(sheets, PATH, ["#20665a"], "cmd", target=("20665a", 1.0))
        self.assertEqual(set(code), CODE_KEYS)
        self.assertEqual(set(atlas.markup_lookup({"text": "<color=#fff>x"}, "text", "cmd")), MARKUP_KEYS)

    def test_checked_winner_is_not_hover_only(self):
        sheets = sheet_set([rule_c(0, ".btn", [("background-color", "#111111")]), rule_c(1, ".btn:checked", [("background-color", "#222222")]),
                            rule_c(2, ".btn:hover", [("background-color", "#333333")])])
        casc = atlas.make_cascade(sheets)
        checked = [dict(n, states=["checked"]) for n in PATH]
        ev = atlas.rule_evidence(casc, sheets, checked, "background-color")
        self.assertEqual((ev["selector"], ev["hover_only"]), (".btn:checked", False))
        both = [dict(n, states=["checked", "hover"]) for n in PATH]
        ev = atlas.rule_evidence(casc, sheets, both, "background-color")
        self.assertEqual((ev["selector"], ev["hover_only"], ev["resting_winner"]["selector"]), (".btn:hover", True, ".btn:checked"))

    def test_code_search_finds_a_colour_the_needles_miss(self):
        sheets = sheet_set([{"i": 0, "s": [".btn"], "t": False, "p": [["background-color", "hsl(165, 53%, 26%)", [["#20665A", 1.0]]]]}])
        ev = atlas.code_search(sheets, PATH, ["#20665a"], "cmd", target=("20665a", 1.0))
        self.assertEqual((ev["matching_selector_hits"], ev["by_colour_only"], ev["by_text_only"]), (1, 1, 0))

    def test_sheet_name_unique_inside_a_bundle(self):
        idx = IndexValidation().minimal()
        idx["sheets"].append({"bundle": "b", "name": "n", "ordinal": 1, "rules": 0})
        idx["meta"]["sheet_count"] = 2
        self.assertTrue(any("twice inside one bundle" in p for p in atlas.validate_index(idx)))



class Amendment1(unittest.TestCase):
    def test_sources_include_inherited_and_initial(self):
        self.assertEqual(set(atlas.SOURCES), {"rule", "inherited", "initial", "inline", "markup", "code"})

    def test_initial_needs_no_declaration_and_the_initial_value(self):
        sheets = sheet_set([rule_c(0, ".other", [("background-color", "#111111")])])
        casc = atlas.make_cascade(sheets)
        ev = atlas.initial_evidence(casc, sheets, PATH, "background-color", "#00000000", reproduce="cmd")
        self.assertEqual((ev["initial_value"], ev["declarations_found_on_path"]), ("#00000000", 0))
        self.assertIsNone(atlas.initial_evidence(casc, sheets, PATH, "background-color", "#00000001"))       # not the initial value
        declared = sheet_set([rule_c(0, ".btn", [("background-color", "#111111")])])
        self.assertIsNone(atlas.initial_evidence(atlas.make_cascade(declared), declared, PATH, "background-color", "#00000000"))   # a rule declares it


if __name__ == "__main__":
    unittest.main()
