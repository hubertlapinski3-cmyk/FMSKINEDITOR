"""M6 prerequisite: the editor endpoints the side panel calls (L: layouts.edit/unedit, V: tables.edit/unedit, USS and tokens: project.write_file, project.save, uss.diagnostics,
tokens.get), each exercised THROUGH RPC against the real game data, each firing exactly one `render.invalidate`, each visible in the next render."""
import json
import tempfile
import unittest
from tests import gamebuild
from pathlib import Path
from unittest import mock

from skin_editor import changes
from skin_editor.api import rpc

from test_api import close_logs, engine

AA = gamebuild.aa()                                         # the configured game folder (tests/gamebuild.py), not a typed path


@gamebuild.requires_build
@unittest.skipUnless(AA.is_dir(), "needs the game install")
class PanelEndpoints(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.addCleanup(self.tmp.cleanup)
        self.addCleanup(close_logs)
        self.addCleanup(changes.set_sink, None)
        self.e = engine(self.tmp.name)
        # Edits are validated against a vanilla snapshot and tokens against the real style index. The temporary workspace gets a small snapshot of its own (the layout bundle of the
        # Squad tiles and the two table bundles, copied from the stock game, with the owner's real manifest) and the real style index; the owner's workspace is only read.
        import shutil
        from skin_editor import config, index_styles, tables
        real = config.workspace(config.load())
        for name in ("ui-visualtreeassets_assets_gameworldvisualtreeassetpreload.bundle", tables.VIEWS_BUNDLE, tables.FACTORIES_BUNDLE):
            shutil.copy2(AA / name, self.e.ws.vanilla / name)
        shutil.copy2(real.vanilla / "manifest.json", self.e.ws.vanilla / "manifest.json")
        self.e.index = index_styles.load(real)
        # The temporary workspace has no selected game install and no snapshot: point the engine at the stock game folder and treat it as stock (the tamper rule guards against a
        # modified install, which this read-only test never makes). Everything the panel calls runs for real on the game's data.
        for target, value in (("skin_editor.engine.Engine.need_info", {"aa_dir": str(AA), "game_dir": str(AA.parents[3])}),
                              ("skin_editor.install.tamper_status", {"state": "stock", "files": {}})):
            patcher = mock.patch(target, return_value=value)
            patcher.start()
            self.addCleanup(patcher.stop)
        self.sub = self.e.events.subscribe()
        self.call("project.create_folder", {"name": "demo", "target": "native"})
        self.events()

    def call(self, method, params=None):
        r = json.loads(rpc.handle(self.e, json.dumps({"jsonrpc": "2.0", "method": method, "id": 1, "params": params or {}})))
        self.assertNotIn("error", r, r)
        return r["result"]

    def events(self):
        out = []
        while not self.sub.empty():
            ev = self.sub.get()
            if ev["type"] == "render.invalidate":
                out.append(ev["data"])
        return out

    def find(self, res, name):
        stack = list(res["tree"])
        while stack:
            x = stack.pop()
            if x["name"] == name:
                return x
            stack.extend(x["children"])

    def loans(self, **kw):
        return self.call("render.layout", dict({"name": "LoansTile_4x2"}, **kw))

    def test_the_L_editor_edits_a_layout_element_and_the_render_shows_it_once(self):
        node = self.find(self.loans(), "title area frame")
        import shutil
        owner = next(r for r in self.call("render.layouts", {"q": node["layout"], "limit": 50})["layouts"] if r["name"] == node["layout"])       # the bundle of the included base template
        if not (self.e.ws.vanilla / owner["bundle"]).is_file():
            shutil.copy2(AA / owner["bundle"], self.e.ws.vanilla / owner["bundle"])
        lay = next(r for r in self.call("layouts.list", {"q": node["layout"]})["layouts"] if r["name"] == node["layout"])
        op = {"op": "set-classes", "id": node["id"], "guard": {"type": node["type"], "name": node["name"]}, "add": ["margin-top-global-gap-regular"]}
        self.call("layouts.edit", {"project": "demo", "bundle": lay["bundle"], "name": lay["name"], "path_id": lay["path_id"], "op": op})
        ev = self.events()
        self.assertEqual([(e["reason"], e["scope"]) for e in ev], [("layout-patch", [node["layout"]])])
        self.assertIn("margin-top", self.find(self.loans(project="demo"), "title area frame")["computed"])
        self.assertNotIn("margin-top", self.find(self.loans(project="demo", skin=False), "title area frame")["computed"])          # the toggle
        self.call("layouts.unedit", {"project": "demo", "bundle": lay["bundle"], "name": lay["name"], "id": node["id"]})
        self.assertEqual([e["reason"] for e in self.events()], ["layout-patch"])
        self.assertNotIn("margin-top", self.find(self.loans(project="demo"), "title area frame")["computed"])

    def test_a_huge_layout_is_capped_by_default_and_opens_by_path_over_rpc(self):
        """M8: render.layout cuts a 5,487-element layout to about 1,000 nodes by default; `open` expands one collapsed node; max_nodes 0 asks for everything."""
        big = next(r for r in self.call("render.layouts", {"q": "DetailedPreferencesBlock", "limit": 20})["layouts"] if r["name"] == "DetailedPreferencesBlock")
        key = {"bundle": big["bundle"], "path_id": big["path_id"]}
        res = self.call("render.layout", key)
        self.assertGreater(res["truncated"]["total"], 5000)
        self.assertLessEqual(res["truncated"]["shown"], 1000)

        def stubs(top, p=""):
            out = []
            for i, n in enumerate(top):
                q = "%s/%d" % (p, i) if p else str(i)
                if n.get("collapsed"):
                    out.append((q, n))
                out += stubs(n["children"], q)
            return out
        path, _n = stubs(res["tree"])[0]
        again = self.call("render.layout", dict(key, open=[path]))
        self.assertGreater(again["truncated"]["shown"], res["truncated"]["shown"])
        self.assertIsNone(self.call("render.layout", dict(key, max_nodes=0))["truncated"])
        self.assertIsNone(self.loans()["truncated"])

    def test_the_V_editor_edits_a_table_view_and_the_placeholder_follows(self):
        views = self.call("tables.list", {"limit": 400})["views"]
        view = None
        for v in views:
            detail = self.call("tables.view", {"path_id": v["path_id"]})
            hide = next((c["id"] for c in detail["columns"] if not c["required"]), None)
            if len(detail["columns"]) >= 4 and hide:
                view = (v, hide, len(detail["columns"]))
                break
        v, hide, n = view
        self.call("tables.edit", {"project": "demo", "name": v["name"], "path_id": v["path_id"], "op": {"op": "hide-column", "column": hide}})
        self.assertEqual([(e["reason"], e["scope"]) for e in self.events()], [("table-edit", [v["name"]])])
        skin = self.call("render.table", {"path_id": v["path_id"], "project": "demo"})
        self.assertEqual(len(skin["columns"]), n - 1)
        self.assertEqual(len(self.call("render.table", {"path_id": v["path_id"], "project": "demo", "skin": False})["columns"]), n)
        self.call("tables.unedit", {"project": "demo", "name": v["name"]})
        self.assertEqual([e["reason"] for e in self.events()], ["table-edit"])
        self.assertEqual(len(self.call("render.table", {"path_id": v["path_id"], "project": "demo"})["columns"]), n)

    def test_the_USS_editor_writes_a_rule_file_and_the_render_shows_it_once(self):
        node = self.find(self.loans(), "layout-tile-interaction-button")
        sel = ".layout-tile-interaction-button-background"
        self.assertEqual(node["computed"]["background-color"]["value"], "#1E2129")
        text = "/* Rules for the game stylesheet AlwaysAppliedStyleSheet. */\n%s {\n  background-color: #00FF00;\n}\n" % sel
        diag = self.call("uss.diagnostics", {"text": text, "sheet": "AlwaysAppliedStyleSheet"})
        self.assertEqual([d for d in diag["diagnostics"] if d.get("severity") == "error"], [])
        self.call("project.new_sheet", {"project": "demo", "sheet": "AlwaysAppliedStyleSheet"})
        self.events()
        self.call("project.write_file", {"project": "demo", "path": "styles/AlwaysAppliedStyleSheet.uss", "text": text})
        ev = self.events()
        self.assertEqual([(e["reason"], e["scope"]) for e in ev], [("file", ["styles/AlwaysAppliedStyleSheet.uss"])])
        self.assertEqual(self.find(self.loans(project="demo"), "layout-tile-interaction-button")["computed"]["background-color"]["value"], "#00FF00")
        self.assertEqual(self.find(self.loans(project="demo", skin=False), "layout-tile-interaction-button")["computed"]["background-color"]["value"], "#1E2129")
        # element -> rule: the winning declaration names the project's rule, the render says which file and line it lives in, and the rule can be fetched as USS text
        res = self.loans(project="demo")
        win = self.find(res, "layout-tile-interaction-button")["computed"]["background-color"]["source"]
        self.assertEqual(win["origin"], {"kind": "project", "sheet": "AlwaysAppliedStyleSheet", "selector": sel})
        origin = next(o for o in res["origins"]["rules"] if o["selector"] == sel)
        self.assertEqual((origin["file"], origin["line"], origin["end"]), ("styles/AlwaysAppliedStyleSheet.uss", 2, 4))
        mine = self.call("render.rule", {"sheet": win["sheet"], "rule": win["rule"], "project": "demo"})
        self.assertFalse(mine["vanilla"])
        self.assertEqual((mine["origin"]["file"], mine["origin"]["line"]), ("styles/AlwaysAppliedStyleSheet.uss", 2))
        self.assertIn("background-color: #00FF00", mine["text"])
        # a game rule that also matched is read-only text with no origin
        other = next(m for m in self.find(res, "layout-tile-interaction-button")["matched"] if "origin" not in m)
        game = self.call("render.rule", {"sheet": other["sheet"], "rule": other["rule"], "project": "demo"})
        self.assertTrue(game["vanilla"])
        self.assertIsNone(game["origin"])
        self.assertIn("{", game["text"])
        # rule -> elements: the ids in the origin are the cascade's rule ids, so the editor's caret line finds the elements the rule styles
        ids = {(i["sheet"], i["rule"]) for i in origin["ids"]}
        self.assertIn((win["sheet"], win["rule"]), ids)

    def test_the_token_editor_saves_an_override_and_the_chain_endpoint_names_the_token(self):
        chain = self.call("tokens.get", {"name": "--colours-ui-soft"})
        self.assertEqual(chain["name"], "--colours-ui-soft")
        p = self.call("project.get", {"name": "demo"})
        p["token_overrides"] = [{"token": "--colours-ui-soft", "value": "#FF0000"}]
        self.call("project.save", {"project": p})
        self.assertEqual([e["reason"] for e in self.events()], ["tokens"])
        self.assertEqual(self.find(self.loans(project="demo"), "layout-tile-interaction-button")["computed"]["background-color"]["value"], "#FF0000")
        origins = self.loans(project="demo")["origins"]["tokens"]
        self.assertEqual(origins["--colours-ui-soft"]["file"], "styles/tokens.uss")             # token -> the line of the override in the project's token file
        self.assertGreater(origins["--colours-ui-soft"]["line"], 0)
        text = self.call("project.read_file", {"project": "demo", "path": "styles/tokens.uss"})["text"]
        self.assertIn("--colours-ui-soft", text.splitlines()[origins["--colours-ui-soft"]["line"] - 1])


if __name__ == "__main__":
    unittest.main()
