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
        "scoped_rules", "declaration_edits", "rename_classes", "contrast_pairs", "tile_placement", "reverts", "image_swaps", "native_sheets", "native_support", "native_name",
        "layout_patches", "font_swaps", "table_patches", "tile_bundle_ops"}
FONT_FILE = re.compile(r"[A-Za-z0-9][\w.-]{0,100}\.(?:ttf|otf)", re.I)
OPTION_KEYS = {"flatten_gradients", "skip_sheets", "raise_specificity", "contrast_backdrop", "club_colours", "club_colours_replacement", "output", "route_preference", "route_preference_explicit", "edit_competition_sheets", "edit_competition_sheets_explicit", "layout_route", "layout_route_explicit", "layout_engine", "layout_engine_explicit", "experimental_bundle_layout_edits", "experimental_bundle_layout_edits_explicit", "experimental_tile_sizes", "experimental_tile_sizes_explicit", "experimental_slot_edits", "experimental_slot_edits_explicit"}
EXPERIMENTAL_BUNDLE_LAYOUT_WARNING = (
    "experimental: layout edits via bundles is on — bundle composition edits rewrite "
    "ui-tileslayouts_assets_all.bundle, move every stored composition in that bundle, and are "
    "ignored on screens customised in the game"
)
ROUTE_PREFERENCES = ("skin_folder", "bundle")
DEFAULT_ROUTE_PREFERENCE = "bundle"
LAYOUT_ROUTES = ("custom_layout", "bundle")       # ST1: how LAYOUT operations (move, resize, max size, add tile, slots, swap tile) reach the game
DEFAULT_LAYOUT_ROUTE = "custom_layout"             # the default for layout operations ONLY; styles and pictures keep route_preference
LAYOUT_ENGINES = ("one_rule", "rea")              # REA-WIN-4: which layout rule the preview uses (both stay selectable)
DEFAULT_LAYOUT_ENGINE = "rea"                     # UI1: the REA port is the default; one_rule remains an explicit project choice
TOKEN_BUNDLES = ("ui-styles_assets_default.bundle", "ui-styles_assets_common.bundle")
OUTPUTS = ("bundles", "native")                    # how the skin reaches the game: patched game bundles, or a native skin folder
CLUB_DEFAULT = {"rgb": "#171717", "a": 1.0}
RULE_KEYS = {"sheet", "selector", "props", "why", "note", "on", "op", "remove", "source"}   # op: replace | remove edit the game's own rule in place (bundle target)
MODES = ("rgba", "rgb-keep-alpha")
NAME_RE = re.compile(r"[A-Za-z0-9][\w.-]{0,63}")
IDENT = re.compile(r"[A-Za-z_][\w-]*")
LITERAL_WARN_HITS = 25


def new(name, game_build=None):
    return {"schema": SCHEMA, "name": name, "game_build": game_build, "vanilla_manifest": None,
            "options": {"flatten_gradients": False, "skip_sheets": [], "raise_specificity": True,
                        "contrast_backdrop": {"rgb": "#171717", "a": 1.0}},
            "token_overrides": [], "literal_swaps": [], "scoped_rules": [], "declaration_edits": [], "rename_classes": {},
            "contrast_pairs": [], "tile_placement": [], "reverts": [], "image_swaps": [], "layout_patches": [], "font_swaps": [], "table_patches": []}


def route_preference(p):
    """The EFFECTIVE build routing of a project. A value counts only when the user chose it explicitly
    (`options.route_preference_explicit` true); otherwise the default is bundle.

    5I commits abf1dac..414990c wrote `route_preference: skin_folder` automatically in `project.new()`; those
    values are treated as UNSET by `migrate()` and take the bundle default. New projects carry no
    route_preference key at all."""
    opts = (p or {}).get("options") or {}
    if opts.get("route_preference_explicit") and opts.get("route_preference") in ROUTE_PREFERENCES:
        return opts["route_preference"]
    return DEFAULT_ROUTE_PREFERENCE


