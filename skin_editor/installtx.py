"""The installation transaction engine (Stage 4F; docs/rea/STAGE-4A-ARCHITECTURE.md sections 6.9 and 8, the Stage 4F
brief). READ-WRITE on the game folder ONLY inside `apply`/`rollback`/`recover`, and only after preflight passed and
verified backups exist. This module never launches the game, never touches catalog.bin/catalog.hash/manifest.dat,
never runs Steam verification, and never disables anything.

RELATIONSHIP TO THE EXISTING INSTALLER: `install.install` / `install.restore` (the hash-verified backup, temp-file
+ os.replace, re-hash, restore-on-error path) stay exactly as they are - the Studio's existing Put-in-game button
keeps using them. This module is the transactional path for Stage 4G: the same foundations (hash-verified backup,
temp file + os.replace, re-hash after every write) wrapped in a DURABLE JOURNAL so an interrupted installation can
be inspected and recovered, a failed one rolled back exactly, and every step audited.

TRANSACTION LIFECYCLE (every transition persisted in the registry's `transactions` table, one connection per write,
so the journal survives process termination):
  created -> preflight -> preflight_passed -> backup_in_progress -> backups_verified -> installing -> verifying
    -> completed
  preflight -> failed (nothing was written; the blocked conditions are in the record)
  installing/verifying -> rollback_required -> rolling_back -> rolled_back | rollback_failed
  any recovered-from state -> manual_intervention (a person decides; nothing is modified)
A cancel request is honoured only BEFORE a destructive step; a cancelled transaction is journalled
(rollback_required -> rolled_back, or left recoverable) and never reported as completed.

JOURNAL PLACEMENT: the same per-installation SQLite registry as the inventory and the graph (one database system,
one identity). Durability relies on SQLite's commit semantics; actual power-loss behaviour was NOT tested and is
not claimed. Backups live under `<workspace>/backups/<install_id>/<tx_id>/files/<rel-path>` and are never pruned;
the legacy `<workspace>/backups/<timestamp>` sets are untouched. A human-readable `transaction.json` copy is written
into the backup folder, but the database stays authoritative.

IDENTITY: a transaction is keyed by `tx_id` (UTC timestamp + random hex), tied to `install_id` (the gameinstall
profile identity), the package id/dir/schema and the profile's game build, catalog and manifest identities. Target
files are addressed by RELATIVE path; every absolute path is re-resolved and checked to stay inside the installation
root, and package paths containing traversal, absolute components or symlinks out of the root are blocked (never
overridable).
"""
import json
import os
import re
import secrets
import shutil
import time
from pathlib import Path

from .bundles import sha256
from .gameinstall import drift as profile_drift

# states a new transaction must not collide with (an incomplete or unresolved transaction needs recovery first)
BUSY_STATES = ("backup_in_progress", "backups_verified", "installing", "verifying", "rollback_required",
               "rolling_back", "rollback_failed", "manual_intervention")
SAFE_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._ -]*$")            # a flat bundle name; never a path
STAGE3G_CAVEAT = ("the catalog is never patched: Unity logs a CRC mismatch for this file and, in the one tested build "
                   "and scenario (27.1.0.2505117, one composition edit, Stage 3G), still loaded the modified bundle - "
                   "observed, not guaranteed; the exact retry path was not observed")


class InstallRefused(RuntimeError):
    """A refused preflight/apply/rollback. `blocked`/`confirmations` carry the structured detail for the UI."""

    def __init__(self, message, blocked=None, confirmations=None):
        super().__init__(message)
        self.blocked = blocked or []
        self.confirmations = confirmations or []


def _now():
    return time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())


def _new_tx_id():
    return "%s-%s" % (_now(), secrets.token_hex(4))


def _resolve_target(root, rel):
    """The absolute target for a relative path, or None when the path is unsafe. Rejects absolute paths, traversal,
    backslashes, and anything that resolves outside the installation root or through a symlink."""
    if not SAFE_NAME.fullmatch(str(rel)):
        return None
    root, target = Path(root).resolve(), (Path(root) / rel).resolve()
    try:
        target.relative_to(root)
    except ValueError:
        return None
    if target.parent != root:                                   # flat bundle names only: no subfolders from packages
        return None
    return target


def _reg(ws, profile):
    """The per-installation journal database (the same registry as the inventory and the graph)."""
    from . import registry as registry_mod
    return registry_mod.Registry.for_install(ws, profile["install_id"])


