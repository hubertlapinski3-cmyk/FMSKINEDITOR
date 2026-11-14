"""M7: the calibration fixture framework (docs/PHASE9-PLAN.md section 8). A fixture is DATA, a folder `tests/fixtures/render/<name>/`:

  fixture.json   what is rendered and how: {name, kind, layout | screen | table, project?, skin, branches?, delivered?, source, build, date}
  dump.json      optional: the live elements of the game (boxes, resolved values, text, structural path), cut from a capture or an inspector dump
  project.json   optional: a project model the render applies (the skin side of a fixture)
  expect.json    the checks: {checks: [{id, kind, ...}]}

Kinds: `boxes` (element boxes against the dump), `values` (resolved colours, font sizes and flex values against the dump, EXACT), `rule` (which rule wins a declaration and whether it
is the project's), `table` (the placeholder table's header row), `tiles` (left/right relations and x positions of cells after a tile move), `screen` (the assembler's host boxes against
the dump), `state` (I3: a hover/press/focus reading against the game's own `:pseudo` rules, with explicit no-op verdicts), `classswap` (a run-time class swap against the declared difference).
Every row is PASS, FAIL or N/A (the render makes no declaration to compare, said as such); nothing is filtered, averaged or re-toleranced.
Tolerance (owner): a box passes when each of x, y, width, height is within 8 px or 5 percent of the measured size, whichever is tighter; colours and font sizes must be exactly equal.
`run_all` returns every fixture's rows; `report` writes the published JSON and Markdown; `add_from_capture` builds a fixture from a capture host subtree and fills expect.json."""
import copy
import json
import re
from pathlib import Path

from .. import project as project_mod

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "tests" / "fixtures" / "render"
RESOLVED = {"color": "color", "backgroundColor": "background-color", "fontSize": "font-size", "flexGrow": "flex-grow", "flexShrink": "flex-shrink", "flexDirection": "flex-direction"}
DEFAULTS = {"flex-grow": "0", "flex-shrink": "1", "flex-direction": "column"}               # Yoga's initial values, the render's own defaults (render/html.py)
LABEL = re.compile(r"^([A-Za-z0-9_`]+)(?:#([^.]*))?")


def tol(expected, ref):
    return min(8.0, 0.05 * (expected if expected > 0 else ref))


def _col(v):
    v = str(v).upper().lstrip("#")
    return v + "FF" if len(v) == 6 else v


def _num(v):
    return "%g" % float(str(v).replace("px", ""))


def same(prop, live, got):
    if prop.endswith("color"):
        return _col(live) == _col(got)
    if prop in ("font-size", "flex-grow", "flex-shrink"):
        return _num(live) == _num(got)
    return str(live).lower().replace(" ", "") == str(got).lower().replace(" ", "")


# ---------------------------------------------------------------- loading
def load(folder):
    f = Path(folder)
    d = {"dir": f, "fixture": json.loads((f / "fixture.json").read_text(encoding="utf-8")), "expect": json.loads((f / "expect.json").read_text(encoding="utf-8"))}
    d["dump"] = json.loads((f / "dump.json").read_text(encoding="utf-8")) if (f / "dump.json").is_file() else None
    d["project"] = project_mod.validate(project_mod.migrate(json.loads((f / "project.json").read_text(encoding="utf-8")))) if (f / "project.json").is_file() else None
    return d


def discover(root=None):
    return sorted(p.parent for p in Path(root or FIXTURES).glob("*/fixture.json"))


class Context:
    """The renderer and the game data the fixtures need, built once."""

    def __init__(self, aa=None, ws=None):
        from .. import config, index_styles
        from .service import Renderer
        self.ws = ws or config.workspace(config.load())
        self.aa = Path(aa or config.load()["aa_dir"])
        self.R = Renderer(self.aa, self.ws.cache, index_styles.load(self.ws))
        self.catalog = {}
        for r in self.R.layouts.catalog():
            self.catalog.setdefault(r["name"], r)
        self._dump = self._tables = None

    def layout_dump(self):
        from .. import layout_dump
        if self._dump is None:
            self._dump = layout_dump.load(self.ws)
        return self._dump

    def tables(self):
        from .. import tables
        if self._tables is None:
            self._tables = tables.Tables(self.aa).load()
        return self._tables


