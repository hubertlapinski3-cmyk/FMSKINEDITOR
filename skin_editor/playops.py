"""Skin Operations and the Playground session (Stage 5B; the architecture is docs/rea/STAGE-5A-ARCHITECTURE.md
section 5). PURE MODEL, no I/O except the explicit save/load of the session file.

THE CENTRAL RULE: an operation is a provenance-carrying record that PROJECTS onto the one edit vocabulary the backend
can actually build. Every kind the schema accepts is either TRANSLATABLE (it names the existing writer it becomes)
or REFUSED with a precise reason - `ReorderNode` and a non-tile `MoveNode` have no writer at all
(element geometry is derived from configs and layouts; sibling order is never written), so they are refused, not
faked. `ResizeNode` and `AddCell` are CANDIDATES (the ADDENDUM of 2026-11-18): the writer they need is exercised
by third-party 27.1 skins but not yet by this project, so they validate and stay preview-only until their own
owner-run runtime test passes. Nothing here invents a capability the 4D adapters do not wrap.

OWNER FINDINGS OF 2026-11-18, APPLIED (they change the model, not just its documentation):

1. SELECTOR REACH. A scoped rule changes EVERYTHING its selector matches, on every screen: element names repeat
   (a third of named elements share type+name inside a layout), so no selector points at one node, and the only
   per-node writer (the layout's inline sheet) is a protected-file question that does not exist here. Therefore a
   SetColor/SetStyle/SetSpacing operation is REFUSED unless it carries a measured `reach` ({elements, layouts,
   screens} from the style and layout indexes - the engine's `layout.reach`), and a reach above one element is a
   SCOPE CHANGE the user must see: the operation's safety class becomes "scope", never a plain value edit. A colour
   change that could go through a token instead records its ROUTE and the reason it was chosen (the two have
   different reach).
2. RUNTIME-DEPENDENT VISIBILITY. A sheet `display`/`visibility` rule loses to inline styles set by code at
   runtime, and 26 of 58 measured nodes carry learned runtime classes: every SetVisibility carries that caveat and
   its effect evidence is "runtime-dependent", never a guaranteed outcome.
3. REBASE IN TIERS, NOT A BLANKET. The logical id matched 71.5% of nodes across the 983 layouts whose shape
   changed; the tier-2 key (layout GUID, type, name) resolves 63-67% uniquely. So every operation stores the
   logical id, the PHYSICAL locator (bundle, bundle_sha256, path_id, m_id) and a type/name/classes GUARD; rule
   provenance is keyed by (bundle, sheet, selector, occurrence) - rule indices are unstable (153 of 5510 positions
   kept their content between builds) and a sheet named "default" exists in two bundles. `rebase` resolves each
   operation through a caller-supplied resolver (the new build's document index) and reports matched / ambiguous /
   unresolved separately, exactly as Gate B does; nothing is silently applied.
4. COMPOSITION-SCOPED MOVES. A MoveNode edits ONE composition; the active one depends on window width (Stage 3E).
   The cell is addressed by (composition, cell_index) with the REQUIRED cell_element_id guard (element ids repeat:
   Team Instructions cells 2 and 3 share one), and the operation carries both caveats: the composition scope, and
   that the D2 overlap gate checks m_gridComponents only - optional slices the game adds at runtime are outside it.

  ReplaceToken        -> project token_overrides            -> token_patch.SheetPatcher        (value; every user of the token changes)
  SetColor/SetStyle/
  SetSpacing          -> a scoped rule on a sheet           -> patcher.patch_sheet + gate      (value or SCOPE, by measured reach)
  SetVisibility       -> a scoped rule (visibility)         -> patcher.patch_sheet            (runtime-dependent effect)
  MoveNode (tile)     -> a placement edit (move-cell)       -> tiles.apply_ops + the D2 gate    (value; composition-scoped)
  ReplaceAsset        -> a project image swap              -> images.apply_swaps               (value)
  anything else       -> refused

IDENTITY: an operation's target is the UiDocument identity (screen, logical_id = layout GUID + structural path,
structural_key for cross-build comparison, locator bundle/CAB/PathID) plus the render position for canvas sync;
`m_Id` is a within-build locator only and is never used as the cross-build key. Provenance of the ORIGINAL value
(bundle, object, field, evidence class) is recorded, never invented. A session records the game build it was made
against; on load, operations whose recorded provenance no longer matches are marked stale - never silently applied
(the Stage 5A identity scheme: element m_Ids are re-minted across builds; the structural_key is the comparison).

UNDO/REDO: the session's ordered operation list is the history. `undo` marks the newest applied operation reverted
(kept, never deleted); `redo` unmarks; individual and full revert are the same mechanism. Two operations on the same
(kind, target, property) do not conflict silently: the later one SUPERSEDES the earlier, which is recorded on both.

SESSION FILE: `<project folder>/edits/playground.json`, schema `fm-playsession/1` - a NEW OPTIONAL file the existing
project readers ignore (projfmt.read skips unknown files); the skin project format is untouched. The engine API for
the Playground views arrives with the first view that consumes it (Stage 5C/5E); this module is the model.
"""
import json
import os
import re
import secrets
import time
from pathlib import Path

SCHEMA = "fm-playsession/1"
OP_SCHEMA = "fm-playop/1"

