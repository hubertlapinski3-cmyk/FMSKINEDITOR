"""Build a UiDocument for one screen (a composition on a grid) from the existing outputs. Read only; nothing here writes a game file, a cache or a project.

Inputs: a layout `Source` (parse records, GUID targets), the layout dump (compositions, cells, tiles), optionally a `Renderer` (cascade results for `computed_style`, rules, tokens, fonts, images).
The existing screen model (`render.screen.Assembler`) decides hosts and tile configs exactly as it does for the render; this module adds identity and the dependency graph on top."""
import re
import hashlib
from collections import Counter

from ..render import screen as screen_mod
from ..render.layouts import is_visual
from ..render.sheets import ROOT_SHEETS
from ..asset_hash import sha256_file
from .model import ELEMENT, HOST, ROOT, SCREEN, TEMPLATE, Gap, Graph, UiDocument, UiNode

COLOUR = re.compile(r"^(#[0-9a-fA-F]{6,8}|rgba?\([^)]*\))$")
DEPTH = 64                                  # the existing expansion's depth argument for the cascade; the model's own expansion has no limit (cycle detection only)
# The composition/breakpoint pairs a runtime observation has MEASURED (Stage 3E: the active composition depends on
# the window width). Everything else stays ESTIMATE - a generalisation must not inherit Team Instructions' claim.
MEASURED_BREAKPOINTS = {("TacticalPlannerTeamInstructionsTabComposition-Large", 3)}


class Source:
    """Adapter over a `render.layouts.LayoutStore`. Tests replace it with a small fake that offers the same five methods."""

    def __init__(self, store):
        self.store, self._rev = store, None
        self._bundle_hashes = {}
        self._named_assets = {}

    def bundle_sha256(self, bundle):
        """Content identity for a physical bundle locator; never trust mtime/size as identity."""
        if bundle not in self._bundle_hashes:
            self._bundle_hashes[bundle] = sha256_file(self.store.folder / bundle)
        return self._bundle_hashes[bundle]

    def physical_source(self, bundle, obj=None, field=None):
        text = str(obj or "")
        match = re.search(r"VisualTreeAsset\s+(-?\d+)", text)
        if not match:
            match = re.search(r"composition asset\s+(-?\d+)", text, re.I)
        if match:
            located = self.physical_locator(bundle, match.group(1), "VisualTreeAsset" if "VisualTreeAsset" in text else "Composition")
            located.update({"object": obj, "field": field})
            return located
        sheet = re.search(r"StyleSheet\s+(.+?)\s+rule\s+\d+", text)
        if sheet:
            located = self.named_asset_locator(bundle, sheet.group(1), "StyleSheet")
            if located:
                return dict(located, object=obj, field=field)
        return {"build_identity": getattr(self, "build_identity", "unknown"), "bundle": bundle,
                "bundle_sha256": self.bundle_sha256(bundle), "serialized_file": None,
                "asset_type": None, "object": obj, "field": field}

    def physical_locator(self, bundle, path_id, asset_type=None):
        return {"build_identity": getattr(self, "build_identity", "unknown"), "bundle": bundle,
                "bundle_sha256": self.bundle_sha256(bundle), "serialized_file": self.file_of(bundle, path_id),
                "path_id": str(path_id), "asset_type": asset_type}

    def parse(self, bundle, path_id):
        return self.store.parse(bundle, path_id)

    def target(self, guid):
        return self.store.target(guid)

    def guid_objects(self, guid):
        return self.store.guids.find(guid)

    def guid_of(self, bundle, path_id):
        if self._rev is None:
            self._rev = {}
            for g, ents in self.store.guids.load().items():
                for b, p in ents:
                    self._rev[(b, str(p))] = g
        return self._rev.get((bundle, str(path_id)))

    def file_of(self, bundle, path_id):
        try:
            return self.store._bundle_objs(bundle)[int(path_id)].assets_file.name
        except Exception:
            return None

    def inline_sheet(self, bundle, path_id):
        obj = self.store._bundle_objs(bundle).get(int(path_id))
        if obj is None:
            return None
        tree = obj.read_typetree()
        ptr = tree.get("inlineSheet") or {}
        sheet_path = ptr.get("m_PathID", 0)
        if not sheet_path:
            return None
        if ptr.get("m_FileID", 0) != 0:
            return {"error": "inline sheet uses external file id %s" % ptr.get("m_FileID"), "file_id": ptr.get("m_FileID"), "path_id": str(sheet_path)}
        return {"bundle": bundle, "path_id": str(sheet_path), "serialized_file": self.file_of(bundle, sheet_path)}

    def named_asset_locator(self, bundle, name, asset_type):
        key = (bundle, name, asset_type)
        if key in self._named_assets:
            return self._named_assets[key]
        for obj in self.store._bundle_objs(bundle).values():
            if obj.type.name not in ("MonoBehaviour", "AssetBundle"):
                continue
            try:
                tree = obj.read_typetree()
            except Exception:
                continue
            if tree.get("m_Name") == name and (asset_type != "StyleSheet" or "m_Rules" in tree):
                self._named_assets[key] = self.physical_locator(bundle, obj.path_id, asset_type)
                return self._named_assets[key]
        self._named_assets[key] = None
        return None

    def name_rows(self, name):
        return sum(1 for r in self.store.catalog() if r["name"] == name)


def _seg(rec):
    base = ("Template:%s" % rec.get("template", "")) if rec["kind"] == "template" else rec["type"]
    return base + ("#" + rec["name"] if rec.get("name") else "")


