"""Phase 2: USS print/parse fidelity and diagnostics. The vanilla-sheet round trip runs against the game's real sheets when the style
index exists on this machine (skipped otherwise); the rest uses synthetic sheets."""
import json, random, unittest
from pathlib import Path

from skin_editor import config, index_styles, projfmt, ussdiag, ussprint
from tests.test_preview import index


def entry(*rules, name="S"):
    return {"name": name, "bundle": "b", "rules": [{"i": i, "s": list(s), "t": 0, "p": [[n, v, []] for n, v in p]} for i, (s, p) in enumerate(rules)], "failures": []}


class Parser(unittest.TestCase):
    def test_structure_comments_strings_and_meta(self):
        src = ('/* head */\n:root {\n    /* meta: {"vanilla": "#DA71FE"} */\n    --a: #112233;\n}\n'
               'a[x="}{;"], .b > .c:hover {\n    background-image: url("a;b.png");\n    content: \'x}\';\n    color: red\n}\n')
        rules, problems = projfmt.parse_uss(src, "f")
        self.assertEqual(problems, [])
        self.assertEqual([r["selector"] for r in rules], [":root", 'a[x="}{;"], .b > .c:hover'])
        self.assertEqual(rules[0]["decls"][0][:3], ("--a", "#112233", {"vanilla": "#DA71FE"}))
        self.assertEqual([d[:2] for d in rules[1]["decls"]], [("background-image", 'url("a;b.png")'), ("content", "'x}'"), ("color", "red")])

    def test_problems_carry_lines(self):
        _, p = projfmt.parse_uss("a {\n  color red;\n}\nb {\n  x: y;\n", "f")
        self.assertEqual([(x["line"], x["message"][:20]) for x in p][:1], [(2, "declaration without ")]); self.assertTrue(any("not closed" in x["message"] for x in p))
        _, p = projfmt.parse_uss("}\n", "f"); self.assertIn("unexpected", p[0]["message"])

    def test_print_then_parse_is_identity_on_tricky_values(self):
        e = entry((["a", ".b > .c"], [("background-image", 'url("x;y.png")'), ("--t", "var(--u)"), ("font", "12px/1.5 'A}B', serif"), ("content", '"{;}"')]),
                  ([":root"], [("--k", "#AABBCC80"), ("--e", "")]), ([], [("opacity", "0")]), (["x:not(.y, .z)"], [("color", "rgba(1, 2, 3, 0.5)")]))
        self.assertEqual(ussprint.roundtrip(e), [])

    def test_fuzz_random_rules_round_trip(self):
        rnd = random.Random(27)
        alphabet = list("abcXYZ0129-_.#>:()%,\"' ") + ["{", "}", ";", "/*", "*/"]
        def junk(n):  # values and selectors may hold quotes with structure characters inside, never bare ones
            s = "".join(rnd.choice(alphabet) for _ in range(n)).replace("/*", "").replace("*/", "")
            for ch in "{};":
                s = s.replace(ch, "")
            return "".join(c for c in s if c not in "\"'") or "x"
        rules = []
        for _ in range(300):
            sel = [junk(rnd.randint(1, 12)) + (rnd.choice(["", '[a="}{;"]', "[b='x;y']"])) for _ in range(rnd.randint(1, 3))]
            decls = [("p-" + "".join(c for c in junk(5) if c.isalnum() or c in "-_"), junk(rnd.randint(1, 20)) + rnd.choice(["", ' "a;b}"', " url('c{d.png')"])) for _ in range(rnd.randint(1, 5))]
            rules.append((sel, decls))
        e = entry(*rules)
        self.assertEqual(ussprint.roundtrip(e), [])


