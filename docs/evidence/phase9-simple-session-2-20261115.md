# Session 2 record (the gallery gate), 2026-11-15: PREFLIGHT ONLY, the in-game part is not done yet

This file is the record the sessions checklist asks for. Right now it holds the preflight, measured before the owner's sitting. **Nothing in the game has been looked at yet**; the per-theme verdicts, the defender-badge answer, the 7 unchecked pairs and the 148 kept colours are added below as they are observed, and a failure is written as a failure.

## Preflight (rules 2, 3, 5, 6 of `docs/SESSIONS-simple-mode-checklist.md`)
- **verify-stock:** `STOCK: 67 of 67 UI bundles equal the stock reference hash; update status: same` (exit 0).
- **Plugin baseline 0.2.2:** DLL sha256 `1C698C3DB45DC59FCF01FDA0C4A8A64819DDC6185982237898FF29638FFD7C6F`; config sha256 `9231F4BB99C0B64B67759FA331D43BBF7AF0D1B9DC7A46D0A313F8711886CE9B`; `Enabled = true`, `MainThreadBudgetMs = 600`, `AllowActions = false`. All equal the checklist's baseline.
- **Game state:** no `fm` or `Football Manager 27` process running; the game was not launched by this work.
- **Boot-time list:** machine last boot 2026-11-15 18:17:12. Running: Steam (18:17:57), Spotify (18:17:40 to 18:18:12), Discord (18:18:01 to 18:18:07), Medal and MedalEncoder (18:18:07 to 18:19:27). Not compared with the F3 list in this record.
- **Offline theme check on this build** (`tools/check_s4_themes.py`): no mapped token missing; Forest, Ocean and Slate and amber pass with 0 failures, defender badge 4.76, 4.77 and 4.81; the export of Forest writes 83 tokens, no problems.
- **Skins folder backup:** `%LOCALAPPDATA%\FM27SkinEditor\backups\skins-20261115-175711` (86 files, hashes equal to the source; hash list `skins-20261115-175711.sha256.txt` beside it).
- **Additions:** three skins written by the Studio's own export into `Documents\Sports Interactive\Football Manager 27\skins`: `gallery-forest`, `gallery-ocean`, `gallery-slate-and-amber` (each 6 files, 83 tokens, no problems). The 86 files that were there are unchanged by hash. No game file was written.

## To do in the game (owner at the PC)
1. Start Football Manager, load the save (same save, same breakpoint, same window size for every theme; write them down).
2. For each of the three themes: Preferences, pick it in the drop-down next to "Reload Skin", Reload Skin, wait 10 s, Confirm.
3. **First, on every theme:** `fm_get_styles` on a defender position badge label (one call): which token or rule wins? That single answer decides whether the badge entry stays in the role map.
4. Then the eight screens (club, competition, portal, recruitment, squad, tactics, tactics-instructions, training): one `fm_screenshot` each, and the observations the checklist lists.

## Observations
(none yet)
