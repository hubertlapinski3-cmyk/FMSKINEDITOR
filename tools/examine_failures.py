"""Fix round problem 1: run every calibration fixture, examine every FAIL row and print/save the result.

    python tools/examine_failures.py OUT.json
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from skin_editor.render import causes, fixtures        # noqa: E402


def main(out):
    ctx = fixtures.Context()
    results = fixtures.run_all(ctx)
    exams = causes.examine_all(ctx, results)
    rows = [dict(x, fixture=r["name"]) for r in results for x in r["rows"] if x["verdict"] == "FAIL"]
    Path(out).write_text(json.dumps(rows, indent=1, default=str), encoding="utf-8")
    print(len(rows), "FAIL rows examined; wrote", out)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "examined.json")