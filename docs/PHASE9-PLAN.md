# Phase 9 implementation plan: in-app visualiser (for approval; no code written)

Written 2026-11-13 against game build 27.0.1.2503222. **Approved by the owner on 2026-11-13 with the amendments below (marked AMENDED).** Sequence: Phase 8's auto-update proof first (the owner is doing the GitHub setup), then the Phase 9 build in milestone order, with evidence at the end of each milestone. Nothing of Phase 9 is built yet.

**Approved decisions:** (1) DOM/CSS rendering, no Python-side layout, on the condition that the value map never silently drops a property (section 1). (2) Tolerance: 8 px or 5 percent, whichever is tighter per element, and exact equality on resolved colours and font sizes; the calibration report publishes passes and failures both (section 8). (3) Scope: all 7,467 layouts render as trees; pixel-faithful claims only for Squad overview, Team Instructions and Preferences; the fixture framework makes every new evidence screenshot a cheap extra fixture (section 8). (4) The layout-index sqlite stays optional; compositions are read from the game bundles directly, the route Phase 7 proved (section 3).
**Standing rules for the phase:** nothing is called done on tests alone; the calibration screens that compare against in-game evidence are the phase's real exit; the performance budget below; the M0 spike runs one layout end to end before the full cascade work starts.

## 1. The one design decision to approve first: render with the webview's own CSS engine

UI Toolkit lays out with Yoga, a flexbox engine, and USS is a CSS subset. The Studio already runs in a browser engine. So the plan does **not** write a layout engine:

- **Engine (Python)** resolves what is specific to this game: which elements exist, which rules match each of them, in what order, with token values resolved, and returns a **render tree of computed declarations** per element.
- **Studio (React)** maps each element to a `<div>` with `box-sizing: border-box`, flexbox defaults set to USS defaults (column direction, `min-width/height: 0`, `align-content: flex-start`, `position: relative`) and the computed declarations as inline CSS. The browser does the geometry.
- The difference from the game is then confined to Yoga-versus-CSS edge cases, text metrics and runtime behaviour, which calibration measures (section 8). A hand-written Yoga port would take weeks and still need that calibration.

Alternative rejected: Python-side layout. It doubles the work, ships pixel data over RPC, and gains nothing in fidelity.

**AMENDED: no property is dropped silently.** The USS-to-CSS map in `render/values.py` is a table with one of three statuses per USS property: `mapped` (equivalent CSS, same meaning), `partial` (CSS approximates it; the difference is written next to the entry, e.g. `-unity-font-style`, `-unity-text-align`, `-unity-slice-*`, `background-image` fit modes, `text-outline`), `unmapped` (no CSS equivalent, e.g. `-unity-paragraph-spacing`, hover/active transitions, `-unity-material`). The render tree carries, per element, the full list of declarations that won the cascade **with their status**; the renderer applies `mapped` and `partial` ones and never discards an `unmapped` one: it stays in the data, the explain panel shows it flagged (a visible "not rendered" or "approximated" badge with the note), and the element gets a small corner marker in the render. The same table drives a fidelity report: counts per status over a whole layout or screen. Any property name not in the table at all is `unknown` and is shown the same way. Tests: every USS property found in the 49 sheets' rules plus the inline rules of all layouts is in the table (a failing test lists the ones that are not), and a render of each calibrated screen reports its unmapped/partial totals in the evidence.

## 2. Engine module layout and the new calls

New package `skin_editor/render/` (nothing existing is moved):

| Module | Job |
|---|---|
| `render/values.py` | Parse the value *text* the style index already stores (`"12px"`, `"var(--x)"`, `"rgba(...)"`, `url(...)`, `linear-gradient`, keywords, lengths, `%`) into typed values; USS property -> CSS property map with the subset and the dropped properties listed (no hover/animation) |
| `render/cascade.py` | The cascade: sheet order, selector matching (id, class, type, descendant `" "`, child `>`, `:root`, wildcards), specificity, source order, inline rule last, `!important` if present; returns per element the ordered list of matched `(sheet, rule index, selector, specificity)` and the winner per property |
| `render/tree.py` | Build the render tree of one layout: elements from the VisualTreeAsset, templates resolved one level (more on demand), placeholders for bindings and data; calls `cascade` for every element |
| `render/geometry.py` | Compositions and the screen -> tiles assembly (section 5) |
| `render/overlay.py` | The project's patch set applied to the in-memory inputs (section 6) |
| `render/assets.py` | Images, fonts, placeholders (section 7) |
| `render/fixtures.py` | Calibration fixtures and comparison helpers (section 8) |

