"""Nested function values decode as the game wrote them (found by the Phase 9 render: 30 nested var() fallbacks in 8 Training layouts)."""
import unittest

from skin_editor import uss

T_FLOAT, T_DIM, T_ENUM, T_FUNC, T_COMMA = 2, 3, 7, 10, 11


def h(t, i):
    return {"m_ValueType": t, "valueIndex": i}


TREE = {"floats": [3, 1, 2], "strings": ["--a", "--b", "--c"], "dimensions": [{"value": 1, "unit": 1}], "colors": []}


class Nested(unittest.TestCase):
    def test_a_simple_var_is_unchanged(self):
        hs = [h(T_FUNC, 1), h(T_FLOAT, 1), h(T_ENUM, 0)]                      # var(--b): floats[1] = 1 argument
        self.assertEqual(uss.value_text(TREE, hs)[0], "var(--a)")

    def test_a_var_with_a_literal_fallback_is_unchanged(self):
        hs = [h(T_FUNC, 1), h(T_FLOAT, 0), h(T_ENUM, 0), h(T_COMMA, 0), h(T_DIM, 0)]          # var(--a, 1px): 3 items
        self.assertEqual(uss.value_text(TREE, hs)[0], "var(--a, 1px)")

    def test_a_nested_var_fallback_keeps_its_arguments_inside(self):
        # var(--a, var(--b)): outer has 3 items (name, comma, the whole inner function); the inner function has 1
        hs = [h(T_FUNC, 1), h(T_FLOAT, 0), h(T_ENUM, 0), h(T_COMMA, 0), h(T_FUNC, 1), h(T_FLOAT, 1), h(T_ENUM, 1)]
        self.assertEqual(uss.value_text(TREE, hs)[0], "var(--a, var(--b))")

    def test_values_after_a_nested_function_stay_after_it(self):
        hs = [h(T_FUNC, 1), h(T_FLOAT, 0), h(T_ENUM, 0), h(T_COMMA, 0), h(T_FUNC, 1), h(T_FLOAT, 1), h(T_ENUM, 1), h(T_DIM, 0), h(T_ENUM, 2)]
        self.assertEqual(uss.value_text(TREE, hs)[0], "var(--a, var(--b)) 1px --c")

    def test_two_levels_of_nesting(self):
        # var(--a, var(--b, var(--c))): the middle function has 3 items, the innermost 1
        tree = dict(TREE, floats=[3, 1, 3])
        hs = [h(T_FUNC, 1), h(T_FLOAT, 0), h(T_ENUM, 0), h(T_COMMA, 0),
              h(T_FUNC, 1), h(T_FLOAT, 2), h(T_ENUM, 1), h(T_COMMA, 0), h(T_FUNC, 1), h(T_FLOAT, 1), h(T_ENUM, 2)]
        self.assertEqual(uss.value_text(tree, hs)[0], "var(--a, var(--b, var(--c)))")


@unittest.skipUnless(__import__("pathlib").Path(r"C:\Program Files (x86)\Steam\steamapps\common\Football Manager 27\fm_Data\StreamingAssets\aa").is_dir(), "needs the game install")
class RealData(unittest.TestCase):
    def test_the_training_rule_that_exposed_it_now_decodes_as_one_var(self):
        from skin_editor import config, index_styles
        ws = config.workspace(config.load())
        ix = index_styles.load(ws) or index_styles.build(ws)             # the cache is rebuilt when its schema changed
        texts = [v for s in ix.sheets for r in s["rules"] for _n, v, _c in r["p"] if "calendar-training-border-soft-colour" in v]
        self.assertTrue(texts)
        for t in texts:
            self.assertNotIn("var()", t)                                   # the broken form is gone


if __name__ == "__main__":
    unittest.main()
