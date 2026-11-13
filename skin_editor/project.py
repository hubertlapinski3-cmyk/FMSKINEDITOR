"""Skin project files (*.skin.json), mapped onto the token_patch.py spec.

Schema 2. Every single-colour value is the canonical object {"rgb": "#RRGGBB", "a": <float 0..1>}; the alpha
is stored as given, never rounded. Other values (var(--x), 12px, keywords, multi-value shorthands) stay strings.
Schema 1 files (colour strings, RGB-only literal swaps) are migrated on load: #RRGGBB becomes alpha 1.0,
#RRGGBBAA becomes alpha byte/255, literal swaps become mode "rgb-keep-alpha"."""
import copy
import json
import re
from pathlib import Path

from . import club_colours, colour, images
from . import token_patch as tp

SCHEMA = 2
KEYS = {"schema", "name", "game_build", "vanilla_manifest", "options", "token_overrides", "literal_swaps",
        "scoped_rules", "rename_classes", "contrast_pairs", "tile_placement", "reverts", "image_swaps", "native_sheets", "native_support", "native_name",
        "layout_patches", "font_swaps", "table_patches"}
FONT_FILE = re.compile(r"[A-Za-z0-9][\w.-]{0,100}\.(?:ttf|otf)", re.I)
OPTION_KEYS = {"flatten_gradients", "skip_sheets", "raise_specificity", "contrast_backdrop", "club_colours", "club_colours_replacement", "output"}
OUTPUTS = ("bundles", "native")                    # how the skin reaches the game: patched game bundles, or a native skin folder
CLUB_DEFAULT = {"rgb": "#171717", "a": 1.0}
RULE_KEYS = {"sheet", "selector", "props", "why", "note", "on", "op", "remove"}   # op: replace | remove edit the game's own rule in place (bundle target)
MODES = ("rgba", "rgb-keep-alpha")
NAME_RE = re.compile(r"[A-Za-z0-9][\w.-]{0,63}")
IDENT = re.compile(r"[A-Za-z_][\w-]*")
LITERAL_WARN_HITS = 25


def new(name, game_build=None):
    return {"schema": SCHEMA, "name": name, "game_build": game_build, "vanilla_manifest": None,
            "options": {"flatten_gradients": False, "skip_sheets": [], "raise_specificity": True,
                        "contrast_backdrop": {"rgb": "#171717", "a": 1.0}},
            "token_overrides": [], "literal_swaps": [], "scoped_rules": [], "rename_classes": {},
            "contrast_pairs": [], "tile_placement": [], "reverts": [], "image_swaps": [], "layout_patches": [], "font_swaps": [], "table_patches": []}


def migrate(p, boundary=colour.B_SCHEMA1):
    """Any schema -> schema 2, colours in canonical form. Idempotent; never drops a field.
    Schema 1 input is a legacy ingestion boundary: percent alphas are normalised and logged (colour.legacy).
    Schema 2 input goes through the strict canonical form; an out-of-range alpha raises."""
    if not isinstance(p, dict):
        raise ValueError("project must be an object")
    p = copy.deepcopy(p)
    old = p.get("schema", 1)
    if old not in (1, SCHEMA):
        raise ValueError("unsupported project schema: %r" % (old,))
    name = str(p.get("name", ""))
    if old == 1:
        conv = lambda v, where: colour.legacy(v, boundary, "%s %s" % (name, where))
    else:
        conv = lambda v, where: colour.canonical(v)
    for e in p.get("token_overrides", []):
        e["value"] = conv(e.get("value"), "token " + str(e.get("token")))
    for e in p.get("literal_swaps", []):
        e["from"], e["to"] = conv(e.get("from"), "literal swap from"), conv(e.get("to"), "literal swap to")
        if old == 1:
            e.setdefault("mode", "rgb-keep-alpha")      # what schema 1 swaps did
    for e in p.get("scoped_rules", []):
        if isinstance(e.get("props"), dict):
            e["props"] = {k: conv(v, "rule %s %s" % (e.get("selector"), k)) for k, v in e["props"].items()}
    for c in p.get("contrast_pairs", []):
        for k in ("fg", "bg"):
            if k in c:
                c[k] = conv(c[k], "contrast pair " + k)
    opts = p.setdefault("options", {})
    opts["contrast_backdrop"] = conv(opts.get("contrast_backdrop", "#171717"), "contrast_backdrop")
    if "club_colours_replacement" in opts:
        opts["club_colours_replacement"] = conv(opts["club_colours_replacement"], "club_colours_replacement")
    p["schema"] = SCHEMA
    return p


