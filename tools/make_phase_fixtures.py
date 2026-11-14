"""Builds the calibration fixtures that are not made by `fixture add` (docs/PHASE9-PLAN.md section 8), from the evidence held: the owner's phase test projects (p6-class-test,
p7-table-test-3, p7-tile-test), the Phase 3 rule, the c2 Loans dump and the Session D/E captures of the screens. Run once; the folders are data in tests/fixtures/render.

    python tools/make_phase_fixtures.py [--captures DIR]

Every fixture says where its truth comes from in fixture.json `source`. Nothing here decides a verdict: the runners (skin_editor/render/fixtures.py) do."""
import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from skin_editor import config, project, tiles                       # noqa: E402
from skin_editor.render import captures, fixtures                     # noqa: E402

UI = Path(r"C:\Users\Admin\FMSKINNING\workspace\notes\ui-dumps")
BUILD = "27.0.1.2503222"


def write(name, fixture, expect, dump=None, proj=None):
    d = fixtures.FIXTURES / name
    d.mkdir(parents=True, exist_ok=True)
    fixture = dict({"name": name, "build": BUILD}, **fixture)
    (d / "fixture.json").write_text(json.dumps(fixture, indent=1), encoding="utf-8")
    (d / "expect.json").write_text(json.dumps({"checks": expect}, indent=1), encoding="utf-8")
    if dump is not None:
        (d / "dump.json").write_text(json.dumps(dump), encoding="utf-8")
    if proj is not None:
        (d / "project.json").write_text(json.dumps(proj, indent=1), encoding="utf-8")
    print("fixture", name)


