# Phase 6 spike: TextCore FontAssets on the bundle route (report only, no build work)

Game 27.0.1.2503222 (inspector `status`, 2026-11-13), UnityPy 1.25.4, Unity 6000.3.18f1. Everything below was read from the game's own bundles
or produced as a scratch copy outside the game and the project; nothing was installed.

## What the game ships

All 34 FontAssets in the ten `ui-fonts_assets_*.bundle` files (production 21 MB, fifa_worldcup 5.5 MB, the rest under 1 MB) are the same kind:

| | |
|---|---|
| population mode | **dynamic** (`m_AtlasPopulationMode = 1`) for all 34 |
| source font | the TTF/OTF is **inside the same bundle** as a `Font` object (`m_FontData`, e.g. ABCSocial 122 KB, NotoSansJP 5.7 MB, EFL1888Pro is OpenType CFF, header `OTTO`) |
| atlas | one or more Alpha8 textures, 1024x1024 (2048x2048 for the CJK fonts), **`m_IsReadable = true`**, `m_ClearDynamicDataOnBuild = 0` |
| SDF settings | render mode 4165 (SDFAA), padding 9 (5 and 2 for CJK), material `_GradientScale = 10` (padding + 1) |
| baked content | glyph and character tables already hold the glyphs used when the asset was built (4 to 1109 glyphs) |
| fallbacks | `m_FallbackFontAssetTable` exists on each asset (the FIFA World Cup asset inspected has one entry); the chains were not traced |

How a family is chosen: `--typography-family-primary` is an asset reference to `ABCSocial-Regular SDF` (production bundle), `--typography-family-condensed`
to `ABCSocialCondensed-Regular SDF`, `--typography-family-thematic` to `FMUniverse-Regular SDF` (fmuniverse bundle), `--typography-family-international`
to `NotoSans-Regular SDF`. The many `--body-md-family`, `--heading-xl-family` ... tokens are `var(--typography-family-primary)` aliases. 25 tokens
reference a FontAsset directly. A native skin replaces such a token with `url("fonts/x.ttf")` (the route Jonukas uses and Phase 6 now exports).

## Routes for the bundle target

**A. Repoint a family token to a FontAsset the game already has.** Exists today: `token_patch.SheetPatcher` has a `font_tokens` option that writes an asset
reference to another `... SDF` object found in a fonts bundle. Works for the 34 shipped fonts, adds no objects. Cannot bring a new typeface.

**B. Put a new font into an existing FontAsset (replace its source `Font`, reset its tables).** Because the assets are dynamic and keep their source font and a
readable atlas, TextCore can in principle regenerate glyphs for a different font at run time. What UnityPy can do, shown on a scratch copy of
`ui-fonts_assets_efl.bundle` (never installed):

- replace `Font.m_FontData` (63,312-byte OpenType) with Impact (206,784 bytes), `save_typetree` on the Font object: reads back byte-identical;
- empty `m_GlyphTable`, `m_CharacterTable`, `m_UsedGlyphRects` and reset `m_FreeGlyphRects` on the FontAsset: reads back with 0 glyphs, 0 characters;
- zero the Alpha8 atlas through `Texture2D.image = RGBA(alpha = 0)` then `save()` (UnityPy encodes Alpha8 from the alpha band; a mode `L` image is refused): reads back 0;
- object set unchanged; exactly 3 objects differ from vanilla (the FontAsset, its atlas Texture2D, the Font), the same shape the gate already checks for image swaps
  (object set equal, untouched objects equal, only the touched ids differ). The 7,467 VisualTreeAssets write the same way once UnityPy's writer is fixed for the
  null managed reference (done in `uxml.py`); FontAssets need no such fix.

