| Method | Kind | Parameters | HTTP route (first server) | What it does |
|---|---|---|---|---|
| `api.methods` | call | - | - | This table: every method with its parameters. |
| `jobs.list` | call | - | - | All known jobs, oldest first. |
| `jobs.get` | call | id: str | - | One job: state, progress, result or error. |
| `jobs.wait` | call | id: str, timeout?: num | - | Block until the job finishes (or the timeout, seconds), then return it. |
| `jobs.cancel` | call | id: str | - | Cancel a job that has not started, or ask a running cancellable job (an inventory scan) to stop. |
| `jobs.latest` | call | - | `GET /api/job` | The most recent job in the first frontend's shape. |
| `app.state` | call | - | `GET /api/state` | Install, snapshot, index, tamper and project state. |
| `app.quit` | call | - | `POST /api/quit` | Stop the server. |
| `game.detect` | call | - | `POST /api/detect` | Search the store libraries for FM installs. |
| `game.select` | call | game_dir: str | `POST /api/config` | Use this game folder. |
| `snapshot.take` | call | force?: bool | `POST /api/snapshot` | Copy the stock style bundles (game closed, stock files). |
| `snapshot.reread` | job | - | - | The guided 'the game was updated' recovery, one button: a fresh vanilla snapshot (force) and a rebuilt style index. Refuses while a file this app installed is still in the game folder: verify in Steam first, then use this. |
| `snapshot.record_reference` | call | force?: bool | `POST /api/reference-hashes` | Record catalog and UI bundle hashes for an older snapshot. |
| `index.build` | job | - | `POST /api/index` | Decode the snapshot's stylesheets into the style index. |
| `tokens.list` | call | q?: str, colours?: bool | `GET /api/tokens` | Tokens by name, value or hex code. |
| `tokens.get` | call | name: str | `GET /api/token` | One token: definitions per sheet, alias chain, reach. |
| `literals.list` | call | - | `GET /api/literals` | Colour literals with hit counts. |
| `literals.get` | call | rgb: str, a: num | `GET /api/literal` | Rules using one RGBA, and every alpha of its RGB. |
| `project.list` | call | - | `GET /api/projects` | Project names. |
| `project.get` | call | name: str | `GET /api/project` | Load a project (a new one when it does not exist). |
| `project.save` | call | project: obj | `POST /api/project` | Validate and store a project. |
| `project.routing` | call | project: str | - | A project's Playground build routing (effective route, whether it was chosen explicitly, the competition-sheet choice) with the trade-off in plain words. Read only. |
| `project.set_routing` | call | project: str, route_preference?: enum: skin_folder | bundle, edit_competition_sheets?: bool, layout_route?: enum: custom_layout | bundle, layout_engine?: enum: one_rule | rea, experimental_bundle_layout_edits?: bool | - | Record an explicit build-routing choice (bundle changes game files when installed and can move tiles and edit the winning declaration; skin-folder changes no game file but cannot express those edits) and/or the separate competition-sheet choice (off by default). Saves through the normal project path. |
| `project.files` | call | project: str | - | Files of a folder project (path, kind, bytes); empty for a legacy project. |
| `project.read_file` | call | project: str, path: str | - | One text file of a folder project. |
| `project.write_file` | call | project: str, path: str, text: str | - | Store a text file exactly as given; returns the project's problems. |
| `project.delete_file` | call | project: str, path: str | - | Delete a file of a folder project (not the core files). |
| `project.problems` | call | project: str | - | Compile a folder project and list problems (file, line, message). |
| `uss.diagnostics` | call | text: str, sheet?: str | - | Diagnostics of USS text: syntax, unknown property or token, bad colour, unit, unused class (with quick-fix suggestions). |
| `game.sheets` | call | - | - | The game's stylesheets (name, bundle, rule count). |
| `game.sheet` | call | name: str, bundle?: str | - | One vanilla sheet printed as USS. |
| `build.plan` | call | project: str, target?: enum: native | bundles | - | What a build would do and drop for a target, without writing anything. |
| `project.import_native` | call | path: str, name: str | - | A native USS skin folder (skin.json + sheets + assets) as a project; the source is only read. |
| `docs.checklist` | call | - | - | The in-game checklist (docs/INGAME-CHECKLIST.md) and its results block. |
| `builds.list` | call | project?: str, limit?: int | - | Prepared packages: every build with a package.json (project, id, gate result, files with hashes, plan digest); `latest` marks what Install build would install. |
| `layout.export_index` | call | index?: str, game_build?: str, areas?: str | - | Build the fmlayout-index/2 dump from the FM27_LayoutMCP sqlite index plus the game's composition bundles (cross-checked cell by cell against the bundles) and import it. |
| `render.layouts` | call | q?: str, limit?: int | - | The game's layouts (VisualTreeAssets) for the render browser: name, bundle, path id, element count, filtered by name; `total` is the number that match. |
| `render.layout` | call | bundle?: str, path_id?: id, name?: str, depth?: int, project?: str, skin?: bool, max_nodes?: int, open?: list of str | - | Offline render of one layout (an approximation, never the game's renderer): its element tree with template includes resolved by GUID, the matched rules per element in cascade order and the computed declarations, each flagged mapped, partial, unmapped or unknown; plus the sheet order, the named gaps and timings. Large layouts are cut to `max_nodes` nodes (default 1000, 0 = all): a collapsed node carries `collapsed`, its path in `open` expands it, and `truncated` says what was cut. |
| `render.rule` | call | sheet: str, rule: int, project?: str, skin?: bool | - | One rule of the render's cascade as USS text and where it lives: a game rule is read-only, a project rule gives its file and line. |
| `render.table` | call | path_id: id, project?: str, skin?: bool, breakpoint?: int | - | A table view as a labelled placeholder table: its header row is the column order; with project (and skin not false) the project's column edits are applied. |
| `render.screen` | call | composition: str, width: num, height: num, reserved_right?: int, padding?: int, project?: str, skin?: bool | - | A composition's cells placed on a grid container of width x height px, with measured pitch, tile layouts and flags; with project (and skin not false) the project's tile moves apply. |
| `uidoc.join` | call | composition?: str, bundle?: str, path_id?: id | - | The (bundle, path_id, m_Id) join between the render nodes and the UiDocument nodes of one composition (named, or the one whose tile closure reaches the layout at bundle + path_id): per layout instance, every node's state - joined, not drawn with the reason (root, non-visual), or unmatched - and, for joined ones, the render position it was joined with. Read only; a top layout of the composition is addressable by UiDocument identity, an included layout stays on render-path addressing and the response says so. |
| `uidoc.inspect` | call | composition?: str, bundle?: str, path_id?: id, logical_id?: str, render_pos?: str | - | The editable surface of one JOINED node: every computed property with its evidence class, source and token chain, which kinds the node accepts (colour, spacing, visibility), a selector proposal built from the element's own evidence WITH ITS MEASURED reach (layout.reach over the visual trees: a static lower bound), the two colour routes (token versus scoped rule) with what each would change, and the runtime-dependent caveat where a visibility edit is concerned. Read only. |
| `uidoc.classify` | call | composition?: str, bundle?: str, path_id?: id, logical_id?: str, render_pos?: str, kind: str, props: obj, route?: obj, sheet?: obj, selector?: str, reach?: obj, original?: obj, note?: str | - | Validate a PROPOSED edit of one joined node through the operation model: the candidate operation is built here from the node's own identity and validated by playops.validate - the backend owns every classification (route, scope, refusal) and the exact refusal text comes back when an edit is refused. Nothing is written: the operation is returned, never added to a session. |
| `playground.session` | call | project: str | - | The project's Playground session: its operations (each with its validation and state), the effective projection onto the project fragments, and the per-state counts. Read only. |
| `playground.add_operation` | call | project: str, operation: obj | - | Record one operation (an fm-playop/1 record as uidoc.classify produced it) in the project's session: validated again on entry, supersession recorded, the session saved atomically; the effective projection comes back. |
| `playground.undo` | call | project: str, op_id?: str | - | Mark the newest applied operation (or the named one) reverted in the project's session; the record stays, the build no longer sees it. |
| `playground.redo` | call | project: str, op_id: str | - | Un-mark the named operation (a superseded record refuses and points at the newer edit). |
| `playground.revert` | call | project: str | - | Mark every applied operation of the project's session reverted (the history is kept, nothing is deleted). |
| `playground.validate_move` | call | composition: str, cell_index: int, geometry: obj, project?: str, resize?: bool | - | The overlap and bounds gate for a tile move or a RESIZE candidate (resize: true runs the same D2 overlap and grid limits without the move-only size block), run as the gesture moves: blocks, warnings and collisions (with the region named) from the placement validation against the imported dump, plus the project's other stored placements. Read only: nothing is stored. |
| `playground.validate_add` | call | composition: str, element_id: str, cell_index: int, geometry: obj, description: obj | - | The gate for ADDING a cell (a candidate operation, preview-only until the add-tile runtime test passes): the new element id must be unique within the composition, the new rectangle must overlap no cell, and the named tile description and configuration index must exist. Read only. |
| `playground.build_operation` | call | kind: str, composition: str, cell_index?: int, geometry?: obj, element_id?: str, max_size?: obj, description?: obj, tile?: obj, project?: str | - | The BACKEND builds the operation record for a screen-canvas gesture: the kind's gate runs first, then the record is assembled from the composition's own data and validated by the operation model; the browser never assembles an operation. The caller records it through playground.add_operation. |
| `render.preview` | call | screen: str, width: int, height: int, setting?: str, states?: list of str, seed?: str, project?: str, simulated_visible?: bool, reserved_right?: int, game_states?: obj, custom_layouts?: obj | - | The deterministic preview: the composition selection from the MEASURED points (1024 -> Small, 1440 -> Standard, 1920 -> Large), each storing the window mode and UI setting it was observed with - a measured width with a different requested setting, or a point whose setting was never recorded, is an ESTIMATE, never a measured claim; between the points an ESTIMATE naming the points it lies between. The breakpoint keys are read from the composition set's SERIALIZED m_gridBreakpointCompositionData; the layout dump is only a cross-check and every disagreement is a named G21 gap. The grid is render.screen's formula, the hosts and the tree carry exactly one evidence flag per node (reconstructed / reconstructed with estimated geometry / simulated / runtime-only), the UI-state cascade applies the sheets' own pseudo rules on a separate path (the default render untouched), placeholders are seeded and never real data, the serialized optional slots are returned with their conditions and inverse flags; visibility follows the game states (default scenario: an ordinary career game, not in a match; game_states drives it; always preview data), the locked Information Display combinations are shown as locked by the game, the state switch options come from the sheets' declared pseudo rules and the measured runtime classes (unsupported states are absent, never shown), and the session's operations are drawn (buildable and candidate marked; pending for compositions not active at the chosen width). Read only. |
| `render.preview_compare` | call | screen: str, a_width: int, a_height: int, b_width: int, b_height: int, setting?: str, seed?: str, project?: str, simulated_visible?: bool, game_states?: obj | - | Side-by-side: two resolutions, each with its selected composition and its evidence label, plus the cell differences between them (appear / disappear / geometry change, cells matched by element id). Read only. |
| `playground.preview_settings` | call | project: str, settings?: obj | - | Read (settings absent) or save the Playground preview settings in the project's own session, so resolution, UI setting, seed, state, simulated toggle and game states survive save-as/export/import/duplicate and a reload. |
| `build.session` | call | project: str, ts?: str, referrers?: obj | - | Build the Playground session from the verified stock snapshot (never the live game folder): every applied operation is routed by what has been proven (token overrides and scoped rules through the skin folder; tile MoveNode through the composition's own bundle; candidate and refused kinds refused with reasons), stale/unresolved operations and identity mismatches are refused, same-cell conflicts and the overlap gate on the composition after all moves run across the whole session, only target bundles are rebuilt, the built bundle's cell layer is compared with the intended moves exactly, the referrer bundles are reported as affected, the skin folder and the schema 2 package are written, and buildability is reported separately from installation readiness. 5G installs nothing. |
| `playground.screens` | call | profile?: str | - | The compositions that hold tiles, with their cells (element id, grid position and size, flags) and per-profile confidence labels, read from the imported layout dump. |
| `playground.screen_index` | call | - | - | B4: full screen index listing panel, composition set, breakpoints, skin variants, and editability per composition. |
| `playground.favourites` | call | - | - | Read the pinned Game Layouts favourites stored in the workspace. |
| `playground.set_favourites` | call | favourites: list | - | Persist the pinned Game Layouts favourites in the workspace. |
| `tables.list` | call | q?: str, limit?: int | - | The game's table views (ui-tableviews): name, path id, column count. |
| `tables.view` | call | path_id: id, project?: str | - | One table view: its columns in order with width and flags, what each column's row cell draws (factory, default width, cell layout), the columns the factory could add; with a project, its patch file. |
| `tables.usage` | call | index?: str | - | Where table views are used: decode the view GUIDs from the layouts' InitFunction arguments in the FM27_LayoutMCP index (read-only) and store the map in the workspace; `tables.view` then returns `used_by` (layout, tile, compositions) and `used_by_summary`. |
| `tables.edit` | call | project: str, name: str, path_id: id, op: obj | - | Add a column edit (set-width, hide-column, show-column, move-column) to the project's patch file of a table view. Bundle target only. |
| `tables.unedit` | call | project: str, name: str | - | Remove the patch file of a table view from the project. |
| `layouts.list` | call | q?: str, bundle?: str, limit?: int | - | The game's UXML layouts (VisualTreeAssets): bundle, name, path id, element count; filtered by name. |
| `layouts.tree` | call | bundle: str, path_id: id, project?: str | - | One layout as an element tree (type, name, classes, attributes, inline style, bindings read-only), templates resolved one level; with a project, its patch file for that layout. |
| `layouts.class_usage` | call | class: str | - | Where a USS class is used: layouts with elements carrying it, and the style rules that mention it. |
| `layouts.edit` | call | project: str, bundle: str, name: str, path_id: id, op: obj | - | Add an edit (set-classes, set-inline, set-attr; addressed by element id plus a type/name guard) to the project's patch file of a layout. Bundle target only. |
| `layouts.unedit` | call | project: str, bundle: str, name: str, id: int, op?: str | - | Remove the edits of one element (or one op kind) from a layout's patch file. |
| `font.tokens` | call | - | - | The game's font-family tokens, the targets of a font swap. |
| `font.set` | call | project: str, token: str, path: str | - | Assign a .ttf/.otf file to a font token (native target: the export copies the font and writes the url() rule). |
| `font.remove` | call | project: str, token: str | - | Remove a font assignment. |
| `inspector.status` | call | - | - | Is the FM27 inspector pipe answering? {online, game, scene} or {online: false, reason}. |
| `preview.live` | call | project: str | - | Live preview: write the project as a native skin skins/<name>-preview, ask the game to reload skins, screenshot it through the inspector. mode static + reason when the pipe is unavailable. Never touches bundles. |
| `findings.get` | call | - | - | The Session 2 findings (the gallery themes in the game): themes, screens, a verdict per theme and screen, the findings, and which screenshots this workspace holds. |
| `screens.list` | call | - | - | Game screenshots kept in the workspace (game-screens), for the tile organiser's backdrop; the folder is never part of a project or a skin. |
| `screens.image` | binary | name: str | - | One game screenshot (PNG). |
| `screens.add` | call | path: str, name?: str, replace?: bool | - | Copy a PNG screenshot into the workspace's game-screens folder. |
| `screens.remove` | call | name: str | - | Delete one screenshot from the game-screens folder. |
| `preview.live_image` | binary | path: str | - | A screenshot taken by preview.live. |
| `update.status` | call | - | - | Live game against the active version profile: same, catalog_changed (guided flow), tamper (bundle installs blocked) or no profile; plus the stored profiles. |
| `update.profiles` | call | - | - | Stored version profiles (id, build, catalog hash, counts). |
| `update.scan` | call | build?: str | - | Scan the vanilla snapshot into a version profile (tokens, sheets, rules, icon classes, hashes) stored under profiles/. |
| `update.import_profile` | call | path: str, build?: str, catalog_hash?: str, note?: str | - | Scan a folder of stock style bundles of another game build (read-only) into a profile for diffing. |
| `update.diff` | call | old: str, new: str, project?: str | - | Diff two profiles: tokens added/removed/changed/renamed, rules whose selector vanished or moved, sheets, icons, layouts; with a project, a state for each of its items (ok, target moved, target gone, vanilla value changed). |
| `update.autofix` | call | project: str, old: str, new: str | - | Apply the auto-fixable (target moved) items to a project: token renames, rules moved to the sheet that now holds the game's rule, repointed images. |
| `project.new_sheet` | call | project: str, sheet: str | - | Add an empty rule sheet styles/<sheet>.uss for a game stylesheet to a folder project. |
| `project.delete` | call | project: str | - | Remove a project from the list: the folder is moved to <workspace>/trash, not erased. |
| `project.search` | call | project: str, q: str, regex?: bool, case?: bool | - | Find text in a folder project's text files. |
| `project.create_folder` | call | name: str, target?: enum: native | bundles, preset?: str, keep_club_colours?: bool | - | New folder project: empty, or from a preset (written as a folder project with the chosen output from the start). keep_club_colours false turns the club-colour removal on. |
| `native.preflight` | call | project: str | - | What 'Put it in the game' would do, without doing it: the skin's name, what it carries (empty = nothing changed yet), the skins folder, first time or not. |
| `native.put` | job | project: str | - | Put the project in the game as a native skin (job; progress messages are plain words). Refuses a project that changes nothing. |
| `native.remove` | call | project: str, confirm?: bool | - | Take a skin this editor wrote out of the skins folder (only a folder with the editor's marker; confirm must be true). |
| `theme.generate` | call | background: str, accent: str, text: str, mode?: enum: dark | light | - | A theme from three colours, not written: what it writes and keeps, and the contrast check. |
| `theme.create` | call | name: str, background: str, accent: str, text: str, mode?: enum: dark | light, keep_club_colours?: bool | - | Write a generated theme as a native folder project; refused when it fails the contrast check. |
| `theme.gallery` | call | - | - | The gallery themes (inputs only, made by the same generator) with their contrast results. |
| `simple.token_screens` | call | token: str | - | On how many of the measured screens the shipped models hold an area this token paints: {screens, of, names}. Counts only. |
| `share.save` | call | project: str, path: str, studio_version?: str, overwrite?: bool | - | S7: save the skin as one file (a zip of its native skin folder, with the versions inside). |
| `share.inspect` | call | path: str | - | S7: what a skin file holds (name, versions, sheets, pictures, fonts, refused files); nothing is written. |
| `share.open` | call | path: str, name: str | - | S7: a skin file as a new project, through the read-only native import; nothing is put into the game. |
| `project.start_over_preview` | call | project: str | - | S7: what Start over takes away. |
| `project.start_over` | call | project: str, confirm?: bool | - | S7: back to the game's look; the previous state goes to the workspace trash. |
| `simple.pictures` | call | - | - | S6: the game's pictures a native skin can replace (wallpapers and USS-class icons), the wallpaper places, and where Look at it shows them. |
| `simple.literal_info` | call | rgb: str, a?: num | - | What a literal colour swap copies into a native skin: {uses, selectors, copied_rules, limit, offered}. |
| `tokens.browse` | call | used_only?: bool | - | Every colour token the game's rules use (all with used_only false): name, colour, number of rule paths it paints. |
| `app.explain` | call | message: str | - | An engine message in plain words: {plain, details}. |
| `project.migrate` | call | project: str | - | Convert a legacy <name>.skin.json into a project folder (verified round trip; the old file is kept as .migrated). |
| `project.create` | call | name: str, preset?: str | `POST /api/preset` | New project, blank or from a preset. |
| `build.bundles` | job | name: str, allow_overlap?: bool, allow_unknown_impact?: bool | `POST /api/build` | Patch fresh copies of the snapshot; gate; write packages. allow_overlap and allow_unknown_impact are deliberate, recorded overrides of the tile-overlap gate and the unresolved-impact block. |
| `build.reach` | job | name: str | `POST /api/reach` | Check scoped-rule selectors against the game layouts. |
| `build.review` | call | project: str, allow_overlap?: bool, allow_unknown_impact?: bool | - | What a bundle build would do, without writing: per-bundle typed adapter ops, validation findings (the tile-overlap gate), and the dependency-impact policy with buildability and installation readiness reported separately. |
| `edit.adapters` | call | - | - | The typed asset adapters (stylesheet, composition, texture, sprite, font): the editable properties, the limitations and the evidence status of each. |
| `edit.read` | call | install_id?: str, bundle: str, path_id: id | - | One asset read through its adapter (read only): identity, structured summary, fingerprint, properties, limitations, evidence. |
| `install.profile_get` | call | install_id?: str | - | The stored installation profile (build, catalog, integrity files), its problems and how the folder differs now. Read only. |
| `install.profile_select` | call | game_dir?: str, role?: enum: installed | copy | test | production, game_build?: str | - | Describe a game folder and store its profile (nothing is written to the game folder). |
| `inventory.scan` | job | install_id?: str, verify?: bool, max_unverified_days?: int | - | Inventory every bundle of the installation into the registry: size, hashes, uncompressed CRC-32, CAB, objects, dependencies, asset index. Read only, cancellable, incremental. |
| `inventory.status` | call | install_id?: str | - | Bundle counts by state, asset count and the last scan. |
| `inventory.list` | call | install_id?: str, q?: str, state?: str, kind?: str, crc_status?: str, limit?: int, offset?: int | - | The inventoried bundles, filtered, paged. |
| `inventory.get` | call | install_id?: str, path: str | - | One bundle record with its asset type counts. |
| `registry.search` | call | install_id?: str, q?: str, type?: str, bundle?: str, guid?: str, path_id?: id, panel_id?: str, ref_guid?: str, limit?: int, offset?: int | - | Search the asset index by name, type, bundle, GUID, path id, panel id or referenced GUID. |
| `registry.get` | call | install_id?: str, bundle: str, cab: str, path_id: id | - | One asset row by its key (bundle, CAB, path id). |
| `graph.build` | job | install_id?: str, scope?: enum: ui | all, bundles?: list of str, rebuild?: bool | - | Build or refresh the asset dependency graph from the inventory: bundle dependencies, PPtrs through externals, GUID references. Read only, cancellable, incremental. |
| `graph.status` | call | install_id?: str | - | Graph size: bundles by build state, edges by kind and resolution. |
| `graph.uses` | call | install_id?: str, bundle: str, cab?: str, path_id?: id, kinds?: list of str, limit?: int, offset?: int | - | What an asset (or a bundle) uses: edges with provenance, resolution and direct/derived. |
| `graph.used_by` | call | install_id?: str, bundle: str, cab?: str, path_id?: id, kinds?: list of str, limit?: int, offset?: int | - | What uses an asset (or a bundle), including ambiguous references that list it as a candidate. |
| `graph.reachable` | call | install_id?: str, bundle: str, cab: str, path_id: id, direction?: enum: uses | used_by, max_depth?: int, max_nodes?: int | - | Closure over resolved edges from one asset, with cycles and unresolved references listed. |
| `graph.affected` | call | install_id?: str, bundle: str, cab: str, path_id: id, edit_kind: enum: value | reference | identity, new_targets?: list of obj | - | Bundles an edit of one asset requires rebuilding, referrers that are only possibly affected, and what is unknown. |
| `graph.screen` | call | install_id?: str, panel_id?: str, bundle?: str, cab?: str, path_id?: id, max_depth?: int, max_nodes?: int | - | Screen-level UiDocument-style graph of a panel or asset, projected from the registry graph. |
| `catalog.status` | call | install_id?: str | - | The installation's catalog.bin and manifest.dat: identity, parse status, record counts, per-status bundle counts, and whether the stored annotation is stale. Read only. |
| `catalog.annotate` | job | install_id?: str | - | Fill every inventoried bundle's catalog record and manifest.dat columns (read only, cancellable): catalog CRC comparison per bundle and whole-file manifest lookup. |
| `integrity.bundle` | call | install_id?: str, path: str | - | One bundle's complete integrity record: hashes named for what they are, the catalog lookup separate from the CRC comparison, the manifest.dat lookup separate from both. Read only. |
| `install.bundles` | call | name: str, force?: bool, confirm_stale?: bool | `POST /api/install` | Install the latest build with backup and verification. |
| `install.preflight` | call | project: str, install_id?: str | - | What installing the project's latest build would do, without writing anything: package validation, installation identity, per-file target states, integrity warnings and the confirmations needed. Blocked conditions cannot be confirmed away. |
| `install.apply` | job | project: str, install_id?: str, confirmations?: list of str | - | One installation transaction: verified backups, staged and atomically replaced files, post-write verification, durable journal. Cancellable before every destructive step; a cancelled or failed transaction is never reported as completed. |
| `install.history` | call | install_id?: str, limit?: int | - | The installation transactions of the installation, newest first, with recovery-required ones listed separately. Read only. |
| `install.transaction` | call | install_id?: str, tx_id: str | - | One transaction with its per-file operations, approved overrides and rollback state. Read only. |
| `install.rollback` | job | install_id?: str, tx_id: str | - | Roll one transaction back to its exact pre-installation state, verifying every restored file; an independently changed file is never overwritten. |
| `install.recovery_scan` | call | install_id?: str | - | READ ONLY: the unfinished transactions, each assessed against the journal and the actual hashes on disk, with the safe actions and a recommendation. Nothing is modified. |
| `install.recover` | job | install_id?: str, tx_id: str, action: enum: rollback | resume | manual | - | Explicit recovery of one unfinished transaction: rollback, resume (only where proven unambiguous, idempotent) or manual (marks it for a person, modifies nothing). |
| `customlayout.list` | call | - | - | READ ONLY: the screens customised in the game (files in the game's CustomGridCompositions folder, named by the composition) with the badge text and the warning for a bundle layout edit on such a screen. |
| `playground.tile_set` | call | composition: str, project?: str | - | The tiles available in one composition's own tile set (id, description object, configuration sizes): a SwapTile may only use these, plus any project-added sizes/tiles labelled 'added by project (bundle build required)'. Read only. |
| `tiles.descriptions` | call | q?: str | - | B2: list every TileDescription in ui-tileslayouts with its sizes and the UXML GUID each configuration uses. |
| `tiles.element_sets` | call | q?: str | - | B3: list every GridElementSet in ui-tileslayouts and the TileDescriptions it allows. |
| `tiles.add_size` | call | project: str, path_id?: id, description?: str, width: int, height: int, reuse_guid?: str | - | B2: record an add-tile-size project patch op on ui-tileslayouts, reusing an existing UXML GUID of that description. |
| `tiles.set_allow` | call | project: str, action: str, set_path_id?: id, element_set?: str, description_path_id?: id, description?: str | - | B3: record a set-add-tile or set-remove-tile project patch op on a GridElementSet. |
| `customlayout.preflight` | call | project: str | - | READ ONLY: what putting the latest build's custom-layout files into the game folder would do: every file, each file already in the folder flagged (a screen customised in the game) and the confirmations needed to replace it. |
| `customlayout.apply` | call | project: str, confirmations?: list of str | - | One custom-layout transaction: the folder backed up and verified, the files written through a temporary file and hash-checked, a journal kept. Refused unless every replace is confirmed and the game is closed. |
| `customlayout.rollback` | call | tx_id: str | - | Roll one custom-layout transaction back to its exact earlier state: files it created are removed, the user's own files come back byte for byte, a file changed since is never overwritten. |
| `customlayout.base` | call | composition: str, profile?: str | - | READ ONLY: the base custom-layout object for the canvas (the owner's file, otherwise the bundle composition), with every cell in its own space: main design cells and each optional-slice zone, plus the design grid and profile confidence. |
| `customlayout.runtime` | call | composition: str, object?: obj, edits?: list of obj, project?: str, width?: int, height?: int, profile?: str | - | READ ONLY: light runtime placement for the Game Layouts canvas at the active viewport profile (default 2560x1440 fullscreen, Small, Larger; windowed selectable). Returns only the cells and slots with their runtime rects and reasons, runtime problems and per-profile confidence. |
| `customlayout.restore_before` | call | tx_id: str, confirm?: bool | - | Put the game folder back to its state before one transaction, including when the game re-saved a file since Apply: the byte-exact backup comes back, or a file the transaction created is deleted. Without confirm it reports what changed and writes nothing. |
| `customlayout.recovery_scan` | call | - | - | READ ONLY: the unfinished custom-layout transactions, each assessed against the journal and the hashes on disk, with the safe action. |
| `customlayout.apply_edits` | call | project: str, composition: str, edits: list of obj, confirmations?: list of str, runtime?: obj, apply_to_breakpoints?: bool | - | Build a valid custom-layout package from the Game Layouts canvas edits (x/y/w/h in their own space) and apply it through layouttx with a backup and journal. Refused if validation, a replacement confirmation, or the runtime overlap/off-grid check fails. |
| `backup.list` | call | - | `GET /api/backups` | Backup sets. |
| `backup.restore` | call | backup: str | `POST /api/restore` | Restore a backup set, or 'vanilla'. |
| `native.info` | call | - | `GET /api/native/info` | The user skins folder, installed skins, wallpaper places. |
| `native.export` | call | project: str, id?: str, display?: str, dest?: str | `POST /api/native/export` | Write the project as a native skin folder. |
| `launcher.create` | call | confirm?: bool, target_dir?: str | `POST /api/launcher` | Plan or create the macOS launcher. |
| `shell.open_folder` | call | path: str | `POST /api/open-folder` | Open an export or skin folder in the file manager. |
| `layout.state` | call | - | `GET /api/layout/state` | The imported layout dump and its staleness. |
| `layout.scan` | job | - | - | Read the game's own UI bundles (VisualTreeAssets, composition sets and compositions, panel ids) and build/refresh the fmlayout-index/2 dump. Cancellable; a cancelled or failed read imports nothing, and the bundled hashes it records must match the snapshot's reference hashes. |
| `layout.import` | call | data: bytes, name?: str | `POST /api/layout/import` | Import a layout dump (fmlayout-index/2). |
| `layout.screens` | call | area?: str, q?: str | `GET /api/layout/screens` | Screens (panels) with areas. |
| `layout.screen` | call | panel: str | `GET /api/layout/screen` | One screen: layouts, compositions, cells. |
| `layout.outline` | call | layout: int, anc?: list of int, q?: str | `GET /api/layout/outline` | Element outline of one layout. |
| `where.token` | call | name: str | `GET /api/where/token` | Screens and areas a token paints. |
| `where.literal` | call | rgb: str, a: num | `GET /api/where/literal` | Screens and areas a literal paints. |
| `where.search` | call | q?: str | `GET /api/where/search` | Where a class or selector is used. |
| `placement.list` | call | project: str | `GET /api/placement/list` | Stored placement edits. |
| `placement.check` | call | project: str, edit: obj | `POST /api/placement/check` | Validate one placement edit. |
| `placement.add` | call | project: str, edit: obj, confirm?: bool | `POST /api/placement/add` | Store a placement edit. |
| `placement.remove` | call | project: str, id: str | `POST /api/placement/remove` | Remove a stored placement edit. |
| `preview.model_names` | call | - | `GET /api/models` | Names of the measured screens. |
| `preview.models` | call | - | `GET /api/preview/models` | Measured screens with region counts. |
| `preview.evaluate` | call | name: str, project?: str | `GET /api/preview/model` | A screen's regions with vanilla and skin colours. |
| `preview.image` | binary | name: str | `GET /api/preview/image` | A measured screen's screenshot. |
| `preview.suggest` | call | name: str, rgb: str | `GET /api/preview/suggest` | Nearest tokens painting a screen. |
| `verify.screenshot` | call | model: str, project?: str, data: bytes | `POST /api/verify` | Compare an in-game screenshot with the expected colours. |
| `images.catalog` | call | refresh?: bool | `GET /api/images/catalog` | Every texture, icon and SVG in the UI bundles. |
| `images.thumb` | binary | bundle: str, path_id: id | `GET /api/images/thumb` | Thumbnail of one image. |
| `images.source` | binary | project: str, file: str | `GET /api/images/source` | A project's stored replacement. |
| `images.swap` | call | project: str, bundle: str, path_id: id, kind: enum: texture | svg | icon, name?: str, fit?: enum: cover | contain | stretch, data: bytes | `POST /api/images/swap` | Store a replacement image for one slot. |
| `images.swap_file` | call | project: str, bundle: str, path_id: id, kind: enum: texture | svg | icon, name?: str, fit?: enum: cover | contain | stretch, path: str | - | Like images.swap, reading the replacement from a local file path. |
| `images.commit` | call | project: str, bundle: str, path_id: id, kind: enum: texture | svg | icon, name?: str, fit?: enum: cover | contain | stretch, where?: list of str, path?: str | - | Commit the staged edit of one slot in a single write: replacement file (path; omit to keep the stored one), fit and where. Returns the project. |
| `images.preview_file` | binary | path: str | - | A local image file as a PNG preview (for a staged, not yet stored replacement). |
| `images.fit` | call | project: str, bundle: str, path_id: id, fit: enum: cover | contain | stretch | - | Change how a stored replacement is fitted. |
| `assets.conflicts` | call | project: str, target?: enum: native | bundles | - | Conflict report of a project's image swaps: missing files, aspect and size problems, slots the game no longer has, wallpapers on the same place, icons a native skin cannot place. |
| `images.remove` | call | project: str, bundle: str, path_id: id | `POST /api/images/remove` | Remove a swap. |
| `images.where` | call | project: str, bundle: str, path_id: id, where: list of str | `POST /api/images/where` | Native skins: where a wallpaper swap is shown. |
| `images.export` | binary | bundle: str, path_id: id | `GET /api/images/export` | One original at true size (PNG or zip). |
| `images.export_all` | job | group?: str, kind?: str, q?: str, big?: bool | `POST /api/images/export-all` | Export every image matching a filter. |
| `compare.load` | call | path: str | `POST /api/compare/load` | Load another skin (USS folder or bundles) for comparison. |
| `compare.state` | call | - | `GET /api/compare/state` | The loaded comparison. |
| `compare.asset` | binary | file: str | `GET /api/compare/asset` | An image of the loaded USS skin. |
| `compare.thumb` | binary | side: enum: vanilla | theirs, bundle: str, path_id: id | `GET /api/compare/thumb` | Thumbnail of a differing image. |
| `compare.import` | call | name: str | `POST /api/compare/import` | New project from the comparison's colours. |
| `skin.inspect` | call | folder: str, stock_dir?: str, bundles?: list of str | - | Read-only diff of a third-party skin folder against stock bundles, grouped by screen and category. No write path. |
| `skin.preview_composition` | call | folder: str, composition: str, width?: int, height?: int | - | Read-only rea runtime preview of one composition from an inspected skin folder at the pinned viewport. |
| `skin.style_definitions` | call | folder: str, stock_dir?: str, sheet?: str, q?: str, limit?: int | - | Read-only list of classes/rules and variables in an inspected skin's StyleSheet. |
| `styles.injected_get` | call | project: str | - | Read a project's injected rules and variables targeting AlwaysAppliedStyleSheet. |
| `styles.injected_save` | call | project: str, text: str | - | Save AlwaysAppliedStyleSheet USS text and return diagnostics. |
| `styles.import_from_skin` | call | project: str, folder: str, kind: enum: class | variable, name: str, selector?: str | - | Import one class or variable from an inspected skin into AlwaysAppliedStyleSheet, tagged with source. |
