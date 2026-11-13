"""Vanilla snapshot, install, backup, restore. The only module that writes the game dir. LEARNINGS 9.1."""
import json
import os
import shutil
import time
from pathlib import Path

from .bundles import STYLE_BUNDLES, sha256


class InstallError(RuntimeError):
    pass


def _now():
    return time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())


def _log(ws, **entry):
    with open(ws.logs / "install-log.jsonl", "a", encoding="utf-8") as f:
        f.write(json.dumps(dict(time=_now(), **entry)) + "\n")


def last_installed(ws):
    """{file: sha256 the last install or restore left in the game dir}."""
    out = {}
    f = ws.logs / "install-log.jsonl"
    if f.is_file():
        for line in f.read_text(encoding="utf-8").splitlines():
            try:
                e = json.loads(line)
                out[e["file"]] = e["after"]
            except (ValueError, KeyError):
                pass
    return out


def live_status(ws, aa_dir):
    man = ws.vanilla_manifest() or {"files": {}}
    last = last_installed(ws)
    out = {}
    for name in STYLE_BUNDLES:
        f = Path(aa_dir) / name
        if not f.is_file():
            out[name] = {"state": "missing"}
            continue
        h = sha256(f)
        van = man["files"].get(name, {}).get("sha256")
        state = "no_snapshot" if not van else "vanilla" if h == van else "skinned" if h == last.get(name) else "changed"
        out[name] = {"state": state, "sha256": h}
    return out


def reference_hashes(aa_dir):
    """Hashes only, no copies: what a layout dump's meta.source is compared with. catalog.hash is read from the platform
    folder or its parent (Windows keeps it one level up); the bundles are every ui-*.bundle in the platform folder."""
    aa_dir = Path(aa_dir)
    cat = next((p for p in (aa_dir / "catalog.hash", aa_dir.parent / "catalog.hash") if p.is_file()), None)
    return {"recorded_utc": _now(), "platform_folder": aa_dir.name,
            "catalog_hash": cat.read_text(encoding="utf-8", errors="replace").strip() if cat else None,
            "bundles": {p.name: sha256(p) for p in sorted(aa_dir.glob("ui-*.bundle"))}}


def record_reference_hashes(ws, aa_dir, force=False):
    """One-time action for a snapshot taken before reference hashes existed. Same precondition as the snapshot: stock files.
    Refused when the style bundles in the game folder are not the ones in the snapshot (skinned, changed or updated)."""
    man = ws.vanilla_manifest()
    if not man:
        raise InstallError("no vanilla snapshot yet; take one first (it records the reference hashes itself)")
    if man.get("reference") and not force:
        raise InstallError("reference hashes already recorded; pass force to replace them")
    for name in STYLE_BUNDLES:
        f = Path(aa_dir) / name
        if not f.is_file() or sha256(f) != man["files"].get(name, {}).get("sha256"):
            raise InstallError("%s in the game folder is not the snapshot's stock file (skinned, modified or updated); "
                               "restore the stock files (or take a new snapshot) before recording reference hashes" % name)
    ref = reference_hashes(aa_dir)
    if not ref["catalog_hash"]:
        raise InstallError("catalog.hash was not found next to the platform folder; cannot record reference hashes")
    man["reference"] = ref
    (ws.vanilla / "manifest.json").write_text(json.dumps(man, indent=1), encoding="utf-8")
    return man


_HASH_CACHE = {}


def _live_sha(path):
    """sha256 cached by (size, mtime): the Setup tab asks often, and the files rarely change."""
    st = path.stat()
    key = (str(path), st.st_size, st.st_mtime_ns)
    if key not in _HASH_CACHE:
        _HASH_CACHE[key] = sha256(path)
    return _HASH_CACHE[key]


