"""Version profiles and the update diff (spec 2.9).

A profile is what "Scan game" learned about one game build: profiles/<game_build>-<catalog_hash12>.json plus its style index in
profiles/<id>.styles.json (the same sheet entries the style index cache holds, so two profiles can be diffed later without the old game
files). `status` compares the live game with the active profile; `diff` compares two profiles; `project_states` gives every item of
a project one of: ok, target moved (auto-fixable), target gone, vanilla value changed (review). Nothing here writes to the game."""
import difflib
import json
import re
import time
from pathlib import Path

from . import bundles, index_styles, install
from . import token_patch as tp

SCHEMA = 1
STYLE_NAMES = bundles.STYLE_BUNDLES


def profiles_dir(ws):
    d = ws.root / "profiles"
    d.mkdir(parents=True, exist_ok=True)
    return d


def profile_id(build, catalog_hash):
    b = re.sub(r"[^\w.-]", "_", build or "unknown")
    return "%s-%s" % (b, (catalog_hash or "nocatalog")[:12])


def _read_catalog_hash(*dirs):
    for d in dirs:
        f = Path(d) / "catalog.hash"
        if f.is_file():
            return f.read_text(encoding="utf-8", errors="replace").strip()
    return None


def scan(ws, bundle_dir, game_build=None, catalog_hash=None, platform_folder=None, bundle_hashes=None, source=None, icon_classes=None,
         layouts=None, note=None):
    """Read the style bundles in bundle_dir into a profile and store it. bundle_dir: a stock folder (the vanilla snapshot, or a folder of
    an older build). catalog_hash/bundle_hashes: from the game folder (or the snapshot's reference) when known. Returns the profile."""
    bundle_dir = Path(bundle_dir)
    names = [n for n in STYLE_NAMES if (bundle_dir / n).is_file()]
    if not names:
        raise FileNotFoundError("no style bundles (%s) in %s" % (", ".join(STYLE_NAMES), bundle_dir))
    sheets = []
    for n in names:
        for tree in bundles.read_sheets(bundle_dir / n):
            sheets.append(index_styles.sheet_entry(n, tree))
    idx = index_styles.StyleIndex(sheets)
    hashes = dict(bundle_hashes or {})
    for n in names:
        hashes.setdefault(n, bundles.sha256(bundle_dir / n))
    catalog_hash = catalog_hash or _read_catalog_hash(bundle_dir, bundle_dir.parent)
    pid = profile_id(game_build, catalog_hash)
    prof = {"schema": SCHEMA, "id": pid, "game_build": game_build, "catalog_hash": catalog_hash, "platform_folder": platform_folder or bundle_dir.name,
            "scanned_utc": time.strftime("%Y%m%dT%H%M%SZ", time.gmtime()), "source": str(source or bundle_dir), "note": note,
            "bundles": {n: {"sha256": h, **({"sheets": [s["name"] for s in sheets if s["bundle"] == n]} if n in names else {})} for n, h in sorted(hashes.items())},
            "tokens": len(idx.defs), "sheets": len(sheets), "rules": sum(len(s["rules"]) for s in sheets),
            "icon_classes": sorted(icon_classes) if icon_classes is not None else None,
            "layouts": layouts, "styles_file": pid + ".styles.json"}
    d = profiles_dir(ws)
    (d / prof["styles_file"]).write_text(json.dumps({"schema": index_styles.CACHE_SCHEMA, "sheets": sheets}), encoding="utf-8")
    (d / (pid + ".json")).write_text(json.dumps(prof, indent=1), encoding="utf-8")
    return prof


def list_profiles(ws):
    out = []
    for f in sorted(profiles_dir(ws).glob("*.json")):
        if f.name.endswith(".styles.json"):
            continue
        try:
            p = json.loads(f.read_text(encoding="utf-8"))
        except ValueError:
            continue
        if not (isinstance(p, dict) and isinstance(p.get("id"), str) and isinstance(p.get("styles_file"), str)
                and (profiles_dir(ws) / p["styles_file"]).is_file()):
            continue                                            # any other json in the folder (a saved diff, a note) is not a profile
        out.append({k: p.get(k) for k in ("id", "game_build", "catalog_hash", "scanned_utc", "tokens", "sheets", "rules", "source", "note")})
    return out


