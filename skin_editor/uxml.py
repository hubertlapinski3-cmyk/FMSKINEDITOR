"""UXML (VisualTreeAsset) access: read the element trees of the game's layouts, find where a class is used, and apply per-layout patches
(set-classes, set-inline, set-attr) to a copy of a bundle. Reading never writes; patching writes only into a build folder.

A VisualTreeAsset is a MonoBehaviour whose typetree has m_VisualTree (a managed reference), the registry `references.RefIds` and
`inlineSheet` (a pointer to the layout's own StyleSheet object in the same bundle). Elements are VisualElementAsset / TemplateAsset
entries of the registry (m_Id, m_Classes, m_Children, m_RuleIndex into the inline sheet, m_SerializedData -> <Type>/UxmlSerializedData
with name and the element's attributes). Element ids (m_Id) are unique inside a layout and are what bindings and template overrides
refer to, so a patch addresses elements by id (plus a type/name guard) and never adds, removes or moves an element."""
import json
import re
from pathlib import Path
from .asset_hash import sha256_file

from . import bundles, uss
from . import token_patch as tp

VTA_GLOB = "ui-visualtreeassets*.bundle"
NOISE = ("uxmlAssetId", "bindings")
PATCH_OPS = ("set-classes", "set-inline", "set-attr")
_FIXED = []


def fix_unitypy_writer():
    """UnityPy's typetree writer fails on the null managed reference every VisualTreeAsset starts with (rid -2, no data: the reader skips
    it, the writer does not). This makes the writer skip it the same way. Idempotent; the build gate re-reads what was written."""
    if _FIXED:
        return
    from UnityPy.helpers import TypeTreeHelper as T
    orig = T.write_value

    def write_value(value, node, writer, config):
        if node.m_Type == "ReferencedObject":
            for child in node.m_Children:
                if child.m_Type == "ReferencedObjectData":
                    nodes = T.get_ref_type_node(value, config.assetsfile)
                    if nodes is None:
                        continue
                    orig(value[child.m_Name], nodes, writer, config)
                else:
                    orig(value[child.m_Name], child, writer, config)
            if T.metaflag_is_aligned(node.m_MetaFlag):
                writer.align_stream()
            return None
        return orig(value, node, writer, config)

    T.write_value = write_value
    _FIXED.append(True)


# ---------------------------------------------------------------- read
def _short(full):
    return (full or "").rsplit(".", 1)[-1].rsplit("/", 1)[0]


def registry(tree):
    return {r["rid"]: r for r in tree.get("references", {}).get("RefIds", [])}


def attrs_of(sd):
    """The element's attributes from its serialized data, flags and noise left out: {name: value}. Only attributes whose
    '<name>_UxmlAttributeFlags' is set (the layout overrides the default) are marked in `set`."""
    if not isinstance(sd, dict):
        return {}, []
    vals = {k: v for k, v in sd.items() if not k.endswith("_UxmlAttributeFlags") and k not in NOISE}
    flagged = sorted(k[: -len("_UxmlAttributeFlags")] for k, v in sd.items() if k.endswith("_UxmlAttributeFlags") and v)
    return vals, flagged


def element(tree, refs, rid):
    """One element as a plain dict (no children resolved)."""
    r = refs.get(rid)
    d = (r or {}).get("data") or {}
    if "m_Id" not in d:
        return None
    sd = (refs.get((d.get("m_SerializedData") or {}).get("rid")) or {}).get("data") or {}
    vals, flagged = attrs_of(sd)
    out = {"rid": rid, "id": d["m_Id"], "kind": "template" if (r.get("type") or {}).get("class") == "TemplateAsset" else "element",
           "type": _short(d.get("m_FullTypeName")) or ("Template:" + str(d.get("m_TemplateAlias", ""))), "full_type": d.get("m_FullTypeName", ""),
           "name": sd.get("name", "") or "", "classes": list(d.get("m_Classes") or []), "rule_index": d.get("m_RuleIndex", -1),
           "children": [c["rid"] for c in d.get("m_Children") or []], "attrs": vals, "attrs_set": flagged,
           "bindings": sd.get("bindings") or [], "properties": [{"name": p.get("name"), "value": p.get("value")} for p in d.get("m_Properties") or []]}
    if out["kind"] == "template":
        out["template"] = d.get("m_TemplateAlias", "")
    return out


