"""Atlas: the offline half of the runtime join (docs/ATLAS-CONTRACT.md).

Builds `atlas/index.json` (pointers only: names, layout guids, bundle names, selector strings, sheet names, rule ordinals, ids; never a USS body, never layout
content, never a texture) from the layout dump (`fmlayout-index/2`) and the style index, and produces the reproducible evidence blocks the runtime plugin's
join records must carry. Stdlib plus skin_editor; it reads game bundles only to decode style sheets the cached style index does not cover, and checks their
sha256 against the dump's `meta.source` first."""
import hashlib
import json
import re
from pathlib import Path

from . import bundles, index_styles, token_patch as tp, ussprint
from .render import cascade as rcascade, sheets as rsheets, values

INDEX_SCHEMA = "fm27-atlas-index/1"
JOIN_SCHEMA = "fm27-atlas-join/1"
SOURCES = ("rule", "inherited", "initial", "inline", "markup", "code")      # amendment 1 (docs/ATLAS-CONTRACT-AMENDMENT-1.md) added inherited and initial to the contract's four
STYLE_PREFIX = "ui-styles_"
VISUAL_TREE_PREFIX = "ui-visualtreeassets_"
FONT_PREFIX = "ui-fonts_"
COLOUR_TAG = re.compile(r'<color=(?:"(?:#[0-9a-fA-F]{6,8}|[A-Za-z]+)"|(?:#[0-9a-fA-F]{6,8}|[A-Za-z]+))>')      # the game writes <color="#FFFFFF"> (quoted; seen in a live label); <color=#fff> is accepted too


