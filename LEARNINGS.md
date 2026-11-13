# FM27 Skin Editor: LEARNINGS

Purpose: everything known (and not yet known) about building a local skin editor for Football Manager 27, so a fresh session or another developer can build it from this file alone. No application code exists yet. This file was written on Windows 11 from work done on the Windows Steam build; the target platform is macOS, which has **not** been tested.

## How to read the tags
- **[V]** verified on the Windows Steam build, game `27.0.1.2494769`, Unity `6000.3.18f1-custom`, with a tool run or an in-game check. Date range of the work: 2026-11-03 to 2026-11-11.
- **[I]** inferred (from docs, naming, other Unity games, or a prior brief) but not checked.
- **[U]** unverified assumption with an experiment listed in section 11.

Everything about macOS is [I] or [U]. Everything about bundle contents is [V] on Windows and [I] for macOS (the macOS build uses a different Addressables platform folder and different bundle files, see section 2).

Source documents that back this file (all on the Windows machine):
- `D:\drive\FM27_SKIN_BRIEF.md` (31 KB): the original skin brief, token mapping, tooling, verification.
- `D:\drive\FM27-Crimson\workspace\tools\` : `token_patch.py`, `uss_decompile.py`, `uss_dump.py`, `uxml_dump.py`, `uxml_edit.py`, `uxml_hide.py`, `grid_patch.py`, `verify_build.py`, `make_crimson_json.py`, `live_reach.py`, `contrast_gate.py`.
- `D:\drive\FM27-Crimson\workspace\notes\` : `token-map.md`, `colour-reach-report.md`, `tile-grid-analysis.md`, `inspector-spec.md`, `keyword-encoding-proof.md`, `CONTINUE-SKIN-tacticalnavy.md`.
- `C:\Users\Admin\Downloads\FM27_ColorFinder_v2\` : the Colour Finder (HTML/JS) and its `verify\` scripts and `REPORT.md`.
- `C:\Users\Admin\Downloads\FM27_LayoutMCP\` : the layout index (`tools\build_index.py`, `layoutdb.py`, `server.py`, `docs\layout-format.md`, `docs\phase3-notes.md`) and `C:\Users\Admin\Downloads\FM27_LAYOUT_MCP.md` (spec incl. Part 2 Figma round trip).
- `C:\Users\Admin\Downloads\SKIN\` : `01_CURRENT_SKIN_install_this` (final crimson skin), `02_history_versions`, `03_backups_original_game_files`, `04_patch_specs`, `README.md`.

**Not found on this machine:** `fm27_bundle_diff.py` (named in the task text). Search of C:\Users\Admin and D:, E:, F: found nothing. Treat its description (UnityFS v7, LZ4/LZMA, type trees, GUID lookup) as [U] until the file is located; UnityPy covers the same ground and is what all verified work used.

---

## 1. Environment

### 1.1 Verified on the build machine (Windows) [V]
| Item | Value |
|---|---|
| Python | 3.14.10 (works). Scripts also run on 3.10+ per the brief. |
| UnityPy | 1.25.4 (requires astc-encoder-py, attrs, brotli, etcpak, fmod_toolkit, fsspec, lz4, Pillow, texture2ddecoder, tpk_ar...) |
| Other packages present | etcpak 0.9.15, pillow 13.0.0, lz4 4.4.5, brotli 1.2.1, texture2ddecoder 1.0.6, archspec 0.2.7, fsspec 2026.9.0, mcp 2.3.0 (layout MCP only), pyfmodex 0.7.2 (not needed) |
| Node.js | needed only for the Colour Finder build (`build.js`, `measure.mjs`) |
| Run flags | `python -I` ignores the user site-packages: if UnityPy was installed with `pip install --user`, `-I` fails with `No module named 'UnityPy'`. Use a venv, then `-I` is safe. [V] |

### 1.2 macOS setup (proposal) [I]
```zsh
# Python 3.12 recommended for PyInstaller/UnityPy wheel availability (3.14 on macOS is [U]).
brew install python@3.12
python3.12 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
python -m skin_editor            # starts the backend, prints http://127.0.0.1:8765
```
`requirements.txt` (pin exactly; these versions are the ones the verified work ran on, platform wheels for macOS arm64/x86_64 must be confirmed [U]):
```
UnityPy==1.25.4
Pillow==13.0.0
etcpak==0.9.15
lz4==4.4.5
brotli==1.2.1
texture2ddecoder==1.0.6
fsspec==2026.9.0
# the web layer: the standard library http.server + json is enough for a localhost app and freezes cleanly; add a framework only if needed
```
UnityPy pulls the rest by itself. `UnityPy/resources/lzma.tpk` ships inside the package and holds the type-tree package (needed at runtime, see section 10). [V]

### 1.3 Existing scripts and how they become modules
| Existing file | Becomes | Notes |
|---|---|---|
| `tools/token_patch.py` | `backend/patcher.py` (library) | Keep `SheetPatcher`, `parse_selector`, `specificity`, value encoders. Replace `main()` and the `sys.argv`/`print` I/O with a function taking a project and returning a report (section 8). |
| `tools/uss_decompile.py`, `uss_dump.py` | `backend/uss.py` | Typetree to readable USS. Used by `extract.py`. |
| `FM27_ColorFinder_v2/extract.py` | `backend/index_styles.py` | Hard-coded `TOOLS = D:\drive\...`; must import from the package instead. Writes the `{bundle: {sheet: {rules:[{i,s,t,p:[[prop,value,colourIdx]]}]}}}` shape. |
| `FM27_ColorFinder_v2/build.js`, `app.template.html`, `refresh.ps1` | `frontend/` + `backend/index_styles.py` | The viewer is one self-contained HTML. In the app the data is served as JSON instead of embedded. `refresh.ps1` becomes a CLI subcommand. |
| `FM27_LayoutMCP/tools/build_index.py`, `layoutdb.py` | `backend/index_layout.py`, `backend/layoutdb.py` | SQLite layout index (section 7). `server.py` (MCP) is optional and stays out of the app. |
| `tools/uxml_dump.py`, `uxml_hide.py`, `uxml_edit.py`, `grid_patch.py` | `backend/uxml_edit.py`, `backend/grid_edit.py` | Needed only for build step 4 (tile placement). Not yet validated on live installs. |
| `tools/verify_build.py` | `backend/verify_static.py` | Static post-build checks (hash and token presence). |
| `fm27_bundle_diff.py` | not found | See above. |

---

## 2. macOS paths and auto-detection

### 2.1 What is verified (Windows) [V]
- Steam default: `C:\Program Files (x86)\Steam\steamapps\common\Football Manager 27\`
- Data folder: `fm_Data\` ; Addressables folder: `fm_Data\StreamingAssets\aa\` containing `catalog.bin` (binary Addressables catalog; header bytes `42 89 e3 0d 02 00 00 00` = magic 0x0DE38942, version 2), `catalog.hash`, `settings.json` and the platform folder `StandaloneWindows64\` with 534 `.bundle` files (UI bundles are the `ui-*` ones; the rest are characters, match, scenes, shaders, crowd).
- Executable: `fm.exe` (process name `fm`). The game also has `GameAssembly.dll` (IL2CPP) and `UnityPlayer.dll`.
- User data: `Documents\Sports Interactive\Football Manager 27\` (games, tactics, matches), `%LOCALAPPDATA%\Sports Interactive\Football Manager 27\` (logs, preferences), `%USERPROFILE%\AppData\LocalLow\Sports Interactive\Football Manager 27\Player.log` (Unity log).
- A game update rewrites bundles and `GameAssembly.dll` (2026-11-10 18:24 on the build machine: dozens of bundles incl. characters, shaders, UI). Later that night (23:31) 15 UI bundles (the 11 skin bundles plus fonts, textures, tactics, table views, tile layouts, data collections) were rewritten back to stock, which is consistent with Steam "Verify integrity of game files" [I: the cause was not observed; the 11 skin bundles were byte-identical to the vanilla backup afterwards, which is observed]. The skin must be re-installed after an update or a verify. [V for the effect]

### 2.2 macOS: the task text says `Football Manager 27.app/Contents/Resources/fm_Data/StreamingAssets/aa/`. This is probably wrong. [U]
Unity macOS players keep data in `<App>.app/Contents/Resources/Data/` (the `fm_Data` name is a Windows/Linux naming convention). Proposed candidates, to be confirmed by listing a real install:
```
~/Library/Application Support/Steam/steamapps/common/Football Manager 27/Football Manager 27.app/Contents/Resources/Data/StreamingAssets/aa/StandaloneOSX/   [I]
/Users/Shared/Epic Games/FootballManager27/.../Football Manager 27.app/Contents/Resources/Data/StreamingAssets/aa/StandaloneOSX/                    [I, Epic path is a guess]
```
Auto-detection algorithm [I]:
1. Candidate library roots: `~/Library/Application Support/Steam/steamapps/common`, every library listed in `~/Library/Application Support/Steam/steamapps/libraryfolders.vdf` (parse the `"path"` entries and append `/steamapps/common`), `/Users/Shared/Epic Games`, `~/Applications`, `/Applications`.
2. In each root look for a directory named like `Football Manager 27*` / `FootballManager27*` / `FM27*`.
3. Inside it find the `.app`, then `glob('**/StreamingAssets/aa')` under the `.app` (do not hard-code `Data` vs `fm_Data`). Take the child directory whose name starts with `Standalone` and contains `*.bundle` files. Require `ui-styles_assets_common.bundle` and `ui-styles_assets_default.bundle` to exist.
4. On several hits, let the user choose; store the choice in `config.json`.
5. Never follow symlinks out of the library root.

### 2.3 Platform difference that matters [I]
Addressables builds one folder per build target (`StandaloneWindows64`, `StandaloneOSX`, ...). The macOS bundles are **different files** from the Windows ones (platform-specific serialisation, shaders, textures). The UI bundles (StyleSheet, VisualTreeAsset, tile data) contain managed-object data and are likely structurally identical, but the editor must index the macOS bundles itself; it must not reuse a Windows index or a Windows-built skin. Whether the macOS game build ships the same game version and bundle names is [U].

### 2.4 Process check for Install [I]
Windows: process `fm` (`Get-Process fm`). macOS proposal: `pgrep -f "Football Manager 27.app/Contents/MacOS"` (exit code 0 = running). The actual executable name inside `Contents/MacOS/` is [U]; read it from `Contents/Info.plist` key `CFBundleExecutable` at detection time and use `pgrep -x <name>` plus the path form as a second check. Refuse to install if either matches. Also refuse if the Steam client reports the app as updating (check `appmanifest_*.acf` field `StateFlags` != 4) [I].

### 2.5 Screenshots on macOS [I]
No external process can inspect the game. Options, in order of effort:
1. The user takes a screenshot (`Shift+Cmd+3`/`Shift+Cmd+4`) and drops the PNG on the Verify page.
2. A helper runs `screencapture -x -R<x>,<y>,<w>,<h> out.png` (needs Screen Recording permission for the terminal/app: System Settings > Privacy & Security > Screen & System Audio Recording) or `screencapture -l <windowid>` after finding the window id with `CGWindowListCopyWindowInfo` (needs pyobjc, [U]).
3. The in-game Windows inspector (BepInEx plugin `FM27Inspector`, pipe `\\.\pipe\fm27-crimson-inspector`) does not run on macOS as built. Porting BepInEx 6 IL2CPP to macOS is [U]; do not depend on it. Preview models are therefore **built on Windows and shipped as data** (section 6.6).

---

## 3. Application directory layout (proposal) [I]
```
fm27-skin-editor/
  pyproject.toml / requirements.txt
  skin_editor/                 # Python package (backend)
    __main__.py                # starts the localhost server
    config.py                  # loads/creates config.json
    detect.py                  # install detection (2.2), process check (2.4)
    bundles.py                 # UnityPy helpers: open, hash, list, container GUIDs
    uss.py                     # StyleSheet typetree <-> readable rules/values
    index_styles.py            # tokens + rules index (7)
    index_layout.py            # layout/compositions/tiles index (7)
    patcher.py                 # SheetPatcher + build (8)
    install.py                 # backup, copy, hash log, verify (9)
    verify.py                  # screenshot vs model (9.3)
    server.py                  # http server + JSON API
  frontend/                    # HTML/JS (Colour Finder derived): editor, preview, token drawer
  data/
    models/                    # shipped preview models per screen (boxes, regions, states), built on Windows
    presets/                   # preset themes (JSON skin projects)
  workspace/                   # per-user, outside the app bundle (see config: workspace_dir)
    cache/                     # indexes (SQLite, JSON) keyed by game build + bundle hashes
    vanilla/                   # read-only copy of stock bundles (the "vanilla backup")
    projects/                  # skin project files *.skin.json
    build/<project>/<ts>/      # built bundles + build-report.json
    backups/<ts>/              # pre-install backups with manifest.json
    logs/                      # install-log.jsonl, app.log
