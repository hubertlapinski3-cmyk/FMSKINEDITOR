"""Live preview: model builder bindings, evaluation against a project, verify region selection, routes."""
import io, json, logging, os, re, sys, tempfile, threading, unittest, urllib.error, urllib.request
from pathlib import Path
from unittest import mock

from skin_editor import index_styles, preview, project, server, verify


class _PreviewModelHelper:
    SCHEMA = "fm27se-preview/1"
    VAR = re.compile(r"var\((--[\w-]+)\)$")
    HEX = re.compile(r"#[0-9A-Fa-f]{6}([0-9A-Fa-f]{2})?$")

    @classmethod
    def winner(cls, src):
        rules = src.get("rules") or []
        verdict = src.get("verdict") or ""
        if verdict.startswith("stylesheet:"):
            for r in rules:
                if verdict.startswith("stylesheet:%s %s " % (r["sheet"], r["selector"])) or verdict == "stylesheet:%s %s" % (r["sheet"], r["selector"]):
                    return r
        return rules[0] if rules else None

    @classmethod
    def binding(cls, src):
        if src.get("inline"):
            return {"kind": "code", "why": "inline value (set by code)"}
        v = src.get("verdict") or ""
        if not v.startswith("stylesheet:"):
            return {"kind": "code", "why": v.split(" (")[0] or "no stylesheet source"}
        r = cls.winner(src)
        if not r:
            return {"kind": "code", "why": "no rule reported"}
        val = r["value"].strip()
        base = {"sheet": r["sheet"], "selector": r["selector"], "value": val, "specificity": r.get("specificity")}
        m = cls.VAR.match(val)
        if m:
            return dict(base, kind="token", token=m.group(1))
        if cls.HEX.match(val):
            return dict(base, kind="literal")
        return dict(base, kind="code", why="value is not a single token or colour: " + val[:60])

    @classmethod
    def norm_hex(cls, h):
        h = (h or "").strip().upper()
        return h if cls.HEX.match(h) else None

    @classmethod
    def build(cls, measure, screen, resolution, build_label=None, state="vanilla"):
        regions = []
        for order, e in enumerate(measure):
            comp = e.get("component") or {}
            if comp.get("type") == "SIGradient" and cls.norm_hex(comp.get("startColour")) and cls.norm_hex(comp.get("endColour")) and e.get("w", 0) >= 1 and e.get("h", 0) >= 1:
                label = e.get("label", "")
                regions.append({
                    "id": "%s#%d:gradient" % (label.split(".")[0][:60], order), "order": order, "prop": "gradient",
                    "rect": [round(e["x"], 1), round(e["y"], 1), round(e["w"], 1), round(e["h"], 1)],
                    "label": label[:200], "text": "", "classes": e.get("classes") or [],
                    "colour": cls.norm_hex(comp["startColour"]), "end": cls.norm_hex(comp["endColour"]), "direction": comp.get("direction") or "LeftToRight",
                    "opacity": (e.get("resolved") or {}).get("opacity", 1),
                    "binding": {"kind": "gradient"} if comp.get("useCustomStyles") else {"kind": "code", "why": "gradient colours set by code (useCustomStyles false)"}})
            for prop, src in (e.get("src") or {}).items():
                col = cls.norm_hex(src.get("resolved") or (e.get("resolved") or {}).get(prop))
                if not col or not (e.get("w", 0) >= 1 and e.get("h", 0) >= 1):
                    continue
                label = e.get("label", "")
                regions.append({
                    "id": "%s#%d:%s" % (label.split(".")[0][:60], order, prop), "order": order, "prop": prop,
                    "rect": [round(e["x"], 1), round(e["y"], 1), round(e["w"], 1), round(e["h"], 1)],
                    "label": label[:200], "text": (e.get("text") or "")[:80], "classes": e.get("classes") or [],
                    "colour": col, "opacity": (e.get("resolved") or {}).get("opacity", 1),
                    "binding": cls.binding(src)})
        return {"schema": cls.SCHEMA, "screen": screen, "resolution": list(resolution), "screenshot": screen + ".png",
                "game_build": build_label, "measured_state": state, "regions": regions}

    @staticmethod
    def mark_sampleable(model, png_bytes, tolerance=6):
        cand = [r for r in model["regions"] if r["prop"] == "background-color" and len(r["colour"]) in (7, 9)
                and (len(r["colour"]) == 7 or r["colour"].endswith("FF")) and r.get("opacity", 1) >= 0.999 and r["rect"][2] >= 12 and r["rect"][3] >= 12]
        probe = {"resolution": model["resolution"], "regions": [{"id": str(i), "rect": r["rect"], "expected": r["colour"][:7]} for i, r in enumerate(cand)]}
        for row, r in zip(verify.compare(probe, png_bytes, tolerance)["rows"], cand):
            r["sample_ok"] = row["result"] == "landed"
        return sum(r.get("sample_ok", False) for r in model["regions"])


