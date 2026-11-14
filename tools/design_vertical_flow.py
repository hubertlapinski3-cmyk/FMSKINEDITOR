"""U5, DESIGN ONLY (v1.1.0): what the Transfers Activity miss of the held-out test implies, as a candidate rule and its predictions, written to docs/evidence/phase9-v110-grid-vertical-flow-design.json.

    python tools/design_vertical_flow.py

The model (render/screen.py) is NOT changed. The candidate is a prototype in this file. Nothing it prints is verified: it was written AFTER seeing the miss, so the miss is the rule's first and only source and the repo's
two-source rule keeps it out of the model until a second, independent capture confirms it.

Two candidates, because the first one the miss suggests is wrong:
  A. "bottom-anchored cells move down by the extra rows" (what the Transfers Activity cells look like). It CONTRADICTS the measured Squad screens: Atmosphere sits at the bottom edge of its composition
     (y 8, h 2 of 10) and does not move on the 30 x 16 grid; so a rule keyed on the bottom edge alone cannot be right.
  B. "a flexible cell's vertical growth pushes down the cells below it" (cells that start at or under its bottom edge and share a column with it). In Transfers Activity the six cells sit beneath the growing
     content block and moved by the grid's extra rows; in Squad the Atmosphere is BESIDE the growing overview block, not below it, and stays. B is consistent with all six measured screens and with the miss."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from skin_editor.render import fixtures, screen          # noqa: E402

OUT = ROOT / "docs" / "evidence" / "phase9-v110-grid-vertical-flow-design.json"


def prototype_b(asm, composition, area, reserved_right=0, padding=12):
    """The model's own result, then candidate B on top: cells below a flexible cell move down by its vertical growth."""
    base = asm.assemble(composition, tuple(area), reserved_right=reserved_right, padding=padding)
    design = {c["element_id"]: c for c in asm.cells[composition]}
    hosts = {h["element_id"]: dict(h) for h in base["hosts"]}
    moved = {}
    for fid, f in design.items():
        flex_h = f["max_h"] >= 100 or f["max_h"] == 0
        if not flex_h:
            continue
        grown = hosts[fid]["h"] - f["h"]
        if grown <= 0:
            continue
        for cid, c in design.items():
            if cid == fid:
                continue
            below = c["y"] >= f["y"] + f["h"]
            share = c["x"] < f["x"] + f["w"] and f["x"] < c["x"] + c["w"]
            if below and share:
                moved[cid] = moved.get(cid, 0) + grown
    for cid, dy in moved.items():
        h = hosts[cid]
        h["row"] += dy
        h["px"] = screen.cell_px(h["col"], h["row"], h["w"], h["h"], padding)
    return hosts, moved, base


def main():
    ctx = fixtures.Context()
    asm = screen.Assembler(ctx.layout_dump())
    held = json.loads((ROOT / "docs" / "evidence" / "phase9-fix-round-heldout-results.json").read_text(encoding="utf-8"))
    pred = json.loads((ROOT / "docs" / "evidence" / "phase9-fix-round-heldout-predictions.json").read_text(encoding="utf-8"))
    out = {"status": "DESIGN ONLY, NOT VERIFIED; blocked on a second measured capture", "model_changed": False, "candidates": {}, "unblocks": {}}
    # the miss
    scr = next(s for s in pred["screens"] if "transfers" in s["capture"])
    hosts, moved, base = prototype_b(asm, scr["composition"], scr["container_area"])
    rows = [r for r in held if "transfers" in r["capture"]]
    retro = []
    for r in rows:
        h = hosts.get(r["host"])
        if h and r.get("real"):
            p = [h["px"]["left"], h["px"]["top"], h["px"]["width"], h["px"]["height"]]
            retro.append({"host": r["host"], "model_1.1": r["predicted"], "candidate_B": p, "real_capture": r["real"], "residual_B": [a - b for a, b in zip(p, r["real"])]})
    out["candidates"]["B"] = {"rule": "cells below a flexible cell (starting at or under its bottom edge, sharing a column) move down by that cell's vertical growth", "cells_moved_on_the_transfers_screen": moved,
                              "retrodiction_on_the_transfers_capture": retro, "note": "a retrodiction: the rule was written after seeing this capture, so it confirms nothing"}
    exact = sum(1 for x in retro if all(v == 0 for v in x["residual_B"]))
    out["candidates"]["B"]["exact_hosts"] = "%d of %d" % (exact, len(retro))
    # the six measured screens must not change under B
    checks = []
    for name in ("screen-squad-large-2500", "screen-squad-large-1600", "screen-squad-large-1680", "screen-squad-standard", "screen-squad-small", "screen-team-instructions-large"):
        fx = fixtures.load(fixtures.FIXTURES / name)
        s = fx["fixture"]["screen"]
        hosts_b, moved_b, base_b = prototype_b(asm, s["composition"], s["area"], s.get("reserved_right", 0), s.get("padding", 12))
        same = all(hosts_b[h["element_id"]]["px"] == h["px"] for h in base_b["hosts"])
        checks.append({"fixture": name, "composition": s["composition"], "cells_candidate_B_would_move": moved_b, "all_hosts_unchanged_by_B": same})
    out["candidates"]["B"]["measured_screens_unchanged"] = checks
    # candidate A against the same six
    a_checks = []
    for name in ("screen-squad-large-2500",):
        fx = fixtures.load(fixtures.FIXTURES / name)
        s = fx["fixture"]["screen"]
        base = asm.assemble(s["composition"], tuple(s["area"]), reserved_right=s.get("reserved_right", 0), padding=s.get("padding", 12))
        c0, r0 = asm.design_size(s["composition"])
        bottom = [c["element_id"] for c in asm.cells[s["composition"]] if c["y"] + c["h"] == r0]
        a_checks.append({"fixture": name, "cells_touching_the_design_bottom_edge": bottom, "grid_rows": base["grid"]["rows"], "design_rows": r0,
                         "contradiction": "candidate A would move these down by %d rows; the capture shows them where the model puts them (the fixture passes)" % (base["grid"]["rows"] - r0)})
    out["candidates"]["A"] = {"rule": "cells touching the composition's bottom edge move down by the extra rows", "against_the_measured_squad_screen": a_checks, "verdict": "rejected by the measured data it would break"}
    out["unblocks"] = {"needed": "a second, INDEPENDENT measured capture of a screen whose composition has a flexible cell with cells below it, on a grid taller than the design, at a panel size other than the Transfers capture's (any Recruitment or Portal screen at another height qualifies; a screen with a fixed cell below a flexible one is the best test)",
                       "how": "an owner-present capture session (read-only inspector, one capture per screen); no game launch happens in this round",
                       "then": "freeze the candidate's predictions for that capture BEFORE opening it (as the held-out test did), compare, and only then decide whether the model gets the rule"}
    OUT.write_text(json.dumps(out, indent=1), encoding="utf-8")
    print("wrote", OUT)
    print("B: moved", moved, "| exact on the Transfers capture:", out["candidates"]["B"]["exact_hosts"], "| measured screens unchanged:", [c["all_hosts_unchanged_by_B"] for c in checks])


if __name__ == "__main__":
    main()
