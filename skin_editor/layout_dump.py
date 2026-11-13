"""Layout dump (schema fmlayout-index/2): validation, import, storage, staleness. Contract: docs/fmlayout-index-2.md.

The dump is read-only input. Nothing here ever writes it. A dump that fails validation is refused as a whole:
the stored current/previous files are not touched."""
import json
import os
import re
from pathlib import Path

SCHEMA = "fmlayout-index/2"
MAX_BYTES = 256 * 1024 * 1024
MAX_ERRORS = 50
MAX_COORD = 100000
SECTIONS = ("layouts", "elements", "includes", "panels", "tiles", "compositions", "cells", "cell_configs")
TOP = ("meta", "areas") + SECTIONS
HEX32 = re.compile(r"[0-9a-f]{32}")
HEX64 = re.compile(r"[0-9a-f]{64}")


class LayoutError(Exception):
    """Refusal to load a dump. `errors` is the (capped) list of violations, `total` the real count."""

    def __init__(self, message, errors=None, total=None):
        super().__init__(message)
        self.errors = errors or []
        self.total = total if total is not None else len(self.errors)


class _Errs:
    def __init__(self):
        self.list, self.total = [], 0

    def add(self, where, msg):
        self.total += 1
        if len(self.list) < MAX_ERRORS:
            self.list.append("%s: %s" % (where, msg))


def _int(v):
    return isinstance(v, int) and not isinstance(v, bool)


def _str(v, nonempty=False):
    return isinstance(v, str) and (bool(v) or not nonempty)


def _strs(v):
    return isinstance(v, list) and all(isinstance(x, str) for x in v)


def _check_record(e, where, rec, spec, optional=()):
    """spec: {key: predicate}. Unknown keys, missing keys and bad types are collected."""
    if not isinstance(rec, dict):
        e.add(where, "must be an object")
        return False
    ok = True
    for k in rec:
        if k not in spec and k not in optional:
            e.add(where, "unknown key %r" % k)
            ok = False
    for k, pred in spec.items():
        if k not in rec:
            e.add(where, "missing key %r" % k)
            ok = False
        elif not pred(rec[k]):
            e.add(where, "bad value for %r: %r" % (k, rec[k] if len(repr(rec[k])) < 60 else type(rec[k]).__name__))
            ok = False
    return ok


def _pos_int(v):
    return _int(v) and v > 0


def _nonneg_int(v):
    return _int(v) and v >= 0


def _pos_or_auto(v):
    """x or y of a cell: >= 0, or -1 which the game's data uses for a cell the grid places itself (two cells in 5,410)."""
    return _int(v) and v >= -1


SPECS = {
    "layouts": {"id": _int, "name": _str, "guid": lambda v: isinstance(v, str) and bool(HEX32.fullmatch(v)), "bundle": _str},
    "elements": {"layout_id": _int, "local_id": _int, "parent_local_id": lambda v: v is None or _int(v), "ord": _int,
                 "type": _str, "name": _str, "classes": _strs},
    "includes": {"from_layout_id": _int, "element_local_id": _int, "alias": _str, "to_layout_id": _int},
    "panels": {"panel_id": lambda v: _str(v, True), "layout_id": _int},
    "tiles": {"panel_layout_id": _int, "set_name": _str, "breakpoint": _int, "variant_idx": _int, "composition": _str,
              "cell_index": _int, "cell_element_id": _str, "cfg_index": _int,
              "size": lambda v: isinstance(v, dict) and set(v) == {"w", "h"} and _pos_int(v["w"]) and _pos_int(v["h"]),
              "tile_layout_id": _int},
    "compositions": {"name": lambda v: _str(v, True), "layout_mode": _str, "preset_name": _str, "preset_w": _nonneg_int,
                     "preset_h": _nonneg_int, "instantiation_order": lambda v: isinstance(v, list) and all(_int(x) for x in v),
                     "conditions": _strs},
    "cells": {"composition": _str, "cell_index": _int, "element_id": _str, "x": _pos_or_auto, "y": _pos_or_auto,
              "w": _pos_int, "h": _pos_int, "min_w": _nonneg_int, "min_h": _nonneg_int, "max_w": _nonneg_int,
              "max_h": _nonneg_int, "flags": _strs, "h_align": _str, "v_align": _str},
    "cell_configs": {"composition": _str, "cell_index": _int, "cfg_index": _int, "size_w": _pos_int, "size_h": _pos_int,
                     "tile_layout_id": _int},
}
ANCHOR_KEYS = ("layout_name", "layout_name_suffix", "layout_name_regex", "element_name", "element_class")


