"""Parsed layouts for the renderer: one VisualTreeAsset -> a plain nested dict, cached in memory and on disk, with template includes resolved by GUID.

Reuses the L view's decode (`uxml.registry`, `uxml.element`, `uxml.inline_rule`, `uxml.usings`); what is new here is (1) the parsed-layout cache, so a layout is
decoded from its bundle once, and (2) include resolution through `m_Usings` GUIDs (see guids.py) instead of matching the alias to a layout name, which fails for
templates such as `tile-wide-4x2` -> `tile-figma-base-template`."""
import copy
import json
from pathlib import Path

from .. import uxml
from ..asset_hash import sha256_file
from .guids import GuidIndex

PARSE_VERSION = 3                         # 3: records are bound to the bundle SHA256, not size/mtime
NON_VISUAL_SUFFIX = "Component"          # BindingRemapperComponent, BindingVariablesComponent ...: attached to the parent, not elements of the visual tree
VISUAL_COMPONENT = "ComponentElement"


def is_visual(node):
    t = node.get("type", "")
    return not (t.endswith(NON_VISUAL_SUFFIX) and t != VISUAL_COMPONENT)


def _scalar_attrs(attrs):
    return {k: v for k, v in (attrs or {}).items() if isinstance(v, (str, int, float, bool))}