def inline_rule(sheet_tree, index):
    """The layout's inline style for rule `index` as [(property, value text)], or None."""
    rules = (sheet_tree or {}).get("m_Rules") or []
    if not 0 <= index < len(rules):
        return None
    return [(uss.prop_name(p), uss.value_text(sheet_tree, p.get("m_Values", []))[0]) for p in rules[index].get("m_Properties", [])]


def usings(tree):
    """alias -> {name?, path_id, file_id} from m_Usings."""
    out = {}
    for u in tree.get("m_Usings") or []:
        a = u.get("m_Alias") or u.get("alias") or ""
        p = u.get("m_Asset") or u.get("asset") or {}
        out[a] = {"path_id": str(p.get("m_PathID", 0)), "file_id": p.get("m_FileID", 0), "path": u.get("m_Path") or u.get("path") or ""}
    return out


class Layouts:
    """Read-only access to the VisualTreeAssets of a folder (the game's aa folder or the vanilla snapshot)."""

    def __init__(self, folder, cache_dir=None):
        self.folder = Path(folder)
        self.cache_dir = Path(cache_dir) if cache_dir else None
        self._cache = {}

    def bundles(self):
        return sorted(p.name for p in self.folder.glob(VTA_GLOB))

    def _env(self, bundle):
        import UnityPy
        if bundle not in self.bundles():
            raise KeyError("no layout bundle " + bundle)
        return UnityPy.load(str(self.folder / bundle))

    def list(self):
        """[{bundle, name, path_id, elements, classes: {class: elements carrying it}}] for every VisualTreeAsset. One pass per bundle,
        cached in memory and (with cache_dir) on disk keyed by the bundle's size and mtime."""
        out = []
        for b in self.bundles():
            f = self.folder / b
            digest = sha256_file(f)
            key = (b, digest)
            if key not in self._cache:
                disk = self.cache_dir / ("layouts-%s-%s.json" % (b[:-len(".bundle")], digest)) if self.cache_dir else None
                if disk is not None and disk.is_file():
                    self._cache[key] = json.loads(disk.read_text(encoding="utf-8"))
                else:
                    rows = []
                    for o in self._env(b).objects:
                        if o.type.name != "MonoBehaviour":
                            continue
                        try:
                            t = o.read_typetree()
                        except Exception:
                            continue
                        if isinstance(t, dict) and "m_VisualTree" in t:
                            cls, n = {}, 0
                            for r in t["references"]["RefIds"]:
                                d = r.get("data") or {}
                                if d.get("m_Id") is not None:
                                    n += 1
                                    for c in d.get("m_Classes") or []:
                                        cls[c] = cls.get(c, 0) + 1
                            rows.append({"bundle": b, "name": t.get("m_Name", ""), "path_id": str(o.path_id), "elements": n, "classes": cls})
                    self._cache[key] = rows
                    if disk is not None:
                        self.cache_dir.mkdir(parents=True, exist_ok=True)
                        disk.write_text(json.dumps(rows), encoding="utf-8")
            out += self._cache[key]
        return out
    def load(self, bundle, path_id):
        """(object, typetree, inline sheet typetree or None) of one layout."""
        env = self._env(bundle)
        objs = {o.path_id: o for o in env.objects}
        o = objs.get(int(path_id))
        if o is None:
            raise KeyError("no object %s in %s" % (path_id, bundle))
        t = o.read_typetree()
        if "m_VisualTree" not in t:
            raise ValueError("path id %s is not a VisualTreeAsset" % path_id)
        pid = (t.get("inlineSheet") or {}).get("m_PathID", 0)
        sheet = objs[pid].read_typetree() if pid in objs else None
        return o, t, sheet

    def tree(self, bundle, path_id, resolve=True):
        """The layout as a nested element tree. Templates are resolved one level when the alias points at a layout in the same folder."""
        _, t, sheet = self.load(bundle, path_id)
        refs = registry(t)
        us = usings(t)
        by_name = None

        def build(rid, depth):
            e = element(t, refs, rid)
            if e is None:
                return None
            e["inline"] = inline_rule(sheet, e["rule_index"]) if e["rule_index"] >= 0 else None
            kids = [build(c, depth) for c in e.pop("children")]
            e["children"] = [k for k in kids if k]
            if e["kind"] == "template" and resolve and depth == 0:
                nonlocal by_name
                if by_name is None:
                    by_name = {}
                    for row in self.list():
                        by_name.setdefault(row["name"], row)
                alias = e.get("template", "")
                row = by_name.get(alias) or by_name.get(Path(us.get(alias, {}).get("path", "")).stem)
                if row:
                    sub = self.tree(row["bundle"], row["path_id"], resolve=False)
                    e["included"] = {"bundle": row["bundle"], "name": row["name"], "path_id": row["path_id"], "root": sub["root"]}
            return e

        root = build(t["m_VisualTree"]["rid"], 0)
        return {"bundle": bundle, "path_id": str(path_id), "name": t.get("m_Name", ""), "usings": us, "has_inline_sheet": sheet is not None, "root": root}

    def class_usage(self, cls, index=None, limit=200):
        """Where a class is used: layouts (elements carrying it) and, with the style index, the rules that mention it."""
        layouts = []
        for row in self.list():
            n = row["classes"].get(cls, 0)
            if n:
                layouts.append({k: row[k] for k in ("bundle", "name", "path_id", "elements")} | {"uses": n})
                if len(layouts) >= limit:
                    break
        rules = []
        if index is not None:
            pat = re.compile(r"\.%s(?![\w-])" % re.escape(cls))
            for sh in index.sheets:
                for r in sh["rules"]:
                    if any(pat.search(s) for s in r["s"]):
                        rules.append({"sheet": sh["name"], "selector": ", ".join(r["s"]), "props": {n: v for n, v, _c in r["p"]}})
                        if len(rules) >= limit:
                            break
        return {"class": cls, "layouts": layouts, "rules": rules}


