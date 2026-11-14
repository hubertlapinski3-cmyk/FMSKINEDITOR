# Phase 9 M4 exit report (2026-11-14, build 27.0.1.2503222)

M4 asked for: images, icons, fonts, placeholders, notice; exit "icons and textures show; data is labelled". Built and verified offline, no game time. Full suite 297 engine tests and 45 studio tests pass.

## What was built
1. **Resolver** `render/assets.py` (`AssetResolver`): `asset(F:P)` -> the target object, always against the bundle the SHEET was read from (externals of that bundle -> CAB -> bundle -> object by path id). Index of 551 CABs built in 9 s and cached; loads a bundle together with the bundles its externals name so a Sprite reaches its atlas; every result memoised. An unresolvable reference returns the failing step, never a guess.
2. **Images:** Sprite and Texture2D targets drawn as PNG data URLs and applied as the node's `background-image` (Unity's default stretch); resolved values flip from `partial` to `mapped` with the source named in the note.
3. **Tint:** `-unity-background-image-tint-color` is applied by multiplying the image (Unity's rule) and flipped to `mapped` where applied.
4. **Fonts:** the UI font is a TextMeshPro SDF asset (ABC Social), so no SDF rendering is attempted: each text node names its family (`ABCSocial Regular`, in `node.font`, `data-font`, the tooltip) and the installed stand-in font draws it. Inherited font values reuse the declaring ancestor's resolution (their own sheet is not recorded).
5. **Placeholders and notice:** bound text is labelled `set` / `sample` / `empty` (`node.placeholder`): the layout's own designer sample (`DebugDisplay`, TextCase applied) stands in and is underlined with dots in both the HTML and the Studio view, with a tooltip saying it is not the delivered value; an unresolved image gets a dashed outline and the reason in its note. A switch element draws ONE branch (first, or the live one inferred from a capture by structural overlap, `captures.infer_branches`), says `branches` / `shown`, and marks the others `switch-branch-not-shown`. The permanent notice now names these.

## Exit check: tiles with assets resolved
| Tile | Assets (images / fonts / unresolved) | Text labelled | Box comparison with the capture of the same tile |
|---|---|---|---|
| LoansTile_4x2 | 0 / 3 / 0 (no USS icons in this layout) | 2 sample | 16 of 17 pass; the failure is the bound-text `AutoScroller` width |
| MedicalCentreTile_4x2 | 4 / 7 / 0 | 6 sample | 26 of 33 pass (branch inferred from the capture: the second, as read live) |
| TacticsTile_4x4 | 3 / 11 / 0 | 7 sample | 17 of 51 pass |
| SquadAtmosphereTile_4x2, TrainingTile_4x4 | 0 / 5 / 0 and 0 / 9 / 0 | 4 and 8 sample | not compared in this pass |

Visual proof: `docs/evidence/phase9-m4-render-MedicalCentreTile_4x2-20261114.png` (the injured and risk icons drawn from the game's own sprites, sample text underlined) and `phase9-m4-render-TacticsTile_4x4-20261114.png`. Spike reports: `phase9-m4-spike-medical-20261114.json`, `phase9-m4-spike-tactics-20261114.json`.

**Icon boxes against the captures (the exit check):**
- Medical Centre, both icons PASS in position and size: injured icon expected 23.4 x 24.4, drawn 24 x 24 (delta 0.6 / -0.4); risk icon expected 15.6 x 16.6, drawn 16 x 16.
- Tactics, both icons: SIZE passes (15.6 expected, 16 drawn), POSITION FAILS (x +30.8 and +9.4, y -20.8). Cause: the pitch above them is code-built (216.8 high live, 175.7 in the render) and the cell widths follow bound text; the low-res pitch sprite sits in the switch branch the capture says is not live. Published as a failure, not re-toleranced.

Remaining Medical Centre failures (7 of 33), all in named categories: the title `AutoScroller` and `title-text` (3, bound text and scroller), the two bound text widths (live "4 players injured" 147.5, sample "7 players injured" in a stand-in font 127.2; 143.6 vs 131.4), and the two 1 px dividers whose sub-pixel offset (0.3 to 0.6) exceeds a tolerance of 5 percent of 1 px. The Tactics failures are dominated by the code-built pitch and bound text.

## Performance
Warm render with assets: 1.4 ms (Loans), 3.5 ms (Medical Centre), 4.5 ms (Tactics), 0.2 ms (SquadScreen) against the 200 ms budget. Cold first calls: Loans 1,026 ms (cascade and sheet index load), Medical Centre 207 ms (icon bundle and atlas load), Tactics 21 ms. A first version re-resolved every reference per call (0.5 to 2 s warm); memoising fixed it.

## Named gaps (not blockers)
1. Component images (`SIImage`, `SIGradient`: 1 in Tactics, 2 in Training) are not drawn: their images come from component fields, not USS values.
2. Font rendering: names only, by design (SDF); the stand-in changes text widths.
3. Bound text widths: sample text, not delivered; the capture's delivered text can replace it where one exists (reader ready, not wired into the render call).
4. Code-built content (the tactics pitch and its players) is not drawn.
5. An inline asset value in a nested layout is resolved against the top layout's bundle (flagged in the code path; none occurred in these tiles).
6. Atmosphere and Training were not box-compared in this pass.

## Status
M4 closed on this report with the gaps above. Next: M5, the project overlay and the vanilla/skin toggle.