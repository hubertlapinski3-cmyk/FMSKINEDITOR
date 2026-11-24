"""Whole-bundle structural comparison (Stage 4D; the Stage 3B compare() script as a library function, per
docs/rea/STAGE-4A-ARCHITECTURE.md section 6.6). Stage 5 adds the CELL layer: for every changed composition object the per-cell changes (structure.cell_changes, from celldiff.cells_diff) and for changed layouts the changed BindingRemapper mappings (structure.binding_mappings_changed), so a build manifest shows exactly which cell changes the built bundle carries.

One call reopens both files read-only and reports the three difference layers separately:
  byte      file sizes and hashes; byte identity is NOT required (UnityPy re-chunks blocks) and the record says so
  object    the object set, the per-object kind/digest comparison, and the first differing field path of every changed
            object (typetrees for MonoBehaviours, raw bytes otherwise)
  structure the serialized-file level: object counts by type, the AssetBundle object (container, dependencies), the
            PPtr multiset, and deserialisation of every object in the output

The build manifest (manifest.py) stores one record per written bundle; verify_static.gate stays the blocking check,
this is the report the manifest carries. Nothing here writes a file.
"""
import json
import os

from . import bundles, celldiff


def pptr_multiset(tree):
    """Every object pointer of a typetree as a sorted multiset [(file_id, path_id)]."""
    out, stack = [], [tree]
    while stack:
        x = stack.pop()
        if isinstance(x, dict):
            if len(x) == 2 and "m_FileID" in x and "m_PathID" in x:
                out.append((x["m_FileID"], x["m_PathID"]))
                continue
            stack.extend(x.values())
        elif isinstance(x, list):
            stack.extend(x)
    return sorted(out)


def compare(vanilla_path, built_path):
    """The three-layer difference record of two bundle files. A check that cannot run is reported as its own field,
    never skipped silently."""
    vd, _ = bundles.object_digests(vanilla_path)
    bd, _ = bundles.object_digests(built_path)
    tt_ids = {i for i in set(vd) & set(bd) if vd[i][0] == "tt"}          # every MonoBehaviour of both files
    _, vtrees = bundles.object_digests(vanilla_path, tt_ids)
    _, btrees = bundles.object_digests(built_path, tt_ids)
    same_set = set(vd) == set(bd)
    changed = sorted(i for i in vd if i in bd and vd[i][:2] != bd[i][:2])
    missing, extra = sorted(set(vd) - set(bd)), sorted(set(bd) - set(vd))
    obj = {"object_set_equal": same_set,
           "missing_path_ids": [str(i) for i in missing], "extra_path_ids": [str(i) for i in extra],
           "changed_objects": []}
    for pid in changed:
        a, b = vtrees.get(pid), btrees.get(pid)
        obj["changed_objects"].append({"path_id": str(pid), "label": bd[pid][2], "kind": bd[pid][0],
                                       "first_difference": bundles.first_difference(a, b) if a is not None and b is not None else "(digest only)"})
    # the structural layer: one read-only open per file gives type counts, the AssetBundle object, deserialisation
    ev, eb = bundles.open_readonly(vanilla_path), bundles.open_readonly(built_path)
    vc, bc = {}, {}
    for o in ev.objects:
        vc[o.type.name] = vc.get(o.type.name, 0) + 1
    errors = []
    for o in eb.objects:
        bc[o.type.name] = bc.get(o.type.name, 0) + 1
        try:
            o.read_typetree() if o.type.name == "MonoBehaviour" else o.read()
        except Exception as e:
            errors.append("%s %s: %s" % (o.type.name, o.path_id, e))
    ab_v, ab_b = ab_of(ev), ab_of(eb)
    structure = {"type_counts_equal": vc == bc, "type_counts_output": bc,
                 "deserialisation_errors_output": errors,
                 "pptr_multiset": {"source": 0, "output": 0, "objects_with_mismatch": []}}
    if ab_v is not None and ab_b is not None:
        structure["assetbundle_object_equal"] = json.dumps(ab_v, sort_keys=True, default=str) == json.dumps(ab_b, sort_keys=True, default=str)
        structure["dependencies_equal"] = (ab_v.get("m_Dependencies") or []) == (ab_b.get("m_Dependencies") or [])
        structure["container_entries"] = len(ab_v.get("m_Container") or [])
    else:
        structure["assetbundle_object"] = "not readable in both files"
    n_v = n_b = 0
    bad = []
    for pid in sorted(tt_ids):
        a, b = pptr_multiset(vtrees.get(pid) or {}), pptr_multiset(btrees.get(pid) or {})
        n_v, n_b = n_v + len(a), n_b + len(b)
        if a != b:
            bad.append(str(pid))
    structure["pptr_multiset"] = {"source": n_v, "output": n_b, "objects_with_mismatch": bad}
    # the CELL layer (Stage 5, the 5G prerequisite): what changed INSIDE the changed compositions, and the
    # BindingRemapper mappings of the changed layouts - so a manifest shows exactly which cell changes the
    # built bundle carries. Empty result = no key added: existing Stage 4 manifests keep their meaning.
    structure.update(celldiff.structure_extras(vtrees, btrees, changed, ev, eb))
    hs, hb = bundles.sha256(vanilla_path), bundles.sha256(built_path)
    return {
        "byte": {"identical": hs == hb, "source_size": os.path.getsize(vanilla_path), "output_size": os.path.getsize(built_path),
                 "source_sha256": hs, "output_sha256": hb,
                 "note": "byte identity is not required: the writer re-chunks the storage blocks (Stage 3A)"},
        "object": obj, "structure": structure,
    }


def ab_of(env):
    """The bundle's AssetBundle object as a typetree, or None."""
    for o in env.objects:
        if o.type.name == "AssetBundle":
            try:
                return o.read_typetree()
            except Exception:
                return None
    return None
