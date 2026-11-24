# Changelog

All notable changes to **FM Skin Studio** are documented here.

## [1.5.0] - 2026-11-24

### New
- **Game Layouts**:
  - Edit pane and live Runtime pane (`design` and `slot` coordinate spaces) for screen compositions.
  - Safe **Apply**, **Rollback**, and recovery backups for custom layout files (`CustomGridCompositions`), plus **Restore to before Apply**.
  - Built-in legality checks (overlaps, bounds, locked cells) before writing.
  - Breakpoint selector (`Small`, `Standard`, `Large`) with automatic viewport selection.
  - Fullscreen (`2560x1440`) and windowed viewport profiles.
  - Screen index, **Favourites**, and the **Apply to Standard & Small** option.
  - Confidence labels (`measured`, `measured mismatch`, `computed`, `unverified`) showing how closely the preview matches recorded game measurements.
- **Slots**: add, remove, and reorder tiles in expandable slots on a screen (ships behind **experimental: slot edits** in `BUILD`, off by default — journal `20261124T070834Z-03e293d7` was rolled back before an in-game check).
- **Tile sizes and allowed tiles** (bundle route): add tiles from other screens to a tile set and build/install bundle updates (`tile sizes` ships behind an opt-in experimental setting in `BUILD`, off by default, until confirmed on its own run).
- **Injected styles editor** (`AlwaysAppliedStyleSheet`): edit custom CSS classes and CSS variables with cascade reach preview.
- **Inspect skin (read only)**: compare a third-party skin folder against stock game bundles without modifying files.
- **Install guards**: verified stock backups required before bundle installs, stale-package confirmation when a project was edited after build, and automatic refusal to install over modified (non-stock) game files.

### Known limits
- Bundle edits (colours, images, fonts, tile sets, tile sizes) must be rebuilt after a Football Manager game update.
- Custom layout files survive game updates, **but Football Manager's own "Reset Layout" deletes them**.
- Unmeasured screens show `computed` or `unverified` confidence labels, and the out-of-sample check scored only **1 of 42** compositions.
- One known measurement mismatch: `3_Tiles_8x4-Expandable_2x4x2`, where `FitHeightToContent` is not modelled yet.
- Tile UXML editing (bindings, conditions, templates) is not included yet.
- Another skin tool that modifies the same game bundles makes them non-stock, and FM Skin Studio will refuse to install until stock files are restored.
