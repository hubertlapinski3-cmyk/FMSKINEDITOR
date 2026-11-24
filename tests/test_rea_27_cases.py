"""Self-contained 27-case REA layout benchmark on release/1.5 (REA_RULE_PASS 27/27)."""
import json
import unittest
from pathlib import Path

from skin_editor.render import preview, rea_rule, screen

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "rea_27_cases.json"
ROOT = Path(__file__).resolve().parent.parent


class _MiniAssembler:
    def __init__(self, c):
        self.cells = {c["composition"]: list(c["cells"])}
        self.optional_slices = dict(c.get("optional_slices") or {})
        self.layout_modes = {c["composition"]: int(c.get("layout_mode", 0))}
        self._dw, self._dh = c["design_size"]

    def design_size(self, _comp):
        return self._dw, self._dh


def _compare(measured, predicted, tol):
    rows = []
    for k, m in measured.items():
        p = predicted.get(k)
        if p is None:
            rows.append({"host": k, "predicted": None, "max": None})
            continue
        dx = abs(m[0] - p[0])
        dy = abs(m[1] - p[1])
        dw = abs(m[2] - p[2])
        dh = abs(m[3] - p[3])
        rows.append({"host": k, "predicted": p, "max": max(dx, dy, dw, dh)})
    scored = [r for r in rows if r["predicted"] is not None]
    worst = max((r["max"] for r in scored), default=0.0)
    failing = [r["host"] for r in scored if r["max"] > tol]
    return {"scored_hosts": len(scored), "pass": bool(scored) and not failing, "worst_px": round(worst, 2), "failing": failing}


class ReaRule27Cases(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = json.loads(FIXTURE.read_text(encoding="utf-8"))
        cls.tol = cls.data["tol"]
        cls.mini_dump = cls.data["mini_dump"]
        cls.results = []
        for c in cls.data["cases"]:
            if c["mode"] == "place_rule":
                a = _MiniAssembler(c)
                placed = rea_rule.place_rule(a, c["composition"], (c["cols"], c["rows"]), reflow=c["reflow"])
                rect = c["rect"]
                pred = {}
                for eid, g in placed.items():
                    px = screen.cell_px(g["col"], g["row"], g["w"], g["h"], padding=c["padding"])
                    pred[eid] = [round(rect[0] + px["left"], 1), round(rect[1] + px["top"], 1),
                                 round(px["width"], 1), round(px["height"], 1)]
                score = _compare(c["measured"], pred, cls.tol)
            elif c["mode"] == "profile_hosts":
                got = preview.profile_hosts(cls.mini_dump, show_tactical_effectiveness=c["show_tactical_effectiveness"], custom=c["custom"])
                mm = c["measured_sorted"]
                pp = sorted(got["hosts"], key=lambda h: (h["row"], h["col"]))
                measured = {"%d:%s" % (i, h["element_id"]): h["rect"] for i, h in enumerate(mm)}
                predicted = {"%d:%s" % (i, p["element_id"]): p["rect"] for i, p in enumerate(pp)}
                score = _compare(measured, predicted, cls.tol)
            elif c["mode"] == "screen_hosts":
                got = preview.screen_hosts(cls.mini_dump, c["composition"], c["rect"], c["reflow"], custom=c["custom"])
                score = _compare(c["measured"], {h["element_id"]: h["rect"] for h in got}, cls.tol)
            else:
                raise AssertionError("unknown mode: %r" % (c["mode"],))
            cls.results.append(dict(score, case=c["case"], composition=c["label"]))

    def test_all_27_cases_score_pass(self):
        self.assertEqual(len(self.results), 27)
        passed = sum(1 for r in self.results if r["pass"])
        print("REA_RULE_PASS %d/27 (one_rule baseline 27/27)" % passed)
        self.assertEqual(passed, 27, [r for r in self.results if not r["pass"]])

    def test_port_does_not_import_one_rule(self):
        source = (ROOT / "skin_editor" / "render" / "rea_rule.py").read_text(encoding="utf-8")
        imports = [ln for ln in source.splitlines() if ln.startswith("import ") or ln.startswith("from ")]
        self.assertFalse(any("one_rule" in ln for ln in imports))


if __name__ == "__main__":
    unittest.main()
