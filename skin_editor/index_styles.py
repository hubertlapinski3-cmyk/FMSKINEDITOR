"""Style index: tokens, alias chains, reach, literals. LEARNINGS section 7.1."""
import json
import re

from . import bundles, colour, uss

VAR_RE = re.compile(r"var\((--[\w-]+)")
REFERENCE_SHEET = "AlwaysAppliedStyleSheet"
CACHE_SCHEMA = 3      # 2: literals carry the decoded alpha float. 3: out-of-range bundle colours are decode
                      # failures, not rescaled. Older caches are never migrated, only rebuilt from the bundles.


def sheet_entry(bundle, tree):
    sel = uss.selector_map(tree)
    rules, failures = [], []
    for i, r in enumerate(tree.get("m_Rules", [])):
        props = []
        for p in r.get("m_Properties", []):
            bad = []
            txt, cols = uss.value_text(tree, p.get("m_Values", []), bad)
            props.append([uss.prop_name(p), txt, cols])
            for f in bad:      # collected, not raised: the whole index is reported together
                failures.append({"rule": i, "selector": ", ".join(uss.selector_text(c) for c in sel[i]),
                                 "property": uss.prop_name(p), "index": f["index"], "raw": f["raw"]})
        rules.append({"i": i, "s": [uss.selector_text(c) for c in sel[i]],
                      "t": uss.is_token_rule(sel[i]), "p": props})
    return {"bundle": bundle, "name": tree.get("m_Name", ""), "rules": rules, "failures": failures}


