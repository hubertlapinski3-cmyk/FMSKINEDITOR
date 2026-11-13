"""Build plan: what a build of a project would do for a target, and what it would drop, computed from the project model and the style
index without writing anything. The same operations are what the gate verifies and the change summary prints.

Operation kinds: RewriteToken, ReplaceLiteral, AppendRule, ReplaceRule, RemoveDeclaration, MoveCell, SetColumnWidth, HideColumn, ShowColumn, MoveColumn, SetClasses, SetInline, SetAttr, WriteFont, RenameClass, ReplaceTexture, PasteIcon, ReplaceVector, NativeWriteSheet,
NativeCopyAsset, NativeSheetPassthrough. Each: {op, count, summary, detail: [...] (capped)}."""
from . import club_colours, images, native
from . import project as project_mod

CAP = 200


def _op(op, summary, detail):
    return {"op": op, "count": len(detail), "summary": summary, "detail": detail[:CAP], "truncated": len(detail) > CAP}


def _hits(index, sheet, selector):
    """How many rules of the game sheet have exactly this selector list (None when the selector does not parse)."""
    from . import token_patch as tp
    try:
        want = tp.selector_key(selector)
        return sum(1 for sh in index.sheets if sh["name"] == sheet for r in sh["rules"]
                   if frozenset(k for t in r["s"] for k in tp.selector_key(t)) == want)
    except Exception:
        return None


