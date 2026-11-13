"""Image and SVG swaps: replace a Texture2D (bitmap) or a VectorImage (imported SVG) inside a UI bundle.

Proven on Windows 2026-11-13: a re-encoded texture (same size, same format) written with UnityPy loads in game (the loading
screen and the report pages showed the labelled replacements). Wallpapers are chosen in code per club / competition, and the
*_blended copies are recoloured by the club colour in the shader (only the image's light and dark survive).

A project lists its swaps in "image_swaps": [{"bundle", "path_id", "name", "kind": "texture"|"svg", "source": file name,
"fit": "cover"|"stretch"|"contain"}]. The source files live in <workspace>/images/<project>/. Builds patch fresh copies from the
vanilla snapshot (image bundles join the snapshot on first use, only when the live file is stock)."""
import io
import json
import re
from pathlib import Path

FORMATS = {1: "Alpha8", 3: "RGB24", 4: "RGBA32", 5: "ARGB32", 10: "DXT1", 12: "DXT5", 25: "BC7", 28: "DXT1Crunched", 29: "DXT5Crunched"}
WRITABLE = {3, 4, 5, 10, 12}                 # UnityPy encodes these; Crunched is re-encoded as plain DXT (bigger, flagged)
CRUNCH_TO = {28: 10, 29: 12}
FITS = ("cover", "stretch", "contain")
BUNDLE_RE = re.compile(r"(ui-[\w.-]+|promobanner[\w.-]*)\.bundle")
SOURCE_RE = re.compile(r"[A-Za-z0-9][\w.-]{0,120}\.(png|jpg|jpeg|webp|svg)")
SCALES = ("1x", "2x", "3x", "4x")
CATALOG_VERSION = 3                            # bump when the catalog's rows change shape (2: icons from the sprite atlases)
ICONS = "ui-icons_assets_%s.bundle"           # Sprite objects (no texture of their own)
ATLASES = "ui-iconspriteatlases_assets_%s.bundle"   # SpriteAtlas + the atlas textures (Crunch DXT5)
SCALE_RE = re.compile(r"[_-]?(?:[1-4]x|x[1-4])$")


def base_name(n):
    """'win_small_2x' -> 'win_small' (the icon's name without its UI-scale suffix)."""
    return SCALE_RE.sub("", n)
GROUPS = [
    ("competition", r"bundesliga|champions|ucl|uefa|europa|conference|premier|laliga|la_liga|serie|ligue|eredivisie|nwsl|wsl|efl|carabao|caraboa|cup|league|liga|nifl|saudi|uae|worldcup|world_cup|superliga|kampioen|premiere"),
    ("wallpaper", r"skin|background|backdrop|wallpaper|texture"),
    ("room", r"room|boardroom|interview|press|media|training environment|treatment|trophy cabinet"),
    ("prematch", r"prematch|lineup"),
    ("menu", r"start_screen|newgame|mainmenu|whatsnew"),
]


def group(name, bundle):
    s = name.lower()
    if "icon" in bundle:
        return "icon"
    for g, rx in GROUPS:
        if re.search(rx, s):
            return g
    return "other"


