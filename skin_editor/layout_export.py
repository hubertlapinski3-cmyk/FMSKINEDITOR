"""Exporter: the real FM27_LayoutMCP index (index/layout-vanilla.sqlite) plus the game's composition and panel bundles -> a
`fmlayout-index/2` dump (docs/fmlayout-index-2.md) the editor imports. Read-only: the sqlite is opened with mode=ro and the bundles are only
read. The sqlite does not list the bundles the compositions live in (ui-tileslayouts, ui-tactics, ui-dynamiccardcollections) and has no panel
table, so those are read straight from the bundles here, and every cell the sqlite holds is cross-checked against the bundle it came from
(`crosscheck`) before the dump is trusted.

Where the real schema and the editor's first contract disagreed, the editor adapted (see docs/PHASE7-EVIDENCE.md): compositions carry their
bundle and path id, `max` 0 means unlimited, area anchors may be regexes, cell flags are derived from the integer columns."""
import hashlib
import json
import re
import sqlite3
import time
from pathlib import Path

from . import bundles

COMP_BUNDLES = ("ui-tileslayouts_assets_all.bundle", "ui-tactics_assets_all.bundle", "ui-dynamiccardcollections_assets_all.bundle")
PANEL_BUNDLE = "ui-panelids_assets_all.bundle"
LAYOUT_MODES = {0: "Standard", 1: "Mode1", 2: "Mode2", 4: "Mode4"}      # the real integer, kept as text where the name is not known
FLAG_COLUMNS = (("locked", "is_locked"), ("debug", "is_debug"), ("dynamic", "is_dynamic"), ("expand_to_content", "expand_to_content"),
                ("takes_focus", "takes_focus"), ("optional", "is_optional"))


def connect(path):
    p = Path(path)
    if not p.is_file():
        raise FileNotFoundError("layout index not found: %s" % p)
    return sqlite3.connect("file:%s?mode=ro" % p.as_posix(), uri=True)


def sha(path):
    return bundles.sha256(path)


def read_panels(aa_dir):
    """[(panel_id, layout guid)] from ui-panelids."""
    import UnityPy
    out = []
    for o in UnityPy.load(str(Path(aa_dir) / PANEL_BUNDLE)).objects:
        if o.type.name != "MonoBehaviour":
            continue
        try:
            t = o.read_typetree()
        except Exception:
            continue
        g = ((t.get("m_panelDescription") or {}).get("uxml") or {}).get("m_AssetGUID")
        if t.get("m_Name") and g:
            out.append((t["m_Name"], g))
    return out


def read_cells(aa_dir, bundle_names=COMP_BUNDLES):
    """{(bundle, path_id): {name, cells: [ {index, id, x, y, w, h, min, max, locked ...} ]}} straight from the bundles."""
    import UnityPy
    out = {}
    for bn in bundle_names:
        for o in UnityPy.load(str(Path(aa_dir) / bn)).objects:
            if o.type.name != "MonoBehaviour":
                continue
            try:
                t = o.read_typetree()
            except Exception:
                continue
            if "m_gridComponents" not in t:
                continue
            out[(bn, o.path_id)] = {"name": t.get("m_Name"), "cells": [
                {"index": i, "id": c.get("m_elementID"), "x": c["m_location"]["x"], "y": c["m_location"]["y"], "w": c["m_location"]["width"], "h": c["m_location"]["height"],
                 "min": (c["m_minSize"]["x"], c["m_minSize"]["y"]), "max": (c["m_maxSize"]["x"], c["m_maxSize"]["y"]), "locked": c.get("m_isLocked", 0)}
                for i, c in enumerate(t["m_gridComponents"])]}
    return out