bpm = _PreviewModelHelper


def index():
    """--base #112233; --alias: var(--base); --deep: var(--alias); --lit #DA0037 (a literal token def); --loop-a <-> --loop-b."""
    rule = lambda i, sels, props, t=0: {"i": i, "s": sels, "t": t, "p": props}
    rules = [rule(0, [":root"], [["--base", "#112233", [["#112233", 1.0]]], ["--alias", "var(--base)", []], ["--deep", "var(--alias)", []],
                                 ["--lit", "#DA0037", [["#DA0037", 1.0]]], ["--loop-a", "var(--loop-b)", []], ["--loop-b", "var(--loop-a)", []]], 1),
             rule(1, [".grad"], [["--start-colour", "var(--base)", []], ["--end-colour", "#DA0037", [["#DA0037", 1.0]]]]),
             rule(2, [".wrong"], [["--start-colour", "#000000", [["#000000", 1.0]]], ["--end-colour", "#000000", [["#000000", 1.0]]]])]
    return index_styles.StyleIndex([{"bundle": "b", "name": "AlwaysAppliedStyleSheet", "rules": rules, "failures": []}])


def src(value=None, verdict=None, inline=None, sheet="AlwaysAppliedStyleSheet", selector=".x", resolved="#112233"):
    rules = [] if value is None else [{"sheet": sheet, "selector": selector, "specificity": 11, "order": "1", "value": value}]
    return {"resolved": resolved, "inline": inline, "rules": rules,
            "verdict": verdict or ("stylesheet:%s %s (value is a variable)" % (sheet, selector) if value else "default (no inline value, no matching rule)")}


def el(label, x, y, w, h, classes=(), **props):
    return {"path": "P0/" + label, "label": label, "text": "", "x": x, "y": y, "w": w, "h": h, "classes": list(classes),
            "resolved": {"opacity": 1}, "src": props}


MEASURE = [
    {"path": "P0", "label": "PanelRootElement#Root", "x": 0, "y": 0, "w": 160, "h": 90, "classes": []},
    el("VisualElement#Panel.panel", 0, 0, 160, 90, ["panel"], **{"background-color": src("var(--deep)")}),
    el("SIText.title", 10, 10, 60, 20, ["title"], color=src("var(--base)")),
    el("VisualElement#Hard.hard", 80, 10, 40, 40, ["hard"], **{"background-color": src("#DA0037", resolved="#DA0037")}),
    el("VisualElement#Code", 10, 50, 40, 30, **{"background-color": src(None, resolved="#445566")}),
    el("VisualElement#Inl", 60, 50, 20, 20, **{"background-color": src("var(--base)", inline="#010101", resolved="#010101")}),
    el("VisualElement#LitTok", 90, 60, 30, 20, **{"background-color": src("var(--lit)", resolved="#DA0037")}),
    el("VisualElement#Tr", 130, 60, 20, 20, **{"background-color": src("var(--base)", resolved="#11223380")}),
]
GRADS = [
    dict(el("SIGradient.grad", 0, 80, 160, 10, ["sigradient", "grad"]), component={"type": "SIGradient", "startColour": "#112233", "endColour": "#DA0037", "useCustomStyles": True, "direction": "LeftToRight"}),
    dict(el("SIGradient.wrong", 0, 0, 160, 5, ["sigradient", "wrong"]), component={"type": "SIGradient", "startColour": "#A40FC7", "endColour": "#A40FC700", "useCustomStyles": True}),
    dict(el("SIGradient#Club", 0, 5, 160, 5, ["sigradient"]), component={"type": "SIGradient", "startColour": "#FFD900E6", "endColour": "#FFD900E6", "useCustomStyles": False}),
]