def phase_projects(ws):
    # 1. Phase 3: the red rule on the pitch container (LEARNINGS.md); the element is added in code, so a synthetic node carries the class
    red = project.new("phase3-red-pitch")
    red["scoped_rules"] = [{"sheet": "AlwaysAppliedStyleSheet", "selector": ".tactics-collapsable-pitch-container.tactics-collapsable-pitch-container",
                            "props": {"background-color": {"rgb": "#6C001C", "a": 1.0}}, "why": "hard-coded #DA0037 in the game's rule; the doubled class raises specificity above it"}]
    write("phase3-red-pitch", {"kind": "rule", "source": "LEARNINGS.md Phase 3 rule and the in-game screenshot held by the owner. NOTE: no layout holds an element with this class (the game adds it in code), "
                               "so the check runs on a synthetic node carrying the class: it verifies the cascade (the project's rule wins over the game's), NOT that the element is the pitch container. "
                               "CORRECTION recorded 2026-11-14: the first version of this fixture expected the game's own colour to be #DA0037, as LEARNINGS.md (section on the Crimson skin's pitch) states; the "
                               "framework's first run showed the game's own rule in this build is #036150 (AlwaysAppliedStyleSheet rule 3904 and FigmaGeneratedStyles 2964; no pitch rule holds #DA0037), so the "
                               "expectation was a fixture error taken from a note about a skin, and it was fixed to the game's data, not to the render's output by tolerance."},
          [{"id": "project-rule-wins", "kind": "rule", "node": {"type": "VisualElement", "classes": ["tactics-collapsable-pitch-container"]}, "property": "background-color",
            "expect": {"value": "#6C001C", "origin": "project", "selector": ".tactics-collapsable-pitch-container.tactics-collapsable-pitch-container"},
            "above_vanilla": ".tactics-collapsable-pitch-container"},
           {"id": "vanilla-is-the-games-colour", "kind": "rule", "skin": False, "node": {"type": "VisualElement", "classes": ["tactics-collapsable-pitch-container"]}, "property": "background-color",
            "expect": {"value": "#036150", "origin": "vanilla", "selector": ".tactics-collapsable-pitch-container"}}], proj=red)
    # 2. Phase 5/6: the class patch that made the Reload Skin row magenta
    p6 = project.load(ws, "p6-class-test")
    write("p6-magenta-reload-skin", {"kind": "layout", "layout": {"name": "PreferencesFMMenuCard"}, "skin": True,
                                     "source": "p6-class-test (the owner's project), PHASE6-EVIDENCE: magenta seen around the Reload Skin row in game, screenshot held by the owner"},
          [{"id": "class-patch-paints-the-button", "kind": "rule", "element": {"type": "VisualElement", "name": "reload-skin-button"}, "property": "background-color",
            "expect": {"value": "#FF00FF", "origin": "project", "selector": ".p6-loud"}},
           {"id": "vanilla-has-no-magenta", "kind": "rule", "skin": False, "element": {"type": "VisualElement", "name": "reload-skin-button"}, "property": "background-color",
            "expect_absent": True}], proj=p6)
    # 3. Phase 7 c3: the Squad overview Physical table
    t3 = project.load(ws, "p7-table-test-3")
    hdr = ["position-dropdown", "inf-team", "portrait-name", "attribute-acceleration", "attribute-agility", "attribute-balance", "attribute-jumping-reach", "attribute-natural-fitness",
           "attribute-pace", "attribute-stamina", "attribute-strength"]
    edited = ["position-dropdown", "inf-team", "portrait-name", "attribute-pace", "attribute-acceleration", "attribute-agility", "attribute-balance", "attribute-natural-fitness",
              "attribute-stamina", "attribute-strength"]
    write("c3-table-header", {"kind": "table", "table": {"name": "FirstTeamTableAttributesPhysical", "breakpoint": 3},
                              "source": "c3-table screenshot 2026-11-13 and the header row written down in INGAME-CHECKLIST.md (Picked, Inf, Player, Pace, Acceleration, Agility, Balance, Natural Fitness, "
                                        "Stamina, Strength; stock order with Jumping Reach); project p7-table-test-3"},
          [{"id": "header-skin", "kind": "table", "skin": True, "header": edited, "absent": ["attribute-jumping-reach"]},
           {"id": "header-vanilla", "kind": "table", "skin": False, "header": hdr}], proj=t3)
    # 4. Phase 7 b1/b2: instructions left, pitch right, at Standard and Large
    moves = tiles.ops_for(ws, "p7-tile-test")
    for bp in ("Standard", "Large"):
        comp = "TacticalPlannerTeamInstructionsTabComposition-" + bp
        write("tiles-" + bp.lower(), {"kind": "tiles", "screen": {"composition": comp, "area": [2361.3, 1213.9], "padding": 0, "reserved_right": 4, "moves": [m for m in moves if m["composition"] == comp]},
                                      "source": "p7-tile-test (the owner's project, stored placement edits) and the tile-1/tile-2 screenshots: instructions left, pitch right at Small and Large in game. "
                                                "Only the left/right relation is checked: the absolute x of those screenshots (40 and 1274 / 865) was taken on another panel size."},
              [{"id": "vanilla-pitch-left", "kind": "tiles", "skin": False, "relations": [{"left": "TeamInstructionsPitch", "right": "TeamInstructionsBlock", "expect": True}]},
               {"id": "skin-instructions-left", "kind": "tiles", "skin": True, "relations": [{"left": "TeamInstructionsBlock", "right": "TeamInstructionsPitch", "expect": True},
                                                                                              {"left": "TeamInstructionsPitch", "right": "TeamInstructionsBlock", "expect": False}]}])


def c2_loans():
    doc = json.loads((UI / "c2-loans-tile-tree-27_0_1_2503222-20261113.json").read_text(encoding="utf-8"))
    nodes = {}
    for p, n in doc["nodes"].items():
        m = re.match(r"^([A-Za-z0-9_`]+)(?:#([^.]*))?", n.get("label", ""))
        if m and n.get("bounds"):
            nodes[p] = {"label": n["label"], "type": m.group(1), "name": m.group(2) or "", "visible": True, "depth": n.get("depth"), "bounds": n["bounds"], "text": n.get("text", ""),
                        "binder": None, "resolved": {}}
    write("tile-loans-c2-dump", {"kind": "layout", "layout": {"name": "LoansTile_4x2"}, "skin": False, "delivered": False,
                                 "source": "inspector fm_dump_tree of the Loans tile, c2 session 2026-11-13 (Small + Larger text): the M0 spike's reference"},
          [{"id": "geometry", "kind": "boxes"}], dump={"root": next(iter(nodes)), "host": "Loans", "nodes": nodes})