What is not known and needs one in-game experiment: whether FM27 lets TextCore repopulate these assets at run time (some games clear dynamic data on load or
rely on the baked tables), how line metrics should be updated (`m_FaceInfo`: units per em, ascent, descent, line height, cap line, mean line from the new
font's `head`/`hhea`/`OS/2` tables, which means reading those tables; `fontTools` is not installed, they are simple enough to parse by hand), and whether the
fallback chain behaves for characters the new font lacks.

**C. Create a new FontAsset (new FontAsset, Material, atlas, Font objects).** UnityPy has no supported way to add objects to a serialized file; it would also need
`AssetBundle.m_Container`, dependency lists and Addressables catalog entries, and a changed `catalog` is what the tamper check treats as a game update. Not worth it.

**Pre-baking the atlas ourselves** (only if B's run-time regeneration does not work): Pillow rasterises through FreeType, numpy is available (scipy, freetype-py and
fontTools are not). A brute-force signed distance transform with the 9 px spread at atlas scale costs about 5 ms per 130x130 glyph in numpy (62 Latin glyphs in
0.3 s), so a Latin set bakes in well under a second; a CJK set of a thousand glyphs would be seconds to a minute (estimate, not measured). The remaining work is glyph packing into the atlas
(a shelf packer), the glyph table with metrics, and the SDF value convention (128 = edge, scaled by the spread). Feasible, roughly 2 to 3 days, all in Python.

## Verdict

- **Native route: done and the right default.** A font file plus a token set to `url()`; no FontAsset generation.
- **Bundle route, route B: feasible, medium risk, one experiment away from a yes or no.** Everything the build and gate need can be written with the tools already
  in the project. The single open question is the game's run-time behaviour with a swapped source font.
- **Route C: no.**

## Proposed experiment (not run; needs your go-ahead because it installs a modified bundle)

1. Scratch build only the smallest asset: `ui-fonts_assets_uefa_supercup.bundle` (0.1 MB, `UEFASupercup_Reg SDF`, 21 glyphs) with its source font replaced and tables reset.
2. Install it through the existing install path (backup, process check, tamper check); find a screen that uses that family (UEFA Super Cup competition pages).
3. Success: text renders in the new font, no log errors, other fonts unchanged. Failure modes to record: blank text (no regeneration), old glyph shapes with new metrics.
4. Restore from the backup afterwards (hashes verified).

If it passes, the product work is: a `font_replace` op in the layout of the existing build (project file `fonts/` + mapping entry with target FontAsset path id), metrics from the font tables,
a gate that checks object set equal and only the three objects differ, and a plan line. About three to four days. If it fails, the pre-baked atlas above is the fallback.

## In-game evidence, native `url()` route (2026-11-13, build 27.0.1.2503222)

Skin `p6-font-test` (`--typography-family-primary: url("fonts/impact.ttf")`, the file byte-identical to `C:\Windows\Fonts\impact.ttf`), selected by hand in
Preferences, Reload Skin, 10 s wait:

- **Rendered:** body and secondary text changed from the stock rounded sans to a condensed bold face (the narrow "Game Date" cell overflowed). Headings, which use another family, did not change.
  Screenshots `font-0-start`, `font-2-p6-reloaded`, `font-3-mine-restored` (ui-dumps/screens). Switching back to Mine restored the original text exactly.
- **Log:** `Player.log` carried **217 lines** `impact FontAsset is invalid. Please assign a Source Font File.` The game built a dynamic FontAsset named `impact` from the .ttf
  and drew with it, but the asset it generated has no Source Font File assigned.
- **Reading:** the dynamic path (the native `url()` route) works. The warning points at what the bundle route would need: a FontAsset **with its Source Font File set**. This feeds the
  experiment above, step 1: the replaced font must be assigned as the FontAsset's source (and the atlas tables reset), not only copied next to it.
- **Not measured:** the inspector's `fm_get_styles` has no font-family field, so the computed family was not read; the evidence is the screenshots plus the rule.

**Backlog (kept open):** (1) the "FontAsset is invalid" warning, whether it is cosmetic or costs something (glyph fallback, missing characters); (2) the FontAsset experiment on
`ui-fonts_assets_uefa_supercup.bundle`, now with the extra condition that the Source Font File must be assigned.

## Licensing note

Fonts are the user's responsibility; the editor copies the file the user picks and never ships one.
