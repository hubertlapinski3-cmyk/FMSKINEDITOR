"""Phase 9 M0 spike: render one layout offline and compare its geometry with an inspector tree dump.

    python tools/render_spike.py [--dump FILE] [--bundle B --path-id P] [--width W --height H] [--out DIR]

Pipeline: layout bundle -> parsed layout (cached) -> includes by GUID -> cascade -> render tree -> HTML -> headless Edge measures every box -> compared with the
inspector's bounds for the same elements (`fm_dump_tree` JSON: {"nodes": {path: {"label", "bounds": [x, y, w, h]}}}).

Tolerance (owner, docs/PHASE9-PLAN.md section 8): a size passes within 8 px or 5 percent of the measured size, whichever is tighter; a position passes within 8 px or
5 percent of the measured root size, whichever is tighter. Passes and failures are both printed and written; nothing is filtered.
Default target: LoansTile_4x2 against the c2 session's dump (2026-11-13, build 27.0.1.2503222, Small + Larger text)."""
import argparse
import json
import re
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from skin_editor import config, index_styles                    # noqa: E402
from skin_editor.render.html import flatten, to_html            # noqa: E402
from skin_editor.render.service import Renderer                 # noqa: E402

EDGE = [r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe", r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"]
AA = r"C:\Program Files (x86)\Steam\steamapps\common\Football Manager 27\fm_Data\StreamingAssets\aa\StandaloneWindows64"
DUMP = r"C:\Users\Admin\FMSKINNING\workspace\notes\ui-dumps\c2-loans-tile-tree-27_0_1_2503222-20261113.json"
LAYOUT = ("ui-visualtreeassets_assets_gameworldvisualtreeassetpreload.bundle", "-3957983696827071101")
LABEL = re.compile(r"^([A-Za-z0-9_`]+)(?:#([^.]*))?")


