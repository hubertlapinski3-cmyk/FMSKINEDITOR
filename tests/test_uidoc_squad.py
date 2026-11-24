"""Step 2/3 acceptance (the finding-5 gate): the UiDocument build GENERALISED to SquadComposition-Standard, on
bundle set C only, with the (bundle, path_id, m_Id) join between the render nodes and the UiDocument nodes.

Acceptance (owner order of 2026-11-18): the independently collected participating set and the dependency graph
agree in BOTH DIRECTIONS on Squad Standard; identity uniqueness is counted; C is the only build used; the join
counts joined / not drawn / unmatched separately and keeps an explicit not-drawn state for roots, non-visual
components and content past the render depth.

Offline and read only: the archived set-C bundles and the C layout dump; scratch caches in a TemporaryDirectory;
no game file is touched. Skipped when they are not on this machine."""
import hashlib
import json
import os
import tempfile
import unittest
from pathlib import Path

from skin_editor import layout_dump
from skin_editor.uidoc import Source, build_document
from skin_editor.uidoc.inventory import collect
from skin_editor.uidoc.model import ROOT

ARCHIVE = Path(os.environ.get("UIDOC_ARCHIVE", r"__absent_fixture_path__"))
SETC = Path(os.environ.get("UIDOC_C_AA") or (next(iter(sorted(ARCHIVE.glob("set-C-*"))), Path("missing")) / "StandaloneWindows64"))
C_DUMP = Path(os.environ.get("UIDOC_C_DUMP", r"__absent_fixture_path__"))
COMPOSITION = "SquadComposition-Standard"
KINDS = {"layouts": "layout", "tiles": "tile", "templates": "template", "stylesheets": ("stylesheet", "inline_sheet"), "rules": "rule", "tokens": "token",
         "hard_coded_colours": "hard_coded_colour", "fonts": "font", "images": "image", "compositions": "composition", "bundles": "bundle",
         "ui_elements": "physical_ui_element", "placement_bindings": "placement_binding", "serialized_references": "serialized_asset_reference", "panels": "panel"}


@unittest.skipUnless(SETC.is_dir() and (SETC / "ui-tileslayouts_assets_all.bundle").is_file() and C_DUMP.is_file(),
                     "needs the archived set-C bundles and the C layout dump")
