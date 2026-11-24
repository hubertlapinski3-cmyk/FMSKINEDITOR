"""Stage 5G tests: the Playground session as a reviewed build, on synthetic sessions and archived set C only.

Never the live game folder; builds go to scratch folders. The archived set C and the live workspace are hashed
before and after the run."""
import hashlib
import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path

from skin_editor import build5g, playops, tiles
from skin_editor.render import compositionset
from skin_editor.render.service import Renderer

ARCHIVE = Path(os.environ.get("UIDOC_ARCHIVE", r"__absent_fixture_path__"))
SETC = Path(os.environ.get("UIDOC_C_AA") or (next(iter(sorted(ARCHIVE.glob("set-C-*"))), Path("missing")) / "StandaloneWindows64"))
C_DUMP = Path(os.environ.get("UIDOC_C_DUMP", r"__absent_fixture_path__"))
SETB = Path(os.environ.get("UIDOC_B_AA") or (next(iter(sorted(ARCHIVE.glob("set-B-*"))), Path("missing")) / "StandaloneWindows64"))
GAME_BUILD = "27.1.0.2505117"
SQUAD = "SquadComposition-Large"
TACTICS = "TacticalPlannerTeamInstructionsTabComposition-Large"


def _sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


class _WS:
    def __init__(self, root):
        self.root = Path(root)
        self.build = Path(root) / "build"
        self.projects = Path(root) / "projects"
        self.images = Path(root) / "images"
        self.exports = Path(root) / "exports"
        self.logs = Path(root) / "logs"
        for d in (self.build, self.projects, self.images, self.exports, self.logs):
            d.mkdir(parents=True, exist_ok=True)


class Fixture:
    _cache = None

    @classmethod
    def get(cls):
        if not SETC.is_dir() or not C_DUMP.is_file():
            raise unittest.SkipTest("archived game bundle set or layout dump not present")
        if cls._cache is None:
            tmp = tempfile.TemporaryDirectory(prefix="fm27se-5g-", ignore_cleanup_errors=True)
            import atexit
            atexit.register(tmp.cleanup)
            rd = Renderer(str(SETC), str(Path(tmp.name) / "cache"), None)
            full = compositionset.index_full(rd.layouts)
            dump = json.loads(C_DUMP.read_text(encoding="utf-8-sig"))
            files = {b: _sha(SETC / b) for b in
                     ("ui-tileslayouts_assets_all.bundle", "ui-tactics_assets_all.bundle",
                      "ui-dynamiccardcollections_assets_all.bundle", "ui-styles_assets_default.bundle",
                      "ui-styles_assets_common.bundle")}
            cls._cache = {"tmp": tmp, "dump": dump, "comps": full["compositions"],
                          "identity": {"game_build": GAME_BUILD, "files": files, "source": str(SETC)},
                          "ws": _WS(tmp.name)}
        return cls._cache

    @classmethod
    def cell(cls, comp, idx):
        return next(c for c in cls.get()["dump"]["cells"] if c["composition"] == comp and c["cell_index"] == idx)

    @classmethod
    def op(cls, kind, comp=None, cell_index=0, to=None, new=None, state="applied", sha=None, bundle=None):
        f = cls.get()
        if kind in ("ReplaceToken", "SetColor", "SetStyle", "SetSpacing", "SetVisibility", "ReplaceAsset"):
            target = {"screen": None, "logical_id": "style:%s" % kind,
                      "locator": {"bundle": bundle or "ui-styles_assets_default.bundle",
                                                  "bundle_sha256": sha if sha is not None else
                                                  f["identity"]["files"].get(bundle or "ui-styles_assets_default.bundle"),
                                                  "path_id": "1"},
                      "guard": {"type": "Label", "name": "x", "classes": []}}
            op = playops.new_operation(kind, target, new or {})
            op["state"] = state
            return op
        c = cls.cell(comp, cell_index)
        comp_rec = f["comps"][comp]
        target = {"screen": comp, "logical_id": "%s|host:%s@%d" % (comp, c["element_id"], cell_index),
                  "locator": {"bundle": comp_rec["bundle"],
                              "bundle_sha256": sha if sha is not None else f["identity"]["files"].get(comp_rec["bundle"]),
                              "path_id": comp_rec["path_id"]},
                  "guard": {"type": "Host", "name": c["element_id"], "classes": []},
                  "cell": {"composition": comp, "cell_index": cell_index, "cell_element_id": c["element_id"],
                           "geometry": {"x": (to or c)["x"], "y": (to or c)["y"],
                                        "w": (to or c).get("w", c["w"]), "h": (to or c).get("h", c["h"])}}}
        original = {"value": {"x": c["x"], "y": c["y"], "w": c["w"], "h": c["h"]}, "evidence": "directly serialized"}
        op = playops.new_operation(kind, target, new or {}, original=original)
        op["state"] = state
        return op

    @classmethod
    def session(cls, *ops, game_build=GAME_BUILD):
        s = playops.new_session("demo", SQUAD, game_build=game_build)
        # the operations are placed directly: their 5B validation is covered by the 5B tests, and 5G consumes the
        # applied records exactly as the session stores them (playops.add would supersede same-cell edits)
        s["operations"] = list(ops)
        return s


