"""M8: the node cap and lazy expansion (skin_editor/render/cap.py), and the 13 layouts that exceeded the 200 ms budget."""
import copy
import time
import unittest
from pathlib import Path

from skin_editor import config
from skin_editor.render import cap
from skin_editor.render.html import flatten


def tree(depth, fan):
    def make(d):
        return {"type": "VisualElement", "name": "", "children": [make(d - 1) for _ in range(fan)] if d else []}
    return [make(depth), make(depth)]


def shape(top):
    return [[shape(c) for c in n["children"]] for n in top]


def paths(top, p=""):
    out = []
    for i, n in enumerate(top):
        q = ("%s/%d" % (p, i)) if p else str(i)
        out.append((q, n))
        out += paths(n["children"], q)
    return out


class Cap(unittest.TestCase):
    def test_small_tree_is_untouched(self):
        t = tree(2, 2)
        self.assertIsNone(cap.cap_tree(t, 100))
        self.assertEqual(cap.count(t), 14)

    def test_cut_is_breadth_first_and_children_are_all_or_none(self):
        t = tree(4, 3)                                     # 2 * (1+3+9+27+81) = 242 nodes
        info = cap.cap_tree(t, 60)
        self.assertEqual(info["total"], 242)
        self.assertLessEqual(info["shown"], 60)
        self.assertGreater(info["collapsed"], 0)
        for _p, n in paths(t):
            if n.get("collapsed"):
                self.assertEqual(n["children"], [])
                self.assertGreater(n["collapsed"]["children"], 0)
            else:
                self.assertIn(len(n["children"]), (0, 3))      # never a part of a node's children
        full = tree(4, 3)
        stub = next(p for p, n in paths(t) if n.get("collapsed"))
        self.assertEqual(len(dict(paths(full))[stub]["children"]), dict(paths(t))[stub]["collapsed"]["children"])     # the same path names the same node in both trees

    def test_open_expands_one_branch_and_moves_nothing_else(self):
        base = tree(4, 3)
        cap.cap_tree(base, 60)
        before = {p for p, _n in paths(base)}
        stub = next(p for p, n in paths(base) if n.get("collapsed"))
        again = tree(4, 3)
        info = cap.cap_tree(again, 60, [stub])
        after = {p for p, _n in paths(again)}
        self.assertTrue(before <= after, "opening a branch must not hide anything that was shown")
        self.assertEqual(len(after - before), 3)             # exactly the opened node's children, their own children stay collapsed
        self.assertEqual(info["opened"], 1)
        for p, n in paths(again):
            if p in after - before:
                self.assertTrue(n.get("collapsed") or not n["children"])

    def test_opening_a_stub_of_an_opened_branch_goes_one_more_level(self):
        t = tree(4, 3)
        cap.cap_tree(t, 60)
        s1 = min((p for p, n in paths(t) if n.get("collapsed")), key=lambda p: p.count("/"))      # the shallowest stub: its children still have children
        t2 = tree(4, 3)
        cap.cap_tree(t2, 60, [s1])
        s2 = next(p for p, n in paths(t2) if p.startswith(s1 + "/") and n.get("collapsed"))
        t3 = tree(4, 3)
        cap.cap_tree(t3, 60, [s1, s2])
        self.assertIn(s2 + "/0", dict(paths(t3)))

    def test_zero_cap_means_every_node(self):
        t = tree(4, 3)
        self.assertIsNone(cap.cap_tree(t, 0))
        self.assertEqual(cap.count(t), 242)


AA = Path(config.load()["aa_dir"]) if (config.load() or {}).get("aa_dir") else None
THIRTEEN = ["DetailedPreferencesBlock", "GameCreationLoadingScreen", "GameCreationManagerSelectionScreen", "IGEEditDetailsBlock", "ManagerPersonaDetailsScreen_EditMode", "NewsTransfersHubSiteHeader",
            "OnThePitchComparisonMainBlock", "PhoneDashboardHeaderNavigationTabs", "PlayerReportHeader", "ShotMapTile_4x4", "StaffTransferActivityBlock_12x8", "TeamShotMapTile_4x6",
            "data_display-graph-shotmap-default"]


@unittest.skipUnless(AA is not None and AA.is_dir(), "needs the game install")
class Budget(unittest.TestCase):
    """The 13 layouts the plan published as exceptions to the 200 ms cached budget: with the cap every one is inside it, and the 5,487-element one renders cold in seconds."""

    @classmethod
    def setUpClass(cls):
        from skin_editor.render import fixtures
        cls.ctx = fixtures.Context()
        row = cls.ctx.catalog["LoansTile_4x2"]
        cls.ctx.R.layout(row["bundle"], row["path_id"])                  # builds the cascade once (a session pays this once)

    def test_the_thirteen_are_inside_the_cached_budget(self):
        slow = []
        for nm in THIRTEEN:
            row = self.ctx.catalog[nm]
            self.ctx.R.layout(row["bundle"], row["path_id"], max_nodes=1000)            # first call: reads and parses the bundle
            t = time.perf_counter()
            res = self.ctx.R.layout(row["bundle"], row["path_id"], max_nodes=1000)
            ms = (time.perf_counter() - t) * 1000
            self.assertLessEqual(len(flatten(res["tree"])), 1000, nm)
            if ms > 200:
                slow.append((nm, round(ms)))
        self.assertEqual(slow, [], "layouts over the 200 ms cached budget")

    def test_the_largest_layout_is_capped_and_opens_lazily(self):
        row = self.ctx.catalog["DetailedPreferencesBlock"]
        t = time.perf_counter()
        res = self.ctx.R.layout(row["bundle"], row["path_id"], max_nodes=1000)
        self.assertLess(time.perf_counter() - t, 5.0)                               # "a few seconds" even cold
        tr = res["truncated"]
        self.assertGreater(tr["total"], 5000)
        self.assertLessEqual(tr["shown"], 1000)
        stub = next(p for p, n in paths(res["tree"]) if n.get("collapsed"))
        again = self.ctx.R.layout(row["bundle"], row["path_id"], max_nodes=1000, open=[stub])
        node = dict(paths(again["tree"]))[stub]
        self.assertFalse(node.get("collapsed"))
        self.assertGreater(len(node["children"]), 0)
        self.assertGreater(again["truncated"]["shown"], tr["shown"])
        self.assertEqual(self.ctx.R.layout(row["bundle"], row["path_id"])["truncated"], None)       # no cap asked: every node, as the fixtures use it

    def test_a_small_layout_is_not_truncated(self):
        row = self.ctx.catalog["LoansTile_4x2"]
        self.assertIsNone(self.ctx.R.layout(row["bundle"], row["path_id"], max_nodes=1000)["truncated"])


if __name__ == "__main__":
    unittest.main()