class SquadStandardAcceptance(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(prefix="fm27se-squad-accept-")
        dc, _raw = layout_dump.read_file(C_DUMP)
        from skin_editor.render.service import Renderer
        cls.rd = Renderer(str(SETC), str(Path(cls.tmp.name) / "cache"), None)
        # the build identity comes from set C's own MANIFEST.json (the archive's record), not from the dump's meta
        cls.manifest = json.loads((ARCHIVE / SETC.parent.name / "MANIFEST.json").read_text(encoding="utf-8-sig")) \
            if (SETC.parent / "MANIFEST.json").is_file() else \
            json.loads((SETC.parent / "MANIFEST.json").read_text(encoding="utf-8-sig"))
        cls.catalog_hash = cls.manifest["catalog_hash"]
        cls.label = {"game_build": "27.1.0.2505117", "status": "set C verified against MANIFEST.json",
                     "label_source": "set C MANIFEST.json (read only)", "folder_catalog_hash": cls.catalog_hash}
        cls.src = Source(cls.rd.layouts)                # one source: the build stamps the build identity on it
        cls.doc = build_document(cls.src, dc, COMPOSITION, (1600, 900), renderer=cls.rd, label=cls.label)
        cls.independent = collect(cls.src, dc, COMPOSITION, cls.rd)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_the_participating_set_and_the_graph_agree_in_both_directions(self):
        for category, kind in KINDS.items():
            k = kind if isinstance(kind, tuple) else (kind,)
            actual = {nid for nid, info in self.doc.dependencies.nodes.items() if info.get("kind") in k}
            expected = set(self.independent.get(category, []))
            self.assertEqual(actual - expected, set(), "%s: graph item outside the independent set" % category)
            self.assertEqual(expected - actual, set(), "%s: independent item unreachable in the graph" % category)

    def test_identity_uniqueness_is_counted(self):
        uniq = self.doc.composition["identity_uniqueness"]
        self.assertEqual(uniq["layouts"], 19)                       # the closure's layouts were all scanned
        self.assertEqual(uniq["layouts_with_duplicate_m_id"], 0)    # and every m_Id is unique within its serialization
        self.assertEqual(uniq["duplicate_occurrences"], 0)
        self.assertNotIn("IDENTITY_COLLISION", {g.code for g in self.doc.diagnostics})

    def test_c_is_the_only_build_used(self):
        scheme = self.doc.identity_scheme
        self.assertEqual(scheme["game_build_label"], "27.1.0.2505117")
        self.assertEqual(scheme["catalog_hash"], self.catalog_hash)
        self.assertEqual(scheme["build_identity_source"], "set C MANIFEST.json (read only)")
        for bundle, h in scheme["bundle_hashes"].items():
            f = SETC / bundle
            self.assertTrue(f.is_file(), bundle)
            self.assertEqual(h, hashlib.sha256(f.read_bytes()).hexdigest(), bundle)
            recorded = (self.manifest["bundles"].get(bundle) or {}).get("sha256")
            self.assertEqual(recorded, h, "the archive MANIFEST records the same hash for %s" % bundle)
        text = json.dumps(scheme)
        self.assertNotIn("dfa1892e", text)                          # no B-era identity anywhere in the document

    def test_the_join_counts_joined_not_drawn_and_unmatched_separately(self):
        join = self.doc.composition["join"]
        nodes = list(self.doc.all_nodes())
        drawn = [n for n in nodes if n.computed_style is not None]
        self.assertEqual(join["joined"], len(drawn))
        self.assertTrue(join["joined"] > 0)
        roots = [n for n in nodes if n.kind == ROOT]
        non_visual = [n for n in nodes if "non_visual" in n.flags]
        self.assertEqual(join["not_drawn"].get("root", 0), len(roots))
        self.assertEqual(join["not_drawn"].get("non_visual", 0), len(non_visual))
        self.assertEqual(join["unmatched_doc"], [])
        self.assertEqual(join["unmatched_render"], [])
        self.assertNotIn("JOIN_UNMATCHED", {g.code for g in self.doc.diagnostics})
        self.assertNotIn("JOIN_OCCURRENCE_MISMATCH", {g.code for g in self.doc.diagnostics})
        for n in drawn:
            self.assertTrue(n.render_pos, "a joined node carries the render position it was joined with")

    def test_not_drawn_states_are_explicit_and_uncomputed(self):
        for n in self.doc.all_nodes():
            if n.kind == ROOT or "non_visual" in n.flags:
                self.assertIsNone(n.computed_style, n.logical_id)   # never styled: the render does not draw it
        join = self.doc.composition["join"]
        self.assertIn("root", join["not_drawn"])
        self.assertIn("non_visual", join["not_drawn"])

    def test_breakpoint_status_is_estimate_on_c_alone(self):
        self.assertEqual(self.doc.screen["breakpoint_status"], "ESTIMATE")
        self.assertNotEqual(self.doc.screen["composition"], "TacticalPlannerTeamInstructionsTabComposition-Large")

    def test_cells_are_read_generically_from_the_serialized_composition(self):
        comp = self.doc.composition
        self.assertEqual(comp["serialized_checks"]["cells_match_dump"], True)
        self.assertEqual(comp["serialized_checks"]["instantiation_order_match"], True)
        self.assertEqual(comp["serialized_checks"]["placement_bindings_are_cells"], True)
        self.assertEqual(len(comp["serialized"]["m_gridComponents"]), 5)
        self.assertEqual(len(comp["serialized"]["m_placementBindings"]), 5)
        self.assertNotIn("COMPOSITION_SERIALIZED_DISAGREES", {g.code for g in self.doc.diagnostics})

    def test_no_duplicate_cell_element_ids_here_and_g19_stays_pinned_by_the_team_instructions_suite(self):
        import sys
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        from test_uidoc import TeamInstructionsOnB                    # the G19 duplicate mechanism lives on TI
        dump_cells = self.doc.composition["cells"]
        ids = [c["element_id"] for c in dump_cells]
        self.assertEqual(len(ids), len(set(ids)))                     # measured: Squad Standard has no duplicate ids
        self.assertTrue(hasattr(TeamInstructionsOnB, "test_reachability_both_ways_against_the_dump_collected_independently"))


if __name__ == "__main__":
    unittest.main()
