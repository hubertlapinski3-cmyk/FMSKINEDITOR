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

    def test_literal_inventory_is_consistent(self):
        lit = self.d["literals"]
        rows, s = lit["rows"], lit["summary"]
        self.assertEqual(s["distinct_literals"], len(rows))
        self.assertEqual(s["with_at_least_one_use"] + s["only_in_token_definitions"], len(rows))
        self.assertEqual(s["total_uses"], sum(r["uses"] for r in rows))
        self.assertEqual(s["crimson_swapped"], sum(1 for r in rows if r["crimson_swapped"]))
        self.assertEqual(len({(r["rgb"], r["a"]) for r in rows}), len(rows), "one row per colour")
        for r in rows:
            self.assertLessEqual(r["selectors"] > 0, r["uses"] > 0, r["rgb"])            # a literal with no use has no selector
            self.assertLessEqual(r["rule_paths"], r["uses"])
            self.assertEqual(r["native_rules_copied_exact_alpha"], r["uses"])
            self.assertGreaterEqual(r["native_rules_copied_rgb_keep_alpha"], r["uses"], "the keep-alpha mode copies every alpha of the colour")
            self.assertLessEqual(sum(r["top_properties"].values()), r["uses"])
        self.assertEqual(rows, sorted(rows, key=lambda r: (-r["uses"], r["rgb"], r["a"])))

    def test_crimson_roles_cover_every_colour_override_once_and_say_where_each_came_from(self):
        cr = self.d["crimson_roles"]
        rows, s = cr["rows"], cr["summary"]
        self.assertEqual(s["colour_overrides"], len(rows))
        self.assertEqual(s["colour_overrides"], self.d["summary"]["crimson_overrides_that_are_colour_tokens"])
        self.assertEqual(len({r["token"] for r in rows}), len(rows))
        self.assertEqual(sum(s["by_role"].values()), len(rows))
        self.assertEqual(sum(s["by_ramp"].values()), len(rows))
        self.assertEqual(s["off_palette"], sum(1 for r in rows if r["palette_entry"] is None))
        self.assertEqual(s["role_unclassified"], sum(1 for r in rows if r["role"].startswith("other")))
        by_token = {t["token"]: t for t in self.rows}
        for r in rows:
            self.assertTrue(r["role_rule"], r["token"] + ": a role has the rule that gave it")
            self.assertTrue(by_token[r["token"]]["crimson_overrides"], r["token"] + " is flagged as a Crimson override in the token rows")

    def test_every_row_is_a_colour(self):
        for r in self.rows:
            self.assertRegex(r["rgb"], r"^#[0-9A-Fa-f]{6}$")
            self.assertTrue(0.0 <= r["a"] <= 1.0, r["token"])


if __name__ == "__main__":
    unittest.main()
