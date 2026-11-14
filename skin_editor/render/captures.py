"""Readers for the inspector's capture files (`fm-capture/1`, one JSON object per line; docs/PHASE9-PLAN.md section 9b).

A capture is a header line, one line per element, and a footer line (`{"end": true, ...}`). An aborted session has no footer; the reader says so instead of failing, and
never invents what is missing. What a capture holds is what the engine reported for that frame: nothing here is inferred.

- `read_capture(path)` -> Capture (header, elements by path, footer, ordering).
- `Capture.template_sources()` -> mode 2: every element that carries a template source, with its subtree size.
- `match_layouts(capture, layouts)` -> mode 2 against the bundles: each source name (and content hash when both sides have one) resolved to `bundle + path_id`, with
  ambiguity reported, never guessed. This is how view and tile-configuration questions are answered by observation.
- `Capture.expectations(...)` -> the checks a mode-1 capture gives a calibration fixture (resolved values and boxes of chosen elements)."""
import json
from pathlib import Path


def sheet_signature(rules):
    """The signature the plugin (0.3.1+) writes for a sheet: sha1 of one line per rule, "<selectors joined ', '>#<property count>", rule order kept.
    `rules` are index_styles entries (`{"s": [selector texts], "p": [[name, value, cols], ...]}`)."""
    import hashlib
    text = "".join("%s#%d\n" % (", ".join(r["s"]), len(r["p"])) for r in rules)
    return hashlib.sha1(text.encode("utf-8")).hexdigest()


class Capture:
    def __init__(self, header, elements, footer, order, sheet_contents=None):
        self.header, self.elements, self.footer, self.order = header, elements, footer, order
        self.sheet_contents = sheet_contents or []

    def match_sheets(self, sheets):
        """Identify every sheet content line against indexed sheets (`index_styles` entries: {name, bundle, rules}).
        Per line: status `identified` (one sheet has this signature AND the rule count), `ambiguous` (several), or `not-found`, with the evidence (names, rule counts).
        A line the plugin could not read (`error`) is `unreadable`. Nothing is guessed: no signature, no match."""
        by_sig = {}
        for sh in sheets:
            by_sig.setdefault(sheet_signature(sh["rules"]), []).append(sh)
        out = []
        for c in self.sheet_contents:
            row = {"owner": c.get("owner"), "name": c.get("name"), "instance": c.get("instance"), "rules": c.get("rules"), "signature": c.get("signature")}
            if c.get("error") or not c.get("signature"):
                row.update(status="unreadable", detail=c.get("error"), candidates=[])
            else:
                hits = [h for h in by_sig.get(c["signature"], []) if len(h["rules"]) == c.get("rules")]
                row.update(status="identified" if len(hits) == 1 else "ambiguous" if hits else "not-found",
                           candidates=[{"name": h["name"], "bundle": h["bundle"], "rules": len(h["rules"])} for h in hits])
            out.append(row)
        return out

    @property
    def complete(self):
        return bool(self.footer) and self.footer.get("state") == "done"

    def summary(self):
        f = self.footer or {}
        return {"mode": self.header.get("mode"), "game": self.header.get("game"), "plugin": self.header.get("plugin"), "elements": len(self.elements),
                "complete": self.complete, "state": f.get("state", "no footer (aborted or still running)"), "skipped": f.get("skipped"),
                "unvisited": f.get("unvisited"), "styles": self.header.get("styles"), "sources": self.header.get("sources"),
                "source_property_available": self.header.get("source_property_available")}

    def delivered_texts(self, subtree=None):
        """{path: {text, width, name}} for every visible SIText that holds text, optionally limited to one subtree: the value the game DELIVERED to the element (mode 1's
        `text`), exactly as read. Nothing is inferred from it."""
        pre = subtree + "/" if subtree else None
        out = {}
        for p, e in self.elements.items():
            if e.get("type") == "SIText" and e.get("visible") and e.get("text") and (pre is None or p == subtree or p.startswith(pre)):
                out[p] = {"text": e["text"], "width": (e.get("world") or [0, 0, 0])[2], "name": e.get("name")}
        return out

    def bindings_summary(self):
        """Mode 4 (plugin 0.4.0+, `bindings` in the header): counts over every SIText: how many carry a `binding` object, how many report IsBound / IsReady, how many have
        delivered text, and the distinct `binder` strings (the only path-like value reading can reach). A capture without the flag says so instead of returning zeros."""
        if not self.header.get("bindings"):
            return {"available": False, "note": "capture taken without bindings=true (plugin %s)" % self.header.get("plugin")}
        tx = [e for e in self.elements.values() if e.get("type") == "SIText"]
        b = [e["binding"] for e in tx if isinstance(e.get("binding"), dict)]
        strings = {}
        for x in b:
            s = x.get("binder")
            if isinstance(s, str):
                strings[s] = strings.get(s, 0) + 1
        return {"available": True, "sitext": len(tx), "with_binding_object": len(b), "no_binder": sum(1 for x in b if x.get("binder") is None),
                "is_bound": sum(1 for x in b if x.get("isBound") is True), "is_ready": sum(1 for x in b if x.get("isReady") is True),
                "unreadable": sum(1 for x in b if any(isinstance(v, str) and v.startswith("unreadable") for v in x.values()) or "error" in x),
                "with_text": sum(1 for e in tx if e.get("text")), "distinct_binder_strings": len(strings), "top_binder_strings": sorted(strings.items(), key=lambda kv: -kv[1])[:8]}

    def children_count(self, path):
        pre = path + "/"
        return sum(1 for p in self.elements if p.startswith(pre))

    def template_sources(self):
        """[{path, type, name, source, subtree}] for every element with a `source`, in capture order."""
        out = []
        for p in self.order:
            e = self.elements[p]
            if e.get("source"):
                out.append({"path": p, "type": e.get("type"), "name": e.get("name"), "source": e["source"], "subtree": self.children_count(p)})
        return out

    def resolved(self, path):
        return (self.elements.get(path) or {}).get("resolved")

    def box(self, path):
        """[x, y, w, h] in panel units (world bound), or None."""
        e = self.elements.get(path)
        return e.get("world") if e else None

    def expectations(self, paths, props=("color", "fontSize", "width", "height")):
        """{path: {label, box, resolved: {prop: value}}} for a calibration fixture: exactly what this capture measured for those elements."""
        out = {}
        for p in paths:
            e = self.elements.get(p)
            if not e:
                continue
            r = e.get("resolved") or {}
            out[p] = {"label": label_of(e), "box": e.get("world"), "resolved": {k: r[k] for k in props if k in r}}
        return out


