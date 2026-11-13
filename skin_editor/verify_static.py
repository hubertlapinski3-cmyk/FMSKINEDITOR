"""Post-build gates. Structural gate = checks 1-3 of tools/verify_build.py (blocks install on failure).
Contrast = tools/contrast_gate.py (reported, does not block)."""
import itertools
import json
import re

from . import bundles, colour, uss
from . import token_patch as tp

EMPTY = {"tokens": {}, "literal_map": {}, "skip_sheets": []}


def _value_types(value):
    scratch = {"m_Rules": [], "colors": [], "floats": [], "dimensions": [], "strings": []}
    return [h["m_ValueType"] for h in tp.SheetPatcher(scratch, EMPTY)._encode(str(value))]


def _rule_matches(got, spec_rule, index):
    chains = tp.parse_selector(spec_rule["selector"])
    ok = len(got["m_ComplexSelectors"]) == len(chains)
    for cs, chain in zip(got["m_ComplexSelectors"], chains):
        ok &= cs["m_Specificity"] == tp.specificity(chain) and cs["ruleIndex"] == index
        ok &= len(cs["m_Selectors"]) == len(chain)
        for sel, (rel, parts) in zip(cs["m_Selectors"], chain):
            ok &= sel["m_PreviousRelationship"] == rel
            ok &= [(p["m_Type"], p["m_Value"]) for p in sel["m_Parts"]] == list(parts)
    want = ["-unity-font-definition" if k == "-unity-font" else k for k in spec_rule["props"]]
    ok &= [uss.prop_name(p) for p in got["m_Properties"]] == want
    for p, (k, v) in zip(got["m_Properties"], spec_rule["props"].items()):
        ok &= [h["m_ValueType"] for h in p["m_Values"]] == _value_types(v)
        ok &= (p["m_Id"] == -1) == k.startswith("--")
    return bool(ok)


def check_edits(edits, vrules, brules):
    """Failures of the in-place edits (replace/remove, in order) of one sheet. Every edit must match a rule of the game sheet, the same
    rules before and after; then each edited rule must hold exactly what applying its edits in order to the vanilla declarations gives:
    same slots in the same order, replaced values with the encoded value types, every other declaration unchanged.
    vrules/brules: the vanilla and built m_Rules."""
    fail, per_rule = [], {}
    for e in edits:
        want = tp.selector_key(e["selector"])
        vi = [i for i, r in enumerate(vrules) if tp.rule_key(r) == want]
        if not vi:
            fail.append("%s '%s' matches no rule of the game sheet" % (e["op"], e["selector"][:80]))
            continue
        bi = [i for i, r in enumerate(brules) if tp.rule_key(r) == want and i < len(vrules)]
        if bi != vi:
            fail.append("%s '%s': the rules it matches changed (%s -> %s)" % (e["op"], e["selector"][:80], vi, bi))
            continue
        for i in vi:
            per_rule.setdefault(i, []).append(e)
    for i, es in sorted(per_rule.items()):
        slots = [{"orig": p, "name": None, "types": None} for p in vrules[i]["m_Properties"]]
        hit = lambda s, n: tp.prop_matches(s["orig"], n) if s["orig"] is not None else s["name"] == n
        for e in es:
            if e["op"] == "remove":
                names = e.get("remove") or []
                slots = [s for s in slots if names and not any(hit(s, n) for n in names)]
                continue
            for k, v in e["props"].items():
                same = [s for s in slots if hit(s, k)]
                for s in same:
                    s["types"] = _value_types(v)
                if not same:
                    slots.append({"orig": None, "name": k, "types": _value_types(v)})
        after = brules[i]["m_Properties"]
        ok = len(after) == len(slots)
        for s, p in zip(slots, after):
            if s["orig"] is not None:
                ok &= p.get("m_Id") == s["orig"].get("m_Id") and p.get("m_CustomName") == s["orig"].get("m_CustomName")
                ok &= (p["m_Values"] == s["orig"]["m_Values"]) if s["types"] is None else [h["m_ValueType"] for h in p["m_Values"]] == s["types"]
            else:
                ok &= tp.prop_matches(p, s["name"]) and [h["m_ValueType"] for h in p["m_Values"]] == s["types"]
        if not ok:
            fail.append("rule %d (%s) does not hold what its edits ask for" % (i, es[0]["selector"][:80]))
    return fail


