# Diff of the new calibration report against the frozen one (computed)

Totals: frozen {'PASS': 683, 'FAIL': 80, 'N/A': 435}, new {'PASS': 638, 'FAIL': 80, 'N/A': 410}.

Rows with the same key in both: 1101. Verdict flipped: 10. Same verdict but another expected or got value: 8. Only in the frozen report: 97. Only in the new report: 27.

## Verdict flipped (frozen -> new)

- tile-atmosphere: PASS -> N/A x 2
- tile-loans: PASS -> N/A x 1
- tile-medical-centre: PASS -> N/A x 2
- tile-tactics: N/A -> PASS x 1
- tile-tactics: PASS -> N/A x 2
- tile-training: PASS -> N/A x 2

## Only in the frozen report (rows no longer emitted or re-keyed)

- state-i3-session-g: FAIL x 3
- state-i3-session-g: N/A x 3
- state-i3-session-g: PASS x 22
- tile-atmosphere: FAIL x 1
- tile-atmosphere: N/A x 9
- tile-atmosphere: PASS x 9
- tile-loans: N/A x 3
- tile-loans: PASS x 3
- tile-medical-centre: FAIL x 1
- tile-medical-centre: N/A x 9
- tile-medical-centre: PASS x 9
- tile-tactics: N/A x 3
- tile-tactics: PASS x 3
- tile-training: FAIL x 1
- tile-training: N/A x 9
- tile-training: PASS x 9

## Only in the new report

- state-i3-session-g: FAIL x 3
- state-i3-session-g: N/A x 3
- state-i3-session-g: PASS x 18
- tile-atmosphere: FAIL x 1
- tile-medical-centre: FAIL x 1
- tile-training: FAIL x 1

