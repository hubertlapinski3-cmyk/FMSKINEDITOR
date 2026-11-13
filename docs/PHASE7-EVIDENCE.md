# Phase 7 evidence (2026-11-13, game 27.0.1.2503222)

Status: **spike verdicts documented** (`docs/PHASE7-TILE-SPIKE.md`); **real-data connection done and verified offline**; **tile editor and table browser/editor built**; **position writes seen in game: PENDING (user)**;
**table view edit seen in game: PENDING (user)**. Nothing here is called done on tests alone: the two in-game checks are the exit criteria and are open.

## What was verified, and how

| claim | evidence |
|---|---|
| all 1,823 compositions / 5,410 cells rewrite unchanged | 0 differing objects, object sets equal, 3 bundles (4,186 / 209 / 113 objects); `tests/test_phase7.py::RealTiles` |
| one move changes exactly the objects it should | 1 object, 1 leaf (`m_gridComponents[i]/m_location/x`); a swap 2 leaves; gate fails a wrong build, guards refuse a moved target |
| index equals bundles | `layout_export.crosscheck`: 1,823 compositions, 5,410 cells, **0 mismatches** |
| dump from the real index is a valid `fmlayout-index/2` | `layout_dump.validate`: 0 errors (after the adaptations in the spike document); imports as **fresh** (catalog `dfa1892e861e`) |
| real screens resolve | 623 panels, 409 with tiles; `TacticalPlannerTool` -> 4 grid sets; `layout.screen` 0.2 s |
| size stays blocked for a measured reason | 5,162 cells with configs, 4,724 with the size of one of their configs (test on the real index) |
| tables decode | 835 views, 243 factories, 808 views fully covered by one factory (PlayerTableFactory 622 cells); 4-op patch on `SquadKeyPlayersTableSmall`: 1 object changes, gate matches, a wrong build fails |
| user `.fmf` views | opaque (entropy 7.8 bits/byte, no stream, no strings); not a write target; bundle route chosen |
| bug found on real data and fixed | deleting a project left its stored position edits behind, so a new project of the same name inherited them (`project.delete` now moves the file too) |
| error boundaries from the start | Tiles and Tables are wrapped in `Guard`; a Vitest test feeds a payload that crashes a render and checks the guard shows the error |

Test totals at the time of writing: 212 Python tests (1 skipped), 22 Vitest tests, `tsc` clean.

## Builds prepared for your in-game checks (not installed)

Both are built from the vanilla snapshot; both gates passed with 0 failures. **The game folder currently holds the `p6-class-test` bundles, so Restore stock first** (the tamper check blocks installs while
they are there, which is the safe behaviour).

1. **Position writes - project `p7-tile-test`** (bundle target; build `build/p7-tile-test/20261113T172840Z`, gate: `tile_moves_checked: 4`, 1 untouched bundle checked; changed file: `ui-tactics_assets_all.bundle`).
   Edits: `TacticalPlannerTeamInstructionsTabComposition-Standard` pitch 0 -> 6, instructions block 6 -> 0; `...-Large` pitch 0 -> 10, block 6 -> 0.
   Check: Restore stock, install this build (game closed), start the game, Tactics, the Team Instructions tab (Standard and Large are the two breakpoints; which one you see depends on your window size).
   Expected: the instructions block on the left, the pitch on the right. Report what you see, including a layout that breaks or a tab that goes blank. Then Restore stock.
2. **Table view edit - project `p7-table-test`** (build `build/p7-table-test/20261113T173106Z`, gate: `table_patches_checked: 1`; changed file: `ui-tableviews_assets_all.bundle`).
   Edits to `SquadKeyPlayersTableSmall`: first column 300 px wide, columns `age` and `club` added after it (club moved after age). I do not know which Squad screen tile uses this "Small" key-players table:
   look at the Squad overview. If nothing changes there, tell me which table you see and I will point the test at it (the views are listed in the Tables view, key V). A custom `.fmf` view of yours could take precedence.

