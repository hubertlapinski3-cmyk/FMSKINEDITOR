# In-game checklist: one uninterrupted session

Prepared 2026-11-13 19:04 local (18:04 UTC), game build **27.0.1.2503222**, catalog `dfa1892e861e`. Everything that can be done offline is done: nothing has been installed, FM27 was not launched.
Order: **a** font, **b** tile layout, **c** table view. Write the observations into the results block at the bottom as you go, and paste it back.

## Where things are (all of it is also in Studio, button **?** in the left bar)

| what | where |
|---|---|
| Studio | `FM Skin Studio.bat` (starts a fresh engine; closes it with the window) |
| Prepared packages | Studio **?** > Packages, or `%LOCALAPPDATA%\FM27SkinEditor\build\<project>\<id>\package.json` (mirrored in `projects\<project>\packages\`) |
| Is the game stock? | `.\.venv\Scripts\python.exe -m skin_editor verify-stock` in the project folder. `STOCK: 67 of 67 ...` and exit code 0 = stock |
| Emergency restore | Studio Build panel **Restore stock**, or `.\.venv\Scripts\python.exe -m skin_editor restore vanilla` (game closed). Last resort: Steam > Football Manager 27 > Properties > Installed files > Verify integrity |
| Game logs | `C:\Program Files (x86)\Steam\steamapps\common\Football Manager 27\BepInEx\LogOutput.log` and `%USERPROFILE%\AppData\LocalLow\Sports Interactive\Football Manager 27\Player.log` |
| Screenshots | Steam overlay F12 (saved in Steam's screenshots) or Win+PrtSc (Pictures\Screenshots); name them `a-font.png`, `b1-standard.png`, `b2-large.png`, `c-table.png` |

**Before you start** (game closed): run `verify-stock`. Expected `STOCK: 67 of 67 UI bundles equal the stock reference hash; update status: same`. Anything else: stop and tell me.

---

## a. Native font (P6 font test, Impact on the primary family)

1. Start FM27 from Steam. At the main menu, top bar: click **Preferences** (between FMFC and More).
2. In the dialog, bottom row (`Reload Skin | <skin> | Reset Layouts | Reset To Default | Confirm`): click the **skin drop-down** (it shows `Mine`). Pick **P6 font test**.
3. Click **Reload Skin**. **Wait 10 seconds** (a reload takes 3 to 8 s).
4. **Expect:** the text of the dialog and the screens behind it in **Impact** (heavy, condensed, all-caps-looking sans) wherever the game uses the *primary* family, which is most body text, labels and buttons. Headings in the game's thematic face (FM Universe) are **not** expected to change. The skin changes nothing else.
5. **Screenshot** the whole Preferences dialog (`a-font.png`). Optionally also the main menu after **Confirm**.
6. **If nothing changed:** wait 10 s more and Reload Skin again once. Then write down: the skin name shown in the drop-down, and from PowerShell:
   `Select-String -Path "C:\Program Files (x86)\Steam\steamapps\common\Football Manager 27\BepInEx\LogOutput.log" -Pattern 'font|skin|uss|p6' | Select -Last 40`
   and the same pattern on `Player.log`. Paste the lines. Also note whether other skins (Mine) still reload fine.
7. **Switch back:** drop-down > **Mine**, **Reload Skin**, wait 10 s, **Confirm**. The magenta/Impact must be gone.
8. Close FM27 completely (Steam shows it stopped; no `fm.exe` in Task Manager).

## b. Tile layout: pitch and instructions swap sides (`p7-tile-test`)

Package `20261113T180410Z`: changes `ui-tactics_assets_all.bundle` only. Four cell moves: `TacticalPlannerTeamInstructionsTabComposition-Standard` pitch 0 to 6 and block 6 to 0; `...-Large` pitch 0 to 10 and block 6 to 0.

1. Game closed. Start `FM Skin Studio.bat`. Left explorer: click project **p7-tile-test**. Bottom panel tab **BUILD**: it must say *Target of p7-tile-test: bundles*. **Do not press Build bundles** (the package is already built and gated; pressing it would only make an identical one).
2. Click **Install build**, confirm the dialog. The OUTPUT tab shows `installed: ... ui-tactics_assets_all.bundle` and a backup path. Write the backup folder name down.
3. In PowerShell: `Get-FileHash "C:\Program Files (x86)\Steam\steamapps\common\Football Manager 27\fm_Data\StreamingAssets\aa\StandaloneWindows64\ui-tactics_assets_all.bundle"`: expected `9559D5968E9D9E686D55C752B4A11C291AA3E68AED733E7969A8835EC7C918B2`. `verify-stock` must now say `NOT STOCK` with exactly one line `differs from stock: ui-tactics_assets_all.bundle` (that is correct for this step). Anything else: stop and restore.
4. Start FM27, **Load Most Recent Career**. Top navigation **Tactics**, then the **Team Instructions** tab (the tab with the pitch and the instruction groups side by side).
5. **Expect (Standard breakpoint):** the **instructions block on the left, the pitch on the right** (vanilla is the other way round). **Expect (Large breakpoint):** the instructions block on the left (wide), the pitch to its right, and, if your build shows it, the phases panel still at the far right edge. Cells may touch or overlap a little in Large; note it.
6. **Both breakpoints.** The breakpoint follows the room the UI has. Do both and screenshot each:
   - *current state:* Preferences > Interface > **Information Display: Small** (your setting), look at the tab, screenshot `b1-standard.png` or `b1-large.png` (write down which: a third panel at the far right means Large).
   - *other state:* Preferences > **Information Display: Large**, **Confirm**, look at the tab again (screenshot), then set Information Display back to **Small** and Confirm. If your window is Windowed you can also drag it narrower or wider instead; either way note the Information Display value and the window size for each screenshot.
7. **If it fails** (nothing swapped, a blank or broken tab, wrong cells moved, an error banner): screenshot, write the symptom, and the log lines: `Select-String ... LogOutput.log -Pattern 'tactic|grid|composition|error|exception' | Select -Last 40`.
8. Close FM27. Studio **Restore stock** (confirm). Then `verify-stock`: expected `STOCK: 67 of 67 ...`. Write the result down.

## c. Table view (`p7-table-test`)

Package `20261113T180415Z`: changes `ui-tableviews_assets_all.bundle` only: `SquadKeyPlayersTableSmall` first column (`portrait-name-position`) 180 to **300 px**, columns **age** and **club** added. Built column order: Name/portrait, **Age**, **Club**, current-ability stars.

1. Game closed. Studio: click project **p7-table-test**, BUILD tab, **Install build**, confirm. OUTPUT shows `ui-tableviews_assets_all.bundle` and a backup path (write it down).
2. `Get-FileHash ...\ui-tableviews_assets_all.bundle`: expected `B6BB58931C690C9460E5DC1841FA13FA12A7086D5100B4215833E9859378E62C`. `verify-stock` must say `NOT STOCK` with exactly `differs from stock: ui-tableviews_assets_all.bundle`.
3. Start FM27, **Load Most Recent Career**, top navigation **Squad**. Look at the Squad overview and its tabs for the small **key players** table (a short list: player portrait + name + position, with a current-ability star rating).
4. **Expect:** that table's first column visibly wider, then **Age** and **Club** columns, then the stars. **Screenshot** (`c-table.png`).
5. **If the visible table is different** (I do not know for sure which tile uses `SquadKeyPlayersTableSmall`): screenshot it, write down the screen and tab, and **every column header in order**. I will map the columns to the table view and point the test at the right one. A custom view of your own (`Documents\...\views\*.fmf`) could take precedence over the bundle default; say if you have customised the Squad view.
6. **If it fails** (nothing changed, an empty table, an error): screenshot, symptom, log lines: `Select-String ... LogOutput.log -Pattern 'table|column|view|error|exception' | Select -Last 40`.
7. Close FM27. Studio **Restore stock**. `verify-stock`: expected `STOCK: 67 of 67 ...`. Write it down.

**Outcome of step c (2026-11-13):** installed, hash matched, game ran; nothing changed on the Squad overview, because `SquadKeyPlayersTableSmall` is the 4x4 configuration of the First Team tile and is not on that screen (see `docs/TABLE-VIEW-USAGE.md`). Retargeted in c2.

## c2. Table view retarget: the Loans tile on the Squad overview (`p7-table-test-2`)

Phase 7's exit criterion is "a table edit seen in game". The Loans tile (bottom right of **Squad > Overview**: "Loans, 5 Players", columns Player, Club code + badge, Rating) was visible in the last session and is the `SquadLoansTileDescription` tile, which uses the table view **`PlayerLoansTileTable`**.

Package `20261113T202702Z` (check the **?** view for the exact latest id): changes `ui-tableviews_assets_all.bundle` only. Edits to `PlayerLoansTileTable`: **hide the Rating column** (`loan-average-rating`) and widen the club code column (`club-icon-name-small`) 70 to **140 px**.

Ground rules: the inspector is read-only (screenshots, `fm_find`, `fm_get_styles`, one call at a time, never while you click); you navigate by hand.

1. Game closed. Install `p7-table-test-2` (Studio: BUILD tab, **Install build**; or `python -m skin_editor install p7-table-test-2`). Write the backup folder name down.
2. `Get-FileHash` of `ui-tableviews_assets_all.bundle` must equal the package's hash (`fbb0d9ec19dfeec8733e97e5d2c25fd44262be870b6e8005ab22b2b8d93975ed` for `20261113T202702Z`). `verify-stock` must say `NOT STOCK` with exactly `differs from stock: ui-tableviews_assets_all.bundle`.
3. Start FM27, load the career, **Squad > Overview**. Look at the **Loans** tile.
4. **Expect:** the **Rating** badge (the green/yellow number) is gone from every Loans row, and the club code column is wider. **Screenshot** (`c2-loans.png`, name it with build and date). If your Loans tile is empty, a squad with players out on loan is needed: say so.
5. **If nothing changed:** screenshot, and note the tile's visible columns. A user view or a different tile size may be in use; I will map it with `tables.view` (the `used_by` line names the tiles).
6. Close FM27. Restore stock (`python -m skin_editor restore vanilla`). `verify-stock`: expected `STOCK: 67 of 67 ...`. Write it down.

**Outcome of step c2 (2026-11-13):** installed, hash matched, game ran; the Loans tile was unchanged. The tile on screen is `LoansTile_4x2`, whose columns are a list in the layout, not a table view (see `docs/TABLE-VIEW-USAGE.md`). Retargeted in c3.

## c3. Table view retarget: the main squad table, view "Physical" (`p7-table-test-3`)

The table that fills the Squad > Overview screen (Picked, Inf, Player, Acceleration, Agility, Balance, Jumping Reach, Natural Fitness, Pace, Stamina, Strength) is the table view **`FirstTeamTableAttributesPhysical`** (same 12 columns, ids match the screen).

Package `20261113T203622Z` (check the **?** view for the latest id): changes `ui-tableviews_assets_all.bundle` only. Edits: **hide the Jumping Reach column** and **move Pace to directly after Player**.

Same ground rules: inspector read-only, one call at a time, you navigate by hand.

1. Game closed. Restore stock first if anything is installed (`restore vanilla`, then `verify-stock` = 67 of 67). Install `p7-table-test-3` (`python -m skin_editor install p7-table-test-3`). Write the backup folder name down.
2. `Get-FileHash` of `ui-tableviews_assets_all.bundle` must equal `1f1c0b22237a0587657156f8da227c4871eb573df3533a75df677e0d84271d64`. `verify-stock` must say `NOT STOCK` with exactly `differs from stock: ui-tableviews_assets_all.bundle`.
3. Start FM27, load the career, **Squad > Overview**, view selector on **Physical** (the game remembers it).
4. **Expect:** the column order is Picked, Inf, Player, **Pace**, Acceleration, Agility, Balance, Natural Fitness, Stamina, Strength. **Jumping Reach is gone.** **Screenshot** (`c3-table.png`, with build and date). Write the header row in order either way.
5. **If nothing changed:** note the view selector's name and whether it is a view you made yourself (a saved user view can win over the bundle default), and the header row.
6. Close FM27. `restore vanilla`. `verify-stock`: expected `STOCK: 67 of 67 ...`.

If at any point the game will not start or the UI is blank: close it, Restore stock, `verify-stock`, and tell me which step you were on.

---

## Results message (offline fields are filled; only the in-game observations are blank)

<!-- RESULTS-START -->
In-game results, build 27.0.1.2503222 (catalog dfa1892e861e). Session date: ______ (prepared 2026-11-13 19:04 local).

Offline preparation (done, verified):
- Stock before the session: restore-stock run through the existing restore code found nothing to copy (the game folder was already stock); all 67 of 67 UI bundles equal the stock reference hash, the p6 patched layout bundle (`ui-visualtreeassets_assets_globalvisualtreeassetpreload`, hash 6ed36b0dbfd9) is gone, update.status = same, tamper = clean, snapshot copies (16 files) equal the live files.
- Packages (gate passed, not installed):
  - p7-tile-test, id 20261113T180410Z: gate 0 failures, tile_moves_checked 4, untouched bundles checked 1; plan MoveCell x4, plan digest ac498b6aa1e7b3319f2ff2287e4b880999689f8c0d56dca7fbbc39b30ace0c54; ui-tactics_assets_all.bundle 9559d5968e9d (vanilla 2026d469e0ef).
  - p7-table-test, id 20261113T180415Z: gate 0 failures, table_patches_checked 1, untouched bundles checked 1; plan SetColumnWidth x1, ShowColumn x2, MoveColumn x1, plan digest ce02464dba6889ab4a5a7aab2c2ea7399cece716c723783b10c3e4eb07d4278d; ui-tableviews_assets_all.bundle b6bb58931c69 (vanilla 90e56b4e0064).
  - Both builds are deterministic (a rebuild gave identical bundle hashes and digests); the game folder was untouched by the builds (67 of 67 still stock afterwards).
- P6 font test skin: native gate 0 problems; the one url() (`fonts/impact.ttf` for --typography-family-primary) resolves inside the skin folder; the font file is byte-identical to C:\Windows\Fonts\impact.ttf (206,784 bytes, sha256 d8bbdb72e3f9...). Mine: installed folder identical to a fresh export of the project (8 files; 53 tokens, 190 rules, 3 images, 0 problems), no test rules left.

In-game observations (fill in):
- a. Font: Impact rendered on the primary family / nothing changed: ______
  Log excerpt if it failed: ______
  Switched back to Mine: yes / no.   Phase 6: closed / still open: ______
- b. Tile test: seen at both breakpoints / not seen / partial: ______
  Breakpoint A (Information Display ____, window ____): ______      Breakpoint B (Information Display ____, window ____): ______
  Installed file hash matched 9559d596...: yes / no.   Restored stock after: verified (STOCK 67 of 67) / issue: ______
- c. Table test: Age + Club seen in SquadKeyPlayersTableSmall / nothing changed: ______
  Actually visible table: screen/tab ______, column headers in order: ______
  Installed file hash matched b6bb5893...: yes / no.   Restored stock after: verified (STOCK 67 of 67) / issue: ______
- c2. Table retarget (`p7-table-test-2`, Loans tile): Rating column gone + club column wider / nothing changed / partial: ______
  Visible Loans columns after install, in order: ______
  Installed file hash matched fbb0d9ec...: yes / no.   Restored stock after: verified (STOCK 67 of 67) / issue: ______
  c2 observed (2026-11-13): nothing changed; Loans tile columns Player, Club (code + badge), Rating, all present; installed hash matched fbb0d9ec...; backup 20261113T203225Z (see evidence file). Cause: the tile is `LoansTile_4x2`, columns listed in the layout.
- c3. Table retarget (`p7-table-test-3`, Squad overview "Physical" view): **Jumping Reach gone + Pace after Player** (2026-11-13, build 27.0.1.2503222, screenshot `c3-table-27_0_1_2503222-20261113.png`).
  Header row in order: Picked, Inf, Player, Pace, Acceleration, Agility, Balance, Natural Fitness, Stamina, Strength. (View selector read "Copy of Physical".)
  Installed file hash matched 1f1c0b22...: yes (1F1C0B22237A0587657156F8DA227C4871EB573DF3533A75DF677E0D84271D64).   Restored stock after: ______ (filled when the game is closed)
- Phase 7: **closed** (tile route and table-view route both proven in game).   Phase 8 starts now.
<!-- RESULTS-END -->
