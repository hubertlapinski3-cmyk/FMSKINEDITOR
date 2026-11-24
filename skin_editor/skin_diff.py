"""Reusable third-party skin bundle differ (SKIN-RR1, C3/C7).

Compares a third-party skin's Unity bundles against a stock bundle set object by object,
matched by (type, name), while filtering out Unity/Addressables build noise (m_ContentHash,
VisualTreeAsset m_Id/m_ParentId/uxmlAssetId/m_OrderInDocument/m_RuleIndex,
m_SerializedDataOverride element ids, and PPtr m_FileID/m_PathID shifts).

Read-only: never writes to the game folder, LocalLow, BepInEx, or the skin folder.
"""
from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Any, Callable

# Keys that shift between builds without representing semantic asset edits.
NOISE_KEYS = frozenset({
    "m_ContentHash",
    "contentHash",
    "m_Id",
    "uxmlAssetId",
    "m_ParentId",
    "m_RuleIndex",
    "m_OrderInDocument",
    "m_ElementId",
    "elementId",
    "m_ElementIdsPath",
    "m_XmlNamespace",
    "m_Hash",
    "m_InstanceID",
    "instanceID",
})

# Keys inside m_SerializedDataOverride entries that carry unstable build IDs.
OVERRIDE_NOISE_KEYS = frozenset({
    "m_ElementId",
    "elementId",
    "m_ElementIdsPath",
    "m_Id",
    "uxmlAssetId",
    "m_ParentId",
})

TEXTURE_TYPES = frozenset({"Texture2D", "Sprite", "VideoClip", "AudioClip"})
STYLE_TYPES = frozenset({"StyleSheet"})
UXML_TYPES = frozenset({"VisualTreeAsset"})
NOT_TIED = "Not tied to a screen"

_VARIANT_TOKEN_RE = re.compile(
    r"(?:[-_](?:Phone[-_]?Landscape|Phone[-_]?Portrait|Phone|Large|Standard|Small|NONE|InMatch|FMC|IM|RR\d*))+$",
    re.I,
)


def _is_pptr(d: Any) -> bool:
    return isinstance(d, dict) and set(d.keys()) <= {"m_FileID", "m_PathID"} and "m_PathID" in d


def normalize_tree(value: Any, obj_type: str = "", parent_key: str = "") -> Any:
    """Recursively strip Unity build-noise fields so semantic diffs are isolated."""
    if isinstance(value, (bytes, bytearray, memoryview)):
        raw = bytes(value)
        return {"__bytes_len": len(raw), "__sha256": hashlib.sha256(raw).hexdigest()[:16]}
    if isinstance(value, dict):
        if _is_pptr(value):
            # Preserve null vs non-null reference without noisy cross-build FileID/PathID shifts
            return "<null>" if int(value.get("m_PathID", 0)) == 0 else "<pptr>"
        out = {}
        in_override = "SerializedDataOverride" in parent_key or "override" in parent_key.lower()
        for k, v in value.items():
            if k in NOISE_KEYS:
                continue
            if in_override and k in OVERRIDE_NOISE_KEYS:
                continue
            if k == "m_Script" and _is_pptr(v):
                continue
            # Large binary blobs in Texture2D / raw data
            if k in ("image data", "m_StreamData") and obj_type in TEXTURE_TYPES:
                continue
            out[k] = normalize_tree(v, obj_type, k)
        return out
    if isinstance(value, list):
        return [normalize_tree(item, obj_type, parent_key) for item in value]
    if isinstance(value, float):
        return round(value, 4)
    return value


def categorize_object(bundle_name: str, obj_type: str, name: str, tree: dict | None = None) -> str:
    """Group an object into a semantic Studio category."""
    bn = (bundle_name or "").lower()
    if obj_type in TEXTURE_TYPES:
        return "texture"
    if obj_type in UXML_TYPES:
        return "uxml"
    if obj_type in STYLE_TYPES:
        return "style"
    if isinstance(tree, dict):
        if "m_gridComponents" in tree:
            return "composition"
        if "m_gridBreakpointCompositionData" in tree:
            return "composition_set"
        if "m_tableView" in tree or "ui-tableviews" in bn:
            return "table_view"
        if "m_columnFactories" in tree or "m_factories" in tree or "ui-tablefactories" in bn:
            return "table_factory"
        if "m_configurations" in tree or "m_tileConfigurations" in tree or "Description" in (name or ""):
            if "ui-tileslayouts" in bn or "m_configurations" in tree or "m_tileConfigurations" in tree:
                return "description"
        if "m_elements" in tree or "m_gridElements" in tree or "ElementSet" in (name or ""):
            return "element_set"
    if "ui-styles" in bn:
        return "style"
    if "ui-visualtreeassets" in bn:
        return "uxml"
    if "ui-tablefactories" in bn:
        return "table_factory"
    if "ui-tableviews" in bn:
        return "table_view"
    if any(k in bn for k in ("globalnavigation", "panelids", "calendar", "datacollections", "visualfunctions")):
        return "navigation"
    if any(k in bn for k in ("textures", "backgrounds", "icons", "mainmenu", "videos")):
        return "texture"
    return "other"


_SCREEN_SUFFIX_RE = re.compile(
    r"(?:Composition|TileCompositionSet|GridCompositionSet|GridComposition|ElementSet|Description|TileDescription)"
    r"(?:[-_](?:Large|Standard|Small|NONE|InMatch|FMC|IM|Phone[-_]?Landscape|Phone[-_]?Portrait|Phone|RR\d*))*$",
    re.I,
)


