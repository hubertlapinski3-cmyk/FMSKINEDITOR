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


def installed_hashes(ws):
    """{file: {sha256 this app ever wrote into the game folder}}: every `after` of the install log, not only the latest."""
    out = {}
    f = ws.logs / "install-log.jsonl"
    if f.is_file():
        for line in f.read_text(encoding="utf-8").splitlines():
            try:
                e = json.loads(line)
                out.setdefault(e["file"], set()).add(e["after"])
            except (ValueError, KeyError):
                pass
    return out


def skinned_bundles(ws, aa_dir):
    """Live bundles that are, by hash, a file this app installed and not that file's stock hash (the snapshot's own copy or its reference). A snapshot taken while any of these is in the game
    folder would record a skin as the game's own, so `snapshot_vanilla` refuses."""
    man = ws.vanilla_manifest() or {}
    stock = {n: {v.get("sha256")} for n, v in (man.get("files") or {}).items()}
    for n, h in ((man.get("reference") or {}).get("bundles") or {}).items():
        stock.setdefault(n, set()).add(h)
    out = []
    for name, hashes in sorted(installed_hashes(ws).items()):
        f = Path(aa_dir) / name
        if f.is_file():
            h = _live_sha(f)
            if h in hashes and h not in stock.get(name, set()):
                out.append(name)
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


UPDATED_MESSAGE = ("The game's catalog.hash changed since the snapshot (%s, was %s): the game was updated, so the snapshot, the style index and every backup made before the update "
                   "describe an older game build. Nothing that copies game files will run until there is a new snapshot. Steam overwrites only the files an update changed, so a skin you "
                   "installed can still be inside the files it left alone, and a snapshot of those would record them as the game's own. So, with Football Manager closed: FIRST run Steam's "
                   "Verify integrity of game files (Steam, right-click Football Manager 27, Properties, Installed files) and let it finish; THEN use the Re-read the game button on the "
                   "Studio's Game updates screen (the command-line equivalent, for a Studio that will not start: "
                   "& \"$env:LOCALAPPDATA\\FM Skin Studio\\fm-skin-engine\\fm-skin-engine.exe\" snapshot --force   and then the same line with   index   in place of   snapshot --force; "
                   "from a source checkout:   python -m skin_editor snapshot --force   and   python -m skin_editor index  ). "
                   "The re-read refuses while a game file is still one this app installed. Verify alone does not read the game again for the Studio.")

def refuse_if_updated(ws, aa_dir, what):
    """SAFETY: a write of game files from a snapshot or a backup is refused when the game's catalog is not the one the snapshot was taken against. `force` never overrides this: the files would be of two builds."""
    t = tamper_status(ws, aa_dir)
    if t["state"] == "game_updated":
        if "restore" in str(what).lower():
            raise InstallError(
                "%s was not done. Restore stock refuses old-build backups because putting an older build's bundles "
                "over an updated game mixes two builds and breaks FM27. Run Steam's Verify integrity of game files "
                "first, then click Reread now. %s" % (what, t["message"])
            )
        raise InstallError("%s was not done. %s" % (what, t["message"]))


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
                "message": UPDATED_MESSAGE % ((live_cat or "missing")[:12], ref["catalog_hash"][:12])}
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
    bad = skinned_bundles(ws, aa_dir)                       # never overridden by force: it would record a skin as the game's own
    if bad:
        raise InstallError("not snapshotted: %s %s still a file this app installed (a skin). Run Steam's Verify integrity of game files first (Steam, right-click Football Manager 27, Properties, Installed files), let it finish, then take the snapshot again." % (", ".join(bad[:4]), "is" if len(bad) == 1 else "are"))
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