# ---------------------------------------------------------------- preflight (READ ONLY)
def preflight(ws, profile, build_dir):
    """Inspect the package and the target installation WITHOUT modifying either. Returns the structured result of
    the brief's section 5.4: ready, blocked, warnings, required_confirmations, file_operations, target_profile,
    package_identity, integrity_summary, diagnostics."""
    build_dir = Path(build_dir)
    blocked, warnings, confirmations, diagnostics = [], [], [], []
    pkg = _load_package(build_dir, blocked, diagnostics)
    report = _load_build_report(build_dir, blocked, diagnostics)
    target_profile = {"install_id": profile.get("install_id"), "game_build": profile.get("game_build"),
                      "steam_build_id": profile.get("steam_build_id"), "unity_version": profile.get("unity_version"),
                      "game_dir": profile.get("game_dir"), "aa_roots": profile.get("aa_roots"),
                      "catalog_sha256": profile.get("catalog_sha256"), "manifest_dat_sha256": profile.get("manifest_dat_sha256")}
    # installation identity: the profile must describe the folder as it is NOW
    d = profile_drift(profile)
    if d:
        blocked.append({"code": "stale_installation_identity", "message": "the game folder no longer matches its profile",
                        "drift": d})
    # a busy earlier transaction must be recovered first (no concurrent installs)
    from . import registry as registry_mod
    reg = registry_mod.Registry.for_install(ws, profile["install_id"])
    busy = reg.list_txs(states=BUSY_STATES, limit=1)
    if busy:
        blocked.append({"code": "incomplete_transaction", "message":
                       "an earlier installation transaction (%s, state %s) is unfinished; recover or roll it back first"
                       % (busy[0]["tx_id"], busy[0]["state"]), "tx_id": busy[0]["tx_id"]})
    file_operations, integrity = [], []
    if pkg and report:
        aa = Path(profile["aa_roots"][0])
        if pkg.get("game_build") and profile.get("game_build") and pkg["game_build"] != profile["game_build"]:
            blocked.append({"code": "stale_game_build", "message":                            # never overridable: two builds must not mix
                            "the package was built for game build %s, the selected installation is %s; take a new snapshot "
                            "and rebuild" % (pkg["game_build"], profile["game_build"])})
        from . import install as legacy
        installed = legacy.installed_hashes(ws)                 # files this app ever wrote (legacy + journaled)
        for tx in reg.list_txs(limit=200):
            for op in reg.get_ops(tx["tx_id"]):
                if op.get("actual_sha256"):
                    installed.setdefault(op["rel_path"], set()).add(op["actual_sha256"])
        seen = set()
        out_names = [o.get("rel_path") for o in (pkg.get("outputs") or []) if isinstance(o, dict)]
        for name in sorted(n for n in out_names if out_names.count(n) > 1):
            blocked.append({"code": "duplicate_output", "message": "the package lists %s twice in its outputs" % name})
        files = pkg.get("files")
        if not isinstance(files, dict) or not files:
            blocked.append({"code": "invalid_package", "message": "the package lists no files"})
        else:
            for name, f in sorted(files.items()):
                if name in seen:
                    blocked.append({"code": "duplicate_output", "message": "the package lists %s twice" % name})
                    continue
                seen.add(name)
                if not isinstance(f, dict) or not f.get("sha256") or not f.get("vanilla_sha256"):
                    blocked.append({"code": "invalid_package", "message": "the package entry for %s is incomplete" % name})
                    continue
                target = _resolve_target(aa, name)
                if target is None:
                    blocked.append({"code": "unsafe_path", "message": "the package target %r is not a safe bundle name" % name})
                    continue
                src = build_dir / name                 # a package.json file entry IS a changed output (write_package
                if not src.is_file():                  # lists only changed files); the snapshot installs unchanged ones
                    blocked.append({"code": "missing_package_file", "message": "the package file %s is missing from %s" % (name, build_dir)})
                    continue
                actual = sha256(src)
                if actual != f.get("sha256"):
                    blocked.append({"code": "invalid_package_hash", "message": "%s does not match its package SHA-256" % name})
                op = {"rel_path": name, "target_path": str(target), "op": "replace", "source": str(src),
                      "expected_sha256": f.get("sha256"), "original_exists": target.is_file()}
                if target.is_file():
                    live = sha256(target)
                    op["original_sha256"] = live
                    op["original_size"] = target.stat().st_size
                    if live == f.get("vanilla_sha256"):
                        op["target_state"] = "stock"
                    elif live == f.get("sha256"):
                        op["target_state"] = "already_this_package"
                    elif live in installed.get(name, set()):
                        op["target_state"] = "installed_by_this_app"
                    else:
                        op["target_state"] = "changed"
                        blocked.append({"code": "changed_target", "message":
                                        "%s in the game folder is not the stock file, not a file this app installed, and not "
                                        "this package's output; it was changed by something else" % name, "rel_path": name,
                                        "confirmation": "changed_target"})
                        confirmations.append({"name": "changed_target", "reason": "the target file was changed by "
                                              "something other than this app; installing will back up and replace its CURRENT state"})
                else:
                    op["target_state"] = "missing"
                    blocked.append({"code": "missing_target", "message": "%s is not in the game folder" % name})
                file_operations.append(op)
        # Stage 5H: PREFLIGHT is the authoritative integrity comparison. The package's build-time statuses stay
        # as information, but the target installation's own catalog.bin/manifest.dat are read here, now, and the
        # output is compared against them (a Steam change to manifest.dat after the build is therefore respected).
        pkg = _live_integrity(pkg, profile, build_dir)
        integrity = _integrity_summary(pkg, warnings, confirmations, diagnostics)
        stale = legacy.stale_package_info(ws, pkg.get("project") or report.get("project"), build_dir, pkg)
        if stale:
            warnings.append({"code": "stale_package",
                             "message": "this build package (%s) is older than the project's last change (%s); "
                                        "rebuild before installing, or confirm to install the older package"
                                        % (stale["package_built_utc"], stale["project_changed_utc"])})
            confirmations.append({"name": "stale_package",
                                  "reason": "the build package is older than the project's last change"})
    ready = not blocked
    return {"ready": ready, "blocked": blocked, "warnings": warnings,
            "required_confirmations": sorted(set(c["name"] for c in confirmations)),
            "file_operations": file_operations, "target_profile": target_profile,
            "package_identity": _package_identity(pkg, build_dir), "integrity_summary": integrity,
            "diagnostics": diagnostics}


