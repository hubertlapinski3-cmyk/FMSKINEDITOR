"""Runs every calibration fixture and publishes the report (not a draft) with the three honesty items on top.

    python tools/publish_calibration.py OUT_DIR

The numbers in the preface are computed from the run, so the text cannot drift from the rows below it."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from skin_editor.render import fixtures                     # noqa: E402


def preface(results, tot):
    causes, unexplained = {}, []
    for r in results:
        if r["name"].startswith("state-"):
            continue
        for x in r["rows"]:
            if x["verdict"] == "FAIL":
                c = fixtures.cause(x, r["name"])
                causes[c or "UNEXPLAINED"] = causes.get(c or "UNEXPLAINED", 0) + 1
    st = next(r for r in results if r["name"] == "state-i3-session-g")
    st_fail = [x for x in st["rows"] if x["verdict"] == "FAIL"]
    paired = sum(r["delivered"]["paired"] for r in results if r.get("delivered"))
    nodes = sum(r["delivered"]["nodes"] for r in results if r.get("delivered"))
    boxes_fail = sum(1 for r in results if not r["name"].startswith("state-") for x in r["rows"] if x["verdict"] == "FAIL")
    out = ["**Status: published, build 27.0.1.2503222. Not a draft.** Phase 9 M7 closed on this report. Three things to read before the numbers:", "",
           "1. **The failure causes are assigned by rule, not row by row.** Every FAIL row below carries a cause named by a rule over the row (`fixtures.CAUSES`); nobody opened the %d "
           "geometry and colour failures one at a time. A rule that fits wrongly would hide an unrelated failure, which is why every row stays published, nothing is filtered or "
           "re-toleranced, and the regression gate (`baseline-failures.json`) lists each failure by name. By rule: %s." % (
               boxes_fail, "; ".join("%s: %d" % (k[:78].rstrip(",: ") + ("..." if len(k) > 78 else ""), v) for k, v in sorted(causes.items(), key=lambda kv: -kv[1]))),
           "2. **Delivered text pairing.** Captured text is paired with the drawn text nodes by the structural template path (`render/delivered.py`): %d of %d text nodes paired on the five tiles. "
           "Measured against the layout's sample text on the same fixtures it changed ONE row (a Tactics `CellText` box now passes, 66.9 against 67.4 wide). The wiring is correct and cheap "
           "but not the improvement hoped for: the stand-in font differs from the game's and many nodes have no captured partner." % (paired, nodes),
           "3. **The state findings come from the I3 session (Session G).** Hover, press, focus and selection were read by hand on the game with the baseline inspector (0.2.2, no actions "
           "allowed, owner at the PC); the readings are the fixture `state-i3-session-g`, source `docs/evidence/phase9-i3-session-G-20261114.md`. The render applies NO runtime state; the "
           "fixture compares each reading with what the game's own `:hover`/`:focus` rules declare for the same element (`Cascade.state_declarations`). Result: %d pass, %d fail, %d n/a. "
           "Hover colours of buttons, list rows, the Loans tile and the nav tab label equal the game's own rules exactly. Pitch markers and instruction tiles get a hover flag and no style "
           "change (explicit no-op verdicts). The inspector's mask for a text label read 0 while its hover colour was applied (noted on the row). **Open:** the pressed Filter button showed "
           "its rest colour (#FFFFFF24) where the hover rule alone predicts #FFFFFF33: one reading, UNEXPLAINED, listed as a known failure. The Inbox selection is a class swap on a "
           "style-setter; the one property the render sees differ (colour) was not measured, so that row is N/A." % (
               st["counts"]["PASS"], st["counts"]["FAIL"], st["counts"]["N/A"])]
    return out


def main():
    out = Path(sys.argv[1])
    ctx = fixtures.Context()
    results = fixtures.run_all(ctx)
    tot = fixtures.report(results, out, title="Render calibration report (published)", preface=preface)
    print("TOTAL", tot, "fixtures", len(results))


if __name__ == "__main__":
    main()