def check_edit(e, vrules, brules):
    return check_edits([e], vrules, brules)


POOLS = ("colors", "floats", "dimensions", "strings")


def untouched_check(label, vpath, bpath, touched):
    """Everything the patcher did not change must equal vanilla; the pools of the sheets it changed must be append-only.
    touched: path ids of the sheets that were saved. Returns (failures, notes). Each failure names the object and the first
    differing field path. Typetrees are compared as json.dumps(sort_keys=True) digests (NaN-safe); non-MonoBehaviour objects by
    get_raw_data(), falling back to typetree equality (and noting it) when the raw bytes differ."""
    fail, notes = [], []
    vd, _ = bundles.object_digests(vpath)
    bd, _ = bundles.object_digests(bpath)
    if set(vd) != set(bd):
        gone, extra = sorted(set(vd) - set(bd)), sorted(set(bd) - set(vd))
        fail.append("%s: object set differs from vanilla (missing path ids %s, extra %s)" % (label, gone[:5], extra[:5]))
    bad = sorted(i for i in vd if i in bd and i not in touched and vd[i][:2] != bd[i][:2])
    pools = sorted(i for i in touched if i in vd and i in bd)
    _, vtrees = bundles.object_digests(vpath, set(bad) | set(pools)) if (bad or pools) else ({}, {})
    _, btrees = bundles.object_digests(bpath, set(bad) | set(pools)) if (bad or pools) else ({}, {})
    for i in bad:
        where = bundles.first_difference(vtrees[i], btrees[i])
        if vd[i][0] == "raw" and where is not None:
            fb = _typetree_pair(vpath, bpath, i)
            if fb is True:
                notes.append("%s: %s differs in raw bytes but its typetree is identical to vanilla (raw comparison does not hold for this object type; typetree comparison used)" % (label, vd[i][2]))
                continue
        fail.append("%s: untouched object %s differs from vanilla at %s" % (label, vd[i][2], where or "(digest only)"))
    for i in pools:
        v, b = vtrees[i], btrees[i]
        if not (isinstance(v, dict) and isinstance(b, dict)):
            continue
        for pool in POOLS:
            vp, bp = v.get(pool) or [], b.get(pool) or []
            if len(bp) < len(vp):
                fail.append("%s: sheet %s pool %r shrank from %d to %d entries" % (label, vd[i][2], pool, len(vp), len(bp)))
                continue
            for k, (x, y) in enumerate(zip(vp, bp)):
                if json.dumps(x, sort_keys=True, default=str) != json.dumps(y, sort_keys=True, default=str):
                    fail.append("%s: sheet %s pool %r entry %d differs from vanilla (pools must be append-only): %s" % (
                        label, vd[i][2], pool, k, bundles.first_difference(x, y, "%s[%d]" % (pool, k)) or "(value)"))
                    break
    return fail, notes


def _typetree_pair(vpath, bpath, pid):
    """True when the typetree of object pid is equal in both bundles; None when it cannot be read."""
    import UnityPy
    try:
        a = next(o for o in UnityPy.load(str(vpath)).objects if o.path_id == pid).read_typetree()
        b = next(o for o in UnityPy.load(str(bpath)).objects if o.path_id == pid).read_typetree()
    except Exception:
        return None
    return bundles._digest(a) == bundles._digest(b)


