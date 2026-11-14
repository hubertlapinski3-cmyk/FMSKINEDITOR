"""M3 exit comparison: assembled screens against the inspector captures of the same screens (docs/PHASE9-PLAN.md sections 5 and 8).

    python tools/m3_exit_compare.py [--out DIR]

Fixtures (all taken 2026-11-14, build 27.0.1.2503222, plugin 0.3.1-capture, AllowActions false):
  squad-large   Squad > Overview, panel 2500 x 1406.25            styles-d1-squad-overview-20261114-111054.ndjson
  squad-medium  Squad > Overview, Information Display Medium      styles-d6-squad-overview-medium-20261114-113402.ndjson
  squad-small-display  Squad > Overview, Small display, panel 1680 x 945 (Session E; a held-out grid size, 20 x 10 = the design size)  styles-e2-squad-small-20261114-115336.ndjson
  teaminstr     Tactics > Team Instructions, panel 2500           styles-d2-team-instructions-20261114-111314.ndjson
Tolerance (owner, section 8): a box passes when each of x, y, width, height is within 8 px or 5 percent of the measured size, whichever is tighter. Passes and failures are
both published, per element; nothing is filtered or re-toleranced. The comparison is against the MEASURED boxes of the inspector captures (the ground truth the plan's
fixtures use); pixel screenshots were not taken this session and are not compared.
Hosts the composition does not hold (the run-time-added slots) are GIVEN to the assembler from the capture (their cells), so they are listed as placeholders and are not
counted as predictions."""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from skin_editor import config, index_styles, layout_dump           # noqa: E402
from skin_editor.render import captures, screen                      # noqa: E402
from skin_editor.render.service import Renderer                      # noqa: E402

UI = Path(r"C:\Users\Admin\FMSKINNING\workspace\notes\ui-dumps")
AA = Path(r"C:\Program Files (x86)\Steam\steamapps\common\Football Manager 27\fm_Data\StreamingAssets\aa\StandaloneWindows64")
FIXTURES = [
    {"id": "squad-large", "file": "styles-d1-squad-overview-20261114-111054.ndjson", "composition": "SquadComposition-Large", "reserved_right": 0,
     "runtime": ["SquadHierachy", "MedicalCentre", "Loans"]},
    {"id": "squad-medium", "file": "styles-d6-squad-overview-medium-20261114-113402.ndjson", "composition": "SquadComposition-Large", "reserved_right": 0,
     "runtime": ["SquadHierachy"]},
    {"id": "squad-small-display", "file": "styles-e2-squad-small-20261114-115336.ndjson", "composition": "SquadComposition-Large", "reserved_right": 0, "runtime": []},
    {"id": "squad-small-composition", "file": "styles-e3-squad-1152x864-20261114-115626.ndjson", "composition": "SquadComposition-Small", "reserved_right": 0, "runtime": []},
    {"id": "squad-standard-composition", "file": "styles-e4-squad-1600x900-20261114-115839.ndjson", "composition": "SquadComposition-Standard", "reserved_right": 0, "runtime": []},
    {"id": "teaminstr", "file": "styles-d2-team-instructions-20261114-111314.ndjson", "composition": "TacticalPlannerTeamInstructionsTabComposition-Large",
     "reserved_right": 4, "runtime": ["ClubTeamReport", "SetPieces", "DataHub", "Penalties", "Captains"], "padding": 0},
]


def tol(measured):
    return min(8.0, 0.05 * measured) if measured else 8.0


def hosts_of(cap):
    return [e for e in cap.elements.values() if e["type"] == "BindableVariableSizedGridElement"]


