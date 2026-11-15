"""Fixes that only the FROZEN engine (PyInstaller) needs.

UnityPy's `export/AudioClipConverter.py` does `import fmod_toolkit` as soon as UnityPy's export code is loaded, and fmod_toolkit loads the FMOD library (`fmod.dll`)
when imported. In a frozen build that library is not in the folder, and the import fails with a PyInstallerImportError (not an ImportError), so every call that reaches
UnityPy's export code failed in the installed app: the thumbnails of the game's 1,341 atlas icons, among others (found 2026-11-15 on the 1.1.0 build; 1.0.0 had it too).

The engine never decodes sound, and shipping FMOD (a proprietary library with its own licence terms) to fix a thumbnail is the wrong trade. So the frozen engine puts a stand-in for
`fmod_toolkit` in place before UnityPy is imported: importing it works, and using audio says plainly that this build has no audio. The freeze also excludes the real package
(tools/freeze_engine.py)."""
import sys
import types


class _NoAudio(types.ModuleType):
    def __getattr__(self, name):
        if name.startswith("__"):
            raise AttributeError(name)
        raise RuntimeError("audio decoding is not available in this build of FM Skin Studio (fmod_toolkit is not included)")


def install_audio_stub():
    """Idempotent. Put the stand-in in sys.modules unless a real fmod_toolkit is already loaded."""
    if "fmod_toolkit" not in sys.modules:
        sys.modules["fmod_toolkit"] = _NoAudio("fmod_toolkit")
    return sys.modules["fmod_toolkit"]


# everything the engine imports to read and draw the game's pictures; each one failed at import in the first frozen builds (fmod_toolkit, then archspec's data files through astc_encoder)
SELFTEST_MODULES = ("UnityPy", "UnityPy.export.Texture2DConverter", "UnityPy.export.AudioClipConverter", "astc_encoder", "texture2ddecoder", "etcpak", "PIL.Image")


def check_failed_call_logs_traceback():
    """A call that fails must leave its traceback in the documented log: <workspace>/logs/app.log (the installed app on Windows: %LOCALAPPDATA%\\FM27SkinEditor\\logs\\app.log).
    Runs one failing call against a throwaway workspace and reads the log back. Returns the problems as text."""
    import json
    import logging
    import os
    import shutil
    import tempfile
    from pathlib import Path
    tmp = tempfile.mkdtemp(prefix="fm-selftest-")
    old = os.environ.get("FM27SE_WORKSPACE")
    os.environ["FM27SE_WORKSPACE"] = tmp
    try:
        from skin_editor.api import rpc
        from skin_editor.engine import Engine
        e = Engine()
        out = json.loads(rpc.handle(e, json.dumps({"jsonrpc": "2.0", "id": 1, "method": "jobs.get", "params": {"id": "selftest-no-such-job"}})))
        for h in logging.getLogger("skin_editor").handlers:
            h.flush()
        if "error" not in out:
            return ["log check: a call that must fail did not fail"]
        log = Path(e.ws.logs) / "app.log"
        text = log.read_text(encoding="utf-8") if log.is_file() else ""
        if "rpc jobs.get failed" not in text or "Traceback" not in text:
            return ["log check: a failed call left no traceback in %s" % log]
        return []
    except BaseException as ex:
        return ["log check: %s: %s" % (type(ex).__name__, str(ex)[:200])]
    finally:
        for h in list(logging.getLogger("skin_editor").handlers):
            logging.getLogger("skin_editor").removeHandler(h); h.close()
        if old is None:
            os.environ.pop("FM27SE_WORKSPACE", None)
        else:
            os.environ["FM27SE_WORKSPACE"] = old
        shutil.rmtree(tmp, ignore_errors=True)


def selftest(modules=SELFTEST_MODULES, log=True):
    """Import what the picture code needs, and check that a failed call writes its traceback to the documented log; returns the problems as text (empty list = fine). The frozen engine runs it
    with `--selftest`; tools/freeze_engine.py runs it after EVERY frozen build (a local build included), and the release workflow runs it again before the installer is built.
    It samples the READ paths and the log, and claims nothing else: the bundle WRITE path (UnityPy load and save) is not covered (docs/PHASE9-PLAN.md, roadmap)."""
    import importlib
    problems = []
    for name in modules:
        try:
            importlib.import_module(name)
        except BaseException as e:                       # PyInstallerImportError is not an ImportError
            problems.append("%s: %s: %s" % (name, type(e).__name__, str(e)[:200]))
    if log:
        problems += check_failed_call_logs_traceback()
    return problems
