"""M7: the render calibration fixtures. `test_every_fixture_runs_and_no_new_failure_appears` runs every folder under tests/fixtures/render against the game's data and fails on a failure
that is not in baseline.json (the published list of known failures, each with its cause in the calibration report); an improvement never fails it. The other tests cover the framework."""
import json
import tempfile
import unittest
from pathlib import Path

from skin_editor.render import delivered, fixtures
from skin_editor.render.measure import edge_path

AA = Path(r"C:\Program Files (x86)\Steam\steamapps\common\Football Manager 27\fm_Data\StreamingAssets\aa\StandaloneWindows64")
BASELINE = fixtures.FIXTURES / "baseline-failures.json"


class Framework(unittest.TestCase):
    def test_the_tolerance_is_eight_pixels_or_five_percent_whichever_is_tighter(self):
        self.assertEqual(fixtures.tol(100, 0), 5.0)
        self.assertEqual(fixtures.tol(1000, 0), 8.0)
        self.assertEqual(fixtures.tol(0, 40), 2.0)                      # a zero-size element is judged against the root

    def test_colours_and_numbers_compare_exactly_in_their_own_forms(self):
        self.assertTrue(fixtures.same("color", "#EBEBEB", "#EBEBEBFF"))
        self.assertFalse(fixtures.same("color", "#EBEBEB", "#EBEBEC"))
        self.assertTrue(fixtures.same("font-size", 14, "14px"))
        self.assertFalse(fixtures.same("font-size", 14, "14.5px"))
        self.assertTrue(fixtures.same("flex-direction", "Column", "column"))

    def test_every_discovered_folder_is_a_complete_fixture(self):
        found = fixtures.discover()
        self.assertGreaterEqual(len(found), 17)
        for f in found:
            fx = fixtures.load(f)
            self.assertIn("kind", fx["fixture"], f.name)
            self.assertTrue(fx["expect"]["checks"], f.name)
            self.assertTrue(fx["fixture"].get("source"), f.name)           # every fixture says where its truth comes from

    def test_report_publishes_passes_failures_and_not_applicables_together(self):
        rows = [{"fixture": "f", "check": "c", "element": "e%d" % i, "property": "p", "expected": 1, "got": 2, "delta": None, "verdict": v, "note": ""} for i, v in enumerate(("PASS", "FAIL", "N/A"))]
        res = [{"name": "f", "source": "s", "build": "b", "rows": rows, "delivered": {"paired": 1, "nodes": 2, "unpaired_texts": 0, "ambiguous_keys": 0}, "counts": {"PASS": 1, "FAIL": 1, "N/A": 1}}]
        out = Path(tempfile.mkdtemp())
        tot = fixtures.report(res, out)
        self.assertEqual(tot, {"PASS": 1, "FAIL": 1, "N/A": 1})
        md = (out / "calibration-report.md").read_text(encoding="utf-8")
        for v in ("PASS", "FAIL", "N/A"):
            self.assertIn("| %s |" % v, md)
        self.assertIn("1 of 2 text nodes paired", md)
        self.assertEqual(fixtures.failures(res), ["f|c|e1|p"])

    def test_delivered_text_pairs_by_structural_path_and_never_gives_a_node_someone_elses_text(self):
        def n(name, type_="VisualElement", kids=(), **kw):
            return dict({"type": type_, "name": name, "children": list(kids), "attrs": {}}, **kw)
        tree = [n("root", kids=[n("title", "SIText"), n("row", kids=[n("text", "SIText"), n("text", "SIText")]), n("hidden", kids=[n("title", "SIText")], layout_rules=["switch-branch-not-shown"])])]
        live = [{"binder": ".../root/title", "text": "LOANS"}, {"binder": ".../root/row/text", "text": "first"}, {"binder": ".../root/row/text", "text": "second"}, {"binder": ".../other/x", "text": "stray"}]
        r = delivered.apply(tree, live)
        texts = [c["attrs"].get("text") for c in tree[0]["children"][1]["children"]]
        self.assertEqual((r["paired"], r["nodes"], r["unpaired_texts"], r["ambiguous_keys"]), (3, 3, 1, 1))     # the hidden branch's title is not drawn, so it is not a node
        self.assertEqual(texts, ["first", "second"])                        # same key twice: paired in order, one to one
        self.assertEqual(tree[0]["children"][0]["attrs"]["text"], "LOANS")
        self.assertNotIn("text", tree[0]["children"][2]["children"][0]["attrs"])     # the hidden title keeps nothing
        self.assertTrue(tree[0]["children"][0]["delivered"])

    def test_a_guid_named_template_segment_counts_as_a_template_container(self):
        g = "4bf029acf1920174cbde93c0376e0f68"
        self.assertEqual(delivered.key_of(["a", g, "b", "t:SIText"]), ("t:TemplateContainer", "b", "t:SIText"))
        self.assertEqual(delivered.key_of(["a", g + "|" + g, "t:SIText"], 2), ("t:TemplateContainer", "t:SIText"))


@unittest.skipUnless(AA.is_dir() and edge_path(), "needs the game install and Microsoft Edge")
class Calibration(unittest.TestCase):
    def test_every_fixture_runs_and_no_new_failure_appears(self):
        ctx = fixtures.Context()
        results = fixtures.run_all(ctx)
        out = Path(tempfile.mkdtemp())
        fixtures.report(results, out)
        known = set(json.loads(BASELINE.read_text(encoding="utf-8"))) if BASELINE.is_file() else set()
        now = set(fixtures.failures(results))
        self.assertEqual(sorted(now - known), [], "failures not in baseline-failures.json (new regressions): report in " + str(out))
        for r in results:
            self.assertGreater(r["counts"]["PASS"] + r["counts"]["FAIL"], 0, r["name"])           # a fixture that compares nothing is not a fixture


if __name__ == "__main__":
    unittest.main()
