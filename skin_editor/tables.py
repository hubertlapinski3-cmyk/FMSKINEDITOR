"""Table views: read the game's column sets (ui-tableviews) and row cell definitions (ui-tablefactories), and patch column width, visibility and
order into a copy of ui-tableviews.

Data model (decoded from the real bundles, 27.0.1.2503222):
- a table view is a MonoBehaviour with `m_tableView.m_tableConfig`, an ordered list of columns: {m_columnID, m_columnMetadata: {m_widthOverride,
  m_minWidthOverride, m_required, m_sortingDisabled, m_priority, m_applicableBreakpoints, conditions, m_titleTranslationIdOverride}}. Order is the list
  order, visibility is presence in the list, width is the override (0 = the column's default).
- a table factory has `m_rowData`, one entry per column id the factory can draw: m_id, default and minimum width, a header translation id, the value
  bindings and `m_uxmlRef` (the GUID of the layout that draws a cell). A view's factory is the one that defines its column ids (found by coverage).
Patches are small per-view files addressed by column id, never a full copy of the view, so they survive unrelated game updates."""
import copy
import json
import re
from pathlib import Path

from . import bundles

VIEWS_BUNDLE = "ui-tableviews_assets_all.bundle"
FACTORIES_BUNDLE = "ui-tablefactories_assets_all.bundle"
TABLE_OPS = ("set-width", "hide-column", "show-column", "move-column")
COL_RE = re.compile(r"[A-Za-z0-9][\w.-]{0,100}")


def _mb(path):
    import UnityPy
    for o in UnityPy.load(str(path)).objects:
        if o.type.name != "MonoBehaviour":
            continue
        try:
            t = o.read_typetree()
        except Exception:
            continue
        if isinstance(t, dict):
            yield o, t


class Tables:
    """Read-only access to the table views and factories of a folder (the game's aa folder or the vanilla snapshot)."""

    def __init__(self, folder, guid_names=None):
        self.folder = Path(folder)
        self.guid_names = guid_names or {}               # layout guid -> name (from the layout dump), optional
        self._views = self._factories = None

    def load(self):
        if self._views is None:
            self._views, self._factories = {}, {}
            for o, t in _mb(self.folder / VIEWS_BUNDLE):
                if "m_tableView" in t:
                    self._views[o.path_id] = {"bundle": VIEWS_BUNDLE, "name": t.get("m_Name", ""), "path_id": str(o.path_id), "tree": t}
            for o, t in _mb(self.folder / FACTORIES_BUNDLE):
                if "m_rowData" in t:
                    self._factories[o.path_id] = {"bundle": FACTORIES_BUNDLE, "name": t.get("m_Name", ""), "path_id": str(o.path_id), "tree": t}
        return self

    def list(self, q=""):
        self.load()
        s = q.strip().lower()
        return [{k: v[k] for k in ("bundle", "name", "path_id")} | {"columns": len(v["tree"]["m_tableView"]["m_tableConfig"])}
                for v in sorted(self._views.values(), key=lambda v: v["name"].lower()) if not s or s in v["name"].lower()]

    def factory_for(self, ids):
        """The factory that defines most of these column ids: (factory entry or None, coverage 0..1)."""
        self.load()
        ids = set(ids)
        best, cov = None, 0.0
        for f in self._factories.values():
            have = {r["m_id"] for r in f["tree"]["m_rowData"]}
            c = len(ids & have) / len(ids) if ids else 0.0
            if c > cov or (c == cov and best is not None and len(have) < len({r["m_id"] for r in best["tree"]["m_rowData"]})):
                best, cov = f, c
        return best, cov

    def view(self, path_id):
        self.load()
        v = self._views.get(int(path_id))
        if v is None:
            raise KeyError("no table view with path id %s" % path_id)
        cols = v["tree"]["m_tableView"]["m_tableConfig"]
        fac, cov = self.factory_for([c["m_columnID"] for c in cols])
        cells = {r["m_id"]: r for r in fac["tree"]["m_rowData"]} if fac else {}
        out = []
        for i, c in enumerate(cols):
            m, cell = c["m_columnMetadata"], cells.get(c["m_columnID"])
            out.append({"index": i, "id": c["m_columnID"], "width": m["m_widthOverride"], "min_width": m["m_minWidthOverride"], "required": bool(m["m_required"]),
                        "sorting_disabled": bool(m["m_sortingDisabled"]), "priority": m["m_priority"], "breakpoints": m["m_applicableBreakpoints"],
                        "conditions": len(m.get("m_optionalConditions") or []) + len(m.get("m_optionalConfigConditions") or []),
                        "cell": None if cell is None else self._cell(cell)})
        available = [self._cell(r) | {"id": r["m_id"]} for r in (fac["tree"]["m_rowData"] if fac else []) if r["m_id"] not in {c["m_columnID"] for c in cols}]
        return {"bundle": v["bundle"], "name": v["name"], "path_id": v["path_id"], "columns": out, "available": available,
                "factory": None if fac is None else {"name": fac["name"], "path_id": fac["path_id"], "coverage": round(cov, 3), "cells": len(cells)}}

    def _cell(self, r):
        g = (r.get("m_uxmlRef") or {}).get("m_AssetGUID", "")
        return {"default_width": r["m_defaultWidth"], "minimum_width": r["m_minimumWidth"], "auto_resize": bool(r["m_allowWidthAutoResizing"]),
                "header_text_id": (r.get("m_translationID") or {}).get("GameID"), "cell_layout_guid": g, "cell_layout": self.guid_names.get(g, "") if g else "",
                "sortable": bool((r.get("m_sortBinding") or {}).get("m_path"))}


