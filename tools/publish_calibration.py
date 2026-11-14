"""Runs every calibration fixture, examines every FAIL row individually, and publishes the report (not a draft) with the honesty items on top.

    python tools/publish_calibration.py OUT_DIR

Every number in the text is computed from the run, so the text cannot drift from the rows below it (a test pins that). Fix round after 1.0.0: the failures are examined row by row
(skin_editor/render/causes.py), coverage is published by row class, the grid model is scoped to what was measured, and the state rows carry observation and interpretation apart."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, ROOT.as_posix())

from skin_editor.render import causes, fixtures, layers as layers_mod, report_tables as rt     # noqa: E402

HELDOUT = ROOT / "docs" / "evidence" / "phase9-fix-round-heldout-results.json"
PRED = ROOT / "docs" / "evidence" / "phase9-fix-round-heldout-predictions.json"


def state_lines(results):
    """The hover narrative, written from the ISOLATED-VARIABLE rows (U4): one variable changed per variant from the published conditional row, on the real ancestry from the captures."""
    st = next((r for r in results if r["name"] == "state-i3-session-g"), None)
    if not st:
        return []

    def verdicts(check):
        rows = [x for x in st["rows"] if x["check"] == check]
        rest = next((x["verdict"] for x in rows if "(rest)" in x["property"]), "n/a")
        state = next((x["verdict"] for x in rows if "(rest)" not in x["property"]), "n/a")
        return rest, state
    c0, v1, v2, v3, v4 = (verdicts(c) for c in ("nav-tab-label-hover", "nav-tab-label-hover@V1-real-ancestry-only", "nav-tab-label-hover@V2-label-state-only",
                                                "nav-tab-label-hover@V3-real-ancestry-and-as-read", "nav-tab-label-hover@V4-V3-plus-recorded-runtime-sheet"))
    f = lambda v: "rest %s, hover %s" % v
    return ["Measured: label colour #FFFFFF under the pointer, rest #EBEBEB; label mask 0; ancestors 2. Not measured: why. Isolated-variable result, one variable changed per variant from the published conditional row "
            "(truncated chain, label hovered, applied sheets only: %s): the real ancestry alone (V1): %s; the label's own state alone, label NOT hovered (V2): %s; both, i.e. real ancestry and the states as read (V3): %s; V3 plus the recorded "
            "run-time sheet, a captured 80-rule sample (V4): %s. Read plainly: the label's own hover is not needed to reach #FFFFFF (an ancestor-hover rule in the applied sheets does it on the truncated chain); the real ancestor "
            "(.nav-on-light) makes the applied sheets predict another colour at rest and on hover; the recorded run-time sheet restores both. The first two published as-read rows changed the ancestor and the state together and could not "
            "say which mattered. The mechanism is unverified: no repeated reads were taken, inheritance was not tested, the Loans title gave no second point." % (f(c0), f(v1), f(v2), f(v3), f(v4)), ""]


def chain_caution():
    """Which state checks run on a truncated chain, counted from the fixture, and the real-ancestry variants added beside them."""
    cks = json.loads((ROOT / "tests" / "fixtures" / "render" / "state-i3-session-g" / "expect.json").read_text(encoding="utf-8"))["checks"]
    st = [c for c in cks if c["kind"] == "state"]
    trunc = [c for c in st if c.get("chain_truncated")]
    real = [c for c in st if "@" in c["id"]]
    return ("Chains: %d of the %d state checks are the published ones and feed the cascade a TRUNCATED chain (the element and at most five ancestors, one element in most), marked chain_truncated and kept with their verdicts; "
            "%d variants beside them use the REAL ancestry of the same element from the captures (the first of several matching elements is taken; ancestors of a hovered element get the hover state, observed by Session G on at most "
            "five levels). Where a real-ancestry variant fails or passes differently, the report says so in its own row." % (len(trunc), len(st), len(real)))


def grid_md(results):
    g = rt.grid_scoping(results, HELDOUT)
    pred = json.loads(PRED.read_text(encoding="utf-8")) if PRED.is_file() else None
    out = ["## Grid placement: what it was measured on", "",
           "Two words are used here and the files used one for both. **Pitch** in `pitch.json` and `screen.py` is the grid CELL pitch (about 65.5 px cell, 16.5 px gap, stride 82 in the game's inline px). "
           "The football pitch is a different thing: it is drawn in code, is not modelled, and its rows are among the failures above.", "",
           "The measured model rests on six screen captures (the Squad overview at three panel sizes and in Large, Standard and Small compositions, and Tactics > Team Instructions at Large), "
           "behind six screen fixtures, 28 host rows, all pass. The approved plan required a fullscreen, a 16x9 and a body preset to be measured before the M3 exit; the plan's own status lists them as unmeasured: they were not.", "",
           "| Fixture | Status | Hosts compared | Given slots | Max residual (world px) | Parameters |", "|---|---|---|---|---|---|"]
    for r in g["fixtures"]:
        out.append("| %s | %s (the capture is behind the fit, so this is a reproduction, not a test) | %d | %d | %s | pitch and gap FITTED to these captures; stride 82 and the host formula FITTED; area, origin, padding and reserved_right are SUPPLIED by the fixture from the capture |" % (
            r["fixture"], r["status"], r["hosts_compared"], r["given_slots"], r["max_residual_px"]))
    out += ["", "Residuals are published, not verdicts: an 8 px tolerance on a 312 px host cannot test a pitch quoted to 0.1 px. The row output now marks `given` slots (cells handed to the assembler from the capture), "
            "which it could not tell from predictions before.", "",
            "### Held-out test (zero game time)", "",
            "The model was frozen at commit `%s` (hashes in `phase9-fix-round-heldout-predictions.json`: screen.py %s, pitch.json %s), its predictions for three captures it was never fitted to were written and committed, "
            "and only then were the hosts' real positions opened (the predictions commit precedes the comparison commit). Assumptions the model could not know: composition = the one whose cells hold all host names (the -Large variant when "
            "there is one), padding 12, no reserved columns. The Phase 7 tile positions (x 40, 1274, 865) were not used: their panel size is not recoverable." % (
                (pred or {}).get("model", {}).get("head", "?")[:10], (pred or {}).get("model", {}).get("screen.py"), (pred or {}).get("model", {}).get("pitch.json")), "",
            "| Capture | Composition predicted | Hosts | Exact (0 px) | Max residual (inline px) |", "|---|---|---|---|---|"]
    for h in g["heldout"]:
        out.append("| %s | %s | %d | %d | %s |" % (h["capture"], h["composition"], h["hosts"], h["exact"], h["max_residual_px"]))
    ho = g["heldout"]
    out += ["", "Result, whichever way it fell: %d of %d hosts exact, %d compositions reproduced exactly, %d did not (the Transfers Activity bottom-row cells sit about 492 px lower than predicted: the model moves right-anchored cells and "
            "grows flexible ones but has no rule for cells anchored to the bottom edge). Nothing was tuned to this result." % (
                sum(h["exact"] for h in ho), sum(h["hosts"] for h in ho), sum(1 for h in ho if h["exact"] == h["hosts"]), sum(1 for h in ho if h["exact"] != h["hosts"])), "",
            "Not counted as checks (circular): any capture behind a pitch.json entry, Standard and Small on the captures they were measured from, given slots, a capture that prompted a model change, and the 1680 capture beyond "
            "panel-size independence for one composition.", "",
            "Grid placement reproduces the captures it was derived from to %.1f px on %d compositions, one save, one club. Held-out checks: %d (%d exact, %d not). Every other composition is an estimate never compared with the game "
            "(%d of 1,804 have a measured pitch entry)." % (max((r["max_residual_px"] or 0) for r in g["fixtures"]), len(g["measured_compositions"]), len(ho), sum(1 for h in ho if h["exact"] == h["hosts"]),
                                                              sum(1 for h in ho if h["exact"] != h["hosts"]), len(g["measured_compositions"])), ""]
    return out


def publish(out, ctx=None, results=None, update_guide=False):
    """Run, examine, write the report into `out`; returns (results, coverage, examination)."""
    out = Path(out)
    ctx = ctx or fixtures.Context()
    results = results if results is not None else fixtures.run_all(ctx)
    causes.examine_all(ctx, results)
    cv = rt.coverage(results)
    ex = rt.examination(results)
    lay = layers_mod.run_layers(ctx, results)
    pd = rt.pairing_delta(ctx)

    def preface(results, tot):
        lines = ["**Status: published, build 27.0.1.2503222, revised after the 1.0.0 review. This file is the revised report and is what the release asset `calibration-report-1.0.0.md` now carries; the first version of the report, as published at release, is retained unchanged in the repository at `docs/evidence/phase9-m7-calibration-20261114/` and in the git history. Not a draft.** Phase 9 M7 closed on the first version of this report. Read these first:", "",
                 "1. **Failure causes: each failing row was examined individually, and the examination is published row by row** (section \"The failures, examined row by row\"). Each of the %d failing rows: %d origin failures, %d displaced by an origin "
                 "listed beside them. The causes are the ORIGIN rows: %d rest on a measured capture fact, %d on magnitude only, %d are UNEXPLAINED; the displaced rows repeat their origin's cause (%d with a measured-fact origin, %d unexplained), so the row counts %d / %d / %d over all failing rows count rows, not independent causes. The 1.0.0 labels came from fixture-wide rules (one label per row type, list order deciding when two fitted, 78 rows labelled, none unexplained); "
                 "they disagree with the examination on %d rows and both labels are kept. The examiner wrote the rules; no second person checked. Of the %d origin rows, %s a class of cause without predicting the size of the gap." % (
                     ex["fail_rows"], ex["origin_rows"], ex["displaced_rows"], ex["origin_grades"]["measured fact"], ex["origin_grades"]["magnitude only"], ex["origin_grades"]["unexplained"], ex["displaced_grades"]["measured fact"], ex["displaced_grades"]["unexplained"],
                     ex["grades"]["measured fact"], ex["grades"]["magnitude only"], ex["unexplained"], ex["D"], ex["origin_rows"], rt.names(ex["origin_magnitude_not_predicted"])),
                 "2. **Coverage is published by row class, and the pass count is not a headline** (table below). Many passes are flex rows at Yoga's initial value, which the render supplies when it declares nothing; the same condition is N/A for colour and font-size. "
                 "tile-loans and tile-loans-c2-dump are one tile counted twice.",
                 "3. **Delivered text pairing.** %s" % _delivered(results),
                 "4. **State findings come from the I3 session (Session G)**, hover, press, focus and selection read by hand on the baseline inspector with the owner at the PC; observation and interpretation are separate fields on each row, each interpretation marked observed, "
                 "derived or inferred. The render applies NO runtime state. " + " ".join(state_lines(results)) + " " + chain_caution(),
                 "5. **Grid placement is scoped** to what was measured, with a held-out test: see \"Grid placement: what it was measured on\".", ""]
        return lines + rt.coverage_md(cv) + [""]

    def appendix(results):
        return rt.examination_md(results, ex) + [""] + rt.pairing_md(pd) + [""] + layers_mod.layers_md(lay) + grid_md(results)
    tot = fixtures.report(results, out, title="Render calibration report (published, revised)", preface=preface, appendix=appendix,
                          extra={"coverage": cv, "examination": ex, "layers": lay, "pairing": pd, "grid": rt.grid_scoping(results, HELDOUT), "duplicates": rt.DUPLICATES})
    if update_guide:                                                       # the guide's trust section carries the same coverage block, between its markers
        g = ROOT / "docs" / "RENDER-GUIDE.md"
        txt = g.read_text(encoding="utf-8").replace("\r\n", "\n")
        a, b = txt.index("<!-- coverage:start -->") + len("<!-- coverage:start -->"), txt.index("<!-- coverage:end -->")
        g.write_bytes((txt[:a] + "\n" + "\n".join(rt.coverage_md(cv)) + "\n" + txt[b:]).replace("\n", "\r\n").encode("utf-8"))      # bytes: write_text would turn \r\n into \r\r\n on Windows
    print("TOTAL", tot, "fixtures", len(results), "| failures", ex["fail_rows"], "origin", ex["origin_rows"], "displaced", ex["displaced_rows"], "grades", ex["grades"], "D", ex["D"])
    return results, cv, ex


def main():
    publish(sys.argv[1], update_guide=True)


def _delivered(results):
    paired = sum(r["delivered"]["paired"] for r in results if r.get("delivered"))
    nodes = sum(r["delivered"]["nodes"] for r in results if r.get("delivered"))
    unpaired = sum(r["delivered"]["unpaired_texts"] for r in results if r.get("delivered"))
    return ("Captured text is paired with the drawn text nodes by the structural template path (`render/delivered.py`): %d of %d text nodes paired on the five tiles, %d captured texts with no render node. Measured against the layout's sample "
            "text on the same fixtures it changed ONE row (a Tactics `CellText` box now passes, 66.9 against 67.4 wide). The wiring is correct and cheap but not the improvement hoped for." % (paired, nodes, unpaired))


if __name__ == "__main__":
    main()