New API methods (in `api/methods.py`, listed in `docs/API.md` as usual):

- `render.layouts` {q, area?}: the 7,467 layouts with name, bundle, path id, element count, area (already known), whether it hosts a grid. Cached.
- `render.layout` {bundle, path_id, project?, skin: bool, include_depth?}: the render tree. `skin: false` is vanilla, `true` applies the project.
- `render.screen` {panel_id, breakpoint?, project?, skin}: a screen assembled from its tile sets (section 5).
- `render.explain` {render_id, element_id}: every matched rule in cascade order (sheet, selector, specificity, source: vanilla sheet / project USS file and line / layout patch), the winning declaration per property, and the token chain back to its definition.
- `render.where` {project, file, line or selector}: the first layouts a rule of the USS editor matches, for the editor's jump-to-render.
- A push event `render.invalidate` on project save so the open render repaints (the event bus already exists).

## 3. Data flow, bundle cache to render tree

```
game's ui-visualtreeassets bundles --(UnityPy, uxml.Layouts.load/tree, cached on disk by bundle size+mtime)--> layout typetree: elements, classes, m_RuleIndex, inline sheet, usings
game's ui-styles bundles          --(index_styles.StyleIndex, already cached by manifest hash)------------------> 49 shared sheets: rules, selectors, value texts
                                                                                      |
                              render/cascade (sheet order + selector match + specificity + inline)  <--- project overlay (section 6)
                                                                                      |
                                              render/tree -> JSON render tree -> Studio DOM renderer (CSS flexbox)
```

