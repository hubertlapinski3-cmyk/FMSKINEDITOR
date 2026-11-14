"""Resolving `asset(F:P)` references of stylesheet values to the game's assets (M4; docs/evidence/phase9-m4-start-20261114.md).

A stylesheet's asset value is a Unity PPtr. `F` indexes the externals of the bundle the SHEET was read from (1-based; 0 would be the sheet's own file), each external is an
`archive:/CAB-<hash>/CAB-<hash>` name, and a CAB name belongs to exactly one bundle, where the object is found by its path id `P`. So the resolver needs the bundle of the sheet,
never a global table of file ids: the same F means different files in different bundles (a layout's inline sheet is not the shared sheets' bundle).

Everything is read from the bundles; nothing is guessed. A reference that cannot be resolved comes back as `{"error": ...}` with the step that failed, so the render can label it.
Caches: the CAB -> bundle map and each bundle's externals live in `<cache>/asset-index.json`; loaded bundles are kept in a small LRU."""
import json
import re
from collections import OrderedDict
from pathlib import Path

REF = re.compile(r"asset\((-?\d+):(-?\d+)\)")


def parse_ref(value):
    """(file id, path id) of an `asset(F:P)` value text, or None."""
    m = REF.search(value or "")
    return (int(m.group(1)), int(m.group(2))) if m else None


class AssetResolver:
    def __init__(self, aa_dir, cache_dir, keep=4):
        self.aa, self.cache = Path(aa_dir), Path(cache_dir)
        self._index = None
        self._env = OrderedDict()
        self._memo = {}                     # resolve() results by (source bundle, F, P): the same reference is asked for many times per render
        self._keep = keep

    # ---- index
    def _index_file(self):
        return self.cache / "asset-index.json"

    def index(self):
        if self._index is None:
            f = self._index_file()
            if f.is_file():
                self._index = json.loads(f.read_text(encoding="utf-8"))
            else:
                self._index = self.build_index()
        return self._index

    def build_index(self):
        import UnityPy
        cab, ext = {}, {}
        for b in sorted(self.aa.glob("*.bundle")):
            try:
                env = UnityPy.load(str(b))
            except Exception:
                continue
            for f in env.files.values():
                for n, sub in (getattr(f, "files", None) or {}).items():
                    if n.startswith("CAB-") and not n.endswith(".resS"):
                        cab[n] = b.name
                        ext[b.name] = [e.path.split("/")[-1] for e in (getattr(sub, "externals", None) or [])]
        idx = {"schema": "fm-asset-index/1", "cab_to_bundle": cab, "externals": ext}
        self.cache.mkdir(parents=True, exist_ok=True)
        self._index_file().write_text(json.dumps(idx), encoding="utf-8")
        return idx

    def _load(self, bundle):
        """One UnityPy environment holding the bundle AND the bundles its externals point to, so a Sprite can reach its atlas texture (UnityPy dereferences across files
        only inside one environment)."""
        import UnityPy
        if bundle in self._env:
            self._env.move_to_end(bundle)
            return self._env[bundle]
        idx = self.index()
        deps = []
        for cab in idx["externals"].get(bundle, []):
            b = idx["cab_to_bundle"].get(cab)
            if b and b != bundle and b not in deps:
                deps.append(b)
        env = UnityPy.load(*[str(self.aa / b) for b in [bundle] + deps])
        self._env[bundle] = env
        while len(self._env) > self._keep:
            self._env.popitem(last=False)
        return env

    def _cabs(self, bundle):
        return {c for c, b in self.index()["cab_to_bundle"].items() if b == bundle}

    # ---- resolution
    def locate(self, source_bundle, file_id, path_id):
        """{bundle, path_id} the reference points at, or {"error": step}."""
        idx = self.index()
        ext = idx["externals"].get(source_bundle)
        if ext is None:
            return {"error": "source bundle %r is not in the asset index" % source_bundle}
        if file_id == 0:
            return {"bundle": source_bundle, "path_id": path_id}
        if not 1 <= file_id <= len(ext):
            return {"error": "file id %d is outside the %d externals of %s" % (file_id, len(ext), source_bundle)}
        cab = ext[file_id - 1]
        if cab.startswith("Library/"):
            return {"error": "built-in Unity resource (%s)" % cab}
        b = idx["cab_to_bundle"].get(cab)
        return {"bundle": b, "path_id": path_id} if b else {"error": "no bundle holds %s" % cab}

    def resolve(self, source_bundle, file_id, path_id):
        """{bundle, path_id, type, name} of the target object, or {"error": step}."""
        key = (source_bundle, file_id, path_id)
        if key in self._memo:
            return dict(self._memo[key])
        res = self._resolve(source_bundle, file_id, path_id)
        self._memo[key] = res
        return dict(res)

    def _resolve(self, source_bundle, file_id, path_id):
        loc = self.locate(source_bundle, file_id, path_id)
        if "error" in loc:
            return loc
        o = self.object(loc["bundle"], path_id)
        if o is not None:
            try:
                name = o.read().m_Name
            except Exception:
                name = ""
            return {"bundle": loc["bundle"], "path_id": path_id, "type": o.type.name, "name": name}
        return {"error": "object %d not found in %s" % (path_id, loc["bundle"])}

    def object(self, bundle, path_id):
        cabs = {c.lower() for c in self._cabs(bundle)}
        for o in self._load(bundle).objects:
            if o.path_id == path_id and o.assets_file.name.lower() in cabs:
                return o
        return None


