"""The three coordinate spaces of a Game Layout, and the conversions between them.

design  the custom file's own numbers: `m_gridComponents` cells, and each
        `m_optionalSlices.<zone>` entry stored relative to its zone base.
slot    the same optional-slice numbers, read as an offset inside their zone
        (before the zone base is added).
runtime the grid a screen actually shows after growth  and compaction .

Decoded sources (no constant is fitted to a measured case):
  * PrepareContent layout-rule + its local GetSliceZoneOffset layout-rule: a slice's
    resolved position is `zone offset + serialized (x, y)`; for the right and
    bottom zones the zone offset base is the mandatory content extent
    (`GridLayoutElementBase +0x418/+0x41c`, the design width/height) plus the
    captured accumulator, and PrepareContent rejects a slice when it leaves the
    grid (x < 0, y < 0, x + w > grid width, y + h > grid height).
  * `GridOptionalSlices.GetSortedZone` layout-rule: zone 4 = m_right, zone 6 =
    m_bottom. `GridSliceZoneUtils.IsRight` layout-rule / `IsBottom` layout-rule.
  * BuildGraph/ApplyGraph layout-rule grow main cells; Compact layout-rule reorders
    them by bottom extent. The right strip keeps its design offset from the
    design right edge (`runtime x = design x + (runtime cols - design cols)`),
    because growth extends the middle column, not the right strip.

Nothing here writes a file. `custom_layouts` applies edits in design/slot space,
`render.preview` reports the runtime result, and the canvas shows both.
"""

# zone ids from SI.UI.GridSliceZone / GridOptionalSlices.GetSortedZone layout-rule
RIGHT_ZONES = frozenset((2, 4, 7))
BOTTOM_ZONES = frozenset((5, 6, 7))
ZONE_M_TOP_LEFT = 0
ZONE_M_TOP = 1
ZONE_M_TOP_RIGHT = 2
ZONE_M_LEFT = 3
ZONE_M_RIGHT = 4
ZONE_M_BOTTOM_LEFT = 5
ZONE_M_BOTTOM = 6
ZONE_M_BOTTOM_RIGHT = 7

# the file's zone key -> the decoded zone id
FILE_ZONES = {
    "m_topLeft": ZONE_M_TOP_LEFT,
    "m_top": ZONE_M_TOP,
    "m_topRight": ZONE_M_TOP_RIGHT,
    "m_left": ZONE_M_LEFT,
    "m_right": ZONE_M_RIGHT,
    "m_bottomLeft": ZONE_M_BOTTOM_LEFT,
    "m_bottom": ZONE_M_BOTTOM,
    "m_bottomRight": ZONE_M_BOTTOM_RIGHT,
}
ZONE_KEYS = {v: k for k, v in FILE_ZONES.items()}

MAIN = "main"

# FS1: fullscreen 2K Small as the main setting, with 2560x1440 windowed kept selectable.
PROFILE_FULLSCREEN = "2560x1440 fullscreen, Small, Larger"
PROFILE_WINDOWED = "2560x1440 windowed, Small, Larger"
DEFAULT_VIEWPORT_PROFILE = PROFILE_FULLSCREEN

MEASURED_VIEWPORT_FULLSCREEN = {
    "profile": PROFILE_FULLSCREEN,
    "width": 2560,
    "height": 1440,
    "window_mode": "fullscreen",
    "information_display": "Small",
    "text_scaling": "Larger",
    "breakpoint": "Large",
    "content_rect": (15.6, 85.9, 2468.8, 1319.3),
    "grid": (30, 16),
}

MEASURED_VIEWPORT_WINDOWED = {
    "profile": PROFILE_WINDOWED,
    "width": 2560,
    "height": 1440,
    "window_mode": "windowed",
    "information_display": "Small",
    "text_scaling": "Larger",
    "breakpoint": "Large",
    "content_rect": (15.6, 85.9, 2468.8, 1319.3),
    "grid": (30, 16),
}