def split_screen_variant(name: str) -> tuple[str, str | None]:
    """Extract (canonical_stem, variant_label) from an asset or composition name.
    Recognizes breakpoints (-Large, -Standard, -Small, -NONE), modes (-IM, -FMC, -InMatch),
    platform variants (-PhoneLandscape, -Phone_Landscape, -PhonePortrait, -Phone), and skin tags (-RR8)."""
    if not name:
        return "Other", None
    tokens: list[str] = []
    cur = name
    # Pull trailing variant / skin tags cleanly in reverse display order
    tag_re = re.compile(
        r"[-_](RR\d+|Phone[-_]?Landscape|Phone[-_]?Portrait|Phone|Large|Standard|Small|NONE|InMatch|FMC|IM)$",
        re.I,
    )
    while True:
        m = tag_re.search(cur)
        if not m:
            break
        tok = m.group(1).replace("_", "")
        if tok.upper() in ("FMC", "IM", "NONE"):
            tok = tok.upper()
        elif tok.lower().startswith("rr"):
            tok = tok.upper()
        elif tok.lower() == "phonelandsacpe":
            tok = "PhoneLandscape"
        else:
            tok = tok[0].upper() + tok[1:] if len(tok) > 1 else tok.upper()
        tokens.append(tok)
        cur = cur[: m.start()]
    # Also check embedded FMC before Composition, e.g. SquadCompositionFMC
    if cur.endswith("CompositionFMC") or cur.endswith("CompositionIM"):
        mode_tok = cur[-3:] if cur.endswith("FMC") else cur[-2:]
        tokens.append(mode_tok)
        cur = cur[: -len(mode_tok)]
    tokens.reverse()
    variant = " · ".join(dict.fromkeys(tokens)) if tokens else None
    return cur or name, variant


def detect_skin_source(skin_dir: Path | str) -> dict[str, str]:
    """Read skin name and version read-only from README/metadata files in `skin_dir`."""
    p = Path(skin_dir)
    skin_json = p / "skin.json"
    if skin_json.is_file():
        try:
            import json
            data = json.loads(skin_json.read_text(encoding="utf-8", errors="replace"))
            name = str(data.get("name") or p.name).strip()
            ver = str(data.get("version") or "").strip()
            if name:
                return {"name": name, "version": ver, "label": f"{name} v{ver}" if ver else name}
        except Exception:
            pass
    for doc_name in ("README_EN.txt", "README.txt", "LIESMICH.txt", "LISEZMOI_FR.txt"):
        doc = p / doc_name
        if doc.is_file():
            try:
                head = " ".join(doc.read_text(encoding="utf-8", errors="replace").splitlines()[:5])
                m = re.search(
                    r"([A-Za-z0-9][A-Za-z0-9._ -]{1,40}?)\s+(?:for\s+Football\s+Manager\s+\d+\s*[-–]?\s*(?:Windows|macOS|Mac)?\s*)?version\s+([0-9]+(?:\.[0-9]+)+[a-zA-Z0-9-]*)",
                    head,
                    re.I,
                )
                if m:
                    name = m.group(1).strip(" -–")
                    ver = m.group(2).strip()
                    return {"name": name, "version": ver, "label": f"{name} v{ver}"}
            except Exception:
                pass
    fallback = p.parent.name if p.name.lower() in ("input", "files") and p.parent.name else p.name
    fallback = fallback or "Inspected skin"
    return {"name": fallback, "version": "", "label": fallback}


def infer_screen_name(name: str, category: str) -> str:
    """Derive a human-readable screen/group key from an object name."""
    if not name:
        return "Other"
    cleaned, _ = split_screen_variant(name)
    cleaned = _SCREEN_SUFFIX_RE.sub("", cleaned)
    cleaned = cleaned.strip("-_ ")
    if not cleaned:
        return name
    return cleaned


def _summarize_texture(obj: Any, tree: dict | None) -> dict:
    info: dict[str, Any] = {}
    if isinstance(tree, dict):
        for k in ("m_Width", "m_Height", "m_TextureFormat", "m_CompleteImageSize"):
            if k in tree:
                info[k] = tree[k]
        if "m_Rect" in tree and isinstance(tree["m_Rect"], dict):
            r = tree["m_Rect"]
            info["rect"] = [round(float(r.get(c, 0)), 1) for c in ("x", "y", "width", "height")]
    try:
        raw = obj.get_raw_data()
        info["raw_size"] = len(raw)
        info["raw_sha256"] = hashlib.sha256(raw).hexdigest()[:16]
    except Exception:
        pass
    return info


def _style_class_sigs(tree: dict) -> dict[str, list[str]]:
    """Map selector class name -> compact rule signatures for comparing stock vs skin StyleSheets."""
    from . import uss
    smap = uss.selector_map(tree)
    rules = tree.get("m_Rules") or []
    out: dict[str, list[str]] = {}
    cls_re = re.compile(r"\.([A-Za-z_][\w-]*)")
    for idx, r in enumerate(rules):
        if not isinstance(r, dict):
            continue
        props = ",".join(
            f"{uss.prop_name(p)}:{len(p.get('m_Values') or [])}"
            for p in (r.get("m_Properties") or [])
            if isinstance(p, dict)
        )
        for cs in smap[idx] if idx < len(smap) else []:
            stxt = uss.selector_text(cs)
            for cls in set(cls_re.findall(stxt)):
                out.setdefault(cls, []).append(f"{stxt}|{props}")
    return out


def _summarize_style(tree: dict) -> dict:
    rules = tree.get("m_Rules") or []
    sels = tree.get("m_ComplexSelectors") or []
    strings = tree.get("strings") or []
    colors = tree.get("colors") or []
    classes = sorted({s for s in strings if isinstance(s, str) and (s.startswith("rr-") or s.startswith("RR-") or s.startswith("rr_"))})
    prop_names = sorted({p.get("m_Name", "") for r in rules if isinstance(r, dict) for p in (r.get("m_Properties") or []) if isinstance(p, dict) and p.get("m_Name")})
    class_sigs = _style_class_sigs(tree) if rules else {}
    return {
        "rules": len(rules),
        "selectors": len(sels),
        "colors": len(colors),
        "strings": len(strings),
        "custom_classes": classes[:50],
        "custom_class_count": len(classes),
        "property_kinds": prop_names[:60],
        "_class_sigs": {k: sorted(v) for k, v in class_sigs.items()},
    }


def _summarize_uxml(tree: dict) -> dict:
    elems = tree.get("m_VisualElementAssets") or []
    tmpls = tree.get("m_TemplateAssets") or []
    usings = tree.get("m_Usings") or []
    classes = set()
    ref_count = 0
    tmpl_count = len(tmpls)
    for e in elems:
        if isinstance(e, dict):
            for c in (e.get("m_Classes") or []):
                if isinstance(c, str):
                    classes.add(c)
    for r in (tree.get("references") or {}).get("RefIds") or []:
        if not isinstance(r, dict):
            continue
        d = r.get("data") or {}
        if d.get("m_Id") is None:
            continue
        ref_count += 1
        if (r.get("type") or {}).get("class") == "TemplateAsset":
            tmpl_count += 1
        for c in (d.get("m_Classes") or []):
            if isinstance(c, str):
                classes.add(c)
    using_aliases = [
        u.get("m_Alias") or u.get("alias")
        for u in usings
        if isinstance(u, dict) and (u.get("m_Alias") or u.get("alias"))
    ]
    return {
        "elements": len(elems) or ref_count,
        "templates": tmpl_count,
        "usings": using_aliases,
        "classes": sorted(classes),
    }