## Studio

T (tile layout): screen list (409 with grids), host/set/breakpoint picker, SVG canvas, drag or numeric x/y, size shown fixed, locked and auto cells refuse, overlap flagged and confirmed, validation list from `placement.check`, commit
stores placement edits, stored edits listed with revert. V (table views): list, column table with widths, draws (cell layout names), up/down/hide, add column from the factory's cells, revert. "Load the layout index" builds
and imports the dump from the MCP index when none is imported (`layout.export_index`).

## Not done / carried over

- Position writes and table edits seen in game (user). Config changes and size changes are not written (size is config-derived; blocked).
- Dragging uses pointer events and was tested through the numeric path in jsdom, not with a real mouse in the desktop window.
- Icons/layouts diff and layout item states in the update flow: close at the next FM patch (as agreed). Table and tile edits are not yet part of the update diff's item states.
- Phase 8 not started.

## Pre-session preparation (2026-11-13 19:04 local, nothing installed, FM27 not launched)

Done offline so the in-game session is one run; the script is `docs/INGAME-CHECKLIST.md` (also in Studio, button ?).

- **Restore stock:** the existing restore (`restore vanilla`) was run headless and found nothing to copy: the game folder was already stock (the install log has no p6 install entry, so it was restored outside this editor,
  most likely by hand or by Steam). Verified by hash: 67 of 67 UI bundles equal the stock reference, the p6 layout bundle hash is `6ed36b0dbfd9` = reference, update.status `same`, tamper `clean`, the 16 snapshot copies equal the live files.
  New command `python -m skin_editor verify-stock` prints one line (`STOCK: 67 of 67 ...`, exit code 0) and is used after every restore in the checklist.
- **Packages:** `p7-tile-test` id `20261113T180410Z` (gate 0 failures, 4 moves checked, plan digest `ac498b6a...`, `ui-tactics_assets_all.bundle` `9559d5968e9d`) and `p7-table-test` id `20261113T180415Z` (gate 0 failures, 1 table patch checked,
  digest `ce02464d...`, `ui-tableviews_assets_all.bundle` `b6bb58931c69`). Builds are deterministic: rebuilding gave identical bundle hashes and digests. The build now writes a `package.json` (project, id, profile, plan digest, file hashes,
  gate result) next to the bundles and mirrors it to `projects/<project>/packages/`; before this the code had no packages, only `build/<project>/<id>/build-report.json`. The game folder was untouched by every build.
- **Font readiness:** P6 font test skin native gate 0 problems, its single `url("fonts/impact.ttf")` resolves inside the skin folder, the font file is byte-identical to `C:\Windows\Fonts\impact.ttf`. Mine: identical to a fresh export of its project (8 files, 53/190/3, 0 problems).
- **Fresh engine:** the old engine was stopped (none running); `FM Skin Studio.bat` started a fresh one (12 s, new pid, new session token), served `update.status`, `docs.checklist` and `builds.list` over RPC and the Vite dev server served the new view;
  closing the window stopped the window, both engine processes, Vite and the bat within one second.
- **Found while preparing:** an empty `src` on image thumbnails made the webview request the page again (fixed); a mistaken PowerShell write emptied `studio/src/App.tsx` and it was restored from the session's file history (version
  before the write), re-verified by `tsc`, 25 Vitest tests and the served module.

## In-game session 2026-11-13 (build 27.0.1.2503222), by hand with a read-only inspector

Rules after a crash: the inspector crashed FM27 twice (access violation `0xc0000005`, `coreclr.dll`, fault offset `0x1d1fdd`) when asked to click the skin dropdown; see `inspector-spec.md` section 9. After that every
UI action was done by hand and the inspector only took screenshots and element queries, one call at a time. No crash occurred during any manual action.

