"""Read-only bundle inventory and asset index (Stage 4B; docs/rea/STAGE-4A-ARCHITECTURE.md sections 6.2 and 6.3).

`scan` walks the platform folder of an installation profile, records every `*.bundle` (size, mtime, SHA-256, uncompressed CRC-32, CAB, Unity version, object and
type counts, bundle dependencies, externals) and indexes its assets (lightweight rows: no typetree except the AssetBundle object, and the panel descriptions of a
panel-id bundle) into the registry. It never writes to the game folder: files are opened for reading only, and the only writes are to the registry database.

Incremental: a bundle whose size and mtime are unchanged AND whose record was verified (hashed) within `max_unverified_days` is reused as is; with `verify=True`
every file is hashed again. A file whose hash is unchanged keeps its parsed record. Modification time is only ever a hint to skip work, never proof of integrity.

One failing bundle is recorded with state `corrupt` or `unsupported` and an error text; the scan continues. A cancel request is honoured between bundles: the
bundles already stored stay stored (each one is written in one transaction), the scan is recorded as `cancelled`."""
import calendar
import os
import re
import time
from collections import Counter
from pathlib import Path

from . import bundles

GUID = re.compile(r"^[0-9a-f]{32}$")
SOURCE_STATES = ("unscanned", "scanning", "valid", "partially_valid", "unsupported", "corrupt", "missing")


class ScanCancelled(Exception):
    """Raised inside `scan` when the cancel callable returns true; carries the partial summary."""

    def __init__(self, summary):
        super().__init__("scan cancelled")
        self.summary = summary


def _now():
    return time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())


def kind_of(filename):
    """A coarse classification from the file name (HEURISTIC: the game does not publish one). 'art-characters_assets_all.bundle' -> 'art-characters'; 'ui-styles_assets_default' -> 'ui-styles'."""
    stem = filename[:-len(".bundle")] if filename.endswith(".bundle") else filename
    head = stem.split("_assets_")[0].split("_scenes_")[0]
    return head if head != stem else stem.split("_")[0]


def list_bundle_files(aa_roots):
    """[(rel_path with forward slashes, absolute Path)] of every `*.bundle` under the roots, sorted. Symlinks are not followed."""
    out = []
    for root in aa_roots:
        root = Path(root)
        for base, dirs, files in os.walk(root, followlinks=False):
            dirs.sort()
            for f in sorted(files):
                if f.endswith(".bundle"):
                    p = Path(base) / f
                    out.append((p.relative_to(root).as_posix(), p))
    return out


def _peek(obj):
    try:
        return obj.peek_name()
    except Exception:
        return None


def inspect_bundle(path, rel):
    """Open one bundle read-only and describe it. Returns (record, asset_rows). Never raises: a failure gives a record with state corrupt/unsupported and `error`."""
    path = Path(path)
    st = path.stat()
    rec = {"rel_path": rel, "abs_path": str(path), "filename": path.name, "size": st.st_size, "mtime_ns": st.st_mtime_ns, "kind": kind_of(path.name),
           "state": "scanning", "error": None, "catalog": None, "catalog_crc_status": "not_checked", "manifest": None, "manifest_status": "not_checked"}
    rec["sha256"] = bundles.sha256(path)
    header = bundles.bundle_header(path)
    if header is None:
        rec.update(state="unsupported", error="not a UnityFS bundle (header not recognised)")
        return rec, []
    rec["unity_version"] = header["unity_revision"]
    try:
        env = bundles.open_readonly(path)
        rec["crc32"] = "%08x" % bundles.crc32_of_env(env)
        sfiles = [(name, sf) for name, sf in env.file.files.items() if hasattr(sf, "objects")]
        if not sfiles:
            rec.update(state="unsupported", error="no serialized file inside the bundle")
            return rec, []
        rec["cab"] = sfiles[0][0]
        rows, counts, errors = [], Counter(), 0
        guid_of, container_of, deps, externals = {}, {}, [], []
        for cab, sf in sfiles:
            externals += [e.path for e in getattr(sf, "externals", [])]
            for pid, obj in sf.objects.items():
                tname = obj.type.name
                counts[tname] += 1
                row = {"cab": cab, "path_id": str(pid), "class_id": int(obj.class_id), "type": tname, "name": _peek(obj)}
                if tname == "AssetBundle":
                    try:
                        t = obj.read_typetree()
                        deps = list(t.get("m_Dependencies") or [])
                        for key, ent in t.get("m_Container") or []:
                            a = (ent or {}).get("asset") or {}
                            if a.get("m_FileID") == 0:
                                if GUID.match(str(key)):
                                    guid_of[(cab, str(a.get("m_PathID")))] = str(key)
                                else:
                                    container_of[(cab, str(a.get("m_PathID")))] = str(key)
                    except Exception:
                        errors += 1
                rows.append(row)
        panel = "panelids" in path.name
        for row in rows:
            k = (row["cab"], row["path_id"])
            row["guid"] = guid_of.get(k)
            row["container"] = container_of.get(k)
            row.setdefault("ref_guid", None)
            row.setdefault("panel_id", None)
        if panel:
            sf_by_cab = dict(sfiles)
            for row in rows:
                if row["type"] != "MonoBehaviour":
                    continue
                try:
                    t = sf_by_cab[row["cab"]].objects[int(row["path_id"])].read_typetree()
                except Exception:
                    errors += 1
                    continue
                if isinstance(t, dict) and "m_id" in t and isinstance(t.get("m_panelDescription"), dict):
                    row["panel_id"] = str(t["m_id"])
                    uxml = (t["m_panelDescription"].get("uxml") or {}).get("m_AssetGUID")
                    if uxml:
                        row["ref_guid"] = str(uxml).lower()
        rec.update(object_count=len(rows), type_counts=dict(counts), dependencies=deps, externals=externals,
                   state="partially_valid" if errors else "valid", error=("%d object(s) could not be read for the index" % errors) if errors else None)
        return rec, rows
    except Exception as e:                      # one failing bundle never stops the scan
        rec.update(state="corrupt", error="%s: %s" % (type(e).__name__, e))
        return rec, []


