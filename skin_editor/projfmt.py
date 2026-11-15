"""Folder project format (fm-skin-project/1): a skin is a folder of text files, not one JSON blob.

  <workspace>/projects/<name>/
    skin.project.json          format, name, target (native|bundles), mode, the game build it was authored on
    mapping.json               which source lands where: token sheet, rule sheets -> game stylesheet, images -> image slot
    styles/tokens.uss          :root { --token: value; }            token overrides
    styles/<Sheet>.uss         rules appended to that game stylesheet (one file per target sheet)
    config/options.json        options, literal swaps, class renames, contrast pairs, reverts
    images/                    replacement images and SVGs

The files are the source of truth. read() compiles them to the project model the build pipelines already use (the dict of
project.py); write() prints a model as files. Text keeps everything the model holds: a colour is written as #RRGGBB or
rgba(r, g, b, a) with the full alpha float, and fields with no USS form (vanilla value, why, note, on) ride in a
/* meta: {json} */ comment in front of the declaration or rule they belong to. Comments and layout a user writes by hand are
kept by the text API (files are written as given); only a save through the model API regenerates a file."""
import json
import re
import shutil
from pathlib import Path

from . import colour
from . import project as project_mod

FORMAT = "fm-skin-project/1"
MARK = "skin.project.json"
MODE_NAMES = {"expert": "advanced"}          # the mode called "expert" until 1.2.0 is "advanced" now; the field is inert metadata (never read for behaviour), renamed with the interface


def migrate_modes(ws):
    """Rewrite `"mode": "expert"` as `"advanced"` in every project folder's skin.project.json (nothing else in the file changes). Returns the names changed."""
    changed = []
    for name in names(ws):
        f = folder(ws, name) / MARK
        if not f.is_file():
            continue
        head = _json(f, {})
        if head.get("mode") in MODE_NAMES:
            head["mode"] = MODE_NAMES[head["mode"]]
            f.write_text(json.dumps(head, indent=2) + "\n", encoding="utf-8")
            changed.append(name)
    return changed
TOKENS = "styles/tokens.uss"
DEFAULT_SHEET = "AlwaysAppliedStyleSheet"
SHEET_FILE = re.compile(r"styles/([A-Za-z0-9_.-]+)\.uss")
REL = re.compile(r"(?:[A-Za-z0-9_][\w .@()-]*/)*[A-Za-z0-9_][\w .@()-]*")
TEXT_EXT = (".uss", ".json", ".md", ".txt")
IMAGE_EXT = (".png", ".jpg", ".jpeg", ".webp", ".svg")


class ProjectProblem(ValueError):
    """A project folder that cannot be compiled. problems: [{file, line, message}]"""

    def __init__(self, problems):
        super().__init__("; ".join("%s:%s %s" % (p["file"], p.get("line", "?"), p["message"]) for p in problems[:5]))
        self.problems = problems


def folder(ws, name):
    if not project_mod.NAME_RE.fullmatch(name):
        raise ValueError("bad project name")
    return ws.projects / name


def is_folder(ws, name):
    return (folder(ws, name) / MARK).is_file()


def names(ws):
    return sorted(p.name for p in ws.projects.iterdir() if p.is_dir() and (p / MARK).is_file())


# ---------------------------------------------------------------- USS text <-> rules (comments kept as metadata)
DIRECTIVE = re.compile(r"\s*(replace|remove)\s*(?::(.*))?$", re.S)   # /* replace: <selector> */ before a rule; /* remove: <selector> | prop, prop */
TOKEN = re.compile(r"/\*(.*?)\*/|(\"(?:\\.|[^\"\\\n])*\"|'(?:\\.|[^'\\\n])*')|([{};])", re.S)    # comments, quoted strings (kept whole), structure