All reads come from the **vanilla snapshot** (the project's own base), never from the live game folder, so a test bundle left installed cannot change a render. The build's profile/catalog hash is part of every cache key.

**AMENDED: compositions come straight from the game bundles.** The tile compositions and their cells (`ui-tileslayouts`, `ui-tactics`, `ui-dynamiccardcollections`, plus the panel ids bundle) are read with the same reader Phase 7's `layout_export.py` uses against the bundles; the FM27_LayoutMCP sqlite is **optional**, used only as an accelerator or a cross-check when present, and the render works without it. A render never requires a path outside the project and the workspace.

**AMENDED: performance budget.** A cached render of one layout returns in **under 200 ms** (server time, `render.layout` with a warm cache on the profile's snapshot); a cold first render of a layout is allowed to be slower but reports its time. (The owner's figure, quoted as the standing budget: I could not find a numeric budget in `docs/SKIN-BUILDER-SPEC.md`, so this plan records it as the requirement and the phase reports measured times against it for the calibrated screens and a sample of 100 layouts, p50/p95/max.)

## 4. What is reused, and what is genuinely new

**Reused as it is**
- **L view decode:** `uxml.Layouts` (`list`, `load`, `tree`, `element`, `inline_rule`, `usings`): elements, classes, attributes, `m_RuleIndex` and the inline sheet, templates resolved one level. This is the render tree's skeleton.
- **Style data and token resolver:** `index_styles.StyleIndex` (all sheets with rule selectors and value texts, `value`/`chain`/`value_colour` token resolution, `REFERENCE_SHEET`) and `uss` (`selector_map`, `selector_text`, `value_text`, `prop_name`).
- **Specificity and selector parsing:** `token_patch.parse_selector`, `token_patch.specificity`, `layout.chain_matches` (a working descendant/child matcher used by the reach check). The cascade module wraps and extends them (pseudo-classes become "runtime state, not applied").
- **Composition index:** `layout_dump` / `layout_join` / `layout_view.View` (screens, tile sets, compositions, cells with x/y/w/h, configs) and the `fmlayout-index/2` dump, plus `placement` for the project's tile moves.
- **Icon map and images:** `images.icon_classes`, `icon_catalog`, `icon_index`, `render_icon`, `thumbnail`, `render_vector`, `docs/image-map.json`; the bundle cache `ws.cache`.
- **Project patch appliers:** `uxml.apply_to_layout`, `tiles` (move ops), `tables.apply_to_view` and the USS/`native` sheet export, run on in-memory copies, so a render is produced by the same code the build uses (see section 6).
- **Jobs, events, error boundaries, the `Guard` component, the Monaco USS editor and its rule model.**

**Genuinely new**
1. The **cascade as a function** (today the project only checks reach and resolves tokens; it never answers "which declaration wins on this element").
2. Typed **value parsing** and the USS->CSS mapping.
3. The **render tree** and the **DOM renderer** with the outline/side-panel UI.
4. **Screen assembly** from tile sets, with cell-unit-to-pixel geometry (section 5).
5. **Placeholders** for bindings, tables and data.
6. The **fixtures and comparison harness**.

## 5. Geometry strategy

- **Inside a layout:** CSS flexbox from the computed declarations (section 1). Percent/auto/absolute offsets map one to one.
- **Layouts that have a composition** (tiles and panels hosting a grid): the cell grid of the composition at a chosen breakpoint, `m_gridComponents[].m_location{x,y,width,height}` in cell units, drawn as CSS grid. Cell pitch (px per cell and gap) is **measured, not guessed**. A first, provisional fit from the c2 session's inspector dump of the 4x2 Loans tile (312 x 148 px, Small + Larger text) gives 66 px cells with 16 px gaps, but that assumes square cells and equal gaps from one tile, so it is a starting point only. M0/M3 repeat the fit over many tiles and each breakpoint (Small/Medium/Large x text scaling) from `ui-dumps` captures, store the result as a small table, and list it in the evidence.
**AMENDED (provisional pitch, per-composition if it varies).** The 66 px / 16 px pitch is one tile at one setting. **Before M3 exit** it is verified against several different compositions taken from the game data (at least one 20x11 fullscreen, one 16x9, one body preset, a team-instructions composition at Standard and Large, and the Squad overview composition), using the preset sizes the bundles carry (`preset_w x preset_h`) and the inspector dumps and screenshots we hold for each. If the pitch differs between compositions or breakpoints, it is **measured and stored per composition (and breakpoint)** in a `pitch.json` keyed by composition name, with the evidence source of each entry; there is no global-grid fallback that pretends to know. A composition with no measurement renders with a flagged estimate (derived from the preset) and is excluded from any pixel-faithful claim.
- **Layouts without a composition** (the majority: panels, blocks, templates): drawn at a nominal container size per area (tile blocks at their config sizes `size_w x size_h`, screens at the preset size, otherwise a chosen viewport) using their own flexbox; no invented positions. A documented fallback: unknown width = fill the viewport, unknown height = content.
- **Screens:** `render.screen` assembles the root layout, then fills every grid with the tile layouts its set places (the existing `screen`/`_sets` data), resolved to the config the cell size selects. This is what makes the Squad overview or Team Instructions render as screens rather than empty frames.
- **Honesty:** nothing is positioned by the cascade that the game would not position; any element whose geometry I fall back on is flagged in the render tree and shown in the notice.

## 6. How project patches layer into the render

The overlay is applied to **inputs**, then the same cascade runs, so "vanilla vs skin" is one flag:

| Project feature | Applied how |
|---|---|
| Token edits and rules, native route | The project's `styles/*.uss` parse into extra sheets appended at the end of the sheet order (author sheet last, as the native skin loads); rule source = file + line |
| Token edits and rules, bundle route | The same edits as the build's SheetPatcher on the in-memory sheet list (`token_patch`), so bundle-route render equals the build's expected state |
| Phase 6 class patches and inline patches | `uxml.apply_to_layout` on the in-memory typetree (classes, attrs, inline rule) |
| Phase 7 tile moves | `placement` edits change the composition cell x/y in the screen assembly |
| Phase 7 table edits | `tables.apply_to_view` on the view; tables render as a labelled placeholder table whose **header row is the view's column order**, so the c3 result is visible |
| Phase 3-5 colour/token swaps | token resolution of the project's `mapping.json` |

The side panel marks each matched rule's source as `vanilla sheet`, `project USS file:line`, or `layout patch`. **AMENDED: `render.invalidate` fires on any project change**, not only on USS saves. It is raised from the places every mutation goes through, so no editor can forget it: (1) a hook in `project.save` (the engine's 15 save call sites: tokens, rules, class/inline patches from the L view, table edits from the V view, fonts, image swaps, options, new sheet ...); (2) the folder-project file writes (`project.write_file`, new sheet, delete, import); (3) the tile placement store (`workspace/placements/<project>.placements.json`), which T-view moves write **outside** `project.save`; (4) project open/close/delete. The event carries `{project, reason, scope}` where reason is one of `tokens|rules|layout-patch|tile-move|table-edit|font|image|file|options`, so the page can repaint only what a change can affect, and it is debounced to one event per burst. **The vanilla/skin toggle repaints as well**, and so does switching the project or the breakpoint. Test: for each mutating API call, exactly one invalidate event is observed, and a render requested after it reflects the change (a token edit, an appended rule, a class patch, an inline patch, a tile move, a table edit, an image swap).

## 7. Images, fonts, data