def tamper_status(ws, aa_dir):
    """Live ui-*.bundle files against the snapshot's reference hashes.
    state: no_reference (cannot check), game_updated (live catalog.hash differs: the reference no longer applies),
    clean, or modified. Per file: stock, skinned (a style bundle this app installed), modified, missing; files with no
    reference are listed as new."""
    man = ws.vanilla_manifest() or {}
    ref = man.get("reference")
    if not ref or not ref.get("catalog_hash"):
        return {"state": "no_reference", "message": "No reference hashes: the game files cannot be checked for tampering. "
                "Record reference hashes on the Setup tab (game closed, stock files)."}
    aa_dir = Path(aa_dir)
    cat = next((p for p in (aa_dir / "catalog.hash", aa_dir.parent / "catalog.hash") if p.is_file()), None)
    live_cat = cat.read_text(encoding="utf-8", errors="replace").strip() if cat else None
    if live_cat != ref["catalog_hash"]:
        return {"state": "game_updated", "catalog_live": live_cat, "catalog_reference": ref["catalog_hash"],
                "message": "The game's catalog.hash changed since the snapshot (%s, was %s): the game was updated or verified. "
                           "Take a new vanilla snapshot, re-index and rebuild." % ((live_cat or "missing")[:12], ref["catalog_hash"][:12])}
    last = last_installed(ws)
    files, bad = {}, []
    for name, want in sorted(ref["bundles"].items()):
        f = aa_dir / name
        if not f.is_file():
            files[name] = "missing"; bad.append(name)
            continue
        h = _live_sha(f)
        if h == want:
            files[name] = "stock"
        elif h == last.get(name):
            files[name] = "skinned"
        else:
            files[name] = "modified"; bad.append(name)
    new = sorted(p.name for p in aa_dir.glob("ui-*.bundle") if p.name not in ref["bundles"])
    msg = ("%d UI bundle%s differ from the reference and were not installed by this app: %s. Restore them (Steam: Verify integrity "
           "of game files, or the backup you made) before building, installing or exporting a layout dump."
           % (len(bad), "" if len(bad) == 1 else "s", ", ".join(bad[:6]))) if bad else ""
    return {"state": "modified" if bad else "clean", "files": files, "modified": bad, "new": new, "message": msg,
            "checked": len(ref["bundles"])}


def add_image_bundle(ws, aa_dir, name):
    """Copy one image bundle into the vanilla snapshot (read-only), hashes only when the live file is the stock one: the
    reference hash recorded at snapshot time. Idempotent."""
    from .images import BUNDLE_RE
    man = ws.vanilla_manifest()
    if not man:
        raise InstallError("take the vanilla snapshot first")
    if not BUNDLE_RE.fullmatch(name) or name in STYLE_BUNDLES:
        raise InstallError("not an image bundle: " + name)
    if name in man.get("image_files", {}) and (ws.vanilla / name).is_file():
        return man
    ref = (man.get("reference") or {}).get("bundles", {}).get(name)
    src = Path(aa_dir) / name
    if not ref:
        raise InstallError("no reference hash for %s: record reference hashes (game closed, stock files) first" % name)
    if not src.is_file() or sha256(src) != ref:
        raise InstallError("%s in the game folder is not the stock file (a skin or a test left it modified); restore it "
                           "(Steam: Verify integrity) before using images from it" % name)
    dst = ws.vanilla / name
    if dst.exists():
        dst.chmod(0o644)
    shutil.copyfile(src, dst)
    dst.chmod(0o444)
    if sha256(dst) != ref:
        raise InstallError("copy mismatch for " + name)
    man.setdefault("image_files", {})[name] = {"sha256": ref, "size": dst.stat().st_size}
    (ws.vanilla / "manifest.json").write_text(json.dumps(man, indent=1), encoding="utf-8")
    return man


def snapshot_vanilla(ws, aa_dir, game_build=None, force=False):
    """Copy the stock style bundles into the read-only vanilla dir. Only correct on an unskinned install."""
    if ws.vanilla_manifest() and not force:
        raise InstallError("vanilla snapshot exists; pass force to replace it")
    for old in ws.vanilla.glob("*.bundle"):                # image bundles of an older snapshot: never restore stale copies
        if old.name not in STYLE_BUNDLES:
            old.chmod(0o644)
            old.unlink()
    files = {}
    for name in STYLE_BUNDLES:
        src, dst = Path(aa_dir) / name, ws.vanilla / name
        if dst.exists():
            dst.chmod(0o644)
        shutil.copyfile(src, dst)
        dst.chmod(0o444)
        h = sha256(dst)
        if h != sha256(src):
            raise InstallError("copy mismatch for " + name)
        files[name] = {"sha256": h, "size": dst.stat().st_size}
    man = {"schema": 1, "taken_utc": _now(), "game_build": game_build, "source": str(aa_dir), "files": files,
           "reference": reference_hashes(aa_dir)}
    (ws.vanilla / "manifest.json").write_text(json.dumps(man, indent=1), encoding="utf-8")
    return man


def _copy(src, dst):
    tmp = dst.with_name("." + dst.name + ".fm27se.tmp")
    shutil.copyfile(src, tmp)
    os.replace(tmp, dst)


