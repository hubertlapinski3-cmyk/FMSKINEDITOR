"""Compare another skin with vanilla: read-only. Two kinds of source:

- a runtime USS skin folder (skin.json + .uss sheets + images and fonts it references with url()), as used by skin-loader mods;
- game bundles (a folder of .bundle files, or one file) from another skin: style bundles are compared token by token, image
  bundles object by object (which textures and SVGs differ).

Nothing is installed and nothing is written outside the workspace's cache. The comparison can be previewed on the measured screens
(its colour tokens become a temporary project) and its colour tokens can be copied into a new project."""
import hashlib
import json
import re
from pathlib import Path

from . import bundles, colour, images, index_styles
from . import project as project_mod

COMMENT = re.compile(r"/\*.*?\*/", re.S)
URL = re.compile(r"url\(\s*['\"]?([^'\")]+)['\"]?\s*\)")
VAR = re.compile(r"var\(\s*(--[\w-]+)\s*\)")


def parse_uss(text):
    """[(selector text, [(property, value)])] from USS source. Tolerant: comments dropped, nested braces not expected."""
    text = COMMENT.sub("", text)
    out = []
    for m in re.finditer(r"([^{}]+)\{([^{}]*)\}", text):
        sel = " ".join(m.group(1).split())
        decls = []
        for d in m.group(2).split(";"):
            if ":" in d:
                k, v = d.split(":", 1)
                if k.strip():
                    decls.append((k.strip(), " ".join(v.split())))
        out.append((sel, decls))
    return out


def _vanilla_colour(index, token):
    """The colour a vanilla token resolves to (through aliases), as #RRGGBBAA, or None."""
    if index is None:
        return None
    chain, c = index.chain(token)
    return colour.hex8(colour.from_obj(c)) if c else None


def _theirs_colour(value, tokens, index, depth=0):
    """Resolve a value of the other skin: a colour, or var() through its own tokens first, then vanilla."""
    v = value.strip()
    c = colour.parse(v)
    if c:
        return colour.hex8(c)
    m = VAR.fullmatch(v)
    if m and depth < 12:
        t = m.group(1)
        if t in tokens:
            return _theirs_colour(tokens[t], tokens, index, depth + 1)
        return _vanilla_colour(index, t)
    return None


def load_uss_skin(folder, index):
    folder = Path(folder)
    manifest = json.loads((folder / "skin.json").read_text(encoding="utf-8-sig"))
    sheets = manifest.get("Sheets") or sorted(p.name for p in folder.glob("*.uss"))
    tokens, rules, per_sheet, urls, props, techniques = {}, [], [], {}, {}, {}
    for name in sheets:
        f = folder / name
        if not f.is_file():
            per_sheet.append({"sheet": name, "missing": True})
            continue
        parsed = parse_uss(f.read_text(encoding="utf-8-sig", errors="replace"))
        nroot = nrules = 0
        for sel, decls in parsed:
            if sel == ":root":
                for k, v in decls:
                    if k.startswith("--"):
                        tokens[k] = v
                        nroot += 1
                continue
            nrules += 1
            rules.append({"sheet": name, "selector": sel, "decls": decls})
            for k, v in decls:
                props[k] = props.get(k, 0) + 1
                for u in URL.findall(v):
                    urls.setdefault(u, set()).add(name)
                if k == "display" and v == "none":
                    techniques["display: none (hide elements)"] = techniques.get("display: none (hide elements)", 0) + 1
                if k in ("rotate", "scale", "translate"):
                    techniques["transforms (%s)" % k] = techniques.get("transforms (%s)" % k, 0) + 1
                if k.startswith("-unity-slice"):
                    techniques["9-slice images"] = techniques.get("9-slice images", 0) + 1
                if k == "background-image":
                    techniques["background images"] = techniques.get("background images", 0) + 1
                if k == "--unity-image-tint-color":
                    techniques["image tint via --unity-image-tint-color"] = techniques.get("image tint via --unity-image-tint-color", 0) + 1
        for v in tokens.values():
            for u in URL.findall(v):
                urls.setdefault(u, set()).add(name)
        per_sheet.append({"sheet": name, "root_tokens": nroot, "rules": nrules, "bytes": f.stat().st_size})
    # tokens: changed vanilla tokens vs new (skin-own) tokens
    changed, new = [], []
    for k, v in sorted(tokens.items()):
        van = index.value(k) if index else None
        row = {"token": k, "theirs": v, "theirs_colour": _theirs_colour(v, tokens, index)}
        if van is None:
            row["kind"] = "font" if ".ttf" in v or ".otf" in v else "image" if URL.search(v) else "other"
            new.append(row)
        else:
            row.update(vanilla=van, vanilla_colour=_vanilla_colour(index, k))
            if row["theirs_colour"] != row["vanilla_colour"] or (row["theirs_colour"] is None and v != van):
                changed.append(row)
    assets = []
    for u, where in sorted(urls.items()):
        p = folder / u
        a = {"file": u, "exists": p.is_file(), "sheets": sorted(where), "kind": "font" if u.lower().endswith((".ttf", ".otf")) else "image"}
        if p.is_file():
            a["bytes"] = p.stat().st_size
            if a["kind"] == "image":
                try:
                    from PIL import Image
                    with Image.open(p) as im:
                        a["w"], a["h"] = im.size
                except Exception:
                    pass
        assets.append(a)
    unused = sorted(p.name for p in folder.iterdir() if p.is_file() and p.suffix.lower() in (".png", ".jpg", ".ttf", ".otf") and p.name not in urls)
    return {"kind": "uss", "name": manifest.get("Name") or folder.name, "path": str(folder), "sheets": per_sheet,
            "tokens_changed": changed, "tokens_new": new, "rules": len(rules), "top_properties": sorted(props.items(), key=lambda x: -x[1])[:25],
            "assets": assets, "unused_files": unused, "techniques": techniques,
            "rule_samples": [{"sheet": r["sheet"], "selector": r["selector"], "decls": r["decls"][:6]} for r in rules[:400]]}


