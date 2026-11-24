# Owner test checklist — UI1

Plain steps to run the whole edit yourself. Game closed while editing; you launch it only for the two comparison steps, on the disposable Dortmund save, and quit with ForceQuitGame(0). Send back a screenshot and the bullet notes after each step.

1. Open Studio. It checks for an app update at launch; note the status in the bottom bar ("app up to date" or the version offered). Expert mode now shows a short activity bar — **Y** is "Game Layouts (Playground)"; the remaining tools are under the **⋯ / More tools** button. Click **Y**, then in **GAME LAYOUTS** type `squadcom` in the search box and click the row named **SquadComposition-Large** (Large, 5 cells). A tab named **SquadComposition-Large** opens in the main area with the canvas. Confirm the project's layout engine shows **rea** (one_rule remains selectable), and confirm the custom-folder view (C) lists the two existing files with their hashes. Note: folder view screenshot; are both files marked as yours?
2. In the Playground, pick **SquadComposition-Large** at 2560x1440 with breakpoint auto (should show **Large**). Note: the preview confidence label and the composition file name shown (-Large).
3. Move one tile. Note: the new preview rect and whether the label changed.
4. Resize one tile. Note: the preview rect and any legality warning shown.
5. Swap one tile. Note: the legality messages — which checks pass, which warn, and whether any blocks.
6. Read the Apply preflight: target file, whether it replaces an existing file, and the highlighted files. Confirm the replacement. Note: preflight screenshot.
7. Apply. Note: the backup path and the journal entry shown.
8. Launch the game yourself on the Dortmund save, open **Squad**, and compare with the preview. Note: screenshot, what matched, what did not (cell by cell if possible).
9. Quit the game with ForceQuitGame(0). Confirm the save is unchanged.
10. In Studio, press **Rollback**. Note: the sha256 verification result and, if the file did not exist before, the confirmation that it is gone.
11. Launch again and open **Squad**. Note: screenshot confirming the stock layout is back.

What to send back: the screenshots from steps 1, 6, 8 and 11, plus for every step one line saying what matched and what did not. If any Apply or Rollback is refused, copy the refusal text verbatim.

## UI3 findings (2026-11-22, game closed; no launch)

**What the game re-saved.** SquadComposition-Large was written by Studio at 22:47 (tx 20261122T224723Z-1289fe01, before 6b8510 -> after aa7501). The current file was exactly that Studio package; a game re-save writes the same bytes but changes the hash only if the layout changes. Rollback of the earlier transaction was refused because a later transaction had superseded it, not because of object ids.

**Object ids are not a gate.** A generated file has `instanceID` 0 everywhere and still loads: the game resolves tiles by name through ResolveDescriptionKeys (0x198d4c0). Evidence: CL3 B1, JX X1-X3 and E2E1 all loaded zero-id files, and the game itself writes zeros when it re-saves. Studio keeps a note when ids are 0; it never refuses the file. (The earlier dfa634f guard is reverted.)

**The actual cause: a partial overlap.** Diff of 6b8510 -> aa7501 is only three numbers:
- Atmosphere x 16 -> 15
- Training x 16 -> 15, y 4 -> 6

That produces three partial overlaps:
- Atmosphere (15,8,4,2) vs Training (15,6,4,4)
- Atmosphere (15,8,4,2) vs FirstTeamOverview (0,1,16,9)
- Training (15,6,4,4) vs FirstTeamOverview (0,1,16,9)

The rea preview makes it visible: stock places Atmosphere at (27,8,4,2); the edited file places it at (15,17,4,2), outside the 31x17 grid. The game then drops FirstTeamOverview and the reflow shifts every row down.

**Studio fix.**
- `validate_before_write` (`skin_editor/custom_layouts.py`) now refuses any PARTIAL overlap between grid cells (exact duplicates stay the LT2 C5 warning). Test: `test_the_one_column_move_that_broke_the_game_is_refused`.
- The Game Layouts canvas (`studio/src/LayoutCanvas.tsx`) detects overlaps as you drag, disables Apply and names the colliding tiles. Test: `blocks Apply when two tiles partially overlap`.
- Tile size/grid clamping from 82c149c stays; the canvas and the backend both clamp to `m_minSize`/`m_maxSize` and the grid.

