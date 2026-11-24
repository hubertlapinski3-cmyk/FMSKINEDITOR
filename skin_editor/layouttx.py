"""The custom-layout transaction: put a build's custom-layout files into the game's CustomGridCompositions folder and take them out again, exactly.

The same ideas as installtx, for plain files: a READ-ONLY preflight (every file to write, each file already in the folder flagged - a screen the user customised in the game - and an
explicit confirmation required to replace it), an apply that backs the whole folder up and VERIFIES the backup before the first write, writes each file through a temporary file and
checks its hash, and keeps a journal; a rollback that restores the exact earlier state (files the transaction created are removed, the user's own files come back byte for byte,
a file changed since is never overwritten); a recovery scan that finds a half-finished transaction. A user's file is never deleted without a backup.

The journal lives in `journal_dir` (the workspace in the app, a temporary folder in tests); the folder defaults to the game's (`custom_layouts.folder()`).
"""
import hashlib
import json
import os
import re
import shutil
import time
import uuid
from pathlib import Path

from . import custom_layouts as cl

SCHEMA = "fm-layouttx/1"
BUSY_STATES = ("created", "backed_up", "writing", "written", "rollback_required", "rollback_failed")
SAFE_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.\-]{0,127}")


class LayoutTxRefused(Exception):
    def __init__(self, message, blocked=None, confirmations=None):
        super().__init__(message)
        self.blocked, self.confirmations = blocked or [], confirmations or []


def _now():
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def _snapshot(folder):
    return cl.snapshot(folder) if Path(folder).is_dir() else {}


def _tx_dir(journal, tx_id):
    return Path(journal) / tx_id


def _save(journal, tx):
    d = _tx_dir(journal, tx["tx_id"])
    d.mkdir(parents=True, exist_ok=True)
    tx["updated_utc"] = _now()
    (d / "tx.json").write_text(json.dumps(tx, indent=1, sort_keys=True), encoding="utf-8")


def _load(journal, tx_id):
    f = _tx_dir(journal, tx_id) / "tx.json"
    if not f.is_file():
        raise LayoutTxRefused("no such transaction: %s" % tx_id)
    return json.loads(f.read_text(encoding="utf-8"))


def transactions(journal):
    out = []
    for f in sorted(Path(journal).glob("*/tx.json")) if Path(journal).is_dir() else []:
        out.append(json.loads(f.read_text(encoding="utf-8")))
    return out


def _package_files(package_dir):
    """[{name, size, sha256}] the build lists in its custom-layouts.json (fm-customlayouts/1)."""
    f = Path(package_dir) / "custom-layouts.json"
    if not f.is_file():
        return None
    return json.loads(f.read_text(encoding="utf-8")).get("files") or []


def _installed_by_us(journal, name):
    """The hashes this app ever wrote for `name` in a completed (not rolled back) transaction: a file with such a hash is ours, not the user's."""
    out = set()
    for tx in transactions(journal) if journal else []:
        if tx.get("state") == "completed":
            for op in tx.get("ops") or []:
                if op["name"] == name and op.get("after_sha256"):
                    out.add(op["after_sha256"])
    return out


# ---------------------------------------------------------------- preflight (READ ONLY)
def preflight(package_dir, folder=None, journal=None):
    """What applying the package would do, without writing anything. {ready, blocked, warnings, required_confirmations, file_operations, folder, folder_exists}."""
    folder = Path(folder or cl.folder())
    blocked, warnings, confirmations, ops = [], [], [], []
    files = _package_files(package_dir)
    if files is None:
        blocked.append({"code": "invalid_package", "message": "no custom-layouts.json in %s" % package_dir})
        files = []
    if not files and not blocked:
        blocked.append({"code": "invalid_package", "message": "the package lists no custom-layout files"})
    seen = set()
    for f in files:
        name = f.get("name")
        if not isinstance(name, str) or not SAFE_NAME.fullmatch(name) or name in (".", ".."):
            blocked.append({"code": "unsafe_path", "message": "the package target %r is not a safe file name" % (name,)})
            continue
        if name in seen:
            blocked.append({"code": "duplicate_output", "message": "the package lists %s twice" % name})
            continue
        seen.add(name)
        src = Path(package_dir) / "custom-layouts" / name
        if not src.is_file():
            blocked.append({"code": "missing_package_file", "message": "the package file %s is missing from %s" % (name, package_dir)})
            continue
        sha = _sha(src)
        if sha != f.get("sha256"):
            blocked.append({"code": "invalid_package_hash", "message": "%s does not match its package SHA-256" % name})
            continue
        op = {"name": name, "source": str(src), "target_path": str(folder / name), "size": src.stat().st_size, "after_sha256": sha}
        target = folder / name
        if not target.exists():
            op["state"] = "new"
        elif _sha(target) == sha:
            op["state"] = "already_this_package"
            op["before_sha256"] = sha
        else:
            op["before_sha256"] = _sha(target)
            op["before_size"] = target.stat().st_size
            if op["before_sha256"] in _installed_by_us(journal, name):
                op["state"] = "installed_by_this_app"
            else:
                op["state"] = "replaces_user_file"
                confirmations.append({"name": "replace:" + name, "reason": "the folder already holds %s (the screen is customised in the game, or by something else): this file "
                                      "is used by the game instead of the bundle; applying backs it up and replaces it, rolling back puts it back byte for byte" % name})
        ops.append(op)
    if not folder.is_dir():
        warnings.append({"code": "folder_missing", "message": "the custom-layout folder does not exist yet; applying creates it, rolling back removes it again"})
    return {"ready": not blocked, "blocked": blocked, "warnings": warnings, "required_confirmations": sorted({c["name"] for c in confirmations}),
            "confirmation_reasons": {c["name"]: c["reason"] for c in confirmations}, "file_operations": ops, "folder": str(folder), "folder_exists": folder.is_dir()}


