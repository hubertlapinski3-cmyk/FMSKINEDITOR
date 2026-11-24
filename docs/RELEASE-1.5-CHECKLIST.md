# FM Skin Studio 1.5.0 Release Checklist

**Branch:** `release/1.5`  
**Status:** Verified local release candidate built and tested in isolated sandbox; **not pushed or published**.

---

## G1 — Freeze & Audit

### Owner In-Game Test Input (2026-11-24, `2560x1440` fullscreen, Small, Larger)

| Feature | Result / Evidence | Status in v1.5.0 |
| --- | --- | --- |
| Squad swap (first milestone) | `20261123T081454Z-ccdf17f9`, matched | Standard (`done`) |
| Tile from another screen | Build `20261124T082312Z`, install backup `20261124T082322Z`; `Penalties` offered in Squad's swap menu, restored to stock afterwards (`files clean`); rendering proven by RR-T5 (`BestXI` on Squad) | Standard (`done`, with install guard + `files clean` check) |
| Tile size | `not owner-confirmed` | Experimental (`experimental: tile sizes` in `BUILD`, off by default — not owner-confirmed on its own run) |
| Slot change | `20261124T070834Z-03e293d7` (`SquadComposition-Large` `m_bottom` `['SquadHierachy','MedicalCentre','Loans']` -> `['SquadHierachy','Loans','Happiness']`), applied `07:08:34Z` and rolled back `07:08:39Z` before any game launch (not confirmed in-game) | Experimental (`experimental: slot edits` in `BUILD`, off by default) |
| Favourites | `20261124T072029Z-916b1fa9` (`CompetitionHub9CompsGridComposition-Large`), `20261124T072115Z-22447dfe` (`SquadComposition-Small`), `20261124T073025Z-6bbea060` (`SquadComposition-Large`) | Standard (`done`) |
| Bundle-route layout edits | Excluded from default route by design (`experimental_bundle_layout_edits`) | Experimental (`experimental: layout edits via bundles` in `BUILD`, off by default — rewrites `ui-tileslayouts_assets_all.bundle`, moves all compositions, ignored on customised screens) |

### Features New Since v1.1.1

- **Game Layouts** (Edit & Runtime panes, Apply/Rollback with backups & recovery, legality checks, breakpoints, fullscreen/windowed viewport profiles, screen index, Favourites, "Apply to Standard & Small", confidence labels `measured`/`measured mismatch`/`computed`/`unverified`): `done`
- **Slots** (add, remove, reorder `m_bottom` / `m_right`): `experimental` (`experimental: slot edits` in `BUILD`, off by default; `20261124T070834Z-03e293d7` was rolled back 5s later before any game launch)
- **Allowed tiles (bundle route)** + install guards (`files clean`, verified stock backups, package age, refusal over non-stock files): `done`
- **Tile sizes (bundle route)**: `experimental` (off by default; not owner-confirmed in v1.5.0)
- **Bundle-route layout edits**: `experimental` (off by default)
- **Injected styles editor (`AlwaysAppliedStyleSheet`)**: `done`
- **Inspect skin (read only)**: `done`

### Real `CustomGridCompositions` State (Untouched)

| File | SHA-256 | Classification |
| --- | --- | --- |
| `CompetitionHub9CompsGridComposition-Large` | `8d68fe405a80781a8f24005ee3cad072c35cc875f187a9728b074b23fd5fccc6` | Test leftover (`20261124T072029Z-916b1fa9`) |
| `CompetitionStagesBottomTileComposition` | `8372412d5a2741e2dcb412cf80058d40b5eeab73ec452261ff0d93a4f8440674` | Owner file (`8372412d...`) |
| `PlayerReportOverviewComposition-Large` | `a2c95aa7135088669f392df4b2b596df6861545c2bdf95dbc4bef960cd3bdf51` | Owner file (`a2c95aa7...`) |
| `SquadComposition-Large` | `8db0b2547ca2806f74fab415ec99e1f443b26a23da67a0b5a467d9e84b5fcb1e` | Test leftover (`8db0b254...`; overwrote milestone `6b8510...` during 2026-11-24 owner tests) |
| `SquadComposition-Small` | `11197bb6449d4bbe5587a553b1af7a37e3fed2e30c371ce1d14d6f597781a005` | Test leftover (`20261124T072115Z-22447dfe`) |

