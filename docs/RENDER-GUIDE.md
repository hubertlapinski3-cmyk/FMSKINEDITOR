# The offline render: a user guide

The render draws any layout of Football Manager 27 inside the Studio without starting the game, and tells you, for every element, which rules styled it and where each value came from. It is an **approximation of the game, not the game's renderer**: it says so on every render, and `docs/evidence/phase9-m7-calibration-20261114/calibration-report.md` publishes every number it was measured against, pass and fail.

## What you get

- **Draw a layout.** Activity bar, `R`. The left list holds the game's layouts (type to filter by name; the number beside a name is its element count). Click one and it is drawn in the middle with the game's own style sheets applied in the game's order. Width, height and zoom change the stage; the corner markers (red = a property the render cannot draw, amber = partly drawn) can be switched off.

- **Why does this element look like that?** Click an element. The right-hand panel lists the rules that matched it, lowest first (the last one wins), then every computed property with its value, its status (`mapped`, `partial`, `unmapped`, `unknown`) and the rule it came from. Click a rule to read it as USS; click a token chip to see its alias chain and where it is defined.

- **Change it.** With a project open, a game rule offers "Override in <project>" (adds a rule to the project's sheet) and a token offers a value box (adds a token override). A rule that already lives in your project opens in the editor at its line.

- **The reverse direction.** In the editor, put the caret on one of your own rules or on a `--token`: a bar under the editor says how many elements it styles in the layout you last rendered, and "Show in render" outlines them.

- **Vanilla or skin.** With a project open, the "skin" tick draws your edits over the game's styles; untick it to see the game as it ships. Every edit repaints the view (one repaint per change).

## Large layouts

Thirteen of the game's layouts went over the 200 ms budget; most hold 900 to 3,800 elements and the largest, `DetailedPreferencesBlock`, 5,487. Drawing all of them is slow and the data is large (29 MB for that one), so the render draws about **1,000 elements** first and says so: *"Large layout: 1,000 of 5,487 elements are drawn"*.

- A branch that was cut shows a dashed **"show N child elements"** button where its children would be. Click it to draw that branch; nothing else moves, and your selection stays.

- **"draw all"** in the banner draws everything (seconds, a large payload); "back to the capped view" returns.

- The cap is only for the view. The calibration fixtures and any call with `max_nodes: 0` use every element.

- Measured cached times for the 13 layouts that were over the 200 ms budget: all between 28 and 90 ms with the cap (the full renders took 23 to 545 ms; the first render after starting the engine is slower because the game's bundles are read once).

## Optional layers (engine level, off by default)

Two layers exist for the calibration and are NOT switched on in the Studio or in `render.layout`: the **live-class layer** adds, to a layout's nodes, the classes the live element carries in a capture and the layout lacks (a sprite class on an icon setter, for instance); the **recorded run-time sheet layer** appends the 80 rules a capture sampled from the game's run-time sheet (of 190) as one more sheet. Both are INFERRED, and neither is a user feature. The first reads its classes from the SAME capture the rows are scored against: that the failing rows it is about pass with it confirms the diagnosis, it does not show the layer could predict a screen no capture was taken of. The second is a CAPTURED SAMPLE: a rule absent from it proves nothing. The report runs each over every paired row, passing rows included, and publishes the rows each one breaks; their rows stand alone in the report's layers section and are in no total and no examination. The base render already applies the per-type classes learned from many dumps (`data/render/runtime-classes.json`, the "runtime classes (learned)" in the explain panel); that file is part of the base and is not a layer.

## What the render does not do

Read the notice at the top and the "What this render does not know" list under the stage. In short:

- **Data is a placeholder.** Bound text shows the layout's own sample text (underlined dotted, tooltip says "sample"), never real player or club data.

- **No runtime state.** There is no hover, press, focus or animation in the picture. The calibration report checks the game's own state rules against readings taken by hand in the game, each reading counted ONCE and scored on the real ancestors of the element from the captures (a one-element chain cannot match a rule that depends on an ancestor). Button, list-row and tile colours match what those rules declare on the real chains; the one rest colour that does not is the Loans tile's, a club colour from a run-time sheet. The navigation label is the case that depends on the ancestors: on its real chain the game's applied sheets predict another colour than the one read, so that base row fails; the label's own hover is not needed to reach the observed colour (a one-variable analysis, outside the totals), and what restores the observed colours is the recorded run-time sheet, a captured 80-rule sample, shown as a LAYER row. The mechanism is unverified. Pitch markers and instruction tiles get a hover flag with no style change.
- **Code-built visuals are approximated or missing:** the tactics pitch and its players, the Training tile's schedule, charts and shot maps are drawn in code by the game.

- **Fonts and images:** the game's fonts are named, not drawn (a stand-in font is used, so text widths differ); atlas icons and images are drawn where they can be found.

- **Club colours.** Some surfaces are painted from the club's colours at run time; the render shows the game's default there.

- **Not applied in the skin view:** class renames, font swaps, the bundle route's image swaps and raising a rule's specificity. **A native project's picture swaps ARE drawn (since S6, 1.2.0):** the same `images.uss` rules the native export writes, with your own files; every image is stretched to its element (the game crops a wallpaper to fill).

## How far to trust it

The published report (for this version `docs/evidence/phase9-v110-calibration-20261114/`; the 1.0.0 reports are frozen history: the revised one the 1.0.0 release assets carry in `docs/evidence/phase9-m7-calibration-revised-20261114/`, and the first one, as published at release, in `docs/evidence/phase9-m7-calibration-20261114/`) compares the render with measurements taken inside the game. Boxes pass within 8 px or 5 percent of the measured size, colours and font sizes exactly. There is no single pass rate to quote: the pass count is made of different kinds of rows, and this is the coverage block, generated from the same rows as the report:

<!-- coverage:start -->
**Coverage: what the pass count is made of.** Of 1128 slots, 718 were compared (pass or fail) and 410 were not (N/A), reasons below. There is no single headline rate: read the classes.

| Row class | Pass | Fail | N/A |
|---|---|---|---|
| geometry | 98 | 67 | 26 |
| colour | 29 | 5 | 256 |
| font-size | 21 | 0 | 124 |
| flex | 430 | 5 | 0 |
| rule winner | 4 | 0 | 0 |
| state | 19 | 3 | 4 |
| screen hosts | 28 | 0 | 0 |
| tile order | 6 | 0 | 0 |
| table header | 3 | 0 | 0 |

Geometry: 98 of 165 compared rows pass, of which 54 are the stage box (the first node of the capture, taken from it) and 44 are other boxes. Colour and font-size: 50 of 55 compared rows pass. Flex: 430 of 435 rows pass; 291 of them have the value supplied by default because the render declared nothing (the same condition is N/A for colour and font-size), and 324 pass with a value equal to Yoga's initial value whether declared or supplied. Passes by value source: 189 declared, 291 default.

| Fixture | geometry | colour | font-size | flex | rule winner | state | screen hosts | tile order | table header |
|---|---|---|---|---|---|---|---|---|---|
| c3-table-header | - | - | - | - | - | - | - | - | 3 / 0 / 0 |
| p6-magenta-reload-skin | - | - | - | - | 2 / 0 / 0 | - | - | - | - |
| phase3-red-pitch | - | - | - | - | 2 / 0 / 0 | - | - | - | - |
| screen-squad-large-1600 | - | - | - | - | - | - | 5 / 0 / 0 | - | - |
| screen-squad-large-1680 | - | - | - | - | - | - | 5 / 0 / 0 | - | - |
| screen-squad-large-2500 | - | - | - | - | - | - | 5 / 0 / 0 | - | - |
| screen-squad-small | - | - | - | - | - | - | 5 / 0 / 0 | - | - |
| screen-squad-standard | - | - | - | - | - | - | 5 / 0 / 0 | - | - |
| screen-team-instructions-large | - | - | - | - | - | - | 3 / 0 / 0 | - | - |
| state-i3-session-g | - | - | - | - | - | 18 / 3 / 4 | - | - | - |
| tile-atmosphere | 14 / 3 / 3 | 2 / 2 / 28 | 3 / 0 / 13 | 48 / 0 / 0 | - | - | - | - | - |
| tile-loans | 15 / 3 / 1 | 2 / 1 / 33 | 2 / 0 / 16 | 54 / 0 / 0 | - | 1 / 0 / 0 | - | - | - |
| tile-loans-c2-dump | 16 / 1 / 2 | - | - | - | - | - | - | - | - |
| tile-medical-centre | 24 / 7 / 15 | 4 / 1 / 55 | 3 / 0 / 27 | 90 / 0 / 0 | - | - | - | - | - |
| tile-tactics | 17 / 33 / 2 | 12 / 0 / 88 | 6 / 0 / 44 | 147 / 3 / 0 | - | - | - | - | - |
| tile-training | 12 / 20 / 3 | 9 / 1 / 52 | 7 / 0 / 24 | 91 / 2 / 0 | - | - | - | - | - |
| tiles-large | - | - | - | - | - | - | - | 3 / 0 / 0 | - |
| tiles-standard | - | - | - | - | - | - | - | 3 / 0 / 0 | - |

(cells are pass / fail / N/A)

**N/A by reason:** no-declaration-live-initial-or-inherited: 382; descendant-of-hidden-switch-branch: 13; live-element-present-but-invisible: 8; live-element-absent-or-not-captured: 5; not-measured-live: 1; no-declaration-parent-not-in-dump: 1. No-declaration rows whose live value is not the initial or inherited one: 0.

**Rows never emitted** (the runners skip them, they are in no verdict): boxes: root of a hidden switch branch (never emitted): 3; values: drawn node with no live partner (every property skipped): 180. Emitted plus skipped equals render nodes times properties in every fixture: yes.

**Live-side coverage** (dump elements paired with a render node): tile-atmosphere 16 of 48; tile-loans 18 of 343; tile-loans-c2-dump 17 of 32; tile-medical-centre 30 of 159; tile-tactics 50 of 242; tile-training 31 of 762. Captured delivered texts with no render node: 38.

**Duplicates, counted twice:** tile-loans and tile-loans-c2-dump are one tile (one tile measured twice (the c2 inspector dump and the squad capture); both are kept and both are counted in every total; deduplicating would change the headline totals and needs the owner's decision). The club colour #17223F is counted in 4 FAIL rows (three tiles and the state fixture's rest row). Nothing was deduplicated.
<!-- coverage:end -->

Each failing row was examined individually and carries a cause, a grade (measured fact, magnitude only) or the label UNEXPLAINED; the author wrote the rules and no second person checked. The main causes are the ones above: code-built content, run-time classes and colours, text width with the stand-in font. The grid placement model is scoped per composition (reproduces the captures it was derived from; one held-out check failed on a screen it had never seen). Use the render to see structure, which rule wins and where a value comes from; confirm pixel-exact spacing and anything data-driven in the game (the PREVIEW tab reloads your skin in the running game).

## Engine calls (for scripts)

`render.layouts`, `render.layout` (`max_nodes`, `open` for large layouts), `render.rule`, `render.table`, `render.screen`. The table and screen calls are also Studio views (v1.1.0): in the render view, the `screen` tab draws a screen's composition on a grid container of a size you give, each cell named and tagged with the tile layout the engine chose (an unmeasured composition is flagged ESTIMATE), and the `table` tab draws a table view's header row as a labelled placeholder table at a breakpoint of your choice; with a project open both apply its tile moves or column edits, and the skin switch shows the game as it ships. Details: `docs/API.md`.
