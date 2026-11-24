"""Asset registry and bundle inventory store (Stage 4B; docs/rea/STAGE-4A-ARCHITECTURE.md sections 6.2 and 6.3). SQLite, standard library only.

One database per installation: `<workspace>/inventory/<install_id>/registry.sqlite`. It is a DERIVED CACHE: every row is read from the game's bundles by
`inventory.py` and the whole file can be deleted and rebuilt. Nothing here reads or writes a game folder.

Identity. An asset is `AssetKey(install_id, bundle, cab, path_id)`. The five identifier kinds stay separate columns and are never interchangeable:
  bundle      physical bundle, relative path under the platform folder     cab        the serialized file inside the bundle (CAB-<hash>)
  path_id     object id in that file (64-bit, kept as a decimal STRING)    type       Unity class name; class_id is its number
  guid        the 32-hex key the bundle's AssetBundle container lists for the asset (Addressables key); empty when the container key is not a GUID
  ref_guid    a GUID the asset REFERENCES (a panel's UXML GUID); not the asset's own GUID
  panel_id    a panel's logical id (the `m_id` of a panel description); not a GUID and not a PathID
  name        display name (a hint, not an identity)
Lightweight rows only: no typetree is stored here (typetrees are read on demand)."""
import json
import sqlite3
import time
from collections import namedtuple
from pathlib import Path

SCHEMA_VERSION = 3          # 2: assets.role, edges, edge_candidates, graph_state (the dependency graph, Stage 4C); a version 1 database is upgraded in place
                             # 3: transactions, file_ops (the installation transaction journal, Stage 4F - additive, no existing column changes)

AssetKey = namedtuple("AssetKey", "install_id bundle cab path_id")

BUNDLE_STATES = ("unscanned", "scanning", "valid", "partially_valid", "unsupported", "corrupt", "missing")