def parse_uss(text, file="?"):
    """[{selector, decls: [(prop, value, meta)], meta, line}] and problems. A /* meta: {...} */ comment belongs to the next rule
    (outside a block) or the next declaration (inside one); other comments are ignored here (the text API keeps them)."""
    rules, problems = [], []
    pos, line, buf, cur, pending, want_replace = 0, 1, "", None, None, None

    def meta_of(comment):
        m = re.match(r"\s*meta:\s*(\{.*\})\s*$", comment, re.S)
        if not m:
            return None
        try:
            return json.loads(m.group(1))
        except ValueError:
            problems.append({"file": file, "line": line, "message": "meta comment is not valid JSON"})
            return None

    for m in TOKEN.finditer(text):
        chunk = text[pos:m.start()]
        buf += chunk
        line += chunk.count("\n")
        pos = m.end()
        if m.group(1) is not None:                         # a comment
            md = meta_of(m.group(1))
            if md is not None:
                pending = md
            dm = DIRECTIVE.match(m.group(1))
            if dm:
                kind, arg = dm.group(1), " ".join((dm.group(2) or "").split())
                if cur is not None:
                    problems.append({"file": file, "line": line, "message": "%s: belongs between rules, not inside one" % kind})
                elif kind == "replace":
                    want_replace = (arg, line)
                else:
                    sel, _, names = arg.partition("|")
                    sel = sel.strip()
                    if not sel:
                        problems.append({"file": file, "line": line, "message": "remove: needs a selector (/* remove: .selector | property, property */)"})
                    else:
                        rules.append({"selector": sel, "decls": [], "meta": pending or {}, "line": line, "op": "remove",
                                      "remove": [n.strip() for n in names.split(",") if n.strip()]})
                        pending = None
            line += m.group(0).count("\n")
            continue
        if m.group(2) is not None:                         # a quoted string: part of the current selector or value
            buf += m.group(2)
            continue
        ch = m.group(3)
        if ch == "{":
            if cur is not None:
                problems.append({"file": file, "line": line, "message": "nested '{' is not supported"})
            cur = {"selector": " ".join(buf.split()), "decls": [], "meta": pending or {}, "line": line}
            if not cur["selector"]:
                problems.append({"file": file, "line": line, "message": "rule without a selector"})
            if want_replace:
                cur["op"] = "replace"
                if want_replace[0] and want_replace[0] != cur["selector"]:
                    problems.append({"file": file, "line": want_replace[1], "message": "replace: names %s but the rule below is %s (they must be the same selector)" % (want_replace[0], cur["selector"])})
            pending, buf, want_replace = None, "", None
        elif ch == ";" or ch == "}":
            if cur is None:
                if buf.strip() or ch == "}":
                    problems.append({"file": file, "line": line, "message": "unexpected '%s' outside a rule" % ch})
                buf = ""
                continue
            d = buf.strip()
            if d:
                if ":" not in d:
                    problems.append({"file": file, "line": line, "message": "declaration without ':' : %s" % d[:40]})
                else:
                    k, v = d.split(":", 1)
                    cur["decls"].append((k.strip(), " ".join(v.split()), pending or {}, line))
                pending = None
            buf = ""
            if ch == "}":
                rules.append(cur)
                cur = None
    if cur is not None:
        problems.append({"file": file, "line": cur["line"], "message": "rule is not closed with '}'"})
    elif text[pos:].strip() and not text[pos:].strip().startswith("/*"):
        problems.append({"file": file, "line": line, "message": "text after the last rule"})
    return rules, problems


def _val(text):
    """USS value text -> project value (a colour becomes the canonical object, anything else stays text)."""
    return colour.canonical(text)


def _txt(v):
    return project_mod.patch_text(v)


def _meta(d):
    return "/* meta: %s */" % json.dumps(d, ensure_ascii=False, sort_keys=True) if d else ""


def tokens_text(p):
    lines = ["/* Token overrides. One declaration per token; the value replaces the token's definition in every game sheet. */", ":root {"]
    for e in p.get("token_overrides", []):
        extra = {k: v for k, v in e.items() if k not in ("token", "value")}
        if extra:
            lines.append("    " + _meta(extra))
        lines.append("    %s: %s;" % (e["token"], _txt(e["value"])))
    lines.append("}")
    return "\n".join(lines) + "\n"


