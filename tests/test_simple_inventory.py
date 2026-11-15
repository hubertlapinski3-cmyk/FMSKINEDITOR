"""S0 of the Simple mode plan: the generated token inventory (data/simple/token-inventory.json) is internally consistent. Needs no game."""
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
INV = ROOT / "data" / "simple" / "token-inventory.json"


class Inventory(unittest.TestCase):
    def setUp(self):
        self.d = json.loads(INV.read_text(encoding="utf-8"))
        self.rows = self.d["tokens"]
        self.s = self.d["summary"]

    def test_summary_is_the_rows_counted(self):
        self.assertEqual(self.s["colour_tokens"], len(self.rows))
        self.assertEqual(self.s["colour_tokens_used_by_a_rule"] + self.s["colour_tokens_unused"], len(self.rows))
        self.assertEqual(self.s["colour_tokens_unused"], sum(1 for r in self.rows if r["rules"] == 0))
        self.assertEqual(self.s["crimson_overrides_that_are_colour_tokens"] + self.s["colour_tokens_not_overridden_by_crimson"], len(self.rows))
        self.assertEqual(self.s["rules_reached_by_all_colour_tokens"], sum(r["rules"] for r in self.rows))
        self.assertLessEqual(self.s["crimson_overrides_that_are_colour_tokens"], self.s["crimson_overrides_total"])
        self.assertLessEqual(self.s["colour_tokens"], self.s["tokens_all"])

    def test_families_add_up_and_rows_are_unique_and_sorted(self):
        f = self.d["families"]
        self.assertEqual(sum(x["tokens"] for x in f.values()), len(self.rows))
        self.assertEqual(sum(x["rules"] for x in f.values()), self.s["rules_reached_by_all_colour_tokens"])
        self.assertEqual(len(f), self.s["families"])
        names = [r["token"] for r in self.rows]
        self.assertEqual(names, sorted(set(names)))

    def test_every_row_is_a_colour(self):
        for r in self.rows:
            self.assertRegex(r["rgb"], r"^#[0-9A-Fa-f]{6}$")
            self.assertTrue(0.0 <= r["a"] <= 1.0, r["token"])


if __name__ == "__main__":
    unittest.main()
