"""Independent participating-set collection for the UiDocument acceptance gate.

This module reads the dump, parsed bundle assets, and renderer outputs directly. It never
walks UiDocument nodes or dependency edges to construct the expected sets.
"""
from collections import Counter

from ..render.html import flatten
from ..render.sheets import ROOT_SHEETS
from .composition import read as read_composition, read_descriptions


def read_panels_own(folder):
    # The inventory's OWN decode of ui-panelids (panel id -> layout GUID), deliberately NOT
    # layout_export.read_panels: the cross-check must compare two decodes of the same bundle, not a function
    # with itself. Written separately so a bug in the exporter's reader cannot propagate into the expected set.
    import UnityPy
    out = []
    for o in UnityPy.load(str(Path(folder) / "ui-panelids_assets_all.bundle")).objects:
        if o.type.name != "MonoBehaviour":
            continue
        try:
            t = o.read_typetree()
        except Exception:
            continue
        guid = ((t.get("m_panelDescription") or {}).get("uxml") or {}).get("m_AssetGUID")
        if t.get("m_Name") and guid:
            out.append((t["m_Name"], guid))
    return out


def collect(source, dump, composition, renderer):

    comp = next(c for c in dump["compositions"] if c["name"] == composition)
    rows = [t for t in dump["tiles"] if t["composition"] == composition]
    layout_rows = {r["id"]: r for r in dump["layouts"]}
    starts = {t["panel_layout_id"] for t in rows} | {t["tile_layout_id"] for t in rows}
    includes = {}
    for row in dump["includes"]:
        includes.setdefault(row["from_layout_id"], []).append(row)
    closure, todo = set(), sorted(starts)
    while todo:
        lid = todo.pop()
        if lid in closure or lid not in layout_rows:
            continue
        closure.add(lid)
        todo.extend(r["to_layout_id"] for r in includes.get(lid, []))

    inv = {k: set() for k in ("layouts", "tiles", "templates", "stylesheets", "rules", "tokens", "hard_coded_colours", "fonts", "images", "compositions", "bundles", "ui_elements", "placement_bindings", "serialized_references", "panels", "tile_descriptions")}
    inv["compositions"].add("composition:" + composition)
    comp_bundle = comp.get("bundle")
    if comp_bundle:
        inv["bundles"].add("bundle:" + comp_bundle)
    for lid in closure:
        row = layout_rows[lid]
        inv["layouts"].add("layout:" + row["guid"])
        if row.get("bundle"):
            inv["bundles"].add("bundle:" + row["bundle"])
        target = source.target(row["guid"])
        if target:
            inline = source.inline_sheet(*target)
            if inline and "bundle" in inline:
                inv["stylesheets"].add("inline_sheet:" + row["guid"])
                inv["bundles"].add("bundle:" + inline["bundle"])
        target = source.target(row["guid"])
        if target:
            inline = source.inline_sheet(*target)
            if inline and "bundle" in inline:
                inv["stylesheets"].add("inline_sheet:" + row["guid"])
                inv["bundles"].add("bundle:" + inline["bundle"])
        for edge in includes.get(lid, []):
            source_guid = row["guid"]
            target_row = layout_rows.get(edge["to_layout_id"])
            target_guid = target_row["guid"] if target_row else "unresolved"
            inv["templates"].add("template-ref:%s:%s:%s" % (source_guid, edge["element_local_id"], target_guid))
        for row in dump["panels"]:              # G9: the panel id -> layout link, cross-checked with a DIRECT read of ui-panelids
            if row["layout_id"] in closure:
                inv["panels"].add("panel:" + row["panel_id"])
        if comp_bundle:
            try:
                lay_ids = {r["id"]: r["guid"] for r in dump["layouts"]}
                for panel_id, guid in read_panels_own(source.store.folder):
                    if guid in {lay_ids[i] for i in closure}:
                        inv["panels"].add("panel:" + panel_id)
            except Exception:
                pass                            # the direct read is a cross-check; the dump rows stay the base

    for i, tile in enumerate(rows):
        inv["tiles"].add("tile:%s:%s:%s:%s:%s" % (composition, tile["cell_index"], tile["cfg_index"], tile["size"]["w"], tile["size"]["h"]))
    raw, _err = read_composition(source, comp_bundle, comp["path_id"], renderer)
    if raw:
        for side in ("m_topLeft", "m_top", "m_topRight", "m_left", "m_right", "m_bottomLeft", "m_bottom", "m_bottomRight"):
            for i, slot in enumerate((raw["fields"].get("m_optionalSlices") or {}).get(side) or []):
                inv["tiles"].add("tile:%s:optional:%s:%d" % (composition, side, i))
        for i, _binding in enumerate(raw["fields"].get("m_placementBindings") or []):
            inv["placement_bindings"].add("placement:%s:%d" % (composition, i))
        for i, ref in enumerate(raw["pointers"]):
            identity = ref.get("guid") or ref.get("path_id", "unknown")
            inv["serialized_references"].add("asset-ref:%s:%d:%s" % (composition, i, identity))
            if ref.get("bundle"):
                inv["bundles"].add("bundle:" + ref["bundle"])
        # ADDENDUM read 1: the cells' tile-configuration descriptions, collected straight from the bundle
        descs, derr = read_descriptions(source, comp_bundle, raw["fields"])
        if descs:
            for rec_ in descs:
                for d_ in rec_["descriptions"]:
                    if not d_.get("read"):
                        continue
                    inv["tile_descriptions"].add("tile_description:%s:%s" % (composition, d_["path_id"]))
                    for cfg in d_["configurations"]:                     # ADDENDUM read 2: every layout a configuration points at
                        guid = cfg.get("asset_guid")
                        targets = []
                        if guid:
                            try:
                                targets = source.guid_objects(guid) or []
                            except Exception:
                                targets = []
                        for tb, tp_ in targets:
                            try:
                                obj_ = source.store._bundle_objs(tb).get(int(tp_))
                                tree_ = obj_.read_typetree() if obj_ is not None else None
                            except Exception:
                                tree_ = None
                            if isinstance(tree_, dict) and "m_VisualTree" in tree_:
                                inv["layouts"].add("layout:" + guid)
                                inv["bundles"].add("bundle:" + tb)
                                break

    for sheet in renderer.bank.ordered():
        inv["stylesheets"].add("sheet:%s/%s" % (sheet.bundle, sheet.name))
        inv["bundles"].add("bundle:" + sheet.bundle)
    occurrence, rule_ids = Counter(), {}
    for sheet in renderer.bank.ordered():
        for rule in sheet.rules:
            selectors = tuple(c[2] for c in rule["chains"])
            occurrence[(sheet.name, selectors)] += 1
            rule_ids[(sheet.name, rule["i"])] = "rule:%s/%s|%s|#%d" % (sheet.bundle, sheet.name, ", ".join(selectors), occurrence[(sheet.name, selectors)] - 1)

    top = {r["id"]: r for r in dump["layouts"]}
    top_ids = {t["panel_layout_id"] for t in rows} | {t["tile_layout_id"] for t in rows}
    top_names = sorted({top[i]["name"] for i in top_ids if i in top})
    catalog = renderer.layouts.catalog()
    by_name = {r["name"]: r for r in catalog}
    for element in dump["elements"]:
        if element["layout_id"] not in closure:
            continue
        row = layout_rows[element["layout_id"]]
        target = source.target(row["guid"])
        if not target:
            continue
        bundle, path_id = target
        physical = source.physical_locator(bundle, path_id, "VisualTreeAsset")
        inv["ui_elements"].add("physical-element:%s:%s:%s:%s:%s" % (physical["build_identity"], physical["bundle_sha256"], physical["serialized_file"], physical["path_id"], element["local_id"]))
    for name in top_names:
        layout = by_name.get(name)
        if not layout:
            continue
        result = renderer.layout(layout["bundle"], layout["path_id"], 64)
        inv["bundles"].add("bundle:" + layout["bundle"])
        for target in renderer.layouts._target.values():
            if target:
                inv["bundles"].add("bundle:" + target[0])
        for node in flatten(result["tree"]):
            node_layout = by_name.get(node.get("layout"))
            if node_layout:
                physical = source.physical_locator(node_layout["bundle"], node_layout["path_id"], "VisualTreeAsset")
                inv["ui_elements"].add("physical-element:%s:%s:%s:%s:%s" % (physical["build_identity"], physical["bundle_sha256"], physical["serialized_file"], physical["path_id"], node.get("id")))
            for match in node.get("matched") or []:
                if (match["sheet"], match["rule"]) in rule_ids:
                    inv["rules"].add(rule_ids[(match["sheet"], match["rule"])])
            for prop, decl in (node.get("computed") or {}).items():
                for token in decl.get("tokens") or []:
                    if isinstance(token, str):
                        inv["tokens"].add("token:" + token)
                value = str(decl.get("value"))
                if value.startswith("#") or value.startswith("rgb(") or value.startswith("rgba("):
                    if not decl.get("tokens"):
                        src = decl.get("source") or {}
                        if src.get("inherited"):
                            src = src.get("from") or {}
                        if src.get("inline"):
                            if node_layout:
                                where = "inline:%s:%s:%s" % (node_layout["bundle"], node_layout["path_id"], node.get("id"))
                            else:
                                where = None
                        elif (src.get("sheet"), src.get("rule")) in rule_ids:
                            where = rule_ids[(src["sheet"], src["rule"])]
                        else:
                            where = None
                        if where:
                            inv["hard_coded_colours"].add("literal:%s|%s|%s" % (where, prop, value))
                for prop, asset in (node.get("assets") or {}).items():
                    if isinstance(asset, dict) and "bundle" in asset and "path_id" in asset:
                        aid = "asset:%s:%s" % (asset["bundle"], asset["path_id"])
                        kind = "fonts" if prop == "-unity-font-definition" else "images"
                        inv[kind].add(aid)
                        inv["bundles"].add("bundle:" + asset["bundle"])

    for token_id in inv["tokens"]:
        token = token_id.removeprefix("token:")
        for sheet in renderer.bank.ordered():
            for rule in sheet.rules:
                if rule["token"] and any(prop.startswith("--") and prop == token for prop, _value, _colour in rule["props"]):
                    inv["rules"].add(rule_ids[(sheet.name, rule["i"])])

    return {key: sorted(values) for key, values in inv.items()}

