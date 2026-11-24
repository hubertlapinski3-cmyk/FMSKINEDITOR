"""The typed build plan and the dependency-impact policy (Stage 4D; docs/rea/STAGE-4A-ARCHITECTURE.md sections 6.5 and 6.6,
owner decisions D1 and D2 of the Stage 4D brief).

WHAT THIS COLLECTS. A project's edits, regrouped per bundle into SECTIONS (a bundle can hold more than one kind):
each typed section carries the asset it edits (bundle, CAB when known, path id), the adapter that owns the edit,
the edit's D1 kind, the adapter's validation findings and its evidence. Sources are the project's own data - the sheet
spec (project.to_spec), the stored placement edits (tiles.ops_for), the image swaps - exactly what the existing
pipeline builds from; the plan does not invent edits. Layout and table patches flow through the existing pipeline steps
and are listed as untyped sections, labelled as such.

D1 POLICY (unknown affected bundles), as approved:
  value      unknown references do not change asset identity or references -> ALLOW the asset's own bundle to build;
             possibly-affected referrers are REPORTED, never silently turned into a confirmed-safe result
  identity    unknown referrers could depend on the changed identity -> BLOCK by default, overridable only by an
             explicit recorded decision (allow_unknown_impact)
  reference   new targets and dependency changes must be established -> BLOCK until resolved (same override)
  unknown     impact cannot be classified safely -> BLOCK, no override
A build being possible (buildable) and its dependency impact being settled (installation_readiness) are reported as two
separate states; a value edit with an unresolved graph is buildable and its readiness is "uncertain", never "ready".

D2 (tile overlap) is enforced by the composition adapter's validation; the plan relays its findings and records the
override decision (build parameter or the pair's edit-time confirmation) for the manifest.

READ ONLY: collecting a plan opens bundles from the vanilla snapshot (and, for validation, the target objects) and
queries the registry; nothing is written by anything in this module.
"""
from . import adapters, depgraph, images, project as project_mod
from . import placement, tiles

EDIT_KINDS = ("value", "reference", "identity")


class BuildPlanError(ValueError):
    """The plan cannot be assembled (no dump for stored position edits, a sheet the game no longer has, ...)."""


def _asset(reg, bundle, path_id, role):
    """The asset row (with CAB) from the registry, or a minimal record without one. The CAB is needed for the graph
    queries; without a registry the plan says so instead of guessing."""
    if path_id is None:
        return {"bundle": bundle, "cab": None, "path_id": None, "name": None, "type": None, "role": None}, False
    a = {"bundle": bundle, "cab": None, "path_id": str(path_id), "name": None, "type": None, "role": None}
    if reg is None:
        return a, False
    rows = reg.search_assets(bundle=bundle, path_id=str(path_id))["assets"]
    if not rows:
        return a, False
    row = next((r for r in rows if role in (r.get("role"), r.get("type"))), rows[0])
    return {"bundle": bundle, "cab": row["cab"], "path_id": str(path_id), "name": row.get("name"),
            "type": row.get("type"), "role": row.get("role"), "guid": row.get("guid")}, True


# ---------------------------------------------------------------- collection
def sheet_ops(ws, spec):
    """The typed sheet section of the two style bundles: which sheets the token/literal pass runs over, and which
    named sheets get appended or replaced rules."""
    from . import bundles
    out = {}
    touched = bool(spec.get("tokens")) or bool(spec.get("literal_map")) or bool(spec.get("rgba_swaps")) \
        or bool(spec.get("flatten_gradients")) or bool(spec.get("rename_classes"))
    appended, edited = spec.get("append_rules_by_sheet", {}), spec.get("edit_rules_by_sheet", {})
    if not (touched or appended or edited):
        return out
    for name in sorted(set(bundles.STYLE_BUNDLES) & set((ws.vanilla_manifest() or {}).get("files", {}))):
        try:
            sheets = list(bundles.sheets(ws.vanilla / name))
        except Exception as ex:
            raise BuildPlanError("the vanilla copy of %s cannot be read: %s" % (name, ex))
        by_name = {sheet_name: pid for pid, sheet_name, _ in sheets}
        out[name] = {"touched_all": touched, "sheets": {str(pid): sheet_name for pid, sheet_name, _ in sheets},
                     "appended": {s: len(appended[s]) for s in appended if s in by_name},
                     "edited": {s: len(edited[s]) for s in edited if s in by_name},
                     "missing": sorted(set(list(appended) + list(edited)) - set(by_name))}
    return out


