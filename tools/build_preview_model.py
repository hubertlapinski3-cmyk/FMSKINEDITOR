"""Build a preview model (data/models/<screen>.json + <screen>.png) from an inspector measurement.

Windows-only dev tool: the measurement comes from the FM27 inspector (Colour Finder `verify/measure.mjs`: every visible element
with its box, resolved colours, and for each visible colour property the stylesheet rules the game reports as its source).
The model is shipped as data; the app never needs the inspector.

usage: python tools/build_preview_model.py MEASURE.json SCREENSHOT.png SCREEN [--build 27.0.1.x] [--state vanilla] [--out data/models]

Region per (element, colour property). Binding:
  token    the winning rule's value is var(--x) (the app follows the alias chain with the project's overrides)
  literal  the winning rule's value is a colour literal
  code     inline value (set by code), no matching rule (default or code), inherited, or anything else
The measured colour is the vanilla on-screen value as the game resolved it (state "vanilla" must be true for the measurement)."""
import argparse
import json
import re
import shutil
import sys
from pathlib import Path

SCHEMA = "fm27se-preview/1"
VAR = re.compile(r"var\((--[\w-]+)\)$")
HEX = re.compile(r"#[0-9A-Fa-f]{6}([0-9A-Fa-f]{2})?$")


def winner(src):
    """The rule the game reports as the winner (from the verdict text), else the first listed rule."""
    rules = src.get("rules") or []
    verdict = src.get("verdict") or ""
    if verdict.startswith("stylesheet:"):
        for r in rules:
            if verdict.startswith("stylesheet:%s %s " % (r["sheet"], r["selector"])) or verdict == "stylesheet:%s %s" % (r["sheet"], r["selector"]):
                return r
    return rules[0] if rules else None


def binding(src):
    if src.get("inline"):
        return {"kind": "code", "why": "inline value (set by code)"}
    v = src.get("verdict") or ""
    if not v.startswith("stylesheet:"):
        return {"kind": "code", "why": v.split(" (")[0] or "no stylesheet source"}
    r = winner(src)
    if not r:
        return {"kind": "code", "why": "no rule reported"}
    val = r["value"].strip()
    base = {"sheet": r["sheet"], "selector": r["selector"], "value": val, "specificity": r.get("specificity")}
    m = VAR.match(val)
    if m:
        return dict(base, kind="token", token=m.group(1))
    if HEX.match(val):
        return dict(base, kind="literal")
    return dict(base, kind="code", why="value is not a single token or colour: " + val[:60])


def norm_hex(h):
    h = (h or "").strip().upper()
    return h if HEX.match(h) else None


def build(measure, screen, resolution, build_label=None, state="vanilla"):
    regions = []
    for order, e in enumerate(measure):
        comp = e.get("component") or {}
        if comp.get("type") == "SIGradient" and norm_hex(comp.get("startColour")) and norm_hex(comp.get("endColour")) and e.get("w", 0) >= 1 and e.get("h", 0) >= 1:
            label = e.get("label", "")
            # an SIGradient paints start -> end. With useCustomStyles the colours come from the --start-colour / --end-colour custom
            # properties of the rules matching the element (resolved by the app from the style index); otherwise code sets them.
            regions.append({
                "id": "%s#%d:gradient" % (label.split(".")[0][:60], order), "order": order, "prop": "gradient",
                "rect": [round(e["x"], 1), round(e["y"], 1), round(e["w"], 1), round(e["h"], 1)],
                "label": label[:200], "text": "", "classes": e.get("classes") or [],
                "colour": norm_hex(comp["startColour"]), "end": norm_hex(comp["endColour"]), "direction": comp.get("direction") or "LeftToRight",
                "opacity": (e.get("resolved") or {}).get("opacity", 1),
                "binding": {"kind": "gradient"} if comp.get("useCustomStyles") else {"kind": "code", "why": "gradient colours set by code (useCustomStyles false)"}})
        for prop, src in (e.get("src") or {}).items():
            col = norm_hex(src.get("resolved") or (e.get("resolved") or {}).get(prop))
            if not col or not (e.get("w", 0) >= 1 and e.get("h", 0) >= 1):
                continue
            label = e.get("label", "")
            regions.append({
                "id": "%s#%d:%s" % (label.split(".")[0][:60], order, prop), "order": order, "prop": prop,
                "rect": [round(e["x"], 1), round(e["y"], 1), round(e["w"], 1), round(e["h"], 1)],
                "label": label[:200], "text": (e.get("text") or "")[:80], "classes": e.get("classes") or [],
                "colour": col, "opacity": (e.get("resolved") or {}).get("opacity", 1),
                "binding": binding(src)})
    return {"schema": SCHEMA, "screen": screen, "resolution": list(resolution), "screenshot": screen + ".png",
            "game_build": build_label, "measured_state": state, "regions": regions}