```
Workspace default on macOS: `~/Library/Application Support/FM27SkinEditor/`. Nothing mutable lives inside the `.app` (it is read-only once signed). [I]

---

## 4. config file schema (`config.json`) [I]
```jsonc
{
  "schema": 1,
  "game_dir": null,              // string|null: path to the app bundle or install root; null = auto-detect (2.2)
  "aa_dir": null,                // string|null: resolved .../StreamingAssets/aa/<platform>/ ; derived from game_dir if null
  "platform_folder": "auto",     // "auto" | "StandaloneOSX" | "StandaloneWindows64"
  "store": "auto",               // "auto" | "steam" | "epic"
  "workspace_dir": "~/Library/Application Support/FM27SkinEditor",
  "vanilla_dir": null,           // null = <workspace_dir>/vanilla ; must be read-only after creation
  "process_names": ["fm", "Football Manager 27"],   // executable names for the running check
  "process_check_cmd": "pgrep -f",                  // macOS; Windows uses tasklist
  "server": { "host": "127.0.0.1", "port": 8765, "open_browser": true },
  "index": { "reindex_on_start": "if_changed", "hash": "sha256", "workers": 2 },
  "build": { "keep_last_builds": 5, "flatten_gradients_default": false },
  "install": { "require_game_closed": true, "backup_keep": 20, "verify_after_copy": true },
  "verify": { "tolerance_rgb": 6, "tolerance_alpha": 0.02, "sample": "region_centre_3x3" },
  "log_level": "info"
}
```
Rules: the server binds to 127.0.0.1 only. `vanilla_dir` and the game dir are never written by Build; only Install writes the game dir.

---

## 5. Skin project file (`*.skin.json`, versioned) [I, shape derived from the verified `token_patch` spec]
Mapping to the proven patcher spec: `tokens` -> `token_overrides`, `literal_map` -> `literal_swaps`, `append_rules_by_sheet` -> `scoped_rules`, `skip_sheets`/`flatten_gradients` -> `options`.
```jsonc
{
  "schema": 1,
  "name": "crimson-dark-tactics",
  "game_build": "27.0.1.2494769",           // build the project was authored against
  "vanilla_manifest": "sha256 of manifest of the 11 style/layout bundles used",
  "options": { "flatten_gradients": false, "skip_sheets": [] },

  "token_overrides": [
    { "token": "--colours-tactics-base-20", "value": "#A40029",
      "vanilla": "#188B78",                 // kept for revert and the "reach" display
      "note": "tactics buttons" }
  ],

  "literal_swaps": [
    { "from": "#DA0037", "to": "#6C001C",   // matches RGB everywhere (alpha kept); see warning below
      "scope": "all_sheets", "hits_expected": 14 }
  ],

  "scoped_rules": [
    { "sheet": "AlwaysAppliedStyleSheet",
      "selector": ".tactics-collapsable-pitch-container.tactics-collapsable-pitch-container",
      "props": { "background-color": "#6C001C" },
      "why": "hard-coded #DA0037 in this rule; doubled class raises specificity above the original" }
  ],

  "tile_placement": [                        // build step 4, not implemented
    { "composition": "SquadComposition-Large", "cell_index": 3, "cell_id": "Atmosphere",
      "location": { "x": 0, "y": 6, "width": 12, "height": 6 },
      "vanilla_location": { "x": 6, "y": 0, "width": 6, "height": 6 } }
  ],

  "reverts": ["--colours-tactics-defender-background", "--colours-tactics-striker-background"]
}
```
Semantics (all [V] from the patcher unless marked):
- `token_overrides`: rewrites the token definition in **every** stylesheet that defines it in a `:root` / `.unity-theme-env-variables` rule (the same token is defined in `FigmaStyleVariables`, `AlwaysAppliedStyleSheet`, `FigmaGeneratedStyles`, `FMColours`, `SIStyles`, `iPhoneStyles`, `FMCStyles`).
- `literal_swaps`: recolours **every** literal RGB match in every rule of every non-skipped sheet. There is no per-element scope; a literal swap can hit unrelated rules (e.g. `#DA0037` appears in many rules). The UI must show the hit list (the patcher records `literal_hits` with sheet, selector, property) before building, and offer "change only this element" (a scoped rule) instead.
- `scoped_rules`: appended to the named sheet's `m_Rules` with specificity computed as `1 + 100*ids + 10*(classes+pseudo) + elements`. Verified in game: the appended pitch-panel rule won over the original rule. Rule order across different sheets is not controlled; make the specificity strictly higher than the rule being overridden.
- `reverts`: tokens whose value is set back to the vanilla value (used for "Squad positions back to vanilla"); implemented as token overrides with the vanilla value.
- Only restore / override what the project lists; Build always starts from fresh vanilla bundles, so removing an entry is a revert.