VIEWPORT_PROFILES = {
    PROFILE_FULLSCREEN: MEASURED_VIEWPORT_FULLSCREEN,
    PROFILE_WINDOWED: MEASURED_VIEWPORT_WINDOWED,
}

# Default measured viewport exposed to callers that read MEASURED_VIEWPORT directly.
MEASURED_VIEWPORT = dict(MEASURED_VIEWPORT_FULLSCREEN)


def normalize_profile(profile=None):
    """Map an explicit viewport profile or shorthand ('fullscreen'/'windowed') to a canonical profile."""
    if not profile:
        return DEFAULT_VIEWPORT_PROFILE
    s = str(profile).strip()
    low = s.lower()
    if low == PROFILE_WINDOWED.lower() or ("window" in low and "full" not in low):
        return PROFILE_WINDOWED
    if low == PROFILE_FULLSCREEN.lower() or "fullscreen" in low:
        return PROFILE_FULLSCREEN
    return DEFAULT_VIEWPORT_PROFILE


def viewport_profile(profile=None):
    """Return a copy of the selected viewport profile dict."""
    key = normalize_profile(profile)
    return dict(VIEWPORT_PROFILES[key])


def _int(v, d=0):
    try:
        return int(v)
    except (TypeError, ValueError):
        return d


def slice_zone_offset(zone, design_size, accum_x=0, accum_y=0):
    """GetSliceZoneOffset layout-rule: zone base + captured accumulator.

    `design_size` is the mandatory content extent (+0x418/+0x41c), which equals
    the design grid width/height for the measured compositions.
    """
    dw, dh = int(design_size[0]), int(design_size[1])
    return (int(accum_x) + (dw if int(zone) in RIGHT_ZONES else 0),
            int(accum_y) + (dh if int(zone) in BOTTOM_ZONES else 0))


def place_optional_slices(slices, design_size, grid_size, zone, accum_x=0, accum_y=0):
    """Absolute runtime cells for one optional-slice zone .

    `slices` accept `{offset:(x,y), size:(w,h)}` or `{x,y,w,h}`. `visible` is the
    PrepareContent bounds test; a rejected slice is never placed.
    """
    ox, oy = slice_zone_offset(zone, design_size, accum_x, accum_y)
    gw, gh = int(grid_size[0]), int(grid_size[1])
    out = []
    for s in slices:
        off = s.get("offset") if s.get("offset") is not None else (s.get("x", 0), s.get("y", 0))
        size = s.get("size") if s.get("size") is not None else (s.get("w", 0), s.get("h", 0))
        dx, dy = _int(off[0]), _int(off[1])
        w, h = _int(size[0]), _int(size[1])
        x, y = ox + dx, oy + dy
        out.append({"element_id": s.get("element_id"), "col": x, "row": y, "w": w, "h": h,
                    "visible": x >= 0 and y >= 0 and x + w <= gw and y + h <= gh,
                    "mode": ["REA X4: optional slice at the design edge + serialized offset"]})
    return out


def zone_accumulator(zone, design_size, runtime_size):
    """The captured accumulator PrepareContent passes to GetSliceZoneOffset.

    Horizontal centre bands (top = 1, bottom = 6) receive the grid's extra width
    (gridWidth - mandatoryWidth); right/left/corner zones receive zero and use
    their own RIGHT_ZONES / BOTTOM_ZONES offsets.
    """
    dw = _int(design_size[0])
    extra_w = max(0, _int(runtime_size[0]) - dw)
    return (extra_w if int(zone) in (ZONE_M_TOP, ZONE_M_BOTTOM) else 0, 0)


