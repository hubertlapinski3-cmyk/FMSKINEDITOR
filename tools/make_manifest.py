"""Writes docs/evidence/MANIFEST.sha256: the sha256 of the published report files, computed on their line-ending-normalised bytes (LF), so the value is the same on any checkout.

    python tools/make_manifest.py

tests/test_evidence_manifest.py recomputes them. The logs of Sessions A, D and E are NOT in the manifest: their recorded hashes were found not to reproduce (docs/evidence/phase9-fix-round-20261114.md)."""
import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FILES = ["docs/evidence/phase9-m7-calibration-20261114/calibration-report.md", "docs/evidence/phase9-m7-calibration-20261114/calibration-report.json",
         "docs/evidence/phase9-m7-calibration-revised-20261114/calibration-report.md", "docs/evidence/phase9-m7-calibration-revised-20261114/calibration-report.json",
         "docs/evidence/phase9-fix-round-heldout-predictions.json", "docs/evidence/phase9-fix-round-heldout-results.json"]


def digest(path):
    return hashlib.sha256(Path(path).read_bytes().replace(b"\r\n", b"\n")).hexdigest()


if __name__ == "__main__":
    lines = ["%s *%s" % (digest(ROOT / f), f) for f in FILES]
    (ROOT / "docs" / "evidence" / "MANIFEST.sha256").write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    print("\n".join(lines))