@unittest.skipUnless((config.workspace(config.load()).cache).is_dir() and index_styles.load(config.workspace(config.load())), "needs the style index of the installed game")
class VanillaSheets(unittest.TestCase):
    def test_every_vanilla_sheet_prints_and_parses_back_equal(self):
        ix = index_styles.load(config.workspace(config.load()))
        self.assertGreaterEqual(len(ix.sheets), 40)
        for sh in ix.sheets:
            self.assertEqual(ussprint.roundtrip(sh), [], sh["name"])
        self.assertGreater(sum(len(s["rules"]) for s in ix.sheets), 10000)


class Diagnostics(unittest.TestCase):
    def codes(self, text, ix=None):
        return [(d["line"], d["severity"], d["code"]) for d in ussdiag.check(text, ix or index())]

    def test_syntax_without_an_index(self):
        d = ussdiag.check("a { color red; }\nb {", None)
        self.assertTrue(all(x["severity"] == "error" and x["code"] == "syntax" for x in d)); self.assertTrue(d)

    def test_unknown_property_token_colour_unit_and_class(self):
        ix = index()
        # the fixture index defines --base/--alias/--deep/--lit and the property names it uses
        text = (".grad {\n    --start-colour: var(--base);\n}\n.x {\n    colr: red;\n    color: var(--nope);\n    background-color: #12;\n"
                "    width: 12pt;\n    height: 4px;\n}\n")
        got = self.codes(text, ix)
        self.assertIn((5, "warning", "unknown-property"), got); self.assertIn((6, "warning", "unknown-token"), got)
        self.assertIn((7, "error", "bad-colour"), got); self.assertIn((8, "warning", "unit"), got)
        self.assertNotIn((9, "warning", "unit"), got); self.assertNotIn((2, "warning", "unknown-token"), got)
        self.assertIn((4, "info", "class-unused"), got); self.assertNotIn((1, "info", "class-unused"), got)               # .grad exists in the fixture's sheet
        d = [x for x in ussdiag.check(text, ix) if x["code"] == "unknown-property"][0]
        self.assertEqual((d["col"], d["end_col"]), (5, 9))                                                                 # the highlight covers the name

    def test_own_root_tokens_count_as_defined_and_typos_get_suggestions(self):
        text = ":root {\n    --mine: #112233;\n}\n.a {\n    color: var(--mine);\n    border-colour: var(--bas);\n}\n"
        got = {(x["code"], x.get("suggest")) for x in ussdiag.check(text, index())}
        self.assertNotIn(("unknown-token", None), {(c, s) for c, s in got if s is None and False})
        self.assertFalse(any(x["code"] == "unknown-token" and "--mine" in x["message"] for x in ussdiag.check(text, index())))
        self.assertIn(("unknown-token", "--base"), got)                                                                     # --bas -> --base


if __name__ == "__main__":
    unittest.main()


