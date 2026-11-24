"""Competition-sheet reach warnings (Stage 5I part 2).

The Bundesliga sheet (ui-styles_assets_default.bundle, 22 rules) is bound to a club's competition, so a plain
render does not apply it. It can still change an edited element: its own selectors paint colours, fonts and sizes
(.prematch-table-bundesliga / .prematch-lineup-bundesliga use a background-colour token; the .bundesliga-licensed-*,
.bundesliga-font and .bundesliga-table-text-* families set typography and sizes). A token used by a competition
sheet is also redefined there.

This module WARNS only where such a rule touches an element the edit addresses (the operation's selector, its
target's class/name guard and its winning-declaration selector), or where a competition sheet redefines an edited
token in that token's measured reach. It never edits a competition sheet: changing one is a separate, explicit
per-project choice (`options.edit_competition_sheets`, OFF by default)."""
import re

from . import specificity

BUNDESLIGA = "Bundesliga"
COMPETITION_SHEETS = frozenset(specificity.LICENSED)
# Properties a competition sheet must set for the warning to fire: colour, font and size - not layout/scale.
COLOUR_FONT_SIZE = {
    "color", "background-color", "border-color", "-unity-background-image-tint-color",
    "font-size", "font", "-unity-font", "-unity-font-definition", "font-style", "font-weight",
    "-unity-font-style", "-unity-text-generate-visual-content", "letter-spacing", "word-spacing",
    "text-overflow", "white-space", "-unity-text-align", "text-align",
}
NOTE = ("changing a competition sheet's own definitions is a separate per-project choice "
        "(options.edit_competition_sheets), OFF by default")
_TERM = re.compile(r"[.#]([A-Za-z_][\w-]*)")


def _terms(*values):
    out = set()
    for v in values:
        if isinstance(v, str):
            out.update(_TERM.findall(v))
            out.update(re.findall(r"[A-Za-z_][\w-]*", v))
        elif isinstance(v, (list, tuple, set)):
            out.update(str(x) for x in v if x)
    return {t for t in out if t}


def _rule_props(rule):
    return {str(p[0]) for p in rule.get("p") or rule.get("props") or [] if p}


def _rule_selectors(rule):
    return list(rule.get("s") or [rule.get("selector")]) if rule.get("s") or rule.get("selector") else []


def _op_terms(op):
    tgt = op.get("target") or {}
    guard = tgt.get("guard") or {}
    rule = (op.get("new") or {}).get("rule") or {}
    prov = (op.get("original") or {}).get("provenance") or {}
    return _terms(rule.get("selector"), prov.get("selector"), guard.get("name"), guard.get("classes"))


def bundesliga_warnings(index, operations):
    """Rows where a Bundesliga rule setting colour/font/size matches an element an edit touches. Only the
    Bundesliga sheet is inspected here (it is the measured competition sheet; the same rule applies to any
    competition sheet listed in COMPETITION_SHEETS)."""
    if index is None:
        return []
    sheet = next((s for s in index.sheets if s.get("name") == BUNDESLIGA), None)
    if sheet is None:
        return []
    out = []
    for op in operations:
        if op.get("state") not in (None, "applied"):
            continue
        terms = _op_terms(op)
        if not terms:
            continue
        for rule in sheet.get("rules") or []:
            props = sorted(_rule_props(rule) & COLOUR_FONT_SIZE)
            if not props:
                continue
            hit = sorted(_terms(*(s for sel in _rule_selectors(rule) for s in [sel])) & terms)
            if not hit:
                continue
            out.append({"code": "competition_sheet_reach", "op_id": op.get("id"), "kind": op.get("kind"),
                        "sheet": BUNDESLIGA, "bundle": sheet.get("bundle"),
                        "selector": ", ".join(_rule_selectors(rule)),
                        "properties": props, "matched": hit,
                        "reason": ("the %s sheet sets %s on an element this edit touches (%s); the sheet is bound "
                                   "to the club's competition, so the preview only shows it when the competition "
                                   "context is on, and %s" % (BUNDESLIGA, ", ".join(props), ", ".join(hit), NOTE))})
    return out


def token_competition_sheets(index, operations):
    """For each ReplaceToken: the competition sheets that redefine that token (and, separately, competition-sheet
    uses inside the token's measured reach). A token change edits every definition, so a competition sheet's
    definition changes too unless the project chooses otherwise."""
    if index is None:
        return []
    out = []
    for op in operations:
        if op.get("kind") != "ReplaceToken" or op.get("state") not in (None, "applied"):
            continue
        token = (op.get("new") or {}).get("token")
        if not token:
            continue
        defs = []
        for sh in index.sheets:
            if sh.get("name") not in COMPETITION_SHEETS:
                continue
            hits = [r for r in sh.get("rules") or []
                    if r.get("t") and any(str(p[0]) == token for p in r.get("p") or [])]
            if hits:
                defs.append({"sheet": sh.get("name"), "bundle": sh.get("bundle"),
                             "definitions": len(hits),
                             "selectors": [", ".join(_rule_selectors(r)) for r in hits]})
        uses = []
        for sheet, selector, prop in sorted(index.reach(token)):
            if sheet in COMPETITION_SHEETS:
                uses.append({"sheet": sheet, "selector": selector, "property": prop})
        if defs or uses:
            out.append({"op_id": op.get("id"), "token": token, "redefined_by": defs,
                        "uses_in_reach": uses, "note": NOTE})
    return out


def warnings(index, operations, edit_competition_sheets=False):
    """The complete competition-context warning block for a plan/preview. `edit_competition_sheets` is the
    project option (OFF by default); it is reported, never assumed."""
    return {"bundesliga_rules": bundesliga_warnings(index, operations),
            "token_competition_sheets": token_competition_sheets(index, operations),
            "edit_competition_sheets": bool(edit_competition_sheets),
            "default": "off", "note": NOTE}
