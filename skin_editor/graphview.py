"""Screen-level view of the dependency graph as a UiDocument-style `Graph` (Stage 4C; D2 of the owner's decisions).

This is a PROJECTION: it reads the resolved edges of the registry (`depgraph`) and fills the existing `skin_editor.uidoc.model.Graph` (the same node/edge/provenance
classes the UiDocument builder uses). It never populates relationships on its own and never reads a bundle. Identity and locator keys follow the UiDocument model unchanged:
a physical locator is {bundle, file (the CAB), path_id}; an edge carries `read_from` {bundle, object, field} naming where in the serialized data it was read; `assumed` is
true only for a relationship that was not read from data (none here: ambiguous and unresolved references are read from data, so they appear as gap nodes with assumed false).

Vocabulary mapping (registry relation -> UiDocument-style edge type):
  uxml_reference              references_layout        inline_stylesheet     has_inline_sheet        stylesheet            uses_stylesheet
  composition_set_reference   uses_composition_set     composition_ref       has_composition         stylesheet_asset      uses_asset
  texture_sprite              uses_texture             material_texture      uses_texture            guid_reference/pptr   references_asset
  every asset also gets `in_bundle` to its bundle node (as the UiDocument builder does).
The whole-installation graph stays in the registry; this view is a bounded walk from one panel or asset."""
from collections import deque

from . import depgraph
from .uidoc.model import Graph

TYPE_MAP = {"uxml_reference": "references_layout", "inline_stylesheet": "has_inline_sheet", "stylesheet": "uses_stylesheet", "composition_set_reference": "uses_composition_set",
            "composition_ref": "has_composition", "stylesheet_asset": "uses_asset", "texture_sprite": "uses_texture", "material_texture": "uses_texture"}
KIND_OF_ROLE = {"PanelDescription": "panel", "VisualTreeAsset": "layout", "StyleSheet": "style_sheet", "TileCompositionSet": "composition_set", "GridComposition": "composition",
                "Texture2D": "texture", "Sprite": "sprite", "SpriteAtlas": "sprite_atlas", "Material": "material", "Font": "font"}


def node_id(bundle, cab, path_id):
    return "asset:%s|%s|%s" % (bundle, cab, path_id)


def _node(g, a):
    role = a.get("role") or a.get("type")
    nid = node_id(a["bundle"], a["cab"], a["path_id"])
    g.node(nid, KIND_OF_ROLE.get(role, "asset"), name=a.get("name"), type=a.get("type"), role=a.get("role"), locator={"bundle": a["bundle"], "file": a["cab"], "path_id": a["path_id"]})
    g.node("bundle:" + a["bundle"], "bundle", file=a["bundle"])
    g.edge(nid, "bundle:" + a["bundle"], "in_bundle", {"bundle": a["bundle"], "object": a["path_id"], "field": None})
    return nid


def project(registry, start, max_depth=8, max_nodes=500, relations=None):
    """Walk the resolved edges from `start` ({bundle, cab, path_id}) and return {"graph": Graph, "root": node id, "stats": {...}}. Ambiguous and unresolved references become
    gap nodes (kind ambiguous_reference / unresolved_reference) so nothing is hidden. `relations` limits the walk to those registry relations (default: all asset relations)."""
    g = Graph()
    root = (start["bundle"], start["cab"], str(start["path_id"]))
    ra = registry.get_asset(*root)
    if ra is None:
        raise KeyError("no such inventory asset: %s / %s / %s" % root)
    rid = _node(g, ra)
    seen, q, depth = {root}, deque([root]), {root: 0}
    gaps = truncated = 0
    while q:
        cur = q.popleft()
        if depth[cur] >= max_depth:
            truncated = 1
            continue
        for e in depgraph.uses(registry, cur[0], cur[1], cur[2], limit=100000)["edges"]:
            if e["kind"] in ("bundle_dependency", "external_file"):
                continue
            if relations and e["relation"] not in relations:
                continue
            frm = node_id(*cur)
            read_from = {"bundle": cur[0], "object": cur[2], "field": e["provenance"]}
            etype = TYPE_MAP.get(e["relation"], "references_asset")
            if e["resolution"] == "resolved" and e["dst"] and e["dst"].get("path_id"):
                d = e["dst"]
                key = (d["bundle"], d["cab"], d["path_id"])
                tgt = registry.get_asset(*key)
                if tgt is None:
                    continue
                tid = _node(g, tgt)
                g.edge(frm, tid, etype, dict(read_from, basis=e["basis"], count=e["count"]))
                if key not in seen:
                    if len(seen) >= max_nodes:
                        truncated = 1
                        continue
                    seen.add(key)
                    depth[key] = depth[cur] + 1
                    q.append(key)
            else:
                gaps += 1
                gid = "gap:%s" % e["id"]
                g.node(gid, "ambiguous_reference" if e["resolution"] == "ambiguous" else "unresolved_reference", reason=e["reason"], target=e["target"], candidates=e.get("candidates"))
                g.edge(frm, gid, etype if e["resolution"] == "ambiguous" else "references_asset", dict(read_from, resolution=e["resolution"]))
    return {"graph": g, "root": rid, "stats": {"nodes": len(g.nodes), "edges": len(g.edges), "assets": len(seen), "gaps": gaps, "truncated": bool(truncated)}}


def project_panel(registry, panel_id, **kw):
    r = registry.search_assets(panel_id=str(panel_id), limit=2)
    if not r["assets"]:
        raise KeyError("no such inventory asset: panel %s" % panel_id)
    a = r["assets"][0]
    return project(registry, {"bundle": a["bundle"], "cab": a["cab"], "path_id": a["path_id"]}, **kw)
