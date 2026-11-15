"""The evidence hash manifest (docs/evidence/MANIFEST.sha256) still matches the published files: the line-ending-normalised hash (any checkout agrees) AND the raw-bytes hash (a changed line ending fails)."""
import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MANIFEST = ROOT / "docs" / "evidence" / "MANIFEST.sha256"
_spec = importlib.util.spec_from_file_location("make_manifest", ROOT / "tools" / "make_manifest.py")
mm = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(mm)


class Manifest(unittest.TestCase):
    def setUp(self):
        self.assertTrue(MANIFEST.is_file(), "run tools/make_manifest.py")
        self.norm, self.raw = mm.parse(MANIFEST.read_text(encoding="utf-8"))

    def test_every_listed_file_hashes_to_its_recorded_normalised_value(self):
        self.assertGreater(len(self.norm), 0)
        for name, want in self.norm.items():
            self.assertEqual(mm.normalised((ROOT / name).read_bytes()), want, name)

    def test_every_listed_file_hashes_to_its_recorded_raw_value(self):
        for name, want in self.raw.items():
            self.assertEqual(mm.raw((ROOT / name).read_bytes()), want, "raw bytes changed (a line ending?): " + name)

    def test_every_normalised_entry_has_a_raw_entry_and_the_tool_lists_the_same_files(self):
        self.assertEqual(set(self.norm), set(self.raw))
        self.assertEqual(set(self.norm), set(mm.FILES))

    def test_the_raw_hash_sees_a_line_ending_change_the_normalised_one_cannot(self):
        lf, crlf = b"a\nb\n", b"a\r\nb\r\n"
        self.assertEqual(mm.normalised(lf), mm.normalised(crlf))
        self.assertNotEqual(mm.raw(lf), mm.raw(crlf))


if __name__ == "__main__":
    unittest.main()