def collect(ws, project, spec=None, tile_ops=None):
    """The project's edits grouped per bundle into sections. Raises BuildPlanError when the edits cannot be built at
    all (the same conditions the existing build refuses on). Does not validate geometry or dependency impact."""
    spec = spec or project_mod.to_spec(project)
    groups = {}

    def add(bundle, section, ops, typed=True):
        g = groups.setdefault(bundle, {"bundle": bundle, "sections": {}, "typed": False, "steps": []})
        g["sections"][section] = ops
        g["typed"] = g["typed"] or typed

    for name, ops in sheet_ops(ws, spec).items():
        add(name, "sheet_spec", ops)
    try:
        if tile_ops is not None:
            raw_tile_ops = tile_ops
        elif project_mod.experimental_bundle_layout_edits(project):
            raw_tile_ops = tiles.ops_for(ws, project["name"])
        else:
            raw_tile_ops = []
        for op in tiles.validate_ops(raw_tile_ops):
            g = groups.setdefault(op["bundle"], {"bundle": op["bundle"], "sections": {}, "typed": False, "steps": []})
            s = g["sections"].setdefault("tile_moves", {"moves": [], "compositions": []})
            s["moves"].append(op)
            if op["composition"] not in s["compositions"]:
                s["compositions"].append(op["composition"])
    except ValueError as ex:
        raise BuildPlanError(str(ex))
    swaps, icons = {}, []
    for e in project.get("image_swaps", []):
        if e["kind"] == "icon":
            icons.append(e)
        else:
            swaps.setdefault(e["bundle"], []).append(e)
    for bundle, es in swaps.items():
        add(bundle, "image_swaps", {"swaps": es})
    if icons:
        for s in images.SCALES:
            for pat in (images.ICONS, images.ATLASES):
                bn = pat % s
                if bn in (ws.vanilla_manifest() or {}).get("reference", {}).get("bundles", {}) \
                        or bn in (ws.vanilla_manifest() or {}).get("image_files", {}):
                    add(bn, "icon_swaps", {"swaps": icons})
    for doc in project.get("layout_patches", []):
        add(doc["layout"]["bundle"], "layout_patch", {"docs": 1, "ops": len(doc.get("ops", []))}, typed=False)
    for doc in project.get("table_patches", []):
        add(doc["view"]["bundle"], "table_patch", {"docs": 1, "ops": len(doc.get("ops", []))}, typed=False)
    return groups


