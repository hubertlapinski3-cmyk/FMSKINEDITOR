"""The join: token / literal / class / selector -> style rules -> classes -> layout elements -> layouts -> screens, with areas.

Inputs are the app's own style index (StyleIndex) and the layout dump (docs/fmlayout-index-1.md). Stdlib only.
Evidence is labelled with three states, driven by the dump:
  verified          the subject class (or id) matches a static element record
  runtime-observed  it matches only classes the exporter observed being added at runtime (elements' runtime_classes)
  unverified        it matches neither (runtime-added or code-driven, or unused). Always displayed and flagged, never dropped.
Results are a lower bound: the dump has no template or table-factory references (see LOWER_BOUND)."""
import re

VERIFIED, RUNTIME, UNVERIFIED = "verified", "runtime-observed", "unverified"
UNASSIGNED = "unassigned"
CODE_COLOURS = ("NOT COVERED: colours set from game code (position chips, gradient start/end, rich-text colour tags, "
                "component colours) and inline layout styles are invisible to this join. A token can paint more places than listed.")
LOWER_BOUND = ("Lower bound: screens reached only through template or table-factory references are not covered, "
               "because the layout dump carries no such references. There is no geometry in the dump either.")
CAPS = {"evidence": 150, "layouts": 80, "elements": 6, "unverified": 150, "search_rules": 200}

_VAR = re.compile(r"var\((--[\w-]+)")
_SPLIT = re.compile(r"\s*>\s*|\s+")


def subject(selector):
    """Facts about the subject (last) compound of a selector: classes, ids, type, pseudo-classes."""
    parts = [p for p in _SPLIT.split(selector.strip()) if p]
    last = parts[-1] if parts else ""
    t = re.match(r"[A-Za-z_][\w-]*", last)
    return {"classes": re.findall(r"\.([\w-]+)", last), "ids": re.findall(r"#([\w-]+)", last),
            "type": t.group(0) if t else None, "pseudo": re.findall(r":([\w-]+)", last)}