def gate(spec, vanilla_dir, build_dir, files, touched=None):
    """Returns ({'fail': [...], 'checked': {...}}, {sheet name: built tree}). touched {bundle: set of changed sheet path ids}:
    when given, every bundle the build wrote is also checked object by object against vanilla (untouched_check); the check
    does not apply to a bundle that was not written (it is installed as the vanilla file)."""
    appended, skip = spec.get("append_rules_by_sheet", {}), set(spec.get("skip_sheets", []))
    fail, built, n_rules, notes, n_obj, n_edits, n_layouts, n_tiles, n_tables = [], {}, 0, [], 0, 0, 0, 0, 0
    for name, f in files.items():
        vc, vs, ve = bundles.inspect(vanilla_dir / name)
        bc, bs, be = bundles.inspect(build_dir / name) if f["changed"] else (vc, vs, ve)
        if not f.get("layout"):
            built.update(bs)                                   # a layout bundle's inline sheets are not game sheets
        if touched is not None and f["changed"]:
            fl, nt = untouched_check(name, vanilla_dir / name, build_dir / name, touched.get(name, set()))
            fail += fl
            notes += nt
            n_obj += 1
        if vc != bc:
            fail.append("%s: object counts differ %s vs %s" % (name, vc, bc))
        if be:
            fail.append("%s: %d objects do not deserialise (%s)" % (name, len(be), be[0]))
        if f.get("tables"):                                    # patched table views: vanilla column list plus exactly the asked-for column edits
            if f["changed"]:
                from . import tables as tables_mod
                docs = [d for d in spec.get("table_patches", []) if d["view"]["bundle"] == name]
                fail += ["%s: %s" % (name, m) for m in tables_mod.check_patches(vanilla_dir / name, build_dir / name, docs)]
                n_tables += len(docs)
            continue
        if f.get("tiles"):                                     # moved grid cells: only the asked-for m_location x/y differ, in the asked-for compositions
            if f["changed"]:
                from . import tiles as tiles_mod
                ops = [o for o in spec.get("tile_ops", []) if o["bundle"] == name]
                fail += ["%s: %s" % (name, m) for m in tiles_mod.check_ops(vanilla_dir / name, build_dir / name, ops)]
                n_tiles += len(ops)
            continue
        if f.get("layout"):                                    # patched layouts: the layout plus exactly the asked-for edits, nothing else
            if f["changed"]:
                from . import uxml
                docs = [d for d in spec.get("layout_patches", []) if d["layout"]["bundle"] == name]
                fail += ["%s: %s" % (name, m) for m in uxml.check_patches(vanilla_dir / name, build_dir / name, docs)]
                n_layouts += len(docs)
            continue
        for sheet, vt in vs.items():
            if sheet not in bs:
                fail.append("%s: sheet missing from the build" % sheet)
                continue
            rules = [] if sheet in skip else appended.get(sheet, [])
            for k, c in enumerate(bs[sheet].get("colors", [])[len(vt.get("colors", [])):]):
                if not colour.in_range(c):      # every colour entry the build added must be a 0..1 quadruplet
                    fail.append("%s: build wrote colour %r outside 0..1 (entry %d)"
                                % (sheet, colour.raw_floats(c), len(vt.get("colors", [])) + k))
            base, got = len(vt["m_Rules"]), len(bs[sheet]["m_Rules"])
            if got != base + len(rules):
                fail.append("%s: %d rules, expected %d" % (sheet, got, base + len(rules)))
                continue
            for i, r in enumerate(rules):
                n_rules += 1
                try:
                    good = _rule_matches(bs[sheet]["m_Rules"][base + i], r, base + i)
                except Exception as e:
                    good = False
                    r = dict(r, selector=r["selector"] + " (%s)" % e)
                if not good:
                    fail.append("appended rule %d '%s' does not decode to the spec" % (i, r["selector"][:80]))
            edits = [] if sheet in skip else spec.get("edit_rules_by_sheet", {}).get(sheet, [])
            n_edits += len(edits)
            try:
                fail += ["%s: %s" % (sheet, m) for m in check_edits(edits, vt["m_Rules"], bs[sheet]["m_Rules"])]
            except Exception as ex:
                fail.append("%s: the edits could not be checked (%s)" % (sheet, ex))
    return {"fail": fail, "appended_rules_checked": n_rules, "edits_checked": n_edits, "layout_patches_checked": n_layouts, "tile_moves_checked": n_tiles, "table_patches_checked": n_tables, "untouched_bundles_checked": n_obj if touched is not None else "skipped",
            "notes": notes}, built