def check_value(value):
    """A canonical colour object, or a string token_patch encodes in a verified way: var(--x), px, %, numbers,
    identifiers (and colour strings inside multi-value shorthands)."""
    if colour.is_obj(value):
        colour.from_obj(value)
        return
    if isinstance(value, dict):
        raise ValueError("bad value: %r" % (value,))
    v = str(value).strip()
    toks = v.split() if " " in v and "(" not in v else [v]
    if not v:
        raise ValueError("empty value")
    for t in toks:
        if t.startswith(("#", "rgb")):
            if not colour.parse(t):
                raise ValueError("bad colour: %r" % t)
            continue
        try:
            kind = tp.parse_token_value(t)
            if kind[0] in ("dim", "float"):
                float(kind[1])
        except Exception:
            raise ValueError("bad value: %r" % t)
        if kind[0] == "var" and not re.fullmatch(r"--[\w-]+", kind[1]):
            raise ValueError("var() takes one token name, no fallback: %r" % t)
        if kind[0] == "dim" and kind[2] not in (1, 2):
            raise ValueError("only px and %% are verified units: %r" % t)
        if kind[0] == "keyword" and not IDENT.fullmatch(kind[1]):
            raise ValueError("bad value: %r" % t)


def patch_text(value):
    """Project value -> the string token_patch receives."""
    return colour.patch_value(colour.from_obj(value)) if colour.is_obj(value) else str(value).strip()


def check_selector(sel):
    branches = tp.parse_selector(sel)
    if not branches:
        raise ValueError("empty selector")
    for chain in branches:
        for _rel, parts in chain:
            for t, v in parts:
                if t != tp.P_WILDCARD and not IDENT.fullmatch(v):
                    raise ValueError("bad selector part %r in %r" % (v, sel))


def validate(p):
    """Validates a schema 2 project (run migrate first for anything read from disk or the network)."""
    if not isinstance(p, dict):
        raise ValueError("project must be an object")
    extra = set(p) - KEYS
    if extra:
        raise ValueError("unknown project keys: " + ", ".join(sorted(extra)))
    if p.get("schema") != SCHEMA:
        raise ValueError("project is not schema %d; migrate it first" % SCHEMA)
    if not NAME_RE.fullmatch(str(p.get("name", ""))):
        raise ValueError("bad project name")
    extra = set(p.get("options", {})) - OPTION_KEYS
    if extra:
        raise ValueError("unknown options: " + ", ".join(sorted(extra)))
    colour.from_obj(p.get("options", {}).get("contrast_backdrop", {"rgb": "#171717", "a": 1.0}))
    if p.get("options", {}).get("output", "bundles") not in OUTPUTS:
        raise ValueError("options.output must be 'bundles' or 'native'")
    if not isinstance(p.get("options", {}).get("club_colours", True), bool):
        raise ValueError("options.club_colours must be true (keep the game's club colours) or false (remove them)")
    colour.from_obj(p.get("options", {}).get("club_colours_replacement", CLUB_DEFAULT))
    for e in p.get("token_overrides", []):
        if not str(e.get("token", "")).startswith("--"):
            raise ValueError("token name must start with --: %r" % e.get("token"))
        if isinstance(e["value"], str) and " " in e["value"].strip() and "(" not in e["value"]:
            raise ValueError("a token override takes a single value: %r" % e["value"])
        check_value(e["value"])
    for e in p.get("literal_swaps", []):
        f, t = colour.from_obj(e.get("from")), colour.from_obj(e.get("to"))
        if e.get("mode") not in MODES:
            raise ValueError("literal swap needs mode 'rgba' or 'rgb-keep-alpha'")
        if e["mode"] == "rgb-keep-alpha" and (f[3] != 1.0 or t[3] != 1.0):
            raise ValueError("an rgb-keep-alpha swap ignores alpha; set both alphas to 1.0 or use mode 'rgba'")
        if e.get("scope", "all_sheets") != "all_sheets":
            raise ValueError("literal swap scope must be all_sheets; use a scoped rule for one element")
    for e in p.get("scoped_rules", []):
        op = e.get("op")
        if op not in (None, "replace", "remove"):
            raise ValueError("rule op must be replace or remove")
        if op == "remove":
            if e.get("props") or not e.get("sheet") or set(e) - RULE_KEYS or not isinstance(e.get("remove", []), list) or not all(isinstance(n, str) and n for n in e.get("remove", [])):
                raise ValueError("a remove edit has no props, and 'remove' is a list of property names (empty = every declaration)")
            check_selector(e["selector"])
            for n in e.get("remove", []):
                if not n.startswith("--") and n not in tp.PROP_TABLE:
                    raise ValueError("unknown property: " + n)
            continue
        if set(e) - RULE_KEYS or not e.get("sheet") or not e.get("props") or "remove" in e:
            raise ValueError("scoped rule needs sheet, selector, props (optional why, note, on)")
        check_selector(e["selector"])
        for k, v in e["props"].items():
            if not k.startswith("--") and k not in tp.PROP_TABLE:
                raise ValueError("unknown property: " + k)
            check_value(v)
    ns = p.get("native_sheets", [])
    if not isinstance(ns, list) or not all(isinstance(x, str) and x.startswith("styles/") and x.endswith(".uss") and ".." not in x for x in ns):
        raise ValueError("native_sheets must be a list of styles/<name>.uss paths")
    nsup = p.get("native_support", [])
    if not isinstance(nsup, list) or not all(isinstance(x, str) and x.split("/", 1)[0] in ("images", "fonts", "assets") and ".." not in x for x in nsup):
        raise ValueError("native_support must be a list of paths in images/, fonts/ or assets/")
    from . import uxml
    seen_layouts = set()
    for doc in p.get("layout_patches", []):
        uxml.validate_doc(doc)
        k = (doc["layout"]["bundle"], doc["layout"]["name"])
        if k in seen_layouts:
            raise ValueError("layout %s is patched in two files" % doc["layout"]["name"])
        seen_layouts.add(k)
    from . import tables as tables_mod
    seen_views = set()
    for doc in p.get("table_patches", []):
        tables_mod.validate_doc(doc)
        k = doc["view"]["name"]
        if k in seen_views:
            raise ValueError("table view %s is patched in two files" % k)
        seen_views.add(k)
    seen_fonts = set()
    for f in p.get("font_swaps", []):
        if not isinstance(f, dict) or set(f) - {"token", "source"} or not isinstance(f.get("source"), str) or not FONT_FILE.fullmatch(f["source"]):
            raise ValueError("font swap needs token and source (a .ttf or .otf file name in the project's fonts folder)")
        if not isinstance(f.get("token"), str) or not re.fullmatch(r"--[\w-]+", f["token"]):
            raise ValueError("font swap token must be a --token name")
        if f["token"] in seen_fonts:
            raise ValueError("token %s gets two fonts" % f["token"])
        seen_fonts.add(f["token"])
    seen = set()
    for e in p.get("image_swaps", []):
        images.check_swap(e)
        if (e["bundle"], e["path_id"]) in seen:
            raise ValueError("image %s in %s is swapped twice" % (e["path_id"], e["bundle"]))
        seen.add((e["bundle"], e["path_id"]))
    for old, newc in p.get("rename_classes", {}).items():
        if not IDENT.fullmatch(old) or not IDENT.fullmatch(str(newc)):
            raise ValueError("bad class rename: %r" % old)
    for c in p.get("contrast_pairs", []):
        if "fg" not in c or "bg" not in c:
            raise ValueError("contrast pair needs fg and bg")
        for k in ("fg", "bg"):
            if colour.is_obj(c[k]):
                colour.from_obj(c[k])
    return p


