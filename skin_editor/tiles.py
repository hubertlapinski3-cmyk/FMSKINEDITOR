"""Tile layout writes: cell POSITIONS (x, y), sizes (m_location width/height + m_maxSize) and ADDED cells of grid
compositions, written into a copy of the composition bundles.

An op is one of:
  {op: "move-cell",   bundle, path_id, composition, cell_index, cell_id, from:{x,y}, to:{x,y}}
  {op: "resize-cell", bundle, path_id, composition, cell_index, cell_id, from:{x,y,w,h}, to:{x,y,w,h}, max:{x,y}}
  {op: "add-cell",    bundle, path_id, composition, cell_index, cell_id, geometry:{x,y,w,h},
                      description:{path_id, config_index}}
`cell_id` and `from` are guards: the composition must still hold that cell (by index and m_elementID) at the
position the edit was made against, else the build refuses, so an edit never lands on something a game update
moved. An added cell REUSES an existing description and one of its configurations (no new description, no new
identity) and must be new within the composition (grid cells, optional slices and placement bindings). Everything
else in the composition, and every other object of the bundle, stays as it was; `check_ops` proves that on the
built file."""
import copy
import json
from pathlib import Path

from . import bundles, layout_dump, placement

TILE_BUNDLES = ("ui-tileslayouts_assets_all.bundle", "ui-tactics_assets_all.bundle", "ui-dynamiccardcollections_assets_all.bundle")


def ops_for(ws, project_name):
    """Build ops from the project's stored placement edits (placement.json of Milestone D): every edit that is not stale and moves x or y.
    Raises ValueError when the edits cannot be built (no dump, composition without bundle/path id, a size or config change)."""
    doc = placement.load(ws, project_name)
    edits = [e for e in doc["edits"] if e.get("state") != "stale" and e.get("geometry")]
    if not edits:
        return []
    d = layout_dump.load(ws)
    if d is None:
        raise ValueError("position edits are stored but no layout dump is imported")
    comps = {c["name"]: c for c in d["compositions"]}
    ops = []
    for e in edits:
        c = comps.get(e["composition"])
        old, new = e["old"]["geometry"], e["geometry"]
        if not c or "bundle" not in c or "path_id" not in c:
            raise ValueError("composition %s has no bundle/path id in the dump: re-export the layout dump with the current exporter" % e["composition"])
        if (old["w"], old["h"]) != (new["w"], new["h"]):
            raise ValueError("%s cell %d: a size change cannot be written (size is derived from the cell's configs)" % (e["composition"], e["cell_index"]))
        if e.get("config") is not None:
            raise ValueError("%s cell %d: a config change cannot be written yet" % (e["composition"], e["cell_index"]))
        if (old["x"], old["y"]) == (new["x"], new["y"]):
            continue
        ops.append({"op": "move-cell", "bundle": c["bundle"], "path_id": str(c["path_id"]), "composition": e["composition"], "cell_index": e["cell_index"],
                    "cell_id": e["cell_element_id"], "from": {"x": old["x"], "y": old["y"]}, "to": {"x": new["x"], "y": new["y"]}})
    return ops


