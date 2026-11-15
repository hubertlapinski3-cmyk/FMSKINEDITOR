"""U4: the REAL ancestry of every element the I3 state fixture reads, taken from the inspector captures, one hop per element, no truncation.

    python tools/make_state_chains.py

Session G read the elements by hand on the baseline plugin; the saved replies hold the element and at most five ancestors. The captures hold the whole tree. Each element is found in a capture
of the same screen by what the replies recorded (type, name, classes, text where it identifies it) and its full path of ancestors is written root first to
tests/fixtures/render/state-i3-session-g/chains.json with the capture, the path and how it was matched. Where several elements match, the FIRST in capture order is taken and the number of
matches is recorded: the screen shows several alike (list rows, nav tabs), the captures were not taken during the hold, so this is an assumption, stated on every row that uses it."""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from skin_editor.render import captures, fixtures      # noqa: E402

OUT = ROOT / "tests" / "fixtures" / "render" / "state-i3-session-g" / "chains.json"
SQUAD, INBOX, TI = "styles-e1-squad-bindings-20261114-115217.ndjson", "styles-e5-inbox-bindings-20261114-120119.ndjson", "styles-d2-team-instructions-20261114-111314.ndjson"


def subtree_text(cap, path):
    return " ".join((cap.elements[p].get("text") or "") for p in cap.order if p == path or p.startswith(path + "/")).strip()


def find(cap, test):
    return [p for p in cap.order if test(cap.elements[p])]


# key -> (capture, predicate on a capture element, human description of how it is matched, optional text test on the subtree)
TARGETS = {
    "nav-tab-label": (SQUAD, lambda e: e["type"] == "SIText" and "portal-text" in e["classes"], "SIText with class portal-text; the tab whose text is TACTICS", lambda cap, p: cap.elements[p].get("text", "").strip().lower() == "tactics"),
    "filter-button": (SQUAD, lambda e: {"buttons-button-base-default", "button-size-medium", "navigatable-no-cursor"} <= set(e["classes"]), "element (it is an SIFloatingPopupWidget, not the SIButton the 1.0.0 state rows named) with the three button classes whose subtree text contains Filter", lambda cap, p: "filter" in subtree_text(cap, p).lower()),
    "loans-tile-button": (SQUAD, lambda e: e["type"] == "SIButton" and e["name"] == "layout-tile-interaction-button" and "anchor-loans" in e["classes"], "SIButton layout-tile-interaction-button with anchor-loans", None),
    "table-row": (SQUAD, lambda e: e["type"] == "BindingRoot" and {"streamed-table__row", "streamed-list-view__row--interactable", "virtualised-list__item"} <= set(e["classes"]) and "virtualised-list__item--first" not in e["classes"] and "virtualised-list__item--odd" not in e["classes"], "BindingRoot with the interactable table-row classes, an EVEN row (neither --first nor --odd), as the row Session G read", None),
    "inbox-row-button": (INBOX, lambda e: e["type"] == "SIButton" and e["name"] == "NewsItemButton", "SIButton NewsItemButton", None),
    "pitch-marker-label": (TI, lambda e: "content-tactics-visualiser-player-indicator-simple" in e["classes"], "the marker's label element (class content-tactics-visualiser-player-indicator-simple), the first in capture order", None),
    "pitch-marker": (TI, lambda e: "projected--position--filled" in e["classes"], "element with class projected--position--filled", None),
    "instruction-tile": (TI, lambda e: e["name"] == "TeamInstructionTile", "TemplateContainer TeamInstructionTile", None),
}


def main():
    ui = fixtures.ui_dumps_dir()
    caps, out = {}, {"note": "real ancestry from the captures, root first; see tools/make_state_chains.py for how each element was matched", "targets": {}}
    for key, (cname, pred, how, textok) in TARGETS.items():
        cap = caps.setdefault(cname, captures.read_capture(ui / cname))
        hits = find(cap, pred)
        if textok:
            hits = [p for p in hits if textok(cap, p)]
        if not hits:
            out["targets"][key] = {"capture": cname, "matched": 0, "how": how}
            continue
        path = hits[0]
        segs = path.split("/")
        chain = []
        for i in range(1, len(segs) + 1):
            q = "/".join(segs[:i])
            e = cap.elements.get(q)
            if e is None:
                continue
            chain.append({"type": e["type"], "name": e["name"], "classes": e["classes"], "path": q, "pseudo_in_capture": e.get("pseudo", 0)})
        out["targets"][key] = {"capture": cname, "matched": len(hits), "how": how, "path": path, "depth": len(chain), "chain": chain}
        print("%-18s %-60s matches %d, chain %d elements" % (key, cname[:40], len(hits), len(chain)))
    OUT.write_text(json.dumps(out, indent=1), encoding="utf-8")
    print("wrote", OUT)


if __name__ == "__main__":
    main()