# ---------------------------------------------------------------- apply
def apply(journal, package_dir, folder=None, confirmations=(), running=None):
    """One transaction. Returns the transaction record. Raises LayoutTxRefused before anything is written (blocked preflight, a missing confirmation, the game running, a busy
    earlier transaction); a failure after the first write rolls back and is reported, never left half done."""
    folder = Path(folder or cl.folder())
    journal = Path(journal)
    busy = [t for t in transactions(journal) if t.get("state") in BUSY_STATES and Path(t["folder"]) == folder]
    if busy:
        raise LayoutTxRefused("an earlier custom-layout transaction (%s, state %s) is unfinished; recover or roll it back first" % (busy[0]["tx_id"], busy[0]["state"]))
    if running and running():
        raise LayoutTxRefused("the game is running; close it first")
    pf = preflight(package_dir, folder, journal)
    if pf["blocked"]:
        raise LayoutTxRefused("the installation was refused: " + "; ".join(b["message"] for b in pf["blocked"]), blocked=pf["blocked"])
    missing = [c for c in pf["required_confirmations"] if c not in set(confirmations or ())]
    if missing:
        raise LayoutTxRefused("the installation needs explicit confirmation for: " + ", ".join(missing), confirmations=pf["required_confirmations"])
    tx_id = "%s-%s" % (time.strftime("%Y%m%dT%H%M%SZ", time.gmtime()), uuid.uuid4().hex[:8])
    tx = {"schema": SCHEMA, "tx_id": tx_id, "state": "created", "created_utc": _now(), "package_dir": str(package_dir), "folder": str(folder),
          "folder_existed": folder.is_dir(), "confirmations": sorted(set(confirmations or ())), "ops": [dict(o) for o in pf["file_operations"] if o["state"] != "already_this_package"]}
    _save(journal, tx)
    backup = _tx_dir(journal, tx_id) / "backup"
    try:
        if folder.is_dir():
            shutil.copytree(folder, backup)
            tx["backup_sha256"] = _snapshot(backup)
            if tx["backup_sha256"] != _snapshot(folder):
                raise RuntimeError("the backup does not match the folder")
        else:
            backup.mkdir(parents=True, exist_ok=True)
            tx["backup_sha256"] = {}
        tx["state"] = "backed_up"
        _save(journal, tx)
    except Exception as e:
        tx.update(state="failed", error="backup failed, nothing was written: %s" % e)
        _save(journal, tx)
        raise LayoutTxRefused(tx["error"]) from None
    try:
        folder.mkdir(parents=True, exist_ok=True)
        tx["state"] = "writing"
        _save(journal, tx)
        for op in tx["ops"]:
            tmp = folder / (".%s.fm27tx" % op["name"])
            shutil.copyfile(op["source"], tmp)
            if _sha(tmp) != op["after_sha256"]:
                raise RuntimeError("%s was not written intact" % op["name"])
            os.replace(tmp, folder / op["name"])
            if _sha(folder / op["name"]) != op["after_sha256"]:
                raise RuntimeError("%s does not read back as the package file" % op["name"])
            op["written"] = True
            _save(journal, tx)
        tx["state"] = "completed"
        tx["completed_utc"] = _now()
        _save(journal, tx)
    except Exception as e:
        tx.update(state="rollback_required", error=str(e))
        _save(journal, tx)
        rolled = rollback(journal, tx_id, folder)
        raise LayoutTxRefused("the installation failed and was rolled back (%s): %s" % (rolled["state"], e)) from None
    return tx


