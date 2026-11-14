import copy, json, logging, os, plistlib, re, shlex, shutil, struct, subprocess, sys, tempfile, threading, time, unittest, urllib.request, urllib.error
from pathlib import Path
from unittest import mock

from skin_editor import (colour, uss, patcher, project, index_styles, install, config, bundles, detect, specificity,
                         verify_static, layout, launcher, server)
from skin_editor import token_patch as tp
from skin_editor.presets import crimson


def H(t, i): return {"m_ValueType": t, "valueIndex": i}
def P(name, vals):
    c = name.startswith("--")
    return {"m_Id": -1 if c else tp.PROP_TABLE[name], "m_CustomName": name if c else "", "m_Line": 1, "m_Values": vals}
def C(spec, sels, i=0):
    return {"m_Specificity": spec, "ruleIndex": i, "m_Selectors": [
        {"m_Parts": [{"m_Type": t, "m_Value": v} for t, v in parts], "m_PreviousRelationship": rel} for parts, rel in sels]}


def sheet(name="AlwaysAppliedStyleSheet", nested=True):
    t = {"m_Name": name, "floats": [1.0], "dimensions": [{"value": 4.0, "unit": 1}],
         "colors": [{"r": 24/255, "g": 139/255, "b": 120/255, "a": 1.0}, {"r": 218/255, "g": 0, "b": 55/255, "a": 0.5},
                    {"r": 1, "g": 1, "b": 1, "a": 1}],
         "strings": ["--base", "center"], "assets": [], "m_Rules": []}
    rules = [
        ([P("--base", [H(4, 0)]), P("--alias", [H(10, 1), H(2, 0), H(8, 0)]), P("--start-colour", [H(4, 2)])],
         C(11, [([(4, "root")], 0)], 0)),
        ([P("background-color", [H(4, 1)]), P("color", [H(10, 1), H(2, 0), H(8, 0)]), P("padding", [H(3, 0)]),
          P("align-items", [H(7, 1)]), P("--start-colour", [H(4, 0)]), P("--end-colour", [H(4, 2)])],
         C(22, [([(2, "SIGradient"), (3, "pitch")], 0), ([(3, "inner")], 1)], 1)),
    ]
    if not nested:
        t["m_ComplexSelectors"] = []
    for props, cs in rules:
        r = {"m_Properties": props, "line": 1}
        if nested: r["m_ComplexSelectors"] = [cs]
        else: t["m_ComplexSelectors"].append(cs)
        t["m_Rules"].append(r)
    return t


def acc(): return patcher.new_acc()
def f32(tree):
    """What the serializer does to the colour table: every component becomes a 32-bit float."""
    for c in tree["colors"]:
        for k in "rgba": c[k] = struct.unpack("<f", struct.pack("<f", c[k]))[0]
    return tree
def index(*sheets): return index_styles.StyleIndex([index_styles.sheet_entry("b", s) for s in (sheets or (sheet(),))])


class Uss(unittest.TestCase):
    def test_decode(self):
        for nested in (True, False):
            e = index_styles.sheet_entry("b", sheet(nested=nested))
            self.assertEqual(e["rules"][0]["s"], [":root"]); self.assertTrue(e["rules"][0]["t"])
            self.assertEqual(e["rules"][1]["s"], ["SIGradient.pitch > .inner"])
            p = {a: b for a, b, _ in e["rules"][1]["p"]}
            self.assertEqual(p["background-color"], "#DA003780"); self.assertEqual(p["color"], "var(--base)")
            self.assertEqual(p["padding"], "4px"); self.assertEqual(p["align-items"], "center")

    def test_decoder_reads_what_token_patch_writes(self):
        t = sheet(); sp = tp.SheetPatcher(t, verify_static.EMPTY)
        for v in ["#A40029", "#A4002980", "var(--x)", "12px", "50%", "0.88 0.88", "none", "center", "auto 4px"]:
            project.check_value(v)
            self.assertEqual(uss.value_text(t, sp._encode(v))[0], v)
        self.assertEqual(sp._encode("center")[0]["m_ValueType"], 7); self.assertEqual(sp._encode("none"), [H(1, 6)])
        for bad in ["12em", "90deg", "var(--x, red)", "url(x)", "", "#12", "1.2.3"]:
            with self.assertRaises(ValueError): project.check_value(bad)


class Patch(unittest.TestCase):
    def proj(self):
        p = project.new("x")
        p["token_overrides"] = [{"token": "--base", "value": "#A40029"}, {"token": "--nope", "value": "#000000"},
                                {"token": "--alias", "value": "#111111"}]
        p["reverts"] = ["--alias"]
        p["literal_swaps"] = [{"from": "#DA0037", "to": "#6C001C"}]
        p["scoped_rules"] = [{"sheet": "AlwaysAppliedStyleSheet", "selector": "SIGradient.pitch > .inner, #a .b:hover",
                              "props": {"background-color": "#6C001C", "display": "none", "color": "#FFFFFF"}, "why": "t"}]
        p["rename_classes"] = {"pitch": "skin-pitch"}
        p["options"]["flatten_gradients"] = True
        return project.migrate(dict(p, schema=1))

    def test_apply_gate_contrast(self):
        t = sheet(); van = sheet(); ncol = len(t["colors"])
        spec = project.to_spec(project.validate(self.proj()))
        log = specificity.raise_spec(spec, index())
        sel = spec["append_rules_by_sheet"]["AlwaysAppliedStyleSheet"][0]["selector"]
        self.assertEqual(sel, "SIGradient.pitch > .inner, #a .b:hover")   # competitor carries a renamed (dead) class
        self.assertEqual(log[0]["excluded_state_or_dead"], 1)
        a = acc(); self.assertTrue(patcher.patch_sheet(t, spec, a))
        e = index_styles.sheet_entry("b", t)
        root = {x: y for x, y, _ in e["rules"][0]["p"]}
        self.assertEqual(root["--base"], "#A40029"); self.assertEqual(root["--alias"], "var(--base)")
        r1 = {x: y for x, y, _ in e["rules"][1]["p"]}
        self.assertEqual(e["rules"][1]["s"], ["SIGradient.skin-pitch > .inner"])
        self.assertEqual(r1["background-color"], "#6C001C80"); self.assertEqual(r1["--end-colour"], r1["--start-colour"])
        self.assertEqual(e["rules"][2]["s"], ["SIGradient.pitch > .inner", "#a .b:hover"])
        self.assertEqual([c["m_Specificity"] for c in t["m_Rules"][2]["m_ComplexSelectors"]], [22, 121])
        self.assertEqual(a["tokens_found"], {"--base"}); self.assertEqual(a["literal_hits"][0]["alpha"], 0.5)
        self.assertEqual(a["totals"], {"tokens": 1, "literals": 1, "gradients": 1, "renames": 1, "appended": 1, "edited": 0, "literals_rgba": 0})
        self.assertEqual(a["literal_hits"][0]["mode"], "rgb-keep-alpha")
        self.assertEqual(t["colors"][:ncol], van["colors"])
        files = {"f": {"changed": True}}
        with mock.patch.object(bundles, "inspect", lambda p: ({"MonoBehaviour": 1}, {"AlwaysAppliedStyleSheet": van if "van" in str(p) else t}, [])):
            g, built = verify_static.gate(spec, Path("van"), Path("out"), files)
            self.assertEqual((g["fail"], g["appended_rules_checked"], g["untouched_bundles_checked"]), ([], 1, "skipped"))      # no touched set given: the object check is skipped
            t["m_Rules"][2]["m_ComplexSelectors"][0]["m_Specificity"] = 5
            self.assertEqual(len(verify_static.gate(spec, Path("van"), Path("out"), files)[0]["fail"]), 1)
        c = verify_static.contrast(spec, built, [{"fg": "--base", "bg": "#101010"}, {"fg": "--missing", "bg": "#000000"}])
        st = {r["src"]: r for r in c["rows"]}
        self.assertEqual(c["pairs"], 3); self.assertEqual(st["contrast_pairs"]["status"] in ("FAIL", "UNRESOLVED"), True)
        self.assertEqual(st[sel[:80]]["status"], "PASS"); self.assertGreater(st[sel[:80]]["ratio"], 10)
        self.assertEqual((st[sel[:80]]["bg_source"], st[sel[:80]]["composited"]), ("rule background-color", False))

    def test_specificity_raise(self):
        spec = {"append_rules_by_sheet": {"AlwaysAppliedStyleSheet": [
            {"selector": ".inner", "props": {"background-color": "#000000"}},
            {"selector": ".inner", "props": {"opacity": "0"}}, {"selector": ":root", "props": {"--x": "1"}}]}}
        log = specificity.raise_spec(spec, index())
        r = spec["append_rules_by_sheet"]["AlwaysAppliedStyleSheet"]
        self.assertEqual(r[0]["selector"], ".inner.inner.inner"); self.assertEqual(r[1]["selector"], ".inner")
        self.assertEqual((log[0]["before"], log[0]["after"]), (11, 31)); self.assertGreater(log[0]["after"], 22)

    def test_skip_and_noop(self):
        t = sheet(); before = copy.deepcopy(t)
        spec = project.to_spec(project.new("x"))
        self.assertFalse(patcher.patch_sheet(t, spec, acc())); self.assertEqual(t, before)
        spec = dict(spec, tokens={"--base": "#000000"}, skip_sheets=["AlwaysAppliedStyleSheet"],
                    append_rules_by_sheet={"AlwaysAppliedStyleSheet": [{"selector": ".a", "props": {"opacity": "0"}}]})
        self.assertFalse(patcher.patch_sheet(t, spec, acc())); self.assertEqual(t, before)

    def test_validate(self):
        for mut in [{"bogus": 1}, {"name": "../x"}, {"token_overrides": [{"token": "base", "value": "#000000"}]},
                    {"token_overrides": [{"token": "--b", "value": "12em"}]},
                    {"literal_swaps": [{"from": "#12345678", "to": "#000000"}]},
                    {"scoped_rules": [{"sheet": "s", "selector": ".a", "props": {"text-transform": "none"}}]},
                    {"scoped_rules": [{"sheet": "s", "selector": ".a{", "props": {"opacity": "0"}}]},
                    {"rename_classes": {"a b": "c"}}]:
            with self.assertRaises(ValueError): project.validate(dict(project.new("x"), **mut))


