"""Live preview: a measured screen model (data/models/<screen>.json + .png, built on Windows by tools/build_preview_model.py)
evaluated against a project. Read-only: nothing here touches the game, the snapshot or the project.

Per region the model holds the vanilla colour the game resolved (measured) and its binding: the token the winning rule uses,
a colour literal, or code. The skin colour is:
  token    the alias chain followed with the project's token overrides (reverts dropped); literal swaps apply to the colour the
           chain ends on (a swap rewrites token definitions too). Unchanged when no override or swap touches the chain: then the
           measured colour is kept (the game may resolve a token from another sheet than the index's reference sheet).
  literal  the project's literal swaps (exact RGBA or RGB keeping alpha).
  code     never changed: the stylesheets do not paint it.
  scoped rules: approximate. A rule whose subject (last compound: type, classes, #name) matches the element and sets the region's
           property is taken to win (build raises its specificity); ancestors and pseudo-states are not checked, so such hits are
           marked approx."""
import json
import re

from . import club_colours, colour, config
from . import project as project_mod
from . import token_patch as tp

SCHEMA = "fm27se-preview/1"
VAR = re.compile(r"var\((--[\w-]+)\)$")
NAME = re.compile(r"[a-z0-9][a-z0-9-]{0,40}")
P_TYPE, P_CLASS, P_PSEUDO, P_NAME = 2, 3, 4, 6


def models_dir():
    return config.resource_root() / "data" / "models"


def models():
    d = models_dir()
    out = []
    for p in sorted(d.glob("*.json")) if d.is_dir() else []:
        try:
            m = json.loads(p.read_text(encoding="utf-8"))
        except ValueError:
            continue
        if m.get("schema") != SCHEMA:
            continue
        kinds = {}
        for r in m["regions"]:
            kinds[r["binding"]["kind"]] = kinds.get(r["binding"]["kind"], 0) + 1
        out.append({"name": p.stem, "resolution": m["resolution"], "game_build": m.get("game_build"),
                    "measured_state": m.get("measured_state"), "regions": len(m["regions"]), "kinds": kinds,
                    "has_image": (d / m.get("screenshot", p.stem + ".png")).is_file()})
    return out


def load(name):
    if not NAME.fullmatch(str(name or "")):
        raise KeyError("bad model name")
    p = models_dir() / (name + ".json")
    if not p.is_file():
        raise KeyError("no such preview model: " + name)
    m = json.loads(p.read_text(encoding="utf-8"))
    if m.get("schema") != SCHEMA:
        raise KeyError("model %s is not %s" % (name, SCHEMA))
    return m


def image(name):
    m = load(name)
    p = models_dir() / m["screenshot"]
    if p.parent != models_dir() or not p.is_file():
        raise KeyError("no screenshot for " + name)
    return p.read_bytes()


