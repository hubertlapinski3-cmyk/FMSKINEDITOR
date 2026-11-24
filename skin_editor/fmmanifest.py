"""Read-only lookups in FM's build-verification manifest (fm_Data/manifest.dat).

manifest.dat (31,200 bytes in build 27.1) stores a WHOLE-FILE zlib CRC-32, little-endian, 4 bytes, for 589 of the 590
files under `aa\\` and for the game runtime binary. A stock file's CRC
is present; a modified bundle's CRC is not; 0 of 200,000 random 4-byte values were found in it.

What is NOT known: the full entry layout. The entries are 25 bytes, but only the CRC's presence and byte order are
established; the other 21 bytes per entry were never decoded, and no file-name-to-entry mapping is claimed. This module
therefore works by BYTE-SEQUENCE SEARCH and says so in every result (`method`): a match is a unique occurrence of the
file's whole-file CRC in the manifest bytes, not a decoded record, and an ambiguous match (two or more occurrences) is
reported as ambiguous, never resolved by picking one.

The verifier that consumes this manifest (SI.UnityBuildVerification.BuildVerifier) runs only with `--verify_build` on
the command line and feeds a crash-report attribute (Stage 3D addendum, static evidence). Nothing here modifies,
suppresses or bypasses any of it. This module NEVER writes to manifest.dat.
"""
import hashlib
import struct
import zlib
from pathlib import Path

PARSER_VERSION = 1
NOTE = ("search-based lookup: the 25-byte entry layout was not decoded (Stage 3D); a match is one occurrence of the "
        "whole-file CRC-32 in the manifest bytes, not a decoded record")


def path_for(aa_roots, profile=None):
    """manifest.dat lives one level above `aa` (in fm_Data). The profile's path when it has one, else derived."""
    if profile and profile.get("manifest_dat_path") and Path(profile["manifest_dat_path"]).is_file():
        return Path(profile["manifest_dat_path"])
    aa = Path(aa_roots[0])
    return aa.parent.parent / "manifest.dat"


def read(path):
    """Read manifest.dat READ ONLY. Returns {status, path, sha256, size, data, note, parser_version}.
    status: ok | missing (no manifest in this installation; the check is unsupported, not failed) | failed (unreadable)."""
    p = Path(path)
    try:
        data = p.read_bytes()
    except FileNotFoundError:
        return {"status": "missing", "reason": "manifest.dat was not found", "path": str(p), "sha256": None,
                "size": None, "data": None, "note": NOTE, "parser_version": PARSER_VERSION}
    except OSError as e:
        return {"status": "failed", "reason": "%s: %s" % (type(e).__name__, e), "path": str(p), "sha256": None,
                "size": None, "data": None, "note": NOTE, "parser_version": PARSER_VERSION}
    return {"status": "ok", "path": str(p), "sha256": hashlib.sha256(data).hexdigest(), "size": len(data),
            "data": data, "note": NOTE, "parser_version": PARSER_VERSION}


def lookup(manifest_data, file_bytes):
    """Does the manifest hold this file's WHOLE-FILE CRC-32? Returns {status, crc32, offset, occurrences, note}.
    status: manifest_match (exactly one occurrence) | manifest_entry_missing | manifest_entry_ambiguous.
    The uncompressed bundle CRC is never used here: this comparison is over the physical file's whole content."""
    if manifest_data is None:
        return {"status": "manifest_parse_unsupported", "crc32": None, "offset": None, "occurrences": 0, "note": NOTE}
    crc = zlib.crc32(file_bytes) & 0xFFFFFFFF
    needle = struct.pack("<I", crc)
    occurrences = manifest_data.count(needle)
    status = "manifest_match" if occurrences == 1 else ("manifest_entry_ambiguous" if occurrences > 1 else "manifest_entry_missing")
    return {"status": status, "crc32": "%08x" % crc,
            "offset": manifest_data.find(needle) if occurrences else None, "occurrences": occurrences, "note": NOTE}