class LayoutData:
    def __init__(self, dump):
        self.meta = dump["meta"]
        self.dump = dump               # read-only; the layout view builds its own indexes from it
        self.layouts = {l["id"]: l for l in dump["layouts"]}
        self.area_map = dump["areas"]["map"]
        self.anchors = dump["areas"]["anchors"]
        self.static, self.runtime, self.named = {}, {}, {}        # class/name -> {layout_id: [element, ...]}
        for e in dump["elements"]:
            for c in e["classes"]:
                self.static.setdefault(c, {}).setdefault(e["layout_id"], []).append(e)
            for c in e.get("runtime_classes", ()):
                self.runtime.setdefault(c, {}).setdefault(e["layout_id"], []).append(e)
            if e["name"]:
                self.named.setdefault(e["name"], {}).setdefault(e["layout_id"], []).append(e)
        self.parents, self.panels = {}, {}
        for i in dump["includes"]:
            self.parents.setdefault(i["to_layout_id"], set()).add(i["from_layout_id"])
        for t in dump["tiles"]:
            self.parents.setdefault(t["tile_layout_id"], set()).add(t["panel_layout_id"])
        for p in dump["panels"]:
            self.panels.setdefault(p["layout_id"], []).append(p["panel_id"])
        self._screens = {}

    # ---- areas and screens
    def area_of(self, layout_id):
        return self.area_map.get(self.layouts[layout_id]["name"], UNASSIGNED)

    def screens_of(self, layout_id):
        """(panel ids, cycle). Iterative walk up includes and tiles; each layout is visited once, so cycles (and self-includes)
        terminate. cycle is True when the graph above this layout contains a cycle."""
        if layout_id in self._screens:
            return self._screens[layout_id]
        seen, stack, found = {layout_id}, [layout_id], set()
        while stack:
            x = stack.pop()
            found.update(self.panels.get(x, ()))
            for p in self.parents.get(x, ()):
                if p not in seen:
                    seen.add(p)
                    stack.append(p)
        self._screens[layout_id] = (sorted(found), self.has_cycle_above(layout_id))
        return self._screens[layout_id]
    def has_cycle_above(self, layout_id):
        """True when the include/tile graph above this layout contains a cycle (iterative three-colour DFS)."""
        state, stack = {}, [(layout_id, iter(self.parents.get(layout_id, ())))]
        state[layout_id] = 1
        while stack:
            node, it = stack[-1]
            nxt = next(it, None)
            if nxt is None:
                state[node] = 2
                stack.pop()
                continue
            if state.get(nxt) == 1:
                return True
            if nxt not in state:
                state[nxt] = 1
                stack.append((nxt, iter(self.parents.get(nxt, ()))))
        return False

    # ---- matching one selector subject against the dump
    def match(self, sub):
        """-> (state, reason, [(layout_id, element)]) for a selector subject."""
        classes, ids = sub["classes"], sub["ids"]
        if not classes and not ids:
            return UNVERIFIED, "the selector's subject has no class or id (type or pseudo-class only): not matched against elements", []
        sets_static, sets_any = [], []
        for c in classes:
            st = {(l, e["local_id"]): e for l, els in self.static.get(c, {}).items() for e in els}
            rt = {(l, e["local_id"]): e for l, els in self.runtime.get(c, {}).items() for e in els}
            sets_static.append(st); sets_any.append({**rt, **st})
        for n in ids:
            nm = {(l, e["local_id"]): e for l, els in self.named.get(n, {}).items() for e in els}
            sets_static.append(nm); sets_any.append(nm)
        keys_static = set.intersection(*[set(s) for s in sets_static])
        if keys_static:
            return VERIFIED, "", [(k[0], sets_static[0].get(k) or next(s[k] for s in sets_static if k in s)) for k in sorted(keys_static)]
        keys_any = set.intersection(*[set(s) for s in sets_any])
        if keys_any:
            return RUNTIME, "class seen only as a runtime-added class on these elements", [(k[0], next(s[k] for s in sets_any if k in s)) for k in sorted(keys_any)]
        return UNVERIFIED, "no element in the dump carries it (runtime-added or code-driven, or unused)", []

    # ---- the join for a list of rule hits
    def join(self, hits):
        """hits: [{sheet, selector (joined), selectors (list), property, value}]. Evidence is grouped per (sheet, selector)."""
        groups = {}
        for h in hits:
            sels = h.get("selectors") or [h.get("selector", "")]
            for sel in sels:
                g = groups.setdefault((h["sheet"], sel), {"sheet": h["sheet"], "selector": sel, "properties": {}})
                g["properties"][h["property"]] = h.get("value", "")
        evidence, layouts, screens, unverified = [], {}, {}, []
        by_state = {VERIFIED: 0, RUNTIME: 0, UNVERIFIED: 0}
        for g in groups.values():
            sub = subject(g["selector"])
            state, reason, found = self.match(sub)
            by_state[state] += 1
            rec = {"sheet": g["sheet"], "selector": g["selector"], "properties": g["properties"], "state": state,
                   "pseudo": sub["pseudo"], "layouts": []}
            per = {}
            for lid, e in found:
                per.setdefault(lid, []).append(e)
            for lid, els in per.items():
                sc, cut = self.screens_of(lid)
                area = self.area_of(lid)
                rec["layouts"].append({"layout": self.layouts[lid]["name"], "area": area, "elements": [self._el(e) for e in els[:CAPS["elements"]]], "count": len(els), "cycle": cut})
                L = layouts.setdefault(lid, {"layout": self.layouts[lid]["name"], "area": area, "states": set(), "screens": sc, "properties": set(), "elements": [], "evidence": 0, "cycle": cut})
                L["states"].add(state); L["properties"].update(g["properties"]); L["evidence"] += 1
                for e in els[:CAPS["elements"]]:
                    if len(L["elements"]) < CAPS["elements"]:
                        L["elements"].append(self._el(e))
                for p in sc:
                    s = screens.setdefault(p, {"areas": set(), "layouts": set(), "states": set()})
                    s["areas"].add(area); s["layouts"].add(self.layouts[lid]["name"]); s["states"].add(state)
            if state == UNVERIFIED:
                unverified.append({"sheet": g["sheet"], "selector": g["selector"], "properties": sorted(g["properties"]), "reason": reason})
            elif state == RUNTIME:
                rec["note"] = reason
            evidence.append(rec)
        by_area = {}
        for L in layouts.values():
            by_area[L["area"]] = by_area.get(L["area"], 0) + 1
        order = lambda L: (-len(L["screens"]), L["layout"])
        lay = [dict(L, states=sorted(L["states"]), properties=sorted(L["properties"])) for L in sorted(layouts.values(), key=order)]
        return {"rules": len(groups), "by_state": by_state, "by_area": by_area,
                "evidence": sorted(evidence, key=lambda r: (r["state"] != VERIFIED, r["selector"]))[:CAPS["evidence"]], "evidence_total": len(evidence),
                "layouts": lay[:CAPS["layouts"]], "layouts_total": len(lay),
                "screens": {p: {"areas": sorted(v["areas"]), "layouts": sorted(v["layouts"])[:6], "states": sorted(v["states"])} for p, v in sorted(screens.items())},
                "unverified": unverified[:CAPS["unverified"]], "unverified_total": len(unverified)}

    @staticmethod
    def _el(e):
        return "%s#%s" % (e["type"].split(".")[-1], e["name"]) if e["name"] else e["type"].split(".")[-1]

    def fresh_notes(self):
        return {"code_set_colours": CODE_COLOURS, "lower_bound": LOWER_BOUND}