def validate_ops(ops):
    seen = set()
    for o in ops:
        if o.get("op") == "add-tile-size":
            if o.get("bundle") != "ui-tileslayouts_assets_all.bundle":
                raise ValueError("an add-tile-size op must target ui-tileslayouts_assets_all.bundle")
            sz = o.get("size")
            if not isinstance(sz, dict) or set(sz) != {"x", "y"} or not all(isinstance(n, int) and not isinstance(n, bool) and n >= 1 for n in sz.values()):
                raise ValueError("an add-tile-size needs positive integer size {x, y}")
            guid = o.get("reuse_guid")
            if not isinstance(guid, str) or len(guid) != 32:
                raise ValueError("an add-tile-size must reuse an existing 32-char UXML GUID (never create a new one)")
            key = ("add-tile-size", o["bundle"], str(o["path_id"]), sz["x"], sz["y"])
            if key in seen:
                raise ValueError("tile size %sx%s on %s is added twice" % (sz["x"], sz["y"], o.get("description") or o["path_id"]))
            seen.add(key)
            continue
        if o.get("op") in ("set-add-tile", "set-remove-tile"):
            if o.get("bundle") != "ui-tileslayouts_assets_all.bundle":
                raise ValueError("a grid-element-set op must target ui-tileslayouts_assets_all.bundle")
            if not o.get("description_path_id"):
                raise ValueError("a grid-element-set op needs description_path_id")
            key = (o["op"], o["bundle"], str(o["path_id"]), str(o["description_path_id"]))
            if key in seen:
                raise ValueError("grid-element-set op on %s is duplicated" % o["description_path_id"])
            seen.add(key)
            continue
        if o.get("op") in ("slot-add", "slot-remove", "slot-reorder"):
            if not o.get("cell_id") and o.get("op") != "slot-reorder":
                raise ValueError("a slot op needs the element id it adds or removes")
            if not isinstance(o.get("direction") or "", str) or not (o.get("direction") or "").startswith("m_"):
                raise ValueError("a slot op needs a region such as m_bottom")
            if o["op"] == "slot-add":
                d = o.get("description") or {}
                if not d.get("path_id") or not isinstance(d.get("config_index"), int):
                    raise ValueError("a slot-add needs {path_id, config_index} of an existing description")
            if o["op"] == "slot-reorder" and not isinstance(o.get("order"), list):
                raise ValueError("a slot-reorder needs the element ids in their new order")
            key = (o["bundle"], o["path_id"], o.get("direction"), o.get("cell_id") or ",".join(o.get("order") or []))
            if key in seen:
                raise ValueError("slot %s is changed twice" % (o.get("cell_id") or o.get("direction")))
            seen.add(key)
            continue
        if o.get("op") == "set-max-size":          # SC2: only the cell's m_maxSize; its position and size are not touched
            if o.get("bundle") not in TILE_BUNDLES:
                raise ValueError("a set-max-size is in one of: " + ", ".join(TILE_BUNDLES))
            for k in ("from", "max"):
                v = o.get(k)
                if not isinstance(v, dict) or set(v) != {"x", "y"} or not all(isinstance(n, int) and not isinstance(n, bool) and n >= 1 for n in v.values()):
                    raise ValueError("a set-max-size needs positive integer %s {x, y}" % k)
            key = (o["bundle"], o["path_id"], o["cell_index"])
            if key in seen:
                raise ValueError("cell %s of %s is changed twice" % (o["cell_index"], o["composition"]))
            seen.add(key)
            continue
        if o.get("op") not in ("move-cell", "resize-cell", "add-cell") or o["bundle"] not in TILE_BUNDLES:
            raise ValueError("a tile op is a move-cell, resize-cell, add-cell, set-max-size or slot op in one of: " + ", ".join(TILE_BUNDLES))
        if o.get("op") == "add-cell":
            for k in ("cell_id", "description"):
                if not o.get(k):
                    raise ValueError("an add-cell needs %s" % ("the new cell's element id" if k == "cell_id"
                                                               else "the description and configuration it reuses"))
            d = o["description"]
            if not isinstance(d, dict) or not d.get("path_id") or not isinstance(d.get("config_index"), int) \
                    or isinstance(d.get("config_index"), bool) or d["config_index"] < 0:
                raise ValueError("an add-cell's description needs {path_id, config_index} (an EXISTING description)")
            g = o.get("geometry")
            if not isinstance(g, dict) or set(g) != {"x", "y", "w", "h"} or not all(isinstance(v, int) and not isinstance(v, bool) for v in g.values()):
                raise ValueError("an add-cell needs integer geometry {x, y, w, h}")
            if g["x"] < 0 or g["y"] < 0 or g["w"] < 1 or g["h"] < 1:
                raise ValueError("an added cell cannot be at a negative position or have a non-positive size")
        else:
            for k in ("from", "to"):
                if set(o[k]) not in ({"x", "y"}, {"x", "y", "w", "h"}) or not all(isinstance(v, int) and not isinstance(v, bool) for v in o[k].values()):
                    raise ValueError("%s needs integer x and y (and w, h for a resize)" % k)
        if o.get("op") == "resize-cell":
            if "w" not in o["to"] or o["to"]["w"] < 1 or o["to"]["h"] < 1:
                raise ValueError("a resize needs positive width and height")
            mx = o.get("max")
            if mx is not None and (set(mx) != {"x", "y"} or not all(isinstance(v, int) and v >= 1 for v in mx.values())):
                raise ValueError("max needs positive integer x and y")
            if mx is not None and (mx["x"] < o["to"]["w"] or mx["y"] < o["to"]["h"]):
                raise ValueError("max must be at least the new width and height")
        if o.get("op") != "add-cell" and (o["to"]["x"] < 0 or o["to"]["y"] < 0):
            raise ValueError("a cell cannot be moved to a negative position")
        key = (o["bundle"], o["path_id"], o["cell_index"])
        if key in seen:
            raise ValueError("cell %s of %s is changed twice" % (o["cell_index"], o["composition"]))
        seen.add(key)
    return ops