# ---------------------------------------------------------------- dump from a capture
def dump_from_capture(cap, host_name, host_type=None):
    """The live elements under one host element of a capture, in capture order, as a small dump: label, bounds, text, structural path and the resolved values the fixtures compare."""
    host = next(e for e in cap.elements.values() if e["name"] == host_name and (host_type is None or e["type"] == host_type))
    nodes = {}
    for p in cap.order:
        e = cap.elements[p]
        if p == host["path"] or p.startswith(host["path"] + "/"):
            lab = e["type"] + ("#" + e["name"] if e["name"] else "") + "".join("." + k for k in e["classes"])
            r = e.get("resolved") or {}
            nodes[p] = {"label": lab, "type": e["type"], "name": e["name"], "visible": e["visible"], "depth": e["depth"], "bounds": e["world"], "text": e.get("text", ""),
                        "binder": (e.get("binding") or {}).get("binder"), "resolved": {k: r[k] for k in RESOLVED if k in r}}
    return {"root": host["path"], "host": host_name, "plugin": cap.header.get("plugin"), "game": cap.header.get("game"), "nodes": nodes}


# ---------------------------------------------------------------- pairing render nodes with live elements
def _flat(top):
    from .html import flatten
    return flatten(top)


def _hidden_ids(top):
    hidden = set()

    def mark(n, h):
        h = h or "switch-branch-not-shown" in (n.get("layout_rules") or ())
        if h:
            hidden.add(id(n))
        for c in n.get("children", []):
            mark(c, h)
    for t in top:
        mark(t, False)
    return hidden


def pair(top, dump):
    """{id(node): live element} by greedy in-order matching of (type, name), the live side starting at the element that is the render's top node."""
    live = [(p, n) for p, n in dump["nodes"].items() if n["visible"] or True]
    first = top[0]
    start = next((i for i, (_p, n) in enumerate(live) if n["type"] == first["type"] and n["name"] == (first.get("name") or "")), 0)
    hidden, pos, out = _hidden_ids(top), start, {}
    for n in _flat(top):
        if id(n) in hidden:
            continue
        j = next((k for k in range(pos, len(live)) if live[k][1]["type"] == n["type"] and live[k][1]["name"] == (n.get("name") or "")), None)
        if j is not None:
            out[id(n)] = live[j]
            pos = j + 1
    return out, live[start][1]["bounds"]


def delivered_of(dump):
    return [{"binder": n["binder"], "text": n["text"], "width": n["bounds"][2], "path": p} for p, n in dump["nodes"].items()
            if n["type"] == "SIText" and n["visible"] and n["text"] and n.get("binder")]


# ---------------------------------------------------------------- the checks
def _render(ctx, fx, skin=None):
    from . import captures
    f = fx["fixture"]
    spec = f["layout"]
    row = ctx.catalog[spec["name"]]
    skin = f.get("skin", True) if skin is None else skin
    project = fx["project"] if (fx["project"] and skin) else None
    chosen = {int(k): v for k, v in (f.get("branches") or {}).items()}
    if f.get("infer_branches") and fx["dump"]:
        elems = [{"type": n["type"], "name": n["name"], "visible": n["visible"]} for n in fx["dump"]["nodes"].values()]
        chosen = dict(captures.infer_branches(ctx.R.layout(row["bundle"], row["path_id"])["tree"], elems)["branches"], **chosen)
    delivered = delivered_of(fx["dump"]) if (f.get("delivered") and fx["dump"]) else None
    return ctx.R.layout(row["bundle"], row["path_id"], branches=chosen, project=project, delivered=delivered)


def _row(fixture, check, element, prop, expected, got, verdict, delta=None, note=""):
    return {"fixture": fixture, "check": check, "element": element, "property": prop, "expected": expected, "got": got, "delta": delta, "verdict": verdict, "note": note}


