"""S0 of the Simple mode plan (docs/SIMPLE-MODE-PLAN.md): the colour-token inventory and the first-run timings. Offline; the real workspace and the game are only READ.

    python tools/make_token_inventory.py            # writes data/simple/token-inventory.json and the measurements file

data/simple/token-inventory.json holds no timestamps and no timings (it is generated data: the same index gives the same bytes).
The timings (snapshot copy, cold style-index build, index load, Crimson built in memory) go to docs/evidence/phase9-s0-measurements-<date>.json: they depend on the machine.
They are measured in a SCRATCH workspace (a temporary folder; its snapshot copy is read from the game, its index cache is written to the scratch folder), never in the real one."""
import json
import shutil
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from skin_editor import config, detect, index_styles, install      # noqa: E402
from skin_editor.presets import PRESETS                              # noqa: E402

OUT = ROOT / "data" / "simple" / "token-inventory.json"
MEAS = ROOT / "docs" / "evidence" / "phase9-s0-measurements-20261115.json"


def family(name):
    parts = name.lstrip("-").split("-")
    return "-".join(parts[:2]) if len(parts) > 1 else parts[0]


def crimson_palette():
    """The crimson preset's own palette (--cr-* name -> colour text), read from the code of presets/crimson.py: the statements of make() above its token section are executed
    in an empty namespace, so the ramps are the preset's, not retyped here."""
    import inspect
    import re
    import textwrap
    from skin_editor.presets import crimson
    src = inspect.getsource(crimson.make).split("\n", 1)[1]
    src = src.split("# ---------------------------------------------------------------- tokens")[0]
    ns = {"re": re}
    exec(textwrap.dedent(src), ns)            # noqa: S102  (our own repo's code, no input)
    return ns["CR"]


def ramp_of(name):
    """--cr-<ramp>-<step> -> the ramp's name."""
    n = name[len("--cr-"):]
    first = n.split("-")[0]
    return {"n": "neutral", "c": "crimson", "a": "alpha overlay", "t": "text", "white": "text"}.get(first, "scale-soft" if n.startswith("scale-soft") else first)


# role of a token, from its NAME and the preset's own note on it, first rule wins. INFERRED (the game has no role field); every row records the rule that fired.
ROLE_RULES = [
    ("page background", r"^--global-background$", None),
    ("calendar / training colours", r"^--colours-calendar-", None),
    ("chart / data series", r"^--colours-(chart|data|linear)-|^--data-average-", None),
    ("tactics position", r"^--colours-tactics-|^--data-player-position-", None),
    ("coaching rating", r"^--status-coaching-", None),
    ("base hue ramp", r"^--colours-base-", None),
    ("hover / pressed", r"hover|pressed|-active", None),
    ("selection", r"selected|selection", None),
    ("focus ring", r"focus", None),
    ("positive", r"feedback-positive|-positive$", None),
    ("negative", r"feedback-negative|-negative$", None),
    ("warning / notice", r"warning|-alert$|-information$", None),
    ("accent text", None, r"crimson text"),
    ("accent", r"^--brand-theme-|^--colours-brand-accent$|^--buttons-primary-|^--continue-button-|key-accent|toggle-active-primary|^--buttons-text-", None),
    ("brand palette", r"^--colours-brand-", None),
    ("primary text", r"^--global-text-primary$|^--modal-text-primary$|^--colours-ui-text-strong$|^--layout-tiles-heading|^--internal-_text", None),
    ("secondary text", r"^--global-text-secondary$|^--colours-ui-text-soft$", None),
    ("border / divider", r"border|^--global-border", None),
    ("raised surface", r"surface|^--layout-ui-|^--tiles-|^--layout-modules-block|^--data-tables-background|^--layout-surfaces-", None),
    ("UI surface ramp", r"^--colours-ui-(base|deep|soft|strong)$", None),
    ("status / club marker", r"^--status-|^--communication-manager-", None),
]


def role_of(token, note):
    import re
    for role, name_re, note_re in ROLE_RULES:
        if (name_re and re.search(name_re, token)) or (note_re and note and re.search(note_re, note)):
            return role, (name_re or note_re)
    return "other (unclassified)", None