def _cell(t, op, where):
    cells = t.get("m_gridComponents") or []
    i = op["cell_index"]
    if not 0 <= i < len(cells) or cells[i].get("m_elementID") != op["cell_id"]:
        raise ValueError("%s: cell %d is not %r any more (game updated? re-do this edit)" % (where, i, op["cell_id"]))
    loc = cells[i]["m_location"]
    if (loc["x"], loc["y"]) != (op["from"]["x"], op["from"]["y"]):
        raise ValueError("%s: cell %s is at (%d, %d), the edit was made against (%d, %d) (game updated? re-do this edit)" % (where, op["cell_id"], loc["x"], loc["y"], op["from"]["x"], op["from"]["y"]))
    return cells[i]


def _description_config(objs, description):
    """The existing description's configuration dict (Description/Size/Asset/AssetRef/Type) it reuses, or a refusal."""
    pid = int(description["path_id"])
    obj = objs.get(pid)
    if obj is None or obj.type.name != "MonoBehaviour":
        raise ValueError("the add-cell's description (path id %s) is not in this bundle" % description["path_id"])
    t = obj.read_typetree()
    cfgs = t.get("<Configurations>k__BackingField") or []
    i = description["config_index"]
    if not 0 <= i < len(cfgs):
        raise ValueError("the description %s has %d configuration(s); index %d does not exist"
                         % (t.get("m_Name") or description["path_id"], len(cfgs), i))
    return copy.deepcopy(cfgs[i]), (t.get("m_Name") or str(description["path_id"]))


def _all_element_ids(tree):
    """Every element id the composition already uses: grid cells, optional slices and placement bindings."""
    ids = {c.get("m_elementID") for c in tree.get("m_gridComponents") or []}
    for group in (tree.get("m_optionalSlices") or {}).values():
        if isinstance(group, list):
            ids.update(x.get("m_elementID") for x in group if isinstance(x, dict))
    ids.update(b.get("m_elementID") for b in tree.get("m_placementBindings") or [] if isinstance(b, dict))
    ids.discard(None)
    return ids


def _added_cell(template, op, cfg):
    cell = copy.deepcopy(template)
    size = cfg.get("Size") or {}
    cell["m_elementID"] = op["cell_id"]
    cell["m_configDescriptions"] = [{"m_FileID": 0, "m_PathID": int(op["description"]["path_id"])}]
    cell["m_configDescriptionKeys"] = []
    cell["m_gridElementConfigs"] = [cfg]
    cell["m_location"] = {"x": op["geometry"]["x"], "y": op["geometry"]["y"],
                          "width": op["geometry"]["w"], "height": op["geometry"]["h"]}
    cell["m_minSize"] = {"x": size.get("x"), "y": size.get("y")}
    cell["m_maxSize"] = {"x": size.get("x"), "y": size.get("y")}
    for k in ("m_isLocked", "m_isDebug", "m_isDynamic", "m_features", "m_expandToContent",
              "m_takesFocus", "m_isOptional", "m_horizontalAlignment", "m_verticalAlignment"):
        if k in cell:
            cell[k] = 0
    return cell


def _slot_template(t, direction):
    """A copy of the region's first slice (key order/shape), or a grid cell's shape when the region is empty."""
    region = ((t.get("m_optionalSlices") or {}).get(direction) or [])
    base = region[0] if region and isinstance(region[0], dict) else (
        (t.get("m_gridComponents") or [None])[0])
    return copy.deepcopy(base) if isinstance(base, dict) else {}


def _element_index(t, direction, position):
    """The flat element index of a slice: grid cells first, then the slice regions in their stored order."""
    idx = len(t.get("m_gridComponents") or [])
    for reg, items in (t.get("m_optionalSlices") or {}).items():
        if reg == "m_instantiationOrder" or not isinstance(items, list):
            continue
        if reg == direction:
            return idx + position
        idx += len(items)
    return None


