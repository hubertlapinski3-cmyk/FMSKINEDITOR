"""The tables the published calibration report adds after the 1.0.0 review (fix round): coverage by row class, the row-by-row examination of the failures, and the grid scoping.

Every number is computed from the rows (nothing is typed), so the preface cannot drift from the JSON; the functions take `results` as returned by fixtures.run_all (after
causes.examine_all for the examination) and return plain data plus markdown lines."""
import json
from pathlib import Path

CLASSES = ["geometry", "colour", "font-size", "flex", "rule winner", "state", "screen hosts", "tile order", "table header"]
DUPLICATES = [{"group": "the Loans tile", "fixtures": ["tile-loans", "tile-loans-c2-dump"],
               "note": "one tile measured twice (the c2 inspector dump and the squad capture); both are kept and both are counted in every total; deduplicating would change the headline totals and needs the owner's decision"}]


def _fx():
    from . import fixtures
    return fixtures


def klass(row):
    kind, prop = row.get("kind"), row["property"].split(" ")[0]
    if kind == "boxes":
        return "geometry"
    if kind == "values":
        return "colour" if prop in ("color", "background-color") else "font-size" if prop == "font-size" else "flex"
    return {"rule": "rule winner", "state": "state", "classswap": "state", "screen": "screen hosts", "tiles": "tile order", "table": "table header"}.get(kind, "state")


def all_rows(results):
    return [dict(x, fixture=r["name"]) for r in results for x in r["rows"]]


def coverage(results):
    """Pass, fail, N/A per fixture and row class; passes split declared vs default and stage box vs other; N/A by reason; rows never emitted; live-side coverage."""
    rows = all_rows(results)
    by = {}
    for x in rows:
        c = by.setdefault(x["fixture"], {}).setdefault(klass(x), {"PASS": 0, "FAIL": 0, "N/A": 0})
        c[x["verdict"]] += 1
    cls = {k: {"PASS": 0, "FAIL": 0, "N/A": 0} for k in CLASSES}
    for f in by.values():
        for k, c in f.items():
            for v in c:
                cls[k][v] += c[v]
    declared = {"declared": 0, "default": 0}
    for x in rows:
        if x["verdict"] == "PASS" and x.get("kind") == "values":
            declared["default" if x.get("value_source") == "default" else "declared"] += 1
    flex = [x for x in rows if x.get("kind") == "values" and klass(x) == "flex"]
    flex_pass = [x for x in flex if x["verdict"] == "PASS"]
    geo = [x for x in rows if klass(x) == "geometry"]
    geo_pass = [x for x in geo if x["verdict"] == "PASS"]
    stage_pass = [x for x in geo_pass if x.get("stage")]
    na = {}
    for x in rows:
        if x["verdict"] == "N/A":
            na[x.get("na_reason") or "UNCODED"] = na.get(x.get("na_reason") or "UNCODED", 0) + 1
    skipped, eq = {}, []
    for r in results:
        cv = r.get("coverage") or {}
        for k, v in (cv.get("skipped") or {}).items():
            skipped[k] = skipped.get(k, 0) + v
        vrows = sum(1 for x in r["rows"] if x.get("kind") == "values")
        vskip = sum(v for k, v in (cv.get("skipped") or {}).items() if k.startswith("values"))
        brows = sum(1 for x in r["rows"] if x.get("kind") == "boxes")
        bskip = sum(v for k, v in (cv.get("skipped") or {}).items() if k.startswith("boxes"))
        if vrows or vskip:
            eq.append({"fixture": r["name"], "what": "values", "render_nodes_x_properties": cv.get("render_nodes", 0) * 6, "emitted": vrows, "skipped": vskip, "sums": cv.get("render_nodes", 0) * 6 == vrows + vskip})
        if brows or bskip:
            eq.append({"fixture": r["name"], "what": "boxes", "render_nodes": cv.get("box_nodes", 0), "emitted": brows, "skipped": bskip, "sums": cv.get("box_nodes", 0) == brows + bskip})
    live = [{"fixture": r["name"], "dump_nodes": (r.get("coverage") or {}).get("dump_nodes", 0), "paired": (r.get("coverage") or {}).get("dump_paired", 0), "unpaired": (r.get("coverage") or {}).get("dump_unpaired", 0),
             "delivered_texts_unpaired": (r.get("delivered") or {}).get("unpaired_texts", 0)} for r in results if (r.get("coverage") or {}).get("dump_nodes")]
    total = len(rows)
    compared = sum(1 for x in rows if x["verdict"] != "N/A")
    return {"total_rows": total, "compared": compared, "by_fixture": by, "by_class": cls, "passes_declared_vs_default": declared,
            "flex": {"rows": len(flex), "pass": len(flex_pass), "pass_at_default": sum(1 for x in flex_pass if x.get("value_source") == "default"),
                     "pass_value_equals_initial": sum(1 for x in flex_pass if _fx().same(x["property"], x["expected"], _fx().DEFAULTS[x["property"]]))},
            "geometry": {"compared": sum(1 for x in geo if x["verdict"] != "N/A"), "pass": len(geo_pass), "pass_stage_box": len(stage_pass), "pass_other": len(geo_pass) - len(stage_pass)},
            "na_by_reason": na, "skipped_never_emitted": skipped, "slots_check": eq, "live_side": live,
            "delivered_texts_unpaired_total": sum(x["delivered_texts_unpaired"] for x in live), "duplicates": DUPLICATES,
            "club_colour_rows": sum(1 for x in rows if x["verdict"] == "FAIL" and str(x.get("expected")).upper() == "#17223F")}


