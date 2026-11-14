"""Writes docs/evidence/MANIFEST.sha256: the sha256 of the published report files, computed on their line-ending-normalised bytes (LF), so the value is the same on any checkout.

    python tools/make_manifest.py

tests/test_evidence_manifest.py recomputes them. The logs of Sessions A, D and E are NOT in the manifest: their recorded hashes were found not to reproduce (docs/evidence/phase9-fix-round-20261114.md)."""
import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FILES = ["docs/evidence/phase9-m7-calibration-20261114/calibration-report.md", "docs/evidence/phase9-m7-calibration-20261114/calibration-report.json",
         "docs/evidence/phase9-m7-calibration-revised-20261114/calibration-report.md", "docs/evidence/phase9-m7-calibration-revised-20261114/calibration-report.json",
         "docs/evidence/phase9-fix-round-heldout-predictions.json", "docs/evidence/phase9-fix-round-heldout-results.json",
         "docs/evidence/phase9-m0-session-B-logs-20261114/LogOutput.log"]


HEADER = [
    "# sha256 of the LF-normalised bytes of each file (so any checkout agrees). Lines starting with # are comments.",
    "# Logs, verified 2026-11-14 (committed LogOutput.log, hashed in the LF form and the CRLF form, against the value recorded in the session doc):",
    "#   Session B: recorded 5DB697AC3446F2F9 (6428 bytes) = the CRLF form of the committed file, so it IS listed below (the manifest hashes its LF form).",
    "#   Session D: recorded 65026D7EA79CF637 (10420 bytes); committed LF form D6808D14A7620392 (10332 bytes), CRLF form FF47B09159183B77 (10421 bytes): NOT reproduced, not listed.",
    "#   Session E: recorded FB54E30D779E10AD (8707 bytes); committed LF form 3ED8D7B277D14D71 (8628 bytes), CRLF form 410FFB1F6A4E143E (8708 bytes): NOT reproduced, not listed.",
    "#   Session A: its doc records no LogOutput hash (only the size and time before launch); LF form 249FBF432001D192, CRLF form 78DADFA92BF05648; nothing to compare, not listed.",
    "#   D and E: the recorded size equals the CRLF form minus one byte, but no simple variant (final byte, BOM, whitespace) reproduces the recorded hash.",
]


def digest(path):
    return hashlib.sha256(Path(path).read_bytes().replace(b"\r\n", b"\n")).hexdigest()


if __name__ == "__main__":
    lines = HEADER + ["%s *%s" % (digest(ROOT / f), f) for f in FILES]
    (ROOT / "docs" / "evidence" / "MANIFEST.sha256").write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    print("\n".join(lines))