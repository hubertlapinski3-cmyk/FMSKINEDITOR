# Addendum to the v1.1.0 calibration report (written 2026-11-15, after the release)

`calibration-report.md` and `calibration-report.json` in this folder are the report that shipped with v1.1.0 (the release assets are byte-identical to them). They are FROZEN: they are not regenerated into, and this addendum changes nothing in them. It records two wording corrections a second-party audit accepted. **The release assets do not carry these corrections.** A report that does is a new folder with a new freeze, not an edit here.

## 1. Hover on ancestors: read on at most five levels, the rest given by Unity's parent-chain rule

The state rows scored on a real ancestry chain (the `@real-chain` / `@real-ancestry` rows, among them the navigation label's `nav-tab-label-hover@real-chain`) put the element's ancestors in the hover state. The report does not say where that comes from:

- Session G READ hover in the game with `get_styles`, one element at a time, and the saved replies hold the element and at most five ancestors, so a reading covers at most five levels of a chain (24 to 72 elements deep);
- every other ancestor is GIVEN the hover state by Unity's parent-chain rule (an element under the pointer puts all its ancestors in `:hover`). That is a rule the fixture applies (`tools/make_phase_fixtures.py`, `real(..., anc_hover=True)`, and the description it writes on each row), not a reading.

So an ancestor-dependent verdict (the navigation label's `.nav-on-light` finding in particular) rests on the label reading plus a derived hover state on every level beyond the five that were read.

## 2. State chains come from a capture instance: the first of up to 18 matches

Each real chain was found by locating the element in a capture of its screen (`tools/make_state_chains.py`, output `tests/fixtures/render/state-i3-session-g/chains.json`), and where several elements match, the FIRST in capture order is taken. The captures were not taken during the hold, and the screen shows several alike (list rows, tabs), so a chain can come from a different instance than the one the reading was taken on. The matches per target, from `chains.json`:

| target | matches | | target | matches |
|---|---|---|---|---|
| nav-tab-label | 1 | | inbox-row-button | 16 |
| filter-button | 1 | | pitch-marker | 11 |
| loans-tile-button | 1 | | pitch-marker-label | 11 |
| table-row | 16 | | instruction-tile | 18 |

The navigation label (the case in the first item) has exactly one match, so the first-of-several assumption does not touch it; it touches the table row, inbox row, pitch marker and instruction tile rows.

## What did not change

- No number in the report: 638 pass, 80 fail, 410 N/A over 1,128 rows, the 30 variant rows and the 6 layer rows are as shipped.
- The v1.0.0 report folders are untouched.
- Nothing was measured again; both corrections are statements about how the published rows were made.
