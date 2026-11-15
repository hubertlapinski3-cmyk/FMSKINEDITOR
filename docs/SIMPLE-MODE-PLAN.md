# Simple mode plan: a first skin for someone who has never skinned (for approval; no code written)

Written 2026-11-15, after the 1.1.0 release. Status: PROPOSAL. Nothing in this document is built. Every statement about the current app was read from the code at 32aef80; statements about what a beginner does are assumptions and are marked as such.

## 1. The goal, stated so it can fail

A person who has never made a skin installs FM Skin Studio, and within ten minutes, without opening a document, has a recoloured skin showing in the game. Today that person stops at one of the points in section 2.

Acceptance is a scripted first-run test with a person who has not used the Studio (section 9), recorded with its date. It is not "the views exist".

## 2. Where a beginner stops today (read from the code)

| # | What happens | Where |
|---|---|---|
| B1 | The app opens on a file explorer in Expert mode. `mode` defaults to `'expert'`. | `studio/src/App.tsx:53` |
| B2 | Simple mode only hides files (everything except `styles/tokens.uss` and `images/`). The views, buttons and wording are the same. | `App.tsx:37`, `App.tsx:232` |
| B3 | The sidebar is eleven single letters (E S P I L T V R ? U G); the meaning is in tooltips only. | `App.tsx:242-252` |
| B4 | A new project is a browser prompt for a name and opens empty. There is no starting point in the Studio, although the engine has one preset (`crimson`) and can start a project from another skin's colours (`compare.import`). | `App.tsx:151-155`, `skin_editor/presets/__init__.py` |
| B5 | The palette is empty until the user searches for a token by name or hex. A beginner does not know `--colours-ui-deep` exists. | `studio/src/Palette.tsx:40` |
| B6 | Changing the colour of something seen on screen means knowing which token or rule paints it. The render already knows (`tokenPaths`, the origins of every value), but only in the direction editor to render, and only as a highlight. | `App.tsx:302-317`, `Render.tsx` |
| B7 | Applying is four buttons and two routes (Export native skin, Build bundles, Install build, Restore stock); using both routes applies changes twice (README). After a native export nothing in the Studio says the skin must be picked once in the game's Preferences; that sentence is in the PREVIEW tab and in a text file inside the exported folder. | `App.tsx:337-340`, `native.py:298` |
| B8 | The only in-app preview of the real game needs the inspector plugin. Without it the message is a pipe name. An empty project exports "0 tokens, 0 rules, 0 images" with no warning. | `Preview.tsx:42-48` |
| B9 | Errors go to an OUTPUT log as `ERROR <message> (code N)`. | `App.tsx:70` |

Not a beginner problem and not touched by this plan: the engine, the render model, the calibration, the bundle route, the tile / table / layout editors. They stay where they are, under Advanced.

## 3. What is built, in the order it removes the most

### S0. Inventory (offline, generated, no UI)
A script writes `data/simple/token-inventory.json` from the style index: every colour token, its vanilla value, how many game rules use it, and what `where.token` says it paints. A second script lists what the Crimson preset maps each token to. This is the raw material for S4 and decides whether S4 is feasible as designed; if the inventory shows that a handful of roles cannot cover the tokens, S4 is redesigned before it is built, and that is reported.

To verify here, not assumed: how many colour tokens there are; how many the Crimson preset overrides; whether `literal_swaps` (in the project model, `project.py:16`) is usable from a click (S3).

### S1. A front door
- **Start screen** when no project is open: "Start from a ready-made theme" (S4; until S4 exists, the Crimson preset through `project.create`), "Open a skin I downloaded" (`project.import_native`, already built), "Start from the game's look" (`project.create_folder`). A name is suggested, not demanded.
- **Labelled navigation in Simple mode:** Colours, Pictures, Look at it, Put it in the game. The letters stay in Advanced.
- **Simple is the default for a fresh install.** An existing install keeps its stored mode. "Advanced" replaces "Expert" as the label (a decision, section 8).
- **Plain messages.** One table maps the engine's reasons to sentences: "The game isn't open, so this is an offline picture" for the missing pipe; "You haven't changed anything yet" for an empty export; "This project has a mistake in a file; open Advanced to see it" for a project that does not compile. The raw text stays available behind "details". The table is data with a test that every reason the engine can return has a sentence.

