# Milestone E: writing tile placements into bundles (report only, no code)

Status: exploration. Nothing here is implemented. Nothing becomes implementation without a separate confirmation on this report.

## 1. What is established and what is not

Established (measured on the Windows install, from the layout index built earlier):
- Composition data (cells, positions, min/max sizes, flags, configs) lives in three bundles: `ui-tileslayouts_assets_all.bundle` (1,697 compositions, 654 composition sets), `ui-tactics_assets_all.bundle` (53 compositions, 27 sets) and `ui-dynamiccardcollections_assets_all.bundle` (73 compositions, no tile references found in the index).
- Tiles reference compositions in the first two only: 1,293 in tileslayouts, 38 in tactics.
- The skin editor already installs modified bundles (the two style bundles) with backup, rehash and rollback, and skins built this way loaded in game. So the game accepts a changed bundle file in place for styles.
- Cell size and configs are coupled in the data: of 5,162 cells that have configs, 4,724 have a cell size equal to one of their config sizes (4,634 equal to exactly one). 94 cells have more than one config.

Not established (no write of composition data has ever been attempted):
- Whether the game honours a changed `m_location` or size, or clamps, ignores or re-derives it (for example from the config).
- Whether other layers override stored geometry at runtime (conditions on compositions, instantiation order, code-driven layout).
- Whether Addressables verifies CRC or hash for these bundles. Styles worked, which is suggestive, not proof for other bundles.

## 2. What writing placements requires

1. A vanilla snapshot of the composition bundles, read-only like the style snapshot. Builds start from a fresh copy of it, never from the installed file.
2. A typetree-aware writer: load the bundle with UnityPy, find the MonoBehaviour by composition name and path id, change the cell's location (and, if allowed, size or config selection), save with the original compression. The exporter's dump already gives the stable key (composition name plus cell index); the writer must re-resolve it against the snapshot and refuse on any mismatch.
3. A target mapping from the stored edit (composition, cell_index, new x/y/w/h) to the exact serialized fields. Edits stay validated by the existing hard-block and warning rules; the writer adds a second check against the snapshot, not only the dump.
4. Build report change: `layout_placement` moves from "stored, not yet written" to a per-edit written, skipped or refused state with reasons.
5. Install: extend the changed-bundle set beyond the two style bundles. The existing backup, process check, rehash and rollback apply unchanged; backups grow by the new bundles.
6. A stale-dump rule: an edit is only written when the dump fingerprint and game build match the snapshot it was validated against.

## 3. Snapshot expansion: size and time

Size (measured file sizes):
- Placement writes need only the composition bundles: tileslayouts 911 KB + tactics 40 KB = about 951 KB. Adding dynamiccardcollections (66 KB) only if its compositions are ever editable: about 1.02 MB.
- The current snapshot is the two style bundles, 1.43 MB. Expansion is therefore about +0.95 to +1.02 MB, roughly +70%. Small. Backups per install grow by the same amount.
- Layout (UXML) bundles are not needed for placement writes. They matter only to the exporter, which stays outside the app.

Indexing time:
- Not measured in this session, so I will not give a number. The data is about 1 MB across about 4,200 MonoBehaviours (tileslayouts); parsing typetrees with UnityPy is expected to be seconds, not minutes. The app does not index at all: it needs the snapshot bytes plus a lookup by name, which is cheaper still. A timing run is the first thing to do if this is approved.

## 4. Bundle files a placement write touches

- `ui-tileslayouts_assets_all.bundle`: nearly all placement edits (screens other than Tactics).
- `ui-tactics_assets_all.bundle`: edits to the Tactics compositions.
- `ui-dynamiccardcollections_assets_all.bundle`: only if edits in those compositions are ever allowed. Recommended out of scope for the first step.
- Possibly the Addressables catalog (`catalog.bin` and `catalog.hash`, hash currently dfa1892e...) if bundle hash or CRC checking turns out to be enforced for these bundles. Style installs did not need it. Unconfirmed for the new bundles; the verification loop below tests it.
- Not touched: style bundles, layout (UXML) bundles, panel ids, table factories.

A single edit rewrites a whole bundle file, so the unit of install is the bundle, not the cell.

## 5. In-game verification loop

Per attempt, on the throwaway Dortmund save only:
1. Build from the fresh snapshot with one edit (a small, unambiguous move on a Tactics tile).
2. Install with backup and the process check (game closed).
3. Launch, open the save, navigate to the screen using the click bridge.
4. Read the live UI tree with the inspector (`fm_dump_tree`, `fm_describe`) and compare the tile's rendered position and size with the edit's expectation; take a screenshot as evidence. Whether the inspector exposes resolved element bounds in the units needed is unchecked and must be confirmed first.
5. Pass if the tile moved as specified; record a result of moved, clamped, ignored or crashed per edit.
6. Roll back from the backup and confirm the file hashes match vanilla.

Order of trials: (a) a no-op rewrite (open, save, install with zero changes) to prove the writer and the game tolerate a re-serialized bundle; (b) a move within the grid; (c) a resize within min/max; (d) a config selection; (e) a collision; (f) a locked cell (expected to be refused before reaching the writer). Each trial answers one of the unknowns in section 1.

## 6. Risks

- Game ignores or clamps the change: the feature would show edits as written while the screen does not change. Mitigation: the verification loop decides this before any UI says "written".
- Config and size coupling: a size that matches no config may be reset by the game, or may break a tile that expects one of its configs.
- Re-serialization fidelity: UnityPy rewriting a bundle may change compression, ordering or other bytes the game cares about. The no-op trial (a) isolates this.
- Hash or CRC enforcement and the catalog: could make the game reject the bundle or trigger a re-download. Unknown for these bundles.
- Steam updates and Verify Integrity overwrite the bundles, silently reverting edits or invalidating the snapshot. Handled by the existing game_build and fingerprint staleness gate, but the edits would need a re-check after every update.
- Wider blast radius than skins: a bad composition can hide or break an entire screen, not just recolour it. A tile off the grid might make a screen unusable in a save.
- Save compatibility: layout data is presumably not stored in saves, but this is unverified.
- Multiplayer or online implications and any integrity checks: unknown, and out of scope for a throwaway save.
- Maintenance: composition structure may change per game build; the writer must refuse on any unexpected typetree shape rather than guess.
- Scope creep: moving from "stored" to "written" changes the promise made to the user; the UI must keep the distinction explicit.

## 7. Recommendation (for the confirmation decision)

If approved, the safest first step is a spike with no UI: a script outside the app that performs trials (a) and (b) on a copy, installs with the existing backup tooling and checks the result with the inspector. It would answer the unknowns in section 1 with evidence before any app code is written. Nothing above should be built until that spike shows the game honours the change.