SCREENS = [
    ("screen-squad-large-2500", "styles-d1-squad-overview-20261114-111054.ndjson", "SquadComposition-Large", 0, 12, ["SquadHierachy", "MedicalCentre", "Loans"], "FirstTeamOverview"),
    ("screen-squad-large-1600", "styles-d6-squad-overview-medium-20261114-113402.ndjson", "SquadComposition-Large", 0, 12, ["SquadHierachy"], "FirstTeamOverview"),
    ("screen-squad-large-1680", "styles-e2-squad-small-20261114-115336.ndjson", "SquadComposition-Large", 0, 12, [], "FirstTeamOverview"),
    ("screen-squad-standard", "styles-e4-squad-1600x900-20261114-115839.ndjson", "SquadComposition-Standard", 0, 12, [], "FirstTeamOverview"),
    ("screen-squad-small", "styles-e3-squad-1152x864-20261114-115626.ndjson", "SquadComposition-Small", 0, 12, [], "FirstTeamOverview"),
    ("screen-team-instructions-large", "styles-d2-team-instructions-20261114-111314.ndjson", "TacticalPlannerTeamInstructionsTabComposition-Large", 4, 0,
     ["ClubTeamReport", "SetPieces", "DataHub", "Penalties", "Captains"], "TeamInstructionsPitch"),
]


def screens():
    for name, file, comp, reserved, pad, runtime, anchor in SCREENS:
        cap = captures.read_capture(UI / file)
        hosts = [e for e in cap.elements.values() if e["type"] == "BindableVariableSizedGridElement"]
        parent_path = next(h["path"].rsplit("/", 1)[0] for h in hosts if h["name"] == anchor)
        parent = cap.elements[parent_path]
        in_grid = {h["name"]: h for h in hosts if h["path"].rsplit("/", 1)[0] == parent_path}
        slots = []
        for n in runtime:
            if n in in_grid:
                px = in_grid[n]["inline"]
                g = lambda k: int(str(px[k]).replace("px", ""))
                slots.append({"element_id": n, "col": round((g("left") - pad) / 82), "row": round((g("top") - pad) / 82), "w": round((g("width") + 16) / 82), "h": round((g("height") + 16) / 82)})
        predicted = {n: [round(v, 1) for v in h["world"]] for n, h in in_grid.items() if n not in runtime}
        write(name, {"kind": "screen", "skin": False, "screen": {"composition": comp, "area": [round(parent["world"][2], 1), round(parent["world"][3], 1)], "padding": pad,
                                                                  "reserved_right": reserved, "origin": [parent["world"][0], parent["world"][1]], "runtime_slots": slots},
                     "source": "capture %s (plugin %s); hosts of the grid container; the run-time slots are GIVEN (cells from the capture) and are not predictions" % (file, cap.header.get("plugin"))},
              [{"id": "hosts", "kind": "screen", "boxes": predicted}])


