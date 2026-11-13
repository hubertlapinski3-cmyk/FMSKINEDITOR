"""Export a project as a native FM27 skin: Documents/Sports Interactive/Football Manager 27/skins/<id>/ with skin.json, USS sheets
and the images they use. FM27 loads these itself (Preferences, next to "Reload Skin"); no game file is changed, so the skin
survives updates. The loader (FM.Lattice / SI.Lattice) only reads files inside the skin folder, so every image is copied in.

What maps to USS:
  token overrides          :root { --token: value }                                         (tokens.uss)
  literal swaps            one rule per game rule that uses the colour, same selector, new colour (later sheet wins ties)
  scoped rules             as written                                                        (rules.uss)
  "remove club colours"    the proven rules, plus .nav-on-light rules set to their dark-bar values (USS cannot rename classes)
  icon swaps               .<icon class> { background-image: url("images/...png") } for every class the game's FMImages
                           stylesheets map to that icon (PNG at 4x; an SVG source is rasterised)       (images.uss)
  SVG swaps                same, through the FMImages_SVG classes (rasterised PNG at 8x)
  texture swaps            wallpapers are chosen in code, so the skin hides or covers the game's picture and paints the image on
                           the chosen places (PLACES; default from the texture's name), as the Jonukas skin does
Not expressible either: class renames, flatten_gradients (listed in the export report)."""
import io
import json
import os
import re
import shutil
import sys
import time
from pathlib import Path

from . import club_colours, colour, images
from . import project as project_mod

ID_RE = re.compile(r"[A-Za-z0-9][\w.-]{0,63}")

# Where a wallpaper can be shown in a native skin. The game picks its wallpaper textures in code, so a skin cannot replace them;
# like the Jonukas skin, it hides the code-set image where needed and paints its own picture on a container USS reaches.
PLACES = {
    "report-pages": ("Report and tool pages (player, club, competition, squad report ...)",
                     ["#Card-frame > #Header, #Card-frame > #GridSafeArea"],
                     ['#Card-frame {\n    --unity-image-tint-color: #00000000;\n}\n', '#Card-frame > * {\n    --unity-image-tint-color: #FFFFFF;\n}\n']),
    "main-screens": ("Main screens (portal, squad, tactics, recruitment, training, club ...)", [".base-layer-content"], []),
    "start-screen": ("Start screen", ["#intro-panel"], []),
    "loading": ("Loading and modal screens", ["#Background.modal-sheet-background", "#fullscreen-center > VisualElement"], []),
    "match-intro": ("Match intro, team news, tunnel interview", ["BindingRoot.panel-fade > VisualElement.row-direction-normal", "Panel#TeamNewsPanel, Panel#TunnelInterviewPanel"], []),
}


def default_places(name):
    """A sensible 'where' for a wallpaper texture from its name (the user can change it)."""
    n = name.lower()
    if "start_screen" in n or "newgame" in n:
        return ["start-screen"]
    if "background-texture" in n or "loading" in n:
        return ["loading"]
    if "lineup" in n or "prematch" in n:
        return ["match-intro"]
    return ["report-pages", "main-screens"]


def nav_on_light_rules(index):
    """Club colours removed: the bar is dark for every club, but on light club colours the game still adds .nav-on-light, whose
    rules set dark text and icons. For each such rule, write the same selector with the value the dark-bar variant (.nav-on-dark,
    or the selector without the class) uses. Returns (rules, count)."""
    if index is None:
        return [], 0
    lookup = {}
    for sh in index.sheets:
        for r in sh["rules"]:
            for s in r["s"]:
                d = lookup.setdefault(" ".join(s.split()), {})
                for name, val, _ in r["p"]:
                    d[name] = val
    out, n = [], 0
    for sh in index.sheets:
        for r in sh["rules"]:
            for s in r["s"]:
                if "nav-on-light" not in s:
                    continue
                cands = [s.replace("nav-on-light", "nav-on-dark"), re.sub(r"\.nav-on-light\b", "", s)]
                cands = [" ".join(c.replace(" > ", " ").split()) if c.strip().startswith(">") else " ".join(c.split()) for c in cands]
                props = {}
                for name, val, _ in r["p"]:
                    for c in cands:
                        if c and name in lookup.get(c, {}):
                            props[name] = lookup[c][name]
                            break
                if props:
                    out.append(_rule(s, props))
                    n += 1
    return out, n


