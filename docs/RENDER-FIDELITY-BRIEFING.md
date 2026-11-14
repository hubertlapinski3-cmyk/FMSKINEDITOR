# Render fidelity: a standalone briefing (for a reviewer who has not followed the project)

Written 2026-11-14 at release 1.0.0. Question to answer: **what is missing to make the offline render look nearly exactly like the game?** This file is self-contained; the evidence it cites is listed at the end.

## 1. What this is

FM Skin Studio is a desktop tool (Python engine + React/Tauri front end) for making skins for Football Manager 27. FM27's interface is Unity UI Toolkit: layouts are UXML-like trees (`VisualTreeAsset`s) inside Unity asset bundles, styled by USS style sheets and design tokens (`--variables`). A skin changes those sheets and tokens.

The **offline render** (Phase 9, Studio activity bar `R`) draws any of the game's 7,467 layouts without starting the game, and for each element says which rules matched and where each value and token came from. It reads the game's own bundles: layout tree, includes resolved by GUID, a cascade over the game's root style sheets in the game's order (specificity, sheet position, rule order, inline last), custom properties resolved, then drawn as HTML/CSS. Screens (several tiles on the game's grid) are assembled by a separate module using measured grid and pitch data.

It is an **approximation and says so on every render**. Nothing in it is the game's renderer.

## 2. How it was measured (the calibration)

An in-game inspector plugin (BepInEx, read-only unless a session allows actions) reads, for live elements: world bounds, resolved colours, font sizes, flex values, text, pseudo-state mask and classes. Those readings are the "truth" the render is compared with. A fixture framework (data folders under `tests/fixtures/render/`, 18 fixtures) compares row by row: boxes within 8 px or 5 percent of the measured size (whichever is tighter); colours, font sizes and flex values exactly. Each row is PASS, FAIL or N/A (the render makes no declaration to compare). Nothing is filtered or re-toleranced. The published report is `docs/evidence/phase9-m7-calibration-20261114/calibration-report.md`.

**Result: 680 pass, 78 fail, 435 N/A.** Whole-screen host placement on the Squad overview and Team Instructions: every predicted host box passed (28 of 28 in the M3 comparison), with the run-time slots given, not predicted.

Important limits of that result:
- N/A is large (435): for many elements the render declares nothing to compare, so "pass" counts overstate coverage.
- It covers 18 fixtures: five tiles (Loans, Medical Centre, Tactics, Atmosphere, Training), a few phase test projects, six screen captures and one state fixture. The other ~7,400 layouts were verified to **render as a tree** (7,467 of 7,467) but never compared with the game.
- The 78 failure causes are assigned **by rule** (`fixtures.CAUSES`), not checked row by row. A rule that fits wrongly would hide an unrelated failure. The report says this at its top.
- Some fixtures carry their own caveats in their `source` text (for example the Phase 3 red-pitch fixture runs on a synthetic node and proves only that the project's rule outranks the game's; its first expected value was wrong and was corrected to the game's data, and the correction is recorded).

## 3. What is missing for a near-exact render

Ranked by how much of the visible/ measured difference each explains.

### 3.1 Real data instead of placeholders
In game, names, numbers, table rows, badges and lists come from the save. The render shows the layout's own sample text, underlined and labelled "sample", or nothing. A capture can deliver the live text for a screen, and pairing it with the drawn nodes by the template-position path was built: it paired 16 of 24 text nodes on the five tiles and changed exactly one measured row (one Tactics `CellText` box, 66.9 vs 67.4 wide). The pairing key (`Binder.ToString()`) is a template-position path, **not** a data path: the render cannot know that a label means "player age". An observer hook was ruled out by the owner, so this is recorded as a permanent gap. Full data fidelity therefore needs per-screen captures or a save reader, neither built.

### 3.2 Fonts and text metrics
The UI font is a TextMeshPro SDF asset (ABC Social). It is named, not drawn; a browser stand-in font is used, with line heights taken from measurements (12 px to 18.6, 13 to 16.6, 14 to 21.5, 16 to 24.4). Text width differs, which moves wrapping and neighbours. Width-driven failures were 12 of the 77 geometry failures, and they cascade. The fix is to extract the SDF atlas and glyph metrics and lay out text with them. Well defined, not started.

### 3.3 Code-built visuals
53 of the 77 geometry failures are two things the game builds in code, not in layout files: the tactics pitch and its players (33) and the Training tile's weekly schedule, calendar and lists (20). Charts, shot maps, `SIImage`/`SIGradient` drawing, and component-drawn images (5 failures) are in the same class. Each needs its own drawing model built from captures of that component.

### 3.4 Run-time club colours
Three root style sheets are created at run time (empty names, negative instance ids) and paint surfaces from the active club's colours. The render shows the game's defaults. Example: the Loans tile background reads #17223F in game and #1E2129 in the render. The palette exists in game data; the club-to-run-time-sheet mapping is not modelled.

### 3.5 State and motion
The render shows no hover, press, focus or animation. A 2026-11-14 manual in-game session (read by hand, baseline inspector, owner at the PC) measured hover, press, focus and selection on seven control types. Result: button, list-row, tile and nav-label colours in each state equal exactly what the game's own `:hover` / `:active:enabled` rules declare (the model needed Unity's `:enabled` pseudo for the pressed case; my first run omitted it and predicted the wrong colour, which is recorded as a learning). Pitch markers and instruction tiles get a hover flag and no style change. So a hover/press toggle is cheap; transitions and animation are not modelled.

### 3.6 Coverage
Only the Squad overview (three composition sizes) and Team Instructions (Large only) are assembled as screens. Measured pitch data exists for those compositions; others return an "estimate" flag. Flexible-cell rules are verified on Large only. Every further screen costs one capture session with the owner at the game.

### 3.7 Smaller named gaps
Class renames, image and font swaps and raising a rule's specificity are not applied in the skin view. No Studio view yet for `render.screen` / `render.table` (engine calls only). Payload per node is large (about 3.9 KB, the explain data); a 1,000-node cap keeps big layouts inside 200 ms cached but payloads still reach 1 to 5 MB, and `PreferencesFMMenuCard` is 12.7 MB for 266 nodes (inlined image data).

## 4. Realistic ceiling
Items 3.2, 3.4 and 3.5 are finite and measurable and would move the render from "structurally right, rules attributed correctly" to "recognisably the same screen" for static chrome. Items 3.1 and 3.3 set the ceiling: without live data and the code-drawn components the frame can match but the content cannot.

## 5. What I (the model that built it) am least sure of, and would like checked
1. Whether the failure-cause rules (`skin_editor/render/fixtures.py`, `CAUSES`) mislabel any of the 77 failures. They were not verified row by row.
2. Whether "pass" on N/A-heavy fixtures (435 N/A) gives a misleadingly rosy picture.
3. Whether the grid/pitch model (`render/screen.py`, `pitch.json`) is fitted to three captures and over-claims general correctness; its limits are stated in `docs/evidence/phase9-m3-exit-report-20261114.md`.
4. The I3 state reading of text labels: the label's own pseudo mask read 0 while its hover colour applied (its ancestors read 2); I explained it as the mask read lagging what the style engine applies, which is an inference, not an observation.
5. The inspector startup stalls seen with modified plugin builds were attributed by the owner to anti-tamper; I could not isolate the cause and parked it. It does not affect the render's results.

## 6. Which files to hand over
Minimum: this file, then `docs/evidence/phase9-m7-calibration-20261114/calibration-report.md` (every compared row), `docs/RENDER-GUIDE.md` (what a user sees), `docs/PHASE9-PLAN.md` (milestones, decisions, evidence log; long). Code to check the claims: `skin_editor/render/fixtures.py` (verdicts and causes), `skin_editor/render/cascade.py`, `skin_editor/render/screen.py`, `tests/fixtures/render/`. Method and sessions: `docs/evidence/phase9-m7-offline-report-20261114.md`, `docs/evidence/phase9-i3-session-G-20261114.md`, `docs/evidence/phase9-m8-report-20261114.md`.