def partition_bottom_slices(bottom_slices, design_size, runtime_size, cells):
    """Partition m_bottom slices into right-anchored (under fixed-width right strip) vs normal.

    - `PrepareContent` : `accum_x = 0` (`normal_bottom` uses `sx = ox`).
    - `right_edge_fixed` / `anchored_bottom` (`design_w - sw <= ox < design_w` shifted by `extra_w`): **fitted on FS1**.
    """
    design_w, design_h = _int(design_size[0]), _int(design_size[1])
    columns, rows = _int(runtime_size[0]), _int(runtime_size[1])
    vis_bottom = []
    for s in bottom_slices or ():
        off = s.get("offset") if s.get("offset") is not None else (s.get("x", 0), s.get("y", 0))
        size = s.get("size") if s.get("size") is not None else (s.get("w", 0), s.get("h", 0))
        ox, oy = _int(off[0]), _int(off[1])
        sw, sh = _int(size[0]), _int(size[1])
        if ox >= 0 and oy >= 0 and ox + sw <= columns and design_h + oy + sh <= rows:
            vis_bottom.append({"element_id": s.get("element_id"), "offset": (ox, oy), "size": (sw, sh)})

    extra_w = max(0, columns - design_w)
    right_edge_fixed = any(
        _int(c.get("x")) + _int(c.get("w", c.get("width"))) == design_w
        and max(_int(c.get("max_w")), _int(c.get("w", c.get("width")))) < columns - _int(c.get("x"))
        for c in (cells or ())
    )
    anchored_bottom, normal_bottom = [], []
    for s in vis_bottom:
        ox, _oy = s["offset"]
        sw, _sh = s["size"]
        if extra_w > 0 and right_edge_fixed and design_w - sw <= ox < design_w:
            if min(ox + extra_w, columns - sw) + sw <= columns:
                anchored_bottom.append(s)
        elif ox + sw <= columns:
            normal_bottom.append(s)
    return anchored_bottom, normal_bottom


def place_zone_slots(slices_by_zone, design_size, runtime_size, cells=None, placed_cells=None, row_shift=None, existing_ids=None):
    """Single shared slot placer for both `rea_rule.place_rule` and `layoutspace.slot_to_runtime`.

    Implements `PrepareContent` , `AdjustOccupiedSpace` , and
    `GetSliceZoneOffset` , with FS1-fitted rules explicitly marked.
    Returns {zone_key: [{"element_id", "col", "row", "w", "h", "visible", "mode"}]}.
    """
    design_w, design_h = _int(design_size[0]), _int(design_size[1])
    columns, rows = _int(runtime_size[0]), _int(runtime_size[1])
    extra_w = max(0, columns - design_w)
    row_shift = row_shift or {}
    existing = set(existing_ids or ())
    placed_list = list(placed_cells or ())
    mode_tag = ["REA recovered rule "]
    out = {}

    # m_right: GetSliceZoneOffset  places past row_end + ox; mandatory_id exclusion fitted on FS1.
    right_rows = []
    for s in (slices_by_zone.get("m_right") or ()):
        off = s.get("offset") if s.get("offset") is not None else (s.get("x", 0), s.get("y", 0))
        size = s.get("size") if s.get("size") is not None else (s.get("w", 0), s.get("h", 0))
        ox, oy = _int(off[0]), _int(off[1])
        sw, sh = _int(size[0]), _int(size[1])
        sy = oy + row_shift.get(oy, 0)
        row_end = max((_int(c.get("x", c.get("col"))) + _int(c.get("w")) for c in placed_list
                       if not (_int(c.get("y", c.get("row"))) + _int(c.get("h")) <= sy or _int(c.get("y", c.get("row"))) >= sy + sh)),
                      default=design_w)
        sx = row_end + ox
        eid = s.get("element_id")
        vis = 0 <= sx and 0 <= sy and sx + sw <= columns and sy + sh <= rows and eid not in existing
        if vis:
            existing.add(eid)
        right_rows.append({"element_id": eid, "col": sx, "row": sy, "w": sw, "h": sh, "visible": vis, "mode": mode_tag})
    if right_rows:
        out["m_right"] = right_rows

    # m_bottom: AdjustOccupiedSpace  reserves bottom_reserved; anchored strip + oy == 0 stack fitted on FS1.
    if cells is None:
        ax, ay = zone_accumulator(ZONE_M_BOTTOM, design_size, runtime_size)
        bottom_rows = place_optional_slices(
            slices_by_zone.get("m_bottom") or (), design_size, runtime_size, ZONE_M_BOTTOM, accum_x=ax, accum_y=ay
        )
    else:
        anchored_bottom, normal_bottom = partition_bottom_slices(slices_by_zone.get("m_bottom") or (), design_size, runtime_size, cells)
        bottom_reserved = max((s["offset"][1] + s["size"][1] for s in normal_bottom), default=0)
        anchored_ids = {id(s): s for s in anchored_bottom}
        bottom_rows = []
        occ_y = design_h
        for s in (slices_by_zone.get("m_bottom") or ()):
            off = s.get("offset") if s.get("offset") is not None else (s.get("x", 0), s.get("y", 0))
            size = s.get("size") if s.get("size") is not None else (s.get("w", 0), s.get("h", 0))
            ox, oy = _int(off[0]), _int(off[1])
            sw, sh = _int(size[0]), _int(size[1])
            eid = s.get("element_id")
            is_anch = any(a["element_id"] == eid and a["offset"] == (ox, oy) and a["size"] == (sw, sh) for a in anchored_ids.values())
            if is_anch:
                sx = min(ox + extra_w, columns - sw)
                sy = max(occ_y, design_h + oy) if oy == 0 else occ_y  # fitted on FS1
                vis = 0 <= sx and 0 <= sy and sx + sw <= columns and sy + sh <= rows and eid not in existing
                if vis:
                    occ_y = sy + sh
                    existing.add(eid)
            else:
                base_y = (rows - bottom_reserved) if bottom_reserved > 0 else design_h
                sx, sy = ox, base_y + oy
                vis = 0 <= ox and 0 <= oy and ox + sw <= columns and design_h + oy + sh <= rows and sx + sw <= columns and sy + sh <= rows
            bottom_rows.append({"element_id": eid, "col": sx, "row": sy, "w": sw, "h": sh, "visible": vis, "mode": mode_tag})
    if bottom_rows:
        out["m_bottom"] = bottom_rows

    # Remaining zones (m_left, m_top, corners): PrepareContent  + GetSliceZoneOffset .
    for zone_key, zone in FILE_ZONES.items():
        if zone_key in ("m_right", "m_bottom"):
            continue
        rows_z = slices_by_zone.get(zone_key) or ()
        if not rows_z:
            continue
        ax, ay = zone_accumulator(zone, design_size, runtime_size)
        out[zone_key] = place_optional_slices(rows_z, design_size, runtime_size, zone, accum_x=ax, accum_y=ay)
    return out