class PlanAndEngine(unittest.TestCase):
    def setUp(self):
        import json, os, tempfile
        from unittest import mock
        from skin_editor import project
        from skin_editor.api import rpc
        from skin_editor.engine import Engine
        self.tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True); self.addCleanup(self.tmp.cleanup)
        with mock.patch.dict(os.environ, {"FM27SE_WORKSPACE": self.tmp.name}):
            self.e = Engine()
        self.e.index = index()
        self.call = lambda m, p=None: json.loads(rpc.handle(self.e, json.dumps({"jsonrpc": "2.0", "id": 1, "method": m, "params": p or {}})))
        self.addCleanup(lambda: [logging_close() for logging_close in ()])
        p = project.new("demo")
        p["token_overrides"] = [{"token": "--base", "value": {"rgb": "#AA0000", "a": 1.0}}, {"token": "--ghost", "value": {"rgb": "#010101", "a": 1.0}}]
        p["scoped_rules"] = [{"sheet": "AlwaysAppliedStyleSheet", "selector": ".x", "props": {"color": {"rgb": "#FF0000", "a": 1.0}}}, {"sheet": "NoSuchSheet", "selector": ".y", "props": {"color": "red"}}]
        p["rename_classes"] = {"a": "b"}; p["options"]["flatten_gradients"] = True; p["options"]["club_colours"] = False
        p["literal_swaps"] = [{"from": {"rgb": "#DA0037", "a": 1.0}, "to": {"rgb": "#6C001C", "a": 1.0}, "mode": "rgb-keep-alpha"}]
        project.save(self.e.ws, p)

    def test_plan_for_both_targets_lists_operations_and_what_is_dropped(self):
        nat = self.call("build.plan", {"project": "demo", "target": "native"})["result"]
        kinds = [o["op"] for o in nat["operations"]]
        self.assertIn("RewriteToken", kinds); self.assertIn("NativeWriteSheet", kinds); self.assertNotIn("RenameClass", kinds)
        self.assertEqual({d["item"].split(" (")[0] for d in nat["dropped"]}, {"class renames", "flatten_gradients"})
        self.assertTrue(any("--ghost" in w for w in nat["warnings"])); self.assertTrue(any("NoSuchSheet" in w for w in nat["warnings"]))
        self.assertEqual(next(o for o in nat["operations"] if o["op"] == "RewriteToken")["count"], 2)
        bun = self.call("build.plan", {"project": "demo", "target": "bundles"})["result"]
        self.assertIn("RenameClass", [o["op"] for o in bun["operations"]]); self.assertEqual(bun["dropped"], [])
        self.assertEqual(self.call("build.plan", {"project": "demo", "target": "usb"})["error"]["code"], -32602)

    def test_diagnostics_and_vanilla_sheet_methods(self):
        d = self.call("uss.diagnostics", {"text": ".x { colr: red; }"})["result"]["diagnostics"]
        self.assertEqual([x["code"] for x in d if x["code"] != "class-unused"], ["unknown-property"])
        self.assertEqual([s["name"] for s in self.call("game.sheets")["result"]], ["AlwaysAppliedStyleSheet"])
        s = self.call("game.sheet", {"name": "AlwaysAppliedStyleSheet"})["result"]
        self.assertIn(":root {", s["text"]); self.assertEqual(self.call("game.sheet", {"name": "Nope"})["error"]["code"], -32004)
        self.assertEqual(ussprint.parse_model(s["text"])[1], [])