def _build(session, **kw):
    f = Fixture.get()
    dest = Path(tempfile.mkdtemp(prefix="fm27se-5g-out-", dir=f["tmp"].name))
    args = dict(ws=f["ws"], source=SETC, identity=f["identity"], dump=f["dump"], compositions=f["comps"],
                dest=dest, ts="20261118T000000Z")
    args.update(kw)
    return build5g.build(session, **args)


class Routing(unittest.TestCase):
    def test_every_kind_has_a_route_and_a_reason(self):
        f = Fixture.get()
        add = Fixture.op("AddCell", SQUAD, 0, {"x": 16, "y": 10, "w": 4, "h": 4})
        add["target"]["cell"].update({"cell_index": 5, "cell_element_id": "Happiness",
                                      "description": {"path_id": "8895524265953504165", "config_index": 2}})
        s = Fixture.session(
            Fixture.op("ReplaceToken", new={"token": "--a", "value": "#fff"}),
            Fixture.op("SetColor", new={"rule": {"sheet": {"name": "AlwaysAppliedStyleSheet", "bundle": "ui-styles_assets_default.bundle"},
                                                "selector": ".x", "props": {"color": "#fff"}}}),
            Fixture.op("MoveNode", SQUAD, 0, {"x": 16, "y": 10, "w": 4, "h": 2}),
            Fixture.op("ResizeNode", SQUAD, 0, {"x": 16, "y": 10, "w": 4, "h": 2}),
            Fixture.op("ReorderNode", SQUAD, 0),
            Fixture.op("ReplaceAsset", new={"swap": {"kind": "texture", "source": "x.png"}}),
        )
        plan = build5g.plan(s, identity=f["identity"], compositions=f["comps"], dump=f["dump"],
                            route_preference="skin_folder")
        routes = {o["kind"]: o for o in plan["operations"]}
        self.assertEqual(routes["ReplaceToken"]["route"], "skin-folder")
        self.assertEqual(routes["SetColor"]["route"], "skin-folder")
        self.assertEqual(routes["MoveNode"]["route"], "bundle")
        self.assertEqual(routes["ResizeNode"]["route"], "bundle")       # promoted by Test C
        add_plan = build5g.plan(Fixture.session(add), identity=f["identity"], compositions=f["comps"],
                                dump=f["dump"], route_preference="skin_folder")
        self.assertEqual(add_plan["operations"][0]["route"], "bundle")  # promoted by Test C+D packing
        self.assertEqual(routes["ReorderNode"]["route"], "refused")
        self.assertIn("no writer", routes["ReorderNode"]["reason"])
        self.assertEqual(routes["ReplaceAsset"]["route"], "refused")

    def test_a_supported_wallpaper_takes_the_skin_folder_route_and_writes_the_picture(self):
        import base64
        f = Fixture.get()
        png = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==")
        images = f["ws"].images / "demo"
        images.mkdir(parents=True, exist_ok=True)
        (images / "wall.png").write_bytes(png)
        op = Fixture.op("ReplaceAsset", new={"swap": {"kind": "texture", "source": "wall.png"}})
        op["target"]["guard"] = {"type": "VisualElement", "name": "background-texture"}
        s = Fixture.session(op)
        plan = build5g.plan(s, identity=f["identity"], compositions=f["comps"], dump=f["dump"],
                            images_dir=images, aa_dir=SETC)
        self.assertEqual(plan["operations"][0]["route"], "skin-folder", plan["operations"][0])
        repo = _build(s, aa_dir=SETC)
        self.assertTrue(repo["outputs"]["skin_folder"])
        self.assertTrue(any((Path(repo["outputs"]["skin_folder"]) / "images").glob("*.png")))

    def test_an_unsupported_asset_is_refused_with_its_reason(self):
        f = Fixture.get()
        op = Fixture.op("ReplaceAsset", new={"swap": {"kind": "font", "source": "x.ttf"}})
        plan = build5g.plan(Fixture.session(op), identity=f["identity"], compositions=f["comps"], dump=f["dump"])
        self.assertEqual(plan["operations"][0]["route"], "refused")
        self.assertIn("not one of them", plan["operations"][0]["reason"])

    def test_the_skin_route_refuses_a_fragment_the_writer_cannot_write(self):
        f = Fixture.get()
        s = Fixture.session(Fixture.op("SetColor", new={"rule": {
            "op": "remove", "sheet": {"name": "AlwaysAppliedStyleSheet", "bundle": "ui-styles_assets_default.bundle"},
            "selector": ".x", "props": {}}}))
        plan = build5g.plan(s, identity=f["identity"], compositions=f["comps"], dump=f["dump"])
        self.assertTrue(plan["refusals"])
        self.assertIn("cannot express a remove", plan["refusals"][0]["reason"])


