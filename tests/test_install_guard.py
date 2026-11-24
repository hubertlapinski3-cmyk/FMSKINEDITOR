"""SAFETY: nothing that copies game files back from a snapshot or a backup runs when the game changed after that snapshot or backup. Every test works on a scratch copy; the real game folder is never touched."""
import json
import logging
import tempfile
import unittest
from pathlib import Path

from skin_editor import bundles, config, index_styles, install, patcher, project
from tests.test_core import fake, sheet


def scratch(tmp):
    aa = Path(tmp) / "StreamingAssets/aa/StandaloneWindows64"
    aa.mkdir(parents=True)
    (aa / bundles.STYLE_BUNDLES[0]).write_text(json.dumps([sheet("FigmaStyleVariables")]))
    (aa / bundles.STYLE_BUNDLES[1]).write_text(json.dumps([sheet()]))
    (aa.parent / "catalog.hash").write_text("cat-old")
    ws = config.Workspace(Path(tmp) / "ws")
    install.snapshot_vanilla(ws, aa)
    ix = index_styles.build(ws)
    p = project.new("t")
    p["scoped_rules"] = [{"sheet": "AlwaysAppliedStyleSheet", "selector": ".inner", "props": {"background-color": "#010203"}}]
    patcher.build(p, ws, ix)
    return aa, ws, patcher.latest_build(ws, "t")


def snapshot_of_files(aa):
    return {f.name: f.read_bytes() for f in aa.glob("*.bundle")}


def close_logs():
    for h in list(logging.getLogger("skin_editor").handlers):
        logging.getLogger("skin_editor").removeHandler(h)
        h.close()


