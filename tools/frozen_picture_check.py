"""Run a FROZEN engine (the installed app's, or a fresh build) against the real game files in a SCRATCH workspace and record what its picture path does.

    python tools/frozen_picture_check.py --exe <fm-skin-engine.exe> --label "installed 1.1.0 (before the fix)" --out docs/evidence/phase9-v111-frozen-picture-check-20261115.json [--sample 40] [--all-icons]

What it does: starts the engine in a temporary workspace (nothing of the real workspace is touched; the game folder is only READ), reads the game (detect, snapshot, index), asks for the picture
catalogue, counts it by kind, then asks for thumbnails: the first N of each kind (N = --sample, in catalogue order), and with --all-icons every icon. A failure keeps the engine's own message.
The result is APPENDED to the output file (one record per run, none replaced), so a before and an after sit side by side. It is the source of every figure the 1.1.1 release notes quote."""
import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path


def rpc(port, token, method, params=None, timeout=120):
    req = urllib.request.Request("http://127.0.0.1:%s/rpc" % port, data=json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": params or {}}).encode(),
                                 headers={"X-Token": token, "Content-Type": "application/json"})
    try:
        return json.loads(urllib.request.urlopen(req, timeout=timeout).read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        return json.loads(e.read().decode("utf-8"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--exe", required=True); ap.add_argument("--label", required=True); ap.add_argument("--out", required=True)
    ap.add_argument("--sample", type=int, default=40); ap.add_argument("--all", action="store_true", help="ask for EVERY picture of every kind, not only the sample"); ap.add_argument("--port", type=int, default=8796)
    a = ap.parse_args()
    source = a.exe == "SOURCE"                         # --exe SOURCE: the engine run from the source tree (`python -m skin_editor serve`), as the reference the frozen builds are compared with
    exe = Path(sys.executable) if source else Path(a.exe)
    root = Path(__file__).resolve().parent.parent
    ws = Path(tempfile.mkdtemp(prefix="picture-check-"))
    (ws / "config.json").write_text(json.dumps({"server": {"port": a.port}}), encoding="utf-8")
    env = dict(os.environ, FM27SE_WORKSPACE=str(ws))
    out_f, err_f = open(ws / "out.txt", "w"), open(ws / "err.txt", "w")
    cmd = [str(exe), "-m", "skin_editor", "serve", "--no-browser"] if source else [str(exe), "serve", "--no-browser"]
    p = subprocess.Popen(cmd, env=env, stdout=out_f, stderr=err_f, creationflags=0x08000000, cwd=str(root) if source else None)
    rec = {"label": a.label, "exe": ("python -m skin_editor (source tree, Python %s)" % sys.version.split()[0]) if source else str(exe), "exe_bytes": 0 if source else exe.stat().st_size, "exe_sha256": "n/a (source)" if source else hashlib.sha256(exe.read_bytes()).hexdigest().upper(), "sample_per_kind": a.sample, "all": a.all}
    try:
        url = ""
        for _ in range(60):
            time.sleep(0.5); out_f.flush()
            url = (ws / "out.txt").read_text(encoding="utf-8", errors="replace").strip()
            if url.startswith("http"):
                break
        m = re.match(r"http://127\.0\.0\.1:(\d+)/\?t=(\S+)", url)
        if not m:
            raise SystemExit("the engine did not start: %r" % url)
        port, tok = m.group(1), m.group(2)
        rpc(port, tok, "game.detect"); r = rpc(port, tok, "snapshot.take")
        if "error" in r:
            raise SystemExit("snapshot: " + r["error"]["message"])
        j = rpc(port, tok, "index.build"); w = rpc(port, tok, "jobs.wait", {"id": j["result"]["job"], "timeout": 120})
        rec["index"] = w["result"]["state"]
        rows = rpc(port, tok, "images.catalog")["result"]
        kinds = {}
        for r_ in rows:
            kinds[r_["kind"]] = kinds.get(r_["kind"], 0) + 1
        rec["catalogue"] = {"total": len(rows), "by_kind": kinds}

        def thumbs(label, subset):
            ok, bad, first, why = 0, 0, None, {}
            for r_ in subset:
                t = rpc(port, tok, "images.thumb", {"bundle": r_["bundle"], "path_id": r_["path_id"]})
                if "error" in t:
                    bad += 1; first = first or {"name": r_["name"], "message": t["error"]["message"][:400]}
                    key = re.sub(r"-?\d{6,}", "<id>", re.sub(r"'[^']*'", "'<path>'", t["error"]["message"]))[:110]
                    why[key] = why.get(key, 0) + 1
                else:
                    ok += 1
            return {"asked": len(subset), "ok": ok, "failed": bad, "first_failure": first, "failures_by_message": why}
        rec["sample"] = {k: thumbs(k, [r_ for r_ in rows if r_["kind"] == k][:a.sample]) for k in ("icon", "svg", "texture")}
        if a.all:
            rec["everything"] = {k: thumbs(k, [r_ for r_ in rows if r_["kind"] == k]) for k in ("icon", "svg", "texture")}
        # a call that fails on purpose, to see whether the engine leaves a traceback in its log
        rpc(port, tok, "jobs.get", {"id": "picture-check-no-such-job"})
    finally:
        p.kill(); p.wait(); out_f.close(); err_f.close()
        time.sleep(0.5)
        log = ws / "logs" / "app.log"
        text = log.read_text(encoding="utf-8", errors="replace") if log.is_file() else ""
        rec["log"] = {"exists": log.is_file(), "bytes": len(text.encode("utf-8")), "has_traceback_for_the_deliberate_failure": ("rpc jobs.get failed" in text and "Traceback" in text)}
        shutil.rmtree(ws, ignore_errors=True)
    path = Path(a.out)
    data = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {"note": "Runs of tools/frozen_picture_check.py: a frozen engine against the real game files in a scratch workspace. One record per run, none replaced.", "runs": []}
    rec["run"] = len(data["runs"]) + 1
    data["runs"].append(rec)
    path.write_text(json.dumps(data, indent=1), encoding="utf-8", newline="\n")
    summary = {k: rec[k] for k in ("label", "catalogue", "log") if k in rec}
    summary["sample"] = {k: (v["ok"], v["failed"]) for k, v in rec["sample"].items()}
    if "everything" in rec:
        summary["everything (ok, failed)"] = {k: (v["ok"], v["failed"]) for k, v in rec["everything"].items()}
        summary["failures_by_message"] = {k: v["failures_by_message"] for k, v in rec["everything"].items() if v["failures_by_message"]}
    print(json.dumps(summary, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
