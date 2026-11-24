"""Typed asset adapters (Stage 4D; docs/rea/STAGE-4A-ARCHITECTURE.md section 6.5, decisions D1 and D2).

An adapter is the one place that knows what one asset kind can edit, how those edits are validated, and what their
limits and evidence are. It WRAPS the existing writers (token_patch through patcher, tiles, images): it is not a second
bundle writer, and it never writes by itself - the build pipeline calls the wrapped functions exactly as before.

What each part is for:
  identify(type_name, tree)   which adapter owns an opened object (a structural test, never a name)
  properties()                the editable surface, each property carrying its evidence
  describe(tree)              a structured summary of one opened object, for edit.read
  validate(...)               findings [{level: error|warning|info, code, message, ...}] BEFORE anything is written;
                              an error blocks the build (patcher.build refuses), an override records itself in the manifest
  apply / verify              the existing writer and the existing post-build check, named per adapter so the build
                              pipeline and the manifest can say which code produced and checked each edit
  edit_kind                   the D1 class of every op this adapter can currently apply: "value" (a serialized value
                              inside one asset; identity and references stay as they are). No adapter can apply a
                              reference or identity edit today; the policy still knows what to do with one.

Overlap (D2) lives in the composition adapter's validation: the final grid state is checked with the existing tile
geometry and validation logic (placement.Grid / placement.check), an overlap is an ERROR by default (Stage 3E proved
the game drops a tile), and the only way past it is an explicit override that is recorded - the affected tiles, the
overlapping region and the validation result - in the build manifest. The rule is enforced here, in the backend, so
the CLI, the API and Studio see one policy; the frontend never duplicates it.
"""
from pathlib import Path

from . import bundles, images, placement

VERSION = 1
LEVELS = ("error", "warning", "info")


def finding(level, code, message, **kw):
    """One validation result. Everything beyond level/code/message is data for the manifest (tiles, region, override)."""
    if level not in LEVELS:
        raise ValueError("a finding level is error, warning or info")
    d = {"level": level, "code": code, "message": message}
    d.update(kw)
    return d


class AssetAdapter:
    """Base class. Subclasses set the metadata and implement identify/describe/validate."""

    name = "?"
    asset_types = ()                 # Unity type names this adapter can describe (identify may accept more)
    edit_kind = "value"              # the D1 class of every op this adapter can apply today
    # evidence: status one of Confirmed | Partial | Unsupported | Runtime-proven (the Stage 4A vocabulary),
    # basis says what holds it up, stages point at the reports.
    evidence = {"status": "Unsupported", "basis": "", "stages": []}
    limitations = []

    def identify(self, type_name, tree):
        raise NotImplementedError

    def properties(self):
        return []

    def describe(self, type_name, tree):
        return {}

    def validate(self, ops, context):
        """ops: the adapter's op records; context: {grid, placements, source_dir, ...} what the validation needs.
        Returns findings; never writes anything."""
        return []

    def info(self):
        return {"name": self.name, "version": VERSION, "asset_types": list(self.asset_types), "edit_kind": self.edit_kind,
                "properties": self.properties(), "limitations": list(self.limitations), "evidence": dict(self.evidence)}


def _fmt_name(fmt):
    return images.FORMATS.get(int(fmt), int(fmt))


