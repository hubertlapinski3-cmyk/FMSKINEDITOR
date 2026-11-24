"""The schema 2 build manifest (Stage 4D; docs/rea/STAGE-4A-ARCHITECTURE.md section 6.8; the integrity sections were
added in Stage 4E from the read-only catalog reader catalog.py and the manifest.dat reader fmmanifest.py).

Two files, one truth:
  package.json   the install manifest. Schema 2 KEEPS every schema 1 field unchanged (id, project, built_utc,
                 game_build, profile, catalog_hash, plan_digest, plan, files, gate, installable) and adds the
                 schema 2 sections (target, edits, outputs, tools, overrides). A schema 1 package stays readable
                 (read_package accepts both; install reads the build report either way).
  build-manifest.json   the full build record written next to it: per-edit adapter ops, validation findings,
                 overrides, per-output hashes + uncompressed CRC-32 + the three-layer diff + the catalog and
                 manifest.dat integrity sections, the dependency impact with buildability and installation
                 readiness reported separately.

Integrity rule (Stage 4E): the catalog comparison is against the SOURCE installation's catalog (never another
build's), the manifest comparison is the OUTPUT's whole-file CRC against the ORIGINAL file's manifest entry, and a
stale catalog identity is its own recorded state, never a silent comparison. A CRC mismatch is reported honestly and
is never a build failure: buildability and installation readiness are separate states (the game logged a CRC mismatch
and still used the bundle in the ONE tested scenario, Stage 3G - observed, not guaranteed).

The `installs` array is written EMPTY by the build and filled by the installer (Stage 4F); it is reserved here so the
shape is stable. No game file, catalog or manifest.dat is ever touched by anything in this module.
"""
import json
import platform
import time
import zlib
from pathlib import Path

from . import adapters, bundles, bundlediff

SCHEMA = 2


def _now():
    return time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())


def integrity_sources(profile=None):
    """Parse the SOURCE installation's catalog.bin and manifest.dat once for a build (read only). None when no
    installation profile is selected: the build then records 'not checked' rather than comparing against nothing."""
    if not profile:
        return None
    from . import catalog, fmmanifest
    aa = profile.get("aa_roots") or []
    cat = catalog.read(catalog.catalog_path_for(aa, profile))
    man = fmmanifest.read(fmmanifest.path_for(aa, profile))
    return {"catalog": cat, "manifest": man, "install_id": profile.get("install_id"),
            "game_build": profile.get("game_build"),
            "catalog_sha256_profile": profile.get("catalog_sha256"),
            "catalog_identity_stale": bool(profile.get("catalog_sha256") and cat.get("sha256")
                                           and profile["catalog_sha256"] != cat["sha256"])}


