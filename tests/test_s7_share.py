"""S7 of the Simple mode plan: save the skin as a file (a zip with the versions inside), open a downloaded skin file as a copy (checked, nothing applied blindly),
and Start over (what is lost is said first; the previous state goes to the trash). Runs without the game."""
import hashlib
import json
import tempfile
import unittest
import zipfile
from pathlib import Path

from skin_editor import native, plain, project as project_mod, projfmt, share
from skin_editor.api import rpc
from tests.test_api import close_logs, engine
from tests.test_s1_engine import crimson_index


class Share(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True); self.addCleanup(self.tmp.cleanup); self.addCleanup(close_logs)
        self.dir = Path(self.tmp.name)
        self.e = engine(self.tmp.name); self.e.index = crimson_index()
        self.assertNotIn("error", self.call("project.create_folder", {"name": "mine"}))
        p = self.call("project.get", {"name": "mine"})["result"]
        p["token_overrides"] = [{"token": "--global-background", "value": {"rgb": "#112233", "a": 1.0}}]
        self.assertNotIn("error", self.call("project.save", {"project": p}))

    def call(self, m, p=None):
        return json.loads(rpc.handle(self.e, json.dumps({"jsonrpc": "2.0", "id": 1, "method": m, "params": p or {}})))

    def err(self, r):
        self.assertIn("error", r, r)
        return r["error"]["data"]["plain"]

    def test_save_writes_one_zip_with_the_versions_and_hashes_inside_and_no_export_marker(self):
        out = self.dir / "mine.zip"
        r = self.call("share.save", {"project": "mine", "path": str(out), "studio_version": "1.2.0"})["result"]
        self.assertEqual((r["skin"], r["manifest"]["format"], r["manifest"]["studio_version"]), ("mine", share.FORMAT, "1.2.0"))
        with zipfile.ZipFile(out) as z:
            names = z.namelist()
            man = json.loads(z.read(share.MANIFEST))
            self.assertIn("mine/skin.json", names); self.assertIn("mine/tokens.uss", names)
            self.assertFalse(any(n.endswith(native.MARKER) for n in names), "this PC's export marker stays out")
            self.assertIn("--global-background: #112233", z.read("mine/tokens.uss").decode())
            for f in man["files"]:
                self.assertEqual(hashlib.sha256(z.read(f["path"])).hexdigest(), f["sha256"], f["path"])
        self.assertEqual(sorted(f["path"] for f in man["files"]), sorted(n for n in names if n != share.MANIFEST))
        self.assertFalse(list(self.dir.glob("*.part")))

    def test_save_refusals_are_in_plain_words(self):
        self.assertIn(".zip", self.err(self.call("share.save", {"project": "mine", "path": str(self.dir / "mine.txt")})))
        (self.dir / "taken.zip").write_bytes(b"x")
        self.assertIn("already there", self.err(self.call("share.save", {"project": "mine", "path": str(self.dir / "taken.zip")})))
        self.assertNotIn("error", self.call("share.save", {"project": "mine", "path": str(self.dir / "taken.zip"), "overwrite": True}))
        self.call("project.create_folder", {"name": "empty"})
        self.assertIn("haven't changed anything", self.err(self.call("share.save", {"project": "empty", "path": str(self.dir / "e.zip")})))

    def test_a_saved_file_round_trips_inspect_then_open_as_a_new_project_that_exports_the_same(self):
        out = self.dir / "mine.zip"
        self.call("share.save", {"project": "mine", "path": str(out), "studio_version": "1.2.0"})
        before = sorted(p.name for p in self.dir.rglob("*"))
        info = self.call("share.inspect", {"path": str(out)})["result"]
        self.assertEqual(sorted(p.name for p in self.dir.rglob("*")), before, "inspect writes nothing")
        self.assertEqual((info["skin"], info["folder"], info["manifest"]["studio_version"], info["refused"]), ("mine", "mine", "1.2.0", []))
        r = self.call("share.open", {"path": str(out), "name": "copy"})
        self.assertNotIn("error", r, r)
        self.assertTrue(projfmt.is_folder(self.e.ws, "copy"))
        skins = self.dir / "skins"; skins.mkdir()
        a = native.export(self.e.ws, project_mod.load(self.e.ws, "mine"), self.e.index, None, skins)
        b = native.export(self.e.ws, project_mod.load(self.e.ws, "copy"), self.e.index, None, skins)
        self.assertIn("--global-background: #112233", "".join((Path(b["folder"]) / s).read_text(encoding="utf-8") for s in b["sheets"]))
        self.assertEqual(a["problems"], []); self.assertEqual(b["problems"], [])
        self.assertIn("a project with that name exists", self.call("share.open", {"path": str(out), "name": "copy"})["error"]["message"])

    def _zip(self, name, files):
        f = self.dir / name
        with zipfile.ZipFile(f, "w") as z:
            for n, data in files.items():
                z.writestr(n, data)
        return f

    def test_a_downloaded_file_is_checked_before_anything_is_made(self):
        skin = {"skin.json": json.dumps({"Name": "Theirs", "Sheets": ["a.uss"]}), "a.uss": ":root { --x: #FFFFFF; }"}
        bad = self._zip("evil.zip", {"../outside.uss": "x", **skin})
        self.assertIn("outside its own folder", self.err(self.call("share.inspect", {"path": str(bad)})))
        none = self._zip("none.zip", {"readme.txt": "hello"})
        self.assertIn("no skin.json", self.err(self.call("share.inspect", {"path": str(none)})))
        odd = self._zip("odd.zip", {**{"Theirs/" + k: v for k, v in skin.items()}, "Theirs/run.exe": "MZ", "Theirs/" + native.MARKER: "{}"})
        info = self.call("share.inspect", {"path": str(odd)})["result"]
        self.assertEqual(info["skin"], "Theirs")
        self.assertEqual(sorted(x["file"] for x in info["refused"]), ["Theirs/.fm27se-export.json", "Theirs/run.exe"])
        self.assertNotIn("error", self.call("share.open", {"path": str(odd), "name": "theirs"}))
        files = [p.name for p in projfmt.folder(self.e.ws, "theirs").rglob("*")]
        self.assertNotIn("run.exe", files); self.assertNotIn(native.MARKER, files)
        theirs = project_mod.load(self.e.ws, "theirs")
        self.assertEqual(native.changes(theirs), {"imported sheets": 1}, "a skin that is only style sheets changes the game: it can be put in the game and saved")
        self.assertNotIn("error", self.call("share.save", {"project": "theirs", "path": str(self.dir / "theirs.zip")}))
        gap = self._zip("gap.zip", {"skin.json": json.dumps({"Name": "G", "Sheets": ["missing.uss"]})})
        self.assertIn("incomplete", self.err(self.call("share.open", {"path": str(gap), "name": "gap"})))
        self.assertFalse(projfmt.is_folder(self.e.ws, "gap"))
        self.assertIn("isn't a skin file", self.err(self.call("share.inspect", {"path": str(self.dir / "nothing.zip")})))

    def test_start_over_says_what_is_lost_first_needs_confirmation_and_keeps_the_old_state_in_the_trash(self):
        pre = self.call("project.start_over_preview", {"project": "mine"})["result"]
        self.assertEqual(pre["lost"], {"colours": 1})
        self.assertIn("nothing was changed", self.err(self.call("project.start_over", {"project": "mine"})))
        self.assertEqual(len(project_mod.load(self.e.ws, "mine")["token_overrides"]), 1)
        r = self.call("project.start_over", {"project": "mine", "confirm": True})["result"]
        self.assertEqual(r["lost"], {"colours": 1})
        self.assertEqual(r["project"]["token_overrides"], []); self.assertEqual(r["project"]["options"]["output"], "native")
        self.assertEqual(native.changes(r["project"]), {})
        old = Path(r["trash"])
        self.assertTrue(old.is_dir()); self.assertIn("#112233", "".join(f.read_text(encoding="utf-8", errors="ignore") for f in old.rglob("*") if f.is_file()))

    def test_every_share_refusal_has_its_own_sentence(self):
        for m in ("a skin file must end in .zip", "that file exists; choose another name or confirm replacing it", "that is not a skin file (a .zip)",
                  "the skin file has no skin.json (or more than one skin)", "the skin file lists sheets it does not hold: a", "the skin file has a path that leaves its folder (x)",
                  "the skin file holds too many files (9; at most 1)", "the skin file unpacks to more than 300 MB", "confirm is required to start over"):
            self.assertIsNotNone(plain.match(m), m)


if __name__ == "__main__":
    unittest.main()
