# Phase 8: Windows release (descoped from cross-platform, 2026-11-13)

Owner decision, 2026-11-13: **Windows only.** macOS is dropped indefinitely (no macOS run, no signing, no notarisation, no Apple Developer account). Linux/Proton stays deferred; the fake-tree tests are its only coverage.
Remaining work: a Windows installer with the bundled engine, and auto-update through GitHub Releases. Exit criteria: installer installed and running with the bundled engine and no Python on PATH; auto-update proven from one installed
version to the next; all tests green; carried items (icons/layouts diff, layout item states) still close at the next FM patch. Evidence carries build and date.

## Done before the descope (Windows, run on this machine, build 27.0.1.2503222, 2026-11-13)

- **Frozen engine:** `tools/freeze_engine.py` (42 s, 94 MB one-dir). Frozen `verify-stock`, `docs.checklist` (bundled docs), `tables.view` (UnityPy inside the freeze) work; **a frozen build of `p7-table-test-3` is bit-identical** to the venv build
  (`1f1c0b22...271d64`, plan digest `83965de6...`, gate 0 failures), the bundle proven in game; `serve` starts in 1 s and answers the page and three RPCs with the session token (header `X-Token`); no process left behind.
- **Shell prefers the frozen engine:** `studio/src-tauri/src/lib.rs` `frozen_engine()`: `FM27SE_ENGINE`, then `<resource dir>/fm-skin-engine/`, then next to the exe, else the repo's Python (dev). `cargo check` passes.
- **Paths:** `skin_editor/userdirs.py` (Windows Documents Known Folder, Linux/Proton and macOS rules kept as deferred design, 10 tests on fake trees, never run on those systems).

## Windows installer: built, installed, proven (2026-11-13, game build 27.0.1.2503222)

- **Built:** `npx tauri build --config src-tauri/tauri.release.conf.json` (NSIS, per-user, frozen engine bundled as a resource). `FM Skin Studio_0.1.0_x64-setup.exe` 40.6 MiB, sha256 `28BC4A54...0968F381`; later `FM Skin Studio_0.1.1_x64-setup.exe` 41.5 MiB, sha256 `57AF9E5D...ECA69712` (with the updater).
- **Installed** silently (`/S`) to `%LOCALAPPDATA%\FM Skin Studio` (shell 9.5 MB, `fm-skin-engine\` 94 MB, uninstaller; registered as "FM Skin Studio" in HKCU). 0.1.1 was installed over 0.1.0 (registered version 0.1.1).
- **Ran with no Python on PATH:** the installed shell was launched with every `Python`, `.venv` and `WindowsApps` (Store stub) entry removed from its PATH (`python`, `python3`, `py` not resolvable) and a neutral working directory. It started
  `fm-skin-engine.exe` from its own install folder (engine announced in 2 s; process tree: shell -> bundled engine, no `python.exe`). Closing the window ended both processes in 1 s, no orphan.
- **End to end through the installed engine's RPC:** `project.list` found all 9 existing projects (Mine, jonukas-dark-paper, overrides, p6-class-test, p6-font-test, p7-table-test, -2, -3, p7-tile-test); `project.get` and `update.status` (state `same`, profile `27.0.1.2503222-dfa1892e861e`) work;
  `build.bundles` on `p7-table-test-3` finished with **gate 0 failures** (1 table patch, 1 untouched bundle checked), package `20261113T210853Z`, bundle sha256 `1f1c0b22237a0587657156f8da227c4871eb573df3533a75df677e0d84271d64` and plan digest `83965de62d5c...`: **identical to the build proven in game**.
  The installed engine's command line, still without Python: `verify-stock` = `STOCK: 67 of 67`, `restore vanilla` = nothing copied (already stock), `verify-stock` again = 67 of 67. The game was closed throughout and never touched.
- **Data paths:** the installed app uses the same workspace as development (`%LOCALAPPDATA%\FM27SkinEditor`, written by the engine itself), so existing projects, profiles, snapshots, backups and builds are found as they are; **no migration was needed**. The installed app writes nothing into its own folder.
- **Not clicked through:** the Studio window itself was open during these runs but the checks above went through the engine the shell started, not through mouse clicks in the UI.

## Auto-update through GitHub Releases

| Item | Status |
|---|---|
| Updater signing keypair | **done**: `%USERPROFILE%\.tauri\fm-skin-studio.key` (private, password in `fm-skin-studio.password`, both outside the project and ignored by `.gitignore`) and `.key.pub`; the public key is in `tauri.conf.json`. **Back the private key up**: an update signed with another key will not install on any existing copy. |
| Shell: check, download, stop engine, install, restart | **done, compiled, tested in the page** (`app_update_check`, `app_update_install` in `lib.rs`; Studio `?` view, "App updates", 4 Vitest tests; 29 of 29 pass). It refuses while `fm.exe` runs, downloads first, stops the bundled engine so the installer can replace its files, then installs and restarts. |
| Signed installer + `.sig` | **done**: `createUpdaterArtifacts`; 0.1.1 built with the key, `.exe.sig` produced. |
| `latest.json` endpoint | `https://github.com/OWNER/REPO/releases/latest/download/latest.json` in `tauri.conf.json`: **placeholder until the repo exists**. |
| GitHub Actions release workflow | **written, not run**: `.github/workflows/release.yml` (tag `vX.Y.Z` -> freeze engine, Studio tests, `tauri-action` builds, signs and publishes the release with `latest.json`). |
| N to N+1 proof | **open**, needs the repo (below). Not provable locally: the updater refuses `http://` endpoints in release builds, and a local HTTPS feed would need a self-made certificate in the Windows trust store. `tools/local_update_server.py` serves a feed for the dev case. |

**What the owner creates and does (once):**
1. A **public** GitHub repository (a private one cannot serve `latest.json` to the app without a token). Tell me `OWNER/REPO`; I put it in `tauri.conf.json`.
2. In the repo: Settings > Secrets and variables > Actions > New repository secret: `TAURI_SIGNING_PRIVATE_KEY` = the contents of `%USERPROFILE%\.tauri\fm-skin-studio.key` (`Get-Content "$env:USERPROFILE\.tauri\fm-skin-studio.key" | clip`, then paste), and `TAURI_SIGNING_PRIVATE_KEY_PASSWORD` = the contents of `fm-skin-studio.password`.
3. Push the project folder to it (this machine has no git; Git for Windows, then `git init`, `git add .`, `git commit`, `git remote add origin ...`, `git push -u origin main`). `.gitignore` is in place and keeps the key, the workspace, build output and game bundles out.
4. Settings > Actions > General: workflow permissions "Read and write".

**Then the proof:** tag `v0.1.1`, the workflow publishes release 0.1.1 + `latest.json`; install that installer; bump to 0.1.2, tag `v0.1.2`; in the installed 0.1.1, `?` > App updates > Check for updates > Install and restart; show 0.1.1 become 0.1.2.
