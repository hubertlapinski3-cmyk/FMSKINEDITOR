"""SC1: the SetCellMaxSize operation (candidate, preview only): its refusals, session undo and redo, the J4 profile preview and the build refusal."""
import json
import unittest
from pathlib import Path

from skin_editor import build5g, playops
from skin_editor.render import preview

DUMP = Path(r"__absent_fixture_path__")
PROFILE = "PlayerReportOverviewComposition-Large"


def mini_dump(configs=((2, 2),)):
    return {"compositions": [{"name": "C", "bundle": "ui-tileslayouts_assets_all.bundle", "path_id": 1234}],
            "cells": [{"composition": "C", "cell_index": 2, "element_id": "FItness", "x": 2, "y": 6, "w": 2, "h": 2, "max_w": 4, "max_h": 4}],
            "cell_configs": [{"composition": "C", "cell_index": 2, "cfg_index": i, "size_w": w, "size_h": h} for i, (w, h) in enumerate(configs)],
            "tiles": []}


def make(max_w, max_h, dump=None, comp="C", cell="FItness"):
    return playops.cell_max_size_operation(dump or mini_dump(), comp, cell, max_w, max_h)


class Refusals(unittest.TestCase):
    def refused(self, *a, **kw):
        with self.assertRaises(playops.OperationError) as cm:
            make(*a, **kw)
        return str(cm.exception)

    def test_an_unknown_composition_or_cell(self):
        self.assertIn("unknown composition", self.refused(6, 4, comp="Nope"))
        self.assertIn("no cell with element id", self.refused(6, 4, cell="Nope"))

    def test_a_max_smaller_than_the_design_size(self):
        self.assertIn("design size 2x2", self.refused(1, 4))
        self.assertIn("design size 2x2", self.refused(4, 1))
        self.assertEqual(make(2, 2)["validation"]["ok"], True)                     # equal to the design size is allowed

    def test_a_max_smaller_than_any_listed_configuration_size(self):
        d = mini_dump(configs=((2, 2), (4, 3)))
        self.assertIn("configuration size the cell lists, 4x3", self.refused(4, 2, dump=d))
        self.assertIn("configuration size the cell lists, 4x3", self.refused(3, 4, dump=d))
        self.assertEqual(make(4, 3, dump=d)["validation"]["ok"], True)

    def test_a_width_or_height_above_100(self):
        self.assertIn("at most 100", self.refused(101, 4))
        self.assertIn("at most 100", self.refused(4, 101))
        self.assertEqual(make(100, 100)["validation"]["ok"], True)

    def test_a_malformed_max(self):
        for w, h in ((0, 4), (4, -1)):
            self.assertIn("positive", self.refused(w, h))
        op = make(6, 4)
        op["target"]["cell"]["max_size"] = {"x": 6.5, "y": 4}
        with self.assertRaises(playops.OperationError):
            playops.validate(op)

    def test_the_operation_is_a_candidate(self):
        v = make(6, 4)["validation"]
        self.assertEqual(v["safety"], "candidate")
        self.assertTrue(v["translation"]["candidate"])
        self.assertIsNone(v["translation"]["writer"])


class Session(unittest.TestCase):
    def test_record_undo_and_redo(self):
        s = playops.new_session("proj", "PlayerReport")
        op = make(6, 4)
        playops.add(s, op)
        self.assertEqual([o["id"] for o in playops.effective(s)], [op["id"]])
        playops.undo(s)
        self.assertEqual(playops.effective(s), [])
        self.assertEqual(len(s["operations"]), 1)                                  # the record is kept
        playops.redo(s, op["id"])
        self.assertEqual([o["id"] for o in playops.effective(s)], [op["id"]])

    def test_a_newer_max_for_the_same_cell_supersedes_the_older(self):
        s = playops.new_session("proj", "PlayerReport")
        a, b = make(5, 4), make(6, 4)
        playops.add(s, a)
        playops.add(s, b)
        self.assertEqual([o["id"] for o in playops.effective(s)], [b["id"]])
        self.assertEqual(a["state"], "superseded")

    def test_the_projection_carries_it_as_a_max_size_fragment_not_a_placement(self):
        s = playops.new_session("proj", "PlayerReport")
        playops.add(s, make(6, 4))
        from skin_editor import project as project_mod
        frags = playops.project_onto(project_mod.new("p", "27.1.0"), s)
        self.assertEqual(frags["placements"], [])
        self.assertEqual(frags["cell_max_sizes"], [{"composition": "C", "cell_index": 2, "cell_element_id": "FItness",
                                                    "max_size": {"x": 6, "y": 4}, "candidate": "set-cell-max-size"}])


