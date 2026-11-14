"""The computed diff between two calibration report JSON files (a frozen one and a new one), by row key (fixture, check, element, property, occurrence).

    python tools/diff_reports.py OLD.json NEW.json OUT.md

Rows with the same key are compared on verdict, expected and got; rows only in one report are listed by fixture and verdict."""
import collections
import json
import sys
from pathlib import Path


def keyed(doc):
    seen, out = collections.Counter(), {}
    for f in doc["fixtures"]:
        for x in f["rows"]:
            k = (f["name"], x["check"], x["element"], x["property"])
            seen[k] += 1
            out[k + (seen[k],)] = x
    return out


def main(old_f, new_f, out_f):
    old, new = json.loads(Path(old_f).read_text(encoding="utf-8")), json.loads(Path(new_f).read_text(encoding="utf-8"))
    o, n = keyed(old), keyed(new)
    both = set(o) & set(n)
    flipped = [k for k in both if o[k]["verdict"] != n[k]["verdict"]]
    moved = [k for k in both if o[k]["verdict"] == n[k]["verdict"] and (o[k]["expected"] != n[k]["expected"] or o[k]["got"] != n[k]["got"])]
    only_old, only_new = [k for k in o if k not in n], [k for k in n if k not in o]
    t = lambda d: {k: d["totals"][k] for k in ("PASS", "FAIL", "N/A")}
    lines = ["# Diff of the new calibration report against the frozen one (computed)", "", "Totals: frozen %s, new %s." % (t(old), t(new)), "",
             "Rows with the same key in both: %d. Verdict flipped: %d. Same verdict but another expected or got value: %d. Only in the frozen report: %d. Only in the new report: %d." % (len(both), len(flipped), len(moved), len(only_old), len(only_new)), ""]
    for title, keys, src in (("Verdict flipped (frozen -> new)", flipped, None), ("Only in the frozen report (rows no longer emitted or re-keyed)", only_old, o), ("Only in the new report", only_new, n)):
        c = collections.Counter()
        for k in keys:
            if src is None:
                c[(k[0], o[k]["verdict"] + " -> " + n[k]["verdict"])] += 1
            else:
                c[(k[0], src[k]["verdict"])] += 1
        lines += ["## " + title, ""] + ["- %s: %s x %d" % (f, v, cnt) for (f, v), cnt in sorted(c.items())] + [""]
    Path(out_f).write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines[:6]))


if __name__ == "__main__":
    main(*sys.argv[1:4])
