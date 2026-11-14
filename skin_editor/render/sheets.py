"""The sheets a render applies, in the order they apply, and an index of their rules for matching.

Where the order comes from (every line is evidence, none is from decompiled code):
- The game's own sheet-configuration assets, read from the AssetRipper rip (`Ripped/ExportedProject/Assets/*StylesheetConfig.asset`; their GUIDs resolved through the
  `AssetBundle` containers of the `ui-styles_assets_*.bundle` files): AlwaysAppliedStylesheetConfig -> AlwaysAppliedStyleSheet; LanguageStylesheetConfig ->
  LanguageDirectionLTRCombined (or RTL); LanguageNameOrderStylesheetConfig -> LanguageNameOrderGivenFirst (or SurnameFirst); ResolutionScaleStylesheetConfig ->
  FMImages_{1..4}x; PCPlatformResolutionScaleStylesheetConfig -> FMControllerIconsPC_{1..4}x. `AlwaysAppliedStyleSheet` imports `default` (its
  m_FlattenedImportedStyleSheets), which applies before it.
- The inspector's `fm_get_styles` on a Dortmund-squad element (2026-11-13, build 27.0.1.2503222, English, LTR, 2x scale, PC) shows the document root carrying
  exactly: AlwaysAppliedStyleSheet, LanguageDirectionLTRCombined, LanguageNameOrderGivenFirst, AnimationStyles, FMImages_2x, FMControllerIconsPC_2x and three
  unnamed sheets. That measured list is the confirming observation for the six named ones and for their order.
- M0 Session A (2026-11-14, same build, Dortmund career loaded, Squad > Overview): the root list read again is TEN entries: the six above in the same order, then
  `Bundesliga`, then three entries with EMPTY names. The same list, unchanged, is what `fm_get_styles` reports from the Loans tile, its base container and the
  StreamedTable (levelsUp 28 = the document root): the table control attaches no sheet of its own. `Bundesliga` is a real sheet in the default bundle (22 rules:
  `--bundesliga-*` font and size tokens and `.bundesliga-licensed-*` classes); it is bound to the club's competition, so a plain render does not apply it.
  `AnimationStyles` (67 rules) is in the default bundle; its selectors need run-time state classes (`.panel--visible`, `.panel--open`), so on a static tree it is inert.
- STILL OPEN: what the three empty-named entries contain (the inspector reports names only). Not applied; `GAPS` says so in every result. Of 117 compared
  properties on 17 live reads of the Loans tile, 82 had a value on both sides and all 82 were equal (colours with alpha, font sizes, flex properties).
- Sheets applied only in other situations (gamepad focus styles, competition sheets, TransferDeadlineDay, FMC images) are not in the order: the configs bind them to
  conditions that are not true on a plain Squad screen.

Shared sheets of the 49-sheet style index are read from it; sheets in other `ui-styles_*` bundles (the 2x image sheets) are decoded on demand and cached."""
import json
from pathlib import Path

from .. import bundles, index_styles, token_patch as tp

D = "ui-styles_assets_default.bundle"
X2 = "ui-styles_assets_2x.bundle"
# (bundle, sheet name, why it is here)
ROOT_SHEETS = [
    (D, "default", "imported by AlwaysAppliedStyleSheet, applied before it"),
    (D, "AlwaysAppliedStyleSheet", "AlwaysAppliedStylesheetConfig"),
    (D, "LanguageDirectionLTRCombined", "LanguageStylesheetConfig (language direction LTR)"),
    (D, "LanguageNameOrderGivenFirst", "LanguageNameOrderStylesheetConfig (given name first)"),
    (D, "AnimationStyles", "present on the measured root; source config unknown (gap)"),
    (X2, "FMImages_2x", "ResolutionScaleStylesheetConfig (scale 2x)"),
    (X2, "FMControllerIconsPC_2x", "PCPlatformResolutionScaleStylesheetConfig (PC, scale 2x)"),
]
GAPS = ["AnimationStyles: no configuration asset lists it; included because the inspector shows it on the root (its selectors need run-time state classes)",
        "Bundesliga (competition sheet, on the measured root for a Bundesliga club) is not applied",
        "three entries with empty names on the measured root are not applied (content not known)"]


class Sheet:
    """One shared sheet with its rules compiled for matching: every selector parsed once into chains with specificity."""
    def __init__(self, pos, bundle, name, entry):
        self.pos, self.bundle, self.name = pos, bundle, name
        self.rules = []                  # [{i, chains:[(chain, spec, text)], props:[[name, value text, cols]], token: bool}]
        for r in entry["rules"]:
            chains = []
            for text in r["s"]:
                for ch in tp.parse_selector(text):
                    chains.append((ch, tp.specificity(ch), text))
            self.rules.append({"i": r["i"], "chains": chains, "props": r["p"], "token": r["t"]})


class SheetBank:
    def __init__(self, folder, cache_dir=None, style_index=None):
        self.folder = Path(folder)
        self.cache_dir = Path(cache_dir) if cache_dir else None
        self.ix = style_index
        self._entries = {}

    def entry(self, bundle, name):
        key = (bundle, name)
        if key in self._entries:
            return self._entries[key]
        e = None
        if self.ix is not None:
            e = next((s for s in self.ix.sheets if s["bundle"] == bundle and s["name"] == name), None)
        if e is None:
            e = self._decode(bundle, name)
        self._entries[key] = e
        return e

    def _decode(self, bundle, name):
        disk = None
        if self.cache_dir:
            f = self.folder / bundle
            st = f.stat()
            disk = self.cache_dir / ("render-sheet-%s-%s-%d-%d.json" % (bundle[:-len(".bundle")], name, st.st_size, st.st_mtime_ns))
            if disk.is_file():
                return json.loads(disk.read_text(encoding="utf-8"))
        for tree in bundles.read_sheets(self.folder / bundle):
            if tree.get("m_Name") == name:
                e = index_styles.sheet_entry(bundle, tree)
                if disk is not None:
                    self.cache_dir.mkdir(parents=True, exist_ok=True)
                    disk.write_text(json.dumps(e), encoding="utf-8")
                return e
        raise KeyError("no sheet %s in %s" % (name, bundle))

    def ordered(self, order=None):
        """The compiled sheets in application order (later sheets win at equal specificity)."""
        return [Sheet(pos, b, n, self.entry(b, n)) for pos, (b, n, _why) in enumerate(order or ROOT_SHEETS)]