def _summarize_composition(tree: dict) -> dict:
    comps = tree.get("m_gridComponents") or []
    slices = tree.get("m_optionalSlices") or {}
    return {
        "name": tree.get("m_Name"),
        "version": tree.get("m_compositionVersion"),
        "cells": [
            {
                "element_id": c.get("m_elementID"),
                "location": c.get("m_location"),
                "min": c.get("m_minSize"),
                "max": c.get("m_maxSize"),
                "locked": c.get("m_isLocked"),
            }
            for c in comps if isinstance(c, dict)
        ],
        "optional_slices": {
            k: [e.get("m_elementID") for e in v if isinstance(e, dict) and "m_elementID" in e]
            for k, v in slices.items() if isinstance(v, list) and v
        },
    }


def diff_trees(a: Any, b: Any, path: str = "", limit: int = 80) -> list[dict]:
    """Return field-level differences between two normalized trees (up to `limit` entries)."""
    out: list[dict] = []

    def walk(x: Any, y: Any, p: str) -> None:
        if len(out) >= limit:
            return
        if type(x) is not type(y):
            out.append({"path": p or "$", "kind": "type_change", "before": _brief(x), "after": _brief(y)})
            return
        if isinstance(x, dict):
            keys = sorted(set(x.keys()) | set(y.keys()))
            for k in keys:
                if len(out) >= limit:
                    return
                kp = f"{p}.{k}" if p else k
                if k not in x:
                    out.append({"path": kp, "kind": "added", "after": _brief(y[k])})
                elif k not in y:
                    out.append({"path": kp, "kind": "removed", "before": _brief(x[k])})
                else:
                    walk(x[k], y[k], kp)
        elif isinstance(x, list):
            if len(x) != len(y):
                out.append({"path": p or "$", "kind": "list_len", "before": len(x), "after": len(y)})
            for i in range(min(len(x), len(y))):
                if len(out) >= limit:
                    return
                walk(x[i], y[i], f"{p}[{i}]")
        else:
            if x != y:
                out.append({"path": p or "$", "kind": "changed", "before": _brief(x), "after": _brief(y)})

    walk(a, b, path)
    return out


def _brief(v: Any) -> Any:
    if isinstance(v, (int, float, bool)) or v is None:
        return v
    if isinstance(v, str):
        return v if len(v) <= 120 else v[:117] + "..."
    if isinstance(v, list):
        return f"<list len={len(v)}>"
    if isinstance(v, dict):
        return f"<dict keys={len(v)}>"
    return str(v)[:120]


def _read_bundle_objects(bundle_path: Path, keep_compositions: bool = False) -> tuple[dict[tuple[str, str, int], dict], dict[str, dict]]:
    """Read a Unity bundle into a dict keyed by (type_name, name, dup_index)."""
    import UnityPy

    env = UnityPy.load(str(bundle_path))
    seen_counts: dict[tuple[str, str], int] = {}
    records: dict[tuple[str, str, int], dict] = {}
    compositions: dict[str, dict] = {}
    for obj in env.objects:
        tname = obj.type.name
        if tname in ("AssetBundle", "PreloadData"):
            continue
        try:
            name = obj.peek_name() or ""
        except Exception:
            name = ""
        tree = None
        if tname in TEXTURE_TYPES:
            try:
                tree = obj.read_typetree()
                if not name and isinstance(tree, dict):
                    name = str(tree.get("m_Name") or "")
            except Exception:
                tree = {}
            norm = _summarize_texture(obj, tree)
            raw_tree = None
        else:
            try:
                tree = obj.read_typetree()
                if not name and isinstance(tree, dict):
                    name = str(tree.get("m_Name") or "")
            except Exception:
                try:
                    raw = obj.get_raw_data()
                    tree = {"__raw_sha256": hashlib.sha256(raw).hexdigest()[:16], "__raw_len": len(raw)}
                except Exception:
                    tree = {}
            norm = normalize_tree(tree, tname)
            raw_tree = tree if isinstance(tree, dict) else None
        key2 = (tname, name)
        idx = seen_counts.get(key2, 0)
        seen_counts[key2] = idx + 1
        cat = categorize_object(bundle_path.name, tname, name, raw_tree)
        rec = {
            "type": tname,
            "name": name,
            "index": idx,
            "category": cat,
            "norm": norm,
            "summary": (
                _summarize_style(raw_tree) if cat == "style" and isinstance(raw_tree, dict)
                else _summarize_uxml(raw_tree) if cat == "uxml" and isinstance(raw_tree, dict)
                else _summarize_composition(raw_tree) if cat == "composition" and isinstance(raw_tree, dict)
                else norm if cat == "texture"
                else None
            ),
        }
        records[(tname, name, idx)] = rec
        if keep_compositions and cat == "composition" and isinstance(raw_tree, dict) and name:
            compositions[name] = raw_tree
    return records, compositions