**Files the game re-saved.**
- `layouttx.restore_to_before` restores the pre-Apply state even when a file changed since Apply: the byte-exact backup, or deletion when the transaction created the file. Journaled on the transaction as `restore_to_before`. RPC: `customlayout.restore_before`.
- When Rollback finds a changed file, the layout tab shows what changed and offers **Restore to before Apply**.
- Tests: `test_a_created_file_is_deleted_even_after_the_game_resaved_it`, `test_a_replaced_file_comes_back_byte_for_byte`.

**Squad restored.** Used `restore_to_before` on tx 20261122T201506Z-00124578: SquadComposition-Large deleted (no file), the two owner files unchanged (a2c95aa7..., 8372412d...).

## UI4: the two panes (2026-11-23)

The Game Layouts tab now has two panes, switched by the buttons at the top:

- **EDIT (file space)** - the left pane. The main grid is drawn at its design size
  (SquadComposition-Large: 20x10). Below it each optional-slice zone is its own labelled
  area (BOTTOM ZONE, RIGHT ZONE), with the stored slot numbers. Drag here; a slot tile can
  only move inside its zone. This is exactly what the file stores.
- **RUNTIME (game result)** - the right pane. It shows the rea result at 2560x1440 and
  updates after every drag. A tile the game places somewhere else (growth, compaction, a
  clamp) is outlined and carries a one-line reason, e.g. "compacted up to row 4".

Drag in the EDIT pane, then look at RUNTIME before Apply. Apply is disabled while two
cells overlap in their own space, or while the runtime result has an overlap or an
off-grid tile. The inspector shows the stored value, the expected runtime column/row and
what the game actually placed.

The old single canvas edited the grown runtime grid and wrote those numbers back as if
they were design numbers; that is what made a one-column drag land in the wrong place in
UI3. See `docs/LAYOUT-COORDINATES.md` and `docs/OWNER-TEST-UI1.md` above (UI3 findings).

## UI5: legal test edit to try in the game (2026-11-23)

Pinned viewport: **2560×1440 windowed · Information Display Small · Text Scaling Larger**
(breakpoint **3 = Large**, `SquadScreen` content rect `[15.6, 85.9, 2468.8, 1319.3]`,
design grid `20×10` → runtime grid `30×16`).

**Test edit on `SquadComposition-Large`:** swap `Training` and `Atmosphere` vertically in
the right column of the **EDIT (file space)** pane:

- `Atmosphere`: move from `(16, 8, 4, 2)` to **`x=16, y=4, w=4, h=2`**
- `Training`: move from `(16, 4, 4, 4)` to **`x=16, y=6, w=4, h=4`**

Both the design-space validation (`validate_before_write`) and the runtime check
(`layoutspace.runtime_problems` on `30×16`) pass with **0 problems**, and **Apply** is
enabled.

**Expected runtime grid positions and UI-unit rects (`[left, top, width, height]`):**

| Tile | Space | Stored `(x, y, w, h)` | Runtime grid `(col, row, w, h)` | Expected runtime rect (UI units) |
|---|---|---|---|---|
| `HumanActionsControlPanelBlock` | `main` | `(0, 0, 16, 1)` | `(0, 0, 26, 1)` | `[27.6, 97.9, 2116.0, 66.0]` |
| `FirstTeamOverview` | `main` | `(0, 1, 16, 9)` | `(0, 1, 26, 15)` | `[27.6, 179.9, 2116.0, 1214.0]` |
| `Tactics` | `main` | `(16, 0, 4, 4)` | `(26, 0, 4, 4)` | `[2159.6, 97.9, 312.0, 312.0]` |
| `Atmosphere` | `main` | **`(16, 4, 4, 2)`** | **`(26, 4, 4, 2)`** | **`[2159.6, 425.9, 312.0, 148.0]`** |
| `Training` | `main` | **`(16, 6, 4, 4)`** | **`(26, 6, 4, 4)`** | **`[2159.6, 589.9, 312.0, 312.0]`** |
| `SquadHierachy` | `m_bottom` | `(16, 0, 4, 2)` | `(26, 10, 4, 2)` | `[2159.6, 917.9, 312.0, 148.0]` |
| `MedicalCentre` | `m_bottom` | `(16, 2, 4, 2)` | `(26, 12, 4, 2)` | `[2159.6, 1081.9, 312.0, 148.0]` |
| `Loans` | `m_bottom` | `(16, 4, 4, 2)` | `(26, 14, 4, 2)` | `[2159.6, 1245.9, 312.0, 148.0]` |

