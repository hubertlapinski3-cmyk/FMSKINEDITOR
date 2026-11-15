# FM27 Skin Editor

Local skin editor for Football Manager 27. Python backend on 127.0.0.1, single-page frontend in the default browser. Built from LEARNINGS.md; section numbers below refer to it.

## Run

```zsh
brew install python@3.12
python3.12 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python -m skin_editor            # prints http://127.0.0.1:8765/?t=<session token> and opens it
python -m unittest tests.test_core tests.test_layout
```

CLI without the browser: `python -m skin_editor detect | status | snapshot | index | new NAME [--preset crimson] | build NAME | reach NAME | install NAME | restore BACKUP|vanilla | launcher | check-layout DUMP | import-layout DUMP`.

## Launch by double-click

One-time, from the running app: Setup tab, "Create launcher", confirm the target shown. Or from a terminal: `python -m skin_editor launcher` (`--dir DIR` to choose the folder, `--yes` to skip the prompt). This writes `FM27 Skin Editor.app` into /Applications when that folder is writable, otherwise next to the app folder. Drag it to the Dock if you like. From then on, click the icon.

What a click does:

1. Checks that the app folder and the workspace still exist at the paths baked into the launcher.
2. If the Python environment is missing or incomplete, creates it with the first of python3.12, 3.13, 3.11, 3.14, 3.10 it finds (never a bare python3) and installs `requirements.txt` (first run only; a notification is shown).
3. Asks the app for its port and state folder, then probes `http://127.0.0.1:<port>/ping`.
   - Nothing listening: removes leftover state files, starts the server in the background, waits until it answers.
   - This workspace's current server answers (instance id equals `state/instance-id`): starts nothing.
   - The app answers with another instance id: dialog. That server belongs to another session and has to be quit first.
   - Anything else answers: dialog. The port is taken by another program.
4. Opens the browser at the address in `state/last-url`.

Repeated clicks never start a second server. Two clicks at the same moment share a lock; the second waits for the first.

Files: the server writes `state/last-url` (tokened address) and `state/instance-id` (random per start) after it has bound the port and removes them on exit. The session token is still rotated on every start. Launcher output goes to `logs/launcher.log`, server output to `logs/server.log`. The engine's own log, `logs/app.log`, holds the traceback of every failed call (the installed app on Windows: `%LOCALAPPDATA%\FM27SkinEditor\logs\app.log`); the frozen engine's `--selftest` checks that it does. Every failure is a macOS dialog with a short message and the log path.

Stopping: without a terminal, "Quit server" on the Setup tab is the only way to stop the server (`POST /api/quit`, token required). Closing the browser tab does not stop it. A server left running in the background is reused by the next launcher click, with the same session address. `GET /ping` is the only route without a token; it returns the app identifier and the instance id, nothing else.

Create the launcher again after moving the app folder or the workspace; the old one reports the move in a dialog. For a moved app folder the dialog prints the command to run once in Terminal: `cd "NEW_FOLDER" && python3.12 -m skin_editor launcher --yes`. Game patches do not affect the launcher. The CLI is unchanged.

The launcher script starts with `#!/bin/bash` and targets the bash 3.2 that macOS ships. The test suite rejects bash 4 constructs in it and checks that it also parses as plain POSIX sh.

Limits: the launcher was exercised on Linux only, by running the generated script under bash 5 with stand-ins for `osascript` and `open` (cold start, two clicks at once during a cold start, repeat click, killed server, other session, foreign port, moved folder). It has not run on macOS, under the real bash 3.2, or from Finder. The icon is the generic application icon.

## Launch on Windows

Double-click `FM27 Skin Editor.bat`. First run creates a private Python environment in `.venv` next to the file and installs `requirements.txt` (needs Python 3.10 or newer and internet once). It then starts the server and opens the browser. Keep the window open while you use the editor; closing it, Ctrl+C or "Quit server" on the Setup tab stops it. If a server for the same workspace is already running, the file opens that session instead of starting a second one. Extra arguments run a CLI command and stop, for example `"FM27 Skin Editor.bat" check-layout DUMP.json`. Set `FM27SE_PYTHON` to use an existing `python.exe` instead of `.venv`. Every failure (no Python, the environment or package install failed, the server could not start, for example because the port is taken) prints what went wrong and the command to run by hand, then waits for a key: the window never closes by itself on an error. Without a terminal, "Quit server" on the Setup tab (or closing the window) is the way to stop it.
## Placement edits