def scan(registry, aa_roots, verify=False, max_unverified_days=7, progress=None, cancel=None):
    """Inventory every bundle under `aa_roots` into `registry`. progress(message, fraction 0..1), cancel() -> bool. Returns the summary; raises ScanCancelled
    (with the partial summary) when cancelled. The game folder is only read."""
    progress = progress or (lambda m, f: None)
    cancel = cancel or (lambda: False)
    files = list_bundle_files(aa_roots)
    total_bytes = sum(p.stat().st_size for _, p in files) or 1
    known = registry.all_bundles()
    mode = "verify" if verify else "quick"
    scan_id = registry.begin_scan(mode)
    t0 = time.time()
    summary = {"scan_id": scan_id, "mode": mode, "files": len(files), "reused": 0, "new": 0, "changed": 0, "rehashed_unchanged": 0, "missing": 0, "errors": 0, "states": {}, "seconds": 0.0}
    done = 0
    cutoff = time.time() - max_unverified_days * 86400

    def finish(state):
        summary["seconds"] = round(time.time() - t0, 2)
        registry.finish_scan(scan_id, state, summary)

    try:
        for i, (rel, path) in enumerate(files):
            if cancel():
                finish("cancelled")
                raise ScanCancelled(dict(summary, state="cancelled"))
            progress("%s (%d of %d)" % (rel, i + 1, len(files)), done / total_bytes)
            st = path.stat()
            old = known.get(rel)
            fresh = (old and old["state"] in ("valid", "partially_valid") and old["size"] == st.st_size and old["mtime_ns"] == st.st_mtime_ns
                     and _recent(old.get("verified_utc"), cutoff))
            if fresh and not verify:
                summary["reused"] += 1
                summary["states"][old["state"]] = summary["states"].get(old["state"], 0) + 1
                done += st.st_size
                continue
            if old and old["state"] in ("valid", "partially_valid") and old["size"] == st.st_size and bundles.sha256(path) == old["sha256"]:
                old.update(mtime_ns=st.st_mtime_ns, verified_utc=_now(), abs_path=str(path))   # same bytes: keep the parsed record and its assets
                registry.put_bundle(old)
                summary["rehashed_unchanged"] += 1
                summary["states"][old["state"]] = summary["states"].get(old["state"], 0) + 1
                done += st.st_size
                continue
            rec, rows = inspect_bundle(path, rel)
            rec["scanned_utc"] = rec["verified_utc"] = _now()
            registry.put_bundle(rec, rows)
            summary["new" if old is None else "changed"] += 1
            if rec["state"] not in ("valid", "partially_valid"):
                summary["errors"] += 1
            summary["states"][rec["state"]] = summary["states"].get(rec["state"], 0) + 1
            done += st.st_size
        gone = registry.mark_missing({rel for rel, _ in files})
        summary["missing"] = len(gone)
        if gone:
            summary["states"]["missing"] = len(gone)
        progress("done", 1.0)
        finish("done")
    except ScanCancelled:
        raise
    except Exception:
        finish("failed")
        raise
    return summary


def _recent(verified_utc, cutoff):
    if not verified_utc:
        return False
    try:
        return calendar.timegm(time.strptime(verified_utc, "%Y%m%dT%H%M%SZ")) >= cutoff
    except ValueError:
        return False
