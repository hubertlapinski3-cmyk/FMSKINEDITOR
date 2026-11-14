"""Fix round after 1.0.0, problem 1: every FAIL row of the calibration report is examined one by one (this module), not labelled by a fixture-wide rule.

The method, per FAIL row (the report publishes the result per row, grade included):

 Step 1  verify the pair before the cause: same type and name, the paired live element sits under the live element paired with the render parent, its depth, text and visible flag.
 Step 2  split a box row into x, y, w, h, each against its own tolerance.
 Step 3  subtract the parent's and the preceding sibling's delta: each failing component is either INHERITED (it equals a displacement some neighbour already has: the parent's,
         the parent's centred, the preceding sibling's end, the sum or maximum of the children) or an ORIGIN (a local residual nothing else explains). An inherited component names the
         origin row(s) it traces to.
 Step 4  an origin must be explained by a mechanism that predicts its magnitude where a magnitude exists; Step 5: and by one independent fact from the capture (a class absent from
         the layout, an inline value set in code, a non-zero pseudo-state mask, wrapper elements the layout does not have, children built at run time).
 A component with no supporting fact is UNEXPLAINED. Nothing here names a fixture or a literal measured value: every predicate reads dump/capture fields (listed in RULES).

GRADES: `measured fact` = an independent capture fact supports it (and, where a magnitude exists, it matches); `magnitude only` = the size or value matches but no independent fact
links it to this element; there is no `asserted`: a mechanism with neither is UNEXPLAINED.

The rules below were written and committed BEFORE they were run over all 78 rows; changing one means saying so in the report (see docs/evidence/phase9-fix-round-causes-*.md)."""
import json
import re
from pathlib import Path

INHERIT_TOL = 1.0                   # px: a component equal to a neighbour's displacement within this is inherited
COMP = "xywh"
UNEXPLAINED = "UNEXPLAINED"

# each rule: key, label, what it reads (the dump/capture fields), grade when it fits
RULES = {
    "runtime-class": ("a class the game sets in code (absent from the layout) carries the value: applying the live class set through the game's own sheets reproduces it",
                      "live classes minus the render node's classes; the cascade over the live classes; the live size or flex value"),
    "empty-code-list": ("a list filled at run time is drawn empty: the game builds its rows in code, the render has none, so it collapses to 0 by 0",
                        "render node has no children and 0 by 0; live element has children in the capture and a non-zero size; the deficit equals the live size"),
    "inline-display-none": ("display:none set in code (inline in the capture, in no layout or sheet): the live element is 0 by 0, the render draws it",
                            "capture inline display = None; live size 0 by 0; the render draws it with a size"),
    "state-captured": ("the capture was taken while the element was in a pseudo-state (mask bit set): the game's own :pseudo rule declares exactly the live value",
                       "capture pseudo-state mask; the cascade's state rules for the render node's classes under that mask"),
    "runtime-sheet-colour": ("a colour painted by a run-time sheet (empty name, negative instance id) that the render does not apply",
                             "the live value is among the values the capture's run-time sheet samples declare; the render declares another value"),
    "code-built-wrapper": ("elements the game builds in code sit between this node and its layout parent (Unity ScrollView internals), changing how the node is laid out",
                           "live path depth between the paired parent and the node; the wrapper elements' names and classes in the capture"),
    "stand-in-font": ("same text string and font size, the stand-in font gives another width",
                      "render text equals live text; live font size; |width residual| at most a quarter of the live width"),
    "code-built-children": ("a widget the game fills in code: the live element has children in the capture and no template source, the layout holds none (its size is set by that content; the size itself is not predicted)",
                            "render node has no children; live element has children in the capture; live source absent"),
    "sub-pixel-tolerance": ("a sub-pixel offset on an element whose tolerance (5 percent of its size) is under half a pixel: the same offset the passing rows of the fixture carry",
                            "tolerance of the component; |delta| under 1 px; the median delta of the rows that pass in the same fixture"),
}
GRADE_FACT, GRADE_MAGNITUDE = "measured fact", "magnitude only"
MASK_BITS = {1: "active", 2: "hover", 8: "checked", 32: "disabled", 64: "focus"}