def _load_package(build_dir, blocked, diagnostics):
    from . import manifest as manifest_mod
    p = build_dir / "package.json"
    if not p.is_file():
        blocked.append({"code": "invalid_package", "message": "no package.json in %s" % build_dir})
        return None
    try:
        return manifest_mod.read_package(p)
    except ValueError as e:
        blocked.append({"code": "invalid_package", "message": str(e)})
        return None


def _load_build_report(build_dir, blocked, diagnostics):
    p = build_dir / "build-report.json"
    if not p.is_file():
        blocked.append({"code": "invalid_package", "message": "no build-report.json in %s" % build_dir})
        return None
    report = json.loads(p.read_text(encoding="utf-8"))
    if report.get("gate", {}).get("fail"):
        blocked.append({"code": "failed_gate", "message": "the build failed its structural gate and cannot be installed"})
    return report


def _package_identity(pkg, build_dir):
    if not pkg:
        return {"dir": str(build_dir)}
    return {"id": pkg.get("id"), "schema": pkg.get("schema"), "project": pkg.get("project"),
            "game_build": pkg.get("game_build"), "dir": str(build_dir)}


def _live_integrity(pkg, profile, build_dir):
    """Recompute catalog and manifest comparisons against the TARGET installation as it is NOW (read only).
    Returns a package copy whose outputs carry the live statuses/integrity. Missing sources stay `not_checked`,
    which is reported as a warning, never silently dropped."""
    import zlib
    from . import bundles as bundles_mod, catalog as catalog_mod, fmmanifest
    pkg2 = dict(pkg)
    outs = []
    aa = Path(profile["aa_roots"][0])
    streaming = aa.parent
    cat_path = next((p for p in (streaming / "catalog.bin", aa / "catalog.bin") if p.is_file()), None)
    game_dir = Path(profile.get("game_dir") or aa.parents[3])
    man_path = game_dir / "fm_Data" / "manifest.dat"
    man_path = man_path if man_path.is_file() else None
    cat_idx = catalog_mod.read(cat_path) if cat_path else None
    man_idx = fmmanifest.read(man_path) if man_path else None
    outs_src = pkg.get("outputs") or [{"rel_path": n} for n in sorted((pkg.get("files") or {}))]
    for o in outs_src:
        rec = dict(o)
        name = rec.get("rel_path")
        built = Path(build_dir) / name
        # the current target file (stock or otherwise) is what manifest.dat describes
        target = aa / name
        cat_status, cat = "not_checked", {"resolution": "no catalog.bin", "stored_crc32": None,
                                          "actual_crc32": None, "comparison": "not_checked"}
        if cat_idx and cat_idx.get("status") == "ok" and built.is_file():
            r = catalog_mod.resolve(cat_idx, name)
            stored = (r.get("records") or [{}])[0].get("crc") if r.get("status") == "found" else None
            try:
                actual = bundles_mod.crc32_uncompressed(built)
            except Exception:
                actual = None
            cat_status = catalog_mod.catalog_crc_status(r.get("status"), stored, actual)
            cat = {"resolution": "found" if stored is not None else r.get("status"),
                   "stored_crc32": ("%08x" % stored) if stored is not None else None,
                   "actual_crc32": ("%08x" % actual) if actual is not None else None,
                   "comparison": cat_status}
        man_status = "manifest_not_checked"
        man = {"entry_status": "no manifest.dat", "stored_crc32": None, "comparison": "not_checked"}
        if man_idx and man_idx.get("status") == "ok" and target.is_file() and built.is_file():
            base = fmmanifest.lookup(man_idx.get("data"), target.read_bytes())
            out_crc = "%08x" % (zlib.crc32(built.read_bytes()) & 0xFFFFFFFF)
            if base.get("status") == "manifest_match":
                man_status = "manifest_match" if base.get("crc32") == out_crc else "manifest_mismatch"
            else:
                man_status = base.get("status") or "manifest_entry_missing"
            man = {"entry_status": base.get("status"), "stored_crc32": base.get("crc32"),
                   "output_crc32": out_crc, "comparison": man_status}
        # live wins when the installation supplies the source; otherwise the build-time record stays, labelled
        if cat_status != "not_checked" or not rec.get("catalog_crc_status"):
            rec["catalog_crc_status"] = cat_status
        else:
            cat = (rec.get("integrity") or {}).get("catalog") or cat
        if man_status not in ("manifest_not_checked", "not_checked") or not rec.get("manifest_status"):
            rec["manifest_status"] = man_status
        else:
            man = (rec.get("integrity") or {}).get("manifest_dat") or man
        rec["integrity"] = {"catalog": cat, "manifest_dat": man,
                            "source_installation": "preflight (live)" if (cat_idx or man_idx) else "package (build)"}
        outs.append(rec)
    pkg2["outputs"] = outs
    return pkg2