def _uses_to_hits(uses):
    return [{"sheet": u["sheet"], "selector": u["selector"], "selectors": u["selectors"], "property": u["property"], "value": u["value"]}
            for u in uses if not u.get("token_def")]


def where_token(ld, ix, token):
    """Hop 0 is the token itself; hop n are tokens that alias it (--a: var(--token)) n steps away. cross_screen_via_alias lists, per alias,
    the screens reached through that alias and not through the token directly."""
    if token not in ix.defs and token not in ix.uses:
        raise KeyError("no such token: " + token)
    hops, seen, frontier, depth, all_hits = [], {token}, [(token, None)], 0, []
    while frontier:
        nxt = []
        for t, via in frontier:
            hits = _uses_to_hits(ix.uses.get(t, []))
            all_hits += hits
            j = ld.join(hits)
            hops.append({"token": t, "hop": depth, "via": via, "rules": j["rules"], "by_state": j["by_state"], "by_area": j["by_area"],
                         "screens": sorted(j["screens"]), "new_screens_vs_hop0": []})
            for u in ix.uses.get(t, []):
                if u.get("token_def") and u["property"] not in seen:
                    seen.add(u["property"]); nxt.append((u["property"], t))
        frontier, depth = nxt, depth + 1
    direct = set(hops[0]["screens"])
    for h in hops[1:]:
        h["new_screens_vs_hop0"] = sorted(set(h["screens"]) - direct)
    total = ld.join(all_hits)
    out = {"token": token, "alias_hops": hops, "cross_screen_via_alias": {h["token"]: h["new_screens_vs_hop0"] for h in hops[1:] if h["new_screens_vs_hop0"]},
           "total": total, "zero_hit": total["rules"] == 0,
           "no_layout_evidence": total["rules"] > 0 and not (total["by_state"][VERIFIED] or total["by_state"][RUNTIME])}
    out.update(ld.fresh_notes())
    return out


def where_literal(ld, ix, rgb, a):
    """Rule hits of one exact RGBA, and of every alpha of the same RGB (the two swap modes)."""
    r = ix.literal(rgb, a)
    out = {"rgb": rgb, "a": a, "exact": ld.join(_uses_to_hits([h for h in r["exact"]])), "rgb_all": ld.join(_uses_to_hits([h for h in r["rgb_all"]]))}
    out["zero_hit"] = out["rgb_all"]["rules"] == 0
    out.update(ld.fresh_notes())
    return out


def where_search(ld, ix, text, limit=4000):
    """A class name or selector substring: matching rules, the tokens they read, then the same join. Classes that exist in layouts
    but have no rule are listed separately."""
    q = text.strip()
    if not q:
        raise ValueError("type a class or selector substring")
    ql, hits, rules, tokens = q.lower(), [], [], set()
    for sh in ix.sheets:
        for r in sh["rules"]:
            if not any(ql in s.lower() for s in r["s"]):
                continue
            for name, val, _cols in r["p"]:
                if len(hits) >= limit:
                    break
                h = {"sheet": sh["name"], "selector": ", ".join(r["s"]), "selectors": [s for s in r["s"] if ql in s.lower()], "property": name, "value": val}
                hits.append(h)
                tokens.update(_VAR.findall(val))
                if len(rules) < CAPS["search_rules"]:
                    rules.append({k: h[k] for k in ("sheet", "selector", "property", "value")})
    j = ld.join(hits)
    ruleless = {}
    if re.fullmatch(r"[\w-]+", q):
        known = {c for c in list(ld.static) + list(ld.runtime) if ql in c.lower()}
        in_rules = {c for h in hits for s in h["selectors"] for c in subject(s)["classes"]}
        for c in sorted(known - in_rules)[:50]:
            lids = set(ld.static.get(c, {})) | set(ld.runtime.get(c, {}))
            ruleless[c] = {"state": VERIFIED if c in ld.static else RUNTIME,
                           "layouts": sorted({ld.layouts[l]["name"] for l in lids})[:6], "areas": sorted({ld.area_of(l) for l in lids}),
                           "screens": sorted({p for l in lids for p in ld.screens_of(l)[0]})}
    out = {"query": q, "rules_matched": len(hits), "rules": rules, "truncated": len(hits) >= limit, "tokens_read": sorted(tokens)[:60],
           "total": j, "classes_in_layouts_without_rules": ruleless, "zero_hit": not hits and not ruleless}
    out.update(ld.fresh_notes())
    return out