def layout_route(p):
    """The route of the project's LAYOUT operations: the game's own custom-layout files (default; no bundle rebuild, no checksum mismatch, undo = restore the file) or the
    bundle. Only a choice made explicitly counts."""
    opts = (p or {}).get("options") or {}
    if opts.get("layout_route_explicit") and opts.get("layout_route") in LAYOUT_ROUTES:
        return opts["layout_route"]
    return DEFAULT_LAYOUT_ROUTE


def set_layout_route(p, value):
    if value not in LAYOUT_ROUTES:
        raise ValueError("layout_route must be 'custom_layout' or 'bundle'")
    opts = p.setdefault("options", {})
    opts["layout_route"] = value
    opts["layout_route_explicit"] = True
    return p


def layout_engine(p):
    """The preview's layout rule. UI1: default rea (the recovered game runtime port, 27/27 measured
    cases); one_rule stays selectable as an explicit project choice."""
    opts = (p or {}).get("options") or {}
    if opts.get("layout_engine_explicit") and opts.get("layout_engine") in LAYOUT_ENGINES:
        return opts["layout_engine"]
    return DEFAULT_LAYOUT_ENGINE


def set_layout_engine(p, value):
    """Record an EXPLICIT preview-engine choice in the project."""
    if value not in LAYOUT_ENGINES:
        raise ValueError("layout_engine must be 'one_rule' or 'rea'")
    opts = p.setdefault("options", {})
    opts["layout_engine"] = value
    opts["layout_engine_explicit"] = True
    return p


def set_route_preference(p, value):
    """Record an EXPLICIT routing choice in the project (the only way the setting is stored)."""
    if value not in ROUTE_PREFERENCES:
        raise ValueError("route_preference must be 'skin_folder' or 'bundle'")
    opts = p.setdefault("options", {})
    opts["route_preference"] = value
    opts["route_preference_explicit"] = True
    return p


def edit_competition_sheets(p):
    """Whether this project chooses to edit competition sheets' own definitions. OFF unless chosen explicitly."""
    opts = (p or {}).get("options") or {}
    return bool(opts.get("edit_competition_sheets_explicit") and opts.get("edit_competition_sheets"))


def set_edit_competition_sheets(p, value):
    opts = p.setdefault("options", {})
    opts["edit_competition_sheets"] = bool(value)
    opts["edit_competition_sheets_explicit"] = True
    return p


def experimental_bundle_layout_edits(p):
    """UI2/UI5 route lock: bundle builds exclude grid-composition edits unless the advanced setting
    'experimental: layout edits via bundles' is explicitly on (off by default)."""
    opts = (p or {}).get("options") or {}
    if "experimental_bundle_layout_edits" in opts:
        return bool(opts.get("experimental_bundle_layout_edits_explicit") and opts.get("experimental_bundle_layout_edits"))
    return bool(opts.get("layout_route_explicit") and opts.get("layout_route") == "bundle")


def set_experimental_bundle_layout_edits(p, value):
    opts = p.setdefault("options", {})
    opts["experimental_bundle_layout_edits"] = bool(value)
    opts["experimental_bundle_layout_edits_explicit"] = True
    return p


def experimental_tile_sizes(p):
    """REL15 G1 gate: tile sizes (add-tile-size) ships behind 'experimental: tile sizes' (off by default)
    until owner-confirmed in-game on a standalone bundle + layout run."""
    opts = (p or {}).get("options") or {}
    return bool(opts.get("experimental_tile_sizes_explicit") and opts.get("experimental_tile_sizes"))


def set_experimental_tile_sizes(p, value):
    opts = p.setdefault("options", {})
    opts["experimental_tile_sizes"] = bool(value)
    opts["experimental_tile_sizes_explicit"] = True
    return p


