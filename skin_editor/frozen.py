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


def selftest(modules=SELFTEST_MODULES):
    """Import what the picture code needs; returns the problems as text (empty list = fine). The frozen engine runs it with `--selftest`, and the release workflow runs that before it builds the installer."""
    import importlib
    problems = []
    for name in modules:
        try:
            importlib.import_module(name)
        except BaseException as e:                       # PyInstallerImportError is not an ImportError
            problems.append("%s: %s: %s" % (name, type(e).__name__, str(e)[:200]))
    return problems
