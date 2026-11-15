"""Run the Studio against a SCRATCH workspace, in your browser, so you can look at the first-run screens without touching your real skins.

    python tools/run_studio_scratch.py            # a fresh install: empty workspace (Simple mode, the setup, the start screen)
    python tools/run_studio_scratch.py --existing # an existing install: one project already there (Advanced mode, no start screen)
    python tools/run_studio_scratch.py --open     # also open the page in the default browser

It starts the engine (workspace in a temporary folder; the game folder is only READ) and the Studio's dev page, prints the address, and waits.
Press Enter (or Ctrl+C) here to stop both and delete the temporary workspace. Nothing in your real workspace, your game folder or your skins folder is written:
do not press "Put it in the game"-style buttons that would export into your Documents skins folder (S1 has none; the later milestones will say so here)."""
import argparse
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def kill_tree(p):
    if p and p.poll() is None:
        subprocess.run(["taskkill", "/T", "/F", "/PID", str(p.pid)], capture_output=True)


def wait_http(url, seconds=60):
    end = time.time() + seconds
    while time.time() < end:
        try:
            urllib.request.urlopen(url, timeout=2).read(1)
            return True
        except Exception:
            time.sleep(0.5)
    return False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--existing", action="store_true", help="seed one project, so the install looks like an existing one")
    ap.add_argument("--open", action="store_true")
    ap.add_argument("--check", action="store_true", help="start, probe both servers, stop (for tests)")
    ap.add_argument("--keep", action="store_true", help="use a PERSISTENT scratch workspace (%%LOCALAPPDATA%%\\FM27SkinEditor-scratch) that survives between runs, like a real install: the setup is done once, your test skin is still there next time")
    ap.add_argument("--reset", action="store_true", help="with --keep: delete that persistent scratch workspace first (a fresh install again)")
    a = ap.parse_args()
    if a.keep:
        scratch = Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "FM27SkinEditor-scratch"
        if a.reset:
            shutil.rmtree(scratch, ignore_errors=True)
        scratch.mkdir(parents=True, exist_ok=True)
    else:
        scratch = Path(tempfile.mkdtemp(prefix="studio-scratch-"))
    env = dict(os.environ, FM27SE_WORKSPACE=str(scratch))
    engine = vite = None
    try:
        if a.existing:
            from skin_editor import config, project as project_mod, projfmt
            os.environ["FM27SE_WORKSPACE"] = str(scratch)
            ws = config.workspace(config.load())
            projfmt.write(ws, project_mod.new("old-skin"))
        engine = subprocess.Popen([sys.executable, "-m", "skin_editor", "serve", "--no-browser"], cwd=ROOT, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        url = engine.stdout.readline().strip()
        m = re.match(r"http://127\.0\.0\.1:(\d+)/\?t=(\S+)", url)
        if not m:
            print("the engine did not start:", url); return 1
        threading.Thread(target=lambda: [None for _ in engine.stdout], daemon=True).start()          # keep the pipe drained
        vite = subprocess.Popen("npm run dev", cwd=ROOT / "studio", shell=True, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if not wait_http("http://127.0.0.1:1420/"):
            print("the Studio page did not start on port 1420 (is another dev server running?)"); return 1
        page = "http://127.0.0.1:1420/?engine=http://127.0.0.1:%s&token=%s" % (m.group(1), m.group(2))
        print("workspace (temporary):", scratch)
        print("OPEN THIS ADDRESS IN YOUR BROWSER:\n\n  " + page + "\n")
        if a.check:
            print("check: the engine printed its address and the Studio page answered on port 1420"); return 0
        if a.open:
            import webbrowser; webbrowser.open(page)
        input("Press Enter here when you are done (this stops everything%s) ... " % ("; the scratch workspace is kept" if a.keep else " and deletes the temporary workspace"))
        return 0
    except KeyboardInterrupt:
        return 0
    finally:
        kill_tree(vite); kill_tree(engine)
        time.sleep(1)
        if a.keep:
            print("stopped; the scratch workspace was KEPT (%s). Run with --keep --reset for a fresh install again." % scratch)
        else:
            shutil.rmtree(scratch, ignore_errors=True)
            print("stopped; temporary workspace removed")


if __name__ == "__main__":
    sys.exit(main())
