"""Phase 6: UXML layouts (read, per-layout patches, gate) and native fonts. Synthetic layouts for the logic; the real game's layout bundles
(skipped without them) for the UnityPy round trip, apply and gate."""
import copy, json, tempfile, unittest
from pathlib import Path

from skin_editor import bundles, config, plan, project, projfmt, uxml
from skin_editor import token_patch as tp
from tests.test_preview import index

GAME = Path(r"C:\Program Files (x86)\Steam\steamapps\common\Football Manager 27\fm_Data\StreamingAssets\aa\StandaloneWindows64")
BUNDLE = "ui-visualtreeassets_assets_fantasydraftvisualtreeassetpreload.bundle"
needs_game = unittest.skipUnless((GAME / BUNDLE).is_file(), "needs the game's layout bundles")


def ref(rid, cls, data):
    return {"rid": rid, "type": {"class": cls, "ns": "", "asm": ""}, "data": data}


def el(i, typ, name, classes, kids, rule=-1, sd=None, rid=None):
    return ref(rid, "VisualElementAsset", {"m_FullTypeName": typ, "m_Id": i, "m_Children": [{"rid": k} for k in kids], "m_RuleIndex": rule, "m_Classes": list(classes),
                                           "m_Properties": [], "m_SerializedData": {"rid": sd}})


def layout():
    """root(1) > panel(2, rule 0) > label(3, text attr) ; inline sheet with one rule (height 34px)."""
    sd = lambda rid, typ, **kw: ref(rid, typ + "/UxmlSerializedData", dict({"uxmlAssetId": 0, "name": "", "bindings": [], "name_UxmlAttributeFlags": 0}, **kw))
    t = {"m_Name": "Demo", "m_Usings": [], "inlineSheet": {"m_FileID": 0, "m_PathID": 77}, "m_VisualTree": {"rid": 1001},
         "references": {"version": 2, "RefIds": [
             {"rid": -2, "type": {"class": "", "ns": "", "asm": ""}},
             el(1, "UnityEngine.UIElements.UXML", "", [], [1002], rid=1001, sd=-2),
             el(2, "SI.Bindable.SIVisible", "", ["a", "b"], [1003], rule=0, rid=1002, sd=2000),
             el(3, "SI.SIText", "", ["label"], [], rid=1003, sd=2001),
             sd(2000, "SIVisible", name="panel"),
             sd(2001, "SIText", name="title", text="Hello", text_UxmlAttributeFlags=0, count=3, count_UxmlAttributeFlags=1, TextBinding="x")]}}
    t["references"]["RefIds"][2]["data"]["m_SerializedData"] = {"rid": 2000}
    t["references"]["RefIds"][3]["data"]["m_SerializedData"] = {"rid": 2001}
    sheet = {"m_Name": "inlineStyle", "floats": [], "dimensions": [{"value": 34.0, "unit": 1}], "colors": [], "strings": [], "assets": [],
             "m_Rules": [{"m_ComplexSelectors": [], "m_Properties": [{"m_Id": tp.PROP_TABLE["height"], "m_CustomName": "", "m_Line": -1, "m_Values": [{"m_ValueType": 3, "valueIndex": 0}]}], "line": -1}]}
    return t, sheet


G = lambda typ, name="": {"type": typ, "name": name}


