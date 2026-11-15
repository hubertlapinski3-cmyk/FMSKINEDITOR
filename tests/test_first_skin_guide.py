"""S8: the one-page guide (docs/FIRST-SKIN.md) names only buttons the Studio has. Every **bold** label in it must occur in the Studio's source, so a renamed button fails here
instead of leaving the guide wrong. The README points to the guide. Runs without the game."""
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GUIDE = (ROOT / "docs" / "FIRST-SKIN.md").read_text(encoding="utf-8")
STUDIO = "\n".join(p.read_text(encoding="utf-8") for p in (ROOT / "studio" / "src").glob("*.ts*") if ".test." not in p.name)
NOT_LABELS = {"bold", "Before you start:", "Start from a ready-made theme:", "Make a theme from three colours:", "Open a skin I downloaded:", "Start from the game's look:",
              "Colours:", "Look at it:", "Pictures:", "not yet been looked at in the game"}


def labels():
    return [m for m in re.findall(r"\*\*(.+?)\*\*", GUIDE)]


class Guide(unittest.TestCase):
    def test_every_bold_label_in_the_guide_is_in_the_studio(self):
        studio = STUDIO.replace("&apos;", "'")
        named = [lab for lab in labels() if lab not in NOT_LABELS]          # the rest are a section's own lead words, not buttons
        self.assertEqual([lab for lab in named if lab not in studio], [], "the guide names buttons the Studio does not have")
        self.assertGreater(len(named), 15)

    def test_the_start_choices_and_the_navigation_are_named_as_the_studio_names_them(self):
        for lab in ("Start from a ready-made theme", "Make a theme from three colours", "Open a skin I downloaded", "Start from the game's look",
                    "Colours", "Look at it", "Pictures", "Put it in the game", "Share and undo"):
            self.assertIn(lab, GUIDE)
            self.assertIn(lab, STUDIO.replace("&apos;", "'"), lab)

    def test_the_readme_points_to_the_guide(self):
        self.assertIn("docs/FIRST-SKIN.md", (ROOT / "README.md").read_text(encoding="utf-8"))


class ApiDoc(unittest.TestCase):
    def test_docs_api_lists_every_method_the_engine_has(self):
        from skin_editor.api.methods import methods
        doc = (ROOT / "docs" / "API.md").read_text(encoding="utf-8")
        missing = [name for name in methods() if "`%s`" % name not in doc]
        self.assertEqual(missing, [], "regenerate the table: python -m skin_editor methods --markdown")


if __name__ == "__main__":
    unittest.main()
