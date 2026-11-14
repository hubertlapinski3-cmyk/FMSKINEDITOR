# Phase 9 M8: performance cap, lazy expansion, user docs (2026-11-14), report

Offline, no game time. Engine suite 342 tests (1 skipped), Studio suite 55 tests, `tsc -b` and `vite build` clean.

## The 13 published exceptions to the 200 ms cached budget
Measured on this machine through `Renderer.layout` (warm = second call in the same engine, the cascade built once). "Full" is the old behaviour, "capped" is the new default of 1,000 nodes.

| Layout | Nodes full | Warm full (ms) | Nodes capped | Warm capped (ms) | Payload full to capped (MB) |
|---|---|---|---|---|---|
| DetailedPreferencesBlock | 5,487 | 545 | 994 | 88 | 29.5 to 5.3 |
| GameCreationLoadingScreen | 3,792 | 354 | 996 | 85 | 10.6 to 3.0 |
| IGEEditDetailsBlock | 1,770 | 278 | 986 | 81 | 6.1 to 3.0 |
| GameCreationManagerSelectionScreen | 1,650 | 134 | 991 | 74 | 5.4 to 3.8 |
| NewsTransfersHubSiteHeader | 1,305 | 145 | 910 | 56 | 3.5 to 2.0 |
| PlayerReportHeader | 1,258 | 134 | 966 | 79 | 4.0 to 2.9 |
| ManagerPersonaDetailsScreen_EditMode | 1,119 | 90 | 976 | 74 | 3.4 to 2.8 |
| OnThePitchComparisonMainBlock | 1,000 | 84 | 963 | 74 | 3.0 to 2.9 |
| PhoneDashboardHeaderNavigationTabs | 903 | 70 | 903 | 75 | 3.6 to 3.6 |
| TeamShotMapTile_4x6 | 406 | 42 | 406 | 47 | 2.7 |
| ShotMapTile_4x4 | 392 | 36 | 392 | 37 | 2.4 |
| data_display-graph-shotmap-default | 359 | 27 | 359 | 28 | 1.0 |
| StaffTransferActivityBlock_12x8 | 332 | 23 | 332 | 28 | 0.9 |

All 13 are now inside the 200 ms cached budget (largest 88 ms); the 5,487-element layout renders cold in under 5 s (test). Several of the 13 were over the budget only on a first, uncached call; the table says what a warm call costs. Honest limit: **payload is still 1 to 5 MB** per capped layout, because every node carries its full computed-property list (about 3.9 KB per node, the explain data). Slimming that (explain data fetched per selected node) would change the Studio's data contract and was not done; the cap bounds it. One layout outside the 13 stands out: `PreferencesFMMenuCard` has 266 nodes and a 12.7 MB payload (inlined image data), cheap in time (21 ms warm) but heavy in size; noted, not changed.

## What was built
- **The cap** (`skin_editor/render/cap.py`, wired in `Renderer.layout(max_nodes, open)`): breadth-first, children kept all or none (so a path means the same node in the capped and full tree), applied after layout patches and before the cascade, so only shown nodes are computed. `render.layout` defaults to 1,000 nodes (`max_nodes` 0 = all); the result carries `truncated` {total, shown, cap, collapsed, opened}. The fixtures and library calls stay uncapped.
- **Lazy tree expansion:** a collapsed node carries `collapsed` {children, descendants}; `open: [paths]` expands those nodes, one level each. Nodes under an opened node never use the shared budget, so opening one branch cannot hide another (test). The Studio draws a dashed "show N child elements" button per stub, a banner "N of M elements are drawn" with "draw all" and "back to the capped view", and keeps the selection when a branch opens.
- **Error boundaries:** already in place (`Guard` around each view in `App.tsx`, M6); the Render view is inside it. No new work.
- **A type error found and fixed:** `tsc -b` (the first step of `npm run build`) failed on `RNode.matched[].origin`, which the M6 explain panel uses but the type did not declare; vitest does not type-check, so it went unseen until now. Fixed; the build is clean.
- **User docs:** `docs/RENDER-GUIDE.md` (what the render shows, large layouts, what it does not do, how far to trust it, engine calls), a README section, and `docs/API.md` regenerated from the method table (it listed 108 methods; the table has 111, and `render.rule`, `render.table`, `render.screen` were missing).

## Tests added
`tests/test_cap.py` (8: cut rules, path stability, open moves nothing else, two-level opening, zero cap, the 13 inside the budget, the largest layout capped and opened, a small layout untouched), one RPC test (default cap, `open`, `max_nodes` 0), three Studio tests (banner and open by path, draw all and back, no banner and no extra parameters for a small layout).

## Named gaps carried
Payload slimming (explain data per selected node); `render.screen` and `render.table` have no Studio view; a node with thousands of direct children opens all at once.