---

## 6. Bundle and style data model

### 6.1 Folder and bundle inventory [V]
Style bundles (the ones skins change): `ui-styles_assets_common.bundle` (5 StyleSheets: `FigmaStyleVariables`, `SIStyles`, `default`, `IGEStyles`, `UnityDefaultRuntimeTheme`, plus 24 small icon textures, 1 material, 1 font) and `ui-styles_assets_default.bundle` (44 StyleSheets incl. `AlwaysAppliedStyleSheet`, `FigmaGeneratedStyles`, `FMCStyles`, plus 2 stylesheet-config assets). Smaller: `ui-styles_assets_1x/2x/3x/4x` (image sheets, 7 each), `ui-styles_assets_match` (`MatchUIStyles`), `ui-styles_assets_` (`MatchWCCompetitionStylesheetConfig`).
Layout bundles: `ui-visualtreeassets_assets_{gameworld 5081, global 2005, match 244, fantasydraft 69, intro 64, init 4}visualtreeassetpreload.bundle` = 7,467 VisualTreeAssets, each paired with an `inlineStyle` StyleSheet.
Data bundles: `ui-tileslayouts_assets_all` (4,185 objects: tile descriptions, grid compositions, composition sets), `ui-tactics_assets_all`, `ui-dynamiccardcollections`, `ui-panelids_assets_all` (623 panel ids), `ui-tableviews` (835 table view settings), `ui-tablefactories` (243 factories with cell layouts), `ui-globalnavigation`, `ui-datacollections`, `ui-staticdataentries`, `ui-factoryxml`, `ui-settings`, `ui-match`, `ui-managercreation`, `ui-calendar`, `ui-visualfunctions`.
Not skin-relevant: `ui-icons*`, `ui-fonts*` (font replacement is possible, see brief), `ui-backgrounds*`, `ui-textures`, `ui-prematch*`.