# ---------------------------------------------------------------- evaluation
class Skin:
    """The project's colour-relevant entries, prepared once."""

    def __init__(self, index, project):
        self.index = index
        p = project_mod.validate(project_mod.migrate(project)) if project else None
        spec = project_mod.to_spec(p) if p else {"tokens": {}, "literal_map": {}, "rgba_swaps": [], "append_rules_by_sheet": {}}
        opts = (p or {}).get("options", {})
        self.club_off = opts.get("club_colours", True) is False
        self.club_colour = colour.from_obj(opts.get("club_colours_replacement", project_mod.CLUB_DEFAULT))
        # the generated club rules are previewed through club_region(), not by subject matching (their subjects are broad)
        club_sel = {r["selector"] for r in club_colours.rules(project_mod.CLUB_DEFAULT)} if self.club_off else set()
        self.tokens = spec["tokens"]
        self.rgb_map = {k.upper(): v.upper() for k, v in spec["literal_map"].items()}
        self.rgba = [(tuple(f), tuple(t)) for _, f, t in spec["rgba_swaps"]]
        self.rules = []
        for sheet, rules in spec["append_rules_by_sheet"].items():
            for r in rules:
                if r["selector"] not in club_sel:
                    self.rules.append((sheet, r["selector"], r["props"]))

    def club_region(self, region):
        """With the option "club colours: remove": the colour this club-painted region gets, else None."""
        if not self.club_off or not club_colours.is_club_region(region):
            return None
        cls = set(region.get("classes") or [])
        name = region.get("label", "").split("#", 1)[1].split(".", 1)[0] if "#" in region.get("label", "") else ""
        if region["prop"].startswith("border-") or name in ("HomeColour", "AwayColour") or cls & {"fm-club-primary-color", "fm-club-secondary-color"}:
            return (0, 0, 0, 0.0)                    # kit strip images (opacity 0) and the club outline (transparent)
        return self.club_colour

    def swap(self, c):
        """Literal swaps on one colour. Returns (colour, changed)."""
        for f, t in self.rgba:
            if colour.same(c, f):
                return t, True
        new = self.rgb_map.get(colour.hex6(c).upper())
        if new:
            n = colour.parse(new)
            return (n[0], n[1], n[2], c[3]), True
        return c, False

    def token(self, name):
        """(colour or None, touched, chain). Follows aliases with overrides; a cycle or a non-colour end gives None."""
        chain, touched = [name], False
        while True:
            cur = chain[-1]
            if cur in self.tokens:
                v, touched = self.tokens[cur], True
            else:
                v = self.index.value(cur) if self.index else None
            if v is None:
                return None, touched, chain
            m = VAR.match(v.strip())
            if m:
                if m.group(1) in chain:
                    return None, touched, chain + [m.group(1)]
                chain.append(m.group(1))
                continue
            c = colour.parse(v.strip())
            if c is None:
                return None, touched, chain
            c2, swapped = self.swap(c)
            return c2, touched or swapped, chain

    def gradient_rule(self, classes):
        """For an SIGradient with custom styles: the value text of --start-colour and --end-colour from the strongest stylesheet
        rule whose subject classes the element carries (no pseudo-state; ancestors not checked: approx). Cached per class set."""
        key = tuple(sorted(classes))
        if not hasattr(self, "_grad"):
            self._grad = {}
        if key in self._grad:
            return self._grad[key]
        cls, best = set(classes), {}
        for sh in (self.index.sheets if self.index else []):
            for k, r in enumerate(sh["rules"]):
                props = {name: val for name, val, _ in r["p"] if name in ("--start-colour", "--end-colour")}
                if not props:
                    continue
                for sel in r["s"]:
                    for chain in tp.parse_selector(sel):
                        parts = chain[-1][1]
                        if not parts or any(t_ == P_PSEUDO for t_, _ in parts) or not all(t_ == P_CLASS and v in cls for t_, v in parts):
                            continue
                        rank = (tp.specificity(chain), k)
                        for name, val in props.items():
                            if name not in best or rank >= best[name][0]:
                                best[name] = (rank, val.strip(), sel, sh["name"])
        out = {n: {"value": v[1], "selector": v[2], "sheet": v[3]} for n, v in best.items()}
        self._grad[key] = out
        return out

    def value(self, text):
        """(colour or None, touched, chain) for a rule value: var(--x) through the overrides, or a literal through the swaps."""
        m = VAR.match(text.strip())
        if m:
            return self.token(m.group(1))
        c = colour.parse(text.strip())
        if c is None:
            return None, False, None
        c2, sw = self.swap(c)
        return c2, sw, None

    def scoped(self, region):
        """Last matching scoped rule for this region's element and property: (value text, rule) or None."""
        hit = None
        label = region.get("label", "")
        typ = re.split(r"[#.]", label, 1)[0]
        nm = label.split("#", 1)[1].split(".", 1)[0] if "#" in label else ""
        classes = set(region.get("classes") or [])
        for sheet, sel, props in self.rules:
            if region["prop"] not in props:
                continue
            for chain in tp.parse_selector(sel):
                parts = chain[-1][1]
                if any(t == P_PSEUDO for t, _ in parts):
                    continue
                ok = all((t == P_CLASS and v in classes) or (t == P_TYPE and v == typ) or (t == P_NAME and v == nm)
                         or t not in (P_CLASS, P_TYPE, P_NAME) for t, v in parts)
                if ok and parts:
                    hit = (props[region["prop"]], {"sheet": sheet, "selector": sel})
                    break
        return hit


