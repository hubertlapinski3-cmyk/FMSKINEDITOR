"""S4 of the Simple mode plan: the role map a three-colour theme is generated from. Writes data/simple/roles.json. Offline; the index is only read.

    python tools/make_role_map.py

Two sources, both read, none typed:
- the Crimson preset (proven in game in its bundle form): its palette (read from the preset's own code) and the value it gives each token. A token whose Crimson colour has the
  RGB of a step of one of three ramps (neutral, accent = Crimson's crimson ramp, text) becomes an entry: that ramp, that step, Crimson's alpha. Every other token Crimson overrides is
  KEPT at the game's own colour (hue families, data scales, ratings, mixes: three input colours cannot derive them), and listed with the reason.
- the game's usage (the style index): only tokens some rule uses are mapped (S0: the 741 unused stay out), and each entry carries its rule count.
The ramp references are the steps of three anchor tokens in Crimson: the page background (`--global-background`), the primary accent (`--brand-theme-primary`) and the primary text
(`--global-text-primary`). Every entry is "unverified" until Session 2 has looked at a generated theme in the game."""
import importlib.util
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
OUT = ROOT / "data" / "simple" / "roles.json"
ANCHORS = {"neutral": "--global-background", "accent": "--brand-theme-primary", "text": "--global-text-primary"}
# Entries added by an owner decision, outside the Crimson-ramp rule above; each says why and what is not known.
ADDED = [
    {"token": "--data-player-position-defender-foreground", "ramp": "text", "step": "t-1", "a": 1.0,
     "decision": "S4 amendment, owner decision 2 (2026-11-15): the defender badge pair blocks, so the theme sets the badge label",
     "why": "the game's own label colour reads at 4.41 to 1 on its fill (minimum 4.5); the theme's primary text replaces it, and the fill keeps the game's teal so positions keep their colours. "
            "NOT ANCHORED in Crimson: Crimson sets this label to its teal Light (#8AD9CD), which is on none of the three ramps, so the reproduction test does not cover this entry. "
            "VISIBILITY UNKNOWN: no style rule of this build uses this token (reach 0) and no token refers to it; whether it paints the badge (game code may read it while running) is for Session 2 to observe with fm_get_styles; if it does not, the entry comes out."},
]


def crimson_palette():
    spec = importlib.util.spec_from_file_location("make_token_inventory", ROOT / "tools" / "make_token_inventory.py")
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
    return m.crimson_palette()


def ramps_of(cr):
    def pick(rx):
        return {k[len("--cr-"):]: v.upper()[:7] for k, v in cr.items() if re.fullmatch(rx, k[len("--cr-"):]) and len(v) == 7}
    neutral = pick(r"n-\d+")
    accent = pick(r"c-\d+")
    text = pick(r"t-(1|2|muted)|white")
    return {"neutral": neutral, "accent": accent, "text": text}


def game_values(ix, pairs):
    """The game's own value of every game token the contrast pairs name (as #RRGGBBAA), so the check can be repeated without the game (tests, CI). Recorded from this build's index."""
    from skin_editor import colour
    out = {}
    for pr in pairs:
        for tok in (pr["fg"], pr["bg"]):
            if tok.startswith("--cr-") or tok in out or tok not in ix.defs:
                continue
            r = ix.token_row(tok)["resolved"]
            if r:
                out[tok] = colour.hex8(colour.from_obj(r))
    return dict(sorted(out.items()))


def build(ix, crimson_project, cr):
    ramps = ramps_of(cr)
    by_rgb = {}
    for ramp in ("text", "accent", "neutral"):                    # first claim wins: white is the text ramp's, not an overlay
        for step, rgb in ramps[ramp].items():
            by_rgb.setdefault(rgb, (ramp, step))
    used = {n: ix.token_row(n)["reach"] for n in ix.defs}
    entries, kept = [], []
    for o in crimson_project["token_overrides"]:
        v = o["value"]
        if not isinstance(v, dict) or used.get(o["token"], 0) == 0:
            continue
        rgb = v["rgb"].upper()
        hit = by_rgb.get(rgb)
        if hit:
            entries.append({"token": o["token"], "ramp": hit[0], "step": hit[1], "a": v["a"], "crimson": "%s a=%s" % (rgb, round(v["a"], 3)), "rules": used[o["token"]], "status": "unverified"})
        else:
            kept.append({"token": o["token"], "crimson": "%s a=%s" % (rgb, round(v["a"], 3)), "rules": used[o["token"]], "why": "not on the neutral, accent or text ramp (a hue family, a data scale, a rating or a mix): three input colours cannot derive it, so the game's own colour stays"})
    crim = {o["token"]: o["value"] for o in crimson_project["token_overrides"] if isinstance(o["value"], dict)}
    for add in ADDED:
        assert add["token"] in ix.defs, "an added entry must exist in this build: " + add["token"]
        assert add["step"] in ramps[add["ramp"]]
        kept = [k for k in kept if k["token"] != add["token"]]
        c = crim.get(add["token"])
        entries.append({**add, "crimson": "%s a=%s" % (c["rgb"].upper(), round(c["a"], 3)) if c else None, "anchor": "none",
                        "rules": used.get(add["token"], 0), "status": "unverified"})
    roles = {r["token"]: r for r in entries}
    refs = {}
    for ramp, tok in ANCHORS.items():
        assert tok in roles and roles[tok]["ramp"] == ramp, "the anchor %s is not on the %s ramp" % (tok, ramp)
        refs[ramp] = roles[tok]["step"]
    entries.sort(key=lambda r: (r["ramp"], r["token"]))
    kept.sort(key=lambda r: r["token"])
    reach_all = set()
    for n, c in used.items():
        if c and ix.token_row(n)["resolved"]:
            reach_all |= ix.reach(n)
    reach_mapped = set()
    for r in entries:
        reach_mapped |= ix.reach(r["token"])
    return {
        "note": "Generated by tools/make_role_map.py from the crimson preset's palette and token values and the style index. Every entry is UNVERIFIED until Session 2 has looked at a generated theme in the game.",
        "status": "unverified",
        "anchors": ANCHORS, "references": refs,
        "ramps": ramps,
        "entries": entries, "kept": kept,
        "summary": {"entries": len(entries), "kept": len(kept), "added_by_decision": len(ADDED), "by_ramp": {k: sum(1 for r in entries if r["ramp"] == k) for k in ramps},
                    "rule_paths_reached_by_entries": len(reach_mapped), "rule_paths_reached_by_all_used_colour_tokens": len(reach_all)},
        "contrast_pairs": [{"fg": p["fg"], "bg": p["bg"]} for p in crimson_project["contrast_pairs"]],
        "game_values": game_values(ix, crimson_project["contrast_pairs"] + [{"fg": "--global-background", "bg": "--global-background"}]),
        "contrast_minimum": 4.5,
        "modes": ["dark"],
        "modes_note": "S4 amendment, owner decision 1 (2026-11-15): light is out of 1.2.0. The role map comes from a dark preset; light themes fail on the surfaces it keeps at the game's own colour; extending the map for light themes is later work, not 1.2.0.",
    }


def main():
    from skin_editor import config, index_styles
    from skin_editor.presets import PRESETS
    ix = index_styles.load(config.workspace(config.load()))
    assert ix is not None, "build the style index first"
    data = build(ix, PRESETS["crimson"](ix, "role-map"), crimson_palette())
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(data, indent=1), encoding="utf-8", newline="\n")
    print(json.dumps(data["summary"], indent=1)); print("references:", data["references"])


if __name__ == "__main__":
    main()