## Confirmed in game (2026-11-23)

**Status:** **Empirical** — `SquadComposition-Large` and this vertical swap edit are the **first Empirical Studio-to-game result**.

- **Date:** 2026-11-23
- **Composition:** `SquadComposition-Large` (pinned viewport: 2560×1440 windowed · Small · Larger, breakpoint 3 = Large, runtime grid `30×16`)
- **Edit (file space / design `20×10`):**
  - `Atmosphere`: `(16, 8, 4, 2)` → `(16, 4, 4, 2)`
  - `Training`: `(16, 4, 4, 4)` → `(16, 6, 4, 4)`
- **Transaction id:** `20261123T081454Z-ccdf17f9` (written sha256 `6b8510255c77f79e85fcecfeb3739e2e777b5d76ac6c206b351dc2a2b4133180`)
- **Expected runtime rects (from UI5, UI units `[left, top, width, height]`):**
  - `HumanActionsControlPanelBlock`: grid `(0, 0, 26, 1)` → `[27.6, 97.9, 2116.0, 66.0]`
  - `FirstTeamOverview`: grid `(0, 1, 26, 15)` → `[27.6, 179.9, 2116.0, 1214.0]`
  - `Tactics`: grid `(26, 0, 4, 4)` → `[2159.6, 97.9, 312.0, 312.0]`
  - `Atmosphere`: grid `(26, 4, 4, 2)` → `[2159.6, 425.9, 312.0, 148.0]`
  - `Training`: grid `(26, 6, 4, 4)` → `[2159.6, 589.9, 312.0, 312.0]`
  - `SquadHierachy`: grid `(26, 10, 4, 2)` → `[2159.6, 917.9, 312.0, 148.0]`
  - `MedicalCentre`: grid `(26, 12, 4, 2)` → `[2159.6, 1081.9, 312.0, 148.0]`
  - `Loans`: grid `(26, 14, 4, 2)` → `[2159.6, 1245.9, 312.0, 148.0]`
- **Result:** **matched** — the game displayed `Tactics`, then `Atmosphere` at row 4, then `Training` at row 6, with `FirstTeamOverview` intact, matching the Studio runtime pane.

## FS1: Viewport profile switch & Favourites checklist (2026-11-23)

### Viewport profile switch
1. Open **Game Layouts (Playground)**. Verify the viewport profile defaults to **`2560x1440 fullscreen, Small, Larger`** (`SquadScreen` content rect `[15.6, 85.9, 2468.8, 1319.3]`, `30×16`; extra rows fullscreen vs windowed = `0` for Squad `16 vs 16`, Portal `16 vs 16`, PlayerReport `13 vs 13`).
2. Switch the viewport selector (`gl-profile` in the sidebar or `layout-viewport-profile` in the canvas header) to **`2560x1440 windowed, Small, Larger`** and back.
3. Confirm confidence labels update per profile (`measured`, `measured mismatch`, `computed`, `unverified`) — for example, a windowed-only screen such as `InjuryHistoryCardGridComposition` reads `measured` in windowed and `unverified` in fullscreen.