def _digests(path):
    d, _ = bundles.object_digests(path)
    return d


def load_bundles(paths, index, aa_dir):
    """Bundles of another skin against the game's stock files (vanilla snapshot copies when present, else the live files)."""
    aa_dir = Path(aa_dir) if aa_dir else None
    out = {"kind": "bundles", "name": Path(paths[0]).parent.name if len(paths) > 1 else Path(paths[0]).name, "path": str(Path(paths[0]).parent),
           "bundles": [], "tokens_changed": [], "tokens_new": [], "images_changed": []}
    for p in paths:
        p = Path(p)
        row = {"bundle": p.name, "bytes": p.stat().st_size}
        if p.name in bundles.STYLE_BUNDLES:
            sheets = [index_styles.sheet_entry(p.name, t) for t in bundles.read_sheets(p)]
            theirs = index_styles.StyleIndex(sheets)
            row["sheets"] = len(sheets)
            for k in sorted(theirs.defs):
                v, van = theirs.value(k), index.value(k) if index else None
                tc, vc = theirs.chain(k)[1], index.chain(k)[1] if index and van is not None else None
                rowk = {"token": k, "theirs": v, "theirs_colour": colour.hex8(colour.from_obj(tc)) if tc else None}
                if van is None:
                    out["tokens_new"].append(dict(rowk, kind="other"))
                elif v != van:
                    out["tokens_changed"].append(dict(rowk, vanilla=van, vanilla_colour=colour.hex8(colour.from_obj(vc)) if vc else None))
            van_rules = sum(len(s["rules"]) for s in index.sheets if s.get("bundle") == p.name) if index else None
            row["rules"] = sum(len(s["rules"]) for s in sheets)
            row["rules_vanilla"] = van_rules
        elif aa_dir and (aa_dir / p.name).is_file():
            mine, base = _digests(p), _digests(aa_dir / p.name)
            diff = [pid for pid in mine if pid in base and mine[pid][:2] != base[pid][:2]]
            row.update(objects=len(mine), changed=len(diff), added=len(set(mine) - set(base)), removed=len(set(base) - set(mine)))
            cat = {c["path_id"]: c for c in images.scan_bundle(p)}
            for pid in diff:
                c = cat.get(str(pid))
                out["images_changed"].append({"bundle": p.name, "path_id": str(pid), "label": mine[pid][2],
                                              "kind": c["kind"] if c else "object", "name": c["name"] if c else mine[pid][2],
                                              "w": c["w"] if c else None, "h": c["h"] if c else None})
        else:
            row["note"] = "no bundle with this name in the game"
        out["bundles"].append(row)
    return out


def load(path, index, aa_dir=None):
    p = Path(path).expanduser()
    if not p.exists():
        raise FileNotFoundError("not found: %s" % p)
    if p.is_dir() and (p / "skin.json").is_file():
        return load_uss_skin(p, index)
    files = [p] if p.is_file() else sorted(p.glob("*.bundle"))
    if p.is_dir() and not files:
        files = sorted(p.rglob("*.bundle"))[:200]
    if not files:
        raise ValueError("no skin.json and no .bundle files in %s" % p)
    return load_bundles(files, index, aa_dir)


def as_project(report, name="comparison"):
    """The comparison's colour tokens as a project (token overrides only): for the preview, or to start a new project."""
    p = project_mod.new(name)
    for t in report.get("tokens_changed", []):
        v = t["theirs"].strip()
        c = colour.parse(v)
        if c:
            val = colour.to_obj(c)
        elif VAR.fullmatch(v):
            val = v
        else:
            continue
        p["token_overrides"].append({"token": t["token"], "value": val, "vanilla": t.get("vanilla", "")})
    return project_mod.validate(project_mod.migrate(p))
