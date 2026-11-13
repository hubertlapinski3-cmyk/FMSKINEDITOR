"""Read-only map of the 2D images in the game's UI bundles: Texture2D (PNG-like bitmaps), Sprite (pieces of a texture or atlas) and
VectorImage (imported SVGs, a MonoBehaviour). Nothing is written to the game folder.

usage: python tools/map_images.py [AA_DIR] [--out docs/image-map.json] [--all]
  AA_DIR defaults to the detected game folder (config). By default ui-*.bundle and promobanner*.bundle are scanned; --all scans
  every bundle (3D art too: slow, rarely useful for skinning)."""
import argparse
import json
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

GROUPS = [   # first match wins; name and bundle lowercased
    ("competition", r"bundesliga|champions|ucl|uefa|europa|conference|premier|laliga|la_liga|serie|ligue|eredivisie|mls|cup|league|competition|comp_|_comp|fifa|euro_|world"),
    ("background", r"background|backdrop|wallpaper|bg_|_bg|bg-|-bg|panorama|hero|splash|loading"),
    ("prematch", r"prematch|pre-match|matchday|tunnel"),
    ("manager-creation", r"managercreation|manager-creation"),
    ("promo", r"promo|banner"),
    ("icon", r"icon|glyph|symbol|arrow|chevron"),
    ("badge-flag-kit", r"badge|crest|flag|kit|shirt|logo"),
    ("texture", r"texture|noise|grain|gradient|pattern|mask"),
]


FORMATS = {1: "Alpha8", 3: "RGB24", 4: "RGBA32", 5: "ARGB32", 10: "DXT1", 12: "DXT5", 25: "BC7", 28: "DXT1Crunched", 29: "DXT5Crunched"}


def group(name, bundle):
    s = (name + " " + bundle).lower()
    for g, rx in GROUPS:
        if re.search(rx, s):
            return g
    return "other"


def scan(path):
    import UnityPy
    env = UnityPy.load(str(path))
    out, errs = [], 0
    for obj in env.objects:
        t = obj.type.name
        try:
            if t == "Texture2D":
                d = obj.read()
                out.append({"kind": "texture", "name": d.m_Name, "w": d.m_Width, "h": d.m_Height,
                            "format": FORMATS.get(int(getattr(d.m_TextureFormat, "value", d.m_TextureFormat)), str(d.m_TextureFormat)), "path_id": obj.path_id,
                            "bytes": int(getattr(d, "m_CompleteImageSize", 0) or 0)})
            elif t == "Sprite":
                d = obj.read()
                r = d.m_Rect
                tex = None
                try:
                    tex = d.m_RD.texture.path_id
                except Exception:
                    pass
                out.append({"kind": "sprite", "name": d.m_Name, "w": round(r.width), "h": round(r.height), "path_id": obj.path_id, "texture_path_id": tex})
            elif t == "MonoBehaviour":
                tt = obj.read_typetree()
                if isinstance(tt, dict) and ("m_Vertices" in tt or "vertices" in tt) and ("m_Indices" in tt or "indices" in tt):
                    size = tt.get("m_Size") or tt.get("size") or {}
                    out.append({"kind": "svg", "name": tt.get("m_Name", ""), "w": round(size.get("x", 0)), "h": round(size.get("y", 0)), "path_id": obj.path_id,
                                "vertices": len(tt.get("m_Vertices") or tt.get("vertices") or [])})
        except Exception:
            errs += 1
    return out, errs


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("aa", nargs="?")
    ap.add_argument("--out", default=str(ROOT / "docs" / "image-map.json"))
    ap.add_argument("--all", action="store_true")
    a = ap.parse_args(argv)
    if a.aa:
        aa = Path(a.aa)
    else:
        from skin_editor import config, detect
        aa = Path(detect.describe(config.load()["game_dir"])["aa_dir"])
    files = sorted(aa.glob("*.bundle")) if a.all else sorted([*aa.glob("ui-*.bundle"), *aa.glob("promobanner*.bundle")])
    t0, rows, per = time.time(), [], {}
    for i, f in enumerate(files):
        items, errs = scan(f)
        for it in items:
            it["bundle"] = f.name
            it["group"] = group(it["name"], f.name)
        rows += items
        if items or errs:
            per[f.name] = {"textures": sum(x["kind"] == "texture" for x in items), "sprites": sum(x["kind"] == "sprite" for x in items),
                           "svgs": sum(x["kind"] == "svg" for x in items), "errors": errs, "mb": round(f.stat().st_size / 1048576, 1)}
        print("%3d/%d %-55s %4d images" % (i + 1, len(files), f.name, len(items)), file=sys.stderr)
    out = {"game_folder": str(aa), "scanned_bundles": len(files), "seconds": round(time.time() - t0, 1), "bundles": per, "images": rows}
    Path(a.out).write_text(json.dumps(out, indent=1), encoding="utf-8")
    print(json.dumps({"images": len(rows), "by_kind": {k: sum(r["kind"] == k for r in rows) for k in ("texture", "sprite", "svg")},
                      "by_group": {g: sum(r["group"] == g for r in rows) for g in sorted({r["group"] for r in rows})}, "seconds": out["seconds"]}, indent=1))


if __name__ == "__main__":
    main()