def reread_after_update(ws, aa_dir, game_build=None, progress=None):
    """The guided 'the game was updated' recovery, in ONE call: the same two steps the PowerShell advice named
    (snapshot --force, then index), from inside the app. REFUSES while a live bundle is still a file this app
    installed - the owner must run Steam's Verify integrity first, or the snapshot would record a skin as the
    game's own (the same precondition as snapshot_vanilla, and it is never overridden). Nothing here writes the
    game folder: a snapshot is a read of it. Returns what the new notes hold."""
    progress = progress or (lambda m, f: None)
    bad = skinned_bundles(ws, aa_dir)                       # never overridden by force: it would record a skin as the game's own
    if bad:
        raise InstallError("not re-read: %s %s still a file this app installed (a skin). Run Steam's Verify integrity of game files first (Steam, right-click Football Manager 27 > Properties > Installed files), let it finish, then use the Re-read the game button again." % (", ".join(bad[:4]), "is" if len(bad) == 1 else "are"))
    progress("reading the game's files", 0.1)
    man = snapshot_vanilla(ws, aa_dir, game_build, force=True)
    progress("reading the game's colours and rules", 0.5)
    from . import index_styles
    ix = index_styles.build(ws, lambda m, f: progress(m, 0.5 + f / 2))
    return {"snapshot": {"taken_utc": man["taken_utc"], "game_build": man.get("game_build"),
                          "catalog_hash": (man.get("reference") or {}).get("catalog_hash")},
            "index": {"sheets": len(ix.sheets), "tokens": len(ix.defs), "literals": len(ix.literals)},
            "quarantined": len(ix.failures)}


def same_dir(a, b):
    return bool(a) and bool(b) and os.path.normcase(os.path.abspath(str(a))) == os.path.normcase(os.path.abspath(str(b)))


def snapshot_mismatch(ws, aa_dir):
    """A message when the vanilla snapshot was taken from another folder than the game folder in use, else None."""
    man = ws.vanilla_manifest()
    if man and man.get("source") and not same_dir(man["source"], aa_dir):
        return ("the vanilla snapshot was taken from %s, but the game folder in use is %s. Builds made from that snapshot do not "
                "match this game: take a new vanilla snapshot here (stock files) and rebuild." % (man["source"], aa_dir))
    return None


def stock_hashes(ws):
    """{bundle_name: stock_sha256} from the vanilla snapshot's reference hashes and copied style/image files."""
    man = ws.vanilla_manifest() or {}
    out = dict(((man.get("reference") or {}).get("bundles") or {}))
    for sec in ("files", "image_files"):
        for n, v in (man.get(sec) or {}).items():
            if isinstance(v, dict) and v.get("sha256") and n not in out:
                out[n] = v["sha256"]
    return out


def find_verified_stock_backups(ws, names=None, stock_overrides=None):
    """Locate a verified stock backup in the workspace (vanilla/ or backups/) for each requested bundle name
    (or every bundle in stock_hashes(ws) when names is None). Returns ({name: Path}, [missing_names])."""
    stock = dict(stock_hashes(ws))
    if stock_overrides:
        for k, v in stock_overrides.items():
            if v and k not in stock:
                stock[k] = v
    want = list(names) if names is not None else sorted(stock)
    candidates = []
    if ws.vanilla.is_dir():
        candidates.append(ws.vanilla)
    if ws.backups.is_dir():
        for p in sorted(ws.backups.iterdir(), reverse=True):
            if not p.is_dir():
                continue
            if (p / "manifest.json").is_file() or any(p.glob("*.bundle")):
                candidates.append(p)
            for sub in sorted(p.iterdir(), reverse=True):
                if sub.is_dir() and (sub / "files").is_dir():
                    candidates.append(sub / "files")
    found, missing = {}, []
    for name in want:
        expected = stock.get(name)
        if not expected:
            missing.append(name)
            continue
        match = None
        for d in candidates:
            cand = d / name
            if cand.is_file() and _live_sha(cand) == expected:
                match = cand
                break
        if match is not None:
            found[name] = match
        else:
            missing.append(name)
    return found, missing


