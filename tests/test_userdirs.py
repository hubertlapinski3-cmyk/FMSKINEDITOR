import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from skin_editor import detect, native, userdirs

SUB = Path("Sports Interactive") / "Football Manager 27"


def mk(p):
    p.mkdir(parents=True, exist_ok=True)
    return p


class Proton(unittest.TestCase):
    def setUp(self):
        self.t = tempfile.TemporaryDirectory()
        self.home = Path(self.t.name)

    def tearDown(self):
        self.t.cleanup()

    def prefix(self, root, appid="4530370"):
        return mk(root / "steamapps" / "compatdata" / appid / "pfx" / "drive_c" / "users" / "steamuser" / "Documents" / SUB)

    def test_user_folder_is_inside_the_proton_prefix_not_home_documents(self):
        mk(self.home / "Documents" / SUB)                          # must lose: Proton's folder is the one the game uses
        want = self.prefix(self.home / ".local" / "share" / "Steam")
        self.assertEqual(userdirs.user_folder(self.home, "linux"), want)

    def test_flatpak_and_snap_steam_roots_are_searched(self):
        want = self.prefix(self.home / ".var" / "app" / "com.valvesoftware.Steam" / ".local" / "share" / "Steam")
        self.assertEqual(userdirs.user_folder(self.home, "linux"), want)

    def test_appid_is_read_from_the_manifest(self):
        root = self.home / ".steam" / "steam"
        mk(root / "steamapps")
        (root / "steamapps" / "appmanifest_999.acf").write_text('"AppState"\n{\n "appid" "999"\n "installdir" "Football Manager 27"\n}\n')
        (root / "steamapps" / "appmanifest_1.acf").write_text('"AppState"\n{\n "appid" "1"\n "installdir" "Other Game"\n}\n')
        want = self.prefix(root, "999")
        self.assertEqual(userdirs.fm27_appids(root / "steamapps"), ["999"])
        self.assertEqual(userdirs.user_folder(self.home, "linux"), want)

    def test_no_prefix_falls_back_to_home_documents_then_none(self):
        self.assertIsNone(userdirs.user_folder(self.home, "linux"))
        d = mk(self.home / "Documents" / SUB)
        self.assertEqual(userdirs.user_folder(self.home, "linux"), d)

    def test_native_skins_root_follows_it(self):
        want = self.prefix(self.home / ".steam" / "steam")
        with mock.patch.object(Path, "home", return_value=self.home), mock.patch.object(sys, "platform", "linux"):
            self.assertEqual(native.skins_root(), want / "skins")


class MacAndWindows(unittest.TestCase):
    def setUp(self):
        self.t = tempfile.TemporaryDirectory()
        self.home = Path(self.t.name)

    def tearDown(self):
        self.t.cleanup()

    def test_macos_application_support(self):
        d = mk(self.home / "Library" / "Application Support" / SUB)
        self.assertEqual(userdirs.user_folder(self.home, "darwin"), d)

    def test_windows_known_folder_wins_over_guessed_home_documents(self):
        redirected = mk(self.home / "D_drive_docs")
        mk(redirected / SUB)
        mk(self.home / "Documents" / SUB)
        self.assertEqual(userdirs.user_folder(self.home, "win32", documents=redirected), redirected / SUB)

    def test_windows_onedrive_is_still_found_when_the_known_folder_is_unknown(self):
        d = mk(self.home / "OneDrive" / "Documents" / SUB)
        with mock.patch.object(userdirs, "windows_documents", return_value=None):
            self.assertEqual(userdirs.user_folder(self.home, "win32"), d)

    def test_this_machine_resolves_the_real_windows_documents_folder(self):
        if sys.platform != "win32":
            self.skipTest("Windows only")
        docs = userdirs.windows_documents()
        self.assertTrue(docs and docs.is_dir())


class LibraryRoots(unittest.TestCase):
    def test_linux_library_roots_cover_xdg_steam_and_libraryfolders(self):
        with tempfile.TemporaryDirectory() as t:
            home = Path(t)
            common = mk(home / ".local" / "share" / "Steam" / "steamapps" / "common")
            lib = mk(home / "games" / "steamapps" / "common")
            (home / ".local" / "share" / "Steam" / "steamapps" / "libraryfolders.vdf").write_text('"libraryfolders"\n{\n "0"\n {\n "path" "%s"\n }\n}\n' % (home / "games").as_posix())
            with mock.patch.object(Path, "home", return_value=home), mock.patch.object(sys, "platform", "linux"):
                roots = detect.library_roots()
            self.assertIn(common, roots)
            self.assertIn(lib, roots)


if __name__ == "__main__":
    unittest.main()