def crimson_roles(crimson, palette):
    """One row per colour override of the crimson preset: the ramp and step it was given (matched on the exact output colour against the preset's palette), the preset's own note, and the inferred role."""
    by = {}
    for nm, val in palette.items():
        v = val.upper()
        key = (v[:7], int(v[7:9], 16) if len(v) == 9 else 255)
        by.setdefault(key, []).append(nm)
    rows = []
    for o in crimson["token_overrides"]:
        if not isinstance(o["value"], dict):
            continue
        v = o["value"]
        key = (v["rgb"].upper(), round(v["a"] * 255))
        cands = by.get(key, [])
        role, rule = role_of(o["token"], o.get("note", ""))
        rows.append({"token": o["token"], "vanilla": o.get("vanilla"), "crimson": "%s a=%s" % (v["rgb"], round(v["a"], 3)), "preset_note": o.get("note", ""),
                     "palette_entry": cands[0][len("--cr-"):] if cands else None, "ramp": ramp_of(cands[0]) if cands else "off-palette (computed at the token)",
                     "palette_entries_with_the_same_colour": len(cands), "role": role, "role_rule": rule})
    count = lambda k: {a: sum(1 for r in rows if r[k] == a) for a in sorted({r[k] for r in rows})}
    return {"note": "second source for S4's role map: what the crimson preset (proven in game in its bundle form) gave each overridden colour token. 'ramp' and 'palette_entry' come from matching the output colour against the preset's own palette (crimson.py); 'preset_note' is the preset's own comment (a design-guide section and the rule applied); 'role' is INFERRED from the token's name by the ordered rules in ROLE_RULES, and 'role_rule' is the rule that fired.",
            "palette_entries": len(palette), "summary": {"colour_overrides": len(rows), "by_role": count("role"), "by_ramp": count("ramp"),
                                                         "off_palette": sum(1 for r in rows if r["palette_entry"] is None),
                                                         "role_unclassified": sum(1 for r in rows if r["role"].startswith("other"))}, "rows": rows}


def literal_inventory(ix, crimson):
    """One row per distinct literal colour (RGB + alpha) in the game's rules: property uses, token definitions, distinct selectors and rule paths, sheets, the properties it is used on, and what a native export would copy for each swap mode."""
    swapped = {(s["from"]["rgb"].upper(), round(s["from"]["a"], 3)) for s in crimson.get("literal_swaps", [])}
    rows = []
    for key, hits in ix.literals.items():
        h0 = hits[0]
        uses = [h for h in hits if not h["token_def"]]
        props = {}
        for h in uses:
            props[h["property"]] = props.get(h["property"], 0) + 1
        rgb_uses = [h for h in ix.by_rgb[h0["rgb"]] if not h["token_def"]]
        rows.append({"rgb": h0["rgb"], "a": h0["a"], "uses": len(uses), "token_definitions": len(hits) - len(uses),
                     "selectors": len({s for h in uses for s in h["selectors"]}), "rule_paths": len({(h["sheet"], h["selector"], h["property"]) for h in uses}),
                     "sheets": len({h["sheet"] for h in uses}), "top_properties": dict(sorted(props.items(), key=lambda kv: (-kv[1], kv[0]))[:3]),
                     "native_rules_copied_exact_alpha": len(uses), "native_rules_copied_rgb_keep_alpha": len(rgb_uses),
                     "crimson_swapped": (h0["rgb"].upper(), round(h0["a"], 3)) in swapped})
    rows.sort(key=lambda r: (-r["uses"], r["rgb"], r["a"]))
    # cross-check against the real thing: the rules the native export copies for the crimson swaps, counted here from the index by the swap's own mode
    from skin_editor import native
    real_rules, _notes = native.literal_rules(crimson, ix)
    mine = 0
    for s in crimson.get("literal_swaps", []):
        from skin_editor import colour as colour_mod
        f = colour_mod.from_obj(s["from"])
        hits = ix.literal(colour_mod.hex6(f), f[3])["exact"] if s["mode"] == "rgba" else ix.literal(colour_mod.hex6(f), 1.0)["rgb_all"]
        mine += sum(1 for h in hits if not h.get("token_def"))
    assert mine == len(real_rules), "literal inventory disagrees with native.literal_rules: %d vs %d" % (mine, len(real_rules))
    return {"note": "generated from the style index. 'uses' counts the rule declarations that hold the colour as a literal (token definitions are counted apart: the token route covers them); 'native_rules_copied_*' is how many game rules a native export copies for a swap of this colour in each mode (native.literal_rules writes one rule per use).",
            "summary": {"distinct_literals": len(rows), "with_at_least_one_use": sum(1 for r in rows if r["uses"] > 0), "only_in_token_definitions": sum(1 for r in rows if r["uses"] == 0),
                        "total_uses": sum(r["uses"] for r in rows), "crimson_swapped": sum(1 for r in rows if r["crimson_swapped"]),
                        "uses_covered_by_crimson_swaps_exact_alpha": sum(r["uses"] for r in rows if r["crimson_swapped"]),
                        "game_rules_the_native_crimson_export_copies_for_its_literal_swaps": len(real_rules), "crimson_literal_swaps": len(crimson.get("literal_swaps", []))}, "rows": rows}


