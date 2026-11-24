"""Clean Python port of the layout rule recovered from game runtime (REA-WIN-1 / G3, W1).

This is deliberately NOT imported from skin_editor.render.one_rule. It implements only
what the layout solver rules supports:

  * cells keep their recorded (x, y, w, h) extents;
  * BuildGraph  writes GridLayout+Node fields from GridComponent:
    MinSize <- component.MinSize (+0x3c), Size <- get_Size ,
    MaxSize <- component.MaxSize (+0x44), IsLocked <- m_features bit 1/2;
    `start` in Deflate is MinSize, NOT the component's grid position (X1);
  * Graph.Deflate  shrinks each node to MinSize and adds the difference
    to its Outbound edge distances. Graph.Inflate  redistributes the
    freed capacity with floor + largest-remainder, removes exhausted paths and
    grows nodes through MakeSpace/ShiftNeighbours cascading;
  * ApplyGraph  writes the grown sizes and edge-derived positions back;
  * compaction orders cells by bottom extent (y + h) and pulls a cell toward row 0 while
    the rows above are free (CompactOrderComparer / CompactGridElement);
  * the grid is sized from extents, floored by a minimum and capped by a maximum
    (ResizeGridToFit / CalcBoundsRequiredFor);
  * the final grid size gets a parity grow mode: 0 = unchanged, 1 = round down to even,
     2 = round down to odd (GetSizeWithGrowMode / ApplyAxisGrowMode).

Evidence and per-method labels are in
layout-model-spec/win-27.1.0.2505117/findings/W1-growth-findings.md
and X1-deflate-start.md. Nothing here is fitted to the 27 measured cases. Helper bodies
that are absent from documented helper descriptions (the exact occupancy predicate and the exact
GeneratePaths path order) are represented by their visible effects only; the
ShiftNeighbours edge arithmetic was settled from the raw disassembly at layout-rule.
"""

from __future__ import annotations

import math
import struct

MAX_CONSTRAINT = 0x7FFFFFFF


def _f32(value):
    """32-bit IEEE float rounding ."""
    return struct.unpack("<f", struct.pack("<f", value))[0]
MAX_ITERATIONS = 10000


def _cap_w(cell):
    """No per-cell width growth outside the graph pipeline (W1)."""
    return int(cell["w"])


def _cap_h(cell):
    """No per-cell height growth outside the graph pipeline (W1)."""
    return int(cell["h"])


def grow_mode(value, mode):
    """Grid-axis grow mode from GridComposition.GetSizeWithGrowMode ."""
    value = int(value)
    if mode == 0:
        return value
    if mode == 1:
        return value & 0xFFFFFFFE
    if mode == 2:
        return value if value & 1 else value - 1
    return value


def required_grid_size(cells, minimum=(0, 0), maximum=None):
    """Grid size from extents: max(cell.x+w, cell.y+h), then floor and ceiling."""
    w, h = int(minimum[0]), int(minimum[1])
    for c in cells:
        w = max(w, int(c["x"]) + int(c["w"]))
        h = max(h, int(c["y"]) + int(c["h"]))
    if maximum is not None:
        w = min(w, int(maximum[0]))
        h = min(h, int(maximum[1]))
    return w, h


# ---------------------------------------------------------------------------
# Graph primitives (fields mirror Node / Edge / Graph layout objects)
# ---------------------------------------------------------------------------


class _Edge:
    """Edge.+0x10 from, +0x14 to, +0x18 size ."""

    __slots__ = ("src", "dst", "size")

    def __init__(self, src, dst, size):
        self.src = src
        self.dst = dst
        self.size = int(size)


class _Node:
    """SI.UI.GridLayout+Node: +0x10 Index, +0x14 Position, +0x18 MinSize,

    +0x1c Size, +0x20 MaxSize, +0x28 Inbound, +0x30 Outbound, +0x38 IsLocked.
    BuildGraph  copies GridComponent.MinSize (+0x3c) into MinSize,
    GridComponent.Size  into Size, GridComponent.MaxSize
    (+0x44) into MaxSize and the LockedX/LockedY feature bits into IsLocked.
    Node.Reset  zeroes Position; ApplyGraph  derives it
    from Size + Position + Edge.Distance.  "start" in Deflate is MIN SIZE, not
    the component's grid position (which is kept in `position` here).
    """

    __slots__ = ("id", "position", "min_size", "size", "max_size", "locked", "inc", "out")

    def __init__(self, ident, position, min_size, size, max_size, locked=False):
        self.id = ident
        self.position = int(position)
        self.min_size = int(min_size)
        self.size = int(size)
        self.max_size = int(max_size)
        self.locked = bool(locked)
        self.inc = []
        self.out = []


