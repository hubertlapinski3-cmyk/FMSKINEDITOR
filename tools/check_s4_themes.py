"""S4 of the Simple mode plan: check the theme generator against the REAL style index of this game build, offline, and write the figures the S4 report quotes.

    python tools/check_s4_themes.py [out.json]

The game is only read (the index the Studio already built); projects go to a scratch workspace and the native export to a scratch skins folder, both deleted after.
For Crimson's own three colours and every gallery theme (and every removed one): the contrast result against the game's live index values, and that the role map's
tokens all exist in this build. One gallery theme is exported natively and the tokens written are counted. Every figure in the report comes from this output."""
import json
import sys
import tempfile
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def main():
    from skin_editor import config, index_styles, native, theme
    from skin_editor.api import rpc
    from tests.test_api import close_logs, engine
    ix = index_styles.load(config.workspace(config.load()))
    assert ix is not None, "build the style index first"
    rm = theme.roles()
    gal = json.loads((ROOT / "data" / "simple" / "gallery.json").read_text(encoding="utf-8"))
    out = {"role_map": rm["summary"], "references": rm["references"], "missing_in_this_build": sorted(e["token"] for e in rm["entries"] if e["token"] not in ix.defs)}

    def reach(tokens):
        s = set()
        for t in tokens:
            s |= ix.reach(t)
        return len(s)
    used_colour = [n for n in ix.defs if ix.token_row(n)["reach"] and ix.token_row(n)["resolved"]]
    # one method for all three (the index's reach, rule paths): what a generated theme writes, what Crimson writes (written + kept), and every used colour token
    out["reach"] = {"used_colour_tokens": len(used_colour), "rule_paths_used_colour_tokens": reach(used_colour),
                    "rule_paths_theme_writes": reach(e["token"] for e in rm["entries"]),
                    "rule_paths_crimson_writes": reach([e["token"] for e in rm["entries"]] + [k["token"] for k in rm["kept"]])}
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        e = engine(tmp); e.index = ix
        skins = Path(tmp) / "skins"; skins.mkdir()

        def call(m, p=None):
            return json.loads(rpc.handle(e, json.dumps({"jsonrpc": "2.0", "id": 1, "method": m, "params": p or {}})))

        def check(name, t):
            resp = call("theme.generate", {k: t[k] for k in ("background", "accent", "text", "mode")})
            if "error" in resp:                                          # light inputs since the S4 amendment (owner decision 1)
                return {"name": name, "inputs": {k: t[k] for k in ("background", "accent", "text", "mode")}, "refused": resp["error"]["data"]["plain"]}
            r = resp["result"]
            c = r["contrast"]
            badge = next(rw for rw in theme.contrast(theme.generate(t["background"], t["accent"], t["text"], t["mode"]), e._game_colour)["rows"]
                         if rw["fg"] == "--data-player-position-defender-foreground")
            # the recorded game values (what tests and CI use) must give the same answer as the live index
            rec = theme.contrast(theme.generate(t["background"], t["accent"], t["text"], t["mode"]), theme.recorded_game_value)
            return {"name": name, "inputs": r["inputs"], "ok": r["ok"], "writes": r["writes"], "keeps": r["keeps"], "checked": c["checked"], "unchecked": len(c["unchecked"]),
                    "failures": [(f["fg"], f["bg"], f["ratio"]) for f in c["failures"]], "game_failures": [(f["fg"], f["bg"], f["ratio"]) for f in c["game_failures"]],
                    "badge": {"ratio": badge["ratio"], "set_by_theme": badge["touched"], "pass": badge["pass"]},
                    "game_low": [(x["fg"], x["bg"], x["game_ratio"], x["ratio"], "corrected" if x["corrected"] else "NOT corrected") for x in c["game_low"]],
                    "lowest_touched": min((rw["ratio"] for rw in rec["rows"] if rw["touched"]), default=None),
                    "recorded_values_agree": [f["fg"] + f["bg"] for f in rec["failures"]] == [f["fg"] + f["bg"] for f in c["failures"]] and rec["checked"] == c["checked"]}
        cr = {"background": rm["ramps"]["neutral"][rm["references"]["neutral"]], "accent": rm["ramps"]["accent"][rm["references"]["accent"]], "text": rm["ramps"]["text"][rm["references"]["text"]], "mode": "dark"}
        out["crimson_inputs"] = check("Crimson's own colours", cr)
        out["gallery"] = [check(t["name"], t) for t in gal["themes"]]
        out["removed"] = [check(r["name"], r["inputs"]) for r in gal["removed"]]
        out["fixed_before"] = []
        names = {t["name"]: t for t in gal["themes"]}
        for f in gal["fixed"]:
            t = dict(names[f["name"]]); t["background"] = f["changed"].split()[1]
            out["fixed_before"].append(check(f["name"] + " before the fix", t))
        g = gal["themes"][0]
        made = call("theme.create", {"name": "s4-check", **{k: g[k] for k in ("background", "accent", "text", "mode")}})
        assert "error" not in made, made
        with mock.patch.object(native, "skins_root", lambda: skins):
            job = call("native.put", {"project": "s4-check"})["result"]["job"]
            res = call("jobs.wait", {"id": job, "timeout": 120})["result"]
        out["export"] = {"theme": g["name"], "state": res["state"], "tokens_written": (res.get("result") or {}).get("tokens"), "problems": (res.get("result") or {}).get("problems")}
        close_logs()
    text = json.dumps(out, indent=1)
    if len(sys.argv) > 1:
        Path(sys.argv[1]).write_text(text + "\n", encoding="utf-8", newline="\n")
    print(text)


if __name__ == "__main__":
    main()
