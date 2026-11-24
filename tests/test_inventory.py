"""Stage 4B: installation profile, bundle inventory, asset registry, job cancellation. Uses the committed SYNTHETIC bundle (data/selftest/roundtrip.unity3d) in
temporary mock installations; no game file is read or written. Tests that check the Stage 3 CRC values read the archived set-C bundles when they are present and skip otherwise."""
import hashlib
import os
import shutil
import tempfile
import threading
import time
import unittest
from pathlib import Path

from skin_editor import bundles, config, gameinstall, inventory, registry
from skin_editor.api.jobs import Cancelled, JobQueue

ROOT = Path(__file__).resolve().parent.parent
FIXTURE = ROOT / "data" / "selftest" / "roundtrip.unity3d"
FIXTURE_CRC = "43791720"            # zlib CRC-32 of the fixture's uncompressed content (608 bytes), computed independently of bundles.py
SETC = Path(os.environ.get("FM27SE_SETC", r"__absent_fixture_path__"))


def tree_hashes(root):
    out = {}
    for dp, _, fs in os.walk(root):
        for f in fs:
            p = Path(dp) / f
            out[str(p.relative_to(root))] = (p.stat().st_size, p.stat().st_mtime_ns, hashlib.sha256(p.read_bytes()).hexdigest())
    return out


def make_install(base, extra=()):
    """A mock FM-shaped installation: <base>/Game/Game.exe, Game_Data/{boot.config, manifest.dat, StreamingAssets/aa/{catalog.bin, catalog.hash, settings.json, StandaloneWindows64/*.bundle}}."""
    game = Path(base) / "Game"
    data = game / "Game_Data"
    aa = data / "StreamingAssets" / "aa"
    plat = aa / "StandaloneWindows64"
    plat.mkdir(parents=True)
    (game / "Game.exe").write_bytes(b"MZ" + b"\0" * 100)
    (data / "boot.config").write_text("gfx-enable-gfx-jobs=1\nbuild-guid=abc123\n")
    (data / "manifest.dat").write_bytes(b"\x01\x02\x03")
    (aa / "catalog.bin").write_bytes(b"B\x89\xe3\r\x02\x00\x00\x00" + b"\0" * 64)
    (aa / "catalog.hash").write_text("0123456789abcdef0123456789abcdef")
    (aa / "settings.json").write_text('{"m_AddressablesVersion": "2.7.0"}')
    for name in ("ui-styles_assets_common.bundle", "ui-styles_assets_default.bundle", "ui-tileslayouts_assets_all.bundle") + tuple(extra):
        shutil.copyfile(FIXTURE, plat / name)
    return game, plat


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="fm27se-inv-"))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.game, self.plat = make_install(self.tmp)
        self.ws = config.Workspace(self.tmp / "ws")
        self.prof = gameinstall.describe_install(self.game, "test", "27.test")
        self.reg = registry.Registry.for_install(self.ws, self.prof["install_id"])


class TestCrcAndHeader(unittest.TestCase):
    def test_crc_of_the_uncompressed_content_matches_the_independent_value(self):
        self.assertEqual("%08x" % bundles.crc32_uncompressed(FIXTURE), FIXTURE_CRC)

    def test_crc_is_not_the_crc_of_the_compressed_file(self):
        import zlib
        self.assertNotEqual(bundles.crc32_uncompressed(FIXTURE), zlib.crc32(FIXTURE.read_bytes()))

    def test_header(self):
        h = bundles.bundle_header(FIXTURE)
        self.assertEqual((h["signature"], h["format"], h["unity_revision"]), ("UnityFS", 8, "2022.3.62f1"))

    def test_header_of_a_file_that_is_not_a_bundle(self):
        d = Path(tempfile.mkdtemp(prefix="fm27se-hdr-"))
        self.addCleanup(shutil.rmtree, d, ignore_errors=True)
        (d / "x.bundle").write_bytes(b"not a bundle at all")
        self.assertIsNone(bundles.bundle_header(d / "x.bundle"))

    @unittest.skipUnless((SETC / "ui-tileslayouts_assets_all.bundle").is_file(), "archived set-C bundles not present")
    def test_stage3_values_on_the_real_set_c_bundles(self):
        self.assertEqual("%08x" % bundles.crc32_uncompressed(SETC / "ui-tileslayouts_assets_all.bundle"), "3949995c")
        self.assertEqual("%08x" % bundles.crc32_uncompressed(SETC / "ui-panelids_assets_all.bundle"), "f04ea76d")


