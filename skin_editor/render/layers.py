"""Optional render LAYERS (v1.1.0): both OFF by default, both flagged as inferred, neither ever changes a base row.

`live-classes` (U1). The game sets classes in code on some elements (a sprite class on an icon setter, for instance) that the layout does not hold. The base render already applies the PER-TYPE classes
learned from many inspector dumps (data/render/runtime-classes.json: 51 types, classes seen on at least 97 percent of at least 15 instances; they are the "runtime classes (learned)" the explain
panel lists), and none of them is a sprite class. This layer is the INSTANCE one: for the elements of a fixture's capture it adds the classes the live element carries and the layout lacks. It
is an inference: the capture is one moment of one save, and the match between a render node and a live element is the fixtures' pairing.

`recorded-runtime-sheet` (U2). The capture's run-time sheet (empty name, negative instance id) sampled 80 of its 190 rules; this layer appends those sampled rules as one extra sheet. A rule absent
from the sample proves nothing, a rule present is the game's own. It is a CAPTURED SAMPLE, labelled so everywhere.

The results are published as LAYER ROWS beside the base rows (and in their own totals), never added to the base totals and never presented as an improvement of them."""
from pathlib import Path

LIVE_CLASSES = "live-classes"
RUNTIME_SHEET = "recorded-runtime-sheet"
LABELS = {LIVE_CLASSES: "live-class layer (instance classes taken from a capture; inferred)",
          RUNTIME_SHEET: "recorded run-time sheet layer (an 80-rule captured sample of the run-time sheet; inferred)"}


def stamp_positions(top):
    """Give every node of the layout tree its position "i/j/k" BEFORE the cascade runs (the cascade drops non-visual nodes, so positions counted afterwards would not match). The key the class layer uses."""

    def walk(n, p):
        n["_pos"] = p
        for j, c in enumerate(n.get("children", [])):
            walk(c, "%s/%d" % (p, j))
    for i, t in enumerate(top):
        walk(t, str(i))


def paths_of(top):
    """{id(node): position} of every node of a RENDERED tree, read from the stamps."""
    out, stack = {}, list(top)
    while stack:
        n = stack.pop()
        out[id(n)] = n["_pos"]
        stack.extend(n.get("children", []))
    return out


def apply_class_layer(top, mapping):
    """Add the classes in `mapping` ({"i/j": [class, ...]}) to the layout nodes before the cascade runs. Returns the number of nodes changed."""
    by_path, n = {}, 0
    stack = list(top)
    while stack:
        node = stack.pop()
        by_path[node["_pos"]] = node
        stack.extend(node.get("children", []))
    for p, extra in mapping.items():
        node = by_path.get(p)
        if node is not None:
            add = [c for c in extra if c not in (node.get("classes") or [])]
            if add:
                node["classes"] = list(node.get("classes") or []) + add
                n += 1
    return n


def sheet_rules_from_capture(cap):
    """The rules the capture sampled from its run-time sheet(s), in the form the sheet compiler takes."""
    rules = []
    for sc in cap.sheet_contents:
        if sc.get("name") == "" and (sc.get("instance") or 0) < 0:
            for s in sc.get("sample", []):
                props = [[p.split(":", 1)[0].strip(), p.split(":", 1)[1].strip(), []] for p in s.get("p", []) if ":" in p]
                rules.append({"i": len(rules), "s": [s["s"]], "p": props, "t": False})
    return rules


