"""Installation-wide asset dependency graph (Stage 4C; docs/rea/STAGE-4A-ARCHITECTURE.md section 6.4). READ ONLY: bundles are opened for reading, the only writes are to
the registry database (tables `edges`, `edge_candidates`, `graph_state`, and the `role` column of `assets`).

What an edge is. Every edge is a reference READ FROM SERIALIZED DATA, never inferred from names:
  pptr               an object reference {m_FileID, m_PathID} inside an asset; m_FileID 0 is the same serialized file, m_FileID n is externals[n-1] of the bundle
  guid_reference     an AssetReference ({m_AssetGUID, ...}) inside an asset, resolved through the bundles' AssetBundle containers (the GUID keys)
  bundle_dependency  AssetBundle.m_Dependencies (a CAB name)             external_file   the serialized file's externals list
`direct` is 1 for all of these. Edges that are computed from others (a bundle-to-bundle summary of asset edges) are DERIVED and returned with direct = false; they are not stored.

The three-step life of an edge: (1) EXTRACT per bundle, in one transaction: the raw target exactly as serialized plus provenance (the field path, up to 5 samples; identical
references inside one asset collapse into one edge with a count). (2) RESOLVE over the whole inventory (cheap, repeatable): CAB name -> bundle through the externals, object
lookup by (CAB, PathID), GUID lookup through the containers. (3) QUERY.
Resolution values: resolved | unresolved (with a reason) | ambiguous (several candidates, all kept in `edge_candidates`). A GUID that names several assets is narrowed only by evidence: (1) 'guid_container+layout_pair': the container lists exactly a VisualTreeAsset and a StyleSheet that is that
layout's own inline sheet (read from the layout's inlineSheet pointer), so the GUID names the layout; (2) the weaker 'guid_container+field_role_hint': the referring field (`uxml`, `m_Usings`,
`AssetRef`, `visualTreeAsset`) is known to reference a VisualTreeAsset. Otherwise it stays ambiguous and every candidate is kept.
`role` is a structural label of a MonoBehaviour read from its own fields (m_VisualTree -> VisualTreeAsset, m_Rules -> StyleSheet, m_gridBreakpointCompositionData ->
TileCompositionSet, m_gridComponents -> GridComposition, m_panelDescription -> PanelDescription), the same tests the existing readers use."""
import json
import re
import time
from collections import defaultdict, deque

from . import bundles

KINDS = ("pptr", "guid_reference", "bundle_dependency", "external_file")
SCOPE_TYPES = ("MonoBehaviour", "Sprite", "SpriteAtlas", "Material")      # asset types whose typetrees are read for references
SKIP_TOP_FIELDS = ("m_Script", "m_GameObject")                            # a MonoBehaviour's script and owner pointers are not asset relationships
MAX_REFS_PER_ASSET = 20000
NULL_GUIDS = ("", "0" * 32)
ROLE_FIELDS = ("uxml", "m_Usings", "AssetRef", "visualTreeAsset")        # fields that, by the serialized data of the game, reference a VisualTreeAsset
CAB = re.compile(r"(?i)(cab-[0-9a-f]{32})")


class Stale(Exception):
    """The bundle on disk no longer matches its inventory record; scan the inventory again first."""


class GraphCancelled(Exception):
    def __init__(self, summary):
        super().__init__("graph build cancelled")
        self.summary = summary


def _now():
    return time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())


# ---------------------------------------------------------------- extraction (pure functions, no I/O)
def classify_role(type_name, tree):
    """Structural role of an object: for a MonoBehaviour from its own fields, else the Unity type for the few types the graph labels."""
    if type_name != "MonoBehaviour":
        return type_name if type_name in ("Sprite", "SpriteAtlas", "Material", "Texture2D", "Font") else None
    if not isinstance(tree, dict):
        return None
    for field, role in (("m_VisualTree", "VisualTreeAsset"), ("m_Rules", "StyleSheet"), ("m_gridBreakpointCompositionData", "TileCompositionSet"),
                        ("m_gridComponents", "GridComposition"), ("m_panelDescription", "PanelDescription")):
        if field in tree:
            return role
    return None


def _join(chain):
    parts = []
    while chain:
        chain, seg = chain
        parts.append(seg)
    out = ""
    for seg in reversed(parts):
        out += seg if seg.startswith("[") or not out else "/" + seg
    return out