def crosscheck(db, aa_dir):
    """The sqlite's composition cells against the bundles they were read from. Returns {compositions, cells, mismatches: [...]}."""
    real = read_cells(aa_dir)
    rows = {}
    for r in db.execute("select c.name, c.bundle, c.path_id, k.cell_index, k.element_id, k.x, k.y, k.w, k.h, k.min_w, k.min_h, k.max_w, k.max_h, k.is_locked "
                        "from compositions c join composition_cells k on k.composition_path_id = c.path_id"):
        rows[(r[1], r[2], r[3])] = r
    bad, n = [], 0
    for (bn, pid), comp in real.items():
        for c in comp["cells"]:
            n += 1
            r = rows.pop((bn, pid, c["index"]), None)
            if r is None:
                bad.append("%s cell %d is in the bundle but not in the index" % (comp["name"], c["index"]))
            elif (r[4], r[5], r[6], r[7], r[8], r[9], r[10], r[11], r[12], r[13]) != (c["id"], c["x"], c["y"], c["w"], c["h"], c["min"][0], c["min"][1], c["max"][0], c["max"][1], c["locked"]):
                bad.append("%s cell %d differs: index %s, bundle %s" % (comp["name"], c["index"], r[4:], (c["id"], c["x"], c["y"], c["w"], c["h"])))
    bad += ["%s cell %d is in the index but not in the bundle" % (k[1], k[2]) for k in list(rows)[:20]]
    return {"compositions": len(real), "cells": n, "mismatches": bad}


def _json(s, default):
    try:
        v = json.loads(s) if s else default
    except ValueError:
        return default
    return default if v is None else v


def derive_areas(layouts, elements, includes, cfg):
    """areas.json of FM27_LayoutMCP -> ({layout name: area}, anchors). scope 'layout' labels the anchor layouts, 'tree' adds the layouts
    reached from them through includes unless something outside the tree also reaches them (shared). Lower priority number wins."""
    by_id = {l["id"]: l for l in layouts}
    inc_to = {}
    for i in includes:
        inc_to.setdefault(i["from_layout_id"], set()).add(i["to_layout_id"])
    incoming = {}
    for i in includes:
        incoming.setdefault(i["to_layout_id"], set()).add(i["from_layout_id"])
    el_names, el_classes = {}, {}
    for e in elements:
        if e["name"]:
            el_names.setdefault(e["name"], set()).add(e["layout_id"])
        for c in e["classes"]:
            el_classes.setdefault(c, set()).add(e["layout_id"])
    labels, anchors = {}, []
    for area in sorted(cfg.get("areas", []), key=lambda a: a.get("priority", 99)):
        seed = set()
        for a in area["anchors"]:
            if "layout_name_regex" in a:
                rx = re.compile(a["layout_name_regex"])
                seed |= {l["id"] for l in layouts if rx.search(l["name"])}
                anchors.append({"area": area["id"], "layout_name_regex": a["layout_name_regex"]})
            elif "element_name" in a:
                seed |= el_names.get(a["element_name"], set())
                anchors.append({"area": area["id"], "element_name": a["element_name"]})
            elif "element_class" in a:
                seed |= el_classes.get(a["element_class"], set())
                anchors.append({"area": area["id"], "element_class": a["element_class"]})
        members = set(seed)
        if area.get("scope") == "tree":
            seen, stack = set(seed), list(seed)
            while stack:
                for nxt in inc_to.get(stack.pop(), ()):
                    if nxt not in seen:
                        seen.add(nxt)
                        stack.append(nxt)
            members = {i for i in seen if i in seed or incoming.get(i, set()) <= seen}
        for i in members:
            labels.setdefault(by_id[i]["name"], area["id"])
    return labels, anchors


