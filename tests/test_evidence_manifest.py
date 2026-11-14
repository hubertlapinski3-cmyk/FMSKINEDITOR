"""The evidence hash manifest (docs/evidence/MANIFEST.sha256) still matches the published report files (line endings normalised, so any checkout agrees)."""
import hashlib
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MANIFEST = ROOT / "docs" / "evidence" / "MANIFEST.sha256"


class Manifest(unittest.TestCase):
    def test_every_listed_file_hashes_to_its_recorded_value(self):
        self.assertTrue(MANIFEST.is_file(), "run tools/make_manifest.py")
        lines = [l for l in MANIFEST.read_text(encoding="utf-8").splitlines() if l.strip() and not l.startswith("#")]
        self.assertGreater(len(lines), 0)
        for l in lines:
            want, name = l.split(" *", 1)
            got = hashlib.sha256((ROOT / name).read_bytes().replace(b"\r\n", b"\n")).hexdigest()
            self.assertEqual(got, want, name)


if __name__ == "__main__":
    unittest.main()