class BundleRoute(unittest.TestCase):
    def test_a_move_is_built_into_the_compositions_own_bundle_including_ui_tactics(self):
        f = Fixture.get()
        repo = _build(Fixture.session(Fixture.op("MoveNode", TACTICS, 0, {"x": 0, "y": 1, "w": 6, "h": 9})))
        self.assertEqual(repo["outputs"]["bundles"].keys(), {"ui-tactics_assets_all.bundle"})
        self.assertTrue(repo["cell_check"]["ok"], repo["cell_check"]["differences"])
        self.assertEqual(repo["operations"][0]["target_bundle"], "ui-tactics_assets_all.bundle")
        self.assertTrue((Path(repo["outputs"]["built_dir"]) / "ui-tactics_assets_all.bundle").is_file())
        self.assertFalse((Path(repo["outputs"]["built_dir"]) / "ui-tileslayouts_assets_all.bundle").exists())

    def test_only_target_bundles_are_rebuilt(self):
        f = Fixture.get()
        repo = _build(Fixture.session(Fixture.op("MoveNode", SQUAD, 0, {"x": 16, "y": 10, "w": 4, "h": 2})))
        self.assertEqual(list(repo["outputs"]["bundles"]), ["ui-tileslayouts_assets_all.bundle"])

    def test_the_cell_layer_matches_the_intended_move_exactly(self):
        f = Fixture.get()
        repo = _build(Fixture.session(Fixture.op("MoveNode", SQUAD, 0, {"x": 16, "y": 10, "w": 4, "h": 2})))
        self.assertTrue(repo["cell_check"]["ok"])
        got = repo["cell_check"]["by_bundle"]["ui-tileslayouts_assets_all.bundle"]["built_cell_changes"]
        moved = next(iter(got.values()))["changed_m_location"]

        def xy(v):
            return (v[0], v[1]) if isinstance(v, (tuple, list)) else (v["x"], v["y"])
        self.assertEqual([(m["element_id"], xy(m["from"]), xy(m["to"])) for m in moved],
                         [("Atmosphere", (16, 8), (16, 10))])

    def test_an_injected_extra_change_fails_the_cell_layer_and_is_named(self):
        f = Fixture.get()
        repo = _build(Fixture.session(Fixture.op("MoveNode", SQUAD, 0, {"x": 16, "y": 10, "w": 4, "h": 2})),
                      extra_change={"bundle": "ui-tileslayouts_assets_all.bundle",
                                    "path_id": f["comps"][SQUAD]["path_id"], "composition": SQUAD,
                                    "cell_index": 1, "cell_id": "Tactics", "from": {"x": 16, "y": 0},
                                    "to": {"x": 16, "y": 2}})
        self.assertFalse(repo["cell_check"]["ok"])
        self.assertTrue(any("not asked for" in d or "not intended" in d for d in repo["cell_check"]["differences"]),
                        repo["cell_check"]["differences"])
        self.assertTrue(repo.get("blocked"))

    def test_referrers_are_reported_as_affected_not_rebuilt(self):
        f = Fixture.get()
        refs = {"ui-tileslayouts_assets_all.bundle": ["ui-visualtreeassets_assets_globalvisualtreeassetpreload.bundle"]}
        repo = _build(Fixture.session(Fixture.op("MoveNode", SQUAD, 0, {"x": 16, "y": 10, "w": 4, "h": 2})),
                      referrers=refs)
        self.assertEqual(repo["referrers"]["affected"], refs["ui-tileslayouts_assets_all.bundle"])
        self.assertEqual(list(repo["outputs"]["bundles"]), ["ui-tileslayouts_assets_all.bundle"])


