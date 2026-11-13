> SUPERSEDED by `fmlayout-index-2.md`. The app refuses `fmlayout-index/1` dumps. Kept for history only.

# Layout dump contract: `fmlayout-index/1`

One JSON file produced by an external, read-only indexer. The app reads it and never writes it. The app does not depend on the indexer at runtime, only on this file. `python -m skin_editor check-layout DUMP.json` validates any file against this contract and prints counts per section; it is also the contract test for the exporter.

Validation is strict: unknown top-level keys, unknown record keys, wrong types, duplicate ids and dangling references are all rejected, and a rejected file is never partially loaded. Integers are JSON integers (booleans are not integers). Names and ids are case-sensitive. Maximum file size 256 MB.

## Top level
Exactly these keys, all required: `meta`, `areas`, `layouts`, `elements`, `includes`, `panels`, `tiles`, `compositions`, `cells`, `cell_configs`.

### meta
| key | type | rule |
|---|---|---|
| `schema` | string | must be exactly `"fmlayout-index/1"`. Any other value (including `/2`) is refused. |
| `game_build` | string | required, non-empty. Compared with the vanilla snapshot's build: the staleness signal. |
| `index_fingerprint` | string | required, non-empty, opaque to the app. Used only to tell whether a re-imported dump differs from the previous one. The exporter's method is per-table row count plus sha256 of the rows. The app shows its first 12 characters. |
| `exported_at` | string | required, non-empty (ISO 8601 recommended). |
| `runtime_classes_provenance` | string | required, non-empty, if any element carries `runtime_classes`: how the observations were made (tool, game build, screens visited). Optional otherwise. |

### areas
`{"map": {layout_name: area}, "anchors": [anchor, ...]}`. The app trusts `map`; `anchors` are informational (how the map was derived).
- `map`: layout name -> non-empty area string. Every key must be the name of a layout in `layouts`. Layouts not in the map are `unassigned`.
- anchor: `{"area": string, <selector>}` with exactly one selector key: `layout_name` (exact match), `layout_name_suffix`, `element_name`, or `element_class` (string). Most specific area wins when anchors overlap; unclaimed layouts are unassigned.

## Sections (each an array of objects; all listed keys required unless marked optional)
- `layouts`: `id` int (unique), `name` string, `guid` string (32 lowercase hex), `bundle` string. Names may repeat; ids may not.
- `elements`: `layout_id` int, `local_id` int, `parent_local_id` int or null, `ord` int, `type` string, `name` string (may be empty), `classes` array of string (static classes in the layout), `runtime_classes` array of string (**optional**). `(layout_id, local_id)` unique; `parent_local_id` must be null or an element of the same layout.
- `includes`: `from_layout_id`, `element_local_id`, `alias` string, `to_layout_id`. The element must exist in the from-layout.
- `panels`: `panel_id` string (unique), `layout_id`.
- `tiles`: `panel_layout_id`, `set_name` string, `breakpoint` int, `variant_idx` int, `composition` string, `cell_index` int, `cell_element_id` string, `cfg_index` int, `size` `{w, h}` (positive ints, grid units), `tile_layout_id`. The composition and `(composition, cell_index)` must exist.
- `compositions`: `name` string (unique), `layout_mode` string, `preset_name` string, `preset_w` int, `preset_h` int (both >= 0), `instantiation_order` array of int, `conditions` array of string (displayed verbatim, opaque to the app).
- `cells`: `composition` string, `cell_index` int, `element_id` string, `x`, `y` int (>= 0), `w`, `h` int (> 0), `min_w`, `min_h`, `max_w`, `max_h` int (>= 0, min <= max, all <= 100000), `flags` array of string, `h_align` string, `v_align` string. `(composition, cell_index)` unique; the composition must exist.
- `cell_configs`: `composition`, `cell_index`, `cfg_index` int, `size_w`, `size_h` positive ints, `tile_layout_id`. `(composition, cell_index, cfg_index)` unique; the cell must exist.

## Class evidence: three states
For a class named by a style rule:
1. **verified**: it appears in `classes` of at least one static element record.
2. **runtime-observed**: it appears in `runtime_classes` of an element and in no static record. Shown with that label, never counted as verified, never dropped. The field is present only where observation actually happened; an absent field means no observations were made for that element.
3. **unverified**: it matches neither (runtime-added or code-driven, or simply unused).

## Cell flags
Only `locked` has app behaviour (a move or resize is refused). Any other flag is carried and displayed, and never blocks.

`locked` blocks geometry, not config choice. This is deliberate: the flag exists to stop a cell from being moved or resized, and selecting one of the cell's own configs (`cfg_index`) is not a move. A locked cell therefore still accepts a config selection; it refuses any change to `x`, `y`, `w` or `h`.

## Limits (stated in the app)
The dump has no geometry and no template/table-factory (attribute) references. Screens reached only through such references are not covered, so any "where it paints" result is a lower bound. A future `attr_refs` section would be a contract version bump; nothing is designed for it now.

## Staleness
The app compares `meta.game_build` with the vanilla snapshot's `game_build`: equal = fresh, different = stale (prominent warning, layout features marked possibly stale), no snapshot or no build recorded = unknown. The fingerprint is never compared with anything but the previous dump ("dump changed" reporting).
