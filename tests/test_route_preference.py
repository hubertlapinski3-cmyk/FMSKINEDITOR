"""Route preference (Stage 5I part 1): the project setting skin_folder|bundle, DEFAULT skin_folder.

Bundle mode: a token override edits every definition in BOTH style bundles (the common bundle's replacement is
labelled UNVERIFIED - third-party Golden Boy/Kuuvaia evidence); SetColor/SetSpacing on a joined node become a
per-declaration edit of the winning declaration carrying its expanded-tree element reach; appended scoped rules
(SetStyle/SetVisibility and colour/spacing without winning-declaration provenance) stay skin-folder-only.

Uses archived set C only (read only; every build writes into a scratch folder) and copies files (never hardlinks).
The routing table, the project projection and the built package must agree per kind."""
import unittest

from skin_editor import build5g, playops, project

from tests.test_build5g import Fixture, SETC, SQUAD, _build

TOKEN = "--pitch-tile-default-background"
COLOR_SELECTOR = ".layout-tile-tactics .layout-tile-base-container"
SPACING_SELECTOR = ".sicell"


def _target(bundle, sheet, selector, occurrence=0, field="background-color", old=None, value=None):
    from tests.test_build5g import Fixture as F
    f = F.get()
    return {"screen": "SquadScreen", "logical_id": "joined/%s" % selector,
            "locator": {"bundle": bundle, "bundle_sha256": f["identity"]["files"].get(bundle),
                        "path_id": "1", "m_id": "2"},
            "guard": {"type": "VisualElement", "name": "joined", "classes": [selector.lstrip(".").split(" ")[0]]},
            "render_pos": "0/1"}, \
           {"value": value if value is not None else old, "evidence": "directly serialized",
            "provenance": {"bundle": bundle, "sheet": sheet, "selector": selector,
                           "occurrence": occurrence, "field": field,
                           "declaration_value": old}}


def _reach(elements=1):
    return {"elements": elements, "layouts": 1, "screens": 1, "measured_by": "layout.reach (static lower bound)"}


def _style_op(kind, bundle, sheet, selector, prop, old, new, route=None, reach=None, occurrence=0):
    target, original = _target(bundle, sheet, selector, occurrence, field=prop, old=old)
    newd = {"rule": {"sheet": {"bundle": bundle, "name": sheet}, "selector": selector,
                     "props": {prop: new}, "reach": reach or _reach()}}
    if route is not None:
        newd["route"] = route
    return playops.new_operation(kind, target, newd, original=original)


def _token_op(token=TOKEN, value="#FF00FF"):
    target, _ = _target("ui-styles_assets_default.bundle", "AlwaysAppliedStyleSheet", ":root",
                        field=token, old="x")
    return playops.new_operation("ReplaceToken", target,
                                 {"token": token, "value": value,
                                  "route": {"chosen": "token", "reason": "the token is the source of the colour"}},
                                 original={"value": value, "evidence": "directly serialized",
                                           "provenance": {"bundle": "ui-styles_assets_default.bundle",
                                                          "sheet": "AlwaysAppliedStyleSheet",
                                                          "selector": ":root", "occurrence": 0, "field": token}})


def _appended_style_op():
    target, _ = _target("ui-styles_assets_default.bundle", "AlwaysAppliedStyleSheet", ".appended-test",
                        field="color")
    return playops.new_operation("SetStyle", target,
                                 {"rule": {"sheet": {"bundle": "ui-styles_assets_default.bundle",
                                                     "name": "AlwaysAppliedStyleSheet"},
                                           "selector": ".appended-test", "props": {"color": "#112233"},
                                           "reach": _reach()}})


def _session(*ops):
    return Fixture.session(*ops)