# the kinds the SCHEMA accepts, and their translation (None = no writer exists; refused at validation, never faked).
# ADDENDUM (Golden Boy evidence, 2026-11-18): AddCell is a CANDIDATE operation - the writer it needs (a cell added
# to an existing composition) is exercised by third-party 27.1 skins (docs/rea/STAGE-5-GOLDENBOY-DIFF.md) but NOT
# yet by this project, so it validates as a candidate and stays preview-only until its own owner-run runtime test
# passes. ResizeNode was promoted from candidate to BUILDABLE on 2026-11-20: Test C proved an ENLARGEMENT with the
# cell's configured size unchanged, rendered by the game at the predicted geometry. Shrinking below the
# configured size stays refused (the config list is not written). ReorderNode and a generic non-tile MoveNode stay
# refused.
KINDS = {
    "ReplaceToken": "token_overrides",
    "SetColor": "scoped_rules",
    "SetStyle": "scoped_rules",
    "SetSpacing": "scoped_rules",
    "SetVisibility": "scoped_rules",
    "MoveNode": "placement",
    "ResizeNode": "placement",
    "AddCell": "placement",
    "SetOptionalSlots": "optional_slots",
    "SetCellMaxSize": "cell_max_sizes",
    "SwapTile": "cell_tiles",
    "ReplaceAsset": "image_swaps",
    "ReorderNode": None,
}
SAFETY = {k: ("candidate" if k in ("SetOptionalSlots", "SetCellMaxSize", "SwapTile") else ("value" if v else "unknown")) for k, v in KINDS.items()}
MAX_CELL_SIZE = 100          # the stock "flexible" m_maxSize; nothing larger is accepted
NO_BUILD_PATH = "SetCellMaxSize has no build path yet"
LAYOUT_KINDS = ("MoveNode", "ResizeNode", "SetCellMaxSize", "AddCell", "SetOptionalSlots", "SwapTile")
# ST1: what is PROVEN in the game through the custom-layout JSON (game stock, plugin 0.2.40); only these are buildable on the custom_layout route.
PROVEN_ON_JSON = {
    "SetCellMaxSize": "CL part B (FItness 4x4 to 6x4, one byte, outcome A)",
    "ResizeNode": "CL3 B1 (generated SquadComposition-Large, Atmosphere 4x4, matches test C to 0.0 px)",
    "SwapTile": "CL3 B2 (Happiness back in the profile's first slot by name, shows HAPPINESS)",
    "MoveNode": "JX X1 (Atmosphere and Training trade places, shows as predicted)",
    "AddCell": "JX X2 (Happiness added at x16 y10, shows as predicted with its text)",
    "SetOptionalSlots": "JX X3 (bottom-slot REPLACE, Loans by Happiness, shows as predicted)",
}
JSON_ONLY_REPLACE = ("SetOptionalSlots",)         # proven on the JSON route for a replace only (one remove and one add in the same region)
SLOT_JSON_REASON = "proven on the bundle route only"
TOKEN = re.compile(r"^--[\w-]+$")
SOURCE_FILE = re.compile(r"^[\w.-]+\.(png|jpg|jpeg|webp|svg)$", re.I)
GEO = ("x", "y", "w", "h")
GEOMETRY = re.compile(r"^(left|right|top|bottom|width|height)$")
SPACING = re.compile(r"^(margin|padding|border-(top|bottom|left|right)-width)$")
VISIBILITY_PROPS = ("visibility", "display")
ROUTE_PREFERENCES = ("skin_folder", "bundle")
DEFAULT_ROUTE_PREFERENCE = "bundle"
# A token is defined in BOTH style bundles on 27.1 (the B2 scan). The default bundle's definitions are
# proven by this project's test B; the common bundle's replacement is UNVERIFIED here (third-party
# Golden Boy/Kuuvaia evidence only).
TOKEN_BUNDLES = ("ui-styles_assets_default.bundle", "ui-styles_assets_common.bundle")
COMMON_TOKEN_BUNDLE = "ui-styles_assets_common.bundle"
COMMON_BUNDLE_LABEL = ("UNVERIFIED by this project: the common bundle's replacement rests on third-party "
                       "Golden Boy/Kuuvaia evidence, not on our own runtime test")


def _now():
    return time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())


class OperationError(ValueError):
    """A refusal with the precise reason (the Playground shows it; the operation never becomes buildable)."""


def _declaration_edit(op):
    """The per-declaration handle for a joined-node SetColor/SetSpacing, or None when the operation is an
    APPENDED scoped rule (no winning-declaration provenance). The handle is keyed by
    (bundle, sheet, normalised selector, occurrence, property) - never by rule index - and carries the
    declaration's whole value list so var() -> literal works. `old` is the winning declaration's value text.

    The handle also carries the operation's expanded-tree element reach (`elements`, `layouts`, `screens`)
    so projection and build can report the same scope the model validated."""
    if op.get("kind") not in ("SetColor", "SetSpacing"):
        return None
    rule = (op.get("new") or {}).get("rule") or {}
    props = rule.get("props") or {}
    orig = op.get("original") or {}
    prov = orig.get("provenance") or {}
    if prov.get("inline"):
        return None                       # inline styles are not a sheet declaration; the scoped route handles them
    bundle, sheet, selector = prov.get("bundle"), prov.get("sheet"), prov.get("selector")
    if not bundle or not sheet or not selector or len(props) != 1:
        return None
    prop, value = next(iter(props.items()))
    old = prov.get("declaration_value", prov.get("old", orig.get("value")))
    if old is None or isinstance(old, (dict, list, tuple)):
        return None
    from . import project as project_mod
    try:
        new_text = project_mod.patch_text(value)
    except Exception:
        return None
    reach = rule.get("reach") or {}
    return {"bundle": bundle, "sheet": sheet, "selector": selector,
            "occurrence": int(prov.get("occurrence") or 0), "property": prop,
            "old": str(old), "new": new_text,
            "reach": {k: reach.get(k) for k in ("elements", "layouts", "screens", "measured_by")
                      if reach.get(k) is not None}}


def declaration_edit(op):
    """Public form (build5g/project projection share it): the handle or None."""
    return _declaration_edit(op)


def route_of(op, route_preference=DEFAULT_ROUTE_PREFERENCE, layout_route="bundle"):
    """The route an operation takes. The DEFAULT is the skin-folder route: it writes the skin folder only and
    changes no game file. With route_preference="bundle" (a project setting, DEFAULT skin_folder):

      - ReplaceToken edits every definition of the token in BOTH style bundles (default + common). The common
        replacement is labelled UNVERIFIED by this project (third-party Golden Boy/Kuuvaia evidence).
      - SetColor/SetSpacing on a JOINED node (its original value carries the winning declaration's provenance)
        become a per-declaration edit of that declaration, carrying its expanded-tree element reach.
      - SetStyle/SetVisibility and appended scoped rules stay skin-folder-only: they append a rule, which has no
        per-declaration bundle writer.
      - tile geometry (MoveNode/ResizeNode/AddCell) keeps the bundle route it always had.
    """
    kind = op.get("kind")
    if layout_route == "custom_layout" and kind in LAYOUT_KINDS:
        if kind in JSON_ONLY_REPLACE and (op.get("new") or {}).get("op") not in ("add-slot", "remove-slot"):
            return {"route": "blocked", "reason": "SetOptionalSlots %s is %s" % ((op.get("new") or {}).get("op") or "?", SLOT_JSON_REASON)}
        return {"route": "custom_layout", "reason": "the game's custom-layout file for the composition; proven: " + PROVEN_ON_JSON[kind]
                + ("; a replace (one remove and one add in the same region) only" if kind in JSON_ONLY_REPLACE else "")}
    if route_preference == "bundle":
        if kind == "ReplaceToken":
            return {"route": "bundle",
                    "reason": "a token override changes every definition of the token in both style bundles; "
                              "the common bundle's replacement is %s" % COMMON_BUNDLE_LABEL,
                    "bundles": list(TOKEN_BUNDLES),
                    "unverified_bundles": [COMMON_TOKEN_BUNDLE],
                    "common_bundle_label": COMMON_BUNDLE_LABEL}
        if kind in ("SetColor", "SetSpacing"):
            handle = _declaration_edit(op)
            if handle:
                return {"route": "bundle",
                        "reason": "a per-declaration edit of the winning declaration in %s; it carries the "
                                  "expanded-tree element reach (%s element(s))" %
                                  (handle["bundle"], handle["reach"].get("elements")),
                        "declaration": handle}
            return {"route": "skin-folder",
                    "reason": "an appended scoped rule (no winning-declaration provenance) stays on the "
                              "skin-folder route: it appends a rule, which the bundle writer does not do"}
        if kind in ("SetStyle", "SetVisibility"):
            return {"route": "skin-folder",
                    "reason": "appended scoped rules stay skin-folder-only; only SetColor and SetSpacing on a "
                              "joined node take the per-declaration bundle route"}
    if kind in ("ReplaceToken", "SetColor", "SetStyle", "SetSpacing", "SetVisibility", "ReplaceAsset"):
        return {"route": "skin-folder", "reason": "the default route writes the skin folder only and changes no game file"}
    if kind == "SetCellMaxSize":
        return {"route": "blocked", "reason": NO_BUILD_PATH}
    if kind == "SetOptionalSlots":
        return {"route": "bundle", "reason": "the composition's optional-slot region is rebuilt into the schema 2 "
                                             "package; the operation is a CANDIDATE until its first runtime test passes"}
    if kind in ("MoveNode", "ResizeNode", "AddCell"):
        return {"route": "bundle", "reason": "the composition asset is rebuilt into the schema 2 package; install.preflight "
                                             "carries the Stage 3G CRC caveat (observed, not guaranteed)"}
    return {"route": "blocked", "reason": "no route: the operation kind has no writer"}