def _apply_slot_op(t, op, objs):
    slices = t.setdefault("m_optionalSlices", {})
    order = slices.get("m_instantiationOrder")
    direction = op.get("direction") or "m_bottom"
    region = slices.setdefault(direction, [])
    if op["op"] == "slot-add":
        if op["cell_id"] in _all_element_ids(t):
            raise ValueError("%s: element id %r is already used in this composition (grid, optional slice or "
                             "placement binding)" % (op["composition"], op["cell_id"]))
        cfg, name = _description_config(objs, op["description"])
        size = cfg.get("Size") or {}
        w, h = size.get("x"), size.get("y")
        loc = op.get("location")
        if loc is None:
            x = (region[0].get("m_location") or {}).get("x", 16) if region else 16
            y = max(((e.get("m_location") or {}).get("y", 0) + (e.get("m_location") or {}).get("height", 0))
                    for e in region) if region else 0
            loc = {"x": x, "y": y, "width": w, "height": h}
        if (loc.get("width"), loc.get("height")) != (w, h):
            raise ValueError("%s: the added slot must use its configuration's own size %sx%s (asked %sx%s)"
                             % (op["composition"], w, h, loc.get("width"), loc.get("height")))
        entry = _slot_template(t, direction)
        entry.update({"m_elementID": op["cell_id"],
                      "m_configDescriptions": [{"m_FileID": 0, "m_PathID": int(op["description"]["path_id"])}],
                      "m_configDescriptionKeys": [], "m_gridElementConfigs": [cfg],
                      "m_location": {"x": loc["x"], "y": loc["y"], "width": w, "height": h},
                      "m_minSize": {"x": w, "y": h}, "m_maxSize": {"x": w, "y": h}})
        for k in ("m_isLocked", "m_isDebug", "m_isDynamic", "m_features", "m_expandToContent",
                  "m_takesFocus", "m_isOptional", "m_horizontalAlignment", "m_verticalAlignment"):
            if k in entry:
                entry[k] = 0
        new_index = _element_index(t, direction, len(region))
        region.append(entry)
        if isinstance(order, list) and new_index is not None and not op.get("no_order_extension"):
            order.append(new_index)
    elif op["op"] == "slot-remove":
        idx = next((i for i, e in enumerate(region) if e.get("m_elementID") == op["cell_id"]), None)
        if idx is None:
            raise ValueError("%s: no optional slice %r in %s" % (op["composition"], op["cell_id"], direction))
        elem_index = _element_index(t, direction, idx)
        region.pop(idx)
        if isinstance(order, list) and elem_index is not None:
            slices["m_instantiationOrder"] = [i if i < elem_index else i - 1 for i in order if i != elem_index]
    elif op["op"] == "slot-reorder":
        ids = [e.get("m_elementID") for e in region]
        if sorted(op["order"]) != sorted(ids):
            raise ValueError("%s: the new order must name exactly the %s slices (%s), got %s"
                             % (op["composition"], direction, ", ".join(ids), ", ".join(op["order"])))
        by = {e.get("m_elementID"): e for e in region}
        new_order = [by[i] for i in op["order"]]
        y = 0
        for e in new_order:                                  # the row comes from m_location.y, so reordering must
            loc = e.setdefault("m_location", {})            # reassign the offsets in the new order
            loc["y"] = y
            y += loc.get("height", 1)
        slices[direction] = new_order
    else:
        raise ValueError("unknown slot op %r" % op["op"])