On the Layout tab, with a project selected and the layout dump **fresh**, "placement edit mode" adds an Edit button per cell on the composition view: new x, y, w, h (grid cell units) and/or a chosen tile config. With a stale or unknown dump the controls are hidden (stored edits stay listed and can be reverted). The edit routes also refuse while the dump is not fresh.

Stored in the workspace and written by a bundle build (positions only). Edits live in the workspace, one versioned list per project (`workspace/placements/<project>.placements.json`, schema 1). They are never written into the dump. A bundle build (Studio: Build bundles) writes the x/y position of every edit that is not stale into a copy of the composition bundle and the gate proves nothing else changed; sizes and config changes are never written; the game folder changes only when that build is installed. Each edit keeps the dump values it replaces (`old`, for revert) and the dump fingerprint and build it was validated against. Revert removes the edit. The build report always has a `layout_placement` section ("stored; positions are written by a bundle build") listing every edit with target, old and new geometry or config, and validation state. The older `tile_placement` key in a project file is left untouched; entries without a schema marker are reported as legacy in the project warnings.

Validation against the dump. Hard blocks refuse the edit: target missing, a `locked` cell (a move or resize is refused; choosing a config is not a move), values that are not integers, outside the composition grid (when the dump has no preset size the bounds cannot be checked and that is a warning), outside the cell's min/max limits, a config the cell does not have, no change. A collision with another cell inside bounds is a warning and needs an explicit confirm (overlap may be intentional layering); other stored edits count at their new position. Unknown flags are shown and do not block.

When the dump changes (a new import), every edit is revalidated: one whose target vanished or moved, or that now blocks or collides, is marked **stale** with the reasons, reported in the list and the build report, and never silently applied or re-enabled; re-adding it validates it afresh.
## Colours: RGBA with alpha as a 0-1 float

The game stores every colour as four floats in the 0-1 range. The app keeps all four.

Canonical form, used in project files, the index and the reports:

```json
{"rgb": "#RRGGBB", "a": 0.652}
```

`a` is stored exactly as decoded or entered and is never rounded. The three-decimal alpha and the 8-digit hex (`#RRGGBBAA`, alpha as a byte) are display and input conveniences: 0.652 shows as `A6`, which is 0.651 as a byte, so the hex form alone cannot carry it. Values that are not a single colour (`var(--x)`, `4px`, keywords, multi-value shorthands) stay strings.

`skin_editor/colour.py` holds every conversion (float, byte, hex digits, parsing, source-over compositing). The browser has one mirror of it (`Col` in `frontend/index.html`).

Editing. Each colour editor has a picker and a 6-digit hex for RGB, the alpha as a float, and the 8-digit hex; all four stay in step. An alpha you do not touch keeps its full stored precision. Token pages show the vanilla value and the override side by side with their alphas.

Literal swaps have two modes, chosen explicitly in the Literals tab and recorded per swap in `build-report.json` under `literal_swaps` (`from`, `to`, `mode`, `hits`):

- `rgba`: only uses with exactly this RGB and this alpha change, and the replacement brings its own alpha. Done by `patcher.swap_rgba` on the vanilla tree before token_patch runs.
- `rgb-keep-alpha`: every use of the RGB changes whatever its alpha, and each use keeps its alpha. This is token_patch's own `literal_map`, unchanged; the crimson preset uses it.

If an `rgba` swap produces an RGB that an `rgb-keep-alpha` swap is looking for, it is recoloured again; the project warns about that.

Project schema 2. Schema 1 files are migrated when loaded: `#RRGGBB` becomes alpha 1.0, `#RRGGBBAA` becomes alpha byte/255, `rgba()` keeps its float, literal swaps become `rgb-keep-alpha`. No field is dropped, and load then save is stable. Colour strings typed into the JSON editor are converted on save.

Percent-style alpha in legacy project data. The canonical form is strict: an alpha outside 0..1 is rejected everywhere. Two legacy project-data boundaries, and only those, accept an alpha above 1 and up to 100, read it as a percentage, divide by 100, and log the original value with the boundary name to `logs/app.log` (also listed on the Setup tab): schema-1 project migration and crimson preset conversion. This rule is never applied to values read from bundles.

