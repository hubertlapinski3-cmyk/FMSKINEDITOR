"""USS values for the renderer: tokenising, `var()` resolution, shorthand expansion and the USS -> CSS map.

The map never drops a property silently (owner condition, docs/PHASE9-PLAN.md section 1). Every USS property is looked up in `PROPERTIES` and comes back with a
status: `mapped` (an equivalent CSS property with the same meaning), `partial` (CSS approximates it; the note says how), `unmapped` (no CSS equivalent; kept in the
data, shown flagged, not drawn) or `unknown` (the name is not in the table, which includes the `-unity-id-N` properties the editor cannot name yet). Custom
properties (`--x`) are `variable`. The renderer applies `mapped` and `partial` values and the explain panel lists the others.

The USS property names and the inherited-property list follow Unity's documented USS reference; the values the table claims as `mapped` are confirmed against the
inspector's resolved values as the calibration fixtures grow (M0/M1)."""
import re

# ---- tokens
_NUM = re.compile(r"^-?(?:\d+\.?\d*|\.\d+)(?:[eE]-?\d+)?$")
_DIM = re.compile(r"^(-?(?:\d+\.?\d*|\.\d+)(?:[eE]-?\d+)?)(px|%|s|ms|deg|grad|rad|turn)$")
_HEX = re.compile(r"^#(?:[0-9a-fA-F]{3,4}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})$")
_FUNC = re.compile(r"^([A-Za-z][\w-]*)\((.*)\)$", re.S)


def split_top(text):
    """Split on spaces and commas outside parentheses and quotes; commas come back as ','."""
    out, cur, depth, quote = [], "", 0, None
    for ch in text:
        if quote:
            cur += ch
            if ch == quote:
                quote = None
        elif ch in "\"'":
            quote = ch
            cur += ch
        elif ch == "(":
            depth += 1
            cur += ch
        elif ch == ")":
            depth -= 1
            cur += ch
        elif depth == 0 and ch in " \t\n,":
            if cur:
                out.append(cur)
                cur = ""
            if ch == ",":
                out.append(",")
        else:
            cur += ch
    if cur:
        out.append(cur)
    return out


def parse_token(s):
    if s == ",":
        return {"k": "comma", "raw": s}
    if _NUM.match(s):
        return {"k": "num", "v": float(s), "raw": s}
    m = _DIM.match(s)
    if m:
        return {"k": "dim", "v": float(m.group(1)), "unit": m.group(2), "raw": s}
    if _HEX.match(s):
        return {"k": "color", "raw": s}
    m = _FUNC.match(s)
    if m:
        return {"k": "func", "name": m.group(1), "args": m.group(2), "raw": s}
    if s[:1] in "\"'":
        return {"k": "str", "v": s[1:-1], "raw": s}
    return {"k": "kw", "v": s, "raw": s}


def parse(text):
    return [parse_token(t) for t in split_top(text or "")]


# ---- var() resolution
def _find_vars(text):
    """[(start, end, name, fallback or None)] for the top-level var( ... ) calls of a text."""
    out, i = [], 0
    while True:
        i = text.find("var(", i)
        if i < 0:
            return out
        depth, j = 0, i + 3
        while j < len(text):
            if text[j] == "(":
                depth += 1
            elif text[j] == ")":
                depth -= 1
                if depth == 0:
                    break
            j += 1
        inner = text[i + 4:j]
        name, _, fb = inner.partition(",")
        out.append((i, j + 1, name.strip(), fb.strip() if _ else None))
        i = j + 1


def resolve_vars(text, lookup, chain=None, depth=0):
    """Replace var(--x[, fallback]) using lookup(name) -> value text or None. `chain` collects the names followed (the token chain). Returns (text, unresolved names)."""
    if depth > 24 or "var(" not in text:
        return text, []
    unresolved, out, last = [], "", 0
    for a, b, name, fb in _find_vars(text):
        out += text[last:a]
        val = lookup(name)
        if chain is not None:
            chain.append(name)
        if val is None:
            if fb is not None:
                val, u = resolve_vars(fb, lookup, chain, depth + 1)
                unresolved += u
            else:
                val = text[a:b]
                unresolved.append(name)
        else:
            val, u = resolve_vars(val, lookup, chain, depth + 1)
            unresolved += u
        out += val
        last = b
    return out + text[last:], unresolved


# ---- shorthands (expanded after var() is resolved)
def _four(vals):
    n = len(vals)
    if n == 1:
        return vals * 4
    if n == 2:
        return [vals[0], vals[1], vals[0], vals[1]]
    if n == 3:
        return [vals[0], vals[1], vals[2], vals[1]]
    return vals[:4]


