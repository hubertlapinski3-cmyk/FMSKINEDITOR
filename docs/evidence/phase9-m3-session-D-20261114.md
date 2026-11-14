# Session D (owner navigates, solo reads): capture-0.3.1 for M3, 2026-11-14

AllowActions false, no clicks. Order: Squad > Overview; Tactics > Team Instructions; Transfers > Activity then Inbox; optional Standard composition.

## Log

- 11:09:30  verify-stock before: STOCK: 67 of 67 UI bundles equal the stock reference hash; update status: same
- 11:09:30  backup C:\Users\Admin\AppData\Local\FM27SkinEditor\backups\inspector-sessionD-20261114T100930Z; DLL 1C698C3DB45DC59FCF01FDA0C4A8A64819DDC6185982237898FF29638FFD7C6F; cfg 9231F4BB99C0B64B67759FA331D43BBF7AF0D1B9DC7A46D0A313F8711886CE9B (both equal the logged baselines)
- 11:09:31  installed 0.3.1 DLL 7940B49FBEDD9BE268BA303567549367C158454E3F5E2B93CDF052BA105C1665
- 11:09:31  cfg: Enabled = true | DumpFolder = C:\Users\Admin\FMSKINNING\workspace\notes\ui-dumps | AllowActions = false | Enabled = true | Styles = true | Sources = true
- 11:09:31  launch requested
- 11:10:20  ready: True plugin 0.3.1-capture
- 11:10:54  capture 1 start: {"v":1,"id":6784,"ms":7.37,"result":{"id":"20261114-111054","mode":"styles","state":"running","elements":0,"skipped":0,"frames":0,"seconds":0,"file":"C:\\Users\\Admin\\FMSKINNING\\workspace\\notes\\ui-dumps\\styles-d1-squad-overview-20261114-111054.ndjson","pending":5,"error":null}}
- 11:10:57  capture 1 status after ~3s: {"v":1,"id":64495,"ms":0.02,"result":{"id":"20261114-111054","mode":"styles","state":"done","elements":7912,"skipped":0,"frames":101,"seconds":3,"file":"C:\\Users\\Admin\\FMSKINNING\\workspace\\notes\\ui-dumps\\styles-d1-squad-overview-20261114-111054.ndjson","pending":0,"error":null}}

- 11:10  CAPTURE 1 Squad > Overview: styles-d1-squad-overview-20261114-111054.ndjson, plugin 0.3.1-capture, 7,912 elements, 0 skipped, 101 frames, 3 s, 12 sheet_content lines. No crash or hang.

