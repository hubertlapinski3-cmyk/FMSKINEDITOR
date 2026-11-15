"""S5 of the Simple mode plan: every layout the Simple mode showcase opens with is one the calibration measured against the game."""
import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def showcase_names():
    text = (ROOT / "studio" / "src" / "showcase.ts").read_text(encoding="utf-8")
    return re.findall(r"name: '([^']+)'", text)


def calibrated_layout_names():
    names = set()
    for f in (ROOT / "tests" / "fixtures" / "render").glob("*/fixture.json"):
        d = json.loads(f.read_text(encoding="utf-8-sig"))
        if isinstance(d.get("layout"), dict) and d["layout"].get("name"):
            names.add(d["layout"]["name"])
    return names


class Showcase(unittest.TestCase):
    def test_every_showcase_layout_is_a_layout_the_calibration_measured(self):
        names, measured = showcase_names(), calibrated_layout_names()
        self.assertGreaterEqual(len(names), 5)
        self.assertEqual(len(names), len(set(names)), "no layout twice")
        self.assertEqual([n for n in names if n not in measured], [], "a showcase layout the calibration did not measure")

    def test_the_labels_are_plain_words(self):
        text = (ROOT / "studio" / "src" / "showcase.ts").read_text(encoding="utf-8")
        for label in re.findall(r"label: '([^']+)'", text):
            self.assertNotRegex(label, r"[_\d]", "a label is words, not the game's layout name: " + label)


if __name__ == "__main__":
    unittest.main()
