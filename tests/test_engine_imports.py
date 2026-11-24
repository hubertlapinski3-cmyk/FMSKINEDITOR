"""E2E1: every `from . import name` inside the engine resolves to a real submodule or attribute. build.session had `from . import build5g, compositionset` (compositionset is in
skin_editor.render) and no test ever ran that method through the engine, so the first real run through the app's RPCs found it."""
import ast
import importlib
import unittest
from pathlib import Path

ENGINE = Path(__file__).resolve().parent.parent / "skin_editor" / "engine.py"


class EngineImports(unittest.TestCase):
    def test_every_relative_import_in_the_engine_resolves(self):
        tree = ast.parse(ENGINE.read_text(encoding="utf-8"))
        bad = []
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.level == 1:
                base = "skin_editor" + ("." + node.module if node.module else "")
                mod = importlib.import_module(base)
                for a in node.names:
                    if not hasattr(mod, a.name):
                        try:
                            importlib.import_module(base + "." + a.name)
                        except ImportError:
                            bad.append("line %d: from .%s import %s" % (node.lineno, node.module or "", a.name))
        self.assertEqual(bad, [])


if __name__ == "__main__":
    unittest.main()