def route_blocked_for_sheets(op, route_preference=DEFAULT_ROUTE_PREFERENCE):
    """Whether the operation would need an appended-rule bundle writer (which does not exist). With the default
    skin_folder preference every scoped-rule kind is blocked here; with bundle it is only the kinds that stay
    appended rules (SetStyle/SetVisibility and SetColor/SetSpacing without winning-declaration provenance)."""
    if op.get("kind") not in ("SetColor", "SetStyle", "SetSpacing", "SetVisibility"):
        return False
    return route_of(op, route_preference)["route"] != "bundle"


def op_id():
    """Collision-safe: a timestamp alone is NOT unique (two operations can be created in the same millisecond), and
    operation records are addressed by id for undo/redo and supersession."""
    return "op-%s-%s" % (_now(), secrets.token_hex(4))


# ---------------------------------------------------------------- the operation record
def new_operation(kind, target, new, original=None, note=""):
    """One operation record. `target`: {screen, logical_id, structural_key, locator:{bundle, bundle_sha256, cab,
    path_id, m_id}, guard:{type, name, classes}, render_pos}; `new`/`original`: the value plus its evidence
    ({value, evidence, provenance}). The record is serialisable as it stands; VALIDATION decides whether it can
    ever build."""
    if kind not in KINDS:
        raise OperationError("unknown operation kind %r; the schema accepts: %s" % (kind, ", ".join(sorted(KINDS))))
    return {"schema": OP_SCHEMA, "id": op_id(), "kind": kind, "target": dict(target), "original": original,
            "new": new, "note": str(note)[:200], "created_utc": _now(), "modified_utc": _now(),
            "state": "applied", "superseded_by": None, "validation": None}


# ---------------------------------------------------------------- validation (translate or refuse)
def slot_op_promoted(op):
    """True for the measured SetOptionalSlots cases: m_bottom on SquadComposition-Large at 2560x1440 Small
    (add, remove-only and reorder). Other regions/settings are not claimed."""
    new = (op or {}).get("new") or {}
    return ((op or {}).get("kind") == "SetOptionalSlots"
            and new.get("composition") == "SquadComposition-Large"
            and (new.get("direction") or "m_bottom") == "m_bottom"
            and new.get("op") in ("add-slot", "remove-slot", "reorder-slot"))


def check_cell_max_size(max_size, design, config_sizes):
    """SC1: the refusal rules of SetCellMaxSize, shared by the builder and validate(). `max_size` {x, y} is the new m_maxSize (width, height),
    `design` {w, h} the cell's design size, `config_sizes` [{x, y}] the configuration sizes the cell lists (cell_configs). Refuses a max
    that is not a positive integer pair, above 100, smaller than the design size, or smaller than any listed configuration size."""
    if not isinstance(max_size, dict) or set(max_size) != {"x", "y"} or not all(isinstance(max_size[k], int) and not isinstance(max_size[k], bool)
                                                                               for k in ("x", "y")):
        raise OperationError("SetCellMaxSize needs the new m_maxSize as integer {x, y} (width, height)")
    if max_size["x"] <= 0 or max_size["y"] <= 0:
        raise OperationError("m_maxSize must be positive, not %dx%d" % (max_size["x"], max_size["y"]))
    if max_size["x"] > MAX_CELL_SIZE or max_size["y"] > MAX_CELL_SIZE:
        raise OperationError("m_maxSize %dx%d is refused: width and height are at most %d (the stock 'flexible' value)"
                             % (max_size["x"], max_size["y"], MAX_CELL_SIZE))
    if max_size["x"] < design["w"] or max_size["y"] < design["h"]:
        raise OperationError("m_maxSize %dx%d is smaller than the cell's design size %dx%d"
                             % (max_size["x"], max_size["y"], design["w"], design["h"]))
    for cs in config_sizes or []:
        if max_size["x"] < cs["x"] or max_size["y"] < cs["y"]:
            raise OperationError("m_maxSize %dx%d is smaller than a configuration size the cell lists, %dx%d"
                                 % (max_size["x"], max_size["y"], cs["x"], cs["y"]))


def cell_max_size_operation(dump, composition, cell_element_id, max_w, max_h, note=""):
    """SC1: build a SetCellMaxSize operation record from the layout dump, or refuse (OperationError) an unknown composition or cell, or a
    max the rules above refuse. The record is a CANDIDATE: it can be recorded, undone and previewed, and has no build path yet."""
    comp = next((c for c in dump.get("compositions") or [] if c.get("name") == composition), None)
    if comp is None:
        raise OperationError("unknown composition %r" % (composition,))
    cells = [c for c in dump.get("cells") or [] if c.get("composition") == composition and c.get("element_id") == cell_element_id]
    if not cells:
        raise OperationError("composition %s has no cell with element id %r" % (composition, cell_element_id))
    cell = cells[0]
    cfgs = [{"x": int(c["size_w"]), "y": int(c["size_h"])} for c in dump.get("cell_configs") or []
            if c.get("composition") == composition and c.get("cell_index") == cell["cell_index"]]
    if not cfgs:
        cfgs = [{"x": int(t["size"]["w"]), "y": int(t["size"]["h"])} for t in dump.get("tiles") or []
                if t.get("composition") == composition and t.get("cell_index") == cell["cell_index"]]
    design = {"w": int(cell["w"]), "h": int(cell["h"])}
    mx = {"x": max_w, "y": max_h}
    check_cell_max_size(mx, design, cfgs)
    cell_rec = {"composition": composition, "cell_index": cell["cell_index"], "cell_element_id": cell_element_id, "design": design,
                "config_sizes": cfgs, "max_size": mx}
    target = {"screen": composition, "logical_id": "%s|host:%s@%d" % (composition, cell_element_id, cell["cell_index"]),
              "structural_key": "%s|host:%s@%d" % (composition, cell_element_id, cell["cell_index"]),
              "locator": {"bundle": comp.get("bundle"), "bundle_sha256": None, "cab": None,
                          "path_id": str(comp.get("path_id")), "m_id": None},
              "guard": {"type": "Host", "name": cell_element_id, "classes": []}, "render_pos": None, "cell": cell_rec}
    original = {"value": {"x": int(cell.get("max_w", 0)), "y": int(cell.get("max_h", 0))}, "evidence": "directly serialized",
                "provenance": {"bundle": "ui-tileslayouts_assets_all.bundle", "field": "m_gridComponents.m_maxSize"}}
    op = new_operation("SetCellMaxSize", target, {}, original=original, note=note)
    op["label"] = "Set %s max size %dx%d -> %dx%d in %s" % (cell_element_id, original["value"]["x"], original["value"]["y"], max_w, max_h, composition)
    op["validation"] = validate(op)
    return op


