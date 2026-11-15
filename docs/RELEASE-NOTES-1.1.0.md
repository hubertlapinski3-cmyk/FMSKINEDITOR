## FM Skin Studio 1.1.0

This release adds two Studio views and an honest second look at how the render is compared with the game. The installer, update path and signing are unchanged.

### New
- **Screen view.** In the render view, the `screen` tab draws a screen's tile layout on the game's grid for a grid size you give, each cell named and tagged with the tile layout the engine chose. A composition the engine has no measurement for is flagged ESTIMATE.
- **Table view.** The `table` tab draws a table view's header row, in the game's column order, as a labelled placeholder table at a breakpoint you choose. With a project open, both views apply its tile moves or column edits; one switch shows the game as it ships.
- **A stricter comparison in the calibration report.** The old pairing matched 11 render nodes to live elements the game hides; the new pairing no longer does that, and every other node keeps the live partner it had (0 partners changed, 0 newly paired). That is the whole difference. It is not a gain: live elements paired fell to 18 of 343 on the Loans tile and 31 of 762 on Training (from 19 and 34), and compared rows on the tile fixtures fell from 697 to 656. Where the render draws an element the game hides, that is now a failure (named visibility; 3 rows), not a non-comparison.

### How far to trust it
The calibration report ships with this release (`calibration-report-1.1.0.md` and `.json`): 638 rows pass, 80 fail and 410 cannot be compared. Of 1128 slots, 718 were compared; the report breaks the passes down by row class and says how many are values the render did not declare. Each of the 80 failing rows was examined individually: 41 are origin failures and 39 are displaced by an origin; of the origins, 20 rest on a measured capture fact, 10 on magnitude only and 11 are unexplained. The author wrote the rules and no second person checked.
The hover and press readings are each counted once, scored on the real ancestors of the element from the captures; 30 variant rows (truncated chains and one-variable analyses of the same readings) and 6 layer rows are published in the report outside those totals. A held-out test of the grid model on 22 hosts of 3 screens it had never seen: 16 were exact; the Transfers Activity screen was missed and the report says why.

### Engine only, not a Studio feature
Two optional calibration layers exist in the engine and are off: one adds the classes a capture shows the game setting in code, one adds a captured 80-rule sample of the game's run-time sheet. Their rows are in the report's own layers section, outside the totals above. The class layer reads its classes from the same capture it is scored against, so it confirms a diagnosis and does not show it could predict: with it 14 of the 18 failing rows it is about pass, and it breaks 1 of the 1042 rows it was run over; with the sheet layer 0 of 3 pass and it breaks 0 of 1042.

### What it is not
An approximation, and it says so on every render: there is no hover, press or animation in the picture, code-drawn visuals (the tactics pitch and players, charts, shot maps, the Training schedule) are approximated or missing, the game's fonts are named rather than drawn, and surfaces painted from the club's colours at run time show the game's default. Use the PREVIEW tab to see your skin in the running game.

### Updating
Installed copies update through Check for updates, then Install and restart. Docs: `docs/RENDER-GUIDE.md`. Evidence: `docs/evidence/`.
