"""Where FM27 keeps its user folder (skins, views) and where Steam libraries live, per platform. Pure functions: every input that differs between
machines (home, platform, the Windows Documents folder, the Steam roots) is a parameter, so the Linux/Proton and macOS rules are testable on any OS.
Status of each rule is in docs/SKIN-BUILDER-SPEC.md Part 5 (macOS and Linux paths are [A]: from documentation, never run on those systems).

FM27's user folder is `Sports Interactive/Football Manager 27`:
- Windows: <Documents>/..., where Documents is the Known Folder (it follows a relocation or OneDrive redirect), not always `~/Documents`.
- macOS: ~/Library/Application Support/...
- Linux with Proton: the game is the Windows build, so the folder sits inside the Steam compat prefix of its app id:
  <steam>/steamapps/compatdata/<appid>/pfx/drive_c/users/steamuser/Documents/...
- Linux native build (if SI ships one): ~/.config/unity3d-style paths are not known; ~/Documents is tried last."""
import re
import sys
from pathlib import Path

FM27_APPID = "4530370"                       # Steam app id, read from the manifest when one is found
SUBDIR = Path("Sports Interactive") / "Football Manager 27"
NAME_RE = re.compile(r"^(football ?manager ?(20)?27|fm ?27)", re.I)


def windows_documents(env=None):
    """The Documents Known Folder on Windows (None elsewhere or when it cannot be asked)."""
    if sys.platform != "win32":
        return None
    try:
        import ctypes
        from ctypes import wintypes
        buf = ctypes.create_unicode_buffer(wintypes.MAX_PATH)
        # CSIDL_PERSONAL (5) with SHGFP_TYPE_CURRENT (0): the current, possibly redirected, Documents folder
        if ctypes.windll.shell32.SHGetFolderPathW(None, 5, None, 0, buf) == 0 and buf.value:
            return Path(buf.value)
    except Exception:
        pass
    return None


def steam_roots(home, platform=None):
    """Steam install roots (the folder that holds `steamapps`), most likely first, existing or not."""
    platform = platform or sys.platform
    home = Path(home)
    if platform == "darwin":
        return [home / "Library" / "Application Support" / "Steam"]
    if platform == "win32":
        return []                            # Windows uses the Program Files path in detect.py
    return [home / ".steam" / "steam", home / ".local" / "share" / "Steam",
            home / ".var" / "app" / "com.valvesoftware.Steam" / ".local" / "share" / "Steam",
            home / "snap" / "steam" / "common" / ".local" / "share" / "Steam"]


def fm27_appids(steamapps):
    """App ids of Football Manager 27 manifests in one steamapps folder (falls back to the known id)."""
    ids = []
    try:
        manifests = sorted(Path(steamapps).glob("appmanifest_*.acf"))
    except OSError:
        manifests = []
    for acf in manifests:
        try:
            txt = acf.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        name = re.search(r'"installdir"\s+"([^"]+)"', txt)
        aid = re.search(r'"appid"\s+"(\d+)"', txt)
        if name and aid and NAME_RE.match(name.group(1)):
            ids.append(aid.group(1))
    return ids or [FM27_APPID]


def proton_user_folders(home, platform=None, roots=None):
    """FM27 user folders inside Proton prefixes (Linux): one per steamapps folder that has a compat prefix for the game."""
    out = []
    for root in (roots if roots is not None else steam_roots(home, platform or "linux")):
        steamapps = Path(root) / "steamapps"
        for aid in fm27_appids(steamapps):
            docs = steamapps / "compatdata" / aid / "pfx" / "drive_c" / "users" / "steamuser" / "Documents"
            out.append(docs / SUBDIR)
    return out


def user_folder_candidates(home=None, platform=None, documents=None, roots=None):
    """Candidate FM27 user folders in the order to try them."""
    home = Path(home) if home else Path.home()
    platform = platform or sys.platform
    if platform == "darwin":
        return [home / "Library" / "Application Support" / SUBDIR]
    if platform == "win32":
        docs = [documents] if documents else [windows_documents()]
        cands = [Path(d) / SUBDIR for d in docs if d]
        cands += [home / "Documents" / SUBDIR, home / "OneDrive" / "Documents" / SUBDIR]
        return cands
    return proton_user_folders(home, platform, roots) + [home / "Documents" / SUBDIR]


def user_folder(home=None, platform=None, documents=None, roots=None):
    """The first candidate that exists, or None."""
    seen = set()
    for c in user_folder_candidates(home, platform, documents, roots):
        if c in seen:
            continue
        seen.add(c)
        if c.is_dir():
            return c
    return None