def validate(op):
    """Translate-or-refuse: returns the operation's VALIDATION record {ok, translation, safety, scope, findings} or
    raises OperationError with the precise reason. The translation names the existing project-model fragment and
    writer; it never invents one. The plan-level checks (overlap, dependency impact) run where they already live:
    the 4D `buildplan.review` at build/review time - this validation is the operation's own shape, target and
    REACH policy. Nothing here ever calls a reach of one a value edit when it was not measured."""
    kind, tgt, new = op["kind"], op.get("target") or {}, op.get("new") or {}
    findings = []
    loc = tgt.get("locator") or {}
    guard = tgt.get("guard") or {}
    if not isinstance(tgt.get("logical_id"), str) or not tgt.get("logical_id"):
        raise OperationError("an operation needs the target's logical id (the UiDocument identity)")
    if not loc.get("bundle") or not loc.get("path_id"):
        raise OperationError("an operation needs the target's physical locator (bundle and path id) so it can be "
                             "re-resolved against a newer build")
    if not isinstance(guard.get("type"), str) or not guard.get("type"):
        raise OperationError("an operation needs the target's type/name guard (the tier-2 key for rebase: names "
                             "repeat, positions shift, so identity alone is not enough)")
    if kind in ("ResizeNode", "ReorderNode"):
        if kind == "ReorderNode":
            raise OperationError("%s is refused: no supported writer changes sibling order; the game derives it from "
                                 "the layout. This edit can be previewed in the Playground but never built" % kind)
        cell = tgt.get("cell")
        if not isinstance(cell, dict) or not isinstance(cell.get("composition"), str) or not cell.get("composition") \
                or not isinstance(cell.get("cell_index"), int) or isinstance(cell.get("cell_index"), bool):
            raise OperationError("ResizeNode needs the cell it resizes: {composition, cell_index} (the writer edits "
                                 "that cell's m_location and m_maxSize on the composition asset)")
        if not isinstance(cell.get("cell_element_id"), str) or not cell.get("cell_element_id"):
            raise OperationError("ResizeNode needs the cell's element id as a guard (element ids are not unique)")
        geo = cell.get("geometry")
        if not isinstance(geo, dict) or set(geo) != set(GEO) or not all(isinstance(geo[k], int) and not isinstance(geo[k], bool)
                                                                       for k in GEO):
            raise OperationError("ResizeNode needs integer x, y, w, h grid units")
        if geo["x"] < 0 or geo["y"] < 0 or geo["w"] <= 0 or geo["h"] <= 0:
            raise OperationError("a cell cannot be resized to a negative position or a non-positive size")
        mx = cell.get("max_size")
        if not isinstance(mx, dict) or set(mx) != {"x", "y"} or not all(isinstance(mx[k], int) and not isinstance(mx[k], bool)
                                                                       for k in ("x", "y")):
            raise OperationError("ResizeNode needs the cell's new m_maxSize as {x, y} integers (the writer sets "
                                 "m_location and m_maxSize on the composition asset; measured in third-party 27.1 skins)")
        cs = cell.get("config_size")
        if cs is not None:
            if not isinstance(cs, dict) or set(cs) != {"x", "y"} or not all(isinstance(cs[k], int) and not isinstance(cs[k], bool)
                                                                            for k in ("x", "y")):
                raise OperationError("ResizeNode's config_size must be {x, y} integers")
            if geo["w"] < cs["x"] or geo["h"] < cs["y"]:
                raise OperationError("shrinking below the tile's configured size is refused: the tile's configuration "
                                     "is %dx%d and the resize asks for %dx%d (the writer does not rewrite the "
                                     "configuration list)" % (cs["x"], cs["y"], geo["w"], geo["h"]))
        findings.append("BUILDABLE enlargement: the writer (m_location + m_maxSize on the composition asset, config "
                        "size unchanged) was proven at runtime by Test C on 2026-11-20 - the game rendered the "
                        "resized tile at the predicted 4-row height. A resize that shrinks below the tile's "
                        "configured size is refused.")
        findings.append("this edits %s only; the active composition depends on the window width (Stage 3E), so the "
                        "resize only takes effect at window sizes where that composition is active" % cell["composition"])
        findings.append("the backend overlap gate (the D2 placement check, no overlap against the composition's cells) "
                        "runs as the resize is made and again at review/build time")
        return {"ok": True, "translation": {"fragment": "placement", "writer": "the 5I resize writer (m_location + "
                "m_maxSize on the composition asset); the D2 overlap gate runs at review/build time",
                "candidate": False, "runtime_test": "passed: resize, Test C, 2026-11-20 (enlargement, config unchanged)"},
                "safety": "value", "scope": {"elements": 1, "layouts": 1, "screens": 1, "scope_change": False,
                                             "note": "one cell of one composition; guarded by the cell's element id"},
                "findings": findings}
    if kind == "AddCell":
        cell = tgt.get("cell")
        if not isinstance(cell, dict) or not isinstance(cell.get("composition"), str) or not cell.get("composition"):
            raise OperationError("AddCell needs the composition it adds a cell to")
        if not isinstance(cell.get("cell_element_id"), str) or not cell.get("cell_element_id"):
            raise OperationError("AddCell needs a NEW element id for the cell; the backend checks it is unique within "
                                 "the composition (no existing cell carries it)")
        if not isinstance(cell.get("cell_index"), int) or isinstance(cell.get("cell_index"), bool) or cell["cell_index"] < 0:
            raise OperationError("AddCell needs the new cell's index (a non-negative integer)")
        geo = cell.get("geometry")
        if not isinstance(geo, dict) or set(geo) != set(GEO) or not all(isinstance(geo[k], int) and not isinstance(geo[k], bool)
                                                                       for k in GEO):
            raise OperationError("AddCell needs integer x, y, w, h grid units")
        if geo["x"] < 0 or geo["y"] < 0 or geo["w"] <= 0 or geo["h"] <= 0:
            raise OperationError("a cell cannot be added at a negative position or with a non-positive size")
        desc = cell.get("description")
        if not isinstance(desc, dict) or not (desc.get("path_id") or desc.get("id")) \
                or not isinstance(desc.get("config_index"), int) or isinstance(desc.get("config_index"), bool) or desc["config_index"] < 0:
            raise OperationError("AddCell must reuse an EXISTING tile description and configuration: name the "
                                 "description (its path id in the composition's bundle, or its id) and the "
                                 "configuration index; a new description is an identity and reference change (D1')")
        findings.append("BUILDABLE when the runtime's PACKING rule lands the cell at the requested row (proven by "
                        "Test C+D on 2026-11-20: cells are packed vertically per column, not clamped). A placement "
                        "the runtime would move (or that overlaps) is refused with the packed row named.")
        findings.append("the backend checks run as the gesture is made and at review/build: the new element id is "
                        "unique within the composition (grid, optional slices and placement bindings), the new "
                        "cell reuses its configuration's own size, the rectangle overlaps no cell, and the named "
                        "description and configuration exist")
        findings.append("this edits %s only; the active composition depends on the window width (Stage 3E)" % cell["composition"])
        return {"ok": True, "translation": {"fragment": "placement", "writer": "the 5I add-cell writer (a new cell of "
                "the composition asset reusing the named description and configuration); the packing, overlap and "
                "uniqueness checks run at review/build time", "candidate": False,
                "runtime_test": "passed: add-cell, Test C+D, 2026-11-20 (packing rule)"},
                "safety": "value", "scope": {"elements": 1, "layouts": 1, "screens": 1, "scope_change": False,
                                             "note": "one added cell of one composition; guarded by the new element id"},
                "findings": findings}
    if kind == "SwapTile":
        cell = tgt.get("cell")
        if not isinstance(cell, dict) or not isinstance(cell.get("composition"), str) or not cell.get("composition") \
                or not isinstance(cell.get("cell_element_id"), str) or not cell.get("cell_element_id"):
            raise OperationError("SwapTile needs the cell it changes: {composition, cell_element_id}")
        tile = new.get("tile")
        if not isinstance(tile, dict) or not isinstance(tile.get("name"), str) or not tile["name"] \
                or not isinstance(tile.get("size"), dict) or not all(isinstance(tile["size"].get(k), int) and not isinstance(tile["size"].get(k), bool) and tile["size"][k] > 0 for k in ("x", "y")):
            raise OperationError("SwapTile needs the new tile by description name and configuration size: {tile: {name, size: {x, y}}}")
        findings.append("CANDIDATE on the bundle route; PROVEN on the custom-layout route (%s): the cell's tile changes by description name from the composition's own tile set; "
                        "its slot (location, min and max size) stays" % PROVEN_ON_JSON["SwapTile"])
        return {"ok": True, "translation": {"fragment": "cell_tiles", "writer": "custom_layouts.swap_cell (custom-layout file)", "candidate": True,
                "runtime_test": "passed on the custom-layout route: " + PROVEN_ON_JSON["SwapTile"]},
                "safety": "candidate", "scope": {"elements": 1, "layouts": 1, "screens": 1, "scope_change": False,
                                                 "note": "one cell's tile of one composition; guarded by the cell's element id"},
                "findings": findings}
    if kind == "SetCellMaxSize":
        cell = tgt.get("cell")
        if not isinstance(cell, dict) or not isinstance(cell.get("composition"), str) or not cell.get("composition") \
                or not isinstance(cell.get("cell_element_id"), str) or not cell.get("cell_element_id"):
            raise OperationError("SetCellMaxSize needs the cell it changes: {composition, cell_element_id}")
        design = cell.get("design")
        if not isinstance(design, dict) or not all(isinstance(design.get(k), int) and not isinstance(design.get(k), bool) for k in ("w", "h")):
            raise OperationError("SetCellMaxSize needs the cell's design size {w, h} (read from the composition)")
        check_cell_max_size(cell.get("max_size"), design, cell.get("config_sizes") or [])
        findings.append("CANDIDATE, preview only: %s. The edit would change one cell's m_maxSize on %s, nothing else; "
                        "it has no writer and no runtime test" % (NO_BUILD_PATH, cell["composition"]))
        return {"ok": True, "translation": {"fragment": "cell_max_sizes", "writer": None, "candidate": True,
                "runtime_test": "none: " + NO_BUILD_PATH},
                "safety": "candidate", "scope": {"elements": 1, "layouts": 1, "screens": 1, "scope_change": False,
                                                 "note": "one cell's m_maxSize of one composition; guarded by the cell's element id"},
                "findings": findings}
    if kind == "SetOptionalSlots":
        op_ = new.get("op")
        direction = new.get("direction") or "m_bottom"
        if not isinstance(direction, str) or not direction.startswith("m_"):
            raise OperationError("SetOptionalSlots needs a slice region such as m_bottom or m_right")
        if op_ == "add-slot":
            if not isinstance(new.get("element_id"), str) or not new["element_id"]:
                raise OperationError("adding an optional slot needs the new element id")
            desc = new.get("description")
            if not isinstance(desc, dict) or not desc.get("path_id") or not isinstance(desc.get("config_index"), int):
                raise OperationError("adding an optional slot must reuse an EXISTING description and configuration "
                                     "from the composition's own set: name {path_id, config_index}")
        elif op_ == "remove-slot":
            if not isinstance(new.get("element_id"), str) or not new["element_id"]:
                raise OperationError("removing an optional slot needs the element id")
        elif op_ == "reorder-slot":
            order = new.get("order")
            if not isinstance(order, list) or not order or not all(isinstance(x, str) and x for x in order):
                raise OperationError("reordering optional slots needs the region's element ids in the new order")
        else:
            raise OperationError("SetOptionalSlots needs op add-slot, remove-slot or reorder-slot")
        promoted = (new.get("composition") == "SquadComposition-Large" and direction == "m_bottom"
                    and op_ in ("add-slot", "remove-slot", "reorder-slot"))
        if promoted:
            findings.append("BUILDABLE for the measured case: add, remove-only and reorder of bottom optional "
                            "slots on SquadComposition-Large at 2560x1440 Small. Other compositions, settings and "
                            "regions are not claimed (m_right is untested).")
        else:
            findings.append("CANDIDATE: remove-only and reorder stay preview-only. A replace (remove plus add) on "
                            "SquadComposition-Large's m_bottom is promoted when the build pairs the remove with its "
                            "add; this record alone is not the measured add/replace case.")
            findings.append("the grid cells and design bottom are never touched by this operation")
        return {"ok": True, "translation": {"fragment": "optional_slots", "region": direction,
                "writer": "the 5I optional-slot writer (m_optionalSlices only; the grid cells and design bottom are "
                          "untouched)", "candidate": not promoted,
                "runtime_test": ("passed: SetOptionalSlots, m_bottom at 2560x1440 Small (2026-11-20)" if promoted
                                 else "optional slots (not the measured add/replace case)")},
                "safety": "value" if promoted else "candidate",
                "scope": {"elements": 1, "layouts": 0, "screens": 1, "scope_change": False,
                          "note": "one optional slot of one composition"},
                "findings": findings}
    if kind == "MoveNode":
        cell = tgt.get("cell")
        if not isinstance(cell, dict) or not isinstance(cell.get("composition"), str) or not cell.get("composition") \
                or not isinstance(cell.get("cell_index"), int) or isinstance(cell.get("cell_index"), bool):
            raise OperationError("MoveNode is refused: only a composition CELL has a writer (tiles.apply_ops), and the "
                                 "target must name {composition, cell_index}; a generic element move has no writer")
        if not isinstance(cell.get("cell_element_id"), str) or not cell.get("cell_element_id"):
            raise OperationError("MoveNode needs the cell's element id as a guard: element ids are not unique (Team "
                                 "Instructions cells 2 and 3 share one), so (composition, cell_index) alone cannot "
                                 "prove it is still the same cell")
        geo = cell.get("geometry")
        if not isinstance(geo, dict) or set(geo) != set(GEO) or not all(isinstance(geo[k], int) and not isinstance(geo[k], bool)
                                                                       for k in GEO):
            raise OperationError("MoveNode needs integer x, y, w, h grid units (the same shape the placement store takes)")
        if geo["x"] < 0 or geo["y"] < 0 or geo["w"] <= 0 or geo["h"] <= 0:
            raise OperationError("a cell cannot be moved to a negative position or given a non-positive size")
        findings.append("this edits %s only; the active composition depends on the window width (Stage 3E), so the "
                        "change does nothing at other breakpoints" % cell["composition"])
        findings.append("the overlap gate checks the composition's own cells (m_gridComponents); optional slices the "
                        "game adds at runtime are outside it (measured on Team Instructions), so a move into a region a "
                        "runtime slot later fills can pass validation and still overlap in game")
        return {"ok": True, "translation": {"fragment": "placement", "writer": "tiles.apply_ops (through the stored "
                "placement edit and the build plan; the D2 overlap gate runs at review/build time)"},
                "safety": "value", "scope": {"elements": 1, "layouts": 1, "screens": 1, "scope_change": False,
                                             "note": "one cell of one composition; guarded by the cell's element id"},
                "findings": findings}
    if kind == "ReplaceToken":
        token, value = new.get("token"), new.get("value")
        if not isinstance(token, str) or not TOKEN.fullmatch(token):
            raise OperationError("ReplaceToken needs a --token name")
        from . import project as project_mod
        try:
            project_mod.check_value(value)
        except ValueError as e:
            raise OperationError("ReplaceToken: %s" % e)
        _require_route(new, "token", "ReplaceToken")
        findings.append("a token change reaches every rule that uses the token, on every screen that paints with it; "
                        "the token's screens are listed by where.token at review time")
        return {"ok": True, "translation": {"fragment": "token_overrides", "writer": "token_patch.SheetPatcher"},
                "safety": "value", "scope": {"elements": None, "layouts": None, "screens": None, "scope_change": True,
                                             "note": "every user of the token changes (unmeasured here; the review "
                                                     "lists the token's screens) - always a scope the user must see"},
                "findings": findings}
    if kind == "ReplaceAsset":
        swap = new.get("swap") or {}
        if swap.get("kind") not in ("texture", "svg", "icon"):
            raise OperationError("ReplaceAsset needs kind texture, svg or icon (the writers the 4D adapters wrap)")
        if not isinstance(swap.get("source"), str) or not SOURCE_FILE.fullmatch(swap["source"]):
            raise OperationError("ReplaceAsset needs a source file name (png, jpg, webp or svg)")
        if not loc.get("bundle") or not loc.get("path_id"):
            raise OperationError("ReplaceAsset needs the target asset's bundle and path id (its provenance)")
        note = "the writable formats and the Crunch/mips limits are the 4D texture adapter's; they are checked at build"
        return {"ok": True, "translation": {"fragment": "image_swaps", "writer": "images.apply_swaps / the icon atlas route"},
                "safety": "value", "scope": {"elements": 1, "layouts": None, "screens": None, "scope_change": False,
                                             "note": "one asset object; every element that draws it changes with it"},
                "findings": [note]}
    if kind in ("SetColor", "SetStyle", "SetSpacing", "SetVisibility"):
        rule = new.get("rule") or {}
        props = rule.get("props") or {}
        sheet, selector = rule.get("sheet"), rule.get("selector")
        if not isinstance(sheet, dict) or not sheet.get("name") or not sheet.get("bundle"):
            raise OperationError("%s needs the sheet its scoped rule will live on, keyed by (bundle, name): a sheet "
                                 "named 'default' exists in more than one bundle, so a bare name is ambiguous" % kind)
        if not isinstance(selector, str) or not selector:
            raise OperationError("%s needs a selector (built from the element's own class/hierarchy evidence)" % kind)
        from . import project as project_mod, token_patch as tp
        for k, v in props.items():
            if not k.startswith("--") and k not in tp.PROP_TABLE:
                raise OperationError("unknown property %r: the game's verified property table does not hold it" % k)
            if kind == "SetColor" and k not in ("color", "background-color", "border-color", "-unity-background-image-tint-color"):
                raise OperationError("SetColor changes a colour property, not %r" % k)
            if kind == "SetSpacing" and not SPACING.fullmatch(k):
                raise OperationError("SetSpacing changes a spacing property (margin/padding/border widths), not %r" % k)
            if kind == "SetVisibility" and k not in VISIBILITY_PROPS:
                raise OperationError("SetVisibility changes visibility or display, not %r" % k)
            try:
                project_mod.check_value(v)
            except ValueError as e:
                raise OperationError("%s: property %s: %s" % (kind, k, e))
        try:
            project_mod.check_selector(selector)
        except ValueError as e:
            raise OperationError("%s: %s" % (kind, e))
        _check_original_rule_provenance(op)
        reach, scope_change, safety = _require_reach(rule, kind)
        findings += _reach_findings(scope_change, selector)
        if kind == "SetColor":
            _require_route(new, "scoped_rule", "SetColor")
        if kind == "SetVisibility":
            findings.append("a sheet visibility/display rule can be overridden by inline styles set by code at "
                            "runtime - on the measured Team Instructions screen 26 of 58 nodes carry learned runtime "
                            "classes - so the effect of this operation is RUNTIME-DEPENDENT, not guaranteed")
        return {"ok": True, "translation": {"fragment": "scoped_rules", "writer": "patcher.patch_sheet (append or the "
                "declared replace); the structural gate checks every rule",
                "effect_evidence": "runtime-dependent" if kind == "SetVisibility" else "computed by the reconstruction engine"},
                "safety": safety, "scope": {"elements": reach["elements"], "layouts": reach["layouts"],
                                            "screens": reach["screens"], "scope_change": scope_change,
                                            "note": reach.get("note", "measured by the style and layout indexes")},
                "findings": findings}
    raise OperationError("unknown operation kind %r" % kind)


