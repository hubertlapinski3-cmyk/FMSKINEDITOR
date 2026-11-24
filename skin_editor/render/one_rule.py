"""AA1: one candidate layout rule with exchangeable row variants (offline; NOT wired into the preview).

Columns (all variants): the extra columns (grid columns - design columns) go left to right to cells whose m_maxSize
width is larger than their width, each up to its maximum; a cell moves right by the growth of the cells to its left
that share design rows. Leftover columns stay empty at the right. An m_maxSize of 0 means "no growth" (measured:
InjuryHistory tiles, Contract Negotiation tiles).

Rows: cells are grouped into vertical strips (design columns overlap, transitively) and, inside a strip, into bands
(cells starting on the same design row). The strip's extra rows (grid rows - design rows) go to growable bands:
  V1 proportional to design band height (largest remainder, capped at the band's maximum, leftovers redistributed)
  V2 bottom-most growable band first, up to its maximum, then the next one up
  V3 top-most growable band first
  V5 (extra) as V1, but the rows left over after flooring go to the tallest band first instead of the largest remainder
  V4 as V1, but a band takes part only if a cell's tile description offers a configuration taller than its design height
A cell grows by min(its own maximum - height, its band's rows); bands below move down by the growth above them.
m_reflowMode 1 compositions additionally get the vertical packing rule (screen.pack_rows). Optional bottom slots are not
modelled (none of the measured compositions has one).
"""

VARIANTS = ("V1", "V2", "V3", "V4")
EXTRA_VARIANTS = ("V5",)   # beyond the AA1 spec: V1 with the leftover rows going to the tallest band (see _proportional)


def _cap_w(c):
    return c["max_w"] if c["max_w"] > c["w"] else c["w"]


def _cap_h(c):
    return c["max_h"] if c["max_h"] > c["h"] else c["h"]


def _waterfill(extra, caps):
    """Equal shares of `extra` over cells with the given caps; remainders go left to right; capped cells' leftovers are redistributed."""
    alloc = [0] * len(caps)
    left, live = extra, list(range(len(caps)))
    while left > 0 and live:
        share, rem = divmod(left, len(live))
        moved = 0
        for k, i in enumerate(live):
            give = min(share + (1 if k < rem else 0), caps[i] - alloc[i])
            alloc[i] += give
            moved += give
        left -= moved
        live = [i for i in live if alloc[i] < caps[i]]
        if moved == 0:
            break
    return alloc


def _equal_growth(cells, extra):
    """C2 (beyond the AA1 spec): per grid row the extra columns are shared equally by the cells that can grow on that row."""
    growth = {c["element_id"]: None for c in cells}
    for r in range(max(c["y"] + c["h"] for c in cells)):
        on = sorted((c for c in cells if c["y"] <= r < c["y"] + c["h"] and _cap_w(c) > c["w"]), key=lambda c: c["x"])
        for c, g in zip(on, _waterfill(extra, [_cap_w(c) - c["w"] for c in on])):
            cur = growth[c["element_id"]]
            growth[c["element_id"]] = g if cur is None else min(cur, g)
    return {k: (v or 0) for k, v in growth.items()}


def columns_rule(cells, cols, design_cols, mode="seq"):
    """{element_id: (col, width)}: extra columns left to right (mode "seq", the AA1 spec) or shared equally per row
    (mode "equal", C2) to cells with max width > width; right neighbours shift by the growth to their left."""
    extra = max(0, cols - design_cols)
    equal = _equal_growth(cells, extra) if mode == "equal" else None
    out, done = {}, []
    for c in sorted(cells, key=lambda c: (c["x"], c["y"], c.get("cell_index", 0))):
        shift = 0
        for l in done:
            if l["x"] + l["w"] <= c["x"] and l["y"] < c["y"] + c["h"] and c["y"] < l["y"] + l["h"]:
                shift = max(shift, l["_shift"] + l["_g"])
        g = equal[c["element_id"]] if equal is not None else min(_cap_w(c) - c["w"], max(0, extra - shift))
        c["_shift"], c["_g"] = shift, g
        done.append(c)
    # ST1 part 0: the column strip moves as one. A cell whose design columns lie INSIDE a shifted cell's design columns moves with it, also when it shares no design rows with the
    # growing cell (an added tile below the right-hand column: measured, Test D and JX X2). A wide cell that merely overlaps a shifted one does not move.
    for _ in range(len(done)):
        moved = False
        for c in done:
            for d in done:
                if d is not c and d["x"] <= c["x"] and c["x"] + c["w"] <= d["x"] + d["w"] and d["_shift"] > c["_shift"]:
                    c["_shift"], moved = d["_shift"], True
        if not moved:
            break
    return {c["element_id"]: (c["x"] + c["_shift"], c["w"] + c["_g"]) for c in done}