class StyleSheetAdapter(AssetAdapter):
    """The game's StyleSheets: token overrides, literal colour swaps, appended and replaced rules, class renames.
    Wraps token_patch.SheetPatcher through patcher.patch_sheet; checked by verify_static.check_edits and the
    appended-rule check of the structural gate."""

    name = "stylesheet"
    asset_types = ("MonoBehaviour",)
    evidence = {"status": "Confirmed",
                "basis": "unit tests plus the object-level comparison against vanilla in every build; applied in game on "
                         "an older build (Phase 6); the 27.1 in-game result of a sheet edit is not tested",
                "stages": ["3A", "4A section 3"]}
    limitations = ["an appended rule is added at the end of the sheet; the game's own rules are never rewritten except by a "
                   "declared replace/remove edit",
                   "the colour, float, dimension and string pools are append-only (the structural gate enforces it)",
                   "a colour entry that did not decode (outside 0..1) is never matched and never rewritten (patcher.refuse_unproven)",
                   "runtime proof on 27.1 exists for a tile composition edit, not for a sheet edit"]

    def identify(self, type_name, tree):
        return type_name == "MonoBehaviour" and isinstance(tree, dict) and "m_Rules" in tree

    def properties(self):
        return [{"name": "tokens", "type": "colour tokens (--name)", "evidence": "token_patch.SheetPatcher, gate check_edits"},
                {"name": "literals", "type": "exact RGBA or rgb-keep-alpha colour swaps", "evidence": "patcher.swap_rgba + SheetPatcher"},
                {"name": "append_rules", "type": "new rules (mini-USS) appended to a named sheet", "evidence": "verify_static._rule_matches"},
                {"name": "edit_rules", "type": "in-place replace/remove of a game rule's declarations", "evidence": "verify_static.check_edits"},
                {"name": "rename_classes", "type": "class renames in every sheet's selectors", "evidence": "token_patch count_renames"}]

    def describe(self, type_name, tree):
        rules = tree.get("m_Rules") or []
        props = {}
        for r in rules:
            for p in r.get("m_Properties") or []:
                name = p.get("m_CustomName") or str(p.get("m_Id"))
                props[name] = props.get(name, 0) + 1
        return {"name": tree.get("m_Name"), "rules": len(rules),
                "pools": {k: len(tree.get(k) or []) for k in ("colors", "floats", "dimensions", "strings")},
                "distinct_properties": len(props), "top_properties": sorted(props.items(), key=lambda kv: -kv[1])[:8]}

    def validate(self, ops, context):
        """ops: {spec, skip_sheets, appended_sheets, edited_sheets}. Everything structural is already validated by the
        project model; what the adapter adds before building is the skip-sheet interaction (rules that would silently
        not apply) and the quarantined-colour refusal, which the build enforces as a hard stop."""
        out = []
        spec = ops["spec"]
        skip = set(ops["skip_sheets"])
        for sheet in sorted(set(ops["appended_sheets"]) | set(ops["edited_sheets"])):
            if sheet in skip:
                out.append(finding("warning", "rules_on_skipped_sheet",
                                    "scoped rules on skipped sheet %s are not applied" % sheet, sheet=sheet))
        lit = spec.get("literal_map") or {}
        if lit and (context or {}).get("quarantined_sheets"):
            out.append(finding("error", "literal_swap_hits_quarantined_colour",
                                "an rgb-keep-alpha swap would copy an undecoded bundle colour; the build refuses this "
                                "(patcher.refuse_unproven)", sheets=list(context["quarantined_sheets"])))
        return out


