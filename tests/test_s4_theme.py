"""S4 of the Simple mode plan: a theme from three colours. The role map's sources, the generator (it reproduces Crimson at Crimson's own colours), the contrast check
(a failure blocks, never adjusts), the gallery (inputs only, each passes; every fix and removal reproduces), and the engine calls. Runs without the game."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from skin_editor import native, projfmt, theme
from skin_editor.api import rpc
from tests import test_core as tc
from tests.test_api import close_logs, engine
from tests.test_s1_engine import crimson_index

RM = theme.roles()
REFS = {r: RM["ramps"][r][RM["references"][r]] for r in ("neutral", "accent", "text")}
GV = theme.recorded_game_value


def gen(b, a, t, m="dark"):
    return theme.generate(b, a, t, m)


class RoleMap(unittest.TestCase):
    def test_every_entry_is_sourced_used_and_unverified(self):
        self.assertEqual(RM["status"], "unverified")
        self.assertEqual(RM["references"], {"neutral": "n-1", "accent": "c-400", "text": "t-1"})
        for e in RM["entries"]:
            self.assertEqual(e["status"], "unverified")
            self.assertIn(e["ramp"], ("neutral", "accent", "text"))
            self.assertIn(e["step"], RM["ramps"][e["ramp"]])
            if e.get("anchor") == "none":                                 # added by an owner decision: says so, and says what is not known
                self.assertIn("owner decision", e["decision"]); self.assertIn("NOT ANCHORED", e["why"]); self.assertIn("VISIBILITY UNKNOWN", e["why"])
                continue
            self.assertGreater(e["rules"], 0, "only colour tokens some rule uses are mapped by the Crimson-ramp rule")
            self.assertEqual(e["crimson"].split()[0], RM["ramps"][e["ramp"]][e["step"]], "the entry's step has Crimson's RGB")
        self.assertEqual(RM["summary"]["entries"], len(RM["entries"])); self.assertEqual(RM["summary"]["kept"], len(RM["kept"]))
        for k in RM["kept"]:
            self.assertTrue(k["why"])
        self.assertEqual(len({e["token"] for e in RM["entries"]} & {k["token"] for k in RM["kept"]}), 0)

    def test_the_contrast_pairs_are_crimsons_own_and_the_minimum_is_four_and_a_half(self):
        self.assertEqual(len(RM["contrast_pairs"]) + len(RM["excluded_pairs"]), 43, "Crimson's 43, of which the ones excluded are listed with their reason")
        self.assertEqual(len(RM["contrast_pairs"]), 42)
        self.assertEqual(RM["contrast_minimum"], 4.5)

    def test_the_defender_badge_is_not_in_the_map_or_the_checks_and_the_record_says_why(self):
        self.assertEqual([e for e in RM["entries"] if e.get("anchor") == "none"], [], "no entry is added outside the Crimson ramps")
        self.assertEqual(RM["summary"]["added_by_decision"], 0)
        self.assertNotIn("--data-player-position-defender-foreground", {e["token"] for e in RM["entries"]})
        self.assertEqual([(x["fg"], x["bg"]) for x in RM["excluded_pairs"]], [("--data-player-position-defender-foreground", "--data-player-position-defender-background")])
        self.assertIn(".text-regular", RM["excluded_pairs"][0]["why"]); self.assertIn("one chip, one screen, one theme", RM["excluded_pairs"][0]["why"].lower())
        self.assertNotIn("--data-player-position-defender-foreground", [p["fg"] for p in RM["contrast_pairs"]])

    def test_light_is_out_and_says_why(self):
        self.assertEqual(RM["modes"], ["dark"])
        self.assertIn("light themes fail on the surfaces it keeps", RM["modes_note"])


class Generator(unittest.TestCase):
    def test_crimsons_own_colours_reproduce_crimsons_values(self):
        g = gen(REFS["neutral"], REFS["accent"], REFS["text"])
        crim = {e["token"]: e["crimson"].split()[0] for e in RM["entries"] if e.get("anchor") != "none"}
        self.assertEqual(len(crim), len(RM["entries"]), "every entry is anchored in Crimson")
        for o in g["overrides"]:
            if o["token"] not in crim:
                continue
            want = crim[o["token"]]
            self.assertLessEqual(max(abs(int(o["value"]["rgb"][i:i + 2], 16) - int(want[i:i + 2], 16)) for i in (1, 3, 5)), 1, o["token"])
            self.assertEqual(o["status"], "unverified")
        self.assertEqual(len(g["overrides"]), len(RM["entries"]))
        self.assertEqual(g["kept"], len(RM["kept"]))

    def test_the_three_inputs_drive_their_ramps(self):
        g = {o["token"]: o["value"]["rgb"] for o in gen("#0F1A24", "#2E86DE", "#E6EEF5")["overrides"]}
        self.assertEqual(g["--global-background"], "#0F1A24", "the page background is the background input")
        self.assertEqual(g["--brand-theme-primary"], "#2E86DE", "the primary accent is the accent input")
        self.assertEqual(g["--global-text-primary"], "#E6EEF5", "the primary text is the text input")

    def test_bad_inputs_and_light_are_refused(self):
        with self.assertRaises(ValueError):
            gen("red", "#2E86DE", "#E6EEF5")
        with self.assertRaises(ValueError):
            gen("#000000", "#2E86DE", "#E6EEF5", "grey")
        with self.assertRaisesRegex(ValueError, "light themes are not in this version"):
            gen("#F4F4F2", "#C2410C", "#1F1F1F", "light")


class Contrast(unittest.TestCase):
    def test_a_failure_blocks_and_is_never_adjusted_and_the_games_own_pair_is_reported_apart(self):
        inputs = ("#16142A", "#8E6CF0", "#ECEAF5")                       # Royal, removed from the gallery
        g = gen(*inputs)
        before = json.dumps(g, sort_keys=True)
        c = theme.contrast(g, GV)
        self.assertTrue(c["failures"])
        self.assertTrue(all(f["touched"] and f["ratio"] < 4.5 for f in c["failures"]))
        self.assertEqual(json.dumps(g, sort_keys=True), before, "the check does not touch the theme")
        self.assertEqual(json.dumps(gen(*inputs), sort_keys=True), before, "and generating again gives the same colours")
        self.assertEqual(c["game_failures"], [], "no pair is left failing in the game's colours")

    def test_a_text_colour_too_dark_is_refused_and_the_games_own_low_values_are_reported_as_corrected(self):
        c = theme.contrast(gen(REFS["neutral"], REFS["accent"], REFS["text"]), GV)
        self.assertEqual([x["fg"] for x in c["game_low"]], ["--status-coaching-adjective-ratings-unsuited-text"])
        self.assertTrue(c["game_low"][0]["corrected"])
        dim = theme.contrast(gen(REFS["neutral"], REFS["accent"], "#A0A0A0"), GV)
        self.assertTrue(dim["failures"], "a theme whose text is too dark for its surfaces is refused")

    def test_crimsons_own_colours_pass_every_pair_they_touch(self):
        c = theme.contrast(gen(REFS["neutral"], REFS["accent"], REFS["text"]), GV)
        self.assertEqual(c["failures"], [])
        self.assertEqual(c["checked"], 35)
        self.assertEqual(len(c["unchecked"]), 7, "white on Crimson's hue families, which a generated theme does not write")
        self.assertEqual([(x["fg"], x["game_ratio"], x["corrected"]) for x in c["game_low"]], [("--status-coaching-adjective-ratings-unsuited-text", 3.93, True)])


class Gallery(unittest.TestCase):
    def setUp(self):
        self.g = json.loads((theme.config.resource_root() / "data" / "simple" / "gallery.json").read_text(encoding="utf-8"))

    def test_every_gallery_theme_is_inputs_only_passes_and_is_not_yet_checked_in_the_game(self):
        self.assertGreaterEqual(len(self.g["themes"]), 3)
        for t in self.g["themes"]:
            self.assertEqual(set(t), {"name", "background", "accent", "text", "mode", "status"})
            self.assertEqual(t["status"], "not yet checked in the game")
            self.assertEqual(theme.contrast(gen(t["background"], t["accent"], t["text"], t["mode"]), GV)["failures"], [], t["name"])

    def test_every_removal_and_every_fix_reproduces(self):
        for r in self.g["removed"]:
            i = r["inputs"]
            if i["mode"] == "light":                                     # light is out of 1.2.0 (decision 1): it cannot even be generated now
                with self.assertRaises(ValueError):
                    gen(i["background"], i["accent"], i["text"], i["mode"])
                continue
            self.assertTrue(theme.contrast(gen(i["background"], i["accent"], i["text"], i["mode"]), GV)["failures"], r["name"] + " fails, as recorded")
        names = {t["name"]: t for t in self.g["themes"]}
        for f in self.g["fixed"]:
            old_bg = f["changed"].split()[1]
            t = names[f["name"]]
            self.assertTrue(theme.contrast(gen(old_bg, t["accent"], t["text"], t["mode"]), GV)["failures"], f["name"] + " failed before the fix")
        self.assertTrue(all(r["inputs"]["mode"] == "light" for r in self.g["removed"] if r["name"] in ("Paper", "Sky")))


def theme_index():
    """A small index that defines every token the role map writes and every game token the contrast pairs name, at the game's value the role map recorded (any colour for the rest)."""
    t = tc.sheet(); sp = tc.tp.SheetPatcher(t, tc.verify_static.EMPTY)
    names = {e["token"] for e in RM["entries"]} | set(RM["game_values"])
    for n in sorted(names):
        t["m_Rules"][0]["m_Properties"].append(tc.P(n, sp._encode(RM["game_values"].get(n, "#16181D"))))
    return tc.index(t)


