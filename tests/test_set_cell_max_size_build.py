"""SC2: the SetCellMaxSize build path (candidate: it builds only with a recorded test-only override). Archived stock set C only; scratch folders."""
import tempfile
import unittest
from pathlib import Path

from skin_editor import build5g, playops, tiles
from tests.test_build5g import Fixture, SETC, _build

PROFILE = "PlayerReportOverviewComposition-Large"
BUNDLE = "ui-tileslayouts_assets_all.bundle"
OVERRIDE = {"overrides": ["SetCellMaxSize"], "allow_candidates": ["SetCellMaxSize"]}


def max_op(w=6, h=4, cell="FItness"):
    f = Fixture.get()
    return playops.cell_max_size_operation(f["dump"], PROFILE, cell, w, h)


def leaf_diffs(built_dir):
    f = Fixture.get()
    pid = int(f["comps"][PROFILE]["path_id"])
    import UnityPy
    pick = lambda p: next(o for o in UnityPy.load(str(p)).objects if o.path_id == pid).read_typetree()   # noqa: E731
    return tiles._leaf_diffs(pick(SETC / BUNDLE), pick(Path(built_dir) / BUNDLE))


@unittest.skipUnless((SETC / BUNDLE).is_file(), "needs archived stock set C")
class MaxSizeBuild(unittest.TestCase):
    def test_the_max_only_build_passes_with_the_override_and_changes_one_leaf(self):
        repo = _build(Fixture.session(max_op()), test_only=OVERRIDE)
        self.assertTrue(repo["cell_check"]["ok"], repo["cell_check"].get("differences"))
        self.assertEqual(repo["test_only"], OVERRIDE)                                  # the override is recorded in the report
        changes = next(iter(repo["cell_check"]["by_bundle"][BUNDLE]["built_cell_changes"].values()))
        self.assertEqual([m["element_id"] for m in changes["changed_m_maxSize"]], ["FItness"])
        self.assertEqual(changes["changed_m_location"], [])
        idx = Fixture.cell(PROFILE, max_op()["target"]["cell"]["cell_index"])["cell_index"]
        self.assertEqual(leaf_diffs(repo["outputs"]["built_dir"]), ["/m_gridComponents[%d]/m_maxSize/x" % idx])   # 4x4 -> 6x4: one leaf

    def test_it_is_refused_without_the_override(self):
        repo = _build(Fixture.session(max_op()))
        self.assertEqual(repo["blocked"], ["SetCellMaxSize has no build path yet"])
        self.assertEqual(repo["outputs"]["bundles"], {})

    def test_a_second_build_is_byte_identical(self):
        a = _build(Fixture.session(max_op()), test_only=OVERRIDE)
        b = _build(Fixture.session(max_op()), test_only=OVERRIDE)
        self.assertEqual(a["outputs"]["bundles"], b["outputs"]["bundles"])
        self.assertEqual((Path(a["outputs"]["built_dir"]) / BUNDLE).read_bytes(), (Path(b["outputs"]["built_dir"]) / BUNDLE).read_bytes())

    def test_an_injected_extra_leaf_change_fails_and_is_named(self):
        f = Fixture.get()
        other = next(c for c in f["dump"]["cells"] if c["composition"] == PROFILE and c["element_id"] != "FItness")
        repo = _build(Fixture.session(max_op()), test_only=OVERRIDE,
                      extra_change={"bundle": BUNDLE, "path_id": f["comps"][PROFILE]["path_id"], "composition": PROFILE,
                                    "cell_index": other["cell_index"], "cell_id": other["element_id"],
                                    "from": {"x": other["x"], "y": other["y"]}, "to": {"x": other["x"] + 1, "y": other["y"]}})
        self.assertFalse(repo["cell_check"]["ok"])
        self.assertTrue(any(other["element_id"] in d for d in repo["cell_check"]["differences"]), repo["cell_check"]["differences"])
        self.assertTrue(repo.get("blocked"))

    def test_a_missing_change_fails_and_names_the_difference(self):
        op = max_op(4, 4)                                                              # the stock max: the build changes nothing
        repo = _build(Fixture.session(op), test_only=OVERRIDE)
        self.assertFalse(repo["cell_check"]["ok"])
        self.assertTrue(any("m_maxSize is unchanged" in d for d in repo["cell_check"]["differences"]), repo["cell_check"]["differences"])

    def test_the_writer_refuses_a_max_made_against_another_value(self):
        f = Fixture.get()
        op = max_op()
        op["original"]["value"] = {"x": 5, "y": 4}                                     # the edit was made against a different stock max
        with self.assertRaises(ValueError):
            _build(Fixture.session(op), test_only=OVERRIDE)


if __name__ == "__main__":
    unittest.main()
