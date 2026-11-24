"""ST1 part A: the custom_layout route in the Playground build routing: which operations are buildable on it (only what is proven in the game through the JSON), what stays a candidate
and why, the project setting, the warnings, and the files a build writes (archived stock set C, scratch folders only)."""
import copy
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from skin_editor import build5g, custom_layouts as cl, playops, project
from tests.test_build5g import SETC, SQUAD, Fixture, _build

TILES = "ui-tileslayouts_assets_all.bundle"
PROFILE = "PlayerReportOverviewComposition-Large"
BUILDABLE = ("SetCellMaxSize", "ResizeNode", "SwapTile", "MoveNode", "AddCell", "SetOptionalSlots")


def slot_op(new):
    f = Fixture.get()
    target = {"screen": SQUAD, "logical_id": "%s|optional:%s" % (SQUAD, new.get("element_id") or "order"),
              "locator": {"bundle": TILES, "bundle_sha256": f["identity"]["files"][TILES], "path_id": "4181126630784745451"},
              "guard": {"type": "GridComposition", "name": SQUAD, "classes": []}}
    return playops.new_operation("SetOptionalSlots", target, new)


def remove_loans():
    return slot_op({"op": "remove-slot", "composition": SQUAD, "direction": "m_bottom", "element_id": "Loans"})


def add_happiness_slot(y=4):
    return slot_op({"op": "add-slot", "composition": SQUAD, "direction": "m_bottom", "element_id": "Happiness",
                    "description": {"path_id": "8895524265953504165", "config_index": 3}, "location": {"x": 16, "y": y, "width": 4, "height": 2}})


def swap_tile(comp, element, name, size):
    f = Fixture.get()
    c = Fixture.cell(comp, next(c["cell_index"] for c in f["dump"]["cells"] if c["composition"] == comp and c["element_id"] == element))
    target = {"screen": comp, "logical_id": "%s|host:%s@%d" % (comp, element, c["cell_index"]),
              "locator": {"bundle": TILES, "bundle_sha256": f["identity"]["files"][TILES], "path_id": f["comps"][comp]["path_id"]},
              "guard": {"type": "Host", "name": element, "classes": []},
              "cell": {"composition": comp, "cell_index": c["cell_index"], "cell_element_id": element}}
    return playops.new_operation("SwapTile", target, {"tile": {"name": name, "size": {"x": size[0], "y": size[1]}}})


def max_op(comp, element, w, h):
    return playops.cell_max_size_operation(Fixture.get()["dump"], comp, element, w, h)


def plan(session, **kw):
    f = Fixture.get()
    return build5g.plan(session, identity=f["identity"], compositions=f["comps"], dump=f["dump"], **kw)


class Setting(unittest.TestCase):
    def test_layout_route_defaults_to_custom_layout_and_only_an_explicit_choice_counts(self):
        p = project.new("p", "27.1.0")
        self.assertEqual(project.layout_route(p), "custom_layout")
        self.assertEqual(project.route_preference(p), project.DEFAULT_ROUTE_PREFERENCE)        # styles and pictures keep their own setting
        project.set_layout_route(p, "bundle")
        self.assertEqual(project.layout_route(p), "bundle")
        with self.assertRaises(ValueError):
            project.set_layout_route(p, "skin_folder")


