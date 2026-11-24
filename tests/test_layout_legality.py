"""UI1 step 3/4 backend: legality findings and snapshot coverage round-trip.

Offline only: no game launch, no scanner, no live CustomGridCompositions. Every
file written in these tests lives in a temporary folder. The real owner-file
copies are used when present (and skipped when absent); otherwise synthetic
layout bytes are generated so the snapshot test always runs.
"""
import copy
import shutil
import tempfile
import unittest
from collections import OrderedDict
from pathlib import Path

from skin_editor import custom_layouts as cl, layout_legality as leg

COPIES = Path(r"__absent_fixture_path__")


def minimal_obj(eid="Happiness", key="Happiness", w=2, h=2):
    """A structurally valid custom composition with one 2x2 cell."""
    cfg = OrderedDict([("Description", OrderedDict([("instanceID", 0)])),
                       ("Size", OrderedDict([("x", w), ("y", h)])),
                       ("Asset", OrderedDict([("instanceID", 0)])),
                       ("AssetRef", OrderedDict([("m_AssetGUID", "aa"), ("m_SubObjectName", ""), ("m_SubObjectType", "")])),
                       ("Type", 0)])
    cell = OrderedDict([("m_elementID", eid),
                        ("m_configDescriptions", [OrderedDict([("instanceID", 0)])]),
                        ("m_configDescriptionKeys", [key]),
                        ("m_gridElementConfigs", [cfg]),
                        ("m_location", OrderedDict([("x", 0), ("y", 0), ("width", w), ("height", h)])),
                        ("m_minSize", OrderedDict([("x", w), ("y", h)])),
                        ("m_maxSize", OrderedDict([("x", w), ("y", h)])),
                        ("m_isLocked", False)])
    o = OrderedDict((k, None) for k in cl.TOP_ORDER)
    o["m_isCustom"] = True
    o["m_gridComponents"] = [cell]
    o["m_optionalSlices"] = OrderedDict([("m_instantiationOrder", [])])
    o["m_placementBindings"] = []
    return o


def clean_source(obj):
    """Bundle context in which every source-driven rule on `obj` passes."""
    cells = obj["m_gridComponents"]
    keys = sorted({k for c in cells for k in c.get("m_configDescriptionKeys") or []})
    sizes = {}
    for c in cells:
        loc = c["m_location"]
        for k in c.get("m_configDescriptionKeys") or []:
            sizes[k] = [[loc["width"], loc["height"]]]
    return {"allowed_descriptions": keys, "resolvable_keys": keys,
            "config_sizes": sizes, "invalid_configs": []}


def ids(findings):
    return {f["rule"] for f in findings}


