"""Backend legality checks for a custom-layout write (SwapTile / AddCell).

Pure and offline: no game access, no writes, no bundle loading. ``check(obj, name,
source)`` returns *structured findings* so the inspector can show a plain-language
reason and decide what to do with it::

    {"rule": "config-for-size", "label": "Confirmed", "severity": "block",
     "reason": "...", "rva": "layout-rule", "cell": "Happiness"}

Labels follow the REA convention used across ``layout-model-spec``:

* **Confirmed** - directly visible in the cited game code / serialized file.
* **Empirical** - measured in a real game run or a proven custom file.
* **Inferred** - a strong structural reading where a decisive helper is unnamed.
* **Unknown** - the evidence cannot settle it.

Gate policy (Studio owns the messages, this module owns the severity):

* A finding is **blocking** only when its label is Confirmed or Empirical *and*
  its rule is marked ``block``. Inferred / Unknown rules are always ``warn``.
* Two Confirmed/Empirical rules are deliberately warn-only by policy: the
  duplicate-rectangle rule (LT2 C5 - the game tolerates a duplicate and takes the
  first match) and the unverifiable forms of the source-driven rules (see below).
* A rule checked from JSON alone can block; a rule that needs bundle data and is
  called without ``source`` degrades to an **Unknown warning**, never a block.

``source`` is an optional dict describing the composition the write targets::

    {
      "allowed_descriptions": ["Happiness", ...],   # GetAllowedDescriptions (layout-rule)
      "resolvable_keys":      ["Happiness", ...],   # ResolvePlacements (layout-rule) / TryGetDescription
      "config_sizes":         {"Happiness": [[2, 2], ...]},  # GetConfig/ResolveConfig
      "invalid_configs":      [("Happiness", 2, 2), ...],    # IsConfigValidForCustomisation (layout-rule)
    }

Each key is optional; absent data makes the corresponding check unverifiable and
produces a warning rather than a guess.
"""
from collections import Counter

CONFIRMED, EMPIRICAL, INFERRED, UNKNOWN = "Confirmed", "Empirical", "Inferred", "Unknown"
BLOCK_LABELS = (CONFIRMED, EMPIRICAL)
BLOCK, WARN = "block", "warn"

# rule id -> (default label, default severity, evidence address, short title)
RULES = {
    "allowed-descriptions":       (CONFIRMED, BLOCK, "layout-rule", "allowed description list"),
    "config-for-size":            (CONFIRMED, BLOCK, "layout-rule", "configuration for the cell size"),
    "config-valid-for-customisation": (CONFIRMED, BLOCK, "layout-rule", "config valid for customisation"),
    "placement-customisable":     (CONFIRMED, BLOCK, "layout-rule", "placement customisable"),
    "description-key-resolution": (CONFIRMED, BLOCK, "layout-rule", "description-key resolution"),
    "grid-components-nonempty":   (EMPIRICAL, BLOCK, "LT3 C2", "non-empty m_gridComponents"),
    "duplicate-rectangle":        (EMPIRICAL, WARN, "LT2 C5", "duplicate rectangle"),
    "locked-cell":                (INFERRED, WARN, "R12", "locked cell"),
    "club-player-competition-context": (UNKNOWN, WARN, "R13", "club/player/competition context"),
}


def _finding(rule, reason, label=None, severity=None, **extra):
    """Build one finding; the rule registry supplies the default label/severity/rva."""
    dlabel, dsev, rva, _title = RULES[rule]
    label = label or dlabel
    severity = severity or dsev
    # an Inferred or Unknown finding can never be a block, whatever the caller asks for
    if label in (INFERRED, UNKNOWN):
        severity = WARN
    out = {"rule": rule, "label": label, "severity": severity, "reason": reason, "rva": rva}
    out.update(extra)
    return out


def _cells(obj):
    """(zone, cell) for every placement in a custom composition (mirrors custom_layouts._cells)."""
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


def _key(cell):
    k = cell.get("m_elementID")
    keys = cell.get("m_configDescriptionKeys") or []
    return (str(k) if k is not None else "?", ",".join(str(x) for x in keys))


def _config(cell):
    cfgs = cell.get("m_gridElementConfigs") or []
    return cfgs[0] if cfgs and isinstance(cfgs[0], dict) else None


def _size(obj):
    if not isinstance(obj, dict):
        return None
    s = obj.get("Size") or obj.get("m_size") or {}
    x, y = s.get("x"), s.get("y")
    return (x, y) if isinstance(x, int) and isinstance(y, int) else None


def _source_has(source, field):
    """True when `source` actually supplies this field (an empty iterable is still 'supplied')."""
    return isinstance(source, dict) and field in source and source[field] is not None


def _as_set(value):
    if isinstance(value, str):
        return {value}
    if isinstance(value, (set, frozenset, list, tuple)):
        return set(value)
    return set()