def i3_states():
    """Session G (docs/evidence/phase9-i3-session-G-20261114.md): state readings taken by hand on the baseline plugin, 2026-11-14. Values are the inspector's resolved values, copied
    from the saved replies (workspace/notes/ui-dumps/i3g-20261114/g-*.json), not from the render."""
    def el(ty, name, classes, states=()):
        return {"type": ty, "name": name, "classes": classes.split(), "states": list(states)}
    btn = "HasSIClickable row-direction-normal buttons-button-base-default button-size-medium navigatable-no-cursor"
    row = "streamed-table__row row-direction-normal streamed-list-view__disable-controller-cell streamed-list-view-item streamed-list-view__row--interactable virtualised-list__item"
    news = ("sibutton navigatable HasSIClickable portal-messages-item-default-style-unread-property-1-message-property-2-default row-direction-normal margin-horizontal-global-gap-none "
            "padding-left-global-padding-regular padding-right-global-padding-large border-color-theme-core-base-border-base-default padding-vertical-global-padding-extra-large "
            "margin-vertical-global-gap-none message-button")
    tile = "sibutton navigatable HasSIClickable interactable-tile layout-tile-interaction-button layout-tile-interaction-button-background anchor-loans"
    bg = "background-color"

    def chk(i, chain, state, rest=None, prop=bg, **kw):
        d = {"id": i, "kind": "state", "chain": chain, "property": prop, "state": state}
        if rest is not None:
            d["rest"] = rest
        d.update(kw)
        return d
    nav_chain = lambda st, light=False: ([el("VisualElement", "MainNav", "tile-mockups-navigation-core-primary-hi-res nav-on-light")] if light else []) + [
                            el("SIButton", "buttons-button-navigation-default", "sibutton navigatable HasSIClickable navigation-tab-portal-default-active-false margin-horizontal-global-gap-none buttongroup__button", ["hover"]),
                            el("VisualElement", "", "thematic-md justify-content-center", ["hover"]),
                            el("VisualElement", "MainFrame", "row-direction-normal align-items-center", ["hover"]),
                            el("SIVisible", "TextVisible", ""),
                            el("SIText", "text", "sitext portal-text margin-right-global-gap-none sitext-hover-cursor margin-right-global-gap-small thematic-md", st)]
    checks = [
        chk("filter-hover", [el("SIButton", "", btn, ["hover"])], "#FFFFFF33", "#FFFFFF24"),
        chk("filter-press-held", [el("SIButton", "", btn, ["hover", "active", "focus"])], "#FFFFFF24", "#FFFFFF24", observation="read with mask 67 (active+hover+focus); background #FFFFFF24 while pressed (one reading)",
            interpretations=[{"text": "the static rule .buttons-button-base-default:active:enabled (specificity 31) declares var(--core-controls-surface-pc-pressed) = #FFFFFF24, equal to rest, and outranks :hover (21)", "status": "derived",
                              "note": "single source: a lookup made AFTER the model was changed (:enabled added) on this same reading; not an independent observation of the press state"}]),
        chk("filter-dragged-off-held", [el("SIButton", "", btn, ["focus"])], "#FFFFFF24", "#FFFFFF24", noop=True, note="mask 64 (focus only) with the mouse still held"),
        chk("filter-released", [el("SIButton", "", btn)], "#FFFFFF24", "#FFFFFF24", noop=True),
        chk("loans-tile-hover", [el("SIButton", "layout-tile-interaction-button", tile, ["hover"])], "#2E3138", "#17223F"),
        chk("nav-tab-label-hover", nav_chain(["hover"]), "#FFFFFF", "#EBEBEB", prop="color", conditional=True,
            observation="Measured: label colour #FFFFFF under the pointer, rest #EBEBEB; label mask 0; ancestors 2 (SIButton, the two wrappers). Not measured: why.",
            interpretations=[{"text": "this row sets hover on the label itself, which the mask did not show: it is CONDITIONAL on that inference", "status": "inferred"},
                             {"text": "a rule in the game's applied sheets, .navigation-tab-portal-default-active-false .portal-text:hover, declares #FFFFFF for a hovered label", "status": "derived"}]),
        chk("nav-tab-label-as-read", nav_chain([], True), "#FFFFFF", "#EBEBEB", prop="color", variant_of="nav-tab-label-hover",
            observation="the same reading with the states AS READ: label 0, ancestors hover (2); the game's applied sheets only",
            interpretations=[{"text": "if this FAILS, no rule in the applied sheets colours the label through a hovered ancestor", "status": "derived"}]),
        chk("nav-tab-label-as-read-runtime-sheet", nav_chain([], True), "#FFFFFF", "#EBEBEB", prop="color", variant_of="nav-tab-label-hover", runtime_sheet_capture="styles-e1-squad-bindings-20261114-115217.ndjson",
            observation="the same reading with the states AS READ (label 0, ancestors hover), plus the RECORDED run-time sheet (empty name, negative instance id) of the squad capture, whose sampled rules include "
                        ".nav-on-light .navigation-tab-portal-default-active-false:hover .portal-text { color: var(--colours-base-neutral-white) }; the label's ancestor MainNav carries nav-on-light in that capture",
            interpretations=[{"text": "an ancestor-hover rule yields #FFFFFF under the masks as read, so the label's own hover is not needed to explain the colour", "status": "derived"},
                             {"text": "whether the game applies that recorded rule to this label at this moment is not observed; a stale mask read is NOT excluded (no repeated reads were taken), and inheritance was not tested", "status": "inferred"}]),
        chk("table-row-hover", [el("BindingRoot", "", row, ["hover"])], "#FFFFFF1A", "#FFFFFF00", note="even row of the zebra list; odd rows rest at #FFFFFF0F (the zebra rule is not part of this check)"),
        chk("inbox-row-hover", [el("SIButton", "NewsItemButton", news, ["hover"])], "#FFFFFF14", "#00000000"),
        chk("inbox-row-clicked-focus", [el("SIButton", "NewsItemButton", news, ["focus"])], "#00000000", "#00000000", noop=True, note="after the selection click the row's button carries mask 64 and no colour change"),
        chk("pitch-marker-hover", [el("VisualElement", "", "projected--position--filled", ["hover"])], "#00000000", "#00000000", noop=True, note="mask 2 on the marker and every descendant read; colour and background unchanged"),
        chk("pitch-marker-label-hover", [el("VisualElement", "", "projected--position--filled", ["hover"]), el("VisualElement", "", "content-tactics-visualiser-player-indicator-simple", ["hover"])],
            "#EBEBEB", "#EBEBEB", prop="color", noop=True),
        chk("instruction-tile-hover", [el("TemplateContainer", "TeamInstructionTile", "height-100-percent", ["hover"])], "#00000000", "#00000000", noop=True,
            note="mask 2 five levels down; colour, background and border unchanged at every level read"),
        {"id": "inbox-selection-class-swap", "kind": "classswap", "element": {"type": "SIStyleSetter", "name": "SIStyleSetter_IsLastSelected"},
         "from": ["flex-grow-class", "row-direction-normal", "message-not-last-selected"], "to": ["flex-grow-class", "row-direction-normal", "message-last-selected"],
         "observed": "class swap seen; no property measured on the setter",
         "note": "the class swap was seen (setters idx 1,22 -> 3,24); no colour was read on the setter, so the render's one declared difference (colour #EBEBEB on the selected setter, inherited by its children) has nothing to compare against"}]
    # U4 (v1.1.0): every published check above gives the cascade a TRUNCATED chain (the element and the ancestors Session G read, at most five). They keep their verdicts and are marked chain_truncated.
    # Next to each one, a variant on the REAL ancestry of the same element from the captures (tools/make_state_chains.py), one variable changed per variant.
    for c in checks:
        if c["kind"] == "state":
            c["chain_truncated"] = True
    import json as _json
    cp = ROOT / "tests" / "fixtures" / "render" / "state-i3-session-g" / "chains.json"
    chains = _json.loads(cp.read_text(encoding="utf-8"))["targets"] if cp.is_file() else {}

    def real(key, target_states, anc_hover=True):
        ch = chains[key]["chain"]
        return [{"type": e["type"], "name": e["name"], "classes": list(e["classes"]), "states": (list(target_states) if i == len(ch) - 1 else (["hover"] if anc_hover else []))} for i, e in enumerate(ch)]

    def src(key):
        t = chains[key]
        return "real ancestry from %s: %d elements root first, %d match(es) in the capture, the first taken; ancestors of a hovered element are given the hover state (Unity sets :hover up the parent chain; Session G read it on at most five levels)" % (t["capture"], t["depth"], t["matched"])
    if chains:
        pairs = [("filter-hover", "filter-button", ["hover"], "#FFFFFF33", "#FFFFFF24", {}),
                 ("filter-press-held", "filter-button", ["hover", "active", "focus"], "#FFFFFF24", "#FFFFFF24", {}),
                 ("filter-dragged-off-held", "filter-button", ["focus"], "#FFFFFF24", "#FFFFFF24", {"anc": False}),
                 ("filter-released", "filter-button", [], "#FFFFFF24", "#FFFFFF24", {"anc": False}),
                 ("loans-tile-hover", "loans-tile-button", ["hover"], "#2E3138", "#17223F", {}),
                 ("table-row-hover", "table-row", ["hover"], "#FFFFFF1A", "#FFFFFF00", {}),
                 ("inbox-row-hover", "inbox-row-button", ["hover"], "#FFFFFF14", "#00000000", {}),
                 ("inbox-row-clicked-focus", "inbox-row-button", ["focus"], "#00000000", "#00000000", {"anc": False}),
                 ("pitch-marker-hover", "pitch-marker", ["hover"], "#00000000", "#00000000", {}),
                 ("instruction-tile-hover", "instruction-tile", ["hover"], "#00000000", "#00000000", {})]
        for cid, key, st, want, rest, o in pairs:
            checks.append(chk(cid + "@real-ancestry", real(key, st, o.get("anc", True)), want, rest, variant_of=cid, isolates="ancestry (the chain is the real one; the states are those of the published row)", chain_source=src(key),
                              note="the Filter button is an SIFloatingPopupWidget in the capture, the published row named it SIButton (a class rule, so the type did not matter)" if key == "filter-button" else ""))
        # the navigation label: one variable per variant (ancestry, label state, both, both plus the recorded run-time sheet)
        nl = "nav-tab-label"
        chk_ = lambda i, chain, **kw: checks.append(chk(i, chain, "#FFFFFF", "#EBEBEB", prop="color", variant_of="nav-tab-label-hover", **kw))
        chk_("nav-tab-label-hover@V1-real-ancestry-only", real(nl, ["hover"]), isolates="ancestry alone: real chain, the label hovered as in the published conditional row", chain_source=src(nl))
        chk_("nav-tab-label-hover@V2-label-state-only", nav_chain([]), isolates="the label's state alone: the published truncated chain, the label NOT hovered (ancestors hovered, as read)", chain_truncated=True)
        chk_("nav-tab-label-hover@V3-real-ancestry-and-as-read", real(nl, []), isolates="both, applied sheets only: real chain, the label not hovered (as read), ancestors hovered", chain_source=src(nl))
        chk_("nav-tab-label-hover@V4-V3-plus-recorded-runtime-sheet", real(nl, []), isolates="V3 plus the recorded run-time sheet layer (an 80-rule CAPTURED SAMPLE of a run-time sheet; U2)", chain_source=src(nl),
             runtime_sheet_capture="styles-e1-squad-bindings-20261114-115217.ndjson", layer="recorded run-time sheet (captured 80-rule sample)")
    write("state-i3-session-g", {"kind": "state", "source": "I3 Session G, manual hover/press/select holds on the baseline plugin 0.2.2 (AllowActions false), 2026-11-14; replies saved as g-*.json in "
                                                              "workspace/notes/ui-dumps/i3g-20261114; log docs/evidence/phase9-i3-session-G-20261114.md. Predictions come from the game's own :pseudo rules "
                                                              "(Cascade.state_declarations); the render itself still applies no state"}, checks)


def main():
    ap = argparse.ArgumentParser()
    ap.parse_args()
    ws = config.workspace(config.load())
    i3_states()
    phase_projects(ws)
    c2_loans()
    screens()


if __name__ == "__main__":
    main()