### 6.2 Reading with UnityPy [V]
- `env = UnityPy.load(path)`; objects of type `MonoBehaviour` expose `read_typetree()` even though `m_Script` PPtr does **not** resolve (the MonoScript lives in another bundle; `deref()` raises FileNotFound). The type tree is embedded in the bundle, so no scripts are needed.
- Identify asset kinds by the **key signature** of the typetree: StyleSheet has `m_Rules`; VisualTreeAsset has `m_HasEditorElements`; composition set has `m_gridBreakpointCompositionData`; composition has `m_gridComponents`; tile description has `<Configurations>k__BackingField`; table factory has `m_rowData`; table view has `m_tableView`; panel id has `m_panelDescription`.
- GUIDs: each bundle's `AssetBundle` object has `m_Container`, a list of `(32-hex key, PPtr)`. For layout bundles every key maps to exactly 2 assets (the VisualTreeAsset and its `inlineStyle` sheet); 7,467 GUIDs, no collisions. For style bundles keys map to StyleSheets (e.g. `d195ddc7caeea4b4e94073ea9321192e` -> `FMCStyles` in `ui-styles_assets_default`). For data bundles keys map to the data assets (e.g. `49c25af415c53814d8d3ed658d867204` -> `PlayerTableFactory`). `catalog.bin` is **not** needed to resolve any of these; it only matters for addresses of other asset types. [V]
- External PPtrs (`m_FileID` 2 or 3) point to other bundles; resolve by `path_id` across the indexed data bundles (path ids are 64-bit and unique in practice). Stability of path ids across game patches is [U].
- Saving: `obj.save_typetree(tree)` then `env.save(pack="original", out_path=dir)` (what `token_patch` does) rewrites the bundle with the same compression; the output keeps the original file name. [V]

### 6.3 StyleSheet decode rules (serialized USS) [V unless marked]
A StyleSheet MonoBehaviour has: `m_Name`, `m_Rules[]`, `floats[]`, `dimensions[]{value,unit}`, `colors[]{r,g,b,a}` (0..1 floats), `strings[]`, `assets[]{m_FileID,m_PathID}`, `m_ImportedWithErrors/Warnings`.
- **Rule** = `{ m_ComplexSelectors[{m_Specificity, m_Selectors[{m_Parts[{m_Type,m_Value}], m_PreviousRelationship}], ruleIndex}], m_Properties[{m_Id, m_CustomName, m_Line, m_Values[{m_ValueType, valueIndex}]}], line }`.
- **Selector part types** (`m_Type`): 1 wildcard (`*`), 2 element type (e.g. `SIGradient`), 3 class, 4 pseudo-class (`root`, `hover`...), 6 id (`#name`). `m_PreviousRelationship`: 0 first part, 1 child (`>`), 2 descendant (space).
- **Specificity**: `1 + 100*ids + 10*(classes + pseudo-classes) + element types` (wildcards add nothing). `m_Specificity` is stored per complex selector.
- **Property id**: built-in properties use `m_Id` (numeric StylePropertyId) with `m_CustomName` empty; custom properties (`--token`) use `m_Id = -1` and the name in `m_CustomName`. Map (from `token_patch.PROP_TABLE`, cross-checked against vanilla): `color 65536`, `font-size 65537`, `-unity-font-definition 65542`, `-unity-text-align 65546`, `visibility 65551`, `white-space 65552`, `align-content 131072`, `align-items 131073`, `align-self 131074`, `border-*-width 131076..131079`, `bottom 131080`, `display 131081`, `flex-basis 131082`, `flex-direction 131083`, `flex-grow 131084`, `flex-shrink 131085`, `flex-wrap 131086`, `height 131087`, `justify-content 131088`, `left 131089`, `margin-* 131090..131093`, `max-height 131094`, `max-width 131095`, `min-height 131096`, `min-width 131097`, `padding-* 131098..131101`, `position 131102`, `right 131103`, `top 131104`, `width 131105`, `border-color 262146`, `border-radius 262147`, `border-width 262148`, `flex 262149`, `margin 262150`, `padding 262151`, `transition 262152`, `background-color 458752`, `background-image 458753`, `border-bottom/left/right/top-color 458758/458761/458762/458763`, `opacity 458767`, `overflow 458768`, `text-overflow 196609`, `-unity-background-image-tint-color 196610`, `rotate 327680`, `scale 327681`, `transform-origin 327682`, `translate 327683`. Missing ids must be taken from `uss_decompile.py` (which has the full table).
- **Value types** (`m_ValueType`, `valueIndex` indexes the matching array): 1 keyword (global keyword index, **not** a string index: `inherit 0, initial 1, auto 2, unset 3, none 6`), 2 float, 3 dimension (unit 1 px, 2 %; further units 3 deg, 4 em, 5 rem, 6 s, 7 ms [I]), 4 colour, 5 resource path, 6 asset reference (`assets[]`), 7 enum string (every other identifier: `center`, `nowrap`, `absolute`, `column`... stored as an index into `strings[]`; this was a verified bug fix, writing identifiers as type 1 is wrong), 8 variable name (string), 9 string, 10 function, 11 comma, 12 scalable image.
- **`var(--x)`** is the three-handle sequence `[10 (valueIndex 1 = var), 2 (valueIndex -> float holding the arg count 1.0), 8 (valueIndex -> string "--x")]`. Alias tokens (`--a: var(--b)`) chain this way; resolve with cycle protection. Multi-value shorthands (`scale: 0.88 0.88`) are one handle per token.
- **Colours are not shared** between properties in the verified skin builds (1,899 references, 0 shared indices), so editing one `colors[]` entry changes one property. The Colour Finder README mentions "editing a shared slot changes all"; whether stock vanilla shares slots is [U] (experiment 11.4). `token_patch` always appends a new colour entry and repoints the handle, which is safe either way.
- **Token rules** are the `:root` rules (`m_Parts` contains pseudo `root`) and `.unity-theme-env-variables`. `FigmaStyleVariables` has 1 `:root` rule with about 1,750 custom properties; `AlwaysAppliedStyleSheet` has a `:root` with about 2,370 plus component rules (about 32k decompiled lines). About 930 colour values in `AlwaysAppliedStyleSheet` are literals (most common `#ffffff` 435, `#000000` 380, `#e6e6fa` 147).
- **Gradients**: buttons and banners draw an `SIGradient` child painted from `--start-colour` and `--end-colour`; 186 rules carry such a pair. The patcher option `flatten_gradients` copies start into end.
- There is no `text-transform` in USS; upper-case labels come from localisation or code and cannot be skinned.
- Competition sheets (e.g. `TransferDeadlineDay`, `UEFAUWCL`) redefine `--brand-theme-*` inside their own `:root`; they load on top of the base sheets for licensed competitions and are normally left alone.