def ensure_verified_stock_backups(ws, aa_dir, names, stock_overrides=None):
    """Ensure every bundle in `names` has a verified stock backup in the workspace before install replaces it.
    If a bundle has no verified stock backup yet and the live file in `aa_dir` equals the stock hash record,
    copy and verify it into `ws.vanilla` first. Raises InstallError listing any bundle that neither has a
    verified stock backup nor is currently stock on disk."""
    stock = dict(stock_hashes(ws))
    if stock_overrides:
        for k, v in stock_overrides.items():
            if v and k not in stock:
                stock[k] = v
    found, missing = find_verified_stock_backups(ws, names, stock_overrides=stock)
    if not missing:
        return found
    still_missing = []
    man = ws.vanilla_manifest()
    man_dirty = False
    for name in missing:
        expected = stock.get(name)
        live = Path(aa_dir) / name
        if expected and live.is_file() and sha256(live) == expected and ws.vanilla.is_dir():
            dst = ws.vanilla / name
            if dst.exists():
                dst.chmod(0o644)
            shutil.copyfile(live, dst)
            dst.chmod(0o444)
            if sha256(dst) != expected:
                still_missing.append(name)
                continue
            _HASH_CACHE.pop((str(dst), dst.stat().st_size, dst.stat().st_mtime_ns), None)
            found[name] = dst
            if isinstance(man, dict) and name not in STYLE_BUNDLES:
                man.setdefault("image_files", {})[name] = {"sha256": expected, "size": dst.stat().st_size}
                man_dirty = True
        else:
            still_missing.append(name)
    if man_dirty and isinstance(man, dict):
        (ws.vanilla / "manifest.json").write_text(json.dumps(man, indent=1), encoding="utf-8")
    if still_missing:
        raise InstallError("refused to install: no verified stock backup exists for %s (and the live file is not stock); "
                           "restore stock first before installing" % ", ".join(still_missing))
    return found


def project_last_changed_ts(ws, project_name):
    """Latest modification timestamp (POSIX seconds) across a project's authored files, or None if not found."""
    if not project_name:
        return None
    latest = None
    projects_dir = getattr(ws, "projects", None)
    if projects_dir:
        proj_dir = Path(projects_dir) / project_name
        if proj_dir.is_dir():
            for p in proj_dir.rglob("*"):
                if not p.is_file():
                    continue
                try:
                    rel = p.relative_to(proj_dir)
                except ValueError:
                    continue
                if rel.parts and rel.parts[0] == "packages":
                    continue                                    # written by builds, not project edits
                mt = p.stat().st_mtime
                if latest is None or mt > latest:
                    latest = mt
        single_proj = Path(projects_dir) / ("%s.skin.json" % project_name)
        if single_proj.is_file():
            mt = single_proj.stat().st_mtime
            if latest is None or mt > latest:
                latest = mt
    placements_dir = getattr(ws, "placements", None)
    if placements_dir:
        single_pl = Path(placements_dir) / ("%s.placements.json" % project_name)
        if single_pl.is_file():
            mt = single_pl.stat().st_mtime
            if latest is None or mt > latest:
                latest = mt
    return latest


def package_built_ts(build_dir, meta=None):
    """Build timestamp (POSIX seconds) from built_utc or build-report.json/package.json mtime."""
    import calendar
    built_utc = (meta or {}).get("built_utc")
    if isinstance(built_utc, str) and built_utc:
        try:
            return float(calendar.timegm(time.strptime(built_utc, "%Y%m%dT%H%M%SZ")))
        except ValueError:
            pass
    for name in ("build-report.json", "package.json"):
        p = Path(build_dir) / name
        if p.is_file():
            return p.stat().st_mtime
    return None


def stale_package_info(ws, project_name, build_dir, meta=None, grace_seconds=2.0):
    """Return a dict describing the age mismatch when the build package is older than the project's last change, else None."""
    proj_ts = project_last_changed_ts(ws, project_name)
    built_ts = package_built_ts(build_dir, meta)
    if proj_ts is None or built_ts is None:
        return None
    if proj_ts > built_ts + grace_seconds:
        return {
            "project": project_name,
            "package_built_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(built_ts)),
            "project_changed_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(proj_ts)),
            "age_seconds": round(proj_ts - built_ts, 1),
        }
    return None