# ---------------------------------------------------------------- patches
def validate_doc(doc):
    """{schema, view: {bundle, name, path_id?}, ops: [...]}: set-width {column, width, guard_width?}, hide-column {column}, show-column {column, after?}, move-column {column, after?}.
    Columns are addressed by id; `after` is the id of the column the target should follow (absent = first)."""
    if not isinstance(doc, dict) or set(doc) - {"schema", "view", "ops"}:
        raise ValueError("a table patch has schema, view and ops")
    v = doc.get("view")
    if not isinstance(v, dict) or v.get("bundle") != VIEWS_BUNDLE or not v.get("name") or set(v) - {"bundle", "name", "path_id"}:
        raise ValueError("view needs bundle %s and name (and path_id)" % VIEWS_BUNDLE)
    if "path_id" in v and not re.fullmatch(r"-?\d{1,20}", str(v["path_id"])):
        raise ValueError("view path_id must be a decimal string")
    if not isinstance(doc.get("ops"), list) or not doc["ops"]:
        raise ValueError("ops must be a non-empty list")
    for op in doc["ops"]:
        if not isinstance(op, dict) or op.get("op") not in TABLE_OPS:
            raise ValueError("op must be one of: " + ", ".join(TABLE_OPS))
        if not isinstance(op.get("column"), str) or not COL_RE.fullmatch(op["column"]):
            raise ValueError("an op names a column by its id")
        extra = set(op) - {"op", "column"}
        if op["op"] == "set-width":
            if extra - {"width"} or not isinstance(op.get("width"), (int, float)) or isinstance(op.get("width"), bool) or not 0 <= op["width"] <= 2000:
                raise ValueError("set-width needs width between 0 and 2000 (0 = the column's default)")
        elif op["op"] == "hide-column":
            if extra:
                raise ValueError("hide-column has only a column")
        else:
            if extra - {"after"} or ("after" in op and not (isinstance(op["after"], str) and COL_RE.fullmatch(op["after"]))):
                raise ValueError("%s takes an optional 'after' column id" % op["op"])
    return doc