def apply_ops(src, out_dir, ops, touched=None):
    """Patch one composition bundle; writes out_dir/<name> when anything changed. Returns (changed, notes, path ids saved)."""
    validate_ops(ops)
    import UnityPy
    env = UnityPy.load(str(src))
    objs = {o.path_id: o for o in env.objects}
    by = {}
    for o in ops:
        by.setdefault(int(o["path_id"]), []).append(o)
    done = []
    for pid, group in by.items():
        obj = objs.get(pid)
        t = obj.read_typetree() if obj is not None and obj.type.name == "MonoBehaviour" else None
        if all(op.get("op") in ("add-tile-size", "set-add-tile", "set-remove-tile") for op in group):
            if not isinstance(t, dict):
                raise ValueError("%s: object %s not found" % (Path(src).name, pid))
            for op in group:
                _apply_bundle_catalog_op(t, op, objs)
            obj.save_typetree(t)
            done.append(pid)
            continue
        if not isinstance(t, dict) or "m_gridComponents" not in t or t.get("m_Name") != group[0]["composition"]:
            raise ValueError("%s: composition %s (path id %s) not found (game updated? re-export the layout dump)" % (Path(src).name, group[0]["composition"], pid))
        for op in group:
            if op["op"] in ("slot-add", "slot-remove", "slot-reorder"):
                _apply_slot_op(t, op, objs)
                continue
            if op["op"] == "add-cell":
                cells = t["m_gridComponents"]
                if op["cell_id"] in _all_element_ids(t):
                    raise ValueError("%s: element id %r is already used in this composition (grid, optional slice or "
                                     "placement binding); an added cell needs a new id" % (op["composition"], op["cell_id"]))
                if int(op["cell_index"]) != len(cells):
                    raise ValueError("%s: an added cell goes at index %d (the current end), not %d"
                                     % (op["composition"], len(cells), op["cell_index"]))
                cfg, desc_name = _description_config(objs, op["description"])
                size = cfg.get("Size") or {}
                if (op["geometry"]["w"], op["geometry"]["h"]) != (size.get("x"), size.get("y")):
                    raise ValueError("%s: the added cell must use its configuration's own size %sx%s (asked %sx%s)"
                                     % (op["composition"], size.get("x"), size.get("y"),
                                        op["geometry"]["w"], op["geometry"]["h"]))
                template = next((c for c in cells if c.get("m_isDynamic") == 0), cells[0]) if cells else {}
                cells.append(_added_cell(template, op, cfg))
                bindings = t.get("m_placementBindings")
                if isinstance(bindings, list) and not any(b.get("m_elementID") == op["cell_id"] for b in bindings):
                    bindings.append({"m_elementID": op["cell_id"], "m_optionalConditions": [],
                                     "m_optionalConfigConditions": []})
                continue
            if op["op"] == "set-max-size":
                cells = t["m_gridComponents"]
                i = int(op["cell_index"])
                if not 0 <= i < len(cells) or cells[i].get("m_elementID") != op["cell_id"]:
                    raise ValueError("%s: cell %d is not %r any more (game updated? re-do this edit)" % (op["composition"], i, op["cell_id"]))
                cur = cells[i]["m_maxSize"]
                if (cur.get("x"), cur.get("y")) != (op["from"]["x"], op["from"]["y"]):
                    raise ValueError("%s: cell %s has m_maxSize %sx%s, the edit was made against %sx%s"
                                     % (op["composition"], op["cell_id"], cur.get("x"), cur.get("y"), op["from"]["x"], op["from"]["y"]))
                cur["x"], cur["y"] = op["max"]["x"], op["max"]["y"]
                continue
            c = _cell(t, op, "%s" % op["composition"])
            c["m_location"]["x"], c["m_location"]["y"] = op["to"]["x"], op["to"]["y"]
            if op["op"] == "resize-cell":
                if (loc_w := c["m_location"].get("width"), c["m_location"].get("height")) != (op["from"].get("w"), op["from"].get("h")):
                    raise ValueError("%s: cell %s is %sx%s, the edit was made against %sx%s" % (op["composition"], op["cell_id"], c["m_location"].get("width"), c["m_location"].get("height"), op["from"].get("w"), op["from"].get("h")))
                c["m_location"]["width"], c["m_location"]["height"] = op["to"]["w"], op["to"]["h"]
                if op.get("max") is not None:
                    c["m_maxSize"]["x"], c["m_maxSize"]["y"] = op["max"]["x"], op["max"]["y"]
        obj.save_typetree(t)
        done.append(pid)
    if touched is not None:
        touched.update(done)
    if done:
        (Path(out_dir) / Path(src).name).write_bytes(env.file.save(packer="original"))
    notes = []
    if done:
        moves = sum(1 for o in ops if o["op"] == "move-cell")
        resizes = sum(1 for o in ops if o["op"] == "resize-cell")
        adds = sum(1 for o in ops if o["op"] == "add-cell")
        maxes = sum(1 for o in ops if o["op"] == "set-max-size")
        notes.append("%d cell change(s) in %d composition(s): %d move(s), %d resize(s), %d add(s), %d max-size change(s)"
                     % (len(ops), len(done), moves, resizes, adds, maxes))
    return bool(done), notes, done


def _leaf_diffs(a, b, path=""):
    """Every leaf path where two typetrees differ (iterative; NaN-safe)."""
    out, stack = [], [(a, b, path)]
    while stack:
        x, y, p = stack.pop()
        if type(x) != type(y):
            out.append(p or "/")
        elif isinstance(x, dict):
            if list(x) != list(y):
                out.append(p + "{keys}")
                continue
            stack.extend((x[k], y[k], "%s/%s" % (p, k)) for k in x)
        elif isinstance(x, list):
            if len(x) != len(y):
                out.append(p + "[len]")
                continue
            stack.extend((u, v, "%s[%d]" % (p, i)) for i, (u, v) in enumerate(zip(x, y)))
        elif x != y and not (x != x and y != y):
            out.append(p or "/")
    return out


