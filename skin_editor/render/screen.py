"""M3 screen assembly: a composition's cells placed on the grid of a panel, each cell resolved to its tile layout (docs/PHASE9-PLAN.md section 5).

Everything here is a MODEL FITTED TO CAPTURES (Squad overview at Large on two panel sizes; Team Instructions at Large), stated as such. Facts it rests on, from the
inspector captures of 2026-11-14 (docs/evidence/phase9-m3-session-D-20261114.md):
- the grid container holds absolutely positioned hosts; each host's inline px is `left = 12 + 82 * column`, `top = 12 + 82 * row`, `width = 82 * n - 16`, `height = 82 * m - 16`
  (stride 82 = cell + gap; measured, `pitch.json`); 12 px is the container padding;
- the grid has `round((extent - 24 + 16) / 82)` columns and rows: the grid follows the PANEL, not the composition;
- a composition is designed for `cols0 x rows0` (the extent of its cells); on a bigger grid, a cell whose right edge touches the composition's right edge moves right by the
  extra columns, a flexible cell (max size 100) grows by the extra columns / rows, a fixed cell keeps its size and its rows. Fitted to: Squad Large (20 x 10 on a 30 x 16 grid and on a
  25 x 13 grid), Team Instructions Large (20 x 9 on a 29 x 15 grid with a 4 column strip reserved on the right for tiles the composition does not hold).
What it does NOT know, and says so: how the game picks the composition (the breakpoint follows the grid size; only Large is measured), who adds extra slots and in what order
(`runtime_slots` carries them as placeholders, from the capture's hosts), and which tile config a flexible cell takes (the largest config that fits is used, flagged)."""
from . import pitch as pitch_mod

PADDING = 12


def grid_dims(width, height, p, padding=PADDING):
    """(columns, rows) of a grid container of `width` x `height` px: the number of strides that fit once the padding is out. The padding is a property of the grid
    container: 12 px on the Squad overview grid and the Team Instructions body grid, 0 on the Team Instructions tab grid (its hosts start at left 0, top 0)."""
    s = pitch_mod.stride(p)
    return max(1, round((width - 2 * padding + p["gap"]) / s)), max(1, round((height - 2 * padding + p["gap"]) / s))


def cell_px(col, row, w, h, padding=PADDING):
    """The inline px a host gets: the game writes whole-pixel strides of 82 and a 16 px gap (the measured gap is 15.5 to 16.5 in world units)."""
    return {"left": padding + 82 * col, "top": padding + 82 * row, "width": 82 * w - 16, "height": 82 * h - 16}


class Assembler:
    def __init__(self, dump):
        self.d = dump
        self.cells, self.layouts = {}, {l["id"]: l for l in dump["layouts"]}
        for c in dump["cells"]:
            self.cells.setdefault(c["composition"], []).append(c)
        self.tiles = {}
        for t in dump["tiles"]:
            self.tiles.setdefault((t["composition"], t["cell_element_id"]), []).append(t)

    def design_size(self, composition):
        cs = self.cells[composition]
        return max(c["x"] + c["w"] for c in cs), max(c["y"] + c["h"] for c in cs)

    def place(self, composition, cols, rows, reserved_right=0):
        """{element_id: {col,row,w,h,mode}} for the composition's cells on a cols x rows grid, `reserved_right` columns held back on the right for slots the composition lacks."""
        c0, r0 = self.design_size(composition)
        dx, dy = (cols - reserved_right) - c0, rows - r0
        out = {}
        for c in self.cells[composition]:
            flex_w, flex_h = c["max_w"] >= 100 or c["max_w"] == 0, c["max_h"] >= 100 or c["max_h"] == 0
            right = c["x"] + c["w"] == c0
            col, w = c["x"], c["w"]
            mode = []
            if flex_w:
                w += dx
                mode.append("flexible width")
            elif right:
                col += dx
                mode.append("right-anchored")
            row, h = c["y"], c["h"]
            if flex_h and c["h"] >= 5:
                h += dy
                mode.append("flexible height")
            out.setdefault(c["element_id"], {"col": col, "row": row, "w": w, "h": h, "mode": mode or ["fixed"]})
        return out

    def tile_for(self, composition, element_id, w, h):
        """The tile layout name for a placed cell: the config of exactly that size, else the largest config that fits (flagged)."""
        recs = self.tiles.get((composition, element_id), [])
        if not recs:
            return None, "no tile record for this cell in the layout index"
        exact = [t for t in recs if (t["size"]["w"], t["size"]["h"]) == (w, h)]
        if exact:
            return self.layouts[exact[0]["tile_layout_id"]]["name"], "config of exactly this size"
        fit = sorted((t for t in recs if t["size"]["w"] <= w and t["size"]["h"] <= h), key=lambda t: -(t["size"]["w"] * t["size"]["h"]))
        if fit:
            return self.layouts[fit[0]["tile_layout_id"]]["name"], "largest config that fits (%dx%d), ASSUMED" % (fit[0]["size"]["w"], fit[0]["size"]["h"])
        return None, "no config fits"

    def assemble(self, composition, area, composition_pitch=None, reserved_right=0, runtime_slots=(), padding=PADDING):
        """The screen: grid, placed cells with px boxes (relative to the grid container), tile layouts, and the slots the composition does not hold.
        `area` is the grid container's size in px (the screen chrome around it is not modelled)."""
        p = pitch_mod.lookup(composition_pitch or composition)
        cols, rows = grid_dims(area[0], area[1], p, padding)
        placed = self.place(composition, cols, rows, reserved_right)
        hosts = []
        for eid, g in placed.items():
            layout, how = self.tile_for(composition, eid, g["w"], g["h"])
            hosts.append(dict(g, element_id=eid, px=cell_px(g["col"], g["row"], g["w"], g["h"], padding), tile_layout=layout, tile_how=how))
        extra = [dict(s, px=cell_px(s["col"], s["row"], s["w"], s["h"], padding), placeholder="run-time-added slot: not in the composition, tile chosen by the game") for s in runtime_slots]
        return {"composition": composition, "pitch": p, "grid": {"columns": cols, "rows": rows}, "hosts": hosts, "runtime_slots": extra,
                "flags": ([p["flag"]] if p["flag"] else []) + (["tile configs chosen by the largest-fit assumption: " + h["element_id"] for h in hosts if "ASSUMED" in (h["tile_how"] or "")])}
