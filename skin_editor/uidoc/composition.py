"""Read the selected composition's serialized fields directly from its original bundle.

The layout dump remains the existing screen assembler input. This supplement reads the
composition asset itself and never fabricates fields absent from that asset.
"""
from copy import deepcopy


FIELDS = ("m_gridBreakpoint", "m_gridComponents", "m_gridElementSet", "m_layoutMode", "m_layoutPreset",
          "m_optionalConditions", "m_optionalConfigConditions", "m_optionalSlices", "m_placementBindings",
          "m_reflowMode", "m_reverseOptionalForRTL", "m_bindingExpect", "m_expectRemaps",
          "m_compositionVersion", "m_contentAlignment", "m_allowedTags")


def read(source, bundle, path_id, renderer=None):
    """Return serialized composition fields and any pointer locators, or an explicit failure."""
    try:
        obj = source.store._bundle_objs(bundle).get(int(path_id))
        if obj is None:
            return None, {"code": "COMPOSITION_ASSET_MISSING", "reason": "PathID %s is absent from %s" % (path_id, bundle)}
        tree = obj.read_typetree()
        if "m_gridComponents" not in tree:
            return None, {"code": "COMPOSITION_ASSET_TYPE_MISMATCH", "reason": "PathID %s in %s has no m_gridComponents" % (path_id, bundle)}
        fields = {k: deepcopy(tree[k]) for k in FIELDS if k in tree}
        pointers = []

        def walk(value, path):
            if isinstance(value, dict):
                guid = value.get("m_AssetGUID")
                if guid:
                    ref = {"field_path": path, "guid": str(guid).lower(), "resolved": False}
                    try:
                        targets = source.guid_objects(guid)
                    except Exception:
                        targets = []
                    for target_bundle, target_pid in targets:
                        try:
                            target_obj = source.store._bundle_objs(target_bundle).get(int(target_pid))
                            if target_obj is not None and target_obj.type.name == "MonoBehaviour":
                                target_tree = target_obj.read_typetree()
                                if "m_VisualTree" in target_tree:
                                    ref.update({"resolved": True, "bundle": target_bundle, "resolved_path_id": str(target_pid), "asset_type": "VisualTreeAsset", "name": target_tree.get("m_Name"), "target_guid": str(guid).lower()})
                                    break
                        except Exception:
                            continue
                    pointers.append(ref)
                if "m_PathID" in value and "m_FileID" in value:
                    pid, fid = value.get("m_PathID"), value.get("m_FileID")
                    if pid:
                        ref = {"field_path": path, "file_id": fid, "path_id": str(pid), "resolved": False}
                        resolver = getattr(renderer, "_assets", None)
                        if resolver is not None:
                            resolved = resolver.resolve(bundle, fid, pid)
                            if "error" not in resolved:
                                ref.update({"resolved": True, "bundle": resolved["bundle"], "resolved_path_id": str(resolved["path_id"]), "asset_type": resolved["type"], "name": resolved.get("name")})
                            else:
                                ref["error"] = resolved["error"]
                        pointers.append(ref)
                    return
                for k, v in value.items():
                    walk(v, path + "." + str(k))
            elif isinstance(value, list):
                for i, v in enumerate(value):
                    walk(v, "%s[%d]" % (path, i))

        walk(fields, "composition")
        return {"fields": fields, "pointers": pointers,
                "physical": {"bundle": bundle, "serialized_file": obj.assets_file.name, "path_id": str(path_id), "asset_type": obj.type.name}}, None
    except Exception as e:
        return None, {"code": "COMPOSITION_READ_FAILED", "reason": "%s: %s" % (type(e).__name__, e)}