# ---- drawing: sprites to PNG data URLs, font names, and the render-tree pass
FONT_SUFFIX = re.compile(r"\s*SDF\s*$")


def font_family(asset_name):
    """('ABCSocial', 'Regular') from a TextMeshPro asset name such as 'ABCSocial-Regular SDF'; the family is named per text node, the stand-in font draws it."""
    base = FONT_SUFFIX.sub("", asset_name or "")
    fam, _, weight = base.partition("-")
    return fam or base, weight or "Regular"


def _hex_to_rgba(h):
    h = (h or "").lstrip("#")
    if len(h) == 6:
        h += "ff"
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4, 6)) if len(h) == 8 else None


class Drawn:
    """Per-render cache of sprite data URLs (key: bundle, path id, tint)."""

    def __init__(self, resolver):
        self.r, self._png = resolver, {}

    def sprite_data_url(self, bundle, path_id, tint=None):
        import base64
        import io
        key = (bundle, path_id, tint)
        if key in self._png:
            return self._png[key]
        o = self.r.object(bundle, path_id)
        out = None
        if o is not None and o.type.name in ("Sprite", "Texture2D"):
            im = o.read().image.convert("RGBA")
            rgba = _hex_to_rgba(tint) if tint else None
            if rgba:                                           # Unity multiplies the image by the tint colour
                from PIL import ImageChops, Image
                im = ImageChops.multiply(im, Image.new("RGBA", im.size, rgba))
            buf = io.BytesIO()
            im.save(buf, "PNG")
            out = "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode("ascii")
        self._png[key] = out
        return out


def apply_assets(top_nodes, resolver, layout_bundle, sheet_bundles, drawn=None):
    """Resolve the asset values of every node: `background-image` (a sprite or texture, drawn) and `-unity-font-definition` (a font: named, not rendered).
    The bundle an `asset(F:P)` indexes is the one its sheet was read from: the shared sheet's bundle (`sheet_bundles[name]`), or the layout's own bundle for an inline value.
    Each node gets `assets: {property: {...}}`; the computed entry's status and note say what was done (a resolved image is `mapped`, an unresolved one stays `partial` with the
    reason, a font stays `partial` and names the family). Returns the counts."""
    drawn = drawn or Drawn(resolver)
    counts = {"images": 0, "fonts": 0, "unresolved": 0}

    def one(n, prop, d, ref, bundle):
        comp = n["computed"]
        res = resolver.resolve(bundle, ref[0], ref[1])
        res["from_bundle"] = bundle
        if "error" in res:
            counts["unresolved"] += 1
            d["note"] = "asset(%d:%d) not resolved: %s; shown as a labelled placeholder" % (ref[0], ref[1], res["error"])
        elif prop == "background-image":
            tint = (comp.get("-unity-background-image-tint-color") or {}).get("value")
            tint = tint if tint and tint.startswith("#") else None
            url = drawn.sprite_data_url(res["bundle"], res["path_id"], tint) if res["type"] in ("Sprite", "Texture2D") else None
            if url:
                res["data_url"], res["tinted"] = url, bool(tint)
                d["status"], d["note"] = "mapped", "drawn from %s (%s %r)%s" % (res["bundle"], res["type"], res["name"], ", tinted by multiplication" if tint else "")
                tc = comp.get("-unity-background-image-tint-color")
                if tc and tint:
                    tc["status"], tc["note"] = "mapped", "applied by multiplying the image (Unity's rule)"
                counts["images"] += 1
            else:
                counts["unresolved"] += 1
                d["note"] = "%s %r is not a drawable image; shown as a labelled placeholder" % (res["type"], res["name"])
        else:
            res["family"], res["weight"] = font_family(res.get("name"))
            d["note"] = "font %s %s (a TextMeshPro SDF asset in %s): named here, drawn with the stand-in font" % (res["family"], res["weight"], res["bundle"])
            counts["fonts"] += 1
        return res

    def walk(n, inherited):
        inh = dict(inherited)
        for prop in ("background-image", "-unity-font-definition"):
            d = n["computed"].get(prop)
            ref = parse_ref(d["value"]) if d else None
            if not ref:
                continue
            sheet = (d.get("source") or {}).get("sheet")
            if sheet and sheet in sheet_bundles:
                res = one(n, prop, d, ref, sheet_bundles[sheet])
            elif not sheet and prop in inh and inh[prop][0] == ref:       # inherited: the declaring ancestor's resolution (its sheet is the one that counts)
                res = dict(inh[prop][1], inherited=True)
                d["note"] = (d.get("note") or "") + " (inherited)"
            elif not sheet and (d.get("source") or {}).get("inline") is None and prop == "background-image":
                res = one(n, prop, d, ref, layout_bundle)                 # an inline value of this layout
            else:
                res = {"error": "declared by an ancestor or an inline style whose sheet is not recorded", "from_bundle": None}
                counts["unresolved"] += 1
                d["note"] = "asset(%d:%d) not resolved: %s" % (ref[0], ref[1], res["error"])
            n.setdefault("assets", {})[prop] = res
            if "error" not in res:
                inh[prop] = (ref, res)
        for c in n.get("children", []):
            walk(c, inh)
    for t in top_nodes:
        walk(t, {})
    return counts
