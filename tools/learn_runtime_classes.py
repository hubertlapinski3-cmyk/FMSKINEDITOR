"""Learn the runtime classes of UI Toolkit control types from inspector dumps.

    python tools/learn_runtime_classes.py DUMP_FOLDER [--out data/render/runtime-classes.json] [--min-n 15] [--share 0.97]

UI Toolkit controls add classes in code (an SIText carries `sitext`, an SIButton `sibutton`, `navigatable`, `HasSIClickable`), and USS rules match on them, but
the layout files do not contain them. The inspector's node labels (`Type#name.class.class`) show the live class list. A class that sits on at least `share`
of all instances of a type (with at least `min-n` instances) is taken to be implied by the type. The table is evidence-based, not exhaustive: types with few
instances, and classes a type adds only in some states, are missing, and the render reports an unexplained class gap rather than hiding it.

Reads the flat `{"result": {"nodes": [{"label": ...}]}}` dumps (`fm_get_screen`/`fm_dump_tree` flat form) and the `{"nodes": {path: {"label": ...}}}` tree form."""
import argparse
import collections
import glob
import json
import re
import sys
from pathlib import Path

LABEL = re.compile(r"^([A-Za-z0-9_`]+)(?:#([^.]*))?((?:\.[^.]+)*)$")


def labels(doc):
    if isinstance(doc, dict):
        nodes = (doc.get("result") or {}).get("nodes")
        if isinstance(nodes, list):
            return [n.get("label", "") for n in nodes if isinstance(n, dict)]
        if isinstance(doc.get("nodes"), dict):
            return [v.get("label", "") for v in doc["nodes"].values() if isinstance(v, dict)]
    return []


def learn(folder, min_n=15, share=0.97):
    by = collections.defaultdict(list)
    used = 0
    for f in sorted(glob.glob(str(Path(folder) / "*.json"))):
        try:
            doc = json.loads(Path(f).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        ls = labels(doc)
        if not ls:
            continue
        used += 1
        for lab in ls:
            m = LABEL.match(lab)
            if m:
                by[m.group(1)].append(frozenset(c for c in m.group(3).split(".") if c))
    table, nodes = {}, sum(len(v) for v in by.values())
    for typ, sets in sorted(by.items()):
        n = len(sets)
        if n < min_n:
            continue
        cnt = collections.Counter(c for s in sets for c in s)
        rc = sorted(c for c, k in cnt.items() if k >= share * n)
        if rc:
            table[typ] = {"n": n, "classes": rc}
    return {"schema": "fm-runtime-classes/1", "source": "inspector dumps", "dump_files": used, "nodes": nodes, "min_instances": min_n, "share": share,
            "types": table}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("folder")
    ap.add_argument("--out", default=str(Path(__file__).resolve().parent.parent / "data" / "render" / "runtime-classes.json"))
    ap.add_argument("--min-n", type=int, default=15)
    ap.add_argument("--share", type=float, default=0.97)
    a = ap.parse_args()
    doc = learn(a.folder, a.min_n, a.share)
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    Path(a.out).write_text(json.dumps(doc, indent=1, sort_keys=True), encoding="utf-8")
    print("wrote %s: %d types from %d dumps, %d nodes" % (a.out, len(doc["types"]), doc["dump_files"], doc["nodes"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