def check_ops(vanilla_path, built_path, ops):
    """Gate: in every addressed composition the only differences between vanilla and built are m_location.x / m_location.y of the addressed
    cells, and they hold the asked-for values. Returns a list of failures. (The generic checks - object set equal, every other object
    identical to vanilla - run on the whole bundle in verify_static.)"""
    import UnityPy
    fail = []
    vo = {o.path_id: o for o in UnityPy.load(str(vanilla_path)).objects}
    bo = {o.path_id: o for o in UnityPy.load(str(built_path)).objects}
    by = {}
    for o in ops:
        by.setdefault(int(o["path_id"]), []).append(o)
    for pid, group in by.items():
        name = group[0].get("composition") or group[0].get("description") or group[0].get("element_set") or str(pid)
        try:
            vt, bt = vo[pid].read_typetree(), bo[pid].read_typetree()
        except Exception as ex:
            fail.append("%s cannot be read (%s)" % (name, ex))
            continue
        catalog_ops = [o for o in group if o["op"] in ("add-tile-size", "set-add-tile", "set-remove-tile")]
        if catalog_ops:
            for op in catalog_ops:
                if op["op"] == "add-tile-size":
                    cfgs = bt.get("<Configurations>k__BackingField") or []
                    sz, guid = op["size"], op["reuse_guid"]
                    if not any((c.get("Size") or {}).get("x") == sz["x"] and (c.get("Size") or {}).get("y") == sz["y"]
                               and ((c.get("AssetRef") or c.get("Asset") or {}).get("m_AssetGUID")) == guid for c in cfgs):
                        fail.append("%s: added size %sx%s with GUID %s missing" % (name, sz["x"], sz["y"], guid))
                elif op["op"] == "set-add-tile":
                    pids = {str(p.get("m_PathID")) for p in (bt.get("m_gridElementDescriptions") or ())}
                    if str(op["description_path_id"]) not in pids:
                        fail.append("%s: description %s not added to GridElementSet" % (name, op["description_path_id"]))
                elif op["op"] == "set-remove-tile":
                    pids = {str(p.get("m_PathID")) for p in (bt.get("m_gridElementDescriptions") or ())}
                    if str(op["description_path_id"]) in pids:
                        fail.append("%s: description %s not removed from GridElementSet" % (name, op["description_path_id"]))
            continue
        slots = [o for o in group if o["op"] in ("slot-add", "slot-remove", "slot-reorder")]
        if slots:
            if bt.get("m_gridComponents") != vt.get("m_gridComponents"):
                fail.append("%s: the grid cells changed while editing optional slots" % name)
            vs, bs = vt.get("m_optionalSlices") or {}, bt.get("m_optionalSlices") or {}
            touched_regions = {o.get("direction") or "m_bottom" for o in slots}
            for reg in sorted(set(vs) | set(bs)):
                if reg == "m_instantiationOrder":
                    continue
                if reg not in touched_regions and vs.get(reg) != bs.get(reg):
                    fail.append("%s: optional region %s changed while editing %s" % (name, reg, ", ".join(touched_regions)))
            for op in slots:
                reg = op.get("direction") or "m_bottom"
                vlist, blist = vs.get(reg) or [], bs.get(reg) or []
                if op["op"] == "slot-add":
                    e = next((x for x in blist if x.get("m_elementID") == op["cell_id"]), None)
                    if e is None:
                        fail.append("%s: added slot %s is not in %s" % (name, op["cell_id"], reg))
                    else:
                        loc = e.get("m_location") or {}
                        want = op.get("location") or {}
                        if want and (loc.get("x"), loc.get("y"), loc.get("width"), loc.get("height")) != \
                                (want.get("x"), want.get("y"), want.get("width"), want.get("height")):
                            fail.append("%s: added slot %s is at %s, expected %s" % (name, op["cell_id"], loc, want))
                        d = (e.get("m_configDescriptions") or [{}])[0]
                        if str(d.get("m_PathID")) != str((op.get("description") or {}).get("path_id")):
                            fail.append("%s: added slot %s points at description %s" % (name, op["cell_id"], d.get("m_PathID")))
                elif op["op"] == "slot-remove":
                    if any(x.get("m_elementID") == op["cell_id"] for x in blist):
                        fail.append("%s: slot %s was not removed from %s" % (name, op["cell_id"], reg))
                elif op["op"] == "slot-reorder":
                    ids = [x.get("m_elementID") for x in blist]
                    if ids != list(op.get("order") or []):
                        fail.append("%s: %s order is %s, expected %s" % (name, reg, ids, op.get("order")))
            # final region membership/order from the original list + the ops, so a remove+add pair is judged together
            for reg in sorted(touched_regions):
                expected = [x.get("m_elementID") for x in (vs.get(reg) or [])]
                for op in slots:
                    if (op.get("direction") or "m_bottom") != reg:
                        continue
                    if op["op"] == "slot-add":
                        expected.append(op["cell_id"])
                    elif op["op"] == "slot-remove" and op["cell_id"] in expected:
                        expected.remove(op["cell_id"])
                    elif op["op"] == "slot-reorder":
                        expected = list(op.get("order") or [])
                got = [x.get("m_elementID") for x in (bs.get(reg) or [])]
                if got != expected:
                    fail.append("%s: %s final order is %s, expected %s" % (name, reg, got, expected))
            continue
        adds = [o for o in group if o["op"] == "add-cell"]
        if adds:
            vc = vt.get("m_gridComponents") or []
            bc = bt.get("m_gridComponents") or []
            if len(bc) != len(vc) + len(adds):
                fail.append("%s: %d cell(s) added, expected %d" % (name, len(bc) - len(vc), len(adds)))
            else:
                addressed = {int(o["cell_index"]) for o in group if o["op"] != "add-cell"}
                for i, cell in enumerate(vc):
                    if i not in addressed and bc[i] != cell:
                        fail.append("%s: existing cell %d changed while adding a cell" % (name, i))
                        break
                for op in sorted(adds, key=lambda o: o["cell_index"]):
                    i = int(op["cell_index"])
                    c = bc[i]
                    if c.get("m_elementID") != op["cell_id"]:
                        fail.append("%s: added cell %d is %r, expected %r" % (name, i, c.get("m_elementID"), op["cell_id"]))
                    loc = c.get("m_location") or {}
                    if (loc.get("x"), loc.get("y"), loc.get("width"), loc.get("height")) != \
                            (op["geometry"]["x"], op["geometry"]["y"], op["geometry"]["w"], op["geometry"]["h"]):
                        fail.append("%s: added cell %s has location %s" % (name, op["cell_id"], loc))
                    descs = c.get("m_configDescriptions") or [{}]
                    if str(descs[0].get("m_PathID")) != str(op["description"]["path_id"]):
                        fail.append("%s: added cell %s points at description %s, expected %s"
                                    % (name, op["cell_id"], descs[0].get("m_PathID"), op["description"]["path_id"]))
                    cfgs = c.get("m_gridElementConfigs") or [{}]
                    size = (cfgs[0].get("Size") or {})
                    if (size.get("x"), size.get("y")) != (op["geometry"]["w"], op["geometry"]["h"]):
                        fail.append("%s: added cell %s uses configuration size %s, expected %dx%d"
                                    % (name, op["cell_id"], size, op["geometry"]["w"], op["geometry"]["h"]))
                binds = {b.get("m_elementID") for b in bt.get("m_placementBindings") or [] if isinstance(b, dict)}
                for op in adds:
                    if op["cell_id"] not in binds:
                        fail.append("%s: added cell %s has no placement binding" % (name, op["cell_id"]))
        want = {}
        for op in group:
            if op["op"] == "add-cell":
                continue
            if op["op"] == "set-max-size":          # the one intended leaf pair; any other changed leaf is "unexpected"
                mb = "/m_gridComponents[%d]/m_maxSize/" % op["cell_index"]
                want[mb + "x"], want[mb + "y"] = op["max"]["x"], op["max"]["y"]
                continue
            base = "/m_gridComponents[%d]/m_location/" % op["cell_index"]
            want[base + "x"], want[base + "y"] = op["to"]["x"], op["to"]["y"]
            if op["op"] == "resize-cell":
                want[base + "width"], want[base + "height"] = op["to"]["w"], op["to"]["h"]
                if op.get("max") is not None:
                    mb = "/m_gridComponents[%d]/m_maxSize/" % op["cell_index"]
                    want[mb + "x"], want[mb + "y"] = op["max"]["x"], op["max"]["y"]
        if adds:
            pass
        else:
            got = set(_leaf_diffs(vt, bt))
            extra = sorted(got - set(want))
            missing = sorted(p for p in want if p not in got and not _same(vt, p, want[p]))
            if extra:
                fail.append("%s: unexpected changes at %s" % (name, ", ".join(extra[:4])))
            for p in want:
                v = _at(bt, p)
                if v != want[p]:
                    fail.append("%s: %s is %r, expected %r" % (name, p, v, want[p]))
            if missing:
                fail.append("%s: expected changes did not happen at %s" % (name, ", ".join(missing[:4])))
    return fail