def _hex(c):
    return colour.hex8(c).upper()


def evaluate(model, index, project):
    """Regions with 'vanilla' (measured) and 'skin' colours (#RRGGBBAA), 'changed', and 'why'. Plus the tokens bound on this screen."""
    skin, vskin = Skin(index, project), Skin(index, None)
    out, screen_tokens = [], {}
    for r in model["regions"]:
        b = r["binding"]
        if r["prop"] == "gradient":
            out.append(_gradient(skin, vskin, r, screen_tokens))
            continue
        van = colour.parse(r["colour"])
        new, why, approx, chain_out = van, "", False, None
        if b["kind"] == "token":
            screen_tokens[b["token"]] = screen_tokens.get(b["token"], 0) + 1
            c, touched, chain = skin.token(b["token"])
            chain_out = chain
            if touched and c is not None:
                new, why = c, "token " + " -> ".join(chain)
            elif touched:
                why = "token %s no longer resolves to one colour (shown unchanged)" % " -> ".join(chain)
        elif b["kind"] == "literal":
            c = colour.parse(b["value"])
            if c is not None:
                c2, ch = skin.swap(c)
                if ch:
                    new, why = c2, "literal swap " + _hex(c)
        sc = None if b.get("why", "").startswith("inline") else skin.scoped(r)      # an inline (code) value beats any rule
        if sc:
            v, rule = sc
            text = project_mod.patch_text(v) if not isinstance(v, str) else v
            m = VAR.match(text.strip())
            c = skin.token(m.group(1))[0] if m else colour.parse(text.strip())
            if c is not None:
                new, why, approx = c, "scoped rule %s (approx: subject match only)" % rule["selector"], True
        cc = skin.club_region(r)
        if cc is not None:
            new, why, approx = cc, "club colours removed (project option)", True
        changed = not colour.same(new, van)
        out.append({"id": r["id"], "order": r["order"], "prop": r["prop"], "rect": r["rect"], "label": r["label"], "text": r.get("text", ""),
                    "binding": b, "chain": chain_out, "vanilla": _hex(van), "skin": _hex(new), "changed": changed, "why": why if changed else "", "approx": approx and changed,
                    "opacity": r.get("opacity", 1), **({"sample_ok": r["sample_ok"]} if "sample_ok" in r else {})})
    return {"screen": model["screen"], "resolution": model["resolution"], "game_build": model.get("game_build"),
            "measured_state": model.get("measured_state"), "regions": out,
            "changed": sum(x["changed"] for x in out), "screen_tokens": sorted(screen_tokens, key=lambda t: -screen_tokens[t])}


def _near(a, b, tol=2):
    """Two colours within tol per byte (RGB and the alpha byte)."""
    if a is None or b is None:
        return False
    byt = lambda c: [int(round(v)) for v in c[:3]] + [colour.unit_to_byte(c[3])]
    return all(abs(x - y) <= tol for x, y in zip(byt(a), byt(b)))


