"""Build an `fmlayout-index/2` dump from the user's own game bundles.

The producer used to be FM27_LayoutMCP's sqlite index (skin_editor/layout_export.py, kept as a developer
cross-check only). This module reads the same facts straight from the `ui-*.bundle` files the game ships:
VisualTreeAssets (layouts, elements, includes, GUIDs, sibling ordinals), composition sets and compositions
(sets, breakpoints, variants, cells, per-cell configs), the panel ids, and the screen -> composition set join.

Two things the sqlite index precomputed are derived here and must not be guessed:

* a layout's GUID is the `container` field UnityPy exposes on the asset object (the Addressables asset GUID);
* an element's `ord` is its position in a pre-order walk of `m_Children` (the serialized sibling order).

The screen join is: for every VisualTreeAsset, walk its OWN serialized tree (template includes are not
expanded, exactly like the sqlite index) and collect composition-set references from
`Bindings.m_gridCompositionSet` and `GridCompositionSets[*].m_gridCompositionSetBindings.m_gridCompositionSet`
on elements, plus `Bindings.m_gridCompositionSet` from a template instance's `m_SerializedDataOverride`
entries. Each set contributes its breakpoints' variants; each variant contributes every cell config.

The build is pure: it returns a dict and never imports it. `read_and_import` validates the finished dump and
only then calls `layout_dump.import_bytes`; a cancelled build imports nothing.
"""
import hashlib
import json
import time
from pathlib import Path

from . import bundles, layout_dump, layout_export
from .render import compositionset
from .render.layouts import LayoutStore

SCHEMA = "fmlayout-index/2"
VTA_GLOB = "ui-visualtreeassets*.bundle"
UI_GLOB = "ui-*.bundle"
LAYOUT_MODES = layout_export.LAYOUT_MODES
# typetree field -> dump flag, in the same order as layout_export.FLAG_COLUMNS
CELL_FLAGS = (
    ("m_isLocked", "locked"), ("m_isDebug", "debug"), ("m_isDynamic", "dynamic"),
    ("m_expandToContent", "expand_to_content"), ("m_takesFocus", "takes_focus"), ("m_isOptional", "optional"),
)
MAX_DEPTH = 512          # a malformed reference graph must not recurse without end


class LayoutScanError(RuntimeError):
    """The bundles do not contain a fact the dump needs, or two records contradict each other."""


class ScanCancelled(Exception):
    """The caller cancelled the build before it finished. Nothing has been imported."""


def _cancelled(progress):
    return bool(progress is not None and getattr(progress, "cancelled", None) and progress.cancelled())


def _check(progress, what=""):
    if _cancelled(progress):
        raise ScanCancelled(what)


def _say(progress, message, fraction):
    if progress is not None and callable(progress):
        progress(message, fraction)


def _hex32(value):
    return isinstance(value, str) and len(value) == 32 and all(c in "0123456789abcdef" for c in value)


# ---------------------------------------------------------------- layouts
def _qualname(ref):
    d = (ref or {}).get("data") or {}
    return d


def _serialized(refs, data):
    return ((refs.get((data.get("m_SerializedData") or {}).get("rid")) or {}).get("data") or {})


def _direct_set_pids(sd):
    """Composition-set pointers a serialized element carries directly (single grid and multi grid)."""
    out = []
    if not isinstance(sd, dict):
        return out
    b = sd.get("Bindings")
    p = b.get("m_gridCompositionSet") if isinstance(b, dict) else None
    if isinstance(p, dict) and "m_PathID" in p:
        out.append(int(p.get("m_PathID") or 0))
    for group in sd.get("GridCompositionSets") or []:
        b = (group or {}).get("m_gridCompositionSetBindings")
        p = b.get("m_gridCompositionSet") if isinstance(b, dict) else None
        if isinstance(p, dict) and "m_PathID" in p:
            out.append(int(p.get("m_PathID") or 0))
    return out


