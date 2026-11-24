"""Image and SVG swaps: conversion, validation, snapshot / build / gate / install flow, routes, and (when the game is installed) a
real swap on copies of game bundles."""
from tests import gamebuild
import io, json, logging, os, tempfile, threading, unittest, urllib.error, urllib.request
from pathlib import Path
from unittest import mock

from skin_editor import bundles, config, images, index_styles, install, patcher, project, server, verify_static
from tests.test_core import fake, sheet

SVG = (b'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100"><circle cx="50" cy="50" r="45" fill="#DA0037"/>'
       b'<path d="M30 30 H70 V70 H30 Z M40 40 V60 H60 V40 Z" fill="#FFFFFF" fill-rule="evenodd"/>'
       b'<rect x="5" y="5" width="20" height="10" fill="#00AA00" fill-opacity="0.5" stroke="#000" stroke-width="2"/></svg>')
GAME = gamebuild.aa()                                         # the configured game folder (tests/gamebuild.py), not a typed path


def png(w=64, h=40, col=(200, 10, 10)):
    from PIL import Image
    b = io.BytesIO(); Image.new("RGB", (w, h), col).save(b, "PNG"); return b.getvalue()


def tt(w=32, h=32):
    return {"size": {"x": float(w), "y": float(h)}, "vertices": [], "indices": [], "settings": [], "atlas": {"m_FileID": 0, "m_PathID": 0}}


class Units(unittest.TestCase):
    def test_pack_unpack_matches_unity_color32(self):
        self.assertEqual(images.unpack(4285228132), (0x64, 0x64, 0x6B, 0xFF))           # a grey from a game icon
        self.assertEqual(images.pack(0x64, 0x64, 0x6B, 0xFF), 4285228132)

    def test_sniff_and_fit(self):
        self.assertEqual(images.sniff(png()), "png"); self.assertEqual(images.sniff(SVG), "svg"); self.assertIsNone(images.sniff(b"hello"))
        for fit in images.FITS:
            self.assertEqual(images.fit_image(png(64, 40), 200, 100, fit).size, (200, 100))
        c = images.fit_image(png(10, 10), 40, 20, "contain")
        self.assertEqual(c.getpixel((0, 10))[3], 0); self.assertEqual(c.getpixel((20, 10))[:3], (200, 10, 10))    # bars transparent, centre image

    def test_svg_to_vector_fills_holes_and_alpha(self):
        t = tt(); notes = images.svg_to_vector(t, SVG)
        self.assertTrue(t["indices"]) and self.assertEqual(len(t["indices"]) % 3, 0)
        self.assertTrue(any("stroke was ignored" in n for n in notes))
        cols = {images.unpack(v["tint"]["rgba"]) for v in t["vertices"]}
        self.assertEqual(cols, {(0xDA, 0, 0x37, 255), (255, 255, 255, 255), (0, 0xAA, 0, 128)})
        self.assertTrue(all(v["flags"]["rgba"] == 0 and 0 <= v["position"]["x"] <= 32 and 0 <= v["position"]["y"] <= 32 for v in t["vertices"]))
        img = images.render_vector(t, 100)
        self.assertEqual(img.getpixel((50, 50))[:3], (0xDA, 0, 0x37))                     # the hole of the white frame shows the red circle
        self.assertEqual(img.getpixel((50, 34))[:3], (255, 255, 255))                     # the white frame
        self.assertEqual(img.getpixel((1, 99))[3], 0)                                     # outside every shape
        with self.assertRaises(ValueError): images.svg_to_vector(tt(), b'<svg xmlns="http://www.w3.org/2000/svg"><rect width="5" height="5" fill="none"/></svg>')
        self.assertTrue(images.render_svg_png(SVG).startswith(b"\x89PNG"))

    def test_flagged_triangles_keep_only_the_unit_circle(self):
        """Game icons draw rounded edges as flagged triangles whose interpolated circle.xy must stay inside the unit circle."""
        def vx(x, y, cx, cy): return {"position": {"x": x, "y": y, "z": 0.0}, "tint": {"rgba": images.pack(255, 255, 255)}, "uv": {"x": 0.0, "y": 0.0},
                                      "settingIndex": 0, "flags": {"rgba": 65536}, "circle": {"x": cx, "y": cy, "z": -9999.9, "w": -9999.9}}
        t = tt(10, 10); t["vertices"] = [vx(0, 0, -2, -2), vx(10, 0, 2, -2), vx(10, 10, 2, 2), vx(0, 10, -2, 2)]; t["indices"] = [0, 1, 2, 0, 2, 3]
        img = images.render_vector(t, 100)
        self.assertEqual(img.getpixel((50, 50))[3], 255); self.assertEqual(img.getpixel((50, 30))[3], 255)     # |xy| <= 1: a disc of radius 25 px
        self.assertEqual(img.getpixel((5, 5))[3], 0); self.assertEqual(img.getpixel((50, 20))[3], 0)            # outside the disc: not drawn

    def test_check_swap(self):
        ok = {"bundle": "ui-backgrounds_assets_.bundle", "path_id": "-123", "name": "x", "kind": "texture", "source": "a.png", "fit": "cover"}
        images.check_swap(ok)
        for bad in (dict(ok, bundle="art-x.bundle"), dict(ok, bundle="../x.bundle"), dict(ok, path_id=1), dict(ok, path_id=True), dict(ok, path_id="1e5"), dict(ok, kind="font"),
                    dict(ok, source="../a.png"), dict(ok, source="a.svg"), dict(ok, kind="svg"), dict(ok, fit="zoom"), dict(ok, extra=1)):
            with self.assertRaises(ValueError): images.check_swap(bad)
        icon = dict(ok, kind="icon", bundle="ui-icons_assets_2x.bundle", source="star.svg")
        images.check_swap(icon); images.check_swap(dict(icon, source="a.png"))
        with self.assertRaises(ValueError): images.check_swap(dict(icon, bundle="ui-icons_assets_1x.bundle"))
        self.assertEqual(images.base_name("win_small_2x"), "win_small"); self.assertEqual(images.base_name("var-efl_x3"), "var-efl")
        p = project.new("p"); p["image_swaps"] = [ok, dict(ok)]
        with self.assertRaises(ValueError): project.validate(p)                           # the same image twice