def slot_to_runtime(zone_key, loc, design_size, runtime_size):
    """slot (stored x/y inside the zone) -> runtime column/row (uses shared place_zone_slots)."""
    placed = place_zone_slots(
        {zone_key: [{"element_id": loc.get("element_id") or "_slot",
                     "x": _int(loc.get("x")), "y": _int(loc.get("y")),
                     "w": _int(loc.get("width", loc.get("w"))), "h": _int(loc.get("height", loc.get("h")))}]},
        design_size, runtime_size,
    ).get(zone_key) or ()
    if placed:
        p = placed[0]
        return {"x": p["col"], "y": p["row"], "w": p["w"], "h": p["h"]}
    zone = FILE_ZONES[zone_key]
    ax, ay = zone_accumulator(zone, design_size, runtime_size)
    ox, oy = slice_zone_offset(zone, design_size, ax, ay)
    return {"x": ox + _int(loc.get("x")), "y": oy + _int(loc.get("y")),
            "w": _int(loc.get("width", loc.get("w"))), "h": _int(loc.get("height", loc.get("h")))}


def runtime_to_slot(zone_key, loc, design_size, runtime_size):
    """runtime column/row -> slot (stored x/y inside the zone)."""
    zone = FILE_ZONES[zone_key]
    ax, ay = zone_accumulator(zone, design_size, runtime_size)
    ox, oy = slice_zone_offset(zone, design_size, ax, ay)
    return {"x": _int(loc.get("x")) - ox, "y": _int(loc.get("y")) - oy}