class TestProfile(Base):
    def test_describe(self):
        p = self.prof
        self.assertEqual(p["role"], "test")
        self.assertEqual(p["game_build"], "27.test")
        self.assertEqual(p["addressables_version"], "2.7.0")
        self.assertEqual(p["unity_build_guid"], "abc123")
        self.assertEqual(p["unity_version"], "2022.3.62f1")
        self.assertTrue(p["catalog_sha256"] and p["catalog_hash_sha256"] and p["manifest_dat_sha256"])
        self.assertEqual(p["catalog_hash"], "0123456789abcdef0123456789abcdef")
        self.assertEqual(gameinstall.validate(p), [])

    def test_roles_are_checked(self):
        with self.assertRaises(gameinstall.ProfileError):
            gameinstall.describe_install(self.game, "nonsense")

    def test_not_a_game_folder(self):
        empty = self.tmp / "empty"
        empty.mkdir()
        with self.assertRaises(gameinstall.ProfileError):
            gameinstall.describe_install(empty)

    def test_identity_changes_when_the_catalog_changes(self):
        before = self.prof["install_id"]
        (self.plat.parent / "catalog.bin").write_bytes(b"different catalog")
        self.assertNotEqual(gameinstall.describe_install(self.game)["install_id"], before)

    def test_drift(self):
        self.assertEqual(gameinstall.drift(self.prof), [])
        (self.plat.parent / "catalog.hash").write_text("ffffffffffffffffffffffffffffffff")
        self.assertIn("catalog_hash_sha256_changed", [d["code"] for d in gameinstall.drift(self.prof)])
        shutil.rmtree(self.game)
        self.assertEqual([d["code"] for d in gameinstall.drift(self.prof)], ["gone"])

    def test_storage_roundtrip_and_active(self):
        gameinstall.save(self.ws, self.prof)
        self.assertEqual(gameinstall.get(self.ws)["install_id"], self.prof["install_id"])
        with self.assertRaises(KeyError):
            gameinstall.get(self.ws, "nope")

    def test_describing_writes_nothing_to_the_game_folder(self):
        before = tree_hashes(self.game)
        gameinstall.describe_install(self.game)
        gameinstall.drift(self.prof)
        self.assertEqual(before, tree_hashes(self.game))


