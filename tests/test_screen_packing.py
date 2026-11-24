"""The runtime placement rule measured by Tests C and D: cells are packed vertically per column.

Test D alone (stock 2-row Atmosphere): the cell serialized at y=12 lands at row 10.
Test C+D (4-row Atmosphere): the same cell lands at row 12. No clamping, no overlap.
"""
import unittest

from skin_editor.render import screen


def cell(eid, x, y, w, h, idx):
    return {"element_id": eid, "x": x, "y": y, "w": w, "h": h, "cell_index": idx}


class PackRows(unittest.TestCase):
    def test_test_d_alone_packs_under_the_stock_two_row_atmosphere(self):
        items = [cell("Tactics", 16, 0, 4, 4, 1), cell("Training", 16, 4, 4, 4, 2),
                 cell("Atmosphere", 16, 8, 4, 2, 0), cell("Happiness", 16, 12, 4, 4, 5)]
        got = {c["element_id"]: c["y"] for c in screen.pack_rows(items)}
        self.assertEqual(got, {"Tactics": 0, "Training": 4, "Atmosphere": 8, "Happiness": 10})

    def test_test_c_plus_d_packs_happiness_at_row_twelve(self):
        items = [cell("Tactics", 16, 0, 4, 4, 1), cell("Training", 16, 4, 4, 4, 2),
                 cell("Atmosphere", 16, 8, 4, 4, 0), cell("Happiness", 16, 12, 4, 4, 5)]
        got = {c["element_id"]: c["y"] for c in screen.pack_rows(items)}
        self.assertEqual(got, {"Tactics": 0, "Training": 4, "Atmosphere": 8, "Happiness": 12})

    def test_stock_columns_are_unchanged_by_packing(self):
        items = [cell("HumanActions", 0, 0, 16, 1, 3), cell("FirstTeamOverview", 0, 1, 16, 9, 4),
                 cell("Tactics", 16, 0, 4, 4, 1), cell("Training", 16, 4, 4, 4, 2),
                 cell("Atmosphere", 16, 8, 4, 2, 0)]
        got = {c["element_id"]: c["y"] for c in screen.pack_rows(items)}
        self.assertEqual(got, {"HumanActions": 0, "FirstTeamOverview": 1, "Tactics": 0,
                               "Training": 4, "Atmosphere": 8})

    def test_the_input_is_not_modified(self):
        items = [cell("A", 16, 0, 4, 2, 0), cell("B", 16, 6, 4, 4, 1)]
        screen.pack_rows(items)
        self.assertEqual([c["y"] for c in items], [0, 6])


class PlaceWithSessionCells(unittest.TestCase):
    """The Assembler path the preview and the screen canvas use: a C resize and a D add."""

    def dump(self):
        cells = [
            {"composition": "C", "cell_index": 0, "element_id": "Atmosphere", "x": 16, "y": 8, "w": 4, "h": 2,
             "min_w": 4, "min_h": 2, "max_w": 4, "max_h": 2, "flags": []},
            {"composition": "C", "cell_index": 1, "element_id": "Tactics", "x": 16, "y": 0, "w": 4, "h": 4,
             "min_w": 4, "min_h": 4, "max_w": 4, "max_h": 4, "flags": []},
            {"composition": "C", "cell_index": 2, "element_id": "Training", "x": 16, "y": 4, "w": 4, "h": 4,
             "min_w": 4, "min_h": 4, "max_w": 4, "max_h": 4, "flags": []},
        ]
        return {"cells": cells, "layouts": [{"id": 1, "name": "Tile", "guid": "g"}],
                "tiles": [{"composition": "C", "cell_element_id": e, "cell_index": i, "size": {"w": 4, "h": 4},
                           "tile_layout_id": 1} for i, e in enumerate(("Atmosphere", "Tactics", "Training"))]}

    def test_adds_only_pack_and_adds_with_a_resize_pack_below_it(self):
        a = screen.Assembler(self.dump())
        add = {"element_id": "Happiness", "cell_index": 5, "geometry": {"x": 16, "y": 12, "w": 4, "h": 4}}
        alone = a.place("C", 30, 16, adds=[add])
        self.assertEqual(alone["Happiness"]["row"], 10)
        both = a.place("C", 30, 16,
                       moves=[{"composition": "C", "cell_id": "Atmosphere",
                               "to": {"x": 16, "y": 8, "w": 4, "h": 4}}], adds=[add])
        self.assertEqual(both["Atmosphere"]["row"], 8)
        self.assertEqual(both["Atmosphere"]["h"], 4)
        self.assertEqual(both["Happiness"]["row"], 12)
        self.assertEqual(both["Happiness"]["col"], 26)      # right-anchored on the wider screen


class OptionalSlices(unittest.TestCase):
    """The four measured states: bottom slices are anchored at the grid's DESIGN bottom."""
    SLOTS = [{"element_id": "SquadHierachy", "direction": "m_bottom", "location": {"x": 16, "y": 0, "width": 4, "height": 2}},
             {"element_id": "MedicalCentre", "direction": "m_bottom", "location": {"x": 16, "y": 2, "width": 4, "height": 2}},
             {"element_id": "Loans", "direction": "m_bottom", "location": {"x": 16, "y": 4, "width": 4, "height": 2}}]

    def place(self, bottom):
        from skin_editor.render import preview
        shown, hidden = [], []
        for s in self.SLOTS:
            geo, why = preview.place_slice(s, bottom, 16)
            (shown if geo else hidden).append(s["element_id"] if geo else (s["element_id"], why))
        return shown, hidden

    def test_stock_design_bottom_10_shows_all_three(self):
        shown, hidden = self.place(10)
        self.assertEqual(shown, ["SquadHierachy", "MedicalCentre", "Loans"])
        self.assertEqual(hidden, [])

    def test_test_c_bottom_12_shows_hierarchy_and_medical_and_clips_loans(self):
        shown, hidden = self.place(12)
        self.assertEqual(shown, ["SquadHierachy", "MedicalCentre"])
        self.assertEqual([h[0] for h in hidden], ["Loans"])

    def test_test_d_and_cd_bottom_16_clip_all_three_so_rows_14_15_stay_empty(self):
        for bottom in (16, 16):
            shown, hidden = self.place(bottom)
            self.assertEqual(shown, [])
            self.assertEqual([h[0] for h in hidden], ["SquadHierachy", "MedicalCentre", "Loans"])


if __name__ == "__main__":
    unittest.main()