def coverage_md(cv):
    out = ["**Coverage: what the pass count is made of.** Of %d slots, %d were compared (pass or fail) and %d were not (N/A), reasons below. There is no single headline rate: read the classes." % (cv["total_rows"], cv["compared"], cv["total_rows"] - cv["compared"]), ""]
    out += ["| Row class | Pass | Fail | N/A |", "|---|---|---|---|"]
    for k in CLASSES:
        c = cv["by_class"][k]
        if sum(c.values()):
            out.append("| %s | %d | %d | %d |" % (k, c["PASS"], c["FAIL"], c["N/A"]))
    g, fx = cv["geometry"], cv["flex"]
    cf = cv["by_class"]
    out += ["", "Geometry: %d of %d compared rows pass, of which %d are the stage box (the first node of the capture, taken from it) and %d are other boxes. Colour and font-size: %d of %d compared rows pass. Flex: %d of %d rows pass; %d of them have the value supplied by default because the render declared nothing (the same condition is N/A for colour and font-size), and %d pass with a value equal to Yoga's initial value whether declared or supplied. Passes by value source: %d declared, %d default." % (
        g["pass"], g["compared"], g["pass_stage_box"], g["pass_other"], cf["colour"]["PASS"] + cf["font-size"]["PASS"], cf["colour"]["PASS"] + cf["colour"]["FAIL"] + cf["font-size"]["PASS"] + cf["font-size"]["FAIL"],
        fx["pass"], fx["rows"], fx["pass_at_default"], fx["pass_value_equals_initial"], cv["passes_declared_vs_default"]["declared"], cv["passes_declared_vs_default"]["default"]), ""]
    out += ["| Fixture | " + " | ".join(k for k in CLASSES if cv["by_class"][k]["PASS"] + cv["by_class"][k]["FAIL"] + cv["by_class"][k]["N/A"]) + " |", "|---|" + "---|" * len([k for k in CLASSES if sum(cv["by_class"][k].values())])]
    for name, f in sorted(cv["by_fixture"].items()):
        out.append("| %s | " % name + " | ".join("%d / %d / %d" % (f[k]["PASS"], f[k]["FAIL"], f[k]["N/A"]) if k in f else "-" for k in CLASSES if sum(cv["by_class"][k].values())) + " |")
    out += ["", "(cells are pass / fail / N/A)", "", "**N/A by reason:** " + "; ".join("%s: %d" % (k, v) for k, v in sorted(cv["na_by_reason"].items(), key=lambda kv: -kv[1])) + ". "
            "No-declaration rows whose live value is not the initial or inherited one: %d." % cv["na_by_reason"].get("no-declaration-live-non-default", 0), "",
            "**Rows never emitted** (the runners skip them, they are in no verdict): " + "; ".join("%s: %d" % (k, v) for k, v in sorted(cv["skipped_never_emitted"].items())) + ". Emitted plus skipped equals render nodes times properties in every fixture: %s." % (
                "yes" if all(e["sums"] for e in cv["slots_check"]) else "NO - see the JSON"), "",
            "**Live-side coverage** (dump elements paired with a render node): " + "; ".join("%s %d of %d" % (x["fixture"], x["paired"], x["dump_nodes"]) for x in cv["live_side"]) +
            ". Captured delivered texts with no render node: %d." % cv["delivered_texts_unpaired_total"], "",
            "**Duplicates, counted twice:** tile-loans and tile-loans-c2-dump are one tile (%s). The club colour #17223F is counted in %d FAIL rows (three tiles and the state fixture's rest row). Nothing was deduplicated." % (DUPLICATES[0]["note"], cv["club_colour_rows"])]
    return out


