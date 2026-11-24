"""Game installation profile (Stage 4B; docs/rea/STAGE-4A-ARCHITECTURE.md section 6.1). READ ONLY: nothing here writes to a game folder.

A profile records what identifies one game installation: where it is, which build, which catalog, which integrity files. It is built from a folder the
user selected or `detect` found, never from a hardcoded path. Profiles are stored in `<workspace>/state/installs.json`, keyed by `install_id`.

Roles (the same code path serves all of them; the role is a label the user sets and the installer later checks):
  installed    the game as installed for play            copy        a copied or extracted installation
  test         a user-selected test installation         production  an installation the user designates as the install target
`install_id` is a short hash of (normalised folder path, catalog.bin sha256, executable size). It changes when the game is updated or moved, which is the
point: an inventory and a build belong to exactly one identity."""
import hashlib
import json
import os
import time
from pathlib import Path

from . import bundles, detect

ROLES = ("installed", "copy", "test", "production")
SCHEMA = 1
FILE = "installs.json"


class ProfileError(ValueError):
    pass


def _now():
    return time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())


def _sha(p):
    return bundles.sha256(p) if p and Path(p).is_file() else None


def _first(*paths):
    return next((Path(p) for p in paths if p and Path(p).is_file()), None)


def _kv(path):
    """key=value lines (boot.config) as a dict; an unreadable file gives {}."""
    out = {}
    try:
        for line in Path(path).read_text(encoding="utf-8", errors="replace").splitlines():
            if "=" in line:
                k, v = line.split("=", 1)
                out[k.strip()] = v.strip()
    except OSError:
        pass
    return out


def _steam_build_id(game_dir):
    """Steam's build id and app id from the library's appmanifest whose installdir is this folder, or (None, None). Read only."""
    game_dir = Path(game_dir)
    if game_dir.parent.name != "common" or game_dir.parent.parent.name != "steamapps":
        return None, None
    for acf in sorted(game_dir.parent.parent.glob("appmanifest_*.acf")):
        try:
            text = acf.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        kv = {}
        for line in text.splitlines():
            parts = [x for x in line.replace("\t", " ").split('"') if x.strip()]
            if len(parts) == 2:
                kv.setdefault(parts[0], parts[1])
        if kv.get("installdir") == game_dir.name:
            return kv.get("buildid"), kv.get("appid")
    return None, None


def compute_id(game_dir, catalog_sha, exe_size):
    key = "%s|%s|%s" % (os.path.normcase(os.path.abspath(str(game_dir))), catalog_sha or "-", exe_size if exe_size is not None else "-")
    return hashlib.sha256(key.encode("utf-8")).hexdigest()[:16]


def describe_install(game_dir, role="installed", game_build=None):
    """Profile of the installation in `game_dir` (the install root). Raises ProfileError when it is not a game folder. No file is written."""
    if role not in ROLES:
        raise ProfileError("role must be one of: " + ", ".join(ROLES))
    info = detect.describe(game_dir)
    if not info:
        raise ProfileError("no StreamingAssets/aa/Standalone folder with the style bundles was found in %s" % game_dir)
    root, aa = Path(info["game_dir"]), Path(info["aa_dir"])
    streaming = aa.parent                       # <data>/StreamingAssets/aa : catalog.bin, catalog.hash, settings.json
    data_dir = streaming.parent.parent          # <data> (fm_Data): manifest.dat, boot.config
    exe = next((p for p in sorted(root.glob("*.exe")) if (root / (p.stem + "_Data")).is_dir()), None)
    catalog = _first(streaming / "catalog.bin", aa / "catalog.bin")
    chash = _first(streaming / "catalog.hash", aa / "catalog.hash")
    settings = _first(streaming / "settings.json", aa / "settings.json")
    manifest = _first(data_dir / "manifest.dat")
    boot = _kv(data_dir / "boot.config") if (data_dir / "boot.config").is_file() else {}
    addr_version, header = None, None
    if settings:
        try:
            addr_version = json.loads(settings.read_text(encoding="utf-8")).get("m_AddressablesVersion")
        except (OSError, ValueError):
            pass
    probe = next((p for p in sorted(aa.glob("*.bundle"))[:8]), None)
    if probe:
        header = bundles.bundle_header(probe)
    steam_build, steam_app = _steam_build_id(root)
    cat_sha = _sha(catalog)
    exe_size = exe.stat().st_size if exe else None
    return {
        "schema": SCHEMA, "install_id": compute_id(root, cat_sha, exe_size), "role": role,
        "game_dir": str(root), "aa_dir": str(aa), "platform_folder": aa.name, "store": info.get("store"),
        "executable": str(exe) if exe else None, "executable_size": exe_size,
        "game_build": game_build, "steam_build_id": steam_build, "steam_app_id": steam_app,
        "unity_version": (header or {}).get("unity_revision"), "unity_build_guid": boot.get("build-guid"),
        "addressables_version": addr_version,
        "catalog_path": str(catalog) if catalog else None, "catalog_sha256": cat_sha,
        "catalog_hash_path": str(chash) if chash else None, "catalog_hash_sha256": _sha(chash),
        "catalog_hash": chash.read_text(encoding="utf-8", errors="replace").strip() if chash else None,
        "settings_path": str(settings) if settings else None,
        "manifest_dat_path": str(manifest) if manifest else None, "manifest_dat_sha256": _sha(manifest),
        "aa_roots": [str(aa)], "other_copies": info.get("other_copies", []),
        "last_inventory_utc": None, "verification": {"state": "unverified", "checked_utc": None},
        "described_utc": _now()}


