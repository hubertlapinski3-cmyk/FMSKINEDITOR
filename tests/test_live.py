"""Phase 5 live preview: the loop against a fake inspector pipe (a transport function), the static fallback, and the no-bundles guarantee."""
import json, tempfile, unittest
from pathlib import Path
from unittest import mock

from skin_editor import config, inspector, live, project, projfmt
from tests.test_preview import index


class Fake:
    """An inspector: answers by tool name; the screenshot writes its file like the game does (a moment after the reply)."""

    def __init__(self, shots, button=True, actions=True, offline=False):
        self.calls, self.shots, self.button, self.actions, self.offline = [], shots, button, actions, offline

    def __call__(self, line, timeout):
        if self.offline:
            raise inspector.Offline("FM27 is not running with the inspector plugin")
        req = json.loads(line)
        self.calls.append((req["tool"], req["params"]))
        t, p = req["tool"], req["params"]
        if t == "status":
            res = {"result": {"game": "27.0.1", "scene": "Main"}, "ms": 3}
        elif t == "find":
            res = {"result": {"matches": [{"path": "P1/4/9", "label": "SIButton", "text": "Reload Skin"}] if self.button else []}, "ms": 5}
        elif t == "click":
            res = {"result": {"clicked": True}} if self.actions else {"fault": {"kind": "actions_disabled", "detail": "[Inspector] AllowActions is false"}}
        elif t == "screenshot":
            f = self.shots / (p["file"] + ".png"); f.write_bytes(b"\x89PNG fake")
            res = {"result": {"file": str(f), "state": "pending"}, "ms": 9}
        else:
            res = {"fault": {"kind": "unknown_tool", "detail": t}}
        return json.dumps(dict(res, v=1, id=req["id"])).encode()


class Live(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        t = Path(self.tmp.name)
        self.ws = config.Workspace(t / "ws"); self.skins = t / "skins"; self.shots = t / "ui-dumps" / "screens"; self.shots.mkdir(parents=True)
        p = project.new("Mine"); p["options"]["output"] = "native"; p["token_overrides"] = [{"token": "--a", "value": {"rgb": "#112233", "a": 1.0}}]
        projfmt.write(self.ws, p); self.p = projfmt.read(self.ws, "Mine")

    def tearDown(self):
        self.tmp.cleanup()

    def run_live(self, fake, **kw):
        return live.run(self.ws, self.p, index(), None, skins_root=self.skins, transport=fake, sleep=lambda s: None, **kw)

    def test_full_loop(self):
        fake = Fake(self.shots)
        r = self.run_live(fake)
        self.assertEqual((r["mode"], r["skin_id"], r["reloaded"]), ("live", "Mine-preview", True))
        self.assertTrue((self.skins / "Mine-preview" / "skin.json").is_file())
        self.assertEqual([c[0] for c in fake.calls], ["status", "find", "click", "screenshot"])
        self.assertEqual(fake.calls[2][1], {"path": "P1/4/9", "expect": "Reload"})
        self.assertTrue(Path(r["screenshot"]).is_file()); self.assertTrue(Path(r["screenshot"]).name.startswith("Mine-preview-"))
        self.assertIn("screenshot", " ".join(r["steps"]))

    def test_game_not_running_falls_back_to_static_and_says_why(self):
        r = self.run_live(Fake(self.shots, offline=True))
        self.assertEqual(r["mode"], "static"); self.assertIn("not running", r["reason"])
        self.assertTrue((self.skins / "Mine-preview" / "skin.json").is_file())               # the native skin is still written

    def test_no_button_or_actions_disabled_still_screenshots_with_a_note(self):
        r = self.run_live(Fake(self.shots, button=False))
        self.assertEqual((r["mode"], r["reloaded"]), ("live", False)); self.assertIn("Reload Skin", r["reload_note"])
        r = self.run_live(Fake(self.shots, actions=False))
        self.assertEqual((r["mode"], r["reloaded"]), ("live", False)); self.assertIn("AllowActions", r["reload_note"])

    def test_missing_screenshot_file_degrades(self):
        fake = Fake(self.shots)
        with mock.patch.object(Path, "is_file", lambda self_: False if self_.suffix == ".png" else Path.exists(self_) and not self_.is_dir()):
            r = self.run_live(fake, shot_wait=0.01)
        self.assertEqual(r["mode"], "static"); self.assertIn("did not write", r["reason"])

    def test_never_touches_bundles(self):
        from skin_editor import patcher, install
        with mock.patch.object(patcher, "build", side_effect=AssertionError("bundle build")), mock.patch.object(install, "install", side_effect=AssertionError("install")):
            self.run_live(Fake(self.shots))

    def test_client_reports_faults_and_offline(self):
        with self.assertRaises(inspector.Offline): inspector.call("status", transport=Fake(self.shots, offline=True))
        with self.assertRaises(inspector.Fault) as c: inspector.call("nope", transport=Fake(self.shots))
        self.assertEqual(c.exception.kind, "unknown_tool")
        def junk(line, timeout): return b"not json"
        with self.assertRaises(inspector.Offline): inspector.call("status", transport=junk)
        with mock.patch.object(inspector, "os", mock.Mock(name="nt")) as m:
            m.name = "posix"
            with self.assertRaises(inspector.Offline) as c: inspector.call("status")
            self.assertIn("Windows", str(c.exception))

    def test_real_pipe_is_offline_when_the_game_is_not_running(self):
        import os
        if os.name != "nt" or "fm27-crimson-inspector" in os.listdir("\\\\.\\pipe\\"):
            self.skipTest("needs Windows with FM27 closed")
        with self.assertRaises(inspector.Offline) as c: inspector.status()
        self.assertIn("not running", str(c.exception))


class AtomicExport(unittest.TestCase):
    def test_a_failed_export_leaves_the_existing_skin_untouched(self):
        from skin_editor import native
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            ws = config.Workspace(Path(tmp) / "ws"); root = Path(tmp) / "skins"; root.mkdir()
            p = project.new("A"); p["token_overrides"] = [{"token": "--a", "value": {"rgb": "#112233", "a": 1.0}}]; projfmt.write(ws, p)
            rep = native.export(ws, projfmt.read(ws, "A"), index(), None, root, "A")
            before = {f.name: f.read_bytes() for f in (root / "A").iterdir() if f.is_file()}
            self.assertEqual(rep["folder"], str(root / "A")); self.assertIn(str(root / "A"), (root / "A" / ".fm27se-export.json").read_text().replace("\\\\", "\\"))
            with mock.patch.object(native, "validate", side_effect=RuntimeError("boom")):
                with self.assertRaises(RuntimeError): native.export(ws, projfmt.read(ws, "A"), index(), None, root, "A")
            self.assertEqual({f.name: f.read_bytes() for f in (root / "A").iterdir() if f.is_file()}, before)
            self.assertEqual([x.name for x in root.iterdir()], ["A"])                                                  # no temp folder left
