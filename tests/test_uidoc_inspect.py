"""Stage 5D, backend: the editable inspector of one JOINED node (uidoc.inspect) and the backend-owned validation
of a proposed edit (uidoc.classify). Every classification - evidence class, measured reach, colour route,
runtime-dependent visibility, refusal - comes from the engine, and this suite pins exactly that.

Data-gated: the configured game and an imported layout dump. The engine runs on a temporary FM27SE_WORKSPACE
(nothing writes the live workspace) and is pointed at the real workspace read-only afterwards."""
import os
import tempfile
import unittest
from pathlib import Path

COMPOSITION = "SquadComposition-Standard"


def _real_config():
    saved = os.environ.pop("FM27SE_WORKSPACE", None)
    try:
        from skin_editor import config
        return config.load()
    finally:
        if saved is not None:
            os.environ["FM27SE_WORKSPACE"] = saved


def _real_ws():
    from skin_editor import config
    return config.workspace(_real_config())


@unittest.skipUnless(_real_config().get("game_dir") and Path(str(_real_config()["game_dir"])).is_dir()
                     and (_real_ws().layout / "current.json").is_file(),
                     "needs the configured game and an imported layout dump")
class InspectorBackend(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from skin_editor import config, detect, layout_dump
        cls.tmp = tempfile.TemporaryDirectory(prefix="fm27se-5d-", ignore_cleanup_errors=True)
        real_cfg = _real_config()
        os.environ["FM27SE_WORKSPACE"] = cls.tmp.name
        try:
            from skin_editor.engine import Engine
            cls.eng = Engine()
        finally:
            os.environ.pop("FM27SE_WORKSPACE", None)
        cls.eng.ws = config.workspace(real_cfg)
        cls.eng.info = detect.describe(real_cfg["game_dir"])
        cls.join = cls.eng.uidoc_join({}, {"composition": COMPOSITION})
        # (render_pos, top bundle, top path_id) candidates: deep enough to be unique within an instance
        cls.candidates = [(pos, i["top"]["bundle"], i["top"]["path_id"])
                          for i in cls.join["instances"]
                          for pos in sorted(i["rows"]) if pos.count("/") >= 2]
        cls._cache = {}

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def _inspect(self, pos, bundle, pid):
        key = (pos, bundle, str(pid))
        if key not in self._cache:
            try:
                self._cache[key] = self.eng.uidoc_inspect({}, {"composition": COMPOSITION, "render_pos": pos,
                                                               "bundle": bundle, "path_id": pid})
            except Exception as e:
                self._cache[key] = {"error": str(e)}
        return self._cache[key]

    def _find(self, pred, limit=40):
        for pos, bundle, pid in self.candidates[:limit]:
            out = self._inspect(pos, bundle, pid)
            if "error" in out:
                continue
            if pred(out):
                return out, (pos, bundle, pid)
        return None, None

    def test_the_inspector_shows_evidence_classes_routes_and_reach(self):
        out, _at = self._find(lambda o: any(p["editable"] for p in o["properties"]))
        self.assertIsNotNone(out, "no inspected node carries an editable property")
        node = out["node"]
        self.assertTrue(node["logical_id"])
        self.assertTrue(node["locator"]["bundle"] and node["locator"]["path_id"] and node["locator"]["m_id"])
        self.assertTrue(node["bundle_sha256"], "the physical locator carries the bundle's content hash")
        props = {p["name"]: p for p in out["properties"]}
        self.assertTrue(props, "the joined node has computed properties")
        for p in props.values():
            self.assertIn(p["evidence"], ("mapped", "partial", "unmapped", "unknown"))
        editables = [p for p in props.values() if p["editable"]]
        self.assertTrue(editables, "the measured Squad tiles carry editable properties")
        self.assertTrue(out["selector"]["selector"])
        reach = out["selector"]["reach"]
        self.assertEqual(reach["measured_by"], "layout.reach (static lower bound)")
        self.assertIsInstance(reach["elements"], int)
        self.assertTrue(reach["note"].startswith("measured by layout.reach"))

    def test_a_colour_shows_both_routes_and_the_visibility_caveat_where_it_applies(self):
        out, _at = self._find(lambda o: o["colour_routes"] is not None)
        if out is None:
            self.skipTest("no inspected node's colour comes through a token")
        routes = out["colour_routes"]
        self.assertTrue(routes["through_token"]["token"].startswith("--"))
        self.assertEqual(routes["through_scoped_rule"]["reach"]["measured_by"], "layout.reach (static lower bound)")
        self.assertIn("every user of the token", routes["through_token"]["effect"])
        self.assertIn("measured above", routes["through_scoped_rule"]["effect"])
        vis = [p for p in out["properties"] if p["runtime_caveat"]]
        for p in vis:
            self.assertEqual(p["editable"], "visibility")

    def test_the_backend_refuses_a_colour_edit_without_its_route(self):
        out, at = self._find(lambda o: any(p["editable"] == "colour" for p in o["properties"]))
        if out is None:
            self.skipTest("no inspected node carries a colour property")
        prop = next(p for p in out["properties"] if p["editable"] == "colour")
        pos, bundle, pid = at
        refused = self.eng.uidoc_classify({}, {"composition": COMPOSITION, "render_pos": pos, "bundle": bundle, "path_id": pid,
                                               "kind": "SetColor", "props": {prop["name"]: {"rgb": "#112233", "a": 1.0}},
                                               "original": {"value": prop["value"], "evidence": prop["evidence"],
                                                            "provenance": {"bundle": "ui-styles_assets_default.bundle",
                                                                           "sheet": "AlwaysAppliedStyleSheet",
                                                                           "selector": out["selector"]["selector"], "occurrence": 0}}})
        self.assertIn("refused", refused)
        self.assertIn("needs its route recorded", refused["refused"])

    def test_a_classified_colour_edit_records_its_route_and_scope(self):
        out, at = self._find(lambda o: any(p["editable"] == "colour" for p in o["properties"]))
        if out is None:
            self.skipTest("no inspected node carries a colour property")
        prop = next(p for p in out["properties"] if p["editable"] == "colour")
        pos, bundle, pid = at
        reach = out["selector"]["reach"]
        res = self.eng.uidoc_classify({}, {"composition": COMPOSITION, "render_pos": pos, "bundle": bundle, "path_id": pid,
                                           "kind": "SetColor", "props": {prop["name"]: {"rgb": "#112233", "a": 1.0}},
                                           "route": {"chosen": "scoped_rule",
                                                     "reason": "the measured reach of the element's own class"},
                                           "original": {"value": prop["value"], "evidence": prop["evidence"],
                                                        "provenance": {"bundle": "ui-styles_assets_default.bundle",
                                                                       "sheet": "AlwaysAppliedStyleSheet",
                                                                       "selector": out["selector"]["selector"], "occurrence": 0}}})
        self.assertNotIn("refused", res, res.get("refused"))
        v = res["validation"]
        self.assertTrue(v["ok"])
        self.assertEqual(v["translation"]["fragment"], "scoped_rules")
        self.assertEqual(v["scope"]["elements"], reach["elements"])
        self.assertEqual(v["safety"], "scope" if reach["elements"] > 1 else "value")
        op = res["operation"]
        self.assertEqual(op["target"]["locator"]["bundle"], out["node"]["locator"]["bundle"])
        self.assertEqual(op["target"]["guard"]["type"], out["node"]["type"])

    def test_unjoined_nodes_are_refused_for_the_inspector(self):
        entries = [(pos, i["top"]["bundle"], i["top"]["path_id"]) for i in self.join["instances"]
                   for pos, r in (i.get("not_drawn") or {}).items()
                   if pos and r["state"].startswith("not_drawn:non_visual")]
        if not entries:
            self.skipTest("no not-drawn non-visual row on this composition's instances")
        pos, bundle, pid = sorted(entries)[0]
        with self.assertRaises(RuntimeError) as c:
            self.eng.uidoc_inspect({}, {"composition": COMPOSITION, "render_pos": pos, "bundle": bundle, "path_id": pid})
        self.assertIn("not drawn by the render", str(c.exception))


if __name__ == "__main__":
    unittest.main()