def rules_text(sheet, rules):
    out = ["/* Rules appended to the game stylesheet %s (they win ties against its own rules; Build raises specificity where needed).\n"
           "   A comment 'replace: .sel' right before a rule changes the game's own rule with that exact selector in place (bundle target);\n"
           "   a comment 'remove: .sel | prop, prop' drops those declarations from it (no list: all of them). */" % sheet]
    for e in rules:
        extra = {k: v for k, v in e.items() if k not in ("sheet", "selector", "props", "op", "remove")}
        if extra:
            out.append(_meta(extra))
        if e.get("op") == "remove":
            out.append("/* remove: %s%s */" % (e["selector"], (" | " + ", ".join(e["remove"])) if e.get("remove") else ""))
            continue
        if e.get("op") == "replace":
            out.append("/* replace: %s */" % e["selector"])
        out.append("%s {" % e["selector"])
        for k, v in e["props"].items():
            out.append("    %s: %s;" % (k, _txt(v)))
        out.append("}")
    return "\n".join(out) + "\n"


# ---------------------------------------------------------------- write (model -> files)
def write(ws, p, images_from=None):
    """Write the model as a project folder (creating or regenerating styles/, config/, mapping.json, skin.project.json).
    images_from: a folder whose files are copied into images/ (migration). Files in images/ are never deleted here."""
    p = project_mod.validate(project_mod.migrate(p))
    d = folder(ws, p["name"])
    (d / "styles").mkdir(parents=True, exist_ok=True)
    (d / "config").mkdir(exist_ok=True)
    (d / "images").mkdir(exist_ok=True)
    if images_from and Path(images_from).is_dir():
        for f in Path(images_from).iterdir():
            if f.is_file():
                shutil.copyfile(f, d / "images" / f.name)
    opts = dict(p.get("options", {}))
    target = opts.pop("output", "bundles")
    head = {"format": FORMAT, "name": p["name"], "target": target, "mode": "advanced", "game_build": p.get("game_build"),
            "vanilla_manifest": p.get("vanilla_manifest")}
    if p.get("native_name"):
        head["native_name"] = p["native_name"]
    old = _json(d / MARK, {})
    head["mode"] = MODE_NAMES.get(old.get("mode", "advanced"), old.get("mode", "advanced"))
    _put(d / MARK, json.dumps(head, indent=2) + "\n")
    _put(d / TOKENS, tokens_text(p))
    by_sheet = {}
    for e in p.get("scoped_rules", []):
        by_sheet.setdefault(e["sheet"], []).append(e)
    keep = set(p.get("native_sheets", []))
    empty = []
    for f in (d / "styles").glob("*.uss"):                    # rule sheets no longer in the model
        if f.name != "tokens.uss" and f.stem not in by_sheet and "styles/" + f.name not in keep:
            if not parse_uss(f.read_text(encoding="utf-8-sig"), f.name)[0]:
                empty.append(f.stem)                          # a new sheet still waiting for its first rule is kept
            else:
                f.unlink()
    entries = [{"source": TOKENS, "mode": "tokens"}]
    for s in p.get("native_sheets", []):
        entries.append({"source": s, "mode": "native-sheet"})
    for s in p.get("native_support", []):
        entries.append({"source": s, "mode": "native-asset"})
    for sheet, rules in by_sheet.items():
        _put(d / "styles" / (sheet + ".uss"), rules_text(sheet, rules))
        entries.append({"source": "styles/%s.uss" % sheet, "target": {"sheet": sheet}})
    for sheet in empty:
        entries.append({"source": "styles/%s.uss" % sheet, "target": {"sheet": sheet}})
    for f in p.get("font_swaps", []):
        entries.append({"source": "fonts/" + f["source"], "mode": "font", "target": {"token": f["token"]}})
    _write_layout_patches(d, p.get("layout_patches", []))
    _write_table_patches(d, p.get("table_patches", []))
    for e in p.get("image_swaps", []):
        ent = {"source": "images/" + e["source"], "target": {"kind": e["kind"], "bundle": e["bundle"], "path_id": e["path_id"], "name": e.get("name", "")}}
        for k in ("fit", "where", "note"):
            if k in e:
                ent[k] = e[k]
        entries.append(ent)
    _put(d / "mapping.json", json.dumps({"schema": 1, "entries": entries}, indent=2) + "\n")
    cfg = {"options": opts}
    for k in ("literal_swaps", "rename_classes", "contrast_pairs", "reverts", "tile_placement"):
        cfg[k] = p.get(k, {} if k == "rename_classes" else [])
    _put(d / "config" / "options.json", json.dumps(cfg, indent=2) + "\n")
    return d


