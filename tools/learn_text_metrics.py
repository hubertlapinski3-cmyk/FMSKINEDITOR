"""Learn the game's single-line text height per font size from inspector dumps.

    python tools/learn_text_metrics.py DUMP_FOLDER [--out data/render/text-metrics.json] [--min-n 100]

The browser's stand-in font has different line metrics from the game's, so text rows come out the wrong height and everything below them shifts. The game's value is
measured, not assumed: for every visible SIText node in the flat inspector dumps (`live-*-flat.json`) the font size the render's own cascade resolves for its classes
is divided into the node's height; for each font size with at least `min-n` single-line samples the dominant value is kept (the median, accepted only when the 90th
percentile equals it, i.e. the distribution has one clear mode). Sizes without a stable mode are left out and the render reports the gap. The table says where it came
from: inspector dumps, no decompiled code.

Calibration check (2026-11-13): 16 px -> 24.4 px matches the c2 session's Loans tile (a 16 px heading row measured 24.4 px)."""
import argparse
import collections
import glob
import json
import re
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from skin_editor import config, index_styles          # noqa: E402
from skin_editor.render.service import Renderer       # noqa: E402

AA = r"C:\Program Files (x86)\Steam\steamapps\common\Football Manager 27\fm_Data\StreamingAssets\aa\StandaloneWindows64"
LABEL = re.compile(r"^SIText(?:#[^.]*)?((?:\.[^.]+)*)$")


def learn(folder, min_n=100):
    ws = config.workspace(config.load())
    cascade = Renderer(AA, ws.cache, index_styles.load(ws)).cascade()
    cache = {}

    def font_size(classes):
        k = tuple(classes)
        if k not in cache:
            n = {"type": "SIText", "name": "", "classes": list(classes), "inline": None, "children": [], "attrs": {}}
            cascade.compute([n])
            m = re.match(r"^([\d.]+)px$", n["computed"].get("font-size", {}).get("value", ""))
            cache[k] = float(m.group(1)) if m else None
        return cache[k]

    rows, files = collections.defaultdict(list), 0
    for f in sorted(glob.glob(str(Path(folder) / "live-*-flat.json"))):
        files += 1
        for n in (json.loads(Path(f).read_text(encoding="utf-8")).get("result") or {}).get("nodes", []):
            m = LABEL.match(n.get("label", ""))
            if not m or not n.get("visible") or not n.get("h"):
                continue
            cl = [c for c in m.group(1).split(".") if c and c != "sitext"]
            fs = font_size(cl) if cl else None
            if fs and n["h"] <= 1.9 * fs * 1.6:
                rows[fs].append(n["h"] / fs)
    table, notes = {}, {}
    for fs in sorted(rows):
        v = sorted(rows[fs])
        n = len(v)
        med, p90 = statistics.median(v), v[int(n * 0.9)]
        if n >= min_n and abs(p90 - med) < 0.005:
            table["%g" % fs] = round(med * fs, 1)
            notes["%g" % fs] = {"n": n, "ratio": round(med, 3)}
    return {"schema": "fm-text-metrics/1", "source": "inspector dumps (live-*-flat.json), single-line SIText, ratio of node height to the cascade's font size",
            "dump_files": files, "min_samples": min_n, "line_height_px": table, "samples": notes,
            "excluded_sizes": {"%g" % fs: len(v) for fs, v in rows.items() if "%g" % fs not in table}}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("folder")
    ap.add_argument("--out", default=str(ROOT / "data" / "render" / "text-metrics.json"))
    ap.add_argument("--min-n", type=int, default=100)
    a = ap.parse_args()
    doc = learn(a.folder, a.min_n)
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    Path(a.out).write_text(json.dumps(doc, indent=1), encoding="utf-8")
    print("wrote", a.out, "| line heights:", doc["line_height_px"], "| excluded (few samples or no clear mode):", doc["excluded_sizes"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
