"""Stage 4F: the installation transaction engine (skin_editor/installtx.py) and its journal (registry tables
`transactions` and `file_ops`). Every test works on a MOCK installation and copied fixtures in temporary directories;
the real game folder is never written, and the target files are copies of the committed synthetic bundle. Interruption
is simulated at each destructive boundary (before backup, after backup, after staging, immediately after replacement,
before completion, during rollback) by driving the journaled steps directly and by a REAL SEPARATE PROCESS that
re-opens the journal and reads the persisted state."""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from skin_editor import bundles, config, gameinstall, installtx, registry as registry_mod
from skin_editor.api import rpc

from test_api import close_logs, engine
from test_inventory import FIXTURE, make_install, tree_hashes

VARIANT_B = b"4F-test-variant-b"
VARIANT_C = b"4F-test-variant-c"


def variant(text):
    """A second valid synthetic bundle: the committed fixture with its TextAsset's script text changed."""
    import UnityPy
    env = UnityPy.load(str(FIXTURE))
    obj = next(o for o in env.objects)
    t = obj.read_typetree()
    t["m_Script"] = text.decode("latin1")
    obj.save_typetree(t)
    return env.file.save(packer="original")


def make_pkg(build_dir, entries, schema=2, game_build="27.test", outputs=None, extra=None):
    """A build folder holding a package: entries {name: (output_bytes, vanilla_sha256)}, a package.json (schema 1 or 2),
    a build-manifest.json and a build-report.json. A name that is not a writable file (an absolute path or traversal
    probe) is listed in the manifest without being written: the preflight must refuse it before any file is opened."""
    build_dir = Path(build_dir)
    build_dir.mkdir(parents=True, exist_ok=True)
    files = {}
    for name, (data, vanilla) in entries.items():
        writable = not any(c in name for c in ":/\\")
        if writable:
            (build_dir / name).write_bytes(data)
            files[name] = {"sha256": bundles.sha256(build_dir / name), "vanilla_sha256": vanilla}
        else:
            import hashlib
            files[name] = {"sha256": hashlib.sha256(data).hexdigest(), "vanilla_sha256": vanilla}
    pkg = {"schema": schema, "id": "20261118T000000Z", "project": "demo", "built_utc": "20261118T000000Z",
           "game_build": game_build, "files": files}
    if outputs is not None:
        pkg["outputs"] = outputs
    if schema == 2:
        pkg.update(gate={"passed": True, "failures": []}, target={}, edits=[], impact={}, overrides={}, tools={})
        pkg["installs"] = []
    if extra:
        pkg.update(extra)
    (build_dir / "package.json").write_text(json.dumps(pkg, indent=1), encoding="utf-8")
    man = dict(pkg, integrity_sources=None, validation=[], note="a stage-4F test package")
    (build_dir / "build-manifest.json").write_text(json.dumps(man, indent=1), encoding="utf-8")
    (build_dir / "build-report.json").write_text(json.dumps(
        {"project": "demo", "gate": {"fail": []},
         "files": {n: {"changed": True, "sha256": f["sha256"], "vanilla_sha256": f["vanilla_sha256"]}
                   for n, f in files.items()}}, indent=1), encoding="utf-8")
    return pkg


def integrity_outputs(entries, catalog="catalog_crc_mismatch", manifest="manifest_mismatch"):
    return [{"rel_path": n, "catalog_crc_status": catalog, "manifest_status": manifest,
             "integrity": {"catalog": {"resolution": "found", "comparison": catalog},
                            "manifest_dat": {"entry_status": "source match", "comparison": manifest},
                            "source_installation": {"install_id": "iid"}}}
            for n in entries]


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="fm27se-tx-"))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.game, self.plat = make_install(self.tmp)
        self.ws = config.Workspace(self.tmp / "ws")
        self.prof = gameinstall.describe_install(self.game, "test", "27.test")
        self.reg = registry_mod.Registry.for_install(self.ws, self.prof["install_id"])
        self.vanilla = FIXTURE.read_bytes()
        self.out_b, self.out_c = variant(VARIANT_B), variant(VARIANT_C)
        self.build = self.tmp / "build" / "20261118T000000Z"
        make_pkg(self.build, {"ui-styles_assets_common.bundle": (self.out_b, bundles.sha256(FIXTURE)),
                              "ui-styles_assets_default.bundle": (self.out_c, bundles.sha256(FIXTURE))})
        self.targets = [self.plat / "ui-styles_assets_common.bundle", self.plat / "ui-styles_assets_default.bundle"]
        self.orig = [bundles.sha256(t) for t in self.targets]

    def sha(self, p):
        return bundles.sha256(p)

    def txs(self, states=None):
        return self.reg.list_txs(states=states, limit=50)