def measure(html_text, out_dir, shot=None, size=(0, 0)):
    edge = next((e for e in EDGE if Path(e).is_file()), None)
    if not edge:
        raise SystemExit("Microsoft Edge not found")
    f = Path(out_dir) / "spike.html"
    f.write_text(html_text, encoding="utf-8")
    # Edge's own stdout is not attached here, so the page's boxes are read through its DevTools port (tools/cdp_measure.mjs). Its own profile folder keeps it away
    # from the user's browser, and every process started with that profile is closed afterwards.
    port = 9340 + (int(time.time()) % 50)
    profile = Path(out_dir) / "spike-edge-profile"
    proc = subprocess.Popen([edge, "--headless=new", "--disable-gpu", "--no-first-run", "--no-default-browser-check", "--user-data-dir=%s" % profile,
                             "--remote-debugging-port=%d" % port, f.as_uri()], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        r = subprocess.run(["node", str(ROOT / "tools" / "cdp_measure.mjs"), str(port), "spike.html"] + ([str(shot), str(size[0]), str(size[1])] if shot else []), capture_output=True, text=True, timeout=120)
    finally:
        subprocess.run(["powershell", "-NoProfile", "-Command",
                        "Get-CimInstance Win32_Process -Filter \"Name='msedge.exe'\" | Where-Object { $_.CommandLine -like '*spike-edge-profile*' } | "
                        "ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }"], capture_output=True)
        proc.kill()
    if r.returncode != 0 or not r.stdout.strip():
        raise SystemExit("no measurement: " + r.stderr[:300])
    return {int(k): v for k, v in json.loads(r.stdout.strip()).items()}


def inspector_nodes(dump):
    doc = json.loads(Path(dump).read_text(encoding="utf-8"))
    rows = []
    for path, n in doc["nodes"].items():
        m = LABEL.match(n.get("label", ""))
        if m and n.get("bounds"):
            rows.append({"path": path, "type": m.group(1), "name": m.group(2) or "", "label": n["label"], "b": n["bounds"], "depth": n.get("depth")})
    return rows


def tol(expected, ref):
    return min(8.0, 0.05 * (expected if expected > 0 else ref))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dump", default=DUMP)
    ap.add_argument("--bundle", default=LAYOUT[0])
    ap.add_argument("--path-id", default=LAYOUT[1])
    ap.add_argument("--branch", action="append", default=[], help="SWITCH_ORDINAL:BRANCH, which branch of the nth switch (depth-first) is live; default 0")
    ap.add_argument("--infer-branches", action="store_true", help="choose each switch's live branch from the dump (structural overlap of named visible elements)")
    ap.add_argument("--shot", help="also save a 2x PNG screenshot of the render to this path")
    ap.add_argument("--out", default=str(Path(config.load().get("workspace") or ".")))
    a = ap.parse_args()
    out_dir = Path(a.out) if Path(a.out).is_dir() else Path(".")
    ws = config.workspace(config.load())
    R = Renderer(AA, ws.cache, index_styles.load(ws))
    ins = inspector_nodes(a.dump)
    doc_nodes = json.loads(Path(a.dump).read_text(encoding="utf-8"))["nodes"]
    # the tile's host container is the first inspector node named like a tile; the layout's top node (BindingExpect#TileBindingExpect) starts after it
    start = next((i for i, r in enumerate(ins) if r["name"] == "TileBindingExpect"), 0)
    root_b = ins[start]["b"]
    W, H = root_b[2], root_b[3]
    t0 = time.perf_counter()
    chosen = {int(x.split(':')[0]): int(x.split(':')[1]) for x in a.branch}
    if a.infer_branches:
        from skin_editor.render import captures
        elems = [{"type": r["type"], "name": r["name"], "visible": n.get("visible", True)} for r, n in zip(ins, [doc_nodes[r["path"]] for r in ins])]
        inf = captures.infer_branches(R.layout(a.bundle, a.path_id)["tree"], elems)
        chosen = dict(inf["branches"], **chosen)
        print("inferred branches:", inf["branches"], "scores", inf["scores"])
    res = R.layout(a.bundle, a.path_id, branches=chosen)
    render_ms = (time.perf_counter() - t0) * 1000
    html_text, nodes = to_html(res["tree"], W, H, res["layout"])
    rects = measure(html_text, ws.cache, a.shot, (W, H))
    # greedy in-order matching of render nodes to inspector nodes by (type, name)
    hidden = set()                                  # nodes inside a switch branch the render does not show: not compared, listed as such

    def mark(n, h):
        h = h or "switch-branch-not-shown" in (n.get("layout_rules") or ())
        if h:
            hidden.add(id(n))
        for c in n.get("children", []):
            mark(c, h)
    for top in res["tree"]:
        mark(top, False)
    pos, rows = start, []
    for i, n in enumerate(nodes):
        if id(n) in hidden:
            rows.append({"i": i, "node": "%s#%s" % (n["type"], n.get("name", "")), "verdict": "HIDDEN BRANCH (switch)"})
            continue
        j = next((k for k in range(pos, len(ins)) if ins[k]["type"] == n["type"] and ins[k]["name"] == (n.get("name") or "")), None)
        if j is None:
            rows.append({"i": i, "node": "%s#%s" % (n["type"], n.get("name", "")), "verdict": "NOT IN INSPECTOR DUMP"})
            continue
        pos = j + 1
        e = ins[j]["b"]
        ex, ey, ew, eh = e[0] - root_b[0], e[1] - root_b[1], e[2], e[3]
        gx, gy, gw, gh = rects[i]
        errs = {"x": gx - ex, "y": gy - ey, "w": gw - ew, "h": gh - eh}
        ok = {"x": abs(errs["x"]) <= tol(ew, W), "y": abs(errs["y"]) <= tol(eh, H), "w": abs(errs["w"]) <= tol(ew, W), "h": abs(errs["h"]) <= tol(eh, H)}
        rows.append({"i": i, "node": "%s#%s" % (n["type"], n.get("name", "")), "expected": [round(ex, 1), round(ey, 1), round(ew, 1), round(eh, 1)],
                     "got": [round(gx, 1), round(gy, 1), round(gw, 1), round(gh, 1)], "delta": {k: round(v, 1) for k, v in errs.items()}, "pass": ok,
                     "verdict": "PASS" if all(ok.values()) else "FAIL"})
    compared = [r for r in rows if "expected" in r]
    report = {"layout": res["layout"], "dump": a.dump, "root_size": [W, H], "render_ms_warm_first_call_included": round(render_ms, 1), "timing_ms": res["timing_ms"],
              "compared": len(compared), "passed": sum(r["verdict"] == "PASS" for r in compared), "failed": sum(r["verdict"] == "FAIL" for r in compared),
              "not_in_dump": sum(r["verdict"].startswith("NOT") for r in rows), "hidden_branch": sum(r["verdict"].startswith("HIDDEN") for r in rows), "rows": rows}
    p = ws.cache / "render-spike-report.json"
    p.write_text(json.dumps(report, indent=1), encoding="utf-8")
    print("layout %s against %s: root %.1f x %.1f; compared %d: %d pass, %d fail; %d render nodes not in the dump" %
          (res["layout"], Path(a.dump).name, W, H, report["compared"], report["passed"], report["failed"], report["not_in_dump"]))
    for r in rows:
        if "expected" in r:
            print("%-4s %-70s expected %-30s got %-30s delta %s" % (r["verdict"], r["node"][:70], r["expected"], r["got"], r["delta"]))
        else:
            print("---- %-70s %s" % (r["node"][:70], r["verdict"]))
    print("report:", p)
    return 0


if __name__ == "__main__":
    sys.exit(main())
