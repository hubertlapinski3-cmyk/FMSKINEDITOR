"""Install detection and running-process check. LEARNINGS sections 2.2 and 2.4 (all unverified on macOS)."""
import os
import plistlib
import re
import subprocess
import sys
from pathlib import Path

from . import userdirs
from .bundles import STYLE_BUNDLES

NAME_RE = re.compile(r"^(football ?manager ?(20)?27|fm ?27)", re.I)


def library_roots():
    home = Path.home()
    roots = []
    if sys.platform == "darwin":
        steam = home / "Library" / "Application Support" / "Steam" / "steamapps"
        roots += [steam / "common", Path("/Users/Shared/Epic Games"), home / "Applications", Path("/Applications")]
    elif sys.platform == "win32":
        steam = Path(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")) / "Steam" / "steamapps"
        roots += [steam / "common", Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "Epic Games"]
    else:
        # Linux: the usual Steam locations (classic, XDG, Flatpak, Snap); the Windows build runs under Proton, so the same folder rules apply
        steams = [r / "steamapps" for r in userdirs.steam_roots(home, "linux")]
        steam = steams[0]
        for s in steams:
            roots.append(s / "common")
    vdfs = [steam / "libraryfolders.vdf"] + ([s / "libraryfolders.vdf" for s in steams[1:]] if sys.platform not in ("darwin", "win32") else [])
    for vdf in vdfs:
        if vdf.is_file():
            for m in re.finditer(r'"path"\s+"([^"]+)"', vdf.read_text(encoding="utf-8", errors="replace")):
                roots.append(Path(m.group(1).replace("\\\\", "\\")) / "steamapps" / "common")
    seen, out = set(), []
    for r in roots:
        if r not in seen and r.is_dir():
            seen.add(r)
            out.append(r)
    return out


def _aa_in(streaming):
    aa = Path(streaming) / "aa"
    if not aa.is_dir():
        return None
    for child in sorted(aa.iterdir()):
        if child.is_dir() and not child.is_symlink() and child.name.startswith("Standalone") \
                and all((child / b).is_file() for b in STYLE_BUNDLES):
            return child
    return None


def find_aa_all(game_dir):
    """Every StreamingAssets/aa/<Standalone*> with the style bundles under a game dir (no symlinks, depth-limited).
    Copies of the game's files (a skin's restore folder, a backup) also match, so the caller must pick the real one."""
    game_dir = Path(game_dir).expanduser()
    out = []
    for base, dirs, _ in os.walk(game_dir, followlinks=False):
        dirs.sort()
        if Path(base).name == "StreamingAssets" and "aa" in dirs:
            hit = _aa_in(base)
            if hit:
                out.append(hit)
            dirs[:] = []
        elif len(Path(base).relative_to(game_dir).parts) >= 8:
            dirs[:] = []
    return out


def find_aa(game_dir):
    """The game's own StreamingAssets/aa/<Standalone*>: the data folder that belongs to the game executable.
    Windows/Linux: <game dir>/<Name>_Data next to <Name>.exe (or <Name>); macOS: <X>.app/Contents/Resources/Data.
    Only when neither exists, the shallowest match (a skin's restore copy or a backup inside the game folder sits deeper
    and is never preferred; on 2026-11-12 'FM Blog Classic Skin 112 Restore/original/game/fm_Data' won by sort order)."""
    game_dir = Path(game_dir).expanduser()
    if game_dir.suffix == ".app":
        hit = _aa_in(game_dir / "Contents" / "Resources" / "Data" / "StreamingAssets")
        if hit:
            return hit
    try:
        children = sorted(game_dir.iterdir())
    except OSError:
        children = []
    for d in children:
        if d.is_dir() and not d.is_symlink() and d.name.endswith("_Data"):
            stem = d.name[:-len("_Data")]
            if (game_dir / (stem + ".exe")).is_file() or (game_dir / stem).is_file():
                hit = _aa_in(d / "StreamingAssets")
                if hit:
                    return hit
    for d in children:
        if d.suffix == ".app" and d.is_dir() and not d.is_symlink():
            hit = _aa_in(d / "Contents" / "Resources" / "Data" / "StreamingAssets")
            if hit:
                return hit
    found = find_aa_all(game_dir)
    return min(found, key=lambda p: (len(p.relative_to(game_dir).parts), str(p))) if found else None


def describe(game_dir):
    """Install record for a game dir (install root or .app), or None when no style bundles are found."""
    game_dir = Path(game_dir).expanduser()
    aa = find_aa(game_dir)
    if not aa:
        return None
    others = [str(p) for p in find_aa_all(game_dir) if p != aa]
    info = {"game_dir": str(game_dir), "aa_dir": str(aa), "platform_folder": aa.name, "app": None, "other_copies": others,
            "executable": None, "version": None,
            "store": "steam" if "steamapps" in game_dir.parts else "epic" if "Epic Games" in game_dir.parts else "unknown"}
    app = next((p for p in [aa, *aa.parents] if p.suffix == ".app"), None)
    if app:
        info["app"] = str(app)
        try:
            with open(app / "Contents" / "Info.plist", "rb") as f:
                pl = plistlib.load(f)
            info["executable"] = pl.get("CFBundleExecutable")
            info["version"] = pl.get("CFBundleShortVersionString") or pl.get("CFBundleVersion")
        except Exception:
            pass
    return info


def find_installs():
    out = []
    for root in library_roots():
        try:
            entries = sorted(root.iterdir())
        except OSError:
            continue
        for d in entries:
            if d.is_dir() and not d.is_symlink() and NAME_RE.match(d.name):
                info = describe(d)
                if info:
                    out.append(info)
    return out


def _run(cmd):
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=10)
    except (OSError, subprocess.TimeoutExpired):
        return None


def game_running(info, process_names=()):
    """True when the game process is detected. On check failure returns True (refuse rather than risk)."""
    names = [n for n in dict.fromkeys([info.get("executable"), *process_names]) if n]
    if sys.platform == "win32":
        r = _run(["tasklist", "/FO", "CSV", "/NH"])
        if r is None or r.returncode != 0:
            return True
        running = {line.split('","')[0].strip('"').lower() for line in r.stdout.splitlines()}
        return any(n.lower() + ".exe" in running for n in names)
    checks = [["pgrep", "-x", n] for n in names]
    if info.get("app"):
        checks.append(["pgrep", "-f", info["app"] + "/Contents/MacOS"])
    for cmd in checks:
        r = _run(cmd)
        if r is None or r.returncode not in (0, 1):
            return True
        if r.returncode == 0:
            return True
    return False


def steam_updating(info):
    """True when the Steam app manifest for this install has StateFlags other than 4."""
    p = Path(info["game_dir"])
    if "steamapps" not in p.parts:
        return False
    steamapps = Path(*p.parts[:p.parts.index("steamapps") + 1])
    folder = p.parts[p.parts.index("steamapps") + 2] if len(p.parts) > p.parts.index("steamapps") + 2 else None
    for acf in steamapps.glob("appmanifest_*.acf"):
        txt = acf.read_text(encoding="utf-8", errors="replace")
        m = re.search(r'"installdir"\s+"([^"]+)"', txt)
        if m and m.group(1) == folder:
            s = re.search(r'"StateFlags"\s+"(\d+)"', txt)
            return bool(s) and s.group(1) != "4"
    return False
