#!/usr/bin/env python3
"""diag_colours.py [BUNDLE_DIR] [--out DIR] - read-only evidence for the colour scale question.

Background (2026-11-11, first real-bundle run on macOS): the index build met bundle colours outside 0..1:
  AlwaysAppliedStyleSheet rule 1766 .continue-button---carabao-cup -unity-background-image-tint-color
  -> #04A08C with alpha 124.0, and an entry #AF78FF with alpha 100.0.
Two hypotheses: (a) some colour pool entries are authored outside 0..1 (percent? byte scale?);
(b) the value handle is misparsed and lands on the wrong entry or the wrong pool.
This script decides nothing. It prints what is stored so the rule can be chosen from evidence.

Reads the two style bundles from BUNDLE_DIR (default: the app's vanilla snapshot). Never writes there.
Writes colour-diag.txt and colour-diag.json into --out (default: <repo>/diagnostics).
It does not use the app's decoder: selectors, handles and pools are read straight from the typetree.

Run:  .venv/bin/python tools/diag_colours.py
"""
import argparse
import collections
import hashlib
import json
import math
import os
import struct
import sys
import time

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)
BUNDLES = ["ui-styles_assets_common.bundle", "ui-styles_assets_default.bundle"]
TINT = 196610            # -unity-background-image-tint-color in token_patch.PROP_TABLE
POOL_OF = {2: "floats", 3: "dimensions", 4: "colors", 5: "strings", 6: "assets", 7: "strings", 8: "strings", 9: "strings"}
KNOWN = {"fm-orange": "FF501E", "midnight": "0A0F1E", "horizon": "AF78FF"}   # FM26 ground truth to compare with

try:
    from skin_editor.token_patch import INV_PROP
except Exception:       # the script must run even if the package is broken
    INV_PROP = {}


def prop_name(p):
    return p.get("m_CustomName") or INV_PROP.get(p.get("m_Id"), "prop-%s" % p.get("m_Id"))


def sel_text(rule):
    out = []
    for cs in rule.get("m_ComplexSelectors", []):
        s = ""
        for sel in cs.get("m_Selectors", []):
            rel = sel.get("m_PreviousRelationship", 0)
            s += " > " if rel == 1 else " " if rel == 2 else ""
            for p in sel.get("m_Parts", []):
                t, v = p.get("m_Type"), p.get("m_Value", "")
                s += {1: "*", 3: "." + v, 4: ":" + v, 6: "#" + v}.get(t, v)
        out.append(s.strip())
    return ", ".join(out)


def is_root(rule):
    return any(p.get("m_Type") == 4 and p.get("m_Value") == "root"
               for cs in rule.get("m_ComplexSelectors", []) for sel in cs.get("m_Selectors", []) for p in sel.get("m_Parts", []))


def quad(c):
    return [float(c.get(k, float("nan"))) for k in "rgba"] if isinstance(c, dict) else None


def f32hex(q):
    return " ".join(struct.pack("<f", v).hex() for v in q)


def hex01(q):
    """Hex under the plain 0..1 reading, clamped. For comparison only."""
    return "".join("%02X" % int(math.floor(min(1.0, max(0.0, v)) * 255 + 0.5)) for v in q)


def bad(q):
    return q is None or any(not (0.0 <= v <= 1.0) for v in q)     # NaN counts as bad


def bucket():
    return {"n": 0, "lt0": 0, "le1": 0, "1_100": 0, "100_255": 0, "gt255": 0, "nonfinite": 0, "max": None,
            "gt1_integer": 0, "gt1_noninteger": 0, "gt1_values": collections.Counter()}


def add(b, v):
    b["n"] += 1
    if v != v or v in (float("inf"), float("-inf")):
        b["nonfinite"] += 1
        return
    b["max"] = v if b["max"] is None else max(b["max"], v)
    if v < 0:
        b["lt0"] += 1
    elif v <= 1:
        b["le1"] += 1
    else:
        b["1_100" if v <= 100 else "100_255" if v <= 255 else "gt255"] += 1
        b["gt1_integer" if v == int(v) else "gt1_noninteger"] += 1
        b["gt1_values"][repr(v)] += 1


