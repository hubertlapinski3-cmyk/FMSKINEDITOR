"""build(project) -> report. Runs the vendored token_patch.SheetPatcher (unchanged) on fresh copies of the
vanilla style bundles, after the specificity pass, then the structural gate and the contrast report."""
import json
import shutil
import time
from pathlib import Path

from . import bundles, colour, images, placement, specificity, verify_static
from . import project as project_mod
from . import token_patch as tp

COUNTS = ("tokens", "literals", "gradients", "renames", "appended", "edited")


class BuildRefused(RuntimeError):
    pass


def _refusal(blocks):
    """One refusal message from the plan's blocking findings (plain words; the findings stay in the manifest)."""
    parts = []
    for b in blocks:
        parts.append(b.get("message") or b.get("code", "unknown block"))
    head = {"tile_overlap": "the build is refused: tiles would overlap, and the game drops a tile when they do "
                            "(Stage 3E). Move the tile so it does not overlap, or start the build with allow overlap "
                            "to record the deliberate exception",
            "impact_unresolved": "the build is refused: an edit's dependency impact is unresolved",
            "unknown_edit_kind": "the build is refused: an edit cannot be classified safely"}.get(blocks[0].get("code"),
                                                                                                 "the build is refused")
    return head + ": " + "; ".join(parts[:6]) + ("; and %d more" % (len(parts) - 6) if len(parts) > 6 else "")


def refuse_unproven(tree, spec):
    """Safety rule: a build never writes a colour derived from a bundle entry that did not decode.
    token_patch's rgb-keep-alpha swap copies the old entry's alpha into a new entry, so a swap that would hit
    an entry outside 0..1 stops the build. (Exact RGBA swaps cannot match such an entry at all.)"""
    lit = spec.get("literal_map") or {}
    if not lit or tree.get("m_Name") in spec.get("skip_sheets", []):
        return
    bad = {i for i, c in enumerate(tree.get("colors", [])) if not colour.in_range(c)}
    if not bad:
        return
    for rule in tree["m_Rules"]:
        for prop in rule["m_Properties"]:
            for h in prop["m_Values"]:
                if h["m_ValueType"] == tp.VT_COLOR and h["valueIndex"] in bad:
                    c = tree["colors"][h["valueIndex"]]
                    rgb = "#" + "".join(colour.byte_to_hex(colour.unit_to_byte(c[k])) for k in "rgb")
                    if rgb in lit:
                        raise BuildRefused(
                            "build refused: the rgb-keep-alpha swap of %s would copy an undecoded bundle colour %r "
                            "(class: %s; %s, %s, %s). Quarantined colours are never rewritten; see diagnostics/README.md. "
                            "Remove that swap or replace the colour with a scoped rule." % (
                                rgb, colour.raw_floats(c), colour.classify_out_of_range(colour.raw_floats(c))[0],
                                tree.get("m_Name"), tp._sel_text(rule),
                                prop.get("m_CustomName") or tp.INV_PROP.get(prop.get("m_Id"), "prop-%s" % prop.get("m_Id"))))


def swap_rgba(tree, spec):
    """Exact RGBA -> RGBA literal swaps (mode "rgba"). Runs on the vanilla tree before token_patch, in every
    rule of every non-skipped sheet. Like token_patch it appends a new colour entry and repoints the handle."""
    swaps = spec.get("rgba_swaps") or []
    if not swaps or tree.get("m_Name") in spec.get("skip_sheets", []):
        return []
    hits = []
    for rule in tree["m_Rules"]:
        for prop in rule["m_Properties"]:
            for h in prop["m_Values"]:
                if h["m_ValueType"] != tp.VT_COLOR:
                    continue
                try:
                    c = colour.from_floats(tree["colors"][h["valueIndex"]], tree.get("m_Name", ""))   # same decode as the index
                except colour.ColourDecodeError:
                    continue        # undecoded entries are never matched, so never rewritten
                for i, f, t in swaps:
                    if colour.same(c, f):
                        tree["colors"].append(colour.to_floats(t))
                        h["valueIndex"] = len(tree["colors"]) - 1
                        hits.append({"swap": i, "mode": "rgba", "sheet": tree.get("m_Name"), "selector": tp._sel_text(rule),
                                     "property": prop.get("m_CustomName") or tp.INV_PROP.get(prop.get("m_Id"), "prop-%s" % prop.get("m_Id")),
                                     "from": colour.to_obj(f), "to": colour.to_obj(t)})
                        break
    return hits


