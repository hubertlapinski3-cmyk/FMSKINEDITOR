# Phase 9 M5: project overlay and the vanilla/skin toggle (2026-11-14), report

Offline, no game time. Engine suite 318 tests (1 skipped), studio suite 48 tests, all passing.

## What was built
- **`skin_editor/changes.py`, `render.invalidate`.** Every place a project can change records `(project, reason, scope)`; the API dispatcher (`api/methods.call`) wraps each call in a batch, so ONE `render.invalidate` event per project leaves a call whatever it touched: `{project, reason, reasons, scope}` (reason `multiple` when one call changed several kinds). Reasons: tokens, rules, layout-patch, tile-move, table-edit, font, image, file, options. Hooks: `project.save` (what differs from the stored model, so an identical save fires nothing; layout and table patches carry the layout/view names as scope), the project file API (`write_file`, `delete_file`, `new_sheet`), native import, legacy migration, project create and delete, and the tile placement store. The engine publishes the event and drops the render's cached skin cascade for that project.
- **`skin_editor/render/overlay.py`, the overlay.** `render.layout` takes `project` and `skin`; `skin: false` is the vanilla game whatever the project holds. Edits are applied to in-memory COPIES (the vanilla bank is never modified, tested):
  - token overrides, literal swaps (rgb-keep-alpha and exact rgba) and scoped rules (replace, remove, append) from `project.to_spec`, the spec the build uses. Output `bundles`: applied in the named game sheet. Output `native`: the game's sheets stay as shipped and one author sheet, last, carries the tokens as `:root` plus the appended rules; replace/remove edits do not exist in a native skin and are reported as notes, not drawn;
  - layout patches (set-classes, set-inline, set-attr) applied to the render tree before the cascade, by element id AND the layout the element came from (an included template's element is patched under its own layout name); a guard mismatch or a missing element is skipped and reported, as the build refuses it;
  - the cascade with a project's edits is cached per project and rebuilt when the project's content hash changes.
- **Tile moves:** `screen.Assembler.place/assemble` take the project's move-cell ops (`tiles.ops_for`); a moved cell keeps its anchoring judged on its design position and is marked "moved by the project"; new method `render.screen` (composition, grid container size, project, skin).
- **Table edits:** `overlay.table_placeholder` and method `render.table`: a labelled placeholder table whose header row is the view's column order, with the project's column edits applied through `tables.apply_to_view` on a copy; a stale op shows the vanilla columns and says why.
- **Studio:** the Render view gets a "skin: <project>" toggle (on draws the open project, off draws the game as it ships), repaints on every `render.invalidate` of the open project (not another's), and lists the overlay's notes and what is not applied.

## Exit check (what was verified, how)
| Edit | Verified by | Result |
|---|---|---|
| Token edit | real Loans tile: the button's background `#1E2129` becomes `#FF0000` through the token `--colours-ui-soft`; without the project it is `#1E2129` again; `invalidate` rebuilds | pass |
| Appended rule, replace, remove | overlay unit tests on a two-sheet bank (appended last, replaced in place, property removed, bank untouched) | pass |
| Class patch, inline patch | real Loans tile: a class brings its rule from the game's sheets, an inline height wins and says it is inline, vanilla unchanged without the project | pass |
| Tile move | assembler tests (position, anchoring, other compositions ignored) | pass at unit level; NOT run end to end through a real placement store and layout dump |
| Table edit | real game table view: a hidden column leaves the placeholder header row, vanilla keeps it | pass |
| One invalidate per edit | `project.create_folder`, `project.save` (two kinds changed together: one event, reason `multiple`), a no-op save (none), `write_file`, `delete_file`, `new_sheet`, `delete`; per-editor reasons for layout, table, font, tokens, rules, options; the placement store writes `tile-move` | pass; `tables.edit`, the L view and `placement.add` endpoints are covered through `project.save` and the placement write, not each called through RPC |
| Toggle repaints | studio tests: toggle on/off sends `skin` true/false; an event of the open project repaints, one of another project does not | pass |

## Not applied, said in every result (`overlay.not_applied`)
Class renames; image and font swaps; the bundle route's `raise_specificity` option (rules are appended as written); native-route literal swaps are applied to the copied game sheets rather than emitted as author rules (the drawn result is the same). `multiple` as a reason value goes beyond the plan's list and is documented in `changes.py`.

## Status
M5 built and verified at the levels above; the end-to-end tile move and the per-endpoint RPC checks for the L, T and V editors are the remaining thin spots, listed rather than claimed. Next: M6 (side panel: click -> rule -> token chain, both directions with the USS editor).