def extract_refs(tree, max_refs=MAX_REFS_PER_ASSET):
    """References inside one typetree: ({(kind, file_id, path_id, guid): {"count", "samples"}}, truncated). Null object pointers (path id 0), empty GUIDs and the
    MonoBehaviour script/owner pointers are not relationships and are skipped. Identical references collapse into one entry with a count and up to 5 field paths."""
    found, n, truncated = {}, 0, False

    def add(key, chain):
        nonlocal n
        e = found.get(key)
        if e is None:
            if n >= max_refs:
                return True
            n += 1
            e = found[key] = {"count": 0, "samples": []}
        e["count"] += 1
        if len(e["samples"]) < 5:
            e["samples"].append(_join(chain))
        return False

    stack = [(tree, None)]
    while stack:
        node, chain = stack.pop()
        if isinstance(node, dict):
            if len(node) == 2 and "m_FileID" in node and "m_PathID" in node:
                pid = node["m_PathID"]
                if pid not in (0, None):
                    if add(("pptr", int(node["m_FileID"]), str(pid), ""), chain):
                        truncated = True
                continue
            g = node.get("m_AssetGUID")
            if isinstance(g, str):
                g = g.lower()
                if g not in NULL_GUIDS and add(("guid_reference", -1, "", g), chain):
                    truncated = True
                continue
            for k, v in node.items():
                if chain is None and k in SKIP_TOP_FIELDS:
                    continue
                if isinstance(v, (dict, list)):
                    stack.append((v, (chain, str(k))))
        elif isinstance(node, list):
            for i, v in enumerate(node):
                if isinstance(v, (dict, list)):
                    stack.append((v, (chain, "[%d]" % i)))
    return found, truncated


def cab_of(path):
    """The lower-case CAB name inside an externals entry ('archive:/CAB-x/CAB-x') or a dependency name ('cab-x'), or ''."""
    m = CAB.search(path or "")
    return m.group(1).lower() if m else ""


def bundle_level_edges(rec):
    """The bundle's own dependency and external-file edges, from its inventory record (no file is read)."""
    out = []
    for dep in rec.get("dependencies") or []:
        out.append({"src_bundle": rec["rel_path"], "src_cab": "", "src_path_id": "", "kind": "bundle_dependency", "relation": None, "t_file_id": -1,
                    "t_path_id": "", "t_guid": "", "t_cab": cab_of(dep) or str(dep).lower(), "direct": 1, "count": 1, "provenance": "AssetBundle/m_Dependencies", "samples": json.dumps(["AssetBundle/m_Dependencies"])})
    for i, ext in enumerate(rec.get("externals") or []):
        out.append({"src_bundle": rec["rel_path"], "src_cab": rec.get("cab") or "", "src_path_id": "", "kind": "external_file", "relation": None, "t_file_id": i + 1,
                    "t_path_id": "", "t_guid": "", "t_cab": cab_of(ext) or str(ext).lower(), "direct": 1, "count": 1, "provenance": "externals[%d]" % i, "samples": json.dumps([str(ext)])})
    merged = {}
    for e in out:                                   # one edge per distinct target: duplicates add to the count and keep their provenance
        key = (e["kind"], e["t_cab"], e["t_file_id"])
        if key in merged:
            merged[key]["count"] += 1
            merged[key]["samples"] = json.dumps(json.loads(merged[key]["samples"]) + json.loads(e["samples"]))
        else:
            merged[key] = dict(e)
    return list(merged.values())