def model():
    return bpm.build(MEASURE, "demo", (160, 90), "27.0.1.x")


def proj(**kw):
    p = project.new("p")
    p.update(kw)
    return p


def by_label(ev, label, prop="background-color"):
    return next(r for r in ev["regions"] if r["label"].startswith(label) and r["prop"] == prop)


class Builder(unittest.TestCase):
    def test_bindings(self):
        m = model()
        k = {r["label"].split(".")[0]: r["binding"] for r in m["regions"]}
        self.assertEqual((k["VisualElement#Panel"]["kind"], k["VisualElement#Panel"]["token"]), ("token", "--deep"))
        self.assertEqual((k["VisualElement#Hard"]["kind"], k["VisualElement#Hard"]["value"]), ("literal", "#DA0037"))
        self.assertEqual(k["VisualElement#Code"]["kind"], "code")
        self.assertEqual((k["VisualElement#Inl"]["kind"], k["VisualElement#Inl"]["why"]), ("code", "inline value (set by code)"))
        self.assertEqual(len(m["regions"]), 7); self.assertEqual(m["schema"], preview.SCHEMA)
        self.assertEqual(bpm.binding(src("var(--a)", verdict="inherited from an ancestor"))["kind"], "code")
        two = src("var(--b)"); two["rules"].insert(0, {"sheet": "S", "selector": ".first", "value": "#000000"})
        self.assertEqual(bpm.binding(two)["token"], "--b")                       # the verdict names the winner, not the list order


class Evaluate(unittest.TestCase):
    def setUp(self): self.ix, self.m = index(), model()

    def ev(self, p=None): return preview.evaluate(self.m, self.ix, p)

    def test_vanilla_changes_nothing(self):
        e = self.ev(); self.assertEqual(e["changed"], 0)
        self.assertEqual(self.ev(proj())["changed"], 0)
        self.assertEqual(e["screen_tokens"][0], "--base")

    def test_token_override_follows_the_alias_chain(self):
        e = self.ev(proj(token_overrides=[{"token": "--alias", "value": {"rgb": "#AA0000", "a": 1.0}}]))
        r = by_label(e, "VisualElement#Panel")
        self.assertEqual((r["skin"], r["changed"], r["chain"]), ("#AA0000FF", True, ["--deep", "--alias"]))
        self.assertEqual(by_label(e, "SIText", "color")["changed"], False)                 # --base itself is not overridden
        e = self.ev(proj(token_overrides=[{"token": "--base", "value": {"rgb": "#00AA00", "a": 0.5}}]))
        self.assertEqual(by_label(e, "VisualElement#Panel")["skin"], "#00AA0080")        # through two aliases, alpha kept
        self.assertEqual(by_label(e, "VisualElement#Inl")["changed"], False)              # inline (code) value: untouched
        self.assertEqual(by_label(e, "VisualElement#Code")["changed"], False)

    def test_override_to_another_token_and_reverts(self):
        e = self.ev(proj(token_overrides=[{"token": "--deep", "value": "var(--lit)"}]))
        self.assertEqual(by_label(e, "VisualElement#Panel")["skin"], "#DA0037FF")
        e = self.ev(proj(token_overrides=[{"token": "--deep", "value": "var(--lit)"}], reverts=["--deep"]))
        self.assertFalse(by_label(e, "VisualElement#Panel")["changed"])
        e = self.ev(proj(token_overrides=[{"token": "--deep", "value": "var(--loop-a)"}]))
        r = by_label(e, "VisualElement#Panel"); self.assertFalse(r["changed"]); self.assertEqual(r["why"], "")    # a cycle: shown unchanged

    def test_literal_swaps_hit_literals_and_literal_token_definitions(self):
        e = self.ev(proj(literal_swaps=[{"from": {"rgb": "#DA0037", "a": 1.0}, "to": {"rgb": "#6C001C", "a": 1.0}, "mode": "rgb-keep-alpha"}]))
        self.assertEqual(by_label(e, "VisualElement#Hard")["skin"], "#6C001CFF")
        self.assertEqual(by_label(e, "VisualElement#LitTok")["skin"], "#6C001CFF")          # --lit is defined as #DA0037
        e = self.ev(proj(literal_swaps=[{"from": {"rgb": "#DA0037", "a": 0.5}, "to": {"rgb": "#6C001C", "a": 1.0}, "mode": "rgba"}]))
        self.assertFalse(by_label(e, "VisualElement#Hard")["changed"])                    # exact RGBA: alpha 1.0 does not match 0.5

    def test_scoped_rule_is_matched_on_the_subject_and_marked_approx(self):
        rule = {"sheet": "AlwaysAppliedStyleSheet", "selector": ".wrap .hard", "props": {"background-color": {"rgb": "#0000FF", "a": 1.0}}}
        r = by_label(self.ev(proj(scoped_rules=[rule])), "VisualElement#Hard")
        self.assertEqual((r["skin"], r["approx"]), ("#0000FFFF", True)); self.assertIn("approx", r["why"])
        hover = dict(rule, selector=".hard:hover")
        self.assertFalse(by_label(self.ev(proj(scoped_rules=[hover])), "VisualElement#Hard")["changed"])         # a state rule is not idle
        inl = dict(rule, selector="#Inl")
        self.assertFalse(by_label(self.ev(proj(scoped_rules=[inl])), "VisualElement#Inl")["changed"])           # an inline value beats rules

    def test_suggest_and_verify_regions(self):
        s = preview.suggest(self.m, self.ix, "#DA0030")
        self.assertEqual(s[0]["token"], "--lit"); self.assertTrue(all(x["distance"] >= s[0]["distance"] for x in s))
        v = preview.verify_regions(self.ev())
        ids = {r["id"].split("#")[0] + "#" + r["id"].split("#")[1] for r in v["regions"]}
        self.assertNotIn("VisualElement#Panel", ids)            # its centre (80, 45) is covered by a later background
        self.assertNotIn("VisualElement#Tr", ids)              # translucent
        self.assertIn("VisualElement#Hard", ids)
        with self.assertRaises(ValueError): preview.suggest(self.m, self.ix, "nope")