### 6.4 Where a colour on screen comes from (the three classes the app must show) [V]
The inspector protocol `colour_source` returns, per element and property, `resolved` colour and `rules[]` (sorted by priority) with `{sheet, selector, specificity, order, value}`. **The real winner is the rule whose value resolves to the same colour as `resolved`**, not necessarily `rules[0]`. A colour is:
1. **Token-driven**: the winning rule's value is `var(--token)` (possibly via alias chain). Show the token, the chain, and its reach = all properties whose resolved value goes through that token. Reach counts come from the token index ("paints N places", as in `TOKENS_EXPLAINED.md`).
2. **Literal**: the winning rule holds `#RRGGBB[AA]`. Swappable with `literal_swaps` (global) or a scoped rule (single element).
3. **Code-driven**: no stylesheet rule produces the colour. Seen sources: inline UXML style (`m_RuleIndex` into the layout's `inlineStyle` sheet; this one **is** editable in principle via the layout's inline sheet), rich-text `<color=...>` tags in strings, component fields (e.g. `SIGradient` `startColour` / `endColour` with `useCustomStyles`, `SIButton` colours), and chip/role colours set by game code (e.g. position chips, availability chips, advisory colours). The app must warn "cannot be changed from a stylesheet" and list only the tokens the code reads where known (for the Tactics toolbar `SIGradient`, the inspector showed `startColour #B4002E` / `endColour #890022`, which equal the values of `--colours-feature-tactics-base-20` / `-40`; that these tokens feed it is [I], the toolbar looked right after those tokens were changed together with others).

### 6.5 Token families seen in the Tactics / Squad work [V]
- Tactics surface: `--colours-tactics-base-00/-20/-40/-50/-60/-80` and `--colours-feature-tactics-base-20/-20-a16/-40/-50/-60/-80` (the feature set feeds the toolbar gradient and `--interaction-tactics-surface-default/hover`).
- Position chips on Squad/Tactics: `--colours-tactics-defender-background` (vanilla `#00756B`), `--colours-tactics-striker-background` (`#BC007B`), `--colours-tactics-attacking-midfield-background` (`#8600C5`), midfield `#004AAA`, defensive midfield `#0B7200`, goalkeeper `#616161`; foreground variants separate. In the crimson skin these were aliased to a crimson value and were reverted to the vanilla literals; the generic `--colours-base-cyan-deep / pink-deep / purple-deep` tokens are also used elsewhere (attribute labels) so they were **not** reverted.
- Pitch panel: hard-coded `#DA0037` in rule `.tactics-collapsable-pitch-container` (a literal in `AlwaysAppliedStyleSheet`).
- Final project values used (for reference and as a preset): `#6C001C` (dark) and `#A40029`; see `C:\Users\Admin\Downloads\SKIN\README.md`.

### 6.6 Preview model (what the Colour Finder does) [V]
- Data: `extract.py` writes `data_live.json` / `data_vanilla.json` (rules + tokens + literals per sheet). `build.js` embeds them into `index.html`. Tabs: Colours, Hard-coded, Screens (7,397 UXML templates from `screens.js`, built by `re\*` scripts), Changes vs vanilla.
- Screen models for Portal, Squad and Tactics are **mock tabs** made from live measurements: boxes (x, y, w, h, z-order), resolved colours, semantic regions (e.g. toolbar, pitch panel), inferred hover/pressed states, and Skin/Vanilla modes (vanilla codes come from the vanilla bundles, not from the installed skin). Source files: `verify\mock-data.json`, `verify\mock-block.js`, `verify\apply-mock2.mjs`, `verify\measure.mjs`, `regions.json`, `states-inferred.json`, `<screen>-measure.json`. `window.__CF` exposes the app; the mock block sits between `<!--MOCK-START-->` and `<!--MOCK-END-->` in `app.template.html`.
- Measurement needs the live game plus the Windows inspector. For a macOS app the models are shipped as static JSON (`data/models/`); re-measuring requires a Windows machine, or an inspector port [U].
- Rules the measurement follows: skip full-screen tints larger than 5000 px² when building flat colours (they washed out the Tactics mock); alpha is composited over the backdrop in z-order.
- Known limit: colours from code and from runtime class setters are visible only through the inspector, not from stylesheets.

---

## 7. Indexing and diff strategy

### 7.1 Style index (tokens and rules) [V]
Inputs: `ui-styles_assets_common.bundle`, `ui-styles_assets_default.bundle` (about 1 minute). Output per sheet: rules with decoded selectors, properties (name, value text, colour index), whether it is a token rule. From this derive: token table (name -> value per sheet, alias chain, resolved colour), reach (properties using the token directly or through aliases), literal table (colour literals per rule), and a "changed vs vanilla" view (resolved colour compare). Record: bundle file name, sha256, sheet `m_Name`, sheet path id.
Conflict rule used by the Colour Finder: when a token is defined in several sheets, the value from `AlwaysAppliedStyleSheet` is taken as the reference and conflicts are flagged.

