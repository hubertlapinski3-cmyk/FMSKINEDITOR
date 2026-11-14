"""Phase 9 M0: values, cascade, includes by GUID, the parsed-layout cache and the LoansTile_4x2 spike (docs/PHASE9-PLAN.md).
Synthetic tests run anywhere; the real-data tests run when the game is installed and skip otherwise."""
import time
import unittest
from pathlib import Path

from skin_editor.render import values
from skin_editor.render.cascade import Cascade
from skin_editor.render.sheets import Sheet

AA = Path(r"C:\Program Files (x86)\Steam\steamapps\common\Football Manager 27\fm_Data\StreamingAssets\aa\StandaloneWindows64")
TILE = ("ui-visualtreeassets_assets_gameworldvisualtreeassetpreload.bundle", "-3957983696827071101")      # LoansTile_4x2
# the element order of the c2 session's inspector tree of this tile (2026-11-13, build 27.0.1.2503222), top node first: the structural fixture
C2_ORDER = ["BindingExpect#TileBindingExpect", "ComponentElement#", "TemplateContainer#tile-wide-4x2", "BindingExpect#TileTemplateBindingExpect",
            "VisualElement#layout-tile-base-container", "BindingVariables#TileVariables", "SIStyleSetter#BackgroundStyleSetter",
            "SIButton#layout-tile-interaction-button", "VisualElement#Border_TIle", "VisualElement#title area frame", "AutoScroller#auto-scroller",
            "TemplateContainer#states-templates-tile-content", "VisualElement#Frame_1000002538", "VisualElement#Frame_1000003021", "StreamedTable#"]


def sheet(pos, name, rules):
    """rules: [(selector text(s), {prop: value})]"""
    return Sheet(pos, "b", name, {"rules": [{"i": i, "s": s if isinstance(s, list) else [s], "t": False, "p": [[k, v, []] for k, v in props.items()]}
                                            for i, (s, props) in enumerate(rules)]})


def node(type_="VisualElement", name="", classes=(), inline=None, children=()):
    return {"type": type_, "name": name, "classes": list(classes), "inline": inline, "children": list(children), "attrs": {}, "kind": "element"}


class Values(unittest.TestCase):
    def test_tokens_and_functions(self):
        self.assertEqual(values.split_top("var(--a, 4px) 2px, 3px"), ["var(--a, 4px)", "2px", ",", "3px"])
        self.assertEqual(values.parse("12px")[0], {"k": "dim", "v": 12.0, "unit": "px", "raw": "12px"})
        self.assertEqual(values.parse("#FF000080")[0]["k"], "color")
        self.assertEqual(values.parse("linear-gradient(a, b)")[0]["k"], "func")

    def test_var_resolution_chain_fallback_and_unresolved(self):
        scope = {"--a": "var(--b)", "--b": "7px"}
        chain = []
        self.assertEqual(values.resolve_vars("var(--a)", scope.get, chain), ("7px", []))
        self.assertEqual(chain, ["--a", "--b"])
        self.assertEqual(values.resolve_vars("var(--zz, 3px)", scope.get)[0], "3px")
        self.assertEqual(values.resolve_vars("var(--zz) 1px", scope.get), ("var(--zz) 1px", ["--zz"]))

    def test_shorthands(self):
        self.assertEqual(values.expand("margin", "1px 2px"), [("margin-top", "1px"), ("margin-right", "2px"), ("margin-bottom", "1px"), ("margin-left", "2px")])
        self.assertEqual(values.expand("flex", "1 0 0"), [("flex-grow", "1"), ("flex-shrink", "0"), ("flex-basis", "0px")])
        self.assertEqual(values.expand("border-radius", "4px")[3], ("border-bottom-left-radius", "4px"))
        self.assertEqual(values.expand("width", "5px"), [("width", "5px")])

    def test_no_property_is_dropped_silently(self):
        self.assertEqual(values.classify("width")[1], "mapped")
        self.assertEqual(values.classify("-unity-text-align")[1], "partial")
        self.assertEqual(values.classify("transition")[1], "unmapped")
        self.assertEqual(values.classify("margin")[1], "shorthand")
        self.assertEqual(values.classify("--x")[1], "variable")
        self.assertEqual(values.classify("-unity-id-393218")[1], "unknown")
        self.assertEqual(values.classify("made-up")[1], "unknown")
        self.assertEqual(values.to_css("transition", "1s"), [])             # not drawn, but classified: the caller keeps it flagged