def _tolx(v):
    """The equality tolerance for 'this displacement equals that one': 1 px plus 1 percent of the displacement (a 105 px list leaves a 1 px rounding)."""
    return INHERIT_TOL + 0.01 * abs(v)


def _close(a, b):
    return a is not None and b is not None and abs(a - b) <= _tolx(b)


def candidates(tab, i, k):
    """Every neighbour displacement the failing component k of row i could be: [(kind, predicted value, [(row, comp) sources])]."""
    n = tab[i]
    d = n["d"]
    par = tab[n["parent"]] if n["parent"] is not None else None
    prev = tab[n["prev"]] if n["prev"] is not None else None
    sibs = [c for c in (par["kids"] if par else []) if tab[c]["d"] and not tab[c]["hidden"]]
    out = []
    if k < 2:
        s = k + 2
        if par and par["d"]:
            out.append(("parent", par["d"][k], [(n["parent"], k)]))
            out.append(("centred-in-parent", par["d"][k] + (par["d"][s] - d[s]) / 2, [(n["parent"], k), (n["parent"], s), (i, s)]))
        if prev and prev["d"]:
            out.append(("preceding-sibling-end", prev["d"][k] + prev["d"][s], [(n["prev"], k), (n["prev"], s)]))
            out.append(("preceding-sibling", prev["d"][k], [(n["prev"], k)]))
        if par and par["d"] and i in sibs and len(sibs) > 1:         # space-between: the free space left by narrower (or wider) siblings is shared out between the gaps
            pos = sibs.index(i)
            before = sum(tab[c]["d"][s] for c in sibs[:pos])
            total = sum(tab[c]["d"][s] for c in sibs)
            out.append(("space-between-share", par["d"][k] + before - pos * total / (len(sibs) - 1), [(c, s) for c in sibs]))
    else:
        if par and par["d"]:
            out.append(("parent-size", par["d"][k], [(n["parent"], k)]))
            others = [c for c in sibs if c != i]
            if others and abs(par["d"][k]) <= 1.0:                      # the parent keeps its size, so what a sibling lost this node gains (flex-grow)
                out.append(("complement-of-siblings", -sum(tab[c]["d"][k] for c in others), [(c, k) for c in others]))
        kids = [c for c in n["kids"] if tab[c]["d"] and not tab[c]["hidden"]]
        if kids:
            out.append(("sum-of-children", sum(tab[c]["d"][k] for c in kids), [(c, k) for c in kids]))
            out.append(("max-of-children", max(tab[c]["d"][k] for c in kids), [(c, k) for c in kids]))
            if len(kids) == 1:                                           # a child larger than its parent (overflow): the parent follows the child's own content
                grand = [g for g in tab[kids[0]]["kids"] if tab[g]["d"] and not tab[g]["hidden"]]
                if grand:
                    out.append(("content-of-child", sum(tab[g]["d"][k] for g in grand), [(g, k) for g in grand]))
    return out


def inheritance(tab, i, k):
    """All the neighbour displacements the failing component k of row i equals, and a partial share when none does but the children explain part of it."""
    d = tab[i]["d"][k]
    cands = candidates(tab, i, k)
    matches = [{"kind": kind, "sources": src, "value": round(v, 1)} for kind, v, src in cands if _close(d, v)]
    partial = None
    if not matches and k >= 2:
        for kind, v, src in cands:
            if kind in ("sum-of-children", "content-of-child") and abs(v) >= 2.0 and v * d > 0 and abs(v) < abs(d):
                partial = {"kind": kind, "sources": src, "value": round(v, 1), "residual": round(d - v, 1)}
                break
    return matches, partial


def _depth(tab, i):
    n = 0
    while tab[i]["parent"] is not None:
        i, n = tab[i]["parent"], n + 1
    return n