### 7.2 Layout index (SQLite) [V]
Built by `FM27_LayoutMCP\tools\build_index.py` in about 10 seconds for the UI bundles. Tables: `bundles(file, side, sha256)`, `assets(bundle_id, cab, path_id, class, name, guid, is_root)`, `elements(asset_id, local_id, parent_local_id, ord, type, name, classes, inline_rule, attrs_json, scope_json)`, `includes(from_asset, element_local_id, alias, to_asset)`, `stylesheet_refs`, `bindings(asset_id, element_local_id, attr, path)`, `selectors(stylesheet_asset_id, rule_index, selector, specificity)`, `data_refs`, `data_guids`, `element_refs`, `screen_grids`, `comp_sets`, `comp_set_variants`, `compositions`, `composition_cells`, `cell_configs`, `tile_descriptions`, `tile_description_configs`, `screen_tiles`, `unresolved`, `meta`. Counts on the verified build: 7,467 layouts, 135,434 elements, 14,658 includes (0 unresolved), 23,587 selectors, 1,823 compositions, 5,410 cells, 4,980 `screen_tiles` rows.
Layout format facts (full text in `FM27_LayoutMCP\docs\layout-format.md`):
- VisualTreeAsset (Unity 6.3): tree in `references.RefIds` (managed references). `m_VisualTree` = `{rid:1000}`; nodes are `VisualElementAsset` (`m_FullTypeName`, `m_Id`, `m_Children[{rid}]`, `m_Classes`, `m_RuleIndex`, `m_StylesheetPaths`), `TemplateAsset` (`m_TemplateAlias`), `UxmlObjectAsset` (binding components), and per-element `<Type>/UxmlSerializedData` linked by `uxmlAssetId == m_Id`. Element **name is in the serialized data** (`name`).
- Includes: `m_Usings[{alias, path (32-hex GUID)}]`; `TemplateAsset.m_TemplateAlias` -> alias -> GUID -> VisualTreeAsset.
- Template-instance overrides: a layout that includes a template stores serialized data for the template's elements right after the instance's own `m_SerializedData` record (so a grid override can name an element id that is not in the layout's own element list). Example: `RevampTacticalPlanner` instances of `FigmaBaseToolTemplate` override `GridLayout` (id 1730545546) with different composition sets.
- Screens: panel id (`ui-panelids`, field `m_panelDescription.uxml`) -> screen layout GUID (live inspector shows `Panel#<panel id>`). Screen layout holds only a grid element; tiles come from composition sets: `Bindings.m_gridCompositionSet` or `MultiGridLayoutElement.GridCompositionSets[]` -> `m_gridBreakpointCompositionData` (breakpoint 0..5 -> list of compositions) -> `m_gridComponents[]` cells -> `m_gridElementConfigs[].AssetRef.m_AssetGUID` -> tile layout.
- **Tile placement fields** (for build step 4): per cell `m_location{x,y,width,height}`, `m_minSize`, `m_maxSize`, `m_isLocked`, `m_isDynamic`, `m_isOptional`, `m_expandToContent`, `m_takesFocus`, `m_horizontalAlignment`, `m_verticalAlignment`, `m_features`, `m_configDescriptionKeys`, `m_optionalConditions`; per composition `m_optionalSlices.m_instantiationOrder`, `m_layoutMode`, `m_layoutPreset`, `m_optionalConditions`, `m_placementBindings`. Editing these is a data edit in `ui-tileslayouts_assets_all.bundle`; **no write has been attempted** [U].
- Tables: `StreamedTable` elements point at `FactoryAsset.m_AssetGUID` (a table factory in `ui-tablefactories`), whose `m_rowData` lists cell layout GUIDs; `ui-tableviews` holds per-view column settings (not linked yet).
- Live match quality (merged tree vs inspector element names, best variant): Squad 79.0%, Tactics 93.3%, Portal 83.9% of live names that have a layout source (all-names: 67.8 / 81.4 / 79.0). Remaining gaps: elements created in code, pitch position cells, table view column selection.

### 7.3 Patch detection and diff [I, partly V]
- Detection: store for every indexed bundle its sha256 and size plus the game version (read `Contents/Info.plist` on macOS or the `Player.log` first line `Unity ... / version` on Windows; `fm_status` of the inspector reports `27.0.1.2494769`). On start, re-hash the UI bundles (about 1.4 GB; hashing the 15 relevant bundles is fast); any change = re-index and diff.
- Style diff: compare per sheet name -> per rule key (selector text + property name) the value text; report added/removed/changed tokens and rules; map each changed token to the project entries that override it ("your override of X is now stale/obsolete").
- Layout diff (`layout_diff(asset)`): per layout GUID compare element lists (type, name, classes, parent, order) and `attrs_json`; list layouts added/removed/changed, then map to screens through `screen_tiles`/panel ids to answer "which screens changed".
- A project stores the vanilla value of every entry; after a patch the build shows entries whose vanilla value changed.
- Observed behaviour: the 2026-11-10 game update rewrote many bundles and `GameAssembly.dll` (timestamps 18:24) under the **same file names**. Bundle names are stable across patches, so detection must use hashes (and mtime as a hint), not names. [V]

---

## 8. The build/patch pipeline (today and as a library)

### 8.1 Today (`token_patch.py`) [V]
```
python token_patch.py spec.json OUT_DIR bundle1 [bundle2 ...]
```
Spec JSON keys (UTF-8 **without BOM**; a BOM raises `JSONDecodeError`): `tokens{--name:value}`, `literal_map{"#RRGGBB":"#RRGGBB"}`, `skip_sheets[]`, `flatten_gradients`, `rename_classes{old:new}`, `append_rules_by_sheet{sheet:[{selector, props{prop:value}}]}`, optional `font_tokens` + `fonts_bundle`. Value syntax: `#RRGGBB`, `#RRGGBBAA`, `rgba(r,g,b,a)`, `var(--x)`, `12px`/`50%`, number, keyword. Steps per MonoBehaviour with `m_Rules`: rename classes -> (unless sheet skipped) patch token rules (`:root`) -> recolour literals in all rules -> flatten gradients -> append rules. Output: patched bundle files in `OUT_DIR` with the same names plus `token_patch-report.json` (`totals`, `tokens_not_found`, `literal_hits[]`). It refuses an `OUT_DIR` whose path contains "football manager 27". Input bundles should be the **vanilla** files; patching an already patched file stacks changes (used deliberately for the incremental v24/v25 steps, but wrong for a repeatable Build).
Verified runs: 6 tokens + 1 appended rule -> 12 token definitions rewritten across both style bundles; 3 position tokens -> 6 definitions. `tokens_not_found: []` means every requested token existed.

### 8.2 What must change to run as a library [I]
1. Replace `main()`/`argv`/`print` with `build(project, vanilla_dir, out_dir) -> BuildReport`; keep `SheetPatcher` unchanged.
2. Always read from `vanilla_dir` (read-only copy); never accept the live game dir as input. Copy files first, patch the copies, then compare hashes: unchanged bundles must not be copied to the game later.
3. Convert the project (section 5) to the spec dict in one place; reject unknown keys, validate every value with `parse_token_value`, check that each token exists in the index and warn on literal swaps with more than N hits.
4. Idempotence: output must be byte-identical for the same project and vanilla (UnityPy repack is deterministic in the runs so far, but this is [U]; test by building twice and comparing sha256).
5. Return structured results (counts, `tokens_not_found`, `literal_hits`, per-bundle sha256) instead of text; write `build-report.json` next to the bundles.
6. Progress callback and cancellation (bundle load takes seconds; the layout bundles are large).
7. Memory: `UnityPy.load` of the 1.1 MB style bundles is trivial; the layout/data bundles reach several hundred MB; process bundle by bundle.
8. Add the missing project operations: `reverts`, per-element scoped rule with automatic specificity (strictly above the rule being overridden: use repeated class selectors), tile placement edits (grid_patch), UXML inline-style edits.

---

## 9. Install and verify

### 9.1 Install routine (proven by hand, to be automated) [V on Windows]
Safety rules:
1. The vanilla backup and the build folder are the only sources; the live game dir is written **only** here.
2. Refuse while the game process runs (section 2.4). Also refuse if the target bundle set differs from the set the project was built for (game updated since).
3. Create `backups/<UTC timestamp>/` containing exact copies of every file about to be replaced, with `manifest.json` (file, size, sha256 before, sha256 of the new file) and a `RESTORE.txt`. The manual runs used folders like `game-files-backup-crimson-before-tactics-dark` with a `RESTORE.txt` that states the exact copy-back command.
4. Copy changed files only (compare sha256 of build output against the live file).
5. After copy, re-hash the live files and compare with the build; on mismatch restore from the backup immediately and report.
6. Append every action to `logs/install-log.jsonl`: time, project, file, hash before, hash after, backup path.
7. Restore command: copy every `.bundle` from the chosen backup over the same name in the game dir (game closed).
8. After a Steam update or "Verify integrity", the skin is gone: detect by comparing live hashes with the last install log and offer re-install.
Windows verified details: install path `...\fm_Data\StreamingAssets\aa\StandaloneWindows64`, the process `fm` was stopped with `Stop-Process` (the owner allowed it), relaunch via `steam://rungameid/<appid>` read from `appmanifest_*.acf`; the game was running during a build but never during a copy.
macOS: file permissions on a Steam `.app` are normally user-writable; if the app is inside `/Applications` and root-owned, copying fails; do not escalate privileges, show the error. Gatekeeper/quarantine: modifying files inside a signed `.app` can invalidate the code signature and make macOS refuse to launch the app ("is damaged") [U, experiment 11.6]. Steam installs are usually not re-validated at launch, but Epic/App Store builds may be.

### 9.2 Relaunch [I]
Steam: `open "steam://rungameid/<appid>"` on macOS; the app id is in `steamapps/appmanifest_<id>.acf` (grep `"name"		"Football Manager 27"`). Epic: launch via the Epic launcher URI [U]. Never launch automatically without a prompt.

### 9.3 Verify comparison logic [I, derived from the Colour Finder model]
1. The user (or helper) provides a screenshot of the target screen at a known resolution and UI scale (the models are stored at the measurement resolution, 2500x1406 in the Windows runs).
2. Scale the screenshot to the model resolution (aspect must match; otherwise ask for a window/resolution change).
3. For each model region with a predicted colour (token-driven or literal, state = idle), sample a 3x3 grid around the region centre, avoiding children; composite expectation = predicted RGBA over the predicted backdrop (alpha-aware, z-order as in the model).
4. Compare per channel with `tolerance_rgb` (default 6) in sRGB; also report max delta. Classify: `landed`, `not landed` (matches the old colour instead: report which entry failed), `unknown` (text/gradient/anti-aliased edges, skip).
5. Regions known to be code-driven are excluded from pass/fail and shown as informational.
6. Output a table plus an annotated overlay; failures link back to the project entry and the rule that was expected to win.
Limits: hover/pressed states cannot appear in a static screenshot unless the user holds them; textures, gradients and blur differ from the flat model.

---

## 10. PyInstaller packaging notes for macOS [I unless marked]
- Build per architecture or `universal2`. Python from python.org is universal2; Homebrew Python is single-arch. UnityPy's compiled extension (`UnityPyBoost`, built as `cp314-win_amd64.pyd` on the Windows machine [V]) and wheels for etcpak, lz4, brotli, texture2ddecoder, Pillow must all exist for the target architecture; a universal2 app needs universal2 or per-arch wheels for each [U]. Safest first target: arm64 only on Apple Silicon.
- Data files: `UnityPy/resources/lzma.tpk` must be bundled: `--collect-data UnityPy` (also `--collect-submodules UnityPy` because it imports classes dynamically). Also `--collect-data` for `archspec` if present, and hidden imports for `UnityPy.classes`, `UnityPy.enums`, `PIL._imaging`, `lz4.block`, `brotli`, `etcpak`, `texture2ddecoder`.
- The one-file mode unpacks to a temp dir each launch (slow with big deps); prefer one-dir inside an `.app` wrapper (`--windowed` has no effect for a server app; use a small launcher that starts the server and opens the browser).
- Cache and workspace must live outside the bundle (`~/Library/Application Support/FM27SkinEditor/`), never under `sys._MEIPASS`.
- Do not rely on `__file__`-relative reads for `frontend/` and `data/`: use `sys._MEIPASS` when frozen, and pass it through `--add-data "frontend:frontend" --add-data "data:data"`.
- Codesigning/notarisation: ad-hoc sign for local use (`codesign --force --deep -s - FM27SkinEditor.app`); distribution needs a Developer ID certificate and `notarytool`. Unsigned apps need right-click > Open. Hardened runtime may require entitlement `com.apple.security.cs.allow-unsigned-executable-memory` for Python extensions [U].
- No Electron. The app opens the default browser at `http://127.0.0.1:8765/`; bind to localhost, random per-session token in the URL to keep other local users out.
- Freezing pitfalls seen elsewhere [I]: `python -I` semantics differ when frozen; multiprocessing needs `multiprocessing.freeze_support()`; the process pool for indexing must use `spawn`.
- Environment pitfall verified in this project [V]: a script launched with `python -I` cannot see packages installed with `--user`. Inside a venv it can.

---

## 11. Open questions and unverified assumptions (with the experiment that closes each)
| # | Question | Experiment |
|---|---|---|
| 1 | Real macOS install path, `.app` internals, platform folder name (`StandaloneOSX`?), executable name for the process check. | On the Mac: `ls "<app>/Contents"`, `find "<app>" -name catalog.bin`, `defaults read "<app>/Contents/Info" CFBundleExecutable`, `ls aa/`. Record in section 2. |
| 2 | Are the macOS UI bundles structurally identical to the Windows ones (same sheet names, tokens, GUIDs)? | Run `index_styles` and `index_layout` on the macOS bundles; diff the token table and the GUID map against the Windows index (counts: 1,750 `FigmaStyleVariables` properties; 7,467 layouts). |
| 3 | Does UnityPy 1.25.4 read and re-save macOS bundles (LZ4HC/LZMA, Unity 6000.3) byte-compatibly? | Load, `save_typetree` unchanged, `env.save(pack="original")`, hash compare with the input, then load the result in UnityPy again. In-game test with an unchanged re-save first. (On Windows, unchanged re-save equality was not tested; only patched saves ran in game.) |
| 4 | Do vanilla colour table entries share indices across properties (editing one entry changes several)? | Count unique vs total `valueIndex` for `VT_COLOR` in vanilla `AlwaysAppliedStyleSheet` (the brief says 1899/0 shared for the skinned build; the Colour Finder README implies sharing is possible). |
| 5 | Is the build deterministic (same project + vanilla = identical bytes)? | Build twice, compare sha256 of every output. |
| 6 | Does modifying files inside the signed `.app` break launch (Gatekeeper/Steam validation) on macOS? | Copy a trivially re-saved bundle into a test install, launch; try with Steam and with Epic. Also test `xattr -dr com.apple.quarantine`. |
| 7 | Can bundles in `aa/` be overridden without touching the originals (a mod folder, catalog redirect) so the app never writes inside the install? | Inspect `settings.json` / `catalog.bin` for a local override path; test whether a second catalog or `StreamingAssets` file with the same name takes precedence. |
| 8 | Stability of path ids and GUIDs across game patches (needed for "project survives patch"). | Index two builds, compare GUID -> name and path id -> name tables. Use name + GUID as the primary key and path id only as a hint until proven. |
| 9 | Is an appended rule's order/specificity honoured identically across sheets for every selector shape? | Two more scoped rules on other elements; screenshot verify. The doubled-class trick worked once (pitch panel). |
| 10 | Can inline UXML styles (layout `inlineStyle` sheet, `m_RuleIndex`) be edited safely for code-looking colours? | Edit one inline colour in a copy of a small layout bundle; check in game. `uxml_edit.py`/`uxml_hide.py` exist but their live use is not recorded here. |
| 11 | Tile placement writes (`ui-tileslayouts_assets_all`): does the game accept changed `m_location` / sizes without breaking the grid, and does the layout engine clamp to `m_minSize`/`m_maxSize`? | Change one cell in a copy, install, inspect in game on Squad. Reorder/reparent in layouts is higher risk (names/positions used by code). |
| 12 | Which screens are built entirely by code (Canvas, CardContainer, scrollbar parts, shirt images)? | Use the live match report (`docs/phase3-notes.md`): names not defined by any layout; treat as not skinnable by layout edits. |
| 13 | Can the inspector (BepInEx 6 IL2CPP plugin) run on macOS? | Try BepInEx on the Mac build; otherwise ship measured models and add a screenshot-based verifier. |
| 14 | Epic Games install path and update behaviour on macOS. | Install via Epic; locate with `find`; check whether Epic "verify" restores files. |
| 15 | `fm27_bundle_diff.py`: where is it and what does it do beyond UnityPy? | Locate on the original machine; if absent, rely on UnityPy and drop the dependency. |
| 16 | Preview accuracy target: how close must the model be to pass Verify? | Measure the delta between model and a real screenshot on Tactics (already visually accepted) and set `tolerance_rgb` from the data. |

## 12. Gotchas collected during the work [V]
- JSON spec files and Node-read JSON: write UTF-8 **without** BOM (PowerShell `Set-Content -Encoding utf8` adds one in Windows PowerShell 5.1).
- A literal swap hits every matching literal: `#DA0037` was both the crimson accent and the hard-coded pitch panel colour.
- Tokens that alias another token (`--colours-tactics-defender-background` -> `var(--colours-base-cyan-deep)`) should be reverted at the alias level; reverting the base token also changes unrelated uses.
- A token can be defined in several sheets: patch all definitions (the patcher does) or the visible value will depend on load order.
- Mixed state danger: patching already patched bundles stacks changes; Build must start from vanilla.
- Do not run a build with the output inside the install folder (the patcher refuses names containing the game folder name).
- Steam may restore files at any time; keep `install-log.jsonl` to detect it.
- Game restarts: on 2026-11-11 the process id changed with no crash evidence (orderly leave-lobby sequence at the end of the old `Player.log`; no crash dump folder, no WER entry for the game). `Cannot initialize Crashpad client` is logged at start, so absence of dumps proves nothing.
- Windows Event Viewer is a quick way to tell a game crash from your own tool crash (`python.exe` APPCRASH 0xc0000005 appeared once from a deep-recursion script).


## Windows findings, 2026-11-12 (placement-write spike)

- Game build seen in game: 27.0.1.2503222 (it was 27.0.1.2494769 earlier in the work). `catalog.hash` (`dfa1892e861eef5fd9c26d5c909a552f` on this install) did not change across the spike; it is a better staleness key than the version string, which the Windows install detection cannot read (the version comes from `Info.plist` on macOS only).
- Composition data: `m_gridComponents` cells carry `m_location` {x, y, width, height}, so size lives inside the location. In the game data 4,724 of 5,162 config-bearing cells have a size equal to one of their config sizes, so size is largely derived from config. Placement edits therefore allow position (x, y) only; size changes are blocked until a config trial shows otherwise.
- A UnityPy re-save (`packer="original"`) is NOT byte-identical (the tactics bundle went from 41,157 to 41,370 bytes) but every object's typetree is identical after reload.
- A no-op re-saved `ui-tactics_assets_all.bundle` installed on Windows loaded with no hash complaint and the Tactics screens drew normally. This does not prove that the game reads composition geometry from that bundle; the position-swap trial (build in `FM27_LayoutMCP\spike`) has no in-game verdict yet.
- The live bundle in the game folder can hold a modified build while the app's live-file check only covers the two style bundles; roll back and hash-check before producing a layout dump.
- Still open: the macOS code-signature question.

- Build gate on real bundles (Windows, 2026-11-12): a patched ui-styles_assets_default.bundle passed the untouched-object check (every other object typetree-identical to vanilla, pools append-only, no raw-bytes fallback needed). Only MonoBehaviour sheets were exercised; non-MonoBehaviour raw-byte comparison has not been tested on a real bundle that contains them.
- Layout dump staleness now uses file hashes (fmlayout-index/2 meta.source vs the manifest's reference hashes); catalog.hash alone does not change when a single bundle is modified.

- Correction (measured on Windows, 2026-11-12): the 67 ui-*.bundle files total about 189 MB, not the 1.4 GB stated above; the whole aa platform folder is about 4.0 GB in 534 bundles. A reference hash was checked against `certutil -hashfile ... SHA256` and matches.