class NativeImport(unittest.TestCase):
    def make_skin(self, root):
        d = Path(root) / "skin-a"; (d / "img").mkdir(parents=True)
        (d / "skin.json").write_text('{"Name": "Skin A", "Sheets": ["one.uss", "two.uss"]}')
        (d / "one.uss").write_text(':root { --a: #112233; }\n.p { background-image: url("img/t.png"); }\n')
        (d / "two.uss").write_text("/* later sheet */\n.q { color: red; }\n")
        (d / "img" / "t.png").write_bytes(b"\x89PNG\r\n\x1a\nfake")
        return d

    def test_import_lays_out_a_project_and_export_works_and_the_source_is_never_written(self):
        import hashlib, json, tempfile
        from skin_editor import native, plan, project
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            src = self.make_skin(tmp); ws = config.Workspace(Path(tmp) / "ws")
            digest = lambda f: {p.relative_to(f).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(Path(f).rglob("*")) if p.is_file()}
            before = digest(src)
            r = projfmt.import_native_skin(ws, src, "a"); self.assertEqual((r["name"], r["sheets"], r["images"]), ("Skin A", 2, 1))
            d = projfmt.folder(ws, "a")
            self.assertFalse((d / "native").exists())                                                                  # the normal project layout
            self.assertTrue((d / "styles" / "one.uss").is_file() and (d / "images" / "img" / "t.png").is_file())
            self.assertIn('url("../images/img/t.png")', (d / "styles" / "one.uss").read_text())
            p = project.load(ws, "a")
            self.assertEqual((p["native_sheets"], p["native_support"], p["native_name"], p["options"]["output"]),
                             (["styles/one.uss", "styles/two.uss"], ["images/img/t.png"], "Skin A", "native"))
            self.assertEqual(projfmt.read(ws, "a")["native_sheets"], p["native_sheets"])
            out = Path(tmp) / "skins"; out.mkdir()
            rep = native.export(ws, p, index(), None, out, "a-out")
            self.assertEqual(rep["problems"], []); self.assertEqual(rep["sheets"], ["one.uss", "two.uss"])             # empty own sheets are not added
            self.assertEqual((rep["tokens"], rep["rules"], rep["images"]), (1, 3, 1))                                  # the imported content is counted
            o = Path(rep["folder"])
            self.assertEqual((o / "images" / "img" / "t.png").read_bytes(), (src / "img" / "t.png").read_bytes())
            self.assertIn('url("images/img/t.png")', (o / "one.uss").read_text()); self.assertEqual((o / "two.uss").read_text(), (src / "two.uss").read_text())
            self.assertEqual(digest(src), before)
            self.assertEqual(json.loads((o / "skin.json").read_text()), {"Name": "Skin A", "Sheets": ["one.uss", "two.uss"]})
            # the project's own edits come after the imported sheets and win ties; own sheets and imported ones survive a save
            p["token_overrides"] = [{"token": "--b", "value": {"rgb": "#445566", "a": 1.0}}]; project.save(ws, p)
            self.assertTrue((d / "styles" / "one.uss").is_file())
            rep2 = native.export(ws, project.load(ws, "a"), index(), None, out, "a-out")
            self.assertEqual(rep2["sheets"], ["one.uss", "two.uss", "tokens.uss"])
            self.assertEqual(plan.plan(ws, project.load(ws, "a"), index(), None, "bundles")["dropped"][0]["item"], "2 native sheet(s) of Skin A")
            self.assertIn("NativeSheetPassthrough", [o["op"] for o in plan.plan(ws, project.load(ws, "a"), index(), None, "native")["operations"]])
            with self.assertRaises(ValueError): projfmt.import_native_skin(ws, src, "a")                              # the name is taken
            (src / "skin.json").write_text('{"Name": "x", "Sheets": ["gone.uss"]}')
            with self.assertRaises(FileNotFoundError): projfmt.import_native_skin(ws, src, "b")
            self.assertFalse(projfmt.folder(ws, "b").exists())                                                        # a failed import leaves nothing behind

    def test_old_native_folder_layout_is_reported_and_delete_moves_to_trash(self):
        import tempfile
        from skin_editor import project
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            ws = config.Workspace(Path(tmp) / "ws"); p = project.new("old"); p["options"]["output"] = "native"; projfmt.write(ws, p)
            d = projfmt.folder(ws, "old"); (d / "native").mkdir(); (d / "native" / "x.uss").write_text(".a { color: red; }")
            m = json.loads((d / "mapping.json").read_text()); m["entries"].append({"source": "native/x.uss", "mode": "native-sheet"})
            (d / "mapping.json").write_text(json.dumps(m))
            _, problems = projfmt.read(ws, "old", strict=False)
            self.assertTrue(any("import the skin folder again" in x["message"] for x in problems))
            where = project.delete(ws, "old")
            self.assertNotIn("old", project.names(ws)); self.assertTrue((Path(where) / "native" / "x.uss").is_file())

    @unittest.skipUnless(Path(r"C:\Users\Admin\Downloads\jonukas-wood\skin.json").is_file(), "needs the jonukas-wood skin")
    def test_jonukas_wood_imports_into_the_project_layout_and_exports_with_the_same_content(self):
        import hashlib, tempfile
        from skin_editor import native, project
        src = Path(r"C:\Users\Admin\Downloads\jonukas-wood")
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            ws = config.Workspace(Path(tmp) / "ws"); r = projfmt.import_native_skin(ws, src, "jw")
            d = projfmt.folder(ws, "jw")
            self.assertFalse((d / "native").exists()); self.assertEqual(len(list((d / "styles").glob("*.uss"))), 11)     # 10 sheets + tokens.uss
            self.assertEqual((r["images"], r["fonts"]), (len(list(src.glob("*.png"))), len(list(src.glob("*.ttf")))))
            rep = native.export(ws, project.load(ws, "jw"), index(), None, Path(tmp), "out")
            self.assertEqual(rep["problems"], [])
            self.assertGreater(rep["tokens"], 0); self.assertGreater(rep["rules"], 0); self.assertEqual(rep["images"], r["images"])
            o = Path(rep["folder"])
            for f in src.iterdir():
                if f.suffix in (".png", ".ttf"):
                    self.assertEqual(hashlib.sha256(f.read_bytes()).hexdigest(), hashlib.sha256(next(o.rglob(f.name)).read_bytes()).hexdigest(), f.name)
            for s in json.loads((src / "skin.json").read_text())["Sheets"]:                                          # same rules, urls aside
                a = projfmt.parse_uss((src / s).read_text(encoding="utf-8-sig"), s)[0]
                import re
                b = projfmt.parse_uss(re.sub(r'url\("(?:images|fonts|assets)/', 'url("', (o / s).read_text(encoding="utf-8-sig")), s)[0]
                self.assertEqual([(x["selector"], [(k, v) for k, v, _, _ in x["decls"]]) for x in a], [(x["selector"], [(k, v) for k, v, _, _ in x["decls"]]) for x in b], s)