def _integrity_summary(pkg, warnings, confirmations, diagnostics):
    """The Stage 4E integrity sections of the package, reported as warnings and required confirmations. A catalog or
    manifest MISMATCH is a warning that must be confirmed, never a silent pass, never an automatic block; the Stage 3G
    caveat travels with it. Missing/ambiguous/unsupported/not-checked states are plain warnings."""
    out = []
    for o in (pkg.get("outputs") or []):
        row = {"rel_path": o.get("rel_path"), "catalog_crc_status": o.get("catalog_crc_status"),
               "manifest_status": o.get("manifest_status")}
        integrity = o.get("integrity")
        if isinstance(integrity, dict):
            row["catalog"] = {k: (integrity.get("catalog") or {}).get(k) for k in ("resolution", "record_offset", "stored_crc32", "comparison")}
            row["manifest_dat"] = {k: (integrity.get("manifest_dat") or {}).get(k) for k in ("entry_status", "stored_crc32", "comparison")}
            row["source_installation"] = integrity.get("source_installation")
        status = row.get("catalog_crc_status")
        if status == "catalog_crc_mismatch":
            warnings.append({"code": "catalog_crc_mismatch", "rel_path": row["rel_path"],
                              "message": "the catalog record for %s holds the ORIGINAL CRC; Unity will log a mismatch for the "
                                         "installed file. %s" % (row["rel_path"], STAGE3G_CAVEAT)})
            confirmations.append({"name": "catalog_crc_mismatch", "reason": "install a file whose catalog CRC differs (Stage 3G: "
                                  "tolerated in the one tested scenario; observed, not guaranteed)"})
        elif status in ("catalog_record_missing", "catalog_record_ambiguous", "catalog_parse_unsupported",
                         "catalog_parse_failed", "catalog_identity_stale", "not_checked", None):
            warnings.append({"code": status or "catalog_not_checked", "rel_path": row["rel_path"],
                              "message": "%s: the catalog comparison is %s (not a match, not a pass)" % (row["rel_path"], status or "not checked")})
        mstatus = row.get("manifest_status")
        if mstatus == "manifest_mismatch":
            warnings.append({"code": "manifest_mismatch", "rel_path": row["rel_path"],
                              "message": "manifest.dat holds the ORIGINAL whole-file CRC for %s; the installed file will not match it" % row["rel_path"]})
            confirmations.append({"name": "manifest_mismatch", "reason": "install a file whose manifest.dat whole-file CRC differs "
                                  "(Stage 3D static evidence: the verifier only runs with --verify_build and feeds a crash-report "
                                  "attribute; not a runtime observation)"})
        elif mstatus in ("manifest_entry_missing", "manifest_entry_ambiguous", "manifest_parse_unsupported",
                         "manifest_parse_failed", "manifest_not_checked", "not_checked", None):
            warnings.append({"code": mstatus or "manifest_not_checked", "rel_path": row["rel_path"],
                              "message": "%s: the manifest.dat comparison is %s (not a match, not a pass)" % (row["rel_path"], mstatus or "not checked")})
        out.append(row)
    return out


# ---------------------------------------------------------------- the transaction engine
def apply(ws, profile, build_dir, confirmations=(), running=None, progress=None, cancel=None):
    """One complete installation transaction. Returns the transaction record on completion. Raises InstallRefused
    before anything is written (blocked preflight, unapproved confirmations, a busy transaction, the game running);
    a cancelled or failed transaction is journalled and rolled back, never reported as completed."""
    progress = progress or (lambda m, f: None)
    cancel = cancel or (lambda: False)
    from . import registry as registry_mod
    reg = registry_mod.Registry.for_install(ws, profile["install_id"])
    tx_id = _new_tx_id()
    rec = {"tx_id": tx_id, "install_id": profile["install_id"], "state": "created", "created_utc": _now(),
           "updated_utc": _now(), "initiating": "install.apply", "package_dir": str(build_dir), "overrides": None}
    _begin(ws, reg, rec, profile, build_dir)
    if running and running():
        reg.update_tx(tx_id, state="failed", error="the game is running or updating; close it first")
        raise InstallRefused("the game is running or updating; close it first")
    reg.update_tx(tx_id, state="preflight")
    pf = preflight(ws, profile, build_dir)
    rec["package_id"] = pf["package_identity"].get("id")
    rec["package_schema"] = pf["package_identity"].get("schema")
    rec["project"] = pf["package_identity"].get("project")
    approved = sorted(set(confirmations or ()))
    reg.update_tx(tx_id, state="preflight_passed", preflight=json.dumps(pf, default=str), overrides=json.dumps(approved))
    unknown = sorted(set(approved) - {"catalog_crc_mismatch", "manifest_mismatch", "changed_target", "stale_package"})
    if unknown:                                                    # unknown confirmations are refused outright: only
        reg.update_tx(tx_id, state="failed", error="unknown confirmations: " + ", ".join(unknown))   # narrowly scoped,
        raise InstallRefused("unknown confirmations (not offered by this preflight): " + ", ".join(unknown))  # preflight-known
    # blocked conditions split: an overridable one (it carries a confirmation name, offered by THIS preflight) passes
    # only when that exact confirmation was given; everything else is hard and never waved through
    hard = [b for b in pf["blocked"] if not b.get("confirmation") or b["confirmation"] not in approved]
    if hard:
        reg.update_tx(tx_id, state="failed", error="; ".join(b["message"] for b in hard))
        raise InstallRefused("the installation was refused: " + "; ".join(b["message"] for b in hard), blocked=hard)
    missing = [c for c in pf["required_confirmations"] if c not in approved]
    if missing:
        reg.update_tx(tx_id, state="failed", error="confirmations required: " + ", ".join(missing))
        raise InstallRefused("the installation needs explicit confirmation for: " + ", ".join(missing),
                             confirmations=pf["required_confirmations"])
    ops = pf["file_operations"]
    try:
        _backup(ws, reg, tx_id, profile, ops, progress, cancel)
        _install(ws, reg, tx_id, profile, list(enumerate(ops)), progress, cancel)
        _finalize(ws, reg, tx_id, profile, pf, approved, progress)
    except _Rollback as e:                                     # a mid-transaction failure or cancel: roll back exactly
        reg.update_tx(tx_id, state="rollback_required", error=e.message)
        _rollback(ws, reg, tx_id, profile, progress=progress, cancel=cancel)
        raise InstallRefused(e.message) from None
    except Cancelled as e:                                     # cancelled before a destructive step: the transaction is
        reg.update_tx(tx_id, error="cancelled before completion; recover or roll this transaction back")   # left journalled
        raise                                                   # and recoverable, never reported as completed
    return reg.get_tx(tx_id)


