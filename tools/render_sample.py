"""Phase 9 M2 evidence: render layouts end to end and report what happened, failures included.

    python tools/render_sample.py [--all | --sample N] [--seed S] [--out FILE]

For each layout: the first call (decode from the bundle or the disk cache, expand includes by GUID, cascade) and a second call (everything cached). Records elements, unresolved
includes, flagged properties, the size of the JSON the render call returns, and any exception. Exit criterion (docs/PHASE9-PLAN.md section 9): any of the 7,467 layouts renders
as a tree; the cached call is under 200 ms at p95 on a 100-layout sample. Failures are listed, never skipped."""
import argparse
import json
import random
import statistics
import sys
import time
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from skin_editor import config, index_styles                    # noqa: E402
from skin_editor.render.html import flatten                      # noqa: E402
from skin_editor.render.service import Renderer                  # noqa: E402

AA = r"C:\Program Files (x86)\Steam\steamapps\common\Football Manager 27\fm_Data\StreamingAssets\aa\StandaloneWindows64"


def pct(v, p):
    v = sorted(v)
    return v[min(len(v) - 1, int(len(v) * p))] if v else None


def main():
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--all", action="store_true")
    g.add_argument("--sample", type=int, default=100)
    ap.add_argument("--seed", type=int, default=27)
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    ws = config.workspace(config.load())
    R = Renderer(AA, ws.cache, index_styles.load(ws))
    # the full catalog, not layout_list: that call is capped at 1,000 rows for the browser, which would silently turn "all" into the 1,000 shortest names
    rows = sorted(({"name": r["name"], "bundle": r["bundle"], "path_id": r["path_id"], "elements": r["elements"]} for r in R.layouts.catalog()),
                  key=lambda r: (r["name"], r["bundle"], r["path_id"]))
    if not a.all:
        random.Random(a.seed).shuffle(rows)
        rows = rows[:a.sample]
    res, fails, t_start = [], [], time.perf_counter()
    for i, r in enumerate(rows):
        rec = {"name": r["name"], "bundle": r["bundle"], "path_id": r["path_id"], "declared_elements": r["elements"]}
        try:
            t0 = time.perf_counter()
            out = R.layout(r["bundle"], r["path_id"])
            rec["first_ms"] = round((time.perf_counter() - t0) * 1000, 1)
            t0 = time.perf_counter()
            out2 = R.layout(r["bundle"], r["path_id"])
            rec["cached_ms"] = round((time.perf_counter() - t0) * 1000, 1)
            nodes = flatten(out2["tree"])
            rec["elements"] = len(nodes)
            rec["includes"] = len(out2["includes"])
            rec["unresolved_includes"] = sum(1 for x in out2["includes"] if not x.get("resolved"))
            rec["flagged"] = sum(1 for n in nodes if n.get("flag"))
            rec["unresolved_variables"] = sum(out2["summary"]["unresolved_variables"].values())
            rec["json_kb"] = round(len(json.dumps(out2["tree"])) / 1024, 1)
        except Exception as e:                                           # a failure is recorded and reported, never hidden
            rec["error"] = "%s: %s" % (type(e).__name__, str(e)[:200])
            rec["trace"] = traceback.format_exc()[-600:]
            fails.append(rec)
        res.append(rec)
        if (i + 1) % 500 == 0:
            print("  %d/%d  %.0f s" % (i + 1, len(rows), time.perf_counter() - t_start), flush=True)
    if a.all and len(rows) != R.layouts.catalog().__len__():
        raise SystemExit("internal check failed: --all rendered %d of %d layouts" % (len(rows), len(R.layouts.catalog())))
    ok = [r for r in res if "error" not in r]
    cached = [r["cached_ms"] for r in ok]
    first = [r["first_ms"] for r in ok]
    report = {
        "layouts": len(rows), "rendered": len(ok), "failed": len(fails), "seed": None if a.all else a.seed, "all": a.all,
        "cached_ms": {"p50": statistics.median(cached) if cached else None, "p95": pct(cached, 0.95), "p99": pct(cached, 0.99), "max": max(cached) if cached else None},
        "first_ms": {"p50": statistics.median(first) if first else None, "p95": pct(first, 0.95), "max": max(first) if first else None},
        "over_200ms_cached": [r["name"] for r in ok if r["cached_ms"] > 200][:20],
        "unresolved_includes": {"layouts": sum(1 for r in ok if r["unresolved_includes"]), "includes": sum(r["unresolved_includes"] for r in ok)},
        "elements_total": sum(r["elements"] for r in ok), "flagged_elements": sum(r["flagged"] for r in ok),
        "unresolved_variable_uses": sum(r["unresolved_variables"] for r in ok),
        "json_kb": {"p50": statistics.median([r["json_kb"] for r in ok]) if ok else None, "p95": pct([r["json_kb"] for r in ok], 0.95), "max": max([r["json_kb"] for r in ok]) if ok else None},
        "biggest": sorted(ok, key=lambda r: -r["elements"])[:5] and [(r["name"], r["elements"], r["cached_ms"], r["json_kb"]) for r in sorted(ok, key=lambda r: -r["elements"])[:5]],
        "seconds": round(time.perf_counter() - t_start, 1), "failures": fails[:50], "game": "27.0.1.2503222"}
    out = Path(a.out) if a.out else ws.cache / ("render-sample-%s.json" % ("all" if a.all else a.sample))
    out.write_text(json.dumps({"report": report, "rows": res}, indent=1), encoding="utf-8")
    print(json.dumps({k: v for k, v in report.items() if k != "failures"}, indent=1))
    for f in fails[:10]:
        print("FAIL", f["name"], f["error"])
    print("written:", out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