- **Font (Phase 6):** body text rendered in the Impact file, switched back to Mine cleanly; 217 log lines "impact FontAsset is invalid" (see `PHASE6-FONTS-SPIKE.md`). Phase 6 closed on visual evidence.
- **Tile (Phase 7 tile route): proven.** `p7-tile-test` `20261113T180410Z` installed (hash `9559D596...C918B2` = package; `verify-stock` NOT STOCK with exactly `ui-tactics_assets_all.bundle`; backup `20261113T201232Z`).
  Tactics > Team Instructions at Information Display Small (Text Scaling Larger) and at Large: instructions on the left, pitch to its right (inspector: instructions block at x=40, pitch tabs at x=1274 at Small and x=865 at Large). Closed, restored, `STOCK: 67 of 67` (backup `20261113T201659Z`).
  Screenshots `tile-1-teaminstructions-first`, `tile-2-teaminstructions-large`. First position write proven in game.
- **Table (first target) inconclusive:** `p7-table-test` `20261113T180415Z` installed (hash `B6BB5893...E62C`) and the game ran, but the Squad overview showed no Age/Club change: the edited view `SquadKeyPlayersTableSmall` is the 4x4 First Team tile
  configuration, not on the club Squad screen (mapping in `docs/TABLE-VIEW-USAGE.md`). Restored, `STOCK: 67 of 67` (backup `20261113T202224Z`).
- **New:** `table_usage.py` / `tables.usage`: reverse linkage of table views to layouts, tiles and compositions (355 of 897 views, 528 references), shown by `tables.view` as `used_by`. Tests `tests/test_table_usage.py`.
- **Retarget:** `p7-table-test-2` edits `PlayerLoansTileTable` (hide `loan-average-rating`, widen `club-icon-name-small` 70 to 140), a table seen on screen in this session (Squad > Overview, Loans tile). Package `20261113T202702Z`,
  gate 0 failures, 1 table patch checked, 1 untouched bundle checked, plan HideColumn x1 + SetColumnWidth x1, plan digest `50c1bf8e586c...`, `ui-tableviews_assets_all.bundle` `fbb0d9ec19df` (vanilla `90e56b4e0064`). Step c2 of `docs/INGAME-CHECKLIST.md`.

### c2 result: Loans tile unchanged, and why (same session, 2026-11-13)

`p7-table-test-2` `20261113T202702Z` was installed (hash `FBB0D9EC...93975ED` = package, `verify-stock` NOT STOCK with exactly `ui-tableviews_assets_all.bundle`, backup `20261113T203225Z`) and the game ran without error.
**The Loans tile was unchanged**: columns Player, Club (code + badge), Rating (values 7.13, 6.96), all still present; no wider club column. Screenshot `c2-table-27_0_1_2503222-20261113.png`; tile tree `ui-dumps/c2-loans-tile-tree-27_0_1_2503222-20261113.json`.

Cause, read offline from the game's own bundle (`ui-visualtreeassets_assets_gameworldvisualtreeassetpreload`, `LoansTile_4x2`):

- The tile on screen is `LoansTile_4x2` (inspector: template `tile-wide-4x2`, 312x148 px). That layout does **not** select a table view asset. Its `StreamedTable` `InitFunction` targets a different function (guid `07913d3a...`)
  whose argument is a **string list of column ids**: `portrait-name`, `club-icon-name-small`, `average-rating`. The columns are written in the layout, so no table view can change them. My edit targeted `PlayerLoansTileTable`, which only the
  8x4 and 6x6 Loans layouts use (8x4 confirmed in the bundle: `InitFunction` argument = view guid `79e69ca9...`).
- My reverse map (`table_usage.py`) listed the tile's sizes 8x4, 8x5, 6x6 because only those layouts carry a view GUID; the 4x2 layout carries none, and the index stores the blob only as the placeholder `<606 bytes>`.
  **Rule going forward: a tile layout whose `StreamedTable` has a string-list init function lists columns itself and is a layout (uxml) edit, not a table-view edit.** `TABLE-VIEW-USAGE.md` records this.
