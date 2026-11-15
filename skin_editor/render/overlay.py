"""The project overlay of the offline render (M5; docs/PHASE9-PLAN.md section 6): the same edits the build makes, applied to IN-MEMORY copies of the render's inputs, so
"vanilla" and "skin" are one flag and the vanilla data is never touched.

- Token overrides, literal swaps, scoped rules (replace / remove / append) come from `project.to_spec`, the spec the build uses.
  Output `bundles`: applied to the named game sheet in place (a token's definition is replaced wherever it is defined; rules are appended to their sheet).
  Output `native`: the game's sheets stay as they are and ONE author sheet, last in the order (a skin loads after the game's sheets), carries the token overrides as a `:root`
  rule and the appended rules; `replace` and `remove` edits do not exist in a native skin and are reported in `notes`, not drawn.
- Layout patches (class and inline edits, attributes) are applied to the render tree before the cascade, to the node whose element id and layout name match; the guard
  (type and name) must match or the op is reported and skipped, as the build refuses it.
- Not applied here, said in `not_applied`: tile moves and table edits (they act on the screen assembly and on table views), class renames, image and font swaps.
Everything returned is data about what was applied; nothing is silent."""
import copy
import hashlib
import json
import re

from .. import colour, project as project_mod
from .sheets import ROOT_SHEETS, Sheet

HEX = re.compile(r"#([0-9a-fA-F]{6})([0-9a-fA-F]{2})?")
AUTHOR_BUNDLE = "(project)"


def project_hash(p):
    """A short hash of everything in a project that changes a render (not the name, the vanilla manifest or the checks)."""
    keys = ("token_overrides", "literal_swaps", "reverts", "scoped_rules", "layout_patches", "options", "rename_classes", "native_sheets")
    return hashlib.sha1(json.dumps({k: p.get(k) for k in keys}, sort_keys=True, default=str).encode("utf-8")).hexdigest()[:16]


def _selectors(text):
    return [s.strip() for s in re.split(r",\s*(?![^()]*\))", text) if s.strip()]


def _is_token_rule(sels):
    return any(s == ":root" or s.endswith(" :root") for s in sels)


def _rule(sheet_rules, selector, props, origin=None):
    sels = _selectors(selector)
    r = {"i": len(sheet_rules), "s": sels, "t": _is_token_rule(sels), "p": [[k, str(v), []] for k, v in props.items()]}
    if origin:
        r["origin"] = origin                      # {"kind": "project", "sheet": <game sheet its file is named for>, "selector": ...}: where the editor finds this rule
    sheet_rules.append(r)


def _swap_literals(entry, rgb_map, rgba_swaps):
    """Replace colour literals in value texts: rgb-keep-alpha swaps by #RRGGBB (the alpha byte stays), exact RGBA swaps by the whole #RRGGBBAA."""
    exact = {}
    for _i, f, t in rgba_swaps:
        exact[colour.hex8(tuple(f)).upper()] = colour.text(tuple(t))       # keyed by #RRGGBBAA: the lookup below pads an opaque #RRGGBB with ff, so an opaque swap keyed by its 6-digit text never matched (fixed 2026-11-15, S3)
    if not rgb_map and not exact:
        return 0
    n = 0
    for r in entry["rules"]:
        for p in r["p"]:
            def sub(m):
                whole = ("#" + m.group(1) + (m.group(2) or "ff")).upper()
                if whole in exact:
                    return exact[whole]
                new = rgb_map.get("#" + m.group(1).upper())
                return (new.upper() + (m.group(2) or "")) if new else m.group(0)
            v = HEX.sub(sub, p[1])
            if v != p[1]:
                p[1], p[2] = v, []
                n += 1
    return n


def _edit_rules(entry, edits, notes):
    for e in edits:
        sels = _selectors(e["selector"])
        hit = [r for r in entry["rules"] if r["s"] == sels or e["selector"] in r["s"]]
        if not hit:
            notes.append("%s: no rule %r to %s in the game's sheet" % (entry["name"], e["selector"], e["op"]))
            continue
        r = hit[0]
        if e["op"] == "replace":
            for k, v in e["props"].items():
                for p in r["p"]:
                    if p[0] == k:
                        p[1], p[2] = str(v), []
                        break
                else:
                    r["p"].append([k, str(v), []])
        else:
            names = set(e.get("remove") or [])
            r["p"] = [p for p in r["p"] if names and p[0] not in names]


