"""Stored placement edits (Milestone D). STORED ONLY: nothing here writes the layout dump, a bundle, or the game folder, and no
build or install step reads these edits to change a file. They are a versioned list in the workspace, one file per project
(workspace/placements/<project>.placements.json), each edit recording the dump fingerprint it was validated against.

Hard blocks refuse an edit outright: target missing, locked cell (a move is refused), values that are not integers, out of the
composition's grid bounds, outside the cell's min/max limits, a config the cell does not have, no change. A collision with another
cell inside bounds is a warning that needs an explicit confirm (overlap may be intentional layering). When the dump changes, the
list is revalidated: an edit whose target vanished or moved, or that now blocks or collides, is marked stale and reported, never
silently applied. Edits can only be added while the dump is fresh (docs/fmlayout-index-1.md, staleness)."""
import json
import os
import time
from pathlib import Path

from . import layout_dump

SCHEMA = 1
STATUS = "stored; positions are written by a bundle build"
NOTE = ("Placement edits are stored in the workspace. A bundle build writes the x/y position of every edit that is not stale into a copy of the "
        "composition bundle (tiles.py); sizes and config changes are not written. Nothing changes the game until that build is installed.")
GEO = ("x", "y", "w", "h")


class PlacementError(Exception):
    """An edit that cannot be stored. blocks: hard refusals. requires_confirm: collisions awaiting an explicit confirm."""

    def __init__(self, message, blocks=None, warnings=None, collisions=None):
        super().__init__(message)
        self.blocks, self.warnings, self.collisions = blocks or [], warnings or [], collisions or []
        self.requires_confirm = bool(self.collisions) and not self.blocks


def _int(v):
    return isinstance(v, int) and not isinstance(v, bool)


class Grid:
    """Indexes of the dump sections the validation needs (built from the raw dump dict)."""

    def __init__(self, dump):
        self.fp = dump["meta"]["index_fingerprint"]
        self.build = dump["meta"]["game_build"]
        self.comps = {c["name"]: c for c in dump["compositions"]}
        self.cells, self.cfgs, self.used, self.cfg_size = {}, {}, {}, {}
        for c in dump["cells"]:
            self.cells[(c["composition"], c["cell_index"])] = c
        for c in dump["cell_configs"]:
            self.cfgs.setdefault((c["composition"], c["cell_index"]), []).append(c["cfg_index"])
            self.cfg_size[(c["composition"], c["cell_index"], c["cfg_index"])] = (c["size_w"], c["size_h"])
        for t in dump["tiles"]:
            self.used.setdefault((t["composition"], t["cell_index"]), set()).add(t["cfg_index"])

    def geometry(self, comp, idx):
        c = self.cells[(comp, idx)]
        return {k: c[k] for k in GEO}

    def siblings(self, comp):
        return [c for (cn, _), c in self.cells.items() if cn == comp]


def eid(comp, idx):
    return "%s#%d" % (comp, idx)


def _overlap(a, b):
    return a["x"] < b["x"] + b["w"] and b["x"] < a["x"] + a["w"] and a["y"] < b["y"] + b["h"] and b["y"] < a["y"] + a["h"]