def _require_reach(rule, kind):
    """A scoped rule without a MEASURED reach is not a value edit: a selector cannot point at one node (names
    repeat; a third of named elements share type+name), so the reach must come from the style and layout indexes
    (the engine's layout.reach). Reach above one element is a scope change the user must see."""
    reach = rule.get("reach")
    if not isinstance(reach, dict) or not isinstance(reach.get("elements"), int) \
            or not isinstance(reach.get("layouts"), int) or not isinstance(reach.get("screens"), int) \
            or not reach.get("measured_by"):
        raise OperationError("%s is refused: the selector's reach was not measured. A scoped rule changes every "
                             "element its selector matches on every screen, so measure the reach first (the engine's "
                             "layout.reach, against the style and layout indexes) and record it on the operation" % kind)
    scope_change = reach["elements"] > 1
    safety = "scope" if scope_change else "value"
    return reach, scope_change, safety


def _reach_findings(scope_change, selector):
    if scope_change:
        return ["scope change: the selector %s reaches more than the selected element; every element it matches, on "
                "every screen, changes with this edit - the user must see and accept the scope" % selector]
    return ["the selector reaches only the measured element(s); still re-checked at review time"]


def _require_route(new, route, kind):
    """A colour change that could go through a token or through a scoped rule must record which route was chosen
    and why: the two have different reach."""
    r = new.get("route")
    if not isinstance(r, dict) or r.get("chosen") != route or not r.get("reason"):
        raise OperationError("%s needs its route recorded: chosen %r with a reason. A colour can go through the "
                             "token (every user of it changes) or through a scoped rule (the selector's reach); the "
                             "two are not interchangeable" % (kind, route))
    if route == "token" and r.get("chosen") != "token":
        raise OperationError("route mismatch")