def _output_integrity(vanilla_path, built_path, sources, out_crc_hex):
    """The integrity section of one output bundle (Stage 4E brief section 9): the catalog lookup kept separate from
    the CRC comparison, the manifest.dat comparison over the PHYSICAL file's whole content, every value named for what
    it is, parser versions, a checked timestamp, and honest statuses wherever something could not be established."""
    from . import catalog, fmmanifest
    sec = {"checked_utc": _now(),
           "parsers": {"catalog": "%s v%d" % (catalog.FORMAT, catalog.PARSER_VERSION),
                       "manifest_dat": "search-based v%d (25-byte entry layout not decoded, Stage 3D)" % fmmanifest.PARSER_VERSION,
                       "crc": "bundles.crc32_of_env (zlib over the uncompressed serialized-data nodes)"},
           "source_installation": {"install_id": sources.get("install_id"), "game_build": sources.get("game_build")},
           "diagnostics": []}
    cat = sources["catalog"]
    if cat["status"] != "ok":
        sec["catalog"] = {"comparison": "catalog_parse_unsupported" if cat["status"] == "unsupported" else "catalog_parse_failed",
                          "reason": cat.get("reason"), "catalog_sha256": cat.get("sha256")}
    else:
        r = catalog.resolve(cat, Path(vanilla_path).name)
        stored = r["records"][0] if r["status"] == "found" else None
        comparison = catalog.catalog_crc_status(r["status"], stored and stored["crc"], int(out_crc_hex, 16))
        if sources.get("catalog_identity_stale"):
            sec["diagnostics"].append("the catalog on disk is not the one the installation profile recorded (profile "
                                      "%s, disk %s): the comparison is against the CURRENT catalog" %
                                      (sources.get("catalog_sha256_profile") or "?", cat["sha256"]))
            comparison = "catalog_identity_stale"
        sec["catalog"] = {"resolution": r["status"], "record_offset": stored and stored["offset"],
                          "stored_crc32": stored and stored["crc_hex"], "stored_size": stored and stored["size"],
                          "bundle_name32": stored and stored["bundle_name32"],
                          "candidates": [c["offset"] for c in r["records"]],
                          "catalog_sha256": cat["sha256"], "comparison": comparison}
        if comparison == "catalog_crc_mismatch":
            sec["catalog"]["note"] = ("the catalog is never patched (owner decision D5): Unity logs a CRC mismatch for "
                                     "this file and, in the one tested build and scenario (27.1.0.2505117, one composition "
                                     "edit, Stage 3G), still loaded the modified bundle - observed, not guaranteed; the "
                                     "exact retry path was not observed")
        elif comparison == "catalog_crc_stored_zero":
            sec["catalog"]["note"] = "this catalog generation stores no CRC for the bundle (field 0): nothing to compare"
        elif comparison in ("catalog_record_missing", "catalog_record_ambiguous"):
            sec["catalog"]["note"] = "no unique catalog record for this bundle: the CRC comparison is not a match"
    man = sources["manifest"]
    if man["status"] != "ok":
        sec["manifest_dat"] = {"comparison": "manifest_parse_unsupported" if man["status"] in ("missing", "unsupported")
                               else "manifest_parse_failed", "reason": man.get("reason"), "manifest_sha256": man.get("sha256")}
    else:
        src_bytes = Path(vanilla_path).read_bytes()
        src_wcrc = zlib.crc32(src_bytes) & 0xFFFFFFFF
        out_wcrc = zlib.crc32(Path(built_path).read_bytes()) & 0xFFFFFFFF
        look = fmmanifest.lookup(man["data"], src_bytes)
        entry = {"entry_status": look["status"], "manifest_sha256": man["sha256"], "note": look["note"],
                 "source_whole_file_crc32": "%08x" % src_wcrc, "output_whole_file_crc32": "%08x" % out_wcrc}
        if look["status"] == "manifest_match":
            entry["stored_crc32"] = look["crc32"]
            entry["comparison"] = "manifest_match" if src_wcrc == out_wcrc else "manifest_mismatch"
            if entry["comparison"] == "manifest_mismatch":
                entry["mismatch_note"] = ("expected for any modified bundle: the manifest entry is the ORIGINAL file's "
                                          "whole-file CRC and was never updated; Stage 3D found the verifier only runs "
                                          "with --verify_build and feeds a crash-report attribute (static evidence, not a "
                                          "runtime observation)")
        elif look["status"] == "manifest_entry_missing":
            entry["comparison"] = "manifest_entry_missing"
            entry["note"] += ("; the SOURCE file's whole-file CRC is not in the manifest, so the original entry cannot "
                              "be established and nothing about the output is claimed")
        else:
            entry["comparison"] = "manifest_entry_ambiguous"
        sec["manifest_dat"] = entry
    return sec