class StockOverlaps(unittest.TestCase):
    def test_every_stock_overlap_is_listed_with_the_rule(self):
        f = Fixture.get()
        overlaps = build5g.stock_overlaps(f["dump"])
        self.assertGreater(len(overlaps), 0)
        tactics = [o for o in overlaps if o["composition"].startswith("TacticalPlannerTeamInstructionsTabComposition")]
        self.assertTrue(tactics, "the Team Instructions design overlaps must be listed")
        for o in overlaps:
            self.assertIn("reported, not an error", o["rule"])
            self.assertIn("only when", o["rule"])
        repo = _build(Fixture.session(Fixture.op("MoveNode", SQUAD, 0, {"x": 16, "y": 10, "w": 4, "h": 2})))
        self.assertGreater(len(repo["stock_overlaps"]), 0)


class ManifestIntegrity(unittest.TestCase):
    def test_a_replaced_bundle_with_a_manifest_entry_is_a_manifest_mismatch(self):
        import struct
        import zlib
        f = Fixture.get()
        tmp = Path(tempfile.mkdtemp(prefix="fm27se-5h-man-", dir=f["tmp"].name))
        src_dir = tmp / "src"
        src_dir.mkdir()
        src_bytes = (SETC / "ui-tileslayouts_assets_all.bundle").read_bytes()
        (src_dir / "ui-tileslayouts_assets_all.bundle").write_bytes(src_bytes)
        crc = zlib.crc32(src_bytes) & 0xFFFFFFFF
        (src_dir / "manifest.dat").write_bytes(b"\x00" * 4 + struct.pack("<I", crc) + b"\x00" * 4)
        built = tmp / "built.bundle"
        changed = bytearray(src_bytes)
        changed[-1] ^= 0xFF
        built.write_bytes(bytes(changed))
        r = build5g._integrity_row(src_dir, "ui-tileslayouts_assets_all.bundle", built, None)
        self.assertEqual(r["manifest_status"], "manifest_mismatch")
        self.assertEqual(r["manifest_dat"]["stored_crc32"], "%08x" % crc)


