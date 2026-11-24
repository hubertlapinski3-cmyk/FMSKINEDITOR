# Game Layout coordinates

One shared module, `skin_editor/layoutspace.py`, owns the three spaces. The canvas,
the inspector, legality, `custom_layouts.apply_canvas_edits` and the preview all call
it; no path keeps a second copy of the arithmetic. Every rule below cites the decoded
method or an earlier report. No constant is fitted to a measured case.

## The three spaces

| space | what the numbers are | where they live |
|---|---|---|
| **design** | the custom file's main-grid cells, in the composition's own design grid | `m_gridComponents[i].m_location` |
| **slot** | an optional-slice entry, stored relative to its zone base | `m_optionalSlices.<m_right\|m_bottom>[i].m_location` |
| **runtime** | the grid the screen actually shows after growth and compaction | `render.preview` hosts (col, row) |

The bundle's `SquadComposition-Large` (dump `layout-dump-C-27.1.0.2505117.json`,
bundle `ui-tileslayouts_assets_all.bundle`, path_id 4181126630784745451) is the worked
example: design `20 x 10`, runtime `30 x 16` at the pinned measured setting
(`2560x1440 windowed, Information Display Small, Text Scaling Larger`, `SquadScreen`
`GridLayoutElementContent` rect `(15.6, 85.9, 2468.8, 1319.3)`), main cells Atmosphere
(16,8,4,2), Tactics (16,0,4,4), Training (16,4,4,4), HumanActionsControlPanelBlock
(0,0,16,1), FirstTeamOverview (0,1,16,9); bottom slots SquadHierachy (16,0,4,2),
MedicalCentre (16,2,4,2), Loans (16,4,4,2).

> **Why UI3 showed `31 x 17` and UI4/UI5 show `30 x 16`:** UI3 passed raw whole-window
> dimensions (`2560x1385`) to `screen.grid_dims` without subtracting the panel chrome and
> title bars (`round((2560-24+16)/82) = 31`, `round((1385-24+16)/82) = 17`), shifting
> right-strip cells by `31 - 20 = 11` (Atmosphere at column 27). UI4/UI5 pin the preview
> viewport to `2560x1440 windowed, Small, Larger`, which selects `MEASURED_PANEL_RECTS`
> (`SquadScreen` content rect `2468.8 x 1319.3`) and `screen.grid_dims_content`
> (`floor((2468.8+16.6)/82) = 30`, `floor((1319.3+16.6)/82) = 16`), giving the measured
> `30 x 16` grid with Atmosphere at column `16 + (30 - 20) = 26`.

## design -> runtime

The right strip keeps its distance from the design right edge. Growth extends the
middle column (`BuildGraph -> Deflate -> Inflate -> ApplyGraph`), so a right-strip cell
shifts by the growth surplus:

```
runtime.x = design.x + (runtime.cols - design.cols)
runtime.y = design.y
```

`layoutspace.main_to_runtime`. Evidence: `docs/rea/STAGE-REA-WIN-2.md` (growth is the
graph pass; `ApplyGraph` `0x19a61c0` derives positions), `STAGE-REA-WIN-1.md`
(`Compact` `0x19a7e20` orders cells by bottom extent `y+h`). The canvas shows the exact
result from `render.preview`, not this formula, for cells that grow.

Reverse: `runtime_to_main` subtracts the same surplus.

## slot -> runtime

`PrepareContent` `0x19a1400` and its local `GetSliceZoneOffset` `0x19a3e90` resolve a
slice as `zone offset + serialized (x, y)`. The zone offset base is the mandatory
content extent (`GridLayoutElementBase +0x418/+0x41c`, the design width/height) plus
the captured accumulator. `PrepareContent` rejects a slice when `x < 0`, `y < 0`,
`x + w > grid width` or `y + h > grid height`.

- `m_bottom` (zone 6, `GridOptionalSlices.GetSortedZone` `0x19b77c0`): the accumulator
  is the grid's extra width, and the base has no mandatory-width term:
  ```
  runtime.x = (runtime.cols - design.cols) + slot.x
  runtime.y = design.rows + slot.y
  ```
  Squad: `(30-20) + 16 = 26`, `10 + 0 = 10`.
- `m_right` (zone 4): the accumulator is zero and the base adds mandatory width:
  ```
  runtime.x = design.cols + slot.x
  runtime.y = slot.y
  ```

`layoutspace.slot_to_runtime` / `runtime_to_slot`, with
`layoutspace.zone_accumulator` and `layoutspace.slice_zone_offset`. Evidence:
`docs/rea/STAGE-REA-WIN-4.md` (Y3), `docs/rea/STAGE-REA-WIN-3.md` (X4/GetSortedZone).

