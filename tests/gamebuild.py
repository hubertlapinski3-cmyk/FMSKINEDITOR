"""Tests that read the game's bundles declare the build they were written against. When the configured game folder is another build they are reported as "not run, build mismatch" instead of failing.

The game folder is the CONFIGURED one (`config.load()["aa_dir"]`, which `FM27SE_WORKSPACE` redirects), never a path typed into a test. The check reads one small file, `catalog.hash`, next to the bundles.
Declared build: 27.0.1.2503222, catalog hash dfa1892e861eef5fd9c26d5c909a552f (bundle set B of docs/UIDOCUMENT-AUDIT.md, the reference build of the calibration evidence)."""
import unittest
from pathlib import Path

EXPECTED_LABEL = "27.0.1.2503222"
EXPECTED_CATALOG = "dfa1892e861eef5fd9c26d5c909a552f"


def aa():
    """The configured platform folder (a Path; `Path("")` when none is configured)."""
    from skin_editor import config
    v = (config.load() or {}).get("aa_dir")
    return Path(v) if v else Path("no-game-configured")


def catalog_of(folder):
    folder = Path(folder)
    for p in (folder / "catalog.hash", folder.parent / "catalog.hash"):
        if p.is_file():
            return p.read_text(encoding="utf-8", errors="replace").strip()
    return None


def mismatch(folder=None):
    """A reason string when the game folder is not the declared build, else None. A folder that is not there is left to the tests' own 'needs the game' skips."""
    folder = Path(folder) if folder else aa()
    if not folder.is_dir():
        return None
    cat = catalog_of(folder)
    if cat == EXPECTED_CATALOG:
        return None
    return "not run, build mismatch: written against %s (catalog %s), the configured game is %s" % (EXPECTED_LABEL, EXPECTED_CATALOG[:8], (cat or "of unknown build (no catalog.hash)")[:8])


def requires_build(obj):
    """Class or function decorator: skip with the build-mismatch reason when the configured game is not the declared build."""
    why = mismatch()
    return unittest.skip(why)(obj) if why else obj