class BuildRefusal(unittest.TestCase):
    def test_the_route_and_the_review_refuse_it_with_the_plain_reason(self):
        op = make(6, 4)
        self.assertEqual(playops.route_of(op)["route"], "blocked")
        self.assertEqual(playops.route_of(op)["reason"], "SetCellMaxSize has no build path yet")
        for pref in ("skin_folder", "bundle"):
            self.assertEqual(build5g._route(op, route_preference=pref), ("refused", "SetCellMaxSize has no build path yet"))
        s = playops.new_session("proj", "PlayerReport")
        playops.add(s, op)
        plan = build5g.plan(s, dump=mini_dump())
        self.assertEqual([(r["kind"], r["reason"]) for r in plan["refusals"]], [("SetCellMaxSize", "SetCellMaxSize has no build path yet")])
        self.assertTrue(plan["operations"][0]["refused"])


@unittest.skipUnless(DUMP.is_file(), "needs the archived set-C layout dump")
class ProfilePreview(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dump = json.loads(DUMP.read_text(encoding="utf-8-sig"))

    def bottom_band(self, out):
        return {h["cell_element_id"]: h for h in out["hosts"] if h["cell_element_id"] != "PlayerAttributesBlock"}

    def test_fitness_max_6x4_in_the_profile_overview(self):
        mx = [{"composition": PROFILE, "cell_element_id": "FItness", "max_size": {"x": 6, "y": 4}}]
        band = self.bottom_band(preview.profile_hosts(self.dump, max_sizes=mx))
        order = ["Happiness", "FItness", "PlayerForm", "PlayerTrainingOverview", "PlayerSeasonStats", "CareerStats"]
        self.assertEqual([band[e]["col"] for e in order], [0, 4, 10, 14, 18, 26])
        self.assertEqual(band["FItness"]["rect"][2], 82 * 6 - 16)                   # FItness is 6 columns wide
        self.assertEqual(preview.profile_hosts(self.dump, max_sizes=mx)["max_size_label"], "candidate, preview only")

    def test_without_the_operation_the_stock_columns_are_unchanged(self):
        band = self.bottom_band(preview.profile_hosts(self.dump))
        order = ["Happiness", "FItness", "PlayerForm", "PlayerTrainingOverview", "PlayerSeasonStats", "CareerStats"]
        self.assertEqual([band[e]["col"] for e in order], [0, 4, 8, 12, 16, 24])     # the measured H2/I2 columns
        self.assertIsNone(preview.profile_hosts(self.dump)["max_size_label"])

    def test_every_composition_applies_it_and_the_dump_is_not_mutated(self):
        from skin_editor.render import screen
        a = screen.Assembler(self.dump)
        mx = [{"composition": "SquadComposition-Large", "cell_element_id": "Tactics", "max_size": {"x": 8, "y": 4}}]
        self.assertEqual(preview.apply_max_sizes(a, "SquadComposition-Large", mx), ["Tactics"])      # CL3: the rule is wired for all compositions
        self.assertEqual(next(c for c in a.cells["SquadComposition-Large"] if c["element_id"] == "Tactics")["max_w"], 8)
        self.assertEqual(next(c for c in self.dump["cells"] if c["composition"] == "SquadComposition-Large" and c["element_id"] == "Tactics")["max_w"], 4)
        a2 = screen.Assembler(self.dump)
        self.assertEqual(preview.apply_max_sizes(a2, PROFILE, [{"composition": PROFILE, "cell_element_id": "FItness", "max_size": {"x": 6, "y": 4}}]), ["FItness"])
        stock = next(c for c in self.dump["cells"] if c["composition"] == PROFILE and c["element_id"] == "FItness")
        self.assertEqual((stock["max_w"], stock["max_h"]), (4, 4))                          # the dump itself is not mutated


if __name__ == "__main__":
    unittest.main()
