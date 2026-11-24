"""Read-only Addressables catalog reader (Stage 4E; evidence: docs/rea/STAGE-3B-CATALOG-ANALYSIS.md and the Stage 3C
offline patch report; scripts `docs/rea/evidence/stage-3b/decode_catalog.py`, `stage-3c/patch_catalog.py`).

What is known (Stage 3B, verified on sets A, B and C, decoded from the files and matched against the stock
Addressables 2.7.0 source):
  header   magic 0x0de38942 (bytes 42 89 e3 0d), u32 version 2, little-endian
  record   found STRUCTURALLY, never by byte search on sizes: an offset X (any byte alignment) starts a bundle
           record when u32[X+0x18] == X (the location's data pointer refers back to the record),
           u32[X+0x04] points at a length-prefixed 32-hex string (bundleNameId), u32[X+0x1c] at a length-prefixed
           location name and u32[X+0x20] at a length-prefixed internal id ending in .bundle
  fields   +0x08 u32 crc  = CRC-32 of the bundle's UNCOMPRESSED content (0 = none stored; verified 534/534 on set C)
           +0x0c u32 size = bundle file size (verified 534/534 on set C)
           +0x10 u32 commonId pointer, +0x14 u32 pointer (unresolved), +0x1c primary key, +0x20 internal id,
           +0x24.. tail (not decoded); strings are u32 length at pointer-4, bytes at the pointer (absolute offsets)
What is NOT known: the rest of the catalog (header pointers past byte 8, key and location tables, any catalog-wide
checksum), the +0x14 field's meaning, the record tail. `catalog.hash` derivation is unknown (Stage 3C).

This module NEVER writes a catalog. Catalog patching is design-only (the Stage 4E report, section on catalog patching);
no write path exists in this code. A malformed record is skipped and counted, and the scan of the rest of the catalog
continues; a catalog whose header is not the known one is reported `unsupported`, never guessed.
"""
import hashlib
import re
import struct
import time
from pathlib import Path

PARSER_VERSION = 1
FORMAT = "addressables-catalog/2 anchor-scan"
MAGIC = 0x0DE38942
VERSION = 2
MAX_STRING = 1000                       # the longest catalog string seen in the evidence is a few hundred bytes
_HEX32 = re.compile(rb"^[0-9a-f]{32}$")

# catalog_crc_status values, and what each one asserts
CRC_STATUSES = ("catalog_crc_match", "catalog_crc_mismatch", "catalog_crc_stored_zero", "catalog_record_missing",
                "catalog_record_ambiguous", "crc_not_calculated", "crc_calculation_failed",
                "catalog_parse_unsupported", "catalog_parse_failed", "catalog_identity_stale", "not_checked")


def _now():
    return time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())


def _sstr(b, ptr):
    """The length-prefixed string at an absolute pointer, or None when the pointer is out of range or the length is
    implausible. Never raises: an unreadable string disqualifies a record candidate, not the catalog."""
    if ptr < 4 or ptr + 4 > len(b):
        return None
    n = struct.unpack_from("<I", b, ptr - 4)[0]
    if n > MAX_STRING or ptr + n > len(b):
        return None
    return b[ptr:ptr + n]


def parse_catalog_bytes(b):
    """The pure parser: header check, structural record scan, typed record dicts. Returns the index dict; never raises.
    One malformed candidate is counted and skipped (`rejected`); the scan continues (record-level isolation). A catalog
    whose header is not the known magic/version is `unsupported`, and a too-short file is `failed` - in both cases no
    records are returned rather than a guess."""
    if len(b) < 8:
        return {"status": "failed", "reason": "the catalog is shorter than its 8-byte header", "records": [], "rejected": 0}
    magic, version = struct.unpack_from("<II", b, 0)
    if magic != MAGIC:
        return {"status": "unsupported", "reason": "unknown catalog magic 0x%08x (expected 0x%08x)" % (magic, MAGIC),
                "records": [], "rejected": 0}
    if version != VERSION:
        return {"status": "unsupported", "reason": "unsupported catalog version %d (expected %d)" % (version, VERSION),
                "records": [], "rejected": 0}
    records, rejected = [], 0
    last = len(b) - 0x30
    for x in range(8, last):
        if int.from_bytes(b[x + 0x18:x + 0x1c], "little") != x:          # the structural anchor: u32[X+0x18] == X
            continue
        rec = _record(b, x)
        if rec is None:
            rejected += 1                                              # anchor held but the record did not decode: skip it, keep scanning
            continue
        records.append(rec)
    return {"status": "ok", "format": FORMAT, "parser_version": PARSER_VERSION,
            "header": {"magic": "%08x" % magic, "version": version}, "records": records, "rejected": rejected}


