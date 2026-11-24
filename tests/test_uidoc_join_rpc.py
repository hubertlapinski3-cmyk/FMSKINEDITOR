"""The uidoc.join engine RPC (the finding-5 join, step 3): one read-only RPC answers with the per-instance join
rows of a composition - a top layout of the composition is addressable by UiDocument identity, an included layout
is not, and the counts separate joined / not drawn / unmatched.

Data-gated: it needs the configured game and an imported layout dump in the workspace. The engine is built with a
temporary FM27SE_WORKSPACE (nothing writes the live workspace) and then pointed at the real workspace read-only;
no config-writing RPC is ever called on it."""
import os
import tempfile
import unittest
from pathlib import Path

COMPOSITION = "SquadComposition-Standard"


def _real_config():
    saved = os.environ.pop("FM27SE_WORKSPACE", None)
    try:
        from skin_editor import config
        return config.load()
    finally:
        if saved is not None:
            os.environ["FM27SE_WORKSPACE"] = saved


def _real_ws():
    from skin_editor import config
    return config.workspace(_real_config())


@unittest.skipUnless(_real_config().get("game_dir") and Path(str(_real_config()["game_dir"])).is_dir()
                     and (_real_ws().layout / "current.json").is_file(),
                     "needs the configured game and an imported layout dump")
class UidocJoinRpc(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from skin_editor import config, detect
        cls.tmp = tempfile.TemporaryDirectory(prefix="fm27se-joinrpc-", ignore_cleanup_errors=True)
        real_cfg = _real_config()
        os.environ["FM27SE_WORKSPACE"] = cls.tmp.name
        try:
            from skin_editor.engine import Engine
            cls.eng = Engine()
        finally:
            os.environ.pop("FM27SE_WORKSPACE", None)
        cls.eng.ws = config.workspace(real_cfg)             # read-only use of the real workspace from here on
        cls.eng.info = detect.describe(real_cfg["game_dir"])

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_the_join_answers_for_the_squad_composition(self):
        out = self.eng.uidoc_join({}, {"composition": COMPOSITION})
        self.assertEqual(out["composition"], COMPOSITION)
        counts = out["counts"]
        self.assertEqual(counts["unmatched_doc"], [])
        self.assertEqual(counts["unmatched_render"], [])
        self.assertGreater(counts["joined"], 0)
        self.assertGreater(counts["not_drawn"].get("root", 0), 0)
        self.assertGreater(counts["not_drawn"].get("non_visual", 0), 0)
        self.assertGreaterEqual(len(out["instances"]), 6)           # the panel + one per cell
        for inst in out["instances"]:
            for row in inst["rows"].values():
                self.assertEqual(row["state"], "joined")
                self.assertTrue(row["logical_id"])
                self.assertTrue(row["m_id"])

    def test_a_top_layout_is_joinable_and_an_included_layout_is_not(self):
        from skin_editor import layout_dump
        d = layout_dump.load(self.eng.ws)
        tiles = [t for t in d["tiles"] if t["composition"] == COMPOSITION]
        self.assertTrue(tiles)
        lay = {l["id"]: l for l in d["layouts"]}
        tile = next(l for l in lay.values() if l["id"] == tiles[0]["tile_layout_id"])
        cat = [r for r in self.eng._renderer().layouts.catalog() if r["name"] == tile["name"]]
        self.assertTrue(cat, tile["name"])
        out = self.eng.uidoc_join({}, {"bundle": cat[0]["bundle"], "path_id": cat[0]["path_id"]})
        self.assertTrue(out.get("joinable"), out.get("reason"))
        self.assertTrue(out["instances"])
        # an included layout keeps render-path addressing, and the response says so
        closure = self.eng._uidoc_closure(d, COMPOSITION)
        starts = {t["panel_layout_id"] for t in tiles} | {t["tile_layout_id"] for t in tiles}
        included_ids = sorted(closure - starts)
        self.assertTrue(included_ids, "the composition reaches layouts only through its top layouts")
        target = next(l for l in lay.values() if l["id"] == included_ids[0])
        cat2 = [r for r in self.eng._renderer().layouts.catalog() if r["name"] == target["name"]]
        self.assertTrue(cat2, target["name"])
        out2 = self.eng.uidoc_join({}, {"composition": COMPOSITION, "bundle": cat2[0]["bundle"], "path_id": cat2[0]["path_id"]})
        self.assertFalse(out2.get("joinable"), out2)
        self.assertTrue(out2.get("reason"))

    def test_an_unknown_composition_is_refused_by_name(self):
        from skin_editor.engine import Engine
        with self.assertRaises(KeyError) as c:
            self.eng.uidoc_join({}, {"composition": "NoSuchComposition"})
        self.assertIn("no such composition", str(c.exception))


if __name__ == "__main__":
    unittest.main()