### S2. One way into the game
- **One button, "Put it in the game"**, in Simple mode: the native route only (`native.export`), which changes no game file. Bundles are not offered in Simple mode.
- **After it runs**, the two steps left are shown with the skin's name filled in: pick it once in Preferences, press Reload Skin. On later runs only the second.
- **"Take it out of the game"**: deletes the folder, only when it carries the editor's own marker (`.fm27se-export.json`, already written by the export), after a confirmation that shows the folder.
- **Guard:** the button is disabled with the sentence from S1 while the project changes nothing.

The Studio cannot tell, offline, whether the user picked the skin in Preferences. It will not claim the skin is active; it says what was written and what is left to do.

### S3. Click it, recolour it
In Simple mode the render becomes pickable: click an element, get a small panel with the colours that element shows (background, text, border), each with a picker.
- A colour that comes from a token is changed by a token override, and the panel says how many other elements in this layout and how many screens (`where.token`) change with it, before the change is made.
- A colour that is a literal in a game rule is offered through `literal_swaps` if S0 shows that is safe from a click; otherwise the panel says "this colour is fixed in the game" and points to Advanced. No scoped rule is written by a click in this version.
- A colour the render cannot attribute (run-time club colours, code-drawn visuals: the known gaps of the calibration report) is shown as such: "the game paints this while running; it can't be changed here".
- "Put it back" on every change (removes the override).

This uses the render's existing origin data. It adds no render rule, so the two-source rule is not engaged; it does inherit every limit of the render (section 7, risk 2).

### S4. A theme from three colours
The user picks a background, an accent and a text colour (and dark or light); the Studio writes the token overrides for the whole palette.
- A **role map** (`data/simple/roles.json`) assigns tokens to roles (page background, raised surface, hover, selection, accent, accent text, primary text, secondary text, positive, negative, ...). Ramps between the three inputs are computed the way the Crimson preset computes its own.
- **Sources for the map:** the Crimson preset (proven in game) is one; the token's usage in the game's rules (S0) is the second. An entry with one source only is marked `unverified` in the file and counted in the theme's own summary. No entry is typed without a source.
- **Checks, automated:** every token in the map exists in the style index of the current build; text over background meets a contrast ratio of 4.5 for every generated theme in the gallery (the project model already has `contrast_pairs`); the export of a generated theme writes more than zero tokens.
- **A small gallery** of ready-made themes generated by the same code (not hand-made files), plus Crimson as it is.
- **Club colours:** a generated dark theme with light club colours left on is the case the Crimson work solved with "Remove club colours". Whether that option is on by default for generated themes is a decision (section 8).
- **Gate: one owner-present session in the game.** The offline render cannot show run-time colours or code-drawn visuals, so a generated theme is not called working until it has been looked at in the game on a fixed list of screens. Until then the gallery says "not yet checked in the game". This is the only part of the plan that needs the game.

### S5. A preview that needs nothing
In Simple mode "Look at it" shows a fixed set of showcase layouts and the measured screens (`preview.evaluate`, `render.layout`), with a before / after switch, and the approximation notice the render already carries. The live preview through the inspector stays in Advanced, unchanged.

### S6. Pictures in three steps
The Images view already swaps pictures and already knows the wallpaper places (report pages, main screens, start screen, loading, match intro). Simple mode gets a short path through it: choose a picture, tick where it shows, see it in S5. No new engine work is expected; S0-style verification of that claim is part of the milestone.

