"""S7 of the Simple mode plan: the share round trip against the REAL game, offline, and the figures the S7 report quotes.

    python tools/check_s7_share.py <scratch workspace> [out.json]

Needs a SCRATCH workspace (FM27SE_WORKSPACE is set to it) holding the snapshot, the style index and the project `s6-check` made by tools/check_s6_pictures.py (a real icon
and a real wallpaper). The native exports go to a folder inside it, never to the real skins folder; the game is only read. Steps: save `s6-check` as a skin file, inspect it,
open it as the new project `s7-copy`, export both natively and compare every exported file but the editor's own (marker, README); then Start over on the copy."""
import hashlib
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def main():
    ws_dir = Path(sys.argv[1])
    os.environ["FM27SE_WORKSPACE"] = str(ws_dir)
    os.environ["FM27SE_SKINS_DIR"] = str(ws_dir / "skins-s7check")
    from skin_editor import native, project as project_mod
    from skin_editor.api import rpc
    from skin_editor.engine import Engine
    e = Engine()

    def call(m, p=None):
        r = json.loads(rpc.handle(e, json.dumps({"jsonrpc": "2.0", "id": 1, "method": m, "params": p or {}})))
        if "error" in r:
            raise RuntimeError("%s: %s" % (m, r["error"]))
        return r["result"]

    out = {}
    zf = ws_dir / "s6-check.zip"
    saved = call("share.save", {"project": "s6-check", "path": str(zf), "studio_version": "check-s7", "overwrite": True})
    out["saved"] = {k: saved[k] for k in ("skin", "files", "bytes", "manifest")}
    out["inspected"] = call("share.inspect", {"path": str(zf)})
    if "s7-copy" in call("project.list"):
        project_mod.delete(e.ws, "s7-copy")
    opened = call("share.open", {"path": str(zf), "name": "s7-copy"})
    out["opened"] = {k: opened[k] for k in ("sheets", "files", "images", "fonts", "notes")}
    skins = Path(os.environ["FM27SE_SKINS_DIR"])

    def files(folder):
        f = Path(folder)
        return {p.relative_to(f).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in f.rglob("*") if p.is_file() and p.name not in (native.MARKER, "README.txt")}
    aa = e.need_info()["aa_dir"]
    a = native.export(e.ws, project_mod.load(e.ws, "s6-check"), e.index, aa, skins)
    b = native.export(e.ws, project_mod.load(e.ws, "s7-copy"), e.index, aa, skins)
    fa, fb = files(a["folder"]), files(b["folder"])
    # The copy carries the original's sheets as IMPORTED sheets (renamed -2, so they never collide with the export's own) and its pictures as imported files under
    # images/images/ (the import keeps a skin's own folder layout): so compare CONTENT: the picture bytes, and the sheets' rules with url() reduced to the file name.
    import re
    pics = lambda f: sorted(v for k, v in f.items() if k.startswith("images/"))

    def rules_of(folder, sheets):
        txt = "".join((Path(folder) / s).read_text(encoding="utf-8") for s in sheets)
        txt = re.sub(r"/\*.*?\*/", "", txt, flags=re.S)
        txt = re.sub(r'url\("(?:[^"/]*/)*([^"/]+)"\)', r'url("\1")', txt)
        return sorted(" ".join(r.split()) for r in re.findall(r"[^{}]+\{[^{}]*\}", txt) if r.strip())
    out["round_trip"] = {"original_files": len(fa), "copy_files": len(fb), "original_problems": a["problems"], "copy_problems": b["problems"],
                         "original_sheets": a["sheets"], "copy_sheets": b["sheets"],
                         "same_picture_bytes": pics(fa) == pics(fb), "pictures": len(pics(fa)),
                         "same_rules": rules_of(a["folder"], a["sheets"]) == rules_of(b["folder"], b["sheets"]), "rules": len(rules_of(a["folder"], a["sheets"]))}
    pre = call("project.start_over_preview", {"project": "s7-copy"})
    done = call("project.start_over", {"project": "s7-copy", "confirm": True})
    out["start_over"] = {"lost": pre["lost"], "after": native.changes(done["project"]), "trash_exists": Path(done["trash"]).is_dir()}
    text = json.dumps(out, indent=1)
    if len(sys.argv) > 2:
        Path(sys.argv[2]).write_text(text + "\n", encoding="utf-8", newline="\n")
    print(text)


if __name__ == "__main__":
    main()
