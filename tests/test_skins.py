"""Compare another skin (USS folder or bundles) and export originals at true size."""
import io, json, logging, os, tempfile, threading, unittest, urllib.error, urllib.request
from pathlib import Path
from unittest import mock

from skin_editor import bundles, colour, images, project, server, skins
from tests.test_core import fake, sheet
from tests.test_preview import index, model
from tests.test_images import GAME, png

USS_A = """/* palette */
:root { --base: #AA0000; --alias: var(--new-wood); --new-wood: #6F4020; --bild-tisch: url("tisch.png"); --schrift-titel: url("titel.ttf"); }
.panel { background-image: var(--bild-tisch); -unity-slice-left: 40; }
.hide { display: none; }"""
USS_B = """:root { --lit: #DA0037; }
#Card-frame { --unity-image-tint-color: #00000000; rotate: -6deg; }"""


def uss_skin(tmp):
    d = Path(tmp) / "wood"; d.mkdir()
    (d / "skin.json").write_text(json.dumps({"Name": "Wood test", "Sheets": ["a.uss", "b.uss", "missing.uss"]}))
    (d / "a.uss").write_text(USS_A); (d / "b.uss").write_text(USS_B)
    (d / "tisch.png").write_bytes(png(40, 20)); (d / "titel.ttf").write_bytes(b"\0font"); (d / "extra.png").write_bytes(png())
    return d


class Uss(unittest.TestCase):
    def test_parse(self):
        rules = skins.parse_uss(USS_A)
        self.assertEqual(rules[0][0], ":root"); self.assertIn(("--base", "#AA0000"), rules[0][1])
        self.assertEqual(rules[2], (".hide", [("display", "none")]))

    def test_load_classifies_tokens_assets_and_techniques(self):
        with tempfile.TemporaryDirectory() as tmp:
            r = skins.load(uss_skin(tmp), index())
            self.assertEqual((r["kind"], r["name"], r["rules"]), ("uss", "Wood test", 3))
            ch = {t["token"]: t for t in r["tokens_changed"]}
            self.assertEqual(set(ch), {"--base", "--alias"})                                   # --lit is unchanged (#DA0037)
            self.assertEqual((ch["--base"]["vanilla_colour"], ch["--base"]["theirs_colour"]), ("#112233FF", "#AA0000FF"))
            self.assertEqual(ch["--alias"]["theirs_colour"], "#6F4020FF")                       # resolved through the skin's own token
            new = {t["token"]: t["kind"] for t in r["tokens_new"]}
            self.assertEqual(new, {"--new-wood": "other", "--bild-tisch": "image", "--schrift-titel": "font"})
            a = {x["file"]: x for x in r["assets"]}
            self.assertEqual((a["tisch.png"]["w"], a["tisch.png"]["h"], a["titel.ttf"]["kind"]), (40, 20, "font"))
            self.assertEqual(r["unused_files"], ["extra.png"]); self.assertTrue(any(s.get("missing") for s in r["sheets"]))
            for k in ("display: none (hide elements)", "transforms (rotate)", "9-slice images", "image tint via --unity-image-tint-color"):
                self.assertIn(k, r["techniques"])
            p = skins.as_project(r, "wood")
            self.assertEqual({o["token"]: o["value"] for o in p["token_overrides"]}, {"--base": {"rgb": "#AA0000", "a": 1.0}, "--alias": "var(--new-wood)"})

    def test_bundles_style_tokens_and_changed_images(self):
        with tempfile.TemporaryDirectory() as tmp, fake():
            game, theirs = Path(tmp) / "game", Path(tmp) / "theirs"; game.mkdir(); theirs.mkdir()
            t = sheet(); t["m_Rules"][0]["m_Properties"][0]["m_Values"][0]["valueIndex"] = 2          # --base now points at white
            (theirs / bundles.STYLE_BUNDLES[1]).write_text(json.dumps([t]))
            (game / "ui-x.bundle").write_text(json.dumps([sheet("A"), sheet("B")]))
            b = sheet("B"); b["floats"] = [2.0]; (theirs / "ui-x.bundle").write_text(json.dumps([sheet("A"), b]))
            from skin_editor import index_styles
            van = index_styles.StyleIndex([index_styles.sheet_entry(bundles.STYLE_BUNDLES[1], sheet())])
            with mock.patch.object(images, "scan_bundle", lambda p: [{"kind": "texture", "name": "bg", "w": 4, "h": 4, "path_id": "1"}]):
                r = skins.load(theirs, van, game)
            self.assertEqual(r["kind"], "bundles")
            ch = {x["token"]: x for x in r["tokens_changed"]}
            self.assertIn("--base", ch); self.assertEqual(ch["--base"]["theirs_colour"], "#FFFFFFFF")
            self.assertEqual([(x["bundle"], x["path_id"], x["name"]) for x in r["images_changed"]], [("ui-x.bundle", "1", "bg")])

    def test_refuses_empty(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError): skins.load(tmp, None)
            with self.assertRaises(FileNotFoundError): skins.load(Path(tmp) / "nope", None)


