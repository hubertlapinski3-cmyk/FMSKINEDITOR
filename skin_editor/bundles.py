"""UnityPy access. The only module that imports UnityPy (lazily). LEARNINGS section 6.2."""
import hashlib
import json
from pathlib import Path

STYLE_BUNDLES = ["ui-styles_assets_common.bundle", "ui-styles_assets_default.bundle"]


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def unitypy_version():
    try:
        import UnityPy
        return UnityPy.__version__
    except Exception:
        return None


def _sheets(env):
    for obj in env.objects:
        if obj.type.name != "MonoBehaviour":
            continue
        try:
            tree = obj.read_typetree()
        except Exception:
            continue
        if isinstance(tree, dict) and "m_Rules" in tree:
            yield obj, tree


def read_sheets(path):
    """Yield StyleSheet typetrees (dicts with m_Rules) from a bundle."""
    import UnityPy
    for _, tree in _sheets(UnityPy.load(str(path))):
        yield tree


def patch_bundle(src, out_dir, fn, touched=None):
    """Call fn(tree) for every StyleSheet; save the ones it changed. Writes out_dir/<same name> only
    when something changed. Returns True when a file was written. `touched` (a set), when given, receives the
    path id of every sheet that was saved (the gate checks everything else against vanilla)."""
    import UnityPy
    env = UnityPy.load(str(src))
    changed = False
    for obj, tree in _sheets(env):
        if fn(tree):
            obj.save_typetree(tree)
            changed = True
            if touched is not None:
                touched.add(obj.path_id)
    if changed:
        env.save(pack="original", out_path=str(out_dir))
        if not (Path(out_dir) / Path(src).name).is_file():
            raise RuntimeError("UnityPy did not write " + Path(src).name)
    return changed


def _digest(tree):
    """Typetree digest via json.dumps(sort_keys=True): plain dict equality fails on NaN, the text form does not."""
    return hashlib.sha256(json.dumps(tree, sort_keys=True, default=str).encode("utf-8")).hexdigest()


def object_digests(path, want_trees=()):
    """({path id: (kind, digest, label)}, {path id: typetree for want_trees}). MonoBehaviours are compared as typetrees
    (kind "tt"); every other object type by get_raw_data() (kind "raw"). An object whose typetree cannot be read falls back
    to raw bytes. Digests only: the trees stay out of memory."""
    import UnityPy
    out, trees = {}, {}
    for obj in UnityPy.load(str(path)).objects:
        pid, kind, tree = obj.path_id, "raw", None
        label = "%s %s" % (obj.type.name, pid)
        if obj.type.name == "MonoBehaviour":
            try:
                tree = obj.read_typetree()
                kind = "tt"
                label = "%s (path id %s)" % (tree.get("m_Name") or "MonoBehaviour", pid) if isinstance(tree, dict) else label
            except Exception:
                tree = None
        if kind == "tt":
            out[pid] = ("tt", _digest(tree), label)
            if pid in want_trees:
                trees[pid] = tree
        else:
            raw = bytes(obj.get_raw_data())
            out[pid] = ("raw", hashlib.sha256(raw).hexdigest(), label)
            if pid in want_trees:
                trees[pid] = raw
    return out, trees


def first_difference(a, b, path=""):
    """Path of the first field where two typetrees (or two byte strings) differ, or None. Iterative."""
    if isinstance(a, (bytes, bytearray)) or isinstance(b, (bytes, bytearray)):
        if a == b:
            return None
        n = next((i for i, (x, y) in enumerate(zip(a, b)) if x != y), min(len(a), len(b)))
        return "raw data, first differing byte at offset %d (lengths %d and %d)" % (n, len(a), len(b))
    stack = [(a, b, path)]
    while stack:
        x, y, pth = stack.pop()
        if type(x) != type(y):
            return pth or "/"
        if isinstance(x, dict):
            if list(x) != list(y):
                return (pth + "/" + str(next((k for k in list(x) + list(y) if k not in x or k not in y), "?"))) or "/"
            stack.extend((x[k], y[k], pth + "/" + str(k)) for k in reversed(list(x)))
        elif isinstance(x, list):
            if len(x) != len(y):
                return pth + "[len %d vs %d]" % (len(x), len(y))
            stack.extend((u, v, "%s[%d]" % (pth, i)) for i, (u, v) in reversed(list(enumerate(zip(x, y)))))
        elif x != y and not (x != x and y != y):
            return pth or "/"
    return None


def inspect(path):
    """verify_build.sheets(): (object counts by type, {sheet name: tree}, deserialisation errors)."""
    import UnityPy
    counts, out, errors = {}, {}, []
    for obj in UnityPy.load(str(path)).objects:
        counts[obj.type.name] = counts.get(obj.type.name, 0) + 1
        try:
            if obj.type.name == "MonoBehaviour":
                t = obj.read_typetree()
                if "m_Rules" in t:
                    out[t["m_Name"]] = t
            else:
                obj.read()
        except Exception as e:
            errors.append("%s %s: %s" % (obj.type.name, obj.path_id, e))
    return counts, out, errors


def read_visual_trees(path):
    """Yield (asset name, nodes) for every VisualTreeAsset; nodes = [[type, name, [classes], parent index or -1]].
    Walk as in verify_build.load_trees, iterative."""
    import UnityPy
    for obj in UnityPy.load(str(path)).objects:
        if obj.type.name != "MonoBehaviour":
            continue
        try:
            t = obj.read_typetree()
        except Exception:
            continue
        if "m_VisualTree" not in t:
            continue
        refs = {r["rid"]: r.get("data") or {} for r in t.get("references", {}).get("RefIds", [])}
        nodes, stack = [], [(t["m_VisualTree"].get("rid"), -1)]
        while stack:
            rid, parent = stack.pop()
            d = refs.get(rid)
            if d is None or "m_FullTypeName" not in d:
                continue
            sd = d.get("m_SerializedData")
            name = ""
            if isinstance(sd, dict) and sd.get("rid") in refs:
                name = refs[sd["rid"]].get("name", "") or ""
            nodes.append([d["m_FullTypeName"].rsplit(".", 1)[-1].rsplit("/", 1)[0], name,
                          list(d.get("m_Classes", [])), parent])
            me = len(nodes) - 1
            for ch in reversed(d.get("m_Children") or []):
                stack.append((ch["rid"], me))
        yield t.get("m_Name", ""), nodes