def analyse(sheets):
    """sheets: [{bundle, name, path_id, tree, raw (bytes or None)}]. Pure: no file access."""
    hist = {k: bucket() for k in ("all", "r", "g", "b", "a")}
    per_bundle = {}
    entries = {"total": 0, "any_out_of_range": 0, "alpha_only_out": 0, "rgb_out": 0, "out_and_referenced": 0, "out_and_unreferenced": 0}
    vt = collections.defaultdict(lambda: {"count": 0, "min_index": None, "max_index": None, "index_out_of_pool": 0})
    tint_shapes, failures, carabao, siblings, af78ff, known = collections.Counter(), [], [], [], [], []
    for sh in sheets:
        t = sh["tree"]
        pool = t.get("colors", [])
        refs = collections.defaultdict(list)
        for ri, rule in enumerate(t.get("m_Rules", [])):
            st = sel_text(rule)
            for p in rule.get("m_Properties", []):
                hs = p.get("m_Values", [])
                shape = ",".join(str(h.get("m_ValueType")) for h in hs)
                if p.get("m_Id") == TINT:
                    tint_shapes[shape] += 1
                for h in hs:
                    ty, ix = h.get("m_ValueType"), h.get("valueIndex")
                    v = vt[ty]
                    v["count"] += 1
                    v["min_index"] = ix if v["min_index"] is None else min(v["min_index"], ix)
                    v["max_index"] = ix if v["max_index"] is None else max(v["max_index"], ix)
                    if ty in POOL_OF and not (0 <= ix < len(t.get(POOL_OF[ty], []))):
                        v["index_out_of_pool"] += 1
                    if ty == 4:
                        refs[ix].append((ri, st, prop_name(p)))
                        q = quad(pool[ix]) if 0 <= ix < len(pool) else None
                        if bad(q):
                            raw = sh.get("raw")
                            pat = struct.pack("<4f", *q) if q and all(v_ == v_ for v_ in q) else None
                            failures.append({
                                "bundle": sh["bundle"], "sheet": sh["name"], "path_id": sh.get("path_id"), "rule": ri, "selector": st,
                                "property_id": p.get("m_Id"), "property": prop_name(p), "handles": [[h_.get("m_ValueType"), h_.get("valueIndex")] for h_ in hs],
                                "index": ix, "pool_len": len(pool), "raw": q, "raw_f32_hex": f32hex(q) if q else None,
                                "raw_bytes_found_in_object": (raw.count(pat) if raw is not None and pat else None),
                                "raw_bytes_first_offset": (raw.find(pat) if raw is not None and pat else None),
                                "neighbours": {str(j): quad(pool[j]) for j in (ix - 1, ix + 1) if 0 <= j < len(pool)}})
                if "carabao" in st:
                    carabao.append({"bundle": sh["bundle"], "sheet": sh["name"], "rule": ri, "selector": st, "property_id": p.get("m_Id"),
                                    "property": prop_name(p), "handles": [[h.get("m_ValueType"), h.get("valueIndex")] for h in hs],
                                    "colours": {str(h["valueIndex"]): (quad(pool[h["valueIndex"]]) if 0 <= h["valueIndex"] < len(pool) else None)
                                                for h in hs if h.get("m_ValueType") == 4}})
                if "continue-button---" in st and p.get("m_Id") == TINT:
                    for h in hs:
                        if h.get("m_ValueType") == 4:
                            siblings.append({"sheet": sh["name"], "rule": ri, "selector": st, "index": h["valueIndex"],
                                             "raw": quad(pool[h["valueIndex"]]) if 0 <= h["valueIndex"] < len(pool) else None})
                if is_root(rule) and p.get("m_CustomName"):
                    for key, want in KNOWN.items():
                        if key in p["m_CustomName"]:
                            for h in hs:
                                if h.get("m_ValueType") == 4 and 0 <= h["valueIndex"] < len(pool):
                                    q = quad(pool[h["valueIndex"]])
                                    known.append({"sheet": sh["name"], "token": p["m_CustomName"], "raw": q, "hex_0_1": hex01(q[:3]),
                                                  "expected_family": want, "rgb_matches": hex01(q[:3]) == want})
        pb = per_bundle.setdefault(sh["bundle"], {k: bucket() for k in ("all", "r", "g", "b", "a")})
        for i, c in enumerate(pool):
            q = quad(c)
            entries["total"] += 1
            for k, v in zip("rgba", q):
                for h in (hist, pb):
                    add(h[k], v)
                    add(h["all"], v)
            if bad(q):
                entries["any_out_of_range"] += 1
                rgb_out = any(not (0.0 <= v <= 1.0) for v in q[:3])
                entries["rgb_out" if rgb_out else "alpha_only_out"] += 1
                entries["out_and_referenced" if refs.get(i) else "out_and_unreferenced"] += 1
            if hex01(q[:3]) == "AF78FF":
                af78ff.append({"bundle": sh["bundle"], "sheet": sh["name"], "index": i, "raw": q, "raw_f32_hex": f32hex(q),
                               "referenced_by": [{"rule": r, "selector": s, "property": pn} for r, s, pn in refs.get(i, [])][:20],
                               "reference_count": len(refs.get(i, []))})

    def fin(h):
        out = {}
        for k, b in h.items():
            b = dict(b)
            b["gt1_values"] = b["gt1_values"].most_common(40)
            out[k] = b
        return out
    return {"sheets": len(sheets), "entries": entries, "histogram": fin(hist), "histogram_per_bundle": {k: fin(v) for k, v in per_bundle.items()},
            "handles_by_value_type": {str(k): v for k, v in sorted(vt.items(), key=lambda kv: str(kv[0]))},
            "tint_property_handle_shapes": tint_shapes.most_common(), "failures": failures, "carabao_rules": carabao,
            "continue_button_tint_siblings": siblings, "af78ff_entries": af78ff, "known_colour_tokens": known}