def load(ws, pid):
    f = profiles_dir(ws) / (re.sub(r"[^\w.-]", "_", pid) + ".json")
    if not f.is_file():
        raise KeyError("no profile %s" % pid)
    return json.loads(f.read_text(encoding="utf-8"))


def load_index(ws, pid):
    prof = load(ws, pid)
    d = json.loads((profiles_dir(ws) / prof["styles_file"]).read_text(encoding="utf-8"))
    return index_styles.StyleIndex(d["sheets"], {"game_build": prof.get("game_build")})


def scan_snapshot(ws, game_build=None, aa_dir=None, icon_classes=None):
    """Scan the vanilla snapshot (stock files by construction) as the profile of its game build. The snapshot's reference hashes give the
    catalog hash and every UI bundle's hash."""
    man = ws.vanilla_manifest()
    if not man:
        raise RuntimeError("no vanilla snapshot; take one first")
    ref = man.get("reference") or {}
    return scan(ws, ws.vanilla, game_build=game_build or man.get("game_build"), catalog_hash=ref.get("catalog_hash"),
                platform_folder=ref.get("platform_folder"), bundle_hashes=ref.get("bundles"), source="vanilla snapshot of " + str(man.get("source")),
                icon_classes=icon_classes)


def active_profile(ws):
    """The profile of the current snapshot (same catalog hash), or None."""
    man = ws.vanilla_manifest() or {}
    cat = (man.get("reference") or {}).get("catalog_hash")
    if not cat:
        return None
    for p in list_profiles(ws):
        if p["catalog_hash"] == cat:
            return p
    return None


def status(ws, aa_dir):
    """Live game against the active profile. state: no_snapshot, no_profile, same, catalog_changed (guided flow), tamper (bundle changed,
    catalog same: block bundle installs, offer restore). Includes the steps of the guided flow and what to do."""
    man = ws.vanilla_manifest()
    live_cat = _read_catalog_hash(aa_dir, Path(aa_dir).parent) if aa_dir else None
    if not man:
        return {"state": "no_snapshot", "live_catalog": live_cat, "message": "No vanilla snapshot yet. Take one (game closed, stock files), then scan the game.", "block_bundle_install": True}
    prof = active_profile(ws)
    if not prof:
        return {"state": "no_profile", "live_catalog": live_cat, "message": "The snapshot has no version profile yet. Scan the game.", "block_bundle_install": False,
                "next": ["scan"]}
    out = {"profile": prof["id"], "game_build": prof["game_build"], "profile_catalog": prof["catalog_hash"], "live_catalog": live_cat}
    if live_cat and live_cat != prof["catalog_hash"]:
        return dict(out, state="catalog_changed", block_bundle_install=True, next=["restore_check", "new_snapshot", "scan", "diff"],
                    message="The game was updated (catalog.hash %s, the profile %s was scanned at %s). Restore the stock files if a skin is installed, take a new "
                            "snapshot, scan, then read the diff before building again." % (live_cat[:12], prof["id"], prof["catalog_hash"][:12]))
    t = install.tamper_status(ws, aa_dir) if aa_dir else {"state": "no_reference"}
    if t.get("state") == "modified":
        return dict(out, state="tamper", block_bundle_install=True, tamper=t, next=["restore"],
                    message="The catalog is unchanged but %d UI bundle(s) differ from the profile (%s): another tool or a leftover test bundle. "
                            "Bundle installs are blocked; restore them (a backup, or Steam > Verify integrity of game files)." % (len(t.get("modified", [])), ", ".join(t.get("modified", [])[:4])))
    return dict(out, state="same", block_bundle_install=False, message="The game matches the profile %s." % prof["id"])


# ---------------------------------------------------------------- diff
def _tokens(idx):
    return {t: sorted(v.items()) for t, v in idx.defs.items()}