# ---------------------------------------------------------------- validation (adapters) and impact (D1)
def validate(ws, groups, spec, grid=None, placements=None, reg=None, allow_overlap=False):
    """Run every typed section's adapter validation. `grid` is the placement Grid of the imported dump (None without
    a dump); `placements` is the stored placement doc (edit-time confirmations)."""
    findings = []
    confirmed = set()
    for e in (placements or {}).get("edits", []):
        for cid in e.get("confirmed_collisions", []):
            confirmed.add(tuple(sorted((e["id"], cid))))
    for bundle, g in sorted(groups.items()):
        s = g["sections"].get("sheet_spec")
        if s:
            f = adapters.by_name("stylesheet").validate(
                {"spec": spec, "skip_sheets": spec.get("skip_sheets", []), "appended_sheets": list(s["appended"]),
                 "edited_sheets": list(s["edited"])}, {})
            findings += [dict(x, bundle=bundle) for x in f]
            for sheet in s.get("missing", []):                       # a game update may move a sheet to another bundle:
                findings.append(dict(adapters.finding(              # reported as before, never silently dropped
                    "warning", "sheet_not_in_bundle",
                    "no sheet named %s in %s (game updated?); its rules are not applied and the build report lists it "
                    "under sheets_not_found" % (sheet, bundle)), bundle=bundle))
        s = g["sections"].get("tile_moves")
        if s:
            comp_adapter = adapters.by_name("composition")
            for comp in s["compositions"]:
                moves = [m for m in s["moves"] if m["composition"] == comp]
                f = comp_adapter.validate({"composition": comp, "bundle": bundle, "path_id": moves[0]["path_id"], "moves": moves},
                                          {"grid": grid, "confirmed": confirmed, "allow_overlap": allow_overlap})
                findings += [dict(x, bundle=bundle, path_id=str(moves[0]["path_id"])) for x in f]
        s = g["sections"].get("image_swaps")
        if s:
            # a bundle not in the snapshot yet is caught by the build step itself (its message says how to add it);
            # the adapter only validates what it can open
            if (ws.vanilla / bundle).is_file():
                f = adapters.by_name("texture").validate({"bundle": bundle, "swaps": s["swaps"]},
                                                         {"source_bundle": ws.vanilla / bundle})
                findings += [dict(x, bundle=bundle) for x in f]
            else:
                findings.append(dict(adapters.finding(
                    "error", "bundle_not_in_snapshot",
                    "%s is not in the vanilla snapshot yet; pick the image again (it adds the bundle)" % bundle,
                    bundle=bundle)))
        s = g["sections"].get("icon_swaps")
        if s:
            f = adapters.by_name("sprite").validate({"bundle": bundle, "swaps": s["swaps"]}, {})
            findings += [dict(x, bundle=bundle) for x in f]
    return findings


def impact(reg, groups):
    """The D1 dependency-impact rows: one per edited asset, from depgraph.affected when the registry knows the asset;
    'not_evaluated' (with its reason) when it does not. A missing evaluation never silently becomes a safe result."""
    rows, notes = [], []
    if reg is None:
        notes.append("no installation inventory is selected, so the dependency impact was not evaluated; a value edit "
                     "still builds its own bundle by policy (D1) and its readiness is reported as uncertain, not ready")
    for bundle, g in sorted(groups.items()):
        s = g["sections"].get("sheet_spec")
        if s:
            for pid, sheet_name in sorted(s["sheets"].items(), key=lambda kv: kv[1]):
                if s["touched_all"] or sheet_name in s["appended"] or sheet_name in s["edited"]:
                    rows.append(_impact_row(reg, bundle, pid, "stylesheet", "value", name=sheet_name))
        s = g["sections"].get("tile_moves")
        if s:
            for comp in s["compositions"]:
                m = next(m for m in s["moves"] if m["composition"] == comp)
                rows.append(_impact_row(reg, bundle, m["path_id"], "composition", "value", name=comp))
        s = g["sections"].get("image_swaps")
        if s:
            for e in s["swaps"]:
                rows.append(_impact_row(reg, bundle, e["path_id"], "texture", "value", name=e.get("name")))
        s = g["sections"].get("icon_swaps")
        if s:
            for e in s["swaps"]:
                rows.append(_impact_row(reg, bundle, e["path_id"], "sprite", "value", name=e.get("name")))
    return {"policy": "D1: a value edit builds its own bundle and its referrers are reported as possibly affected at "
                      "runtime; an identity or reference edit blocks until its impact is resolved (an explicit recorded "
                      "override can pass a blocked case); an edit whose kind cannot be classified blocks outright",
            "evaluated": reg is not None, "per_asset": rows, "notes": notes}


