# FM Skin Studio

A skin maker for Football Manager 27, for Windows. It reads the game's own styles, lets you change colours, pictures and themes, draws a preview of the game's layouts offline, and writes your skin into the game's skins folder. **No game file is changed** on the way that Simple mode uses: Football Manager loads the skin itself (Preferences, next to "Reload Skin").

**New here? Read [`docs/FIRST-SKIN.md`](docs/FIRST-SKIN.md):** one page from installing to seeing your skin in the game.

## Install and update
- Download the installer from the repository's **Releases** page and run it. The Studio checks for updates itself (**Check for updates**) and installs a new version when you ask.
- The first start reads the game once (**Find my game and read it**). The game must be closed while it does.

## Simple mode (the default for a fresh install)
Words on the left, one job per screen:
- **Projects**: your skins, and the start screen with four ways to begin: a ready-made theme, a theme from three colours, a skin you downloaded, or the game's look.
- **Colours**: every colour the game's styles use, in groups, with your own saved colours (**My colours**, up to 10).
- **Pictures**: replace a wallpaper or an icon with your own picture in three steps.
- **Look at it**: a game layout drawn offline, the game as it ships beside your skin; click a part to recolour it.
- **Put it in the game**: writes the skin folder; the first time, the game needs the skin picked once in Preferences.
- **Share and undo**: save the skin as one .zip, open a skin file someone sent you (you see what is inside first, and get your own copy), or start over.

## What is and is not checked in the game
Said here plainly because the Studio says it on screen too:
- **Not yet looked at in the game:** the ready-made themes (Crimson in this form, Forest, Ocean, Slate and amber) and every theme made from three colours. Each is labelled "not yet checked in the game" until the in-game sessions (`docs/SESSIONS-simple-mode-checklist.md`) record it.
- **Look at it is an approximation**, not the game's renderer: data, hover states and code-drawn visuals are approximated, and the notice above each picture says so. The guide to what it can and cannot show is `docs/RENDER-GUIDE.md`; the published calibration report is in `docs/evidence/phase9-m7-calibration-20261114/`. A repair release such as 1.1.1 attaches no calibration report: the report of the release it repairs (1.1.0) is unchanged and lives on that release's page.
- **Themes are dark** in this version: the theme generator's role map comes from a dark preset, and light themes failed its readability check.

## Advanced mode
Click **S** (or the mode name at the bottom right) to switch. Advanced mode keeps everything Simple mode hides: project folders of USS files in a code editor with live problems and quick fixes, every game stylesheet read-only, the render browser with the explanation of every element, the full Images view, layouts, tile layout (with an optional screenshot of the real game drawn behind the grid, to line the tiles up by eye; the pictures stay in `game-screens` in your workspace and are never put in a project or a skin) and table views, game-update profiles, and the **bundle route** (build patched copies of the game's bundles and install them with a backup). The bundle route changes game files; Steam's "Verify integrity of game files" undoes it. Use one route at a time.

## Where things are
- **Workspace** (projects, the game's snapshot and index, caches): `%LOCALAPPDATA%\FM27SkinEditor` (override with `FM27SE_WORKSPACE`).
- **Logs:** the engine's own log, `logs/app.log` in the workspace (installed app: `%LOCALAPPDATA%\FM27SkinEditor\logs\app.log`), holds the traceback of every failed call; the frozen engine's `--selftest` checks that it does. The source-tree launcher writes `logs/launcher.log`.
- **Your skins** go to `Documents\Sports Interactive\Football Manager 27\skins\<name>\`.

## From source (development)
- Engine: Python 3.14 (what CI and the release build use), `pip install -r requirements.txt`, then `python -m skin_editor serve --no-browser` (it prints its address and session token). `python -m skin_editor --help` lists the command-line tools; `python -m skin_editor verify-stock` says in one line whether the game's UI bundles are stock.
- Studio: in `studio/`, `npm install`, then `npm run dev` (browser, pass the engine address and token) or `npm run tauri dev` (desktop window; needs Rust).
- Tests: `python -m unittest discover -s tests` (some tests read the real game when it is installed and are skipped otherwise) and `npm test` in `studio/`. CI runs both on every push.
- The engine API (every operation as a named, schema-checked method): `docs/API.md`, or `python -m skin_editor methods`.

## Releases
Built by the release workflow (`.github/workflows/release.yml`): the engine is frozen with the PyInstaller version pinned in `requirements-build.txt` (printed into the build log), self-tested (the picture code imports, a bundle writes and reads back on a committed synthetic fixture, a failed call is logged), then the installer is built and signed. Every release passes the release checklist in `docs/PHASE9-PLAN.md` and the owner's approval before its tag.
