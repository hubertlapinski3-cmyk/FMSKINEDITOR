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
from . import one_rule

# GridLayoutSettings (globalobjects_assets_all.bundle, path_id=7732983250881643699):
#   m_cellSize = (66, 66), m_padding = (12, 12), m_spacing = (16, 16)
CELL_SIZE = 66
SPACING = 16
PADDING = 12
STRIDE = CELL_SIZE + SPACING


def grid_dims(width, height, p, padding=PADDING):
    """(columns, rows) of a grid container of `width` x `height` px: the number of strides that fit once the padding is out. The padding is a property of the grid
    container: 12 px on the Squad overview grid and the Team Instructions body grid, 0 on the Team Instructions tab grid (its hosts start at left 0, top 0)."""
    s = pitch_mod.stride(p)
    return max(1, round((width - 2 * padding + p["gap"]) / s)), max(1, round((height - 2 * padding + p["gap"]) / s))


def grid_dims_content(content_width, content_height, padding=PADDING, cell_size=CELL_SIZE, spacing=SPACING):
    """A2: grid dimensions from measured GridLayoutElementContent extent: round((extent - 2 * padding + spacing) / (cellSize + spacing)).

    Squad content 2468.8x1319.3 -> 30x16; PlayerReport content 2468.8x1074.2 -> 30x13.
    """
    stride = cell_size + spacing
    return (max(1, int(round((content_width - 2 * padding + spacing) / stride))),
            max(1, int(round((content_height - 2 * padding + spacing) / stride))))


def grid_size_uncertain(content_width, content_height, padding=PADDING, cell_size=CELL_SIZE, spacing=SPACING):
    """True when width or height lands within 1 px of a round() column/row boundary."""
    stride = float(cell_size + spacing)
    for ext in (content_width, content_height):
        val = (float(ext) - 2 * padding + spacing) / stride
        if abs((val % 1.0) - 0.5) * stride <= 1.0:
            return True
    return False




# J1: measured content rects (left, top, width, height) for the two screens with measurements.
PANEL_CONTENT_RECTS = {
    "SquadScreen": (0.0, 0.0, 2468.8, 1319.3),          # existing measurements (content extent only)
    "PlayerReport": (15.6, 273.4, 2468.8, 1074.2),      # H2/I2
}



def cell_px(col, row, w, h, padding=PADDING):
    """The inline px a host gets: the game writes whole-pixel strides of 82 and a 16 px gap (the measured gap is 15.5 to 16.5 in world units)."""
    return {"left": padding + 82 * col, "top": padding + 82 * row, "width": 82 * w - 16, "height": 82 * h - 16}


