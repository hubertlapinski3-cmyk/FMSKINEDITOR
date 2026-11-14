# Render calibration report

Tolerance: box x, y, width, height within 8 px or 5 percent of the measured size, whichever is tighter; colours, font sizes and flex values exactly equal. Every row is published: PASS, FAIL, or N/A (nothing to compare). Nothing is filtered, averaged or re-toleranced.

**Totals: 660 pass, 77 fail, 431 n/a.**

| Fixture | Pass | Fail | N/A | Source |
|---|---|---|---|---|
| c3-table-header | 3 | 0 | 0 | c3-table screenshot 2026-11-13 and the header row written down in INGAME-CHECKLIST.md (Picked, Inf, Player, Pace, Acceleration, Agility, Balance, Natural Fitness, Stamina, Strength; stock order with Jumping Reach); project p7-table-test-3 |
| p6-magenta-reload-skin | 2 | 0 | 0 | p6-class-test (the owner's project), PHASE6-EVIDENCE: magenta seen around the Reload Skin row in game, screenshot held by the owner |
| phase3-red-pitch | 2 | 0 | 0 | LEARNINGS.md Phase 3 rule and the in-game screenshot held by the owner. NOTE: no layout holds an element with this class (the game adds it in code), so the check runs on a synthetic node carrying the class: it verifies the cascade (the project's rule wins over the game's), NOT that the element is the pitch container. CORRECTION recorded 2026-11-14: the first version of this fixture expected the game's own colour to be #DA0037, as LEARNINGS.md (section on the Crimson skin's pitch) states; the framework's first run showed the game's own rule in this build is #036150 (AlwaysAppliedStyleSheet rule 3904 and FigmaGeneratedStyles 2964; no pitch rule holds #DA0037), so the expectation was a fixture error taken from a note about a skin, and it was fixed to the game's data, not to the render's output by tolerance. |
| screen-squad-large-1600 | 5 | 0 | 0 | capture styles-d6-squad-overview-medium-20261114-113402.ndjson (plugin 0.3.1-capture); hosts of the grid container; the run-time slots are GIVEN (cells from the capture) and are not predictions |
| screen-squad-large-1680 | 5 | 0 | 0 | capture styles-e2-squad-small-20261114-115336.ndjson (plugin 0.4.0-capture); hosts of the grid container; the run-time slots are GIVEN (cells from the capture) and are not predictions |
| screen-squad-large-2500 | 5 | 0 | 0 | capture styles-d1-squad-overview-20261114-111054.ndjson (plugin 0.3.1-capture); hosts of the grid container; the run-time slots are GIVEN (cells from the capture) and are not predictions |
| screen-squad-small | 5 | 0 | 0 | capture styles-e3-squad-1152x864-20261114-115626.ndjson (plugin 0.4.0-capture); hosts of the grid container; the run-time slots are GIVEN (cells from the capture) and are not predictions |
| screen-squad-standard | 5 | 0 | 0 | capture styles-e4-squad-1600x900-20261114-115839.ndjson (plugin 0.4.0-capture); hosts of the grid container; the run-time slots are GIVEN (cells from the capture) and are not predictions |
| screen-team-instructions-large | 3 | 0 | 0 | capture styles-d2-team-instructions-20261114-111314.ndjson (plugin 0.3.1-capture); hosts of the grid container; the run-time slots are GIVEN (cells from the capture) and are not predictions |
| tile-atmosphere | 78 | 5 | 51 | capture styles-e1-squad-bindings-20261114-115217.ndjson, host Atmosphere |
| tile-loans | 77 | 4 | 52 | capture styles-e1-squad-bindings-20261114-115217.ndjson, host Loans |
| tile-loans-c2-dump | 16 | 1 | 2 | inspector fm_dump_tree of the Loans tile, c2 session 2026-11-13 (Small + Larger text): the M0 spike's reference |
| tile-medical-centre | 132 | 8 | 104 | capture styles-e1-squad-bindings-20261114-115217.ndjson, host MedicalCentre |
| tile-tactics | 186 | 36 | 136 | capture styles-e1-squad-bindings-20261114-115217.ndjson, host Tactics |
| tile-training | 130 | 23 | 86 | capture styles-e1-squad-bindings-20261114-115217.ndjson, host Training |
| tiles-large | 3 | 0 | 0 | p7-tile-test (the owner's project, stored placement edits) and the tile-1/tile-2 screenshots: instructions left, pitch right at Small and Large in game. Only the left/right relation is checked: the absolute x of those screenshots (40 and 1274 / 865) was taken on another panel size. |
| tiles-standard | 3 | 0 | 0 | p7-tile-test (the owner's project, stored placement edits) and the tile-1/tile-2 screenshots: instructions left, pitch right at Small and Large in game. Only the left/right relation is checked: the absolute x of those screenshots (40 and 1274 / 865) was taken on another panel size. |

## c3-table-header

| Verdict | Check | Element | Property | Expected | Got | Delta | Note / cause |
|---|---|---|---|---|---|---|---|
| PASS | header-skin | FirstTeamTableAttributesPhysical | header order (skin) | ["position-dropdown", "inf-team", "portrait-name", "attribute-pace", "attribute-acceleration", "attribute-agility", "attribute-balance", "attribute-natural-fitness", "attribute-stamina", "attribute-strength"] | ["position-dropdown", "inf-team", "portrait-name", "attribute-pace", "attribute-acceleration", "attribute-agility", "attribute-balance", "attribute-natural-fitness", "attribute-stamina", "attribute-strength"] |  |  |
| PASS | header-skin | FirstTeamTableAttributesPhysical | column attribute-jumping-reach | "absent" | "absent" |  |  |
| PASS | header-vanilla | FirstTeamTableAttributesPhysical | header order (vanilla) | ["position-dropdown", "inf-team", "portrait-name", "attribute-acceleration", "attribute-agility", "attribute-balance", "attribute-jumping-reach", "attribute-natural-fitness", "attribute-pace", "attribute-stamina", "attribute-strength"] | ["position-dropdown", "inf-team", "portrait-name", "attribute-acceleration", "attribute-agility", "attribute-balance", "attribute-jumping-reach", "attribute-natural-fitness", "attribute-pace", "attribute-stamina", "attribute-strength"] |  |  |

## p6-magenta-reload-skin

| Verdict | Check | Element | Property | Expected | Got | Delta | Note / cause |
|---|---|---|---|---|---|---|---|
| PASS | class-patch-paints-the-button | VisualElement#reload-skin-button | background-color | {"value": "#FF00FF", "origin": "project", "selector": ".p6-loud"} | {"value": "#FF00FF", "origin": "project", "selector": ".p6-loud"} |  |  |
| PASS | vanilla-has-no-magenta | VisualElement#reload-skin-button | background-color | "no declaration" | null |  |  |

## phase3-red-pitch

| Verdict | Check | Element | Property | Expected | Got | Delta | Note / cause |
|---|---|---|---|---|---|---|---|
| PASS | project-rule-wins | VisualElement# | background-color | {"value": "#6C001C", "origin": "project", "selector": ".tactics-collapsable-pitch-container.tactics-collapsable-pitch-container"} | {"value": "#6C001C", "origin": "project", "selector": ".tactics-collapsable-pitch-container.tactics-collapsable-pitch-container", "order": [["vanilla", ".tactics-collapsable-pitch-container"], ["project", ".tactics-collapsable-pitch-container.tactics-collapsable-pitch-container"]]} |  |  |
| PASS | vanilla-is-the-games-colour | VisualElement# | background-color | {"value": "#036150", "origin": "vanilla", "selector": ".tactics-collapsable-pitch-container"} | {"value": "#036150", "origin": "vanilla", "selector": ".tactics-collapsable-pitch-container"} |  |  |

## screen-squad-large-1600

| Verdict | Check | Element | Property | Expected | Got | Delta | Note / cause |
|---|---|---|---|---|---|---|---|
| PASS | hosts | Atmosphere | box | [1750.4, 761.7, 311.9, 147.8] | [1750.3, 761.1, 312, 148] | [-0.1, -0.6, 0.1, 0.2] |  |
| PASS | hosts | Tactics | box | [1750.4, 105.3, 311.9, 311.9] | [1750.3, 105.1, 312, 312] | [-0.1, -0.2, 0.1, 0.1] |  |
| PASS | hosts | Training | box | [1750.4, 433.5, 311.9, 311.9] | [1750.3, 433.1, 312, 312] | [-0.1, -0.4, 0.1, 0.1] |  |
| PASS | hosts | HumanActionsControlPanelBlock | box | [27.8, 105.3, 1706.3, 66.1] | [28.3, 105.1, 1706, 66] | [0.5, -0.2, -0.3, -0.1] |  |
| PASS | hosts | FirstTeamOverview | box | [27.8, 187, 1706.3, 968.3] | [28.3, 187.1, 1706, 968] | [0.5, 0.1, -0.3, -0.3] |  |

## screen-squad-large-1680

| Verdict | Check | Element | Property | Expected | Got | Delta | Note / cause |
|---|---|---|---|---|---|---|---|
| PASS | hosts | Atmosphere | box | [1340.1, 769.1, 311.7, 147.7] | [1339.8, 769.1, 312, 148] | [-0.3, 0.0, 0.3, 0.3] |  |
| PASS | hosts | Tactics | box | [1340.1, 112.9, 311.7, 312.4] | [1339.8, 113.1, 312, 312] | [-0.3, 0.2, 0.3, -0.4] |  |
| PASS | hosts | Training | box | [1340.1, 441, 311.7, 311.7] | [1339.8, 441.1, 312, 312] | [-0.3, 0.1, 0.3, 0.3] |  |
| PASS | hosts | HumanActionsControlPanelBlock | box | [28.2, 112.9, 1296.1, 66.3] | [27.8, 113.1, 1296, 66] | [-0.4, 0.2, -0.1, -0.3] |  |
| PASS | hosts | FirstTeamOverview | box | [28.2, 194.9, 1296.1, 721.9] | [27.8, 195.1, 1296, 722] | [-0.4, 0.2, -0.1, 0.1] |  |

## screen-squad-large-2500

| Verdict | Check | Element | Property | Expected | Got | Delta | Note / cause |
|---|---|---|---|---|---|---|---|
| PASS | hosts | Atmosphere | box | [2160.2, 753.9, 311.5, 147.5] | [2159.6, 753.9, 312, 148] | [-0.6, 0.0, 0.5, 0.5] |  |
| PASS | hosts | Tactics | box | [2160.2, 97.7, 311.5, 311.5] | [2159.6, 97.9, 312, 312] | [-0.6, 0.2, 0.5, 0.5] |  |
| PASS | hosts | Training | box | [2160.2, 425.8, 311.5, 311.5] | [2159.6, 425.9, 312, 312] | [-0.6, 0.1, 0.5, 0.5] |  |
| PASS | hosts | HumanActionsControlPanelBlock | box | [28.3, 97.7, 2115.2, 66.4] | [27.6, 97.9, 2116, 66] | [-0.7, 0.2, 0.8, -0.4] |  |
| PASS | hosts | FirstTeamOverview | box | [28.3, 179.7, 2115.2, 1213.9] | [27.6, 179.9, 2116, 1214] | [-0.7, 0.2, 0.8, 0.1] |  |

## screen-squad-small

| Verdict | Check | Element | Property | Expected | Got | Delta | Note / cause |
|---|---|---|---|---|---|---|---|
| PASS | hosts | Training | box | [356.4, 598.2, 312, 148.4] | [356, 598.2, 312, 148] | [-0.4, 0.0, 0, -0.4] |  |
| PASS | hosts | Atmosphere | box | [684.4, 598.2, 312, 148.4] | [684, 598.2, 312, 148] | [-0.4, 0.0, 0, -0.4] |  |
| PASS | hosts | Tactics | box | [28.4, 598.2, 312, 148.4] | [28, 598.2, 312, 148] | [-0.4, 0.0, 0, -0.4] |  |
| PASS | hosts | HumanActionsControlPanelBlock | box | [28.4, 106.7, 968, 65.8] | [28, 106.2, 968, 66] | [-0.4, -0.5, 0, 0.2] |  |
| PASS | hosts | FirstTeamOverview | box | [28.4, 188.4, 968, 393.8] | [28, 188.2, 968, 394] | [-0.4, -0.2, 0, 0.2] |  |

## screen-squad-standard

| Verdict | Check | Element | Property | Expected | Got | Delta | Note / cause |
|---|---|---|---|---|---|---|---|
| PASS | hosts | Training | box | [1019.4, 434.6, 311.6, 148.6] | [1019.1, 434.8, 312, 148] | [-0.3, 0.2, 0.4, -0.6] |  |
| PASS | hosts | Atmosphere | box | [1019.4, 598.5, 311.6, 148.6] | [1019.1, 598.8, 312, 148] | [-0.3, 0.3, 0.4, -0.6] |  |
| PASS | hosts | Tactics | box | [1019.4, 106.7, 311.6, 311.6] | [1019.1, 106.8, 312, 312] | [-0.3, 0.1, 0.4, 0.4] |  |
| PASS | hosts | HumanActionsControlPanelBlock | box | [35, 106.7, 968.2, 65.7] | [35.1, 106.8, 968, 66] | [0.1, 0.1, -0.2, 0.3] |  |
| PASS | hosts | FirstTeamOverview | box | [35, 188.7, 968.2, 558.4] | [35.1, 188.8, 968, 558] | [0.1, 0.1, -0.2, -0.4] |  |

## screen-team-instructions-large

| Verdict | Check | Element | Property | Expected | Got | Delta | Note / cause |
|---|---|---|---|---|---|---|---|
| PASS | hosts | TeamInstructionsPitch | box | [28.3, 194.3, 475.6, 1213.9] | [28.3, 194.3, 476, 1214] | [0.0, 0.0, 0.4, 0.1] |  |
| PASS | hosts | TeamInstructionsBlock | box | [519.5, 194.3, 1214.8, 1213.9] | [520.3, 194.3, 1214, 1214] | [0.8, 0.0, -0.8, 0.1] |  |
| PASS | hosts | PhasesAndTeamInstructions | box | [1750, 194.3, 311.5, 1213.9] | [1750.3, 194.3, 312, 1214] | [0.3, 0.0, 0.5, 0.1] |  |

## tile-atmosphere

Delivered text wired: 2 of 4 text nodes paired by structural path, 1 captured texts unpaired.

| Verdict | Check | Element | Property | Expected | Got | Delta | Note / cause |
|---|---|---|---|---|---|---|---|
| PASS | geometry | BindingExpect#TileBindingExpect | box | [0.0, 0.0, 311.5, 147.5] | [0, 0, 311.5, 147.5] | [0.0, 0.0, 0.0, 0.0] |  |
| PASS | geometry | TutorialAnchorElement# | box | [0.0, 0.0, 311.5, 147.5] | [0, 0, 311.5, 147.5] | [0.0, 0.0, 0.0, 0.0] |  |
| PASS | geometry | TemplateContainer# | box | [0.0, 0.0, 311.5, 147.5] | [0, 0, 311.5, 147.5] | [0.0, 0.0, 0.0, 0.0] |  |
| PASS | geometry | BindingExpect#TileTemplateBindingExpect | box | [0.0, 0.0, 311.5, 147.5] | [0, 0, 311.5, 147.5] | [0.0, 0.0, 0.0, 0.0] |  |
| PASS | geometry | VisualElement#layout-tile-base-container | box | [0.0, 0.0, 311.5, 147.5] | [0, 0, 311.5, 147.5] | [0.0, 0.0, 0.0, 0.0] |  |
| PASS | geometry | BindingVariables#TileVariables | box | [0.0, 0.0, 311.5, 147.5] | [0, 0, 311.5, 147.5] | [0.0, 0.0, 0.0, 0.0] |  |
| PASS | geometry | SIButton#layout-tile-interaction-button | box | [0.0, 0.0, 311.5, 147.5] | [0, 0, 311.5, 147.5] | [0.0, 0.0, 0.0, 0.0] |  |
| PASS | geometry | VisualElement#Tile_Border | box | [0.0, 0.0, 311.5, 147.5] | [0, 0, 311.5, 147.5] | [0.0, 0.0, 0.0, 0.0] |  |
| PASS | geometry | VisualElement#title area frame | box | [0.0, 0.0, 311.5, 34.2] | [0, 0, 311.5, 34] | [0.0, 0.0, 0.0, -0.2] |  |
| PASS | geometry | VisualElement# | box | [11.7, 2.0, 0, 32.2] | [12, 2, 0, 32] | [0.3, 0.0, 0, -0.2] |  |
| PASS | geometry | VisualElement#TitleContainer | box | [11.7, 2.0, 288.1, 32.2] | [12, 2, 287.5, 32] | [0.3, 0.0, -0.6, -0.2] |  |
| FAIL | geometry | AutoScroller# | box | [11.7, 8.8, 288.1, 17.6] | [12, 2, 287.5, 32] | [0.3, -6.8, -0.6, 14.4] | cause (by rule): bound text, scroller or list width: the width depends on the delivered data and the game's font (stand-in font drawn) |
| FAIL | geometry | SIText#title-text | box | [11.7, 8.8, 52.7, 17.6] | [12, 2, 283.5, 16] | [0.3, -6.8, 230.8, -1.6] | cause (by rule): bound text, scroller or list width: the width depends on the delivered data and the game's font (stand-in font drawn) |
| FAIL | geometry | SIVisible# | box | [11.7, 8.8, 0, 0] | [12, 18, 287.5, 16] | [0.3, 9.2, 287.5, 16] | cause (by rule): bound text, scroller or list width: the width depends on the delivered data and the game's font (stand-in font drawn) |
| N/A | geometry | SIText#title-text-alt | box | null | [12, 18, 287.5, 16] |  | no live element paired (not on screen, or not reached by the capture) |
| PASS | geometry | VisualElement#CarouselMask | box | [303.7, 2.0, 0, 32.2] | [303.5, 2, 0, 32] | [-0.2, 0.0, 0, -0.2] |  |
| PASS | geometry | TemplateContainer#states-templates-tile-content | box | [0.0, 34.2, 311.5, 113.3] | [0, 34, 311.5, 113.5] | [0.0, -0.2, 0.0, 0.2] |  |
| PASS | geometry | VisualElement#Frame | box | [11.7, 34.2, 288.1, 105.5] | [12, 34, 287.5, 105.5] | [0.3, -0.2, -0.6, 0.0] |  |
| PASS | geometry | SIText#state_text | box | [11.7, 34.2, 288.1, 24.4] | [12, 34, 287.5, 24.4] | [0.3, -0.2, -0.6, 0.0] |  |
| PASS | geometry | SIText#description | box | [11.7, 66.4, 288.1, 73.2] | [12, 66.4, 287.5, 73.1] | [0.3, 0.0, -0.6, -0.1] |  |
| N/A | values | BindingExpect#TileBindingExpect | color | "#EBEBEB" | null |  | the render declares no color here |
| N/A | values | BindingExpect#TileBindingExpect | background-color | "#00000000" | null |  | the render declares no background-color here |
| N/A | values | BindingExpect#TileBindingExpect | font-size | 14 | null |  | the render declares no font-size here |
| PASS | values | BindingExpect#TileBindingExpect | flex-grow | 0 | "0" |  |  |
| PASS | values | BindingExpect#TileBindingExpect | flex-shrink | 1 | "1" |  |  |
| PASS | values | BindingExpect#TileBindingExpect | flex-direction | "Column" | "column" |  |  |
| N/A | values | TutorialAnchorElement# | color | "#EBEBEB" | null |  | the render declares no color here |
| N/A | values | TutorialAnchorElement# | background-color | "#00000000" | null |  | the render declares no background-color here |
| N/A | values | TutorialAnchorElement# | font-size | 14 | null |  | the render declares no font-size here |
| PASS | values | TutorialAnchorElement# | flex-grow | 0 | "0" |  |  |
| PASS | values | TutorialAnchorElement# | flex-shrink | 1 | "1" |  |  |
| PASS | values | TutorialAnchorElement# | flex-direction | "Column" | "column" |  |  |
| N/A | values | TemplateContainer# | color | "#EBEBEB" | null |  | the render declares no color here |
| N/A | values | TemplateContainer# | background-color | "#00000000" | null |  | the render declares no background-color here |
| N/A | values | TemplateContainer# | font-size | 14 | null |  | the render declares no font-size here |
| PASS | values | TemplateContainer# | flex-grow | 0 | "0" |  |  |
| PASS | values | TemplateContainer# | flex-shrink | 1 | "1" |  |  |
| PASS | values | TemplateContainer# | flex-direction | "Column" | "column" |  |  |
| N/A | values | BindingExpect#TileTemplateBindingExpect | color | "#EBEBEB" | null |  | the render declares no color here |
| N/A | values | BindingExpect#TileTemplateBindingExpect | background-color | "#00000000" | null |  | the render declares no background-color here |
| N/A | values | BindingExpect#TileTemplateBindingExpect | font-size | 14 | null |  | the render declares no font-size here |
| PASS | values | BindingExpect#TileTemplateBindingExpect | flex-grow | 1 | "1" |  |  |
| PASS | values | BindingExpect#TileTemplateBindingExpect | flex-shrink | 1 | "1" |  |  |
| PASS | values | BindingExpect#TileTemplateBindingExpect | flex-direction | "Column" | "column" |  |  |
| N/A | values | VisualElement#layout-tile-base-container | color | "#EBEBEB" | null |  | the render declares no color here |
| N/A | values | VisualElement#layout-tile-base-container | background-color | "#00000000" | null |  | the render declares no background-color here |
| N/A | values | VisualElement#layout-tile-base-container | font-size | 14 | null |  | the render declares no font-size here |
| PASS | values | VisualElement#layout-tile-base-container | flex-grow | 0 | "0" |  |  |
| PASS | values | VisualElement#layout-tile-base-container | flex-shrink | 0 | "0" |  |  |
| PASS | values | VisualElement#layout-tile-base-container | flex-direction | "Column" | "column" |  |  |
| N/A | values | BindingVariables#TileVariables | color | "#EBEBEB" | null |  | the render declares no color here |
| N/A | values | BindingVariables#TileVariables | background-color | "#00000000" | null |  | the render declares no background-color here |
| N/A | values | BindingVariables#TileVariables | font-size | 14 | null |  | the render declares no font-size here |
| PASS | values | BindingVariables#TileVariables | flex-grow | 1 | "1" |  |  |
| PASS | values | BindingVariables#TileVariables | flex-shrink | 1 | "1" |  |  |
| PASS | values | BindingVariables#TileVariables | flex-direction | "Column" | "column" |  |  |
| N/A | values | SIButton#layout-tile-interaction-button | color | "#EBEBEB" | null |  | the render declares no color here |
| FAIL | values | SIButton#layout-tile-interaction-button | background-color | "#17223F" | "#1E2129" |  | cause (by rule): run-time club-colour sheet (an empty-named root sheet, not applied): the game paints this from the club's colours |
| N/A | values | SIButton#layout-tile-interaction-button | font-size | 14 | null |  | the render declares no font-size here |
| PASS | values | SIButton#layout-tile-interaction-button | flex-grow | 0 | "0" |  |  |
| PASS | values | SIButton#layout-tile-interaction-button | flex-shrink | 0 | "0" |  |  |
| PASS | values | SIButton#layout-tile-interaction-button | flex-direction | "Column" | "column" |  |  |
| N/A | values | VisualElement#Tile_Border | color | "#EBEBEB" | null |  | the render declares no color here |
| N/A | values | VisualElement#Tile_Border | background-color | "#00000000" | null |  | the render declares no background-color here |
| N/A | values | VisualElement#Tile_Border | font-size | 14 | null |  | the render declares no font-size here |
| PASS | values | VisualElement#Tile_Border | flex-grow | 1 | "1" |  |  |
| PASS | values | VisualElement#Tile_Border | flex-shrink | 1 | "1" |  |  |
| PASS | values | VisualElement#Tile_Border | flex-direction | "Column" | "column" |  |  |
| N/A | values | VisualElement#title area frame | color | "#EBEBEB" | null |  | the render declares no color here |
| N/A | values | VisualElement#title area frame | background-color | "#00000000" | null |  | the render declares no background-color here |
| N/A | values | VisualElement#title area frame | font-size | 14 | null |  | the render declares no font-size here |
| PASS | values | VisualElement#title area frame | flex-grow | 0 | "0" |  |  |
| PASS | values | VisualElement#title area frame | flex-shrink | 1 | "1" |  |  |
| PASS | values | VisualElement#title area frame | flex-direction | "Row" | "row" |  |  |
| N/A | values | VisualElement# | color | "#EBEBEB" | null |  | the render declares no color here |
| N/A | values | VisualElement# | background-color | "#00000000" | null |  | the render declares no background-color here |
| N/A | values | VisualElement# | font-size | 14 | null |  | the render declares no font-size here |
| PASS | values | VisualElement# | flex-grow | 0 | "0" |  |  |
| PASS | values | VisualElement# | flex-shrink | 1 | "1" |  |  |
| PASS | values | VisualElement# | flex-direction | "Column" | "column" |  |  |
| N/A | values | VisualElement#TitleContainer | color | "#EBEBEB" | null |  | the render declares no color here |
| N/A | values | VisualElement#TitleContainer | background-color | "#00000000" | null |  | the render declares no background-color here |
| N/A | values | VisualElement#TitleContainer | font-size | 14 | null |  | the render declares no font-size here |
| PASS | values | VisualElement#TitleContainer | flex-grow | 1 | "1" |  |  |
| PASS | values | VisualElement#TitleContainer | flex-shrink | 0 | "0" |  |  |
| PASS | values | VisualElement#TitleContainer | flex-direction | "Column" | "column" |  |  |
| N/A | values | AutoScroller# | color | "#EBEBEB" | null |  | the render declares no color here |
| N/A | values | AutoScroller# | background-color | "#00000000" | null |  | the render declares no background-color here |
| N/A | values | AutoScroller# | font-size | 14 | null |  | the render declares no font-size here |
| PASS | values | AutoScroller# | flex-grow | 0 | "0" |  |  |
| PASS | values | AutoScroller# | flex-shrink | 1 | "1" |  |  |
| PASS | values | AutoScroller# | flex-direction | "Column" | "column" |  |  |
| PASS | values | SIText#title-text | color | "#FAFAFA" | "#FAFAFA" |  |  |
| N/A | values | SIText#title-text | background-color | "#00000000" | null |  | the render declares no background-color here |
| PASS | values | SIText#title-text | font-size | 14 | "14px" |  |  |
| PASS | values | SIText#title-text | flex-grow | 0 | "0" |  |  |
| PASS | values | SIText#title-text | flex-shrink | 1 | "1" |  |  |
| PASS | values | SIText#title-text | flex-direction | "Column" | "column" |  |  |
| N/A | values | SIVisible# | color | "#EBEBEB" | null |  | the render declares no color here |
| N/A | values | SIVisible# | background-color | "#00000000" | null |  | the render declares no background-color here |
| N/A | values | SIVisible# | font-size | 14 | null |  | the render declares no font-size here |
| PASS | values | SIVisible# | flex-grow | 0 | "0" |  |  |
| PASS | values | SIVisible# | flex-shrink | 1 | "1" |  |  |
| PASS | values | SIVisible# | flex-direction | "Column" | "column" |  |  |
| N/A | values | VisualElement#CarouselMask | color | "#EBEBEB" | null |  | the render declares no color here |
| N/A | values | VisualElement#CarouselMask | background-color | "#00000000" | null |  | the render declares no background-color here |
| N/A | values | VisualElement#CarouselMask | font-size | 14 | null |  | the render declares no font-size here |
| PASS | values | VisualElement#CarouselMask | flex-grow | 0 | "0" |  |  |
| PASS | values | VisualElement#CarouselMask | flex-shrink | 1 | "1" |  |  |
| PASS | values | VisualElement#CarouselMask | flex-direction | "Column" | "column" |  |  |
| N/A | values | TemplateContainer#states-templates-tile-content | color | "#EBEBEB" | null |  | the render declares no color here |
| N/A | values | TemplateContainer#states-templates-tile-content | background-color | "#00000000" | null |  | the render declares no background-color here |
| N/A | values | TemplateContainer#states-templates-tile-content | font-size | 14 | null |  | the render declares no font-size here |
| PASS | values | TemplateContainer#states-templates-tile-content | flex-grow | 1 | "1" |  |  |
| PASS | values | TemplateContainer#states-templates-tile-content | flex-shrink | 1 | "1" |  |  |
| PASS | values | TemplateContainer#states-templates-tile-content | flex-direction | "Row" | "row" |  |  |
| N/A | values | VisualElement#Frame | color | "#EBEBEB" | null |  | the render declares no color here |
| N/A | values | VisualElement#Frame | background-color | "#00000000" | null |  | the render declares no background-color here |
| N/A | values | VisualElement#Frame | font-size | 14 | null |  | the render declares no font-size here |
| PASS | values | VisualElement#Frame | flex-grow | 1 | "1" |  |  |
| PASS | values | VisualElement#Frame | flex-shrink | 0 | "0" |  |  |
| PASS | values | VisualElement#Frame | flex-direction | "Column" | "column" |  |  |
| FAIL | values | SIText#state_text | color | "#4EEB3D" | "#EBEBEB" |  | cause (by rule): code-built or binding-driven colour (not in any style sheet) |
| N/A | values | SIText#state_text | background-color | "#00000000" | null |  | the render declares no background-color here |
| PASS | values | SIText#state_text | font-size | 16 | "16px" |  |  |
| PASS | values | SIText#state_text | flex-grow | 0 | "0" |  |  |
| PASS | values | SIText#state_text | flex-shrink | 1 | "1" |  |  |
| PASS | values | SIText#state_text | flex-direction | "Column" | "column" |  |  |
| PASS | values | SIText#description | color | "#B7B7B9" | "#B7B7B9" |  |  |
| N/A | values | SIText#description | background-color | "#00000000" | null |  | the render declares no background-color here |
| PASS | values | SIText#description | font-size | 14 | "14px" |  |  |
| PASS | values | SIText#description | flex-grow | 1 | "1" |  |  |
| PASS | values | SIText#description | flex-shrink | 1 | "1" |  |  |
| PASS | values | SIText#description | flex-direction | "Column" | "column" |  |  |

## tile-loans

Delivered text wired: 1 of 2 text nodes paired by structural path, 13 captured texts unpaired.

| Verdict | Check | Element | Property | Expected | Got | Delta | Note / cause |
|---|---|---|---|---|---|---|---|
| PASS | geometry | BindingExpect#TileBindingExpect | box | [0.0, 0.0, 311.5, 147.5] | [0, 0, 311.5, 147.5] | [0.0, 0.0, 0.0, 0.0] |  |
| PASS | geometry | ComponentElement# | box | [0.0, 0.0, 311.5, 147.5] | [0, 0, 311.5, 147.5] | [0.0, 0.0, 0.0, 0.0] |  |
| PASS | geometry | TemplateContainer#tile-wide-4x2 | box | [0.0, 0.0, 311.5, 147.5] | [0, 0, 311.5, 147.5] | [0.0, 0.0, 0.0, 0.0] |  |
| PASS | geometry | BindingExpect#TileTemplateBindingExpect | box | [0.0, 0.0, 311.5, 147.5] | [0, 0, 311.5, 147.5] | [0.0, 0.0, 0.0, 0.0] |  |
| PASS | geometry | VisualElement#layout-tile-base-container | box | [0.0, 0.0, 311.5, 147.5] | [0, 0, 311.5, 147.5] | [0.0, 0.0, 0.0, 0.0] |  |
| PASS | geometry | BindingVariables#TileVariables | box | [0.0, 0.0, 311.5, 147.5] | [0, 0, 311.5, 147.5] | [0.0, 0.0, 0.0, 0.0] |  |
| PASS | geometry | SIStyleSetter#BackgroundStyleSetter | box | [0.0, 0.0, 311.5, 147.5] | [0, 0, 311.5, 147.5] | [0.0, 0.0, 0.0, 0.0] |  |
| PASS | geometry | SIButton#layout-tile-interaction-button | box | [0.0, 0.0, 311.5, 147.5] | [0, 0, 311.5, 147.5] | [0.0, 0.0, 0.0, 0.0] |  |
| PASS | geometry | VisualElement#Border_TIle | box | [0.0, 0.0, 311.5, 147.5] | [0, 0, 311.5, 147.5] | [0.0, 0.0, 0.0, 0.0] |  |
| PASS | geometry | VisualElement#title area frame | box | [0.0, 0.0, 311.5, 33.2] | [0, 0, 311.5, 34] | [0.0, 0.0, 0.0, 0.8] |  |
| PASS | geometry | VisualElement# | box | [11.7, 1.9, 0, 31.2] | [12, 2, 0, 32] | [0.3, 0.1, 0, 0.8] |  |
| FAIL | geometry | AutoScroller#auto-scroller | box | [11.7, 1.9, 32.2, 31.2] | [12, 2, 38.1, 32] | [0.3, 0.1, 5.9, 0.8] | cause (by rule): bound text, scroller or list width: the width depends on the delivered data and the game's font (stand-in font drawn) |
| FAIL | geometry | SIText#title-text | box | [11.7, 1.9, 32.2, 31.2] | [12, 2, 38.1, 21.5] | [0.3, 0.1, 5.9, -9.7] | cause (by rule): bound text, scroller or list width: the width depends on the delivered data and the game's font (stand-in font drawn) |
| PASS | geometry | TemplateContainer#states-templates-tile-content | box | [0.0, 33.2, 311.5, 114.3] | [0, 34, 311.5, 113.5] | [0.0, 0.8, 0.0, -0.8] |  |
| PASS | geometry | VisualElement# | box | [11.7, 33.2, 288.1, 106.4] | [12, 34, 287.5, 105.5] | [0.3, 0.8, -0.6, -0.9] |  |
| PASS | geometry | VisualElement#Frame_1000002538 | box | [11.7, 33.2, 288.1, 106.4] | [12, 34, 287.5, 105.5] | [0.3, 0.8, -0.6, -0.9] |  |
| PASS | geometry | VisualElement#Frame_1000003021 | box | [11.7, 33.2, 288.1, 24.4] | [12, 34, 287.5, 24.4] | [0.3, 0.8, -0.6, 0.0] |  |
| FAIL | geometry | SIText#title-text | box | [11.7, 33.2, 82, 24.4] | [12, 34, 70.3, 24.4] | [0.3, 0.8, -11.7, 0.0] | cause (by rule): bound text, scroller or list width: the width depends on the delivered data and the game's font (stand-in font drawn) |
| PASS | geometry | StreamedTable# | box | [11.7, 57.6, 288.1, 82] | [12, 58.4, 287.5, 81.1] | [0.3, 0.8, -0.6, -0.9] |  |
| N/A | values | BindingExpect#TileBindingExpect | color | "#EBEBEB" | null |  | the render declares no color here |
| N/A | values | BindingExpect#TileBindingExpect | background-color | "#00000000" | null |  | the render declares no background-color here |
| N/A | values | BindingExpect#TileBindingExpect | font-size | 14 | null |  | the render declares no font-size here |
| PASS | values | BindingExpect#TileBindingExpect | flex-grow | 0 | "0" |  |  |
| PASS | values | BindingExpect#TileBindingExpect | flex-shrink | 1 | "1" |  |  |
| PASS | values | BindingExpect#TileBindingExpect | flex-direction | "Column" | "column" |  |  |
| N/A | values | ComponentElement# | color | "#EBEBEB" | null |  | the render declares no color here |
| N/A | values | ComponentElement# | background-color | "#00000000" | null |  | the render declares no background-color here |
| N/A | values | ComponentElement# | font-size | 14 | null |  | the render declares no font-size here |
| PASS | values | ComponentElement# | flex-grow | 0 | "0" |  |  |
| PASS | values | ComponentElement# | flex-shrink | 1 | "1" |  |  |
| PASS | values | ComponentElement# | flex-direction | "Column" | "column" |  |  |
| N/A | values | TemplateContainer#tile-wide-4x2 | color | "#EBEBEB" | null |  | the render declares no color here |
| N/A | values | TemplateContainer#tile-wide-4x2 | background-color | "#00000000" | null |  | the render declares no background-color here |
| N/A | values | TemplateContainer#tile-wide-4x2 | font-size | 14 | null |  | the render declares no font-size here |
| PASS | values | TemplateContainer#tile-wide-4x2 | flex-grow | 0 | "0" |  |  |
| PASS | values | TemplateContainer#tile-wide-4x2 | flex-shrink | 1 | "1" |  |  |
| PASS | values | TemplateContainer#tile-wide-4x2 | flex-direction | "Column" | "column" |  |  |
| N/A | values | BindingExpect#TileTemplateBindingExpect | color | "#EBEBEB" | null |  | the render declares no color here |
| N/A | values | BindingExpect#TileTemplateBindingExpect | background-color | "#00000000" | null |  | the render declares no background-color here |
| N/A | values | BindingExpect#TileTemplateBindingExpect | font-size | 14 | null |  | the render declares no font-size here |
| PASS | values | BindingExpect#TileTemplateBindingExpect | flex-grow | 1 | "1" |  |  |
| PASS | values | BindingExpect#TileTemplateBindingExpect | flex-shrink | 1 | "1" |  |  |
| PASS | values | BindingExpect#TileTemplateBindingExpect | flex-direction | "Column" | "column" |  |  |
| N/A | values | VisualElement#layout-tile-base-container | color | "#EBEBEB" | null |  | the render declares no color here |
| N/A | values | VisualElement#layout-tile-base-container | background-color | "#00000000" | null |  | the render declares no background-color here |
| N/A | values | VisualElement#layout-tile-base-container | font-size | 14 | null |  | the render declares no font-size here |
| PASS | values | VisualElement#layout-tile-base-container | flex-grow | 0 | "0" |  |  |
| PASS | values | VisualElement#layout-tile-base-container | flex-shrink | 0 | "0" |  |  |
| PASS | values | VisualElement#layout-tile-base-container | flex-direction | "Column" | "column" |  |  |
| N/A | values | BindingVariables#TileVariables | color | "#EBEBEB" | null |  | the render declares no color here |
| N/A | values | BindingVariables#TileVariables | background-color | "#00000000" | null |  | the render declares no background-color here |
| N/A | values | BindingVariables#TileVariables | font-size | 14 | null |  | the render declares no font-size here |
| PASS | values | BindingVariables#TileVariables | flex-grow | 1 | "1" |  |  |
| PASS | values | BindingVariables#TileVariables | flex-shrink | 1 | "1" |  |  |
| PASS | values | BindingVariables#TileVariables | flex-direction | "Column" | "column" |  |  |
| N/A | values | SIStyleSetter#BackgroundStyleSetter | color | "#EBEBEB" | null |  | the render declares no color here |
| N/A | values | SIStyleSetter#BackgroundStyleSetter | background-color | "#00000000" | null |  | the render declares no background-color here |
| N/A | values | SIStyleSetter#BackgroundStyleSetter | font-size | 14 | null |  | the render declares no font-size here |
| PASS | values | SIStyleSetter#BackgroundStyleSetter | flex-grow | 1 | "1" |  |  |
| PASS | values | SIStyleSetter#BackgroundStyleSetter | flex-shrink | 1 | "1" |  |  |
| PASS | values | SIStyleSetter#BackgroundStyleSetter | flex-direction | "Column" | "column" |  |  |
| N/A | values | SIButton#layout-tile-interaction-button | color | "#EBEBEB" | null |  | the render declares no color here |
| FAIL | values | SIButton#layout-tile-interaction-button | background-color | "#2E3138" | "#1E2129" |  | cause (by rule): code-built or binding-driven colour (not in any style sheet) |
| N/A | values | SIButton#layout-tile-interaction-button | font-size | 14 | null |  | the render declares no font-size here |
| PASS | values | SIButton#layout-tile-interaction-button | flex-grow | 0 | "0" |  |  |
| PASS | values | SIButton#layout-tile-interaction-button | flex-shrink | 0 | "0" |  |  |
| PASS | values | SIButton#layout-tile-interaction-button | flex-direction | "Column" | "column" |  |  |
| N/A | values | VisualElement#Border_TIle | color | "#EBEBEB" | null |  | the render declares no color here |
| N/A | values | VisualElement#Border_TIle | background-color | "#00000000" | null |  | the render declares no background-color here |
| N/A | values | VisualElement#Border_TIle | font-size | 14 | null |  | the render declares no font-size here |
| PASS | values | VisualElement#Border_TIle | flex-grow | 0 | "0" |  |  |
| PASS | values | VisualElement#Border_TIle | flex-shrink | 1 | "1" |  |  |
| PASS | values | VisualElement#Border_TIle | flex-direction | "Column" | "column" |  |  |
| N/A | values | VisualElement#title area frame | color | "#EBEBEB" | null |  | the render declares no color here |
| N/A | values | VisualElement#title area frame | background-color | "#00000000" | null |  | the render declares no background-color here |
| N/A | values | VisualElement#title area frame | font-size | 14 | null |  | the render declares no font-size here |
| PASS | values | VisualElement#title area frame | flex-grow | 0 | "0" |  |  |
| PASS | values | VisualElement#title area frame | flex-shrink | 1 | "1" |  |  |
| PASS | values | VisualElement#title area frame | flex-direction | "Row" | "row" |  |  |
| N/A | values | VisualElement# | color | "#EBEBEB" | null |  | the render declares no color here |
| N/A | values | VisualElement# | background-color | "#00000000" | null |  | the render declares no background-color here |
| N/A | values | VisualElement# | font-size | 14 | null |  | the render declares no font-size here |
| PASS | values | VisualElement# | flex-grow | 0 | "0" |  |  |
| PASS | values | VisualElement# | flex-shrink | 1 | "1" |  |  |
| PASS | values | VisualElement# | flex-direction | "Column" | "column" |  |  |
| N/A | values | AutoScroller#auto-scroller | color | "#EBEBEB" | null |  | the render declares no color here |
| N/A | values | AutoScroller#auto-scroller | background-color | "#00000000" | null |  | the render declares no background-color here |
| N/A | values | AutoScroller#auto-scroller | font-size | 14 | null |  | the render declares no font-size here |
| PASS | values | AutoScroller#auto-scroller | flex-grow | 0 | "0" |  |  |
| PASS | values | AutoScroller#auto-scroller | flex-shrink | 1 | "1" |  |  |
| PASS | values | AutoScroller#auto-scroller | flex-direction | "Column" | "column" |  |  |
| PASS | values | SIText#title-text | color | "#FAFAFA" | "#FAFAFA" |  |  |
| N/A | values | SIText#title-text | background-color | "#00000000" | null |  | the render declares no background-color here |
| PASS | values | SIText#title-text | font-size | 14 | "14px" |  |  |
| PASS | values | SIText#title-text | flex-grow | 0 | "0" |  |  |
| PASS | values | SIText#title-text | flex-shrink | 1 | "1" |  |  |
| PASS | values | SIText#title-text | flex-direction | "Column" | "column" |  |  |
| N/A | values | TemplateContainer#states-templates-tile-content | color | "#EBEBEB" | null |  | the render declares no color here |
| N/A | values | TemplateContainer#states-templates-tile-content | background-color | "#00000000" | null |  | the render declares no background-color here |
| N/A | values | TemplateContainer#states-templates-tile-content | font-size | 14 | null |  | the render declares no font-size here |
| PASS | values | TemplateContainer#states-templates-tile-content | flex-grow | 1 | "1" |  |  |
| PASS | values | TemplateContainer#states-templates-tile-content | flex-shrink | 1 | "1" |  |  |
| PASS | values | TemplateContainer#states-templates-tile-content | flex-direction | "Row" | "row" |  |  |
| N/A | values | VisualElement# | color | "#EBEBEB" | null |  | the render declares no color here |
| N/A | values | VisualElement# | background-color | "#00000000" | null |  | the render declares no background-color here |
| N/A | values | VisualElement# | font-size | 14 | null |  | the render declares no font-size here |
| PASS | values | VisualElement# | flex-grow | 1 | "1" |  |  |
| PASS | values | VisualElement# | flex-shrink | 1 | "1" |  |  |
| PASS | values | VisualElement# | flex-direction | "Column" | "column" |  |  |
| N/A | values | VisualElement#Frame_1000002538 | color | "#EBEBEB" | null |  | the render declares no color here |
| N/A | values | VisualElement#Frame_1000002538 | background-color | "#00000000" | null |  | the render declares no background-color here |
| N/A | values | VisualElement#Frame_1000002538 | font-size | 14 | null |  | the render declares no font-size here |
| PASS | values | VisualElement#Frame_1000002538 | flex-grow | 1 | "1" |  |  |
| PASS | values | VisualElement#Frame_1000002538 | flex-shrink | 0 | "0" |  |  |
| PASS | values | VisualElement#Frame_1000002538 | flex-direction | "Column" | "column" |  |  |
| N/A | values | VisualElement#Frame_1000003021 | color | "#EBEBEB" | null |  | the render declares no color here |
| N/A | values | VisualElement#Frame_1000003021 | background-color | "#00000000" | null |  | the render declares no background-color here |
| N/A | values | VisualElement#Frame_1000003021 | font-size | 14 | null |  | the render declares no font-size here |
| PASS | values | VisualElement#Frame_1000003021 | flex-grow | 0 | "0" |  |  |
| PASS | values | VisualElement#Frame_1000003021 | flex-shrink | 1 | "1" |  |  |
| PASS | values | VisualElement#Frame_1000003021 | flex-direction | "Row" | "row" |  |  |
| PASS | values | SIText#title-text | color | "#EBEBEB" | "#EBEBEB" |  |  |
| N/A | values | SIText#title-text | background-color | "#00000000" | null |  | the render declares no background-color here |
| PASS | values | SIText#title-text | font-size | 16 | "16px" |  |  |
| PASS | values | SIText#title-text | flex-grow | 0 | "0" |  |  |
| PASS | values | SIText#title-text | flex-shrink | 1 | "1" |  |  |
| PASS | values | SIText#title-text | flex-direction | "Column" | "column" |  |  |
| N/A | values | StreamedTable# | color | "#EBEBEB" | null |  | the render declares no color here |
| N/A | values | StreamedTable# | background-color | "#00000000" | null |  | the render declares no background-color here |
| N/A | values | StreamedTable# | font-size | 14 | null |  | the render declares no font-size here |
| PASS | values | StreamedTable# | flex-grow | 1 | "1" |  |  |
| PASS | values | StreamedTable# | flex-shrink | 1 | "1" |  |  |
| PASS | values | StreamedTable# | flex-direction | "Column" | "column" |  |  |

## tile-loans-c2-dump

| Verdict | Check | Element | Property | Expected | Got | Delta | Note / cause |
|---|---|---|---|---|---|---|---|
| PASS | geometry | BindingExpect#TileBindingExpect | box | [0.0, 0.0, 311.5, 147.5] | [0, 0, 311.5, 147.5] | [0.0, 0.0, 0.0, 0.0] |  |
| PASS | geometry | ComponentElement# | box | [0.0, 0.0, 311.5, 147.5] | [0, 0, 311.5, 147.5] | [0.0, 0.0, 0.0, 0.0] |  |
| PASS | geometry | TemplateContainer#tile-wide-4x2 | box | [0.0, 0.0, 311.5, 147.5] | [0, 0, 311.5, 147.5] | [0.0, 0.0, 0.0, 0.0] |  |
| PASS | geometry | BindingExpect#TileTemplateBindingExpect | box | [0.0, 0.0, 311.5, 147.5] | [0, 0, 311.5, 147.5] | [0.0, 0.0, 0.0, 0.0] |  |
| PASS | geometry | VisualElement#layout-tile-base-container | box | [0.0, 0.0, 311.5, 147.5] | [0, 0, 311.5, 147.5] | [0.0, 0.0, 0.0, 0.0] |  |
| PASS | geometry | BindingVariables#TileVariables | box | [0.0, 0.0, 311.5, 147.5] | [0, 0, 311.5, 147.5] | [0.0, 0.0, 0.0, 0.0] |  |
| PASS | geometry | SIStyleSetter#BackgroundStyleSetter | box | [0.0, 0.0, 311.5, 147.5] | [0, 0, 311.5, 147.5] | [0.0, 0.0, 0.0, 0.0] |  |
| PASS | geometry | SIButton#layout-tile-interaction-button | box | [0.0, 0.0, 311.5, 147.5] | [0, 0, 311.5, 147.5] | [0.0, 0.0, 0.0, 0.0] |  |
| PASS | geometry | VisualElement#Border_TIle | box | [0.0, 0.0, 311.5, 147.5] | [0, 0, 311.5, 147.5] | [0.0, 0.0, 0.0, 0.0] |  |
| PASS | geometry | VisualElement#title area frame | box | [0.0, 0.0, 311.5, 33.2] | [0, 0, 311.5, 34] | [0.0, 0.0, 0.0, 0.8] |  |
| PASS | geometry | VisualElement# | box | [11.7, 1.9, 0, 31.2] | [12, 2, 0, 32] | [0.3, 0.1, 0, 0.8] |  |
| FAIL | geometry | AutoScroller#auto-scroller | box | [11.7, 1.9, 32.2, 31.2] | [12, 2, 38.1, 32] | [0.3, 0.1, 5.9, 0.8] | cause (by rule): bound text, scroller or list width: the width depends on the delivered data and the game's font (stand-in font drawn) |
| N/A | geometry | SIText#title-text | box | null | [12, 2, 38.1, 21.5] |  | no live element paired (not on screen, or not reached by the capture) |
| PASS | geometry | TemplateContainer#states-templates-tile-content | box | [0.0, 33.2, 311.5, 114.3] | [0, 34, 311.5, 113.5] | [0.0, 0.8, 0.0, -0.8] |  |
| PASS | geometry | VisualElement# | box | [11.7, 33.2, 288.1, 106.4] | [12, 34, 287.5, 105.5] | [0.3, 0.8, -0.6, -0.9] |  |
| PASS | geometry | VisualElement#Frame_1000002538 | box | [11.7, 33.2, 288.1, 106.4] | [12, 34, 287.5, 105.5] | [0.3, 0.8, -0.6, -0.9] |  |
| PASS | geometry | VisualElement#Frame_1000003021 | box | [11.7, 33.2, 288.1, 24.4] | [12, 34, 287.5, 24.4] | [0.3, 0.8, -0.6, 0.0] |  |
| N/A | geometry | SIText#title-text | box | null | [12, 34, 70.3, 24.4] |  | no live element paired (not on screen, or not reached by the capture) |
| PASS | geometry | StreamedTable# | box | [11.7, 57.6, 288.1, 82] | [12, 58.4, 287.5, 81.1] | [0.3, 0.8, -0.6, -0.9] |  |

## tile-medical-centre

Delivered text wired: 2 of 4 text nodes paired by structural path, 5 captured texts unpaired.

| Verdict | Check | Element | Property | Expected | Got | Delta | Note / cause |
|---|---|---|---|---|---|---|---|
| PASS | geometry | BindingExpect#TileBindingExpect | box | [0.0, 0, 311.5, 147.5] | [0, 0, 311.5, 147.5] | [0.0, 0, 0.0, 0.0] |  |
| PASS | geometry | TutorialAnchorElement# | box | [0.0, 0, 311.5, 147.5] | [0, 0, 311.5, 147.5] | [0.0, 0, 0.0, 0.0] |  |
| PASS | geometry | BindingRemapper# | box | [0.0, 0, 311.5, 147.5] | [0, 0, 311.5, 147.5] | [0.0, 0, 0.0, 0.0] |  |
| PASS | geometry | TemplateContainer# | box | [0.0, 0, 311.5, 147.5] | [0, 0, 311.5, 147.5] | [0.0, 0, 0.0, 0.0] |  |
| PASS | geometry | BindingExpect#TileTemplateBindingExpect | box | [0.0, 0, 311.5, 147.5] | [0, 0, 311.5, 147.5] | [0.0, 0, 0.0, 0.0] |  |
| PASS | geometry | VisualElement#layout-tile-base-container | box | [0.0, 0, 311.5, 147.5] | [0, 0, 311.5, 147.5] | [0.0, 0, 0.0, 0.0] |  |
| PASS | geometry | BindingVariables#TileVariables | box | [0.0, 0, 311.5, 147.5] | [0, 0, 311.5, 147.5] | [0.0, 0, 0.0, 0.0] |  |
| PASS | geometry | SIButton#layout-tile-interaction-button | box | [0.0, 0, 311.5, 147.5] | [0, 0, 311.5, 147.5] | [0.0, 0, 0.0, 0.0] |  |
| PASS | geometry | VisualElement#Tile_Border | box | [0.0, 0, 311.5, 147.5] | [0, 0, 311.5, 147.5] | [0.0, 0, 0.0, 0.0] |  |
| PASS | geometry | VisualElement#title area frame | box | [0.0, 0, 311.5, 33.2] | [0, 0, 311.5, 34] | [0.0, 0, 0.0, 0.8] |  |
| PASS | geometry | VisualElement# | box | [11.7, 2, 0, 31.2] | [12, 2, 0, 32] | [0.3, 0, 0, 0.8] |  |
| PASS | geometry | VisualElement#TitleContainer | box | [11.7, 2, 288.1, 31.2] | [12, 2, 287.5, 32] | [0.3, 0, -0.6, 0.8] |  |
| FAIL | geometry | AutoScroller# | box | [11.7, 8.8, 288.1, 17.6] | [12, 2, 287.5, 32] | [0.3, -6.8, -0.6, 14.4] | cause (by rule): bound text, scroller or list width: the width depends on the delivered data and the game's font (stand-in font drawn) |
| FAIL | geometry | SIText#title-text | box | [11.7, 8.8, 85, 17.6] | [12, 2, 283.5, 16] | [0.3, -6.8, 198.5, -1.6] | cause (by rule): bound text, scroller or list width: the width depends on the delivered data and the game's font (stand-in font drawn) |
| FAIL | geometry | SIVisible# | box | [11.7, 8.8, 0, 0] | [12, 18, 287.5, 16] | [0.3, 9.2, 287.5, 16] | cause (by rule): bound text, scroller or list width: the width depends on the delivered data and the game's font (stand-in font drawn) |
| N/A | geometry | SIText#title-text-alt | box | null | [12, 18, 287.5, 16] |  | no live element paired (not on screen, or not reached by the capture) |
| PASS | geometry | VisualElement#CarouselMask | box | [303.7, 2, 0, 31.2] | [303.5, 2, 0, 32] | [-0.2, 0, 0, 0.8] |  |
| PASS | geometry | TemplateContainer#states-templates-tile-content | box | [0.0, 33.2, 311.5, 114.3] | [0, 34, 311.5, 113.5] | [0.0, 0.8, 0.0, -0.8] |  |
| PASS | geometry | VisualElement# | box | [11.7, 33.2, 288.1, 106.4] | [12, 34, 287.5, 105.5] | [0.3, 0.8, -0.6, -0.9] |  |
| PASS | geometry | BindableSwitchElement# | box | [11.7, 33.2, 288.1, 106.4] | [12, 34, 287.5, 105.5] | [0.3, 0.8, -0.6, -0.9] |  |
| N/A | geometry | VisualElement#Frame | box | null | [0, 0, 0, 0] |  | no live element paired (not on screen, or not reached by the capture) |
| N/A | geometry | VisualElement#Frame | box | null | [0, 0, 0, 0] |  | no live element paired (not on screen, or not reached by the capture) |
| N/A | geometry | VisualElement# | box | null | [0, 0, 0, 0] |  | no live element paired (not on screen, or not reached by the capture) |
| N/A | geometry | VisualElement#Frame | box | null | [0, 0, 0, 0] |  | no live element paired (not on screen, or not reached by the capture) |
| N/A | geometry | VisualElement#Frame | box | null | [0, 0, 0, 0] |  | no live element paired (not on screen, or not reached by the capture) |
| N/A | geometry | SIText#text | box | null | [0, 0, 0, 0] |  | no live element paired (not on screen, or not reached by the capture) |
| N/A | geometry | StreamedObjectList# | box | null | [0, 0, 0, 0] |  | no live element paired (not on screen, or not reached by the capture) |
| N/A | geometry | TemplateContainer# | box | null | [0, 0, 0, 0] |  | no live element paired (not on screen, or not reached by the capture) |
| N/A | geometry | VisualElement#layout-divider-solid-horizontal | box | null | [0, 0, 0, 0] |  | no live element paired (not on screen, or not reached by the capture) |
| N/A | geometry | VisualElement#data_display-string-list-item-default-unpacked | box | null | [0, 0, 0, 0] |  | no live element paired (not on screen, or not reached by the capture) |
| N/A | geometry | VisualElement# | box | null | [0, 0, 0, 0] |  | no live element paired (not on screen, or not reached by the capture) |
| N/A | geometry | SIText#text | box | null | [0, 0, 0, 0] |  | no live element paired (not on screen, or not reached by the capture) |
| PASS | geometry | VisualElement# | box | [11.7, 33.2, 288.1, 106.4] | [12, 34, 287.5, 105.5] | [0.3, 0.8, -0.6, -0.9] |  |
| PASS | geometry | VisualElement#Frame | box | [11.7, 33.2, 288.1, 79.1] | [12, 34, 287.5, 77.9] | [0.3, 0.8, -0.6, -1.2] |  |
| PASS | geometry | VisualElement#Frame | box | [11.7, 33.2, 288.1, 79.1] | [12, 34, 287.5, 77.9] | [0.3, 0.8, -0.6, -1.2] |  |
| PASS | geometry | VisualElement#scaling-icons-condition | box | [11.7, 33.2, 23.4, 24.4] | [12, 34, 24, 24] | [0.3, 0.8, 0.6, -0.4] |  |
| PASS | geometry | VisualElement#Frame | box | [39.0, 33.2, 260.7, 79.1] | [40, 34, 259.5, 77.9] | [1.0, 0.8, -1.2, -1.2] |  |
| PASS | geometry | VisualElement#Frame | box | [42.9, 33.2, 256.8, 24.4] | [44, 34, 255.5, 24.4] | [1.1, 0.8, -1.3, 0.0] |  |
| FAIL | geometry | SIText#text | box | [42.9, 33.2, 147.5, 24.4] | [44, 34, 127.2, 24.4] | [1.1, 0.8, -20.3, 0.0] | cause (by rule): bound text, scroller or list width: the width depends on the delivered data and the game's font (stand-in font drawn) |
| PASS | geometry | StreamedObjectList# | box | [39.0, 65.5, 260.7, 46.9] | [40, 66.4, 259.5, 45.5] | [1.0, 0.9, -1.2, -1.4] |  |
| PASS | geometry | VisualElement#Frame | box | [11.7, 112.3, 288.1, 27.3] | [12, 111.9, 287.5, 27.6] | [0.3, -0.4, -0.6, 0.3] |  |
| FAIL | geometry | TemplateContainer#layout-divider-solid-horizontal | box | [11.7, 112.3, 288.1, 1] | [12, 111.9, 287.5, 1] | [0.3, -0.4, -0.6, 0] | cause (by rule): sub-pixel offset on a very small element: the owner's tolerance is 5 percent of the size, 0.05 px for a 1 px divider |
| FAIL | geometry | VisualElement#layout-divider-solid-horizontal | box | [11.7, 112.3, 288.1, 1] | [12, 111.9, 287.5, 1] | [0.3, -0.4, -0.6, 0] | cause (by rule): sub-pixel offset on a very small element: the owner's tolerance is 5 percent of the size, 0.05 px for a 1 px divider |
| PASS | geometry | VisualElement#data_display-string-list-item-default-unpacked | box | [11.7, 121.1, 283.2, 18.6] | [12, 120.9, 283.5, 18.6] | [0.3, -0.2, 0.3, -0.0] |  |
| PASS | geometry | VisualElement# | box | [11.7, 122.1, 15.6, 16.6] | [12, 122.2, 16, 16] | [0.3, 0.1, 0.4, -0.6] |  |
| FAIL | geometry | SIText#text | box | [31.2, 121.1, 143.6, 18.6] | [32, 120.9, 129.4, 18.6] | [0.8, -0.2, -14.2, -0.0] | cause (by rule): bound text, scroller or list width: the width depends on the delivered data and the game's font (stand-in font drawn) |
| N/A | values | BindingExpect#TileBindingExpect | color | "#EBEBEB" | null |  | the render declares no color here |
| N/A | values | BindingExpect#TileBindingExpect | background-color | "#00000000" | null |  | the render declares no background-color here |
| N/A | values | BindingExpect#TileBindingExpect | font-size | 14 | null |  | the render declares no font-size here |
| PASS | values | BindingExpect#TileBindingExpect | flex-grow | 0 | "0" |  |  |
| PASS | values | BindingExpect#TileBindingExpect | flex-shrink | 1 | "1" |  |  |
| PASS | values | BindingExpect#TileBindingExpect | flex-direction | "Column" | "column" |  |  |
| N/A | values | TutorialAnchorElement# | color | "#EBEBEB" | null |  | the render declares no color here |
| N/A | values | TutorialAnchorElement# | background-color | "#00000000" | null |  | the render declares no background-color here |
| N/A | values | TutorialAnchorElement# | font-size | 14 | null |  | the render declares no font-size here |
| PASS | values | TutorialAnchorElement# | flex-grow | 0 | "0" |  |  |
| PASS | values | TutorialAnchorElement# | flex-shrink | 1 | "1" |  |  |
| PASS | values | TutorialAnchorElement# | flex-direction | "Column" | "column" |  |  |
| N/A | values | BindingRemapper# | color | "#EBEBEB" | null |  | the render declares no color here |
| N/A | values | BindingRemapper# | background-color | "#00000000" | null |  | the render declares no background-color here |
| N/A | values | BindingRemapper# | font-size | 14 | null |  | the render declares no font-size here |
| PASS | values | BindingRemapper# | flex-grow | 0 | "0" |  |  |
| PASS | values | BindingRemapper# | flex-shrink | 1 | "1" |  |  |
| PASS | values | BindingRemapper# | flex-direction | "Column" | "column" |  |  |
| N/A | values | TemplateContainer# | color | "#EBEBEB" | null |  | the render declares no color here |
| N/A | values | TemplateContainer# | background-color | "#00000000" | null |  | the render declares no background-color here |
| N/A | values | TemplateContainer# | font-size | 14 | null |  | the render declares no font-size here |
| PASS | values | TemplateContainer# | flex-grow | 0 | "0" |  |  |
| PASS | values | TemplateContainer# | flex-shrink | 1 | "1" |  |  |
| PASS | values | TemplateContainer# | flex-direction | "Column" | "column" |  |  |
| N/A | values | BindingExpect#TileTemplateBindingExpect | color | "#EBEBEB" | null |  | the render declares no color here |
| N/A | values | BindingExpect#TileTemplateBindingExpect | background-color | "#00000000" | null |  | the render declares no background-color here |
| N/A | values | BindingExpect#TileTemplateBindingExpect | font-size | 14 | null |  | the render declares no font-size here |
| PASS | values | BindingExpect#TileTemplateBindingExpect | flex-grow | 1 | "1" |  |  |
| PASS | values | BindingExpect#TileTemplateBindingExpect | flex-shrink | 1 | "1" |  |  |
| PASS | values | BindingExpect#TileTemplateBindingExpect | flex-direction | "Column" | "column" |  |  |
| N/A | values | VisualElement#layout-tile-base-container | color | "#EBEBEB" | null |  | the render declares no color here |
| N/A | values | VisualElement#layout-tile-base-container | background-color | "#00000000" | null |  | the render declares no background-color here |
| N/A | values | VisualElement#layout-tile-base-container | font-size | 14 | null |  | the render declares no font-size here |
| PASS | values | VisualElement#layout-tile-base-container | flex-grow | 0 | "0" |  |  |
| PASS | values | VisualElement#layout-tile-base-container | flex-shrink | 0 | "0" |  |  |
| PASS | values | VisualElement#layout-tile-base-container | flex-direction | "Column" | "column" |  |  |
| N/A | values | BindingVariables#TileVariables | color | "#EBEBEB" | null |  | the render declares no color here |
| N/A | values | BindingVariables#TileVariables | background-color | "#00000000" | null |  | the render declares no background-color here |
| N/A | values | BindingVariables#TileVariables | font-size | 14 | null |  | the render declares no font-size here |
| PASS | values | BindingVariables#TileVariables | flex-grow | 1 | "1" |  |  |
| PASS | values | BindingVariables#TileVariables | flex-shrink | 1 | "1" |  |  |
| PASS | values | BindingVariables#TileVariables | flex-direction | "Column" | "column" |  |  |
| N/A | values | SIButton#layout-tile-interaction-button | color | "#EBEBEB" | null |  | the render declares no color here |
| FAIL | values | SIButton#layout-tile-interaction-button | background-color | "#17223F" | "#1E2129" |  | cause (by rule): run-time club-colour sheet (an empty-named root sheet, not applied): the game paints this from the club's colours |
| N/A | values | SIButton#layout-tile-interaction-button | font-size | 14 | null |  | the render declares no font-size here |
| PASS | values | SIButton#layout-tile-interaction-button | flex-grow | 0 | "0" |  |  |
| PASS | values | SIButton#layout-tile-interaction-button | flex-shrink | 0 | "0" |  |  |
| PASS | values | SIButton#layout-tile-interaction-button | flex-direction | "Column" | "column" |  |  |
| N/A | values | VisualElement#Tile_Border | color | "#EBEBEB" | null |  | the render declares no color here |
| N/A | values | VisualElement#Tile_Border | background-color | "#00000000" | null |  | the render declares no background-color here |
| N/A | values | VisualElement#Tile_Border | font-size | 14 | null |  | the render declares no font-size here |
| PASS | values | VisualElement#Tile_Border | flex-grow | 1 | "1" |  |  |
| PASS | values | VisualElement#Tile_Border | flex-shrink | 1 | "1" |  |  |
| PASS | values | VisualElement#Tile_Border | flex-direction | "Column" | "column" |  |  |
| N/A | values | VisualElement#title area frame | color | "#EBEBEB" | null |  | the render declares no color here |
| N/A | values | VisualElement#title area frame | background-color | "#00000000" | null |  | the render declares no background-color here |
| N/A | values | VisualElement#title area frame | font-size | 14 | null |  | the render declares no font-size here |
| PASS | values | VisualElement#title area frame | flex-grow | 0 | "0" |  |  |
| PASS | values | VisualElement#title area frame | flex-shrink | 1 | "1" |  |  |
| PASS | values | VisualElement#title area frame | flex-direction | "Row" | "row" |  |  |
| N/A | values | VisualElement# | color | "#EBEBEB" | null |  | the render declares no color here |
| N/A | values | VisualElement# | background-color | "#00000000" | null |  | the render declares no background-color here |
| N/A | values | VisualElement# | font-size | 14 | null |  | the render declares no font-size here |
| PASS | values | VisualElement# | flex-grow | 0 | "0" |  |  |
| PASS | values | VisualElement# | flex-shrink | 1 | "1" |  |  |
| PASS | values | VisualElement# | flex-direction | "Column" | "column" |  |  |
| N/A | values | VisualElement#TitleContainer | color | "#EBEBEB" | null |  | the render declares no color here |
| N/A | values | VisualElement#TitleContainer | background-color | "#00000000" | null |  | the render declares no background-color here |
| N/A | values | VisualElement#TitleContainer | font-size | 14 | null |  | the render declares no font-size here |
| PASS | values | VisualElement#TitleContainer | flex-grow | 1 | "1" |  |  |
| PASS | values | VisualElement#TitleContainer | flex-shrink | 0 | "0" |  |  |
| PASS | values | VisualElement#TitleContainer | flex-direction | "Column" | "column" |  |  |
| N/A | values | AutoScroller# | color | "#EBEBEB" | null |  | the render declares no color here |
| N/A | values | AutoScroller# | background-color | "#00000000" | null |  | the render declares no background-color here |
| N/A | values | AutoScroller# | font-size | 14 | null |  | the render declares no font-size here |
| PASS | values | AutoScroller# | flex-grow | 0 | "0" |  |  |
| PASS | values | AutoScroller# | flex-shrink | 1 | "1" |  |  |
| PASS | values | AutoScroller# | flex-direction | "Column" | "column" |  |  |
| PASS | values | SIText#title-text | color | "#FAFAFA" | "#FAFAFA" |  |  |
| N/A | values | SIText#title-text | background-color | "#00000000" | null |  | the render declares no background-color here |
| PASS | values | SIText#title-text | font-size | 14 | "14px" |  |  |
| PASS | values | SIText#title-text | flex-grow | 0 | "0" |  |  |
| PASS | values | SIText#title-text | flex-shrink | 1 | "1" |  |  |
| PASS | values | SIText#title-text | flex-direction | "Column" | "column" |  |  |
| N/A | values | SIVisible# | color | "#EBEBEB" | null |  | the render declares no color here |
| N/A | values | SIVisible# | background-color | "#00000000" | null |  | the render declares no background-color here |
| N/A | values | SIVisible# | font-size | 14 | null |  | the render declares no font-size here |
| PASS | values | SIVisible# | flex-grow | 0 | "0" |  |  |
| PASS | values | SIVisible# | flex-shrink | 1 | "1" |  |  |
| PASS | values | SIVisible# | flex-direction | "Column" | "column" |  |  |
| N/A | values | VisualElement#CarouselMask | color | "#EBEBEB" | null |  | the render declares no color here |
| N/A | values | VisualElement#CarouselMask | background-color | "#00000000" | null |  | the render declares no background-color here |
| N/A | values | VisualElement#CarouselMask | font-size | 14 | null |  | the render declares no font-size here |
| PASS | values | VisualElement#CarouselMask | flex-grow | 0 | "0" |  |  |
| PASS | values | VisualElement#CarouselMask | flex-shrink | 1 | "1" |  |  |
| PASS | values | VisualElement#CarouselMask | flex-direction | "Column" | "column" |  |  |
| N/A | values | TemplateContainer#states-templates-tile-content | color | "#EBEBEB" | null |  | the render declares no color here |
| N/A | values | TemplateContainer#states-templates-tile-content | background-color | "#00000000" | null |  | the render declares no background-color here |
| N/A | values | TemplateContainer#states-templates-tile-content | font-size | 14 | null |  | the render declares no font-size here |
| PASS | values | TemplateContainer#states-templates-tile-content | flex-grow | 1 | "1" |  |  |
| PASS | values | TemplateContainer#states-templates-tile-content | flex-shrink | 1 | "1" |  |  |
| PASS | values | TemplateContainer#states-templates-tile-content | flex-direction | "Row" | "row" |  |  |
| N/A | values | VisualElement# | color | "#EBEBEB" | null |  | the render declares no color here |
| N/A | values | VisualElement# | background-color | "#00000000" | null |  | the render declares no background-color here |
| N/A | values | VisualElement# | font-size | 14 | null |  | the render declares no font-size here |
| PASS | values | VisualElement# | flex-grow | 1 | "1" |  |  |
| PASS | values | VisualElement# | flex-shrink | 1 | "1" |  |  |
| PASS | values | VisualElement# | flex-direction | "Column" | "column" |  |  |
| N/A | values | BindableSwitchElement# | color | "#EBEBEB" | null |  | the render declares no color here |
| N/A | values | BindableSwitchElement# | background-color | "#00000000" | null |  | the render declares no background-color here |
| N/A | values | BindableSwitchElement# | font-size | 14 | null |  | the render declares no font-size here |
| PASS | values | BindableSwitchElement# | flex-grow | 1 | "1" |  |  |
| PASS | values | BindableSwitchElement# | flex-shrink | 1 | "1" |  |  |
| PASS | values | BindableSwitchElement# | flex-direction | "Column" | "column" |  |  |
| N/A | values | VisualElement# | color | "#EBEBEB" | null |  | the render declares no color here |
| N/A | values | VisualElement# | background-color | "#00000000" | null |  | the render declares no background-color here |
| N/A | values | VisualElement# | font-size | 14 | null |  | the render declares no font-size here |
| PASS | values | VisualElement# | flex-grow | 1 | "1" |  |  |
| PASS | values | VisualElement# | flex-shrink | 1 | "1" |  |  |
| PASS | values | VisualElement# | flex-direction | "Column" | "column" |  |  |
| N/A | values | VisualElement#Frame | color | "#EBEBEB" | null |  | the render declares no color here |
| N/A | values | VisualElement#Frame | background-color | "#00000000" | null |  | the render declares no background-color here |
| N/A | values | VisualElement#Frame | font-size | 14 | null |  | the render declares no font-size here |
| PASS | values | VisualElement#Frame | flex-grow | 1 | "1" |  |  |
| PASS | values | VisualElement#Frame | flex-shrink | 0 | "0" |  |  |
| PASS | values | VisualElement#Frame | flex-direction | "Column" | "column" |  |  |
| N/A | values | VisualElement#Frame | color | "#EBEBEB" | null |  | the render declares no color here |
| N/A | values | VisualElement#Frame | background-color | "#00000000" | null |  | the render declares no background-color here |
| N/A | values | VisualElement#Frame | font-size | 14 | null |  | the render declares no font-size here |
| PASS | values | VisualElement#Frame | flex-grow | 1 | "1" |  |  |
| PASS | values | VisualElement#Frame | flex-shrink | 0 | "0" |  |  |
| PASS | values | VisualElement#Frame | flex-direction | "Row" | "row" |  |  |
| N/A | values | VisualElement#scaling-icons-condition | color | "#EBEBEB" | null |  | the render declares no color here |
| N/A | values | VisualElement#scaling-icons-condition | background-color | "#00000000" | null |  | the render declares no background-color here |
| N/A | values | VisualElement#scaling-icons-condition | font-size | 14 | null |  | the render declares no font-size here |
| PASS | values | VisualElement#scaling-icons-condition | flex-grow | 0 | "0" |  |  |
| PASS | values | VisualElement#scaling-icons-condition | flex-shrink | 0 | "0" |  |  |
| PASS | values | VisualElement#scaling-icons-condition | flex-direction | "Column" | "column" |  |  |
| N/A | values | VisualElement#Frame | color | "#EBEBEB" | null |  | the render declares no color here |
| N/A | values | VisualElement#Frame | background-color | "#00000000" | null |  | the render declares no background-color here |
| N/A | values | VisualElement#Frame | font-size | 14 | null |  | the render declares no font-size here |
| PASS | values | VisualElement#Frame | flex-grow | 1 | "1" |  |  |
| PASS | values | VisualElement#Frame | flex-shrink | 0 | "0" |  |  |
| PASS | values | VisualElement#Frame | flex-direction | "Column" | "column" |  |  |
| N/A | values | VisualElement#Frame | color | "#EBEBEB" | null |  | the render declares no color here |
| N/A | values | VisualElement#Frame | background-color | "#00000000" | null |  | the render declares no background-color here |
| N/A | values | VisualElement#Frame | font-size | 14 | null |  | the render declares no font-size here |
| PASS | values | VisualElement#Frame | flex-grow | 0 | "0" |  |  |
| PASS | values | VisualElement#Frame | flex-shrink | 1 | "1" |  |  |
| PASS | values | VisualElement#Frame | flex-direction | "Row" | "row" |  |  |
| PASS | values | SIText#text | color | "#EBEBEB" | "#EBEBEB" |  |  |
| N/A | values | SIText#text | background-color | "#00000000" | null |  | the render declares no background-color here |
| PASS | values | SIText#text | font-size | 16 | "16px" |  |  |
| PASS | values | SIText#text | flex-grow | 0 | "0" |  |  |
| PASS | values | SIText#text | flex-shrink | 1 | "1" |  |  |
| PASS | values | SIText#text | flex-direction | "Column" | "column" |  |  |
| N/A | values | StreamedObjectList# | color | "#EBEBEB" | null |  | the render declares no color here |
| N/A | values | StreamedObjectList# | background-color | "#00000000" | null |  | the render declares no background-color here |
| N/A | values | StreamedObjectList# | font-size | 14 | null |  | the render declares no font-size here |
| PASS | values | StreamedObjectList# | flex-grow | 1 | "1" |  |  |
| PASS | values | StreamedObjectList# | flex-shrink | 1 | "1" |  |  |
| PASS | values | StreamedObjectList# | flex-direction | "Row" | "row" |  |  |
| N/A | values | VisualElement#Frame | color | "#EBEBEB" | null |  | the render declares no color here |
| N/A | values | VisualElement#Frame | background-color | "#00000000" | null |  | the render declares no background-color here |
| N/A | values | VisualElement#Frame | font-size | 14 | null |  | the render declares no font-size here |
| PASS | values | VisualElement#Frame | flex-grow | 0 | "0" |  |  |
| PASS | values | VisualElement#Frame | flex-shrink | 1 | "1" |  |  |
| PASS | values | VisualElement#Frame | flex-direction | "Column" | "column" |  |  |
| N/A | values | TemplateContainer#layout-divider-solid-horizontal | color | "#EBEBEB" | null |  | the render declares no color here |
| N/A | values | TemplateContainer#layout-divider-solid-horizontal | background-color | "#00000000" | null |  | the render declares no background-color here |
| N/A | values | TemplateContainer#layout-divider-solid-horizontal | font-size | 14 | null |  | the render declares no font-size here |
| PASS | values | TemplateContainer#layout-divider-solid-horizontal | flex-grow | 0 | "0" |  |  |
| PASS | values | TemplateContainer#layout-divider-solid-horizontal | flex-shrink | 1 | "1" |  |  |
| PASS | values | TemplateContainer#layout-divider-solid-horizontal | flex-direction | "Column" | "column" |  |  |
| N/A | values | VisualElement#layout-divider-solid-horizontal | color | "#EBEBEB" | null |  | the render declares no color here |
| PASS | values | VisualElement#layout-divider-solid-horizontal | background-color | "#FFFFFF3D" | "#FFFFFF3D" |  |  |
| N/A | values | VisualElement#layout-divider-solid-horizontal | font-size | 14 | null |  | the render declares no font-size here |
| PASS | values | VisualElement#layout-divider-solid-horizontal | flex-grow | 0 | "0" |  |  |
| PASS | values | VisualElement#layout-divider-solid-horizontal | flex-shrink | 1 | "1" |  |  |
| PASS | values | VisualElement#layout-divider-solid-horizontal | flex-direction | "Column" | "column" |  |  |
| N/A | values | VisualElement#data_display-string-list-item-default-unpacked | color | "#EBEBEB" | null |  | the render declares no color here |
| N/A | values | VisualElement#data_display-string-list-item-default-unpacked | background-color | "#00000000" | null |  | the render declares no background-color here |
| N/A | values | VisualElement#data_display-string-list-item-default-unpacked | font-size | 14 | null |  | the render declares no font-size here |
| PASS | values | VisualElement#data_display-string-list-item-default-unpacked | flex-grow | 0 | "0" |  |  |
| PASS | values | VisualElement#data_display-string-list-item-default-unpacked | flex-shrink | 1 | "1" |  |  |
| PASS | values | VisualElement#data_display-string-list-item-default-unpacked | flex-direction | "Row" | "row" |  |  |
| N/A | values | VisualElement# | color | "#EBEBEB" | null |  | the render declares no color here |
| N/A | values | VisualElement# | background-color | "#00000000" | null |  | the render declares no background-color here |
| N/A | values | VisualElement# | font-size | 14 | null |  | the render declares no font-size here |
| PASS | values | VisualElement# | flex-grow | 0 | "0" |  |  |
| PASS | values | VisualElement# | flex-shrink | 0 | "0" |  |  |
| PASS | values | VisualElement# | flex-direction | "Column" | "column" |  |  |
| PASS | values | SIText#text | color | "#B7B7B9" | "#B7B7B9" |  |  |
| N/A | values | SIText#text | background-color | "#00000000" | null |  | the render declares no background-color here |
| PASS | values | SIText#text | font-size | 12 | "12px" |  |  |
| PASS | values | SIText#text | flex-grow | 0 | "0" |  |  |
| PASS | values | SIText#text | flex-shrink | 1 | "1" |  |  |
| PASS | values | SIText#text | flex-direction | "Column" | "column" |  |  |

## tile-tactics

Delivered text wired: 5 of 6 text nodes paired by structural path, 11 captured texts unpaired.

| Verdict | Check | Element | Property | Expected | Got | Delta | Note / cause |
|---|---|---|---|---|---|---|---|
| PASS | geometry | BindingExpect#TileBindingExpect | box | [0.0, 0.0, 311.5, 311.5] | [0, 0, 311.5, 311.5] | [0.0, 0.0, 0.0, 0.0] |  |
| PASS | geometry | BindingVariables#tactic-variables | box | [0.0, 0.0, 311.5, 311.5] | [0, 0, 311.5, 311.5] | [0.0, 0.0, 0.0, 0.0] |  |
| PASS | geometry | ComponentElement# | box | [0.0, 0.0, 311.5, 311.5] | [0, 0, 311.5, 311.5] | [0.0, 0.0, 0.0, 0.0] |  |
| PASS | geometry | TutorialAnchorElement# | box | [0.0, 0.0, 311.5, 311.5] | [0, 0, 311.5, 311.5] | [0.0, 0.0, 0.0, 0.0] |  |
| PASS | geometry | TemplateContainer#tile-square-4x4 | box | [0.0, 0.0, 311.5, 311.5] | [0, 0, 311.5, 311.5] | [0.0, 0.0, 0.0, 0.0] |  |
| PASS | geometry | BindingExpect#TileTemplateBindingExpect | box | [0.0, 0.0, 311.5, 311.5] | [0, 0, 311.5, 311.5] | [0.0, 0.0, 0.0, 0.0] |  |
| PASS | geometry | VisualElement#layout-tile-base-container | box | [0.0, 0.0, 311.5, 311.5] | [0, 0, 311.5, 311.5] | [0.0, 0.0, 0.0, 0.0] |  |
| PASS | geometry | BindingVariables#TileVariables | box | [0.0, 0.0, 311.5, 311.5] | [0, 0, 311.5, 311.5] | [0.0, 0.0, 0.0, 0.0] |  |
| PASS | geometry | SIStyleSetter#BackgroundStyleSetter | box | [0.0, 0.0, 311.5, 311.5] | [0, 0, 311.5, 311.5] | [0.0, 0.0, 0.0, 0.0] |  |
| PASS | geometry | SIButton#layout-tile-interaction-button | box | [0.0, 0.0, 311.5, 311.5] | [0, 0, 311.5, 311.5] | [0.0, 0.0, 0.0, 0.0] |  |
| PASS | geometry | VisualElement#Border_TIle | box | [0.0, 0.0, 311.5, 311.5] | [0, 0, 311.5, 311.5] | [0.0, 0.0, 0.0, 0.0] |  |
| PASS | geometry | VisualElement#title area frame | box | [0.0, 0.0, 311.5, 34.2] | [0, 0, 311.5, 34] | [0.0, 0.0, 0.0, -0.2] |  |
| PASS | geometry | VisualElement# | box | [11.7, 1.9, 0, 32.2] | [12, 2, 0, 32] | [0.3, 0.1, 0, -0.2] |  |
| FAIL | geometry | AutoScroller#auto-scroller | box | [11.7, 1.9, 41, 32.2] | [12, 2, 38.1, 32] | [0.3, 0.1, -2.9, -0.2] | cause (by rule): code-built content: the tactics pitch and its players are drawn in code, so the render's boxes around it differ |
| FAIL | geometry | SIText#title-text | box | [11.7, 1.9, 41, 32.2] | [12, 2, 38.1, 21.5] | [0.3, 0.1, -2.9, -10.7] | cause (by rule): code-built content: the tactics pitch and its players are drawn in code, so the render's boxes around it differ |
| PASS | geometry | TemplateContainer#states-templates-tile-content | box | [0.0, 34.1, 311.5, 277.3] | [0, 34, 311.5, 277.5] | [0.0, -0.1, 0.0, 0.2] |  |
| PASS | geometry | VisualElement# | box | [0.0, 256.8, 311.5, 54.7] | [0, 256, 311.5, 55.5] | [0.0, -0.8, 0.0, 0.8] |  |
| PASS | geometry | VisualElement#tile-templates-4x4-template-2 | box | [11.7, 34.1, 288.1, 269.5] | [12, 34, 287.5, 269.5] | [0.3, -0.1, -0.6, 0.0] |  |
| FAIL | geometry | VisualElement#TacticsPitch-UNPACKED | box | [11.7, 34.1, 288.1, 216.8] | [12, 34, 287.5, 175.7] | [0.3, -0.1, -0.6, -41.1] | cause (by rule): code-built content: the tactics pitch and its players are drawn in code, so the render's boxes around it differ |
| FAIL | geometry | BindingExpect#pitch-expect | box | [11.7, 34.1, 288.1, 216.8] | [12, 34, 287.5, 175.7] | [0.3, -0.1, -0.6, -41.1] | cause (by rule): code-built content: the tactics pitch and its players are drawn in code, so the render's boxes around it differ |
| FAIL | geometry | BindingRemapper#pitch-remapper | box | [11.7, 34.1, 288.1, 216.8] | [12, 34, 287.5, 175.7] | [0.3, -0.1, -0.6, -41.1] | cause (by rule): code-built content: the tactics pitch and its players are drawn in code, so the render's boxes around it differ |
| FAIL | geometry | BindingVariables#pitch-variables | box | [11.7, 34.1, 288.1, 216.8] | [12, 34, 287.5, 175.7] | [0.3, -0.1, -0.6, -41.1] | cause (by rule): code-built content: the tactics pitch and its players are drawn in code, so the render's boxes around it differ |
| PASS | geometry | VisualElement#TileHeaderElements | box | [11.7, 34.1, 288.1, 23.4] | [12, 34, 287.5, 24] | [0.3, -0.1, -0.6, 0.6] |  |
| FAIL | geometry | TemplateContainer#SetPiecesCell | box | [11.7, 34.1, 102.5, 23.4] | [12, 34, 88.9, 24] | [0.3, -0.1, -13.6, 0.6] | cause (by rule): code-built content: the tactics pitch and its players are drawn in code, so the render's boxes around it differ |
| FAIL | geometry | SIButton#OpenCardButton | box | [11.7, 34.1, 102.5, 23.4] | [12, 34, 88.9, 24] | [0.3, -0.1, -13.6, 0.6] | cause (by rule): code-built content: the tactics pitch and its players are drawn in code, so the render's boxes around it differ |
| FAIL | geometry | SIStyleSetter#IconStyleSetter | box | [20.5, 38.0, 15.6, 15.6] | [21, 46, 0, 0] | [0.5, 8.0, -15.6, -15.6] | cause (by rule): code-built content: the tactics pitch and its players are drawn in code, so the render's boxes around it differ |
| FAIL | geometry | SIText#CellText | box | [40.0, 35.1, 65.4, 21.5] | [25, 35.2, 66.9, 21.5] | [-15.0, 0.1, 1.5, 0.0] | cause (by rule): code-built content: the tactics pitch and its players are drawn in code, so the render's boxes around it differ |
| FAIL | geometry | TemplateContainer#PenaltiesCell | box | [114.2, 34.1, 81.1, 23.4] | [120.8, 34, 69.9, 24] | [6.6, -0.1, -11.2, 0.6] | cause (by rule): code-built content: the tactics pitch and its players are drawn in code, so the render's boxes around it differ |
| FAIL | geometry | SIButton#OpenCardButton | box | [122.0, 34.1, 65.4, 23.4] | [128.8, 34, 53.9, 24] | [6.8, -0.1, -11.5, 0.6] | cause (by rule): code-built content: the tactics pitch and its players are drawn in code, so the render's boxes around it differ |
| FAIL | geometry | SIStyleSetter#IconStyleSetter | box | [130.8, 38.0, 15.6, 15.6] | [137.8, 46, 0, 0] | [7.0, 8.0, -15.6, -15.6] | cause (by rule): code-built content: the tactics pitch and its players are drawn in code, so the render's boxes around it differ |
| FAIL | geometry | SIText#CellText | box | [150.3, 35.1, 28.3, 21.5] | [141.8, 35.2, 31.9, 21.5] | [-8.5, 0.1, 3.6, 0.0] | cause (by rule): code-built content: the tactics pitch and its players are drawn in code, so the render's boxes around it differ |
| FAIL | geometry | TemplateContainer#OppositionInstructionsCell | box | [195.3, 34.1, 104.5, 23.4] | [210.6, 34, 88.9, 24] | [15.3, -0.1, -15.6, 0.6] | cause (by rule): code-built content: the tactics pitch and its players are drawn in code, so the render's boxes around it differ |
| FAIL | geometry | SIButton#OpenCardButton | box | [195.3, 34.1, 104.5, 23.4] | [210.6, 34, 88.9, 24] | [15.3, -0.1, -15.6, 0.6] | cause (by rule): code-built content: the tactics pitch and its players are drawn in code, so the render's boxes around it differ |
| FAIL | geometry | SIStyleSetter#IconStyleSetter | box | [204.1, 38.0, 15.6, 15.6] | [219.6, 46, 0, 0] | [15.5, 8.0, -15.6, -15.6] | cause (by rule): code-built content: the tactics pitch and its players are drawn in code, so the render's boxes around it differ |
| PASS | geometry | SIText#CellText | box | [223.6, 35.1, 67.4, 21.5] | [223.6, 35.2, 66.9, 21.5] | [-0.0, 0.1, -0.5, 0.0] |  |
| FAIL | geometry | BindableSwitchElement# | box | [11.7, 34.1, 288.1, 216.8] | [12, 34, 287.5, 175.7] | [0.3, -0.1, -0.6, -41.1] | cause (by rule): code-built content: the tactics pitch and its players are drawn in code, so the render's boxes around it differ |
| FAIL | geometry | SIImage# | box | [11.7, 34.1, 288.1, 216.8] | [12, 34, 287.5, 175.7] | [0.3, -0.1, -0.6, -41.1] | cause (by rule): code-built content: the tactics pitch and its players are drawn in code, so the render's boxes around it differ |
| FAIL | geometry | FMTacticsPanel# | box | [11.7, 82.0, 288.1, 161.1] | [12, 82, 287.5, 119.7] | [0.3, 0.0, -0.6, -41.4] | cause (by rule): code-built content: the tactics pitch and its players are drawn in code, so the render's boxes around it differ |
| FAIL | geometry | BindableSwitchElement#tactic-info-switch | box | [11.7, 250.9, 288.1, 52.7] | [12, 209.7, 287.5, 93.8] | [0.3, -41.2, -0.6, 41.1] | cause (by rule): code-built content: the tactics pitch and its players are drawn in code, so the render's boxes around it differ |
| N/A | geometry | SIText#text | box | null | [0, 0, 0, 0] |  | no live element paired (not on screen, or not reached by the capture) |
| FAIL | geometry | VisualElement#tactic-info-container | box | [11.7, 271.4, 288.1, 19.5] | [12, 250.6, 287.5, 20] | [0.3, -20.8, -0.6, 0.5] | cause (by rule): code-built content: the tactics pitch and its players are drawn in code, so the render's boxes around it differ |
| FAIL | geometry | VisualElement#formation-cells--unpacked | box | [11.7, 271.4, 288.1, 19.5] | [12, 250.6, 287.5, 20] | [0.3, -20.8, -0.6, 0.5] | cause (by rule): code-built content: the tactics pitch and its players are drawn in code, so the render's boxes around it differ |
| FAIL | geometry | VisualElement#data_display-cell-combo_cell-default-type-default-icon-size-medium-orientation-horizontal-combo-2-cell | box | [11.7, 271.4, 288.1, 19.5] | [12, 250.6, 287.5, 20] | [0.3, -20.8, -0.6, 0.5] | cause (by rule): code-built content: the tactics pitch and its players are drawn in code, so the render's boxes around it differ |
| FAIL | geometry | VisualElement#frame | box | [70.3, 271.4, 170.9, 19.5] | [74.2, 250.6, 163.0, 20] | [3.9, -20.8, -7.9, 0.5] | cause (by rule): code-built content: the tactics pitch and its players are drawn in code, so the render's boxes around it differ |
| FAIL | geometry | BindingRemapper# | box | [70.3, 271.4, 78.1, 19.5] | [74.2, 250.6, 72.2, 20] | [3.9, -20.8, -5.9, 0.5] | cause (by rule): code-built content: the tactics pitch and its players are drawn in code, so the render's boxes around it differ |
| FAIL | geometry | VisualElement# | box | [70.3, 271.4, 74.2, 19.5] | [74.2, 250.6, 68.2, 20] | [3.9, -20.8, -6.0, 0.5] | cause (by rule): code-built content: the tactics pitch and its players are drawn in code, so the render's boxes around it differ |
| FAIL | geometry | VisualElement#game-concepts-in-possession_small | box | [70.3, 273.4, 15.6, 15.6] | [74.2, 252.6, 16, 16] | [3.9, -20.8, 0.4, 0.4] | cause (by rule): code-built content: the tactics pitch and its players are drawn in code, so the render's boxes around it differ |
| FAIL | geometry | SIText#in-posession-formation-text | box | [89.8, 271.4, 54.7, 20.5] | [94.2, 249.8, 48.2, 21.5] | [4.4, -21.6, -6.5, 1.0] | cause (by rule): code-built content: the tactics pitch and its players are drawn in code, so the render's boxes around it differ |
| FAIL | geometry | BindingRemapper# | box | [148.4, 271.4, 92.8, 19.5] | [146.5, 250.6, 90.8, 20] | [-1.9, -20.8, -2.0, 0.5] | cause (by rule): code-built content: the tactics pitch and its players are drawn in code, so the render's boxes around it differ |
| FAIL | geometry | VisualElement# | box | [148.4, 271.4, 92.8, 19.5] | [146.5, 250.6, 90.8, 20] | [-1.9, -20.8, -2.0, 0.5] | cause (by rule): code-built content: the tactics pitch and its players are drawn in code, so the render's boxes around it differ |
| FAIL | geometry | VisualElement#game-concepts-out-of-possession_small | box | [148.4, 273.4, 15.6, 15.6] | [146.5, 252.6, 16, 16] | [-1.9, -20.8, 0.4, 0.4] | cause (by rule): code-built content: the tactics pitch and its players are drawn in code, so the render's boxes around it differ |
| FAIL | geometry | SIText#out-of-possession-formation-text | box | [167.9, 271.4, 73.2, 20.5] | [166.5, 249.8, 70.8, 21.5] | [-1.4, -21.6, -2.4, 1.0] | cause (by rule): code-built content: the tactics pitch and its players are drawn in code, so the render's boxes around it differ |
| N/A | values | BindingExpect#TileBindingExpect | color | "#EBEBEB" | null |  | the render declares no color here |
| N/A | values | BindingExpect#TileBindingExpect | background-color | "#00000000" | null |  | the render declares no background-color here |
| N/A | values | BindingExpect#TileBindingExpect | font-size | 14 | null |  | the render declares no font-size here |
| PASS | values | BindingExpect#TileBindingExpect | flex-grow | 0 | "0" |  |  |
| PASS | values | BindingExpect#TileBindingExpect | flex-shrink | 1 | "1" |  |  |
| PASS | values | BindingExpect#TileBindingExpect | flex-direction | "Column" | "column" |  |  |
| N/A | values | BindingVariables#tactic-variables | color | "#EBEBEB" | null |  | the render declares no color here |
| N/A | values | BindingVariables#tactic-variables | background-color | "#00000000" | null |  | the render declares no background-color here |
| N/A | values | BindingVariables#tactic-variables | font-size | 14 | null |  | the render declares no font-size here |
| PASS | values | BindingVariables#tactic-variables | flex-grow | 0 | "0" |  |  |
| PASS | values | BindingVariables#tactic-variables | flex-shrink | 1 | "1" |  |  |
| PASS | values | BindingVariables#tactic-variables | flex-direction | "Column" | "column" |  |  |
| N/A | values | ComponentElement# | color | "#EBEBEB" | null |  | the render declares no color here |
| N/A | values | ComponentElement# | background-color | "#00000000" | null |  | the render declares no background-color here |
| N/A | values | ComponentElement# | font-size | 14 | null |  | the render declares no font-size here |
| PASS | values | ComponentElement# | flex-grow | 0 | "0" |  |  |
| PASS | values | ComponentElement# | flex-shrink | 1 | "1" |  |  |
| PASS | values | ComponentElement# | flex-direction | "Column" | "column" |  |  |
| N/A | values | TutorialAnchorElement# | color | "#EBEBEB" | null |  | the render declares no color here |
| N/A | values | TutorialAnchorElement# | background-color | "#00000000" | null |  | the render declares no background-color here |
| N/A | values | TutorialAnchorElement# | font-size | 14 | null |  | the render declares no font-size here |
| PASS | values | TutorialAnchorElement# | flex-grow | 0 | "0" |  |  |
| PASS | values | TutorialAnchorElement# | flex-shrink | 1 | "1" |  |  |
| PASS | values | TutorialAnchorElement# | flex-direction | "Column" | "column" |  |  |
| N/A | values | TemplateContainer#tile-square-4x4 | color | "#EBEBEB" | null |  | the render declares no color here |
| N/A | values | TemplateContainer#tile-square-4x4 | background-color | "#00000000" | null |  | the render declares no background-color here |
| N/A | values | TemplateContainer#tile-square-4x4 | font-size | 14 | null |  | the render declares no font-size here |
| PASS | values | TemplateContainer#tile-square-4x4 | flex-grow | 0 | "0" |  |  |
| PASS | values | TemplateContainer#tile-square-4x4 | flex-shrink | 1 | "1" |  |  |
| PASS | values | TemplateContainer#tile-square-4x4 | flex-direction | "Column" | "column" |  |  |
| N/A | values | BindingExpect#TileTemplateBindingExpect | color | "#EBEBEB" | null |  | the render declares no color here |
| N/A | values | BindingExpect#TileTemplateBindingExpect | background-color | "#00000000" | null |  | the render declares no background-color here |
| N/A | values | BindingExpect#TileTemplateBindingExpect | font-size | 14 | null |  | the render declares no font-size here |
| PASS | values | BindingExpect#TileTemplateBindingExpect | flex-grow | 1 | "1" |  |  |
| PASS | values | BindingExpect#TileTemplateBindingExpect | flex-shrink | 1 | "1" |  |  |
| PASS | values | BindingExpect#TileTemplateBindingExpect | flex-direction | "Column" | "column" |  |  |
| N/A | values | VisualElement#layout-tile-base-container | color | "#EBEBEB" | null |  | the render declares no color here |
| PASS | values | VisualElement#layout-tile-base-container | background-color | "#03614F" | "#03614F" |  |  |
| N/A | values | VisualElement#layout-tile-base-container | font-size | 14 | null |  | the render declares no font-size here |
| PASS | values | VisualElement#layout-tile-base-container | flex-grow | 0 | "0" |  |  |
| PASS | values | VisualElement#layout-tile-base-container | flex-shrink | 0 | "0" |  |  |
| PASS | values | VisualElement#layout-tile-base-container | flex-direction | "Column" | "column" |  |  |
| N/A | values | BindingVariables#TileVariables | color | "#EBEBEB" | null |  | the render declares no color here |
| N/A | values | BindingVariables#TileVariables | background-color | "#00000000" | null |  | the render declares no background-color here |
| N/A | values | BindingVariables#TileVariables | font-size | 14 | null |  | the render declares no font-size here |
| PASS | values | BindingVariables#TileVariables | flex-grow | 1 | "1" |  |  |
| PASS | values | BindingVariables#TileVariables | flex-shrink | 1 | "1" |  |  |
| PASS | values | BindingVariables#TileVariables | flex-direction | "Column" | "column" |  |  |
| N/A | values | SIStyleSetter#BackgroundStyleSetter | color | "#EBEBEB" | null |  | the render declares no color here |
| N/A | values | SIStyleSetter#BackgroundStyleSetter | background-color | "#00000000" | null |  | the render declares no background-color here |
| N/A | values | SIStyleSetter#BackgroundStyleSetter | font-size | 14 | null |  | the render declares no font-size here |
| PASS | values | SIStyleSetter#BackgroundStyleSetter | flex-grow | 1 | "1" |  |  |
| PASS | values | SIStyleSetter#BackgroundStyleSetter | flex-shrink | 1 | "1" |  |  |
| PASS | values | SIStyleSetter#BackgroundStyleSetter | flex-direction | "Column" | "column" |  |  |
| N/A | values | SIButton#layout-tile-interaction-button | color | "#EBEBEB" | null |  | the render declares no color here |
| PASS | values | SIButton#layout-tile-interaction-button | background-color | "#FFFFFF14" | "#FFFFFF14" |  |  |
| N/A | values | SIButton#layout-tile-interaction-button | font-size | 14 | null |  | the render declares no font-size here |
| PASS | values | SIButton#layout-tile-interaction-button | flex-grow | 0 | "0" |  |  |
| PASS | values | SIButton#layout-tile-interaction-button | flex-shrink | 0 | "0" |  |  |
| PASS | values | SIButton#layout-tile-interaction-button | flex-direction | "Column" | "column" |  |  |
| N/A | values | VisualElement#Border_TIle | color | "#EBEBEB" | null |  | the render declares no color here |
| N/A | values | VisualElement#Border_TIle | background-color | "#00000000" | null |  | the render declares no background-color here |
| N/A | values | VisualElement#Border_TIle | font-size | 14 | null |  | the render declares no font-size here |
| PASS | values | VisualElement#Border_TIle | flex-grow | 0 | "0" |  |  |
| PASS | values | VisualElement#Border_TIle | flex-shrink | 1 | "1" |  |  |
| PASS | values | VisualElement#Border_TIle | flex-direction | "Column" | "column" |  |  |
| N/A | values | VisualElement#title area frame | color | "#EBEBEB" | null |  | the render declares no color here |
| N/A | values | VisualElement#title area frame | background-color | "#00000000" | null |  | the render declares no background-color here |
| N/A | values | VisualElement#title area frame | font-size | 14 | null |  | the render declares no font-size here |
| PASS | values | VisualElement#title area frame | flex-grow | 0 | "0" |  |  |
| PASS | values | VisualElement#title area frame | flex-shrink | 1 | "1" |  |  |
| PASS | values | VisualElement#title area frame | flex-direction | "Row" | "row" |  |  |
| N/A | values | VisualElement# | color | "#EBEBEB" | null |  | the render declares no color here |
| N/A | values | VisualElement# | background-color | "#00000000" | null |  | the render declares no background-color here |
| N/A | values | VisualElement# | font-size | 14 | null |  | the render declares no font-size here |
| PASS | values | VisualElement# | flex-grow | 0 | "0" |  |  |
| PASS | values | VisualElement# | flex-shrink | 1 | "1" |  |  |
| PASS | values | VisualElement# | flex-direction | "Column" | "column" |  |  |
| N/A | values | AutoScroller#auto-scroller | color | "#EBEBEB" | null |  | the render declares no color here |
| N/A | values | AutoScroller#auto-scroller | background-color | "#00000000" | null |  | the render declares no background-color here |
| N/A | values | AutoScroller#auto-scroller | font-size | 14 | null |  | the render declares no font-size here |
| PASS | values | AutoScroller#auto-scroller | flex-grow | 0 | "0" |  |  |
| PASS | values | AutoScroller#auto-scroller | flex-shrink | 1 | "1" |  |  |
| PASS | values | AutoScroller#auto-scroller | flex-direction | "Column" | "column" |  |  |
| PASS | values | SIText#title-text | color | "#EBEBEB" | "#EBEBEB" |  |  |
| N/A | values | SIText#title-text | background-color | "#00000000" | null |  | the render declares no background-color here |
| PASS | values | SIText#title-text | font-size | 14 | "14px" |  |  |
| PASS | values | SIText#title-text | flex-grow | 0 | "0" |  |  |
| PASS | values | SIText#title-text | flex-shrink | 1 | "1" |  |  |
| PASS | values | SIText#title-text | flex-direction | "Column" | "column" |  |  |
| N/A | values | TemplateContainer#states-templates-tile-content | color | "#EBEBEB" | null |  | the render declares no color here |
| N/A | values | TemplateContainer#states-templates-tile-content | background-color | "#00000000" | null |  | the render declares no background-color here |
| N/A | values | TemplateContainer#states-templates-tile-content | font-size | 14 | null |  | the render declares no font-size here |
| PASS | values | TemplateContainer#states-templates-tile-content | flex-grow | 1 | "1" |  |  |
| PASS | values | TemplateContainer#states-templates-tile-content | flex-shrink | 1 | "1" |  |  |
| PASS | values | TemplateContainer#states-templates-tile-content | flex-direction | "Row" | "row" |  |  |
| N/A | values | VisualElement# | color | "#EBEBEB" | null |  | the render declares no color here |
| PASS | values | VisualElement# | background-color | "#00000033" | "#00000033" |  |  |
| N/A | values | VisualElement# | font-size | 14 | null |  | the render declares no font-size here |
| PASS | values | VisualElement# | flex-grow | 1 | "1" |  |  |
| PASS | values | VisualElement# | flex-shrink | 1 | "1" |  |  |
| PASS | values | VisualElement# | flex-direction | "Column" | "column" |  |  |
| N/A | values | VisualElement#tile-templates-4x4-template-2 | color | "#EBEBEB" | null |  | the render declares no color here |
| N/A | values | VisualElement#tile-templates-4x4-template-2 | background-color | "#00000000" | null |  | the render declares no background-color here |
| N/A | values | VisualElement#tile-templates-4x4-template-2 | font-size | 14 | null |  | the render declares no font-size here |
| PASS | values | VisualElement#tile-templates-4x4-template-2 | flex-grow | 1 | "1" |  |  |
| PASS | values | VisualElement#tile-templates-4x4-template-2 | flex-shrink | 1 | "1" |  |  |
| PASS | values | VisualElement#tile-templates-4x4-template-2 | flex-direction | "Column" | "column" |  |  |
| N/A | values | VisualElement#TacticsPitch-UNPACKED | color | "#EBEBEB" | null |  | the render declares no color here |
| N/A | values | VisualElement#TacticsPitch-UNPACKED | background-color | "#00000000" | null |  | the render declares no background-color here |
| N/A | values | VisualElement#TacticsPitch-UNPACKED | font-size | 14 | null |  | the render declares no font-size here |
| PASS | values | VisualElement#TacticsPitch-UNPACKED | flex-grow | 3 | "3" |  |  |
| PASS | values | VisualElement#TacticsPitch-UNPACKED | flex-shrink | 0 | "0" |  |  |
| PASS | values | VisualElement#TacticsPitch-UNPACKED | flex-direction | "Column" | "column" |  |  |
| N/A | values | BindingExpect#pitch-expect | color | "#EBEBEB" | null |  | the render declares no color here |
| N/A | values | BindingExpect#pitch-expect | background-color | "#00000000" | null |  | the render declares no background-color here |
| N/A | values | BindingExpect#pitch-expect | font-size | 14 | null |  | the render declares no font-size here |
| PASS | values | BindingExpect#pitch-expect | flex-grow | 1 | "1" |  |  |
| PASS | values | BindingExpect#pitch-expect | flex-shrink | 1 | "1" |  |  |
| PASS | values | BindingExpect#pitch-expect | flex-direction | "Column" | "column" |  |  |
| N/A | values | BindingRemapper#pitch-remapper | color | "#EBEBEB" | null |  | the render declares no color here |
| N/A | values | BindingRemapper#pitch-remapper | background-color | "#00000000" | null |  | the render declares no background-color here |
| N/A | values | BindingRemapper#pitch-remapper | font-size | 14 | null |  | the render declares no font-size here |
| PASS | values | BindingRemapper#pitch-remapper | flex-grow | 1 | "1" |  |  |
| PASS | values | BindingRemapper#pitch-remapper | flex-shrink | 1 | "1" |  |  |
| PASS | values | BindingRemapper#pitch-remapper | flex-direction | "Column" | "column" |  |  |
| N/A | values | BindingVariables#pitch-variables | color | "#EBEBEB" | null |  | the render declares no color here |
| N/A | values | BindingVariables#pitch-variables | background-color | "#00000000" | null |  | the render declares no background-color here |
| N/A | values | BindingVariables#pitch-variables | font-size | 14 | null |  | the render declares no font-size here |
| PASS | values | BindingVariables#pitch-variables | flex-grow | 0 | "0" |  |  |
| PASS | values | BindingVariables#pitch-variables | flex-shrink | 1 | "1" |  |  |
| PASS | values | BindingVariables#pitch-variables | flex-direction | "Column" | "column" |  |  |
| N/A | values | VisualElement#TileHeaderElements | color | "#EBEBEB" | null |  | the render declares no color here |
| N/A | values | VisualElement#TileHeaderElements | background-color | "#00000000" | null |  | the render declares no background-color here |
| N/A | values | VisualElement#TileHeaderElements | font-size | 14 | null |  | the render declares no font-size here |
| PASS | values | VisualElement#TileHeaderElements | flex-grow | 0 | "0" |  |  |
| PASS | values | VisualElement#TileHeaderElements | flex-shrink | 1 | "1" |  |  |
| PASS | values | VisualElement#TileHeaderElements | flex-direction | "Row" | "row" |  |  |
| N/A | values | TemplateContainer#SetPiecesCell | color | "#EBEBEB" | null |  | the render declares no color here |
| N/A | values | TemplateContainer#SetPiecesCell | background-color | "#00000000" | null |  | the render declares no background-color here |
| N/A | values | TemplateContainer#SetPiecesCell | font-size | 14 | null |  | the render declares no font-size here |
| PASS | values | TemplateContainer#SetPiecesCell | flex-grow | 0 | "0" |  |  |
| PASS | values | TemplateContainer#SetPiecesCell | flex-shrink | 1 | "1" |  |  |
| PASS | values | TemplateContainer#SetPiecesCell | flex-direction | "Column" | "column" |  |  |
| N/A | values | SIButton#OpenCardButton | color | "#EBEBEB" | null |  | the render declares no color here |
| PASS | values | SIButton#OpenCardButton | background-color | "#AF78FF33" | "#AF78FF33" |  |  |
| N/A | values | SIButton#OpenCardButton | font-size | 14 | null |  | the render declares no font-size here |
| PASS | values | SIButton#OpenCardButton | flex-grow | 0 | "0" |  |  |
| PASS | values | SIButton#OpenCardButton | flex-shrink | 0 | "0" |  |  |
| PASS | values | SIButton#OpenCardButton | flex-direction | "Row" | "row" |  |  |
| N/A | values | SIStyleSetter#IconStyleSetter | color | "#EBEBEB" | null |  | the render declares no color here |
| N/A | values | SIStyleSetter#IconStyleSetter | background-color | "#00000000" | null |  | the render declares no background-color here |
| N/A | values | SIStyleSetter#IconStyleSetter | font-size | 14 | null |  | the render declares no font-size here |
| PASS | values | SIStyleSetter#IconStyleSetter | flex-grow | 0 | "0" |  |  |
| FAIL | values | SIStyleSetter#IconStyleSetter | flex-shrink | 0 | "1" |  | cause (by rule): component-drawn image (SIImage, SIStyleSetter): its size and shrink come from component fields, not from style sheets |
| PASS | values | SIStyleSetter#IconStyleSetter | flex-direction | "Column" | "column" |  |  |
| PASS | values | SIText#CellText | color | "#EBEBEB" | "#EBEBEB" |  |  |
| N/A | values | SIText#CellText | background-color | "#00000000" | null |  | the render declares no background-color here |
| PASS | values | SIText#CellText | font-size | 14 | "14px" |  |  |
| PASS | values | SIText#CellText | flex-grow | 0 | "0" |  |  |
| PASS | values | SIText#CellText | flex-shrink | 1 | "1" |  |  |
| PASS | values | SIText#CellText | flex-direction | "Column" | "column" |  |  |
| N/A | values | TemplateContainer#PenaltiesCell | color | "#EBEBEB" | null |  | the render declares no color here |
| N/A | values | TemplateContainer#PenaltiesCell | background-color | "#00000000" | null |  | the render declares no background-color here |
| N/A | values | TemplateContainer#PenaltiesCell | font-size | 14 | null |  | the render declares no font-size here |
| PASS | values | TemplateContainer#PenaltiesCell | flex-grow | 0 | "0" |  |  |
| PASS | values | TemplateContainer#PenaltiesCell | flex-shrink | 1 | "1" |  |  |
| PASS | values | TemplateContainer#PenaltiesCell | flex-direction | "Column" | "column" |  |  |
| N/A | values | SIButton#OpenCardButton | color | "#EBEBEB" | null |  | the render declares no color here |
| PASS | values | SIButton#OpenCardButton | background-color | "#AF78FF33" | "#AF78FF33" |  |  |
| N/A | values | SIButton#OpenCardButton | font-size | 14 | null |  | the render declares no font-size here |
| PASS | values | SIButton#OpenCardButton | flex-grow | 0 | "0" |  |  |
| PASS | values | SIButton#OpenCardButton | flex-shrink | 0 | "0" |  |  |
| PASS | values | SIButton#OpenCardButton | flex-direction | "Row" | "row" |  |  |
| N/A | values | SIStyleSetter#IconStyleSetter | color | "#EBEBEB" | null |  | the render declares no color here |
| N/A | values | SIStyleSetter#IconStyleSetter | background-color | "#00000000" | null |  | the render declares no background-color here |
| N/A | values | SIStyleSetter#IconStyleSetter | font-size | 14 | null |  | the render declares no font-size here |
| PASS | values | SIStyleSetter#IconStyleSetter | flex-grow | 0 | "0" |  |  |
| FAIL | values | SIStyleSetter#IconStyleSetter | flex-shrink | 0 | "1" |  | cause (by rule): component-drawn image (SIImage, SIStyleSetter): its size and shrink come from component fields, not from style sheets |
| PASS | values | SIStyleSetter#IconStyleSetter | flex-direction | "Column" | "column" |  |  |
| PASS | values | SIText#CellText | color | "#EBEBEB" | "#EBEBEB" |  |  |
| N/A | values | SIText#CellText | background-color | "#00000000" | null |  | the render declares no background-color here |
| PASS | values | SIText#CellText | font-size | 14 | "14px" |  |  |
| PASS | values | SIText#CellText | flex-grow | 0 | "0" |  |  |
| PASS | values | SIText#CellText | flex-shrink | 1 | "1" |  |  |
| PASS | values | SIText#CellText | flex-direction | "Column" | "column" |  |  |
| N/A | values | TemplateContainer#OppositionInstructionsCell | color | "#EBEBEB" | null |  | the render declares no color here |
| N/A | values | TemplateContainer#OppositionInstructionsCell | background-color | "#00000000" | null |  | the render declares no background-color here |
| N/A | values | TemplateContainer#OppositionInstructionsCell | font-size | 14 | null |  | the render declares no font-size here |
| PASS | values | TemplateContainer#OppositionInstructionsCell | flex-grow | 0 | "0" |  |  |
| PASS | values | TemplateContainer#OppositionInstructionsCell | flex-shrink | 1 | "1" |  |  |
| PASS | values | TemplateContainer#OppositionInstructionsCell | flex-direction | "Column" | "column" |  |  |
| N/A | values | SIButton#OpenCardButton | color | "#EBEBEB" | null |  | the render declares no color here |
| PASS | values | SIButton#OpenCardButton | background-color | "#AF78FF33" | "#AF78FF33" |  |  |
| N/A | values | SIButton#OpenCardButton | font-size | 14 | null |  | the render declares no font-size here |
| PASS | values | SIButton#OpenCardButton | flex-grow | 0 | "0" |  |  |
| PASS | values | SIButton#OpenCardButton | flex-shrink | 0 | "0" |  |  |
| PASS | values | SIButton#OpenCardButton | flex-direction | "Row" | "row" |  |  |
| N/A | values | SIStyleSetter#IconStyleSetter | color | "#EBEBEB" | null |  | the render declares no color here |
| N/A | values | SIStyleSetter#IconStyleSetter | background-color | "#00000000" | null |  | the render declares no background-color here |
| N/A | values | SIStyleSetter#IconStyleSetter | font-size | 14 | null |  | the render declares no font-size here |
| PASS | values | SIStyleSetter#IconStyleSetter | flex-grow | 0 | "0" |  |  |
| FAIL | values | SIStyleSetter#IconStyleSetter | flex-shrink | 0 | "1" |  | cause (by rule): component-drawn image (SIImage, SIStyleSetter): its size and shrink come from component fields, not from style sheets |
| PASS | values | SIStyleSetter#IconStyleSetter | flex-direction | "Column" | "column" |  |  |
| PASS | values | SIText#CellText | color | "#EBEBEB" | "#EBEBEB" |  |  |
| N/A | values | SIText#CellText | background-color | "#00000000" | null |  | the render declares no background-color here |
| PASS | values | SIText#CellText | font-size | 14 | "14px" |  |  |
| PASS | values | SIText#CellText | flex-grow | 0 | "0" |  |  |
| PASS | values | SIText#CellText | flex-shrink | 1 | "1" |  |  |
| PASS | values | SIText#CellText | flex-direction | "Column" | "column" |  |  |
| N/A | values | BindableSwitchElement# | color | "#EBEBEB" | null |  | the render declares no color here |
| N/A | values | BindableSwitchElement# | background-color | "#00000000" | null |  | the render declares no background-color here |
| N/A | values | BindableSwitchElement# | font-size | 14 | null |  | the render declares no font-size here |
| PASS | values | BindableSwitchElement# | flex-grow | 1 | "1" |  |  |
| PASS | values | BindableSwitchElement# | flex-shrink | 1 | "1" |  |  |
| PASS | values | BindableSwitchElement# | flex-direction | "Column" | "column" |  |  |
| N/A | values | SIImage# | color | "#EBEBEB" | null |  | the render declares no color here |
| N/A | values | SIImage# | background-color | "#00000000" | null |  | the render declares no background-color here |
| N/A | values | SIImage# | font-size | 14 | null |  | the render declares no font-size here |
| PASS | values | SIImage# | flex-grow | 0 | "0" |  |  |
| PASS | values | SIImage# | flex-shrink | 1 | "1" |  |  |
| PASS | values | SIImage# | flex-direction | "Column" | "column" |  |  |
| N/A | values | FMTacticsPanel# | color | "#EBEBEB" | null |  | the render declares no color here |
| N/A | values | FMTacticsPanel# | background-color | "#00000000" | null |  | the render declares no background-color here |
| N/A | values | FMTacticsPanel# | font-size | 14 | null |  | the render declares no font-size here |
| PASS | values | FMTacticsPanel# | flex-grow | 1 | "1" |  |  |
| PASS | values | FMTacticsPanel# | flex-shrink | 1 | "1" |  |  |
| PASS | values | FMTacticsPanel# | flex-direction | "Column" | "column" |  |  |
| N/A | values | BindableSwitchElement#tactic-info-switch | color | "#EBEBEB" | null |  | the render declares no color here |
| N/A | values | BindableSwitchElement#tactic-info-switch | background-color | "#00000000" | null |  | the render declares no background-color here |
| N/A | values | BindableSwitchElement#tactic-info-switch | font-size | 14 | null |  | the render declares no font-size here |
| PASS | values | BindableSwitchElement#tactic-info-switch | flex-grow | 1 | "1" |  |  |
| PASS | values | BindableSwitchElement#tactic-info-switch | flex-shrink | 1 | "1" |  |  |
| PASS | values | BindableSwitchElement#tactic-info-switch | flex-direction | "Column" | "column" |  |  |
| N/A | values | VisualElement#tactic-info-container | color | "#EBEBEB" | null |  | the render declares no color here |
| N/A | values | VisualElement#tactic-info-container | background-color | "#00000000" | null |  | the render declares no background-color here |
| N/A | values | VisualElement#tactic-info-container | font-size | 14 | null |  | the render declares no font-size here |
| PASS | values | VisualElement#tactic-info-container | flex-grow | 0 | "0" |  |  |
| PASS | values | VisualElement#tactic-info-container | flex-shrink | 1 | "1" |  |  |
| PASS | values | VisualElement#tactic-info-container | flex-direction | "Column" | "column" |  |  |
| N/A | values | VisualElement#formation-cells--unpacked | color | "#EBEBEB" | null |  | the render declares no color here |
| N/A | values | VisualElement#formation-cells--unpacked | background-color | "#00000000" | null |  | the render declares no background-color here |
| N/A | values | VisualElement#formation-cells--unpacked | font-size | 14 | null |  | the render declares no font-size here |
| PASS | values | VisualElement#formation-cells--unpacked | flex-grow | 0 | "0" |  |  |
| PASS | values | VisualElement#formation-cells--unpacked | flex-shrink | 1 | "1" |  |  |
| PASS | values | VisualElement#formation-cells--unpacked | flex-direction | "Column" | "column" |  |  |
| N/A | values | VisualElement#data_display-cell-combo_cell-default-type-default-icon-size-medium-orientation-horizontal-combo-2-cell | color | "#EBEBEB" | null |  | the render declares no color here |
| N/A | values | VisualElement#data_display-cell-combo_cell-default-type-default-icon-size-medium-orientation-horizontal-combo-2-cell | background-color | "#00000000" | null |  | the render declares no background-color here |
| N/A | values | VisualElement#data_display-cell-combo_cell-default-type-default-icon-size-medium-orientation-horizontal-combo-2-cell | font-size | 14 | null |  | the render declares no font-size here |
| PASS | values | VisualElement#data_display-cell-combo_cell-default-type-default-icon-size-medium-orientation-horizontal-combo-2-cell | flex-grow | 0 | "0" |  |  |
| PASS | values | VisualElement#data_display-cell-combo_cell-default-type-default-icon-size-medium-orientation-horizontal-combo-2-cell | flex-shrink | 1 | "1" |  |  |
| PASS | values | VisualElement#data_display-cell-combo_cell-default-type-default-icon-size-medium-orientation-horizontal-combo-2-cell | flex-direction | "Row" | "row" |  |  |
| N/A | values | VisualElement#frame | color | "#EBEBEB" | null |  | the render declares no color here |
| N/A | values | VisualElement#frame | background-color | "#00000000" | null |  | the render declares no background-color here |
| N/A | values | VisualElement#frame | font-size | 14 | null |  | the render declares no font-size here |
| PASS | values | VisualElement#frame | flex-grow | 0 | "0" |  |  |
| PASS | values | VisualElement#frame | flex-shrink | 1 | "1" |  |  |
| PASS | values | VisualElement#frame | flex-direction | "Row" | "row" |  |  |
| N/A | values | BindingRemapper# | color | "#EBEBEB" | null |  | the render declares no color here |
| N/A | values | BindingRemapper# | background-color | "#00000000" | null |  | the render declares no background-color here |
| N/A | values | BindingRemapper# | font-size | 14 | null |  | the render declares no font-size here |
| PASS | values | BindingRemapper# | flex-grow | 0 | "0" |  |  |
| PASS | values | BindingRemapper# | flex-shrink | 1 | "1" |  |  |
| PASS | values | BindingRemapper# | flex-direction | "Column" | "column" |  |  |
| N/A | values | VisualElement# | color | "#EBEBEB" | null |  | the render declares no color here |
| N/A | values | VisualElement# | background-color | "#00000000" | null |  | the render declares no background-color here |
| N/A | values | VisualElement# | font-size | 14 | null |  | the render declares no font-size here |
| PASS | values | VisualElement# | flex-grow | 0 | "0" |  |  |
| PASS | values | VisualElement# | flex-shrink | 0 | "0" |  |  |
| PASS | values | VisualElement# | flex-direction | "Row" | "row" |  |  |
| N/A | values | VisualElement#game-concepts-in-possession_small | color | "#EBEBEB" | null |  | the render declares no color here |
| N/A | values | VisualElement#game-concepts-in-possession_small | background-color | "#00000000" | null |  | the render declares no background-color here |
| N/A | values | VisualElement#game-concepts-in-possession_small | font-size | 14 | null |  | the render declares no font-size here |
| PASS | values | VisualElement#game-concepts-in-possession_small | flex-grow | 0 | "0" |  |  |
| PASS | values | VisualElement#game-concepts-in-possession_small | flex-shrink | 0 | "0" |  |  |
| PASS | values | VisualElement#game-concepts-in-possession_small | flex-direction | "Column" | "column" |  |  |
| PASS | values | SIText#in-posession-formation-text | color | "#EBEBEB" | "#EBEBEB" |  |  |
| N/A | values | SIText#in-posession-formation-text | background-color | "#00000000" | null |  | the render declares no background-color here |
| PASS | values | SIText#in-posession-formation-text | font-size | 14 | "14px" |  |  |
| PASS | values | SIText#in-posession-formation-text | flex-grow | 0 | "0" |  |  |
| PASS | values | SIText#in-posession-formation-text | flex-shrink | 1 | "1" |  |  |
| PASS | values | SIText#in-posession-formation-text | flex-direction | "Column" | "column" |  |  |
| N/A | values | BindingRemapper# | color | "#EBEBEB" | null |  | the render declares no color here |
| N/A | values | BindingRemapper# | background-color | "#00000000" | null |  | the render declares no background-color here |
| N/A | values | BindingRemapper# | font-size | 14 | null |  | the render declares no font-size here |
| PASS | values | BindingRemapper# | flex-grow | 0 | "0" |  |  |
| PASS | values | BindingRemapper# | flex-shrink | 1 | "1" |  |  |
| PASS | values | BindingRemapper# | flex-direction | "Column" | "column" |  |  |
| N/A | values | VisualElement# | color | "#EBEBEB" | null |  | the render declares no color here |
| N/A | values | VisualElement# | background-color | "#00000000" | null |  | the render declares no background-color here |
| N/A | values | VisualElement# | font-size | 14 | null |  | the render declares no font-size here |
| PASS | values | VisualElement# | flex-grow | 0 | "0" |  |  |
| PASS | values | VisualElement# | flex-shrink | 0 | "0" |  |  |
| PASS | values | VisualElement# | flex-direction | "Row" | "row" |  |  |
| N/A | values | VisualElement#game-concepts-out-of-possession_small | color | "#EBEBEB" | null |  | the render declares no color here |
| N/A | values | VisualElement#game-concepts-out-of-possession_small | background-color | "#00000000" | null |  | the render declares no background-color here |
| N/A | values | VisualElement#game-concepts-out-of-possession_small | font-size | 14 | null |  | the render declares no font-size here |
| PASS | values | VisualElement#game-concepts-out-of-possession_small | flex-grow | 0 | "0" |  |  |
| PASS | values | VisualElement#game-concepts-out-of-possession_small | flex-shrink | 0 | "0" |  |  |
| PASS | values | VisualElement#game-concepts-out-of-possession_small | flex-direction | "Column" | "column" |  |  |
| PASS | values | SIText#out-of-possession-formation-text | color | "#EBEBEB" | "#EBEBEB" |  |  |
| N/A | values | SIText#out-of-possession-formation-text | background-color | "#00000000" | null |  | the render declares no background-color here |
| PASS | values | SIText#out-of-possession-formation-text | font-size | 14 | "14px" |  |  |
| PASS | values | SIText#out-of-possession-formation-text | flex-grow | 0 | "0" |  |  |
| PASS | values | SIText#out-of-possession-formation-text | flex-shrink | 1 | "1" |  |  |
| PASS | values | SIText#out-of-possession-formation-text | flex-direction | "Column" | "column" |  |  |

## tile-training

Delivered text wired: 6 of 8 text nodes paired by structural path, 8 captured texts unpaired.

| Verdict | Check | Element | Property | Expected | Got | Delta | Note / cause |
|---|---|---|---|---|---|---|---|
| PASS | geometry | BindingExpect#TileBindingExpect | box | [0.0, 0.0, 311.5, 311.5] | [0, 0, 311.5, 311.5] | [0.0, 0.0, 0.0, 0.0] |  |
| PASS | geometry | TutorialAnchorElement# | box | [0.0, 0.0, 311.5, 311.5] | [0, 0, 311.5, 311.5] | [0.0, 0.0, 0.0, 0.0] |  |
| PASS | geometry | TemplateContainer#tile-square-4x4 | box | [0.0, 0.0, 311.5, 311.5] | [0, 0, 311.5, 311.5] | [0.0, 0.0, 0.0, 0.0] |  |
| PASS | geometry | BindingExpect#TileTemplateBindingExpect | box | [0.0, 0.0, 311.5, 311.5] | [0, 0, 311.5, 311.5] | [0.0, 0.0, 0.0, 0.0] |  |
| PASS | geometry | VisualElement#layout-tile-base-container | box | [0.0, 0.0, 311.5, 311.5] | [0, 0, 311.5, 311.5] | [0.0, 0.0, 0.0, 0.0] |  |
| PASS | geometry | BindingVariables#TileVariables | box | [0.0, 0.0, 311.5, 311.5] | [0, 0, 311.5, 311.5] | [0.0, 0.0, 0.0, 0.0] |  |
| PASS | geometry | SIButton#layout-tile-interaction-button | box | [0.0, 0.0, 311.5, 311.5] | [0, 0, 311.5, 311.5] | [0.0, 0.0, 0.0, 0.0] |  |
| PASS | geometry | VisualElement#Tile_Border | box | [0.0, 0.0, 311.5, 311.5] | [0, 0, 311.5, 311.5] | [0.0, 0.0, 0.0, 0.0] |  |
| PASS | geometry | VisualElement#title area frame | box | [0.0, 0.0, 311.5, 34.2] | [0, 0, 311.5, 34] | [0.0, 0.0, 0.0, -0.2] |  |
| PASS | geometry | VisualElement# | box | [11.7, 1.9, 0, 32.2] | [12, 2, 0, 32] | [0.3, 0.1, 0, -0.2] |  |
| PASS | geometry | VisualElement#TitleContainer | box | [11.7, 1.9, 288.1, 32.2] | [12, 2, 287.5, 32] | [0.3, 0.1, -0.6, -0.2] |  |
| FAIL | geometry | AutoScroller# | box | [11.7, 8.8, 288.1, 17.6] | [12, 2, 287.5, 32] | [0.3, -6.8, -0.6, 14.4] | cause (by rule): code-built content: the Training tile's weekly schedule, calendar and training lists are built at run time (the capture holds 'This Week's Schedule', Mon to Sun, the counts), so everything below them is displaced in the render |
| FAIL | geometry | SIText#title-text | box | [11.7, 8.8, 46.9, 17.6] | [12, 2, 283.5, 16] | [0.3, -6.8, 236.6, -1.6] | cause (by rule): code-built content: the Training tile's weekly schedule, calendar and training lists are built at run time (the capture holds 'This Week's Schedule', Mon to Sun, the counts), so everything below them is displaced in the render |
| FAIL | geometry | SIVisible# | box | [11.7, 8.8, 0, 0] | [12, 18, 287.5, 16] | [0.3, 9.2, 287.5, 16] | cause (by rule): code-built content: the Training tile's weekly schedule, calendar and training lists are built at run time (the capture holds 'This Week's Schedule', Mon to Sun, the counts), so everything below them is displaced in the render |
| N/A | geometry | SIText#title-text-alt | box | null | [12, 18, 287.5, 16] |  | no live element paired (not on screen, or not reached by the capture) |
| PASS | geometry | VisualElement#CarouselMask | box | [303.7, 1.9, 0, 32.2] | [303.5, 2, 0, 32] | [-0.2, 0.1, 0, -0.2] |  |
| PASS | geometry | TemplateContainer#states-templates-tile-content | box | [0.0, 34.2, 311.5, 277.3] | [0, 34, 311.5, 277.5] | [0.0, -0.2, 0.0, 0.2] |  |
| FAIL | geometry | ComponentElement# | box | [11.7, 34.2, 288.1, 222.7] | [12, 34, 287.5, 118.3] | [0.3, -0.2, -0.6, -104.4] | cause (by rule): code-built content: the Training tile's weekly schedule, calendar and training lists are built at run time (the capture holds 'This Week's Schedule', Mon to Sun, the counts), so everything below them is displaced in the render |
| FAIL | geometry | VisualElement#TrainingTile | box | [11.7, 34.2, 288.1, 269.5] | [12, 34, 287.5, 118.3] | [0.3, -0.2, -0.6, -151.2] | cause (by rule): code-built content: the Training tile's weekly schedule, calendar and training lists are built at run time (the capture holds 'This Week's Schedule', Mon to Sun, the counts), so everything below them is displaced in the render |
| PASS | geometry | SIText#ScheduleTitle | box | [11.7, 34.2, 288.1, 18.6] | [12, 34, 287.5, 18.6] | [0.3, -0.2, -0.6, -0.0] |  |
| FAIL | geometry | StreamedObjectList#Week | box | [8.7, 60.5, 293.9, 105.5] | [155.8, 60.6, 0, 0] | [147.0, 0.1, -293.9, -105.5] | cause (by rule): code-built content: the Training tile's weekly schedule, calendar and training lists are built at run time (the capture holds 'This Week's Schedule', Mon to Sun, the counts), so everything below them is displaced in the render |
| FAIL | geometry | TemplateContainer#Divider | box | [11.7, 181.6, 288.1, 1] | [12, 76.6, 287.5, 1] | [0.3, -105.0, -0.6, 0] | cause (by rule): code-built content: the Training tile's weekly schedule, calendar and training lists are built at run time (the capture holds 'This Week's Schedule', Mon to Sun, the counts), so everything below them is displaced in the render |
| FAIL | geometry | VisualElement#layout-divider-solid-horizontal | box | [11.7, 181.6, 288.1, 1] | [12, 76.6, 287.5, 1] | [0.3, -105.0, -0.6, 0] | cause (by rule): code-built content: the Training tile's weekly schedule, calendar and training lists are built at run time (the capture holds 'This Week's Schedule', Mon to Sun, the counts), so everything below them is displaced in the render |
| FAIL | geometry | SIText#IndividualTrainingTitle | box | [11.7, 198.2, 288.1, 18.6] | [12, 93.6, 287.5, 18.6] | [0.3, -104.6, -0.6, -0.0] | cause (by rule): code-built content: the Training tile's weekly schedule, calendar and training lists are built at run time (the capture holds 'This Week's Schedule', Mon to Sun, the counts), so everything below them is displaced in the render |
| FAIL | geometry | VisualElement#IndividualTraining | box | [11.7, 216.8, 288.1, 40] | [12, 112.2, 287.5, 40.1] | [0.3, -104.6, -0.6, 0.1] | cause (by rule): code-built content: the Training tile's weekly schedule, calendar and training lists are built at run time (the capture holds 'This Week's Schedule', Mon to Sun, the counts), so everything below them is displaced in the render |
| FAIL | geometry | VisualElement#Improvements | box | [11.7, 216.8, 151.4, 40] | [12, 112.2, 148.4, 40.1] | [0.3, -104.6, -3.0, 0.1] | cause (by rule): code-built content: the Training tile's weekly schedule, calendar and training lists are built at run time (the capture holds 'This Week's Schedule', Mon to Sun, the counts), so everything below them is displaced in the render |
| FAIL | geometry | VisualElement#Stat | box | [11.7, 216.8, 143.6, 21.5] | [12, 112.2, 140.4, 21.5] | [0.3, -104.6, -3.2, 0.0] | cause (by rule): code-built content: the Training tile's weekly schedule, calendar and training lists are built at run time (the capture holds 'This Week's Schedule', Mon to Sun, the counts), so everything below them is displaced in the render |
| FAIL | geometry | SIImage#Arrow | box | [11.7, 216.8, 15.6, 16.6] | [12, 112.2, 0, 21.5] | [0.3, -104.6, -15.6, 4.9] | cause (by rule): code-built content: the Training tile's weekly schedule, calendar and training lists are built at run time (the capture holds 'This Week's Schedule', Mon to Sun, the counts), so everything below them is displaced in the render |
| FAIL | geometry | SIText#Value | box | [27.3, 216.8, 20.5, 21.5] | [12, 112.2, 19.6, 21.5] | [-15.3, -104.6, -0.9, 0.0] | cause (by rule): code-built content: the Training tile's weekly schedule, calendar and training lists are built at run time (the capture holds 'This Week's Schedule', Mon to Sun, the counts), so everything below them is displaced in the render |
| FAIL | geometry | SIText#Title | box | [11.7, 238.3, 143.6, 18.6] | [12, 133.7, 140.4, 18.6] | [0.3, -104.6, -3.2, -0.0] | cause (by rule): code-built content: the Training tile's weekly schedule, calendar and training lists are built at run time (the capture holds 'This Week's Schedule', Mon to Sun, the counts), so everything below them is displaced in the render |
| FAIL | geometry | VisualElement#Regressions | box | [163.0, 216.8, 136.7, 40] | [160.4, 112.2, 139.1, 40.1] | [-2.6, -104.6, 2.4, 0.1] | cause (by rule): code-built content: the Training tile's weekly schedule, calendar and training lists are built at run time (the capture holds 'This Week's Schedule', Mon to Sun, the counts), so everything below them is displaced in the render |
| FAIL | geometry | VisualElement#Stat | box | [170.9, 216.8, 128.9, 21.5] | [168.4, 112.2, 131.1, 21.5] | [-2.5, -104.6, 2.2, 0.0] | cause (by rule): code-built content: the Training tile's weekly schedule, calendar and training lists are built at run time (the capture holds 'This Week's Schedule', Mon to Sun, the counts), so everything below them is displaced in the render |
| FAIL | geometry | SIImage#Arrow | box | [170.9, 216.8, 15.6, 16.6] | [168.4, 112.2, 0, 21.5] | [-2.5, -104.6, -15.6, 4.9] | cause (by rule): code-built content: the Training tile's weekly schedule, calendar and training lists are built at run time (the capture holds 'This Week's Schedule', Mon to Sun, the counts), so everything below them is displaced in the render |
| FAIL | geometry | SIText#Value | box | [186.5, 216.8, 13.7, 21.5] | [168.4, 112.2, 11.8, 21.5] | [-18.1, -104.6, -1.9, 0.0] | cause (by rule): code-built content: the Training tile's weekly schedule, calendar and training lists are built at run time (the capture holds 'This Week's Schedule', Mon to Sun, the counts), so everything below them is displaced in the render |
| FAIL | geometry | SIText#Title | box | [170.9, 238.3, 128.9, 18.6] | [168.4, 133.7, 131.1, 18.6] | [-2.5, -104.6, 2.2, -0.0] | cause (by rule): code-built content: the Training tile's weekly schedule, calendar and training lists are built at run time (the capture holds 'This Week's Schedule', Mon to Sun, the counts), so everything below them is displaced in the render |
| N/A | values | BindingExpect#TileBindingExpect | color | "#EBEBEB" | null |  | the render declares no color here |
| N/A | values | BindingExpect#TileBindingExpect | background-color | "#00000000" | null |  | the render declares no background-color here |
| N/A | values | BindingExpect#TileBindingExpect | font-size | 14 | null |  | the render declares no font-size here |
| PASS | values | BindingExpect#TileBindingExpect | flex-grow | 0 | "0" |  |  |
| PASS | values | BindingExpect#TileBindingExpect | flex-shrink | 1 | "1" |  |  |
| PASS | values | BindingExpect#TileBindingExpect | flex-direction | "Column" | "column" |  |  |
| N/A | values | TutorialAnchorElement# | color | "#EBEBEB" | null |  | the render declares no color here |
| N/A | values | TutorialAnchorElement# | background-color | "#00000000" | null |  | the render declares no background-color here |
| N/A | values | TutorialAnchorElement# | font-size | 14 | null |  | the render declares no font-size here |
| PASS | values | TutorialAnchorElement# | flex-grow | 0 | "0" |  |  |
| PASS | values | TutorialAnchorElement# | flex-shrink | 1 | "1" |  |  |
| PASS | values | TutorialAnchorElement# | flex-direction | "Column" | "column" |  |  |
| N/A | values | TemplateContainer#tile-square-4x4 | color | "#EBEBEB" | null |  | the render declares no color here |
| N/A | values | TemplateContainer#tile-square-4x4 | background-color | "#00000000" | null |  | the render declares no background-color here |
| N/A | values | TemplateContainer#tile-square-4x4 | font-size | 14 | null |  | the render declares no font-size here |
| PASS | values | TemplateContainer#tile-square-4x4 | flex-grow | 0 | "0" |  |  |
| PASS | values | TemplateContainer#tile-square-4x4 | flex-shrink | 1 | "1" |  |  |
| PASS | values | TemplateContainer#tile-square-4x4 | flex-direction | "Column" | "column" |  |  |
| N/A | values | BindingExpect#TileTemplateBindingExpect | color | "#EBEBEB" | null |  | the render declares no color here |
| N/A | values | BindingExpect#TileTemplateBindingExpect | background-color | "#00000000" | null |  | the render declares no background-color here |
| N/A | values | BindingExpect#TileTemplateBindingExpect | font-size | 14 | null |  | the render declares no font-size here |
| PASS | values | BindingExpect#TileTemplateBindingExpect | flex-grow | 1 | "1" |  |  |
| PASS | values | BindingExpect#TileTemplateBindingExpect | flex-shrink | 1 | "1" |  |  |
| PASS | values | BindingExpect#TileTemplateBindingExpect | flex-direction | "Column" | "column" |  |  |
| N/A | values | VisualElement#layout-tile-base-container | color | "#EBEBEB" | null |  | the render declares no color here |
| N/A | values | VisualElement#layout-tile-base-container | background-color | "#00000000" | null |  | the render declares no background-color here |
| N/A | values | VisualElement#layout-tile-base-container | font-size | 14 | null |  | the render declares no font-size here |
| PASS | values | VisualElement#layout-tile-base-container | flex-grow | 0 | "0" |  |  |
| PASS | values | VisualElement#layout-tile-base-container | flex-shrink | 0 | "0" |  |  |
| PASS | values | VisualElement#layout-tile-base-container | flex-direction | "Column" | "column" |  |  |
| N/A | values | BindingVariables#TileVariables | color | "#EBEBEB" | null |  | the render declares no color here |
| N/A | values | BindingVariables#TileVariables | background-color | "#00000000" | null |  | the render declares no background-color here |
| N/A | values | BindingVariables#TileVariables | font-size | 14 | null |  | the render declares no font-size here |
| PASS | values | BindingVariables#TileVariables | flex-grow | 1 | "1" |  |  |
| PASS | values | BindingVariables#TileVariables | flex-shrink | 1 | "1" |  |  |
| PASS | values | BindingVariables#TileVariables | flex-direction | "Column" | "column" |  |  |
| N/A | values | SIButton#layout-tile-interaction-button | color | "#EBEBEB" | null |  | the render declares no color here |
| FAIL | values | SIButton#layout-tile-interaction-button | background-color | "#17223F" | "#1E2129" |  | cause (by rule): run-time club-colour sheet (an empty-named root sheet, not applied): the game paints this from the club's colours |
| N/A | values | SIButton#layout-tile-interaction-button | font-size | 14 | null |  | the render declares no font-size here |
| PASS | values | SIButton#layout-tile-interaction-button | flex-grow | 0 | "0" |  |  |
| PASS | values | SIButton#layout-tile-interaction-button | flex-shrink | 0 | "0" |  |  |
| PASS | values | SIButton#layout-tile-interaction-button | flex-direction | "Column" | "column" |  |  |
| N/A | values | VisualElement#Tile_Border | color | "#EBEBEB" | null |  | the render declares no color here |
| N/A | values | VisualElement#Tile_Border | background-color | "#00000000" | null |  | the render declares no background-color here |
| N/A | values | VisualElement#Tile_Border | font-size | 14 | null |  | the render declares no font-size here |
| PASS | values | VisualElement#Tile_Border | flex-grow | 1 | "1" |  |  |
| PASS | values | VisualElement#Tile_Border | flex-shrink | 1 | "1" |  |  |
| PASS | values | VisualElement#Tile_Border | flex-direction | "Column" | "column" |  |  |
| N/A | values | VisualElement#title area frame | color | "#EBEBEB" | null |  | the render declares no color here |
| N/A | values | VisualElement#title area frame | background-color | "#00000000" | null |  | the render declares no background-color here |
| N/A | values | VisualElement#title area frame | font-size | 14 | null |  | the render declares no font-size here |
| PASS | values | VisualElement#title area frame | flex-grow | 0 | "0" |  |  |
| PASS | values | VisualElement#title area frame | flex-shrink | 1 | "1" |  |  |
| PASS | values | VisualElement#title area frame | flex-direction | "Row" | "row" |  |  |
| N/A | values | VisualElement# | color | "#EBEBEB" | null |  | the render declares no color here |
| N/A | values | VisualElement# | background-color | "#00000000" | null |  | the render declares no background-color here |
| N/A | values | VisualElement# | font-size | 14 | null |  | the render declares no font-size here |
| PASS | values | VisualElement# | flex-grow | 0 | "0" |  |  |
| PASS | values | VisualElement# | flex-shrink | 1 | "1" |  |  |
| PASS | values | VisualElement# | flex-direction | "Column" | "column" |  |  |
| N/A | values | VisualElement#TitleContainer | color | "#EBEBEB" | null |  | the render declares no color here |
| N/A | values | VisualElement#TitleContainer | background-color | "#00000000" | null |  | the render declares no background-color here |
| N/A | values | VisualElement#TitleContainer | font-size | 14 | null |  | the render declares no font-size here |
| PASS | values | VisualElement#TitleContainer | flex-grow | 1 | "1" |  |  |
| PASS | values | VisualElement#TitleContainer | flex-shrink | 0 | "0" |  |  |
| PASS | values | VisualElement#TitleContainer | flex-direction | "Column" | "column" |  |  |
| N/A | values | AutoScroller# | color | "#EBEBEB" | null |  | the render declares no color here |
| N/A | values | AutoScroller# | background-color | "#00000000" | null |  | the render declares no background-color here |
| N/A | values | AutoScroller# | font-size | 14 | null |  | the render declares no font-size here |
| PASS | values | AutoScroller# | flex-grow | 0 | "0" |  |  |
| PASS | values | AutoScroller# | flex-shrink | 1 | "1" |  |  |
| PASS | values | AutoScroller# | flex-direction | "Column" | "column" |  |  |
| PASS | values | SIText#title-text | color | "#FAFAFA" | "#FAFAFA" |  |  |
| N/A | values | SIText#title-text | background-color | "#00000000" | null |  | the render declares no background-color here |
| PASS | values | SIText#title-text | font-size | 14 | "14px" |  |  |
| PASS | values | SIText#title-text | flex-grow | 0 | "0" |  |  |
| PASS | values | SIText#title-text | flex-shrink | 1 | "1" |  |  |
| PASS | values | SIText#title-text | flex-direction | "Column" | "column" |  |  |
| N/A | values | SIVisible# | color | "#EBEBEB" | null |  | the render declares no color here |
| N/A | values | SIVisible# | background-color | "#00000000" | null |  | the render declares no background-color here |
| N/A | values | SIVisible# | font-size | 14 | null |  | the render declares no font-size here |
| PASS | values | SIVisible# | flex-grow | 0 | "0" |  |  |
| PASS | values | SIVisible# | flex-shrink | 1 | "1" |  |  |
| PASS | values | SIVisible# | flex-direction | "Column" | "column" |  |  |
| N/A | values | VisualElement#CarouselMask | color | "#EBEBEB" | null |  | the render declares no color here |
| N/A | values | VisualElement#CarouselMask | background-color | "#00000000" | null |  | the render declares no background-color here |
| N/A | values | VisualElement#CarouselMask | font-size | 14 | null |  | the render declares no font-size here |
| PASS | values | VisualElement#CarouselMask | flex-grow | 0 | "0" |  |  |
| PASS | values | VisualElement#CarouselMask | flex-shrink | 1 | "1" |  |  |
| PASS | values | VisualElement#CarouselMask | flex-direction | "Column" | "column" |  |  |
| N/A | values | TemplateContainer#states-templates-tile-content | color | "#EBEBEB" | null |  | the render declares no color here |
| N/A | values | TemplateContainer#states-templates-tile-content | background-color | "#00000000" | null |  | the render declares no background-color here |
| N/A | values | TemplateContainer#states-templates-tile-content | font-size | 14 | null |  | the render declares no font-size here |
| PASS | values | TemplateContainer#states-templates-tile-content | flex-grow | 1 | "1" |  |  |
| PASS | values | TemplateContainer#states-templates-tile-content | flex-shrink | 1 | "1" |  |  |
| PASS | values | TemplateContainer#states-templates-tile-content | flex-direction | "Row" | "row" |  |  |
| N/A | values | ComponentElement# | color | "#EBEBEB" | null |  | the render declares no color here |
| N/A | values | ComponentElement# | background-color | "#00000000" | null |  | the render declares no background-color here |
| N/A | values | ComponentElement# | font-size | 14 | null |  | the render declares no font-size here |
| PASS | values | ComponentElement# | flex-grow | 1 | "1" |  |  |
| PASS | values | ComponentElement# | flex-shrink | 1 | "1" |  |  |
| PASS | values | ComponentElement# | flex-direction | "Column" | "column" |  |  |
| N/A | values | VisualElement#TrainingTile | color | "#EBEBEB" | null |  | the render declares no color here |
| N/A | values | VisualElement#TrainingTile | background-color | "#00000000" | null |  | the render declares no background-color here |
| N/A | values | VisualElement#TrainingTile | font-size | 14 | null |  | the render declares no font-size here |
| PASS | values | VisualElement#TrainingTile | flex-grow | 1 | "1" |  |  |
| PASS | values | VisualElement#TrainingTile | flex-shrink | 1 | "1" |  |  |
| PASS | values | VisualElement#TrainingTile | flex-direction | "Column" | "column" |  |  |
| PASS | values | SIText#ScheduleTitle | color | "#B7B7B9" | "#B7B7B9" |  |  |
| N/A | values | SIText#ScheduleTitle | background-color | "#00000000" | null |  | the render declares no background-color here |
| PASS | values | SIText#ScheduleTitle | font-size | 12 | "12px" |  |  |
| PASS | values | SIText#ScheduleTitle | flex-grow | 0 | "0" |  |  |
| PASS | values | SIText#ScheduleTitle | flex-shrink | 1 | "1" |  |  |
| PASS | values | SIText#ScheduleTitle | flex-direction | "Column" | "column" |  |  |
| N/A | values | StreamedObjectList#Week | color | "#EBEBEB" | null |  | the render declares no color here |
| N/A | values | StreamedObjectList#Week | background-color | "#00000000" | null |  | the render declares no background-color here |
| N/A | values | StreamedObjectList#Week | font-size | 14 | null |  | the render declares no font-size here |
| PASS | values | StreamedObjectList#Week | flex-grow | 0 | "0" |  |  |
| PASS | values | StreamedObjectList#Week | flex-shrink | 0 | "0" |  |  |
| PASS | values | StreamedObjectList#Week | flex-direction | "Row" | "row" |  |  |
| N/A | values | TemplateContainer#Divider | color | "#EBEBEB" | null |  | the render declares no color here |
| PASS | values | TemplateContainer#Divider | background-color | "#FFFFFF33" | "#FFFFFF33" |  |  |
| N/A | values | TemplateContainer#Divider | font-size | 14 | null |  | the render declares no font-size here |
| PASS | values | TemplateContainer#Divider | flex-grow | 0 | "0" |  |  |
| PASS | values | TemplateContainer#Divider | flex-shrink | 0 | "0" |  |  |
| PASS | values | TemplateContainer#Divider | flex-direction | "Column" | "column" |  |  |
| N/A | values | VisualElement#layout-divider-solid-horizontal | color | "#EBEBEB" | null |  | the render declares no color here |
| PASS | values | VisualElement#layout-divider-solid-horizontal | background-color | "#FFFFFF3D" | "#FFFFFF3D" |  |  |
| N/A | values | VisualElement#layout-divider-solid-horizontal | font-size | 14 | null |  | the render declares no font-size here |
| PASS | values | VisualElement#layout-divider-solid-horizontal | flex-grow | 0 | "0" |  |  |
| PASS | values | VisualElement#layout-divider-solid-horizontal | flex-shrink | 1 | "1" |  |  |
| PASS | values | VisualElement#layout-divider-solid-horizontal | flex-direction | "Column" | "column" |  |  |
| PASS | values | SIText#IndividualTrainingTitle | color | "#B7B7B9" | "#B7B7B9" |  |  |
| N/A | values | SIText#IndividualTrainingTitle | background-color | "#00000000" | null |  | the render declares no background-color here |
| PASS | values | SIText#IndividualTrainingTitle | font-size | 12 | "12px" |  |  |
| PASS | values | SIText#IndividualTrainingTitle | flex-grow | 0 | "0" |  |  |
| PASS | values | SIText#IndividualTrainingTitle | flex-shrink | 1 | "1" |  |  |
| PASS | values | SIText#IndividualTrainingTitle | flex-direction | "Column" | "column" |  |  |
| N/A | values | VisualElement#IndividualTraining | color | "#EBEBEB" | null |  | the render declares no color here |
| N/A | values | VisualElement#IndividualTraining | background-color | "#00000000" | null |  | the render declares no background-color here |
| N/A | values | VisualElement#IndividualTraining | font-size | 14 | null |  | the render declares no font-size here |
| PASS | values | VisualElement#IndividualTraining | flex-grow | 0 | "0" |  |  |
| PASS | values | VisualElement#IndividualTraining | flex-shrink | 1 | "1" |  |  |
| PASS | values | VisualElement#IndividualTraining | flex-direction | "Row" | "row" |  |  |
| N/A | values | VisualElement#Improvements | color | "#EBEBEB" | null |  | the render declares no color here |
| N/A | values | VisualElement#Improvements | background-color | "#00000000" | null |  | the render declares no background-color here |
| N/A | values | VisualElement#Improvements | font-size | 14 | null |  | the render declares no font-size here |
| PASS | values | VisualElement#Improvements | flex-grow | 1 | "1" |  |  |
| PASS | values | VisualElement#Improvements | flex-shrink | 1 | "1" |  |  |
| PASS | values | VisualElement#Improvements | flex-direction | "Column" | "column" |  |  |
| N/A | values | VisualElement#Stat | color | "#EBEBEB" | null |  | the render declares no color here |
| N/A | values | VisualElement#Stat | background-color | "#00000000" | null |  | the render declares no background-color here |
| N/A | values | VisualElement#Stat | font-size | 14 | null |  | the render declares no font-size here |
| PASS | values | VisualElement#Stat | flex-grow | 1 | "1" |  |  |
| PASS | values | VisualElement#Stat | flex-shrink | 1 | "1" |  |  |
| PASS | values | VisualElement#Stat | flex-direction | "Row" | "row" |  |  |
| N/A | values | SIImage#Arrow | color | "#EBEBEB" | null |  | the render declares no color here |
| N/A | values | SIImage#Arrow | background-color | "#00000000" | null |  | the render declares no background-color here |
| N/A | values | SIImage#Arrow | font-size | 14 | null |  | the render declares no font-size here |
| PASS | values | SIImage#Arrow | flex-grow | 0 | "0" |  |  |
| FAIL | values | SIImage#Arrow | flex-shrink | 0 | "1" |  | cause (by rule): component-drawn image (SIImage, SIStyleSetter): its size and shrink come from component fields, not from style sheets |
| PASS | values | SIImage#Arrow | flex-direction | "Column" | "column" |  |  |
| PASS | values | SIText#Value | color | "#EBEBEB" | "#EBEBEB" |  |  |
| N/A | values | SIText#Value | background-color | "#00000000" | null |  | the render declares no background-color here |
| PASS | values | SIText#Value | font-size | 14 | "14px" |  |  |
| PASS | values | SIText#Value | flex-grow | 0 | "0" |  |  |
| PASS | values | SIText#Value | flex-shrink | 1 | "1" |  |  |
| PASS | values | SIText#Value | flex-direction | "Column" | "column" |  |  |
| PASS | values | SIText#Title | color | "#EBEBEB" | "#EBEBEB" |  |  |
| N/A | values | SIText#Title | background-color | "#00000000" | null |  | the render declares no background-color here |
| PASS | values | SIText#Title | font-size | 12 | "12px" |  |  |
| PASS | values | SIText#Title | flex-grow | 0 | "0" |  |  |
| PASS | values | SIText#Title | flex-shrink | 1 | "1" |  |  |
| PASS | values | SIText#Title | flex-direction | "Column" | "column" |  |  |
| N/A | values | VisualElement#Regressions | color | "#EBEBEB" | null |  | the render declares no color here |
| N/A | values | VisualElement#Regressions | background-color | "#00000000" | null |  | the render declares no background-color here |
| N/A | values | VisualElement#Regressions | font-size | 14 | null |  | the render declares no font-size here |
| PASS | values | VisualElement#Regressions | flex-grow | 1 | "1" |  |  |
| PASS | values | VisualElement#Regressions | flex-shrink | 1 | "1" |  |  |
| PASS | values | VisualElement#Regressions | flex-direction | "Column" | "column" |  |  |
| N/A | values | VisualElement#Stat | color | "#EBEBEB" | null |  | the render declares no color here |
| N/A | values | VisualElement#Stat | background-color | "#00000000" | null |  | the render declares no background-color here |
| N/A | values | VisualElement#Stat | font-size | 14 | null |  | the render declares no font-size here |
| PASS | values | VisualElement#Stat | flex-grow | 1 | "1" |  |  |
| PASS | values | VisualElement#Stat | flex-shrink | 1 | "1" |  |  |
| PASS | values | VisualElement#Stat | flex-direction | "Row" | "row" |  |  |
| N/A | values | SIImage#Arrow | color | "#EBEBEB" | null |  | the render declares no color here |
| N/A | values | SIImage#Arrow | background-color | "#00000000" | null |  | the render declares no background-color here |
| N/A | values | SIImage#Arrow | font-size | 14 | null |  | the render declares no font-size here |
| PASS | values | SIImage#Arrow | flex-grow | 0 | "0" |  |  |
| FAIL | values | SIImage#Arrow | flex-shrink | 0 | "1" |  | cause (by rule): component-drawn image (SIImage, SIStyleSetter): its size and shrink come from component fields, not from style sheets |
| PASS | values | SIImage#Arrow | flex-direction | "Column" | "column" |  |  |
| PASS | values | SIText#Value | color | "#EBEBEB" | "#EBEBEB" |  |  |
| N/A | values | SIText#Value | background-color | "#00000000" | null |  | the render declares no background-color here |
| PASS | values | SIText#Value | font-size | 14 | "14px" |  |  |
| PASS | values | SIText#Value | flex-grow | 0 | "0" |  |  |
| PASS | values | SIText#Value | flex-shrink | 1 | "1" |  |  |
| PASS | values | SIText#Value | flex-direction | "Column" | "column" |  |  |
| PASS | values | SIText#Title | color | "#EBEBEB" | "#EBEBEB" |  |  |
| N/A | values | SIText#Title | background-color | "#00000000" | null |  | the render declares no background-color here |
| PASS | values | SIText#Title | font-size | 12 | "12px" |  |  |
| PASS | values | SIText#Title | flex-grow | 0 | "0" |  |  |
| PASS | values | SIText#Title | flex-shrink | 1 | "1" |  |  |
| PASS | values | SIText#Title | flex-direction | "Column" | "column" |  |  |

## tiles-large

| Verdict | Check | Element | Property | Expected | Got | Delta | Note / cause |
|---|---|---|---|---|---|---|---|
| PASS | vanilla-pitch-left | TeamInstructionsPitch left of TeamInstructionsBlock | x (vanilla) | true | true |  | px left: TeamInstructionsPitch=0 TeamInstructionsBlock=492 |
| PASS | skin-instructions-left | TeamInstructionsBlock left of TeamInstructionsPitch | x (skin) | true | true |  | px left: TeamInstructionsBlock=0 TeamInstructionsPitch=820 |
| PASS | skin-instructions-left | TeamInstructionsPitch left of TeamInstructionsBlock | x (skin) | false | false |  | px left: TeamInstructionsPitch=820 TeamInstructionsBlock=0 |

## tiles-standard

| Verdict | Check | Element | Property | Expected | Got | Delta | Note / cause |
|---|---|---|---|---|---|---|---|
| PASS | vanilla-pitch-left | TeamInstructionsPitch left of TeamInstructionsBlock | x (vanilla) | true | true |  | px left: TeamInstructionsPitch=0 TeamInstructionsBlock=492 |
| PASS | skin-instructions-left | TeamInstructionsBlock left of TeamInstructionsPitch | x (skin) | true | true |  | px left: TeamInstructionsBlock=0 TeamInstructionsPitch=492 |
| PASS | skin-instructions-left | TeamInstructionsPitch left of TeamInstructionsBlock | x (skin) | false | false |  | px left: TeamInstructionsPitch=492 TeamInstructionsBlock=0 |
