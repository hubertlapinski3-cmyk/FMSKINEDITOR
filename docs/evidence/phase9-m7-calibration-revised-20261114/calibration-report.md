# Render calibration report (published, revised)

**Status: published, build 27.0.1.2503222, revised after the 1.0.0 review (this is a re-run of the calibration; the shipped 1.0.0 report is `calibration-report-1.0.0.md`). Not a draft.** Phase 9 M7 closed on the first version of this report. Read these first:

1. **Failure causes: each failing row was examined individually, and the examination is published row by row** (section "The failures, examined row by row"). Each of the 80 failing rows: 38 origin failures, 42 displaced by an origin listed beside them; 62 causes rest on a measured capture fact, 10 on magnitude only, 8 are UNEXPLAINED. The 1.0.0 labels came from fixture-wide rules (one label per row type, list order deciding when two fitted, 78 rows labelled, none unexplained); they disagree with the examination on 34 rows and both labels are kept. The examiner wrote the rules; no second person checked. Of the 38 origin rows, 1 name a class of cause without predicting the size of the gap.
2. **Coverage is published by row class, and the pass count is not a headline** (table below). Many passes are flex rows at Yoga's initial value, which the render supplies when it declares nothing; the same condition is N/A for colour and font-size. tile-loans and tile-loans-c2-dump are one tile counted twice.
3. **Delivered text pairing.** Captured text is paired with the drawn text nodes by the structural template path (`render/delivered.py`): 16 of 24 text nodes paired on the five tiles, 38 captured texts with no render node. Measured against the layout's sample text on the same fixtures it changed ONE row (a Tactics `CellText` box now passes, 66.9 against 67.4 wide). The wiring is correct and cheap but not the improvement hoped for.
4. **State findings come from the I3 session (Session G)**, hover, press, focus and selection read by hand on the baseline inspector with the owner at the PC; observation and interpretation are separate fields on each row, each interpretation marked observed, derived or inferred. The render applies NO runtime state. Measured: label colour #FFFFFF under the pointer, rest #EBEBEB; label mask 0; ancestors 2. Not measured: why. The prediction of the conditional row assumes the label is hovered, which the mask did not show. Rows as read, published beside it whatever their verdict: with the game's applied sheets only FAIL (state rule .nav-on-light .navigation-tab-portal-default-active-false:hover .portal-text); with the recorded run-time sheet added PASS (state rule .nav-on-light .navigation-tab-portal-default-active-false:hover .portal-text). The recorded run-time sheet holds an ancestor-hover rule, .nav-on-light .navigation-tab-portal-default-active-false:hover .portal-text, whose ancestor MainNav is in the capture: under the masks as read it yields the observed colour, so the label's own hover is not needed to explain it. The mask is not shown to be stale (no repeated reads were taken), inheritance was not tested, and the mechanism is unverified: the pattern was seen once (the Loans tile title gave no second point: its colour did not change). 
5. **Grid placement is scoped** to what was measured, with a held-out test: see "Grid placement: what it was measured on".

**Coverage: what the pass count is made of.** Of 1198 slots, 763 were compared (pass or fail) and 435 were not (N/A), reasons below. There is no single headline rate: read the classes.

| Row class | Pass | Fail | N/A |
|---|---|---|---|
| geometry | 106 | 67 | 18 |
| colour | 29 | 5 | 278 |
| font-size | 21 | 0 | 135 |
| flex | 463 | 5 | 0 |
| rule winner | 4 | 0 | 0 |
| state | 23 | 3 | 4 |
| screen hosts | 28 | 0 | 0 |
| tile order | 6 | 0 | 0 |
| table header | 3 | 0 | 0 |

Geometry: 106 of 173 compared rows pass, of which 54 are the stage box (the first node of the capture, taken from it) and 52 are other boxes. Colour and font-size: 50 of 55 compared rows pass. Flex: 463 of 468 rows pass; 324 of them have the value supplied by default because the render declared nothing (the same condition is N/A for colour and font-size), and 357 pass with a value equal to Yoga's initial value whether declared or supplied. Passes by value source: 189 declared, 324 default.

| Fixture | geometry | colour | font-size | flex | rule winner | state | screen hosts | tile order | table header |
|---|---|---|---|---|---|---|---|---|---|
| c3-table-header | - | - | - | - | - | - | - | - | 3 / 0 / 0 |
| p6-magenta-reload-skin | - | - | - | - | 2 / 0 / 0 | - | - | - | - |
| phase3-red-pitch | - | - | - | - | 2 / 0 / 0 | - | - | - | - |
| screen-squad-large-1600 | - | - | - | - | - | - | 5 / 0 / 0 | - | - |
| screen-squad-large-1680 | - | - | - | - | - | - | 5 / 0 / 0 | - | - |
| screen-squad-large-2500 | - | - | - | - | - | - | 5 / 0 / 0 | - | - |
| screen-squad-small | - | - | - | - | - | - | 5 / 0 / 0 | - | - |
| screen-squad-standard | - | - | - | - | - | - | 5 / 0 / 0 | - | - |
| screen-team-instructions-large | - | - | - | - | - | - | 3 / 0 / 0 | - | - |
| state-i3-session-g | - | - | - | - | - | 22 / 3 / 4 | - | - | - |
| tile-atmosphere | 16 / 3 / 1 | 2 / 2 / 34 | 3 / 0 / 16 | 57 / 0 / 0 | - | - | - | - | - |
| tile-loans | 16 / 3 / 0 | 2 / 1 / 35 | 2 / 0 / 17 | 57 / 0 / 0 | - | 1 / 0 / 0 | - | - | - |
| tile-loans-c2-dump | 16 / 1 / 2 | - | - | - | - | - | - | - | - |
| tile-medical-centre | 26 / 7 / 13 | 4 / 1 / 61 | 3 / 0 / 30 | 99 / 0 / 0 | - | - | - | - | - |
| tile-tactics | 18 / 33 / 1 | 12 / 0 / 90 | 6 / 0 / 45 | 150 / 3 / 0 | - | - | - | - | - |
| tile-training | 14 / 20 / 1 | 9 / 1 / 58 | 7 / 0 / 27 | 100 / 2 / 0 | - | - | - | - | - |
| tiles-large | - | - | - | - | - | - | - | 3 / 0 / 0 | - |
| tiles-standard | - | - | - | - | - | - | - | 3 / 0 / 0 | - |

(cells are pass / fail / N/A)

**N/A by reason:** no-declaration-live-initial-or-inherited: 415; descendant-of-hidden-switch-branch: 13; live-element-absent-or-not-captured: 5; no-declaration-parent-not-in-dump: 1; not-measured-live: 1. No-declaration rows whose live value is not the initial or inherited one: 0.

**Rows never emitted** (the runners skip them, they are in no verdict): boxes: root of a hidden switch branch (never emitted): 3; values: drawn node with no live partner (every property skipped): 114. Emitted plus skipped equals render nodes times properties in every fixture: yes.

**Live-side coverage** (dump elements paired with a render node): tile-atmosphere 19 of 48; tile-loans 19 of 343; tile-loans-c2-dump 17 of 32; tile-medical-centre 33 of 159; tile-tactics 51 of 242; tile-training 34 of 762. Captured delivered texts with no render node: 38.

**Duplicates, counted twice:** tile-loans and tile-loans-c2-dump are one tile (one tile measured twice (the c2 inspector dump and the squad capture); both are kept and both are counted in every total; deduplicating would change the headline totals and needs the owner's decision). The club colour #17223F is counted in 4 FAIL rows (three tiles and the state fixture's rest row). Nothing was deduplicated.


Tolerance: box x, y, width, height within 8 px or 5 percent of the measured size, whichever is tighter; colours, font sizes and flex values exactly equal. Every row is published: PASS, FAIL, or N/A (nothing to compare). Nothing is filtered, averaged or re-toleranced.

