"""Tile layout writes: cell POSITIONS (x, y) of grid compositions, written into a copy of the composition bundles. Sizes are not written: a
cell's size is derived from its configs (4,724 of the 5,162 cells that have configs have the size of one of them, measured on the real index).

An op is {op: "move-cell", bundle, path_id, composition, cell_index, cell_id, from: {x, y}, to: {x, y}}. `cell_id` and `from` are guards: the
composition must still hold that cell (by index and m_elementID) at the position the edit was made against, else the build refuses, so an
edit never lands on something a game update moved. Only m_location.x and m_location.y of the addressed cells are touched. Everything else in
the composition, and every other object of the bundle, stays as it was; `check` proves that on the built file."""
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
        if o.get("op") != "move-cell" or o["bundle"] not in TILE_BUNDLES:
            raise ValueError("a tile op is a move-cell in one of: " + ", ".join(TILE_BUNDLES))
        for k in ("from", "to"):
            if set(o[k]) != {"x", "y"} or not all(isinstance(v, int) and not isinstance(v, bool) for v in o[k].values()):
                raise ValueError("%s needs integer x and y" % k)
        if o["to"]["x"] < 0 or o["to"]["y"] < 0:
            raise ValueError("a cell cannot be moved to a negative position")
        key = (o["bundle"], o["path_id"], o["cell_index"])
        if key in seen:
            raise ValueError("cell %s of %s is moved twice" % (o["cell_index"], o["composition"]))
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


def apply_ops(src, out_dir, ops, touched=None):
    """Patch one composition bundle; writes out_dir/<name> when anything changed. Returns (changed, notes, path ids saved)."""
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
        if not isinstance(t, dict) or "m_gridComponents" not in t or t.get("m_Name") != group[0]["composition"]:
            raise ValueError("%s: composition %s (path id %s) not found (game updated? re-export the layout dump)" % (Path(src).name, group[0]["composition"], pid))
        for op in group:
            c = _cell(t, op, "%s" % op["composition"])
            c["m_location"]["x"], c["m_location"]["y"] = op["to"]["x"], op["to"]["y"]
        obj.save_typetree(t)
        done.append(pid)
    if touched is not None:
        touched.update(done)
    if done:
        (Path(out_dir) / Path(src).name).write_bytes(env.file.save(packer="original"))
    return bool(done), ["%d cell position(s) in %d composition(s)" % (len(ops), len(done))] if done else [], done


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
        name = group[0]["composition"]
        try:
            vt, bt = vo[pid].read_typetree(), bo[pid].read_typetree()
        except Exception as ex:
            fail.append("%s cannot be read (%s)" % (name, ex))
            continue
        want = {}
        for op in group:
            base = "/m_gridComponents[%d]/m_location/" % op["cell_index"]
            want[base + "x"], want[base + "y"] = op["to"]["x"], op["to"]["y"]
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