def run_boxes(ctx, fx, check, res):
    from .html import to_html
    from .measure import measure
    top = res["tree"]
    pairs, root = pair(top, fx["dump"])
    W, H = root[2], root[3]
    html, nodes = to_html(top, W, H, res["layout"])
    rects = measure(html, ctx.ws.cache / "fixtures-edge")
    rows, name = [], fx["fixture"]["name"]
    for i, n in enumerate(nodes):
        label = "%s#%s" % (n["type"], n.get("name") or "")
        if id(n) not in pairs:
            if "switch-branch-not-shown" in (n.get("layout_rules") or ()):
                continue
            rows.append(_row(name, check["id"], label, "box", None, [round(v, 1) for v in rects[i]], "N/A", note="no live element paired (not on screen, or not reached by the capture)"))
            continue
        e = pairs[id(n)][1]["bounds"]
        ex = [e[0] - root[0], e[1] - root[1], e[2], e[3]]
        g = rects[i]
        d = [g[0] - ex[0], g[1] - ex[1], g[2] - ex[2], g[3] - ex[3]]
        ok = abs(d[0]) <= tol(ex[2], W) and abs(d[1]) <= tol(ex[3], H) and abs(d[2]) <= tol(ex[2], W) and abs(d[3]) <= tol(ex[3], H)
        rows.append(_row(name, check["id"], label, "box", [round(v, 1) for v in ex], [round(v, 1) for v in g], "PASS" if ok else "FAIL", [round(v, 1) for v in d]))
    return rows


def run_values(ctx, fx, check, res):
    pairs, _root = pair(res["tree"], fx["dump"])
    rows, name = [], fx["fixture"]["name"]
    for n in _flat(res["tree"]):
        if id(n) not in pairs:
            continue
        live = pairs[id(n)][1]
        for lk, rk in RESOLVED.items():
            if lk not in live["resolved"]:
                continue
            d = n["computed"].get(rk)
            got = d["value"] if d else DEFAULTS.get(rk)
            label = "%s#%s" % (n["type"], n.get("name") or "")
            if got is None:
                rows.append(_row(name, check["id"], label, rk, live["resolved"][lk], None, "N/A", note="the render declares no %s here" % rk))
            else:
                rows.append(_row(name, check["id"], label, rk, live["resolved"][lk], got, "PASS" if same(rk, live["resolved"][lk], got) else "FAIL"))
    return rows


def _find(top, ty, nm):
    stack = list(top)
    while stack:
        n = stack.pop(0)
        if n["type"] == ty and (n.get("name") or "") == nm:
            return n
        stack = list(n.get("children", [])) + stack
    return None


def _synthetic(ctx, fx, check):
    """A node built from the check (type, name, classes) and run through the cascade of this fixture's project: for an element no layout holds (a class the game adds in code)."""
    s = check["node"]
    node = {"type": s["type"], "name": s.get("name", ""), "classes": list(s.get("classes", [])), "children": [], "inline": [], "attrs": {}, "id": None, "layout": None}
    project = fx["project"] if (fx["project"] and check.get("skin", True)) else None
    casc = ctx.R.skin_cascade(project)[0] if project else ctx.R.cascade()
    casc.compute([node])
    return {"tree": [node]}