### Capture 1 analysis
**Calibration (before any conclusion about the unnamed sheets): PASSED.** All six named root sheets match the 7,545-sheet census by content signature + rule count and the matching candidate list contains the true name each time: AlwaysAppliedStyleSheet (5,510 rules), LanguageDirectionLTRCombined (95), AnimationStyles (67), Bundesliga (22) are unique; LanguageNameOrderGivenFirst (1 rule) is ambiguous with SurnameFirst (same selectors and property count); FMImages_2x (1,434) and FMControllerIconsPC_2x (39) match their own scale variants plus the other scales (1x..4x have the same structure). FMCStyles (22) on a template also unique. The signature cannot tell scale variants apart; it can tell everything else. Against the 49-sheet style index two of them show `not-found` only because the 2x image bundles are not in that index; against the full census they identify.
**The three empty-named sheets: NOT FOUND in the census, so not bundle assets; content now known.** Instance ids are negative (-508, -510, -522: runtime-created objects; the named ones are positive). Zero of the 7,545 census sheets share their signature. What they hold (first rules, `docs/evidence/phase9-m3-unnamed-sheets-20261114.json`):
- -508, 1 rule, `:root`, 53 custom properties: theme variables (`--brand-theme-accent: #7694FE`, `--accessibility-focus: #7694FE`, ...).
- -510, 190 rules, 215 properties: the club-colour recolour sheet (`.navigation-header-gradient`, `#EntityGradient`, `SIGradient#PlayerGradient`, `#PlayerReportHeaderRemapper.entity-background-header` ... with `#17223F`, `--start-colour`/`--end-colour`).
- -522, 9 rules, 14 properties: modal and card backgrounds (`#Background.modal-sheet-background`, `#Card-frame` tints, `.base-layer-content`, `background-image` asset references).
Classification: runtime-generated, club- and settings-dependent: the same placeholder category as club colours and wallpapers (matches the memory note that wallpapers are picked in code with a club recolour). The render does not apply them and now says exactly what they contain.
**Hosts of the Squad tiles (resolved by capture):** the eight tile hosts are siblings under `GridLayoutElementContent`, each `position:absolute` with INLINE px set by code (left/top/width/height): column x=2144, rows at top = 12 + 82 x row (12, 340, 668, then 832, 996, 1160), sizes 312/148 px for 4x4/4x2; world bounds are 311.5/147.5 (the inline values are the rounded forms). Stride 82 per cell confirmed from a second source (the inline values), gap 16 (inline) or 16.5 (world).
**The extra tiles (SquadHierachy, MedicalCentre, Loans at rows 10, 12, 14, all 4x2): NAMED GAP, not a blocker.** Mode 2 records sources only on the 12 swap-dropdown widgets and 5 document roots, none on a tile. In the layout index, SquadComposition-Large has five cells only; Loans and MedicalCentre cells exist only in the FMC compositions (Large: MedicalCentre 4x4 at x16 y4, Loans 8x5) and in other screens, with different sizes. So the three tiles are added by the grid at run time (the tile grid extends below the composition), source unknown offline.
- 11:13:15  capture 2 start: {"v":1,"id":112852,"ms":1.38,"result":{"id":"20261114-111314","mode":"styles","state":"running","elements":0,"skipped":0,"frames":0,"seconds":0,"file":"C:\\Users\\Admin\\FMSKINNING\\workspace\\notes\\ui-dumps\\styles-d2-team-instructions-20261114-111314.ndjson","pending":5,"error":null}}
- 11:13:18  capture 2 status after ~3s: {"v":1,"id":955481,"ms":0.01,"result":{"id":"20261114-111314","mode":"styles","state":"done","elements":4424,"skipped":0,"frames":58,"seconds":3,"file":"C:\\Users\\Admin\\FMSKINNING\\workspace\\notes\\ui-dumps\\styles-d2-team-instructions-20261114-111314.ndjson","pending":0,"error":null}}
- 11:14:11  read target Pitch = P3/0/4/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/1/0/2/0/0/0/1/0/0/0/0/0/0/0/0/0/0/0/0/0/1/0/0/0/0/1/0/1/0/0/0/0/1/0/0/0/0/0/0/0/0/0/0/0/0/0/0/1/1/0/0/1/0
- 11:14:11  read target PitchMask = P3/0/4/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/1/0/2/0/0/0/1/0/0/0/0/0/0/0/0/0/0/0/0/0/1/0/0/0/0/0/0/0/0/0/0/0/0/1/0/0/0/0/0/0/1/0/0/0/0/0
- 11:14:11  read target TeamInstructionsBlock = P3/0/4/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/1/0/2/0/0/0/1/0/0/0/0/0/0/0/0/0/0/0/0/0/1/0/0/0/0/1/0/1/0/0/0/0/1/0/0/0/0/1
- 11:14:11  read target TeamInstructionsPitch = P3/0/4/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/1/0/2/0/0/0/1/0/0/0/0/0/0/0/0/0/0/0/0/0/1/0/0/0/0/1/0/1/0/0/0/0/1/0/0/0/0/0
- 11:14:11  read target PhasesAndTeamInstructions = P3/0/4/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/1/0/2/0/0/0/1/0/0/0/0/0/0/0/0/0/0/0/0/0/1/0/0/0/0/1/0/1/0/0/0/0/1/0/0/0/0/2
- 11:14:11  get_styles reads saved: d2-styles-*.json

- 11:13  CAPTURE 2 Tactics > Team Instructions: styles-d2-team-instructions-20261114-111314.ndjson, 4,424 elements, 0 skipped, 58 frames, 3 s, 12 sheet_content lines. No crash or hang. get_styles on the pitch cells: `d2-styles-*.json` (5 reads, one call at a time).