def short_type(t):
    return (t or "").rsplit(".", 1)[-1].rsplit("/", 1)[0]


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def dumps(obj):
    """The one serialisation of the index: sorted keys, compact separators, LF, trailing newline. The recorded sha256 is of these bytes."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n"


# ---- sheets
def sheet_key(entry):
    return "%s:%s:%d" % (entry["bundle"], entry["name"], entry["ordinal"])


def collect_sheets(ws, aa_dir, source):
    """Every style sheet of every ui-styles_* bundle the dump names, as decoded entries with an `ordinal` (position within its bundle).
    The cached style index supplies the bundles it covers; the others are decoded from the game folder after their sha256 is checked
    against the dump's `meta.source.bundles` (a mismatch raises: the atlas never reads files the dump was not made from).
    Returns (entries sorted by (bundle, ordinal), provenance)."""
    wanted = sorted(b for b in source["bundles"] if b.startswith(STYLE_PREFIX))
    ix = index_styles.load(ws)
    man = ws.vanilla_manifest() or {}
    ref = (man.get("reference") or {}).get("bundles", {})
    out, prov = [], {}
    cached = {}
    if ix is not None:
        for e in ix.sheets:
            cached.setdefault(e["bundle"], []).append(e)
    for b in wanted:
        if b in cached and ref.get(b) == source["bundles"][b]:
            for k, e in enumerate(cached[b]):
                out.append(dict(e, ordinal=k))
            prov[b] = "style index cache (hash equals the dump's)"
            continue
        f = Path(aa_dir) / b
        if sha256_file(f) != source["bundles"][b]:
            raise RuntimeError("%s differs from the dump's meta.source hash: refusing to read it" % b)
        for k, tree in enumerate(bundles.read_sheets(f)):
            out.append(dict(index_styles.sheet_entry(b, tree), ordinal=k))
        prov[b] = "decoded from the game folder (hash equals the dump's)"
    out.sort(key=lambda e: (e["bundle"], e["ordinal"]))
    return out, prov


def rule_first_lines(entry):
    """1-based line of each rule's selector line in `ussprint.print_sheet(entry)` (header on line 1). This is the contract's 'line number'."""
    lines, n = [], 2
    for _sel, decls in ussprint.model(entry):
        lines.append(n)
        n += len(decls) + 2
    return lines


# ---- index
def layout_ref(layout):
    return {"layout": layout["name"], "guid": layout["guid"], "bundle": layout["bundle"]}


def build_index(dump, sheets, prov, images, fonts, generated_at, inputs):
    layouts = {l["id"]: l for l in dump["layouts"]}
    els = {}
    for e in dump["elements"]:
        if e["name"]:
            els.setdefault(e["name"], {})[layouts[e["layout_id"]]["guid"]] = layout_ref(layouts[e["layout_id"]])
    elements = {n: sorted(v.values(), key=lambda r: (r["layout"], r["guid"])) for n, v in els.items()}
    selectors = {}
    for sh in sheets:
        for r in sh["rules"]:
            for text in r["s"]:
                selectors.setdefault(text, []).append({"sheet": sh["name"], "sheet_ordinal": sh["ordinal"], "rule": r["i"], "bundle": sh["bundle"]})
    assets = {}
    for im in images:
        assets["%s:%s" % (im["bundle"], im["path_id"])] = {"kind": im["kind"], "name": im["name"], "container": im.get("atlas") or "none", "bundle": im["bundle"]}
    for bundle, name in fonts:
        assets["%s:font:%s" % (bundle, name)] = {"kind": "font", "name": name, "container": "none", "bundle": bundle}
    gradients = {}
    for e in dump["elements"]:
        if short_type(e["type"]) == "SIGradient":
            l = layouts[e["layout_id"]]
            gradients["%s:%d" % (l["guid"], e["local_id"])] = {"holder": l["name"], "bundle": l["bundle"], "asset": "code"}
    for aid, a in assets.items():
        if "gradient" in a["name"].lower() and a["kind"] != "font":
            gradients["asset:" + aid] = {"holder": a["container"] if a["container"] != "none" else a["name"], "bundle": a["bundle"], "asset": aid}
    return {
        "meta": {
            "schema": INDEX_SCHEMA, "generated_at": generated_at, "inputs": inputs,
            "source": {"catalog_hash": dump["meta"]["source"]["catalog_hash"], "dump_schema": dump["meta"]["schema"], "dump_fingerprint": dump["meta"]["index_fingerprint"],
                       "game_build_label": dump["meta"]["game_build"]},
            "sheet_count": len(sheets), "sheet_provenance": prov,
            "counts": {"layouts": len(layouts), "named_elements": sum(len(v) for v in els.values()), "distinct_element_names": len(elements),
                       "selectors": len(selectors), "assets": len(assets), "gradients": len(gradients)},
        },
        "sheets": [{"bundle": s["bundle"], "name": s["name"], "ordinal": s["ordinal"], "rules": len(s["rules"])} for s in sheets],
        "elements": elements, "selectors": selectors, "assets": assets, "gradients": gradients,
    }


def validate_index(idx):
    """[problem, ...] (empty when valid). Checks keys, types, and that every pointer lands on something the index lists."""
    bad = []
    if set(idx) != {"meta", "sheets", "elements", "selectors", "assets", "gradients"}:
        return ["top-level keys are %s" % sorted(idx)]
    if idx["meta"].get("schema") != INDEX_SCHEMA:
        bad.append("meta.schema is %r" % idx["meta"].get("schema"))
    keys = {(s["bundle"], s["name"], s["ordinal"]) for s in idx["sheets"]}
    if len(keys) != len(idx["sheets"]):
        bad.append("duplicate (bundle, name, ordinal) in sheets")
    if len({(k[0], k[1]) for k in keys}) != len(keys):
        bad.append("a sheet name occurs twice inside one bundle: the cascade keys sheets by (bundle, name)")
    if idx["meta"].get("sheet_count") != len(idx["sheets"]):
        bad.append("meta.sheet_count %r != %d sheets" % (idx["meta"].get("sheet_count"), len(idx["sheets"])))
    for sel, hits in idx["selectors"].items():
        for h in hits:
            if (h["bundle"], h["sheet"], h["sheet_ordinal"]) not in keys:
                bad.append("selector %r points at an unlisted sheet %r" % (sel, h["sheet"]))
                break
    for n, refs in idx["elements"].items():
        if not refs or any(set(r) != {"layout", "guid", "bundle"} for r in refs):
            bad.append("element %r has a malformed layout pointer" % n)
    for aid, a in idx["assets"].items():
        if set(a) != {"kind", "name", "container", "bundle"}:
            bad.append("asset %r has keys %s" % (aid, sorted(a)))
    for gid, g in idx["gradients"].items():
        if set(g) != {"holder", "bundle", "asset"}:
            bad.append("gradient %r has keys %s" % (gid, sorted(g)))
        elif g["asset"] != "code" and g["asset"] not in idx["assets"]:
            bad.append("gradient %r names an asset that is not listed: %r" % (gid, g["asset"]))
    return bad[:50]


# ---- cascade over the index's sheets
ROOT_ORDER = rsheets.ROOT_SHEETS


def ordered_sheets(sheets):
    """Sheet objects for a Cascade: the measured root order first (render/sheets.py ROOT_SHEETS; positions 0..n-1), then every other sheet of the index
    (positions n..), so a search over all sheets can still ask 'is this sheet on the measured root' (pos < len(ROOT_ORDER))."""
    by = {}
    for e in sheets:
        by.setdefault((e["bundle"], e["name"]), e)
    out, used = [], set()
    for pos, (b, n, _why) in enumerate(ROOT_ORDER):
        e = by[(b, n)]
        out.append(rsheets.Sheet(pos, b, n, e))
        used.add(id(e))
    for e in sheets:
        if id(e) not in used:
            out.append(rsheets.Sheet(len(out), e["bundle"], e["name"], e))
    return out


def make_cascade(sheets):
    return rcascade.Cascade(ordered_sheets(sheets), runtime_classes={})


def nodes_from_path(path):
    """The join record's element.path (root first): [{type, name, classes, states?}] -> cascade nodes. `classes` are the classes the live element reports."""
    out = []
    for n in path:
        out.append({"type": short_type(n.get("type")), "name": n.get("name") or "", "classes": list(n.get("classes") or []),
                    "_classes": list(n.get("classes") or []), "_states": set(n.get("states") or [])})
    return out