def diff_object_maps(
    bundle_name: str,
    stock_map: dict[tuple[str, str, int], dict],
    skin_map: dict[tuple[str, str, int], dict],
    field_limit: int = 40,
) -> dict:
    """Compare two normalized object maps (used by both bundle diffing and fixture unit tests)."""
    added, removed, changed = [], [], []
    unchanged = 0
    by_category: dict[str, dict[str, int]] = {}

    def bump(cat: str, kind: str) -> None:
        c = by_category.setdefault(cat, {"added": 0, "removed": 0, "changed": 0})
        c[kind] += 1

    all_keys = sorted(set(stock_map.keys()) | set(skin_map.keys()))
    for key in all_keys:
        tname, name, idx = key
        in_stock = key in stock_map
        in_skin = key in skin_map
        if in_skin and not in_stock:
            rec = skin_map[key]
            cat = rec["category"]
            bump(cat, "added")
            added.append({
                "type": tname, "name": name, "category": cat,
                "screen": infer_screen_name(name, cat),
                "summary": rec.get("summary"),
            })
        elif in_stock and not in_skin:
            rec = stock_map[key]
            cat = rec["category"]
            bump(cat, "removed")
            removed.append({
                "type": tname, "name": name, "category": cat,
                "screen": infer_screen_name(name, cat),
            })
        else:
            a, b = stock_map[key], skin_map[key]
            if a["norm"] == b["norm"]:
                unchanged += 1
                continue
            cat = b["category"]
            bump(cat, "changed")
            fields = diff_trees(a["norm"], b["norm"], limit=field_limit)
            changed.append({
                "type": tname, "name": name, "category": cat,
                "screen": infer_screen_name(name, cat),
                "fields": fields,
                "field_count": len(fields),
                "before_summary": a.get("summary"),
                "after_summary": b.get("summary"),
            })

    status = "identical" if not added and not removed and not changed else "changed"
    return {
        "bundle": bundle_name,
        "status": status,
        "counts": {
            "added": len(added),
            "removed": len(removed),
            "changed": len(changed),
            "unchanged": unchanged,
        },
        "by_category": by_category,
        "added": added,
        "removed": removed,
        "changed": changed,
    }


def diff_bundle(skin_bundle: Path, stock_bundle: Path | None, field_limit: int = 40) -> dict:
    """Diff one skin bundle against its stock counterpart (or report all objects as added if new)."""
    skin_bundle = Path(skin_bundle)
    skin_map, _ = _read_bundle_objects(skin_bundle)
    if stock_bundle is None or not Path(stock_bundle).is_file():
        res = diff_object_maps(skin_bundle.name, {}, skin_map, field_limit=field_limit)
        res["status"] = "new"
        res["skin_path"] = str(skin_bundle)
        res["stock_path"] = None
        return res
    stock_bundle = Path(stock_bundle)
    stock_map, _ = _read_bundle_objects(stock_bundle)
    res = diff_object_maps(skin_bundle.name, stock_map, skin_map, field_limit=field_limit)
    res["skin_path"] = str(skin_bundle)
    res["stock_path"] = str(stock_bundle)
    return res


def discover_skin_bundles(skin_dir: Path) -> list[Path]:
    """Find the primary skin bundles in a third-party skin folder.
    If a `files/` subdirectory exists, inspect `files/*.bundle`;
    otherwise inspect `*.bundle` directly in `skin_dir` (or recursively if none at root)."""
    skin_dir = Path(skin_dir)
    if not skin_dir.is_dir():
        raise FileNotFoundError(f"skin folder not found: {skin_dir}")
    files_sub = skin_dir / "files"
    if files_sub.is_dir() and any(files_sub.glob("*.bundle")):
        return sorted(files_sub.glob("*.bundle"))
    direct = sorted(skin_dir.glob("*.bundle"))
    if direct:
        return direct
    return sorted(skin_dir.rglob("*.bundle"))


def _build_tile_bundle_maps(stock_dir: Path, guid_to_name: dict[str, str]) -> dict:
    """Read TileDescription, GridElementSet and GridCompositionSet links from stock ui-tileslayouts_assets_all.bundle."""
    import UnityPy

    tb = Path(stock_dir) / "ui-tileslayouts_assets_all.bundle"
    out = {"desc_to_vtas": {}, "vta_to_descs": {}, "eset_to_descs": {}, "set_to_comps": {}}
    if not tb.is_file():
        return out
    env = UnityPy.load(str(tb))
    pid_to_desc: dict[int, str] = {}
    pid_to_comp: dict[int, str] = {}
    esets: list[tuple[str, list[int]]] = []
    csets: list[tuple[str, list[int]]] = []
    for o in env.objects:
        if o.type.name != "MonoBehaviour":
            continue
        try:
            t = o.read_typetree()
        except Exception:
            continue
        if not isinstance(t, dict):
            continue
        name = t.get("m_Name") or ""
        if "<Configurations>k__BackingField" in t or "m_configurations" in t:
            if name:
                pid_to_desc[o.path_id] = name
                cfgs = t.get("<Configurations>k__BackingField") or t.get("m_configurations") or []
                for c in cfgs:
                    if not isinstance(c, dict):
                        continue
                    aref = c.get("AssetRef") or c.get("m_assetReference") or {}
                    g = aref.get("m_AssetGUID") or ""
                    vname = guid_to_name.get(g) or guid_to_name.get(g.lower())
                    if vname:
                        out["desc_to_vtas"].setdefault(name, set()).add(vname)
                        out["vta_to_descs"].setdefault(vname, set()).add(name)
        elif "m_gridComponents" in t and name:
            pid_to_comp[o.path_id] = name
        elif ("m_gridElementDescriptions" in t or "m_elements" in t) and name:
            refs = t.get("m_gridElementDescriptions") or t.get("m_elements") or []
            pids = [int(r["m_PathID"]) for r in refs if isinstance(r, dict) and r.get("m_PathID")]
            if pids:
                esets.append((name, pids))
        elif "m_gridBreakpointCompositionData" in t and name:
            pids = [
                int((d.get("m_gridComposition") or {}).get("m_PathID", 0))
                for d in (t.get("m_gridBreakpointCompositionData") or [])
                if isinstance(d, dict) and (d.get("m_gridComposition") or {}).get("m_PathID")
            ]
            if pids:
                csets.append((name, pids))
    for sname, pids in esets:
        for p in pids:
            dname = pid_to_desc.get(p)
            if dname:
                out["eset_to_descs"].setdefault(sname, set()).add(dname)
    for sname, pids in csets:
        for p in pids:
            cname = pid_to_comp.get(p)
            if cname:
                out["set_to_comps"].setdefault(sname, set()).add(cname)
    return out


_VTA_STEM_RE = re.compile(r"(?:_(?:\d+|N)x(?:\d+|N)|_(?:Row|Child|Cell|Item|Entry|Template|Header|Footer)(?:_.*)?)$", re.I)