# ---------------------------------------------------------------- patches
CLASS_RE = re.compile(r"[A-Za-z_][\w-]*")
FORBIDDEN_ATTR = re.compile(r"binding|datasource|template|valuevars|funcs|viewdatakey|uxmlassetid|^name$", re.I)   # bindings and structure stay as they are
EMPTY_SPEC = {"tokens": {}, "literal_map": {}, "skip_sheets": []}


def validate_doc(doc):
    """Shape of one per-layout patch file: {schema, layout: {bundle, name, path_id?}, ops: [...]}. Raises ValueError."""
    from .images import BUNDLE_RE
    from . import project as project_mod
    if not isinstance(doc, dict) or set(doc) - {"schema", "layout", "ops"}:
        raise ValueError("a layout patch has schema, layout and ops")
    lay = doc.get("layout")
    if not isinstance(lay, dict) or set(lay) - {"bundle", "name", "path_id"} or not BUNDLE_RE.fullmatch(str(lay.get("bundle", ""))) or not lay.get("name"):
        raise ValueError("layout needs bundle (ui-*.bundle) and name (and the path_id the patch was made on)")
    if "path_id" in lay and not re.fullmatch(r"-?\d{1,20}", str(lay["path_id"])):
        raise ValueError("layout path_id must be a decimal string")
    if not isinstance(doc.get("ops"), list) or not doc["ops"]:
        raise ValueError("ops must be a non-empty list")
    for op in doc["ops"]:
        if not isinstance(op, dict) or op.get("op") not in PATCH_OPS:
            raise ValueError("op must be one of: " + ", ".join(PATCH_OPS))
        if not isinstance(op.get("id"), int) or isinstance(op.get("id"), bool):
            raise ValueError("an op addresses an element by its integer id (m_Id)")
        g = op.get("guard")
        if not isinstance(g, dict) or not isinstance(g.get("type"), str) or not g["type"] or set(g) - {"type", "name"}:
            raise ValueError("an op needs guard {type, name?}: the element's type (and name) it was made for")
        extra = set(op) - {"op", "id", "guard"}
        if op["op"] == "set-classes":
            if extra - {"add", "remove"} or not (op.get("add") or op.get("remove")):
                raise ValueError("set-classes has add and/or remove (lists of class names)")
            for k in ("add", "remove"):
                if not isinstance(op.get(k, []), list) or not all(isinstance(c, str) and CLASS_RE.fullmatch(c) for c in op.get(k, [])):
                    raise ValueError("%s must be a list of class names" % k)
            if set(op.get("add", [])) & set(op.get("remove", [])):
                raise ValueError("a class cannot be both added and removed")
        elif op["op"] == "set-inline":
            if extra - {"props"} or not isinstance(op.get("props"), dict) or not op["props"]:
                raise ValueError("set-inline has props {property: value}")
            for k, v in op["props"].items():
                if not k.startswith("--") and k not in tp.PROP_TABLE:
                    raise ValueError("unknown property: " + k)
                project_mod.check_value(v)
        else:
            if extra - {"name", "value"} or not isinstance(op.get("name"), str) or "value" not in op:
                raise ValueError("set-attr has name and value")
            if FORBIDDEN_ATTR.search(op["name"]) or op["name"].endswith("_UxmlAttributeFlags"):
                raise ValueError("attribute %s cannot be edited (names, bindings, templates and ids are structure)" % op["name"])
            if not isinstance(op["value"], (str, int, float, bool)):
                raise ValueError("an attribute value is text, a number or true/false")
    return doc