def _at(t, path):
    cur = t
    for part in [p for p in path.split("/") if p]:
        if "[" in part:
            k, i = part[:-1].split("[")
            cur = cur[k][int(i)]
        else:
            cur = cur[part]
    return cur


def _same(t, path, value):
    return _at(t, path) == value


def _apply_bundle_catalog_op(t, op, objs):
    """Apply B2 (add-tile-size) or B3 (set-add-tile / set-remove-tile) onto a TileDescription or GridElementSet."""
    kind = op.get("op")
    if kind == "add-tile-size":
        cfgs = t.get("<Configurations>k__BackingField")
        if not isinstance(cfgs, list):
            raise ValueError("%s is not a TileDescription with <Configurations>k__BackingField" % op["path_id"])
        sz, guid = op["size"], op["reuse_guid"]
        if any((c.get("Size") or {}).get("x") == sz["x"] and (c.get("Size") or {}).get("y") == sz["y"] for c in cfgs):
            return
        src_cfg = next((c for c in cfgs if ((c.get("AssetRef") or c.get("Asset") or {}).get("m_AssetGUID")) == guid), None)
        if src_cfg is None:
            raise ValueError("%s: UXML GUID %s does not exist on this description (reusing an existing GUID is required)" % (t.get("m_Name"), guid))
        new_cfg = copy.deepcopy(src_cfg)
        new_cfg["Size"] = {"x": int(sz["x"]), "y": int(sz["y"])}
        cfgs.append(new_cfg)
    elif kind == "set-add-tile":
        descs = t.get("m_gridElementDescriptions")
        if not isinstance(descs, list):
            raise ValueError("%s is not a GridElementSet with m_gridElementDescriptions" % op["path_id"])
        target_pid = int(op["description_path_id"])
        if target_pid not in objs:
            raise ValueError("description %s does not exist in bundle" % target_pid)
        if not any(int(p.get("m_PathID", 0)) == target_pid for p in descs):
            descs.append({"m_FileID": 0, "m_PathID": target_pid})
    elif kind == "set-remove-tile":
        descs = t.get("m_gridElementDescriptions")
        if not isinstance(descs, list):
            raise ValueError("%s is not a GridElementSet with m_gridElementDescriptions" % op["path_id"])
        target_pid = int(op["description_path_id"])
        t["m_gridElementDescriptions"] = [p for p in descs if int(p.get("m_PathID", 0)) != target_pid]
    else:
        raise ValueError("unknown catalog op %r" % kind)