class TestPreflight(Base):
    """Read-only inspection: package validation, identity, target states, Stage 4E integrity, explicit confirmations.
    Never modifies the package or the installation."""

    def test_a_valid_package_against_stock_targets_is_ready(self):
        before = tree_hashes(self.game)
        pf = installtx.preflight(self.ws, self.prof, self.build)
        self.assertTrue(pf["ready"], pf["blocked"])
        self.assertEqual(pf["blocked"], [])
        self.assertEqual([o["rel_path"] for o in pf["file_operations"]], ["ui-styles_assets_common.bundle", "ui-styles_assets_default.bundle"])
        self.assertTrue(all(o["target_state"] == "stock" for o in pf["file_operations"]))
        self.assertEqual(pf["required_confirmations"], [])
        self.assertEqual(pf["package_identity"]["schema"], 2)
        self.assertEqual(before, tree_hashes(self.game))                    # preflight wrote nothing

    def test_integrity_mismatches_are_warnings_that_need_confirmation_never_blocks(self):
        make_pkg(self.build, {"ui-styles_assets_common.bundle": (self.out_b, bundles.sha256(FIXTURE))},
                 outputs=integrity_outputs({"ui-styles_assets_common.bundle": (self.out_b, "x")}))
        pf = installtx.preflight(self.ws, self.prof, self.build)
        self.assertTrue(pf["ready"], pf["blocked"])
        # the synthetic installation has no catalog record for the fixture: live preflight is authoritative and
        # reports the manifest mismatch; the catalog status is the live "record missing", not the package's claim
        self.assertEqual(sorted(pf["required_confirmations"]), ["manifest_mismatch"])
        self.assertIn("manifest.dat holds the ORIGINAL whole-file CRC",
                      [w["message"] for w in pf["warnings"] if w["code"] == "manifest_mismatch"][0])   # the Stage 3G caveat travels with it

    def test_preflight_itself_compares_manifest_dat_against_the_installation(self):
        import struct
        import zlib
        # the package carries NO manifest status; preflight must read the installation's manifest.dat itself
        fm_data = self.game / "fm_Data"
        fm_data.mkdir(parents=True, exist_ok=True)
        crc = zlib.crc32(self.vanilla) & 0xFFFFFFFF
        (fm_data / "manifest.dat").write_bytes(b"\x00" * 4 + struct.pack("<I", crc) + b"\x00" * 4)
        make_pkg(self.build, {"ui-styles_assets_common.bundle": (self.out_b, bundles.sha256(FIXTURE))})
        pf = installtx.preflight(self.ws, self.prof, self.build)
        self.assertIn("manifest_mismatch", pf["required_confirmations"], pf["integrity_summary"])
        self.assertIn("manifest_mismatch", [w["code"] for w in pf["warnings"]])

    def test_integrityless_and_schema1_packages_are_ready(self):
        make_pkg(self.build, {"ui-styles_assets_common.bundle": (self.out_b, bundles.sha256(FIXTURE))})
        pf = installtx.preflight(self.ws, self.prof, self.build)
        self.assertTrue(pf["ready"])
        self.assertTrue(all(row["catalog_crc_status"] in ("not_checked", "catalog_record_missing")
                            for row in pf["integrity_summary"]))     # reported, not silently dropped
        make_pkg(self.build, {"ui-styles_assets_common.bundle": (self.out_b, bundles.sha256(FIXTURE))}, schema=1)
        pf = installtx.preflight(self.ws, self.prof, self.build)
        self.assertTrue(pf["ready"])
        self.assertEqual(pf["package_identity"]["schema"], 1)

    def test_a_broken_package_is_blocked_and_never_confirmed_away(self):
        (self.build / "ui-styles_assets_common.bundle").unlink()
        pf = installtx.preflight(self.ws, self.prof, self.build)
        self.assertEqual(pf["blocked"][0]["code"], "missing_package_file")
        make_pkg(self.build, {"ui-styles_assets_common.bundle": (self.out_b, bundles.sha256(FIXTURE))})
        (self.build / "ui-styles_assets_common.bundle").write_bytes(b"corrupted away from its package hash")
        pf = installtx.preflight(self.ws, self.prof, self.build)
        self.assertIn("invalid_package_hash", [b["code"] for b in pf["blocked"]])
        (self.build / "package.json").unlink()
        pf = installtx.preflight(self.ws, self.prof, self.build)
        self.assertIn("invalid_package", [b["code"] for b in pf["blocked"]])
        (self.build / "package.json").write_text(json.dumps({"schema": 3}))
        pf = installtx.preflight(self.ws, self.prof, self.build)
        self.assertIn("invalid_package", [b["code"] for b in pf["blocked"]])

    def test_duplicate_outputs_and_unsafe_paths_block(self):
        out = integrity_outputs({"ui-styles_assets_common.bundle": (self.out_b, "x")})
        out.append(dict(out[0]))
        make_pkg(self.build, {"ui-styles_assets_common.bundle": (self.out_b, bundles.sha256(FIXTURE))}, outputs=out)
        self.assertIn("duplicate_output", [b["code"] for b in installtx.preflight(self.ws, self.prof, self.build)["blocked"]])
        pkg = make_pkg(self.build, {"../evil.bundle": (self.out_b, bundles.sha256(FIXTURE))})
        self.assertIn("unsafe_path", [b["code"] for b in installtx.preflight(self.ws, self.prof, self.build)["blocked"]])
        make_pkg(self.build, {r"C:\abs\evil.bundle": (self.out_b, bundles.sha256(FIXTURE))})
        self.assertIn("unsafe_path", [b["code"] for b in installtx.preflight(self.ws, self.prof, self.build)["blocked"]])

    def test_a_stale_game_build_or_stale_installation_blocks_and_is_never_confirmable(self):
        make_pkg(self.build, {"ui-styles_assets_common.bundle": (self.out_b, bundles.sha256(FIXTURE))},
                 game_build="27.other")
        pf = installtx.preflight(self.ws, self.prof, self.build)
        self.assertEqual([b["code"] for b in pf["blocked"]], ["stale_game_build"])
        self.assertNotIn("stale_game_build", pf["required_confirmations"])
        make_pkg(self.build, {"ui-styles_assets_common.bundle": (self.out_b, bundles.sha256(FIXTURE))})
        (self.plat.parent / "catalog.bin").write_bytes(b"a different catalog: the game was updated")
        pf = installtx.preflight(self.ws, self.prof, self.build)
        self.assertEqual([b["code"] for b in pf["blocked"]], ["stale_installation_identity"])

    def test_missing_and_changed_targets(self):
        make_pkg(self.build, {"ui-styles_assets_gone.bundle": (self.out_b, bundles.sha256(FIXTURE))})
        pf = installtx.preflight(self.ws, self.prof, self.build)
        self.assertIn("missing_target", [b["code"] for b in pf["blocked"]])
        make_pkg(self.build, {"ui-styles_assets_common.bundle": (self.out_c, bundles.sha256(FIXTURE))})
        (self.targets[0]).write_bytes(self.out_b)                    # a VALID bundle, changed by something else
        pf = installtx.preflight(self.ws, self.prof, self.build)
        self.assertEqual([b["code"] for b in pf["blocked"]], ["changed_target"])
        self.assertEqual(pf["required_confirmations"], ["changed_target"])       # the one overridable condition


