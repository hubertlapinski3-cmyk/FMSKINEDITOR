# FM Skin Builder: analysis of the current editor and specification of its successor

Written 2026-11-13 against the editor at `C:\Users\Admin\Downloads\fm27-skin-editor` (about 5,900 lines of Python engine, an 866-line single-file frontend, 141 tests) and FM27 build 27.0.1.2503222 on Windows.

Marking used below: **[V]** verified on this machine in this project, **[A]** assumption or general Unity knowledge not yet verified against FM, **[U]** unknown.

---

## Part 1. Analysis of the current tool

### 1.1 What it does well

| Area | State | Evidence |
|---|---|---|
| StyleSheet decoding and patching | Token rewrite in `:root`, literal swaps (exact RGBA, RGB keep alpha), appended rules with automatic specificity raise, class renames, quarantine of out-of-range colours | `token_patch.py`, `uss.py`, `specificity.py`, `colour.py`; real builds pass the gate [V] |
| Safety line | Read-only vanilla snapshot, builds always from vanilla, backup before install, re-hash, rollback, process check, tamper check over 67 UI bundles, folder-mismatch guard | `install.py`, `verify_static.py` [V]. The guard exists because a real incident (wrong folder detected) happened. |
| Build gate | Object counts, deserialisation, appended rules decode to spec, every untouched object identical to vanilla (typetree digest, NaN-safe), pools append-only | `verify_static.untouched_check` [V on real bundles] |
| Two output routes | Bundle patching, and native skin folder export that FM27 loads itself | `patcher.py`, `native.py`; native export seen working in game [V] |
| Image pipeline | Texture2D re-encode, atlas icon paste at 4 scales, SVG to VectorImage mesh, exact export at true size, VectorImage rounded-edge decode | `images.py`; texture and atlas icon swaps seen in game [V]; SVG-into-VectorImage built but not seen in game |
| Knowledge of the game | Icon class map from the FMImages sheets, wallpaper code binding, club-colour mechanics, `nav-on-light` | `images.icon_classes`, `club_colours.py` [V] |
| Preview | Measured screens repainted with project colours; region to rule to token; live token edit; Verify against a screenshot | `preview.py`, 8 models [V in browser] |
| Compare | Loads other USS skins or bundles, shows token and image differences, previews, imports colours | `skins.py` [V for USS; bundle path tested with stand-ins only] |
| Layout awareness | Contract `fmlayout-index/2`, join "where it paints", stored placement edits | `layout_*.py`, `placement.py`; **only against a synthetic fixture**, no real dump yet |
| Test culture | 141 tests, several on real game files, frontend scan tests for read-only guarantees | `tests/` |

### 1.2 What is missing or limited

1. **No real USS authoring.** The user cannot write USS. A project is five lists (token overrides, literal swaps, scoped rules, renames, image swaps). There is no way to delete or edit an existing vanilla rule, no `@import`, no free-form sheet, no comments, no ordering control beyond "appended last".
2. **No mapping system.** Rules are appended to a named sheet by a field on the rule. There is no concept "this source file targets these sheets in these bundles", no wildcard targets, no per-sheet overrides.
3. **UXML is read-only.** Visual trees are only walked for selector reach. No UXML edit, no inline-style edit, no template override.
4. **Fonts not supported** on the bundle route (native route can use `url()` fonts, but the exporter does not emit them).
5. **Table views and tile layouts** are not editable. Placement edits are stored only; the write spike proved a no-op re-save loads, but the position-swap verdict was never taken.
6. **Layout data is hypothetical.** The dump exporter does not exist; everything layout-related ran on a synthetic fixture.
7. **Preview is static.** Eight measured screenshots of one save, one club, one resolution, idle state. It cannot show images, fonts, outlines, hover states, or screens that were not measured.
8. **No undo, no history.** Every save overwrites `<project>.skin.json`.
9. **macOS never run.** The app was written for macOS, and every test and in-game check ran on Windows. Code-signature behaviour of a modified `.app` is unknown [U].
10. **Game load diagnostics not read.** `UssDecodeReport` exists in `SI.Lattice` [V from type names], but where it surfaces is unknown [U].
11. **Packaging.** Runs from source in a venv; pip cache and Python version problems already hit the owner twice.

### 1.3 Technical strengths

- **Correct separation of unsafe operations.** Only `install.py` writes the game folder. Everything else is pure functions over a snapshot.
- **Typetree-level patching** through UnityPy instead of byte patching: survives layout shifts inside a sheet.
- **Gate that proves non-interference**, not just "it deserialises".
- **Engine is UI-agnostic.** Every feature is a Python function with a thin HTTP route; a new UI can reuse it unchanged.
- **Facts are recorded** (LEARNINGS.md, docs/, memory notes) with what was seen in game versus inferred.

### 1.4 Technical weaknesses

| Weakness | Consequence |
|---|---|
| `frontend/index.html` is one 866-line file of template strings, global state (`S`, `P`, `PV`, `IM`, `CM`) and full re-renders | No components, no tests of UI logic, focus loss on re-render, cannot scale to editors |
| `server.py` is a 576-line class with 40+ routes on stdlib `http.server` | No schema validation of requests, errors as strings, one global job slot, state such as `self.compare` held in memory |
| Project model is colour-centric JSON | Cannot represent a USS file, a UXML patch, a font, a mapping |
| Index picks one "reference sheet" for token values | Tokens defined differently across sheets are flattened; conflicts only flagged |
| Rule identity is `(sheet, selector text, property)` | Fragile against game updates that reorder or rename; no stable ids |
| Preview models are hand-captured through a Windows-only inspector | Cannot be regenerated by users; stale after patches |
| Bundles are loaded repeatedly (catalog, thumbs, gate, digests each reload the file) | Fine at 189 MB of UI bundles; will hurt with fonts/backgrounds/3D |
| Crunch textures are rewritten as plain DXT | Bundle size grows; untested at scale |
| Windows path and process handling was retrofitted | The folder-detection bug shows platform code needs its own layer and tests |

### 1.5 UX gaps

- Ten flat top tabs; no explorer, no notion of "files in my skin".
- No dirty state, no undo/redo, no find/replace, no multi-select.
- Colour is edited one token at a time; no palette/ramp view, no "apply to family".
- Errors appear as a toast that disappears; no problems panel.
- The two output routes are explained in prose rather than shown as a build target with capabilities.
- Images tab mixes browsing, swapping and exporting in one panel.
- No onboarding: a new user must know to snapshot, index, then create a project.

### 1.6 Distance from a production-grade builder

Rough coverage of the target in this document:

| Capability | Now | Gap |
|---|---|---|
| StyleSheet read/patch | 70% | full encoder for every value type, rule removal/replacement, imports, new sheets |
| USS authoring | 5% | parser, editor, diagnostics |
| Mapping | 10% | whole subsystem |
| Textures / icons / SVG | 75% | sprite metadata edits, new atlas entries, Crunch policy, fonts |
| Fonts | 0% (bundle), 10% (native) | SDF font asset generation or `url()` route |
| UXML | 5% (read) | editor and writer |
| Tile layout / table views | 15% (model, stored edits) | real data, writer, in-game proof |
| Build / install safety | 85% | packages, signing of what was built, multi-platform |
| Preview | 40% | generated, not captured; live reload loop |
| UI shell | 15% | full rewrite |
| Cross-platform | Windows only in practice | macOS, Linux/Proton, store variants |