def _override_set_pids(sd):
    """A template instance's override may carry the single-grid binding; the sqlite index read only this form."""
    if not isinstance(sd, dict):
        return []
    b = sd.get("Bindings")
    p = b.get("m_gridCompositionSet") if isinstance(b, dict) else None
    return [int(p.get("m_PathID") or 0)] if isinstance(p, dict) and "m_PathID" in p else []


def _read_layouts(store, progress=None, bundle_names=None):
    """(layouts, elements, includes, grid_refs, guid_to_id, path_to_guid).

    layouts:       [{id, name, guid, bundle}]
    elements:      [{layout_id, local_id, parent_local_id, ord, type, name, classes}]
    includes:      [{from_layout_id, element_local_id, alias, to_layout_id}]
    grid_refs:     {layout guid: [(element_local_id, set path id), ...]}   the screen join's raw rows
    """
    aa = Path(store.folder)
    names = list(bundle_names or sorted(p.name for p in aa.glob(VTA_GLOB)))
    if not names:
        raise LayoutScanError("no %s bundles in %s" % (VTA_GLOB, aa))
    raw, guid_seen, path_to_guid = [], {}, {}
    for k, bundle_name in enumerate(names):
        _check(progress, "reading " + bundle_name)
        _say(progress, "reading the layouts in " + bundle_name, 0.10 + 0.35 * (k / max(1, len(names))))
        objs = store._bundle_objs(bundle_name)
        for obj in objs.values():
            if getattr(obj.type, "name", "") != "MonoBehaviour":
                continue
            try:
                tree = obj.read_typetree()
            except Exception as ex:                    # a layout we cannot decode is a fact we do not have
                raise LayoutScanError("cannot decode %s object %s in %s: %s" % (obj.type.name, obj.path_id, bundle_name, ex))
            if not isinstance(tree, dict) or "m_VisualTree" not in tree:
                continue
            guid = (getattr(obj, "container", "") or "").lower()
            if not _hex32(guid):
                raise LayoutScanError("%s object %s in %s has no 32-hex asset GUID (container %r); the dump cannot name the layout"
                                      % (tree.get("m_Name") or "VisualTreeAsset", obj.path_id, bundle_name, getattr(obj, "container", None)))
            if guid in guid_seen:
                raise LayoutScanError("layout GUID %s appears twice (%s and %s)" % (guid, guid_seen[guid][0], bundle_name))
            refs = {r["rid"]: r for r in (tree.get("references") or {}).get("RefIds", [])}
            usings = {}
            for u in tree.get("m_Usings") or []:
                alias = u.get("alias") or u.get("m_Alias") or ""
                path = (u.get("path") or u.get("m_Path") or "").lower()
                usings[alias] = path
            elements, includes, grid_refs = [], [], []

            def walk(rid, parent_id, depth):
                if depth > MAX_DEPTH:
                    raise LayoutScanError("layout %s (%s) nests deeper than %d references" % (tree.get("m_Name"), guid, MAX_DEPTH))
                rec = refs.get(rid) or {}
                d = rec.get("data") or {}
                if "m_Id" not in d:
                    return
                local_id = d["m_Id"]
                if not isinstance(local_id, int) or isinstance(local_id, bool):
                    raise LayoutScanError("layout %s element has a non-integer m_Id %r" % (tree.get("m_Name"), local_id))
                sd = _serialized(refs, d)
                rec_type = rec.get("type") or {}
                is_template = rec_type.get("class") == "TemplateAsset"
                full = d.get("m_FullTypeName") or ""
                alias = (d.get("m_TemplateAlias") or "") if is_template else ""
                typ = full if full else ("Template:" + (d.get("m_TemplateAlias") or ""))
                elements.append({"local_id": local_id, "parent_local_id": parent_id, "ord": len(elements),
                                 "type": typ, "name": (sd.get("name") if isinstance(sd, dict) else "") or "",
                                 "classes": [c for c in (d.get("m_Classes") or []) if isinstance(c, str) and c]})
                for pid in _direct_set_pids(sd):
                    grid_refs.append((local_id, pid))
                if is_template:
                    includes.append({"element_local_id": local_id, "alias": alias, "to_guid": usings.get(alias, "")})
                    for override in d.get("m_SerializedDataOverride") or []:
                        ov_sd = (refs.get((override.get("m_SerializedData") or {}).get("rid")) or {}).get("data") or {}
                        for pid in _override_set_pids(ov_sd):
                            grid_refs.append((int(override.get("m_ElementId")), pid))
                for child in d.get("m_Children") or []:
                    walk(child["rid"], local_id, depth + 1)

            root = (tree.get("m_VisualTree") or {}).get("rid")
            if root is None:
                raise LayoutScanError("layout %s (%s) has no m_VisualTree root" % (tree.get("m_Name"), guid))
            walk(root, None, 0)
            raw.append({"bundle": bundle_name, "name": tree.get("m_Name") or "", "guid": guid,
                        "path_id": int(obj.path_id), "elements": elements, "includes": includes, "grid_refs": grid_refs})
            guid_seen[guid] = (bundle_name, tree.get("m_Name") or "")
            path_to_guid[int(obj.path_id)] = guid

    raw.sort(key=lambda r: (r["bundle"], r["name"], r["guid"]))
    layouts, elements, includes, grid_by_guid = [], [], [], {}
    for i, rec in enumerate(raw, 1):
        layouts.append({"id": i, "name": rec["name"], "guid": rec["guid"], "bundle": rec["bundle"]})
        for e in rec["elements"]:
            elements.append(dict(e, layout_id=i))
        for inc in rec["includes"]:
            includes.append({"from_layout_id": i, "element_local_id": inc["element_local_id"], "alias": inc["alias"],
                             "to_layout_id": None, "_to_guid": inc["to_guid"]})
        grid_by_guid[rec["guid"]] = rec["grid_refs"]
    guid_to_id = {r["guid"]: r["id"] for r in layouts}
    for inc in includes:
        to = inc.pop("_to_guid")
        if not to or to not in guid_to_id:
            raise LayoutScanError("layout %d element %d includes %r, whose GUID %r is not a layout in these bundles"
                                  % (inc["from_layout_id"], inc["element_local_id"], inc["alias"], to))
        inc["to_layout_id"] = guid_to_id[to]
    return layouts, elements, includes, grid_by_guid, guid_to_id, path_to_guid