class CascadeRules(unittest.TestCase):
    def run_cascade(self, sheets, top, rc=None):
        c = Cascade(sheets, rc or {})
        c.compute([top])
        return c

    def test_specificity_beats_order_and_later_sheet_wins_at_equal_specificity(self):
        s1 = sheet(0, "one", [(".a", {"width": "1px"}), ("#x", {"height": "9px"})])
        s2 = sheet(1, "two", [(".a", {"width": "2px"}), (".a", {"height": "5px"})])
        n = node(name="x", classes=["a"])
        self.run_cascade([s1, s2], n)
        self.assertEqual(n["computed"]["width"]["value"], "2px")            # equal specificity: later sheet
        self.assertEqual(n["computed"]["height"]["value"], "9px")           # id beats class even though it is earlier
        self.assertEqual(n["computed"]["width"]["source"]["sheet"], "two")

    def test_inline_wins_and_combinators(self):
        s = sheet(0, "s", [(".p .c", {"color": "#111111"}), (".p > .c", {"color": "#222222"}), (".c", {"color": "#333333", "width": "1px"})])
        child = node(classes=["c"], inline=[["width", "8px"]])
        top = node(classes=["p"], children=[node(children=[child])])        # the child is a grandchild: ".p > .c" must not match
        self.run_cascade([s], top)
        self.assertEqual(child["computed"]["color"]["value"], "#111111")    # descendant (spec 21) beats the plain class
        self.assertEqual(child["computed"]["width"]["value"], "8px")
        self.assertTrue(child["computed"]["width"]["source"]["inline"])

    def test_state_selectors_are_skipped_and_counted_and_root_variables_feed_var(self):
        s = sheet(0, "s", [(":root", {"--gap": "6px"}), (".a:hover", {"width": "99px"}), (".a", {"margin": "var(--gap)", "padding": "var(--missing)"})])
        n = node(classes=["a"])
        c = self.run_cascade([s], n)
        self.assertEqual(c.stats["state_selectors_skipped"], 1)
        self.assertNotIn("width", n["computed"])
        self.assertEqual(n["computed"]["margin-left"]["value"], "6px")
        self.assertEqual(n["computed"]["margin-left"]["tokens"], ["--gap"])
        self.assertEqual(n["computed"]["padding-top"]["unresolved"], ["--missing"])      # reported, never silent
        self.assertEqual(c.summary["unresolved_variables"], {"--missing": 4})

    def test_inheritance_and_runtime_classes_and_status(self):
        s = sheet(0, "s", [(".sitext", {"color": "#ABCDEF", "transition": "opacity 1s"}), (".p", {"font-size": "20px"})])
        t = node("SIText")
        top = node(classes=["p"], children=[t])
        c = self.run_cascade([s], top, rc={"SIText": ["sitext"]})
        self.assertIn("sitext", t["_classes"])
        self.assertEqual(t["computed"]["font-size"]["value"], "20px")
        self.assertTrue(t["computed"]["font-size"]["source"]["inherited"])
        self.assertEqual(t["computed"]["transition"]["status"], "unmapped")           # kept in the data, flagged
        self.assertEqual(t["computed"]["color"]["status"], "mapped")
        self.assertGreaterEqual(c.summary["by_status"].get("unmapped", 0), 1)

    def test_non_visual_components_are_not_elements(self):
        comp = node("BindingRemapperComponent")
        top = node(children=[comp, node("SIText")])
        self.run_cascade([sheet(0, "s", [])], top)
        self.assertEqual([c["type"] for c in top["children"]], ["SIText"])
        self.assertEqual(top["components"], ["BindingRemapperComponent"])


@unittest.skipUnless(AA.is_dir(), "needs the game install")
class RealTile(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from skin_editor import config, index_styles
        from skin_editor.render.service import Renderer
        cls.ws = config.workspace(config.load())
        cls.R = Renderer(AA, cls.ws.cache, index_styles.load(cls.ws))
        cls.out = cls.R.layout(*TILE)

    @staticmethod
    def flat(top):
        from skin_editor.render.html import flatten
        return flatten(top)

    def test_includes_resolve_by_guid_and_the_tree_matches_the_c2_inspector_order(self):
        inc = {i["alias"]: i for i in self.out["includes"]}
        self.assertTrue(inc["tile-wide-4x2"]["resolved"])
        self.assertEqual(inc["tile-wide-4x2"]["layout"], "tile-figma-base-template")      # alias differs from the layout name: the GUID did it
        names = ["%s#%s" % (n["type"], n.get("name", "")) for n in self.flat(self.out["tree"])]
        pos = -1
        for want in C2_ORDER:                                      # every inspector element appears, in the inspector's order (render may have more)
            self.assertIn(want, names[pos + 1:], want)
            pos = names.index(want, pos + 1)

    def test_known_cascade_results(self):
        t = next(n for n in self.flat(self.out["tree"]) if n["type"] == "SIText" and "heading-md" in n["classes"])
        self.assertEqual(t["computed"]["font-size"]["value"], "16px")                  # .heading-md -> --heading-md-size -> --typography-size-16
        self.assertEqual(t["computed"]["font-size"]["tokens"], ["--heading-md-size", "--typography-size-16"])
        self.assertIn("sitext", t["_classes"])                                         # a learned runtime class
        self.assertEqual(self.out["summary"]["unresolved_variables"], {})

    def test_the_render_call_is_inside_the_budget_when_cached(self):
        t0 = time.perf_counter()
        self.R.layout(*TILE)
        self.assertLess((time.perf_counter() - t0) * 1000, 200)                        # owner requirement: under 200 ms cached per layout

    def test_gaps_and_notice_are_always_reported(self):
        self.assertTrue(self.out["gaps"])
        self.assertIn("Approximation", self.out["notice"])
        self.assertEqual(self.out["sheet_order"][1]["sheet"], "AlwaysAppliedStyleSheet")


if __name__ == "__main__":
    unittest.main()
