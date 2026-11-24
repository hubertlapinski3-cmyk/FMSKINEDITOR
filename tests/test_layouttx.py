"""ST1 part B: the custom-layout transaction (preflight, apply, byte-exact rollback, recovery scan). Temporary folders only; never the live CustomGridCompositions."""
import hashlib
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from skin_editor import layouttx


def sha(b):
    return hashlib.sha256(b).hexdigest()


class Base(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix="fm27se-ltx-"))
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)
        self.folder = self.root / "CustomGridCompositions"
        self.journal = self.root / "journal"
        self.pkg = self.root / "package"

    def package(self, files):
        (self.pkg / "custom-layouts").mkdir(parents=True, exist_ok=True)
        rows = []
        for name, data in files.items():
            (self.pkg / "custom-layouts" / name).write_bytes(data)
            rows.append({"name": name, "composition": name, "size": len(data), "sha256": sha(data)})
        (self.pkg / "custom-layouts.json").write_text(json.dumps({"schema": "fm-customlayouts/1", "files": rows}), encoding="utf-8")

    def user_folder(self, files):
        self.folder.mkdir(parents=True, exist_ok=True)
        for name, data in files.items():
            (self.folder / name).write_bytes(data)

    def state(self):
        return {p.name: p.read_bytes() for p in sorted(self.folder.iterdir())} if self.folder.is_dir() else None

    def crash_after_first_write(self, **kw):
        """Apply with the second file's copy failing and the automatic rollback 'crashing': the transaction stays unfinished, as after a power cut."""
        real = layouttx.shutil.copyfile
        calls = {"n": 0}

        def flaky(src, dst):
            calls["n"] += 1
            if calls["n"] == 2:
                raise OSError("power cut")
            return real(src, dst)

        with mock.patch.object(layouttx, "rollback", side_effect=KeyboardInterrupt):
            with mock.patch.object(layouttx.shutil, "copyfile", flaky):
                with self.assertRaises(KeyboardInterrupt):
                    layouttx.apply(self.journal, self.pkg, self.folder, **kw)


class Preflight(Base):
    def test_lists_every_file_and_flags_the_users_own_one_with_a_confirmation(self):
        self.user_folder({"Mine": b"user layout", "Same": b"same"})
        self.package({"New": b"new file", "Mine": b"ours", "Same": b"same"})
        before = self.state()
        pf = layouttx.preflight(self.pkg, self.folder, self.journal)
        self.assertTrue(pf["ready"])
        states = {o["name"]: o["state"] for o in pf["file_operations"]}
        self.assertEqual(states, {"New": "new", "Mine": "replaces_user_file", "Same": "already_this_package"})
        self.assertEqual(pf["required_confirmations"], ["replace:Mine"])
        self.assertIn("customised in the game", pf["confirmation_reasons"]["replace:Mine"])
        self.assertEqual(self.state(), before)                                               # read only

    def test_blocks_a_damaged_missing_or_unsafe_package(self):
        self.package({"A": b"a"})
        (self.pkg / "custom-layouts" / "A").write_bytes(b"tampered")
        self.assertEqual([b["code"] for b in layouttx.preflight(self.pkg, self.folder)["blocked"]], ["invalid_package_hash"])
        (self.pkg / "custom-layouts" / "A").unlink()
        self.assertEqual([b["code"] for b in layouttx.preflight(self.pkg, self.folder)["blocked"]], ["missing_package_file"])
        meta = json.loads((self.pkg / "custom-layouts.json").read_text(encoding="utf-8"))
        meta["files"][0]["name"] = "../evil"
        (self.pkg / "custom-layouts.json").write_text(json.dumps(meta), encoding="utf-8")
        self.assertEqual([b["code"] for b in layouttx.preflight(self.pkg, self.folder)["blocked"]], ["unsafe_path"])
        self.assertEqual([b["code"] for b in layouttx.preflight(self.root / "nothing", self.folder)["blocked"]], ["invalid_package"])

    def test_a_missing_folder_is_a_warning_not_a_block(self):
        self.package({"A": b"a"})
        pf = layouttx.preflight(self.pkg, self.folder)
        self.assertTrue(pf["ready"])
        self.assertEqual([w["code"] for w in pf["warnings"]], ["folder_missing"])