# ---------------------------------------------------------------- compositions, sets, panels
def _canonical_conditions(values):
    return [v if isinstance(v, str) else json.dumps(v, sort_keys=True) for v in (values or [])]


def _read_compositions(store, sets, comps, guid_to_id, progress=None):
    """(compositions, cells, cell_configs, set_by_path) from the composition typetrees.

    `sets` and `comps` are compositionset.scan's dicts (identified by serialized type signature, not names).
    """
    set_by_path = {}
    for key, rec in sets.items():
        pid = int(rec["path_id"])
        obj = (store._objs.get(rec["bundle"]) or {}).get(pid)
        tree = obj.read_typetree() if obj is not None else None
        name = (tree or {}).get("m_Name") if isinstance(tree, dict) else None
        if name is None:
            name = key
        if pid in set_by_path:
            raise LayoutScanError("composition set path id %d appears twice" % pid)
        breakpoints = {}
        for bp, refs in rec["breakpoints"].items():
            breakpoints[int(bp)] = [int(r["path_id"]) for r in refs]
        set_by_path[pid] = {"name": name, "bundle": rec["bundle"], "breakpoints": breakpoints}

    compositions, cells, cell_configs = [], [], []
    names, pids = {}, set()
    items = sorted(comps.items(), key=lambda kv: (kv[0], kv[1]["bundle"], int(kv[1]["path_id"])))
    for k, (name, rec) in enumerate(items):
        _check(progress, "reading composition " + name)
        if k % 200 == 0:
            _say(progress, "reading compositions (%d/%d)" % (k, len(items)), 0.50 + 0.20 * (k / max(1, len(items))))
        pid = int(rec["path_id"])
        obj = (store._objs.get(rec["bundle"]) or {}).get(pid)
        if obj is None:
            raise LayoutScanError("composition %s (%s object %s) is not in the bundle" % (name, rec["bundle"], pid))
        tree = obj.read_typetree()
        if not isinstance(tree, dict) or "m_gridComponents" not in tree:
            raise LayoutScanError("composition %s (%s object %s) has no m_gridComponents" % (name, rec["bundle"], pid))
        if name in names:
            raise LayoutScanError("composition name %r appears twice (%s and %s); the dump's name-keyed rows would collide"
                                  % (name, names[name], rec["bundle"]))
        if pid in pids:
            raise LayoutScanError("composition path id %d appears twice" % pid)
        names[name] = rec["bundle"]
        pids.add(pid)
        preset = tree.get("m_layoutPreset") or {}
        size = preset.get("Size") or {}
        slices = tree.get("m_optionalSlices") or {}
        comp = {"name": name, "layout_mode": LAYOUT_MODES.get(tree.get("m_layoutMode"), str(tree.get("m_layoutMode"))),
                "preset_name": preset.get("Name") or "", "preset_w": int(size.get("x") or 0), "preset_h": int(size.get("y") or 0),
                "instantiation_order": [int(x) for x in (slices.get("m_instantiationOrder") or [])],
                "conditions": _canonical_conditions((tree.get("m_optionalConditions") or []) + (tree.get("m_optionalConfigConditions") or [])),
                "bundle": rec["bundle"], "path_id": pid}
        compositions.append(comp)
        for ci, cell in enumerate(tree["m_gridComponents"]):
            loc = cell.get("m_location") or {}
            mn, mx = cell.get("m_minSize") or {}, cell.get("m_maxSize") or {}
            flags = [flag for field, flag in CELL_FLAGS if cell.get(field)]
            if cell.get("m_features"):
                flags.append("features:%d" % int(cell["m_features"]))
            cells.append({"composition": name, "cell_index": ci, "element_id": cell.get("m_elementID") or "",
                          "x": int(loc.get("x") or 0), "y": int(loc.get("y") or 0), "w": int(loc.get("width") or 0),
                          "h": int(loc.get("height") or 0), "min_w": int(mn.get("x") or 0), "min_h": int(mn.get("y") or 0),
                          "max_w": int(mx.get("x") or 0), "max_h": int(mx.get("y") or 0), "flags": flags,
                          "h_align": str(cell.get("m_horizontalAlignment", 0)), "v_align": str(cell.get("m_verticalAlignment", 0))})
            for cfg_index, cfg in enumerate(cell.get("m_gridElementConfigs") or []):
                cfg_size = cfg.get("Size") or {}
                guid = ((cfg.get("AssetRef") or {}).get("m_AssetGUID") or "").lower()
                if guid not in guid_to_id:
                    raise LayoutScanError("composition %s cell %d config %d names tile GUID %r, which is not a layout in these bundles"
                                          % (name, ci, cfg_index, guid))
                cell_configs.append({"composition": name, "cell_index": ci, "cfg_index": cfg_index,
                                     "size_w": int(cfg_size.get("x") or 0), "size_h": int(cfg_size.get("y") or 0),
                                     "tile_layout_id": guid_to_id[guid]})
    compositions.sort(key=lambda c: c["name"])
    cells.sort(key=lambda c: (c["composition"], c["cell_index"]))
    cell_configs.sort(key=lambda c: (c["composition"], c["cell_index"], c["cfg_index"]))
    return compositions, cells, cell_configs, set_by_path


