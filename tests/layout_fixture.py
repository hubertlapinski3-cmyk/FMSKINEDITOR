"""Synthetic layout dump and style index for the join tests. The dump is built from the contract (docs/fmlayout-index-1.md); a test
runs the contract validator over it so the fixture cannot drift from the contract. Replace with the first real dump when the exporter exists."""
import copy

from skin_editor import index_styles


SOURCE = {"platform_folder": "StandaloneWindows64", "catalog_hash": "c" * 32,
          "bundles": {"ui-a.bundle": "1" * 64, "ui-b.bundle": "2" * 64}}


def manifest(build="27.0.1.2494769", catalog=None, bundles=None, reference=True):
    """A vanilla manifest whose reference hashes match SOURCE (override a part to make a dump stale or contaminated)."""
    m = {"game_build": build, "files": {}}
    if reference:
        m["reference"] = {"platform_folder": SOURCE["platform_folder"], "catalog_hash": catalog or SOURCE["catalog_hash"],
                          "bundles": dict(SOURCE["bundles"] if bundles is None else bundles)}
    return m


def _el(layout_id, local_id, parent, name="", classes=(), runtime=None, typ="UnityEngine.UIElements.VisualElement", ord_=0):
    e = {"layout_id": layout_id, "local_id": local_id, "parent_local_id": parent, "ord": ord_, "type": typ, "name": name, "classes": list(classes)}
    if runtime is not None:
        e["runtime_classes"] = list(runtime)
    return e


def fixture(deep=0):
    """Layouts: 1 Screen (PanelOne) includes 2 Mid includes 3 Leaf (.cls-v, runtime .cls-rt);
    6 Training (PanelTwo, .cls-alias); 7 CycA <-> 8 CycB (PanelCycle, .cls-cyc); 9 SelfInc includes itself (PanelSelf, .cls-self);
    4 PitchHeader (tile of Screen 1). deep=N adds a chain of N layouts above layout 100 (.cls-deep) ending in PanelDeep."""
    L = lambda i, n: {"id": i, "name": n, "guid": ("%032x" % i), "bundle": "b"}
    d = {
        "meta": {"schema": "fmlayout-index/2", "game_build": "27.0.1.2494769", "index_fingerprint": "f" * 40, "exported_at": "2026-11-12T10:00:00Z", "source": copy.deepcopy(SOURCE),
                 "runtime_classes_provenance": "synthetic fixture"},
        "areas": {"map": {"Leaf": "pitch_header", "Screen": "tactics_panel", "Mid": "tactics_panel", "PitchHeader": "pitch_header", "Training": "training"},
                  "anchors": [{"area": "pitch_header", "layout_name_suffix": "Header"}]},
        "layouts": [L(1, "Screen"), L(2, "Mid"), L(3, "Leaf"), L(4, "PitchHeader"), L(6, "Training"), L(7, "CycA"), L(8, "CycB"), L(9, "SelfInc")],
        "elements": [_el(1, 10, None, "root"), _el(1, 11, 10, "slot"), _el(2, 20, None, "mid"), _el(2, 21, 20, "slot2"),
                     _el(3, 30, None, "leaf", ["cls-v"], runtime=["cls-rt"], typ="SI.Bindable.SIButton"),
                     _el(4, 40, None, "ph", ["cls-ph"]), _el(6, 60, None, "tr", ["cls-alias"]),
                     _el(7, 70, None, "a"), _el(7, 71, 70, "slotA"), _el(8, 80, None, "b", ["cls-cyc"]), _el(8, 81, 80, "slotB"),
                     _el(9, 90, None, "s", ["cls-self"]), _el(9, 91, 90, "slotS")],
        "includes": [{"from_layout_id": 1, "element_local_id": 11, "alias": "Mid", "to_layout_id": 2},
                     {"from_layout_id": 2, "element_local_id": 21, "alias": "Leaf", "to_layout_id": 3},
                     {"from_layout_id": 7, "element_local_id": 71, "alias": "B", "to_layout_id": 8},
                     {"from_layout_id": 8, "element_local_id": 81, "alias": "A", "to_layout_id": 7},
                     {"from_layout_id": 9, "element_local_id": 91, "alias": "Self", "to_layout_id": 9}],
        "panels": [{"panel_id": "PanelOne", "layout_id": 1}, {"panel_id": "PanelTwo", "layout_id": 6}, {"panel_id": "PanelCycle", "layout_id": 7},
                   {"panel_id": "PanelSelf", "layout_id": 9}],
        "tiles": [{"panel_layout_id": 1, "set_name": "Set", "breakpoint": 1, "variant_idx": 0, "composition": "Comp", "cell_index": 0,
                   "cell_element_id": "Body", "cfg_index": 0, "size": {"w": 4, "h": 2}, "tile_layout_id": 4}],
        "compositions": [{"name": "Comp", "layout_mode": "0", "preset_name": "", "preset_w": 12, "preset_h": 8, "instantiation_order": [0], "conditions": []}],
        "cells": [{"composition": "Comp", "cell_index": 0, "element_id": "Body", "x": 0, "y": 0, "w": 4, "h": 2, "min_w": 1, "min_h": 1, "max_w": 12, "max_h": 8,
                   "flags": [], "h_align": "0", "v_align": "0"}],
        "cell_configs": [{"composition": "Comp", "cell_index": 0, "cfg_index": 0, "size_w": 4, "size_h": 2, "tile_layout_id": 4}],
    }
    if deep:
        base = 100
        for i in range(deep + 1):
            lid = base + i
            d["layouts"].append(L(lid, "Deep%d" % i))
            d["elements"].append(_el(lid, 1, None, "d%d" % i, ["cls-deep"] if i == 0 else []))
            d["elements"].append(_el(lid, 2, 1, "slot"))
            if i:
                d["includes"].append({"from_layout_id": lid, "element_local_id": 2, "alias": "Deep", "to_layout_id": lid - 1})
        d["panels"].append({"panel_id": "PanelDeep", "layout_id": base + deep})
    return d