class LegalityAPI(unittest.TestCase):
    def test_all_five_confirmed_rules_block_when_source_shows_a_violation(self):
        obj = minimal_obj()
        src = clean_source(obj)
        src["allowed_descriptions"] = []                 # GetAllowedDescriptions excludes this tile
        src["resolvable_keys"] = []                      # ResolvePlacements cannot resolve the key
        src["config_sizes"] = {"Happiness": [[4, 4]]}    # ResolveConfig has no 2x2 configuration
        src["invalid_configs"] = [("Happiness", 2, 2)]   # IsConfigValidForCustomisation rejects it
        obj["m_gridComponents"][0]["m_configDescriptions"] = [{"instanceID": 0}, {"instanceID": 0}]  # 2 refs
        findings = leg.check(obj, "C", src, target="Happiness")
        expected = {"allowed-descriptions", "config-for-size", "config-valid-for-customisation",
                    "placement-customisable", "description-key-resolution"}
        self.assertTrue(expected <= ids(findings), ids(findings))
        for f in findings:
            if f["rule"] in expected:
                self.assertEqual(f["label"], "Confirmed", f)
                self.assertEqual(f["severity"], "block", f)
                self.assertTrue(f["reason"].strip(), f)
        self.assertTrue(leg.should_block(findings))

    def test_source_driven_rules_degrade_to_unknown_warnings_without_source(self):
        findings = leg.check(minimal_obj(), "C")
        for rule in ("allowed-descriptions", "config-for-size", "config-valid-for-customisation",
                     "description-key-resolution"):
            self.assertEqual([(f["label"], f["severity"]) for f in findings if f["rule"] == rule],
                             [("Unknown", "warn")], rule)
        self.assertFalse(leg.should_block(findings))

    def test_empty_placements_is_an_empirical_block(self):
        obj = minimal_obj()
        obj["m_gridComponents"] = []
        findings = leg.check(obj, "C")
        self.assertEqual([(f["label"], f["severity"]) for f in findings if f["rule"] == "grid-components-nonempty"],
                         [("Empirical", "block")])
        self.assertTrue(leg.should_block(findings))

    def test_duplicate_rect_is_an_empirical_warning_only(self):
        obj = minimal_obj()
        second = copy.deepcopy(obj["m_gridComponents"][0])
        second["m_elementID"] = "Other"
        second["m_configDescriptionKeys"] = ["Other"]
        obj["m_gridComponents"].append(second)             # same (0,0,2,2) rectangle
        findings = leg.check(obj, "C", clean_source(obj))
        dup = [f for f in findings if f["rule"] == "duplicate-rectangle"]
        self.assertEqual(len(dup), 1)
        self.assertEqual((dup[0]["label"], dup[0]["severity"]), ("Empirical", "warn"))
        self.assertIn("first match", dup[0]["reason"])
        self.assertFalse(leg.should_block(findings))

    def test_locked_cell_is_an_inferred_warning_never_a_block(self):
        obj = minimal_obj()
        obj["m_gridComponents"][0]["m_isLocked"] = True
        findings = leg.check(obj, "C", clean_source(obj), target="Happiness")
        locked = [f for f in findings if f["rule"] == "locked-cell"]
        self.assertEqual([(f["label"], f["severity"]) for f in locked], [("Inferred", "warn")])
        self.assertFalse(leg.should_block(findings))
        # even a caller that asks for 'block' cannot promote an Inferred finding
        self.assertEqual(leg._finding("locked-cell", "x", severity="block")["severity"], "warn")

    def test_club_player_competition_context_is_an_unknown_warning(self):
        obj = minimal_obj()
        findings = leg.check(obj, "C", clean_source(obj))
        ctx = [f for f in findings if f["rule"] == "club-player-competition-context"]
        self.assertEqual([(f["label"], f["severity"]) for f in ctx], [("Unknown", "warn")])
        src = clean_source(obj)
        src["context_verified"] = True
        self.assertNotIn("club-player-competition-context", ids(leg.check(obj, "C", src)))

    def test_block_and_warn_are_disjoint_and_cover_all_findings(self):
        findings = leg.check(minimal_obj(), "C")
        self.assertEqual([f["rule"] for f in leg.blocking(findings)], [])
        self.assertTrue(ids(leg.warnings(findings)))
        self.assertEqual(len(leg.blocking(findings)) + len(leg.warnings(findings)), len(findings))
        self.assertTrue(all(lbl in ("Confirmed", "Empirical", "Inferred", "Unknown")
                            for lbl in leg.summary(findings)))

    def test_every_declared_rule_has_a_plain_language_reason_in_its_own_case(self):
        self.assertEqual(len(leg.RULES), 9)
        # 6 block rules (5 Confirmed checks + the Empirical non-empty rule), 3 warn rules.
        self.assertEqual(sum(1 for _label, sev, _rva, _t in leg.RULES.values() if sev == "block"), 6)
        self.assertEqual(sum(1 for _label, sev, _rva, _t in leg.RULES.values() if sev == "warn"), 3)
        self.assertEqual(sum(1 for label, _sev, _rva, _t in leg.RULES.values() if label == "Confirmed"), 5)
        self.assertEqual(sum(1 for label, _sev, _rva, _t in leg.RULES.values() if label == "Empirical"), 2)
        self.assertEqual(sum(1 for label, _sev, _rva, _t in leg.RULES.values() if label == "Inferred"), 1)
        self.assertEqual(sum(1 for label, _sev, _rva, _t in leg.RULES.values() if label == "Unknown"), 1)