class ReplaceRemove(unittest.TestCase):
    SEL = "SIGradient.pitch > .inner"            # the second rule of tests.test_core.sheet()

    def test_comment_syntax_parses_and_round_trips(self):
        import tempfile
        from skin_editor import project
        text = ('/* replace: .a */\n.a { color: red; }\n/* meta: {"why": "x"} */\n/* remove: .b .c | color, padding */\n'
                '/* remove: .d */\n.e { color: blue; }\n/* just a remark about replace: nothing */\n')
        rules, problems = projfmt.parse_uss(text, "f")
        self.assertEqual(problems, [])
        self.assertEqual([(r["selector"], r.get("op"), r.get("remove")) for r in rules],
                         [(".a", "replace", None), (".b .c", "remove", ["color", "padding"]), (".d", "remove", []), (".e", None, None)])
        self.assertEqual(rules[1]["meta"], {"why": "x"})
        self.assertTrue(any("must be the same selector" in p["message"] for p in projfmt.parse_uss("/* replace: .x */\n.y { color: red; }", "f")[1]))
        self.assertTrue(projfmt.parse_uss(".y { /* remove: .z */ color: red; }", "f")[1])
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            ws = config.Workspace(Path(tmp) / "ws"); p = project.new("rr")
            p["scoped_rules"] = [{"sheet": "S", "selector": ".a", "props": {"color": "#FF0000"}, "op": "replace", "why": "w"},
                                 {"sheet": "S", "selector": ".b .c", "props": {}, "op": "remove", "remove": ["color", "padding"]},
                                 {"sheet": "S", "selector": ".d", "props": {}, "op": "remove", "remove": []},
                                 {"sheet": "S", "selector": ".e", "props": {"color": "#0000FF"}}]
            projfmt.write(ws, p)
            self.assertIn("/* replace: .a */", (projfmt.folder(ws, "rr") / "styles" / "S.uss").read_text())
            q = projfmt.read(ws, "rr")
            self.assertEqual([(e["selector"], e.get("op"), e.get("remove")) for e in q["scoped_rules"]],
                             [(".a", "replace", None), (".b .c", "remove", ["color", "padding"]), (".d", "remove", []), (".e", None, None)])
            self.assertEqual(q["scoped_rules"][0]["why"], "w")
            bad = dict(p, scoped_rules=[{"sheet": "S", "selector": ".b", "props": {"color": "#FF0000"}, "op": "remove", "remove": []}])
            with self.assertRaises(ValueError): project.validate(bad)

    def test_patch_replace_remove_and_gate(self):
        from skin_editor import patcher, project, verify_static
        from tests.test_core import sheet, acc
        p = project.new("x")
        p["scoped_rules"] = [
            {"sheet": "AlwaysAppliedStyleSheet", "selector": self.SEL, "props": {"background-color": "#112233", "padding": "8px", "margin-left": "3px"}, "op": "replace"},
            {"sheet": "AlwaysAppliedStyleSheet", "selector": self.SEL, "props": {}, "op": "remove", "remove": ["color", "align-items"]},
            {"sheet": "AlwaysAppliedStyleSheet", "selector": "SIGradient.pitch > .inner", "props": {"padding": "1px"}}]   # a plain append, same selector
        spec = project.to_spec(p)
        self.assertEqual(len(spec["edit_rules_by_sheet"]["AlwaysAppliedStyleSheet"]), 2); self.assertEqual(len(spec["append_rules_by_sheet"]["AlwaysAppliedStyleSheet"]), 1)
        v, b, a = sheet(), sheet(), acc()
        self.assertTrue(patcher.patch_sheet(b, spec, a))
        self.assertEqual(len(b["m_Rules"]), len(v["m_Rules"]) + 1)                       # nothing added except the append
        names = [tp_name for tp_name in (__import__("skin_editor.uss", fromlist=["x"]).prop_name(x) for x in b["m_Rules"][1]["m_Properties"])]
        self.assertEqual(names, ["background-color", "padding", "--start-colour", "--end-colour", "margin-left"])
        self.assertEqual(len(b["m_Rules"][2]["m_Properties"]), 1)                        # the append was not edited
        self.assertEqual([(e["op"], e["rules_hit"], e["declarations"]) for e in a["edits"]], [("replace", 1, 3), ("remove", 1, 2)])
        self.assertEqual(a["totals"]["edited"], 5)
        es = spec["edit_rules_by_sheet"]["AlwaysAppliedStyleSheet"]
        self.assertEqual(verify_static.check_edits(es, v["m_Rules"], b["m_Rules"]), [])
        # the gate notices a wrong result and a selector that matches nothing
        b["m_Rules"][1]["m_Properties"].pop(0)
        self.assertTrue(verify_static.check_edits(es, v["m_Rules"], b["m_Rules"]))
        miss = {"op": "remove", "selector": ".nope", "remove": []}
        self.assertIn("matches no rule", verify_static.check_edit(miss, v["m_Rules"], b["m_Rules"])[0])
        # whole-rule remove empties the rule but keeps it
        t = sheet(); a2 = acc()
        patcher.patch_sheet(t, {"tokens": {}, "literal_map": {}, "skip_sheets": [], "append_rules_by_sheet": {},
                                "edit_rules_by_sheet": {"AlwaysAppliedStyleSheet": [{"op": "remove", "selector": self.SEL, "remove": []}]}}, a2)
        self.assertEqual((len(t["m_Rules"]), t["m_Rules"][1]["m_Properties"]), (2, []))

    def test_new_sheet_is_listed_and_survives_a_model_save(self):
        import tempfile
        from skin_editor import project
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            ws = config.Workspace(Path(tmp) / "ws"); projfmt.write(ws, project.new("ns"))
            self.assertEqual(projfmt.create_sheet(ws, "ns", "SIStyles"), "styles/SIStyles.uss")
            self.assertEqual(projfmt.read(ws, "ns")["scoped_rules"], [])                      # compiles, no "not in mapping" problem
            project.save(ws, projfmt.read(ws, "ns"))
            self.assertTrue((projfmt.folder(ws, "ns") / "styles" / "SIStyles.uss").is_file())
            with self.assertRaises(ValueError): projfmt.create_sheet(ws, "ns", "SIStyles")
            with self.assertRaises(ValueError): projfmt.create_sheet(ws, "ns", "bad name")
            projfmt.write_file(ws, "ns", "styles/SIStyles.uss", "/* replace: .a */\n.a { padding: 2px; }\n")
            self.assertEqual(projfmt.read(ws, "ns")["scoped_rules"][0]["op"], "replace")

    def test_diagnostics_flag_an_edit_that_matches_no_game_rule(self):
        from tests.test_core import index as core_index
        text = "/* replace: .ghost */\n.ghost { padding: 1px; }\n/* replace: SIGradient.pitch > .inner */\nSIGradient.pitch > .inner { padding: 1px; }\n"
        d = [x for x in ussdiag.check(text, core_index(), "AlwaysAppliedStyleSheet") if x["code"] == "no-game-rule"]
        self.assertEqual([x["line"] for x in d], [2])
        self.assertEqual([x for x in ussdiag.check(text, core_index()) if x["code"] == "no-game-rule"], [])

    def test_plan_and_native_target(self):
        import tempfile
        from skin_editor import native, plan, project
        from tests.test_core import sheet, index as core_index
        p = project.new("x")
        p["options"]["output"] = "bundles"
        p["scoped_rules"] = [{"sheet": "AlwaysAppliedStyleSheet", "selector": self.SEL, "props": {"padding": "8px"}, "op": "replace"},
                             {"sheet": "AlwaysAppliedStyleSheet", "selector": ".ghost", "props": {}, "op": "remove", "remove": ["color"]},
                             {"sheet": "AlwaysAppliedStyleSheet", "selector": ".plain", "props": {"color": "#112233"}}]
        pl = plan.plan(None, p, core_index(), None, "bundles")
        kinds = {o["op"]: o for o in pl["operations"]}
        self.assertEqual(kinds["ReplaceRule"]["detail"][0]["rules_hit"], 1); self.assertEqual(kinds["RemoveDeclaration"]["detail"][0]["rules_hit"], 0)
        self.assertEqual(kinds["AppendRule"]["detail"], [{"sheet": "AlwaysAppliedStyleSheet", "rules": 1}])
        self.assertTrue(any("matches no rule" in w for w in pl["warnings"]))
        pn = plan.plan(None, p, core_index(), None, "native")
        self.assertTrue(any(d["item"].startswith("remove: .ghost") for d in pn["dropped"]))
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            ws = config.Workspace(Path(tmp) / "ws")
            rep = native.export(ws, p, core_index(), None, Path(tmp), "out")
            self.assertTrue(any(s.startswith("remove: .ghost") for s in rep["skipped"]))
            self.assertIn(".plain", (Path(rep["folder"]) / "rules.uss").read_text()); self.assertIn("padding", (Path(rep["folder"]) / "rules.uss").read_text())


