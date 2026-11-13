"""Diagnostics for USS text, for the editor's markers. Facts come from the installed game's own sheets (the style index): the set of
properties it uses, the tokens it defines, the classes its selectors name. Severity: error = the game or the build will reject or
misread it; warning = probably a mistake; info = may be fine (a class can exist only in a layout).

Each item: {line, col, end_col, severity, code, message, suggest?}. `suggest` is a replacement for the highlighted text (a quick fix)."""
import difflib
import re

from . import colour, projfmt
from . import token_patch as tp

HEX = re.compile(r"#(?:[0-9A-Fa-f]{3,4}|[0-9A-Fa-f]{6}|[0-9A-Fa-f]{8})$")
NUM = re.compile(r"^-?(?:\d+\.?\d*|\.\d+)([a-zA-Z%]*)$")
UNITS_OK = {"", "px", "%", "deg", "grad", "rad", "turn", "s", "ms"}
VAR = re.compile(r"var\(\s*(--[\w-]+)")
CLASS = re.compile(r"\.([A-Za-z_][\w-]*)")


def facts(index):
    """(property names, token names, class names) the game's sheets use. Cached on the index object."""
    f = getattr(index, "_ussdiag_facts", None)
    if f is None:
        props, tokens, classes = set(), set(), set()
        for sh in index.sheets:
            for r in sh["rules"]:
                for s in r["s"]:
                    classes.update(CLASS.findall(s))
                for name, _, _ in r["p"]:
                    (tokens if name.startswith("--") else props).add(name)
        f = (props, tokens | set(index.defs), classes)
        index._ussdiag_facts = f
    return f


def _find(text_lines, line, needle, start=0):
    """1-based (col, end_col) of needle on the given 1-based line, or (1, len) when it is not found."""
    s = text_lines[line - 1] if 0 < line <= len(text_lines) else ""
    i = s.find(needle, start)
    return (i + 1, i + 1 + len(needle)) if i >= 0 else (1, max(2, len(s) + 1))


def check(text, index=None, sheet=None):
    """Diagnostics of one USS text. index=None: syntax only. sheet: the game sheet this file's rules go to (styles/<sheet>.uss);
    with it, a replace/remove that matches no game rule of that sheet is flagged."""
    lines = text.splitlines() or [""]
    out = []

    def add(line, needle, severity, code, message, suggest=None, start=0):
        col, end = _find(lines, line, needle, start)
        d = {"line": line, "col": col, "end_col": end, "severity": severity, "code": code, "message": message}
        if suggest is not None:
            d["suggest"] = suggest
        out.append(d)

    rules, problems = projfmt.parse_uss(text, "<text>")
    for p in problems:
        add(p.get("line") or 1, "", "error", "syntax", p["message"])
    if index is None:
        return out
    props, tokens, classes = facts(index)
    own = {k for r in rules if r["selector"] == ":root" for k, _, _, _ in r["decls"] if k.startswith("--")}
    known = {s["name"] for s in index.sheets}
    for r in rules:
        if r.get("op") and sheet in known:
            from . import plan
            if plan._hits(index, sheet, r["selector"]) == 0:
                add(r["line"], r["selector"], "warning", "no-game-rule", "%s: the game sheet %s has no rule with exactly this selector (a build would fail its gate)" % (r["op"], sheet))
        if r["selector"] != ":root":
            for sel in r["selector"].split(","):
                subject = re.split(r"[\s>]+", sel.strip())[-1] if sel.strip() else ""
                for c in CLASS.findall(subject):
                    if c not in classes:
                        add(r["line"], "." + c, "info", "class-unused", "class .%s is not used by any game stylesheet (it may still exist in a layout)" % c)
        for name, value, _meta, line in r["decls"]:
            if name.startswith("--"):
                pass
            elif name not in props:
                near = difflib.get_close_matches(name, props, 1, 0.8)
                add(line, name, "warning", "unknown-property", "unknown property %s%s" % (name, " (did you mean %s?)" % near[0] if near else ""), near[0] if near else None)
            for ref in VAR.findall(value):
                if ref not in tokens and ref not in own:
                    near = difflib.get_close_matches(ref, tokens, 1, 0.85)
                    add(line, ref, "warning", "unknown-token", "token %s is not defined in the game's sheets or in this file%s" % (ref, " (did you mean %s?)" % near[0] if near else ""), near[0] if near else None)
            v = value.strip()
            if v.startswith("#") and not HEX.match(v):
                add(line, v, "error", "bad-colour", "not a colour: %s (use #RGB, #RRGGBB or #RRGGBBAA)" % v)
            elif v.startswith("rgb"):
                try:
                    if colour.parse(v) is None:
                        raise ValueError
                except ValueError:
                    add(line, v, "error", "bad-colour", "not a colour: %s" % v)
            else:
                for tok in v.split():
                    m = NUM.match(tok)
                    if m and m.group(1) not in UNITS_OK:
                        add(line, tok, "warning", "unit", "unit %r is not supported by USS (px, %%, deg, s, ms ...)" % m.group(1))
    return out