def _write_layout_patches(d, docs):
    """layouts/<Layout>.patch.json, one small file per patched layout; files of layouts no longer patched are removed."""
    ld = d / "layouts"
    keep, used = set(), set()
    for doc in docs:
        base = re.sub(r"[^\w.-]", "_", doc["layout"]["name"])[:80] or "layout"
        fn = base
        if fn.lower() in used:
            fn = "%s-%s" % (base, str(doc["layout"].get("path_id", "x"))[-6:].lstrip("-"))
        used.add(fn.lower())
        ld.mkdir(exist_ok=True)
        _put(ld / (fn + ".patch.json"), json.dumps(doc, indent=2) + "\n")
        keep.add(fn + ".patch.json")
    if ld.is_dir():
        for f in ld.glob("*.patch.json"):
            if f.name not in keep:
                f.unlink()


def _write_table_patches(d, docs):
    """tables/<View>.patch.json, one small file per patched table view; files of views no longer patched are removed."""
    td = d / "tables"
    keep = set()
    for doc in docs:
        fn = re.sub(r"[^\w.-]", "_", doc["view"]["name"])[:80] or "view"
        td.mkdir(exist_ok=True)
        _put(td / (fn + ".patch.json"), json.dumps(doc, indent=2) + "\n")
        keep.add(fn + ".patch.json")
    if td.is_dir():
        for f in td.glob("*.patch.json"):
            if f.name not in keep:
                f.unlink()


def _put(path, text):
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(text, encoding="utf-8", newline="\n")
    tmp.replace(path)


def _json(path, default, problems=None, rel=None):
    if not path.is_file():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except ValueError as ex:
        if problems is not None:
            problems.append({"file": rel or path.name, "line": getattr(ex, "lineno", 1), "message": "not valid JSON: %s" % ex})
        return default


