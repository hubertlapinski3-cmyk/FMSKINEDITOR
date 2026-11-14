"""Prepares a corrected latest.json for the owner's web-UI swap on a release: ONLY the `notes` field changes, every other byte of the live asset stays.

    python tools/make_latest_json.py OUT_FILE [--report DIR]

The notes are the live notes with the "Know how far to trust it" bullet rewritten from the report JSON's totals (none typed). The script fetches the live asset, replaces the notes value
in the raw text (no re-serialisation), then verifies: the text before and after the notes value is byte-identical, and every parsed field except `notes` is equal."""
import json
import re
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
URL = "https://github.com/hubertlapinski3-cmyk/FMSKINEDITOR/releases/latest/download/latest.json"


def build(report_dir, live_bytes):
    txt = live_bytes.decode("utf-8")
    m = re.search(r'"notes"\s*:\s*"((?:[^"\\]|\\.)*)"', txt)
    old = json.loads('"' + m.group(1) + '"')
    t = json.loads((Path(report_dir) / "calibration-report.json").read_text(encoding="utf-8"))["totals"]
    bullet = re.search(r"^- \*\*Know how far to trust it\.\*\*.*$", old, re.M)
    new_bullet = ("- **Know how far to trust it.** The calibration report ships with this release (`calibration-report-1.0.0.md` and `.json`, attached below): every comparison against measurements taken in the game, "
                  "%d passing, %d failing, %d not comparable. Every failing row was examined individually and carries a cause, a grade or the label UNEXPLAINED, and coverage is broken down by row class. "
                  "(Revised on 2026-11-14 after a review: no published row changed, 5 rows were added; the first version of the report is kept in the repository.)" % (t["PASS"], t["FAIL"], t["N/A"]))
    new = old[:bullet.start()] + new_bullet + old[bullet.end():]
    out = txt[:m.start(1)] + json.dumps(new, ensure_ascii=False)[1:-1] + txt[m.end(1):]
    return txt, out, old, new, m


def verify(txt, out, m):
    new_m = re.search(r'"notes"\s*:\s*"((?:[^"\\]|\\.)*)"', out)
    assert txt[:m.start(1)] == out[:new_m.start(1)], "bytes before the notes value changed"
    assert txt[m.end(1):] == out[new_m.end(1):], "bytes after the notes value changed"
    a, b = json.loads(txt), json.loads(out)
    a.pop("notes"), b.pop("notes")
    assert a == b, "a field other than notes differs"
    return sorted(a)


if __name__ == "__main__":
    out_file = Path(sys.argv[1])
    report = Path(sys.argv[sys.argv.index("--report") + 1]) if "--report" in sys.argv else ROOT / "docs" / "evidence" / "phase9-m7-calibration-revised-20261114"
    live = urllib.request.urlopen(urllib.request.Request(URL, headers={"User-Agent": "fm-latest-json-prep"})).read()
    txt, out, old, new, m = build(report, live)
    fields = verify(txt, out, m)
    out_file.write_bytes(out.encode("utf-8"))
    print("wrote", out_file, len(out.encode("utf-8")), "bytes (live", len(live), ")")
    print("fields identical apart from notes:", fields)
    print("notes now mention:", re.search(r"\d+ passing, \d+ failing, \d+ not comparable", new).group(0))