class Index(unittest.TestCase):
    def test_index(self):
        ix = index(sheet(), sheet("FMColours"))
        self.assertEqual(ix.chain("--alias"), (["--alias", "--base"], {"rgb": "#188B78", "a": 1.0}))
        row = ix.token("--base")
        self.assertEqual(row["reach"], 2); self.assertEqual(row["sheets"], 2); self.assertFalse(row["conflict"])
        find = lambda q: [r["name"] for r in ix.tokens(q)["rows"]]                    # search by hex code
        self.assertEqual(find("188B78"), ["--alias", "--base"]); self.assertEqual(find("#188b78"), ["--alias", "--base"])
        self.assertEqual(find("188B78FF"), ["--alias", "--base"]); self.assertEqual(find("ffffff"), ["--start-colour"])
        self.assertEqual(find("123456"), []); self.assertEqual(find("alias"), ["--alias"])
        hits = ix.literal("#da0037", 0.5)
        self.assertEqual(len(hits["exact"]), 2); self.assertEqual(hits["exact"][0]["selectors"], ["SIGradient.pitch > .inner"])
        self.assertEqual(ix.literal("#DA0037", 1.0)["exact"], []); self.assertEqual(len(ix.literal("#DA0037", 1.0)["rgb_all"]), 2)

    def test_reach(self):
        trees = [["b:T", [["UXML", "", [], -1], ["SIGradient", "g", ["pitch"], 0], ["VisualElement", "", ["x"], 1],
                          ["VisualElement", "", ["inner"], 2]]]]
        r = layout.reach([{"selector": "SIGradient.pitch .inner.inner, SIGradient.pitch > .inner, #g:hover > .x, .nope"},
                          {"selector": ":root"}], trees)
        self.assertEqual([x["hits"] for x in r["rows"]], [1, 0, 1, 0]); self.assertEqual(r["rows"][3]["missing"], [".nope"])

    def test_crimson_preset(self):
        t = sheet(); sp = tp.SheetPatcher(t, verify_static.EMPTY)
        for i, n in enumerate(["--global-background", "--colours-tactics-base-20", "--colours-base-red-strong"]):
            t["m_Rules"][0]["m_Properties"].append(P(n, sp._encode("#16181D")))
        ix = index(t)
        p = project.validate(crimson.project(ix, "cr"))
        self.assertEqual({e["token"] for e in p["token_overrides"]},
                         {"--global-background", "--colours-tactics-base-20", "--colours-base-red-strong"})
        self.assertEqual(p["token_overrides"][0]["vanilla"], "#16181D")
        self.assertGreater(len(p["scoped_rules"]), 60); self.assertGreater(len(p["literal_swaps"]), 60)
        spec = project.to_spec(p); specificity.raise_spec(spec, ix)
        a = acc(); built = copy.deepcopy(t); patcher.patch_sheet(built, spec, a)
        with mock.patch.object(bundles, "inspect", lambda q: ({"MonoBehaviour": 1}, {"AlwaysAppliedStyleSheet": t if "van" in str(q) else built}, [])):
            g, bs = verify_static.gate(spec, Path("van"), Path("out"), {"f": {"changed": True}})
        self.assertEqual(g["fail"], []); self.assertEqual(g["appended_rules_checked"], len(p["scoped_rules"]))
        c = verify_static.contrast(spec, bs, p["contrast_pairs"])
        self.assertGreater(c["pairs"], 40)
        self.assertFalse([r for r in c["rows"] if r["status"] == "FAIL" and "--cr-" in str(r["fg"]) and "--cr-" in str(r["bg"])])


