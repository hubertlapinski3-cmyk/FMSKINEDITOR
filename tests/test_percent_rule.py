"""The percentage main-axis rule (render/html.py), closed on two in-game sources: Loans table and Inbox Messages (docs/evidence/phase9-m3-session-D-20261114.md)."""
import unittest

from skin_editor.render.html import percent_main_axis_rule


def node(name, props=None, children=()):
    comp = {k: {"value": v} for k, v in (props or {}).items()}
    style = {k: v for k, v in (props or {}).items() if k in ("height", "flex-grow", "flex-basis")}
    return {"type": "VisualElement", "name": name, "computed": comp, "style": style, "children": list(children)}


class Rule(unittest.TestCase):
    def test_percent_height_under_a_flexed_parent_becomes_auto(self):
        # the Loans shape: a column with no declared height (it is flexed by its own parent), a content row and a table with height 100% and grow 1
        table = node("table", {"height": "100%", "flex-grow": "1"})
        row = node("row", {})
        frame = node("frame", {"flex-grow": "1"}, [row, table])
        root = node("root", {"height": "100%"}, [frame])
        changed = percent_main_axis_rule([root])
        self.assertEqual([n["name"] for n in changed], ["table"])
        self.assertNotIn("height", table["style"])
        self.assertEqual(table["layout_rules"], ["percent-main-axis-as-auto"])
        self.assertEqual(table["style"]["flex-grow"], "1")              # nothing else is touched

    def test_a_definite_parent_keeps_its_percentage(self):
        child = node("child", {"height": "50%"})
        parent = node("parent", {"height": "200px"}, [child])
        self.assertEqual(percent_main_axis_rule([parent]), [])
        self.assertEqual(child["style"]["height"], "50%")

    def test_a_chain_of_percentages_from_a_definite_top_stays_definite(self):
        leaf = node("leaf", {"height": "100%"})
        mid = node("mid", {"height": "100%"}, [leaf])
        top = node("top", {"height": "100%"}, [mid])
        self.assertEqual(percent_main_axis_rule([top]), [])

    def test_a_declared_flex_basis_wins_in_both_engines(self):
        child = node("child", {"height": "100%", "flex-basis": "0px", "flex-grow": "1"})
        frame = node("frame", {"flex-grow": "1"}, [child, node("sibling", {})])
        top = node("top", {}, [frame])
        self.assertEqual(percent_main_axis_rule([top]), [])
        self.assertEqual(child["style"]["height"], "100%")

    def test_a_row_parent_is_untouched_the_percentage_is_cross_axis(self):
        child = node("child", {"height": "100%"})
        row = node("row", {"flex-direction": "row"}, [child])
        top = node("top", {}, [row])
        self.assertEqual(percent_main_axis_rule([top]), [])

    def test_an_absolute_child_is_out_of_flow_and_keeps_its_percentage(self):
        border = node("border", {"height": "100%", "position": "absolute"})
        frame = node("frame", {"flex-grow": "1"}, [border, node("title", {})])
        top = node("top", {}, [frame])
        self.assertEqual(percent_main_axis_rule([top]), [])

    def test_it_only_fires_where_a_shrinkable_content_sized_sibling_makes_the_engines_differ(self):
        only = node("only", {"height": "100%", "flex-grow": "1"})
        frame = node("frame", {"flex-grow": "1"}, [only])
        self.assertEqual(percent_main_axis_rule([node("top", {}, [frame])]), [])           # no sibling: both engines give the same size
        fixed = node("fixed", {"flex-shrink": "0"})
        t2 = node("t2", {"height": "100%", "flex-grow": "1"})
        frame2 = node("frame2", {"flex-grow": "1"}, [fixed, t2])
        self.assertEqual(percent_main_axis_rule([node("top2", {}, [frame2])]), [])         # a non-shrinking sibling: same size again (the Transfers tabs)


if __name__ == "__main__":
    unittest.main()