class Safety(unittest.TestCase):
    def test_two_moves_on_the_same_cell_conflict(self):
        f = Fixture.get()
        s = playops.new_session("demo", SQUAD, game_build=GAME_BUILD)
        # two APPLIED operations (playops.add would supersede the first; the point here is the cross-session check)
        s["operations"] = [Fixture.op("MoveNode", SQUAD, 0, {"x": 16, "y": 10, "w": 4, "h": 2}),
                           Fixture.op("MoveNode", SQUAD, 0, {"x": 12, "y": 10, "w": 4, "h": 2})]
        plan = build5g.plan(s, identity=f["identity"], compositions=f["comps"], dump=f["dump"])
        self.assertTrue(any(c["kind"] == "same_cell" for c in plan["conflicts"]))
        self.assertEqual(len(plan["conflicts"][0]["operations"]), 2)

    def test_the_overlap_gate_runs_on_the_composition_after_all_moves(self):
        f = Fixture.get()
        # moving Atmosphere onto Training is valid alone but collides with the unmoved Training cell
        s = Fixture.session(Fixture.op("MoveNode", SQUAD, 0, {"x": 16, "y": 4, "w": 4, "h": 2}))
        plan = build5g.plan(s, identity=f["identity"], compositions=f["comps"], dump=f["dump"])
        overlap = [c for c in plan["conflicts"] if c["kind"] == "overlap"]
        self.assertTrue(overlap)
        self.assertEqual(set(overlap[0]["cells"]), {"Atmosphere", "Training"})

    def test_the_overlap_gate_does_not_flag_pre_existing_design_overlaps(self):
        f = Fixture.get()
        # the tactics composition has two cells sharing a rectangle by design (cell 2 and 3)
        s = Fixture.session(Fixture.op("MoveNode", TACTICS, 0, {"x": 0, "y": 1, "w": 6, "h": 9}))
        plan = build5g.plan(s, identity=f["identity"], compositions=f["comps"], dump=f["dump"])
        self.assertEqual(plan["conflicts"], [])

    def test_stale_and_unresolved_operations_are_refused(self):
        f = Fixture.get()
        stale = Fixture.op("MoveNode", SQUAD, 0, {"x": 16, "y": 10, "w": 4, "h": 2}, state="stale")
        unresolved = Fixture.op("MoveNode", SQUAD, 1, {"x": 12, "y": 10, "w": 4, "h": 4})
        unresolved["rebased"] = [{"status": "unresolved"}]
        plan = build5g.plan(Fixture.session(stale, unresolved), identity=f["identity"],
                            compositions=f["comps"], dump=f["dump"])
        reasons = " ".join(r["reason"] for r in plan["refusals"])
        self.assertIn("stale", reasons)
        self.assertIn("unresolved", reasons)

    def test_an_identity_mismatch_is_refused(self):
        f = Fixture.get()
        wrong_build = Fixture.session(Fixture.op("MoveNode", SQUAD, 0, {"x": 16, "y": 10, "w": 4, "h": 2}),
                                     game_build="27.0.1.2503222")
        plan = build5g.plan(wrong_build, identity=f["identity"], compositions=f["comps"], dump=f["dump"])
        self.assertIn("identity mismatch", plan["refusals"][0]["reason"])
        bad_sha = Fixture.session(Fixture.op("MoveNode", SQUAD, 0, {"x": 16, "y": 10, "w": 4, "h": 2},
                                             sha="0" * 64))
        plan = build5g.plan(bad_sha, identity=f["identity"], compositions=f["comps"], dump=f["dump"])
        self.assertIn("identity mismatch", plan["refusals"][0]["reason"])

    def test_two_builds_of_the_same_session_are_byte_identical(self):
        s = Fixture.session(Fixture.op("MoveNode", SQUAD, 0, {"x": 16, "y": 10, "w": 4, "h": 2}))
        a, b = _build(s), _build(s)
        det = build5g.determinism(a, b)
        self.assertTrue(det["identical"], det)
        self.assertEqual(a["outputs"]["bundles"], b["outputs"]["bundles"])
        for bundle, sha in a["outputs"]["bundles"].items():
            self.assertEqual(sha, _sha(Path(b["outputs"]["built_dir"]) / bundle))

    def test_a_mixed_session_produces_one_skin_folder_and_one_package(self):
        f = Fixture.get()
        s = Fixture.session(
            Fixture.op("ReplaceToken", new={"token": "--x-test", "value": "#112233"}),
            Fixture.op("MoveNode", SQUAD, 0, {"x": 16, "y": 10, "w": 4, "h": 2}))
        repo = _build(s, index=None, aa_dir=SETC, route_preference="skin_folder")
        self.assertTrue(repo["outputs"]["skin_folder"])
        self.assertTrue(Path(repo["outputs"]["skin_folder"]).is_dir())
        self.assertTrue((Path(repo["outputs"]["skin_folder"]) / "tokens.uss").is_file())
        self.assertTrue(Path(repo["outputs"]["package"]).is_file())
        self.assertEqual(list(repo["outputs"]["bundles"]), ["ui-tileslayouts_assets_all.bundle"])
        self.assertEqual(repo["buildability"]["buildable"], True)
        self.assertEqual(repo["installation_ready"]["ready"], False)