def output_record(vanilla_path, built_path, semantic=None, reg=None, sources=None):
    """One output bundle: source and output hashes, uncompressed CRC-32 (the value the Addressables catalog holds,
    Stage 3B), the three-layer diff, and the integrity section against the SOURCE installation's catalog and
    manifest.dat when a profile was given (else the registry's recorded catalog status, else not checked). A file that
    is not a UnityFS bundle (only possible in synthetic fixtures) records hashes and a note, never a crash."""
    rec = {"rel_path": Path(built_path).name,
           "source_sha256": bundles.sha256(vanilla_path), "output_sha256": bundles.sha256(built_path),
           "source_crc32": None, "output_crc32": None, "diff": None, "semantic": semantic or {},
           "catalog_crc_status": None, "manifest_status": None, "integrity": None}
    if bundles.bundle_header(vanilla_path) is None or bundles.bundle_header(built_path) is None:
        rec["note"] = "not a UnityFS bundle: hashes only, no CRC or structural diff"
        return rec
    rec["source_crc32"] = "%08x" % bundles.crc32_uncompressed(vanilla_path)
    rec["output_crc32"] = "%08x" % bundles.crc32_uncompressed(built_path)
    rec["diff"] = bundlediff.compare(vanilla_path, built_path)
    if sources is not None:
        rec["integrity"] = _output_integrity(vanilla_path, built_path, sources, rec["output_crc32"])
        rec["catalog_crc_status"] = (rec["integrity"].get("catalog") or {}).get("comparison")
        rec["manifest_status"] = (rec["integrity"].get("manifest_dat") or {}).get("comparison")
    elif reg is not None:
        b = reg.get_bundle(rec["rel_path"])
        if b and (b.get("catalog") or {}).get("found"):
            cat = b["catalog"]
            rec["catalog_crc_status"] = ("catalog_crc_mismatch" if cat.get("crc") and int(cat["crc"], 16) != int(rec["output_crc32"], 16)
                                         else "catalog_crc_match")
            rec["catalog_record"] = {"bundle_name": cat.get("bundle_name32"), "crc": cat.get("crc"), "size": cat.get("size")}
            rec["catalog_note"] = ("the catalog is never patched (owner decision D5): Unity logs a CRC mismatch for this "
                                   "file and, in the tested build and scenario (27.1.0.2505117, one composition edit), still "
                                   "loaded the modified bundle - observed, not guaranteed (Stage 3G)")
        if b and b.get("manifest_status"):
            rec["manifest_status"] = b["manifest_status"]
    return rec


def edits_section(plan):
    """The manifest's per-edit records, straight from the typed plan (adapters, ops, validation, impact, evidence)."""
    out = []
    for bundle, rec in sorted(plan.get("bundles", {}).items()):
        for op in rec.get("ops", []):
            out.append({"asset": op.get("asset"), "bundle": bundle, "adapter": {"name": op.get("adapter"), "version": op.get("adapter_version")},
                        "adapter_evidence": op.get("evidence"), "edit_kind": op.get("edit_kind"), "ops": op.get("ops"),
                        "validation": op.get("validation", []), "dependencies": op.get("impact", {}),
                        "build_step": op.get("build_step")})
    return out


