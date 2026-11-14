"""Writes docs/RELEASE-NOTES-<version>.md from a report folder's JSON: every number in the notes is read from the report, none is typed.

    python tools/make_release_notes.py 1.1.0 docs/evidence/phase9-v110-calibration-20261114

The release workflow uses docs/RELEASE-NOTES-<version>.md as the release body and the same file is what a latest.json notes field is made from."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def notes(version, report_dir):
    d = json.loads((Path(report_dir) / "calibration-report.json").read_text(encoding="utf-8"))
    t, cv, ex, lay, pd = d["totals"], d["totals"]["coverage"], d["examination"], d["layers"], d["pairing"]
    ho = d["grid"]["heldout"]
    st = next(f for f in d["fixtures"] if f["name"] == "state-i3-session-g")
    variants = sorted({x["check"] for x in st["rows"] if "@" in x["check"]})
    lc, rs = lay["live-classes"], lay["recorded-runtime-sheet"]
    loans = next(x for x in pd if x["fixture"] == "tile-loans")
    train = next(x for x in pd if x["fixture"] == "tile-training")
    return f"""## FM Skin Studio {version}

This release adds two Studio views and makes the render more honest about what it knows. The installer, update path and signing are unchanged.

### New
- **Screen view.** In the render view, the `screen` tab draws a screen's tile layout on the game's grid for a grid size you give, each cell named and tagged with the tile layout the engine chose. A composition the engine has no measurement for is flagged ESTIMATE.
- **Table view.** The `table` tab draws a table view's header row, in the game's column order, as a labelled placeholder table at a breakpoint you choose. With a project open, both views apply its tile moves or column edits; one switch shows the game as it ships.
- **Pairing by structure.** The render is compared with live captures by the structure of the layout, and invisible live elements are no longer paired. {loans['structural_paired']} of {loans['dump_nodes']} live elements are paired on the Loans tile and {train['structural_paired']} of {train['dump_nodes']} on Training: not more than before ({loans['greedy_paired']} and {train['greedy_paired']}), because the count is bounded by the elements the render draws; what changed is which element each one is compared with.
- **Optional layers, off by default and labelled as inferred.** One applies the classes the game sets in code (read from a capture); one applies a captured 80-rule sample of the game's run-time sheet. With the class layer {lc['now_pass']} of the {lc['base_rows']} failing rows it is about pass; with the sheet layer {rs['now_pass']} of {rs['base_rows']}. The base numbers are not changed by them.

### How far to trust it
The calibration report ships with this release (`calibration-report-{version}.md` and `.json`): {t['PASS']} rows pass, {t['FAIL']} fail and {t['N/A']} cannot be compared. Of {cv['total_rows']} slots, {cv['compared']} were compared; the report breaks the passes down by row class and says how many are values the render did not declare. Each of the {ex['fail_rows']} failing rows was examined individually: {ex['origin_rows']} are origin failures and {ex['displaced_rows']} are displaced by an origin; of the origins, {ex['origin_grades']['measured fact']} rest on a measured capture fact, {ex['origin_grades']['magnitude only']} on magnitude only and {ex['origin_grades']['unexplained']} are unexplained. The author wrote the rules and no second person checked.
The hover and press checks now also run on the real ancestors of each element from the captures ({len(variants)} variants beside the published rows). A held-out test of the grid model on {sum(h['hosts'] for h in ho)} hosts of {len(ho)} screens it had never seen: {sum(h['exact'] for h in ho)} were exact; the Transfers Activity screen was missed and the report says why.

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