### S7. Share and undo
- "Save my skin as a file" (a zip of the exported native folder) and "Open a skin file" (unzip to a temporary folder, then the existing import, which only reads).
- "Start over" on the project (back to the game's look), with the previous state kept in the workspace trash, as project deletion already does.

### S8. Words and release
A one-page "your first skin" guide generated from the same message table and screenshots of the Studio (not of the game); the README's Studio section rewritten around Simple mode; release through the standing pre-tag audit.

## 4. What is deliberately not in it
- No tile, table or layout editing in Simple mode. No bundle route in Simple mode.
- No new render rule and no change to the calibration. The reports of 1.0.0 and 1.1.0 are untouched.
- No plugin, no inspector change, no automation of the game's Preferences.
- No claim that the offline picture is the game.

## 5. Milestones and estimates (working days, one developer; estimates, not commitments)

| Milestone | Content | Days | Needs the game |
|---|---|---|---|
| S0 | Inventory, feasibility of S3 literals and S4 roles | 1 | no |
| S1 | Start screen, labelled navigation, default mode, message table | 2 | no |
| S2 | One apply button, steps, removal, empty guard | 1.5 | no |
| S5 | Before / after preview on showcase screens | 1.5 | no |
| S3 | Click to recolour | 3 | no |
| S4 | Role map, generator, gallery, checks | 4 | one owner-present session |
| S6 | Pictures path | 1 | no |
| S7 | Share, start over | 1 | no |
| S8 | Guide, README, release | 1 | no |

Order of building: S0, S1, S2, S5, S3, S4, S6, S7, S8. The first four remove B1, B3, B4 (with Crimson only), B7, B8 and B9 and can ship alone.

## 6. Release shape (recommended)
- **1.2.0:** S0, S1, S2, S5. All offline. A beginner can start from Crimson or an imported skin, see it, and put it in the game.
- **1.3.0:** S3, S4, S6, S7, S8. Contains the one game session.

Each goes through the standing gate: suites, type gate, linter, CI green, then a read-only audit against origin/main before the tag, then the owner's approval.

## 7. Risks
1. **The role map is wrong in places the offline render cannot show.** A theme that looks right in the Studio shows a wrong colour in the game on a run-time or code-drawn surface. Mitigation: Crimson as the proven base; `unverified` entries counted and shown; the in-game gate before any theme is called working. Not mitigated: a later game update that renames tokens; the existing update diff (`update.diff`) will show it, and the map's existence check will fail on the new build's index.
2. **The approximation misleads a beginner more than an expert.** An expert reads the notice; a beginner sees a picture. Mitigation: the before / after switch (the difference between two approximations is more trustworthy than either), the notice kept, and "the game paints this while running" on unattributable colours in S3. The published calibration numbers are not restated in Simple mode as a quality claim.
3. **Simple and Advanced edit the same project.** Simple mode writes through the project model, which rewrites `styles/tokens.uss`; the palette already refuses a project that does not compile (`Palette.tsx:34`). A project broken in Advanced locks Simple mode out until fixed. Mitigation: the plain message from S1; no automatic repair.
4. **The step in the game's Preferences cannot be removed or checked offline.** It is one step, once per skin name. Mitigation: a fixed skin name per project so it is picked once; clear wording. If first-run testing shows people fail here, that is recorded as a finding, not papered over.
5. **Scope.** Nine milestones. The split in section 6 is the mitigation; 1.2.0 is useful without 1.3.0.

## 8. Decisions for the owner
1. **Default mode:** Simple for fresh installs, stored mode kept for existing ones, "Advanced" as the name of the other mode. Recommended: yes.
2. **Release split** as in section 6, or one release. Recommended: split.
3. **Theme inputs:** three colours plus dark / light, with more behind "more colours". Recommended: three. To be confirmed or changed by S0's inventory.
4. **"Remove club colours" on by default for generated themes.** Recommended: on, with a visible switch, because it is the configuration proven in the Crimson skin. It changes what the user sees for every club, so it is the owner's call.
5. **Bundles absent from Simple mode entirely.** Recommended: yes.
6. **The first-run test person** (section 9): who, and whether the owner runs the script or watches.

## 9. Acceptance
- **Automated:** vitest for the start screen, the apply flow, the message table (every engine reason has a sentence) and the pick panel; engine tests for the generator (tokens exist, contrast, non-empty export) and for removal (only a folder with the editor's marker). Existing suites, type gate and linter unchanged in strictness.
- **First-run test (1.2.0):** a person who has not used the Studio, given only the installer, is asked to "make the game look different and see it in the game". Recorded: time to the skin showing in the game, every point where they stopped or asked, verbatim. Pass: under ten minutes, no document opened, no question that the Studio should have answered. One person is one data point; it is reported as that.
- **In-game gate (1.3.0):** each gallery theme looked at in the game by the owner on the fixed screen list; findings recorded per theme; a theme that fails is fixed or removed from the gallery, not relabelled.
