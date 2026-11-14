# Phase 9 M3 exit report (2026-11-14, build 27.0.1.2503222)

M3 asked for: compositions read from the bundles, screen assembly, per-composition pitch verified, two screens matching, and a statement of what stays placeholder. Sources: five inspector captures (plugin 0.3.1-capture, AllowActions false, no clicks) and the layout index of 2026-11-13. Reproduce: `python tools/m3_exit_compare.py` (also a test, `tests/test_m3_exit.py`); report `docs/evidence/phase9-m3-exit-compare-20261114.json`; full suite 285 tests, 0 failures.

## 1. Screens matched
Tolerance as fixed by the owner: each of x, y, width, height within 8 px or 5 percent of the measured size, whichever is tighter; passes and failures both published.

| Screen | Composition | Grid (columns x rows) | Predicted hosts | Result |
|---|---|---|---|---|
| Squad > Overview, panel 2500 | SquadComposition-Large | 30 x 16 | Atmosphere, Tactics, Training, HumanActionsControlPanelBlock, FirstTeamOverview | 5 pass, 0 fail (largest delta 0.8 px) |
| Squad > Overview, Information Display Medium | SquadComposition-Large | 25 x 13 | same five | 5 pass, 0 fail (largest delta 0.6 px) |
| Tactics > Team Instructions | TacticalPlannerTeamInstructionsTabComposition-Large | 29 x 15, no padding, 4 columns reserved right | TeamInstructionsPitch, TeamInstructionsBlock, PhasesAndTeamInstructions | 3 pass, 0 fail (largest delta 0.8 px) |

Honest limits of that result:
- **The model is fitted to these same captures.** The rules (grid size from the container, right-anchored fixed cells, flexible cells absorb the extra columns and rows, 4 columns reserved on the Team Instructions grid) were read off Squad Large and Team Instructions Large; Medium is the only held-out check (a different grid size, same rules: it passed without refitting). Nothing was predicted for an unseen composition.
- **Compared against measured boxes, not pixel screenshots.** The captures are the plan's ground truth for geometry; no screenshot was taken in Session D. Tile CONTENT was checked structurally (named elements of the resolved tile layout present in the host's subtree): Atmosphere 14/15, Tactics 34/36, Training 25/26, HumanActions 1/1, FirstTeamOverview 33/48 (`SquadOverviewTableBlock`, a bound table, config chosen by the "largest that fits" ASSUMPTION), Team Instructions pitch block 15/19 and block 12/17; `PhasesAndTeamInstructions` has no tile record in the index. Not all present, listed, not claimed.
- Two inputs are given, not derived: the grid container's size (screen chrome is not modelled) and the Team Instructions `reserved_right = 4`.

## 2. What is claimed for each screen
- **Squad overview** = `SquadComposition-Large` (five cells) **plus three run-time-added slots without a default tile** (SquadHierachy, MedicalCentre, Loans, each 4x2, stacked below Atmosphere at rows 10, 12, 14 of the 30 x 16 grid; Hierarchy only on the 25 x 13 grid). Probe: the swap dropdowns of Tactics and Training mark their own tile "(Default)"; the dropdowns of the three extra slots mark none. Placeholder category for the render (like the club recolour sheet): what they show is a run-time choice; the render takes their cells as input.
- **Team Instructions** at Large = the three composition cells **plus five run-time-added slots** (ClubTeamReport, SetPieces, DataHub, Penalties, Captains, 4 columns wide at column 25), same category. No composition in the index holds the pitch and these tiles together.

## 3. Pitch (`skin_editor/render/pitch.json`, `render.pitch.lookup`)
Stride 82, gap 16 to 16.5 (cell 65.5 to 66): measured on SquadComposition-Large at two panel sizes (stride 82.000 / gap 16.5 on 2500, residual 0.0 px; stride 81.85 / gap 15.5 on 1600, residual 0.4 px) and on the Team Instructions Large composition (stride 81.97, gap 16.2, residual 0.85 px). The game writes whole-pixel hosts (left = padding + 82 x column, width = 82 x n - 16; padding 12 on the Squad and body grids, 0 on the Team Instructions tab grid). Any composition without an entry returns an `ESTIMATE` flag and is excluded from pixel-faithful claims (tested).

## 4. The height:100% render rule
`render.html.percent_main_axis_rule`: a percentage height in a column, whose parent's height is still being flexed, is treated as auto (basis 0, then grow) where the game does so; CSS would resolve it against the flexed parent and shrink the siblings. **Two sources:** the Loans table (`LoansTile_4x2`, c2 in game and capture 104418: resolved basis 0, row 24.4, table 82.0 against CSS's 19.8) and the Inbox `VisualElement#Messages` (capture 111746: resolved basis 0). **Strict firing condition:** declared percentage height, no declared basis, in flow, column parent that is flexed (grows in a column or is a percentage chain from one), and at least one in-flow sibling that is content-sized and shrinkable; elsewhere both engines agree, so it does nothing (Transfers > Activity is the control: non-shrinking sibling). M0 spike for LoansTile_4x2: 16 of 17 pass, the one failure the bound-text `AutoScroller` width. Limits: Inbox confirms through the resolved basis, not a size gap beyond pixel snapping; the declared height is read from the layout, not from the live element.

## 5. Sheets
The six named root sheets (AlwaysAppliedStyleSheet, LanguageDirectionLTRCombined, LanguageNameOrderGivenFirst, AnimationStyles, FMImages_2x, FMControllerIconsPC_2x) plus Bundesliga, FMCStyles and UnityDefaultRuntimeTheme identify by content against the 7,545-sheet census (scale variants and the two name-order variants share structure and are reported ambiguous with the true name among the candidates). The three empty-named root sheets are **runtime-generated**: negative instance ids, no census match; content recorded (53 theme variables; 190 rules of club-colour recolour; 9 rules of modal backgrounds), `docs/evidence/phase9-m3-unnamed-sheets-20261114.json`. The table control attaches no sheet of its own.

## 6. Named gaps (not blockers)
1. **Who adds the extra slots and in what order** (Squad: Hierarchy, Medical Centre, Loans; Team Instructions: the five side tiles), and whether the order is the game's or the owner's pick. No default tile exists for them.
2. **Standard and Small compositions: MEASURED in Session E (2026-11-14), after the M3 close.** Lowering the resolution to 1152 x 864 gave the Small composition (grid 12 x 8) and 1600 x 900 the Standard one (16 x 8); the breakpoint follows the grid. Pitches stored; both fixtures 5 of 5 (docs/evidence/phase9-i2-session-E-20261114.md). Limit: both grids are the composition's design size, so the flexible-cell rules are still verified on Large only. Team Instructions at Standard and Small, and fullscreen, 16x9 and body presets, remain unmeasured and ESTIMATE-flagged.
3. Tile config for flexible cells (largest-fit assumption), the 12 px vs 0 px grid padding per screen (read per screen, not derived), and `reserved_right` on Team Instructions.
4. Fullscreen, 16x9 and body-preset compositions from plan section 5 are not measured.
5. Pixel screenshots were not compared.

## 7. Status
M3 closed on this report with the gaps above. Next: I2 (mode 4, binding values), offline first.
