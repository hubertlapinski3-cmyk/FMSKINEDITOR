"""S6 of the Simple mode plan: a native project's picture swaps are drawn in the offline render exactly where the native export puts them (the export's images.uss rules,
the user's own files). Runs without the game: the game's icon classes and catalogue are stand-ins."""
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from PIL import Image

from skin_editor import native, project as project_mod, projfmt
from skin_editor.render import overlay
from skin_editor.render.assets import Drawn, apply_assets
from tests.test_api import close_logs, engine

CLASSES = {("icon", "tick_small"): ["ui-concepts-tick_small"], ("svg", "77"): ["svg-flag", "svg-flag-alt"]}


def project_with_pictures(ws, name="pics", output="native"):
    p = project_mod.new(name)
    p["options"]["output"] = output
    projfmt.write(ws, p)
    d = project_mod.images_dir(ws, name); d.mkdir(parents=True, exist_ok=True)
    Image.new("RGBA", (16, 16), (255, 0, 160, 255)).save(d / "icon.png")
    Image.new("RGB", (32, 18), (20, 160, 90)).save(d / "wall.jpg")
    p = project_mod.load(ws, name)
    p["image_swaps"] = [
        {"bundle": "ui-icons_assets_2x.bundle", "path_id": "5", "name": "tick_small", "kind": "icon", "source": "icon.png", "fit": "cover"},
        {"bundle": "ui-backgrounds_assets_.bundle", "path_id": "9", "name": "fm27_skin_wall", "kind": "texture", "source": "wall.jpg", "fit": "cover", "where": ["main-screens", "report-pages"]},
        {"bundle": "ui-icons_assets_2x.bundle", "path_id": "6", "name": "placed_in_code", "kind": "icon", "source": "icon.png", "fit": "cover"},
    ]
    project_mod.save(ws, project_mod.validate(project_mod.migrate(p)))
    return project_mod.load(ws, name)


class Rules(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True); self.addCleanup(self.tmp.cleanup); self.addCleanup(close_logs)
        self.e = engine(self.tmp.name); self.ws = self.e.ws
        self.p = project_with_pictures(self.ws)
        self.dir = project_mod.images_dir(self.ws, "pics")

    def test_the_rules_are_the_native_exports_own(self):
        rules, files, skipped = overlay.image_rules(self.p, CLASSES, self.dir)
        sels = [s for s, _ in rules]
        self.assertIn(".ui-concepts-tick_small", sels)
        self.assertIn(", ".join(native.PLACES["main-screens"][1]), sels)
        self.assertIn(", ".join(native.PLACES["report-pages"][1]), sels)
        self.assertEqual(files, {"images/tick_small.png": "icon.png", "images/fm27_skin_wall.jpg": "wall.jpg"}, "a JPG wallpaper keeps .jpg, read from its bytes, as the export does")
        self.assertEqual(len(skipped), 1); self.assertIn("placed_in_code", skipped[0])

    def test_the_overlay_rules_equal_the_images_uss_the_export_writes(self):
        skins = Path(self.tmp.name) / "skins"
        with mock.patch("skin_editor.images.icon_classes", lambda aa: CLASSES), \
             mock.patch("skin_editor.images.catalog", lambda ws, aa: [{"bundle": "ui-icons_assets_2x.bundle", "path_id": "5", "w": 32, "h": 32}]):
            rep = native.export(self.ws, self.p, None, "unused", skins)
        uss = (skins / "pics" / "images.uss").read_text(encoding="utf-8")
        exported = overlay._parse_raw(uss.split("*/", 1)[-1])
        mine, files, _ = overlay.image_rules(self.p, CLASSES, self.dir)
        self.assertEqual(sorted(map(repr, exported)), sorted(map(repr, mine)))
        for fn in files:
            self.assertTrue((skins / "pics" / fn).is_file(), fn)
        self.assertEqual(rep["own"]["images"], 2)

    def test_only_a_native_project_gets_them_in_the_render_and_the_not_applied_list_says_so(self):
        class Bank:
            def entry(self, b, n):
                return {"bundle": b, "name": n, "rules": []}
        imgs = {"classes": CLASSES, "dir": self.dir}
        sheets, _ = overlay.build_sheets(Bank(), self.p, order=[("b", "s", "")], images=imgs)
        author = sheets[-1].name if hasattr(sheets[-1], "name") else None
        self.assertTrue(author.endswith("(project)"))
        self.assertEqual(overlay.not_applied(self.p), ["class renames", "font swaps"])
        bundles = dict(self.p, options=dict(self.p["options"], output="bundles"))
        self.assertEqual(overlay.not_applied(bundles), ["class renames", "image and font swaps"])
        self.assertNotEqual(overlay.project_hash(self.p), overlay.project_hash(dict(self.p, image_swaps=[])), "a picture change re-renders")


class Catalogue(unittest.TestCase):
    def test_simple_offers_wallpapers_and_class_drawn_icons_and_counts_the_rest(self):
        from skin_editor import simple
        rows = [{"kind": "texture", "bundle": "b", "path_id": 1, "name": "fm27_skin_default"}, {"kind": "texture", "bundle": "b", "path_id": 2, "name": "start_screen_x"},
                {"kind": "icon", "bundle": "i", "path_id": 5, "name": "tick_small"}, {"kind": "icon", "bundle": "i", "path_id": 6, "name": "placed_in_code"},
                {"kind": "svg", "bundle": "s", "path_id": 77, "name": "flag"}, {"kind": "svg", "bundle": "s", "path_id": 78, "name": "nope"}]
        c = simple.picture_catalog(rows, CLASSES)
        self.assertEqual(c["counts"], {"wallpapers": 2, "icons": 2, "left_out": 2})
        self.assertEqual([r["name"] for r in c["rows"] if r["kind"] == "icon"], ["tick_small", "flag"])
        self.assertEqual(next(r for r in c["rows"] if r["name"] == "start_screen_x")["where_default"], ["start-screen"])
        self.assertEqual(set(c["places"]), set(native.PLACES))
        self.assertEqual(set(c["look_at"]), {"main-screens"}, "only the place a measured layout shows")
        self.assertTrue(all(c["look_at"][k]["name"] for k in c["look_at"]))


class Drawing(unittest.TestCase):
    def test_a_url_the_project_holds_is_drawn_from_the_users_file_and_others_are_left_alone(self):
        with tempfile.TemporaryDirectory() as t:
            f = Path(t) / "mine.png"; Image.new("RGBA", (4, 4), (1, 2, 3, 255)).save(f)
            node = {"computed": {"background-image": {"value": 'url("images/tick_small.png")', "status": "partial"}}, "children": [
                {"computed": {"background-image": {"value": 'url("images/other.png")', "status": "partial"}}, "children": []}]}
            counts = apply_assets([node], resolver=None, layout_bundle="x", sheet_bundles={}, drawn=Drawn(None), project_files={"images/tick_small.png": str(f)})
            a = node["assets"]["background-image"]
            self.assertTrue(a["project"]); self.assertTrue(a["data_url"].startswith("data:image/png;base64,"))
            self.assertEqual(node["computed"]["background-image"]["status"], "mapped")
            self.assertIn("your picture", node["computed"]["background-image"]["note"])
            self.assertNotIn("assets", node["children"][0])
            self.assertEqual(counts["project_images"], 1)


if __name__ == "__main__":
    unittest.main()
