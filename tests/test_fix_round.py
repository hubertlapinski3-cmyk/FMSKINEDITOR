"""Fix round after 1.0.0: pins on the published calibration report (needs the game install, Edge and the captures; skipped without them).

 - every FAIL row carries a cause grade or an explicit UNEXPLAINED, never nothing, and its id is unique;
 - the preface's counts are the JSON's counts (they are generated, not typed);
 - the coverage tables sum to the total number of rows, N/A rows all carry a reason, emitted plus skipped equals render nodes times properties, paired plus unpaired equals dump nodes;
 - a state row's as-read variants are published beside the conditional row, whatever their verdict."""
import importlib.util
import json
import re
import tempfile
import unittest
from pathlib import Path

from skin_editor.render import fixtures
from skin_editor.render.measure import edge_path

ROOT = Path(__file__).resolve().parent.parent
try:
    from skin_editor import config
    AA = Path(config.load()["aa_dir"]) if (config.load() or {}).get("aa_dir") else None
except Exception:
    AA = None


@unittest.skipUnless(AA is not None and AA.is_dir() and edge_path() and fixtures.ui_dumps_dir().is_dir(), "needs the game install, Microsoft Edge and the inspector captures")
class FixRound(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        spec = importlib.util.spec_from_file_location("publish_calibration", ROOT / "tools" / "publish_calibration.py")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        cls.out = Path(tempfile.mkdtemp())
        cls.results, cls.cv, cls.ex = mod.publish(cls.out)
        cls.doc = json.loads((cls.out / "calibration-report.json").read_text(encoding="utf-8"))
        cls.md = (cls.out / "calibration-report.md").read_text(encoding="utf-8")

    def rows(self):
        return [(r["name"], x) for r in self.results for x in r["rows"]]

    def test_every_fail_row_has_a_cause_grade_or_an_explicit_unexplained_and_a_unique_id(self):
        ids = [x["id"] for _n, x in self.rows()]
        self.assertEqual(len(ids), len(set(ids)), "row ids must be unique")
        for n, x in self.rows():
            if x["verdict"] != "FAIL":
                continue
            self.assertIsNotNone(x.get("exam"), "%s: a FAIL row without an examination" % x["id"])
            if x.get("cause_key"):
                self.assertIn(x.get("cause_grade"), ("measured fact", "magnitude only"), "%s: a cause without a grade" % x["id"])
            else:
                self.assertEqual(x["cause"], "UNEXPLAINED", x["id"])
                self.assertIsNone(x.get("cause_grade"))

    def test_unexplained_exists_and_is_used(self):
        self.assertGreater(self.ex["unexplained"], 0, "with no UNEXPLAINED rows the label is unreachable again")

    def test_the_preface_counts_are_the_json_counts(self):
        ex, t = self.doc["examination"], self.doc["totals"]
        m = re.search(r"Each of the (\d+) failing rows: (\d+) origin failures, (\d+) displaced by an origin listed beside them\. The causes are the ORIGIN rows: (\d+) rest on a measured capture fact, (\d+) on magnitude only, (\d+) are UNEXPLAINED", self.md)
        self.assertIsNotNone(m, "the preface sentence is missing")
        self.assertEqual(tuple(int(g) for g in m.groups()), (ex["fail_rows"], ex["origin_rows"], ex["displaced_rows"], ex["origin_grades"]["measured fact"], ex["origin_grades"]["magnitude only"], ex["origin_grades"]["unexplained"]))
        self.assertEqual(ex["fail_rows"], t["FAIL"])
        m = re.search(r"\*\*Totals: (\d+) pass, (\d+) fail, (\d+) n/a", self.md)
        self.assertEqual(tuple(int(g) for g in m.groups()), (t["PASS"], t["FAIL"], t["N/A"]))
        m = re.search(r"Of (\d+) slots, (\d+) were compared", self.md)
        cv = self.doc["totals"]["coverage"]
        self.assertEqual((int(m.group(1)), int(m.group(2))), (cv["total_rows"], cv["compared"]))
        self.assertEqual(cv["total_rows"], t["PASS"] + t["FAIL"] + t["N/A"])

    def test_the_coverage_tables_sum_to_the_total(self):
        cv = self.doc["totals"]["coverage"]
        self.assertEqual(sum(sum(c.values()) for c in cv["by_class"].values()), cv["total_rows"])
        self.assertEqual(sum(sum(sum(c.values()) for c in f.values()) for f in cv["by_fixture"].values()), cv["total_rows"])
        total_na = sum(1 for _n, x in self.rows() if x["verdict"] == "N/A")
        self.assertEqual(sum(cv["na_by_reason"].values()), total_na)
        self.assertNotIn("UNCODED", cv["na_by_reason"], "every N/A row carries a reason code")
        self.assertEqual(cv["na_by_reason"].get("no-declaration-live-non-default", 0), 0)
        self.assertEqual(cv["geometry"]["pass_stage_box"] + cv["geometry"]["pass_other"], cv["geometry"]["pass"])
        self.assertEqual(sum(cv["passes_declared_vs_default"].values()), sum(1 for _n, x in self.rows() if x["verdict"] == "PASS" and x.get("kind") == "values"))

    def test_emitted_plus_skipped_equals_nodes_times_properties_and_paired_plus_unpaired_equals_the_dump(self):
        cv = self.doc["totals"]["coverage"]
        self.assertTrue(cv["slots_check"])
        for e in cv["slots_check"]:
            self.assertTrue(e["sums"], e)
        for r in self.results:
            c = r["coverage"]
            if c["dump_nodes"]:
                self.assertEqual(c["dump_paired"] + c["dump_unpaired"], c["dump_nodes"], r["name"])

    def test_release_notes_numbers_are_read_from_the_report_json(self):
        spec = importlib.util.spec_from_file_location("make_release_notes", ROOT / "tools" / "make_release_notes.py")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        txt = mod.notes("9.9.9", self.out)
        t, cv, ex = self.doc["totals"], self.doc["totals"]["coverage"], self.doc["examination"]
        for needle in ("%d rows pass, %d fail and %d cannot be compared" % (t["PASS"], t["FAIL"], t["N/A"]), "Of %d slots, %d were compared" % (cv["total_rows"], cv["compared"]),
                       "Each of the %d failing rows" % ex["fail_rows"], "calibration-report-9.9.9.md"):
            self.assertIn(needle, txt)

    def test_layers_stand_alone_inferred_and_are_in_no_total_and_no_examination(self):
        lay = self.doc["layers"]
        self.assertEqual(set(lay), {"live-classes", "recorded-runtime-sheet"})
        base_ids = {b["id"] for _n, b in self.rows()}
        for k, v in lay.items():
            self.assertEqual(v["default"], "off")
            self.assertEqual(v["status"], "inferred")
            self.assertGreater(v["rows_compared"], v["base_rows"], "the layer was run over every paired row, not only the rows it is about")
            for x in v["rows"] + v["broken"]:
                self.assertEqual(x["layer"], k)
                self.assertEqual(x["status"], "inferred")
                base = next(b for _n, b in self.rows() if b["id"] == x["base_id"])
                self.assertEqual(base["verdict"], x["base_verdict"], "the base row is untouched by the layer")
        # no layer row is in the base rows, the totals or the examination
        for r in self.results:
            for x in r["layer_rows"]:
                self.assertTrue(x.get("layer"))
                self.assertNotIn(x["id"], base_ids)
            self.assertFalse([x for x in r["rows"] if x.get("layer")], "a layer row leaked into the base rows")
        t = self.doc["totals"]
        self.assertEqual(t["PASS"] + t["FAIL"] + t["N/A"], t["coverage"]["total_rows"])
        self.assertEqual(self.doc["examination"]["fail_rows"], t["FAIL"])
        self.assertEqual(sum(r["counts"]["PASS"] + r["counts"]["FAIL"] + r["counts"]["N/A"] for r in self.results), t["coverage"]["total_rows"])

    def test_each_state_reading_is_counted_once_on_its_real_chain_and_the_variants_are_outside_the_totals(self):
        st = next(r for r in self.results if r["name"] == "state-i3-session-g")
        base = {x["check"] for x in st["rows"]}
        var = {x["check"] for x in st["variant_rows"]}
        lay = {x["check"] for x in st["layer_rows"]}
        self.assertFalse(base & var, "a row is a base row or a variant, never both")
        for c in ("nav-tab-label-hover@V1-real-ancestry-only", "nav-tab-label-hover@V2-label-state-only", "nav-tab-label-hover", "nav-tab-label-as-read"):
            self.assertIn(c, var)
        self.assertIn("nav-tab-label-hover@real-chain", base)
        self.assertIn("nav-tab-label-hover@V4-base-plus-recorded-runtime-sheet", lay)
        self.assertIn("loans-tile-hover@runtime-sheet-layer", lay)
        pub = [x for x in st["variant_rows"] if x["check"] == "nav-tab-label-hover" and "(rest)" not in x["property"]]
        self.assertEqual(pub[0]["verdict"], "PASS", "the published row keeps its verdict")
        self.assertTrue(pub[0].get("chain_truncated"))
        # one reading, one scored pair: every base real-chain check replaces exactly one published check
        replaced = [x["scored_instead_of"] for x in st["rows"] if x.get("scored_instead_of") and "(rest)" in x["property"]]
        self.assertEqual(len(replaced), len(set(replaced)))
        # the real chain is the comparison: the Loans rest colour fails, the pitch marker and instruction tile rest rows are N/A
        by = {(x["check"], x["property"].split(" ")[0] + (" (rest)" if "(rest)" in x["property"] else "")): x["verdict"] for x in st["rows"]}
        self.assertEqual(by[("loans-tile-hover@real-ancestry", "background-color (rest)")], "FAIL")
        self.assertEqual(by[("pitch-marker-hover@real-ancestry", "background-color (rest)")], "N/A")
        self.assertEqual(by[("instruction-tile-hover@real-ancestry", "background-color (rest)")], "N/A")

    def test_a_hidden_live_element_the_render_draws_is_a_failure_named_visibility(self):
        vis = [(r["name"], x) for r in self.results for x in r["rows"] if x["property"] == "visibility"]
        self.assertGreaterEqual(len(vis), 3)
        for _n, x in vis:
            self.assertEqual(x["verdict"], "FAIL")
            self.assertGreater(x["got"][2], 0.5)
            self.assertGreater(x["got"][3], 0.5)
        self.assertEqual(self.doc["pairing_effect"]["visibility_fail_rows"], len(vis))

    def test_the_release_notes_pairing_sentence_is_the_json_s_pairing_table(self):
        spec = importlib.util.spec_from_file_location("make_release_notes", ROOT / "tools" / "make_release_notes.py")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        txt = mod.notes("9.9.9", self.out)
        pd = self.doc["pairing"]
        self.assertIn("matched %d render nodes to live elements the game hides" % sum(x["greedy_invisible_partners"] for x in pd), txt)
        self.assertIn("%d partners changed" % sum(x["changed_partner"] for x in pd), txt)
        self.assertNotIn("which element each one is compared with", txt)
        self.assertNotIn("### New\n- **Optional layers", txt)


if __name__ == "__main__":
    unittest.main()