class Rgba(unittest.TestCase):
    def test_conversions_at_the_boundaries(self):
        for unit, byte, hx in [(0, 0, "00"), (1, 255, "FF"), (1 / 255, 1, "01"), (0.5, 128, "80"), (254 / 255, 254, "FE")]:
            self.assertEqual(colour.unit_to_byte(unit), byte); self.assertEqual(colour.byte_to_hex(byte), hx)
            self.assertEqual(colour.hex_to_byte(hx), byte)
        self.assertEqual([colour.unit_to_byte(colour.byte_to_unit(b)) for b in range(256)], list(range(256)))
        self.assertEqual((colour.unit_to_byte(-1), colour.unit_to_byte(2)), (0, 255))
        for bad in (-1, 256): self.assertRaises(ValueError, colour.byte_to_unit, bad)
        self.assertRaises(ValueError, colour.hex_to_byte, "G0")
        self.assertEqual(colour.parse("#DA003780"), (218, 0, 55, 128 / 255)); self.assertEqual(colour.parse("#da0037"), (218, 0, 55, 1.0))
        self.assertEqual(colour.parse("rgba(218, 0, 55, 0.652)"), (218, 0, 55, 0.652)); self.assertIsNone(colour.parse("var(--x)"))
        self.assertRaises(ValueError, colour.parse, "rgba(300,0,0,1)"); self.assertRaises(ValueError, colour.parse, "rgba(0,0,0,1.5)")
        c = (218, 0, 55, 0.652)
        self.assertEqual(colour.to_obj(c), {"rgb": "#DA0037", "a": 0.652}); self.assertEqual(colour.from_obj(colour.to_obj(c)), c)
        self.assertEqual((colour.hex8(c), colour.text(c), colour.text((1, 2, 3, 1.0))), ("#DA0037A6", "#DA0037A6", "#010203"))
        self.assertEqual(colour.parse(colour.patch_value(c)), c)                      # the patcher string keeps the float
        self.assertEqual(tp.parse_token_value(colour.patch_value(c))[1][3], 0.652)
        self.assertEqual(colour.patch_value((1, 2, 3, 1.0)), "#010203")
        self.assertEqual(colour.composite((255, 255, 255, 0.5), (0, 0, 0)), (128, 128, 128))
        self.assertEqual(colour.composite((10, 20, 30, 0.0), (1, 2, 3)), (1, 2, 3)); self.assertEqual(colour.composite((10, 20, 30, 1.0), (1, 2, 3)), (10, 20, 30))
        for bad in ({"rgb": "#12", "a": 1}, {"rgb": "#000000", "a": 1.2}, {"rgb": "#000000"}, {"rgb": "#000000", "a": True}):
            self.assertRaises(ValueError, colour.from_obj, bad)

    def test_migration(self):
        old = {"schema": 1, "name": "m", "options": {"flatten_gradients": True, "skip_sheets": ["X"]},
               "token_overrides": [{"token": "--a", "value": "#A40029", "vanilla": "#188B78", "note": "n"},
                                   {"token": "--b", "value": "#A4002980"}, {"token": "--c", "value": "rgba(1, 2, 3, 0.652)"},
                                   {"token": "--d", "value": "var(--a)"}, {"token": "--e", "value": "4px"}],
               "literal_swaps": [{"from": "#DA0037", "to": "#6C001C", "scope": "all_sheets", "hits_expected": 14}],
               "scoped_rules": [{"sheet": "S", "selector": ".a", "props": {"background-color": "#6C001C", "display": "none",
                                                                             "scale": "0.88 0.88"}, "why": "w"}],
               "contrast_pairs": [{"fg": "--a", "bg": "#101010", "min": 3}], "reverts": ["--e"]}
        p = project.validate(project.migrate(old))
        v = [e["value"] for e in p["token_overrides"]]
        self.assertEqual(v, [{"rgb": "#A40029", "a": 1.0}, {"rgb": "#A40029", "a": 128 / 255}, {"rgb": "#010203", "a": 0.652},
                             "var(--a)", "4px"])
        self.assertEqual(p["literal_swaps"][0], {"from": {"rgb": "#DA0037", "a": 1.0}, "to": {"rgb": "#6C001C", "a": 1.0},
                                                 "scope": "all_sheets", "hits_expected": 14, "mode": "rgb-keep-alpha"})
        self.assertEqual(p["scoped_rules"][0]["props"], {"background-color": {"rgb": "#6C001C", "a": 1.0}, "display": "none", "scale": "0.88 0.88"})
        self.assertEqual((p["schema"], p["token_overrides"][0]["note"], p["token_overrides"][0]["vanilla"], p["reverts"]), (2, "n", "#188B78", ["--e"]))
        self.assertEqual(p["contrast_pairs"][0], {"fg": "--a", "bg": {"rgb": "#101010", "a": 1.0}, "min": 3})
        self.assertEqual(p["options"]["contrast_backdrop"], {"rgb": "#171717", "a": 1.0})
        self.assertEqual(project.migrate(p), p)                                        # idempotent
        with tempfile.TemporaryDirectory() as tmp:
            ws = config.Workspace(tmp)
            project.path(ws, "m").write_text(json.dumps(old))
            first = project.save(ws, project.load(ws, "m")); again = project.save(ws, project.load(ws, "m"))
            self.assertEqual(first, p); self.assertEqual(again, p)                     # no loss on load/save round trips
            self.assertEqual(json.loads(project.path(ws, "m").read_text()), p)
        spec = project.to_spec(p)
        self.assertEqual(spec["tokens"]["--c"], "rgba(1, 2, 3, 0.652)"); self.assertNotIn("--e", spec["tokens"])
        self.assertEqual(spec["literal_map"], {"#DA0037": "#6C001C"}); self.assertEqual(spec["rgba_swaps"], [])
        with self.assertRaises(ValueError): project.validate(dict(p, literal_swaps=[{"from": p["literal_swaps"][0]["from"], "to": p["literal_swaps"][0]["to"]}]))
        with self.assertRaises(ValueError): project.validate(old)                      # schema 1 must be migrated first

    def test_alpha_round_trip_through_sheetpatcher(self):
        p = project.new("a")
        p["token_overrides"] = [{"token": "--base", "value": {"rgb": "#A40029", "a": 0.5}}]
        p["scoped_rules"] = [{"sheet": "AlwaysAppliedStyleSheet", "selector": ".x", "props": {"background-color": {"rgb": "#102030", "a": 0.652}}}]
        p["literal_swaps"] = [{"from": {"rgb": "#DA0037", "a": 0.5}, "to": {"rgb": "#010203", "a": 0.652}, "mode": "rgba"},
                              {"from": {"rgb": "#FFFFFF", "a": 1.0}, "to": {"rgb": "#EDEDED", "a": 1.0}, "mode": "rgb-keep-alpha"}]
        t = sheet(); a = acc()
        self.assertTrue(patcher.patch_sheet(t, project.to_spec(project.validate(p)), a))
        self.assertEqual({k: t["colors"][-1][k] for k in "a"}, {"a": 0.652})           # written as a 0..1 float, not a byte
        e = index_styles.sheet_entry("b", f32(t))                                       # serializer precision, then the app's decoder
        got = {(r["s"][0], name): cols for r in e["rules"] for name, _, cols in r["p"] if cols}
        self.assertEqual(got[(":root", "--base")], [["#A40029", 0.5]])                  # 0.5 is exact in float32
        for key, rgb in (((".x", "background-color"), "#102030"), (("SIGradient.pitch > .inner", "background-color"), "#010203")):
            self.assertEqual(got[key][0][0], rgb); self.assertAlmostEqual(got[key][0][1], 0.652, delta=3e-8)
            self.assertEqual(got[key][0][1], struct.unpack("<f", struct.pack("<f", 0.652))[0])
        self.assertEqual(got[("SIGradient.pitch > .inner", "--end-colour")], [["#EDEDED", 1.0]])
        rows = patcher.swap_report(p, a["literal_hits"])
        self.assertEqual([(r["mode"], r["hits"]) for r in rows], [("rgba", 1), ("rgb-keep-alpha", 2)])
        self.assertEqual(a["totals"]["literals_rgba"], 1)
        # an rgba swap must not touch the same RGB at another alpha; rgb-keep-alpha keeps the 0.5
        t2 = sheet(); p["literal_swaps"] = [{"from": {"rgb": "#DA0037", "a": 1.0}, "to": {"rgb": "#010203", "a": 0.2}, "mode": "rgba"}]
        a2 = acc(); patcher.patch_sheet(t2, project.to_spec(p), a2); self.assertEqual(a2["totals"]["literals_rgba"], 0)
        t3 = sheet(); p["literal_swaps"] = [{"from": {"rgb": "#DA0037", "a": 1.0}, "to": {"rgb": "#010203", "a": 1.0}, "mode": "rgb-keep-alpha"}]
        patcher.patch_sheet(t3, project.to_spec(p), acc())
        self.assertEqual(index_styles.sheet_entry("b", t3)["rules"][1]["p"][0][2], [["#010203", 0.5]])

    def test_percent_alpha_only_at_the_ingestion_boundaries(self):
        bad, good = {"rgb": "#AF78FF", "a": 100.0}, {"rgb": "#AF78FF", "a": 1.0}
        colour.LEGACY.clear(); colour._seen.clear()
        # boundary 1: schema-1 project migration
        old = {"schema": 1, "name": "m", "token_overrides": [{"token": "--a", "value": dict(bad)}, {"token": "--b", "value": "rgba(1, 2, 3, 50)"}],
               "literal_swaps": [{"from": dict(bad), "to": "#010203"}],
               "scoped_rules": [{"sheet": "S", "selector": ".a", "props": {"color": dict(bad)}}]}
        with self.assertLogs("skin_editor.colour", "WARNING") as lg:
            p = project.validate(project.migrate(old))
        self.assertEqual(p["token_overrides"][0]["value"], good); self.assertEqual(p["scoped_rules"][0]["props"]["color"], good)
        self.assertEqual(p["literal_swaps"][0]["from"], good); self.assertEqual(p["token_overrides"][1]["value"], {"rgb": "#010203", "a": 0.5})
        self.assertIn("100.0", lg.output[0]); self.assertIn(colour.B_SCHEMA1, lg.output[0])
        # boundary 2: crimson preset conversion (same converter, its own label)
        with self.assertLogs("skin_editor.colour", "WARNING") as lg:
            q = project.migrate({"schema": 1, "name": "c", "token_overrides": [{"token": "--a", "value": dict(bad)}]}, colour.B_PRESET)
        self.assertEqual(q["token_overrides"][0]["value"], good); self.assertIn(colour.B_PRESET, lg.output[0])
        self.assertEqual({x["boundary"] for x in colour.LEGACY}, {colour.B_SCHEMA1, colour.B_PRESET})
        self.assertEqual({(x["original"], x["stored"]) for x in colour.LEGACY}, {(100.0, 1.0), (50.0, 0.5)})
        # bundle data is not a percent boundary any more
        self.assertRaises(ValueError, colour.legacy_alpha, 100.0, "literal import from the index (bundle colour decode)")
        # every non-boundary path refuses the same dict
        self.assertRaises(ValueError, colour.from_obj, bad); self.assertRaises(ValueError, colour.canonical, bad)
        self.assertRaises(ValueError, colour.coerce, bad); self.assertRaises(ValueError, colour.legacy_alpha, 100.0, "somewhere else")
        s2 = project.new("x"); s2["token_overrides"] = [{"token": "--a", "value": dict(bad)}]
        for fn in (project.migrate, project.validate, project.to_spec):
            self.assertRaises(ValueError, fn, s2)                                   # schema 2: strict, no normalisation
        self.assertRaises(ValueError, project.check_value, bad)
        with tempfile.TemporaryDirectory() as tmp:
            self.assertRaises(ValueError, project.save, config.Workspace(tmp), s2)
        self.assertRaises(ValueError, verify_static.contrast, {"append_rules_by_sheet": {}}, {}, [{"fg": bad, "bg": "#000000"}])
        # out of range in any other way still raises, at the boundaries too
        for a_ in (100.5, 250, -0.1, float("nan"), "100", True):
            self.assertRaises(ValueError, colour.legacy, {"rgb": "#AF78FF", "a": a_}, colour.B_SCHEMA1)

    def test_out_of_range_bundle_colours_are_failures_not_guesses(self):
        """Real-bundle findings 2026-11-11: #AF78FF with alpha 100.0, and .continue-button---carabao-cup
        -unity-background-image-tint-color #04A08C with alpha 124.0. No scale is applied until proven."""
        def bad_sheet():
            t = sheet()
            t["colors"] += [{"r": 175 / 255, "g": 120 / 255, "b": 1.0, "a": 100.0}, {"r": 4 / 255, "g": 160 / 255, "b": 140 / 255, "a": 124.0}]
            t["m_Rules"][1]["m_Properties"] += [P("border-color", [H(4, 3)]), P("-unity-background-image-tint-color", [H(4, 4)])]
            t["m_Rules"][0]["m_Properties"].append(P("--horizon", [H(4, 3)]))
            return t
        t = bad_sheet()
        self.assertRaises(colour.ColourDecodeError, colour.from_floats, t["colors"][3])
        self.assertRaises(colour.ColourDecodeError, colour.from_floats, {"r": 4.0, "g": 160.0, "b": 140.0, "a": 1.0})
        ix = index(t)                                                   # collects, does not stop at the first
        self.assertEqual([(f["sheet"], f["rule"], f["property"], f["raw"][3]) for f in ix.failures],
                         [("AlwaysAppliedStyleSheet", 0, "--horizon", 100.0), ("AlwaysAppliedStyleSheet", 1, "border-color", 100.0),
                          ("AlwaysAppliedStyleSheet", 1, "-unity-background-image-tint-color", 124.0)])
        self.assertEqual(ix.failures[2]["selector"], "SIGradient.pitch > .inner")
        # classes from the real-bundle table (diagnostics/README.md): byte-alpha candidates and hdr
        self.assertEqual([(f["class"], f["display"]) for f in ix.failures[1:]],
                         [("byte-alpha candidate", {"rgb": "#AF78FF", "a": 100 / 255}), ("byte-alpha candidate", {"rgb": "#04A08C", "a": 124 / 255})])
        for alpha, shown in ((100.0, 0.392), (124.0, 0.486), (243.0, 0.953), (255.0, 1.0)):
            cls, d = colour.classify_out_of_range([0.5, 0.5, 0.5, alpha])
            self.assertEqual((cls, round(d["a"], 3)), ("byte-alpha candidate", shown))
        self.assertEqual(colour.classify_out_of_range([4.62, 0.2, 0.1, 1.0]), ("hdr", None))
        self.assertEqual(colour.classify_out_of_range([4.62, 0.2, 0.1, 255.0]), ("hdr", None))
        for raw in ([0.5, 0.5, 0.5, 124.5], [0.5, 0.5, 0.5, 256.0], [0.5, 0.5, 0.5, -1.0], [-0.1, 0.5, 0.5, 1.0], [0.5, 0.5, 0.5, float("nan")]):
            self.assertEqual(colour.classify_out_of_range(raw)[0], "unclassified")
        h = sheet(); h["colors"].append({"r": 4.62, "g": 0.2, "b": 0.1, "a": 1.0})
        h["m_Rules"][1]["m_Properties"].append(P("--line-colour", [H(4, 3)]))
        qh = index(t, h).quarantine()
        self.assertEqual((qh["count"], qh["unique"], qh["classes"]), (4, 3, {"byte-alpha candidate": {"entries": 3, "unique": 2}, "hdr": {"entries": 1, "unique": 1}}))
        hp = project.new("h"); hp["literal_swaps"] = [{"from": {"rgb": "#FF331A", "a": 1.0}, "to": {"rgb": "#010203", "a": 1.0}, "mode": "rgb-keep-alpha"}]
        self.assertRaisesRegex(patcher.BuildRefused, "class: hdr", patcher.patch_sheet, h, project.to_spec(hp), acc())
        self.assertFalse([r for r in ix.literal_list() if r["rgb"] in ("#AF78FF", "#04A08C")])   # not offered as literals
        self.assertIsNone(ix.chain("--horizon")[1]); self.assertIn("?colour[3]", ix.value("--horizon"))
        before = copy.deepcopy(t["colors"])
        p = project.new("s")
        p["literal_swaps"] = [{"from": {"rgb": "#AF78FF", "a": 1.0}, "to": {"rgb": "#010203", "a": 0.25}, "mode": "rgba"},
                              {"from": {"rgb": "#DA0037", "a": 1.0}, "to": {"rgb": "#6C001C", "a": 1.0}, "mode": "rgb-keep-alpha"}]
        a = acc(); patcher.patch_sheet(t, project.to_spec(project.validate(p)), a)   # swaps elsewhere still build
        self.assertEqual((a["totals"]["literals_rgba"], a["totals"]["literals"]), (0, 1))
        self.assertEqual(t["colors"][:5], before)                       # undecoded entries untouched
        self.assertTrue(all(colour.in_range(c) for c in t["colors"][5:]))
        for rgb in ("#AF78FF", "#04A08C"):                              # a swap that would copy an undecoded alpha is refused
            p["literal_swaps"] = [{"from": {"rgb": rgb, "a": 1.0}, "to": {"rgb": "#010203", "a": 1.0}, "mode": "rgb-keep-alpha"}]
            t = bad_sheet()
            self.assertRaisesRegex(patcher.BuildRefused, "undecoded bundle colour", patcher.patch_sheet, t, project.to_spec(p), acc())
            self.assertEqual(t["colors"], before)
        van, built = bad_sheet(), bad_sheet(); built["colors"].append({"r": 0.1, "g": 0.2, "b": 0.3, "a": 124.0})
        with mock.patch.object(bundles, "inspect", lambda q: ({"MonoBehaviour": 1}, {"AlwaysAppliedStyleSheet": van if "van" in str(q) else built}, [])):
            g, _ = verify_static.gate(verify_static.EMPTY, Path("van"), Path("out"), {"f": {"changed": True}})
        self.assertEqual(len(g["fail"]), 1); self.assertIn("outside 0..1", g["fail"][0])   # gate blocks install
        verify_static.contrast({"append_rules_by_sheet": {}}, {"AlwaysAppliedStyleSheet": bad_sheet()}, [{"fg": "--horizon", "bg": "#000000"}])

    def test_index_keys_literals_on_full_rgba(self):
        t = sheet(); t["colors"].append({"r": 218 / 255, "g": 0, "b": 55 / 255, "a": 0.652})
        t["m_Rules"][1]["m_Properties"].append(P("border-color", [H(4, 3)]))
        ix = index(f32(t))
        rows = {(r["rgb"], round(r["a"], 3)): r for r in ix.literal_list()}
        self.assertEqual((rows[("#DA0037", 0.5)]["hits"], rows[("#DA0037", 0.652)]["hits"], rows[("#DA0037", 0.652)]["rgb_hits"]), (1, 1, 2))
        a = rows[("#DA0037", 0.652)]["a"]; self.assertNotEqual(a, 0.652)               # the decoded float32, kept in full
        self.assertEqual(len(ix.literal("#DA0037", a)["exact"]), 1)

    def test_contrast_composites_alpha(self):
        spec = {"append_rules_by_sheet": {"S": [
            {"selector": ".t", "props": {"color": "rgba(255, 255, 255, 0.5)", "background-color": "rgba(0, 0, 0, 0.5)"}},
            {"selector": ".u", "props": {"color": "#FFFFFF"}}, {"selector": ".v", "props": {"color": "#FFFFFF"}, "on": ["--base"]}]}}
        c = verify_static.contrast(spec, {"AlwaysAppliedStyleSheet": sheet()}, [{"fg": {"rgb": "#FFFFFF", "a": 0.25}, "bg": "--base"}],
                                   page=(0x20, 0x20, 0x20, 1.0))
        rows = {r["src"]: r for r in c["rows"]}
        t = rows[".t"]
        self.assertEqual((t["composited"], t["bg_source"], t["bg_painted"], t["fg_painted"]), (True, "rule background-color", "#101010", "#888888"))
        self.assertEqual(t["fg_rgba"], {"rgb": "#FFFFFF", "a": 0.5}); self.assertEqual(t["backdrop"], "#202020")
        self.assertEqual((rows[".u"]["bg_source"], rows[".u"]["composited"], rows[".u"]["bg_painted"]), ("default backdrop", False, "#202020"))
        self.assertEqual((rows[".v"]["bg_source"], rows[".v"]["bg_painted"]), ("rule on", "#188B78"))
        self.assertEqual((rows["contrast_pairs"]["composited"], c["composited"]), (True, 2))
        opaque = verify_static.contrast({"append_rules_by_sheet": {"S": [{"selector": ".t", "props": {"color": "#FFFFFF", "background-color": "#000000"}}]}}, {})
        self.assertGreater(opaque["rows"][0]["ratio"], t["ratio"])                      # treating .t as opaque would overstate it