def _gradient(skin, vskin, r, screen_tokens):
    """An SIGradient region: both ends evaluated like a property each (start, end). The rule is found by subject classes only,
    so an end is trusted (and repainted) only when the rule's vanilla value resolves to the colour the game showed."""
    ends, info = {}, {}
    rule = skin.gradient_rule(r.get("classes") or []) if r["binding"]["kind"] == "gradient" else {}
    for end, prop, measured in (("start", "--start-colour", r["colour"]), ("end", "--end-colour", r["end"])):
        van = colour.parse(measured)
        new, chain, why = van, None, ""
        ru = rule.get(prop)
        if ru and not _near(vskin.value(ru["value"])[0], van):
            why_skip = "%s: the matched rule %s gives %s in vanilla, the game showed %s: not trusted" % (
                end, ru["selector"], _hex(vskin.value(ru["value"])[0]) if vskin.value(ru["value"])[0] else ru["value"], _hex(van))
            info[end] = why_skip
            ru = None
        if ru:
            m = VAR.match(ru["value"])
            if m:
                screen_tokens[m.group(1)] = screen_tokens.get(m.group(1), 0) + 1
            c, touched, chain = skin.value(ru["value"])
            if touched and c is not None:
                new, why = c, "%s %s: %s" % (end, prop, " -> ".join(chain) if chain else "literal swap")
        sc = skin.scoped(dict(r, prop=prop)) if r["binding"]["kind"] == "gradient" else None
        if sc:
            v, sr = sc
            c = skin.value(project_mod.patch_text(v) if not isinstance(v, str) else v)[0]
            if c is not None:
                new, why = c, "%s: scoped rule %s (approx)" % (end, sr["selector"])
        cc = skin.club_region(r)
        if cc is not None:
            new, why = cc, "club colours removed (project option)"
        ends[end] = (van, new, chain, why, ru)
    changed = any(not colour.same(v, n) for v, n, *_ in ends.values())
    b = dict(r["binding"])
    trusted = {e: ends[e][4] for e in ends if ends[e][4]}
    if trusted:
        b.update({"start": trusted.get("start"), "end": trusted.get("end")})
    elif b["kind"] == "gradient":
        b = {"kind": "code", "why": "; ".join(info.values()) or "no stylesheet rule sets --start-colour / --end-colour for these classes"}
    return {"id": r["id"], "order": r["order"], "prop": "gradient", "rect": r["rect"], "label": r["label"], "text": "",
            "binding": b, "direction": r.get("direction", "LeftToRight"),
            "chain": (ends["start"][2] or []) + (ends["end"][2] or []) or None, "chain_start": ends["start"][2], "chain_end": ends["end"][2],
            "vanilla": _hex(ends["start"][0]), "skin": _hex(ends["start"][1]), "vanilla_end": _hex(ends["end"][0]), "skin_end": _hex(ends["end"][1]),
            "changed": changed, "why": "; ".join(x[3] for x in ends.values() if x[3]) if changed else "", "approx": changed,
            "opacity": r.get("opacity", 1)}


def suggest(model, index, rgb, limit=8):
    """Tokens that paint on this screen, nearest first to an RGB colour (for code or literal regions)."""
    target = colour.parse(rgb)
    if target is None:
        raise ValueError("bad colour")
    seen = {}
    for r in model["regions"]:
        b = r["binding"]
        if b["kind"] == "token" and b["token"] not in seen:
            c = colour.parse(r["colour"])
            seen[b["token"]] = c
    rows = sorted(((sum((a - b) ** 2 for a, b in zip(c[:3], target[:3])) ** 0.5, t, c) for t, c in seen.items()), key=lambda x: x[0])
    return [{"token": t, "colour": _hex(c), "distance": round(d, 1)} for d, t, c in rows[:limit]]


def verify_regions(evaluated, min_side=12):
    """Regions a centre sample can judge: opaque background fills, big enough, that the model builder confirmed on the measured
    screenshot (sample_ok: the centre shows the region's own colour, not text, an icon or a child). Models without that flag fall back to
    'centre not covered by a later background region'. In the format verify.compare reads."""
    bgs = [r for r in evaluated["regions"] if r["prop"] == "background-color"]
    flagged = any("sample_ok" in r for r in bgs)
    out = []
    for i, r in enumerate(bgs):
        x, y, w, h = r["rect"]
        if w < min_side or h < min_side or colour.parse(r["skin"])[3] < 0.999 or colour.parse(r["vanilla"])[3] < 0.999 or r.get("opacity", 1) < 0.999:
            continue
        if flagged:
            if not r.get("sample_ok"):
                continue
        else:
            cx, cy = x + w / 2, y + h / 2
            if any(o["order"] > r["order"] and o["rect"][0] <= cx <= o["rect"][0] + o["rect"][2] and o["rect"][1] <= cy <= o["rect"][1] + o["rect"][3]
                   for o in bgs[i + 1:]):
                continue
        out.append({"id": r["id"], "rect": r["rect"], "expected": r["skin"][:7], "vanilla": r["vanilla"][:7],
                    "code_driven": r["binding"]["kind"] == "code", "entry": r["why"] or None})
    return {"screen": evaluated["screen"], "resolution": evaluated["resolution"], "regions": out}