class TestApply(Base):
    """The complete transaction: verified backups, staged and atomic replacement, post-write verification, the
    journal, the installs array - and every failure leaving the originals or a clearly journalled recoverable state."""

    def apply(self, **kw):
        return installtx.apply(self.ws, self.prof, self.build, **kw)

    def test_a_successful_multi_file_install_is_journalled_and_verified(self):
        before = {n: self.sha(t) for n, t in zip(("a", "b"), self.targets)}
        rec = self.apply()
        self.assertEqual(rec["state"], "completed")
        self.assertEqual([self.sha(t) for t in self.targets], [bundles.sha256(self.build / n)
                         for n in ("ui-styles_assets_common.bundle", "ui-styles_assets_default.bundle")])
        ops = self.reg.get_ops(rec["tx_id"])
        self.assertEqual([o["state"] for o in ops], ["replaced", "replaced"])
        self.assertEqual([o["verify"] for o in ops], ["match", "match"])
        self.assertEqual([o["rollback_state"] for o in ops], [None, None])
        backups = [Path(o["backup_path"]) for o in ops]
        for b, h in zip(backups, [before["a"], before["b"]]):
            self.assertTrue(b.is_file() and self.sha(b) == h)                 # verified backups of the originals
        # the installs array, in both schema 2 files, with the journal's identity
        for name in ("package.json", "build-manifest.json"):
            d = json.loads((self.build / name).read_text(encoding="utf-8"))
            self.assertEqual(len(d["installs"]), 1)
            r = d["installs"][0]
            self.assertEqual(r["tx_id"], rec["tx_id"])
            self.assertEqual(r["status"], "completed")
            self.assertEqual([f["rel_path"] for f in r["files"]], ["ui-styles_assets_common.bundle", "ui-styles_assets_default.bundle"])
            self.assertEqual(r["files"][0]["original_sha256"], before["a"])
        self.assertIn("note", json.loads((self.build / "build-manifest.json").read_text(encoding="utf-8")))  # unknown fields kept
        log = (self.ws.logs / "install-log.jsonl").read_text(encoding="utf-8")
        self.assertIn(rec["tx_id"], log)                                       # the legacy log knows the transaction too

    def test_unapproved_or_unknown_confirmations_refuse_without_writing(self):
        make_pkg(self.build, {"ui-styles_assets_common.bundle": (self.out_b, bundles.sha256(FIXTURE))},
                 outputs=integrity_outputs({"ui-styles_assets_common.bundle": (self.out_b, "x")}))
        before = tree_hashes(self.game)
        with self.assertRaises(installtx.InstallRefused) as c:
            self.apply()
        self.assertIn("needs explicit confirmation", str(c.exception))
        self.assertEqual(self.txs()[0]["state"], "failed")
        with self.assertRaises(installtx.InstallRefused) as c:
            self.apply(confirmations=["force"])
        self.assertIn("unknown confirmations", str(c.exception))
        self.assertEqual(before, tree_hashes(self.game))

    def test_a_stale_build_refuses_without_writing(self):
        make_pkg(self.build, {"ui-styles_assets_common.bundle": (self.out_b, bundles.sha256(FIXTURE))}, game_build="27.other")
        before = tree_hashes(self.game)
        with self.assertRaises(installtx.InstallRefused):
            self.apply()
        self.assertEqual(self.txs()[0]["state"], "failed")
        self.assertEqual(before, tree_hashes(self.game))

    def test_the_game_running_refuses(self):
        with self.assertRaises(installtx.InstallRefused) as c:
            self.apply(running=lambda: True)
        self.assertIn("the game is running", str(c.exception))

    def test_a_changed_target_installs_only_with_its_recorded_confirmation(self):
        (self.targets[0]).write_bytes(self.out_c)                   # a valid bundle changed by something else
        changed = self.sha(self.targets[0])
        with self.assertRaises(installtx.InstallRefused):
            self.apply()
        rec = self.apply(confirmations=["changed_target"])
        self.assertEqual(rec["state"], "completed")
        ops = self.reg.get_ops(rec["tx_id"])
        self.assertEqual(ops[0]["original_sha256"], changed)                   # the CURRENT state was backed up
        self.assertEqual(json.loads((self.build / "package.json").read_text())["installs"][0]["approved_overrides"],
                         ["changed_target"])

    def test_a_target_changed_between_backup_and_replacement_conflicts_and_rolls_back(self):
        pf = installtx.preflight(self.ws, self.prof, self.build)
        tx_id = installtx._new_tx_id()
        self.reg.begin_tx({"tx_id": tx_id, "install_id": self.prof["install_id"], "state": "created",
                           "created_utc": installtx._now(), "updated_utc": installtx._now(),
                           "package_dir": str(self.build)})
        installtx._backup(self.ws, self.reg, tx_id, self.prof, pf["file_operations"], lambda m, f: None, lambda: False)
        (self.targets[0]).write_bytes(b"independently changed mid-flight")     # between the backup and the replacement
        with self.assertRaises(installtx._Rollback) as c:
            installtx._install(self.ws, self.reg, tx_id, self.prof, list(enumerate(pf["file_operations"])),
                                lambda m, f: None, lambda: False)
        self.assertIn("changed since preflight", str(c.exception))

    def test_a_corrupted_staged_file_rolls_back_before_any_replacement(self):
        pf = installtx.preflight(self.ws, self.prof, self.build)
        tx_id = installtx._new_tx_id()
        self.reg.begin_tx({"tx_id": tx_id, "install_id": self.prof["install_id"], "state": "created",
                           "created_utc": installtx._now(), "updated_utc": installtx._now(), "package_dir": str(self.build)})
        installtx._backup(self.ws, self.reg, tx_id, self.prof, pf["file_operations"], lambda m, f: None, lambda: False)
        (self.build / "ui-styles_assets_common.bundle").write_bytes(b"the package file was corrupted in flight")
        before = tree_hashes(self.game)
        with self.assertRaises(installtx._Rollback) as c:
            installtx._install(self.ws, self.reg, tx_id, self.prof, list(enumerate(pf["file_operations"])),
                               lambda m, f: None, lambda: False)
        self.assertIn("did not match the package SHA-256", str(c.exception))
        self.assertEqual(before, tree_hashes(self.game))                      # nothing was replaced

    def test_a_failure_after_the_first_of_several_replacements_rolls_everything_back(self):
        real_copy = installtx._copy_verified
        state = {"n": 0}

        def flaky(src, dst):
            if dst.name.endswith(".tmp") and "ui-styles_assets_default" in dst.name:
                dst.write_bytes(b"corruption during the second stage")         # the second stage turns to garbage
                return
            real_copy(src, dst)
        with mock.patch.object(installtx, "_copy_verified", flaky):
            with self.assertRaises(installtx.InstallRefused):
                self.apply()
        tx = self.txs()[0]
        self.assertEqual(tx["state"], "rolled_back")                          # the exact original state, verified
        self.assertEqual([self.sha(t) for t in self.targets], self.orig)
        ops = self.reg.get_ops(tx["tx_id"])
        self.assertEqual([o["rollback_state"] for o in ops], ["rolled_back", "rolled_back"])
        self.assertEqual([o["state"] for o in ops], ["replaced", "stage_failed"])

    def test_a_cancel_before_the_first_replacement_leaves_a_recoverable_state(self):
        before = tree_hashes(self.game)
        with self.assertRaises(installtx.Cancelled):
            self.apply(cancel=lambda: True)
        tx = self.txs()[0]
        self.assertIn(tx["state"], installtx.BUSY_STATES)
        self.assertIn("cancelled", tx["error"])
        self.assertEqual(before, tree_hashes(self.game))
        # and a new transaction is refused until this one is resolved
        with self.assertRaises(installtx.InstallRefused) as c:
            self.apply()
        self.assertIn("unfinished", str(c.exception))

    def test_a_cancel_between_replacements_is_journalled_and_recoverable(self):
        state = {"n": 0}

        def cancel_after_first():
            state["n"] += 1
            return state["n"] > 3                                               # after the first file's steps
        with self.assertRaises(installtx.Cancelled):
            self.apply(cancel=cancel_after_first)
        tx = self.txs()[0]
        self.assertEqual(tx["state"], "installing")
        self.assertEqual(self.sha(self.targets[0]), bundles.sha256(self.build / "ui-styles_assets_common.bundle"))
        self.assertEqual(self.sha(self.targets[1]), self.orig[1])              # a clearly journalled mid-state
        scan = installtx.recovery_scan(self.ws, self.prof)
        one = scan["transactions"][0]
        self.assertEqual(one["replaced"], 1)
        self.assertIn("rollback", one["safe_actions"])
        rec = installtx.recover(self.ws, self.prof, tx["tx_id"], "rollback")
        self.assertEqual(rec["state"], "rolled_back")
        self.assertEqual([self.sha(t) for t in self.targets], self.orig)

    def test_a_manifest_write_failure_never_erases_the_transaction_history(self):
        # sabotage only the manifest UPDATE: the build-manifest becomes unreadable, the package stays valid
        (self.build / "build-manifest.json").unlink()
        (self.build / "build-manifest.json").mkdir()
        rec = self.apply()
        self.assertEqual(rec["state"], "completed")                            # the journal survives the manifest
        self.assertIn("build-manifest.json", rec["recovery"])                 # the failure is reported, not hidden
        self.assertEqual(len(json.loads((self.build / "package.json").read_text())["installs"]), 1)