def extract_bundle(rec):
    """(edges, roles, notes) of one bundle from its file. Raises Stale when the file changed since the inventory; any other exception means the bundle could not be
    parsed (the caller records it and keeps no edges)."""
    from pathlib import Path
    path = Path(rec["abs_path"])
    try:
        st = path.stat()
    except OSError as e:
        raise Stale("file is gone: %s" % e)
    if st.st_size != rec["size"] or st.st_mtime_ns != rec["mtime_ns"]:
        raise Stale("size or modification time differs from the inventory record")
    env = bundles.open_readonly(path)
    edges, roles, errors, truncated = bundle_level_edges(rec), {}, 0, 0
    for cab, sf in ((n, v) for n, v in env.file.files.items() if hasattr(v, "objects")):
        for pid, obj in sf.objects.items():
            tname = obj.type.name
            if tname not in SCOPE_TYPES:
                continue
            try:
                tree = obj.read_typetree()
            except Exception:
                errors += 1
                continue
            role = classify_role(tname, tree)
            if role:
                roles[(cab, str(pid))] = role
            refs, trunc = extract_refs(tree)
            truncated += 1 if trunc else 0
            for (kind, fid, tpid, guid), info in refs.items():
                edges.append({"src_bundle": rec["rel_path"], "src_cab": cab, "src_path_id": str(pid), "kind": kind, "relation": None, "t_file_id": fid, "t_path_id": tpid,
                              "t_guid": guid, "t_cab": "", "direct": 1, "count": info["count"], "provenance": info["samples"][0], "samples": json.dumps(info["samples"])})
    notes = []
    if errors:
        notes.append("%d object(s) could not be read" % errors)
    if truncated:
        notes.append("%d asset(s) hit the reference limit" % truncated)
    return edges, roles, notes


# ---------------------------------------------------------------- build (per-bundle transactions, incremental)
def in_scope(rec, scope, only=None):
    if only:
        return rec["rel_path"] in only
    return scope == "all" or (scope == "ui" and (rec.get("kind") or "").startswith("ui-"))


def build(registry, scope="ui", only=None, rebuild=False, progress=None, cancel=None, extractor=extract_bundle):
    """Build or refresh the graph from the inventory. Every inventoried bundle gets its bundle-level edges; bundles in `scope` ('ui' | 'all') or listed in `only` also get
    asset-level edges. A bundle whose inventory sha256 equals its graph sha256 (and whose depth is unchanged) is skipped. One failing bundle is recorded as failed with NO
    edges and the build continues. cancel() is honoured between bundles. Ends with resolve()."""
    progress = progress or (lambda m, f: None)
    cancel = cancel or (lambda: False)
    recs = {k: v for k, v in registry.all_bundles().items() if v["state"] in ("valid", "partially_valid")}
    states = registry.graph_states()
    gone = registry.drop_missing_graph(set(recs))
    summary = {"scope": scope, "bundles": len(recs), "built": 0, "bundle_only": 0, "skipped": 0, "failed": 0, "stale": 0, "removed": len(gone), "cancelled": False, "edges": 0, "seconds": 0.0}
    t0 = time.time()
    order = sorted(recs)
    total = sum((recs[r].get("object_count") or 1) for r in order) or 1
    done = 0
    for i, rel in enumerate(order):
        rec = recs[rel]
        if cancel():
            summary["cancelled"] = True
            summary["seconds"] = round(time.time() - t0, 2)
            resolve(registry)
            raise GraphCancelled(dict(summary, resolution=registry.graph_summary()))
        progress("%s (%d of %d)" % (rel, i + 1, len(order)), done / total)
        done += rec.get("object_count") or 1
        want_assets = in_scope(rec, scope, only)
        old = states.get(rel)
        if not rebuild and old and old["sha256"] == rec["sha256"] and old["state"] in ("built", "bundle_only") and (old["state"] == "built" or not want_assets):
            summary["skipped"] += 1
            continue
        try:
            if want_assets:
                edges, roles, notes = extractor(rec)
                registry.replace_bundle_graph(rel, rec["sha256"], edges, roles, "built", note="; ".join(notes) or None)
                summary["built"] += 1
            else:
                registry.replace_bundle_graph(rel, rec["sha256"], bundle_level_edges(rec), None, "bundle_only")
                summary["bundle_only"] += 1
        except Stale as e:
            registry.fail_bundle_graph(rel, rec["sha256"], "stale: %s" % e)
            summary["stale"] += 1
        except Exception as e:                       # one failing bundle never stops the build and never leaves partial edges
            registry.fail_bundle_graph(rel, rec["sha256"], "%s: %s" % (type(e).__name__, e))
            summary["failed"] += 1
    progress("resolving references", 0.99)
    res = resolve(registry)
    summary.update(edges=registry.graph_summary()["edges"], resolution=res, seconds=round(time.time() - t0, 2))
    progress("done", 1.0)
    return summary


# ---------------------------------------------------------------- resolution (whole inventory, repeatable)
def expected_role(samples):
    for s in samples:
        for seg in re.split(r"[/\[\]]+", s or ""):
            if seg in ROLE_FIELDS:
                return "VisualTreeAsset"
    return None


