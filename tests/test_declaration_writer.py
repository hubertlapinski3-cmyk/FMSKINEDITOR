"""Stage 5H: the per-declaration writer (handle bundle/sheet/normalized selector/occurrence/property/old).

Uses archived set C only, read only. The writer replaces the WHOLE value list, so var() -> literal is supported."""
import copy
import unittest
from pathlib import Path

from skin_editor import index_styles, project, token_patch as tp
from skin_editor.render.service import Renderer
import tempfile

SETC = Path(r"__absent_fixture_path__")


@unittest.skipUnless((SETC / "ui-styles_assets_default.bundle").is_file(), "archived set C not present")
class DeclarationWriter(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(prefix="fm27se-decl-")
        cls.addClassCleanup(cls.tmp.cleanup)
        rd = Renderer(str(SETC), str(Path(cls.tmp.name) / "cache"), None)
        cls.bundle = "ui-styles_assets_default.bundle"
        objs = rd.layouts._bundle_objs(cls.bundle)
        cls.tree = None
        for obj in objs.values():
            try:
                t = obj.read_typetree()
            except Exception:
                continue
            if isinstance(t, dict) and t.get("m_Name") == "AlwaysAppliedStyleSheet":
                cls.tree = t
                break
        assert cls.tree is not None
        cls.spec = project.to_spec(project.new("decl-writer", "27.1.0.2505117"))

    def handle(self, selector, prop, old, occurrence=0):
        return {"bundle": self.bundle, "sheet": "AlwaysAppliedStyleSheet", "selector": selector,
                "occurrence": occurrence, "property": prop, "old": old, "new": "#FF00FF"}

    def entry(self, tree):
        return index_styles.sheet_entry(self.bundle, tree)

    def find(self, tree, selector, prop):
        want = tp.selector_key(selector)
        for r in self.entry(tree)["rules"]:
            if tp.selector_key(", ".join(r["s"])) == want:
                for p in r["p"]:
                    if p[0] == prop:
                        return r["i"], p
        return None, None

    def test_var_to_literal_changes_only_that_declaration(self):
        tree = copy.deepcopy(self.tree)
        before = self.entry(tree)
        sp = tp.SheetPatcher(tree, self.spec)
        hits, changed = sp.set_declaration(self.handle(".layout-tile-tactics .layout-tile-base-container",
                                                        "background-color",
                                                        "var(--pitch-tile-default-background)"))
        self.assertEqual((hits, changed), (1, 1))
        after = self.entry(tree)
        self.assertEqual(len(after["rules"]), len(before["rules"]))          # rule count unchanged
        i, p = self.find(tree, ".layout-tile-tactics .layout-tile-base-container", "background-color")
        self.assertEqual(p[1], "#FF00FF")
        # only that one declaration differs anywhere in the sheet
        flat_before = [(r["i"], prop[0], prop[1]) for r in before["rules"] for prop in r["p"]]
        flat_after = [(r["i"], prop[0], prop[1]) for r in after["rules"] for prop in r["p"]]
        diffs = [a for a, b in zip(flat_before, flat_after) if a != b]
        self.assertEqual(diffs, [(i, "background-color", "var(--pitch-tile-default-background)")])

    def test_every_other_rule_and_declaration_is_identical_and_colors_only_grow(self):
        tree = copy.deepcopy(self.tree)
        before_rules = copy.deepcopy(tree["m_Rules"])
        before_colors = copy.deepcopy(tree["colors"])
        sp = tp.SheetPatcher(tree, self.spec)
        sp.set_declaration(self.handle(".layout-tile-tactics .layout-tile-base-container",
                                       "background-color", "var(--pitch-tile-default-background)"))
        # decode both and compare rule by rule; only the target declaration may differ
        a, b = self.entry({**tree, "m_Rules": before_rules}), self.entry(tree)
        self.assertEqual(len(a["rules"]), len(b["rules"]))
        diffs = []
        for ra, rb in zip(a["rules"], b["rules"]):
            if ra != rb:
                diffs.append(ra["i"])
        i, _p = self.find(tree, ".layout-tile-tactics .layout-tile-base-container", "background-color")
        self.assertEqual(diffs, [i])
        # typetree: every other rule object identical, target rule differs only in that property's m_Values
        for idx, (ra, rb) in enumerate(zip(before_rules, tree["m_Rules"])):
            if idx != i:
                self.assertEqual(ra, rb)
            else:
                self.assertEqual({k: v for k, v in ra.items() if k != "m_Properties"},
                                 {k: v for k, v in rb.items() if k != "m_Properties"})
                differing = [k for k, (pa, pb) in enumerate(zip(ra["m_Properties"], rb["m_Properties"])) if pa != pb]
                self.assertEqual(len(differing), 1)
                self.assertEqual(_p[0], "background-color")
        # the colour table only grows; no existing entry changed
        self.assertGreaterEqual(len(tree["colors"]), len(before_colors))
        self.assertEqual(tree["colors"][:len(before_colors)], before_colors)

    def test_literal_to_literal(self):
        tree = copy.deepcopy(self.tree)
        sp = tp.SheetPatcher(tree, self.spec)
        sp.set_declaration(self.handle(":root", "--pitch-tile-default-background", "#03614F"))
        _, p = self.find(tree, ":root", "--pitch-tile-default-background")
        self.assertEqual(p[1], "#FF00FF")

    def test_the_patcher_applies_a_declaration_edit_and_records_it(self):
        from skin_editor import patcher
        tree = copy.deepcopy(self.tree)
        spec = dict(self.spec)
        spec["declaration_edits"] = [self.handle(".layout-tile-tactics .layout-tile-base-container",
                                                 "background-color", "var(--pitch-tile-default-background)")]
        acc = patcher.new_acc()
        changed = patcher.apply_declaration_edits(tree, self.bundle, spec, acc)
        self.assertTrue(changed)
        self.assertEqual(acc["declaration_edits"][0]["property"], "background-color")
        _, p = self.find(tree, ".layout-tile-tactics .layout-tile-base-container", "background-color")
        self.assertEqual(p[1], "#FF00FF")

    def test_two_bundle_builds_are_byte_identical_and_only_one_object_changes(self):
        import tempfile
        from skin_editor import bundlediff, bundles, patcher
        spec = dict(self.spec)
        spec["declaration_edits"] = [self.handle(".layout-tile-tactics .layout-tile-base-container",
                                                 "background-color", "var(--pitch-tile-default-background)")]
        outs = []
        for i in range(2):
            out = Path(tempfile.mkdtemp(prefix="fm27se-decl-b%d-" % i))
            acc = patcher.new_acc()
            bundles.patch_bundle(SETC / self.bundle, out,
                                 lambda tree: patcher.apply_declaration_edits(tree, self.bundle, spec, acc), set())
            outs.append(out / self.bundle)
        self.assertEqual(bundles.sha256(outs[0]), bundles.sha256(outs[1]))
        cmp_ = bundlediff.compare(SETC / self.bundle, outs[0])
        self.assertEqual(len(cmp_["object"]["changed_objects"]), 1)
        self.assertTrue(cmp_["object"]["object_set_equal"])

    def test_a_stale_or_ambiguous_handle_is_refused(self):
        sp = tp.SheetPatcher(copy.deepcopy(self.tree), self.spec)
        with self.assertRaises(ValueError):
            sp.set_declaration(self.handle(".layout-tile-tactics .layout-tile-base-container",
                                            "background-color", "#03614F"))          # wrong old value
        with self.assertRaises(ValueError):
            sp.set_declaration(self.handle(".layout-tile-tactics .layout-tile-base-container",
                                            "background-color", "var(--pitch-tile-default-background)",
                                            occurrence=1))                            # only one occurrence
        with self.assertRaises(ValueError):
            sp.set_declaration(self.handle(".not-a-selector", "background-color", "#03614F"))


if __name__ == "__main__":
    unittest.main()