class StyleIndex:
    def __init__(self, sheets, meta=None):
        self.sheets, self.meta = sheets, meta or {}
        self.defs, self.def_cols, self.uses, self.literals, self.by_rgb = {}, {}, {}, {}, {}
        for sh in sheets:
            for r in sh["rules"]:
                sel = ", ".join(r["s"])
                for name, val, cols in r["p"]:
                    is_def = r["t"] and name.startswith("--")
                    if is_def:
                        self.defs.setdefault(name, {})[sh["name"]] = val
                        self.def_cols.setdefault(name, {})[sh["name"]] = cols
                    use = {"sheet": sh["name"], "selector": sel, "selectors": r["s"], "property": name,
                           "value": val, "token_def": is_def}
                    for v in set(VAR_RE.findall(val)):
                        self.uses.setdefault(v, []).append(use)
                    for rgb, a in {(c[0], c[1]) for c in cols}:     # full RGBA: alpha is part of the key
                        c = colour.from_obj({"rgb": rgb, "a": a})
                        hit = dict(use, rgb=rgb, a=a)
                        self.literals.setdefault(colour.key(c), []).append(hit)
                        self.by_rgb.setdefault(rgb, []).append(hit)
        self._reach = {}
        # bundle colours outside 0..1: not decoded, not offered as literals, never written by a build
        self.failures = []
        for sh in sheets:
            for f in sh.get("failures", []):
                cls, display = colour.classify_out_of_range(f["raw"])
                self.failures.append(dict(f, sheet=sh["name"], bundle=sh["bundle"], **{"class": cls, "display": display}))

    def quarantine(self):
        """Quarantined bundle colours by class: entries, unique raw quadruplets, and the rows."""
        classes = {}
        for f in self.failures:
            c = classes.setdefault(f["class"], {"entries": 0, "colours": set()})
            c["entries"] += 1
            c["colours"].add(tuple(f["raw"]))
        return {"count": len(self.failures), "unique": len({tuple(f["raw"]) for f in self.failures}),
                "classes": {k: {"entries": v["entries"], "unique": len(v["colours"])} for k, v in classes.items()},
                "rows": self.failures[:200]}

    def value(self, token):
        d = self.defs.get(token)
        if not d:
            return None
        return d.get(REFERENCE_SHEET, next(iter(d.values())))

    def value_colour(self, token):
        """Canonical colour object when the token's reference value is one literal colour, else None."""
        d, v = self.def_cols.get(token), self.value(token)
        if not d or v is None or v.startswith("var(") or " " in v:
            return None
        cols = d.get(REFERENCE_SHEET, next(iter(d.values())))
        return {"rgb": cols[0][0], "a": cols[0][1]} if len(cols) == 1 else None

    def chain(self, token):
        """[token, alias, ...] and the resolved colour object with its full alpha (or None)."""
        seen = [token]
        while True:
            v = self.value(seen[-1])
            if v is None:
                return seen, None
            m = re.fullmatch(r"var\((--[\w-]+)\)", v)
            if not m:
                return seen, self.value_colour(seen[-1])
            if m.group(1) in seen:
                return seen, None
            seen.append(m.group(1))

    def reach(self, token, _stack=()):
        """Set of (sheet, selector, property) painted through this token, following aliases."""
        if token in self._reach:
            return self._reach[token]
        out = set()
        for u in self.uses.get(token, []):
            if u["token_def"]:
                if u["property"] not in _stack and u["property"] != token:
                    out |= self.reach(u["property"], _stack + (token,))
            else:
                out.add((u["sheet"], u["selector"], u["property"]))
        if not _stack:
            self._reach[token] = out
        return out

    def token_row(self, name):
        d = self.defs[name]
        chain, resolved = self.chain(name)
        return {"name": name, "value": self.value(name), "resolved": resolved, "chain": chain,
                "sheets": len(d), "conflict": len(set(d.values())) > 1, "reach": len(self.reach(name))}

    def tokens(self, q="", colours_only=False, limit=400):
        """q matches the token name, its value text, or the hex code it resolves to through aliases
        (#RRGGBB, RRGGBB, or the 8-digit form with the alpha byte; case-insensitive, # optional)."""
        q = q.lower().strip()
        hexq = q.lstrip("#") if re.fullmatch(r"#?[0-9a-f]{3,8}", q) else None
        rows = []
        for name in sorted(self.defs):
            row = self.token_row(name)
            if q and q not in name.lower() and q not in (self.value(name) or "").lower():
                c = row["resolved"]
                if not (hexq and c and hexq in colour.hex8(colour.from_obj(c)).lower()):
                    continue
            if colours_only and not row["resolved"]:
                continue
            rows.append(row)
        return {"total": len(rows), "rows": rows[:limit]}

    def token(self, name):
        if name not in self.defs:
            raise KeyError("no such token: " + name)
        row = self.token_row(name)
        row["defs"] = self.defs[name]
        row["uses"] = [dict(zip(("sheet", "selector", "property"), u)) for u in sorted(self.reach(name))[:300]]
        return row

    def literal_list(self):
        rows = []
        for hits in self.literals.values():
            h = hits[0]
            rows.append({"rgb": h["rgb"], "a": h["a"], "hits": len(hits), "rgb_hits": len(self.by_rgb[h["rgb"]])})
        return sorted(rows, key=lambda r: (-r["hits"], r["rgb"], r["a"]))

    def literal(self, rgb, a):
        """Hits for one exact RGBA, and for every alpha of the same RGB (the two swap modes)."""
        c = colour.from_obj({"rgb": rgb, "a": float(a)})
        exact = [h for h in self.by_rgb.get(colour.hex6(c), []) if colour.same(colour.from_obj({"rgb": h["rgb"], "a": h["a"]}), c)]
        return {"exact": exact, "rgb_all": self.by_rgb.get(colour.hex6(c), [])}


def cache_path(ws, manifest):
    key = "".join(manifest["files"][n]["sha256"][:8] for n in sorted(manifest["files"]))
    return ws.cache / ("styles%d-%s.json" % (CACHE_SCHEMA, key))


def build(ws, progress=None):
    man = ws.vanilla_manifest()
    if not man:
        raise RuntimeError("no vanilla snapshot; take one first")
    sheets = []
    names = sorted(man["files"])
    for k, name in enumerate(names):
        if progress:
            progress("indexing " + name, k / len(names))
        for tree in bundles.read_sheets(ws.vanilla / name):
            sheets.append(sheet_entry(name, tree))
    cache_path(ws, man).write_text(json.dumps({"schema": CACHE_SCHEMA, "game_build": man.get("game_build"), "sheets": sheets}),
                                   encoding="utf-8")
    return StyleIndex(sheets, {"game_build": man.get("game_build")})


def load(ws):
    man = ws.vanilla_manifest()
    if not man or not cache_path(ws, man).is_file():
        return None
    d = json.loads(cache_path(ws, man).read_text(encoding="utf-8"))
    if d.get("schema") != CACHE_SCHEMA:
        return None
    return StyleIndex(d["sheets"], {"game_build": d.get("game_build")})