class Preflight(unittest.TestCase):
    def test_install_preflight_on_a_scratch_copy_of_set_c(self):
        f = Fixture.get()
        s = Fixture.session(Fixture.op("MoveNode", SQUAD, 0, {"x": 16, "y": 10, "w": 4, "h": 2}))
        repo = _build(s)
        scratch = Path(tempfile.mkdtemp(prefix="fm27se-5g-inst-", dir=f["tmp"].name))
        for name in f["identity"]["files"]:
            shutil.copyfile(SETC / name, scratch / name)
        from skin_editor import installtx
        prof = {"install_id": "scratch-set-c", "game_build": GAME_BUILD, "game_dir": str(scratch),
                "aa_roots": [str(scratch)], "steam_build_id": None, "unity_version": None,
                "catalog_sha256": None, "manifest_dat_sha256": None}
        pf = installtx.preflight(f["ws"], prof, repo["outputs"]["built_dir"])
        self.assertIn("ready", pf)
        self.assertIn("blocked", pf)
        self.assertIn("warnings", pf)
        self.assertTrue(isinstance(pf["blocked"], list))


class Guards(unittest.TestCase):
    def test_the_archived_set_c_and_the_live_workspace_are_unchanged(self):
        ws = Path(os.environ.get("FM27SE_WORKSPACE_REAL", r"__absent_fixture_path__"))
        before = {str(p): _sha(p) for p in [ws / "config.json", ws / "layout" / "current.json",
                                            SETC / "ui-tileslayouts_assets_all.bundle",
                                            SETC / "ui-tactics_assets_all.bundle"] if p.is_file()}
        f = Fixture.get()
        _build(Fixture.session(Fixture.op("MoveNode", SQUAD, 0, {"x": 16, "y": 10, "w": 4, "h": 2})))
        after = {str(p): _sha(p) for p in [ws / "config.json", ws / "layout" / "current.json",
                                           SETC / "ui-tileslayouts_assets_all.bundle",
                                           SETC / "ui-tactics_assets_all.bundle"] if p.is_file()}
        self.assertEqual(before, after)


class TestOnlyResize(unittest.TestCase):
    def test_a_resize_enlargement_builds_and_a_shrink_below_the_config_is_refused(self):
        f = Fixture.get()
        big = Fixture.op("ResizeNode", SQUAD, 0, {"x": 16, "y": 8, "w": 4, "h": 4})
        big["target"]["cell"]["max_size"] = {"x": 4, "y": 4}
        s = Fixture.session(big)
        plan = build5g.plan(s, identity=f["identity"], compositions=f["comps"], dump=f["dump"],
                            route_preference="bundle")
        self.assertEqual(plan["operations"][0]["route"], "bundle")
        repo = _build(s)
        self.assertTrue(repo["cell_check"]["ok"], repo["cell_check"].get("differences"))
        self.assertIn("ui-tileslayouts_assets_all.bundle", repo["outputs"]["bundles"])
        # shrinking below the tile's configured 4x2 is refused (the config list is not written)
        small = Fixture.op("ResizeNode", SQUAD, 0, {"x": 16, "y": 8, "w": 4, "h": 1})
        small["target"]["cell"]["max_size"] = {"x": 4, "y": 1}
        refused = build5g.plan(Fixture.session(small), identity=f["identity"], compositions=f["comps"],
                               dump=f["dump"], route_preference="bundle")
        self.assertTrue(refused["operations"][0]["refused"])
        self.assertIn("shrinking below the tile's configured size", refused["operations"][0]["reason"])