def apply_declaration_edits(tree, bundle, spec, acc):
    """Stage 5H per-declaration edits for one sheet tree. Returns True when anything changed."""
    edits = [e for e in spec.get("declaration_edits") or []
             if e.get("bundle") == bundle and e.get("sheet") == tree.get("m_Name")]
    if not edits:
        return False
    sp = tp.SheetPatcher(tree, spec)
    changed = False
    for e in edits:
        hits, n = sp.set_declaration(e)
        acc.setdefault("declaration_edits", []).append({"sheet": tree.get("m_Name"), "selector": e["selector"],
                                                        "occurrence": e.get("occurrence", 0),
                                                        "property": e["property"], "old": e.get("old"),
                                                        "new": e.get("new"), "hits": hits, "changed": n})
        changed = changed or bool(n)
    return changed


def patch_sheet(tree, spec, acc):
    """One sheet: exact RGBA swaps, then token_patch in its own step order. Returns True when the tree changed."""
    refuse_unproven(tree, spec)
    rgba_hits = swap_rgba(tree, spec)
    acc["literal_hits"] += rgba_hits
    acc["totals"]["literals_rgba"] += len(rgba_hits)
    sp = tp.SheetPatcher(tree, spec)
    name = tree.get("m_Name")
    if sp.patch() != "skipped":
        for e in spec.get("edit_rules_by_sheet", {}).get(name, []):      # edits first, so they only ever see the game's own rules
            hits, changed = sp.edit_rule(e)
            acc["edits"].append({"sheet": name, "op": e["op"], "selector": e["selector"], "rules_hit": hits, "declarations": changed})
            acc["sheets_found"].add(name)
        for rule in spec.get("append_rules_by_sheet", {}).get(name, []):
            sp.append_rule(rule)
            acc["sheets_found"].add(name)
    for k in COUNTS:
        acc["totals"][k] += getattr(sp, "count_" + k)
    acc["tokens_found"] |= sp.found_tokens
    acc["literal_hits"] += [dict(h, mode="rgb-keep-alpha") for h in sp.literal_hits]
    return bool(rgba_hits) or any(getattr(sp, "count_" + k) for k in COUNTS)


def new_acc():
    return {"tokens_found": set(), "sheets_found": set(), "literal_hits": [], "edits": [],
            "totals": dict(dict.fromkeys(COUNTS, 0), literals_rgba=0)}


def swap_report(project, hits):
    """One row per literal swap of the project: from, to, mode, hits."""
    rows = []
    for i, e in enumerate(project.get("literal_swaps", [])):
        if e["mode"] == "rgba":
            n = sum(h["mode"] == "rgba" and h["swap"] == i for h in hits)
        else:
            f = colour.hex6(colour.from_obj(e["from"]))
            n = sum(h["mode"] == "rgb-keep-alpha" and h["from"] == f for h in hits)
        rows.append({"from": e["from"], "to": e["to"], "mode": e["mode"], "hits": n})
    return rows


