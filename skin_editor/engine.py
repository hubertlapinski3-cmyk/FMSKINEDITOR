"""The engine: every operation of the editor as a method of one object, with no transport code. The HTTP server (server.py),
the JSON-RPC API (api/) and the CLI are clients of it. Methods keep the (q, b) signature of the original routes: q = string
parameters, b = a JSON object or raw bytes; api/methods.py gives each one a name and a parameter schema."""
import io
import copy
import json
import os
import re
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
        info = self.need_info()
        return detect.game_running(info, self.cfg["process_names"]) or detect.steam_updating(info)

    def start_job(self, label, fn):
        """Queue fn(progress) as a job; returns its legacy view ({running, label, progress, error, result, id}). Jobs run one at
        a time in submission order (they share the workspace and UnityPy is not re-entrant)."""
        return self.jobs.submit(label, fn).legacy()

    @property
    def job(self):
        """The most recently submitted job in the shape the first frontend polls."""
        return self.jobs.latest_legacy()

    # ---- routes
    def state(self, q, b):
        info = self.info
        return {"install": info, "candidates": getattr(self, "candidates", None),
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
        return layout_dump.state(self.ws)

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
    # overridable (FM27_LAYOUT_INDEX, FM27_LAYOUT_AREAS); the defaults are the owner's FM27_LayoutMCP checkout
    LAYOUT_INDEX = os.environ.get("FM27_LAYOUT_INDEX") or r"C:\Users\Admin\Downloads\FM27_LayoutMCP\index\layout-vanilla.sqlite"
    LAYOUT_AREAS = os.environ.get("FM27_LAYOUT_AREAS") or r"C:\Users\Admin\Downloads\FM27_LayoutMCP\config\areas.json"

    def layout_export(self, q, b):
        """Build the fmlayout-index/2 dump from the FM27_LayoutMCP sqlite index and the game's composition bundles, cross-check every cell against
        its bundle, and import it (the import decides fresh / stale / contaminated from the bundle hashes). Read-only on the index and the game."""
        from . import layout_export
        aa = self.need_info()["aa_dir"]
        path = b.get("index") or self.LAYOUT_INDEX
        db = layout_export.connect(path)
        cc = layout_export.crosscheck(db, aa)
        if cc["mismatches"]:
            raise RuntimeError("the index does not match the game's composition bundles (%d mismatch(es), e.g. %s); rebuild the index" % (len(cc["mismatches"]), cc["mismatches"][0]))
        from . import profile
        build = b.get("game_build") or (profile.active_profile(self.ws) or {}).get("game_build") or "unknown"
        d = layout_export.build_dump(path, aa, build, b.get("areas") or self.LAYOUT_AREAS)
        r = layout_dump.import_bytes(self.ws, json.dumps(d).encode("utf-8"), "layout index " + time.strftime("%Y-%m-%d"))
        self._ld = (None, None)
        return {"imported": r, "crosscheck": {"compositions": cc["compositions"], "cells": cc["cells"], "mismatches": 0}, "state": layout_dump.state(self.ws)}

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
        t = install.tamper_status(self.ws, aa)
        bad = [n for n, s in (t.get("files") or {}).items() if n in (tables.VIEWS_BUNDLE, tables.FACTORIES_BUNDLE) and s != "stock"]
        if bad or t.get("state") == "game_updated":
            raise RuntimeError("the game's table bundles are not stock (%s); restore them or take a new snapshot" % (", ".join(bad) or t.get("message", "")))
        return tables.Tables(aa, gn)

    def tables_list(self, q, b):
        rows = self._tables().list(str(b.get("q", "")))
        return {"total": len(rows), "views": rows[: int(b.get("limit") or 300)]}

    def tables_usage(self, q, b):
        """Where table views are used: read the FM27_LayoutMCP index (read-only), decode the view GUIDs out of the layouts' InitFunction arguments,
        and keep the result in the workspace (table-view-usage.json) so `tables.view` can say which layout and tile show a view."""
        from . import table_usage, profile
        db = table_usage.connect(b.get("index") or self.LAYOUT_INDEX)
        usage = table_usage.build(db)
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
        t = install.tamper_status(self.ws, aa)
        bad = [n for n, s in (t.get("files") or {}).items() if n.startswith("ui-visualtreeassets") and s != "stock"]
        if t.get("state") in ("modified", "game_updated") and bad or t.get("state") == "game_updated":
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
        t = install.tamper_status(self.ws, str(aa))
        bad = [n for n, s in (t.get("files") or {}).items() if n.startswith("ui-visualtreeassets") and s != "stock"]
        if t.get("state") == "game_updated" or (t.get("state") == "modified" and bad):
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
        moves = []
        if b.get("project") and b.get("skin", True):
            from . import tiles
            moves = tiles.ops_for(self.ws, b["project"])
        d = layout_dump.load(self.ws)
        if d is None:
            raise RuntimeError("no layout dump is imported")
        return screen.Assembler(d).assemble(b["composition"], (float(b["width"]), float(b["height"])), reserved_right=int(b.get("reserved_right") or 0),
                                            padding=int(b.get("padding") if b.get("padding") is not None else 12), moves=moves)

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

    # ---- live preview loop (native skins/<id>-preview + inspector pipe; never touches bundles)
    def inspector_status(self, q, b):
        from . import inspector
        try:
            return {"online": True, **inspector.status()}
        except inspector.Offline as ex:
            return {"online": False, "reason": str(ex)}

    def preview_live(self, q, b):
        from . import live
        p = project_mod.load(self.ws, b["project"])
        return live.run(self.ws, p, self.index, (self.info or {}).get("aa_dir"))

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

        def fn(prog):
            from . import tiles as tiles_mod
            aa = (self.info or {}).get("aa_dir")
            for bn in sorted({o["bundle"] for o in tiles_mod.ops_for(self.ws, p["name"])}):     # a position edit needs its composition bundle in the snapshot
                if aa:
                    install.add_image_bundle(self.ws, aa, bn)
            rep = patcher.build(p, self.ws, ix, game_dir, self.cfg["build"]["keep_last_builds"], prog)
            rep.pop("spec")
            rep["literal_hits"] = rep["literal_hits"][:200]
            return rep
        return self.start_job("building", fn)

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
                               self.cfg["install"]["backup_keep"])

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
        return native.export(self.ws, p, self.index, info.get("aa_dir"), root, b.get("id") or None, b.get("display") or None)

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


