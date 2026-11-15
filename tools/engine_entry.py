"""Entry point for the frozen engine (PyInstaller). Same as `python -m skin_editor`; the freeze needs a plain script, not a package __main__."""
import multiprocessing
import sys

from skin_editor.frozen import install_audio_stub

install_audio_stub()                      # before UnityPy is imported: the frozen engine has no FMOD library (skin_editor/frozen.py)

from skin_editor.__main__ import main     # noqa: E402

if __name__ == "__main__":
    multiprocessing.freeze_support()
    if sys.argv[1:] == ["--selftest"]:
        from skin_editor.frozen import selftest
        bad = selftest()
        print("\n".join(bad) if bad else "selftest ok: the picture code imports and a failed call leaves its traceback in app.log")
        sys.exit(1 if bad else 0)
    sys.exit(main())