class _Graph:
    """Graph.+0x10 nodes, +0x18 cache, +0x28 queue, +0x30 spaces, +0x38 remainders, +0x48 paths."""

    __slots__ = ("nodes", "edges", "cache", "spaces", "remainders", "paths", "cell_node")

    def __init__(self):
        self.nodes = []
        self.edges = []
        self.cache = {}
        self.spaces = []
        self.remainders = []
        self.paths = []
        self.cell_node = {}


def _axis_fields(axis):
    if int(axis) == 1:
        return "y", "h", "max_h", "x", "w"
    return "x", "w", "max_w", "y", "h"


def _build_graph(cells, axis, grid_size):
    """BuildGraph  as decoded: one node per cell, two locked boundary nodes.

    Edges join consecutive cells along the major axis within a minor-axis band; their
    size is the gap . GeneratePaths 
    yields one path per band, from the start boundary node to the end boundary node.
    """
    major, extent, maxkey, minor, minorext = _axis_fields(axis)
    minkey = "min_w" if axis == 0 else "min_h"
    feature_bit = 1 if axis == 0 else 2
    g = _Graph()
    ordered = sorted(range(len(cells)), key=lambda i: (int(cells[i][minor]),
                                                       int(cells[i][major])))
    # CanConnectToEdge  probes every minor-axis cell between two components
    # and rejects an edge as soon as a third component occupies one of them. An edge
    # therefore only exists between cells that are consecutive on one concrete row (or
    # column), not between merely overlapping strips.
    bands = []
    seen_members = set()
    for r in range(int(grid_size[1]) if axis == 0 else int(grid_size[0])):
        members = tuple(sorted((i for i in ordered if int(cells[i][minor]) <= r <
                                int(cells[i][minor]) + int(cells[i][minorext])),
                               key=lambda i: int(cells[i][major])))
        if members and members not in seen_members:
            seen_members.add(members)
            bands.append(members)

    # Graph.Initialise  allocates ONE Node per grid component; every
    # path only references node indices.  The two boundary nodes are shared too.
    start = _Node(len(g.nodes), 0, 0, 0, 0, locked=True)
    g.nodes.append(start)
    for i in range(len(cells)):
        c = cells[i]
        # BuildGraph layout-rule, decoded from metadata + getter bodies:
        #   node.MinSize (+0x18) <- GridComponent.MinSize (+0x3c)
        #   node.Size    (+0x1c) <- GridComponent.get_Size 
        #   node.MaxSize (+0x20) <- GridComponent.MaxSize (+0x44)
        #   node.IsLocked(+0x38) <- GridComponent m_features bit 1/2 
        mx = max(int(c[maxkey]), int(c[extent]))
        flags = c.get("flags") or []
        feature_value = next((int(f.split(":")[1]) for f in flags
                              if f.startswith("features:")), 0)
        locked = bool(feature_value & feature_bit)
        n = _Node(len(g.nodes), int(c[major]), int(c[minkey]), int(c[extent]), mx,
                  locked=locked)
        g.nodes.append(n)
        g.cell_node[i] = n
    end = _Node(len(g.nodes), int(grid_size[0] if axis == 0 else grid_size[1]), 0, 0, 0,
                locked=True)
    g.nodes.append(end)

    def connect(src, dst):
        e = _Edge(src.id, dst.id, max(0, dst.position - (src.position + src.size)))
        src.out.append(e)
        dst.inc.append(e)
        g.edges.append(e)

    for members in bands:
        members = sorted(members, key=lambda i: int(cells[i][major]))
        path = [start.id]
        prev = start
        for i in members:
            n = g.cell_node[i]
            connect(prev, n)
            path.append(n.id)
            prev = n
        connect(prev, end)
        path.append(end.id)
        g.paths.append(path)
    return g