def install(ws, aa_dir, build_dir, running, force=False, backup_keep=20, confirm_stale=False):
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
    stale = stale_package_info(ws, report.get("project"), build_dir, report)
    if stale and not confirm_stale and not force:
        raise InstallError("this build package (%s) is older than the project's last change (%s); rebuild first or confirm stale_package"
                           % (stale["package_built_utc"], stale["project_changed_utc"]))
    refuse_if_updated(ws, aa_dir, "The install")               # even with force: a changed catalog means another game build
    tamper = tamper_status(ws, aa_dir)
    if tamper["state"] == "modified" and not force:
        raise InstallError("tamper check: " + tamper["message"])
    last = last_installed(ws)
    stock = stock_hashes(ws)
    report_stock = {name: f.get("vanilla_sha256") for name, f in report["files"].items() if f.get("vanilla_sha256")}
    changed_names = [name for name, f in sorted(report["files"].items()) if f.get("changed")]
    for name, f in sorted(report["files"].items()):
        live = Path(aa_dir) / name
        if not live.is_file():
            raise InstallError("missing in the game folder: " + name)
        h = sha256(live)
        expected_stock = stock.get(name) or f.get("vanilla_sha256")
        if h not in (f["vanilla_sha256"], expected_stock, last.get(name), f["sha256"]) and not force:
            raise InstallError("%s differs from the vanilla snapshot and from the last install; the game was "
                               "probably updated. Take a new vanilla snapshot, re-index and rebuild." % name)
    verified_backups = ensure_verified_stock_backups(ws, aa_dir, changed_names, stock_overrides=report_stock)
    unchanged_backups, _ = find_verified_stock_backups(ws, [n for n, f in sorted(report["files"].items()) if not f.get("changed")], stock_overrides=report_stock)
    targets = {}
    for name, f in report["files"].items():
        if f.get("changed"):
            targets[name] = build_dir / name
        elif name in unchanged_backups:
            targets[name] = unchanged_backups[name]
        elif (ws.vanilla / name).is_file():
            targets[name] = ws.vanilla / name
    res = _write_set(ws, aa_dir, targets, report["project"], backup_keep)
    res["verified_stock_backups"] = {k: str(v) for k, v in sorted(verified_backups.items())}
    return res


def restore(ws, aa_dir, backup, running, backup_keep=20):
    """backup: a folder name under backups/, or 'vanilla' for the stock snapshot."""
    if running():
        raise InstallError("the game is running or updating; close it first")
    src = ws.vanilla if backup == "vanilla" else ws.backups / Path(backup).name
    refuse_if_updated(ws, aa_dir, "The restore")               # a snapshot or backup of the old build over the new one would mix two builds
    if backup == "vanilla":
        mm = snapshot_mismatch(ws, aa_dir)
        if mm:
            raise InstallError("not restored: " + mm)
        stock = stock_hashes(ws)
        files = {p.name: p for p in src.glob("*.bundle") if p.name not in stock or sha256(p) == stock[p.name]}
        non_stock = []
        for name, want in sorted(stock.items()):
            live = Path(aa_dir) / name
            if live.is_file() and sha256(live) != want:
                non_stock.append(name)
        need_from_backups = [n for n in non_stock if n not in files]
        if need_from_backups:
            found, missing = find_verified_stock_backups(ws, need_from_backups)
            if missing:
                raise InstallError("not restored: no verified stock backup matching the stock hash record for: "
                                   + ", ".join(missing))
            files.update(found)
        for name, cand in sorted(files.items()):
            if name in stock and sha256(cand) != stock[name]:
                raise InstallError("not restored: backup for %s does not match the stock hash record" % name)
    else:
        m = src / "manifest.json"
        meta = json.loads(m.read_text(encoding="utf-8")) if m.is_file() else {}
        origin = meta.get("game_dir")
        if origin and not same_dir(origin, aa_dir):
            raise InstallError("not restored: backup %s holds files from %s, not from the game folder in use (%s)" % (src.name, origin, aa_dir))
        for e in meta.get("files", []):                        # the live file must still be one this backup was made from or installed over
            live = Path(aa_dir) / e["file"]
            if live.is_file() and sha256(live) not in (e.get("sha256_before"), e.get("sha256_new")):
                raise InstallError("not restored: %s in the game folder is neither the file this backup was taken from nor the one it installed, so the game changed after the backup "
                                   "(a game update). Restoring would mix two game builds. Take a new vanilla snapshot instead." % e["file"])
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