# ---- contrast (contrast_gate.py, alpha-aware)
def _lum(c):
    def ch(x):
        x /= 255
        return x / 12.92 if x <= 0.03928 else ((x + 0.055) / 1.055) ** 2.4
    r, g, b = (ch(x) for x in c[:3])
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def ratio(a, b):
    la, lb = sorted((_lum(a), _lum(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def _ref(v):
    """Pair side as text: token name, var(--x), or a colour."""
    c = colour.coerce(v) if (colour.is_obj(v) or isinstance(v, str)) else None
    return colour.patch_value(c) if c else str(v)


def contrast(spec, built_sheets, pairs_extra=(), page=(0x17, 0x17, 0x17, 1.0)):
    """Text colour against its surface, both with their alpha. The surface is composited over the backdrop
    (options.contrast_backdrop), the text over the composited surface, then the ratio is taken.
    Surface source per pair: the rule's own background-color, the rule's 'on' list, a contrast_pairs entry,
    or the backdrop itself when a rule sets only color. Tokens resolve from the built sheets; every
    definition is tried and the worst case reported."""
    skip, defs = set(spec.get("skip_sheets", [])), {}
    for name, t in built_sheets.items():
        if name in skip:
            continue
        for r in t["m_Rules"]:
            if uss.is_token_rule(r.get("m_ComplexSelectors", [])):
                for p in r["m_Properties"]:
                    if p.get("m_CustomName"):
                        text, cols = uss.value_text(t, p["m_Values"])
                        one = len(cols) == 1 and not text.startswith("var(") and " " not in text
                        defs.setdefault(p["m_CustomName"], []).append(
                            colour.from_obj({"rgb": cols[0][0], "a": cols[0][1]}) if one else text)

    def resolve(v, depth=0):
        if isinstance(v, tuple):
            return {v}
        m = re.match(r"var\((--[\w-]+)\)$", v.strip())
        if m:
            if depth > 12 or m.group(1) not in defs:
                return set()
            return set().union(*[resolve(x, depth + 1) for x in defs[m.group(1)]])
        c = colour.parse(v)
        return {c} if c else set()

    def values(ref):
        return resolve(ref if ref.startswith(("#", "var(", "rgb")) else "var(%s)" % ref)

    backdrop = colour.hex6(page)
    pairs = []
    replaced = [[e for e in es if e["op"] == "replace"] for es in spec.get("edit_rules_by_sheet", {}).values()]
    for rules in list(spec.get("append_rules_by_sheet", {}).values()) + replaced:    # a replace sets colours too
        for r in rules:
            pr = r["props"]
            if "color" not in pr:
                continue
            if "background-color" in pr:
                pairs.append({"fg": pr["color"], "bg": pr["background-color"], "src": r["selector"], "bg_source": "rule background-color"})
            if r.get("on"):
                pairs += [{"fg": pr["color"], "bg": b, "src": r["selector"], "bg_source": "rule on"} for b in r["on"]]
            if "background-color" not in pr and not r.get("on"):
                pairs.append({"fg": pr["color"], "bg": backdrop, "src": r["selector"], "bg_source": "default backdrop"})
    pairs += [dict(p, fg=_ref(p["fg"]), bg=_ref(p["bg"]), src=p.get("note", "contrast_pairs"), bg_source="contrast_pairs")
              for p in pairs_extra]
    rows = []
    for p in pairs:
        fgs, bgs, need = values(str(p["fg"])), values(str(p["bg"])), p.get("min", 4.5)
        row = {"fg": p["fg"], "bg": p["bg"], "need": need, "src": p["src"][:80], "bg_source": p["bg_source"],
               "backdrop": backdrop}
        if not fgs or not bgs:
            rows.append(dict(row, status="UNRESOLVED", ratio=None, composited=False))
            continue
        worst = None
        for fg, bg in itertools.product(fgs, bgs):
            bgc = colour.composite(bg, page)
            fgc = colour.composite(fg, bgc)
            r = ratio(fgc, bgc)
            if worst is None or r < worst[0]:
                worst = (r, fg, bg, fgc, bgc)
        r, fg, bg, fgc, bgc = worst
        rows.append(dict(row, status="PASS" if r >= need else "FAIL", ratio=round(r, 2),
                         fg_rgba=colour.to_obj(fg), bg_rgba=colour.to_obj(bg),
                         fg_painted=colour.hex6(fgc), bg_painted=colour.hex6(bgc),
                         composited=fg[3] < 1.0 or bg[3] < 1.0))
    rows.sort(key=lambda x: (x["status"] == "PASS", x["ratio"] or 0))
    return {"pairs": len(rows), "failures": sum(r["status"] != "PASS" for r in rows),
            "composited": sum(bool(r["composited"]) for r in rows), "backdrop": backdrop, "rows": rows}
