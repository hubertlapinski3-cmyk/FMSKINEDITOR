"""Crimson preset. Rule body vendored verbatim from tools/make_crimson_json.py (FM27-CRIMSON-EDITION rev 5).
Changes: wrapped in make(MAN), the token inventory comes from the app's style index instead of
reference/uss_2026-11-02/manifest.json, header_sweep.json rules are passed in (none by default)."""
import re

from .. import colour
from .. import project as project_mod


def make(MAN, sweep_rules=()):
    """MAN: {token: [{"value": text}, ...]} for every :root token. Returns (spec, why, vanilla values)."""
    # ---------------------------------------------------------------- palette
    CR = {}          # --cr-* name -> value (single source of every colour)
    def cr(name, val):
        CR["--cr-" + name] = val
        return val

    NEUTRAL = dict(zip(["n-0", "n-1", "n-2", "n-3", "n-4", "n-5", "n-6", "n-7", "n-8"],
                       ["#101010", "#171717", "#202020", "#292929", "#353535", "#444444", "#555555", "#626262", "#777777"]))
    for k, v in NEUTRAL.items():
        cr(k, v)
    cr("t-muted", "#999999"); cr("t-2", "#BDBDBD"); cr("t-1", "#EDEDED"); cr("white", "#FFFFFF")
    CRIMSON = dict(zip([50, 100, 200, 300, 400, 500, 600, 700, 800, 900],
                       ["#FFE0E8", "#FFB3C5", "#FF7D9E", "#F34772", "#DA0037", "#B90030", "#970027", "#75001E", "#530016", "#32000D"]))
    for k, v in CRIMSON.items():
        cr(f"c-{k}", v)
    ALPHA = {"a-subtle": "#FFFFFF0D", "a-hover": "#FFFFFF14", "a-odd": "#FFFFFF08", "a-sel": "#DA003726",
             "a-sel-strong": "#DA003740", "a-overlay": "#00000040", "a-backdrop": "#00000099",
             "c-400-08": "#DA003714", "c-400-16": "#DA003729", "c-400-40": "#DA003766", "c-400-70": "#DA0037B3",
             "c-400-0": "#DA003700", "transparent": "#00000000"}
    for k, v in ALPHA.items():
        cr(k, v)

    FAM = {  # guide 2.4: Soft, Light, Base, Deep, Strong
        "red": ["#FCE4E7", "#F5A6B0", "#E64B5D", "#B92D40", "#761B2A"],
        "orange": ["#FFF0DF", "#FFC58A", "#F28C28", "#C76A16", "#87440D"],
        "yellow": ["#FFF8D6", "#FFE68A", "#EFC642", "#C69D21", "#846A16"],
        "lime": ["#F1F8D9", "#D0E88A", "#A4C943", "#789B2C", "#506B1B"],
        "green": ["#DDF5E9", "#91DAB1", "#35B879", "#238657", "#145637"],
        "teal": ["#D9F4F0", "#8AD9CD", "#35B6A5", "#23877D", "#15564F"],
        "cyan": ["#DDF6FA", "#91DCEB", "#35B9D4", "#2589A4", "#17596D"],
        "blue": ["#E0ECFF", "#9ABEFF", "#4789ED", "#3166B9", "#204477"],
        "indigo": ["#E8E8FF", "#ADACF5", "#7475DF", "#5253AC", "#363773"],
        "purple": ["#F0E4FC", "#C7A0F1", "#9B62DC", "#7042A8", "#492B70"],
        "pink": ["#FCE4F1", "#F3A4CE", "#DE65AA", "#AE4482", "#702C55"],
        "grey": ["#EEEEEE", "#BDBDBD", "#888888", "#555555", "#303030"],
    }
    STEP = ["soft", "light", "base", "deep", "strong"]
    for f, vals in FAM.items():
        for s, v in zip(STEP, vals):
            cr(f"{f}-{s}", v)
    def fam(f, s):
        return FAM[f][STEP.index(s)]

    SCALE = ["#E64B5D", "#EC6B44", "#F28C28", "#F1A935", "#EFC642", "#CAC843", "#A4C943", "#8EC957", "#78C96B", "#35B879"]
    for i, v in enumerate(SCALE, 1):
        cr(f"scale-{i}", v)

    def mix(a, b, t):
        a = [int(a[i:i + 2], 16) for i in (1, 3, 5)]
        b = [int(b[i:i + 2], 16) for i in (1, 3, 5)]
        return "#%02X%02X%02X" % tuple(round(x * t + y * (1 - t)) for x, y in zip(a, b))
    SCALE_SOFT = [mix(c, "#171717", 0.30) for c in SCALE]   # dark tints for -soft-ondark chips
    for i, v in enumerate(SCALE_SOFT, 1):
        cr(f"scale-soft-{i}", v)
    RATING = {"outstanding": "#35B879", "very-good": "#78C96B", "good": "#A4C943", "average": "#EFC642",
              "below": "#F28C28", "poor": "#E64B5D"}
    for k, v in RATING.items():
        cr(f"rating-{k}", v)

    def a(hex6, alpha):  # hex6 + alpha (0..1) -> #RRGGBBAA
        return hex6[:7] + "%02X" % round(alpha * 255)

    # ---------------------------------------------------------------- tokens
    T, WHY = {}, {}
    def tok(name, value, why):
        if name not in MAN:
            WHY.setdefault("_not_in_vanilla", []).append(name)
            return
        T[name] = value
        WHY[name] = why

    def vanilla(name):
        return sorted({d["value"] for d in MAN.get(name, [])})

    def resolve(name, depth=0):
        """vanilla literal behind a token (first definition, follows var())."""
        vs = vanilla(name)
        if not vs or depth > 10:
            return None
        v = vs[0]
        m = re.match(r"var\((--[\w-]+)\)$", v)
        return resolve(m.group(1), depth + 1) if m else v

    # 3.2 table -------------------------------------------------------------
    for n in ["--colours-ui-deep", "--colours-brand-foundation-midnight", "--colours-brand-foundation-midnight-base",
              "--colours-base-neutral-black"]:
        tok(n, NEUTRAL["n-0"], "3.2 deepest well")
    for n in ["--global-background", "--colours-ui-base", "--colours-brand-foundation-midnight-100",
              "--colours-brand-foundation-midnight-soft"]:
        tok(n, NEUTRAL["n-1"], "3.2 page")
    for n in ["--colours-ui-soft", "--layout-modules-block-surface", "--layout-ui-tiles-light-background",
              "--layout-surfaces-cards-surface", "--colours-brand-foundation-twilight", "--colours-brand-foundation-twilight-base"]:
        tok(n, NEUTRAL["n-2"], "3.2 panels/cards/tables")
    for n in ["--colours-ui-strong", "--layout-ui-tiles-interaction-surface-light-hover",
              "--colours-brand-foundation-twilight-soft"]:
        tok(n, NEUTRAL["n-3"], "3.2 headers/hover/inputs")
    for n in ["--layout-surfaces-modal-surface", "--layout-surfaces-modules-modal"]:
        tok(n, NEUTRAL["n-4"], "3.2 modals")
    for n in ["--colours-ui-text-strong", "--global-text-primary", "--buttons-text-default", "--layout-tiles-heading",
              "--layout-tiles-heading-permanent", "--modal-text-primary", "--internal-_text-theme"]:
        tok(n, "#EDEDED", "3.2 primary text")
    for n in ["--colours-ui-text-soft", "--global-text-secondary"]:
        tok(n, "#BDBDBD", "3.2 secondary text")
    for n in ["--brand-theme-primary", "--brand-theme-primary-accent", "--brand-theme-ui-base",
              "--buttons-primary-surface-default"]:
        tok(n, CRIMSON[400], "3.2 crimson 400")
    for n in ["--brand-theme-primary-soft", "--brand-theme-primary-accent-soft", "--brand-theme-ui-soft",
              "--buttons-primary-surface-hover"]:
        tok(n, CRIMSON[500], "3.2 crimson 500 (hover)")
    for n in ["--brand-theme-accent", "--brand-theme-light", "--colours-brand-foundation-horizon-base",
              "--colours-brand-highlight-pink", "--colours-brand-highlight-pink-base"]:
        tok(n, CRIMSON[200], "3.2 crimson text (200, >=5.1:1)")
    for n, v in [("--brand-theme-primary-08", "#DA003714"), ("--brand-theme-primary-16", "#DA003729"),
                 ("--brand-theme-primary-70", "#DA0037B3"), ("--brand-theme-primary-0", "#DA003700"),
                 ("--brand-theme-accent-40", "#DA003766"), ("--colours-brand-highlight-pink-40", "#DA003766")]:
        tok(n, v, "3.2 crimson alpha")
    # orange / red highlight families -> crimson (no orange accent)
    for n in MAN:
        if re.match(r"--colours-brand-highlight-(orange|red)(-|$)", n):
            v = resolve(n) or ""
            al = int(v[7:9], 16) / 255 if len(v) == 9 else 1.0
            step = 500 if n.endswith(("-deep",)) else 200 if n.endswith("-soft") else 400
            tok(n, a(CRIMSON[step], al) if al < 1 else CRIMSON[step], "3.2 orange/red highlight -> crimson family")
    for n in ["--colours-brand-fm-orange", "--colours-brand-fm-yellow"]:
        tok(n, CRIMSON[400], "no orange accent (inventory decision 4)")
    for n in ["--colours-brand-accent", "--colours-brand-hyper-turquoise", "--data-tables-key-accent",
              "--colours-brand-fm-ultra-violet", "--colours-brand-foundation-cloud"]:
        tok(n, "#EDEDED", "3.2 no blue/purple accent -> off-white")
    for n in ["--colours-brand-fm25-lilac", "--colours-brand-tints-horizon-120"]:
        tok(n, "#BDBDBD", "3.2 no purple -> secondary text")
    for n in ["--colours-brand-foundation-twilight-strong"]:
        tok(n, NEUTRAL["n-3"], "twilight ramp -> neutrals (3.2 twilight-soft)")
    for n in ["--colours-brand-fm-purple", "--colours-brand-fm25-twiight"]:
        tok(n, CRIMSON[400], "brand purple -> crimson")
    tok("--colours-brand-fm-purple-dark", CRIMSON[700], "brand purple dark -> crimson 700")
    tok("--colours-brand-fm-purple-light", CRIMSON[300], "brand purple light -> crimson 300")
    tok("--colours-brand-fm25twlight-light", CRIMSON[300], "brand purple light -> crimson 300")
    # continue (3.2): flat crimson
    for n in MAN:
        if n.startswith(("--continue-button-default-", "--continue-button-standard-")):
            hover = "hover" in n
            if n.endswith("-border") or "border" in n:
                tok(n, CRIMSON[400], "3.2 continue border")
            elif "secondary" in n:
                tok(n, CRIMSON[200], "3.2 continue secondary")
            else:
                tok(n, CRIMSON[500] if hover else CRIMSON[400], "3.2 continue flat (grad-l = grad-r)")
    # must-respond / response-required keep FM's alert literals (pin them so the
    # orange/red -> crimson remap cannot drag them along); border crimson 200 (3.3)
    for n in MAN:
        if n.startswith(("--continue-button-must-respond-", "--continue-button-response-required-")):
            v = resolve(n)
            if n == "--continue-button-must-respond-border":
                tok(n, CRIMSON[200], "3.3 must-respond border crimson 200")
            elif v and v.startswith("#"):
                tok(n, v, "pinned FM alert literal (3.2: must-respond keeps FM's alert)")
    # tables / borders / focus
    for n, v, w in [("--data-tables-background-selected", "#DA003726", "3.2"), ("--data-tables-border-selected", CRIMSON[400], "3.2"),
                    ("--data-tables-background-hover", "#FFFFFF14", "3.2"), ("--data-tables-background-odd", "#FFFFFF08", "3.2"),
                    ("--data-tables-border", "#FFFFFF14", "3.2"), ("--layout-modules-block-border-colour", "#FFFFFF14", "3.2"),
                    ("--global-border-color", "#FFFFFF14", "3.2"), ("--tiles-border-default", "#FFFFFF14", "3.2"),
                    ("--accessibility-focus", CRIMSON[400], "3.2"), ("--communication-accessibility-focus", CRIMSON[400], "3.2"),
                    ("--buttons-toggle-active-primary-border", CRIMSON[400], "active toggles crimson (3.3 tactics)")]:
        tok(n, v, w)
    for n, v in [("--global-radius-small", "2px"), ("--global-radius-regular", "3px"), ("--global-radius-large", "4px"),
                 ("--layout-modules-block-radius", "4px")]:
        tok(n, v, "3.2 radii")

    # 2.4 families by role ----------------------------------------------------
    ROLE = {"soft": "light", "20": "soft", "40": "light", "strong": "base", "base": "deep", "50": "deep",
            "60": "strong", "deep": "strong", "80": "strong"}
    for n in MAN:
        m = re.match(r"--colours-base-(red|orange|yellow|lime|green|teal|cyan|blue|purple|pink|grey)-(.+)$", n)
        if not m:
            continue
        f, s = m.groups()
        am = re.match(r"base-(\d+)$", s)
        if am:
            tok(n, a(fam(f, "base"), int(am.group(1)) / 100), "2.4 -base-NN -> Base at same alpha")
        elif s in ROLE:
            tok(n, fam(f, ROLE[s]), f"2.4 vanilla -{s} -> {ROLE[s].title()}")
        else:
            WHY.setdefault("_family_unmapped", []).append(n)

    # 2.5 semantics -----------------------------------------------------------
    for n, v in [("--interaction-global-color-feedback-positive", "#35B879"), ("--interaction-global-color-feedback-warning", "#EFC642"),
                 ("--interaction-global-color-feedback-negative", "#E64B5D"), ("--communication-feedback-positive", "#35B879"),
                 ("--communication-feedback-negative", "#E64B5D"), ("--communication-feedback-information", "#9ABEFF"),
                 ("--communication-feedback-alert", "#F28C28")]:
        tok(n, v, "2.5 semantics")
    tok("--status-player-status-manager-club", "#EDEDED", "own club = normal text (round 3: no pink names; FM code paints the own-club table row itself)")
    tok("--communication-manager-club", CRIMSON[200], "own club = crimson text")
    tok("--status-player-status-affiated-club", fam("orange", "light"), "affiliated club = Orange Light (round 3: was crimson 100 = pink names)")
    tok("--communication-manager-affiated-club", CRIMSON[100], "affiliated club")
    tok("--status-neutral-thematic-base", CRIMSON[400], "thematic = brand")
    tok("--status-neutral-thematic-soft", CRIMSON[800], "thematic soft (dark fill)")
    tok("--status-neutral-thematic-strong", CRIMSON[100], "thematic strong (text)")
    for n, f in [("--status-loaned-in-border", "blue"), ("--status-loaned-out-border", "red"), ("--status-shortlist-border", "orange"),
                 ("--status-trial-in-border", "yellow"), ("--status-trial-out-border", "indigo")]:
        tok(n, a(fam(f, "light"), 0x52 / 255), "status border: family Light at vanilla alpha")
    # coaching adjective ratings: 10-step scale
    ADJ = {"unsuited": 3, "good": 6, "very-good": 7, "outstanding": 9, "elite": 10}
    for pre in ("--status-coaching-adjective-ratings-",):
        for k, i in ADJ.items():
            tok(f"{pre}{k}-text", SCALE[i - 1], f"2.6 linear scale step {i}")
            tok(f"{pre}{k}-surface", a(SCALE[i - 1], 0x29 / 255), f"2.6 scale step {i} at 16%")

    # 2.6 ratings / scales / charts / positions / heat ------------------------
    for n, v in [("--data-average-rating-surface-0-6", RATING["poor"]), ("--data-average-rating-surface-6-7", "#444444"),
                 ("--data-average-rating-surface-7-8", RATING["good"]), ("--data-average-rating-surface-8-9", RATING["very-good"]),
                 ("--data-average-rating-surface-9-10", RATING["outstanding"]), ("--data-average-rating-surface-not-available", "#444444"),
                 ("--colours-data-ratings-average-rating-bad", RATING["poor"]), ("--colours-data-ratings-average-rating-good", RATING["good"]),
                 ("--colours-data-ratings-average-rating-excellent", RATING["outstanding"])]:
        tok(n, v, "2.6 rating fills (neutral #444444)")
    for n in MAN:
        m = re.match(r"--colours-(?:data-)?linear-scale-(strong-(?:ondark-)?)?(\d+)(?:-alpha-(\d+))?$", n)
        if m:
            pre, i, al = m.group(1), int(m.group(2)), m.group(3)
            if pre is None:                       # 20-step scale -> even picks
                i = round((i - 1) * 9 / 19) + 1
            c = SCALE[min(i, 10) - 1]
            tok(n, a(c, int(al) / 100) if al else c, "2.6 10-step linear scale" + (" (20->10 even picks)" if pre is None else ""))
            continue
        m = re.match(r"--colours-(?:data-)?linear-scale-soft-(?:ondark-)?(\d+)$", n)
        if m:
            tok(n, SCALE_SOFT[int(m.group(1)) - 1], "2.6 scale step as dark tint (30% on #171717)")
    # positions (2.6: GK grey, DEF teal, DM green, MID blue, AM purple, ST pink; Strong fills)
    POS = {"goalkeeper": "grey", "defender": "teal", "defensive-midfield": "green", "midfield": "blue",
           "attacking-midfield": "purple", "striker": "pink"}
    for p, f in POS.items():
        for pre in ("--data-player-position-", "--colours-tactics-"):
            tok(f"{pre}{p}-background", fam(f, "strong"), "2.6 position Strong fill")
            if pre.startswith("--data"):
                tok(f"{pre}{p}-foreground", fam(f, "light"), "2.6 position label Light on Strong")
            else:
                tok(f"{pre}{p}-foreground", fam(f, "strong"), "2.6 tactics position (vanilla foreground is the darker shade)")
    tok("--data-player-position-striker-background-2", fam("pink", "strong"), "2.6 position")
    # tactics teal ramp -> neutrals (3.3 tactics: teal to neutrals, pitch green kept)
    for s, v in {"00": NEUTRAL["n-6"], "20": NEUTRAL["n-5"], "40": NEUTRAL["n-3"], "50": NEUTRAL["n-2"],
                 "60": NEUTRAL["n-1"], "80": NEUTRAL["n-0"]}.items():
        tok(f"--colours-tactics-base-{s}", v, "3.3 tactics teal -> neutrals")
    tok("--colours-tactics-tweak-pending", CRIMSON[200], "pending tweak = attention (no blue accent)")
    tok("--colours-tactics-tweak-pending-background", "#DA003729", "pending tweak background")
    tok("--colours-tactics-phase-highlight-background", "#FFFFFF14", "phase highlight -> neutral hover tint")
    # training calendar (3.3: families, start = end)
    for cat, f in {"extra-curricular": "orange", "footballing-development": "pink", "match-preparation": "blue",
                   "physical-and-recovery": "red", "tactical-understanding": "teal"}.items():
        b = f"--colours-calendar-training-{cat}"
        tok(b + "-start", a(fam(f, "base"), 0x52 / 255), "3.3 training family Base, start = end")
        tok(b + "-end", a(fam(f, "base"), 0x52 / 255), "3.3 training family Base, start = end")
        tok(b + "-border", a(fam(f, "light"), 0x59 / 255), "3.3 training family Light border")
    tok("--colours-calendar-training-rest-border", a(fam("grey", "light"), 0x59 / 255), "3.3 training rest")
    tok("--colours-calendar-training-travel-border", a(fam("grey", "deep"), 0x59 / 255), "3.3 training travel")
    # charts (2.6)
    for n, v in [("--colours-chart-league-line", a(CRIMSON[400], .8)), ("--colours-chart-league-line-1", a(CRIMSON[400], .8)),
                 ("--colours-chart-league-line-2", a(fam("blue", "base"), .8)), ("--colours-chart-fifa-ranking-line", CRIMSON[400]),
                 ("--colours-chart-wage-expenditure-line", a(CRIMSON[400], .8)), ("--colours-chart-wage-expenditure-line-1", a(CRIMSON[400], .8)),
                 ("--colours-chart-wage-expenditure-line-2", a(fam("blue", "base"), .8)),
                 ("--colours-chart-financial-line", a(fam("green", "base"), .8)),
                 ("--colours-chart-squad-injury-line-1", a(fam("blue", "base"), .8)), ("--colours-chart-squad-injury-fill-1", a(fam("blue", "base"), .4)),
                 ("--colours-chart-squad-injury-line-2", a(fam("red", "base"), .8)), ("--colours-chart-squad-injury-fill-2", a(fam("red", "base"), .2)),
                 ("--colours-chart-ability-line", a("#EDEDED", .8)), ("--colours-chart-ability-fill", a(fam("green", "base"), .4)),
                 ("--colours-chart-ability-recent-line", a(CRIMSON[400], .8)), ("--colours-chart-ability-recent-fill", a(CRIMSON[400], .1)),
                 ("--colours-chart-attribute-fill", a(fam("green", "base"), .4))]:
        tok(n, v, "2.6 charts: own crimson, opponent blue, positive green")
    # radial/selection literals in tokens handled by literal_map

    # ---------------------------------------------------------------- literal_map
    LIT = {
        # navy-tinted surfaces -> neutral ladder (3.2)
        "#0D0E11": "#101010", "#16181D": "#171717", "#1E2129": "#202020", "#2E3138": "#292929", "#232735": "#171717",
        "#0A0F1E": "#101010", "#252931": "#202020", "#080B17": "#101010", "#222735": "#202020", "#0F1025": "#101010",
        "#15122C": "#171717", "#1C202F": "#202020", "#272C42": "#292929", "#3A3D4D": "#353535", "#1A237E": "#292929",
        "#3C3C5A": "#444444", "#3A3E4D": "#626262", "#67697A": "#626262", "#5F6A6F": "#626262", "#646478": "#444444",
        "#93949B": "#999999", "#C6C7D1": "#BDBDBD",
        # lavender off-whites -> off-white
        "#E6E6FA": "#EDEDED", "#E0DFF7": "#EDEDED", "#D2C8F5": "#EDEDED", "#D7C0FC": "#EDEDED",
        # brand purple / pink UI -> crimson scale (3.2)
        "#A300DB": CRIMSON[400], "#6E0FD7": CRIMSON[400], "#8B3FDF": CRIMSON[200], "#DA71FE": CRIMSON[200],
        "#EB85FF": CRIMSON[200], "#AF78FF": CRIMSON[200], "#7871F7": "#EDEDED", "#C20FFF": CRIMSON[500],
        "#C7005A": CRIMSON[400], "#FA0070": CRIMSON[500], "#D493F5": CRIMSON[400], "#8959C5": CRIMSON[400],
        "#A40FC7": CRIMSON[600], "#570DA8": CRIMSON[700], "#783A8E": CRIMSON[600], "#5F1084": CRIMSON[700],
        "#CF86F6": CRIMSON[400], "#8600C5": CRIMSON[500], "#FF3FE8": CRIMSON[400], "#882DF0": CRIMSON[300],
        "#641EAA": CRIMSON[300], "#321450": CRIMSON[800], "#190A28": CRIMSON[900], "#C299FF": CRIMSON[100],
        "#F2CCFF": CRIMSON[50],
        # Unity default-theme selection/focus blues (interface accent, 2.8) -> crimson
        "#006AA6": CRIMSON[400], "#3A72B0": CRIMSON[600], "#3D80DF": CRIMSON[500], "#3356DA": CRIMSON[400],
        "#356AA3": CRIMSON[600], "#557BD5": CRIMSON[400], "#274A9D": CRIMSON[700],
        # tactics teal (3.2)
        "#036150": "#202020", "#32755D": "#FFFFFF",  # RGB only; alpha of the use is kept (border uses are opaque -> see note)
        # data purple literals in rule bodies -> Purple family by role
        "#B23FE8": fam("purple", "base"), "#B27CFF": fam("purple", "base"), "#D99FF4": fam("purple", "light"),
        "#9912BE": fam("purple", "deep"),
        # build 1 residual check: remaining UI (non-data) blues / purples
        "#004AAA": CRIMSON[400],   # .tactical-tweaks-badge (pending tweaks = attention)
        "#08397D": fam("blue", "strong"),  # speak-to target TAG gradient: categorical tag -> Blue (review 2026-11-03)
        "#060912": "#101010",      # --colours-speak-to-background-dark
        "#232835": "#171717",      # --colours-speak-to-background-default
        "#9625F2": CRIMSON[400],   # --data-tables-ip-preferred-accent
        "#E664FF": CRIMSON[200],   # --colours-feature-draft-shortlist(-alpha-*)
    }
    # 3.2 says #32755D -> #FFFFFF14; literal_map keeps the use's alpha (opaque here),
    # so map it to the composite of #FFFFFF14 over the #202020 panel instead.
    LIT["#32755D"] = "#323232"

    # safety: no literal_map key may equal a palette value (it would recolour our own tokens)
    pal = {v[:7].upper() for v in CR.values()} | {v[:7].upper() for v in T.values() if str(v).startswith("#")}
    clash = sorted(k for k in LIT if k.upper() in pal)
    assert not clash, f"literal_map keys collide with palette values: {clash}"

    # ---------------------------------------------------------------- append rules
    R = []
    def rule(sel, props, on=None, note=None):
        r = {"selector": sel, "props": props}
        if on:
            r["on"] = on          # contrast gate: surfaces this text sits on
        if note:
            r["note"] = note
        R.append(r)

    rule(":root", dict(sorted(CR.items()), **{"--crimson-skin": "1"}), note="--cr-* palette (single source) + plugin handshake 6.3")
    # navigation (3.3)
    rule(".navigation-header-gradient", {"background-color": "var(--cr-n-1)", "border-bottom-width": "1px", "border-bottom-color": "var(--cr-a-hover)"})
    rule(".navigation-header-gradient SIGradient, .navigation-header-gradient SIImage", {"opacity": "0"})
    rule("#EntityGradient", {"background-color": "var(--cr-n-5)"})
    rule("#EntityGradient SIGradient, #EntityGradient SIImage, #EntityGradient #ClubGradientTdd", {"opacity": "0"})
    rule("#MainNav", {"background-color": "var(--cr-n-1)"})
    rule(".navigation-type-competition", {"background-color": "var(--cr-n-5)"})
    rule("#MainNavigationBar", {"color": "var(--cr-t-1)"}, on=["--cr-n-1"])
    rule(".navigation-header-gradient .portal-text", {"color": "var(--cr-t-muted)"}, on=["--cr-n-1"], note="inactive top tabs")
    rule("#EntityGradient .portal-text", {"color": "var(--cr-t-2)"}, on=["--cr-n-5"], note="inactive secondary tabs")
    rule(".navigation-tab-portal-default-active-true .portal-text", {"color": "var(--cr-t-1)"}, on=["--cr-n-1", "--cr-n-5"])
    rule(".navigation-tab-portal-default-active-true .navigation-chip", {"background-color": "var(--cr-c-400)", "width": "100%", "height": "2px"})
    rule(".navigation-tab-portal-default-active-true #NavTabDropdownIndicator, .navigation-tab-portal-default-active-true .portal-image",
         {"-unity-background-image-tint-color": "var(--cr-t-1)"})
    rule(".navigation-secondary-tab-portal-default-active-true .sigradient", {"--start-colour": "var(--cr-c-400)", "--end-colour": "var(--cr-c-400)"})
    # surfaces (3.3)
    rule("#GameWorldBackground", {"background-color": "var(--cr-n-1)"}, note="Calm Dark runtime name; not in UXML dumps")
    rule("#background_image, #GameWorldBackground #background_image", {"opacity": "0"})
    rule("#Card-frame, #ReportBody #Card-frame, #MenuBody #Card-frame, #CardBody #Card-frame",
         {"-unity-background-image-tint-color": "var(--cr-transparent)", "background-color": "var(--cr-n-1)"})
    rule("SIGradient#PlayerReportHeaderGradient, SIGradient#PlayerGradient, SIGradient#Club",
         {"--start-colour": "var(--cr-n-2)", "--end-colour": "var(--cr-n-2)"}, note="colour, not opacity: header holds photo + name")
    rule("#SenderArea", {"background-color": "var(--cr-n-3)"}, note="PortalMessagesContentBlock band")
    rule("#EntityTextureClub, #EntityTextureNation, #GradientsAdditional SIGradient, #DynamicBackgroundImage_Club, #IsEmployedDivider VisualElement",
         {"opacity": "0"})
    rule("#IsEmployedDivider", {"border-bottom-width": "2px", "border-bottom-color": "var(--cr-c-400)"})
    rule("#ClubSIGradient_LeftToRight", {"--start-colour": "var(--cr-n-3)", "--end-colour": "var(--cr-n-3)"})
    # buttons (3.3)
    rule(".buttons-button-primary-default", {"border-radius": "3px", "color": "var(--cr-white)"}, on=["--cr-c-400", "--cr-c-500"])
    rule(".buttons-button-primary-default .sigradient", {"--start-colour": "var(--cr-c-400)", "--end-colour": "var(--cr-c-400)"})
    rule(".buttons-button-primary-default:hover .sigradient", {"--start-colour": "var(--cr-c-500)", "--end-colour": "var(--cr-c-500)"})
    rule(".buttons-button-secondary-default", {"background-color": "var(--cr-n-5)", "color": "var(--cr-t-1)",
                                               "border-color": "var(--cr-n-6)", "border-radius": "3px"})
    rule(".buttons-button-secondary-default:hover", {"background-color": "var(--cr-n-6)"})
    rule(".continue-button", {"background-color": "var(--cr-c-400)"})
    rule(".continue-button:hover", {"background-color": "var(--cr-c-500)"})
    rule(".continue-button SIGradient, .continue-button .continue-button--background-image, .continue-button .continue-button---pulse-overlay",
         {"opacity": "0"})
    rule(".continue-button.continue-button---must-respond", {"background-color": "var(--continue-button-must-respond-background)",
                                                             "border-color": "var(--cr-c-200)"}, note="keeps FM's alert colour")
    # tables (3.3)
    rule(".streamed-table .streamed-table__row, .streamed-table .streamed-table__row .streamed-table__cell", {"min-height": "0"})
    rule(".streamed-table .virtualised-list__item--selected", {"background-color": "var(--cr-a-sel)", "border-left-width": "2px",
                                                               "border-left-color": "var(--cr-c-400)"},
         note="3.6: doubled class -> real parent scope (.streamed-table)")
    rule(".streamed-table .virtualised-list__item--odd", {"background-color": "var(--cr-a-odd)"})
    rule(".streamed-table .virtualised-list__item--odd:hover, .streamed-table .streamed-table__row:hover", {"background-color": "var(--cr-a-hover)"})
    rule(".data_display-average_rating-default-default-rating-6, .data_display-average_rating-default-default-rating-null",
         {"background-color": "var(--cr-n-5)", "color": "var(--cr-t-1)"}, note="neutral chips #444444 + #EDEDED")
    rule(".data_display-average_rating-default-default-rating-less-than-6, .data_display-average_rating-default-default-rating-7, "
         ".data_display-average_rating-default-default-rating-8, .data_display-average_rating-default-default-rating-9",
         {"color": "var(--cr-n-1)"}, on=["--cr-rating-poor", "--cr-rating-good", "--cr-rating-very-good", "--cr-rating-outstanding"],
         note="coloured rating chips get a #171717 label")
    # screens (3.3)
    rule(".portal-messages-item-message-text-read", {"color": "var(--cr-t-2)"}, on=["--cr-n-2", "--cr-n-3"])
    rule(".tactics-collapsable-pitch-container, .tactics-collapsable-pitch-container-with-darker-header, .tactics-subs-block",
         {"background-color": "var(--cr-n-2)", "border-color": "var(--cr-a-hover)"})
    rule("SIGradient.frame-tactics-nav-menu", {"visibility": "hidden"},
         note="round 11: the toolbar gradient is code-bound (useCustomStyles=false; colour rules cannot win), so hide it (AGENTS 7)...")
    rule("SIGradient.frame-tactics-nav-menu > *", {"visibility": "visible"},
         note="round 11: ...but keep its real children visible (the two action rows render on the flat #101010 env)")
    rule(".tactics-subs-block-cell-selected", {"background-color": "var(--cr-a-sel)", "border-color": "var(--cr-c-400)"})
    # round 7 (2026-11-04): vanilla .surfaces-card-tile-border draws its frame in --colours-alpha-light-20
    # (#FFFFFF33), invisible on vanilla's light panels but a bright line on our dark surfaces (reported on the
    # squad-table photo thumbnails). 8% white matches every other card border (guide 3.3); the hover/active and
    # instruction-tile state rules have higher specificity and keep their own colours.
    rule(".surfaces-card-tile-border", {"border-color": "var(--cr-a-hover)"},
         note="vanilla tile-card border #FFFFFF33 was a visible line on dark; -> #FFFFFF14 (guide 3.3)")
    # round 9 (2026-11-04): sidebar SHELVED by user decision ("forget the sidebar"). The round-7
    # rail rules (#MainNav rows, #SecondaryNavigationBar margin-left: 210px, .cr-sidebar page shift),
    # the round-8 #CrimsonSideBar/#DirectLinks rules and the FMET hybrid + Club Info retirement rules
    # were removed here (the round-7c/round-8 builds and their hashes remain in backups\ and the
    # install log). This restores the pure base Crimson rule set (round 7, 185 rules).
    # match (3.3)
    rule("#PositionBlock #NumberText", {"white-space": "nowrap", "min-width": "22px", "-unity-text-align": "middle-right"})
    rule("#LatestScores #Home, #LatestScores #Away, #LatestScoresContainer #Home, #LatestScoresContainer #Away",
         {"flex-grow": "1", "flex-shrink": "1"})
    rule("#LatestScores #HomeTeam, #LatestScores #AwayTeam, #LatestScoresContainer #HomeTeam, #LatestScoresContainer #AwayTeam",
         {"text-overflow": "ellipsis", "overflow": "hidden"})
    rule("#LatestScores #Score, #LatestScoresContainer #Score", {"max-width": "44px"})

    # ---- step 4 round 1 fixes (2026-11-03, Dortmund screenshots) ------------------
    # 1. club background: GameWorldBackground panel (layer "Background"). Root has the
    #    non-unique name panel_root (5 trees) but name + its two classes is unique (1 element
    #    in 7328 trees). SIRenderTextureImage = game.BackgroundImage.BackgroundRenderTexture,
    #    #background_image = game.BackgroundImage.BackgroundImage (both children of the
    #    Use3DBackground BindableSwitchElement). Never display:none (guide 3.3).
    GWB = "#panel_root.align-items-stretch.justify-content-space-between"
    rule(GWB, {"background-color": "var(--cr-n-0)"}, note="GameWorldBackground root (unique: name + 2 classes)")
    rule(f"{GWB} > BindableSwitchElement > #background_image, {GWB} > BindableSwitchElement > SIRenderTextureImage, {GWB} SIGradient",
         {"opacity": "0"}, note="club wallpaper: 2D image + 3D render texture (+ any gradient; none in vanilla)")
    # 2. player profile header: SIGradient #PlayerReportHeaderGradient is bound in code to
    #    teamcontainer.TitlebarBackgroundColour (custom props lose) and is the PARENT of the
    #    whole header, so opacity would hide photo + name. visibility is inherited but a child
    #    may set visible: the gradient stops drawing, its content stays.
    rule("#PlayerReportHeaderRemapper.entity-background-header", {"background-color": "var(--cr-n-1)", "border-bottom-width": "1px",
                                                                  "border-bottom-color": "var(--cr-n-5)"}, note="flat header like the nav bars")
    rule("SIGradient#PlayerReportHeaderGradient", {"visibility": "hidden"})
    rule("SIGradient#PlayerReportHeaderGradient > #PlayerReportHeaderSetter", {"visibility": "visible"})
    # 3. budget figures: SIText #AvailableValueText .brand-foundation-horizon-color (Transfer/Wage
    #    budget tiles, club finances, scouting budget: 55 elements). Static UXML class (no state
    #    binding) -> brand-accent figure, not a state -> off-white.
    rule(".brand-foundation-horizon-color", {"color": "var(--cr-t-1)"}, on=["--cr-n-2", "--cr-n-3"],
         note="was --colours-brand-foundation-horizon-base (crimson 200)")
    # 4. Portal tile headings: SIText .layout-modules-tiles-title-color .tile-title-color inside a
    #    tertiary button; vanilla .layout-modules-tiles-title-color (brand accent) beat
    #    .tile-title-color by sheet order. Off-white text, crimson underline on hover only.
    rule(".layout-modules-tiles-title-color", {"color": "var(--cr-t-1)"}, on=["--cr-n-2"])
    # round 2 (2026-11-03): the real section headings are the `title-link` template
    # (+ NewsRoundupTitle): SIButton .title-link-button (underline = its border-bottom,
    # --colours-brand-highlight-pink-base) > SIText .title-link-primary-text (same token;
    # hover = --colours-base-pink-soft). Off-white at rest, no underline; crimson 1px on hover/press.
    rule(".title-link-button", {"border-bottom-width": "1px", "border-bottom-color": "var(--cr-transparent)"})
    rule(".title-link-button:hover, .title-link-button:active:enabled", {"border-bottom-color": "var(--cr-c-400)"})
    rule(".title-link-primary-text, .title-link-button:hover .title-link-primary-text, "
         ".title-link-button:active:enabled .title-link-primary-text", {"color": "var(--cr-t-1)"}, on=["--cr-n-1", "--cr-n-2"])
    # round 2: report/tool page wallpaper. SIImage #Card-frame is bound to
    # game.BackgroundImage.BackgroundImage in FigmaBaseTool*(6), FigmaBaseReportTabbedTemplate,
    # FigmaFullscreenBlockTemplate, ContractNegotiationToolTemplate, OnlineManagerAndGameStatus(2)
    # - player, staff, club-profile and nation-profile reports. It is the parent of the whole
    # card: visibility hidden stops the image, its children set visible again (never opacity/display).
    # round 4 fix: round 2 hid EVERY #Card-frame, which also emptied the 6 unbound (opaque)
    # frames of club/nation/recruitment/site pages and left the bound pages transparent, so the
    # screen underneath showed through. Now: hide only the 10 bound frames (selectors proven to
    # match exactly those 10 and none of the 6 unbound), and give the bound frame's parent (its
    # only child is the frame, which holds #Header + #GridSafeArea) an opaque #101010.
    CF_BOUND = ["#SpeakToVariables SIImage#Card-frame",                       # 5 FigmaBaseTool*, ReportTabbed, FullscreenBlock, ContractNegotiation
                "#SpeakToSideRemapper SIImage#Card-frame",                     # OnlineManagerAndGameStatus
                "#ElementBindingRoot > ComponentElement > BaseCardTemplateImpl#CardController > ComponentElement"
                " > #layout-tool-default-default > #layout-tool-default-default > SIImage#Card-frame"]  # ...Fullscreen
    rule(", ".join(CF_BOUND), {"visibility": "hidden"}, note="club wallpaper (game.BackgroundImage.BackgroundImage) in the 10 bound frames only")
    rule(", ".join(s + " > *" for s in CF_BOUND), {"visibility": "visible"})
    CF_PARENTS = ["#SpeakToVariables.height-100-percent > SIStyleSetter.flex-grow-class > VisualElement.flex-grow-class > #BindingVariables.flex-grow-class",  # 5 FigmaBaseTool*
                  "#SpeakToVariables #layout-report-default-default--unpacked > #layout-report-default-default",   # FigmaBaseReportTabbedTemplate
                  "#card-variables > #layout-report-default-default > #layout-report-default-default",              # FigmaFullscreenBlockTemplate
                  "#SpeakToVariables #layout-tool-default-default > #layout-tool-default-default",                  # ContractNegotiationToolTemplate
                  "#SpeakToSideRemapper #layout-tool-default-default",                                              # OnlineManagerAndGameStatus
                  "#ElementBindingRoot > ComponentElement > BaseCardTemplateImpl#CardController > ComponentElement"
                  " > #layout-tool-default-default > #layout-tool-default-default"]                                  # ...Fullscreen
    rule(", ".join(CF_PARENTS), {"background-color": "var(--cr-n-0)"}, note="opaque page behind the hidden bound frame")
    # round 4: news hub header bands (Transfer Hub "Headline Stories", News home / for you /
    # around the world; and the entity news headers club / comp / nation / continent / national
    # team). SIImage (texture) > SIGradient (club/entity colour, bound in code) wrap the whole
    # header content, so: both stop drawing (visibility), the content wrapper stays visible and
    # carries the flat #171717 band with a 1px #444444 bottom line, like the nav bars.
    NEWS = ["BindingExpect#BindingExpect.flex-grow-class > SIImage.flex-grow-class",
            "BindingExpect#BindingExpect.flex-grow-class > BindingRemapper.flex-grow-class > SIImage.flex-grow-class"]
    rule(", ".join(f"{n}, {n} > SIGradient.flex-grow-class" for n in NEWS), {"visibility": "hidden"},
         note="NewsTransfersHub/Home/ForYou/AroundTheWorld + News Club/Comp/Nation/Continent/NationalTeam site headers")
    rule(", ".join(f"{n} > SIGradient.flex-grow-class > *" for n in NEWS),
         {"visibility": "visible", "background-color": "var(--cr-n-1)", "border-bottom-width": "1px", "border-bottom-color": "var(--cr-n-5)"})
    # round 5: header sweep - every UXML element bound to a club / team / nation / competition / continent colour,
    # classified and given a proven selector by tools/header_sweep.py (list: notes/header-sweep.md). Nav bars,
    # scoreboards, commentary, crests / flags / kits, licensed broadcast popups and data colours are excluded there.
    # 2026-11-04 fix: selectors start at the template's first real element (UXML root dropped - a runtime instance
    # sits under a TemplateContainer, colour-reach-report Q1a/Q1b), each re-proved structurally + by raw byte search.
    # Kept club-coloured by user decision (2026-11-03): NonPlayerReportHeader (staff profile), ClubSiteHeader,
    # ContinentSiteHeader; NationSiteHeader dropped (chain identical to ClubSiteHeader's).
    R.extend(sweep_rules)
    # round 3: Auto Training Week 0.4.1 adds cr-atw-* classes. Its colours stay inline in the
    # mod (inline beats USS; the dialog must keep working when the vanilla bundles are back).
    # The font is the one property the mod never sets inline, so it comes from here.
    rule(".cr-atw-dialog", {"-unity-font-definition": "var(--typography-family-primary)"},
         note="Auto Training Week 0.4.1 dialog font (no-op until the mod is installed)")
    # 5. top-left sliver: PrimaryNavigationBarClubColours kit strip - SIStyleSetter
    #    #ClubColoursStyleSetter / #NationColoursStyleSetter .navigation-core-clubname-kit holding
    #    Image #HomeColour .fm-club-primary-color / #AwayColour .fm-club-secondary-color (code-set
    #    from human.team.club.PrimaryColor/SecondaryColor) + the .clubcolours-border outline.
    rule("#ClubColoursStyleSetter.navigation-core-clubname-kit, #NationColoursStyleSetter.navigation-core-clubname-kit",
         {"background-color": "var(--cr-n-1)"})
    rule(".navigation-core-clubname-kit Image", {"opacity": "0"})
    rule(".clubcolours-border", {"border-color": "var(--cr-transparent)"})

    # ---------------------------------------------------------------- contrast pairs (FM tokens)
    PAIRS = []
    for fg in ["--colours-ui-text-strong", "--colours-ui-text-soft"]:
        for bg in ["--colours-ui-base", "--colours-ui-soft", "--colours-ui-strong", "--layout-surfaces-modal-surface"]:
            PAIRS.append({"fg": fg, "bg": bg})
    PAIRS += [{"fg": "--cr-t-muted", "bg": b} for b in ["--cr-n-1", "--cr-n-2", "--cr-n-3"]]
    PAIRS += [{"fg": "--brand-theme-accent", "bg": b, "note": "crimson text"} for b in ["--cr-n-1", "--cr-n-2", "--cr-n-3", "--cr-n-4"]]
    PAIRS += [{"fg": "--buttons-text-default", "bg": "--cr-n-5", "note": "secondary button"}]
    PAIRS += [{"fg": "--cr-t-1", "bg": "--data-average-rating-surface-6-7", "note": "neutral rating chip"}]
    for f in POS.values():
        PAIRS.append({"fg": "--cr-white", "bg": f"--cr-{f}-strong", "note": "tactics position label"})
    for p in POS:
        PAIRS.append({"fg": f"--data-player-position-{p}-foreground", "bg": f"--data-player-position-{p}-background", "note": "position chip"})
    for k in ADJ:
        PAIRS.append({"fg": f"--status-coaching-adjective-ratings-{k}-text", "bg": f"--status-coaching-adjective-ratings-{k}-surface", "note": "coaching adjective on panel"})
    for fg in ["--interaction-global-color-feedback-positive", "--interaction-global-color-feedback-warning",
               "--communication-feedback-information", "--status-player-status-manager-club"]:
        PAIRS += [{"fg": fg, "bg": b} for b in ["--cr-n-1", "--cr-n-2"]]
    PAIRS += [{"fg": "--cr-white", "bg": "--cr-red-deep", "note": "critical state 2.5"}]

    SPEC = {
        "version": "crimson 0.1.0 (2026-11-03) - FM27-CRIMSON-EDITION.md rev 5 sections 2-3, vanilla 2026-11-02",
        "notes": "Generated by tools/make_crimson_json.py; documented in notes/token-map.md. Values: #RRGGBB | #RRGGBBAA | rgba() | var(--x) | <n>px. "
                 "literal_map keys are RGB (alpha of each use kept). Appended-rule keys 'on' (contrast gate surfaces) and 'note' are ignored by token_patch.py.",
        "competition_sheets": "skip",
        "skip_sheets": ["PremierLeague", "Bundesliga", "EFLChampionship", "UEFAChampionsLeague", "UEFAEuropa", "UEFASuperCup",
                        "UEFAUWCL", "FIFAWC", "FIFAWC2026", "LanguageDirectionCommon", "LanguageDirectionLTR", "LanguageDirectionRTL",
                        "LanguageDirectionLTRCombined", "LanguageDirectionRTLCombined", "LanguageNameOrderGivenFirst",
                        "LanguageNameOrderSurnameFirst", "TestsStyles"],
        "flatten_gradients": True,
        "tokens": dict(sorted(T.items())),
        "literal_map": dict(sorted(LIT.items())),
        "rename_classes": {"nav-on-light": "skin-off-navlight0", "nav-on-dark": "skin-off-navdark0"},
        "append_rules_by_sheet": {"AlwaysAppliedStyleSheet": R},
        "contrast_pairs": PAIRS,
    }
    return SPEC, WHY, {k: vanilla(k) for k in T}


def project(index, name):
    """The generator's strings are converted to the canonical colour form by project.migrate (as a schema 1
    project): #RRGGBB -> alpha 1.0, #RRGGBBAA -> alpha byte/255, literal_map -> rgb-keep-alpha swaps."""
    man = {t: [{"value": v} for v in d.values()] for t, d in index.defs.items()}
    spec, why, van = make(man)
    p = project_mod.new(name, index.meta.get("game_build"))
    p["schema"] = 1
    p["options"].update(flatten_gradients=True, skip_sheets=spec["skip_sheets"])
    p["rename_classes"] = spec["rename_classes"]
    p["token_overrides"] = [{"token": k, "value": v, "vanilla": " / ".join(van[k]), "note": why.get(k, "")}
                            for k, v in spec["tokens"].items()]
    p["literal_swaps"] = [{"from": k, "to": v, "scope": "all_sheets"} for k, v in spec["literal_map"].items()]
    p["scoped_rules"] = [dict(r, sheet="AlwaysAppliedStyleSheet") for r in spec["append_rules_by_sheet"]["AlwaysAppliedStyleSheet"]]
    p["contrast_pairs"] = spec["contrast_pairs"]
    return project_mod.migrate(p, colour.B_PRESET)