def skins_root():
    """The FM27 user folder's skins folder (created on export). Windows: Documents (or OneDrive Documents); macOS: Application
    Support. Returns the path even when it does not exist yet; None when no FM27 user folder is found."""
    from . import userdirs
    folder = userdirs.user_folder()
    return folder / "skins" if folder else None


def _value(v):
    """Project value -> USS text. Colours as #RRGGBB or #RRGGBBAA (the 8-digit form USS reads)."""
    if colour.is_obj(v):
        c = colour.from_obj(v)
        return colour.hex6(c) if colour.unit_to_byte(c[3]) == 255 else colour.hex8(c)
    return str(v).strip()


def _rule(sel, props):
    body = "".join("    %s: %s;\n" % (k, _value(v)) for k, v in props.items())
    return "%s {\n%s}\n" % (sel, body)


def literal_rules(project, index):
    """USS cannot swap a literal everywhere, so each game rule that uses a swapped colour gets a copy with the new colour."""
    out, notes = [], []
    if index is None:
        return out, ["literal swaps skipped: build the style index first"]
    for e in project.get("literal_swaps", []):
        f, t = colour.from_obj(e["from"]), colour.from_obj(e["to"])
        if e["mode"] == "rgba":
            hits = index.literal(colour.hex6(f), f[3])["exact"]
        else:
            hits = index.literal(colour.hex6(f), 1.0)["rgb_all"]
        n = 0
        for h in hits:
            if h.get("token_def"):
                continue                       # a token definition: the token override route covers it (as :root here)
            hc = colour.from_obj({"rgb": h["rgb"], "a": h["a"]})
            new = t if e["mode"] == "rgba" else (t[0], t[1], t[2], hc[3])
            old_txt = [colour.hex6(hc), colour.hex8(hc), colour.text(hc)]
            val = h["value"]
            nv = _value(colour.to_obj(new))
            if colour.parse(val.strip()) is not None:
                val2 = nv
            else:
                val2 = val
                for o in old_txt:
                    val2 = re.sub(re.escape(o), nv, val2, flags=re.I)
                if val2 == val:
                    continue
            out.append(_rule(", ".join(h["selectors"]), {h["property"]: val2}))
            n += 1
        notes.append("literal %s -> %s (%s): %d rule(s)" % (colour.text(f), colour.text(t), e["mode"], n))
    # the same selector+property may appear twice when two swaps touch one rule: later wins, as in the build
    return out, notes


def export(ws, project, index, aa_dir, dest_root, skin_id=None, display=None):
    """Write the skin folder; returns a report {folder, sheets, images, rules, skipped, notes}. Overwrites only a folder this
    exporter wrote before (it carries .fm27se-export.json)."""
    p = project_mod.validate(project_mod.migrate(project))
    skin_id = skin_id or p["name"]
    if not ID_RE.fullmatch(skin_id):
        raise ValueError("skin folder name: letters, digits, dot, dash, underscore")
    final = Path(dest_root) / skin_id
    if final.exists() and not (final / ".fm27se-export.json").is_file():
        raise ValueError("%s exists and was not written by this editor; choose another name" % final)
    tmp = final.with_name(".%s.new" % skin_id)             # written aside and swapped in, so a failed export never destroys the skin that is there
    shutil.rmtree(tmp, ignore_errors=True)
    try:
        report = _export(ws, p, index, aa_dir, tmp, skin_id, display)
    except BaseException:
        shutil.rmtree(tmp, ignore_errors=True)
        raise
    if final.exists():
        shutil.rmtree(final)
    tmp.rename(final)
    report["folder"] = str(final)
    (final / ".fm27se-export.json").write_text(json.dumps(report, indent=1), encoding="utf-8")
    return report