# the installation transaction journal (Stage 4F). The journal lives in the SAME per-installation database as the
# inventory and the graph: one database system, one identity (install_id). transactions is the durable transaction
# state machine; file_ops holds one row per target file (see skin_editor/installtx.py for the lifecycle).
_DDL = """
CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT);
CREATE TABLE IF NOT EXISTS bundles (
    rel_path TEXT PRIMARY KEY, abs_path TEXT, filename TEXT, size INTEGER, mtime_ns INTEGER, sha256 TEXT, crc32 TEXT, cab TEXT, unity_version TEXT,
    kind TEXT, object_count INTEGER, type_counts TEXT, dependencies TEXT, externals TEXT, state TEXT, error TEXT,
    scanned_utc TEXT, verified_utc TEXT, catalog TEXT, catalog_crc_status TEXT, manifest TEXT, manifest_status TEXT);
CREATE TABLE IF NOT EXISTS assets (
    bundle TEXT NOT NULL, cab TEXT NOT NULL, path_id TEXT NOT NULL, class_id INTEGER, type TEXT, name TEXT, guid TEXT, ref_guid TEXT, panel_id TEXT, container TEXT, role TEXT,
    PRIMARY KEY (bundle, cab, path_id));
CREATE INDEX IF NOT EXISTS assets_name ON assets (name COLLATE NOCASE);
CREATE INDEX IF NOT EXISTS assets_type ON assets (type);
CREATE INDEX IF NOT EXISTS assets_guid ON assets (guid);
CREATE INDEX IF NOT EXISTS assets_ref_guid ON assets (ref_guid);
CREATE INDEX IF NOT EXISTS assets_panel ON assets (panel_id);
CREATE INDEX IF NOT EXISTS assets_path ON assets (path_id);
CREATE TABLE IF NOT EXISTS edges (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    src_bundle TEXT NOT NULL, src_cab TEXT NOT NULL DEFAULT '', src_path_id TEXT NOT NULL DEFAULT '',          -- src_path_id '' = a bundle-level edge
    kind TEXT NOT NULL,                                                                                       -- pptr | guid_reference | bundle_dependency | external_file
    relation TEXT,                                                                                            -- a label derived from the roles of both ends once resolved
    t_file_id INTEGER NOT NULL DEFAULT -1, t_path_id TEXT NOT NULL DEFAULT '', t_guid TEXT NOT NULL DEFAULT '', t_cab TEXT NOT NULL DEFAULT '',   -- the raw target exactly as serialized
    direct INTEGER NOT NULL DEFAULT 1, count INTEGER NOT NULL DEFAULT 1, provenance TEXT, samples TEXT,
    dst_bundle TEXT, dst_cab TEXT, dst_path_id TEXT, resolution TEXT NOT NULL DEFAULT 'pending', reason TEXT, basis TEXT,
    UNIQUE (src_bundle, src_cab, src_path_id, kind, t_file_id, t_path_id, t_guid, t_cab));
CREATE INDEX IF NOT EXISTS edges_src ON edges (src_bundle, src_cab, src_path_id);
CREATE INDEX IF NOT EXISTS edges_dst ON edges (dst_bundle, dst_cab, dst_path_id);
CREATE INDEX IF NOT EXISTS edges_res ON edges (resolution);
CREATE TABLE IF NOT EXISTS edge_candidates (edge_id INTEGER NOT NULL, bundle TEXT, cab TEXT, path_id TEXT, role TEXT);
CREATE INDEX IF NOT EXISTS cand_edge ON edge_candidates (edge_id);
CREATE INDEX IF NOT EXISTS cand_target ON edge_candidates (bundle, cab, path_id);
CREATE TABLE IF NOT EXISTS graph_state (bundle TEXT PRIMARY KEY, sha256 TEXT, state TEXT, error TEXT, built_utc TEXT, edges INTEGER, note TEXT);
CREATE TABLE IF NOT EXISTS scans (
    id INTEGER PRIMARY KEY AUTOINCREMENT, started_utc TEXT, finished_utc TEXT, state TEXT, mode TEXT, summary TEXT);
CREATE TABLE IF NOT EXISTS transactions (
    tx_id TEXT PRIMARY KEY, install_id TEXT NOT NULL, package_id TEXT, package_schema INTEGER, package_dir TEXT, project TEXT,
    game_build TEXT, steam_build_id TEXT, catalog_sha256 TEXT, manifest_sha256 TEXT,
    state TEXT NOT NULL, created_utc TEXT, updated_utc TEXT, initiating TEXT, preflight TEXT, overrides TEXT,
    completed_utc TEXT, error TEXT, recovery TEXT);
CREATE INDEX IF NOT EXISTS tx_install ON transactions (install_id, state);
CREATE TABLE IF NOT EXISTS file_ops (
    tx_id TEXT NOT NULL, op_index INTEGER NOT NULL, rel_path TEXT NOT NULL, op TEXT NOT NULL,
    target_path TEXT, original_exists INTEGER, original_sha256 TEXT, original_size INTEGER, original_mtime_ns INTEGER,
    backup_path TEXT, backup_sha256 TEXT, staged_path TEXT, staged_sha256 TEXT,
    expected_sha256 TEXT, actual_sha256 TEXT, state TEXT NOT NULL, replaced_utc TEXT,
    verify TEXT, rollback_state TEXT, error TEXT,
    PRIMARY KEY (tx_id, op_index));
"""

_BUNDLE_COLS = ("rel_path abs_path filename size mtime_ns sha256 crc32 cab unity_version kind object_count type_counts dependencies externals state error "
                "scanned_utc verified_utc catalog catalog_crc_status manifest manifest_status").split()
_JSON_COLS = ("type_counts", "dependencies", "externals", "catalog", "manifest")


def _now():
    return time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())


def db_path(ws, install_id):
    d = Path(ws.root) / "inventory" / install_id
    d.mkdir(parents=True, exist_ok=True)
    return d / "registry.sqlite"


