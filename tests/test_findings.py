"""The Session 2 findings data: well formed, every verdict has its theme and screen, every finding points at real ones, and the engine reports which screenshots the workspace holds."""
import json
import tempfile
import unittest
from pathlib import Path

from PIL import Image

from skin_editor import config, gamescreens
from skin_editor.api import rpc
from tests.test_api import close_logs, engine

DATA = json.loads((config.resource_root() / "data" / "findings" / "session2.json").read_text(encoding="utf-8"))
THEMES = {t["id"] for t in DATA["themes"]}
SCREENS = {s["id"] for s in DATA["screens"]}


class Data(unittest.TestCase):
    def test_every_theme_and_screen_has_a_verdict_in_a_known_word_and_a_note(self):
        for t in THEMES:
            for s in SCREENS:
                v = DATA["verdicts"]["%s/%s" % (t, s)]
                self.assertIn(v["v"], ("works", "exceptions", "clash", "not-done")); self.assertTrue(v["note"])
        self.assertEqual(len(DATA["verdicts"]), len(THEMES) * len(SCREENS))

    def test_findings_point_at_real_themes_and_screens_and_say_what_kind_they_are(self):
        ids = [f["id"] for f in DATA["findings"]]
        self.assertEqual(len(ids), len(set(ids)))
        for f in DATA["findings"]:
            self.assertIn(f["kind"], ("missing", "open", "decision", "works", "info"))
            self.assertTrue(f["title"] and f["text"])
            self.assertLessEqual(set(f["themes"]), THEMES); self.assertLessEqual(set(f["screens"]), SCREENS)

    def test_the_themes_match_the_gallery_and_the_numbers_quoted_agree_with_the_role_map(self):
        gal = json.loads((config.resource_root() / "data" / "simple" / "gallery.json").read_text(encoding="utf-8"))["themes"]
        self.assertEqual(sorted(t["name"] for t in DATA["themes"]), sorted(t["name"] for t in gal))
        badge = next(f for f in DATA["findings"] if f["id"] == "badge")
        rm = json.loads((config.resource_root() / "data" / "simple" / "roles.json").read_text(encoding="utf-8"))
        self.assertIn("%d entries" % len(rm["entries"]), badge["text"]); self.assertIn("%d checked pairs" % len(rm["contrast_pairs"]), badge["text"])
        self.assertIn("148", next(f for f in DATA["findings"] if f["id"] == "family-colours")["text"]); self.assertEqual(len(rm["kept"]), 148)


class Engine(unittest.TestCase):
    def test_findings_get_reports_only_the_screenshots_this_workspace_holds_by_name(self):
        tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True); self.addCleanup(tmp.cleanup); self.addCleanup(close_logs)
        e = engine(tmp.name)
        png = Path(tmp.name) / "x.png"; Image.new("RGB", (4, 4)).save(png)
        gamescreens.add(e.ws, png, "gallery-forest-squad.png"); gamescreens.add(e.ws, png, "something-else.png")
        r = json.loads(rpc.handle(e, json.dumps({"jsonrpc": "2.0", "id": 1, "method": "findings.get", "params": {}})))["result"]
        self.assertEqual(r["shots"], {"forest/squad": "gallery-forest-squad.png"})
        self.assertEqual(len(r["findings"]), len(DATA["findings"]))


if __name__ == "__main__":
    unittest.main()