Reverse:
```
slot.x = runtime.x - ((runtime.cols - design.cols) [m_bottom] or design.cols [m_right])
slot.y = runtime.y - (design.rows [m_bottom] or 0 [m_right])
```

## Overlap and legality

- main cells are compared with each other in **design** space;
- slots are compared with each other inside **their own zone** in **slot** space;
- the two kinds are never compared with each other.

`layoutspace.overlaps` is the per-space check. A partial overlap is refused; an exact
duplicate stays the LT2 C5 warning (the game takes the first match). After conversion,
`customlayout.apply_edits` renders the staged object and runs
`layoutspace.runtime_problems` over the runtime hosts: an off-grid tile or a runtime
overlap blocks Apply even when the stored numbers look legal.

## Why the UI3 drag broke

The UI3 edit was `Atmosphere x 16 -> 15` and `Training x 16 -> 15, y 4 -> 6`. The
canvas had drawn the grown 31-column runtime, so the drag felt like one column inside
the right strip, but it wrote design `x = 15`. In design space that intrudes into
FirstTeamOverview `(0,1,16,9)`; in runtime the preview places Atmosphere at
`(15,17,4,2)`, outside the 31x17 grid, and drops the main tile. The design-space check
now names it `design: ...` instead of a cross-space comparison.

## Fullscreen profile and FS1 panel content rects (2026-11-23)

- **Default viewport profile:** `2560x1440 fullscreen, Small, Larger` (UI scale `1.024`,
  `Screen = 2560x1440`, `fullScreen = True`, `fullScreenMode = FullScreenWindow`).
- **Measured `SquadScreen` content rect:** `GridLayoutElementContent` =
  `(15.6, 85.9, 2468.8, 1319.3)` -> runtime grid `30 x 16` (identical cell grid to
  windowed `2560x1440`, with Atmosphere at column `26`).
- **Selectable windowed profile:** `2560x1440 windowed, Small, Larger` remains selectable
  with its own panel content rects and confidence labels; windowed measurements never
  count as `measured` in fullscreen (and vice versa).
- **All optional slice zones:** `layoutspace.FILE_ZONES` and `customlayout.runtime` support
  all eight `SI.UI.GridSliceZone` zones (`m_topLeft` 0, `m_top` 1, `m_topRight` 2,
  `m_left` 3, `m_right` 4, `m_bottomLeft` 5, `m_bottom` 6, `m_bottomRight` 7).
- **FS1 sweep & scoring (initial):** 123 compositions captured (`docs/rea/data/fullscreen-2k-measurements.json`,
  `tools/score_fs1_fullscreen.py`); 122 scored (`112` `measured` <= 1.5 px across all
  cells, `10` `measured mismatch` with per-cell deltas and inferred causes; `1` hidden tab
  unmeasurable).

## FS2: Verified fullscreen rect, 0 px nested padding, slot-strip reservation (2026-11-23)

- **Fullscreen rect verified live (not copied):** `20261123T123035Z/sweep-results.json`
  (`started_utc: 2026-11-23T12:30:35Z`) logged `Screen = 2560x1440`, `fullScreen = True`,
  `fullScreenMode = FullScreenWindow`, `scale = 1.024`, and live `squad_baseline`
  `GridLayoutElementContent = [15.6, 85.9, 2468.8, 1319.3]`. Both fullscreen and the earlier
  measured windowed `2560x1440` baseline rendered into a `2560x1440` Unity backbuffer at
  `scale = 1.024` (`2500 x 1406.25` UI units), so extra rows fullscreen vs windowed = **0**
  (`Squad 16 vs 16`, `Portal 16 vs 16`, `PlayerReport 13 vs 13`).
- **Bundle-derived container padding (`0 px` vs `12 px`):** `preview.composition_padding`
  uses `GridLayoutSettings.m_padding` (`12`) or `0` when `IgnoreOuterPadding` (`+0x408`,
  get `0x19a4ca0`, set `0x19a55e0`) applies — set either from UXML
  (`BindableGridLayoutElement.set_IgnoreOuterPadding` `0x1821200` /
  `InitializeGridLayoutElement` `0x181ad00` at `+0x2ea..+0x2fa`) or by code in
  `FixedAspectGridLayoutElement.AttachToPanelCallback` (`0x1989120`) /
  `FlexibleAspectGridLayoutElement.AttachToPanelCallback` (`0x1989d70`) via
  `GetFirstAncestorOfType<GridLayoutElementBase>()` (`0x180ca3260`) when nested inside
  another grid's tile.