def _crosscheck_cells(aa, compositions, cells):
    """layout_export.read_cells reads the same cells a second, independent way (it ignores configs); compare the
    geometry it returns with the one taken from the composition typetrees. A disagreement means one reader is wrong,
    so the build stops instead of choosing."""
    real = layout_export.read_cells(aa)
    seen = set()
    for comp in compositions:
        key = (comp["bundle"], comp["path_id"])
        rec = real.get(key)
        if rec is None:
            raise LayoutScanError("composition %s (%s object %s) is not in read_cells' output"
                                  % (comp["name"], comp["bundle"], comp["path_id"]))
        mine = [c for c in cells if c["composition"] == comp["name"]]
        if len(mine) != len(rec["cells"]):
            raise LayoutScanError("composition %s has %d cells in the typetree but %d in read_cells"
                                  % (comp["name"], len(mine), len(rec["cells"])))
        for c, r in zip(mine, rec["cells"]):
            got = (c["cell_index"], c["element_id"], c["x"], c["y"], c["w"], c["h"], c["min_w"], c["min_h"],
                   c["max_w"], c["max_h"], "locked" in c["flags"])
            want = (r["index"], r["id"], r["x"], r["y"], r["w"], r["h"], r["min"][0], r["min"][1],
                    r["max"][0], r["max"][1], bool(r["locked"]))
            if got != want:
                raise LayoutScanError("composition %s cell %d disagrees with read_cells: typetree %r, read_cells %r"
                                      % (comp["name"], c["cell_index"], got, want))
        seen.add(key)
    return len(seen)