def merge_op(doc, op):
    """Fold one op into the patch file of its layout (same element and op kind merge: classes add/remove cancel each other, inline props
    and attribute values are replaced; an inline prop set to None is dropped). Returns the doc; ops that end up empty are removed."""
    ops = doc["ops"]
    same = next((o for o in ops if o["op"] == op["op"] and o["id"] == op["id"] and (op["op"] != "set-attr" or o["name"] == op["name"])), None)
    if same is None:
        ops.append(json.loads(json.dumps(op)))
        same = ops[-1]
        if op["op"] == "set-classes":
            same["add"], same["remove"] = list(op.get("add", [])), list(op.get("remove", []))
    elif op["op"] == "set-classes":
        add, rem = list(same.get("add", [])), list(same.get("remove", []))
        for c in op.get("remove", []):                          # removing a class this patch added undoes the add
            if c in add:
                add.remove(c)
            elif c not in rem:
                rem.append(c)
        for c in op.get("add", []):                             # adding a class this patch removed undoes the removal
            if c in rem:
                rem.remove(c)
            elif c not in add:
                add.append(c)
        same["add"], same["remove"] = add, rem
        same["guard"] = op["guard"]
    elif op["op"] == "set-inline":
        merged = dict(same["props"])
        merged.update(op["props"])
        same["props"] = {k: v for k, v in merged.items() if v is not None}
        same["guard"] = op["guard"]
    else:
        same["value"], same["guard"] = op["value"], op["guard"]
    if same["op"] == "set-classes":
        for k in ("add", "remove"):
            if not same.get(k):
                same.pop(k, None)
        if not same.get("add") and not same.get("remove"):
            ops.remove(same)
    elif same["op"] == "set-inline":
        same["props"] = {k: v for k, v in same["props"].items() if v is not None}
        if not same["props"]:
            ops.remove(same)
    return doc


def patch_label(doc):
    return "%s (%s)" % (doc["layout"]["name"], doc["layout"]["bundle"][len("ui-visualtreeassets_assets_"):-len("visualtreeassetpreload.bundle")] if doc["layout"]["bundle"].startswith("ui-visualtreeassets_assets_") else doc["layout"]["bundle"])


def locate(t, op, where=""):
    """(registry, rid, VisualElementAsset data, serialized data) of the element an op addresses; the guard must match."""
    refs = registry(t)
    for rid, r in refs.items():
        d = r.get("data") or {}
        if d.get("m_Id") == op["id"]:
            e = element(t, refs, rid)
            g = op["guard"]
            if e["type"] != g["type"] or ("name" in g and e["name"] != g["name"]):
                raise ValueError("%s element %d is now %s#%s, the patch was made for %s#%s (game updated? re-do this edit)" % (
                    where, op["id"], e["type"], e["name"], g["type"], g.get("name", "")))
            return refs, rid, d, (refs.get((d.get("m_SerializedData") or {}).get("rid")) or {}).get("data")
    raise ValueError("%s has no element with id %d (game updated? re-do this edit)" % (where, op["id"]))