def merge_op(doc, op):
    """Fold one op into a view's patch file. set-width and move-column replace an earlier op of that column; hide and show cancel each other
    (showing a column this patch hid, or hiding one it showed, removes the earlier op). Returns the doc."""
    ops, cid, kind = doc["ops"], op["column"], op["op"]
    same = [o for o in ops if o["column"] == cid and o["op"] == kind]
    if kind in ("set-width", "move-column"):
        for o in same:
            ops.remove(o)
        ops.append(op)
    elif kind == "hide-column":
        shown = [o for o in ops if o["column"] == cid and o["op"] == "show-column"]
        if shown:
            ops.remove(shown[0])
            ops[:] = [o for o in ops if not (o["column"] == cid and o["op"] in ("set-width", "move-column"))]
        elif not same:
            ops.append(op)
    else:
        hidden = [o for o in ops if o["column"] == cid and o["op"] == "hide-column"]
        if hidden:
            ops.remove(hidden[0])
        elif not same:
            ops.append(op)
    return doc


def apply_to_view(tree, ops, where="", factory_ids=None):
    """Apply ops in order to one decoded table view's m_tableConfig. Returns the list of result column ids. Raises ValueError on a stale op."""
    cols = tree["m_tableView"]["m_tableConfig"]
    ids = lambda: [c["m_columnID"] for c in cols]
    for op in ops:
        cid = op["column"]
        if op["op"] == "show-column":
            if cid in ids():
                raise ValueError("%s column %s is already shown" % (where, cid))
            if factory_ids is not None and cid not in factory_ids:
                raise ValueError("%s column %s is not one this table's factory can draw" % (where, cid))
            if not cols:
                raise ValueError("%s has no column to model a new one on" % where)
            new = copy.deepcopy(cols[0])
            new["m_columnID"] = cid
            m = new["m_columnMetadata"]
            m.update({"m_required": 0, "m_sortingDisabled": 0, "m_widthOverride": 0.0, "m_minWidthOverride": 0.0, "m_applicableBreakpoints": -1, "m_priority": 0})
            m["m_optionalConditions"], m["m_optionalConfigConditions"] = [], []
            cols.insert(_after(cols, op.get("after"), where), new)
            continue
        i = ids().index(cid) if cid in ids() else -1
        if i < 0:
            raise ValueError("%s has no column %s (game updated? re-do this edit)" % (where, cid))
        if op["op"] == "set-width":
            m = cols[i]["m_columnMetadata"]
            m["m_widthOverride"] = float(op["width"])
            if m["m_minWidthOverride"] > m["m_widthOverride"]:
                m["m_minWidthOverride"] = float(op["width"])
        elif op["op"] == "hide-column":
            if cols[i]["m_columnMetadata"]["m_required"]:
                raise ValueError("%s column %s is required and cannot be hidden" % (where, cid))
            del cols[i]
        else:
            col = cols.pop(i)
            cols.insert(_after(cols, op.get("after"), where), col)
    return ids()


def _after(cols, after, where):
    if after is None:
        return 0
    for j, c in enumerate(cols):
        if c["m_columnID"] == after:
            return j + 1
    raise ValueError("%s: the column to place after, %s, is not in the table" % (where, after))


def expected_columns(vanilla_tree, ops, factory_ids=None):
    """What the vanilla view plus the ops must give: the list of (column id, metadata dict). Independent of apply_to_view's bookkeeping:
    it works on plain (id, metadata) pairs."""
    cols = [(c["m_columnID"], copy.deepcopy(c["m_columnMetadata"])) for c in vanilla_tree["m_tableView"]["m_tableConfig"]]
    for op in ops:
        cid = op["column"]
        pos = next((i for i, (k, _m) in enumerate(cols) if k == cid), -1)
        place = lambda lst: 0 if op.get("after") is None else next(j + 1 for j, (k, _m) in enumerate(lst) if k == op["after"])
        if op["op"] == "show-column":
            base = copy.deepcopy(cols[0][1])
            base.update({"m_required": 0, "m_sortingDisabled": 0, "m_widthOverride": 0.0, "m_minWidthOverride": 0.0, "m_applicableBreakpoints": -1, "m_priority": 0,
                         "m_optionalConditions": [], "m_optionalConfigConditions": []})
            cols.insert(place(cols), (cid, base))
        elif op["op"] == "set-width":
            m = cols[pos][1]
            m["m_widthOverride"] = float(op["width"])
            if m["m_minWidthOverride"] > m["m_widthOverride"]:
                m["m_minWidthOverride"] = float(op["width"])
        elif op["op"] == "hide-column":
            del cols[pos]
        else:
            item = cols.pop(pos)
            cols.insert(place(cols), item)
    return cols