# ---------------------------------------------------------------- rollback
def rollback(journal, tx_id, folder=None):
    """Restore the folder to its exact state before the transaction. A file this transaction created is removed; a user's file it replaced is copied back from the verified backup;
    a file that changed since the transaction (its hash is neither the written nor the earlier one) is never overwritten: the transaction becomes rollback_failed."""
    journal = Path(journal)
    tx = _load(journal, tx_id)
    folder = Path(folder or tx["folder"])
    backup = _tx_dir(journal, tx_id) / "backup"
    changed_before = changed_since_apply(journal, tx_id, folder)
    conflicts = []
    for op in tx["ops"]:
        tmp = folder / (".%s.fm27tx" % op["name"])
        if tmp.exists():
            tmp.unlink()                                                # a half-written temporary file of this transaction
        target = folder / op["name"]
        before, after = op.get("before_sha256"), op["after_sha256"]
        now = _sha(target) if target.is_file() else None
        if now == before and (before is not None or not target.exists()):
            continue                                                    # already as before
        if now is not None and now != after:
            conflicts.append(op["name"])                                # changed independently: never overwritten
            continue
        if before is None:
            if target.exists():
                target.unlink()                                         # created by this transaction (its hash is the written one)
        else:
            src = backup / op["name"]
            if not src.is_file() or _sha(src) != before:
                conflicts.append(op["name"])
                continue
            shutil.copy2(src, target)
    if not conflicts and not tx.get("folder_existed") and folder.is_dir() and not any(folder.iterdir()):
        folder.rmdir()                                                  # the folder was created by this transaction and is empty again
    ok = not conflicts and _snapshot(folder) == (tx.get("backup_sha256") or {})
    tx["state"] = "rolled_back" if ok else "rollback_failed"
    tx["rollback"] = {"utc": _now(), "conflicts": conflicts, "exact": ok, "folder_now": _snapshot(folder),
                      "changed": changed_before}
    _save(journal, tx)
    return tx


def changed_since_apply(journal, tx_id, folder=None):
    """READ ONLY: files this transaction wrote whose bytes are not the ones it wrote (the game re-saved
    them during play, or a person changed them). [{name, before_sha256, after_sha256, now_sha256}]."""
    journal = Path(journal)
    tx = _load(journal, tx_id)
    folder = Path(folder or tx["folder"])
    out = []
    for op in tx["ops"]:
        target = folder / op["name"]
        now = _sha(target) if target.is_file() else None
        if now != op.get("after_sha256"):
            out.append({"name": op["name"], "before_sha256": op.get("before_sha256"),
                        "after_sha256": op.get("after_sha256"), "now_sha256": now})
    return out


def restore_to_before(journal, tx_id, folder=None, confirm=False):
    """Put the folder back to its state BEFORE this transaction, even when a file was re-saved since
    Apply (the case rollback refuses). A file that existed before is copied back from the verified
    backup; a file the transaction created is deleted. Journals the action on the transaction.

    Without confirm, a changed file returns {needs_confirmation: true, changed: [...]} and writes
    nothing."""
    journal = Path(journal)
    tx = _load(journal, tx_id)
    folder = Path(folder or tx["folder"])
    changed = changed_since_apply(journal, tx_id, folder)
    if changed and not confirm:
        return {"tx_id": tx_id, "needs_confirmation": True, "changed": changed}
    before_snapshot = _snapshot(folder)
    backup = _tx_dir(journal, tx_id) / "backup"
    restored = []
    for op in tx["ops"]:
        target = folder / op["name"]
        before = op.get("before_sha256")
        if before is None:
            if target.exists():
                target.unlink()
                restored.append({"name": op["name"], "action": "deleted"})
            else:
                restored.append({"name": op["name"], "action": "absent"})
        else:
            src = backup / op["name"]
            if not src.is_file() or _sha(src) != before:
                raise RuntimeError("the backup of %s is missing or does not match its recorded hash" % op["name"])
            shutil.copy2(src, target)
            restored.append({"name": op["name"], "action": "restored_before"})
    tx["restore_to_before"] = {"utc": _now(), "changed": changed, "restored": restored,
                               "folder_before": before_snapshot, "folder_now": _snapshot(folder)}
    tx["state"] = "restored_before_apply"
    _save(journal, tx)
    return {"tx_id": tx_id, "state": tx["state"], "changed": changed, "restored": restored,
            "folder_now": _snapshot(folder)}


# ---------------------------------------------------------------- recovery
def recovery_scan(journal, folder=None):
    """READ ONLY: every unfinished transaction, assessed against the journal and the hashes on disk now: per file untouched / written / changed since, and the safe action."""
    out = []
    for tx in transactions(journal):
        if tx.get("state") not in BUSY_STATES:
            continue
        fold = Path(folder or tx["folder"])
        files = []
        for op in tx["ops"]:
            t = fold / op["name"]
            now = _sha(t) if t.is_file() else None
            before, after = op.get("before_sha256"), op["after_sha256"]
            status = ("untouched" if now == before else "written" if now == after else "changed since (not ours, not the original)")
            files.append({"name": op["name"], "status": status})
        out.append({"tx_id": tx["tx_id"], "state": tx["state"], "files": files, "error": tx.get("error"),
                    "safe_action": "rollback" if not any(f["status"].startswith("changed") for f in files) else "none: a file changed since; resolve it by hand"})
    return out


def recover(journal, tx_id, action="rollback", folder=None):
    if action != "rollback":
        raise LayoutTxRefused("the only recovery action is rollback")
    return rollback(journal, tx_id, folder)
