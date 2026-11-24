"""The game's custom-layout files (CustomGridCompositions): read, generate from a bundle composition, edit, write byte-stable, back up and restore.

FM27 keeps a customised screen as ONE line of UTF-8 JSON (no BOM, no newline) named exactly by the composition's m_Name in
<home>/AppData/LocalLow/Sports Interactive/Football Manager 27/CustomGridCompositions/. When the file exists the game uses it instead of the bundle's
composition (CL part B/C, 2026-11-21); when it is absent the bundle's layout shows and the game does not recreate the file.

Instance ids (HYPOTHESIS, tested in CL3 part B): the game writes Unity instance ids for object references (the tile descriptions, the element set, the
validator). They change between sessions, so a generated file keeps the values from a REAL file only where the cell matches (same element id and
description keys) and uses 0 everywhere else; the descriptions are also named in m_configDescriptionKeys, which is what the game is believed to resolve.
"""
import copy
import datetime
import hashlib
import json
import os
import shutil
from collections import OrderedDict
from pathlib import Path

TOP_ORDER = ["m_compositionVersion", "m_gridBreakpoint", "m_layoutMode", "m_layoutPreset", "m_allowedTags", "m_contentAlignment", "m_gridComponents",
             "m_optionalSlices", "m_gridElementSet", "m_validator", "m_editorValidator", "m_reflowMode", "m_reverseOptionalForRTL", "m_isCustom",
             "m_optionalConditions", "m_optionalConfigConditions", "m_bindingExpect", "m_expectRemaps", "m_placementBindings"]
BOOL_KEYS = {"m_isLocked", "m_isDebug", "m_isDynamic", "m_expandToContent", "m_takesFocus", "m_isOptional", "m_overrideSlicesOrder", "m_reverseOptionalForRTL"}
PPTR = {"m_FileID", "m_PathID"}


# ---------------------------------------------------------------- locate, list, read, write
def folder(home=None):
    override = os.environ.get("FM27SE_CUSTOM_LAYOUTS")
    if home is None and override:
        return Path(override)
    return Path(home or Path.home()) / "AppData" / "LocalLow" / "Sports Interactive" / "Football Manager 27" / "CustomGridCompositions"


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def list_customised(fold=None):
    """The customised screens: every file in the folder (file name = composition name) with size, mtime and sha256."""
    fold = Path(fold or folder())
    if not fold.is_dir():
        return []
    return [{"composition": p.name, "size": p.stat().st_size, "mtime": datetime.datetime.fromtimestamp(p.stat().st_mtime).strftime("%Y-%m-%d %H:%M:%S"),
             "sha256": sha256(p)} for p in sorted(fold.iterdir()) if p.is_file()]


def loads(data):
    """bytes -> OrderedDict (key order kept)."""
    return json.loads(data.decode("utf-8"), object_pairs_hook=OrderedDict)


