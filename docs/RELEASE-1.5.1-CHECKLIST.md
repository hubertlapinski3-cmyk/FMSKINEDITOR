# Release 1.5.1 Checklist & Verification

**Branch:** `release/1.5.1` (branched from `release/1.5`, `ea3a4d8`)
**Development commit synced:** `stage5-local` (`237d0f1`, local-only; `stage5-local` stays unpushed)

## Summary of 1.5.1 Changes

1. **FM27 `27.1.1.2511875` (`bc824c385acb`) compatibility:**
   - Measurement carry-over & build-tagged confidence labels (`"measured (27.1.0, carried over to 27.1.1)"`).
   - Added `2560x1440 fullscreen, Medium, Larger` (`25x13`) and `2560x1440 fullscreen, Large, Larger` (`20x11`) profiles.
2. **Guided "FM27 was updated" banner:**
   - `studio/src/App.tsx`: shows `data-testid="game-updated-banner"` when `update.status` reports `catalog_changed`, with `"Reread now"` (`snapshot.reread`) so users can update Studio's snapshot and index in one click.
3. **Clear Restore stock refusal on updated game:**
   - `skin_editor/install.py` (`refuse_if_updated`) and `studio/src/Updates.tsx`: explain why Restore stock refuses old-build backups (mixing two builds breaks FM27; verify integrity in Steam first, then click Reread now).

## Rule 4 & Gate Verification

- **Rule 4 scan on `git ls-files`:** `0` hits (`local_path`: 0, `username`: 0, `rea_derived`: 0, `decompiled`: 0, `token`: 0).
- **Backend suite (`release/1.5.1`):** `976` ran, `0` failed, `0` errors, `195` skipped (`REA_RULE_PASS 27/27`, `one_rule baseline 27/27`).
- **Studio suite (`release/1.5.1`):** `298/298` passed (`29` test files), `npm run lint`: `0` errors (`85` pre-existing warnings).

## Build Artifacts (Unsigned)

- **Frozen engine:** `build-sidecar/fm-skin-engine/fm-skin-engine.exe` (`--selftest` passed; `sha256: BE6231FC5B0472AE2C21E6B3DE82C24BB1553FF3190837B96B389859129D01F7`)
- **Desktop binary:** `studio/src-tauri/target/release/fm-skin-studio.exe` (`sha256: BDD74BDCA5FEF7339C9112E488F5F12603D08481D75CD7A7DD73290C78746D96`)
- **NSIS installer:** `studio/src-tauri/target/release/bundle/nsis/FM Skin Studio_1.5.1_x64-setup.exe` (`36,091,059` bytes / `34.42 MiB`, `sha256: C8C86739520D5CF30351758A15FE2D0E87CD2CBA21FAF87FBC472BB8E5953C38`)
- **Signed:** `no` (`Get-AuthenticodeSignature`: `NotSigned`).

## Isolated Install & Upgrade Tests (`%LOCALAPPDATA%\FMSkinStudioRC151Test`)

1. Silent `1.5.0 -> 1.5.1` upgrade exit `0`; `FileVersion` `1.5.1`; `fm-skin-engine.exe --selftest` exit `0`.
2. Migrated `27` projects and `2` favourites in isolated workspace (`FM27SE_WORKSPACE`); `app_version: 1.5.1`.
3. `catalog_changed` pre-reread: `backup.restore("vanilla")` refused with Steam verify + Reread explanation; `snapshot.reread` completed (`done`), `update.status` returned `same` (`bc824c385acb3bc352c9e5844c19aadc`).
4. `playground.screens` for `SquadComposition-Large` returned `measured` across `Small, Larger`, `Medium, Larger`, and `Large, Larger`.
5. Sandbox `build.bundles` + `install.bundles` + `backup.restore("vanilla")` succeeded on isolated `game_sandbox`.
6. Silent uninstall (`/S`) exit `0`; test directory removed; owner's installed `FM Skin Studio` (`9D5B7E33...`), `CustomGridCompositions` (all 5 hashes), and real FM27 `aa` untouched.

## Publish Commands (Not Run)

```powershell
git push -u origin release/1.5.1
git tag -a v1.5.1 -m "FM Skin Studio v1.5.1"
git push origin v1.5.1
gh release create v1.5.1 "studio/src-tauri/target/release/bundle/nsis/FM Skin Studio_1.5.1_x64-setup.exe" --title "FM Skin Studio v1.5.1" --notes-file docs/RELEASE-NOTES-1.5.1.md
```
