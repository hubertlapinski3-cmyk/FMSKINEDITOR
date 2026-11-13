"""Print a decoded stylesheet (index_styles.sheet_entry) as USS text, and prove the text parses back to the same rules.

The round trip decode -> print -> parse is the property the USS tooling relies on: whatever the editor shows for a vanilla sheet,
and whatever it writes back, means the same rules and declarations. `model()` is the comparable form (selectors text and
declaration (property, value) pairs per rule, whitespace collapsed); `roundtrip()` returns the differences, empty when equal."""
from . import projfmt


def _ws(s):
    return " ".join(str(s).split())


def model(entry):
    """[(selectors text, [(property, value)])] of a decoded sheet, in rule order."""
    return [(_ws(", ".join(r["s"])), [(_ws(n), _ws(v)) for n, v, _ in r["p"]]) for r in entry["rules"]]


def print_sheet(entry, header=True):
    out = ["/* %s (decoded from %s) */" % (entry["name"], entry.get("bundle", "?"))] if header else []
    for sel, decls in model(entry):
        out.append("%s {" % (sel or "*"))
        out += ["    %s: %s;" % (n, v) for n, v in decls]
        out.append("}")
    return "\n".join(out) + "\n"


def parse_model(text):
    """The same comparable form, from USS text. Returns (model, problems)."""
    rules, problems = projfmt.parse_uss(text, "<sheet>")
    return [(_ws(r["selector"]), [(_ws(k), _ws(v)) for k, v, _, _ in r["decls"]]) for r in rules], problems


def roundtrip(entry):
    """Differences between a decoded sheet and its printed-then-parsed form: [] when they are equal."""
    want = model(entry)
    want = [(s or "*", d) for s, d in want]
    got, problems = parse_model(print_sheet(entry))
    diffs = ["parse problem: %s line %s: %s" % (p["file"], p.get("line"), p["message"]) for p in problems[:5]]
    if len(got) != len(want):
        diffs.append("rule count %d != %d" % (len(got), len(want)))
    for i, (a, b) in enumerate(zip(want, got)):
        if a != b:
            diffs.append("rule %d differs: %r vs %r" % (i, a[0][:80], b[0][:80]) if a[0] != b[0] else "rule %d (%s) declarations differ" % (i, a[0][:60]))
            if len(diffs) >= 8:
                break
    return diffs
