# Handoff: Simple mode (1.2.0) and where it stands (written 2026-11-15, end of the sitting)

Read this first, then `docs/SIMPLE-MODE-PLAN.md` (the milestone reports S0 to S8 and the amendments) and `docs/evidence/phase9-simple-session-2-20261115.md` (the Session 2 record). Repo `C:\Users\Admin\Downloads\fm27-skin-editor`, branch `main`, remote `hubertlapinski3-cmyk/FMSKINEDITOR`. The released version is **1.1.1**; `tauri.conf.json` still says **1.1.0** (the bump to 1.2.0 belongs to the release candidate, which is not prepared).

## 1. What is built (all pushed; every push so far read green on CI up to 38db30e; the last three, d7c637c, f94c92c and this handoff's commit, were queued when written: read them first)
| Milestone | Commit | What |
|---|---|---|
| S0 to S2, S5, S3 | up to 013188b | Inventory; setup and start screen; "Put it in the game" (removal behind a switch); Look at it (offline render, no game screenshot); click-to-recolour; My colours |
| S4 | d256dd8, a673338, f82e171 | A theme from three colours and the gallery (Forest, Ocean, Slate and amber). Dark only (light is out of 1.2.0). Role map: **82 entries, 148 kept**, 42 checked pairs. The defender badge entry and pair were added then **removed** after the game showed the chip label is painted by `.text-regular` |
| S6 | 36f0fb5 | Pictures in three steps; the render now draws a native project's picture swaps (the plan's "no engine work" was wrong) |
| S7 | a8ac4de | Share and undo (zip with manifest, inspect then copy, Start over); two import bugs fixed |
| S8 | a97b25a | `docs/FIRST-SKIN.md`, README rewritten, API.md regenerated, **PyInstaller pinned** (`requirements-build.txt`, 6.22.3) and printed at build, **bundle round-trip self-test** on a synthetic fixture (`data/selftest/roundtrip.unity3d`) |
| Extras | 186b7b0, d7c637c | Tile organiser: a game screenshot behind the grid (Advanced; PNGs in `<workspace>/game-screens`, never in a project or skin). **Findings view** (Advanced, the F button; `data/findings/session2.json`, `findings.get`) |
Tests at the last full run: Python **451** (1 skipped), Studio **166**, tsc and lint clean (only existing warnings).

