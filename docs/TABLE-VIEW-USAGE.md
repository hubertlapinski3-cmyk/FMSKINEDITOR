# Where a table view is used (reverse linkage)

Question this answers: "which screen shows table view X?" Answered from the FM27_LayoutMCP index, read-only. Build 27.0.1.2503222, 2026-11-13.

## How views are linked to layouts

Nothing in the index links a table view to a layout by an ordinary asset reference (`data_refs` and `element_refs` hold no entry for any view GUID). The link is a
visual-scripting `InitFunction` on the layout's `SI.Bindable.StreamedTable` element: its argument bytes (`m_inputs.m_variable.m_argumentBytes`) spell
`...SI.VisualScripting.AssetReferenceVisualArg <32-hex view GUID>`. Decoding the bytes and matching the GUID against `data_guids` (bundle `ui-tableviews`) gives
**355 of the 897 views, 528 references**. The other 542 views are chosen by code or are saved user views and cannot be traced from layouts.

Layout to screen: a layout named `<Name>Tile_WxH` is the (W, H) configuration of the tile descriptions whose `tile_description_configs` point at it; `cell_configs` lists the
compositions (screens at a breakpoint) whose cells offer that tile. A cell offers all configurations; the cell size picks one, so the screen list is "where it can appear".

Code: `skin_editor/table_usage.py`; engine call `tables.usage` (writes `table-view-usage.json` to the workspace); after that `tables.view` returns `used_by` and `used_by_summary`.
Tests: `tests/test_table_usage.py`.

## Two ways a tile gets its columns (learned in the c2 in-game check)

1. **A table view asset:** the `StreamedTable`'s `InitFunction` (target `446475dd...`) takes a view GUID. Editing the view (`tables.edit`) changes the tile. `LoansTile_8x4` and `LoansTile_6x6` work this way.
2. **A list of column ids in the layout:** the `InitFunction` (target `07913d3a...`) takes a `StringListVisualArg` such as `portrait-name`, `club-icon-name-small`, `average-rating`. No view is involved; the columns are in the layout and
   only a layout (uxml) edit changes them. `LoansTile_4x2` works this way, and it is the Loans tile on the Squad overview. The sqlite index stores such blobs only as `<N bytes>`, so this must be read from the bundle.

A view found by this map is therefore **not guaranteed to be what is on screen**: the tile's size picks the layout, and the layout may not use a view at all. Confirm the on-screen tile's template (inspector element `tile-wide-4x2` etc.) first.

The main player table on Squad > Overview is a third case: the view `FirstTeamTableAttributesPhysical` (selected by code from the "Physical" view choice, no layout references it).

## SquadKeyPlayersTableSmall

- Used by exactly one layout: **`FirstTeamTile_4x4`** (the `StreamedTable` element). Its larger sibling `SquadKeyPlayersTable` is used by `FirstTeamTile_8x4`; `FirstTeamTile_4x8` uses `FirstTeamTile4x8TableViewSettings`.
- `FirstTeamTile_4x4` is the **4x4 configuration** of `SquadFirstTeamTileDescription` (cfg 3). `SquadFirstTeamSecondaryTileDescription` has the same layout but no composition offers it.
- `SquadFirstTeamTileDescription` is offered by 23 compositions, at cell sizes 2x2, 4x2, 4x8, 8x4, 8x8, 8x10. The cells that are **4 wide and tall enough for a 4x4 configuration** are the
  `InternationalYouthSetupIndividualOverviewComposition` family (Small/Standard/Large, 4x8 cell). The Squad screens offer the tile at 8x4, 8x8 and 8x10, which draws `FirstTeamTile_8x4` and
  `SquadKeyPlayersTable`, not the Small view.
- **Conclusion:** the Small view is not on the club Squad overview. It belongs to the International Youth Setup overview (a national-team job), not reachable in a Borussia Dortmund club career. The first table test (`p7-table-test`) installed and ran
  cleanly but its table was not on screen, which this explains.
- The seen-in-game proof of 2026-11-13: Squad overview showed the Physical squad table (a user/default view) and the Loans tile; neither is this view.

## PlayerLoansTileTable (the retarget)

Used by `LoansTile_8x4` and `LoansTile_6x6`, configurations of `SquadLoansTileDescription` (8x4, 8x5, 6x6; 11 compositions). Columns: `portrait-name` 320, `club` 190, `club-icon-name-small` 70, `loan-average-rating` 70.
The Loans tile seen on Squad > Overview (Player, club code with badge, rating) matches `portrait-name`, `club-icon-name-small`, `loan-average-rating`. Test project `p7-table-test-2` edits this view.

## Other views seen on the Squad screens (from the same map)

`FirstTeamTile_4x8` -> `FirstTeamTile4x8TableViewSettings`, `SquadCurrentInjuriesTile_4x4/8x4` -> `SquadCurrentInjuriesCompactTable/Table`, `SquadHappinessTile_4x4/8x4` -> `SquadHappinessMiddleTable/LargeTable`,
`SquadHierarchyTableBlock` -> `SquadHierarchyManagerTable/PlayersTable`, `SquadRecentlyReturnedTile_4x4/8x4`, `SquadDynamicsTile_8x4` -> `PlayerBuyInTable`. The main player table on the Squad Overview (view "Physical") was not
found by this map; its name was not searched for individually, so it may be a saved or default view chosen by code.