def build_dump(sqlite_path, aa_dir, game_build, areas_json=None, now=None):
    """The dump dict (not validated; run layout_dump.validate). aa_dir: the platform folder holding the bundles the sqlite was read from."""
    aa = Path(aa_dir)
    db = connect(sqlite_path)
    q = lambda s: db.execute(s).fetchall()
    bfile = {r[0]: r[1] for r in q("select id, file from bundles")}
    recorded = {r[1]: r[2] for r in q("select id, file, sha256 from bundles")}
    layouts = [{"id": r[0], "name": r[1], "guid": r[2], "bundle": bfile[r[3]]} for r in q("select id, name, guid, bundle_id from assets where class='VisualTreeAsset'")]
    lay_ids = {l["id"] for l in layouts}
    elements = []
    for r in db.execute("select asset_id, local_id, parent_local_id, ord, type, name, classes from elements"):
        elements.append({"layout_id": r[0], "local_id": r[1], "parent_local_id": r[2], "ord": r[3], "type": r[4], "name": r[5] or "", "classes": [c for c in _json(r[6], []) if c]})
    includes = [{"from_layout_id": r[0], "element_local_id": r[1], "alias": r[2], "to_layout_id": r[3]} for r in q("select from_asset, element_local_id, alias, to_asset from includes")]
    guid_to_id = {l["guid"]: l["id"] for l in layouts}
    panels = [{"panel_id": n, "layout_id": guid_to_id[g]} for n, g in read_panels(aa) if g in guid_to_id]
    comp_name = {r[0]: r[1] for r in q("select path_id, name from compositions")}
    compositions = []
    for r in q("select name, layout_mode, preset_name, preset_w, preset_h, instantiation_order, optional_conditions_json, optional_config_conditions_json, bundle, path_id from compositions order by path_id"):
        conds = [json.dumps(c, sort_keys=True) if not isinstance(c, str) else c for c in (_json(r[6], []) or []) + (_json(r[7], []) or [])]
        compositions.append({"name": r[0], "layout_mode": LAYOUT_MODES.get(r[1], str(r[1])), "preset_name": r[2] or "", "preset_w": r[3] or 0, "preset_h": r[4] or 0,
                             "instantiation_order": [int(x) for x in _json(r[5], [])], "conditions": conds, "bundle": r[8], "path_id": r[9]})
    cells = []
    for r in db.execute("select composition_path_id, cell_index, element_id, x, y, w, h, min_w, min_h, max_w, max_h, is_locked, is_debug, is_dynamic, expand_to_content, takes_focus, is_optional, features, h_align, v_align from composition_cells order by composition_path_id, cell_index"):
        flags = [name for (name, _), v in zip(FLAG_COLUMNS, r[11:17]) if v]
        if r[17]:
            flags.append("features:%d" % r[17])
        cells.append({"composition": comp_name[r[0]], "cell_index": r[1], "element_id": r[2], "x": r[3], "y": r[4], "w": r[5], "h": r[6], "min_w": r[7], "min_h": r[8],
                      "max_w": r[9], "max_h": r[10], "flags": flags, "h_align": str(r[18]), "v_align": str(r[19])})
    cell_configs = [{"composition": comp_name[r[0]], "cell_index": r[1], "cfg_index": r[2], "size_w": r[3], "size_h": r[4], "tile_layout_id": r[5]}
                    for r in q("select composition_path_id, cell_index, cfg_index, size_w, size_h, to_asset from cell_configs order by composition_path_id, cell_index, cfg_index")]
    tiles = [{"panel_layout_id": r[0], "set_name": r[1], "breakpoint": r[2], "variant_idx": r[3], "composition": r[4], "cell_index": r[5], "cell_element_id": r[6], "cfg_index": r[7],
              "size": {"w": r[8], "h": r[9]}, "tile_layout_id": r[10]}
             for r in q("select screen_asset, set_name, breakpoint, variant_idx, composition_name, cell_index, cell_element_id, cfg_index, size_w, size_h, tile_asset from screen_tiles")]
    cfg = json.loads(Path(areas_json).read_text(encoding="utf-8")) if areas_json and Path(areas_json).is_file() else {"areas": []}
    amap, anchors = derive_areas(layouts, elements, includes, cfg)
    read_bundles = dict(recorded)
    for bn in COMP_BUNDLES + (PANEL_BUNDLE,):
        read_bundles[bn] = sha(aa / bn)
    cat = next((p for p in (aa / "catalog.hash", aa.parent / "catalog.hash") if p.is_file()), None)
    sections = {"layouts": layouts, "elements": elements, "includes": includes, "panels": panels, "tiles": tiles, "compositions": compositions, "cells": cells, "cell_configs": cell_configs}
    fp = hashlib.sha256(json.dumps({k: [len(v), hashlib.sha256(json.dumps(v, sort_keys=True).encode()).hexdigest()] for k, v in sections.items()}, sort_keys=True).encode()).hexdigest()
    meta = {"schema": "fmlayout-index/2", "game_build": game_build, "index_fingerprint": fp, "exported_at": now or time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "source": {"platform_folder": aa.name, "catalog_hash": cat.read_text(encoding="utf-8", errors="replace").strip() if cat else "", "bundles": read_bundles}}
    return dict({"meta": meta, "areas": {"map": amap, "anchors": anchors}}, **sections)