IMG = "ui-backgrounds_assets_.bundle"


def fake_apply(src, out, swaps, source_dir, touched=None):
    """Stand-in for images.apply_swaps on a JSON 'bundle': marks sheet 0 swapped with the source file's size."""
    sheets = json.loads(Path(src).read_text())
    sheets[0]["swapped"] = len((Path(source_dir) / swaps[0]["source"]).read_bytes())
    if touched is not None: touched.add(0)
    (Path(out) / Path(src).name).write_text(json.dumps(sheets))
    return True, ["fake note"], [0]


def setup_game(tmp):
    aa = Path(tmp) / "StreamingAssets/aa/StandaloneWindows64"; aa.mkdir(parents=True)
    (aa / bundles.STYLE_BUNDLES[0]).write_text(json.dumps([sheet("FigmaStyleVariables")]))
    (aa / bundles.STYLE_BUNDLES[1]).write_text(json.dumps([sheet()]))
    (aa / IMG).write_text(json.dumps([sheet("Img")])); (aa.parent / "catalog.hash").write_text("cat1")
    return aa


class Flow(unittest.TestCase):
    def tearDown(self):
        for h in list(logging.getLogger("skin_editor").handlers): logging.getLogger("skin_editor").removeHandler(h); h.close()

    def test_snapshot_build_gate_install_and_removal(self):
        with tempfile.TemporaryDirectory() as tmp, fake(), mock.patch.object(images, "apply_swaps", fake_apply):
            aa = setup_game(tmp); ws = config.Workspace(Path(tmp) / "ws"); install.snapshot_vanilla(ws, aa); ix = index_styles.build(ws)
            p = project.new("t"); (ws.images / "t").mkdir(parents=True); (ws.images / "t" / "bg.png").write_bytes(png())
            p["image_swaps"] = [{"bundle": IMG, "path_id": "5", "name": "fm27_skin_bundesliga", "kind": "texture", "source": "bg.png", "fit": "cover"}]
            project.save(ws, p)
            with self.assertRaises(RuntimeError) as c: patcher.build(p, ws, ix)
            self.assertIn("not in the vanilla snapshot", str(c.exception))
            install.add_image_bundle(ws, aa, IMG); self.assertIn(IMG, ws.vanilla_manifest()["image_files"])
            rep = patcher.build(p, ws, ix)
            self.assertTrue(rep["files"][IMG]["changed"]); self.assertEqual(rep["gate"]["fail"], []); self.assertEqual(rep["image_swaps"]["notes"], ["fake note"])
            r = install.install(ws, aa, patcher.latest_build(ws, "t"), lambda: False)
            self.assertIn(IMG, r["copied"]); self.assertEqual(json.loads((aa / IMG).read_text())[0]["swapped"], len(png()))
            self.assertEqual(install.tamper_status(ws, aa)["state"], "clean")               # our own install is not tampering
            p["image_swaps"] = []; project.save(ws, p)                                      # swap removed: the next install puts vanilla back
            rep = patcher.build(p, ws, ix); self.assertFalse(rep["files"][IMG]["changed"])
            install.install(ws, aa, patcher.latest_build(ws, "t"), lambda: False)
            self.assertNotIn("swapped", json.loads((aa / IMG).read_text())[0])

    def test_add_image_bundle_refuses_modified_or_unknown_files(self):
        with tempfile.TemporaryDirectory() as tmp, fake():
            aa = setup_game(tmp); ws = config.Workspace(Path(tmp) / "ws")
            with self.assertRaises(install.InstallError): install.add_image_bundle(ws, aa, IMG)        # no snapshot
            install.snapshot_vanilla(ws, aa)
            (aa / IMG).write_text("modified by a test")
            with self.assertRaises(install.InstallError) as c: install.add_image_bundle(ws, aa, IMG)
            self.assertIn("not the stock file", str(c.exception))
            with self.assertRaises(install.InstallError): install.add_image_bundle(ws, aa, bundles.STYLE_BUNDLES[0])
            with self.assertRaises(install.InstallError): install.add_image_bundle(ws, aa, "ui-unknown.bundle")
            (aa / IMG).write_text(json.dumps([sheet("Img")])); install.add_image_bundle(ws, aa, IMG)
            install.snapshot_vanilla(ws, aa, force=True)                                   # a new snapshot drops old image copies
            self.assertFalse((ws.vanilla / IMG).exists()); self.assertNotIn("image_files", ws.vanilla_manifest())