def read_set_descriptions(source, bundle, fields):
    """The composition's m_gridElementSet descriptions, INCLUDING the ones no cell currently places (read for the
    AddCell gate; the per-cell read above stays the inventory's source so inventory counts do not change). Returns
    (descriptions, error) with the same record shape read_descriptions uses: [{path_id, read, name, id,
    default_config_index, configurations}]."""
    try:
        objs = source.store._bundle_objs(bundle)
    except Exception as e:
        return None, "%s: %s" % (type(e).__name__, e)
    ref = fields.get("m_gridElementSet") or {}
    pid = ref.get("m_PathID")
    obj = objs.get(int(pid)) if isinstance(pid, int) and not isinstance(pid, bool) else None
    if obj is None:
        return None, "the grid element set is absent from the composition's bundle"
    try:
        st = obj.read_typetree()
    except Exception as e:
        return None, "%s: %s" % (type(e).__name__, str(e)[:80])
    out = []
    for dref in st.get("m_gridElementDescriptions") or []:
        dpid = (dref or {}).get("m_PathID")
        obj2 = objs.get(int(dpid)) if isinstance(dpid, int) and not isinstance(dpid, bool) else None
        if obj2 is None:
            out.append({"path_id": str(dpid), "read": False, "reason": "the description asset is absent from the composition's bundle"})
            continue
        try:
            t = obj2.read_typetree()
        except Exception as e:
            out.append({"path_id": str(dpid), "read": False, "reason": "%s: %s" % (type(e).__name__, str(e)[:80])})
            continue
        cfgs = []
        for c in t.get("<Configurations>k__BackingField") or []:
            cfgs.append({"size": c.get("Size"), "type": c.get("Type"),
                         "asset_guid": (c.get("AssetRef") or {}).get("m_AssetGUID"),
                         "asset_path_id": (str((c.get("Asset") or {}).get("m_PathID"))
                                           if (c.get("Asset") or {}).get("m_PathID") else None)})
        out.append({"path_id": str(dpid), "read": True, "name": t.get("m_Name"),
                    "id": t.get("<ID>k__BackingField"),
                    "default_config_index": t.get("<DefaultConfigIndex>k__BackingField"),
                    "configurations": cfgs})
    return out, None


def read_descriptions(source, bundle, fields):
    """ADDENDUM read 1 (2026-11-18): each cell's tile-configuration DESCRIPTIONS, read from the composition's
    bundle: every cell's m_minSize and m_maxSize, and each description asset's full configuration list with its
    sizes and the layout references it carries (the AssetRef GUID and the same-bundle Asset PPtr). Read only:
    nothing is fabricated, an unreadable description is reported as its own record."""
    try:
        objs = source.store._bundle_objs(bundle)
    except Exception as e:
        return None, "%s: %s" % (type(e).__name__, e)
    out = []
    for i, cell in enumerate(fields.get("m_gridComponents") or []):
        rec = {"cell_index": i, "element_id": cell.get("m_elementID"),
               "min_size": cell.get("m_minSize"), "max_size": cell.get("m_maxSize"), "descriptions": []}
        for ref in cell.get("m_configDescriptions") or []:
            ref = ref or {}
            fid, pid = ref.get("m_FileID", 0), ref.get("m_PathID")
            if fid not in (0, None):
                rec["descriptions"].append({"path_id": str(pid), "read": False, "reason": "the description uses external file id %s" % fid})
                continue
            obj = objs.get(int(pid)) if isinstance(pid, int) and not isinstance(pid, bool) else None
            if obj is None:
                rec["descriptions"].append({"path_id": str(pid), "read": False, "reason": "the description asset is absent from the composition's bundle"})
                continue
            try:
                t = obj.read_typetree()
            except Exception as e:
                rec["descriptions"].append({"path_id": str(pid), "read": False, "reason": "%s: %s" % (type(e).__name__, str(e)[:80])})
                continue
            cfgs = []
            for c in t.get("<Configurations>k__BackingField") or []:
                cfgs.append({"size": c.get("Size"), "type": c.get("Type"),
                             "asset_guid": (c.get("AssetRef") or {}).get("m_AssetGUID"),
                             "asset_path_id": (str((c.get("Asset") or {}).get("m_PathID"))
                                               if (c.get("Asset") or {}).get("m_PathID") else None)})
            rec["descriptions"].append({"path_id": str(pid), "read": True, "name": t.get("m_Name"),
                                        "id": t.get("<ID>k__BackingField"),
                                        "default_config_index": t.get("<DefaultConfigIndex>k__BackingField"),
                                        "configurations": cfgs})
        out.append(rec)
    return out, None