class TestRollback(Base):
    def test_rollback_of_a_completed_install_restores_and_verifies_the_exact_originals(self):
        rec = installtx.apply(self.ws, self.prof, self.build)
        out = installtx.rollback(self.ws, self.reg, self.prof, rec["tx_id"])
        self.assertEqual(out["state"], "rolled_back")
        self.assertEqual([self.sha(t) for t in self.targets], self.orig)
        r = json.loads((self.build / "package.json").read_text())["installs"][0]
        self.assertEqual(r["rollback"]["status"], "rolled_back")
        again = installtx.rollback(self.ws, self.reg, self.prof, rec["tx_id"])   # idempotent
        self.assertEqual(again["state"], "rolled_back")

    def test_a_corrupt_backup_fails_the_rollback_and_overwrites_nothing(self):
        rec = installtx.apply(self.ws, self.prof, self.build)
        ops = self.reg.get_ops(rec["tx_id"])
        Path(ops[0]["backup_path"]).write_bytes(b"a corrupt backup")
        installed = self.sha(self.targets[0])
        out = installtx.rollback(self.ws, self.reg, self.prof, rec["tx_id"])
        self.assertEqual(out["state"], "rollback_failed")
        self.assertEqual(self.sha(self.targets[0]), installed)                 # NOT overwritten by a corrupt restore
        self.assertEqual(self.reg.get_ops(rec["tx_id"])[0]["rollback_state"], "backup_failed")
        self.assertIn("manual", str(out["error"]))

    def test_an_independently_changed_target_is_never_overwritten(self):
        rec = installtx.apply(self.ws, self.prof, self.build)
        (self.targets[0]).write_bytes(b"changed by the user after the install")
        changed = self.sha(self.targets[0])
        out = installtx.rollback(self.ws, self.reg, self.prof, rec["tx_id"])
        self.assertEqual(out["state"], "rollback_failed")
        self.assertEqual(self.sha(self.targets[0]), changed)                   # the user's change was preserved
        self.assertEqual(self.sha(self.targets[1]), self.orig[1])              # the clean file was restored
        self.assertIn("changed independently", out["error"])

    def test_a_file_the_transaction_created_is_removed_only_if_it_still_is_the_output(self):
        tx_id = installtx._new_tx_id()
        self.reg.begin_tx({"tx_id": tx_id, "install_id": self.prof["install_id"], "state": "rollback_required",
                           "created_utc": installtx._now(), "updated_utc": installtx._now(), "package_dir": str(self.build)})
        new = self.plat / "ui-created-by-the-transaction.bundle"
        new.write_bytes(self.out_b)
        self.reg.put_op(tx_id, 0, {"rel_path": new.name, "op": "replace", "target_path": str(new),
                                   "original_exists": 0, "expected_sha256": bundles.sha256(self.build / "ui-styles_assets_common.bundle"),
                                   "actual_sha256": self.sha(new), "state": "replaced"})
        out = installtx.rollback(self.ws, self.reg, self.prof, tx_id)
        self.assertEqual((out["state"], new.exists()), ("rolled_back", False))
        new.write_bytes(b"changed by the user after the transaction created it")
        self.reg.put_op(tx_id, 0, {"rel_path": new.name, "op": "replace", "target_path": str(new), "original_exists": 0,
                                   "actual_sha256": self.sha(self.build / "ui-styles_assets_common.bundle"), "state": "replaced"})
        out = installtx.rollback(self.ws, self.reg, self.prof, tx_id)
        self.assertEqual(out["state"], "rollback_failed")                       # an independent change is never deleted
        self.assertTrue(new.is_file())


