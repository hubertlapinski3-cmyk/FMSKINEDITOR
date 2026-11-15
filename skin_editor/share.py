"""Share and undo (docs/SIMPLE-MODE-PLAN.md, S7).

save:        the skin as ONE file: a zip of the native skin folder this project exports (the same export "Put it in the game" writes), with a manifest inside
             (`fm-skin-studio.json`: the share format, the Studio version, the game build, the skin's name, every file with its SHA-256). The editor's own export marker is
             left out: it belongs to this PC's skins folder, and a copy of it would make another Studio treat the unzipped folder as its own export.
inspect:     what a downloaded skin file holds, BEFORE anything is made from it: the skin's name, the manifest's versions, the sheets, pictures and fonts, and the files that are
             refused. Nothing is written.
open_copy:   the skin file as a NEW project, through the existing read-only import of a native skin folder: the zip is extracted into a private temporary folder (paths checked,
             sizes capped, only the file types a native skin uses), then imported; nothing is put into the game, nothing is applied to another project.
start_over:  back to the game's look: the project goes to the workspace trash (restorable by hand) and an empty project of the same name takes its place. `lost` says first what
             goes, in counts a person can check."""
import hashlib
import json
import shutil
import tempfile
import time
import zipfile
from pathlib import Path, PurePosixPath

from . import native
from . import project as project_mod

FORMAT = "fm-skin-studio-share/1"
MANIFEST = "fm-skin-studio.json"
ALLOWED = {".uss", ".json", ".png", ".jpg", ".jpeg", ".webp", ".svg", ".ttf", ".otf", ".txt"}
MAX_FILES = 5000
MAX_TOTAL = 300 * 1024 * 1024           # uncompressed bytes, all files together
MAX_ONE = 60 * 1024 * 1024


def save(ws, p, index, aa_dir, dest, studio_version=None, game_build=None, overwrite=False):
    """Write the skin file. -> {file, skin, files, bytes, manifest}."""
    dest = Path(dest)
    if dest.suffix.lower() != ".zip":
        raise ValueError("a skin file must end in .zip")
    if dest.exists() and not overwrite:
        raise ValueError("that file exists; choose another name or confirm replacing it")
    if not native.changes(p):
        raise ValueError("this skin changes nothing yet: change a colour first")
    with tempfile.TemporaryDirectory(prefix="fmss-save-") as tmp:
        rep = native.export(ws, p, index, aa_dir, Path(tmp), None, None)
        folder = Path(rep["folder"])
        skin_dir = folder.name
        files = []
        for f in sorted(folder.rglob("*")):
            if f.is_file() and f.name != native.MARKER:
                rel = f.relative_to(folder).as_posix()
                files.append({"path": skin_dir + "/" + rel, "sha256": hashlib.sha256(f.read_bytes()).hexdigest(), "bytes": f.stat().st_size})
        man = {"format": FORMAT, "studio_version": studio_version or "unknown", "game_build": game_build, "skin": rep["skin"], "folder": skin_dir,
               "made_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "files": files,
               "note": "A Football Manager 27 skin made with FM Skin Studio. Unzip the folder into Documents/Sports Interactive/Football Manager 27/skins, or open this file in FM Skin Studio."}
        part = dest.with_name(dest.name + ".part")
        with zipfile.ZipFile(part, "w", zipfile.ZIP_DEFLATED) as z:
            z.writestr(MANIFEST, json.dumps(man, indent=1))
            for e in files:
                z.write(folder / e["path"].split("/", 1)[1], e["path"])
        part.replace(dest)
    return {"file": str(dest), "skin": man["skin"], "files": len(files), "bytes": dest.stat().st_size, "manifest": {k: man[k] for k in ("format", "studio_version", "game_build", "skin")}}