def _impact_row(reg, bundle, path_id, adapter, edit_kind, name=None):
    asset, found = _asset(reg, bundle, path_id, _ROLE_OF[adapter])
    row = {"asset": dict(asset, name=name), "adapter": adapter, "edit_kind": edit_kind,
           "status": "not_evaluated", "reason": None, "rebuild_required": [bundle],
           "possibly_affected_at_runtime": [], "unknown": [], "evidence": {}}
    if reg is None:
        row["reason"] = "no installation inventory is selected"
        return row
    if not found:
        row["reason"] = "the asset is not in the inventory (its bundle was not scanned, or the game was updated)"
        return row
    try:
        r = depgraph.affected(reg, asset["bundle"], asset["cab"], asset["path_id"], edit_kind)
    except Exception as ex:
        row["reason"] = "the impact query failed: %s: %s" % (type(ex).__name__, ex)
        return row
    row.update(status=r["status"], reason=None, rebuild_required=r["rebuild_required"],
               possibly_affected_at_runtime=r["possibly_affected_at_runtime"], unknown=r["unknown"],
               evidence=r["evidence"])
    return row


_ROLE_OF = {"stylesheet": "StyleSheet", "composition": "GridComposition", "texture": "Texture2D", "sprite": "Sprite"}


# ---------------------------------------------------------------- the D1 decision
def policy(findings, impact_rows, allow_unknown_impact=False):
    """Apply D1 (and D2, whose errors arrive as adapter findings). Returns the blocked findings, whether the build can
    run (buildable), the installation readiness, and the recorded overrides. A blocked identity/reference case can be
    passed only by the explicit allow_unknown_impact decision; an unclassifiable edit blocks with no override."""
    blocked = [f for f in findings if f["level"] == "error"]
    for r in impact_rows:
        if r["edit_kind"] not in EDIT_KINDS:
            blocked.append({"level": "error", "code": "unknown_edit_kind", "message":
                            "an edit of %s has an unknown kind %r, so its impact cannot be classified safely; the build is "
                            "refused" % (r["asset"]["bundle"], r["edit_kind"]), "asset": r["asset"]})
        elif r["edit_kind"] in ("identity", "reference") and r["status"] != "complete":
            if not allow_unknown_impact:
                blocked.append({"level": "error", "code": "impact_unresolved", "message":
                                "the %s edit of %s has unresolved dependencies (%s); the build is refused until they are "
                                "resolved, or until you explicitly allow it (recorded in the manifest)"
                                % (r["edit_kind"], r["asset"]["bundle"], r.get("reason") or "status %s" % r["status"]),
                                "asset": r["asset"], "impact": r})
    ready = "ready"
    if any(r["status"] in ("unknown", "not_evaluated") for r in impact_rows):
        ready = "uncertain"
    if blocked:
        ready = "blocked"
    return {"blocked": blocked, "buildable": not blocked, "installation_readiness": ready,
            "overrides": {"allow_overlap": any(f.get("code") == "tile_overlap" and f.get("override") for f in findings),
                          "allow_overlap_source": next((f.get("override_source") for f in findings
                                                        if f.get("code") == "tile_overlap" and f.get("override")), None),
                          "allow_unknown_impact": bool(allow_unknown_impact)}}


