# Phase 9 M3, offline data work (2026-11-14, build 27.0.1.2503222)

Everything here is read from files already held (the layout index `fmlayout-index` of 2026-11-13, the style census, and the Session C capture); nothing was run in game.

## 1. Which screen is "Squad overview", and which composition was on screen
- Panel `SquadScreen` (layout 403), tile set `SquadTileCompositionSet`, compositions `SquadComposition-{Small,Standard,Large}` (+ `FMC` variants).
- On screen: `SquadComposition-Large` (Tactics x16 y0 4x4, Training x16 y4 4x4, Atmosphere x16 y8 4x2 fixed cells; `HumanActionsControlPanelBlock` 16x1 and `FirstTeamOverview` 16x9 flexible). Matches the captured positions to 0.1 px.
- Three more tile hosts were on screen (`SquadHierachy`, `MedicalCentre`, `Loans`, all 4x2, stacked below Atmosphere at y 918, 1082, 1246) that this composition does not contain: the player's own layout or the host adds them; M3 must read where they come from before claiming the screen (open).

## 2. Measured pitch (stored in `skin_editor/render/pitch.json`, read by `render.pitch`)
- Fit over the three fixed-size cells (min size == max size): stride 82.000, gap 16.500, cell 65.500 px (panel units, panel 2500 x 1406.25). All six size residuals 0.0 px; stacked cells start 328.1 apart (4 strides = 328.0, 0.1 px off).
- It confirms the c2 provisional figure (66 / 16, from one tile) to within 0.5 px, and is now measured on three tiles of one composition at one setting.
- Flexible cells (max size 100) do not follow the pitch: they take what the fixed cells leave (2115.2 wide = content width minus the 4-cell column minus a 16.7 px gap). The vertical gap below the top flexible row is 15.6 (66.4 high for a 1-cell row), so a flexible row is not exactly one pitch row either. Recorded, not modelled.
- Still to measure before M3 exit (plan section 5): Squad overview at Standard and Small, the Team Instructions composition at Standard and Large, one 20x11 fullscreen, one 16x9, one body preset. A composition without an entry returns `measured: false` with an `ESTIMATE` flag and is excluded from pixel-faithful claims (tested).

## 3. Team Instructions composition (for the M3 session)
- `TacticalPlannerTeamInstructions` is a tab hosted by the tactical planner cards; its compositions: `...TabComposition-Standard` (pitch cell 6x7 fixed, block 6x7 flexible), `...-Large` (pitch 6x9 fixed, block 10x9 flexible from min 10, `PhasesAndTeamInstructions` 4x9 fixed at x16), `...-Large-InMatch`. Large gives two fixed cells (6x9 and 4x9) for a second pitch fit.

## 4. height:100% closer (H-pct): discriminating candidates mapped
Criteria: declared `height:100%`, no declared flex-basis, `flex-grow > 0`, column parent, in-flow sibling, not absolute, parent not a switch (a switch shows one branch, so branch containers have no live sibling). 151 of the layouts have one (list: `C:\Users\Admin\FMSKINNING\workspace\notes\hpct-candidate-layouts-20261114.json`).
- Squad overview (all size variants of its 11 tile stems): `LoansTile_4x2` table (already measured, one element) and a switch-branch container in `MedicalCentreTile_4x2` (no live sibling): NO new discriminating element.
- Team Instructions (2 layouts): none.
- Elsewhere, named and reachable: `TransferActivityMainBlock-Standard/Large` (`StreamedTable#dof-transfer-targets-table`, `ComponentElement#all-transfers-frame`, `#in-transfers-frame`, `#out-transfers-frame`, `SIVisible#trades-transfers-frame-visible`; Transfers > Activity) and `MessagesToolBlock` (`VisualElement#Messages`; Inbox). Both are one navigation away from the M3 screens, so a third capture closes H-pct if the layouts are the live ones; if not, it stays open (not an exit blocker).

## 5. Plugin 0.3.1-capture (built, not installed): sheet content for the empty-named sheets
- New `sheet_content` line in the capture, once per distinct StyleSheet instance attached to a captured element, written before that element: owner path, index, name, instance id, rule count, property count, import count, `signature`, and a rule sample (80 rules for unnamed sheets, 6 for named). Read-only property reads of the members `ColourTrace` already uses; a failure writes an `error` field and never skips an element.
- `signature` = sha1 of "<selectors joined ', '>#<property count>\n" per rule in rule order; `captures.sheet_signature(rules)` computes the same from any indexed sheet and `Capture.match_sheets(sheets)` reports `identified` / `ambiguous` / `not-found` / `unreadable` with candidates. Tested on synthetic captures (identified, ambiguous with two same-content sheets, not-found, rule-count mismatch, unreadable).
- Calibration plan: the six NAMED root sheets must come back `identified` as themselves first. If they do not, the signature method is wrong and no verdict on the three unnamed sheets is drawn from it.
- DLL: `inspector/staging/capture-0.3.1/FM27Inspector.dll`, 61,440 bytes, sha256 `7940B49FBEDD9BE268BA303567549367C158454E3F5E2B93CDF052BA105C1665`; version string `0.3.1-capture`; default `DumpFolder` is the C path (checked in the binary). Source: `inspector/plugin`.