def _export(ws, p, index, aa_dir, dest, skin_id, display):
    marker = dest / ".fm27se-export.json"
    (dest / "images").mkdir(parents=True)
    skipped, notes = [], []
    spec = project_mod.to_spec(p)

    # tokens
    toks = {e["token"]: e["value"] for e in p.get("token_overrides", []) if e["token"] not in set(p.get("reverts", []))}
    fonts_written, font_problems = 0, []
    pdir = None
    for fs in p.get("font_swaps", []):                         # a font is a token set to url("fonts/<file>"), the way native skins load them
        from . import projfmt
        pdir = pdir or projfmt.folder(ws, p["name"])
        src = pdir / "fonts" / fs["source"]
        if not src.is_file():
            font_problems.append("font %s for %s is missing from the project's fonts folder" % (fs["source"], fs["token"]))
            continue
        if fs["token"] in toks:
            notes.append("font for %s replaces the colour/value override of the same token" % fs["token"])
        (dest / "fonts").mkdir(exist_ok=True)
        out_f = dest / "fonts" / fs["source"]
        if not out_f.exists():
            shutil.copyfile(src, out_f)
        toks[fs["token"]] = 'url("fonts/%s")' % fs["source"]
        fonts_written += 1
    tokens_uss = "/* Token overrides of project %s (FM27 Skin Editor). */\n" % p["name"] + (_rule(":root", toks) if toks else "")

    # rules: club colours first (the project's own rules win ties), literal copies, scoped rules
    rules = []
    if p.get("options", {}).get("club_colours", True) is False:
        for r in club_colours.rules(p["options"].get("club_colours_replacement", project_mod.CLUB_DEFAULT)):
            rules.append(_rule(r["selector"], r["props"]))
        nav, n_nav = nav_on_light_rules(index)
        rules += nav
        notes.append("club colours: %d .nav-on-light rule(s) set to their dark-bar values (instead of the bundle build's class rename)" % n_nav)
    lit, lit_notes = literal_rules(p, index)
    rules += lit
    notes += lit_notes
    for e in p.get("scoped_rules", []):
        if e.get("op") == "remove":
            skipped.append("remove: %s%s cannot be expressed in a native skin (USS cannot delete a game declaration); use the bundle target" % (
                e["selector"][:60], (" | " + ", ".join(e["remove"])) if e.get("remove") else ""))
            continue
        rules.append(_rule(e["selector"], e["props"]))                 # a replace is written as a normal rule: it wins ties against the game's own
    if p.get("rename_classes"):
        skipped.append("class renames (%d) cannot be expressed in USS" % len(p["rename_classes"]))
    if p.get("options", {}).get("flatten_gradients"):
        skipped.append("flatten_gradients is a bundle-build option; not exported")
    rules_uss = "/* Rules of project %s (FM27 Skin Editor). */\n" % p["name"] + "".join(rules)

    # images
    img_rules, written = [], 0
    cls = images.icon_classes(aa_dir) if p.get("image_swaps") else {}
    src_dir = project_mod.images_dir(ws, p["name"])
    for e in p.get("image_swaps", []):
        data = (src_dir / e["source"]).read_bytes()
        if e["kind"] == "texture":
            where = e.get("where") or default_places(e["name"])
            ext = images.sniff(data)
            fn = "images/%s.%s" % (images._safe(e["name"]), "jpg" if ext == "jpg" else "png")
            if ext in ("jpg", "png"):
                (dest / fn).write_bytes(data)
            else:
                from PIL import Image
                Image.open(io.BytesIO(data)).save(dest / fn)
            written += 1
            for w in where:
                label, sels, extra = PLACES[w]
                img_rules.extend(extra)
                img_rules.append(_rule(", ".join(sels), {"background-image": 'url("%s")' % fn, "-unity-background-scale-mode": "scale-and-crop"}))
            notes.append("wallpaper %s: shown on %s (the game's own picture is hidden or covered there)" % (e["name"], ", ".join(PLACES[w][0] for w in where)))
            continue
        key = ("icon", e["name"]) if e["kind"] == "icon" else ("svg", str(e["path_id"]))
        classes = cls.get(key)
        if not classes:
            skipped.append("%s %s: no USS class draws it (placed in code); install it with Build + Install (bundle)" % (e["kind"], e["name"]))
            continue
        cat = next((r for r in images.catalog(ws, aa_dir) if r["bundle"] == e["bundle"] and r["path_id"] == str(e["path_id"])), None)
        bw, bh = ((cat["w"] / 2, cat["h"] / 2) if e["kind"] == "icon" else (cat["w"], cat["h"])) if cat else (32, 32)
        k = 4 if e["kind"] == "icon" else 8
        img = images.render_icon(data, max(1, round(bw * k)), max(1, round(bh * k)))
        fn = "images/%s.png" % images._safe(e["name"])
        img.save(dest / fn)
        written += 1
        img_rules.append(_rule(", ".join("." + c for c in classes), {"background-image": 'url("%s")' % fn}))
    images_uss = "/* Icon and SVG replacements (FM27 Skin Editor): the classes are the game's own (FMImages stylesheets). */\n" + "".join(img_rules)

    own = {"tokens.uss": (tokens_uss, bool(toks)), "rules.uss": (rules_uss, bool(rules)), "images.uss": (images_uss, bool(img_rules))}
    imported = list(p.get("native_sheets", []))
    imp_tokens = imp_rules = imp_images = imp_fonts = 0
    flat = []                                                # sheet names as written at the skin root
    if imported:                                             # an imported native skin: sheets flat at the root, files under images/ fonts/ assets/
        from . import projfmt
        pd = projfmt.folder(ws, p["name"])
        for rel in p.get("native_support", []):
            out = dest / rel
            if out.exists():
                raise ValueError("%s of the imported skin collides with a file this export writes" % rel)
            out.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(pd / rel, out)
            imp_images += rel.startswith("images/")
            imp_fonts += rel.startswith("fonts/")
        for rel in imported:
            name_ = rel.split("/", 1)[1]
            if name_ in own or (dest / name_).exists():
                raise ValueError("the imported sheet %s has the same name as a file this export writes; rename it before exporting" % name_)
            text = (pd / rel).read_text(encoding="utf-8-sig")
            (dest / name_).write_text(projfmt.URL_RE.sub(lambda m: 'url("%s")' % m.group(2).strip()[3:] if m.group(2).strip().startswith("../") else m.group(0), text), encoding="utf-8", newline="\n")
            flat.append(name_)
            rs, _ = projfmt.parse_uss(text, rel)
            imp_rules += len(rs)
            imp_tokens += sum(1 for r in rs if r["selector"] == ":root" for k, _v, _m, _l in r["decls"] if k.startswith("--"))
    sheets = flat + [n for n, (_, has) in own.items() if has or not imported]
    for n, (txt, has) in own.items():
        if n in sheets:
            (dest / n).write_text(txt, encoding="utf-8")
    name = display or p.get("native_name") or p["name"]
    (dest / "skin.json").write_text(json.dumps({"Name": name, "Sheets": sheets}, indent=2), encoding="utf-8")
    report = {"folder": str(dest), "skin": name, "sheets": list(sheets), "tokens": len(toks) + imp_tokens, "rules": len(rules) + imp_rules, "images": written + imp_images, "fonts": imp_fonts + fonts_written,
              "own": {"tokens": len(toks), "rules": len(rules), "images": written},
              "skipped": skipped, "notes": notes, "exported_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "project": p["name"]}
    report["problems"] = validate(dest) + font_problems
    tok_text = (dest / "tokens.uss").read_text(encoding="utf-8") if (dest / "tokens.uss").is_file() else ""
    for fs in p.get("font_swaps", []):                         # the font gate: file copied, token rule written, url() resolves inside the skin folder
        if (dest / "fonts" / fs["source"]).is_file() and ('%s: url("fonts/%s")' % (fs["token"], fs["source"])) not in tok_text:
            report["problems"].append("font %s: the url() rule for %s was not written" % (fs["source"], fs["token"]))
    marker.write_text(json.dumps(report, indent=1), encoding="utf-8")
    (dest / "README.txt").write_text(
        "%s - exported by FM27 Skin Editor from project %s.\n\nFM27: cog > Preferences > pick \"%s\" in the drop-down next to "
        "\"Reload Skin\".\nTo remove: delete this folder.\n" % (name, p["name"], name), encoding="utf-8")
    return report


def validate(folder):
    """Static check of an exported (or any) skin folder: every sheet listed exists and parses, and every url() points to a file
    inside the folder. The game's own load report is the final word."""
    from . import skins
    folder = Path(folder)
    probs = []
    man = json.loads((folder / "skin.json").read_text(encoding="utf-8"))
    for s in man.get("Sheets", []):
        f = folder / s
        if not f.is_file():
            probs.append("sheet missing: " + s)
            continue
        text = f.read_text(encoding="utf-8")
        if text.count("{") != text.count("}"):
            probs.append("unbalanced braces in " + s)
        for sel, decls in skins.parse_uss(text):
            for k, v in decls:
                for u in skins.URL.findall(v):
                    t = (folder / u).resolve()
                    if folder.resolve() not in t.parents or not t.is_file():
                        probs.append("%s: url(%s) is missing or outside the skin folder" % (s, u))
    return probs