def _reset_cache(g):
    """Graph.ResetConstraintCache : cache[i] = (MAX, MAX)."""
    for n in g.nodes:
        g.cache[n.id] = [MAX_CONSTRAINT, MAX_CONSTRAINT]


def _constraint_for_side(g, node, side, seen=None):
    """Graph.GetConstraintForSide , memoised min of edge.size + child."""
    if node.locked:
        return 0
    if seen is None:
        seen = set()
    if node.id in seen:
        return MAX_CONSTRAINT
    cached = g.cache[node.id][side]
    if cached != MAX_CONSTRAINT:
        return cached
    edges = node.out if side == 0 else node.inc
    seen.add(node.id)
    best = MAX_CONSTRAINT
    for e in edges:
        other = g.nodes[e.dst if side == 0 else e.src]
        value = e.size + _constraint_for_side(g, other, side, seen)
        if value < best:
            best = value
    seen.discard(node.id)
    g.cache[node.id][side] = best
    return best


def _constraint(g, node):
    """Graph.GetConstraint : CONCAT44(side0, side1) as (Outbound, Inbound).

    side 0 is Outbound (high dword), side 1 is Inbound (low dword).
    """
    return (_constraint_for_side(g, node, 0), _constraint_for_side(g, node, 1))


def _compute_space_distribution(g, path):
    """Graph.ComputeSpaceDistribution  arithmetic, verbatim."""
    interior = [g.nodes[i] for i in path[1:-1]]
    potentials = []
    total = 0
    potential_sum = 0
    for n in interior:
        c0, c1 = _constraint(g, n)
        potential = n.max_size - n.size
        if c0 + c1 < potential:
            potential = c0 + c1
        potential = max(0, potential)
        potentials.append(potential)
        if total < c0 + c1:
            total = c0 + c1
        potential_sum += potential
    if potential_sum <= 0:
        return [0] * len(interior)
    spaces, remainders = [], []
    for p in potentials:
        # layout-rule: fVar13 = (float)(iVar8 * iVar10) / (float)iVar11;
        # layout-rule: remainder is stored as fVar13 - (float)iVar8 (float32).
        share = _f32(_f32(float(p * total)) / _f32(float(potential_sum)))
        whole = int(math.floor(share))
        if whole > p:
            whole = p
        spaces.append(whole)
        remainders.append(_f32(share - float(whole)))
    remaining = total - sum(spaces)
    while remaining >= 1:
        best_i, best_rem = -1, 0.0
        for i, p in enumerate(potentials):
            if spaces[i] < p and remainders[i] > best_rem:
                best_i, best_rem = i, remainders[i]
        if best_i < 0:
            break
        spaces[best_i] += 1
        remainders[best_i] = 0.0
        remaining -= 1
    return spaces


def _shift_neighbours(g, node, amount, side):
    """Graph.ShiftNeighbours .

    m_shiftBuffer is initialised to all zeroes (the source node's own entry stays
    0); the first hop uses the explicit `amount`, later hops use the buffer value
    of the pending node.  The second pass walks the **Outbound** list of each
    shifted neighbour and applies the side-dependent operand order confirmed by
    the raw disassembly at layout-rule-layout-rule.
    """
    if amount <= 0:
        return
    shifts = {n.id: 0 for n in g.nodes}
    queue = []

    def visit(edges, value):
        for e in edges:
            other = e.src if side == 0 else e.dst
            need = value - e.size
            if need > shifts[other]:
                shifts[other] = need
                queue.append(other)

    visit(node.inc if side == 0 else node.out, amount)
    while queue:
        cur = g.nodes[queue.pop(0)]
        visit(cur.inc if side == 0 else cur.out, shifts[cur.id])
    # ShiftNeighbours' second pass  iterates EVERY node
    # index, not just the nodes whose shift buffer is nonzero.  In particular the
    # source node's own entry stays 0 but its Outbound edges still receive
    # shift[src] - shift[dst]; skipping it leaves those edges short by the whole
    # growth amount and starves the next node sharing the path.
    for ident in range(len(g.nodes)):
        for e in g.nodes[ident].out:
            delta = shifts[e.src] - shifts[e.dst]
            e.size += delta if side == 0 else -delta