def _check_source(e, src):
    """meta.source: which files the dump was read from. platform_folder and catalog_hash are non-empty strings;
    bundles maps every bundle file name the exporter read to its sha256 (64 lowercase hex), at least one."""
    if not isinstance(src, dict):
        e.add("meta.source", "required object with platform_folder, catalog_hash and bundles")
        return
    for k in src:
        if k not in ("platform_folder", "catalog_hash", "bundles"):
            e.add("meta.source", "unknown key %r" % k)
    for k in ("platform_folder", "catalog_hash"):
        if not _str(src.get(k), True):
            e.add("meta.source." + k, "required, non-empty string")
    b = src.get("bundles")
    if not isinstance(b, dict) or not b:
        e.add("meta.source.bundles", "required non-empty object: bundle file name -> sha256")
        return
    for name, h in b.items():
        if not _str(name, True):
            e.add("meta.source.bundles", "bundle name must be a non-empty string")
        elif not (isinstance(h, str) and HEX64.fullmatch(h)):
            e.add("meta.source.bundles", "%s: sha256 must be 64 lowercase hex characters" % name)


def validate(d):
    """Returns (errors, total). Empty errors = the dump is valid. Never raises for bad content."""
    e = _Errs()
    if not isinstance(d, dict):
        e.add("file", "top level must be an object")
        return e.list, e.total
    meta = d.get("meta")
    if not isinstance(meta, dict):
        e.add("meta", "missing or not an object")
    else:
        sch = meta.get("schema")
        if sch != SCHEMA:
            e.add("meta.schema", "unsupported schema %r; this app reads only %r%s" % (sch, SCHEMA, " (fmlayout-index/1 is refused: it does not say which files it was read from; re-export with the /2 exporter)" if sch == "fmlayout-index/1" else ""))
            return e.list, e.total        # a different contract version: nothing else is meaningful
        allowed = {"schema", "game_build", "index_fingerprint", "exported_at", "runtime_classes_provenance", "source"}
        for k in meta:
            if k not in allowed:
                e.add("meta", "unknown key %r" % k)
        for k in ("game_build", "index_fingerprint", "exported_at"):
            if not _str(meta.get(k), True):
                e.add("meta." + k, "required, non-empty string")
        if "runtime_classes_provenance" in meta and not _str(meta["runtime_classes_provenance"], True):
            e.add("meta.runtime_classes_provenance", "must be a non-empty string")
        _check_source(e, meta.get("source"))
    for k in d:
        if k not in TOP:
            e.add("file", "unknown top-level key %r" % k)
    for k in TOP:
        if k not in d:
            e.add("file", "missing section %r" % k)
    if e.total:
        return e.list, e.total
    for k in SECTIONS:
        if not isinstance(d[k], list):
            e.add(k, "must be an array")
    areas = d["areas"]
    if not (isinstance(areas, dict) and set(areas) == {"map", "anchors"} and isinstance(areas["map"], dict) and isinstance(areas["anchors"], list)):
        e.add("areas", "must be an object with exactly 'map' (object) and 'anchors' (array)")
    if e.total:
        return e.list, e.total
    # per-record shape
    ok = {}
    for sec in SECTIONS:
        opt = ("runtime_classes",) if sec == "elements" else ("bundle", "path_id") if sec == "compositions" else ()
        ok[sec] = []
        for i, rec in enumerate(d[sec]):
            good = _check_record(e, "%s[%d]" % (sec, i), rec, SPECS[sec], opt)
            if good and sec == "elements" and "runtime_classes" in rec and not _strs(rec["runtime_classes"]):
                e.add("elements[%d]" % i, "runtime_classes must be an array of strings"); good = False
            if good and sec == "compositions" and (("bundle" in rec and not _str(rec["bundle"], True)) or ("path_id" in rec and not _int(rec["path_id"]))):
                e.add("compositions[%d]" % i, "bundle must be a non-empty string and path_id an integer (where the composition lives in the game)"); good = False
            if good:
                ok[sec].append(rec)
    for name, area in areas["map"].items():
        if not _str(area, True):
            e.add("areas.map", "area for %r must be a non-empty string" % name)
    for i, a in enumerate(areas["anchors"]):
        w = "areas.anchors[%d]" % i
        if not isinstance(a, dict):
            e.add(w, "must be an object"); continue
        sel = [k for k in a if k != "area"]
        if not _str(a.get("area"), True) or len(sel) != 1 or sel[0] not in ANCHOR_KEYS or not _str(a[sel[0]], True):
            e.add(w, "needs 'area' plus exactly one of %s" % ", ".join(ANCHOR_KEYS))
    if any(isinstance(r, dict) and "runtime_classes" in r for r in d["elements"]) and not _str((d["meta"] or {}).get("runtime_classes_provenance"), True):
        e.add("meta.runtime_classes_provenance", "required when any element has runtime_classes")
    if e.total:
        return e.list, e.total
    # identity and references (only when every record is well formed)
    lay = {}
    for r in d["layouts"]:
        if r["id"] in lay:
            e.add("layouts", "duplicate id %d" % r["id"])
        lay[r["id"]] = r
    names = {r["name"] for r in d["layouts"]}
    for n in areas["map"]:
        if n not in names:
            e.add("areas.map", "layout name %r is not in layouts" % n)
    els = set()
    for r in d["elements"]:
        k = (r["layout_id"], r["local_id"])
        if k in els:
            e.add("elements", "duplicate (layout_id, local_id) %r" % (k,))
        els.add(k)
        if r["layout_id"] not in lay:
            e.add("elements", "layout_id %d is not in layouts" % r["layout_id"])
    for r in d["elements"]:
        if r["parent_local_id"] is not None and (r["layout_id"], r["parent_local_id"]) not in els:
            e.add("elements", "parent %d of (%d, %d) is not an element of that layout" % (r["parent_local_id"], r["layout_id"], r["local_id"]))
    for r in d["includes"]:
        if r["from_layout_id"] not in lay or r["to_layout_id"] not in lay:
            e.add("includes", "unknown layout id in %r" % ((r["from_layout_id"], r["to_layout_id"]),))
        elif (r["from_layout_id"], r["element_local_id"]) not in els:
            e.add("includes", "element %d is not in layout %d" % (r["element_local_id"], r["from_layout_id"]))
    pids = set()
    for r in d["panels"]:
        if r["panel_id"] in pids:
            e.add("panels", "duplicate panel_id %r" % r["panel_id"])
        pids.add(r["panel_id"])
        if r["layout_id"] not in lay:
            e.add("panels", "layout_id %d is not in layouts" % r["layout_id"])
    comps = set()
    for r in d["compositions"]:
        if r["name"] in comps:
            e.add("compositions", "duplicate name %r" % r["name"])
        comps.add(r["name"])
    cells = set()
    for r in d["cells"]:
        k = (r["composition"], r["cell_index"])
        if k in cells:
            e.add("cells", "duplicate %r" % (k,))
        cells.add(k)
        if r["composition"] not in comps:
            e.add("cells", "composition %r is not in compositions" % r["composition"])
        if (r["max_w"] > 0 and r["min_w"] > r["max_w"]) or (r["max_h"] > 0 and r["min_h"] > r["max_h"]):      # a max of 0 means unlimited in the game's data
            e.add("cells", "%r has min above max" % (k,))
        if max(r["x"], r["y"], r["w"], r["h"], r["min_w"], r["min_h"], r["max_w"], r["max_h"]) > MAX_COORD:
            e.add("cells", "%r has a value above %d" % (k, MAX_COORD))
    cfgs = set()
    for r in d["cell_configs"]:
        k = (r["composition"], r["cell_index"], r["cfg_index"])
        if k in cfgs:
            e.add("cell_configs", "duplicate %r" % (k,))
        cfgs.add(k)
        if (r["composition"], r["cell_index"]) not in cells:
            e.add("cell_configs", "cell %r does not exist" % ((r["composition"], r["cell_index"]),))
        if r["tile_layout_id"] not in lay:
            e.add("cell_configs", "tile_layout_id %d is not in layouts" % r["tile_layout_id"])
    for r in d["tiles"]:
        if r["panel_layout_id"] not in lay or r["tile_layout_id"] not in lay:
            e.add("tiles", "unknown layout id in %r" % ((r["panel_layout_id"], r["tile_layout_id"]),))
        if r["composition"] not in comps:
            e.add("tiles", "composition %r is not in compositions" % r["composition"])
        elif (r["composition"], r["cell_index"]) not in cells:
            e.add("tiles", "cell %r does not exist" % ((r["composition"], r["cell_index"]),))
    return e.list, e.total