# ---------------------------------------------------------------- the review (read only)
def review(ws, project, index=None, reg=None, allow_overlap=False, allow_unknown_impact=False, tile_ops=None):
    """The typed plan of a project: per-bundle sections with adapter ops, the validation findings, the D1 impact
    section with buildability and installation readiness separate, and what would block the build. Read only."""
    project = project_mod.validate(project_mod.migrate(project))
    spec = project_mod.to_spec(project)
    groups = collect(ws, project, spec, tile_ops)
    grid = placement._grid(ws)
    placements = placement._read(ws, project["name"])
    findings = validate(ws, groups, spec, grid, placements, reg, allow_overlap)
    imp = impact(reg, groups)
    pol = policy(findings, imp["per_asset"], allow_unknown_impact)
    snap = _snapshot_bundles(ws)
    bundles_out = {}
    for bundle, g in sorted(groups.items()):
        ops, primary = [], None
        for section, s in g["sections"].items():
            if section == "sheet_spec":
                primary = primary or "stylesheet"
                for pid, sheet_name in sorted(s["sheets"].items(), key=lambda kv: kv[1]):
                    if s["touched_all"] or sheet_name in s["appended"] or sheet_name in s["edited"]:
                        kind = ("token_and_literal_pass" if s["touched_all"] else "") + \
                               ("|append_rules" if sheet_name in s["appended"] else "") + \
                               ("|edit_rules" if sheet_name in s["edited"] else "")
                        ops.append(_op(reg, bundle, pid, "stylesheet", {"op": kind.strip("|"), "sheet": sheet_name,
                                       "appended": s["appended"].get(sheet_name, 0), "edited": s["edited"].get(sheet_name, 0)},
                                       sheet_name, findings))
            elif section == "tile_moves":
                primary = primary or "composition"
                for comp in s["compositions"]:
                    moves = [m for m in s["moves"] if m["composition"] == comp]
                    ops.append(_op(reg, bundle, moves[0]["path_id"], "composition",
                                   {"moves": [{"cell_index": m["cell_index"], "cell_id": m["cell_id"], "to": m["to"]} for m in moves]},
                                   comp, [f for f in findings if f.get("bundle") == bundle and f.get("composition") == comp]))
            elif section == "image_swaps":
                primary = primary or "texture"
                for e in s["swaps"]:
                    ops.append(_op(reg, bundle, e["path_id"], "texture",
                                   {"kind": e["kind"], "source": e["source"], "fit": e.get("fit")}, e.get("name"),
                                   [f for f in findings if f.get("bundle") == bundle and str(f.get("path_id")) == str(e["path_id"])]))
            elif section == "icon_swaps":
                primary = primary or "sprite"
                for e in s["swaps"]:
                    ops.append(_op(reg, bundle, e["path_id"], "sprite", {"kind": "icon", "source": e["source"]},
                                   e.get("name"), [f for f in findings if f.get("bundle") == bundle and f.get("code") == "sprite_edited_through_atlas"]))
            elif section in ("layout_patch", "table_patch"):
                ops.append({"asset": {"bundle": bundle, "cab": None, "path_id": None}, "adapter": None, "adapter_version": None,
                            "edit_kind": None, "ops": dict(s, step="existing pipeline (uxml.apply_patches / tables.apply_patches)"),
                            "evidence": None, "validation": [], "build_step": "uxml.apply_patches" if section == "layout_patch" else "tables.apply_patches",
                            "typed": False})
        bundles_out[bundle] = {"bundle": bundle, "adapter": primary, "typed": g["typed"], "in_snapshot": bundle in snap,
                               "sections": sorted(g["sections"]), "ops": ops,
                               "note": None if g["typed"] else
                               "built through the existing pipeline step; not a typed adapter yet "
                               "(Stage 4D scope: stylesheet, composition, texture, sprite)"}
    return {"project": project["name"], "bundles": bundles_out, "findings": findings,
            "impact": dict(imp, buildable=pol["buildable"], installation_readiness=pol["installation_readiness"]),
            "overrides": pol["overrides"], "blocked": pol["blocked"]}


def _op(reg, bundle, path_id, adapter, ops, name, validation):
    """One typed op record for the plan and the manifest, with the adapter's validation findings attached."""
    a = adapters.by_name(adapter)
    asset, _ = _asset(reg, bundle, path_id, _ROLE_OF[adapter])
    return {"asset": dict(asset, name=name), "adapter": adapter, "adapter_version": adapters.VERSION,
            "edit_kind": a.edit_kind, "ops": ops, "evidence": a.evidence,
            "validation": validation, "build_step": _STEP_OF[adapter]}


_STEP_OF = {"stylesheet": "bundles.patch_bundle + patcher.patch_sheet (token_patch.SheetPatcher)",
           "composition": "tiles.apply_ops", "texture": "images.apply_swaps", "sprite": "images.apply_icon_swaps"}


def _snapshot_bundles(ws):
    man = ws.vanilla_manifest() or {}
    return set(man.get("files", {})) | set(man.get("image_files", {}))
