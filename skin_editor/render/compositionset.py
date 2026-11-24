"""Composition sets and compositions read from their SERIALIZED assets, across every UI bundle.

Identification is by TYPE SIGNATURE, never by name or bundle name:
  - a composition set is a MonoBehaviour with m_gridBreakpointCompositionData
  - a composition is a MonoBehaviour with m_gridComponents
Both are looked for in every `ui-*.bundle` of the layout folder, and the result is cached per folder.

The serialized shape (verified on builds B and C):

    m_gridBreakpointCompositionData = {
        "m_values": [ {"m_key": <breakpoint int>, "m_value": [ ppPtr, ... ]}, ... ],
        "m_keys": [ ... ]        # incomplete; m_values is authoritative
    }

`survey()` reports the per-bundle counts and compares them with the layout dump: compositions by name, and the
set names the dump's tiles rows carry. Anything found in one source but not the other is named (G22).

The layout dump remains only a cross-check; the preview reads the serialized asset.
"""
import json
from pathlib import Path

CACHE = {}
UI_BUNDLE_GLOB = "ui-*.bundle"


def parse(tree):
    """The set's breakpoint -> [composition refs] mapping, straight from the serialized field."""
    data = tree.get("m_gridBreakpointCompositionData") or {}
    out = {}
    for entry in data.get("m_values") or []:
        key = entry.get("m_key")
        refs = []
        for ref in entry.get("m_value") or []:
            if not isinstance(ref, dict):
                continue
            refs.append({"file_id": ref.get("m_FileID"), "path_id": str(ref.get("m_PathID"))})
        if isinstance(key, int):
            out[key] = refs
    return out


def _resolve_refs(objs, refs):
    out = []
    for ref in refs:
        rec = dict(ref)
        rec["name"], rec["has_grid_components"] = None, False
        pid = int(ref["path_id"]) if ref.get("path_id") not in (None, "") else None
        if ref.get("file_id") in (0, None) and pid is not None and pid in objs:
            try:
                t = objs[pid].read_typetree()
            except Exception:
                t = None
            if isinstance(t, dict):
                rec["name"] = t.get("m_Name")
                rec["has_grid_components"] = "m_gridComponents" in t
        out.append(rec)
    return out


def scan(layouts, check=None):
    """Scan every UI bundle by type signature. Returns (sets, compositions, stats).

    sets:         {set_name: {bundle, path_id, breakpoints: {key: [refs]}}}
    compositions: {composition_name: {bundle, path_id}}
    stats:        per bundle, how many sets and compositions were found.
    `check`, when given, is called once per bundle: a cancellable caller raises from it to stop.
    """
    folder = str(getattr(layouts, "folder", layouts))
    base = Path(folder)
    sets, comps, stats = {}, {}, {}
    for path in sorted(base.glob(UI_BUNDLE_GLOB)):
        if check is not None:
            check()
        try:
            objs = layouts._bundle_objs(path.name)
        except Exception:
            stats[path.name] = {"sets": 0, "compositions": 0, "read": False}
            continue
        n_sets = n_comps = 0
        for pid, obj in list(objs.items()):
            try:
                if obj.type.name != "MonoBehaviour":
                    continue
                t = obj.read_typetree()
            except Exception:
                continue
            if not isinstance(t, dict):
                continue
            name = t.get("m_Name")
            if "m_gridBreakpointCompositionData" in t:
                n_sets += 1
                key = name or "%s:%s" % (path.name, pid)
                if key not in sets:
                    raw = parse(t)
                    sets[key] = {"bundle": path.name, "path_id": str(pid),
                                 "breakpoints": {k: _resolve_refs(objs, v) for k, v in raw.items()}}
            if "m_gridComponents" in t:
                n_comps += 1
                if name and name not in comps:
                    comps[name] = {"bundle": path.name, "path_id": str(pid)}
        stats[path.name] = {"sets": n_sets, "compositions": n_comps, "read": True}
    return sets, comps, stats


def index(layouts):
    """Every composition set in the UI bundles ({set_name: record}), cached per folder. A set is identified by
    its serialized field; the name is only the lookup label."""
    folder = str(getattr(layouts, "folder", layouts))
    if folder not in CACHE:
        sets, comps, stats = scan(layouts)
        CACHE[folder] = {"sets": sets, "compositions": comps, "stats": stats}
    return CACHE[folder]["sets"]


def index_full(layouts):
    folder = str(getattr(layouts, "folder", layouts))
    if folder not in CACHE:
        sets, comps, stats = scan(layouts)
        CACHE[folder] = {"sets": sets, "compositions": comps, "stats": stats}
    return CACHE[folder]


def composition(layouts, bundle, path_id):
    """One composition's serialized typetree, or None (never fabricated)."""
    try:
        objs = layouts._bundle_objs(bundle)
        obj = objs.get(int(path_id))
        if obj is None:
            return None
        t = obj.read_typetree()
        return t if isinstance(t, dict) else None
    except Exception:
        return None


def find(indexed, family):
    """The set the preview should read: `family` as a set name, else the set that holds a composition of
    that name. Returns (set_name, set_record) or (None, None)."""
    if not indexed:
        return None, None
    if family in indexed:
        return family, indexed[family]
    hits = [name for name, rec in indexed.items()
            if any(c.get("name") == family for refs in rec["breakpoints"].values() for c in refs)]
    if hits:
        hits.sort(key=lambda n: (len(n), n))
        return hits[0], indexed[hits[0]]
    return None, None