def propagate(tab, failing, fits):
    """failing: {row index: [failing component indices]}; fits(key) -> True when a mechanism with an independent fact fits that (row, comp). Returns {(row, comp): {status, matches, partial,
    origins, cycle}}: `origins` are the (row, comp) pairs at the end of every chain the component can be traced along. A chain that only loops (a parent sized by its child that is sized
    by its parent) cannot be separated by deltas: the loop's origin is the deepest member where a mechanism fits; if none fits, the group is unexplained and its deepest member stands for it."""
    status = {}
    for i, comps in failing.items():
        for k in comps:
            matches, partial = inheritance(tab, i, k)
            status[(i, k)] = {"status": "inherited" if matches else "origin", "matches": matches, "partial": partial, "cycle": False}
    terminals, group_of = set(), {}

    def reachable(key):
        out, todo = set(), [key]
        while todo:
            x = todo.pop()
            if x in out or x not in status:
                continue
            out.add(x)
            for m in status[x]["matches"]:
                todo += [s for s in m["sources"] if s in status and s not in out]
        return out

    def origins(key, trail):
        st = status.get(key)
        if st is None:                       # a neighbour that does not fail at this component: not an origin of anything
            return set(), set()
        if st["status"] == "origin" or key in terminals:
            return {key}, set()
        if key in group_of:                  # already attributed to the origin of its group
            return {group_of[key]}, set()
        if key in trail:
            return set(), {key}
        out, cyc = set(), set()
        for m in st["matches"]:
            for s in m["sources"]:
                o, c = origins(s, trail | {key})
                out |= o
                cyc |= c
        return out, cyc | ({key} if not out else set())
    for _round in range(len(status) + 1):
        stuck = {}
        for key, st in status.items():
            if st["status"] == "inherited":
                o, cyc = origins(key, frozenset())
                if not o:
                    stuck[key] = {key} | cyc
        if not stuck:
            break
        keys_all = set().union(*[reachable(k) for k in stuck])
        adj = {k: set() for k in keys_all}
        for k in keys_all:
            for m in status[k]["matches"]:
                for s in m["sources"]:
                    if s in adj:
                        adj[k].add(s)
                        adj[s].add(k)
        seen = set()
        for k0 in sorted(keys_all):                                            # connected groups of components that share one displacement: ONE origin for the group
            if k0 in seen:
                continue
            comp, todo = set(), [k0]
            while todo:
                x = todo.pop()
                if x in comp:
                    continue
                comp.add(x)
                todo += [y for y in adj[x] if y not in comp]
            seen |= comp
            members = {k for k in comp if k in stuck} | {k for k in comp if status[k]["status"] == "inherited" and not origins(k, frozenset())[0]}
            if not members:
                continue
            fit = [m for m in members if fits(m)]
            pick = max(fit or members, key=lambda kk: (_depth(tab, kk[0]), -kk[0]))
            terminals.add(pick)
            status[pick]["cycle"] = True
            for k in members:
                group_of[k] = pick
    for key, st in status.items():
        o, _c = origins(key, frozenset())
        if not o and key in group_of:
            o = {group_of[key]}                                                # shares the group's displacement but no chain reaches the origin: attributed to it
        st["origins"] = sorted(o)
    return status

# ---------------------------------------------------------------- mechanisms (the frozen rules)
def _live(rec):
    return rec.get("live") if isinstance(rec.get("live"), dict) else {}


def _px(v):
    try:
        return float(str(v).replace("px", ""))
    except (TypeError, ValueError):
        return None


def rule_runtime_class(rec, casc, comp=None):
    """The live element carries classes the layout does not: put them on a copy of the render node, run the game's cascade and see whether it yields the live value."""
    lv, rn = _live(rec), rec.get("render") or {}
    extra = [c for c in (lv.get("classes") or []) if c not in (rn.get("all_classes") or [])]
    if not extra:
        return None
    node = {"type": rn["type"], "name": rn.get("name", ""), "classes": list(rn.get("classes") or []) + extra, "children": [], "inline": [], "attrs": {}, "id": None, "layout": None}
    casc.compute([node])
    c = node["computed"]
    ev = {"extra_live_classes": extra, "cascade_with_them": {k: c[k]["value"] for k in ("width", "height", "flex-shrink") if k in c}}
    prop = rec["property"]
    if prop == "flex-shrink":
        ok = "flex-shrink" in c and str(c["flex-shrink"]["value"]) == str(rec["expected"])
    elif prop == "box" and comp in ("w", "h"):
        want = (rec.get("expected_box") or [None] * 4)["xywh".index(comp)]
        have = _px(c.get("width" if comp == "w" else "height", {}).get("value"))
        ok = have is not None and want is not None and abs(have - want) <= max(0.05 * want, 1.0)
        ev["predicted_px"], ev["live_px"] = have, want
    else:
        return None
    return (GRADE_FACT, ev) if ok else None


