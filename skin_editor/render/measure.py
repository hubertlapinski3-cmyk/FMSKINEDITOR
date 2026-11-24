"""Measure a render in headless Edge: every element's box as the browser lays it out (what the fixtures compare with the game's own boxes). Edge's stdout is not attached here, so
the page's boxes are read through its DevTools port by tools/cdp_measure.mjs; its own profile folder keeps it away from the owner's browser and every process started with that
profile is closed afterwards."""
import json
import os
import shutil
import socket
import subprocess
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
EDGE = [r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe", r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"]
READY_TIMEOUT = 25.0
MEASURE_TIMEOUT = 120


def edge_path():
    return next((e for e in EDGE if Path(e).is_file()), None)


def _free_port():
    """A port the OS says is free right now (never 9400 + time-derived guesses)."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _wait_devtools(port, proc, timeout=READY_TIMEOUT):
    """Wait until Edge answers its DevTools endpoint. Returns (ready, detail); detail names what did not come up."""
    import urllib.request
    deadline = time.time() + timeout
    last = "no answer yet"
    while time.time() < deadline:
        if proc.poll() is not None:
            return False, "Microsoft Edge exited before its DevTools port %d was up (exit code %s)" % (port, proc.returncode)
        try:
            with urllib.request.urlopen("http://127.0.0.1:%d/json/version" % port, timeout=1.0) as r:
                if r.status == 200:
                    return True, "ready"
                last = "HTTP %s" % r.status
        except Exception as e:
            last = str(e)
        time.sleep(0.25)
    return False, ("Microsoft Edge did not expose its DevTools port %d within %.0fs (%s)"
                   % (port, timeout, last))


def measure(html_text, out_dir, shot=None, size=(0, 0)):
    """{node index: [x, y, w, h]} for the page `html_text` (see render/html.to_html); optionally a 2x PNG of it at `shot`."""
    edge = edge_path()
    if not edge:
        raise RuntimeError("Microsoft Edge not found")
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    f = out_dir / "fixture.html"
    f.write_text(html_text, encoding="utf-8")
    port = _free_port()
    # a UNIQUE profile per measurement: a stale profile lock from an earlier run is what made Edge never come up
    profile = Path(tempfile.mkdtemp(prefix="fixture-edge-%d-" % os.getpid(), dir=str(out_dir)))
    proc = subprocess.Popen([edge, "--headless=new", "--disable-gpu", "--no-first-run", "--no-default-browser-check",
                             "--user-data-dir=%s" % profile, "--remote-debugging-port=%d" % port, f.as_uri()],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        ready, detail = _wait_devtools(port, proc)
        if not ready:
            raise RuntimeError("no measurement: " + detail)
        r = None
        for attempt in range(2):                       # bounded retry: the page can still be parsing on the first ask
            r = subprocess.run(["node", str(ROOT / "tools" / "cdp_measure.mjs"), str(port), "fixture.html"]
                               + ([str(shot), str(size[0]), str(size[1])] if shot else []),
                               capture_output=True, text=True, timeout=MEASURE_TIMEOUT)
            if r.returncode == 0 and r.stdout.strip():
                break
            if r.returncode != 2:                      # 2 is the page/attribute not ready; anything else is fatal
                break
            time.sleep(0.5)
    finally:
        subprocess.run(["powershell", "-NoProfile", "-Command",
                        "Get-CimInstance Win32_Process -Filter \"Name='msedge.exe'\" | Where-Object { $_.CommandLine -like '*fixture-edge-%d-*' } | "
                        "ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }" % os.getpid()],
                       capture_output=True)
        try:
            proc.kill()
        except Exception:
            pass
        shutil.rmtree(profile, ignore_errors=True)
    if r.returncode != 0 or not r.stdout.strip():
        raise RuntimeError("no measurement: " + (r.stderr.strip()[:300] or "the page produced no data-rects"))
    return {int(k): v for k, v in json.loads(r.stdout.strip()).items()}