class Gradients(unittest.TestCase):
    def test_stylesheet_gradient_is_evaluated_only_when_the_matched_rule_explains_vanilla(self):
        m = bpm.build(MEASURE + GRADS, "demo", (160, 90))
        g = [r for r in m["regions"] if r["prop"] == "gradient"]
        self.assertEqual([r["binding"]["kind"] for r in g], ["gradient", "gradient", "code"])
        p = proj(token_overrides=[{"token": "--base", "value": {"rgb": "#00AA00", "a": 1.0}}],
                 literal_swaps=[{"from": {"rgb": "#DA0037", "a": 1.0}, "to": {"rgb": "#6C001C", "a": 1.0}, "mode": "rgb-keep-alpha"}])
        ev = preview.evaluate(m, index(), p)
        good, wrong, club = [r for r in ev["regions"] if r["prop"] == "gradient"]
        self.assertEqual((good["skin"], good["skin_end"], good["changed"], good["approx"]), ("#00AA00FF", "#6C001CFF", True, True))
        self.assertEqual((good["chain_start"], good["chain_end"]), (["--base"], None))
        self.assertIn("--base", ev["screen_tokens"])
        self.assertEqual((wrong["changed"], wrong["binding"]["kind"]), (False, "code")); self.assertIn("not trusted", wrong["binding"]["why"])
        self.assertFalse(club["changed"]); self.assertIn("code", club["binding"]["why"])
        self.assertEqual(preview.evaluate(m, index(), None)["changed"], 0)


