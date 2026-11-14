"""M3 screen assembly: the grid and placement model, checked on the measured areas of 2026-11-14 and on a synthetic composition."""
import unittest

from skin_editor.render import pitch, screen

P = pitch.lookup("SquadComposition-Large")


def cell(eid, x, y, w, h, min_w=0, max_w=0, min_h=0, max_h=0, comp="C"):
    return {"composition": comp, "element_id": eid, "x": x, "y": y, "w": w, "h": h, "min_w": min_w or w, "max_w": max_w or w, "min_h": min_h or h, "max_h": max_h or h}


class Grid(unittest.TestCase):
    def test_measured_grid_areas_give_the_columns_and_rows_the_hosts_use(self):
        self.assertEqual(screen.grid_dims(2468.8, 1319.3, P), (30, 16))                  # Squad overview, panel 2500
        self.assertEqual(screen.grid_dims(2057.3, 1074.4, P), (25, 13))                  # same screen, Information Display Medium
        self.assertEqual(screen.grid_dims(2361.3, 1213.9, P, padding=0), (29, 15))       # Team Instructions tab grid (no padding)

    def test_host_px_follow_the_stride_of_82_and_the_16_gap(self):
        self.assertEqual(screen.cell_px(26, 0, 4, 4), {"left": 2144, "top": 12, "width": 312, "height": 312})        # Tactics, inline values read from the game
        self.assertEqual(screen.cell_px(26, 8, 4, 2), {"left": 2144, "top": 668, "width": 312, "height": 148})       # Atmosphere
        self.assertEqual(screen.cell_px(0, 0, 6, 15, padding=0), {"left": 0, "top": 0, "width": 476, "height": 1214})  # Team Instructions pitch


class Placement(unittest.TestCase):
    def setUp(self):
        # a design of 20 x 10: a flexible banner on top, a flexible body, three fixed tiles on the right edge
        cells = [cell("banner", 0, 0, 16, 1, max_w=100, max_h=100), cell("body", 0, 1, 16, 9, min_w=12, max_w=100, min_h=8, max_h=100),
                 cell("t1", 16, 0, 4, 4), cell("t2", 16, 4, 4, 4), cell("t3", 16, 8, 4, 2)]
        a = screen.Assembler({"layouts": [], "cells": cells, "tiles": []})
        self.a, self.cells = a, cells

    def test_a_bigger_grid_moves_right_edge_cells_and_stretches_flexible_ones(self):
        g = self.a.place("C", 30, 16)
        self.assertEqual((g["t1"]["col"], g["t1"]["row"], g["t1"]["w"], g["t1"]["h"]), (26, 0, 4, 4))     # fixed: moves right, keeps its rows and size
        self.assertEqual((g["t3"]["col"], g["t3"]["row"]), (26, 8))
        self.assertEqual((g["banner"]["w"], g["banner"]["h"]), (26, 1))                                    # flexible width; a 1-row cell does not stretch
        self.assertEqual((g["body"]["w"], g["body"]["h"]), (26, 15))                                       # flexible both ways: + 10 columns, + 6 rows

    def test_the_design_size_grid_changes_nothing(self):
        g = self.a.place("C", 20, 10)
        self.assertEqual((g["t1"]["col"], g["body"]["w"], g["body"]["h"]), (16, 16, 9))

    def test_reserved_columns_are_held_back_for_slots_the_composition_lacks(self):
        g = self.a.place("C", 24, 10, reserved_right=4)
        self.assertEqual((g["t1"]["col"], g["body"]["w"]), (16, 16))

    def test_an_unmeasured_composition_carries_the_estimate_flag_through_assembly(self):
        res = self.a.assemble("C", (2468.8, 1319.3), composition_pitch="TacticalPlannerTeamInstructionsTabComposition-Standard")
        self.assertFalse(res["pitch"]["measured"])
        self.assertTrue(any("ESTIMATE" in f for f in res["flags"]))


if __name__ == "__main__":
    unittest.main()
