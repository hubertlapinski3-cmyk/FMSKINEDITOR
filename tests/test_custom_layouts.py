"""CL3 part A: the custom-layout writer. Real files are the owner's copies in layout-model-spec (skipped when missing); the bundle is archived stock set C."""
import copy
import glob
import json
import tempfile
import unittest
from pathlib import Path

from skin_editor import custom_layouts as cl

COPIES = Path(r"__absent_fixture_path__")
PROFILE = "PlayerReportOverviewComposition-Large"
STAGES = "CompetitionStagesBottomTileComposition"
SETC = next(iter(sorted(glob.glob(r"__absent_fixture_path__"))), None)
TILES = "ui-tileslayouts_assets_all.bundle"


def paths(a, b, p=""):
    """Every leaf path where two JSON values differ (both ways)."""
    out = []
    if isinstance(a, dict) and isinstance(b, dict):
        for k in list(a) + [k for k in b if k not in a]:
            if k not in a or k not in b:
                out.append(p + "/" + k + " (only in one)")
            else:
                out += paths(a[k], b[k], p + "/" + k)
    elif isinstance(a, list) and isinstance(b, list):
        if len(a) != len(b):
            out.append(p + "[len %d != %d]" % (len(a), len(b)))
        for i, (x, y) in enumerate(zip(a, b)):
            out += paths(x, y, "%s[%d]" % (p, i))
    elif a != b:
        out.append(p)
    return out


@unittest.skipUnless((COPIES / PROFILE).is_file(), "needs the copied real files")
class RoundTrip(unittest.TestCase):
    def test_reading_and_writing_an_unchanged_real_file_reproduces_it_byte_for_byte(self):
        for name in (PROFILE, STAGES):
            raw = (COPIES / name).read_bytes()
            self.assertEqual(cl.dumps(cl.loads(raw)), raw, name)
            tmp = Path(tempfile.mkdtemp()) / name
            cl.write(tmp, cl.read(COPIES / name))
            self.assertEqual(tmp.read_bytes(), raw)

    def test_the_format_is_one_line_utf8_without_bom(self):
        raw = (COPIES / PROFILE).read_bytes()
        self.assertFalse(raw.startswith(b"\xef\xbb\xbf"))
        self.assertNotIn(b"\n", raw)
        self.assertNotIn(b" ", raw.replace(b"Tactical Effectiveness", b""))