class TestInventory(Base):
    def scan(self, **kw):
        return inventory.scan(self.reg, self.prof["aa_roots"], **kw)

    def test_first_scan_records_every_bundle(self):
        s = self.scan()
        self.assertEqual((s["files"], s["new"], s["reused"], s["errors"]), (3, 3, 0, 0))
        self.assertEqual(s["states"], {"valid": 3})
        b = self.reg.get_bundle("ui-tileslayouts_assets_all.bundle")
        self.assertEqual((b["state"], b["crc32"], b["object_count"], b["cab"], b["unity_version"]), ("valid", FIXTURE_CRC, 1, "CAB-fmskinstudioselftest0000000", "2022.3.62f1"))
        self.assertEqual(b["sha256"], hashlib.sha256(FIXTURE.read_bytes()).hexdigest())
        self.assertEqual(b["type_counts"], {"TextAsset": 1})
        self.assertEqual((b["catalog_crc_status"], b["manifest_status"]), ("not_checked", "not_checked"))   # 4E fills these in

    def test_scan_never_touches_the_game_folder(self):
        before = tree_hashes(self.game)
        self.scan()
        self.scan(verify=True)
        self.assertEqual(before, tree_hashes(self.game))

    def test_no_file_handle_stays_open_on_a_scanned_bundle(self):
        self.scan()
        for p in self.plat.glob("*.bundle"):
            p.unlink()                                 # fails on Windows when a handle is still open

    def test_second_scan_reuses_everything(self):
        self.scan()
        s = self.scan()
        self.assertEqual((s["reused"], s["new"], s["changed"]), (3, 0, 0))

    def test_verify_rehashes_but_keeps_the_parsed_records(self):
        self.scan()
        s = self.scan(verify=True)
        self.assertEqual((s["reused"], s["rehashed_unchanged"], s["changed"]), (0, 3, 0))

    def test_modification_time_alone_is_not_trusted_after_the_window(self):
        self.scan()
        s = self.scan(max_unverified_days=0)
        self.assertEqual(s["reused"], 0)

    def test_changed_file_is_detected_and_reindexed(self):
        self.scan()
        f = self.plat / "ui-tileslayouts_assets_all.bundle"
        f.write_bytes(b"corrupted now")
        s = self.scan()
        self.assertEqual((s["changed"], s["reused"], s["errors"]), (1, 2, 1))
        b = self.reg.get_bundle("ui-tileslayouts_assets_all.bundle")
        self.assertEqual(b["state"], "unsupported")
        self.assertEqual(self.reg.search_assets(bundle="ui-tileslayouts_assets_all.bundle")["total"], 0)      # the old rows are gone with the old bytes

    def test_same_bytes_new_mtime_keeps_the_record(self):
        self.scan()
        f = self.plat / "ui-tileslayouts_assets_all.bundle"
        os.utime(f, ns=(time.time_ns(), time.time_ns() + 5_000_000_000))
        s = self.scan()
        self.assertEqual((s["rehashed_unchanged"], s["changed"]), (1, 0))

    def test_a_bad_bundle_does_not_stop_the_scan(self):
        (self.plat / "broken.bundle").write_bytes(b"UnityFS\0garbage")
        (self.plat / "junk.bundle").write_bytes(b"nothing")
        s = self.scan()
        self.assertEqual(s["files"], 5)
        self.assertEqual(s["states"].get("valid"), 3)
        self.assertEqual(self.reg.get_bundle("junk.bundle")["state"], "unsupported")
        self.assertIn(self.reg.get_bundle("broken.bundle")["state"], ("corrupt", "unsupported"))
        self.assertTrue(self.reg.get_bundle("broken.bundle")["error"])

    def test_missing_bundle_is_marked_and_kept(self):
        self.scan()
        (self.plat / "ui-styles_assets_common.bundle").unlink()
        s = self.scan()
        self.assertEqual(s["missing"], 1)
        self.assertEqual(self.reg.get_bundle("ui-styles_assets_common.bundle")["state"], "missing")

    def test_cancel_keeps_finished_bundles_and_records_the_scan(self):
        calls = [0]

        def cancel():
            calls[0] += 1
            return calls[0] > 1                      # first bundle runs, then the cancel is seen
        with self.assertRaises(inventory.ScanCancelled) as cm:
            self.scan(cancel=cancel)
        self.assertEqual(cm.exception.summary["state"], "cancelled")
        self.assertEqual(self.reg.summary()["bundles"], 1)
        self.assertEqual(self.reg.summary()["last_scan"]["state"], "cancelled")
        s = self.scan()                              # the next scan finishes the rest
        self.assertEqual((s["new"], s["reused"]), (2, 1))

    def test_progress_reaches_the_end(self):
        seen = []
        self.scan(progress=lambda m, f: seen.append(f))
        self.assertEqual(seen[-1], 1.0)
        self.assertTrue(all(0.0 <= x <= 1.0 for x in seen))

    def test_kind_is_a_heuristic_from_the_name(self):
        self.assertEqual(inventory.kind_of("ui-styles_assets_default.bundle"), "ui-styles")
        self.assertEqual(inventory.kind_of("scenes_scenes_changingroomhighend.bundle"), "scenes")
        self.assertEqual(inventory.kind_of("odd.bundle"), "odd")