# ---------------------------------------------------------------- read (files -> model)
def read(ws, name, strict=True):
    """The project model compiled from the folder. strict: raise ProjectProblem on any problem; otherwise return (model, problems)
    with whatever could be compiled (the editor shows the problems)."""
    d = folder(ws, name)
    if not (d / MARK).is_file():
        raise FileNotFoundError("no project folder: %s" % name)
    problems = []
    head = _json(d / MARK, {}, problems, MARK)
    if head.get("format") != FORMAT:
        problems.append({"file": MARK, "line": 1, "message": "format must be %s" % FORMAT})
    cfg = _json(d / "config" / "options.json", {}, problems, "config/options.json")
    mapping = _json(d / "mapping.json", {"entries": []}, problems, "mapping.json")
    p = project_mod.new(name, head.get("game_build"))
    p["vanilla_manifest"] = head.get("vanilla_manifest")
    if head.get("native_name"):
        p["native_name"] = head["native_name"]
    p["options"] = dict(cfg.get("options", p["options"]), output=head.get("target", "bundles"))
    for k in ("literal_swaps", "rename_classes", "contrast_pairs", "reverts", "tile_placement"):
        if k in cfg:
            p[k] = cfg[k]
    seen_sources = set()
    for n, ent in enumerate(mapping.get("entries", []) if isinstance(mapping.get("entries"), list) else []):
        src = ent.get("source", "") if isinstance(ent, dict) else ""
        where = {"file": "mapping.json", "line": n + 1}
        if not REL.fullmatch(src) or ".." in src:
            problems.append(dict(where, message="bad source path: %r" % src))
            continue
        seen_sources.add(src)
        f = d / src
        if not f.is_file():
            problems.append(dict(where, message="source file is missing: %s" % src))
            continue
        if ent.get("mode") in ("native-sheet", "native-asset"):   # part of an imported native skin: used by the native target only
            if src.startswith("native/"):
                problems.append(dict(where, message="old project layout (native/ folder). Delete this project and import the skin folder again"))
                continue
            if ent["mode"] == "native-sheet":
                if not src.startswith("styles/") or not src.lower().endswith(".uss"):
                    problems.append(dict(where, message="an imported sheet lives in styles/ and ends in .uss"))
                    continue
                p.setdefault("native_sheets", []).append(src)
            else:
                if src.split("/", 1)[0] not in ("images", "fonts", "assets"):
                    problems.append(dict(where, message="an imported file lives in images/, fonts/ or assets/"))
                    continue
                p.setdefault("native_support", []).append(src)
            continue
        if ent.get("mode") == "font":
            t = (ent.get("target") or {}).get("token")
            if not src.startswith("fonts/") or not project_mod.FONT_FILE.fullmatch(src[len("fonts/"):]) or not t:
                problems.append(dict(where, message="a font entry needs source fonts/<file>.ttf|otf and target.token"))
                continue
            p.setdefault("font_swaps", []).append({"token": t, "source": src[len("fonts/"):]})
            continue
        if ent.get("mode") == "tokens":
            rules, pr = parse_uss(f.read_text(encoding="utf-8-sig"), src)
            problems += pr
            for r in rules:
                if r["selector"] != ":root":
                    problems.append({"file": src, "line": r["line"], "message": "a token sheet only holds :root { --token: value; }"})
                    continue
                for k, v, meta, ln in r["decls"]:
                    if not k.startswith("--"):
                        problems.append({"file": src, "line": ln, "message": "not a token (must start with --): %s" % k})
                        continue
                    p["token_overrides"] = [o for o in p["token_overrides"] if o["token"] != k]     # a later declaration wins
                    p["token_overrides"].append(dict({"token": k, "value": _val(v)}, **meta))
        elif src.lower().endswith(".uss"):
            sheet = (ent.get("target") or {}).get("sheet")
            if not sheet:
                problems.append(dict(where, message="a rule sheet needs target.sheet (the game stylesheet it is appended to)"))
                continue
            rules, pr = parse_uss(f.read_text(encoding="utf-8-sig"), src)
            problems += pr
            for r in rules:
                e = dict({"sheet": sheet, "selector": r["selector"], "props": {k: _val(v) for k, v, _, _ in r["decls"]}}, **r["meta"])
                if r.get("op") == "remove":
                    p["scoped_rules"].append(dict(e, op="remove", remove=r["remove"]))
                    continue
                if r.get("op") == "replace":
                    e["op"] = "replace"
                if not e["props"]:
                    problems.append({"file": src, "line": r["line"], "message": "rule without declarations"})
                    continue
                p["scoped_rules"].append(e)
        else:
            t = ent.get("target") or {}
            e = {"bundle": t.get("bundle"), "path_id": t.get("path_id"), "name": t.get("name", ""), "kind": t.get("kind"), "source": src.split("/", 1)[1] if src.startswith("images/") else src}
            if not src.startswith("images/"):
                problems.append(dict(where, message="image sources live in images/"))
                continue
            for k in ("fit", "where", "note"):
                if k in ent:
                    e[k] = ent[k]
            p["image_swaps"].append(e)
    for f in sorted((d / "tables").glob("*.patch.json")) if (d / "tables").is_dir() else []:
        rel = "tables/" + f.name
        doc = _json(f, None, problems, rel)
        if doc is None:
            continue
        try:
            from . import tables as tables_mod
            p.setdefault("table_patches", []).append(tables_mod.validate_doc(doc))
        except ValueError as ex:
            problems.append({"file": rel, "line": 1, "message": str(ex)})
    for f in sorted((d / "layouts").glob("*.patch.json")) if (d / "layouts").is_dir() else []:
        rel = "layouts/" + f.name
        doc = _json(f, None, problems, rel)
        if doc is None:
            continue
        try:
            from . import uxml
            p.setdefault("layout_patches", []).append(uxml.validate_doc(doc))
        except ValueError as ex:
            problems.append({"file": rel, "line": 1, "message": str(ex)})
    for f in sorted((d / "styles").glob("*.uss")) if (d / "styles").is_dir() else []:
        if "styles/" + f.name not in seen_sources:
            problems.append({"file": "styles/" + f.name, "line": 1, "message": "not in mapping.json: this sheet is not built (add an entry with target.sheet)"})
    try:
        p = project_mod.validate(project_mod.migrate(p))
    except (ValueError, KeyError, TypeError) as ex:
        problems.append({"file": _blame(str(ex)), "line": 1, "message": str(ex)})
    if strict and problems:
        raise ProjectProblem(problems)
    return p if strict else (p, problems)