def rule_empty_code_list(rec, comp=None):
    lv, rn = _live(rec), rec.get("render") or {}
    if rec["property"] != "box" or comp not in ("w", "h") or rn.get("has_children") or lv.get("source"):
        return None
    got, exp = rec.get("got_box"), rec.get("expected_box")
    if not got or not exp or got[2] > 0.5 or got[3] > 0.5 or (lv.get("children_in_capture") or 0) < 1:
        return None
    k = "xywh".index(comp)
    if abs(rec["d"][k] + exp[k]) > 1.0:          # the deficit must equal the live size: the render draws nothing where the game has the list
        return None
    return GRADE_FACT, {"live_children_in_capture": lv["children_in_capture"], "render_children": 0, "deficit": rec["d"][k], "live_size": exp[k]}


def rule_inline_display_none(rec, comp=None):
    lv = _live(rec)
    inline = lv.get("inline") or {}
    if rec["property"] != "box" or str(inline.get("display")) != "None":
        return None
    exp, got = rec.get("expected_box"), rec.get("got_box")
    if not exp or exp[2] > 0.5 or exp[3] > 0.5 or not got or (got[2] <= 0.5 and got[3] <= 0.5):
        return None
    return GRADE_FACT, {"inline": {"display": "None"}, "live_size": exp[2:], "render_size": got[2:]}


def rule_state_captured(rec, casc):
    lv, rn = _live(rec), rec.get("render") or {}
    mask = lv.get("pseudo") or 0
    if not mask or rec["property"] not in ("background-color", "color"):
        return None
    states = {MASK_BITS[b] for b in MASK_BITS if mask & b} | ({"enabled"} if not mask & 32 else set())
    node = {"type": rn["type"], "name": rn.get("name", ""), "classes": list(rn.get("all_classes") or []), "children": [], "inline": [], "attrs": {}, "id": None, "layout": None}
    casc.compute([node])
    node["_states"] = states
    d = casc.state_declarations([node], (rec["property"],)).get(rec["property"])
    if d and str(d["value"]).upper().lstrip("#") == str(rec["expected"]).upper().lstrip("#"):
        return GRADE_FACT, {"mask": mask, "states": sorted(states), "state_rule": d["source"]["selector"], "declares": d["value"]}
    return None


def rule_runtime_sheet_colour(rec, runtime_values):
    if rec["property"] not in ("background-color", "color", "background-color (rest)") or not runtime_values:
        return None
    live = str(rec["expected"]).upper()
    if live in runtime_values and str(rec["got"]).upper() != live:
        return GRADE_MAGNITUDE, {"live_value_in_runtime_sheet_samples": True, "note": "the sheet's sampled rules paint this value elsewhere; this element's own rule is not in the 80-rule sample"}
    return None


def rule_wrapper_gap(rec, comp=None):
    w = (rec.get("pair") or {}).get("wrappers")
    if not w or rec["property"] != "box":
        return None
    return GRADE_FACT, {"wrappers_in_capture_not_in_layout": [{"name": x["name"], "classes": x["classes"][:2]} for x in w]}


def rule_stand_in_font(rec, comp=None):
    rn, lv = rec.get("render") or {}, _live(rec)
    if rec["property"] != "box" or comp not in ("w", "h") or rn.get("type") != "SIText":
        return None
    if not lv.get("text") or (rn.get("text") or "").strip() != lv["text"].strip():
        return None
    exp = rec["expected_box"]["xywh".index(comp)]
    if exp and abs(rec["d"]["xywh".index(comp)]) <= 0.25 * exp:
        return GRADE_MAGNITUDE, {"same_text": lv["text"][:30], "live_font_size": lv.get("font_size"), "residual": rec["d"]["xywh".index(comp)], "live": exp}
    return None


