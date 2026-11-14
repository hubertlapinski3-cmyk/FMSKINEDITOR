## FM Skin Studio 1.0.0

The offline visualiser is complete. You can now see what a skin does to Football Manager 27's screens without starting the game, and trace any element back to the rule and the token behind it.

### What you can do
- **Render any layout of the game.** All 7,467 layouts draw offline, with the game's own style sheets applied in the game's order, its icons and textures where they can be found, and every piece of data shown as a clearly labelled placeholder (the layout's sample text, underlined; never invented player or club data). The engine can also assemble a whole screen's tiles on the game's grid (the Squad overview at its three measured sizes, Team Instructions at the large one; this is an engine call, not yet a Studio view), and large layouts open branch by branch instead of freezing.
- **Click any element to see why it looks like that.** The panel lists the rules that matched it in cascade order and every computed value with its source. Click a rule to read it, click a token to follow its chain of aliases to the value, and override either in your project.
- **Go the other way.** Put the caret on one of your rules or tokens in the editor and see which elements it paints.
- **Edit a project or a native skin and watch it change.** Your edits (rules, tokens, tile moves, table columns) repaint the render as you save; one switch shows the game as it ships, another shows your skin.
- **Know how far to trust it.** The calibration report ships with this release (`calibration-report-1.0.0.md` and `.json`, attached below): every comparison against measurements taken in the game, 680 passing, 78 failing, 435 not comparable, each failure with a named cause. The causes are assigned by rule, not checked row by row, and the report says so.

### What it is not
An approximation, and it says so on every render: there is no hover, press or animation in the picture (the game's own state rules are checked in the report), code-drawn visuals (the tactics pitch and players, charts, shot maps, the Training schedule) are approximated or missing, the game's fonts are named rather than drawn so text widths differ, and surfaces painted from the club's colours at run time show the game's default. Class renames, image and font swaps and raising a rule's specificity are not applied in the skin view. Use the PREVIEW tab to see your skin in the running game.

### Updating
Installed copies update through Check for updates, then Install and restart. Docs: `docs/RENDER-GUIDE.md`. Evidence: `docs/evidence/` (reports for every milestone, the calibration report and the in-game sessions behind it).

### Revision of the calibration report (2026-11-14, after a review)
The paragraph above describes the report as first published (680 passing, 78 failing, causes assigned by rule). The report asset was replaced in place after a review: no published row changed, 5 rows were added, every failing row is now examined individually, coverage is broken down by row class, the grid model has a held-out test, and the start-up stall is written up. Totals of the revised report: 683 pass, 80 fail, 435 not comparable. The update dialog of the installed 1.0.0 shows the original notes (latest.json is part of the published release and was left untouched); the release page carries the dated note. Details: `docs/evidence/phase9-fix-round-20261114.md`.