URL_RE = re.compile(r"""url\(\s*(["']?)([^)"']+)\1\s*\)""")
IMG_EXT = {".png", ".jpg", ".jpeg", ".gif", ".bmp", ".tga", ".svg", ".webp"}
FONT_EXT = {".ttf", ".otf", ".woff", ".woff2"}


def _category(rel):
    ext = Path(rel).suffix.lower()
    return "images" if ext in IMG_EXT else "fonts" if ext in FONT_EXT else "assets"


def _unique(taken, rel):
    """rel, or rel with -2, -3 ... before the extension when taken."""
    q = Path(rel)
    cand, n = rel, 1
    while cand.lower() in taken:
        n += 1
        cand = q.with_name("%s-%d%s" % (q.stem, n, q.suffix)).as_posix()
    taken.add(cand.lower())
    return cand


def import_native_skin(ws, src, name):
    """A native USS skin folder (skin.json + sheets + images/fonts) as a project, in the normal project layout: sheets go to styles/
    (listed in order in mapping.json, mode native-sheet), pictures to images/, fonts to fonts/, anything else to assets/ (mode
    native-asset). url() paths in the sheets are rewritten to point at the new places. The project's own tokens/rules/images are
    written after them, so they win ties. Nothing in the source folder is modified."""
    src = Path(src)
    man = json.loads((src / "skin.json").read_text(encoding="utf-8-sig"))
    sheets = man.get("Sheets")
    if not isinstance(sheets, list) or not sheets:
        raise ValueError("skin.json has no Sheets list")
    d = folder(ws, name)
    if d.exists():
        raise ValueError("a project named %s already exists" % name)
    srcroot = src.resolve()
    for s in sheets:
        if not (src / s).is_file():
            raise FileNotFoundError("sheet listed in skin.json is missing: %s" % s)
    taken = {"tokens.uss", "rules.uss", "images.uss"}       # the names the native export writes itself: an imported sheet of that name (a skin this Studio saved) is renamed, or its export collides (found by S7's round trip)
    sheet_dest = {}                                          # source sheet (posix, relative) -> styles/<name>.uss
    for s in sheets:
        s = s.replace("\\", "/")
        sheet_dest[s] = "styles/" + _unique(taken, Path(s).name)
    asset_taken, asset_dest = set(), {}                      # absolute source file -> project path
    for f in sorted(src.rglob("*")):
        if f.is_file() and f.name != "skin.json" and f.suffix.lower() != ".uss":
            rel = f.relative_to(src).as_posix()
            asset_dest[f.resolve()] = _category(f.name) + "/" + _unique(asset_taken, rel)
    notes = []
    texts = {}
    for s, dest in sheet_dest.items():
        sdir = (src / s).parent
        def fix(m, sdir=sdir, s=s):
            u = m.group(2).strip()
            if re.match(r"^(?:[a-z][a-z0-9+.-]*:|/)", u, re.I):
                return m.group(0)
            target = (sdir / u).resolve()
            if srcroot not in target.parents or target not in asset_dest:
                notes.append("%s: url(%s) points at a file that is not in the skin folder; left as it was" % (s, u))
                return m.group(0)
            return 'url("../%s")' % asset_dest[target]
        texts[dest] = URL_RE.sub(fix, (src / s).read_text(encoding="utf-8-sig"))
    p = project_mod.new(name)
    p["options"]["output"] = "native"
    p["native_sheets"] = list(sheet_dest.values())
    p["native_support"] = sorted(asset_dest.values())
    p["native_name"] = man.get("Name") or src.name
    try:
        write(ws, p)
        for dest, text in texts.items():
            _put(d / dest, text)
        for f, dest in asset_dest.items():
            (d / dest).parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(f, d / dest)
        read(ws, name)                                       # must compile
    except Exception:
        shutil.rmtree(d, ignore_errors=True)
        raise
    from . import changes
    changes.record(name, "file", ["imported native skin"])
    return {"folder": str(d), "name": p["native_name"], "sheets": len(sheets), "files": len(tree(ws, name)),
            "images": sum(1 for v in asset_dest.values() if v.startswith("images/")), "fonts": sum(1 for v in asset_dest.values() if v.startswith("fonts/")), "notes": notes}