class Routing(unittest.TestCase):
    def test_every_proven_kind_is_buildable_with_its_evidence_and_nothing_else_is(self):
        self.assertEqual(sorted(playops.PROVEN_ON_JSON), sorted(BUILDABLE))
        ops = {"MoveNode": Fixture.op("MoveNode", SQUAD, 0, {"x": 16, "y": 4, "w": 4, "h": 2}), "ResizeNode": Fixture.op("ResizeNode", SQUAD, 0, {"x": 16, "y": 8, "w": 4, "h": 4}),
               "SetCellMaxSize": max_op(PROFILE, "FItness", 6, 4), "SwapTile": swap_tile(PROFILE, "Happiness", "TacticalEffectiveness", (2, 2)),
               "AddCell": Fixture.op("AddCell", SQUAD, 0, {"x": 16, "y": 10, "w": 4, "h": 4})}
        for kind, op in ops.items():
            r = playops.route_of(op, layout_route="custom_layout")
            self.assertEqual(r["route"], "custom_layout", kind)
            self.assertIn(playops.PROVEN_ON_JSON[kind], r["reason"])
        self.assertEqual(playops.route_of(add_happiness_slot(), layout_route="custom_layout")["route"], "custom_layout")
        self.assertEqual(playops.route_of(remove_loans(), layout_route="custom_layout")["route"], "custom_layout")

    def test_slot_add_remove_reorder_stay_candidates_on_this_route(self):
        reorder = slot_op({"op": "reorder-slot", "composition": SQUAD, "direction": "m_bottom", "order": ["Loans", "SquadHierachy", "MedicalCentre"]})
        r = playops.route_of(reorder, layout_route="custom_layout")
        self.assertEqual((r["route"], r["reason"]), ("blocked", "SetOptionalSlots reorder-slot is proven on the bundle route only"))
        for session in (Fixture.session(add_happiness_slot()), Fixture.session(remove_loans()), Fixture.session(reorder)):
            row = plan(session, layout_route="custom_layout")["operations"][0]
            self.assertTrue(row["refused"], row)
            self.assertIn("proven on the bundle route only", row["reason"])

    def test_a_replace_is_buildable_and_the_bundle_route_is_unchanged(self):
        s = Fixture.session(remove_loans(), add_happiness_slot())
        p = plan(s, layout_route="custom_layout")
        self.assertEqual([(r["route"], r["refused"]) for r in p["operations"]], [("custom_layout", False)] * 2)
        self.assertEqual(p["custom_layout_files"], [SQUAD])
        b = plan(s, layout_route="bundle")
        self.assertEqual([r["route"] for r in b["operations"]], ["bundle", "bundle"])

    def test_the_plan_names_the_route_and_reason_of_every_operation_and_the_files(self):
        s = Fixture.session(Fixture.op("MoveNode", SQUAD, 0, {"x": 16, "y": 4, "w": 4, "h": 2}),
                            Fixture.op("ReplaceToken", new={"token": "--a", "value": "#fff"}))
        p = plan(s, layout_route="custom_layout", route_preference="skin_folder")
        rows = {r["kind"]: r for r in p["operations"]}
        self.assertEqual(rows["MoveNode"]["route"], "custom_layout")
        self.assertEqual(rows["MoveNode"]["custom_layout_file"], SQUAD)
        self.assertEqual(rows["ReplaceToken"]["route"], "skin-folder")             # styles keep their current route
        self.assertEqual(p["layout_route"], "custom_layout")
        self.assertEqual(p["custom_layout_files"], [SQUAD])

    def test_a_superseded_move_is_history_not_a_refusal(self):
        """The Playground records every gesture; the newest move of a cell supersedes the older one. The build must route the effective one and not be blocked by the history."""
        s = playops.new_session("demo", SQUAD)
        first, second = Fixture.op("MoveNode", SQUAD, 0, {"x": 16, "y": 10, "w": 4, "h": 2}), Fixture.op("MoveNode", SQUAD, 0, {"x": 16, "y": 12, "w": 4, "h": 2})
        playops.add(s, first)
        playops.add(s, second)
        p = plan(s, layout_route="custom_layout")
        self.assertEqual([r["id"] for r in p["operations"]], [second["id"]])
        self.assertEqual(p["refusals"], [])
        self.assertEqual([x["id"] for x in p["superseded"]], [first["id"]])
        self.assertTrue(p["routable"])

    def test_customised_screens_warn_on_a_bundle_edit_and_need_a_replace_confirmation_on_this_route(self):
        s = Fixture.session(Fixture.op("MoveNode", SQUAD, 0, {"x": 16, "y": 4, "w": 4, "h": 2}))
        b = plan(s, layout_route="bundle", customised=[SQUAD])
        self.assertIn("will not show", b["operations"][0]["warning"])
        self.assertEqual(b["warnings"][0]["kind"], "MoveNode")
        self.assertEqual(plan(s, layout_route="bundle", customised=["Other"])["warnings"], [])
        c = plan(s, layout_route="custom_layout", customised=[SQUAD])
        self.assertTrue(c["operations"][0]["replaces_user_file"])
        self.assertEqual(c["warnings"], [])
        self.assertEqual(c["customised_in_game"], [SQUAD])