class _Rollback(Exception):
    def __init__(self, message):
        super().__init__(message)
        self.message = message


class Cancelled(Exception):
    """Raised inside `apply` when a cancel is honoured before a destructive step; the transaction is journalled and
    rolled back (or left recoverable), and never reported as completed."""

    def __init__(self, summary):
        super().__init__("installation cancelled")
        self.summary = summary


def _begin(ws, reg, rec, profile, build_dir):
    rec.update(game_build=profile.get("game_build"), steam_build_id=profile.get("steam_build_id"),
               catalog_sha256=profile.get("catalog_sha256"), manifest_sha256=profile.get("manifest_dat_sha256"))
    reg.begin_tx(rec)
    bdir = _backup_dir(ws, profile, rec["tx_id"])
    bdir.mkdir(parents=True, exist_ok=True)


def _backup_dir(ws, profile, tx_id):
    return Path(ws.backups) / profile["install_id"] / tx_id


def _backup(ws, reg, tx_id, profile, ops, progress, cancel):
    """Verified backups BEFORE any replacement: copy, fsync, hash, compare with preflight, journal per file."""
    reg.update_tx(tx_id, state="backup_in_progress")
    bdir = _backup_dir(ws, profile, tx_id) / "files"
    for i, op in enumerate(ops):
        if cancel():
            raise Cancelled({"tx_id": tx_id, "state": "backup_in_progress"})
        progress("backing up %s" % op["rel_path"], i / max(1, len(ops)))
        row = {"rel_path": op["rel_path"], "op": op["op"], "target_path": op["target_path"],
               "original_exists": bool(op["original_exists"]), "original_sha256": op.get("original_sha256"),
               "original_size": op.get("original_size"), "expected_sha256": op["expected_sha256"], "state": "pending"}
        if not op["original_exists"]:
            row.update(state="no_original", rollback_state="nothing_to_restore")    # a file the transaction will create
            reg.put_op(tx_id, i, row)
            continue
        dst = bdir / op["rel_path"]
        dst.parent.mkdir(parents=True, exist_ok=True)
        _copy_verified(Path(op["target_path"]), dst)
        h = sha256(dst)
        if h != op["original_sha256"]:
            row.update(state="backup_failed", error="backup hash does not equal the preflight original")
            reg.put_op(tx_id, i, row)
            raise _Rollback("the backup of %s did not verify; nothing was installed" % op["rel_path"])
        row.update(state="backup_verified", backup_path=str(dst), backup_sha256=h)
        reg.put_op(tx_id, i, row)
    reg.update_tx(tx_id, state="backups_verified")


def _copy_verified(src, dst):
    """Copy + flush to disk (the existing installer's temp-file + atomic-replacement foundation, one place).
    Verification is the CALLER's job: every caller compares the result against the hash it expects, with its own
    journal row and its own error state."""
    tmp = dst.with_name("." + dst.name + ".fm27se.tmp")
    with open(src, "rb") as a, open(tmp, "wb") as b:
        shutil.copyfileobj(a, b)
        b.flush()
        os.fsync(b.fileno())
    os.replace(tmp, dst)


def _install(ws, reg, tx_id, profile, plan, progress, cancel):
    """Stage, verify, atomically replace, verify again - one journalled operation at a time. `plan` is
    [(op_index, op)] so the journal row of each operation keeps its stable index across apply, resume and recovery."""
    reg.update_tx(tx_id, state="installing")
    all_rows = reg.get_ops(tx_id)
    for i, op in plan:
        if cancel():
            raise Cancelled({"tx_id": tx_id, "state": "installing"})
        progress("installing %s" % op["rel_path"], i / max(1, len(plan)))
        row = all_rows[i]
        target = Path(op["target_path"])
        live = sha256(target) if target.is_file() else None
        if live == op["expected_sha256"] and row.get("state") != "replaced":
            reg.put_op(tx_id, i, dict(row, state="already_installed", actual_sha256=live, verify="match"))
            continue
        if live != op.get("original_sha256") and live is not None:
            reg.put_op(tx_id, i, dict(row, state="conflict", error="the target changed since preflight"))
            raise _Rollback("%s changed since preflight; the transaction was stopped and the originals restored"
                            % op["rel_path"])
        staged = target.with_name("." + target.name + ".tx-%s.tmp" % tx_id)
        _copy_verified(Path(op["source"]), staged)
        staged_sha = sha256(staged)
        if staged_sha != op["expected_sha256"]:
            staged.unlink(missing_ok=True)
            reg.put_op(tx_id, i, dict(row, state="stage_failed", error="the staged file does not match the package hash"))
            raise _Rollback("the staged copy of %s did not match the package SHA-256; nothing was installed" % op["rel_path"])
        reg.put_op(tx_id, i, dict(row, state="staged", staged_path=str(staged), staged_sha256=staged_sha))
        all_rows = reg.get_ops(tx_id)                           # the staged state is PERSISTED before the replacement
        os.replace(staged, target)
        final = sha256(target)
        verify = "match" if final == op["expected_sha256"] else "mismatch"
        reg.put_op(tx_id, i, dict(all_rows[i], state="replaced", actual_sha256=final, replaced_utc=_now(), verify=verify))
        all_rows = reg.get_ops(tx_id)
        if final != op["expected_sha256"]:
            raise _Rollback("%s did not verify after replacement; the originals are being restored" % op["rel_path"])
    reg.update_tx(tx_id, state="verifying")
    for i, op in plan:                                          # the final pass: a transaction is complete only when
        row = reg.get_ops(tx_id)[i]                             # every file is verified on disk as it now stands
        target = Path(op["target_path"])
        if not target.is_file() or sha256(target) != (row.get("actual_sha256") or op["expected_sha256"]):
            raise _Rollback("%s does not hold its verified state; the originals are being restored" % op["rel_path"])