class UpdatedGameRefusesEveryWrite(unittest.TestCase):
    def test_restore_vanilla_is_refused_after_a_game_update_and_writes_nothing(self):
        with tempfile.TemporaryDirectory() as tmp, fake():
            aa, ws, d = scratch(tmp)
            install.install(ws, aa, d, lambda: False)                       # an ordinary install on the build the snapshot was taken on
            (aa.parent / "catalog.hash").write_text("cat-new")               # the game updates: new catalog, new files
            (aa / bundles.STYLE_BUNDLES[1]).write_text("new build")
            before = snapshot_of_files(aa)
            with self.assertRaises(install.InstallError) as c:
                install.restore(ws, aa, "vanilla", lambda: False)
            self.assertIn("catalog.hash changed since the snapshot", str(c.exception))
            self.assertIn("snapshot --force", str(c.exception))
            self.assertEqual(snapshot_of_files(aa), before)
            close_logs()

    def test_restore_of_a_backup_made_before_the_update_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp, fake():
            aa, ws, d = scratch(tmp)
            install.install(ws, aa, d, lambda: False)
            b = install.list_backups(ws)[0]["name"]
            (aa.parent / "catalog.hash").write_text("cat-new")
            before = snapshot_of_files(aa)
            with self.assertRaises(install.InstallError) as c:
                install.restore(ws, aa, b, lambda: False)
            self.assertIn("catalog.hash changed since the snapshot", str(c.exception))
            self.assertEqual(snapshot_of_files(aa), before)
            close_logs()

    def test_restore_of_a_backup_is_refused_when_the_live_file_is_not_one_it_knows(self):
        """Catalog unchanged (no reference to compare with), but the live file is neither what the backup was taken from nor what it installed."""
        with tempfile.TemporaryDirectory() as tmp, fake():
            aa, ws, d = scratch(tmp)
            install.install(ws, aa, d, lambda: False)
            b = install.list_backups(ws)[0]["name"]
            (aa / bundles.STYLE_BUNDLES[1]).write_text("a different build of this file")
            before = snapshot_of_files(aa)
            with self.assertRaises(install.InstallError) as c:
                install.restore(ws, aa, b, lambda: False)
            self.assertIn("would mix two game builds", str(c.exception))
            self.assertEqual(snapshot_of_files(aa), before)
            close_logs()

    def test_force_does_not_override_a_changed_catalog(self):
        with tempfile.TemporaryDirectory() as tmp, fake():
            aa, ws, d = scratch(tmp)
            (aa.parent / "catalog.hash").write_text("cat-new")
            before = snapshot_of_files(aa)
            with self.assertRaises(install.InstallError) as c:
                install.install(ws, aa, d, lambda: False, force=True)
            self.assertIn("The install was not done", str(c.exception))
            self.assertEqual(snapshot_of_files(aa), before)
            close_logs()

    def test_snapshot_refuses_while_a_live_bundle_is_a_file_this_app_installed_and_force_does_not_override(self):
        with tempfile.TemporaryDirectory() as tmp, fake():
            aa, ws, d = scratch(tmp)
            install.install(ws, aa, d, lambda: False)                         # the skin is now in the game folder
            before = snapshot_of_files(aa)
            for force in (False, True):
                with self.assertRaises(install.InstallError) as c:
                    install.snapshot_vanilla(ws, aa, force=force)
                self.assertIn("not snapshotted", str(c.exception))
                self.assertIn("Verify integrity", str(c.exception))
            self.assertEqual(install.skinned_bundles(ws, aa), [bundles.STYLE_BUNDLES[1]])
            self.assertEqual(snapshot_of_files(aa), before)
            close_logs()

    def test_snapshot_still_works_when_every_live_bundle_is_stock_even_after_installs_and_restores(self):
        with tempfile.TemporaryDirectory() as tmp, fake():
            aa, ws, d = scratch(tmp)
            install.install(ws, aa, d, lambda: False)
            install.restore(ws, aa, "vanilla", lambda: False)                  # stock is back; the log still holds the skin's hash
            self.assertEqual(install.skinned_bundles(ws, aa), [])
            install.snapshot_vanilla(ws, aa, force=True)
            close_logs()

    def test_a_backup_still_restores_when_nothing_changed(self):
        with tempfile.TemporaryDirectory() as tmp, fake():
            aa, ws, d = scratch(tmp)
            original = (aa / bundles.STYLE_BUNDLES[1]).read_bytes()
            install.install(ws, aa, d, lambda: False)
            b = install.list_backups(ws)[0]["name"]
            install.restore(ws, aa, b, lambda: False)
            self.assertEqual((aa / bundles.STYLE_BUNDLES[1]).read_bytes(), original)
            close_logs()

    def test_install_refuses_unless_every_replaced_bundle_has_a_verified_stock_backup_first(self):
        with tempfile.TemporaryDirectory() as tmp, fake():
            aa, ws, d = scratch(tmp)
            target = bundles.STYLE_BUNDLES[1]
            # First install while live is stock: verified stock backup exists in vanilla/
            res = install.install(ws, aa, d, lambda: False)
            self.assertIn(target, res["verified_stock_backups"])
            # Remove the stock backup from vanilla/ and backups/ while live holds the skin
            (ws.vanilla / target).chmod(0o644)
            (ws.vanilla / target).unlink()
            for bdir in ws.backups.iterdir():
                if bdir.is_dir():
                    for f in bdir.rglob(target):
                        f.unlink()
            before = snapshot_of_files(aa)
            with self.assertRaises(install.InstallError) as c:
                install.install(ws, aa, d, lambda: False)
            self.assertIn("no verified stock backup exists", str(c.exception))
            self.assertIn(target, str(c.exception))
            self.assertEqual(snapshot_of_files(aa), before)
            close_logs()

    def test_restore_vanilla_finds_verified_stock_backups_for_non_style_bundles_and_refuses_if_missing(self):
        with tempfile.TemporaryDirectory() as tmp, fake():
            aa = Path(tmp) / "StreamingAssets/aa/StandaloneWindows64"
            aa.mkdir(parents=True)
            (aa / bundles.STYLE_BUNDLES[0]).write_text(json.dumps([sheet("FigmaStyleVariables")]))
            (aa / bundles.STYLE_BUNDLES[1]).write_text(json.dumps([sheet()]))
            extra = "ui-tileslayouts_assets_all.bundle"
            stock_bytes = b"stock-tileslayouts-bundle"
            (aa / extra).write_bytes(stock_bytes)
            (aa.parent / "catalog.hash").write_text("cat-stock")
            ws = config.Workspace(Path(tmp) / "ws")
            install.snapshot_vanilla(ws, aa)
            # Place a verified stock backup in a transaction backup folder (as installtx does)
            tx_files = ws.backups / "9762c3bb3aaf8a94" / "20261122T201537Z-c354b2df" / "files"
            tx_files.mkdir(parents=True)
            (tx_files / extra).write_bytes(stock_bytes)
            # Modify live extra bundle
            (aa / extra).write_bytes(b"modified-tileslayouts-bundle")
            res = install.restore(ws, aa, "vanilla", lambda: False)
            self.assertIn(extra, res["copied"])
            self.assertEqual((aa / extra).read_bytes(), stock_bytes)
            # If the backup is corrupt/missing while live is modified, restore('vanilla') refuses
            (aa / extra).write_bytes(b"modified-again")
            (tx_files / extra).write_bytes(b"corrupt-backup")
            with self.assertRaises(install.InstallError) as c:
                install.restore(ws, aa, "vanilla", lambda: False)
            self.assertIn("no verified stock backup matching the stock hash record", str(c.exception))
            self.assertIn(extra, str(c.exception))
            close_logs()

    def test_install_warns_and_requires_confirmation_when_build_package_is_older_than_project(self):
        import os, time
        from skin_editor import gameinstall, installtx
        with tempfile.TemporaryDirectory() as tmp, fake():
            aa, ws, d = scratch(tmp)
            p = project.new("t")
            project.save(ws, p)
            # Make the project file strictly newer than the build package
            proj_file = ws.projects / "t.skin.json"
            if not proj_file.is_file():
                proj_file = ws.projects / "t" / "project.json"
            future = time.time() + 120
            os.utime(proj_file, (future, future))
            # Legacy install refuses without confirm_stale
            with self.assertRaises(install.InstallError) as c:
                install.install(ws, aa, d, lambda: False)
            self.assertIn("older than the project's last change", str(c.exception))
            # With explicit confirm_stale=True it succeeds
            res = install.install(ws, aa, d, lambda: False, confirm_stale=True)
            self.assertIn(bundles.STYLE_BUNDLES[1], res["copied"])
            # Restore stock and verify installtx.preflight warns + requires stale_package confirmation
            install.restore(ws, aa, "vanilla", lambda: False)
            game_dir = aa.parents[3]
            (game_dir / "fm.exe").write_bytes(b"fm")
            prof = gameinstall.describe_install(game_dir, "test", "27.test")
            pf = installtx.preflight(ws, prof, d)
            self.assertIn("stale_package", [w["code"] for w in pf["warnings"]])
            self.assertIn("stale_package", pf["required_confirmations"])
            with self.assertRaises(installtx.InstallRefused) as ref:
                installtx.apply(ws, prof, d, confirmations=[], running=lambda: False)
            self.assertIn("stale_package", ref.exception.confirmations)
            close_logs()


if __name__ == "__main__":
    unittest.main()