### Capture 2 analysis
- The screen is a nested grid: `Body` (2443.4 x 1295.9) holds `TeamInstructionsTabGrid` = 29 columns x 15 rows (2361.3 x 1213.9), the same absolute-inline-px mechanism as the Squad grid (left/top/width/height set by code; column left = 82 x column, width = 82 x n - 16).
- Fixed cells follow the pitch: `TeamInstructionsPitch` 6 columns = 475.6 wide, `PhasesAndTeamInstructions` 4 = 311.5, side tiles `ClubTeamReport` / `SetPieces` / `Penalties` / `Captains` 4x2 = 311.5 x 147.5 (148.4 for ClubTeamReport), `DataHub` 4x4 = 311.5 x 312.5. Fit: stride 81.965, gap 16.21, max residual 0.85 px (the two heights that are content-driven). Positions are exact multiples of the stride: block at column 6.0, Phases 21.0, side tiles 25.0; tile tops at 0, 2, 6, 8, 10 rows.
- Flexible: `TeamInstructionsBlock` = 1214.8 (15 columns), full height 1213.9 (15 rows, more than the composition's 9: the grid is sized to the panel, not to the composition).
- So the stride 82 / gap ~16-16.5 is now measured on two compositions (SquadComposition-Large and TacticalPlannerTeamInstructionsTabComposition-Large), consistent to 0.85 px; stored per composition in `pitch.json` (second entry). Columns and rows of the grid come from the panel size (floor((size + gap) / stride)), not from the composition: Squad 30 x 16 (2444.8 x 1295.3 content), Team Instructions 29 x 15 inside Body. Still unmeasured: Standard (needs a smaller panel or interface size), fullscreen and body presets.
- Pitch image inside the cell: `Pitch` 444.3 x 652.3 within the 475.6 x 1213.9 cell (read by get_styles).
- 11:15:18  capture 3 start: {"v":1,"id":569184,"ms":1.46,"result":{"id":"20261114-111518","mode":"styles","state":"running","elements":0,"skipped":0,"frames":0,"seconds":0,"file":"C:\\Users\\Admin\\FMSKINNING\\workspace\\notes\\ui-dumps\\styles-d3-transfers-activity-20261114-111518.ndjson","pending":5,"error":null}}
- 11:15:21  capture 3 status after ~3s: {"v":1,"id":444014,"ms":0.01,"result":{"id":"20261114-111518","mode":"styles","state":"done","elements":2760,"skipped":0,"frames":33,"seconds":3,"file":"C:\\Users\\Admin\\FMSKINNING\\workspace\\notes\\ui-dumps\\styles-d3-transfers-activity-20261114-111518.ndjson","pending":0,"error":null}}

- 11:15  CAPTURE 3 Transfers > Activity: styles-d3-transfers-activity-20261114-111518.ndjson, 2,760 elements, 0 skipped, 33 frames, 3 s. No crash or hang.

### Capture 3 analysis (height:100% closer): NON-DISCRIMINATING, and the criterion was sharpened
- On screen: `SwitchElement#TabsContent` (grow 1, shrink 1, resolved basis 0, 1214.8 high) in `TabGroup` (1262.7, column) next to `ButtonGroup#TabButtons` (36.1, grow 0, SHRINK 0); the inner `TabsContent` (1182.6) next to `TabButtons` (32.2, shrink 0); `all-transfers-frame` is an only child. `dof-transfer-targets-table`, `in-transfers-frame`, `out-transfers-frame` are not on this tab.
- Why it cannot discriminate: the sibling does not shrink, so a CSS model (basis = 100% of the parent, then shrink) and the auto-basis-then-grow model (H-pct) give the SAME size (parent - sibling, minus the margin: 1262.7 - 36.1 = 1226.6 predicted by both against 1214.8 measured, the 11.8 difference being spacing neither model includes). The two models only differ when the sibling is content-sized AND shrinkable (the Loans row: shrink 1), because CSS then takes pixels from the sibling too.
- The strict criterion (declared height 100%, no declared basis, grow > 0, column parent that is not a switch, at least one in-flow sibling with grow 0, no declared basis and shrink > 0) leaves 43 layouts (`hpct-strict-candidates-20261114.json`). Loans' table is one (the only on the Squad screen). The Inbox qualifies: `MessagesToolBlock` / `VisualElement#Messages` with shrinkable siblings `ButtonPanel` and an `SIVisible`. Also `PortalScreen` messages tile, `TeamShapePitchAndTableBlocks` / `TacticsPitch` (sibling `pitch-header`), `PassMaps_Block`, `TransferActivityMainBlock-Small`.
- Next: Inbox (capture 4), then decide.

- 11:17  CAPTURE 4 Inbox: styles-d4-inbox-20261114-111746.ndjson, 9,880 elements, 0 skipped, 113 frames, 3.1 s. No crash or hang. (The first two log lines of this capture could not be written, the file was locked by the editor; this entry replaces them.)

### Capture 4 analysis (height:100% closer): CLOSES H-pct, with the limits stated
Element: `VisualElement#Messages` (two instances, two panels, same numbers), layout `MessagesToolBlock`, declared height 100% (from the layout render), no declared basis, grow 1, in `TabGroup#Content` (column, 1268.6 high, itself flexed: grow 1, resolved basis 0, top padding 7.8), beside `VisualElement#ButtonPanel` (content-sized: grow 0, shrink 1, resolved basis 35.906, margin-bottom 11.719).
- Measured: Messages 1213.9 high, **resolved flex-basis 0**; ButtonPanel 35.2. 1213.9 + 35.2 + 11.7 = 1260.8 = the parent's content height.
- CSS model (percentage against the flexed parent, then shrink): Messages basis = 1260.8, predicted 1214.5 and ButtonPanel 34.6, resolved basis 1260.8. H-pct (auto, basis 0, grow): Messages 1213.2, ButtonPanel 35.9, resolved basis 0.
- Sizes alone do NOT separate them (measured is 0.6-0.7 px from each; the game also snaps to its own pixel grid). What separates them is the engine's resolved basis: 0, exactly what H-pct says and not what CSS says. Same as the Loans table (resolved basis 0 beside a 24.4 px shrinkable row; sizes 24.4 / 82.0 exact, CSS gives 19.8 / 86.5).
- Transfers > Activity (capture 3) stays non-discriminating: its sibling does not shrink.
Decision: H-pct becomes a render rule, **two sources named: Loans table (LoansTile_4x2 `StreamedTable`, c2 in game and capture 104418) and Inbox Messages (MessagesToolBlock, capture 111746)**. Limits: the Inbox confirms the mechanism through the resolved basis, not through a size difference larger than the pixel snapping; the declared height 100% of both elements is read from the layout render, not from the live element (the capture's `inline` does not hold uxml styles).
Implemented: `render.html.percent_main_axis_rule` (called by `Renderer.layout`; `style_dict` honours it; each changed node carries `layout_rules: ["percent-main-axis-as-auto"]`). It fires only where the engines differ: a percentage height in a column, the parent being flexed (grows in a column, or a percentage chain from one), no declared basis, the node in flow, and a shrinkable content-sized sibling in flow. Re-run of the M0 spike for LoansTile_4x2 against the c2 dump: **16 of 17 pass, 1 fail** (was 15 / 2): the row now 24.4 (was 19.8) and the table 81.1 against 82 measured; the remaining failure is `AutoScroller` width (bound text, accepted placeholder category). Tests: tests/test_percent_rule.py (7), full suite 278 passed, 2 skipped.

- 11:26  Swap dropdown of the Tactics tile held open by the owner; read-only capture of its subtree (`styles-d5-swap-dropdown-open-20261114-112636.ndjson`, 391 elements, 0 skipped).
### Extra-tiles probe (owner's revised plan)
- The open `StreamedDropdownList` (P3/0/19) lists 20 tiles: Tactics (Default), Captains, Discipline, Dynamics, First Team, Happiness, Hierarchy, Internationals, Loans, Medical Centre, Promises, Squad Feedback, Squad Numbers, Squad Registration, Targets, Training, Youth Candidates, Youth Development, Youth Setup, Youth Squad. **No reset or restore entry**; a search of the whole screen for Reset / Restore / Revert / Original found nothing. So there is no reset to trigger.
- New observation: **the slot's default tile is marked in the list ("Tactics (Default)")**, so the game stores a default tile per slot and shows which one is current. For the three extra slots (SquadHierachy, MedicalCentre, Loans) opening their dropdowns would show "<tile> (Default)" on the current tile if they are default fills, and on another entry if swapped. Not done yet: needs the owner to open those three dropdowns (no item clicks).
- 11:28  Probe, Training tile (a composition slot, control case): the open list marks **Training (Default)** (styles-d5b-swap-dropdown-20261114-112841.ndjson). Tactics tile earlier: **Tactics (Default)**. Both composition slots hold their default tile. Verdicts for Loans, Medical Centre, Hierarchy: pending.

- 11:29  Probe, Loans tile (owner opened its swap dropdown; styles-d5c-dropdown-loans-20261114-112939.ndjson): the 20 entries are alphabetical with **no entry marked (Default)** and the current tile is not moved to the top, unlike Tactics and Training where the slot's own tile is listed first as '(Default)'. Reading: this slot has no default tile of its own, i.e. it is not a composition slot.

- 11:30  Probe, Medical Centre tile (styles-d5d-dropdown-medical-20261114-113023.ndjson): 20 entries, alphabetical, **no entry marked (Default)**; same as Loans.

- 11:32  Probe, Hierarchy tile (`styles-d5e-dropdown-hierarchy-20261114-113206.ndjson`): 20 entries, alphabetical, **no entry marked (Default)**.

### Extra-tiles verdict (probe complete)
| Slot | Dropdown | Marked (Default) |
|---|---|---|
| Tactics (composition slot, control) | current tile listed first | **Tactics (Default)** |
| Training (composition slot, control) | current tile listed first | **Training (Default)** |
| Loans (extra) | alphabetical, 20 entries | none |
| Medical Centre (extra) | alphabetical, 20 entries | none |
| Hierarchy (extra) | alphabetical, 20 entries | none |
Neither of the two predicted outcomes occurred: the current tile is not marked default (so not "the game's default fill of a composition slot"), and no other entry is marked default (so not "a swap away from a slot default"). The observation is a third one: **the three extra slots have no default tile at all**, unlike the composition slots. They are slots the game adds at run time below the composition; which tile each shows is a tile choice for a slot with no default, so a swap cannot be told from the game's own fill with this data.
Claim for the M3 exit: the Squad overview is the composition `SquadComposition-Large` (five cells) plus three run-time-added slots without a default tile (Hierarchy, Medical Centre, Loans, all 4x2, stacked below Atmosphere at rows 10, 12, 14); what they show is a runtime choice, so they are placeholder category for the render. Not resolved: who adds them and whether Hierarchy, Medical Centre and Loans is the game's order or the owner's pick.
- 11:3x  CAPTURE 5 Squad > Overview, Information Display Medium: C:\Users\Admin\FMSKINNING\workspace\notes\ui-dumps\styles-d6-squad-overview-medium-20261114-113402.ndjson ; 7500 elements, 0 skipped, 83 frames. No crash or hang.

### Capture 5 analysis (Squad > Overview, Information Display Medium)
- Medium did NOT switch to `SquadComposition-Standard`: the hosts are the Large composition's (Tactics 4x4 top right, Training 4x4 below, Atmosphere 4x2), only the panel is smaller (1600 wide, grid area 2057.3 x 1074.4 = 25 columns x 13 rows, so the tiles below the composition that fit are fewer: Hierarchy at row 10 is there, Medical Centre and Loans are not).
- Pitch unchanged by the panel size: stride 81.85, gap 15.5, max residual 0.4 px over 7 sizes; tile tops 4, 4 and 2 strides apart; the grid still places the right column at 82 x column + 12 (left 1734 = column 21). The pitch of `SquadComposition-Large` is therefore measured at two panel sizes (2500 and 1600 wide); stored in `pitch.json` (`also_measured`).
- The Standard composition is still NOT measured: the breakpoint is not reached by Medium on this panel (it is a function of the panel/grid size, not of the preference alone). Stays an `ESTIMATE` for `SquadComposition-Standard` and `-Small` (flagged by `render.pitch.lookup`), named gap for the M3 exit. The Information Display preference changes the panel size, which the render can take as a parameter.
## Close-out (game closed by the owner)
- log pair preserved: LogOutput.log 10420 bytes sha 65026D7EA79CF637; Player.log 31489 bytes sha D0C397A383C071A2
- LogOutput: quitting line:    at AutoDev.Plugin.<>c.<InstallExitDiagnostics>b__10_2() in C:\Users\Admin\Dow
- capture sessions: 10 done; warnings/errors mentioning Capture or Inspector: 1
- restored DLL 1C698C3DB45DC59FCF01FDA0C4A8A64819DDC6185982237898FF29638FFD7C6F ok=True; cfg 9231F4BB99C0B64B67759FA331D43BBF7AF0D1B9DC7A46D0A313F8711886CE9B ok=True
- cfg values: Enabled = true | DumpFolder = C:\Users\Admin\FMSKINNING\workspace\notes\ui-dumps | AllowActions = false
- verify-stock after: STOCK: 67 of 67 UI bundles equal the stock reference hash; update status: same