def _record(b, x):
    """One record at a validated anchor, with every field the evidence established, and the raw fields preserved."""
    u = lambda o: struct.unpack_from("<I", b, o)[0]
    name32, key, iid = _sstr(b, u(x + 4)), _sstr(b, u(x + 0x1c)), _sstr(b, u(x + 0x20))
    if name32 is None or not _HEX32.match(name32) or key is None or iid is None or not iid.endswith(b".bundle"):
        return None
    common = None
    cptr = u(x + 0x10)
    if cptr and cptr + 8 <= len(b):
        timeout, redirect, retry, flags = struct.unpack_from("<hBBI", b, cptr)
        common = {"timeout": timeout, "redirect_limit": redirect, "retry_count": retry, "flags": flags}
    crc = u(x + 8)
    return {"offset": x, "bundle_name32": name32.decode(), "crc": crc, "crc_hex": "%08x" % crc,
            "size": u(x + 0xc), "primary_key": key.decode("utf-8", "replace"),
            "internal_id": iid.decode("utf-8", "replace"), "file": iid.decode("utf-8", "replace").rsplit("\\", 1)[-1],
            "common": common,
            "raw": {"hash_ptr": u(x), "bundle_name_ptr": u(x + 4), "common_ptr": cptr, "f5": u(x + 0x14),
                    "self_ptr": u(x + 0x18), "tail": [u(x + 0x24 + 4 * k) for k in range(6)]},
            "not_decoded": ["+0x00 hashId (Hash128, all zero in sets A/B/C)", "+0x14 pointer", "+0x24.. tail",
                            "catalog header past byte 8, key and location tables"]}


def read(path):
    """Parse one catalog.bin file READ ONLY. Returns the index dict plus the file identity (sha256, size, path)."""
    p = Path(path)
    try:
        b = p.read_bytes()
    except OSError as e:
        return {"status": "failed", "reason": "%s: %s" % (type(e).__name__, e), "records": [], "rejected": 0,
                "path": str(p), "sha256": None, "size": None}
    idx = parse_catalog_bytes(b)
    idx.update(path=str(p), sha256=hashlib.sha256(b).hexdigest(), size=len(b))
    return idx


def by_file(index):
    """{filename: [records]} of a parsed index. A file with several records stays a list of several records;
    nothing is silently selected."""
    out = {}
    for r in index.get("records") or []:
        out.setdefault(r["file"], []).append(r)
    return out


def resolve(index, filename):
    """The records for one bundle FILE name. Status: found (exactly one record), missing, ambiguous (two or more
    records name the same file - all kept, never one picked). Uses the parsed index or a prebuilt by_file map."""
    recs = (index if isinstance(index, dict) and "records" in index else {}).get("records")
    if recs is None and isinstance(index, dict):
        recs = index.get(filename)          # a by_file map: the list is the answer
        return {"status": ("found" if len(recs) == 1 else "ambiguous") if recs else "missing", "records": recs or []}
    matching = [r for r in recs or [] if r["file"] == filename]
    return {"status": ("found" if len(matching) == 1 else "ambiguous") if matching else "missing", "records": matching}


def catalog_crc_status(record_status, stored_crc, actual_crc):
    """The comparison status for one bundle. Kept SEPARATE from the record lookup: an ambiguous record is never a
    CRC match, a missing record is never a match, and a stored zero is its own state (0 means 'no CRC stored',
    Stage 3B sets A/B), never a mismatch."""
    if record_status == "missing":
        return "catalog_record_missing"
    if record_status == "ambiguous":
        return "catalog_record_ambiguous"
    if record_status == "found":
        if stored_crc == 0:
            return "catalog_crc_stored_zero"
        if actual_crc is None:
            return "crc_not_calculated"
        return "catalog_crc_match" if int(stored_crc) == int(actual_crc) else "catalog_crc_mismatch"
    return "not_checked"


# ---------------------------------------------------------------- installation annotation (READ ONLY)
def catalog_path_for(aa_roots, profile=None):
    """The catalog.bin of an installation: the profile's path when it has one, else `aa/catalog.bin`."""
    if profile and profile.get("catalog_path") and Path(profile["catalog_path"]).is_file():
        return Path(profile["catalog_path"])
    return Path(aa_roots[0]) / "catalog.bin"


