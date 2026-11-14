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

    def test_the_as_read_variants_sit_beside_the_conditional_row(self):
        st = next(r for r in self.results if r["name"] == "state-i3-session-g")
        checks = {x["check"] for x in st["rows"]}
        self.assertTrue({"nav-tab-label-hover", "nav-tab-label-as-read", "nav-tab-label-as-read-runtime-sheet"} <= checks)
        cond = [x for x in st["rows"] if x["check"] == "nav-tab-label-hover" and x.get("conditional") and "(rest)" not in x["property"]]
        self.assertEqual(len(cond), 1)
        self.assertEqual(cond[0]["verdict"], "PASS", "the existing row and its verdict are untouched")
        for x in st["rows"]:
            if x["check"].startswith("nav-tab-label-as-read"):
                self.assertEqual(x.get("variant_of"), "nav-tab-label-hover")


if __name__ == "__main__":
    unittest.main()