### G1 Gate Suites
- Backend (`stage5-local` @ `0357c83`): `1217` ran, `0` failed, `0` errors, `43` skipped.
- Studio (`stage5-local` @ `0357c83`): `298/298` passed, `npm run lint` passed, `npm run build` passed.

---

## G2 — Version & Changelog

- Version set to `1.5.0` in:
  - `studio/package.json`
  - `studio/src-tauri/tauri.conf.json`
  - `studio/src-tauri/Cargo.toml`
  - `studio/src-tauri/Cargo.lock`
  - `skin_editor/__init__.py` (`__version__ = "1.5.0"`, returned by `Engine.state()` as `app_version`)
  - Status bar & About modal (`studio/src/App.tsx`)
  - Updater comparison (`studio/src/AppUpdate.tsx` + Tauri updater `PackageInfo` `1.5.0`)
- Changelog & notes: `CHANGELOG.md`, `docs/RELEASE-NOTES-1.5.0.md`.

---

## G3 — Release Branch Cleanup & Scan

- Branch `release/1.5` created from `stage5-local` (`0357c83`). `stage5-local` remains untouched with `.local-only` and `.git/hooks/pre-push` intact.
- Excluded items removed (1,178 files total):
  - Scanner/atlas plugins & staging + connectors/tests: `393`
  - Dev launch/safety/inventory/cfg tools & tests: `253` (including `tools/build_preview_model.py`)
  - REA tooling, root dev markers & REA/evidence tests: `407` (including `tests/test_safety_snapshot.py`)
  - Dev docs & evidence: `115`
  - Game screenshots outside Studio `docs/ui-checks`: `10` (`data/models/*.png`, `docs/ui-checks/ui3-game-1.jpg`, `docs/ui-checks/ui3-game-2.jpg`)
- Dev-only UI (`PREVIEW` bottom panel tab) hidden behind `import.meta.env.VITE_DEV_TOOLS === 'true'`; `inspector_status` and `preview_live` in `skin_editor/engine.py` return offline/disabled stubs so nothing shipped expects the plugin.
- Rule 4 scan after cleanup & docs:
  - `local_path`: 0 hits (33 prior hits scrubbed: 31 in `tests/`, 2 in `docs/rea/data/layout-parity.json`)
  - `username`: 2 justified hits (public GitHub release URLs in `studio/src-tauri/tauri.conf.json` & `tools/make_latest_json.py`; 2 prior capture hits scrubbed)
  - `token`: 0 hits
  - `rea_derived`: 0 hits (6 prior hits scrubbed)
  - `decompiled`: 0 hits (106 prior hits scrubbed)
  - `third_party_skin`: 0 hits (36 prior hits scrubbed)
- `THIRD_PARTY_NOTICES.md`: complete across desktop shell/frontend crates/npm deps and bundled Python engine runtime packages.
- Gate suites on `release/1.5`:
  - Backend: `971` ran, `0` fail, `194` skipped
  - Studio: `298/298` passed, `lint` exited 0, `build` succeeded

---

## G4 — User Docs

- Added `docs/USER-GUIDE.md` covering Game Layouts (Edit/Runtime, Apply/Rollback, recovery, legality, screen index, Favourites, Apply to Standard & Small), Restore stock / `files clean`, confidence labels, viewport profiles, bundle rebuilds after game updates, FM "Reset Layout", experimental toggles, and personal-use rules for third-party skin content.
- Updated `README.md` for end users; `tests/test_frozen.py` & `tests/test_first_skin_guide.py` passed (`20/20`).

---

## G5 — Build Release Candidate

- Frozen engine: `build-sidecar/fm-skin-engine/fm-skin-engine.exe` (`PyInstaller 6.22.3`, Python `3.14.10`, `--selftest` passed; `sha256: 36788c77f766e5f807978a2457f9aef60941f9762a1e7cbd84e4b6c594da1de9`)
- Desktop binary: `studio/src-tauri/target/release/fm-skin-studio.exe` (`sha256: 2c96e93a610666b6483f6e9fcc36d285dc3aa973bd54a6bed4c4eba5ea18ba08`)
- NSIS installer: `studio/src-tauri/target/release/bundle/nsis/FM Skin Studio_1.5.0_x64-setup.exe` (`33,177,602` bytes, `sha256: 715730d16f37200a314deea208d724ec276a9a886dc6d2b4f8cf7bc34c8b012c`)
- **Signed:** `no` (`Get-AuthenticodeSignature`: `NotSigned`). Note for the owner: **SignPath Foundation** offers free Authenticode code signing for open-source Windows projects (not configured here).

