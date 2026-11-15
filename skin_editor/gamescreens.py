"""Game screenshots for the tile organiser's backdrop (owner request, 2026-11-15, decided: Advanced tile organiser only; kept only on this PC).

A folder of PNG captures of the real game (taken with the inspector during a session, or added by hand) lives in the workspace: <workspace>/game-screens/. The tile organiser (Advanced mode)
can draw one behind the grid so the grid can be lined up with the real screen. These pictures show real club and player names: they are NEVER written into a project, a skin, an export,
the installer or the repository (the folder is inside the user's workspace, which is not in the repo), and Simple mode never reads them (the S5 rule: no screenshot of the game in Simple mode)."""
import re
import shutil
from pathlib import Path

NAME_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9 ._()-]{0,100}\.png")
MAX_BYTES = 30 * 1024 * 1024
PNG = b"\x89PNG\r\n\x1a\n"


def folder(ws):
    d = Path(ws.root) / "game-screens"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _png_size(f):
    """(width, height) from the PNG header, or None."""
    with open(f, "rb") as fh:
        h = fh.read(24)
    if len(h) < 24 or h[:8] != PNG:
        return None
    return int.from_bytes(h[16:20], "big"), int.from_bytes(h[20:24], "big")


def list_screens(ws):
    out = []
    for f in sorted(folder(ws).glob("*.png"), key=lambda p: p.name.lower()):
        if not NAME_RE.fullmatch(f.name):
            continue
        sz = _png_size(f)
        if sz:
            out.append({"name": f.name, "bytes": f.stat().st_size, "width": sz[0], "height": sz[1], "modified": f.stat().st_mtime})
    return out


def _path(ws, name):
    if not NAME_RE.fullmatch(name or ""):
        raise ValueError("bad screenshot name: letters, digits, spaces, dots, dashes, underscores and brackets, ending in .png")
    f = (folder(ws) / name).resolve()
    if f.parent != folder(ws).resolve():
        raise ValueError("bad screenshot name")
    return f


def read(ws, name):
    f = _path(ws, name)
    if not f.is_file():
        raise FileNotFoundError("no screenshot named %s" % name)
    return f.read_bytes()


def add(ws, source, name=None, replace=False):
    """Copy a PNG file in. -> the entry. A file that is not a PNG, is over 30 MB, or whose name is taken (unless `replace`) is refused."""
    src = Path(source)
    if not src.is_file():
        raise ValueError("pick a PNG screenshot")
    if src.stat().st_size > MAX_BYTES:
        raise ValueError("a screenshot is at most 30 MB")
    if _png_size(src) is None:
        raise ValueError("pick a PNG screenshot")
    dest = _path(ws, name or re.sub(r"[^A-Za-z0-9 ._()-]+", "-", src.name) or "screenshot.png")
    if dest.exists() and not replace:
        raise ValueError("a screenshot with that name is already there")
    tmp = dest.with_name(dest.name + ".part")
    shutil.copyfile(src, tmp)
    tmp.replace(dest)
    sz = _png_size(dest)
    return {"name": dest.name, "bytes": dest.stat().st_size, "width": sz[0], "height": sz[1], "modified": dest.stat().st_mtime}


def remove(ws, name):
    f = _path(ws, name)
    if not f.is_file():
        raise FileNotFoundError("no screenshot named %s" % name)
    f.unlink()
    return {"removed": name}
