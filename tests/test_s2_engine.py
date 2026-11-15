"""S2 of the Simple mode plan, engine side: 'Put it in the game' (native route only), the empty-project guard, first-time and later steps, and the removal behind its own call."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from skin_editor import native, plain, project as project_mod
from skin_editor.api import rpc
from tests.test_api import close_logs, engine
from tests.test_s1_engine import crimson_index


class Changes(unittest.TestCase):
    def test_an_empty_project_changes_nothing_and_each_kind_is_counted(self):
        p = project_mod.new("x")
        self.assertEqual(native.changes(p), {})
        p["token_overrides"] = [{"token": "--a", "value": {"rgb": "#112233", "a": 1.0}}, {"token": "--b", "value": {"rgb": "#112233", "a": 1.0}}]
        p["reverts"] = ["--b"]
        self.assertEqual(native.changes(p), {"colours": 1}, "a reverted token does not count")
        p["options"]["club_colours"] = False
        self.assertEqual(native.changes(p), {"colours": 1, "flat look": 1})

    def test_the_steps_left_carry_the_skin_name_the_first_time_and_only_the_reload_after(self):
        first = native.steps_left("My skin", True)
        later = native.steps_left("My skin", False)
        self.assertEqual(len(first), 2); self.assertIn('pick "My skin"', first[0]); self.assertIn("Preferences", first[0])
        self.assertEqual(first[1], 'Press "Reload Skin".')
        self.assertEqual(later, ['Press "Reload Skin".'])


class Put(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True); self.addCleanup(self.tmp.cleanup); self.addCleanup(close_logs)
        self.skins = Path(self.tmp.name) / "skins"; self.skins.mkdir()
        self.e = engine(self.tmp.name); self.e.index = crimson_index()
        patcher = mock.patch.object(native, "skins_root", lambda: self.skins); patcher.start(); self.addCleanup(patcher.stop)

    def call(self, method, params=None):
        return json.loads(rpc.handle(self.e, json.dumps({"jsonrpc": "2.0", "method": method, "id": 1, "params": params or {}})))

    def put(self, name):
        r = self.call("native.put", {"project": name}); self.assertNotIn("error", r, r)
        return self.call("jobs.wait", {"id": r["result"]["job"], "timeout": 30})["result"]

    def make(self, name, change=True):
        self.assertNotIn("error", self.call("project.create_folder", {"name": name}))
        if change:
            p = self.call("project.get", {"name": name})["result"]
            p["token_overrides"] = [{"token": "--global-background", "value": {"rgb": "#112233", "a": 1.0}}]
            self.assertNotIn("error", self.call("project.save", {"project": p}))

    def test_an_empty_project_is_refused_in_plain_words_and_nothing_is_written(self):
        self.make("empty", change=False)
        pre = self.call("native.preflight", {"project": "empty"})["result"]
        self.assertFalse(pre["has_changes"]); self.assertEqual(pre["changes"], {})
        job = self.put("empty")
        self.assertEqual(job["state"], "failed")
        self.assertIn("changes nothing yet", job["error"])
        self.assertIn("haven't changed anything", plain.plain(job["error"].split(": ", 1)[-1])["plain"])
        self.assertEqual(list(self.skins.iterdir()), [], "the skins folder is untouched")

    def test_the_first_put_writes_the_skin_and_says_two_steps_the_second_says_one(self):
        self.make("mine")
        pre = self.call("native.preflight", {"project": "mine"})["result"]
        self.assertTrue(pre["has_changes"]); self.assertTrue(pre["first_time"]); self.assertEqual(pre["changes"], {"colours": 1}); self.assertEqual(pre["skin"], "mine")
        self.assertEqual(pre["skins_folder"], str(self.skins))
        job = self.put("mine"); self.assertEqual(job["state"], "done", job)
        res = job["result"]
        self.assertEqual((res["skin"], res["first_time"], res["tokens"]), ("mine", True, 1))
        self.assertEqual(len(res["steps_left"]), 2); self.assertIn('"mine"', res["steps_left"][0])
        self.assertEqual(res["problems"], [])
        folder = self.skins / "mine"
        self.assertTrue((folder / "skin.json").is_file()); self.assertTrue((folder / native.MARKER).is_file())
        self.assertIn("--global-background: #112233", (folder / "tokens.uss").read_text(encoding="utf-8"))
        self.assertFalse(self.call("native.preflight", {"project": "mine"})["result"]["first_time"])
        again = self.put("mine")["result"]
        self.assertEqual((again["first_time"], again["steps_left"]), (False, ['Press "Reload Skin".']))

    def test_the_job_reports_its_steps_in_words(self):
        self.make("mine")
        job = self.put("mine"); self.assertEqual(job["state"], "done")
        # events are throttled to ten a second, but the job's own label follows every message: the last one is the last step, in words
        self.assertEqual(job["label"], "Checking what was written")
        self.assertEqual(job["progress"], 1.0)
        labels = {"Checking your skin", "Writing the skin into your skins folder", "Checking what was written"}
        self.assertTrue(all(isinstance(s, str) and s[0].isupper() and not s.endswith(".") for s in labels))

    def test_a_folder_this_editor_did_not_write_is_never_overwritten_and_the_refusal_is_plain(self):
        self.make("mine")
        (self.skins / "mine").mkdir(); (self.skins / "mine" / "keep.txt").write_text("someone else's", encoding="utf-8")
        job = self.put("mine"); self.assertEqual(job["state"], "failed")
        self.assertIn("not written by this editor", job["error"])
        self.assertEqual((self.skins / "mine" / "keep.txt").read_text(encoding="utf-8"), "someone else's")

    def test_the_game_folder_is_never_written(self):
        self.make("mine")
        written = []
        real = Path.write_text
        with mock.patch.object(Path, "write_text", lambda s, *a, **k: (written.append(str(s)), real(s, *a, **k))[1]):
            self.put("mine")
        self.assertTrue(written)
        for w in written:
            self.assertNotIn("StreamingAssets", w); self.assertNotIn("Football Manager 27\\fm_Data", w)

    def test_removal_needs_confirmation_and_only_removes_a_folder_this_editor_wrote(self):
        self.make("mine"); self.put("mine")
        self.assertIn("error", self.call("native.remove", {"project": "mine"}))
        self.assertTrue((self.skins / "mine").is_dir())
        r = self.call("native.remove", {"project": "mine", "confirm": True}); self.assertNotIn("error", r, r)
        self.assertFalse((self.skins / "mine").exists())
        gone = self.call("native.remove", {"project": "mine", "confirm": True}); self.assertIn("error", gone)
        self.assertIn("no skin of that name", gone["error"]["data"]["plain"])
        self.make("other"); (self.skins / "other").mkdir(); (self.skins / "other" / "f.txt").write_text("x", encoding="utf-8")
        refused = self.call("native.remove", {"project": "other", "confirm": True}); self.assertIn("error", refused)
        self.assertIn("wasn't made by this Studio", refused["error"]["data"]["plain"])
        self.assertTrue((self.skins / "other" / "f.txt").is_file())


class SkinsRootOverride(unittest.TestCase):
    def test_the_scratch_override_redirects_the_skins_folder_and_is_off_otherwise(self):
        with mock.patch.dict("os.environ", {"FM27SE_SKINS_DIR": r"C:\scratch\skins"}):
            self.assertEqual(native.skins_root(), Path(r"C:\scratch\skins"))
        with mock.patch.dict("os.environ", {}, clear=False):
            import os; os.environ.pop("FM27SE_SKINS_DIR", None)
            self.assertNotEqual(str(native.skins_root() or ""), r"C:\scratch\skins")


class FlatLookReplacement(unittest.TestCase):
    """What the club-colour option writes (checked against the real index on 2026-11-15: 20 club rules + 76 nav rules): only 9 of the 96 rules carry the replacement colour."""
    def test_the_replacement_colour_goes_into_exactly_the_surface_rules_and_nothing_else_changes(self):
        from skin_editor import club_colours
        a, b = club_colours.rules({"rgb": "#171717", "a": 1.0}), club_colours.rules({"rgb": "#ABCDEF", "a": 1.0})
        self.assertEqual(len(a), len(b)); self.assertEqual(len(a), 20)
        self.assertEqual([r["selector"] for r in a], [r["selector"] for r in b])
        differing = [(x, y) for x, y in zip(a, b) if x["props"] != y["props"]]
        self.assertEqual(len(differing), 9)
        for x, y in differing:
            for k in x["props"]:
                if x["props"][k] != y["props"][k]:
                    self.assertIn(k, {"background-color", "--start-colour", "--end-colour"}); self.assertEqual(y["props"][k]["rgb"], "#ABCDEF")
        for x, y in zip(a, b):
            if x["props"] == y["props"]:
                self.assertTrue(set(x["props"]) <= {"opacity", "visibility", "border-color"}, x["selector"])

    def test_the_dark_bar_rules_do_not_depend_on_the_replacement(self):
        import inspect
        self.assertEqual(list(inspect.signature(native.nav_on_light_rules).parameters), ["index"])


if __name__ == "__main__":
    unittest.main()