class Export(unittest.TestCase):
    def test_band_region_is_clipped_exactly(self):
        P = [(0, 0), (10, 0), (0, 10)]
        C = [(-3, 0), (3, 0), (-3, 0)]                     # rank one: the band |u| <= 1 is 10/3 wide around x = 5
        kind, poly = images._flagged_region(P, C)
        self.assertEqual(kind, "poly")
        xs = sorted(round(p[0], 6) for p in poly); self.assertAlmostEqual(min(xs), 10 / 3, 5); self.assertAlmostEqual(max(xs), 20 / 3, 5)
        self.assertIsNone(images._flagged_region(P, [(5, 5)] * 3))
        self.assertEqual(images._flagged_region(P, [(0.1, 0)] * 3)[0], "poly")
        self.assertEqual(images._flagged_region(P, [(-2, -2), (2, -2), (-2, 2)])[0], "ellipse")

    def test_vector_to_svg(self):
        from tests.test_images import tt, SVG
        t = tt(); images.svg_to_vector(t, SVG)
        s = images.vector_to_svg(t).decode()
        self.assertTrue(s.startswith('<svg xmlns="http://www.w3.org/2000/svg" width="32" height="32"'))
        self.assertIn('fill="#DA0037"', s); self.assertIn('fill-opacity="0.502', s)

    @unittest.skipUnless((GAME / "ui-icons_assets_common.bundle").is_file(), "needs the game")
    def test_export_real_items_at_true_size(self):
        from PIL import Image
        icon = {"kind": "icon", "name": "win_small", "bundle": "ui-icons_assets_2x.bundle", "path_id": "0"}
        files = dict(images.export_item(GAME, icon))
        self.assertEqual({k: Image.open(io.BytesIO(v)).size for k, v in files.items()},
                         {"win_small_1x.png": (16, 16), "win_small_2x.png": (32, 32), "win_small_3x.png": (48, 48), "win_small_4x.png": (64, 64)})
        svg = next(x for x in images.scan_bundle(GAME / "ui-icons_assets_common.bundle") if x["kind"] == "svg")
        f = dict(images.export_item(GAME, dict(svg, bundle="ui-icons_assets_common.bundle")))
        self.assertTrue(any(k.endswith(".svg") for k in f)); self.assertTrue(any(k.endswith("@8x.png") for k in f))


