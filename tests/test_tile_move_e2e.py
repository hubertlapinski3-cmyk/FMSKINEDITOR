"""M5 follow-up (the tile-move thin spot): a tile move through the REAL path, offline: the real layout dump imported into a temporary workspace, the placement store written by the
RPC `placement.add`, the project's move-cell ops built by `tiles.ops_for`, and `render.screen` drawing the moved cell with the skin on and the vanilla position with it off."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from skin_editor import changes, layout_dump, tiles
from skin_editor.api import rpc

from test_api import close_logs, engine

REAL = Path.home() / "AppData" / "Local" / "FM27SkinEditor" / "layout" / "current.json"


@unittest.skipUnless(REAL.is_file(), "needs the imported layout dump")
class TileMoveEndToEnd(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.addCleanup(self.tmp.cleanup)
        self.addCleanup(close_logs)
        self.addCleanup(changes.set_sink, None)
        self.e = engine(self.tmp.name)
        layout_dump.import_dump(self.e.ws, str(REAL))
        # The freshness gate compares the dump with the installed game's reference hashes: it guards WRITING to the game, which this test never does, and a temporary workspace has no
        # snapshot. It is stubbed; everything else is the real path (dump, placement store, ops, assembly).
        p = mock.patch("skin_editor.placement.can_edit", return_value={"ok": True, "why": ""})
        p.start()
        self.addCleanup(p.stop)
        self.sub = self.e.events.subscribe()

    def call(self, method, params=None):
        r = json.loads(rpc.handle(self.e, json.dumps({"jsonrpc": "2.0", "method": method, "id": 1, "params": params or {}})))
        self.assertNotIn("error", r, r)
        return r["result"]

    def events(self):
        out = []
        while not self.sub.empty():
            ev = self.sub.get()
            if ev["type"] == "render.invalidate":
                out.append(ev["data"])
        return out

    def host(self, screen, name):
        return next(h for h in screen["hosts"] if h["element_id"] == name)

    def test_a_stored_move_reaches_the_screen_assembly_and_the_toggle_and_remove_undo_it(self):
        d = layout_dump.load(self.e.ws)
        cell = next(c for c in d["cells"] if c["composition"] == "SquadComposition-Large" and c["element_id"] == "Atmosphere")
        self.call("project.create_folder", {"name": "demo", "target": "native"})
        self.events()
        screen = lambda skin=True: self.call("render.screen", {"composition": "SquadComposition-Large", "width": 2468.8, "height": 1319.3, "project": "demo", "skin": skin})
        base = self.host(screen(False), "Atmosphere")
        self.assertEqual((base["col"], base["row"]), (26, 8))                       # right-anchored on the 30 x 16 grid, as measured in the game
        edit = {"composition": "SquadComposition-Large", "cell_index": cell["cell_index"], "geometry": {"x": 12, "y": 8, "w": cell["w"], "h": cell["h"]}}
        checked = self.call("placement.check", {"project": "demo", "edit": edit})
        self.assertEqual(checked["blocks"], [])
        self.assertTrue(checked["collisions"])                                        # it overlaps FirstTeamOverview: the panel must confirm
        with self.assertRaises(AssertionError):
            self.call("placement.add", {"project": "demo", "edit": edit})            # refused without confirm, nothing stored
        self.assertEqual(self.events(), [])
        self.call("placement.add", {"project": "demo", "edit": edit, "confirm": True})
        ev = self.events()
        self.assertEqual([(e["project"], e["reason"]) for e in ev], [("demo", "tile-move")])         # exactly one invalidate
        ops = tiles.ops_for(self.e.ws, "demo")
        self.assertEqual([(o["cell_id"], o["to"]) for o in ops], [("Atmosphere", {"x": 12, "y": 8})])
        moved = self.host(screen(True), "Atmosphere")
        self.assertEqual((moved["col"], moved["row"]), (12 + 10, 8))                  # the design position moved by 4 columns, still right-anchored by its design edge
        self.assertIn("moved by the project", moved["mode"])
        self.assertEqual(moved["px"]["left"], 12 + 82 * 22)
        self.assertEqual(self.host(screen(False), "Atmosphere")["col"], 26)            # the vanilla toggle draws the game's own cell
        self.assertEqual(self.host(screen(True), "Tactics"), self.host(screen(False), "Tactics"))        # nothing else moved
        self.call("placement.remove", {"project": "demo", "id": self.call("placement.list", {"project": "demo"})["edits"][0]["id"]})
        self.assertEqual([e["reason"] for e in self.events()], ["tile-move"])
        self.assertEqual(self.host(screen(True), "Atmosphere")["col"], 26)


if __name__ == "__main__":
    unittest.main()
