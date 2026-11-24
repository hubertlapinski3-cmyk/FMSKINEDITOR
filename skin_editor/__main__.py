"""python -m skin_editor [serve|detect|status|verify-stock|snapshot|index|new NAME [--preset crimson]|build NAME|reach NAME|check-layout DUMP|import-layout DUMP|install NAME|restore BACKUP|launcher [--dir DIR] [--yes]]"""
import argparse
import json
import multiprocessing
import os
import sys

from . import config, detect, index_styles, install, launcher, layout, layout_dump, patcher, server
from .presets import PRESETS
from . import project as project_mod


def main(argv=None):
    ap = argparse.ArgumentParser(prog="skin_editor")
    sub = ap.add_subparsers(dest="cmd")
    s = sub.add_parser("serve"); s.add_argument("--no-browser", action="store_true")
    sub.add_parser("detect"); sub.add_parser("status"); sub.add_parser("verify-stock", help="one line: are the game's UI bundles stock? exit code 0 = yes"); sub.add_parser("index")
    s = sub.add_parser("snapshot"); s.add_argument("--force", action="store_true")
    s = sub.add_parser("build"); s.add_argument("name")
    s = sub.add_parser("install"); s.add_argument("name"); s.add_argument("--force", action="store_true")
    s = sub.add_parser("restore"); s.add_argument("backup")
    s = sub.add_parser("new"); s.add_argument("name"); s.add_argument("--preset", choices=sorted(PRESETS))
    s = sub.add_parser("reach"); s.add_argument("name")
    s = sub.add_parser("launcher"); s.add_argument("--dir"); s.add_argument("--yes", action="store_true")
    s = sub.add_parser("record-reference"); s.add_argument("--force", action="store_true")
    s = sub.add_parser("check-layout"); s.add_argument("dump")
    s = sub.add_parser("import-layout"); s.add_argument("dump")
    sub.add_parser("paths")
    s = sub.add_parser("uidoc", help="read only: print a screen's UiDocument as JSON (Gate B of docs/UIDOCUMENT-AUDIT.md)")
    s.add_argument("--fixture", default="screen-team-instructions-large", help="a screen fixture under tests/fixtures/render (its composition, area, padding, reserved_right)")
    s.add_argument("--aa", help="the aa/StandaloneWindows64 folder to read (default: the configured game)"); s.add_argument("--dump", help="a fmlayout-index/2 file (default: the imported dump)")
    s.add_argument("--cache", help="the renderer's cache folder (default: a new folder of its own)"); s.add_argument("--build-label"); s.add_argument("--status"); s.add_argument("--label-source")
    s.add_argument("--computed", choices=["none", "summary", "full"], default="summary"); s.add_argument("--no-cascade", action="store_true"); s.add_argument("--order", choices=["natural", "reversed"], default="natural")
    s.add_argument("--out"); s.add_argument("--indent", action="store_true")
    s = sub.add_parser("fixture", help="render calibration fixtures: add one from a capture, or run them and publish the report")
    fs = s.add_subparsers(dest="fcmd")
    f = fs.add_parser("add"); f.add_argument("--name", required=True); f.add_argument("--capture", required=True); f.add_argument("--host", required=True, help="the host element of the subtree (e.g. Loans)")
    f.add_argument("--layout", required=True, help="the layout the host shows (e.g. LoansTile_4x2)"); f.add_argument("--screenshot"); f.add_argument("--project", help="a project model (JSON) the render applies")
    f.add_argument("--no-delivered", action="store_true", help="render with the layout's sample text instead of the captured text")
    f = fs.add_parser("run"); f.add_argument("--report", help="write calibration-report.json and .md to this folder"); f.add_argument("--only", action="append", default=[])
    s = sub.add_parser("methods", help="list the API methods"); s.add_argument("--markdown", action="store_true")
    s = sub.add_parser("rpc", help="call one API method: rpc METHOD ['{json params}']")
    s.add_argument("method"); s.add_argument("params", nargs="?", default="{}")
    s.add_argument("--data-file", help="file sent as the method's 'data' parameter")
    s.add_argument("--out", help="write a binary result to this file")
    s.add_argument("--no-wait", action="store_true", help="return a job id instead of waiting for the job")
    a = ap.parse_args(argv)
    if a.cmd in (None, "serve"):
        server.serve(False if getattr(a, "no_browser", False) else None)
        return 0
    if a.cmd == "check-layout":      # validates any file against the contract; needs neither a game nor a workspace
        try:
            r = layout_dump.check_file(a.dump)
        except layout_dump.LayoutError as ex:
            print(json.dumps({"valid": False, "errors": [str(ex)]}, indent=1))
            return 1
        print(json.dumps(r, indent=1))
        return 0 if r["valid"] else 1
    if a.cmd == "uidoc":
        from .uidoc import cli as uidoc_cli
        return uidoc_cli.run(a)
    if a.cmd == "fixture":
        from .render import fixtures
        if a.fcmd == "add":
            d = fixtures.add_from_capture(a.name, a.capture, a.host, a.layout, screenshot=a.screenshot, project_file=a.project, delivered=not a.no_delivered)
            print("created %s (boxes and values checks filled from the capture)" % d)
            return 0
        if a.fcmd == "run":
            ctx = fixtures.Context()
            res = fixtures.run_all(ctx, only=set(a.only))
            tot = {v: sum(r["counts"][v] for r in res) for v in ("PASS", "FAIL", "N/A")}
            for r in res:
                print("%-34s pass %-3d fail %-3d n/a %-3d" % (r["name"], r["counts"]["PASS"], r["counts"]["FAIL"], r["counts"]["N/A"]))
            print("TOTAL pass %(PASS)d fail %(FAIL)d n/a %(N/A)d" % tot)
            if a.report:
                fixtures.report(res, a.report)
                print("report written to", a.report)
            return 0
        print("usage: fixture add|run")
        return 2
    if a.cmd == "methods":
        from .api.methods import methods
        rows = [m.info() for m in methods().values()]
        if a.markdown:
            print("| Method | Kind | Parameters | HTTP route (first server) | What it does |\n|---|---|---|---|---|")
            for r in rows:
                ps = ", ".join("%s%s: %s" % (k, "" if v["required"] else "?", v["type"]) for k, v in r["params"].items())
                print("| `%s` | %s | %s | %s | %s |" % (r["name"], r["kind"], ps or "-", "`%s`" % r["http"] if r["http"] else "-", r["doc"]))
        else:
            print(json.dumps(rows, indent=1))
        return 0
    if a.cmd == "rpc":
        import base64
        from .api import rpc
        from .engine import Engine
        try:
            params = json.loads(a.params)
        except ValueError as ex:
            print("params must be JSON: %s" % ex, file=sys.stderr)
            return 2
        if a.data_file:
            params["data"] = base64.b64encode(open(a.data_file, "rb").read()).decode("ascii")
        eng = Engine()
        try:
            res = rpc.invoke(eng, a.method, params)
            if isinstance(res, dict) and "job" in res and not a.no_wait:
                res = eng.jobs.wait(res["job"]).view()
                if res["state"] != "done":
                    print(json.dumps(res, indent=1, default=str))
                    return 1
        except rpc.MethodNotFound:
            print("no such method: %s (see: python -m skin_editor methods)" % a.method, file=sys.stderr)
            return 2
        except Exception as ex:
            print(json.dumps({"error": rpc.error_of(ex)}, indent=1, default=str))
            return 1
        if a.out and isinstance(res, dict) and "base64" in res:
            open(a.out, "wb").write(base64.b64decode(res["base64"]))
            res = dict(res, base64="(%d bytes written to %s)" % (len(base64.b64decode(res["base64"])), a.out))
        print(json.dumps(res, indent=1, default=str))
        return 0
    cfg = config.load()
    ws = config.workspace(cfg)
    config.setup_logging(ws)
    out = lambda x: print(json.dumps(x, indent=1, default=str))
    if a.cmd == "import-layout":
        try:
            r = layout_dump.import_dump(ws, a.dump)
        except layout_dump.LayoutError as ex:
            print(json.dumps({"imported": False, "message": str(ex), "errors": ex.errors, "total_errors": ex.total}, indent=1))
            return 1
        out(r)
        if r["staleness"]["status"] != "fresh":
            print("WARNING: " + r["staleness"]["message"], file=sys.stderr)
        return 0
    if a.cmd == "paths":        # used by the launcher: port, then the state folder
        print(cfg["server"]["port"])
        print(ws.state)
        return 0
    if a.cmd == "launcher":
        p = launcher.plan(cfg)
        target = a.dir or p["target_dir"]
        print("Launcher: %s\nApp folder: %s\nWorkspace: %s\nPython environment: %s"
              % (os.path.join(target, launcher.APP_NAME), p["project"], p["workspace"], p["venv"]))
        if not p["macos"]:
            print("Note: this is not macOS; the generated app only runs on macOS.")
        if not a.yes and input("Create it there? [y/N] ").strip().lower() != "y":
            return 1
        out(launcher.generate(cfg, target))
        return 0
    if a.cmd == "detect":
        out(detect.find_installs())
        return 0
    info = detect.describe(cfg["game_dir"]) if cfg.get("game_dir") else None
    if not info:
        found = detect.find_installs()
        if len(found) != 1:
            print("set game_dir in %s (found %d installs)" % (ws.root / "config.json", len(found)), file=sys.stderr)
            return 2
        info = found[0]
    running = lambda: detect.game_running(info, cfg["process_names"]) or detect.steam_updating(info)
    prog = lambda msg, frac: print("%3d%% %s" % (frac * 100, msg), file=sys.stderr)
    if a.cmd == "status":
        out({"install": info, "running": running(), "live": install.live_status(ws, info["aa_dir"])})
    elif a.cmd == "verify-stock":
        from . import bundles as _b, profile
        man = ws.vanilla_manifest() or {}
        ref = (man.get("reference") or {}).get("bundles")
        if not ref:
            print("NOT VERIFIED: the snapshot has no reference hashes (run record-reference on a stock game)", file=sys.stderr)
            return 2
        from pathlib import Path as _P
        aa = _P(info["aa_dir"])
        bad = [n for n, h in ref.items() if not (aa / n).is_file() or _b.sha256(aa / n) != h]
        st = profile.status(ws, str(aa))
        print("%s: %d of %d UI bundles equal the stock reference hash; update status: %s" % ("STOCK" if not bad and st["state"] == "same" else "NOT STOCK", len(ref) - len(bad), len(ref), st["state"]))
        for n in bad:
            print("  differs from stock: %s" % n)
        if st["state"] != "same":
            print("  " + st["message"])
        return 0 if not bad and st["state"] == "same" else 1
    elif a.cmd == "snapshot":
        if running():
            print("close the game first", file=sys.stderr)
            return 2
        out(install.snapshot_vanilla(ws, info["aa_dir"], info.get("version"), a.force))
    elif a.cmd == "record-reference":
        if running():
            print("close the game first", file=sys.stderr)
            return 2
        try:
            out(install.record_reference_hashes(ws, info["aa_dir"], a.force))
        except install.InstallError as ex:
            print(str(ex), file=sys.stderr)
            return 2
    elif a.cmd == "index":
        ix = index_styles.build(ws, prog)
        out({"sheets": len(ix.sheets), "tokens": len(ix.defs), "literals": len(ix.literals),
             "quarantined": ix.quarantine()})
        if ix.failures:
            print("%d bundle colour entries are quarantined (outside 0..1): %s. See diagnostics/README.md"
                  % (len(ix.failures), ", ".join("%d %s" % (v["entries"], k) for k, v in ix.quarantine()["classes"].items())),
                  file=sys.stderr)
    elif a.cmd == "build":
        ix = index_styles.load(ws) or index_styles.build(ws, prog)
        rep = patcher.build(project_mod.load(ws, a.name), ws, ix, info["game_dir"], cfg["build"]["keep_last_builds"], prog)
        rep.pop("literal_hits"); rep.pop("spec")
        out(rep)
    elif a.cmd == "install":
        d = patcher.latest_build(ws, a.name)
        if not d:
            print("no build for " + a.name, file=sys.stderr)
            return 2
        out(install.install(ws, info["aa_dir"], d, running, a.force, cfg["install"]["backup_keep"]))
    elif a.cmd == "new":
        ix = index_styles.load(ws) or index_styles.build(ws, prog)
        p = PRESETS[a.preset](ix, a.name) if a.preset else project_mod.new(a.name, ix.meta.get("game_build"))
        project_mod.save(ws, p)
        out({k: len(v) for k, v in p.items() if isinstance(v, (list, dict))})
    elif a.cmd == "reach":
        out(layout.reach(project_mod.load(ws, a.name)["scoped_rules"], layout.load_trees(info["aa_dir"], ws.cache, prog)))
    elif a.cmd == "restore":
        out(install.restore(ws, info["aa_dir"], a.backup, running, cfg["install"]["backup_keep"]))
    return 0


if __name__ == "__main__":
    multiprocessing.freeze_support()
    sys.exit(main())