### Per-favourite round-trip checklist (game closed while editing)
For each screen you star into **FAVOURITES** at the top of Game Layouts (persisted in the workspace `favourites.json`):
- [ ] **Edit:** Star the composition, open it from **FAVOURITES**, note its active profile confidence label (`measured` / `measured mismatch` / `computed` / `unverified`), drag or resize one legal tile in **EDIT (file space)**, and check **RUNTIME (game result)** shows 0 overlap/off-grid problems.
- [ ] **Apply:** Click **Apply** (confirm any existing-file replacement prompt) and record the `tx_id`.
- [ ] **Check:** Launch FM27 on your test save, open that screen, and verify in-game tile positions match the RUNTIME pane (screenshot).
- [ ] **Rollback:** Quit FM27 (`ForceQuitGame(0)`), click **Rollback** in Studio on `tx_id`, verify hash/removal, and confirm the stock layout returns on next launch.

## BND1 Empirical Results (2026-11-23)

- **RR-T5 (`Empirical`):** Added `BestXITileDescription` (`BestXI` `4x2`) to `SquadTileSet` via `build.bundles` + Studio `install`, swapped `Atmosphere` -> `BestXI` in `SquadComposition-Large`; `BEST XI` rendered and resolved in-game (`bnd1-20261123T150437Z-rrt5.png`), then rolled back cleanly to `590 + 3` stock.
- **Slot reorder (`Empirical`):** Reordered `m_bottom` slots (`Loans`, `MedicalCentre`, `SquadHierachy`) in `SquadComposition-Large`; in-game hosts matched rows `10, 12, 14` (`bnd1-20261123T150806Z-slot-reorder.png`). Canvas `Move slot up` / `Move slot down` enabled for `m_bottom` reorder.

## BND2 Empirical Results (2026-11-23)

- **Slot add (`Empirical`):** Added `Happiness` (`4×2`, `y=6`) to `m_bottom` in `SquadComposition-Large` before launch; game loaded `isCustom: true` with 4 `optionalSlices.bottom` slots (`SquadHierachy`, `MedicalCentre`, `Loans`, `Happiness`) and placed the 3 slots that fit in the 16-row right column (`bnd2-20261123T171623Z-slot-add`).
- **Slot remove & navigate-away re-read (`Empirical`):** Wrote 2-slot `m_bottom` (`Loans` removed), navigated `Squad -> Portal -> Squad`; `SquadComposition-Large` rebound (`instanceId -4964 -> -5430`), `optionalSlices.bottom` dropped to `['SquadHierachy', 'MedicalCentre']`, and `Loans` disappeared from the visual tree (`bnd2-20261123T171623Z-slot-remove`). Canvas `Add bottom slot` and `Remove slot` enabled for `m_bottom`.
- **OOS check (`Empirical`):** `OnThePitchComparisonCardGridComposition-Large` (`PlayerReport/Comparison` on `Waldemar Anton`) scored `0.7 px` worst delta (`PASS`) against the frozen `06b5bc1` engine; `StaffResponsibilitiesOverviewCardGridComposition-Large` was inactive/collapsed (`crect=[0, 117.2, 0, 0]`).

## ALL1 Information Display Profiles (`2560x1440 fullscreen`, Text Scaling `Larger`)

Studio now includes all three fullscreen Information Display profiles in the viewport selector (`gl-profile` / `layout-viewport-profile`), each with its own measured content rects, grid sizes, and build-tagged confidence labels (`docs/rea/ALL1-COVERAGE.md`):
- **`2560x1440 fullscreen, Small, Larger`** (`M1`): `scale = 1.024`, default content rect `[15.6, 85.9, 2468.8, 1319.3]`, grid `30×16` (`docs/rea/data/fullscreen-2k-measurements.json`, `140/141` pass).
- **`2560x1440 fullscreen, Medium, Larger`** (`M2`): `scale = 1.22488`, default content rect `[13.1, 71.8, 2063.9, 1102.9]`, grid `25×13` (`docs/rea/data/all1-m2.json`, `139/141` pass).
- **`2560x1440 fullscreen, Large, Larger`** (`M3`): `scale = 1.52381`, default content rect `[10.5, 57.7, 1659.0, 886.6]`, grid `20×11` (`docs/rea/data/all1-m3.json`, `138/139` pass).
