"""The engine: every operation of the editor as a method of one object, with no transport code. The HTTP server (server.py),
the JSON-RPC API (api/) and the CLI are clients of it. Methods keep the (q, b) signature of the original routes: q = string
parameters, b = a JSON object or raw bytes; api/methods.py gives each one a name and a parameter schema."""
import io
import copy
import json
import os
import re
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path

from . import bundles, colour, config, detect, images, native, preview, skins, index_styles, install, launcher, layout, layout_dump, layout_join, layout_view, patcher, placement, verify
from .presets import PRESETS
from . import project as project_mod
from . import changes
from .api.jobs import EventBus, JobQueue

DEFAULT_NODE_CAP = 1000          # M8: the render tree of one layout is cut to about this many nodes (render/cap.py); the rest opens branch by branch

LAYOUT_INDEX_ENV = "FM27_LAYOUT_INDEX"
LAYOUT_AREAS_ENV = "FM27_LAYOUT_AREAS"
LAYOUT_INDEX_HELP = (
    "No layout index is configured. Set %s (or \"layout_index\" in the workspace config.json) to "
    "FM27_LayoutMCP's index/layout-vanilla.sqlite. FM27_LayoutMCP is a developer-only tool and does not ship "
    "with FM27 Skin Studio, so an ordinary installation has no layout index until one is built there." % LAYOUT_INDEX_ENV)


def resolve_layout_index(cfg, override=None):
    """The FM27_LayoutMCP sqlite index: the call's override, else the environment, else config.json. Refuses in plain
    words when none is configured or the path is missing - the tool that builds it is not shipped."""
    path = override or os.environ.get(LAYOUT_INDEX_ENV) or (cfg or {}).get("layout_index")
    if not path:
        raise RuntimeError("The layout index is not configured. " + LAYOUT_INDEX_HELP)
    if not Path(path).is_file():
        raise RuntimeError("The layout index %s does not exist. %s" % (path, LAYOUT_INDEX_HELP))
    return str(path)


def resolve_layout_areas(cfg, override=None):
    """FM27_LayoutMCP's areas.json: optional (build_dump falls back to no areas), same three sources."""
    return override or os.environ.get(LAYOUT_AREAS_ENV) or (cfg or {}).get("layout_areas")


def layout_index_state(cfg):
    """Whether a layout index is configured AND present, for the UI to hide what needs it. The tool that builds
    the index is developer-only, so an ordinary installation reports configured=False."""
    env = os.environ.get(LAYOUT_INDEX_ENV)
    path = env or (cfg or {}).get("layout_index")
    if not path:
        return {"configured": False, "source": None, "path": None, "help": LAYOUT_INDEX_HELP}
    present = Path(path).is_file()
    return {"configured": present, "source": "environment" if env else "config", "path": str(path),
            "help": None if present else LAYOUT_INDEX_HELP}


class PlacementRefused(Exception):
    """Carries the validation result of a refused placement edit to the HTTP layer."""
    def __init__(self, message, err):
        super().__init__(message)
        self.err = err