class Builder:
    def __init__(self, source, dump, renderer=None, label=None, order="natural"):
        self.src, self.dump, self.rd, self.order = source, dump, renderer, order
        self.label = label or {}
        self.g, self.gaps, self.index = Graph(), [], {}
        build_label = self.label.get("game_build") or "unlabelled"
        catalog = self.label.get("folder_catalog_hash") or self.label.get("dump_catalog_hash") or "unknown"
        self.identity_scheme = {"build_identity": "%s@catalog:%s" % (build_label, catalog), "game_build_label": str(build_label), "build_identity_source": self.label.get("label_source", "not supplied"),
                                "catalog_hash": catalog, "bundle_hashes": {},
                                "logical_scheme": "top-layout-guid + structural path + occurrence among identical siblings",
                                "logical_scope": "deterministic within the serialized input; not a universal cross-build identity",
                                "cross_build_evidence": "B-to-C set C provisional; see docs/UIDOCUMENT-AUDIT.md"}
        if hasattr(self.src, "physical_locator"):
            self.src.build_identity = self.identity_scheme["build_identity"]
        self.g.source_resolver = self.src.physical_source if hasattr(self.src, "physical_source") else None
        self.layouts_seen = {}                       # guid -> (bundle, path_id, name)
        self.rule_ids = {}
        self._occ = None
        self.style_coverage = {"structural_tree": "complete recursive expansion until unresolved include or cycle", "cascade_depth_limit": DEPTH, "partial": self.rd is None}

    # ---- identity helpers
    def gap(self, code, obj, reason, audit=""):
        self.gaps.append(Gap(code, obj, reason, audit))
        if hasattr(self, "g"):
            digest = hashlib.sha256((str(code) + "\n" + str(obj) + "\n" + str(reason)).encode("utf-8")).hexdigest()[:16]
            nid = "gap:%s:%s" % (code, digest)
            self.g.node(nid, "diagnostic_gap", code=code, object=obj, reason=reason, audit_gap=audit)
            if obj in self.g.nodes:
                self.g.edge(obj, nid, "has_diagnostic", {"bundle": None, "object": obj, "field": code})

    def _register(self, node):
        if node.logical_id in self.index:
            self.gap("IDENTITY_COLLISION", node.logical_id, "two nodes share this logical id; the second was kept apart by its position only", "G14")
            node.logical_id = "%s@dup%d" % (node.logical_id, sum(1 for k in self.index if k.startswith(node.logical_id)))
        self.index[node.logical_id] = node
        self.g.node("node:" + node.logical_id, "ui_node", type=node.type, name=node.name)

    @staticmethod
    def _structured_sources(descriptions, physical=None):
        return {field: {"kind": "derived" if text != "unknown by design" else "unknown", "source": physical,
                        "field": text, "derivation": text if field in ("logical_id", "children") else None}
                for field, text in descriptions.items()}

    def _make(self, rec, ctx, segs, kind, flags, pos):
        top = ctx["top"]
        base = top + "|" + "/".join(b for b, _m in segs)
        marked = top + "|" + "/".join(m for _b, m in segs)
        physical = self.src.physical_locator(ctx["bundle"], ctx["pid"], "VisualTreeAsset") if hasattr(self.src, "physical_locator") else {"bundle": ctx["bundle"], "path_id": ctx["pid"]}
        physical.update({"element_id": rec["id"], "element_identity_scope": "within this serialized VisualTreeAsset and game build"})
        loc = {"layout": ctx["name"], "layout_guid": ctx["guid"], "bundle": ctx["bundle"], "file": ctx["file"], "path_id": ctx["pid"], "m_id": rec["id"], "physical": physical}
        asset_source = {"build_identity": self.identity_scheme["build_identity"], "bundle": ctx["bundle"], "bundle_sha256": physical.get("bundle_sha256"),
                        "serialized_file": ctx["file"], "path_id": ctx["pid"], "asset_type": "VisualTreeAsset"}
        src = {
            "logical_id": {"kind": "derived", "source": asset_source, "field": "m_VisualTree/m_Id, parent-child path, template instance path", "method": "top layout GUID plus structural path; occurrence index among identical siblings"},
            "structural_key": {"kind": "derived", "source": asset_source, "field": "m_VisualTree/m_Id and hierarchy", "method": "logical_id with occurrence marks removed"},
            "locator": {"kind": "serialized", "source": asset_source, "field": "m_Id"}, "physical": {"kind": "serialized", "source": physical},
            "type": {"kind": "serialized", "source": asset_source, "field": "m_FullTypeName"}, "name": {"kind": "serialized", "source": asset_source, "field": "serialized data name"},
            "classes": {"kind": "serialized", "source": asset_source, "field": "m_Classes"},
            "children": {"kind": "serialized+expanded", "source": asset_source, "field": "m_Children", "method": "template expansion and slot insertion in authored order"},
            "computed_style": {"kind": "measured-render-output", "source": None, "method": "existing Renderer.layout cascade paired by render position"} if self.rd else {"kind": "unavailable", "source": None, "reason": "cascade not requested"},
            "semantic_role": {"kind": "reserved", "source": None}, "edit_safety": {"kind": "unknown", "source": None}}
        if physical.get("bundle_sha256"):
            self.identity_scheme["bundle_hashes"][ctx["bundle"]] = physical["bundle_sha256"]
        node = UiNode(logical_id=marked, structural_key=base, locator=loc, type=("TemplateContainer" if rec["kind"] == "template" else rec["type"]), name=rec.get("name") or "",
                      classes=list(rec.get("classes") or []), kind=kind, flags=list(flags), render_pos=pos, sources=src)
        if not is_visual(rec):
            node.flags.append("non_visual")
            self.gap("NONVISUAL_COMPONENT_KEPT", "node:" + node.logical_id, "a non-visual component (%s): kept and flagged; the cascade removes it and its bindings are decoded only as a yes/no" % rec["type"], "G6")
        ctx["inst"][rec["id"]] = node
        self._register(node)
        if physical.get("bundle_sha256"):
            physical_element_id = "physical-element:%s:%s:%s:%s:%s" % (physical["build_identity"], physical["bundle_sha256"], physical["serialized_file"], physical["path_id"], rec["id"])
            self.g.node(physical_element_id, "physical_ui_element", type=node.type, name=node.name, locator=physical)
            self.g.edge("node:" + node.logical_id, physical_element_id, "has_physical_locator", {"bundle": ctx["bundle"], "object": "VisualTreeAsset %s" % ctx["pid"], "field": "m_Id"})
        return node

    def _children(self, parent_rec, ctx, psegs, chain, pos_of):
        recs = parent_rec["children"]
        segs = [_seg(c) for c in recs]
        counts = Counter(segs)
        seen, out = Counter(), []
        for j, c in enumerate(recs):
            s = segs[j]
            mark = s if counts[s] == 1 else "%s~%d" % (s, seen[s])
            seen[s] += 1
            out.append(self._element(c, ctx, psegs + [(s, mark)], chain, pos_of(j)))
        return out

    def _element(self, rec, ctx, segs, chain, pos):
        if rec["kind"] != "template":
            node = self._make(rec, ctx, segs, ELEMENT, [], pos)
            node.children = self._children(rec, ctx, segs, chain, lambda j, p=pos: "%s/%d" % (p, j))
            return node
        node = self._make(rec, ctx, segs, TEMPLATE, ["template_instance"], pos)
        alias = rec.get("template", "")
        guid = (ctx["usings"].get(alias) or {}).get("guid")
        tgt = self.src.target(guid) if guid else None
        ref_id = "template-ref:%s:%s:%s" % (ctx["guid"], rec["id"], guid or "unresolved")
        self.g.node(ref_id, "template", alias=alias, source_layout_guid=ctx["guid"], element_id=rec["id"], target_layout_guid=guid, resolved=bool(tgt))
        self.g.edge("node:" + node.logical_id, ref_id, "is_template_reference", {"bundle": ctx["bundle"], "object": "VisualTreeAsset %s" % ctx["pid"], "field": "m_TemplateAlias / m_Usings"})
        if not tgt:
            self.gap("TEMPLATE_TARGET_UNRESOLVED", ref_id, "template alias %r has no resolvable GUID target" % alias, "G2")
        kids_pos = lambda j, p=pos: "%s/%d" % (p, j)
        if not tgt or (tgt[0], str(tgt[1])) in chain:
            code, why = ("INCLUDE_UNRESOLVED", "no layout for this GUID in the layout bundles") if not tgt else ("INCLUDE_CYCLE", "the include would enter a layout that is already open")
            node.flags.append("include_unresolved" if not tgt else "include_cycle")
            self.gap(code, "node:" + node.logical_id, "template alias %r (GUID %s) in layout %s: %s; the instance keeps only its own children" % (alias, guid, ctx["name"], why), "G2")
            node.children = self._children(rec, ctx, segs, chain, kids_pos)
            return node
        node.locator["template_alias"], node.locator["included_layout_guid"] = alias, guid
        inc_root, inc_ctx, inc_rec = self.layout_instance(guid, ctx["top"], segs, chain, pos)
        node.children = [inc_root]
        self.g.edge("node:" + node.logical_id, "layout:" + guid, "includes_layout",
                    {"bundle": ctx["bundle"], "object": "VisualTreeAsset %s" % ctx["pid"], "field": "m_Usings[%s] -> GUID %s" % (alias, guid)})
        self.g.edge("layout:" + ctx["guid"], "layout:" + guid, "includes", {"bundle": ctx["bundle"], "object": "VisualTreeAsset %s" % ctx["pid"], "field": "m_Usings[%s]" % alias})
        cc = inc_rec["content_container"]
        slot = inc_ctx["inst"].get(cc) if cc else None
        target = slot if slot is not None else inc_root
        base_pos = slot.render_pos if slot is not None else pos
        offset = len(target.children)
        kids = self._children(rec, ctx, segs, chain, lambda j, b=base_pos, o=offset: "%s/%d" % (b, o + j))
        for k in kids:
            k.flags.append("slot_content")
        target.children.extend(kids)
        node.locator["slot"] = "content container %s" % cc if slot is not None else "after the included children"
        return node

    def layout_instance(self, guid, top, parent_segs, chain, pos_base):
        """One instance of a layout in the document: its ROOT node (kept) and everything below. `pos_base` None = a top layout; else the render position of the template it replaces."""
        bundle, pid = self.src.target(guid)
        rec = self.src.parse(bundle, pid)
        ctx = {"guid": guid, "name": rec["name"], "bundle": bundle, "pid": str(pid), "file": self.src.file_of(bundle, pid), "top": top, "usings": rec["usings"], "inst": {}}
        self.layouts_seen[guid] = (bundle, str(pid), rec["name"])
        self.g.node("layout:" + guid, "layout", name=rec["name"], bundle=bundle, path_id=str(pid))
        self.g.node("bundle:" + bundle, "bundle", file=bundle)
        self.g.edge("layout:" + guid, "bundle:" + bundle, "in_bundle", {"bundle": bundle, "object": "VisualTreeAsset %s" % pid})
        rows = self.src.name_rows(rec["name"])
        if rows > 1:
            self.gap("LAYOUT_NAME_NOT_UNIQUE", "layout:" + guid, "%d layouts share the name %r; the model identifies this one by GUID" % (rows, rec["name"]), "G14")
        inline = self.src.inline_sheet(bundle, pid) if hasattr(self.src, "inline_sheet") else None
        if inline and "error" not in inline:
            inline["bundle_sha256"] = self.src.bundle_sha256(inline["bundle"])
            inline["build_identity"] = self.identity_scheme["build_identity"]
            inline["asset_type"] = "StyleSheet"
            self.identity_scheme["bundle_hashes"][inline["bundle"]] = inline["bundle_sha256"]
            self.g.node("inline_sheet:%s" % guid, "inline_sheet", bundle=inline["bundle"], path_id=inline["path_id"], physical=inline)
            self.g.edge("layout:" + guid, "inline_sheet:%s" % guid, "has_inline_sheet", {"bundle": bundle, "object": "VisualTreeAsset %s" % pid, "field": "inlineSheet.m_PathID"})
        elif inline and inline.get("error"):
            self.gap("INLINE_SHEET_UNRESOLVED", "layout:" + guid, inline["error"], "inline")
        else:
            self.gap("INLINE_SHEET_MISSING", "layout:" + guid, "VisualTreeAsset has no inlineSheet PathID", "inline")
        chain2 = chain + [(bundle, str(pid))]
        root_seg = ("UXML@" + guid[:8]) if pos_base is not None else "UXML"
        segs = parent_segs + [(root_seg, root_seg)]
        root = self._make(rec["root"], ctx, segs, ROOT, ["root"], None)
        if pos_base is None:
            root.children = self._children(rec["root"], ctx, segs, chain2, lambda j: str(j))
        else:
            root.children = self._children(rec["root"], ctx, segs, chain2, lambda j, p=pos_base: "%s/%d" % (p, j))
        return root, ctx, rec

    # ---- the screen
    def _panels_from_bundle(self):
        """G9, the corrected source: the panel id -> layout GUID links read DIRECTLY from
        ui-panelids_assets_all.bundle (not from the dump's derived panels table). Read only; cross-checked
        against the dump's rows in build()."""
        if getattr(self, "_panels_bundle", None) is None:
            try:
                from ..layout_export import read_panels
                rows = read_panels(self.src.store.folder) if hasattr(self.src, "store") else []
                self._panels_bundle = {"rows": rows, "source": "ui-panelids_assets_all.bundle"}
            except Exception as e:
                self._panels_bundle = {"rows": [], "source": "ui-panelids_assets_all.bundle", "error": "%s: %s" % (type(e).__name__, str(e)[:80])}
        return self._panels_bundle

    def build(self, composition, area, padding=screen_mod.PADDING, reserved_right=0):
        d = self.dump
        if self.identity_scheme["game_build_label"] == "unlabelled":
            meta = d.get("meta", {})
            game_build = meta.get("game_build") or "unlabelled"
            catalog = (meta.get("source") or {}).get("catalog_hash") or "unknown"
            self.identity_scheme.update({"game_build_label": game_build, "catalog_hash": catalog, "build_identity": "%s@catalog:%s" % (game_build, catalog),
                                         "build_identity_source": "layout dump meta.game_build + meta.source.catalog_hash"})
            if hasattr(self.src, "physical_locator"):
                self.src.build_identity = self.identity_scheme["build_identity"]
        asm = screen_mod.Assembler(d)
        out = asm.assemble(composition, tuple(area), reserved_right=reserved_right, padding=padding)
        lay = {l["id"]: l for l in d["layouts"]}
        crec = next(c for c in d["compositions"] if c["name"] == composition)
        cells = sorted((c for c in d["cells"] if c["composition"] == composition), key=lambda c: c["cell_index"])
        tiles = [t for t in d["tiles"] if t["composition"] == composition]
        hosts = {h["element_id"]: h for h in out["hosts"]}
        dup_ids = {k for k, v in Counter(c["element_id"] for c in cells).items() if v > 1}
        breakpoints = sorted({t.get("breakpoint") for t in self.dump["tiles"] if t["composition"] == composition and t.get("breakpoint") is not None})
        breakpoint = breakpoints[0] if len(breakpoints) == 1 else None
        measured = (composition, breakpoint) in MEASURED_BREAKPOINTS
        screen_id = "screen:%s@%s:%sx%s" % (composition, breakpoint if breakpoint is not None else "unknown", area[0], area[1])
        comp_physical = self.src.physical_locator(crec.get("bundle"), crec.get("path_id"), "Composition") if crec.get("bundle") and crec.get("path_id") is not None and hasattr(self.src, "physical_locator") else None
        root = UiNode(logical_id=screen_id, structural_key=screen_id, locator={"composition": composition, "bundle": crec.get("bundle"), "path_id": str(crec.get("path_id")), "physical": comp_physical}, type="Screen", name=composition,
                      classes=[], kind=SCREEN, flags=["root", "synthetic"],
                      sources=self._structured_sources({"logical_id": "the composition name", "locator": "layout dump compositions[name]", "children": "dump panels (tiles.panel_layout_id) and dump cells in cell_index order", "semantic_role": "empty by design", "edit_safety": "unknown by design"}, comp_physical))
        self._register(root)
        comp_id = "composition:" + composition
        self.g.node(comp_id, "composition", name=composition)
        if crec.get("bundle"):
            self.g.node("bundle:" + crec["bundle"], "bundle", file=crec["bundle"])
            self.g.edge(comp_id, "bundle:" + crec["bundle"], "in_bundle", {"bundle": crec["bundle"], "object": "composition asset %s" % crec.get("path_id")})
        # the panel layout(s) that hold the grid
        top_jobs = []
        for pid_ in sorted({t["panel_layout_id"] for t in tiles}):
            top_jobs.append(("panel", None, lay[pid_]["guid"], lay[pid_]["name"]))
        for c in cells:
            recs = [t for t in tiles if t["cell_index"] == c["cell_index"]]
            host = hosts.get(c["element_id"])
            pick = next((t for t in recs if host and lay[t["tile_layout_id"]]["name"] == host["tile_layout"]), recs[0] if recs else None)
            top_jobs.append(("cell", c, lay[pick["tile_layout_id"]]["guid"] if pick else None, lay[pick["tile_layout_id"]]["name"] if pick else None))
        jobs = list(reversed(top_jobs)) if self.order == "reversed" else top_jobs
        built = {}
        for kind, c, guid, name in jobs:
            if guid is None:
                continue
            tgt = self.src.target(guid)
            if not tgt:
                self.gap("LAYOUT_UNRESOLVED", "layout:" + guid, "the dump names layout %r (GUID %s) but no layout bundle holds it" % (name, guid), "G17")
                continue
            psegs = [] if kind == "panel" else [("host:" + c["element_id"], "host:" + c["element_id"] + ("~%d" % c["cell_index"] if c["element_id"] in dup_ids else ""))]
            r, ctx, rec = self.layout_instance(guid, guid, psegs, [], None)
            built[(kind, c["cell_index"] if c else None)] = (r, tgt)
        # identity uniqueness (counted, never assumed): m_Id within each participating layout's serialization
        identity_uniqueness = {"layouts": 0, "layouts_with_duplicate_m_id": 0, "duplicate_occurrences": 0, "examples": []}
        for guid, (bundle, pid, name) in sorted(self.layouts_seen.items(), key=lambda kv: (kv[1][2], kv[0])):
            rec_ = self.src.parse(bundle, pid)
            counts = Counter()
            stack_ = [rec_["root"]]
            while stack_:
                n_ = stack_.pop()
                counts[n_["id"]] += 1
                stack_.extend(n_["children"])
            identity_uniqueness["layouts"] += 1
            dups = {k: v for k, v in counts.items() if v > 1}
            if dups:
                identity_uniqueness["layouts_with_duplicate_m_id"] += 1
                identity_uniqueness["duplicate_occurrences"] += sum(v - 1 for v in dups.values())
                if len(identity_uniqueness["examples"]) < 5:
                    identity_uniqueness["examples"].append({"layout": name, "repeated_m_ids": [str(k) for k in sorted(dups, key=str)[:4]]})
        if identity_uniqueness["layouts_with_duplicate_m_id"]:
            self.gap("M_ID_NOT_UNIQUE_WITHIN_LAYOUT", "document", "%d participating layout(s) repeat an m_Id inside one serialization (%d extra occurrence(s); e.g. %s); the locator (bundle, path_id, m_Id) is therefore not unique there and the join disambiguates by authored occurrence" % (
                identity_uniqueness["layouts_with_duplicate_m_id"], identity_uniqueness["duplicate_occurrences"], identity_uniqueness["examples"][:2]), "G5")
        # canonical child order, whatever order the layouts were built in
        panel_nodes = [built[k][0] for k in sorted((k for k in built if k[0] == "panel"), key=lambda k: built[k][0].logical_id)]
        root.children = list(panel_nodes)
        cell_info = []
        for c in cells:
            eid, idx = c["element_id"], c["cell_index"]
            cid = "cell:%s#%d" % (composition, idx)
            self.g.node(cid, "cell", element_id=eid, cell_index=idx)
            self.g.edge(comp_id, cid, "has_cell", {"bundle": crec.get("bundle"), "object": "dump cells[%s,%d]" % (composition, idx), "field": "m_gridComponents[%d]" % idx})
            host_node = UiNode(logical_id="%s|host:%s@%d" % (screen_id, eid, idx), structural_key="%s|host:%s@%d" % (screen_id, eid, idx), locator={"composition": composition, "cell_index": idx, "element_id": eid},
                               type="Host", name=eid, classes=[], kind=HOST, flags=["synthetic"] + (["duplicate_element_id"] if eid in dup_ids else []),
                               sources=self._structured_sources({"logical_id": "composition name + cell element id + cell index", "locator": "layout dump cells[(composition, cell_index)]", "children": "the tile layout the existing assembler picks for this cell",
                                        "semantic_role": "empty by design", "edit_safety": "unknown by design"}, comp_physical))
            self._register(host_node)
            host = hosts.get(eid)
            placed = None
            if host is not None:
                placed = {k: host[k] for k in ("col", "row", "w", "h", "mode", "px", "tile_layout", "tile_how")}
            if eid in dup_ids:
                self.gap("DUPLICATE_CELL_ELEMENT_ID", cid, "cells %s of %r share the element id %r; the existing assembler places one host for them (screen.py Assembler.place setdefault) and the model keeps every cell" % (
                    sorted(x["cell_index"] for x in cells if x["element_id"] == eid), composition, eid), "G19")
            key = ("cell", idx)
            if key in built:
                r, tgt = built[key]
                host_node.children = [r]
                self.g.edge(cid, "layout:" + r.locator["layout_guid"], "places_tile", {"bundle": crec.get("bundle"), "object": "dump tiles[%s,%d] / cell_configs" % (composition, idx), "field": "tile_layout_id"})
                if placed and "ASSUMED" in (placed["tile_how"] or ""):
                    self.gap("TILE_CONFIG_ASSUMED", cid, "the tile config was chosen by the largest-fit assumption (%s)" % placed["tile_how"], "D14")
            else:
                self.gap("HOST_WITHOUT_TILE", cid, "no tile record for cell %d (%s) in the layout dump" % (idx, eid), "G7")
            root.children.append(host_node)
            cell_info.append({"cell_index": idx, "element_id": eid, "x": c["x"], "y": c["y"], "w": c["w"], "h": c["h"], "min": [c["min_w"], c["min_h"]], "max": [c["max_w"], c["max_h"]], "flags": c["flags"],
                              "placed_by_assembler": placed, "assembler_host_shared_with_other_cell": eid in dup_ids})
        for cfg in (c for c in d["cell_configs"] if c["composition"] == composition):
            pass
        pid_layout = sorted({t["panel_layout_id"] for t in tiles})
        bundle_panels = self._panels_from_bundle()
        by_guid = {}
        for panel_id, guid in bundle_panels["rows"]:
            by_guid.setdefault(guid, []).append(panel_id)
        for pl in pid_layout:
            g_ = lay[pl]["guid"]
            panel_rows = sorted((p for p in d["panels"] if p["layout_id"] == pl), key=lambda p: p["panel_id"])
            bundle_ids = sorted(set(by_guid.get(g_) or []))
            if bundle_panels.get("error"):
                self.gap("PANELIDS_UNREAD", "layout:" + g_, "the panel links could not be read from %s: %s; the dump's panels table was used" % (
                    bundle_panels["source"], bundle_panels["error"]), "G9")
            if not panel_rows and not bundle_ids:
                self.gap("PANEL_ID_UNRESOLVED", "layout:" + g_, "tiles name panel layout %r but neither the dump's panels table nor %s links a panel id to it" % (lay[pl]["name"], bundle_panels["source"]), "G9")
            for panel_id in bundle_ids:               # G9: the link read directly from ui-panelids
                pn = "panel:%s" % panel_id
                self.g.node(pn, "panel", name=panel_id, layout_guid=g_)
                self.g.edge(pn, "layout:" + g_, "reaches_layout_by_panel_id",
                            {"bundle": "ui-panelids_assets_all.bundle", "object": "MonoBehaviour %s" % panel_id, "field": "m_panelDescription.uxml.m_AssetGUID"})
                dump_ids = {p["panel_id"] for p in panel_rows}
                if panel_id not in dump_ids:
                    self.gap("PANELIDS_TABLE_MISMATCH", "layout:" + g_, "%s links panel id %r to this layout but the dump's panels table does not" % (bundle_panels["source"], panel_id), "G9")
            for p in panel_rows:
                if p["panel_id"] not in bundle_ids:
                    self.gap("PANELIDS_TABLE_MISMATCH", "layout:" + g_, "the dump's panels table links panel id %r to this layout but %s does not" % (p["panel_id"], bundle_panels["source"]), "G9")
            if ("panel", None) in built:
                self.g.edge(comp_id, "layout:" + g_, "tiles_declared_in_panel", {"bundle": crec.get("bundle"), "object": "dump tiles.panel_layout_id", "field": "panel_layout_id"})
        self.gap("GRID_CONTAINER_NOT_LINKED", comp_id, "the panel layout's grid element is not linked to the composition's hosts; the screen chrome around the grid is not modelled (screen.py:86-87)", "G18")
        composition_obj = {"name": composition, "breakpoint": breakpoint, "breakpoint_status": "MEASURED" if measured else "ESTIMATE", "runtime_elements": [], "runtime_element_status": "NOT_FROM_BUNDLES",
                           "bundle": crec.get("bundle"), "path_id": str(crec.get("path_id")), "physical": comp_physical,
                           "layout_mode": crec["layout_mode"], "preset": [crec["preset_w"], crec["preset_h"]], "conditions": crec["conditions"],
                           "instantiation_order": crec["instantiation_order"], "pitch": out["pitch"], "grid": out["grid"], "area": list(area), "padding": padding, "reserved_right": reserved_right,
                           "cells": cell_info, "hosts_returned_by_assembler": len(out["hosts"]), "cells_in_dump": len(cells), "tiles_in_dump": len(tiles),
                           "instantiation_order_indices_without_a_cell": sorted(i for i in crec["instantiation_order"] if i not in {c["cell_index"] for c in cells}),
                           "identity_uniqueness": identity_uniqueness}
        if composition_obj["instantiation_order_indices_without_a_cell"]:
            self.gap("INSTANTIATION_ORDER_UNEXPLAINED", comp_id, "instantiation_order names cell indices %s that the dump holds no cell for" % composition_obj["instantiation_order_indices_without_a_cell"], "G8")
        self._attach_composition_bundle_data(composition_obj, crec, comp_id)
        # cascade, styles, tokens, assets
        sheets = []
        if self.rd is not None:
            sheets = self._attach_cascade(root, built)
            composition_obj["join"] = dict(self._join_stats)
        self.style_coverage["computed_nodes"] = sum(1 for n in self.index.values() if n.computed_style is not None)
        self.style_coverage["nodes_without_computed_style"] = sum(1 for n in self.index.values() if n.computed_style is None and n.kind not in (ROOT, HOST, SCREEN) and "non_visual" not in n.flags)
        composition_obj["style_coverage"] = dict(self.style_coverage)
        for info in self.g.nodes.values():
            physical = info.get("physical")
            if info.get("kind") == "bundle" and physical and physical.get("bundle_sha256"):
                self.identity_scheme["bundle_hashes"][info["file"]] = physical["bundle_sha256"]
        bundle_fingerprint = hashlib.sha256("\n".join("%s:%s" % pair for pair in sorted(self.identity_scheme["bundle_hashes"].items())).encode("utf-8")).hexdigest()
        self.identity_scheme["participating_bundle_set_sha256"] = bundle_fingerprint
        doc = UiDocument(screen={"composition": composition, "breakpoint": breakpoint, "breakpoint_status": composition_obj["breakpoint_status"], "area": list(area), "padding": padding, "reserved_right": reserved_right,
                               "runtime_elements": [], "runtime_element_status": "NOT_FROM_BUNDLES"}, root_node=root, composition=composition_obj, style_sheets=sheets,
                         dependencies=self.g, diagnostics=self.gaps, source=dict(self.label), index=self.index, rule_ids=self.rule_ids, identity_scheme=self.identity_scheme)
        from .inventory import collect
        doc.inventory = collect(self.src, d, composition, self.rd) if self.rd is not None else {}
        graph_kinds = {"layouts": "layout", "tiles": "tile", "templates": "template", "stylesheets": ("stylesheet", "inline_sheet"), "rules": "rule", "tokens": "token",
                       "hard_coded_colours": "hard_coded_colour", "fonts": "font", "images": "image", "compositions": "composition", "bundles": "bundle",
                       "ui_elements": "physical_ui_element", "placement_bindings": "placement_binding", "serialized_references": "serialized_asset_reference",
                       "panels": "panel", "tile_descriptions": "tile_description"}
        for category, kind in graph_kinds.items():
            expected = set(doc.inventory.get(category, []))
            kinds = kind if isinstance(kind, tuple) else (kind,)
            actual = {nid for nid, info in self.g.nodes.items() if info.get("kind") in kinds}
            for missing in sorted(expected - actual):
                self.gap("INVENTORY_ITEM_UNREACHABLE", missing, "independent %s inventory item is not reachable in Dependencies" % category, "inventory")
            for extra in sorted(actual - expected):
                self.gap("GRAPH_ITEM_OUTSIDE_INVENTORY", extra, "dependency graph %s item is absent from the independent participating-set inventory" % category, "inventory")
        self._document_gaps(doc)
        return doc

    def _attach_composition_bundle_data(self, composition_obj, crec, comp_id):
        """Attach composition fields read from the bundle, retaining the dump as a derived assembly input."""
        if not hasattr(self.src, "store") or not crec.get("bundle") or crec.get("path_id") is None:
            self.gap("COMPOSITION_BUNDLE_DATA_UNAVAILABLE", comp_id, "the source does not expose the composition's serialized bundle object", "composition")
            self.gap("OPTIONAL_SLOTS_NOT_IN_DUMP", comp_id, "serialized optional slot data was unavailable; it was not inferred from the dump", "G7")
            return
        from .composition import read, read_descriptions
        raw, err = read(self.src, crec["bundle"], crec["path_id"], self.rd)
        if err:
            self.gap(err["code"], comp_id, err["reason"], "composition")
            self.gap("OPTIONAL_SLOTS_NOT_IN_DUMP", comp_id, "serialized optional slot data could not be read; it was not inferred from the dump", "G7")
            return
        composition_obj["serialized"] = raw["fields"]
        composition_obj["serialized_pointer_refs"] = raw["pointers"]
        # cross-check the serialized composition against the dump rows this build assembled from (the dump is the
        # derived input; the asset is the source). A disagreement is a named gap, never silently resolved.
        cells_ = sorted((c for c in self.dump["cells"] if c["composition"] == composition_obj["name"]), key=lambda c: c["cell_index"])
        ser_cells = raw["fields"].get("m_gridComponents") or []
        dump_seq = [(c["element_id"], c["x"], c["y"], c["w"], c["h"]) for c in cells_]
        ser_seq = [(c.get("m_elementID"), c["m_location"]["x"], c["m_location"]["y"], c["m_location"]["width"], c["m_location"]["height"]) for c in ser_cells]
        io_ser = (raw["fields"].get("m_optionalSlices") or {}).get("m_instantiationOrder")
        checks = {"cells_match_dump": ser_seq == dump_seq,
                  "instantiation_order_match": (io_ser == crec["instantiation_order"]) if isinstance(io_ser, list) else None,
                  "placement_bindings_are_cells": all((b or {}).get("m_elementID") in {c["element_id"] for c in cells_}
                                                      for b in (raw["fields"].get("m_placementBindings") or []))}
        composition_obj["serialized_checks"] = checks
        if checks["cells_match_dump"] is False:
            self.gap("COMPOSITION_SERIALIZED_DISAGREES", comp_id, "the serialized m_gridComponents differ from the dump's cells for %r (%d serialized vs %d dump rows; first difference %s vs %s)" % (
                composition_obj["name"], len(ser_seq), len(dump_seq),
                ser_seq[0] if ser_seq else None, dump_seq[0] if dump_seq else None), "composition")
        if checks["instantiation_order_match"] is False:
            self.gap("COMPOSITION_SERIALIZED_DISAGREES", comp_id, "the serialized m_optionalSlices.m_instantiationOrder %s differs from the dump's instantiation_order %s" % (
                io_ser, crec["instantiation_order"]), "composition")
        if checks["placement_bindings_are_cells"] is False:
            self.gap("COMPOSITION_SERIALIZED_DISAGREES", comp_id, "a serialized m_placementBindings entry names an element id that is no cell of %r" % composition_obj["name"], "composition")
        physical = raw["physical"]
        physical["build_identity"] = self.identity_scheme["build_identity"]
        physical["bundle_sha256"] = self.src.bundle_sha256(crec["bundle"])
        self.identity_scheme["bundle_hashes"][crec["bundle"]] = physical["bundle_sha256"]
        for side in ("m_topLeft", "m_top", "m_topRight", "m_left", "m_right", "m_bottomLeft", "m_bottom", "m_bottomRight"):
            slots = (raw["fields"].get("m_optionalSlices") or {}).get(side) or []
            for i, slot in enumerate(slots):
                sid = "tile:%s:optional:%s:%d" % (composition_obj["name"], side, i)
                self.g.node(sid, "tile", name=slot.get("m_elementID"), optional=True, region=side, order=i, composition=composition_obj["name"])
                self.g.edge(comp_id, sid, "has_optional_tile", {"bundle": crec["bundle"], "object": "Composition %s" % crec.get("path_id"), "field": "m_optionalSlices.%s[%d]" % (side, i)})
        for i, binding in enumerate(raw["fields"].get("m_placementBindings") or []):
            bid = "placement:%s:%d" % (composition_obj["name"], i)
            self.g.node(bid, "placement_binding", name=binding.get("m_elementID"), element_id=binding.get("m_elementID"), index=i)
            self.g.edge(comp_id, bid, "has_placement_binding", {"bundle": crec["bundle"], "object": "Composition %s" % crec.get("path_id"), "field": "m_placementBindings[%d]" % i})
        for i, ref in enumerate(raw["pointers"]):
            identity = ref.get("guid") or ref.get("path_id", "unknown")
            target = "asset-ref:%s:%d:%s" % (composition_obj["name"], i, identity)
            self.g.node(target, "serialized_asset_reference", field_path=ref["field_path"], path_id=ref.get("path_id"), guid=ref.get("guid"), bundle=ref.get("bundle"), asset_type=ref.get("asset_type"), name=ref.get("name"), resolved=ref["resolved"])
            self.g.edge(comp_id, target, "references_asset", {"bundle": crec["bundle"], "object": "Composition %s" % crec.get("path_id"), "field": ref["field_path"]})
            if ref["resolved"]:
                asset_id = "composition-asset:%s:%s" % (ref["bundle"], ref["resolved_path_id"])
                self.g.node(asset_id, "composition_asset", bundle=ref["bundle"], path_id=ref["resolved_path_id"], asset_type=ref.get("asset_type"), name=ref.get("name"))
                self.g.node("bundle:" + ref["bundle"], "bundle", file=ref["bundle"])
                self.g.edge(target, asset_id, "resolves_to", {"bundle": crec["bundle"], "object": "Composition %s" % crec.get("path_id"), "field": ref["field_path"]})
                self.g.edge(asset_id, "bundle:" + ref["bundle"], "in_bundle", {"bundle": ref["bundle"], "object": "%s %s" % (ref.get("asset_type"), ref.get("resolved_path_id"))})
            else:
                reference = "GUID %s" % ref["guid"] if ref.get("guid") else "fileID=%s PathID=%s" % (ref.get("file_id"), ref.get("path_id"))
                self.gap("COMPOSITION_REFERENCE_UNRESOLVED", target, "serialized reference %s at %s could not be resolved%s" % (
                    reference, ref["field_path"], (": " + ref["error"]) if ref.get("error") else ""), "composition")
        # ADDENDUM read 1 + read 2: the cells' tile-configuration descriptions (sizes, min/max, layout references)
        descs, err = read_descriptions(self.src, crec["bundle"], raw["fields"])
        if err:
            self.gap("TILE_DESCRIPTIONS_UNREAD", comp_id, "the cells' configuration descriptions could not be read: %s" % err, "G7")
            composition_obj["cell_configurations"] = None
        else:
            composition_obj["cell_configurations"] = descs
            seen_desc = {}
            for rec_ in descs:
                for d_ in rec_["descriptions"]:
                    if not d_.get("read"):
                        self.gap("TILE_DESCRIPTION_UNREAD", comp_id, "cell %d (%s): description path id %s: %s" % (
                            rec_["cell_index"], rec_["element_id"], d_.get("path_id"), d_.get("reason")), "G7")
                        continue
                    did = "tile_description:%s:%s" % (composition_obj["name"], d_["path_id"])
                    if did not in seen_desc:
                        seen_desc[did] = d_
                        self.g.node(did, "tile_description", name=d_.get("name"), description_id=d_.get("id"),
                                    default_config_index=d_.get("default_config_index"), configurations=len(d_["configurations"]),
                                    path_id=d_["path_id"], physical=dict(physical, path_id=d_["path_id"]))
                        self.g.edge(comp_id, did, "has_tile_description",
                                    {"bundle": crec["bundle"], "object": "Composition %s cell %s m_configDescriptions" % (crec.get("path_id"), rec_["element_id"]), "field": "m_configDescriptions"})
                    for j, cfg in enumerate(d_["configurations"]):
                        guid, asset_pid = cfg.get("asset_guid"), cfg.get("asset_path_id")
                        layout_node = None
                        if guid:
                            targets = []
                            try:
                                targets = self.src.guid_objects(guid) or []
                            except Exception:
                                targets = []
                            for tb, tp_ in targets:
                                obj_ = self.src.store._bundle_objs(tb).get(int(tp_)) if hasattr(self.src, "store") else None
                                tree_ = obj_.read_typetree() if obj_ is not None else None
                                if isinstance(tree_, dict) and "m_VisualTree" in tree_:
                                    layout_node = "layout:" + guid
                                    self.g.node(layout_node, "layout", name=tree_.get("m_Name"), bundle=tb, path_id=str(tp_))
                                    self.g.node("bundle:" + tb, "bundle", file=tb)
                                    self.g.edge(layout_node, "bundle:" + tb, "in_bundle", {"bundle": tb, "object": "VisualTreeAsset %s" % tp_})
                                    break
                        if layout_node:
                            self.g.edge(did, layout_node, "references_layout", {"bundle": crec["bundle"],
                                                                                "object": "TileDescription %s" % d_.get("id"),
                                                                                "field": "<Configurations>[%d].AssetRef.m_AssetGUID" % j})
                        elif asset_pid:
                            obj_ = self.src.store._bundle_objs(crec["bundle"]).get(int(asset_pid))
                            tree_ = obj_.read_typetree() if obj_ is not None else None
                            if isinstance(tree_, dict) and "m_VisualTree" in tree_:
                                g_ = self.src.guid_of(crec["bundle"], asset_pid)
                                layout_node = "layout:" + g_ if g_ else "layout:asset:%s:%s" % (crec["bundle"], asset_pid)
                                self.g.node(layout_node, "layout", name=tree_.get("m_Name"), bundle=crec["bundle"], path_id=str(asset_pid))
                                self.g.node("bundle:" + crec["bundle"], "bundle", file=crec["bundle"])
                                self.g.edge(layout_node, "bundle:" + crec["bundle"], "in_bundle", {"bundle": crec["bundle"], "object": "VisualTreeAsset %s" % asset_pid})
                                self.g.edge(did, layout_node, "references_layout", {"bundle": crec["bundle"],
                                                                                    "object": "TileDescription %s" % d_.get("id"),
                                                                                    "field": "<Configurations>[%d].Asset.m_PathID" % j})
                        if not layout_node:
                            self.gap("DESCRIPTION_LAYOUT_REFERENCE_UNRESOLVED", did,
                                     "configuration %d of %s: size %s, AssetRef GUID %s / Asset PathID %s resolves to no layout in the layout bundles" % (
                                         j, d_.get("id"), cfg.get("size"), guid, asset_pid), "composition")
        # Mirror screen-tile records as explicit graph nodes, each backed by the derived dump row.
        for i, tile in enumerate(t for t in self.dump["tiles"] if t["composition"] == composition_obj["name"]):
            tid = "tile:%s:%s:%s:%s:%s" % (composition_obj["name"], tile["cell_index"], tile["cfg_index"], tile["size"]["w"], tile["size"]["h"])
            self.g.node(tid, "tile", composition=composition_obj["name"], cell_index=tile["cell_index"], config_index=tile["cfg_index"], size=tile["size"], tile_layout_id=tile["tile_layout_id"], source_kind="derived-layout-dump", physical=physical)
            self.g.edge(comp_id, tid, "has_tile_configuration", {"bundle": None, "object": "fmlayout-index/2 tiles row %d" % i, "field": "tile_layout_id / size"})

    # ---- styles, rules, tokens, fonts, images
    def _rule_occurrence(self, sheets):
        occ = {}
        for s in sheets:
            seen = Counter()
            for r in s.rules:
                key = tuple(c[2] for c in r["chains"])
                seen[key] += 1
                occ[(s.name, r["i"])] = (s.bundle, key, seen[key] - 1)
        return occ

    def rule_id(self, sheet_name, i):
        b, key, k = self._occ[(sheet_name, i)]
        return "rule:%s/%s|%s|#%d" % (b, sheet_name, ", ".join(key), k)

    def _attach_cascade(self, root, built):
        bank = self.rd.bank.ordered()
        self._occ = self._rule_occurrence(bank)
        sheets, bundle_of = [], {}
        for s in bank:
            sid = "sheet:%s/%s" % (s.bundle, s.name)
            bundle_of[s.name] = s.bundle
            sheet_physical = self.src.named_asset_locator(s.bundle, s.name, "StyleSheet") if hasattr(self.src, "named_asset_locator") else None
            self.g.node(sid, "stylesheet", name=s.name, bundle=s.bundle, order=s.pos, physical=sheet_physical)
            self.g.node("bundle:" + s.bundle, "bundle", file=s.bundle)
            self.g.edge(sid, "bundle:" + s.bundle, "in_bundle", {"bundle": s.bundle, "object": "StyleSheet %s" % s.name})
            sheets.append({"id": sid, "bundle": s.bundle, "name": s.name, "order": s.pos, "rules": len(s.rules), "source": "render.sheets.ROOT_SHEETS (applied order)"})
        token_defs = {}
        for s in bank:
            for r in s.rules:
                if r["token"]:
                    for nm, _v, _c in r["props"]:
                        if nm.startswith("--"):
                            token_defs.setdefault(nm, []).append((s.name, r["i"]))
        used_tokens = set()
        self._join_stats = {"joined": 0, "not_drawn": {}, "unmatched_doc": [], "unmatched_render": []}
        for key, (rnode, tgt) in sorted(built.items(), key=lambda kv: kv[1][0].logical_id):
            res = self.rd.layout(tgt[0], tgt[1], DEPTH)
            depth_limited = [inc for inc in (res.get("includes") or []) if inc.get("problem") == "not expanded (depth limit)"]
            if depth_limited:
                self.style_coverage["partial"] = True
                self.gap("COMPUTED_STYLE_DEPTH_LIMIT", "layout:%s" % (rnode.locator.get("layout_guid")), "%d template instance(s) exceed the renderer cascade depth %d; structural expansion remains complete but styles are partial" % (len(depth_limited), DEPTH), "depth")
            # THE JOIN (finding 5): render nodes <-> UiDocument nodes by (bundle, path_id, m_Id) within this layout
            # instance - NOT by render position. The two trees disagree by design (the UiDocument keeps the roots
            # and non-visual components the cascade drops and expands without a depth limit; slot placement and
            # m_Id reuse differ), but both enumerate the SAME authored elements in the SAME authored order, so the
            # k-th occurrence of a (layout, m_Id) key on one side is the same element as the k-th on the other.
            pairs, not_drawn, unmatched_r, unmatched_d = self._join_instance(rnode, res, [inc.get("guid") for inc in depth_limited])
            self._join_stats["joined"] += len(pairs)
            for reason, nodes in not_drawn.items():
                self._join_stats["not_drawn"][reason] = self._join_stats["not_drawn"].get(reason, 0) + len(nodes)
            self._join_stats["unmatched_doc"] += unmatched_d
            self._join_stats["unmatched_render"] += unmatched_r
            if unmatched_r or unmatched_d:
                self.gap("JOIN_UNMATCHED", "layout:" + (rnode.locator.get("layout_guid") or ""), "%d render node(s) and %d UiDocument node(s) of this instance found no partner by (bundle, path_id, m_Id): e.g. render %s, document %s" % (
                    len(unmatched_r), len(unmatched_d), [(n.get("layout"), str(n.get("id"))) for n in unmatched_r[:3]], [(u.locator.get("layout"), str(u.locator.get("m_id"))) for u in unmatched_d[:3]]), "join")
            for u, rn in pairs:
                self._attach_pair(u, rn, bundle_of, used_tokens)
        cascade_stats = self.rd.cascade().stats
        for t in sorted(used_tokens):
            defs = token_defs.get(t, [])
            for sh, i in defs:
                rid = self.rule_id(sh, i)
                physical = self.src.named_asset_locator(bundle_of[sh], sh, "StyleSheet") if hasattr(self.src, "named_asset_locator") else None
                self.g.node(rid, "rule", sheet=sh, index=i, selector="token definition", physical=physical)
                self.g.edge("token:" + t, rid, "defined_by", {"bundle": bundle_of[sh], "object": "StyleSheet %s rule %d" % (sh, i), "field": t})
                definition = next((r for sheet in bank if sheet.name == sh for r in sheet.rules if r["i"] == i), None)
                for name, value, _colour in (definition or {}).get("props", []):
                    if name == t:
                        alias = re.fullmatch(r"var\((--[\w-]+)\)", str(value).strip())
                        if alias:
                            aid = "token:" + alias.group(1)
                            self.g.node(aid, "token", name=alias.group(1))
                            self.g.edge("token:" + t, aid, "aliases_to", {"bundle": bundle_of[sh], "object": "StyleSheet %s rule %d" % (sh, i), "field": name, "value": value})
            if not defs:
                self.gap("TOKEN_DEFINITION_NOT_TRACED", "token:" + t, "no applied sheet defines this token in a token rule (defined on an element scope, or by a sheet that is not applied)", "D9")
            elif len(defs) > 1:
                self.gap("TOKEN_DEFINED_MORE_THAN_ONCE", "token:" + t, "%d definitions in the applied sheets: %s" % (len(defs), defs), "G14")
        self._cascade_stats = cascade_stats
        return sheets

    # ---- the join (finding 5): one render result against one UiDocument layout instance
    @staticmethod
    def _not_drawn_reason(u):
        """Why the render does not draw this UiDocument node, or None. Roots (the render replaces every layout root
        with its children) and non-visual components (the cascade drops them, keeping their types under the
        parent's `components`) are the explicit not-drawn states; content the render did not expand to is handled
        by the caller through the depth-limited includes."""
        if u.kind == ROOT:
            return "root"
        if "non_visual" in u.flags:
            return "non_visual"
        return None

    def _join_instance(self, rnode, res, depth_limited_guids):
        """Pair one render result with one UiDocument instance subtree by (layout, m_Id) occurrences, in pre-order.
        Returns (pairs, not_drawn {reason: [node]}, unmatched_render, unmatched_doc). The keys are (layout NAME,
        m_Id): the render stamps each node with the layout it was read from and the UiDocument locator carries the
        same layout name and m_Id; both sides enumerate the same authored elements in the same authored order."""
        render_pool, doc_pool = {}, {}
        stack = list(reversed(res["tree"]))
        while stack:
            n = stack.pop()
            render_pool.setdefault((n.get("layout"), str(n.get("id"))), []).append(n)
            for c in reversed(n.get("children") or []):
                stack.append(c)
        not_drawn, unmatched_d = {}, []
        limited = set(g for g in depth_limited_guids if g)
        stack = [(rnode, False)]
        while stack:
            u, deep = stack.pop()
            reason = self._not_drawn_reason(u)
            if reason:
                not_drawn.setdefault(reason, []).append(u)
            elif deep:
                not_drawn.setdefault("past_render_depth", []).append(u)
            else:
                doc_pool.setdefault((u.locator.get("layout"), str(u.locator.get("m_id"))), []).append(u)
            deep2 = deep or ("included_layout_guid" in u.locator and u.locator["included_layout_guid"] in limited)
            for c in reversed(u.children):
                stack.append((c, deep2))
        pairs, unmatched_r = [], []
        for key, rns in render_pool.items():
            dus = doc_pool.get(key, [])
            if len(dus) != len(rns):
                self.gap("JOIN_OCCURRENCE_MISMATCH", "layout:%s" % (rnode.locator.get("layout_guid") or ""), "key %s: %d render occurrence(s) vs %d UiDocument occurrence(s); the extra side stays unjoined" % (
                    "%s|%s" % key, len(rns), len(dus)), "join")
            for rn, du in zip(rns, dus):
                pairs.append((du, rn))
            unmatched_r.extend(rns[len(dus):])
        for key, dus in doc_pool.items():
            if key not in render_pool:
                unmatched_d.extend(dus)
        return pairs, not_drawn, unmatched_r, unmatched_d

    def _attach_pair(self, u, rn, bundle_of, used_tokens):
        """One joined pair: the cascade result is attached and the graph gets the same rule/token/colour/asset
        edges the render position pairing used to create."""
        u.computed_style = rn
        u.render_pos = rn["_pos"]               # the render's own position of the joined element
        nid = "node:" + u.logical_id
        for m in rn.get("matched") or []:
            if (m["sheet"], m["rule"]) not in self._occ:
                continue
            rid = self.rule_id(m["sheet"], m["rule"])
            self.rule_ids[(m["sheet"], m["rule"])] = rid
            sheet_physical = self.src.named_asset_locator(bundle_of[m["sheet"]], m["sheet"], "StyleSheet") if hasattr(self.src, "named_asset_locator") else None
            self.g.node(rid, "rule", sheet=m["sheet"], index=m["rule"], selector=m["selector"], physical=sheet_physical)
            self.g.edge(nid, rid, "matched_by", {"bundle": bundle_of[m["sheet"]], "object": "StyleSheet %s rule %d" % (m["sheet"], m["rule"]), "field": "selector " + m["selector"]})
            self.g.edge(rid, "sheet:%s/%s" % (bundle_of[m["sheet"]], m["sheet"]), "defined_in", {"bundle": bundle_of[m["sheet"]], "object": "StyleSheet %s" % m["sheet"]})
        for prop, cd in (rn.get("computed") or {}).items():
            for t in cd.get("tokens") or []:
                if isinstance(t, str):
                    used_tokens.add(t)
                    self.g.node("token:" + t, "token", name=t)
                    source = cd.get("source") or {}
                    if source.get("inherited"):
                        source = source.get("from") or {}
                    source_bundle = u.locator.get("bundle") if source.get("inline") else bundle_of.get(source.get("sheet"))
                    self.g.edge(nid, "token:" + t, "uses_token", {"bundle": source_bundle, "object": ("inline StyleSheet of %s" % u.locator.get("path_id")) if source.get("inline") else "StyleSheet %s rule %s" % (source.get("sheet"), source.get("rule")),
                                                                     "field": prop, "selector": source.get("selector"), "token_chain": cd.get("tokens"), "resolved_value": cd.get("value")})
            v = str(cd.get("value"))
            if COLOUR.match(v) and not cd.get("tokens"):
                src = cd.get("source") or {}
                if src.get("inherited"):
                    src = src.get("from") or {}
                if src.get("inline"):
                    where = "inline:%s:%s:%s" % (u.locator["bundle"], u.locator["path_id"], u.locator["m_id"])
                    rf = {"bundle": u.locator["bundle"], "object": "VisualTreeAsset %s inline sheet" % u.locator["path_id"], "field": prop}
                elif (src.get("sheet"), src.get("rule")) in self._occ:
                    where = self.rule_id(src["sheet"], src["rule"])
                    rf = {"bundle": bundle_of[src["sheet"]], "object": "StyleSheet %s rule %d" % (src["sheet"], src["rule"]), "field": prop}
                else:
                    continue
                lid = "literal:%s|%s|%s" % (where, prop, v)
                self.g.node(lid, "hard_coded_colour", value=v, property=prop)
                self.g.edge(nid, lid, "uses_literal_colour", rf)
        for prop, a in (rn.get("assets") or {}).items():
            if not isinstance(a, dict):
                gap_id = "asset-gap:%s:%s" % (u.logical_id, prop)
                self.g.node(gap_id, "unresolved_asset", property=prop, value=a, reason="asset metadata is not an object")
                self.g.edge(nid, gap_id, "uses_unresolved_asset", {"bundle": u.locator.get("bundle"), "object": "computed style " + u.logical_id, "field": prop})
                self.gap("ASSET_METADATA_INCOMPLETE", gap_id, "asset property %s returned incomplete metadata" % prop, "asset")
                continue
            if "error" in a or "bundle" not in a or "path_id" not in a:
                gap_id = "asset-gap:%s:%s" % (u.logical_id, prop)
                self.g.node(gap_id, "unresolved_asset", property=prop, value=a, reason=a.get("error", "bundle or PathID missing"))
                self.g.edge(nid, gap_id, "uses_unresolved_asset", {"bundle": u.locator.get("bundle"), "object": "computed style " + u.logical_id, "field": prop})
                self.gap("ASSET_REFERENCE_UNRESOLVED", gap_id, str(a.get("error", "asset metadata omitted bundle or PathID")), "asset")
                continue
            kind = "font" if prop == "-unity-font-definition" else "image"
            aid = "asset:%s:%s" % (a["bundle"], a["path_id"])
            asset_physical = self.src.physical_locator(a["bundle"], a["path_id"], a.get("type")) if hasattr(self.src, "physical_locator") else None
            self.g.node(aid, kind, name=a.get("name"), type=a.get("type"), bundle=a["bundle"], path_id=a["path_id"], physical=asset_physical)
            self.g.node("bundle:" + a["bundle"], "bundle", file=a["bundle"])
            self.g.edge(nid, aid, "uses_font" if kind == "font" else "uses_image", {"bundle": a.get("from_bundle"), "object": "declared by a rule of the sheet bundle (asset(F:P))", "field": prop})
            self.g.edge(aid, "bundle:" + a["bundle"], "in_bundle", {"bundle": a["bundle"], "object": "%s %s" % (a.get("type"), a["path_id"])})

    def _document_gaps(self, doc):
        label = self.label
        self.gap("BUILD_LABEL_SOURCE", "document", "build label %r, status %r, label source %r; only a label, never used for identity" % (label.get("game_build"), label.get("status"), label.get("label_source")), "G4")
        self.gap("RULE_INDEX_IS_A_LOCATOR_ONLY", "document", "rules are identified by sheet, selector and occurrence; the rule index kept the same content at 153 of 5510 positions between builds B and C", "G3")
        self.gap("M_ID_IS_A_LOCATOR_ONLY", "document", "m_Id was re-minted for every element of the two TI layouts that changed between B and C; it is stored as a within-build locator", "G5")
        if self.identity_scheme["catalog_hash"] == "unknown":
            self.gap("BUILD_CATALOG_HASH_UNKNOWN", "document", "no catalog hash was supplied by the snapshot or layout dump; per-bundle SHA256 values still qualify physical assets", "G4")
        if self.rd is not None:
            from ..render.sheets import GAPS
            for g_ in GAPS:
                self.gap("SHEET_NOT_APPLIED", "document", g_, "6.4")
            st = getattr(self, "_cascade_stats", {})
            if st.get("state_selectors_skipped"):
                self.gap("STATE_SELECTORS_NOT_APPLIED", "document", "%d selectors with run-time states (%s) are not applied" % (st["state_selectors_skipped"], st.get("state_pseudo_classes")), "D9")
            rc = sum(1 for n in doc.all_nodes() if n.computed_style and n.computed_style.get("runtime_classes"))
            self.gap("RUNTIME_CLASSES_LEARNED", "document", "%d nodes carry classes learned per type from inspector dumps (data/render/runtime-classes.json) that no layout holds" % rc, "6.4")