def _text(v):
    from . import project as project_mod
    return project_mod.patch_text(v)


def apply_to_layout(t, sheet, ops, where=""):
    """Apply ops to one decoded layout (and its inline sheet) in place. Returns (notes, sheet_changed)."""
    notes, sheet_changed, sp = [], False, None
    for op in ops:
        refs, rid, d, sd = locate(t, op, where)
        if op["op"] == "set-classes":
            cur = list(d.get("m_Classes") or [])
            new = [c for c in cur if c not in op.get("remove", [])] + [c for c in op.get("add", []) if c not in cur]
            d["m_Classes"] = new
        elif op["op"] == "set-inline":
            if sheet is None:
                raise ValueError("%s has no inline style sheet" % where)
            sp = sp or tp.SheetPatcher(sheet, EMPTY_SPEC)
            props = {k: _text(v) for k, v in op["props"].items()}
            if d.get("m_RuleIndex", -1) >= 0:
                sp.set_props(sheet["m_Rules"][d["m_RuleIndex"]], props)
            else:
                d["m_RuleIndex"] = sp.append_props_rule(props)
            sheet_changed = True
        else:
            if not isinstance(sd, dict) or op["name"] not in sd or op["name"].endswith("_UxmlAttributeFlags"):
                raise ValueError("%s element %d has no attribute %s in the game's layout (only attributes the game already uses can be set)" % (where, op["id"], op["name"]))
            old = sd[op["name"]]
            v = op["value"]
            if isinstance(old, bool) or (isinstance(old, int) and isinstance(v, bool)):
                v = int(v)
            if type(v) is not type(old) and not (isinstance(old, float) and isinstance(v, int)):
                raise ValueError("%s element %d attribute %s is %s, not %s" % (where, op["id"], op["name"], type(old).__name__, type(v).__name__))
            sd[op["name"]] = float(v) if isinstance(old, float) else v
            flag = op["name"] + "_UxmlAttributeFlags"
            if flag in sd:
                sd[flag] = 1                                  # the layout now sets this attribute explicitly
    return notes, sheet_changed


def apply_patches(src, out_dir, docs, touched=None):
    """Patch the layouts of one bundle (docs: the patch files for it); writes out_dir/<name> when anything changed.
    Returns (changed, notes, path ids saved)."""
    import UnityPy
    fix_unitypy_writer()
    env = UnityPy.load(str(src))
    objs = {o.path_id: o for o in env.objects}
    by_name = {}
    for o in env.objects:
        if o.type.name == "MonoBehaviour":
            try:
                nm = o.peek_name()
            except Exception:
                nm = None
            if nm:
                by_name.setdefault(nm, []).append(o)
    notes, done = [], []
    for doc in docs:
        lay = doc["layout"]
        where = "%s in %s:" % (lay["name"], Path(src).name)
        o = objs.get(int(lay["path_id"])) if lay.get("path_id") else None
        if o is None or (o.peek_name() if o.type.name == "MonoBehaviour" else None) != lay["name"]:
            cands = [x for x in by_name.get(lay["name"], []) if "m_VisualTree" in (x.read_typetree() if x.type.name == "MonoBehaviour" else {})]
            if len(cands) != 1:
                raise ValueError("%s layout not found (game updated? pick it again in the Layouts view)" % where)
            o = cands[0]
        t = o.read_typetree()
        sheet_o = objs.get((t.get("inlineSheet") or {}).get("m_PathID", 0))
        sheet = sheet_o.read_typetree() if sheet_o is not None else None
        n, sheet_changed = apply_to_layout(t, sheet, doc["ops"], where)
        notes += n
        o.save_typetree(t)
        done.append(o.path_id)
        if sheet_changed:
            sheet_o.save_typetree(sheet)
            done.append(sheet_o.path_id)
    if touched is not None:
        touched.update(done)
    if done:
        (Path(out_dir) / Path(src).name).write_bytes(env.file.save(packer="original"))
    return bool(done), notes, done