def _write_set(ws, aa_dir, targets, label, backup_keep):
    """targets {name: source path}. Backup, copy the ones that differ, verify, roll back on mismatch."""
    aa_dir = Path(aa_dir)
    todo = {}
    for name, src in targets.items():
        live = aa_dir / name
        before, want = sha256(live), sha256(src)
        if before != want:
            todo[name] = (src, before, want)
    if not todo:
        return {"copied": [], "backup": None}
    bdir = ws.backups / _now()
    n = 1
    while bdir.exists():
        bdir = ws.backups / ("%s-%d" % (_now(), n)); n += 1
    bdir.mkdir(parents=True)
    for name in todo:
        shutil.copyfile(aa_dir / name, bdir / name)
        if sha256(bdir / name) != todo[name][1]:
            raise InstallError("backup copy mismatch for %s; nothing was installed" % name)
    (bdir / "manifest.json").write_text(json.dumps({
        "label": label, "game_dir": str(aa_dir),
        "files": [{"file": k, "size": (bdir / k).stat().st_size, "sha256_before": v[1], "sha256_new": v[2]}
                  for k, v in todo.items()]}, indent=1), encoding="utf-8")
    (bdir / "RESTORE.txt").write_text(
        "Close the game, then copy every .bundle in this folder over the same name in:\n%s\n\ncp \"%s\"/*.bundle \"%s\"/\n"
        % (aa_dir, bdir, aa_dir), encoding="utf-8")
    try:
        for name, (src, _, want) in todo.items():
            _copy(src, aa_dir / name)
            if sha256(aa_dir / name) != want:
                raise InstallError("verify mismatch after copy: " + name)
    except Exception as e:
        for name in todo:
            try:
                _copy(bdir / name, aa_dir / name)
            except OSError:
                pass
        raise InstallError("install failed and the previous files were restored from %s: %s" % (bdir, e))
    for name, (_, before, want) in todo.items():
        _log(ws, project=label, file=name, before=before, after=want, backup=str(bdir))
    old = sorted(p for p in ws.backups.iterdir() if p.is_dir())
    for p in old[:-backup_keep] if backup_keep else []:
        shutil.rmtree(p, ignore_errors=True)
    return {"copied": sorted(todo), "backup": str(bdir)}


def same_dir(a, b):
    return bool(a) and bool(b) and os.path.normcase(os.path.abspath(str(a))) == os.path.normcase(os.path.abspath(str(b)))


def snapshot_mismatch(ws, aa_dir):
    """A message when the vanilla snapshot was taken from another folder than the game folder in use, else None."""
    man = ws.vanilla_manifest()
    if man and man.get("source") and not same_dir(man["source"], aa_dir):
        return ("the vanilla snapshot was taken from %s, but the game folder in use is %s. Builds made from that snapshot do not "
                "match this game: take a new vanilla snapshot here (stock files) and rebuild." % (man["source"], aa_dir))
    return None


def install(ws, aa_dir, build_dir, running, force=False, backup_keep=20):
    """running: callable -> bool (game process or Steam update detected)."""
    if running():
        raise InstallError("the game is running or updating; close it first")
    mm = snapshot_mismatch(ws, aa_dir)
    if mm:
        raise InstallError(mm)
    build_dir = Path(build_dir)
    report = json.loads((build_dir / "build-report.json").read_text(encoding="utf-8"))
    if report.get("gate", {}).get("fail"):
        raise InstallError("this build failed the structural gate and cannot be installed: " + report["gate"]["fail"][0])
    tamper = tamper_status(ws, aa_dir)
    if tamper["state"] in ("modified", "game_updated") and not force:
        raise InstallError("tamper check: " + tamper["message"])
    last = last_installed(ws)
    targets = {}
    for name, f in report["files"].items():
        live = Path(aa_dir) / name
        if not live.is_file():
            raise InstallError("missing in the game folder: " + name)
        h = sha256(live)
        if h not in (f["vanilla_sha256"], last.get(name), f["sha256"]) and not force:
            raise InstallError("%s differs from the vanilla snapshot and from the last install; the game was "
                               "probably updated. Take a new vanilla snapshot, re-index and rebuild." % name)
        targets[name] = build_dir / name if f["changed"] else ws.vanilla / name
    return _write_set(ws, aa_dir, targets, report["project"], backup_keep)


def restore(ws, aa_dir, backup, running, backup_keep=20):
    """backup: a folder name under backups/, or 'vanilla' for the stock snapshot."""
    if running():
        raise InstallError("the game is running or updating; close it first")
    src = ws.vanilla if backup == "vanilla" else ws.backups / Path(backup).name
    if backup == "vanilla":
        mm = snapshot_mismatch(ws, aa_dir)
        if mm:
            raise InstallError("not restored: " + mm)
    else:
        m = src / "manifest.json"
        origin = json.loads(m.read_text(encoding="utf-8")).get("game_dir") if m.is_file() else None
        if origin and not same_dir(origin, aa_dir):
            raise InstallError("not restored: backup %s holds files from %s, not from the game folder in use (%s)" % (src.name, origin, aa_dir))
    files = {p.name: p for p in src.glob("*.bundle")}
    if not files:
        raise InstallError("no bundles in " + str(src))
    return _write_set(ws, aa_dir, files, "restore:" + backup, backup_keep)


def list_backups(ws):
    out = []
    for p in sorted(ws.backups.iterdir(), reverse=True):
        m = p / "manifest.json"
        if m.is_file():
            d = json.loads(m.read_text(encoding="utf-8"))
            out.append({"name": p.name, "label": d.get("label"), "files": [f["file"] for f in d["files"]]})
    return out