# ---------------------------------------------------------------- the examination of the failures
LEGACY_COMPAT = {"sub-pixel offset": {"sub-pixel-tolerance"}, "run-time club-colour sheet": {"runtime-sheet-colour"}, "code-built or binding-driven colour": set(),
                 "code-built content: the tactics pitch": {"code-built-children"}, "code-built content: the Training tile": {"empty-code-list"},
                 "component-drawn image": {"runtime-class"}, "bound text, scroller or list width": {"stand-in-font"}}


def legacy_class(text):
    return next((k for k in LEGACY_COMPAT if text and text.startswith(k)), None)


def examination(results):
    fails = [x for x in all_rows(results) if x["verdict"] == "FAIL"]
    origin = [x for x in fails if (x.get("exam") or {}).get("status") == "origin"]
    inherited = [x for x in fails if (x.get("exam") or {}).get("status") == "inherited"]
    grades = {"measured fact": 0, "magnitude only": 0, "unexplained": 0}
    magnitude_not_predicted = 0
    for x in fails:
        g = x.get("cause_grade")
        grades[g if g else "unexplained"] += 1
        ev = (x.get("exam") or {}).get("evidence")
        if g == "measured fact" and isinstance(ev, dict) and not ev.get("magnitude_predicted", True) and (x.get("exam") or {}).get("status") == "origin":
            magnitude_not_predicted += 1
    D, conf = 0, {}
    for x in [y for y in fails if not y.get("variant_of")]:                         # the as-read variants are new rows of this round: they have no 1.0.0 label
        leg = legacy_class(x.get("legacy_cause"))
        new = x.get("cause_key")
        agree = (new in LEGACY_COMPAT.get(leg, set())) if leg else (new is None)
        D += 0 if agree else 1
        conf.setdefault(leg or "none", {}).setdefault(new or "UNEXPLAINED", 0)
        conf[leg or "none"][new or "UNEXPLAINED"] += 1
    double = sum(1 for x in fails if sum(1 for _t, test in __import__("skin_editor.render.fixtures", fromlist=["x"]).LEGACY_CAUSES if _safe(test, x)) > 1)
    by_cause = {}
    for x in fails:
        k = x.get("cause_key") or "UNEXPLAINED"
        c = by_cause.setdefault(k, {"rows": 0, "origin_rows": 0, "displaced_rows": 0})
        c["rows"] += 1
        c["origin_rows" if (x.get("exam") or {}).get("status") == "origin" else "displaced_rows"] += 1
    sus = [x["id"] for x in fails if any(v is False for k, v in ((x.get("exam") or {}).get("pair_checks") or {}).items() if k in ("same_type", "same_name", "parent_chain_ok", "live_visible", "text_equal"))]
    secondary = [x["id"] for x in fails if (x.get("exam") or {}).get("unexplained_components") and x.get("cause_key")]
    return {"pair_flags": sus, "rows_with_unexplained_secondary_component": secondary, "fail_rows": len(fails), "origin_rows": len(origin), "displaced_rows": len(inherited), "grades": grades, "unexplained": grades["unexplained"], "D": D, "confusion": conf,
            "legacy_rows_satisfying_two_rules": double, "by_cause": by_cause, "origin_magnitude_not_predicted": magnitude_not_predicted}


def _safe(test, x):
    try:
        return bool(test(x, x["fixture"]))
    except Exception:
        return False