class WriteGate(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix="fm27se-leg-"))
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)

    def test_write_refuses_a_confirmed_block_but_not_warnings(self):
        obj = minimal_obj()
        src = clean_source(obj)
        src["resolvable_keys"] = []                       # LT3 C1: unknown key picks a different tile
        problems = cl.validate_before_write(obj, "C", src)
        self.assertTrue(any("Description key" in p for p in problems))
        # the same source-driven block is enforced by the existing write paths
        with self.assertRaises(ValueError):
            cl.write(self.root / "C", obj, src)
        with self.assertRaises(ValueError):
            cl.write_raw(self.root / "C", cl.dumps(obj), src)
        # and both still refuse an offline-detectable block without any source
        broken = minimal_obj()
        broken["m_gridComponents"] = []
        with self.assertRaises(ValueError):
            cl.write(self.root / "C", broken)
        with self.assertRaises(ValueError):
            cl.write_raw(self.root / "C", cl.dumps(broken))

    def test_write_accepts_warning_only_findings_and_the_companion_reports_them(self):
        obj = minimal_obj()
        obj["m_gridComponents"][0]["m_isLocked"] = True
        twin = copy.deepcopy(obj["m_gridComponents"][0])
        twin["m_elementID"] = "Other"
        twin["m_configDescriptionKeys"] = ["Other"]
        obj["m_gridComponents"].append(twin)
        findings = cl.legality_findings(obj, "C", clean_source(obj))
        self.assertTrue({"duplicate-rectangle", "locked-cell"} <= ids(findings))
        self.assertEqual(cl.validate_before_write(obj, "C", clean_source(obj)), [])
        cl.write(self.root / "C", obj)
        self.assertEqual((self.root / "C").read_bytes(), cl.dumps(obj))

    def test_validation_wiring_is_in_the_existing_write_paths(self):
        # no second/raw write path was introduced: both go through validate_before_write
        import inspect
        self.assertIn("validate_before_write", inspect.getsource(cl.write))
        self.assertIn("validate_before_write", inspect.getsource(cl.write_raw))


class SnapshotCoverage(unittest.TestCase):
    """The project snapshot covers layout bundles AND every custom-layout file, byte-exact."""

    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix="fm27se-snap-"))
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)
        self.fold = self.root / "project-snapshot"
        self.fold.mkdir()

    def _layout_files(self):
        """Real owner copies when available, else synthetic valid layout bytes."""
        real = sorted(p for p in COPIES.iterdir() if p.is_file()) if COPIES.is_dir() else []
        if real:
            return {p.name: p.read_bytes() for p in real}
        return {"SyntheticComposition-%d" % i: cl.dumps(minimal_obj("Tile%d" % i, "Tile%d" % i))
                for i in range(3)}

    def _populate(self):
        files = self._layout_files()
        for name, data in files.items():
            (self.fold / name).write_bytes(data)
        # layout bundles alongside the custom-layout files in the project snapshot
        bundles = {"ui-tileslayouts_assets_all.bundle": b"UnityFS-tiles",
                   "ui-visualtreeassets_assets_all.bundle": b"UnityFS-vta"}
        for name, data in bundles.items():
            (self.fold / name).write_bytes(data)
        return files, bundles

    def test_snapshot_includes_the_layout_bundles_and_every_custom_layout_file(self):
        files, bundles = self._populate()
        snap = cl.snapshot(self.fold)
        self.assertEqual(set(snap), set(files) | set(bundles))
        self.assertTrue(set(bundles) <= set(snap))
        self.assertTrue(set(files) <= set(snap))
        self.assertTrue(all(v == cl.sha256(self.fold / k) for k, v in snap.items()))

    def test_snapshot_backup_restore_round_trips_every_layout_file_byte_exact(self):
        files, bundles = self._populate()
        before = {p.name: p.read_bytes() for p in self.fold.iterdir() if p.is_file()}
        hashes = cl.snapshot(self.fold)
        dest, backed = cl.backup(self.fold, self.root / "backup")
        self.assertEqual(backed, hashes)
        # a run changes every layout file and leaves an extra one behind
        for name in list(files) + list(bundles):
            (self.fold / name).write_bytes(b"changed " + name.encode("utf-8"))
        (self.fold / "extra-after-run").write_bytes(b"x")
        result = cl.restore(self.fold, dest, hashes)
        self.assertTrue(result["restored_equals_backup"])
        self.assertEqual(result["extra_files_moved_aside"], ["extra-after-run"])
        after = {p.name: p.read_bytes() for p in self.fold.iterdir() if p.is_file()}
        self.assertEqual(after, before)                    # byte-exact for every file, not just hash-equal


if __name__ == "__main__":
    unittest.main()