def expand(name, text):
    """[(longhand, value text)] for a declaration; a longhand or an unknown name comes back as it is."""
    toks = [t for t in split_top(text) if t != ","]
    if name in ("margin", "padding") and toks:
        return [("%s-%s" % (name, side), v) for side, v in zip(("top", "right", "bottom", "left"), _four(toks))]
    if name in ("border-width", "border-color") and toks:
        base = name.split("-")[1]
        return [("border-%s-%s" % (side, base), v) for side, v in zip(("top", "right", "bottom", "left"), _four(toks))]
    if name == "border-radius" and toks:
        return [("border-%s-radius" % c, v) for c, v in zip(("top-left", "top-right", "bottom-right", "bottom-left"), _four(toks))]
    if name == "flex" and toks:
        if toks[0] == "initial":
            g, s, b = "0", "1", "auto"
        elif toks[0] == "auto":
            g, s, b = "1", "1", "auto"
        elif toks[0] == "none":
            g, s, b = "0", "0", "auto"
        else:
            g, s, b = "0", "1", "auto"
            nums = [t for t in toks if _NUM.match(t)]
            dims = [t for t in toks if _DIM.match(t) or t == "auto"]
            if nums:
                g = nums[0]
            if len(nums) > 1:
                s = nums[1]
            if len(nums) > 2 and not dims:
                dims = [nums[2]]
            if dims:
                b = dims[0]
        return [("flex-grow", g), ("flex-shrink", s), ("flex-basis", "0px" if b == "0" else b)]
    return [(name, text)]


# ---- inheritance (USS: documented inherited properties) and the map
INHERITED = {"color", "cursor", "font-size", "letter-spacing", "word-spacing", "visibility", "white-space", "-unity-font", "-unity-font-definition",
             "-unity-font-style", "-unity-text-align", "-unity-text-outline-color", "-unity-text-outline-width", "text-shadow",
             "-unity-paragraph-spacing", "-unity-text-overflow-position", "-unity-text-generator"}

_M, _P, _U = "mapped", "partial", "unmapped"
PROPERTIES = {}


def _add(status, note, *items):
    for it in items:
        css, uss = (it, it) if isinstance(it, str) else it
        PROPERTIES[uss] = (css, status, note)


_add(_M, "", "width", "height", "min-width", "min-height", "max-width", "max-height", "flex-grow", "flex-shrink", "flex-basis", "flex-direction", "flex-wrap",
     "align-items", "align-self", "align-content", "justify-content", "display", "position", "left", "top", "right", "bottom",
     "margin-top", "margin-right", "margin-bottom", "margin-left", "padding-top", "padding-right", "padding-bottom", "padding-left",
     "border-top-width", "border-right-width", "border-bottom-width", "border-left-width",
     "border-top-color", "border-right-color", "border-bottom-color", "border-left-color",
     "border-top-left-radius", "border-top-right-radius", "border-bottom-right-radius", "border-bottom-left-radius",
     "background-color", "color", "font-size", "opacity", "overflow", "visibility", "letter-spacing", "word-spacing", "text-overflow")
_add(_P, "USS 'normal' and 'nowrap' only; other values pass through", "white-space")
_add(_P, "Unity text alignment (nine positions) is approximated with text-align and the element's own box; vertical alignment is not drawn", "-unity-text-align")
_add(_P, "bold, italic and bold-and-italic map to font-weight and font-style; the game's font is not loaded", "-unity-font-style")
_add(_P, "the font family is a game asset or a url(); not loaded by the offline render, a stand-in family is used", "-unity-font-definition", "-unity-font")
_add(_P, "an image asset reference; drawn only when the asset resolves (M4), otherwise a labelled placeholder", "background-image")
_add(_P, "the tint multiplies the image in Unity; not applied", "-unity-background-image-tint-color")
_add(_P, "scale mode approximated with background-size", "-unity-background-scale-mode")
_add(_P, "mapped to CSS transforms; rotation origin differs slightly", "translate", "scale", "rotate", "transform-origin")
_add(_P, "9-slice insets approximated as a stretched image", "-unity-slice-left", "-unity-slice-top", "-unity-slice-right", "-unity-slice-bottom", "-unity-slice-scale", "-unity-slice-type")
_add(_P, "text outline approximated with text-shadow", "-unity-text-outline-width", "-unity-text-outline-color")
_add(_U, "transitions are not animated in the render", "transition", "transition-property", "transition-duration", "transition-timing-function", "transition-delay")
_add(_U, "pointer cursors have no effect in the render", "cursor")
_add(_U, "no CSS equivalent", "-unity-paragraph-spacing", "-unity-text-overflow-position", "-unity-text-generator", "text-shadow", "-unity-overflow-clip-box")
_add(_M, "", "aspect-ratio")
_add(_P, "background positioning and size are approximated; drawn once background images resolve (M4)", "background-position-x", "background-position-y", "background-repeat",
     "background-size")
SHORTHANDS = ("margin", "padding", "border-width", "border-color", "border-radius", "flex")