class ApplyRollback(Base):
    def test_a_replace_needs_the_confirmation_and_nothing_is_written_without_it(self):
        self.user_folder({"Mine": b"user layout"})
        self.package({"Mine": b"ours"})
        before = self.state()
        with self.assertRaises(layouttx.LayoutTxRefused) as cm:
            layouttx.apply(self.journal, self.pkg, self.folder)
        self.assertEqual(cm.exception.confirmations, ["replace:Mine"])
        self.assertEqual(self.state(), before)

    def test_apply_backs_up_first_writes_verifies_and_journals(self):
        self.user_folder({"Mine": b"user layout", "Other": b"other"})
        self.package({"Mine": b"ours", "New": b"brand new"})
        tx = layouttx.apply(self.journal, self.pkg, self.folder, confirmations=["replace:Mine"])
        self.assertEqual(tx["state"], "completed")
        self.assertEqual(self.state(), {"Mine": b"ours", "Other": b"other", "New": b"brand new"})
        backup = self.journal / tx["tx_id"] / "backup"
        self.assertEqual((backup / "Mine").read_bytes(), b"user layout")                    # the user's file is backed up before it is replaced
        self.assertEqual(tx["backup_sha256"]["Mine"], sha(b"user layout"))
        self.assertTrue((self.journal / tx["tx_id"] / "tx.json").is_file())
        self.assertEqual(layouttx.recovery_scan(self.journal), [])

    def test_rollback_restores_the_exact_state_the_users_files_byte_for_byte(self):
        self.user_folder({"Mine": b"user layout \x00\xff", "Other": b"other"})
        before = self.state()
        self.package({"Mine": b"ours", "New": b"brand new"})
        tx = layouttx.apply(self.journal, self.pkg, self.folder, confirmations=["replace:Mine"])
        done = layouttx.rollback(self.journal, tx["tx_id"])
        self.assertEqual(done["state"], "rolled_back")
        self.assertTrue(done["rollback"]["exact"])
        self.assertEqual(self.state(), before)                                              # New removed, Mine back byte for byte, Other untouched

    def test_rollback_removes_a_folder_the_transaction_created(self):
        self.package({"A": b"a"})
        tx = layouttx.apply(self.journal, self.pkg, self.folder)
        self.assertTrue(self.folder.is_dir())
        layouttx.rollback(self.journal, tx["tx_id"])
        self.assertFalse(self.folder.exists())

    def test_a_file_changed_since_is_never_overwritten_by_a_rollback(self):
        self.user_folder({"Mine": b"user layout"})
        self.package({"Mine": b"ours", "New": b"brand new"})
        tx = layouttx.apply(self.journal, self.pkg, self.folder, confirmations=["replace:Mine"])
        (self.folder / "Mine").write_bytes(b"the user edited it again in the game")
        done = layouttx.rollback(self.journal, tx["tx_id"])
        self.assertEqual(done["state"], "rollback_failed")
        self.assertEqual(done["rollback"]["conflicts"], ["Mine"])
        self.assertEqual((self.folder / "Mine").read_bytes(), b"the user edited it again in the game")
        self.assertFalse((self.folder / "New").exists())                                    # the other file was still rolled back

    def test_a_running_game_and_a_busy_transaction_block_a_new_one(self):
        self.package({"A": b"a", "B": b"b"})
        with self.assertRaises(layouttx.LayoutTxRefused):
            layouttx.apply(self.journal, self.pkg, self.folder, running=lambda: True)
        self.assertIsNone(self.state())
        self.crash_after_first_write()
        with self.assertRaises(layouttx.LayoutTxRefused) as cm:
            layouttx.apply(self.journal, self.pkg, self.folder)
        self.assertIn("unfinished", str(cm.exception))

    def test_a_failure_mid_write_rolls_back_automatically(self):
        self.user_folder({"Mine": b"user layout"})
        before = self.state()
        self.package({"Mine": b"ours", "Two": b"second"})
        real = layouttx.shutil.copyfile
        calls = {"n": 0}

        def flaky(src, dst):
            calls["n"] += 1
            if calls["n"] == 2:                                                             # the first file is written, the second fails
                raise OSError("disk full")
            return real(src, dst)

        with mock.patch.object(layouttx.shutil, "copyfile", flaky):
            with self.assertRaises(layouttx.LayoutTxRefused) as cm:
                layouttx.apply(self.journal, self.pkg, self.folder, confirmations=["replace:Mine"])
        self.assertIn("rolled back", str(cm.exception))
        self.assertEqual(self.state(), before)
        self.assertEqual([t["state"] for t in layouttx.transactions(self.journal)], ["rolled_back"])


class Recovery(Base):
    def test_the_scan_finds_a_half_finished_transaction_and_recover_rolls_it_back(self):
        self.user_folder({"Mine": b"user layout"})
        before = self.state()
        self.package({"Mine": b"ours", "Two": b"second"})
        self.crash_after_first_write(confirmations=["replace:Mine"])
        scan = layouttx.recovery_scan(self.journal)
        self.assertEqual(len(scan), 1)
        self.assertEqual(scan[0]["state"], "rollback_required")
        self.assertEqual({f["name"]: f["status"] for f in scan[0]["files"]}, {"Mine": "written", "Two": "untouched"})
        self.assertEqual(scan[0]["safe_action"], "rollback")
        layouttx.recover(self.journal, scan[0]["tx_id"])
        self.assertEqual(self.state(), before)
        self.assertEqual(layouttx.recovery_scan(self.journal), [])

    def test_the_scan_says_when_a_file_changed_since(self):
        self.package({"A": b"a", "B": b"b"})
        self.crash_after_first_write()
        (self.folder / "A").write_bytes(b"someone else")
        scan = layouttx.recovery_scan(self.journal)
        self.assertTrue(scan[0]["files"][0]["status"].startswith("changed since"))
        self.assertTrue(scan[0]["safe_action"].startswith("none"))


if __name__ == "__main__":
    unittest.main()