class Registry:
    """Thin wrapper over one SQLite file. Every method opens its own connection (the engine's job thread and its request threads both use it)."""

    def __init__(self, path, install_id):
        self.path, self.install_id = Path(path), install_id
        with self._db() as db:
            db.executescript(_DDL)
            cur = db.execute("SELECT value FROM meta WHERE key='schema'").fetchone()
            if cur is None:
                db.execute("INSERT INTO meta VALUES ('schema', ?)", (str(SCHEMA_VERSION),))
                db.execute("INSERT OR REPLACE INTO meta VALUES ('install_id', ?)", (install_id,))
            elif int(cur[0]) == 1:                               # upgrade a Stage 4B database: it is a cache, the new column and tables are additive
                if "role" not in [r[1] for r in db.execute("PRAGMA table_info(assets)")]:
                    db.execute("ALTER TABLE assets ADD COLUMN role TEXT")
                db.execute("UPDATE meta SET value=? WHERE key='schema'", (str(SCHEMA_VERSION),))
            elif int(cur[0]) == 2:                               # Stage 4F: the transaction tables are additive (created above); nothing else changes
                db.execute("UPDATE meta SET value=? WHERE key='schema'", (str(SCHEMA_VERSION),))
            elif int(cur[0]) != SCHEMA_VERSION:
                raise RuntimeError("registry schema %s is not supported (expected %d); delete %s, it is a rebuildable cache" % (cur[0], SCHEMA_VERSION, self.path))

    @classmethod
    def for_install(cls, ws, install_id):
        return cls(db_path(ws, install_id), install_id)

    def _db(self):
        con = sqlite3.connect(str(self.path), timeout=30)
        con.row_factory = sqlite3.Row
        return closing_commit(con)

    # ---- bundles
    def get_bundle(self, rel):
        with self._db() as db:
            r = db.execute("SELECT * FROM bundles WHERE rel_path=?", (rel,)).fetchone()
        return _bundle(r) if r else None

    def all_bundles(self):
        with self._db() as db:
            return {r["rel_path"]: _bundle(r) for r in db.execute("SELECT * FROM bundles")}

    def put_bundle(self, rec, assets=None):
        """Store one bundle record; when `assets` is given the bundle's rows are replaced by it (one transaction: a cancelled or failed scan never leaves half a bundle)."""
        row = {c: rec.get(c) for c in _BUNDLE_COLS}
        for c in _JSON_COLS:
            row[c] = json.dumps(row[c], sort_keys=True) if row[c] is not None else None
        with self._db() as db:
            db.execute("INSERT OR REPLACE INTO bundles (%s) VALUES (%s)" % (",".join(_BUNDLE_COLS), ",".join("?" * len(_BUNDLE_COLS))), [row[c] for c in _BUNDLE_COLS])
            if assets is not None:
                db.execute("DELETE FROM assets WHERE bundle=?", (rec["rel_path"],))
                db.executemany("INSERT OR REPLACE INTO assets (bundle,cab,path_id,class_id,type,name,guid,ref_guid,panel_id,container) VALUES (?,?,?,?,?,?,?,?,?,?)",
                               [(rec["rel_path"], a["cab"], str(a["path_id"]), a.get("class_id"), a.get("type"), a.get("name"), a.get("guid"), a.get("ref_guid"),
                                 a.get("panel_id"), a.get("container")) for a in assets])

    def mark_missing(self, present):
        """Bundles in the database that are no longer on disk: state 'missing' (the record and its assets stay as evidence of what was there). Returns their paths."""
        gone = []
        with self._db() as db:
            for (rel,) in db.execute("SELECT rel_path FROM bundles WHERE state != 'missing'").fetchall():
                if rel not in present:
                    gone.append(rel)
            for rel in gone:
                db.execute("UPDATE bundles SET state='missing', scanned_utc=? WHERE rel_path=?", (_now(), rel))
        return gone

    def list_bundles(self, q=None, state=None, kind=None, crc_status=None, limit=200, offset=0):
        where, args = [], []
        if q:
            where.append("(filename LIKE ? ESCAPE '\\' OR rel_path LIKE ? ESCAPE '\\')")
            like = "%" + q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
            args += [like, like]
        if state:
            where.append("state=?"); args.append(state)
        if kind:
            where.append("kind=?"); args.append(kind)
        if crc_status:
            where.append("catalog_crc_status=?"); args.append(crc_status)
        sql = "FROM bundles" + (" WHERE " + " AND ".join(where) if where else "")
        with self._db() as db:
            total = db.execute("SELECT COUNT(*) " + sql, args).fetchone()[0]
            rows = db.execute("SELECT * " + sql + " ORDER BY rel_path LIMIT ? OFFSET ?", args + [int(limit), int(offset)]).fetchall()
        return {"total": total, "bundles": [_bundle(r) for r in rows]}

    def summary(self):
        with self._db() as db:
            states = {r[0]: r[1] for r in db.execute("SELECT state, COUNT(*) FROM bundles GROUP BY state")}
            n_assets = db.execute("SELECT COUNT(*) FROM assets").fetchone()[0]
            size = db.execute("SELECT COALESCE(SUM(size),0) FROM bundles WHERE state != 'missing'").fetchone()[0]
            last = db.execute("SELECT * FROM scans ORDER BY id DESC LIMIT 1").fetchone()
        return {"bundles": sum(states.values()), "states": states, "assets": n_assets, "bytes": size,
                "last_scan": ({"id": last["id"], "started_utc": last["started_utc"], "finished_utc": last["finished_utc"], "state": last["state"], "mode": last["mode"],
                               "summary": json.loads(last["summary"]) if last["summary"] else None} if last else None)}

    # ---- scans
    def begin_scan(self, mode):
        with self._db() as db:
            cur = db.execute("INSERT INTO scans (started_utc, state, mode) VALUES (?, 'scanning', ?)", (_now(), mode))
            return cur.lastrowid

    def finish_scan(self, scan_id, state, summary):
        with self._db() as db:
            db.execute("UPDATE scans SET finished_utc=?, state=?, summary=? WHERE id=?", (_now(), state, json.dumps(summary, sort_keys=True), scan_id))

    # ---- assets
    def search_assets(self, q=None, type=None, bundle=None, guid=None, path_id=None, panel_id=None, ref_guid=None, limit=100, offset=0):
        where, args = [], []
        if q:
            where.append("name LIKE ? ESCAPE '\\'")
            args.append("%" + q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%")
        for col, val in (("type", type), ("bundle", bundle), ("guid", guid), ("path_id", path_id), ("panel_id", panel_id), ("ref_guid", ref_guid)):
            if val not in (None, ""):
                where.append("%s=?" % col)
                args.append(str(val).lower() if col in ("guid", "ref_guid") else str(val))
        sql = "FROM assets" + (" WHERE " + " AND ".join(where) if where else "")
        with self._db() as db:
            total = db.execute("SELECT COUNT(*) " + sql, args).fetchone()[0]
            rows = db.execute("SELECT * " + sql + " ORDER BY bundle, name, path_id LIMIT ? OFFSET ?", args + [int(limit), int(offset)]).fetchall()
        return {"total": total, "assets": [self._asset(r) for r in rows]}

    def get_asset(self, bundle, cab, path_id):
        with self._db() as db:
            r = db.execute("SELECT * FROM assets WHERE bundle=? AND cab=? AND path_id=?", (bundle, cab, str(path_id))).fetchone()
        return self._asset(r) if r else None

    def type_counts(self, bundle=None):
        with self._db() as db:
            if bundle:
                rows = db.execute("SELECT type, COUNT(*) FROM assets WHERE bundle=? GROUP BY type ORDER BY 2 DESC", (bundle,)).fetchall()
            else:
                rows = db.execute("SELECT type, COUNT(*) FROM assets GROUP BY type ORDER BY 2 DESC").fetchall()
        return {r[0]: r[1] for r in rows}

    def _asset(self, r):
        d = {k: r[k] for k in r.keys()}
        d["key"] = AssetKey(self.install_id, d["bundle"], d["cab"], d["path_id"])._asdict()
        return d


    # ---- dependency graph storage (Stage 4C; algorithms live in depgraph.py)
    def graph_states(self):
        with self._db() as db:
            return {r["bundle"]: {k: r[k] for k in r.keys()} for r in db.execute("SELECT * FROM graph_state")}

    def replace_bundle_graph(self, bundle, sha256, edges, roles, state, error=None, note=None):
        """ONE transaction: the bundle's edges and asset roles are replaced together, so a failure leaves the previous graph of the bundle, never a partial one.
        `edges` are raw-reference dicts (see depgraph.Edge); `roles` {(cab, path_id): role}."""
        cols = ("src_bundle src_cab src_path_id kind relation t_file_id t_path_id t_guid t_cab direct count provenance samples").split()
        with self._db() as db:
            db.execute("DELETE FROM edge_candidates WHERE edge_id IN (SELECT id FROM edges WHERE src_bundle=?)", (bundle,))
            db.execute("DELETE FROM edges WHERE src_bundle=?", (bundle,))
            db.executemany("INSERT INTO edges (%s) VALUES (%s)" % (",".join(cols), ",".join("?" * len(cols))), [tuple(e.get(c) for c in cols) for e in edges])
            if roles is not None:
                db.execute("UPDATE assets SET role=NULL WHERE bundle=?", (bundle,))
                db.executemany("UPDATE assets SET role=? WHERE bundle=? AND cab=? AND path_id=?", [(r, bundle, c, str(pid)) for (c, pid), r in roles.items()])
            db.execute("INSERT OR REPLACE INTO graph_state (bundle, sha256, state, error, built_utc, edges, note) VALUES (?,?,?,?,?,?,?)",
                       (bundle, sha256, state, error, _now(), len(edges), note))

    def fail_bundle_graph(self, bundle, sha256, error):
        """A bundle whose graph could not be built: its edges are removed (no partial edges), the failure is recorded."""
        with self._db() as db:
            db.execute("DELETE FROM edge_candidates WHERE edge_id IN (SELECT id FROM edges WHERE src_bundle=?)", (bundle,))
            db.execute("DELETE FROM edges WHERE src_bundle=?", (bundle,))
            db.execute("INSERT OR REPLACE INTO graph_state (bundle, sha256, state, error, built_utc, edges, note) VALUES (?,?,'failed',?,?,0,NULL)", (bundle, sha256, error, _now()))

    def drop_missing_graph(self, present):
        """Graph rows of bundles that are no longer inventoried as present: removed with their edges."""
        with self._db() as db:
            gone = [r[0] for r in db.execute("SELECT bundle FROM graph_state") if r[0] not in present]
            for b in gone:
                db.execute("DELETE FROM edge_candidates WHERE edge_id IN (SELECT id FROM edges WHERE src_bundle=?)", (b,))
                db.execute("DELETE FROM edges WHERE src_bundle=?", (b,))
                db.execute("DELETE FROM graph_state WHERE bundle=?", (b,))
        return gone

    def graph_summary(self):
        with self._db() as db:
            states = {r[0]: r[1] for r in db.execute("SELECT state, COUNT(*) FROM graph_state GROUP BY state")}
            res = {r[0]: r[1] for r in db.execute("SELECT resolution, COUNT(*) FROM edges GROUP BY resolution")}
            kinds = {r[0]: r[1] for r in db.execute("SELECT kind, COUNT(*) FROM edges GROUP BY kind")}
            n = db.execute("SELECT COUNT(*) FROM edges").fetchone()[0]
        return {"bundles_by_state": states, "edges": n, "by_resolution": res, "by_kind": kinds}

    # ---- catalog / manifest integrity (Stage 4E; a targeted update so adding metadata never reparses a bundle)
    def set_integrity(self, rel, catalog, catalog_crc_status, manifest, manifest_status):
        """One bundle's catalog record, catalog-CRC comparison status, manifest.dat entry and manifest status, in one
        UPDATE. No asset rows, no other column: a metadata-only change is a metadata-only write."""
        with self._db() as db:
            db.execute("UPDATE bundles SET catalog=?, catalog_crc_status=?, manifest=?, manifest_status=? WHERE rel_path=?",
                       (json.dumps(catalog, sort_keys=True) if catalog is not None else None, catalog_crc_status,
                        json.dumps(manifest, sort_keys=True) if manifest is not None else None, manifest_status, rel))

    def set_integrity_meta(self, identity, utc):
        """Which catalog and manifest.dat this database's integrity columns were annotated against, and when."""
        with self._db() as db:
            db.execute("INSERT OR REPLACE INTO meta VALUES ('integrity', ?)", (json.dumps(dict(identity, annotated_utc=utc), sort_keys=True),))

    def get_integrity_meta(self):
        with self._db() as db:
            r = db.execute("SELECT value FROM meta WHERE key='integrity'").fetchone()
        return json.loads(r[0]) if r else None

    def integrity_counts(self):
        """{status: count} for the two integrity columns, over present bundles only."""
        with self._db() as db:
            cat = {r[0]: r[1] for r in db.execute("SELECT catalog_crc_status, COUNT(*) FROM bundles WHERE state != 'missing' GROUP BY catalog_crc_status")}
            man = {r[0]: r[1] for r in db.execute("SELECT manifest_status, COUNT(*) FROM bundles WHERE state != 'missing' GROUP BY manifest_status")}
        return {"catalog_crc_status": cat, "manifest_status": man}

    # ---- the installation transaction journal (Stage 4F; the state machine lives in installtx.py)
    def begin_tx(self, tx):
        """Insert one transaction record. `tx` is the column dict; unknown keys are ignored."""
        cols = ("tx_id install_id package_id package_schema package_dir project game_build steam_build_id catalog_sha256 "
                "manifest_sha256 state created_utc updated_utc initiating preflight overrides completed_utc error recovery").split()
        with self._db() as db:
            db.execute("INSERT INTO transactions (%s) VALUES (%s)" % (",".join(cols), ",".join("?" * len(cols))),
                       [tx.get(c) for c in cols])

    def update_tx(self, tx_id, **fields):
        """Durable state transition: every write updates updated_utc; unknown fields are refused."""
        fields = dict(fields, updated_utc=time.strftime("%Y%m%dT%H%M%SZ", time.gmtime()))
        allowed = set("state preflight overrides completed_utc error recovery package_dir".split())
        bad = set(fields) - allowed - {"updated_utc"}
        if bad:
            raise ValueError("unknown transaction fields: " + ", ".join(sorted(bad)))
        with self._db() as db:
            db.execute("UPDATE transactions SET %s WHERE tx_id=?" % ", ".join("%s=?" % k for k in fields),
                       list(fields.values()) + [tx_id])

    def get_tx(self, tx_id):
        with self._db() as db:
            r = db.execute("SELECT * FROM transactions WHERE tx_id=?", (tx_id,)).fetchone()
        return dict(r) if r else None

    def list_txs(self, states=None, limit=100):
        """Transactions newest first, optionally filtered by state. `error`/`preflight`/`overrides` stay lazily
        unparsed (they can be large); transaction() gives the parsed detail."""
        with self._db() as db:
            if states:
                rows = db.execute("SELECT * FROM transactions WHERE state IN (%s) ORDER BY created_utc DESC, tx_id DESC LIMIT ?"
                                  % ",".join("?" * len(states)), list(states) + [int(limit)]).fetchall()
            else:
                rows = db.execute("SELECT * FROM transactions ORDER BY created_utc DESC, tx_id DESC LIMIT ?", (int(limit),)).fetchall()
        return [dict(r) for r in rows]

    def put_op(self, tx_id, op_index, op):
        """Insert or replace one file operation row (the journal of a destructive step)."""
        cols = ("rel_path op target_path original_exists original_sha256 original_size original_mtime_ns backup_path backup_sha256 "
                "staged_path staged_sha256 expected_sha256 actual_sha256 state replaced_utc verify rollback_state error").split()
        with self._db() as db:
            db.execute("INSERT OR REPLACE INTO file_ops (tx_id, op_index, %s) VALUES (%s)"
                       % (",".join(cols), ",".join("?" * (len(cols) + 2))),
                       [tx_id, int(op_index)] + [op.get(c) for c in cols])

    def get_ops(self, tx_id):
        with self._db() as db:
            return [dict(r) for r in db.execute("SELECT * FROM file_ops WHERE tx_id=? ORDER BY op_index", (tx_id,))]


class closing_commit:
    """Context manager: a connection that commits on success, rolls back on error and always closes."""

    def __init__(self, con):
        self.con = con

    def __enter__(self):
        return self.con

    def __exit__(self, et, ev, tb):
        try:
            if et is None:
                self.con.commit()
            else:
                self.con.rollback()
        finally:
            self.con.close()
        return False


def _bundle(r):
    d = {k: r[k] for k in r.keys()}
    for c in _JSON_COLS:
        d[c] = json.loads(d[c]) if d.get(c) else None
    return d
