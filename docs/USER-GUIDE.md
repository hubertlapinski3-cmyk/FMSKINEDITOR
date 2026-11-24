# FM Skin Studio 1.5 User Guide

FM Skin Studio lets you customise colours, pictures, injected stylesheets, and screen layouts for Football Manager 27 without hand-editing raw game files.

---

## Quick Start

1. Close **Football Manager 27** before scanning or modifying files.
2. On first launch, let FM Skin Studio find your Football Manager 27 installation and take a one-time stock snapshot and style index.
3. Choose **Simple mode** (guided colours, pictures, offline look preview, native skin export) or switch to **Advanced mode** using the mode toggle in the bottom-right corner (`simple` / `advanced`).

For a one-page walkthrough of your first colour/theme skin, see [FIRST-SKIN.md](FIRST-SKIN.md).

---

## Game Layouts

Open **Game Layouts** from the left rail (`GL`) in Advanced mode to browse the game's screens, pick favourites, and open any composition in a canvas tab.

### Edit and Runtime Panes

Every Game Layout tab offers two views of a screen:

- **EDIT (file space)**: shows the design grid and optional slot strips (`m_right`, `m_bottom`) as stored in the composition layout file. Drag tiles to move them, resize tiles within their allowed limits, add/remove/reorder slot tiles, or swap a tile with another allowed tile.
- **RUNTIME (game result)**: computes how Football Manager's grid reflow lays out the tiles at the active viewport resolution and displays slot offsets and resolved tile rectangles before you apply anything.

### Screen Index, Favourites, and Breakpoints

- **Screen Index & Search**: browse screens grouped by area or filter by composition name.
- **Favourites**: star compositions you work on often so they stay pinned at the top of the Game Layouts list.
- **Viewport Profiles**: switch between the **Fullscreen** profile (for example `2560x1440 fullscreen, Small, Larger`) and **Windowed** profiles to preview how Football Manager chooses the `Small`, `Standard`, or `Large` breakpoint and lays out optional slots.
- **Also apply to Standard & Small**: when editing a `-Large` composition, tick **Apply to Standard & Small** if you want compatible moves/resizes mirrored to the `-Standard` and `-Small` compositions when you click **Apply**. Tiles that cannot fit safely in a smaller breakpoint are skipped and reported.

### Confidence Labels

Every composition shows a confidence badge telling you how closely Studio's layout engine matches recorded in-game measurements:

- **measured**: verified directly against recorded game measurements (`design` and `runtime` predictions agree with the in-game capture).
- **measured mismatch**: verified against a game capture, but a known difference remains (for example `3_Tiles_8x4-Expandable_2x4x2`, where `FitHeightToContent` is not yet modelled).
- **computed**: computed by the deterministic layout model and consistent across checks, though not yet measured on that exact screen in-game.
- **unverified**: the two layout models disagree or no parity evidence exists yet for that screen. Double-check the screen inside the game after clicking **Apply**.

### Legality Checks, Apply, Rollback, and Recovery

Before **Apply** writes a custom layout file to your game's `CustomGridCompositions` folder, Studio runs structural legality checks (for example overlapping tiles, grid bounds, invalid sizes, or locked-cell warnings):

- Blocking issues prevent writing until resolved.
- Each **Apply** records a transaction backup in your Studio workspace (`custom-layout-journal`).
- **Rollback** / **Restore to before Apply** restores any replaced custom layout file byte-for-byte or removes newly created files safely (if the game modified a file after Apply, Studio asks for confirmation before overwriting).
- If a previous Apply or Rollback was interrupted, Studio shows an unfinished-transaction recovery prompt on launch so you can cleanly undo or complete it.

### FM's "Reset Layout"

- Custom layout files in `CustomGridCompositions` **survive game updates**.
- However, clicking **Reset Layout** or **Reset All** inside Football Manager itself **deletes custom layout files** from `CustomGridCompositions`. Your backups stay safely inside FM Skin Studio so you can re-apply them whenever you wish.

---

## Bundle Edits, Restore Stock, and "files clean"

Some edits — such as full bundle stylesheets, tile set additions (**Allowed tiles**), and **Tile sizes** — patch copies of game bundles rather than exporting a native skin folder:

- **files clean**: the status bar indicator checks your game's UI bundles against the stock snapshot.
  - `files clean` means every tracked bundle matches the original stock game files.
  - `files modified` means one or more bundles differ from stock (either from Studio or from another skin tool).
  - `files game_updated` means Football Manager updated since the last snapshot.
- **Install guards**: Studio requires a verified stock backup before installing patched bundles, warns if your built package is older than your latest project edits, and **refuses to install over non-stock bundles** modified outside Studio (such as by another skin tool) until stock files are restored.
- **Restore stock**: restores the original unpatched bundles from verified backups so your game returns to `files clean`.

### After a Football Manager Game Update

- Close Football Manager 27.
- In Steam, verify integrity of game files (**Properties > Installed files > Verify integrity of game files**) if needed so game files are cleanly on the new version.
- Use **Game updates > Re-read the game** inside FM Skin Studio to refresh your snapshot and index.
- **Rebuild and re-install** any bundle edits for the new game version (old bundle packages from an earlier game build are refused so two game builds are never mixed).

---

## Slots, Tile Sets, Injected Styles, and Inspect Skin

- **Slots**: in a Game Layout tab, select a bottom-slot tile (`m_bottom`) to add, remove, or reorder tiles within that slot (gated behind `experimental: slot edits` in `BUILD`, off by default).
- **Allowed tiles & Tile sizes**: manage `GridElementSet` and `TileDescription` entries in the **Tile layout** (`T`) view and swap tiles right from **Game Layouts**.
- **Injected styles** (`IS`): edit custom CSS classes and CSS variables targeting `AlwaysAppliedStyleSheet` with syntax diagnostics and cascade reach info.
- **Inspect skin** (`K`): open a third-party skin folder in **read-only** mode to inspect changed compositions, styles, and views compared against stock game bundles without altering your game or that skin.

---

## Experimental Features

Features that are optional or not yet fully confirmed in-game ship **off by default** behind opt-in checkboxes in the **BUILD** panel (Advanced mode):

- `experimental: layout edits via bundles` — routes composition layout edits into `ui-tileslayouts_assets_all.bundle` instead of custom layout files (note: bundle layout edits move every composition in that bundle and are ignored on screens customised inside the game).
- `experimental: tile sizes` — allows staging new `TileDescription` size entries for bundle builds.
- `experimental: slot edits` — enables adding, removing, and reordering optional `m_bottom` slot tiles in Game Layouts (rolled back before an in-game check in v1.5).

To enable either setting: open your project in Advanced mode, open the **BUILD** tab in the bottom panel, and tick the checkbox next to the experimental option. Clear the warning carefully and test after building and installing.

---

## Third-Party Skins & Sharing Notice

When using **Inspect skin** or importing classes, variables, images, or themes from a third-party skin:

- Imported or inspected third-party skin content is for your **personal use only** unless the original author explicitly allows sharing or redistribution.
- When you share your own skin created in Studio (**Share and undo > Save as .zip**), only share assets and styles you created or have permission to distribute.