@unittest.skipUnless((SETC / TILES).is_file(), "needs archived stock set C")
class BuildWritesFiles(unittest.TestCase):
    def built(self, *ops, **kw):
        repo = _build(Fixture.session(*ops), layout_route="custom_layout", **kw)
        folder = Path(repo["outputs"]["built_dir"]) / "custom-layouts"
        return repo, folder

    def expected(self, comp, fn):
        tt, objs = cl.load_composition(SETC / TILES, comp)
        obj = cl.generate(tt, objs)
        fn(obj, tt, objs)
        return cl.dumps(obj)

    def test_no_bundle_is_written_and_the_package_lists_the_file(self):
        repo, folder = self.built(Fixture.op("MoveNode", SQUAD, 0, {"x": 16, "y": 10, "w": 4, "h": 2}))
        self.assertEqual(repo["outputs"]["bundles"], {})
        self.assertFalse((Path(repo["outputs"]["built_dir"]) / TILES).exists())
        pkg = json.loads(Path(repo["outputs"]["package"]).read_text(encoding="utf-8"))
        self.assertEqual([f["name"] for f in pkg["custom_layouts"]], [SQUAD])
        self.assertEqual(pkg["custom_layouts"][0]["sha256"], hashlib.sha256((folder / SQUAD).read_bytes()).hexdigest())
        self.assertTrue((Path(repo["outputs"]["built_dir"]) / "custom-layouts.json").is_file())

    def test_move_resize_max_size_are_exact(self):
        repo, folder = self.built(Fixture.op("MoveNode", SQUAD, 0, {"x": 16, "y": 10, "w": 4, "h": 2}))         # Atmosphere moved to y10, size untouched
        want = self.expected(SQUAD, lambda o, *_: cl.set_location(o, "Atmosphere", 16, 10, 4, 2))
        self.assertEqual((folder / SQUAD).read_bytes(), want)
        big = Fixture.op("ResizeNode", SQUAD, 0, {"x": 16, "y": 8, "w": 4, "h": 4})
        big["target"]["cell"]["max_size"] = {"x": 4, "y": 4}
        repo2, folder2 = self.built(big)                                                                      # test C's edit
        want2 = self.expected(SQUAD, lambda o, *_: (cl.set_location(o, "Atmosphere", 16, 8, 4, 4), cl.set_max_size(o, "Atmosphere", 4, 4)))
        self.assertEqual((folder2 / SQUAD).read_bytes(), want2)

    def test_add_cell_and_slot_replace_and_swap_tile_are_exact_and_deterministic(self):
        add = Fixture.op("AddCell", SQUAD, 0, {"x": 16, "y": 10, "w": 4, "h": 4})
        add["target"]["cell"].update({"cell_index": 5, "cell_element_id": "Happiness", "description": {"path_id": "8895524265953504165", "config_index": 2}})
        repo, folder = self.built(add)
        want = self.expected(SQUAD, lambda o, tt, objs: cl.add_cell(o, "Happiness", cl.description_cell_by_ref(objs, "8895524265953504165", 2), (16, 10, 4, 4)))
        self.assertEqual((folder / SQUAD).read_bytes(), want)                                                 # = JX X2's file
        repo2, folder2 = self.built(remove_loans(), add_happiness_slot(4))
        want2 = self.expected(SQUAD, lambda o, tt, objs: cl.set_slots(o, "m_bottom", [("SquadHierachy", None, (16, 0)), ("MedicalCentre", None, (16, 2)),
                                                                                       ("Happiness", cl.description_cell_by_ref(objs, "8895524265953504165", 3), (16, 4))]))
        self.assertEqual((folder2 / SQUAD).read_bytes(), want2)                                               # = JX X3's file
        repo3, folder3 = self.built(swap_tile(PROFILE, "Happiness", "TacticalEffectiveness", (2, 2)))
        want3 = self.expected(PROFILE, lambda o, tt, objs: cl.swap_cell(o, "Happiness", cl.description_cell_in_set(tt, objs, "TacticalEffectiveness", (2, 2))))
        self.assertEqual((folder3 / PROFILE).read_bytes(), want3)
        again, folder4 = self.built(swap_tile(PROFILE, "Happiness", "TacticalEffectiveness", (2, 2)))
        self.assertEqual((folder4 / PROFILE).read_bytes(), (folder3 / PROFILE).read_bytes())

    def test_a_tile_outside_the_composition_tile_set_is_refused(self):
        with self.assertRaises(RuntimeError):
            self.built(swap_tile(PROFILE, "Happiness", "NoSuchTile", (2, 2)))

    def test_the_bundle_route_still_builds_a_bundle_when_chosen(self):
        repo = _build(Fixture.session(Fixture.op("MoveNode", SQUAD, 0, {"x": 16, "y": 10, "w": 4, "h": 2})), layout_route="bundle")
        self.assertIn(TILES, repo["outputs"]["bundles"])
        self.assertEqual(repo["custom_layouts"]["files"], [])


if __name__ == "__main__":
    unittest.main()