def _val(v):
    """One display value of a token across its sheets (the first sheet's, others joined when they differ)."""
    vals = [x for _s, x in v]
    return vals[0] if len(set(vals)) == 1 else " | ".join("%s=%s" % (s, x) for s, x in v)


def _rule_map(idx):
    """{selector text: [(sheet, bundle, props-dict)]} for the non-token rules."""
    m = {}
    for sh in idx.sheets:
        for r in sh["rules"]:
            if r["t"]:
                continue
            m.setdefault(", ".join(r["s"]), []).append((sh["name"], sh["bundle"], {n: v for n, v, _c in r["p"]}))
    return m


def diff(old_prof, new_prof, old_idx, new_idx, cap=300):
    """Tokens added/removed/changed, rules whose selector vanished (with where they moved to), sheets, icons renamed, layouts changed."""
    ot, nt = _tokens(old_idx), _tokens(new_idx)
    removed = sorted(set(ot) - set(nt))
    added = sorted(set(nt) - set(ot))
    changed = [{"token": t, "old": _val(ot[t]), "new": _val(nt[t])} for t in sorted(set(ot) & set(nt)) if ot[t] != nt[t]]
    moved_tokens = []
    by_val = {}
    for t in added:
        by_val.setdefault(_val(nt[t]), []).append(t)
    for t in removed:                                           # a removed token whose value reappears under a similar new name was probably renamed
        close = difflib.get_close_matches(t, added, 1, 0.75)
        same = [a for a in by_val.get(_val(ot[t]), []) if a in added]
        pick = close[0] if close else (same[0] if len(same) == 1 else None)
        if pick:
            moved_tokens.append({"old": t, "new": pick, "same_value": _val(ot[t]) == _val(nt[pick])})
    orm, nrm = _rule_map(old_idx), _rule_map(new_idx)
    vanished, rule_changed = [], []
    for sel, olds in orm.items():
        news = nrm.get(sel)
        if not news:
            vanished.append({"selector": sel, "sheet": olds[0][0]})
            continue
        osheets = {s for s, _b, _p in olds}
        if not (osheets & {s for s, _b, _p in news}):
            rule_changed.append({"selector": sel, "kind": "moved", "from": sorted(osheets), "to": sorted({s for s, _b, _p in news})})
            continue
        op, np_ = {}, {}                                          # a selector can appear several times in a sheet: compare what they add up to
        for s, _b, p in olds:
            op.setdefault(s, {}).update(p)
        for s, _b, p in news:
            np_.setdefault(s, {}).update(p)
        for s in sorted(set(op) & set(np_)):
            if op[s] != np_[s]:
                d = {k: [op[s].get(k), np_[s].get(k)] for k in sorted(set(op[s]) | set(np_[s])) if op[s].get(k) != np_[s].get(k)}
                rule_changed.append({"selector": sel, "kind": "changed", "sheet": s, "props": d})
                break
    osh, nsh = {(s["bundle"], s["name"]) for s in old_idx.sheets}, {(s["bundle"], s["name"]) for s in new_idx.sheets}
    out = {"old": old_prof["id"], "new": new_prof["id"], "old_build": old_prof.get("game_build"), "new_build": new_prof.get("game_build"),
           "tokens": {"old": len(ot), "new": len(nt), "added": added[:cap], "added_count": len(added), "removed": removed[:cap], "removed_count": len(removed),
                      "changed": changed[:cap], "changed_count": len(changed), "renamed": moved_tokens[:cap]},
           "rules": {"old": len(orm), "new": len(nrm), "vanished": vanished[:cap], "vanished_count": len(vanished), "added_count": len(set(nrm) - set(orm)),
                     "moved_or_changed": rule_changed[:cap], "moved_or_changed_count": len(rule_changed)},
           "sheets": {"added": sorted("%s/%s" % x for x in nsh - osh), "removed": sorted("%s/%s" % x for x in osh - nsh)}}
    oi, ni = old_prof.get("icon_classes"), new_prof.get("icon_classes")
    if oi is None or ni is None:
        out["icons"] = {"available": False, "reason": "icon class lists exist for %s only" % ", ".join(p["id"] for p in (old_prof, new_prof) if p.get("icon_classes") is not None) if (oi or ni) else "neither profile recorded icon classes (the old icon bundles are not on disk)"}
    else:
        gone, new = sorted(set(oi) - set(ni)), sorted(set(ni) - set(oi))
        ren = []
        for g in gone:
            c = difflib.get_close_matches(g, new, 1, 0.88)
            if c:
                ren.append({"old": g, "new": c[0]})
        out["icons"] = {"available": True, "old": len(oi), "new": len(ni), "removed": gone[:cap], "added": new[:cap], "renamed": ren[:cap]}
    ol, nl = old_prof.get("layouts"), new_prof.get("layouts")
    if not ol or not nl:
        out["layouts"] = {"available": False, "reason": "no layout dump was recorded with %s" % (old_prof["id"] if not ol else new_prof["id"])}
    else:
        out["layouts"] = {"available": True, "changed": sorted(k for k in set(ol) & set(nl) if ol[k] != nl[k])[:cap], "added": sorted(set(nl) - set(ol))[:cap],
                          "removed": sorted(set(ol) - set(nl))[:cap]}
    return out