def grid_parent(cap, fx):
    hs = hosts_of(cap)
    by = {}
    for h in hs:
        by.setdefault(h["path"].rsplit("/", 1)[0], []).append(h)
    names = {h["name"] for h in hs}
    want = "TeamInstructionsPitch" if fx["id"] == "teaminstr" else "FirstTeamOverview"
    for p, v in by.items():
        if any(h["name"] == want for h in v):
            return cap.elements[p], v
    raise SystemExit("no grid holds %s in %s" % (want, fx["file"]))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(ROOT / "docs" / "evidence"))
    a = ap.parse_args()
    ws = config.workspace(config.load())
    asm = screen.Assembler(layout_dump.load(ws))
    R = Renderer(AA, ws.cache, index_styles.load(ws))
    cat = {}
    for r in R.layouts.catalog():
        cat.setdefault(r["name"], r)
    report = {"schema": "fm-m3-exit/1", "tolerance": "8 px or 5 percent of the measured size, whichever is tighter", "fixtures": []}
    for fx in FIXTURES:
        cap = captures.read_capture(UI / fx["file"])
        parent, hosts = grid_parent(cap, fx)
        pw, ph = parent["world"][2], parent["world"][3]
        measured = {h["name"]: h for h in hosts}
        runtime = []
        for n in fx["runtime"]:
            if n in measured:
                px = measured[n]["inline"]
                g = lambda k: int(str(px[k]).replace("px", ""))
                pad = fx.get("padding", 12)
                runtime.append({"element_id": n, "col": round((g("left") - pad) / 82), "row": round((g("top") - pad) / 82), "w": round((g("width") + 16) / 82), "h": round((g("height") + 16) / 82)})
        res = asm.assemble(fx["composition"], (pw, ph), reserved_right=fx["reserved_right"], runtime_slots=runtime, padding=fx.get("padding", 12))
        rows = []
        ox, oy = parent["world"][0], parent["world"][1]
        for h in res["hosts"]:
            m = measured.get(h["element_id"])
            if not m:
                rows.append({"element": h["element_id"], "verdict": "NOT ON SCREEN (cell assembled, host absent in capture)", "expected": None})
                continue
            mx, my, mw, mh = m["world"]
            ex = [ox + h["px"]["left"], oy + h["px"]["top"], h["px"]["width"], h["px"]["height"]]
            got = [mx, my, mw, mh]
            delta = [round(e - g, 1) for e, g in zip(ex, got)]
            ok = all(abs(d) <= tol(s) for d, s in zip(delta, (mw, mh, mw, mh)))
            tile = None
            if h["tile_layout"] and h["tile_layout"] in cat:
                r = cat[h["tile_layout"]]
                lay = set()

                def walk(n):
                    if n["name"]:
                        lay.add((n["type"], n["name"]))
                    for c in n["children"]:
                        walk(c)
                for t in R.layout(r["bundle"], r["path_id"])["tree"]:
                    walk(t)
                sub = {(e["type"], e["name"]) for e in cap.elements.values() if e["path"].startswith(m["path"] + "/") and e["name"]}
                tile = {"layout": h["tile_layout"], "how": h["tile_how"], "named_elements": len(lay), "present_on_screen": len(lay & sub),
                        "all_present": lay <= sub}
            rows.append({"element": h["element_id"], "mode": h["mode"], "expected": [round(v, 1) for v in ex], "measured": [round(v, 1) for v in got], "delta": delta,
                         "verdict": "PASS" if ok else "FAIL", "tile": tile})
        placeholders = []
        for s in res["runtime_slots"]:
            m = measured.get(s["element_id"])
            placeholders.append({"element": s["element_id"], "given_cell": [s["col"], s["row"], s["w"], s["h"]], "measured": [round(v, 1) for v in m["world"]] if m else None,
                                 "category": "run-time-added slot without a default tile (placeholder)"})
        report["fixtures"].append({"id": fx["id"], "capture": fx["file"], "composition": fx["composition"], "grid_container": [round(pw, 1), round(ph, 1)], "grid": res["grid"],
                                   "pitch": res["pitch"], "rows": rows, "runtime_slots": placeholders, "flags": res["flags"],
                                   "passed": sum(1 for r in rows if r["verdict"] == "PASS"), "failed": sum(1 for r in rows if r["verdict"] == "FAIL")})
    out = Path(a.out) / "phase9-m3-exit-compare-20261114.json"
    out.write_text(json.dumps(report, indent=1), encoding="utf-8")
    for f in report["fixtures"]:
        print("== %s (%s) grid %s: %d pass, %d fail" % (f["id"], f["composition"], f["grid"], f["passed"], f["failed"]))
        for r in f["rows"]:
            t = r.get("tile")
            print("  %-4s %-30s %s expected %s measured %s%s" % (r["verdict"][:4], r["element"], r.get("mode"), r.get("expected"), r.get("measured"),
                  ("  tile %s %d/%d" % (t["layout"], t["present_on_screen"], t["named_elements"])) if t else ""))
        for s in f["runtime_slots"]:
            print("  PLACEHOLDER %s cell %s measured %s" % (s["element"], s["given_cell"], s["measured"]))
    print("report:", out)


if __name__ == "__main__":
    main()