class ProjectSetting(unittest.TestCase):
    def test_default_is_bundle_and_only_an_explicit_choice_is_stored(self):
        p = project.new("route-demo", "27.1.0.2505117")
        self.assertNotIn("route_preference", p["options"])
        self.assertEqual(project.route_preference(p), "bundle")
        m = project.validate(project.migrate(p))
        self.assertEqual(project.route_preference(m), "bundle")
        project.set_route_preference(p, "skin_folder")
        self.assertEqual(p["options"]["route_preference"], "skin_folder")
        self.assertTrue(p["options"]["route_preference_explicit"])
        self.assertEqual(project.validate(project.migrate(p))["options"]["route_preference"], "skin_folder")
        project.set_route_preference(p, "bundle")
        self.assertEqual(project.to_spec(p)["token_bundles"], list(project.TOKEN_BUNDLES))
        with self.assertRaises(ValueError):
            project.set_route_preference(p, "sideways")
        p["options"]["route_preference"] = "sideways"
        with self.assertRaises(ValueError) as c:
            project.validate(p)
        self.assertIn("route_preference", str(c.exception))

    def test_automatic_values_written_by_the_first_two_5i_commits_migrate_to_unset(self):
        # project.new() in abf1dac..414990c wrote these automatically; they are not user choices.
        p = project.new("auto", "27.1.0.2505117")
        p["options"].update({"route_preference": "skin_folder", "edit_competition_sheets": False})
        m = project.migrate(p)
        self.assertNotIn("route_preference", m["options"])
        self.assertNotIn("edit_competition_sheets", m["options"])
        self.assertEqual(project.route_preference(m), "bundle")          # takes the new default
        self.assertFalse(project.edit_competition_sheets(m))
        project.set_edit_competition_sheets(p, True)
        self.assertTrue(project.edit_competition_sheets(project.migrate(p)))
        # an explicit skin_folder choice is kept
        project.set_route_preference(p, "skin_folder")
        self.assertEqual(project.route_preference(project.migrate(p)), "skin_folder")


class RouteTable(unittest.TestCase):
    def test_bundle_mode_routes_each_kind_and_carries_the_reach(self):
        color = _style_op("SetColor", "ui-styles_assets_default.bundle", "AlwaysAppliedStyleSheet",
                          COLOR_SELECTOR, "background-color", "var(%s)" % TOKEN, "#FF00FF",
                          route={"chosen": "scoped_rule", "reason": "measured single-element selector"},
                          reach=_reach(9))
        spacing = _style_op("SetSpacing", "ui-styles_assets_default.bundle", "TileStyles",
                            SPACING_SELECTOR, "margin", "4px", "8px", reach=_reach(4))
        appended = _appended_style_op()
        token = _token_op()
        self.assertEqual(playops.route_of(color, "bundle")["route"], "bundle")
        handle = playops.route_of(color, "bundle")["declaration"]
        self.assertEqual(handle["selector"], COLOR_SELECTOR)
        self.assertEqual(handle["property"], "background-color")
        self.assertEqual(handle["reach"]["elements"], 9)
        self.assertEqual(playops.route_of(spacing, "bundle")["route"], "bundle")
        self.assertEqual(playops.route_of(spacing, "bundle")["declaration"]["reach"]["elements"], 4)
        self.assertEqual(playops.route_of(appended, "bundle")["route"], "skin-folder")
        self.assertIn("appended scoped rules stay skin-folder-only", playops.route_of(appended, "bundle")["reason"])
        token_route = playops.route_of(token, "bundle")
        self.assertEqual(token_route["route"], "bundle")
        self.assertEqual(token_route["bundles"], list(playops.TOKEN_BUNDLES))
        self.assertEqual(token_route["unverified_bundles"], [playops.COMMON_TOKEN_BUNDLE])
        self.assertIn("UNVERIFIED", token_route["reason"])

    def test_skin_folder_mode_is_unchanged_even_with_winning_provenance(self):
        color = _style_op("SetColor", "ui-styles_assets_default.bundle", "AlwaysAppliedStyleSheet",
                          COLOR_SELECTOR, "background-color", "var(%s)" % TOKEN, "#FF00FF",
                          route={"chosen": "scoped_rule", "reason": "measured"})
        self.assertEqual(playops.route_of(color, "skin_folder")["route"], "skin-folder")
        skin = project.new("p", "27.1.0.2505117")
        project.set_route_preference(skin, "skin_folder")
        frags = playops.project_onto(skin, _session(color))
        self.assertEqual(frags["declaration_edits"], [])
        self.assertEqual(len(frags["scoped_rules"]), 1)