class Routes(unittest.TestCase):
    def test_compare_preview_import(self):
        with tempfile.TemporaryDirectory() as tmp, mock.patch.dict(os.environ, {"FM27SE_WORKSPACE": tmp + "/ws"}):
            md = Path(tmp) / "models"; md.mkdir(); (md / "demo.json").write_text(json.dumps(model()))
            from PIL import Image
            Image.new("RGB", (160, 90)).save(md / "demo.png")
            skin = uss_skin(tmp)
            with mock.patch("skin_editor.preview.models_dir", lambda: md):
                app = server.App(); app.index = index()
                httpd = server.ThreadingHTTPServer(("127.0.0.1", 0), server.make_handler(app, "tok", 0)); port = httpd.server_address[1]
                th = threading.Thread(target=httpd.serve_forever, daemon=True); th.start()
                def call(path, body=None):
                    data = None if body is None else json.dumps(body).encode()
                    req = urllib.request.Request("http://127.0.0.1:%d%s" % (port, path), data=data, headers={"X-Token": "tok", "Host": "127.0.0.1:0"})
                    try: r = urllib.request.urlopen(req); return r.status, r.headers.get("Content-Type"), r.read()
                    except urllib.error.HTTPError as e: return e.code, e.headers.get("Content-Type"), e.read()
                try:
                    self.assertEqual(call("/api/preview/model?name=demo&project=__compare__")[0], 400)          # nothing loaded yet
                    code, _, body = call("/api/compare/load", {"path": str(skin)}); self.assertEqual(code, 200, body)
                    code, ct, body = call("/api/compare/asset?file=tisch.png"); self.assertEqual((code, ct), (200, "image/png"))
                    self.assertEqual(call("/api/compare/asset?file=../../ws/config.json")[0], 400)
                    self.assertEqual(call("/api/compare/asset?file=extra.png")[0], 400)                            # not referenced by the skin
                    code, _, body = call("/api/preview/model?name=demo&project=__compare__"); self.assertGreater(json.loads(body)["changed"], 0)
                    code, _, body = call("/api/compare/import", {"name": "wood"}); self.assertEqual(json.loads(body)["tokens"], 2)
                    self.assertEqual(call("/api/compare/import", {"name": "wood"})[0], 400)                         # exists
                finally:
                    httpd.shutdown(); httpd.server_close(); th.join(5)
                    for h in list(logging.getLogger("skin_editor").handlers): logging.getLogger("skin_editor").removeHandler(h); h.close()

    def test_frontend_has_compare_and_export(self):
        html = (Path(__file__).resolve().parent.parent / "frontend" / "index.html").read_text(encoding="utf-8")
        self.assertIn('"compare"', html.split("pages = [")[1].split("]")[0])
        for needle in ("/api/compare/load", "/api/images/export?", "/api/images/export-all", "__compare__"):
            self.assertIn(needle, html)


if __name__ == "__main__":
    unittest.main()


@unittest.skipUnless((GAME / "ui-styles_assets_2x.bundle").is_file(), "needs the game")
class IconClasses(unittest.TestCase):
    def test_classes_from_the_games_image_stylesheets(self):
        m = images.icon_classes(GAME)
        self.assertEqual(m[("icon", "win_small")], ["game-concepts-win_small"])
        self.assertGreater(sum(1 for k in m if k[0] == "icon"), 1200); self.assertGreater(sum(1 for k in m if k[0] == "svg"), 250)