def create_sheet(ws, name, sheet):
    """A new, empty rule sheet styles/<sheet>.uss for the game stylesheet <sheet>, listed in mapping.json. Returns its project path."""
    if not SHEET_FILE.fullmatch("styles/%s.uss" % sheet) or sheet == "tokens":
        raise ValueError("a sheet name is letters, digits, _ . - (the game stylesheet its rules are appended to)")
    rel = "styles/%s.uss" % sheet
    f = folder(ws, name) / rel
    if f.exists():
        raise ValueError("%s already exists" % rel)
    p, _ = read(ws, name, strict=False)
    _put(f, "/* Rules for the game stylesheet %s. A comment 'replace: .sel' before a rule edits the game's own rule in place;\n   'remove: .sel | prop' deletes declarations (bundle target). */\n" % sheet)
    write(ws, p)
    from . import changes
    changes.record(name, "file", [rel])
    return rel


def _blame(msg):
    """Best guess of the file a model validation error comes from."""
    m = msg.lower()
    if "token" in m:
        return TOKENS
    if "image swap" in m or "where must" in m or "fit must" in m:
        return "mapping.json"
    if "selector" in m or "property" in m or "rule" in m:
        return "styles/"
    return "config/options.json"


# ---------------------------------------------------------------- files (text API for the editor)
def tree(ws, name):
    """[{path, kind: text|image|other, bytes}] of the project folder (packages/ and dot-folders left out)."""
    d = folder(ws, name)
    out = []
    for f in sorted(d.rglob("*")):
        rel = f.relative_to(d).as_posix()
        if not f.is_file() or rel.startswith(("packages/", ".")) or "/." in rel or rel.endswith(".tmp"):
            continue
        ext = f.suffix.lower()
        out.append({"path": rel, "kind": "text" if ext in TEXT_EXT else "image" if ext in IMAGE_EXT else "other", "bytes": f.stat().st_size})
    return out


def _safe(ws, name, rel):
    d = folder(ws, name)
    if not (d / MARK).is_file():
        raise FileNotFoundError("no project folder: %s" % name)
    if not REL.fullmatch(rel) or ".." in rel.split("/"):
        raise ValueError("bad path: %r" % rel)
    f = (d / rel).resolve()
    if d.resolve() not in f.parents:
        raise ValueError("path leaves the project folder")
    return f