---

## G6 — Installed App Tests (Isolated Test Copy)

1. **Silent install to `%LOCALAPPDATA%\FMSkinStudioRC15Test`**: exit `0`. Owner's v1.1.1 at `%LOCALAPPDATA%\FM Skin Studio\fm-skin-studio.exe` untouched (`sha256: 9d5b7e3347743b8643ee99b8363826d8387319aedae9631c320ef5c7a9503198`).
2. **Fresh install** (temp workspace + temp `CustomGridCompositions`): detected FM27, created stock snapshot + style/layout index + layout scan, reported `app_version: 1.5.0`, `tamper: clean`, opened `SquadComposition-Large` at fullscreen `2560x1440` with `measured` confidence in both engine RPC and live installed Studio UI (`docs/ui-checks/rel15-squad-measured.png`).
3. **Upgrade from v1.1.1 copy**: migrated all `26` projects, `config.json` settings, and `2` favourites cleanly; executable `FileVersion` and engine `app_version` both `1.5.0`.
4. **Custom layout Apply / Rollback / Restore to before Apply** on temp `CustomGridCompositions`: Apply modified only the temp copy; Rollback restored exact original SHA-256; simulated game re-save triggered `needs_confirmation: true` and `confirm: true` returned `restored_before_apply` with exact original SHA-256. Real `CustomGridCompositions` hashes stayed unchanged throughout.
5. **Bundle install & Restore stock on sandbox game copy**: `install.bundles` refused over modified non-stock bundle; clean bundle install with backup succeeded; `backup.restore("vanilla")` returned exact stock hashes and `tamper.state == "clean"`.
6. **Uninstall** (`/S`): removed `%LOCALAPPDATA%\FMSkinStudioRC15Test` completely; verified FM27 game folder (`67 of 67` bundles stock), LocalLow `CustomGridCompositions` (all 5 hashes unchanged), `Documents\Sports Interactive\Football Manager 27\games` (`14` items intact), and owner's installed v1.1.1 (`9d5b7e33...`) all untouched.
7. **Launchers**: `FM Skin Studio RELEASED.bat` still points to `%LOCALAPPDATA%\FM Skin Studio\fm-skin-studio.exe`; `FM Skin Studio TESTING (unreleased).bat` runs `npm run tauri dev` in `studio/`.
8. **Screenshots**: `docs/ui-checks/rel15-installed-studio.png`, `docs/ui-checks/rel15-about-build.png`, `docs/ui-checks/rel15-squad-measured.png` (captured directly from installed `fm-skin-studio.exe` WebView2 over isolated test workspace).

---

## REL15-C — Pre-Publish Verification

1. **Skipped tests audit (`release/1.5` backend suite: `974` ran, `780` passed, `0` failed, `0` errors, `194` skipped):**
   - **Dev tooling (`1`):** `test_core.Launcher` (`1`, `needs bash and curl`).
   - **Needs real game (`193`):**
     - Archived bundle sets / layout dumps / layout copies (`162`): `test_route_preference` (`6`), `test_adapters` (`2`), `test_build5g` (`26`), `test_catalog` (`8`), `test_custom_layout_route` (`11`), `test_custom_layouts.CanvasEdits/Generate/PreWriteChecks/RoundTrip/StructuralOperations/Ui3/Ui3RestoreBefore` (`26`), `test_declaration_writer` (`6`), `test_depgraph` (`12`), `test_inventory` (`1`), `test_layout_scan` (`8`), `test_layoutspace` (`8`), `test_preview_custom_layouts` (`7`), `test_preview_profile` (`5`), `test_session_stand_ins` (`3`), `test_set_cell_max_size` (`3`), `test_set_cell_max_size_build` (`6`), `test_tiles_add_cell` (`7`), `test_uidoc` (`9`), `test_uidoc_squad` (`8`).
     - Older build mismatch `27.0.1.2503222` (`dfa1892e`) vs configured `ccf4d25f` (`30`): `test_assets` (`1`), `test_cap` (`3`), `test_captures` (`1`), `test_fixtures` (`2`), `test_images` (`2`), `test_overlay` (`3`), `test_panel_rpc` (`5`), `test_phase7` (`4`), `test_render_m0` (`4`), `test_render_m1` (`1`), `test_skins` (`2`), `test_uss_nested` (`1`), `test_uxml` (`1`).
     - External native skin sample (`1`): `test_uss.NativeImport` (`1`, `needs a sample native skin`).
   - **Bug (`0`, fixed `0`):** zero skips caused by missing shipped data.
   - **27-case REA check on `release/1.5`:** `tests/test_rea_27_cases.py` (`tests/fixtures/rea_27_cases.json`) ran cleanly and printed `REA_RULE_PASS 27/27 (one_rule baseline 27/27)`.
   - **Studio suite & lint:** `298/298` passed, `oxlint` `0` errors.
