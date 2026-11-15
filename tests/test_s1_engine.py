"""S1 of the Simple mode plan, engine side: a preset is created as a FOLDER project with native output, the club-colour answer reaches the project, the stored mode word 'expert' becomes 'advanced'."""
import json
import tempfile
import unittest
from pathlib import Path

from skin_editor import projfmt
from skin_editor.api import rpc
from tests import test_core as tc
from tests.test_api import close_logs, engine


def crimson_index():
    t = tc.sheet(); sp = tc.tp.SheetPatcher(t, tc.verify_static.EMPTY)
    for n in ("--global-background", "--colours-tactics-base-20", "--colours-base-red-strong"):
        t["m_Rules"][0]["m_Properties"].append(tc.P(n, sp._encode("#16181D")))
    return tc.index(t)


class S1Engine(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True); self.addCleanup(self.tmp.cleanup); self.addCleanup(close_logs)
        self.e = engine(self.tmp.name)
        self.e.index = crimson_index()

    def rpc(self, method, params=None):
        return json.loads(rpc.handle(self.e, json.dumps({"jsonrpc": "2.0", "method": method, "id": 1, "params": params or {}})))

    def test_a_preset_is_a_folder_project_with_native_output_from_the_start(self):
        r = self.rpc("project.create_folder", {"name": "cr", "preset": "crimson"})
        self.assertNotIn("error", r, r)
        ws = self.e.ws
        self.assertTrue(projfmt.is_folder(ws, "cr"))
        self.assertFalse((ws.projects / "cr.skin.json").exists(), "never the single-file form")
        p = r["result"]["project"]
        self.assertEqual(p["options"]["output"], "native")
        self.assertEqual({o["token"] for o in p["token_overrides"]}, {"--global-background", "--colours-tactics-base-20", "--colours-base-red-strong"})
        self.assertGreater(len(p["scoped_rules"]), 60)
        self.assertEqual(json.loads((projfmt.folder(ws, "cr") / projfmt.MARK).read_text(encoding="utf-8"))["target"], "native")

    def test_the_old_create_still_writes_the_single_file_form(self):
        self.assertNotIn("error", self.rpc("project.create", {"name": "old", "preset": "crimson"}))
        self.assertFalse(projfmt.is_folder(self.e.ws, "old"))
        self.assertTrue((self.e.ws.projects / "old.skin.json").is_file())

    def test_the_club_colour_answer_reaches_the_project(self):
        keep = self.rpc("project.create_folder", {"name": "keep", "preset": "crimson", "keep_club_colours": True})["result"]["project"]
        absent = self.rpc("project.create_folder", {"name": "absent", "preset": "crimson"})["result"]["project"]
        gone = self.rpc("project.create_folder", {"name": "gone", "preset": "crimson", "keep_club_colours": False})["result"]["project"]
        self.assertIsNot(keep["options"].get("club_colours"), False)
        self.assertIsNot(absent["options"].get("club_colours"), False)
        self.assertIs(gone["options"]["club_colours"], False)
        empty = self.rpc("project.create_folder", {"name": "empty", "keep_club_colours": False})["result"]["project"]
        self.assertEqual(empty["token_overrides"], [])

    def test_an_unknown_preset_is_refused_with_a_plain_sentence(self):
        r = self.rpc("project.create_folder", {"name": "x", "preset": "nope"})
        self.assertIn("error", r)
        self.assertIn("plain", r["error"]["data"])

    def test_the_stored_mode_expert_is_migrated_to_advanced_and_only_that_changes(self):
        self.rpc("project.create_folder", {"name": "m1"})
        mark = projfmt.folder(self.e.ws, "m1") / projfmt.MARK
        head = json.loads(mark.read_text(encoding="utf-8"))
        self.assertEqual(head["mode"], "advanced", "a new project is written as advanced")
        head["mode"] = "expert"; mark.write_text(json.dumps(head, indent=2) + "\n", encoding="utf-8")
        before = {k: v for k, v in head.items() if k != "mode"}
        self.assertEqual(projfmt.migrate_modes(self.e.ws), ["m1"])
        after = json.loads(mark.read_text(encoding="utf-8"))
        self.assertEqual(after["mode"], "advanced")
        self.assertEqual({k: v for k, v in after.items() if k != "mode"}, before)
        self.assertEqual(projfmt.migrate_modes(self.e.ws), [], "idempotent")
        # a rewrite of the project through the model keeps 'advanced', and a stray 'expert' is mapped on write
        head["mode"] = "expert"; mark.write_text(json.dumps(head, indent=2) + "\n", encoding="utf-8")
        projfmt.write(self.e.ws, self.e.load_project("m1") if hasattr(self.e, "load_project") else __import__("skin_editor.project", fromlist=["load"]).load(self.e.ws, "m1"))
        self.assertEqual(json.loads(mark.read_text(encoding="utf-8"))["mode"], "advanced")

    def test_a_new_engine_migrates_existing_projects_on_start(self):
        self.rpc("project.create_folder", {"name": "m2"})
        mark = projfmt.folder(self.e.ws, "m2") / projfmt.MARK
        head = json.loads(mark.read_text(encoding="utf-8")); head["mode"] = "expert"; mark.write_text(json.dumps(head, indent=2) + "\n", encoding="utf-8")
        e2 = engine(self.tmp.name)
        self.assertEqual(json.loads(mark.read_text(encoding="utf-8"))["mode"], "advanced")
        del e2

    def test_browse_returns_the_used_colour_tokens_and_all_of_them_on_request(self):
        used = self.rpc("tokens.browse")["result"]
        everything = self.rpc("tokens.browse", {"used_only": False})["result"]
        self.assertEqual(used["total"], len(used["rows"]))
        self.assertGreaterEqual(everything["total"], used["total"])
        for r in everything["rows"]:
            self.assertRegex(r["rgb"], r"^#[0-9A-Fa-f]{6}$"); self.assertTrue(0 <= r["a"] <= 1)
        self.assertTrue(all(r["reach"] > 0 for r in used["rows"]))
        self.assertEqual([r["name"] for r in everything["rows"]], sorted(r["name"] for r in everything["rows"]))
        self.assertTrue({"--global-background", "--colours-tactics-base-20", "--colours-base-red-strong"} <= {r["name"] for r in everything["rows"]}, "the fixture's colour tokens are listed")

    def test_explain_returns_the_sentence_and_the_details(self):
        r = self.rpc("app.explain", {"message": "close the game before taking the vanilla snapshot"})["result"]
        self.assertIn("Close Football Manager", r["plain"])
        self.assertEqual(r["details"], "close the game before taking the vanilla snapshot")


if __name__ == "__main__":
    unittest.main()
