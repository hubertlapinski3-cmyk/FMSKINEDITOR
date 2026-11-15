# Simple mode plan: a first skin for someone who has never skinned (for approval; no code written)

Written 2026-11-15 after the 1.1.0 release; AMENDED the same day after a second-party audit (the owner's amendments 8 to 15, each verified in the code before it was written in, section 0). Status: PROPOSAL. Nothing in this document is built. Statements about the current app were read from the code at 25eb4f1; statements about what a beginner does are assumptions and are marked as such.

## 0. Verification log of the audit amendments (2026-11-15; code read, and the Crimson export run offline into a scratch folder)

| # | Claim | Result |
|---|---|---|
| 8 | `project.create` with a preset makes an old-style single-file project with bundle output | **Verified.** `engine.py:716-722` saves the preset model with `project_mod.save`, which writes `<name>.skin.json` unless a folder exists (`project.py:309-312`); the model carries no `output` option, so it defaults to bundles (`projfmt.py:202`, `project.py:136`). The Studio shows the "Convert to folder" banner for it (`App.tsx:280`). |
| 8 | The native export skips class renames | **Verified**, and more: the offline export of Crimson (422 token overrides, 70 literal swaps, 66 scoped rules; written to a scratch folder, nothing in the workspace or the game) reports 2 skipped items: `class renames (2) cannot be expressed in USS` and `flatten_gradients is a bundle-build option; not exported`. **Not in that list, found by reading `native.py`:** (i) `skip_sheets` (17 sheets: PremierLeague, Bundesliga, EFLChampionship, UEFAChampionsLeague, UEFAEuropa, UEFASuperCup, UEFAUWCL, FIFAWC, FIFAWC2026, six language-direction and name-order sheets, TestsStyles) is not read by the native export at all, neither applied nor reported; (ii) the preset has no `club_colours` option, which defaults to "keep", so the native Crimson does not carry the dark-bar rules the bundle Crimson got from its class renames; (iii) 22 of the 70 literal swaps hit 0 rules (the export notes say so per swap, they are not in the skipped list). Output: 3 sheets (`tokens.uss`, `rules.uss`, `images.uss`), 422 tokens, 528 rules, 0 images, 0 problems, 0.03 s. |
| 9 | What the native club-colour option does | **Verified in `club_colours.py` and `native.py:198`.** Not "proven in the Crimson skin": that was the bundle build. **Not reproduced as worded:** "10 card frames hidden": the code has 3 selectors for the bound card frames (`CF_BOUND`); "10" is the figure in a code comment about frames in the game, not something the code counts. Session 1 (b) counts it. |
| 10 | `App.tsx:53` falls back to Expert when nothing is stored | **Verified:** `useState<Mode>((localStorage.getItem('studio.mode') as Mode) \|\| 'expert')`. A second place holds the word: every project file carries `"mode": "expert"` (`projfmt.py:203` and `208`); it is read only to be written back, so it is inert metadata, but the rename must migrate it too. |
| 13 | S3 screen counts and copied-rule counts | **Counts: partly verified.** A literal swap in a native export copies every game rule that uses the literal (`native.py:109-139`), so the copied-rule count exists before applying. `where.token` counts over ALL panels of the imported layout dump (`layout_view.py`), and a layout dump is produced in the game and imported (`layout.import`): a fresh install has none, and the call then returns the hint "No layout dump imported". The "of the 8 modelled screens" count therefore has to come from the shipped models (`data/models`, 8 screens), not from `where.token`. To be confirmed in S0. |
| 15 | The installer ships the eight `data/models` screenshots | **Verified:** `tools/freeze_engine.py` bundles all of `data/`; `data/models` holds club, competition, portal, recruitment, squad, tactics, tactics-instructions and training as JSON plus PNG, 11,886,365 bytes of PNG. The README's "four models ship" is out of date. **And this plan's first S5 was wrong:** it named `preview.evaluate`, which repaints those in-game screenshots. Corrected in S5. |
| 12 | A first-run style-index build exists to be timed | **NEW FINDING, not in the amendments, changes the plan:** the installed Studio has NO setup path. Nothing in `studio/src` calls `game.detect`, `game.select`, `snapshot.take` or `index.build`; the engine does not do it on its own either (`need_index` raises "no style index; take a vanilla snapshot and index first"). Detecting the game, taking the vanilla snapshot and building the index are reachable only from the command line (`python -m skin_editor`) and the old browser page's Setup tab. On a fresh install the Palette, native export and Crimson preset cannot work. This is B0 below and milestone S1a. |

Two items could not be verified offline and are carried as work, not assumed: the style-index build time (S0 measures it; it needs the game's bundles read into a scratch workspace) and the first render time on a fresh machine.

## 1. The goal, stated so it can fail

A person who has never made a skin installs FM Skin Studio, and within ten minutes, without opening a document, has a recoloured skin showing in the game. Today that person stops at one of the points in section 2.

Acceptance is a scripted first-run test (section 9), with the clock defined in advance. It is not "the views exist".

## 2. Where a beginner stops today (read from the code)

| # | What happens | Where |
|---|---|---|
| B0 | **A fresh install cannot get started in the Studio:** no game detection, no vanilla snapshot, no style index (section 0). | `studio/src` (no call), `engine.py:101-104`, `engine.py:137-171` |
| B1 | The app opens on a file explorer in Expert mode. `mode` falls back to `'expert'` when nothing is stored. | `studio/src/App.tsx:53` |
| B2 | Simple mode only hides files (everything except `styles/tokens.uss` and `images/`). The views, buttons and wording are the same. | `App.tsx:37`, `App.tsx:232` |
| B3 | The sidebar is eleven single letters (E S P I L T V R ? U G); the meaning is in tooltips only. | `App.tsx:242-252` |
| B4 | A new project is a browser prompt for a name and opens empty. The one preset (`crimson`) cannot be reached from the Studio, and made from the engine it is a legacy single-file bundle project (section 0, #8). | `App.tsx:151-155`, `engine.py:716` |
| B5 | The palette is empty until the user searches for a token by name or hex. | `studio/src/Palette.tsx:40` |
| B6 | Changing the colour of something seen on screen means knowing which token or rule paints it. The render knows (`tokenPaths`, the origins of every value), but only in the direction editor to render, and only as a highlight. | `App.tsx:302-317`, `Render.tsx` |
| B7 | Applying is four buttons and two routes; using both applies changes twice (README). After a native export nothing in the Studio says the skin must be picked once in the game's Preferences; that sentence is in the PREVIEW tab and in a text file inside the exported folder. | `App.tsx:337-340`, `native.py:298` |
| B8 | The only in-app preview of the real game needs the inspector plugin; without it the message is a pipe name. An empty project exports "0 tokens, 0 rules, 0 images" with no warning. | `Preview.tsx:42-48` |
| B9 | Errors go to an OUTPUT log as `ERROR <message> (code N)`. | `App.tsx:70` |

Not a beginner problem and not touched: the engine, the render model, the calibration, the bundle route, the tile / table / layout editors. They stay under Advanced.

## 3. What is built, in the order it removes the most

### S0. Inventory and measurements (offline, generated, no UI)
- `data/simple/token-inventory.json` from the style index: every colour token, its vanilla value, how many game rules use it, what it paints. A second script lists what the Crimson preset maps each token to. This decides whether S4 is feasible as designed; if a handful of roles cannot cover the tokens, S4 is redesigned before it is built, and that is reported.
- **Crimson, natively, offline** (started, see section 0): export it into a scratch folder and list everything the export's own skipped list reports, plus what the export does not report (the `skip_sheets` and club-colour findings above). The list is the input to S1's Crimson decision and to Session 1 (a).
- **Measure, in a scratch workspace, never the real one:** the style-index build time and the vanilla snapshot time, and the time of the first render of a layout on a machine with an empty cache (component times for section 9).
- Verify, not assume: whether `literal_swaps` is usable from a click (S3); which counts S3 can show without a layout dump (section 0, #13).

**S0 results (2026-11-15, run alone while the owner was away; offline; `tools/make_token_inventory.py`, data in `data/simple/token-inventory.json` and `docs/evidence/phase9-s0-measurements-20261115.json`; the game folder was only read, and the tactics bundle's hash was checked unchanged before and after):**
- **Inventory:** 2,059 tokens, 1,481 of them colour tokens in 139 families; 740 colour tokens are used by at least one rule and 741 by none. Crimson overrides 422 tokens, 418 of them colour tokens; the 418 reach 4,340 of the 10,687 rule paths that colour tokens reach (41%), 11 colour tokens have different values in different sheets. Meaning for S4: a three-colour theme has to produce values for several hundred tokens to match what Crimson does by hand, so the role map is a large table, not a handful of rows; whether it can be smaller without losing the look is NOT shown by these numbers and is Session 2's question.
- **First-run timings on this machine, one run, scratch workspace:** vanilla snapshot copy 0.15 s (the snapshot holds only the 2 style bundles, 1.5 MB); cold style-index build 0.80 s (49 sheets, 2,059 tokens, 3.6 MB cache; warm load 0.08 s); render layout list on an empty cache 1.5 s; the FIRST layout render on an empty cache 9.1 s (`Intro`, 37 elements: the cost is loading and cascading the game's sheets, not the layout), the same layout again 0.00 s; the render cache after that is 9.6 MB in 15 files. So the setup the Studio lacks (S1a) is cheap in time; what costs is the first render. A slower disk or a larger library will differ: these are one machine's numbers and are used only as the first entries of the section 9 clock.
- **Not yet done in S0:** the Crimson role comparison beyond the counts above; the check whether `literal_swaps` is usable from a click; the S3 count source (needs the shipped models read for regions). They stay open.

### S1a. First-run setup inside the Studio (NEW)
"Find the game, read it once": detect the install (`game.detect`, a folder picker when none is found), take the vanilla snapshot (`snapshot.take`, game closed), build the index (`index.build` as a job with progress), each with a plain sentence and a progress bar, and a result the rest of the Studio waits for. Failure messages follow S1's table. Without this nothing after it works for a new user.

### S1. A front door
- **Start screen** when no project is open: "Start from a ready-made theme", "Open a skin I downloaded" (`project.import_native`, built), "Start from the game's look" (`project.create_folder` with target native). A name is suggested, not demanded.
- **Crimson (amended):** created as a FOLDER project with `output` = native from the start (the preset's model is migrated and written with `projfmt.write`, not saved as a single file), never through `project.create`'s current path. It ships labelled **"not yet checked in the game in this form"** until Session 1 (a) has looked at it. The skipped and unreported items from S0 are shown to the user in plain words where they change the look (club colours stay as the game paints them; league and club sheets that the bundle build skipped are not skipped).
- **Club colours, asked at creation (amended):** "Do you want the club's own colours kept?" with the plain description of what removing them does in the native route (below), never the words "proven in the Crimson skin". What the native option does, from the code: the navigation bars' text and icon colours are set to the dark-bar values on the game's `.nav-on-light` rules (so light club colours stay readable); the club wallpaper (its 2D image and the 3D render texture) stops drawing; the club's card frames and the news header bands are hidden and filled with one flat colour; the kit strip and its outline disappear. It is a native rule set that has not been looked at in the game in this form (the proof was the bundle build). No default is revisited before Session 1 (b) has looked at a light-club save and a dark-club save.
- **Labelled navigation in Simple mode:** Colours, Pictures, Look at it, Put it in the game. The letters stay in Advanced.
- **Mode (amended):** a fresh install is detected by an EMPTY WORKSPACE (no projects), not by the missing setting: only then is the default Simple. An existing install (any project present, or any stored mode) is written `advanced` on first launch of the new version. The stored value `expert` is migrated to `advanced` everywhere it is stored: the `studio.mode` browser setting and the `"mode"` field of every project file (inert, but renamed with the rest). "Advanced" replaces "Expert" in the interface.
- **Plain messages.** One table maps the engine's reasons to sentences ("The game isn't open, so this is an offline picture"; "You haven't changed anything yet"; "This project has a mistake in a file; open Advanced to see it"). The raw text stays under "details". The table is data, with a test that every reason the engine can return has a sentence.

### S2. One way into the game
- **One button, "Put it in the game"**, in Simple mode: the native route only (`native.export`), which changes no game file. Bundles are not offered in Simple mode.
- **After it runs**, the two steps left are shown with the skin's name filled in: pick it once in Preferences, press Reload Skin. On later runs only the second. The Studio cannot tell, offline, whether the user did the first; it says what was written and what is left to do.
- **"Take it out of the game" (amended):** deletes the skin's folder, only when it carries the editor's marker (`.fm27se-export.json`), after a confirmation that shows the folder. The removal text says first: "Switch to the default skin in Preferences, then remove it." What happens when the SELECTED skin's folder is deleted has never been observed (game restart, Reload Skin); it is item (e) of Session 1, run last. **If (e) shows breakage, the removal button stays out of 1.2.0**; until (e) is run the button is built behind the setting and not in the release candidate.
- **Guard:** the button is disabled with a plain sentence while the project changes nothing.

### S3. Click it, recolour it
In Simple mode the render becomes pickable: click an element, get a small panel with the colours it shows, each with a picker.
- A colour from a token changes a token override. Before applying, the panel states how many other elements in this layout use the token and **how many of the 8 modelled screens (club, competition, portal, recruitment, squad, tactics, tactics-instructions, training) change with it**, from the shipped models, not from a layout dump (section 0, #13).
- A colour that is a literal in a game rule is offered through `literal_swaps` only if S0 shows it is safe from a click. In a native skin a literal change COPIES every game rule that uses the literal, so the panel shows the copied-rule count before applying, beside the use count and the selector count. Otherwise it says "this colour is fixed in the game" and points to Advanced. No scoped rule is written by a click in this version.
- A colour the render cannot attribute (run-time club colours, code-drawn visuals: the known gaps of the calibration report) is shown as such: "the game paints this while running; it can't be changed here".
- "Put it back" on every change.
Uses the render's existing origin data; adds no render rule (the two-source rule is not engaged); inherits every limit of the render.

### S4. A theme from three colours
The user picks a background, an accent and a text colour (and dark or light); the Studio writes the token overrides for the whole palette.
- A **role map** (`data/simple/roles.json`) assigns tokens to roles; ramps between the inputs are computed the way the Crimson preset computes its own.
- **Every role-map entry is marked `unverified` until the in-game check (amended).** Both sources (the Crimson preset and the token's usage in the game's rules) are inferences, and Crimson's own native form has not been looked at in the game yet (Session 1 (a)). An entry has no other status in this plan; the gallery says "not yet checked in the game" for every theme until Session 2 has recorded it.
- **Checks, automated:** every token in the map exists in the style index of the current build; the export of a generated theme writes more than zero tokens; **contrast (ratio 4.5) is checked on EVERY theme generated from the user's own colours, at the moment of generation, and fails loudly** (the generate button reports the failing pairs and does not write the theme) (amended; not only on the gallery). The project model already has `contrast_pairs`.
- A small **gallery** of themes generated by the same code (not hand-made files), plus Crimson as it is.
- **Gate: Session 2** (below).

### S5. A preview that needs nothing, and shows no screenshot
In Simple mode "Look at it" shows the OFFLINE RENDER on both sides of a before / after switch: the same showcase layouts rendered without and with the project (`render.layout`, `render.screen`), with the approximation notice the render already carries. **No in-game screenshot appears anywhere in Simple mode (amended):** the static repaint of `preview.evaluate` paints regions over the `data/models` PNGs, which are in-game screenshots with real club and player names, so it is NOT used. Where any component would show one of them it is replaced by a code-drawn placeholder (a labelled grid of the screen's regions), and a test fails if a Simple-mode view requests `preview.image` or `preview.live_image`. The live preview through the inspector stays in Advanced, unchanged. W9 (the repo and the installer holding those screenshots) no longer gates 1.2.0, but its record states that the installer still ships them (`PHASE9-PLAN.md`, W9 amendment).

### S6. Pictures in three steps
The Images view already swaps pictures and knows the wallpaper places. Simple mode gets a short path through it: choose a picture, tick where it shows, see it in S5. No new engine work is expected; S0-style verification of that claim is part of the milestone.

### S7. Share and undo
"Save my skin as a file" (a zip of the exported native folder), "Open a skin file" (unzip to a temporary folder, then the existing read-only import), "Start over" (back to the game's look; the previous state goes to the workspace trash).

### S8. Words and release
A one-page "your first skin" guide generated from the same message table, with screenshots of the Studio (not of the game); the README's Studio section rewritten around Simple mode; release through the standing checklist (`PHASE9-PLAN.md`, Release checklist).

## 4. What is deliberately not in it
No tile, table or layout editing in Simple mode. No bundle route in Simple mode. No new render rule and no change to the calibration; the 1.0.0 and 1.1.0 report folders are untouched. No plugin or inspector change, no automation of the game's Preferences. No claim that the offline picture is the game, and no in-game screenshot in Simple mode.

## 5. Milestones and estimates (working days, one developer; estimates, not commitments)

| Milestone | Content | Days | Needs the game |
|---|---|---|---|
| S0 | Inventory, Crimson native audit, measurements, feasibility | 1.5 | no |
| S1a | First-run setup in the Studio (NEW) | 2.5 | no |
| S1 | Start screen, Crimson as a native folder project, club-colour question, labelled navigation, mode migration, message table | 3 | no |
| S2 | One apply button, steps, removal (behind a setting until Session 1 (e)), empty guard | 1.5 | removal only |
| S5 | Before / after offline preview, no screenshots | 1.5 | no |
| S3 | Click to recolour | 3 | no |
| S4 | Role map, generator, gallery, checks | 4 | Session 2 |
| S6 | Pictures path | 1 | no |
| S7 | Share, start over | 1 | no |
| S8 | Guide, README, release | 1 | no |

Order: S0, S1a, S1, S2, S5, S3, S4, S6, S7, S8.

## 6. Release shape (amended)
- **1.2.0:** S0, S1a, S1, S2, S5. **The earlier claim that 1.2.0 needs no game time is withdrawn:** Crimson's native form and the native club-colour removal have never been looked at in the game, and the removal button depends on observation (e). The 1.2.0 release candidate is built only after Session 1; what Session 1 does not clear ships labelled "not yet checked in the game" or stays out (the removal button).
- **1.3.0:** S3, S4, S6, S7, S8, after Session 2.
Each goes through the standing release checklist: suites, type gate, linter, CI green, the read-only audit of origin/main, the owner's approval, the post-run checks, the freeze line and the manifest hashes.

## 7. Risks
1. **The role map is wrong in places the offline render cannot show** (run-time or code-drawn surfaces). Mitigation: every entry `unverified`; the in-game gate before any theme is called working; Crimson as the base only after Session 1 (a). Not mitigated: a later game update that renames tokens (the update diff and the map's existence check will show it).
2. **The approximation misleads a beginner more than an expert.** Mitigation: before / after of two offline renders, the notice kept, "the game paints this while running" where the render cannot attribute a colour, no quality number restated in Simple mode.
3. **Simple and Advanced edit the same project.** A project broken in Advanced locks Simple mode out until fixed; the plain message points to Advanced; no automatic repair.
4. **The Preferences step cannot be removed or checked offline.** One step, once per skin name; a fixed skin name per project; clear wording; a failure there is recorded as a finding.
5. **First-run setup is the biggest unknown** (S1a): it reads the game's bundles, takes a snapshot of them and decodes every stylesheet. Its time and failure modes on a clean machine are unmeasured; the section 9 clock records it as its own component.
6. **Scope.** Ten milestones; the split in section 6 is the mitigation.

## 8. Decisions
Settled by the owner's amendments (2026-11-15): Simple is the default for a fresh install (detected by an empty workspace), existing installs become Advanced, "Expert" is renamed "Advanced" with its stored values migrated; the creation dialogue asks about club colours and states what the native option does; Crimson is a native folder project labelled unchecked; removal waits for Session 1 (e). Still open: (1) the release split as in section 6 (recommended); (2) the theme inputs, three colours plus dark / light (recommended, to be confirmed by S0's inventory); (3) who the first-run tester is and whether the owner runs the script or watches; (4) the fixed screen list for the game sessions (`docs/SESSIONS-simple-mode-checklist.md` proposes the eight modelled screens; the owner confirms or replaces it).

## 9. Acceptance
- **Automated:** vitest for the start screen, first-run setup states, the apply flow, the message table (every engine reason has a sentence), the pick panel, the mode migration (a stored `expert` becomes `advanced`; an empty workspace is Simple; a workspace with a project is Advanced) and the no-screenshot rule for Simple mode; engine tests for the generator (tokens exist, contrast fails loudly on a bad theme, non-empty export), for Crimson as a folder project with native output, and for removal (only a folder with the editor's marker).
- **First-run test (1.2.0), the clock written down before the release candidate:** starting conditions: the game installed and closed, a save available, the Studio installer downloaded, no Studio workspace. **The clock starts when the installer is started and stops when the skin is visible in the game on a named screen** (the screen is named in advance; proposed: the squad screen). Component times recorded separately: installer, first-run setup (game detection, snapshot, style-index build), first render, export, game start, save load, skin visible. Recorded verbatim: every point where the person stopped or asked. Pass: under ten minutes of the person's own time (game start and save load are reported but the person is not waiting on the Studio for them), no document opened, no question the Studio should have answered. One person is one data point and is reported as that. The style-index build time is measured in S0 first so the target is not set blind.
- **In-game gates:** Sessions 1 and 2 (`docs/SESSIONS-simple-mode-checklist.md`), one record per item, findings fixed or the item removed from the release, never relabelled.