def build_manifest(ws, project, plan, report, out_dir, ts, reg=None, profile=None, semantics=None):
    """Assemble the schema 2 manifest of one finished build. `report` is patcher.build's report; `semantics` is
    {bundle: what the pipeline knows about its edits} (tile notes, image notes, sheet counts). The game folder is read
    ONLY for the integrity section when an installation profile is given (the catalog and manifest.dat, read only);
    the vanilla snapshot is the source of every source_* hash."""
    man = ws.vanilla_manifest() or {}
    prof = profile or {}
    semantics = semantics or {}
    sources = integrity_sources(profile)
    target = {"game_build": man.get("game_build") or prof.get("game_build"), "install_id": prof.get("install_id"),
              "unity_version": prof.get("unity_version"), "build_id": prof.get("build_id"),
              "catalog_sha256": prof.get("catalog_sha256"), "catalog_hash_sha256": prof.get("catalog_hash_sha256"),
              "manifest_dat_sha256": prof.get("manifest_dat_sha256"),
              "catalog_hash_of_snapshot": (man.get("reference") or {}).get("catalog_hash")}
    outputs = []
    for name, f in sorted(report.get("files", {}).items()):
        if not f.get("changed"):
            continue
        outputs.append(output_record(ws.vanilla / name, Path(out_dir) / name, semantics.get(name), reg, sources))
    integrity_sources_rec = None
    if sources is not None:
        cat, mdat = sources["catalog"], sources["manifest"]
        integrity_sources_rec = {
            "install_id": sources.get("install_id"), "game_build": sources.get("game_build"),
            "catalog": {"path": cat.get("path"), "sha256": cat.get("sha256"), "size": cat.get("size"),
                        "status": cat["status"], "reason": cat.get("reason"),
                        "records": len(cat.get("records") or []), "identity_stale": sources.get("catalog_identity_stale"),
                        "identity_note": "the catalog identity the installation profile recorded" if not sources.get("catalog_identity_stale")
                        else "the catalog on disk differs from the installation profile's record: comparisons are against the current file"},
            "manifest_dat": {"path": mdat.get("path"), "sha256": mdat.get("sha256"), "size": mdat.get("size"),
                             "status": mdat["status"], "reason": mdat.get("reason"), "note": mdat.get("note")}}
    return {"schema": SCHEMA, "id": ts, "built_utc": ts, "project": {"name": project["name"], "format": project.get("schema")},
            "target": target, "integrity_sources": integrity_sources_rec, "edits": edits_section(plan), "outputs": outputs,
            "validation": plan.get("findings", []), "overrides": plan.get("overrides", {}),
            "impact": plan.get("impact", {}),
            "gate": {"passed": not report.get("gate", {}).get("fail"), "failures": report.get("gate", {}).get("fail", [])},
            "tools": {"unitypy": bundles.unitypy_version(), "pipeline": "stage-4d", "python": platform.python_version(),
                      "adapter_framework": adapters.VERSION},
            "installs": [],
            "note": "only bundles with edits are rebuilt; every other bundle of the snapshot installs as the vanilla file"}


def write(manifest, out_dir):
    """build-manifest.json next to the bundles. Returns the path."""
    p = Path(out_dir) / "build-manifest.json"
    p.write_text(json.dumps(manifest, indent=1), encoding="utf-8")
    return p


def schema2_package(pkg1, manifest):
    """Extend a schema 1 package.json dict to schema 2: every schema 1 key stays, the new sections are added."""
    out = dict(pkg1)
    out["schema"] = SCHEMA
    out["target"] = manifest["target"]
    out["edits"] = [{"asset": e["asset"], "bundle": e["bundle"], "adapter": e["adapter"], "edit_kind": e["edit_kind"],
                     "ops_count": len(e.get("ops") or [])} for e in manifest["edits"]]
    out["outputs"] = [{"rel_path": o["rel_path"], "source_sha256": o["source_sha256"], "output_sha256": o["output_sha256"],
                       "source_crc32": o["source_crc32"], "output_crc32": o["output_crc32"],
                       "catalog_crc_status": o["catalog_crc_status"], "manifest_status": o.get("manifest_status"),
                       "objects_changed": len((o["diff"] or {}).get("object", {}).get("changed_objects", [])) if o["diff"] else None,
                       "object_set_equal": (o["diff"] or {}).get("object", {}).get("object_set_equal") if o["diff"] else None}
                      for o in manifest["outputs"]]
    out["validation"] = manifest["validation"]
    out["overrides"] = manifest["overrides"]
    out["impact"] = {k: manifest["impact"][k] for k in ("buildable", "installation_readiness", "evaluated") if k in manifest["impact"]}
    out["integrity_sources"] = manifest.get("integrity_sources")
    out["tools"] = manifest["tools"]
    out["manifest_file"] = "build-manifest.json"
    return out


def read_package(path):
    """A package.json of schema 1 or 2. Schema 1 stays exactly as written (compatibility is a tested property)."""
    d = json.loads(Path(path).read_text(encoding="utf-8"))
    if d.get("schema") not in (1, SCHEMA):
        raise ValueError("package schema %r is not supported (expected 1 or %d)" % (d.get("schema"), SCHEMA))
    return d
