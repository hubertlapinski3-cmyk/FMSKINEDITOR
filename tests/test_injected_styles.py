"""Unit tests for SKIN-RR2 Part C: Injected styles (AlwaysAppliedStyleSheet) + skin import."""
import copy
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from skin_editor import config, native, projfmt, project as project_mod, token_patch as tp
from skin_editor.api import methods
from skin_editor.engine import Engine


class TestInjectedStyles(unittest.TestCase):
    def test_rpcs_registered(self):
        m = methods.methods()
        for name in ("styles.injected_get", "styles.injected_save", "styles.import_from_skin", "skin.style_definitions"):
            self.assertIn(name, m)

    def test_save_import_and_export_routes(self):
        with tempfile.TemporaryDirectory() as tmp:
            ws = config.Workspace(Path(tmp) / "ws")
            p = project_mod.new("demo", "27.1")
            projfmt.write(ws, p)

            e = Engine.__new__(Engine)
            e.ws = ws
            e.index = None
            e.info = {"aa_dir": tmp}

            # 1. Save custom USS rules + :root variable targeting AlwaysAppliedStyleSheet
            uss = ":root {\n    --rr-accent: #3B8FE1;\n}\n.rr-card-header {\n    background-color: var(--rr-accent);\n    padding: 8px;\n}\n"
            res = e.styles_injected_save({}, {"project": "demo", "text": uss})
            self.assertEqual(res["problems"], [])
            inj = res["injected"]
            self.assertEqual(inj["sheet"], "AlwaysAppliedStyleSheet")
            self.assertEqual([c["name"] for c in inj["classes"]], ["rr-card-header"])
            self.assertEqual([v["name"] for v in inj["variables"]], ["--rr-accent"])

            # 2. Import class + variable from an inspected skin tagged with source
            fake_defs = {
                "skin_dir": str(Path(tmp) / "sample-skin"),
                "sheet": "AlwaysAppliedStyleSheet",
                "source": {"name": "Sample-Skin", "version": "1.0.2", "label": "Sample-Skin v1.0.2"},
                "personal_use_notice": "Personal use only",
                "variables_total": 1,
                "rules_total": 1,
                "variables": [{"name": "--sample-surface", "value": "#123456", "is_new": True, "uss_text": ":root { --sample-surface: #123456; }"}],
                "rules": [{"selector": ".sample-imported-pill", "classes": ["sample-imported-pill"], "props": {"background-color": "#123456", "border-radius": "6px"}, "is_new": True}],
            }
            fake_skin_dir = Path(tmp) / "sample-skin"
            fake_skin_dir.mkdir()
            with mock.patch("skin_editor.skin_diff.read_skin_style_definitions", return_value=fake_defs):
                imp_v = e.styles_import_from_skin({}, {"project": "demo", "folder": str(fake_skin_dir), "kind": "variable", "name": "--sample-surface"})
                imp_c = e.styles_import_from_skin({}, {"project": "demo", "folder": str(fake_skin_dir), "kind": "class", "name": "sample-imported-pill"})
            self.assertIn("author", imp_v["notice"].lower())
            self.assertIn("author", imp_c["notice"].lower())

            inj2 = imp_c["injected"]
            cls_entry = next(c for c in inj2["classes"] if c["name"] == "sample-imported-pill")
            self.assertEqual(cls_entry["source"], {"skin": "Sample-Skin", "version": "1.0.2"})
            var_entry = next(v for v in inj2["variables"] if v["name"] == "--sample-surface")
            self.assertEqual(var_entry["source"], {"skin": "Sample-Skin", "version": "1.0.2"})

            # 3. Export via native route
            loaded = project_mod.load(ws, "demo")
            dest = Path(tmp) / "native_out"
            rep = native.export(ws, loaded, None, tmp, dest, skin_id="demo-native")
            rules_uss = (Path(rep["folder"]) / "rules.uss").read_text(encoding="utf-8")
            self.assertIn("--sample-surface", rules_uss)
            self.assertIn(".sample-imported-pill", rules_uss)
            self.assertIn(".rr-card-header", rules_uss)

            # 4. Export via bundle route (SheetPatcher on AlwaysAppliedStyleSheet typetree)
            spec = project_mod.to_spec(loaded)
            sheet_tree = {"m_Name": "AlwaysAppliedStyleSheet", "m_Rules": [], "colors": [], "dimensions": [], "floats": [], "strings": []}
            sp = tp.SheetPatcher(copy.deepcopy(sheet_tree), spec)
            for rule in spec["append_rules_by_sheet"]["AlwaysAppliedStyleSheet"]:
                sp.append_rule(rule)
            self.assertGreaterEqual(sp.count_appended, 3)
            all_prop_names = {
                p.get("m_CustomName") or tp.INV_PROP.get(p.get("m_Id"))
                for r in sp.t["m_Rules"]
                for p in r.get("m_Properties", [])
            }
            all_sel_vals = {
                pt["m_Value"]
                for r in sp.t["m_Rules"]
                for cs in r.get("m_ComplexSelectors", [])
                for s in cs.get("m_Selectors", [])
                for pt in s.get("m_Parts", [])
            }
            self.assertIn("--sample-surface", all_prop_names)
            self.assertIn("--rr-accent", all_prop_names)
            self.assertIn("sample-imported-pill", all_sel_vals)
            self.assertIn("rr-card-header", all_sel_vals)


if __name__ == "__main__":
    unittest.main()