def plan(ws, project, index, aa_dir=None, target=None):
    p = project_mod.validate(project_mod.migrate(project))
    target = target or p["options"].get("output", "bundles")
    if target not in project_mod.OUTPUTS:
        raise ValueError("target must be bundles or native")
    ops, dropped, warnings = [], [], []
    sheets = {s["name"] for s in index.sheets} if index else set()
    reverts = set(p.get("reverts", []))
    club_off = p["options"].get("club_colours", True) is False

    toks = [e for e in p.get("token_overrides", []) if e["token"] not in reverts]
    detail = []
    for e in toks:
        n = len(index.defs.get(e["token"], {})) if index else 0
        if index and n == 0:
            warnings.append("token %s is not defined in any game sheet (the override has nothing to rewrite)" % e["token"])
        detail.append({"token": e["token"], "value": project_mod.patch_text(e["value"]), "defined_in_sheets": n})
    if toks:
        ops.append(_op("RewriteToken", "Rewrite %d token definition(s) in every game sheet that defines them" % len(toks) if target == "bundles"
                       else "Write %d token override(s) to tokens.uss" % len(toks), detail))

    ns = p.get("native_sheets", [])
    if ns:
        if target == "native":
            ops.append(_op("NativeSheetPassthrough", "Copy %d sheet(s) of the imported skin unchanged (%s), then this project's own sheets" % (len(ns), p.get("native_name", "")), [{"sheet": s} for s in ns]))
        else:
            dropped.append({"item": "%d native sheet(s) of %s" % (len(ns), p.get("native_name", "the imported skin")), "reason": "USS skin sheets only apply to the native target"})
    swaps = p.get("literal_swaps", [])
    if swaps:
        if target == "native":
            rules, _notes = native.literal_rules(p, index)
            ops.append(_op("ReplaceLiteral", "Copy %d game rule(s) that use a swapped colour, with the new colour" % len(rules),
                           [{"swap": "%s -> %s (%s)" % (project_mod.patch_text(e["from"]), project_mod.patch_text(e["to"]), e["mode"])} for e in swaps]))
        else:
            d = []
            for e in swaps:
                from . import colour
                f = colour.from_obj(e["from"])
                hits = len(index.literal(colour.hex6(f), f[3])["exact"]) if (index and e["mode"] == "rgba") else len(index.literal(colour.hex6(f), 1.0)["rgb_all"]) if index else 0
                d.append({"swap": "%s -> %s (%s)" % (project_mod.patch_text(e["from"]), project_mod.patch_text(e["to"]), e["mode"]), "hits": hits})
            ops.append(_op("ReplaceLiteral", "Recolour %d literal swap(s) in place in every sheet" % len(swaps), d))

    by_sheet, rep, rem = {}, [], []
    for e in p.get("scoped_rules", []):
        if index and e["sheet"] not in sheets:
            warnings.append("rule %r targets the sheet %s, which this game build does not have" % (e["selector"][:50], e["sheet"]))
        if e.get("op") and target == "bundles":
            n = _hits(index, e["sheet"], e["selector"]) if index else None
            if n == 0:
                warnings.append("%s %r matches no rule of the sheet %s: the build's gate would fail" % (e["op"], e["selector"][:50], e["sheet"]))
            (rem if e["op"] == "remove" else rep).append({"sheet": e["sheet"], "selector": e["selector"], "rules_hit": n,
                                                          **({"properties": e["remove"] or "all declarations"} if e["op"] == "remove" else {"properties": list(e["props"])})})
            continue
        if e.get("op") == "remove":          # native
            dropped.append({"item": "remove: %s%s" % (e["selector"][:50], (" | " + ", ".join(e["remove"])) if e["remove"] else ""),
                            "reason": "USS cannot delete a game declaration; use the bundle target"})
            continue
        by_sheet.setdefault(e["sheet"], []).append(e)
    if rep:
        ops.append(_op("ReplaceRule", "Change %d game rule selector(s) in place (the rule keeps its place and specificity)" % len(rep), rep))
    if rem:
        ops.append(_op("RemoveDeclaration", "Remove declarations from %d game rule selector(s)" % len(rem), rem))
    if by_sheet:
        ops.append(_op("AppendRule", "Append %d scoped rule(s) to %d sheet(s)%s" % (sum(map(len, by_sheet.values())), len(by_sheet), "; Build raises specificity where a game rule would win" if target == "bundles" else ""),
                       [{"sheet": s, "rules": len(r)} for s, r in by_sheet.items()]))
    if club_off:
        n_nav = native.nav_on_light_rules(index)[1] if (target == "native" and index) else 0
        ops.append(_op("AppendRule", "Remove club colours: %d proven rule(s)%s" % (len(club_colours.rules(p["options"].get("club_colours_replacement", project_mod.CLUB_DEFAULT))),
                       (" + %d .nav-on-light rule(s)" % n_nav) if target == "native" else " + class renames nav-on-light/dark"),
                       [{"replacement": project_mod.patch_text(p["options"].get("club_colours_replacement", project_mod.CLUB_DEFAULT))}]))
        if target == "bundles":
            ops.append(_op("RenameClass", "Rename 2 club-theme classes in every sheet", [{"from": k, "to": v} for k, v in club_colours.RENAMES.items()]))

    renames = p.get("rename_classes", {})
    if renames:
        if target == "bundles":
            ops.append(_op("RenameClass", "Rename %d class(es) in every sheet" % len(renames), [{"from": k, "to": v} for k, v in renames.items()]))
        else:
            dropped.append({"item": "class renames (%d)" % len(renames), "reason": "USS cannot rename classes; use the bundle target"})
    if p["options"].get("flatten_gradients"):
        if target == "native":
            dropped.append({"item": "flatten_gradients", "reason": "a bundle-build option; not expressible in USS"})
        else:
            ops.append(_op("AppendRule", "Flatten gradients (copy each start colour into its end colour)", [{"option": "flatten_gradients"}]))

    lp = p.get("layout_patches", [])
    if lp:
        n_ops = sum(len(d["ops"]) for d in lp)
        if target == "bundles":
            for kind, title in (("set-classes", "SetClasses"), ("set-inline", "SetInline"), ("set-attr", "SetAttr")):
                rows = [{"layout": d["layout"]["name"], "bundle": d["layout"]["bundle"], "element": o["id"], "guard": "%s#%s" % (o["guard"]["type"], o["guard"].get("name", "")),
                         **({"add": o.get("add", []), "remove": o.get("remove", [])} if kind == "set-classes" else {"props": o["props"]} if kind == "set-inline" else {"attribute": o["name"], "value": o["value"]})}
                        for d in lp for o in d["ops"] if o["op"] == kind]
                if rows:
                    ops.append(_op(title, "%s on %d element(s) in %d layout(s) (a copy of the layout bundle is patched; elements are never added, removed or moved)" % (
                        {"SetClasses": "Add/remove classes", "SetInline": "Set inline styles", "SetAttr": "Set attributes"}[title], len(rows), len({r["layout"] for r in rows})), rows))
        else:
            dropped.append({"item": "%d layout edit(s) in %d layout(s)" % (n_ops, len(lp)), "reason": "UXML edits change the game's layout bundles; a native skin cannot. Use the bundle target"})
    tp_ = p.get("table_patches", [])
    if tp_:
        if target == "bundles":
            for kind, title, what in (("set-width", "SetColumnWidth", "Set column widths"), ("hide-column", "HideColumn", "Hide columns"), ("show-column", "ShowColumn", "Show columns"), ("move-column", "MoveColumn", "Move columns")):
                rows = [{"view": d["view"]["name"], "column": o["column"], **({"width": o["width"]} if kind == "set-width" else {"after": o.get("after")} if kind in ("show-column", "move-column") else {})} for d in tp_ for o in d["ops"] if o["op"] == kind]
                if rows:
                    ops.append(_op(title, "%s in %d table view(s) (a copy of ui-tableviews is patched; the column list is edited, nothing else)" % (what, len({r["view"] for r in rows})), rows))
        else:
            dropped.append({"item": "%d table edit(s) in %d view(s)" % (sum(len(d["ops"]) for d in tp_), len(tp_)), "reason": "table views live in the game's ui-tableviews bundle; a native skin cannot change them. Use the bundle target"})
    from . import tiles as tiles_mod
    try:
        tops = tiles_mod.ops_for(ws, p["name"]) if ws is not None else []
    except (ValueError, OSError) as ex:
        tops = []
        warnings.append("tile position edits cannot be built: %s" % ex)
    if tops:
        if target == "bundles":
            ops.append(_op("MoveCell", "Move %d grid cell(s) in %d composition(s) (x, y only; the composition bundle copy is patched, sizes are never written)" % (len(tops), len({o["composition"] for o in tops})),
                           [{"composition": o["composition"], "cell": "%d (%s)" % (o["cell_index"], o["cell_id"]), "from": "%d,%d" % (o["from"]["x"], o["from"]["y"]), "to": "%d,%d" % (o["to"]["x"], o["to"]["y"]), "bundle": o["bundle"]} for o in tops]))
        else:
            dropped.append({"item": "%d tile position edit(s)" % len(tops), "reason": "grid compositions live in the game's bundles; a native skin cannot move cells. Use the bundle target"})
    fonts = p.get("font_swaps", [])
    if fonts:
        if target == "native":
            ops.append(_op("WriteFont", "Copy %d font file(s) into the skin and point their tokens at them with url()" % len(fonts), [{"token": f["token"], "file": f["source"]} for f in fonts]))
            if index:
                for f in fonts:
                    if f["token"] not in index.defs:
                        warnings.append("font token %s is not defined in any game sheet (the skin would define a token nothing uses)" % f["token"])
        else:
            dropped.append({"item": "%d font swap(s)" % len(fonts), "reason": "the bundle route needs TextCore FontAssets (SDF atlas); see docs/PHASE6-FONTS-SPIKE.md. Use the native target"})
    if p.get("image_swaps"):                                  # the asset conflict report (errors and warnings) is part of the plan's warnings
        from . import assetcheck
        try:
            cat = images.catalog(ws, aa_dir) if aa_dir else None
            cls = images.icon_classes(aa_dir) if (aa_dir and target == "native") else None
            warnings += ["%s: %s" % (r["severity"], r["message"]) for r in assetcheck.conflicts(ws, p, cat, cls, target) if r["severity"] != "info"]
        except Exception as ex:
            warnings.append("asset check could not run: %s" % ex)
    classes = images.icon_classes(aa_dir) if (target == "native" and aa_dir and any(e["kind"] != "texture" for e in p.get("image_swaps", []))) else {}
    tex, ico, vec, assets = [], [], [], []
    for e in p.get("image_swaps", []):
        if target == "bundles":
            if e["kind"] == "texture":
                tex.append({"image": e["name"], "bundle": e["bundle"]})
            elif e["kind"] == "icon":
                ico.append({"icon": e["name"], "atlases": "1x 2x 3x 4x"})
            else:
                vec.append({"svg": e["name"], "bundle": e["bundle"]})
        elif e["kind"] == "texture":
            where = e.get("where") or native.default_places(e["name"])
            assets.append({"image": e["name"], "wallpaper_on": [native.PLACES[w][0] for w in where]})
        else:
            key = ("icon", e["name"]) if e["kind"] == "icon" else ("svg", str(e["path_id"]))
            cls = classes.get(key)
            if cls:
                assets.append({"image": e["name"], "classes": cls})
            else:
                dropped.append({"item": "%s %s" % (e["kind"], e["name"]), "reason": "no USS class draws it (it is placed in code); use the bundle target"})
    for kind, rows, text in (("ReplaceTexture", tex, "Replace %d texture(s) inside the bundles"), ("PasteIcon", ico, "Paste %d icon(s) into the atlases"),
                             ("ReplaceVector", vec, "Replace %d vector icon(s) with the SVG's filled shapes")):
        if rows:
            ops.append(_op(kind, text % len(rows), rows))
    if assets:
        ops.append(_op("NativeCopyAsset", "Copy %d image(s) into the skin folder and style them by class or place" % len(assets), assets))

    if target == "native":
        ops.append(_op("NativeWriteSheet", "Write skin.json and 3 sheets (tokens.uss, rules.uss, images.uss) into the skins folder", [{"folder": str(native.skins_root() or "?")}]))
    else:
        ops.append(_op("NativeWriteSheet", "Patch fresh copies of the snapshot bundles, run the gate, then install with a backup", [{"bundles": "style bundles + any image bundles used"}]))
    return {"project": p["name"], "target": target, "operations": ops, "dropped": dropped, "warnings": warnings,
            "totals": {"operations": len(ops), "dropped": len(dropped), "warnings": len(warnings)}}