2. **Runtime data in built sidecar (`build-sidecar/fm-skin-engine/_internal/`):**
   - `docs/rea/data/layout-parity.json`: present (`yes`).
   - `docs/rea/data/fullscreen-2k-measurements.json`: present (`yes`).
   - Measured panel rects (`MEASURED_PANEL_RECTS` / `PANEL_CONTENT_RECTS` in `skin_editor/render/{preview,screen}.py` & `skin_editor/layoutspace.py`, plus `docs/rea/data/fullscreen-2k-measurements.json`): present (`yes`).
   - Additional bundled data files verified: `docs/INGAME-CHECKLIST.md`, `data/findings/session2.json`, `data/models/*.json` (8 files), `data/render/{runtime-classes,text-metrics,uss-property-census}.json`, `data/selftest/roundtrip.unity3d`, `data/simple/{gallery,roles,token-inventory}.json`.
   - Installed RC (`FMSkinStudioRC15Test`) `SquadComposition-Large` at `2560x1440 fullscreen, Small, Larger`: displays `measured`; screenshot at `docs/ui-checks/rel15-squad-measured.png`.
   - Rebuild needed: `yes` (because slot edits moved to experimental & 2 local paths in `layout-parity.json` / `rea_rule.py` were scrubbed); new installer SHA-256: `715730d16f37200a314deea208d724ec276a9a886dc6d2b4f8cf7bc34c8b012c`.
3. **Slot transaction audit (`20261124T070834Z-03e293d7`):**
   - Journal (`custom-layout-journal/20261124T070834Z-03e293d7/tx.json`): edited `SquadComposition-Large` `m_bottom` slot order (`['SquadHierachy','MedicalCentre','Loans']` -> `['SquadHierachy','Loans','Happiness']`), applied `2026-11-24T07:08:34Z`, rolled back 5s later (`2026-11-24T07:08:39Z`, `state: "rolled_back"`) before any game launch.
   - Action taken: slot editing (`add`, `remove`, `reorder`) moved to `"experimental"` (`experimental: slot edits`, `experimental_slot_edits`, off by default); backend `customlayout.apply_edits` refuses slot edits when off, Studio `LayoutCanvas` disables slot controls with experimental notice when off, and `CHANGELOG.md`, `docs/RELEASE-NOTES-1.5.0.md`, `docs/USER-GUIDE.md`, and `README.md` updated accordingly (`tests/test_tiles_bnd1.py` verifies the refusal guard).

---

## G7 — Publish Commands (Run Only When Owner Says `"publish v1.5"`)

> Do **not** push `stage5-local` (`.local-only` and `.git/hooks/pre-push` stay in place).

```powershell
# 1. Push only the release/1.5 branch and create the v1.5.0 tag
git checkout release/1.5
git push -u origin release/1.5
git tag -a v1.5.0 -m "FM Skin Studio 1.5.0"
git push origin v1.5.0

# Option A (automated CI release build via .github/workflows/release.yml):
# Pushing tag v1.5.0 triggers the workflow to freeze, selftest, build, and publish the release assets.

# Option B (manual upload of local release candidate assets via GitHub CLI):
gh release create v1.5.0 `
  "studio/src-tauri/target/release/bundle/nsis/FM Skin Studio_1.5.0_x64-setup.exe" `
  --title "FM Skin Studio 1.5.0" `
  --notes-file "docs/RELEASE-NOTES-1.5.0.md"
```