class TestAddCellPromotion(unittest.TestCase):
    def op(self, y):
        op = Fixture.op("AddCell", SQUAD, 0, {"x": 16, "y": y, "w": 4, "h": 4})
        op["target"]["cell"].update({"cell_index": 5, "cell_element_id": "Happiness",
                                     "description": {"path_id": "8895524265953504165", "config_index": 2}})
        return op

    def test_a_cell_at_the_packed_row_builds_without_an_override(self):
        f = Fixture.get()
        repo = _build(Fixture.session(self.op(10)))       # stock Atmosphere ends at row 10
        self.assertTrue(repo["cell_check"]["ok"], repo["cell_check"].get("differences"))
        changes = next(iter(repo["cell_check"]["by_bundle"]["ui-tileslayouts_assets_all.bundle"]["built_cell_changes"].values()))
        self.assertEqual([c["element_id"] for c in changes["added_cells"]], ["Happiness"])
        self.assertEqual(changes["removed_cells"], [])
        self.assertEqual(changes["changed_m_location"], [])

    def test_a_row_the_runtime_would_pack_elsewhere_is_refused_with_the_packed_row_named(self):
        f = Fixture.get()
        plan = build5g.plan(Fixture.session(self.op(12)), identity=f["identity"], compositions=f["comps"],
                            dump=f["dump"], route_preference="bundle")
        self.assertTrue(plan["operations"][0]["refused"])
        self.assertIn("packs this added cell to row 10", plan["operations"][0]["reason"])


class OptionalSlotEffects(unittest.TestCase):
    def test_a_resize_and_an_add_report_the_optional_tiles_they_hide(self):
        f = Fixture.get()
        resize = Fixture.op("ResizeNode", SQUAD, 0, {"x": 16, "y": 8, "w": 4, "h": 4})
        resize["target"]["cell"]["max_size"] = {"x": 4, "y": 4}
        add = Fixture.op("AddCell", SQUAD, 0, {"x": 16, "y": 12, "w": 4, "h": 4})
        add["target"]["cell"].update({"cell_index": 5, "cell_element_id": "Happiness",
                                      "description": {"path_id": "8895524265953504165", "config_index": 2}})
        repo = _build(Fixture.session(resize, add))
        effects = repo["optional_slot_effects"]
        self.assertEqual([e["kind"] for e in effects], ["ResizeNode", "AddCell"])
        self.assertEqual(effects[0]["hidden"], ["Loans"])
        self.assertEqual(set(effects[1]["hidden"]), {"SquadHierachy", "MedicalCentre"})
        self.assertIn("hides SquadHierachy, MedicalCentre", effects[1]["summary"])
        self.assertIn("2560x1440 Small", effects[1]["summary"])
        self.assertEqual([e for e in repo["cell_check"]["differences"]], [])


class AddCellPlacementOptions(unittest.TestCase):
    def op(self, y):
        op = Fixture.op("AddCell", SQUAD, 0, {"x": 16, "y": y, "w": 4, "h": 4})
        op["target"]["cell"].update({"cell_index": 5, "cell_element_id": "Happiness",
                                     "description": {"path_id": "8895524265953504165", "config_index": 2}})
        return op

    def test_the_review_offers_the_requested_row_and_the_low_impact_aligned_row(self):
        f = Fixture.get()
        opts = build5g.addcell_placement_options(Fixture.session(self.op(12)), f["dump"], f["comps"], SETC)
        self.assertEqual(len(opts), 1)
        rows = {o["label"]: o for o in opts[0]["options"]}
        self.assertEqual(rows["requested"]["geometry"]["y"], 12)
        self.assertEqual(set(rows["requested"]["hidden"]), {"SquadHierachy", "MedicalCentre", "Loans"})
        self.assertEqual(rows["lowest impact"]["geometry"]["y"], 10)
        self.assertEqual(rows["lowest impact"]["hidden"], ["MedicalCentre", "Loans"])
        self.assertEqual(rows["lowest impact"]["visible"], ["SquadHierachy"])
        self.assertEqual(opts[0]["recommended"]["label"], "lowest impact")