def build(project, ws, index, game_dir=None, keep=5, progress=None, reg=None, profile=None,
          allow_overlap=False, allow_unknown_impact=False):
    """Never reads or writes the game dir. Stage 4D: the typed plan (buildplan.review) runs first and its policy can
    refuse the build (tile overlap without an override, an unresolved identity/reference impact); the finished build
    writes the schema 2 manifest (build-manifest.json) and a schema 2 package.json (schema 1 keys unchanged)."""
    project = project_mod.validate(project_mod.migrate(project))
    spec = project_mod.to_spec(project)
    opts = project.get("options", {})
    man = ws.vanilla_manifest()
    if not man:
        raise RuntimeError("no vanilla snapshot; take one first")
    from . import buildplan
    plan = buildplan.review(ws, project, index, reg=reg, allow_overlap=allow_overlap,
                            allow_unknown_impact=allow_unknown_impact)
    if plan["blocked"]:
        raise BuildRefused(_refusal(plan["blocked"]))
    spec_log = specificity.raise_spec(spec, index) if opts.get("raise_specificity", True) else []
    from . import tiles as _tiles
    allow_bundle_tiles = project_mod.experimental_bundle_layout_edits(project)
    catalog_ops = _tiles.validate_ops(project.get("tile_bundle_ops") or [])
    spec["tile_ops"] = (_tiles.validate_ops(_tiles.ops_for(ws, project["name"])) if allow_bundle_tiles else []) + catalog_ops         # route lock: cell moves need flag; B2/B3 catalog ops use bundle route
    ts = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    out = ws.build / project["name"] / ts
    if "football manager 27" in str(out).lower() or (game_dir and Path(game_dir).resolve() in out.resolve().parents):
        raise RuntimeError("build output must not be inside the game folder")
    out.mkdir(parents=True, exist_ok=True)
    acc = new_acc()
    files, touched = {}, {}
    semantics = {}                                          # per-bundle semantic summary for the build manifest
    names = sorted(man["files"])
    for k, name in enumerate(names):
        if progress:
            progress("patching " + name, k / (len(names) + 1))
        src = ws.vanilla / name
        if bundles.sha256(src) != man["files"][name]["sha256"]:
            raise RuntimeError("vanilla copy of %s does not match its manifest" % name)
        touched[name] = set()
        changed = bundles.patch_bundle(
            src, out, lambda tree, _b=name: (patch_sheet(tree, spec, acc) or apply_declaration_edits(tree, _b, spec, acc)),
            touched[name])
        files[name] = {"changed": changed, "vanilla_sha256": man["files"][name]["sha256"],
                       "sha256": bundles.sha256(out / name) if changed else man["files"][name]["sha256"]}
        if changed:
            semantics.setdefault(name, {"adapter": "stylesheet"})
    # image and SVG swaps: every image bundle of the snapshot is part of the build, unchanged ones install as the vanilla file
    image_notes = []
    swaps, icon_swaps = {}, [e for e in project.get("image_swaps", []) if e["kind"] == "icon"]
    for e in project.get("image_swaps", []):
        if e["kind"] != "icon":
            swaps.setdefault(e["bundle"], []).append(e)
    layout_docs = {}
    for doc in project.get("layout_patches", []):
        layout_docs.setdefault(doc["layout"]["bundle"], []).append(doc)
    from . import tiles as tiles_mod
    tile_ops = {}
    if allow_bundle_tiles:
        for op in tiles_mod.validate_ops(tiles_mod.ops_for(ws, project["name"])):
            tile_ops.setdefault(op["bundle"], []).append(op)
    for op in catalog_ops:
        tile_ops.setdefault(op["bundle"], []).append(op)
    table_docs = {}
    for doc in project.get("table_patches", []):
        table_docs.setdefault(doc["view"]["bundle"], []).append(doc)
    needed = set(swaps) | set(layout_docs) | set(tile_ops) | set(table_docs)
    if icon_swaps:                                         # an icon lives in the atlas of every UI scale
        needed |= {b for s in images.SCALES for b in (images.ICONS % s, images.ATLASES % s)
                   if b in man.get("reference", {}).get("bundles", {})}
    for name in sorted(needed):
        if name not in man.get("image_files", {}):
            raise RuntimeError("%s is not in the vanilla snapshot yet; %s" % (name, "edit the layout again in the Layouts view (it adds the bundle)" if name in layout_docs else "build from the Studio (it adds the composition bundle)" if name in tile_ops else "edit the table in the Tables view again (it adds the bundle)" if name in table_docs else "pick the image again on the Images tab (it adds the bundle)"))
    atlas_scale = {images.ATLASES % s: s for s in images.SCALES}
    for name, f in sorted(man.get("image_files", {}).items()):
        src = ws.vanilla / name
        if bundles.sha256(src) != f["sha256"]:
            raise RuntimeError("vanilla copy of %s does not match its manifest" % name)
        if progress:
            progress("images " + name, 0.9)
        touched[name] = set()
        changed = False
        if name in table_docs:
            from . import tables as tables_mod
            changed, notes, _ = tables_mod.apply_patches(src, out, table_docs[name], touched[name])
            image_notes += notes
            files[name] = {"changed": changed, "tables": True, "vanilla_sha256": f["sha256"], "sha256": bundles.sha256(out / name) if changed else f["sha256"]}
            semantics[name] = {"kind": "table_patch", "notes": notes}
            continue
        if name in tile_ops:
            changed, notes, _ = tiles_mod.apply_ops(src, out, tile_ops[name], touched[name])
            image_notes += notes
            files[name] = {"changed": changed, "tiles": True, "vanilla_sha256": f["sha256"], "sha256": bundles.sha256(out / name) if changed else f["sha256"]}
            semantics[name] = {"adapter": "composition", "notes": notes}
            continue
        if name in layout_docs:
            from . import uxml
            changed, notes, _ = uxml.apply_patches(src, out, layout_docs[name], touched[name])
            image_notes += notes
            files[name] = {"changed": changed, "layout": True, "vanilla_sha256": f["sha256"], "sha256": bundles.sha256(out / name) if changed else f["sha256"]}
            semantics[name] = {"kind": "layout_patch", "notes": notes}
            continue
        if name in swaps:
            changed, notes, _ = images.apply_swaps(src, out, swaps[name], project_mod.images_dir(ws, project["name"]), touched[name])
            image_notes += notes
            semantics[name] = {"adapter": "texture", "notes": notes}
        elif icon_swaps and name in atlas_scale:
            icons_src = ws.vanilla / (images.ICONS % atlas_scale[name])
            changed, notes = images.apply_icon_swaps(src, icons_src, out, icon_swaps, project_mod.images_dir(ws, project["name"]), touched[name])
            image_notes += notes
            semantics[name] = {"adapter": "sprite", "scale": atlas_scale[name], "notes": notes}
        files[name] = {"changed": changed, "vanilla_sha256": f["sha256"], "sha256": bundles.sha256(out / name) if changed else f["sha256"]}
        if changed and name not in semantics:
            semantics[name] = {"kind": "image_swaps"}
    if progress:
        progress("verifying build", len(names) / (len(names) + 1))
    gate, built = verify_static.gate(spec, ws.vanilla, out, files, touched)
    contrast = verify_static.contrast(spec, built, project.get("contrast_pairs", []),
                                      colour.from_obj(opts["contrast_backdrop"]))
    swaps = swap_report(project, acc["literal_hits"])
    ruled = set(spec["append_rules_by_sheet"]) | set(spec.get("edit_rules_by_sheet", {}))
    skipped_rules = sorted(ruled & set(spec["skip_sheets"]))
    report = {
        "project": project["name"], "built_utc": ts, "game_build": man.get("game_build"), "files": files,
        "totals": acc["totals"],
        "tokens_not_found": sorted(set(spec["tokens"]) - acc["tokens_found"]),
        "sheets_not_found": sorted(ruled - acc["sheets_found"] - set(skipped_rules)),
        "edits": acc["edits"],
        "decode_failures": len(index.failures),
        "gate": gate, "contrast": contrast, "specificity_log": spec_log,
        "literal_swaps": swaps,
        "warnings": project_mod.warnings(project, [r["hits"] for r in swaps])
        + (["%d quarantined bundle colour(s) (outside 0..1) are left exactly as in vanilla" % len(index.failures)]
           if index.failures else [])
        + ["scoped rules on skipped sheet %s were not applied" % s for s in skipped_rules]
        + ["cannot raise above %s: %s" % (x["strongest"], x["branch"]) for x in spec_log if x.get("cannot_raise")],
        "literal_hits": acc["literal_hits"], "spec": spec,
        # stored placement edits: reported here; their x/y are built into the composition bundles (tiles.py) and gated
        "layout_placement": placement.report(ws, project["name"]),
        "table_patches": {"files": len(project.get("table_patches", [])), "ops": sum(len(d["ops"]) for d in project.get("table_patches", []))},
        "tile_edits": {"cells": sum(len(v) for v in tile_ops.values()), "bundles": sorted(tile_ops)},
        "image_swaps": {"count": len(project.get("image_swaps", [])), "notes": image_notes},
        "layout_patches": {"files": len(project.get("layout_patches", [])), "ops": sum(len(d["ops"]) for d in project.get("layout_patches", []))},
    }
    (out / "build-report.json").write_text(json.dumps(report, indent=1), encoding="utf-8")
    if progress:
        progress("recording the build manifest", 0.98)
    from . import manifest as manifest_mod
    m = manifest_mod.build_manifest(ws, project, plan, report, out, ts, reg=reg, profile=profile, semantics=semantics)
    manifest_mod.write(m, out)
    report["manifest"] = {"schema": m["schema"], "file": "build-manifest.json", "outputs": len(m["outputs"]),
                          "edits": len(m["edits"]), "overrides": m["overrides"],
                          "installation_readiness": m["impact"].get("installation_readiness")}
    # Stage 4E: the report's integrity section. A catalog or manifest MISMATCH is reported here as an installation
    # warning, never as a build failure: the gate decides buildability, the statuses decide readiness.
    report["integrity"] = {
        "sources": m.get("integrity_sources"),
        "buildable": plan["impact"]["buildable"], "installation_readiness": plan["impact"]["installation_readiness"],
        "outputs": {o["rel_path"]: {"source_sha256": o["source_sha256"], "output_sha256": o["output_sha256"],
                                    "source_crc32": o["source_crc32"], "output_crc32": o["output_crc32"],
                                    "catalog_crc_status": o["catalog_crc_status"],
                                    "catalog_record_offset": ((o.get("integrity") or {}).get("catalog") or {}).get("record_offset"),
                                    "catalog_stored_crc32": ((o.get("integrity") or {}).get("catalog") or {}).get("stored_crc32"),
                                    "manifest_status": o.get("manifest_status"),
                                    "output_whole_file_crc32": ((o.get("integrity") or {}).get("manifest_dat") or {}).get("output_whole_file_crc32")}
                    for o in m["outputs"]},
        "note": "a catalog CRC or manifest mismatch is an installation warning, not a build failure; the game logged a "
                "CRC mismatch and still used the modified bundle in the one tested scenario (Stage 3G) - observed, not guaranteed"}
    report["package"] = write_package(ws, project, index, report, out, man, ts, m)
    old = sorted(p for p in (ws.build / project["name"]).iterdir() if p.is_dir() and (p / "build-report.json").exists())
    for p in old[:-keep] if keep else []:
        shutil.rmtree(p, ignore_errors=True)
    report["dir"] = str(out)
    return report