def examination_md(results, ex):
    from .causes import RULES
    out = ["## The failures, examined row by row", "",
           "Each of the %d failing rows was examined individually (pairing, the x, y, w, h split against each tolerance, the parent's and the preceding sibling's displacement, and for origins a mechanism with one independent capture fact). %d are origin failures; %d are displaced by an origin listed beside them. %d causes rest on a measured capture fact, %d on magnitude only, %d are unexplained. The earlier rule label disagreed on %d rows; both are kept. The examiner wrote the rules; no second person checked." % (
               ex["fail_rows"], ex["origin_rows"], ex["displaced_rows"], ex["grades"]["measured fact"], ex["grades"]["magnitude only"], ex["unexplained"], ex["D"]), "",
           "Of the origin rows graded measured fact, %d name a class of cause without predicting the size of the gap (the pitch is code-built; the height deficit of 41 px is not derived). %d rows have a primary cause and at least one further origin component with no mechanism (listed in the JSON as unexplained_components); %d rows were flagged at the pairing step (a live partner that is invisible, or text that differs). The 1.0.0 labels came from fixture-wide rules: %d rows satisfied two of them, so list order decided the label." % (
               ex["origin_magnitude_not_predicted"], len(ex["rows_with_unexplained_secondary_component"]), len(ex["pair_flags"]), ex["legacy_rows_satisfying_two_rules"]), "",
           "| Root cause | Rows | Origin rows | Displaced rows |", "|---|---|---|---|"]
    for k, c in sorted(ex["by_cause"].items(), key=lambda kv: -kv[1]["rows"]):
        out.append("| %s | %d | %d | %d |" % (RULES[k][0] if k in RULES else "UNEXPLAINED (no supporting capture fact)", c["rows"], c["origin_rows"], c["displaced_rows"]))
    out += ["", "Confusion table, 1.0.0 label (rows) by the examined cause (columns): both labels are kept on every row.", ""]
    keys = sorted({n for v in ex["confusion"].values() for n in v})
    out += ["| 1.0.0 label | " + " | ".join(keys) + " |", "|---|" + "---|" * len(keys)]
    for leg, v in sorted(ex["confusion"].items()):
        out.append("| %s | " % leg + " | ".join(str(v.get(k, 0)) for k in keys) + " |")
    out += ["", "| Row id | Status | Origin id | Examined cause | Grade | Evidence | 1.0.0 label |", "|---|---|---|---|---|---|---|"]
    for r in results:
        for x in r["rows"]:
            if x["verdict"] != "FAIL":
                continue
            e = x.get("exam") or {}
            ev = e.get("evidence")
            evs = json.dumps(ev, default=str)[:160] if isinstance(ev, dict) else (ev or "")
            out.append("| %s | %s | %s | %s | %s | %s | %s |" % (x["id"], e.get("status"), (", ".join(o for o in e.get("origin_ids", []) if o != x["id"]) or "itself"), x.get("cause_key") or "UNEXPLAINED", x.get("cause_grade") or "-", evs, legacy_class(x.get("legacy_cause")) or "-"))
    return out


# ---------------------------------------------------------------- grid scoping
def grid_scoping(results, heldout_file=None):
    from . import pitch as pitch_mod
    pit = pitch_mod.table()
    rows = []
    for r in results:
        if not r["name"].startswith("screen-"):
            continue
        xs = [x for x in r["rows"] if x.get("kind") == "screen"]
        if not xs:
            continue
        res = [max(abs(v) for v in x["delta"]) for x in xs if x.get("delta")]
        rows.append({"fixture": r["name"], "source": r["source"], "hosts_compared": len(xs), "given_slots": sum(1 for x in xs if x.get("given")), "max_residual_px": max(res) if res else None,
                     "status": "measured-in-fit"})
    held = []
    if heldout_file and Path(heldout_file).is_file():
        by = {}
        for x in json.loads(Path(heldout_file).read_text(encoding="utf-8")):
            by.setdefault((x["capture"], x.get("composition")), []).append(x)
        for (cap, comp), xs in by.items():
            ok = [x for x in xs if x.get("residual") is not None]
            held.append({"capture": cap, "composition": comp, "hosts": len(xs), "exact": sum(1 for x in ok if x["max_abs"] == 0), "max_residual_px": max((x["max_abs"] for x in ok), default=None)})
    return {"measured_compositions": sorted(pit), "fixtures": rows, "heldout": held}