POINTER_STATES = {"hover", "active", "focus"}      # set by the pointer / focus; every other state (enabled, disabled, checked, selected) is read from the element and kept at rest


def _decl(rule, prop):
    """(value text, decoded colours) of the declaration that sets `prop` in this rule, or None. Shorthands are expanded as the render does."""
    for name, val, cols in (rule["props"] if "props" in rule else rule["p"]):
        cname, _inf = values.canonical(name)
        if cname == prop:
            return val, cols
        if not cname.startswith("--"):
            try:
                if any(lh == prop for lh, _t in values.expand(cname, val)):
                    return val, cols
            except Exception:
                pass
    return None


def _declares(rule, prop):
    d = _decl(rule, prop)
    return None if d is None else d[0]


def _rgba(val, cols, ix):
    """The winner's colour as {rgb, a}: its one decoded literal, or the end of a var() alias chain; None when it is neither (a non-colour value)."""
    if len(cols) == 1:
        return {"rgb": cols[0][0].upper(), "a": cols[0][1]}
    m = re.fullmatch(r"\s*var\((--[\w-]+)\)\s*", val)
    if m and ix is not None:
        c = ix.chain(m.group(1))[1]
        return None if not c else {"rgb": c["rgb"].upper(), "a": c["a"]}
    return None