def run_rule(ctx, fx, check, res):
    if "node" in check:
        res = _synthetic(ctx, fx, check)
        check = dict(check, element={"type": check["node"]["type"], "name": check["node"].get("name", "")})
    elif check.get("skin") is not None and check["skin"] != fx["fixture"].get("skin", True):
        res = _render(ctx, fx, check["skin"])
    n = _find(res["tree"], check["element"]["type"], check["element"].get("name", ""))
    name = fx["fixture"]["name"]
    label = "%s#%s" % (check["element"]["type"], check["element"].get("name", ""))
    if n is None:
        return [_row(name, check["id"], label, check["property"], check.get("expect"), None, "FAIL", note="element not in the render")]
    d = n["computed"].get(check["property"])
    if check.get("expect_absent"):                          # the element must carry NO declaration of this property (the patch adds one; the game's own styles do not)
        return [_row(name, check["id"], label, check["property"], "no declaration", None if d is None else d["value"], "PASS" if d is None else "FAIL")]
    if d is None:
        return [_row(name, check["id"], label, check["property"], check["expect"], None, "FAIL", note="no such declaration")]
    exp = check["expect"]
    got = {"value": d["value"], "origin": "project" if (d["source"] or {}).get("origin") else "vanilla", "selector": (d["source"] or {}).get("selector")}
    ok = all(got.get(k) == v for k, v in exp.items() if k in got) and all(k in got for k in exp)
    if "above_vanilla" in check:                            # the project's rule sits in the cascade order ABOVE the vanilla rule named here
        order = [("project" if m.get("origin") else "vanilla", m["selector"]) for m in n["matched"]]
        mine = [i for i, (o, s) in enumerate(order) if o == "project" and s == exp.get("selector")]
        van = [i for i, (o, s) in enumerate(order) if o == "vanilla" and s == check["above_vanilla"]]
        ok = ok and bool(mine) and bool(van) and min(mine) > max(van)
        got["order"] = order
    return [_row(name, check["id"], label, check["property"], exp, got, "PASS" if ok else "FAIL")]


def run_table(ctx, fx, check, res=None):
    from . import overlay
    f = fx["fixture"]
    T = ctx.tables()
    view = next(v for v in T._views.values() if v["name"] == f["table"]["name"])
    project = fx["project"] if check.get("skin", True) else None
    cols = [c["id"] for c in overlay.table_placeholder(T, view["path_id"], project, f["table"].get("breakpoint"))["columns"]]
    name, rows = f["name"], []
    want = check.get("header")
    if want is not None:
        ok = cols == want
        rows.append(_row(name, check["id"], f["table"]["name"], "header order" + (" (skin)" if check.get("skin", True) else " (vanilla)"), want, cols, "PASS" if ok else "FAIL"))
    for a in check.get("absent", []):
        rows.append(_row(name, check["id"], f["table"]["name"], "column " + a, "absent" if check.get("skin", True) else "present", "present" if a in cols else "absent",
                         "PASS" if ((a not in cols) == check.get("skin", True)) else "FAIL"))
    return rows


def run_screen(ctx, fx, check, res=None):
    from . import screen
    f = fx["fixture"]
    s = f["screen"]
    d = ctx.layout_dump()
    moves = s.get("moves", []) if check.get("skin", False) else []
    out = screen.Assembler(d).assemble(s["composition"], tuple(s["area"]), reserved_right=s.get("reserved_right", 0), padding=s.get("padding", 12), moves=moves,
                                       runtime_slots=s.get("runtime_slots", []))
    px = {h["element_id"]: h["px"] for h in out["hosts"]}
    px.update({h["element_id"]: h["px"] for h in out["runtime_slots"]})
    ox, oy = s["origin"]
    rows, name = [], f["name"]
    for el, box in check["boxes"].items():
        if el not in px:
            rows.append(_row(name, check["id"], el, "box", box, None, "FAIL", note="cell not assembled"))
            continue
        g = [ox + px[el]["left"], oy + px[el]["top"], px[el]["width"], px[el]["height"]]
        dl = [g[0] - box[0], g[1] - box[1], g[2] - box[2], g[3] - box[3]]
        ok = abs(dl[0]) <= tol(box[2], box[2]) and abs(dl[1]) <= tol(box[3], box[3]) and abs(dl[2]) <= tol(box[2], box[2]) and abs(dl[3]) <= tol(box[3], box[3])
        rows.append(_row(name, check["id"], el, "box", [round(v, 1) for v in box], [round(v, 1) for v in g], "PASS" if ok else "FAIL", [round(v, 1) for v in dl]))
    return rows