def relation_for(kind, src_role, dst_role, dst_type, provenance):
    if kind in ("bundle_dependency", "external_file"):
        return kind
    r = dst_role or dst_type
    if kind == "guid_reference":
        return "uxml_reference" if r == "VisualTreeAsset" else "guid_reference"
    if src_role == "VisualTreeAsset" and r == "StyleSheet":
        return "inline_stylesheet" if "inlineSheet" in (provenance or "") or "inlineStyle" in (provenance or "") else "stylesheet"
    if src_role == "VisualTreeAsset" and r == "TileCompositionSet":
        return "composition_set_reference"
    if src_role == "TileCompositionSet" and r == "GridComposition":
        return "composition_ref"
    if src_role == "StyleSheet" and r in ("Texture2D", "Sprite", "Font"):
        return "stylesheet_asset"
    if src_role in ("Sprite", "SpriteAtlas") and r in ("Texture2D", "SpriteAtlas"):
        return "texture_sprite"
    if src_role == "Material" and r == "Texture2D":
        return "material_texture"
    return "pptr"


def _layout_pair(hits, inline):
    """A container GUID that lists exactly one VisualTreeAsset and one StyleSheet where that sheet is the layout's own inline sheet (read from the layout's inlineSheet pointer)
    names the LAYOUT: the pair is how the game's layout bundles key a layout (Stage 2D: SquadScreen's GUID lists the layout and its inline sheet). Returns the layout row or None."""
    if len(hits) != 2:
        return None
    vta = [h for h in hits if (h[3] or h[4]) == "VisualTreeAsset"]
    sheet = [h for h in hits if (h[3] or h[4]) == "StyleSheet"]
    if len(vta) == 1 and len(sheet) == 1 and inline.get((vta[0][0], vta[0][1], vta[0][2])) == sheet[0][2] and sheet[0][:2] == vta[0][:2]:
        return vta[0]
    return None


