# Phase 6 evidence (2026-11-13, game 27.0.1.2503222)

Status of the exit criteria: **FontAsset spike report delivered** (`docs/PHASE6-FONTS-SPIKE.md`); **class edits seen in game** and **native fonts seen in game** are
the user's checks, prepared below. Everything else was verified here, offline.

## UXML read

- 7,467 VisualTreeAssets in 6 `ui-visualtreeassets_*` bundles (init 4, intro 64, fantasy draft 69, match 244, global 2,005, game world 5,081 layouts); 114,772 VisualElementAssets,
  14,658 TemplateAssets, 6,004 UxmlObjectAssets; element ids are unique inside every layout (0 duplicates); every layout points at its own inline StyleSheet (`inlineSheet`, named
  `inlineStyle`, rules without selectors) and 42,112 elements carry a `m_RuleIndex` into it. Included templates resolve by alias (`m_Usings` alias = the included layout's name).
- `skin_editor/uxml.py` + methods `layouts.list`, `layouts.tree`, `layouts.class_usage`; Studio view **L**: layout list with filter, element tree (templates expandable one level), inspector
  (type, name, id, classes, inline style, set attributes, bindings read-only), where-is-this-class-used (layouts with element counts, plus the style rules that mention the class, from the style index).
  The class index over all layouts is built in one pass and cached (0.9 s warm for `layouts.list`).

## The write risk, retired first

UnityPy 1.25.4 cannot write a VisualTreeAsset back as it stands: its typetree writer crashes on the null managed reference every layout starts with (`rid -2`, no `data`; the reader
skips it, the writer does not). `uxml.fix_unitypy_writer()` makes the writer skip it the same way. Result on the real bundles: rewriting **all 7,467 layouts unchanged** gives a bundle whose object set
and every object digest equal vanilla (0 differing objects, 5 bundles + init); one class edit changes exactly one object. This is a test (`tests/test_uxml.py`, runs when the game is installed).

## Patches

Per-layout files `layouts/<Layout>.patch.json` in the project: `set-classes` (add/remove), `set-inline` (properties through the existing StyleSheet encoder, pools append-only; an element without an
inline rule gets a new selector-less rule and its `m_RuleIndex`), `set-attr` (only attributes present in that element's serialized data, same value type, `<attr>_UxmlAttributeFlags` set to 1; names, bindings,
templates, ids and data sources are refused). Addressed by element id with a type/name guard; a mismatch or a vanished id refuses the build with a message. No op can add, remove or move an element.
Bundle target only: a native build drops them and says why (plan: `dropped`). Gate (`uxml.check_patches`): the built layout equals the vanilla layout plus exactly the asked-for edits (every other
field of the layout, every other element and serialized-data entry, every other inline rule compared field by field), the inline sheet has the expected rule count, the standard untouched-object and
pool append-only checks still run, object set equal.

Real build on the vanilla snapshot (project `p6-class-test`, bundle target): layout `PreferencesFMMenuCard`, element `VisualElement#reload-skin-button` (id 685404427) gets the class `p6-loud`, plus a rule
`.p6-loud { background-color: #FF00FF }` appended to AlwaysAppliedStyleSheet. Build 7.4 s, **gate: 0 failures**, `layout_patches_checked: 1`, `appended_rules_checked: 1`, untouched bundles checked 2,
changed files: `ui-styles_assets_default.bundle` and `ui-visualtreeassets_assets_globalvisualtreeassetpreload.bundle`. Build output: `build/p6-class-test/20261113T152749Z`. Not installed.

## Native fonts

The exporter now writes fonts: the project has `fonts/`, a mapping entry `{"mode": "font", "target": {"token": ...}}`, the export copies the file to `fonts/<file>` in the skin and writes
`--token: url("fonts/<file>")` into `tokens.uss`; the native gate (`validate`) checks that every `url()` resolves inside the skin folder, and a font file missing from the project or a url rule that was not
written is reported as a problem. Plan: `WriteFont` (native) or a dropped item pointing at the spike (bundles). Methods `font.tokens`, `font.set`, `font.remove`; Studio: FONTS section of the Images view.
Project `p6-font-test` (native): `--typography-family-primary` -> `C:\Windows\Fonts\impact.ttf`, exported to `Documents\Sports Interactive\Football Manager 27\skins\p6-font-test` (display name
"P6 font test"), 0 problems.

## For the in-game checks

1. Class edit: Studio > project `p6-class-test` > Build bundles (gate must pass) > Install build (game closed) > open Preferences: the row around "Reload Skin" and the skin chooser should be magenta.
   Then Restore stock. (The same edit is also visible in the Layouts view, the edited element has a dot.)
2. Native font: in the game, Preferences > skin drop-down > "P6 font test" > Reload Skin: all text that uses the primary family (most of the UI) should render in Impact.
   If nothing changes, tell me what the log says; the url() route is the one the Jonukas skin uses, but this token and this build are unproven for it.

## Not done / carried over

- Item states for layout patches in the update diff (needs layouts in the profile; closes with the icon/layout diff at the next patch).
- Install and Restore buttons were added to the Studio Build panel (they call the existing, tested `install.bundles` and `backup.restore`); not exercised from the UI here.
- FontAsset route B is an experiment away (see the spike); nothing was built for it.

## In-game results (reported by the user, build 27.0.1.2503222, 2026-11-13)

- **Exit criterion 1, class edit: MET.** Project `p6-class-test` (layout `PreferencesFMMenuCard`, element `reload-skin-button`, class `p6-loud` + rule `.p6-loud { background-color: #FF00FF }`):
  the gate passed, the build was installed with the game closed, and magenta was seen around the Reload Skin row and the skin chooser in Preferences. Screenshot evidence is held by the user.
- **Exit criterion 2, native font (P6 font test, Impact on the primary family): PENDING**, to be reported by the user.
- **Restore stock: PENDING.** Until it is done the game folder holds the patched `ui-visualtreeassets_assets_globalvisualtreeassetpreload.bundle` and `ui-styles_assets_default.bundle`
  of `p6-class-test`, so the tamper check reports the game as modified (expected; it blocks further bundle installs until the stock files are back).
- **Exit criterion 3, FontAsset spike report: delivered** (`docs/PHASE6-FONTS-SPIKE.md`).

Phase 6 therefore stays open on the native font check and the restore.
