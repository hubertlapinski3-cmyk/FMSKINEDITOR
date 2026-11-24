"""Stage 5F: the deterministic preview engine (docs/rea/STAGE-5F-PREVIEW-REPORT.md).

The backend computes every preview: the composition selection (from the MEASURED points, with the breakpoint
keys read from the composition set's SERIALIZED data - `m_gridBreakpointCompositionData` - never from name
patterns and never from the dump), the grid (render.screen's formula), the hosts, the tree with exactly ONE
evidence flag per node, the UI-state cascade (the sheets' own pseudo rules, applied by a separate path - the
default render and its calibration are untouched), the placeholder content (seeded, deterministic, never real
data), the optional slots from the serialized composition, and the session's operations.

Everything measured, inferred or estimated is labelled. The browser renders what the backend returns and adds
no geometry, state or classification of its own.

MEASURED composition-switch points (Stage 3E, build C 27.1.0.2505117). Each point stores the window mode and
UI setting it was OBSERVED with - it is never assumed for another combination:

    1024x768   Small      UI setting not recorded (window mode not recorded)
    1440x900   Standard   windowed, Large UI
    1920x1080  Large      Large UI (window mode not recorded)
    1920x1200  Large      windowed, Large UI

A measured width with a DIFFERENT requested UI setting is an ESTIMATE, not a measured claim; a point whose
observed setting was never recorded is an ESTIMATE too (the setting cannot be confirmed). Between the measured
points the selection is an ESTIMATE naming the points it lies between.

The dump (layout dump's `tiles` rows) is kept only as a CROSS-CHECK: the serialized set is authoritative, and
every disagreement becomes a named gap (G21), the G9 pattern.

The Information Display lock is the B-build fact (27.0.1.2503222): the game locks the Information Display
options per resolution. BUILD-C found no bundle value that decides the availability, and a third-party
installer unlocks it by patching game runtime. A locked combination is shown as locked by the game, with
that caveat, and the Playground never offers to unlock it. The Stage 3E measured runs (on C) used Large UI at
every tested width where the setting was recorded, so those combinations are recorded as MEASURED-available.
"""
import hashlib
import json
import os
import random
import re
from functools import lru_cache
from pathlib import Path

from . import compositionset
from . import one_rule
from . import screen as screen_mod
from . import values
from .. import config as _config
from .cascade import Cascade, Entry, P_CLASS, P_ELEMENT, P_ID, P_PSEUDO
from .sheets import ROOT_SHEETS

MEASURED_SOURCE = "Stage 3E runtime tests on build 27.1.0.2505117 (measured on the Squad screen family)"

# (width, height, window mode as recorded, UI setting as recorded, composition suffix, attempt)
MEASURED_POINTS = (
    {"width": 1024, "height": 768, "window_mode": None, "ui_setting": None, "composition": "Small",
     "attempt": "Stage 3E fifth attempt"},
    {"width": 1440, "height": 900, "window_mode": "windowed", "ui_setting": "Large UI", "composition": "Standard",
     "attempt": "Stage 3E final baseline"},
    {"width": 1920, "height": 1080, "window_mode": None, "ui_setting": "Large UI", "composition": "Large",
     "attempt": "Stage 3E fourth attempt"},
    {"width": 1920, "height": 1200, "window_mode": "windowed", "ui_setting": "Large UI", "composition": "Large",
     "attempt": "Stage 3E sixth attempt"},
)
MEASURED_SOURCE_LONG = MEASURED_SOURCE + "; the breakpoint keys are the composition set's own serialized data"

# the DEFAULT game-state scenario: an ordinary career game, not in a match. Slot visibility follows from the
# conditions with their inverse flags applied (game.IsFantasyDraftGame is FALSE in an ordinary career, so a
# slot conditional on it with m_inverseCheck 1 is VISIBLE).
DEFAULT_GAME_STATES = {"game.IsDuringMatch": False, "game.IsFantasyDraftGame": False}
GAME_STATE_SCENARIO = "ordinary career game, not in a match"

# the Information Display lock (the B-build fact; untested on C where not recorded - see the module docstring)
ID_LOCK = {
    "statement": "the game locks the Information Display options per resolution (build B fact, 27.0.1.2503222)",
    "evidence": ("BUILD-C: the availability rule is not a layout or style value in the bundles; a third-party "
                 "installer unlocks it by patching game runtime. The B-build fact stays labelled as a B "
                 "fact; on 27.1 the limit is untested."),
    "measured_available_on_C": [[1440, 900, "Large UI"], [1920, 1080, "Large UI"], [1920, 1200, "Large UI"],
                                [2560, 1440, "Large UI"]],
    "locked": [[1024, 768, "Large UI"], [1024, 768, "Normal UI"]],
    "locked_evidence": ("the game locks the Information Display options per resolution; the unlock is a "
                        "game runtime patch (BUILD-C: no bundle value decides the availability). At "
                        "1024x768 the game produced the Small composition (Stage 3E fifth attempt), so the "
                        "wider options are treated as locked there - an inference, labelled ESTIMATE"),
}

SETTINGS = ("Small UI", "Normal UI", "Large UI")
OFFERED_STATES = ("hover", "pressed")
DECLARED_STATES = ("checked", "selected", "focus")     # offered only where the sheets declare a rule
RUNTIME_STATES = ("drag", "hovered-ancestor")          # code-set: only if in the measured runtime classes

SLICE_DIRECTIONS = ("m_topLeft", "m_top", "m_topRight", "m_left", "m_right", "m_bottomLeft", "m_bottom",
                    "m_bottomRight")

# the element types the game draws in code (labelled placeholder boxes, real geometry)
CODE_DRAWN = ("PitchElement", "PitchView", "GraphView", "ChartElement", "HeatMapElement", "ShirtElement",
              "BadgeElement", "StarRating", "SmallStarRating", "CircleRating", "FormGuideElement",
              "SmallAmountTextElement", "GaugeElement", "MiniPitchElement")


def _measured_point_for(width):
    """The measured point the width's composition comes from (the canonical point), plus the corroborating
    point at the same width when there is one."""
    if width <= 1024:
        primary = MEASURED_POINTS[0]
    elif width < 1920:
        primary = MEASURED_POINTS[1]
    else:
        primary = MEASURED_POINTS[2]
    others = [p for p in MEASURED_POINTS if p["width"] == primary["width"] and p is not primary]
    return primary, others


def _between(width):
    if width < 1024:
        return None, MEASURED_POINTS[0]
    if width < 1440:
        return MEASURED_POINTS[0], MEASURED_POINTS[1]
    if width < 1920:
        return MEASURED_POINTS[1], MEASURED_POINTS[2]
    return MEASURED_POINTS[2], None


def _selection_label(points_all, primary, width, setting):
    """(label, evidence). MEASURED only when the width is a measured one AND the requested UI setting is the
    setting that point was observed with (and it was recorded). Everything else is an ESTIMATE, naming why."""
    observed, win = primary["ui_setting"], primary["window_mode"]
    where = "%dx%d" % (primary["width"], primary["height"])
    if width == primary["width"] and observed and setting == observed:
        if win:
            return ("MEASURED at %s (%s, %s): %s" % (where, win, setting, MEASURED_SOURCE), "MEASURED")
        return ("MEASURED at %s with %s; the window mode was not recorded, so a windowed/fullscreen difference in "
                "usable width is unverified: %s" % (where, setting, MEASURED_SOURCE), "MEASURED")
    if width == primary["width"]:
        if not observed:
            return ("ESTIMATE: the composition was measured at %s, but the UI setting it was observed with was "
                    "not recorded, so the requested %s cannot be confirmed (the width rule is Stage 3E's)"
                    % (where, setting), "ESTIMATE")
        return ("ESTIMATE: the point at %s was measured with %s, not the requested %s (the width rule is "
                "Stage 3E's)" % (where, observed, setting), "ESTIMATE")
    lo, hi = _between(width)
    if lo is None:
        claim = "below the smallest measured point (%s)" % where
    elif hi is None:
        claim = "above the largest measured point (%s)" % where
    else:
        claim = "between the measured points %dx%d (%s) and %dx%d (%s)" % (
            lo["width"], lo["height"], lo["composition"], hi["width"], hi["height"], hi["composition"])
    note = ""
    if observed and setting != observed:
        note = "; the nearest point was measured with %s, not the requested %s" % (observed, setting)
    elif not observed:
        note = "; the nearest point's UI setting was not recorded"
    return ("ESTIMATE %s%s: %s" % (claim, note, MEASURED_SOURCE), "ESTIMATE")


def _public_points():
    return [{"width": p["width"], "height": p["height"], "window_mode": p["window_mode"],
             "ui_setting": p["ui_setting"], "composition": p["composition"], "attempt": p["attempt"]}
            for p in MEASURED_POINTS]


def _dump_set_rows(dump, family):
    rows = [t for t in dump.get("tiles") or [] if t.get("set_name") == family]
    if not rows:
        stem = family.split("-")[0]
        rows = [t for t in dump.get("tiles") or []
                if (t.get("composition") or "").startswith(stem + "-") or (t.get("composition") or "") == family]
    return rows