def to_spec(p):
    """Project -> token_patch spec plus 'rgba_swaps' (exact RGBA swaps, applied by patcher.swap_rgba).
    Build starts from vanilla, so a revert is simply a dropped override."""
    reverts = set(p.get("reverts", []))
    opts = p.get("options", {})
    rules = {}
    if opts.get("club_colours", True) is False:          # first, so the project's own scoped rules win at equal specificity
        for e in club_colours.rules(opts.get("club_colours_replacement", CLUB_DEFAULT)):
            rules.setdefault(e["sheet"], []).append({"selector": e["selector"], "props": {k: patch_text(v) for k, v in e["props"].items()}})
    edits = {}
    for e in p.get("scoped_rules", []):
        if e.get("op"):
            edits.setdefault(e["sheet"], []).append({"op": e["op"], "selector": e["selector"], "props": {k: patch_text(v) for k, v in e["props"].items()},
                                                     "remove": list(e.get("remove", []))})
            continue
        r = {"selector": e["selector"], "props": {k: patch_text(v) for k, v in e["props"].items()}}
        if e.get("on"):
            r["on"] = list(e["on"])
        rules.setdefault(e["sheet"], []).append(r)
    swaps = [(i, e) for i, e in enumerate(p.get("literal_swaps", []))]
    return {
        "tokens": {e["token"]: patch_text(e["value"]) for e in p.get("token_overrides", []) if e["token"] not in reverts},
        "literal_map": {colour.hex6(colour.from_obj(e["from"])): colour.hex6(colour.from_obj(e["to"]))
                        for _, e in swaps if e["mode"] == "rgb-keep-alpha"},
        "rgba_swaps": [[i, list(colour.from_obj(e["from"])), list(colour.from_obj(e["to"]))]
                       for i, e in swaps if e["mode"] == "rgba"],
        "append_rules_by_sheet": rules,
        "edit_rules_by_sheet": edits,
        "layout_patches": copy.deepcopy(p.get("layout_patches", [])),
        "table_patches": copy.deepcopy(p.get("table_patches", [])),
        "skip_sheets": list(opts.get("skip_sheets", [])),
        "flatten_gradients": bool(opts.get("flatten_gradients", False)),
        "rename_classes": dict(club_colours.RENAMES, **p.get("rename_classes", {})) if opts.get("club_colours", True) is False
        else dict(p.get("rename_classes", {})),
    }