# ---------------------------------------------------------------- bundle access (UnityPy)
def dump_node(node, depth=0, limit=5):
    line = "%s%s %s (bytes %s)" % ("  " * depth, getattr(node, "m_Type", "?"), getattr(node, "m_Name", "?"), getattr(node, "m_ByteSize", "?"))
    out = [line]
    if depth < limit:
        for ch in getattr(node, "m_Children", None) or []:
            out += dump_node(ch, depth + 1, limit)
    return out


def find_field(node, name):
    for ch in getattr(node, "m_Children", None) or []:
        if getattr(ch, "m_Name", None) == name:
            return ch
    return None


def load(path):
    import UnityPy
    env = UnityPy.load(path)
    sheets, structs, version = [], collections.Counter(), None
    for obj in env.objects:
        if version is None:
            version = str(getattr(getattr(obj, "assets_file", None), "unity_version", "?"))
        if obj.type.name != "MonoBehaviour":
            continue
        try:
            tree = obj.read_typetree()
        except Exception:
            continue
        if not isinstance(tree, dict) or "m_Rules" not in tree:
            continue
        try:
            root = obj._get_typetree_node()
            text = []
            for field in ("colors", "floats", "dimensions"):
                f = find_field(root, field)
                text += dump_node(f) if f is not None else ["<no field %s in the declared typetree>" % field]
            rules = find_field(root, "m_Rules")
            text += ["-- m_Rules element --"] + (dump_node(rules, limit=9) if rules is not None else ["<none>"])
            structs["\n".join(text)] += 1
        except Exception as e:
            structs["<typetree nodes not readable: %s: %s>" % (type(e).__name__, e)] += 1
        try:
            raw = obj.get_raw_data()
        except Exception:
            raw = None
        sheets.append({"bundle": os.path.basename(path), "name": tree.get("m_Name", ""), "path_id": obj.path_id, "tree": tree, "raw": raw})
    return sheets, structs, version


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


