# Diff of the revised calibration report against the shipped 1.0.0 report (computed)

Totals: shipped {'PASS': 680, 'FAIL': 78, 'N/A': 435}, revised {'PASS': 683, 'FAIL': 80, 'N/A': 435}.

Rows in both: 1193. Verdict, expected or got changed on a shared row: 0. Rows only in the revised report: 5. Rows only in the shipped report: 0.

Rows added (verdict, fixture, check, property):
- FAIL | state-i3-session-g | nav-tab-label-as-read | color (rest)
- FAIL | state-i3-session-g | nav-tab-label-as-read | color (enabled)
- PASS | state-i3-session-g | nav-tab-label-as-read-runtime-sheet | color (rest)
- PASS | state-i3-session-g | nav-tab-label-as-read-runtime-sheet | color (enabled)
- PASS | tile-loans | hover-captured | background-color (enabled+hover)

Cause label changes on the 78 shared FAIL rows (shipped label start, examined cause): 19 distinct pairs.

- code-built content: the tactics pitch an -> code-built-children: 18
- code-built content: the Training tile's  -> empty-code-list: 12
- code-built content: the tactics pitch an -> runtime-class: 10
- component-drawn image (SIImage, SIStyleS -> runtime-class: 5
- run-time club-colour sheet (an empty-nam -> runtime-sheet-colour: 4
- bound text, scroller or list width: the  -> code-built-wrapper: 4
- bound text, scroller or list width: the  -> UNEXPLAINED: 3
- bound text, scroller or list width: the  -> stand-in-font: 3
- code-built content: the tactics pitch an -> UNEXPLAINED: 3
- code-built content: the Training tile's  -> runtime-class: 3
- bound text, scroller or list width: the  -> inline-display-none: 2
- sub-pixel offset on a very small element -> sub-pixel-tolerance: 2
- code-built content: the tactics pitch an -> stand-in-font: 2
- code-built content: the Training tile's  -> code-built-wrapper: 2
- code-built or binding-driven colour (not -> UNEXPLAINED: 1
- code-built or binding-driven colour (not -> state-captured: 1
- code-built content: the Training tile's  -> inline-display-none: 1
- code-built content: the Training tile's  -> UNEXPLAINED: 1
- code-built content: the Training tile's  -> stand-in-font: 1

New fields on rows: id, kind, live, node, value_source, na_reason, stage, given, exam, cause_key, cause_grade, legacy_cause, conditional, variant_of, observation, interpretations. New top-level blocks: coverage (also under totals), examination, grid, duplicates. New sections in the markdown: coverage block above the totals, the row-by-row examination, grid scoping.