def run_tiles(ctx, fx, check, res=None):
    from . import screen
    f = fx["fixture"]
    s = f["screen"]
    moves = s.get("moves", []) if check.get("skin", True) else []
    out = screen.Assembler(ctx.layout_dump()).assemble(s["composition"], tuple(s["area"]), reserved_right=s.get("reserved_right", 0), padding=s.get("padding", 12), moves=moves)
    px = {h["element_id"]: h["px"]["left"] for h in out["hosts"]}
    name, rows = f["name"], []
    for rel in check["relations"]:
        a, b = rel["left"], rel["right"]
        ok = a in px and b in px and px[a] < px[b]
        rows.append(_row(name, check["id"], "%s left of %s" % (a, b), "x" + (" (skin)" if check.get("skin", True) else " (vanilla)"), rel.get("expect", True),
                         ok if (a in px and b in px) else None, "PASS" if ok == rel.get("expect", True) else "FAIL", note="px left: %s=%s %s=%s" % (a, px.get(a), b, px.get(b))))
    return rows


def _state_chain(ctx, check, key="chain"):
    """The synthetic ancestor chain of a state check, computed through the vanilla cascade: nodes {type, name, classes, states}, root first, the element under test last."""
    nodes = []
    for s in check[key]:
        nodes.append({"type": s["type"], "name": s.get("name", ""), "classes": list(s.get("classes", [])), "children": [], "inline": [], "attrs": {}, "id": None, "layout": None,
                      "_states": set(s.get("states", [])) | (set() if "disabled" in s.get("states", []) else {"enabled"})})     # Unity's :enabled holds unless the element is disabled (mask 32)
    for a, b in zip(nodes, nodes[1:]):
        a["children"] = [b]
    casc = ctx.R.cascade()
    casc.compute([nodes[0]])
    return casc, nodes


def run_state(ctx, fx, check, res=None):
    """I3 (docs/evidence/phase9-i3-session-G-20261114.md): a runtime state (hover, focus, press) read in the game against what the game's own `:pseudo` rules declare for the same
    element. `rest` and `state` are the values the inspector read; the render predicts the state value from the rules (`Cascade.state_declarations`) and, when no state rule
    declares the property, predicts no change from the rest value. A check with `noop` is the explicit verdict that a state changes nothing the render needs."""
    casc, path = _state_chain(ctx, check)
    node, name = path[-1], fx["fixture"]["name"]
    prop = check["property"]
    label = "%s#%s" % (node["type"], node.get("name") or "") + ("." + ".".join(node["classes"][:2]) if node["classes"] and not node.get("name") else "")
    decl = casc.state_declarations(path, (prop,)).get(prop)
    rest = node["computed"].get(prop)
    rows = []
    state_txt = "+".join(sorted(node["_states"])) or "rest"
    if "rest" in check:
        rows.append(_row(name, check["id"], label, prop + " (rest)", check["rest"], rest["value"] if rest else None, "PASS" if rest and same(prop, check["rest"], rest["value"]) else ("N/A" if not rest else "FAIL"),
                         note="" if rest else "the render declares no %s here" % prop))
    if decl:
        pred = decl["value"]
    elif rest:
        pred = rest["value"]
    else:
        pred = "unchanged (no declaration, no state rule)"          # the render declares nothing: its prediction is that the state changes nothing
    ok = same(prop, check["state"], pred) if (decl or rest) else ("rest" in check and same(prop, check["state"], check["rest"]))
    note = ("state rule %s" % decl["source"]["selector"]) if decl else "no state rule declares %s: the render predicts no change" % prop
    if check.get("noop"):
        note = "explicit no-op: " + note
    rows.append(_row(name, check["id"], label, "%s (%s)" % (prop, state_txt), check["state"], pred, "PASS" if ok else "FAIL", note=note + ((" | " + check["note"]) if check.get("note") else "")))
    return rows


