"""Three refusals, three different messages: the game was updated; a game file was changed; a layout name is unknown. Built from the real code paths, on a scratch copy."""
import json
import tempfile
import unittest
from pathlib import Path

from skin_editor import bundles, config, install, plain
from tests.test_core import fake
from tests.test_install_guard import close_logs, scratch


class Messages(unittest.TestCase):
    def test_game_updated_says_what_to_do_and_does_not_send_the_user_to_verify(self):
        with tempfile.TemporaryDirectory() as tmp, fake():
            aa, ws, _d = scratch(tmp)
            (aa.parent / "catalog.hash").write_text("cat-new")
            with self.assertRaises(install.InstallError) as c:
                install.refuse_if_updated(ws, aa, "The render")
            tech = str(c.exception)
            self.assertIn("fm-skin-engine.exe", tech)                          # the installed app's engine, not only a source checkout's command
            self.assertIn("snapshot --force", tech)
            self.assertIn("python -m skin_editor snapshot --force", tech)
            said = plain.plain(tech)["plain"]
            self.assertIn("updated", said)
            self.assertIn("Re-read the game button", said)                     # the in-app way is now the primary instruction
            self.assertIn("fm-skin-engine.exe", said)                         # the command stays as the fallback for a Studio that will not start
            self.assertIn("snapshot --force", said)
            self.assertIn("FIRST verify in Steam", said)                     # verify first, then the button
            self.assertLess(said.index("FIRST verify in Steam"), said.index("Re-read the game"))
            self.assertLess(said.index("FIRST verify in Steam"), said.index("snapshot --force"))
            self.assertLess(tech.index("FIRST run Steam's"), tech.index("Re-read the game"))
            self.assertIn("refuses while a game file is still one this app installed", tech)
            self.assertNotIn("reinstall", said.lower())
            self.assertNotIn("no button", said)                               # the button exists now
            close_logs()

    def test_the_reread_recovers_the_updated_game_in_one_call(self):
        from skin_editor import index_styles
        with tempfile.TemporaryDirectory() as tmp, fake():
            aa, ws, _d = scratch(tmp)
            (aa.parent / "catalog.hash").write_text("cat-new")
            out = install.reread_after_update(ws, aa, "27.1.0.2505117")
            man = ws.vanilla_manifest()
            self.assertEqual(man["reference"]["catalog_hash"], "cat-new")     # the snapshot now describes the updated game
            self.assertEqual(out["snapshot"]["catalog_hash"], "cat-new")
            self.assertGreater(out["index"]["sheets"], 0)                     # and the style index was rebuilt with it
            ix = index_styles.load(ws)
            self.assertEqual(len(ix.sheets), out["index"]["sheets"])
            close_logs()

    def test_the_reread_refuses_while_a_skin_is_still_installed_and_never_records_it_as_the_games_own(self):
        with tempfile.TemporaryDirectory() as tmp, fake():
            aa, ws, _d = scratch(tmp)
            (aa / bundles.STYLE_BUNDLES[0]).write_text("a skin this app installed earlier")
            from skin_editor import install as legacy
            with open(ws.logs / "install-log.jsonl", "a", encoding="utf-8") as f:
                f.write(json.dumps({"time": "t", "file": bundles.STYLE_BUNDLES[0], "after": legacy.sha256(aa / bundles.STYLE_BUNDLES[0])}) + "\n")
            with self.assertRaises(install.InstallError) as c:
                install.reread_after_update(ws, aa, "27.1.0.2505117")
            self.assertIn("Verify integrity of game files first", str(c.exception))
            self.assertIn("Re-read the game button again", str(c.exception))
            said = plain.plain(str(c.exception))["plain"]
            self.assertIn("Verify integrity of game files", said)             # the plain sentence for the new refusal
            close_logs()

    def test_a_changed_game_file_keeps_the_verify_advice_and_is_not_called_an_update(self):
        with tempfile.TemporaryDirectory() as tmp, fake():
            aa, ws, _d = scratch(tmp)
            (aa / bundles.STYLE_BUNDLES[1]).write_text("someone's test skin")          # same catalog, one file changed: not an update
            self.assertEqual(install.live_status(ws, aa)[bundles.STYLE_BUNDLES[1]]["state"], "changed")
            self.assertEqual(install.tamper_status(ws, aa)["state"], "modified")
            said = plain.plain("the game's layout bundles are not stock (ui-tactics_assets_all.bundle); restore them or take a new snapshot")["plain"]
            self.assertIn("Verify integrity", said)
            self.assertNotIn("updated", said)
            close_logs()

    def test_an_unknown_layout_name_never_says_reinstall(self):
        said = plain.plain("no layout named 'NoSuchLayout'")["plain"]
        self.assertIn("No layout with that name", said)
        self.assertNotIn("reinstall", said.lower())
        self.assertNotIn("Verify", said)


if __name__ == "__main__":
    unittest.main()
