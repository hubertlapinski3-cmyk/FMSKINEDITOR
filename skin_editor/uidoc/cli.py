"""`python -m skin_editor uidoc`: print one screen's UiDocument as JSON. Read only: the game's bundles, the layout dump and the fixture are only read; the only thing written is the renderer's own cache, in a folder of its own."""
import hashlib
import json
import sys
from pathlib import Path


def run(a):
    from .. import config, layout_dump
    from ..render.layouts import LayoutStore
    from ..render.service import Renderer
    from .build import Source, build_document

    root = Path(__file__).resolve().parents[2]
    fx = json.loads((root / "tests" / "fixtures" / "render" / a.fixture / "fixture.json").read_text(encoding="utf-8"))
    s = fx["screen"]                                   # the existing fixture format: composition, area, padding, reserved_right
    cfg = config.load()
    ws = config.workspace(cfg)
    aa = Path(a.aa or cfg["aa_dir"])
    if a.dump:
        dump, _raw = layout_dump.read_file(a.dump)
        errs, total = layout_dump.validate(dump)
        if total:
            print(json.dumps({"error": "the layout dump is not valid", "errors": errs}), file=sys.stderr)
            return 1
    else:
        dump = layout_dump.load(ws)
        if dump is None:
            print("no layout dump imported; give --dump FILE", file=sys.stderr)
            return 1
    cache = Path(a.cache) if a.cache else Path(ws.cache) / ("uidoc-" + hashlib.sha1(str(aa).encode()).hexdigest()[:8])   # never the shared cache: its asset index has no folder key
    cache.mkdir(parents=True, exist_ok=True)
    rd = None if a.no_cascade else Renderer(aa, str(cache), None)
    store = rd.layouts if rd is not None else LayoutStore(aa, str(cache))
    label = {"set_folder": str(aa), "game_build": a.build_label or dump["meta"]["game_build"], "status": a.status or "unlabelled", "label_source": a.label_source or "layout dump meta.game_build (a display label only)",
             "dump_game_build": dump["meta"]["game_build"], "dump_fingerprint": dump["meta"]["index_fingerprint"], "dump_catalog_hash": dump["meta"]["source"]["catalog_hash"]}
    cat = next((p for p in (aa / "catalog.hash", aa.parent / "catalog.hash") if p.is_file()), None)
    label["folder_catalog_hash"] = cat.read_text(encoding="utf-8", errors="replace").strip() if cat else None
    doc = build_document(Source(store), dump, s["composition"], s["area"], s.get("padding", 12), s.get("reserved_right", 0), renderer=rd, label=label, order=a.order)
    text = json.dumps(doc.to_dict(a.computed), indent=1 if a.indent else None, default=str)
    if a.out:
        Path(a.out).write_text(text, encoding="utf-8")
        print("written", a.out, len(text), "bytes; nodes", len(doc.index), "edges", len(doc.dependencies.edges), "diagnostics", len(doc.diagnostics))
    else:
        print(text)
    return 0
