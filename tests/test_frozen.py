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
    return subprocess.run([sys.executable, "-c", textwrap.dedent(code)], cwd=str(ROOT), capture_output=True, text=True, timeout=120, env={"PYTHONPATH": str(ROOT), "SYSTEMROOT": __import__("os").environ.get("SYSTEMROOT", "")})


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

    def test_every_frozen_build_runs_the_selftest_not_only_the_release_workflow(self):
        self.assertIn('"--selftest"', FREEZE)
        self.assertLess(FREEZE.index("--collect-all"), FREEZE.index('"--selftest"'))
        self.assertIn("return st.returncode", FREEZE)

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
