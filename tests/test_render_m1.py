"""Phase 9 M1: the property map is complete, inferred names are flagged, the cascade matches measured vanilla values (docs/PHASE9-PLAN.md section 1 and 9)."""
import json
import unittest
from tests import gamebuild
from pathlib import Path

from skin_editor.render import values
from skin_editor.render.cascade import Cascade
from skin_editor.render.sheets import Sheet

ROOT = Path(__file__).resolve().parent.parent
CENSUS = ROOT / "data" / "render" / "uss-property-census.json"
AA = gamebuild.aa()                                         # the configured game folder (tests/gamebuild.py), not a typed path

# The only names the map does not classify: rare (at most four uses in 7,545 sheets), mostly CSS-style names that are not USS properties, one id left unnamed.
# A new name appearing in the census fails the test below instead of passing silently.
ALLOWED_UNKNOWN = {"-unity-background-image-tint-height": 4, "-unity-background-image-tint-font-size": 4, "-unity-background-image-tint-width": 1, "transform": 3,
                   "gap": 2, "border-top": 1, "border-right": 1, "border-left": 1, "-unity-id-262145": 1}

# Measured vanilla values: the inspector's fm_get_styles on SIText#club_name_data of the Dortmund main-menu card (2026-11-13, build 27.0.1.2503222, plugin 0.2.2),
# element classes sitext primary-text-colour thematic-xxl sitext-hover-cursor content-wrap: resolved color #EBEBEB, font-size 40.
MEASURED = [{"type": "SIText", "classes": ["primary-text-colour", "thematic-xxl", "sitext-hover-cursor", "content-wrap"], "expect": {"color": "#EBEBEB", "font-size": "40px"},
             "source": "fm_get_styles club_name_data, 2026-11-13, build 27.0.1.2503222"}]


class Census(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.doc = json.loads(CENSUS.read_text(encoding="utf-8"))

    def test_census_covers_every_stylesheet_and_has_no_new_unknown_property(self):
        self.assertGreaterEqual(self.doc["stylesheets"], 7545)
        unknown = {k: v["count"] for k, v in self.doc["unknown"].items()}
        self.assertEqual(unknown, ALLOWED_UNKNOWN, "a property name the map does not know appeared (or one was classified): update the map or this list on purpose")

    def test_every_census_name_still_classifies_as_recorded(self):
        for name, row in self.doc["properties"].items():
            self.assertEqual(values.classify(name)[1], row["status"], name)

    def test_shorthand_longhand_and_inferred_names(self):
        for pid, name in values.ID_NAMES.items():
            self.assertNotEqual(values.classify(name)[1], "unknown", "%s (id %d)" % (name, pid))
            self.assertEqual(values.canonical("-unity-id-%d" % pid), (name, True))
        self.assertEqual(values.canonical("width"), ("width", False))
        self.assertEqual(values.canonical("-unity-id-262145"), ("-unity-id-262145", False))       # left unnamed rather than guessed

    def test_corner_radius_ids_now_map(self):
        self.assertEqual(values.classify(values.canonical("-unity-id-458759")[0])[1], "mapped")


def sheet(pos, name, rules):
    return Sheet(pos, "b", name, {"rules": [{"i": i, "s": s if isinstance(s, list) else [s], "t": False, "p": [[k, v, []] for k, v in props.items()]}
                                            for i, (s, props) in enumerate(rules)]})


class CascadeMore(unittest.TestCase):
    def test_a_later_longhand_overrides_an_earlier_shorthand_and_comma_selectors_use_the_best_match(self):
        s = sheet(0, "s", [(".a", {"margin": "4px"}), ([".b", ".a.c"], {"width": "1px"}), (".a.c", {"margin-left": "9px"})])
        n = {"type": "VisualElement", "name": "", "classes": ["a", "c"], "inline": None, "children": [], "attrs": {}}
        c = Cascade([s], {})
        c.compute([n])
        self.assertEqual(n["computed"]["margin-left"]["value"], "9px")
        self.assertEqual(n["computed"]["margin-top"]["value"], "4px")
        self.assertEqual(n["computed"]["width"]["source"]["specificity"], 21)       # ".a.c" (two classes), not ".b"

    def test_custom_properties_inherit_down_the_tree(self):
        s = sheet(0, "s", [(".p", {"--gap": "5px"}), (".c", {"margin": "var(--gap)"})])
        child = {"type": "VisualElement", "name": "", "classes": ["c"], "inline": None, "children": [], "attrs": {}}
        top = {"type": "VisualElement", "name": "", "classes": ["p"], "inline": None, "children": [child], "attrs": {}}
        Cascade([s], {}).compute([top])
        self.assertEqual(child["computed"]["margin-top"]["value"], "5px")

    def test_inferred_property_names_are_flagged_in_the_result(self):
        s = sheet(0, "s", [(".a", {"-unity-id-458759": "8px"})])
        n = {"type": "VisualElement", "name": "", "classes": ["a"], "inline": None, "children": [], "attrs": {}}
        Cascade([s], {}).compute([n])
        d = n["computed"]["border-bottom-left-radius"]
        self.assertEqual((d["value"], d["status"], d["inferred_name_from"]), ("8px", "mapped", "-unity-id-458759"))


@gamebuild.requires_build
@unittest.skipUnless(AA.is_dir(), "needs the game install")
class MeasuredVanilla(unittest.TestCase):
    def test_cascade_reproduces_the_inspector_values(self):
        from skin_editor import config, index_styles
        from skin_editor.render.service import Renderer
        ws = config.workspace(config.load())
        c = Renderer(AA, ws.cache, index_styles.load(ws)).cascade()
        for m in MEASURED:
            n = {"type": m["type"], "name": "", "classes": m["classes"], "inline": None, "children": [], "attrs": {}}
            c.compute([n])
            for prop, want in m["expect"].items():
                self.assertEqual(n["computed"][prop]["value"], want, "%s (%s)" % (prop, m["source"]))


if __name__ == "__main__":
    unittest.main()