def inventory(ix, crimson_tokens, crimson=None):
    rows, fams = [], {}
    for name in sorted(ix.defs):
        r = ix.token_row(name)
        col = r["resolved"]
        if not col:
            continue
        reach = r["reach"]
        row = {"token": name, "value": r["value"], "chain": len(r["chain"]) - 1, "rgb": col["rgb"], "a": col["a"], "rules": reach,
               "sheets_defining": r["sheets"], "conflict": r["conflict"], "crimson_overrides": name in crimson_tokens}
        rows.append(row)
        f = fams.setdefault(family(name), {"tokens": 0, "rules": 0, "crimson_overrides": 0, "unused": 0})
        f["tokens"] += 1
        f["rules"] += reach
        f["crimson_overrides"] += int(row["crimson_overrides"])
        f["unused"] += int(reach == 0)
    top_unused = sorted(r["token"] for r in rows if r["rules"] == 0)
    summary = {"tokens_all": len(ix.defs), "colour_tokens": len(rows), "colour_tokens_used_by_a_rule": sum(1 for r in rows if r["rules"] > 0),
               "colour_tokens_unused": len(top_unused), "crimson_overrides_total": len(crimson_tokens),
               "crimson_overrides_that_are_colour_tokens": sum(1 for r in rows if r["crimson_overrides"]),
               "colour_tokens_not_overridden_by_crimson": sum(1 for r in rows if not r["crimson_overrides"]),
               "rules_reached_by_overridden_colour_tokens": sum(r["rules"] for r in rows if r["crimson_overrides"]),
               "rules_reached_by_all_colour_tokens": sum(r["rules"] for r in rows),
               "colour_tokens_in_conflict_between_sheets": sum(1 for r in rows if r["conflict"]),
               "families": len(fams)}
    out = {"note": "generated by tools/make_token_inventory.py from the style index; one row per colour token (a token whose reference value resolves to one colour). 'rules' counts the (sheet, selector, property) triples painted through the token, following aliases. Crimson overrides are the tokens the crimson preset overrides.",
           "game_build": ix.meta.get("game_build"), "summary": summary,
           "families": {k: fams[k] for k in sorted(fams)}, "tokens": rows}
    if crimson is not None:
        out["crimson_roles"] = crimson_roles(crimson, crimson_palette())
        out["literals"] = literal_inventory(ix, crimson)
    return out


