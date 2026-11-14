"""Census of every USS property name in the game's stylesheets, classified by the renderer's value map.

    python tools/uss_property_census.py [--aa AA_DIR] [--out data/render/uss-property-census.json]

Reads every StyleSheet object in the `ui-styles_*` and `ui-visualtreeassets_*` bundles (the shared sheets and every layout's inline sheet), counts each property name
(custom properties `--x` are only counted), maps property ids the editor cannot name through `render.values.ID_NAMES`, and classifies each name with
`render.values.classify`. The result is written to data/render/uss-property-census.json, which `tests/test_render_m1.py` uses to check, without the game, that no
property is missing from the map: the only `unknown` names allowed are the ones listed here, with their counts and an example value, so a gap is visible and not silent."""
import argparse
import collections
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from skin_editor import uss                                    # noqa: E402
from skin_editor.render import values                           # noqa: E402

AA = r"C:\Program Files (x86)\Steam\steamapps\common\Football Manager 27\fm_Data\StreamingAssets\aa\StandaloneWindows64"


def census(aa):
    import UnityPy
    counts, example, custom, sheets = collections.Counter(), {}, 0, 0
    files = sorted(Path(aa).glob("ui-styles_*.bundle")) + sorted(Path(aa).glob("ui-visualtreeassets_*.bundle"))
    for f in files:
        for o in UnityPy.load(str(f)).objects:
            if o.type.name != "MonoBehaviour":
                continue
            try:
                t = o.read_typetree()
            except Exception:
                continue
            if not isinstance(t, dict) or "m_Rules" not in t:
                continue
            sheets += 1
            for r in t["m_Rules"]:
                for p in r.get("m_Properties", []):
                    raw = uss.prop_name(p)
                    if raw.startswith("--"):
                        custom += 1
                        continue
                    counts[raw] += 1
                    if raw not in example:
                        txt, _ = uss.value_text(t, p.get("m_Values", []))
                        example[raw] = txt[:60]
    props, unknown = {}, {}
    for raw, n in sorted(counts.items(), key=lambda kv: -kv[1]):
        name, inferred = values.canonical(raw)
        _css, status, note = values.classify(name)
        row = {"count": n, "status": status, "example": example[raw]}
        if inferred:
            row["raw_id_name"], row["name_inferred"] = raw, True
        props[name if not inferred else name] = row if name not in props else {**row, "count": props[name]["count"] + n}
        if status == "unknown":
            unknown[raw] = {"count": n, "example": example[raw]}
    return {"schema": "fm-uss-property-census/1", "stylesheets": sheets, "custom_property_declarations": custom, "distinct_properties": len(props),
            "by_status": dict(collections.Counter(v["status"] for v in props.values())), "unknown": unknown, "properties": props}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--aa", default=AA)
    ap.add_argument("--out", default=str(ROOT / "data" / "render" / "uss-property-census.json"))
    a = ap.parse_args()
    doc = census(a.aa)
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    Path(a.out).write_text(json.dumps(doc, indent=1), encoding="utf-8")
    print("stylesheets %d; distinct properties %d; custom declarations %d; by status %s; unknown %s" %
          (doc["stylesheets"], doc["distinct_properties"], doc["custom_property_declarations"], doc["by_status"], doc["unknown"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