class ScreenResolver:
    """Read-only resolver mapping UXML, style classes, table views/factories, descriptions,
    composition sets, element sets, compositions and navigation assets to parent screens."""

    def __init__(
        self,
        dump: dict | None = None,
        table_usage: dict | None = None,
        tables_obj: Any = None,
        stock_dir: Path | str | None = None,
    ) -> None:
        self.comp_to_panels: dict[str, set[str]] = {}
        self.set_to_panels: dict[str, set[str]] = {}
        self.vta_to_panels: dict[str, set[str]] = {}
        self.vta_stem_to_panels: dict[str, set[str]] = {}
        self.desc_to_panels: dict[str, set[str]] = {}
        self.eset_to_panels: dict[str, set[str]] = {}
        self.table_view_to_panels: dict[str, set[str]] = {}
        self.table_factory_to_panels: dict[str, set[str]] = {}
        self.class_to_panels: dict[str, set[str]] = {}
        self.panel_ids: set[str] = set()
        self.panel_by_stem: dict[str, list[str]] = {}

        guid_to_name: dict[str, str] = {}
        if dump:
            from .layout_join import LayoutData

            ld = LayoutData(dump)
            self.panel_ids = {p["panel_id"] for p in dump.get("panels") or ()}
            for pid in self.panel_ids:
                stem = re.sub(r"(?:Screen|Card|Tool|ModalDialog|Dialog|Panel)$", "", pid)
                if stem:
                    self.panel_by_stem.setdefault(stem.lower(), []).append(pid)

            id_to_name = {l["id"]: l["name"] for l in dump.get("layouts") or ()}
            guid_to_name = {l["guid"]: l["name"] for l in dump.get("layouts") or () if l.get("guid")}

            for t in dump.get("tiles") or ():
                sc, _ = ld.screens_of(t["panel_layout_id"])
                if not sc:
                    continue
                comp = t.get("composition") or ""
                sname = t.get("set_name") or ""
                if comp:
                    self.comp_to_panels.setdefault(comp, set()).update(sc)
                if sname:
                    self.set_to_panels.setdefault(sname, set()).update(sc)
                tlid = t.get("tile_layout_id")
                if tlid in id_to_name:
                    self.vta_to_panels.setdefault(id_to_name[tlid], set()).update(sc)

            for cc in dump.get("cell_configs") or ():
                panels = self.comp_to_panels.get(cc.get("composition") or "")
                tname = id_to_name.get(cc.get("tile_layout_id"))
                if panels and tname:
                    self.vta_to_panels.setdefault(tname, set()).update(panels)

            for l in dump.get("layouts") or ():
                sc, _ = ld.screens_of(l["id"])
                if sc:
                    self.vta_to_panels.setdefault(l["name"], set()).update(sc)

            for cls_map in (ld.static, ld.runtime):
                for cls_name, by_lid in cls_map.items():
                    ps = self.class_to_panels.setdefault(cls_name, set())
                    for lid in by_lid:
                        sc, _ = ld.screens_of(lid)
                        if sc:
                            ps.update(sc)

        tile_maps = _build_tile_bundle_maps(Path(stock_dir), guid_to_name) if stock_dir else {
            "desc_to_vtas": {}, "vta_to_descs": {}, "eset_to_descs": {}, "set_to_comps": {}
        }
        for sname, comps in tile_maps["set_to_comps"].items():
            for c in comps:
                ps = self.comp_to_panels.get(c)
                if ps:
                    self.set_to_panels.setdefault(sname, set()).update(ps)
        for dname, vtas in tile_maps["desc_to_vtas"].items():
            for vn in vtas:
                ps = self.vta_to_panels.get(vn)
                if ps:
                    self.desc_to_panels.setdefault(dname, set()).update(ps)
        # Propagate description -> all alternate size VTAs (e.g. CoachReportBlock_8x10)
        for dname, ps in self.desc_to_panels.items():
            for vn in tile_maps["desc_to_vtas"].get(dname, ()):
                self.vta_to_panels.setdefault(vn, set()).update(ps)

        # B6: Propagate template UXML via m_Usings (dump["includes"]: parent VTA -> child template VTA).
        if dump:
            adj: dict[str, set[str]] = {}
            for inc in dump.get("includes") or ():
                fn = id_to_name.get(inc.get("from_layout_id"))
                tn = id_to_name.get(inc.get("to_layout_id"))
                if fn and tn and fn != tn:
                    adj.setdefault(fn, set()).add(tn)
            queue = list(self.vta_to_panels.keys())
            while queue:
                cur = queue.pop(0)
                ps = self.vta_to_panels.get(cur)
                if not ps:
                    continue
                for child in adj.get(cur, ()):
                    existing = self.vta_to_panels.setdefault(child, set())
                    if not ps.issubset(existing):
                        existing.update(ps)
                        queue.append(child)
        for ename, descs in tile_maps["eset_to_descs"].items():
            for dn in descs:
                ps = self.desc_to_panels.get(dn)
                if ps:
                    self.eset_to_panels.setdefault(ename, set()).update(ps)

        if table_usage:
            for view_name, rows in table_usage.items():
                ps = self.table_view_to_panels.setdefault(view_name, set())
                for r in rows:
                    lay = r.get("layout") or ""
                    if lay in self.vta_to_panels:
                        ps.update(self.vta_to_panels[lay])
                    for t in r.get("tiles") or ():
                        for cname in t.get("screens") or ():
                            if cname in self.comp_to_panels:
                                ps.update(self.comp_to_panels[cname])
                            else:
                                hit = self._match_panel_by_name(cname)
                                ps.update(hit)
                        dname = t.get("description") or ""
                        if dname in self.desc_to_panels:
                            ps.update(self.desc_to_panels[dname])

        if tables_obj is not None:
            try:
                tables_obj.load()
                for v in tables_obj._views.values():
                    vname = v["name"]
                    cols = [c["m_columnID"] for c in v["tree"]["m_tableView"]["m_tableConfig"]]
                    fac, cov = tables_obj.factory_for(cols)
                    if not fac or cov <= 0:
                        continue
                    fname = fac["name"]
                    vps = set(self.table_view_to_panels.get(vname) or ())
                    if not vps:
                        stem, _ = split_screen_variant(vname)
                        vps = set(self.table_view_to_panels.get(stem) or ())
                    if vps:
                        self.table_factory_to_panels.setdefault(fname, set()).update(vps)
                # Map table factory cell VTAs -> factory panels
                for f in tables_obj._factories.values():
                    fname = f["name"]
                    fps = self.table_factory_to_panels.get(fname) or set(self._match_panel_by_name(fname))
                    if not fps:
                        continue
                    for row in f["tree"].get("m_rowData") or ():
                        g = (row.get("m_uxmlRef") or {}).get("m_AssetGUID") or ""
                        vname = guid_to_name.get(g)
                        if vname:
                            self.vta_to_panels.setdefault(vname, set()).update(fps)
            except Exception:
                pass

        for vn, ps in list(self.vta_to_panels.items()):
            stem, _ = split_screen_variant(vn)
            stem = _VTA_STEM_RE.sub("", stem)
            if stem and len(stem) >= 4:
                self.vta_stem_to_panels.setdefault(stem, set()).update(ps)

    def _match_panel_by_name(self, name: str) -> list[str]:
        if not name or not self.panel_ids:
            return []
        if name in self.panel_ids:
            return [name]
        base, _ = split_screen_variant(name)
        if base in self.panel_ids:
            return [base]
        stem = infer_screen_name(name, "other")
        for cand in (stem, stem + "Screen", stem + "Card", stem + "Tool"):
            if cand in self.panel_ids:
                return [cand]
        hits = self.panel_by_stem.get(stem.lower(), [])
        if hits:
            return hits[:3]
        return []

    def resolve_item(
        self,
        cat: str,
        name: str,
        summary: dict | None = None,
        extra_class_panels: dict[str, set[str]] | None = None,
    ) -> tuple[list[str], str, str | None]:
        """Return (screens, via, unmapped_reason). Empty screens -> caller routes to NOT_TIED."""
        base, _ = split_screen_variant(name)
        if cat == "composition":
            no_skin = re.sub(r"[-_]RR\d*$", "", name, flags=re.I)
            no_mode = re.sub(r"[-_](?:FMC|IM)$", "", no_skin, flags=re.I)
            ps = (
                self.comp_to_panels.get(name)
                or self.comp_to_panels.get(no_skin)
                or self.comp_to_panels.get(no_mode)
                or self.comp_to_panels.get(base)
            )
            if not ps and base:
                ps_acc: set[str] = set()
                for ck, cp in self.comp_to_panels.items():
                    if ck == base or ck.startswith(base + "-") or ck.startswith(base + "_"):
                        ps_acc.update(cp)
                ps = ps_acc or None
            if ps:
                return sorted(ps), "composition -> tile slot -> panel", None
            fb = self._match_panel_by_name(name)
            if fb:
                return sorted(fb), "composition name -> panel", None
            return [infer_screen_name(name, cat)], "composition name stem", None

        if cat == "composition_set":
            ps = self.set_to_panels.get(name) or self.set_to_panels.get(base)
            if ps:
                return sorted(ps), "composition set -> panel", None
            return self._match_panel_by_name(name) or [infer_screen_name(name, cat)], "composition set name", None

        if cat == "description":
            ps = self.desc_to_panels.get(name) or self.desc_to_panels.get(base)
            if ps:
                return sorted(ps), "tile description -> VTA -> composition -> panel", None
            fb = self._match_panel_by_name(name)
            if fb:
                return sorted(fb), "tile description name -> panel", None
            return [], "", "Tile description not placed on any mapped panel in layout dump"

        if cat == "element_set":
            ps = self.eset_to_panels.get(name) or self.eset_to_panels.get(base)
            if ps:
                return sorted(ps), "element set -> tile description -> panel", None
            fb = self._match_panel_by_name(name)
            if fb:
                return sorted(fb), "element set name -> panel", None
            return [], "", "Grid element set has no statically mapped tile descriptions"

        if cat == "uxml":
            ps = self.vta_to_panels.get(name) or self.vta_to_panels.get(base)
            if ps:
                return sorted(ps), "VTA -> layout/composition graph -> panel", None
            stem = _VTA_STEM_RE.sub("", base)
            if stem in self.vta_stem_to_panels:
                return sorted(self.vta_stem_to_panels[stem]), "VTA tile/row family -> panel", None
            fb = self._match_panel_by_name(name)
            if fb:
                return sorted(fb), "VTA name -> panel", None
            return [], "", "Template/helper VTA not statically referenced by any panel in layout dump"

        if cat == "table_view":
            ps = self.table_view_to_panels.get(name) or self.table_view_to_panels.get(base)
            if ps:
                return sorted(ps), "table view -> layout/tile -> panel", None
            fb = self._match_panel_by_name(name)
            if fb:
                return sorted(fb), "table view name -> panel", None
            return [], "", "Dynamic or user table view (chosen in game code; not in static table-view usage)"

        if cat == "table_factory":
            ps = self.table_factory_to_panels.get(name) or self.table_factory_to_panels.get(base)
            if ps:
                return sorted(ps), "table factory -> table view -> panel", None
            fb = self._match_panel_by_name(name)
            if fb:
                return sorted(fb), "table factory name -> panel", None
            return [], "", "Table factory not statically linked to a tracked table view"

        if cat == "navigation":
            fb = self._match_panel_by_name(name)
            if fb:
                return sorted(fb), "navigation asset -> panel", None
            return [], "", "Global navigation, calendar, or chart helper across screens"

        if cat == "texture":
            fb = self._match_panel_by_name(name)
            if fb and "icon" not in name.lower():
                return sorted(fb), "texture name -> panel", None
            return [], "", "Global texture/icon asset (atlas or C#-assigned image, not tied to one panel)"

        if cat == "style":
            return [], "", "Global stylesheet (see per-screen class matches where layouts use modified classes)"

        return [], "", "Bundle data object without a static screen link"


