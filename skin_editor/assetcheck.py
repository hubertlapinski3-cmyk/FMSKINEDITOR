"""Conflict report for a project's image swaps (textures, icons, SVG), read-only. Each row: {severity: error|warning|info, code, message,
image: {kind, name, bundle, path_id}}. Errors would stop or silently break a build/export; warnings are things that look wrong;
info is worth knowing. Nothing is written."""
import io
import re

from . import images, native
from . import project as project_mod

ASPECT_TOL = 0.08


def _row(sev, code, msg, e=None):
    r = {"severity": sev, "code": code, "message": msg}
    if e:
        r["image"] = {"kind": e["kind"], "name": e.get("name", ""), "bundle": e["bundle"], "path_id": e["path_id"]}
    return r


def _dims(path):
    """(w, h) of a stored replacement, or None for an SVG or an unreadable file."""
    if path.suffix.lower() == ".svg":
        return None
    try:
        from PIL import Image
        with Image.open(path) as im:
            return im.size
    except Exception:
        return None


def conflicts(ws, project, catalog=None, icon_classes=None, target=None):
    """catalog: images.catalog rows (None: the checks that need the game's images are skipped). icon_classes: images.icon_classes (native
    icon/SVG placement), None to skip. target: native or bundles (default: the project's output)."""
    p = project_mod.validate(project_mod.migrate(project))
    target = target or p["options"].get("output", "bundles")
    swaps = p.get("image_swaps", [])
    out = []
    folder = project_mod.images_dir(ws, p["name"])
    rows = {(r["bundle"], str(r["path_id"])): r for r in (catalog or [])}
    uses = {}
    for e in swaps:
        uses.setdefault(e["source"], []).append(e)
    for e in swaps:
        f = folder / e["source"]
        label = "%s %s" % (e["kind"], e.get("name") or e["path_id"])
        if not f.is_file():
            out.append(_row("error", "source-missing", "%s: the replacement file %s is not in the project's images folder" % (label, e["source"]), e))
            continue
        if catalog is not None:
            cat = rows.get((e["bundle"], str(e["path_id"])))
            if cat is None:
                out.append(_row("error", "slot-gone", "%s: the game has no image with this id in %s (game updated? pick the image again)" % (label, e["bundle"]), e))
                continue
            d = _dims(f)
            if d and cat.get("w") and cat.get("h") and e["kind"] != "svg":
                want = cat["w"] / cat["h"]
                have = d[0] / d[1]
                if abs(have - want) / want > ASPECT_TOL and e.get("fit", "cover") != "stretch":
                    out.append(_row("warning", "aspect", "%s: the game's picture is %dx%d (ratio %.2f) but yours is %dx%d (%.2f); fit '%s' will %s" % (
                        label, cat["w"], cat["h"], want, d[0], d[1], have, e.get("fit", "cover"),
                        "crop it" if e.get("fit", "cover") == "cover" else "leave empty bars"), e))
                if e["kind"] == "texture" and d[0] * d[1] < 0.4 * cat["w"] * cat["h"]:
                    out.append(_row("info", "small", "%s: yours (%dx%d) has fewer pixels than the game's (%dx%d); it will look soft" % (label, d[0], d[1], cat["w"], cat["h"]), e))
            if cat.get("format_id") in images.CRUNCH_TO:
                out.append(_row("info", "crunch", "%s: the game stores it Crunch-compressed; the build writes plain %s, so the bundle grows" % (
                    label, images.FORMATS[images.CRUNCH_TO[cat["format_id"]]]), e))
    for src, es in uses.items():
        if len(es) > 1:
            out.append(_row("info", "shared-source", "%s is used for %d slots: %s" % (src, len(es), ", ".join(x.get("name") or x["path_id"] for x in es))))
    if target == "native":
        painted = {}
        for e in swaps:
            if e["kind"] == "texture":
                for w in (e.get("where") or native.default_places(e.get("name", ""))):
                    painted.setdefault(w, []).append(e)
            elif icon_classes is not None:
                key = ("icon", e["name"]) if e["kind"] == "icon" else ("svg", str(e["path_id"]))
                if not icon_classes.get(key):
                    out.append(_row("warning", "no-class", "%s %s: no USS class draws it (the game places it in code), so a native skin cannot replace it; use the bundle target" % (e["kind"], e.get("name") or e["path_id"]), e))
        for w, es in painted.items():
            if len(es) > 1:
                nm = lambda x: x.get("name") or x["path_id"]
                out.append(_row("warning", "same-place", "%d wallpapers are shown on %s: %s is the one you see (it is written last); %s %s hidden there, so delete %s if you do not want %s" % (
                    len(es), native.PLACES[w][0], nm(es[-1]), ", ".join(nm(x) for x in es[:-1]), "is" if len(es) == 2 else "are",
                    "it" if len(es) == 2 else "them", "it" if len(es) == 2 else "them"), es[-1]))
        taken = set(p.get("native_support", []))
        for e in swaps:
            if e["kind"] == "texture":
                fn = "images/%s.%s" % (images._safe(e["name"]), "jpg" if images.sniff((folder / e["source"]).read_bytes()) == "jpg" else "png") if (folder / e["source"]).is_file() else None
                if fn and fn in taken:
                    out.append(_row("error", "name-clash", "%s: the export would write %s, which the imported skin already has" % (e["name"], fn), e))
        sel_hits = []
        from . import projfmt
        pd = projfmt.folder(ws, p["name"])
        for s in p.get("native_sheets", []):
            try:
                text = (pd / s).read_text(encoding="utf-8-sig")
            except OSError:
                continue
            for w in painted:
                if any(sel in text for sel in native.PLACES[w][1][0].split(", ")) and "background-image" in text:
                    sel_hits.append((w, s))
        for w, s in sel_hits:
            out.append(_row("info", "imported-paints", "the imported sheet %s also styles %s; your wallpaper rule is written after it and wins ties" % (s.split("/")[-1], native.PLACES[w][0])))
    else:
        for e in swaps:
            if e["kind"] == "icon" and e["source"].lower().endswith(".svg"):
                out.append(_row("info", "icon-svg", "icon %s: the SVG is rendered to pixels for every UI scale" % e["name"], e))
        if p.get("native_sheets"):
            out.append(_row("info", "native-dropped", "the %d imported native sheet(s) and their pictures are not part of a bundle build" % len(p["native_sheets"])))
    order = {"error": 0, "warning": 1, "info": 2}
    out.sort(key=lambda r: order[r["severity"]])
    return out