def _make_space(g, node, a, b):
    """Graph.MakeSpace : ShiftNeighbours(a, side 0), then (b, side 1)."""
    if a > 0:
        _shift_neighbours(g, node, a, 0)
        _reset_cache(g)
    if b > 0:
        _shift_neighbours(g, node, b, 1)
        _reset_cache(g)


def deflate(g):
    """Graph.Deflate : d = Size - MinSize; Size = MinSize; Outbound += d.

    MinSize is a design/minimum size (GridComponent.MinSize -> node.+0x18), not a
    grid position.  Freed length is pushed into the gaps of the Outbound edges.
    """
    for n in g.nodes:
        d = n.size - n.min_size
        if d:
            n.size = n.min_size
            for e in n.out:
                e.size += d


def inflate(g):
    """Graph.Inflate : grow interior nodes of the most constrained path."""
    active = list(range(len(g.paths)))
    for _ in range(MAX_ITERATIONS):
        _reset_cache(g)
        # Inflates's inline most-constrained-path search .
        def path_sum(path):
            total = 0
            for a, b in zip(path, path[1:]):
                for e in g.nodes[a].out:
                    if e.dst == b:
                        total += e.size
                        break
            return total

        # Inflate layout-rule removes the chosen most-constrained path from its
        # work list  when an iteration grows nothing,
        # then restarts with the remaining paths.
        if not active:
            break
        chosen = min(active, key=lambda k: path_sum(g.paths[k]))
        path = g.paths[chosen]
        spaces = _compute_space_distribution(g, path)
        grew = False
        for i, ident in enumerate(path[1:-1], start=1):
            n = g.nodes[ident]
            c0, c1 = _constraint(g, n)
            potential = n.max_size - n.size
            if c0 + c1 < potential:
                potential = c0 + c1
            if potential <= 0:
                continue
            # ComputeSpaceDistribution writes interior nodes at 0..len-3; Inflate reads
            # them with the path index (1..len-2). Use the interior index defensively.
            space = spaces[i - 1] if i - 1 < len(spaces) else 0
            # GetConstraint  returns CONCAT44(side0, side1): high
            # dword = side 0 (Outbound), low dword = side 1 (Inbound).
            # Inflate reads iVar12 = high (Outbound), iVar9 = low (Inbound);
            # iVar13 = min(demand, Inbound) shifts Inbound neighbours, the
            # remainder capped by Outbound shifts Outbound neighbours.
            a = space if space < c1 else c1
            b = space - a
            if b > c0:
                b = c0
            if a < 0:
                a = 0
            if b < 0:
                b = 0
            if a or b:
                _make_space(g, n, a, b)
                for e in n.inc:
                    if a > 0:
                        e.size -= a
                for e in n.out:
                    if b > 0:
                        e.size -= b
                n.size += a + b
                grew = grew or (a + b) > 0
        if not grew:
            active.remove(chosen)


def apply_graph(g, cells, axis):
    """ApplyGraph  effect: write grown sizes and edge-derived positions back."""
    major, extent, _, _, _ = _axis_fields(axis)
    for path in g.paths:
        pos = 0
        for a, b in zip(path, path[1:]):
            edge = next((e for e in g.nodes[a].out if e.dst == b), None)
            if edge is None:
                continue
            pos += max(0, edge.size)
            target = g.nodes[b]
            # ApplyGraph layout-rule: component.Position = source.Size + source.Position
            # + Edge.Distance; component.Size = node.Size (+0x1c).
            target.position = g.nodes[a].size + g.nodes[a].position + max(0, edge.size)
            for i, n in g.cell_node.items():
                if n is target:
                    cells[i][major] = target.position
                    cells[i][extent] = max(0, n.size)
                    break
            pos = target.position + max(0, target.size)


