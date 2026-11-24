"""The frozen engine has no FMOD library: skin_editor/frozen.py stands in for fmod_toolkit, so UnityPy's export code imports and pictures work. Needs no game."""
import subprocess
import sys
import textwrap
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FREEZE = (ROOT / "tools" / "freeze_engine.py").read_text(encoding="utf-8")
ENTRY = (ROOT / "tools" / "engine_entry.py").read_text(encoding="utf-8")


def run(code):
    import os
    env = {"PYTHONPATH": str(ROOT), "SYSTEMROOT": os.environ.get("SYSTEMROOT", "")}
    for k in ("APPDATA", "LOCALAPPDATA", "USERPROFILE"):     # Python's per-user site-packages (UnityPy lives there on Windows)
        if os.environ.get(k):
            env[k] = os.environ[k]
    return subprocess.run([sys.executable, "-c", textwrap.dedent(code)], cwd=str(ROOT), capture_output=True, text=True, timeout=120, env=env)


class FrozenEngine(unittest.TestCase):
    def test_the_stand_in_makes_unitypys_export_code_importable_and_says_plainly_that_audio_is_absent(self):
        r = run("""
            import sys
            from skin_editor.frozen import install_audio_stub
            sys.modules.pop("fmod_toolkit", None)
            sys.modules["fmod_toolkit_real"] = None                      # the real package must not be what makes this pass: the stand-in is installed first
            m = install_audio_stub()
            import UnityPy.export.AudioClipConverter                     # the import that failed in the installed app
            assert sys.modules["fmod_toolkit"] is m
            try:
                m.import_pyfmodex()
            except RuntimeError as e:
                print("audio says:", e)
            else:
                raise SystemExit("using audio did not fail")
            print("export import ok")
        """)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("export import ok", r.stdout)
        self.assertIn("audio decoding is not available in this build", r.stdout)

    def test_the_stand_in_is_idempotent_and_does_not_replace_a_real_package_already_loaded(self):
        r = run("""
            import sys, types
            from skin_editor.frozen import install_audio_stub
            real = types.ModuleType("fmod_toolkit"); real.marker = 1; sys.modules["fmod_toolkit"] = real
            assert install_audio_stub() is real and install_audio_stub() is real
            print("ok")
        """)
        self.assertEqual((r.returncode, r.stdout.strip()), (0, "ok"), r.stderr)

    def test_the_frozen_entry_installs_it_before_anything_imports_unitypy_and_the_freeze_leaves_fmod_out(self):
        self.assertLess(ENTRY.index("install_audio_stub()"), ENTRY.index("from skin_editor.__main__ import main"))
        self.assertIn('"--exclude-module", "fmod_toolkit"', FREEZE)
        self.assertIn('"--exclude-module", "pyfmodex"', FREEZE)

    def test_the_selftest_passes_here_and_names_a_module_that_fails_to_import_even_when_it_is_not_an_importerror(self):
        from unittest import mock
        from skin_editor import frozen
        self.assertEqual(frozen.selftest(), [])
        class PyInstallerImportError(Exception): pass
        real = __import__("importlib").import_module
        def boom(name, *a, **k):
            if name == "astc_encoder": raise PyInstallerImportError("Failed to load dynlib/dll 'x'")
            return real(name, *a, **k)
        with mock.patch("importlib.import_module", boom):
            bad = frozen.selftest()
        self.assertEqual(len(bad), 1); self.assertIn("astc_encoder: PyInstallerImportError", bad[0])

    def test_the_bundle_round_trip_passes_on_the_committed_synthetic_fixture(self):
        from skin_editor import frozen
        self.assertEqual(frozen.bundle_roundtrip(), [])

    def test_the_committed_fixture_is_exactly_what_the_generator_writes_so_it_holds_no_game_content(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location("make_selftest_bundle", ROOT / "tools" / "make_selftest_bundle.py")
        m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
        self.assertEqual((ROOT / "data" / "selftest" / "roundtrip.unity3d").read_bytes(), m.bundle())

    def test_the_round_trip_reports_a_broken_write_path_a_missing_fixture_and_a_wrong_object(self):
        from unittest import mock
        from skin_editor import frozen
        import UnityPy.helpers.CompressionHelper as ch

        def broken(*a, **k):
            raise RuntimeError("Failed to load dynlib/dll 'lz4'")
        patched = {k: broken for k in ch.COMPRESSION_MAP}
        with mock.patch.dict(ch.COMPRESSION_MAP, patched):
            bad = frozen.bundle_roundtrip()
        self.assertEqual(len(bad), 1); self.assertIn("bundle round-trip: RuntimeError", bad[0])
        self.assertIn("is missing", frozen.bundle_roundtrip(ROOT / "data" / "selftest" / "nope.unity3d")[0])
        with mock.patch.object(frozen, "ROUNDTRIP_NAME", "something else"):
            self.assertIn("the fixture's object is", frozen.bundle_roundtrip()[0])

    def test_the_freeze_ships_the_fixture(self):
        self.assertIn('(ROOT / "data", sep)', FREEZE, "data/ (and so data/selftest/roundtrip.unity3d) is added to the frozen build")

    def test_a_failed_call_must_leave_its_traceback_in_the_documented_log_and_the_check_notices_when_it_does_not(self):
        from unittest import mock
        import logging
        from skin_editor import frozen
        self.assertEqual(frozen.check_failed_call_logs_traceback(), [])
        with mock.patch.object(logging.Logger, "warning", lambda *a, **k: None):           # a build that swallowed the log line
            bad = frozen.check_failed_call_logs_traceback()
        self.assertEqual(len(bad), 1); self.assertIn("left no traceback", bad[0]); self.assertIn("app.log", bad[0])

    def test_the_log_path_is_documented_where_the_other_logs_are_and_named_in_the_release_notes(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn("logs/launcher.log", readme); self.assertIn("logs/app.log", readme)
        self.assertIn("%LOCALAPPDATA%\\FM27SkinEditor\\logs\\app.log", readme)
        notes = (ROOT / "docs" / "RELEASE-NOTES-1.1.1.md").read_text(encoding="utf-8")
        self.assertIn("%LOCALAPPDATA%\\FM27SkinEditor\\logs\\app.log", notes)

    def test_the_notes_and_the_readme_say_where_the_calibration_report_of_a_repair_release_lives(self):
        notes = (ROOT / "docs" / "RELEASE-NOTES-1.1.1.md").read_text(encoding="utf-8")
        self.assertIn("No calibration report is attached to this release", notes); self.assertIn("v1.1.0 release page", notes)
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn("attaches no calibration report", readme); self.assertIn("lives on that release's page", readme)

    def test_every_frozen_build_runs_the_selftest_not_only_the_release_workflow(self):
        self.assertIn('"--selftest"', FREEZE)
        self.assertLess(FREEZE.index("--collect-all"), FREEZE.index('"--selftest"'))
        self.assertIn("return st.returncode", FREEZE)

    def test_pyinstaller_is_pinned_and_its_resolved_version_is_printed_at_build_time(self):
        import re
        pin = re.findall(r"(?mi)^pyinstaller==([\w.]+)\s*$", (ROOT / "requirements-build.txt").read_text(encoding="utf-8"))
        self.assertEqual(len(pin), 1, "exactly one pinned PyInstaller")
        wf = (ROOT / ".github" / "workflows" / "release.yml").read_text(encoding="utf-8")
        self.assertIn("-r requirements-build.txt", wf)
        self.assertNotRegex(wf, r"(?m)pip install[^\n]*\bpyinstaller\b(?!\S)", "no unpinned install left in the release")
        self.assertIn("PyInstaller resolved for this release", wf)
        self.assertLess(wf.index("PyInstaller resolved for this release"), wf.index("freeze_engine.py"))
        self.assertIn('print("PyInstaller resolved: %s (pinned: %s)', FREEZE, "every build, a local one included, prints it")
        self.assertIn("return 2", FREEZE, "and a build with another version is refused unless asked for as an experiment")
        import importlib.util
        spec = importlib.util.spec_from_file_location("freeze_engine", ROOT / "tools" / "freeze_engine.py")
        m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
        self.assertEqual(m.pinned_pyinstaller(), pin[0])

    def test_a_repair_release_without_its_own_report_attaches_none_instead_of_mislabelling_an_old_one(self):
        wf = (ROOT / ".github" / "workflows" / "release.yml").read_text(encoding="utf-8")
        self.assertIn("$v -like '1.0.*'", wf)          # only the 1.0.x line may use the frozen 1.0.0 report
        self.assertIn("none attached", wf)
        self.assertNotIn('throw "no published calibration report', wf)

    def test_the_version_is_one_number_everywhere_and_has_its_notes(self):
        import json, re
        v = json.loads((ROOT / "studio" / "src-tauri" / "tauri.conf.json").read_text(encoding="utf-8"))["version"]
        self.assertRegex((ROOT / "studio" / "src-tauri" / "Cargo.toml").read_text(encoding="utf-8"), r'(?m)^version = "%s"' % re.escape(v))
        self.assertRegex((ROOT / "studio" / "src-tauri" / "Cargo.lock").read_text(encoding="utf-8"), r'name = "fm-skin-studio"\r?\nversion = "%s"' % re.escape(v))
        self.assertTrue((ROOT / "docs" / ("RELEASE-NOTES-%s.md" % v)).is_file())

    def test_the_freeze_collects_what_the_picture_codecs_read_at_run_time_and_the_release_runs_the_selftest(self):
        for needle in ('"--collect-all", "archspec"', '"--collect-all", "astc_encoder"', '"--collect-all", "UnityPy"'):
            self.assertIn(needle, FREEZE)
        wf = (ROOT / ".github" / "workflows" / "release.yml").read_text(encoding="utf-8")
        self.assertIn("fm-skin-engine.exe --selftest", wf)
        self.assertLess(wf.index("freeze_engine.py"), wf.index("--selftest"), "the selftest runs after the freeze")
        self.assertLess(wf.index("--selftest"), wf.index("Build, sign and publish"), "and before the installer is built")


if __name__ == "__main__":
    unittest.main()