def _key_for(refs_by_key, suffix, family):
    """The breakpoint key from the SERIALIZED mapping: the composition that ends with the MEASURED suffix
    (`-Small`/`-Standard`/`-Large`, never an FMC variant), then by size order. The requested `family` never
    decides the key: the measured width does."""
    for key, refs in sorted(refs_by_key.items()):
        if any((c.get("name") or "").endswith("-" + suffix) and "FMC" not in (c.get("name") or "")
               for c in refs):
            return key
    keys = sorted(refs_by_key)
    order = {"Small": 0, "Standard": 1, "Large": 2}.get(suffix, len(keys) - 1)
    return keys[min(order, len(keys) - 1)]


def _composition_for(refs, suffix, family):
    names = [c.get("name") for c in refs if c.get("name")]
    if family in names:
        return family
    for name in names:
        if name.endswith("-" + suffix) and "FMC" not in name:
            return name
    return names[0] if names else None


def select_breakpoint(dump, family, width, setting="Large UI", sets=None):
    """The composition selection for one width.

    Returns a dict: breakpoint (the serialized key), composition, label/evidence, the measured points with
    their window mode and UI setting, the source (serialized set; the dump only as cross-check), and the
    cross-check with its named gaps. `sets` is compositionset.index(layouts) or a synthetic mapping."""
    primary, corroborating = _measured_point_for(width)
    suffix = primary["composition"]
    clean_family = _measured_name(family)
    set_name, record = compositionset.find(sets or {}, clean_family)
    dump_rows = _dump_set_rows(dump, clean_family) if dump else []
    gaps = []
    if record is None:
        # no serialized set: the dump is the only source. Never claim measured keys; name the gap.
        keys = {}
        for row in dump_rows:
            keys.setdefault(row.get("breakpoint"), []).append({"name": row.get("composition")})
        if not keys and dump and (any(c.get("name") == clean_family for c in (dump.get("compositions") or []))
                                  or any(c.get("composition") == clean_family for c in (dump.get("cells") or []))):
            bp_key = 3 if "Large" in clean_family else 2 if "Standard" in clean_family else 1 if "Small" in clean_family else 0
            keys = {bp_key: [{"name": clean_family}]}
        if not keys:
            raise KeyError("no composition set named %r in the serialized tile bundles or the layout dump" % family)
        set_name = next((r.get("set_name") for r in dump_rows if r.get("set_name")), clean_family)
        source = {"kind": "dump (fallback; no serialized set was supplied)", "asset": "layout dump tiles rows"}
        cross = {"status": "NOT_CHECKED", "source": "layout dump only", "dump_rows": len(dump_rows),
                 "keys_compared": sorted(keys), "gaps": [
                     {"code": "G21", "set": set_name, "kind": "serialized_missing",
                      "detail": "the serialized composition set was not supplied; the breakpoint keys come from "
                                "the dump (D15/G7 show the dump can miss fields)"}]}
    else:
        keys = {k: v for k, v in record["breakpoints"].items()}
        source = {"kind": "serialized", "asset": "m_gridBreakpointCompositionData", "set": set_name,
                  "bundle": record["bundle"], "path_id": record["path_id"]}
        cross = compositionset.cross_check(keys, dump_rows, set_name)
        cross["source"] = "serialized m_gridBreakpointCompositionData"
    key = _key_for(keys, suffix, clean_family)
    composition = _composition_for(keys.get(key) or [], suffix, clean_family)
    if not composition:
        raise KeyError("the composition set %r has no composition at breakpoint %r" % (set_name, key))
    label, evidence = _selection_label(MEASURED_POINTS, primary, width, setting)
    if record is None:
        evidence = "ESTIMATE"
        label = ("ESTIMATE: the serialized composition set was not supplied, so the breakpoint keys come from "
                 "the layout dump (D15/G7 show it can miss fields); " + label)
    return {"breakpoint": key, "composition": composition, "label": label, "evidence": evidence,
            "setting": setting, "width": width,
            "measured_points": _public_points(),
            "corroborating_points": [{"width": p["width"], "height": p["height"], "window_mode": p["window_mode"],
                                      "ui_setting": p["ui_setting"], "composition": p["composition"]}
                                     for p in corroborating],
            "source": source, "cross_check": cross, "gaps": cross.get("gaps") or []}


def _lock_for(setting, width, height=None):
    """The Information Display availability for one (setting, resolution): locked / available / unknown, with
    the reason and its evidence class."""
    for w, h, s in ID_LOCK["locked"]:
        if width <= w and setting == s:
            return {"setting": setting, "locked": True,
                    "reason": "locked by the game at %dx%d: %s" % (w, h, ID_LOCK["locked_evidence"]),
                    "evidence": "ESTIMATE (inferred from the B-build per-resolution lock and the Stage 3E Small "
                                "observation)"}
    for w, h, s in ID_LOCK["measured_available_on_C"]:
        if setting == s and width >= w:
            return {"setting": setting, "locked": False,
                    "reason": "available: MEASURED on C at %dx%d with %s (Stage 3E)" % (w, h, s),
                    "evidence": "MEASURED"}
    return {"setting": setting, "locked": False,
            "reason": "the (resolution, setting) combination is not in the measured table; the game's "
                      "availability rule is decided in code, not in the bundles",
            "evidence": "UNKNOWN (the B-build lock is per resolution; untested on C for this combination)"}


def apply_max_sizes(assembler, composition, max_sizes):
    """The session's SetCellMaxSize maxima applied to COPIES of the composition's cells (CL3: for every composition, since rule V5+C2 is wired for all).
    Returns the element ids changed."""
    sizes = {m["cell_element_id"]: m["max_size"] for m in max_sizes or [] if m.get("composition") == composition}
    if not sizes:
        return []
    done, cells = [], []
    for c in assembler.cells.get(composition, []):
        if c["element_id"] in sizes:
            mx = sizes[c["element_id"]]
            c = dict(c, max_w=int(mx["x"]), max_h=int(mx["y"]))
            done.append(c["element_id"])
        cells.append(c)
    assembler.cells[composition] = cells
    return done


# E2E1 / UI5: the measured panel content rects at the pinned 2560x1440 windowed, Small, Larger setting
# (C3, Tests C and D, CL3 B1, JX X1 to X3: Squad is 30 x 16, the window minus the title bars; the whole-window
# estimate 31 x 17 is one column and one row too many).
from .. import layoutspace as _layoutspace

MEASURED_VIEWPORT = dict(_layoutspace.MEASURED_VIEWPORT)
MEASURED_PANEL_RECTS = {
    ("SquadComposition-Large", 2560, 1440): ("SquadScreen", (15.6, 85.9, 2468.8, 1319.3)),
    ("Portal-Large", 2560, 1440): ("PortalScreen", (15.6, 85.9, 2468.8, 1319.3)),
    ("ClubProfileCardGridComposition-Large", 2560, 1440): ("ClubProfileCard", (15.6, 85.9, 2468.8, 1319.3)),
    ("CoachReportCardGridComposition-Large", 2560, 1440): ("CoachReportCard", (15.6, 85.9, 2468.8, 1319.3)),
    ("ContractNegotiationPromisesGridComposition_Large", 2560, 1440): ("ContractNegotiationTool", (18.6, 85.9, 2139.6, 1319.3)),
    ("InjuryHistoryCardGridComposition", 2560, 1440): ("InjuryHistoryCard", (15.6, 85.9, 2468.8, 1319.3)),
    ("PersonBiographyCardGridComposition-Large", 2560, 1440): ("PersonBiographyCard", (15.6, 85.9, 2468.8, 1319.3)),
    ("PlayerContractUserOwnedNoWorkPermitGridComposition-Large", 2560, 1440): ("PlayerContractCard", (15.6, 265.6, 2468.8, 1074.2)),
    ("PlayerReportFitnessCardGridComposition-Large", 2560, 1440): ("PlayerReportFitnessCard", (15.6, 85.9, 2468.8, 1319.3)),
    ("PlayerReportPersonal-Large", 2560, 1440): ("PlayerReportPersonal", (15.6, 273.4, 2468.8, 1074.2)),
    ("PlayingTimeCardGridComposition-Large", 2560, 1440): ("PlayingTimeCard", (15.6, 85.9, 2468.8, 1319.3)),
    ("PlayerReportOverviewComposition-Large", 2560, 1440): ("PlayerReport", (15.6, 273.4, 2468.8, 1074.2)),
    ("HomegrownStatusToolGridComposition-Large", 2560, 1440): ("HomegrownStatusTool", (15.6, 85.9, 2468.8, 1319.3)),
    ("PlayerReportDevelopmentProgressReportCardGridComposition-Large", 2560, 1440): ("PlayerReportDevelopmentProgressReportCard", (15.6, 85.9, 2468.8, 1319.3)),
    ("TacticalEffectivenessGridComposition-Large", 2560, 1440): ("TacticalEffectivenessCard", (15.6, 85.9, 2468.8, 1319.3)),
    ("TeamIndividualTrainingToolTileComposition-Large", 2560, 1440): ("TeamIndividualTrainingTool", (15.6, 85.9, 2468.8, 1319.3)),
    ("TransferStatusCardGridComposition-Large", 2560, 1440): ("TransferStatus", (15.6, 273.4, 2468.8, 1074.2)),
}
RULE_LABEL = "rule V5+C2: fitted on 10 screens, passed 6 out of sample including one growth test"
CUSTOM_LABEL = "custom layout from the game folder"


