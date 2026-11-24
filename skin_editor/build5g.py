"""Stage 5G: the Playground session as a reviewed build (docs/rea/STAGE-5G-BUILD-INTEGRATION-REPORT.md).

Every routing decision is the backend's and is recorded with its reason:
  - token overrides and scoped rules -> the SKIN-FOLDER route (native skin; changes no game file),
  - tile MoveNode and ResizeNode -> the BUNDLE route (the composition's own bundle, from the SERIALIZED
    composition index); a resize is buildable only when it does not shrink below the tile's configured size,
  - AddCell -> the BUNDLE route when the runtime's PACKING rule lands it at the requested row (Test C+D); a
    placement the runtime would move is refused with the packed row named,
  - every other kind -> refused with its reason.

The build reads ONLY a verified stock source (never the live game folder), checks the source identity and each
operation's locator, refuses stale/unresolved operations, detects same-cell conflicts and the overlap gate on the
composition as it stands after all moves, rebuilds ONLY the target bundles, reports the referrer bundles as
affected, compares the built bundle's cell layer with the intended MoveNode operations exactly, and writes a
schema-2 manifest + package. Two builds of the same session from the same source are byte-identical.
"""
import hashlib
import json
import time
import tempfile
from pathlib import Path

from . import playops, tiles
from .render import compositionset

CANDIDATES = ("SetOptionalSlots",)
SKIN_KINDS = ("ReplaceToken", "SetColor", "SetStyle", "SetSpacing", "SetVisibility")
SCHEMA = "fm-buildsession/1"


def _loc(value):
    """A cell location as {x, y} (and w, h for a resize) whether the cell layer reports a dict or a tuple."""
    if isinstance(value, (tuple, list)):
        out = {"x": value[0], "y": value[1]}
        if len(value) > 3:
            out.update({"w": value[2], "h": value[3]})
        return out
    return dict(value or {})