def run_classswap(ctx, fx, check, res=None):
    """A class that the game swaps at run time (the Inbox selection): which declared properties differ between the two class sets, against the property values the session read, if it read any."""
    name = fx["fixture"]["name"]
    a, b = check["from"], check["to"]
    casc, pa = _state_chain(ctx, dict(check, chain=[dict(check["element"], classes=a)]))
    _c, pb = _state_chain(ctx, dict(check, chain=[dict(check["element"], classes=b)]))
    diff = {k: [(pa[-1]["computed"].get(k) or {}).get("value"), (pb[-1]["computed"].get(k) or {}).get("value")] for k in sorted(set(pa[-1]["computed"]) | set(pb[-1]["computed"]))
            if (pa[-1]["computed"].get(k) or {}).get("value") != (pb[-1]["computed"].get(k) or {}).get("value")}
    label = "%s#%s" % (check["element"]["type"], check["element"].get("name", ""))
    rows = [_row(name, check["id"], label, "class swap " + " -> ".join(x[-1] for x in (check["from"], check["to"])), check.get("observed"), diff or "no declared difference",
                 "N/A", note=check.get("note", "the session recorded the class swap but measured no property on the swapped element: nothing to compare"))]
    return rows


RUNNERS = {"boxes": run_boxes, "values": run_values, "rule": run_rule, "table": run_table, "screen": run_screen, "tiles": run_tiles, "state": run_state, "classswap": run_classswap}


def run(folder, ctx):
    fx = load(folder)
    rows, res = [], None
    for check in fx["expect"]["checks"]:
        if (check["kind"] in ("boxes", "values") or (check["kind"] == "rule" and "node" not in check)) and (res is None or check.get("rerender")):
            res = _render(ctx, fx)
        rows.extend(RUNNERS[check["kind"]](ctx, fx, check, res))
    delivered = (res or {}).get("delivered")
    return {"name": fx["fixture"]["name"], "source": fx["fixture"].get("source", ""), "build": fx["fixture"].get("build", ""), "rows": rows,
            "delivered": delivered, "counts": {v: sum(1 for r in rows if r["verdict"] == v) for v in ("PASS", "FAIL", "N/A")}}


def run_all(ctx, root=None, only=None):
    return [run(f, ctx) for f in discover(root) if not only or f.name in only]


CAUSES = [
    ("sub-pixel offset on a very small element: the owner's tolerance is 5 percent of the size, 0.05 px for a 1 px divider", lambda r, f: r["property"] == "box" and r["expected"] and min(r["expected"][2], r["expected"][3]) <= 2 and max(abs(d) for d in (r["delta"] or [0])) < 1.5),
    ("run-time club-colour sheet (an empty-named root sheet, not applied): the game paints this from the club's colours", lambda r, f: r["property"].startswith("background-color") and str(r["expected"]).upper().startswith("#17223F")),
    ("code-built or binding-driven colour (not in any style sheet)", lambda r, f: r["property"].split(" ")[0] in ("color", "background-color") and "(" not in r["property"]),
    ("code-built content: the Training tile's weekly schedule, calendar and training lists are built at run time (the capture holds 'This Week's Schedule', Mon to Sun, the counts), so everything below them is displaced in the render", lambda r, f: f == "tile-training" and r["property"] == "box"),
    ("code-built content: the tactics pitch and its players are drawn in code, so the render's boxes around it differ", lambda r, f: f == "tile-tactics" and r["property"] == "box"),
    ("component-drawn image (SIImage, SIStyleSetter): its size and shrink come from component fields, not from style sheets", lambda r, f: r["property"] == "flex-shrink" or (r["property"] == "box" and "SIStyleSetter" in r["element"]) or (r["property"] == "box" and "SIImage" in r["element"])),
    ("bound text, scroller or list width: the width depends on the delivered data and the game's font (stand-in font drawn)", lambda r, f: r["property"] == "box" and any(k in r["element"] for k in ("SIText", "AutoScroller", "SIVisible", "StreamedObjectList", "SIButton", "ComponentElement", "BindingRemapper", "BindableSwitchElement"))),
]


def cause(row, fixture):
    """A named cause for a FAIL row, from rules over the row (not verified row by row); None when no rule fits, so an unexplained failure stays visibly unexplained."""
    for text, test in CAUSES:
        try:
            if test(row, fixture):
                return text
        except (TypeError, ValueError, KeyError):
            continue
    return None