- **Grid size formula (`GridLayoutSettings.GetGridSize`, `0x198dd40` / `0x198dde0`):**
  `round((extent - 2 * padding + spacing) / (cellSize + spacing))`, with
  `m_cellSize = (66, 66)`, `m_padding = (12, 12)`, `m_spacing = (16, 16)` from
  `GridLayoutSettings` (`globalobjects_assets_all.bundle`). Extents within `1 px` of a
  `round()` boundary are flagged `grid_size_uncertain`.
- **Slot-strip reservation & single shared slot function:** `layoutspace.place_zone_slots`
  is shared by both `rea_rule.place_rule` and `layoutspace.slot_to_runtime` (EDIT and
  RUNTIME panes). `PrepareContent` (`0x19a1400`), `AdjustOccupiedSpace` (`0x19a3d80`), and
  `GetSliceZoneOffset` (`0x19a3e90`) are cited for bounds checks and `bottom_reserved` /
  `right_res` clamping; `right_edge_fixed` / `anchored_bottom`, `mandatory_ids` exclusion,
  `has_flex` on `m_right`, `oy == 0` right-strip stacking, and `axes = (0, 1)` for
  `m_layoutMode = 4` are marked **fitted on FS1**.
- **FS2 rescore:** `121 / 122` scored compositions match within `1.5 px` (`0` regressions on all
  previously passing FS1 cases and `27 / 27` windowed cases); `1` honest `measured mismatch`
  remains (`3_Tiles_8x4-Expandable_2x4x2`, where `0 px` padding fixed x-offset to `-0.1 px`
  and `FitHeightToContent` shrinks the top message card to 5 rows vs 8 in `m_gridComponents`).
- **ALL1 & Build `27.1.1.2511875` (`2026-11-24`, `bc824c385acb`):**
  - Full Information Display sweep (`M1` Small `scale=1.024` `30x16`, `M2` Medium `scale=1.22488` `25x13`, `M3` Large `scale=1.52381` `20x11`, all `Breakpoint = Large`): `143 / 1,815` editable compositions measured (`M1` `140/141` pass, `M2` `139/141` pass, `M3` `138/139` pass). See `docs/rea/ALL1-COVERAGE.md`.
  - **RVA map (`27.1.0.2505117` -> `27.1.1.2511875`, uniform `-0x100` in `SI.UI`/`SI.Bindable`/`FM.UI`, `-0x170` in `GameWorldTabsAndBookmarksModule`, `0` behaviour changes):**
    - `ApplyGraph`: `0x19a61c0` (`27.1.0.2505117`) -> `0x19a60c0` (`27.1.1.2511875`)
    - `Compact`: `0x19a7e20` (`27.1.0.2505117`) -> `0x19a7d20` (`27.1.1.2511875`)
    - `PrepareContent`: `0x19a1400` (`27.1.0.2505117`) -> `0x19a1300` (`27.1.1.2511875`)
    - `AdjustOccupiedSpace`: `0x19a3d80` (`27.1.0.2505117`) -> `0x19a3c80` (`27.1.1.2511875`)
    - `GetSliceZoneOffset`: `0x19a3e90` (`27.1.0.2505117`) -> `0x19a3d90` (`27.1.1.2511875`)
    - `GridOptionalSlices.GetSortedZone`: `0x19b77c0` (`27.1.0.2505117`) -> `0x19b76c0` (`27.1.1.2511875`)
    - `GridLayoutSettings.GetGridSize`: `0x198dd40`/`0x198dde0` (`27.1.0.2505117`) -> `0x198dc40`/`0x198dce0` (`27.1.1.2511875`)
    - `IgnoreOuterPadding` get/set: `0x19a4ca0`/`0x19a55e0` (`27.1.0.2505117`) -> `0x19a4ba0`/`0x19a54e0` (`27.1.1.2511875`)
    - `BindableGridLayoutElement.InitializeGridLayoutElement` / `set_IgnoreOuterPadding`: `0x181ad00`/`0x1821200` (`27.1.0.2505117`) -> `0x181ac00`/`0x1821100` (`27.1.1.2511875`)
    - `FixedAspectGridLayoutElement.AttachToPanelCallback` / `FlexibleAspectGridLayoutElement.AttachToPanelCallback`: `0x1989120`/`0x1989d70` (`27.1.0.2505117`) -> `0x1989020`/`0x1989c70` (`27.1.1.2511875`)