def _strips(cells):
    parent = list(range(len(cells)))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    for i, a in enumerate(cells):
        for j in range(i + 1, len(cells)):
            b = cells[j]
            if a["x"] < b["x"] + b["w"] and b["x"] < a["x"] + a["w"]:
                parent[find(i)] = find(j)
    groups = {}
    for i, c in enumerate(cells):
        groups.setdefault(find(i), []).append(c)
    return list(groups.values())


def _proportional(bands, extra, leftover="remainder"):
    """Largest remainder over band design heights, capped at each band's cap, leftovers redistributed."""
    alloc = {y: 0 for y in bands}
    left = extra
    live = {y: b for y, b in bands.items() if b["cap"] > 0}
    while left > 0 and live:
        total = sum(b["h"] for b in live.values())
        share = {y: left * b["h"] / total for y, b in live.items()}
        floor = {y: min(int(share[y]), live[y]["cap"] - alloc[y]) for y in live}
        for y in live:
            alloc[y] += floor[y]
        left -= sum(floor.values())
        if left > 0:
            order = (sorted(live, key=lambda y: (-live[y]["h"], y)) if leftover == "tallest"
                     else sorted(live, key=lambda y: (-(share[y] - int(share[y])), y)))
            for y in order:
                if left > 0 and alloc[y] < live[y]["cap"]:
                    alloc[y] += 1
                    left -= 1
        live = {y: b for y, b in live.items() if alloc[y] < b["cap"]}
        if sum(floor.values()) == 0 and left == extra:
            break
    return alloc


def _ordered(bands, extra, bottom_first):
    alloc = {y: 0 for y in bands}
    left = extra
    for y in sorted(bands, reverse=bottom_first):
        take = min(bands[y]["cap"], left)
        alloc[y] = take
        left -= take
    return alloc


def rows_rule(a, composition, cells, rows, design_rows, variant, tall=None):
    """{element_id: (row, height)} for one composition."""
    out = {}
    for strip in _strips(cells):
        # ST1 part 0: the spare rows are counted per column strip, against the strip's own design bottom: an added tile in another strip does not use up the rows of this one
        extra = max(0, rows - max(c["y"] + c["h"] for c in strip))
        bands = {}
        for c in strip:
            bands.setdefault(c["y"], {"cells": [], "h": 0})["cells"].append(c)
        for y, b in bands.items():
            b["h"] = max(c["h"] for c in b["cells"])
            grow = [c for c in b["cells"] if _cap_h(c) > c["h"]]
            if variant == "V4":   # `tall` = {cell id: tallest configuration its tile description(s) offer}; else the layout dump's configs
                grow = [c for c in grow if (tall.get(c["element_id"], 0) if tall is not None else
                                            max((t["size"]["h"] for t in a.tiles.get((composition, c["element_id"]), [])), default=0)) > c["h"]]
            b["grow"] = grow
            b["cap"] = max((_cap_h(c) - c["h"] for c in grow), default=0)
        live = {y: b for y, b in bands.items() if b["cap"] > 0}
        if variant in ("V1", "V4", "V5"):
            alloc = _proportional(live, extra, "tallest" if variant == "V5" else "remainder")
        else:
            alloc = _ordered(live, extra, bottom_first=(variant == "V2"))
        shift = 0
        for y in sorted(bands):
            b = bands[y]
            band_growth = 0
            for c in b["cells"]:
                g = min(_cap_h(c) - c["h"], alloc.get(y, 0)) if c in b["grow"] else 0
                band_growth = max(band_growth, g)
                out[c["element_id"]] = (c["y"] + shift, c["h"] + g)
            shift += band_growth
    return out


def place_rule(a, composition, grid, row_variant="V4", reflow=None, tall=None, col_mode="seq"):
    """{element_id: {col,row,w,h,mode}} on a `grid` = (columns, rows) grid. `a` is a render.screen.Assembler."""
    from .screen import pack_rows
    cols, rows = grid
    cells = [dict(c) for c in a.cells[composition]]
    c0, r0 = a.design_size(composition)
    colw = columns_rule([dict(c) for c in cells], cols, c0, col_mode)
    rowh = rows_rule(a, composition, cells, rows, r0, row_variant, tall)
    items = []
    for c in cells:
        x, w = colw[c["element_id"]]
        y, h = rowh[c["element_id"]]
        items.append({"element_id": c["element_id"], "cell_index": c.get("cell_index"), "x": x, "w": w, "y": y, "h": h})
    if reflow == 1:
        items = pack_rows(items)
    return {i["element_id"]: {"col": i["x"], "row": i["y"], "w": i["w"], "h": i["h"],
                              "mode": ["one rule %s%s" % (row_variant, " + packing" if reflow == 1 else "")]} for i in items}