class AssetConflicts(unittest.TestCase):
    def png(self, w, h):
        import io
        from PIL import Image
        b = io.BytesIO(); Image.new("RGB", (w, h), (10, 20, 30)).save(b, "PNG"); return b.getvalue()

    def test_report(self):
        import tempfile
        from skin_editor import assetcheck, images, project
        B = "ui-backgrounds_assets_.bundle"
        cat = [{"bundle": B, "path_id": "1", "name": "wall", "kind": "texture", "w": 1920, "h": 1080, "format_id": 29, "group": "wallpaper"},
               {"bundle": B, "path_id": "2", "name": "wall2", "kind": "texture", "w": 100, "h": 100, "format_id": 4, "group": "wallpaper"}]
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            ws = config.Workspace(Path(tmp) / "ws"); p = project.new("ac"); p["options"]["output"] = "native"; projfmt.write(ws, p)
            d = projfmt.folder(ws, "ac") / "images"
            (d / "a.png").write_bytes(self.png(400, 400)); (d / "b.png").write_bytes(self.png(1920, 1080))
            sw = lambda pid, src, **k: dict({"bundle": B, "path_id": pid, "name": "wall" if pid == "1" else "n" + pid, "kind": "texture", "source": src}, **k)
            p["image_swaps"] = [sw("1", "a.png", where=["main-screens"]), sw("2", "b.png", where=["main-screens"]), sw("9", "b.png"), sw("3", "gone.png")]
            codes = lambda rows: sorted(r["code"] for r in rows)
            rows = assetcheck.conflicts(ws, p, cat, {})
            self.assertEqual(codes(rows), sorted(["aspect", "aspect", "crunch", "same-place", "same-place", "shared-source", "slot-gone", "small", "source-missing"]))
            self.assertEqual(rows[0]["severity"], "error"); self.assertEqual({r["code"] for r in rows if r["severity"] == "error"}, {"slot-gone", "source-missing"})
            self.assertEqual([r["code"] for r in assetcheck.conflicts(ws, dict(p, image_swaps=[]), cat, {})], [])
            # an icon no USS class draws is only a problem for the native target
            ico = {"bundle": images.ICONS % "2x", "path_id": "5", "name": "star", "kind": "icon", "source": "a.png"}
            q = dict(p, image_swaps=[ico])
            self.assertEqual(codes(assetcheck.conflicts(ws, q, None, {})), ["no-class"]); self.assertEqual(assetcheck.conflicts(ws, q, None, {}, "bundles"), [])


