"""Simple mode's engine helpers (docs/SIMPLE-MODE-PLAN.md, S3). They return counts, never a picture of the game.

token_screens: on how many of the measured screens the shipped models hold an area painted by a token. Computed from the models in data/models (the regions measured on eight
screens) by asking what a probe override of the token changes: the count the S3 wording quotes ("used on N of the 8 measured screens we have models for"). It UNDERCOUNTS by design:
a model holds only the areas that were measured, so 0 means "not in an area we measured", never "nothing changes".

literal_info: what a literal colour swap would cost in a native skin: how many game rules use exactly this colour (each is copied into the skin), how many selectors, and whether
Simple mode offers it (more than 0 and at most LITERAL_LIMIT copied rules, the limit the owner approved)."""
from . import preview, project as project_mod

LITERAL_LIMIT = 50
PROBE = {"rgb": "#FE01FE", "a": 1.0}          # a colour no game token uses, so any region it reaches shows as changed
_screens_cache = {}


def token_screens(ix, token):
    key = (id(ix), token)
    if key in _screens_cache:
        return _screens_cache[key]
    p = project_mod.new("simple-probe")
    p["token_overrides"] = [{"token": token, "value": dict(PROBE)}]
    p = project_mod.validate(project_mod.migrate(p))
    names, regions = [], {}
    models = preview.models()
    for m in models:
        ev = preview.evaluate(preview.load(m["name"]), ix, p)
        n = sum(1 for r in ev["regions"] if r["changed"])
        regions[m["name"]] = n
        if n:
            names.append(m["name"])
    out = {"token": token, "screens": len(names), "of": len(models), "names": names, "regions": regions}
    _screens_cache[key] = out
    return out


def literal_info(ix, rgb, a):
    """Matched by the alpha BYTE (a colour shown as #RRGGBBAA has lost the alpha's last decimals), then by the exact alpha the game's rules carry: `a_exact` is that value, and a
    swap must use it as its `from`, because the native export copies only the rules whose alpha equals it exactly. When two exact alphas share one byte, the one with more uses wins."""
    from . import colour
    c = colour.from_obj({"rgb": rgb, "a": float(a)})
    byte = colour.unit_to_byte(c[3])
    groups = {}
    for h in ix.by_rgb.get(colour.hex6(c), []) if hasattr(ix, "by_rgb") else ix.literal(colour.hex6(c), c[3])["exact"]:
        if h.get("token_def") or colour.unit_to_byte(h.get("a", c[3])) != byte:
            continue
        groups.setdefault(h.get("a", c[3]), []).append(h)
    a_exact, uses = max(groups.items(), key=lambda kv: len(kv[1])) if groups else (c[3], [])
    return {"rgb": colour.hex6(c), "a": c[3], "a_exact": a_exact, "uses": len(uses), "selectors": len({s for h in uses for s in h["selectors"]}),
            "copied_rules": len(uses), "limit": LITERAL_LIMIT, "offered": 0 < len(uses) <= LITERAL_LIMIT}
