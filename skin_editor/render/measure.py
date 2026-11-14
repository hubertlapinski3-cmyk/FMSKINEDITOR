"""Measure a render in headless Edge: every element's box as the browser lays it out (what the fixtures compare with the game's own boxes). Edge's stdout is not attached here, so
the page's boxes are read through its DevTools port by tools/cdp_measure.mjs; its own profile folder keeps it away from the owner's browser and every process started with that
profile is closed afterwards."""
import json
import subprocess
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
EDGE = [r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe", r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"]


def edge_path():
    return next((e for e in EDGE if Path(e).is_file()), None)


def measure(html_text, out_dir, shot=None, size=(0, 0)):
    """{node index: [x, y, w, h]} for the page `html_text` (see render/html.to_html); optionally a 2x PNG of it at `shot`."""
    edge = edge_path()
    if not edge:
        raise RuntimeError("Microsoft Edge not found")
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    f = out_dir / "fixture.html"
    f.write_text(html_text, encoding="utf-8")
    port = 9400 + (int(time.time() * 10) % 400)
    profile = out_dir / "fixture-edge-profile"
    proc = subprocess.Popen([edge, "--headless=new", "--disable-gpu", "--no-first-run", "--no-default-browser-check", "--user-data-dir=%s" % profile,
                             "--remote-debugging-port=%d" % port, f.as_uri()], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        r = subprocess.run(["node", str(ROOT / "tools" / "cdp_measure.mjs"), str(port), "fixture.html"] + ([str(shot), str(size[0]), str(size[1])] if shot else []),
                           capture_output=True, text=True, timeout=120)
    finally:
        subprocess.run(["powershell", "-NoProfile", "-Command",
                        "Get-CimInstance Win32_Process -Filter \"Name='msedge.exe'\" | Where-Object { $_.CommandLine -like '*fixture-edge-profile*' } | "
                        "ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }"], capture_output=True)
        proc.kill()
    if r.returncode != 0 or not r.stdout.strip():
        raise RuntimeError("no measurement: " + r.stderr[:300])
    return {int(k): v for k, v in json.loads(r.stdout.strip()).items()}
