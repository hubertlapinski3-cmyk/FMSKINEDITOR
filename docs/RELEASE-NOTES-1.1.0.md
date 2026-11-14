## FM Skin Studio 1.1.0

This release adds two Studio views and makes the render more honest about what it knows. The installer, update path and signing are unchanged.

### New
- **Screen view.** In the render view, the `screen` tab draws a screen's tile layout on the game's grid for a grid size you give, each cell named and tagged with the tile layout the engine chose. A composition the engine has no measurement for is flagged ESTIMATE.
- **Table view.** The `table` tab draws a table view's header row, in the game's column order, as a labelled placeholder table at a breakpoint you choose. With a project open, both views apply its tile moves or column edits; one switch shows the game as it ships.
- **Pairing by structure.** The render is compared with live captures by the structure of the layout, and invisible live elements are no longer paired. 18 of 343 live elements are paired on the Loans tile and 31 of 762 on Training: not more than before (19 and 34), because the count is bounded by the elements the render draws; what changed is which element each one is compared with.
- **Optional layers, off by default and labelled as inferred.** One applies the classes the game sets in code (read from a capture); one applies a captured 80-rule sample of the game's run-time sheet. With the class layer 14 of the 18 failing rows it is about pass; with the sheet layer 0 of 3. The base numbers are not changed by them.

### How far to trust it
The calibration report ships with this release (`calibration-report-1.1.0.md` and `.json`): 664 rows pass, 83 fail and 415 cannot be compared. Of 1162 slots, 747 were compared; the report breaks the passes down by row class and says how many are values the render did not declare. Each of the 83 failing rows was examined individually: 44 are origin failures and 39 are displaced by an origin; of the origins, 19 rest on a measured capture fact, 12 on magnitude only and 13 are unexplained. The author wrote the rules and no second person checked.
The hover and press checks now also run on the real ancestors of each element from the captures (15 variants beside the published rows). A held-out test of the grid model on 22 hosts of 3 screens it had never seen: 16 were exact; the Transfers Activity screen was missed and the report says why.

### What it is not
An approximation, and it says so on every render: there is no hover, press or animation in the picture, code-drawn visuals (the tactics pitch and players, charts, shot maps, the Training schedule) are approximated or missing, the game's fonts are named rather than drawn, and surfaces painted from the club's colours at run time show the game's default. Use the PREVIEW tab to see your skin in the running game.

### Updating
Installed copies update through Check for updates, then Install and restart. Docs: `docs/RENDER-GUIDE.md`. Evidence: `docs/evidence/`.
