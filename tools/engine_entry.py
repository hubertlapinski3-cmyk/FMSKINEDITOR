"""Entry point for the frozen engine (PyInstaller). Same as `python -m skin_editor`; the freeze needs a plain script, not a package __main__."""
import multiprocessing
import sys

from skin_editor.__main__ import main

if __name__ == "__main__":
    multiprocessing.freeze_support()
    sys.exit(main())