def _read_panels(aa, guid_to_id):
    out = []
    for panel_id, guid in layout_export.read_panels(aa):
        lid = guid_to_id.get((guid or "").lower())
        if lid is not None:
            out.append({"panel_id": panel_id, "layout_id": lid})
    out.sort(key=lambda p: p["panel_id"])
    return out


def _read_tiles(guid_to_id, grid_by_guid, set_by_path, comp_by_name, cell_configs, cells):
    """The screen -> set -> breakpoint -> variant -> composition cell config join."""
    element_id = {(c["composition"], c["cell_index"]): c["element_id"] for c in cells}
    configs = {}
    for cfg in cell_configs:
        configs.setdefault(cfg["composition"], []).append(cfg)
    tiles = []
    for screen_guid, refs in grid_by_guid.items():
        screen_id = guid_to_id[screen_guid]
        for element_local_id, set_pid in refs:
            if not set_pid:
                continue
            s = set_by_path.get(set_pid)
            if s is None:
                raise LayoutScanError("layout %s element %d names composition set %d, which these bundles do not contain"
                                      % (screen_guid, element_local_id, set_pid))
            for breakpoint in sorted(s["breakpoints"]):
                for variant_idx, comp_pid in enumerate(s["breakpoints"][breakpoint]):
                    comp = comp_by_name.get(comp_pid)
                    if comp is None:
                        raise LayoutScanError("composition set %r breakpoint %d variant %d names composition %d, which these bundles do not contain"
                                              % (s["name"], breakpoint, variant_idx, comp_pid))
                    for cfg in configs.get(comp, ()):
                        key = (cfg["composition"], cfg["cell_index"])
                        tiles.append({"panel_layout_id": screen_id, "set_name": s["name"], "breakpoint": breakpoint,
                                      "variant_idx": variant_idx, "composition": comp, "cell_index": cfg["cell_index"],
                                      "cell_element_id": element_id[key], "cfg_index": cfg["cfg_index"],
                                      "size": {"w": cfg["size_w"], "h": cfg["size_h"]}, "tile_layout_id": cfg["tile_layout_id"]})
    tiles.sort(key=lambda t: (t["panel_layout_id"], t["set_name"], t["breakpoint"], t["variant_idx"], t["composition"],
                              t["cell_index"], t["cfg_index"]))
    return tiles


# ---------------------------------------------------------------- the build
def _fingerprint(sections):
    return hashlib.sha256(json.dumps({k: [len(v), hashlib.sha256(json.dumps(v, sort_keys=True).encode()).hexdigest()]
                                      for k, v in sections.items()}, sort_keys=True).encode()).hexdigest()