class Diagnostic(unittest.TestCase):
    def test_analyse(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location("diag_colours", config.resource_root() / "tools" / "diag_colours.py")
        d = importlib.util.module_from_spec(spec); spec.loader.exec_module(d)
        t = sheet()
        t["colors"] += [{"r": 175 / 255, "g": 120 / 255, "b": 1.0, "a": 100.0}, {"r": 4 / 255, "g": 160 / 255, "b": 140 / 255, "a": 124.0}]
        t["m_Rules"][0]["m_Properties"].append(P("--colours-brand-foundation-horizon-base", [H(4, 3)]))
        t["m_Rules"].append({"m_Properties": [P("-unity-background-image-tint-color", [H(4, 4)]), P("color", [H(4, 9)])], "line": 1,
                             "m_ComplexSelectors": [C(11, [([(3, "continue-button---carabao-cup")], 0)], 2)]})
        raw = b"xx" + struct.pack("<4f", 4 / 255, 160 / 255, 140 / 255, 124.0)
        r = d.analyse([{"bundle": "b", "name": "AlwaysAppliedStyleSheet", "path_id": 1, "tree": t, "raw": raw}])
        self.assertEqual(r["entries"], {"total": 5, "any_out_of_range": 2, "alpha_only_out": 2, "rgb_out": 0,
                                        "out_and_referenced": 2, "out_and_unreferenced": 0})
        a = r["histogram"]["a"]
        self.assertEqual((a["le1"], a["1_100"], a["100_255"], a["max"], a["gt1_integer"], a["gt1_noninteger"]), (3, 1, 1, 124.0, 2, 0))
        self.assertEqual(r["histogram"]["r"]["le1"], 5)
        f = {x["property"]: x for x in r["failures"]}
        self.assertEqual(len(r["failures"]), 3)
        tint = f["-unity-background-image-tint-color"]
        self.assertEqual((tint["rule"], tint["selector"], tint["handles"], tint["raw"][3], tint["raw_bytes_found_in_object"], tint["raw_bytes_first_offset"]),
                         (2, ".continue-button---carabao-cup", [[4, 4]], 124.0, 1, 2))
        self.assertEqual((f["color"]["index"], f["color"]["raw"]), (9, None))            # handle outside the pool
        self.assertEqual(r["handles_by_value_type"]["4"]["index_out_of_pool"], 1)
        self.assertEqual(r["tint_property_handle_shapes"], [("4", 1)])
        self.assertEqual((r["af78ff_entries"][0]["raw"][3], r["af78ff_entries"][0]["reference_count"]), (100.0, 1))
        self.assertEqual(r["known_colour_tokens"][0]["rgb_matches"], True)
        self.assertEqual(len(r["carabao_rules"]), 2); self.assertEqual(r["continue_button_tint_siblings"][0]["raw"][3], 124.0)
        text = d.render(r, [], [])
        self.assertIn("124.0", text); self.assertIn("carabao", text)


class FakeBundles:
    """Bundles as JSON lists of sheets, to exercise build and install without Unity files."""
    @staticmethod
    def read_sheets(path): return json.loads(Path(path).read_text())
    @staticmethod
    def patch_bundle(src, out, fn, touched=None):
        sheets = json.loads(Path(src).read_text()); ch = [fn(t) for t in sheets]
        if touched is not None: touched.update(i for i, c in enumerate(ch) if c)       # the fake's path id is the list index
        if any(ch): (Path(out) / Path(src).name).write_text(json.dumps(sheets))
        return any(ch)
    @staticmethod
    def object_digests(path, want_trees=()):
        sheets = json.loads(Path(path).read_text())
        return ({i: ("tt", bundles._digest(t), "%s (path id %d)" % (t["m_Name"], i)) for i, t in enumerate(sheets)},
                {i: t for i, t in enumerate(sheets) if i in want_trees})
    @staticmethod
    def inspect(path):
        sheets = json.loads(Path(path).read_text())
        return {"MonoBehaviour": len(sheets)}, {t["m_Name"]: t for t in sheets}, []


def fake():
    return mock.patch.multiple(bundles, read_sheets=FakeBundles.read_sheets, patch_bundle=FakeBundles.patch_bundle,
                               inspect=FakeBundles.inspect, object_digests=FakeBundles.object_digests)


class UntouchedGate(unittest.TestCase):
    """The gate for objects the patcher did not change: they must equal vanilla, and the pools of changed sheets are append-only."""
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.v, self.b = Path(self.tmp.name) / "van", Path(self.tmp.name) / "out"; self.v.mkdir(); self.b.mkdir()
        self.van = [sheet("Changed"), sheet("Other")]
        (self.v / "f").write_text(json.dumps(self.van))
        self.built = copy.deepcopy(self.van); self.built[0]["colors"].append({"r": 0.1, "g": 0.2, "b": 0.3, "a": 1.0})     # an append: allowed

    def run_gate(self, touched=frozenset({0})):
        (self.b / "f").write_text(json.dumps(self.built))
        with fake():
            return verify_static.untouched_check("f", self.v / "f", self.b / "f", set(touched))

    def test_clean_build_passes(self):
        self.assertEqual(self.run_gate(), ([], []))

    def test_untouched_sheet_mutated_after_the_build_fails_and_is_named(self):
        self.built[1]["floats"][0] = 9.0
        fail, _ = self.run_gate()
        self.assertEqual(len(fail), 1); self.assertIn("Other (path id 1)", fail[0]); self.assertIn("/floats[0]", fail[0])
        self.built[1]["floats"][0] = 1.0; self.built[1]["m_Name"] = "Renamed"          # the first differing path is reported for any field
        self.assertIn("/m_Name", self.run_gate()[0][0])

    def test_vanilla_pool_entry_altered_in_a_changed_sheet_fails(self):
        self.built[0]["colors"][1]["a"] = 0.25                                           # an existing (e.g. quarantined) entry rewritten
        fail, _ = self.run_gate()
        self.assertEqual(len(fail), 1); self.assertIn("Changed (path id 0)", fail[0]); self.assertIn("'colors' entry 1", fail[0]); self.assertIn("append-only", fail[0])
        self.built[0]["colors"][1]["a"] = 0.5; self.built[0]["strings"].pop()             # a shrunk pool is also refused
        self.assertIn("shrank", self.run_gate()[0][0])

    def test_nan_in_vanilla_does_not_break_the_comparison(self):
        self.van[1]["floats"][0] = float("nan"); (self.v / "f").write_text(json.dumps(self.van)); self.built[1]["floats"][0] = float("nan")
        self.assertEqual(self.run_gate(), ([], []))

    def test_object_set_must_match_and_the_gate_blocks_install(self):
        self.built.pop()
        self.assertIn("object set differs", self.run_gate()[0][0])
        self.built = copy.deepcopy(self.van); self.built[1]["floats"][0] = 9.0; (self.b / "f").write_text(json.dumps(self.built))
        with fake():
            g, _ = verify_static.gate(verify_static.EMPTY, self.v, self.b, {"f": {"changed": True, "vanilla_sha256": "x", "sha256": "y"}}, {"f": {0}})
        self.assertTrue(any("untouched object Other" in x for x in g["fail"]), g["fail"])           # a failed gate blocks install (Flow test)
        with fake():                                                                                  # an unchanged bundle is installed as the vanilla file: not checked
            g, _ = verify_static.gate(verify_static.EMPTY, self.v, self.b, {"f": {"changed": False}}, {"f": set()})
        self.assertEqual(g["fail"], [])


class GameFolderDetection(unittest.TestCase):
    def test_a_restore_copy_inside_the_game_folder_is_never_the_game(self):
        """2026-11-12: 'FM Blog Classic Skin 112 Restore/original/game/fm_Data' sorted before 'fm_Data' and was taken as the game."""
        with tempfile.TemporaryDirectory() as tmp, fake():
            g = Path(tmp) / "Football Manager 27"
            real = g / "fm_Data/StreamingAssets/aa/StandaloneWindows64"
            copy_ = g / "FM Blog Classic Skin 112 Restore/original/game/fm_Data/StreamingAssets/aa/StandaloneWindows64"
            for d, tag in ((real, "real"), (copy_, "old")):
                d.mkdir(parents=True)
                (d / bundles.STYLE_BUNDLES[0]).write_text(json.dumps([sheet("FigmaStyleVariables")]))
                (d / bundles.STYLE_BUNDLES[1]).write_text(json.dumps([dict(sheet(), note=tag)]))
            (g / "fm.exe").write_text("")
            info = detect.describe(g)
            self.assertEqual(Path(info["aa_dir"]), real); self.assertEqual([Path(x) for x in info["other_copies"]], [copy_])
            # a workspace whose snapshot came from the copy: install and restore refuse, with the reason
            ws = config.Workspace(Path(tmp) / "ws"); install.snapshot_vanilla(ws, copy_)
            ix = index_styles.build(ws)
            p = project.new("t"); p["scoped_rules"] = [{"sheet": "AlwaysAppliedStyleSheet", "selector": ".inner", "props": {"background-color": "#010203"}}]
            patcher.build(p, ws, ix); d = patcher.latest_build(ws, "t")
            before = (real / bundles.STYLE_BUNDLES[1]).read_text()
            with self.assertRaises(install.InstallError) as c: install.install(ws, real, d, lambda: False)
            self.assertIn("vanilla snapshot was taken from", str(c.exception)); self.assertEqual((real / bundles.STYLE_BUNDLES[1]).read_text(), before)
            with self.assertRaises(install.InstallError): install.restore(ws, real, "vanilla", lambda: False)
            install.install(ws, copy_, d, lambda: False)                                   # the folder the snapshot came from: allowed
            b = install.list_backups(ws)[0]["name"]
            with self.assertRaises(install.InstallError) as c: install.restore(ws, real, b, lambda: False)
            self.assertIn("holds files from", str(c.exception))
            install.snapshot_vanilla(ws, real, force=True); self.assertIsNone(install.snapshot_mismatch(ws, real))
            for h in list(logging.getLogger("skin_editor").handlers): logging.getLogger("skin_editor").removeHandler(h); h.close()


class TamperBeforeInstall(unittest.TestCase):
    def test_modified_ui_bundle_or_updated_catalog_blocks_install(self):
        with tempfile.TemporaryDirectory() as tmp, fake():
            aa = Path(tmp) / "StreamingAssets/aa/StandaloneWindows64"; aa.mkdir(parents=True)
            (aa / bundles.STYLE_BUNDLES[0]).write_text(json.dumps([sheet("FigmaStyleVariables")]))
            (aa / bundles.STYLE_BUNDLES[1]).write_text(json.dumps([sheet()]))
            other = aa / "ui-tactics_assets_all.bundle"; other.write_text("stock"); (aa.parent / "catalog.hash").write_text("cat1")
            ws = config.Workspace(Path(tmp) / "ws"); install.snapshot_vanilla(ws, aa)
            ix = index_styles.build(ws)
            p = project.new("t"); p["scoped_rules"] = [{"sheet": "AlwaysAppliedStyleSheet", "selector": ".inner", "props": {"background-color": "#010203"}}]
            patcher.build(p, ws, ix); d = patcher.latest_build(ws, "t")
            other.write_text("move build")
            with self.assertRaises(install.InstallError) as c: install.install(ws, aa, d, lambda: False)
            self.assertIn("ui-tactics_assets_all.bundle", str(c.exception)); self.assertEqual(install.live_status(ws, aa)[bundles.STYLE_BUNDLES[1]]["state"], "vanilla")
            other.write_text("stock")
            self.assertEqual(install.install(ws, aa, d, lambda: False)["copied"], [bundles.STYLE_BUNDLES[1]])
            self.assertEqual(install.tamper_status(ws, aa)["state"], "clean")                   # our own skin counts as expected
            (aa.parent / "catalog.hash").write_text("cat2")
            with self.assertRaises(install.InstallError) as c: install.install(ws, aa, d, lambda: False)
            self.assertIn("catalog.hash changed", str(c.exception))
            for h in list(logging.getLogger("skin_editor").handlers): logging.getLogger("skin_editor").removeHandler(h); h.close()


class Flow(unittest.TestCase):
    def test_build_install_restore(self):
        with tempfile.TemporaryDirectory() as tmp, fake():
            aa = Path(tmp) / "game/X.app/Contents/Resources/Data/StreamingAssets/aa/StandaloneOSX"; aa.mkdir(parents=True)
            (aa / bundles.STYLE_BUNDLES[0]).write_text(json.dumps([sheet("FigmaStyleVariables")]))
            (aa / bundles.STYLE_BUNDLES[1]).write_text(json.dumps([sheet()]))
            info = detect.describe(Path(tmp) / "game")
            self.assertEqual(info["platform_folder"], "StandaloneOSX"); self.assertTrue(info["app"].endswith("X.app"))
            ws = config.Workspace(Path(tmp) / "ws")
            install.snapshot_vanilla(ws, aa)
            with self.assertRaises(install.InstallError): install.snapshot_vanilla(ws, aa)
            ix = index_styles.build(ws); self.assertEqual(len(index_styles.load(ws).sheets), len(ix.sheets))
            p = project.new("t")
            p["scoped_rules"] = [{"sheet": "AlwaysAppliedStyleSheet", "selector": ".inner", "props": {"background-color": "#010203"}}]
            rep = patcher.build(p, ws, ix, Path(tmp) / "game")
            self.assertEqual([f["changed"] for _, f in sorted(rep["files"].items())], [False, True])
            self.assertEqual(rep["gate"]["fail"], []); self.assertEqual(rep["specificity_log"][0]["after"], 31)
            self.assertEqual(p["scoped_rules"][0]["selector"], ".inner")   # the project keeps the authored selector
            d = patcher.latest_build(ws, "t")
            with self.assertRaises(install.InstallError): install.install(ws, aa, d, lambda: True)
            r = install.install(ws, aa, d, lambda: False)
            self.assertEqual(r["copied"], [bundles.STYLE_BUNDLES[1]])
            st = install.live_status(ws, aa)
            self.assertEqual([st[b]["state"] for b in bundles.STYLE_BUNDLES], ["vanilla", "skinned"])
            self.assertEqual(install.install(ws, aa, d, lambda: False)["copied"], [])
            patcher.build(project.new("e"), ws, ix)            # empty project: install puts vanilla back
            install.install(ws, aa, patcher.latest_build(ws, "e"), lambda: False)
            self.assertEqual(install.live_status(ws, aa)[bundles.STYLE_BUNDLES[1]]["state"], "vanilla")
            rp = d / "build-report.json"; bad = json.loads(rp.read_text()); bad["gate"]["fail"] = ["x"]
            rp.write_text(json.dumps(bad))                      # failed gate blocks install
            with self.assertRaises(install.InstallError): install.install(ws, aa, d, lambda: False)
            bad["gate"]["fail"] = []; rp.write_text(json.dumps(bad))
            (aa / bundles.STYLE_BUNDLES[1]).write_text("updated")   # simulated game update: refuse
            with self.assertRaises(install.InstallError): install.install(ws, aa, d, lambda: False)
            self.assertEqual(install.live_status(ws, aa)[bundles.STYLE_BUNDLES[1]]["state"], "changed")
            install.restore(ws, aa, "vanilla", lambda: False)
            self.assertEqual(install.live_status(ws, aa)[bundles.STYLE_BUNDLES[1]]["state"], "vanilla")
            self.assertEqual(len(install.list_backups(ws)), 3)
            self.assertFalse(list(aa.glob(".*tmp")))


class Launcher(unittest.TestCase):
    def test_generate(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg = dict(config.DEFAULTS, workspace_dir=tmp + "/w s")
            r = launcher.generate(cfg, tmp + "/out", project="/Users/me/It's here/fm27", venv="/Users/me/It's here/fm27/.venv")
            app = Path(tmp) / "out" / launcher.APP_NAME
            self.assertEqual(r["app"], str(app))
            with open(app / "Contents/Info.plist", "rb") as f: pl = plistlib.load(f)
            self.assertEqual((pl["CFBundleExecutable"], pl["CFBundlePackageType"], pl["CFBundleIdentifier"]),
                             ("launcher", "APPL", launcher.BUNDLE_ID))
            exe = app / "Contents/MacOS/launcher"
            self.assertTrue(os.access(exe, os.X_OK))
            txt = exe.read_text()
            self.assertTrue(txt.startswith("#!/bin/bash\n"))
            # macOS ships bash 3.2: no bash 4 constructs, and the script must also parse as plain POSIX sh
            for pat in (r"declare\s+-\w*A", r"\b(mapfile|readarray|coproc)\b", r"&>>", r"\|&", r"\$\{[^}]*(\^\^|,,)[^}]*\}",
                        r";;&", r";&\s*$", r"\$\{[^}]*@[QEPAa]\}", r"\bwait\s+-n\b", r"globstar", r"\$EPOCH", r"\[\["):
                self.assertIsNone(re.search(pat, txt, re.M), pat)
            self.assertIn('cd \\"NEW_FOLDER\\" && python3.12 -m skin_editor launcher --yes', txt)
            self.assertIn("python3.13, python3.11, python3.14 or python3.10", txt)         # the moved-folder dialog names the same fallback list
            # candidate order 3.12, 3.13, 3.11, 3.14, 3.10, and never a bare python3 as a candidate
            m = re.search(r"for v in ([\d. ]+); do", txt); self.assertIsNotNone(m)
            self.assertEqual(m.group(1).split(), ["3.12", "3.13", "3.11", "3.14", "3.10"])
            self.assertIn("python$v", txt)
            self.assertIsNone(re.search(r"(?<![\w.$/])python3(?![\w.])\s*(-m|\"|\)|;|\n)", txt.split("# ---- Python environment")[1].split("export FM27SE_WORKSPACE")[0].replace("python3.1", "")), "bare python3 candidate")
            self.assertIn("""PROJECT='/Users/me/It'"'"'s here/fm27'""", txt)
            self.assertIn("WS=%s" % shlex.quote(str(Path(tmp + "/w s"))), txt); self.assertNotIn("@", txt.split("LOG=")[0])   # the path as the OS writes it (backslashes on Windows)
            for sh in ("bash", "sh", "dash"):
                if shutil.which(sh):
                    r_ = subprocess.run([sh, "-n", exe.as_posix()], capture_output=True, text=True)           # the syntax check; the shell and its message are in the failure text
                    self.assertEqual(r_.returncode, 0, "%s -n: %s (%s)" % (sh, r_.stderr.strip()[:300], shutil.which(sh)))
            launcher.generate(cfg, tmp + "/out", project="/new/place", venv="/new/place/.venv")   # regenerate
            self.assertIn("PROJECT=/new/place", exe.read_text())
            (app / "Contents/Info.plist").write_bytes(plistlib.dumps({"CFBundleIdentifier": "com.other.app"}))
            with self.assertRaises(RuntimeError): launcher.generate(cfg, tmp + "/out")              # not ours
            self.assertEqual(launcher.plan(cfg)["choices"][-1], str(config.resource_root().parent))

    @unittest.skipUnless(shutil.which("bash") and shutil.which("curl") and sys.platform != "win32", "needs bash and curl")
    def test_cold_start_two_clicks(self):
        """Two clicks at the same moment with no server running: one server, the loser waits, both open the URL."""
        with tempfile.TemporaryDirectory() as tmp, mock.patch.dict(os.environ, {"FM27SE_WORKSPACE": tmp + "/ws"}):
            os.makedirs(tmp + "/ws"); os.makedirs(tmp + "/venv/bin"); os.makedirs(tmp + "/stub")
            Path(tmp, "ws/config.json").write_text(json.dumps({"server": {"port": 8797}}))
            os.symlink(sys.executable, tmp + "/venv/bin/python")
            for name, body in (("open", 'echo "OPEN $1" >> "%s/calls"' % tmp), ("osascript", 'echo "DIALOG $*" >> "%s/calls"' % tmp)):
                Path(tmp, "stub", name).write_text("#!/bin/sh\n" + body + "\n"); os.chmod(tmp + "/stub/" + name, 0o755)
            exe = Path(launcher.generate(config.load(), tmp + "/out", venv=tmp + "/venv")["app"]) / "Contents/MacOS/launcher"
            env = dict(os.environ, PATH=tmp + "/stub" + os.pathsep + os.environ["PATH"])
            env.pop("FM27SE_WORKSPACE")                                 # the launcher must supply it from its baked path
            url = None
            try:
                clicks = [subprocess.Popen(["bash", str(exe)], env=env) for _ in range(2)]
                self.assertEqual([c.wait(90) for c in clicks], [0, 0])
                calls = Path(tmp, "calls").read_text().splitlines(); log = Path(tmp, "ws/logs/launcher.log").read_text()
                url = Path(tmp, "ws/state/last-url").read_text().strip()
                self.assertEqual(calls, ["OPEN " + url] * 2)
                self.assertEqual(log.count("starting server"), 1)
                self.assertEqual(log.count("another launch is in progress; waiting for it"), 1)
                self.assertFalse(Path(tmp, "ws/state/launcher.lock").exists())
                ping = urllib.request.urlopen("http://127.0.0.1:8797/ping").read().decode()
                self.assertEqual(ping.split()[1], Path(tmp, "ws/state/instance-id").read_text().strip())
            finally:
                if url:
                    urllib.request.urlopen(urllib.request.Request("http://127.0.0.1:8797/api/quit", data=b"{}",
                                                                  headers={"X-Token": url.split("t=")[1]}))
                    time.sleep(0.5)

    def test_server_state_ping_quit(self):
        with tempfile.TemporaryDirectory() as tmp, mock.patch.dict(os.environ, {"FM27SE_WORKSPACE": tmp}):
            Path(tmp, "config.json").write_text(json.dumps({"server": {"port": 8793}}))
            th = threading.Thread(target=server.serve, args=(False,), daemon=True); th.start()
            state = Path(tmp) / "state"
            for _ in range(100):
                if (state / "last-url").exists(): break
                time.sleep(0.05)
            url = (state / "last-url").read_text().strip(); inst = (state / "instance-id").read_text().strip()
            self.assertRegex(url, r"^http://127\.0\.0\.1:8793/\?t=.{20,}$"); self.assertRegex(inst, "^[0-9a-f]{16}$")
            ping = urllib.request.urlopen("http://127.0.0.1:8793/ping").read().decode()
            self.assertEqual(ping, "fm27-skin-editor " + inst)
            def post(path, tok):
                req = urllib.request.Request("http://127.0.0.1:8793" + path, data=b"{}", headers={"X-Token": tok})
                try: return urllib.request.urlopen(req).status
                except urllib.error.HTTPError as e: return e.code
            self.assertEqual(post("/api/quit", "wrong"), 403)
            self.assertEqual(post("/api/launcher", url.split("t=")[1]), 200)
            self.assertEqual(post("/api/quit", url.split("t=")[1]), 200)
            th.join(5); self.assertFalse(th.is_alive())
            self.assertFalse((state / "last-url").exists()); self.assertFalse((state / "instance-id").exists())
            lg = logging.getLogger("skin_editor")           # the app log handler keeps app.log open; Windows cannot delete the temp dir otherwise
            for h in list(lg.handlers): lg.removeHandler(h); h.close()


if __name__ == "__main__":
    unittest.main()