def main_to_runtime(loc, design_size, runtime_size):
    """A main cell anchored to the right strip: the growth surplus shifts it right.

    Main cells that grow into the surplus are placed by ApplyGraph ;
    the caller takes those from `render.preview`. This is the strip conversion
    used to show a stored number next to its runtime column.
    """
    dx = max(0, _int(runtime_size[0]) - _int(design_size[0]))
    return {"x": _int(loc.get("x")) + dx, "y": _int(loc.get("y")),
            "w": _int(loc.get("width", loc.get("w"))), "h": _int(loc.get("height", loc.get("h")))}


def runtime_to_main(loc, design_size, runtime_size):
    """Inverse of main_to_runtime for a right-strip cell."""
    dx = max(0, _int(runtime_size[0]) - _int(design_size[0]))
    return {"x": _int(loc.get("x")) - dx, "y": _int(loc.get("y"))}


def design_extent(obj):
    """The file's own design grid: the greatest right/bottom edge in `m_gridComponents`."""
    cells = obj.get("m_gridComponents") or []
    cols = max([_int((c.get("m_location") or {}).get("x")) + _int((c.get("m_location") or {}).get("width")) for c in cells] or [1])
    rows = max([_int((c.get("m_location") or {}).get("y")) + _int((c.get("m_location") or {}).get("height")) for c in cells] or [1])
    return max(1, cols), max(1, rows)


def zones(obj):
    """{zone_key: [{element_id, x, y, width, height, min_w, min_h, max_w, max_h}]} for m_right/m_bottom."""
    out = {}
    slices = obj.get("m_optionalSlices") or {}
    for key in FILE_ZONES:
        rows = []
        for e in slices.get(key) or []:
            if not isinstance(e, dict) or "m_elementID" not in e:
                continue
            loc = e.get("m_location") or {}
            mn = e.get("m_minSize") or {}
            mx = e.get("m_maxSize") or {}
            rows.append({"element_id": e.get("m_elementID"),
                         "x": _int(loc.get("x")), "y": _int(loc.get("y")),
                         "width": _int(loc.get("width")), "height": _int(loc.get("height")),
                         "min_w": _int(mn.get("x"), 1), "min_h": _int(mn.get("y"), 1),
                         "max_w": _int(mx.get("x")), "max_h": _int(mx.get("y"))})
        out[key] = rows
    return out


def rects_overlap(a, b):
    """True when two (x, y, w, h) rectangles share area (touching edges do not count)."""
    return a[0] < b[0] + b[2] and b[0] < a[0] + a[2] and a[1] < b[1] + b[3] and b[1] < a[1] + a[3]


def overlaps(entries):
    """[(id_a, id_b, rect_a, rect_b)] for every partial or exact overlap in one space."""
    out = []
    for i in range(len(entries)):
        for j in range(i + 1, len(entries)):
            a, b = entries[i], entries[j]
            ra = (a["x"], a["y"], a["width"], a["height"])
            rb = (b["x"], b["y"], b["width"], b["height"])
            if rects_overlap(ra, rb):
                out.append((a.get("element_id"), b.get("element_id"), ra, rb))
    return out


def runtime_problems(hosts, cols, rows):
    """Overlaps and off-grid tiles in the runtime pane. `hosts` = [{element_id, x, y, w, h}].

    Called after conversion, so a design edit that grows or compacts into a
    collision is blocked by the runtime result, not by the stored number.
    """
    entries = [{"element_id": h.get("element_id"), "x": _int(h.get("x")), "y": _int(h.get("y")),
                "width": _int(h.get("w")), "height": _int(h.get("h"))} for h in hosts or []]
    problems = []
    for e in entries:
        if e["x"] < 0 or e["y"] < 0 or e["x"] + e["width"] > cols or e["y"] + e["height"] > rows:
            problems.append("cell %s at %d,%d %dx%d is outside the %dx%d runtime grid"
                            % (e["element_id"], e["x"], e["y"], e["width"], e["height"], cols, rows))
    for a, b, ra, rb in overlaps(entries):
        problems.append("runtime cells %s %s and %s %s overlap" % (a, ra, b, rb))
    return problems