def _check_original_rule_provenance(op):
    """Rules are keyed by (bundle, sheet, selector, occurrence) - never by index: rule indices kept the same content
    at only 153 of 5510 positions between two builds, and a sheet named 'default' exists in two bundles."""
    prov = ((op.get("original") or {}).get("provenance") or {})
    if isinstance(prov.get("rule"), int):
        raise OperationError("the original value cites a rule by INDEX; rule indices are not stable across builds. "
                             "Key it by {bundle, sheet, selector, occurrence} instead")
    if prov.get("sheet") and not prov.get("bundle"):
        raise OperationError("the original value cites a sheet by name only; a sheet named 'default' exists in two "
                             "bundles, so the provenance must name the bundle too")


# ---------------------------------------------------------------- the session
def new_session(project, screen, game_build=None):
    return {"schema": SCHEMA, "project": project, "screen": screen, "game_build": game_build,
            "created_utc": _now(), "modified_utc": _now(), "operations": [], "preview": {}, "notes": ""}


def add(session, op):
    """Validate, record supersession, append. The newest operation on the same (kind, target, property-key) supersedes
    the earlier one; both records say so - a conflict is never resolved silently."""
    v = validate(op)
    op["validation"] = v
    key = _conflict_key(op)
    for older in session["operations"]:
        if _conflict_key(older) == key and older.get("state") == "applied":
            older["state"], older["superseded_by"] = "superseded", op["id"]
            older["modified_utc"] = _now()
    session["operations"].append(op)
    session["modified_utc"] = _now()
    return op


