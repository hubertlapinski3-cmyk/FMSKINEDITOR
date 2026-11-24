"""Skin backups: a skin written into the game's skins folder is also copied to config `skin_backup_dir`, a new dated folder per save; no config, no backup; a failed backup never fails the save."""
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from skin_editor import native
from skin_editor.engine import Engine


def skin(root, name="demo"):
    f = Path(root) / name
    (f / "images").mkdir(parents=True)
    (f / "skin.json").write_text("{}", encoding="utf-8")
    return f


class Backup(unittest.TestCase):
    def test_each_save_gets_its_own_folder_and_nothing_is_overwritten(self):
        with tempfile.TemporaryDirectory() as t:
            f = skin(Path(t) / "skins")
            a = native.backup(f, Path(t) / "bk")
            (f / "skin.json").write_text('{"v": 2}', encoding="utf-8")
            b = native.backup(f, Path(t) / "bk")
            self.assertNotEqual(a, b)
            self.assertEqual((a / "skin.json").read_text(encoding="utf-8"), "{}")
            self.assertEqual((b / "skin.json").read_text(encoding="utf-8"), '{"v": 2}')
            self.assertEqual(a.parent, Path(t) / "bk" / "demo")

    def _engine(self, cfg):
        e = Engine.__new__(Engine)
        e.cfg = cfg
        return e

    def test_engine_backs_up_only_when_configured_and_only_the_game_skins_folder(self):
        with tempfile.TemporaryDirectory() as t:
            root = Path(t) / "skins"
            f = skin(root)
            with mock.patch.object(native, "skins_root", return_value=root):
                rep = {"folder": str(f)}
                self._engine({}).__dict__  # no setting: nothing happens
                self._engine({})._backup_skin(rep, root)
                self.assertNotIn("backup", rep)
                rep = {"folder": str(f)}
                self._engine({"skin_backup_dir": str(Path(t) / "bk")})._backup_skin(rep, root)
                self.assertTrue(Path(rep["backup"], "skin.json").is_file())
                rep = {"folder": str(f)}                                           # a test or custom destination is not the game's folder: no backup
                self._engine({"skin_backup_dir": str(Path(t) / "bk2")})._backup_skin(rep, Path(t) / "elsewhere")
                self.assertNotIn("backup", rep)

    def test_a_failed_backup_is_said_not_raised(self):
        with tempfile.TemporaryDirectory() as t:
            root = Path(t) / "skins"
            f = skin(root)
            with mock.patch.object(native, "skins_root", return_value=root), mock.patch.object(native, "backup", side_effect=OSError("disk full")):
                rep = {"folder": str(f)}
                self._engine({"skin_backup_dir": str(Path(t) / "bk")})._backup_skin(rep, root)
                self.assertEqual(rep["backup_error"], "disk full")


def tree_hashes(root):
    import hashlib
    return {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(Path(root).rglob("*")) if p.is_file()}


class OffByDefaultAndBuilds(unittest.TestCase):
    def test_the_backup_location_is_off_by_default_for_every_other_user(self):
        import copy
        from skin_editor import config
        self.assertIsNone(config.DEFAULTS["skin_backup_dir"])
        e = Engine.__new__(Engine)
        e.cfg = copy.deepcopy(config.DEFAULTS)
        e.ws = None
        with tempfile.TemporaryDirectory() as t:
            root = Path(t) / "skins"
            f = skin(root)
            rep = {"folder": str(f)}
            with mock.patch.object(native, "skins_root", return_value=root):
                e._backup_skin(rep, root)
            self.assertNotIn("backup", rep)
            with mock.patch("skin_editor.patcher.latest_build", return_value=f):
                e._backup_build("demo", rep)
            self.assertNotIn("backup", rep)
            self.assertEqual([p.name for p in Path(t).iterdir()], ["skins"])         # nothing was created anywhere

    def test_a_bundles_build_is_copied_whole_and_the_build_is_not_touched(self):
        with tempfile.TemporaryDirectory() as t:
            build = Path(t) / "ws" / "build" / "demo" / "20261117T000000Z"
            build.mkdir(parents=True)
            (build / "ui-styles_assets_default.bundle").write_bytes(b"B" * 5000)
            (build / "package.json").write_text('{"id": "x"}', encoding="utf-8")
            before = tree_hashes(build)
            e = Engine.__new__(Engine)
            e.cfg = {"skin_backup_dir": str(Path(t) / "bk")}
            e.ws = None
            with mock.patch("skin_editor.patcher.latest_build", return_value=build):
                rep = {}
                e._backup_build("demo", rep)
                again = {}
                e._backup_build("demo", again)
            target = Path(rep["backup"])
            self.assertEqual(target, Path(t) / "bk" / "demo" / "bundles-20261117T000000Z")
            self.assertEqual(tree_hashes(target), before)                           # the copy is byte for byte
            self.assertEqual(tree_hashes(build), before)                            # the build output did not change by one byte
            self.assertEqual(again["backup"], rep["backup"])                        # a second call overwrites nothing
            self.assertEqual(tree_hashes(target), before)


if __name__ == "__main__":
    unittest.main()