# Names for property ids the editor's token_patch table does not have. NOT from decompiled code. Source of each name: Unity numbers the style properties of a group
# alphabetically (the editor's own known ids show it: 131072 align-content, 131073 align-items, 131074 align-self, 131076 border-bottom-width ...), so an unknown id
# sits in the alphabetical gap of its neighbours; the CONFIRMING OBSERVATION is the value pattern of every rule that uses the id in the 49 sheets (counts in
# data/render/uss-property-census.json), e.g. 393216..393219 carry '0s' / durations / 'opacity' / 'ease-in-out' = transition-delay, -duration, -property,
# -timing-function (the order of Unity's manual); 196608 carries 'url(..) x y' = cursor; 458759/60/64/65 carry '8px' '4px' = the four corner radii.
# Names marked INFERRED rest on that pattern only; they are reported as inferred wherever they are shown.
ID_NAMES = {
    65548: "-unity-text-generator",            # values advanced/standard
    65549: "-unity-text-outline-color",        # colour values (#00000000, var(--none))
    65550: "-unity-text-outline-width",        # value 0
    65553: "word-spacing",                     # 4px; follows white-space (65552) alphabetically
    131075: "aspect-ratio",                    # value 1
    196608: "cursor",                          # url(...) hotspot-x hotspot-y
    196611: "-unity-overflow-clip-box",        # content-box
    196612: "-unity-slice-bottom",             # alphabetical run bottom, left, right, scale, top, type, text-overflow-position
    196613: "-unity-slice-left",               # 19 / 10
    196614: "-unity-slice-right",              # 19 / 10
    196615: "-unity-slice-scale",              # 0.1px
    196616: "-unity-slice-top",                # 0
    196617: "-unity-slice-type",               # 'sliced'
    196618: "-unity-text-overflow-position",   # end
    262153: "-unity-background-scale-mode",    # scale-to-fit / scale-and-crop / stretch-to-fill (the enum's own values)
    393216: "transition-delay",                # 0s, 0s 0s
    393217: "transition-duration",             # 0.5s, var(--global-transition-*)
    393218: "transition-property",             # opacity / translate / scale
    393219: "transition-timing-function",      # ease-in-out
    458754: "background-position-x",           # 'right 2px', 'left 0'
    458755: "background-position-y",           # 'top 0'
    458756: "background-repeat",               # 'repeat repeat'
    458757: "background-size",                 # '13px 13px', '35px 25px'
    458759: "border-bottom-left-radius",       # 8px 4px 0 12px
    458760: "border-bottom-right-radius",
    458764: "border-top-left-radius",
    458765: "border-top-right-radius",
}


def canonical(name):
    """(name to use, True when the name is inferred from a property id). The id 262145 ('right', one rule) is left unnamed rather than guessed."""
    if name.startswith("-unity-id-"):
        try:
            nm = ID_NAMES.get(int(name.rsplit("-", 1)[1]))
        except ValueError:
            nm = None
        if nm:
            return nm, True
    return name, False


def classify(name):
    """(css property or None, status, note) for a USS property name."""
    if name.startswith("--"):
        return None, "variable", "custom property: resolved into the values that use it"
    if name in SHORTHANDS:
        return None, "shorthand", "expanded into its longhands, which are what is classified and drawn"
    hit = PROPERTIES.get(name)
    if hit:
        return hit
    if name.startswith("-unity-id-"):
        return None, "unknown", "a property id the editor cannot name yet (not in the property table)"
    return None, "unknown", "not in the USS property table"


_TEXT_ALIGN = {"left": "left", "center": "center", "right": "right"}


def to_css(name, value):
    """[(css property, css value)] that draw one resolved longhand, [] when it is not drawn. Called only for `mapped` and `partial` names."""
    css, status, _ = classify(name)
    if css is None or status not in ("mapped", "partial"):
        return []
    v = value.strip()
    if name == "align-items" and v == "auto":
        v = "stretch"
    if name == "-unity-font-style":
        return [("font-weight", "700" if "bold" in v else "400"), ("font-style", "italic" if "italic" in v else "normal")]
    if name == "-unity-text-align":
        h = v.split("-")[-1]
        return [("text-align", _TEXT_ALIGN.get(h, "left"))]
    if name in ("-unity-font-definition", "-unity-font", "-unity-background-image-tint-color", "background-image", "-unity-background-scale-mode") or name.startswith("-unity-slice"):
        return []                                  # partial: the explain panel says why nothing is drawn yet
    if name in ("translate", "scale", "rotate", "transform-origin"):
        return []                                  # M2: composed into one transform
    if name in ("-unity-text-outline-width", "-unity-text-outline-color"):
        return []
    if name == "text-overflow" and v not in ("clip", "ellipsis"):
        return []
    if name == "white-space" and v not in ("normal", "nowrap", "pre", "pre-wrap"):
        return []
    # unitless numbers on length properties are pixels in USS
    if re.match(r"^-?[\d.]+$", v) and name not in ("opacity", "flex-grow", "flex-shrink"):
        v = "%spx" % v if float(v) != 0 else "0"
    return [(css, v)]
