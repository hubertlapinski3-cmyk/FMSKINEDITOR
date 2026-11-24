"""E2E1: the tile-move overlap gate counts the Playground session's own moves as stand-ins for their cells, so two tiles can swap places (Atmosphere y4, Training y6) one recorded move at a time."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from skin_editor import config, playops
from skin_editor.engine import Engine

DUMP = Path(r"__absent_fixture_path__")
SQUAD = "SquadComposition-Large"


def move_op(cell_index, element, x, y, w, h):
    target = {"screen": SQUAD, "logical_id": "%s|host:%s@%d" % (SQUAD, element, cell_index), "structural_key": "k", "locator": {"bundle": "b", "bundle_sha256": None, "path_id": "1"},
              "guard": {"type": "Host", "name": element, "classes": []},
              "cell": {"composition": SQUAD, "cell_index": cell_index, "cell_element_id": element, "geometry": {"x": x, "y": y, "w": w, "h": h}}}
    return playops.new_operation("MoveNode", target, {}, original={"value": {"x": 16, "y": 8, "w": w, "h": h}, "evidence": "directly serialized"})


@unittest.skipUnless(DUMP.is_file(), "needs the archived set-C layout dump")
class SessionStandIns(unittest.TestCase):
    def engine(self, session):
        e = Engine.__new__(Engine)
        e.ws = config.Workspace(tempfile.mkdtemp(prefix="fm27se-si-"))
        dump = json.loads(DUMP.read_text(encoding="utf-8-sig"))
        self.patches = [mock.patch("skin_editor.engine.layout_dump.load", return_value=dump),
                        mock.patch("skin_editor.engine.layout_dump.staleness", return_value={"status": "fresh"}),
                        mock.patch.object(Engine, "_playground_session", return_value=(session, None))]
        for p in self.patches:
            p.start()
            self.addCleanup(p.stop)
        return e

    def gate(self, e, cell_index, x, y, w, h):
        return e.playground_validate_move({}, {"composition": SQUAD, "cell_index": cell_index, "geometry": {"x": x, "y": y, "w": w, "h": h}, "project": "pg"})

    def test_without_the_session_each_half_of_the_exchange_collides_with_the_stock_cell(self):
        e = self.engine(playops.new_session("pg", None))
        self.assertFalse(self.gate(e, 0, 16, 4, 4, 2)["valid"])            # Atmosphere onto stock Training
        self.assertFalse(self.gate(e, 2, 16, 6, 4, 4)["valid"])            # Training onto stock Atmosphere

    def test_with_the_first_move_recorded_the_second_is_checked_against_where_it_now_stands(self):
        s = playops.new_session("pg", None)
        playops.add(s, move_op(0, "Atmosphere", 16, 10, 4, 2))              # Atmosphere out of the way (a free row)
        e = self.engine(s)
        self.assertTrue(self.gate(e, 2, 16, 6, 4, 4)["valid"])              # Training to y6: Atmosphere no longer stands at y8
        playops.add(s, move_op(2, "Training", 16, 6, 4, 4))
        r = self.gate(e, 0, 16, 4, 4, 2)                                    # Atmosphere to y4: Training now stands at y6-9
        self.assertTrue(r["valid"], r)

    def test_a_real_overlap_with_a_moved_cell_is_still_refused(self):
        s = playops.new_session("pg", None)
        playops.add(s, move_op(2, "Training", 16, 6, 4, 4))
        e = self.engine(s)
        r = self.gate(e, 0, 16, 6, 4, 2)                                    # onto Training's NEW place
        self.assertFalse(r["valid"])
        self.assertEqual([c["element_id"] for c in r["collisions"]], ["Training"])


if __name__ == "__main__":
    unittest.main()