def build_dump(aa_dir, game_build, areas_json=None, progress=None, now=None, store=None, crosscheck=True):
    """Build the dump dict (not imported). `aa_dir` is a platform folder holding the game's ui-*.bundle files."""
    aa = Path(aa_dir)
    if not aa.is_dir():
        raise LayoutScanError("no such folder: %s" % aa)
    _check(progress, "before reading")
    _say(progress, "reading the composition sets", 0.02)
    if store is None:
        store = LayoutStore(aa)
    sets, comps, stats = compositionset.scan(store, check=lambda: _check(progress, "while scanning the UI bundles"))
    bad = sorted(n for n, s in stats.items() if not s.get("read"))
    if bad:
        raise LayoutScanError("cannot read %d UI bundle%s (%s)" % (len(bad), "" if len(bad) == 1 else "s", ", ".join(bad[:6])))
    _say(progress, "reading the layouts", 0.10)
    layouts, elements, includes, grid_by_guid, guid_to_id, path_to_guid = _read_layouts(store, progress)
    _say(progress, "reading the compositions", 0.50)
    compositions, cells, cell_configs, set_by_path = _read_compositions(store, sets, comps, guid_to_id, progress)
    if crosscheck:
        _say(progress, "cross-checking the cells against read_cells", 0.70)
        _crosscheck_cells(aa, compositions, cells)
    comp_by_pid = {c["path_id"]: c["name"] for c in compositions}
    _say(progress, "joining the screen tiles", 0.72)
    tiles = _read_tiles(guid_to_id, grid_by_guid, set_by_path, comp_by_pid, cell_configs, cells)
    _check(progress, "before the panels")
    _say(progress, "reading the panel ids", 0.88)
    panels = _read_panels(aa, guid_to_id)
    if areas_json and Path(areas_json).is_file():
        cfg = json.loads(Path(areas_json).read_text(encoding="utf-8"))
        amap, anchors = layout_export.derive_areas(layouts, elements, includes, cfg)
    else:
        amap, anchors = {}, []
    _check(progress, "before hashing the bundles")
    _say(progress, "hashing the bundles the build read", 0.92)
    cat = next((p for p in (aa / "catalog.hash", aa.parent / "catalog.hash") if p.is_file()), None)
    if cat is None:
        raise LayoutScanError("no catalog.hash in %s or its parent; the dump could not say which game build it read" % aa)
    names = sorted(stats)
    source_bundles = {}
    for k, name in enumerate(names):
        _check(progress, "while hashing the bundles")
        if k % 10 == 0:
            _say(progress, "hashing the bundles (%d/%d)" % (k, len(names)), 0.92 + 0.05 * (k / max(1, len(names))))
        source_bundles[name] = bundles.sha256(aa / name)
    sections = {"layouts": layouts, "elements": elements, "includes": includes, "panels": panels, "tiles": tiles,
                "compositions": compositions, "cells": cells, "cell_configs": cell_configs}
    meta = {"schema": SCHEMA, "game_build": str(game_build or "unknown"), "index_fingerprint": _fingerprint(sections),
            "exported_at": now or time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "source": {"platform_folder": aa.name,
                       "catalog_hash": cat.read_text(encoding="utf-8", errors="replace").strip(),
                       "bundles": source_bundles}}
    _say(progress, "finished reading", 0.98)
    return dict({"meta": meta, "areas": {"map": amap, "anchors": anchors}}, **sections)


def read_and_import(ws, aa_dir, game_build, areas_json=None, progress=None, now=None, store=None):
    """Build, validate and import. The current dump is untouched unless the WHOLE build finished and validated."""
    d = build_dump(aa_dir, game_build, areas_json=areas_json, progress=progress, now=now, store=store)
    errs, total = layout_dump.validate(d)
    if errs:
        raise LayoutScanError("the built dump is not valid (%d violation%s): %s"
                              % (total, "" if total == 1 else "s", "; ".join(errs[:5])))
    _check(progress, "before importing")
    _say(progress, "importing the layout dump", 0.99)
    raw = json.dumps(d).encode("utf-8")
    return d, layout_dump.import_bytes(ws, raw, "read the game")