def _finalize(ws, reg, tx_id, profile, pf, approved, progress):
    progress("recording the installation", 0.98)
    completed = _now()
    reg.update_tx(tx_id, state="completed", completed_utc=completed)
    ops = reg.get_ops(tx_id)
    record = _installs_record(ws, profile, tx_id, "completed", ops, approved)
    record["integrity_warnings"] = [w["code"] for w in pf["warnings"]]
    from . import install as legacy
    for o in ops:                                              # the legacy log keeps the whole ecosystem informed
        legacy._log(ws, project=pf["package_identity"].get("project") or "", file=o["rel_path"],
                    before=o.get("original_sha256"), after=o.get("actual_sha256"),
                    backup=o.get("backup_path"), tx=tx_id)
    note = _append_installs(Path(pf["package_identity"]["dir"]), record)
    if note:
        reg.update_tx(tx_id, recovery=note)                    # the journal stays authoritative; the failure is reported
    _write_transaction_json(_backup_dir(ws, profile, tx_id), reg.get_tx(tx_id), ops)


def _append_installs(build_dir, record):
    """Append the installation record to the schema 2 `installs` arrays (package.json when it is schema 2, and
    build-manifest.json), each rewritten atomically with unknown fields preserved. Returns None, or the reason a
    manifest could not be updated (the journal is the authority and the failure is reported, not hidden)."""
    notes = []
    for name in ("package.json", "build-manifest.json"):
        p = build_dir / name
        if not p.is_file():
            if name == "build-manifest.json":
                notes.append("no build-manifest.json in the package")
            continue
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, ValueError) as e:
            notes.append("%s could not be read (%s)" % (name, e))
            continue
        if name == "package.json" and d.get("schema") != 2:
            notes.append("package.json is schema %s: its installs array is not written (schema 1 compatibility)" % d.get("schema"))
            continue
        existing = [r for r in d.get("installs") or [] if r.get("tx_id") != record["tx_id"]]
        d["installs"] = existing + [record]
        tmp = p.with_suffix(p.suffix + ".fm27se.tmp")
        try:
            tmp.write_text(json.dumps(d, indent=1, default=str), encoding="utf-8")
            os.replace(tmp, p)
        except OSError as e:
            notes.append("%s could not be written (%s); the transaction journal remains the record" % (name, e))
    return "; ".join(notes) or None


def _write_transaction_json(bdir, tx, ops):
    """The human-readable copy of the transaction in its backup folder (the database stays authoritative)."""
    try:
        (bdir / "transaction.json").write_text(json.dumps(dict(tx, file_operations=ops), indent=1, default=str),
                                               encoding="utf-8")
    except OSError:
        pass


# ---------------------------------------------------------------- rollback
def rollback(ws, reg, profile, tx_id, progress=None, cancel=None):
    """Explicit rollback of one transaction to its exact pre-installation state. Idempotent per file; a target that
    changed independently is never overwritten (the op is marked conflicted and the transaction rollback_failed)."""
    progress = progress or (lambda m, f: None)
    tx = reg.get_tx(tx_id)
    if tx is None:
        raise InstallRefused("no such transaction: %s" % tx_id)
    return _rollback(ws, reg, tx_id, profile, progress=progress, cancel=cancel)