class TestRecovery(Base):
    """Simulated interruption at the destructive boundaries, recovery decided from PERSISTED state, idempotence, and
    one REAL separate process re-reading the journal."""

    def interrupted(self, state, replaced_first=False, tamper=False):
        """A transaction journalled exactly as an interruption at a boundary would leave it."""
        pf = installtx.preflight(self.ws, self.prof, self.build)
        tx_id = installtx._new_tx_id()
        self.reg.begin_tx({"tx_id": tx_id, "install_id": self.prof["install_id"], "state": state,
                           "created_utc": installtx._now(), "updated_utc": installtx._now(),
                           "package_dir": str(self.build), "preflight": json.dumps(pf, default=str),
                           "overrides": "[]"})
        if state in ("backup_in_progress", "backups_verified", "installing", "verifying"):
            installtx._backup(self.ws, self.reg, tx_id, self.prof, pf["file_operations"], lambda m, f: None, lambda: False)
        if replaced_first:
            self.reg.put_op(tx_id, 0, dict(self.reg.get_ops(tx_id)[0], state="replaced",
                                           actual_sha256=bundles.sha256(self.build / "ui-styles_assets_common.bundle")))
            _copy_into(self.build / "ui-styles_assets_common.bundle", self.targets[0])
        if tamper:
            (self.targets[0]).write_bytes(b"independently changed while the app was away")
        return tx_id, pf

    def test_interruption_after_the_backup_before_any_replacement(self):
        tx_id, _ = self.interrupted("backups_verified")
        scan = installtx.recovery_scan(self.ws, self.prof)
        self.assertEqual(scan["transactions"][0]["safe_actions"], ["rollback", "resume"])
        self.assertEqual(scan["transactions"][0]["recommendation"], "rollback")
        out = installtx.recover(self.ws, self.prof, tx_id, "rollback")
        self.assertEqual(out["state"], "rolled_back")                          # the originals were never touched
        self.assertEqual([self.sha(t) for t in self.targets], self.orig)

    def test_interruption_mid_install_resumes_idempotently_and_completes(self):
        tx_id, _ = self.interrupted("installing", replaced_first=True)
        scan = installtx.recovery_scan(self.ws, self.prof)
        self.assertEqual(scan["transactions"][0]["replaced"], 1)
        self.assertIn("resume", scan["transactions"][0]["safe_actions"])
        out = installtx.recover(self.ws, self.prof, tx_id, "resume")
        self.assertEqual(out["state"], "completed")
        self.assertEqual([self.sha(t) for t in self.targets],
                         [bundles.sha256(self.build / n) for n in ("ui-styles_assets_common.bundle", "ui-styles_assets_default.bundle")])
        self.assertEqual(len(json.loads((self.build / "package.json").read_text())["installs"]), 1)
        with self.assertRaises(installtx.InstallRefused):                      # never accidentally re-installed
            installtx.recover(self.ws, self.prof, tx_id, "resume")

    def test_an_independently_changed_target_refuses_resume_and_conflicts_on_rollback(self):
        tx_id, _ = self.interrupted("installing", replaced_first=True, tamper=True)
        scan = installtx.recovery_scan(self.ws, self.prof)
        self.assertEqual(scan["transactions"][0]["recommendation"], "manual")
        with self.assertRaises(installtx.InstallRefused) as c:
            installtx.recover(self.ws, self.prof, tx_id, "resume")
        self.assertIn("resume is refused", str(c.exception))
        self.assertIn("roll back", str(c.exception))
        out = installtx.recover(self.ws, self.prof, tx_id, "rollback")
        self.assertEqual(out["state"], "rollback_failed")                      # the user's change was left alone
        self.assertIn(b"independently changed", self.targets[0].read_bytes())

    def test_the_journal_is_read_back_correctly_by_a_real_separate_process(self):
        tx_id, _ = self.interrupted("backups_verified")
        prof_file = self.tmp / "prof.json"
        prof_file.write_text(json.dumps(self.prof), encoding="utf-8")        # JSON in, JSON out: no literal injection
        code = ("import json, sys; sys.path.insert(0, %r); from skin_editor import config, installtx, "
                "registry as rm; ws = config.Workspace(%r); prof = json.loads(open(%r, encoding='utf-8').read()); "
                "reg = rm.Registry.for_install(ws, prof['install_id']); tx = reg.get_tx(%r); "
                "scan = installtx.recovery_scan(ws, prof); "
                "print(json.dumps({'state': tx['state'], 'ops': len(reg.get_ops(tx['tx_id'])), "
                "'scan_states': [t['state'] for t in scan['transactions']]}))")
        args = (str(Path(__file__).resolve().parent.parent), str(self.ws.root), str(prof_file), tx_id)
        out = subprocess.run([sys.executable, "-c", code % args], capture_output=True, text=True, timeout=120)
        self.assertEqual(out.returncode, 0, out.stderr)
        d = json.loads(out.stdout.strip().splitlines()[-1])
        self.assertEqual(d, {"state": "backups_verified", "ops": 2, "scan_states": ["backups_verified"]})

    def test_recovery_from_a_fresh_connection_uses_the_persisted_state(self):
        tx_id, _ = self.interrupted("backups_verified")
        fresh = registry_mod.Registry.for_install(self.ws, self.prof["install_id"])
        self.assertEqual(fresh.get_tx(tx_id)["state"], "backups_verified")
        scan = installtx.recovery_scan(self.ws, self.prof)                     # decided from the journal + the disk
        self.assertEqual(scan["transactions"][0]["tx_id"], tx_id)

    def test_manual_intervention_modifies_nothing(self):
        tx_id, _ = self.interrupted("backups_verified")
        before = tree_hashes(self.game)
        out = installtx.recover(self.ws, self.prof, tx_id, "manual")
        self.assertEqual(out["state"], "manual_intervention")
        self.assertEqual(before, tree_hashes(self.game))
        with self.assertRaises(installtx.InstallRefused):                      # it still blocks new transactions
            installtx.apply(self.ws, self.prof, self.build)
        self.assertEqual(installtx.recover(self.ws, self.prof, tx_id, "rollback")["state"], "rolled_back")