The engine is roughly half of a production tool; the application shell and the authoring experience are close to zero. The correct move is **keep the engine, replace the shell, and generalise the project model**.

---

## Part 2. Specification of the new application ("FM Skin Studio")

### 2.1 Design principles

1. **Two targets, one project.** *Native skin* (USS + assets in the user folder, loaded by FM itself) is the default and the only target that survives updates. *Bundle patch* is the escalation for what USS cannot reach (textures inside bundles, atlas sprites, VectorImages, UXML, tile layouts, table views). Every project item declares which targets can carry it; the build tells the user what was dropped and why.
2. **Source of truth is text.** A skin is a folder of `.uss`, `.uxml` patches, images, fonts and small JSON files. Visual editors read and write that text. Diff, undo and version control all fall out of this.
3. **Nothing touches the game without a snapshot, a gate and a backup.** Unchanged from today.
4. **Discover, do not hard-code.** Sheets, tokens, classes, icons, panels are discovered from the installed build and stored in a *version profile*. Hard-coded knowledge (club-colour rules, wallpaper places) lives in data packs with the build they were proven on.
5. **Everything observed in game is recorded as evidence** with build and date; everything else is labelled unverified in the UI.

### 2.2 High-level architecture

```
┌────────────────────────────── Desktop shell (Tauri 2) ──────────────────────────────┐
│  UI (TypeScript, React)                                                             │
│  Activity bar │ Explorer │ Editors (Monaco, tree, grids, canvas) │ Panels │ Status  │
│        ▲ typed RPC (JSON-RPC over localhost WebSocket, token-authenticated)         │
└────────┼────────────────────────────────────────────────────────────────────────────┘
         ▼
┌──────────────────────────── Engine (Python 3.12, sidecar) ──────────────────────────┐
│  api/         RPC surface, request schemas, job queue, event stream                 │
│  workspace/   projects, recent list, settings, history (per-file snapshots)         │
│  game/        install detection, platform layer, process check, version profile     │
│  bundles/     UnityFS read/patch/repack (UnityPy), object digests, catalog facts    │
│  stylesheet/  StyleSheet model: decode ⇄ USS text ⇄ encode, pools, specificity      │
│  uss/         USS parser (lossless CST), linter, auto-fix, variable resolver        │
│  mapping/     source → target resolution, conflict report                           │
│  assets/      textures, atlas sprites, VectorImage, fonts                           │
│  uxml/        VisualTreeAsset decode ⇄ UXML text ⇄ patch                            │
│  layout/      tile compositions, table views, panel registry (index + writers)      │
│  build/       plan → targets (native, bundles) → gate → packages/                   │
│  install/     backup, copy, verify, rollback, tamper check   (only writer to game)  │
│  preview/     screen models, repaint, live-reload bridge                            │
│  knowledge/   data packs: club colours, wallpaper places, icon classes, per build   │
└──────────────────────────────────────────────────────────────────────────────────────┘
         │ read-only                       │ write (install/ only)
         ▼                                 ▼
   vanilla snapshot                  game folder  /  user skins folder
```

The engine stays a library with no UI imports; the CLI (`fmskin build`, `install`, `export`, `doctor`) is a second client of the same API, which keeps CI and headless use possible.

### 2.3 Unity StyleSheet serialization (the core)

A UI Toolkit StyleSheet is a MonoBehaviour. Fields as observed in FM27 (Unity 6000.3) [V unless marked]:

```
m_Rules[]                 { m_Properties[], line, customPropertiesCount? }
  m_Properties[]          { m_Name | (m_Id, m_CustomName), m_Line, m_Values[] }
    m_Values[]            { m_ValueType, valueIndex }          ← "value handle"
m_ComplexSelectors[]      { m_Selectors[], m_Specificity, ruleIndex }
  m_Selectors[]           { m_Parts[], m_PreviousRelationship }
    m_Parts[]             { m_Value, m_Type }
floats[]  dimensions[{unit,value}]  colors[{r,g,b,a}]  strings[]  assets[PPtr]
imports[]  scalableImages[]  m_FlattenedImportedStyleSheets[]  m_ContentHash
```