def validate(profile):
    """Problems that make the profile unusable for an inventory or a build: [{code, message}], empty when fine. Read only."""
    out = []
    aa = Path(profile.get("aa_dir") or "")
    if not aa.is_dir():
        out.append({"code": "aa_missing", "message": "the bundle folder %s does not exist" % aa})
    if not profile.get("catalog_path"):
        out.append({"code": "catalog_missing", "message": "catalog.bin was not found next to the platform folder"})
    if not profile.get("catalog_hash_path"):
        out.append({"code": "catalog_hash_missing", "message": "catalog.hash was not found"})
    if profile.get("role") not in ROLES:
        out.append({"code": "bad_role", "message": "unknown role %r" % profile.get("role")})
    return out


def drift(profile):
    """How the folder differs now from the stored profile: [] when identical. Used to refuse work on a game that changed (updated, moved, modified) after the profile was made."""
    try:
        now = describe_install(profile["game_dir"], profile.get("role", "installed"), profile.get("game_build"))
    except ProfileError as e:
        return [{"code": "gone", "message": str(e)}]
    out = []
    for k in ("catalog_sha256", "catalog_hash_sha256", "manifest_dat_sha256", "executable_size", "unity_version", "install_id"):
        if profile.get(k) != now.get(k):
            out.append({"code": k + "_changed", "message": "%s changed (%s -> %s)" % (k, profile.get(k), now.get(k))})
    return out


# ---- storage (the only writer; the workspace, never a game folder)
def _file(ws):
    return Path(ws.state) / FILE


def load_all(ws):
    f = _file(ws)
    if not f.is_file():
        return {"schema": SCHEMA, "active": None, "installs": {}}
    try:
        d = json.loads(f.read_text(encoding="utf-8"))
        d.setdefault("installs", {})
        d.setdefault("active", None)
        return d
    except ValueError:
        return {"schema": SCHEMA, "active": None, "installs": {}}


def save(ws, profile, make_active=True):
    d = load_all(ws)
    d["installs"][profile["install_id"]] = profile
    if make_active or not d["active"]:
        d["active"] = profile["install_id"]
    tmp = _file(ws).with_suffix(".tmp")
    tmp.write_text(json.dumps(d, indent=1), encoding="utf-8")
    os.replace(tmp, _file(ws))
    return profile


def get(ws, install_id=None):
    d = load_all(ws)
    iid = install_id or d["active"]
    if not iid or iid not in d["installs"]:
        raise KeyError("no such installation profile: %s" % (iid or "(none selected)"))
    return d["installs"][iid]


def touch_inventory(ws, install_id):
    d = load_all(ws)
    if install_id in d["installs"]:
        d["installs"][install_id]["last_inventory_utc"] = _now()
        tmp = _file(ws).with_suffix(".tmp")
        tmp.write_text(json.dumps(d, indent=1), encoding="utf-8")
        os.replace(tmp, _file(ws))
