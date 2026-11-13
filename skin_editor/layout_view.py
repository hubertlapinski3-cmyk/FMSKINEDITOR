"""Read-only views of the layout dump for the Layout tab: screen browser, element outline, composition and cell views.

Built on LayoutData (the same join pipeline: areas, screens_of, cycle handling). Pure reads: nothing here edits anything.
There is no geometry in the dump: grid coordinates are cell units of a composition, not pixels. Strings (flags, alignments,
conditions, layout mode, preset name) are returned verbatim."""
from .layout_join import UNASSIGNED, VERIFIED, RUNTIME

OUTLINE_CAP = 600
NOTE = ("Structure only: the layout dump has no geometry, so nothing here is a position on screen. Grid x, y, w, h are cell units of a "
        "composition. Results are a lower bound (no template or table-factory references).")


class View:
    def __init__(self, ld):
        self.ld, d = ld, ld.dump
        self.els, self.inc, self.tiles, self.kids = {}, {}, {}, {}
        for e in d["elements"]:
            self.els.setdefault(e["layout_id"], []).append(e)
        for v in self.els.values():
            v.sort(key=lambda e: (e["ord"], e["local_id"]))
        for i in d["includes"]:
            self.inc.setdefault((i["from_layout_id"], i["element_local_id"]), []).append((i["to_layout_id"], i["alias"]))
            self.kids.setdefault(i["from_layout_id"], set()).add(i["to_layout_id"])
        for t in d["tiles"]:
            self.tiles.setdefault(t["panel_layout_id"], []).append(t)
            self.kids.setdefault(t["panel_layout_id"], set()).add(t["tile_layout_id"])
        self.comps = {c["name"]: c for c in d["compositions"]}
        self.cells, self.cfgs = {}, {}
        for c in d["cells"]:
            self.cells.setdefault(c["composition"], []).append(c)
        for v in self.cells.values():
            v.sort(key=lambda c: c["cell_index"])
        for c in d["cell_configs"]:
            self.cfgs.setdefault((c["composition"], c["cell_index"]), []).append(c)
        for v in self.cfgs.values():
            v.sort(key=lambda c: c["cfg_index"])
        self.panels = {p["panel_id"]: p["layout_id"] for p in d["panels"]}

    def _lay(self, lid):
        return {"layout_id": lid, "layout": self.ld.layouts[lid]["name"], "area": self.ld.area_of(lid)}

    def reach_down(self, layout_id):
        """Layout ids below this one through includes and tiles (iterative, visited set: cycles terminate). Includes the start."""
        seen, stack = {layout_id}, [layout_id]
        while stack:
            for k in self.kids.get(stack.pop(), ()):
                if k not in seen:
                    seen.add(k); stack.append(k)
        return seen

    def by_area(self, layout_ids):
        out = {}
        for lid in layout_ids:
            a = self.ld.area_of(lid)
            out[a] = out.get(a, 0) + 1
        return dict(sorted(out.items()))

    # ---- screen browser
    def screens(self, area=None, q=""):
        ql = q.strip().lower()
        rows = []
        for pid, lid in sorted(self.panels.items()):
            a = self.ld.area_of(lid)
            name = self.ld.layouts[lid]["name"]
            if area and a != area:
                continue
            if ql and ql not in pid.lower() and ql not in name.lower():
                continue
            tiles = [t for r in self.reach_down(lid) for t in self.tiles.get(r, ())]          # grids of the layouts the screen includes count too
            rows.append({"panel_id": pid, "layout_id": lid, "layout": name, "area": a, "elements": len(self.els.get(lid, ())),
                         "tiles": len(tiles), "sets": len({(t["panel_layout_id"], t["set_name"]) for t in tiles})})
        every = {}
        for lid in self.panels.values():
            every[self.ld.area_of(lid)] = every.get(self.ld.area_of(lid), 0) + 1
        return {"note": NOTE, "total": len(self.panels), "shown": len(rows), "screens": rows,
                "by_area": dict(sorted(every.items())), "layouts": len(self.ld.layouts),
                "layouts_by_area": self.by_area(list(self.ld.layouts))}

    def screen(self, panel_id):
        if panel_id not in self.panels:
            raise KeyError("no such panel: " + panel_id)
        lid = self.panels[panel_id]
        reach = self.reach_down(lid)
        # In the game's data a grid belongs to the layout that hosts it, usually a template the panel includes, not to the panel's root layout:
        # the sets of a screen are those of every layout it reaches (the root first), each tagged with its host.
        order = [lid] + sorted((r for r in reach if r != lid), key=lambda r: self.ld.layouts[r]["name"])
        sets = []
        for host in order:
            for s in self._sets(host):
                sets.append(dict(s, host=self._lay(host)))
        out = dict(self._lay(lid), panel_id=panel_id, note=NOTE, elements=len(self.els.get(lid, ())),
                   reach={"layouts": len(reach), "by_area": self.by_area(reach)}, sets=sets)
        return out

    def _sets(self, lid):
        sets = {}
        for t in self.tiles.get(lid, []):
            v = sets.setdefault(t["set_name"], {}).setdefault((t["breakpoint"], t["variant_idx"], t["composition"]), {})
            v[t["cell_index"]] = t
        out = []
        for sname, variants in sorted(sets.items()):
            vs = []
            for (bp, vi, comp), placed in sorted(variants.items()):
                c = self.comps.get(comp)
                cells = []
                for cell in self.cells.get(comp, []):
                    cfgs = self.cfgs.get((comp, cell["cell_index"]), [])
                    p = placed.get(cell["cell_index"])
                    cells.append({"cell_index": cell["cell_index"], "element_id": cell["element_id"],
                                  "x": cell["x"], "y": cell["y"], "w": cell["w"], "h": cell["h"],
                                  "min_w": cell["min_w"], "min_h": cell["min_h"], "max_w": cell["max_w"], "max_h": cell["max_h"],
                                  "flags": list(cell["flags"]), "h_align": cell["h_align"], "v_align": cell["v_align"],
                                  "configs": [dict(self._lay(g["tile_layout_id"]), cfg_index=g["cfg_index"], size_w=g["size_w"], size_h=g["size_h"]) for g in cfgs],
                                  "placed": None if p is None else dict(self._lay(p["tile_layout_id"]), cfg_index=p["cfg_index"], size=p["size"])})
                vs.append({"breakpoint": bp, "variant_idx": vi, "composition": comp,
                           "composition_info": None if c is None else {k: (list(c[k]) if isinstance(c[k], list) else c[k]) for k in
                                                                         ("layout_mode", "preset_name", "preset_w", "preset_h", "instantiation_order", "conditions")},
                           "cells": cells})
            out.append({"set_name": sname, "variants": vs})
        return out

    # ---- outline: one layout's element tree, one include level at a time
    def outline(self, layout_id, ancestry=(), q="", cap=OUTLINE_CAP):
        """ancestry: layout ids already opened on the way here. An include whose target is the layout itself or is in the ancestry is
        flagged `cycle` and is not expandable (cycle guard)."""
        if layout_id not in self.ld.layouts:
            raise KeyError("no such layout id: %s" % layout_id)
        els = self.els.get(layout_id, [])
        chain = tuple(ancestry) + (layout_id,)
        ql = q.strip().lower()
        by_local = {e["local_id"]: e for e in els}
        keep = None
        if ql:
            hit = {e["local_id"] for e in els if ql in e["name"].lower() or any(ql in c.lower() for c in e["classes"]) or any(ql in c.lower() for c in e.get("runtime_classes", ()))}
            keep = set(hit)
            for lid in hit:                      # ancestors of a match stay visible so the match has its context
                p = by_local[lid]["parent_local_id"]
                while p is not None and p not in keep:
                    keep.add(p); p = by_local[p]["parent_local_id"]
            matches = len(hit)
        else:
            matches = None
        nodes, root, total, truncated = {}, [], 0, False
        for e in els:
            if keep is not None and e["local_id"] not in keep:
                continue
            total += 1
            if total > cap:
                truncated = True
                continue
            p = e["parent_local_id"]
            if p is not None and p not in nodes:        # its parent was cut by the cap: the branch is not shown
                truncated = True
                continue
            incs = []
            for to, alias in self.inc.get((layout_id, e["local_id"]), ()):
                incs.append(dict(self._lay(to), alias=alias, cycle=to in chain))
            n = {"local_id": e["local_id"], "type": e["type"].split(".")[-1], "name": e["name"],
                 "classes": [{"name": c, "state": VERIFIED} for c in e["classes"]],
                 "runtime_classes": [{"name": c, "state": RUNTIME} for c in e.get("runtime_classes", ()) if c not in e["classes"]],
                 "includes": incs, "match": bool(keep is not None and e["local_id"] in hit), "children": []}
            nodes[e["local_id"]] = n
            (nodes[p]["children"] if p in nodes else root).append(n)
        return dict(self._lay(layout_id), ancestry=list(ancestry), total=total, shown=min(total, cap), truncated=truncated, cap=cap,
                    matches=matches, tree=root, note=NOTE)