def resolve(registry):
    """Resolve every stored edge against the current inventory. Deterministic and repeatable: it recomputes dst_*, resolution, reason, basis, relation and the candidates of
    every edge, so a change in ANY bundle is picked up without re-reading the source bundles. Returns counts by resolution."""
    with registry._db() as db:
        cab_bundles = defaultdict(set)
        for b, c in db.execute("SELECT DISTINCT bundle, cab FROM assets"):
            cab_bundles[c.lower()].add(b)
        objs, guids = defaultdict(list), defaultdict(list)
        for b, c, p, g, role, typ in db.execute("SELECT bundle, cab, path_id, guid, role, type FROM assets"):
            row = (b, c, p, role, typ)
            objs[(c.lower(), p)].append(row)
            if g:
                guids[g].append(row)
        roles = {(b, c, p): (role, typ) for lst in objs.values() for (b, c, p, role, typ) in lst}
        externals = {r[0]: json.loads(r[1]) if r[1] else [] for r in db.execute("SELECT rel_path, externals FROM bundles")}
        inline = {}                                  # (bundle, cab, layout path id) -> inline style sheet path id, READ from the layout's own inlineSheet pointer (same file)
        for r in db.execute("SELECT src_bundle, src_cab, src_path_id, t_path_id FROM edges WHERE kind='pptr' AND t_file_id=0 AND (provenance='inlineSheet' OR provenance='inlineStyle')"):
            if (roles.get((r[0], r[1], r[2])) or (None,))[0] == "VisualTreeAsset":
                inline[(r[0], r[1], r[2])] = r[3]
        updates, cands, counts = [], [], defaultdict(int)
        for e in db.execute("SELECT * FROM edges").fetchall():
            src_role = (roles.get((e["src_bundle"], e["src_cab"], e["src_path_id"])) or (None, None))[0] if e["src_path_id"] else None
            samples = json.loads(e["samples"]) if e["samples"] else []
            res, reason, basis, dst, cand = "unresolved", None, None, (None, None, None), []
            kind = e["kind"]
            if kind in ("bundle_dependency", "external_file"):
                cab = e["t_cab"]
                bs = cab_bundles.get(cab)
                if not cab.startswith("cab-"):
                    reason = "builtin_resource"
                elif not bs:
                    reason = "cab_not_in_inventory"
                elif len(bs) == 1:
                    res, dst = "resolved", (next(iter(bs)), None, None)
                else:
                    res, cand = "ambiguous", [(b, None, None, None) for b in sorted(bs)]
            elif kind == "pptr":
                if e["t_file_id"] == 0:
                    cab = e["src_cab"].lower()
                else:
                    ext = externals.get(e["src_bundle"], [])
                    idx = e["t_file_id"] - 1
                    cab = cab_of(ext[idx]) if 0 <= idx < len(ext) else ""
                    if not cab:
                        reason = "bad_file_id" if not (0 <= idx < len(ext)) else "builtin_resource"
                if cab:
                    hits = objs.get((cab, e["t_path_id"]), [])
                    if len(hits) == 1:
                        res, dst = "resolved", hits[0][:3]
                    elif len(hits) > 1:
                        res, cand = "ambiguous", [(b, c, p, r) for b, c, p, r, _t in hits]
                    else:
                        reason = "object_not_in_inventory" if cab in cab_bundles else "cab_not_in_inventory"
            elif kind == "guid_reference":
                hits = guids.get(e["t_guid"], [])
                if len(hits) == 1:
                    res, dst, basis = "resolved", hits[0][:3], "guid_container"
                elif len(hits) > 1:
                    cand = [(b, c, p, r or t) for b, c, p, r, t in hits]
                    pair = _layout_pair(hits, inline)
                    want = expected_role(samples)
                    narrowed = [h for h in hits if (h[3] or h[4]) == want] if want else []
                    if pair:
                        res, dst, basis = "resolved", pair[:3], "guid_container+layout_pair"
                    elif len(narrowed) == 1:
                        res, dst, basis = "resolved", narrowed[0][:3], "guid_container+field_role_hint"
                    else:
                        res, basis = "ambiguous", "guid_container"
                else:
                    reason = "guid_not_in_inventory"
            dst_role = (roles.get(dst) or (None, None)) if dst[1] else (None, None)
            rel = relation_for(kind, src_role, dst_role[0], dst_role[1], e["provenance"])
            updates.append((rel, dst[0], dst[1], dst[2], res, reason, basis, e["id"]))
            for c in cand:
                cands.append((e["id"],) + tuple(c))
            counts[res] += 1
        db.execute("DELETE FROM edge_candidates")
        db.executemany("UPDATE edges SET relation=?, dst_bundle=?, dst_cab=?, dst_path_id=?, resolution=?, reason=?, basis=? WHERE id=?", updates)
        db.executemany("INSERT INTO edge_candidates (edge_id, bundle, cab, path_id, role) VALUES (?,?,?,?,?)", cands)
    return dict(counts)


# ---------------------------------------------------------------- queries
def _ref(db, bundle, cab, path_id):
    if bundle is None:
        return None
    if cab is None or path_id is None:
        return {"bundle": bundle, "cab": None, "path_id": None, "name": None, "type": None, "role": None}
    r = db.execute("SELECT name, type, role FROM assets WHERE bundle=? AND cab=? AND path_id=?", (bundle, cab, path_id)).fetchone()
    return {"bundle": bundle, "cab": cab, "path_id": path_id, "name": r[0] if r else None, "type": r[1] if r else None, "role": r[2] if r else None}


def _edge_view(db, e, cand_cache=None):
    d = {"id": e["id"], "kind": e["kind"], "relation": e["relation"], "direct": bool(e["direct"]), "resolution": e["resolution"], "reason": e["reason"], "basis": e["basis"],
         "count": e["count"], "provenance": e["provenance"], "samples": json.loads(e["samples"]) if e["samples"] else [],
         "src": _ref(db, e["src_bundle"], e["src_cab"] or None, e["src_path_id"] or None) if e["src_path_id"] else {"bundle": e["src_bundle"], "cab": None, "path_id": None, "name": None, "type": None, "role": None},
         "dst": _ref(db, e["dst_bundle"], e["dst_cab"], e["dst_path_id"]),
         "target": {"file_id": e["t_file_id"] if e["t_file_id"] >= 0 else None, "path_id": e["t_path_id"] or None, "guid": e["t_guid"] or None, "cab": e["t_cab"] or None}}
    if e["resolution"] == "ambiguous" or (e["basis"] or "").startswith("guid_container+"):
        d["candidates"] = [{"bundle": r[0], "cab": r[1], "path_id": r[2], "role": r[3]} for r in db.execute("SELECT bundle, cab, path_id, role FROM edge_candidates WHERE edge_id=?", (e["id"],))]
    return d