class NativeExport(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True); self.addCleanup(self.tmp.cleanup)
        from skin_editor import config
        self.ws = config.Workspace(Path(self.tmp.name) / "ws")

    def proj(self):
        p = project.new("demo")
        p["token_overrides"] = [{"token": "--base", "value": {"rgb": "#AA0000", "a": 1.0}}, {"token": "--alias", "value": "var(--lit)"}]
        p["literal_swaps"] = [{"from": {"rgb": "#DA0037", "a": 1.0}, "to": {"rgb": "#6C001C", "a": 0.5}, "mode": "rgba"}]
        p["scoped_rules"] = [{"sheet": "AlwaysAppliedStyleSheet", "selector": ".mine", "props": {"color": {"rgb": "#FF0000", "a": 1.0}}}]
        p["options"]["club_colours"] = False
        d = self.ws.images / "demo"; d.mkdir(parents=True, exist_ok=True); (d / "star.svg").write_bytes(b'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 10"><rect width="10" height="10" fill="#f00"/></svg>')
        (d / "bg.png").write_bytes(png())
        p["image_swaps"] = [{"bundle": "ui-icons_assets_2x.bundle", "path_id": "7", "name": "win_small", "kind": "icon", "source": "star.svg", "fit": "contain"},
                            {"bundle": "ui-backgrounds_assets_.bundle", "path_id": "9", "name": "wall", "kind": "texture", "source": "bg.png", "fit": "cover"}]
        return p

    def export(self, p, dest):
        from skin_editor import native
        cat = [{"kind": "icon", "name": "win_small", "w": 32, "h": 32, "bundle": "ui-icons_assets_2x.bundle", "path_id": "7"}]
        with mock.patch.object(images, "icon_classes", lambda aa: {("icon", "win_small"): ["game-concepts-win_small"]}), \
             mock.patch.object(images, "catalog", lambda ws, aa, refresh=False: cat):
            return native.export(self.ws, p, index(), "aa", dest, "demo-skin", "Demo")

    def test_export_writes_a_loadable_folder(self):
        from PIL import Image
        dest = Path(self.tmp.name) / "skins"; dest.mkdir()
        r = self.export(self.proj(), dest)
        d = Path(r["folder"])
        self.assertEqual(json.loads((d / "skin.json").read_text()), {"Name": "Demo", "Sheets": ["tokens.uss", "rules.uss", "images.uss"]})
        tok = (d / "tokens.uss").read_text(); self.assertIn("--base: #AA0000;", tok); self.assertIn("--alias: var(--lit);", tok)
        rules = (d / "rules.uss").read_text()
        self.assertTrue(rules.index(".navigation-header-gradient {") < rules.index(".mine {"))      # club rules first: the project's win ties
        self.assertIn("color: #FF0000;", rules)
        img = (d / "images.uss").read_text(); self.assertIn('.game-concepts-win_small {\n    background-image: url("images/win_small.png");', img)
        self.assertEqual(Image.open(d / "images" / "win_small.png").size, (64, 64))                     # 16 px icon at 4x
        self.assertEqual((r["problems"], r["skipped"]), ([], []))
        self.assertIn("#Card-frame {\n    --unity-image-tint-color: #00000000;", img)                 # the wallpaper: game picture hidden ...
        self.assertIn(".base-layer-content {\n    background-image: url(\"images/wall.png\");", img)    # ... and covered (default places)
        self.assertTrue((d / "images" / "wall.png").is_file()); self.assertTrue(any("nav-on-light" in s for s in r["notes"]))
        p2 = self.proj(); p2["image_swaps"][1]["where"] = ["loading"]
        img2 = (Path(self.export(p2, dest)["folder"]) / "images.uss").read_text()
        self.assertIn("#Background.modal-sheet-background", img2); self.assertNotIn("#Card-frame", img2)
        bad = self.proj(); bad["image_swaps"][1]["where"] = ["moon"]
        with self.assertRaises(ValueError): project.validate(bad)
        o = project.new("x"); o["options"]["output"] = "native"; project.validate(o); o["options"]["output"] = "usb"
        with self.assertRaises(ValueError): project.validate(o)
        r2 = self.export(self.proj(), dest); self.assertEqual(r2["problems"], [])                          # re-export replaces our own folder
        (dest / "other").mkdir(); (dest / "other" / "skin.json").write_text("{}")
        from skin_editor import native
        with self.assertRaises(ValueError):
            native.export(self.ws, self.proj(), index(), "aa", dest, "other")                              # never overwrites a folder we did not write

    def test_literal_rules_copy_each_rule_using_the_colour(self):
        from skin_editor import native
        rules, notes = native.literal_rules(self.proj(), index())
        self.assertEqual(rules, [".grad {\n    --end-colour: #6C001C80;\n}\n"])                            # the one non-token rule using #DA0037
        self.assertIn("1 rule(s)", notes[0])

    def test_validate_catches_missing_and_escaping_urls(self):
        from skin_editor import native
        d = Path(self.tmp.name) / "s"; d.mkdir()
        (d / "skin.json").write_text(json.dumps({"Sheets": ["a.uss", "gone.uss"]}))
        (d / "a.uss").write_text('.x { background-image: url("nope.png"); } .y { background-image: url("../../evil.png"); }')
        probs = native.validate(d)
        self.assertEqual(len(probs), 3); self.assertTrue(any("gone.uss" in x for x in probs))


class NavOnLight(unittest.TestCase):
    def test_light_bar_rules_take_their_dark_bar_values(self):
        from skin_editor import index_styles, native
        rule = lambda i, sels, props: {"i": i, "s": sels, "t": 0, "p": [[k, v, []] for k, v in props]}
        ix = index_styles.StyleIndex([{"bundle": "b", "name": "S", "failures": [], "rules": [
            rule(0, [".nav-on-light .tab .portal-text"], [("color", "#000000")]),
            rule(1, [".nav-on-dark .tab .portal-text"], [("color", "#FFFFFF")]),
            rule(2, ["#MainNav.nav-on-light .icon"], [("-unity-background-image-tint-color", "#111111")]),
            rule(3, ["#MainNav .icon"], [("-unity-background-image-tint-color", "var(--white)")]),
            rule(4, [".nav-on-light .orphan"], [("color", "#222222")])]}])
        rules, n = native.nav_on_light_rules(ix)
        self.assertEqual(n, 2)
        self.assertIn(".nav-on-light .tab .portal-text {\n    color: #FFFFFF;\n}\n", rules)
        self.assertIn("#MainNav.nav-on-light .icon {\n    -unity-background-image-tint-color: var(--white);\n}\n", rules)