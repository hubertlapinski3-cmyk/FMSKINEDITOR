# Walkthrough record, run 1 (2026-11-15): checklist sections D and E, partly

Run by a screen-driving Claude following `docs/WALKTHROUGH-FOR-CLAUDE.md` against the browser form of the Studio (test workspace, no game). This is its report, recorded as returned; the notes in brackets are mine. **Not a pass of any section:** the run stopped in section E, and nothing from F onward was run.

## Why it stopped
After E3 the reviewer reloaded the page with an address carrying a placeholder token (the real token was hidden from it). The Studio then showed "The Studio can't reach its engine. Close the Studio and open it again." It did not try to repair it. [A mistake in the brief, not a Studio defect: the brief now forbids rebuilding the address.]

## Setup
A1 to A3 COULD NOT CHECK: the setup was already done in the workspace, and the Studio opened in Advanced with a project `s` open. [An existing install opens in Advanced by design.]

## Results, line by line
- **G1 MATCH:** four start titles: "Start from a ready-made theme", "Make a theme from three colours", "Open a skin I downloaded", "Start from the game's look".
- **G2 (partly):** four themes listed, Crimson ("the dark crimson look") and Forest, Ocean, Slate and amber, the last three "not yet checked in the game", each with three colour squares. [The brief said five by mistake; four is right.] Ocean and its **Make it** were not run.
- **D1 MATCH:** the six layouts and the search box ("Part of a layout's name ..."); the first-time line: "Reading the game's styles for the first time. This takes about ten seconds and happens once."
- **D2 MATCH:** "The game as it ships" and "With my skin: my-first-skin-2"; left blue-navy, right dark brown; "visible but subtle".
- **D3 MATCH:** each button shows only what its name says; Side by side shows both.
- **D4 MATCH:** the approximation line appears once, above the pictures: "Approximation, not the game's renderer: bindings and data render as placeholders, there are no hover or animation states, code-bound visuals are approximated, and the sheets and runtime classes listed under `gaps` are not applied."
- **D5 DIFFERENT (observations):** all five other layouts open. Training tile and Atmosphere tile show text only; the Tactics tile is all green; the Preferences card loaded slowly and showed button-like items. Searching "Squad" lists 13 results; SquadScreen opened but both sides were blank when looked at, and the reviewer did not wait for it to render. [Needs a re-check with a wait.]
- **D6 MATCH:** Simple mode bottom tabs PROBLEMS and OUTPUT; Advanced adds BUILD and PREVIEW; S returned to Simple; 0 `img` elements in Simple mode.
- **D7 COULD NOT CHECK** (engine lost).
- **E1 DIFFERENT (observations):** "MY COLOURS (0/10)" with "Nothing saved yet. Save up to 10 colours here; they then appear as one-click choices beside every colour picker." Adding grey gave `#808080` with an "×" and 1/10. Adding it again: "#808080 is already in My colours." Nine more colours (set by script, not the picker) reached 10/10; **the Add button turned off with no reason on screen** [fixed in 18b11a2]; the star at 10/10 said "My colours holds 10. Remove one first."
- **E2 DIFFERENT (observations):** each row has a star and a small arrow, plus "used in 4" and "put back" when changed. The star saved the row's colour (`#171717`); the arrow opened a strip of saved colours, and picking `#112233` set the row to it. "put back" returned the game's own colour `#232735`, not the previous pick: as specified.
- **E3 DIFFERENT (observation):** with "One flat colour instead of each club's colours" ticked, a star and a row of ten "Use #..." buttons sit beside the colour; **no arrow**. [By design: the choices are already showing. The checklist is corrected.]
- **E4 COULD NOT CHECK** (the reload that broke the session).
- **F, G2 to G6, H, I: not run.**

## Screenshots
S-start captured; S-look captured (the sides differ subtly). S-colours, S-put and S-wallpaper not captured.

## Owner-only items
H3 (stretched wallpaper) and I2 (exported skin, not the project): not reached.

## Reviewer's notes (guesses and confusing points)
- The side-by-side difference in Look at it is hard to see.
- "Reading the game's styles for the first time" can leave Look at it empty for about 10 seconds.
- "My colours" gave no on-screen reason when the button turned off at 10. [Fixed.]
- "Used in 4" does not say what it counts. [Fixed: "used in 4 places", with a tooltip.]
- Layouts open one at a time, slowly, with blank frames.
- The Top bar row differs from the other rows (inline "Use #..." buttons, no arrow). [Documented.]
- The brief expected five themes; the Studio shows four. [Brief fixed.]

## Still open from this run
D5 SquadScreen re-check with a wait; D7; E4; all of F, G (from the theme build on), H and I; screenshots S-colours and S-put; the owner-only judgments H3 and I2; whether the subtle before/after difference (D2) and the blank frames while a layout draws are acceptable.