class Ops(unittest.TestCase):
    def test_validation(self):
        lay = {"bundle": BUNDLE, "name": "Demo", "path_id": "5"}
        ok = {"schema": 1, "layout": lay, "ops": [{"op": "set-classes", "id": 2, "guard": G("SIVisible", "panel"), "add": ["x"]}]}
        uxml.validate_doc(ok)
        bad = lambda **kw: self.assertRaises(ValueError, uxml.validate_doc, dict(ok, **kw))
        bad(ops=[{"op": "add-element", "id": 2, "guard": G("A")}])                                                  # structural ops do not exist
        bad(ops=[{"op": "set-classes", "id": 2, "guard": G("A"), "add": ["bad class"]}])
        bad(ops=[{"op": "set-classes", "id": 2, "guard": G("A"), "add": ["x"], "remove": ["x"]}])
        bad(ops=[{"op": "set-classes", "id": 2, "add": ["x"]}])                                                      # no guard
        bad(ops=[{"op": "set-attr", "id": 2, "guard": G("A"), "name": "name", "value": "x"}])                      # names are structure
        bad(ops=[{"op": "set-attr", "id": 2, "guard": G("A"), "name": "TextBinding", "value": "x"}])               # bindings are read-only
        bad(ops=[{"op": "set-inline", "id": 2, "guard": G("A"), "props": {"not-a-property": "1px"}}])
        bad(layout={"bundle": "nope.bundle", "name": "x"})

    def test_merge_ops(self):
        doc = {"schema": 1, "layout": {"bundle": BUNDLE, "name": "Demo"}, "ops": []}
        g = G("SIVisible", "panel")
        uxml.merge_op(doc, {"op": "set-classes", "id": 2, "guard": g, "add": ["x"]})
        uxml.merge_op(doc, {"op": "set-classes", "id": 2, "guard": g, "add": ["y"], "remove": ["a"]})
        self.assertEqual(doc["ops"][0]["add"], ["x", "y"]); self.assertEqual(doc["ops"][0]["remove"], ["a"])
        uxml.merge_op(doc, {"op": "set-classes", "id": 2, "guard": g, "remove": ["x", "y"], "add": ["a"]})            # cancels what was asked before
        self.assertEqual(doc["ops"], [])
        uxml.merge_op(doc, {"op": "set-inline", "id": 2, "guard": g, "props": {"height": "10px"}})
        uxml.merge_op(doc, {"op": "set-inline", "id": 2, "guard": g, "props": {"opacity": "0.5", "height": None}})
        self.assertEqual(doc["ops"][0]["props"], {"opacity": "0.5"})
        uxml.merge_op(doc, {"op": "set-inline", "id": 2, "guard": g, "props": {"opacity": None}}); self.assertEqual(doc["ops"], [])
        uxml.merge_op(doc, {"op": "set-attr", "id": 3, "guard": G("SIText", "title"), "name": "text", "value": "a"})
        uxml.merge_op(doc, {"op": "set-attr", "id": 3, "guard": G("SIText", "title"), "name": "text", "value": "b"})
        self.assertEqual([o["value"] for o in doc["ops"]], ["b"])

    def test_apply_to_a_layout(self):
        t, sheet = layout()
        ops = [{"op": "set-classes", "id": 2, "guard": G("SIVisible", "panel"), "add": ["x", "a"], "remove": ["b"]},
               {"op": "set-inline", "id": 2, "guard": G("SIVisible", "panel"), "props": {"opacity": "0.5"}},        # existing inline rule: opacity is added to it
               {"op": "set-inline", "id": 3, "guard": G("SIText", "title"), "props": {"display": "none"}},          # no rule yet: a new one is appended
               {"op": "set-attr", "id": 3, "guard": G("SIText", "title"), "name": "text", "value": "Bye"},
               {"op": "set-attr", "id": 3, "guard": G("SIText", "title"), "name": "count", "value": 5}]
        before = copy.deepcopy((t, sheet))
        notes, changed = uxml.apply_to_layout(t, sheet, ops, "demo:")
        refs = uxml.registry(t)
        self.assertEqual(refs[1002]["data"]["m_Classes"], ["a", "x"]); self.assertEqual(refs[1002]["data"]["m_RuleIndex"], 0)
        self.assertEqual(len(sheet["m_Rules"]), 2); self.assertEqual(refs[1003]["data"]["m_RuleIndex"], 1)
        self.assertEqual(uxml.inline_rule(sheet, 0), [("height", "34px"), ("opacity", "0.5")]); self.assertEqual(uxml.inline_rule(sheet, 1), [("display", "none")])
        sd = refs[2001]["data"]
        self.assertEqual((sd["text"], sd["text_UxmlAttributeFlags"], sd["count"], sd["count_UxmlAttributeFlags"]), ("Bye", 1, 5, 1))
        self.assertEqual(sheet["dimensions"][:1], before[1]["dimensions"])                                         # pools only grow
        self.assertTrue(changed)
        # the element tree reads back the same way
        e = uxml.element(t, refs, 1002); self.assertEqual((e["type"], e["name"], e["classes"]), ("SIVisible", "panel", ["a", "x"]))

    def test_guards_and_vanilla_only_attributes(self):
        for op, msg in (({"op": "set-classes", "id": 2, "guard": G("SIText", "panel"), "add": ["x"]}, "now SIVisible#panel"),
                        ({"op": "set-classes", "id": 2, "guard": G("SIVisible", "other"), "add": ["x"]}, "now SIVisible#panel"),
                        ({"op": "set-classes", "id": 99, "guard": G("SIVisible"), "add": ["x"]}, "no element with id 99"),
                        ({"op": "set-attr", "id": 3, "guard": G("SIText", "title"), "name": "tooltip", "value": "x"}, "only attributes the game already uses"),
                        ({"op": "set-attr", "id": 3, "guard": G("SIText", "title"), "name": "count", "value": "five"}, "is int, not str")):
            t, sheet = layout()
            with self.assertRaises(ValueError) as c:
                uxml.apply_to_layout(t, sheet, [op], "demo:")
            self.assertIn(msg, str(c.exception))
            self.assertEqual((t, sheet), layout())                                                                   # nothing was half applied for a refused op


