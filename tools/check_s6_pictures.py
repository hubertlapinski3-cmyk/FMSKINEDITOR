"""S6 of the Simple mode plan: check "pictures in three steps" against the REAL game, offline, and write the figures the S6 report quotes.

    python tools/check_s6_pictures.py <scratch workspace> [out.json]

Run it with FM27SE_WORKSPACE pointing at a SCRATCH workspace that already holds the snapshot and the style index (for example a copy of the persistent scratch of
tools/run_studio_scratch.py --keep); FM27SE_SKINS_DIR is set to a folder inside it, so the native export never reaches the real skins folder. The game is only read.

It measures (1) the catalogue by kind and how many icons and SVGs a native skin can replace (a USS class draws them); (2) for one icon and one wallpaper picked from the
catalogue: the render of a layout that shows them, with and without the skin, counting the elements drawn with the user's picture; (3) the native export of the same project:
its images.uss must hold exactly the rules the render overlay applies (the same selectors and values), and the picture files it names."""
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def main():
    ws_dir = Path(sys.argv[1])
    os.environ["FM27SE_WORKSPACE"] = str(ws_dir)
    os.environ["FM27SE_SKINS_DIR"] = str(ws_dir / "skins-s6check")
    from collections import Counter
    from PIL import Image
    from skin_editor import images, native
    from skin_editor.render import overlay
    from skin_editor.api import rpc
    from skin_editor.engine import Engine
    e = Engine()

    def call(m, p=None):
        r = json.loads(rpc.handle(e, json.dumps({"jsonrpc": "2.0", "id": 1, "method": m, "params": p or {}})))
        if "error" in r:
            raise RuntimeError("%s: %s" % (m, r["error"]))
        return r["result"]

    aa = e.need_info()["aa_dir"]
    cat = images.catalog(e.ws, aa)
    cls = images.icon_classes(aa)
    out = {"catalog": dict(Counter(r["kind"] for r in cat)),
           "native_replaceable": dict(Counter(r["kind"] for r in cat if r["kind"] in ("icon", "svg") and cls.get(("icon", r["name"]) if r["kind"] == "icon" else ("svg", str(r["path_id"]))))),
           "wallpaper_places": {k: v[0] for k, v in native.PLACES.items()}}

    pics = ws_dir / "s6-pictures"; pics.mkdir(exist_ok=True)
    Image.new("RGBA", (64, 64), (255, 0, 160, 255)).save(pics / "icon.png")
    Image.new("RGB", (640, 360), (20, 160, 90)).save(pics / "wallpaper.jpg", quality=90)
    name = "s6-check"
    if name not in call("project.list"):
        call("project.create_folder", {"name": name, "target": "native"})
    icon = next(r for r in cat if r["kind"] == "icon" and r["name"] == "tick_small")              # drawn on the Preferences card (S5 showcase)
    tex = next(r for r in cat if r["kind"] == "texture" and "base-layer" not in r["name"] and native.default_places(r["name"]) == ["report-pages", "main-screens"])
    call("images.commit", {"project": name, "bundle": icon["bundle"], "path_id": icon["path_id"], "kind": "icon", "name": icon["name"], "path": str(pics / "icon.png")})
    call("images.commit", {"project": name, "bundle": tex["bundle"], "path_id": tex["path_id"], "kind": "texture", "name": tex["name"], "where": ["main-screens"], "path": str(pics / "wallpaper.jpg")})
    out["swaps"] = {"icon": icon["name"], "wallpaper": tex["name"], "wallpaper_where": ["main-screens"]}

    def drawn_with_mine(layout_name, skin):
        row = next(x for x in call("render.layouts", {"q": layout_name})["layouts"] if x["name"] == layout_name)
        r = call("render.layout", {"bundle": row["bundle"], "path_id": row["path_id"], "project": name, "skin": skin, "max_nodes": 0, "depth": 6})
        n = 0

        def walk(nd):
            nonlocal n
            a = (nd.get("assets") or {}).get("background-image") or {}
            n += 1 if a.get("project") and a.get("data_url") else 0
            for c in nd.get("children", []):
                walk(c)
        for t in r["tree"]:
            walk(t)
        return {"layout": layout_name, "skin": skin, "elements_with_your_picture": n, "project_images_counted": (r.get("assets") or {}).get("project_images", 0),
                "not_applied": (r.get("overlay") or {}).get("not_applied")}
    out["render"] = [drawn_with_mine(L, s) for L in ("PreferencesFMMenuCard", "SquadScreen") for s in (False, True)]

    exp = call("native.put", {"project": name})
    res = call("jobs.wait", {"id": exp["job"], "timeout": 300})
    folder = Path(os.environ["FM27SE_SKINS_DIR"]) / name
    uss = (folder / "images.uss").read_text(encoding="utf-8") if (folder / "images.uss").is_file() else ""
    exported = overlay._parse_raw(uss.split("*/", 1)[-1])
    from skin_editor import project as project_mod
    p = project_mod.load(e.ws, name)
    mine, files, skipped = overlay.image_rules(p, cls, project_mod.images_dir(e.ws, name))
    out["export"] = {"state": res["state"], "images": (res.get("result") or {}).get("images"), "problems": (res.get("result") or {}).get("problems"),
                     "skipped": (res.get("result") or {}).get("skipped"),
                     "images_uss_rules": len(exported), "overlay_rules": len(mine), "same_rules": sorted(map(json.dumps, exported)) == sorted(map(json.dumps, mine)),
                     "files_named_exist": all((folder / fn).is_file() for fn in files)}
    text = json.dumps(out, indent=1)
    if len(sys.argv) > 2:
        Path(sys.argv[2]).write_text(text + "\n", encoding="utf-8", newline="\n")
    print(text)


if __name__ == "__main__":
    main()