- **Icons:** icon classes -> atlas sprites via `images.icon_classes`; **textures** via PPtr -> bundle cache -> PNG (`thumbnail`); SVG vectors via `render_vector`. Cached as data URLs the existing way.
- **Fonts:** `url()` families in the project load through the webview's FontFace; vanilla families (FM Universe, the primary sans) are approximated with the closest installed font and flagged.
- **Bindings and data:** every `SIText` with a binding renders its bound path as a placeholder chip (`team.Name`), tables as a placeholder grid, switch elements show their first branch and say so. No hover, no animation, no pseudo states.
- **Code-bound visuals** (club colours, wallpapers): drawn from the knowledge packs (`preview.py` models) and flagged approximate.
- A **permanent notice** on every render: approximation, what is placeholder, what is applied.

## 8. Calibration fixtures (exit criterion 3)

**AMENDED tolerances (fixed by the owner):** box geometry passes when the difference is within **8 px or 5 percent of the measured size, whichever is tighter, per element**; resolved colours and font sizes must be **exactly equal**. The calibration report **publishes passes and failures both**, per fixture and per element (expected, got, delta, verdict); a failure is never filtered, averaged away, or re-toleranced to turn green. The report is generated by the test run and stored with the evidence.

Each fixture is a stored expectation plus these tolerances, run in the test suite and reported in the evidence.

| Fixture | Source of truth | Check |
|---|---|---|
| Red around the pitch, Phase 3 | the `Mine` rule on `.tactics-collapsable-pitch-container` and the in-game screenshot | the matched rule is the project's, in cascade order above the vanilla one, red wins; the element is the pitch container |
| Magenta Reload Skin button, Phase 5/6 | the p6 class test and the screenshot | the class patch appears in the matched rules; the button's background resolves to the patched value |
| Tile positions b1/b2 | `tile-1/tile-2` screenshots and inspector positions (instructions x=40, pitch x=1274 at Small; x=865 at Large) | the render puts the instructions cell left of the pitch cell at both breakpoints, with a tolerance on x of a few px; the vanilla render has them swapped |
| c3 table header order | `c3-table` screenshot | the placeholder table's header row equals Picked, Inf, Player, Pace, Acceleration, ..., no Jumping Reach; vanilla shows the stock order |
| Cascade against known vanilla values | the inspector `fm_get_styles` resolved values (e.g. `thematic-xxl` font-size 40) and the sheet list on the root | resolved declarations equal the inspector's for a set of elements (a list of ~30, taken once and stored) |
| Geometry | inspector bounds (`fm_dump_tree`, e.g. the Loans tile tree) | element boxes within the tolerance above, reported as a table, failures included |

**AMENDED: the fixture framework makes a new evidence screenshot a cheap extra fixture.** A fixture is **data, not code**: one folder `tests/fixtures/render/<name>/` holding `fixture.json` (what is being rendered: screen/layout, breakpoint, project and whether the skin is applied, game build and date), the screenshot, an optional inspector dump (`fm_dump_tree` JSON), and `expect.json` (the checks: element selectors -> expected resolved values or boxes, rule-in-cascade expectations, table header rows, tile positions). One generic test discovers every fixture folder and runs it; one command, `python -m skin_editor fixture add --name N --dump DUMP.json --screenshot S.png --screen PANEL`, creates the folder from an inspector dump and a screenshot **and fills `expect.json` from the dump** (resolved styles and bounds for the elements in it), so adding evidence from the next in-game session is a few minutes, not a coding task. The calibrated set therefore grows as evidence accumulates, and the report counts fixtures and passes. The earlier inspector screenshots and dumps in the workspace notes (`ui-dumps/`) are candidate fixtures; they are **not required for exit**, and I will convert the cheap ones after M7 if the owner wants them.

Plus unit tests: specificity and order cases, token chains, value parsing, render-tree snapshots for a few layouts (small, medium, one 5,000-element screen) kept as golden JSON.

## 9. Milestones and estimates (working days, one developer; these are estimates, not commitments)

