"""The cascade as a function: for every element of a render tree, which rules match, in what order they win, and the computed declarations.

Rules (Unity USS, as used by the existing selector tools): a rule applies with the specificity of its best matching selector (1 + 100*ids + 10*(classes + pseudo)
+ types, `token_patch.specificity`); declarations apply in order of (specificity, sheet position, rule order, declaration order), the layout's inline rule last.
A selector with a pseudo-class other than `:root` is a runtime state (hover, focus ...) and is not applied; the count is reported. Custom properties inherit and are
resolved into the values that use them; shorthands are expanded after resolution; the USS inherited properties are carried down. Every computed property is
classified by `values.classify` and nothing is dropped silently.

What the render cannot know is listed in each result (`gaps`): runtime classes not learned, sheets not applied, unresolved variables."""
import json
import time
from pathlib import Path

from .. import config, token_patch as tp
from . import values
from .layouts import is_visual

P_ID, P_CLASS, P_ELEMENT, P_PSEUDO, P_WILDCARD = tp.P_ID, tp.P_CLASS, tp.P_ELEMENT, tp.P_PSEUDO, tp.P_WILDCARD
RC_FILE = Path("data") / "render" / "runtime-classes.json"


def load_runtime_classes(path=None):
    p = Path(path) if path else config.resource_root() / RC_FILE
    if not p.is_file():
        return {}
    return {t: v["classes"] for t, v in json.loads(p.read_text(encoding="utf-8")).get("types", {}).items()}


def _compound_ok(node, parts):
    for t, v in parts:
        if t == P_ID:
            if node.get("name") != v:
                return False
        elif t == P_CLASS:
            if v not in node["_classes"]:
                return False
        elif t == P_ELEMENT:
            if node.get("type") != v:
                return False
        elif t == P_PSEUDO:
            return False
    return True                                    # wildcards match anything


def _match(chain, k, path, i):
    if not _compound_ok(path[i], chain[k][1]):
        return False
    if k == 0:
        return True
    if chain[k][0] == 1:                           # child
        return i > 0 and _match(chain, k - 1, path, i - 1)
    return any(_match(chain, k - 1, path, j) for j in range(i - 1, -1, -1))     # descendant


class Entry:
    __slots__ = ("spec", "pos", "rule", "chain", "text", "sheet")

    def __init__(self, spec, pos, rule, chain, text, sheet):
        self.spec, self.pos, self.rule, self.chain, self.text, self.sheet = spec, pos, rule, chain, text, sheet


