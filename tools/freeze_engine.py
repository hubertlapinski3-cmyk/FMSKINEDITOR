"""Freeze the engine into a one-dir PyInstaller bundle: the sidecar the Studio shell starts, so the user needs no Python, venv or pip.

    python tools/freeze_engine.py [--out DIR] [--name NAME]

Output: <out>/<name>/<name>[.exe] plus its _internal folder. Data the engine reads at run time is bundled under the same relative names
`config.resource_root()` already expects (frontend/, data/, docs/INGAME-CHECKLIST.md). Build on the platform you ship for: PyInstaller does not cross-compile
(macOS and Linux builds run on macOS and Linux; see docs/PHASE8-PLAN.md)."""
import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def command(out, name):
    sep = os.pathsep
    cmd = [sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", "--onedir", "--console", "--name", name,
           "--distpath", str(out), "--workpath", str(out / "_work"), "--specpath", str(out / "_work"),
           "--paths", str(ROOT),
           "--add-data", "%s%sfrontend" % (ROOT / "frontend", sep),
           "--add-data", "%s%sdata" % (ROOT / "data", sep),
           "--add-data", "%s%sdocs" % (ROOT / "docs" / "INGAME-CHECKLIST.md", sep),
           # UnityPy loads its typetree and resource files by path, and texture codecs are C extensions imported by name
           "--collect-all", "UnityPy", "--collect-all", "texture2ddecoder", "--collect-all", "etcpak",
           "--hidden-import", "skin_editor.api.methods", "--hidden-import", "skin_editor.table_usage", "--hidden-import", "skin_editor.userdirs",
           str(ROOT / "tools" / "engine_entry.py")]
    return cmd


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(ROOT / "build-sidecar"))
    ap.add_argument("--name", default="fm-skin-engine")
    a = ap.parse_args()
    out = Path(a.out).resolve()
    if (out / a.name).exists():
        shutil.rmtree(out / a.name)
    r = subprocess.run(command(out, a.name), cwd=str(ROOT))
    if r.returncode:
        return r.returncode
    exe = out / a.name / (a.name + (".exe" if sys.platform == "win32" else ""))
    print("frozen engine:", exe, "(exists)" if exe.is_file() else "(MISSING)")
    return 0 if exe.is_file() else 1


if __name__ == "__main__":
    sys.exit(main())