def _attach_item(
    by_screen: dict[str, dict[str, list[dict]]],
    variants_by_screen: dict[str, set[str]],
    scr: str,
    cat: str,
    entry: dict,
) -> None:
    by_screen.setdefault(scr, {}).setdefault(cat, []).append(entry)
    if entry.get("variant"):
        variants_by_screen.setdefault(scr, set()).add(entry["variant"])


def diff_skin_folder(
    skin_dir: Path | str,
    stock_dir: Path | str,
    bundle_filter: list[str] | None = None,
    progress: Callable[[str, float], None] | None = None,
    resolver: ScreenResolver | None = None,
) -> dict:
    """Diff every bundle in `skin_dir` against `stock_dir`, returning per-bundle, per-category,
    and per-screen summaries. Strictly read-only."""
    skin_root = Path(skin_dir)
    stock_root = Path(stock_dir)
    skin_source = detect_skin_source(skin_root)
    bundles = discover_skin_bundles(skin_root)
    if bundle_filter:
        want = set(bundle_filter)
        bundles = [b for b in bundles if b.name in want]

    reports = []
    totals = {"bundles": len(bundles), "added": 0, "removed": 0, "changed": 0, "unchanged": 0}
    by_category: dict[str, dict[str, int]] = {}
    by_screen: dict[str, dict[str, list[dict]]] = {}
    variants_by_screen: dict[str, set[str]] = {}
    compositions_changed: list[dict] = []

    raw_items: list[tuple[str, str, dict]] = []

    for i, sb in enumerate(bundles):
        if progress:
            progress(f"diffing {sb.name}", i / max(1, len(bundles)))
        stk = stock_root / sb.name
        rep = diff_bundle(sb, stk if stk.is_file() else None)
        reports.append(rep)
        for k in ("added", "removed", "changed", "unchanged"):
            totals[k] += rep["counts"].get(k, 0)
        for cat, cnts in rep["by_category"].items():
            agg = by_category.setdefault(cat, {"added": 0, "removed": 0, "changed": 0})
            for k in ("added", "removed", "changed"):
                agg[k] += cnts.get(k, 0)
        for kind in ("added", "removed", "changed"):
            for item in rep[kind]:
                raw_items.append((sb.name, kind, item))

    # Pass 1: resolve all non-style items and harvest skin VTA classes -> screens
    skin_class_panels: dict[str, set[str]] = {}
    style_items: list[tuple[str, str, dict]] = []

    for bname, kind, item in raw_items:
        cat = item.get("category") or "other"
        if cat == "style":
            style_items.append((bname, kind, item))
            continue
        _, variant = split_screen_variant(item["name"])
        summ = item.get("after_summary") or item.get("summary")
        if resolver is not None:
            screens, via, reason = resolver.resolve_item(cat, item["name"], summ)
        else:
            screens = [item.get("screen") or "Other"]
            via, reason = "name pattern", None

        if cat == "uxml" and isinstance(summ, dict):
            for cls_name in summ.get("classes") or ():
                if screens:
                    skin_class_panels.setdefault(cls_name, set()).update(screens)

        target_screens = screens if screens else [NOT_TIED]
        for scr in target_screens:
            entry = {
                "bundle": bname,
                "kind": kind,
                "type": item["type"],
                "name": item["name"],
                "field_count": item.get("field_count", 0),
                "source_label": skin_source["label"],
                "variant": variant,
                "via": via if screens else None,
                "unmapped_reason": None if screens else reason,
            }
            _attach_item(by_screen, variants_by_screen, scr, cat, entry)
        if cat == "composition" and kind in ("added", "changed"):
            compositions_changed.append({
                "name": item["name"],
                "bundle": bname,
                "kind": kind,
                "screen": target_screens[0],
                "variant": variant,
                "summary": summ,
            })

    # Pass 2: attach stylesheets (to NOT_TIED if global, plus screen-specific modified class hits)
    for bname, kind, item in style_items:
        _, variant = split_screen_variant(item["name"])
        before_sigs = ((item.get("before_summary") or {}).get("_class_sigs") or {})
        after_sigs = ((item.get("after_summary") or item.get("summary") or {}).get("_class_sigs") or {})
        changed_classes = sorted(
            cls for cls, sigs in after_sigs.items() if before_sigs.get(cls) != sigs
        )
        screen_to_classes: dict[str, list[str]] = {}
        if resolver is not None:
            for cls_name in changed_classes:
                ps = (resolver.class_to_panels.get(cls_name) or set()) | (skin_class_panels.get(cls_name) or set())
                if 1 <= len(ps) <= 12:
                    for scr in ps:
                        screen_to_classes.setdefault(scr, []).append(cls_name)

        sheet_global = len(screen_to_classes) > 12 or item["name"] in (
            "AlwaysAppliedStyleSheet", "FMColours", "FigmaGeneratedStyles",
        ) or item["name"].startswith("FMImages_") or resolver is None

        if not sheet_global and screen_to_classes:
            for scr, clses in sorted(screen_to_classes.items()):
                _attach_item(by_screen, variants_by_screen, scr, "style", {
                    "bundle": bname,
                    "kind": kind,
                    "type": item["type"],
                    "name": item["name"],
                    "field_count": item.get("field_count", 0),
                    "source_label": skin_source["label"],
                    "variant": variant,
                    "via": f"style class {', '.join('.' + c for c in clses[:3])} -> layout -> panel",
                    "unmapped_reason": None,
                })
        else:
            target = NOT_TIED if resolver is not None else (item.get("screen") or "Other")
            reason = (
                f"Global stylesheet ({len(changed_classes)} modified selector classes reaching {len(screen_to_classes)} screens)"
                if resolver is not None
                else None
            )
            _attach_item(by_screen, variants_by_screen, target, "style", {
                "bundle": bname,
                "kind": kind,
                "type": item["type"],
                "name": item["name"],
                "field_count": item.get("field_count", 0),
                "source_label": skin_source["label"],
                "variant": variant,
                "via": None if resolver is not None else "name pattern",
                "unmapped_reason": reason,
            })
            if resolver is not None:
                for scr, clses in sorted(screen_to_classes.items()):
                    clses_u = sorted(set(clses))
                    _attach_item(by_screen, variants_by_screen, scr, "style", {
                        "bundle": bname,
                        "kind": kind,
                        "type": "StyleClassRules",
                        "name": f"{item['name']} ({', '.join('.' + c for c in clses_u[:4])}{' ...' if len(clses_u) > 4 else ''})",
                        "field_count": len(clses_u),
                        "source_label": skin_source["label"],
                        "variant": variant,
                        "via": f"class -> layout -> panel ({len(clses_u)} classes)",
                        "derived": True,
                        "unmapped_reason": None,
                    })

        # Strip private _class_sigs before returning JSON-friendly summaries
        for key in ("before_summary", "after_summary", "summary"):
            if isinstance(item.get(key), dict) and "_class_sigs" in item[key]:
                item[key].pop("_class_sigs", None)

    # Strip private _class_sigs from bundle reports' non-style items too if present
    ranked = sorted(
        (
            (scr, sum(len(lst) for lst in cats.values()))
            for scr, cats in by_screen.items()
            if scr != NOT_TIED
        ),
        key=lambda x: (-x[1], x[0]),
    )
    default_screen = ranked[0][0] if ranked and ranked[0][1] > 0 else (NOT_TIED if by_screen.get(NOT_TIED) else None)
    screen_meta = {
        scr: {
            "count": sum(len(lst) for lst in cats.values()),
            "variants": sorted(variants_by_screen.get(scr, ())),
        }
        for scr, cats in by_screen.items()
    }

    if progress:
        progress("done", 1.0)
    return {
        "skin_dir": str(skin_root),
        "stock_dir": str(stock_root),
        "source": skin_source,
        "default_screen": default_screen,
        "screen_meta": screen_meta,
        "totals": totals,
        "by_category": by_category,
        "by_screen": {k: by_screen[k] for k in sorted(by_screen)},
        "compositions": sorted(compositions_changed, key=lambda c: c["name"]),
        "bundles": reports,
    }


