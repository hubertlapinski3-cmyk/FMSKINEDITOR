"""GUID -> asset index of the layout bundles.

A layout's `m_Usings` names an included template only by GUID (its asset pointer is empty in the file), so the GUID has to be resolved. Each
`ui-visualtreeassets_*.bundle` carries an AssetBundle object whose container is keyed by asset GUID (a 32-hex string) and points at the objects of that asset: for a
layout, its VisualTreeAsset and its inline StyleSheet. Reading these containers is enough; nothing outside the game's bundles is needed (the FM27_LayoutMCP sqlite
holds the same mapping but is optional and not used here)."""
import hashlib
import json
import re
from pathlib import Path

HEX = re.compile(r"^[0-9a-f]{32}$")


def path_id_of(entry):
    """Path id of a container entry: a PPtr (`m_PathID`) in some bundles, an AssetInfo holding one (`.asset`) in others."""
    return entry.m_PathID if hasattr(entry, "m_PathID") else entry.asset.m_PathID


class GuidIndex:
    def __init__(self, folder, cache_dir=None):
        self.folder = Path(folder)
        self.cache_dir = Path(cache_dir) if cache_dir else None
        self._map = None

    def _files(self):
        return sorted(self.folder.glob("ui-visualtreeassets*.bundle"))

    def _key(self):
        return hashlib.sha256(repr([(f.name, f.stat().st_size, f.stat().st_mtime_ns) for f in self._files()]).encode()).hexdigest()[:16]

    def load(self):
        """{guid: [[bundle file name, path id as text], ...]}; built once per set of bundle files, then read from the disk cache."""
        if self._map is not None:
            return self._map
        disk = self.cache_dir / ("render-guids-%s.json" % self._key()) if self.cache_dir else None
        if disk is not None and disk.is_file():
            self._map = json.loads(disk.read_text(encoding="utf-8"))
            return self._map
        import UnityPy
        out = {}
        for f in self._files():
            for o in UnityPy.load(str(f)).objects:
                if o.type.name != "AssetBundle":
                    continue
                for key, ptr in o.read().m_Container:
                    if HEX.match(key):
                        out.setdefault(key, []).append([f.name, str(path_id_of(ptr))])
        self._map = out
        if disk is not None:
            self.cache_dir.mkdir(parents=True, exist_ok=True)
            disk.write_text(json.dumps(out), encoding="utf-8")
        return out

    def find(self, guid):
        return [tuple(x) for x in self.load().get((guid or "").lower(), [])]