# UI1 / FS1: generated per-composition parity (windowed) and FS1 fullscreen measurements drive
# profile-isolated preview confidence labels and measured panel content rects.
PARITY_RELATIVE_PATH = "docs/rea/data/layout-parity.json"
PARITY_PATH_ENV = "FM27_LAYOUT_PARITY"          # relocation/test override; never written by the app
FULLSCREEN_MEASUREMENTS_RELATIVE_PATH = "docs/rea/data/fullscreen-2k-measurements.json"
FULLSCREEN_MEASUREMENTS_ENV = "FM27_FULLSCREEN_MEASUREMENTS"
CONFIDENCE_LABELS = ("measured", "measured mismatch", "computed", "unverified")


def parity_path():
    """Where the generated parity data lives. The repo file is the default; an explicit override lets a
    test (or a relocated install) point at another copy without changing code."""
    override = os.environ.get(PARITY_PATH_ENV)
    return Path(override) if override else _config.resource_root() / PARITY_RELATIVE_PATH


def fullscreen_measurements_path():
    """Where the FS1 fullscreen 2560x1440 Small/Larger measurement & scoring table lives."""
    override = os.environ.get(FULLSCREEN_MEASUREMENTS_ENV)
    return Path(override) if override else _config.resource_root() / FULLSCREEN_MEASUREMENTS_RELATIVE_PATH


def _measured_name(name):
    """A measured case may name the screen in parentheses or carry a .json/.Clone suffix; the key is the bare composition."""
    s = re.sub(r"\s*\([^)]*\)\s*$", "", str(name or "")).strip()
    s = re.sub(r"\(Clone\)$", "", s).strip()
    return re.sub(r"\.json$", "", s, flags=re.I)


@lru_cache(maxsize=8)
def layout_parity(path=None):
    """Read the generated parity data once per path. Read only. A missing/corrupt file degrades to an
    explicit 'no data' record (the preview must keep working); the backend test asserts the repo file."""
    path = str(path or parity_path())
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8-sig"))
        rows = {r["composition"]: r for r in data.get("compositions") or []}
        measured = {}
        for case in data.get("measured_cases") or []:
            measured.setdefault(_measured_name(case.get("composition")), []).append(case)
        return {"available": True, "path": path, "generator": data.get("generated_by"),
                "counts": data.get("counts") or {}, "method": data.get("method") or {},
                "rows": rows, "measured": measured}
    except (OSError, ValueError, TypeError, KeyError, AttributeError):
        return {"available": False, "path": path, "generator": None, "counts": {},
                "method": {}, "rows": {}, "measured": {}}


@lru_cache(maxsize=8)
def fullscreen_measurements(path=None):
    """Read FS1 fullscreen 2560x1440 Small/Larger measurements once per path. Windowed cases never appear here."""
    path = str(path or fullscreen_measurements_path())
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8-sig"))
        rows = {r["composition"]: r for r in (data.get("compositions") or []) if r.get("composition")}
        return {"available": True, "path": path, "profile": data.get("profile"),
                "counts": data.get("counts") or {}, "rows": rows}
    except (OSError, ValueError, TypeError, KeyError, AttributeError):
        return {"available": False, "path": path, "profile": None, "counts": {}, "rows": {}}


def panel_content_rect(composition, width, height, profile=None):
    """Return `(panel_name, (left, top, width, height))` for `composition` under `profile`, or None.

    Profiles are strictly isolated: fullscreen reads ONLY FS1 fullscreen measurements; windowed reads
    ONLY the windowed `MEASURED_PANEL_RECTS` table.
    """
    prof = _layoutspace.normalize_profile(profile)
    if prof == _layoutspace.PROFILE_WINDOWED:
        return MEASURED_PANEL_RECTS.get((composition, width, height))
    if (width, height) not in ((2560, 1440), (0, 0)):
        return None
    fs = fullscreen_measurements(str(fullscreen_measurements_path()))
    row = fs["rows"].get(_measured_name(composition))
    if row and isinstance(row.get("content_rect"), list) and len(row["content_rect"]) == 4:
        return (row.get("panel") or composition, tuple(row["content_rect"]))
    return None


def confidence_for(composition, engine="rea", profile=None):
    """UI1 / FS1 confidence for one preview composition under a viewport profile.

      measured          - measured in-game under this profile and all scored cells match REA <= 1.5 px;
      measured mismatch - measured in-game under this profile with cell(s) > 1.5 px from REA;
      computed          - no measurement under this profile, but generated parity agrees cell-for-cell;
      unverified        - parity disagrees or no record exists for this composition.

    Windowed measurements never count as measured when `profile` is fullscreen (and vice versa).
    When `profile` is omitted (`None`), legacy UI1 windowed parity lookup is used to keep parity checks stable.
    """
    parity = layout_parity(str(parity_path()))
    name = _measured_name(composition)
    row = parity["rows"].get(name)
    other = "one_rule" if engine == "rea" else "rea"
    agree = bool(row["agree"]) if row else None

    use_fullscreen = profile is not None and _layoutspace.normalize_profile(profile) == _layoutspace.PROFILE_FULLSCREEN
    fs_row = fullscreen_measurements(str(fullscreen_measurements_path()))["rows"].get(name) if use_fullscreen else None
    cases = [] if use_fullscreen else parity["measured"].get(name, [])

    mismatches = None
    source_path = parity["path"] if parity["available"] else None
    if use_fullscreen:
        if fs_row is not None:
            source_path = fullscreen_measurements(str(fullscreen_measurements_path()))["path"]
            if fs_row.get("pass"):
                label = "measured"
                reason = ("MEASURED (2560x1440 fullscreen, Small, Larger): %s on %s matched REA across %d host(s) "
                          "(worst %.1f px, within 1.5 px)"
                          % (name, fs_row.get("panel") or "?", fs_row.get("scored_hosts") or 0, fs_row.get("worst_px") or 0.0))
                measured_cases = [{"case": "FS1", "panel": fs_row.get("panel"), "grid": fs_row.get("grid"),
                                   "worst_px": fs_row.get("worst_px"), "scored_hosts": fs_row.get("scored_hosts")}]
            else:
                label = "measured mismatch"
                mismatches = list(fs_row.get("mismatches") or [])
                worst_m = max(mismatches, key=lambda m: m.get("max_px") or 0) if mismatches else {}
                reason = ("MEASURED MISMATCH (2560x1440 fullscreen, Small, Larger): %s on %s cell %s off by %.1f px (%s)"
                          % (name, fs_row.get("panel") or "?", worst_m.get("cell") or "?",
                             worst_m.get("max_px") or fs_row.get("worst_px") or 0.0,
                             worst_m.get("cause") or "differs from REA"))
                measured_cases = [{"case": "FS1", "panel": fs_row.get("panel"), "grid": fs_row.get("grid"),
                                   "worst_px": fs_row.get("worst_px"), "scored_hosts": fs_row.get("scored_hosts"),
                                   "pass": False, "mismatches": mismatches}]
        else:
            measured_cases = None
            if agree is True:
                label = "computed"
                reason = ("COMPUTED (fullscreen profile): no FS1 fullscreen capture, but parity records one_rule "
                          "and REA agreeing on all %d cell(s)" % (row.get("cells") or 0))
            elif agree is False:
                label = "unverified"
                reason = ("UNVERIFIED (fullscreen profile): parity records disagreement on %d of %d cell(s) "
                          "(worst %s px at 2560x1440); no FS1 fullscreen measurement"
                          % (row.get("disagree_cells") or 0, row.get("cells") or 0, row.get("worst_px_2560x1440")))
            else:
                label = "unverified"
                reason = "UNVERIFIED (fullscreen profile): no FS1 fullscreen measurement and no parity record for this composition"
    else:
        measured_ok = bool(cases) and all(c.get("pass") is not False for c in cases)
        if measured_ok and agree is not False:
            label = "measured"
        elif agree is True:
            label = "computed"
        else:
            label = "unverified"
        measured_cases = [{"case": c.get("case"), "worst_px": c.get("worst_px")} for c in cases] or None
        if label == "measured":
            worst_px = max((c.get("worst_px") or 0) for c in cases)
            reason = ("MEASURED: both engines passed %d in-game measured case(s) for this composition "
                      "(worst %.1f px, within the 1.5 px tolerance)" % (len(cases), worst_px))
            reason += ("; the generated parity data also records cell-for-cell agreement" if agree is True
                       else "; this composition is outside the 412-composition Large parity set"
                       if agree is None else "")
        elif label == "computed":
            reason = ("COMPUTED: the generated parity data records one_rule and REA agreeing on all %d cell(s) "
                      "at the Large 1920x1080 point; no in-game measurement for this composition"
                      % (row.get("cells") or 0))
        elif agree is False:
            reason = ("UNVERIFIED: the generated parity data records disagreement on %d of %d cell(s) "
                      "(worst %s cells / %s px at 2560x1440); neither engine is claimed to match the game here"
                      % (row.get("disagree_cells") or 0, row.get("cells") or 0, row.get("worst"),
                         row.get("worst_px_2560x1440")))
        else:
            reason = "UNVERIFIED: no generated parity record and no measured case for this composition"

    other_cells = {}
    for delta in (row.get("deltas") or []) if row else []:
        geometry = delta.get("one_rule" if other == "one_rule" else "rea")
        if isinstance(geometry, list) and len(geometry) == 4:
            other_cells[delta.get("cell")] = {"col": geometry[0], "row": geometry[1],
                                              "w": geometry[2], "h": geometry[3]}
    tip = reason
    if other_cells:
        tip += " | %s geometry per cell (col,row,w,h) is in other_engine_result" % other
        if label == "unverified" and row.get("worst_cell") in other_cells:
            g = other_cells[row["worst_cell"]]
            tip += "; worst cell %s: %s" % (row["worst_cell"], [g["col"], g["row"], g["w"], g["h"]])
    out = {"label": label, "engine": engine,
           "profile": _layoutspace.normalize_profile(profile) if profile is not None else None,
           "composition": name, "other_engine": other,
           "reason": reason, "tooltip": tip,
           "measured_cases": measured_cases,
           "mismatches": mismatches,
           "parity": ({"agree": agree, "cells": row.get("cells"), "worst": row.get("worst"),
                       "worst_px_2560x1440": row.get("worst_px_2560x1440"),
                       "worst_cell": row.get("worst_cell"),
                       "disagree_cells": row.get("disagree_cells")} if row else None),
           "other_engine_result": {"engine": other, "available": bool(other_cells), "cells": other_cells,
                                   "note": ("the other engine's per-cell geometry from the same "
                                            "parity computation" if other_cells else
                                            "no parity record: the other engine's geometry is unavailable")},
           "source": source_path}
    return out