def survey(layouts, dump):
    """The per-bundle counts plus the comparison with the layout dump. Names everything found in one source
    only (G22)."""
    full = index_full(layouts)
    sets, comps, stats = full["sets"], full["compositions"], full["stats"]
    dump_sets = sorted({t.get("set_name") for t in dump.get("tiles") or [] if t.get("set_name")})
    dump_comps = sorted({c.get("name") for c in dump.get("compositions") or [] if c.get("name")})
    dump_comps_by_bundle = {}
    for c in dump.get("compositions") or []:
        if c.get("name") and c.get("bundle"):
            dump_comps_by_bundle.setdefault(c["bundle"], 0)
            dump_comps_by_bundle[c["bundle"]] += 1
    ser_comps_by_bundle = {}
    for name, rec in comps.items():
        ser_comps_by_bundle.setdefault(rec["bundle"], 0)
        ser_comps_by_bundle[rec["bundle"]] += 1
    only_ser_sets = sorted(set(sets) - set(dump_sets))
    only_dump_sets = sorted(set(dump_sets) - set(sets))
    only_ser_comps = sorted(set(comps) - set(dump_comps))
    only_dump_comps = sorted(set(dump_comps) - set(comps))
    gaps = []
    if only_ser_sets:
        gaps.append({"code": "G22", "kind": "set_only_serialized", "names": only_ser_sets,
                     "detail": "%d composition set(s) exist in the serialized UI bundles but no dump tiles row "
                               "names them" % len(only_ser_sets)})
    if only_dump_sets:
        gaps.append({"code": "G22", "kind": "set_only_dump", "names": only_dump_sets,
                     "detail": "%d dump tile set name(s) have no serialized composition set" % len(only_dump_sets)})
    if only_ser_comps:
        gaps.append({"code": "G22", "kind": "composition_only_serialized", "names": only_ser_comps,
                     "detail": "%d composition(s) exist in the serialized UI bundles but are not in the dump"
                               % len(only_ser_comps)})
    if only_dump_comps:
        gaps.append({"code": "G22", "kind": "composition_only_dump", "names": only_dump_comps,
                     "detail": "%d dump composition(s) were not found by the serialized scan" % len(only_dump_comps)})
    return {"totals": {"sets": len(sets), "compositions": len(comps),
                       "dump_sets": len(dump_sets), "dump_compositions": len(dump_comps)},
            "per_bundle": {b: {"sets": s["sets"], "compositions": s["compositions"],
                               "dump_compositions": dump_comps_by_bundle.get(b, 0), "read": s["read"]}
                           for b, s in stats.items() if s["sets"] or s["compositions"] or
                           dump_comps_by_bundle.get(b)},
            "only_serialized_sets": only_ser_sets, "only_dump_sets": only_dump_sets,
            "only_serialized_compositions": only_ser_comps, "only_dump_compositions": only_dump_comps,
            "gaps": gaps}


def cross_check(serialized, dump_rows, set_name):
    """Compare the serialized mapping with the dump's tiles rows for the same set. Every disagreement is a
    NAMED gap (G21): the serialized asset is authoritative; the dump is the convenience copy."""
    gaps = []
    dump_by_key = {}
    for row in dump_rows or []:
        dump_by_key.setdefault(row.get("breakpoint"), []).append(row.get("composition"))
    ser_keys = {k for k, refs in serialized.items() if refs}
    all_keys = sorted(ser_keys | set(dump_by_key))
    for key in all_keys:
        ser = [c.get("name") for c in serialized.get(key) or []]
        dump = dump_by_key.get(key)
        if dump is None:
            gaps.append({"code": "G21", "set": set_name, "breakpoint": key,
                         "kind": "dump_missing_breakpoint", "serialized": ser,
                         "detail": "the serialized set carries breakpoint %s (%s); the dump has no tiles row for it"
                                   % (key, ", ".join(n or "?" for n in ser))})
            continue
        if not ser:
            gaps.append({"code": "G21", "set": set_name, "breakpoint": key,
                         "kind": "dump_only_breakpoint", "dump": sorted(set(dump)),
                         "detail": "the dump has tiles rows for breakpoint %s (%s) but the serialized set has no composition there"
                                   % (key, ", ".join(sorted(set(dump))))})
            continue
        dump_names, ser_names = sorted(set(dump)), sorted(set(ser))
        missing = [n for n in ser_names if n not in dump_names]     # variants the dump's per-cell rows do not list
        extra = [n for n in dump_names if n not in ser_names]       # the dump names something the set does not hold
        if extra:
            gaps.append({"code": "G21", "set": set_name, "breakpoint": key, "kind": "composition_mismatch",
                         "serialized": ser_names, "dump": dump_names,
                         "detail": "breakpoint %s CONTRADICTS the serialized set: the dump names %s, the set holds %s"
                                   % (key, extra, ser_names)})
        if missing:
            gaps.append({"code": "G21", "set": set_name, "breakpoint": key, "kind": "dump_omits_variants",
                         "serialized": ser_names, "dump": dump_names,
                         "detail": "breakpoint %s: the dump lists %s; the serialized set also offers %s (its rows hold one "
                                   "chosen composition per cell, not every candidate)" % (key, dump_names, missing)})
    contradictions = [g for g in gaps if g["kind"] in ("composition_mismatch", "dump_only_breakpoint",
                                                       "dump_missing_breakpoint")]
    return {"status": "AGREE" if not contradictions else "MISMATCH",
            "source": "serialized m_gridBreakpointCompositionData",
            "dump_rows": len(dump_rows or []),
            "keys_compared": all_keys,
            "gaps": gaps}