class CompositionAdapter(AssetAdapter):
    """Grid compositions (m_gridComponents): cell positions, written by tiles.apply_ops from the stored placement edits.
    The adapter's validation is where the tile-overlap policy (D2) lives."""

    name = "composition"
    asset_types = ("MonoBehaviour",)
    evidence = {"status": "Runtime-proven (position edits)",
                "basis": "Stage 3G: a non-overlapping position edit of SquadComposition-Standard rebuilt only "
                         "ui-tileslayouts_assets_all.bundle and moved the tile in the running game (build 27.1.0.2505117, "
                         "1440x900 windowed, Large UI); sizes and configs are blocked by placement.py",
                "stages": ["3E", "3F", "3G"]}
    limitations = ["only cell positions (m_location.x/y) are written; a size or config change is refused (a cell's size is "
                   "derived from its configs)",
                   "the cell must still be the one the edit was made against (index and m_elementID guard), so a game "
                   "update that moves it makes the build refuse rather than land somewhere else",
                   "the active composition depends on the window width; an edit is invisible when its composition is "
                   "not the active one (Stage 3E)",
                   "an overlapping edit can drop a tile in game (Stage 3E): overlap is a validation error unless explicitly "
                   "overridden"]

    def identify(self, type_name, tree):
        return type_name == "MonoBehaviour" and isinstance(tree, dict) and "m_gridComponents" in tree

    def properties(self):
        return [{"name": "cell_position", "type": "move-cell {to: {x, y}} (grid units)", "evidence": "tiles.apply_ops / tiles.check_ops"}]

    def describe(self, type_name, tree):
        cells = tree.get("m_gridComponents") or []
        rows = []
        for i, c in enumerate(cells):
            loc = c.get("m_location") or {}
            rows.append({"cell_index": i, "element_id": c.get("m_elementID"), "x": loc.get("x"), "y": loc.get("y")})
        return {"name": tree.get("m_Name"), "cells": len(cells), "positions": rows[:400],
                "note": "sizes derive from the cells' configs; the validated geometry (with sizes) lives in the layout dump"}

    # ---- validation (D2): bounds from the existing checks, overlap on the FINAL state, error by default
    def validate(self, ops, context):
        """ops: one move-cell op per edited cell of ONE composition {composition, bundle, path_id, moves: [...]}.
        context: {grid: placement.Grid, confirmed: {composition#cell_index pairs confirmed at edit time},
        allow_overlap: bool}. Returns findings; an overlap is an error unless the pair was explicitly confirmed at
        edit time or the whole build was started with allow_override - both are recorded, never silent."""
        grid, comp = context["grid"], ops["composition"]
        if grid is None:
            return [finding("error", "no_geometry",
                            "composition %s cannot be validated: no layout dump is imported" % comp, composition=comp)]
        out, moves = [], ops["moves"]
        by_idx = {m["cell_index"]: m for m in moves}
        # the existing per-edit validation, with the other edits standing in for the dump's geometry
        for m in moves:
            if (comp, m["cell_index"]) not in grid.cells:
                out.append(finding("error", "cell_invalid",
                                   "%s cell %d is not in the dump (game updated? re-do this edit)" % (comp, m["cell_index"]),
                                   composition=comp, cell_index=m["cell_index"]))
                continue
            geo = self._geometry(grid, comp, m["cell_index"], m["to"]["x"], m["to"]["y"])
            others = [{"composition": comp, "cell_index": o["cell_index"],
                       "geometry": self._geometry(grid, comp, o["cell_index"], o["to"]["x"], o["to"]["y"])}
                      for o in moves if o["cell_index"] != m["cell_index"] and (comp, o["cell_index"]) in grid.cells]
            r = placement.check(grid, {"composition": comp, "cell_index": m["cell_index"], "geometry": geo}, others)
            out += [finding("error", "cell_invalid", "%s cell %d: %s" % (comp, m["cell_index"], b),
                            composition=comp, cell_index=m["cell_index"]) for b in r["blocks"]]
        # final-state overlap: every edited cell against every other cell (edited cells at their new position),
        # never the game's own pre-existing overlaps against each other; one finding per pair
        if grid.comps.get(comp) is not None:
            siblings = grid.siblings(comp)
            seen_pairs = set()
            for m in sorted(moves, key=lambda x: x["cell_index"]):
                a = self._geometry(grid, comp, m["cell_index"], m["to"]["x"], m["to"]["y"])
                for sib in siblings:
                    if sib["cell_index"] == m["cell_index"]:
                        continue
                    edit = by_idx.get(sib["cell_index"])
                    g = {"x": edit["to"]["x"], "y": edit["to"]["y"], "w": sib["w"], "h": sib["h"]} if edit \
                        else {k: sib[k] for k in placement.GEO}
                    region = _intersection(a, g)
                    if not region:
                        continue
                    pair = tuple(sorted([placement.eid(comp, m["cell_index"]), placement.eid(comp, sib["cell_index"])]))
                    if pair in seen_pairs:
                        continue
                    seen_pairs.add(pair)
                    confirmed = pair in context.get("confirmed", set())
                    overridden = confirmed or bool(context.get("allow_overlap"))
                    out.append(finding(
                        "warning" if overridden else "error", "tile_overlap",
                        "%s: cell %d (%s) overlaps cell %d (%s) in the region x=%d..%d, y=%d..%d. The game drops a "
                        "tile when cells overlap (Stage 3E), so this is an error unless it is deliberately overridden."
                        % (comp, m["cell_index"], _cell_id(grid, comp, m["cell_index"]), sib["cell_index"],
                           sib["element_id"], region["x"], region["x"] + region["w"], region["y"], region["y"] + region["h"]),
                        composition=comp,
                        tiles=[{"cell_index": m["cell_index"], "element_id": _cell_id(grid, comp, m["cell_index"]),
                                "geometry": a},
                               {"cell_index": sib["cell_index"], "element_id": sib["element_id"], "geometry": g}],
                        region=region, override=bool(overridden),
                        override_source=("edit_time_confirmation" if confirmed and not context.get("allow_overlap")
                                         else "build_parameter" if context.get("allow_overlap") else None)))
        return out

    @staticmethod
    def _geometry(grid, comp, idx, x, y):
        old = grid.geometry(comp, idx)
        return {"x": x, "y": y, "w": old["w"], "h": old["h"]}