class ImagesCommit(unittest.TestCase):
    def engine(self, tmp):
        from skin_editor import project
        from skin_editor.engine import Engine
        e = Engine.__new__(Engine); e.ws = config.Workspace(Path(tmp) / "ws"); e.info = None
        p = project.new("c"); p["options"]["output"] = "native"
        p["image_swaps"] = [{"bundle": "ui-backgrounds_assets_.bundle", "path_id": "7", "name": "wall", "kind": "texture", "source": "w.png", "fit": "cover"}]
        projfmt.write(e.ws, p); (projfmt.folder(e.ws, "c") / "images" / "w.png").write_bytes(b"x")
        return e

    def test_commit_changes_fit_and_where_in_one_write_and_delegates_a_file(self):
        import tempfile
        from skin_editor import project
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            e = self.engine(tmp)
            slot = {"project": "c", "bundle": "ui-backgrounds_assets_.bundle", "path_id": "7", "kind": "texture", "name": "wall"}
            r = e.images_commit({}, dict(slot, fit="contain", where=["loading", "main-screens"]))
            sw = r["project"]["image_swaps"][0]
            self.assertEqual((sw["fit"], sw["where"], sw["source"]), ("contain", ["loading", "main-screens"], "w.png"))
            with self.assertRaises(ValueError): e.images_commit({}, dict(slot, path_id="8", fit="cover"))            # nothing stored for that slot
            with self.assertRaises(ValueError): e.images_commit({}, dict(slot, path="C:/does/not/exist.png"))
            seen = {}
            e.images_swap = lambda q, b, where=None: seen.update(q=q, b=b, where=where) or {"project": {}, "notes": []}
            f = Path(tmp) / "n.png"; f.write_bytes(b"data")
            e.images_commit({}, dict(slot, path=str(f), fit="stretch", where=["loading"]))
            self.assertEqual((seen["b"], seen["where"], seen["q"]["fit"]), (b"data", ["loading"], "stretch"))
            e.images_commit({}, dict(slot, path=str(f)))
            self.assertIsNone(seen["where"])                                                                          # not staged: the slot keeps its places

    def test_preview_of_a_local_file(self):
        import io, tempfile
        from PIL import Image
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            e = self.engine(tmp)
            f = Path(tmp) / "big.png"; Image.new("RGB", (1200, 800), (1, 2, 3)).save(f)
            data, ctype = e.images_preview_file({}, {"path": str(f)})
            self.assertEqual(ctype, "image/png"); self.assertLessEqual(Image.open(io.BytesIO(data)).size[0], 360)
            with self.assertRaises(ValueError): e.images_preview_file({}, {"path": str(Path(tmp) / "nope.png")})