def apply_patches(src, out_dir, docs, touched=None):
    """Patch the table views of ui-tableviews named by docs; writes out_dir/<name> when anything changed. Returns (changed, notes, path ids)."""
    import UnityPy
    env = UnityPy.load(str(src))
    objs = {o.path_id: o for o in env.objects}
    tb = Tables(Path(src).parent).load() if (Path(src).parent / FACTORIES_BUNDLE).is_file() else None
    done = []
    for doc in docs:
        v = doc["view"]
        o = objs.get(int(v["path_id"])) if v.get("path_id") else None
        t = o.read_typetree() if o is not None and o.type.name == "MonoBehaviour" else None
        if not isinstance(t, dict) or "m_tableView" not in t or t.get("m_Name") != v["name"]:
            cands = [x for x in env.objects if x.type.name == "MonoBehaviour" and x.peek_name() == v["name"] and "m_tableView" in x.read_typetree()]
            if len(cands) != 1:
                raise ValueError("table view %s not found (game updated? pick it again in the Tables view)" % v["name"])
            o = cands[0]
            t = o.read_typetree()
        fac_ids = None
        if tb is not None:
            fac, _ = tb.factory_for([c["m_columnID"] for c in t["m_tableView"]["m_tableConfig"]])
            fac_ids = {r["m_id"] for r in fac["tree"]["m_rowData"]} if fac else None
        apply_to_view(t, doc["ops"], v["name"] + ":", fac_ids)
        o.save_typetree(t)
        done.append(o.path_id)
    if touched is not None:
        touched.update(done)
    if done:
        (Path(out_dir) / Path(src).name).write_bytes(env.file.save(packer="original"))
    return bool(done), ["%d table view(s) patched" % len(done)] if done else [], done


def check_patches(vanilla_path, built_path, docs):
    """Gate: each patched view equals the vanilla view with exactly the asked-for column changes (ids, order, metadata), and no other field
    of the view differs. Returns a list of failures."""
    import UnityPy
    fail = []
    vo = {o.path_id: o for o in UnityPy.load(str(vanilla_path)).objects}
    bo = {o.path_id: o for o in UnityPy.load(str(built_path)).objects}
    for doc in docs:
        v = doc["view"]
        pid = int(v["path_id"]) if v.get("path_id") and int(v["path_id"]) in vo and vo[int(v["path_id"])].peek_name() == v["name"] else \
            next((p for p, o in vo.items() if o.type.name == "MonoBehaviour" and o.peek_name() == v["name"] and "m_tableView" in o.read_typetree()), None)
        if pid is None:
            fail.append("%s: not found" % v["name"])
            continue
        try:
            vt, bt = vo[pid].read_typetree(), bo[pid].read_typetree()
            want = expected_columns(vt, doc["ops"])
        except Exception as ex:
            fail.append("%s: cannot be checked (%s)" % (v["name"], ex))
            continue
        got = [(c["m_columnID"], c["m_columnMetadata"]) for c in bt["m_tableView"]["m_tableConfig"]]
        if [k for k, _ in got] != [k for k, _ in want]:
            fail.append("%s: columns are %s, expected %s" % (v["name"], [k for k, _ in got][:8], [k for k, _ in want][:8]))
        else:
            for (k, g), (_k, w) in zip(got, want):
                if g != w:
                    fail.append("%s: column %s metadata differs from the expected" % (v["name"], k))
        for key in vt:                                          # everything but the column list is untouched
            if key == "m_tableView":
                a = {k: x for k, x in vt[key].items() if k != "m_tableConfig"}
                b = {k: x for k, x in bt[key].items() if k != "m_tableConfig"}
                if bundles.first_difference(a, b) is not None:
                    fail.append("%s: a field of m_tableView other than m_tableConfig changed" % v["name"])
            elif bundles.first_difference(vt[key], bt.get(key)) is not None:
                fail.append("%s: field %s changed" % (v["name"], key))
    return fail
