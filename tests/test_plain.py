"""S1 of the Simple mode plan: every reason the engine can give has a sentence in plain words (skin_editor/plain.py)."""
import ast
import json
import unittest
from pathlib import Path

from skin_editor import plain
from skin_editor.api import rpc

ROOT = Path(__file__).resolve().parent.parent
MODULES = ("engine.py", "install.py", "native.py", "detect.py")
# raises whose text is built elsewhere or carried as structured data; they are mapped by their error code or by the message they were built from
STRUCTURED = {("engine.py", "PlacementRefused"), ("install.py", "InstallError")}


def raised_texts():
    out = []
    for f in MODULES:
        tree = ast.parse((ROOT / "skin_editor" / f).read_text(encoding="utf-8"))
        for n in ast.walk(tree):
            if isinstance(n, ast.Raise) and isinstance(n.exc, ast.Call) and n.exc.args:
                text = "".join(x.value for x in ast.walk(n.exc.args[0]) if isinstance(x, ast.Constant) and isinstance(x.value, str))
                out.append((f, n.lineno, getattr(n.exc.func, "id", getattr(n.exc.func, "attr", "?")), text))
    return out


class PlainWords(unittest.TestCase):
    def test_every_raise_in_the_user_facing_modules_has_a_specific_sentence(self):
        sites = raised_texts()
        self.assertGreater(len(sites), 60, "the scan found the raise sites")
        missing = [(f, ln, kind, t) for f, ln, kind, t in sites if t.strip() and not plain.match(t)]
        self.assertEqual(missing, [], "reasons without a plain sentence (add a rule to skin_editor/plain.py)")
        empty = [(f, ln, kind) for f, ln, kind, t in sites if not t.strip()]
        for f, ln, kind in empty:
            self.assertIn((f, kind), STRUCTURED, "%s:%d raises %s with no text: map it by code or add it to STRUCTURED with a reason" % (f, ln, kind))

    def test_the_sentences_are_plain_and_none_is_empty_or_a_duplicate_of_its_pattern(self):
        for rx, sentence in plain.RULES:
            self.assertGreater(len(sentence), 20, rx)
            self.assertTrue(sentence.endswith((".", "?", "\"")), rx)
            self.assertNotRegex(sentence, r"Traceback|Exception|RuntimeError|KeyError|\bpath_id\b|\bbundle\b.*\bhash\b", rx)

    def test_an_unmatched_message_gets_the_generic_sentence_with_its_own_text_as_details(self):
        r = plain.plain("zzz unheard-of reason")
        self.assertEqual((r["plain"], r["details"]), (plain.GENERIC, "zzz unheard-of reason"))

    def test_every_rpc_error_carries_a_plain_sentence(self):
        from skin_editor import install
        for ex, want in ((install.InstallError("the game is running or updating; close it first"), "Close Football Manager"),
                         (FileNotFoundError("no project named x"), "no project with that name"),
                         (RuntimeError("no style index; take a vanilla snapshot and index first"), "Read the game"),
                         (ValueError("something nobody wrote a sentence for"), plain.GENERIC)):
            e = rpc.error_of(ex)
            self.assertIn(want, e["data"]["plain"])
            self.assertTrue(e["message"], "the raw message stays (the details)")
        from skin_editor.api.schema import SchemaError
        self.assertIn("disagree", rpc.error_of(SchemaError(["x"]))["data"]["plain"])


if __name__ == "__main__":
    unittest.main()
