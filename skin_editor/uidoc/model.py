"""UiDocument model (Gate B of docs/UIDOCUMENT-AUDIT.md): one document that reaches every object taking part in a screen from one root.

An ADAPTER over the existing outputs (layout parse records, the layout dump, the style bank, the cascade); it changes none of them. Semantic classification, fake content and user operations are
NOT part of it: `semantic_map` and `user_operations` exist and stay empty, `semantic_role` is empty and `edit_safety` is "unknown" on every node.

Identity (decided 2026-11-17, section 11 of the audit):
- an element's `logical_id` is the layout GUID of the top layout it was reached from plus a STRUCTURAL PATH (type and name of every ancestor, the template-instance chain, an `~k` occurrence mark only among
  identical siblings). `m_Id` is a within-build LOCATOR only (it was re-minted for every element of the layouts that changed between builds B and C).
- a rule is identified by sheet, selector and occurrence, never by index (the index stays a locator).
- roots (the UXML root of every layout) and non-visual component nodes stay in the model, flagged."""
from dataclasses import dataclass, field
import json

SCHEMA = "fm-uidocument/1"
ELEMENT, TEMPLATE, ROOT, HOST, SCREEN = "element", "template", "root", "host", "screen"


@dataclass
class UiNode:
    logical_id: str
    structural_key: str                    # the logical id without `~k` marks: what is compared between builds
    locator: dict                          # within-build: layout, layout_guid, bundle, file (the CAB inside the bundle), path_id, m_id
    type: str
    name: str
    classes: list
    kind: str
    flags: list = field(default_factory=list)
    children: list = field(default_factory=list)          # ordered as the layout orders them (slot content sits where the existing expansion puts it)
    computed_style: object = None          # the existing cascade result for this node (the very dict `render` computed), None where the cascade has none (roots, non-visual)
    render_pos: str = None                 # the position string of the existing render tree this node was paired with
    semantic_role: str = ""
    edit_safety: str = "unknown"
    sources: dict = field(default_factory=dict)           # field name -> where it was read from

    def to_dict(self, computed="summary", rule_id=None):
        d = {"logical_id": self.logical_id, "structural_key": self.structural_key, "locator": self.locator, "type": self.type, "name": self.name, "classes": self.classes, "kind": self.kind,
             "flags": self.flags, "render_pos": self.render_pos, "semantic_role": self.semantic_role, "edit_safety": self.edit_safety, "sources": self.sources}
        cs = self.computed_style
        if computed == "full":
            d["computed_style"] = cs
        elif cs is None:
            d["computed_style"] = None
        else:
            d["computed_style"] = {"ref": "existing cascade result", "render_pos": self.render_pos, "properties": len(cs.get("computed") or {}), "matched_rules": [rule_id(m) for m in cs.get("matched") or []] if rule_id else None}
        d["children"] = [c.to_dict(computed, rule_id) for c in self.children]
        return d


@dataclass
class Edge:
    frm: str
    to: str
    type: str
    read_from: dict                        # the bundle and object the link was read from, and the field
    assumed: bool = False

    def to_dict(self):
        return {"from": self.frm, "to": self.to, "type": self.type, "read_from": self.read_from, "assumed": self.assumed}


class Graph:
    """Typed dependency graph. `uses[x]` are the edges leaving x, `used_by[x]` the edges arriving at x; both are derived from the same edge list."""

    def __init__(self):
        self.nodes, self.edges = {}, []
        self._seen = set()
        self.source_resolver = None

    def node(self, nid, kind, **info):
        if kind == "bundle" and info.get("file") and self.source_resolver:
            try:
                info["physical"] = self.source_resolver(info["file"], None, None)
            except (OSError, KeyError, ValueError):
                info["physical"] = {"bundle": info["file"], "resolution": "failed"}
        if nid not in self.nodes:
            self.nodes[nid] = dict(info, kind=kind)
        else:
            self.nodes[nid].update({k: v for k, v in info.items() if k not in self.nodes[nid]})
        return nid

    def edge(self, frm, to, type_, read_from, assumed=False):
        provenance = dict(read_from or {})
        bundle = provenance.get("bundle")
        if bundle and self.source_resolver:
            try:
                provenance["physical_source"] = self.source_resolver(bundle, provenance.get("object"), provenance.get("field"))
            except (OSError, KeyError, ValueError):
                provenance["physical_source"] = {"bundle": bundle, "resolution": "failed"}
        key = (frm, to, type_, json.dumps(provenance, sort_keys=True, default=str), bool(assumed))
        if key in self._seen:
            return
        self._seen.add(key)
        self.edges.append(Edge(frm, to, type_, provenance, assumed))

    def uses(self, nid):
        return [e for e in self.edges if e.frm == nid]

    def used_by(self, nid):
        return [e for e in self.edges if e.to == nid]

    def to_dict(self):
        uses, used_by = {}, {}
        for i, e in enumerate(self.edges):
            uses.setdefault(e.frm, []).append(i)
            used_by.setdefault(e.to, []).append(i)
        return {"nodes": self.nodes, "edges": [e.to_dict() for e in self.edges], "uses": uses, "used_by": used_by}


@dataclass
class Gap:
    code: str
    object: str
    reason: str
    audit_gap: str = ""                    # the number in docs/UIDOCUMENT-AUDIT.md section 9 / 11.2, where there is one

    def to_dict(self):
        return {"code": self.code, "object": self.object, "reason": self.reason, "audit_gap": self.audit_gap}


@dataclass
class UiDocument:
    screen: dict
    root_node: UiNode
    composition: dict
    style_sheets: list
    dependencies: Graph
    diagnostics: list
    source: dict
    semantic_map: dict = field(default_factory=dict)
    user_operations: list = field(default_factory=list)
    index: dict = field(default_factory=dict)             # logical_id -> UiNode, every node of the tree
    rule_ids: dict = field(default_factory=dict)          # (sheet name, rule index) -> logical rule id, for the rules this document matched
    identity_scheme: dict = field(default_factory=dict)   # explicit build qualification and cross-build limitations
    inventory: dict = field(default_factory=dict)         # independently collected participating-set inventory

    def all_nodes(self):
        stack = [self.root_node]
        while stack:
            n = stack.pop()
            yield n
            stack.extend(reversed(n.children))

    def to_dict(self, computed="summary"):
        rid = lambda m: self.rule_ids.get((m["sheet"], m["rule"]))
        return {"schema": SCHEMA, "source": self.source, "screen": self.screen, "root_node": self.root_node.to_dict(computed, rid), "composition": self.composition, "style_sheets": self.style_sheets,
                "dependencies": self.dependencies.to_dict(), "diagnostics": [g.to_dict() for g in self.diagnostics], "semantic_map": self.semantic_map, "user_operations": self.user_operations,
                "identity_scheme": self.identity_scheme, "inventory": self.inventory}