def _conflict_key(op):
    tgt, new = op.get("target") or {}, op.get("new") or {}
    if op["kind"] == "ReplaceToken":
        prop = new.get("token")
    elif op["kind"] in ("MoveNode", "ResizeNode", "AddCell"):
        prop = (tgt.get("cell") or {}).get("cell_index")
    elif op["kind"] in ("SetCellMaxSize", "SwapTile"):
        prop = (tgt.get("cell") or {}).get("cell_element_id")
    elif op["kind"] == "ReplaceAsset":
        prop = (tgt.get("locator") or {}).get("path_id")
    else:
        prop = ",".join(sorted((new.get("rule") or {}).get("props") or {}))
    return (op["kind"], tgt.get("logical_id"), prop)


def effective(session):
    """The operations that build: applied, not superseded, in order. Superseded and reverted records stay in the
    history (nothing is ever deleted)."""
    return [o for o in session["operations"] if o.get("state") == "applied"]


def undo(session, op_id_=None):
    """Mark the newest applied operation (or the named one) reverted. The record stays; the build no longer sees it."""
    ops = [o for o in session["operations"] if o.get("state") == "applied" and (op_id_ is None or o["id"] == op_id_)]
    if not ops:
        raise OperationError("nothing to undo")
    op = ops[-1]
    op["state"], op["modified_utc"] = "reverted", _now()
    session["modified_utc"] = _now()
    return op


def redo(session, op_id_):
    op = next((o for o in session["operations"] if o["id"] == op_id_), None)
    if op is None:
        raise OperationError("no such operation: %s" % op_id_)
    if op.get("state") == "superseded":
        raise OperationError("operation %s was superseded by %s; re-do the newer edit instead" % (op_id_, op.get("superseded_by")))
    op["state"], op["modified_utc"] = "applied", _now()
    session["modified_utc"] = _now()
    return op


def revert_all(session):
    for op in effective(session):
        op["state"], op["modified_utc"] = "reverted", _now()
    session["modified_utc"] = _now()