def _cell_id(grid, comp, idx):
    return (grid.cells.get((comp, idx)) or {}).get("element_id")


def _intersection(a, b):
    """The overlapping region of two cells, or None. Axis-aligned grid units."""
    x, y = max(a["x"], b["x"]), max(a["y"], b["y"])
    w = min(a["x"] + a["w"], b["x"] + b["w"]) - x
    h = min(a["y"] + a["h"], b["y"] + b["h"]) - y
    return {"x": x, "y": y, "w": w, "h": h} if w > 0 and h > 0 else None


class TextureAdapter(AssetAdapter):
    """Texture2D swaps (images.swap_texture) and VectorImage (SVG) swaps: the replacement is re-encoded into the
    texture's own size and, where writable, its own format."""

    name = "texture"
    asset_types = ("Texture2D",)
    evidence = {"status": "Confirmed",
                "basis": "unit tests and Stage 3B offline round-trips; no 27.1 in-game result for a texture edit",
                "stages": ["3B", "3F"]}
    limitations = ["writable formats: %s; a Crunch texture is re-encoded as plain DXT (larger file)" %
                   ", ".join(_fmt_name(f) for f in sorted(images.WRITABLE)),
                   "mip levels are reduced to 1 on write (UnityPy limitation)",
                   "the replacement is fitted (cover, contain, stretch) into the texture's own size; the size is not changed",
                   "runtime behaviour on 27.1 is untested (offline round-trip only)"]

    def identify(self, type_name, tree):
        return type_name == "Texture2D"

    def properties(self):
        return [{"name": "pixels", "type": "a replacement image (png/jpg/webp) re-encoded into the same size and format",
                  "evidence": "images.swap_texture; checked object by object by the structural gate"}]

    def describe(self, type_name, obj_or_tree):
        d = obj_or_tree
        if isinstance(d, dict):          # a typetree (not used by the current writers, kept for completeness)
            return {"name": d.get("m_Name"), "width": d.get("m_Width"), "height": d.get("m_Height"),
                    "format": _fmt_name(d.get("m_TextureFormat")), "mips": d.get("m_MipCount")}
        fmt = int(getattr(d.m_TextureFormat, "value", d.m_TextureFormat))
        return {"name": d.m_Name, "width": d.m_Width, "height": d.m_Height, "format": _fmt_name(fmt),
                "mips": int(getattr(d, "m_MipCount", 1) or 1), "writable": fmt in images.WRITABLE,
                "reencoded": fmt in images.CRUNCH_TO and _fmt_name(images.CRUNCH_TO[fmt]) or None}

    def validate(self, ops, context):
        """ops: {bundle, swaps: [{path_id, kind, source, fit}]}. The source bundle is opened READ ONLY; every target
        must exist, be the right kind, and (for a texture) be writable or Crunch-re-encodable."""
        src = (context or {}).get("source_bundle")
        out = []
        if not src or not ops.get("swaps"):
            return out
        if bundles.bundle_header(src) is None:
            # not a UnityFS bundle (only possible in synthetic fixtures): the target object cannot be pre-checked;
            # the apply step stays the authority and raises its own error on a missing target
            return [finding("info", "target_not_prechecked",
                            "%s is not a UnityFS bundle, so the swap targets were not pre-checked; the build step still "
                            "checks them" % Path(src).name, bundle=ops["bundle"])]
        env = bundles.open_readonly(src)                      # bytes: no Windows handle is left open on the game file
        objs = {o.path_id: o for o in env.objects}
        for s in ops["swaps"]:
            obj = objs.get(int(s["path_id"]))
            if obj is None:
                out.append(finding("error", "target_missing",
                                   "%s: no object with path id %s (game updated? re-pick the image)"
                                   % (Path(src).name, s["path_id"]), bundle=ops["bundle"], path_id=str(s["path_id"])))
                continue
            if s.get("kind") == "texture":
                if obj.type.name != "Texture2D":
                    out.append(finding("error", "target_not_texture",
                                       "%s: path id %s is not a texture" % (Path(src).name, s["path_id"]),
                                       bundle=ops["bundle"], path_id=str(s["path_id"])))
                    continue
                fmt = int(getattr(obj.read().m_TextureFormat, "value", 0))
                if fmt not in images.WRITABLE and fmt not in images.CRUNCH_TO:
                    out.append(finding("error", "format_not_writable",
                                       "%s: texture format %s cannot be written" % (Path(src).name, _fmt_name(fmt)),
                                       bundle=ops["bundle"], path_id=str(s["path_id"])))
                elif fmt in images.CRUNCH_TO:
                    out.append(finding("info", "crunch_reencoded",
                                        "%s: Crunch texture will be written as plain %s (larger file)"
                                        % (Path(src).name, _fmt_name(images.CRUNCH_TO[fmt])),
                                        bundle=ops["bundle"], path_id=str(s["path_id"])))
            elif s.get("kind") == "svg":
                tt = obj.read_typetree() if obj.type.name == "MonoBehaviour" else None
                if not isinstance(tt, dict) or "vertices" not in tt:
                    out.append(finding("error", "target_not_vector",
                                       "%s: path id %s is not an SVG (VectorImage)" % (Path(src).name, s["path_id"]),
                                       bundle=ops["bundle"], path_id=str(s["path_id"])))
        return out