def dumps(obj):
    """OrderedDict -> the game's exact bytes: one line, no spaces, UTF-8 without BOM, no trailing newline."""
    return json.dumps(obj, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def read(path):
    return loads(Path(path).read_bytes())


def _dim(d, key, default):
    try:
        return int((d or {}).get(key, default))
    except (TypeError, ValueError):
        return default


def _clamp(v, lo, hi):
    return max(lo, min(hi, v))


def cell_limits(cell):
    """(min_w, min_h), (max_w, max_h) a cell may legally take. A zero max means unbounded."""
    mn, mx = cell.get("m_minSize") or {}, cell.get("m_maxSize") or {}
    return ((_dim(mn, "x", 1), _dim(mn, "y", 1)),
            (_dim(mx, "x", 0), _dim(mx, "y", 0)))


def has_real_references(obj):
    """Information only: whether the file carries non-zero Unity instance ids.

    Never a gate. A generated file has instanceID 0 everywhere and still loads: the game resolves
    tiles by name, and instance ids are per-session runtime numbers that cannot survive a restart.
    Real files keep non-zero ids only from the session that saved them."""
    for k in ("m_gridElementSet", "m_validator", "m_editorValidator"):
        if _dim(obj.get(k), "instanceID", 0) > 0:
            return True
    for c in obj.get("m_gridComponents") or []:
        for d in c.get("m_configDescriptions") or []:
            if _dim(d, "instanceID", 0) > 0:
                return True
        for cfg in c.get("m_gridElementConfigs") or []:
            if _dim(cfg.get("Description"), "instanceID", 0) > 0:
                return True
    return False


def grid_extent(obj):
    """The composition's own grid extent (max right/bottom edge) before any edit. A tile must stay inside it:
    a smaller breakpoint uses fewer columns, and writing a cell outside the extent is what crashes the game."""
    cells = obj.get("m_gridComponents") or []
    cols = max([_dim(c.get("m_location"), "x", 0) + _dim(c.get("m_location"), "width", 0) for c in cells] or [1])
    rows = max([_dim(c.get("m_location"), "y", 0) + _dim(c.get("m_location"), "height", 0) for c in cells] or [1])
    return max(1, cols), max(1, rows)


def apply_canvas_edits(obj, edits, runtime=None):
    """Apply Game Layouts canvas edits IN THEIR OWN SPACE. Returns how many cells changed.

    `space` is "main" (m_gridComponents, design coordinates) or a zone key
    ("m_right" / "m_bottom", the stored coordinates of m_optionalSlices.<zone>).
    A main edit is clamped to the design grid; a slot edit is clamped so its
    runtime cell (layoutspace.slice_zone_offset) stays inside the
    runtime grid. `runtime` is {"cols": n, "rows": n} from the preview; without it
    a slot only keeps x, y >= 0. Overlap is checked per space, never across.

    A saved cell has no cell_index - m_elementID is the only stable identity.
    """
    from . import layoutspace
    main = {}
    for c in obj.get("m_gridComponents") or []:
        ident = c.get("m_elementID")
        if ident is not None:
            main.setdefault(str(ident), c)
    slices = obj.get("m_optionalSlices") or {}
    by_zone = {}
    for zone in layoutspace.FILE_ZONES:
        by_zone[zone] = {}
        for e in slices.get(zone) or []:
            if isinstance(e, dict) and e.get("m_elementID") is not None:
                by_zone[zone].setdefault(str(e["m_elementID"]), e)
    dcols, drows = grid_extent(obj)
    rcols = _dim(runtime or {}, "cols", dcols)
    rrows = _dim(runtime or {}, "rows", drows)
    applied = 0
    for e in edits or []:
        space = str(e.get("space") or layoutspace.MAIN)
        if space == layoutspace.MAIN:
            c = main.get(str(e.get("element_id", "")))
            if c is None:
                continue
            loc = c.setdefault("m_location", {})
            if e.get("op") == "swap":
                new_id = str(e.get("new_element_id") or "").strip()
                if not new_id:
                    continue
                c["m_elementID"] = new_id
                c["m_configDescriptionKeys"] = [new_id]
                main[new_id] = c
                w = max(1, _dim(e, "w", _dim(loc, "width", 4)))
                h = max(1, _dim(e, "h", _dim(loc, "height", 2)))
                x = _clamp(_dim(e, "x", _dim(loc, "x", 0)), 0, max(0, dcols - w))
                y = _clamp(_dim(e, "y", _dim(loc, "y", 0)), 0, max(0, drows - h))
                mn = c.setdefault("m_minSize", {})
                mx = c.setdefault("m_maxSize", {})
                mn["x"], mn["y"] = min(w, _dim(mn, "x", w)), min(h, _dim(mn, "y", h))
                mx["x"], mx["y"] = max(w, _dim(mx, "x", w)), max(h, _dim(mx, "y", h))
            else:
                (min_w, min_h), (max_w, max_h) = cell_limits(c)
                w = max(min_w, _dim(e, "w", _dim(loc, "width", min_w)))
                h = max(min_h, _dim(e, "h", _dim(loc, "height", min_h)))
                if max_w > 0:
                    w = _clamp(w, min_w, max_w)
                if max_h > 0:
                    h = _clamp(h, min_h, max_h)
                x = _clamp(_dim(e, "x", _dim(loc, "x", 0)), 0, max(0, dcols - w))
                y = _clamp(_dim(e, "y", _dim(loc, "y", 0)), 0, max(0, drows - h))
                mx = c.setdefault("m_maxSize", {})
                mx["x"], mx["y"] = max(w, _dim(mx, "x", 0)), max(h, _dim(mx, "y", 0))
        else:
            op = e.get("op")
            eid = str(e.get("element_id", ""))
            if op == "remove":
                lst = slices.get(space)
                if isinstance(lst, list):
                    before_n = len(lst)
                    slices[space] = [x for x in lst if not (isinstance(x, dict) and str(x.get("m_elementID", "")) == eid)]
                    if len(slices[space]) < before_n:
                        by_zone.get(space, {}).pop(eid, None)
                        applied += 1
                continue
            if op == "add" and eid and space in layoutspace.FILE_ZONES:
                lst = slices.setdefault(space, [])
                w = max(1, _dim(e, "w", 4))
                h = max(1, _dim(e, "h", 2))
                x = max(0, _dim(e, "x", 16))
                y = max(0, _dim(e, "y", 0))
                slot = {
                    "m_elementID": eid,
                    "m_configDescriptions": [{"instanceID": 0}],
                    "m_configDescriptionKeys": [eid],
                    "m_gridElementConfigs": [],
                    "m_location": {"x": x, "y": y, "width": w, "height": h},
                    "m_minSize": {"x": w, "y": h},
                    "m_maxSize": {"x": w, "y": h},
                    "m_isLocked": False,
                    "m_isDebug": False,
                    "m_isDynamic": False,
                    "m_features": 0,
                    "m_expandToContent": False,
                    "m_takesFocus": False,
                    "m_isOptional": True,
                    "m_horizontalAlignment": 0,
                    "m_verticalAlignment": 0,
                }
                lst.append(slot)
                by_zone.setdefault(space, {})[eid] = slot
                applied += 1
                continue
            c = by_zone.get(space, {}).get(eid)
            if c is None:
                continue
            loc = c.setdefault("m_location", {})
            (min_w, min_h), (max_w, max_h) = cell_limits(c)
            w = max(min_w, _dim(e, "w", _dim(loc, "width", min_w)))
            h = max(min_h, _dim(e, "h", _dim(loc, "height", min_h)))
            if max_w > 0:
                w = _clamp(w, min_w, max_w)
            if max_h > 0:
                h = _clamp(h, min_h, max_h)
            zone = layoutspace.FILE_ZONES[space]
            ax, ay = layoutspace.zone_accumulator(zone, (dcols, drows), (rcols, rrows))
            ox, oy = layoutspace.slice_zone_offset(zone, (dcols, drows), ax, ay)
            # stored -> runtime -> clamped runtime -> stored
            x = _dim(e, "x", _dim(loc, "x", 0))
            y = _dim(e, "y", _dim(loc, "y", 0))
            rx = _clamp(ox + x, 0, max(0, rcols - w))
            ry = _clamp(oy + y, 0, max(0, rrows - h))
            x, y = rx - ox, ry - oy
            mx = c.setdefault("m_maxSize", {})
            mx["x"], mx["y"] = max(w, _dim(mx, "x", 0)), max(h, _dim(mx, "y", 0))
        loc["x"], loc["y"], loc["width"], loc["height"] = x, y, w, h
        applied += 1
    return applied


def _cells(obj):
    """Yield (zone, cell) for every placement in a custom composition."""
    for c in obj.get("m_gridComponents") or []:
        if isinstance(c, dict):
            yield ("m_gridComponents", c)
    for zone, entries in (obj.get("m_optionalSlices") or {}).items():
        if isinstance(entries, list):
            for c in entries:
                if isinstance(c, dict) and "m_elementID" in c:
                    yield (zone, c)


def _rect(cell):
    loc = cell.get("m_location") or {}
    return (loc.get("x"), loc.get("y"), loc.get("width"), loc.get("height"))


def validate_before_write(obj, name=None, source=None, target=None):
    """Hard structural gate plus the backend legality rules, before any write.

    Returns a list of refusal reasons; an empty list means 'write it'. The
    structural checks below are the format/file-name rules the game needs. The
    game-behaviour rules (allowed descriptions, config resolution/validity,
    placement customisability, description keys, non-empty placements, duplicate
    rectangles, locked cells and club/player/competition context) come from
    :mod:`skin_editor.layout_legality` and are structured findings: only its
    Confirmed/Empirical *blocking* findings become refusals here; its warnings
    (duplicate rectangles by Studio policy, and every Inferred/Unknown rule)
    never stop a write. Studio can get the full findings with
    :func:`legality_findings` and render the warning message itself.

    ``source`` is the optional bundle-derived context for the rules that cannot
    be checked from the JSON alone (see layout_legality.check). Without it those
    rules degrade to warnings, never blocks.
    """
    problems = []
    if name is not None:
        name = str(name)
        if not name or name in (".", "..") or Path(name).name != name or Path(name).is_absolute():
            problems.append("the file name %r is not a single safe path component" % name)
        if any(ch in name for ch in '<>:"|?*\\/'):
            problems.append("the file name %r contains a path character the game rejects" % name)
    if not isinstance(obj, dict):
        return problems + ["a custom layout must be a JSON object"]
    for key in TOP_ORDER:
        if key not in obj:
            problems.append("missing top-level key %s" % key)
    if obj.get("m_isCustom") is not True:
        problems.append("m_isCustom must be true for a custom layout")
    # LT3 C2 (Empirical) is now a legality finding (layout_legality rule
    # "grid-components-nonempty") so it carries its label and reason too.
    ids = set()
    for zone, cell in _cells(obj):
        eid = cell.get("m_elementID")
        if not isinstance(eid, str) or not eid:
            problems.append("a cell in %s has no element id" % zone)
        elif eid in ids:
            problems.append("duplicate element id %s" % eid)
        else:
            ids.add(eid)
        if any(v is None for v in _rect(cell)):
            problems.append("cell %s has no complete m_location" % eid)
        # Duplicate rectangles are NOT a refusal: LT2 C5 measured that the game
        # tolerates a duplicate and takes the first match. layout_legality emits
        # it as a Studio-policy WARNING only.
        keys = cell.get("m_configDescriptionKeys")
        if not isinstance(keys, list) or not keys or not all(isinstance(k, str) and k for k in keys):
            problems.append("cell %s has no usable m_configDescriptionKeys" % eid)
    # A tile smaller than its own m_minSize or outside the composition's grid extent is
    # written by no write path: the game crashes on such a file (2026-11-22, Squad Large).
    cols, rows = grid_extent(obj)
    for c in obj.get("m_gridComponents") or []:
        eid = c.get("m_elementID", "?")
        loc = c.get("m_location") or {}
        x, y = _dim(loc, "x", 0), _dim(loc, "y", 0)
        w, h = _dim(loc, "width", 0), _dim(loc, "height", 0)
        (min_w, min_h), (max_w, max_h) = cell_limits(c)
        if w < min_w or (max_w > 0 and w > max_w) or h < min_h or (max_h > 0 and h > max_h):
            problems.append("cell %s size %dx%d is outside its legal %dx%d .. %s" % (
                eid, w, h, min_w, min_h, ("%dx%d" % (max_w, max_h)) if max_w or max_h else "unbounded"))
        if x < 0 or y < 0 or x + w > cols or y + h > rows:
            problems.append("cell %s at %d,%d %dx%d is outside the composition's %dx%d grid" % (eid, x, y, w, h, cols, rows))
    # UI4: overlap is judged PER SPACE - main cells in design space, and slots inside
    # their own zone in slot space. Never across spaces. A PARTIAL overlap is blocked;
    # an exact duplicate stays the LT2 C5 warning (the game takes the first match).
    from . import layoutspace
    def _entries(rows):
        return [{"element_id": e.get("m_elementID", "?"),
                 "x": _dim(e.get("m_location"), "x", 0), "y": _dim(e.get("m_location"), "y", 0),
                 "width": _dim(e.get("m_location"), "width", 0), "height": _dim(e.get("m_location"), "height", 0)}
                for e in rows or []]
    spaces = [("main", obj.get("m_gridComponents") or [])]
    slices = obj.get("m_optionalSlices") or {}
    spaces += [(zone, slices.get(zone) or []) for zone in layoutspace.FILE_ZONES]
    for space_name, rows in spaces:
        for a, b, ra, rb in layoutspace.overlaps(_entries(rows)):
            if ra == rb:
                continue                                        # exact duplicate: warn only (LT2 C5)
            problems.append("%s: cell %s %s overlaps cell %s %s"
                            % ("design" if space_name == "main" else space_name, a, ra, b, rb))
    try:
        raw = dumps(obj)
    except (TypeError, ValueError) as exc:
        problems.append("the object is not JSON serialisable: %s" % exc)
    else:
        if raw.startswith(b"\xef\xbb\xbf") or b"\n" in raw or b"\r" in raw:
            problems.append("the serialised layout is not the game's single-line UTF-8 form")
    # Backend legality: block on the Confirmed/Empirical rules, warn on the rest.
    from . import layout_legality
    problems += layout_legality.reasons(layout_legality.blocking(layout_legality.check(obj, name, source, target)))
    return problems


def legality_findings(obj, name=None, source=None, target=None):
    """Companion to :func:`validate_before_write`: the full structured findings.

    Studio uses this in the inspector to render the block/warn messages; the
    write path uses ``validate_before_write``, which refuses only the blocking
    ones. Warnings here (duplicate rectangles, locked cells, context, and any
    source-driven rule that could not be verified offline) never block a write.
    """
    from . import layout_legality
    return layout_legality.check(obj, name, source, target)


def write(path, obj, source=None, target=None):
    """Write a custom-layout file, refusing anything the game or the proven files reject.

    ``source``/``target`` are the optional bundle context and operation target for
    the legality rules; with no source the rules that need the bundle warn instead
    of blocking (see validate_before_write).
    """
    problems = validate_before_write(obj, Path(path).name, source, target)
    if problems:
        raise ValueError("custom layout refused: " + "; ".join(problems))
    Path(path).write_bytes(dumps(obj))


def write_raw(path, data, source=None, target=None):
    """Write pre-serialised bytes (LT1 C5/C6): prove they are JSON and pass the checks first.

    LT1 showed that a raw write can bypass validate_before_write and that truncated
    JSON blocks the game's UI. Both are refused here before any byte is written.
    ``source``/``target`` pass through to the same legality checks as :func:`write`;
    this is not a new write path, it is the same guarded one.
    """
    try:
        obj = loads(data)
    except Exception as exc:
        raise ValueError("custom layout refused: the bytes are not valid JSON: %s" % exc)
    problems = validate_before_write(obj, Path(path).name, source, target)
    if problems:
        raise ValueError("custom layout refused: " + "; ".join(problems))
    Path(path).write_bytes(data)


# ---------------------------------------------------------------- generate from a bundle composition
def _conv(v, key=None):
    """A bundle typetree value in the game's JSON form: references become {instanceID: 0} (see the policy), 0/1 flags become booleans."""
    if isinstance(v, dict):
        if set(v) == PPTR:
            return OrderedDict([("instanceID", 0)])
        return OrderedDict((k, _conv(x, k)) for k, x in v.items())
    if isinstance(v, list):
        return [_conv(x, key) for x in v]
    if key in BOOL_KEYS:
        return bool(v)
    return v


def description_name(objs, pptr):
    """The tile description's ID (the name the game keys it by), read from the bundle object a reference points at; None when it is not in `objs`."""
    o = objs.get(int(pptr["m_PathID"])) if isinstance(pptr, dict) else None
    if o is None:
        return None
    t = o.read_typetree()
    return t.get("<ID>k__BackingField") or t.get("<Name>k__BackingField") or t.get("m_Name")


def _cell(tt, objs):
    c = _conv(tt)
    c["m_configDescriptionKeys"] = [n for n in (description_name(objs, p) for p in tt.get("m_configDescriptions") or []) if n is not None]
    return c


def generate(comp_tt, objs, real=None):
    """A custom file (OrderedDict) from a bundle composition typetree. `objs` {path_id: unitypy object} resolves the description names.
    `real` (an existing custom file of the SAME composition) supplies instance ids for cells that match (element id and keys), and the three
    top-level references; everything else gets 0."""
    out = OrderedDict()
    for k in TOP_ORDER:
        if k == "m_isCustom":
            out[k] = True
        elif k == "m_gridComponents":
            out[k] = [_cell(c, objs) for c in comp_tt[k]]
        elif k == "m_optionalSlices":
            sl = _conv(comp_tt[k])
            for region, items in comp_tt[k].items():                      # optional slice entries are cells too: fill their name keys
                if isinstance(items, list) and items and isinstance(items[0], dict) and "m_elementID" in items[0]:
                    sl[region] = [_cell(c, objs) for c in items]
            out[k] = sl
        elif k in comp_tt:
            out[k] = _conv(comp_tt[k], k)
        else:
            out[k] = OrderedDict([("instanceID", 0)]) if k in ("m_editorValidator",) else None
    if real:
        inherit_ids(out, real)
    return out


def inherit_ids(out, real):
    """The instance-id policy: take the three top-level references and, for every cell whose element id AND name keys match a cell of the real file, its
    description references from the real file. Everything else stays as generated (0)."""
    for k in ("m_gridElementSet", "m_validator", "m_editorValidator"):
        if k in real:
            out[k] = copy.deepcopy(real[k])
    by_id = {c["m_elementID"]: c for c in real["m_gridComponents"]}
    for c in out["m_gridComponents"]:
        r = by_id.get(c["m_elementID"])
        if r is not None and r.get("m_configDescriptionKeys") == c["m_configDescriptionKeys"]:
            c["m_configDescriptions"] = copy.deepcopy(r["m_configDescriptions"])
            for mine, theirs in zip(c["m_gridElementConfigs"], r["m_gridElementConfigs"]):
                mine["Description"] = copy.deepcopy(theirs["Description"])
    return out


def load_composition(bundle_path, name):
    """(typetree, {path_id: object}) of the composition `name` in a bundle."""
    import UnityPy
    env = UnityPy.load(str(bundle_path))
    objs = {o.path_id: o for o in env.objects}
    for o in env.objects:
        if o.type.name == "MonoBehaviour":
            try:
                t = o.read_typetree()
            except Exception:
                continue
            if isinstance(t, dict) and t.get("m_Name") == name and "m_gridComponents" in t:
                return t, objs
    raise KeyError("no composition %r in %s" % (name, bundle_path))


def description_cell(bundle_paths, name, size, prefer=None):
    """A cell source for a swap BY NAME: the tile description whose ID or object name (m_Name, e.g. SquadHappinessTileDescription) is `name` (the one in the bundle `prefer` first), its configuration of `size` (x, y),
    and the name key. Instance ids are 0 (policy)."""
    import UnityPy
    order = sorted(bundle_paths, key=lambda p: (Path(p).name != prefer, str(p)))
    for b in order:
        for o in UnityPy.load(str(b)).objects:
            if o.type.name != "MonoBehaviour":
                continue
            try:
                t = o.read_typetree()
            except Exception:
                continue
            if isinstance(t, dict) and name in (t.get("<ID>k__BackingField"), t.get("m_Name")) and t.get("<Configurations>k__BackingField"):
                cfgs = [c for c in t["<Configurations>k__BackingField"] if (c["Size"]["x"], c["Size"]["y"]) == tuple(size)]
                if cfgs:
                    key = t.get("<ID>k__BackingField") or name
                    return OrderedDict([("m_elementID", key), ("m_configDescriptions", [OrderedDict([("instanceID", 0)])]),
                                        ("m_configDescriptionKeys", [key]), ("m_gridElementConfigs", [_conv(cfgs[0])])])
    raise KeyError("no tile description %r with a %sx%s configuration" % (name, size[0], size[1]))


def description_cell_by_ref(objs, path_id, config_index):
    """A cell source from a description reference (an operation's {path_id, config_index}): the tile's name key and that configuration. Instance ids are 0 (policy)."""
    o = objs.get(int(path_id))
    if o is None:
        raise KeyError("the description (path id %s) is not in this bundle" % path_id)
    t = o.read_typetree()
    cfgs = t.get("<Configurations>k__BackingField") or []
    if not 0 <= int(config_index) < len(cfgs):
        raise KeyError("the description %s has %d configuration(s); index %s does not exist" % (t.get("m_Name"), len(cfgs), config_index))
    key = t.get("<ID>k__BackingField") or t.get("<Name>k__BackingField") or t.get("m_Name")
    return OrderedDict([("m_elementID", key), ("m_configDescriptions", [OrderedDict([("instanceID", 0)])]), ("m_configDescriptionKeys", [key]),
                        ("m_gridElementConfigs", [_conv(cfgs[int(config_index)])])])


def tile_set(comp_tt, objs):
    """The tiles available in the composition's OWN tile set (its m_gridElementSet): [{id, object, sizes: [[x, y], ...]}], sorted by id. A swap by name may only use one of these."""
    ref = comp_tt.get("m_gridElementSet") or {}
    o = objs.get(int(ref.get("m_PathID", 0)))
    if o is None:
        return []
    out = []
    for p in o.read_typetree().get("m_gridElementDescriptions") or []:
        d = objs.get(int(p["m_PathID"]))
        if d is None:
            continue
        t = d.read_typetree()
        cfgs = t.get("<Configurations>k__BackingField") or []
        out.append({"id": t.get("<ID>k__BackingField") or t.get("m_Name"), "object": t.get("m_Name"),
                    "sizes": sorted({(c["Size"]["x"], c["Size"]["y"]) for c in cfgs})})
    return sorted(({"id": e["id"], "object": e["object"], "sizes": [list(z) for z in e["sizes"]]} for e in out), key=lambda e: (str(e["id"]), str(e["object"])))


def description_cell_in_set(comp_tt, objs, name, size):
    """A swap source from the composition's OWN tile set only: the description whose ID or object name is `name`, its configuration of `size`. KeyError when the set has no such tile."""
    ref = comp_tt.get("m_gridElementSet") or {}
    o = objs.get(int(ref.get("m_PathID", 0)))
    if o is None:
        raise KeyError("the composition has no tile set in this bundle")
    for p in o.read_typetree().get("m_gridElementDescriptions") or []:
        d = objs.get(int(p["m_PathID"]))
        if d is None:
            continue
        t = d.read_typetree()
        if name in (t.get("<ID>k__BackingField"), t.get("m_Name")):
            for i, c in enumerate(t.get("<Configurations>k__BackingField") or []):
                if (c["Size"]["x"], c["Size"]["y"]) == tuple(size):
                    return description_cell_by_ref(objs, p["m_PathID"], i)
    raise KeyError("the tile set has no tile %r with a %sx%s configuration" % (name, size[0], size[1]))


# ---------------------------------------------------------------- operations (each changes only its own fields)
def _cell_of(obj, element_id):
    cells = [c for c in obj["m_gridComponents"] if c["m_elementID"] == element_id]
    if len(cells) != 1:
        raise KeyError("%d cells with element id %r" % (len(cells), element_id))
    return cells[0]


def set_max_size(obj, element_id, x, y):
    c = _cell_of(obj, element_id)
    c["m_maxSize"]["x"], c["m_maxSize"]["y"] = int(x), int(y)
    return obj


def set_location(obj, element_id, x, y, w, h):
    loc = _cell_of(obj, element_id)["m_location"]
    loc["x"], loc["y"], loc["width"], loc["height"] = int(x), int(y), int(w), int(h)
    return obj


def swap_cell(obj, element_id, source):
    """Replace the tile of the cell `element_id` by the tile of `source` (a cell in the game's JSON form, e.g. from description_cell or from generate): its element
    id, description references, name keys and configurations. The slot (location, min and max size, flags) stays."""
    c = _cell_of(obj, element_id)
    for k in ("m_elementID", "m_configDescriptions", "m_configDescriptionKeys", "m_gridElementConfigs"):
        c[k] = copy.deepcopy(source[k])
    return obj


# ---------------------------------------------------------------- structural operations (JX)
def _flat_ids(obj):
    """The flat element list m_instantiationOrder indexes: grid cells first, then every optional region in its stored order."""
    ids = [c["m_elementID"] for c in obj["m_gridComponents"]]
    for reg, items in obj["m_optionalSlices"].items():
        if reg != "m_instantiationOrder" and isinstance(items, list):
            ids += [e["m_elementID"] for e in items]
    return ids


def _reindex(obj, before_ids):
    """Keep m_instantiationOrder consistent after cells or slices were added or removed: the same elements in the same order under their new flat index, new elements last."""
    order = obj["m_optionalSlices"]["m_instantiationOrder"]
    kept = [before_ids[i] for i in order if i < len(before_ids)]
    after = _flat_ids(obj)
    new = [after.index(e) for e in kept if e in after]
    new += [i for i, e in enumerate(after) if e not in before_ids]
    obj["m_optionalSlices"]["m_instantiationOrder"] = new
    return obj


def add_cell(obj, element_id, source, location):
    """Add a grid component: a copy of the first static cell's shape with the tile of `source` (a cell from description_cell), the location (x, y, w, h), min and max size equal to
    the configuration's size, flags zero; plus its placement binding and name keys. The element id must be new."""
    if element_id in _flat_ids(obj) or any(b["m_elementID"] == element_id for b in obj["m_placementBindings"]):
        raise KeyError("element id %r is already used in this composition" % element_id)
    before = _flat_ids(obj)
    template = next((c for c in obj["m_gridComponents"] if not c["m_isDynamic"]), obj["m_gridComponents"][0])
    cell = copy.deepcopy(template)
    cfg = copy.deepcopy(source["m_gridElementConfigs"][0])
    x, y, w, h = location
    if (cfg["Size"]["x"], cfg["Size"]["y"]) != (w, h):
        raise ValueError("an added cell must use its configuration's own size %sx%s" % (cfg["Size"]["x"], cfg["Size"]["y"]))
    cell["m_elementID"] = element_id
    cell["m_configDescriptions"] = copy.deepcopy(source["m_configDescriptions"])
    cell["m_configDescriptionKeys"] = list(source["m_configDescriptionKeys"])
    cell["m_gridElementConfigs"] = [cfg]
    cell["m_location"] = OrderedDict([("x", x), ("y", y), ("width", w), ("height", h)])
    cell["m_minSize"] = OrderedDict([("x", w), ("y", h)])
    cell["m_maxSize"] = OrderedDict([("x", w), ("y", h)])
    for k in ("m_isLocked", "m_isDebug", "m_isDynamic", "m_expandToContent", "m_takesFocus", "m_isOptional"):
        cell[k] = False
    cell["m_features"] = 0
    cell["m_horizontalAlignment"] = cell["m_verticalAlignment"] = 0
    obj["m_gridComponents"].append(cell)
    obj["m_placementBindings"].append(OrderedDict([("m_elementID", element_id), ("m_optionalConditions", []), ("m_optionalConfigConditions", [])]))
    return _reindex(obj, before)


def set_slots(obj, region, slots):
    """Write m_optionalSlices[region] as `slots`, a list of (element id, source cell, (x, y) offset). An element already in the region keeps its entry (only its offset is
    set); a new one is a copy of the region's first entry with the source tile, the configuration's size and the offset. m_instantiationOrder is re-indexed."""
    before = _flat_ids(obj)
    cur = obj["m_optionalSlices"][region]
    by_id = {e["m_elementID"]: e for e in cur}
    template = cur[0] if cur else None
    out = []
    for element_id, source, (x, y) in slots:
        if element_id in by_id:
            e = copy.deepcopy(by_id[element_id])
            e["m_location"]["x"], e["m_location"]["y"] = x, y
        else:
            if element_id in before or any(b["m_elementID"] == element_id for b in obj["m_placementBindings"]):
                raise KeyError("element id %r is already used in this composition" % element_id)
            if template is None:
                raise ValueError("the region %s has no entry to take the shape from" % region)
            e = copy.deepcopy(template)
            cfg = copy.deepcopy(source["m_gridElementConfigs"][0])
            w, h = cfg["Size"]["x"], cfg["Size"]["y"]
            e["m_elementID"] = element_id
            e["m_configDescriptions"] = copy.deepcopy(source["m_configDescriptions"])
            e["m_configDescriptionKeys"] = list(source["m_configDescriptionKeys"])
            e["m_gridElementConfigs"] = [cfg]
            e["m_location"] = OrderedDict([("x", x), ("y", y), ("width", w), ("height", h)])
            e["m_minSize"] = OrderedDict([("x", w), ("y", h)])
            e["m_maxSize"] = OrderedDict([("x", w), ("y", h)])
        out.append(e)
    obj["m_optionalSlices"][region] = out
    return _reindex(obj, before)


# ---------------------------------------------------------------- back up and restore
def snapshot(fold):
    return {p.name: sha256(p) for p in sorted(Path(fold).iterdir()) if p.is_file()} if Path(fold).is_dir() else {}


def backup(fold, root):
    """Copy the whole folder to <root>/backup-<timestamp>/ and verify; returns (path, {file: sha256})."""
    dest = Path(root) / ("backup-" + datetime.datetime.now().strftime("%Y%m%dT%H%M%S"))
    shutil.copytree(fold, dest)
    hashes = snapshot(fold)
    if snapshot(dest) != hashes:
        raise RuntimeError("the backup does not match the folder")
    return dest, hashes


def restore(fold, dest, hashes):
    """Put the folder back exactly as backed up (files the run added are moved into <dest>/extra-after-run, never deleted) and verify every sha256."""
    fold = Path(fold)
    extras = []
    for p in sorted(fold.iterdir()):
        if p.is_file() and p.name not in hashes:
            aside = Path(dest) / "extra-after-run"
            aside.mkdir(exist_ok=True)
            shutil.move(str(p), str(aside / p.name))
            extras.append(p.name)
    for name in hashes:
        t = fold / name
        if not t.is_file() or sha256(t) != hashes[name]:
            shutil.copy2(Path(dest) / name, t)
    now = snapshot(fold)
    return {"restored_equals_backup": now == hashes, "files": now, "extra_files_moved_aside": extras}
