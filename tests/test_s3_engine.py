"""S3 of the Simple mode plan, engine side: the measured-screen count of a token and the cost of a literal swap. Counts only; no picture is returned."""
import json
import tempfile
import unittest

from skin_editor import preview, simple
from skin_editor.api import rpc
from tests.test_api import close_logs, engine
from tests.test_s1_engine import crimson_index


class FakeIndex:
    def __init__(self, hits, rgb="#112233"):
        self.defs, self.by_rgb = {}, {rgb: hits}


def hit(sel, token_def=False, a=1.0):
    return {"selectors": [sel], "token_def": token_def, "a": a}


class LiteralInfo(unittest.TestCase):
    def test_offered_only_between_one_and_fifty_copied_rules_and_token_definitions_do_not_count(self):
        self.assertEqual(simple.LITERAL_LIMIT, 50)
        r = simple.literal_info(FakeIndex([hit(".a"), hit(".b"), hit(".a"), hit(":root", True)]), "#112233", 1.0)
        self.assertEqual((r["uses"], r["selectors"], r["copied_rules"], r["offered"]), (3, 2, 3, True))
        self.assertFalse(simple.literal_info(FakeIndex([hit(".x%d" % i) for i in range(51)]), "#112233", 1.0)["offered"])
        self.assertTrue(simple.literal_info(FakeIndex([hit(".x%d" % i) for i in range(50)]), "#112233", 1.0)["offered"])
        self.assertFalse(simple.literal_info(FakeIndex([hit(":root", True)]), "#112233", 1.0)["offered"], "a colour only in token definitions copies nothing")


class LiteralAlpha(unittest.TestCase):
    def test_a_colour_shown_with_a_rounded_alpha_byte_finds_the_rules_and_returns_their_exact_alpha(self):
        ix = FakeIndex([hit(".a", a=0.3499999940395355), hit(".b", a=0.3499999940395355), hit(".c", a=0.5)], "#FFFFFF")
        r = simple.literal_info(ix, "#FFFFFF", 89 / 255)            # #FFFFFF59 as the render shows it
        self.assertEqual((r["uses"], r["a_exact"]), (2, 0.3499999940395355))
        self.assertEqual(simple.literal_info(ix, "#FFFFFF", 0.5)["uses"], 1)

    def test_the_render_overlay_applies_an_exact_swap_of_an_OPAQUE_colour_and_of_a_transparent_one(self):
        from skin_editor.render import overlay
        entry = {"rules": [{"p": [["color", "#8F8F8F", []], ["background-color", "#FFFFFF59", []], ["border-color", "#8F8F8F80", []]]}]}
        n = overlay._swap_literals(entry, {}, [[0, [0x8F, 0x8F, 0x8F, 1.0], [0, 255, 0, 1.0]], [1, [255, 255, 255, 0.3499999940395355], [255, 0, 0, 0.3499999940395355]]])
        vals = {p[0]: p[1] for p in entry["rules"][0]["p"]}
        self.assertEqual(vals["color"].upper(), "#00FF00", "an opaque exact swap applies (it never did before the fix)")
        self.assertEqual(vals["background-color"].upper(), "#FF000059")
        self.assertEqual(vals["border-color"].upper(), "#8F8F8F80", "another alpha of the same RGB is not touched by an exact swap")
        self.assertEqual(n, 2)


class TokenScreens(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True); self.addCleanup(self.tmp.cleanup); self.addCleanup(close_logs)
        self.e = engine(self.tmp.name); self.e.index = crimson_index()
        simple._screens_cache.clear()

    def call(self, m, p):
        return json.loads(rpc.handle(self.e, json.dumps({"jsonrpc": "2.0", "id": 1, "method": m, "params": p})))

    def test_the_count_is_out_of_the_shipped_models_and_is_cached_and_returns_no_picture(self):
        r = self.call("simple.token_screens", {"token": "--global-background"})["result"]
        self.assertEqual(r["of"], len(preview.models()))
        self.assertEqual(r["of"], 8)
        self.assertLessEqual(r["screens"], r["of"])
        self.assertEqual(set(r), {"token", "screens", "of", "names", "regions"}, "counts and names only")
        self.assertNotIn("image", json.dumps(r))
        self.assertIs(simple.token_screens(self.e.index, "--global-background"), simple.token_screens(self.e.index, "--global-background"))

    def test_an_unknown_token_is_refused_in_plain_words(self):
        r = self.call("simple.token_screens", {"token": "--no-such"})
        self.assertIn("not in the game's styles", r["error"]["data"]["plain"])


if __name__ == "__main__":
    unittest.main()