def check(obj, name=None, source=None, target=None):
    """Legality findings for the *result* of a SwapTile / AddCell, before it is written.

    ``obj`` is the custom-layout object (OrderedDict from custom_layouts.loads).
    ``name`` is the target file name (accepted for API symmetry; findings are about
    the object, so no reason currently depends on it).
    ``source`` is the optional bundle-derived context described in this module's docstring.
    ``target`` is the element id (or a collection of them) actually being swapped or
    added. It scopes the ``placement-customisable`` rule: a game file can legitimately
    hold a multi-description cell (an owner file has one with three), and the game's
    ``IsPlacementCustomisable`` only decides whether the *edited* cell can be
    customised. With no target the rule is a warning; on a targeted cell it blocks.

    Returns a list of finding dicts. An empty list means no problem was found *and*
    every rule was verifiable; warnings are returned too and Studio may show them.
    """
    out = []
    targets = _as_set(target) if target is not None else set()
    if not isinstance(obj, dict):
        return out                                  # structural refusal is validate_before_write's job

    # 6 (Empirical, block) - LT3 C2: an empty top-level placement list loses the cells.
    grid = obj.get("m_gridComponents")
    if not isinstance(grid, list) or not grid:
        out.append(_finding("grid-components-nonempty",
                            "This layout has no placements. The game does not fall back to the bundle's "
                            "layout when the custom file's m_gridComponents is empty: it simply shows no "
                            "cells (LT3 C2), so a file with no placements must not be written."))

    cells = list(_cells(obj))

    # source-driven checks: a rule we cannot evaluate is an Unknown warning, never a block.
    allowed = resolvable = None
    if _source_has(source, "allowed_descriptions"):
        allowed = _as_set(source["allowed_descriptions"])
    else:
        out.append(_finding("allowed-descriptions",
                            "Cannot verify the allowed tile list offline: the game filters tile "
                            "descriptions through GetAllowedDescriptions using this screen's allowed tags "
                            "and validator (layout-rule). Pass the composition's allowed descriptions as "
                            "source to check it; until then this is a warning, not a block.",
                            label=UNKNOWN))
    if _source_has(source, "resolvable_keys"):
        resolvable = _as_set(source["resolvable_keys"])
    elif allowed is not None:
        resolvable = set(allowed)                   # allowed descriptions are a reasonable resolver proxy
    else:
        out.append(_finding("description-key-resolution",
                            "Cannot verify description keys offline: the game resolves m_configDescriptionKeys "
                            "through ResolvePlacements / TryGetDescription (layout-rule). An unknown key does "
                            "not error - it makes the game pick a different tile (LT3 C1). Pass the "
                            "resolvable keys as source to check it; until then this is a warning, not a block.",
                            label=UNKNOWN))
    invalid = None
    if _source_has(source, "invalid_configs"):
        invalid = {(tuple(row[:3])) for row in source["invalid_configs"] if isinstance(row, (list, tuple)) and len(row) >= 3}
    else:
        out.append(_finding("config-valid-for-customisation",
                            "Cannot verify IsConfigValidForCustomisation offline (layout-rule): the game rejects "
                            "a configuration whose flag at +0x30 is 1 and applies a runtime validator whose "
                            "meaning is only Inferred. Pass the configurations the game rejects as source to "
                            "check it; until then this is a warning, not a block.",
                            label=UNKNOWN))
    sizes = None
    if _source_has(source, "config_sizes"):
        sizes = source["config_sizes"]
    else:
        out.append(_finding("config-for-size",
                            "Cannot verify configuration-for-size offline: the game resolves a tile's "
                            "configuration for the cell's size with GetConfig (layout-rule) / ResolveConfig "
                            "(layout-rule). The configuration embedded in the JSON is the tile's own config and "
                            "need not match a cell that was moved or resized (the proven X1 move file has a "
                            "4x2 config on a 4x4 cell), so do not refuse on that basis. Pass the tile set's "
                            "available sizes as source to check this rule; until then it is a warning.",
                            label=UNKNOWN))

    for zone, cell in cells:
        eid, keyname = _key(cell)
        cfg = _config(cell)
        cw, ch = (_rect(cell)[2], _rect(cell)[3])
        where = "%s in %s" % (eid, zone) if zone != "m_gridComponents" else eid

        # 4 (Confirmed, block) - IsPlacementCustomisable: at most one description reference.
        descs = cell.get("m_configDescriptions")
        ndesc = len(descs) if isinstance(descs, list) else (0 if descs is None else 1)
        if ndesc > 1:
            # A real game file may hold a multi-description cell (an owner file has one with
            # three); the game's check asks whether the cell being *edited* is customisable.
            # Block only when this cell is the SwapTile/AddCell target, warn otherwise.
            targeted = eid in targets
            out.append(_finding("placement-customisable",
                                "Cell %s carries %d description references; the game only customises a cell "
                                "with at most one (IsPlacementCustomisable, layout-rule). Keep a single "
                                "description on the tile you swap or add." % (where, ndesc),
                                severity=BLOCK if targeted else WARN,
                                cell=eid, count=ndesc, targeted=targeted))

        # 2 (Confirmed, block) - GetConfig / ResolveConfig: a config for the cell's size.
        # The embedded config's own Size may differ from a moved/resized cell (proven X1),
        # so only a missing config (offline) or an unavailable size in the tile set (source) is a block.
        csize = _size(cfg)
        # Optional-slice entries are slot references: the game resolves their config from the
        # source composition's placement, so an empty m_gridElementConfigs is normal there.
        if cfg is None and zone == "m_gridComponents":
            out.append(_finding("config-for-size",
                                "Cell %s has no usable tile configuration, so the game cannot resolve a "
                                "configuration for its size (GetConfig layout-rule / ResolveConfig layout-rule)." % where,
                                cell=eid))
        elif isinstance(sizes, dict) and keyname in sizes:
            known = {tuple(v) for v in (sizes[keyname] or []) if isinstance(v, (list, tuple)) and len(v) >= 2}
            if known and (cw, ch) not in known:
                out.append(_finding("config-for-size",
                                    "Cell %s is %sx%s but tile %s has no configuration of that size in the "
                                    "composition's tile set (GetConfig layout-rule / ResolveConfig layout-rule)." %
                                    (where, cw, ch, keyname), cell=eid))

        # 1 (Confirmed, block) - GetAllowedDescriptions: the tile must be allowed on this screen.
        if allowed is not None:
            keys = [str(k) for k in (cell.get("m_configDescriptionKeys") or []) if k]
            for k in keys:
                if k not in allowed:
                    out.append(_finding("allowed-descriptions",
                                        "Tile '%s' on %s is not in this screen's allowed description list. "
                                        "The game builds that list with GetAllowedDescriptions (layout-rule) "
                                        "from the element set and allowed tags, so this tile will not be "
                                        "offered." % (k, where), cell=eid, key=k))

        # 5 (Confirmed, block; LT3 C1 Empirical outcome) - description-key resolution.
        if resolvable is not None:
            keys = [str(k) for k in (cell.get("m_configDescriptionKeys") or []) if k]
            for k in keys:
                if k not in resolvable:
                    out.append(_finding("description-key-resolution",
                                        "Description key '%s' on %s cannot be resolved in this screen's tile "
                                        "set (ResolvePlacements layout-rule / TryGetDescription). The game does "
                                        "not report an unknown key - it silently picks a different tile, which "
                                        "is what LT3 C1 measured." % (k, where), cell=eid, key=k,
                                        evidence="LT3 C1 Empirical"))

        # 3 (Confirmed, block) - IsConfigValidForCustomisation, when source supplies the flag.
        if invalid is not None and csize is not None and (keyname, csize[0], csize[1]) in invalid:
            out.append(_finding("config-valid-for-customisation",
                                "The %sx%s configuration of %s is one the game rejects as non-customisable "
                                "(IsConfigValidForCustomisation, layout-rule: the flag at +0x30 is 1 or the "
                                "runtime validator rejects it). Choose a different tile or size." %
                                (csize[0], csize[1], where), cell=eid))

        # 8 (Inferred, warn only) - a locked cell may not be swappable; enforcement is unverified.
        if cell.get("m_isLocked") is True:
            out.append(_finding("locked-cell",
                                "Cell %s is locked (m_isLocked). Enforcement is unverified: check the "
                                "screen in the game before relying on it." % where, cell=eid))

    # 7 (Empirical, warn only by Studio policy) - duplicate rectangles.
    rects = Counter((zone,) + tuple(_rect(cell)) for zone, cell in cells if not any(v is None for v in _rect(cell)))
    for (zone, x, y, w, h), n in sorted(rects.items(), key=lambda kv: str(kv[0])):
        if n > 1:
            out.append(_finding("duplicate-rectangle",
                                "%d cells in %s share the rectangle (%s, %s, %s, %s). The game tolerates a "
                                "duplicate and resolves by first match (LT2 C5), so this is not a game rule: "
                                "Studio warns because the later cell's tile can be lost." % (n, zone, x, y, w, h),
                                zone=zone, rect=[x, y, w, h], count=n))

    # 9 (Unknown, warn only) - club/player/competition context cannot be read from the file.
    if not isinstance(source, dict) or source.get("context_verified") is not True:
        out.append(_finding("club-player-competition-context",
                            "Whether this tile is available in the current club / player / competition "
                            "context cannot be determined from the layout file alone: the game evaluates "
                            "scoped bindings at runtime and no static rule covers it. Verify in the game; "
                            "this is never a write block."))

    return out


def blocking(findings):
    """Findings that must prevent the write (Confirmed/Empirical rules marked 'block')."""
    return [f for f in findings if f.get("severity") == BLOCK and f.get("label") in BLOCK_LABELS]


def warnings(findings):
    """Findings Studio may show but must not prevent the write."""
    return [f for f in findings if f.get("severity") == WARN]


def should_block(findings):
    return bool(blocking(findings))


def reasons(findings, severity=None):
    """Plain-language reason strings, for the existing ValueError gate and Studio messages."""
    chosen = findings if severity is None else [f for f in findings if f.get("severity") == severity]
    return [f["reason"] for f in chosen]


def summary(findings):
    """{label: count} over all findings, handy for a report/UI badge."""
    return dict(Counter(f.get("label") for f in findings))
