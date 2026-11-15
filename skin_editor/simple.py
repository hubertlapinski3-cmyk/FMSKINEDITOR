"""Simple mode's engine helpers (docs/SIMPLE-MODE-PLAN.md, S3). They return counts, never a picture of the game.

token_screens: on how many of the measured screens the shipped models hold an area painted by a token. Computed from the models in data/models (the regions measured on eight
screens) by asking what a probe override of the token changes: the count the S3 wording quotes ("used on N of the 8 measured screens we have models for"). It UNDERCOUNTS by design:
a model holds only the areas that were measured, so 0 means "not in an area we measured", never "nothing changes".

literal_info: what a literal colour swap would cost in a native skin: how many game rules use exactly this colour (each is copied into the skin), how many selectors, and whether
Simple mode offers it (more than 0 and at most LITERAL_LIMIT copied rules, the limit the owner approved)."""
from . import preview, project as project_mod

LITERAL_LIMIT = 50
# S6: the wallpaper place a layout Look at it can draw is known to show (measured by tools/check_s6_pictures.py: the Squad screen's `.base-layer-content` takes the picture).
# The other places sit on screens no measured layout covers yet; Simple mode says so instead of suggesting a layout it has not checked.
LOOK_AT = {"main-screens": {"name": "SquadScreen", "label": "Squad screen"}}


def picture_catalog(rows, classes):
    """The game's pictures a NATIVE skin can replace, for Simple mode's Pictures (S6): every wallpaper (painted on the places the person ticks) and every icon or SVG a USS class
    draws (the others are placed in code and only the bundle route reaches them, so they are left out and counted). Each wallpaper carries its default places."""
    from . import native
    out, left = [], 0
    for r in rows:
        if r["kind"] == "texture":
            out.append({"kind": "wallpaper", "game_kind": "texture", "bundle": r["bundle"], "path_id": str(r["path_id"]), "name": r["name"], "w": r.get("w"), "h": r.get("h"),
                        "group": r.get("group", ""), "where_default": native.default_places(r["name"])})
        elif classes.get(("icon", r["name"]) if r["kind"] == "icon" else ("svg", str(r["path_id"]))):
            out.append({"kind": "icon", "game_kind": r["kind"], "bundle": r["bundle"], "path_id": str(r["path_id"]), "name": r["name"], "w": r.get("w"), "h": r.get("h"), "group": r.get("group", "")})
        else:
            left += 1
    return {"rows": out, "counts": {"wallpapers": sum(1 for r in out if r["kind"] == "wallpaper"), "icons": sum(1 for r in out if r["kind"] == "icon"), "left_out": left},
            "places": {k: v[0] for k, v in native.PLACES.items()}, "look_at": LOOK_AT}
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