def confidence_summary(profile=None):
    """Label counts over the generated parity set (or FS1 fullscreen set when profile=fullscreen)."""
    parity = layout_parity(str(parity_path()))
    if profile is None or _layoutspace.normalize_profile(profile) == _layoutspace.PROFILE_WINDOWED:
        counts = {"measured": 0, "computed": 0, "unverified": 0}
        for comp in parity["rows"]:
            lbl = confidence_for(comp, "rea", profile=profile)["label"]
            counts[lbl] = counts.get(lbl, 0) + 1
        counts["total"] = sum(counts.values())
        counts["measured_compositions"] = len(parity["measured"])
        return counts
    fs = fullscreen_measurements(str(fullscreen_measurements_path()))
    counts = {k: 0 for k in CONFIDENCE_LABELS}
    names = sorted(set(parity["rows"]) | set(fs["rows"]))
    for comp in names:
        lbl = confidence_for(comp, "rea", profile=_layoutspace.PROFILE_FULLSCREEN)["label"]
        counts[lbl] = counts.get(lbl, 0) + 1
    counts["total"] = len(names)
    counts["measured_compositions"] = len(fs["rows"])
    return counts


def ENGINE_LABEL(engine="one_rule"):
    """Playground-facing name of the layout engine (REA-WIN-4, UI1). The APPLICATION default is
    project.DEFAULT_LAYOUT_ENGINE = "rea"; the low-level preview helpers keep an explicit `engine=`
    parameter (defaulting to one_rule for backwards compatibility) so one_rule stays selectable."""
    return ("engine: one_rule (fitted V5+C2 candidate; explicitly selectable)" if engine != "rea"
            else "engine: REA (game runtime port, 27/27 measured cases)")


def rule_place(a, composition, cols, rows, reflow, moves=(), adds=(), engine="one_rule"):
    """{element_id: {col,row,w,h,mode}} by the chosen layout engine. Default "one_rule" (frozen V5+C2 candidate); "rea" is the statically recovered game runtime port. The session's moves and
    added cells are applied to COPIES of the cells first; reflow 1 compositions get the vertical packing inside place_rule; the optional bottom slots are
    placed by build_preview's own slice rule (not here)."""
    saved = a.cells[composition]
    cells = [dict(c) for c in saved]
    by_id = {c["element_id"]: c for c in cells}
    for o in moves:
        c = by_id.get(o.get("cell_id"))
        if o.get("composition") == composition and c is not None:
            t = o.get("to") or {}
            c["x"], c["y"] = t.get("x", c["x"]), t.get("y", c["y"])
            if t.get("w") is not None:
                c["w"], c["max_w"] = t["w"], max(c.get("max_w", 0), t["w"]) if c.get("max_w", 0) not in (0, None) else c.get("max_w", 0)
            if t.get("h") is not None:
                c["h"], c["max_h"] = t["h"], max(c.get("max_h", 0), t["h"]) if c.get("max_h", 0) not in (0, None) else c.get("max_h", 0)
    for ad in adds:
        g = ad.get("geometry") or {}
        cells.append({"composition": composition, "element_id": ad.get("element_id"), "cell_index": ad.get("cell_index"), "x": g.get("x"), "y": g.get("y"),
                      "w": g.get("w"), "h": g.get("h"), "min_w": g.get("w"), "min_h": g.get("h"), "max_w": g.get("w"), "max_h": g.get("h"), "flags": ["added cell (candidate)"]})
    a.cells[composition] = cells
    try:
        if engine == "rea":
            from . import rea_rule
            return rea_rule.place_rule(a, composition, (max(1, cols), rows), "V5", reflow, None, "equal")
        return one_rule.place_rule(a, composition, (max(1, cols), rows), "V5", reflow, None, "equal")
    finally:
        a.cells[composition] = saved


def _optional_slices_from_custom(custom):
    """m_right / m_bottom of a custom-layout object, in the shape rea_rule expects."""
    obj = (custom or {}).get("m_optionalSlices") or {}
    out = {}
    for zone in ("m_right", "m_bottom"):
        rows = []
        for e in obj.get(zone) or []:
            loc = e.get("m_location") or {}
            rows.append({"element_id": e.get("m_elementID"),
                         "offset": (loc.get("x", 0), loc.get("y", 0)),
                         "size": (loc.get("width", 0), loc.get("height", 0))})
        out[zone] = rows
    return out


def _grid_layout_nodes(node, out):
    if "GridLayout" in (node.get("type") or ""):
        out.append(((node.get("attrs") or {}).get("IgnoreOuterPadding"), node.get("classes") or []))
    for ch in node.get("children") or ():
        _grid_layout_nodes(ch, out)


def composition_padding(engine, composition, content_rect=None, nested=False):
    """A1: GridLayoutSettings m_padding (12) or 0 when IgnoreOuterPadding applies.

    IgnoreOuterPadding  is set either from UXML
    
    or by code when nested inside another GridLayoutElementBase .
    """
    if nested:
        return 0
    default_pad = screen_mod.PADDING
    if engine is None:
        return default_pad
    cache = getattr(engine, "_comp_padding_cache", None)
    if cache is None:
        cache = {}
        engine._comp_padding_cache = cache
    if composition in cache:
        return cache[composition]
    dump = engine._preview_dump()
    comp_lids = getattr(engine, "_comp_to_lids_cache", None)
    if comp_lids is None:
        comp_lids = {}
        for t in dump.get("tiles") or ():
            if t.get("composition") and t.get("panel_layout_id"):
                comp_lids.setdefault(t["composition"], set()).add(t["panel_layout_id"])
        engine._comp_to_lids_cache = comp_lids
    lids = sorted(comp_lids.get(composition) or ())
    if not lids:
        cache[composition] = default_pad
        return default_pad
    layouts_by_id = getattr(engine, "_layouts_by_id_cache", None)
    if layouts_by_id is None:
        layouts_by_id = {l["id"]: l for l in (dump.get("layouts") or ())}
        engine._layouts_by_id_cache = layouts_by_id
    grid_cache = getattr(engine, "_layout_grid_attrs_cache", None)
    if grid_cache is None:
        grid_cache = {}
        engine._layout_grid_attrs_cache = grid_cache
    has_iop_list = []
    for lid in lids:
        layout_info = layouts_by_id.get(lid)
        if not layout_info:
            continue
        if lid not in grid_cache:
            res = engine.render_layout({}, {"name": layout_info["name"], "depth": 20, "max_nodes": 0})
            nodes = []
            for root in res.get("tree") or ():
                _grid_layout_nodes(root, nodes)
            grid_cache[lid] = nodes
        nodes = grid_cache[lid]
        if nodes:
            has_iop_list.append(any(iop == 1 for iop, _ in nodes))
    pad = 0 if (has_iop_list and all(has_iop_list)) else default_pad
    cache[composition] = pad
    return pad