def experimental_slot_edits(p):
    """REL15-C gate: slot editing (add, remove, reorder) ships behind 'experimental: slot edits'
    (off by default) because 20261124T070834Z-03e293d7 was rolled back before an in-game check."""
    opts = (p or {}).get("options") or {}
    return bool(opts.get("experimental_slot_edits_explicit") and opts.get("experimental_slot_edits"))


def set_experimental_slot_edits(p, value):
    opts = p.setdefault("options", {})
    opts["experimental_slot_edits"] = bool(value)
    opts["experimental_slot_edits_explicit"] = True
    return p


def migrate(p, boundary=colour.B_SCHEMA1):
    """Any schema -> schema 2, colours in canonical form. Idempotent; never drops an authored field (the two
    automatic 5I routing values are dropped: they count as UNSET, see route_preference()).
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
    # 5I migration: `route_preference` written automatically by project.new() in commits abf1dac..414990c is
    # UNSET, not a user choice. Same for the automatic edit_competition_sheets: false. An explicit choice is
    # the only stored one. The file is not rewritten here; a normal save writes the migrated options.
    if not opts.get("route_preference_explicit"):
        opts.pop("route_preference", None)
        opts.pop("route_preference_explicit", None)
    if not opts.get("edit_competition_sheets_explicit"):
        opts.pop("edit_competition_sheets", None)
        opts.pop("edit_competition_sheets_explicit", None)
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
    if p.get("options", {}).get("route_preference", DEFAULT_ROUTE_PREFERENCE) not in ROUTE_PREFERENCES:
        raise ValueError("options.route_preference must be 'skin_folder' (default) or 'bundle'")
    if not isinstance(p.get("options", {}).get("route_preference_explicit", False), bool):
        raise ValueError("options.route_preference_explicit must be true or false")
    if "route_preference" in p.get("options", {}) and not p["options"].get("route_preference_explicit"):
        raise ValueError("route_preference is stored only on an explicit choice: use set_route_preference()")
    if not isinstance(p.get("options", {}).get("edit_competition_sheets", False), bool):
        raise ValueError("options.edit_competition_sheets must be true (explicit choice) or false (default)")
    if "edit_competition_sheets" in p.get("options", {}) and not p["options"].get("edit_competition_sheets_explicit"):
        raise ValueError("edit_competition_sheets is stored only on an explicit choice: use set_edit_competition_sheets()")
    if p.get("options", {}).get("layout_engine", DEFAULT_LAYOUT_ENGINE) not in LAYOUT_ENGINES:
        raise ValueError("options.layout_engine must be 'rea' (default) or 'one_rule'")
    if not isinstance(p.get("options", {}).get("layout_engine_explicit", False), bool):
        raise ValueError("options.layout_engine_explicit must be true or false")
    if "layout_engine" in p.get("options", {}) and not p["options"].get("layout_engine_explicit"):
        raise ValueError("layout_engine is stored only on an explicit choice: use set_layout_engine()")
    if not isinstance(p.get("options", {}).get("experimental_bundle_layout_edits", False), bool):
        raise ValueError("options.experimental_bundle_layout_edits must be true or false")
    if not isinstance(p.get("options", {}).get("experimental_bundle_layout_edits_explicit", False), bool):
        raise ValueError("options.experimental_bundle_layout_edits_explicit must be true or false")
    if "experimental_bundle_layout_edits" in p.get("options", {}) and not p["options"].get("experimental_bundle_layout_edits_explicit"):
        raise ValueError("experimental_bundle_layout_edits is stored only on an explicit choice: use set_experimental_bundle_layout_edits()")
    if not isinstance(p.get("options", {}).get("experimental_tile_sizes", False), bool):
        raise ValueError("options.experimental_tile_sizes must be true or false")
    if not isinstance(p.get("options", {}).get("experimental_tile_sizes_explicit", False), bool):
        raise ValueError("options.experimental_tile_sizes_explicit must be true or false")
    if "experimental_tile_sizes" in p.get("options", {}) and not p["options"].get("experimental_tile_sizes_explicit"):
        raise ValueError("experimental_tile_sizes is stored only on an explicit choice: use set_experimental_tile_sizes()")
    if not isinstance(p.get("options", {}).get("experimental_slot_edits", False), bool):
        raise ValueError("options.experimental_slot_edits must be true or false")
    if not isinstance(p.get("options", {}).get("experimental_slot_edits_explicit", False), bool):
        raise ValueError("options.experimental_slot_edits_explicit must be true or false")
    if "experimental_slot_edits" in p.get("options", {}) and not p["options"].get("experimental_slot_edits_explicit"):
        raise ValueError("experimental_slot_edits is stored only on an explicit choice: use set_experimental_slot_edits()")
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
            raise ValueError("scoped rule needs sheet, selector, props (optional why, note, on, source)")
        check_selector(e["selector"])
        for k, v in e["props"].items():
            if not k.startswith("--") and k not in tp.PROP_TABLE:
                raise ValueError("unknown property: " + k)
            check_value(v)
    seen_decl = set()
    for e in p.get("declaration_edits", []):
        if not isinstance(e, dict) or set(e) - {"bundle", "sheet", "selector", "occurrence", "property", "old", "new", "reach"}:
            raise ValueError("a declaration edit takes bundle, sheet, selector, occurrence, property, old, new (and reach)")
        for k in ("bundle", "sheet", "selector", "property", "new"):
            if not e.get(k):
                raise ValueError("a declaration edit needs %s" % k)
        if e["property"] not in tp.PROP_TABLE and not str(e["property"]).startswith("--"):
            raise ValueError("unknown declaration property: " + str(e["property"]))
        check_selector(e["selector"])
        check_value(e["new"])
        key = (e["bundle"], e["sheet"], e["selector"], int(e.get("occurrence") or 0), e["property"])
        if key in seen_decl:
            raise ValueError("declaration %s of %s %s is edited twice" % (e["property"], e["sheet"], e["selector"]))
        seen_decl.add(key)
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
        "declaration_edits": copy.deepcopy(p.get("declaration_edits", [])),
        "append_rules_by_sheet": rules,
        "edit_rules_by_sheet": edits,
        "layout_patches": copy.deepcopy(p.get("layout_patches", [])),
        "table_patches": copy.deepcopy(p.get("table_patches", [])),
        "skip_sheets": list(opts.get("skip_sheets", [])),
        "flatten_gradients": bool(opts.get("flatten_gradients", False)),
        "route_preference": route_preference(p),
        "token_bundles": list(TOKEN_BUNDLES) if route_preference(p) == "bundle" else [],
        "rename_classes": dict(club_colours.RENAMES, **p.get("rename_classes", {})) if opts.get("club_colours", True) is False
        else dict(p.get("rename_classes", {})),
    }


def warnings(p, swap_hits=None):
    """swap_hits: per-swap hit counts from a build (same order as literal_swaps), or None before a build."""
    out = []
    if experimental_bundle_layout_edits(p):
        out.append(EXPERIMENTAL_BUNDLE_LAYOUT_WARNING)
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
    from . import changes, projfmt
    p = validate(migrate(p))
    try:
        old = load(ws, p["name"])
    except Exception:                                       # a new project, or one that does not load: everything in it counts as new
        old = None
    if projfmt.is_folder(ws, p["name"]):
        projfmt.write(ws, p)
    else:
        path(ws, p["name"]).write_text(json.dumps(p, indent=2), encoding="utf-8")
    for reason, scope in changes.diff_reasons(old, p):      # one record per kind of change; the dispatcher turns them into one event (changes.batch)
        changes.record(p["name"], reason, scope)
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
    from . import changes
    changes.record(name, "file", ["project removed"])
    return str(dest)
