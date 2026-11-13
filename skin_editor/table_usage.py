"""Reverse linkage for table views: which layouts (and through them which tiles and compositions) show a given ui-tableviews view.

A layout picks its table view with a visual-scripting `InitFunction` on the `SI.Bindable.StreamedTable` element. The argument bytes
(`m_inputs.m_variable.m_argumentBytes`) spell an asset reference ending in the view's 32-hex GUID, so the view GUID can be read out of
the bytes and matched against `data_guids`. Nothing in the index links a view to a layout by an ordinary reference, so this is the only
route. 355 of the 897 views are reached this way (528 references); the rest are chosen by code or by saved user views.

Layout -> tile: a layout named like `FirstTeamTile_4x4` is the (4, 4) configuration of the tile descriptions whose
`tile_description_configs` point at that asset. Tile description -> screens: `cell_configs` (every composition cell that offers the tile).
A cell offers a tile at all its configurations; which one is drawn depends on the cell size at the breakpoint, so `screens` lists where the
tile CAN appear, `sizes` the configuration this layout is.

Read-only: the sqlite is opened with mode=ro."""
import collections
import json
import re
import sqlite3
from pathlib import Path

HEX = re.compile(r"[0-9a-f]{32}")


def guids_in_arguments(attrs):
    """Every 32-hex GUID spelled by an `m_argumentBytes` list anywhere inside one element's attribute tree."""
    def walk(o):
        if isinstance(o, dict):
            for k, v in o.items():
                if k == "m_argumentBytes" and isinstance(v, list):
                    yield from HEX.findall(bytes(x for x in v if isinstance(x, int) and 0 <= x < 256).decode("latin-1"))
                else:
                    yield from walk(v)
        elif isinstance(o, list):
            for v in o:
                yield from walk(v)
    return list(walk(attrs))


def connect(path):
    p = Path(path)
    if not p.is_file():
        raise FileNotFoundError("layout index not found: %s" % p)
    return sqlite3.connect("file:%s?mode=ro" % p.as_posix(), uri=True)


def build(db):
    """{view name: [{layout, element, tiles: [{description, size, screens: [...]}]}]} for every table view reachable through a layout."""
    q = lambda s, *a: db.execute(s, a).fetchall()
    views = {g: n for g, n in q("select guid, name from data_guids where bundle like '%tableviews%'")}
    layout_ids = {n: i for i, n in q("select id, name from assets")}
    uses = collections.defaultdict(list)
    for aid, an, et, en, aj in q("select e.asset_id, (select name from assets where id=e.asset_id), e.type, e.name, e.attrs_json from elements e "
                                 "where e.attrs_json like '%argumentBytes%'"):
        for g in dict.fromkeys(guids_in_arguments(json.loads(aj))):
            if g in views:
                uses[views[g]].append({"layout": an, "asset_id": aid, "element": et + ("#" + en if en else "")})
    screens = {}
    out = {}
    for view, lst in uses.items():
        rows = []
        for u in lst:
            tiles = []
            for dname, w, h in q("select d.name, t.size_w, t.size_h from tile_description_configs t join tile_descriptions d on d.path_id=t.desc_path_id "
                                 "where t.to_asset=?", u["asset_id"]):
                if dname not in screens:
                    screens[dname] = sorted({r[0] for r in q("select co.name from cell_configs cc join compositions co on co.path_id=cc.composition_path_id "
                                                              "where cc.description_name=?", dname)})
                tiles.append({"description": dname, "size": [w, h], "screens": screens[dname]})
            rows.append({"layout": u["layout"], "element": u["element"], "tiles": tiles})
        out[view] = rows
    return out


def summary(usage, name):
    """One line a person can read: where a view is used."""
    rows = usage.get(name)
    if not rows:
        return "not referenced by any layout in the index (chosen by code or by a saved user view)"
    parts = []
    for r in rows:
        t = "; ".join("%s %dx%d in %d composition(s)" % (x["description"], x["size"][0], x["size"][1], len(x["screens"])) for x in r["tiles"])
        parts.append(r["layout"] + (" [" + t + "]" if t else " (not a tile layout)"))
    return ", ".join(parts)


def save(path, usage, game_build):
    Path(path).write_text(json.dumps({"schema": "fm-table-view-usage/1", "game_build": game_build, "views": usage}, indent=1, sort_keys=True), encoding="utf-8")


def load(path):
    p = Path(path)
    return json.loads(p.read_text(encoding="utf-8"))["views"] if p.is_file() else None