## 2. What is NOT done (the work left, in the order to do it)
1. **The owner's eyeball pass, sections D to I of `docs/S1-EYEBALL-CHECKLIST.md`.** A screen-driving Claude ran part of D and E (`docs/WALKTHROUGH-RESULTS-20261115.md`) and stopped when it lost the engine token. The brief for another run is `docs/WALKTHROUGH-FOR-CLAUDE.md` (never retype the address; `--keep --reset` for a fresh install). **Two judgments are the owner's alone:** the stretched wallpaper in Look at it (H3) and "a saved skin file is the exported skin, not the project" (I2). The guide `docs/FIRST-SKIN.md` has no screenshots yet.
2. **Session 2 (the gallery gate) is mostly done, by eye, not closed.** Record: `docs/evidence/phase9-simple-session-2-20261115.md`. Looked at: Forest all 8 screens plus Data Hub; Ocean and Slate and amber 7 screens plus Data Hub each. **Missing: Competition for Ocean and Slate** (the Competitions tab is a dropdown the inspector's click cannot open), any measured contrast, the 7 unchecked pairs and the 148 kept colours one by one, the defender chip's fill source. No theme is marked verified; none was removed.
3. ~~The three gallery skins were exported before the badge entry came out~~ **DONE 2026-11-16:** re-exported, 82 tokens each, recorded in the Session 2 record.
4. **Decide on the teal Tactics panels.** Under Ocean and Slate they clash: a gradient the game draws in code (`#20665A` to `#036150`, style rules ignored), so no colour token reaches it. Needs another mechanism, or the owner accepts it. It is also the first answer to Session 1 (c).
5. **Session 1** (`docs/SESSIONS-simple-mode-checklist.md`): (a) Crimson native, (b) club-colour removal on a light and a dark club (the owner must name the saves), (c) the SIGradient end colour (first answer above), (d) U5, (e) removal while selected, LAST. `REMOVAL_RELEASED` flips only in the commit that records (e); if (e) shows breakage the removal button stays out.
6. **Then the release candidate**: bump the version to 1.2.0, release notes, the friend's first-run test on the candidate with the clock written down first (plan section 9), the read-only audit, the owner's approval. **Nothing is tagged without the owner's explicit go.**

**Owner's order of 2026-11-16:** the walkthrough D to I (owner, with the guide screenshots taken during it); the Competition screens, the one-by-one examination of the 7 unchecked pairs and the 148 kept colours, and the defender chip call all fold into Session 2, one inspector call at a time, one record per theme. **Teal Tactics panels: decision rule, no new machinery before the RC:** ask `fm_colour_source` and `fm_get_styles` on a teal panel under a theme; a reachable colour token = candidate role-map entry for later; a texture or image = the S6 picture route as a written proposal only; nothing a skin can reach = ACCEPT as a recorded limit of 1.2.0 (one plain sentence on the theme screens: "some surfaces, like the Tactics panels, keep the game's own colours"; the limit goes in the plan with its evidence). The two club saves for Session 1 (b) are the owner's to name; add them to the checklist when given. The owner also said: when a game step is needed, launch the game and give orders one by one.

## 3. Standing rules (the owner's; keep them)
- Offline unless a session is attended. Never touch release assets (the owner does the web UI). The operator audits, the owner approves, before any tag push.
- Frozen report folders never change (corrections go in addenda). Every published number is generated (the `tools/check_*.py` scripts write the evidence). Raw hashes are recorded from committed bytes. **Read CI after every push; a red run is fixed first.** A milestone report after each milestone.
- A question that needs an owner decision stops work and is asked at once; everything else proceeds. The user's email is private.
- **Waived by the owner on 2026-11-15:** the inspector plugin config stays at **`AllowActions = true`** (hash `AD6B2013...7092`; the baseline copy with hash `9231F4BB...CE9B` is at `%LOCALAPPDATA%/FM27SkinEditor/backups/fm27inspector.cfg.baseline-20261115`). `fm_click` works on navigation buttons only (not on dropdowns such as the settings cog or the Competitions tab), so **skins are picked by hand in Preferences**. Click nothing that changes the save: it is the owner's real Dortmund save. Re-record the config hash at the start of any session.
- No screenshot of the game anywhere in Simple mode (the S5 rule). Game screenshots exist only in the Advanced tile organiser and Findings view, on the user's PC.

## 4. How to run and check things
- **Studio in a browser, scratch workspace:** `.\.venv\Scripts\python.exe tools\run_studio_scratch.py --keep --open` (add `--reset` for a fresh install). It prints the address with the token: use it exactly.
- **Python tests:** `.\.venv\Scripts\python.exe -m unittest discover -s tests` (CI runs it exactly this way, no `-t .`). **Studio:** in `studio/`, `npx vitest run`, `npx tsc --noEmit -p .`, `npx oxlint`.
- **Evidence generators:** `tools/check_s4_themes.py` (themes against the real index), `tools/check_s6_pictures.py <scratch ws>`, `tools/check_s7_share.py <scratch ws>`, `tools/make_role_map.py` (regenerates `data/simple/roles.json`), `tools/make_selftest_bundle.py`. `python -m skin_editor methods --markdown` regenerates the API table (a test keeps `docs/API.md` complete).
- **CI without `gh`:** `curl -s "https://api.github.com/repos/hubertlapinski3-cmyk/FMSKINEDITOR/actions/runs?branch=main&per_page=5"`.
- **The game:** `python -m skin_editor verify-stock` must say 67 of 67 before and after a game session. The `fm27` MCP tools read the running game (one call at a time; after each navigation the first `fm_screenshot` fails once, retry).
- **Frozen engine:** `python tools/freeze_engine.py --out <dir>` prints the pinned PyInstaller version and runs the self-test (including the bundle round trip).

## 5. Traps found this sitting
- Windows PowerShell and Git Bash quoting: write commit messages to a file or use a heredoc with a quoted delimiter; `python -c "..."` with backslashes in a bash string corrupts paths (use forward slashes or write a script file).
- A stray `dis.py` in the system TEMP folder shadows the standard library: run scratch Python from a folder of your own.
- `git add` warns that LF becomes CRLF; evidence files are `-text` on purpose (`.gitattributes`).
- The workspace for scratch work is a COPY (`vanilla`, `cache`, `state`, `config.json` with `workspace_dir` edited); never point a check at the real workspace unless it only reads.

## 6. The owner's own words, for the record
"I want to see what is missing on my own eyes": the Findings view (F in Advanced) was built for that. Open it first: it shows every theme on every screen with the screenshots and what the three-colour map does not change.