class TestRegistry(Base):
    def test_search_and_identity(self):
        inventory.scan(self.reg, self.prof["aa_roots"])
        r = self.reg.search_assets(q="selftest")
        self.assertEqual(r["total"], 3)                                   # the same object in three bundles: three distinct assets
        keys = {(a["bundle"], a["cab"], a["path_id"]) for a in r["assets"]}
        self.assertEqual(len(keys), 3)
        a = r["assets"][0]
        self.assertEqual(set(a["key"]), {"install_id", "bundle", "cab", "path_id"})
        self.assertEqual(a["key"]["install_id"], self.prof["install_id"])
        self.assertIsInstance(a["path_id"], str)                         # 64-bit ids are decimal strings
        self.assertEqual(self.reg.search_assets(type="TextAsset")["total"], 3)
        self.assertEqual(self.reg.search_assets(path_id="1", bundle="ui-styles_assets_default.bundle")["total"], 1)
        self.assertEqual(self.reg.search_assets(guid="0" * 32)["total"], 0)
        self.assertEqual(self.reg.get_asset("ui-styles_assets_default.bundle", "CAB-fmskinstudioselftest0000000", 1)["name"], "fm-skin-studio-selftest")
        self.assertIsNone(self.reg.get_asset("ui-styles_assets_default.bundle", "CAB-x", 1))

    def test_search_text_is_not_a_pattern(self):
        inventory.scan(self.reg, self.prof["aa_roots"])
        self.assertEqual(self.reg.search_assets(q="%")["total"], 0)
        self.assertEqual(self.reg.list_bundles(q="_")["total"], 3)       # every name contains an underscore (a literal one)
        self.assertEqual(self.reg.list_bundles(q="zzz")["total"], 0)

    def test_list_filters(self):
        inventory.scan(self.reg, self.prof["aa_roots"])
        self.assertEqual(self.reg.list_bundles(kind="ui-styles")["total"], 2)
        self.assertEqual(self.reg.list_bundles(state="valid", limit=1)["bundles"].__len__(), 1)

    def test_the_database_is_a_rebuildable_cache(self):
        inventory.scan(self.reg, self.prof["aa_roots"])
        first = {k: v["sha256"] for k, v in self.reg.all_bundles().items()}
        self.reg.path.unlink()
        reg2 = registry.Registry.for_install(self.ws, self.prof["install_id"])
        self.assertEqual(reg2.summary()["bundles"], 0)
        inventory.scan(reg2, self.prof["aa_roots"])
        self.assertEqual(first, {k: v["sha256"] for k, v in reg2.all_bundles().items()})

    def test_unknown_schema_is_refused_with_the_remedy(self):
        import sqlite3
        con = sqlite3.connect(str(self.reg.path))
        con.execute("UPDATE meta SET value='99' WHERE key='schema'")
        con.commit()
        con.close()
        with self.assertRaises(RuntimeError) as cm:
            registry.Registry(self.reg.path, self.prof["install_id"])
        self.assertIn("rebuildable", str(cm.exception))


class TestJobCancel(unittest.TestCase):
    def test_a_running_cancellable_job_is_asked_to_stop_and_keeps_its_partial_result(self):
        q = JobQueue()
        started = threading.Event()

        def fn(prog):
            started.set()
            for i in range(200):
                if prog.cancelled():
                    raise Cancelled({"done": i})
                time.sleep(0.01)
            return {"done": 200}
        job = q.submit("scan", fn, cancellable=True)
        self.assertTrue(started.wait(5))
        self.assertTrue(q.cancel(job.id))
        q.wait(job.id, 5)
        self.assertEqual(job.state, "cancelled")
        self.assertLess(job.result["done"], 200)
        self.assertTrue(job.view()["cancel_requested"])

    def test_a_running_job_that_is_not_cancellable_is_left_alone(self):
        q = JobQueue()
        started, release = threading.Event(), threading.Event()

        def fn(prog):
            started.set()
            release.wait(5)
            return "ok"
        job = q.submit("write", fn)
        self.assertTrue(started.wait(5))
        self.assertFalse(q.cancel(job.id))
        release.set()
        q.wait(job.id, 5)
        self.assertEqual((job.state, job.result), ("done", "ok"))

    def test_a_queued_job_is_still_cancelled_at_once(self):
        q = JobQueue()
        gate = threading.Event()
        first = q.submit("block", lambda prog: gate.wait(5))
        second = q.submit("later", lambda prog: 1)
        self.assertTrue(q.cancel(second.id))
        gate.set()
        q.wait(first.id, 5)
        self.assertEqual(second.state, "cancelled")