def write_package(ws, project, index, report, out, man, ts, manifest2=None):
    """The build's package manifest (spec: Package = id, profile, plan digest, files with hashes, gate result): written as package.json next to
    the bundles and mirrored to <project folder>/packages/<id>.json. The plan digest is the sha256 of the build plan's operations and dropped
    items (not its warnings), so two builds of the same project state have the same digest. Stage 4D: with a finished build manifest the
    package is schema 2 (every schema 1 key unchanged, the typed edits/outputs/validation sections added). Installing still goes through
    install.install, which re-checks the gate and the tamper state; the manifest is the record of what was built."""
    import hashlib
    from . import plan as plan_mod, profile, projfmt
    try:
        pl = plan_mod.plan(ws, project, index, None, "bundles")
        digest = hashlib.sha256(json.dumps({"operations": pl["operations"], "dropped": pl["dropped"]}, sort_keys=True, default=str).encode("utf-8")).hexdigest()
        ops = [{"op": o["op"], "count": o["count"]} for o in pl["operations"] if o["op"] != "NativeWriteSheet"]
    except Exception as ex:
        digest, ops = None, ["plan failed: %s" % ex]
    act, act_build = None, None
    try:
        a = profile.active_profile(ws) or {}
        act, act_build = a.get("id"), a.get("game_build")
    except Exception:
        pass
    gate = report["gate"]
    pkg = {"schema": 1, "id": ts, "project": project["name"], "built_utc": ts, "game_build": man.get("game_build") or act_build or report.get("game_build"), "profile": act,
           "catalog_hash": (man.get("reference") or {}).get("catalog_hash"), "plan_digest": digest, "plan": ops,
           "files": {n: {"sha256": f["sha256"], "vanilla_sha256": f["vanilla_sha256"]} for n, f in report["files"].items() if f["changed"]},
           "gate": {"passed": not gate["fail"], "failures": gate["fail"], "checked": {k: v for k, v in gate.items() if k.endswith("_checked") or k == "untouched_bundles_checked"}},
           "installable": not gate["fail"]}
    if manifest2 is not None:
        from . import manifest as manifest_mod
        pkg = manifest_mod.schema2_package(pkg, manifest2)
    text = json.dumps(pkg, indent=1)
    (Path(out) / "package.json").write_text(text, encoding="utf-8")
    if projfmt.is_folder(ws, project["name"]):
        d = projfmt.folder(ws, project["name"]) / "packages"
        d.mkdir(exist_ok=True)
        (d / ("%s.json" % ts)).write_text(text, encoding="utf-8")
    return pkg


def latest_build(ws, name):
    d = ws.build / name
    builds = sorted(p for p in d.iterdir() if (p / "build-report.json").exists()) if d.is_dir() else []
    return builds[-1] if builds else None
