"""Delivered text into the render (M7): a capture with binding reads (plugin 0.4.0) records, for each SIText, the text the game delivered and its Binder path, the element's position
in its template tree (`.../Ancestor/t:Type/name`: named ancestors by name, unnamed ones as `t:Type`, template instances by their GUID name, the element's own name or `t:SIText`
last). The render node's own chain of ancestors is the same thing, so the last K segments pair a captured text with a layout node. Pairing rules, nothing guessed:
- GUID-named segments count as `t:TemplateContainer` on both sides;
- the key is the last K (3) segments; when several nodes and several captured texts share a key they are paired in depth-first / capture order, one to one, and a node with no
  captured partner keeps its sample text (so a hidden switch branch or a node the capture did not reach is never given someone else's text);
- only nodes that are drawn (the shown switch branch) take part.
`apply` sets `attrs.text` and `delivered: true` on the paired nodes and returns what was paired and what was not."""
import re

GUID = re.compile(r"^[0-9a-f]{32}(\|[0-9a-f]{32})?$")
K = 3


def _seg(s):
    return "t:TemplateContainer" if GUID.match(s) else s


def key_of(segments, k=K):
    segs = [s for i, s in enumerate(segments) if not (i == 0 and s == "...")]          # the game cuts the head of a Binder path: ".../a/b" is "a/b" as far as it goes
    return tuple(_seg(s) for s in segs[-k:])


def chains(top_nodes):
    """[(segments, node)] for every drawn SIText of a render tree, depth first; nodes inside a switch branch that is not shown are skipped."""
    out = []

    def walk(n, anc):
        if "switch-branch-not-shown" in (n.get("layout_rules") or ()):
            return
        segs = anc + [n.get("name") or "t:" + n.get("type", "VisualElement")]
        if n.get("type") == "SIText":
            out.append((segs, n))
        for c in n.get("children", []):
            walk(c, segs)
    for t in top_nodes:
        walk(t, [])
    return out


def apply(top_nodes, delivered, k=K):
    """Pair `delivered` ([{binder, text, ...}], capture order) with the drawn SIText nodes. Returns {paired, nodes, unpaired_texts, ambiguous_keys}."""
    pool = {}
    for d in delivered:
        pool.setdefault(key_of(d["binder"].split("/"), k), []).append(d)
    paired, nodes, ambiguous = 0, 0, set()
    for segs, n in chains(top_nodes):
        nodes += 1
        key = key_of(segs, k)
        bucket = pool.get(key)
        if not bucket:
            continue
        if len(bucket) > 1:
            ambiguous.add(key)
        d = bucket.pop(0)
        n.setdefault("attrs", {})["text"] = d["text"]
        n["delivered"] = True
        n["delivered_from"] = {"path": d.get("path"), "width": d.get("width")}
        paired += 1
    left = sum(len(v) for v in pool.values())
    return {"paired": paired, "nodes": nodes, "unpaired_texts": left, "ambiguous_keys": len(ambiguous)}