def _derived_bundle_edges(db, bundle, outgoing):
    if outgoing:
        rows = db.execute("SELECT dst_bundle AS other, COUNT(*) AS n, GROUP_CONCAT(DISTINCT relation) AS rel FROM edges WHERE src_bundle=? AND src_path_id!='' AND resolution='resolved' "
                          "AND dst_bundle IS NOT NULL AND dst_bundle!=src_bundle GROUP BY dst_bundle", (bundle,)).fetchall()
    else:
        rows = db.execute("SELECT src_bundle AS other, COUNT(*) AS n, GROUP_CONCAT(DISTINCT relation) AS rel FROM edges WHERE dst_bundle=? AND src_path_id!='' AND resolution='resolved' "
                          "AND src_bundle!=dst_bundle GROUP BY src_bundle", (bundle,)).fetchall()
    out = []
    for r in rows:
        a, b = (bundle, r["other"]) if outgoing else (r["other"], bundle)
        out.append({"id": None, "kind": "bundle_reference", "relation": r["rel"], "direct": False, "resolution": "resolved", "reason": None, "basis": "summary of %d asset reference(s)" % r["n"],
                    "count": r["n"], "provenance": None, "samples": [], "src": {"bundle": a, "cab": None, "path_id": None}, "dst": {"bundle": b, "cab": None, "path_id": None}, "target": {}})
    return out


def uses(registry, bundle, cab=None, path_id=None, kinds=None, limit=500, offset=0):
    """Edges leaving an asset (bundle + cab + path_id) or, with only `bundle`, the bundle's own dependency edges plus derived bundle-to-bundle summaries (direct = false)."""
    kinds = list(kinds) if kinds else None
    with registry._db() as db:
        if path_id is None:
            q, args = "FROM edges WHERE src_bundle=? AND src_path_id=''", [bundle]
        else:
            q, args = "FROM edges WHERE src_bundle=? AND src_cab=? AND src_path_id=?", [bundle, cab, str(path_id)]
        if kinds:
            q += " AND kind IN (%s)" % ",".join("?" * len(kinds))
            args += kinds
        total = db.execute("SELECT COUNT(*) " + q, args).fetchone()[0]
        rows = db.execute("SELECT * " + q + " ORDER BY id LIMIT ? OFFSET ?", args + [int(limit), int(offset)]).fetchall()
        out = [_edge_view(db, r) for r in rows]
        if path_id is None:
            out += _derived_bundle_edges(db, bundle, True)
    return {"total": total, "edges": out}


def used_by(registry, bundle, cab=None, path_id=None, kinds=None, limit=500, offset=0):
    """Edges arriving at an asset: resolved edges to it, plus ambiguous edges that list it among their candidates (marked via_candidate). With only `bundle`: bundle-level edges
    from bundles that depend on it plus derived summaries."""
    kinds = list(kinds) if kinds else None
    with registry._db() as db:
        extra = ""
        if kinds:
            extra = " AND e.kind IN (%s)" % ",".join("?" * len(kinds))
        if path_id is None:
            sql = "SELECT e.* FROM edges e WHERE e.dst_bundle=? AND e.dst_cab IS NULL AND e.src_path_id=''" + extra
            args = [bundle] + (kinds or [])
            rows = db.execute(sql + " ORDER BY e.id LIMIT ? OFFSET ?", args + [int(limit), int(offset)]).fetchall()
            out = [_edge_view(db, r) for r in rows] + _derived_bundle_edges(db, bundle, False)
            return {"total": len(out), "edges": out}
        sql = ("SELECT e.*, 0 AS via_candidate FROM edges e WHERE e.dst_bundle=? AND e.dst_cab=? AND e.dst_path_id=?" + extra +
               " UNION ALL SELECT e.*, 1 AS via_candidate FROM edges e JOIN edge_candidates c ON c.edge_id=e.id WHERE e.resolution='ambiguous' AND c.bundle=? AND c.cab=? AND c.path_id=?" + extra)
        args = [bundle, cab, str(path_id)] + (kinds or []) + [bundle, cab, str(path_id)] + (kinds or [])
        rows = db.execute(sql + " ORDER BY id LIMIT ? OFFSET ?", args + [int(limit), int(offset)]).fetchall()
        out = []
        for r in rows:
            v = _edge_view(db, r)
            v["via_candidate"] = bool(r["via_candidate"])
            out.append(v)
        return {"total": len(out), "edges": out}