def rule_rects(a, composition, rect, reflow, padding=12, engine="one_rule"):
    """{element_id: [x, y, w, h]} in UI units of a panel whose own grid content rect is `rect` (the measured-case predictor: content rect plus cell_px)."""
    cols, rows = screen_mod.grid_dims_content(rect[2], rect[3])
    out = {}
    for eid, g in rule_place(a, composition, cols, rows, reflow, engine=engine).items():
        px = screen_mod.cell_px(g["col"], g["row"], g["w"], g["h"], padding=padding)
        out[eid] = [round(rect[0] + px["left"], 1), round(rect[1] + px["top"], 1), round(px["width"], 1), round(px["height"], 1)]
    return (cols, rows), out


def screen_hosts(dump, composition, rect, reflow, custom=None, engine="one_rule"):
    """Every host a screen shows, as the measured cases score them: [{element_id, col, row, rect[x, y, w, h]}] for the cells (rule V5+C2, the custom file applied when given) and the
    custom file's optional slices of the regions it holds. m_bottom slices start at the design bottom (the highest cell bottom) plus their offset and are right-anchored like the
    cells they sit under (Test C+D rule, measured column 26); a slice that does not fit the grid is not shown."""
    a = screen_mod.Assembler(dump)
    if custom is not None and apply_custom(a, composition, custom) is None:
        custom = None
    cols, rows = screen_mod.grid_dims_content(rect[2], rect[3])
    c0 = max(c["x"] + c["w"] for c in a.cells[composition])
    hosts = []

    def add(eid, col, row, w, h):
        px = screen_mod.cell_px(col, row, w, h)
        hosts.append({"element_id": eid, "col": col, "row": row,
                      "rect": [round(rect[0] + px["left"], 1), round(rect[1] + px["top"], 1), round(px["width"], 1), round(px["height"], 1)]})

    for eid, g in rule_place(a, composition, cols, rows, reflow, engine=engine).items():
        add(eid, g["col"], g["row"], g["w"], g["h"])
    if engine != "rea":                       # the REA port places optional slices itself (X4 rule)
        bottom = max(c["y"] + c["h"] for c in a.cells[composition])
        for e in ((custom or {}).get("m_optionalSlices") or {}).get("m_bottom") or []:
            geo, _why = place_slice({"location": e["m_location"], "direction": "m_bottom"}, bottom, rows)
            if geo is not None:
                add(e["m_elementID"], geo["x"] + (cols - c0 if geo["x"] + geo["w"] == c0 else 0), geo["y"], geo["w"], geo["h"])
    return hosts


def apply_custom(a, composition, custom):
    """C2: the game's custom-layout file for this composition (a JSON object, skin_editor.custom_layouts) replaces the bundle's cells in the assembler: element id, location,
    min and max size per cell, in file order; cells beyond the bundle's count are ADDED cells (CL3/JX). Returns {"swapped": [(bundle id, file id)], "added": [ids]} for the
    labels, or None when the file does not fit (fewer cells than the bundle has)."""
    cells = a.cells.get(composition)
    comps = custom.get("m_gridComponents") if isinstance(custom, dict) else None
    if not cells or not isinstance(comps, list) or len(comps) < len(cells):
        return None
    base = sorted(cells, key=lambda c: c["cell_index"])
    out, swapped, added = [], [], []
    for i, j in enumerate(comps):
        loc, mn, mx = j["m_location"], j["m_minSize"], j["m_maxSize"]
        fields = dict(element_id=j["m_elementID"], x=loc["x"], y=loc["y"], w=loc["width"], h=loc["height"], min_w=mn["x"], min_h=mn["y"], max_w=mx["x"], max_h=mx["y"])
        if i < len(base):
            c = dict(base[i], **fields)
            if j["m_elementID"] != base[i]["element_id"]:
                swapped.append((base[i]["element_id"], j["m_elementID"]))
        else:
            c = dict(fields, composition=composition, cell_index=i, flags=["added cell (custom layout)"], h_align="0", v_align="0")
            added.append(j["m_elementID"])
        out.append(c)
    a.cells[composition] = out
    return {"swapped": swapped, "added": added}


def grid_for(dump, composition, width, height, reserved_right=0, content_rect=None, expanding=False, max_sizes=None, reflow=None, custom=None, engine="one_rule"):
    """The grid and the placed hosts, from render.screen's own formula. The pitch is looked up per
    composition (render/pitch.json carries the MEASURED pitches; everything else is the ESTIMATE flag the
    module documents, carried into the preview's labels).

    J1: when `content_rect` is given, the grid comes from the panel's measured content extent (floor rule) and
    `expanding` uses the m_reflowMode 0 hypothesis (max-width packing + proportional row sharing).
    """
    a = screen_mod.Assembler(dump)
    if custom:
        apply_custom(a, composition, custom)
    if engine == "rea":
        a.optional_slices = _optional_slices_from_custom(custom)
    apply_max_sizes(a, composition, max_sizes)
    from . import pitch as pitch_mod
    pitch = pitch_mod.lookup(composition)
    if content_rect is not None:
        cols, rows = screen_mod.grid_dims_content(content_rect[2], content_rect[3])
    else:
        cols, rows = screen_mod.grid_dims(width, height, pitch, padding=12)
    hosts = rule_place(a, composition, cols - reserved_right, rows, reflow, engine=engine)
    measured = pitch.get("measured")
    return {"cols": cols, "rows": rows, "pitch": {"cell": pitch.get("cell"), "gap": pitch.get("gap"),
                                                  "measured": measured,
                                                  "label": "MEASURED" if measured else
                                                  "ESTIMATE (the pitch is the 66/16 starting figure, not measured for this composition)"}}, hosts


PROFILE_COMPOSITION = "PlayerReportOverviewComposition-Large"
SHOW_TACTICAL_EFFECTIVENESS = True
def expands(composition):
    """CL3: rule V5+C2 is wired for every composition (the J4 restriction to the profile Overview is gone); kept for callers that ask."""
    return True


def profile_hosts(dump, composition=PROFILE_COMPOSITION, show_tactical_effectiveness=SHOW_TACTICAL_EFFECTIVENESS, max_sizes=None, custom=None, engine="one_rule"):
    """J1: the PlayerReport preview hosts, with the measured content rect and the tile swap state.

    Grid 30x13 from the content rect (15.6, 273.4, 2468.8, 1074.2); expanding layout; the Happiness cell draws
    PlayerReportTacticalEffectivenessTileDescription when the state is on (default, measured for this career in
    H2/I2). How the game picks the description is INFERRED from the two availability paths, not serialized.
    """
    rect = screen_mod.PANEL_CONTENT_RECTS["PlayerReport"]
    grid, placed = grid_for(dump, composition, 0, 0, content_rect=rect, max_sizes=max_sizes, reflow=0, custom=custom, engine=engine)
    hosts = []
    for element, info in placed.items():
        px = screen_mod.cell_px(info["col"], info["row"], info["w"], info["h"])
        shown = ("TacticalEffectiveness" if element == "Happiness" and show_tactical_effectiveness else element)
        hosts.append({"element_id": shown, "cell_element_id": element,
                      "rect": [round(rect[0] + px["left"], 1), round(rect[1] + px["top"], 1),
                               round(px["width"], 1), round(px["height"], 1)],
                      "col": info["col"], "row": info["row"], "mode": info["mode"],
                      "evidence": ("tile description is inferred from m_availabilityPath; not serialized"
                                   if element == "Happiness" else "serialized composition cell")})
    hosts.sort(key=lambda h: (h["row"], h["col"], h["element_id"]))
    return {"cols": grid["cols"], "rows": grid["rows"], "content_rect": list(rect), "hosts": hosts,
            "show_tactical_effectiveness": bool(show_tactical_effectiveness),
            "label": RULE_LABEL + ((" | " + CUSTOM_LABEL) if custom else ""),
            "max_size_label": "candidate, preview only" if max_sizes else None}


def _seed_rng(seed, node_path):
    """Deterministic per (seed, node path): SHA-256 first for cross-version stability."""
    digest = int(hashlib.sha256(("%s|%s" % (seed, node_path)).encode("utf-8")).hexdigest()[:16], 16)
    return random.Random(digest)


_FIRST = ("Alex", "Sam", "Jordan", "Taylor", "Morgan", "Casey", "Riley", "Quinn", "Avery", "Blake")
_LAST = ("Baker", "Carter", "Dawson", "Ellis", "Foster", "Grant", "Hayes", "Irwin", "Jensen", "Klein")
_CLUBS = ("Northgate United", "Riverside Rovers", "Kingsbridge Athletic", "Old Harbour FC",
          "Fairview Town", "Stonebrook Wanderers")
_WORDS = ("Archive", "Overview", "Report", "Schedule", "Training", "Transfers", "Finances", "Squad")


def _placeholder_text(kind, seed, path):
    r = _seed_rng(seed, path)
    if kind == "player":
        return "%s %s" % (r.choice(_FIRST), r.choice(_LAST))
    if kind == "club":
        return r.choice(_CLUBS)
    if kind == "number":
        return str(r.randint(0, 99))
    if kind == "date":
        return "%02d/%02d/%d" % (r.randint(1, 28), r.randint(1, 12), 2026)
    if kind == "heading":
        return "%s %s" % (r.choice(_WORDS), r.choice(_WORDS))
    return "simulated"