def project_states(project, old_idx, new_idx, catalog=None):
    """One row per project item: {kind, item, state, detail, fix?}. state: ok | target moved | target gone | vanilla value changed.
    A `fix` (auto-fixable) names the change `autofix` applies. catalog: the new game's image catalog rows (None: images are not checked)."""
    rows = []

    def row(kind, item, state, detail="", fix=None):
        r = {"kind": kind, "item": item, "state": state, "detail": detail}
        if fix:
            r["fix"] = fix
        rows.append(r)

    ot, nt = _tokens(old_idx), _tokens(new_idx)
    added = [t for t in nt if t not in ot]
    for e in project.get("token_overrides", []):
        t = e["token"]
        if t in nt:
            if t in ot and ot[t] != nt[t]:
                row("token", t, "vanilla value changed", "game value was %s, now %s (your override is kept)" % (_val(ot[t]), _val(nt[t])))
            else:
                row("token", t, "ok")
            continue
        close = difflib.get_close_matches(t, added, 1, 0.75)
        same = [a for a in added if t in ot and _val(nt[a]) == _val(ot[t])]
        pick = close[0] if close else (same[0] if len(same) == 1 else None)
        if pick:
            row("token", t, "target moved", "the game now calls it %s" % pick, {"op": "rename_token", "from": t, "to": pick})
        else:
            row("token", t, "target gone", "no token with this name or value in the new game")
    orm, nrm = _rule_map(old_idx), _rule_map(new_idx)
    nsheets = {s["name"] for s in new_idx.sheets}
    for e in project.get("scoped_rules", []):
        sel, sheet, op = e["selector"], e["sheet"], e.get("op")
        label = "%s%s [%s]" % (("%s: " % op) if op else "", sel[:70], sheet)
        if sheet not in nsheets:
            row("rule", label, "target gone", "the game has no stylesheet %s any more" % sheet)
            continue
        if not op:                                                   # an appended rule needs no vanilla rule, only its sheet
            row("rule", label, "ok")
            continue
        here = [p for s, _b, p in nrm.get(sel, []) if s == sheet]
        if not here:
            elsewhere = sorted({s for s, _b, _p in nrm.get(sel, [])})
            if elsewhere:
                row("rule", label, "target moved", "the game rule is now in %s" % ", ".join(elsewhere), {"op": "move_rule", "selector": sel, "from": sheet, "to": elsewhere[0]})
            else:
                row("rule", label, "target gone", "the game has no rule with exactly this selector any more")
            continue
        before = [p for s, _b, p in orm.get(sel, []) if s == sheet]
        names = list(e.get("props", {})) + list(e.get("remove", []))
        was = {k: v for p in before for k, v in p.items() if not names or k in names}
        now = {k: v for p in here for k, v in p.items() if not names or k in names}
        if before and was != now:
            row("rule", label, "vanilla value changed", "the game's own %s changed: %s" % (", ".join(k for k in set(was) | set(now) if was.get(k) != now.get(k))[:80], "review your edit"))
        else:
            row("rule", label, "ok")
    for i, s in enumerate(project.get("literal_swaps", [])):
        from . import colour
        try:
            c = colour.from_obj(s["from"])
            f = lambda idx: len(idx.literal(colour.hex6(c), c[3])["exact"]) if s["mode"] == "rgba" else len(idx.literal(colour.hex6(c), 1.0)["rgb_all"])
            o, n = f(old_idx), f(new_idx)
        except Exception as ex:
            row("literal swap", "#%d" % (i + 1), "target gone", "could not be checked: %s" % ex)
            continue
        item = "%s -> %s" % (colour.hex6(c), colour.hex6(colour.from_obj(s["to"])))
        if n == 0:
            row("literal swap", item, "target gone", "the colour is no longer used by any game rule")
        elif o != n:
            row("literal swap", item, "vanilla value changed", "the game uses this colour in %d places now (was %d)" % (n, o))
        else:
            row("literal swap", item, "ok", "%d places" % n)
    if catalog is not None:
        by_id = {(r["bundle"], str(r["path_id"])) for r in catalog}
        by_name = {}
        for r in catalog:
            by_name.setdefault((r["kind"], r["name"]), []).append(r)
        for e in project.get("image_swaps", []):
            label = "%s %s" % (e["kind"], e.get("name") or e["path_id"])
            if (e["bundle"], str(e["path_id"])) in by_id:
                row("image", label, "ok")
                continue
            c = by_name.get((e["kind"], e.get("name")), [])
            if len(c) == 1:
                row("image", label, "target moved", "same name, now %s id %s" % (c[0]["bundle"], c[0]["path_id"]),
                    {"op": "repoint_image", "bundle": e["bundle"], "path_id": str(e["path_id"]), "to_bundle": c[0]["bundle"], "to_path_id": str(c[0]["path_id"])})
            else:
                row("image", label, "target gone", "no image with this id or name in the new game")
    for old, new in project.get("rename_classes", {}).items():
        used = any(re.search(r"\.%s(?![\w-])" % re.escape(old), ", ".join(r["s"])) for sh in new_idx.sheets for r in sh["rules"])
        row("class rename", "%s -> %s" % (old, new), "ok" if used else "target gone", "" if used else "the class is not used by any game rule any more")
    if project.get("native_sheets"):
        row("native sheets", "%d imported sheet(s)" % len(project["native_sheets"]), "ok", "USS sheets are read by the game at start; they keep working, the diff only tells what drifted")
    return rows


def autofix(project, rows):
    """Apply the auto-fixable ('target moved') rows to the project model. Returns (project, applied descriptions)."""
    p = json.loads(json.dumps(project))
    done = []
    for r in rows:
        f = r.get("fix")
        if not f:
            continue
        if f["op"] == "rename_token":
            for e in p.get("token_overrides", []):
                if e["token"] == f["from"] and not any(x["token"] == f["to"] for x in p["token_overrides"]):
                    e["token"] = f["to"]; done.append("token %s -> %s" % (f["from"], f["to"]))
        elif f["op"] == "move_rule":
            for e in p.get("scoped_rules", []):
                if e["selector"] == f["selector"] and e["sheet"] == f["from"] and e.get("op"):
                    e["sheet"] = f["to"]; done.append("%s moved to %s" % (f["selector"][:50], f["to"]))
        elif f["op"] == "repoint_image":
            for e in p.get("image_swaps", []):
                if e["bundle"] == f["bundle"] and str(e["path_id"]) == f["path_id"]:
                    e["bundle"], e["path_id"] = f["to_bundle"], f["to_path_id"]; done.append("image %s repointed" % (e.get("name") or e["path_id"]))
    return p, done