def summary(d):
    """Counts per section (call on a valid dump)."""
    out = {k: len(d[k]) for k in SECTIONS}
    out["areas.map"] = len(d["areas"]["map"])
    out["areas.anchors"] = len(d["areas"]["anchors"])
    out["elements_with_runtime_classes"] = sum(1 for r in d["elements"] if r.get("runtime_classes"))
    return out


def short_fingerprint(fp):
    return (fp or "")[:12]


def read_file(path):
    """Parse a dump file. Raises LayoutError for size, encoding and JSON problems."""
    p = Path(path)
    if not p.is_file():
        raise LayoutError("no such file: %s" % p)
    if p.stat().st_size > MAX_BYTES:
        raise LayoutError("file is larger than %d MB; refusing to load it" % (MAX_BYTES // (1024 * 1024)))
    raw = p.read_bytes()
    try:
        return json.loads(raw.decode("utf-8-sig")), raw
    except (UnicodeDecodeError, ValueError) as ex:
        raise LayoutError("not valid UTF-8 JSON: %s" % ex)


def check_file(path):
    """Validate any file. Returns {"valid", "summary" | "errors", "total_errors", "meta"}; raises LayoutError only for unreadable input."""
    d, _ = read_file(path)
    errs, total = validate(d)
    if errs:
        return {"valid": False, "errors": errs, "total_errors": total}
    m = d["meta"]
    return {"valid": True, "schema": m["schema"], "game_build": m["game_build"],
            "fingerprint": short_fingerprint(m["index_fingerprint"]), "exported_at": m["exported_at"], "counts": summary(d)}


# ---------------------------------------------------------------- storage
def _dir(ws):
    d = Path(ws.layout)
    d.mkdir(parents=True, exist_ok=True)
    return d


def _atomic(path, data):
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_bytes(data)
    os.replace(tmp, path)


def _read_meta(path):
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))["meta"]
    except (OSError, ValueError, KeyError):
        return None