**Totals: 683 pass, 80 fail, 435 n/a.**

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
| state-i3-session-g | 22 | 3 | 4 | I3 Session G, manual hover/press/select holds on the baseline plugin 0.2.2 (AllowActions false), 2026-11-14; replies saved as g-*.json in workspace/notes/ui-dumps/i3g-20261114; log docs/evidence/phase9-i3-session-G-20261114.md. Predictions come from the game's own :pseudo rules (Cascade.state_declarations); the render itself still applies no state |
| tile-atmosphere | 78 | 5 | 51 | capture styles-e1-squad-bindings-20261114-115217.ndjson, host Atmosphere |
| tile-loans | 78 | 4 | 52 | capture styles-e1-squad-bindings-20261114-115217.ndjson, host Loans |
| tile-loans-c2-dump | 16 | 1 | 2 | inspector fm_dump_tree of the Loans tile, c2 session 2026-11-13 (Small + Larger text): the M0 spike's reference |
| tile-medical-centre | 132 | 8 | 104 | capture styles-e1-squad-bindings-20261114-115217.ndjson, host MedicalCentre |
| tile-tactics | 186 | 36 | 136 | capture styles-e1-squad-bindings-20261114-115217.ndjson, host Tactics |
| tile-training | 130 | 23 | 86 | capture styles-e1-squad-bindings-20261114-115217.ndjson, host Training |
| tiles-large | 3 | 0 | 0 | p7-tile-test (the owner's project, stored placement edits) and the tile-1/tile-2 screenshots: instructions left, pitch right at Small and Large in game. Only the left/right relation is checked: the absolute x of those screenshots (40 and 1274 / 865) was taken on another panel size. |
| tiles-standard | 3 | 0 | 0 | p7-tile-test (the owner's project, stored placement edits) and the tile-1/tile-2 screenshots: instructions left, pitch right at Small and Large in game. Only the left/right relation is checked: the absolute x of those screenshots (40 and 1274 / 865) was taken on another panel size. |

## The failures, examined row by row

Each of the 80 failing rows was examined individually (pairing, the x, y, w, h split against each tolerance, the parent's and the preceding sibling's displacement, and for origins a mechanism with one independent capture fact). 38 are origin failures; 42 are displaced by an origin listed beside them. 62 causes rest on a measured capture fact, 10 on magnitude only, 8 are unexplained. The earlier rule label disagreed on 34 rows; both are kept. The examiner wrote the rules; no second person checked.

Of the origin rows graded measured fact, 1 name a class of cause without predicting the size of the gap (the pitch is code-built; the height deficit of 41 px is not derived). 5 rows have a primary cause and at least one further origin component with no mechanism (listed in the JSON as unexplained_components); 8 rows were flagged at the pairing step (a live partner that is invisible, or text that differs). The 1.0.0 labels came from fixture-wide rules: 33 rows satisfied two of them, so list order decided the label.

| Root cause | Rows | Origin rows | Displaced rows |
|---|---|---|---|
| a widget the game fills in code: the live element has children in the capture and no template source, the layout holds none (its size is set by that content; the size itself is not predicted) | 18 | 1 | 17 |
| a class the game sets in code (absent from the layout) carries the value: applying the live class set through the game's own sheets reproduces it | 18 | 10 | 8 |
| a list filled at run time is drawn empty: the game builds its rows in code, the render has none, so it collapses to 0 by 0 | 12 | 1 | 11 |
| UNEXPLAINED (no supporting capture fact) | 8 | 6 | 2 |
| elements the game builds in code sit between this node and its layout parent (Unity ScrollView internals), changing how the node is laid out | 6 | 3 | 3 |
| same text string and font size, the stand-in font gives another width | 6 | 6 | 0 |
| a colour painted by a run-time sheet (empty name, negative instance id) that the render does not apply | 4 | 4 | 0 |
| display:none set in code (inline in the capture, in no layout or sheet): the live element is 0 by 0, the render draws it | 3 | 3 | 0 |
| a recorded run-time sheet declares the value (assigned by a listed per-row override: the twin variant that includes that sheet passes) | 2 | 2 | 0 |
| a sub-pixel offset on an element whose tolerance (5 percent of its size) is under half a pixel: the same offset the passing rows of the fixture carry | 2 | 1 | 1 |
| the capture was taken while the element was in a pseudo-state (mask bit set): the game's own :pseudo rule declares exactly the live value | 1 | 1 | 0 |

Confusion table, 1.0.0 label (rows) by the examined cause (columns): both labels are kept on every row.

| 1.0.0 label | UNEXPLAINED | code-built-children | code-built-wrapper | empty-code-list | inline-display-none | runtime-class | runtime-sheet-colour | stand-in-font | state-captured | sub-pixel-tolerance |
|---|---|---|---|---|---|---|---|---|---|---|
| bound text, scroller or list width | 3 | 0 | 4 | 0 | 2 | 0 | 0 | 3 | 0 | 0 |
| code-built content: the Training tile | 1 | 0 | 2 | 12 | 1 | 3 | 0 | 1 | 0 | 0 |
| code-built content: the tactics pitch | 3 | 18 | 0 | 0 | 0 | 10 | 0 | 2 | 0 | 0 |
| code-built or binding-driven colour | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 1 | 0 |
| component-drawn image | 0 | 0 | 0 | 0 | 0 | 5 | 0 | 0 | 0 | 0 |
| run-time club-colour sheet | 0 | 0 | 0 | 0 | 0 | 0 | 4 | 0 | 0 | 0 |
| sub-pixel offset | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 2 |

| Row id | Status | Origin id | Examined cause | Grade | Evidence | 1.0.0 label |
|---|---|---|---|---|---|---|
| state-i3-session-g|loans-tile-hover|SIButton#layout-tile-interaction-button|background-color (rest)|- | origin | itself | runtime-sheet-colour | magnitude only | {"live_value_in_runtime_sheet_samples": true, "note": "the sheet's sampled rules paint this value elsewhere; this element's own rule is not in the 80-rule sampl | run-time club-colour sheet |
| state-i3-session-g|nav-tab-label-as-read|SIText#text|color (rest)|- | origin | itself | runtime-sheet-declares-value | measured fact | variant row nav-tab-label-as-read-runtime-sheet, color (rest): PASS; the capture's run-time sheet sample holds .nav-on-light .navigation-tab-portal-default-active-false .portal-text {color: var(--global-text-primary)} | - |
| state-i3-session-g|nav-tab-label-as-read|SIText#text|color (enabled)|- | origin | itself | runtime-sheet-declares-value | measured fact | variant row nav-tab-label-as-read-runtime-sheet, color (enabled): PASS; rule .nav-on-light .navigation-tab-portal-default-active-false:hover .portal-text in the capture's run-time sheet sample | - |
| tile-atmosphere|geometry|AutoScroller#|box|P4/0/4/0/0/0/0/0/0/0/1/0/0/0/0/0/0/0/0/0/0/0/0/0/0/1/1/0 | inherited | tile-atmosphere|geometry|SIText#title-text|box|P4/0/4/0/0/0/0/0/0/0/1/0/0/0/0/0/0/0/0/0/0/0/0/0/0/1/1/0/0/0/0/0, tile-atmosphere|geometry|SIVisible#|box|P4/0/4/0/0/0/0/0/0/0/1/0/0/0/0/0/0/0/0/0/0/0/0/0/0/1/1/0/0/0/0/1 | code-built-wrapper | measured fact | displaced by tile-atmosphere|geometry|SIText#title-text|box|P4/0/4/0/0/0/0/0/0/0/1/0/0/0/0/0/0/0/0/0/0/0/0/0/0/1/1/0/0/0/0/0, tile-atmosphere|geometry|SIVisible#|box|P4/0/4/0/0/0/0/0/0/0/1/0/0/0/0/0/0/0/0/0/0/0/0/0/0/1/1/0/0/0/0/1 | bound text, scroller or list width |
| tile-atmosphere|geometry|SIText#title-text|box|P4/0/4/0/0/0/0/0/0/0/1/0/0/0/0/0/0/0/0/0/0/0/0/0/0/1/1/0/0/0/0/0 | origin | itself | code-built-wrapper | measured fact | {"wrappers_in_capture_not_in_layout": [{"name": "unity-content-and-vertical-scroll-container", "classes": ["unity-scroll-view__content-and-vertical-scroll-conta | bound text, scroller or list width |
| tile-atmosphere|geometry|SIVisible#|box|P4/0/4/0/0/0/0/0/0/0/1/0/0/0/0/0/0/0/0/0/0/0/0/0/0/1/1/0/0/0/0/1 | origin | itself | inline-display-none | measured fact | {"inline": {"display": "None"}, "live_size": [0, 0], "render_size": [287.5, 16], "magnitude_predicted": true} | bound text, scroller or list width |
| tile-atmosphere|values|SIButton#layout-tile-interaction-button|background-color|P4/0/4/0/0/0/0/0/0/0/1/0/0/0/0/0/0/0/0/0/0/0/0/0/0 | origin | itself | runtime-sheet-colour | magnitude only | {"live_value_in_runtime_sheet_samples": true, "note": "the sheet's sampled rules paint this value elsewhere; this element's own rule is not in the 80-rule sampl | run-time club-colour sheet |
| tile-atmosphere|values|SIText#state_text|color|P4/0/4/0/0/0/0/0/0/0/1/0/0/0/0/0/0/0/0/0/0/0/0/0/0/2/0/0 | origin | itself | UNEXPLAINED | - |  | code-built or binding-driven colour |
| tile-loans|geometry|AutoScroller#auto-scroller|box|P4/0/4/0/0/0/0/0/0/0/1/0/0/0/0/7/0/0/0/0/0/0/0/0/0/0/1/1 | inherited | tile-loans|geometry|SIText#title-text|box|P4/0/4/0/0/0/0/0/0/0/1/0/0/0/0/7/0/0/0/0/0/0/0/0/0/0/1/1/0/0/0/0 | UNEXPLAINED | - | displaced by tile-loans|geometry|SIText#title-text|box|P4/0/4/0/0/0/0/0/0/0/1/0/0/0/0/7/0/0/0/0/0/0/0/0/0/0/1/1/0/0/0/0 | bound text, scroller or list width |
| tile-loans|geometry|SIText#title-text|box|P4/0/4/0/0/0/0/0/0/0/1/0/0/0/0/7/0/0/0/0/0/0/0/0/0/0/1/1/0/0/0/0 | origin | itself | UNEXPLAINED | - |  | bound text, scroller or list width |
| tile-loans|geometry|SIText#title-text|box|P4/0/4/0/0/0/0/0/0/0/1/0/0/0/0/7/0/0/0/0/0/0/0/0/0/0/2/0/0/0/0 | origin | itself | stand-in-font | magnitude only | {"same_text": "5 Players", "live_font_size": 16, "residual": -11.7, "live": 82, "magnitude_predicted": false} | bound text, scroller or list width |
| tile-loans|values|SIButton#layout-tile-interaction-button|background-color|P4/0/4/0/0/0/0/0/0/0/1/0/0/0/0/7/0/0/0/0/0/0/0/0/0/0 | origin | itself | state-captured | measured fact | {"mask": 2, "states": ["enabled", "hover"], "state_rule": ".layout-tile-interaction-button:hover", "declares": "#2E3138", "magnitude_predicted": true} | code-built or binding-driven colour |
| tile-loans-c2-dump|geometry|AutoScroller#auto-scroller|box|P3/0/4/0/0/0/0/0/0/0/1/0/0/0/0/7/0/0/0/0/0/0/0/0/0/0/1/1 | origin | itself | UNEXPLAINED | - |  | bound text, scroller or list width |
| tile-medical-centre|geometry|AutoScroller#|box|P4/0/4/0/0/0/0/0/0/0/1/0/0/0/0/6/0/0/0/0/0/0/0/0/0/0/1/1/0 | inherited | tile-medical-centre|geometry|SIText#title-text|box|P4/0/4/0/0/0/0/0/0/0/1/0/0/0/0/6/0/0/0/0/0/0/0/0/0/0/1/1/0/0/0/0/0, tile-medical-centre|geometry|SIVisible#|box|P4/0/4/0/0/0/0/0/0/0/1/0/0/0/0/6/0/0/0/0/0/0/0/0/0/0/1/1/0/0/0/0/1 | code-built-wrapper | measured fact | displaced by tile-medical-centre|geometry|SIText#title-text|box|P4/0/4/0/0/0/0/0/0/0/1/0/0/0/0/6/0/0/0/0/0/0/0/0/0/0/1/1/0/0/0/0/0, tile-medical-centre|geometry|SIVisible#|box|P4/0/4/0/0/0/0/0/0/0/1/0/0/0/0/6/0/0/0/0/0/0/0/0/0/0/1/1/0/0/0/0/1 | bound text, scroller or list width |
| tile-medical-centre|geometry|SIText#title-text|box|P4/0/4/0/0/0/0/0/0/0/1/0/0/0/0/6/0/0/0/0/0/0/0/0/0/0/1/1/0/0/0/0/0 | origin | itself | code-built-wrapper | measured fact | {"wrappers_in_capture_not_in_layout": [{"name": "unity-content-and-vertical-scroll-container", "classes": ["unity-scroll-view__content-and-vertical-scroll-conta | bound text, scroller or list width |
| tile-medical-centre|geometry|SIVisible#|box|P4/0/4/0/0/0/0/0/0/0/1/0/0/0/0/6/0/0/0/0/0/0/0/0/0/0/1/1/0/0/0/0/1 | origin | itself | inline-display-none | measured fact | {"inline": {"display": "None"}, "live_size": [0, 0], "render_size": [287.5, 16], "magnitude_predicted": true} | bound text, scroller or list width |
| tile-medical-centre|geometry|SIText#text|box|P4/0/4/0/0/0/0/0/0/0/1/0/0/0/0/6/0/0/0/0/0/0/0/0/0/0/2/0/0/0/0/0/1/0/0 | origin | itself | stand-in-font | magnitude only | {"same_text": "4 players injured", "live_font_size": 16, "residual": -20.3, "live": 147.5, "magnitude_predicted": false} | bound text, scroller or list width |
| tile-medical-centre|geometry|TemplateContainer#layout-divider-solid-horizontal|box|P4/0/4/0/0/0/0/0/0/0/1/0/0/0/0/6/0/0/0/0/0/0/0/0/0/0/2/0/0/0/1/0 | inherited | tile-medical-centre|geometry|VisualElement#layout-divider-solid-horizontal|box|P4/0/4/0/0/0/0/0/0/0/1/0/0/0/0/6/0/0/0/0/0/0/0/0/0/0/2/0/0/0/1/0/0 | sub-pixel-tolerance | measured fact | displaced by tile-medical-centre|geometry|VisualElement#layout-divider-solid-horizontal|box|P4/0/4/0/0/0/0/0/0/0/1/0/0/0/0/6/0/0/0/0/0/0/0/0/0/0/2/0/0/0/1/0/0 | sub-pixel offset |
| tile-medical-centre|geometry|VisualElement#layout-divider-solid-horizontal|box|P4/0/4/0/0/0/0/0/0/0/1/0/0/0/0/6/0/0/0/0/0/0/0/0/0/0/2/0/0/0/1/0/0 | origin | itself | sub-pixel-tolerance | measured fact | {"tolerance": 0.05, "delta": -0.4, "median_delta_of_passing_rows": 0, "magnitude_predicted": true} | sub-pixel offset |
| tile-medical-centre|geometry|SIText#text|box|P4/0/4/0/0/0/0/0/0/0/1/0/0/0/0/6/0/0/0/0/0/0/0/0/0/0/2/0/0/0/1/1/1 | origin | itself | stand-in-font | magnitude only | {"same_text": "8 players at risk of injury", "live_font_size": 12, "residual": -14.2, "live": 143.6, "magnitude_predicted": false} | bound text, scroller or list width |
| tile-medical-centre|values|SIButton#layout-tile-interaction-button|background-color|P4/0/4/0/0/0/0/0/0/0/1/0/0/0/0/6/0/0/0/0/0/0/0/0/0/0 | origin | itself | runtime-sheet-colour | magnitude only | {"live_value_in_runtime_sheet_samples": true, "note": "the sheet's sampled rules paint this value elsewhere; this element's own rule is not in the 80-rule sampl | run-time club-colour sheet |
| tile-tactics|geometry|AutoScroller#auto-scroller|box|P4/0/4/0/0/0/0/0/0/0/1/0/0/0/0/1/0/0/0/0/0/0/0/0/0/0/0/0/1/1 | inherited | tile-tactics|geometry|SIText#title-text|box|P4/0/4/0/0/0/0/0/0/0/1/0/0/0/0/1/0/0/0/0/0/0/0/0/0/0/0/0/1/1/0/0/0/0 | UNEXPLAINED | - | displaced by tile-tactics|geometry|SIText#title-text|box|P4/0/4/0/0/0/0/0/0/0/1/0/0/0/0/1/0/0/0/0/0/0/0/0/0/0/0/0/1/1/0/0/0/0 | code-built content: the tactics pitch |
| tile-tactics|geometry|SIText#title-text|box|P4/0/4/0/0/0/0/0/0/0/1/0/0/0/0/1/0/0/0/0/0/0/0/0/0/0/0/0/1/1/0/0/0/0 | origin | itself | UNEXPLAINED | - |  | code-built content: the tactics pitch |
| tile-tactics|geometry|VisualElement#TacticsPitch-UNPACKED|box|P4/0/4/0/0/0/0/0/0/0/1/0/0/0/0/1/0/0/0/0/0/0/0/0/0/0/0/0/2/1/0 | inherited | tile-tactics|geometry|FMTacticsPanel#|box|P4/0/4/0/0/0/0/0/0/0/1/0/0/0/0/1/0/0/0/0/0/0/0/0/0/0/0/0/2/1/0/0/0/0/2 | code-built-children | measured fact | displaced by tile-tactics|geometry|FMTacticsPanel#|box|P4/0/4/0/0/0/0/0/0/0/1/0/0/0/0/1/0/0/0/0/0/0/0/0/0/0/0/0/2/1/0/0/0/0/2 | code-built content: the tactics pitch |
| tile-tactics|geometry|BindingExpect#pitch-expect|box|P4/0/4/0/0/0/0/0/0/0/1/0/0/0/0/1/0/0/0/0/0/0/0/0/0/0/0/0/2/1/0/0 | inherited | tile-tactics|geometry|FMTacticsPanel#|box|P4/0/4/0/0/0/0/0/0/0/1/0/0/0/0/1/0/0/0/0/0/0/0/0/0/0/0/0/2/1/0/0/0/0/2 | code-built-children | measured fact | displaced by tile-tactics|geometry|FMTacticsPanel#|box|P4/0/4/0/0/0/0/0/0/0/1/0/0/0/0/1/0/0/0/0/0/0/0/0/0/0/0/0/2/1/0/0/0/0/2 | code-built content: the tactics pitch |
| tile-tactics|geometry|BindingRemapper#pitch-remapper|box|P4/0/4/0/0/0/0/0/0/0/1/0/0/0/0/1/0/0/0/0/0/0/0/0/0/0/0/0/2/1/0/0/0 | inherited | tile-tactics|geometry|FMTacticsPanel#|box|P4/0/4/0/0/0/0/0/0/0/1/0/0/0/0/1/0/0/0/0/0/0/0/0/0/0/0/0/2/1/0/0/0/0/2 | code-built-children | measured fact | displaced by tile-tactics|geometry|FMTacticsPanel#|box|P4/0/4/0/0/0/0/0/0/0/1/0/0/0/0/1/0/0/0/0/0/0/0/0/0/0/0/0/2/1/0/0/0/0/2 | code-built content: the tactics pitch |
| tile-tactics|geometry|BindingVariables#pitch-variables|box|P4/0/4/0/0/0/0/0/0/0/1/0/0/0/0/1/0/0/0/0/0/0/0/0/0/0/0/0/2/1/0/0/0/0 | inherited | tile-tactics|geometry|FMTacticsPanel#|box|P4/0/4/0/0/0/0/0/0/0/1/0/0/0/0/1/0/0/0/0/0/0/0/0/0/0/0/0/2/1/0/0/0/0/2 | code-built-children | measured fact | displaced by tile-tactics|geometry|FMTacticsPanel#|box|P4/0/4/0/0/0/0/0/0/0/1/0/0/0/0/1/0/0/0/0/0/0/0/0/0/0/0/0/2/1/0/0/0/0/2 | code-built content: the tactics pitch |
| tile-tactics|geometry|TemplateContainer#SetPiecesCell|box|P4/0/4/0/0/0/0/0/0/0/1/0/0/0/0/1/0/0/0/0/0/0/0/0/0/0/0/0/2/1/0/0/0/0/0/0 | inherited | tile-tactics|geometry|SIStyleSetter#IconStyleSetter|box|P4/0/4/0/0/0/0/0/0/0/1/0/0/0/0/1/0/0/0/0/0/0/0/0/0/0/0/0/2/1/0/0/0/0/0/0/0/0 | runtime-class | measured fact | displaced by tile-tactics|geometry|SIStyleSetter#IconStyleSetter|box|P4/0/4/0/0/0/0/0/0/0/1/0/0/0/0/1/0/0/0/0/0/0/0/0/0/0/0/0/2/1/0/0/0/0/0/0/0/0 | code-built content: the tactics pitch |
| tile-tactics|geometry|SIButton#OpenCardButton|box|P4/0/4/0/0/0/0/0/0/0/1/0/0/0/0/1/0/0/0/0/0/0/0/0/0/0/0/0/2/1/0/0/0/0/0/0/0 | inherited | tile-tactics|geometry|SIStyleSetter#IconStyleSetter|box|P4/0/4/0/0/0/0/0/0/0/1/0/0/0/0/1/0/0/0/0/0/0/0/0/0/0/0/0/2/1/0/0/0/0/0/0/0/0 | runtime-class | measured fact | displaced by tile-tactics|geometry|SIStyleSetter#IconStyleSetter|box|P4/0/4/0/0/0/0/0/0/0/1/0/0/0/0/1/0/0/0/0/0/0/0/0/0/0/0/0/2/1/0/0/0/0/0/0/0/0 | code-built content: the tactics pitch |
| tile-tactics|geometry|SIStyleSetter#IconStyleSetter|box|P4/0/4/0/0/0/0/0/0/0/1/0/0/0/0/1/0/0/0/0/0/0/0/0/0/0/0/0/2/1/0/0/0/0/0/0/0/0 | origin | itself | runtime-class | measured fact | {"extra_live_classes": ["game-concepts-training-set-pieces_small"], "cascade_with_them": {"width": "16px", "height": "16px", "flex-shrink": "0"}, "predicted_px" | code-built content: the tactics pitch |
| tile-tactics|geometry|SIText#CellText|box|P4/0/4/0/0/0/0/0/0/0/1/0/0/0/0/1/0/0/0/0/0/0/0/0/0/0/0/0/2/1/0/0/0/0/0/0/0/1 | inherited | tile-tactics|geometry|SIStyleSetter#IconStyleSetter|box|P4/0/4/0/0/0/0/0/0/0/1/0/0/0/0/1/0/0/0/0/0/0/0/0/0/0/0/0/2/1/0/0/0/0/0/0/0/0 | runtime-class | measured fact | displaced by tile-tactics|geometry|SIStyleSetter#IconStyleSetter|box|P4/0/4/0/0/0/0/0/0/0/1/0/0/0/0/1/0/0/0/0/0/0/0/0/0/0/0/0/2/1/0/0/0/0/0/0/0/0 | code-built content: the tactics pitch |
| tile-tactics|geometry|TemplateContainer#PenaltiesCell|box|P4/0/4/0/0/0/0/0/0/0/1/0/0/0/0/1/0/0/0/0/0/0/0/0/0/0/0/0/2/1/0/0/0/0/0/1 | inherited | tile-tactics|geometry|SIStyleSetter#IconStyleSetter|box|P4/0/4/0/0/0/0/0/0/0/1/0/0/0/0/1/0/0/0/0/0/0/0/0/0/0/0/0/2/1/0/0/0/0/0/0/0/0, tile-tactics|geometry|SIStyleSetter#IconStyleSetter|box|P4/0/4/0/0/0/0/0/0/0/1/0/0/0/0/1/0/0/0/0/0/0/0/0/0/0/0/0/2/1/0/0/0/0/0/1/0/0, tile-tactics|geometry|SIStyleSetter#IconStyleSetter|box|P4/0/4/0/0/0/0/0/0/0/1/0/0/0/0/1/0/0/0/0/0/0/0/0/0/0/0/0/2/1/0/0/0/0/0/2/0/0, tile-tactics|geometry|SIText#CellText|box|P4/0/4/0/0/0/0/0/0/0/1/0/0/0/0/1/0/0/0/0/0/0/0/0/0/0/0/0/2/1/0/0/0/0/0/1/0/1 | runtime-class | measured fact | displaced by tile-tactics|geometry|SIStyleSetter#IconStyleSetter|box|P4/0/4/0/0/0/0/0/0/0/1/0/0/0/0/1/0/0/0/0/0/0/0/0/0/0/0/0/2/1/0/0/0/0/0/0/0/0, tile-tactics|geometry|SIStyleSetter#IconStyleSetter|box|P4/0/4/0/0/0/0/0/0/0/1/0/0/0/0/1/0/0/0/0/0/0/0/0/0/0/0/0/2/1/0/0/0/0/0/1/0/0, tile-tactics|geometry|SIStyleSetter#IconStyleSetter|box|P4/0/4/0/0/0/0/0/0/0/1/0/0/0/0/1/0/0/0/0/0/0/0/0/0/0/0/0/2/1/0/0/0/0/0/2/0/0, tile-tactics|geometry|SIText#CellText|box|P4/0/4/0/0/0/0/0/0/0/1/0/0/0/0/1/0/0/0/0/0/0/0/0/0/0/0/0/2/1/0/0/0/0/0/1/0/1 | code-built content: the tactics pitch |
| tile-tactics|geometry|SIButton#OpenCardButton|box|P4/0/4/0/0/0/0/0/0/0/1/0/0/0/0/1/0/0/0/0/0/0/0/0/0/0/0/0/2/1/0/0/0/0/0/1/0 | inherited | tile-tactics|geometry|SIStyleSetter#IconStyleSetter|box|P4/0/4/0/0/0/0/0/0/0/1/0/0/0/0/1/0/0/0/0/0/0/0/0/0/0/0/0/2/1/0/0/0/0/0/0/0/0, tile-tactics|geometry|SIStyleSetter#IconStyleSetter|box|P4/0/4/0/0/0/0/0/0/0/1/0/0/0/0/1/0/0/0/0/0/0/0/0/0/0/0/0/2/1/0/0/0/0/0/1/0/0, tile-tactics|geometry|SIStyleSetter#IconStyleSetter|box|P4/0/4/0/0/0/0/0/0/0/1/0/0/0/0/1/0/0/0/0/0/0/0/0/0/0/0/0/2/1/0/0/0/0/0/2/0/0, tile-tactics|geometry|SIText#CellText|box|P4/0/4/0/0/0/0/0/0/0/1/0/0/0/0/1/0/0/0/0/0/0/0/0/0/0/0/0/2/1/0/0/0/0/0/1/0/1 | runtime-class | measured fact | displaced by tile-tactics|geometry|SIStyleSetter#IconStyleSetter|box|P4/0/4/0/0/0/0/0/0/0/1/0/0/0/0/1/0/0/0/0/0/0/0/0/0/0/0/0/2/1/0/0/0/0/0/0/0/0, tile-tactics|geometry|SIStyleSetter#IconStyleSetter|box|P4/0/4/0/0/0/0/0/0/0/1/0/0/0/0/1/0/0/0/0/0/0/0/0/0/0/0/0/2/1/0/0/0/0/0/1/0/0, tile-tactics|geometry|SIStyleSetter#IconStyleSetter|box|P4/0/4/0/0/0/0/0/0/0/1/0/0/0/0/1/0/0/0/0/0/0/0/0/0/0/0/0/2/1/0/0/0/0/0/2/0/0, tile-tactics|geometry|SIText#CellText|box|P4/0/4/0/0/0/0/0/0/0/1/0/0/0/0/1/0/0/0/0/0/0/0/0/0/0/0/0/2/1/0/0/0/0/0/1/0/1 | code-built content: the tactics pitch |
| tile-tactics|geometry|SIStyleSetter#IconStyleSetter|box|P4/0/4/0/0/0/0/0/0/0/1/0/0/0/0/1/0/0/0/0/0/0/0/0/0/0/0/0/2/1/0/0/0/0/0/1/0/0 | origin | itself | runtime-class | measured fact | {"extra_live_classes": ["game-concepts-penalties_small"], "cascade_with_them": {"width": "16px", "height": "16px", "flex-shrink": "0"}, "predicted_px": 16.0, "l | code-built content: the tactics pitch |
| tile-tactics|geometry|SIText#CellText|box|P4/0/4/0/0/0/0/0/0/0/1/0/0/0/0/1/0/0/0/0/0/0/0/0/0/0/0/0/2/1/0/0/0/0/0/1/0/1 | origin | itself | stand-in-font | magnitude only | {"same_text": "Pens", "live_font_size": 14, "residual": 3.6, "live": 28.3, "magnitude_predicted": false} | code-built content: the tactics pitch |
| tile-tactics|geometry|TemplateContainer#OppositionInstructionsCell|box|P4/0/4/0/0/0/0/0/0/0/1/0/0/0/0/1/0/0/0/0/0/0/0/0/0/0/0/0/2/1/0/0/0/0/0/2 | inherited | tile-tactics|geometry|SIStyleSetter#IconStyleSetter|box|P4/0/4/0/0/0/0/0/0/0/1/0/0/0/0/1/0/0/0/0/0/0/0/0/0/0/0/0/2/1/0/0/0/0/0/0/0/0, tile-tactics|geometry|SIStyleSetter#IconStyleSetter|box|P4/0/4/0/0/0/0/0/0/0/1/0/0/0/0/1/0/0/0/0/0/0/0/0/0/0/0/0/2/1/0/0/0/0/0/1/0/0, tile-tactics|geometry|SIStyleSetter#IconStyleSetter|box|P4/0/4/0/0/0/0/0/0/0/1/0/0/0/0/1/0/0/0/0/0/0/0/0/0/0/0/0/2/1/0/0/0/0/0/2/0/0, tile-tactics|geometry|SIText#CellText|box|P4/0/4/0/0/0/0/0/0/0/1/0/0/0/0/1/0/0/0/0/0/0/0/0/0/0/0/0/2/1/0/0/0/0/0/1/0/1 | runtime-class | measured fact | displaced by tile-tactics|geometry|SIStyleSetter#IconStyleSetter|box|P4/0/4/0/0/0/0/0/0/0/1/0/0/0/0/1/0/0/0/0/0/0/0/0/0/0/0/0/2/1/0/0/0/0/0/0/0/0, tile-tactics|geometry|SIStyleSetter#IconStyleSetter|box|P4/0/4/0/0/0/0/0/0/0/1/0/0/0/0/1/0/0/0/0/0/0/0/0/0/0/0/0/2/1/0/0/0/0/0/1/0/0, tile-tactics|geometry|SIStyleSetter#IconStyleSetter|box|P4/0/4/0/0/0/0/0/0/0/1/0/0/0/0/1/0/0/0/0/0/0/0/0/0/0/0/0/2/1/0/0/0/0/0/2/0/0, tile-tactics|geometry|SIText#CellText|box|P4/0/4/0/0/0/0/0/0/0/1/0/0/0/0/1/0/0/0/0/0/0/0/0/0/0/0/0/2/1/0/0/0/0/0/1/0/1 | code-built content: the tactics pitch |
| tile-tactics|geometry|SIButton#OpenCardButton|box|P4/0/4/0/0/0/0/0/0/0/1/0/0/0/0/1/0/0/0/0/0/0/0/0/0/0/0/0/2/1/0/0/0/0/0/2/0 | inherited | tile-tactics|geometry|SIStyleSetter#IconStyleSetter|box|P4/0/4/0/0/0/0/0/0/0/1/0/0/0/0/1/0/0/0/0/0/0/0/0/0/0/0/0/2/1/0/0/0/0/0/0/0/0, tile-tactics|geometry|SIStyleSetter#IconStyleSetter|box|P4/0/4/0/0/0/0/0/0/0/1/0/0/0/0/1/0/0/0/0/0/0/0/0/0/0/0/0/2/1/0/0/0/0/0/1/0/0, tile-tactics|geometry|SIStyleSetter#IconStyleSetter|box|P4/0/4/0/0/0/0/0/0/0/1/0/0/0/0/1/0/0/0/0/0/0/0/0/0/0/0/0/2/1/0/0/0/0/0/2/0/0, tile-tactics|geometry|SIText#CellText|box|P4/0/4/0/0/0/0/0/0/0/1/0/0/0/0/1/0/0/0/0/0/0/0/0/0/0/0/0/2/1/0/0/0/0/0/1/0/1 | runtime-class | measured fact | displaced by tile-tactics|geometry|SIStyleSetter#IconStyleSetter|box|P4/0/4/0/0/0/0/0/0/0/1/0/0/0/0/1/0/0/0/0/0/0/0/0/0/0/0/0/2/1/0/0/0/0/0/0/0/0, tile-tactics|geometry|SIStyleSetter#IconStyleSetter|box|P4/0/4/0/0/0/0/0/0/0/1/0/0/0/0/1/0/0/0/0/0/0/0/0/0/0/0/0/2/1/0/0/0/0/0/1/0/0, tile-tactics|geometry|SIStyleSetter#IconStyleSetter|box|P4/0/4/0/0/0/0/0/0/0/1/0/0/0/0/1/0/0/0/0/0/0/0/0/0/0/0/0/2/1/0/0/0/0/0/2/0/0, tile-tactics|geometry|SIText#CellText|box|P4/0/4/0/0/0/0/0/0/0/1/0/0/0/0/1/0/0/0/0/0/0/0/0/0/0/0/0/2/1/0/0/0/0/0/1/0/1 | code-built content: the tactics pitch |
| tile-tactics|geometry|SIStyleSetter#IconStyleSetter|box|P4/0/4/0/0/0/0/0/0/0/1/0/0/0/0/1/0/0/0/0/0/0/0/0/0/0/0/0/2/1/0/0/0/0/0/2/0/0 | origin | itself | runtime-class | measured fact | {"extra_live_classes": ["game-concepts-opposition-instructions_small"], "cascade_with_them": {"width": "16px", "height": "16px", "flex-shrink": "0"}, "predicted | code-built content: the tactics pitch |
| tile-tactics|geometry|BindableSwitchElement#|box|P4/0/4/0/0/0/0/0/0/0/1/0/0/0/0/1/0/0/0/0/0/0/0/0/0/0/0/0/2/1/0/0/0/0/1 | inherited | tile-tactics|geometry|FMTacticsPanel#|box|P4/0/4/0/0/0/0/0/0/0/1/0/0/0/0/1/0/0/0/0/0/0/0/0/0/0/0/0/2/1/0/0/0/0/2 | code-built-children | measured fact | displaced by tile-tactics|geometry|FMTacticsPanel#|box|P4/0/4/0/0/0/0/0/0/0/1/0/0/0/0/1/0/0/0/0/0/0/0/0/0/0/0/0/2/1/0/0/0/0/2 | code-built content: the tactics pitch |
| tile-tactics|geometry|SIImage#|box|P4/0/4/0/0/0/0/0/0/0/1/0/0/0/0/1/0/0/0/0/0/0/0/0/0/0/0/0/2/1/0/0/0/0/1/0 | inherited | tile-tactics|geometry|FMTacticsPanel#|box|P4/0/4/0/0/0/0/0/0/0/1/0/0/0/0/1/0/0/0/0/0/0/0/0/0/0/0/0/2/1/0/0/0/0/2 | code-built-children | measured fact | displaced by tile-tactics|geometry|FMTacticsPanel#|box|P4/0/4/0/0/0/0/0/0/0/1/0/0/0/0/1/0/0/0/0/0/0/0/0/0/0/0/0/2/1/0/0/0/0/2 | code-built content: the tactics pitch |
| tile-tactics|geometry|FMTacticsPanel#|box|P4/0/4/0/0/0/0/0/0/0/1/0/0/0/0/1/0/0/0/0/0/0/0/0/0/0/0/0/2/1/0/0/0/0/2 | origin | itself | code-built-children | measured fact | {"live_children_in_capture": 162, "render_children": 0, "magnitude_predicted": false} | code-built content: the tactics pitch |
| tile-tactics|geometry|BindableSwitchElement#tactic-info-switch|box|P4/0/4/0/0/0/0/0/0/0/1/0/0/0/0/1/0/0/0/0/0/0/0/0/0/0/0/0/2/1/1 | inherited | tile-tactics|geometry|FMTacticsPanel#|box|P4/0/4/0/0/0/0/0/0/0/1/0/0/0/0/1/0/0/0/0/0/0/0/0/0/0/0/0/2/1/0/0/0/0/2 | code-built-children | measured fact | displaced by tile-tactics|geometry|FMTacticsPanel#|box|P4/0/4/0/0/0/0/0/0/0/1/0/0/0/0/1/0/0/0/0/0/0/0/0/0/0/0/0/2/1/0/0/0/0/2 | code-built content: the tactics pitch |
| tile-tactics|geometry|VisualElement#tactic-info-container|box|P4/0/4/0/0/0/0/0/0/0/1/0/0/0/0/1/0/0/0/0/0/0/0/0/0/0/0/0/2/1/1/0 | inherited | tile-tactics|geometry|FMTacticsPanel#|box|P4/0/4/0/0/0/0/0/0/0/1/0/0/0/0/1/0/0/0/0/0/0/0/0/0/0/0/0/2/1/0/0/0/0/2 | code-built-children | measured fact | displaced by tile-tactics|geometry|FMTacticsPanel#|box|P4/0/4/0/0/0/0/0/0/0/1/0/0/0/0/1/0/0/0/0/0/0/0/0/0/0/0/0/2/1/0/0/0/0/2 | code-built content: the tactics pitch |
| tile-tactics|geometry|VisualElement#formation-cells--unpacked|box|P4/0/4/0/0/0/0/0/0/0/1/0/0/0/0/1/0/0/0/0/0/0/0/0/0/0/0/0/2/1/1/0/0 | inherited | tile-tactics|geometry|FMTacticsPanel#|box|P4/0/4/0/0/0/0/0/0/0/1/0/0/0/0/1/0/0/0/0/0/0/0/0/0/0/0/0/2/1/0/0/0/0/2 | code-built-children | measured fact | displaced by tile-tactics|geometry|FMTacticsPanel#|box|P4/0/4/0/0/0/0/0/0/0/1/0/0/0/0/1/0/0/0/0/0/0/0/0/0/0/0/0/2/1/0/0/0/0/2 | code-built content: the tactics pitch |
| tile-tactics|geometry|VisualElement#data_display-cell-combo_cell-default-type-default-icon-size-medium-orientation-horizontal-combo-2-cell|box|P4/0/4/0/0/0/0/0/0/0/1/0/0/0/0/1/0/0/0/0/0/0/0/0/0/0/0/0/2/1/1/0/0/0 | inherited | tile-tactics|geometry|FMTacticsPanel#|box|P4/0/4/0/0/0/0/0/0/0/1/0/0/0/0/1/0/0/0/0/0/0/0/0/0/0/0/0/2/1/0/0/0/0/2 | code-built-children | measured fact | displaced by tile-tactics|geometry|FMTacticsPanel#|box|P4/0/4/0/0/0/0/0/0/0/1/0/0/0/0/1/0/0/0/0/0/0/0/0/0/0/0/0/2/1/0/0/0/0/2 | code-built content: the tactics pitch |
| tile-tactics|geometry|VisualElement#frame|box|P4/0/4/0/0/0/0/0/0/0/1/0/0/0/0/1/0/0/0/0/0/0/0/0/0/0/0/0/2/1/1/0/0/0/0 | inherited | tile-tactics|geometry|FMTacticsPanel#|box|P4/0/4/0/0/0/0/0/0/0/1/0/0/0/0/1/0/0/0/0/0/0/0/0/0/0/0/0/2/1/0/0/0/0/2 | code-built-children | measured fact | displaced by tile-tactics|geometry|FMTacticsPanel#|box|P4/0/4/0/0/0/0/0/0/0/1/0/0/0/0/1/0/0/0/0/0/0/0/0/0/0/0/0/2/1/0/0/0/0/2 | code-built content: the tactics pitch |
| tile-tactics|geometry|BindingRemapper#|box|P4/0/4/0/0/0/0/0/0/0/1/0/0/0/0/1/0/0/0/0/0/0/0/0/0/0/0/0/2/1/1/0/0/0/0/0 | inherited | tile-tactics|geometry|FMTacticsPanel#|box|P4/0/4/0/0/0/0/0/0/0/1/0/0/0/0/1/0/0/0/0/0/0/0/0/0/0/0/0/2/1/0/0/0/0/2, tile-tactics|geometry|SIText#in-posession-formation-text|box|P4/0/4/0/0/0/0/0/0/0/1/0/0/0/0/1/0/0/0/0/0/0/0/0/0/0/0/0/2/1/1/0/0/0/0/0/0/1 | code-built-children | measured fact | displaced by tile-tactics|geometry|FMTacticsPanel#|box|P4/0/4/0/0/0/0/0/0/0/1/0/0/0/0/1/0/0/0/0/0/0/0/0/0/0/0/0/2/1/0/0/0/0/2, tile-tactics|geometry|SIText#in-posession-formation-text|box|P4/0/4/0/0/0/0/0/0/0/1/0/0/0/0/1/0/0/0/0/0/0/0/0/0/0/0/0/2/1/1/0/0/0/0/0/0/1 | code-built content: the tactics pitch |
| tile-tactics|geometry|VisualElement#|box|P4/0/4/0/0/0/0/0/0/0/1/0/0/0/0/1/0/0/0/0/0/0/0/0/0/0/0/0/2/1/1/0/0/0/0/0/0 | inherited | tile-tactics|geometry|FMTacticsPanel#|box|P4/0/4/0/0/0/0/0/0/0/1/0/0/0/0/1/0/0/0/0/0/0/0/0/0/0/0/0/2/1/0/0/0/0/2, tile-tactics|geometry|SIText#in-posession-formation-text|box|P4/0/4/0/0/0/0/0/0/0/1/0/0/0/0/1/0/0/0/0/0/0/0/0/0/0/0/0/2/1/1/0/0/0/0/0/0/1 | code-built-children | measured fact | displaced by tile-tactics|geometry|FMTacticsPanel#|box|P4/0/4/0/0/0/0/0/0/0/1/0/0/0/0/1/0/0/0/0/0/0/0/0/0/0/0/0/2/1/0/0/0/0/2, tile-tactics|geometry|SIText#in-posession-formation-text|box|P4/0/4/0/0/0/0/0/0/0/1/0/0/0/0/1/0/0/0/0/0/0/0/0/0/0/0/0/2/1/1/0/0/0/0/0/0/1 | code-built content: the tactics pitch |
| tile-tactics|geometry|VisualElement#game-concepts-in-possession_small|box|P4/0/4/0/0/0/0/0/0/0/1/0/0/0/0/1/0/0/0/0/0/0/0/0/0/0/0/0/2/1/1/0/0/0/0/0/0/0 | inherited | tile-tactics|geometry|FMTacticsPanel#|box|P4/0/4/0/0/0/0/0/0/0/1/0/0/0/0/1/0/0/0/0/0/0/0/0/0/0/0/0/2/1/0/0/0/0/2, tile-tactics|geometry|SIText#in-posession-formation-text|box|P4/0/4/0/0/0/0/0/0/0/1/0/0/0/0/1/0/0/0/0/0/0/0/0/0/0/0/0/2/1/1/0/0/0/0/0/0/1 | code-built-children | measured fact | displaced by tile-tactics|geometry|FMTacticsPanel#|box|P4/0/4/0/0/0/0/0/0/0/1/0/0/0/0/1/0/0/0/0/0/0/0/0/0/0/0/0/2/1/0/0/0/0/2, tile-tactics|geometry|SIText#in-posession-formation-text|box|P4/0/4/0/0/0/0/0/0/0/1/0/0/0/0/1/0/0/0/0/0/0/0/0/0/0/0/0/2/1/1/0/0/0/0/0/0/1 | code-built content: the tactics pitch |
| tile-tactics|geometry|SIText#in-posession-formation-text|box|P4/0/4/0/0/0/0/0/0/0/1/0/0/0/0/1/0/0/0/0/0/0/0/0/0/0/0/0/2/1/1/0/0/0/0/0/0/1 | origin | itself | stand-in-font | magnitude only | {"same_text": "Custom", "live_font_size": 14, "residual": -6.5, "live": 54.7, "magnitude_predicted": false} | code-built content: the tactics pitch |
| tile-tactics|geometry|BindingRemapper#|box|P4/0/4/0/0/0/0/0/0/0/1/0/0/0/0/1/0/0/0/0/0/0/0/0/0/0/0/0/2/1/1/0/0/0/0/1 | inherited | tile-tactics|geometry|FMTacticsPanel#|box|P4/0/4/0/0/0/0/0/0/0/1/0/0/0/0/1/0/0/0/0/0/0/0/0/0/0/0/0/2/1/0/0/0/0/2 | code-built-children | measured fact | displaced by tile-tactics|geometry|FMTacticsPanel#|box|P4/0/4/0/0/0/0/0/0/0/1/0/0/0/0/1/0/0/0/0/0/0/0/0/0/0/0/0/2/1/0/0/0/0/2 | code-built content: the tactics pitch |
| tile-tactics|geometry|VisualElement#|box|P4/0/4/0/0/0/0/0/0/0/1/0/0/0/0/1/0/0/0/0/0/0/0/0/0/0/0/0/2/1/1/0/0/0/0/1/0 | inherited | tile-tactics|geometry|FMTacticsPanel#|box|P4/0/4/0/0/0/0/0/0/0/1/0/0/0/0/1/0/0/0/0/0/0/0/0/0/0/0/0/2/1/0/0/0/0/2 | code-built-children | measured fact | displaced by tile-tactics|geometry|FMTacticsPanel#|box|P4/0/4/0/0/0/0/0/0/0/1/0/0/0/0/1/0/0/0/0/0/0/0/0/0/0/0/0/2/1/0/0/0/0/2 | code-built content: the tactics pitch |
| tile-tactics|geometry|VisualElement#game-concepts-out-of-possession_small|box|P4/0/4/0/0/0/0/0/0/0/1/0/0/0/0/1/0/0/0/0/0/0/0/0/0/0/0/0/2/1/1/0/0/0/0/1/0/0 | origin | itself | UNEXPLAINED | - |  | code-built content: the tactics pitch |
| tile-tactics|geometry|SIText#out-of-possession-formation-text|box|P4/0/4/0/0/0/0/0/0/0/1/0/0/0/0/1/0/0/0/0/0/0/0/0/0/0/0/0/2/1/1/0/0/0/0/1/0/1 | inherited | tile-tactics|geometry|FMTacticsPanel#|box|P4/0/4/0/0/0/0/0/0/0/1/0/0/0/0/1/0/0/0/0/0/0/0/0/0/0/0/0/2/1/0/0/0/0/2 | code-built-children | measured fact | displaced by tile-tactics|geometry|FMTacticsPanel#|box|P4/0/4/0/0/0/0/0/0/0/1/0/0/0/0/1/0/0/0/0/0/0/0/0/0/0/0/0/2/1/0/0/0/0/2 | code-built content: the tactics pitch |
| tile-tactics|values|SIStyleSetter#IconStyleSetter|flex-shrink|P4/0/4/0/0/0/0/0/0/0/1/0/0/0/0/1/0/0/0/0/0/0/0/0/0/0/0/0/2/1/0/0/0/0/0/0/0/0 | origin | itself | runtime-class | measured fact | {"extra_live_classes": ["game-concepts-training-set-pieces_small"], "cascade_with_them": {"width": "16px", "height": "16px", "flex-shrink": "0"}, "magnitude_pre | component-drawn image |
| tile-tactics|values|SIStyleSetter#IconStyleSetter|flex-shrink|P4/0/4/0/0/0/0/0/0/0/1/0/0/0/0/1/0/0/0/0/0/0/0/0/0/0/0/0/2/1/0/0/0/0/0/1/0/0 | origin | itself | runtime-class | measured fact | {"extra_live_classes": ["game-concepts-penalties_small"], "cascade_with_them": {"width": "16px", "height": "16px", "flex-shrink": "0"}, "magnitude_predicted": t | component-drawn image |
| tile-tactics|values|SIStyleSetter#IconStyleSetter|flex-shrink|P4/0/4/0/0/0/0/0/0/0/1/0/0/0/0/1/0/0/0/0/0/0/0/0/0/0/0/0/2/1/0/0/0/0/0/2/0/0 | origin | itself | runtime-class | measured fact | {"extra_live_classes": ["game-concepts-opposition-instructions_small"], "cascade_with_them": {"width": "16px", "height": "16px", "flex-shrink": "0"}, "magnitude | component-drawn image |
| tile-training|geometry|AutoScroller#|box|P4/0/4/0/0/0/0/0/0/0/1/0/0/0/0/2/0/0/0/0/0/0/0/0/0/1/1/0 | inherited | tile-training|geometry|SIText#title-text|box|P4/0/4/0/0/0/0/0/0/0/1/0/0/0/0/2/0/0/0/0/0/0/0/0/0/1/1/0/0/0/0/0, tile-training|geometry|SIVisible#|box|P4/0/4/0/0/0/0/0/0/0/1/0/0/0/0/2/0/0/0/0/0/0/0/0/0/1/1/0/0/0/0/1 | code-built-wrapper | measured fact | displaced by tile-training|geometry|SIText#title-text|box|P4/0/4/0/0/0/0/0/0/0/1/0/0/0/0/2/0/0/0/0/0/0/0/0/0/1/1/0/0/0/0/0, tile-training|geometry|SIVisible#|box|P4/0/4/0/0/0/0/0/0/0/1/0/0/0/0/2/0/0/0/0/0/0/0/0/0/1/1/0/0/0/0/1 | code-built content: the Training tile |
| tile-training|geometry|SIText#title-text|box|P4/0/4/0/0/0/0/0/0/0/1/0/0/0/0/2/0/0/0/0/0/0/0/0/0/1/1/0/0/0/0/0 | origin | itself | code-built-wrapper | measured fact | {"wrappers_in_capture_not_in_layout": [{"name": "unity-content-and-vertical-scroll-container", "classes": ["unity-scroll-view__content-and-vertical-scroll-conta | code-built content: the Training tile |
| tile-training|geometry|SIVisible#|box|P4/0/4/0/0/0/0/0/0/0/1/0/0/0/0/2/0/0/0/0/0/0/0/0/0/1/1/0/0/0/0/1 | origin | itself | inline-display-none | measured fact | {"inline": {"display": "None"}, "live_size": [0, 0], "render_size": [287.5, 16], "magnitude_predicted": true} | code-built content: the Training tile |
| tile-training|geometry|ComponentElement#|box|P4/0/4/0/0/0/0/0/0/0/1/0/0/0/0/2/0/0/0/0/0/0/0/0/0/2/0 | inherited | tile-training|geometry|StreamedObjectList#Week|box|P4/0/4/0/0/0/0/0/0/0/1/0/0/0/0/2/0/0/0/0/0/0/0/0/0/2/0/0/1 | empty-code-list | measured fact | displaced by tile-training|geometry|StreamedObjectList#Week|box|P4/0/4/0/0/0/0/0/0/0/1/0/0/0/0/2/0/0/0/0/0/0/0/0/0/2/0/0/1 | code-built content: the Training tile |
| tile-training|geometry|VisualElement#TrainingTile|box|P4/0/4/0/0/0/0/0/0/0/1/0/0/0/0/2/0/0/0/0/0/0/0/0/0/2/0/0 | origin | itself | UNEXPLAINED | - |  | code-built content: the Training tile |
| tile-training|geometry|StreamedObjectList#Week|box|P4/0/4/0/0/0/0/0/0/0/1/0/0/0/0/2/0/0/0/0/0/0/0/0/0/2/0/0/1 | origin | itself | empty-code-list | measured fact | {"live_children_in_capture": 699, "render_children": 0, "deficit": -293.9, "live_size": 293.9, "magnitude_predicted": true} | code-built content: the Training tile |
| tile-training|geometry|TemplateContainer#Divider|box|P4/0/4/0/0/0/0/0/0/0/1/0/0/0/0/2/0/0/0/0/0/0/0/0/0/2/0/0/2 | inherited | tile-training|geometry|StreamedObjectList#Week|box|P4/0/4/0/0/0/0/0/0/0/1/0/0/0/0/2/0/0/0/0/0/0/0/0/0/2/0/0/1 | empty-code-list | measured fact | displaced by tile-training|geometry|StreamedObjectList#Week|box|P4/0/4/0/0/0/0/0/0/0/1/0/0/0/0/2/0/0/0/0/0/0/0/0/0/2/0/0/1 | code-built content: the Training tile |
| tile-training|geometry|VisualElement#layout-divider-solid-horizontal|box|P4/0/4/0/0/0/0/0/0/0/1/0/0/0/0/2/0/0/0/0/0/0/0/0/0/2/0/0/2/0 | inherited | tile-training|geometry|StreamedObjectList#Week|box|P4/0/4/0/0/0/0/0/0/0/1/0/0/0/0/2/0/0/0/0/0/0/0/0/0/2/0/0/1 | empty-code-list | measured fact | displaced by tile-training|geometry|StreamedObjectList#Week|box|P4/0/4/0/0/0/0/0/0/0/1/0/0/0/0/2/0/0/0/0/0/0/0/0/0/2/0/0/1 | code-built content: the Training tile |
| tile-training|geometry|SIText#IndividualTrainingTitle|box|P4/0/4/0/0/0/0/0/0/0/1/0/0/0/0/2/0/0/0/0/0/0/0/0/0/2/0/0/3 | inherited | tile-training|geometry|StreamedObjectList#Week|box|P4/0/4/0/0/0/0/0/0/0/1/0/0/0/0/2/0/0/0/0/0/0/0/0/0/2/0/0/1 | empty-code-list | measured fact | displaced by tile-training|geometry|StreamedObjectList#Week|box|P4/0/4/0/0/0/0/0/0/0/1/0/0/0/0/2/0/0/0/0/0/0/0/0/0/2/0/0/1 | code-built content: the Training tile |
| tile-training|geometry|VisualElement#IndividualTraining|box|P4/0/4/0/0/0/0/0/0/0/1/0/0/0/0/2/0/0/0/0/0/0/0/0/0/2/0/0/4 | inherited | tile-training|geometry|StreamedObjectList#Week|box|P4/0/4/0/0/0/0/0/0/0/1/0/0/0/0/2/0/0/0/0/0/0/0/0/0/2/0/0/1 | empty-code-list | measured fact | displaced by tile-training|geometry|StreamedObjectList#Week|box|P4/0/4/0/0/0/0/0/0/0/1/0/0/0/0/2/0/0/0/0/0/0/0/0/0/2/0/0/1 | code-built content: the Training tile |
| tile-training|geometry|VisualElement#Improvements|box|P4/0/4/0/0/0/0/0/0/0/1/0/0/0/0/2/0/0/0/0/0/0/0/0/0/2/0/0/4/0 | inherited | tile-training|geometry|StreamedObjectList#Week|box|P4/0/4/0/0/0/0/0/0/0/1/0/0/0/0/2/0/0/0/0/0/0/0/0/0/2/0/0/1 | empty-code-list | measured fact | displaced by tile-training|geometry|StreamedObjectList#Week|box|P4/0/4/0/0/0/0/0/0/0/1/0/0/0/0/2/0/0/0/0/0/0/0/0/0/2/0/0/1 | code-built content: the Training tile |
| tile-training|geometry|VisualElement#Stat|box|P4/0/4/0/0/0/0/0/0/0/1/0/0/0/0/2/0/0/0/0/0/0/0/0/0/2/0/0/4/0/0 | inherited | tile-training|geometry|StreamedObjectList#Week|box|P4/0/4/0/0/0/0/0/0/0/1/0/0/0/0/2/0/0/0/0/0/0/0/0/0/2/0/0/1 | empty-code-list | measured fact | displaced by tile-training|geometry|StreamedObjectList#Week|box|P4/0/4/0/0/0/0/0/0/0/1/0/0/0/0/2/0/0/0/0/0/0/0/0/0/2/0/0/1 | code-built content: the Training tile |
| tile-training|geometry|SIImage#Arrow|box|P4/0/4/0/0/0/0/0/0/0/1/0/0/0/0/2/0/0/0/0/0/0/0/0/0/2/0/0/4/0/0/0 | origin | itself | runtime-class | measured fact | {"extra_live_classes": ["game-concepts-sort-arrow-up_small"], "cascade_with_them": {"width": "16px", "height": "16px", "flex-shrink": "0"}, "predicted_px": 16.0 | code-built content: the Training tile |
| tile-training|geometry|SIText#Value|box|P4/0/4/0/0/0/0/0/0/0/1/0/0/0/0/2/0/0/0/0/0/0/0/0/0/2/0/0/4/0/0/1 | inherited | tile-training|geometry|SIImage#Arrow|box|P4/0/4/0/0/0/0/0/0/0/1/0/0/0/0/2/0/0/0/0/0/0/0/0/0/2/0/0/4/0/0/0, tile-training|geometry|StreamedObjectList#Week|box|P4/0/4/0/0/0/0/0/0/0/1/0/0/0/0/2/0/0/0/0/0/0/0/0/0/2/0/0/1 | runtime-class | measured fact | displaced by tile-training|geometry|SIImage#Arrow|box|P4/0/4/0/0/0/0/0/0/0/1/0/0/0/0/2/0/0/0/0/0/0/0/0/0/2/0/0/4/0/0/0, tile-training|geometry|StreamedObjectList#Week|box|P4/0/4/0/0/0/0/0/0/0/1/0/0/0/0/2/0/0/0/0/0/0/0/0/0/2/0/0/1 | code-built content: the Training tile |
| tile-training|geometry|SIText#Title|box|P4/0/4/0/0/0/0/0/0/0/1/0/0/0/0/2/0/0/0/0/0/0/0/0/0/2/0/0/4/0/1 | inherited | tile-training|geometry|StreamedObjectList#Week|box|P4/0/4/0/0/0/0/0/0/0/1/0/0/0/0/2/0/0/0/0/0/0/0/0/0/2/0/0/1 | empty-code-list | measured fact | displaced by tile-training|geometry|StreamedObjectList#Week|box|P4/0/4/0/0/0/0/0/0/0/1/0/0/0/0/2/0/0/0/0/0/0/0/0/0/2/0/0/1 | code-built content: the Training tile |
| tile-training|geometry|VisualElement#Regressions|box|P4/0/4/0/0/0/0/0/0/0/1/0/0/0/0/2/0/0/0/0/0/0/0/0/0/2/0/0/4/1 | inherited | tile-training|geometry|StreamedObjectList#Week|box|P4/0/4/0/0/0/0/0/0/0/1/0/0/0/0/2/0/0/0/0/0/0/0/0/0/2/0/0/1 | empty-code-list | measured fact | displaced by tile-training|geometry|StreamedObjectList#Week|box|P4/0/4/0/0/0/0/0/0/0/1/0/0/0/0/2/0/0/0/0/0/0/0/0/0/2/0/0/1 | code-built content: the Training tile |
| tile-training|geometry|VisualElement#Stat|box|P4/0/4/0/0/0/0/0/0/0/1/0/0/0/0/2/0/0/0/0/0/0/0/0/0/2/0/0/4/1/0 | inherited | tile-training|geometry|StreamedObjectList#Week|box|P4/0/4/0/0/0/0/0/0/0/1/0/0/0/0/2/0/0/0/0/0/0/0/0/0/2/0/0/1 | empty-code-list | measured fact | displaced by tile-training|geometry|StreamedObjectList#Week|box|P4/0/4/0/0/0/0/0/0/0/1/0/0/0/0/2/0/0/0/0/0/0/0/0/0/2/0/0/1 | code-built content: the Training tile |
| tile-training|geometry|SIImage#Arrow|box|P4/0/4/0/0/0/0/0/0/0/1/0/0/0/0/2/0/0/0/0/0/0/0/0/0/2/0/0/4/1/0/0 | origin | itself | runtime-class | measured fact | {"extra_live_classes": ["game-concepts-sort-arrow-down_small"], "cascade_with_them": {"width": "16px", "height": "16px", "flex-shrink": "0"}, "predicted_px": 16 | code-built content: the Training tile |
| tile-training|geometry|SIText#Value|box|P4/0/4/0/0/0/0/0/0/0/1/0/0/0/0/2/0/0/0/0/0/0/0/0/0/2/0/0/4/1/0/1 | origin | itself | stand-in-font | magnitude only | {"same_text": "3", "live_font_size": 14, "residual": -1.9, "live": 13.7, "magnitude_predicted": false} | code-built content: the Training tile |
| tile-training|geometry|SIText#Title|box|P4/0/4/0/0/0/0/0/0/0/1/0/0/0/0/2/0/0/0/0/0/0/0/0/0/2/0/0/4/1/1 | inherited | tile-training|geometry|StreamedObjectList#Week|box|P4/0/4/0/0/0/0/0/0/0/1/0/0/0/0/2/0/0/0/0/0/0/0/0/0/2/0/0/1 | empty-code-list | measured fact | displaced by tile-training|geometry|StreamedObjectList#Week|box|P4/0/4/0/0/0/0/0/0/0/1/0/0/0/0/2/0/0/0/0/0/0/0/0/0/2/0/0/1 | code-built content: the Training tile |
| tile-training|values|SIButton#layout-tile-interaction-button|background-color|P4/0/4/0/0/0/0/0/0/0/1/0/0/0/0/2/0/0/0/0/0/0/0/0/0 | origin | itself | runtime-sheet-colour | magnitude only | {"live_value_in_runtime_sheet_samples": true, "note": "the sheet's sampled rules paint this value elsewhere; this element's own rule is not in the 80-rule sampl | run-time club-colour sheet |
| tile-training|values|SIImage#Arrow|flex-shrink|P4/0/4/0/0/0/0/0/0/0/1/0/0/0/0/2/0/0/0/0/0/0/0/0/0/2/0/0/4/0/0/0 | origin | itself | runtime-class | measured fact | {"extra_live_classes": ["game-concepts-sort-arrow-up_small"], "cascade_with_them": {"width": "16px", "height": "16px", "flex-shrink": "0"}, "magnitude_predicted | component-drawn image |
| tile-training|values|SIImage#Arrow|flex-shrink|P4/0/4/0/0/0/0/0/0/0/1/0/0/0/0/2/0/0/0/0/0/0/0/0/0/2/0/0/4/1/0/0 | origin | itself | runtime-class | measured fact | {"extra_live_classes": ["game-concepts-sort-arrow-down_small"], "cascade_with_them": {"width": "16px", "height": "16px", "flex-shrink": "0"}, "magnitude_predict | component-drawn image |

## Grid placement: what it was measured on

Two words are used here and the files used one for both. **Pitch** in `pitch.json` and `screen.py` is the grid CELL pitch (about 65.5 px cell, 16.5 px gap, stride 82 in the game's inline px). The football pitch is a different thing: it is drawn in code, is not modelled, and its rows are among the failures above.

The measured model rests on six screen captures (the Squad overview at three panel sizes and in Large, Standard and Small compositions, and Tactics > Team Instructions at Large), behind six screen fixtures, 28 host rows, all pass. The approved plan required a fullscreen, a 16x9 and a body preset to be measured before the M3 exit; the plan's own status lists them as unmeasured: they were not.

| Fixture | Status | Hosts compared | Given slots | Max residual (world px) | Parameters |
|---|---|---|---|---|---|
| screen-squad-large-1600 | measured-in-fit (the capture is behind the fit, so this is a reproduction, not a test) | 5 | 0 | 0.6 | pitch and gap FITTED to these captures; stride 82 and the host formula FITTED; area, origin, padding and reserved_right are SUPPLIED by the fixture from the capture |
| screen-squad-large-1680 | measured-in-fit (the capture is behind the fit, so this is a reproduction, not a test) | 5 | 0 | 0.4 | pitch and gap FITTED to these captures; stride 82 and the host formula FITTED; area, origin, padding and reserved_right are SUPPLIED by the fixture from the capture |
| screen-squad-large-2500 | measured-in-fit (the capture is behind the fit, so this is a reproduction, not a test) | 5 | 0 | 0.8 | pitch and gap FITTED to these captures; stride 82 and the host formula FITTED; area, origin, padding and reserved_right are SUPPLIED by the fixture from the capture |
| screen-squad-small | measured-in-fit (the capture is behind the fit, so this is a reproduction, not a test) | 5 | 0 | 0.5 | pitch and gap FITTED to these captures; stride 82 and the host formula FITTED; area, origin, padding and reserved_right are SUPPLIED by the fixture from the capture |
| screen-squad-standard | measured-in-fit (the capture is behind the fit, so this is a reproduction, not a test) | 5 | 0 | 0.6 | pitch and gap FITTED to these captures; stride 82 and the host formula FITTED; area, origin, padding and reserved_right are SUPPLIED by the fixture from the capture |
| screen-team-instructions-large | measured-in-fit (the capture is behind the fit, so this is a reproduction, not a test) | 3 | 0 | 0.8 | pitch and gap FITTED to these captures; stride 82 and the host formula FITTED; area, origin, padding and reserved_right are SUPPLIED by the fixture from the capture |

Residuals are published, not verdicts: an 8 px tolerance on a 312 px host cannot test a pitch quoted to 0.1 px. The row output now marks `given` slots (cells handed to the assembler from the capture), which it could not tell from predictions before.

### Held-out test (zero game time)

The model was frozen at commit `5a661f39a6` (hashes in `phase9-fix-round-heldout-predictions.json`: screen.py 2c50023f3bfe6385, pitch.json 4775b145a1e99ed6), its predictions for three captures it was never fitted to were written and committed, and only then were the hosts' real positions opened (the predictions commit precedes the comparison commit). Assumptions the model could not know: composition = the one whose cells hold all host names (the -Large variant when there is one), padding 12, no reserved columns. The Phase 7 tile positions (x 40, 1274, 865) were not used: their panel size is not recoverable.

| Capture | Composition predicted | Hosts | Exact (0 px) | Max residual (inline px) |
|---|---|---|---|---|
| styles-d3-transfers-activity-20261114-111518.ndjson | RecruitmentComposition-Large | 8 | 2 | 656 |
| styles-d4-inbox-20261114-111746.ndjson | Portal-Large | 7 | 7 | 0 |
| styles-sessionB-start-screen-20261114-103457.ndjson | MainMenuHasSaveComposition-Large-IM | 7 | 7 | 0 |

Result, whichever way it fell: 16 of 22 hosts exact, 2 compositions reproduced exactly, 1 did not (the Transfers Activity bottom-row cells sit about 492 px lower than predicted: the model moves right-anchored cells and grows flexible ones but has no rule for cells anchored to the bottom edge). Nothing was tuned to this result.

Not counted as checks (circular): any capture behind a pitch.json entry, Standard and Small on the captures they were measured from, given slots, a capture that prompted a model change, and the 1680 capture beyond panel-size independence for one composition.

Grid placement reproduces the captures it was derived from to 0.8 px on 4 compositions, one save, one club. Held-out checks: 3 (2 exact, 1 not). Every other composition is an estimate never compared with the game (4 of 1,804 have a measured pitch entry).


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

## state-i3-session-g

| Verdict | Check | Element | Property | Expected | Got | Delta | Note / cause |
|---|---|---|---|---|---|---|---|
| PASS | filter-hover | SIButton#.HasSIClickable.row-direction-normal | background-color (rest) | "#FFFFFF24" | "#FFFFFF24" |  |  |
| PASS | filter-hover | SIButton#.HasSIClickable.row-direction-normal | background-color (enabled+hover) | "#FFFFFF33" | "#FFFFFF33" |  | state rule .buttons-button-base-default:hover |
| PASS | filter-press-held | SIButton#.HasSIClickable.row-direction-normal | background-color (rest) | "#FFFFFF24" | "#FFFFFF24" |  |  |
| PASS | filter-press-held | SIButton#.HasSIClickable.row-direction-normal | background-color (active+enabled+focus+hover) | "#FFFFFF24" | "#FFFFFF24" |  | observation: read with mask 67 (active+hover+focus); background #FFFFFF24 while pressed (one reading) | state rule .buttons-button-base-default:active:enabled | interpretation (derived): the static rule .buttons-button-base-default:active:enabled (specificity 31) declares var(--core-controls-surface-pc-pressed) = #FFFFFF24, equal to rest, and outranks :hover (21) [single source: a lookup made AFTER the model was changed (:enabled added) on this same reading; not an independent observation of the press state] |
| PASS | filter-dragged-off-held | SIButton#.HasSIClickable.row-direction-normal | background-color (rest) | "#FFFFFF24" | "#FFFFFF24" |  |  |
| PASS | filter-dragged-off-held | SIButton#.HasSIClickable.row-direction-normal | background-color (enabled+focus) | "#FFFFFF24" | "#FFFFFF24" |  | explicit no-op: no state rule declares background-color: the render predicts no change | mask 64 (focus only) with the mouse still held |
| PASS | filter-released | SIButton#.HasSIClickable.row-direction-normal | background-color (rest) | "#FFFFFF24" | "#FFFFFF24" |  |  |
| PASS | filter-released | SIButton#.HasSIClickable.row-direction-normal | background-color (enabled) | "#FFFFFF24" | "#FFFFFF24" |  | explicit no-op: no state rule declares background-color: the render predicts no change |
| FAIL | loans-tile-hover | SIButton#layout-tile-interaction-button | background-color (rest) | "#17223F" | "#1E2129" |  | cause (examined, magnitude only): runtime-sheet-colour |
| PASS | loans-tile-hover | SIButton#layout-tile-interaction-button | background-color (enabled+hover) | "#2E3138" | "#2E3138" |  | state rule .layout-tile-interaction-button:hover |
| PASS | nav-tab-label-hover | SIText#text | color (rest) | "#EBEBEB" | "#EBEBEB" |  |  | CONDITIONAL on the inference that the label is hovered (the mask read 0) |
| PASS | nav-tab-label-hover | SIText#text | color (enabled+hover) | "#FFFFFF" | "#FFFFFF" |  | observation: Measured: label colour #FFFFFF under the pointer, rest #EBEBEB; label mask 0; ancestors 2 (SIButton, the two wrappers). Not measured: why. | state rule .navigation-tab-portal-default-active-false .portal-text:hover | CONDITIONAL on the inference that the label is hovered (the mask read 0) | interpretation (inferred): this row sets hover on the label itself, which the mask did not show: it is CONDITIONAL on that inference | interpretation (derived): a rule in the game's applied sheets, .navigation-tab-portal-default-active-false .portal-text:hover, declares #FFFFFF for a hovered label |
| FAIL | nav-tab-label-as-read | SIText#text | color (rest) | "#EBEBEB" | "#000000B2" |  | cause (examined, measured fact): runtime-sheet-declares-value | variant of nav-tab-label-hover |
| FAIL | nav-tab-label-as-read | SIText#text | color (enabled) | "#FFFFFF" | "#000000B2" |  | observation: the same reading with the states AS READ: label 0, ancestors hover (2); the game's applied sheets only | state rule .nav-on-light .navigation-tab-portal-default-active-false:hover .portal-text | cause (examined, measured fact): runtime-sheet-declares-value | variant of nav-tab-label-hover | interpretation (derived): if this FAILS, no rule in the applied sheets colours the label through a hovered ancestor |
| PASS | nav-tab-label-as-read-runtime-sheet | SIText#text | color (rest) | "#EBEBEB" | "#EBEBEB" |  |  | variant of nav-tab-label-hover |
| PASS | nav-tab-label-as-read-runtime-sheet | SIText#text | color (enabled) | "#FFFFFF" | "#FFFFFF" |  | observation: the same reading with the states AS READ (label 0, ancestors hover), plus the RECORDED run-time sheet (empty name, negative instance id) of the squad capture, whose sampled rules include .nav-on-light .navigation-tab-portal-default-active-false:hover .portal-text { color: var(--colours-base-neutral-white) }; the label's ancestor MainNav carries nav-on-light in that capture | state rule .nav-on-light .navigation-tab-portal-default-active-false:hover .portal-text | variant of nav-tab-label-hover | interpretation (derived): an ancestor-hover rule yields #FFFFFF under the masks as read, so the label's own hover is not needed to explain the colour | interpretation (inferred): whether the game applies that recorded rule to this label at this moment is not observed; a stale mask read is NOT excluded (no repeated reads were taken), and inheritance was not tested |
| PASS | table-row-hover | BindingRoot#.streamed-table__row.row-direction-normal | background-color (rest) | "#FFFFFF00" | "#FFFFFF00" |  |  |
| PASS | table-row-hover | BindingRoot#.streamed-table__row.row-direction-normal | background-color (enabled+hover) | "#FFFFFF1A" | "#FFFFFF1A" |  | state rule .streamed-table__row.virtualised-list__item:hover | even row of the zebra list; odd rows rest at #FFFFFF0F (the zebra rule is not part of this check) |
| PASS | inbox-row-hover | SIButton#NewsItemButton | background-color (rest) | "#00000000" | "#00000000" |  |  |
| PASS | inbox-row-hover | SIButton#NewsItemButton | background-color (enabled+hover) | "#FFFFFF14" | "#FFFFFF14" |  | state rule .message-button:hover |
| PASS | inbox-row-clicked-focus | SIButton#NewsItemButton | background-color (rest) | "#00000000" | "#00000000" |  |  |
| PASS | inbox-row-clicked-focus | SIButton#NewsItemButton | background-color (enabled+focus) | "#00000000" | "#00000000" |  | explicit no-op: no state rule declares background-color: the render predicts no change | after the selection click the row's button carries mask 64 and no colour change |
| N/A | pitch-marker-hover | VisualElement#.projected--position--filled | background-color (rest) | "#00000000" | null |  | the render declares no background-color here |
| PASS | pitch-marker-hover | VisualElement#.projected--position--filled | background-color (enabled+hover) | "#00000000" | "unchanged (no declaration, no state rule)" |  | explicit no-op: no state rule declares background-color: the render predicts no change | mask 2 on the marker and every descendant read; colour and background unchanged |
| N/A | pitch-marker-label-hover | VisualElement#.content-tactics-visualiser-player-indicator-simple | color (rest) | "#EBEBEB" | null |  | the render declares no color here |
| PASS | pitch-marker-label-hover | VisualElement#.content-tactics-visualiser-player-indicator-simple | color (enabled+hover) | "#EBEBEB" | "unchanged (no declaration, no state rule)" |  | explicit no-op: no state rule declares color: the render predicts no change |
| N/A | instruction-tile-hover | TemplateContainer#TeamInstructionTile | background-color (rest) | "#00000000" | null |  | the render declares no background-color here |
| PASS | instruction-tile-hover | TemplateContainer#TeamInstructionTile | background-color (enabled+hover) | "#00000000" | "unchanged (no declaration, no state rule)" |  | explicit no-op: no state rule declares background-color: the render predicts no change | mask 2 five levels down; colour, background and border unchanged at every level read |
| N/A | inbox-selection-class-swap | SIStyleSetter#SIStyleSetter_IsLastSelected | class swap message-not-last-selected -> message-last-selected | "class swap seen; no property measured on the setter" | {"color": [null, "#EBEBEB"]} |  | the class swap was seen (setters idx 1,22 -> 3,24); no colour was read on the setter, so the render's one declared difference (colour #EBEBEB on the selected setter, inherited by its children) has nothing to compare against |

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
| FAIL | geometry | AutoScroller# | box | [11.7, 8.8, 288.1, 17.6] | [12, 2, 287.5, 32] | [0.3, -6.8, -0.6, 14.4] | cause (examined, measured fact): code-built-wrapper; displaced by tile-atmosphere|geometry|SIText#title-text|box|P4/0/4/0/0/0/0/0/0/0/1/0/0/0/0/0/0/0/0/0/0/0/0/0/0/1/1/0/0/0/0/0, tile-atmosphere|geometry|SIVisible#|box|P4/0/4/0/0/0/0/0/0/0/1/0/0/0/0/0/0/0/0/0/0/0/0/0/0/1/1/0/0/0/0/1 |
| FAIL | geometry | SIText#title-text | box | [11.7, 8.8, 52.7, 17.6] | [12, 2, 283.5, 16] | [0.3, -6.8, 230.8, -1.6] | cause (examined, measured fact): code-built-wrapper |
| FAIL | geometry | SIVisible# | box | [11.7, 8.8, 0, 0] | [12, 18, 287.5, 16] | [0.3, 9.2, 287.5, 16] | cause (examined, measured fact): inline-display-none |
| N/A | geometry | SIText#title-text-alt | box | null | [12, 18, 287.5, 16] |  | no live element paired: the drawn node has no partner in the capture (absent or not captured) |
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
| FAIL | values | SIButton#layout-tile-interaction-button | background-color | "#17223F" | "#1E2129" |  | cause (examined, magnitude only): runtime-sheet-colour |
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
| FAIL | values | SIText#state_text | color | "#4EEB3D" | "#EBEBEB" |  | cause (examined, no supporting fact): UNEXPLAINED |
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
| FAIL | geometry | AutoScroller#auto-scroller | box | [11.7, 1.9, 32.2, 31.2] | [12, 2, 38.1, 32] | [0.3, 0.1, 5.9, 0.8] | cause (examined, no supporting fact): UNEXPLAINED; displaced by tile-loans|geometry|SIText#title-text|box|P4/0/4/0/0/0/0/0/0/0/1/0/0/0/0/7/0/0/0/0/0/0/0/0/0/0/1/1/0/0/0/0 |
| FAIL | geometry | SIText#title-text | box | [11.7, 1.9, 32.2, 31.2] | [12, 2, 38.1, 21.5] | [0.3, 0.1, 5.9, -9.7] | cause (examined, no supporting fact): UNEXPLAINED |
| PASS | geometry | TemplateContainer#states-templates-tile-content | box | [0.0, 33.2, 311.5, 114.3] | [0, 34, 311.5, 113.5] | [0.0, 0.8, 0.0, -0.8] |  |
| PASS | geometry | VisualElement# | box | [11.7, 33.2, 288.1, 106.4] | [12, 34, 287.5, 105.5] | [0.3, 0.8, -0.6, -0.9] |  |
| PASS | geometry | VisualElement#Frame_1000002538 | box | [11.7, 33.2, 288.1, 106.4] | [12, 34, 287.5, 105.5] | [0.3, 0.8, -0.6, -0.9] |  |
| PASS | geometry | VisualElement#Frame_1000003021 | box | [11.7, 33.2, 288.1, 24.4] | [12, 34, 287.5, 24.4] | [0.3, 0.8, -0.6, 0.0] |  |
| FAIL | geometry | SIText#title-text | box | [11.7, 33.2, 82, 24.4] | [12, 34, 70.3, 24.4] | [0.3, 0.8, -11.7, 0.0] | cause (examined, magnitude only): stand-in-font |
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
| FAIL | values | SIButton#layout-tile-interaction-button | background-color | "#2E3138" | "#1E2129" |  | cause (examined, measured fact): state-captured |
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
| PASS | hover-captured | SIButton#layout-tile-interaction-button | background-color (enabled+hover) | "#2E3138" | "#2E3138" |  | state rule .layout-tile-interaction-button:hover | paired with the FAIL row of the values check (added after 1.0.0, the FAIL is kept as scored): this tile was captured with the button's pseudo-state mask = 2 (hover), so its resolved value is the hover value |

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
| FAIL | geometry | AutoScroller#auto-scroller | box | [11.7, 1.9, 32.2, 31.2] | [12, 2, 38.1, 32] | [0.3, 0.1, 5.9, 0.8] | cause (examined, no supporting fact): UNEXPLAINED |
| N/A | geometry | SIText#title-text | box | null | [12, 2, 38.1, 21.5] |  | no live element paired: the drawn node has no partner in the capture (absent or not captured) |
| PASS | geometry | TemplateContainer#states-templates-tile-content | box | [0.0, 33.2, 311.5, 114.3] | [0, 34, 311.5, 113.5] | [0.0, 0.8, 0.0, -0.8] |  |
| PASS | geometry | VisualElement# | box | [11.7, 33.2, 288.1, 106.4] | [12, 34, 287.5, 105.5] | [0.3, 0.8, -0.6, -0.9] |  |
| PASS | geometry | VisualElement#Frame_1000002538 | box | [11.7, 33.2, 288.1, 106.4] | [12, 34, 287.5, 105.5] | [0.3, 0.8, -0.6, -0.9] |  |
| PASS | geometry | VisualElement#Frame_1000003021 | box | [11.7, 33.2, 288.1, 24.4] | [12, 34, 287.5, 24.4] | [0.3, 0.8, -0.6, 0.0] |  |
| N/A | geometry | SIText#title-text | box | null | [12, 34, 70.3, 24.4] |  | no live element paired: the drawn node has no partner in the capture (absent or not captured) |
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
| FAIL | geometry | AutoScroller# | box | [11.7, 8.8, 288.1, 17.6] | [12, 2, 287.5, 32] | [0.3, -6.8, -0.6, 14.4] | cause (examined, measured fact): code-built-wrapper; displaced by tile-medical-centre|geometry|SIText#title-text|box|P4/0/4/0/0/0/0/0/0/0/1/0/0/0/0/6/0/0/0/0/0/0/0/0/0/0/1/1/0/0/0/0/0, tile-medical-centre|geometry|SIVisible#|box|P4/0/4/0/0/0/0/0/0/0/1/0/0/0/0/6/0/0/0/0/0/0/0/0/0/0/1/1/0/0/0/0/1 |
| FAIL | geometry | SIText#title-text | box | [11.7, 8.8, 85, 17.6] | [12, 2, 283.5, 16] | [0.3, -6.8, 198.5, -1.6] | cause (examined, measured fact): code-built-wrapper |
| FAIL | geometry | SIVisible# | box | [11.7, 8.8, 0, 0] | [12, 18, 287.5, 16] | [0.3, 9.2, 287.5, 16] | cause (examined, measured fact): inline-display-none |
| N/A | geometry | SIText#title-text-alt | box | null | [12, 18, 287.5, 16] |  | no live element paired: the drawn node has no partner in the capture (absent or not captured) |
| PASS | geometry | VisualElement#CarouselMask | box | [303.7, 2, 0, 31.2] | [303.5, 2, 0, 32] | [-0.2, 0, 0, 0.8] |  |
| PASS | geometry | TemplateContainer#states-templates-tile-content | box | [0.0, 33.2, 311.5, 114.3] | [0, 34, 311.5, 113.5] | [0.0, 0.8, 0.0, -0.8] |  |
| PASS | geometry | VisualElement# | box | [11.7, 33.2, 288.1, 106.4] | [12, 34, 287.5, 105.5] | [0.3, 0.8, -0.6, -0.9] |  |
| PASS | geometry | BindableSwitchElement# | box | [11.7, 33.2, 288.1, 106.4] | [12, 34, 287.5, 105.5] | [0.3, 0.8, -0.6, -0.9] |  |
| N/A | geometry | VisualElement#Frame | box | null | [0, 0, 0, 0] |  | descendant of a switch branch the render chose not to show (one branch per switch): no live partner by design |
| N/A | geometry | VisualElement#Frame | box | null | [0, 0, 0, 0] |  | descendant of a switch branch the render chose not to show (one branch per switch): no live partner by design |
| N/A | geometry | VisualElement# | box | null | [0, 0, 0, 0] |  | descendant of a switch branch the render chose not to show (one branch per switch): no live partner by design |
| N/A | geometry | VisualElement#Frame | box | null | [0, 0, 0, 0] |  | descendant of a switch branch the render chose not to show (one branch per switch): no live partner by design |
| N/A | geometry | VisualElement#Frame | box | null | [0, 0, 0, 0] |  | descendant of a switch branch the render chose not to show (one branch per switch): no live partner by design |
| N/A | geometry | SIText#text | box | null | [0, 0, 0, 0] |  | descendant of a switch branch the render chose not to show (one branch per switch): no live partner by design |
| N/A | geometry | StreamedObjectList# | box | null | [0, 0, 0, 0] |  | descendant of a switch branch the render chose not to show (one branch per switch): no live partner by design |
| N/A | geometry | TemplateContainer# | box | null | [0, 0, 0, 0] |  | descendant of a switch branch the render chose not to show (one branch per switch): no live partner by design |
| N/A | geometry | VisualElement#layout-divider-solid-horizontal | box | null | [0, 0, 0, 0] |  | descendant of a switch branch the render chose not to show (one branch per switch): no live partner by design |
| N/A | geometry | VisualElement#data_display-string-list-item-default-unpacked | box | null | [0, 0, 0, 0] |  | descendant of a switch branch the render chose not to show (one branch per switch): no live partner by design |
| N/A | geometry | VisualElement# | box | null | [0, 0, 0, 0] |  | descendant of a switch branch the render chose not to show (one branch per switch): no live partner by design |
| N/A | geometry | SIText#text | box | null | [0, 0, 0, 0] |  | descendant of a switch branch the render chose not to show (one branch per switch): no live partner by design |
| PASS | geometry | VisualElement# | box | [11.7, 33.2, 288.1, 106.4] | [12, 34, 287.5, 105.5] | [0.3, 0.8, -0.6, -0.9] |  |
| PASS | geometry | VisualElement#Frame | box | [11.7, 33.2, 288.1, 79.1] | [12, 34, 287.5, 77.9] | [0.3, 0.8, -0.6, -1.2] |  |
| PASS | geometry | VisualElement#Frame | box | [11.7, 33.2, 288.1, 79.1] | [12, 34, 287.5, 77.9] | [0.3, 0.8, -0.6, -1.2] |  |
| PASS | geometry | VisualElement#scaling-icons-condition | box | [11.7, 33.2, 23.4, 24.4] | [12, 34, 24, 24] | [0.3, 0.8, 0.6, -0.4] |  |
| PASS | geometry | VisualElement#Frame | box | [39.0, 33.2, 260.7, 79.1] | [40, 34, 259.5, 77.9] | [1.0, 0.8, -1.2, -1.2] |  |
| PASS | geometry | VisualElement#Frame | box | [42.9, 33.2, 256.8, 24.4] | [44, 34, 255.5, 24.4] | [1.1, 0.8, -1.3, 0.0] |  |
| FAIL | geometry | SIText#text | box | [42.9, 33.2, 147.5, 24.4] | [44, 34, 127.2, 24.4] | [1.1, 0.8, -20.3, 0.0] | cause (examined, magnitude only): stand-in-font |
| PASS | geometry | StreamedObjectList# | box | [39.0, 65.5, 260.7, 46.9] | [40, 66.4, 259.5, 45.5] | [1.0, 0.9, -1.2, -1.4] |  |
| PASS | geometry | VisualElement#Frame | box | [11.7, 112.3, 288.1, 27.3] | [12, 111.9, 287.5, 27.6] | [0.3, -0.4, -0.6, 0.3] |  |
| FAIL | geometry | TemplateContainer#layout-divider-solid-horizontal | box | [11.7, 112.3, 288.1, 1] | [12, 111.9, 287.5, 1] | [0.3, -0.4, -0.6, 0] | cause (examined, measured fact): sub-pixel-tolerance; displaced by tile-medical-centre|geometry|VisualElement#layout-divider-solid-horizontal|box|P4/0/4/0/0/0/0/0/0/0/1/0/0/0/0/6/0/0/0/0/0/0/0/0/0/0/2/0/0/0/1/0/0 |
| FAIL | geometry | VisualElement#layout-divider-solid-horizontal | box | [11.7, 112.3, 288.1, 1] | [12, 111.9, 287.5, 1] | [0.3, -0.4, -0.6, 0] | cause (examined, measured fact): sub-pixel-tolerance |
| PASS | geometry | VisualElement#data_display-string-list-item-default-unpacked | box | [11.7, 121.1, 283.2, 18.6] | [12, 120.9, 283.5, 18.6] | [0.3, -0.2, 0.3, -0.0] |  |
| PASS | geometry | VisualElement# | box | [11.7, 122.1, 15.6, 16.6] | [12, 122.2, 16, 16] | [0.3, 0.1, 0.4, -0.6] |  |
| FAIL | geometry | SIText#text | box | [31.2, 121.1, 143.6, 18.6] | [32, 120.9, 129.4, 18.6] | [0.8, -0.2, -14.2, -0.0] | cause (examined, magnitude only): stand-in-font |
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
| FAIL | values | SIButton#layout-tile-interaction-button | background-color | "#17223F" | "#1E2129" |  | cause (examined, magnitude only): runtime-sheet-colour |
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
| FAIL | geometry | AutoScroller#auto-scroller | box | [11.7, 1.9, 41, 32.2] | [12, 2, 38.1, 32] | [0.3, 0.1, -2.9, -0.2] | cause (examined, no supporting fact): UNEXPLAINED; displaced by tile-tactics|geometry|SIText#title-text|box|P4/0/4/0/0/0/0/0/0/0/1/0/0/0/0/1/0/0/0/0/0/0/0/0/0/0/0/0/1/1/0/0/0/0 |
| FAIL | geometry | SIText#title-text | box | [11.7, 1.9, 41, 32.2] | [12, 2, 38.1, 21.5] | [0.3, 0.1, -2.9, -10.7] | cause (examined, no supporting fact): UNEXPLAINED |
| PASS | geometry | TemplateContainer#states-templates-tile-content | box | [0.0, 34.1, 311.5, 277.3] | [0, 34, 311.5, 277.5] | [0.0, -0.1, 0.0, 0.2] |  |
| PASS | geometry | VisualElement# | box | [0.0, 256.8, 311.5, 54.7] | [0, 256, 311.5, 55.5] | [0.0, -0.8, 0.0, 0.8] |  |
| PASS | geometry | VisualElement#tile-templates-4x4-template-2 | box | [11.7, 34.1, 288.1, 269.5] | [12, 34, 287.5, 269.5] | [0.3, -0.1, -0.6, 0.0] |  |
| FAIL | geometry | VisualElement#TacticsPitch-UNPACKED | box | [11.7, 34.1, 288.1, 216.8] | [12, 34, 287.5, 175.7] | [0.3, -0.1, -0.6, -41.1] | cause (examined, measured fact): code-built-children; displaced by tile-tactics|geometry|FMTacticsPanel#|box|P4/0/4/0/0/0/0/0/0/0/1/0/0/0/0/1/0/0/0/0/0/0/0/0/0/0/0/0/2/1/0/0/0/0/2 |
| FAIL | geometry | BindingExpect#pitch-expect | box | [11.7, 34.1, 288.1, 216.8] | [12, 34, 287.5, 175.7] | [0.3, -0.1, -0.6, -41.1] | cause (examined, measured fact): code-built-children; displaced by tile-tactics|geometry|FMTacticsPanel#|box|P4/0/4/0/0/0/0/0/0/0/1/0/0/0/0/1/0/0/0/0/0/0/0/0/0/0/0/0/2/1/0/0/0/0/2 |
| FAIL | geometry | BindingRemapper#pitch-remapper | box | [11.7, 34.1, 288.1, 216.8] | [12, 34, 287.5, 175.7] | [0.3, -0.1, -0.6, -41.1] | cause (examined, measured fact): code-built-children; displaced by tile-tactics|geometry|FMTacticsPanel#|box|P4/0/4/0/0/0/0/0/0/0/1/0/0/0/0/1/0/0/0/0/0/0/0/0/0/0/0/0/2/1/0/0/0/0/2 |
| FAIL | geometry | BindingVariables#pitch-variables | box | [11.7, 34.1, 288.1, 216.8] | [12, 34, 287.5, 175.7] | [0.3, -0.1, -0.6, -41.1] | cause (examined, measured fact): code-built-children; displaced by tile-tactics|geometry|FMTacticsPanel#|box|P4/0/4/0/0/0/0/0/0/0/1/0/0/0/0/1/0/0/0/0/0/0/0/0/0/0/0/0/2/1/0/0/0/0/2 |
| PASS | geometry | VisualElement#TileHeaderElements | box | [11.7, 34.1, 288.1, 23.4] | [12, 34, 287.5, 24] | [0.3, -0.1, -0.6, 0.6] |  |
| FAIL | geometry | TemplateContainer#SetPiecesCell | box | [11.7, 34.1, 102.5, 23.4] | [12, 34, 88.9, 24] | [0.3, -0.1, -13.6, 0.6] | cause (examined, measured fact): runtime-class; displaced by tile-tactics|geometry|SIStyleSetter#IconStyleSetter|box|P4/0/4/0/0/0/0/0/0/0/1/0/0/0/0/1/0/0/0/0/0/0/0/0/0/0/0/0/2/1/0/0/0/0/0/0/0/0 |
| FAIL | geometry | SIButton#OpenCardButton | box | [11.7, 34.1, 102.5, 23.4] | [12, 34, 88.9, 24] | [0.3, -0.1, -13.6, 0.6] | cause (examined, measured fact): runtime-class; displaced by tile-tactics|geometry|SIStyleSetter#IconStyleSetter|box|P4/0/4/0/0/0/0/0/0/0/1/0/0/0/0/1/0/0/0/0/0/0/0/0/0/0/0/0/2/1/0/0/0/0/0/0/0/0 |
| FAIL | geometry | SIStyleSetter#IconStyleSetter | box | [20.5, 38.0, 15.6, 15.6] | [21, 46, 0, 0] | [0.5, 8.0, -15.6, -15.6] | cause (examined, measured fact): runtime-class |
| FAIL | geometry | SIText#CellText | box | [40.0, 35.1, 65.4, 21.5] | [25, 35.2, 66.9, 21.5] | [-15.0, 0.1, 1.5, 0.0] | cause (examined, measured fact): runtime-class; displaced by tile-tactics|geometry|SIStyleSetter#IconStyleSetter|box|P4/0/4/0/0/0/0/0/0/0/1/0/0/0/0/1/0/0/0/0/0/0/0/0/0/0/0/0/2/1/0/0/0/0/0/0/0/0 |
| FAIL | geometry | TemplateContainer#PenaltiesCell | box | [114.2, 34.1, 81.1, 23.4] | [120.8, 34, 69.9, 24] | [6.6, -0.1, -11.2, 0.6] | cause (examined, measured fact): runtime-class; displaced by tile-tactics|geometry|SIStyleSetter#IconStyleSetter|box|P4/0/4/0/0/0/0/0/0/0/1/0/0/0/0/1/0/0/0/0/0/0/0/0/0/0/0/0/2/1/0/0/0/0/0/0/0/0, tile-tactics|geometry|SIStyleSetter#IconStyleSetter|box|P4/0/4/0/0/0/0/0/0/0/1/0/0/0/0/1/0/0/0/0/0/0/0/0/0/0/0/0/2/1/0/0/0/0/0/1/0/0, tile-tactics|geometry|SIStyleSetter#IconStyleSetter|box|P4/0/4/0/0/0/0/0/0/0/1/0/0/0/0/1/0/0/0/0/0/0/0/0/0/0/0/0/2/1/0/0/0/0/0/2/0/0, tile-tactics|geometry|SIText#CellText|box|P4/0/4/0/0/0/0/0/0/0/1/0/0/0/0/1/0/0/0/0/0/0/0/0/0/0/0/0/2/1/0/0/0/0/0/1/0/1 |
| FAIL | geometry | SIButton#OpenCardButton | box | [122.0, 34.1, 65.4, 23.4] | [128.8, 34, 53.9, 24] | [6.8, -0.1, -11.5, 0.6] | cause (examined, measured fact): runtime-class; displaced by tile-tactics|geometry|SIStyleSetter#IconStyleSetter|box|P4/0/4/0/0/0/0/0/0/0/1/0/0/0/0/1/0/0/0/0/0/0/0/0/0/0/0/0/2/1/0/0/0/0/0/0/0/0, tile-tactics|geometry|SIStyleSetter#IconStyleSetter|box|P4/0/4/0/0/0/0/0/0/0/1/0/0/0/0/1/0/0/0/0/0/0/0/0/0/0/0/0/2/1/0/0/0/0/0/1/0/0, tile-tactics|geometry|SIStyleSetter#IconStyleSetter|box|P4/0/4/0/0/0/0/0/0/0/1/0/0/0/0/1/0/0/0/0/0/0/0/0/0/0/0/0/2/1/0/0/0/0/0/2/0/0, tile-tactics|geometry|SIText#CellText|box|P4/0/4/0/0/0/0/0/0/0/1/0/0/0/0/1/0/0/0/0/0/0/0/0/0/0/0/0/2/1/0/0/0/0/0/1/0/1 |
| FAIL | geometry | SIStyleSetter#IconStyleSetter | box | [130.8, 38.0, 15.6, 15.6] | [137.8, 46, 0, 0] | [7.0, 8.0, -15.6, -15.6] | cause (examined, measured fact): runtime-class |
| FAIL | geometry | SIText#CellText | box | [150.3, 35.1, 28.3, 21.5] | [141.8, 35.2, 31.9, 21.5] | [-8.5, 0.1, 3.6, 0.0] | cause (examined, magnitude only): stand-in-font |
| FAIL | geometry | TemplateContainer#OppositionInstructionsCell | box | [195.3, 34.1, 104.5, 23.4] | [210.6, 34, 88.9, 24] | [15.3, -0.1, -15.6, 0.6] | cause (examined, measured fact): runtime-class; displaced by tile-tactics|geometry|SIStyleSetter#IconStyleSetter|box|P4/0/4/0/0/0/0/0/0/0/1/0/0/0/0/1/0/0/0/0/0/0/0/0/0/0/0/0/2/1/0/0/0/0/0/0/0/0, tile-tactics|geometry|SIStyleSetter#IconStyleSetter|box|P4/0/4/0/0/0/0/0/0/0/1/0/0/0/0/1/0/0/0/0/0/0/0/0/0/0/0/0/2/1/0/0/0/0/0/1/0/0, tile-tactics|geometry|SIStyleSetter#IconStyleSetter|box|P4/0/4/0/0/0/0/0/0/0/1/0/0/0/0/1/0/0/0/0/0/0/0/0/0/0/0/0/2/1/0/0/0/0/0/2/0/0, tile-tactics|geometry|SIText#CellText|box|P4/0/4/0/0/0/0/0/0/0/1/0/0/0/0/1/0/0/0/0/0/0/0/0/0/0/0/0/2/1/0/0/0/0/0/1/0/1 |
| FAIL | geometry | SIButton#OpenCardButton | box | [195.3, 34.1, 104.5, 23.4] | [210.6, 34, 88.9, 24] | [15.3, -0.1, -15.6, 0.6] | cause (examined, measured fact): runtime-class; displaced by tile-tactics|geometry|SIStyleSetter#IconStyleSetter|box|P4/0/4/0/0/0/0/0/0/0/1/0/0/0/0/1/0/0/0/0/0/0/0/0/0/0/0/0/2/1/0/0/0/0/0/0/0/0, tile-tactics|geometry|SIStyleSetter#IconStyleSetter|box|P4/0/4/0/0/0/0/0/0/0/1/0/0/0/0/1/0/0/0/0/0/0/0/0/0/0/0/0/2/1/0/0/0/0/0/1/0/0, tile-tactics|geometry|SIStyleSetter#IconStyleSetter|box|P4/0/4/0/0/0/0/0/0/0/1/0/0/0/0/1/0/0/0/0/0/0/0/0/0/0/0/0/2/1/0/0/0/0/0/2/0/0, tile-tactics|geometry|SIText#CellText|box|P4/0/4/0/0/0/0/0/0/0/1/0/0/0/0/1/0/0/0/0/0/0/0/0/0/0/0/0/2/1/0/0/0/0/0/1/0/1 |
| FAIL | geometry | SIStyleSetter#IconStyleSetter | box | [204.1, 38.0, 15.6, 15.6] | [219.6, 46, 0, 0] | [15.5, 8.0, -15.6, -15.6] | cause (examined, measured fact): runtime-class |
| PASS | geometry | SIText#CellText | box | [223.6, 35.1, 67.4, 21.5] | [223.6, 35.2, 66.9, 21.5] | [-0.0, 0.1, -0.5, 0.0] |  |
| FAIL | geometry | BindableSwitchElement# | box | [11.7, 34.1, 288.1, 216.8] | [12, 34, 287.5, 175.7] | [0.3, -0.1, -0.6, -41.1] | cause (examined, measured fact): code-built-children; displaced by tile-tactics|geometry|FMTacticsPanel#|box|P4/0/4/0/0/0/0/0/0/0/1/0/0/0/0/1/0/0/0/0/0/0/0/0/0/0/0/0/2/1/0/0/0/0/2 |
| FAIL | geometry | SIImage# | box | [11.7, 34.1, 288.1, 216.8] | [12, 34, 287.5, 175.7] | [0.3, -0.1, -0.6, -41.1] | cause (examined, measured fact): code-built-children; displaced by tile-tactics|geometry|FMTacticsPanel#|box|P4/0/4/0/0/0/0/0/0/0/1/0/0/0/0/1/0/0/0/0/0/0/0/0/0/0/0/0/2/1/0/0/0/0/2 |
| FAIL | geometry | FMTacticsPanel# | box | [11.7, 82.0, 288.1, 161.1] | [12, 82, 287.5, 119.7] | [0.3, 0.0, -0.6, -41.4] | cause (examined, measured fact): code-built-children |
| FAIL | geometry | BindableSwitchElement#tactic-info-switch | box | [11.7, 250.9, 288.1, 52.7] | [12, 209.7, 287.5, 93.8] | [0.3, -41.2, -0.6, 41.1] | cause (examined, measured fact): code-built-children; displaced by tile-tactics|geometry|FMTacticsPanel#|box|P4/0/4/0/0/0/0/0/0/0/1/0/0/0/0/1/0/0/0/0/0/0/0/0/0/0/0/0/2/1/0/0/0/0/2 |
| N/A | geometry | SIText#text | box | null | [0, 0, 0, 0] |  | descendant of a switch branch the render chose not to show (one branch per switch): no live partner by design |
| FAIL | geometry | VisualElement#tactic-info-container | box | [11.7, 271.4, 288.1, 19.5] | [12, 250.6, 287.5, 20] | [0.3, -20.8, -0.6, 0.5] | cause (examined, measured fact): code-built-children; displaced by tile-tactics|geometry|FMTacticsPanel#|box|P4/0/4/0/0/0/0/0/0/0/1/0/0/0/0/1/0/0/0/0/0/0/0/0/0/0/0/0/2/1/0/0/0/0/2 |
| FAIL | geometry | VisualElement#formation-cells--unpacked | box | [11.7, 271.4, 288.1, 19.5] | [12, 250.6, 287.5, 20] | [0.3, -20.8, -0.6, 0.5] | cause (examined, measured fact): code-built-children; displaced by tile-tactics|geometry|FMTacticsPanel#|box|P4/0/4/0/0/0/0/0/0/0/1/0/0/0/0/1/0/0/0/0/0/0/0/0/0/0/0/0/2/1/0/0/0/0/2 |
| FAIL | geometry | VisualElement#data_display-cell-combo_cell-default-type-default-icon-size-medium-orientation-horizontal-combo-2-cell | box | [11.7, 271.4, 288.1, 19.5] | [12, 250.6, 287.5, 20] | [0.3, -20.8, -0.6, 0.5] | cause (examined, measured fact): code-built-children; displaced by tile-tactics|geometry|FMTacticsPanel#|box|P4/0/4/0/0/0/0/0/0/0/1/0/0/0/0/1/0/0/0/0/0/0/0/0/0/0/0/0/2/1/0/0/0/0/2 |
| FAIL | geometry | VisualElement#frame | box | [70.3, 271.4, 170.9, 19.5] | [74.2, 250.6, 163.0, 20] | [3.9, -20.8, -7.9, 0.5] | cause (examined, measured fact): code-built-children; displaced by tile-tactics|geometry|FMTacticsPanel#|box|P4/0/4/0/0/0/0/0/0/0/1/0/0/0/0/1/0/0/0/0/0/0/0/0/0/0/0/0/2/1/0/0/0/0/2 |
| FAIL | geometry | BindingRemapper# | box | [70.3, 271.4, 78.1, 19.5] | [74.2, 250.6, 72.2, 20] | [3.9, -20.8, -5.9, 0.5] | cause (examined, measured fact): code-built-children; displaced by tile-tactics|geometry|FMTacticsPanel#|box|P4/0/4/0/0/0/0/0/0/0/1/0/0/0/0/1/0/0/0/0/0/0/0/0/0/0/0/0/2/1/0/0/0/0/2, tile-tactics|geometry|SIText#in-posession-formation-text|box|P4/0/4/0/0/0/0/0/0/0/1/0/0/0/0/1/0/0/0/0/0/0/0/0/0/0/0/0/2/1/1/0/0/0/0/0/0/1 |
| FAIL | geometry | VisualElement# | box | [70.3, 271.4, 74.2, 19.5] | [74.2, 250.6, 68.2, 20] | [3.9, -20.8, -6.0, 0.5] | cause (examined, measured fact): code-built-children; displaced by tile-tactics|geometry|FMTacticsPanel#|box|P4/0/4/0/0/0/0/0/0/0/1/0/0/0/0/1/0/0/0/0/0/0/0/0/0/0/0/0/2/1/0/0/0/0/2, tile-tactics|geometry|SIText#in-posession-formation-text|box|P4/0/4/0/0/0/0/0/0/0/1/0/0/0/0/1/0/0/0/0/0/0/0/0/0/0/0/0/2/1/1/0/0/0/0/0/0/1 |
| FAIL | geometry | VisualElement#game-concepts-in-possession_small | box | [70.3, 273.4, 15.6, 15.6] | [74.2, 252.6, 16, 16] | [3.9, -20.8, 0.4, 0.4] | cause (examined, measured fact): code-built-children; displaced by tile-tactics|geometry|FMTacticsPanel#|box|P4/0/4/0/0/0/0/0/0/0/1/0/0/0/0/1/0/0/0/0/0/0/0/0/0/0/0/0/2/1/0/0/0/0/2, tile-tactics|geometry|SIText#in-posession-formation-text|box|P4/0/4/0/0/0/0/0/0/0/1/0/0/0/0/1/0/0/0/0/0/0/0/0/0/0/0/0/2/1/1/0/0/0/0/0/0/1 |
| FAIL | geometry | SIText#in-posession-formation-text | box | [89.8, 271.4, 54.7, 20.5] | [94.2, 249.8, 48.2, 21.5] | [4.4, -21.6, -6.5, 1.0] | cause (examined, magnitude only): stand-in-font |
| FAIL | geometry | BindingRemapper# | box | [148.4, 271.4, 92.8, 19.5] | [146.5, 250.6, 90.8, 20] | [-1.9, -20.8, -2.0, 0.5] | cause (examined, measured fact): code-built-children; displaced by tile-tactics|geometry|FMTacticsPanel#|box|P4/0/4/0/0/0/0/0/0/0/1/0/0/0/0/1/0/0/0/0/0/0/0/0/0/0/0/0/2/1/0/0/0/0/2 |
| FAIL | geometry | VisualElement# | box | [148.4, 271.4, 92.8, 19.5] | [146.5, 250.6, 90.8, 20] | [-1.9, -20.8, -2.0, 0.5] | cause (examined, measured fact): code-built-children; displaced by tile-tactics|geometry|FMTacticsPanel#|box|P4/0/4/0/0/0/0/0/0/0/1/0/0/0/0/1/0/0/0/0/0/0/0/0/0/0/0/0/2/1/0/0/0/0/2 |
| FAIL | geometry | VisualElement#game-concepts-out-of-possession_small | box | [148.4, 273.4, 15.6, 15.6] | [146.5, 252.6, 16, 16] | [-1.9, -20.8, 0.4, 0.4] | cause (examined, no supporting fact): UNEXPLAINED |
| FAIL | geometry | SIText#out-of-possession-formation-text | box | [167.9, 271.4, 73.2, 20.5] | [166.5, 249.8, 70.8, 21.5] | [-1.4, -21.6, -2.4, 1.0] | cause (examined, measured fact): code-built-children; displaced by tile-tactics|geometry|FMTacticsPanel#|box|P4/0/4/0/0/0/0/0/0/0/1/0/0/0/0/1/0/0/0/0/0/0/0/0/0/0/0/0/2/1/0/0/0/0/2 |
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
| FAIL | values | SIStyleSetter#IconStyleSetter | flex-shrink | 0 | "1" |  | cause (examined, measured fact): runtime-class |
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
| FAIL | values | SIStyleSetter#IconStyleSetter | flex-shrink | 0 | "1" |  | cause (examined, measured fact): runtime-class |
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
| FAIL | values | SIStyleSetter#IconStyleSetter | flex-shrink | 0 | "1" |  | cause (examined, measured fact): runtime-class |
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
| FAIL | geometry | AutoScroller# | box | [11.7, 8.8, 288.1, 17.6] | [12, 2, 287.5, 32] | [0.3, -6.8, -0.6, 14.4] | cause (examined, measured fact): code-built-wrapper; displaced by tile-training|geometry|SIText#title-text|box|P4/0/4/0/0/0/0/0/0/0/1/0/0/0/0/2/0/0/0/0/0/0/0/0/0/1/1/0/0/0/0/0, tile-training|geometry|SIVisible#|box|P4/0/4/0/0/0/0/0/0/0/1/0/0/0/0/2/0/0/0/0/0/0/0/0/0/1/1/0/0/0/0/1 |
| FAIL | geometry | SIText#title-text | box | [11.7, 8.8, 46.9, 17.6] | [12, 2, 283.5, 16] | [0.3, -6.8, 236.6, -1.6] | cause (examined, measured fact): code-built-wrapper |
| FAIL | geometry | SIVisible# | box | [11.7, 8.8, 0, 0] | [12, 18, 287.5, 16] | [0.3, 9.2, 287.5, 16] | cause (examined, measured fact): inline-display-none |
| N/A | geometry | SIText#title-text-alt | box | null | [12, 18, 287.5, 16] |  | no live element paired: the drawn node has no partner in the capture (absent or not captured) |
| PASS | geometry | VisualElement#CarouselMask | box | [303.7, 1.9, 0, 32.2] | [303.5, 2, 0, 32] | [-0.2, 0.1, 0, -0.2] |  |
| PASS | geometry | TemplateContainer#states-templates-tile-content | box | [0.0, 34.2, 311.5, 277.3] | [0, 34, 311.5, 277.5] | [0.0, -0.2, 0.0, 0.2] |  |
| FAIL | geometry | ComponentElement# | box | [11.7, 34.2, 288.1, 222.7] | [12, 34, 287.5, 118.3] | [0.3, -0.2, -0.6, -104.4] | cause (examined, measured fact): empty-code-list; displaced by tile-training|geometry|StreamedObjectList#Week|box|P4/0/4/0/0/0/0/0/0/0/1/0/0/0/0/2/0/0/0/0/0/0/0/0/0/2/0/0/1 |
| FAIL | geometry | VisualElement#TrainingTile | box | [11.7, 34.2, 288.1, 269.5] | [12, 34, 287.5, 118.3] | [0.3, -0.2, -0.6, -151.2] | cause (examined, no supporting fact): UNEXPLAINED |
| PASS | geometry | SIText#ScheduleTitle | box | [11.7, 34.2, 288.1, 18.6] | [12, 34, 287.5, 18.6] | [0.3, -0.2, -0.6, -0.0] |  |
| FAIL | geometry | StreamedObjectList#Week | box | [8.7, 60.5, 293.9, 105.5] | [155.8, 60.6, 0, 0] | [147.0, 0.1, -293.9, -105.5] | cause (examined, measured fact): empty-code-list |
| FAIL | geometry | TemplateContainer#Divider | box | [11.7, 181.6, 288.1, 1] | [12, 76.6, 287.5, 1] | [0.3, -105.0, -0.6, 0] | cause (examined, measured fact): empty-code-list; displaced by tile-training|geometry|StreamedObjectList#Week|box|P4/0/4/0/0/0/0/0/0/0/1/0/0/0/0/2/0/0/0/0/0/0/0/0/0/2/0/0/1 |
| FAIL | geometry | VisualElement#layout-divider-solid-horizontal | box | [11.7, 181.6, 288.1, 1] | [12, 76.6, 287.5, 1] | [0.3, -105.0, -0.6, 0] | cause (examined, measured fact): empty-code-list; displaced by tile-training|geometry|StreamedObjectList#Week|box|P4/0/4/0/0/0/0/0/0/0/1/0/0/0/0/2/0/0/0/0/0/0/0/0/0/2/0/0/1 |
| FAIL | geometry | SIText#IndividualTrainingTitle | box | [11.7, 198.2, 288.1, 18.6] | [12, 93.6, 287.5, 18.6] | [0.3, -104.6, -0.6, -0.0] | cause (examined, measured fact): empty-code-list; displaced by tile-training|geometry|StreamedObjectList#Week|box|P4/0/4/0/0/0/0/0/0/0/1/0/0/0/0/2/0/0/0/0/0/0/0/0/0/2/0/0/1 |
| FAIL | geometry | VisualElement#IndividualTraining | box | [11.7, 216.8, 288.1, 40] | [12, 112.2, 287.5, 40.1] | [0.3, -104.6, -0.6, 0.1] | cause (examined, measured fact): empty-code-list; displaced by tile-training|geometry|StreamedObjectList#Week|box|P4/0/4/0/0/0/0/0/0/0/1/0/0/0/0/2/0/0/0/0/0/0/0/0/0/2/0/0/1 |
| FAIL | geometry | VisualElement#Improvements | box | [11.7, 216.8, 151.4, 40] | [12, 112.2, 148.4, 40.1] | [0.3, -104.6, -3.0, 0.1] | cause (examined, measured fact): empty-code-list; displaced by tile-training|geometry|StreamedObjectList#Week|box|P4/0/4/0/0/0/0/0/0/0/1/0/0/0/0/2/0/0/0/0/0/0/0/0/0/2/0/0/1 |
| FAIL | geometry | VisualElement#Stat | box | [11.7, 216.8, 143.6, 21.5] | [12, 112.2, 140.4, 21.5] | [0.3, -104.6, -3.2, 0.0] | cause (examined, measured fact): empty-code-list; displaced by tile-training|geometry|StreamedObjectList#Week|box|P4/0/4/0/0/0/0/0/0/0/1/0/0/0/0/2/0/0/0/0/0/0/0/0/0/2/0/0/1 |
| FAIL | geometry | SIImage#Arrow | box | [11.7, 216.8, 15.6, 16.6] | [12, 112.2, 0, 21.5] | [0.3, -104.6, -15.6, 4.9] | cause (examined, measured fact): runtime-class |
| FAIL | geometry | SIText#Value | box | [27.3, 216.8, 20.5, 21.5] | [12, 112.2, 19.6, 21.5] | [-15.3, -104.6, -0.9, 0.0] | cause (examined, measured fact): runtime-class; displaced by tile-training|geometry|SIImage#Arrow|box|P4/0/4/0/0/0/0/0/0/0/1/0/0/0/0/2/0/0/0/0/0/0/0/0/0/2/0/0/4/0/0/0, tile-training|geometry|StreamedObjectList#Week|box|P4/0/4/0/0/0/0/0/0/0/1/0/0/0/0/2/0/0/0/0/0/0/0/0/0/2/0/0/1 |
| FAIL | geometry | SIText#Title | box | [11.7, 238.3, 143.6, 18.6] | [12, 133.7, 140.4, 18.6] | [0.3, -104.6, -3.2, -0.0] | cause (examined, measured fact): empty-code-list; displaced by tile-training|geometry|StreamedObjectList#Week|box|P4/0/4/0/0/0/0/0/0/0/1/0/0/0/0/2/0/0/0/0/0/0/0/0/0/2/0/0/1 |
| FAIL | geometry | VisualElement#Regressions | box | [163.0, 216.8, 136.7, 40] | [160.4, 112.2, 139.1, 40.1] | [-2.6, -104.6, 2.4, 0.1] | cause (examined, measured fact): empty-code-list; displaced by tile-training|geometry|StreamedObjectList#Week|box|P4/0/4/0/0/0/0/0/0/0/1/0/0/0/0/2/0/0/0/0/0/0/0/0/0/2/0/0/1 |
| FAIL | geometry | VisualElement#Stat | box | [170.9, 216.8, 128.9, 21.5] | [168.4, 112.2, 131.1, 21.5] | [-2.5, -104.6, 2.2, 0.0] | cause (examined, measured fact): empty-code-list; displaced by tile-training|geometry|StreamedObjectList#Week|box|P4/0/4/0/0/0/0/0/0/0/1/0/0/0/0/2/0/0/0/0/0/0/0/0/0/2/0/0/1 |
| FAIL | geometry | SIImage#Arrow | box | [170.9, 216.8, 15.6, 16.6] | [168.4, 112.2, 0, 21.5] | [-2.5, -104.6, -15.6, 4.9] | cause (examined, measured fact): runtime-class |
| FAIL | geometry | SIText#Value | box | [186.5, 216.8, 13.7, 21.5] | [168.4, 112.2, 11.8, 21.5] | [-18.1, -104.6, -1.9, 0.0] | cause (examined, magnitude only): stand-in-font |
| FAIL | geometry | SIText#Title | box | [170.9, 238.3, 128.9, 18.6] | [168.4, 133.7, 131.1, 18.6] | [-2.5, -104.6, 2.2, -0.0] | cause (examined, measured fact): empty-code-list; displaced by tile-training|geometry|StreamedObjectList#Week|box|P4/0/4/0/0/0/0/0/0/0/1/0/0/0/0/2/0/0/0/0/0/0/0/0/0/2/0/0/1 |
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
| FAIL | values | SIButton#layout-tile-interaction-button | background-color | "#17223F" | "#1E2129" |  | cause (examined, magnitude only): runtime-sheet-colour |
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
| FAIL | values | SIImage#Arrow | flex-shrink | 0 | "1" |  | cause (examined, measured fact): runtime-class |
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
| FAIL | values | SIImage#Arrow | flex-shrink | 0 | "1" |  | cause (examined, measured fact): runtime-class |
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