def _rollback(ws, reg, tx_id, profile, progress=None, cancel=None):
    progress = progress or (lambda m, f: None)
    cancel = cancel or (lambda: False)
    tx = reg.get_tx(tx_id)
    if tx is None:
        raise InstallRefused("no such transaction: %s" % tx_id)
    ops = reg.get_ops(tx_id)
    if not ops:
        reg.update_tx(tx_id, state="rolled_back")               # nothing was ever written
        return reg.get_tx(tx_id)
    reg.update_tx(tx_id, state="rolling_back")
    conflicts, failures = [], []
    for i, row in enumerate(ops):
        if cancel():
            reg.update_tx(tx_id, state="rollback_required", error="rollback cancelled; it can be continued")
            raise Cancelled({"tx_id": tx_id, "state": "rollback_required"})
        progress("rolling back %s" % row["rel_path"], i / len(ops))
        target = _resolve_target(Path(profile["aa_roots"][0]), row["rel_path"])
        if target is None:
            conflicts.append("%s: the target path is no longer safe" % row["rel_path"])
            reg.put_op(tx_id, i, dict(row, rollback_state="conflict", error="unsafe path"))
            continue
        live = sha256(target) if target.is_file() else None
        if row.get("rollback_state") == "rolled_back" or live == row.get("original_sha256") and row["original_exists"]:
            if row.get("staged_path"):                          # an interrupted transaction can leave its staged temp
                Path(row["staged_path"]).unlink(missing_ok=True)  # behind even though the target was never replaced
            reg.put_op(tx_id, i, dict(row, rollback_state="rolled_back", staged_path=None))   # idempotent: restored
            continue
        if not row["original_exists"]:                          # the file was created by the transaction: remove it,
            if live == row.get("actual_sha256"):               # but only if it still is the transaction's own output
                target.unlink()
                reg.put_op(tx_id, i, dict(row, rollback_state="rolled_back"))
            elif live is None:
                reg.put_op(tx_id, i, dict(row, rollback_state="rolled_back"))
            else:
                conflicts.append("%s was created by the transaction but has changed since; it was left alone" % row["rel_path"])
                reg.put_op(tx_id, i, dict(row, rollback_state="conflict", error="created file changed after installation"))
            continue
        backup = Path(row["backup_path"]) if row.get("backup_path") else None
        if backup is None or not backup.is_file() or sha256(backup) != row.get("backup_sha256"):
            failures.append("%s: the backup is missing or corrupt" % row["rel_path"])
            reg.put_op(tx_id, i, dict(row, rollback_state="backup_failed", error="backup missing or corrupt"))
            continue
        if live is not None and live not in (row.get("original_sha256"), row.get("actual_sha256")):
            conflicts.append("changed_target: %s changed independently after installation; it was left alone"
                             % row["rel_path"])
            reg.put_op(tx_id, i, dict(row, rollback_state="conflict", error="changed_target: target changed independently"))
            continue
        _copy_verified(backup, target)
        if sha256(target) != row["original_sha256"]:
            failures.append("%s: the restored file does not verify" % row["rel_path"])
            reg.put_op(tx_id, i, dict(row, rollback_state="verify_failed"))
            continue
        if row.get("staged_path"):                              # the transaction's own staged temp file, cleaned only at
            Path(row["staged_path"]).unlink(missing_ok=True)   # this verified terminal state (backups are kept)
        reg.put_op(tx_id, i, dict(row, rollback_state="rolled_back"))
    if conflicts or failures:
        reg.update_tx(tx_id, state="rollback_failed",
                     error="; ".join(conflicts + failures) + " - manual intervention required; nothing conflicted was overwritten")
        _update_installs_rollback(ws, profile, tx_id, "rollback_failed")
        return reg.get_tx(tx_id)
    reg.update_tx(tx_id, state="rolled_back", completed_utc=None)
    _update_installs_rollback(ws, profile, tx_id, "rolled_back")
    _write_transaction_json(_backup_dir(ws, profile, tx_id), reg.get_tx(tx_id), reg.get_ops(tx_id))
    return reg.get_tx(tx_id)


def _update_installs_rollback(ws, profile, tx_id, status):
    """Set the rollback status on the package manifest's installs record when one exists; a missing manifest is fine
    (the journal is the authority)."""
    tx = None
    from . import registry as registry_mod
    reg = registry_mod.Registry.for_install(ws, profile["install_id"])
    tx = reg.get_tx(tx_id)
    d = Path(tx["package_dir"]) if tx and tx.get("package_dir") else None
    if not d:
        return
    stamp = {"utc": _now(), "status": status}
    for name in ("package.json", "build-manifest.json"):
        p = d / name
        if not p.is_file():
            continue
        try:
            doc = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if doc.get("schema") not in (None, 2) and name == "package.json":
            continue
        for r in doc.get("installs") or []:
            if r.get("tx_id") == tx_id:
                r["rollback"] = stamp
        tmp = p.with_suffix(p.suffix + ".fm27se.tmp")
        try:
            tmp.write_text(json.dumps(doc, indent=1, default=str), encoding="utf-8")
            os.replace(tmp, p)
        except OSError:
            pass


# ---------------------------------------------------------------- crash recovery
def recovery_scan(ws, profile):
    """READ ONLY: every unfinished transaction, assessed against the journal AND the actual hashes on disk. Returns
    per-transaction: what happened, what is safe (resume / rollback / complete), what conflicts, and a recommendation.
    Nothing is modified; resume/rollback are explicit `recover` actions."""
    from . import registry as registry_mod
    reg = registry_mod.Registry.for_install(ws, profile["install_id"])
    out = []
    for tx in reg.list_txs(states=BUSY_STATES, limit=50):
        ops = reg.get_ops(tx["tx_id"])
        replaced = [o for o in ops if o.get("state") == "replaced"]
        intact_replaced = all(Path(o["target_path"]).is_file() and sha256(Path(o["target_path"])) == o.get("actual_sha256")
                              for o in replaced)
        pending = [o for o in ops if o.get("state") in ("pending", "backup_verified", "staged", "no_original")]
        originals_ok = all(not o["original_exists"] or (Path(o["target_path"]).is_file()
                                                        and sha256(Path(o["target_path"])) == o.get("original_sha256"))
                            for o in pending)
        conflicts = []
        for o in ops:
            live = sha256(Path(o["target_path"])) if Path(o["target_path"]).is_file() else None
            if o.get("state") == "replaced" and live != o.get("actual_sha256"):
                conflicts.append("%s does not hold the installed state" % o["rel_path"])
            if o.get("state") in ("pending", "backup_verified", "staged") and o["original_exists"] \
                    and live not in (o.get("original_sha256"), o.get("actual_sha256")):
                conflicts.append("%s changed independently" % o["rel_path"])
        if conflicts:
            actions, recommendation = ["rollback", "manual"], "manual"
        elif replaced and len(replaced) == len([o for o in ops if o.get("state") != "no_original"]) and intact_replaced:
            actions, recommendation = ["complete"], "complete"            # every file replaced and verified: finish it
        elif not replaced and originals_ok:
            actions, recommendation = ["rollback", "resume"], "rollback"   # nothing written yet: rollback is safest
        elif intact_replaced and originals_ok:
            actions, recommendation = ["resume", "rollback"], "rollback"  # mid-way but consistent: either is safe
        else:
            actions, recommendation = ["manual"], "manual"
        out.append({"tx_id": tx["tx_id"], "state": tx["state"], "package_dir": tx.get("package_dir"),
                    "error": tx.get("error"), "ops": len(ops), "replaced": len(replaced),
                    "safe_actions": actions, "recommendation": recommendation,
                    "conflicts": conflicts,
                    "note": "nothing was modified by this scan; resume or rollback is an explicit recover action"})
    return {"install_id": profile["install_id"], "transactions": out}