class Storage(unittest.TestCase):
    def test_patch_files_round_trip_in_the_project_folder_and_the_plan(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            ws = config.Workspace(Path(tmp) / "ws")
            p = project.new("lp"); p["options"]["output"] = "bundles"
            p["layout_patches"] = [{"schema": 1, "layout": {"bundle": BUNDLE, "name": "Demo layout", "path_id": "-5"}, "ops": [
                {"op": "set-classes", "id": 2, "guard": G("SIVisible", "panel"), "add": ["x"]},
                {"op": "set-inline", "id": 2, "guard": G("SIVisible", "panel"), "props": {"opacity": "0.5"}},
                {"op": "set-attr", "id": 3, "guard": G("SIText", "title"), "name": "text", "value": "Hi"}]}]
            projfmt.write(ws, p)
            f = projfmt.folder(ws, "lp") / "layouts" / "Demo_layout.patch.json"
            self.assertTrue(f.is_file()); self.assertEqual(json.loads(f.read_text())["ops"][0]["add"], ["x"])
            q = projfmt.read(ws, "lp"); self.assertEqual(q["layout_patches"], p["layout_patches"])
            pl = plan.plan(ws, q, index(), None, "bundles")
            self.assertTrue({"SetClasses", "SetInline", "SetAttr"} <= {o["op"] for o in pl["operations"]})
            pn = plan.plan(ws, q, index(), None, "native")
            self.assertTrue(any("layout edit" in d["item"] and "native skin cannot" in d["reason"] for d in pn["dropped"]))
            self.assertEqual(project.to_spec(q)["layout_patches"], p["layout_patches"])
            f.write_text('{"schema": 1, "layout": {"bundle": "x", "name": "y"}, "ops": []}')                         # a hand edit that breaks the file is a problem, not a crash
            _, problems = projfmt.read(ws, "lp", strict=False)
            self.assertTrue(any(x["file"] == "layouts/Demo_layout.patch.json" for x in problems))
            p["layout_patches"] = []; projfmt.write(ws, p); self.assertFalse(f.exists())                              # an unpatched layout loses its file


class Fonts(unittest.TestCase):
    def test_native_export_writes_the_font_the_url_rule_and_the_gate_passes(self):
        from skin_editor import native
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            ws = config.Workspace(Path(tmp) / "ws"); root = Path(tmp) / "skins"; root.mkdir()
            p = project.new("fo"); p["options"]["output"] = "native"
            p["font_swaps"] = [{"token": "--typography-family-primary", "source": "my-font.ttf"}]
            projfmt.write(ws, p)
            fd = projfmt.folder(ws, "fo") / "fonts"; fd.mkdir(); (fd / "my-font.ttf").write_bytes(b"\x00\x01\x00\x00fakefont")
            q = projfmt.read(ws, "fo")
            self.assertEqual(q["font_swaps"], p["font_swaps"])
            rep = native.export(ws, q, index(), None, root, "fo")
            self.assertEqual((rep["problems"], rep["fonts"]), ([], 1))
            out = Path(rep["folder"])
            self.assertEqual((out / "fonts" / "my-font.ttf").read_bytes(), b"\x00\x01\x00\x00fakefont")
            self.assertIn('--typography-family-primary: url("fonts/my-font.ttf");', (out / "tokens.uss").read_text())
            self.assertIn("tokens.uss", json.loads((out / "skin.json").read_text())["Sheets"])
            (out.parent / "fo2").mkdir()                                                                               # gate: a url() that points nowhere is reported
            (out / "fonts" / "my-font.ttf").unlink()
            self.assertTrue(any("url(" in x or "missing" in x for x in native.validate(out)))
            pl = plan.plan(ws, q, index(), None, "native"); self.assertIn("WriteFont", [o["op"] for o in pl["operations"]])
            pb = plan.plan(ws, q, index(), None, "bundles"); self.assertTrue(any("FONTS-SPIKE" in d["reason"].upper() for d in pb["dropped"]))
            # a project with the font file missing says so instead of exporting a dangling url()
            (fd / "my-font.ttf").unlink()
            with self.assertRaises(ValueError): projfmt.read(ws, "fo")                                                # mapping: source file is missing
            self.assertTrue(any("missing" in x["message"] for x in projfmt.read(ws, "fo", strict=False)[1]))

    def test_font_swap_validation(self):
        p = project.new("x"); p["font_swaps"] = [{"token": "--t", "source": "a.ttf"}, {"token": "--t", "source": "b.otf"}]
        with self.assertRaises(ValueError): project.validate(p)
        p["font_swaps"] = [{"token": "t", "source": "a.ttf"}]
        with self.assertRaises(ValueError): project.validate(p)
        p["font_swaps"] = [{"token": "--t", "source": "a.exe"}]
        with self.assertRaises(ValueError): project.validate(p)


@needs_game
class RealLayouts(unittest.TestCase):
    """The game's own fantasy-draft layout bundle: UnityPy must write VisualTreeAssets back exactly, and the gate must hold."""

    def digests(self, path):
        return bundles.object_digests(path)[0]

    def test_unchanged_round_trip_is_exact_then_apply_and_gate(self):
        import UnityPy
        uxml.fix_unitypy_writer()
        L = uxml.Layouts(GAME)
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            out = Path(tmp)
            env = UnityPy.load(str(GAME / BUNDLE)); n = 0
            for o in env.objects:
                if o.type.name == "MonoBehaviour":
                    t = o.read_typetree()
                    if "m_VisualTree" in t:
                        o.save_typetree(t); n += 1
            (out / "rt").mkdir(); env.save(pack="original", out_path=str(out / "rt"))
            v, b = self.digests(GAME / BUNDLE), self.digests(out / "rt" / BUNDLE)
            self.assertGreater(n, 50); self.assertEqual(set(v), set(b)); self.assertEqual([k for k in v if v[k][:2] != b[k][:2]], [])
            row = next(r for r in L.list() if r["name"] == "ShuffleDraft_HelpPanel")
            tr = L.tree(row["bundle"], row["path_id"])
            find = lambda e, i: e if e["id"] == i else next((r for c in e["children"] for r in [find(c, i)] if r), None)
            btn, grad, txt = (find(tr["root"], i) for i in (-380929026, 421011723, -1100122572))
            g = lambda e: {"type": e["type"], "name": e["name"]}
            doc = {"schema": 1, "layout": {"bundle": BUNDLE, "name": row["name"], "path_id": row["path_id"]}, "ops": [
                {"op": "set-classes", "id": btn["id"], "guard": g(btn), "add": ["p6-test-class"], "remove": [btn["classes"][0]]},
                {"op": "set-inline", "id": btn["id"], "guard": g(btn), "props": {"height": "40px", "opacity": "0.5"}},
                {"op": "set-inline", "id": grad["id"], "guard": g(grad), "props": {"display": "none"}},
                {"op": "set-attr", "id": txt["id"], "guard": g(txt), "name": "text", "value": "patched"}]}
            uxml.validate_doc(doc)
            (out / "b").mkdir(); touched = set()
            changed, _, done = uxml.apply_patches(GAME / BUNDLE, out / "b", [doc], touched)
            self.assertTrue(changed); self.assertEqual(len(touched), 2)                                             # the layout and its inline sheet
            b2 = self.digests(out / "b" / BUNDLE)
            self.assertEqual(set(v), set(b2)); self.assertEqual({k for k in v if v[k][:2] != b2[k][:2]}, touched)
            self.assertEqual(uxml.check_patches(GAME / BUNDLE, out / "b" / BUNDLE, [doc]), [])
            nb = uxml.Layouts(out / "b").tree(row["bundle"], row["path_id"])
            nbtn, ngrad = find(nb["root"], btn["id"]), find(nb["root"], grad["id"])
            self.assertEqual((nbtn["classes"][-1], nbtn["inline"], ngrad["inline"]), ("p6-test-class", [("height", "40px"), ("opacity", "0.5")], [("display", "none")]))
            # the gate notices a build that is not what the patch file asks for
            other = json.loads(json.dumps(doc)); other["ops"][3]["value"] = "something else"
            (out / "c").mkdir(); uxml.apply_patches(GAME / BUNDLE, out / "c", [other], set())
            self.assertTrue(uxml.check_patches(GAME / BUNDLE, out / "c" / BUNDLE, [doc]))
            # class usage over every layout agrees with the trees
            u = L.class_usage("p6-test-class"); self.assertEqual(u["layouts"], [])
            self.assertGreater(len(L.class_usage("flex-grow-class")["layouts"]), 10)
