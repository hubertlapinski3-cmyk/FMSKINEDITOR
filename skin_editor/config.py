"""config.json and workspace paths. LEARNINGS sections 3 and 4."""
import copy
import json
import logging
import os
import sys
from pathlib import Path

DEFAULTS = {
    "schema": 1,
    "game_dir": None,
    "aa_dir": None,
    "platform_folder": "auto",
    "store": "auto",
    "workspace_dir": None,
    "vanilla_dir": None,
    "process_names": ["fm", "Football Manager 27"],
    "server": {"host": "127.0.0.1", "port": 8765, "open_browser": True},
    "build": {"keep_last_builds": 5, "flatten_gradients_default": False},
    "install": {"require_game_closed": True, "backup_keep": 20, "verify_after_copy": True},
    "verify": {"tolerance_rgb": 6, "sample": "region_centre_3x3"},
    "log_level": "info",
}


def default_workspace():
    if os.environ.get("FM27SE_WORKSPACE"):
        return Path(os.environ["FM27SE_WORKSPACE"])
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "FM27SkinEditor"
    if sys.platform == "win32":
        return Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "FM27SkinEditor"
    return Path.home() / ".local" / "share" / "FM27SkinEditor"


def resource_root():
    """frontend/ and data/ live here; sys._MEIPASS when frozen with PyInstaller."""
    return Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))


class Workspace:
    def __init__(self, root, vanilla_dir=None):
        self.root = Path(root).expanduser()
        self.cache, self.projects, self.build = self.root / "cache", self.root / "projects", self.root / "build"
        self.backups, self.logs, self.state = self.root / "backups", self.root / "logs", self.root / "state"
        self.placements = self.root / "placements"   # stored placement edits, one list per project (never written into the dump or a bundle)
        self.exports = self.root / "exports"      # exported originals (true size) for editing
        self.images = self.root / "images"        # replacement images and SVGs per project: images/<project>/<file>
        self.layout = self.root / "layout"        # layout dump: current.json, previous.json, status.json (read-only input, imported by layout_dump)
        self.vanilla = Path(vanilla_dir).expanduser() if vanilla_dir else self.root / "vanilla"
        for d in (self.cache, self.projects, self.build, self.backups, self.logs, self.state, self.layout, self.placements, self.vanilla, self.images):
            d.mkdir(parents=True, exist_ok=True)

    def vanilla_manifest(self):
        f = self.vanilla / "manifest.json"
        return json.loads(f.read_text(encoding="utf-8")) if f.is_file() else None


def _merge(base, over):
    for k, v in over.items():
        if isinstance(v, dict) and isinstance(base.get(k), dict):
            _merge(base[k], v)
        else:
            base[k] = v
    return base


def load():
    root = default_workspace()
    root.mkdir(parents=True, exist_ok=True)
    cfg = copy.deepcopy(DEFAULTS)
    f = root / "config.json"
    if f.is_file():
        _merge(cfg, json.loads(f.read_text(encoding="utf-8-sig")))
    if cfg["server"]["host"] not in ("127.0.0.1", "localhost"):
        cfg["server"]["host"] = "127.0.0.1"
    cfg["workspace_dir"] = cfg["workspace_dir"] or str(root)
    return cfg


def save(cfg):
    f = default_workspace() / "config.json"
    f.write_text(json.dumps(cfg, indent=2), encoding="utf-8")


def workspace(cfg):
    return Workspace(cfg["workspace_dir"], cfg.get("vanilla_dir"))


def setup_logging(ws):
    """App log in the workspace (percent-alpha conversions at the ingestion boundaries land here)."""
    root = logging.getLogger("skin_editor")
    if not root.handlers:
        h = logging.FileHandler(ws.logs / "app.log", encoding="utf-8")
        h.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
        root.addHandler(h)
        root.setLevel(logging.INFO)
