"""Cell pitch per composition (docs/PHASE9-PLAN.md section 5): measured values only, estimates clearly flagged.

`lookup(name)` returns {"cell", "gap", "measured", "source"} for a composition with an entry in pitch.json, and for any other composition the 66 / 16 starting figure
of the c2 session with `measured: False` and a `flag` that says it is an estimate: callers must carry that flag into the render and keep the composition out of any
pixel-faithful claim. There is no silent global default.

`extent(n, pitch)` is the size of n cells with the gaps between them; `stride` is cell + gap (where the next cell starts)."""
import json
from pathlib import Path

_FILE = Path(__file__).with_name("pitch.json")
ESTIMATE = {"cell": 66.0, "gap": 16.0}


def table():
    return json.loads(_FILE.read_text(encoding="utf-8"))["compositions"]


def lookup(composition):
    t = table().get(composition)
    if t:
        return {"cell": t["cell"], "gap": t["gap"], "measured": True, "source": t["context"], "flag": None}
    return dict(ESTIMATE, measured=False, source="c2 session, one 4x2 Loans tile",
                flag="ESTIMATE: no measured pitch for composition %r; excluded from pixel-faithful claims" % composition)


def extent(n, p):
    return n * p["cell"] + max(0, n - 1) * p["gap"]


def stride(p):
    return p["cell"] + p["gap"]