def reachable(registry, bundle, cab, path_id, direction="uses", max_depth=6, max_nodes=2000):
    """Breadth-first closure over resolved edges from one asset. Returns nodes with their depth, the edges walked, the cycles found (strongly connected groups of more than one
    node, and self references) and whether the limits cut the walk. Ambiguous and unresolved edges are listed, never followed."""
    start = (bundle, cab, str(path_id))
    seen, depth, edges, unresolved = {start: 0}, {start: 0}, [], []
    q = deque([start])
    cut = False
    fn = uses if direction == "uses" else used_by
    while q:
        cur = q.popleft()
        if depth[cur] >= max_depth:
            cut = True
            continue
        res = fn(registry, cur[0], cur[1], cur[2], limit=100000)
        for e in res["edges"]:
            other = e["dst"] if direction == "uses" else e["src"]
            if e["resolution"] != "resolved" or not other or not other.get("path_id"):
                if e["resolution"] != "resolved":
                    unresolved.append({"from": cur, "edge": e["id"], "resolution": e["resolution"], "reason": e["reason"]})
                continue
            nxt = (other["bundle"], other["cab"], other["path_id"])
            edges.append({"from": cur, "to": nxt, "id": e["id"], "relation": e["relation"], "direct": e["direct"]})
            if nxt not in seen:
                if len(seen) >= max_nodes:
                    cut = True
                    continue
                seen[nxt] = depth[nxt] = depth[cur] + 1
                q.append(nxt)
    return {"start": start, "direction": direction, "nodes": [{"bundle": k[0], "cab": k[1], "path_id": k[2], "depth": v} for k, v in seen.items()], "edges": edges,
            "cycles": _cycles(seen, edges), "unresolved": unresolved, "truncated": cut}


def _cycles(nodes, edges):
    """Strongly connected components of more than one node and self loops (iterative Tarjan)."""
    adj = defaultdict(set)
    for e in edges:
        adj[e["from"]].add(e["to"])
    index, low, on, stack, out, counter = {}, {}, set(), [], [], [0]
    for root in nodes:
        if root in index:
            continue
        work = [(root, iter(sorted(adj[root])))]
        index[root] = low[root] = counter[0]
        counter[0] += 1
        stack.append(root)
        on.add(root)
        while work:
            v, it = work[-1]
            for w in it:
                if w not in index:
                    index[w] = low[w] = counter[0]
                    counter[0] += 1
                    stack.append(w)
                    on.add(w)
                    work.append((w, iter(sorted(adj[w]))))
                    break
                if w in on:
                    low[v] = min(low[v], index[w])
            else:
                work.pop()
                if work:
                    low[work[-1][0]] = min(low[work[-1][0]], low[v])
                if low[v] == index[v]:
                    comp = []
                    while True:
                        w = stack.pop()
                        on.discard(w)
                        comp.append(w)
                        if w == v:
                            break
                    if len(comp) > 1 or v in adj[v]:
                        out.append(sorted(comp))
    return sorted(out)


