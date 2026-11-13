# Phase 7 spike verdicts: tile position writes and table views

Game 27.0.1.2503222 (inspector `status`, 2026-11-13), UnityPy 1.25.4. Everything below ran on scratch copies outside the game, or read the game's files; nothing was installed.
The in-game tolerance of a moved cell is the one thing offline work cannot decide; it is the check that is waiting on you (see PHASE7-EVIDENCE.md).

## 1. Tile layout: position-only writes

**Where the data is.** Grid compositions are MonoBehaviours with `m_gridComponents[]` in three bundles: `ui-tileslayouts_assets_all` (1,697 compositions, 5,024 cells),
`ui-tactics_assets_all` (53, 146) and `ui-dynamiccardcollections_assets_all` (73, 240): **1,823 compositions, 5,410 cells**. A cell is `{m_elementID, m_location{x,y,width,height},
m_minSize, m_maxSize, flags, m_configDescriptionKeys, ...}`. None of these bundles is in the FM27_LayoutMCP `bundles` table; the index knows them only through the `bundle` column of `compositions`.

**Verdict 1: rewriting every cell unchanged is exact.** `save_typetree` of every composition of the three bundles gives a bundle whose object set and every object digest equal vanilla
(0 differing objects in 4,186 + 209 + 113 objects). This is the earlier MCP "no-op" spike, now over all 1,823 compositions, and it is a test (`tests/test_phase7.py`).

**Verdict 2: one position edit changes exactly the objects it should.** Moving one cell changes exactly one object of the bundle (the composition) and exactly one leaf of its typetree
(`/m_gridComponents[i]/m_location/x`); a two-cell swap changes two leaves. No pool, no other object, no field order changes.

**Verdict 3: the gate can prove "built = vanilla plus exactly the asked edits".** `tiles.check_ops` diffs vanilla and built compositions leaf by leaf and requires the set of differing leaves to
equal the x/y of the addressed cells, holding the asked-for values. A build made with a different position than the edit list fails it ("x is 7, expected 6"); an unexpected extra change would fail it
("unexpected changes at ..."). The generic checks (object set equal, every untouched object identical to vanilla) run on the whole bundle first. An edit carries guards (`cell_id`, `from`): if the
composition no longer holds that cell at that position (game updated), the build refuses with a message instead of writing.

**Verdict 4: size stays blocked, measured.** On the real index 5,162 cells have configs; **4,724 of them have exactly the size of one of their configs** (the figure in the spec, reproduced by a test). A
cell's size is therefore derived from its config and would be overwritten or contradicted; the writer refuses any size change and any config change (`tiles.ops_for`, `placement.check`). Two cells have
`x = y = -1` (the game places them itself); the editor treats -1 as "auto" and refuses to move them.

**What is not proven: that FM27 draws a grid with moved cells.** The data side is exact; the game side needs one in-game check on a test project. `p7-tile-test` is built for it: on the Tactics screen,
team-instructions tab, the pitch and the instructions block swap sides (Standard 12 columns and Large 16 columns). Until that is seen, position writes are *built and gate-proven* but not *seen in game*.
Risks I could name and not test: a composition whose `m_instantiationOrder`/optional slices assume a cell order; compositions the game rebuilds at run time; user layouts (`.fmf`, below) overriding a bundle default.

**Verdict: position writes are unblocked pending that one in-game look. Size writes stay blocked.**

## 2. Table views (ui-tableviews, ui-tablefactories): decoded

- **835 table views**, each `m_tableView.m_tableConfig[]`: an ordered column list, every entry `{m_columnID, m_columnMetadata{m_widthOverride, m_minWidthOverride, m_required,
  m_sortingDisabled, m_priority, m_applicableBreakpoints, conditions, m_titleTranslationIdOverride}}`. 6,197 column entries over 1,080 distinct ids. Order is list order, visibility is presence, width is the
  override (0 = the column's default). A 65-object `...TableViewSettingsCollection` set holds the user-facing "choose columns" menus; it is not needed for the three edits.
- **243 table factories**, each `m_rowData[]`: one entry per column id it can draw: default and minimum width, header translation id, value bindings and `m_uxmlRef` (the GUID of the layout that
  draws the cell, e.g. `PlayerPortraitNamePositionCell`). `PlayerTableFactory` alone has 622 cells.
- **The view-to-factory link is by column ids:** 808 of 835 views have all their columns defined by exactly one factory, 10 more at 90 percent or better, 14 partly, 3 not at all (their columns come from other
  mechanisms). The editor shows the coverage and refuses to add a column the factory cannot draw.
- **Edits proven offline:** set width, hide, show (modelled on an existing entry of the same view), move. On the real `SquadKeyPlayersTableSmall` (2 columns; 620 more available) a four-op patch changes exactly one
  object of `ui-tableviews`, the gate (`tables.check_patches`) re-derives the expected column list from vanilla plus the ops and matches it, and a build made with another width fails it.

**Write route decision: the bundle, not the user `views` folder.** `Documents/Sports Interactive/Football Manager 27/views` holds 14 `.fmf` files of 1.0 to 1.5 KB each (the user's own views, e.g. `main`, `WTS Contract
View`). They are opaque: every file starts `02 01 'afe' 2e 08 00 00`, the rest has 7.8 bits/byte of entropy, no zlib/deflate stream, no readable strings. They carry only a user's customisation, not the game's column
sets, and cannot be read here, so they are not a write target. The bundle carries the full column set and decodes completely. Caveat that needs your eyes: if you have a custom `.fmf` for a table you edit,
the game may prefer it over the bundle default.

**Verdict: table read and the three edits are feasible and built on the bundle route; the in-game check is `p7-table-test`.**

## 3. Real data (spec warning 10)

The layout features had only ever run on fixtures. Against the real FM27_LayoutMCP index and the game's bundles: the index's 1,823 compositions and 5,410 cells equal the bundles cell by cell (0 mismatches);
the dump built from it validates against the editor's `fmlayout-index/2` contract with 0 errors after the editor adapted to the real data in these places (the editor adapted, not the index):

| disagreement | adaptation |
|---|---|
| compositions live in 3 bundles the index does not list; no `panels` table | exporter reads the composition bundles and `ui-panelids` directly, hashes them into `meta.source.bundles`; compositions carry `bundle` and `path_id` (optional contract keys) |
| 2 cells have `x = y = -1` | contract accepts -1 as "auto"; `placement.check` refuses to move such a cell |
| `max = 0` means unlimited, min can exceed it | the min-above-max rule applies only when max > 0 |
| area anchors in `areas.json` are regexes with scopes | contract allows `layout_name_regex`; the exporter derives the layout-to-area map |
| flags are integer columns, alignments integers | exporter turns them into flag names and text, the editor keeps carrying unknown flags |
| a grid is attached to the layout that hosts it, usually an included template, not to the panel root | `layout.screen` and `layout.screens` collect the sets of every layout the panel reaches (`TacticalPlannerTool`: 4 sets, 12 tiles; 409 of 623 panels have tiles) |

Staleness: the imported dump is `fresh` against the snapshot's reference hashes (catalog `dfa1892e861e`, 18 bundles named).
