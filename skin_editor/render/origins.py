"""Where a project's own rules and token overrides live in its files (M6): the side panel opens the USS editor at the right line, and the editor's caret finds the elements a rule
styles. A rule the overlay appended carries `origin {kind, sheet, selector}`; here it is found in `styles/<sheet>.uss` by selector. Vanilla (game) rules have no origin: they are
read-only text, and the panel offers an override instead."""
import re

from .. import projfmt


def _norm(sel):
    return " ".join(sel.split())


def _lines(ws, project, rel):
    """[(selector, first line, last line)] of the rules of one project file, or [] when the file is missing (a legacy .skin.json project has none)."""
    try:
        text = projfmt.read_file(ws, project, rel)
    except Exception:
        return []
    rules, _problems = projfmt.parse_uss(text, rel)
    out = []
    for r in rules:
        last = max([d[3] for d in r["decls"]] or [r["line"]])
        out.append((_norm(r["selector"]), r["line"], last + 1))
    return out


def file_of(origin):
    return projfmt.TOKENS if origin.get("sheet") == "tokens" else "styles/%s.uss" % origin["sheet"]


def resolve(ws, project, top_nodes):
    """{rules: [{file, line, end, selector, sheet, ids: [{sheet, rule}]}], tokens: {token: {file, line}}}: every project rule that matched an element of this render, with the
    lines of its source, and every token the project overrides."""
    seen, ids = {}, {}
    stack = list(top_nodes)
    while stack:
        n = stack.pop()
        stack.extend(n.get("children", []))
        for m in n.get("matched", []):
            o = m.get("origin")
            if o:
                ids.setdefault((o["sheet"], _norm(o["selector"])), set()).add((m["sheet"], m["rule"]))
    cache = {}
    for (sheet, sel), idset in ids.items():
        rel = file_of({"sheet": sheet})
        cache.setdefault(rel, _lines(ws, project["name"], rel))
        hit = next((x for x in cache[rel] if x[0] == sel), None)
        seen[(sheet, sel)] = {"file": rel, "line": hit[1] if hit else None, "end": hit[2] if hit else None, "selector": sel, "sheet": sheet,
                              "ids": [{"sheet": s, "rule": r} for s, r in sorted(idset)]}
    tokens = {}
    wanted = [e["token"] for e in project.get("token_overrides", [])]
    if wanted:
        try:
            text = projfmt.read_file(ws, project["name"], projfmt.TOKENS)
        except Exception:
            text = ""
        for i, line in enumerate(text.splitlines(), 1):
            m = re.match(r"\s*(--[\w-]+)\s*:", line)
            if m and m.group(1) in wanted:
                tokens[m.group(1)] = {"file": projfmt.TOKENS, "line": i}
    return {"rules": list(seen.values()), "tokens": tokens}


def rule_text(rule):
    """USS text of one compiled rule (selectors, declarations)."""
    sels = ", ".join(sorted({c[2] for c in rule["chains"]}, key=lambda s: [c[2] for c in rule["chains"]].index(s)))
    body = "".join("  %s: %s;\n" % (n, v) for n, v, _c in rule["props"])
    return "%s {\n%s}" % (sels, body)