class SpriteAdapter(AssetAdapter):
    """Icon swaps: a sprite is a view into an atlas texture, so an icon swap is written through the atlas of every UI
    scale (images.apply_icon_swaps). Everything else about a sprite is read-only today."""

    name = "sprite"
    asset_types = ("Sprite",)
    evidence = {"status": "Partial",
                "basis": "the atlas write is tested; a sprite's own rect, pivot and border are never edited",
                "stages": ["4A section 3"]}
    limitations = ["an icon swap writes the atlas textures of every UI scale, not the sprite object itself",
                   "a sprite's rect, pivot, border or atlas membership is not editable (unsupported)",
                   "an icon is addressed by its 2x sprite (bundle %s)" % (images.ICONS % "2x")]

    def identify(self, type_name, tree):
        return type_name == "Sprite"

    def properties(self):
        return [{"name": "icon_pixels", "type": "a replacement image written through the sprite atlas of every scale",
                  "evidence": "images.apply_icon_swaps; object-level comparison by the gate"}]

    def describe(self, type_name, tree):
        return {"name": tree.get("m_Name"), "rect": tree.get("m_Rect"),
                "note": "sprites are views into atlas textures; an icon swap writes the atlases"}

    def validate(self, ops, context):
        return [finding("info", "sprite_edited_through_atlas",
                        "icon swaps are written through the atlas textures of every UI scale; the sprite object itself "
                        "is not edited", bundle=ops.get("bundle"))]


class FontAdapter(AssetAdapter):
    """Fonts: a font-family token can be repointed (native target: the export copies the font and writes the url()
    rule). A FontAsset replacement inside a bundle is unsupported and stays out of the build."""

    name = "font"
    asset_types = ("Font",)
    edit_kind = "value"
    evidence = {"status": "Partial",
                "basis": "font.set writes a -unity-font-definition rule from a token; FontAsset replacement was spiked and "
                         "is not implemented (docs/PHASE6-FONTS-SPIKE.md)",
                "stages": ["4A section 3"]}
    limitations = ["only the font-family token route exists, and only for a native skin export",
                   "a FontAsset inside a bundle is not replaced (unsupported)",
                   "no bundle build step: fonts never appear in the typed bundle build"]

    def identify(self, type_name, tree):
        return type_name == "Font"

    def properties(self):
        return [{"name": "font_family_token", "type": "a --token assigned a .ttf/.otf (native target only)",
                  "evidence": "font.set / native export"}]

    def describe(self, type_name, tree):
        return {"name": tree.get("m_Name") if isinstance(tree, dict) else None,
                "note": "FontAsset replacement is unsupported; only font-family tokens are editable (native target)"}


ADAPTERS = (StyleSheetAdapter(), CompositionAdapter(), TextureAdapter(), SpriteAdapter(), FontAdapter())


def all_adapters():
    return list(ADAPTERS)


def find(type_name, tree):
    """The adapter that owns an opened object, or None. First match wins; identify is structural (never a name)."""
    for a in ADAPTERS:
        if a.identify(type_name, tree):
            return a
    return None


def by_name(name):
    for a in ADAPTERS:
        if a.name == name:
            return a
    raise KeyError("no adapter named %s" % name)