class ProjectionAndPackage(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ops = [
            _token_op(),
            _style_op("SetColor", "ui-styles_assets_default.bundle", "AlwaysAppliedStyleSheet",
                      COLOR_SELECTOR, "background-color", "var(%s)" % TOKEN, "#FF00FF",
                      route={"chosen": "scoped_rule", "reason": "measured single-element selector"},
                      reach=_reach(9)),
            _style_op("SetSpacing", "ui-styles_assets_default.bundle", "TileStyles",
                      SPACING_SELECTOR, "margin", "4px", "8px", reach=_reach(4)),
            _appended_style_op(),
        ]
        cls.session = _session(*cls.ops)
        cls.pref_project = project.new("route-bundle", "27.1.0.2505117")
        project.set_route_preference(cls.pref_project, "bundle")

    def test_projection_agrees_with_the_routing_table(self):
        frags = playops.project_onto(self.pref_project, self.session)
        self.assertEqual(len(frags["token_overrides"]), 1)
        self.assertEqual(frags["token_overrides"][0]["bundles"], list(playops.TOKEN_BUNDLES))
        self.assertEqual(frags["token_overrides"][0]["unverified_bundles"], [playops.COMMON_TOKEN_BUNDLE])
        self.assertEqual(len(frags["declaration_edits"]), 2)
        by_prop = {d["property"]: d for d in frags["declaration_edits"]}
        self.assertEqual(by_prop["background-color"]["selector"], COLOR_SELECTOR)
        self.assertEqual(by_prop["background-color"]["reach"]["elements"], 9)
        self.assertEqual(by_prop["margin"]["selector"], SPACING_SELECTOR)
        self.assertEqual(len(frags["scoped_rules"]), 1)             # the appended SetStyle
        self.assertEqual(frags["scoped_rules"][0]["selector"], ".appended-test")
        self.assertEqual(playops.project_onto(self.pref_project, self.session), frags)   # idempotent

    def test_both_style_bundles_are_built_and_every_definition_changes(self):
        f = Fixture.get()
        repo = _build(self.session, route_preference="bundle", aa_dir=SETC)
        self.assertEqual(repo["route_preference"], "bundle")
        self.assertFalse(repo.get("blocked"), repo.get("blocked"))
        built = set(repo["outputs"]["bundles"])
        self.assertIn("ui-styles_assets_default.bundle", built)
        self.assertIn(playops.COMMON_TOKEN_BUNDLE, built)
        self.assertTrue((repo["style"]["bundles"][playops.COMMON_TOKEN_BUNDLE]["common_bundle_label"] or "")
                        .startswith("UNVERIFIED"))
        for bundle in playops.TOKEN_BUNDLES:
            row = repo["style"]["bundles"][bundle]
            self.assertTrue(row["tokens"][TOKEN]["definitions"] > 0, bundle)
            self.assertTrue(row["tokens"][TOKEN]["all_changed"], (bundle, row["tokens"][TOKEN]))
        # the package carries the same bundles the routing table named
        with open(repo["outputs"]["package"], encoding="utf-8") as fh:
            package = __import__("json").load(fh)
        self.assertEqual(set(package["files"]), built)
        self.assertEqual(package["route_preference"], "bundle")
        style = package["validation"]["style_layer"]
        self.assertEqual(len(style["ui-styles_assets_default.bundle"]["declaration_edits"]), 2)
        self.assertEqual(style[playops.COMMON_TOKEN_BUNDLE]["tokens"][TOKEN]["all_changed"], True)
        # the skin folder carries only the appended rule
        self.assertTrue(repo["outputs"]["skin_folder"])
        from pathlib import Path
        skin = "\n".join(p.read_text(encoding="utf-8") for p in Path(repo["outputs"]["skin_folder"]).rglob("*.uss"))
        self.assertNotIn(TOKEN, skin)                     # the token took the bundle route
        self.assertIn(".appended-test", skin)             # the appended rule stayed on the skin route
        self.assertEqual(len(frags_for(self.session)), 2)   # the default (bundle) projection carries both

    def test_a_bundle_token_write_changes_only_the_token_definitions(self):
        from skin_editor import bundlediff, bundles, index_styles
        f = Fixture.get()
        repo = _build(_session(_token_op()), route_preference="bundle", aa_dir=SETC)
        self.assertFalse(repo.get("blocked"), repo.get("blocked"))
        for bundle in playops.TOKEN_BUNDLES:
            src, out = SETC / bundle, __import__("pathlib").Path(repo["outputs"]["built_dir"]) / bundle
            cmp_ = bundlediff.compare(src, out)
            self.assertTrue(cmp_["object"]["object_set_equal"])
            changed = {str(o.get("path_id")) for o in cmp_["object"]["changed_objects"]}
            src_sheets = {}
            for pid, name, tree in bundles.sheets(src):
                e = index_styles.sheet_entry(bundle, tree)
                if any(p[0] == TOKEN for r in e["rules"] if r.get("t") for p in r["p"]):
                    src_sheets[str(pid)] = name
            self.assertTrue(src_sheets, bundle)
            self.assertTrue(changed <= set(src_sheets), (bundle, changed, set(src_sheets)))


def frags_for(session):
    return playops.project_onto({}, session)["declaration_edits"]


class PlanAndBuildAgree(unittest.TestCase):
    def _with_project(self, value):
        f = Fixture.get()
        p = project.new("demo", "27.1.0.2505117")
        project.set_route_preference(p, value)
        project.save(f["ws"], p)
        return f

    def test_plan_and_build_report_the_same_route_for_a_skin_folder_project(self):
        f = self._with_project("skin_folder")
        s = _session(_token_op())
        try:
            planned = build5g.plan(s, identity=f["identity"], compositions=f["comps"], dump=f["dump"],
                                   project=project.load(f["ws"], "demo"))
            repo = _build(s)
            self.assertEqual(planned["route_preference"], "skin_folder")
            self.assertEqual(repo["route_preference"], "skin_folder")
            self.assertEqual(planned["operations"][0]["route"], "skin-folder")
            self.assertEqual(repo["operations"][0]["route"], "skin-folder")
            self.assertTrue(repo["outputs"]["skin_folder"])
            self.assertEqual(repo["outputs"]["bundles"], {})
        finally:
            from pathlib import Path
            p = f["ws"].projects / "demo.skin.json"
            if p.is_file():
                p.unlink()

    def test_plan_and_build_report_the_same_route_for_a_bundle_project(self):
        f = self._with_project("bundle")
        s = _session(_token_op())
        try:
            planned = build5g.plan(s, identity=f["identity"], compositions=f["comps"], dump=f["dump"],
                                   project=project.load(f["ws"], "demo"))
            repo = _build(s)
            self.assertEqual(planned["route_preference"], "bundle")
            self.assertEqual(repo["route_preference"], "bundle")
            self.assertEqual(planned["operations"][0]["route"], "bundle")
            self.assertEqual(repo["operations"][0]["route"], "bundle")
            self.assertIn(playops.COMMON_TOKEN_BUNDLE, repo["outputs"]["bundles"])
        finally:
            from pathlib import Path
            for p in (f["ws"].projects / "demo.skin.json",):
                if p.is_file():
                    p.unlink()


class SimpleModeIgnoresRouting(unittest.TestCase):
    def test_a_bundle_preference_project_still_writes_a_skin_folder_and_no_game_bundle(self):
        import hashlib
        import tempfile
        from pathlib import Path
        from skin_editor import native
        f = Fixture.get()
        p = project.new("simple-mode", "27.1.0.2505117")
        project.set_route_preference(p, "bundle")
        p["token_overrides"] = [{"token": TOKEN, "value": "#FF00FF"}]
        p["scoped_rules"] = [{"sheet": "AlwaysAppliedStyleSheet", "selector": ".simple-mode-probe",
                              "props": {"color": "#FF00FF"}}]
        before = {b: hashlib.sha256((SETC / b).read_bytes()).hexdigest() for b in playops.TOKEN_BUNDLES}
        with tempfile.TemporaryDirectory(prefix="fm27se-simple-") as tmp:
            rep = native.export(f["ws"], p, None, SETC, tmp)
            folder = Path(rep["folder"])
            self.assertTrue((folder / "tokens.uss").is_file())
            self.assertTrue((folder / "rules.uss").is_file())
            self.assertIn(TOKEN, (folder / "tokens.uss").read_text(encoding="utf-8"))
            self.assertIn(".simple-mode-probe", (folder / "rules.uss").read_text(encoding="utf-8"))
            self.assertEqual(list(folder.rglob("*.bundle")), [])       # simple mode writes no game bundle
        after = {b: hashlib.sha256((SETC / b).read_bytes()).hexdigest() for b in playops.TOKEN_BUNDLES}
        self.assertEqual(before, after)                                # no game file changed
        self.assertEqual(project.route_preference(p), "bundle")        # the setting never reaches simple mode


if __name__ == "__main__":
    unittest.main()