def build_sheets(bank, p, order=None):
    """(compiled sheets in application order with the project's edits applied, notes). Entries are copied: the bank's own sheets are never modified."""
    spec = project_mod.to_spec(p)
    native = (p.get("options") or {}).get("output", "bundles") == "native"
    skip = set(spec["skip_sheets"])
    sheets, notes, tokens_left = [], [], dict(spec["tokens"])
    author = {"bundle": AUTHOR_BUNDLE, "name": "%s (project)" % p.get("name", "project"), "rules": []}
    for b, n, _why in (order or ROOT_SHEETS):
        if n in skip:
            notes.append("sheet %s skipped by the project" % n)
            continue
        entry = copy.deepcopy(bank.entry(b, n))
        if not native:
            for r in entry["rules"]:
                if r["t"]:
                    for pr in r["p"]:
                        if pr[0] in spec["tokens"]:
                            pr[1], pr[2] = spec["tokens"][pr[0]], []
                            tokens_left.pop(pr[0], None)
            _edit_rules(entry, spec["edit_rules_by_sheet"].get(n, []), notes)
            for e in spec["append_rules_by_sheet"].get(n, []):
                _rule(entry["rules"], e["selector"], e["props"], {"kind": "project", "sheet": n, "selector": e["selector"]})
        _swap_literals(entry, spec["literal_map"], spec["rgba_swaps"])
        sheets.append(entry)
    if native:
        if spec["tokens"]:
            _rule(author["rules"], ":root", spec["tokens"], {"kind": "project", "sheet": "tokens", "selector": ":root"})
        for sheet_name, rules in spec["append_rules_by_sheet"].items():
            for e in rules:
                _rule(author["rules"], e["selector"], e["props"], {"kind": "project", "sheet": sheet_name, "selector": e["selector"]})
        for sheet_name, edits in spec["edit_rules_by_sheet"].items():
            notes.append("%d replace/remove edit(s) on %s do not exist in a native skin: not drawn" % (len(edits), sheet_name))
        sheets.append(author)
    elif tokens_left:
        notes.append("token overrides with no definition in the root sheets (not drawn): " + ", ".join(sorted(tokens_left)))
    return [Sheet(i, e["bundle"], e["name"], e) for i, e in enumerate(sheets)], notes


def apply_layout_patches(top_nodes, docs):
    """Apply the project's layout patch ops to the render tree in place. Returns (applied count, notes). A node is addressed by its element id AND the layout it came from."""
    by_layout = {}
    for d in docs or []:
        by_layout.setdefault(d["layout"]["name"], []).extend(d["ops"])
    if not by_layout:
        return 0, []
    applied, notes = 0, []
    index = {}

    def walk(n):
        if n.get("id") is not None and n.get("layout") in by_layout:
            index[(n["layout"], n["id"])] = n
        for c in n.get("children", []):
            walk(c)
    for t in top_nodes:
        walk(t)
    for layout, ops in by_layout.items():
        for op in ops:
            n = index.get((layout, op["id"]))
            if n is None:
                notes.append("%s: no element %d in this render (not reached, or the game changed)" % (layout, op["id"]))
                continue
            g = op["guard"]
            if n.get("type") != g["type"] or ("name" in g and (n.get("name") or "") != g["name"]):
                notes.append("%s: element %d is now %s#%s, the patch was made for %s#%s: skipped" % (layout, op["id"], n.get("type"), n.get("name"), g["type"], g.get("name", "")))
                continue
            if op["op"] == "set-classes":
                cur = list(n.get("classes") or [])
                n["classes"] = [c for c in cur if c not in op.get("remove", [])] + [c for c in op.get("add", []) if c not in cur]
            elif op["op"] == "set-inline":
                inline = [(k, v) for k, v in (n.get("inline") or []) if k not in op["props"]]
                inline += [(k, project_mod.patch_text(v)) for k, v in op["props"].items()]
                n["inline"] = inline
            else:
                n.setdefault("attrs", {})[op["name"]] = op["value"]
            n.setdefault("layout_rules", []).append("project-patch")
            applied += 1
    return applied, notes


def table_placeholder(T, path_id, project=None, breakpoint=None):
    """A table view as a LABELLED PLACEHOLDER table: the header row is the view's column order (with the project's column edits applied when `project` is given), the cells
    are placeholders (no data). `T` is a `tables.Tables`. The column edits are the ones the build makes (`tables.apply_to_view` on a copy of the view)."""
    from .. import tables as tables_mod
    base = T.view(path_id)
    cells = {c["id"]: c["cell"] for c in base["columns"] if c["cell"]}
    cells.update({a["id"]: a for a in base["available"]})
    notes = []
    cols = [dict(c) for c in base["columns"]]
    doc = next((d for d in (project or {}).get("table_patches", []) if d["view"]["name"] == base["name"]), None)
    if doc:
        tree = copy.deepcopy(T._views[int(path_id)]["tree"])
        fac = None
        try:
            fac, _cov = T.factory_for([c["id"] for c in base["columns"]])
            fac_ids = {r["m_id"] for r in fac["tree"]["m_rowData"]} if fac else None
            tables_mod.apply_to_view(tree, doc["ops"], base["name"], fac_ids)
            cols = []
            for i, c in enumerate(tree["m_tableView"]["m_tableConfig"]):
                m = c["m_columnMetadata"]
                cols.append({"index": i, "id": c["m_columnID"], "width": m["m_widthOverride"], "required": bool(m["m_required"]), "cell": cells.get(c["m_columnID"])})
        except ValueError as e:
            notes.append(str(e))                                  # a stale op: the vanilla columns are shown and the reason is said
    masks = {c["id"]: c["breakpoints"] for c in base["columns"]}
    if breakpoint is not None:                    # a column shows at a breakpoint when its applicable-breakpoints mask has that bit (-1 = all): the screen's header row, not the view's whole list
        cols = [c for c in cols if masks.get(c["id"], -1) == -1 or masks[c["id"]] & (1 << int(breakpoint))]
    return {"view": base["name"], "path_id": base["path_id"], "edited": bool(doc) and not notes, "ops": len(doc["ops"]) if doc else 0, "notes": notes, "breakpoint": breakpoint,
            "columns": [{"id": c["id"], "width": c["width"], "header_text_id": (c.get("cell") or {}).get("header_text_id"), "cell_layout": (c.get("cell") or {}).get("cell_layout", "")} for c in cols],
            "label": "placeholder table: the header row is the view's column order, the cells hold no data"}


NOT_APPLIED = ["class renames", "image and font swaps"]