class ClubColours(unittest.TestCase):
    def test_option_adds_the_proven_rules_first_and_only_when_off(self):
        from skin_editor import club_colours
        p = proj(scoped_rules=[{"sheet": "AlwaysAppliedStyleSheet", "selector": ".mine", "props": {"color": {"rgb": "#FF0000", "a": 1.0}}}])
        self.assertEqual(len(project.to_spec(project.validate(p))["append_rules_by_sheet"]["AlwaysAppliedStyleSheet"]), 1)      # default: keep
        p["options"]["club_colours"] = False
        p["options"]["club_colours_replacement"] = "#202020"                                                                       # migrated to canonical
        p = project.validate(project.migrate(p))
        self.assertEqual(p["options"]["club_colours_replacement"], {"rgb": "#202020", "a": 1.0})
        rules = project.to_spec(p)["append_rules_by_sheet"]["AlwaysAppliedStyleSheet"]
        self.assertEqual(len(rules), len(club_colours.rules(project.CLUB_DEFAULT)) + 1); self.assertEqual(rules[-1]["selector"], ".mine")   # project rules last: they win
        self.assertEqual(rules[0], {"selector": ".navigation-header-gradient", "props": {"background-color": "#202020"}})
        self.assertEqual(project.to_spec(p)["rename_classes"], {"nav-on-light": "skin-off-navlight0", "nav-on-dark": "skin-off-navdark0"})
        self.assertEqual(project.to_spec(project.validate(proj()))["rename_classes"], {})
        self.assertIn({"selector": ".clubcolours-border", "props": {"border-color": "rgba(0, 0, 0, 0.0)"}}, rules)
        for r in club_colours.rules(project.CLUB_DEFAULT):
            project.check_selector(r["selector"]); [project.check_value(v) for v in r["props"].values()]
        p["options"]["club_colours"] = "no"
        with self.assertRaises(ValueError): project.validate(p)

    def test_preview_marks_only_club_painted_regions(self):
        ms = MEASURE + [
            dict(el("SIGradient#Club.sigradient", 0, 0, 160, 8, ["sigradient"]), component={"type": "SIGradient", "startColour": "#FFD900E6", "endColour": "#FFD900E6", "useCustomStyles": False}),
            el("VisualElement#BorderStyle.clubcolours-border", 0, 0, 4, 40, ["clubcolours-border"], **{"border-top-color": src(None, resolved="#FFFFFF59")}),
            el("SIText#fm-tactics-shirt-number.fm-club-primary-color", 20, 20, 10, 10, ["fm-club-primary-color"], color=src(None, resolved="#000000"))]
        m = bpm.build(ms, "demo", (160, 90))
        p = proj(); p["options"]["club_colours"] = False
        ev = preview.evaluate(m, index(), p)
        ch = {r["label"].split(".")[0]: r for r in ev["regions"] if r["changed"]}
        self.assertEqual(set(ch), {"SIGradient#Club", "VisualElement#BorderStyle"})
        self.assertEqual((ch["SIGradient#Club"]["skin"], ch["SIGradient#Club"]["skin_end"]), ("#171717FF", "#171717FF"))
        self.assertEqual(ch["VisualElement#BorderStyle"]["skin"], "#00000000"); self.assertTrue(ch["SIGradient#Club"]["approx"])
        self.assertEqual(preview.evaluate(m, index(), proj())["changed"], 0)


class Compare(unittest.TestCase):
    def test_screenshot_compare_landed_and_not_landed(self):
        from PIL import Image
        m = model(); ix = index()
        p = proj(literal_swaps=[{"from": {"rgb": "#DA0037", "a": 1.0}, "to": {"rgb": "#6C001C", "a": 1.0}, "mode": "rgb-keep-alpha"}])
        v = preview.verify_regions(preview.evaluate(m, ix, p))
        img = Image.new("RGB", (320, 180), (0x44, 0x55, 0x66))
        img.paste((0x6C, 0x00, 0x1C), (160, 20, 240, 100))                 # the Hard box (80,10,40,40) at 2x: skin colour landed
        buf = io.BytesIO(); img.save(buf, "PNG")
        r = verify.compare(v, buf.getvalue())
        row = next(x for x in r["rows"] if x["id"].startswith("VisualElement#Hard"))
        self.assertEqual(row["result"], "landed")
        img.paste((0xDA, 0x00, 0x37), (160, 20, 240, 100)); buf = io.BytesIO(); img.save(buf, "PNG")
        row = next(x for x in verify.compare(v, buf.getvalue())["rows"] if x["id"].startswith("VisualElement#Hard"))
        self.assertEqual(row["result"], "not_landed")