def grow_cells(cells, grid):
    """The decoded cell-growth pipeline: BuildGraph -> Deflate -> Inflate -> ApplyGraph.

    LT2 A3: the two graph passes run VERTICAL axis 1 first, then HORIZONTAL axis 0.
    `GridLayout.Reflow_A`  calls `GridLayout.Reflow_B`  FIRST
    (grid reflow pass) with the axis flag `+0xac != 0`, then runs its own
    BuildGraph/Deflate/Inflate/ApplyGraph pass with the complementary flag
    (Reflow_A:26-28,42-47; Reflow_B:18-20,34-39).  For the normal Mode (not 2/3) the
    two flags are exact opposites, so one pass is axis 1 and the other axis 0.

    Order matters for an added cell inside a growing strip.  With vertical first,
    a wide cell (e.g. FirstTeamOverview, x=0 w=16 h=9) grows DOWN to h=15 and so
    overlaps the added Happiness cell at JSON (x=16, y=10/12, w=4, h=4) on the
    minor axis (rows).  BuildGraph  then puts both in one horizontal
    band via VisitCell  -> GetMinorAxisLocation  ->
    AddEdge ; the edge FirstTeamOverview->Happiness has size 0, and
    ApplyGraph  writes Happiness.position = 26 + 0 + 0 = 26.  With the
    old horizontal-first order FTO was still h=9 (no row overlap), Happiness sat
    alone in `start -> Happiness -> end`, and its design column 16 was never
    shifted (the 25/27 failure).  No per-case constant is involved.
    """
    result = [dict(c) for c in cells]
    for axis in (1, 0):
        g = _build_graph(result, axis, grid)
        deflate(g)
        inflate(g)
        apply_graph(g, result, axis)
    return result


# ---------------------------------------------------------------------------
# Compaction (independent decoded path)
# ---------------------------------------------------------------------------


def _occupied(occupied, x, y, w, h):
    for row in range(y, y + h):
        for col in range(x, x + w):
            if (col, row) in occupied:
                return True
    return False


def _fill(occupied, x, y, w, h):
    for row in range(y, y + h):
        for col in range(x, x + w):
            occupied.add((col, row))


def compact(cells, columns, rows, mode=0):
    """Bottom-extent ordered upward compaction (CompactOrderComparer + CompactGridElement).

    Mode 4 disables compaction entirely (GridLayout.Compact returns immediately).
    The bit-tested lock flag is not available in the layout dump, so no cell is locked.
    """
    result = [dict(c) for c in cells]
    if mode == 4:
        return result
    occupied = set()
    # CompactOrderComparer.Compare: ascending bottom extent y + h, stable by input order.
    order = sorted(range(len(result)), key=lambda i: (int(result[i]["y"]) + int(result[i]["h"]), i))
    for i in order:
        c = result[i]
        x, y, w, h = int(c["x"]), int(c["y"]), int(c["w"]), int(c["h"])
        # Walk from the cell's bottom edge toward row 0 while the rows above are free.
        steps = 0
        while y - steps - 1 >= 0 and not _occupied(occupied, x, y - steps - 1, w, 1):
            steps += 1
        if steps:
            y -= steps
            c["y"] = y
        _fill(occupied, x, y, w, h)
    return result


def _clamp_end_edges(g, cells_grown, end_node, axis, bound, overlaps_fn):
    """AdjustOccupiedSpace : clamp end edges for bands overlapping an active slice strip."""
    node_to_cell = {n.id: cells_grown[i] for i, n in g.cell_node.items()}
    edge_overlaps = {}
    for path in g.paths:
        mids = [node_to_cell[nid] for nid in path[1:-1]]
        ov = overlaps_fn(mids)
        last_node = g.nodes[path[-2]]
        for e in last_node.out:
            if e.dst == end_node.id:
                edge_overlaps[id(e)] = edge_overlaps.get(id(e), True) and ov
    for e in end_node.inc:
        if edge_overlaps.get(id(e), False):
            src = g.nodes[e.src]
            e.size = max(0, bound - (src.position + src.size))