def warnings(p, swap_hits=None):
    """swap_hits: per-swap hit counts from a build (same order as literal_swaps), or None before a build."""
    out = []
    legacy = [e for e in p.get("tile_placement", []) if not (isinstance(e, dict) and "schema" in e)]
    if legacy:      # entries from before placement edits had their own list: preserved untouched, never validated, never built
        out.append("tile_placement has %d legacy entr%s (no schema marker): kept untouched, not validated, not built. Placement edits live in their own per-project list (Layout tab)" % (len(legacy), "y" if len(legacy) == 1 else "ies"))
    elif p.get("tile_placement"):
        out.append("tile_placement is stored but not built (grid_patch.py output has never been installed live)")
    swaps = p.get("literal_swaps", [])
    rgb_from = {colour.hex6(colour.from_obj(e["from"])) for e in swaps if e["mode"] == "rgb-keep-alpha"}
    for e in swaps:
        if e["mode"] == "rgba" and colour.hex6(colour.from_obj(e["to"])) in rgb_from:
            out.append("rgba swap to %s is recoloured again by the rgb-keep-alpha swap of the same RGB"
                       % colour.text(colour.from_obj(e["to"])))
    if swap_hits is not None:
        for e, n in zip(swaps, swap_hits):
            label = "%s (%s)" % (colour.text(colour.from_obj(e["from"])), e["mode"])
            if n == 0:
                out.append("literal %s matched nothing" % label)
            elif "hits_expected" in e and e["hits_expected"] != n:
                out.append("literal %s: %d hits, expected %d" % (label, n, e["hits_expected"]))
            elif "hits_expected" not in e and n > LITERAL_WARN_HITS:
                out.append("literal %s hits %d properties" % (label, n))
    return out


def path(ws, name):
    if not NAME_RE.fullmatch(name):
        raise ValueError("bad project name")
    return ws.projects / (name + ".skin.json")


def load(ws, name):
    """A project by name: a project folder (projfmt, the current format) or a legacy <name>.skin.json."""
    from . import projfmt
    if projfmt.is_folder(ws, name):
        return projfmt.read(ws, name)
    return migrate(json.loads(path(ws, name).read_text(encoding="utf-8-sig")))


def save(ws, p):
    """Store a project model. A folder project has its generated files rewritten from the model (hand-written comments in them
    are not kept: the text API, projfmt.write_file, is the way to edit files as text)."""
    from . import projfmt
    p = validate(migrate(p))
    if projfmt.is_folder(ws, p["name"]):
        projfmt.write(ws, p)
    else:
        path(ws, p["name"]).write_text(json.dumps(p, indent=2), encoding="utf-8")
    return p


def names(ws):
    from . import projfmt
    return sorted(set(f.name[:-len(".skin.json")] for f in ws.projects.glob("*.skin.json")) | set(projfmt.names(ws)))


def images_dir(ws, name):
    """Where a project's replacement images live: images/ inside a project folder, else <workspace>/images/<name>/."""
    from . import projfmt
    return projfmt.folder(ws, name) / "images" if projfmt.is_folder(ws, name) else ws.images / name


def delete(ws, name):
    """Remove a project (folder or legacy file) from the list. It is moved to <workspace>/trash/<name>-<time>, not erased, and the
    new place is returned."""
    import shutil
    import time
    from . import projfmt
    trash = ws.projects.parent / "trash"
    trash.mkdir(parents=True, exist_ok=True)
    dest = trash / ("%s-%s" % (name, time.strftime("%Y%m%d-%H%M%S")))
    if projfmt.is_folder(ws, name):
        shutil.move(str(projfmt.folder(ws, name)), str(dest))
    else:
        dest.mkdir()
        shutil.move(str(path(ws, name)), str(dest / path(ws, name).name))
        if (ws.images / name).is_dir():
            shutil.move(str(ws.images / name), str(dest / "images"))
    stored = Path(ws.placements) / ("%s.placements.json" % name)       # the project's stored position edits go with it, or a new project of that name inherits them
    if stored.is_file():
        shutil.move(str(stored), str(dest / stored.name))
    return str(dest)