def import_dump(ws, path):
    """Validate, then store as current.json (the old current becomes previous.json, one generation). All or nothing."""
    d, raw = read_file(path)
    return _import(ws, d, raw, Path(path).name)


def import_bytes(ws, raw, source_name="upload"):
    """Same as import_dump for a dump received as bytes (the browser upload)."""
    if len(raw) > MAX_BYTES:
        raise LayoutError("file is larger than %d MB; refusing to load it" % (MAX_BYTES // (1024 * 1024)))
    try:
        d = json.loads(raw.decode("utf-8-sig"))
    except (UnicodeDecodeError, ValueError) as ex:
        raise LayoutError("not valid UTF-8 JSON: %s" % ex)
    return _import(ws, d, raw, source_name)


def _import(ws, d, raw, source_name):
    errs, total = validate(d)
    if errs:
        raise LayoutError("layout dump refused (%d violation%s); nothing was loaded" % (total, "" if total == 1 else "s"), errs, total)
    st = staleness(d["meta"], ws)
    if st["status"] == "contaminated":
        raise LayoutError("layout dump refused: " + st["message"] + " Nothing was loaded.", [st["message"]], 1)
    base = _dir(ws)
    cur, prev, tmp = base / "current.json", base / "previous.json", base / "incoming.tmp"
    old = _read_meta(cur)
    tmp.write_bytes(raw)
    backup = None
    try:
        if cur.is_file():
            backup = base / "previous.json.new"
            os.replace(cur, backup)
        os.replace(tmp, cur)
        if backup is not None:
            os.replace(backup, prev)
    except OSError:
        if backup is not None and backup.is_file() and not cur.is_file():
            os.replace(backup, cur)       # put the old current back: never a half-imported state
        if tmp.is_file():
            tmp.unlink()
        raise
    status = {"source_name": source_name, "fingerprint": d["meta"]["index_fingerprint"],
              "previous_fingerprint": old["index_fingerprint"] if old else None,
              "changed": None if old is None else old["index_fingerprint"] != d["meta"]["index_fingerprint"]}
    _atomic(base / "status.json", json.dumps(status).encode("utf-8"))
    return state(ws)

def load(ws):
    """The stored current dump (already validated at import), or None."""
    cur = Path(ws.layout) / "current.json"
    if not cur.is_file():
        return None
    return json.loads(cur.read_text(encoding="utf-8-sig"))


def staleness(meta, ws):
    """Compare meta.source with the manifest's reference hashes (game_build is a display label only).
    fresh: catalog hash and every bundle hash equal. stale: the catalog hash differs (game updated) or another platform folder.
    contaminated: catalog hash equal but a bundle hash differs (the dump was read from modified files). unknown: no reference
    hashes yet, or the dump names a bundle the manifest has no reference for."""
    man = ws.vanilla_manifest()
    ref = (man or {}).get("reference")
    src = meta["source"]
    base = {"dump_build": meta["game_build"], "snapshot_build": (man or {}).get("game_build"), "differing_bundles": []}
    if not ref or not ref.get("catalog_hash") or not isinstance(ref.get("bundles"), dict):
        return dict(base, status="unknown", message="The vanilla snapshot has no reference hashes yet (a snapshot taken before this "
                    "version, or none at all). Use 'Record reference hashes' on the Setup tab with the game closed and stock files; "
                    "until then layout features cannot be checked against the game files.")
    if src["platform_folder"] != ref.get("platform_folder") or src["catalog_hash"] != ref["catalog_hash"]:
        return dict(base, status="stale", message="STALE LAYOUT DATA: the dump was read from catalog %s (%s) but the snapshot's reference is "
                    "catalog %s (%s): the game was updated or this is another install. Re-export the dump and take a new snapshot."
                    % (src["catalog_hash"][:12], src["platform_folder"], str(ref["catalog_hash"])[:12], ref.get("platform_folder")))
    diff = sorted(n for n, h in src["bundles"].items() if n in ref["bundles"] and ref["bundles"][n] != h)
    if diff:
        return dict(base, status="contaminated", differing_bundles=diff,
                    message="CONTAMINATED DUMP: the catalog matches but %d bundle%s differ from the reference (%s): the dump was read "
                            "from modified files. Restore the stock files and re-export." % (len(diff), "" if len(diff) == 1 else "s", ", ".join(diff[:5])))
    missing = sorted(n for n in src["bundles"] if n not in ref["bundles"])
    if missing:
        return dict(base, status="unknown", message="The dump read %d bundle%s the snapshot has no reference hash for (%s); record "
                    "reference hashes again." % (len(missing), "" if len(missing) == 1 else "s", ", ".join(missing[:5])))
    return dict(base, status="fresh", message="")


def state(ws):
    base = Path(ws.layout)
    meta = _read_meta(base / "current.json")
    if not meta:
        return {"present": False}
    try:
        st = json.loads((base / "status.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        st = {}
    prev = _read_meta(base / "previous.json")
    return {"present": True, "game_build": meta["game_build"], "exported_at": meta["exported_at"],
            "fingerprint": short_fingerprint(meta["index_fingerprint"]),
            "previous_fingerprint": short_fingerprint(prev["index_fingerprint"]) if prev else None,
            "changed_vs_previous": st.get("changed"), "source_name": st.get("source_name"),
            "staleness": staleness(meta, ws), "source": {"platform_folder": meta["source"]["platform_folder"], "catalog_hash": meta["source"]["catalog_hash"][:12], "bundles": len(meta["source"]["bundles"])},
            "runtime_classes_provenance": meta.get("runtime_classes_provenance")}