class TestMethodTable(unittest.TestCase):
    def test_methods_are_registered_with_schemas(self):
        from skin_editor.api.methods import methods
        from skin_editor.api.schema import SchemaError, validate
        m = methods()
        for name in ("install.profile_get", "install.profile_select", "inventory.scan", "inventory.status", "inventory.list", "inventory.get", "registry.search", "registry.get"):
            self.assertIn(name, m)
        self.assertEqual(m["inventory.scan"].kind, "job")
        validate(m["registry.search"].schema, {"path_id": "-8744014289983900540", "type": "MonoBehaviour"})
        with self.assertRaises(SchemaError):
            validate(m["registry.search"].schema, {"path_id": 12})            # path ids are decimal strings
        with self.assertRaises(SchemaError):
            validate(m["inventory.get"].schema, {})


class TestEngineRpc(unittest.TestCase):
    """The same services through the engine and the method table (the way the Studio will call them), in a scratch workspace and a mock installation."""

    def setUp(self):
        from unittest import mock
        from skin_editor.engine import Engine
        self.tmp = Path(tempfile.mkdtemp(prefix="fm27se-eng-"))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.addCleanup(self._close_logs)
        self.game, self.plat = make_install(self.tmp)
        with mock.patch.dict(os.environ, {"FM27SE_WORKSPACE": str(self.tmp / "ws")}):
            self.e = Engine()

    @staticmethod
    def _close_logs():
        import logging
        for h in list(logging.getLogger("skin_editor").handlers):
            logging.getLogger("skin_editor").removeHandler(h)
            h.close()

    def call(self, name, params=None):
        from skin_editor.api.methods import call, methods
        return call(self.e, methods()[name], params or {})

    def test_profile_scan_list_search_through_the_method_table(self):
        before = tree_hashes(self.game)
        empty = self.call("install.profile_get")
        self.assertIsNone(empty["profile"])
        sel = self.call("install.profile_select", {"game_dir": str(self.game), "role": "test", "game_build": "27.test"})
        self.assertEqual(sel["problems"], [])
        got = self.call("install.profile_get")
        self.assertEqual((got["profile"]["role"], got["drift"], got["active"]), ("test", [], sel["profile"]["install_id"]))
        job = self.call("inventory.scan", {})
        done = self.e.jobs.wait(job["job"], 60).view()
        self.assertEqual(done["state"], "done", done["error"])
        self.assertEqual(done["result"]["states"], {"valid": 3})
        self.assertEqual(self.call("inventory.status")["bundles"], 3)
        lst = self.call("inventory.list", {"q": "tiles"})
        self.assertEqual([b["filename"] for b in lst["bundles"]], ["ui-tileslayouts_assets_all.bundle"])
        one = self.call("inventory.get", {"path": "ui-tileslayouts_assets_all.bundle"})
        self.assertEqual((one["crc32"], one["asset_types"]), (FIXTURE_CRC, {"TextAsset": 1}))
        hit = self.call("registry.search", {"type": "TextAsset", "bundle": "ui-styles_assets_default.bundle"})
        self.assertEqual(hit["total"], 1)
        a = hit["assets"][0]
        self.assertEqual(self.call("registry.get", {"bundle": a["bundle"], "cab": a["cab"], "path_id": a["path_id"]})["name"], "fm-skin-studio-selftest")
        with self.assertRaises(KeyError):
            self.call("inventory.get", {"path": "nope.bundle"})
        self.assertEqual(before, tree_hashes(self.game))                  # nothing was written to the game folder, by any of the calls

    def test_selecting_a_folder_that_is_not_a_game_is_refused(self):
        with self.assertRaises(ValueError):
            self.call("install.profile_select", {"game_dir": str(self.tmp / "ws")})

    def test_a_scan_can_be_cancelled_through_jobs_cancel(self):
        for i in range(60):
            shutil.copyfile(FIXTURE, self.plat / ("extra%02d.bundle" % i))
        self.call("install.profile_select", {"game_dir": str(self.game)})
        gate = threading.Event()
        blocker = self.e.jobs.submit("hold the worker", lambda prog: gate.wait(10))
        job = self.call("inventory.scan", {"verify": True})
        self.assertTrue(self.call("jobs.cancel", {"id": job["job"]})["cancelled"])     # still queued: cancelled at once
        gate.set()
        self.e.jobs.wait(blocker.id, 10)
        self.assertEqual(self.e.jobs.get(job["job"]).state, "cancelled")


if __name__ == "__main__":
    unittest.main()