def check(grid, edit, others=()):
    """Validate one edit against the dump. `others`: the other stored edits of the same list that count (not stale), whose new geometry
    stands in for the dump's when looking for collisions. Returns {blocks, warnings, collisions, old, new}; never raises for content."""
    blocks, warns, coll = [], [], []
    comp, idx = edit.get("composition"), edit.get("cell_index")
    if not isinstance(comp, str) or not _int(idx) or (comp, idx) not in grid.cells:
        return {"blocks": ["target missing: composition %r cell %r is not in the dump" % (comp, idx)], "warnings": [], "collisions": [], "old": None, "new": None}
    cell, comp_rec = grid.cells[(comp, idx)], grid.comps[comp]
    geo, cfg = edit.get("geometry"), edit.get("config")
    if geo is None and cfg is None:
        blocks.append("the edit changes nothing: give a geometry and/or a config")
    old = {"geometry": grid.geometry(comp, idx), "config": None, "configs": sorted(grid.cfgs.get((comp, idx), []))}
    used = sorted(grid.used.get((comp, idx), ()))
    old["config"] = used[0] if len(used) == 1 else None
    new = {"geometry": None, "config": None}
    if geo is not None:
        if not isinstance(geo, dict) or set(geo) != set(GEO) or not all(_int(geo[k]) for k in GEO):
            blocks.append("geometry needs integer x, y, w, h (grid units)")
        else:
            new["geometry"] = {k: geo[k] for k in GEO}
            if geo["x"] < 0 or geo["y"] < 0 or geo["w"] <= 0 or geo["h"] <= 0:
                blocks.append("out of bounds: x and y must be >= 0 and w and h > 0")
            if "locked" in cell["flags"]:
                blocks.append("locked: this cell has the 'locked' flag, a move or resize is refused")
            if cell["x"] < 0 or cell["y"] < 0:
                blocks.append("auto-placed: the game places this cell itself (x/y = -1 in its data), it has no position to move")
            pw, ph = comp_rec["preset_w"], comp_rec["preset_h"]
            if pw > 0 and ph > 0:
                if geo["x"] + geo["w"] > pw or geo["y"] + geo["h"] > ph:
                    blocks.append("out of bounds: x+w=%d, y+h=%d exceed the composition grid %d x %d" % (geo["x"] + geo["w"], geo["y"] + geo["h"], pw, ph))
            else:
                warns.append("the composition has no preset size in the dump: grid bounds were not checked")
            og = old["geometry"]
            if og and (geo["w"] != og["w"] or geo["h"] != og["h"]):
                blocks.append("size change not supported: cell size is largely derived from its configs (4,724 of 5,162 config cells in the game data); only a position change (x, y) is allowed")
            for axis, v, lo, hi in (("w", geo["w"], cell["min_w"], cell["max_w"]), ("h", geo["h"], cell["min_h"], cell["max_h"])):
                if v < lo:
                    blocks.append("grid limits: %s=%d is below the cell's minimum %d" % (axis, v, lo))
                if hi > 0 and v > hi:
                    blocks.append("grid limits: %s=%d is above the cell's maximum %d" % (axis, v, hi))
            if new["geometry"] == old["geometry"] and cfg is None:
                blocks.append("no change: the geometry equals the dump's")
            if not blocks:
                mine = (comp, idx)
                stand_in = {(o["composition"], o["cell_index"]): o["geometry"] for o in others if o.get("geometry") and o.get("state") != "stale" and (o["composition"], o["cell_index"]) != mine}
                for sib in grid.siblings(comp):
                    if sib["cell_index"] == idx:
                        continue
                    g = stand_in.get((comp, sib["cell_index"])) or {k: sib[k] for k in GEO}
                    if _overlap(new["geometry"], g):
                        coll.append({"cell_index": sib["cell_index"], "element_id": sib["element_id"], "geometry": g})
                if coll:
                    warns.append("overlaps %s: confirm to store (overlap may be intentional layering)" % ", ".join("cell %d (%s)" % (c["cell_index"], c["element_id"]) for c in coll))
    if cfg is not None:
        if not _int(cfg) or cfg not in grid.cfgs.get((comp, idx), []):
            blocks.append("config %r is not one of this cell's configs %s" % (cfg, old["configs"]))
        else:
            new["config"] = cfg
            cur, want = cell, grid.cfg_size.get((comp, idx, cfg))
            if want is not None and (cur["w"], cur["h"]) != want:
                blocks.append("config change not supported yet: config %d is %d x %d but the cell is %d x %d; choosing it would store a cell whose size no longer matches its config (blocked until a config trial has run in game)" % (cfg, want[0], want[1], cur["w"], cur["h"]))
            if cfg == old["config"] and geo is None:
                blocks.append("no change: config %d is already the one used in the dump" % cfg)
    return {"blocks": blocks, "warnings": warns, "collisions": coll, "old": old, "new": new}


# ---------------------------------------------------------------- storage
def _path(ws, project):
    return Path(ws.placements) / ("%s.placements.json" % project)


def _blank(project):
    return {"schema": SCHEMA, "project": project, "edits": []}


def _read(ws, project):
    p = _path(ws, project)
    if not p.is_file():
        return _blank(project)
    d = json.loads(p.read_text(encoding="utf-8-sig"))
    if d.get("schema") != SCHEMA or d.get("project") != project or not isinstance(d.get("edits"), list):
        raise ValueError("placement list for %r has an unsupported schema; it was not loaded" % project)
    return d


def _write(ws, doc):
    p = _path(ws, doc["project"])
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_name(p.name + ".tmp")
    tmp.write_text(json.dumps(doc, indent=1), encoding="utf-8")
    os.replace(tmp, p)
    from . import changes
    changes.record(doc["project"], "tile-move")


def _grid(ws):
    d = layout_dump.load(ws)
    return Grid(d) if d else None