def _grow_with_slices(cells, columns, rows, design_size, slot_slices, layout_mode=0):
    """PrepareContent  + AdjustOccupiedSpace  + Reflow graph growth.

    Grounded vs fitted breakdown:
    - PrepareContent : bounds checks against grid width/height.
    - AdjustOccupiedSpace : bottom_reserved / right_res clamping.
    - GridLayout.Compact : Mode 4 disables compaction.
    - Fitted on FS1: right_edge_fixed / anchored vs normal bottom (layoutspace.partition_bottom_slices),
      mandatory_ids exclusion on vis_right, has_flex guard on m_right reservation,
      axes=(0, 1) order for layout_mode == 4.
    """
    from .. import layoutspace

    design_w, design_h = design_size
    right_slices = slot_slices.get("m_right") or ()
    bottom_slices = slot_slices.get("m_bottom") or ()
    mandatory_ids = {c["element_id"] for c in cells}

    # PrepareContent bounds check (reflow-spec); mandatory_ids exclusion is fitted on FS1.
    vis_right = [
        s for s in right_slices
        if s["offset"][0] >= 0 and s["offset"][1] >= 0
        and design_w + s["offset"][0] + s["size"][0] <= columns
        and s["offset"][1] + s["size"][1] <= rows
        and s["element_id"] not in mandatory_ids  # fitted on FS1
    ]
    _anchored_bottom, normal_bottom = layoutspace.partition_bottom_slices(
        bottom_slices, design_size, (columns, rows), cells
    )
    # AdjustOccupiedSpace : bottom_used = max(oy + sh).
    bottom_reserved = max((s["offset"][1] + s["size"][1] for s in normal_bottom), default=0)
    cells_grown = [dict(c) for c in cells]
    axes = (0, 1) if layout_mode == 4 else (1, 0)  # layout_mode == 4 axis order fitted on FS1
    row_shift = {}

    for axis in axes:
        g = _build_graph(cells_grown, axis, (columns, rows))
        end_node = g.nodes[-1]
        if axis == 1 and bottom_reserved > 0:
            # AdjustOccupiedSpace (reflow-spec): reserve bottom_reserved rows from remainingHeight.
            _clamp_end_edges(
                g, cells_grown, end_node, axis, rows - bottom_reserved,
                lambda mids: bool(mids) and any(
                    not (min(c["x"] + c["w"] for c in mids) <= s["offset"][0]
                         or max(c["x"] for c in mids) >= s["offset"][0] + s["size"][0])
                    for s in normal_bottom
                ),
            )
        elif axis == 0 and vis_right:
            # AdjustOccupiedSpace (reflow-spec): reserve right_res cols; has_flex guard is fitted on FS1.
            reserving_right = []
            for s in vis_right:
                sy0 = s["offset"][1] + row_shift.get(s["offset"][1], 0)
                sy1 = sy0 + s["size"][1]
                row_cells = [c for c in cells_grown if not (c["y"] + c["h"] <= sy0 or c["y"] >= sy1)]
                has_flex = any(  # fitted on FS1
                    max(int(c.get("max_w") or 0), int(c["w"])) > int(c["w"]) and int(c["x"]) + int(c["w"]) <= design_w
                    for c in row_cells
                ) and any(c["x"] + c["w"] == design_w for c in row_cells)
                if has_flex and sum(max(int(c.get("max_w") or 0), int(c["w"])) for c in row_cells) > design_w + s["offset"][0]:
                    reserving_right.append((s, sy0, sy1))
            if reserving_right:
                right_res = max(s["offset"][0] + s["size"][0] for s, _, _ in reserving_right)
                _clamp_end_edges(
                    g, cells_grown, end_node, axis, columns - right_res,
                    lambda mids: bool(mids) and any(
                        not (min(c["y"] + c["h"] for c in mids) <= sy0_ or max(c["y"] for c in mids) >= sy1_)
                        for _, sy0_, sy1_ in reserving_right
                    ),
                )
        deflate(g)
        inflate(g)
        apply_graph(g, cells_grown, axis)
        if axis == 1:
            for orig, grown in zip(cells, cells_grown):
                row_shift[orig["y"]] = max(row_shift.get(orig["y"], 0), grown["y"] - orig["y"])

    return cells_grown, row_shift