def _text_kind(node):
    t = (node.get("type") or "")
    n = (node.get("name") or "")
    if "player" in n.lower() or "player" in t.lower():
        return "player"
    if "club" in n.lower() or "team" in n.lower():
        return "club"
    if "date" in n.lower() or "age" in n.lower():
        return "date"
    if "value" in n.lower() or "wage" in n.lower() or "cost" in n.lower() or "rating" in n.lower():
        return "number"
    if "title" in n.lower() or "header" in n.lower() or "heading" in n.lower():
        return "heading"
    return "text"


def _state_names(requested, sheets, node_type, runtime_classes):
    """The states the preview may apply to one node: the offered ones always, the declared ones only where
    the sheets declare a matching pseudo rule, the code-set ones only when the measured runtime-classes data
    holds them. Returns (states, labels) - labels carrying why each state is offered. `pressed` is offered as
    the `active` pseudo (the sheet's own pseudo-class name)."""
    rc = runtime_classes.get(node_type, [])
    labels, out = [], []
    for s in requested:
        if s == "normal":
            continue
        pseudo = "active" if s == "pressed" else s
        if s in OFFERED_STATES:
            labels.append((pseudo, "offered: a normal interaction state (the preview supplies the gesture)"))
            out.append(pseudo)
        elif s in DECLARED_STATES:
            labels.append((pseudo, "offered only where the sheets declare a matching pseudo rule"))
            out.append(pseudo)
        elif s in RUNTIME_STATES and s in rc:
            labels.append((pseudo, "offered: the state is in the measured runtime-classes data for %s" % node_type))
            out.append(pseudo)
        elif s in RUNTIME_STATES:
            labels.append((pseudo, "NOT offered: a code-set state not in the measured runtime-classes data"))
        else:
            labels.append((pseudo, "not a known state"))
    return out, labels


def state_tree(rd, tree, states, props=None):
    """The UI-state pass: a SEPARATE path over the computed tree. For every node whose requested states
    intersect a rule the sheets declare, the declarations of those rules (the winner per property, resolved
    through the token scope), each citing its sheet/rule/selector. The default cascade, its depth default and
    the calibration are untouched. `:enabled` is carried: a node is enabled unless the requested states say
    otherwise, and `:enabled` pseudo rules match enabled nodes."""
    cascade = rd.cascade()
    if props is None:
        props = set()
        for e in cascade.state_entries:
            for name, _v, _c in e.rule["props"]:
                cname, _inf = values.canonical(name)
                if not cname.startswith("--"):
                    props.add(cname)
    def walk(node, path):
        st = [s for s in states if s != "normal"]
        if "pressed" in st:
            st = [s if s != "pressed" else "active" for s in st]
        node["_states"] = set(st + (["enabled"] if "disabled" not in st else []))
        decl = cascade.state_declarations(path, props=sorted(props))
        if decl:
            node["state_computed"] = decl
        for child in node.get("children", []):
            walk(child, path + [child])
    for root in tree:
        walk(root, [root])
    return tree


def _declared_pseudos(rd):
    """Every pseudo-class the loaded sheets actually declare (the state entries the default cascade skips)."""
    out = set()
    try:
        cascade = rd.cascade()
    except Exception:
        return out
    for entry in getattr(cascade, "state_entries", []) or []:
        for chain, _spec, _text in entry.rule["chains"]:
            for _rel, parts in chain:
                for kind, value in parts:
                    if kind == P_PSEUDO:
                        out.add(value)
    return out


def state_options(rd, tree, runtime_classes):
    """The states the preview may OFFER for these sheets and this screen: normal/hover/pressed always; a declared
    state only where the sheets declare a matching pseudo-class rule; a code-set state only where the measured
    runtime-classes data holds it for a node type the preview actually contains. Unsupported states are ABSENT,
    not shown and refused."""
    declared = _declared_pseudos(rd)
    types = set()
    def collect(node):
        if node.get("type"):
            types.add(node["type"])
        for child in node.get("children") or []:
            collect(child)
    for root in tree:
        collect(root)
    runtime = sorted(s for s in RUNTIME_STATES
                     if any(s in (runtime_classes.get(t) or []) for t in types))
    out = [{"state": "normal", "label": "normal", "evidence": "always offered"},
           {"state": "hover", "label": "hover", "evidence": "offered: a normal interaction state"},
           {"state": "pressed", "label": "pressed / active", "evidence": "offered: a normal interaction state"}]
    for s in DECLARED_STATES:
        if s in declared:
            out.append({"state": s, "label": s,
                        "evidence": "the sheets declare a :%s rule" % s})
    for s in runtime:
        out.append({"state": s, "label": s,
                    "evidence": "in the measured runtime-classes data for the preview's node types"})
    return out


def evidence_flag(node, geometry_measured):
    """Exactly ONE flag per node."""
    if node.get("_runtime_slot"):
        return "runtime-only (not from the bundles)"
    if node.get("_placeholder_box"):
        return "simulated"
    if geometry_measured:
        return "reconstructed"
    return "reconstructed with estimated geometry"


def decorate(node, path, seed, geometry_measured, simulated_visible=True, runtime_classes=None):
    """One node's preview fields: its evidence flag, the state cascade output, the placeholder content. The
    text nodes keep the layout's own sample text (flagged sample); a seeded placeholder is flagged simulated.
    Code-drawn visuals become labelled placeholder boxes with the element's real geometry."""
    kind = _text_kind(node)
    flag = evidence_flag(node, geometry_measured)
    out = {"path": path, "type": node.get("type"), "name": node.get("name") or "", "classes": node.get("classes") or [],
           "evidence": flag,
           "runtime_classes": node.get("runtime_classes") or [],
           "style": node.get("style") or {}, "computed": node.get("computed") or {},
           "state_computed": node.get("state_computed") or {}}
    if node.get("_states"):
        out["states"] = sorted(node["_states"])
    text = node.get("text")
    if text:
        out["text"] = {"value": text, "flag": "sample (the layout's own text)"}
    elif placeholder_kind := node.get("placeholder"):
        if placeholder_kind in ("empty", "set") and simulated_visible:
            out["text"] = {"value": _placeholder_text(kind, seed, path), "flag": "simulated (seeded placeholder, no real data)"}
        elif placeholder_kind in ("empty", "set"):
            out["text"] = {"value": None, "flag": "simulated content hidden by the toggle"}
    is_code_drawn = any(t in (node.get("type") or "") for t in CODE_DRAWN)
    if is_code_drawn:
        out["placeholder_box"] = {"label": "code-drawn visual (%s): a labelled placeholder box, the element's real geometry" % node.get("type"),
                                  "flag": "simulated" if simulated_visible else "simulated content hidden by the toggle"}
    children = []
    for i, child in enumerate(node.get("children") or []):
        children.append(decorate(child, path + "/%d" % i, seed, geometry_measured, simulated_visible, runtime_classes))
    out["children"] = children
    if node.get("include"):
        out["include"] = node["include"]
    if node.get("flag"):
        out["worst_flag"] = node["flag"]
    return out


def _condition(condition):
    """One condition as the game writes it: `{"m_path": {"m_path": "game.X"}, "m_inverseCheck": 0|1}`."""
    if isinstance(condition, dict):
        path = condition.get("m_path")
        if isinstance(path, dict):
            path = path.get("m_path")
        return {"path": str(path) if path else None, "inverse": bool(condition.get("m_inverseCheck"))}
    return {"path": str(condition), "inverse": False}


def _condition_text(condition):
    text = condition.get("path") or "?"
    if condition.get("inverse"):
        text += " (inverse check)"
    return text


def extract_slots(composition_tree):
    """The composition's optional slots, from its serialized `m_optionalSlices` and its conditional
    `m_placementBindings`. Each condition keeps its path and inverse flag; VISIBILITY follows from the game
    states the preview supplies (default scenario: an ordinary career game, not in a match), never from a
    per-slot guess."""
    if not isinstance(composition_tree, dict):
        return []
    out = []
    slices = composition_tree.get("m_optionalSlices") or {}
    for direction in SLICE_DIRECTIONS:
        for i, entry in enumerate(slices.get(direction) or []):
            if not isinstance(entry, dict):
                continue
            eid = entry.get("m_elementID") or ("slice-%s-%d" % (direction, i))
            conds = [_condition(c) for c in entry.get("m_optionalConditions") or []]
            ccfg = [_condition(c) for c in entry.get("m_optionalConfigConditions") or []]
            out.append({"id": "%s:%s" % (direction, eid), "kind": "optional_slice", "element_id": eid,
                        "direction": direction, "location": entry.get("m_location"),
                        "min_size": entry.get("m_minSize"), "max_size": entry.get("m_maxSize"),
                        "conditions": [_condition_text(c) for c in conds],
                        "config_conditions": [_condition_text(c) for c in ccfg],
                        "condition_data": conds + ccfg,
                        "label": "preview data: visibility follows the game states, inverse flags applied"})
    for binding in composition_tree.get("m_placementBindings") or []:
        if not isinstance(binding, dict):
            continue
        conds = [_condition(c) for c in binding.get("m_optionalConditions") or []]
        ccfg = [_condition(c) for c in binding.get("m_optionalConfigConditions") or []]
        if not (conds or ccfg):
            continue                                  # an unconditional binding is not a slot
        eid = binding.get("m_elementID")
        out.append({"id": "binding:%s" % eid, "kind": "placement_binding", "element_id": eid,
                    "direction": "placement_binding", "location": None, "min_size": None, "max_size": None,
                    "conditions": [_condition_text(c) for c in conds],
                    "config_conditions": [_condition_text(c) for c in ccfg],
                    "condition_data": conds + ccfg,
                    "label": "preview data: visibility follows the game states, inverse flags applied"})
    return out