# ---- the gate's independent check
def _expected(t, ops, where):
    """What the vanilla layout plus the ops must give: {id: classes}, {id: {attr: value}}, {id: props}. No encoding involved."""
    cls, attrs, inline = {}, {}, {}
    for op in ops:
        refs, rid, d, sd = locate(t, op, where)
        i = op["id"]
        if op["op"] == "set-classes":
            cur = cls.get(i, list(d.get("m_Classes") or []))
            cls[i] = [c for c in cur if c not in op.get("remove", [])] + [c for c in op.get("add", []) if c not in cur]
        elif op["op"] == "set-inline":
            inline.setdefault(i, {}).update(op["props"])
        else:
            attrs.setdefault(i, {})[op["name"]] = op["value"]
    return cls, attrs, inline


def check_patches(vanilla_path, built_path, docs):
    """Gate for a patched layout bundle: for every patch file, the built layout must be the vanilla layout plus exactly the edits asked
    for, and nothing else in it or in its inline sheet may differ. Returns a list of failures."""
    import UnityPy
    from . import verify_static as vs
    fail = []
    venv, benv = UnityPy.load(str(vanilla_path)), UnityPy.load(str(built_path))
    vo, bo = {o.path_id: o for o in venv.objects}, {o.path_id: o for o in benv.objects}
    for doc in docs:
        lay = doc["layout"]
        where = "%s:" % lay["name"]
        try:
            pid = int(lay["path_id"]) if lay.get("path_id") and int(lay["path_id"]) in vo and vo[int(lay["path_id"])].peek_name() == lay["name"] else \
                next(p for p, o in vo.items() if o.type.name == "MonoBehaviour" and o.peek_name() == lay["name"] and "m_VisualTree" in o.read_typetree())
            vt, bt = vo[pid].read_typetree(), bo[pid].read_typetree()
            cls, attrs, inline = _expected(vt, doc["ops"], where)
        except Exception as ex:
            fail.append("%s cannot be checked (%s)" % (where, ex))
            continue
        sp = (vt.get("inlineSheet") or {}).get("m_PathID", 0)
        vs_t = vo[sp].read_typetree() if sp in vo else None
        bs_t = bo[sp].read_typetree() if sp in bo else None
        for k in vt:                                           # everything but the registry is untouched
            if k != "references" and bundles.first_difference(vt[k], bt.get(k)) is not None:
                fail.append("%s field %s changed" % (where, k))
        vref, bref = registry(vt), registry(bt)
        if set(vref) != set(bref):
            fail.append("%s the element set changed" % where)
            continue
        n_old = len((vs_t or {}).get("m_Rules", []))
        new_ids = sorted(i for i in inline if next((r["data"]["m_RuleIndex"] for r in vref.values() if (r.get("data") or {}).get("m_Id") == i), -1) < 0)
        rule_of, sd_rids, handled = {}, set(), set()
        for rid, vr in vref.items():
            br = bref[rid]
            vd, bd = vr.get("data"), br.get("data")
            if vd is None or bd is None:
                if vd != bd:
                    fail.append("%s entry %s changed" % (where, rid))
                continue
            if "m_Id" not in vd:                               # a serialized-data entry: checked with its element, or untouched
                sd_rids.add(rid)
                continue
            i = vd.get("m_Id")
            for k in vd:
                if k in ("m_Classes", "m_RuleIndex", "m_SerializedData"):
                    continue
                if bundles.first_difference(vd[k], bd.get(k)) is not None:
                    fail.append("%s element %s field %s changed" % (where, i, k))
            if bd.get("m_Classes") != cls.get(i, vd.get("m_Classes")):
                fail.append("%s element %s classes are %s, expected %s" % (where, i, bd.get("m_Classes"), cls.get(i, vd.get("m_Classes"))))
            if i in inline:
                rule_of[i] = bd.get("m_RuleIndex", -1)
                if vd.get("m_RuleIndex", -1) >= 0 and rule_of[i] != vd["m_RuleIndex"]:
                    fail.append("%s element %s changed its rule index" % (where, i))
            elif bd.get("m_RuleIndex") != vd.get("m_RuleIndex"):
                fail.append("%s element %s rule index changed without an edit" % (where, i))
            vsd, bsd = (vref.get((vd.get("m_SerializedData") or {}).get("rid")) or {}).get("data"), (bref.get((bd.get("m_SerializedData") or {}).get("rid")) or {}).get("data")
            if (vd.get("m_SerializedData") or {}) != (bd.get("m_SerializedData") or {}):
                fail.append("%s element %s serialized data reference changed" % (where, i))
            if isinstance(vsd, dict) and isinstance(bsd, dict):
                handled.add((vd.get("m_SerializedData") or {}).get("rid"))
                want = attrs.get(i, {})
                for k in vsd:
                    if k in want:
                        v = want[k]
                        v = int(v) if isinstance(vsd[k], int) and isinstance(v, bool) else v
                        if bsd.get(k) != (float(v) if isinstance(vsd[k], float) else v) or (k + "_UxmlAttributeFlags" in vsd and bsd.get(k + "_UxmlAttributeFlags") != 1):
                            fail.append("%s element %s attribute %s is %r, expected %r" % (where, i, k, bsd.get(k), v))
                    elif k.endswith("_UxmlAttributeFlags") and k[:-len("_UxmlAttributeFlags")] in want:
                        continue
                    elif bundles.first_difference(vsd[k], bsd.get(k)) is not None:
                        fail.append("%s element %s attribute %s changed without an edit" % (where, i, k))
        for rid in sd_rids - handled:                          # serialized data nobody addressed must be identical
            if bundles.first_difference(vref[rid].get("data"), bref[rid].get("data")) is not None:
                fail.append("%s serialized data %s changed without an edit" % (where, rid))
        if inline:
            if vs_t is None or bs_t is None:
                fail.append("%s has no inline sheet" % where)
                continue
            if len(bs_t["m_Rules"]) != n_old + len(new_ids):
                fail.append("%s inline sheet has %d rules, expected %d" % (where, len(bs_t["m_Rules"]), n_old + len(new_ids)))
                continue
            targeted = set()
            for i, props in inline.items():
                ri = rule_of.get(i, -1)
                if not 0 <= ri < len(bs_t["m_Rules"]):
                    fail.append("%s element %s has no inline rule after the build" % (where, i))
                    continue
                targeted.add(ri)
                before = vs_t["m_Rules"][ri]["m_Properties"] if ri < n_old else []
                after = bs_t["m_Rules"][ri]["m_Properties"]
                slots = [{"orig": p, "name": None, "types": None} for p in before]
                for k, v in props.items():
                    same = [s for s in slots if (tp.prop_matches(s["orig"], k) if s["orig"] is not None else s["name"] == k)]
                    for s in same:
                        s["types"] = vs._value_types(_text(v))
                    if not same:
                        slots.append({"orig": None, "name": k, "types": vs._value_types(_text(v))})
                ok = len(after) == len(slots)
                for s, p in zip(slots, after):
                    if s["orig"] is not None:
                        ok &= p.get("m_Id") == s["orig"].get("m_Id") and p.get("m_CustomName") == s["orig"].get("m_CustomName")
                        ok &= (p["m_Values"] == s["orig"]["m_Values"]) if s["types"] is None else [h["m_ValueType"] for h in p["m_Values"]] == s["types"]
                    else:
                        ok &= tp.prop_matches(p, s["name"]) and [h["m_ValueType"] for h in p["m_Values"]] == s["types"]
                if not ok:
                    fail.append("%s inline rule %d does not hold the asked-for properties" % (where, ri))
            for ri in range(n_old):
                if ri not in targeted and bundles.first_difference(vs_t["m_Rules"][ri], bs_t["m_Rules"][ri]) is not None:
                    fail.append("%s inline rule %d changed without an edit" % (where, ri))
        elif vs_t is not None and bs_t is not None and bundles.first_difference(vs_t, bs_t) is not None:
            fail.append("%s the inline sheet changed without an inline edit" % where)
    return fail