def _safe_members(z):
    """(members to extract, refused [(name, why)]). Raises when the archive as a whole is unsafe (too many files, too large, a path that leaves the folder)."""
    infos = [i for i in z.infolist() if not i.is_dir()]
    if len(infos) > MAX_FILES:
        raise ValueError("the skin file holds too many files (%d; at most %d)" % (len(infos), MAX_FILES))
    if sum(i.file_size for i in infos) > MAX_TOTAL:
        raise ValueError("the skin file unpacks to more than %d MB" % (MAX_TOTAL // (1024 * 1024)))
    keep, refused = [], []
    for i in infos:
        name = i.filename.replace("\\", "/")
        pp = PurePosixPath(name)
        if pp.is_absolute() or ".." in pp.parts or (pp.parts and ":" in pp.parts[0]):
            raise ValueError("the skin file has a path that leaves its folder (%s); it was not opened" % name)
        if name == MANIFEST:
            continue
        if pp.suffix.lower() not in ALLOWED:
            refused.append((name, "not a file type a skin uses"))
        elif i.file_size > MAX_ONE:
            refused.append((name, "larger than %d MB" % (MAX_ONE // (1024 * 1024))))
        elif pp.name == native.MARKER:
            refused.append((name, "another Studio's export marker"))
        else:
            keep.append(i)
    return keep, refused


def _skin_root(names):
    """The folder of the archive that holds skin.json: the root, or ONE folder level down. None when there is none or more than one."""
    roots = sorted({str(PurePosixPath(n).parent) for n in names if PurePosixPath(n).name == "skin.json" and len(PurePosixPath(n).parts) <= 2})
    return roots[0] if len(roots) == 1 else None


def inspect(path, current_build=None):
    """What the skin file holds; nothing is written. -> {skin, folder, manifest, sheets, pictures, fonts, files, refused, build_note}."""
    path = Path(path)
    if not path.is_file() or not zipfile.is_zipfile(path):
        raise ValueError("that is not a skin file (a .zip)")
    with zipfile.ZipFile(path) as z:
        keep, refused = _safe_members(z)
        names = [i.filename.replace("\\", "/") for i in keep]
        root = _skin_root(names)
        if root is None:
            raise ValueError("the skin file has no skin.json (or more than one skin); it is not a skin made for the game's skins folder")
        prefix = "" if root == "." else root + "/"
        man = None
        if MANIFEST in z.namelist():
            try:
                man = json.loads(z.read(MANIFEST).decode("utf-8"))
            except ValueError:
                man = None
        sk = json.loads(z.read(prefix + "skin.json").decode("utf-8-sig"))
    inside = [n for n in names if n.startswith(prefix)]
    outside = [n for n in names if not n.startswith(prefix)]
    refused += [(n, "outside the skin's folder") for n in outside]
    sheets = sk.get("Sheets") if isinstance(sk.get("Sheets"), list) else []
    missing = [s for s in sheets if prefix + str(s).replace("\\", "/") not in inside]
    note = None
    if man and current_build and man.get("game_build") and man["game_build"] != current_build:
        note = "made for game build %s; this game is %s" % (man["game_build"], current_build)
    return {"skin": sk.get("Name") or (root if root != "." else path.stem), "folder": root, "manifest": {k: man.get(k) for k in ("format", "studio_version", "game_build", "skin", "made_utc")} if man else None,
            "sheets": len(sheets), "missing_sheets": missing,
            "pictures": sum(1 for n in inside if PurePosixPath(n).suffix.lower() in (".png", ".jpg", ".jpeg", ".webp", ".svg")),
            "fonts": sum(1 for n in inside if PurePosixPath(n).suffix.lower() in (".ttf", ".otf")),
            "files": len(inside), "refused": [{"file": n, "why": w} for n, w in refused], "build_note": note}


def open_copy(ws, path, name, current_build=None):
    """The skin file as a new project (a copy; the file is only read). -> the import's report plus the inspection."""
    info = inspect(path, current_build)
    if info["missing_sheets"]:
        raise ValueError("the skin file lists sheets it does not hold: %s" % ", ".join(info["missing_sheets"][:5]))
    from . import projfmt
    with tempfile.TemporaryDirectory(prefix="fmss-open-") as tmp:
        with zipfile.ZipFile(path) as z:
            keep, _refused = _safe_members(z)
            prefix = "" if info["folder"] == "." else info["folder"] + "/"
            for i in keep:
                n = i.filename.replace("\\", "/")
                if not n.startswith(prefix):
                    continue
                out = Path(tmp) / "skin" / n[len(prefix):]
                out.parent.mkdir(parents=True, exist_ok=True)
                with z.open(i) as src, open(out, "wb") as dst:
                    shutil.copyfileobj(src, dst)
        rep = projfmt.import_native_skin(ws, Path(tmp) / "skin", name)
    return dict(rep, inspected=info)


def lost(p):
    """What starting over takes away, by kind (native.changes, plus the files of an imported skin)."""
    return native.changes(p)


def start_over(ws, name, confirm=False, game_build=None):
    """Back to the game's look. -> {trash, lost, project}."""
    if confirm is not True:
        raise ValueError("confirm is required to start over")
    p = project_mod.load(ws, name)
    gone = lost(p)
    from . import projfmt
    trash = project_mod.delete(ws, name)
    fresh = project_mod.new(name, game_build)
    fresh["options"]["output"] = "native"
    projfmt.write(ws, fresh)
    from . import changes
    changes.record(name, "options", ["started over: back to the game's look"])
    return {"trash": str(trash), "lost": gone, "project": project_mod.load(ws, name)}