def annotate(registry, aa_roots, profile=None, progress=None, cancel=None, only=None):
    """Fill the 4B placeholders (catalog, catalog_crc_status, manifest, manifest_status) of every inventoried bundle,
    READ ONLY: the catalog and manifest are read once, each bundle file is read once more for its WHOLE-file CRC (no
    UnityPy parse, no bundle reparse), and the only writes are registry columns. Incremental: a bundle whose recorded
    annotation used the same catalog and manifest identity and whose sha256 is unchanged is kept as is.
    Returns the summary with the per-status counts."""
    from . import fmmanifest
    progress = progress or (lambda m, f: None)
    cancel = cancel or (lambda: False)
    cat = read(catalog_path_for(aa_roots, profile))
    man = fmmanifest.read(fmmanifest.path_for(aa_roots, profile))
    by = by_file(cat)
    identity = {"catalog_sha256": cat.get("sha256"), "manifest_sha256": man.get("sha256")}
    previous = registry.get_integrity_meta()
    fresh_identity = previous and previous.get("catalog_sha256") == identity["catalog_sha256"] \
        and previous.get("manifest_sha256") == identity["manifest_sha256"]
    counts, done, skipped, files = {}, 0, 0, registry.all_bundles()
    todo = {k: v for k, v in files.items() if v["state"] in ("valid", "partially_valid")} if not only \
        else {k: files[k] for k in only if files.get(k, {}).get("state") in ("valid", "partially_valid")}
    t0 = time.time()
    for i, (rel, rec) in enumerate(sorted(todo.items())):
        if cancel():
            return _annotate_summary(counts, skipped, cat, man, done, time.time() - t0, cancelled=True)
        progress("%s (%d of %d)" % (rel, i + 1, len(todo)), i / max(1, len(todo)))
        old_cat, old_man = rec.get("catalog"), rec.get("manifest")
        if fresh_identity and old_cat and "resolution" in old_cat and old_man and old_man.get("file_sha256") == rec["sha256"]:
            skipped += 1                                                # same catalog, same manifest, same file bytes: keep the annotation
            _bump(counts, "catalog", rec.get("catalog_crc_status"))
            _bump(counts, "manifest", rec.get("manifest_status"))
            continue
        path = Path(rec["abs_path"])
        row = {"catalog": None, "catalog_crc_status": "catalog_parse_failed", "manifest": None, "manifest_status": "manifest_parse_failed"}
        if cat["status"] != "ok":
            row["catalog"] = {"found": False, "parse_status": cat["status"], "reason": cat.get("reason")}
            row["catalog_crc_status"] = "catalog_parse_unsupported" if cat["status"] == "unsupported" else "catalog_parse_failed"
        else:
            r = resolve(by, Path(rel).name)
            stored = r["records"][0] if r["status"] == "found" else None
            row["catalog"] = {"found": r["status"] == "found", "resolution": r["status"], "offset": stored and stored["offset"],
                              "crc": stored and stored["crc"], "crc_hex": stored and stored["crc_hex"],
                              "size": stored and stored["size"], "bundle_name32": stored and stored["bundle_name32"],
                              "candidates": [c["offset"] for c in r["records"]]}
            row["catalog_crc_status"] = catalog_crc_status(r["status"], stored and stored["crc"],
                                                           int(rec["crc32"], 16) if rec.get("crc32") else None)
        row["manifest"] = {"found": False}
        if man["status"] == "ok":
            try:
                data = path.read_bytes()
                import zlib
                wcrc = zlib.crc32(data) & 0xFFFFFFFF
                look = fmmanifest.lookup(man["data"], data)
                row["manifest"] = dict(look, found=look["status"] == "manifest_match", crc32="%08x" % wcrc,
                                       file_sha256=rec["sha256"],
                                       scope="manifest.dat covers 589 of the 590 aa files (Stage 3D); bundles are in scope")
                row["manifest_status"] = look["status"]
            except OSError as e:
                row["manifest"] = {"found": False, "reason": "%s: %s" % (type(e).__name__, e)}
                row["manifest_status"] = "manifest_parse_failed"
        else:
            row["manifest"] = {"found": False, "parse_status": man["status"], "reason": man.get("reason")}
            row["manifest_status"] = "manifest_parse_unsupported" if man["status"] in ("missing", "unsupported") else "manifest_parse_failed"
        registry.set_integrity(rel, row["catalog"], row["catalog_crc_status"], row["manifest"], row["manifest_status"])
        _bump(counts, "catalog", row["catalog_crc_status"])
        _bump(counts, "manifest", row["manifest_status"])
        done += 1
    registry.set_integrity_meta(identity, _now())
    out = _annotate_summary(counts, skipped, cat, man, done, time.time() - t0, cancelled=False)
    progress("done", 1.0)
    return out


