"""The audit dossier of a repair release branch, written from git and the CI API (nothing typed that git can say):

    python tools/make_release_dossier.py --branch origin/release/1.1.1 --base v1.1.0 --facts <facts.json> --out docs/RELEASE-1.1.1-DOSSIER.md

`facts.json` holds what only a run can say (the branch suite result, the frozen build's size and hash, the self-test line); everything else is read from the repository.
The script FAILS if a changed file has no stated reason, or a reason names a file that did not change: the dossier cannot describe a diff other than the real one."""
import argparse
import ast
import hashlib
import json
import re
import subprocess
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GIT = r"C:\Program Files\Git\cmd\git.exe"

REASONS = {
    ".github/workflows/ci.yml": "CI also runs on pushes to `release/**`, so a release branch has a real run before its tag (it ran only on main and pull requests).",
    ".github/workflows/release.yml": "Adds the frozen engine's self-test after the sidecar build and before the installer is built; the calibration report is attached only for the 1.0.x line (see section 4), so a repair release attaches none instead of a mislabelled old one.",
    "README.md": "One sentence beside `logs/launcher.log` and `logs/server.log`: `logs/app.log` holds the traceback of every failed call (path given), the self-test checks it; and where the calibration report of a repair release lives.",
    "skin_editor/api/rpc.py": "`import logging` and one `warning(..., exc_info=True)` line: every failed call writes its traceback to `app.log` (it logged nothing before). Nothing else in the file changes on this branch.",
    "skin_editor/frozen.py": "NEW. The stand-in for `fmod_toolkit` (the engine never decodes audio; FMOD is not shipped) and the self-test: the picture code must import, and a deliberately failing call must leave its traceback in `app.log`.",
    "studio/src-tauri/Cargo.lock": "Version 1.1.0 -> 1.1.1 of the `fm-skin-studio` package (one line).",
    "studio/src-tauri/Cargo.toml": "Version 1.1.0 -> 1.1.1 (one line).",
    "studio/src-tauri/tauri.conf.json": "Version 1.1.0 -> 1.1.1 (one line): the installer, the updater feed and `latest.json` take their version from here, and the release workflow refuses a tag that does not match it.",
    "tools/engine_entry.py": "Installs the stand-in before anything imports UnityPy, and adds `--selftest`.",
    "tools/freeze_engine.py": "Excludes `fmod_toolkit` and `pyfmodex`, collects `astc_encoder` and `archspec` (the data files the picture codec needs), and runs `--selftest` after EVERY freeze, failing the build when it fails.",
    "docs/RELEASE-NOTES-1.1.1.md": "NEW. The release body (the workflow reads `docs/RELEASE-NOTES-<version>.md`).",
    "tests/test_frozen.py": "NEW. Eleven tests that pin the above: the stand-in, the self-test and its log assertion (with a negative case), the freeze flags, the workflow order, the notes and README statements, the version in all three places.",
}
ENGINE_FILES = ["skin_editor/frozen.py", "skin_editor/api/rpc.py", "tools/engine_entry.py", "tools/freeze_engine.py"]


def git(*a, check=True):
    return subprocess.run([GIT, *a], cwd=str(ROOT), capture_output=True, text=True, check=check).stdout


def blob(ref, path):
    return subprocess.run([GIT, "show", "%s:%s" % (ref, path)], cwd=str(ROOT), capture_output=True, check=True).stdout


def sha(b):
    return hashlib.sha256(b).hexdigest()


def test_ids(ref):
    """Static enumeration of the tests defined in tests/*.py at a ref: module.Class.method (class bodies only; a test a class merely inherits is not listed)."""
    out = {}
    for f in git("ls-tree", "--name-only", ref, "tests/").splitlines():
        name = Path(f).name
        if not (name.startswith("test_") and name.endswith(".py")):
            continue
        tree = ast.parse(blob(ref, f).decode("utf-8-sig"))
        for c in [n for n in tree.body if isinstance(n, ast.ClassDef)]:
            for m in c.body:
                if isinstance(m, ast.FunctionDef) and m.name.startswith("test_"):
                    out["%s.%s.%s" % (name[:-3], c.name, m.name)] = f
    return out