class Routes(unittest.TestCase):
    def test_upload_preview_remove(self):
        with tempfile.TemporaryDirectory() as tmp, mock.patch.dict(os.environ, {"FM27SE_WORKSPACE": tmp + "/ws"}), fake():
            aa = setup_game(tmp)
            app = server.App(); app.info = {"aa_dir": str(aa), "game_dir": tmp}
            install.snapshot_vanilla(app.ws, aa); project.save(app.ws, project.new("demo"))
            httpd = server.ThreadingHTTPServer(("127.0.0.1", 0), server.make_handler(app, "tok", 0)); port = httpd.server_address[1]
            th = threading.Thread(target=httpd.serve_forever, daemon=True); th.start()
            def call(path, body=None, raw=False):
                data = None if body is None else (body if raw else json.dumps(body).encode())
                req = urllib.request.Request("http://127.0.0.1:%d%s" % (port, path), data=data, headers={"X-Token": "tok", "Host": "127.0.0.1:0"})
                try: r = urllib.request.urlopen(req); return r.status, r.headers.get("Content-Type"), r.read()
                except urllib.error.HTTPError as e: return e.code, e.headers.get("Content-Type"), e.read()
            try:
                q = "/api/images/swap?project=demo&bundle=%s&path_id=-77&kind=texture&name=bg&fit=contain" % IMG
                code, _, body = call(q, png(), raw=True); self.assertEqual(code, 200, body)
                p = json.loads(body)["project"]; e = p["image_swaps"][0]
                self.assertEqual((e["path_id"], e["fit"], e["source"]), ("-77", "contain", "ui-backgrounds_assets__77.png"))
                self.assertTrue((app.ws.images / "demo" / e["source"]).is_file()); self.assertIn(IMG, app.ws.vanilla_manifest()["image_files"])
                code, ct, body = call("/api/images/source?project=demo&file=" + e["source"]); self.assertEqual((code, ct), (200, "image/png"))
                self.assertEqual(call(q.replace("kind=texture", "kind=svg"), png(), raw=True)[0], 400)            # wrong file type for the slot
                self.assertEqual(call(q, b"not an image", raw=True)[0], 400)
                self.assertEqual(call("/api/images/source?project=demo&file=../../config.json")[0], 400)
                self.assertEqual(call("/api/images/swap?project=demo&bundle=../x.bundle&path_id=1&kind=texture", png(), raw=True)[0], 400)
                code, _, body = call("/api/images/remove", {"project": "demo", "bundle": IMG, "path_id": "-77"})
                self.assertEqual(json.loads(body)["project"]["image_swaps"], []); self.assertFalse((app.ws.images / "demo" / e["source"]).exists())
            finally:
                httpd.shutdown(); httpd.server_close(); th.join(5)
                for h in list(logging.getLogger("skin_editor").handlers): logging.getLogger("skin_editor").removeHandler(h); h.close()

    def test_frontend_has_the_images_tab(self):
        html = (Path(__file__).resolve().parent.parent / "frontend" / "index.html").read_text(encoding="utf-8")
        self.assertIn('"images"', html.split("pages = [")[1].split("]")[0])
        for needle in ("/api/images/catalog", "/api/images/swap", "/api/images/thumb", "Use this file"):
            self.assertIn(needle, html)