def _sha(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _project_layout_route(ws, session, override=None, project=None):
    """The route of LAYOUT operations: an explicit override, else the project's layout_route (default custom_layout), else the legacy 'bundle' when there is no project at all."""
    if override:
        if override not in ("custom_layout", "bundle"):
            raise ValueError("layout_route must be 'custom_layout' or 'bundle'")
        return override
    from . import project as project_mod
    if project is not None:
        return project_mod.layout_route(project)
    if ws is None or not session.get("project"):
        return "bundle"
    try:
        return project_mod.layout_route(project_mod.load(ws, str(session["project"])))
    except Exception:
        return "bundle"


def _slot_replace_ids(session):
    """The ids of the SetOptionalSlots operations that form a REPLACE (exactly one remove-slot and one add-slot in the same composition and region): the only slot edit proven on
    the custom-layout route (JX X3). Everything else stays a candidate there: 'proven on the bundle route only'."""
    groups = {}
    for op in playops.effective(session):
        if op.get("kind") != "SetOptionalSlots":
            continue
        new = op.get("new") or {}
        groups.setdefault((new.get("composition") or (op.get("target") or {}).get("screen"), new.get("direction") or "m_bottom"), []).append(op)
    ok = set()
    for ops in groups.values():
        kinds = sorted((o.get("new") or {}).get("op") for o in ops)
        if kinds == ["add-slot", "remove-slot"]:
            ok.update(o.get("id") for o in ops)
    return ok


def _project_route_preference(ws, session, override=None, project=None):
    """The project's EFFECTIVE route_preference (a choice only when explicit, else the bundle default). Explicit
    overrides win; otherwise the given project dict, or the project file named by the session, is read. A
    missing/legacy project keeps the default."""
    if override:
        if override not in playops.ROUTE_PREFERENCES:
            raise ValueError("route_preference must be one of: " + ", ".join(playops.ROUTE_PREFERENCES))
        return override
    from . import project as project_mod
    if project is not None:
        return project_mod.route_preference(project)
    if ws is None or not session.get("project"):
        return playops.DEFAULT_ROUTE_PREFERENCE
    try:
        p = project_mod.load(ws, str(session["project"]))
        return project_mod.route_preference(p)
    except Exception:
        return playops.DEFAULT_ROUTE_PREFERENCE


def _route(op, *, images_dir=None, aa_dir=None, route_preference=playops.DEFAULT_ROUTE_PREFERENCE, layout_route="bundle"):
    """(route, reason) by what has been PROVEN, for the project's route_preference.

    skin_folder (DEFAULT): value edits write the skin folder only; tile geometry takes the bundle route.
    bundle: ReplaceToken edits both style bundles; SetColor/SetSpacing on a joined node edit the winning
    declaration in place; appended scoped rules (SetStyle/SetVisibility and colour/spacing without a winning
    declaration) STAY on the skin-folder route. ReplaceAsset's Simple-mode picture writer is unchanged."""
    kind = op.get("kind")
    if layout_route == "custom_layout" and kind in playops.LAYOUT_KINDS:       # ST1: layout operations take the game's own custom-layout files
        r = playops.route_of(op, route_preference, "custom_layout")
        return ("custom_layout", r["reason"]) if r["route"] == "custom_layout" else ("refused", r["reason"])
    if kind == "SetCellMaxSize":
        return "refused", playops.NO_BUILD_PATH
    if kind == "SwapTile":
        return "refused", "SwapTile has no bundle writer; it is proven on the custom-layout route only"
    if route_preference == "bundle":
        rule = (op.get("new") or {}).get("rule") or {}
        if kind in ("SetColor", "SetStyle", "SetSpacing", "SetVisibility") and rule.get("op") == "remove":
            return "refused", ("the skin-folder writer cannot express a remove (USS cannot delete a game "
                               "declaration); the per-declaration bundle writer changes a value, it does not "
                               "remove a rule")
        if kind == "ReplaceToken":
            return "bundle", ("the token override rewrites every definition of the token in both style bundles; "
                              "the common bundle's replacement is %s" % playops.COMMON_BUNDLE_LABEL)
        if kind in ("SetColor", "SetSpacing"):
            handle = playops.declaration_edit(op)
            if handle:
                return "bundle", ("the per-declaration writer edits the winning declaration %s #%d %s in %s; "
                                  "its expanded-tree reach is %s element(s)" %
                                  (handle["selector"], handle["occurrence"], handle["property"], handle["bundle"],
                                   (handle["reach"] or {}).get("elements")))
            return "skin-folder", ("an appended scoped rule (no winning-declaration provenance) stays on the "
                                   "skin-folder route; it appends a rule, which the bundle writer does not do")
        if kind in ("SetStyle", "SetVisibility"):
            return "skin-folder", ("appended scoped rules stay skin-folder-only; only SetColor and SetSpacing on "
                                   "a joined node take the per-declaration bundle route")
    if kind in CANDIDATES:
        return "refused", ("candidate operation: %s stays preview-only until its own runtime test passes"
                           % kind)
    if kind in SKIN_KINDS:
        rule = (op.get("new") or {}).get("rule") or {}
        if kind != "ReplaceToken" and rule.get("op") == "remove":
            return "refused", ("the skin-folder writer cannot express a remove (USS cannot delete a game "
                               "declaration); the bundle route for sheets is blocked until runtime test B")
        return "skin-folder", "the default route writes the skin folder only and changes no game file"
    if kind in ("MoveNode", "ResizeNode", "AddCell"):
        if not (op.get("target") or {}).get("cell"):
            return "refused", "the operation has no cell target"
        return "bundle", ("the composition asset is rebuilt into the schema 2 package; install.preflight "
                          "carries the Stage 3G CRC caveat (observed, not guaranteed)")
    if kind == "ReplaceAsset":
        from . import native
        swap = (op.get("new") or {}).get("swap") or {}
        akind = swap.get("kind")
        if akind not in ("texture", "icon", "svg"):
            return "refused", ("the skin writer supports wallpaper textures, icons and SVGs; %r is not one of "
                               "them" % akind)
        source = swap.get("source")
        if not source or images_dir is None or not (Path(images_dir) / source).is_file():
            return "refused", ("the project has no image payload for %s; pick the picture again on the Images "
                               "tab" % (source or "this asset"))
        if akind in ("icon", "svg") and aa_dir is None:
            return "refused", ("an icon or SVG needs the game's image catalogue to resolve its classes; no "
                               "verified source is available for this build")
        if akind == "texture" and not (swap.get("where") or native.default_places(swap.get("name") or "")):
            return "refused", "the skin writer has no place on screen for this wallpaper"
        return "skin-folder", ("the Simple-mode skin-picture writer draws it in the skin folder (no game file "
                               "changes)")
    return "refused", "no route: the operation kind has no writer"


def _translation(op, route_preference=playops.DEFAULT_ROUTE_PREFERENCE, layout_route="bundle"):
    kind = op.get("kind")
    route = _route(op, route_preference=route_preference, layout_route=layout_route)[0]
    if route == "custom_layout":
        cell = (op.get("target") or {}).get("cell") or {}
        return {"fragment": "custom_layout", "composition": cell.get("composition") or (op.get("new") or {}).get("composition"),
                "element_id": cell.get("cell_element_id") or (op.get("new") or {}).get("element_id"), "writer": "skin_editor.custom_layouts (one JSON file per composition)"}
    if kind == "ReplaceToken":
        new = op.get("new") or {}
        row = {"fragment": "token_overrides", "token": new.get("token"), "value": new.get("value")}
        if route == "bundle":
            row["bundles"] = list(playops.TOKEN_BUNDLES)
            row["unverified_bundles"] = [playops.COMMON_TOKEN_BUNDLE]
            row["common_bundle_label"] = playops.COMMON_BUNDLE_LABEL
        return row
    if kind in ("SetColor", "SetSpacing") and route == "bundle":
        handle = playops.declaration_edit(op)
        return {"fragment": "declaration_edits", "declaration": handle,
                "reach": (handle or {}).get("reach")}
    if kind in ("SetColor", "SetStyle", "SetSpacing", "SetVisibility"):
        rule = (op.get("new") or {}).get("rule") or {}
        return {"fragment": "scoped_rules", "sheet": (rule.get("sheet") or {}).get("name"),
                "selector": rule.get("selector"), "props": rule.get("props"),
                "specificity": "written as a native rule (wins ties by order); not raised numerically"}
    if kind in ("MoveNode", "ResizeNode", "AddCell"):
        cell = (op.get("target") or {}).get("cell") or {}
        return {"fragment": "placement", "composition": cell.get("composition"),
                "cell_index": cell.get("cell_index"), "element_id": cell.get("cell_element_id"),
                "geometry": cell.get("geometry")}
    return {"fragment": None}


def _is_stale(op):
    if op.get("state") != "applied":
        return "state is %r (not applied)" % op.get("state")
    for r in op.get("rebased") or []:
        if r.get("status") in ("unresolved", "ambiguous"):
            return "rebase %s" % r.get("status")
    if op.get("stale_reason"):
        return str(op["stale_reason"])
    return None


def _config_size(dump, composition, cell_index):
    """The size of the configuration the composition's own tile row uses for this cell: the tile row's cfg_index
    resolved against cell_configs. None when the dump does not carry it (the gate then cannot judge a shrink)."""
    rows = [t for t in (dump.get("tiles") or [])
            if t.get("composition") == composition and t.get("cell_index") == cell_index]
    cfgs = [c for c in (dump.get("cell_configs") or [])
            if c.get("composition") == composition and c.get("cell_index") == cell_index]
    if not cfgs:
        return None
    cfg_index = (rows[0].get("cfg_index") if rows else 0)
    pick = next((c for c in cfgs if c.get("cfg_index") == cfg_index), cfgs[0])
    return {"x": int(pick.get("size_w")), "y": int(pick.get("size_h"))}


def _packed_add_row(dump, session, op):
    """Where the runtime PACKS an added cell: the Test C+D rule (render.screen.pack_rows) applied to the
    composition with the session's other cell geometry already applied. Returns (row, packed_item) or (None, None)."""
    from .render import screen as screen_mod
    cell = (op.get("target") or {}).get("cell") or {}
    comp = cell.get("composition")
    geometry = {}
    adds = []
    for other in playops.effective(session):
        c = (other.get("target") or {}).get("cell") or {}
        if c.get("composition") != comp:
            continue
        g = dict(c.get("geometry") or {})
        if other.get("kind") == "AddCell":
            adds.append({"element_id": c.get("cell_element_id"), "cell_index": c.get("cell_index"),
                         "x": g.get("x"), "y": g.get("y"), "w": g.get("w"), "h": g.get("h")})
        else:
            geometry[c.get("cell_index")] = g
    items = []
    for c in dump.get("cells") or []:
        if c.get("composition") != comp:
            continue
        g = geometry.get(c["cell_index"]) or {}
        items.append({"element_id": c["element_id"], "cell_index": c["cell_index"],
                      "x": g.get("x", c["x"]), "y": g.get("y", c["y"]),
                      "w": g.get("w", c["w"]), "h": g.get("h", c["h"])})
    items.extend(adds)
    for packed in screen_mod.pack_rows(items):
        if packed.get("element_id") == cell.get("cell_element_id") and packed.get("cell_index") == cell.get("cell_index"):
            return packed.get("y"), packed
    return None, None


def _bottom_slots(source, compositions, composition):
    """The composition's m_bottom* optional slices: [{element_id, direction, y, h}] from its own bundle. Read only.
    A missing composition/bundle returns [] (the effect is then reported as not measured)."""
    import UnityPy
    rec = (compositions or {}).get(composition)
    if not rec or not source:
        return []
    try:
        env = UnityPy.load(str(Path(source) / rec["bundle"]))
        obj = {o.path_id: o for o in env.objects}.get(int(rec["path_id"]))
        t = obj.read_typetree() if obj is not None else None
    except Exception:
        return []
    slices = (t or {}).get("m_optionalSlices") or {}
    out = []
    for direction in ("m_bottom", "m_bottomLeft", "m_bottomRight"):
        for e in slices.get(direction) or []:
            if not isinstance(e, dict):
                continue
            g = e.get("m_location") or {}
            out.append({"element_id": e.get("m_elementID"), "direction": direction,
                        "y": g.get("y", 0), "h": g.get("height", 1)})
    return out


def _preview_context(session):
    """The project session's saved preview size/setting, with the measured default (2560x1440 Small) when none was
    stored. Returns (width, height, setting label, grid rows). The measured runtime grid is 16 rows at 2560x1440."""
    pv = (session or {}).get("preview") or {}
    w = int(pv.get("width") or 2560)
    h = int(pv.get("height") or 1440)
    setting = pv.get("setting") or "Small"
    if (w, h) == (2560, 1440):
        rows = 16
    else:
        rows = max(1, round((h - 24 + 16.6) / 82))       # estimate outside the measured point
    return w, h, setting, rows


def optional_slot_effects(session, dump, compositions, source, grid_rows=None):
    """What the session's AddCell/ResizeNode/SetOptionalSlots operations do to the composition's BOTTOM optional
    tiles. Optional bottom regions are anchored at the grid's design bottom (Test C+D rule), so an operation that
    raises the bottom pushes them down; one that passes the grid's last row hides them. Reported per operation,
    with the preview size/setting named (the measured point is 2560x1440 Small, 16 rows)."""
    if not dump or not source:
        return []
    w, h, setting, measured_rows = _preview_context(session)
    if grid_rows is None:
        grid_rows = measured_rows
    label = "%dx%d %s" % (w, h, setting)
    measured = (w, h) == (2560, 1440) and setting in ("Small", "Small UI")
    est = "" if measured else " (estimate)"
    by_comp = {}
    for c in dump.get("cells") or []:
        by_comp.setdefault(c.get("composition"), []).append(c)
    bottom = {comp: max((c["y"] + c["h"] for c in cells), default=0) for comp, cells in by_comp.items()}
    # pair a remove and an add in the same region as a REPLACE, so the review names both halves in one sentence
    slot_ops = [o for o in playops.effective(session) if o.get("kind") == "SetOptionalSlots"]
    pairs, paired_removes = {}, set()
    removes = [o for o in slot_ops if (o.get("new") or {}).get("op") == "remove-slot"]
    adds = [o for o in slot_ops if (o.get("new") or {}).get("op") == "add-slot"]
    for rem in removes:
        rn = rem.get("new") or {}
        for add in adds:
            an = add.get("new") or {}
            if (add.get("id") in pairs or add.get("id") is None):
                continue
            if (rn.get("composition"), rn.get("direction") or "m_bottom") == \
                    (an.get("composition"), an.get("direction") or "m_bottom"):
                pairs[add.get("id")] = rn.get("element_id")
                paired_removes.add(rem.get("id"))
                break
    effects = []
    for op in slot_ops:
        new = op.get("new") or {}
        comp = new.get("composition") or (op.get("target") or {}).get("screen")
        if comp not in bottom:
            continue
        direction = new.get("direction") or "m_bottom"
        before = bottom[comp]
        slots = _bottom_slots(source, compositions, comp)
        if new.get("op") == "add-slot":
            loc = new.get("location") or {}
            row = before + int(loc.get("y", 0))
            h = int(loc.get("height", 1))
            hidden = row + h > grid_rows
            removed = pairs.get(op.get("id"))
            if removed:
                base = ("replaces %s with %s; %s %s" %
                        (removed, new.get("element_id"), new.get("element_id"),
                         ("will not appear: starts at row %d, the grid's last row is %d (needs a taller grid)"
                          % (row, grid_rows - 1)) if hidden else ("appears at row %d" % row)))
            else:
                base = ("adding optional slot %s %s" %
                        (new.get("element_id"),
                         ("starts at row %d; the grid's last row is %d (needs a taller grid)"
                          % (row, grid_rows - 1)) if hidden else ("appears at row %d" % row)))
            effects.append({"op_id": op.get("id"), "kind": "SetOptionalSlots",
                            "element_id": new.get("element_id"),
                            "composition": comp, "design_bottom_before": before, "design_bottom_after": before,
                            "grid_rows": grid_rows, "hidden": [new.get("element_id")] if hidden else [],
                            "moved": [], "replaces": removed,
                            "summary": "%s at %s%s" % (base, label, est)})
        elif new.get("op") == "remove-slot":
            if op.get("id") in paired_removes:
                continue
            row = next((before + s["y"] for s in slots if s["element_id"] == new.get("element_id")), None)
            if row is not None:
                effects.append({"op_id": op.get("id"), "kind": "SetOptionalSlots",
                                "element_id": new.get("element_id"),
                                "composition": comp, "design_bottom_before": before, "design_bottom_after": before,
                                "grid_rows": grid_rows, "hidden": [], "moved": [],
                                "summary": "removing optional slot %s at row %d at %s%s"
                                           % (new.get("element_id"), row, label, est)})
        elif new.get("op") == "reorder-slot":
            effects.append({"op_id": op.get("id"), "kind": "SetOptionalSlots", "element_id": None,
                            "composition": comp, "design_bottom_before": before, "design_bottom_after": before,
                            "grid_rows": grid_rows, "hidden": [], "moved": [],
                            "summary": "reordering %s to %s at %s%s"
                                       % (direction, ", ".join(new.get("order") or []), label, est)})
        continue
    for op in playops.effective(session):
        kind = op.get("kind")
        if kind not in ("AddCell", "ResizeNode"):
            continue
        cell = (op.get("target") or {}).get("cell") or {}
        comp = cell.get("composition")
        g = cell.get("geometry") or {}
        if comp not in bottom or not isinstance(g.get("y"), int):
            continue
        before = bottom[comp]
        after = max(before, int(g["y"]) + int(g.get("h", 0)))
        bottom[comp] = after
        if after == before:
            continue
        hidden, moved = [], []
        for s in _bottom_slots(source, compositions, comp):
            row_before = before + s["y"]
            row_after = after + s["y"]
            if row_before + s["h"] <= grid_rows and row_after + s["h"] > grid_rows:
                hidden.append(s["element_id"])
            elif row_before != row_after:
                moved.append({"element_id": s["element_id"], "from_row": row_before, "to_row": row_after})
        if hidden or moved:
            elem_label = cell.get("cell_element_id") or kind
            bits = []
            if hidden:
                bits.append("%s hides %s" % ("adding " + elem_label if kind == "AddCell" else "resizing " + elem_label,
                                              ", ".join(hidden)))
            if moved:
                bits.append("%s moves %s" % ("adding " + elem_label if kind == "AddCell" else "resizing " + elem_label,
                                             ", ".join("%s to row %d" % (m["element_id"], m["to_row"]) for m in moved)))
            effects.append({"op_id": op.get("id"), "kind": kind, "element_id": elem_label, "composition": comp,
                            "design_bottom_before": before, "design_bottom_after": after,
                            "grid_rows": grid_rows, "hidden": hidden, "moved": moved,
                            "summary": "; ".join(bits) + " at %s%s" % (label, est)})
    return effects


def addcell_placement_options(session, dump, compositions, source, grid_rows=16):
    """For each AddCell, the requested placement and the aligned placement that hides the fewest bottom optional
    tiles. The runtime packs an added cell to the end of its column; only that row builds, so the low-impact option
    is that packed row. Both carry their design bottom and optional-slot effect, so the review can offer a choice."""
    if not dump or not source:
        return []
    w, h, setting, _rows = _preview_context(session)
    pv_label = "%dx%d %s" % (w, h, setting)
    pv_est = "" if ((w, h) == (2560, 1440) and setting in ("Small", "Small UI")) else " (estimate)"
    by_comp = {}
    for c in dump.get("cells") or []:
        by_comp.setdefault(c.get("composition"), []).append(c)
    out = []
    for op in playops.effective(session):
        if op.get("kind") != "AddCell":
            continue
        cell = (op.get("target") or {}).get("cell") or {}
        comp = cell.get("composition")
        g = dict(cell.get("geometry") or {})
        if comp not in by_comp or not isinstance(g.get("y"), int):
            continue
        base_bottom = 0
        for c in by_comp[comp]:
            base_bottom = max(base_bottom, c["y"] + c["h"])
        for other in playops.effective(session):
            if other is op or other.get("kind") not in ("ResizeNode", "AddCell"):
                continue
            c2 = (other.get("target") or {}).get("cell") or {}
            if c2.get("composition") != comp:
                continue
            gg = c2.get("geometry") or {}
            if isinstance(gg.get("y"), int):
                base_bottom = max(base_bottom, gg["y"] + gg.get("h", 0))
        slots = _bottom_slots(source, compositions, comp)

        def option(label, y, aligned):
            bottom = max(base_bottom, y + g.get("h", 0))
            hidden, visible = [], []
            for s in slots:
                row = bottom + s["y"]
                (hidden if row + s["h"] > grid_rows else visible).append(s["element_id"])
            return {"label": label, "geometry": dict(g, y=y), "packed_row": base_bottom if aligned else None,
                    "aligned": aligned, "design_bottom": bottom, "hidden": hidden, "visible": visible,
                    "summary": ("%s at row %d: design bottom %d, hides %s at %s%s" %
                                ("aligned" if aligned else "requested", y, bottom,
                                 ", ".join(hidden) if hidden else "no optional tile", pv_label, pv_est))}
        requested = option("requested", g["y"], g["y"] == base_bottom)
        best = option("lowest impact", base_bottom, True)
        best["default"] = True
        requested["default"] = requested["geometry"] == best["geometry"]
        options = [requested] if requested["geometry"] == best["geometry"] else [requested, best]
        out.append({"op_id": op.get("id"), "element_id": cell.get("cell_element_id"), "composition": comp,
                    "grid_rows": grid_rows, "options": options,
                    "recommended": min(options, key=lambda o: (len(o["hidden"]), o["design_bottom"]))})
    return out


def plan(session, *, identity=None, compositions=None, dump=None, referrers=None, images_dir=None, aa_dir=None,
         route_preference=None, index=None, edit_competition_sheets=False, project=None, test_only=None, layout_route=None, customised=None):
    """Classify every effective operation and validate the session's conflicts. Read only.

    identity: {game_build, files: {bundle: sha256}, source}
    compositions: {name: {bundle, path_id}} (compositionset index_full()["compositions"])
    dump: the layout dump (for the overlap gate and the referrer scan)
    project: the project model whose effective route_preference is used (the build passes it; explicit
             route_preference overrides it). A missing project keeps the default.
    test_only: TEST/EVIDENCE ONLY. {overrides: [...], allow_candidates: ["ResizeNode"]} routes a named
               candidate kind to its bundle writer for one build and records the override in the report and
               package. The normal build passes nothing and keeps refusing candidates.
    """
    allow_candidates = set((test_only or {}).get("allow_candidates") or [])
    pref = _project_route_preference(None, session, route_preference, project=project)
    lroute = _project_layout_route(None, session, layout_route, project=project)
    customised = set(customised or [])
    replace_ids = _slot_replace_ids(session)
    if project is not None and not edit_competition_sheets:
        from . import project as project_mod
        edit_competition_sheets = project_mod.edit_competition_sheets(project)
    ops = [op for op in (session.get("operations") or []) if op.get("state") in ("applied", "stale", "superseded")]
    effective = [op for op in ops if op.get("state") == "applied" and not op.get("superseded_by")]
    rows, refusals = [], []
    targets = set()
    superseded = []
    for op in ops:
        if op.get("state") == "superseded":              # history: a newer operation replaced it. It is not built and it is not a refusal (found by the E2E1 chain)
            superseded.append({"id": op.get("id"), "kind": op.get("kind"), "superseded_by": op.get("superseded_by")})
            continue
        route, reason = _route(op, images_dir=images_dir, aa_dir=aa_dir, route_preference=pref, layout_route=lroute)
        if route == "custom_layout" and op.get("kind") == "SetOptionalSlots" and op.get("id") not in replace_ids:
            route, reason = "refused", ("SetOptionalSlots %s alone is %s; on the custom-layout route only a replace (one remove and one add in the same region) is proven (JX X3)"
                                        % ((op.get("new") or {}).get("op") or "?", playops.SLOT_JSON_REASON))
        if lroute != "custom_layout" and op.get("kind") == "SetOptionalSlots" and playops.slot_op_promoted(op):
            route = "bundle"
            reason = ("promoted: optional-slot add/remove/reorder on SquadComposition-Large's m_bottom was "
                      "proven at 2560x1440 Small (Test E); other regions/settings are not claimed")
        if op.get("kind") in allow_candidates and route == "refused":
            route = "bundle"
            reason = ("TEST-ONLY override: candidate operation %s is routed to its bundle writer for this "
                      "recorded test build (the normal build keeps refusing it)" % op.get("kind"))
        row = {"id": op.get("id"), "kind": op.get("kind"), "route": route, "reason": reason,
               "translation": _translation(op, pref, lroute), "refused": route == "refused"}
        stale = _is_stale(op)
        if stale:
            row.update(route="refused", reason="stale/unresolved: " + stale, refused=True)
        if identity is not None:
            if session.get("game_build") and identity.get("game_build") and \
                    session["game_build"] != identity["game_build"]:
                row.update(route="refused", refused=True,
                           reason="identity mismatch: the session was made for %s, the source is %s"
                                  % (session["game_build"], identity["game_build"]))
            loc = (op.get("target") or {}).get("locator") or {}
            bundle = loc.get("bundle")
            want = loc.get("bundle_sha256")
            have = (identity.get("files") or {}).get(bundle)
            if bundle and have is None:
                row.update(route="refused", refused=True,
                           reason="identity mismatch: %s is not in the verified source" % bundle)
            elif want and have and want != have:
                row.update(route="refused", refused=True,
                           reason="identity mismatch: the operation was made against %s %s, the source holds %s"
                                  % (bundle, want[:12], have[:12]))
        comp_name = ((op.get("target") or {}).get("cell") or {}).get("composition") or (op.get("new") or {}).get("composition") or (op.get("target") or {}).get("screen")
        if row["route"] == "custom_layout":
            row["custom_layout_file"] = comp_name
            if comp_name in customised:
                row["replaces_user_file"] = True
        if row["route"] == "bundle" and op.get("kind") in playops.LAYOUT_KINDS and comp_name in customised:
            row["warning"] = ("this screen is customised in the game: its custom-layout file is used instead of the bundle, so this bundle layout edit will not show")
        if row["route"] in ("bundle", "custom_layout"):
            if op.get("kind") == "AddCell" and dump:
                cell = (op.get("target") or {}).get("cell") or {}
                want_y = int((cell.get("geometry") or {}).get("y", 0))
                packed_y, _packed = _packed_add_row(dump, session, op)
                if packed_y is not None and packed_y != want_y:
                    row.update(route="refused", refused=True,
                               reason="the runtime packs this added cell to row %d, not the requested row %d "
                                      "(Test C+D: cells are packed vertically per column). Place it at row %d, or "
                                      "add the cell(s) that occupy the rows above it." % (packed_y, want_y, packed_y))
        if row["route"] in ("bundle", "custom_layout"):
            if op.get("kind") == "ResizeNode" and dump:
                cell = (op.get("target") or {}).get("cell") or {}
                cs = _config_size(dump, cell.get("composition"), cell.get("cell_index"))
                geo = cell.get("geometry") or {}
                if cs and (int(geo.get("w", 0)) < cs["x"] or int(geo.get("h", 0)) < cs["y"]):
                    row.update(route="refused", refused=True,
                               reason="shrinking below the tile's configured size is refused: %s cell %s is %dx%d "
                                      "configured; the resize asks for %sx%s (the writer does not rewrite the "
                                      "configuration list)" % (cell.get("composition"), cell.get("cell_element_id"),
                                                               cs["x"], cs["y"], geo.get("w"), geo.get("h")))
        if row["route"] == "bundle":
            if op.get("kind") in ("ReplaceToken",):
                row["target_bundles"] = list(playops.TOKEN_BUNDLES)
                row["common_bundle_label"] = playops.COMMON_BUNDLE_LABEL
                targets.update(playops.TOKEN_BUNDLES)
                for b in playops.TOKEN_BUNDLES:
                    if identity is not None and (identity.get("files") or {}).get(b) is None:
                        row.update(route="refused", refused=True,
                                   reason="identity mismatch: %s is not in the verified source" % b)
            elif op.get("kind") in ("SetColor", "SetSpacing"):
                handle = playops.declaration_edit(op)
                row["target_bundle"] = handle["bundle"]
                row["declaration"] = handle
                targets.add(handle["bundle"])
            elif op.get("kind") == "SetOptionalSlots":
                bundle_ = ((op.get("target") or {}).get("locator") or {}).get("bundle")
                row["target_bundle"] = bundle_
                if bundle_:
                    targets.add(bundle_)
            else:
                cell = (op.get("target") or {}).get("cell") or {}
                comp = compositions.get(cell.get("composition")) if compositions else None
                if not comp:
                    row.update(route="refused", refused=True,
                               reason="the composition %r was not found in the serialized UI bundles"
                                      % cell.get("composition"))
                else:
                    row["target_bundle"] = comp["bundle"]
                    row["target_path_id"] = comp["path_id"]
                    targets.add(comp["bundle"])
        rows.append(row)
        if row["refused"]:
            refusals.append({"id": row["id"], "kind": row.get("kind"), "reason": row["reason"]})

    # same-cell conflicts across the WHOLE session
    seen, conflicts = {}, []
    for op in effective:
        cell = (op.get("target") or {}).get("cell") or {}
        key = (cell.get("composition"), cell.get("cell_index"))
        if op.get("kind") not in ("MoveNode", "ResizeNode", "AddCell"):
            continue
        if key in seen:
            conflicts.append({"kind": "same_cell", "composition": key[0], "cell_index": key[1],
                              "operations": [seen[key], op.get("id")],
                              "reason": "two applied operations change the same cell; one must supersede the other"})
        else:
            seen[key] = op.get("id")

    # the overlap gate on the composition AS IT STANDS after all the session's moves
    moves = {}
    for op in effective:
        if op.get("kind") not in ("MoveNode", "ResizeNode", "AddCell") or _is_stale(op):
            continue
        cell = (op.get("target") or {}).get("cell") or {}
        moves[(cell.get("composition"), cell.get("cell_index"))] = cell.get("geometry") or {}
    if dump and moves:
        for comp in sorted({c for c, _i in moves}):
            cells = [c for c in dump.get("cells") or [] if c.get("composition") == comp]
            rects = []
            for c in cells:
                g = moves.get((comp, c["cell_index"]))
                x, y, w, h = (g.get("x", c["x"]), g.get("y", c["y"]), g.get("w", c["w"]), g.get("h", c["h"])) if g else (c["x"], c["y"], c["w"], c["h"])
                rects.append((c["cell_index"], c["element_id"], x, y, w, h))
            known = {r[0] for r in rects}
            for op in effective:
                cell = (op.get("target") or {}).get("cell") or {}
                if op.get("kind") == "AddCell" and cell.get("composition") == comp and cell.get("cell_index") not in known:
                    g = cell.get("geometry") or {}
                    rects.append((cell.get("cell_index"), cell.get("cell_element_id"),
                                  g.get("x"), g.get("y"), g.get("w"), g.get("h")))
            moved = {ci for (cc, ci) in moves if cc == comp}
            for i in range(len(rects)):
                for j in range(i + 1, len(rects)):
                    a, b = rects[i], rects[j]
                    if a[0] not in moved and b[0] not in moved:
                        continue                       # pre-existing design overlaps are not caused by the session
                    if a[2] < b[2] + b[4] and b[2] < a[2] + a[4] and a[3] < b[3] + b[5] and b[3] < a[3] + a[5]:
                        conflicts.append({"kind": "overlap", "composition": comp,
                                          "cells": [a[1], b[1]], "cell_indexes": [a[0], b[0]],
                                          "reason": "the cells overlap after the session's moves"})
    # referrers: from the 4C graph when supplied; otherwise a named gap (never silently empty)
    refs = referrers or {}
    affected = sorted({b for bundle in targets for b in (refs.get(bundle) or [])})
    from . import competition
    effective_ops = [op for op in ops if op.get("state") == "applied"]
    competition_warnings = competition.warnings(index, effective_ops,
                                                edit_competition_sheets=edit_competition_sheets)
    warnings = [{"id": r["id"], "kind": r["kind"], "warning": r["warning"]} for r in rows if r.get("warning")]
    return {"schema": SCHEMA, "project": session.get("project"), "game_build": session.get("game_build"),
            "route_preference": pref, "layout_route": lroute, "test_only": test_only or {},
            "customised_in_game": sorted(customised), "warnings": warnings, "superseded": superseded,
            "custom_layout_files": sorted({r["custom_layout_file"] for r in rows if r.get("custom_layout_file") and not r["refused"]}),
            "operations": rows, "refusals": refusals, "conflicts": conflicts,
            "competition_warnings": competition_warnings,
            "targets": sorted(targets), "affected": affected,
            "referrers": {"source": "4C dependency graph used_by" if refs else "not supplied (G23)",
                          "by_bundle": {b: refs.get(b, []) for b in sorted(targets)},
                          "affected": affected},
            "routable": bool(effective) and not conflicts and not refusals}


def stock_overlaps(dump):
    """Every cell-rectangle overlap ALREADY present in a stock composition (no session move involved). Stage 3E
    showed an overlap makes the game drop a tile, so these are themselves a finding: either the game resolves
    them through conditions/optional slots, or the geometric model is incomplete. RULE: only an overlap that
    involves a cell the session MOVED is a build error; a stock overlap is reported, never refused."""
    out = []
    if not dump:
        return out
    by = {}
    for c in dump.get("cells") or []:
        by.setdefault(c.get("composition"), []).append(c)
    for comp, cells in sorted(by.items()):
        rects = [(c.get("cell_index"), c.get("element_id"), c.get("x"), c.get("y"), c.get("w"), c.get("h"))
                 for c in cells]
        for i in range(len(rects)):
            for j in range(i + 1, len(rects)):
                a, b = rects[i], rects[j]
                if a[2] < b[2] + b[4] and b[2] < a[2] + a[4] and a[3] < b[3] + b[5] and b[3] < a[3] + a[5]:
                    out.append({"composition": comp, "cells": [a[1], b[1]],
                                "cell_indexes": [a[0], b[0]],
                                "rule": "stock overlap: reported, not an error; an overlap is an error only when "
                                        "one of its cells was moved by the session"})
    return out


def _scoped_project(session, name, ws=None, aa_dir=None, route_preference=playops.DEFAULT_ROUTE_PREFERENCE):
    from . import project as project_mod
    p = project_mod.new(name, session.get("game_build"))
    project_mod.set_route_preference(p, route_preference)
    for op in playops.effective(session):
        route, _reason = _route(op, images_dir=(project_mod.images_dir(ws, session.get("project")) if ws else None),
                                aa_dir=aa_dir, route_preference=route_preference)
        if route != "skin-folder":
            continue
        kind, new = op.get("kind"), op.get("new") or {}
        if kind == "ReplaceToken":
            p["token_overrides"].append({"token": new.get("token"), "value": new.get("value")})
        elif kind in ("SetColor", "SetStyle", "SetSpacing", "SetVisibility"):
            rule = new.get("rule") or {}
            p["scoped_rules"].append({"sheet": (rule.get("sheet") or {}).get("name"),
                                      "selector": rule.get("selector"), "props": dict(rule.get("props") or {})})
        elif kind == "ReplaceAsset":
            swap = new.get("swap") or {}
            frag = {"bundle": (op.get("target") or {}).get("locator", {}).get("bundle"),
                    "path_id": str((op.get("target") or {}).get("locator", {}).get("path_id")),
                    "kind": swap.get("kind"), "source": swap.get("source"),
                    "name": (op.get("target") or {}).get("guard", {}).get("name") or swap.get("name")}
            if swap.get("where"):
                frag["where"] = swap["where"]
            p["image_swaps"].append(frag)
            if swap.get("kind") == "icon":
                p["image_swaps"][-1]["kind"] = "icon"
    return p


def _utf8_tree(path):
    return sorted((str(p.relative_to(path)), _sha(p)) for p in Path(path).rglob("*") if p.is_file())


def _custom_layout_files(session, report, source, compositions, out, project_mod, ws, lroute, pref, images_dir, aa_dir):
    """ST1: the custom-layout files of the session's layout operations: one JSON file per composition, generated from the VERIFIED stock bundle and edited by the operations in
    session order (skin_editor.custom_layouts). Written to <out>/custom-layouts/<composition> with a manifest <out>/custom-layouts.json; nothing is written to the game.
    Returns [{name, size, sha256, composition, operations}]."""
    from . import custom_layouts as cl
    replace_ids = _slot_replace_ids(session)
    by_comp = {}
    for op in playops.effective(session):
        if op.get("kind") not in playops.LAYOUT_KINDS:
            continue
        if _route(op, images_dir=images_dir, aa_dir=aa_dir, route_preference=pref, layout_route=lroute)[0] != "custom_layout":
            continue
        if op.get("kind") == "SetOptionalSlots" and op.get("id") not in replace_ids:
            continue
        comp = ((op.get("target") or {}).get("cell") or {}).get("composition") or (op.get("new") or {}).get("composition") or (op.get("target") or {}).get("screen")
        by_comp.setdefault(comp, []).append(op)
    files = []
    folder = Path(out) / "custom-layouts"
    for comp, ops in sorted(by_comp.items()):
        rec = (compositions or {}).get(comp)
        if not rec:
            raise RuntimeError("the composition %r was not found in the serialized UI bundles" % comp)
        tt, objs = cl.load_composition(Path(source) / rec["bundle"], comp)
        obj = cl.generate(tt, objs)
        slot_ops = [o for o in ops if o.get("kind") == "SetOptionalSlots"]
        for op in ops:
            kind, new = op.get("kind"), op.get("new") or {}
            cell = (op.get("target") or {}).get("cell") or {}
            eid = cell.get("cell_element_id")
            geo = cell.get("geometry") or {}
            if kind == "MoveNode":
                cur = next(c for c in obj["m_gridComponents"] if c["m_elementID"] == eid)["m_location"]
                cl.set_location(obj, eid, geo["x"], geo["y"], cur["width"], cur["height"])
            elif kind == "ResizeNode":
                cl.set_location(obj, eid, geo["x"], geo["y"], geo["w"], geo["h"])
                cl.set_max_size(obj, eid, cell["max_size"]["x"], cell["max_size"]["y"])
            elif kind == "SetCellMaxSize":
                cl.set_max_size(obj, eid, cell["max_size"]["x"], cell["max_size"]["y"])
            elif kind == "AddCell":
                d = cell.get("description") or {}
                cl.add_cell(obj, eid, cl.description_cell_by_ref(objs, d["path_id"], d["config_index"]), (geo["x"], geo["y"], geo["w"], geo["h"]))
            elif kind == "SwapTile":
                tile = new["tile"]
                if tile["name"] not in {t["id"] for t in cl.tile_set(tt, objs)}:
                    raise RuntimeError("%s is not in %s's own tile set" % (tile["name"], comp))
                cl.swap_cell(obj, eid, cl.description_cell_in_set(tt, objs, tile["name"], (tile["size"]["x"], tile["size"]["y"])))
        if slot_ops:
            by_region = {}
            for o in slot_ops:
                by_region.setdefault((o.get("new") or {}).get("direction") or "m_bottom", []).append(o)
            for region, rops in by_region.items():
                rem = next(o for o in rops if (o.get("new") or {}).get("op") == "remove-slot")["new"]
                add = next(o for o in rops if (o.get("new") or {}).get("op") == "add-slot")["new"]
                entries = []
                for e in obj["m_optionalSlices"][region]:
                    if e["m_elementID"] == rem["element_id"]:
                        loc = add.get("location") or {}
                        off = (loc.get("x", e["m_location"]["x"]), loc.get("y", e["m_location"]["y"]))
                        d = add["description"]
                        entries.append((add["element_id"], cl.description_cell_by_ref(objs, d["path_id"], d["config_index"]), off))
                    else:
                        entries.append((e["m_elementID"], None, (e["m_location"]["x"], e["m_location"]["y"])))
                cl.set_slots(obj, region, entries)
        folder.mkdir(parents=True, exist_ok=True)
        cl.write(folder / comp, obj)
        files.append({"name": comp, "composition": comp, "size": (folder / comp).stat().st_size, "sha256": cl.sha256(folder / comp),
                      "operations": [o.get("id") for o in ops]})
    if files:
        (Path(out) / "custom-layouts.json").write_text(json.dumps({"schema": "fm-customlayouts/1", "game_build": session.get("game_build"), "files": files}, indent=1, sort_keys=True),
                                                      encoding="utf-8")
    return files


def build(session, *, ws, source, identity, dump, compositions, index=None, aa_dir=None,
          dest=None, ts=None, referrers=None, extra_change=None, manifest_path=None, route_preference=None,
          test_only=None, layout_route=None, customised=None, layout_source=None):
    """Build the session from the VERIFIED stock source into `dest` (a scratch folder in tests/evidence).
    Returns the report; writes the target bundles, build-manifest.json, package.json, the skin folder and
    build-5g-report.json. `route_preference` (project setting, DEFAULT skin_folder) decides whether value
    edits take the skin-folder or the per-declaration/token bundle route."""
    from . import native
    ts = ts or time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    source = Path(source)
    out = Path(dest) if dest else (Path(ws.build) / str(session.get("project") or "session") / ts)
    out.mkdir(parents=True, exist_ok=True)
    from . import project as project_mod
    project = None
    if ws is not None and session.get("project"):
        try:
            project = project_mod.load(ws, str(session["project"]))
        except Exception:
            project = None
    pref = _project_route_preference(ws, session, route_preference, project=project)
    lroute = _project_layout_route(ws, session, layout_route, project=project)
    images_dir = None
    if ws is not None:
        try:
            images_dir = project_mod.images_dir(ws, str(session.get("project") or "session"))
        except Exception:
            images_dir = None
    edit_comp = project_mod.edit_competition_sheets(project) if project is not None else False
    report = plan(session, identity=identity, compositions=compositions, dump=dump, referrers=referrers,
                  images_dir=images_dir, aa_dir=aa_dir, route_preference=pref, index=index,
                  edit_competition_sheets=edit_comp, project=project, test_only=test_only, layout_route=lroute, customised=customised)
    report["stock_overlaps"] = stock_overlaps(dump) if dump else []
    report["optional_slot_effects"] = optional_slot_effects(session, dump, compositions, source)
    report["addcell_placement_options"] = addcell_placement_options(session, dump, compositions, source)
    report["built_utc"] = ts
    report["source"] = {"folder": str(source), "kind": "verified stock source (never the live game folder)",
                        "game_build": (identity or {}).get("game_build")}
    if report["conflicts"] or report["refusals"]:
        report["blocked"] = [c["reason"] for c in report["conflicts"]] + [r["reason"] for r in report["refusals"]]
        report["outputs"] = {"built_dir": str(out), "skin_folder": None, "package": None, "manifest": None,
                             "bundles": {}}
        report["cell_check"] = None
        (out / "build-5g-report.json").write_text(json.dumps(report, indent=1, sort_keys=True), encoding="utf-8")
        return report

    # ---- bundle route: one group per composition's OWN bundle (serialized, never assumed)
    allow_candidates = set((test_only or {}).get("allow_candidates") or [])
    by_bundle = {}
    intended = {}
    for op in playops.effective(session):
        kind = op.get("kind")
        if kind == "SetOptionalSlots":
            new = op.get("new") or {}
            loc = op.get("target") or {}
            comp = ((op.get("target") or {}).get("locator") or {}).get("bundle")
            row = {"op": {"add-slot": "slot-add", "remove-slot": "slot-remove",
                          "reorder-slot": "slot-reorder"}.get(new.get("op"), "slot-unknown"),
                   "bundle": comp, "path_id": str((loc.get("locator") or {}).get("path_id")),
                   "composition": new.get("composition") or (op.get("target") or {}).get("screen"),
                   "cell_id": new.get("element_id"), "direction": new.get("direction") or "m_bottom",
                   "description": dict(new.get("description") or {}), "order": list(new.get("order") or []),
                   "no_order_extension": bool(new.get("no_order_extension")),
                   "location": dict(new.get("location") or {}) if new.get("location") else None}
            if _route(op, images_dir=(project_mod.images_dir(ws, session.get("project")) if ws else None),
                     aa_dir=aa_dir, route_preference=pref, layout_route=lroute)[0] != "bundle" and kind not in allow_candidates:
                if not playops.slot_op_promoted(op):
                    continue
            by_bundle.setdefault(row["bundle"], []).append(row)
            continue
        if kind not in ("MoveNode", "ResizeNode", "AddCell", "SetCellMaxSize"):
            continue
        if _route(op, images_dir=(project_mod.images_dir(ws, session.get("project")) if ws else None),
                 aa_dir=aa_dir, route_preference=pref, layout_route=lroute)[0] != "bundle" and kind not in allow_candidates:
            continue
        cell = (op.get("target") or {}).get("cell") or {}
        comp = compositions.get(cell.get("composition"))
        if kind == "SetCellMaxSize":         # SC2: the intended change is exactly this cell's m_maxSize
            orig_max = dict(op.get("original") or {}).get("value") or {}
            row = {"op": "set-max-size", "bundle": comp["bundle"], "path_id": str(comp["path_id"]),
                   "composition": cell.get("composition"), "cell_index": int(cell.get("cell_index")),
                   "cell_id": cell.get("cell_element_id"),
                   "from": {"x": int(orig_max["x"]), "y": int(orig_max["y"])},
                   "max": {"x": int(cell["max_size"]["x"]), "y": int(cell["max_size"]["y"])}}
            by_bundle.setdefault(comp["bundle"], []).append(row)
            intended.setdefault(comp["bundle"], {}).setdefault(str(comp["path_id"]), []).append({
                "element_id": cell.get("cell_element_id"), "cell_index": int(cell.get("cell_index")),
                "set_max": True, "from_max": row["from"], "max": row["max"]})
            continue
        orig = dict(op.get("original") or {}).get("value") or {}
        if kind == "AddCell":
            row = {"op": "add-cell", "bundle": comp["bundle"], "path_id": str(comp["path_id"]),
                   "composition": cell.get("composition"), "cell_index": int(cell.get("cell_index")),
                   "cell_id": cell.get("cell_element_id"), "geometry": dict(cell.get("geometry") or {}),
                   "description": dict(cell.get("description") or {})}
            by_bundle.setdefault(comp["bundle"], []).append(row)
            intended.setdefault(comp["bundle"], {}).setdefault(str(comp["path_id"]), []).append({
                "element_id": cell.get("cell_element_id"), "cell_index": int(cell.get("cell_index")),
                "added": True, "geometry": dict(cell.get("geometry") or {}),
                "description": dict(cell.get("description") or {})})
            continue
        row = {"op": "resize-cell" if kind == "ResizeNode" else "move-cell",
               "bundle": comp["bundle"], "path_id": str(comp["path_id"]),
               "composition": cell.get("composition"), "cell_index": int(cell.get("cell_index")),
               "cell_id": cell.get("cell_element_id"), "from": orig,
               "to": {"x": int(cell["geometry"]["x"]), "y": int(cell["geometry"]["y"])}}
        want_to = {"x": int(cell["geometry"]["x"]), "y": int(cell["geometry"]["y"])}
        if kind == "ResizeNode":
            row["to"].update({"w": int(cell["geometry"]["w"]), "h": int(cell["geometry"]["h"])})
            row["max"] = {"x": int(cell["max_size"]["x"]), "y": int(cell["max_size"]["y"])}
            want_to.update({"w": int(cell["geometry"]["w"]), "h": int(cell["geometry"]["h"])})
        by_bundle.setdefault(comp["bundle"], []).append(row)
        intended.setdefault(comp["bundle"], {}).setdefault(str(comp["path_id"]), []).append({
            "element_id": cell.get("cell_element_id"), "cell_index": int(cell.get("cell_index")),
            "resize": kind == "ResizeNode",
            "from": orig or {"x": cell["geometry"]["x"], "y": cell["geometry"]["y"]},
            "to": want_to, "max": row.get("max")})
    bundle_out = {}
    cell_check = {"ok": True, "by_bundle": {}, "differences": []}
    for bundle, ops in sorted(by_bundle.items()):
        src = source / bundle
        if not src.is_file():
            raise RuntimeError("the verified source has no %s" % bundle)
        sha = _sha(src)
        if identity and (identity.get("files") or {}).get(bundle) not in (None, sha):
            raise RuntimeError("the source copy of %s does not match the installation identity" % bundle)
        tiles.apply_ops(src, out, ops)
        built = out / bundle
        if extra_change and extra_change.get("bundle") == bundle:
            # TEST/EVIDENCE HOOK: inject an extra change into the built bundle so the 5G cell check must catch it
            tiles.apply_ops(built, out, [{"op": "move-cell", "bundle": bundle,
                                          "path_id": str(extra_change["path_id"]),
                                          "composition": extra_change["composition"],
                                          "cell_index": int(extra_change["cell_index"]),
                                          "cell_id": extra_change.get("cell_id"),
                                          "from": extra_change.get("from") or {}, "to": extra_change["to"]}])
        fails = tiles.check_ops(src, built, ops)
        from . import bundlediff
        cmp_ = bundlediff.compare(src, built)
        changed_cells = (cmp_.get("structure") or {}).get("cell_changes") or {}
        want = intended.get(bundle, {})
        diffs = list(fails)
        for pid, rows in want.items():
            got = changed_cells.get(str(pid)) or {}
            got_moves = {(m["element_id"], m["occurrence"]): (m["from"], m["to"]) for m in got.get("changed_m_location") or []}
            got_max = {(m["element_id"], m["occurrence"]): (m["from"], m["to"]) for m in got.get("changed_m_maxSize") or []}
            resized_ids = {(r["element_id"], 0) for r in rows if r.get("resize") or r.get("set_max")}
            added_ids = {(r["element_id"], 0) for r in rows if r.get("added")}
            got_added = {(m["element_id"], m["occurrence"]): m.get("location") for m in got.get("added_cells") or []}
            if got.get("removed_cells") or got.get("changed_m_minSize") \
                    or (set(got_max) - resized_ids) or (set(got_added) - added_ids):
                diffs.append("%s: the build changed cells that were not asked for (added %d, removed %d, resized %d, min %d)"
                             % (got.get("composition"), len(set(got_added) - added_ids),
                                len(got.get("removed_cells") or []),
                                len(set(got_max) - resized_ids),
                                len(got.get("changed_m_minSize") or [])))
            for row in rows:
                key = (row["element_id"], 0)
                if row.get("added"):
                    loc = got_added.get(key)
                    want_loc = (row["geometry"]["x"], row["geometry"]["y"], row["geometry"]["w"], row["geometry"]["h"])
                    if loc is None:
                        diffs.append("%s: intended added cell %s was not built" % (got.get("composition"), row["element_id"]))
                    elif tuple(loc) != want_loc:
                        diffs.append("%s: added cell %s built at %s, intended %s"
                                     % (got.get("composition"), row["element_id"], loc, want_loc))
                    continue
                if row.get("set_max"):                 # SC2: only m_maxSize of this cell; nothing else about it may change
                    mx = got_max.get(key)
                    if mx is None:
                        diffs.append("%s: intended m_maxSize change of %s was not built (difference: m_maxSize is unchanged)"
                                     % (got.get("composition"), row["element_id"]))
                    else:
                        mold, mnew = _loc(mx[0]), _loc(mx[1])
                        if (int(mold.get("x")), int(mold.get("y"))) != (row["from_max"]["x"], row["from_max"]["y"]) \
                                or (int(mnew.get("x")), int(mnew.get("y"))) != (row["max"]["x"], row["max"]["y"]):
                            diffs.append("%s: m_maxSize of %s built as %s -> %s, intended %s -> %s"
                                         % (got.get("composition"), row["element_id"], mold, mnew, row["from_max"], row["max"]))
                    if key in got_moves:
                        diffs.append("%s: %s also changed its m_location, which was not asked for"
                                     % (got.get("composition"), row["element_id"]))
                    continue
                if key not in got_moves:
                    diffs.append("%s: intended %s %s was not built"
                                 % (got.get("composition"), "resize" if row.get("resize") else "move", row["element_id"]))
                    continue
                old, new = _loc(got_moves[key][0]), _loc(got_moves[key][1])
                bad = (int(old.get("x")) != int(row["from"].get("x")) or int(old.get("y")) != int(row["from"].get("y"))
                       or int(new.get("x")) != int(row["to"]["x"]) or int(new.get("y")) != int(row["to"]["y"]))
                if row.get("resize"):
                    bad = bad or int(old.get("w")) != int(row["from"].get("w")) \
                        or int(old.get("h")) != int(row["from"].get("h")) \
                        or int(new.get("w")) != int(row["to"]["w"]) or int(new.get("h")) != int(row["to"]["h"])
                if bad:
                    diffs.append("%s: %s %s built as %s -> %s, intended %s -> %s"
                                 % (got.get("composition"), "resize" if row.get("resize") else "move",
                                    row["element_id"], old, new, row["from"], row["to"]))
                if row.get("resize"):
                    mx = got_max.get(key)
                    if mx is None:
                        diffs.append("%s: intended resize %s did not set m_maxSize"
                                     % (got.get("composition"), row["element_id"]))
                    else:
                        mob, mnew = _loc(mx[0]), _loc(mx[1])
                        if int(mnew.get("x")) != int(row["max"]["x"]) or int(mnew.get("y")) != int(row["max"]["y"]):
                            diffs.append("%s: resize %s set m_maxSize to %s, intended %s"
                                         % (got.get("composition"), row["element_id"], mnew, row["max"]))
            extra = [k for k in got_moves if k[0] not in {r["element_id"] for r in rows}]
            if extra:
                diffs.append("%s: the build moved cells that were not asked for: %s"
                             % (got.get("composition"), ", ".join(k[0] for k in extra)))
        other = (cmp_.get("object") or {}).get("changed_objects") or []
        if other:
            allowed = {str(pid) for pid in want} | {str(o["path_id"]) for o in ops if str(o.get("op", "")).startswith("slot-")}
            bad = [o for o in other if str(o.get("path_id")) not in allowed]
            if bad:
                diffs.append("%s: objects changed outside the addressed compositions: %s"
                             % (bundle, ", ".join(str(o.get("path_id")) for o in bad[:4])))
        cell_check["by_bundle"][bundle] = {"intended": want, "built_cell_changes": changed_cells,
                                           "object_set_equal": (cmp_.get("object") or {}).get("object_set_equal"),
                                           "differences": diffs}
        if diffs:
            cell_check["ok"] = False
            cell_check["differences"] += diffs
        bundle_out[bundle] = _sha(built)
    report["cell_check"] = cell_check
    custom_files = _custom_layout_files(session, report, layout_source or source, compositions, out, project_mod, ws, lroute, pref, images_dir, aa_dir)
    report["custom_layouts"] = {"files": custom_files, "layout_route": lroute}
    if not cell_check["ok"]:
        report["blocked"] = cell_check["differences"]
        report["outputs"] = {"built_dir": str(out), "skin_folder": None, "package": None, "manifest": None,
                             "bundles": bundle_out}
        (out / "build-5g-report.json").write_text(json.dumps(report, indent=1, sort_keys=True), encoding="utf-8")
        return report

    # ---- bundle route for style values (route_preference=bundle): token definitions in BOTH style bundles and
    # per-declaration edits of the winning declaration. Appended scoped rules stay on the skin-folder route.
    style_report = {"bundles": {}, "declaration_edits": [], "token_overrides": [],
                    "common_bundle_label": playops.COMMON_BUNDLE_LABEL, "differences": []}
    style_ops = [op for op in playops.effective(session)
                 if _route(op, images_dir=(project_mod.images_dir(ws, session.get("project")) if ws else None),
                           aa_dir=aa_dir, route_preference=pref, layout_route=lroute)[0] == "bundle"
                 and op.get("kind") in ("ReplaceToken", "SetColor", "SetSpacing")]
    if style_ops:
        from . import bundles, bundlediff, index_styles, patcher
        p_style = project_mod.new(str(session.get("project") or "session"), session.get("game_build"))
        project_mod.set_route_preference(p_style, "bundle")
        wanted_bundles = set()
        for op in style_ops:
            if op.get("kind") == "ReplaceToken":
                new = op.get("new") or {}
                p_style["token_overrides"].append({"token": new["token"], "value": new["value"]})
                style_report["token_overrides"].append({"token": new["token"], "value": new.get("value"),
                                                        "bundles": list(playops.TOKEN_BUNDLES),
                                                        "unverified_bundles": [playops.COMMON_TOKEN_BUNDLE]})
                wanted_bundles.update(playops.TOKEN_BUNDLES)
            else:
                handle = playops.declaration_edit(op)
                if handle:
                    p_style["declaration_edits"].append(handle)
                    style_report["declaration_edits"].append(handle)
                    wanted_bundles.add(handle["bundle"])
        spec = project_mod.to_spec(project_mod.validate(project_mod.migrate(p_style)))
        acc = patcher.new_acc()
        for bundle in sorted(wanted_bundles):
            src = source / bundle
            if not src.is_file():
                raise RuntimeError("the verified source has no %s" % bundle)
            sha = _sha(src)
            if identity and (identity.get("files") or {}).get(bundle) not in (None, sha):
                raise RuntimeError("the source copy of %s does not match the installation identity" % bundle)
            touched = set()

            def _patch(tree, _b=bundle):
                a = patcher.patch_sheet(tree, spec, acc)
                b = patcher.apply_declaration_edits(tree, _b, spec, acc)
                return a or b

            changed = bundles.patch_bundle(src, out, _patch, touched)
            built = (out / bundle) if (out / bundle).is_file() else src
            cmp_ = bundlediff.compare(src, built)
            sheet_pids = {name: pid for pid, name, _tree in bundles.sheets(src)}
            changed_pids = {str(o.get("path_id")) for o in (cmp_.get("object") or {}).get("changed_objects") or []}
            row = {"changed": bool(changed), "touched_sheets": len(touched),
                   "object_set_equal": (cmp_.get("object") or {}).get("object_set_equal"),
                   "changed_objects": sorted(changed_pids),
                   "tokens": {}, "common_bundle_label": (playops.COMMON_BUNDLE_LABEL
                                                         if bundle == playops.COMMON_TOKEN_BUNDLE else None)}

            def token_defs(path):
                out_defs = {}
                for pid, name, tree in bundles.sheets(path):
                    entry = index_styles.sheet_entry(bundle, tree)
                    for r in entry["rules"]:
                        if not r.get("t"):
                            continue
                        for pname, pval, _cols in r["p"]:
                            out_defs.setdefault(pname, []).append((name, r["i"], pval, str(pid)))
                return out_defs

            src_defs, out_defs = token_defs(src), token_defs(built)
            for ov in p_style["token_overrides"]:
                token = ov["token"]
                before, after = src_defs.get(token) or [], out_defs.get(token) or []
                if not before:
                    row["tokens"][token] = {"definitions": 0, "all_changed": True,
                                            "note": "token is not defined in this bundle"}
                    continue
                want_text = spec["tokens"].get(token)
                ok = len(before) == len(after) and all(v == want_text for _s, _i, v, _p in after)
                row["tokens"][token] = {"definitions": len(before), "all_changed": ok,
                                        "sheets": sorted({s for s, _i, _v, _p in before})}
                if not ok:
                    style_report["differences"].append(
                        "%s: token %s has %d definition(s), %d now carry %r"
                        % (bundle, token, len(before), sum(v == want_text for _s, _i, v, _p in after), want_text))
            # per-declaration edits: only the addressed declarations' sheets may change in this bundle
            allowed = {str(sheet_pids.get(d["sheet"])) for d in p_style["declaration_edits"]
                       if d["bundle"] == bundle}
            if allowed and changed_pids - allowed:
                style_report["differences"].append(
                    "%s: the declaration edits changed objects outside %s: %s"
                    % (bundle, ", ".join(sorted({d["sheet"] for d in p_style["declaration_edits"]
                                                 if d["bundle"] == bundle})),
                       ", ".join(sorted(changed_pids - allowed))))
            applied = [a for a in acc.get("declaration_edits") or [] if a.get("sheet") in
                       {d["sheet"] for d in p_style["declaration_edits"]}]
            row["declaration_edits"] = applied
            style_report["bundles"][bundle] = row
            if changed:
                bundle_out[bundle] = _sha(built)
        style_report["patcher_totals"] = acc.get("totals")
        style_report["tokens_found"] = sorted(acc.get("tokens_found") or [])
    report["style"] = style_report
    if style_report["differences"]:
        report["blocked"] = style_report["differences"]
        report["outputs"] = {"built_dir": str(out), "skin_folder": None, "package": None, "manifest": None,
                             "bundles": bundle_out}
        (out / "build-5g-report.json").write_text(json.dumps(report, indent=1, sort_keys=True), encoding="utf-8")
        return report

    # ---- skin-folder route: the projected fragments, through the existing native writer
    skin_folder = None
    if any(_route(op, images_dir=(project_mod.images_dir(ws, session.get("project")) if ws else None),
                  aa_dir=aa_dir, route_preference=pref, layout_route=lroute)[0] == "skin-folder"
           for op in playops.effective(session)):
        # the skin project keeps the SESSION's name so the Simple-mode image writer reads the project's own
        # images folder (ws.images/<project>) - the same payload the user picked in the app
        p = _scoped_project(session, str(session.get("project") or "session"), ws=ws, aa_dir=aa_dir,
                            route_preference=pref)
        skin_root = out / "skin"
        skin_root.mkdir(exist_ok=True)
        if aa_dir is None:
            aa_dir = source
        rep = native.export(ws, p, index, str(aa_dir), skin_root)
        skin_folder = rep["folder"]
        # byte-identical builds: the exporter stamps the export time; pin it to the build's ts
        meta_path = Path(skin_folder) / ".fm27se-export.json"
        if meta_path.is_file():
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            meta["exported_utc"] = ts
            meta["folder"] = "."                    # byte-identical builds must not embed the destination
            meta_path.write_text(json.dumps(meta, indent=1, sort_keys=True), encoding="utf-8")
        # cross-check against the patcher report: every requested token must exist in the game's styles
        token_names = set()
        try:
            for sheet in (index.sheets if index is not None else []):
                for rule in sheet.get("rules") or []:
                    for name, _v, _c in rule.get("p") or []:
                        if str(name).startswith("--"):
                            token_names.add(name)
        except Exception:
            token_names = set()
        wanted = {e["token"] for e in p.get("token_overrides") or []}
        report["skin"] = {"folder": skin_folder, "report": rep,
                          "tokens_not_found": sorted(wanted - token_names) if token_names else [],
                          "tokens_checked": bool(token_names),
                          "literal_hits": [r for r in (rep.get("notes") or []) if "literal" in r.lower()],
                          "exact_fragments": len(p["token_overrides"]) == len(wanted)
                          and len(p["scoped_rules"]) == len({(r["sheet"], r["selector"]) for r in p["scoped_rules"]})}

    # ---- outputs: schema 2 manifest + package (built files only)
    built_files = {b: bundle_out[b] for b in sorted(bundle_out)}
    style_structure = {b: {"tokens": row.get("tokens") or {},
                           "declaration_edits": row.get("declaration_edits") or [],
                           "common_bundle_label": row.get("common_bundle_label")}
                       for b, row in (style_report.get("bundles") or {}).items()}
    manifest = {"schema": 2, "kind": "build-session", "project": session.get("project"), "built_utc": ts,
                "game_build": (identity or {}).get("game_build") or session.get("game_build"),
                "source": report["source"], "files": built_files,
                "route_preference": pref,
                "structure": {"cell_changes": {b: v["built_cell_changes"] for b, v in cell_check["by_bundle"].items()},
                              "style": style_structure},
                "test_only": test_only or {},
                "optional_slot_effects": report.get("optional_slot_effects") or [],
                "addcell_placement_options": report.get("addcell_placement_options") or [],
                "referrers": report["referrers"], "integrity": _integrity(built_files)}
    (out / "build-manifest.json").write_text(json.dumps(manifest, indent=1, sort_keys=True), encoding="utf-8")
    outputs = []
    from . import bundlediff
    for b, h in sorted(built_files.items()):
        integ = _integrity_row(source, b, Path(out) / b, identity, manifest_path=manifest_path)
        cmp_ = bundlediff.compare(source / b, Path(out) / b) if (Path(out) / b).is_file() else {}
        changed = (cmp_.get("object") or {}).get("changed_objects") or []
        outputs.append({"rel_path": b, "source_sha256": (identity or {}).get("files", {}).get(b),
                        "output_sha256": h, "source_crc32": integ["catalog"].get("stored_crc32"),
                        "output_crc32": integ["catalog"].get("actual_crc32"),
                        "catalog_crc_status": integ["catalog_crc_status"],
                        "manifest_status": integ["manifest_status"], "objects_changed": len(changed),
                        "object_set_equal": (cmp_.get("object") or {}).get("object_set_equal"),
                        "integrity": integ})
    pkg = {"schema": 2, "id": ts, "project": session.get("project"), "built_utc": ts,
           "route_preference": pref, "test_only": test_only or {},
           "game_build": manifest["game_build"], "outputs": outputs,
           "files": {b: {"sha256": h, "vanilla_sha256": (identity or {}).get("files", {}).get(b)}
                     for b, h in sorted(built_files.items())},
           "gate": {"passed": True, "failures": [], "checked": {"cell_layer": True, "style_layer": bool(style_ops),
                                                               "untouched_bundles_checked": True}},
           "installable": True,
           "skin_folder": (Path(skin_folder).relative_to(out).as_posix() if skin_folder else None),
           "installation": {"status": "not installed (5G installs nothing)",
                            "preflight": "run install.preflight against a scratch installation"},
           "target": {"kind": "session-build"}, "edits": [], "validation": {"cell_layer": cell_check,
                                                                             "style_layer": style_structure},
           "overrides": {}, "impact": {"buildable": True, "installation_readiness": "preflight only"},
           "optional_slot_effects": report.get("optional_slot_effects") or [],
           "addcell_placement_options": report.get("addcell_placement_options") or [],
           "custom_layouts": custom_files}
    (out / "package.json").write_text(json.dumps(pkg, indent=1, sort_keys=True), encoding="utf-8")
    (out / "build-report.json").write_text(json.dumps(
        {"gate": {"pass": ["cell layer", "object set", "only target bundles"], "fail": []},
         "files": {b: {"changed": True, "sha256": h} for b, h in sorted(built_files.items())},
         "built_utc": ts, "project": session.get("project")}, indent=1, sort_keys=True), encoding="utf-8")
    report["outputs"] = {"built_dir": str(out), "skin_folder": skin_folder,
                         "manifest": str(out / "build-manifest.json"), "package": str(out / "package.json"),
                         "bundles": built_files}
    report["buildability"] = {"buildable": True, "reason": "every applied operation was routed and built"}
    report["installation_ready"] = {"ready": False, "reason": "5G installs nothing; installation and the runtime tests are 5H"}
    report["integrity"] = _integrity(built_files)
    (out / "build-5g-report.json").write_text(json.dumps(report, indent=1, sort_keys=True), encoding="utf-8")
    # determinism hashes exclude the report itself (it records the destination folder)
    report["outputs"]["hashes"] = [h for h in _utf8_tree(out) if not h[0].endswith("build-5g-report.json")]
    return report


def _integrity_row(source, bundle, built_path, identity, manifest_path=None):
    """The catalog/manifest comparison for one built bundle (read only): the catalog record's stored CRC against
    the built file's whole-file CRC; manifest.dat if the source carries one. A mismatch is a confirmable
    installation warning (Stage 4E/3G), never a build failure."""
    from . import catalog, bundles
    source = Path(source)
    cat_idx, cat_path = None, None
    for p in (source / "catalog.bin", source.parent / "catalog.bin", source.parent.parent / "catalog.bin"):
        if p.is_file():
            cat_idx, cat_path = catalog.read(p), p
            break
    if cat_idx is None or cat_idx.get("status") != "ok":
        cat = {"resolution": "no catalog.bin beside the source", "record_offset": None, "stored_crc32": None,
               "actual_crc32": bundles.crc32_uncompressed(built_path) if built_path.is_file() else None,
               "comparison": "not_checked"}
        status = "not_checked"
    else:
        r = catalog.resolve(cat_idx, bundle)
        rec = (r.get("records") or [None])[0] if r.get("status") == "found" else None
        actual = bundles.crc32_uncompressed(built_path) if built_path.is_file() else None
        status = catalog.catalog_crc_status(r.get("status"), (rec or {}).get("crc"), actual)
        cat = {"resolution": "found" if rec else r.get("status"), "record_offset": (rec or {}).get("offset"),
               "stored_crc32": (rec or {}).get("crc_hex"), "actual_crc32": ("%08x" % actual) if actual is not None else None,
               "comparison": status}
    from . import fmmanifest
    man_status = "manifest_not_checked"
    man = {"entry_status": "no manifest.dat found", "stored_crc32": None, "comparison": "not_checked"}
    candidates = []
    if manifest_path:
        candidates.append(Path(manifest_path))
    candidates += [source / "manifest.dat", source.parent / "manifest.dat", source.parent.parent / "manifest.dat"]
    for p in candidates:
        if not p.is_file():
            continue
        try:
            man_idx = fmmanifest.read(p)
            # Stage 4E semantics: look up the SOURCE bundle's whole-file CRC; the output must keep the same
            # CRC or the manifest.dat entry no longer matches the installed file.
            src_bytes = (source / bundle).read_bytes() if (source / bundle).is_file() else b""
            src_hit = fmmanifest.lookup(man_idx.get("data"), src_bytes)
            out_bytes = built_path.read_bytes() if built_path.is_file() else b""
            out_crc = "%08x" % (__import__("zlib").crc32(out_bytes) & 0xFFFFFFFF)
            if src_hit.get("status") == "manifest_match":
                man_status = "manifest_match" if src_hit.get("crc32") == out_crc else "manifest_mismatch"
                man = {"entry_status": "manifest_match", "stored_crc32": src_hit.get("crc32"),
                       "output_crc32": out_crc, "comparison": man_status}
            else:
                man_status = src_hit.get("status") or "manifest_entry_missing"
                man = {"entry_status": man_status, "stored_crc32": None, "output_crc32": out_crc,
                       "comparison": man_status}
        except Exception as e:
            man_status = "manifest_parse_failed"
            man = {"entry_status": str(e)[:80], "stored_crc32": None, "comparison": man_status}
        break
    return {"catalog_crc_status": status, "manifest_status": man_status,
            "catalog": cat, "manifest_dat": man,
            "source_installation": None, "catalog_source": str(cat_path) if cat_path else None}


def _integrity(built_files):
    """Stage 4E reporting: a catalog CRC mismatch is an installation warning, never a build failure."""
    return [{"bundle": b, "sha256": h, "catalog_crc": "not recomputed here",
             "status": "install-time check (Stage 3G): CRC mismatch warns, it does not fail the build"}
            for b, h in sorted(built_files.items())]


def determinism(report_a, report_b):
    """The same session twice from the same source: byte-identical outputs."""
    a, b = report_a.get("outputs") or {}, report_b.get("outputs") or {}
    ha, hb = dict(map(tuple, a.get("hashes") or [])), dict(map(tuple, b.get("hashes") or []))
    differing = sorted(k for k in set(ha) | set(hb) if ha.get(k) != hb.get(k))
    return {"identical": not differing and a.get("bundles") == b.get("bundles"),
            "differing_files": differing,
            "build_a": {"bundles": a.get("bundles"), "hashes": a.get("hashes")},
            "build_b": {"bundles": b.get("bundles"), "hashes": b.get("hashes")}}