def mark_sampleable(model, png_bytes, tolerance=6):
    """Self-check against the measured screenshot: an opaque background region whose centre sample (the one Verify takes) shows its
    own measured colour is marked sample_ok. Verify judges only those; a centre covered by text, an icon or a child is left out."""
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from skin_editor import verify
    cand = [r for r in model["regions"] if r["prop"] == "background-color" and len(r["colour"]) in (7, 9)
            and (len(r["colour"]) == 7 or r["colour"].endswith("FF")) and r.get("opacity", 1) >= 0.999 and r["rect"][2] >= 12 and r["rect"][3] >= 12]
    probe = {"resolution": model["resolution"], "regions": [{"id": str(i), "rect": r["rect"], "expected": r["colour"][:7]} for i, r in enumerate(cand)]}
    for row, r in zip(verify.compare(probe, png_bytes, tolerance)["rows"], cand):
        r["sample_ok"] = row["result"] == "landed"
    return sum(r.get("sample_ok", False) for r in model["regions"])


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("measure"); ap.add_argument("screenshot"); ap.add_argument("screen")
    ap.add_argument("--build"); ap.add_argument("--state", default="vanilla")
    ap.add_argument("--out", default=str(Path(__file__).resolve().parent.parent / "data" / "models"))
    a = ap.parse_args(argv)
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,40}", a.screen):
        sys.exit("screen name: lowercase letters, digits, dashes")
    from PIL import Image
    with Image.open(a.screenshot) as im:
        size = im.size
    measure = json.loads(Path(a.measure).read_text(encoding="utf-8"))
    roots = [e for e in measure if "/" not in e.get("path", "/") and e.get("w")]      # panel roots P0, P1, ...: the largest is the screen frame
    root = max(roots, key=lambda e: e["w"] * e["h"]) if roots else {}
    if root.get("w") and abs(root["w"] / root["h"] - size[0] / size[1]) > 0.01:
        sys.exit("screenshot %dx%d does not match the measured panel %sx%s" % (size[0], size[1], root["w"], root["h"]))
    resolution = (round(root.get("w") or size[0], 1), round(root.get("h") or size[1], 1))
    model = build(measure, a.screen, resolution, a.build, a.state)
    mark_sampleable(model, Path(a.screenshot).read_bytes())
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(a.screenshot, out / (a.screen + ".png"))
    (out / (a.screen + ".json")).write_text(json.dumps(model, separators=(",", ":")), encoding="utf-8")
    kinds = {}
    for r in model["regions"]:
        kinds[r["binding"]["kind"]] = kinds.get(r["binding"]["kind"], 0) + 1
    print("%s: %d regions %s, %d sampleable for Verify, resolution %s, screenshot %dx%d" % (
        a.screen, len(model["regions"]), kinds, sum(r.get("sample_ok", False) for r in model["regions"]), resolution, size[0], size[1]))


if __name__ == "__main__":
    main()
