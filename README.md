# FM Skin Studio

A desktop skin and layout editor for **Football Manager 27** on Windows. FM Skin Studio reads your installed game's styles and layouts, lets you edit colours, images, stylesheets, and screen layouts safely with backups, and exports either native skin folders or verified bundle packages.

- **New to skinning?** Read [`docs/FIRST-SKIN.md`](docs/FIRST-SKIN.md) for a one-page walkthrough of creating your first skin.
- **Full feature manual:** Read [`docs/USER-GUIDE.md`](docs/USER-GUIDE.md) for Game Layouts, confidence labels, viewport profiles, bundle install guards, Restore stock, experimental features, and personal-use rules.
- **Release notes & changes:** See [`CHANGELOG.md`](CHANGELOG.md) and [`docs/RELEASE-NOTES-1.5.0.md`](docs/RELEASE-NOTES-1.5.0.md).
- **Open-source licences:** See [`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md).

## Install and First Run

1. Download the installer (`FM Skin Studio_1.5.0_x64-setup.exe`) from the **Releases** page and run it. Your existing projects, settings, and favourites are preserved on upgrade.
2. Make sure **Football Manager 27** is closed, then launch FM Skin Studio.
3. On first launch, let the Studio detect your game folder, create its stock snapshot, and index the game's styles.
4. Studio checks for app updates automatically and lets you update from the **Check for updates** control when a newer release is available.

## Modes and Features

- **Simple mode** (default for fresh installs): guided **Projects**, **Colours** (including presets, three-colour dark themes, and **My colours**), **Pictures**, **Look at it** (an offline preview approximation alongside the stock look), **Put it in the game** (writes native skin folders without touching game files), and **Share and undo**.
- **Advanced mode** (toggle `simple` / `advanced` in the bottom-right status bar):
  - **Game Layouts** (`Edit` and `Runtime` panes, legality checks, Apply / Rollback with backups and recovery, viewport profiles, breakpoints, screen index, Favourites, **Apply to Standard & Small**, and confidence labels).
  - **Slots** (experimental, off by default under **experimental: slot edits** in `BUILD`: add, remove, reorder tiles), **Allowed tiles**, and **Tile sizes** (`tile sizes` is off by default under **experimental: tile sizes** in `BUILD`).
  - **Injected styles** editor (`AlwaysAppliedStyleSheet`) and code editor with live USS diagnostics.
  - **Inspect skin** (read-only comparison of a third-party skin folder against stock bundles — for personal use unless its author allows sharing).
  - **Install guards** (`files clean` verification, verified stock backups, stale-package prompts, and refusal over non-stock files modified outside Studio).

## Notes and Calibration Information

- **Look at it** and layout previews are approximations, not the game's own renderer. A repair release such as 1.1.1 attaches no calibration report: the report of the release it repairs (1.1.0) is unchanged and lives on that release's page.
- Custom layout files survive game updates, **but Football Manager's own "Reset Layout" deletes them** (Studio backups survive). Bundle edits must be rebuilt after a game update.

## Where Data and Logs Live

- **Workspace** (projects, stock snapshot, backups, and index): `%LOCALAPPDATA%\FM27SkinEditor` (can be overridden via `FM27SE_WORKSPACE`).
- **Logs**: `%LOCALAPPDATA%\FM27SkinEditor\logs\app.log` (`logs/app.log` in the workspace) records diagnostic details and tracebacks for any failed operation; the source-tree launcher writes `logs/launcher.log`.
- **Native skins folder**: `Documents\Sports Interactive\Football Manager 27\skins\<name>\`.