# ---------------------------------------------------------------- the published report
def report(results, out_dir, title="Render calibration report", preface=None):
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    tot = {v: sum(r["counts"][v] for r in results) for v in ("PASS", "FAIL", "N/A")}
    for r in results:                                                                  # every FAIL row carries its cause (or says it has none)
        for x in r["rows"]:
            if x["verdict"] == "FAIL":
                x["cause"] = cause(x, r["name"])
    (out_dir / "calibration-report.json").write_text(json.dumps({"schema": "fm-calibration/1", "totals": tot, "fixtures": results}, indent=1), encoding="utf-8")
    md = ["# %s" % title, ""] + (list(preface(results, tot)) + [""] if callable(preface) else list(preface or [])) + ["Tolerance: box x, y, width, height within 8 px or 5 percent of the measured size, whichever is tighter; colours, font sizes and flex values exactly equal. Every row is published: "
          "PASS, FAIL, or N/A (nothing to compare). Nothing is filtered, averaged or re-toleranced.", "",
          "**Totals: %d pass, %d fail, %d n/a.**" % (tot["PASS"], tot["FAIL"], tot["N/A"]), "", "| Fixture | Pass | Fail | N/A | Source |", "|---|---|---|---|---|"]
    for r in results:
        md.append("| %s | %d | %d | %d | %s |" % (r["name"], r["counts"]["PASS"], r["counts"]["FAIL"], r["counts"]["N/A"], r["source"]))
    for r in results:
        md += ["", "## %s" % r["name"], ""]
        if r.get("delivered"):
            md.append("Delivered text wired: %(paired)d of %(nodes)d text nodes paired by structural path, %(unpaired_texts)d captured texts unpaired." % r["delivered"])
            md.append("")
        md += ["| Verdict | Check | Element | Property | Expected | Got | Delta | Note / cause |", "|---|---|---|---|---|---|---|---|"]
        for x in r["rows"]:
            note = x["note"] or ((("cause (by rule): " + (cause(x, r["name"]) or "UNEXPLAINED")) if x["verdict"] == "FAIL" else ""))
            md.append("| %s | %s | %s | %s | %s | %s | %s | %s |" % (x["verdict"], x["check"], x["element"], x["property"], json.dumps(x["expected"]), json.dumps(x["got"]), json.dumps(x["delta"]) if x["delta"] else "", note))
    (out_dir / "calibration-report.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    return tot


def failures(results):
    return sorted("%s|%s|%s|%s" % (r["name"], x["check"], x["element"], x["property"]) for r in results for x in r["rows"] if x["verdict"] == "FAIL")


# ---------------------------------------------------------------- fixture add
def add_from_capture(name, capture_file, host, layout, screenshot=None, root=None, source="", delivered=True, infer_branches=True, project_file=None, skin=True):
    """Create tests/fixtures/render/<name>/ from a capture's host subtree and fill expect.json with a `boxes` and a `values` check over everything the dump holds."""
    from . import captures
    import shutil
    cap = captures.read_capture(capture_file)
    folder = Path(root or FIXTURES) / name
    if folder.exists():
        raise FileExistsError("fixture %s exists" % name)
    folder.mkdir(parents=True)
    dump = dump_from_capture(cap, host)
    (folder / "dump.json").write_text(json.dumps(dump), encoding="utf-8")
    fixture = {"name": name, "kind": "layout", "layout": {"name": layout}, "skin": skin, "delivered": bool(delivered and delivered_of(dump)), "infer_branches": infer_branches,
               "source": source or "capture %s, host %s" % (Path(capture_file).name, host), "build": cap.header.get("game"), "plugin": cap.header.get("plugin"),
               "date": (cap.header.get("started") or "")[:10]}
    (folder / "fixture.json").write_text(json.dumps(fixture, indent=1), encoding="utf-8")
    (folder / "expect.json").write_text(json.dumps({"checks": [{"id": "geometry", "kind": "boxes"}, {"id": "values", "kind": "values"}]}, indent=1), encoding="utf-8")
    if project_file:
        shutil.copy2(project_file, folder / "project.json")
    if screenshot:
        shutil.copy2(screenshot, folder / ("screenshot" + Path(screenshot).suffix))
    return folder