def build_document(source, dump, composition, area, padding=screen_mod.PADDING, reserved_right=0, renderer=None, label=None, order="natural"):
    return Builder(source, dump, renderer, label, order).build(composition, area, padding, reserved_right)


def structural_keys(doc):
    """{structural_key: count} over the element-level nodes of a document (the synthetic screen and host nodes are left out: they are keyed by composition and cell, not by structure)."""
    return Counter(n.structural_key for n in doc.all_nodes() if "synthetic" not in n.flags)


def compare_documents(a, b):
    """Cross-build acceptance row: how many element-level nodes of `a` have a structural key that `b` holds exactly once, with the rest counted apart.
    matched    = the key is held once by each document;
    ambiguous  = the key is held more than once by at least one document (an `~k` occurrence mark would be needed to tell the nodes apart; not matched, not called unmatched);
    unmatched  = the key is held once by one document and not at all by the other.
    Rates are over a's element-level nodes (`a_nodes`) and b's (`b_nodes`)."""
    ka, kb = structural_keys(a), structural_keys(b)
    ambiguous = {k for k in set(ka) | set(kb) if ka.get(k, 0) > 1 or kb.get(k, 0) > 1}
    matched = {k for k in set(ka) & set(kb) if k not in ambiguous}
    only_a = {k for k in ka if k not in kb and k not in ambiguous}
    only_b = {k for k in kb if k not in ka and k not in ambiguous}
    by_layout = lambda keys: dict(Counter(k.split("|", 1)[0] for k in keys))
    return {"a_nodes": sum(ka.values()), "b_nodes": sum(kb.values()), "matched": len(matched), "ambiguous_keys": len(ambiguous), "ambiguous_nodes_a": sum(ka.get(k, 0) for k in ambiguous),
            "ambiguous_nodes_b": sum(kb.get(k, 0) for k in ambiguous), "unmatched_a": len(only_a), "unmatched_b": len(only_b),
            "matched_share_of_a": round(len(matched) / max(1, sum(ka.values())), 4), "matched_share_of_b": round(len(matched) / max(1, sum(kb.values())), 4),
            "unmatched_a_by_top_layout_guid": by_layout(only_a), "unmatched_b_by_top_layout_guid": by_layout(only_b), "unmatched_a_keys": sorted(only_a), "unmatched_b_keys": sorted(only_b),
            "ambiguous_key_list": sorted(ambiguous)}
