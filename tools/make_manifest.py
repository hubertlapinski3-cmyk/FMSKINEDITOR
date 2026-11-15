"""Writes docs/evidence/MANIFEST.sha256: two hashes of every published evidence file.

    python tools/make_manifest.py

  <sha256> *<path>        computed on the line-ending-NORMALISED bytes (CRLF -> LF): the same value on any checkout.
  raw <sha256> *<path>    computed on the file's RAW bytes: it changes if a line ending changes. docs/evidence/** is `-text` in
                          .gitattributes, so git never converts these files and the raw hash is the same on any checkout too.

tests/test_evidence_manifest.py recomputes both. The normalised hash alone cannot see a line-ending change (the 1.0.0 report assets are
compared with the repo files byte for byte, so a change of that kind must fail a test); the raw one can.
The logs of Sessions A, D and E are NOT in the manifest: their recorded hashes were found not to reproduce (docs/evidence/phase9-fix-round-20261114.md)."""
import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FILES = ["docs/evidence/phase9-m7-calibration-20261114/calibration-report.md", "docs/evidence/phase9-m7-calibration-20261114/calibration-report.json",
         "docs/evidence/phase9-m7-calibration-revised-20261114/calibration-report.md", "docs/evidence/phase9-m7-calibration-revised-20261114/calibration-report.json",
         "docs/evidence/phase9-fix-round-heldout-predictions.json", "docs/evidence/phase9-fix-round-heldout-results.json",
         "docs/evidence/phase9-m0-session-B-logs-20261114/LogOutput.log",
         "docs/evidence/phase9-v110-calibration-20261114/calibration-report.md", "docs/evidence/phase9-v110-calibration-20261114/calibration-report.json",
         "docs/evidence/phase9-v110-calibration-20261114/diff-vs-frozen-1.0.0.md", "docs/evidence/phase9-v110-calibration-20261114/ADDENDUM.md",
         "docs/evidence/phase9-v110-grid-vertical-flow-design.json",
         "docs/evidence/phase9-v111-frozen-picture-check-20261115.json",
         "docs/evidence/phase9-v111-installed-engine-check-20261115.json"]


HEADER = [
    "# sha256 of the LF-normalised bytes of each file (so any checkout agrees). Lines starting with # are comments.",
    "# Lines starting with 'raw ' carry the sha256 of the RAW bytes of the same file (added 2026-11-15): they catch a line-ending change the normalised hash cannot see.",
    "# The raw hashes are of the COMMITTED bytes (docs/evidence/** is -text, so any checkout has exactly these bytes). Five older files (the first m7 report, the held-out predictions and results, the Session B log) are stored with LF endings; a Windows checkout made before the attribute existed may hold CRLF copies of them, which fail the raw check: restore them from git (delete, then git checkout). Found 2026-11-15 when CI failed on exactly that.",
    "# Logs, verified 2026-11-14 (committed LogOutput.log, hashed in the LF form and the CRLF form, against the value recorded in the session doc):",
    "#   Session B: recorded 5DB697AC3446F2F9 (6428 bytes) = the CRLF form of the committed file, so it IS listed below (the manifest hashes its LF form).",
    "#   Session D: recorded 65026D7EA79CF637 (10420 bytes); committed LF form D6808D14A7620392 (10332 bytes), CRLF form FF47B09159183B77 (10421 bytes): NOT reproduced, not listed.",
    "#   Session E: recorded FB54E30D779E10AD (8707 bytes); committed LF form 3ED8D7B277D14D71 (8628 bytes), CRLF form 410FFB1F6A4E143E (8708 bytes): NOT reproduced, not listed.",
    "#   Session A: its doc records no LogOutput hash (only the size and time before launch); LF form 249FBF432001D192, CRLF form 78DADFA92BF05648; nothing to compare, not listed.",
    "#   D and E: the recorded size equals the CRLF form minus one byte, but no simple variant (final byte, BOM, whitespace) reproduces the recorded hash.",
]


def digest(path):
    return normalised(Path(path).read_bytes())


def normalised(b):
    return hashlib.sha256(b.replace(b"\r\n", b"\n")).hexdigest()


def raw(b):
    return hashlib.sha256(b).hexdigest()


def parse(text):
    """-> (normalised {path: sha}, raw {path: sha}) from a manifest's text."""
    norm, rw = {}, {}
    for l in text.splitlines():
        if not l.strip() or l.startswith("#"):
            continue
        if l.startswith("raw "):
            want, name = l[4:].split(" *", 1)
            rw[name] = want
        else:
            want, name = l.split(" *", 1)
            norm[name] = want
    return norm, rw


if __name__ == "__main__":
    blobs = {f: (ROOT / f).read_bytes() for f in FILES}
    lines = HEADER + ["%s *%s" % (normalised(blobs[f]), f) for f in FILES] + ["raw %s *%s" % (raw(blobs[f]), f) for f in FILES]
    (ROOT / "docs" / "evidence" / "MANIFEST.sha256").write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    print("\n".join(lines))