class Engine(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True); self.addCleanup(self.tmp.cleanup); self.addCleanup(close_logs)
        self.e = engine(self.tmp.name); self.e.index = theme_index()
        self.skins = Path(self.tmp.name) / "skins"; self.skins.mkdir()
        patcher = mock.patch.object(native, "skins_root", lambda: self.skins); patcher.start(); self.addCleanup(patcher.stop)

    def call(self, m, p=None):
        return json.loads(rpc.handle(self.e, json.dumps({"jsonrpc": "2.0", "id": 1, "method": m, "params": p or {}})))

    def test_every_mapped_token_must_exist_in_this_builds_index_or_nothing_is_written(self):
        self.e.index = crimson_index()                                   # an index without most of the map's tokens: a different build
        g = self.call("theme.generate", {"background": "#0F1A24", "accent": "#2E86DE", "text": "#E6EEF5"})["result"]
        self.assertFalse(g["ok"]); self.assertGreater(len(g["missing"]), 0)
        r = self.call("theme.create", {"name": "ocean", "background": "#0F1A24", "accent": "#2E86DE", "text": "#E6EEF5"})
        self.assertIn("game has changed some of the colours", r["error"]["data"]["plain"])
        self.assertFalse(projfmt.is_folder(self.e.ws, "ocean"))

    def test_the_export_of_a_generated_theme_writes_its_tokens(self):
        self.assertNotIn("error", self.call("theme.create", {"name": "ocean", "background": "#0F1A24", "accent": "#2E86DE", "text": "#E6EEF5", "mode": "dark"}))
        j = self.call("native.put", {"project": "ocean"})["result"]["job"]
        res = self.call("jobs.wait", {"id": j, "timeout": 60})["result"]
        self.assertEqual(res["state"], "done", res)
        self.assertEqual(res["result"]["tokens"], len(RM["entries"]))
        self.assertIn("--global-background: #0F1A24", (self.skins / "ocean" / "tokens.uss").read_text(encoding="utf-8"))

    def test_generate_writes_nothing_and_says_it_is_unchecked(self):
        r = self.call("theme.generate", {"background": "#0F1A24", "accent": "#2E86DE", "text": "#E6EEF5", "mode": "dark"})["result"]
        self.assertEqual((r["writes"], r["keeps"], r["status"]), (len(RM["entries"]), len(RM["kept"]), "not yet checked in the game"))
        self.assertTrue(r["ok"])
        self.assertEqual(self.call("project.list")["result"], [])

    def test_create_refuses_a_failing_theme_in_plain_words_and_writes_nothing(self):
        r = self.call("theme.create", {"name": "royal", "background": "#16142A", "accent": "#8E6CF0", "text": "#ECEAF5", "mode": "dark"})
        self.assertIn("error", r)
        self.assertIn("hard to read", r["error"]["data"]["plain"])
        self.assertFalse(projfmt.is_folder(self.e.ws, "royal"))

    def test_a_light_theme_is_refused_in_plain_words(self):
        r = self.call("theme.generate", {"background": "#F4F4F2", "accent": "#C2410C", "text": "#1F1F1F", "mode": "light"})
        self.assertIn("Light themes aren't available", r["error"]["data"]["plain"])
        r = self.call("theme.create", {"name": "paper", "background": "#F4F4F2", "accent": "#C2410C", "text": "#1F1F1F", "mode": "light"})
        self.assertIn("error", r); self.assertFalse(projfmt.is_folder(self.e.ws, "paper"))

    def test_create_writes_a_passing_theme_as_a_native_folder_project_marked_unverified(self):
        r = self.call("theme.create", {"name": "ocean", "background": "#0F1A24", "accent": "#2E86DE", "text": "#E6EEF5", "mode": "dark", "keep_club_colours": False})
        self.assertNotIn("error", r, r)
        p = r["result"]["project"]
        self.assertTrue(projfmt.is_folder(self.e.ws, "ocean"))
        self.assertEqual(p["options"]["output"], "native"); self.assertIs(p["options"]["club_colours"], False)
        self.assertEqual(len(p["token_overrides"]), len(RM["entries"]))
        self.assertTrue(all("unverified" in o.get("note", "") for o in p["token_overrides"]))
        self.assertEqual(r["result"]["status"], "not yet checked in the game")

    def test_the_gallery_comes_from_the_same_generator_with_its_results(self):
        r = self.call("theme.gallery")["result"]["themes"]
        self.assertEqual([t["name"] for t in r], [t["name"] for t in theme.gallery()])
        self.assertTrue(all(t["status"] == "not yet checked in the game" for t in r))


if __name__ == "__main__":
    unittest.main()
