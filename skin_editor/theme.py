"""A theme from three colours (docs/SIMPLE-MODE-PLAN.md, S4): a background, an accent and a text colour, turned into DARK-theme token overrides through the role map
(data/simple/roles.json, made by tools/make_role_map.py from the Crimson preset's ramps and the game's usage).
Light themes are out of 1.2.0 (S4 amendment, owner decision 1): the map comes from a dark preset and light themes fail on the surfaces it keeps; `generate` refuses them.

How a value is made, for an entry on ramp R at step k (R's reference step is ref, the input for R is X):
    lightness  L = L(X) + (L(k) - L(ref))
    hue        H = H(X) + (H(k) - H(ref))
    saturation S = S(X) * S(k) / S(ref)                (S(X) when the reference has none)
    alpha      the alpha Crimson gives that token
so the inputs equal to Crimson's own reference colours reproduce Crimson's values (pinned by a test; an entry marked `anchor: none`, added by an owner decision, is not on
Crimson's ramps and is not covered by that test). Tokens the map KEEPS are not written: they stay the game's own colour.

The contrast check runs on every generated theme at the moment it is made: Crimson's own 43 foreground / background pairs, the minimum ratio 4.5, colours with transparency
composited over the page background first. A failing pair is reported as a finding; no colour is adjusted to make it pass, and `create` refuses to write a failing theme.
Every generated entry is "unverified" until Session 2 has looked at the theme in the game."""
import colorsys
import json
from pathlib import Path

from . import config, colour
from . import project as project_mod

MIN = 4.5
_roles = None


def roles():
    global _roles
    if _roles is None:
        _roles = json.loads((config.resource_root() / "data" / "simple" / "roles.json").read_text(encoding="utf-8"))
    return _roles


def recorded_game_value(token, rm=None):
    """The game's own value of a token as the role map recorded it from the index (for the contrast check without the game: tests and CI)."""
    v = (rm or roles()).get("game_values", {}).get(token)
    return colour.parse(v) if v else None


def gallery():
    return json.loads((config.resource_root() / "data" / "simple" / "gallery.json").read_text(encoding="utf-8"))["themes"]


def _hls(hex6):
    r, g, b = (int(hex6[i:i + 2], 16) / 255 for i in (1, 3, 5))
    return colorsys.rgb_to_hls(r, g, b)


def _hex(h, l, s):
    r, g, b = colorsys.hls_to_rgb(h % 1.0, min(1.0, max(0.0, l)), min(1.0, max(0.0, s)))
    return "#%02X%02X%02X" % tuple(int(round(v * 255)) for v in (r, g, b))


def _norm(x):
    x = x.strip().upper()
    if not (len(x) == 7 and x[0] == "#" and all(c in "0123456789ABCDEF" for c in x[1:])):
        raise ValueError("a theme colour must be #RRGGBB: %r" % x)
    return x


def generate(background, accent, text, mode="dark", rm=None):
    """-> {"overrides": [{token, value: {rgb, a}, ramp, step, status}], "kept": n, "inputs": {...}}. Pure: no index, no files beyond the role map."""
    rm = rm or roles()
    if mode == "light":
        raise ValueError("light themes are not in this version: the role map comes from a dark preset")
    if mode != "dark":
        raise ValueError("mode must be dark")
    inputs = {"neutral": _norm(background), "accent": _norm(accent), "text": _norm(text)}
    s = 1.0
    out = []
    for e in rm["entries"]:
        ramp = e["ramp"]
        k, ref, x = _hls(rm["ramps"][ramp][e["step"]]), _hls(rm["ramps"][ramp][rm["references"][ramp]]), _hls(inputs[ramp])
        h = x[0] + (k[0] - ref[0])
        l = x[1] + s * (k[1] - ref[1])
        sat = x[2] * (k[2] / ref[2]) if ref[2] > 1e-9 else x[2]
        out.append({"token": e["token"], "value": {"rgb": _hex(h, l, sat), "a": e["a"]}, "ramp": ramp, "step": e["step"], "status": "unverified"})
    return {"overrides": out, "kept": len(rm["kept"]), "inputs": {"background": inputs["neutral"], "accent": inputs["accent"], "text": inputs["text"], "mode": mode}}


def _lum(rgb):
    def lin(v):
        c = v / 255
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    return 0.2126 * lin(rgb[0]) + 0.7152 * lin(rgb[1]) + 0.0722 * lin(rgb[2])