class Sampleable(unittest.TestCase):
    def test_builder_self_check_keeps_only_regions_whose_centre_shows_their_colour(self):
        from PIL import Image
        m = model()
        img = Image.new("RGB", (160, 90), (0x11, 0x22, 0x33))                 # the panel colour everywhere
        img.paste((0xDA, 0x00, 0x37), (80, 10, 120, 50))                       # Hard box painted as measured
        img.paste((0xFF, 0xFF, 0xFF), (20, 55, 40, 75))                        # something (text, icon) over the centre of the Code box
        buf = io.BytesIO(); img.save(buf, "PNG")
        self.assertGreater(bpm.mark_sampleable(m, buf.getvalue()), 0)
        ok = {r["label"].split(".")[0]: r.get("sample_ok") for r in m["regions"] if r["prop"] == "background-color"}
        self.assertTrue(ok["VisualElement#Hard"]); self.assertFalse(ok["VisualElement#Code"]); self.assertIsNone(ok["VisualElement#Tr"])   # translucent: never a candidate
        v = preview.verify_regions(preview.evaluate(m, index(), None))
        self.assertTrue(v["regions"]); self.assertTrue(all(r["id"].split("#")[0] + "#" + r["id"].split("#")[1].split(":")[0] != "VisualElement#Code" for r in v["regions"]))
        self.assertEqual(verify.compare(v, buf.getvalue())["landed"], len(v["regions"]))       # vanilla screenshot, no project: every judged region lands


class Routes(unittest.TestCase):
    def test_http(self):
        from PIL import Image
        with tempfile.TemporaryDirectory() as tmp, mock.patch.dict(os.environ, {"FM27SE_WORKSPACE": tmp + "/ws"}):
            md = Path(tmp) / "models"; md.mkdir()
            (md / "demo.json").write_text(json.dumps(model()))
            Image.new("RGB", (160, 90)).save(md / "demo.png")
            (md / "old.json").write_text(json.dumps({"screen": "old", "regions": []}))          # another schema: not listed
            with mock.patch.object(preview, "models_dir", lambda: md):
                app = server.App(); app.index = index()
                project.save(app.ws, proj(token_overrides=[{"token": "--base", "value": {"rgb": "#00AA00", "a": 1.0}}]))
                httpd = server.ThreadingHTTPServer(("127.0.0.1", 0), server.make_handler(app, "tok", 0)); port = httpd.server_address[1]
                th = threading.Thread(target=httpd.serve_forever, daemon=True); th.start()
                def call(path):
                    req = urllib.request.Request("http://127.0.0.1:%d%s" % (port, path), headers={"X-Token": "tok", "Host": "127.0.0.1:0"})
                    try:
                        r = urllib.request.urlopen(req); return r.status, r.headers.get("Content-Type"), r.read()
                    except urllib.error.HTTPError as e:
                        return e.code, e.headers.get("Content-Type"), e.read()
                try:
                    code, ct, body = call("/api/preview/models"); self.assertEqual([m["name"] for m in json.loads(body)], ["demo"])
                    code, ct, body = call("/api/preview/model?name=demo&project=p"); ev = json.loads(body)
                    self.assertEqual(code, 200); self.assertGreater(ev["changed"], 0)
                    code, ct, body = call("/api/preview/model?name=demo"); self.assertEqual(json.loads(body)["changed"], 0)
                    code, ct, body = call("/api/preview/image?name=demo"); self.assertEqual((code, ct, body[:4]), (200, "image/png", b"\x89PNG"))
                    for bad in ("../ws/config", "DEMO", "old", "nope"):
                        self.assertEqual(call("/api/preview/model?name=" + bad)[0], 400, bad)
                    code, ct, body = call("/api/preview/suggest?name=demo&rgb=%23112233"); s = json.loads(body); self.assertEqual((s[0]["distance"], s[0]["token"] in ("--base", "--deep")), (0, True))     # both paint #112233 here
                    self.assertEqual(json.loads(call("/api/models")[2]), ["demo"])
                finally:
                    httpd.shutdown(); httpd.server_close(); th.join(5)
                    lg = logging.getLogger("skin_editor")
                    for h in list(lg.handlers): lg.removeHandler(h); h.close()

    def test_frontend_has_the_preview_page(self):
        html = (Path(__file__).resolve().parent.parent / "frontend" / "index.html").read_text(encoding="utf-8")
        self.assertIn('"preview"', html.split("pages = [")[1].split("]")[0])
        for needle in ("/api/preview/model", "/api/preview/image", "function pvRepaint", "Save override"):
            self.assertIn(needle, html)


if __name__ == "__main__":
    unittest.main()