@gamebuild.requires_build
@unittest.skipUnless((GAME / "ui-icons_assets_common.bundle").is_file() and (GAME / "ui-backgrounds_assets_1x.bundle").is_file(), "needs the game")
class RealBundles(unittest.TestCase):
    @gamebuild.requires_build
    @unittest.skipUnless((GAME / "ui-iconspriteatlases_assets_2x.bundle").is_file(), "needs the game")
    def test_icon_into_every_atlas(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:     # UnityPy keeps read bundles mapped on Windows
            out = Path(tmp); (out / "s.svg").write_bytes(SVG)
            for s, ib, ab in images.icon_bundles(GAME):
                touched = set()
                ch, notes = images.apply_icon_swaps(GAME / ab, GAME / ib, out, [{"name": "win_small", "source": "s.svg"}], out, touched)
                self.assertTrue(ch); self.assertEqual(verify_static.untouched_check(ab, GAME / ab, out / ab, touched), ([], []))
                e = images.icon_index(GAME / ib, out / ab)["win_small"]
                import UnityPy
                img = next(o.read().image for o in UnityPy.load(str(out / ab)).objects if o.path_id == e["tex_pid"])
                c = img.getpixel((round(e["x"] + e["w"] / 2), round(e["y"] + e["h"] / 2)))
                self.assertTrue(c[0] > 180 and c[1] < 60 and c[3] > 200, (s, c))       # the red disc of the test SVG at the icon's centre

    """On copies of real game bundles (the game folder is only read): the swap lands, everything else stays identical."""
    def test_texture_and_svg(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:     # UnityPy keeps read bundles mapped on Windows: deleting the copies can fail after the checks passed (a test-cleanup flake, not a fault of the code)
            src_dir, out = Path(tmp) / "src", Path(tmp) / "out"; src_dir.mkdir(); out.mkdir()
            (src_dir / "a.png").write_bytes(png(50, 50, (10, 200, 30))); (src_dir / "i.svg").write_bytes(SVG)
            for b, kind, srcf in (("ui-backgrounds_assets_1x.bundle", "texture", "a.png"), ("ui-icons_assets_common.bundle", "svg", "i.svg")):
                tgt = next(x for x in images.scan_bundle(GAME / b) if x["kind"] == kind and (kind == "svg" or x["format_id"] in images.WRITABLE))
                touched = set()
                ch, notes, done = images.apply_swaps(GAME / b, out, [{"bundle": b, "path_id": tgt["path_id"], "name": tgt["name"], "kind": kind, "source": srcf}], src_dir, touched)
                self.assertTrue(ch); self.assertEqual(verify_static.untouched_check(b, GAME / b, out / b, touched), ([], []))
                back = next(x for x in images.scan_bundle(out / b) if x["path_id"] == tgt["path_id"])
                self.assertEqual((back["w"], back["h"]), (tgt["w"], tgt["h"]))
                if kind == "texture":
                    self.assertEqual(back["format"], tgt["format"])
                    from PIL import Image
                    im = Image.open(io.BytesIO(images.thumbnail(out / b, tgt["path_id"]))).convert("RGB")
                    c = im.getpixel((im.width // 2, im.height // 2)); self.assertTrue(abs(c[1] - 200) < 12 and c[0] < 30, c)


if __name__ == "__main__":
    unittest.main()
