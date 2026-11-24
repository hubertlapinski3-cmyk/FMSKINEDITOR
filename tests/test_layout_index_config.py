"""The layout index is built by FM27_LayoutMCP, a developer-only tool that is not shipped. The engine must not
carry a machine-specific path for it: the path comes from the call, the environment, or config.json, and when
there is none the refusal says so in plain words.

The live workspace config.json is READ by these tests, never written: its hash is asserted unchanged around every
case, so a resolution bug can never quietly rewrite the owner's settings."""
import hashlib
import os
import tempfile
import unittest
from pathlib import Path

from skin_editor import config, engine


def _live_config():
    return Path(config.default_workspace()) / "config.json"


def _sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None


class LayoutIndexPath(unittest.TestCase):
    def setUp(self):
        self._env = {k: os.environ.pop(k, None) for k in (engine.LAYOUT_INDEX_ENV, engine.LAYOUT_AREAS_ENV)}
        self.live_config = _live_config()
        self.before = _sha(self.live_config)

    def tearDown(self):
        for k, v in self._env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        self.assertEqual(_sha(self.live_config), self.before,
                         "the live workspace config.json changed during a read-only layout-index test")

    def test_absent_is_refused_in_plain_words(self):
        with self.assertRaises(RuntimeError) as e:
            engine.resolve_layout_index({})
        msg = str(e.exception)
        self.assertIn(engine.LAYOUT_INDEX_ENV, msg)
        self.assertIn("developer-only", msg)
        self.assertIn("does not ship", msg)

    def test_config_json_value_is_used(self):
        with tempfile.TemporaryDirectory() as d:
            index = Path(d) / "layout-vanilla.sqlite"
            index.write_bytes(b"")
            self.assertEqual(engine.resolve_layout_index({"layout_index": str(index)}), str(index))

    def test_environment_wins_over_config(self):
        with tempfile.TemporaryDirectory() as d:
            env_index = Path(d) / "env.sqlite"
            env_index.write_bytes(b"")
            os.environ[engine.LAYOUT_INDEX_ENV] = str(env_index)
            self.assertEqual(engine.resolve_layout_index({"layout_index": str(Path(d) / "cfg.sqlite")}), str(env_index))

    def test_missing_file_names_the_path_and_the_tool(self):
        with self.assertRaises(RuntimeError) as e:
            engine.resolve_layout_index({"layout_index": "C:/nowhere/layout-vanilla.sqlite"})
        msg = str(e.exception)
        self.assertIn("nowhere", msg)
        self.assertIn("developer-only", msg)

    def test_areas_are_optional(self):
        self.assertIsNone(engine.resolve_layout_areas({}))

    def test_state_reports_not_configured_and_never_writes_the_config(self):
        state = engine.layout_index_state({})
        self.assertFalse(state["configured"])
        self.assertIsNone(state["source"])
        self.assertIn("developer-only", state["help"])

    def test_state_reports_the_source_and_presence(self):
        with tempfile.TemporaryDirectory() as d:
            index = Path(d) / "layout-vanilla.sqlite"
            index.write_bytes(b"")
            state = engine.layout_index_state({"layout_index": str(index)})
            self.assertTrue(state["configured"])
            self.assertEqual(state["source"], "config")
            self.assertIsNone(state["help"])


if __name__ == "__main__":
    unittest.main()