# ---------------------------------------------------------------- catalog (read-only)
def scan_bundle(path, kinds=("texture", "svg")):
    """[{kind, name, w, h, format, path_id, mips}] for the swappable images in one bundle. Sprites are left out: they are views
    into an atlas texture, so swapping the atlas texture (or the SVG) is the unit of change."""
    import UnityPy
    out = []
    for obj in UnityPy.load(str(path)).objects:
        try:
            if obj.type.name == "Texture2D" and "texture" in kinds:
                d = obj.read()
                fmt = int(getattr(d.m_TextureFormat, "value", d.m_TextureFormat))
                out.append({"kind": "texture", "name": d.m_Name, "w": d.m_Width, "h": d.m_Height, "format": FORMATS.get(fmt, str(fmt)),
                            "format_id": fmt, "mips": int(getattr(d, "m_MipCount", 1) or 1), "path_id": str(obj.path_id)})
            elif obj.type.name == "MonoBehaviour" and "svg" in kinds:
                tt = obj.read_typetree()
                if isinstance(tt, dict) and "vertices" in tt and "indices" in tt and "size" in tt:
                    out.append({"kind": "svg", "name": tt.get("m_Name", ""), "w": round(tt["size"]["x"]), "h": round(tt["size"]["y"]),
                                "triangles": len(tt["indices"]) // 3, "path_id": str(obj.path_id)})
        except Exception:
            continue
    return out


def catalog(ws, aa_dir, refresh=False):
    """Every swappable image in the ui-* bundles of the game folder, cached by the bundles' sizes and mtimes."""
    aa_dir = Path(aa_dir)
    files = sorted(p for p in aa_dir.glob("*.bundle") if BUNDLE_RE.fullmatch(p.name))
    key = [CATALOG_VERSION] + [[p.name, p.stat().st_size, p.stat().st_mtime_ns] for p in files]
    cache = Path(ws.cache) / "image-catalog.json"
    if cache.is_file() and not refresh:
        try:
            d = json.loads(cache.read_text(encoding="utf-8"))
            if d.get("key") == key:
                return d["images"]
        except ValueError:
            pass
    rows = []
    rows += icon_catalog(aa_dir)
    try:
        cls = icon_classes(aa_dir)
    except Exception:
        cls = {}
    for p in files:
        if re.fullmatch(r"ui-icons_assets_[1-4]x\.bundle", p.name) or p.name.startswith("ui-iconspriteatlases_"):
            continue                                            # icons are listed once per name (all scales), above
        for it in scan_bundle(p):
            if it["kind"] == "texture" and ("Atlas" in it["name"] and "font" in p.name):
                continue                                       # font glyph atlases are not images
            it["bundle"] = p.name
            it["group"] = group(it["name"], p.name)
            if it["kind"] == "svg" and ("svg", it["path_id"]) in cls:
                it["classes"] = cls[("svg", it["path_id"])]
            rows.append(it)
    for r in rows:
        if r["kind"] == "icon" and ("icon", r["name"]) in cls:
            r["classes"] = cls[("icon", r["name"])]
    cache.write_text(json.dumps({"key": key, "images": rows}), encoding="utf-8")
    return rows


def thumbnail(bundle_path, path_id, size=(360, 220)):
    """PNG bytes of one texture (scaled) or a rasterised preview of one VectorImage."""
    import UnityPy
    from PIL import Image
    for obj in UnityPy.load(str(bundle_path)).objects:
        if obj.path_id != int(path_id):
            continue
        if obj.type.name == "Texture2D":
            img = obj.read().image
        else:
            img = render_vector(obj.read_typetree(), max(size))
        img = img.convert("RGBA")
        img.thumbnail(size)
        buf = io.BytesIO()
        img.save(buf, "PNG")
        return buf.getvalue()
    raise KeyError("no object %s in %s" % (path_id, Path(bundle_path).name))


def render_vector(tt, px=256):
    """Rasterise a VectorImage the way the game draws it. Plain triangles (flags 0) are solid. Flagged triangles (flags 0x10000)
    carry rounded-edge geometry: 'circle.xy' is a coordinate in unit-circle space, interpolated across the triangle, and only the
    pixels with |xy| <= 1 are drawn (decoded 2026-11-13 from the game's own icons)."""
    import numpy as np
    from PIL import Image
    w, h = tt["size"]["x"] or 1, tt["size"]["y"] or 1
    s = px / max(w, h)
    W, H = max(1, round(w * s)), max(1, round(h * s))
    acc = np.zeros((H, W, 4), np.float64)
    v, ix = tt["vertices"], tt["indices"]
    for k in range(0, len(ix) - 2, 3):
        tri = [v[ix[k + j]] for j in range(3)]
        P = [(q["position"]["x"] * s, q["position"]["y"] * s) for q in tri]
        x_lo, x_hi = max(0, int(min(p[0] for p in P))), min(W, int(max(p[0] for p in P)) + 2)
        y_lo, y_hi = max(0, int(min(p[1] for p in P))), min(H, int(max(p[1] for p in P)) + 2)
        if x_lo >= x_hi or y_lo >= y_hi:
            continue
        ys, xs = np.mgrid[y_lo:y_hi, x_lo:x_hi] + 0.5
        (x0, y0), (x1, y1), (x2, y2) = P
        den = (y1 - y2) * (x0 - x2) + (x2 - x1) * (y0 - y2)
        if abs(den) < 1e-12:
            continue
        a = ((y1 - y2) * (xs - x2) + (x2 - x1) * (ys - y2)) / den
        b = ((y2 - y0) * (xs - x2) + (x0 - x2) * (ys - y2)) / den
        c = 1 - a - b
        m = (a >= -1e-9) & (b >= -1e-9) & (c >= -1e-9)
        if any(q["flags"]["rgba"] for q in tri):
            cx = a * tri[0]["circle"]["x"] + b * tri[1]["circle"]["x"] + c * tri[2]["circle"]["x"]
            cy = a * tri[0]["circle"]["y"] + b * tri[1]["circle"]["y"] + c * tri[2]["circle"]["y"]
            m &= cx * cx + cy * cy <= 1.0
        r, g, bb, al = unpack(tri[0]["tint"]["rgba"])
        al /= 255.0
        reg = acc[y_lo:y_hi, x_lo:x_hi]
        for ch, val in enumerate((r, g, bb)):
            reg[..., ch][m] = val * al + reg[..., ch][m] * (1 - al)
        reg[..., 3][m] = al + reg[..., 3][m] * (1 - al)
    rgb = np.where(acc[..., 3:4] > 0, acc[..., :3] / np.maximum(acc[..., 3:4], 1e-9), 0)
    out = np.dstack([rgb, acc[..., 3:4] * 255]).clip(0, 255).astype("uint8")
    return Image.fromarray(out, "RGBA")


def thumbnails_for_bundle(bundle_path, dest, tag, size=(360, 220)):
    """Write a PNG thumbnail of every texture and VectorImage in one bundle (loaded once): dest/<path_id>_<tag>.png."""
    import UnityPy
    dest = Path(dest)
    dest.mkdir(parents=True, exist_ok=True)
    n = 0
    for obj in UnityPy.load(str(bundle_path)).objects:
        try:
            if obj.type.name == "Texture2D":
                img = obj.read().image
            elif obj.type.name == "MonoBehaviour":
                tt = obj.read_typetree()
                if not (isinstance(tt, dict) and "vertices" in tt and "size" in tt):
                    continue
                img = render_vector(tt, max(size))
            else:
                continue
            img = img.convert("RGBA")
            img.thumbnail(size)
            img.save(dest / ("%s_%s.png" % (obj.path_id, tag)))
            n += 1
        except Exception:
            continue
    return n


# ---------------------------------------------------------------- colour packing (Unity Color32: r in the low byte)
def pack(r, g, b, a=255):
    return int(r) | int(g) << 8 | int(b) << 16 | int(a) << 24


def unpack(v):
    return (v & 255, v >> 8 & 255, v >> 16 & 255, v >> 24 & 255)


# ---------------------------------------------------------------- textures
def fit_image(src_bytes, w, h, fit="cover"):
    """The replacement as an RGBA image of exactly w x h."""
    from PIL import Image
    img = Image.open(io.BytesIO(src_bytes)).convert("RGBA")
    if fit == "stretch":
        return img.resize((w, h), Image.LANCZOS)
    sw, sh = img.size
    if fit == "contain":
        k = min(w / sw, h / sh)
        im2 = img.resize((max(1, round(sw * k)), max(1, round(sh * k))), Image.LANCZOS)
        out = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        out.paste(im2, ((w - im2.width) // 2, (h - im2.height) // 2))
        return out
    k = max(w / sw, h / sh)                                         # cover: fill, crop the overflow from the centre
    im2 = img.resize((max(w, round(sw * k)), max(h, round(sh * k))), Image.LANCZOS)
    x, y = (im2.width - w) // 2, (im2.height - h) // 2
    return im2.crop((x, y, x + w, y + h))


def swap_texture(obj, src_bytes, fit="cover"):
    """Re-encode one Texture2D with the replacement, same size and (where writable) same format. Returns notes."""
    d = obj.read()
    notes = []
    fmt = int(getattr(d.m_TextureFormat, "value", d.m_TextureFormat))
    if fmt in CRUNCH_TO:
        d.m_TextureFormat = CRUNCH_TO[fmt]
        notes.append("%s was Crunch-compressed; written as plain %s (UnityPy cannot write Crunch)" % (d.m_Name, FORMATS[CRUNCH_TO[fmt]]))
    elif fmt not in WRITABLE:
        raise ValueError("%s: texture format %s cannot be written" % (d.m_Name, FORMATS.get(fmt, fmt)))
    if int(getattr(d, "m_MipCount", 1) or 1) > 1:
        notes.append("%s had %d mip levels; written with 1" % (d.m_Name, d.m_MipCount))
    img = fit_image(src_bytes, d.m_Width, d.m_Height, fit)
    if fmt in (10, 3, 28):
        img = img.convert("RGB")
    d.image = img
    d.save()
    return notes


# ---------------------------------------------------------------- export (true size, for editing)
def _flagged_region(P, C):
    """The drawn part of a rounded-edge triangle: positions P, circle coordinates C (affine across the triangle), kept where |c| <= 1.
    Returns ("ellipse", (a, b, c, d, e, f)) when the circle map is invertible (the region is the triangle clipped by an ellipse:
    SVG matrix of the unit circle), ("poly", [points]) when it is rank one (a straight band between two parallel lines, clipped
    exactly), or None when nothing is drawn."""
    import numpy as np
    P, C = np.array(P, float), np.array(C, float)
    D = np.array([C[1] - C[0], C[2] - C[0]])                        # rows: dc/dl1, dc/dl2 (barycentric)
    sv = np.linalg.svd(D, compute_uv=False)
    if sv[0] < 1e-9:                                                 # constant: all or nothing
        return ("poly", P.tolist()) if C[0] @ C[0] <= 1 else None
    if sv[1] / sv[0] > 1e-3:
        M = np.c_[C, np.ones(3)]
        sx, sy = np.linalg.solve(M, P[:, 0]), np.linalg.solve(M, P[:, 1])
        return ("ellipse", (sx[0], sy[0], sx[1], sy[1], sx[2], sy[2]))
    u = np.linalg.svd(D)[2][0]                                       # the line the circle coordinates move along
    tv = [(C[k] - C[0]) @ u for k in range(3)]
    b, c0 = C[0] @ u, C[0] @ C[0] - (C[0] @ u) ** 2                  # |C0 + t u|^2 ~ (t + b)^2 + c0 (off-line part constant)
    if c0 > 1:
        return None
    half = (1 - c0) ** 0.5
    lo, hi = -b - half, -b + half
    poly = [(P[k], tv[k]) for k in range(3)]
    for keep in (lambda x: x >= lo, lambda x: x <= hi):              # Sutherland-Hodgman against the two lines t = lo, t = hi
        bound = lo if keep(lo + 1) and not keep(lo - 1) else hi
        out = []
        for k in range(len(poly)):
            (p1, t1), (p2, t2) = poly[k - 1], poly[k]
            if keep(t2):
                if not keep(t1):
                    a = (bound - t1) / (t2 - t1); out.append((p1 + a * (p2 - p1), bound))
                out.append((p2, t2))
            elif keep(t1):
                a = (bound - t1) / (t2 - t1); out.append((p1 + a * (p2 - p1), bound))
        poly = out
        if not poly:
            return None
    return ("poly", [q.tolist() for q, _ in poly])


def vector_to_svg(tt):
    """A VectorImage as an editable SVG at its own size: plain triangles as polygons (merged per colour), rounded-edge triangles as
    the triangle clipped by the ellipse their circle coordinates describe, or the exact band when that map is rank one."""
    w, h = tt["size"]["x"], tt["size"]["y"]
    v, ix = tt["vertices"], tt["indices"]
    plain, clips, out = {}, [], []
    f = lambda x: ("%.4f" % x).rstrip("0").rstrip(".")
    for k in range(0, len(ix) - 2, 3):
        tri = [v[ix[k + j]] for j in range(3)]
        P = [(q["position"]["x"], q["position"]["y"]) for q in tri]
        r, g, b, a = unpack(tri[0]["tint"]["rgba"])
        col = "#%02X%02X%02X" % (r, g, b)
        op = round(a / 255, 4)
        poly = P
        if any(q["flags"]["rgba"] for q in tri):
            reg = _flagged_region(P, [(q["circle"]["x"], q["circle"]["y"]) for q in tri])
            if reg is None:
                continue
            if reg[0] == "ellipse":
                cid = "c%d" % len(clips)
                clips.append('<clipPath id="%s"><polygon points="%s"/></clipPath>' % (cid, " ".join("%s,%s" % (f(x), f(y)) for x, y in P)))
                out.append('<g clip-path="url(#%s)"><circle r="1" transform="matrix(%s)" fill="%s"%s/></g>' % (
                    cid, " ".join(f(x) for x in reg[1]), col, "" if op >= 0.999 else ' fill-opacity="%s"' % f(op)))
                continue
            poly = reg[1]
        if len(poly) >= 3:
            plain.setdefault((col, op), []).append("M%sZ" % " L".join("%s,%s" % (f(x), f(y)) for x, y in poly))
    paths = ['<path fill="%s" stroke="%s" stroke-width="0.05" stroke-linejoin="round"%s d="%s"/>' % (
        c, c, "" if o >= 0.999 else ' fill-opacity="%s" stroke-opacity="%s"' % (f(o), f(o)), "".join(d)) for (c, o), d in plain.items()]
    return ('<svg xmlns="http://www.w3.org/2000/svg" width="%s" height="%s" viewBox="0 0 %s %s">\n<defs>%s</defs>\n%s\n%s\n</svg>\n'
            % (f(w), f(h), f(w), f(h), "".join(clips), "\n".join(paths), "\n".join(out))).encode("utf-8")


def _safe(n):
    return re.sub(r"[^\w.-]+", "_", n).strip("_") or "unnamed"


def export_item(aa_dir, item):
    """Files for one catalog row at its true size: [(relative path, bytes)]. texture: PNG at full resolution. svg: the SVG and a PNG
    at 8x. icon: one PNG per UI scale at the exact size of its atlas slot."""
    import io as _io
    import UnityPy
    aa_dir = Path(aa_dir)
    files = []
    def png(img):
        b = _io.BytesIO(); img.save(b, "PNG"); return b.getvalue()
    if item["kind"] == "icon":
        for s, ib, ab in icon_bundles(aa_dir):
            idx = icon_index(aa_dir / ib, aa_dir / ab)
            e = idx.get(item["name"])
            if not e:
                continue
            tex = next(o for o in UnityPy.load(str(aa_dir / ab)).objects if o.path_id == e["tex_pid"]).read().image
            crop = tex.crop((round(e["x"]), round(e["y"]), round(e["x"] + e["w"]), round(e["y"] + e["h"]))).convert("RGBA")
            files.append(("%s_%s.png" % (_safe(item["name"]), s), png(crop)))
        return files
    obj = next(o for o in UnityPy.load(str(aa_dir / item["bundle"])).objects if o.path_id == int(item["path_id"]))
    if item["kind"] == "texture":
        return [("%s.png" % _safe(item["name"]), png(obj.read().image.convert("RGBA")))]
    tt = obj.read_typetree()
    return [("%s.svg" % _safe(item["name"]), vector_to_svg(tt)),
            ("%s@8x.png" % _safe(item["name"]), png(render_vector(tt, 8 * max(tt["size"]["x"], tt["size"]["y"]))))]


def export_all(aa_dir, rows, dest, progress=None):
    """Export many catalog rows into dest/<group>/<kind>/... plus index.csv (name, kind, size, bundle, path id, files). Bundles are
    loaded once per bundle."""
    import csv
    import io as _io
    import UnityPy
    aa_dir, dest = Path(aa_dir), Path(dest)
    dest.mkdir(parents=True, exist_ok=True)
    index = []
    def put(rel, data):
        f = dest / rel
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_bytes(data)
        return rel
    def png(img):
        b = _io.BytesIO(); img.save(b, "PNG"); return b.getvalue()
    icons = [r for r in rows if r["kind"] == "icon"]
    others = {}
    for r in rows:
        if r["kind"] != "icon":
            others.setdefault(r["bundle"], []).append(r)
    done, total = 0, len(rows)
    for b, rs in sorted(others.items()):
        want = {int(r["path_id"]): r for r in rs}
        for o in UnityPy.load(str(aa_dir / b)).objects:
            r = want.get(o.path_id)
            if not r:
                continue
            try:
                base = "%s/%s/%s" % (r["group"], r["kind"], _safe(r["name"]))
                if r["kind"] == "texture":
                    fl = [put(base + ".png", png(o.read().image.convert("RGBA")))]
                else:
                    tt = o.read_typetree()
                    fl = [put(base + ".svg", vector_to_svg(tt)), put(base + "@8x.png", png(render_vector(tt, 8 * max(tt["size"]["x"], tt["size"]["y"]))))]
                index.append([r["name"], r["kind"], "%sx%s" % (r["w"], r["h"]), b, r["path_id"], " ".join(fl)])
            except Exception as ex:
                index.append([r["name"], r["kind"], "", b, r["path_id"], "ERROR " + str(ex)[:80]])
            done += 1
            if progress:
                progress("exporting " + b, done / max(1, total))
    if icons:
        names = {r["name"] for r in icons}
        per = {}
        for s, ib, ab in icon_bundles(aa_dir):
            idx = icon_index(aa_dir / ib, aa_dir / ab)
            atl = {o.path_id: o.read().image for o in UnityPy.load(str(aa_dir / ab)).objects
                   if o.type.name == "Texture2D" and o.path_id in {e["tex_pid"] for n, e in idx.items() if n in names}}
            for n in names:
                e = idx.get(n)
                if not e:
                    continue
                crop = atl[e["tex_pid"]].crop((round(e["x"]), round(e["y"]), round(e["x"] + e["w"]), round(e["y"] + e["h"]))).convert("RGBA")
                per.setdefault(n, []).append(put("icon/%s/%s_%s.png" % (s, _safe(n), s), png(crop)))
            if progress:
                progress("exporting icons " + s, 0.99)
        for r in icons:
            index.append([r["name"], "icon", "%sx%s at 2x" % (r["w"], r["h"]), ICONS % "2x", r["path_id"], " ".join(per.get(r["name"], []))])
    with open(dest / "index.csv", "w", newline="", encoding="utf-8") as fh:
        wr = csv.writer(fh)
        wr.writerow(["name", "kind", "size", "bundle", "path_id", "files"])
        wr.writerows(index)
    return {"folder": str(dest), "items": len(index), "errors": sum(1 for x in index if x[5].startswith("ERROR"))}


# ---------------------------------------------------------------- icons packed in sprite atlases
def _key(k):
    """A SpriteAtlas render-data key ({data[0..3]}, id) in any of its typetree shapes -> hashable tuple."""
    if isinstance(k, dict) and "first" in k:
        k = (k["first"], k["second"])
    g, i = k[0], k[1]
    return tuple(g[f"data[{n}]"] for n in range(4)) + (int(i),)


def icon_index(icons_path, atlas_path):
    """{base name: {sprite, path_id, w, h, tex_pid, atlas, x, y, rot}} for one UI scale. x, y, w, h: the sprite's full rect in the
    atlas texture, top-left origin (the texture as UnityPy decodes it)."""
    import UnityPy
    sprites = {}
    for o in UnityPy.load(str(icons_path)).objects:
        if o.type.name == "Sprite":
            tt = o.read_typetree()
            sprites[_key(tt["m_RenderDataKey"])] = (tt["m_Name"], o.path_id, tt["m_Rect"])
    out, heights = {}, {}
    env = UnityPy.load(str(atlas_path))
    for o in env.objects:
        if o.type.name == "Texture2D":
            d = o.read()
            heights[o.path_id] = (d.m_Height, d.m_Name)
    for o in env.objects:
        if o.type.name != "SpriteAtlas":
            continue
        tt = o.read_typetree()
        for k, v in tt["m_RenderDataMap"]:
            s = sprites.get(_key(k))
            tex = v["texture"]["m_PathID"]
            if not s or tex not in heights:
                continue
            name, pid, rect = s
            tr, off = v["textureRect"], v["textureRectOffset"]
            x0, y0 = tr["x"] - off["x"], tr["y"] - off["y"]               # the full sprite rect's origin (bottom-left, Unity)
            H = heights[tex][0]
            out[base_name(name)] = {"sprite": name, "path_id": pid, "w": rect["width"], "h": rect["height"], "tex_pid": tex,
                                    "atlas": heights[tex][1], "x": x0, "y": H - (y0 + rect["height"]), "rot": (v["settingsRaw"] >> 2) & 15}
    return out


def icon_classes(aa_dir):
    """{("icon", base name) | ("svg", VectorImage path id): [USS classes]} from the game's own image stylesheets: FMImages_2x (in
    ui-styles_assets_2x) maps every icon class to its sprite, FMImages_SVG (ui-styles_assets_default) every SVG class to its
    VectorImage. These classes are what a native USS skin targets to restyle or replace an icon."""
    import UnityPy
    aa_dir = Path(aa_dir)
    out = {}
    def sheet(bundle, name):
        f = aa_dir / bundle
        if not f.is_file():
            return None
        for o in UnityPy.load(str(f)).objects:
            if o.type.name == "MonoBehaviour":
                try:
                    tt = o.read_typetree()
                except Exception:
                    continue
                if tt.get("m_Name") == name:
                    return tt
        return None
    def classes_by_asset(tt):
        by = {}
        for r in tt["m_Rules"]:
            idx = [v["valueIndex"] for prop in r["m_Properties"] for v in prop["m_Values"] if v["m_ValueType"] == 6]   # 6 = asset reference
            names = []
            for cs in r.get("m_ComplexSelectors", []) or []:
                parts = cs["m_Selectors"][-1]["m_Parts"]
                names += [p["m_Value"] for p in parts if p["m_Type"] == 3]
            for i in idx:
                pid = tt["assets"][i]["m_PathID"]
                by.setdefault(pid, []).extend(n for n in names if n not in by.get(pid, []))
        return by
    s2 = sheet("ui-styles_assets_2x.bundle", "FMImages_2x")
    if s2 and (aa_dir / (ICONS % "2x")).is_file():
        names = {}
        for o in UnityPy.load(str(aa_dir / (ICONS % "2x"))).objects:
            if o.type.name == "Sprite":
                names[o.path_id] = base_name(o.read_typetree()["m_Name"])
        for pid, cls in classes_by_asset(s2).items():
            if pid in names:
                out.setdefault(("icon", names[pid]), []).extend(cls)
    sv = sheet("ui-styles_assets_default.bundle", "FMImages_SVG")
    if sv:
        for pid, cls in classes_by_asset(sv).items():
            out.setdefault(("svg", str(pid)), []).extend(cls)
    return out


def icon_catalog(aa_dir):
    """Logical icons (one per name, all scales) from the 2x bundles, for the catalog."""
    aa_dir = Path(aa_dir)
    if not (aa_dir / (ICONS % "2x")).is_file() or not (aa_dir / (ATLASES % "2x")).is_file():
        return []
    idx = icon_index(aa_dir / (ICONS % "2x"), aa_dir / (ATLASES % "2x"))
    return [{"kind": "icon", "name": n, "w": round(e["w"]), "h": round(e["h"]), "format": "atlas sprite", "path_id": str(e["path_id"]),
             "bundle": ICONS % "2x", "group": "icon", "atlas": e["atlas"]} for n, e in sorted(idx.items())]


def icon_thumbnails(aa_dir, dest, tag, size=(160, 160)):
    """Crop every 2x icon out of its atlas: dest/<sprite path_id>_<tag>.png."""
    import UnityPy
    aa_dir, dest = Path(aa_dir), Path(dest)
    dest.mkdir(parents=True, exist_ok=True)
    idx = icon_index(aa_dir / (ICONS % "2x"), aa_dir / (ATLASES % "2x"))
    atl = {o.path_id: o.read().image for o in UnityPy.load(str(aa_dir / (ATLASES % "2x"))).objects
           if o.type.name == "Texture2D" and o.path_id in {e["tex_pid"] for e in idx.values()}}
    for e in idx.values():
        im = atl[e["tex_pid"]].crop((round(e["x"]), round(e["y"]), round(e["x"] + e["w"]), round(e["y"] + e["h"]))).convert("RGBA")
        im.thumbnail(size)
        im.save(dest / ("%s_%s.png" % (e["path_id"], tag)))
    return len(idx)


def render_icon(src_bytes, w, h):
    """The replacement for one icon slot as an RGBA image of w x h: an SVG is rasterised at that size, a bitmap is fitted (contain)."""
    if sniff(src_bytes) == "svg":
        tt = {"size": {"x": float(w), "y": float(h)}, "vertices": [], "indices": [], "settings": []}
        svg_to_vector(tt, src_bytes)
        from PIL import Image
        img = render_vector(tt, 4 * max(w, h))
        return img.resize((w, h), Image.LANCZOS)
    return fit_image(src_bytes, w, h, "contain")


def apply_icon_swaps(atlas_src, icons_src, out_dir, swaps, source_dir, touched=None):
    """Paste the replacements of 'swaps' (kind icon) into one scale's atlas textures; writes out_dir/<atlas bundle> when anything
    changed. Crunch atlases are written as plain DXT5. Returns (changed, notes)."""
    import UnityPy
    from PIL import Image
    idx = icon_index(icons_src, atlas_src)
    env = UnityPy.load(str(atlas_src))
    texs = {o.path_id: o for o in env.objects if o.type.name == "Texture2D"}
    work, notes = {}, []
    for s in swaps:
        e = idx.get(s["name"])
        if not e:
            notes.append("%s: no icon %r at this scale" % (Path(atlas_src).name, s["name"]))
            continue
        if e["rot"]:
            raise ValueError("icon %s is packed rotated in its atlas; not supported" % s["name"])
        if e["tex_pid"] not in work:
            work[e["tex_pid"]] = texs[e["tex_pid"]].read().image.convert("RGBA")
        img = work[e["tex_pid"]]
        w, h = max(1, round(e["w"])), max(1, round(e["h"]))
        x, y = round(e["x"]), round(e["y"])
        img.paste(Image.new("RGBA", (w, h), (0, 0, 0, 0)), (x, y))
        img.paste(render_icon((Path(source_dir) / s["source"]).read_bytes(), w, h), (x, y))
    for pid, img in work.items():
        d = texs[pid].read()
        fmt = int(getattr(d.m_TextureFormat, "value", d.m_TextureFormat))
        if fmt in CRUNCH_TO:
            d.m_TextureFormat = CRUNCH_TO[fmt]
            notes.append("%s: atlas %s written as plain %s (was Crunch)" % (Path(atlas_src).name, d.m_Name, FORMATS[CRUNCH_TO[fmt]]))
        d.image = img
        d.save()
        if touched is not None:
            touched.add(pid)
    if work:
        (Path(out_dir) / Path(atlas_src).name).write_bytes(env.file.save(packer="original"))
    return bool(work), notes


def icon_bundles(aa_or_vanilla_dir):
    """[(scale, icons bundle, atlas bundle)] that exist in a folder."""
    d = Path(aa_or_vanilla_dir)
    return [(s, ICONS % s, ATLASES % s) for s in SCALES if (d / (ICONS % s)).is_file() and (d / (ATLASES % s)).is_file()]


# ---------------------------------------------------------------- SVG -> VectorImage
def _parse_colour(c):
    if c is None or c.value is None:
        return None
    a = c.alpha if c.alpha is not None else 255
    return (c.red, c.green, c.blue, a)


def svg_polygons(svg_bytes, width, height, tolerance=0.25):
    """[(rgba, [ring, ...])] filled shapes of an SVG scaled into width x height (aspect kept, centred). Rings are lists of (x, y).
    Strokes are not converted (listed in the notes)."""
    from svgelements import SVG, Shape, Path as SPath, Move, Close
    doc = SVG.parse(io.BytesIO(svg_bytes), reify=True)
    vb = doc.viewbox
    vw, vh = (vb.width, vb.height) if vb is not None else (doc.width or width, doc.height or height)
    k = min(width / vw, height / vh) if vw and vh else 1.0
    ox, oy = (width - vw * k) / 2 - (vb.x * k if vb is not None else 0), (height - vh * k) / 2 - (vb.y * k if vb is not None else 0)
    shapes, notes = [], []
    for el in doc.elements():
        if not isinstance(el, Shape):
            continue
        fill = _parse_colour(el.fill)
        if el.stroke is not None and el.stroke.value is not None and (el.stroke_width or 0) > 0:
            notes.append("a stroke was ignored (convert strokes to filled paths before importing)")
        if fill is None or fill[3] == 0:
            continue
        p = SPath(el)                                      # svgelements already folds fill-opacity into the fill's alpha
        rings, cur = [], []
        for seg in p.segments():
            if isinstance(seg, Move):
                if len(cur) > 2:
                    rings.append(cur)
                cur = [(seg.end.x, seg.end.y)]
                continue
            if isinstance(seg, Close):
                if len(cur) > 2:
                    rings.append(cur)
                cur = []
                continue
            if type(seg).__name__ == "Line":
                n = 1
            else:                                               # curves: about one point per 2 output pixels, 4..64
                try:
                    n = min(64, max(4, int(seg.length(error=1e-3) * k / 2)))
                except Exception:
                    n = 16
            for i in range(1, n + 1):
                q = seg.point(i / n)
                cur.append((q.x, q.y))
        if len(cur) > 2:
            rings.append(cur)
        rings = [[(x * k + ox, y * k + oy) for x, y in r] for r in rings]
        if rings:
            shapes.append((fill, rings, el.values.get("fill-rule", "nonzero")))
    return shapes, sorted(set(notes))


def _area(r):
    return sum(r[i][0] * r[i - 1][1] - r[i - 1][0] * r[i][1] for i in range(len(r))) / 2


def _inside(pt, ring):
    x, y, c = pt[0], pt[1], False
    for i in range(len(ring)):
        x1, y1 = ring[i - 1]
        x2, y2 = ring[i]
        if (y1 > y) != (y2 > y) and x < (x2 - x1) * (y - y1) / ((y2 - y1) or 1e-12) + x1:
            c = not c
    return c


def triangulate(rings):
    """Rings of one filled shape -> (points, triangle indices). Nesting depth decides fill (even-odd): a ring inside an odd number
    of others is a hole of its nearest container."""
    import numpy as np
    import mapbox_earcut as earcut
    rings = [r for r in rings if abs(_area(r)) > 1e-6]
    depth = [sum(1 for j, o in enumerate(rings) if j != i and _inside(r[0], o)) for i, r in enumerate(rings)]
    pts, tris = [], []
    for i, r in enumerate(rings):
        if depth[i] % 2:
            continue
        holes = [h for j, h in enumerate(rings) if depth[j] == depth[i] + 1 and _inside(h[0], r)]
        verts = [r] + holes
        flat = np.array([p for ring in verts for p in ring], dtype=np.float64).reshape(-1, 2)
        ends = np.array(np.cumsum([len(x) for x in verts]), dtype=np.uint32)
        idx = earcut.triangulate_float64(flat, ends)
        base = len(pts)
        pts += [tuple(p) for p in flat]
        tris += [base + int(t) for t in idx]
    return pts, tris


def svg_to_vector(tt, svg_bytes):
    """Replace a VectorImage typetree's mesh with the SVG's filled shapes (plain triangles, no gradients). Keeps the size."""
    w, h = tt["size"]["x"], tt["size"]["y"]
    shapes, notes = svg_polygons(svg_bytes, w, h)
    if not shapes:
        raise ValueError("the SVG has no filled shapes")
    verts, idx = [], []
    for fill, rings, _rule in shapes:
        pts, tris = triangulate(rings)
        base = len(verts)
        col = pack(*fill)
        for x, y in pts:
            verts.append({"position": {"x": float(x), "y": float(y), "z": 0.0}, "tint": {"rgba": col}, "uv": {"x": 0.0, "y": 0.0},
                          "settingIndex": 0, "flags": {"rgba": 0}, "circle": {"x": 0.0, "y": 0.0, "z": 0.0, "w": 0.0}})
        idx += [base + t for t in tris]
    if len(verts) > 65535:
        raise ValueError("the SVG is too detailed: %d vertices (max 65535)" % len(verts))
    tt["vertices"], tt["indices"], tt["settings"] = verts, idx, []
    tt["atlas"] = {"m_FileID": 0, "m_PathID": 0}
    return notes + ["%d triangles" % (len(idx) // 3)]


def render_svg_png(svg_bytes, w=256, h=256):
    """PNG of an SVG as the game will draw it after conversion (filled shapes as triangles)."""
    tt = {"size": {"x": float(w), "y": float(h)}, "vertices": [], "indices": [], "settings": []}
    svg_to_vector(tt, svg_bytes)
    buf = io.BytesIO()
    render_vector(tt, max(w, h)).save(buf, "PNG")
    return buf.getvalue()


def sniff(data):
    """'png' | 'jpg' | 'webp' | 'svg' | None from the file's first bytes."""
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return "png"
    if data[:3] == b"\xff\xd8\xff":
        return "jpg"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "webp"
    head = data[:2048].lstrip().lower()
    if head.startswith(b"<?xml") or head.startswith(b"<svg") or b"<svg" in head:
        return "svg"
    return None


# ---------------------------------------------------------------- build step
def apply_swaps(src, out_dir, swaps, source_dir, touched=None):
    """Patch one bundle with its swaps; writes out_dir/<name> when anything changed. Returns (changed, notes, done path ids)."""
    import UnityPy
    env = UnityPy.load(str(src))
    want = {int(s["path_id"]): s for s in swaps}
    notes, done = [], []
    for obj in env.objects:
        s = want.get(obj.path_id)
        if not s:
            continue
        data = (Path(source_dir) / s["source"]).read_bytes()
        if s["kind"] == "texture":
            if obj.type.name != "Texture2D":
                raise ValueError("%s: path id %s is not a texture" % (Path(src).name, obj.path_id))
            notes += swap_texture(obj, data, s.get("fit", "cover"))
        else:
            tt = obj.read_typetree()
            if "vertices" not in tt:
                raise ValueError("%s: path id %s is not an SVG (VectorImage)" % (Path(src).name, obj.path_id))
            notes += ["%s: %s" % (tt.get("m_Name"), n) for n in svg_to_vector(tt, data)]
            obj.save_typetree(tt)
        done.append(obj.path_id)
        if touched is not None:
            touched.add(obj.path_id)
    missing = sorted(set(want) - set(done))
    if missing:
        raise ValueError("%s: no object with path id %s (game updated? re-pick the image)" % (Path(src).name, missing))
    if done:
        (Path(out_dir) / Path(src).name).write_bytes(env.file.save(packer="original"))
    return bool(done), notes, done


def check_swap(e):
    """Validate one image_swaps entry (shape only; the object is checked at build)."""
    if not isinstance(e, dict) or set(e) - {"bundle", "path_id", "name", "kind", "source", "fit", "note", "where"}:
        raise ValueError("image swap needs bundle, path_id, name, kind, source (optional fit, note, where)")
    from .native import PLACES
    if "where" in e and (not isinstance(e["where"], list) or set(e["where"]) - set(PLACES)):
        raise ValueError("where must be a list of: " + ", ".join(PLACES))
    if not BUNDLE_RE.fullmatch(str(e.get("bundle", ""))):
        raise ValueError("image swap bundle must be a ui-*.bundle file name: %r" % e.get("bundle"))
    if not (isinstance(e.get("path_id"), str) and re.fullmatch(r"-?\d{1,20}", e["path_id"])):
        raise ValueError("image swap path_id must be the object's path id as a decimal string (64-bit ids do not fit a JavaScript number)")
    if e.get("kind") not in ("texture", "svg", "icon"):
        raise ValueError("image swap kind must be texture, svg or icon")
    if not SOURCE_RE.fullmatch(str(e.get("source", ""))):
        raise ValueError("image swap source must be a file name in the project's images folder (png, jpg, webp or svg)")
    if e["kind"] != "icon" and (e["kind"] == "svg") != e["source"].lower().endswith(".svg"):
        raise ValueError("an svg swap takes an .svg file; a texture swap takes png, jpg or webp")
    if e["kind"] == "icon" and e["bundle"] != ICONS % "2x":
        raise ValueError("an icon swap names the icon by its 2x sprite (bundle %s)" % (ICONS % "2x"))
    if e.get("fit", "cover") not in FITS:
        raise ValueError("fit must be cover, stretch or contain")