class LayoutStore:
    def __init__(self, folder, cache_dir=None):
        self.folder = Path(folder)
        self.cache_dir = Path(cache_dir) if cache_dir else None
        self.guids = GuidIndex(folder, cache_dir)
        self._objs = {}
        self._parsed = {}
        self._target = {}
        self._bundle_hashes = {}
        self.stats = {"decoded": 0, "disk_hits": 0, "memory_hits": 0}

    def catalog(self):
        """[{bundle, name, path_id, elements, classes}] for every VisualTreeAsset, from the L view's lister (one pass per bundle, cached on disk by size and mtime)."""
        if getattr(self, "_catalog", None) is None:
            self._catalog = uxml.Layouts(self.folder, self.cache_dir).list()
        return self._catalog

    # ---- decode, once per layout
    def _bundle_objs(self, bundle):
        if bundle not in self._objs:
            import UnityPy
            self._objs[bundle] = {o.path_id: o for o in UnityPy.load(str(self.folder / bundle)).objects}
        return self._objs[bundle]

    def _bundle_hash(self, bundle):
        if bundle not in self._bundle_hashes:
            self._bundle_hashes[bundle] = sha256_file(self.folder / bundle)
        return self._bundle_hashes[bundle]

    def _disk(self, bundle, path_id):
        if not self.cache_dir:
            return None
        return self.cache_dir / ("render-layout-%s-%s-%s.json" % (bundle[:-len(".bundle")], path_id, self._bundle_hash(bundle)))

    def parse(self, bundle, path_id):
        """The layout as {bundle, path_id, name, usings: {alias: {guid}}, content_container, root} with a nested `root`; cached."""
        key = (bundle, str(path_id))
        if key in self._parsed:
            self.stats["memory_hits"] += 1
            return self._parsed[key]
        disk = self._disk(bundle, path_id)
        if disk is not None and disk.is_file():
            rec = json.loads(disk.read_text(encoding="utf-8"))
            if rec.get("v") == PARSE_VERSION and rec.get("bundle_sha256") == self._bundle_hash(bundle):
                self._parsed[key] = rec
                self.stats["disk_hits"] += 1
                return rec
        objs = self._bundle_objs(bundle)
        o = objs.get(int(path_id))
        if o is None:
            raise KeyError("no object %s in %s" % (path_id, bundle))
        t = o.read_typetree()
        if "m_VisualTree" not in t:
            raise ValueError("path id %s is not a VisualTreeAsset" % path_id)
        pid = (t.get("inlineSheet") or {}).get("m_PathID", 0)
        sheet = objs[pid].read_typetree() if pid in objs else None
        refs = uxml.registry(t)

        def build(rid):
            e = uxml.element(t, refs, rid)
            if e is None:
                return None
            node = {"id": e["id"], "kind": e["kind"], "type": e["type"], "name": e["name"], "classes": e["classes"],
                    "inline": uxml.inline_rule(sheet, e["rule_index"]) if e["rule_index"] >= 0 else None,
                    "attrs": _scalar_attrs(e["attrs"]), "has_bindings": bool(e["bindings"])}
            if e["kind"] == "template":
                node["template"] = e.get("template", "")
            node["children"] = [c for c in (build(r) for r in e["children"]) if c]
            return node

        rec = {"v": PARSE_VERSION, "bundle": bundle, "bundle_sha256": self._bundle_hash(bundle), "path_id": str(path_id), "name": t.get("m_Name", ""), "content_hash": t.get("m_ContentHash"),
               "usings": {a: {"guid": u["path"]} for a, u in uxml.usings(t).items()},
               "content_container": t.get("m_ContentContainerId", 0), "root": build(t["m_VisualTree"]["rid"])}
        self._parsed[key] = rec
        self.stats["decoded"] += 1
        if disk is not None:
            self.cache_dir.mkdir(parents=True, exist_ok=True)
            disk.write_text(json.dumps(rec), encoding="utf-8")
        return rec

    # ---- includes by GUID
    def target(self, guid):
        """(bundle, path_id) of the VisualTreeAsset a GUID names, or None. A GUID covers a layout and its inline sheet; the one that is a layout wins."""
        guid = (guid or "").lower()
        if guid in self._target:
            return self._target[guid]
        found = None
        for bundle, pid in self.guids.find(guid):
            try:
                self.parse(bundle, pid)
            except (ValueError, KeyError):
                continue
            found = (bundle, pid)
            break
        self._target[guid] = found
        return found

    # ---- the expanded tree
    def expand(self, bundle, path_id, depth=3, _seen=()):
        """A fresh nested tree (safe to modify) with templates replaced by their included layout's children, `depth` levels deep. Slot content (the instance's
        children) goes into the included layout's content container when it names one, else after the included children. Unresolved includes are flagged."""
        rec = self.parse(bundle, path_id)
        return self._node(copy.deepcopy(rec["root"]), rec, depth, _seen + ((bundle, str(path_id)),))

    def _node(self, n, rec, depth, seen):
        kids = [self._node(c, rec, depth, seen) for c in n.pop("children", [])]
        n["layout"] = rec["name"]
        n["visual"] = is_visual(n)
        if n["kind"] != "template":
            n["children"] = kids
            return n
        n["type"] = "TemplateContainer"
        alias = n.get("template", "")
        guid = (rec["usings"].get(alias) or {}).get("guid")
        tgt = self.target(guid) if guid else None
        n["include"] = {"alias": alias, "guid": guid, "resolved": bool(tgt)}
        if not tgt or depth <= 0 or tgt[:2] in seen or (tgt[0], str(tgt[1])) in seen:
            n["children"] = kids
            if not tgt:
                n["include"]["problem"] = "no layout for this GUID in the layout bundles"
            elif depth <= 0:
                n["include"]["problem"] = "not expanded (depth limit)"
            else:
                n["include"]["problem"] = "include cycle"
            return n
        inc_rec = self.parse(*tgt)
        inc = self.expand(tgt[0], tgt[1], depth - 1, seen)
        n["include"]["layout"] = inc_rec["name"]
        inner = inc.get("children", [])
        slot = self._find_id(inner, inc_rec["content_container"], inc_rec["name"]) if inc_rec["content_container"] else None
        if slot is not None:
            slot["children"] = slot.get("children", []) + kids
            n["include"]["slot"] = "content container %s" % inc_rec["content_container"]
            n["children"] = inner
        else:
            n["include"]["slot"] = "after the included children"
            n["children"] = inner + kids
        return n

    def _find_id(self, nodes, ident, layout_name):
        for c in nodes:
            if c.get("id") == ident and c.get("layout") == layout_name:
                return c
            hit = self._find_id(c.get("children", []), ident, layout_name)
            if hit is not None:
                return hit
        return None