def _annotate_summary(counts, skipped, cat, man, done, seconds, cancelled):
    return {"annotated": done, "skipped_fresh": skipped, "cancelled": cancelled,
            "catalog": {"path": cat.get("path"), "sha256": cat.get("sha256"), "size": cat.get("size"),
                        "status": cat["status"], "reason": cat.get("reason"), "records": len(cat.get("records") or []),
                        "rejected_records": cat.get("rejected", 0)},
            "manifest": {"path": man.get("path"), "sha256": man.get("sha256"), "size": man.get("size"),
                         "status": man["status"], "reason": man.get("reason"),
                         "method": man.get("note")},
            "catalog_crc_status": counts.get("catalog", {}), "manifest_status": counts.get("manifest", {}),
            "seconds": round(seconds, 2)}


def _bump(counts, kind, status):
    counts.setdefault(kind, {})
    if status:
        counts[kind][status] = counts[kind].get(status, 0) + 1


# ---------------------------------------------------------------- one bundle's unified record (section 8)
def integrity_bundle(registry, rel, profile=None, aa_roots=None):
    """The unified integrity record of one inventoried bundle: every hash named for what it is, the catalog lookup
    result kept separate from the CRC comparison, the manifest result separate from both, parser versions and a
    checked timestamp. Read only."""
    from . import fmmanifest
    rec = registry.get_bundle(rel)
    if rec is None:
        raise KeyError("no such inventory bundle: " + rel)
    out = {"bundle": rel, "checked_utc": _now(),
           "parsers": {"catalog": "%s v%d" % (FORMAT, PARSER_VERSION), "crc": "bundles.crc32_of_env (zlib, uncompressed nodes)"},
           "diagnostics": []}
    if profile:
        out["source_installation"] = {"install_id": profile.get("install_id"), "game_build": profile.get("game_build"),
                                      "catalog_sha256_profile": profile.get("catalog_sha256")}
        cat = read(catalog_path_for(aa_roots or profile.get("aa_roots", []), profile))
        if cat.get("sha256") and profile.get("catalog_sha256") and cat["sha256"] != profile["catalog_sha256"]:
            out["diagnostics"].append("the catalog on disk is not the one the installation profile recorded "
                                      "(profile %s, disk %s): the comparison is against the CURRENT catalog, and the "
                                      "profile is stale" % (profile.get("catalog_sha256")[:8] + "...", cat["sha256"][:8] + "..."))
        r = resolve(cat, Path(rel).name)
        stored = r["records"][0] if r["status"] == "found" else None
        out["catalog"] = {"resolution": r["status"], "offset": stored and stored["offset"],
                          "stored_crc32": stored and stored["crc_hex"], "stored_size": stored and stored["size"],
                          "catalog_sha256": cat.get("sha256"),
                          "comparison": catalog_crc_status(r["status"], stored and stored["crc"],
                                                            int(rec["crc32"], 16) if rec.get("crc32") else None)}
    else:
        out["source_installation"] = None
        out["catalog"] = rec.get("catalog") or {}
        out["catalog"]["comparison"] = rec.get("catalog_crc_status") or "not_checked"
    out["hashes"] = {
        "source_file_sha256": rec.get("sha256"),
        "source_uncompressed_crc32": rec.get("crc32"),
        "physical_file_crc32": None, "physical_file_crc32_status": None,
        "catalog_stored_crc32": (rec.get("catalog") or {}).get("crc_hex"),
        "manifest_stored_crc32": (rec.get("manifest") or {}).get("crc32"),
        "names": {"source_file_sha256": "SHA-256 over the physical bundle file",
                  "physical_file_crc32": "CRC-32 over the physical bundle file (what manifest.dat stores)",
                  "source_uncompressed_crc32": "CRC-32 over the bundle's uncompressed content (what the catalog stores)",
                  "catalog_stored_crc32": "the CRC-32 field of the catalog record",
                  "manifest_stored_crc32": "the whole-file CRC-32 found in manifest.dat"}}
    man = rec.get("manifest") or {}
    out["hashes"]["physical_file_crc32"] = man.get("crc32")
    out["hashes"]["physical_file_crc32_status"] = man.get("status")
    out["manifest_dat"] = {"entry_status": rec.get("manifest_status"), "found": man.get("found"),
                           "stored_crc32": man.get("crc32"), "note": man.get("note"),
                           "scope": man.get("scope")}
    if not rec.get("catalog_crc_status"):
        out["diagnostics"].append("this bundle has not been annotated yet: run the catalog check to fill the catalog "
                                  "and manifest columns")
    return out
