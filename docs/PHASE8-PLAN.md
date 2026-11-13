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
| `latest.json` endpoint | **done**: `https://github.com/hubertlapinski3-cmyk/FMSKINEDITOR/releases/latest/download/latest.json` (public repo), embedded in the published installer (checked in the installed `fm-skin-studio.exe`: endpoint string present, placeholder absent). |
| GitHub Actions release workflow | **done and run**: `.github/workflows/release.yml` built, signed and published releases 0.1.1 and 0.1.2 (see the evidence below). |
| N to N+1 proof | **done 2026-11-14**: installed 0.1.1 (from the published release) became 0.1.2 through its own Check for updates > Install and restart. Evidence below. |

**What the owner creates and does (once):**
1. A **public** GitHub repository (a private one cannot serve `latest.json` to the app without a token). Tell me `OWNER/REPO`; I put it in `tauri.conf.json`.
2. In the repo: Settings > Secrets and variables > Actions > New repository secret: `TAURI_SIGNING_PRIVATE_KEY` = the contents of `%USERPROFILE%\.tauri\fm-skin-studio.key` (`Get-Content "$env:USERPROFILE\.tauri\fm-skin-studio.key" | clip`, then paste), and `TAURI_SIGNING_PRIVATE_KEY_PASSWORD` = the contents of `fm-skin-studio.password`.
3. Push the project folder to it (this machine has no git; Git for Windows, then `git init`, `git add .`, `git commit`, `git remote add origin ...`, `git push -u origin main`). `.gitignore` is in place and keeps the key, the workspace, build output and game bundles out.
4. Settings > Actions > General: workflow permissions "Read and write".

### Update proof, with evidence (2026-11-13 / 2026-11-14; times UTC unless marked local, local is UTC+1; game build 27.0.1.2503222)

Repository `hubertlapinski3-cmyk/FMSKINEDITOR` (public), `main` pushed by the owner (commit `e31f770`, 212 files).

1. **First release run failed, as a secrets problem, not a build problem.** Run `43519177408` (tag `v0.1.1`, 22:25Z): Python 3.14 setup, engine freeze, `npm ci`, Studio tests, the Rust build and NSIS all passed on the runner (so the Python-version risk did not occur);
   only the signing step failed: `failed to decode secret key: incorrect updater private key password: Missing comment in secret key`. GitHub shows step logs only to signed-in users, so a **secrets check step** was added to the workflow (commit `7dc1b9c`): it prints only lengths and flags and signs a test file,
   and fails in about a minute. Run `43522208813` attempt 1 printed `key: set=False length=0 | password: set=False length=0`: the secrets were not reaching the workflow. The owner re-entered both as **Repository secrets**; attempt 2 (started 23:09:43Z) printed `key: set=True length=348 trailingWhitespace=False innerWhitespace=False startsLikeKey=True | password: set=True length=28 hasWhitespace=False` and `signing test: signed OK`, then built and published.
   (Local reproduction of damaged secrets: a wrong password gives "Wrong password for that key", a doubled or truncated key gives other messages; an empty key is what gives "Missing comment".)
2. **Release 0.1.1 published** 2026-11-13T23:17Z: assets `FM.Skin.Studio_0.1.1_x64-setup.exe` (41.3 MiB, sha256 `9BCCD67B...2A88C`), its `.sig`, and `latest.json`. The updater endpoint answered HTTP 200 (served from `release-assets.githubusercontent.com`) with `version 0.1.1`, `pub_date 2026-11-13T23:17:40Z`, platforms `windows-x86_64` and `windows-x86_64-nsis`, signature 444 characters; the asset's `.sig` equals the signature in `latest.json`; the public key in `tauri.conf.json` is the one in the repo.
3. **0.1.1 installed here** from that release (silent `/S`, over the earlier local build that had the placeholder endpoint): `fm-skin-studio.exe` 0.1.1, sha256 `699FEBAC66115525...`, registry DisplayVersion 0.1.1, real endpoint embedded.
4. **0.1.2 released:** local suite run first (229 Python tests, `tsc` clean, 29 Studio tests, game stock), version bumped in `tauri.conf.json` and `Cargo.toml` (commit `87787f9`), new tag `v0.1.2` (the `v0.1.1` tag was not touched); run `43526398542` succeeded; release published 23:29:31Z, `latest.json` version 0.1.2, `pub_date 2026-11-13T23:29:34Z`, installer sha256 `964BDD7F7081CD71F90B661B53A784371FC213EB631E63385157DD8C39706A6D`.
5. **The update, done by the owner in the installed app** (the Studio window of 0.1.1 was open, local time): `?` > App updates > **Check for updates** > **Install and restart**.
   - 00:32:22 local: the updater downloaded `FM Skin Studio-0.1.2-installer.exe` into `%TEMP%\FM Skin Studio-0.1.2-updater-usMxUI`; its sha256 is `964BDD7F...06A6D`, **byte-identical to the published GitHub release asset**.
   - 00:32:27: `uninstall.exe` rewritten by the installer; 00:32:28: a new `fm-skin-studio.exe` (pid 9072) started, with its bundled `fm-skin-engine.exe` from the install folder (the old shell and engine, started 00:31, were gone: the app stopped its engine before installing).
   - After: `fm-skin-studio.exe` version **0.1.2**, sha256 `53BF67E9209315B1...` (was `699FEBAC...`), registry DisplayVersion 0.1.2. Read through UI Automation from the new window, in the same view: `App updates | FM Skin Studio | 0.1.2 | up to date`.
   - The updated app works: its engine lists the existing projects, `verify-stock` = `STOCK: 67 of 67`, closing the window ended both processes in 1 s.
   - How the evidence was gathered: an attempt to drive the WebView through a debugging port failed (Tauri sets its own WebView arguments) and did nothing; the automation that ran afterwards used Windows UI Automation and only invoked `?` and Check for updates, after the update had already happened. The Install click was the owner's.
6. **Side note:** after the update the owner deleted the `overrides` project in the Studio (moved to `%LOCALAPPDATA%\FM27SkinEditor\trash\overrides-20261114-003259`, recoverable); deliberate, not part of the proof.

**Left as they are:** the workflow's secrets check step stays (it prints no secret text); GitHub warns that `checkout@v4`, `setup-node@v4` and `setup-python@v5` target Node 20 and run on Node 24 (a warning, to revisit when those actions are updated); the repository's commit identity is the placeholder `your name <you@example.com>`; **back up the updater private key and password** (`%USERPROFILE%\.tauri\`), because no existing installation will accept an update signed with another key. GitHub's unauthenticated API allows 60 calls an hour, so release checks poll `latest.json` and the run pages instead.

**Phase 8 exit criteria (revised for the Windows-only descope): met.** Installer installed and running with the bundled engine and no Python on PATH (section above); auto-update proven from one installed version to the next through GitHub Releases (this section); all tests green (229 Python, 29 Studio, `tsc` clean); the carried items (icons/layouts diff, layout item states) are unchanged and still close at the next FM patch.
