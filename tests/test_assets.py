"""M4: asset(F:P) resolution (the sheet's bundle, never a global file id), the render-tree pass, font naming, sample-text labelling."""
import unittest
from tests import gamebuild
from pathlib import Path

from skin_editor.render import assets
from skin_editor.render.html import placeholder_kind, placeholder_text, font_label, to_html, switch_branch_rule

AA = gamebuild.aa()                                         # the configured game folder (tests/gamebuild.py), not a typed path


class Fake:
    """A resolver that records the source bundle it was asked with and knows two assets."""
    def __init__(self):
        self.asked = []

    def resolve(self, bundle, fid, pid):
        self.asked.append((bundle, fid, pid))
        if (fid, pid) == (11, 5):
            return {"bundle": "fonts.bundle", "path_id": pid, "type": "MonoBehaviour", "name": "ABCSocial-Regular SDF"}
        if (fid, pid) == (3, 7):
            return {"bundle": "icons.bundle", "path_id": pid, "type": "Sprite", "name": "icon"}
        return {"error": "file id %d is outside the externals of %s" % (fid, bundle)}


class FakeDrawn:
    def sprite_data_url(self, bundle, pid, tint=None):
        return "data:image/png;base64,AAAA" + (tint or "")


def node(name, props, children=(), **kw):
    comp = {k: {"value": v, "source": s, "status": "partial", "note": ""} for k, (v, s) in props.items()}
    return dict({"type": "VisualElement", "name": name, "computed": comp, "children": list(children), "attrs": {}}, **kw)


class Refs(unittest.TestCase):
    def test_parse_and_font_family(self):
        self.assertEqual(assets.parse_ref("asset(3:8088184964230055163)"), (3, 8088184964230055163))
        self.assertIsNone(assets.parse_ref("none"))
        self.assertEqual(assets.font_family("ABCSocial-Regular SDF"), ("ABCSocial", "Regular"))
        self.assertEqual(assets.font_family("Roboto"), ("Roboto", "Regular"))


class Pass(unittest.TestCase):
    def test_the_bundle_a_value_is_resolved_against_is_the_one_its_sheet_was_read_from(self):
        r = Fake()
        icon = node("icon", {"background-image": ("asset(3:7)", {"sheet": "FMImages_2x"})})
        assets.apply_assets([icon], r, "layout.bundle", {"FMImages_2x": "ui-styles_assets_2x.bundle"}, FakeDrawn())
        self.assertEqual(r.asked, [("ui-styles_assets_2x.bundle", 3, 7)])
        self.assertEqual(icon["computed"]["background-image"]["status"], "mapped")
        self.assertTrue(icon["assets"]["background-image"]["data_url"].startswith("data:image/png"))

    def test_an_inherited_font_reuses_the_declaring_ancestors_resolution(self):
        child = node("child", {"-unity-font-definition": ("asset(11:5)", None)})
        parent = node("parent", {"-unity-font-definition": ("asset(11:5)", {"sheet": "AlwaysAppliedStyleSheet"})}, [child])
        counts = assets.apply_assets([parent], Fake(), "layout.bundle", {"AlwaysAppliedStyleSheet": "ui-styles_assets_default.bundle"}, FakeDrawn())
        self.assertEqual(child["assets"]["-unity-font-definition"]["family"], "ABCSocial")
        self.assertTrue(child["assets"]["-unity-font-definition"]["inherited"])
        self.assertEqual(counts["unresolved"], 0)
        self.assertEqual(font_label(child), "ABCSocial Regular")
        self.assertIn("stand-in", parent["computed"]["-unity-font-definition"]["note"])          # the font is named, not rendered

    def test_an_unresolvable_reference_is_a_labelled_placeholder_not_a_silent_gap(self):
        bad = node("bad", {"background-image": ("asset(9:9)", {"sheet": "S"})})
        counts = assets.apply_assets([bad], Fake(), "l.bundle", {"S": "s.bundle"}, FakeDrawn())
        self.assertEqual(counts["unresolved"], 1)
        self.assertIn("not resolved", bad["computed"]["background-image"]["note"])
        self.assertIn("labelled placeholder", bad["computed"]["background-image"]["note"])
        self.assertEqual(bad["computed"]["background-image"]["status"], "partial")

    def test_a_tint_is_multiplied_in_and_flagged_mapped(self):
        icon = node("icon", {"background-image": ("asset(3:7)", {"sheet": "S"}), "-unity-background-image-tint-color": ("#4EEB3D", {"sheet": "S"})})
        assets.apply_assets([icon], Fake(), "l.bundle", {"S": "s.bundle"}, FakeDrawn())
        self.assertTrue(icon["assets"]["background-image"]["tinted"])
        self.assertEqual(icon["computed"]["-unity-background-image-tint-color"]["status"], "mapped")


class Labels(unittest.TestCase):
    def test_bound_text_is_labelled_sample_or_empty_and_set_text_is_not(self):
        t = lambda a: {"type": "SIText", "attrs": a, "computed": {}, "children": []}
        self.assertEqual(placeholder_kind(t({"text": "LOANS"})), "set")
        self.assertEqual(placeholder_kind(t({"DebugDisplay": "7 players injured"})), "sample")
        self.assertEqual(placeholder_kind(t({})), "empty")
        self.assertEqual(placeholder_text(t({"DebugDisplay": "title", "TextCase": 1})), "TITLE")
        self.assertIsNone(placeholder_kind({"type": "VisualElement", "attrs": {}, "computed": {}, "children": []}))

    def test_the_html_marks_sample_text_and_names_the_font(self):
        txt = {"type": "SIText", "name": "t", "attrs": {"DebugDisplay": "Sample"}, "computed": {}, "children": [], "assets": {"-unity-font-definition": {"family": "ABCSocial", "weight": "Regular"}}}
        html, _ = to_html([txt], 100, 20)
        self.assertIn('data-placeholder="sample"', html)
        self.assertIn('data-font="ABCSocial Regular"', html)

    def test_a_switch_shows_one_branch_and_says_so(self):
        a, b = node("a", {}), node("b", {})
        sw = {"type": "BindableSwitchElement", "name": "", "computed": {}, "children": [a, b], "attrs": {}}
        switch_branch_rule([sw], {0: 1})
        self.assertEqual((sw["shown"], sw["branches"]), (1, 2))
        self.assertEqual(a["layout_rules"], ["switch-branch-not-shown"])
        self.assertNotIn("layout_rules", b)


@gamebuild.requires_build
@unittest.skipUnless(AA.is_dir(), "needs the game install")
class Real(unittest.TestCase):
    def test_the_two_worked_examples_resolve_with_their_own_source_bundles(self):
        import tempfile
        r = assets.AssetResolver(AA, tempfile.mkdtemp())
        f = r.resolve("ui-styles_assets_default.bundle", 11, 5636211117028388537)
        self.assertEqual((f["type"], f["name"]), ("MonoBehaviour", "ABCSocial-Regular SDF"))
        i = r.resolve("ui-styles_assets_2x.bundle", 3, 8088184964230055163)
        self.assertEqual((i["type"], i["name"]), ("Sprite", "level=injured, size=medium 24px_2x"))
        self.assertIn("error", r.resolve("ui-styles_assets_2x.bundle", 99, 1))             # an index outside the externals is an error, not a guess


if __name__ == "__main__":
    unittest.main()