def pack_rows(items):
    """The runtime's cell placement rule (Test C+D, 2026-11-20): cells are PACKED vertically inside their
    column, not clamped to the design edge. `items` are dicts with x, w, y, h, cell_index (and element_id).
    Cells sharing an x and width are one column; they are ordered by their serialized y (then cell_index) and
    laid out contiguously from the column's first y, each keeping its height. Test D alone: a cell at y=12
    lands at row 10 under the stock 2-row Atmosphere; with C's 4-row Atmosphere it lands at row 12. Returns a
    new list of copies with the packed y; the input is not changed."""
    from collections import defaultdict
    groups = defaultdict(list)
    for it in items:
        groups[(it.get("x"), it.get("w"))].append(dict(it))
    out = []
    for key in sorted(groups, key=lambda k: (k[0] if k[0] is not None else -1, k[1] if k[1] is not None else -1)):
        group = sorted(groups[key], key=lambda c: (c.get("y") or 0, c.get("cell_index") if c.get("cell_index") is not None else -1))
        if not group:
            continue
        row = min((c.get("y") or 0) for c in group)
        for c in group:
            c["y"] = row
            row += c.get("h") or 0
            out.append(c)
    return out


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

    def place(self, composition, cols, rows, reserved_right=0, moves=(), adds=()):
        """{element_id: {col,row,w,h,mode}} for the composition's cells on a cols x rows grid, `reserved_right` columns held back on the right for slots the composition lacks.
        Cells are PACKED vertically per column (see pack_rows; Test C+D) and only then flexed/anchored. `adds`
        are effective added cells (candidate AddCell placements) with element_id, geometry and cell_index."""
        c0, r0 = self.design_size(composition)
        dx, dy = (cols - reserved_right) - c0, rows - r0
        moved = {o["cell_id"]: o["to"] for o in moves if o.get("composition") == composition}        # project tile moves (placement store): a cell's position in the design
        items = []
        for c in self.cells[composition]:
            e = dict(c)
            if e["element_id"] in moved:
                t = moved[e["element_id"]]
                e["x"], e["y"] = t["x"], t["y"]
                if t.get("w") is not None:
                    e["w"] = t["w"]
                if t.get("h") is not None:
                    e["h"] = t["h"]
                e["_moved"] = True
            e["_right"] = c["x"] + c["w"] == c0                                                     # anchoring is judged on the cell's ORIGINAL position
            e["_flex_w"] = c["max_w"] >= 100 or c["max_w"] == 0
            e["_flex_h"] = c["max_h"] >= 100 or c["max_h"] == 0
            items.append(e)
        for a in adds:
            g = a.get("geometry") or {}
            pid = a.get("cell_index")
            items.append({"element_id": a.get("element_id"), "cell_index": pid, "x": g.get("x"), "y": g.get("y"),
                          "w": g.get("w"), "h": g.get("h"), "max_w": g.get("w"), "max_h": g.get("h"),
                          "_right": g.get("x") is not None and g.get("w") is not None and g["x"] + g["w"] == c0,
                          "_flex_w": False, "_flex_h": False, "_added": True})
        out = {}
        for c in pack_rows(items):
            col, w = c["x"], c["w"]
            mode = []
            if c["_flex_w"]:
                w += dx
                mode.append("flexible width")
            elif c["_right"]:
                col += dx
                mode.append("right-anchored")
            row, h = c["y"], c["h"]
            if c["_flex_h"] and c["h"] >= 5:
                h += dy
                mode.append("flexible height")
            if c.get("_added"):
                mode.append("added cell (candidate)")
            elif c.get("_moved"):
                mode.append("moved by the project")
            out.setdefault(c["element_id"], {"col": col, "row": row, "w": w, "h": h, "mode": (mode or ["fixed"])})
        return out

    def place_expanding(self, composition, cols, rows):
        """J1 HYPOTHESIS (measured on PlayerReport only): m_reflowMode 0 layouts grow the bottom band.

        Widths: each band cell grows to its m_maxSize width and packs left-to-right in design order; the
        attributes cell (y 0) takes the full grid width. Heights: the extra rows are shared by the design bands
        in proportion to their design height with largest remainder; the bottom band is anchored to the last row.
        """
        cs = sorted(self.cells[composition], key=lambda c: (c["y"], c["x"], c["cell_index"]))
        bands = {}
        for c in cs:
            bands.setdefault(c["y"], []).append(c)
        base = sum(max(c["h"] for c in v) for v in bands.values()) or 1
        extra = max(0, rows - base)
        alloc, rem = {}, {}
        for y, v in bands.items():
            h = max(c["h"] for c in v)
            q = extra * h / base
            alloc[y] = int(q)
            rem[y] = q - alloc[y]
        while sum(alloc.values()) < extra:
            y = max(rem, key=rem.get)
            alloc[y] += 1
            rem[y] -= 1
        out = {}
        ypos = 0
        # AA1: x and width come from the design position plus the growth of the cells to the left (one_rule.columns_rule).
        # The old per-band left-to-right packing restarted every band at column 0 and could push a cell past the grid.
        colw = one_rule.columns_rule([dict(c) for c in cs], cols, self.design_size(composition)[0])
        for y in sorted(bands):
            bh = max(c["h"] for c in bands[y]) + alloc.get(y, 0)
            for c in sorted(bands[y], key=lambda c: (c["x"], c["cell_index"])):
                col, w = colw[c["element_id"]]
                out[c["element_id"]] = {"col": col, "row": ypos, "w": w, "h": bh,
                                        "mode": ["expanding (m_reflowMode 0, HYPOTHESIS)"]}
            ypos += bh
        return out

    def place_growth(self, composition, cols, rows):
        """J5 hypothesis (not wired): only cells whose max > design grow; fixed cells keep size and shift."""
        cs = sorted(self.cells[composition], key=lambda c: (c["y"], c["x"], c["cell_index"]))
        bands = {}
        for c in cs:
            bands.setdefault(c["y"], []).append(c)
        design_rows = max(c["y"] + c["h"] for c in cs)
        extra = max(0, rows - design_rows)
        grow_bands = {y: v for y, v in bands.items() if any((c.get("max_w") or c["w"]) > c["w"] or
                                                           (c.get("max_h") or c["h"]) > c["h"] for c in v)}
        base = sum(max(c["h"] for c in v) for v in grow_bands.values()) or 1
        alloc, rem = {}, {}
        for y, v in grow_bands.items():
            h = max(c["h"] for c in v)
            q = extra * h / base
            alloc[y] = int(q)
            rem[y] = q - alloc[y]
        while sum(alloc.values()) < extra:
            y = max(rem, key=rem.get)
            alloc[y] += 1
            rem[y] -= 1
        out = {}
        ypos = 0
        colw = one_rule.columns_rule([dict(c) for c in cs], cols, self.design_size(composition)[0])   # AA1, see place_expanding
        for y in sorted(bands):
            v = bands[y]
            bh = max(c["h"] for c in v)
            if y in alloc:
                bh = min(bh + alloc[y], max((c.get("max_h") or c["h"]) for c in v))
            for c in sorted(v, key=lambda c: (c["x"], c["cell_index"])):
                col, w = colw[c["element_id"]]
                out[c["element_id"]] = {"col": col, "row": ypos, "w": w, "h": bh,
                                        "mode": ["growth (max>design, HYPOTHESIS)"]}
            ypos += bh
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

    def assemble(self, composition, area, composition_pitch=None, reserved_right=0, runtime_slots=(), padding=PADDING, moves=(), adds=()):
        """The screen: grid, placed cells with px boxes (relative to the grid container), tile layouts, and the slots the composition does not hold.
        `area` is the grid container's size in px (the screen chrome around it is not modelled)."""
        p = pitch_mod.lookup(composition_pitch or composition)
        cols, rows = grid_dims(area[0], area[1], p, padding)
        placed = self.place(composition, cols, rows, reserved_right, moves, adds)
        hosts = []
        for eid, g in placed.items():
            layout, how = self.tile_for(composition, eid, g["w"], g["h"])
            hosts.append(dict(g, element_id=eid, px=cell_px(g["col"], g["row"], g["w"], g["h"], padding), tile_layout=layout, tile_how=how))
        extra = [dict(s, px=cell_px(s["col"], s["row"], s["w"], s["h"], padding), placeholder="run-time-added slot: not in the composition, tile chosen by the game") for s in runtime_slots]
        return {"composition": composition, "pitch": p, "grid": {"columns": cols, "rows": rows}, "hosts": hosts, "runtime_slots": extra,
                "flags": ([p["flag"]] if p["flag"] else []) + (["tile configs chosen by the largest-fit assumption: " + h["element_id"] for h in hosts if "ASSUMED" in (h["tile_how"] or "")])}