def rule_code_built_children(rec, comp=None):
    lv, rn = _live(rec), rec.get("render") or {}
    if rec["property"] != "box" or rn.get("has_children") or lv.get("source") or (lv.get("children_in_capture") or 0) < 2:
        return None
    return GRADE_FACT, {"live_children_in_capture": lv["children_in_capture"], "render_children": 0, "magnitude_predicted": False}


def rule_sub_pixel(rec, comp=None):
    if rec["property"] != "box" or comp is None or not rec.get("tol") or rec["tol"]["xywh".index(comp)] > 0.5:
        return None
    k = "xywh".index(comp)
    off = rec.get("tile_offset")
    if abs(rec["d"][k]) < 1.0 and off and abs(rec["d"][k] - off[k]) <= 0.5:
        return GRADE_FACT, {"tolerance": rec["tol"][k], "delta": rec["d"][k], "median_delta_of_passing_rows": off[k], "magnitude_predicted": True}
    return None


def mechanisms(rec, comp, casc, runtime_values):
    """Every rule that fits this origin component, in priority order: [(key, grade, evidence)]. Priority is by independence of the fact, not by fixture."""
    out = []
    for key, fn in (("runtime-class", lambda: rule_runtime_class(rec, casc, comp)), ("empty-code-list", lambda: rule_empty_code_list(rec, comp)),
                    ("inline-display-none", lambda: rule_inline_display_none(rec, comp)), ("state-captured", lambda: rule_state_captured(rec, casc)),
                    ("runtime-sheet-colour", lambda: rule_runtime_sheet_colour(rec, runtime_values)), ("stand-in-font", lambda: rule_stand_in_font(rec, comp)),
                    ("sub-pixel-tolerance", lambda: rule_sub_pixel(rec, comp)), ("code-built-wrapper", lambda: rule_wrapper_gap(rec, comp)),
                    ("code-built-children", lambda: rule_code_built_children(rec, comp))):
        try:
            r = fn()
        except (KeyError, TypeError, ValueError, StopIteration):
            r = None
        if r:
            ev = dict(r[1])
            ev.setdefault("magnitude_predicted", key in ("runtime-class", "empty-code-list", "inline-display-none", "state-captured"))
            out.append((key, r[0], ev))
    out.sort(key=lambda m: (not m[2]["magnitude_predicted"], m[1] != GRADE_FACT))          # a mechanism that predicts the magnitude outranks one that only names a class of cause
    return out


# ---------------------------------------------------------------- facts and the examination of all FAIL rows
def row_id(fixture, row):
    """A unique id for a published row: fixture, check, element, property and the live element's capture path (or the node index): the old key collided on same-named rows."""
    return "%s|%s|%s|%s|%s" % (fixture, row["check"], row["element"], row["property"], row.get("live") if row.get("live") else ("n%s" % row["node"] if row.get("node") is not None else "-"))


def capture_for(fx, ui_dir):
    from . import captures
    m = re.search(r"capture (\S+\.ndjson)", fx["fixture"].get("source", ""))
    if not m or not (Path(ui_dir) / m.group(1)).is_file():
        return None
    return captures.read_capture(Path(ui_dir) / m.group(1))


def runtime_sheet_values(cap):
    vals = set()
    for sc in (cap.sheet_contents if cap else []) or []:
        if sc.get("name") == "" and (sc.get("instance") or 0) < 0:
            for s in sc.get("sample", []):
                for p in s.get("p", []):
                    if ":" in p:
                        vals.add(p.split(":", 1)[1].strip().upper())
    return vals


def _tree_maps(top):
    parent, prev = {}, {}

    def walk(n, p):
        parent[id(n)] = p
        last = None
        for c in n.get("children", []):
            prev[id(c)] = last
            walk(c, n)
            last = c
    for i, t in enumerate(top):
        prev[id(t)] = top[i - 1] if i else None
        walk(t, None)
    return parent, prev