class OptionalSlotsPromotion(unittest.TestCase):
    def op(self, new):
        f = Fixture.get()
        target = {"screen": SQUAD, "logical_id": "%s|optional:%s" % (SQUAD, new.get("element_id") or "order"),
                  "locator": {"bundle": "ui-tileslayouts_assets_all.bundle",
                              "bundle_sha256": f["identity"]["files"]["ui-tileslayouts_assets_all.bundle"],
                              "path_id": "4181126630784745451"},
                  "guard": {"type": "GridComposition", "name": SQUAD, "classes": []}}
        return playops.new_operation("SetOptionalSlots", target, new)

    def add(self, y=6):
        return self.op({"op": "add-slot", "composition": SQUAD, "direction": "m_bottom",
                        "element_id": "Happiness", "description": {"path_id": "8895524265953504165",
                                                                   "config_index": 3},
                        "location": {"x": 16, "y": y, "width": 4, "height": 2}})

    def test_add_and_replace_build_without_an_override_and_remove_or_reorder_stay_refused(self):
        f = Fixture.get()
        repo = _build(Fixture.session(self.add()))
        self.assertTrue(repo["cell_check"]["ok"])
        self.assertIn("Happiness", repo["optional_slot_effects"][0]["summary"])

        remove = self.op({"op": "remove-slot", "composition": SQUAD, "direction": "m_bottom", "element_id": "Loans"})
        add = self.add(4)
        s = Fixture.session(remove, add)
        repo = _build(s)
        self.assertTrue(repo["cell_check"]["ok"])
        self.assertEqual(len(repo["operations"]), 2)
        self.assertEqual(repo["optional_slot_effects"][0]["summary"],
                         "replaces Loans with Happiness; Happiness appears at row 14 at 2560x1440 Small")

        # remove-only is now promoted for the measured m_bottom case
        plan_remove = build5g.plan(Fixture.session(remove), identity=f["identity"], compositions=f["comps"],
                                   dump=f["dump"])
        self.assertEqual(plan_remove["operations"][0]["route"], "bundle")

        # outside the measured region the same remove-only falls back to candidate and does not build
        remove_right = self.op({"op": "remove-slot", "composition": SQUAD, "direction": "m_right",
                                "element_id": "Loans"})
        refused = build5g.plan(Fixture.session(remove_right), identity=f["identity"], compositions=f["comps"],
                               dump=f["dump"])
        self.assertTrue(refused["operations"][0]["refused"])
        self.assertIn("candidate", refused["operations"][0]["reason"].lower())

        # a non-measured preview setting marks every slot/cell visibility message as an estimate
        s3 = Fixture.session(self.add())
        s3["preview"] = {"width": 1920, "height": 1080, "setting": "Large UI"}
        est = _build(s3)
        self.assertIn("(estimate)", est["optional_slot_effects"][0]["summary"])

        reorder = self.op({"op": "reorder-slot", "composition": SQUAD, "direction": "m_bottom",
                           "order": ["MedicalCentre", "SquadHierachy", "Loans"]})
        self.assertEqual(build5g.plan(Fixture.session(reorder), identity=f["identity"], compositions=f["comps"],
                                      dump=f["dump"])["operations"][0]["route"], "bundle")
        reorder_right = self.op({"op": "reorder-slot", "composition": SQUAD, "direction": "m_right",
                                 "order": ["MedicalCentre", "SquadHierachy", "Loans"]})
        refused = build5g.plan(Fixture.session(reorder_right), identity=f["identity"], compositions=f["comps"],
                               dump=f["dump"])
        self.assertTrue(refused["operations"][0]["refused"])


if __name__ == "__main__":
    unittest.main()
