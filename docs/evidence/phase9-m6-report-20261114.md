# Phase 9 M6: the side panel, click to rule to token and back (2026-11-14), report

Offline, no game time. Engine suite 323 tests (1 skipped), studio suite 52 tests, type check clean.

## Pre-work the owner asked for
1. **Tile move, end to end through the real path** (`tests/test_tile_move_e2e.py`): the real 33 MB layout dump imported into a temporary workspace; `placement.check` finds the move collides with FirstTeamOverview, `placement.add` without `confirm` is refused and stores nothing, with `confirm` it is stored and fires exactly one `render.invalidate` (`tile-move`); `tiles.ops_for` builds the `move-cell` op; `render.screen` with the skin on puts Atmosphere at column 22 row 8 (moved by the project, px left 1816) and with the skin off at the game's column 26; Tactics is identical either way; `placement.remove` fires one event and the cell is back. Only the write-freshness gate (it compares the dump with the installed game's reference hashes and guards writing to the game) is stubbed, stated in the test.
2. **RPC coverage of the editor endpoints the panel calls** (`tests/test_panel_rpc.py`, real game data, temporary workspace with its own small vanilla snapshot): L `layouts.edit` / `layouts.unedit` (one `layout-patch` event with the layout name as scope; the class shows in the next render; vanilla toggle clean), V `tables.edit` / `tables.unedit` (one `table-edit` event; `render.table` follows, vanilla keeps the column), USS `uss.diagnostics` + `project.new_sheet` + `project.write_file` (one `file` event; the rule paints the Loans button `#00FF00`), tokens `tokens.get` + `project.save` (one `tokens` event; `#FF0000`).

## What M6 added
**Engine.**
- Provenance: a rule the overlay appends carries `origin {kind, sheet, selector}`; it flows through the compiled sheets into every node's `matched` list and into each declaration's `source`.
- `render.layout` with a project returns `origins`: for every project rule that matched an element, its file, first and last line and the cascade rule ids it corresponds to; and for every token the project overrides, its line in `styles/tokens.uss`.
- New method `render.rule` (sheet, rule, project, skin): the rule as USS text; a game rule is `vanilla: true` with no origin (read-only), a project rule gives its file and line.

**Studio, element -> rule -> token.** The explain panel's matched rules and each property's winning source are clickable and open the rule as USS text: a project rule offers "Open <file>:<line> in the editor"; a game rule shows read-only text and "Override in <project>" (adds a scoped rule with the same selector and declarations through `project.save`, then opens the file). Every token in a property's chain is a chip that opens the token: its alias chain, value, definitions per sheet, and either "Open the project's override" at its line or a value box and "Override in <project>".

**Studio, USS editor -> element.** The editor's caret position is matched against the last render: when it sits inside a project rule, a bar says how many elements that rule styles; when it is on a `--token`, how many elements it paints; "Show in render" switches to the render view with those elements outlined. (Rule -> elements uses the cascade rule ids in `origins`; token -> elements uses each property's token chain.)

## Verification
| Direction | Verified by | Result |
|---|---|---|
| element -> project rule (file, line) | RPC test on real data: the winning `background-color` source has the origin; `origins.rules` gives `styles/AlwaysAppliedStyleSheet.uss` lines 2 to 4; `render.rule` returns the text and file:line | pass |
| element -> game rule | RPC test: a matched game rule is `vanilla`, origin null, text returned | pass |
| rule -> elements | the origin's ids contain the winning rule's id; studio test `rulePaths` | pass |
| token -> project override line | RPC test: `origins.tokens` line holds the token in `styles/tokens.uss` | pass |
| token -> elements, caret helpers | studio tests `tokenPaths`, `ruleAtLine`, `tokenAt` | pass |
| panel actions | studio tests: open at line, override a game rule (`project.get` + `project.save` with the scoped rule), token chain, open and set a token override, highlight outline | pass |
| flagged properties | the status badges and "flagged only" filter are kept; the old explain test still passes with the token chain as chips | pass |
| repaint on change | M5's `render.invalidate` subscription redraws the view after every override the panel makes | pass at the M5 level |

## Not verified, stated
- The caret bar and the view switching in `App.tsx` (editor <-> render) are exercised through their helpers and the type check, not by a UI test of the whole app; the Monaco editor is not mounted in any test.
- Overriding a game rule copies ALL its declarations; a declaration with a hidden name (`-unity-id-N`) is refused by project validation and the error is shown, not worked around.
- A legacy single-file project (no `styles/` folder) has no file to open: its rules show no origin.

## The structural template path (`Binder.ToString()`): did it earn its place?
No, and it was not wired. The panel's click targets are render nodes, which already carry their layout name and element id, so there is nothing to pair. The path pairs LIVE elements with layout nodes: it belongs to the live-compare work in M7's fixtures (and to any future "click in the game" feature). Kept as a named item for M7.

## Status
M6 built and verified at the levels above. Next: M7, the fixture framework: all six calibration fixtures, the geometry table and a published pass/fail report, with the Atmosphere and Training tiles in the fixture plan and the structural path considered for the live pairing.