@unittest.skipUnless((COPIES / PROFILE).is_file() and SETC, "needs the copied real files and archived set C")
class Generate(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.real = cl.read(COPIES / PROFILE)
        cls.tt, cls.objs = cl.load_composition(Path(SETC) / TILES, PROFILE)

    def swapped(self, real=None):
        out = cl.generate(self.tt, self.objs, real=real)
        src = cl.description_cell([Path(SETC) / TILES, Path(SETC) / "ui-tactics_assets_all.bundle"], "TacticalEffectiveness", (2, 2), prefer=TILES)
        cl.swap_cell(out, "Happiness", src)
        return cl.inherit_ids(out, self.real) if real else out

    def test_generated_profile_with_the_swap_equals_the_real_file_except_instance_ids_and_the_stale_asset_guid(self):
        out = self.swapped(real=self.real)
        diffs = paths(out, self.real)
        # the game's own swap kept the OLD tile's asset GUID (Happiness' 2x2) next to the new name key; a swap by name uses the new description's own configuration
        self.assertEqual(diffs, ["/m_gridComponents[1]/m_gridElementConfigs[0]/AssetRef/m_AssetGUID"], diffs)
        self.assertEqual(out["m_isCustom"], True)
        self.assertEqual(list(out), cl.TOP_ORDER)

    def test_without_a_real_file_every_instance_id_is_zero_and_nothing_else_differs_from_the_policy(self):
        out = self.swapped()
        diffs = paths(out, self.real)
        self.assertTrue(all("instanceID" in d or d.endswith("m_AssetGUID") for d in diffs), diffs)
        self.assertEqual(out["m_gridElementSet"], {"instanceID": 0})
        self.assertTrue(all(c["m_configDescriptions"] == [{"instanceID": 0}] for c in out["m_gridComponents"][:1]))

    def test_each_operation_changes_only_its_own_fields(self):
        base = cl.generate(self.tt, self.objs)
        a = copy.deepcopy(base)
        cl.set_max_size(a, "FItness", 6, 4)
        self.assertEqual(paths(a, base), ["/m_gridComponents[2]/m_maxSize/x"])
        b = copy.deepcopy(base)
        cl.set_location(b, "PlayerForm", 4, 6, 2, 4)
        self.assertEqual(paths(b, base), ["/m_gridComponents[3]/m_location/height"])
        c = copy.deepcopy(base)
        cl.swap_cell(c, "Happiness", cl.description_cell([Path(SETC) / TILES, Path(SETC) / "ui-tactics_assets_all.bundle"], "TacticalEffectiveness", (2, 2), prefer=TILES))
        self.assertTrue(all(d.startswith("/m_gridComponents[1]/") for d in paths(c, base)))
        self.assertEqual(c["m_gridComponents"][1]["m_location"], base["m_gridComponents"][1]["m_location"])      # the slot stays

    def test_the_stages_file_equals_its_bundle_composition_with_its_one_swap(self):
        tt, objs = cl.load_composition(Path(SETC) / TILES, STAGES)
        real = cl.read(COPIES / STAGES)
        out = cl.generate(tt, objs, real=real)
        diffs = paths(out, real)
        self.assertTrue(all(d.startswith("/m_gridComponents[3]/") for d in diffs), diffs)      # SeasonPreview for CompetitionSiteAboutRules, nothing else


@unittest.skipUnless(SETC, "needs archived set C")
class StructuralOperations(unittest.TestCase):
    """JX part A: add_cell and set_slots on SquadComposition-Large."""

    @classmethod
    def setUpClass(cls):
        cls.tt, cls.objs = cl.load_composition(Path(SETC) / TILES, "SquadComposition-Large")
        cls.bundles = [Path(SETC) / TILES]
        cls.happiness = lambda self, size: cl.description_cell(self.bundles, "SquadHappinessTileDescription", size, prefer=TILES)

    def base(self):
        return cl.generate(self.tt, self.objs)

    def test_add_cell_changes_only_the_new_cell_its_binding_and_the_order_indexes(self):
        base = self.base()
        out = cl.add_cell(copy.deepcopy(base), "Happiness", self.happiness((4, 4)), (16, 10, 4, 4))
        diffs = paths(out, base)
        self.assertTrue(all(d.startswith("/m_gridComponents[len") or d.startswith("/m_placementBindings[len") or d.startswith("/m_optionalSlices/m_instantiationOrder")
                            for d in diffs), diffs)
        cell = out["m_gridComponents"][-1]
        self.assertEqual((cell["m_elementID"], cell["m_configDescriptionKeys"], cell["m_location"]["x"], cell["m_location"]["y"]), ("Happiness", ["Happiness"], 16, 10))
        self.assertEqual(cell["m_gridElementConfigs"][0]["AssetRef"]["m_AssetGUID"], "ee9c1eef7befdb74d818d840506962b4")       # SquadHappiness 4x4 (test D)
        self.assertEqual(out["m_placementBindings"][-1]["m_elementID"], "Happiness")
        order = out["m_optionalSlices"]["m_instantiationOrder"]
        self.assertEqual(sorted(order), list(range(9)))                                    # a permutation of the 9 elements, consistent
        self.assertEqual(cl.dumps(cl.loads(cl.dumps(out))), cl.dumps(out))                   # still round-trips

    def test_add_cell_refuses_a_used_id_and_a_wrong_size(self):
        base = self.base()
        with self.assertRaises(KeyError):
            cl.add_cell(copy.deepcopy(base), "Atmosphere", self.happiness((4, 4)), (16, 10, 4, 4))
        with self.assertRaises(ValueError):
            cl.add_cell(copy.deepcopy(base), "Happiness", self.happiness((4, 4)), (16, 10, 4, 2))

    def test_set_slots_replaces_loans_by_happiness_and_changes_only_that_slot(self):
        base = self.base()
        loans = base["m_optionalSlices"]["m_bottom"]
        out = cl.set_slots(copy.deepcopy(base), "m_bottom", [("SquadHierachy", None, (16, 0)), ("MedicalCentre", None, (16, 2)), ("Happiness", self.happiness((4, 2)), (16, 4))])
        diffs = paths(out, base)
        self.assertTrue(all(d.startswith("/m_optionalSlices/m_bottom[2]/") for d in diffs), diffs)           # only the third slot, the order is unchanged
        e = out["m_optionalSlices"]["m_bottom"][2]
        self.assertEqual((e["m_elementID"], e["m_configDescriptionKeys"], e["m_location"]["y"], e["m_location"]["width"], e["m_location"]["height"]), ("Happiness", ["Happiness"], 4, 4, 2))
        self.assertEqual(out["m_optionalSlices"]["m_instantiationOrder"], base["m_optionalSlices"]["m_instantiationOrder"])
        self.assertEqual(cl.dumps(cl.loads(cl.dumps(out))), cl.dumps(out))
        self.assertEqual(loans[2]["m_elementID"], "Loans")

    def test_set_slots_reindexes_the_order_when_the_count_changes(self):
        base = self.base()
        out = cl.set_slots(copy.deepcopy(base), "m_bottom", [("SquadHierachy", None, (16, 0)), ("MedicalCentre", None, (16, 2))])
        self.assertEqual(sorted(out["m_optionalSlices"]["m_instantiationOrder"]), list(range(7)))
        with self.assertRaises(KeyError):
            cl.set_slots(copy.deepcopy(base), "m_bottom", [("Tactics", self.happiness((4, 2)), (16, 0))])             # a grid id is not a slot id


class BackupRestore(unittest.TestCase):
    def test_backup_restore_is_exact_and_extras_are_moved_aside(self):
        root = Path(tempfile.mkdtemp())
        fold = root / "f"
        fold.mkdir()
        (fold / "a").write_bytes(b"1")
        (fold / "b").write_bytes(b"2")
        dest, hashes = cl.backup(fold, root / "bk")  if (root / "bk").mkdir() is None else (None, None)
        (fold / "a").write_bytes(b"changed")
        (fold / "b").unlink()
        (fold / "new").write_bytes(b"x")
        r = cl.restore(fold, dest, hashes)
        self.assertTrue(r["restored_equals_backup"])
        self.assertEqual(r["extra_files_moved_aside"], ["new"])
        self.assertEqual(cl.snapshot(fold), hashes)
        self.assertTrue((dest / "extra-after-run" / "new").is_file())            # moved aside, not deleted


if __name__ == "__main__":
    unittest.main()

@unittest.skipUnless((COPIES / PROFILE).is_file(), "needs the copied real files")
class PreWriteChecks(unittest.TestCase):
    """REA-WIN-2 W7: only Confirmed and Empirical rules are implemented."""

    @classmethod
    def setUpClass(cls):
        cls.root = COPIES.parent
        cls.proven = sorted({p for p in cls.root.rglob("*") if p.is_file()})

    def test_owner_files_are_accepted(self):
        for name in (PROFILE, STAGES):
            self.assertEqual(cl.validate_before_write(cl.read(COPIES / name), name), [], name)

    def test_every_proven_cl_cl3_jx_e2e1_file_is_accepted(self):
        self.assertGreaterEqual(len(self.proven), 6)
        for p in self.proven:
            self.assertEqual(cl.validate_before_write(cl.read(p), p.name), [], str(p))

    def test_write_allows_a_duplicate_rect_but_reports_it_as_a_warning(self):
        # LT2 C5: the game tolerates a duplicate rectangle and takes the first match.
        # It is a Studio-policy WARNING, not a game rule, so write must not refuse.
        obj = cl.read(COPIES / PROFILE)
        a, b = obj["m_gridComponents"][1], obj["m_gridComponents"][2]   # both fixed 2x2
        b["m_location"] = copy.deepcopy(a["m_location"])
        cl.write(Path(tempfile.mkdtemp()) / PROFILE, obj)
        dup = [f for f in cl.legality_findings(obj) if f["rule"] == "duplicate-rectangle"]
        self.assertEqual(len(dup), 1)
        self.assertEqual((dup[0]["label"], dup[0]["severity"]), ("Empirical", "warn"))
        self.assertNotIn(dup[0]["reason"], cl.validate_before_write(obj, PROFILE))

    def test_write_refuses_a_missing_description_key(self):
        obj = cl.read(COPIES / PROFILE)
        obj["m_gridComponents"][0]["m_configDescriptionKeys"] = []
        with self.assertRaises(ValueError):
            cl.write(Path(tempfile.mkdtemp()) / PROFILE, obj)

    def test_unsafe_names_are_refused(self):
        obj = cl.read(COPIES / PROFILE)
        for name in ("../evil", "a/b", r"c:\x", "."):
            self.assertTrue(cl.validate_before_write(obj, name), name)

    def test_write_raw_refuses_truncated_json(self):
        raw = cl.dumps(cl.read(COPIES / PROFILE))
        with self.assertRaises(ValueError):
            cl.write_raw(Path(tempfile.mkdtemp()) / PROFILE, raw[: len(raw) // 2])

    def test_write_raw_allows_a_duplicate_rect_but_reports_it_as_a_warning(self):
        obj = cl.read(COPIES / PROFILE)
        a, b = obj["m_gridComponents"][1], obj["m_gridComponents"][2]   # both fixed 2x2
        b["m_location"] = copy.deepcopy(a["m_location"])
        tmp = Path(tempfile.mkdtemp()) / PROFILE
        cl.write_raw(tmp, cl.dumps(obj))
        self.assertEqual(tmp.read_bytes(), cl.dumps(obj))
        self.assertTrue(any(f["rule"] == "duplicate-rectangle" and f["severity"] == "warn"
                            for f in cl.legality_findings(obj)))

    def test_write_raw_accepts_proven_file_bytes(self):
        raw = (COPIES / PROFILE).read_bytes()
        tmp = Path(tempfile.mkdtemp()) / PROFILE
        cl.write_raw(tmp, raw)
        self.assertEqual(tmp.read_bytes(), raw)

    def test_write_refuses_empty_placements(self):
        obj = cl.read(COPIES / PROFILE)
        obj.pop("m_gridComponents", None)
        with self.assertRaises(ValueError):
            cl.write(Path(tempfile.mkdtemp()) / PROFILE, obj)

SQUAD_RESAVE = next(iter(sorted(glob.glob(
    r"__absent_fixture_path__"))), None)


class Ui3(unittest.TestCase):
    """UI3 (2026-11-22): the one-column drag that broke Squad Large."""

    @unittest.skipUnless(SQUAD_RESAVE, "no game re-save of SquadComposition-Large available")
    def test_the_one_column_move_that_broke_the_game_is_refused(self):
        obj = cl.read(Path(SQUAD_RESAVE))
        by = {c["m_elementID"]: c for c in obj["m_gridComponents"]}
        # The exact staged edit: Atmosphere and Training each moved from x16 to x15;
        # Training also dragged from y4 to y6.
        by["Atmosphere"]["m_location"]["x"] = 15
        by["Training"]["m_location"].update({"x": 15, "y": 6})
        probs = cl.validate_before_write(obj, "SquadComposition-Large")
        overlap = [p for p in probs if "overlaps" in p]
        self.assertTrue(overlap, probs)
        self.assertTrue(any("FirstTeamOverview" in p for p in overlap))
        # The canvas path must produce the same refusal.
        n = cl.apply_canvas_edits(obj, [
            {"element_id": "Atmosphere", "x": 15, "y": 8},
            {"element_id": "Training", "x": 15, "y": 6}])
        self.assertEqual(n, 2)
        self.assertTrue([p for p in cl.validate_before_write(obj, "SquadComposition-Large") if "overlaps" in p])


@unittest.skipUnless(COPIES.is_dir(), "needs layout fixture copies")
class Ui3RestoreBefore(unittest.TestCase):
    """UI3: a file the game re-saved since Apply can be put back to its pre-Apply state."""

    def _apply(self, obj):
        from skin_editor import layouttx
        pkg, target, journal = Path(tempfile.mkdtemp()), Path(tempfile.mkdtemp()), Path(tempfile.mkdtemp())
        (pkg / "custom-layouts").mkdir()
        cl.write(pkg / "custom-layouts" / PROFILE, obj)
        (pkg / "custom-layouts.json").write_text(json.dumps({
            "schema": "fm-customlayouts/1",
            "files": [{"name": PROFILE, "sha256": cl.sha256(pkg / "custom-layouts" / PROFILE)}]}), encoding="utf-8")
        return layouttx, layouttx.apply(journal, pkg, folder=target), target, journal

    def test_a_created_file_is_deleted_even_after_the_game_resaved_it(self):
        layouttx, tx, target, journal = self._apply(cl.read(COPIES / PROFILE))
        self.assertTrue((target / PROFILE).is_file())
        changed = cl.read(target / PROFILE)               # the game re-saved it: different bytes
        changed["m_gridComponents"][0]["m_location"]["x"] += 1
        cl.write(target / PROFILE, changed)
        res = layouttx.restore_to_before(journal, tx["tx_id"], confirm=False)
        self.assertTrue(res["needs_confirmation"])
        self.assertEqual([c["name"] for c in res["changed"]], [PROFILE])
        self.assertTrue((target / PROFILE).is_file())     # nothing written without confirmation
        res = layouttx.restore_to_before(journal, tx["tx_id"], confirm=True)
        self.assertEqual(res["state"], "restored_before_apply")
        self.assertFalse((target / PROFILE).exists())

    def test_a_replaced_file_comes_back_byte_for_byte(self):
        target_original = (COPIES / PROFILE).read_bytes()
        layouttx, tx, target, journal = self._apply(cl.read(COPIES / PROFILE))
        # pretend the owner's file existed before: run a second apply over a fresh folder holding it
        folder = Path(tempfile.mkdtemp())
        (folder / PROFILE).write_bytes(target_original)
        journal2 = Path(tempfile.mkdtemp())
        pkg = Path(tempfile.mkdtemp())
        (pkg / "custom-layouts").mkdir()
        edited = cl.read(COPIES / PROFILE)
        edited["m_gridComponents"][0]["m_isDebug"] = not edited["m_gridComponents"][0]["m_isDebug"]   # bytes change, geometry does not
        cl.write(pkg / "custom-layouts" / PROFILE, edited)
        (pkg / "custom-layouts.json").write_text(json.dumps({
            "schema": "fm-customlayouts/1",
            "files": [{"name": PROFILE, "sha256": cl.sha256(pkg / "custom-layouts" / PROFILE)}]}), encoding="utf-8")
        tx2 = layouttx.apply(journal2, pkg, folder=folder, confirmations=["replace:" + PROFILE])
        self.assertNotEqual((folder / PROFILE).read_bytes(), target_original)
        layouttx.restore_to_before(journal2, tx2["tx_id"], confirm=True)
        self.assertEqual((folder / PROFILE).read_bytes(), target_original)


@unittest.skipUnless(COPIES.is_dir(), "needs layout fixture copies")
class CanvasEdits(unittest.TestCase):
    def test_edits_match_by_element_id_not_cell_index(self):
        obj = cl.read(COPIES / PROFILE)
        atmos = obj["m_gridComponents"][0]
        self.assertNotIn("cell_index", atmos)
        old_max = atmos["m_maxSize"]["x"]
        (min_w, min_h), (max_w, max_h) = cl.cell_limits(atmos)
        n = cl.apply_canvas_edits(obj, [{"element_id": atmos["m_elementID"], "cell_index": 0, "x": 18, "y": 4, "w": 6, "h": 3}])
        self.assertEqual(n, 1)
        loc = atmos["m_location"]
        self.assertEqual(loc["width"], min(max(6, min_w), max_w))
        self.assertEqual(loc["height"], min(max(3, min_h), max_h))
        self.assertGreaterEqual(loc["x"], 0)
        self.assertGreaterEqual(loc["y"], 0)
        self.assertEqual(atmos["m_maxSize"]["x"], max(loc["width"], old_max))
        self.assertEqual(cl.apply_canvas_edits(obj, [{"element_id": "NoSuchTile", "x": 1}]), 0)

    def test_file_without_real_references_is_rejected(self):
        obj = cl.read(COPIES / PROFILE)
        self.assertTrue(cl.has_real_references(obj))
        for k in ("m_gridElementSet", "m_validator", "m_editorValidator"):
            obj[k] = {"instanceID": 0}
        for c in obj.get("m_gridComponents") or []:
            for d in c.get("m_configDescriptions") or []:
                d["instanceID"] = 0
            for cfg in c.get("m_gridElementConfigs") or []:
                if isinstance(cfg.get("Description"), dict):
                    cfg["Description"]["instanceID"] = 0
        self.assertFalse(cl.has_real_references(obj))

    def test_zero_id_file_passes_validation_and_applies(self):
        """UI3: zero ids are not a gate. A generated file (every reference instanceID 0) validates and
        installs through layouttx. Evidence: ResolveDescriptionKeys layout-rule, CL3 B1, JX X1-X3, E2E1."""
        from skin_editor import layouttx
        obj = cl.read(COPIES / PROFILE)
        for k in ("m_gridElementSet", "m_validator", "m_editorValidator"):
            obj[k] = {"instanceID": 0}
        for c in obj.get("m_gridComponents") or []:
            for d in c.get("m_configDescriptions") or []:
                d["instanceID"] = 0
            for cfg in c.get("m_gridElementConfigs") or []:
                if isinstance(cfg.get("Description"), dict):
                    cfg["Description"]["instanceID"] = 0
        self.assertFalse(cl.has_real_references(obj))
        self.assertEqual(cl.validate_before_write(obj, PROFILE), [])
        pkg = Path(tempfile.mkdtemp())
        (pkg / "custom-layouts").mkdir()
        cl.write(pkg / "custom-layouts" / PROFILE, obj)
        (pkg / "custom-layouts.json").write_text(json.dumps({
            "schema": "fm-customlayouts/1",
            "files": [{"name": PROFILE, "sha256": cl.sha256(pkg / "custom-layouts" / PROFILE)}]}), encoding="utf-8")
        target, journal = Path(tempfile.mkdtemp()), Path(tempfile.mkdtemp())
        tx = layouttx.apply(journal, pkg, folder=target)
        self.assertEqual(tx["state"], "completed")
        self.assertTrue((target / PROFILE).is_file())

    def test_fixed_size_tile_cannot_be_shrunk_below_its_minimum(self):
        obj = cl.read(COPIES / PROFILE)
        cell = obj["m_gridComponents"][0]
        eid = cell["m_elementID"]
        (min_w, min_h), _max = cl.cell_limits(cell)
        before = dict(cell["m_location"])
        cl.apply_canvas_edits(obj, [{"element_id": eid, "w": 1, "h": 1}])
        loc = cell["m_location"]
        self.assertGreaterEqual(loc["width"], min_w)
        self.assertGreaterEqual(loc["height"], min_h)
        self.assertEqual((loc["x"], loc["y"]), (before["x"], before["y"]))
        self.assertEqual(cl.validate_before_write(obj, PROFILE), [])