# ---------------------------------------------------------------- report text
def render(rep, files, structs):
    L = ["FM27 colour scale diagnostic  %s" % time.strftime("%Y-%m-%d %H:%M:%S"), "Read-only. Decides nothing.", ""]
    L.append("== 1. Files")
    for f in files:
        L.append("  %s  %s bytes  sha256 %s  unity %s  stylesheets %s" % (f["name"], f["size"], f["sha256"], f["unity"], f["sheets"]))
    L += ["", "== 2. Declared typetree of the pools and of a rule (distinct structures, with the number of sheets using each)"]
    for text, n in structs:
        L.append("  -- %d sheet(s) --" % n)
        L += ["  " + x for x in text.split("\n")]
    L += ["", "== 3. Histogram of ALL colour pool components (both bundles), then per bundle",
          "  entries: %s" % json.dumps(rep["entries"])]

    def hist(h, indent="  "):
        for k in ("all", "r", "g", "b", "a"):
            b = h[k]
            L.append("%s%-3s n=%d  <0:%d  <=1:%d  (1,100]:%d  (100,255]:%d  >255:%d  nonfinite:%d  max=%r  >1 integers:%d  >1 non-integers:%d"
                     % (indent, k, b["n"], b["lt0"], b["le1"], b["1_100"], b["100_255"], b["gt255"], b["nonfinite"], b["max"],
                        b["gt1_integer"], b["gt1_noninteger"]))
            if b["gt1_values"]:
                L.append("%s    values >1 (value x count): %s" % (indent, ", ".join("%s x%d" % (v, n) for v, n in b["gt1_values"])))
    hist(rep["histogram"])
    for name, h in rep["histogram_per_bundle"].items():
        L.append("  " + name)
        hist(h, "    ")
    L += ["", "== 4. Handles by value type (hypothesis b: are colour handles landing inside the colour pool?)"]
    for k, v in rep["handles_by_value_type"].items():
        L.append("  type %-4s count=%d  valueIndex min=%s max=%s  index outside its pool: %d" % (k, v["count"], v["min_index"], v["max_index"], v["index_out_of_pool"]))
    L.append("  handle type sequences of -unity-background-image-tint-color (id %d): %s" % (TINT, ", ".join("[%s] x%d" % sn for sn in rep["tint_property_handle_shapes"]) or "none"))
    L += ["", "== 5. Every colour handle whose entry is outside 0..1 or outside the pool: %d" % len(rep["failures"])]
    for f in rep["failures"]:
        L.append("  %s / %s (path_id %s) rule %d  %s" % (f["bundle"], f["sheet"], f["path_id"], f["rule"], f["selector"]))
        L.append("      property %s (id %s)  handles [type, index] %s" % (f["property"], f["property_id"], f["handles"]))
        L.append("      colors[%d] of %d  raw r,g,b,a = %r   float32 bytes: %s" % (f["index"], f["pool_len"], f["raw"], f["raw_f32_hex"]))
        L.append("      same 16 bytes found in the object's raw data: %s time(s), first offset %s   neighbours: %s"
                 % (f["raw_bytes_found_in_object"], f["raw_bytes_first_offset"], json.dumps(f["neighbours"])))
    L += ["", "== 6. Rules with 'carabao' in the selector, every property with raw handles"]
    for c in rep["carabao_rules"]:
        L.append("  %s rule %d  %s  |  %s (id %s)  handles %s  colours %s" % (c["sheet"], c["rule"], c["selector"], c["property"], c["property_id"], c["handles"], json.dumps(c["colours"])))
    L.append("  -- other .continue-button---* rules with the tint property (compare their alphas) --")
    for s in rep["continue_button_tint_siblings"]:
        L.append("  %s rule %d  %s  colors[%d] = %r" % (s["sheet"], s["rule"], s["selector"], s["index"], s["raw"]))
    L += ["", "== 7. Pool entries whose RGB reads as #AF78FF under 0..1"]
    for e in rep["af78ff_entries"]:
        L.append("  %s / %s colors[%d] raw %r  float32 %s  referenced %d time(s)" % (e["bundle"], e["sheet"], e["index"], e["raw"], e["raw_f32_hex"], e["reference_count"]))
        for r in e["referenced_by"]:
            L.append("      rule %d  %s  %s" % (r["rule"], r["selector"], r["property"]))
    L += ["", "== 8. Known colours (:root tokens with fm-orange / midnight / horizon in the name; FM26 truth FF501E / 0A0F1E / AF78FF)"]
    for k in rep["known_colour_tokens"]:
        L.append("  %s  %s  raw %r  hex under 0..1: %s  %s" % (k["sheet"], k["token"], k["raw"], k["hex_0_1"],
                                                               "= " + k["expected_family"] if k["rgb_matches"] else ""))
    return "\n".join(L) + "\n"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("bundle_dir", nargs="?")
    ap.add_argument("--out", default=os.path.join(REPO, "diagnostics"))
    a = ap.parse_args()
    src = a.bundle_dir
    if not src:
        from skin_editor import config
        src = str(config.workspace(config.load()).vanilla)
    out = os.path.abspath(a.out)
    if os.path.abspath(src) == out or "streamingassets" in out.lower():
        print("REFUSED: the output folder must not be the bundle folder")
        return 3
    sheets, structs, files = [], collections.Counter(), []
    for name in BUNDLES:
        path = os.path.join(src, name)
        if not os.path.isfile(path):
            print("missing: " + path)
            return 2
        s, st, version = load(path)
        sheets += s
        structs.update(st)
        files.append({"name": name, "size": os.path.getsize(path), "sha256": sha256(path), "unity": version, "sheets": len(s)})
    rep = analyse(sheets)
    os.makedirs(out, exist_ok=True)
    text = render(rep, files, structs.most_common())
    with open(os.path.join(out, "colour-diag.txt"), "w", encoding="utf-8") as f:
        f.write(text)
    with open(os.path.join(out, "colour-diag.json"), "w", encoding="utf-8") as f:
        json.dump({"files": files, "typetree": structs.most_common(), "report": rep}, f, indent=1)
    print(text)
    print("written: %s and colour-diag.json" % os.path.join(out, "colour-diag.txt"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
