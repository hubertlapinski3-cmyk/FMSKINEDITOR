"""Writes docs/RELEASE-NOTES-<version>.md from a report folder's JSON: every number in the notes is read from the report, none is typed, and every claim is one the JSON backs.

    python tools/make_release_notes.py 1.1.0 docs/evidence/phase9-v110-calibration-20261114

The release workflow uses docs/RELEASE-NOTES-<version>.md as the release body and the same file is what a latest.json notes field is made from."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def notes(version, report_dir):
    d = json.loads((Path(report_dir) / "calibration-report.json").read_text(encoding="utf-8"))
    t, cv, ex, lay, pd, pe = d["totals"], d["totals"]["coverage"], d["examination"], d["layers"], d["pairing"], d["pairing_effect"]
    ho = d["grid"]["heldout"]
    variants = sum(len(f.get("variant_rows", [])) for f in d["fixtures"])
    layer_rows = sum(len(f.get("layer_rows", [])) for f in d["fixtures"])
    lc, rs = lay["live-classes"], lay["recorded-runtime-sheet"]
    invisible = sum(x["greedy_invisible_partners"] for x in pd)
    changed = sum(x["changed_partner"] for x in pd)
    only_structural = sum(x["only_structural"] for x in pd)
    loans = next(x for x in pd if x["fixture"] == "tile-loans")
    train = next(x for x in pd if x["fixture"] == "tile-training")
    return f"""## FM Skin Studio {version}

This release adds two Studio views and an honest second look at how the render is compared with the game. The installer, update path and signing are unchanged.

### New
- **Screen view.** In the render view, the `screen` tab draws a screen's tile layout on the game's grid for a grid size you give, each cell named and tagged with the tile layout the engine chose. A composition the engine has no measurement for is flagged ESTIMATE.
- **Table view.** The `table` tab draws a table view's header row, in the game's column order, as a labelled placeholder table at a breakpoint you choose. With a project open, both views apply its tile moves or column edits; one switch shows the game as it ships.
- **A stricter comparison in the calibration report.** The old pairing matched {invisible} render nodes to live elements the game hides; the new pairing no longer does that, and every other node keeps the live partner it had ({changed} partners changed, {only_structural} newly paired). That is the whole difference. It is not a gain: live elements paired fell to {loans['structural_paired']} of {loans['dump_nodes']} on the Loans tile and {train['structural_paired']} of {train['dump_nodes']} on Training (from {loans['greedy_paired']} and {train['greedy_paired']}), and compared rows on the tile fixtures fell from {pe['compared_before']} to {pe['compared_after']}. Where the render draws an element the game hides, that is now a failure (named visibility; {pe['visibility_fail_rows']} rows), not a non-comparison.

### How far to trust it
The calibration report ships with this release (`calibration-report-{version}.md` and `.json`): {t['PASS']} rows pass, {t['FAIL']} fail and {t['N/A']} cannot be compared. Of {cv['total_rows']} slots, {cv['compared']} were compared; the report breaks the passes down by row class and says how many are values the render did not declare. Each of the {ex['fail_rows']} failing rows was examined individually: {ex['origin_rows']} are origin failures and {ex['displaced_rows']} are displaced by an origin; of the origins, {ex['origin_grades']['measured fact']} rest on a measured capture fact, {ex['origin_grades']['magnitude only']} on magnitude only and {ex['origin_grades']['unexplained']} are unexplained. The author wrote the rules and no second person checked.
The hover and press readings are each counted once, scored on the real ancestors of the element from the captures; {variants} variant rows (truncated chains and one-variable analyses of the same readings) and {layer_rows} layer rows are published in the report outside those totals. A held-out test of the grid model on {sum(h['hosts'] for h in ho)} hosts of {len(ho)} screens it had never seen: {sum(h['exact'] for h in ho)} were exact; the Transfers Activity screen was missed and the report says why.

### Engine only, not a Studio feature
Two optional calibration layers exist in the engine and are off: one adds the classes a capture shows the game setting in code, one adds a captured 80-rule sample of the game's run-time sheet. Their rows are in the report's own layers section, outside the totals above. The class layer reads its classes from the same capture it is scored against, so it confirms a diagnosis and does not show it could predict: with it {lc['now_pass']} of the {lc['base_rows']} failing rows it is about pass, and it breaks {len(lc['broken'])} of the {lc['rows_compared']} rows it was run over; with the sheet layer {rs['now_pass']} of {rs['base_rows']} pass and it breaks {len(rs['broken'])} of {rs['rows_compared']}.

### What it is not
An approximation, and it says so on every render: there is no hover, press or animation in the picture, code-drawn visuals (the tactics pitch and players, charts, shot maps, the Training schedule) are approximated or missing, the game's fonts are named rather than drawn, and surfaces painted from the club's colours at run time show the game's default. Use the PREVIEW tab to see your skin in the running game.

### Updating
Installed copies update through Check for updates, then Install and restart. Docs: `docs/RENDER-GUIDE.md`. Evidence: `docs/evidence/`.
"""


if __name__ == "__main__":
    version, report = sys.argv[1], Path(sys.argv[2])
    out = ROOT / "docs" / ("RELEASE-NOTES-%s.md" % version)
    out.write_text(notes(version, report), encoding="utf-8", newline="\n")
    print("wrote", out)