# ---------------------------------------------------------------- projection (the bridge to build and render)
def project_onto(project, session, route_preference=None):
    """The effective operations as the EXISTING project-model fragments: token_overrides, declaration_edits,
    scoped_rules, image_swaps and the placement-edit geometry records. This is the one bridge - the render overlay
    and the build both consume the project model exactly as they do today. The project model addresses a scoped
    rule by sheet NAME (its own convention); the operation keeps the bundle-keyed identity for rebase, and the
    projection notes the bundle in the record. Idempotent per session: fragments are rebuilt from the operation
    list, never accumulated.

    route_preference (project setting, DEFAULT skin_folder) decides the shape of a value edit:
      - bundle: ReplaceToken -> token_overrides (flagged with BOTH style bundles); SetColor/SetSpacing on a
        joined node -> declaration_edits (the winning declaration's handle, with its expanded-tree reach);
      - skin-folder (and appended scoped rules in either mode): token_overrides / scoped_rules as before.
    """
    if route_preference is None:
        from . import project as project_mod
        route_preference = project_mod.route_preference(project)
    frags = {"token_overrides": [], "declaration_edits": [], "scoped_rules": [], "image_swaps": [], "placements": [], "cell_max_sizes": [], "cell_tiles": []}
    for op in effective(session):
        kind, new, tgt = op["kind"], op.get("new") or {}, op.get("target") or {}
        route = route_of(op, route_preference)["route"]
        if kind == "ReplaceToken":
            frag = {"token": new["token"], "value": new["value"]}
            if route == "bundle":
                frag["bundles"] = list(TOKEN_BUNDLES)
                frag["unverified_bundles"] = [COMMON_TOKEN_BUNDLE]
            frags["token_overrides"].append(frag)
        elif kind in ("SetColor", "SetSpacing") and route == "bundle":
            frags["declaration_edits"].append(declaration_edit(op))
        elif kind in ("SetColor", "SetStyle", "SetSpacing", "SetVisibility"):
            rule = new["rule"]
            frags["scoped_rules"].append({"sheet": rule["sheet"]["name"], "selector": rule["selector"],
                                          "props": dict(rule["props"]),
                                          "playground_bundle": rule["sheet"]["bundle"]})
        elif kind == "ReplaceAsset":
            loc = tgt["locator"]
            frags["image_swaps"].append({"bundle": loc["bundle"], "path_id": str(loc["path_id"]),
                                         "kind": new["swap"]["kind"], "source": new["swap"]["source"],
                                         "name": tgt.get("name") or ""})
        elif kind == "MoveNode":
            cell = tgt["cell"]
            frags["placements"].append({"composition": cell["composition"], "cell_index": cell["cell_index"],
                                        "geometry": dict(cell["geometry"]),
                                        "cell_element_id": cell["cell_element_id"]})
        elif kind == "SwapTile":
            cell = tgt["cell"]
            frags["cell_tiles"].append({"composition": cell["composition"], "cell_element_id": cell["cell_element_id"], "tile": dict(new["tile"]), "candidate": "swap-tile"})
        elif kind == "SetCellMaxSize":
            cell = tgt["cell"]
            frags["cell_max_sizes"].append({"composition": cell["composition"], "cell_index": cell.get("cell_index"),
                                            "cell_element_id": cell["cell_element_id"], "max_size": dict(cell["max_size"]),
                                            "candidate": "set-cell-max-size"})
        elif kind == "ResizeNode":
            cell = tgt["cell"]
            frags["placements"].append({"composition": cell["composition"], "cell_index": cell["cell_index"],
                                        "geometry": dict(cell["geometry"]), "cell_element_id": cell["cell_element_id"],
                                        "max_size": dict(cell["max_size"]), "candidate": "resize"})
        elif kind == "AddCell":
            cell = tgt["cell"]
            frags["placements"].append({"composition": cell["composition"], "cell_index": cell["cell_index"],
                                        "geometry": dict(cell["geometry"]), "cell_element_id": cell["cell_element_id"],
                                        "description": dict(cell["description"]), "candidate": "add-cell"})
    return frags


# ---------------------------------------------------------------- persistence (the session file; no game file is ever touched)
def session_path(folder):
    return Path(folder) / "edits" / "playground.json"


def save(folder, session):
    """Write the session atomically. `folder` is the PROJECT folder (a workspace path, never a game path)."""
    p = session_path(folder)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_name(p.name + ".tmp")
    tmp.write_text(json.dumps(dict(session, modified_utc=_now()), indent=1), encoding="utf-8")
    os.replace(tmp, p)
    return p


def load(folder):
    """Load and RE-VALIDATE: every applied operation is checked again; one that no longer validates raises
    OperationError naming it (the session is not silently applied). Stale provenance (a different game build) marks
    the operation stale rather than refusing the whole session - the newer build may still resolve the target."""
    p = session_path(folder)
    d = json.loads(p.read_text(encoding="utf-8-sig"))
    if d.get("schema") != SCHEMA:
        raise OperationError("the playground session is schema %r, expected %s" % (d.get("schema"), SCHEMA))
    for op in d.get("operations") or []:
        try:
            validate(op)
        except OperationError as e:
            raise OperationError("session operation %s (%s) no longer validates: %s" % (op.get("id"), op.get("kind"), e))
    return d


def export(session):
    """The portable form: the full session dict (operations carry their provenance and validation). Import is `load`
    semantics on a folder, or `json.loads` + revalidation by the caller."""
    return json.dumps(session, indent=1)


def mark_stale(session, game_build):
    """DEPRECATED blanket form, kept only for callers that have no new-build index: a different game build marks
    every applied operation stale. `rebase` is the real resolution: tiers, guards and a per-operation report."""
    stale = []
    if session.get("game_build") and game_build and session["game_build"] != game_build:
        for op in session["operations"]:
            if op.get("state") == "applied":
                op["state"], op["modified_utc"] = "stale", _now()
                stale.append(op["id"])
    return stale


def rebase(session, resolve, game_build):
    """Resolve every applied operation against a NEWER build, in tiers, through a caller-supplied resolver (the new
    build's document index - this module never reads bundles). The resolver maps one operation's target to
    {"status": "matched", "tier": 1|2, "logical_id": the new id} | {"status": "ambiguous", "tier": 2, "candidates":
    [...]} | {"status": "unresolved"}. Tier 1 is the logical id; tier 2 is the (layout GUID, type, name) guard with
    the class guard as a tiebreak - the measured fallback (71.5% tier-1 across the 983 changed layouts, 63-67%
    unique at tier 2). The report separates matched / ambiguous / unresolved exactly as Gate B does; matched
    operations carry their new identity, ambiguous and unresolved ones are marked stale and NEVER applied."""
    report = {"matched": [], "ambiguous": [], "unresolved": []}
    for op in effective(session):
        r = resolve(op)
        if not isinstance(r, dict) or r.get("status") not in ("matched", "ambiguous", "unresolved"):
            raise OperationError("the rebase resolver must answer matched, ambiguous or unresolved for %s" % op["id"])
        if r["status"] == "matched":
            if r.get("logical_id"):
                op["target"]["logical_id"] = r["logical_id"]
                op["target"]["structural_key"] = r.get("structural_key") or op["target"].get("structural_key")
            op.setdefault("rebased", []).append({"from_build": session.get("game_build"), "to_build": game_build,
                                                "tier": r.get("tier"), "utc": _now()})
            report["matched"].append({"id": op["id"], "tier": r.get("tier")})
        elif r["status"] == "ambiguous":
            op["state"], op["modified_utc"] = "stale", _now()
            op["stale_reason"] = "ambiguous against build %s: the tier-2 guard names more than one node (%s)" % (
                game_build, ", ".join((r.get("candidates") or [])[:4]))
            report["ambiguous"].append({"id": op["id"], "candidates": r.get("candidates") or []})
        else:
            op["state"], op["modified_utc"] = "stale", _now()
            op["stale_reason"] = "unresolved against build %s: neither the logical id nor the type/name guard " \
                                  "matched a node of the new build" % game_build
            report["unresolved"].append({"id": op["id"]})
    session["game_build"] = game_build
    session["modified_utc"] = _now()
    return report