def rule_evidence(casc, sheets, path, prop, ix=None, reproduce=None):
    """The contract's 'rule' evidence for one property: the winner among the rules of the measured root that match the path with the states the plugin
    recorded, and the resting winner (only the pointer states hover/active/focus cleared). None when no rule declares the property.
    Order is the existing cascade's: (specificity, sheet position, rule ordinal). `value` / `value_rgba` are the winner's declaration, so the caller can
    compare it with the live value: a rule whose value differs from the live one is not the source."""
    nodes = nodes_from_path(path)
    root = len(ROOT_ORDER)                       # only the sheets of the measured root apply (render/sheets.py); the others are searched, not applied
    ent = [e for e in casc.matches_with_states(nodes)[0] if e.pos < root]
    rest_nodes = nodes_from_path([dict(n, states=[s for s in n.get("states") or [] if s not in POINTER_STATES]) for n in path])
    rest_ent = [e for e in casc.matches_with_states(rest_nodes)[0] if e.pos < root]

    def pick(entries):
        win = None
        for e in entries:
            if _declares(e.rule, prop) is not None:
                win = e
        return win
    w, r = pick(ent), pick(rest_ent)
    if w is None:
        return None
    sh = next(s for s in sheets if (s["bundle"], s["name"]) == (w.sheet.bundle, w.sheet.name))
    val, cols = _decl(w.rule, prop)

    def ident(e):
        return (e.sheet.bundle, e.sheet.name, e.rule["i"])
    return {"selector": w.text, "sheet": w.sheet.name, "sheet_bundle": w.sheet.bundle, "sheet_ordinal": sh["ordinal"], "rule": w.rule["i"],
            "line": rule_first_lines(sh)[w.rule["i"]], "specificity": w.spec, "active_pseudo_states": sorted({s for n in nodes for s in n["_states"]}),
            "resting_winner": None if r is None else {"selector": r.text, "sheet": r.sheet.name, "rule": r.rule["i"]},
            "hover_only": r is None or ident(r) != ident(w), "value": val, "value_rgba": _rgba(val, cols, ix), "reproduce": reproduce}


# ---- code search
def needle_forms(rgb_hex, alpha, ix):
    """['#20665a', '#20665A', 'rgb(32, 102, 90)', 'rgba(32, 102, 90, 1)'] plus one 'var(--token)' per token that resolves to this exact colour."""
    h = rgb_hex.lstrip("#")
    r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
    forms = ["#" + h.lower(), "#" + h.upper(), "rgb(%d, %d, %d)" % (r, g, b), "rgba(%d, %d, %d, %s)" % (r, g, b, ("%g" % alpha))]
    for tok in sorted(ix.defs):
        _chain, c = ix.chain(tok)
        if c and c["rgb"].lstrip("#").lower() == h.lower() and abs(c["a"] - alpha) < 1e-6:
            forms.append("var(%s)" % tok)
    return forms


def _col_hit(cols, h, alpha):
    return any(c[0].lstrip("#").lower() == h and abs(c[1] - alpha) < 1e-3 for c in cols)


def code_search(sheets, path, forms, command, state_path=None, inline_sheet_count=0, target=None):
    """The contract's 'code' evidence. Every sheet of the index is searched; a hit is a (sheet, rule, property) whose value text contains a needle form OR whose
    decoded colours contain `target` ((rrggbb, alpha)), so a print format the needles miss cannot hide a hit. A hit is 'matching' when the rule's selector matches
    the element's path (with the recorded states) in the cascade built from ALL sheets; every other hit is coincidental. `by_text_only` / `by_colour_only` count the
    declarations one method alone found, so a gap between the two methods is visible."""
    casc = make_cascade(sheets)
    ent, _ = casc.matches_with_states(nodes_from_path(state_path or path))
    matching = {(e.sheet.bundle, e.sheet.name, e.rule["i"]): e.pos < len(ROOT_ORDER) for e in ent}
    low = [f.lower() for f in forms]
    match_hits, coincidental, on_root, only_text, only_cols = 0, [], [], 0, 0
    for sh in sheets:
        lines = rule_first_lines(sh)
        for r in sh["rules"]:
            hit = []
            for name, val, cols in r["p"]:
                t = any(f in val.lower() for f in low)
                c = target is not None and _col_hit(cols, target[0], target[1])
                if t or c:
                    hit.append(name)
                    only_text += t and not c
                    only_cols += c and not t
            if not hit:
                continue
            key = (sh["bundle"], sh["name"], r["i"])
            if key in matching:
                match_hits += 1
                on_root.append({"sheet": sh["name"], "line": lines[r["i"]], "selector": ", ".join(r["s"]), "properties": hit, "on_measured_root": matching[key]})
            else:
                coincidental.append({"sheet": sh["name"], "line": lines[r["i"]], "selector": ", ".join(r["s"])})
    coincidental.sort(key=lambda h: (h["sheet"], h["line"]))
    return {"command": command, "sheets_searched": len(sheets), "sheets": [sheet_key(s) for s in sheets], "inline_sheets_searched": inline_sheet_count,
            "needle_forms": forms, "matching_selector_hits": match_hits, "matching_hits": on_root, "coincidental_hits": coincidental,
            "by_text_only": only_text, "by_colour_only": only_cols}


