"""Game screenshots for the tile organiser's backdrop: a folder in the workspace, PNG only, never part of a project or a skin. Runs without the game."""
import json
import tempfile
import unittest
from pathlib import Path

from PIL import Image

from skin_editor import gamescreens, plain, project as project_mod
from skin_editor.api import rpc
from tests.test_api import close_logs, engine


class Screens(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True); self.addCleanup(self.tmp.cleanup); self.addCleanup(close_logs)
        self.dir = Path(self.tmp.name)
        self.e = engine(self.tmp.name)
        self.png = self.dir / "shot.png"; Image.new("RGB", (40, 20), (1, 2, 3)).save(self.png)

    def call(self, m, p=None):
        return json.loads(rpc.handle(self.e, json.dumps({"jsonrpc": "2.0", "id": 1, "method": m, "params": p or {}})))

    def test_add_list_read_remove_round_trip_and_it_stays_in_the_workspace_folder(self):
        r = self.call("screens.add", {"path": str(self.png), "name": "forest-squad.png"})["result"]
        self.assertEqual((r["name"], r["width"], r["height"]), ("forest-squad.png", 40, 20))
        lst = self.call("screens.list")["result"]
        self.assertEqual([s["name"] for s in lst["screens"]], ["forest-squad.png"])
        self.assertEqual(Path(lst["folder"]), Path(self.e.ws.root) / "game-screens")
        img = self.call("screens.image", {"name": "forest-squad.png"})["result"]
        self.assertEqual(img["content_type"], "image/png")
        self.assertTrue(__import__("base64").b64decode(img["base64"]).startswith(gamescreens.PNG))
        self.assertEqual(self.call("screens.remove", {"name": "forest-squad.png"})["result"], {"removed": "forest-squad.png"})
        self.assertEqual(self.call("screens.list")["result"]["screens"], [])

    def test_refusals_are_in_plain_words_and_nothing_escapes_the_folder(self):
        txt = self.dir / "x.png"; txt.write_text("not a png")
        self.assertIn("Pick a PNG", self.call("screens.add", {"path": str(txt)})["error"]["data"]["plain"])
        self.assertIn("Pick a PNG", self.call("screens.add", {"path": str(self.dir / "missing.png")})["error"]["data"]["plain"])
        self.call("screens.add", {"path": str(self.png), "name": "a.png"})
        self.assertIn("already there", self.call("screens.add", {"path": str(self.png), "name": "a.png"})["error"]["data"]["plain"])
        self.assertNotIn("error", self.call("screens.add", {"path": str(self.png), "name": "a.png", "replace": True}))
        for bad in ("../a.png", "a/b.png", "..\a.png", "a.jpg", ".png", ""):
            self.assertIn("Use only letters", self.call("screens.image", {"name": bad})["error"]["data"]["plain"], bad)
        self.assertIn("isn't in the list", self.call("screens.image", {"name": "nope.png"})["error"]["data"]["plain"])
        self.assertEqual(list(Path(self.tmp.name).glob("*.part")), [])

    def test_a_projects_files_and_exports_never_contain_the_screenshots(self):
        self.call("screens.add", {"path": str(self.png), "name": "club.png"})
        p = project_mod.new("pp"); from skin_editor import projfmt; projfmt.write(self.e.ws, p)
        names = {f.name for f in projfmt.folder(self.e.ws, "pp").rglob("*")}
        self.assertNotIn("club.png", names)
        self.assertNotIn("game-screens", {x.name for x in projfmt.folder(self.e.ws, "pp").iterdir()})

    def test_every_refusal_has_its_own_sentence(self):
        for m in ("pick a PNG screenshot", "a screenshot is at most 30 MB", "a screenshot with that name is already there", "bad screenshot name: letters", "no screenshot named x"):
            self.assertIsNotNone(plain.match(m), m)


if __name__ == "__main__":
    unittest.main()