def run_layers(ctx, results, ui_dir=None):
    """Run each layer over EVERY paired row of every layout fixture (passing rows included), not only the rows it is about, and publish what it fixes (FAIL -> PASS), what it BREAKS (PASS -> FAIL)
    and, as the layer's table, the failing rows it is about (cause runtime-class for the class layer, runtime-sheet-colour for the sheet layer). Layer rows from the state fixture (the recorded
    sheet on the real chains) are collected from each result's `layer_rows`. Nothing here touches the base rows or the base totals."""
    from . import causes, fixtures
    ui_dir = Path(ui_dir) if ui_dir else fixtures.ui_dumps_dir(ctx)
    out = {k: {"label": LABELS[k], "rows": [], "base_rows": 0, "now_pass": 0, "applied_nodes": 0, "default": "off", "status": "inferred", "rows_compared": 0, "fixed": 0, "broken": [], "unchanged": 0,
               "state_rows": [], "state_counts": {"PASS": 0, "FAIL": 0, "N/A": 0}} for k in (LIVE_CLASSES, RUNTIME_SHEET)}
    wanted = {LIVE_CLASSES: "runtime-class", RUNTIME_SHEET: "runtime-sheet-colour"}
    for r in results:
        base_by_id = {x["id"]: x for x in r["rows"] if x.get("kind") in ("boxes", "values")}
        fx0 = fixtures.load(fixtures.FIXTURES / r["name"])
        if not base_by_id or fx0["fixture"].get("kind") != "layout" or not fx0["dump"]:
            continue
        cap = causes.capture_for(fx0, ui_dir)
        if cap is None:
            continue
        for layer, cause_key in wanted.items():
            ids = {i for i, x in base_by_id.items() if x["verdict"] == "FAIL" and x.get("cause_key") == cause_key}
            fx = fixtures.load(fixtures.FIXTURES / r["name"])
            if layer == LIVE_CLASSES:
                base = fixtures._render(ctx, fx)
                pairs, _root = fixtures.pair(base["tree"], fx["dump"])
                pos = paths_of(base["tree"])
                mapping = {pos[nid]: list(cap.elements[lp]["classes"]) for nid, (lp, _n) in pairs.items() if lp in cap.elements and cap.elements[lp].get("classes")}
                layers = {"class_layer": mapping}
            else:
                layers = {"runtime_sheet": sheet_rules_from_capture(cap)}
            res2 = fixtures._render(ctx, fx, layers=layers)
            if layer == LIVE_CLASSES:
                out[layer]["applied_nodes"] += (res2.get("layers") or {}).get("class_layer", {}).get("nodes", 0)
            rows2 = []
            for check in fx["expect"]["checks"]:
                if check["kind"] in ("boxes", "values"):
                    rows2 += fixtures.RUNNERS[check["kind"]](ctx, fx, check, res2)
            for x in rows2:
                x.setdefault("kind", "boxes" if x["property"] in ("box", "visibility") else "values")
                rid = causes.row_id(r["name"], x)
                b = base_by_id.get(rid)
                if b is None:
                    continue
                out[layer]["rows_compared"] += 1
                rec = {"fixture": r["name"], "base_id": rid, "element": x["element"], "property": x["property"], "base_verdict": b["verdict"], "layer_verdict": x["verdict"], "expected": x["expected"],
                       "base_got": b["got"], "layer_got": x["got"], "layer_delta": x["delta"], "layer": layer, "status": "inferred"}
                if rid in ids:
                    out[layer]["rows"].append(rec)
                if b["verdict"] == "FAIL" and x["verdict"] == "PASS":
                    out[layer]["fixed"] += 1
                elif b["verdict"] == "PASS" and x["verdict"] == "FAIL":
                    out[layer]["broken"].append(rec)
                else:
                    out[layer]["unchanged"] += 1
    for r in results:                                                       # the state fixture's layer rows (the recorded sheet on the real chains): their own counts
        for x in r.get("layer_rows", []):
            if "run-time sheet" in (x.get("layer") or ""):
                out[RUNTIME_SHEET]["state_rows"].append({"fixture": r["name"], "check": x["check"], "property": x["property"], "verdict": x["verdict"], "expected": x["expected"], "got": x["got"], "layer": x["layer"]})
                out[RUNTIME_SHEET]["state_counts"][x["verdict"]] += 1
    for k, v in out.items():
        v["base_rows"] = len(v["rows"])
        v["now_pass"] = sum(1 for x in v["rows"] if x["layer_verdict"] == "PASS")
    return out


def layers_md(lay):
    out = ["## Optional layers (off by default, inferred; layer rows stand alone: they are not in the totals above and not in the examination)", ""]
    for k in (LIVE_CLASSES, RUNTIME_SHEET):
        v = lay[k]
        out += ["### " + v["label"], ""]
        if k == LIVE_CLASSES:
            out += ["**Circularity, stated plainly:** the layer reads each element's classes from the SAME capture the row is scored against. That the failing rows it is about pass when it is applied confirms the diagnosis (those classes set in code explain those boxes); it does not show that the layer could PREDICT them for a screen no capture was taken of. "
                    "The base render already applies the per-type classes learned from many dumps (`data/render/runtime-classes.json`); that file holds no sprite class and is not this layer.", ""]
        else:
            out += ["The rules come from the 80 rules the squad capture sampled from its run-time sheet (of 190): a CAPTURED SAMPLE; a rule absent from it proves nothing.", ""]
        out += ["Run over every paired row of the layout fixtures, passing rows included: %d rows compared; %d FAIL -> PASS; **%d PASS -> FAIL (rows the layer breaks)**; %d unchanged. Of the %d failing base rows the layer is about, %d pass with it, %d still fail." % (
            v["rows_compared"], v["fixed"], len(v["broken"]), v["unchanged"], v["base_rows"], v["now_pass"], v["base_rows"] - v["now_pass"]), ""]
        if v["broken"]:
            out += ["Rows the layer breaks:", "", "| Fixture | Element | Property | Base | With the layer | Expected | Got with the layer |", "|---|---|---|---|---|---|---|"]
            out += ["| %s | %s | %s | %s | %s | %s | %s |" % (x["fixture"], x["element"], x["property"], x["base_verdict"], x["layer_verdict"], x["expected"], x["layer_got"]) for x in v["broken"]] + [""]
        else:
            out += ["The layer breaks no row.", ""]
        out += ["| Fixture | Element | Property | Base | With the layer | Expected | Got with the layer |", "|---|---|---|---|---|---|---|"]
        for x in v["rows"]:
            out.append("| %s | %s | %s | %s | %s | %s | %s |" % (x["fixture"], x["element"], x["property"], x["base_verdict"], x["layer_verdict"], x["expected"], x["layer_got"]))
        out.append("")
        if v["state_rows"]:
            c = v["state_counts"]
            out += ["State rows with this layer on the real ancestry chains (layer rows, their own counts: %d pass, %d fail, %d N/A):" % (c["PASS"], c["FAIL"], c["N/A"]), "", "| Check | Property | Verdict | Expected | Got |", "|---|---|---|---|---|"]
            out += ["| %s | %s | %s | %s | %s |" % (x["check"], x["property"], x["verdict"], x["expected"], x["got"]) for x in v["state_rows"]] + [""]
    return out
