"""Screenshot vs preview model. LEARNINGS 9.3. Models are JSON in data/models:
{"screen": "tactics", "resolution": [2500, 1406],
 "regions": [{"id": "pitch-panel", "rect": [x, y, w, h], "expected": "#6C001C", "vanilla": "#DA0037",
              "code_driven": false, "entry": "scoped_rules[0]"}]}
'expected' is the flat colour after compositing; the model builder owns that step.
"""
import io
import json
from statistics import median

from . import colour, config


def models():
    d = config.resource_root() / "data" / "models"
    return sorted(p.stem for p in d.glob("*.json")) if d.is_dir() else []


def load_model(name):
    if name not in models():
        raise KeyError("no such model: " + name)
    return json.loads((config.resource_root() / "data" / "models" / (name + ".json")).read_text(encoding="utf-8"))


def compare(model, png_bytes, tolerance=6):
    from PIL import Image
    img = Image.open(io.BytesIO(png_bytes)).convert("RGB")
    mw, mh = model["resolution"]
    if abs(img.width / img.height - mw / mh) > 0.01:
        raise ValueError("screenshot aspect %dx%d does not match the model %dx%d" % (img.width, img.height, mw, mh))
    sx, sy = img.width / mw, img.height / mh
    rows = []
    for r in model["regions"]:
        x, y, w, h = r["rect"]
        pts = [(int((x + w / 2 + dx * w / 6) * sx), int((y + h / 2 + dy * h / 6) * sy))
               for dx in (-1, 0, 1) for dy in (-1, 0, 1)]
        px = [img.getpixel((min(max(px_, 0), img.width - 1), min(max(py, 0), img.height - 1))) for px_, py in pts]
        got = tuple(int(median(p[i] for p in px)) for i in range(3))

        def delta(hex_):
            return max(abs(a - b) for a, b in zip(got, colour.parse(hex_)[:3]))

        d = delta(r["expected"])
        if r.get("code_driven"):
            result = "info"
        elif d <= tolerance:
            result = "landed"
        elif r.get("vanilla") and delta(r["vanilla"]) <= tolerance:
            result = "not_landed"
        else:
            result = "unknown"
        rows.append({"id": r["id"], "expected": r["expected"], "got": "#%02X%02X%02X" % got, "max_delta": d,
                     "result": result, "entry": r.get("entry")})
    return {"rows": rows, "landed": sum(r["result"] == "landed" for r in rows),
            "not_landed": sum(r["result"] == "not_landed" for r in rows)}