def _conditions_met(conditions, game_states):
    """All conditions true under the given game-state values. A state that was not supplied is NOT assumed;
    an inverse condition is true when its path is false."""
    for condition in conditions or []:
        path = condition.get("path")
        if not path or path not in game_states:
            return False
        value = bool(game_states[path])
        if condition.get("inverse"):
            value = not value
        if not value:
            return False
    return True


def _effective_slots(slots, game_states):
    states = dict(DEFAULT_GAME_STATES)
    states.update(game_states or {})
    out = []
    for slot in slots:
        rec = dict(slot)
        rec["visible"] = _conditions_met(slot["condition_data"], states)
        rec["default"] = _conditions_met(slot["condition_data"], DEFAULT_GAME_STATES)
        out.append(rec)
    return out


def _game_state_options(slots, game_states):
    states = dict(DEFAULT_GAME_STATES)
    states.update(game_states or {})
    paths = []
    for slot in slots:
        for condition in slot["condition_data"]:
            if condition.get("path") and condition["path"] not in paths:
                paths.append(condition["path"])
    return [{"state": path, "value": bool(states.get(path, False)),
             "default": bool(DEFAULT_GAME_STATES.get(path, False)),
             "evidence": "preview data: the state values the slot conditions are evaluated with"} for path in paths]


def _composition_tree(dump, layouts, composition, composition_data=None):
    if isinstance(composition_data, dict):
        return composition_data
    if layouts is None:
        return None
    row = next((c for c in dump.get("compositions") or [] if c.get("name") == composition), None)
    if not row or not row.get("bundle"):
        return None
    return compositionset.composition(layouts, row["bundle"], row["path_id"])


def _competition_context(competition):
    """Preview-only competition context (Stage 5I part 2). OFF by default and explicit per project: a project is
    not tied to a save, and a shared skin must not preview with Bundesliga fonts. This block is LABELLED preview
    data; it never claims the sheet is applied by the ordinary render."""
    on = bool(competition)
    return {"bundesliga": on, "default": False, "label": "preview data",
            "sheet": "Bundesliga", "bundle": "ui-styles_assets_default.bundle", "rules": 22,
            "evidence": "measured on archived set C (get_styles on a Bundesliga save); 22 rules",
            "note": ("Bundesliga competition context is preview data, off by default and explicit per project; "
                     "the sheet is bound to the club's competition, so a plain render does not apply it. "
                     "Changing its definitions is a separate per-project choice, off by default.")}


def place_slice(slot, grid_bottom, grid_rows):
    """One optional slice's host geometry under the Test C+D rule, or (None, reason) when it does not fit.
    m_bottom* regions start at the design bottom and add the slice's serialized offset; other regions keep it."""
    g = slot.get("location") or {}
    if not isinstance(g, dict):
        return None, "no serialized location"
    direction = slot.get("direction") or ""
    col, row = g.get("x", 0), g.get("y", 0)
    if direction.startswith("m_bottom"):
        row = grid_bottom + row
    w, h = g.get("width", 1), g.get("height", 1)
    if row + h > grid_rows:
        return None, ("the %s region starts at design bottom row %d; this slot would occupy rows %d-%d, beyond the "
                      "%d-row grid" % (direction, grid_bottom, row, row + h - 1, grid_rows))
    return {"x": col, "y": row, "w": w, "h": h}, None


def _design_bottom(dump, composition, ops):
    """The composition's design bottom before flex growth: the max serialized cell bottom, with the session's
    move/resize/add geometry applied. The optional bottom regions start here (Test C+D rule), so a flexible cell
    that grows to fill the screen does not push the slots down."""
    bottom = 0
    for c in dump.get("cells") or []:
        if c.get("composition") == composition:
            bottom = max(bottom, c["y"] + c["h"])
    for pl in (ops or {}).get("placements") or []:
        if pl.get("composition") != composition:
            continue
        g = pl.get("geometry") or {}
        if isinstance(g.get("y"), (int, float)) and isinstance(g.get("h"), (int, float)):
            bottom = max(bottom, g["y"] + g["h"])
    return bottom


def _reflow_mode(rd, dump, composition):
    """J2: read m_reflowMode from the serialized composition; None when unavailable (fake test renderer)."""
    try:
        rec = next(c for c in dump.get("compositions") or [] if c.get("name") == composition)
        obj = rd.layouts._bundle_objs(rec["bundle"])[int(rec["path_id"])]
        return obj.read_typetree().get("m_reflowMode")
    except Exception:
        return None