def label_of(e):
    s = e.get("type", "")
    if e.get("name"):
        s += "#" + e["name"]
    return s + "".join("." + c for c in e.get("classes", []))


def read_capture(path):
    header, footer, elements, order, sheets = None, None, {}, [], []
    for n, line in enumerate(Path(path).read_text(encoding="utf-8").splitlines()):
        if not line.strip():
            continue
        try:
            o = json.loads(line)
        except ValueError:
            raise ValueError("%s line %d is not JSON (a truncated write?)" % (path, n + 1))
        if n == 0:
            if o.get("schema") != "fm-capture/1":
                raise ValueError("not an fm-capture/1 file: %s" % path)
            header = o
        elif o.get("end"):
            footer = o
        elif o.get("sheet_content"):
            sheets.append(o)                                   # 0.3.1+: rule content of the sheets attached to captured elements
        else:
            elements[o["path"]] = o
            order.append(o["path"])
    if header is None:
        raise ValueError("empty capture: %s" % path)
    return Capture(header, elements, footer, order, sheets)


def match_layouts(capture, layouts, hash_of=None):
    """Resolve each template source of a mode-2 capture to the layouts of the bundles.
    layouts: [{name, bundle, path_id, content_hash (optional)}]; `hash_of(row)` supplies a missing content hash, only for the candidates of a source name.
    A hash match is exact; a name with exactly one layout is a name match; a name that exists more than once and no hash to tell them apart is reported
    `ambiguous` with the candidates."""
    by_name = {}
    for r in layouts:
        by_name.setdefault(r["name"], []).append(r)
    out = []
    for t in capture.template_sources():
        src = t["source"]
        cands = by_name.get(src.get("name"), [])
        h = src.get("hash")
        if hash_of is not None:
            for c in cands:
                if "content_hash" not in c:
                    c["content_hash"] = hash_of(c)
        exact = [c for c in cands if h is not None and c.get("content_hash") == h]
        if exact:
            res = {"status": "matched by name and content hash", "layout": exact[0]}
        elif len(cands) == 1:
            res = {"status": "matched by name (hash not compared)" if h is None or cands[0].get("content_hash") is None else "name matches, HASH DIFFERS",
                   "layout": cands[0]}
        elif not cands:
            res = {"status": "no layout of that name in the bundles", "layout": None}
        else:
            res = {"status": "ambiguous", "candidates": [(c["bundle"], c["path_id"]) for c in cands]}
        out.append(dict(t, **res))
    return out


def infer_branches(top_nodes, subtree_elements):
    """Which branch of each switch element is live, read from a capture: {switch ordinal (depth-first, as html.switch_branch_rule counts them): branch index}.
    A branch scores the named elements ((type, name) pairs) it shares with the VISIBLE elements of the captured subtree; the best score wins, a tie or no named element keeps
    branch 0. This is structural evidence from the screen, not a guess about the game's binding; the scores are returned in `scores` for the evidence."""
    from .html import SWITCH_TYPES
    live = {(e.get("type"), e.get("name")) for e in subtree_elements if e.get("visible") and e.get("name")}
    chosen, scores, ordinal = {}, {}, [0]

    def named(n, acc):
        if n.get("name"):
            acc.add((n["type"], n["name"]))
        for c in n.get("children", []):
            named(c, acc)
        return acc

    def walk(n):
        if n.get("type") in SWITCH_TYPES and len(n.get("children", [])) > 1:
            k = ordinal[0]
            ordinal[0] += 1
            sc = [len(named(c, set()) & live) for c in n["children"]]
            best = max(range(len(sc)), key=lambda i: (sc[i], -i))
            chosen[k], scores[k] = (best if sc[best] > sc[0] else 0), sc
        for c in n.get("children", []):
            walk(c)
    for t in top_nodes:
        walk(t)
    return {"branches": chosen, "scores": scores}