| # | Milestone | Days | Done when |
|---|---|---|---|
| M0 | **Spike: one layout end to end before any full cascade work.** One real layout (a small tile, e.g. `LoansTile_4x2`, whose inspector tree we hold) goes through the whole chain: typetree -> minimal value parser -> minimal cascade -> JSON render tree -> DOM -> compared with the inspector's resolved values and bounds. Then widen to 10 layouts; decide the sheet order from the root's attached-sheet list. Measures its own time against the 200 ms budget | 2 | The single layout renders, resolved values equal the inspector's (exact for colours and font sizes), gaps are named; the sheet order and the cached time are recorded. **The full cascade work (M1) does not start until this passes or its gaps are written up and accepted** |
| M1 | `values.py` (with the mapped/partial/unmapped/unknown table), `cascade.py`, tests for specificity/order/inheritance | 4 | Cascade tests green on vanilla values; every USS property in the sheets is in the map |
| M2 | `tree.py`, `render.layout`, DOM renderer, layout browser, flagged-property markers | 5 | Any of the 7,467 layouts renders vanilla offline as a tree; cached p95 under 200 ms on a 100-layout sample |
| M3 | Compositions read from the bundles, screen assembly, **per-composition pitch verified against several compositions** (section 5) | 4 | **Two screens match screenshots** (Squad overview and Team Instructions) within the tolerance, the pitch table is stored per composition where it varies, and **the phase report states what remains placeholder instead of widening the claim** |
| M4 | Images, icons, fonts, placeholders, notice | 3 | Icons and textures show; data is labelled |
| M5 | Overlay: USS, class/inline, tile moves, table placeholder, vanilla/skin toggle, `render.invalidate` on every project change | 3 | A token edit, an appended rule, a class patch, an inline patch, a tile move and a table edit are all visible, each from its own editor (L, T, V views, USS), each firing exactly one invalidate; the toggle repaints |
| M6 | Side panel: click -> rule -> token chain, both directions with the USS editor, flagged properties shown, repaint on change | 4 | The click-to-rule-to-token chain works both ways; unmapped and partial properties appear flagged in the panel |
| M7 | Fixture framework (data-driven, `fixture add`), all six calibration fixtures, geometry table, **published pass/fail report**, evidence | 4 | All six fixtures run; the report lists every pass and every failure; the exit is judged on the calibrated screens (Squad overview, Team Instructions, Preferences), not on tests alone |
| M8 | Performance, error boundaries, docs, README | 2 | A 5,000-element screen renders in a few seconds |
| | **Total** | **31 (about six weeks)** | |

## 10. The three biggest risks and the mitigation for each

1. **Fidelity: the render looks plausible but is wrong in places** (Yoga vs CSS edge cases, text metrics, runtime-applied classes, bindings that change visibility). Mitigation: calibrate against measured inspector values and bounds, publish the tolerance and the failures, flag every unresolved element in the UI, keep the permanent approximation notice, and make "compare with live" (the Phase 5 loop plus an inspector bounds dump overlaid on the render) the official escape hatch. The render never claims to replace the in-game check.
2. **Screens are mostly data, so renders look empty or wrong** (tables, lists, switch elements, tiles chosen at run time; geometry for layouts with no composition). Mitigation: assemble screens from the tile sets the composition index already holds, placeholders with real column names and bound paths (the `used_by` and view data we already read), first-branch rule for switches, and explicit "geometry fallback" flags. Scope guard: milestone M3 ends with two screens that match screenshots; if more do not, the phase reports which categories are placeholder instead of widening the claim.
3. **Scale and data dependency:** 135,434 elements and 49+ shared sheets with a rule index of about 23,600 selectors; per-element matching and 5,000-node DOMs can be slow; and the richest index (the FM27_LayoutMCP sqlite) lives outside the repo at a hard-coded path. Mitigation: an inverted index (class/id/type -> rules) built once per profile and cached, matching only the elements of the layout in view, includes expanded lazily, DOM virtualisation and a node cap with a "show more"; the render reads the game's own bundles, including the compositions (the Phase 7 route), and the sqlite is **optional** (decided), only an accelerator or cross-check; every cache keyed on the profile hash; the **200 ms cached budget** is measured and reported, not assumed.

## 11. Decisions (all resolved by the owner, 2026-11-13)

1. **Rendering approach:** DOM/CSS approved, no Python-side layout; condition: no silently dropped property (section 1).
2. **Tolerances:** 8 px or 5 percent, whichever is tighter per element; exact equality on resolved colours and font sizes; passes and failures both published (section 8).
3. **Scope:** all 7,467 layouts as trees; pixel-faithful claims only for Squad overview, Team Instructions and Preferences; every new evidence screenshot a cheap extra fixture (section 8).
4. **FM27_LayoutMCP sqlite:** optional; compositions are read from the game bundles (section 3).
5. **Order:** Phase 8 auto-update proof first, then Phase 9 in milestone order with evidence at each milestone end.

Amendments carried into the plan: pitch is provisional and verified per composition before M3 exit (section 5); `render.invalidate` on any project change including the toggle (section 6); performance budget under 200 ms cached per layout and the M0 one-layout spike before M1 (sections 3 and 9); M3 exit as stated, with the placeholder statement (section 9).