def search(ws, name, q, regex=False, case=False, limit=500):
    """Find text in the project's text files: [{path, line, col, text}] (text = the line, trimmed), at most `limit`; truncated flag."""
    if not q:
        return {"hits": [], "truncated": False}
    flags = 0 if case else re.I
    try:
        rx = re.compile(q if regex else re.escape(q), flags)
    except re.error as ex:
        raise ValueError("bad regular expression: %s" % ex)
    hits = []
    for t in tree(ws, name):
        if t["kind"] != "text":
            continue
        for n, line in enumerate(read_file(ws, name, t["path"]).splitlines(), 1):
            m = rx.search(line)
            if m:
                hits.append({"path": t["path"], "line": n, "col": m.start() + 1, "text": line.strip()[:200]})
                if len(hits) >= limit:
                    return {"hits": hits, "truncated": True}
    return {"hits": hits, "truncated": False}


def read_file(ws, name, rel):
    f = _safe(ws, name, rel)
    if f.suffix.lower() not in TEXT_EXT:
        raise ValueError("not a text file: %s" % rel)
    return f.read_text(encoding="utf-8-sig")


def write_file(ws, name, rel, text):
    """Store one text file exactly as given, then compile the project: returns the problems (the file is kept either way, as in
    any editor; a project with problems does not build)."""
    f = _safe(ws, name, rel)
    if f.suffix.lower() not in TEXT_EXT:
        raise ValueError("not a text file: %s" % rel)
    if len(text) > 4 * 1024 * 1024:
        raise ValueError("file too large")
    f.parent.mkdir(parents=True, exist_ok=True)
    _put(f, text)
    from . import changes
    changes.record(name, "file", [rel])
    return read(ws, name, strict=False)[1]


def delete_file(ws, name, rel):
    f = _safe(ws, name, rel)
    if rel in (MARK, "mapping.json", "config/options.json", TOKENS):
        raise ValueError("%s is part of every project and cannot be deleted" % rel)
    f.unlink()
    from . import changes
    changes.record(name, "file", [rel])
    return read(ws, name, strict=False)[1]


# ---------------------------------------------------------------- migration
def migrate_legacy(ws, name):
    """<name>.skin.json (+ <workspace>/images/<name>/) -> projects/<name>/. The JSON file is kept as <name>.skin.json.migrated.
    The folder must compile to exactly the model it was written from, or nothing is changed."""
    legacy = ws.projects / (name + ".skin.json")
    if not legacy.is_file():
        raise FileNotFoundError("no legacy project file: %s" % legacy.name)
    if (folder(ws, name)).exists():
        raise ValueError("a folder named %s already exists in projects/" % name)
    before = project_mod.validate(project_mod.migrate(json.loads(legacy.read_text(encoding="utf-8-sig"))))
    d = write(ws, before, images_from=ws.images / name)
    try:
        after = read(ws, name)
        if _norm(after) != _norm(before):
            raise ProjectProblem([{"file": MARK, "line": 1, "message": "the folder does not compile back to the same project (differs in: %s)"
                                   % ", ".join(k for k in before if _norm(after).get(k) != _norm(before).get(k))}])
    except Exception:
        shutil.rmtree(d, ignore_errors=True)
        raise
    legacy.rename(legacy.with_name(legacy.name + ".migrated"))
    from . import changes
    changes.record(name, "file", ["migrated to a folder project"])
    return {"folder": str(d), "files": [t["path"] for t in tree(ws, name)]}


def _norm(p):
    """The model with scoped rules grouped by sheet (the folder keeps the order inside each sheet, which is what a build uses)."""
    q = json.loads(json.dumps(p))
    by = {}
    for e in q.get("scoped_rules", []):
        by.setdefault(e["sheet"], []).append(e)
    q["scoped_rules"] = [e for s in by for e in by[s]]
    return q
