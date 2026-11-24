"""Cell-level comparison of composition assets and remapper mapping capture (Stage 5, the 5G prerequisite).

`skin_editor.bundlediff.compare` reports the byte/object/structure layers but cannot say WHICH CELLS of a
changed composition moved, resized or were added. This module adds that layer: `cells_diff` compares two
composition typetrees cell by cell (insertion-safe), `raw_remappers` reads a layout's BindingRemapper mappings
from the RAW element tree (the render's parse record keeps only scalar attributes, and a mapping is the
non-scalar `Mappings` list). `structure_extras` is the seam `compare` calls: it builds the manifest's
`structure.cell_changes` and `structure.binding_mappings_changed` from the already-decoded typetrees and envs,
and returns an EMPTY dict when a pair has no composition or layout change - so existing Stage 4 manifests keep
their meaning.

The matchers were originally written for the Golden Boy diff (evidence/stage-5join/goldenboy-diff.py), where
three bugs were caught by the owner's independent reading and fixed; the fixed versions live HERE now (the
tests import the app module: tests/test_goldenboy_diff_tool.py).
"""
import json

GEO = ("x", "y", "w", "h")


def cells_of(tree):
    """{(element_id, occurrence): {location, min, max, locked, optional}} of one composition object. The
    occurrence counts duplicates of the same element id in order, so an inserted cell does not shift the keys
    (matching by index miscounted moved cells as removals+additions; caught by the owner's five facts)."""
    out, seen = {}, {}
    for i, c in enumerate(tree.get("m_gridComponents") or []):
        eid = c.get("m_elementID")
        k = seen[eid] if eid in seen else 0
        seen[eid] = k + 1
        loc = c.get("m_location") or {}
        out[(eid, k)] = {
            "location": (loc.get("x"), loc.get("y"), loc.get("width"), loc.get("height")),
            "min": ((c.get("m_minSize") or {}).get("x"), (c.get("m_minSize") or {}).get("y")),
            "max": ((c.get("m_maxSize") or {}).get("x"), (c.get("m_maxSize") or {}).get("y")),
            "locked": c.get("m_isLocked"), "optional": c.get("m_isOptional"),
        }
    return out


def cells_diff(vt, gt):
    """The insertion-safe cell comparison of two composition typetrees: cells matched by
    (element_id, occurrence); a real location change is a move, an index shift alone is not."""
    cv, cg = cells_of(vt), cells_of(gt)
    added, removed = sorted(set(cg) - set(cv)), sorted(set(cv) - set(cg))
    moved, resized, mins = [], [], []
    for key in sorted(set(cg) & set(cv)):
        if cg[key]["location"] != cv[key]["location"]:
            moved.append({"element_id": key[0], "occurrence": key[1], "from": cv[key]["location"], "to": cg[key]["location"]})
        if cg[key]["max"] != cv[key]["max"]:
            resized.append({"element_id": key[0], "occurrence": key[1], "from": cv[key]["max"], "to": cg[key]["max"]})
        if cg[key]["min"] != cv[key]["min"]:
            mins.append({"element_id": key[0], "occurrence": key[1], "from": cv[key]["min"], "to": cg[key]["min"]})
    return {"composition": gt.get("m_Name"), "cells_vanilla": len(cv), "cells_goldenboy": len(cg),
            "added_cells": [{"element_id": k[0], "occurrence": k[1], "location": cg[k]["location"]} for k in added],
            "removed_cells": [{"element_id": k[0], "occurrence": k[1]} for k in removed],
            "changed_m_location": moved, "changed_m_maxSize": resized, "changed_m_minSize": mins}


def mappings_from_attrs(attrs):
    """A BindingRemapper element's MAPPINGS from its raw attributes: the parse record keeps only scalar
    attributes, and the mapping is the non-scalar `Mappings` list ({from, to.m_path}) - reading it from the
    parse record returned empty strings (the second bug the owner's five facts caught)."""
    return [{"from": m.get("from"), "to": (m.get("to") or {}).get("m_path")}
            for m in (attrs or {}).get("Mappings") or []]


def raw_remappers(env, pid):
    """The BindingRemapper elements' MAPPINGS of one VisualTreeAsset object, from the RAW element tree.
    `env` is any object holding `objects`, each with `path_id` and `read_typetree()` (a UnityPy environment,
    or the tests' fake)."""
    from . import uxml
    obj = next((o for o in env.objects if str(o.path_id) == str(pid)), None)
    if obj is None:
        return None
    try:
        t = obj.read_typetree()
        refs = uxml.registry(t)
    except Exception as e:
        return "unreadable: %s" % str(e)[:60]
    out, stack = [], [t["m_VisualTree"]["rid"]]
    while stack:
        rid = stack.pop()
        e = uxml.element(t, refs, rid)
        if e is None:
            continue
        if "BindingRemapper" in (e.get("type") or ""):
            out.append({"name": e.get("name") or "", "maps": mappings_from_attrs(e.get("attrs"))})
        stack.extend(reversed(e.get("children") or []))
    return sorted(out, key=lambda r: (r["name"], json.dumps(r["maps"], sort_keys=True)))


def structure_extras(vtrees, btrees, changed, vanilla_env, built_env):
    """{cell_changes, binding_mappings_changed} for the changed path ids; only the keys that have content.
    `vanilla_env`/`built_env` may be None (no remapper layer is then produced)."""
    cell_changes, binding_mappings = {}, {}
    for pid in changed:
        vt, bt = vtrees.get(pid), btrees.get(pid)
        if not isinstance(vt, dict) or not isinstance(bt, dict):
            continue
        if "m_gridComponents" in bt and "m_gridComponents" in vt:
            try:
                cell_changes[str(pid)] = cells_diff(vt, bt)
            except Exception as e:
                cell_changes[str(pid)] = {"composition": bt.get("m_Name"), "error": "%s: %s" % (type(e).__name__, str(e)[:80])}
        elif "m_VisualTree" in bt:
            try:
                mappings = None
                vanilla = None
                if built_env is not None:
                    mappings = raw_remappers(built_env, pid)
                if vanilla_env is not None:
                    vanilla = raw_remappers(vanilla_env, pid)
                if mappings is not None and vanilla is not None and mappings != vanilla:
                    binding_mappings[str(pid)] = {"layout": bt.get("m_Name"), "vanilla": vanilla, "output": mappings}
            except Exception as e:
                binding_mappings[str(pid)] = {"layout": bt.get("m_Name"), "error": "%s: %s" % (type(e).__name__, str(e)[:80])}
    out = {}
    if cell_changes:
        out["cell_changes"] = cell_changes
    if binding_mappings:
        out["binding_mappings_changed"] = binding_mappings
    return out