def main():
    cfg = config.load()
    real = config.workspace(cfg)
    info = detect.describe(cfg["game_dir"]) if cfg.get("game_dir") else None
    meas = {"note": "S0 measurements, one machine, one run, offline; scratch workspace for everything that writes", "machine": "owner's PC"}
    ix = index_styles.load(real)
    assert ix is not None, "the real workspace has no style index (build it once with the CLI)"

    t = time.perf_counter(); crimson = PRESETS["crimson"](ix, "s0-crimson"); meas["crimson_built_in_memory_s"] = round(time.perf_counter() - t, 3)
    crimson_tokens = {e["token"] for e in crimson["token_overrides"]}

    scratch = Path(tempfile.mkdtemp(prefix="s0-scratch-"))
    try:
        sws = config.Workspace(scratch)
        if info:
            snap_dir = Path(scratch) / "vanilla"
            t = time.perf_counter()
            try:
                install.snapshot_vanilla(sws, info["aa_dir"], info.get("version"), force=True)
                meas["snapshot_copy_s"] = round(time.perf_counter() - t, 2)
                man = sws.vanilla_manifest()
                meas["snapshot_files"] = len(man["files"])
                meas["snapshot_mb"] = round(sum(f.stat().st_size for f in snap_dir.glob("*.bundle")) / 1e6, 1)
            except Exception as e:                    # a snapshot of a non-stock game folder may be refused; then the real snapshot copy is used
                meas["snapshot_copy_s"] = None
                meas["snapshot_error"] = str(e)[:300]
        if "snapshot_copy_s" not in meas or meas["snapshot_copy_s"] is None:
            sws = config.Workspace(scratch, vanilla_dir=real.vanilla)       # reads the real snapshot copy, writes the index cache to the scratch folder
            meas["index_built_from"] = "the real workspace's existing snapshot copy (read only)"
        else:
            meas["index_built_from"] = "the scratch snapshot just taken from the game folder"
        t = time.perf_counter(); built = index_styles.build(sws); meas["index_build_cold_s"] = round(time.perf_counter() - t, 2)
        meas["index_sheets"], meas["index_tokens"] = len(built.sheets), len(built.defs)
        t = time.perf_counter(); index_styles.load(sws); meas["index_load_warm_s"] = round(time.perf_counter() - t, 2)
        meas["index_cache_mb"] = round(index_styles.cache_path(sws, sws.vanilla_manifest()).stat().st_size / 1e6, 1)
        if info:                                           # the first render on an EMPTY cache: the render reads the game's layout bundles (read only) and writes its caches to the scratch folder
            from skin_editor.render.service import Renderer
            R = Renderer(Path(info["aa_dir"]), scratch / "cache", built)
            t = time.perf_counter(); lst = R.layout_list("", 200)["layouts"]; meas["render_layout_list_cold_s"] = round(time.perf_counter() - t, 2)
            pick = lst[0]
            t = time.perf_counter(); R.layout(pick["bundle"], pick["path_id"], 3, max_nodes=1000); meas["render_first_layout_cold_s"] = round(time.perf_counter() - t, 2)
            meas["render_first_layout"] = "%s (%d elements)" % (pick["name"], pick["elements"])
            t = time.perf_counter(); R.layout(pick["bundle"], pick["path_id"], 3, max_nodes=1000); meas["render_same_layout_again_s"] = round(time.perf_counter() - t, 2)
            fs = [f for f in (scratch / "cache").rglob("*") if f.is_file()]
            meas["render_cache_after_mb"], meas["render_cache_after_files"] = round(sum(f.stat().st_size for f in fs) / 1e6, 1), len(fs)
        inv = inventory(built, crimson_tokens, crimson)
    finally:
        shutil.rmtree(scratch, ignore_errors=True)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(inv, indent=1, sort_keys=False), encoding="utf-8", newline="\n")
    runs = []                                            # every run is kept: the timings vary from run to run, and a single number would hide that
    if MEAS.is_file():
        old = json.loads(MEAS.read_text(encoding="utf-8"))
        runs = old.get("runs", [old] if "index_build_cold_s" in old else [])
    meas["run"] = len(runs) + 1
    MEAS.write_text(json.dumps({"note": "S0 timings, the owner's PC, offline; a scratch workspace for everything that writes; one entry per run, none discarded", "runs": runs + [meas]}, indent=1), encoding="utf-8", newline="\n")
    print(json.dumps(inv["summary"], indent=1)); print(json.dumps(inv["literals"]["summary"], indent=1)); print(json.dumps(inv["crimson_roles"]["summary"], indent=1)); print(json.dumps(meas, indent=1))


if __name__ == "__main__":
    main()