def recover(ws, profile, tx_id, action, running=None, progress=None, cancel=None):
    """EXPLICIT recovery of one unfinished transaction: 'rollback' (restore the originals), 'resume' (only where the
    scan proved it unambiguous), or 'manual' (mark it for a person; modify nothing). Idempotent: a completed rollback
    stays completed; a consistent resume never reinstalls a replaced file."""
    from . import registry as registry_mod
    reg = registry_mod.Registry.for_install(ws, profile["install_id"])
    tx = reg.get_tx(tx_id)
    if tx is None:
        raise InstallRefused("no such transaction: %s" % tx_id)
    if action not in ("rollback", "resume", "manual"):
        raise InstallRefused("the recovery action must be rollback, resume or manual")
    if running and running():
        raise InstallRefused("the game is running or updating; close it first")
    if action == "manual":
        reg.update_tx(tx_id, state="manual_intervention", error=(tx.get("error") or "") + " - marked for manual intervention")
        return reg.get_tx(tx_id)
    if action == "rollback":
        return _rollback(ws, reg, tx_id, profile, progress=progress, cancel=cancel)
    # resume: only from a state the scan can prove consistent
    ops = reg.get_ops(tx_id)
    replaced = [o for o in ops if o.get("state") == "replaced"]
    if tx["state"] not in ("backup_in_progress", "backups_verified", "installing", "verifying"):
        raise InstallRefused("a transaction in state %s cannot be resumed; roll it back" % tx["state"])
    for o in ops:
        live = sha256(Path(o["target_path"])) if Path(o["target_path"]).is_file() else None
        if o.get("state") == "replaced" and live != o.get("actual_sha256"):
            raise InstallRefused("%s does not hold the state the journal recorded; resume is refused, roll back instead"
                                 % o["rel_path"])
        if o.get("state") in ("pending", "backup_verified", "staged") and o["original_exists"] \
                and live not in (o.get("original_sha256"), o.get("actual_sha256")):
            raise InstallRefused("%s changed independently since the interruption; resume is refused, roll back instead"
                                 % o["rel_path"])
    if tx["state"] == "verifying" or (replaced and len(replaced) == len(ops)):
        reg.update_tx(tx_id, state="verifying")
        for o in ops:                                           # the completion check: every file verified as-is
            if not Path(o["target_path"]).is_file() or sha256(Path(o["target_path"])) != (o.get("actual_sha256") or o.get("expected_sha256")):
                raise InstallRefused("the resumed transaction does not verify; roll it back instead")
        reg.update_tx(tx_id, state="completed", completed_utc=_now())
        _append_installs(Path(tx["package_dir"]), _installs_record(ws, profile, tx_id, "completed", ops,
                                                                   json.loads(tx["overrides"]) if tx.get("overrides") else []))
        _write_transaction_json(_backup_dir(ws, profile, tx_id), reg.get_tx(tx_id), ops)
        return reg.get_tx(tx_id)
    # resume the interrupted installation from the journal's position (replaced files keep their state)
    pf = json.loads(tx["preflight"]) if tx.get("preflight") else None
    if not pf:
        raise InstallRefused("the transaction has no preflight record; resume is refused, roll back instead")
    todo = []
    for i, op in enumerate(pf["file_operations"]):
        row = ops[i]
        if row.get("state") == "replaced" or (Path(op["target_path"]).is_file()
                                              and sha256(Path(op["target_path"])) == op["expected_sha256"]):
            continue                                            # already installed (idempotent resume)
        todo.append((i, op))
    try:
        _install(ws, reg, tx_id, profile, todo, progress or (lambda m, f: None), cancel or (lambda: False))
        approved = json.loads(tx["overrides"]) if tx.get("overrides") else []
        _finalize(ws, reg, tx_id, profile, pf, approved, progress or (lambda m, f: None))
    except _Rollback as e:
        reg.update_tx(tx_id, state="rollback_required", error=e.message)
        _rollback(ws, reg, tx_id, profile, progress=progress, cancel=cancel)
        raise InstallRefused(e.message) from None
    return reg.get_tx(tx_id)


def _installs_record(ws, profile, tx_id, status, ops, approved):
    """The schema 2 `installs` record of one completed installation, built from the journal (the authority)."""
    return {"tx_id": tx_id, "install_id": profile["install_id"], "game_build": profile.get("game_build"),
            "steam_build_id": profile.get("steam_build_id"), "installed_utc": _now(), "status": status,
            "files": [{"rel_path": o["rel_path"], "original_sha256": o.get("original_sha256"),
                       "installed_sha256": o.get("actual_sha256"), "backup_path": o.get("backup_path"),
                       "backup_sha256": o.get("backup_sha256")} for o in ops],
            "approved_overrides": approved, "rollback": None}