class Cascade:
    def __init__(self, sheets, runtime_classes=None):
        t0 = time.perf_counter()
        self.sheets = sheets
        self.rc = runtime_classes if runtime_classes is not None else load_runtime_classes()
        self.by_key, self.root_vars, self.state_entries = {}, {}, []
        self.stats = {"sheets": len(sheets), "rules": 0, "selectors": 0, "state_selectors_skipped": 0, "root_variables": 0}
        pseudos = {}
        for sh in sheets:
            for rule in sh.rules:
                self.stats["rules"] += 1
                for chain, spec, text in rule["chains"]:
                    self.stats["selectors"] += 1
                    last = chain[-1][1]
                    ps = [v for t, v in last if t == P_PSEUDO]
                    if ps:
                        if ps == ["root"] and len(chain) == 1 and len(last) == 1:
                            for name, val, _cols in rule["props"]:
                                if name.startswith("--"):
                                    self.root_vars[name] = (val, sh.name, text)
                        else:
                            self.state_entries.append(Entry(spec, sh.pos, rule, chain, text, sh))      # kept for `state_declarations` (I3 state fixtures); the render itself never applies them
                            self.stats["state_selectors_skipped"] += 1
                            for p in ps:
                                pseudos[p] = pseudos.get(p, 0) + 1
                        continue
                    if any(t == P_PSEUDO for _c, parts in chain[:-1] for t, _v in parts):          # a pseudo-class on an ANCESTOR compound (a hovered tab colouring its label): never matches in the render, kept for the state fixtures
                        self.state_entries.append(Entry(spec, sh.pos, rule, chain, text, sh))
                    ids = [v for t, v in last if t == P_ID]
                    cls = [v for t, v in last if t == P_CLASS]
                    typ = [v for t, v in last if t == P_ELEMENT]
                    key = ("#", ids[0]) if ids else (".", cls[0]) if cls else ("T", typ[0]) if typ else "*"
                    self.by_key.setdefault(key, []).append(Entry(spec, sh.pos, rule, chain, text, sh))
        self.stats["root_variables"] = len(self.root_vars)
        self.stats["state_pseudo_classes"] = dict(sorted(pseudos.items(), key=lambda kv: -kv[1])[:8])
        self.stats["build_ms"] = round((time.perf_counter() - t0) * 1000)

    # ---- matching
    def classes_of(self, node):
        seen, out = set(), []
        for c in list(node.get("classes") or []) + list(self.rc.get(node.get("type"), [])):
            if c not in seen:
                seen.add(c)
                out.append(c)
        return out

    def matches(self, path):
        """Entries whose selector matches the last node of `path`, deduplicated per rule (best specificity), in cascade order."""
        node = path[-1]
        keys = [("T", node.get("type")), "*"] + [(".", c) for c in node["_classes"]]
        if node.get("name"):
            keys.append(("#", node["name"]))
        best = {}
        for k in keys:
            for e in self.by_key.get(k, ()):
                if _match(e.chain, len(e.chain) - 1, path, len(path) - 1):
                    ident = (e.pos, e.rule["i"])
                    if ident not in best or e.spec > best[ident].spec:
                        best[ident] = e
        return sorted(best.values(), key=lambda e: (e.spec, e.pos, e.rule["i"]))

    # ---- runtime state (hover, active, focus ...): not part of the render, used by the state fixtures
    def state_declarations(self, path, props=("background-color", "color")):
        """For the last node of `path` (nodes already computed, each may carry `_states`, a set of pseudo-class names such as {"hover"}): the declarations of the rules whose
        pseudo-class selector matches in that state, with the winner per property: {prop: {"value", "source"}}. The result of a state rule is only what the sheets declare."""
        def ok(node, parts):
            for t, v in parts:
                if t == P_ID and node.get("name") != v:
                    return False
                if t == P_CLASS and v not in node["_classes"]:
                    return False
                if t == P_ELEMENT and node.get("type") != v:
                    return False
                if t == P_PSEUDO and v not in node.get("_states", ()):
                    return False
            return True

        def match(chain, k, i):
            if not ok(path[i], chain[k][1]):
                return False
            if k == 0:
                return True
            if chain[k][0] == 1:
                return i > 0 and match(chain, k - 1, i - 1)
            return any(match(chain, k - 1, j) for j in range(i - 1, -1, -1))
        hits = {}
        for e in self.state_entries:
            for chain, spec, text in e.rule["chains"]:
                if any(t == P_PSEUDO for _c, parts in chain for t, _v in parts) and match(chain, len(chain) - 1, len(path) - 1):
                    cur = hits.get((e.pos, e.rule["i"]))
                    if cur is None or spec > cur[0].spec:
                        hits[(e.pos, e.rule["i"])] = (Entry(spec, e.pos, e.rule, chain, text, e.sheet),)
        scope = {k: (v[0], v[1], v[2]) for k, v in self.root_vars.items()}
        for nd in path:
            for p, d in (nd.get("computed") or {}).items():
                if p.startswith("--"):
                    scope[p] = (d["value"], "", "")
        look = self._lookup_factory(scope)
        out = {}
        for e, in sorted(hits.values(), key=lambda t: (t[0].spec, t[0].pos, t[0].rule["i"])):
            for name, val, _c in e.rule["props"]:
                cname, _inf = values.canonical(name)
                if cname.startswith("--"):
                    scope[cname] = (val, e.sheet.name, e.text)
                    continue
                resolved, unresolved = values.resolve_vars(val, look, [])
                for lh, text in values.expand(cname, resolved):
                    if lh in props:
                        out[lh] = {"value": text, "source": {"sheet": e.sheet.name, "rule": e.rule["i"], "selector": e.text, "specificity": e.spec}, "unresolved": unresolved or None}
        return out

    # ---- compute
    def compute(self, top_nodes):
        """Annotate a list of top-level render nodes in place: `_classes`, `matched`, `computed`, `unmapped`. Non-visual nodes are removed from the tree and
        kept under `components` of their parent. Returns the summary of what could not be explained."""
        self.summary = {"elements": 0, "properties": 0, "by_status": {}, "unresolved_variables": {}, "unexplained_classes": 0, "matched_rules": 0}
        root_scope = {k: (v[0], v[1], v[2]) for k, v in self.root_vars.items()}
        for n in top_nodes:
            self._walk(n, [], root_scope, {})
        return self.summary

    def _lookup_factory(self, scope):
        def look(name):
            hit = scope.get(name)
            return hit[0] if hit else None
        return look

    def _walk(self, node, ancestors, parent_scope, parent_computed):
        kids = node.get("children") or []
        node["components"] = [k["type"] for k in kids if not is_visual(k)]
        node["children"] = [k for k in kids if is_visual(k)]
        node["_classes"] = self.classes_of(node)
        path = ancestors + [node]
        ent = self.matches(path)
        node["matched"] = [dict({"sheet": e.sheet.name, "rule": e.rule["i"], "selector": e.text, "specificity": e.spec}, **({"origin": e.rule["origin"]} if e.rule.get("origin") else {})) for e in ent]
        decls = []                                              # (source, name, text) in winning order, inline last
        inferred = {}                                           # property name -> the raw id name it was inferred from (values.ID_NAMES)
        for e in ent:
            src = {"sheet": e.sheet.name, "rule": e.rule["i"], "selector": e.text, "specificity": e.spec}
            if e.rule.get("origin"):
                src["origin"] = e.rule["origin"]                    # a project's own rule: the editor opens it by (file, selector)
            for name, val, _cols in e.rule["props"]:
                cname, inf = values.canonical(name)
                if inf:
                    inferred[cname] = name
                decls.append((src, cname, val))
        for name, val in node.get("inline") or []:
            cname, inf = values.canonical(name)
            if inf:
                inferred[cname] = name
            decls.append(({"inline": True, "layout": node.get("layout")}, cname, val))
        scope = dict(parent_scope)
        for src, name, val in decls:
            if name.startswith("--"):
                scope[name] = (val, src.get("sheet") or "inline", src.get("selector") or "inline")
        look = self._lookup_factory(scope)
        computed = {}
        for src, name, val in decls:
            if name.startswith("--"):
                continue
            chain, unresolved = [], []
            resolved, unresolved = values.resolve_vars(val, look, chain)
            for lh, text in values.expand(name, resolved):
                computed[lh] = {"value": text, "raw": val if val != text else None, "tokens": chain or None, "source": src, "unresolved": unresolved or None}
                for u in unresolved:
                    self.summary["unresolved_variables"][u] = self.summary["unresolved_variables"].get(u, 0) + 1
        for p in values.INHERITED:
            if p not in computed and p in parent_computed:
                pc = parent_computed[p]
                computed[p] = {"value": pc["value"], "raw": None, "tokens": pc.get("tokens"), "source": {"inherited": True, "from": pc["source"]}, "unresolved": None}
        for p, d in computed.items():
            css, status, note = values.classify(p)
            d["status"], d["note"] = status, note
            if p in inferred:
                d["inferred_name_from"] = inferred[p]          # the name is inferred from the property id's numbering and value pattern, not read
            d["css"] = [list(x) for x in values.to_css(p, d["value"])]
            self.summary["properties"] += 1
            self.summary["by_status"][status] = self.summary["by_status"].get(status, 0) + 1
        node["computed"] = computed
        node["scope_size"] = len(scope)
        self.summary["elements"] += 1
        self.summary["matched_rules"] += len(ent)
        for c in node["children"]:
            self._walk(c, path, scope, computed)
