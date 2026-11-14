"""The render call: a layout -> render tree with computed styles, plus what the render cannot know."""
import time

from . import cascade as cascade_mod
from . import delivered as delivered_mod
from . import overlay
from .html import flatten, font_label, load_text_metrics, percent_main_axis_rule, placeholder_kind, placeholder_text, style_dict, switch_branch_rule
from .assets import AssetResolver, Drawn, apply_assets
from .layouts import LayoutStore
from .sheets import GAPS, ROOT_SHEETS, SheetBank

FLAG_ORDER = ("unknown", "unmapped", "partial")          # worst first; mapped, variable and shorthand are not flagged


def worst_flag(node):
    present = {d["status"] for d in node["computed"].values()}
    return next((s for s in FLAG_ORDER if s in present), None)

NOTICE = ("Approximation, not the game's renderer: bindings and data render as placeholders, there are no hover or animation states, code-bound visuals are "
          "approximated, and the sheets and runtime classes listed under `gaps` are not applied.")


class Renderer:
    def __init__(self, folder, cache_dir=None, style_index=None, runtime_classes=None):
        self.layouts = LayoutStore(folder, cache_dir)
        self.bank = SheetBank(folder, cache_dir, style_index)
        self._rc = runtime_classes
        self._cascade = None
        self._skin = {}                      # project name -> (project hash, Cascade, notes): the cascade with that project's edits, dropped by invalidate()
        self._metrics = load_text_metrics()
        self._assets = AssetResolver(folder, cache_dir) if cache_dir else None      # M4: asset(F:P) values; none without a cache folder
        self._drawn = Drawn(self._assets) if self._assets else None

    def layout_list(self, q="", limit=200):
        """Layouts for the browser: name, bundle, path id and element count, filtered by a case-insensitive substring of the name, shortest names first."""
        ql = (q or "").strip().lower()
        rows = [{"name": r["name"], "bundle": r["bundle"], "path_id": r["path_id"], "elements": r["elements"]}
                for r in self.layouts.catalog() if not ql or ql in r["name"].lower()]
        rows.sort(key=lambda r: (len(r["name"]), r["name"]))
        return {"total": len(rows), "layouts": rows[:max(1, min(int(limit or 200), 1000))]}

    def cascade(self):
        if self._cascade is None:
            self._cascade = cascade_mod.Cascade(self.bank.ordered(), self._rc)
        return self._cascade

    def invalidate(self, project=None):
        """Drop the cached skin cascade of one project (or of all): the next render with that project is built again."""
        if project is None:
            self._skin.clear()
        else:
            self._skin.pop(project, None)

    def skin_cascade(self, p):
        """(Cascade, notes) with the project's edits applied to in-memory copies of the sheets; cached per project and rebuilt when its content hash changes."""
        h = overlay.project_hash(p)
        hit = self._skin.get(p["name"])
        if not hit or hit[0] != h:
            sheets, notes = overlay.build_sheets(self.bank, p)
            hit = (h, cascade_mod.Cascade(sheets, self._rc), notes)
            self._skin[p["name"]] = hit
        return hit[1], hit[2]

    def layout(self, bundle, path_id, depth=3, branches=None, project=None, delivered=None):
        t0 = time.perf_counter()
        notes, applied = [], 0
        if project is not None:
            c, notes = self.skin_cascade(project)
        else:
            c = self.cascade()
        t1 = time.perf_counter()
        tree = self.layouts.expand(bundle, path_id, depth)
        t2 = time.perf_counter()
        top = tree["children"]
        if project is not None:
            applied, pnotes = overlay.apply_layout_patches(top, project.get("layout_patches"))
            notes = notes + pnotes
        summary = c.compute(top)
        asset_counts = None
        if self._assets:
            sheet_bundles = {n: b for b, n, _w in ROOT_SHEETS}
            sheet_bundles.update({s['name']: s['bundle'] for s in (self.bank.ix.sheets if self.bank.ix is not None else [])})
            asset_counts = apply_assets(top, self._assets, bundle, sheet_bundles, self._drawn)
        switch_branch_rule(top, branches)
        delivered_report = delivered_mod.apply(top, delivered) if delivered else None      # M7: captured text for the nodes it pairs with, by structural path                             # one branch per switch, the rest not drawn and said so
        percent_main_axis_rule(top)                                   # a game rule CSS does not share (html.py); notes each node it changes in `layout_rules`
        for n in flatten(top):
            n["style"] = style_dict(n, self._metrics)               # what draws the element (mapped and partial properties only)
            n["text"] = placeholder_text(n)
            n["placeholder"] = placeholder_kind(n)                      # set | sample | empty: bound text is labelled, never passed off as data
            n["font"] = font_label(n)                                    # the family the game uses for this text (named, drawn with the stand-in font)
            n["flag"] = worst_flag(n)                                  # the worst status among its properties, for the marker; the explain panel lists them all
            n["runtime_classes"] = [x for x in n["_classes"] if x not in n["classes"]]
        t3 = time.perf_counter()
        includes = []

        def walk(n):
            if n.get("include"):
                includes.append(dict(n["include"], name=n.get("name")))
            for k in n.get("children", []):
                walk(k)
        for n in top:
            walk(n)
        return {"layout": tree["layout"], "bundle": bundle, "path_id": str(path_id), "notice": NOTICE, "tree": top, "includes": includes, "summary": summary, "assets": asset_counts, "delivered": delivered_report,
                "overlay": ({"project": project["name"], "hash": overlay.project_hash(project), "output": (project.get("options") or {}).get("output", "bundles"),
                             "layout_patch_ops_applied": applied, "notes": notes, "not_applied": overlay.NOT_APPLIED} if project is not None else None),
                "sheet_order": [{"position": i, "bundle": b, "sheet": n, "why": why} for i, (b, n, why) in enumerate(ROOT_SHEETS)],
                "gaps": GAPS + (["%d selectors with runtime states (%s) are not applied" % (c.stats["state_selectors_skipped"],
                                                                                          ", ".join("%s %d" % kv for kv in c.stats["state_pseudo_classes"].items()))]
                                if c.stats["state_selectors_skipped"] else []),
                "cascade_stats": c.stats, "store_stats": dict(self.layouts.stats),
                "timing_ms": {"cascade_ready": round((t1 - t0) * 1000, 1), "expand": round((t2 - t1) * 1000, 1), "compute": round((t3 - t2) * 1000, 1),
                              "total": round((t3 - t0) * 1000, 1)}}
