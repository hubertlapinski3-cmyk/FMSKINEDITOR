"""M3 exit comparison as a regression gate: re-runs tools/m3_exit_compare.py against the stored captures (skipped where they are not present) and requires zero failures."""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
UI = Path(r"C:\Users\Admin\FMSKINNING\workspace\notes\ui-dumps")
NEED = ["styles-d1-squad-overview-20261114-111054.ndjson", "styles-d6-squad-overview-medium-20261114-113402.ndjson", "styles-d2-team-instructions-20261114-111314.ndjson", "styles-e2-squad-small-20261114-115336.ndjson", "styles-e3-squad-1152x864-20261114-115626.ndjson", "styles-e4-squad-1600x900-20261114-115839.ndjson"]


@unittest.skipUnless(all((UI / n).is_file() for n in NEED), "needs the Session D captures")
class ExitCompare(unittest.TestCase):
    def test_every_predicted_host_passes_and_extra_slots_are_placeholders(self):
        out = tempfile.mkdtemp()
        r = subprocess.run([sys.executable, str(ROOT / "tools" / "m3_exit_compare.py"), "--out", out], capture_output=True, text=True, cwd=str(ROOT))
        self.assertEqual(r.returncode, 0, r.stderr[-400:])
        rep = json.loads((Path(out) / "phase9-m3-exit-compare-20261114.json").read_text(encoding="utf-8"))
        self.assertEqual({f["id"]: (f["passed"], f["failed"]) for f in rep["fixtures"]}, {"squad-large": (5, 0), "squad-medium": (5, 0), "squad-small-display": (5, 0), "squad-small-composition": (5, 0), "squad-standard-composition": (5, 0), "teaminstr": (3, 0)})
        self.assertEqual(sum(len(f["runtime_slots"]) for f in rep["fixtures"]), 9)


if __name__ == "__main__":
    unittest.main()