# ---- markup
def markup_lookup(attrs, key, reproduce=None):
    """The contract's 'markup' evidence from one stored attribute map: {key, stored, tag}. The tag counts as stored only when one complete colour tag
    is in the single string stored under `key`; otherwise the source is 'code' (the caller must not call it markup)."""
    stored = attrs.get(key)
    if not isinstance(stored, str):
        return None
    m = COLOUR_TAG.search(stored)
    return {"key": key, "stored": stored, "tag": m.group(0) if m else None, "complete_tag": bool(m), "reproduce": reproduce}


def inline_sheets(aa_dir, source):
    """Every layout's inline sheet (the StyleSheet objects inside the ui-visualtreeassets_* bundles) as decoded entries, after the bundle hash check.
    A separate population from the shared sheets: an inline sheet applies only to its own layout."""
    out = []
    for b in sorted(x for x in source["bundles"] if x.startswith(VISUAL_TREE_PREFIX)):
        f = Path(aa_dir) / b
        if sha256_file(f) != source["bundles"][b]:
            raise RuntimeError("%s differs from the dump's meta.source hash: refusing to read it" % b)
        for k, tree in enumerate(bundles.read_sheets(f)):
            out.append(dict(index_styles.sheet_entry(b, tree), ordinal=k))
    return out


def inline_hits(inline, forms):
    """Needle hits inside inline sheets: [{sheet, line, selector}] (an inline rule has no selector; '' is recorded). Coincidental by definition."""
    low = [f.lower() for f in forms]
    out = []
    for sh in inline:
        lines = rule_first_lines(sh)
        for r in sh["rules"]:
            if any(any(f in val.lower() for f in low) for _n, val, _c in r["p"]):
                out.append({"sheet": "inline:" + sheet_key(sh), "line": lines[r["i"]], "selector": ", ".join(r["s"])})
    return out


# ---- amendment 1: initial values
# Initial (computed when nothing declares the property) values of the colour properties the plugin reads. Source of the table: the resolved values the live game reports on
# elements that no rule reaches (observed, 2026-11-16), not the engine's documentation; a patch can change it, so the table is part of the evidence ('initial_table').
INITIAL = {"background-color": "#00000000", "border-top-color": "#00000000", "border-right-color": "#00000000", "border-bottom-color": "#00000000",
           "border-left-color": "#00000000", "-unity-background-image-tint-color": "#FFFFFFFF"}
INHERITED_PROPERTIES = {"color"}


def initial_evidence(casc, sheets, path, prop, live_hex8, ix=None, reproduce=None):
    """The 'initial' evidence: no rule of the measured root declares `prop` for the element (and, for an inherited property, for any ancestor), and the live value
    equals the initial table's value. None when a declaration exists or the value differs."""
    want = INITIAL.get(prop)
    if want is None or want.upper() != live_hex8.upper():
        return None
    cuts = range(len(path), 0, -1) if prop in INHERITED_PROPERTIES else [len(path)]
    for k in cuts:
        if rule_evidence(casc, sheets, path[:k], prop, ix=ix) is not None:
            return None
    return {"initial_value": want, "declarations_found_on_path": 0, "checked": "element and ancestors" if prop in INHERITED_PROPERTIES else "element only (not inherited)",
            "initial_table": "observed on the live game, see docs/ATLAS-CONTRACT-AMENDMENT-1.md", "reproduce": reproduce}