def _copy_into(src, dst):
    installtx._copy_verified(Path(src), Path(dst))


class TestEngineMethods(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.addCleanup(self.tmp.cleanup)
        self.addCleanup(close_logs)
        self.e = engine(self.tmp.name)
        # the process check is INJECTED: the tests never read the real process table, so the result cannot depend
        # on whether Football Manager is open on the machine running them (the game is mocked as closed here)
        self.e._running_override = False
        self.game, self.plat = make_install(Path(self.tmp.name) / "game")
        self.ws = self.e.ws
        self.prof = gameinstall.describe_install(self.game, "test", "27.test")
        gameinstall.save(self.ws, self.prof)
        out = variant(VARIANT_B)
        d = self.ws.build / "demo" / "20261118T000000Z"
        make_pkg(d, {"ui-styles_assets_common.bundle": (out, bundles.sha256(FIXTURE))})
        (self.ws.projects / "demo").mkdir(parents=True, exist_ok=True)

    def select_game(self):
        """The engine's own configured-game state (self.info / self.running) points at the mock install - set
        DIRECTLY, never through `game.select`: that method persists the choice to config.json, and the engine
        fixture's FM27SE_WORKSPACE redirection is only active during Engine(), so a later RPC would write the
        LIVE config of the person running the tests."""
        from skin_editor import detect
        self.e.info = detect.describe(str(self.game))
        self.assertIsNotNone(self.e.info)

    def call(self, method, params=None, want_error=False):
        r = json.loads(rpc.handle(self.e, json.dumps({"jsonrpc": "2.0", "method": method, "id": 1, "params": params or {}})))
        if want_error:
            return r
        self.assertNotIn("error", r, r)
        return r["result"]

    def job(self, method, params=None):
        j = self.call(method, params)["job"]
        done = self.e.jobs.wait(j, 60).view()
        self.assertEqual(done["state"], "done", done["error"])
        return done["result"]

    def test_preflight_apply_history_transaction_and_rollback_through_the_api(self):
        self.select_game()
        before = tree_hashes(self.game)
        pf = self.call("install.preflight", {"project": "demo"})
        self.assertTrue(pf["ready"], pf["blocked"])
        self.assertEqual(before, tree_hashes(self.game))                      # preflight through the API wrote nothing
        rec = self.job("install.apply", {"project": "demo"})
        self.assertEqual(rec["state"], "completed")
        self.assertEqual(bundles.sha256(self.plat / "ui-styles_assets_common.bundle"),
                         bundles.sha256(self.ws.build / "demo" / "20261118T000000Z" / "ui-styles_assets_common.bundle"))
        hist = self.call("install.history", {})
        self.assertEqual(hist["transactions"][0]["tx_id"], rec["tx_id"])
        self.assertEqual(hist["recovery_required"], [])
        one = self.call("install.transaction", {"tx_id": rec["tx_id"]})
        self.assertEqual(len(one["file_operations"]), 1)
        self.assertEqual(one["file_operations"][0]["state"], "replaced")
        out = self.job("install.rollback", {"tx_id": rec["tx_id"]})
        self.assertEqual(out["state"], "rolled_back")
        scan = self.call("install.recovery_scan", {})
        self.assertEqual(scan["transactions"], [])
        r = self.call("install.transaction", {"tx_id": "nope"}, want_error=True)
        self.assertEqual(r["error"]["code"], -32004)

    def test_preflight_requires_both_crc_and_manifest_confirmations(self):
        from skin_editor import installtx as _tx
        pkg = {"outputs": [{"rel_path": "ui-styles_assets_common.bundle",
                            "catalog_crc_status": "catalog_crc_mismatch",
                            "manifest_status": "manifest_mismatch"}]}
        warnings, confirmations = [], []
        rows = _tx._integrity_summary(pkg, warnings, confirmations, [])
        names = [c if isinstance(c, str) else c.get("name") for c in confirmations]
        self.assertIn("catalog_crc_mismatch", names)
        self.assertIn("manifest_mismatch", names)
        self.assertEqual({w["code"] for w in warnings}, {"catalog_crc_mismatch", "manifest_mismatch"})
        self.assertEqual(len(rows), 1)

    def test_the_running_check_is_injected_and_refuses_explicitly(self):
        self.select_game()
        self.e._running_override = True
        before = tree_hashes(self.game)
        r = json.loads(rpc.handle(self.e, json.dumps({"jsonrpc": "2.0", "method": "install.apply", "id": 1,
                                                      "params": {"project": "demo"}})))
        done = self.e.jobs.wait(r["result"]["job"], 60).view()
        self.assertEqual(done["state"], "failed")
        self.assertIn("the game is running", done["error"])
        self.assertEqual(before, tree_hashes(self.game))                 # nothing was written
        self.e._running_override = False
        rec = self.job("install.apply", {"project": "demo"})
        self.assertEqual(rec["state"], "completed")                      # game closed: the same call succeeds

    def test_the_legacy_install_route_still_works_alongside_the_transactions(self):
        self.select_game()
        rep = self.call("install.preflight", {"project": "demo"})
        self.assertTrue(rep["ready"])
        r = self.call("install.bundles", {"name": "demo"})                    # the pre-4F route, unchanged and working
        self.assertEqual(r["copied"], ["ui-styles_assets_common.bundle"])
        self.assertEqual(bundles.sha256(self.plat / "ui-styles_assets_common.bundle"),
                         bundles.sha256(self.ws.build / "demo" / "20261118T000000Z" / "ui-styles_assets_common.bundle"))


if __name__ == "__main__":
    unittest.main()