- Not a failure of the table write route: the edit was applied to a view that the visible tile does not read. Equally, the route is **not yet proven in game**.

First table test, same reading: `p7-table-test` (`SquadKeyPlayersTableSmall`) installed and ran cleanly; its table (the 4x4 First Team tile configuration) is not on any club Squad screen. Its non-effect says nothing against the write route either.
Neither test has put an edited table view on screen yet, so the table route stays open.

**Retarget 3: `p7-table-test-3`**, the Squad overview's main table, view **`FirstTeamTableAttributesPhysical`** (12 columns: `position-dropdown` = "Picked", `inf-team` = "Inf", `portrait-name` = "Player", `portrait-shortname`,
and eight `attribute-*` columns Acceleration ... Strength), which is exactly what the screen showed. Chosen by code (no layout references it), so it was not in the map. Edits: **hide `attribute-jumping-reach`** and **move `attribute-pace` to right after `portrait-name`**.
Package `20261113T203622Z`: gate 0 failures, 1 table patch checked, 1 untouched bundle checked, plan HideColumn x1 + MoveColumn x1, plan digest `83965de62d5c...`, `ui-tableviews_assets_all.bundle` `1f1c0b22237a`. Step c3 of the checklist.

### c3 result: PASSED. A table-view edit seen in game (2026-11-13, build 27.0.1.2503222)

Stock restored first (`STOCK: 67 of 67`, backup `20261113T203842Z`), then `p7-table-test-3` installed (backup `20261113T203843Z`): installed hash `1F1C0B22...271D64` = package, `verify-stock` NOT STOCK with exactly `differs from stock: ui-tableviews_assets_all.bundle`.
Squad > Overview, the main squad table, header row read from the screenshot `c3-table-27_0_1_2503222-20261113.png` (build 27.0.1.2503222, 2026-11-13):

| | before (stock "Physical", `c2-table` screenshot) | after (`p7-table-test-3`) |
|---|---|---|
| headers in order | Picked, Inf, Player, Acceleration, Agility, Balance, Jumping Reach, Natural Fitness, Pace, Stamina, Strength | Picked, Inf, Player, **Pace**, Acceleration, Agility, Balance, Natural Fitness, Stamina, Strength |

Both edits are visible: **Jumping Reach is gone** (hide-column) and **Pace sits directly after Player** (move-column). This is the first table-view edit seen on screen: the ui-tableviews bundle default **is** consulted for this view and the write route (`tables.edit` -> patch file -> bundle patch -> gate -> install) works.

Caveat recorded: the view selector above the table read **"Copy of Physical"** (the stock screenshots read "Physical"). The columns shown are the edited ones, so the table was drawn from the changed bundle view; whether the copy was made by the game or by the user is not known and does not change the result.

Restored after c3: `STOCK: 67 of 67` (backup `20261113T204424Z`). The c3 session closed with no crash event.

Side observation, not caused by an inspector action (the inspector was read-only): the **c2 session** (`fm.exe` pid 30428, `p7-table-test-2` installed) ended with an `fm.exe` crash event at 21:38:22 local while it was being closed
(`0xc0000005`, faulting module unknown, fault offset `0x130800d0150`, bucket BEX64; Application log ids 1000/1001). The earlier tile session and the c3 session closed without one. Whether the c2 build is involved is not known; the c2 build changed only a view that its tile does not read.
Worth one repeat observation if an exit crash shows up again.

**Phase 7 closed.** Route status: tile write proven (c, `p7-tile-test`), table-view write proven (c3), native fonts proven (Phase 6). Open items carried: layout edit for string-list columns (`LoansTile_4x2` type tiles), icons/layouts diff and layout item states at the next FM patch,
drag-and-drop onto image slots, FontAsset experiment, real mouse drag test on the tile canvas, store-variant paths.