def read_skin_composition(skin_dir: Path | str, composition_name: str) -> dict | None:
    """Read a single GridComposition MonoBehaviour typetree from a skin folder (read-only),
    for previewing with the rea engine without writing any file."""
    import UnityPy

    for b in discover_skin_bundles(Path(skin_dir)):
        if "tileslayouts" not in b.name.lower() and "tactics" not in b.name.lower():
            continue
        env = UnityPy.load(str(b))
        for obj in env.objects:
            if obj.type.name != "MonoBehaviour":
                continue
            try:
                if (obj.peek_name() or "") == composition_name:
                    return obj.read_typetree()
            except Exception:
                continue
    return None


PERSONAL_USE_NOTICE = (
    "Third-party skin rules and variables are imported for personal use and study only. "
    "Distributing third-party content requires the original author's permission."
)


def _extract_sheet_defs(bundle_path: Path, sheet_name: str) -> tuple[dict[str, str], list[dict]]:
    import UnityPy
    from . import uss

    env = UnityPy.load(bundle_path.read_bytes())
    cls_re = re.compile(r"\.([A-Za-z_][\w-]*)")
    vars_map: dict[str, str] = {}
    rules_list: list[dict] = []
    for obj in env.objects:
        if obj.type.name not in ("MonoBehaviour", "StyleSheet"):
            continue
        try:
            name = obj.peek_name() or ""
            if name != sheet_name:
                continue
            tree = obj.read_typetree()
        except Exception:
            continue
        if not isinstance(tree, dict) or "m_Rules" not in tree:
            continue
        smap = uss.selector_map(tree)
        for idx, r in enumerate(tree.get("m_Rules") or []):
            if not isinstance(r, dict):
                continue
            sels = smap[idx] if idx < len(smap) else []
            sel_str = ", ".join(uss.selector_text(c) for c in sels if isinstance(c, dict))
            if not sel_str:
                continue
            props: dict[str, str] = {}
            for p in r.get("m_Properties") or []:
                if not isinstance(p, dict):
                    continue
                pn = uss.prop_name(p)
                pv, _ = uss.value_text(tree, p.get("m_Values") or [])
                props[pn] = pv
            if not props:
                continue
            if uss.is_token_rule(sels):
                for pn, pv in props.items():
                    if pn.startswith("--"):
                        vars_map[pn] = pv
            else:
                classes = sorted(set(cls_re.findall(sel_str)))
                rules_list.append({"selector": sel_str, "classes": classes, "props": props})
        break
    return vars_map, rules_list