def build_preview(dump, rd, family, width, height, setting, states, seed,
                  session_operations=None, simulated_visible=True, reserved_right=0, runtime_classes=None,
                  layouts=None, sets=None, composition_data=None, game_states=None, competition=None, custom_layouts=None,
                  engine="one_rule"):
    """The full preview: selection (serialized breakpoint keys + the measured points with their settings), the
    grid, the hosts, the tree with one evidence flag per node, the state cascade, the slots, the operations,
    and the measured / estimated lists."""
    sel = select_breakpoint(dump, family, width, setting, sets=sets)
    composition, key = sel["composition"], sel["breakpoint"]
    id_lock = _lock_for(setting, width, height)
    reflow = composition_data.get("m_reflowMode") if isinstance(composition_data, dict) else None
    if reflow is None:
        reflow = _reflow_mode(rd, dump, composition)
    custom = (custom_layouts or {}).get(composition)
    panel = MEASURED_PANEL_RECTS.get((composition, width, height))
    grid, _hosts_map = grid_for(dump, composition, width, height, reserved_right=reserved_right, content_rect=(panel[1] if panel else None), reflow=reflow, custom=custom, engine=engine)
    if panel:
        grid["content_rect"] = list(panel[1])
        grid["measured_panel"] = panel[0]

    def rect_of(px):                                # absolute UI units when the panel's content rect is measured
        return [round(panel[1][0] + px["left"], 1), round(panel[1][1] + px["top"], 1), round(px["width"], 1), round(px["height"], 1)] if panel else None
    a = screen_mod.Assembler(dump)
    custom_info = apply_custom(a, composition, custom) if custom else None
    if custom and custom_info is None:
        custom = None                                          # a file that does not fit the bundle's cells is not used
    grid["layout_label"] = ENGINE_LABEL(engine) + " | " + RULE_LABEL + ((" | " + CUSTOM_LABEL) if custom else "")
    # the session's operations, as the projection of the effective ones (buildable and candidate marked)
    ops = session_operations or {"placements": [], "token_overrides": [], "scoped_rules": [], "image_swaps": []}
    max_sizes_applied = apply_max_sizes(a, composition, ops.get("cell_max_sizes"))
    adds = [{"element_id": pl.get("cell_element_id"), "cell_index": pl.get("cell_index"),
             "geometry": dict(pl.get("geometry") or {})}
            for pl in ops.get("placements") or []
            if pl.get("candidate") == "add-cell" and pl.get("composition") == composition]
    moves = [{"composition": pl.get("composition"), "cell_id": pl.get("cell_element_id"),
              "to": dict(pl.get("geometry") or {})}
             for pl in ops.get("placements") or []
             if pl.get("candidate") != "add-cell" and pl.get("composition") == composition]
    placed = rule_place(a, composition, grid["cols"] - reserved_right, grid["rows"], reflow, moves=moves, adds=adds, engine=engine)
    cell_infos = []
    for c in sorted((c for c in a.cells.get(composition, []) if c["composition"] == composition), key=lambda c: c["cell_index"]):
        info = placed.get(c["element_id"]) or {}
        px = screen_mod.cell_px(info.get("col", c["x"]), info.get("row", c["y"]), info.get("w", c["w"]), info.get("h", c["h"]))
        cell_infos.append({"cell_index": c["cell_index"], "element_id": c["element_id"],
                           "geometry": {"x": info.get("col", c["x"]), "y": info.get("row", c["y"]),
                                        "w": info.get("w", c["w"]), "h": info.get("h", c["h"])},
                           "px": px, "rect": rect_of(px), "flags": c["flags"],
                           "limits": {"min_w": c.get("min_w"), "min_h": c.get("min_h"),
                                      "max_w": c.get("max_w"), "max_h": c.get("max_h")}})
    known = {c["element_id"] for c in dump["cells"] if c["composition"] == composition}
    for ad in adds:
        if not ad["element_id"] or ad["element_id"] in known:
            continue
        info = placed.get(ad["element_id"]) or {}
        g = ad["geometry"]
        px = screen_mod.cell_px(info.get("col", g.get("x")), info.get("row", g.get("y")),
                                info.get("w", g.get("w")), info.get("h", g.get("h")))
        cell_infos.append({"cell_index": ad["cell_index"], "element_id": ad["element_id"],
                           "geometry": {"x": info.get("col", g.get("x")), "y": info.get("row", g.get("y")),
                                        "w": info.get("w", g.get("w")), "h": info.get("h", g.get("h"))},
                           "px": px, "rect": rect_of(px), "flags": ["added cell (candidate)"]})
    # the preview tree per host: the tile layout's render tree, states applied, placeholders, flags
    tree = []
    host_rows = [t for t in dump["tiles"] if t["composition"] == composition]
    lay = {l["id"]: l for l in dump["layouts"]}
    for cell in cell_infos:
        trows = [t for t in host_rows if t["cell_index"] == cell["cell_index"]]
        guid = lay[trows[0]["tile_layout_id"]]["guid"] if trows and trows[0]["tile_layout_id"] in lay else None
        tgt = rd.layouts.target(guid) if guid else None
        if tgt is None:
            tree.append({"host": cell, "evidence": "runtime-only (not from the bundles)",
                         "note": "no tile layout resolved for this cell", "children": []})
            continue
        res = rd.layout(tgt[0], tgt[1], 64, max_nodes=800)
        st_tree = state_tree(rd, res["tree"], states if states else ["normal"])
        measured_geo = composition.endswith("-Large") or "Large" in composition
        decorated = decorate(st_tree[0], cell["element_id"], seed, measured_geo, simulated_visible, runtime_classes)
        tree.append({"host": cell, "px": cell["px"], "tile_layout": res["layout"], "evidence": None,
                     "children": [decorated]})
    # the host-level evidence: MEASURED geometry for the Squad Large (fitted to captures); estimated otherwise
    for h in tree:
        if h.get("evidence") is None:
            h["evidence"] = ("reconstructed" if (composition.endswith("-Large") and composition.startswith("Squad"))
                             else "reconstructed with estimated geometry")
    # the serialized optional slots (preview data; visibility follows the game states). The bottom regions are
    # anchored at the composition's DESIGN BOTTOM (max grid cell bottom), then stacked by their serialized offset:
    # stock (grid bottom 10): Hierarchy row 10, Medical 12, Loans 14; C (12): 12/14/16 -> Loans clipped;
    # D and C+D (16): all start at 16 and are clipped. This is the rule measured on 2026-11-20.
    comp_tree = _composition_tree(dump, layouts, composition, custom or composition_data)
    slots = _effective_slots(extract_slots(comp_tree), game_states)
    grid_bottom = _design_bottom(dump, composition, ops)
    hidden_slots = []
    from .. import layoutspace
    for slot in slots:
        if not slot["visible"] or not isinstance(slot.get("location"), dict):
            continue
        if any(c["element_id"] == slot["element_id"] for c in cell_infos):
            continue
        direction = slot.get("direction") or ""
        geo, why = place_slice(slot, grid_bottom, grid["rows"])
        if geo is None:
            hidden_slots.append({"element_id": slot["element_id"], "direction": direction, "reason": why})
            continue
        col, row, w, h = geo["x"], geo["y"], geo["w"], geo["h"]
        design_right = max((c["x"] + c["w"]) for c in a.cells.get(composition, [])) if a.cells.get(composition) else None
        if panel and direction in layoutspace.FILE_ZONES and design_right is not None:
            rt_slot = layoutspace.slot_to_runtime(direction, slot["location"], (design_right, grid_bottom),
                                                  (grid["cols"], grid["rows"]))
            col, row, w, h = rt_slot["x"], rt_slot["y"], rt_slot["w"], rt_slot["h"]
        px = screen_mod.cell_px(col, row, w, h)
        host = {"cell_index": None, "element_id": slot["element_id"],
                "geometry": {"x": col, "y": row, "w": w, "h": h},
                "px": px, "rect": rect_of(px), "flags": ["optional_slice"]}
        tree.append({"host": host, "px": px, "evidence": "reconstructed", "slot": slot["id"],
                     "note": "the serialized optional slice (m_optionalSlices.%s); its tile layout is not resolved "
                             "in this preview" % direction, "children": []})
    # the session's operations, as the projection of the effective ones (buildable and candidate marked)
    ops = session_operations or {"placements": [], "token_overrides": [], "scoped_rules": [], "image_swaps": []}
    applied, pending = [], []
    for pl in ops.get("placements") or []:
        entry = dict(pl)
        if entry.get("composition") == composition:
            applied.append(entry)
        else:
            pending.append(entry)
    measured = [sel["label"] if sel["evidence"] == "MEASURED" else "the composition switch: " + sel["label"],
                "the grid formula is render.screen's (the game's constants: stride 82, gap 16, padding 12)",
                "the breakpoint keys are the composition set's serialized m_gridBreakpointCompositionData"]
    measured += ["the Information Display availability rows measured on C: %dx%d %s" % (w, h, s)
                 for w, h, s in ID_LOCK["measured_available_on_C"]]
    estimated = []
    if sel["evidence"] != "MEASURED":
        estimated.append(sel["label"])
    for h in tree:
        if h.get("evidence") == "reconstructed with estimated geometry":
            estimated.append("host %s: the geometry is the grid model's estimate (measured on the Squad Large captures only)" % h["host"]["element_id"])
    for gap in sel["gaps"]:
        estimated.append("%s %s: %s" % (gap["code"], gap["kind"], gap["detail"]))
    options = state_options(rd, tree, runtime_classes or {})
    return {"screen": family, "composition": composition, "breakpoint": key, "width": width, "height": height,
            "setting": setting, "information_display": id_lock, "state_options": options,
            "confidence": confidence_for(composition, engine),
            "selection": {"label": sel["label"], "evidence": sel["evidence"],
                          "measured_points": sel["measured_points"],
                          "corroborating_points": sel["corroborating_points"],
                          "source": sel["source"], "cross_check": sel["cross_check"],
                          "gaps": sel["gaps"]},
            "grid": grid, "hosts": tree, "cells": cell_infos,
            "slots": slots, "optional_slots_hidden": hidden_slots,
            "competition": _competition_context(competition),
            "game_states": {"scenario": GAME_STATE_SCENARIO,
                            "defaults": dict(DEFAULT_GAME_STATES),
                            "values": {**DEFAULT_GAME_STATES, **(game_states or {})},
                            "options": _game_state_options(slots, game_states)},
            "operations": {"applied": applied, "pending": pending,
                           "max_sizes": [dict(m, preview=("candidate, preview only" if m.get("cell_element_id") in max_sizes_applied
                                                          and m.get("composition") == composition else "not previewed"))
                                         for m in ops.get("cell_max_sizes") or []]},
            "measured": measured, "estimated": estimated,
            "notice": ("Approximation, not the game's renderer: the preview is deterministic for the same seed; "
                       "every node carries exactly one evidence flag; the state cascade applies the sheets' own "
                       "pseudo rules; placeholders are seeded and never real data.")}


def compare_preview(dump, rd, family, a, b, setting, seed, session_operations=None, simulated_visible=True,
                    layouts=None, sets=None, composition_data=None, game_states=None, competition=None, engine="one_rule"):
    """Side-by-side: two resolutions, each with its selection, plus the cell differences between them
    (cells matched by element id, via skin_editor.celldiff's matching rule)."""
    kw = dict(layouts=layouts, sets=sets, composition_data=composition_data, game_states=game_states,
              competition=competition, engine=engine)
    pa = build_preview(dump, rd, family, a[0], a[1], setting, [], seed, session_operations, simulated_visible, **kw)
    pb = build_preview(dump, rd, family, b[0], b[1], setting, [], seed, session_operations, simulated_visible, **kw)
    ca = {c["element_id"]: c for c in pa["cells"]}
    cb = {c["element_id"]: c for c in pb["cells"]}
    appear, disappear, changed = [], [], []
    for eid in sorted(set(cb) - set(ca)):                      # present in B, absent in A -> appears
        appear.append({"element_id": eid, "geometry": cb[eid]["geometry"]})
    for eid in sorted(set(ca) - set(cb)):                      # present in A, absent in B -> disappears
        disappear.append({"element_id": eid, "geometry": ca[eid]["geometry"]})
    for eid in sorted(set(ca) & set(cb)):
        if ca[eid]["geometry"] != cb[eid]["geometry"]:
            changed.append({"element_id": eid, "from": ca[eid]["geometry"], "to": cb[eid]["geometry"]})
    return {"a": {"width": a[0], "height": a[1], "composition": pa["composition"],
                  "selection": pa["selection"]["label"], "evidence": pa["selection"]["evidence"],
                  "competition": pa["competition"], "confidence": confidence_for(pa["composition"], engine)},
            "b": {"width": b[0], "height": b[1], "composition": pb["composition"],
                  "selection": pb["selection"]["label"], "evidence": pb["selection"]["evidence"],
                  "competition": pb["competition"], "confidence": confidence_for(pb["composition"], engine)},
            "cells": {"appear": appear, "disappear": disappear, "changed": changed}}
