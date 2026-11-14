"""Fix round, problem 3: a held-out test of the grid-placement model (render/screen.py + pitch.json), zero game time.

    python tools/heldout_grid.py predict OUT.json     # STEP 1: write the model's predictions. Reads from each capture ONLY the names of the grid hosts and the container's size.
    python tools/heldout_grid.py compare PRED.json OUT.json   # STEP 2 (after the predictions are committed): open the hosts' real positions and compare.

The commit order is the proof: the predictions file is committed, with the blob hashes of screen.py, pitch.json and the layout dump's cell table, before `compare` is ever run.
What `predict` assumes, because it cannot know it without looking at the answer: the composition is the one whose cells hold all the host names (the `-Large` variant when the grid is at
least 20 columns wide, as measured for Squad and Team Instructions), padding 12, no reserved columns; hosts the composition does not hold (run-time slots) are not predicted."""
import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from skin_editor.render import captures, fixtures, pitch as pitch_mod, screen   # noqa: E402

UI = Path(r"C:\Users\Admin\FMSKINNING\workspace\notes\ui-dumps")
CAPTURES = ["styles-d3-transfers-activity-20261114-111518.ndjson", "styles-d4-inbox-20261114-111746.ndjson", "styles-sessionB-start-screen-20261114-103457.ndjson"]
GIT = r"C:\Program Files\Git\cmd\git.exe"


def blob(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()[:16]


def hosts_of(cap):
    hosts = [e for e in cap.elements.values() if e["type"] == "BindableVariableSizedGridElement"]
    groups = {}
    for h in hosts:
        groups.setdefault(h["path"].rsplit("/", 1)[0], []).append(h)
    parent_path = max(groups, key=lambda p: len(groups[p]))
    return parent_path, groups[parent_path]


def predict(out):
    ctx = fixtures.Context()
    d = ctx.layout_dump()
    asm = screen.Assembler(d)
    by_comp = {}
    for c in d["cells"]:
        by_comp.setdefault(c["composition"], set()).add(c["element_id"])
    result = {"model": {"head": subprocess.run([GIT, "rev-parse", "HEAD"], capture_output=True, text=True, cwd=ROOT).stdout.strip(), "screen.py": blob(ROOT / "skin_editor/render/screen.py"),
                        "pitch.json": blob(ROOT / "skin_editor/render/pitch.json"), "layout_dump_cells": hashlib.sha256(json.dumps(d["cells"], sort_keys=True).encode()).hexdigest()[:16]},
              "assumptions": "composition = the one whose cells hold all host names, the -Large variant when the grid is >= 20 columns; padding 12; reserved_right 0; hosts not in the composition are run-time slots and are not predicted",
              "screens": []}
    for f in CAPTURES:
        cap = captures.read_capture(UI / f)
        parent_path, hosts = hosts_of(cap)
        names = sorted({h["name"] for h in hosts})
        parent = cap.elements[parent_path]
        area = [round(parent["world"][2], 1), round(parent["world"][3], 1)]
        cols, rows = None, None
        cands = [(len(set(names) & cells), comp) for comp, cells in by_comp.items() if set(names) & cells]
        cands.sort(key=lambda t: (-t[0], t[1]))
        best = cands[0][0]
        pool = [c for n, c in cands if n == best]
        pick = next((c for c in pool if c.endswith("-Large")), None) or sorted(pool, key=len)[0]
        if not pick.endswith("-Large") and any(c.endswith("-Large") for c in by_comp):
            pass
        res = asm.assemble(pick, tuple(area), reserved_right=0, padding=12, moves=(), runtime_slots=[])
        cols, rows = res["grid"]["columns"], res["grid"]["rows"]
        px = {h["element_id"]: [h["px"]["left"], h["px"]["top"], h["px"]["width"], h["px"]["height"]] for h in res["hosts"]}
        result["screens"].append({"capture": f, "container_area": area, "grid": [cols, rows], "host_names_seen": names, "composition": pick, "candidates_considered": pool[:6], "covered": best,
                                  "predictions_px": {k: v for k, v in px.items() if k in names}, "predicted_but_not_in_capture": sorted(k for k in px if k not in names),
                                  "capture_hosts_not_in_composition": sorted(set(names) - set(px))})
    Path(out).write_text(json.dumps(result, indent=1), encoding="utf-8")
    print("wrote", out)


def compare(pred_file, out):
    pred = json.loads(Path(pred_file).read_text(encoding="utf-8"))
    rows = []
    for s in pred["screens"]:
        cap = captures.read_capture(UI / s["capture"])
        parent_path, hosts = hosts_of(cap)
        by = {}
        for h in hosts:
            by.setdefault(h["name"], []).append(h)
        for name, box in s["predictions_px"].items():
            for h in by.get(name, []):
                inl = h.get("inline") or {}
                try:
                    real = [int(str(inl[k]).replace("px", "")) for k in ("left", "top", "width", "height")]
                except (KeyError, ValueError):
                    rows.append({"capture": s["capture"], "host": name, "predicted": box, "real": None, "residual": None})
                    continue
                rows.append({"capture": s["capture"], "host": name, "composition": s["composition"], "predicted": box, "real": real, "residual": [p - r for p, r in zip(box, real)],
                              "max_abs": max(abs(p - r) for p, r in zip(box, real))})
    Path(out).write_text(json.dumps(rows, indent=1), encoding="utf-8")
    ok = [r for r in rows if r.get("residual") is not None]
    print(len(rows), "hosts compared;", sum(1 for r in ok if r["max_abs"] == 0), "exact;", "max residual", max((r["max_abs"] for r in ok), default=None))


if __name__ == "__main__":
    if len(sys.argv) >= 3 and sys.argv[1] == "predict":
        predict(sys.argv[2])
    elif len(sys.argv) >= 4 and sys.argv[1] == "compare":
        compare(sys.argv[2], sys.argv[3])
    else:
        sys.exit(__doc__)