def fixture_tables(ctx, fx):
    """Re-render one layout fixture and return (node table, per-node render info, pairs, capture): the table holds, per drawn node, its parent, preceding sibling, children, live partner and delta."""
    from . import fixtures
    from .html import to_html
    from .measure import measure
    res = fixtures._render(ctx, fx)
    top = res["tree"]
    pairs, root = fixtures.pair(top, fx["dump"])
    W, H = root[2], root[3]
    html, nodes = to_html(top, W, H, res["layout"])
    rects = measure(html, ctx.ws.cache / "fixtures-edge")
    parent, prev = _tree_maps(top)
    idx = {id(n): i for i, n in enumerate(nodes)}
    kids = {}
    for n in nodes:
        p = parent.get(id(n))
        if p is not None:
            kids.setdefault(id(p), []).append(idx.get(id(n)))
    tab, info = [], []
    for i, n in enumerate(nodes):
        ex = None
        if id(n) in pairs:
            e = pairs[id(n)][1]["bounds"]
            ex = [e[0] - root[0], e[1] - root[1], e[2], e[3]]
        tab.append({"i": i, "type": n["type"], "name": n.get("name") or "", "parent": idx.get(id(parent[id(n)])) if parent.get(id(n)) is not None else None,
                    "prev": idx.get(id(prev[id(n)])) if prev.get(id(n)) is not None else None, "kids": [k for k in kids.get(id(n), []) if k is not None],
                    "live": pairs[id(n)][0] if id(n) in pairs else None, "d": [round(rects[i][k] - ex[k], 1) for k in range(4)] if ex else None,
                    "expected": [round(v, 1) for v in ex] if ex else None, "got": [round(v, 1) for v in rects[i]], "hidden": "switch-branch-not-shown" in (n.get("layout_rules") or ())})
        info.append(n)
    return tab, info, pairs, (W, H), parent


