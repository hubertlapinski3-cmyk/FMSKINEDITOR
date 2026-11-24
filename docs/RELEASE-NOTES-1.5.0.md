## FM Skin Studio 1.5.0

Feature release adding **Game Layouts**, slot editing, bundle tile management, the injected styles editor, read-only skin inspection, and stronger install guards.

### New in 1.5.0
- **Game Layouts**: interactive Edit and Runtime panes, Apply and Rollback with verified backups and recovery, legality checks, breakpoints, fullscreen and windowed viewport profiles, the screen index, Favourites, the **Apply to Standard & Small** option, and preview confidence labels (`measured`, `measured mismatch`, `computed`, `unverified`).
- **Slots**: add, remove, and reorder tiles inside layout slots (gated behind the `experimental: slot edits` setting in `BUILD`, off by default, until confirmed in-game).
- **Tile sizes and allowed tiles (bundle route)**: add tiles to tile sets cleanly with `files clean` verification and Restore stock (`tile sizes` is gated behind the `experimental: tile sizes` setting in `BUILD`, off by default, until confirmed in-game on its own run).
- **Injected styles editor**: edit custom `AlwaysAppliedStyleSheet` classes and variables with reach diagnostics.
- **Inspect skin (read only)**: inspect a third-party skin folder side-by-side against stock bundles.
- **Install guards**: requires verified stock backups, warns when a built package is older than recent project edits, and refuses to overwrite non-stock game files.

### Known limits
- Bundle edits must be rebuilt after a game update.
- Custom layout files survive game updates, but Football Manager's own **Reset Layout** deletes them.
- Unmeasured screens show `computed` or `unverified`, and the out-of-sample check scored only 1 of 42 compositions.
- Known mismatch: `3_Tiles_8x4-Expandable_2x4x2`, where `FitHeightToContent` is not modelled.
- Tile UXML editing (bindings, conditions, templates) is not included yet.
- Another skin tool that edits the same bundles makes them non-stock, and FM Skin Studio refuses to install until stock files are restored.

### Logs and diagnostics
If anything goes wrong, the engine writes diagnostic logs to `%LOCALAPPDATA%\FM27SkinEditor\logs\app.log` and launcher output to `logs/launcher.log`.
