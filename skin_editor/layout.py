"""Selector reach in the game's visual trees (check 5 of tools/verify_build.py, typetree part only).
Reads the ui-visualtreeassets bundles from the game folder; never writes there."""
import hashlib
import json
from pathlib import Path

from . import bundles
from . import token_patch as tp


def load_trees(aa_dir, cache_dir, progress=None):
    files = sorted(Path(aa_dir).glob("ui-visualtreeassets*.bundle"))
    if not files:
        raise RuntimeError("no ui-visualtreeassets bundles in " + str(aa_dir))
    key = hashlib.sha256(repr([(f.name, f.stat().st_size, f.stat().st_mtime_ns) for f in files]).encode()).hexdigest()[:16]
    cache = Path(cache_dir) / ("layout-%s.json" % key)
    if cache.is_file():
        return json.loads(cache.read_text(encoding="utf-8"))
    trees = []
    for k, f in enumerate(files):
        if progress:
            progress("reading " + f.name, k / len(files))
        for name, nodes in bundles.read_visual_trees(f):
            trees.append([f.name.replace(".bundle", "") + ":" + name, nodes])
    cache.write_text(json.dumps(trees), encoding="utf-8")
    return trees


def _ok(node, parts):
    for typ, val in parts:
        if typ == tp.P_ID and node[1] != val:
            return False
        if typ == tp.P_CLASS and val not in node[2]:
            return False
        if typ == tp.P_ELEMENT and node[0] != val:
            return False
    return True  # pseudo-classes and wildcards are runtime states


def chain_matches(nodes, chain):
    hits = 0
    for i, n in enumerate(nodes):
        if not _ok(n, chain[-1][1]):
            continue
        cur, ok, k = i, True, len(chain) - 1
        while k > 0:
            rel, want, p = chain[k][0], chain[k - 1][1], nodes[cur][3]
            if rel == 1:
                if p < 0 or not _ok(nodes[p], want):
                    ok = False
                    break
            else:
                while p >= 0 and not _ok(nodes[p], want):
                    p = nodes[p][3]
                if p < 0:
                    ok = False
                    break
            cur = p
            k -= 1
        hits += ok
    return hits


def reach(scoped_rules, trees):
    """Per selector branch: matches inside single templates, and parts found in no template at all."""
    names = {n[1] for _, ns in trees for n in ns}
    classes = {c for _, ns in trees for n in ns for c in n[2]}
    types = {n[0] for _, ns in trees for n in ns}
    rows = []
    for r in scoped_rules:
        if r["selector"].strip() == ":root":
            continue
        for branch, chain in zip([s.strip() for s in r["selector"].split(",") if s.strip()], tp.parse_selector(r["selector"])):
            hits, where = 0, []
            for asset, ns in trees:
                n = chain_matches(ns, chain)
                if n:
                    hits += n
                    if len(where) < 5:
                        where.append(asset)
            missing = []
            for _rel, parts in chain:
                for typ, val in parts:
                    if typ == tp.P_ID and val not in names:
                        missing.append("#" + val)
                    elif typ == tp.P_CLASS and val not in classes:
                        missing.append("." + val)
                    elif typ == tp.P_ELEMENT and val not in types:
                        missing.append(val)
            rows.append({"branch": branch, "hits": hits, "templates": where, "missing": sorted(set(missing))})
    return {"trees": len(trees), "no_match": sum(r["hits"] == 0 for r in rows), "rows": rows}