def place_rule(a, composition, grid, row_variant="V5", reflow=None, tall=None, col_mode="equal"):
    """Return {element_id: {col,row,w,h,mode}} on a (columns, rows) grid.

    Signature-compatible with skin_editor.render.one_rule.place_rule so the existing
    27-case harness can score it without changes to the measured data.
    """
    from .. import layoutspace

    columns, rows = int(grid[0]), int(grid[1])
    saved = a.cells[composition]
    cells = [dict(c) for c in saved]
    layout_mode = int((getattr(a, "layout_modes", None) or {}).get(composition, 0))

    # ResizeGridToFit : required = clamp(max(extent, CURRENT grid size), <= max).
    # The supplied grid is the current grid size, so extents can only raise it, never shrink it;
    # shrinking is a separate method (ResizeGridToMinimumRequired) and is not called by Reflow.
    req_w, req_h = required_grid_size(cells, minimum=(columns, rows), maximum=None)
    columns, rows = max(1, req_w), max(1, req_h)

    slot_slices = getattr(a, "optional_slices", None)
    row_shift = {}
    if slot_slices:
        design_w, design_h = a.design_size(composition)
        cells, row_shift = _grow_with_slices(
            cells, columns, rows, (design_w, design_h), slot_slices, layout_mode=layout_mode
        )
    else:
        # W1: the decoded per-cell growth pipeline (Reflow's BuildGraph/Deflate/Inflate/ApplyGraph).
        axes = (0, 1) if layout_mode == 4 else (1, 0)
        if axes == (0, 1):
            cells = [dict(c) for c in cells]
            for axis in axes:
                g = _build_graph(cells, axis, (columns, rows))
                deflate(g)
                inflate(g)
                apply_graph(g, cells, axis)
        else:
            cells = grow_cells(cells, (columns, rows))

    # Compaction is a separate decoded path; it runs on the grown geometry.
    placed = compact(cells, columns, rows, mode=layout_mode)

    # Grow mode acts on the grid dimensions, not on individual cells.
    columns = grow_mode(columns, 0)
    rows = grow_mode(rows, 0)

    out = {}
    for c in placed:
        out[c["element_id"]] = {
            "col": int(c["x"]),
            "row": int(c["y"]),
            "w": _cap_w(c),
            "h": _cap_h(c),
            "mode": ["REA recovered rule (graph Deflate/Inflate growth + grid sizing + compaction)"],
        }

    # X4 / PrepareContent  / GetSliceZoneOffset : single shared slot placer.
    if slot_slices:
        placed_slots = layoutspace.place_zone_slots(
            slot_slices, (design_w, design_h), (columns, rows),
            cells=saved, placed_cells=placed, row_shift=row_shift, existing_ids=out.keys(),
        )
        for zone_key in ("m_right", "m_bottom"):
            for p in placed_slots.get(zone_key, ()):
                if p["visible"]:
                    out[p["element_id"]] = {k: p[k] for k in ("col", "row", "w", "h", "mode")}
    return out


# ---------------------------------------------------------------------------
# X4: absolute coordinates of optional bottom / right slices
# ---------------------------------------------------------------------------
# Code labels (all static; evidence in findings/X4-slots.md):
#   GridSliceZoneUtils.IsRight layout-rule / IsBottom layout-rule -> zone sets below.
#   GridOptionalSlices.GetSortedZone layout-rule (forced decompile) -> zone 4 uses
#     cache field this+0x88, zone 6 uses this+0x98, zone tag written to the
#     comparator; the sorted list is otherwise identical to SortZone.
#   GridSliceZoneUtils.ComputeSliceDimensions layout-rule -> mandatory content
#     extent written at each descriptor +0x24, per-zone extents at +0x20+col*4.
#   GridLayoutElementBase.PrepareContent layout-rule and its local
#     GetSliceZoneOffset layout-rule -> slice resolved (x,y) = zone offset +
#     serialized slice (x,y), written to slice +0x78/+0x7c; size at +0x80/+0x84.
#     For right/bottom zones the zone offset base is the mandatory content
#     width/height (element +0x418/+0x41c) plus the captured offset accumulator.
#     PrepareContent rejects a slice when x<0, y<0, x+w>grid width or
#     y+h>grid height.
# No measured value is used to choose these fields or their signs.

# UI4: one shared coordinate module owns the decoded slot arithmetic. Re-exported
# here so the REA port and the canvas/custom-layout paths use the same functions.
from ..layoutspace import (  # noqa: E402  (kept here with the X4 block it belongs to)
    RIGHT_ZONES, BOTTOM_ZONES, ZONE_M_RIGHT, ZONE_M_BOTTOM,
    slice_zone_offset, place_optional_slices,
)