def affected(registry, bundle, cab, path_id, edit_kind, new_targets=None):
    """Which bundles an edit of one asset affects. edit_kind:
      value      a serialized VALUE changes (a colour, a position, pixels); references, identity and object set stay as they are
      reference  the asset's OUTGOING references change (it points at other assets); `new_targets` [{bundle}] says where
      identity   the asset's PathID, GUID/container key or existence changes (replace, rename key, delete)
    Returns the bundles that MUST be rebuilt (the asset's own, plus for `identity` the bundles of every resolved referrer), bundles that are merely referrers (not rebuilt for a value
    edit), and what is UNKNOWN because the graph does not cover it: an ambiguous referrer, or a bundle whose references were not read (PPtr referrers can only be in bundles whose
    externals contain the asset's CAB; GUID referrers can be in any bundle, so they are complete only when every bundle is built)."""
    if edit_kind not in ("value", "reference", "identity"):
        raise ValueError("edit_kind must be value, reference or identity")
    with registry._db() as db:
        a = db.execute("SELECT * FROM assets WHERE bundle=? AND cab=? AND path_id=?", (bundle, cab, str(path_id))).fetchone()
        if a is None:
            raise KeyError("no such inventory asset: %s / %s / %s" % (bundle, cab, path_id))
        brec = db.execute("SELECT * FROM bundles WHERE rel_path=?", (bundle,)).fetchone()
        states = {r["bundle"]: r["state"] for r in db.execute("SELECT bundle, state FROM graph_state")}
        allb = {r["rel_path"]: (json.loads(r["externals"]) if r["externals"] else []) for r in db.execute("SELECT rel_path, externals FROM bundles WHERE state IN ('valid','partially_valid')")}
    users = used_by(registry, bundle, cab, path_id, limit=100000)["edges"]
    resolved_refs = sorted({e["src"]["bundle"] for e in users if not e.get("via_candidate") and e["resolution"] == "resolved"} - {bundle})
    ambiguous_refs = sorted({e["src"]["bundle"] for e in users if e.get("via_candidate")} - {bundle})
    required, notes, unknown = [bundle], [], []
    possibly = resolved_refs
    if edit_kind == "value":
        notes.append("a value edit changes data inside this asset only; referencing bundles are listed as possibly affected at runtime but are not rebuilt")
    elif edit_kind == "reference":
        if new_targets:
            deps = {cab_of(d) for d in (json.loads(brec["dependencies"]) if brec["dependencies"] else [])}
            tb = {t["bundle"] for t in new_targets}
            need = []
            for t in sorted(tb - {bundle}):
                row = db_cab(registry, t)
                if row and row not in deps:
                    need.append({"target_bundle": t, "cab": row, "reason": "the bundle's dependency list does not name this CAB"})
            notes.append("the bundle is rebuilt; its dependency metadata may need %d new entr%s" % (len(need), "y" if len(need) == 1 else "ies"))
            if need:
                unknown.append({"what": "dependency_metadata_update", "targets": need})
        else:
            unknown.append({"what": "new_targets_not_given", "reason": "an edit that changes outgoing references needs the targets to decide whether the bundle's dependency list changes"})
    else:
        required = sorted({bundle, *resolved_refs})
        possibly = []
        notes.append("an identity change breaks every resolved reference to this asset: the bundles of those referrers are required")
        for b in ambiguous_refs:
            unknown.append({"what": "ambiguous_referrer", "bundle": b, "reason": "an ambiguous reference lists this asset among its candidates"})
    cab_l = cab.lower()
    pptr_possible = sorted(b for b, ext in allb.items() if b != bundle and any(cab_of(x) == cab_l for x in ext))
    unread_pptr = [b for b in pptr_possible if states.get(b) != "built"]
    guid_possible = bool(a["guid"])
    unread_guid = sorted(b for b in allb if b != bundle and states.get(b) != "built") if guid_possible else []
    if edit_kind in ("identity",) or edit_kind == "reference":
        for b in unread_pptr:
            unknown.append({"what": "unread_bundle", "bundle": b, "reason": "its externals name this asset's CAB but its references were not read (graph state %s)" % states.get(b, "unbuilt")})
        if unread_guid and edit_kind == "identity":
            unknown.append({"what": "unread_bundles_for_guid_references", "count": len(unread_guid), "reason": "this asset has a container GUID; any bundle that is not graph-built could reference it by GUID"})
    complete = not unknown
    return {"asset": {"bundle": bundle, "cab": cab, "path_id": str(path_id), "name": a["name"], "type": a["type"], "role": a["role"], "guid": a["guid"]}, "edit_kind": edit_kind,
            "rebuild_required": required, "possibly_affected_at_runtime": possibly, "unknown": unknown, "status": "complete" if complete else "unknown", "notes": notes,
            "evidence": {"resolved_referrer_bundles": resolved_refs, "ambiguous_referrer_bundles": ambiguous_refs,
                         "bundles_whose_externals_name_this_cab": pptr_possible, "guid_referrers_possible_in_unbuilt_bundles": len(unread_guid)}}


def db_cab(registry, bundle):
    with registry._db() as db:
        r = db.execute("SELECT cab FROM bundles WHERE rel_path=?", (bundle,)).fetchone()
    return (r[0] or "").lower() if r else None