def _rule(i, sels, props, token_rule=False):
    return {"i": i, "s": list(sels), "t": 1 if token_rule else 0, "p": props}


def style_index():
    """Tokens: --t0 (colour), --a1: var(--t0), --a2: var(--a1), --lonely (unused). Rules use them through classes that the dump may or may not carry."""
    rules = [
        _rule(0, [":root"], [["--t0", "#112233", [["#112233", 1.0]]], ["--a1", "var(--t0)", []], ["--a2", "var(--a1)", []], ["--lonely", "#445566", [["#445566", 1.0]]]], True),
        _rule(1, [".cls-v"], [["background-color", "var(--t0)", []]]),                              # verified, through include + panel registry
        _rule(2, [".cls-alias"], [["color", "var(--a1)", []]]),                                       # reached only through the alias: other screen
        _rule(3, [".cls-rt"], [["border-color", "var(--t0)", []]]),                                   # runtime-observed on the Leaf button
        _rule(4, [".cls-none"], [["background-color", "var(--t0)", []]]),                             # unverified: no element anywhere
        _rule(5, ["SIButton"], [["background-color", "var(--t0)", []]]),                              # unverified: type-only subject
        _rule(6, [".cls-ph:hover"], [["background-color", "var(--a2)", []]]),                         # alias hop 2, pseudo-class, tile layout
        _rule(7, [".cls-cyc"], [["color", "var(--t0)", []]]), _rule(8, [".cls-self"], [["color", "var(--t0)", []]]),
        _rule(9, [".cls-deep"], [["color", "var(--t0)", []]]),
        _rule(10, [".wrap .cls-v"], [["opacity", "0.5", []]]),                                          # descendant: subject is .cls-v
        _rule(11, [".cls-ph"], [["background-color", "#036150", [["#036150", 1.0]]]]),               # a literal on the tile layout
    ]
    return index_styles.StyleIndex([{"bundle": "b", "name": "AlwaysAppliedStyleSheet", "rules": rules, "failures": []}])