class Engine:
    def __init__(self):
        self.cfg = config.load()
        self.ws = config.workspace(self.cfg)
        config.setup_logging(self.ws)
        from . import projfmt
        projfmt.migrate_modes(self.ws)                 # "expert" is "advanced" now (docs/SIMPLE-MODE-PLAN.md S1)
        self.index = index_styles.load(self.ws)
        self.info = None
        self._ld = (None, None)           # (current.json mtime, LayoutData)
        self._view = (None, None)         # (LayoutData it was built from, View)
        self.events = EventBus()
        changes.set_sink(self._project_changed)
        self.jobs = JobQueue(self.events)
        self.lock = threading.Lock()
        if self.cfg.get("game_dir"):
            self.info = detect.describe(self.cfg["game_dir"])

    # ---- helpers
    def need_info(self):
        if not self.info:
            raise RuntimeError("no game install selected")
        return self.info

    def layout_data(self):
        """The imported layout dump as a LayoutData (cached by file mtime), or None."""
        f = self.ws.layout / "current.json"
        if not f.is_file():
            self._ld = (None, None)
            return None
        m = f.stat().st_mtime_ns
        if self._ld[0] != m:
            self._ld = (m, layout_join.LayoutData(layout_dump.load(self.ws)))
        return self._ld[1]

    def _view_of(self):
        ld = self.layout_data()
        if ld is None:
            return None
        if self._view[0] is not ld:
            self._view = (ld, layout_view.View(ld))
        return self._view[1]

    def _read(self, fn):
        """Read-only layout views (GET only). Without a dump: a hint, never an error."""
        v = self._view_of()
        if v is None:
            return {"layout_present": False, "message": "No layout dump imported. Import one on the Setup tab."}
        out = fn(v)
        out["layout_present"] = True
        out["dump"] = layout_dump.state(self.ws)      # not "layout": view results use that key for a layout name
        return out

    def view_screens(self, q, b):
        return self._read(lambda v: v.screens(q.get("area") or None, q.get("q", "")))

    def view_screen(self, q, b):
        return self._read(lambda v: v.screen(q["panel"]))

    def view_outline(self, q, b):
        anc = [int(x) for x in q.get("anc", "").split(",") if x]
        return self._read(lambda v: v.outline(int(q["layout"]), anc, q.get("q", "")))

    def _where(self, fn, *args):
        ld = self.layout_data()
        if ld is None:
            return {"layout_present": False, "message": "No layout dump imported. Import one on the Setup tab (or: python -m skin_editor import-layout DUMP.json)."}
        out = fn(ld, self.need_index(), *args)
        out["layout_present"] = True
        out["layout"] = layout_dump.state(self.ws)
        return out

    def need_index(self):
        if not self.index:
            raise RuntimeError("no style index; take a vanilla snapshot and index first")
        return self.index

    def running(self):
        """True when the game (or a Steam update) is detected. `_running_override` makes the check INJECTABLE for
        tests: they set it to True/False explicitly instead of reading the real process table, so a suite never
        depends on whether Football Manager happens to be open on the machine."""
        override = getattr(self, "_running_override", None)
        if override is not None:
            return bool(override)
        info = self.need_info()
        return detect.game_running(info, self.cfg["process_names"]) or detect.steam_updating(info)

    def start_job(self, label, fn, cancellable=False):
        """Queue fn(progress) as a job; returns its legacy view ({running, label, progress, error, result, id}). Jobs run one at
        a time in submission order (they share the workspace and UnityPy is not re-entrant). A cancellable job can be stopped while running (`progress.cancelled()`)."""
        return self.jobs.submit(label, fn, cancellable).legacy()

    @property
    def job(self):
        """The most recently submitted job in the shape the first frontend polls."""
        return self.jobs.latest_legacy()

    # ---- routes
    def state(self, q, b):
        from . import __version__
        info = self.info
        return {"install": info, "candidates": getattr(self, "candidates", None),
                "app_version": __version__,
                "running": self.running() if info else None,
                "live": install.live_status(self.ws, info["aa_dir"]) if info else None,
                "tamper": install.tamper_status(self.ws, info["aa_dir"]) if info else None,
                "snapshot_mismatch": install.snapshot_mismatch(self.ws, info["aa_dir"]) if info else None,
                "vanilla": self.ws.vanilla_manifest(), "indexed": bool(self.index),
                "index_stats": {"sheets": len(self.index.sheets), "tokens": len(self.index.defs),
                                "literals": len(self.index.literals)} if self.index else None,
                "unitypy": bundles.unitypy_version(), "workspace": str(self.ws.root),
                "projects": project_mod.names(self.ws), "presets": sorted(PRESETS), "job": self.job,
                "platform": sys.platform, "legacy_alpha": colour.LEGACY[-50:],
                "decode_failures": self.index.quarantine() if self.index else None,
                "layout": layout_dump.state(self.ws)}

    def do_detect(self, q, b):
        self.candidates = detect.find_installs()
        if len(self.candidates) == 1 and not self.info:
            self.set_game({}, {"game_dir": self.candidates[0]["game_dir"]})
        return self.state(q, b)

    def set_game(self, q, b):
        info = detect.describe(b["game_dir"])
        if not info:
            raise RuntimeError("no StreamingAssets/aa/Standalone* folder with the style bundles under that path")
        self.info = info
        self.cfg.update(game_dir=info["game_dir"], aa_dir=info["aa_dir"])
        config.save(self.cfg)
        return self.state(q, b)

    def snapshot(self, q, b):
        info = self.need_info()
        if self.running():
            raise RuntimeError("close the game before taking the vanilla snapshot")
        install.snapshot_vanilla(self.ws, info["aa_dir"], info.get("version"), force=bool(b.get("force")))
        self.index = index_styles.load(self.ws)
        return self.state(q, b)

    def snapshot_reread(self, q, b):
        """Job: the guided 'the game was updated' recovery, one button inside the app (game closed, stock files):
        a fresh vanilla snapshot (force) and a rebuilt style index. Refuses while a file this app installed is still
        in the game folder: verify in Steam first, then use this."""
        info = self.need_info()

        def fn(prog):
            out = install.reread_after_update(self.ws, info["aa_dir"], info.get("version"), prog)
            self.index = index_styles.load(self.ws)
            return out
        return self.start_job("re-reading the game", fn)

    def reference_hashes(self, q, b):
        info = self.need_info()
        if self.running():
            raise RuntimeError("close the game before recording reference hashes")
        install.record_reference_hashes(self.ws, info["aa_dir"], force=bool(b.get("force")))
        return self.state(q, b)

    def do_index(self, q, b):
        def fn(prog):
            self.index = index_styles.build(self.ws, prog)
            return {"sheets": len(self.index.sheets), "tokens": len(self.index.defs), "decode_failures": len(self.index.failures)}
        return self.start_job("indexing", fn)

    def tokens(self, q, b):
        return self.need_index().tokens(q.get("q", ""), q.get("colours") == "1")

    def token(self, q, b):
        return self.need_index().token(q["name"])

    # ---- S4: a theme from three colours (skin_editor/theme.py, data/simple/roles.json and gallery.json)
    def _game_colour(self, token):
        ix = self.need_index()
        if token not in ix.defs:
            return None
        r = ix.token_row(token)["resolved"]
        return colour.from_obj(r) if r else None

    def _theme_missing(self, gen):
        """The role map's tokens the style index of THIS build does not define (a game update can drop one): a theme is not written while any is missing."""
        ix = self.need_index()
        return sorted(o["token"] for o in gen["overrides"] if o["token"] not in ix.defs)

    def theme_generate(self, q, b):
        """Make a theme from three colours WITHOUT writing it: how many tokens it writes, how many it keeps at the game's colour, and the contrast check (failures block create)."""
        from . import theme
        gen = theme.generate(b["background"], b["accent"], b["text"], b.get("mode", "dark"))
        c = theme.contrast(gen, self._game_colour)
        missing = self._theme_missing(gen)
        return {"inputs": gen["inputs"], "writes": len(gen["overrides"]), "keeps": gen["kept"], "status": "not yet checked in the game", "missing": missing,
                "contrast": {k: c[k] for k in ("minimum", "pairs", "checked", "failures", "game_failures", "game_low", "unchecked")}, "ok": not c["failures"] and not missing,
                "preview": {o["token"]: o["value"] for o in gen["overrides"] if o["token"] in ("--global-background", "--colours-ui-soft", "--colours-ui-strong", "--brand-theme-primary", "--brand-theme-accent", "--global-text-primary", "--global-text-secondary")}}

    def theme_create(self, q, b):
        """Write a generated theme as a native folder project, ONLY when it passes the contrast check: a failing pair is refused, never adjusted."""
        from . import projfmt, theme
        name = b["name"]
        if name in project_mod.names(self.ws):
            raise RuntimeError("a project with that name exists")
        gen = theme.generate(b["background"], b["accent"], b["text"], b.get("mode", "dark"))
        missing = self._theme_missing(gen)
        if missing:
            raise ValueError("the role map names %d token(s) this game build does not have (%s); nothing was written" % (len(missing), ", ".join(missing[:5])))
        c = theme.contrast(gen, self._game_colour)
        if c["failures"]:
            raise ValueError("the theme fails the contrast check on %d pair(s), the lowest %.2f (minimum %.1f); nothing was written" % (len(c["failures"]), min(f["ratio"] for f in c["failures"]), c["minimum"]))
        p = theme.project_for(name, gen, b.get("keep_club_colours", True), (self.ws.vanilla_manifest() or {}).get("game_build"))
        projfmt.write(self.ws, p)
        changes.record(name, "options", ["project created from a theme"])
        return {"project": project_mod.load(self.ws, name), "writes": len(gen["overrides"]), "contrast": {k: c[k] for k in ("checked", "failures", "game_failures", "game_low")}, "status": "not yet checked in the game"}

    def theme_gallery(self, q, b):
        """The gallery: each theme's inputs, made by the same generator, with its contrast result computed now."""
        from . import theme
        out = []
        for t in theme.gallery():
            gen = theme.generate(t["background"], t["accent"], t["text"], t["mode"])
            c = theme.contrast(gen, self._game_colour)
            out.append({**t, "ok": not c["failures"], "failures": len(c["failures"]), "checked": c["checked"]})
        rm = theme.roles()
        ref = {k: rm["ramps"][r][rm["references"][r]] for k, r in (("background", "neutral"), ("accent", "accent"), ("text", "text"))}
        return {"themes": out, "crimson": {**ref, "mode": "dark", "source": "the Crimson preset's own page background, accent and text (data/simple/roles.json)"}}

    def simple_token_screens(self, q, b):
        """On how many of the measured screens the shipped models hold an area this token paints (Simple mode's 'used on N of the 8 measured screens'). Counts only, no picture."""
        from . import simple
        ix = self.need_index()
        if b["token"] not in ix.defs:
            raise KeyError("no such token: %s" % b["token"])
        return simple.token_screens(ix, b["token"])

    def simple_pictures(self, q, b):
        """S6: the pictures Simple mode offers (what a native skin can replace), the wallpaper places, and where Look at it can show them."""
        from . import simple
        return simple.picture_catalog(images.catalog(self.ws, self.need_info()["aa_dir"]), self._icon_classes())

    def simple_literal_info(self, q, b):
        """What a literal colour swap would copy into a native skin, and whether Simple mode offers it (at most simple.LITERAL_LIMIT copied rules)."""
        from . import simple
        return simple.literal_info(self.need_index(), b["rgb"], b.get("a", 1.0))

    def browse_colours(self, q, b):
        """Every colour token the game's rules use (or, with used_only false, every colour token), compact: name, resolved colour, and the number of rule paths it paints.
        The Simple palette shows these so a person can see everything and click what to change (docs/SIMPLE-MODE-PLAN.md S1)."""
        ix = self.need_index()
        used_only = b.get("used_only", True) is not False
        rows = []
        for name in sorted(ix.defs):
            r = ix.token_row(name)
            c = r["resolved"]
            if not c or (used_only and r["reach"] == 0):
                continue
            rows.append({"name": name, "rgb": c["rgb"], "a": c["a"], "reach": r["reach"]})
        return {"total": len(rows), "rows": rows}

    def literals(self, q, b):
        return self.need_index().literal_list()

    def literal(self, q, b):
        return self.need_index().literal(q["rgb"], q["a"])

    def layout_state(self, q, b):
        return dict(layout_dump.state(self.ws), index=layout_index_state(self.cfg))

    def layout_import(self, q, b):
        r = layout_dump.import_bytes(self.ws, b, q.get("name", "upload"))
        self._ld = (None, None)
        return r

    def where_token(self, q, b):
        return self._where(layout_join.where_token, q["name"])

    def where_literal(self, q, b):
        return self._where(layout_join.where_literal, q["rgb"], float(q["a"]))

    def where_search(self, q, b):
        return self._where(layout_join.where_search, q.get("q", ""))

    # ---- placement edits (stored only; see placement.py). Add and remove refuse unless the dump is fresh / the project exists.
    def placement_list(self, q, b):
        return placement.summary(self.ws, q["project"])

    def placement_check(self, q, b):
        ce = placement.can_edit(self.ws)
        g = placement._grid(self.ws)
        if g is None:
            return {"blocks": [ce["why"]], "warnings": [], "collisions": [], "can_edit": False}
        doc = placement.load(self.ws, b["project"])
        key = (b["edit"].get("composition"), b["edit"].get("cell_index"))
        r = placement.check(g, b["edit"], [o for o in doc["edits"] if (o["composition"], o["cell_index"]) != key])
        if not ce["ok"]:
            r["blocks"] = [ce["why"]] + r["blocks"]
        r["can_edit"] = ce["ok"]
        return r

    def placement_add(self, q, b):
        project_mod.load(self.ws, b["project"])       # the project must exist
        try:
            return {"edit": placement.add(self.ws, b["project"], b["edit"], bool(b.get("confirm")))}
        except placement.PlacementError as e:
            raise PlacementRefused(str(e), e)

    def placement_remove(self, q, b):
        placement.remove(self.ws, b["project"], b["id"])
        return placement.summary(self.ws, b["project"])

    def projects(self, q, b):
        return project_mod.names(self.ws)

    def get_project(self, q, b):
        try:
            return project_mod.load(self.ws, q["name"])
        except FileNotFoundError:
            return project_mod.new(q["name"], (self.ws.vanilla_manifest() or {}).get("game_build"))

    def save_project(self, q, b):
        p = project_mod.save(self.ws, b)      # migrates schema 1 input, validates, writes schema 2
        return {"project": p, "warnings": project_mod.warnings(p)}

    def project_routing(self, q, b):
        """The Playground build routing of one project, with the trade-off in plain words. A setting counts
        only when the user chose it explicitly; otherwise the default is bundle. Read only."""
        name = q.get("project") or b.get("project")
        p = project_mod.load(self.ws, name)
        return {"project": name,
                "route_preference": project_mod.route_preference(p),
                "route_preference_explicit": bool((p.get("options") or {}).get("route_preference_explicit")),
                "edit_competition_sheets": project_mod.edit_competition_sheets(p),
                "edit_competition_sheets_explicit": bool((p.get("options") or {}).get(
                    "edit_competition_sheets_explicit")),
                "layout_route": project_mod.layout_route(p),
                "layout_route_explicit": bool((p.get("options") or {}).get("layout_route_explicit")),
                "layout_route_default": project_mod.DEFAULT_LAYOUT_ROUTE,
                "layout_engine": project_mod.layout_engine(p),
                "layout_engine_explicit": bool((p.get("options") or {}).get("layout_engine_explicit")),
                "layout_engine_default": project_mod.DEFAULT_LAYOUT_ENGINE,
                "layout_engines": list(project_mod.LAYOUT_ENGINES),     # UI1: both remain selectable in the Playground
                "layout_engine_note": "rea is the default layout engine; one_rule stays selectable",
                "experimental_bundle_layout_edits": project_mod.experimental_bundle_layout_edits(p),
                "experimental_bundle_layout_edits_explicit": bool((p.get("options") or {}).get("experimental_bundle_layout_edits_explicit")),
                "experimental_bundle_layout_warning": project_mod.EXPERIMENTAL_BUNDLE_LAYOUT_WARNING,
                "layout_route_note": "layout operations (move, resize, max size, add tile, slots, swap tile) go to the game's custom-layout files by default: no bundle rebuild, no "
                                     "checksum mismatch, undo is restoring the file; styles and pictures keep their own route",
                "default": project_mod.DEFAULT_ROUTE_PREFERENCE,
                "tradeoffs": {
                    "bundle": "changes the game files when installed, and is the only route that can move, "
                              "resize or add tiles and edit the winning declaration",
                    "skin_folder": "writes only the skin folder and changes no game file, but cannot express "
                                   "tile moves or per-declaration edits",
                    "edit_competition_sheets": "off by default; changing a competition sheet's own definitions "
                                               "is a separate, explicit choice"},
                "note": "the skin-folder route is chosen explicitly; a project without a choice uses bundle"}

    def project_set_routing(self, q, b):
        """Record an EXPLICIT routing choice (or competition-sheet choice) through the normal project save path:
        the setting is stored only when chosen, with its explicit marker."""
        p = project_mod.load(self.ws, b["project"])
        if "route_preference" in b:
            project_mod.set_route_preference(p, b["route_preference"])
        if "edit_competition_sheets" in b:
            project_mod.set_edit_competition_sheets(p, b["edit_competition_sheets"])
        if "layout_route" in b:
            project_mod.set_layout_route(p, b["layout_route"])
        if "layout_engine" in b:
            project_mod.set_layout_engine(p, b["layout_engine"])
        if "experimental_bundle_layout_edits" in b:
            project_mod.set_experimental_bundle_layout_edits(p, b["experimental_bundle_layout_edits"])
        p = project_mod.save(self.ws, p)
        return self.project_routing({}, {"project": p["name"]})

    # ---- folder projects (projfmt): files as the source of truth
    def pf_tree(self, q, b):
        from . import projfmt
        return {"project": q["project"], "folder": projfmt.is_folder(self.ws, q["project"]), "files": projfmt.tree(self.ws, q["project"]) if projfmt.is_folder(self.ws, q["project"]) else []}

    def pf_read(self, q, b):
        from . import projfmt
        return {"path": q["path"], "text": projfmt.read_file(self.ws, q["project"], q["path"])}

    def pf_write(self, q, b):
        from . import projfmt
        return {"problems": projfmt.write_file(self.ws, b["project"], b["path"], b["text"])}

    def pf_delete(self, q, b):
        from . import projfmt
        return {"problems": projfmt.delete_file(self.ws, b["project"], b["path"])}

    def pf_problems(self, q, b):
        from . import projfmt
        return {"problems": projfmt.read(self.ws, q["project"], strict=False)[1]}

    # ---- USS tooling (phase 2)
    def uss_diagnostics(self, q, b):
        from . import ussdiag
        return {"diagnostics": ussdiag.check(b["text"], self.index, b.get("sheet"))}

    def game_sheets(self, q, b):
        ix = self.need_index()
        return [{"name": s["name"], "bundle": s["bundle"], "rules": len(s["rules"])} for s in ix.sheets]

    def game_sheet(self, q, b):
        """A vanilla sheet printed as USS (read-only view for go-to-definition)."""
        from . import ussprint
        s = next((x for x in self.need_index().sheets if x["name"] == q["name"] and (not q.get("bundle") or x["bundle"] == q["bundle"])), None)
        if not s:
            raise KeyError("no such sheet: " + q["name"])
        return {"name": s["name"], "text": ussprint.print_sheet(s), "rules": len(s["rules"])}

    def build_plan(self, q, b):
        from . import plan
        p = project_mod.load(self.ws, b["project"])
        return plan.plan(self.ws, p, self.index, (self.info or {}).get("aa_dir"), b.get("target"))

    def pf_import_native(self, q, b):
        from . import projfmt
        return projfmt.import_native_skin(self.ws, b["path"], b["name"])

    # ---- in-game checklist and the prepared packages
    def docs_checklist(self, q, b):
        """docs/INGAME-CHECKLIST.md (the one document this method serves) and its results block, for the Studio's help view."""
        f = config.resource_root() / "docs" / "INGAME-CHECKLIST.md"           # sys._MEIPASS when frozen, the repo root otherwise
        if not f.is_file():
            raise FileNotFoundError("docs/INGAME-CHECKLIST.md is missing")
        text = f.read_text(encoding="utf-8")
        m = re.search(r"<!-- RESULTS-START -->(.*?)<!-- RESULTS-END -->", text, re.S)
        return {"path": str(f), "text": text, "results": m.group(1).strip() if m else ""}

    def builds_list(self, q, b):
        """The packages: every build that has a package.json (project, id, gate result, files with hashes, plan digest). `latest` marks the
        build install.bundles would install for its project."""
        out = []
        for pd in sorted(p for p in self.ws.build.iterdir() if p.is_dir()):
            if b.get("project") and pd.name != b["project"]:
                continue
            latest = patcher.latest_build(self.ws, pd.name)
            for bd in sorted((p for p in pd.iterdir() if (p / "package.json").is_file()), reverse=True):
                try:
                    pk = json.loads((bd / "package.json").read_text(encoding="utf-8"))
                except ValueError:
                    continue
                out.append(dict(pk, dir=str(bd), latest=bool(latest and bd.name == latest.name)))
        out.sort(key=lambda r: r["built_utc"], reverse=True)
        return {"packages": out[: int(b.get("limit") or 40)]}

    # ---- the real layout index -> the editor's layout dump
    # The index is built by FM27_LayoutMCP, a developer-only tool that is not shipped: the path comes from the
    # call, FM27_LAYOUT_INDEX, or config.json's "layout_index", and a missing one is refused in plain words.
    def layout_export(self, q, b):
        """Build the fmlayout-index/2 dump from the FM27_LayoutMCP sqlite index and the game's composition bundles, cross-check every cell against
        its bundle, and import it (the import decides fresh / stale / contaminated from the bundle hashes). Read-only on the index and the game."""
        from . import layout_export
        aa = self.need_info()["aa_dir"]
        path = resolve_layout_index(self.cfg, b.get("index"))
        db = layout_export.connect(path)
        try:
            cc = layout_export.crosscheck(db, aa)
        finally:
            db.close()
        if cc["mismatches"]:
            raise RuntimeError("the index does not match the game's composition bundles (%d mismatch(es), e.g. %s); rebuild the index" % (len(cc["mismatches"]), cc["mismatches"][0]))
        from . import profile
        build = b.get("game_build") or (profile.active_profile(self.ws) or {}).get("game_build") or "unknown"
        d = layout_export.build_dump(path, aa, build, resolve_layout_areas(self.cfg, b.get("areas")))
        r = layout_dump.import_bytes(self.ws, json.dumps(d).encode("utf-8"), "layout index " + time.strftime("%Y-%m-%d"))
        self._ld = (None, None)
        return {"imported": r, "crosscheck": {"compositions": cc["compositions"], "cells": cc["cells"], "mismatches": 0}, "state": layout_dump.state(self.ws)}

    def layout_scan(self, q, b):
        """Read the game's own UI bundles (never FM27_LayoutMCP) and build/refresh the fmlayout-index/2 dump as a
        cancellable job. The reference hashes must be clean and current; the finished dump is validated and only
        then imported, so a cancelled or failed read leaves the stored dump untouched."""
        from . import layout_scan as scan
        from .api import jobs as job_mod
        info = self.need_info()
        aa = info["aa_dir"]
        ws = self.ws

        def fn(prog):
            t = install.tamper_status(ws, aa)
            if t["state"] == "game_updated":
                raise RuntimeError("catalog.hash changed since the snapshot: " + t["message"])
            if t["state"] == "no_reference":
                raise RuntimeError("the game has no reference hashes yet. Take the vanilla snapshot first (Read the game), then it can be read for layouts.")
            if t["state"] == "modified":
                raise RuntimeError("the game's UI bundles are not the stock files (%s). Restore them (Steam: Verify integrity) before reading the layouts."
                                   % ", ".join(t.get("modified") or t.get("new") or []))
            if t.get("new"):
                raise RuntimeError("the game has UI bundles the snapshot has no reference for (%s); take a new snapshot first."
                                   % ", ".join(t["new"][:6]))
            from . import profile
            build = ((ws.vanilla_manifest() or {}).get("game_build") or (profile.active_profile(ws) or {}).get("game_build")
                     or info.get("version") or "unknown")
            try:
                d, r = scan.read_and_import(ws, aa, build, areas_json=resolve_layout_areas(self.cfg), progress=prog)
            except scan.ScanCancelled:
                job_mod.cancel_with()
            self._ld = (None, None)
            return {"imported": r, "counts": layout_dump.summary(d), "game_build": build,
                    "source_bundles": len(d["meta"]["source"]["bundles"]),
                    "fingerprint": layout_dump.short_fingerprint(d["meta"]["index_fingerprint"])}
        return self.start_job("reading the game's layouts", fn, cancellable=True)

    # ---- table views
    def _tables(self):
        from . import tables
        gn = {}
        d = layout_dump.load(self.ws)
        if d:
            gn = {l["guid"]: l["name"] for l in d["layouts"]}
        if (self.ws.vanilla / tables.VIEWS_BUNDLE).is_file() and (self.ws.vanilla / tables.FACTORIES_BUNDLE).is_file():
            return tables.Tables(self.ws.vanilla, gn)
        aa = self.need_info()["aa_dir"]
        install.refuse_if_updated(self.ws, aa, "Reading the tables")
        t = install.tamper_status(self.ws, aa)
        bad = [n for n, s in (t.get("files") or {}).items() if n in (tables.VIEWS_BUNDLE, tables.FACTORIES_BUNDLE) and s != "stock"]
        if bad:
            raise RuntimeError("the game's table bundles are not stock (%s); restore them or take a new snapshot" % (", ".join(bad) or t.get("message", "")))
        return tables.Tables(aa, gn)

    def tables_list(self, q, b):
        rows = self._tables().list(str(b.get("q", "")))
        return {"total": len(rows), "views": rows[: int(b.get("limit") or 300)]}

    def tables_usage(self, q, b):
        """Where table views are used: read the FM27_LayoutMCP index (read-only), decode the view GUIDs out of the layouts' InitFunction arguments,
        and keep the result in the workspace (table-view-usage.json) so `tables.view` can say which layout and tile show a view."""
        from . import table_usage, profile
        db = table_usage.connect(resolve_layout_index(self.cfg, b.get("index")))
        try:
            usage = table_usage.build(db)
        finally:
            db.close()
        table_usage.save(self.ws.root / "table-view-usage.json", usage, (profile.active_profile(self.ws) or {}).get("game_build") or "unknown")
        return {"views_with_layouts": len(usage), "references": sum(len(v) for v in usage.values()), "path": str(self.ws.root / "table-view-usage.json")}

    def tables_view(self, q, b):
        out = self._tables().view(b["path_id"])
        from . import table_usage
        usage = table_usage.load(self.ws.root / "table-view-usage.json")
        if usage is not None:
            out["used_by"] = usage.get(out["name"], [])
            out["used_by_summary"] = table_usage.summary(usage, out["name"])
        if b.get("project"):
            out["patches"] = next((d for d in project_mod.load(self.ws, b["project"]).get("table_patches", []) if d["view"]["name"] == out["name"]), None)
        return out

    def tables_edit(self, q, b):
        """Fold one column op (set-width, hide-column, show-column, move-column) into the project's patch file for a view, after checking it
        against the view as the game has it."""
        from . import tables
        op = dict(b["op"])
        view = {"bundle": tables.VIEWS_BUNDLE, "name": b["name"], "path_id": str(b["path_id"])}
        p = project_mod.load(self.ws, b["project"])
        doc = next((d for d in p.get("table_patches", []) if d["view"]["name"] == view["name"]), None)
        if doc is None:
            doc = {"schema": 1, "view": view, "ops": []}
            p.setdefault("table_patches", []).append(doc)
        tables.merge_op(doc, op)
        if not doc["ops"]:
            p["table_patches"].remove(doc)
        else:
            T = self._tables().load()
            v = T._views[int(view["path_id"])]
            fac, _ = T.factory_for([c["m_columnID"] for c in v["tree"]["m_tableView"]["m_tableConfig"]])
            tables.apply_to_view(copy.deepcopy(v["tree"]), doc["ops"], view["name"] + ":", {r["m_id"] for r in fac["tree"]["m_rowData"]} if fac else None)
            aa = self.need_info()["aa_dir"]
            for bn in (tables.VIEWS_BUNDLE, tables.FACTORIES_BUNDLE):
                install.add_image_bundle(self.ws, aa, bn)
        project_mod.save(self.ws, project_mod.validate(project_mod.migrate(p)))
        return {"project": project_mod.load(self.ws, b["project"])}

    def tables_unedit(self, q, b):
        p = project_mod.load(self.ws, b["project"])
        p["table_patches"] = [d for d in p.get("table_patches", []) if d["view"]["name"] != b["name"]]
        project_mod.save(self.ws, project_mod.validate(project_mod.migrate(p)))
        return {"project": project_mod.load(self.ws, b["project"])}

    # ---- UXML layouts (read, class usage, per-layout patches) and fonts
    def _layouts(self):
        """Layouts are read from the vanilla snapshot when it holds the layout bundles, else from the game folder while those bundles are
        stock (read-only either way)."""
        from . import uxml
        if any(self.ws.vanilla.glob(uxml.VTA_GLOB)):
            return uxml.Layouts(self.ws.vanilla, self.ws.cache)
        aa = self.need_info()["aa_dir"]
        install.refuse_if_updated(self.ws, aa, "Reading the layouts")
        t = install.tamper_status(self.ws, aa)
        bad = [n for n, s in (t.get("files") or {}).items() if n.startswith("ui-visualtreeassets") and s != "stock"]
        if t.get("state") == "modified" and bad:
            raise RuntimeError("the game's layout bundles are not stock (%s); restore them or take a new snapshot" % (", ".join(bad[:3]) or t.get("message", "")))
        return uxml.Layouts(aa, self.ws.cache)

    def _project_changed(self, ev):
        """A project changed (skin_editor/changes.py): the render's cached overlay for it is dropped and `render.invalidate` goes out on the event bus."""
        rd = getattr(self, "_rd", None)
        if rd:
            rd[1].invalidate(ev["project"])
        self.events.publish("render.invalidate", ev)

    # ---- offline render (Phase 9, docs/PHASE9-PLAN.md): an approximation of the game's UI, never the game's renderer
    def _renderer(self):
        """One Renderer per game folder/profile; the layout bundles are read from the snapshot or from the stock game folder, as `_layouts` does."""
        from .render.service import Renderer
        from . import uxml
        folder = self._render_folder(uxml)
        key = (str(folder), id(self.index))
        if getattr(self, "_rd", (None, None))[0] != key:
            rd = Renderer(folder, self.ws.cache, self.index)
            rd.project_images = lambda p: {"classes": self._icon_classes(), "dir": project_mod.images_dir(self.ws, p["name"])}     # S6: a native project's pictures are drawn
            self._rd = (key, rd)
        return self._rd[1]

    def _icon_classes(self):
        """images.icon_classes of the game, once per game folder (it reads two style bundles)."""
        aa = self.need_info()["aa_dir"]
        if getattr(self, "_ic", (None, None))[0] != aa:
            self._ic = (aa, images.icon_classes(aa))
        return self._ic[1]

    def _render_folder(self, uxml):
        """The folder the render reads every layout bundle from. The snapshot is used only when it holds the COMPLETE set of the game's layout bundles (it often holds just
        the few the build touches, and the L view's loader reads the snapshot as soon as it holds any one); otherwise the game folder, and only while its layout bundles
        are stock (the same tamper rule as `_layouts`), so a test bundle left installed can never change a render."""
        aa = Path(self.need_info()["aa_dir"])
        live = {p.name for p in aa.glob(uxml.VTA_GLOB)}
        if live and live <= {p.name for p in Path(self.ws.vanilla).glob(uxml.VTA_GLOB)}:
            return Path(self.ws.vanilla)
        install.refuse_if_updated(self.ws, str(aa), "The render")
        t = install.tamper_status(self.ws, str(aa))
        bad = [n for n, s in (t.get("files") or {}).items() if n.startswith("ui-visualtreeassets") and s != "stock"]
        if t.get("state") == "modified" and bad:
            raise RuntimeError("the game's layout bundles are not stock (%s); restore them or take a new snapshot" % (", ".join(bad[:3]) or t.get("message", "")))
        return aa

    def render_layouts(self, q, b):
        """The layouts the render browser lists (the VisualTreeAssets of the game), filtered by name."""
        return self._renderer().layout_list(b.get("q", ""), b.get("limit") or 200)

    def render_layout(self, q, b):
        """The render tree of one layout with computed styles. `bundle` + `path_id`, or `name` (the first layout of that name)."""
        bundle, pid = b.get("bundle"), b.get("path_id")
        if not (bundle and pid):
            rows = [r for r in self._layouts().list() if r["name"] == b.get("name")]
            if not rows:
                raise KeyError("no layout named %r" % b.get("name"))
            bundle, pid = rows[0]["bundle"], rows[0]["path_id"]
        project = None
        if b.get("project") and b.get("skin", True):                      # the skin toggle: skin=false renders the vanilla game whatever the project holds
            project = project_mod.load(self.ws, b["project"])
        cap = DEFAULT_NODE_CAP if b.get("max_nodes") is None else int(b["max_nodes"])        # 0 = every node (the caller asked for it)
        res = self._renderer().layout(bundle, pid, int(b.get("depth") or 3), project=project, max_nodes=cap, open=[str(x) for x in (b.get("open") or [])])
        if project is not None:
            from .render import origins
            res["origins"] = origins.resolve(self.ws, project, res["tree"])          # where the project's own rules and token overrides are, for the side panel
        return res

    def render_rule(self, q, b):
        """One rule of the render's cascade as USS text, with where it lives: a rule of the game's sheets is read-only (`origin` null, `vanilla` true); a rule the project appended
        gives its file and line. `sheet` is the name the render showed (a project's native author sheet included)."""
        from .render import origins
        project = project_mod.load(self.ws, b["project"]) if b.get("project") and b.get("skin", True) else None
        rd = self._renderer()
        casc = rd.skin_cascade(project)[0] if project is not None else rd.cascade()
        sheet = next((s for s in casc.sheets if s.name == b["sheet"]), None)
        rule = next((r for r in sheet.rules if r["i"] == int(b["rule"])), None) if sheet else None
        if rule is None:
            raise KeyError("no rule %s in sheet %r" % (b["rule"], b["sheet"]))
        o = rule.get("origin")
        loc = None
        if o and project is not None:
            rel = origins.file_of(o)
            hit = next((x for x in origins._lines(self.ws, project["name"], rel) if x[0] == origins._norm(o["selector"])), None)
            loc = {"file": rel, "line": hit[1] if hit else None, "end": hit[2] if hit else None}
        return {"sheet": sheet.name, "rule": rule["i"], "text": origins.rule_text(rule), "vanilla": not o, "origin": loc,
                "properties": [{"name": n, "value": v} for n, v, _c in rule["props"]], "token_rule": bool(rule["token"])}

    def render_table(self, q, b):
        """A table view as a labelled placeholder table (its header row is the column order); with `project` (and skin not false) the project's column edits are applied."""
        project = project_mod.load(self.ws, b["project"]) if b.get("project") and b.get("skin", True) else None
        from .render import overlay
        return overlay.table_placeholder(self._tables(), b["path_id"], project, b.get("breakpoint"))

    def render_screen(self, q, b):
        """A composition's cells placed on a grid container of `width` x `height` px (see render/screen.py). With `project` (and skin not false) the project's tile moves apply."""
        from .render import screen
        moves, adds = [], []
        if b.get("project") and b.get("skin", True):
            from . import tiles
            moves = tiles.ops_for(self.ws, b["project"])
            try:
                s, _folder = self._playground_session(b["project"])
                proj = self._playground_projection(b["project"], s)
                adds = [{"element_id": p.get("cell_element_id"), "cell_index": p.get("cell_index"),
                         "geometry": dict(p.get("geometry") or {})}
                        for p in proj.get("placements") or []
                        if p.get("candidate") == "add-cell" and p.get("composition") == b["composition"]]
                moves += [{"composition": p.get("composition"), "cell_id": p.get("cell_element_id"),
                           "to": dict(p.get("geometry") or {})}
                          for p in proj.get("placements") or []
                          if p.get("candidate") != "add-cell" and p.get("composition") == b["composition"]]
            except Exception:
                adds = []
        d = layout_dump.load(self.ws)
        if d is None:
            raise RuntimeError("no layout dump is imported")
        return screen.Assembler(d).assemble(b["composition"], (float(b["width"]), float(b["height"])), reserved_right=int(b.get("reserved_right") or 0),
                                            padding=int(b.get("padding") if b.get("padding") is not None else 12), moves=moves, adds=adds)

    # ---- Stage 5, the finding-5 join: render nodes <-> UiDocument nodes by (bundle, path_id, m_Id)
    def _uidoc_document(self, d, composition):
        """The UiDocument of one composition, built from the imported dump and the stock game's layout bundles
        (read only) and cached per composition and dump fingerprint. The renderer depth default is untouched."""
        fp = d["meta"]["index_fingerprint"]
        cache = getattr(self, "_uidoc_docs", None)
        if cache is None:
            cache = self._uidoc_docs = {}
        hit = cache.get((composition, fp))
        if hit is not None:
            return hit
        from .uidoc import Source, build_document
        from .render.service import Renderer
        rd = self._renderer()
        label = {"game_build": d["meta"].get("game_build") or (self._game_build() or "unknown"),
                 "status": "read-only reconstruction from the imported layout dump and the stock game files",
                 "dump_catalog_hash": d["meta"]["source"]["catalog_hash"]}
        doc = build_document(Source(rd.layouts), d, composition, (1600, 900), renderer=rd, label=label)
        cache[(composition, fp)] = doc
        return doc

    def _uidoc_composition(self, d, b):
        """The composition the join is asked for: named, or the one whose tile closure reaches the named layout.
        (None, []) when a layout was asked for and no composition reaches it - the caller answers joinable:false."""
        if b.get("composition"):
            if not any(c["name"] == b["composition"] for c in d["compositions"]):
                raise KeyError("no such composition %r in the imported layout dump" % b["composition"])
            return b["composition"], []
        if not (b.get("bundle") and b.get("path_id")):
            raise KeyError("no such composition: name the composition, or give the layout's bundle and path id")
        try:
            guid = self._layout_guid(b.get("bundle"), b.get("path_id"))
            lay_id = {l["guid"]: l["id"] for l in d["layouts"]}.get(guid)
        except KeyError:
            return None, []
        if lay_id is None:
            return None, []
        owners_direct, owners_closure = [], []
        for row in sorted(d["tiles"], key=lambda t: (t["composition"], t["cell_index"])):
            comp = row["composition"]
            if comp in owners_direct or comp in owners_closure:
                continue
            starts = {t["panel_layout_id"] for t in d["tiles"] if t["composition"] == comp} | {t["tile_layout_id"] for t in d["tiles"] if t["composition"] == comp}
            if lay_id in starts:
                owners_direct.append(comp)          # a TOP layout of the composition: its instances' rows address it directly
            elif lay_id in self._uidoc_closure(d, comp):
                owners_closure.append(comp)         # reached only through includes: no direct instance rows
        if owners_direct:
            return owners_direct[0], owners_direct[1:] + owners_closure
        return None, owners_closure

    def _uidoc_closure(self, d, composition):
        """The dump layout ids one composition's panel and tile layouts reach through includes (cached per fingerprint)."""
        cache = getattr(self, "_uidoc_closures", None)
        fp = d["meta"]["index_fingerprint"]
        if cache is None or cache[0] != fp:
            cache = self._uidoc_closures = (fp, {})
        hits = cache[1]
        if composition in hits:
            return hits[composition]
        rows = [t for t in d["tiles"] if t["composition"] == composition]
        lay_ids = {l["id"]: l for l in d["layouts"]}
        includes = {}
        for r in d["includes"]:
            includes.setdefault(r["from_layout_id"], []).append(r["to_layout_id"])
        closure, todo = set(), list({t["panel_layout_id"] for t in rows} | {t["tile_layout_id"] for t in rows})
        while todo:
            x = todo.pop()
            if x in closure or x not in lay_ids:
                continue
            closure.add(x)
            todo.extend(includes.get(x, []))
        hits[composition] = closure
        return closure

    def _layout_guid(self, bundle, path_id):
        """The container GUID of one (bundle, path_id), from the render's GUID index (read only)."""
        from .render.service import Renderer
        gi = self._renderer().layouts.guids
        for g, ents in gi.load().items():
            for eb, ep in ents:
                if eb == bundle and str(ep) == str(path_id):
                    return g
        raise KeyError("no layout named by %s/%s in the layout bundles" % (bundle, path_id))

    def uidoc_join(self, q, b):
        """The (bundle, path_id, m_Id) join between the render nodes and the UiDocument nodes of one composition:
        per layout instance, every node's state (joined / not drawn with the reason / unmatched) and, for joined
        ones, the render position it was joined with. `composition` names one; otherwise the composition whose
        tile closure reaches the layout at `bundle` + `path_id` is used (candidates listed when several). With a
        layout that is a TOP layout of the composition (a panel or tile layout), the canvas can address its nodes
        by UiDocument identity; an INCLUDED layout's own render numbers positions from its own root, so it stays
        on render-path addressing and the response says so."""
        d = layout_dump.load(self.ws)
        if d is None:
            raise RuntimeError("no layout dump is imported")
        st = layout_dump.staleness(d["meta"], self.ws)
        if st["status"] in ("stale", "contaminated"):
            raise RuntimeError("the imported layout dump is %s against the game's files (%s); re-export or re-import a dump "
                               "of this build before a join is built from it" % (st["status"], (st.get("message") or "").strip()))
        composition, others = self._uidoc_composition(d, b)
        if composition is None:
            return {"joinable": False, "included_in_compositions": others,
                    "reason": "the layout %s/%s is reached only as an included layout (of %s), never as a top layout of a "
                              "composition; this canvas keeps render-path addressing for it"
                              % (b.get("bundle"), b.get("path_id"), ", ".join(others[:3]) or "no composition")}
        doc = self._uidoc_document(d, composition)
        from .uidoc import build as uidoc_build
        from .uidoc.model import HOST, ROOT, SCREEN
        lay = {l["id"]: l for l in d["layouts"]}
        instances = []
        for host in doc.root_node.children:
            stack = [(host, None)]
            while stack:
                u, cell = stack.pop()
                if u.kind == HOST:
                    stack.extend((c, u.locator.get("cell_index")) for c in u.children)
                    continue
                if u.kind != ROOT:
                    continue
                top_target = self._renderer().layouts.target(u.locator.get("layout_guid"))
                top_row = next((l for l in lay.values() if l["guid"] == u.locator.get("layout_guid")), None)
                rows, not_drawn = {}, {}
                stack2 = [u]
                while stack2:
                    n = stack2.pop()
                    if n is not u:
                        if n.computed_style is not None:
                            rows[n.render_pos] = {"logical_id": n.logical_id, "m_id": str(n.locator.get("m_id")),
                                                  "bundle": n.locator.get("bundle"), "path_id": str(n.locator.get("path_id")),
                                                  "layout": n.locator.get("layout"), "layout_guid": n.locator.get("layout_guid"), "state": "joined"}
                        elif n.kind not in (HOST, SCREEN):
                            reason = uidoc_build.Builder._not_drawn_reason(n) or "unmatched"
                            (not_drawn if reason != "unmatched" else rows)[n.render_pos or ""] = {
                                "logical_id": n.logical_id, "m_id": str(n.locator.get("m_id")), "layout": n.locator.get("layout"),
                                "layout_guid": n.locator.get("layout_guid"), "state": ("not_drawn:" + reason) if reason != "unmatched" else "unmatched"}
                    stack2.extend(n.children)
                instances.append({"top": {"guid": u.locator.get("layout_guid"), "name": top_row["name"] if top_row else None,
                                          "bundle": top_target[0] if top_target else (top_row.get("bundle") if top_row else None),
                                          "path_id": str(top_target[1]) if top_target else None},
                                  "cell_index": cell, "rows": rows, "not_drawn": not_drawn})
        out = {"composition": composition, "other_compositions": others,
               "breakpoint": doc.screen["breakpoint"], "breakpoint_status": doc.screen["breakpoint_status"],
               "identity": doc.identity_scheme, "counts": doc.composition["join"], "instances": instances,
               "cell_configurations": doc.composition.get("cell_configurations")}
        bundle, pid = b.get("bundle"), b.get("path_id")
        if bundle and pid:
            guid = self._layout_guid(bundle, pid)
            mine = [i for i in instances if i["top"]["guid"] == guid]
            out["layout"] = {"bundle": bundle, "path_id": str(pid), "guid": guid}
            out["joinable"] = bool(mine)
            out["instances"] = mine
            out["shared_by_cells"] = sorted(str(i["cell_index"]) for i in mine if i["cell_index"] is not None)
            if not mine:
                closure = self._uidoc_closure(d, composition)
                included = guid in {lay[i]["guid"] for i in closure}
                out["included_by_the_screen"] = included
                out["reason"] = ("the layout takes part in %s only as an included layout; its own render numbers positions from "
                                 "its own root, so this canvas keeps render-path addressing for it" % composition) if included else \
                                ("the layout is not one of %s's drawn top layouts (the assembler picks the tile each cell draws); "
                                 "this canvas keeps render-path addressing for it" % composition)
        return out

    # ---- Stage 5D: the editable inspector - every validation and classification comes from the backend
    COLOUR_PROPS = ("color", "background-color", "border-color", "-unity-background-image-tint-color")
    VISIBILITY_PROPS_5D = ("visibility", "display")

    def _uidoc_instances(self, doc):
        """The layout instances of one document as the canvas sees them: (root node, cell_index) for the panel
        layout and for every cell's tile layout."""
        from .uidoc.model import HOST, ROOT
        out = []
        for child in doc.root_node.children:
            stack = [(child, None)]
            while stack:
                u, cell = stack.pop()
                if u.kind == HOST:
                    stack.extend((c, u.locator.get("cell_index")) for c in u.children)
                    continue
                if u.kind != ROOT:
                    continue
                out.append((u, cell))
        return out

    def _uidoc_node(self, d, b, joined_only=True):
        """The joined UiDocument node an inspector call addresses: by logical_id, or by render_pos on a top layout
        of the composition (the canvas's selection; the layout named by bundle + path_id selects the instances).
        A position shared by several instances is refused by name."""
        composition, _others = self._uidoc_composition(d, b)
        if composition is None:
            raise KeyError("no such composition: the layout takes part in no composition as a top layout")
        doc = self._uidoc_document(d, composition)
        node, hits = None, []
        if b.get("logical_id"):
            node = doc.index.get(b["logical_id"])
            if node is None:
                raise KeyError("no such node: %r is not in this document" % b["logical_id"])
        elif b.get("render_pos") is not None:
            want = None
            if b.get("bundle") and b.get("path_id"):
                want = self._layout_guid(b["bundle"], b["path_id"])          # restrict to this layout's instances
            for root, _cell in self._uidoc_instances(doc):
                if want is not None and root.locator.get("layout_guid") != want:
                    continue
                stack = [root]
                while stack:
                    u = stack.pop()
                    if u is not root and u.render_pos == b["render_pos"]:
                        hits.append(u)
                    stack.extend(u.children)
            if not hits:
                raise KeyError("no joined node at render position %r: the inspector edits joined nodes only" % b["render_pos"])
            joined = [u for u in hits if u.computed_style is not None]
            if joined_only and not joined:
                raise RuntimeError("this node is not drawn by the render (a root or a non-visual component); the inspector edits joined nodes only")
            if len(joined) > 1:
                raise KeyError("render position %r is shared by %d instances of this layout (%s); name the composition's "
                               "cell or address by logical id" % (b["render_pos"], len(joined), ", ".join(sorted(set(u.locator.get("layout") or "" for u in joined))[:3])))
            node = joined[0] if joined_only else hits[0]
        else:
            raise KeyError("address the node by logical_id or by render_pos")
        if joined_only and node.computed_style is None:
            raise RuntimeError("this node is not drawn by the render (a root or a non-visual component); the inspector edits joined nodes only")
        return composition, doc, node

    def _uidoc_reach(self, selector):
        """The MEASURED reach of one selector, as playops validation takes it: from layout.reach over the visual
        trees of the configured game (read only, cached). A static lower bound: includes not expanded, no
        table-factory rows, no runtime classes, pseudo-classes ignored."""
        from . import layout as layout_mod
        aa = self.need_info()["aa_dir"]
        trees = layout_mod.load_trees(aa, self.ws.cache)
        res = layout_mod.reach([{"selector": selector}], trees)
        rows = res["rows"]
        elements = sum(r["hits"] for r in rows)
        templates = sorted({t for r in rows for t in r["templates"]})
        note = "measured by layout.reach over the game's visual trees; a static lower bound (includes not expanded, " \
               "table-factory rows and runtime classes absent, pseudo-class states ignored)"
        if len(templates) == 5 and any(len(r["templates"]) == 5 for r in rows):
            note += "; the template list is capped, so the layout count is a lower bound too"
        return {"elements": elements, "layouts": len(templates), "screens": len(templates),
                "measured_by": "layout.reach (static lower bound)", "note": note,
                "templates": templates[:5], "no_match": res["no_match"] > 0}

    def uidoc_inspect(self, q, b):
        """The editable surface of one JOINED node: every computed property with its evidence class and source,
        what this node accepts editing (colour, spacing, visibility), a selector proposal built from the node's
        own class/hierarchy evidence WITH ITS MEASURED reach, and, for a colour, the two routes (token versus
        scoped rule) with what each would change. Read only; nothing is validated against a session here."""
        d = layout_dump.load(self.ws)
        if d is None:
            raise RuntimeError("no layout dump is imported")
        st = layout_dump.staleness(d["meta"], self.ws)
        if st["status"] in ("stale", "contaminated"):
            raise RuntimeError("the imported layout dump is %s against the game's files (%s); re-export or re-import a dump "
                               "of this build before the inspector is built on it" % (st["status"], (st.get("message") or "").strip()))
        composition, doc, node = self._uidoc_node(d, b)
        from . import playops, token_patch as tp
        props = []
        for name, cd in (node.computed_style.get("computed") or {}).items():
            kind = ("colour" if name in self.COLOUR_PROPS else
                    "spacing" if playops.SPACING.fullmatch(name) else
                    "visibility" if name in self.VISIBILITY_PROPS_5D else None)
            props.append({"name": name, "value": cd.get("value"), "evidence": cd.get("status"), "note": cd.get("note"),
                          "tokens": cd.get("tokens"), "source": cd.get("source"), "editable": kind,
                          "runtime_caveat": kind == "visibility"})
        classes = [c for c in node.classes if c]
        if classes:
            proposal, why = "." + classes[0], "the element's own class %r" % classes[0]
        elif node.name:
            proposal, why = "#" + node.name, "the element's name %r (names repeat: the reach says what it would change)" % node.name
        else:
            proposal, why = node.type, "the element's type only (widest possible scope; the reach is expected to be large)"
        reach = self._uidoc_reach(proposal)
        colour_routes = None
        colour_decl = next(((n, cd) for n, cd in (node.computed_style.get("computed") or {}).items()
                            if n in self.COLOUR_PROPS and cd.get("tokens")), None)
        if colour_decl:
            chain = [t for t in colour_decl[1]["tokens"] if isinstance(t, str)]
            colour_routes = {"through_token": {"token": chain[-1] if chain else None, "chain": chain,
                                               "effect": "every user of the token changes (unmeasured here; the review lists the token's screens)"},
                             "through_scoped_rule": {"selector": proposal, "reach": reach,
                                                     "effect": "only what the selector matches, on every screen (measured above)"}}
        return {"composition": composition, "node": {"logical_id": node.logical_id, "structural_key": node.structural_key,
                                                     "type": node.type, "name": node.name, "classes": node.classes,
                                                     "layout": node.locator.get("layout"), "layout_guid": node.locator.get("layout_guid"),
                                                     "locator": {k: node.locator.get(k) for k in ("bundle", "path_id", "m_id")},
                                                     "bundle_sha256": (node.locator.get("physical") or {}).get("bundle_sha256"),
                                                     "render_pos": node.render_pos},
                "properties": props, "selector": {"selector": proposal, "reason": why, "reach": reach},
                "colour_routes": colour_routes,
                "visibility_caveat": ("a sheet visibility/display rule can be overridden by inline styles set by code at runtime - "
                                      "on the measured Team Instructions screen 26 of 58 nodes carry learned runtime classes - so the "
                                      "effect of a visibility edit is RUNTIME-DEPENDENT, not guaranteed") if any(p["runtime_caveat"] for p in props) else None}

    def uidoc_classify(self, q, b):
        """Validate a PROPOSED edit of one joined node through the 5B model: the candidate operation is built here
        from the node's own identity and validated by `playops.validate` - the backend owns every classification
        (route, scope, refusal). Nothing is written: the operation is returned, not added to a session."""
        d = layout_dump.load(self.ws)
        if d is None:
            raise RuntimeError("no layout dump is imported")
        st = layout_dump.staleness(d["meta"], self.ws)
        if st["status"] in ("stale", "contaminated"):
            raise RuntimeError("the imported layout dump is %s against the game's files (%s); re-export or re-import a dump "
                               "of this build before an edit is classified" % (st["status"], (st.get("message") or "").strip()))
        composition, doc, node = self._uidoc_node(d, b)
        from . import playops
        kind = b.get("kind")
        props = b.get("props") or {}
        sheet = b.get("sheet") or {}
        if not sheet.get("name") or not sheet.get("bundle"):
            src = next((cd.get("source") or {} for cd in (node.computed_style.get("computed") or {}).values()
                        if (cd.get("source") or {}).get("sheet")), None)
            if src and src.get("sheet"):
                sheet = {"name": src["sheet"], "bundle": self._sheet_bundle(src["sheet"])}
            else:
                sheet = {"name": "AlwaysAppliedStyleSheet", "bundle": "ui-styles_assets_default.bundle"}
        selector = b.get("selector")
        if not selector:
            classes = [c for c in node.classes if c]
            selector = ("." + classes[0]) if classes else (("#" + node.name) if node.name else node.type)
        rule = {"sheet": {"bundle": sheet["bundle"], "name": sheet["name"]}, "selector": selector,
                "props": dict(props), "reach": b.get("reach") or self._uidoc_reach(selector)}
        new = {"rule": rule}
        if kind == "SetColor":
            new["route"] = b.get("route") or {}
        elif kind == "ReplaceToken":
            new = {"token": (b.get("token") or (props or {}).get("token")), "value": props,
                   "route": b.get("route") or {}}
        target = {"screen": composition, "logical_id": node.logical_id, "structural_key": node.structural_key,
                  "locator": {"bundle": node.locator.get("bundle"), "bundle_sha256": (node.locator.get("physical") or {}).get("bundle_sha256"),
                              "cab": None, "path_id": str(node.locator.get("path_id")), "m_id": str(node.locator.get("m_id"))},
                  "guard": {"type": node.type, "name": node.name, "classes": list(node.classes)},
                  "render_pos": node.render_pos}
        original = b.get("original")
        if not original and props:
            name = sorted(props)[0]
            cd = (node.computed_style.get("computed") or {}).get(name) or {}
            src = cd.get("source") or {}
            if src.get("inherited"):
                src = src.get("from") or {}
            prov = {"field": name}
            if src.get("inline"):
                prov.update({"bundle": node.locator.get("bundle"), "inline": True, "path_id": str(node.locator.get("path_id"))})
            elif src.get("sheet"):
                try:
                    prov.update({"bundle": self._sheet_bundle(src["sheet"]), "sheet": src["sheet"],
                                 "selector": src.get("selector"), "occurrence": 0})
                except KeyError:
                    prov.update({"bundle": node.locator.get("bundle"), "sheet": src["sheet"],
                                 "selector": src.get("selector"), "occurrence": 0, "bundle_unverified": True})
            original = {"value": cd.get("value"), "evidence": cd.get("status") or "unknown", "provenance": prov}
        op = playops.new_operation(kind, target, new, original=original, note=b.get("note") or "")
        try:
            validation = playops.validate(op)
        except playops.OperationError as e:
            return {"refused": str(e), "operation": op}
        op["validation"] = validation
        return {"operation": op, "validation": validation}

    def _sheet_bundle(self, name):
        """The bundle an applied sheet lives in, from the render's own sheet bank (read only)."""
        for s in self._renderer().bank.ordered():
            if s.name == name:
                return s.bundle
        raise KeyError("no applied sheet named %r" % name)

    # ---- Stage 5F: the deterministic preview engine
    def _preview_dump(self):
        f = self.ws.layout / "current.json"
        m = f.stat().st_mtime_ns if f.is_file() else None
        cached = getattr(self, "_raw_dump", (None, None))
        if m is not None and cached[0] == m and cached[1] is not None:
            d = cached[1]
        else:
            d = layout_dump.load(self.ws)
            self._raw_dump = (m, d)
        if d is None:
            raise RuntimeError("no layout dump is imported")
        st = layout_dump.staleness(d["meta"], self.ws)
        if st["status"] in ("stale", "contaminated"):
            raise RuntimeError("the imported layout dump is %s against the game's files (%s); the preview needs a "
                               "fresh dump (re-export or re-import the dump of this build)" % (st["status"], (st.get("message") or "").strip()))
        return d

    def _preview_ops(self, project):
        """The effective operations' projection (read only): the preview draws what the session holds."""
        if not project:
            return None
        from . import playops
        s, _folder = self._playground_session(project)
        return self._playground_projection(project, s)

    def render_preview(self, q, b):
        """The deterministic preview: the composition selection from the MEASURED width points (the
        breakpoint keys read from the composition set's data), the grid, the hosts, the tree with exactly one
        evidence flag per node, the UI-state cascade (the sheets' own pseudo rules, a separate path), the
        seeded placeholder content, and the session's operations. UI1 adds an additive `confidence`
        block (label + tooltip payload, including the other engine's cell geometry). Read only."""
        d = self._preview_dump()
        rd = self._renderer()
        from .render import compositionset, preview as preview_mod
        ops = self._preview_ops(b.get("project"))
        project = project_mod.load(self.ws, b["project"]) if b.get("project") else None
        return preview_mod.build_preview(
            d, rd, b["screen"], int(b["width"]), int(b["height"]), b.get("setting") or "Large UI",
            [s for s in (b.get("states") or []) if s != "normal"], b.get("seed") or "preview",
            session_operations=ops, simulated_visible=b.get("simulated_visible", True),
            reserved_right=int(b.get("reserved_right") or 0),
            runtime_classes=getattr(rd, "_rc", None) or {},
            layouts=rd.layouts, sets=compositionset.index(rd.layouts),
            game_states=b.get("game_states") or {},
            competition=b.get("competition"),
            custom_layouts=self._custom_layouts(b),
            engine=project_mod.layout_engine(project))

    def _custom_layouts(self, b):
        """CL3 C2: the game's own custom-layout files (a file named by the composition) so the preview shows a customised screen as the game does. Read only;
        pass use_custom_layouts: false to ignore them. UI4: `custom_layouts` carries a STAGED object
        (never written) so the canvas sees the runtime result of a drag before Apply."""
        if b.get("use_custom_layouts") is False:
            return None
        from . import custom_layouts as cl
        try:
            out = {c["composition"]: cl.read(cl.folder() / c["composition"]) for c in cl.list_customised()}
        except Exception:
            out = {}
        staged = b.get("custom_layouts")
        if isinstance(staged, dict):
            out.update({str(k): v for k, v in staged.items() if isinstance(v, dict)})
        return out

    def render_preview_compare(self, q, b):
        """Side-by-side: two resolutions with their selections, plus the cell differences between them
        (cells matched by element id). Read only."""
        d = self._preview_dump()
        rd = self._renderer()
        from .render import compositionset, preview as preview_mod
        ops = self._preview_ops(b.get("project"))
        project = project_mod.load(self.ws, b["project"]) if b.get("project") else None
        return preview_mod.compare_preview(
            d, rd, b["screen"], (int(b["a_width"]), int(b["a_height"])), (int(b["b_width"]), int(b["b_height"])),
            b.get("setting") or "Large UI", b.get("seed") or "preview", ops,
            simulated_visible=b.get("simulated_visible", True),
            layouts=rd.layouts, sets=compositionset.index(rd.layouts),
            game_states=b.get("game_states") or {},
            competition=b.get("competition"),
            engine=project_mod.layout_engine(project))

    # ---- Stage 5H: the preview settings travel with the project's session
    def playground_preview_settings(self, q, b):
        """Read or save the Playground's preview settings (resolution, setting, seed, state, simulated toggle,
        game states) in the project's own session, so they survive save-as/export/import/duplicate and a
        reload. Read only when `settings` is absent."""
        from . import playops
        s, folder = self._playground_session(b["project"])
        if b.get("settings") is not None:
            s["preview"] = dict(b["settings"])
            playops.save(folder, s)
        return {"preview": s.get("preview")}

    # ---- Stage 5G: the session as a reviewed build
    def build_session(self, q, b):
        """Build the project's Playground session from the VERIFIED stock snapshot (never the live game
        folder): route every applied operation by what has been proven, check the source identity, detect
        same-cell conflicts and overlaps, rebuild only the target bundles, compare the built cell layer with
        the intended moves exactly, write the skin folder and the schema 2 package, and report. 5G installs
        nothing."""
        import time
        from . import build5g
        from .render import compositionset
        s, _folder = self._playground_session(b["project"])
        man = self.ws.vanilla_manifest()
        if not man:
            raise RuntimeError("no vanilla snapshot: 5G builds from the verified stock snapshot, never the live "
                               "game folder - take the vanilla snapshot first")
        rd = self._renderer()
        full = compositionset.index_full(rd.layouts)
        identity = {"game_build": man.get("game_build") or self._game_build(),
                    "files": {n: f["sha256"] for n, f in (man.get("files") or {}).items()},
                    "source": str(self.ws.vanilla)}
        ts = b.get("ts") or time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
        dest = Path(self.ws.build) / b["project"] / ts
        layout_source = self._layout_source_for(s, identity)
        return build5g.build(s, ws=self.ws, source=self.ws.vanilla, identity=identity, layout_source=layout_source,
                             dump=self._preview_dump(), compositions=full["compositions"],
                             index=self.index, aa_dir=self.need_info()["aa_dir"], dest=dest, ts=ts,
                             referrers=b.get("referrers") or {}, customised=self._customised_names(),
                             manifest_path=Path(self.need_info()["game_dir"]) / "fm_Data" / "manifest.dat")

    def _layout_source_for(self, session, identity):
        """The vanilla snapshot holds the two style bundles only, so the layout bundles a session's layout operations target are read from the game folder, and only while they verify
        as STOCK (the tamper rule of `_render_folder`, here for the target bundle itself). Their sha256 joins the build's source identity. Returns the folder, or None when the
        snapshot already holds them all (found by the E2E1 chain: a layout build through the app had never been possible from the snapshot alone)."""
        from . import playops
        want = set()
        for op in playops.effective(session):
            if op.get("kind") in playops.LAYOUT_KINDS:
                b = ((op.get("target") or {}).get("locator") or {}).get("bundle")
                if b and b not in identity["files"]:
                    want.add(b)
        if not want:
            return None
        aa = Path(self.need_info()["aa_dir"])
        install.refuse_if_updated(self.ws, str(aa), "The build")
        t = install.tamper_status(self.ws, str(aa))
        for name in sorted(want):
            state = (t.get("files") or {}).get(name)
            if state != "stock" or not (aa / name).is_file():
                raise RuntimeError("the game's layout bundle %s is not stock (%s); restore it (Steam: Verify integrity of game files) before building a layout edit" % (name, state or "not checked"))
            identity["files"][name] = install.sha256(aa / name)
        return aa

    # ---- ST1: the game's custom-layout files (a screen customised in the game uses its file instead of the bundle)
    def _customised_names(self):
        from . import custom_layouts as cl
        try:
            return [c["composition"] for c in cl.list_customised()]
        except Exception:
            return []

    def _layout_journal(self):
        d = self.ws.root / "custom-layout-journal"
        d.mkdir(parents=True, exist_ok=True)
        return d

    def custom_layouts_list(self, q, b):
        """READ ONLY: the screens customised in the game (a file named by the composition in the game's CustomGridCompositions folder) with size, mtime and sha256, and the
        badge text the Playground shows. Nothing is written."""
        from . import custom_layouts as cl
        fold = cl.folder()
        files = cl.list_customised(fold)
        return {"folder": str(fold), "folder_exists": fold.is_dir(), "files": files,
                "badge": "customised in the game: this file is used instead of the bundle",
                "warning": "a bundle layout edit on a customised screen will not show"}

    def playground_tile_set(self, q, b):
        """The tiles available in one composition's OWN tile set (its m_gridElementSet): id, description object and configuration sizes. A SwapTile may only use these. Read only."""
        from . import custom_layouts as cl
        d = self._preview_dump()
        rec = next((c for c in d.get("compositions") or [] if c.get("name") == b["composition"]), None)
        if rec is None:
            raise ValueError("unknown composition %r" % b["composition"])
        rd = self._renderer()
        objs = rd.layouts._bundle_objs(rec["bundle"])
        tt = objs[int(rec["path_id"])].read_typetree()
        rows = cl.tile_set(tt, objs)
        proj_name = b.get("project")
        if proj_name:
            p = project_mod.load(self.ws, proj_name)
            ops = p.get("tile_bundle_ops") or []
            set_pid = str((tt.get("m_gridElementSet") or {}).get("m_PathID", ""))
            by_id = {r["id"]: r for r in rows}
            for op in ops:
                if op.get("op") == "set-remove-tile" and str(op.get("path_id")) == set_pid:
                    rows = [r for r in rows if r["id"] != op.get("description_id")]
                    by_id.pop(op.get("description_id"), None)
                elif op.get("op") == "set-add-tile" and str(op.get("path_id")) == set_pid:
                    desc_obj = objs.get(int(op["description_path_id"]))
                    dt = desc_obj.read_typetree() if desc_obj is not None else {}
                    did = dt.get("<ID>k__BackingField") or dt.get("m_Name") or op.get("description_id")
                    cfgs = dt.get("<Configurations>k__BackingField") or []
                    sizes = sorted({(c["Size"]["x"], c["Size"]["y"]) for c in cfgs})
                    if did not in by_id:
                        entry = {"id": did, "object": dt.get("m_Name") or did, "sizes": [list(z) for z in sizes],
                                 "added_by_project": True, "label": "added by project (bundle build required)"}
                        rows.append(entry)
                        by_id[did] = entry
                    else:
                        by_id[did]["added_by_project"] = True
                        by_id[did].setdefault("label", "added by project")
            for op in ops:
                if op.get("op") == "add-tile-size":
                    did = op.get("description")
                    sz = [int(op["size"]["x"]), int(op["size"]["y"])]
                    target = by_id.get(did) or next((r for r in rows if r["object"] == did), None)
                    if target is not None:
                        if sz not in target["sizes"]:
                            target["sizes"].append(sz)
                            target["sizes"].sort()
                        target.setdefault("added_sizes", []).append(sz)
                        target["size_labels"] = {**target.get("size_labels", {}), f"{sz[0]}x{sz[1]}": "added by project (bundle build required)"}
        return {"composition": b["composition"], "tiles": rows}

    def _tileslayouts_bundle_path(self):
        aa = (self.info or {}).get("aa_dir")
        if aa:
            p = Path(aa) / "ui-tileslayouts_assets_all.bundle"
            if p.is_file():
                return p
        p = self.ws.vanilla / "ui-tileslayouts_assets_all.bundle"
        if p.is_file():
            return p
        raise RuntimeError("ui-tileslayouts_assets_all.bundle is not available in the game folder or snapshot")

    def tiles_descriptions(self, q, b):
        """B2: list every TileDescription with its sizes and the UXML GUID each configuration uses."""
        from . import tiles as tiles_mod
        rows = tiles_mod.list_tile_descriptions(self._tileslayouts_bundle_path())
        qf = (b.get("q") or "").strip().lower()
        if qf:
            rows = [r for r in rows if qf in r["id"].lower() or qf in r["name"].lower()]
        return {"descriptions": rows}

    def tiles_element_sets(self, q, b):
        """B3: list every GridElementSet and the TileDescriptions it allows."""
        from . import tiles as tiles_mod
        rows = tiles_mod.list_element_sets(self._tileslayouts_bundle_path())
        qf = (b.get("q") or "").strip().lower()
        if qf:
            rows = [r for r in rows if qf in r["name"].lower()]
        return {"element_sets": rows}

    def tiles_add_size(self, q, b):
        """B2: record an add-tile-size project patch op on ui-tileslayouts (reusing an existing GUID)."""
        from . import tiles as tiles_mod
        p = project_mod.load(self.ws, b["project"])
        if not project_mod.experimental_tile_sizes(p):
            raise ValueError("Tile sizes is experimental (not owner-confirmed in v1.5): enable 'experimental: tile sizes' in BUILD first")
        bundle_path = self._tileslayouts_bundle_path()
        descs = tiles_mod.list_tile_descriptions(bundle_path)
        target = next((d for d in descs if str(d["path_id"]) == str(b.get("path_id"))
                       or d["id"] == b.get("description") or d["name"] == b.get("description")), None)
        if target is None:
            raise ValueError("unknown tile description %r" % (b.get("description") or b.get("path_id")))
        w, h = int(b["width"]), int(b["height"])
        guid = b.get("reuse_guid") or (target["configurations"][0]["guid"] if target["configurations"] else "")
        if not any(c["guid"] == guid for c in target["configurations"]):
            raise ValueError("GUID %s does not belong to %s; never create a new GUID" % (guid, target["name"]))
        op = {"op": "add-tile-size", "bundle": "ui-tileslayouts_assets_all.bundle",
              "path_id": str(target["path_id"]), "description": target["id"],
              "size": {"x": w, "y": h}, "reuse_guid": guid}
        ops = list(p.get("tile_bundle_ops") or [])
        ops.append(op)
        tiles_mod.validate_ops(ops)
        p["tile_bundle_ops"] = ops
        project_mod.save(self.ws, p)
        return {"op": op, "tile_bundle_ops": ops}

    def tiles_set_allow(self, q, b):
        """B3: record a set-add-tile or set-remove-tile op on a GridElementSet."""
        from . import tiles as tiles_mod
        p = project_mod.load(self.ws, b["project"])
        action = b.get("action")
        if action not in ("add", "remove"):
            raise ValueError("action must be 'add' or 'remove'")
        bundle_path = self._tileslayouts_bundle_path()
        sets = tiles_mod.list_element_sets(bundle_path)
        descs = tiles_mod.list_tile_descriptions(bundle_path)
        es = next((s for s in sets if str(s["path_id"]) == str(b.get("set_path_id")) or s["name"] == b.get("element_set")), None)
        if es is None:
            raise ValueError("unknown GridElementSet %r" % (b.get("element_set") or b.get("set_path_id")))
        desc = next((d for d in descs if str(d["path_id"]) == str(b.get("description_path_id"))
                     or d["id"] == b.get("description") or d["name"] == b.get("description")), None)
        if desc is None:
            raise ValueError("unknown tile description %r" % (b.get("description") or b.get("description_path_id")))
        op = {"op": "set-add-tile" if action == "add" else "set-remove-tile",
              "bundle": "ui-tileslayouts_assets_all.bundle",
              "path_id": str(es["path_id"]), "element_set": es["name"],
              "description_path_id": str(desc["path_id"]), "description_id": desc["id"]}
        ops = list(p.get("tile_bundle_ops") or [])
        ops.append(op)
        tiles_mod.validate_ops(ops)
        p["tile_bundle_ops"] = ops
        project_mod.save(self.ws, p)
        return {"op": op, "tile_bundle_ops": ops}

    def _project_bundle_build_installed(self, project_name, bundle_name="ui-tileslayouts_assets_all.bundle"):
        """True when the project's latest bundle build changed `bundle_name` and that exact sha256 is in aa_dir."""
        latest = patcher.latest_build(self.ws, project_name)
        if not latest or not (Path(latest) / bundle_name).is_file():
            return False
        aa = (self.info or {}).get("aa_dir")
        if not aa or not (Path(aa) / bundle_name).is_file():
            return False
        return bundles.sha256(Path(aa) / bundle_name) == bundles.sha256(Path(latest) / bundle_name)

    def _refuse_if_uninstalled_project_tile_ops(self, project_name, objs):
        """B2/B3 apply guard: refuse custom files using a project-added size/tile until the bundle build is installed."""
        p = project_mod.load(self.ws, project_name)
        ops = p.get("tile_bundle_ops") or []
        if not ops:
            return None
        added_sizes = {(op.get("description"), int(op["size"]["x"]), int(op["size"]["y"]))
                       for op in ops if op.get("op") == "add-tile-size"}
        added_tiles = {op.get("description_id") for op in ops if op.get("op") == "set-add-tile"}
        needs_bundle = False
        for obj in objs:
            for c in (obj.get("m_gridComponents") or ()):
                eid = c.get("m_elementID")
                loc = c.get("m_location") or {}
                keys = list(c.get("m_configDescriptionKeys") or ()) + [eid]
                w, h = int(loc.get("width", 0)), int(loc.get("height", 0))
                if any((k, w, h) in added_sizes for k in keys):
                    needs_bundle = True
                if any(k in added_tiles for k in keys):
                    needs_bundle = True
        if needs_bundle and not self._project_bundle_build_installed(project_name):
            return ("custom file uses a tile size or allowed tile added by project %s; "
                    "build and install the project's bundle build first" % project_name)
        return None

    def _latest_layout_package(self, project):
        d = patcher.latest_build(self.ws, project)
        if not d or not (Path(d) / "custom-layouts.json").is_file():
            raise RuntimeError("the latest build of %s holds no custom-layout files" % project)
        return d

    def customlayout_preflight(self, q, b):
        """READ ONLY: what putting the latest build's custom-layout files into the game folder would do: every file, each file already in the folder (a screen customised in the
        game) flagged, and the confirmations needed to replace it."""
        from . import layouttx
        return layouttx.preflight(self._latest_layout_package(b["project"]), journal=self._layout_journal())

    def customlayout_apply(self, q, b):
        """One custom-layout transaction: the whole folder backed up and verified, the files written and hash-checked, a journal kept. Refused unless every replace is confirmed
        and the game is closed."""
        from . import custom_layouts as cl, layouttx
        pkg = self._latest_layout_package(b["project"])
        proj = project_mod.load(self.ws, b["project"])
        if proj.get("tile_bundle_ops"):
            pkg_files = []
            for f in (json.loads((pkg / "custom-layouts.json").read_text(encoding="utf-8")).get("files") or []):
                fp = pkg / "custom-layouts" / f["name"]
                if fp.is_file():
                    try:
                        pkg_files.append(cl.read(fp))
                    except ValueError:
                        pass
            guard = self._refuse_if_uninstalled_project_tile_ops(b["project"], pkg_files)
            if guard:
                return {"refused": guard, "blocked": ["project_bundle_build_required"], "required_confirmations": []}
        try:
            return layouttx.apply(self._layout_journal(), pkg, confirmations=b.get("confirmations") or [],
                                  running=self.running)
        except layouttx.LayoutTxRefused as e:
            return {"refused": str(e), "blocked": e.blocked, "required_confirmations": e.confirmations}

    def customlayout_rollback(self, q, b):
        """Roll one custom-layout transaction back to the exact earlier state (the user's own files byte for byte; a file changed since is never overwritten)."""
        from . import layouttx
        return layouttx.rollback(self._layout_journal(), b["tx_id"])

    def customlayout_restore_before(self, q, b):
        """Put the game folder back to its state before one transaction, even when the game re-saved a
        file since Apply (rollback refuses that case). Without confirm it reports what changed."""
        from . import layouttx
        return layouttx.restore_to_before(self._layout_journal(), b["tx_id"], confirm=bool(b.get("confirm")))

    def customlayout_recovery_scan(self, q, b):
        """READ ONLY: unfinished custom-layout transactions, assessed against the journal and the hashes on disk."""
        from . import layouttx
        return layouttx.recovery_scan(self._layout_journal())

    def _cached_composition_bundle(self, comp):
        """UI5: cache the parsed bundle composition (base custom-layout object, m_reflowMode, design extent,
        and dump cells) per session so only the first call reads bundles with UnityPy."""
        from . import custom_layouts as cl
        dump = self._preview_dump()
        fp = (dump.get("meta") or {}).get("index_fingerprint")
        cache = getattr(self, "_comp_bundle_cache", None)
        if cache is None or cache[0] != fp:
            cache = self._comp_bundle_cache = (fp, {})
        hits = cache[1]
        if comp in hits:
            return hits[comp]
        rec = next((c for c in (dump.get("compositions") or []) if c.get("name") == comp), None)
        if rec is None:
            raise ValueError("unknown composition %r" % comp)
        dump_cells = [dict(c) for c in (dump.get("cells") or []) if c.get("composition") == comp]
        if rec.get("bundle") and rec.get("path_id") is not None:
            objs = self._renderer().layouts._bundle_objs(rec["bundle"])
            tt = objs[int(rec["path_id"])].read_typetree()
            obj = cl.generate(tt, objs)
            reflow = tt.get("m_reflowMode")
        else:
            obj = {"m_Name": comp, "m_isCustom": True, "m_layoutMode": 0, "m_reflowMode": 0,
                   "m_gridComponents": [
                       {"m_elementID": c["element_id"],
                        "m_location": {"x": c["x"], "y": c["y"], "width": c["w"], "height": c["h"]},
                        "m_minSize": {"x": c.get("min_w", c["w"]), "y": c.get("min_h", c["h"])},
                        "m_maxSize": {"x": c.get("max_w", c["w"]), "y": c.get("max_h", c["h"])}}
                       for c in sorted(dump_cells, key=lambda x: x.get("cell_index", 0))],
                   "m_optionalSlices": {"m_right": [], "m_bottom": []}}
            reflow = 0
        cols, rows = cl.grid_extent(obj)
        entry = {"object": obj, "reflow": reflow, "design": {"cols": cols, "rows": rows}, "cells": dump_cells}
        hits[comp] = entry
        return entry

    @staticmethod
    def _extract_space_cells(obj):
        cells = []
        for i, c in enumerate(obj.get("m_gridComponents") or []):
            loc, mn, mx = c.get("m_location") or {}, c.get("m_minSize") or {}, c.get("m_maxSize") or {}
            cells.append({"space": "main", "order": i, "element_id": c.get("m_elementID"),
                          "x": int(loc.get("x", 0)), "y": int(loc.get("y", 0)),
                          "width": int(loc.get("width", 0)), "height": int(loc.get("height", 0)),
                          "min_w": int(mn.get("x", 1)), "min_h": int(mn.get("y", 1)),
                          "max_w": int(mx.get("x", 0)), "max_h": int(mx.get("y", 0))})
        for zone, entries in (obj.get("m_optionalSlices") or {}).items():
            if not isinstance(entries, list):
                continue
            for i, e in enumerate(entries):
                if not isinstance(e, dict) or "m_elementID" not in e:
                    continue
                loc, mn, mx = e.get("m_location") or {}, e.get("m_minSize") or {}, e.get("m_maxSize") or {}
                cells.append({"space": zone, "order": i, "element_id": e.get("m_elementID"),
                              "x": int(loc.get("x", 0)), "y": int(loc.get("y", 0)),
                              "width": int(loc.get("width", 0)), "height": int(loc.get("height", 0)),
                              "min_w": int(mn.get("x", 1)), "min_h": int(mn.get("y", 1)),
                              "max_w": int(mx.get("x", 0)), "max_h": int(mx.get("y", 0))})
        return cells

    def customlayout_base(self, q, b):
        """READ ONLY: the base custom-layout object for the canvas, with every cell in its own space.
        The owner's file when one exists, otherwise the bundle composition; never written."""
        from . import custom_layouts as cl, layoutspace, layouttx
        from .render import preview as preview_mod
        comp = b["composition"]
        profile = layoutspace.normalize_profile(b.get("profile"))
        cached = self._cached_composition_bundle(comp)
        bundle_obj = copy.deepcopy(cached["object"])
        bundle_cols, bundle_rows = cl.grid_extent(bundle_obj)
        bundle_cells = self._extract_space_cells(bundle_obj)
        f = cl.folder() / comp
        if f.is_file():
            obj, source = cl.read(f), "game_folder"
        else:
            obj, source = bundle_obj, "bundle"
        cols, rows = cl.grid_extent(obj)
        cells = self._extract_space_cells(obj)
        last_tx = None
        if source == "game_folder":
            for tx in reversed(layouttx.transactions(self._layout_journal())):
                if tx.get("state") == "completed" and any(o.get("name") == comp for o in (tx.get("ops") or [])):
                    last_tx = tx.get("tx_id")
                    break
        return {"composition": comp, "source": source, "object": obj, "cells": cells,
                "design": {"cols": cols, "rows": rows},
                "bundle_cells": bundle_cells, "bundle_design": {"cols": bundle_cols, "rows": bundle_rows},
                "last_tx": last_tx,
                "confidence": preview_mod.confidence_for(comp, "rea", profile=profile),
                "viewport": layoutspace.viewport_profile(profile),
                "profiles": [dict(v) for v in layoutspace.VIEWPORT_PROFILES.values()]}

    def customlayout_runtime(self, q, b):
        """FS1 / UI5: light runtime RPC for the Game Layouts canvas. Returns cells and optional
        slices with their runtime grid coordinates, pixel rects and movement reasons at the active
        viewport profile (default 2560x1440 fullscreen, Small, Larger; windowed selectable), plus
        runtime problems and profile-isolated confidence."""
        from . import custom_layouts as cl, layoutspace
        from .render import pitch as pitch_mod, preview as preview_mod, screen as screen_mod
        comp = b["composition"]
        profile = layoutspace.normalize_profile(b.get("profile"))
        project = project_mod.load(self.ws, b["project"]) if b.get("project") else None
        engine = project_mod.layout_engine(project)
        cached = self._cached_composition_bundle(comp)
        design_cols = int(cached["design"]["cols"])
        design_rows = int(cached["design"]["rows"])
        if isinstance(b.get("object"), dict):
            obj = copy.deepcopy(b["object"])
            source = "staged"
        else:
            f = cl.folder() / comp
            if f.is_file():
                obj, source = cl.read(f), "game_folder"
            else:
                obj, source = copy.deepcopy(cached["object"]), "bundle"
        vp = layoutspace.viewport_profile(profile)
        width = int(b.get("width") or vp["width"])
        height = int(b.get("height") or vp["height"])
        panel = preview_mod.panel_content_rect(comp, width, height, profile=profile)
        content_rect = panel[1] if panel else (vp["content_rect"] if (width, height) == (vp["width"], vp["height"]) else None)
        pad = preview_mod.composition_padding(self, comp, content_rect=content_rect)
        if content_rect is not None:
            rcols, rrows = screen_mod.grid_dims_content(content_rect[2], content_rect[3], padding=pad)
        else:
            rcols, rrows = screen_mod.grid_dims(width, height, pitch_mod.lookup(comp), padding=pad)
        if b.get("edits"):
            cl.apply_canvas_edits(obj, b["edits"], runtime={"cols": rcols, "rows": rrows})
        dcols, drows = cl.grid_extent(obj)
        design_cols = max(design_cols, dcols)
        design_rows = max(design_rows, drows)

        mini_dump = {"cells": [dict(c) for c in cached["cells"]], "layouts": [], "tiles": []}
        a = screen_mod.Assembler(mini_dump)
        preview_mod.apply_custom(a, comp, obj)
        if engine == "rea":
            a.optional_slices = preview_mod._optional_slices_from_custom(obj)
            a.layout_modes = {comp: int(obj.get("m_layoutMode") or 0)}
        placed = preview_mod.rule_place(a, comp, rcols, rrows, cached["reflow"], engine=engine)

        def px_rect(col, row, w, h):
            px = screen_mod.cell_px(col, row, w, h, padding=pad)
            if content_rect is not None:
                return [round(content_rect[0] + px["left"], 1), round(content_rect[1] + px["top"], 1),
                        round(px["width"], 1), round(px["height"], 1)]
            return [round(px["left"], 1), round(px["top"], 1), round(px["width"], 1), round(px["height"], 1)]

        surplus = max(0, rcols - design_cols)
        cells_out, slots_out, hosts_out = [], [], []
        for i, comp_cell in enumerate(obj.get("m_gridComponents") or []):
            eid = comp_cell.get("m_elementID")
            loc = comp_cell.get("m_location") or {}
            sx, sy, sw, sh = int(loc.get("x", 0)), int(loc.get("y", 0)), int(loc.get("width", 1)), int(loc.get("height", 1))
            strip = sx + sw >= design_cols
            exp_x, exp_y = sx + (surplus if strip else 0), sy
            g = placed.get(eid) or {"col": exp_x, "row": exp_y, "w": sw, "h": sh}
            rx, ry, rw, rh = int(g["col"]), int(g["row"]), int(g["w"]), int(g["h"])
            why = ""
            if ry < exp_y:
                why = "compacted up to row %d" % ry
            elif rx != exp_x:
                why = "placed at column %d (runtime strip)" % rx
            elif ry != exp_y:
                why = "placed at row %d" % ry
            rect = px_rect(rx, ry, rw, rh)
            rec = {"space": "main", "order": i, "element_id": eid,
                   "stored": {"x": sx, "y": sy, "w": sw, "h": sh},
                   "expected": {"x": exp_x, "y": exp_y, "w": sw, "h": sh},
                   "x": rx, "y": ry, "w": rw, "h": rh, "rect": rect, "reason": why,
                   "host": {"element_id": eid, "geometry": {"x": rx, "y": ry, "w": rw, "h": rh}}}
            cells_out.append(rec)
            hosts_out.append(rec)

        slices_obj = obj.get("m_optionalSlices") or {}
        placed_main = [{"element_id": c["element_id"], "x": c["x"], "y": c["y"], "w": c["w"], "h": c["h"]} for c in cells_out]
        shared_slots = layoutspace.place_zone_slots(
            preview_mod._optional_slices_from_custom(obj) if hasattr(preview_mod, "_optional_slices_from_custom") else {},
            (design_cols, design_rows), (rcols, rrows),
            cells=a.cells.get(comp), placed_cells=placed_main, existing_ids={c["element_id"] for c in cells_out},
        )
        for zone_key in layoutspace.FILE_ZONES:
            zone_placed = shared_slots.get(zone_key) or []
            for i, entry in enumerate(slices_obj.get(zone_key) or []):
                if not isinstance(entry, dict) or "m_elementID" not in entry:
                    continue
                eid = entry.get("m_elementID")
                loc = entry.get("m_location") or {}
                sx, sy, sw, sh = int(loc.get("x", 0)), int(loc.get("y", 0)), int(loc.get("width", 1)), int(loc.get("height", 1))
                sp = zone_placed[i] if i < len(zone_placed) else None
                if sp is not None:
                    rx, ry, rw, rh, visible = sp["col"], sp["row"], sp["w"], sp["h"], sp["visible"]
                else:
                    rt_loc = layoutspace.slot_to_runtime(zone_key, {"x": sx, "y": sy, "width": sw, "height": sh},
                                                         (design_cols, design_rows), (rcols, rrows))
                    rx, ry, rw, rh = rt_loc["x"], rt_loc["y"], rt_loc["w"], rt_loc["h"]
                    visible = rx >= 0 and ry >= 0 and rx + rw <= rcols and ry + rh <= rrows
                why = "" if visible else ("outside the %dx%d runtime grid" % (rcols, rrows))
                rect = px_rect(rx, ry, rw, rh)
                rec = {"space": zone_key, "order": i, "element_id": eid,
                       "stored": {"x": sx, "y": sy, "w": sw, "h": sh},
                       "expected": {"x": rx, "y": ry, "w": rw, "h": rh},
                       "x": rx, "y": ry, "w": rw, "h": rh, "rect": rect,
                       "visible": visible, "reason": why,
                       "host": {"element_id": eid, "geometry": {"x": rx, "y": ry, "w": rw, "h": rh}}}
                slots_out.append(rec)
                if visible:
                    hosts_out.append(rec)

        uncertain = bool(content_rect is not None and screen_mod.grid_size_uncertain(content_rect[2], content_rect[3], padding=pad))
        problems = layoutspace.runtime_problems(
            [{"element_id": h["element_id"], "x": h["x"], "y": h["y"], "w": h["w"], "h": h["h"]}
             for h in (cells_out + slots_out)],
            rcols, rrows)
        return {
            "composition": comp,
            "source": source,
            "engine": engine,
            "confidence": preview_mod.confidence_for(comp, engine, profile=profile),
            "viewport": dict(vp, width=width, height=height),
            "design": {"cols": design_cols, "rows": design_rows},
            "grid": {"cols": rcols, "rows": rrows, "padding": pad, "uncertain": uncertain,
                     "content_rect": list(content_rect) if content_rect else None},
            "cells": cells_out,
            "slots": slots_out,
            "hosts": hosts_out,
            "problems": problems,
        }

    def _runtime_hosts_for(self, comp, obj, width=2560, height=1440, profile=None):
        """The runtime hosts a staged custom object produces, for the post-conversion check."""
        rt = self.customlayout_runtime({}, {"composition": comp, "object": obj, "width": width, "height": height, "profile": profile})
        return {"cols": rt["grid"]["cols"], "rows": rt["grid"]["rows"],
                "hosts": [{"element_id": h["element_id"], "x": h["x"], "y": h["y"], "w": h["w"], "h": h["h"]}
                          for h in (rt.get("cells") or []) + (rt.get("slots") or [])]}

    def customlayout_apply_edits(self, q, b):
        """Build a valid custom-layout package from the Game Layouts canvas edits, then apply it through
        layouttx. The base is the owner's file when one exists, otherwise the bundle composition. Every
        byte still goes through custom_layouts.validate_before_write and layouttx.apply (backup + journal)."""
        from . import custom_layouts as cl, layouttx
        project, comp = b["project"], b["composition"]
        edits = b.get("edits") or []
        if any(str(e.get("space") or "main") != "main" for e in edits):
            proj_obj = project_mod.load(self.ws, project)
            if not project_mod.experimental_slot_edits(proj_obj):
                return {"refused": "Slot editing is experimental (not confirmed in-game in v1.5): enable 'experimental: slot edits' in BUILD first"}
        base = cl.folder() / comp
        if base.is_file():
            obj = cl.read(base)
        else:
            obj = copy.deepcopy(self._cached_composition_bundle(comp)["object"])
        if not cl.apply_canvas_edits(obj, edits, runtime=b.get("runtime")):
            return {"refused": "none of the edited tiles exist in " + comp}
        problems = cl.validate_before_write(obj, comp)
        if problems:
            return {"refused": "custom layout refused: " + "; ".join(problems)}
        guard = self._refuse_if_uninstalled_project_tile_ops(project, [obj])
        if guard:
            return {"refused": guard}
        # After the design/slot conversion, check what the game actually places: overlaps and
        # off-grid tiles in the runtime grid are blocked even when the stored numbers look legal.
        try:
            rt = self._runtime_hosts_for(comp, obj, b.get("width") or 2560, b.get("height") or 1440)
        except Exception as e:
            return {"refused": "the runtime result could not be checked: %s" % e}
        from . import layoutspace
        runtime_problems = layoutspace.runtime_problems(rt["hosts"], int(rt["cols"]), int(rt["rows"]))
        if runtime_problems:
            return {"refused": "runtime layout refused: " + "; ".join(runtime_problems)}
        pkg = Path(self.ws.build) / project / ("canvas-" + time.strftime("%Y%m%dT%H%M%SZ", time.gmtime()))
        (pkg / "custom-layouts").mkdir(parents=True, exist_ok=True)
        cl.write(pkg / "custom-layouts" / comp, obj)
        files = [{"name": comp, "sha256": cl.sha256(pkg / "custom-layouts" / comp)}]
        (pkg / "custom-layouts.json").write_text(json.dumps(
            {"schema": "fm-customlayouts/1", "game_build": self._game_build(), "files": files}, indent=1), encoding="utf-8")
        journal = self._layout_journal()
        pf = layouttx.preflight(pkg, journal=journal)
        need = list(pf.get("required_confirmations") or [])
        given = list(b.get("confirmations") or [])
        missing = [c for c in need if c not in given]
        if missing:
            return {"refused": "the installation needs explicit confirmation for: " + ", ".join(missing),
                    "required_confirmations": need}
        try:
            tx = layouttx.apply(journal, pkg, confirmations=given, running=self.running)
        except layouttx.LayoutTxRefused as e:
            return {"refused": str(e), "blocked": e.blocked, "required_confirmations": e.confirmations}
        if isinstance(tx, dict) and not cl.has_real_references(obj):
            # Information only, never a refusal: a generated file has instanceID 0 for references.
            # The game resolves tiles by name; ids are a per-session runtime number and cannot survive a restart.
            tx = dict(tx)
            tx["note"] = ("object reference ids are 0 in this generated file; the game resolves tiles "
                          "by name and per-session ids are not required.")
        if b.get("apply_to_breakpoints") and comp.endswith("-Large"):
            base_prefix = comp[:-6]
            all_comps = {c["name"] for c in (self._preview_dump().get("compositions") or ())}
            bp_applied, bp_skipped = [], []
            for bp in ("Standard", "Small"):
                bp_comp = f"{base_prefix}-{bp}"
                if bp_comp not in all_comps:
                    bp_skipped.append({"composition": bp_comp, "reason": "not in bundle dump"})
                    continue
                bp_base = cl.folder() / bp_comp
                bp_obj = cl.read(bp_base) if bp_base.is_file() else copy.deepcopy(self._cached_composition_bundle(bp_comp)["object"])
                if not cl.apply_canvas_edits(bp_obj, edits, runtime=None):
                    bp_skipped.append({"composition": bp_comp, "reason": "none of the edited element ids exist in " + bp_comp})
                    continue
                bp_problems = cl.validate_before_write(bp_obj, bp_comp)
                if bp_problems:
                    bp_skipped.append({"composition": bp_comp, "reason": "; ".join(bp_problems)})
                    continue
                bp_guard = self._refuse_if_uninstalled_project_tile_ops(project, [bp_obj])
                if bp_guard:
                    bp_skipped.append({"composition": bp_comp, "reason": bp_guard})
                    continue
                try:
                    bp_rt = self._runtime_hosts_for(bp_comp, bp_obj, b.get("width") or 2560, b.get("height") or 1440)
                    bp_rt_probs = layoutspace.runtime_problems(bp_rt["hosts"], int(bp_rt["cols"]), int(bp_rt["rows"]))
                except Exception as ex:
                    bp_skipped.append({"composition": bp_comp, "reason": "runtime check failed: %s" % ex})
                    continue
                if bp_rt_probs:
                    bp_skipped.append({"composition": bp_comp, "reason": "; ".join(bp_rt_probs)})
                    continue
                bp_pkg = Path(self.ws.build) / project / ("canvas-" + time.strftime("%Y%m%dT%H%M%SZ", time.gmtime()) + "-" + bp)
                (bp_pkg / "custom-layouts").mkdir(parents=True, exist_ok=True)
                cl.write(bp_pkg / "custom-layouts" / bp_comp, bp_obj)
                bp_files = [{"name": bp_comp, "sha256": cl.sha256(bp_pkg / "custom-layouts" / bp_comp)}]
                (bp_pkg / "custom-layouts.json").write_text(json.dumps(
                    {"schema": "fm-customlayouts/1", "game_build": self._game_build(), "files": bp_files}, indent=1), encoding="utf-8")
                bp_pf = layouttx.preflight(bp_pkg, journal=journal)
                bp_need = list(bp_pf.get("required_confirmations") or [])
                bp_missing = [c for c in bp_need if c not in given]
                if bp_missing:
                    bp_skipped.append({"composition": bp_comp, "reason": "needs confirmation: " + ", ".join(bp_missing)})
                    continue
                try:
                    bp_tx = layouttx.apply(journal, bp_pkg, confirmations=given, running=self.running)
                    bp_applied.append({"composition": bp_comp, "tx_id": bp_tx.get("tx_id")})
                except layouttx.LayoutTxRefused as ex:
                    bp_skipped.append({"composition": bp_comp, "reason": str(ex)})
            if isinstance(tx, dict):
                tx = dict(tx)
                tx["breakpoint_applied"] = bp_applied
                tx["breakpoint_skipped"] = bp_skipped
        return tx

    # ---- Stage 5E: the Playground session (operations) and the tile-move gate, on the 5B model
    def _playground_projection(self, project, session):
        """The session's effective operations projected with THIS PROJECT's route_preference (the project file
        is the setting's home; a missing/legacy project keeps the current default)."""
        from . import playops
        try:
            p = project_mod.load(self.ws, str(project)) if project else {}
        except Exception:
            p = {}
        return playops.project_onto(p, session)

    def _playground_session(self, project):
        """The project's playground session, loaded and re-validated, or a new one. The session lives in the
        project folder (edits/playground.json); a legacy single-file project has no folder to hold it."""
        from . import playops, projfmt
        if not projfmt.is_folder(self.ws, project):
            raise RuntimeError("the playground session lives in the project folder (edits/playground.json); the project %r is a "
                               "legacy single-file project and has no folder - re-save it as a folder project first" % project)
        folder = self.ws.projects / project
        try:
            s = playops.load(folder)
        except FileNotFoundError:
            s = playops.new_session(project, None, game_build=self._game_build())
        return s, folder

    def playground_session(self, q, b):
        """The project's Playground session: its operations, the effective projection onto the project fragments,
        and the counts (applied / superseded / reverted / stale). Read only; creates nothing on disk."""
        from . import playops
        s, _folder = self._playground_session(b["project"])
        states = {}
        for op in s["operations"]:
            states[op.get("state") or "applied"] = states.get(op.get("state") or "applied", 0) + 1
        return {"session": s, "projection": self._playground_projection(b.get("project"), s), "counts": dict(states, total=len(s["operations"]))}

    def playground_add_operation(self, q, b):
        """Record one operation (as `uidoc.classify` produced it) in the project's session: validated again on
        entry, supersession recorded, the session saved atomically. The effective projection comes back for the
        render overlay and the build."""
        from . import playops
        s, folder = self._playground_session(b["project"])
        op = b["operation"]
        if not isinstance(op, dict) or op.get("schema") != playops.OP_SCHEMA:
            raise ValueError("the operation must be an fm-playop/1 record as uidoc.classify produced it")
        playops.add(s, op)
        playops.save(folder, s)
        superseded = [o["id"] for o in s["operations"] if o.get("superseded_by") == op["id"]]
        return {"operation": op, "superseded": superseded,
                "projection": self._playground_projection(b.get("project"), s),
                "counts": {"total": len(s["operations"]), "applied": len(playops.effective(s))}}

    def playground_undo(self, q, b):
        from . import playops
        s, folder = self._playground_session(b["project"])
        op = playops.undo(s, b.get("op_id"))
        playops.save(folder, s)
        return {"undone": op["id"], "projection": self._playground_projection(b.get("project"), s)}

    def playground_redo(self, q, b):
        from . import playops
        s, folder = self._playground_session(b["project"])
        if not b.get("op_id"):
            raise ValueError("redo names the operation id")
        op = playops.redo(s, b["op_id"])
        playops.save(folder, s)
        return {"redone": op["id"], "projection": self._playground_projection(b.get("project"), s)}

    def playground_revert(self, q, b):
        from . import playops
        s, folder = self._playground_session(b["project"])
        playops.revert_all(s)
        playops.save(folder, s)
        return {"reverted": "all", "projection": self._playground_projection(b.get("project"), s)}

    def playground_build_operation(self, q, b):
        """The BACKEND builds the operation record for a screen-canvas gesture (the browser never assembles an
        fm-playop record): the kind's gate runs here first, then the record is built from the composition's own
        data and validated by the 5B model. Returns {gate, operation, validation} - the caller records the
        operation through playground.add_operation, which validates it AGAIN."""
        d = layout_dump.load(self.ws)
        if d is None:
            raise RuntimeError("no layout dump is imported")
        from . import playops
        kind = b.get("kind")
        if kind == "SetCellMaxSize":                 # SC1: a candidate; its refusals come from playops.cell_max_size_operation
            try:
                mx = b.get("max_size") or {}
                op = playops.cell_max_size_operation(d, b.get("composition"), b.get("element_id"), mx.get("x"), mx.get("y"))
            except playops.OperationError as e:
                return {"gate": None, "operation": None, "validation": None, "refused": str(e)}
            return {"gate": {"valid": True, "blocks": [], "collisions": []}, "operation": op, "validation": op["validation"]}
        if kind == "SwapTile":                        # ST1: a cell's tile by description name, from the composition's own tile set
            comp, eid, tile = b.get("composition"), b.get("element_id"), b.get("tile") or {}
            cell = next((c for c in d.get("cells") or [] if c.get("composition") == comp and c.get("element_id") == eid), None)
            rec = next((c for c in d.get("compositions") or [] if c.get("name") == comp), None)
            if cell is None or rec is None:
                return {"gate": None, "operation": None, "validation": None, "refused": "unknown composition or cell"}
            size = tile.get("size") or {}
            available = {t["id"]: t for t in self.playground_tile_set({}, {"composition": comp})["tiles"]}
            if tile.get("name") not in available or [size.get("x"), size.get("y")] not in available[tile.get("name")]["sizes"]:
                return {"gate": None, "operation": None, "validation": None,
                        "refused": "%s with a %sx%s configuration is not in %s's own tile set" % (tile.get("name"), size.get("x"), size.get("y"), comp)}
            target = {"screen": comp, "logical_id": "%s|host:%s@%d" % (comp, eid, cell["cell_index"]), "structural_key": "%s|host:%s@%d" % (comp, eid, cell["cell_index"]),
                      "locator": {"bundle": rec.get("bundle"), "bundle_sha256": None, "cab": None, "path_id": str(rec.get("path_id")), "m_id": None},
                      "guard": {"type": "Host", "name": eid, "classes": []}, "render_pos": None,
                      "cell": {"composition": comp, "cell_index": cell["cell_index"], "cell_element_id": eid}}
            try:
                op = playops.new_operation("SwapTile", target, {"tile": {"name": tile["name"], "size": {"x": size["x"], "y": size["y"]}}})
                op["label"] = "Swap the tile of %s in %s to %s (%dx%d)" % (eid, comp, tile["name"], size["x"], size["y"])
                op["validation"] = playops.validate(op)
            except playops.OperationError as e:
                return {"gate": None, "operation": None, "validation": None, "refused": str(e)}
            return {"gate": {"valid": True, "blocks": [], "collisions": []}, "operation": op, "validation": op["validation"]}
        if kind not in ("MoveNode", "ResizeNode", "AddCell"):
            raise ValueError("build_operation builds the screen-canvas kinds (MoveNode, ResizeNode, AddCell); classify a style or token edit through uidoc.classify")
        comp, idx = b.get("composition"), b.get("cell_index")
        geo = b.get("geometry") or {}
        if idx is None or not geo:
            raise ValueError("%s needs cell_index and geometry" % kind)
        if kind == "AddCell":
            gate = self.playground_validate_add({}, {"composition": comp, "element_id": b.get("element_id"),
                                                     "cell_index": idx, "geometry": geo, "description": b.get("description") or {}})
            eid_new = b.get("element_id")
        else:
            gate = self.playground_validate_move({}, {"composition": comp, "cell_index": idx, "geometry": geo,
                                                      "project": b.get("project"), "resize": kind == "ResizeNode"})
            cell = next((c for c in d["cells"] if c["composition"] == comp and c["cell_index"] == idx), None)
            eid_new = cell["element_id"] if cell else None
        if not gate.get("valid"):
            return {"gate": gate, "operation": None, "validation": None,
                    "refused": gate["blocks"][0] if gate["blocks"] else
                    ("a collision needs a deliberate confirm" if gate["collisions"] else "the gate refused the gesture")}
        cell_rec = {"composition": comp, "cell_index": idx, "cell_element_id": eid_new, "geometry": {k: geo[k] for k in ("x", "y", "w", "h")}}
        crec = next((c for c in d["compositions"] if c["name"] == comp), None)
        locator = {"bundle": (crec or {}).get("bundle"), "bundle_sha256": None, "cab": None,
                   "path_id": str((crec or {}).get("path_id")) if crec else None, "m_id": None}
        if kind == "ResizeNode":
            from . import build5g
            cs = build5g._config_size(d, comp, idx)
            if cs:
                cell_rec["config_size"] = cs
            mx = b.get("max_size") or {"x": geo["w"], "y": geo["h"]}
            cell_rec["max_size"] = {"x": int(mx["x"]), "y": int(mx["y"])}
        if kind == "AddCell":
            desc = b.get("description") or {}
            cell_rec["description"] = {"path_id": (gate.get("configuration") or {}).get("path_id") or desc.get("path_id"),
                                       "config_index": int((gate.get("configuration") or {}).get("config_index", desc.get("config_index", 0)))}
        target = {"screen": comp, "logical_id": "%s|host:%s@%d" % (comp, eid_new, idx),
                  "structural_key": "%s|host:%s@%d" % (comp, eid_new, idx),
                  "locator": locator,
                  "guard": {"type": "Host", "name": eid_new, "classes": []}, "render_pos": None, "cell": cell_rec}
        original = None
        if kind in ("MoveNode", "ResizeNode"):
            base = next((c for c in d["cells"] if c["composition"] == comp and c["cell_index"] == idx), None)
            if base is not None:
                original = {"value": {"x": base["x"], "y": base["y"], "w": base["w"], "h": base["h"]},
                            "evidence": "directly serialized",
                            "provenance": {"bundle": "ui-tileslayouts_assets_all.bundle", "field": "m_gridComponents"}}
        note = ""
        op = playops.new_operation(kind, target, {}, original=original, note=note)
        verb = {"ResizeNode": "Resize", "AddCell": "Add", "MoveNode": "Move"}.get(kind, kind)
        if kind == "ResizeNode":
            op["label"] = "%s %s %dx%d -> %dx%d in %s" % (verb, eid_new, (original or {}).get("value", {}).get("w", geo["w"]),
                                                          (original or {}).get("value", {}).get("h", geo["h"]),
                                                          geo["w"], geo["h"], comp)
        elif kind == "AddCell":
            op["label"] = "%s %s %dx%d to %s" % (verb, eid_new, geo["w"], geo["h"], comp)
        else:
            op["label"] = "%s %s to (%d, %d) in %s" % (verb, eid_new, geo["x"], geo["y"], comp)
        # where the edited composition is active (from the MEASURED composition-switch points; a label, not a claim
        # about this exact setting). The Playground compares it with its current preview selection.
        try:
            from .render import preview as preview_mod
            suffix = str(comp).rsplit("-", 1)[-1]
            widths = sorted({p["width"] for p in preview_mod.MEASURED_POINTS if p["composition"] == suffix})
            op["activity"] = {"composition": comp, "measured_widths": widths,
                              "source": "render.preview measured composition-switch points",
                              "note": ("%s is active at the measured composition-switch points with widths %s px; "
                                       "the game picks one composition by window width, so this edit applies only "
                                       "where %s is the active one"
                                       % (comp, ", ".join(str(w) for w in widths), comp) if widths else
                                       "%s is not one of the measured compositions; the window widths where it is "
                                       "active are not known" % comp)}
        except Exception:
            op["activity"] = {"composition": comp, "measured_widths": []}
        op["validation"] = playops.validate(op)
        return {"gate": gate, "operation": op, "validation": op["validation"]}

    def _session_stand_ins(self, project):
        """The Playground session's own effective moves and resizes, as stand-ins for their cells in the overlap gate (the same shape as tiles.ops_for): a swap of two tiles' places
        can only be recorded when the first move already stands in for its cell while the second is checked (found by the E2E1 chain)."""
        from . import playops
        try:
            s, _folder = self._playground_session(project)
        except Exception:
            return []
        out = []
        for op in playops.effective(s):
            c = (op.get("target") or {}).get("cell") or {}
            if op.get("kind") in ("MoveNode", "ResizeNode") and c.get("geometry"):
                out.append({"composition": c.get("composition"), "cell_index": c.get("cell_index"), "geometry": dict(c["geometry"]), "state": op.get("state")})
        return out

    def playground_validate_move(self, q, b):
        """The overlap and bounds gate for a tile move, run AS THE TILE MOVES: the D2 placement validation against
        the imported dump (blocks, warnings, collisions with the region named), plus the project's other stored
        placements standing in for their cells. Read only: nothing is stored here."""
        d = layout_dump.load(self.ws)
        if d is None:
            raise RuntimeError("no layout dump is imported")
        st = layout_dump.staleness(d["meta"], self.ws)
        if st["status"] != "fresh":
            raise RuntimeError("the imported layout dump is %s against the game's files; placement edits can only be "
                               "validated against a fresh dump (re-export or re-import the dump of this build)" % st["status"])
        from . import placement
        grid = placement.Grid(d)
        cell = grid.cells.get((b.get("composition"), b.get("cell_index")))
        if not cell:
            return {"blocks": ["composition %r cell %r is not in the dump" % (b.get("composition"), b.get("cell_index"))],
                    "warnings": [], "collisions": [], "cell_element_id": None, "valid": False}
        if b.get("resize"):
            # a RESIZE (promoted from candidate by Test C): the same D2 overlap check, without the move-only size
            # block. ENLARGEMENT is buildable while the configuration stays unchanged; a shrink below the tile's
            # configured size is refused (the writer does not rewrite the configuration list).
            geo = b.get("geometry") or {}
            blocks, warnings, collisions = [], [], []
            config_size = None
            try:
                from . import build5g
                config_size = build5g._config_size(d, b.get("composition"), b.get("cell_index"))
            except Exception:
                config_size = None
            if not isinstance(geo, dict) or set(geo) != {"x", "y", "w", "h"} or not all(isinstance(geo[k], int) and not isinstance(geo[k], bool) for k in ("x", "y", "w", "h")):
                blocks.append("geometry needs integer x, y, w, h grid units")
            else:
                if config_size and (geo["w"] < config_size["x"] or geo["h"] < config_size["y"]):
                    blocks.append("shrinking below the tile's configured size is refused: the configuration is %dx%d "
                                  "and the resize asks for %dx%d (the writer does not rewrite the configuration list)"
                                  % (config_size["x"], config_size["y"], geo["w"], geo["h"]))
                if geo["w"] < cell["min_w"] or (cell["max_w"] > 0 and geo["w"] > cell["max_w"]):
                    warnings.append("the dump's limits are w %d..%s; the writer edits m_maxSize with this resize, so the limits change with it" % (cell["min_w"], cell["max_w"] or "unlimited"))
                if geo["h"] < cell["min_h"] or (cell["max_h"] > 0 and geo["h"] > cell["max_h"]):
                    warnings.append("the dump's limits are h %d..%s; the writer edits m_maxSize with this resize, so the limits change with it" % (cell["min_h"], cell["max_h"] or "unlimited"))
                if "locked" in cell["flags"]:
                    blocks.append("locked: this cell has the 'locked' flag, a resize is refused")
                others = []
                if b.get("project"):
                    from . import tiles as tiles_mod
                    try:
                        others = tiles_mod.ops_for(self.ws, b["project"])
                    except Exception:
                        others = []
                    others = others + self._session_stand_ins(b["project"])
                stand_in = {(o["composition"], o["cell_index"]): o["geometry"] for o in others if o.get("geometry") and o.get("state") != "stale"}
                for sib in grid.siblings(b["composition"]):
                    if sib["cell_index"] == b.get("cell_index"):
                        continue
                    g = stand_in.get((b["composition"], sib["cell_index"])) or {k: sib[k] for k in ("x", "y", "w", "h")}
                    if geo["x"] < g["x"] + g["w"] and g["x"] < geo["x"] + geo["w"] and geo["y"] < g["y"] + g["h"] and g["y"] < geo["y"] + geo["h"]:
                        collisions.append({"cell_index": sib["cell_index"], "element_id": sib["element_id"], "geometry": g})
            return {"blocks": blocks, "warnings": warnings, "collisions": collisions,
                    "cell_element_id": cell["element_id"], "config_size": config_size,
                    "valid": not blocks and not collisions}
        edit = {"composition": b.get("composition"), "cell_index": b.get("cell_index"), "geometry": b.get("geometry")}
        others = []
        if b.get("project"):
            from . import tiles as tiles_mod
            try:
                others = tiles_mod.ops_for(self.ws, b["project"])
            except Exception:
                others = []
            others = others + self._session_stand_ins(b["project"])
        res = placement.check(grid, edit, others)
        res["cell_element_id"] = cell["element_id"]
        res["valid"] = not res["blocks"] and not res["collisions"]
        return res

    def playground_validate_add(self, q, b):
        """The gate for ADDING a cell (the addendum's candidate kind): the new element id must be unique within the
        composition, the new rectangle must overlap no cell, and the named tile description and configuration
        index must exist. Read only: the dump for the cells, the built document for the descriptions."""
        d = layout_dump.load(self.ws)
        if d is None:
            raise RuntimeError("no layout dump is imported")
        st = layout_dump.staleness(d["meta"], self.ws)
        if st["status"] != "fresh":
            raise RuntimeError("the imported layout dump is %s against the game's files; cells can only be added "
                               "against a fresh dump (re-export or re-import the dump of this build)" % st["status"])
        blocks, comp, geo, eid_new = [], b.get("composition"), b.get("geometry"), b.get("element_id")
        if not isinstance(eid_new, str) or not eid_new:
            raise ValueError("add needs the new cell's element_id")
        if not isinstance(geo, dict) or set(geo) != {"x", "y", "w", "h"} or not all(isinstance(geo[k], int) and not isinstance(geo[k], bool) for k in ("x", "y", "w", "h")):
            raise ValueError("geometry needs integer x, y, w, h grid units")
        existing = [c for c in d["cells"] if c["composition"] == comp]
        if not existing:
            blocks.append("composition %r is not in the dump" % comp)
        if any(c["element_id"] == eid_new for c in existing):
            blocks.append("element id %r is not unique within %r (a cell already carries it)" % (eid_new, comp))
        if any(c["cell_index"] == b.get("cell_index") for c in existing):
            blocks.append("cell index %r already exists in %r" % (b.get("cell_index"), comp))
        if int(b.get("cell_index", -1)) != len(existing) and existing:
            blocks.append("a new cell goes at index %d (the current end of %r's grid), not %r"
                          % (len(existing), comp, b.get("cell_index")))
        new_rect = {"x": geo["x"], "y": geo["y"], "w": geo["w"], "h": geo["h"]}
        collisions = []
        for c in existing:
            if new_rect["x"] < c["x"] + c["w"] and c["x"] < new_rect["x"] + new_rect["w"] and new_rect["y"] < c["y"] + c["h"] and c["y"] < new_rect["y"] + new_rect["h"]:
                collisions.append({"cell_index": c["cell_index"], "element_id": c["element_id"],
                                   "geometry": {"x": c["x"], "y": c["y"], "w": c["w"], "h": c["h"]}})
        descriptions = self._uidoc_descriptions(comp)
        desc_ref, cfg = b.get("description") or {}, None
        for rec_ in descriptions or []:
            for d_ in rec_["descriptions"]:
                if (desc_ref.get("path_id") and str(d_.get("path_id")) == str(desc_ref["path_id"])) or \
                        (desc_ref.get("id") and d_.get("id") == desc_ref.get("id")):
                    cfgs = d_.get("configurations") or []
                    if isinstance(desc_ref.get("config_index"), int) and 0 <= desc_ref["config_index"] < len(cfgs):
                        cfg = {"description_id": d_.get("id"), "path_id": d_.get("path_id"),
                               "config_index": desc_ref["config_index"], "size": cfgs[desc_ref["config_index"]].get("size")}
                    else:
                        blocks.append("configuration index %r does not exist on description %s (%d configurations)" % (
                            desc_ref.get("config_index"), d_.get("id") or d_.get("path_id"), len(cfgs)))
                    break
        if cfg is None and not any("configuration index" in blk for blk in blocks):
            blocks.append("the named description (%s) is not one of %r's cell descriptions" % (
                desc_ref.get("id") or desc_ref.get("path_id"), comp))
        if cfg is not None:
            size = cfg.get("size") or {}
            if (geo["w"], geo["h"]) != (size.get("x"), size.get("y")):
                blocks.append("an added cell must use its configuration's own size %sx%s (asked %dx%d)"
                              % (size.get("x"), size.get("y"), geo["w"], geo["h"]))
        return {"blocks": blocks, "warnings": [], "collisions": collisions,
                "valid": not blocks and not collisions, "configuration": cfg, "kind": "AddCell"}

    def _uidoc_descriptions(self, composition):
        """The built document's per-cell configuration descriptions for one composition (the addendum read 1),
        plus the composition's m_gridElementSet descriptions that NO cell places yet (read only for the AddCell
        gate; the inventory keeps its per-cell read, so its counts do not change)."""
        try:
            doc = self._uidoc_document(layout_dump.load(self.ws), composition)
        except Exception:
            return None
        rows = doc.composition.get("cell_configurations")
        if rows is None:
            return None
        try:
            from .uidoc import Source
            from .uidoc.composition import read_set_descriptions
            fields = doc.composition.get("serialized") or {}
            bundle = doc.composition.get("bundle")
            extras, _err = read_set_descriptions(Source(self._renderer().layouts), bundle, fields)
        except Exception:
            extras = None
        if extras:
            seen = {d.get("path_id") for rec in rows for d in rec.get("descriptions") or []}
            add = [d for d in extras if d.get("path_id") not in seen]
            if add:
                rows = list(rows) + [{"cell_index": None, "element_id": None, "descriptions": add}]
        return rows

    def _composition_screen_meta(self, d):
        """B4: map composition name -> {panel, composition_set, breakpoint, variant} from dump tiles/panels/layouts."""
        panel_by_lid = {p["layout_id"]: p["panel_id"] for p in (d.get("panels") or ())}
        layout_by_lid = {l["id"]: l["name"] for l in (d.get("layouts") or ())}
        bp_names = {0: "Small", 1: "Standard", 2: "Standard", 3: "Large"}
        meta = {}
        for t in (d.get("tiles") or ()):
            cn = t.get("composition")
            if not cn or cn in meta:
                continue
            lid = t.get("panel_layout_id")
            panel = panel_by_lid.get(lid) or layout_by_lid.get(lid) or ""
            sname = t.get("set_name") or ""
            bp = bp_names.get(t.get("breakpoint"), "")
            v_idx = t.get("variant_idx")
            variant = "FMC" if ("-FMC" in cn or v_idx == 1) else ("NONE" if "-NONE" in cn else ("NoLeague" if "-NoLeague" in cn else "FM"))
            meta[cn] = {"panel": panel, "composition_set": sname, "breakpoint": bp, "variant": variant}
        return meta

    def playground_screen_index(self, q, b):
        """B4: every screen with its panel, composition set, and compositions per breakpoint and skin variant."""
        d = layout_dump.load(self.ws)
        if d is None:
            raise RuntimeError("no layout dump is imported")
        cells_comps = {c["composition"] for c in (d.get("cells") or ())}
        meta = self._composition_screen_meta(d)
        grouped = {}
        editable_count = 0
        template_count = 0
        for comp in (d.get("compositions") or ()):
            cn = comp["name"]
            m = meta.get(cn) or {}
            editable = cn in cells_comps
            if editable:
                editable_count += 1
            else:
                template_count += 1
            panel = m.get("panel") or ""
            cset = m.get("composition_set") or cn
            bp = m.get("breakpoint") or ("Large" if "-Large" in cn else ("Standard" if "-Standard" in cn else ("Small" if "-Small" in cn else "Other")))
            variant = m.get("variant") or ("FMC" if "-FMC" in cn else ("NONE" if "-NONE" in cn else ("NoLeague" if "-NoLeague" in cn else "FM")))
            key = (panel, cset)
            entry = grouped.setdefault(key, {"panel": panel, "composition_set": cset, "compositions": []})
            entry["compositions"].append({
                "name": cn,
                "breakpoint": bp,
                "variant": variant,
                "editable_by_file": editable,
                "editability_label": "editable by file" if editable else "template, not editable by file",
            })
        screens = sorted(grouped.values(), key=lambda s: (s["panel"] or s["composition_set"], s["composition_set"]))
        return {
            "screens": screens,
            "counts": {
                "screens": len(screens),
                "compositions": editable_count + template_count,
                "editable": editable_count,
                "template": template_count,
            },
        }

    def playground_screens(self, q, b):
        """The compositions that hold tiles (the screens the canvas can draw and drag on), with their cells
        and per-profile confidence labels: read from the imported dump and parity/measurement tables only."""
        from . import layoutspace
        from .render import preview as preview_mod
        d = layout_dump.load(self.ws)
        if d is None:
            raise RuntimeError("no layout dump is imported")
        profile = layoutspace.normalize_profile((b or {}).get("profile"))
        meta = self._composition_screen_meta(d)
        cells = {}
        for c in d["cells"]:
            cells.setdefault(c["composition"], []).append(
                {"cell_index": c["cell_index"], "element_id": c["element_id"], "x": c["x"], "y": c["y"], "w": c["w"], "h": c["h"],
                 "flags": c["flags"]})
        rows = []
        confidences = {}
        for comp in d["compositions"]:
            cn = comp["name"]
            cs = cells.get(cn)
            m = meta.get(cn) or {}
            if cs:
                conf = preview_mod.confidence_for(cn, "rea", profile=profile)
                confidences[cn] = conf["label"]
                rows.append({"name": cn, "preset": [comp["preset_w"], comp["preset_h"]],
                             "panel": m.get("panel") or "",
                             "composition_set": m.get("composition_set") or "",
                             "breakpoint": m.get("breakpoint") or "",
                             "variant": m.get("variant") or "FM",
                             "editable_by_file": True,
                             "editability_label": "editable by file",
                             "confidence": conf["label"],
                             "cells": sorted(cs, key=lambda c: c["cell_index"])})
        rows.sort(key=lambda r: (r.get("panel") or r["name"], r["name"]))
        return {"total": len(rows), "profile": profile,
                "profiles": [dict(v) for v in layoutspace.VIEWPORT_PROFILES.values()],
                "confidences": confidences, "screens": rows}

    def _favourites_path(self):
        return self.ws.root / "favourites.json"

    def playground_favourites(self, q, b):
        """Read the pinned Game Layouts favourites stored in the workspace (favourites.json)."""
        import json
        p = self._favourites_path()
        if not p.is_file():
            return {"favourites": []}
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {"favourites": []}
        raw = data.get("favourites") if isinstance(data, dict) else None
        if not isinstance(raw, list):
            return {"favourites": []}
        seen, out = set(), []
        for item in raw:
            if isinstance(item, str) and item and item not in seen:
                seen.add(item)
                out.append(item)
        return {"favourites": out}

    def playground_set_favourites(self, q, b):
        """Atomically persist the pinned Game Layouts favourites in the workspace (favourites.json)."""
        import json
        import os
        import tempfile
        raw = (b or {}).get("favourites")
        if not isinstance(raw, list):
            raise ValueError("favourites must be a list of composition names")
        seen, out = set(), []
        for item in raw:
            if isinstance(item, str) and item and item not in seen:
                seen.add(item)
                out.append(item)
        p = self._favourites_path()
        p.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps({"favourites": out}, indent=2) + "\n"
        fd, tmp = tempfile.mkstemp(prefix=".favs-", suffix=".tmp", dir=str(p.parent))
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                fh.write(payload)
            os.replace(tmp, p)
        except Exception:
            try:
                os.unlink(tmp)
            except OSError:
                pass
            raise
        return {"favourites": out}

    def layouts_list(self, q, b):
        rows = self._layouts().list()
        s = str(b.get("q", "")).lower()
        if b.get("bundle"):
            rows = [r for r in rows if r["bundle"] == b["bundle"]]
        if s:
            rows = [r for r in rows if s in r["name"].lower()]
        lim = int(b.get("limit") or 300)
        return {"total": len(rows), "layouts": [{k: r[k] for k in ("bundle", "name", "path_id", "elements")} for r in rows[:lim]]}

    def layouts_tree(self, q, b):
        out = self._layouts().tree(b["bundle"], b["path_id"])
        if b.get("project"):
            out["patches"] = next((d for d in project_mod.load(self.ws, b["project"]).get("layout_patches", [])
                                   if d["layout"]["bundle"] == b["bundle"] and d["layout"]["name"] == out["name"]), None)
        return out

    def layouts_class_usage(self, q, b):
        return self._layouts().class_usage(b["class"], self.index)

    def layouts_edit(self, q, b):
        """Fold one op (set-classes, set-inline, set-attr) into the project's patch file of that layout, after checking it against the
        layout as the game has it (element id and guard, attribute exists, bundle copied into the snapshot)."""
        from . import uxml
        op = dict(b["op"])
        lay = {"bundle": b["bundle"], "name": b["name"], "path_id": str(b["path_id"])}
        p = project_mod.load(self.ws, b["project"])
        doc = next((d for d in p.get("layout_patches", []) if d["layout"]["bundle"] == lay["bundle"] and d["layout"]["name"] == lay["name"]), None)
        if doc is None:
            doc = {"schema": 1, "layout": lay, "ops": []}
            p.setdefault("layout_patches", []).append(doc)
        uxml.merge_op(doc, op)
        if not doc["ops"]:
            p["layout_patches"].remove(doc)
        else:
            _, t, sheet = self._layouts().load(lay["bundle"], lay["path_id"])      # the op must fit the game's layout
            probe_t = json.loads(json.dumps(t))
            uxml.apply_to_layout(probe_t, json.loads(json.dumps(sheet)) if sheet else None, [o for o in doc["ops"]], lay["name"] + ":")
            install.add_image_bundle(self.ws, self.need_info()["aa_dir"], lay["bundle"])
        project_mod.save(self.ws, project_mod.validate(project_mod.migrate(p)))
        return {"project": project_mod.load(self.ws, b["project"])}

    def layouts_unedit(self, q, b):
        p = project_mod.load(self.ws, b["project"])
        for d in p.get("layout_patches", []):
            if d["layout"]["bundle"] == b["bundle"] and d["layout"]["name"] == b["name"]:
                d["ops"] = [o for o in d["ops"] if not (o["id"] == b["id"] and (not b.get("op") or o["op"] == b["op"]))]
        p["layout_patches"] = [d for d in p.get("layout_patches", []) if d["ops"]]
        project_mod.save(self.ws, project_mod.validate(project_mod.migrate(p)))
        return {"project": project_mod.load(self.ws, b["project"])}

    def font_tokens(self, q, b):
        """Tokens a font can be assigned to: the game's own font-family tokens."""
        ix = self.need_index()
        rows = [r for r in ix.tokens("typography-family", False, 100)["rows"]] if hasattr(ix, "tokens") else []
        return {"tokens": [{"name": r["name"], "value": r.get("value")} for r in rows]}

    def font_set(self, q, b):
        """Assign a .ttf/.otf file to a font token: the file is copied into the project's fonts/ folder and mapped; native export writes
        the url() rule and the file."""
        import shutil as _sh
        f = Path(b["path"])
        if not f.is_file() or f.stat().st_size > 30 * 1024 * 1024:
            raise ValueError("pick a .ttf or .otf file (at most 30 MB)")
        head = f.open("rb").read(4)
        if head not in (b"\x00\x01\x00\x00", b"OTTO", b"true"):
            raise ValueError("%s is not a TrueType or OpenType font file" % f.name)
        fn = re.sub(r"[^\w.-]", "_", f.name)
        if not project_mod.FONT_FILE.fullmatch(fn):
            raise ValueError("the font file name must be letters, digits, dot, dash, underscore and end in .ttf or .otf")
        p = project_mod.load(self.ws, b["project"])
        from . import projfmt
        d = projfmt.folder(self.ws, b["project"]) / "fonts"
        d.mkdir(exist_ok=True)
        _sh.copyfile(f, d / fn)
        p["font_swaps"] = [x for x in p.get("font_swaps", []) if x["token"] != b["token"]] + [{"token": b["token"], "source": fn}]
        project_mod.save(self.ws, project_mod.validate(project_mod.migrate(p)))
        return {"project": project_mod.load(self.ws, b["project"])}

    def font_remove(self, q, b):
        from . import projfmt
        p = project_mod.load(self.ws, b["project"])
        gone = [x for x in p.get("font_swaps", []) if x["token"] == b["token"]]
        if not gone:
            raise ValueError("no font is assigned to %s" % b["token"])
        p["font_swaps"] = [x for x in p["font_swaps"] if x["token"] != b["token"]]
        project_mod.save(self.ws, p)
        for x in gone:
            f = projfmt.folder(self.ws, b["project"]) / "fonts" / x["source"]
            if f.is_file() and not any(y["source"] == x["source"] for y in p["font_swaps"]) and x["source"] not in [s.split("/")[-1] for s in p.get("native_support", [])]:
                f.unlink()
        return {"project": project_mod.load(self.ws, b["project"])}

    # ---- live preview loop (disabled in release builds; no inspector plugin shipped)
    def inspector_status(self, q, b):
        return {"online": False, "reason": "Live preview is disabled in release builds"}

    def findings_get(self, q, b):
        """The Session 2 findings (data/findings/session2.json) with which of their screenshots exist in this workspace's game-screens folder: the pictures are named gallery-<theme>-<screen>.png."""
        from . import gamescreens
        d = json.loads((config.resource_root() / "data" / "findings" / "session2.json").read_text(encoding="utf-8"))
        have = {s["name"] for s in gamescreens.list_screens(self.ws)}
        d["shots"] = {"%s/%s" % (th["id"], sc["id"]): "gallery-%s-%s.png" % (th["id"], sc["id"]) for th in d["themes"] for sc in d["screens"] if "gallery-%s-%s.png" % (th["id"], sc["id"]) in have}
        return d

    # ---- game screenshots for the tile organiser's backdrop (skin_editor/gamescreens.py; Advanced mode only, kept in the workspace)
    def screens_list(self, q, b):
        from . import gamescreens
        return {"folder": str(gamescreens.folder(self.ws)), "screens": gamescreens.list_screens(self.ws)}

    def screens_image(self, q, b):
        from . import gamescreens
        return gamescreens.read(self.ws, b["name"]), "image/png"

    def screens_add(self, q, b):
        from . import gamescreens
        return gamescreens.add(self.ws, b["path"], b.get("name"), bool(b.get("replace")))

    def screens_remove(self, q, b):
        from . import gamescreens
        return gamescreens.remove(self.ws, b["name"])

    def preview_live(self, q, b):
        p = project_mod.load(self.ws, b["project"])
        return {"mode": "static", "skin_id": p["name"] + "-preview", "exported": "",
                "steps": [], "reloaded": False, "reason": "Live preview is disabled in release builds"}

    def preview_live_image(self, q, b):
        f = Path(b["path"]).resolve()
        if f.suffix.lower() != ".png" or f.parent.name != "screens" or "-preview-" not in f.name or not f.is_file():
            raise ValueError("only a live-preview screenshot can be read")
        return f.read_bytes(), "image/png"

    # ---- version profiles and the update diff (spec 2.9)
    def update_status(self, q, b):
        from . import profile
        aa = (self.info or {}).get("aa_dir")
        return {"status": profile.status(self.ws, aa), "profiles": profile.list_profiles(self.ws)}

    def update_profiles(self, q, b):
        from . import profile
        return profile.list_profiles(self.ws)

    def update_scan(self, q, b):
        """Scan the vanilla snapshot as the profile of its game build (needs the snapshot; the live folder only supplies the icon classes)."""
        from . import profile
        aa = (self.info or {}).get("aa_dir")
        cls = None
        if aa:
            try:
                cls = [f"{k[0]}:{k[1]}" for k in images.icon_classes(aa)]
            except Exception:
                cls = None
        return {"profile": profile.scan_snapshot(self.ws, b.get("build") or None, icon_classes=cls)}

    def update_import_profile(self, q, b):
        """Scan a folder of stock bundles of another build (read-only) into a profile, so it can be diffed against the current one."""
        from . import profile
        return {"profile": profile.scan(self.ws, b["path"], game_build=b.get("build") or None, catalog_hash=b.get("catalog_hash") or None,
                                        source=b["path"], note=b.get("note") or None)}

    def update_diff(self, q, b):
        from . import profile
        old, new = profile.load(self.ws, b["old"]), profile.load(self.ws, b["new"])
        oi, ni = profile.load_index(self.ws, b["old"]), profile.load_index(self.ws, b["new"])
        out = {"diff": profile.diff(old, new, oi, ni)}
        if b.get("project"):
            p = project_mod.load(self.ws, b["project"])
            cat = None
            active = profile.active_profile(self.ws)
            aa = (self.info or {}).get("aa_dir")
            if aa and active and active["id"] == new["id"] and p.get("image_swaps"):
                cat = images.catalog(self.ws, aa)
            out["items"] = profile.project_states(p, oi, ni, cat)
        return out

    def update_autofix(self, q, b):
        from . import profile
        p = project_mod.load(self.ws, b["project"])
        oi, ni = profile.load_index(self.ws, b["old"]), profile.load_index(self.ws, b["new"])
        cat = None
        aa = (self.info or {}).get("aa_dir")
        if aa and p.get("image_swaps"):
            cat = images.catalog(self.ws, aa)
        fixed, done = profile.autofix(p, profile.project_states(p, oi, ni, cat))
        if done:
            project_mod.save(self.ws, project_mod.validate(project_mod.migrate(fixed)))
        return {"applied": done, "items": profile.project_states(project_mod.load(self.ws, b["project"]), oi, ni, cat)}

    def pf_new_sheet(self, q, b):
        from . import projfmt
        rel = projfmt.create_sheet(self.ws, b["project"], b["sheet"])
        return {"path": rel, "files": projfmt.tree(self.ws, b["project"])}

    def pf_remove(self, q, b):
        """Take a project out of the list. It is moved to <workspace>/trash, not erased."""
        if b["project"] not in project_mod.names(self.ws):
            raise FileNotFoundError("no project named %s" % b["project"])
        return {"trash": project_mod.delete(self.ws, b["project"])}

    def pf_search(self, q, b):
        from . import projfmt
        return projfmt.search(self.ws, q["project"], q["q"], q.get("regex") == "1", q.get("case") == "1")

    def pf_create(self, q, b):
        """A new, empty folder project. target: native (default for the shell) or bundles."""
        from . import projfmt
        name = b["name"]
        if name in project_mod.names(self.ws):
            raise RuntimeError("a project with that name exists")
        if b.get("preset"):
            # a preset as a FOLDER project with the chosen output from the start (never the single-file form `project.create` writes); the preset's own settings are kept
            if b["preset"] not in PRESETS:
                raise KeyError("no such preset: %s" % b["preset"])
            p = PRESETS[b["preset"]](self.need_index(), name)
        else:
            p = project_mod.new(name, (self.ws.vanilla_manifest() or {}).get("game_build"))
        p["options"]["output"] = b.get("target", "native")
        if b.get("keep_club_colours") is False:          # the native option: the dark-bar rules, wallpaper and card frames hidden (docs/SIMPLE-MODE-PLAN.md S1); absent or true keeps the club's colours
            p["options"]["club_colours"] = False
        projfmt.write(self.ws, p)
        changes.record(name, "options", ["project created"])
        return {"project": project_mod.load(self.ws, name), "files": [t["path"] for t in projfmt.tree(self.ws, name)]}

    def explain(self, q, b):
        """An engine message in plain words (skin_editor/plain.py): {plain, details}."""
        from . import plain
        return plain.plain(b["message"])

    def pf_migrate(self, q, b):
        from . import projfmt
        return projfmt.migrate_legacy(self.ws, b["project"])

    def preset(self, q, b):
        if b.get("name") in project_mod.names(self.ws):
            raise RuntimeError("a project with that name exists")
        if b.get("preset"):
            p = PRESETS[b["preset"]](self.need_index(), b["name"])
        else:
            p = project_mod.new(b["name"], (self.ws.vanilla_manifest() or {}).get("game_build"))
        return {"project": project_mod.save(self.ws, p)}

    def build(self, q, b):
        p = project_mod.load(self.ws, b["name"])
        ix = self.need_index()
        game_dir = self.info["game_dir"] if self.info else None
        allow_overlap, allow_unknown = bool(b.get("allow_overlap")), bool(b.get("allow_unknown_impact"))

        def fn(prog):
            from . import tiles as tiles_mod
            aa = (self.info or {}).get("aa_dir")
            if project_mod.experimental_bundle_layout_edits(p):
                for bn in sorted({o["bundle"] for o in tiles_mod.ops_for(self.ws, p["name"])}):     # a position edit needs its composition bundle in the snapshot
                    if aa:
                        install.add_image_bundle(self.ws, aa, bn)
            for bn in sorted({o["bundle"] for o in (p.get("tile_bundle_ops") or ())}):
                if aa:
                    install.add_image_bundle(self.ws, aa, bn)
            reg, prof = self._plan_registry()
            rep = patcher.build(p, self.ws, ix, game_dir, self.cfg["build"]["keep_last_builds"], prog, reg=reg, profile=prof,
                                allow_overlap=allow_overlap, allow_unknown_impact=allow_unknown)
            rep.pop("spec")
            rep["literal_hits"] = rep["literal_hits"][:200]
            self._backup_build(p["name"], rep)
            return rep
        return self.start_job("building", fn)

    def _plan_registry(self):
        """The registry and install profile for build planning, or (None, None) when no installation is selected or
        scanned: the D1 policy treats that as 'not evaluated' (a value edit still builds; nothing is guessed)."""
        try:
            prof, reg = self._registry()
            return reg, prof
        except Exception:
            return None, None

    def build_review(self, q, b):
        """What a bundle build would do, without writing anything: the typed per-bundle ops, the adapter validation
        findings (the tile-overlap gate among them), and the D1 dependency impact with buildability and installation
        readiness reported separately."""
        from . import buildplan
        p = project_mod.load(self.ws, b["project"])
        reg, _prof = self._plan_registry()
        return buildplan.review(self.ws, p, self.index, reg=reg,
                                allow_overlap=bool(b.get("allow_overlap")),
                                allow_unknown_impact=bool(b.get("allow_unknown_impact")))

    def edit_adapters(self, q, b):
        """The typed asset adapters: what each one can edit, with its properties, limitations and evidence status."""
        from . import adapters
        return {"adapters": [a.info() for a in adapters.all_adapters()],
                "note": "adapters wrap the existing writers; no adapter is a second bundle writer"}

    def edit_read(self, q, b):
        """One asset read through its adapter: identity, a structured summary, the object fingerprint, the editable
        properties, the limitations and the evidence. Read only: the vanilla snapshot copy when the bundle is in it,
        else the installed file through the read-only bundle opener."""
        from . import adapters, bundles
        ws = self.ws
        src = ws.vanilla / b["bundle"] if (ws.vanilla / b["bundle"]).is_file() else None
        if src is None:
            try:
                prof = self._profile(b.get("install_id"))
                src = next((Path(r) / b["bundle"] for r in prof.get("aa_roots", []) if (Path(r) / b["bundle"]).is_file()), None)
            except Exception:
                src = None
        if src is None:
            raise FileNotFoundError("no copy of %s exists: not in the vanilla snapshot and not in the game folder" % b["bundle"])
        env = bundles.open_readonly(src)
        obj = next((o for o in env.objects if str(o.path_id) == str(b["path_id"])), None)
        if obj is None:
            raise KeyError("no object with path id %s in %s" % (b["path_id"], b["bundle"]))
        reg, _prof = self._plan_registry()
        asset = {"bundle": b["bundle"], "cab": None, "path_id": str(b["path_id"]), "name": None,
                 "type": obj.type.name, "role": None, "guid": None}
        if reg is not None:
            rows = reg.search_assets(bundle=b["bundle"], path_id=str(b["path_id"]))["assets"]
            if rows:
                asset.update(cab=rows[0]["cab"], name=rows[0].get("name"), guid=rows[0].get("guid"), role=rows[0].get("role"))
        tree = None
        if obj.type.name == "MonoBehaviour":
            tree = obj.read_typetree()
        adapter = adapters.find(obj.type.name, tree if isinstance(tree, dict) else None)
        if adapter is None:
            return {"adapter": None, "identity": dict(asset, source=str(src)),
                    "note": "no adapter owns this object type; it is preserved untouched by every build"}
        summary = adapter.describe(obj.type.name, tree if isinstance(tree, dict) else obj.read())
        return {"adapter": adapter.info(), "identity": dict(asset, source=str(src), read_only=True),
                "summary": summary, "fingerprint": bundles._digest(tree) if isinstance(tree, dict) else None}

    def reach(self, q, b):
        p = project_mod.load(self.ws, b["name"])
        aa = self.need_info()["aa_dir"]
        return self.start_job("reading layouts", lambda prog: layout.reach(
            p["scoped_rules"], layout.load_trees(aa, self.ws.cache, prog)))

    def do_install(self, q, b):
        info = self.need_info()
        d = patcher.latest_build(self.ws, b["name"])
        if not d:
            raise RuntimeError("no build for this project")
        return install.install(self.ws, info["aa_dir"], d, self.running, bool(b.get("force")),
                               self.cfg["install"]["backup_keep"], confirm_stale=bool(b.get("confirm_stale")))

    # ---- Stage 4B: installation profile, bundle inventory, asset registry (READ ONLY; nothing here writes a game folder)
    def _profile(self, install_id=None):
        from . import gameinstall
        try:
            return gameinstall.get(self.ws, install_id)
        except KeyError:
            if install_id or not self.info:
                raise
            return gameinstall.save(self.ws, gameinstall.describe_install(self.info["game_dir"], "installed", self._game_build()))

    def _registry(self, install_id=None):
        from . import registry
        p = self._profile(install_id)
        return p, registry.Registry.for_install(self.ws, p["install_id"])

    def install_profile_get(self, q, b):
        """The stored profile of the installation (the active one, or install_id), its problems and how the folder differs now from it."""
        from . import gameinstall
        d = gameinstall.load_all(self.ws)
        if not d["installs"] and not self.info:
            return {"active": None, "installs": [], "profile": None, "problems": [], "drift": []}
        p = self._profile(b.get("install_id"))
        d = gameinstall.load_all(self.ws)
        return {"active": d["active"], "installs": [{"install_id": k, "role": v.get("role"), "game_dir": v.get("game_dir")} for k, v in d["installs"].items()],
                "profile": p, "problems": gameinstall.validate(p), "drift": gameinstall.drift(p)}

    def install_profile_select(self, q, b):
        """Describe a game folder (default: the folder in use) and store the profile; nothing is written to the game folder."""
        from . import gameinstall
        folder = b.get("game_dir") or (self.info or {}).get("game_dir")
        if not folder:
            raise RuntimeError("no game install selected")
        prof = gameinstall.describe_install(folder, b.get("role") or "installed", b.get("game_build") or self._game_build())     # ProfileError (a ValueError) says why
        gameinstall.save(self.ws, prof)
        return {"profile": prof, "problems": gameinstall.validate(prof)}

    def inventory_status(self, q, b):
        p, reg = self._registry(b.get("install_id"))
        return dict(reg.summary(), install_id=p["install_id"], last_inventory_utc=p.get("last_inventory_utc"))

    def inventory_scan(self, q, b):
        """Job: inventory every bundle of the installation into the registry (read only; cancellable). verify=true hashes every file again."""
        from . import gameinstall, inventory
        p, reg = self._registry(b.get("install_id"))
        verify, days = bool(b.get("verify")), int(b.get("max_unverified_days", 7))

        def fn(prog):
            from .api.jobs import cancel_with
            drift = gameinstall.drift(p)
            try:
                out = inventory.scan(reg, p["aa_roots"], verify=verify, max_unverified_days=days, progress=prog, cancel=prog.cancelled)
            except inventory.ScanCancelled as e:
                cancel_with(dict(e.summary, install_id=p["install_id"], drift=drift))
            # Stage 4E: the same job fills the catalog and manifest.dat columns (read only; one extra file pass)
            from . import catalog
            ann = catalog.annotate(reg, p["aa_roots"], p, progress=prog, cancel=prog.cancelled)
            if ann.get("cancelled"):
                cancel_with(dict(out, install_id=p["install_id"], drift=drift, integrity=ann))
            gameinstall.touch_inventory(self.ws, p["install_id"])
            return dict(out, install_id=p["install_id"], drift=drift, integrity=ann)
        return self.start_job("scanning bundles", fn, cancellable=True)

    def inventory_list(self, q, b):
        p, reg = self._registry(b.get("install_id"))
        r = reg.list_bundles(b.get("q"), b.get("state"), b.get("kind"), b.get("crc_status"), int(b.get("limit", 200)), int(b.get("offset", 0)))
        return dict(r, install_id=p["install_id"])

    def inventory_get(self, q, b):
        p, reg = self._registry(b.get("install_id"))
        rec = reg.get_bundle(b["path"])
        if rec is None:
            raise KeyError("no such inventory bundle: " + b["path"])
        rec["asset_types"] = reg.type_counts(b["path"])
        return rec

    def registry_search(self, q, b):
        p, reg = self._registry(b.get("install_id"))
        r = reg.search_assets(b.get("q"), b.get("type"), b.get("bundle"), b.get("guid"), b.get("path_id"), b.get("panel_id"), b.get("ref_guid"),
                              int(b.get("limit", 100)), int(b.get("offset", 0)))
        return dict(r, install_id=p["install_id"])

    def registry_get(self, q, b):
        p, reg = self._registry(b.get("install_id"))
        a = reg.get_asset(b["bundle"], b["cab"], b["path_id"])
        if a is None:
            raise KeyError("no such inventory asset: %s / %s / %s" % (b["bundle"], b["cab"], b["path_id"]))
        return a

    # ---- Stage 4C: asset dependency graph (READ ONLY; built from the inventory, stored in the registry database)
    def graph_build(self, q, b):
        """Job: build or refresh the dependency graph from the inventory (read only, cancellable, incremental)."""
        from . import depgraph
        p, reg = self._registry(b.get("install_id"))
        scope, only, rebuild = b.get("scope") or "ui", set(b.get("bundles") or []) or None, bool(b.get("rebuild"))

        def fn(prog):
            from .api.jobs import cancel_with
            try:
                out = depgraph.build(reg, scope=scope, only=only, rebuild=rebuild, progress=prog, cancel=prog.cancelled)
            except depgraph.GraphCancelled as e:
                cancel_with(dict(e.summary, install_id=p["install_id"]))
            return dict(out, install_id=p["install_id"])
        return self.start_job("building the dependency graph", fn, cancellable=True)

    def graph_status(self, q, b):
        p, reg = self._registry(b.get("install_id"))
        return dict(reg.graph_summary(), install_id=p["install_id"])

    def graph_uses(self, q, b):
        from . import depgraph
        p, reg = self._registry(b.get("install_id"))
        r = depgraph.uses(reg, b["bundle"], b.get("cab"), b.get("path_id"), b.get("kinds"), int(b.get("limit", 500)), int(b.get("offset", 0)))
        return dict(r, install_id=p["install_id"])

    def graph_used_by(self, q, b):
        from . import depgraph
        p, reg = self._registry(b.get("install_id"))
        r = depgraph.used_by(reg, b["bundle"], b.get("cab"), b.get("path_id"), b.get("kinds"), int(b.get("limit", 500)), int(b.get("offset", 0)))
        return dict(r, install_id=p["install_id"])

    def graph_reachable(self, q, b):
        from . import depgraph
        p, reg = self._registry(b.get("install_id"))
        return depgraph.reachable(reg, b["bundle"], b["cab"], b["path_id"], b.get("direction") or "uses", int(b.get("max_depth", 6)), int(b.get("max_nodes", 2000)))

    def graph_affected(self, q, b):
        """Which bundles an edit of one asset affects (value / reference / identity), with what is unknown spelled out."""
        from . import depgraph
        p, reg = self._registry(b.get("install_id"))
        return depgraph.affected(reg, b["bundle"], b["cab"], b["path_id"], b["edit_kind"], b.get("new_targets"))

    def graph_screen(self, q, b):
        """The screen-level view (UiDocument-style graph) of a panel or an asset, projected from the registry graph."""
        from . import graphview
        p, reg = self._registry(b.get("install_id"))
        kw = {"max_depth": int(b.get("max_depth", 8)), "max_nodes": int(b.get("max_nodes", 500))}
        if b.get("panel_id"):
            r = graphview.project_panel(reg, b["panel_id"], **kw)
        else:
            r = graphview.project(reg, {"bundle": b["bundle"], "cab": b["cab"], "path_id": b["path_id"]}, **kw)
        return {"install_id": p["install_id"], "root": r["root"], "stats": r["stats"], "graph": r["graph"].to_dict()}

    # ---- Stage 4E: read-only catalog, CRC and build-integrity reporting (nothing here writes a game file)
    def catalog_status(self, q, b):
        """The installation's catalog.bin and manifest.dat: identity, parse status, record counts, the per-status
        bundle counts from the registry, and whether the recorded annotation is stale. Read only."""
        from . import catalog, fmmanifest
        p, reg = self._registry(b.get("install_id"))
        aa = p.get("aa_roots") or []
        cat = catalog.read(catalog.catalog_path_for(aa, p))
        man = fmmanifest.read(fmmanifest.path_for(aa, p))
        meta = reg.get_integrity_meta()
        stale = bool(meta and meta.get("catalog_sha256") and cat.get("sha256") and meta["catalog_sha256"] != cat["sha256"]) \
            or bool(meta and meta.get("manifest_sha256") and man.get("sha256") and meta["manifest_sha256"] != man["sha256"]) \
            or bool(p.get("catalog_sha256") and cat.get("sha256") and p["catalog_sha256"] != cat["sha256"])
        return {"install_id": p["install_id"],
                "catalog": {"path": cat.get("path"), "sha256": cat.get("sha256"), "size": cat.get("size"),
                            "status": cat["status"], "reason": cat.get("reason"), "header": cat.get("header"),
                            "records": len(cat.get("records") or []), "rejected_records": cat.get("rejected", 0),
                            "format": cat.get("format"), "parser_version": catalog.PARSER_VERSION},
                "manifest_dat": {"path": man.get("path"), "sha256": man.get("sha256"), "size": man.get("size"),
                                 "status": man["status"], "reason": man.get("reason"), "note": man.get("note"),
                                 "parser_version": fmmanifest.PARSER_VERSION},
                "counts": reg.integrity_counts(), "annotated_utc": (meta or {}).get("annotated_utc"),
                "identity_stale": stale,
                "note": "the per-bundle statuses are in inventory.list; a stale identity means the annotation was taken "
                        "against another catalog or manifest, so the stored statuses are a record of that annotation, "
                        "not of the files now on disk"}

    def catalog_annotate(self, q, b):
        """Job: fill every inventoried bundle's catalog and manifest.dat columns (read only on the game: the catalog
        and manifest are parsed once, each bundle file is read once for its whole-file CRC; only the registry is written)."""
        from . import catalog
        p, reg = self._registry(b.get("install_id"))

        def fn(prog):
            from .api.jobs import cancel_with
            out = catalog.annotate(reg, p["aa_roots"], p, progress=prog, cancel=prog.cancelled)
            if out.get("cancelled"):
                cancel_with(dict(out, install_id=p["install_id"]))
            return dict(out, install_id=p["install_id"])
        return self.start_job("checking catalog and manifest integrity", fn, cancellable=True)

    def integrity_bundle(self, q, b):
        """One bundle's complete integrity record: every hash named for what it is, the catalog lookup kept separate
        from the CRC comparison, and the manifest.dat lookup separate from both. Read only."""
        from . import catalog
        p, reg = self._registry(b.get("install_id"))
        return dict(catalog.integrity_bundle(reg, b["path"], p, p.get("aa_roots")), install_id=p["install_id"])

    # ---- Stage 4F: installation transactions (preflight read only; apply/rollback/recover write the game folder
    # only after verified backups; every step is journalled in the per-installation registry)
    def _tx_profile(self, install_id):
        return self._profile(install_id)

    def install_preflight(self, q, b):
        """What installing the project's latest build would do, without modifying anything: package validation, the
        installation profile identity, per-file target states, the Stage 4E integrity warnings, and the explicit
        confirmations needed (blocked conditions cannot be confirmed away)."""
        from . import installtx
        prof = self._tx_profile(b.get("install_id"))
        d = patcher.latest_build(self.ws, b["project"])
        if not d:
            return {"ready": False, "no_build": True, "blocked": [], "warnings": [],
                    "required_confirmations": [], "file_operations": [],
                    "target_profile": {"install_id": prof.get("install_id"), "game_build": prof.get("game_build"),
                                       "game_dir": prof.get("game_dir")},
                    "package_identity": {"project": b["project"], "dir": None},
                    "integrity_summary": [], "diagnostics": []}
        return installtx.preflight(self.ws, prof, d)

    def install_apply(self, q, b):
        """Job: one complete installation transaction (preflight, verified backups, staged and atomically replaced
        files, post-write verification, the journal). Cancellable before every destructive step; never reports a
        cancelled or failed transaction as completed."""
        from . import installtx
        prof = self._tx_profile(b.get("install_id"))
        d = patcher.latest_build(self.ws, b["project"])
        if not d:
            raise RuntimeError("no build for this project")
        confirmations = list(b.get("confirmations") or [])

        def fn(prog):
            from .api.jobs import cancel_with
            try:
                rec = installtx.apply(self.ws, prof, d, confirmations=confirmations, running=self.running,
                                      progress=prog, cancel=prog.cancelled)
            except installtx.Cancelled as e:
                cancel_with(e.summary)
            return self._tx_view(rec)
        return self.start_job("installing (transaction)", fn, cancellable=True)

    def install_history(self, q, b):
        """The installation transactions of the installation, newest first, with the recovery-required ones first
        class. Read only."""
        from . import installtx
        p, reg = self._registry(b.get("install_id"))
        rows = reg.list_txs(limit=int(b.get("limit", 50)))
        return {"install_id": p["install_id"],
                "recovery_required": [self._tx_view(r) for r in reg.list_txs(states=installtx.BUSY_STATES, limit=50)],
                "transactions": [self._tx_view(r) for r in rows]}

    def install_transaction(self, q, b):
        """One transaction with its per-file operations, its approved overrides and its rollback state. Read only."""
        p, reg = self._registry(b.get("install_id"))
        tx = reg.get_tx(b["tx_id"])
        if tx is None:
            raise KeyError("no such transaction: %s" % b["tx_id"])
        return self._tx_view(tx, reg.get_ops(tx["tx_id"]))

    def install_rollback(self, q, b):
        """Job: roll one transaction back to its exact pre-installation state, verifying every restored file. A file
        that changed independently is never overwritten: the transaction ends rollback_failed and asks for a person."""
        from . import installtx
        prof = self._tx_profile(b.get("install_id"))

        def fn(prog):
            from .api.jobs import cancel_with
            reg = installtx._reg(self.ws, prof)
            try:
                rec = installtx.rollback(self.ws, reg, prof, b["tx_id"], progress=prog, cancel=prog.cancelled)
            except installtx.Cancelled as e:
                cancel_with(e.summary)
            return self._tx_view(rec, reg.get_ops(b["tx_id"]))
        return self.start_job("rolling back", fn, cancellable=True)

    def install_recovery_scan(self, q, b):
        """READ ONLY: the unfinished transactions of the installation, each assessed against the journal AND the
        actual hashes on disk, with the safe actions and a recommendation. Nothing is modified."""
        from . import installtx
        prof = self._tx_profile(b.get("install_id"))
        return installtx.recovery_scan(self.ws, prof)

    def install_recover(self, q, b):
        """Job: explicit recovery of one unfinished transaction - 'rollback', 'resume' (only where the scan proved
        it unambiguous; idempotent) or 'manual' (marks it for a person, modifies nothing)."""
        from . import installtx
        prof = self._tx_profile(b.get("install_id"))

        def fn(prog):
            from .api.jobs import cancel_with
            try:
                rec = installtx.recover(self.ws, prof, b["tx_id"], b["action"], running=self.running,
                                        progress=prog, cancel=prog.cancelled)
            except installtx.Cancelled as e:
                cancel_with(e.summary)
            return self._tx_view(rec, installtx._reg(self.ws, prof).get_ops(b["tx_id"]))
        return self.start_job("recovering the installation", fn, cancellable=True)

    @staticmethod
    def _tx_view(tx, ops=None):
        """A transaction record shaped for the UI: the stored preflight stays out unless explicitly requested."""
        out = {k: tx.get(k) for k in ("tx_id install_id package_id package_schema package_dir project game_build "
                                      "steam_build_id catalog_sha256 manifest_sha256 state created_utc updated_utc "
                                      "initiating completed_utc error recovery").split()}
        try:
            out["overrides"] = json.loads(tx.get("overrides") or "[]")
        except ValueError:
            out["overrides"] = None
        if ops is not None:
            out["file_operations"] = [{k: o.get(k) for k in ("op_index rel_path op original_exists original_sha256 "
                                                             "backup_path backup_sha256 staged_sha256 expected_sha256 "
                                                             "actual_sha256 state verify rollback_state error").split()}
                                      | {"op_index": o.get("op_index")} for o in ops]
        return out

    def backups(self, q, b):
        return install.list_backups(self.ws)

    def restore(self, q, b):
        return install.restore(self.ws, self.need_info()["aa_dir"], b["backup"], self.running,
                               self.cfg["install"]["backup_keep"])

    def make_launcher(self, q, b):
        """Without confirm: the plan (target, baked paths). With confirm and one of the offered folders: generate."""
        p = launcher.plan(self.cfg)
        if not b.get("confirm"):
            return p
        if b.get("target_dir") not in p["choices"]:
            raise RuntimeError("target must be one of: " + ", ".join(p["choices"]))
        return launcher.generate(self.cfg, b["target_dir"])

    def quit(self, q, b):
        stop = getattr(self, "on_quit", None) or (self.httpd.shutdown if hasattr(self, "httpd") else None)
        if stop:
            threading.Thread(target=stop, daemon=True).start()
        return {"stopping": bool(stop)}

    def models(self, q, b):
        return [m["name"] for m in preview.models()]

    def _preview_project(self, q):
        name = q.get("project")
        if name == "__compare__":                              # the loaded comparison's colours (temporary, never saved)
            if not getattr(self, "compare", None):
                raise ValueError("no comparison loaded (Compare tab)")
            return self.compare["project"]
        return project_mod.load(self.ws, name) if name else None

    # ---- compare another skin (read-only)
    def compare_load(self, q, b):
        info = self.info or {}
        rep = skins.load(b["path"], self.index, info.get("aa_dir"))
        self.compare = {"report": rep, "project": skins.as_project(rep)}
        return rep

    def compare_state(self, q, b):
        return getattr(self, "compare", None) and self.compare["report"]

    def compare_asset(self, q, b):
        """An image the loaded USS skin references (only files listed in its report)."""
        rep = (getattr(self, "compare", None) or {}).get("report") or {}
        a = next((x for x in rep.get("assets", []) if x["file"] == q.get("file") and x["kind"] == "image" and x["exists"]), None)
        if not a:
            raise KeyError("no such asset in the comparison")
        data = (Path(rep["path"]) / a["file"]).read_bytes()
        kind = images.sniff(data)
        if kind not in ("png", "jpg", "webp"):
            raise ValueError("not an image")
        return data, {"png": "image/png", "jpg": "image/jpeg", "webp": "image/webp"}[kind]

    def compare_thumb(self, q, b):
        rep = (getattr(self, "compare", None) or {}).get("report") or {}
        name, pid = self._image_key(q)
        if q.get("side") == "theirs":
            if not any(x["bundle"] == name for x in rep.get("bundles", [])):
                raise KeyError("bundle not in the comparison")
            src = Path(rep["path"]) / name
            if not src.is_file():
                src = next(Path(rep["path"]).rglob(name))
        else:
            src = Path(self.need_info()["aa_dir"]) / name
        return images.thumbnail(src, pid), "image/png"

    def compare_import(self, q, b):
        """A new project with the comparison's colour tokens (token overrides only)."""
        if not getattr(self, "compare", None):
            raise ValueError("no comparison loaded")
        if b["name"] in project_mod.names(self.ws):
            raise ValueError("a project with that name exists")
        p = skins.as_project(self.compare["report"], b["name"])
        project_mod.save(self.ws, p)
        return {"project": project_mod.load(self.ws, b["name"]), "tokens": len(p["token_overrides"])}

    # ---- SKIN-RR1 C7: read-only third-party skin inspection (no write path)
    def skin_inspect(self, q, b):
        """Read-only diff of a third-party skin folder against stock bundles, with full screen-graph resolution."""
        from . import skin_diff, table_usage
        folder = Path(b["folder"])
        if not folder.is_dir():
            raise ValueError("skin folder not found: %s" % folder)
        stock_dir = b.get("stock_dir") or self.need_info()["aa_dir"]
        resolver = getattr(self, "_skin_resolver_cache", None)
        if resolver is None or getattr(resolver, "_stock_dir", None) != str(stock_dir):
            try:
                dump = self._preview_dump()
            except Exception:
                dump = None
            tu = table_usage.load(self.ws.root / "table-view-usage.json")
            try:
                tbls = self._tables()
            except Exception:
                tbls = None
            resolver = skin_diff.ScreenResolver(
                dump=dump, table_usage=tu, tables_obj=tbls, stock_dir=stock_dir,
            )
            resolver._stock_dir = str(stock_dir)
            self._skin_resolver_cache = resolver
        rep = skin_diff.diff_skin_folder(
            folder, stock_dir, bundle_filter=b.get("bundles"), resolver=resolver,
        )
        rep["bundles"] = [
            {"bundle": x["bundle"], "status": x["status"], "counts": x["counts"], "by_category": x["by_category"]}
            for x in rep["bundles"]
        ]
        return rep

    # ---- SKIN-RR2 Part C: Injected styles (AlwaysAppliedStyleSheet) + skin style import
    def skin_style_definitions(self, q, b):
        """Read-only list of classes/rules and variables from an inspected skin's AlwaysAppliedStyleSheet."""
        from . import skin_diff
        folder = Path(b["folder"])
        if not folder.is_dir():
            raise ValueError("skin folder not found: %s" % folder)
        stock_dir = b.get("stock_dir") or self.need_info()["aa_dir"]
        return skin_diff.read_skin_style_definitions(
            folder, stock_dir=stock_dir, sheet=b.get("sheet") or "AlwaysAppliedStyleSheet",
            query=str(b.get("q") or ""), limit=int(b.get("limit") or 150),
        )

    def styles_injected_get(self, q, b):
        """Return custom classes, rules, CSS variables and USS text targeting AlwaysAppliedStyleSheet."""
        from . import colour, projfmt
        name = b["project"]
        p = project_mod.load(self.ws, name)
        sheet = "AlwaysAppliedStyleSheet"
        rel = "styles/%s.uss" % sheet
        cls_re = re.compile(r"\.([A-Za-z_][\w-]*)")

        if projfmt.is_folder(self.ws, name):
            try:
                uss_text = projfmt.read_file(self.ws, name, rel)
            except FileNotFoundError:
                uss_text = ""
        else:
            sheet_rules = [e for e in p.get("scoped_rules", []) if e.get("sheet") == sheet]
            uss_text = projfmt.rules_text(sheet, sheet_rules) if sheet_rules else ""

        rules_out = []
        vars_out = []
        cls_map: dict[str, dict] = {}
        sheet_rules = [e for e in p.get("scoped_rules", []) if e.get("sheet") == sheet and e.get("selector", "").strip() != ":root"]
        reach_by_sel: dict[str, int] = {}
        aa = (self.info or {}).get("aa_dir")
        if aa and sheet_rules:
            try:
                trees = getattr(self, "_cached_layout_trees", None)
                if trees is None:
                    trees = layout.load_trees(aa, self.ws.cache)
                    self._cached_layout_trees = trees
                for rr in layout.reach(sheet_rules, trees):
                    reach_by_sel[rr["branch"]] = reach_by_sel.get(rr["branch"], 0) + int(rr.get("hits") or 0)
            except Exception:
                pass

        for idx, e in enumerate(p.get("scoped_rules", [])):
            if e.get("sheet") != sheet:
                continue
            sel = e["selector"]
            props = {k: project_mod.patch_text(v) for k, v in (e.get("props") or {}).items()}
            src = e.get("source")
            if sel.strip() == ":root":
                for vn, vv in props.items():
                    if vn.startswith("--"):
                        vars_out.append({"name": vn, "value": vv, "scope": "AlwaysAppliedStyleSheet", "source": src})
                continue
            classes = sorted(set(cls_re.findall(sel)))
            body = "".join("    %s: %s;\n" % (k, v) for k, v in props.items())
            branches = [s.strip() for s in sel.split(",") if s.strip()]
            rule_reach = sum(reach_by_sel.get(br, 0) for br in branches) if reach_by_sel or (aa and sheet_rules) else None
            src_tag = (src.get("skin") if isinstance(src, dict) else src) or e.get("op") or "manual"
            rules_out.append({
                "index": idx,
                "selector": sel,
                "classes": classes,
                "props": props,
                "op": e.get("op"),
                "source": src,
                "source_tag": src_tag,
                "reach": rule_reach,
                "zero_reach_warning": "0 matches on stock UXML" if rule_reach == 0 else None,
                "uss_text": "%s {\n%s}" % (sel, body),
            })
            for c in classes:
                rec = cls_map.setdefault(c, {"name": c, "rules": 0, "selectors": [], "source": src})
                rec["rules"] += 1
                rec["selectors"].append(sel)
                if src and not rec.get("source"):
                    rec["source"] = src

        for t in p.get("token_overrides", []):
            vars_out.append({
                "name": t["token"],
                "value": project_mod.patch_text(t["value"]),
                "scope": "tokens",
                "source": t.get("source"),
            })

        return {
            "project": name,
            "sheet": sheet,
            "file": rel,
            "header_note": "AlwaysAppliedStyleSheet: one global stylesheet; each rule shows its Source tag and stock UXML reach.",
            "uss_text": uss_text,
            "classes": sorted(cls_map.values(), key=lambda x: x["name"]),
            "variables": vars_out,
            "rules": rules_out,
        }

    def styles_injected_save(self, q, b):
        """Save AlwaysAppliedStyleSheet USS text and return updated diagnostics and injected styles summary."""
        from . import projfmt, ussdiag
        name = b["project"]
        text = b["text"]
        sheet = "AlwaysAppliedStyleSheet"
        rel = "styles/%s.uss" % sheet
        problems = []
        if projfmt.is_folder(self.ws, name):
            problems = projfmt.write_file(self.ws, name, rel, text)
            pdir = projfmt.folder(self.ws, name)
            mp = json.loads((pdir / "mapping.json").read_text(encoding="utf-8"))
            if not any(ent.get("source") == rel for ent in mp.get("entries", [])):
                mp.setdefault("entries", []).append({"source": rel, "target": {"sheet": sheet}})
                (pdir / "mapping.json").write_text(json.dumps(mp, indent=2) + "\n", encoding="utf-8")
            problems = projfmt.read(self.ws, name, strict=False)[1]
        else:
            parsed, parse_probs = projfmt.parse_uss(text, rel)
            problems = list(parse_probs)
            if not problems:
                p = project_mod.load(self.ws, name)
                kept = [e for e in p.get("scoped_rules", []) if e.get("sheet") != sheet]
                for r in parsed:
                    e = {"sheet": sheet, "selector": r["selector"],
                         "props": {k: projfmt._val(v) for k, v, _, _ in r["decls"]}}
                    e.update(r.get("meta") or {})
                    if r.get("op"):
                        e["op"] = r["op"]
                    if r.get("op") == "remove":
                        e["remove"] = r["remove"]
                    kept.append(e)
                p["scoped_rules"] = kept
                project_mod.save(self.ws, p)
        diags = ussdiag.check(text, self.index, sheet)
        return {
            "diagnostics": diags,
            "problems": problems,
            "injected": self.styles_injected_get(q, {"project": name}),
        }

    def styles_import_from_skin(self, q, b):
        """Import a class rule or :root variable from an inspected skin into AlwaysAppliedStyleSheet, tagged with source."""
        from . import colour, skin_diff, token_patch as tp
        name = b["project"]
        folder = Path(b["folder"])
        kind = b["kind"]
        target_name = b["name"]
        selector_want = b.get("selector")
        stock_dir = b.get("stock_dir") or (self.info or {}).get("aa_dir")
        defs = skin_diff.read_skin_style_definitions(
            folder, stock_dir=stock_dir, sheet="AlwaysAppliedStyleSheet", query="", limit=20000,
        )
        src_meta = {"skin": defs["source"]["name"], "version": defs["source"]["version"]}
        p = project_mod.load(self.ws, name)
        sheet = "AlwaysAppliedStyleSheet"
        imported = []

        if kind == "variable":
            v = next((x for x in defs["variables"] if x["name"] == target_name), None)
            if v is None:
                raise KeyError("no such variable in inspected skin: %s" % target_name)
            val = colour.canonical(v["value"])
            project_mod.check_value(val)
            # Update or append :root rule targeting AlwaysAppliedStyleSheet so both bundle and native export carry it
            root_rule = next(
                (r for r in p.get("scoped_rules", []) if r.get("sheet") == sheet and r.get("selector") == ":root" and r.get("source") == src_meta),
                None,
            )
            if root_rule is None:
                root_rule = {"sheet": sheet, "selector": ":root", "props": {}, "source": src_meta, "note": skin_diff.PERSONAL_USE_NOTICE}
                p.setdefault("scoped_rules", []).append(root_rule)
            root_rule["props"][target_name] = val
            imported.append({"kind": "variable", "name": target_name, "value": v["value"]})
        else:
            matches = [
                r for r in defs["rules"]
                if (selector_want and r["selector"] == selector_want) or (not selector_want and target_name in r["classes"])
            ]
            if not matches:
                raise KeyError("no matching rule for class %s in inspected skin" % target_name)
            for m in matches[:8]:
                try:
                    project_mod.check_selector(m["selector"])
                except ValueError:
                    continue
                clean_props = {}
                for k, v in m["props"].items():
                    if not (k.startswith("--") or k in tp.PROP_TABLE):
                        continue
                    try:
                        cv = colour.canonical(v)
                        project_mod.check_value(cv)
                        clean_props[k] = cv
                    except Exception:
                        continue
                if not clean_props:
                    continue
                existing = next(
                    (r for r in p.get("scoped_rules", []) if r.get("sheet") == sheet and r.get("selector") == m["selector"] and not r.get("op")),
                    None,
                )
                if existing is not None:
                    existing["props"].update(clean_props)
                    existing["source"] = src_meta
                    existing["note"] = skin_diff.PERSONAL_USE_NOTICE
                else:
                    p.setdefault("scoped_rules", []).append({
                        "sheet": sheet,
                        "selector": m["selector"],
                        "props": clean_props,
                        "source": src_meta,
                        "note": skin_diff.PERSONAL_USE_NOTICE,
                    })
                imported.append({"kind": "class", "selector": m["selector"], "props": len(clean_props)})
            if not imported:
                raise ValueError("matched rule(s) use only unencodable asset/unknown properties")

        project_mod.save(self.ws, p)
        return {
            "source": defs["source"],
            "notice": skin_diff.PERSONAL_USE_NOTICE,
            "imported": imported,
            "injected": self.styles_injected_get(q, {"project": name}),
        }

    def skin_preview_composition(self, q, b):
        """Read-only rea runtime preview of a composition directly from an inspected skin folder."""
        from . import custom_layouts as cl, layoutspace, skin_diff
        from .render import pitch as pitch_mod, preview as preview_mod, screen as screen_mod
        folder = Path(b["folder"])
        comp = b["composition"]
        obj = skin_diff.read_skin_composition(folder, comp)
        if obj is None:
            raise ValueError("no such composition in skin folder: %s" % comp)
        vp = dict(preview_mod.MEASURED_VIEWPORT)
        width = int(b.get("width") or vp["width"])
        height = int(b.get("height") or vp["height"])
        base_comp = re.sub(r"[-_]RR\d*$", "", comp, flags=re.I)
        panel = preview_mod.MEASURED_PANEL_RECTS.get((comp, width, height)) or preview_mod.MEASURED_PANEL_RECTS.get((base_comp, width, height))
        content_rect = panel[1] if panel else (vp["content_rect"] if (width, height) == (2560, 1440) else None)
        if content_rect is not None:
            rcols, rrows = screen_mod.grid_dims_content(content_rect[2], content_rect[3])
        else:
            rcols, rrows = screen_mod.grid_dims(width, height, pitch_mod.lookup(base_comp), padding=12)
        dcols, drows = cl.grid_extent(obj)
        reflow = int(obj.get("m_reflowMode", 0))
        cells_in = []
        for i, c in enumerate(obj.get("m_gridComponents") or []):
            if not isinstance(c, dict):
                continue
            loc = c.get("m_location") or {}
            mn = c.get("m_minSize") or {}
            mx = c.get("m_maxSize") or {}
            cells_in.append({
                "composition": comp, "cell_index": i, "element_id": c.get("m_elementID"),
                "x": int(loc.get("x", 0)), "y": int(loc.get("y", 0)),
                "w": int(loc.get("width", 0)), "h": int(loc.get("height", 0)),
                "min_w": int(mn.get("x", 1)), "min_h": int(mn.get("y", 1)),
                "max_w": int(mx.get("x", 0)), "max_h": int(mx.get("y", 0)),
                "flags": [],
            })
        mini_dump = {"cells": cells_in, "layouts": [], "tiles": []}
        a = screen_mod.Assembler(mini_dump)
        preview_mod.apply_custom(a, comp, obj)
        placed = preview_mod.rule_place(a, comp, rcols, rrows, reflow, engine="rea")

        def px_rect(col, row, w, h):
            px = screen_mod.cell_px(col, row, w, h)
            if content_rect is not None:
                return [round(content_rect[0] + px["left"], 1), round(content_rect[1] + px["top"], 1),
                        round(px["width"], 1), round(px["height"], 1)]
            return [round(px["left"], 1), round(px["top"], 1), round(px["width"], 1), round(px["height"], 1)]

        surplus = max(0, rcols - dcols)
        cells_out = []
        hosts = []
        for i, comp_cell in enumerate(obj.get("m_gridComponents") or []):
            if not isinstance(comp_cell, dict):
                continue
            eid = comp_cell.get("m_elementID")
            loc = comp_cell.get("m_location") or {}
            sx, sy, sw, sh = int(loc.get("x", 0)), int(loc.get("y", 0)), int(loc.get("width", 1)), int(loc.get("height", 1))
            strip = sx + sw >= dcols
            g = placed.get(eid) or {"col": sx + (surplus if strip else 0), "row": sy, "w": sw, "h": sh}
            rx, ry, rw, rh = int(g["col"]), int(g["row"]), int(g["w"]), int(g["h"])
            rect = px_rect(rx, ry, rw, rh)
            entry = {
                "space": "main", "order": i, "element_id": eid,
                "x": rx, "y": ry, "w": rw, "h": rh,
                "rect": rect, "reason": "",
            }
            cells_out.append(entry)
            hosts.append({"host": {"cell_index": i, "element_id": eid,
                                   "geometry": {"x": rx, "y": ry, "w": rw, "h": rh}},
                          "rect": rect, "space": "main", "reason": ""})
        slots_out = []
        design_box = {"cols": dcols, "rows": drows}
        runtime_box = {"cols": rcols, "rows": rrows}
        for zone, entries in (obj.get("m_optionalSlices") or {}).items():
            if not isinstance(entries, list):
                continue
            for idx, e in enumerate(entries):
                if not isinstance(e, dict) or "m_elementID" not in e:
                    continue
                loc = e.get("m_location") or {}
                sx, sy, sw, sh = int(loc.get("x", 0)), int(loc.get("y", 0)), int(loc.get("width", 0)), int(loc.get("height", 0))
                rx, ry = layoutspace.slot_to_runtime(zone, sx, sy, design_box, runtime_box)
                rect = px_rect(rx, ry, sw, sh)
                slot_entry = {
                    "space": zone, "order": idx, "element_id": e["m_elementID"],
                    "x": rx, "y": ry, "w": sw, "h": sh, "stored": {"x": sx, "y": sy, "w": sw, "h": sh},
                    "rect": rect, "reason": "",
                }
                slots_out.append(slot_entry)
                hosts.append({"host": {"cell_index": idx, "element_id": e["m_elementID"],
                                       "geometry": {"x": rx, "y": ry, "w": sw, "h": sh}},
                              "rect": rect, "space": zone, "reason": ""})
        problems = layoutspace.runtime_problems(
            [{"element_id": h["host"]["element_id"], **h["host"]["geometry"]} for h in hosts],
            rcols, rrows,
        )
        return {
            "composition": comp, "source": "skin_inspect", "engine": "rea",
            "confidence": preview_mod.confidence_for(base_comp, "rea"),
            "viewport": dict(vp, width=width, height=height, grid={"cols": rcols, "rows": rrows}),
            "design": design_box, "grid": runtime_box,
            "cells": cells_out, "slots": slots_out, "hosts": hosts,
            "problems": problems,
        }

    def preview_models(self, q, b):
        return preview.models()

    def preview_model(self, q, b):
        """The model evaluated against a project (or vanilla when no project is given)."""
        return preview.evaluate(preview.load(q["name"]), self.index, self._preview_project(q))

    def preview_image(self, q, b):
        return preview.image(q["name"]), "image/png"

    def preview_suggest(self, q, b):
        return preview.suggest(preview.load(q["name"]), self.index, q["rgb"])

    # ---- image and SVG swaps
    def images_catalog(self, q, b):
        return images.catalog(self.ws, self.need_info()["aa_dir"], refresh=q.get("refresh") == "1")

    def _image_key(self, q):
        name, pid = q.get("bundle", ""), q.get("path_id", "")
        if not images.BUNDLE_RE.fullmatch(name) or not re.fullmatch(r"-?\d{1,20}", pid):
            raise ValueError("bad bundle or path_id")
        return name, int(pid)

    _thumb_locks = {}

    def images_thumb(self, q, b):
        """Thumbnails come from the live game bundle (read-only); the first request for a bundle renders all of its images once."""
        name, pid = self._image_key(q)
        live = Path(self.need_info()["aa_dir"]) / name
        cache = Path(self.ws.cache) / "thumbs" / name
        tag = str(live.stat().st_mtime_ns)
        if name == images.ICONS % "2x":                      # icons: cropped out of the 2x atlas
            tag += "_" + str((live.parent / (images.ATLASES % "2x")).stat().st_mtime_ns)
        f = cache / ("%d_%s.png" % (pid, tag))
        if not f.is_file():
            lock = self._thumb_locks.setdefault(name, threading.Lock())
            with lock:
                if not f.is_file():
                    if name == images.ICONS % "2x":
                        images.icon_thumbnails(live.parent, cache, tag)
                    else:
                        images.thumbnails_for_bundle(live, cache, tag)
        if not f.is_file():
            raise KeyError("no image with path id %d in %s" % (pid, name))
        return f.read_bytes(), "image/png"

    def _swap_dir(self, project):
        project_mod.load(self.ws, project)                      # the project must exist
        d = project_mod.images_dir(self.ws, project)
        d.mkdir(parents=True, exist_ok=True)
        return d

    def images_source(self, q, b):
        """The stored replacement as PNG (an SVG is rendered the way the game will draw it)."""
        d = self._swap_dir(q["project"])
        if not images.SOURCE_RE.fullmatch(q.get("file", "")):
            raise ValueError("bad file name")
        data = (d / q["file"]).read_bytes()
        if q["file"].lower().endswith(".svg"):
            return images.render_svg_png(data, 256, 256), "image/png"
        return data, {"png": "image/png", "jpg": "image/jpeg", "webp": "image/webp"}[images.sniff(data)]

    def images_swap(self, q, b, where=None):
        """Raw body: the replacement file. Query: project, bundle, path_id, kind, name, fit. where: the places a native skin shows a
        wallpaper (None keeps the slot's earlier choice)."""
        name, pid = self._image_key(q)
        kind, fit = q.get("kind"), q.get("fit", "cover")
        if not b or len(b) > 40 * 1024 * 1024:
            raise ValueError("send the image file (at most 40 MB)")
        ext = images.sniff(b)
        if kind == "svg" and ext != "svg":
            raise ValueError("an SVG slot takes an .svg file")
        if kind == "texture" and ext not in ("png", "jpg", "webp"):
            raise ValueError("an image slot takes a PNG, JPG or WebP file")
        if kind == "icon" and ext not in ("png", "jpg", "webp", "svg"):
            raise ValueError("an icon takes a PNG, JPG, WebP or SVG file")
        notes = []
        if ext == "svg":
            notes = images.svg_to_vector({"size": {"x": 64.0, "y": 64.0}, "vertices": [], "indices": [], "settings": []}, b)   # converts?
        else:
            from PIL import Image
            import io as _io
            Image.open(_io.BytesIO(b)).verify()
        aa = self.need_info()["aa_dir"]
        if kind == "icon":                                   # every UI scale: the sprite bundle and its atlas bundle
            for _s, ib, ab in images.icon_bundles(aa):
                install.add_image_bundle(self.ws, aa, ib)
                install.add_image_bundle(self.ws, aa, ab)
        else:
            install.add_image_bundle(self.ws, aa, name)
        d = self._swap_dir(q["project"])
        fn = "%s_%d.%s" % (re.sub(r"[^\w.-]", "_", name[:-len(".bundle")]), abs(pid), ext)
        (d / fn).write_bytes(b)
        p = project_mod.load(self.ws, q["project"])
        old = next((e for e in p.get("image_swaps", []) if e["bundle"] == name and e["path_id"] == str(pid)), None)
        p["image_swaps"] = [e for e in p.get("image_swaps", []) if e is not old]
        entry = {"bundle": name, "path_id": str(pid), "name": q.get("name", "")[:120], "kind": kind, "source": fn, "fit": fit}
        keep = where if where is not None else (old or {}).get("where")
        if keep is not None:
            entry["where"] = list(keep)
        p["image_swaps"].append(entry)
        project_mod.save(self.ws, project_mod.validate(project_mod.migrate(p)))
        return {"project": project_mod.load(self.ws, q["project"]), "notes": notes}

    def images_commit(self, q, b):
        """The staged edit of one slot in a single write: the replacement file (path; omit to keep the stored one), fit and where."""
        args = {k: str(v) for k, v in b.items() if k in ("project", "bundle", "path_id", "kind", "name", "fit") and v is not None}
        where = b.get("where")
        if b.get("path"):
            f = Path(b["path"])
            if not f.is_file() or f.stat().st_size > 40 * 1024 * 1024:
                raise ValueError("pick an image file (at most 40 MB)")
            return self.images_swap(args, f.read_bytes(), list(where) if where is not None else None)
        p = project_mod.load(self.ws, b["project"])
        e = next((x for x in p.get("image_swaps", []) if x["bundle"] == b["bundle"] and x["path_id"] == str(b["path_id"])), None)
        if not e:
            raise ValueError("this slot has no stored replacement yet; stage a file first")
        if b.get("fit"):
            e["fit"] = b["fit"]
        if where is not None:
            e["where"] = list(where)
        project_mod.save(self.ws, project_mod.validate(project_mod.migrate(p)))
        return {"project": project_mod.load(self.ws, b["project"]), "notes": []}

    def images_preview_file(self, q, b):
        """A local file as a PNG preview (staged pictures that are not in the project yet); an SVG is drawn the way the game will."""
        f = Path(b["path"])
        if not f.is_file() or f.stat().st_size > 40 * 1024 * 1024:
            raise ValueError("not an image file (at most 40 MB)")
        data = f.read_bytes()
        if images.sniff(data) == "svg":
            return images.render_svg_png(data, 256, 256), "image/png"
        from PIL import Image
        with Image.open(io.BytesIO(data)) as im:
            im = im.convert("RGBA")
            im.thumbnail((360, 220))
            out = io.BytesIO()
            im.save(out, "PNG")
        return out.getvalue(), "image/png"

    def images_swap_file(self, q, b):
        """images.swap with the replacement read from a local file (picked in the desktop shell) instead of sent as base64."""
        f = Path(b["path"])
        if not f.is_file() or f.stat().st_size > 40 * 1024 * 1024:
            raise ValueError("pick an image file (at most 40 MB)")
        args = {k: str(v) for k, v in b.items() if k in ("project", "bundle", "path_id", "kind", "name", "fit")}
        return self.images_swap(args, f.read_bytes())

    def images_fit(self, q, b):
        """Change how a stored replacement is fitted (cover, contain, stretch)."""
        p = project_mod.load(self.ws, b["project"])
        e = next((x for x in p.get("image_swaps", []) if x["bundle"] == b["bundle"] and x["path_id"] == str(b["path_id"])), None)
        if not e:
            raise ValueError("no such image swap")
        e["fit"] = b["fit"]
        project_mod.save(self.ws, project_mod.validate(project_mod.migrate(p)))
        return {"project": project_mod.load(self.ws, b["project"])}

    def assets_conflicts(self, q, b):
        from . import assetcheck
        p = project_mod.load(self.ws, b["project"])
        aa = (self.info or {}).get("aa_dir")
        cat = cls = None
        if aa and p.get("image_swaps"):
            cat = images.catalog(self.ws, aa)
            try:
                cls = images.icon_classes(aa)
            except Exception:
                cls = None
        return {"conflicts": assetcheck.conflicts(self.ws, p, cat, cls, b.get("target"))}

    def _catalog_row(self, q):
        name, pid = self._image_key(q)
        row = next((r for r in images.catalog(self.ws, self.need_info()["aa_dir"]) if r["bundle"] == name and r["path_id"] == str(pid)), None)
        if not row:
            raise KeyError("no such image")
        return row

    def images_export(self, q, b):
        """One image at its true size: a PNG, or a zip (an SVG with its 8x PNG; an icon at all four UI scales)."""
        row = self._catalog_row(q)
        files = images.export_item(self.need_info()["aa_dir"], row)
        if len(files) == 1:
            return files[0][1], "image/png", files[0][0]
        import zipfile
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
            for rel, data in files:
                z.writestr(rel, data)
        return buf.getvalue(), "application/zip", images._safe(row["name"]) + ".zip"

    def images_export_all(self, q, b):
        """Export every catalog row matching the filter (group, kind, q, big) into <workspace>/exports/<time>/ as a job."""
        aa = self.need_info()["aa_dir"]
        rows = images.catalog(self.ws, aa)
        g, k, s, big = b.get("group", "all"), b.get("kind", "all"), str(b.get("q", "")).lower(), bool(b.get("big"))
        rows = [r for r in rows if (g == "all" or r["group"] == g) and (k == "all" or r["kind"] == k) and (not s or s in r["name"].lower())
                and (not big or r["kind"] != "texture" or r["w"] * r["h"] >= 640 * 360)]
        if not rows:
            raise ValueError("nothing matches the filter")
        dest = Path(self.ws.exports) / time.strftime("%Y%m%d-%H%M%S")
        return self.start_job("exporting %d images" % len(rows), lambda prog: images.export_all(aa, rows, dest, prog))

    def images_where(self, q, b):
        """Native skins: where a wallpaper swap is shown (see native.PLACES)."""
        p = project_mod.load(self.ws, b["project"])
        e = next((x for x in p.get("image_swaps", []) if x["bundle"] == b["bundle"] and x["path_id"] == str(b["path_id"])), None)
        if not e:
            raise ValueError("no such image swap")
        e["where"] = list(b["where"])
        project_mod.save(self.ws, project_mod.validate(project_mod.migrate(p)))
        return {"project": project_mod.load(self.ws, b["project"])}

    def native_info(self, q, b):
        root = native.skins_root()
        return {"places": {k: v[0] for k, v in native.PLACES.items()}, "skins_root": str(root) if root else None, "exists": bool(root and root.is_dir()),
                "installed": sorted(p.name for p in root.iterdir() if (p / "skin.json").is_file()) if root and root.is_dir() else []}

    def native_export(self, q, b):
        """Write the project as a native skin into the FM27 user folder's skins folder (or b['dest'])."""
        p = project_mod.load(self.ws, b["project"])
        root = Path(b["dest"]) if b.get("dest") else native.skins_root()
        if root is None:
            raise ValueError("no FM27 user folder found (Documents/Sports Interactive/Football Manager 27); give a destination folder")
        root.mkdir(parents=True, exist_ok=True)
        info = self.info or {}
        rep = native.export(self.ws, p, self.index, info.get("aa_dir"), root, b.get("id") or None, b.get("display") or None)
        self._backup_skin(rep, root)
        return rep

    def _backup_build(self, name, rep):
        """When config.json names skin_backup_dir, the build just made (its folder under build/<project>) is also copied to <dir>/<project>/bundles-<build id>/. Copy only: the build folder is not touched. Never fails the build."""
        dest = self.cfg.get("skin_backup_dir")
        d = patcher.latest_build(self.ws, name) if dest else None
        if not d:
            return
        try:
            target = Path(dest) / name / ("bundles-" + d.name)
            if not target.exists():
                shutil.copytree(d, target)
            rep["backup"] = str(target)
        except OSError as ex:
            rep["backup_error"] = str(ex)

    def _backup_skin(self, rep, root):
        """When config.json names `skin_backup_dir`, every skin written into the game's own skins folder is also copied there, a new dated folder each time. A failed backup never fails the save: it is said in the report."""
        dest = self.cfg.get("skin_backup_dir")
        if not dest or native.skins_root() is None or Path(root) != Path(native.skins_root()):
            return
        try:
            rep["backup"] = str(native.backup(rep["folder"], dest))
        except OSError as ex:
            rep["backup_error"] = str(ex)

    # ---- Simple mode: "Put it in the game" (docs/SIMPLE-MODE-PLAN.md S2). The native route only; no game file is written.
    def native_preflight(self, q, b):
        """What 'Put it in the game' would do, without doing it: the skin's name in the game, what it carries (empty = nothing changed yet), the skins folder, and whether this skin was put there before."""
        p = project_mod.load(self.ws, b["project"])
        root = native.skins_root()
        ch = native.changes(p)
        final = Path(root) / p["name"] if root else None
        first = not (final and (final / native.MARKER).is_file())
        return {"project": p["name"], "skin": p.get("native_name") or p["name"], "changes": ch, "has_changes": bool(ch), "skins_folder": str(root) if root else None,
                "skins_folder_found": bool(root), "folder": str(final) if final else None, "first_time": first}

    def native_put(self, q, b):
        """The job behind the button: check, write the native skin folder, check what was written. Progress messages are the words the centre indicator shows."""
        name = b["project"]

        def fn(prog):
            prog("Checking your skin", 0.1)
            p = project_mod.load(self.ws, name)
            if not native.changes(p):
                raise ValueError("this skin changes nothing yet: change a colour first")
            root = native.skins_root()
            if root is None:
                raise ValueError("no FM27 user folder found (Documents/Sports Interactive/Football Manager 27); give a destination folder")
            first = not ((Path(root) / p["name"] / native.MARKER).is_file())
            prog("Writing the skin into your skins folder", 0.4)
            rep = native.export(self.ws, p, self.index, (self.info or {}).get("aa_dir"), Path(root), None, None)
            self._backup_skin(rep, root)
            prog("Checking what was written", 0.85)
            problems = native.validate(rep["folder"])
            return {"project": p["name"], "skin": rep["skin"], "folder": rep["folder"], "first_time": first, "steps_left": native.steps_left(rep["skin"], first),
                    "tokens": rep["tokens"], "rules": rep["rules"], "images": rep["images"], "fonts": rep["fonts"], "skipped": rep["skipped"], "problems": list(rep["problems"]) + problems}
        return self.start_job("put it in the game", fn)

    # ---- S7: share and undo (skin_editor/share.py)
    def _game_build(self):
        return (self.ws.vanilla_manifest() or {}).get("game_build")

    def share_save(self, q, b):
        """Save the skin as one file (a zip of its native skin folder, with the versions inside)."""
        from . import share
        p = project_mod.load(self.ws, b["project"])
        return share.save(self.ws, p, self.index, (self.info or {}).get("aa_dir"), b["path"], b.get("studio_version"), self._game_build(), bool(b.get("overwrite")))

    def share_inspect(self, q, b):
        """What a downloaded skin file holds, before anything is made from it."""
        from . import share
        return share.inspect(b["path"], self._game_build())

    def share_open(self, q, b):
        """A downloaded skin file as a new project (a copy; nothing is put into the game)."""
        from . import share
        if b["name"] in project_mod.names(self.ws):
            raise RuntimeError("a project with that name exists")
        return share.open_copy(self.ws, b["path"], b["name"], self._game_build())

    def start_over_preview(self, q, b):
        """What "Start over" would take away, said before it is done."""
        from . import share
        p = project_mod.load(self.ws, b["project"])
        return {"project": p["name"], "lost": share.lost(p), "trash": str(self.ws.projects.parent / "trash")}

    def start_over(self, q, b):
        """Back to the game's look; the previous state goes to the workspace trash."""
        from . import share
        return share.start_over(self.ws, b["project"], b.get("confirm"), self._game_build())

    def native_remove(self, q, b):
        """Take a skin this editor put in the skins folder out again (only a folder with the editor's marker). The interface offers it only behind a setting until the in-game check has been run."""
        if b.get("confirm") is not True:
            raise ValueError("confirm is required to remove a skin folder")
        p = project_mod.load(self.ws, b["project"])
        root = native.skins_root()
        if root is None:
            raise ValueError("no FM27 user folder found (Documents/Sports Interactive/Football Manager 27); give a destination folder")
        return {"removed": native.remove(root, p["name"])}

    def open_folder(self, q, b):
        """Open an export folder in the file manager (inside the workspace's exports, or an exported native skin)."""
        f = Path(b["path"]).resolve()
        roots = [Path(self.ws.exports).resolve()] + ([native.skins_root().resolve()] if native.skins_root() else [])
        if not any(r in [f, *f.parents] for r in roots) or not f.is_dir():
            raise ValueError("only export folders can be opened")
        if sys.platform == "win32":
            os.startfile(str(f))
        elif sys.platform == "darwin":
            subprocess.Popen(["open", str(f)])
        else:
            subprocess.Popen(["xdg-open", str(f)])
        return {"opened": str(f)}

    def images_remove(self, q, b):
        p = project_mod.load(self.ws, b["project"])
        keep, gone = [], []
        for e in p.get("image_swaps", []):
            (gone if e["bundle"] == b["bundle"] and e["path_id"] == str(b["path_id"]) else keep).append(e)
        if not gone:
            raise ValueError("no such image swap")
        p["image_swaps"] = keep
        project_mod.save(self.ws, p)
        for e in gone:
            f = project_mod.images_dir(self.ws, b["project"]) / e["source"]
            if f.is_file() and not any(x["source"] == e["source"] for x in keep):
                f.unlink()
        return {"project": project_mod.load(self.ws, b["project"])}

    def do_verify(self, q, b):
        ev = preview.evaluate(preview.load(q["model"]), self.index, self._preview_project(q))
        return verify.compare(preview.verify_regions(ev), b, self.cfg["verify"]["tolerance_rgb"])