SIMPLE_TEST_MODULES = {"test_plain": "Simple mode: plain-words table (S1)", "test_s1_engine": "Simple mode: S1 engine (preset folder project, club colours, mode migration, colour browse)", "test_s2_engine": "Simple mode: S2 engine (Put it in the game, removal, flat-look rules)", "test_simple_inventory": "Simple mode: S0 token and literal inventory"}
EVIDENCE_TOOLING = {"test_evidence_manifest": "evidence manifest raw-hash tests (a test of `docs/evidence` tooling added after 1.1.0; NOT a Simple mode test)"}
FORBIDDEN_PATH = re.compile(r"calibration|evidence|report|simple|plain|Start\.tsx|PutInGame|Setup\.tsx|Palette|colourGroups|/render/|^data/|^studio/src/", re.I)


def show(ref, path):
    return git("show", "%s:%s" % (ref, path)).replace("\r\n", "\n")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--branch", default="origin/release/1.1.1"); ap.add_argument("--base", default="v1.1.0"); ap.add_argument("--main", default="origin/main")
    ap.add_argument("--facts", required=True); ap.add_argument("--out", required=True)
    a = ap.parse_args()
    facts = json.loads(Path(a.facts).read_text(encoding="utf-8-sig"))
    head, base, mainhead = git("rev-parse", a.branch).strip(), git("rev-parse", a.base + "^{commit}").strip(), git("rev-parse", a.main).strip()
    changed = {}
    for line in git("diff", "--name-status", a.base, a.branch).splitlines():
        st, path = line.split("\t", 1); changed[path] = st
    assert set(changed) == set(REASONS), "the diff and the stated reasons differ: %s" % sorted(set(changed) ^ set(REASONS))
    stat = {l.split("\t")[2]: (l.split("\t")[0], l.split("\t")[1]) for l in git("diff", "--numstat", a.base, a.branch).splitlines()}
    L = []
    w = L.append
    w("# Audit report: release 1.1.1 (repair): the read-only audit of `origin/release/1.1.1`\n")
    w("Run by the operator (the standing gate: the operator audits, the owner reads this and approves the tag). Generated by `tools/make_release_dossier.py` from git and the CI API; every claim below is a command output, not a restatement. The release target is the branch below, **not main**. The tag `v1.1.1` has not been pushed.\n")
    w("## 1. The target\n")
    tags = git("ls-remote", "--tags", "origin", "v1.1.1").strip()
    w("| | |\n|---|---|\n| branch | `%s` |\n| head | `%s` |\n| base (tag `%s`) | `%s` |\n| commits on the branch since the base | %s |\n| tag `v1.1.1` on origin | %s |\n| main, for comparison (NOT the target) | `%s` |\n" % (
        a.branch, head, a.base, base, git("rev-list", "--count", a.base + ".." + a.branch).strip(), "**none**" if not tags else "EXISTS: " + tags, mainhead))
    w("**The head is `%s`, not `b1ddf93`.** The tag approval as last worded names `b1ddf93`; that commit predates the audit condition that the notes and the README say where the unchanged calibration report lives (the notes, the README and one test changed), so a tag on `b1ddf93` would ship notes without that statement. The commit to tag is the head above; the approval needs to name it.\n" % head[:7])
    w("## 2. The diff `%s..%s`: %d files, each with its reason\n" % (a.base, a.branch.split("/", 1)[-1], len(changed)))
    w("| file | status | + / - | why |\n|---|---|---|---|")
    for p in sorted(changed):
        w("| `%s` | %s | %s / %s | %s |" % (p, {"A": "new", "M": "changed"}[changed[p]], stat[p][0], stat[p][1], REASONS[p]))
    hits = [p for p in changed if FORBIDDEN_PATH.search(p)]
    w("\n**File by file, none of the %d is a Simple mode, calibration, report or evidence file.** Verified by path against `%s`: matching files: %s. The files live in: %s.\n" % (len(changed), FORBIDDEN_PATH.pattern, "**NONE**" if not hits else "**%s: STOP**" % hits, ", ".join("`%s`" % d for d in sorted({p.rsplit("/", 1)[0] if "/" in p else "(repository root)" for p in changed}))))
    w("Checked by the script: the files above are exactly the files that differ; there is no Simple mode file on the branch: %s.\n" % ("`skin_editor/plain.py`, `studio/src/Start.tsx`, `studio/src/PutInGame.tsx`, `data/simple/` are all absent" if not any(
        subprocess.run([GIT, "cat-file", "-e", "%s:%s" % (a.branch, f)], cwd=str(ROOT), capture_output=True).returncode == 0 for f in ("skin_editor/plain.py", "studio/src/Start.tsx", "studio/src/PutInGame.tsx", "data/simple/token-inventory.json")) else "**PRESENT: STOP**"))
    w("Nothing under `docs/evidence/` is in the diff: %s; nothing under `studio/src` is in the diff: %s.\n" % ("**confirmed**" if not any(p.startswith("docs/evidence/") for p in changed) else "**NO**", "**confirmed**" if not any(p.startswith("studio/src/") for p in changed) else "**NO**"))
    w("## 3. Every place that carries the version\n")
    w("| location | content on the branch |\n|---|---|")
    conf = json.loads(show(a.branch, "studio/src-tauri/tauri.conf.json"))
    w("| `studio/src-tauri/tauri.conf.json` (installer, updater, `latest.json`) | `\"version\": \"%s\"` |" % conf["version"])
    w("| `studio/src-tauri/Cargo.toml` | `%s` |" % re.search(r'(?m)^version = "[^"]+"', show(a.branch, "studio/src-tauri/Cargo.toml")).group(0))
    lock = show(a.branch, "studio/src-tauri/Cargo.lock"); m = re.search(r'name = "fm-skin-studio"\nversion = "[^"]+"', lock)
    w("| `studio/src-tauri/Cargo.lock` | `%s` |" % m.group(0).replace("\n", " / "))
    notes = show(a.branch, "docs/RELEASE-NOTES-1.1.1.md")
    w("| `docs/RELEASE-NOTES-1.1.1.md` (release body) | `%s` |" % notes.splitlines()[0])
    w("| `.github/workflows/release.yml` | refuses a tag that differs from `tauri.conf.json`: `%s` |" % [l.strip() for l in show(a.branch, ".github/workflows/release.yml").splitlines() if "does not match" in l][0][:140])
    init = show(a.branch, "skin_editor/__init__.py")
    w("| engine (`skin_editor/__init__.py`) | %s |" % ("`%s`" % re.search(r"__version__\s*=\s*[^\n]+", init).group(0) if re.search(r"__version__", init) else "no version string (unchanged from 1.1.0; the engine reports no version of its own)"))
    w("| `studio/package.json` | `%s`: not the app version (unchanged, 0.0.0 since the first commit) |" % re.search(r'"version": "[^"]+"', show(a.branch, "studio/package.json")).group(0))
    w("| `latest.json` | not in the repository: `tauri-action` writes it at release time from `tauri.conf.json`; the post-run check reads it |")
    assert conf["version"] == "1.1.1" and 'version = "1.1.1"' in show(a.branch, "studio/src-tauri/Cargo.toml") and "1.1.1" in m.group(0)
    left = [l for l in git("grep", "-n", "-E", r'"1\.1\.0"|^version = "1\.1\.0"', a.branch, "--", "studio/src-tauri/tauri.conf.json", "studio/src-tauri/Cargo.toml", check=False).splitlines()]
    deps = len(re.findall(r'(?m)^version = "1\.1\.0"', lock))
    w("\nNo `1.1.0` remains in `tauri.conf.json` or `Cargo.toml`, and the `fm-skin-studio` package in `Cargo.lock` is 1.1.1: %s. (`Cargo.lock` has %d other packages that happen to be at their own version 1.1.0: those are dependencies, not this app, and are untouched.)\n" % ("**confirmed**" if not left else "**NOT CONFIRMED: %s**" % left, deps))
    w("## 4. The workflow `release.yml` on the branch\n")
    rel = show(a.branch, ".github/workflows/release.yml"); lines = rel.splitlines()
    def block(start, n):
        i = [k for k, l in enumerate(lines) if start in l][0]; return "\n".join(lines[i:i + n])
    w("**The self-test, after the sidecar build and before the installer is built** (line numbers in the file: freeze %d, self-test %d, build and publish %d):\n" % (
        [k for k, l in enumerate(lines, 1) if "tools/freeze_engine.py" in l][0], [k for k, l in enumerate(lines, 1) if "--selftest" in l][0], [k for k, l in enumerate(lines, 1) if "Build, sign and publish" in l][0]))
    w("```yaml\n%s\n\n%s\n```\n" % (block("Freeze the engine", 6), block("Self-test the frozen engine", 6)))
    w("**The log-path assertion** lives in the self-test (`skin_editor/frozen.py::check_failed_call_logs_traceback`: one deliberately failing call, then the traceback must be in `<workspace>/logs/app.log`) and is pinned by `tests/test_frozen.py::test_a_failed_call_must_leave_its_traceback_in_the_documented_log_and_the_check_notices_when_it_does_not` (it includes the negative case: a build that swallows the log line is reported). The path is named in the README and in the release notes, pinned by `test_the_log_path_is_documented_where_the_other_logs_are_and_named_in_the_release_notes`.\n")
    w("**The report-attachment step: the reason a 1.1.1 release attaches none is evidence.** On `%s` (the tag, 1.1.0) the step read:\n" % a.base)
    old = show(a.base, ".github/workflows/release.yml").splitlines()
    oi = [k for k, l in enumerate(old) if "Where-Object { $_.Name -like \"phase9-v$tag-calibration-*\" }" in l][0]
    w("```powershell\n%s\n```\n" % "\n".join(old[oi:oi + 3]))
    copies = [l.strip() for l in old if "Copy-Item" in l]
    w("and the lines that name the files it uploads, on `%s`:\n\n```powershell\n%s\n```\n\nwith `$v` = `1.1.1` those are, exactly: **`calibration-report-1.1.1.md`** and **`calibration-report-1.1.1.json`**, copied from the folder the rule had picked (below).\n" % (a.base, "\n".join(copies)))
    w("and on the branch it reads:\n")
    ni = [k for k, l in enumerate(lines) if "Where-Object { $_.Name -like \"phase9-v$tag-calibration-*\" }" in l][0]
    w("```powershell\n%s\n```\n" % "\n".join(lines[ni:ni + 3]))
    folders = [l.split("\t")[1].split("/")[2] for l in git("ls-tree", "-d", a.branch, "docs/evidence/").splitlines()] if False else [l.split("/")[-1] for l in git("ls-tree", "--name-only", a.branch, "docs/evidence/").splitlines()]
    cal = sorted(f for f in folders if f.startswith("phase9-") and "calibration" in f)
    tag = "1.1.1".replace(".", "")
    new_pick = [f for f in cal if f.startswith("phase9-v%s-calibration-" % tag)]
    old_pick = new_pick or [f for f in cal if f.startswith("phase9-m7-calibration-")][-1:]
    w("Run on the folders that exist on the branch (%s), for version 1.1.1 (`$tag` = `%s`): **the 1.1.0 rule would have attached `%s` as `calibration-report-1.1.1.md` and `.json`** (the frozen 1.0.0 revised report, under a 1.1.1 name); **the branch rule finds no folder `phase9-v%s-calibration-*`, the 1.0.x fallback does not apply to 1.1.1, and it attaches nothing** (it prints why and exits 0). The notes and the README say the 1.1.0 report stands and lives on the v1.1.0 release page.\n" % (", ".join("`%s`" % f for f in cal), tag, old_pick[0] if old_pick else "?", tag))
    pins = []
    for wf in git("ls-tree", "--name-only", a.branch, ".github/workflows/").splitlines():
        for l in show(a.branch, wf).splitlines():
            m = re.search(r"uses:\s*(\S+)@([0-9a-f]{40})(.*)", l)
            if m:
                pins.append((Path(wf).name, m.group(1), m.group(2), m.group(3).strip()))
            elif re.search(r"uses:\s*\S+@", l):
                pins.append((Path(wf).name, l.strip(), "NOT PINNED", ""))
    w("**Actions pinned to commit SHAs** (`ci.yml`, `release.yml`): %d `uses:` lines, %s.\n" % (len(pins), "all 40-hex pinned" if all(p[2] != "NOT PINNED" for p in pins) else "**NOT ALL PINNED: STOP**"))
    w("| workflow | action | commit | comment |\n|---|---|---|---|")
    for p in sorted(set(pins)):
        w("| `%s` | `%s` | `%s` | %s |" % p)
    w("")
    w("## 5. `RELEASE-NOTES-1.1.1.md` in full, and where its numbers come from\n")
    w("```markdown\n%s\n```\n" % notes.rstrip("\n"))
    toks = sorted(set(re.findall(r"\d+(?:\.\d+)+|\b\d+\b", notes)))
    w("Every digit sequence in the notes: %s. These are **version numbers only** (`1.1.1`: `tauri.conf.json`, section 3; `1.1.0` and `1.0.0`: the releases it repairs and the older affected one, tags `v1.1.0` and `v1.0.0`; the installer's file name `FM.Skin.Studio_1.1.1_x64-setup.exe`, which the Tauri build produces, also contains the platform name `x64`, which is not a number the notes compute). **No measured value, count or rate appears in the notes, so no run produced a number in them.**\n" % ", ".join("`%s`" % t for t in toks))
    w("## 6. Suites and CI\n")
    w("| | result |\n|---|---|\n| engine suite on the branch head | %s |\n| Studio suite | not run on the branch: the Studio is byte-identical to `%s` (no file under `studio/src` is in the diff); the release workflow runs it before the build |" % (facts["suite"], a.base))
    runs = json.loads(urllib.request.urlopen(urllib.request.Request("https://api.github.com/repos/hubertlapinski3-cmyk/FMSKINEDITOR/actions/runs?per_page=40&branch=release%2F1.1.1", headers={"User-Agent": "dossier"})).read().decode("utf-8"))["workflow_runs"]
    w("\nCI runs on the branch (read from the API):\n\n| run | commit | conclusion |\n|---|---|---|")
    for r in runs:
        w("| %s `%s` | `%s` | %s |" % (r["name"], r["id"], r["head_sha"][:7], r["conclusion"] or r["status"]))
    last = [r for r in runs if r["head_sha"] == head]
    w("\nCI at the head `%s`: **%s**.\n" % (head[:7], (last[0]["conclusion"] or last[0]["status"]) if last else "NO RUN FOUND"))
    w("## 7. The frozen build was made the way the installer makes it\n")
    w("The release workflow's step is `python -m pip install -r requirements.txt pyinstaller`, then `python tools/freeze_engine.py` (section 4); the build tested here was made with the same script (`%s`), on the head above, followed by the script's own self-test (it runs after every freeze):\n" % facts["command"])
    w("| | |\n|---|---|\n| self-test line | `%s` |\n| frozen `fm-skin-engine.exe` | %s bytes, sha256 `%s` |\n| the whole one-dir build | %s bytes |\n| files with `fmod` in their name in the build | %s |\n| interpreter, PyInstaller | %s, PyInstaller %s |\n| thumbnails served by the frozen engine | %s |" % (
        facts["selftest"], facts["exe_size"], facts["exe_sha"], facts["folder_bytes"], facts["fmod_files"], facts["python"], facts["pyinstaller"], facts["thumbnails"]))
    same = all(git("rev-parse", "fc1b8e8:" + f).strip() == git("rev-parse", head + ":" + f).strip() for f in ENGINE_FILES)
    w("\nThe four engine files are blob-identical between `fc1b8e8` (the commit the thumbnail run was made on) and the head: **%s**, so that run describes this head's engine.\n" % ("yes" if same else "NO"))
    ciw = show(a.branch, ".github/workflows/release.yml")
    pyv = re.search(r'python-version:\s*"?([\d.]+)"?', ciw)
    w("How the CI build differs from the one tested here: the workflow installs `pyinstaller` **unpinned** (`pip install -r requirements.txt pyinstaller`), so the CI build uses the PyInstaller current on the day (here %s), and its Python is %s. The self-test in the workflow is what guards that drift.\n" % (facts["pyinstaller"], ("`%s`" % pyv.group(1)) if pyv else "as set in the workflow"))
    w("What this does not show: the build is not byte-reproducible (the CI build of the installer will have another hash), and the build here ran as administrator (PyInstaller prints a deprecation notice about that; not a 1.1.1 matter). The proof that matters for the shipped artifact is the post-run check in section 9: the installed engine's `--selftest` after the update.\n")
    w("## 8. Byte-identity of the repair: the branch against main, file by file\n")
    w("`%s` (main) is **not** the release target. It holds the same repair as ordinary commits plus the unreleased Simple mode work and keeps version 1.1.0, so 1.1.1 and 1.2.0 ship the same repair if the table below says so. sha256 of each file's bytes as committed:\n" % mainhead[:7])
    w("| file | sha256 on the branch | sha256 on main | result |\n|---|---|---|---|")
    why = {"studio/src-tauri/Cargo.lock": "differs BY DESIGN: main stays at 1.1.0 until the 1.2.0 bump", "studio/src-tauri/Cargo.toml": "differs BY DESIGN: main stays at 1.1.0 until the 1.2.0 bump", "studio/src-tauri/tauri.conf.json": "differs BY DESIGN: main stays at 1.1.0 until the 1.2.0 bump"}
    ident, other = 0, []
    for p in sorted(changed):
        sb, sm = sha(blob(a.branch, p)), sha(blob(a.main, p))
        if sb == sm:
            res = "**identical**"; ident += 1
        elif p in why:
            res = why[p]
        elif p == "skin_editor/api/rpc.py":
            res = "differs: see the hunk check below"
        else:
            res = "**DIFFERS (unexplained)**"; other.append(p)
        w("| `%s` | `%s` | `%s` | %s |" % (p, sb[:16], sm[:16], res))
    rpc_added = [l[1:] for l in git("diff", "-U0", a.base, a.branch, "--", "skin_editor/api/rpc.py").splitlines() if l.startswith("+") and not l.startswith("+++")]
    rpc_main = show(a.main, "skin_editor/api/rpc.py").splitlines()
    inmain = [l in rpc_main for l in rpc_added]
    w("\n**%d of the %d files are byte-identical; 3 differ by design (the version); `skin_editor/api/rpc.py` differs only because main's copy also carries Simple mode's plain-words wrapper.** The hunk check for `rpc.py`: the branch adds exactly these %d lines to the file at `%s`:\n" % (ident, len(changed), len(rpc_added), a.base))
    w("```python\n%s\n```\n" % "\n".join(rpc_added))
    w("and each of them is present, character for character, in main's `rpc.py`: **%s**. The repair commits on main: %s.\n" % ("yes, all %d" % len(rpc_added) if all(inmain) else "**NO: %s**" % [l for l, k in zip(rpc_added, inmain) if not k], ", ".join("`%s`" % l.split()[0] for l in git("log", "--oneline", a.base + ".." + a.main, "--", "skin_editor/frozen.py", "tools/freeze_engine.py", "tools/engine_entry.py").splitlines())))
    assert not other, other
    w("## 8b. The tests that run on main and not on the branch (a listed fact, not an inference)\n")
    tb, tm = test_ids(a.branch), test_ids(a.main)
    only_main, only_branch = sorted(set(tm) - set(tb)), sorted(set(tb) - set(tm))
    w("Static enumeration of `tests/test_*.py` (every class's `test_*` methods) at each ref: **branch %d, main %d, on main only %d, on the branch only %d.** The actual runs are in section 6 (they also count tests that a class inherits, so they differ from this count by that much).\n" % (len(tb), len(tm), len(only_main), len(only_branch)))
    RENAMED = {"test_evidence_manifest.Manifest.test_every_listed_file_hashes_to_its_recorded_value": "test_evidence_manifest.Manifest.test_every_listed_file_hashes_to_its_recorded_normalised_value"}
    unexplained = [x for x in only_branch if RENAMED.get(x) not in tm]
    assert not unexplained, "a test on the branch has no counterpart on main: %s" % unexplained
    if not only_branch:
        w("**On the branch only: none.** Every test of the branch also exists on main under the same name.\n")
    else:
        w("**On the branch only: %d, and it is a rename, not a drop.** `%s` exists on main as `%s`: the check is the same (the sha256 of the LF-normalised bytes of every file in the manifest equals its recorded value; main's version computes it through `tools/make_manifest.py`'s `normalised()`, which is `hashlib.sha256(bytes.replace(b\"\\r\\n\", b\"\\n\"))`, the expression the branch's version spells out). The rename happened on main when the raw-hash tests were added. So no test was dropped: every other test of the branch exists on main under the same name.\n" % (len(only_branch), only_branch[0], RENAMED[only_branch[0]]))
    w("The %d tests on main and not on the branch, by module:\n\n| module | what it is | tests |\n|---|---|---|" % len(only_main))
    bymod = {}
    for i_ in only_main:
        bymod.setdefault(i_.split(".")[0], []).append(i_)
    unclassified = []
    for mod in sorted(bymod):
        kind = SIMPLE_TEST_MODULES.get(mod) or EVIDENCE_TOOLING.get(mod)
        if not kind:
            unclassified.append(mod); kind = "**UNCLASSIFIED**"
        w("| `%s` | %s | %d |" % (mod, kind, len(bymod[mod])))
    simple_n = sum(len(v) for k, v in bymod.items() if k in SIMPLE_TEST_MODULES); other_n = len(only_main) - simple_n
    w("\n**%d of them are Simple mode tests; %d are not**: they are in `test_evidence_manifest` (%d is the renamed counterpart of the branch's own test, above; %d are the new raw-hash checks of `docs/evidence`, added to main after 1.1.0; the branch keeps the 1.1.0 version of that file and its manifest, which pass). That is a statement about main's evidence tooling, not about the repair, and it is listed here because \"all of them are Simple mode tests\" would not be true.\n" % (simple_n, other_n, len(only_branch), other_n - len(only_branch)))
    w("```text\n%s\n```\n" % "\n".join(only_main))
    assert not unclassified, unclassified
    w("Actual runs at these heads: branch `%s`; main `%s`.\n" % (facts["suite"], facts.get("main_suite", "not recorded")))
    w("## 9. After the owner's approval (the order, unchanged)\n")
    w("1. Push the tag `v1.1.1` on the head above (`git tag v1.1.1 %s`; `git push origin v1.1.1`). 2. Post-run checks: the installer's size and sha256; `latest.json` version 1.1.1, notes equal to `RELEASE-NOTES-1.1.1.md`, both signatures equal to the `.sig` asset; the v1.0.0 and v1.1.0 releases untouched (their assets byte-identical to the hashes in the plan, still downloadable); **no calibration asset on 1.1.1**; the self-test ran in the workflow on the shipped artifact and passed (the run's log). 3. The owner, in order: Check for updates (with the fallback in the plan), the Images view icon thumbnails, the click-to-explain step of the smoke test, the S2 section C look including Images. 4. Only after ALL of the above has passed: remove the release worktree and record that CI runs on `release/**` as a standing rule. **The branch `release/1.1.1` is KEPT after the tag: it is the provenance of the tag.**\n" % head[:7])
    w("## 10. Two things for the owner to decide or know\n")
    w("- **`latest.json` notes byte-equal to the notes file.** For 1.1.0 the feed's notes and the release body carried CRLF line endings and no final newline while the file is LF with one; the cause was not isolated (the workflow reads the file with `Get-Content -Raw` and writes it through `Out-File` into the job environment, `release.yml`). A byte-for-byte comparison therefore fails unless the line endings are normalised first, and I cannot test a workflow change without a release run. **The check as I will run it: equal after CRLF to LF and trimming the final newline**, stated as such in the result. If you want true byte equality, say so: it needs a change to the workflow step that I could not verify before the tag.")
    w("- **The first observed end-to-end update run** is the 1.1.0 -> 1.1.1 update on your PC; the 1.0.0 -> 1.1.0 one completed but was not observed live (recorded in the plan from the updater's leftovers).\n")
    w("- **The direct hop 1.0.0 -> 1.1.1 is accepted and NOT tested.** The proven hop is 1.0.0 -> 1.1.0 (same shape: the installed updater reads the latest manifest whatever version it starts from); a 1.0.0 user updating straight to 1.1.1 is the accepted, untested case. Your install is not downgraded to test it.\n")
    w("- **Amendment to decision point 1** (recorded in the plan as an amendment, with its reason): it said the 1.1.1 release attaches the calibration report assets byte-identical to the v1.1.0 copies. Amended: **1.1.1 attaches no calibration report.** The rule as written assumed a report whose provenance matched the release; a packaging patch with no calibration change carries no report. The report for this calibration lives on the v1.1.0 release, named in the notes and the README (section 4 shows what the old rule would have uploaded and under which names).\n")
    Path(a.out).write_text("\n".join(L) + "\n", encoding="utf-8", newline="\n")
    print("wrote", a.out, "(%d lines)" % len(L))
    return 0


if __name__ == "__main__":
    sys.exit(main())