def list_tile_descriptions(bundle_path):
    """B2: list all TileDescriptions with their sizes and the UXML GUID each configuration uses."""
    import UnityPy
    env = UnityPy.load(str(bundle_path))
    out = []
    for o in env.objects:
        if o.type.name != "MonoBehaviour":
            continue
        try:
            t = o.read_typetree()
        except Exception:
            continue
        if not isinstance(t, dict) or not isinstance(t.get("<Configurations>k__BackingField"), list):
            continue
        cfgs = []
        for idx, c in enumerate(t["<Configurations>k__BackingField"]):
            sz = c.get("Size") or {}
            guid = ((c.get("AssetRef") or c.get("Asset") or {}).get("m_AssetGUID")) or ""
            cfgs.append({"index": idx, "width": int(sz.get("x", 0)), "height": int(sz.get("y", 0)), "guid": guid})
        out.append({
            "path_id": str(o.path_id),
            "name": t.get("m_Name") or "",
            "id": t.get("<ID>k__BackingField") or t.get("m_Name") or "",
            "configurations": cfgs,
        })
    out.sort(key=lambda r: (r["id"], r["name"], r["path_id"]))
    return out


def list_element_sets(bundle_path):
    """B3: list all GridElementSets and the TileDescriptions they allow."""
    import UnityPy
    env = UnityPy.load(str(bundle_path))
    objs = {o.path_id: o for o in env.objects}
    out = []
    for o in env.objects:
        if o.type.name != "MonoBehaviour":
            continue
        try:
            t = o.read_typetree()
        except Exception:
            continue
        if not isinstance(t, dict) or not isinstance(t.get("m_gridElementDescriptions"), list):
            continue
        descs = []
        for p in t["m_gridElementDescriptions"]:
            pid = int(p.get("m_PathID", 0))
            d = objs.get(pid)
            dt = d.read_typetree() if d is not None else {}
            descs.append({
                "path_id": str(pid),
                "name": dt.get("m_Name") or "",
                "id": dt.get("<ID>k__BackingField") or dt.get("m_Name") or "",
            })
        out.append({
            "path_id": str(o.path_id),
            "name": t.get("m_Name") or "",
            "descriptions": descs,
        })
    out.sort(key=lambda r: (r["name"], r["path_id"]))
    return out
