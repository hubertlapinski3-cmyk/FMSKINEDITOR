"""No test and no tool may contain the live game's folder as a literal. They read the CONFIGURED game folder (`config.load()["aa_dir"]` / `["game_dir"]`, which FM27SE_WORKSPACE redirects), so a run can be pointed at an archived
bundle set and can never touch the live game by accident (the owner's rule of 2026-11-17, after a suite run read the live bundles through a typed path in tools/m3_exit_compare.py)."""
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SUFFIXES = {".py", ".ps1", ".sh", ".bat", ".cmd"}
# built from pieces so that this file does not contain the literal it forbids
SEP = r"[\\/]+"
LIVE = re.compile(SEP.join([r"Program Files \(x86\)", "Steam", "steamapps", "common", "Football Manager 27"]), re.I)


def files():
    for folder in ("tests", "tools"):
        for p in sorted((ROOT / folder).rglob("*")):
            if p.is_file() and p.suffix.lower() in SUFFIXES and "__pycache__" not in p.parts and "node_modules" not in p.parts:
                yield p


class NoLiveGamePath(unittest.TestCase):
    def test_no_test_or_tool_contains_the_live_game_folder_as_a_literal(self):
        hits = []
        for p in files():
            text = p.read_text(encoding="utf-8-sig", errors="replace")
            for i, line in enumerate(text.splitlines(), 1):
                if LIVE.search(line):
                    hits.append("%s:%d" % (p.relative_to(ROOT).as_posix(), i))
        self.assertEqual(hits, [], "the live game path is typed here; read config.load() instead (see tests/gamebuild.py)")

    def test_the_scan_sees_the_files_it_is_meant_to_scan(self):
        names = {p.name for p in files()}
        self.assertTrue({"gamebuild.py", "freeze_engine.py", "test_uxml.py"} <= names)
        parts = ["Program Files (x86)", "Steam", "steamapps", "common", "Football Manager 27"]
        self.assertTrue(LIVE.search("C:\\" + "\\".join(parts) + "\\fm_Data"))
        self.assertTrue(LIVE.search("c:/" + "/".join(parts).lower()))
        self.assertFalse(LIVE.search("C:\\Users\\example\\FM\\bundle-sets"))


if __name__ == "__main__":
    unittest.main()