**Value type codes** (the handle's `m_ValueType`), with the pool each indexes:

| Code | Meaning | Pool | Seen in FM27 |
|---|---|---|---|
| 1 | Keyword (`auto`, `none`, `initial` ...) | value is the keyword enum itself | [A] |
| 2 | Float | `floats` | [V] |
| 3 | Dimension (px, %, deg, s ...) | `dimensions` | [V] |
| 4 | Color | `colors` | [V] |
| 5 | ResourcePath | `strings` | [A] |
| 6 | AssetReference | `assets` (PPtr, may point to another bundle) | [V] icons, images |
| 7 | Enum (identifier such as `center`) | `strings` | [V] |
| 8 | Variable name (`--x`) | `strings` | [V] |
| 9 | String | `strings` | [A] |
| 10 | Function (`var`, `rgba` ...) followed by arg count and args | `strings` for the name | [V] `var()` = 10, 2, 8 |
| 11 | Comma separator | none | [A] |
| 12 | ScalableImage | `scalableImages` | [V] 50 uses |
| 13 | MissingAssetReference | `strings` | [A] |

**Selector part types:** 1 wildcard, 2 type, 3 class, 4 pseudo-class, 5 recursive pseudo, 6 id (name), 7 predicate. **Relationships:** 0 none (start), 1 child (`>`), 2 descendant [V for 2, 3, 4, 6 and all three relationships].

Rules the encoder must obey (each one is a bug we already hit or avoided):

1. **Pools are append-only.** Never rewrite an existing pool entry: other handles share it. New values append; the gate checks the first N entries equal vanilla [V].
2. **A `var()` is three handles** (function, arg count as float, variable name). Shorthands with several values are a flat handle list.
3. **Colours are floats 0..1.** 16 vanilla entries are out of range (bytes stored as floats, e.g. alpha 124.0); they are quarantined and never rewritten [V].
4. **Specificity is stored**, not computed by the game at load: `m_Specificity` must match the selector (id 100, class/pseudo 10, type 1) [V: the gate checks it].
5. **`ruleIndex` and array order are the cascade order** for equal specificity; appended rules win ties. Sheet order across sheets is the panel's sheet list (e.g. `AlwaysAppliedStyleSheet` ... `FMImages_2x`, `Bundesliga`) [V from the inspector].
6. **Property identity.** In this Unity version a property carries `m_Id` (e.g. 458753 = background-image) plus `m_CustomName` for custom properties (`m_Id` -1). The id table must be discovered per build (collect every `(m_Id, name)` pair from vanilla; the current `PROP_TABLE` is that list) [V].
7. **`m_ContentHash`** is left as is; the game did not object to changed sheets with the old hash [V]. Record as a risk for future Unity versions.
8. **Asset references** are PPtrs into the bundle's external list; adding a new texture reference means adding an object to a bundle and possibly a new external. MVP: only reuse existing asset slots or replace the asset's content; new references are an advanced feature.

**Model:** `stylesheet/model.py` decodes a sheet into an immutable `Sheet(rules: [Rule(selectors, declarations, origin)])` where each declaration keeps its handle list and each value is typed (`Color`, `Dim`, `Var`, `Enum`, `Asset(ref)`, `Raw(handles)` for anything not understood). `Raw` round-trips untouched, so unknown value types never block a build. `to_uss()` prints text; `encode()` writes handles back with append-only pools.

### 2.4 Bundles and Addressables

Facts [V]: bundles are UnityFS; UI data is in 67 `ui-*.bundle` files (189 MB); style bundles `ui-styles_assets_{common,default,1x..4x,match}`; layouts in `ui-visualtreeassets_*`; tile data in `ui-tileslayouts_assets_all` and `ui-tactics_assets_all`; icons in `ui-icons_assets_{1x..4x,common}` plus atlases in `ui-iconspriteatlases_assets_{1x..4x}`; wallpapers in `ui-backgrounds_assets_*`. `catalog.bin` + `catalog.hash` + `settings.json` sit in `StreamingAssets/aa`. A modified bundle with a different size and hash loads without a catalog change; the catalog hash does not change when a bundle is modified.

Pipeline:

1. **Read** with UnityPy; never hold more than one large bundle; cache per-bundle indexes keyed by `(name, size, mtime, sha256)`.
2. **Patch** through typetrees (`read_typetree` / `save_typetree`) for MonoBehaviours, `Texture2D.image = ...; save()` for textures.
3. **Repack** with the original compression (`packer="original"`). Re-save is not byte-identical but is typetree-identical [V].
4. **Constraints:** Crunch textures cannot be written (re-encode as DXT1/DXT5, flag size growth); streamed texture data (`.resS`) moves inline on save, which the game accepts [V]; never add or remove objects in the MVP (object set must equal vanilla).
5. **Catalog:** treated as read-only evidence (hash for staleness). If a future build enforces CRC, the fallback is a native-only build; do not plan to rewrite `catalog.bin`.

### 2.5 Mapping system

Purpose: decide which user source lands in which sheet of which bundle (bundle target) or in which exported sheet (native target).

`mapping.json` (also editable visually):

```jsonc
{
  "schema": 1,
  "defaults": { "sheet": "AlwaysAppliedStyleSheet", "position": "append" },
  "entries": [
    { "source": "styles/colours.uss",   "target": { "sheet": "FigmaStyleVariables" }, "mode": "tokens" },
    { "source": "styles/tactics/*.uss", "target": { "sheet": "AlwaysAppliedStyleSheet" } },
    { "source": "styles/match.uss",     "target": { "bundle": "ui-styles_assets_match.bundle", "sheet": "*" } },
    { "source": "images/icons/win.png", "target": { "icon": "win_small" }, "native": { "class": "game-concepts-win_small" } },
    { "source": "images/wall.jpg",      "target": { "texture": "fm27_skin_blended" }, "native": { "places": ["report-pages"] } },
    { "source": "uxml/TitleBar.patch.uxml", "target": { "layout": "TitleBar", "guid": "…" } }
  ]
}
```

Resolution rules:

- **`mode: tokens`**: `:root { --x: v }` declarations rewrite the token's definition in **every** sheet that defines it (today's behaviour), because the game resolves a token from whichever sheet wins.
- **`mode: rules`** (default): each rule is matched against the target sheet. Same selector and property: replace in place when specificity and position allow it, else append and raise specificity (today's `specificity.py`). A rule marked `/* @remove */` deletes the vanilla declaration (bundle target only; native target emits `initial`).
- **Auto-mapping:** with no entry, the resolver finds the sheet(s) that already contain the rule's subject classes and proposes a target; ambiguity is a warning with a quick-fix.
- **Conflict report:** two sources writing the same `(sheet, selector, property)`; a rule whose subject class exists in no sheet and no layout; a native-only construct in a bundle-only mapping.
- **Stable addressing:** targets are by sheet *name* and bundle *name*, never path id; assets by *name* with path id as a cached hint, re-resolved per build (path ids changed meaning between scales and may change across game builds).

### 2.6 Assets

| Kind | Bundle target | Native target |
|---|---|---|
| Texture (wallpaper, image) | replace `Texture2D` content, same size and format [V] | hide the code-set image and paint `background-image: url()` on a container (places data pack) [V] |
| Atlas icon | paste into the atlas at 1x–4x [V] | rule on the icon's class from FMImages [V mapping, native rule not yet seen in game] |
| VectorImage (SVG) | SVG to triangle mesh (fills only) [built] | rasterised PNG on its class |
| Font | **[U]** needs TextCore `FontAsset` (SDF atlas + glyph table) generation; phase 4 | `url("x.ttf")` in a token or rule, as Jonukas and Dugout do [V they ship TTFs] |
| New asset (not replacing) | advanced: add object + external; not in MVP | trivial: copy file, reference by `url()` |

Asset replacement tool: browse catalog with thumbnails and class names, export originals at true size, drop a replacement, choose fit, see both targets' outcome side by side.

### 2.7 UXML (limited editing)

A `VisualTreeAsset` stores its tree as managed references [V]: `m_VisualTree → VisualElementAsset { m_FullTypeName, m_Id, m_Children, m_Classes, m_RuleIndex, m_StylesheetPaths }`, `TemplateAsset { m_TemplateAlias }`, per-element `UxmlSerializedData` (name, attributes), `m_Usings[{alias, guid}]`.

Scope, in order of risk:

1. **Read** (phase 2): tree + inspector, includes resolved one level at a time, "where is this class used".
2. **Class edits** (phase 4): add/remove classes on an element, since `m_Classes` is a plain string list. This is the highest-value, lowest-risk edit: it lets USS reach elements that have no usable selector.
3. **Inline style edits**: `m_RuleIndex` points into the layout's own inline StyleSheet; edit through the StyleSheet encoder.
4. **Attribute edits** on serialized data (text, name): typed per element class; allow only attributes seen in vanilla.
5. **No structural edits** (add/remove/reparent elements) until a spike proves the game tolerates changed reference ids; bindings and template overrides reference elements by id.

UXML patches are stored as a small patch file per layout (`set-classes`, `set-inline`, `set-attr` operations addressed by element id plus a name/type guard), not as a full UXML copy, so they survive unrelated vanilla changes.

### 2.8 Tile layouts and table views

- **Tile layout editor:** composition grid canvas (cells with x, y, w, h, min/max, flags, configs) per panel and breakpoint. Data source is the real index (reuse `FM27_LayoutMCP` tables through the dump contract). Writes are **gated on the spike**: position-only first; size stays blocked while size is derived from config (4,724 of 5,162 cells) [V].
- **Table views:** `ui-tableviews` (column sets) and `ui-tablefactories` (row cell layouts) are known to exist [V] but not decoded. Phase 5: read-only browser first, then column visibility/order/width edits. The game also stores user views under `Documents/.../views`, which may be the safer place to write [U].

### 2.9 Version profiles and game updates

`profiles/<game_build>-<catalog_hash>.json`, generated by "Scan game":

```jsonc
{ "game_build": "27.0.1.2503222", "catalog_hash": "dfa1…", "platform_folder": "StandaloneWindows64", "unity": "6000.3.18f1",
  "bundles": { "ui-styles_assets_default.bundle": { "sha256": "…", "sheets": ["AlwaysAppliedStyleSheet", …] } },
  "property_ids": { "458753": "background-image", … },
  "tokens": 2059, "sheets": 49, "icon_classes": 1290, "layouts": 7467,
  "knowledge": { "club_colours": "proven 27.0.1.2494769", "wallpaper_places": "proven 27.0.1.2503222" } }
```

On start the app compares the live `catalog.hash` and bundle hashes with the active profile:

- **same**: continue;
- **catalog changed**: guided flow (restore check → new snapshot → scan → *diff*): tokens added/removed/changed, rules whose selector vanished, icons renamed, layouts changed. Each project item gets a state: `ok`, `target moved` (auto-fixable), `target gone`, `vanilla value changed` (review).
- **bundle changed, catalog same**: tamper (another tool or a leftover); block bundle installs, offer restore.

Native-target projects keep working across updates by nature; the diff still runs so the user sees what drifted.

### 2.10 Backup and restore

Keep the current design and extend it:

- Snapshot is per *profile*; old snapshots are kept until the user deletes them (needed to diff across builds).
- Every install writes a backup set with manifest and a `RESTORE` script; restore refuses a set taken from another folder [V].
- `fmskin doctor`: one command that reports snapshot validity, tamper state, installed package, native skins present, and the exact command to return to stock.
- Uninstall = restore vanilla for every bundle the package touched, verified by hash.

---

## Part 3. Project system

### 3.1 Structure on disk

```
MySkin/
  skin.project.json        name, id, schema, game profile it was authored on, default target, mode (simple|expert)
  mapping.json
  styles/                  *.uss (user-authored; generated files are marked and regenerated)
    tokens.uss             :root overrides (the Simple-mode palette writes here)
    generated/             literal-swap rules, club-colour pack (read-only in the editor)
  uxml/                    *.patch.json per layout
  layout/                  tiles.json, tables.json (edits with the vanilla values they replace)
  images/  icons/  fonts/
  config/                  options.json (club colours, contrast backdrop, flags), knowledge overrides
  packages/                build outputs (ignored by history)
  .history/                per-file snapshots (content-addressed), build reports
```

`skin.project.json` holds no styling; it points at files. Migration from today's `*.skin.json`: token overrides → `styles/tokens.uss`; scoped rules → `styles/rules.uss` + mapping entries; literal swaps and options → `config/options.json` (generated rules); image swaps → `images/` + mapping entries.

### 3.2 Lifecycle

- **New project:** blank, from template (Dark neutral, Light, "Vanilla with club colours removed"), or *from another skin* (the current Compare import, extended to import its USS as files).
- **Recent projects**, open folder, duplicate, export as zip (sources) or as a shareable package.
- **Simple mode:** palette (token families as ramps), club-colour switch, wallpaper and icon pickers, preview, one "Apply" button. Writes the same files Expert mode edits.
- **Expert mode:** explorer, editors, mapping, build panel, problems. A toggle in the status bar; no feature is Simple-only.

---

## Part 4. Editors

| Editor | Simple | Expert |
|---|---|---|
| **USS** | not shown | Monaco with a USS language service: tokenizer + CST from `uss/parser`, completion for properties (from the profile's property table), classes (from sheets and layouts), tokens (with swatch and resolved value), inline colour picker, hover = "defined in sheet X, used by N rules, paints screens …", go-to-definition into a read-only view of the vanilla sheet, diagnostics (unknown property, unsupported unit, `var()` to a missing token, selector that matches nothing), **auto-fix** (wrong unit, missing `;`, `rgba()` normalisation, specificity too low → rewrite selector) |
| **Variables** | palette ramps, family shift (hue/lightness), contrast check live | table of 2,059 tokens: vanilla value, override, alias chain, reach, conflicts across sheets; multi-edit |
| **Mapping** | hidden (auto) | visual: sources on the left, sheets/bundles on the right, lines with status colours; JSON view of the same file |
| **UXML** | not shown | tree (includes expandable), inspector (type, name, classes, attributes, inline styles, bindings read-only), "add class" action, patch list |
| **Config** | switches | form + JSON |
| **Tile layout** | not shown | grid canvas per panel/breakpoint, drag to move, numeric fields, validation list |
| **Table views** | not shown | column list, order, visibility, width |
| **Assets** | picker with thumbnails | catalog, replace, export, mapping, fit, per-target outcome |

All editors share: multi-tab, split view, undo/redo per document, find/replace across the project, dirty markers, and a **Problems** panel fed by the engine's linter and the mapping resolver.

---

## Part 5. Build and apply

1. **Plan.** The engine resolves mapping and produces a *build plan*: per target, the list of operations (`rewrite token --x in sheet S`, `append rule`, `replace texture T`, `write images/x.png`) and the list of dropped items with reasons. The plan is shown before anything is written.
2. **Preview mode.** (a) Static: repaint measured screens (today's preview) from the plan's resolved colours. (b) Live: build the native target into `skins/<id>-preview/`, trigger FM's skin reload, take a screenshot through the inspector bridge when available. Live preview never touches bundles.
3. **Build.** Outputs to `packages/<id>-<n>/`:
   - `native/` (skin folder), `bundles/` (patched bundles + `build-report.json`), `package.json` (profile, hashes, plan, gate result, dropped items).
4. **Gate.** Blocks install: object set equal, untouched objects identical, pools append-only, appended rules decode to the plan, textures same size/format class, native sheets parse and every `url()` resolves inside the folder.
5. **Install.** One click, target-aware: native → copy folder to the user skins folder; bundles → process check, tamper check, backup, copy changed, verify, rollback on mismatch.
6. **Change summary.** Human-readable: "53 tokens, 114 rules, 2 icons, 1 wallpaper; skipped: …", plus a machine log (`logs/build-*.jsonl`).
7. **Path detection.** Platform layer with one module per store:

| Store / OS | Install root | User folder | Status |
|---|---|---|---|
| Steam, Windows | `steamapps/common/Football Manager 27` (+ `libraryfolders.vdf`) | `Documents/Sports Interactive/Football Manager 27` (OneDrive redirect possible) | [V] |
| Steam, macOS | `.app/Contents/Resources/Data/StreamingAssets/aa/StandaloneOSX` | `~/Library/Application Support/Sports Interactive/Football Manager 27` | [A] paths from docs; never run |
| Epic, Windows | `Epic Games/…` (manifests in `ProgramData/Epic/EpicGamesLauncher/Data/Manifests`) | same Documents path | [A] |
| Game Pass / MS Store | `XboxGames/<title>/Content`; files may be read-only or ACL-protected | same Documents path | [U] bundle route may be impossible; native route should work |
| Linux (Proton) | Steam library, Windows build under `steamapps/common` | inside the Proton prefix `compatdata/<id>/pfx/drive_c/users/steamuser/Documents/…` | [A] |

Detection rule learned the hard way: pick the data folder that belongs to the game executable (`<Name>_Data` next to `<Name>.exe`, or `.app/Contents/Resources/Data`), never the first match of a recursive search; list other copies and ignore them [V].

---

## Part 6. UX and interface

```
┌─┬───────────────┬──────────────────────────────────────────┬──────────────────────┐
│A│ EXPLORER      │  tokens.uss × │ tactics.uss │ Mapping    │  PREVIEW / INSPECTOR │
│c│  styles/      │                                          │  screen ▾  target ▾  │
│t│  images/      │   (editor area, split-capable)           │  [measured screen]   │
│i│  uxml/        │                                          │  region → rule → tok │
│v│  layout/      │                                          │                      │
│i│ GAME          ├──────────────────────────────────────────┴──────────────────────┤
│t│  sheets (49)  │ PROBLEMS │ BUILD │ OUTPUT │ CHANGES                             │
│y│  tokens       │  plan, gate, dropped items, install log                         │
├─┴───────────────┴─────────────────────────────────────────────────────────────────┤
│ FM27 27.0.1.2503222 ✓ stock │ target: Native ▾ │ Simple/Expert │ game: not running│
└───────────────────────────────────────────────────────────────────────────────────┘
```

- **Activity bar:** Explorer, Search, Game (vanilla browser: sheets, tokens, layouts, icons), Assets, Layout, Compare, Build, Settings.
- **Status bar:** game build and tamper state, active target, mode, running state, last build result. Clicking any item opens the relevant panel.
- **Mapping feedback:** every file in the explorer shows a badge (mapped / unmapped / conflict / dropped on current target); every rule in the USS editor has a gutter marker (replaces vanilla, appended, no match).
- **Changes view:** vanilla ⇄ skin diff per sheet and per token, before building.
- Undo/redo is document-level text history plus project-level operation history (asset swaps, mapping edits) backed by `.history/`.

---

## Part 7. Recommended tech stack

| Layer | Choice | Why |
|---|---|---|
| Engine | Python 3.12 + UnityPy 1.25, Pillow, etcpak, numpy, mapbox-earcut, svgelements | 5,900 lines of working, tested engine; UnityPy handles Unity 6 typetrees [V] |
| Engine API | JSON-RPC over a localhost WebSocket (stdlib-compatible; `websockets` or a small ASGI app), pydantic-style request schemas, a job queue with progress events | replaces the single job slot and string errors |
| UI | TypeScript, React, Vite; Monaco for USS/JSON; a canvas library (Konva or plain canvas) for preview and tile grid; TanStack Table for token/asset grids | Monaco gives multi-tab editing, find/replace and language-service hooks for free |
| Shell | Tauri 2 (small, native menus, auto-update, sidecar process management) | Electron is the fallback if a needed WebView feature is missing on macOS |
| Packaging | Engine frozen with PyInstaller (one-dir) as a Tauri sidecar; signed and notarised on macOS | removes the Python/venv/pip class of failures already seen |
| Tests | pytest (engine, with real-bundle tests skipped when the game is absent), Vitest (UI logic), Playwright (shell smoke) | keeps today's test culture |
| Alternative considered | C# engine on AssetsTools.NET | one language with Unity, good bundle fidelity, but a full rewrite of a working engine; revisit only if UnityPy blocks font or UXML work |

---

## Part 8. Data models (engine)

```python
Declaration   = (property: str, value: [Value], origin: SourceRef | VanillaRef)
Rule          = (selectors: [Selector], declarations: [Declaration], comment: str | None)
Sheet         = (name, bundle, path_id_hint, rules: [Rule], pools_digest)
TokenDef      = (name, per_sheet: {sheet: Value}, chain: [str], resolved: Color | None, conflict: bool)
Target        = Sheet(name, bundle?) | Icon(name) | Texture(name) | Vector(name) | Layout(name, guid) | Composition(name, cell)
MappingEntry  = (source_glob, target, mode, native_hint)
Operation     = RewriteToken | ReplaceDecl | AppendRule | RemoveDecl | ReplaceTexture | PasteIcon | ReplaceVector
              | SetClasses | SetInline | MoveCell | NativeWriteSheet | NativeCopyAsset
BuildPlan     = (profile, target, operations: [Operation], dropped: [(item, reason)], warnings)
Package       = (id, n, profile, plan_digest, files: {name: sha256}, gate: GateResult)
Evidence      = (claim, build, date, how: "seen in game" | "gate" | "inferred", ref)
```

`Operation` is the unit that the gate verifies and the change summary prints; both targets are compilers from the same plan to different outputs.

---

## Part 9. Prioritised features

**MVP (replaces today's tool)**
1. New shell with explorer, tabs, problems, build panel, status bar.
2. Project folder format + migration from `*.skin.json`.
3. USS parser/printer and Monaco editor with token completion and diagnostics.
4. Native target build with mapping defaults, plan view, change summary, install to skins folder.
5. Token/palette editor (Simple mode) writing `tokens.uss`.
6. Asset replacement (textures by places, icons by class) on the native target.
7. Static preview from the plan.
8. Version profile scan, staleness and tamper states.

**V1**
9. Bundle target: full StyleSheet encoder (replace/remove/append), gate, packages, backup/install (port of today's engine).
10. Mapping editor (visual + JSON) and conflict report.
11. Bundle asset swaps (textures, atlas icons, VectorImages).
12. Update diff and guided migration.
13. Live preview loop (skin reload + screenshot) on Windows.

**V2**
14. UXML read + class/inline edits.
15. Fonts (native first; bundle FontAsset after a spike).
16. Tile layout editor with writes (after the spike verdicts).
17. Table view editor.
18. Compare/import other skins as files; share packages.
19. macOS and Linux certification.

---

## Part 10. Key technical challenges and answers

| Challenge | Answer |
|---|---|
| Lossless USS round-trip (comments, formatting) | CST parser; visual editors apply minimal text edits, never regenerate a user file |
| Encoding every USS value correctly | Typed values for the known set; `Raw(handles)` passthrough for the rest; encoder refuses (with a diagnostic) rather than guesses |
| Cascade correctness (will my rule win?) | Compute from stored specificity + order + sheet order per panel; show "wins / loses to X" in the editor; auto-raise specificity only on request |
| Tokens defined in several sheets | Model per-sheet definitions; rewrite all; show conflicts instead of picking a reference sheet |
| Code-set values (inline styles, `<color>` tags, gradients with `useCustomStyles=false`, wallpaper choice) | Knowledge packs with hide/cover techniques; the inspector labels a region "code" so users stop fighting it |
| Game updates | Profiles, name-based addressing, diff with per-item states, native target as the stable default |
| Bundle fidelity | Typetree patching, append-only pools, untouched-object gate, no object add/remove in MVP |
| Crunch and streamed textures | Re-encode policy with visible size cost; keep dimensions and mip policy explicit |
| Fonts | Native `url()` first; bundle route needs SDF atlas generation, treat as research |
| Preview truthfulness | Label static preview as colour-only; make live preview the real check; store evidence of what was seen in game |
| 64-bit path ids in a JS UI | Always strings across the API [V bug already hit] |
| Platform differences | One `game/platform_*.py` per OS/store with its own tests and fixtures built from real folder listings |
| Performance | Per-bundle index cache keyed by hash, lazy thumbnails rendered once per bundle, background job queue, incremental build (only sheets whose inputs changed) |

---

## Part 11. Roadmap

| Phase | Weeks (one developer) | Exit criteria |
|---|---|---|
| 0. Foundations | 2 | Engine extracted as a package with JSON-RPC, job queue, schemas; all 141 tests green; CLI parity |

**Phase 0 status (2026-11-13): done.** `skin_editor/engine.py` (no transport code), `skin_editor/api/` (schemas, 61 named methods, JSON-RPC 2.0, job queue, event bus), `POST /rpc`, `GET /events` (server-sent events instead of a WebSocket: stdlib on both sides; the method table is transport-free), CLI `rpc` and `methods`. 151 tests green (141 + 10 new); the first frontend runs unchanged on the extracted engine. Reference: `docs/API.md`.

| 1. Shell + project format | 4 | Tauri app opens/creates projects, explorer, tabs, status bar; migration of `Mine` round-trips to an identical native export |

**Phase 1 status (2026-11-13): complete.** (Also done since the text below: the real Mine was converted to a project folder and its native export is byte-identical to the one made before; tabs and the open project are remembered; project-wide find; a Simple-mode palette that edits styles/tokens.uss.) The desktop window runs: `npm run tauri dev` in `studio/` compiles the Rust shell (Rust 1.100, Windows SDK 10.0.28000), the shell finds or starts the engine and the interface shows the projects, status bar and panels (window captured and checked). Earlier text of this paragraph, kept for the record: Done: the folder project format and lossless migration (`skin_editor/projfmt.py`); six project-file API methods plus `project.create_folder`; CORS for the shell origins (token still required); the shell UI in `studio/` (Vite, React, TypeScript, Monaco bundled for offline use): project list, explorer, multi-tab editor with per-file undo, dirty markers, Ctrl+S, find/replace, `var(--token)` completion, colour swatches, a Problems panel that jumps to file and line, Output and Build panels, status bar (game build, tamper, running, target, mode) and a Simple/Expert toggle. Checked in a browser against the real engine: create a project, edit, save, see the problem. The Tauri wrapper (`studio/src-tauri`, finds or starts the engine and passes its URL and token) first failed to link because Visual Studio here had no Windows SDK; the owner installed one. Note: files written with PowerShell 5.1 `-Encoding utf8` carry a BOM that Tauri's config parser rejects. 155 tests green.


| 2. USS authoring + native target | 5 | Parser/printer fuzz-tested against all 49 vanilla sheets (decode → print → parse → equal model); Monaco service; plan view; Jonukas-wood imports and re-exports to an equivalent skin |

**Phase 2 status (2026-11-13): done for the native route.**
- **Round trip:** `skin_editor/ussprint.py` prints a decoded sheet as USS and `projfmt.parse_uss` (now quote-aware) reads it back. All 49 vanilla sheets (13,028 rules) decode, print, parse and compare equal; a 300-rule fuzz (quotes, braces and semicolons inside strings) passes too (`tests/test_uss.py`).
- **Editor service:** `skin_editor/ussdiag.py` + `uss.diagnostics`: syntax errors with lines, unknown property (with "did you mean"), unknown `var()` token, bad colour, unsupported unit, class used nowhere in the game's sheets. In Monaco these are squiggles; unknown property and token offer a quick fix. Token completion from the game's tokens. A read-only viewer of every vanilla sheet (G in the activity bar; sheets are identified by bundle and name because names repeat across bundles).
- **Plan view:** `build.plan` (`skin_editor/plan.py`) lists what a build would do for a target and what it would drop and why, without writing anything; shown in the Build panel.
- **Import and re-export:** `project.import_native` lays a native skin out as a normal project: sheets in `styles/` (listed in order in mapping.json, mode `native-sheet`), pictures in `images/`, fonts in `fonts/`, anything else in `assets/` (mode `native-asset`), and the `url()` paths in the sheets are rewritten to point there. Exporting writes the sheets flat at the skin root again with the paths turned back, copies the files, and the report counts the imported tokens, rules, images and fonts. For jonukas-wood: 10 sheets, 38 images, 9 fonts, 1452 tokens, 1960 rules, 0 problems; every picture and font is byte-identical and the parsed rules equal the original (urls aside). The source folder is never written. The project's own edits are added after the imported sheets so they win ties. Bundle builds drop the imported sheets, and the plan says so. Projects imported before 2026-11-13 used a `native/` folder; they report "old project layout" and must be deleted and imported again.
- **Projects can be closed and deleted** (`project.delete` moves the folder to `<workspace>/trash/<name>-<time>`; nothing is erased). The import button opens the Windows folder picker (Tauri dialog plugin).
- **Not done in phase 2:** the in-game check of an exported imported skin (the export is identical to the original that is known to work, but it has not been loaded in this build of the game by this tool), and rule replacement or removal for the bundle target (phase 3).

| 3. Bundle target v2 | 5 | Replace/remove/append in sheets; gate; packages; install/restore; real build of a project that deletes and replaces vanilla declarations, seen in game |

**Phase 3 status (2026-11-13): replace and remove are built and pass the gate on the real vanilla snapshot; the in-game check and an install of such a build are still to do.**
- **Syntax (in the normal USS files under `styles/`, no extra file):** `/* replace: .selector */` right before a rule `.selector { ... }` changes the game's own rule(s) with exactly that selector list: listed properties are set in place (added when the rule lacks them). `/* remove: .selector | prop, prop */` (its own comment, no rule) drops those declarations from the game's rule; without `| ...` it drops all of them (the rule stays, empty, so rule indices do not move). Selector lists match as a set of complex selectors, so order and spacing do not matter; a selector that matches no game rule is a plan warning and a gate failure. Other comments that merely contain the word are ignored. A `replace:` that names a different selector than the rule below it is a syntax problem.
- **Model/engine:** `scoped_rules` entries carry optional `op` (`replace`|`remove`) and `remove` (property names); `to_spec` puts them in `edit_rules_by_sheet`; `token_patch.SheetPatcher.edit_rule` edits the decoded rule in place (the value pools stay append-only); `patcher.patch_sheet` applies edits first, then appends, so an edit never sees a rule the build appended. The build report has `edits` (rules hit and declarations changed per edit) and a new `edited` total.
- **Gate:** `verify_static.check_edits` re-derives the expected declarations of every edited rule from the vanilla rule plus the edits in order (same slots in the same order, replaced values with the right encoded types, everything else equal) and also fails when an edit matches nothing or changes which rules it matches. The existing checks (rule count = vanilla + appended, untouched objects equal vanilla, pools append-only) still run.
- **Plan:** `ReplaceRule` and `RemoveDeclaration` operations with the number of game rules each hits. Native target: a replace is written as an ordinary rule (it wins ties), a remove is listed as dropped (USS cannot delete a game declaration).
- **Verified:** unit tests (parse, round trip, patch, gate failures, plan, native) and a real build of a replace plus a remove on `.rotate-manager-shortcut` in SIStyles: 2 edits applied, 0 gate failures, every untouched bundle equal to vanilla.
- **Also done:** Monaco warns on a replace/remove whose selector matches no rule of that game sheet (code no-game-rule; uss.diagnostics takes the optional sheet); the contrast report reads replace rules.
- **Not done in phase 3:** installing such a build and looking at it in the game.

| 4. Assets + mapping editor | 4 | Both targets for textures/icons/SVG; visual mapping; conflict report |

**Phase 4 status (2026-11-13): built; the in-game look of a swap made from the new view is still to check.**
- **Both targets:** the engine already wrote textures, icons (all four UI scales) and SVG (vector) swaps for bundles, and wallpapers/icons/SVG as USS rules for native skins; unchanged.
- **Visual mapping (activity bar I):** every swap of the project with the game's picture beside yours, fit (cover/contain/stretch), where a wallpaper is shown (native target, the five places), replace-file (Windows file picker), remove; `+ add` browses the game's 2,995 images with thumbnails and a filter. New methods: `images.swap_file` (reads a local path, no base64), `images.fit`, `assets.conflicts`.
- **Conflict report (`skin_editor/assetcheck.py`):** errors: replacement file missing, slot no longer in the game, export name clashes with an imported skin's file. Warnings: aspect ratio mismatch (with what fit will do), several wallpapers on one place, icon/SVG that no USS class draws (native cannot place it). Info: fewer pixels than the game's, Crunch re-encoded as plain DXT (bundle grows), one file used for several slots, imported sheet also styles a place, imported sheets dropped by a bundle build. The same rows (errors and warnings) appear in the Build plan's warnings. Verified on the real game: 2,995-row catalog, thumbnails and stored replacements load, Mine reports no conflicts.
- **Staged edits (Images view):** picking a file, the fit and the places only change the view's state (`studio/src/staging.ts`, unit-tested with Vitest: `npm test` in `studio/`). The slot shows the staged picture (dashed) next to the game's with an "unsaved" marker; **Override** writes file + fit + places in one call (`images.commit`, one project save), **Revert** drops the staging, and after a commit the slot shows your stored thumbnail (re-fetched: its cache key carries a per-slot version) with a persistent "saved" badge. The conflict report is refreshed after each commit. A failed commit keeps the staging. `images.preview_file` draws a staged local file.
- **Engine lifetime:** the shell stops the engine it started when the last window closes and waits for it (taskkill /T on Windows, because the venv's python.exe starts the real interpreter as a child); an engine it merely reused is left alone. `FM Skin Studio.bat` also stops every skin_editor Python process after the window exits.
- **Not done in phase 4:** drag and drop of files onto a slot; an in-game look at a swap made from the view (the engine path is the one already seen in game).

| 5. Updates + live preview | 3 | Profile diff across two real builds; reload-and-screenshot loop on Windows |

**Phase 5 status (2026-11-13): built; exit criteria met for style tokens/rules and the Windows reload-and-screenshot loop; evidence in `docs/PHASE5-EVIDENCE.md`.**
- **Profiles (`skin_editor/profile.py`):** `update.scan` stores `profiles/<build>-<catalog12>.json` plus its style index; `update.import_profile` scans a folder of an older build's style bundles read-only; `update.status` compares the live `catalog.hash` and bundle hashes with the active profile: same, `catalog_changed` (guided flow: restore check, new snapshot, scan, diff; bundle installs blocked), `tamper` (catalog same, a bundle differs: bundle installs blocked, restore offered). The install itself already refuses `game_updated` and `modified` states.
- **Diff (`update.diff`):** tokens added/removed/changed/renamed, rules whose selector vanished or moved or changed, sheets, icons (renamed by name similarity), layouts, and with a project a state per item: ok, target moved (auto-fixable by `update.autofix`: token renames, rules moved to the sheet that now holds the game's rule, repointed images), target gone, vanilla value changed.
- **Two real builds:** 27.0.1.2494769 (old style bundles found on disk) against 27.0.1.2503222: tokens identical, 3 selectors vanished, 7 new, 10 changed. Icons and layouts cannot be compared for that pair (their old files are not on disk); they close at the next patch.
- **Live preview (`skin_editor/inspector.py`, `live.py`):** `preview.live` writes the native skin `<name>-preview`, clicks Reload Skin through the inspector pipe, waits 10 s, screenshots; never bundles. Without the pipe it returns `mode: static` with the reason and the Preview panel shows the static repaint. Proven on the real game (magenta rule, on and off).
- **Studio:** U in the activity bar (status, Scan game, Import older build, profiles, Diff, item states, Auto-fix); a PREVIEW tab in the bottom panel.
- **Not done:** selecting the preview skin in the Preferences drop-down automatically; icons/layouts diff on real data; a profile guard that blocks the Build button itself (installs are blocked by the existing tamper check).

| 6. UXML + fonts | 5 | Class edits seen in game; native fonts; FontAsset spike report |

**Phase 6 status (2026-11-13): built and verified offline; the two in-game checks are the user's; evidence in `docs/PHASE6-EVIDENCE.md`, spike in `docs/PHASE6-FONTS-SPIKE.md`.**
- **UXML read:** `skin_editor/uxml.py`, `layouts.*`, Studio view L (tree, inspector, templates one level, class usage over 7,467 layouts and the style rules). UnityPy's writer needed a fix for the null managed reference (`uxml.fix_unitypy_writer`); with it all 7,467 layouts rewrite with every object digest equal.
- **Class/inline/attribute edits:** per-layout patch files `layouts/*.patch.json` (set-classes, set-inline, set-attr; element id plus type/name guard; no structural ops; attributes only as seen in vanilla, names/bindings/templates refused); bundle target only, native drops them with a reason; gate `uxml.check_patches` plus the existing untouched-object and pool checks. Real build gate: 0 failures.
- **Native fonts:** `fonts/` in the project, `mode: font` mapping entries, export copies the file and writes the `url()` token rule, gate checks every url() resolves inside the skin.
- **FontAsset spike:** all 34 game FontAssets are dynamic with an embedded source Font and readable atlases; verdict: route B (swap the source font inside an existing FontAsset) feasible with medium risk, one in-game experiment away; creating new FontAssets is not.
- **Studio:** L view, FONTS section in the Images view, Install build and Restore stock buttons in the Build panel.
- **In game (2026-11-13, build 27.0.1.2503222):** class edit seen (magenta around the Reload Skin row and the skin chooser), gate passed. **Still open:** native font check and Restore stock (user), layout item states in the update diff (next patch).

| 7. Layout + tables | 6 | Spike verdicts first; then position writes with in-game proof; table view read/edit |

**Phase 7 status (2026-11-13): CLOSED. Tile position write and table-view edit both seen in game (build 27.0.1.2503222); evidence in `docs/PHASE7-EVIDENCE.md`, verdicts in `docs/PHASE7-TILE-SPIKE.md`, where-a-table-is-used in `docs/TABLE-VIEW-USAGE.md`.**
- **In game:** `p7-tile-test` (instructions left, pitch right, at Small and Large); `p7-table-test-3` (Squad overview "Physical" view: Jumping Reach hidden, Pace moved after Player). Two earlier table tests did not show an effect because their views were not on screen (`SquadKeyPlayersTableSmall`: International Youth Setup only; `PlayerLoansTileTable`: the visible Loans tile is `LoansTile_4x2`, whose columns are a list in the layout).
- **Carried:** layout edit for string-list columns, icons/layouts diff and layout item states at the next patch, drag-and-drop onto image slots, FontAsset experiment (Source Font File must be assigned), real mouse drag test on the tile canvas, store-variant paths.
- **Spike verdicts:** tile position writes exact on all 1,823 compositions (unchanged rewrite = 0 differing objects; one move = 1 object, 1 leaf; gate proves vanilla plus exactly the asked edits); size stays blocked (4,724 of 5,162 config cells, reproduced); the user `views/*.fmf` files are opaque and not a write target, tables are written in the bundle.
- **Real data (warning 10):** `skin_editor/layout_export.py` turns the real FM27_LayoutMCP index plus the composition and panel bundles into a valid `fmlayout-index/2` dump (cross-checked cell by cell against the bundles, 0 mismatches); the editor adapted to the real schema (see the spike document); `layout.export_index` imports it, fresh against the snapshot.
- **Writes:** `tiles.py` (move-cell x/y from the stored placement edits, bundle target), `tables.py` (set-width, hide, show, move per view; patch files `tables/*.patch.json`), both gated in `verify_static`, planned (`MoveCell`, `SetColumnWidth` ...), dropped with a reason on the native target.
- **Studio:** T tile canvas and V table views, both behind error boundaries.
- **Open:** position writes and a table edit seen in game (user); carried: icons/layouts diff and layout item states at the next patch.

| 8. Windows release | 4 | **Descoped 2026-11-13 by owner decision to Windows only** (was: cross-platform + release). Windows installer with the bundled frozen engine, auto-update via GitHub Releases. |

**Phase 9 (planned): in-app visualiser.** Plan approved 2026-11-13 with amendments, in `docs/PHASE9-PLAN.md`: DOM/CSS renderer fed by an engine-side cascade, 8 px / 5 percent geometry tolerance and exact colours and font sizes, calibrated screens (Squad overview, Team Instructions, Preferences) as the real exit, standing budget under 200 ms cached per layout. Starts after the Phase 8 auto-update proof.

**Descope (owner decision, 2026-11-13): Phase 8 is Windows only.** All macOS work is dropped indefinitely: no macOS full run, no signing, no notarisation, no Apple Developer account, no `.app` questions. Linux/Proton stays deferred; the fake-tree tests in `tests/test_userdirs.py` are its only coverage and nothing was or will be run on Linux. The macOS and Linux rows in Part 5, the "macOS never run" warning (Part 1) and the macOS items in Parts 6 and 7 stay in the document as history and design notes, not as work.
**Revised exit criteria:** (1) the Windows installer is installed and running with the bundled engine and no Python on PATH; (2) auto-update proven from one installed version to the next through GitHub Releases; (3) all tests green; (4) the carried items (icons/layouts diff, layout item states) still close at the next FM patch.

**Phase 8 status (2026-11-14): CLOSED (Windows only); plan, status and evidence in `docs/PHASE8-PLAN.md`.** Installer proven with the bundled engine and no Python on PATH; auto-update proven 0.1.1 to 0.1.2 through GitHub Releases (`hubertlapinski3-cmyk/FMSKINEDITOR`); updater key to be kept backed up by the owner. Phase 9 starts at M0 (`docs/PHASE9-PLAN.md`).
*(Earlier status, kept for history:)* IN PROGRESS (Windows).
- **Done and run (Windows):** PyInstaller one-dir engine (`tools/freeze_engine.py`), a frozen build bit-identical to the venv build of the in-game-proven bundle, frozen `serve` + RPC; shell prefers a bundled engine (`cargo check` passes); Windows user folder via the Documents Known Folder; platform path rules (`skin_editor/userdirs.py`, 10 tests on fake trees).
- **Open:** installer built, installed and proven; GitHub Releases auto-update.

Each phase ends with an in-game check recorded as evidence; nothing is called done on tests alone.

---

## Part 12. Warnings and lessons

From this project's own incidents [V]:

1. **Wrong folder.** A recursive search picked a restore copy inside the game folder; snapshots and installs went to the copy. Bind to the executable's data folder and refuse installs when the snapshot source differs.
2. **Wrong base.** Builds made from a stale snapshot were copied into a newer game. Tie every package to a profile and refuse cross-profile installs.
3. **Leftover test bundles.** A spike left a modified bundle in the game folder; `catalog.hash` did not notice. Hash every UI bundle (tamper check), not just the ones you patch.
4. **Byte-as-float colours.** 16 vanilla colour entries are outside 0..1; normalising them silently changed colours. Quarantine what you do not understand.
5. **Reference-sheet shortcut.** Picking one sheet's token value hid real conflicts. Model the truth.
6. **Icons are not what they seem.** The 286 VectorImages are a minority; most icons are atlas sprites behind classes. Verify which asset an element draws before building a swap for it.
7. **Wallpapers and club colours are code-bound.** No stylesheet or texture choice changes which image the game picks; hide and cover, or replace the texture content.
8. **Python distribution.** Newest Python without wheels, a locked pip cache file: ship a frozen engine.
9. **JS numbers.** 64-bit path ids silently lost precision in the browser.
10. **Synthetic fixtures drift.** The layout features have never met real data; do not build UI on top of an untested contract.

From other skins on this machine [V by reading them]:

11. **Native USS skins are the community's stable route** (Jonukas, FM Dugout): no game files changed, hashed asset names, `@import` structure, dated in-game notes. They still need per-update touch-ups ("after an FM27 update a spot may look different").
12. **Hide-and-cover beats replacement** for code-bound visuals: `--unity-image-tint-color: #00000000` on the bound element, reset on children, paint a sibling.
13. **Text coloured in code** (`<color>` tags) cannot be restyled by `color`; Jonukas uses text outlines and thinned fonts as a workaround. Expose this as a documented limitation, not a bug.
14. **Restore folders inside the game directory** (e.g. "FM Blog Classic Skin 112 Restore") are common; treat any duplicate data tree as a hazard.

General [A]:

15. Bundle-replacing skins are undone by every Steam update and by Verify Integrity, and can conflict with each other; make the tool say which bundles a package owns and detect foreign changes.
16. Store builds with protected install folders (Game Pass) may make bundle installs impossible; the native target must always be a complete fallback.
17. Do not redistribute game assets: packages should contain only user content and patches (operations), with bundles rebuilt on the user's machine from their own snapshot. This is also what makes a package survive a game update.
18. Unverified in this document: the internals of other community builders. Where this spec says how "existing tools" behave, it is limited to the files read on this machine.