def revalidate(grid, doc):
    """Recheck every edit against the current dump. Marks edits stale (with reasons); returns True when the list changed."""
    changed = False
    for e in doc["edits"]:
        if e.get("state") == "stale":
            continue
        reasons = []
        key = (e["composition"], e["cell_index"])
        if grid is None:
            reasons.append("no layout dump is imported")
        elif key not in grid.cells or grid.cells[key]["element_id"] != e["cell_element_id"]:
            reasons.append("target vanished or changed: %s is not in the current dump" % eid(*key))
        else:
            now = grid.geometry(*key)
            if e["old"]["geometry"] != now:
                reasons.append("target moved: the dump's geometry is now %s, the edit was made against %s" % (now, e["old"]["geometry"]))
            others = [o for o in doc["edits"] if o is not e]
            r = check(grid, {"composition": e["composition"], "cell_index": e["cell_index"], "geometry": e.get("geometry"), "config": e.get("config")}, others)
            for b in r["blocks"]:
                if not b.startswith("no change"):
                    reasons.append("now invalid: " + b)
            known = set(e.get("confirmed_collisions", []))
            fresh = [c for c in r["collisions"] if eid(e["composition"], c["cell_index"]) not in known]
            if fresh:
                reasons.append("now collides with " + ", ".join("cell %d (%s)" % (c["cell_index"], c["element_id"]) for c in fresh))
        if reasons:
            e["state"], e["reasons"] = "stale", reasons
            changed = True
        elif grid is not None and e.get("validated_against", {}).get("fingerprint") != grid.fp:
            e["validated_against"] = {"fingerprint": grid.fp, "game_build": grid.build}      # rechecked against the new dump and still holds
            changed = True
    return changed


def load(ws, project):
    """The project's edit list, revalidated against the current dump (stale edits are marked and saved)."""
    doc = _read(ws, project)
    if doc["edits"] and revalidate(_grid(ws), doc):
        _write(ws, doc)
    return doc


def can_edit(ws):
    st = layout_dump.state(ws)
    if not st.get("present"):
        return {"ok": False, "why": "No layout dump is imported."}
    s = st["staleness"]
    return {"ok": s["status"] == "fresh", "why": "" if s["status"] == "fresh" else s["message"]}


def add(ws, project, edit, confirm=False):
    """Validate and store one edit (replacing an earlier edit of the same cell). Refused while the dump is not fresh."""
    ce = can_edit(ws)
    if not ce["ok"]:
        raise PlacementError("placement edits are only accepted while the layout dump is fresh. " + ce["why"], blocks=[ce["why"] or "stale dump"])
    grid = _grid(ws)
    doc = load(ws, project)
    key = (edit.get("composition"), edit.get("cell_index"))
    others = [o for o in doc["edits"] if (o["composition"], o["cell_index"]) != key]
    r = check(grid, edit, others)
    if r["blocks"]:
        raise PlacementError("edit refused: " + "; ".join(r["blocks"]), r["blocks"], r["warnings"])
    if r["collisions"] and not confirm:
        raise PlacementError("edit collides with other cells; confirm to store it", [], r["warnings"], r["collisions"])
    cell = grid.cells[key]
    rec = {"id": eid(*key), "composition": key[0], "cell_index": key[1], "cell_element_id": cell["element_id"],
           "geometry": r["new"]["geometry"], "config": r["new"]["config"], "old": r["old"], "note": str(edit.get("note", ""))[:200],
           "confirmed_collisions": [eid(key[0], c["cell_index"]) for c in r["collisions"]], "warnings": r["warnings"],
           "state": "valid", "reasons": [], "validated_against": {"fingerprint": grid.fp, "game_build": grid.build},
           "created_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    doc["edits"] = [o for o in doc["edits"] if o["id"] != rec["id"]] + [rec]
    _write(ws, doc)
    return rec


def remove(ws, project, edit_id):
    """Revert: drop the edit. The dump's own values are untouched, and kept in `old` while the edit existed."""
    doc = _read(ws, project)
    n = len(doc["edits"])
    doc["edits"] = [e for e in doc["edits"] if e["id"] != edit_id]
    if len(doc["edits"]) == n:
        raise KeyError("no such placement edit: " + edit_id)
    _write(ws, doc)
    return doc


def summary(ws, project):
    doc = load(ws, project)
    ce = can_edit(ws)
    return {"project": project, "edits": doc["edits"], "can_edit": ce["ok"], "why_not": ce["why"], "status": STATUS, "note": NOTE}


def report(ws, project):
    """The build report's layout placement section."""
    doc = load(ws, project)
    st = layout_dump.state(ws)
    rows = []
    for e in doc["edits"]:
        rows.append({"target": "%s / cell %d (%s)" % (e["composition"], e["cell_index"], e["cell_element_id"]), "composition": e["composition"],
                     "cell_index": e["cell_index"], "cell_element_id": e["cell_element_id"],
                     "changes": [k for k in ("geometry", "config") if e.get(k) is not None],
                     "old": {"geometry": e["old"]["geometry"], "config": e["old"]["config"]},
                     "new": {"geometry": e.get("geometry"), "config": e.get("config")},
                     "state": e["state"], "reasons": e.get("reasons", []), "warnings": e.get("warnings", []),
                     "confirmed_collisions": e.get("confirmed_collisions", []), "validated_against": e.get("validated_against")})
    return {"status": STATUS, "note": NOTE,
            "dump": None if not st.get("present") else {"fingerprint": st["fingerprint"], "game_build": st["game_build"], "staleness": st["staleness"]["status"]},
            "counts": {"edits": len(rows), "valid": sum(1 for r in rows if r["state"] == "valid"), "stale": sum(1 for r in rows if r["state"] == "stale")},
            "edits": rows}
