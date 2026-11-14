# The offline render: a user guide

The render draws any layout of Football Manager 27 inside the Studio without starting the game, and tells you, for every element, which rules styled it and where each value came from. It is an **approximation of the game, not the game's renderer**: it says so on every render, and `docs/evidence/phase9-m7-calibration-20261114/calibration-report.md` publishes every number it was measured against, pass and fail.

## What you get

- **Draw a layout.** Activity bar, `R`. The left list holds the game's layouts (type to filter by name; the number beside a name is its element count). Click one and it is drawn in the middle with the game's own style sheets applied in the game's order. Width, height and zoom change the stage; the corner markers (red = a property the render cannot draw, amber = partly drawn) can be switched off.
- **Why does this element look like that?** Click an element. The right-hand panel lists the rules that matched it, lowest first (the last one wins), then every computed property with its value, its status (`mapped`, `partial`, `unmapped`, `unknown`) and the rule it came from. Click a rule to read it as USS; click a token chip to see its alias chain and where it is defined.
- **Change it.** With a project open, a game rule offers "Override in <project>" (adds a rule to the project's sheet) and a token offers a value box (adds a token override). A rule that already lives in your project opens in the editor at its line.
- **The reverse direction.** In the editor, put the caret on one of your own rules or on a `--token`: a bar under the editor says how many elements it styles in the layout you last rendered, and "Show in render" outlines them.
- **Vanilla or skin.** With a project open, the "skin" tick draws your edits over the game's styles; untick it to see the game as it ships. Every edit repaints the view (one repaint per change).

## Large layouts

Thirteen of the game's layouts went over the 200 ms budget; most hold 900 to 3,800 elements and the largest, `DetailedPreferencesBlock`, 5,487. Drawing all of them is slow and the data is large (29 MB for that one), so the render draws about **1,000 elements** first and says so: *"Large layout: 1,000 of 5,487 elements are drawn"*.

- A branch that was cut shows a dashed **"show N child elements"** button where its children would be. Click it to draw that branch; nothing else moves, and your selection stays.
- **"draw all"** in the banner draws everything (seconds, a large payload); "back to the capped view" returns.
- The cap is only for the view. The calibration fixtures and any call with `max_nodes: 0` use every element.
- Measured cached times for the 13 layouts that were over the 200 ms budget: all between 28 and 90 ms with the cap (the full renders took 23 to 545 ms; the first render after starting the engine is slower because the game's bundles are read once).

## What the render does not do

Read the notice at the top and the "What this render does not know" list under the stage. In short:

- **Data is a placeholder.** Bound text shows the layout's own sample text (underlined dotted, tooltip says "sample"), never real player or club data.
- **No runtime state.** There is no hover, press, focus or animation in the picture. (The game's own state rules are known and checked in the calibration report: hover colours of buttons, list rows, tiles and tabs match the game exactly; some elements get a hover flag with no style change.)
- **Code-built visuals are approximated or missing:** the tactics pitch and its players, the Training tile's schedule, charts and shot maps are drawn in code by the game.
- **Fonts and images:** the game's fonts are named, not drawn (a stand-in font is used, so text widths differ); atlas icons and images are drawn where they can be found.
- **Club colours.** Some surfaces are painted from the club's colours at run time; the render shows the game's default there.
- **Not applied in the skin view:** class renames, image and font swaps and raising a rule's specificity.

## How far to trust it

The published report compares the render with measurements taken inside the game (680 pass, 78 fail, 435 not comparable). Boxes within 8 px or 5 percent, colours and font sizes exactly. The failures are listed with a cause assigned **by rule, not row by row**, and the main causes are the ones above (code-built content, run-time colours, text width with the stand-in font). Use the render to see structure, which rule wins and where a value comes from; confirm pixel-exact spacing and anything data-driven in the game (the PREVIEW tab reloads your skin in the running game).

## Engine calls (for scripts)

`render.layouts`, `render.layout` (`max_nodes`, `open` for large layouts), `render.rule`, `render.table`, `render.screen`. The table and screen calls (a table view's header row as a placeholder; a screen's tiles placed on a grid of a given size, with your tile moves applied) are engine-only: the Studio does not draw them yet. Details: `docs/API.md`.