Quarantined bundle colours. The real style bundles hold 16 colour entries (7 unique colours) with a component above 1. They are classified, not rescaled: 14 "byte-alpha candidates" (valid RGB, integer alpha of 100, 124, 243 or 255, shown with alpha = stored / 255 for display only) and 2 "hdr" (a red component of 4.62; raw floats kept, no hex rendering, excluded from literal swaps permanently). None is offered as a literal and a build never rewrites any of them; a swap that would copy one is refused. The byte-alpha quarantine ends with one in-game observation (selected cell of the Squad streamed table: solid #AF78FF means the game clamps to opaque, translucent means the byte scale is live). Evidence, decision and exit condition: `diagnostics/README.md`.

Search by hex code. The Tokens search box matches the token name, its value text, or the hex code the token resolves to through its alias chain (`AF78FF`, `#af78ff`, or the 8-digit form with the alpha byte). The Literals tab has its own hex search box.

Re-index required. The style index cache is now schema 3: literal colours are keyed on full RGBA and carry the decoded alpha float, and out-of-range bundle colours are recorded as failures. Caches from earlier versions are never migrated; they are ignored and rebuilt from the bundles, so after updating the Tokens and Literals tabs ask for the index again. Run Setup, "Build index" once. The Literals list is longer than before because the same RGB at two alphas is now two entries; that is intended.

Build. Colours with alpha below 1 are passed to token_patch as `rgba(r, g, b, a)` with the full float, which it writes as a 0-1 quadruplet. The test suite builds colours with alpha 0.5 and 0.652, rounds the colour table to 32-bit floats as the serializer does, decodes with the app's decoder and compares.

Contrast. Each pair is composited before the ratio is taken: surface over the backdrop (`options.contrast_backdrop`), then text over the composited surface. Each row states where the surface came from (`rule background-color`, `rule on`, `contrast_pairs`, or `default backdrop` for a rule that sets only `color`), the two RGBA values, the painted results, and `composited: true` when either alpha was below 1.

## Layout data and "where it paints"

The app is layout-aware through a **layout dump**: one versioned JSON file (`fmlayout-index/2`, contract in `docs/fmlayout-index-2.md`; `/1` is refused) produced by an external, read-only indexer. The app never depends on that indexer at runtime, only on the file. Stdlib JSON only; the dump is never written.

Import: Setup tab, "Layout data", choose the file and Import; or `python -m skin_editor import-layout DUMP.json`. `python -m skin_editor check-layout DUMP.json` validates any file against the contract and prints counts per section (exit 1 when invalid); it needs no game and no workspace and doubles as the exporter's contract test. Validation is strict and all-or-nothing: a file that breaks the contract (unknown schema, wrong types, duplicate ids, dangling references, bad cells) is refused with the violations listed and nothing is loaded. The stored copy is `workspace/layout/current.json`; the one before it is kept as `previous.json`.

Staleness is decided from file hashes, not the build label. The vanilla snapshot records reference hashes (the contents of `catalog.hash` and the sha256 of every `ui-*.bundle`; hashes only, no copies); an older snapshot gets them with "Record reference hashes" on the Setup tab (or `python -m skin_editor record-reference`) with the game closed and stock files. The dump's `meta.source` (platform folder, catalog hash, bundle hashes) is compared with them: **fresh** (all equal), **stale** (catalog differs: game updated), **contaminated** (catalog equal but a bundle hash differs: the dump was read from modified files; the import is refused) or **unknown** (no reference hashes yet). The fingerprint is opaque and only compared with the previous dump ("changed vs previous"); its first 12 characters are shown. Placement edits accept only a position change (x, y): size changes are blocked, and so is a config choice whose size differs from the cell's current size, until a config trial has run in game.

Where it paints. The Tokens and Literals detail panels end with a "Where it paints" section, and the Tokens page has a search box for a class or selector substring. All three use one pipeline: style rules (the app's own index, including alias chains) -> the subject class or id of each selector -> elements in the dump -> layouts -> screens (panel ids, through includes and tiles), with the area of each layout from the dump's resolved area map. Alias hops are listed explicitly (hop depth, the token it came through, screens reached) and `cross_screen_via_alias` names the screens reached only through an alias (for example a token that also paints the training calendar). Each hit carries its evidence: rule, selector, property, layout, element.

Three evidence states, and nothing is dropped:
- **verified**: the class (or id) matches a static element record.
- **runtime-observed**: it matches only a class the exporter saw being added at runtime (`runtime_classes`). Labelled, never counted as verified.
- **unverified**: it matches neither (runtime-added or code-driven, or unused), or the selector's subject has no class or id. Listed with the reason; it adds no screens.

Only the subject (last) compound of a selector is matched; pseudo-classes are shown as states, not matched. Include and tile walks are iterative with a visited set, so cycles and self-includes terminate and are flagged on the layout.

The Layout tab (read-only) browses the dump with the same join pipeline. Screens: every panel id with its layout, area, element, tile and set counts, a filter by area (areas with no anchor show as "unassigned", never hidden) and by name, and the by-area breakdown of screens and of layouts. Selecting a screen shows how many layouts sit below it (through includes and tiles) by area; an outline of its layout's elements with their classes; and its composition sets, variants and cells. Includes expand one level at a time with a cycle guard (an include back to a layout already open, or to itself, is marked and not opened); the outline has a search by element name or class and a node cap with a truncation notice. Class chips carry the evidence state (verified, or runtime-observed with an asterisk) and clicking one shows where it paints. Composition and cell views show grid x, y, w, h and the size limits as cell units, and flags, alignments, layout mode, preset and conditions exactly as stored. The tab itself has no edit controls and only reads; stored placement edits (below) are a separate, opt-in mode on the composition and cell view. The dump has no geometry, so nothing in the tab is a position on screen.
Honest limits:
- **Lower bound.** The dump has no template or table-factory (attribute) references, so screens reached only through those are not covered. Any "where it paints" result lists at least where a token paints.
- **No geometry.** The dump knows which layouts, elements and grid cells exist, not where anything is on screen.
- **Runtime-added classes are unverified** unless the exporter observed them.
- **Code-driven colours are not covered.** Colours set from game code (position chips, gradient start and end, rich-text colour tags, component colours) and inline layout styles are invisible to this join. Every result carries that warning.
## Workflow

1. Setup: auto-detect or paste the game path, take the vanilla snapshot (game closed, stock files), build the index.
2. Project: New, blank or from the crimson preset (generated from the index of the installed build).
3. Tokens: search, pick, override with an RGBA colour or a raw value. Literals: swap in `rgba` or `rgb-keep-alpha` mode, or "Only this" to append a rule with the same selector.
4. Build: specificity pass, `token_patch.SheetPatcher` on fresh copies of the snapshot, structural gate, contrast report. Output in `workspace/build/<project>/<ts>/` with `build-report.json`. Optional: selector reach against the game's visual trees.
5. Install: refused when the gate failed, the game runs, or Steam is updating. Backs up, copies changed bundles only, re-hashes, rolls back on mismatch, logs to `logs/install-log.jsonl`.

Workspace: `~/Library/Application Support/FM27SkinEditor/` (override with `FM27SE_WORKSPACE`). `config.json` lives there.

## What happened to each original tool

| Tool | Decision | Where |
|---|---|---|
| token_patch.py | Core. Vendored verbatim (UnityPy import moved into `main()`). | `skin_editor/token_patch.py`, driven by `patcher.py` |
| uss_decompile.py | Core. Decoder kept equivalent; token inventory is the style index. | `uss.py`, `index_styles.py` |
| specificity_pass.py | Core. Ported; runs at build on every sheet's appended rules, reads the index. | `specificity.py` |
| verify_build.py | Checks 1 to 3 ported as the gate that blocks install. Check 5 (typetree part) ported as selector reach. Check 4 (residual purple and navy) dropped: Crimson-specific. Raw-byte search dropped. | `verify_static.py`, `layout.py` |
| contrast_gate.py | Ported; reported per build, does not block. Backdrop is `options.contrast_backdrop`. | `verify_static.py` |
| make_crimson_json.py | Rule body vendored verbatim as a preset; token inventory comes from the index. | `presets/crimson.py` |
| header_sweep.py | Not ported. The crimson preset therefore lacks the header sweep rules (`make()` accepts them as `sweep_rules`). Needs every visual tree plus per-skin classification lists. |
| uxml_dump.py | Superseded by `bundles.read_visual_trees` (same walk, iterative). |
| uss_dump.py | Dropped. Its own successor says its selector and property tables are wrong. |
| write_token_map.py | Dropped. `build-report.json` carries totals, hits, specificity log and contrast rows. |
| live_reach.py, probe_ancestors.py | Dropped. Both need the Windows inspector. |
| uxml_edit.py, uxml_hide.py, sidebar_build.py | Not ported. UXML writes (patched SerializeReference writer, raw class swaps, sidebar clone) are a separate bundle pipeline with hard-coded Crimson and Tactical Navy targets. |
| grid_patch.py | Not ported. `tile_placement` stays stored only until a grid edit has been installed and checked in game. |
| bg_replace.py, font_replace.py, font_coverage.py | Not ported. Texture and font bundles are outside the snapshot, build and install set; `font_tokens` in token_patch is unused. |
| ctrl_dump.py | Dropped. FM26 skin analysis. Its `CLASS_TOKEN` regex does not compile, so the script fails at import. |

## Status

Tested here (21 unit tests plus an HTTP run): colour conversions at the boundaries, percent-alpha normalisation at the two legacy project-data boundaries only, out-of-range bundle colours as collected failures with build refusal, the diagnostic's analysis, schema 1 to 2 migration and round trip, alpha 0.5 and 0.652 through SheetPatcher and the decoder, RGBA literal keys, alpha-composited contrast, launcher generation and shell constraints, the cold-start two-click lock, server state files, ping and quit, the vendored patcher driven through the app, decoder against the patcher's encoder, project validation, specificity pass, gate, contrast, reach matching, crimson preset generation and build, snapshot, index, build, install, rollback paths, restore. All against synthetic StyleSheet typetrees and fake bundle files.

Not tested: anything against real FM27 bundles, UnityPy load and `env.save(pack="original")` through this app, `bundles.inspect` and `read_visual_trees` on real files, macOS paths, the `pgrep` process check, the game accepting the output. Run section 11 experiments 1, 2, 3, 5, 6 of LEARNINGS.md on the Mac before trusting an install.

## Preview

The Preview tab shows a measured screenshot of a vanilla screen repainted with the selected project. Four models ship in `data/models`: tactics, tactics-instructions, squad and portal. They were measured on Windows with the FM27 inspector, build 27.0.1.2494769.

- **What it shows.** Every region whose colour comes from a stylesheet token or literal gets its skin colour. Code-painted regions keep their measured colour.
- **Inspecting a region.** Hover a region to see what paints it. Click it for the rule, the alias chain and the vanilla vs skin colour.
- **Editing.** For a token region, edit the colour and the screen repaints instantly; Save stores the override.
- **Gradients.** A gradient is trusted only when its matched rule explains the vanilla colour. On these four screens every gradient is code-bound, including the Tactics toolbar.
- **Scoped rules.** They are matched on the element only, so those hits are marked approx.
- **Building more models.** Run `python tools/build_preview_model.py MEASURE.json SCREENSHOT.png NAME` (Windows, from an inspector measurement).

Verify compares an in-game screenshot with the project's expected colours. It judges only opaque background regions whose centre sample the builder confirmed on the measured screenshot: 40 on tactics, 20 on squad, 9 on portal, 19 on tactics-instructions.

## Images and SVGs

The Images tab lists every texture and SVG in the game's `ui-*` bundles: 1,728 in all, with thumbnails, filters and search. Pick one, choose a replacement and the project stores it. Build writes it into a fresh copy of the bundle, and Install puts it in the game with a backup, the same as the style bundles.

- **Images (PNG/JPG/WebP)** are fitted to the original size (cover, contain or stretch) and re-encoded in the original format. A Crunch-compressed texture is written as plain DXT, which makes a larger file.
- **SVGs** are converted to the game's vector mesh. Only filled shapes are converted: strokes and gradients are ignored, and edges are not anti-aliased.
- **Snapshot.** An image bundle joins the vanilla snapshot the first time you use an image from it, and only when the live file is stock.
- **Gate.** It checks that every object you didn't swap is identical to vanilla.
- **Removing a swap.** Remove it, then Build and Install; the next install puts the original back.

Proven in game (Windows, 2026-11-13):
- The editor's build of a wallpaper swap showed in game.
- The `fm27_skin_blended` wallpaper on report and tool pages (Recruitment, for example) is recoloured by the game with the club colour, so only the light and dark of a replacement show there.
- The loading screen uses `fm27-background-texture` blended with `fm27_skin_default`.

Not proven or not covered:
- **SVG swaps** are built and gate-checked, but not yet seen in game.
- **Icons (kind "icon").** Most UI icons are bitmap sprites in the icon atlases (`ui-icons_assets_1x..4x` with `ui-iconspriteatlases_assets_1x..4x`, 1,341 icons), picked by a stylesheet class such as `.game-concepts-win_small`. An icon swap draws your PNG or SVG into the icon's slot in the atlas at all four UI scales. The Crunch atlases are written back as plain DXT5, a few MB larger.
- **Proven in game (2026-11-13):** the Portal's win and draw result icons changed to the test shapes.
- **Not yet seen in game:** SVG swaps into the 286 VectorImages (most of the UI uses the atlas icons instead).

## FM Skin Studio (new interface, `studio/`)

In-game checklist and prepared packages (?): the script for a hands-on session and every build that has a `package.json` (gate result, plan digest, file hashes). `python -m skin_editor verify-stock` says in one line whether the game's UI bundles are stock.


Tile layout (T): the game's grid compositions per screen and breakpoint as a canvas; drag a cell or type x/y to move it (positions only, a cell's size is derived from its configs), validation list, stored as placement edits and written by a bundle build. Table views (V): columns, widths, order and visibility of the game's tables, edited as small per-view patch files (bundle target). Both load the real layout index (FM27_LayoutMCP) through `layout.export_index`.


Layouts (L): the game's UXML element trees with an inspector; add/remove classes, set inline styles or attributes the game already uses (small per-layout patch files, bundle target only). Fonts: assign a .ttf/.otf to a font token (native target). Build panel: Build bundles, Install build, Restore stock.


Game updates (U): profiles of game builds, the diff between two of them and the state of each project item. PREVIEW tab: write the project as a native `<name>-preview` skin, reload it in the running game and screenshot it through the inspector (falls back to a static repaint and says why).


Images (activity bar I): the game's picture next to yours for every swap, fit and where-shown, a conflict report, and a browser of all game images to replace.


Bundle target: in a rule sheet under `styles/`, `/* replace: .selector */` before a rule changes the game's own rule in place and `/* remove: .selector | prop, prop */` deletes declarations from it. The Build panel's plan shows how many game rules each one hits.


Features: project folders with a Monaco editor, live diagnostics with quick fixes, a Problems panel, project-wide search, a palette view for token colours, read-only vanilla sheets (G), a plan of what a build would do and drop, and import of any native USS skin folder (the download icon next to PROJECTS). Open tabs and the open project are remembered. The old page stays available for the bundle route until phase 3.


A project is now a folder of text files (`docs/SKIN-BUILDER-SPEC.md`, part 3). The new interface edits those files in Monaco with a Problems panel and builds from them.

- **In a browser (works now):** start the engine (`python -m skin_editor serve --no-browser`), then in `studio/` run `npm install` once and `npm run dev`, and open `http://127.0.0.1:1420/?engine=http://127.0.0.1:PORT&token=TOKEN` (PORT and TOKEN are in the engine's URL).
- **As a desktop app (Tauri):** `npm run tauri dev` in `studio/`. It needs Rust and the Windows SDK (both installed on this machine); it starts the engine itself.
- Existing projects keep working in the old page. Convert one with `python -m skin_editor rpc project.migrate '{"project": "NAME"}'` (verified first; the old file is kept as `.migrated`).

**Render (activity bar R, Phase 9):** draws any game layout offline and explains every element (which rules matched, where each value and token comes from, in both directions between the render and your editor); large layouts are drawn about 1,000 elements at a time with a "show" button per collapsed branch. It is an approximation: the published calibration report is `docs/evidence/phase9-m7-calibration-20261114/`, the user guide is `docs/RENDER-GUIDE.md`.

## Engine API

Every operation is also available as a named, schema-checked method:

- `python -m skin_editor methods` lists them; `docs/API.md` is the reference.
- `python -m skin_editor rpc tokens.get '{"name": "--colours-ui-deep"}'` calls one from the command line. Jobs are waited for; `--out FILE` saves binary results.
- `POST /rpc` (JSON-RPC 2.0) and `GET /events` (job events) serve the same methods to a UI.

The page's own `/api/...` routes call the same engine functions.

## Two ways to apply a skin (per project, Build tab)

- **Native skin folder** (recommended). It is written to `Documents\Sports Interactive\Football Manager 27\skins\<name>\`, and FM27 loads it itself (Preferences, next to "Reload Skin"). No game file changes, and it survives updates.
  - `tokens.uss`: token overrides.
  - `rules.uss`: the club-colour rules plus the `.nav-on-light` rules set to their dark-bar values (so light club colours keep a readable top bar), one copy of every game rule that uses a swapped colour, and the scoped rules last.
  - `images.uss`: icon and SVG swaps on the game's own icon classes (read from the FMImages stylesheets). Wallpapers are hidden and covered, the way the Jonukas skin does it: the game's picture is made transparent (`#Card-frame`) or painted over, and yours is drawn on the places you tick on the Images tab: report pages, main screens, start screen, loading, match intro.
  - Every export checks that each sheet parses and that each `url()` points inside the folder. Re-exporting replaces only a folder the editor wrote.
- **Game bundles.** Build patches copies of the game's bundles; Install puts them in with a backup. This route can also replace textures, atlas icons and SVGs inside the game files. Steam updates and Verify Integrity undo it.

Use one route at a time: a native skin on top of an installed bundle skin applies the changes twice.

## Export originals and compare skins

- **Export.** Images tab: "Export original at true size" for one item, or "Export these N" for the current filter (into `<workspace>\exports\<time>\` with an `index.csv`).
  - Textures export as full-resolution PNG.
  - Icons export as PNG at 1x, 2x, 3x and 4x, at the exact pixel size of each atlas slot (for example 16, 32, 48 and 64 px).
  - The game's vector icons export as an editable SVG at their own size, plus an 8x PNG. Rounded edges are exact ellipse clips or bands, matching the game.
- **Compare tab** (read-only). Load another skin's folder: a native USS skin (`skin.json` + `.uss`, for example from FM forums) or another skin's `.bundle` files. It shows:
  - the tokens it changes against vanilla, with swatches, and its own tokens;
  - its images and fonts, sheets, rule techniques and rules;
  - for bundles, the images that differ (vanilla | theirs).

  "Preview its colours" repaints the measured screens with its colour tokens. "Copy its colours into a new project" starts a project from them.
- **Native skins:** FM27 loads USS skins from `Documents\Sports Interactive\Football Manager 27\skins\<name>\skin.json` (Preferences, next to "Reload Skin"), with no game files changed. See `docs/analysis-jonukas-wood.md`.

## Club colours

Project page, Options: **Remove club colours** (off by default), with one replacement colour (default #171717). When ticked, the build adds 20 rules and renames the club-theme classes `nav-on-light` / `nav-on-dark`. These are the rules proven in game in the Crimson skin:

- code-bound club gradients, textures, the club wallpaper and news header bands stop drawing;
- the bars behind them take the replacement colour;
- the kit strip and its club outline disappear;
- the top-bar text stays light for every club.

Not covered: the Crimson header-sweep rules for other club-bound headers, and the club-coloured shirt numbers on the pitch. The rules go before the project's own scoped rules, so a project rule wins at equal specificity.

Not built: tile placement, UXML edits, fonts, backgrounds, patch diff beyond hash-based change detection, PyInstaller packaging (the launcher runs the source tree in a venv).

## Differences from the original pipeline

- Exact-RGBA literal swaps are an added pass in `patcher.py`; the vendored token_patch is still unmodified.
- The contrast report adds a pair against the backdrop for every scoped rule that sets `color` without a surface. contrast_gate.py skipped those.
- Only sheets the patcher changed are saved, and only bundles with a changed sheet are written. The original saved every sheet and every bundle. An untouched bundle is installed as the vanilla file.
- Project values are limited to what token_patch encodes in a verified way: colours (canonical objects), `var(--x)`, px, %, numbers, identifiers. deg, em, rem, s, ms are rejected: token_patch, uss_decompile and uss_dump carry three different unit tables and only 1 px and 2 % are verified.
- The decoder prints units 3 and up per Unity's `Dimension.Unit` enum (3 s, 4 ms, 5 deg).
- The specificity pass does not write raised selectors back into the project. The raised spec is stored in `build-report.json`.
- A branch with no class and no id cannot be raised; the original would crash there, the port reports it as a build warning.
- `reverts` drops the token override at build time. Build starts from vanilla.
- token_patch order is unchanged, so a literal swap also recolours a token value written in the same build if the colours match. The crimson preset asserts that it has no such clash.
- Install refuses when a live bundle matches neither the snapshot, the last install, nor the build (game updated or verified), and the process check fails closed.