def _tile_offset(tab, exclude):
    """Median delta per component over the rows that were not failing at all: the constant offset every passing row of a fixture carries."""
    out = []
    for k in range(4):
        v = sorted(t["d"][k] for t in tab if t["d"] and t["i"] not in exclude)
        out.append(v[len(v) // 2] if v else 0)
    return out


def examine_fixture(ctx, fx, rows, casc, ui_dir, runtime_fallback=None):
    """The examination of every FAIL row of one fixture. Returns {row id: exam}."""
    from . import fixtures
    fails = [r for r in rows if r["verdict"] == "FAIL"]
    if not fails:
        return {}
    cap = capture_for(fx, ui_dir)
    runtime = runtime_sheet_values(cap)
    cross = False
    if not runtime and runtime_fallback:                       # a fixture with no capture of its own (the state fixture): the run-time sheet values of the squad capture, same build, flagged
        runtime, cross = runtime_fallback, True
    layout_fixture = fx["fixture"].get("kind") == "layout" and fx["dump"] is not None
    tab = info = pairs = None
    if layout_fixture:
        tab, info, pairs, (W, H), parent = fixture_tables(ctx, fx)
    name = fx["fixture"]["name"]
    recs = {}
    for r in fails:
        rec = {"id": row_id(name, r), "row": r, "property": r["property"], "expected": r["expected"], "got": r["got"], "delta": r["delta"], "live": None, "render": None, "pair": None}
        node = None
        if tab is not None:
            if r["property"] == "box" and r.get("node") is not None:
                node = r["node"]
            elif r.get("live"):
                node = next((t["i"] for t in tab if t["live"] == r["live"]), None)
        if node is not None:
            n = info[node]
            rec["node"] = node
            rec["render"] = {"type": n["type"], "name": n.get("name") or "", "classes": n.get("classes"), "all_classes": list(n.get("_classes") or []), "has_children": bool(n.get("children")),
                             "text": n.get("text"), "layout": n.get("layout")}
            t = tab[node]
            if r["property"] == "box":
                rec["d"], rec["expected_box"], rec["got_box"] = t["d"], t["expected"], t["got"]
            pp = parent.get(id(n))
            live_path = t["live"]
            if live_path:
                liveN = fx["dump"]["nodes"][live_path]
                par_live = tab[t["parent"]]["live"] if t["parent"] is not None else None
                rec["pair"] = {"live": live_path, "live_label": liveN["label"], "live_visible": liveN["visible"], "live_text": liveN["text"], "live_depth": liveN["depth"],
                               "same_name": liveN["name"] == (n.get("name") or ""), "same_type": liveN["type"] == n["type"],
                               "parent_chain_ok": True if par_live is None else live_path.startswith(par_live + "/"),
                               "parent_depth_gap": (liveN["depth"] - fx["dump"]["nodes"][par_live]["depth"]) if par_live and par_live in fx["dump"]["nodes"] else None}
                if cap is not None and live_path in cap.elements:
                    e = cap.elements[live_path]
                    res_live = e.get("resolved") or {}
                    rec["live"] = {"classes": e.get("classes"), "inline": e.get("inline"), "pseudo": e.get("pseudo"), "visible": e.get("visible"), "text": e.get("text"), "source": e.get("source"),
                                   "children_in_capture": cap.children_count(live_path), "font_size": res_live.get("fontSize"), "display": res_live.get("display")}
                    if par_live and live_path.startswith(par_live + "/") and par_live in cap.elements:
                        wr = [q for q in cap.order if q.startswith(par_live + "/") and live_path.startswith(q + "/")]
                        rec["pair"]["wrappers"] = [{"name": cap.elements[q]["name"], "classes": cap.elements[q]["classes"][:3]} for q in wr] or None
        elif name.startswith("state-") or r["property"].startswith("background-color"):
            rec["state_fixture"] = True
        recs[rec["id"]] = rec
    # components and inheritance (box rows)
    failing, tols, comps_of = {}, {}, {}
    for rid, rec in recs.items():
        if rec["property"] == "box" and rec.get("d") and rec.get("node") is not None:
            W_, H_ = (W, H)
            exp = rec["expected_box"]
            tl = [fixtures.tol(exp[2], W_), fixtures.tol(exp[3], H_), fixtures.tol(exp[2], W_), fixtures.tol(exp[3], H_)]
            fk = [k for k in range(4) if abs(rec["d"][k]) > tl[k]]
            failing[rec["node"]] = fk
            tols[rec["node"]] = tl
            comps_of[rid] = fk
            rec["tol"] = [round(x, 2) for x in tl]
            rec["tile_offset"] = _tile_offset(tab, set(failing) | {rec["node"]})
    node_rec = {rec["node"]: rec for rec in recs.values() if rec.get("node") is not None and rec["property"] == "box"}

    def fits(key):
        rec_ = node_rec.get(key[0])
        return bool(rec_) and bool(mechanisms(rec_, COMP[key[1]], casc, runtime))
    status = propagate(tab, failing, fits) if failing else {}
    node_rid = {rec["node"]: rid for rid, rec in recs.items() if rec.get("node") is not None and rec["property"] == "box"}
    origin_keys = {key for key, st in status.items() if st["status"] == "origin" or st["cycle"]}      # a loop's chosen member is an origin too
    out = {}
    for rid, rec in recs.items():
        ex = {"id": rid, "pair_checks": None, "components": [], "status": None, "origin_ids": [], "cause_key": None, "cause": None, "grade": None, "evidence": None, "also_fits": []}
        if rec.get("pair"):
            p = rec["pair"]
            ex["pair_checks"] = {k: p.get(k) for k in ("same_type", "same_name", "parent_chain_ok", "parent_depth_gap", "live_visible", "live_depth")}
            ex["pair_checks"]["text_equal"] = None if not (rec["render"] and rec["render"].get("text") is not None and p.get("live_text")) else (rec["render"]["text"].strip() == p["live_text"].strip())
        origin_comps = []
        if rec["property"] == "box" and rid in comps_of:
            for k in comps_of[rid]:
                st = status[(rec["node"], k)]
                origin_rows = sorted({node_rid[o[0]] for o in st["origins"] if o[0] in node_rid})
                ex["components"].append({"c": COMP[k], "delta": rec["d"][k], "tol": round(tols[rec["node"]][k], 1), "status": st["status"], "origin_rows": origin_rows, "cycle": st["cycle"],
                                         "kinds": [m["kind"] for m in st["matches"]], "partial": st["partial"]})
                if (rec["node"], k) in origin_keys:
                    origin_comps.append(COMP[k])
            inherited_from = sorted({o for c in ex["components"] if c["status"] == "inherited" for o in c["origin_rows"] if o != rid})
            ex["status"] = ("origin" if origin_comps else "inherited") if ex["components"] else "origin"
            ex["origin_ids"] = [rid] if origin_comps else inherited_from
            ex["displaced_by"] = inherited_from
        else:
            ex["status"] = "origin"
            ex["origin_ids"] = [rid]
            origin_comps = [None]
        # step 4-5 for the origin components
        best = None
        for comp in origin_comps:
            ms = mechanisms(rec, comp, casc, runtime)
            if cross:
                ms = [(k, g, dict(e, cross_capture=True)) for k, g, e in ms]
            size = abs(rec["d"]["xywh".index(comp)]) if (comp and rec.get("d")) else 0
            ex.setdefault("origin_components", []).append({"c": comp, "mechanisms": [{"key": k, "grade": g, "evidence": e} for k, g, e in ms]})
            if best is None or (ms and not best[1]) or (bool(ms) == bool(best[1]) and size > best[2]):
                best = (comp, ms, size)
        if best and best[1]:
            key, grade, evidence = best[1][0]
            ex.update({"cause_key": key, "cause": RULES[key][0], "grade": grade, "evidence": evidence, "also_fits": [k for k, _g, _e in best[1][1:]]})
        elif best:
            ex.update({"cause_key": None, "cause": UNEXPLAINED, "grade": None, "evidence": None})
        ex["_rec"] = rec
        out[rid] = ex
    # inherited rows take the cause of the origin row(s) they trace to
    for rid, ex in out.items():
        if ex["status"] == "inherited":
            srcs = [out[o] for o in ex["origin_ids"] if o in out]
            ex["inherited_cause_keys"] = sorted({s["cause_key"] or UNEXPLAINED for s in srcs})
            first = srcs[0] if srcs else None
            if first:
                ex.update({"cause_key": first["cause_key"], "cause": first["cause"] if first["cause_key"] else UNEXPLAINED, "grade": first["grade"], "evidence": "displaced by " + ", ".join(ex["origin_ids"])})
            else:
                ex.update({"cause_key": None, "cause": UNEXPLAINED, "grade": None})
    for ex in out.values():
        ex.pop("_rec", None)
    return out


def examine_all(ctx, results, ui_dir=None):
    """Attach the examination to every FAIL row of `results` (the output of fixtures.run_all): row["id"], row["exam"], row["cause"], row["cause_grade"], row["legacy_cause"]. Returns the list of exams."""
    from . import fixtures
    ui_dir = Path(ui_dir) if ui_dir else Path(ctx.ws.root) / "notes" / "ui-dumps"
    if not ui_dir.is_dir():
        ui_dir = Path(r"C:\Users\Admin\FMSKINNING\workspace\notes\ui-dumps")
    casc = ctx.R.cascade()
    base = next((p for p in sorted(ui_dir.glob("styles-e1-squad-bindings-*.ndjson"))), None)
    fallback = runtime_sheet_values(__import__("skin_editor.render.captures", fromlist=["x"]).read_capture(base)) if base else None
    exams = []
    for r in results:
        fx = fixtures.load(fixtures.FIXTURES / r["name"])
        for row in r["rows"]:
            row["id"] = row_id(r["name"], row)
        out = examine_fixture(ctx, fx, r["rows"], casc, ui_dir, fallback)
        for row in r["rows"]:
            if row["verdict"] == "FAIL":
                ex = out.get(row["id"])
                row["exam"] = ex
                row["cause"] = ex["cause"] if ex and ex["cause"] else UNEXPLAINED
                row["cause_grade"] = ex["grade"] if ex and ex["grade"] else None
                row["cause_key"] = ex["cause_key"] if ex else None
                row["legacy_cause"] = fixtures.legacy_cause(row, r["name"])
                exams.append(ex)
    return exams