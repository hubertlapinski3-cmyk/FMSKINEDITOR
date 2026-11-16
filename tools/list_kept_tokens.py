"""Session 2: the 148 colours the theme leaves at the game's own value, one row each, from the real style index (read only).

    python tools/list_kept_tokens.py [out.json]

For every `kept` token of data/simple/roles.json: its resolved value in this game build, its alias chain, how many rule paths use it, up to three of those rules (sheet, selector, property), its family (the part of the name
after the first prefix), and the white-on-it contrast ratio (the pairs the offline check cannot compute are white on these fills). The in-game column is empty here and is filled by the inspector, one call at a time,
in docs/evidence/phase9-simple-session-2-20261115.md; this file does not claim any token was seen in the game."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def main():
    from skin_editor import colour, config, index_styles, theme
    ix = index_styles.load(config.workspace(config.load()))
    assert ix is not None, "build the style index first"
    rm = theme.roles()
    rows = []
    for k in rm["kept"]:
        t = k["token"]
        r = ix.token_row(t)
        v = r["resolved"]
        reach = sorted(ix.reach(t))
        parts = t[2:].split("-")
        rows.append({"token": t, "group": "-".join(parts[:2]), "game_value": (v["rgb"] + ("" if v["a"] == 1.0 else " a=%s" % round(v["a"], 3))) if v else None, "crimson": k["crimson"],
                     "chain": r["chain"], "rules_using_it": r["reach"], "sample_rules": [list(x) for x in reach[:3]],
                     "white_on_it": round(theme.ratio((255, 255, 255), tuple(colour.from_obj(v)[:3])), 2) if v and v["a"] == 1.0 else None, "seen_in_game": None})
    groups = {}
    for r in rows:
        groups.setdefault(r["group"], []).append(r["token"])
    out = {"count": len(rows), "groups": {g: len(v) for g, v in sorted(groups.items(), key=lambda x: -len(x[1]))}, "rows": rows}
    text = json.dumps(out, indent=1)
    if len(sys.argv) > 1:
        Path(sys.argv[1]).write_text(text + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"count": out["count"], "groups": out["groups"], "no_rules": sum(1 for r in rows if not r["rules_using_it"])}, indent=1))


if __name__ == "__main__":
    main()