def read_skin_style_definitions(
    skin_dir: Path | str,
    stock_dir: Path | str | None = None,
    sheet: str = "AlwaysAppliedStyleSheet",
    query: str = "",
    limit: int = 150,
) -> dict:
    """Read custom classes/rules and CSS variables from an inspected skin's StyleSheet (strictly read-only)."""
    skin_root = Path(skin_dir)
    source = detect_skin_source(skin_root)
    bundles = discover_skin_bundles(skin_root)
    style_b = next((b for b in bundles if b.name == "ui-styles_assets_default.bundle"), None)
    if style_b is None:
        style_b = next((b for b in bundles if "ui-styles_assets" in b.name), None)
    if style_b is None:
        raise FileNotFoundError(f"no ui-styles bundle found in {skin_root}")

    skin_vars, skin_rules = _extract_sheet_defs(style_b, sheet)
    stock_vars: dict[str, str] = {}
    stock_rules_map: dict[str, dict[str, str]] = {}
    if stock_dir:
        stk_b = Path(stock_dir) / style_b.name
        if stk_b.is_file():
            stock_vars, stk_rules = _extract_sheet_defs(stk_b, sheet)
            for r in stk_rules:
                stock_rules_map[r["selector"]] = r["props"]

    ql = query.strip().lower()
    var_rows = []
    for k, v in skin_vars.items():
        if ql and ql not in k.lower() and ql not in v.lower():
            continue
        is_new = k not in stock_vars or stock_vars[k] != v
        var_rows.append({
            "name": k,
            "value": v,
            "is_new": is_new,
            "uss_text": f":root {{\n    {k}: {v};\n}}",
        })
    var_rows.sort(key=lambda x: (not x["is_new"], x["name"]))

    rule_rows = []
    for r in skin_rules:
        sel = r["selector"]
        if ql and ql not in sel.lower() and not any(ql in c.lower() for c in r["classes"]):
            continue
        is_new = sel not in stock_rules_map or stock_rules_map[sel] != r["props"]
        body = "".join(f"    {pk}: {pv};\n" for pk, pv in r["props"].items())
        rule_rows.append({
            "selector": sel,
            "classes": r["classes"],
            "props": r["props"],
            "is_new": is_new,
            "uss_text": f"{sel} {{\n{body}}}",
        })
    rule_rows.sort(key=lambda x: (not x["is_new"], x["selector"]))

    return {
        "skin_dir": str(skin_root),
        "sheet": sheet,
        "source": source,
        "personal_use_notice": PERSONAL_USE_NOTICE,
        "variables_total": len(var_rows),
        "rules_total": len(rule_rows),
        "variables": var_rows[:limit],
        "rules": rule_rows[:limit],
    }