def ratio(fg, bg):
    a, b = _lum(fg), _lum(bg)
    return (max(a, b) + 0.05) / (min(a, b) + 0.05)


def _step_value(gen, step, rm):
    """The generated colour of a ramp step (for Crimson's `--cr-<step>` pair names), or None when the step is on no ramp."""
    for ramp, steps in rm["ramps"].items():
        if step in steps:
            one = generate(gen["inputs"]["background"], gen["inputs"]["accent"], gen["inputs"]["text"], gen["inputs"]["mode"],
                           rm={**rm, "entries": [{"token": "--cr-" + step, "ramp": ramp, "step": step, "a": 1.0}]})
            return colour.from_obj(one["overrides"][0]["value"])
    return None


def contrast(gen, game_value, rm=None):
    """Crimson's 43 pairs on the generated theme. game_value(token) -> (r, g, b, a) or None, for the tokens the theme does not write.
    A pair is TOUCHED when the theme writes one of its colours (a token it overrides, or a `--cr-<step>` of a ramp): a touched pair under the minimum is a FAILURE and blocks the theme.
    A pair whose colours the theme does not write, and that is not seen through transparency over the generated page, measures the game's own colours: under the minimum it is reported in `game_failures`, a finding about the game, and does not block.
    `game_low`: every pair that is under the minimum in the game's OWN colours (both colours plain game values), with the theme's ratio and whether the theme corrects it.
    -> {minimum, pairs, checked, failures, game_failures, game_low, unchecked, rows}"""
    rm = rm or roles()
    mine = {o["token"]: colour.from_obj(o["value"]) for o in gen["overrides"]}

    def val(tok):
        if tok in mine:
            return mine[tok], True
        if tok.startswith("--cr-"):
            v = _step_value(gen, tok[len("--cr-"):], rm)
            return v, v is not None
        return game_value(tok), False
    page = val("--global-background")[0]
    rows, failures, game_failures, unchecked = [], [], [], []
    for pr in rm["contrast_pairs"]:
        (fg, tf), (bg, tb) = val(pr["fg"]), val(pr["bg"])
        if fg is None or bg is None or page is None:
            unchecked.append({"fg": pr["fg"], "bg": pr["bg"], "why": "a colour of this pair is not a plain colour (a palette family or a value the index cannot resolve)"})
            continue
        under = colour.composite(bg, page[:3]) if bg[3] < 1 else bg[:3]
        top = colour.composite(fg, under) if fg[3] < 1 else fg[:3]
        r = round(ratio(top, under), 2)
        page_written = "--global-background" in mine
        touched = tf or tb or (page_written and (bg[3] < 1 or fg[3] < 1))      # a transparent colour is seen over the generated page: the theme changes that pair too
        row = {"fg": pr["fg"], "bg": pr["bg"], "ratio": r, "pass": r >= rm["contrast_minimum"], "touched": touched}
        rows.append(row)
        if not row["pass"]:
            (failures if row["touched"] else game_failures).append(row)
    game_low = []
    gpage = game_value("--global-background")
    for row in rows:
        gf, gb = game_value(row["fg"]), game_value(row["bg"])
        if gf is None or gb is None or gpage is None:
            continue
        under = colour.composite(gb, gpage[:3]) if gb[3] < 1 else gb[:3]
        top = colour.composite(gf, under) if gf[3] < 1 else gf[:3]
        g = round(ratio(top, under), 2)
        if g < rm["contrast_minimum"]:
            game_low.append({"fg": row["fg"], "bg": row["bg"], "game_ratio": g, "ratio": row["ratio"], "corrected": row["touched"] and row["pass"]})
    return {"minimum": rm["contrast_minimum"], "pairs": len(rm["contrast_pairs"]), "checked": len(rows), "failures": failures, "game_failures": game_failures,
            "game_low": game_low, "unchecked": unchecked, "rows": rows}


def project_for(name, gen, keep_club_colours=True, game_build=None):
    p = project_mod.new(name, game_build)
    p["options"]["output"] = "native"
    if keep_club_colours is False:
        p["options"]["club_colours"] = False
    p["token_overrides"] = [{"token": o["token"], "value": o["value"], "note": "generated theme (%s %s), unverified" % (o["ramp"], o["step"])} for o in gen["overrides"]]
    return p
