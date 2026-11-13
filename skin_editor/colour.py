"""The only colour conversion code in the app. A colour is a tuple (r, g, b, a): r, g, b bytes 0..255,
a a float 0..1 kept at full precision. Canonical JSON form: {"rgb": "#RRGGBB", "a": 0.652}.
The game stores colours as four 0..1 floats; the 8-digit hex form is display only (alpha rounded to a byte)."""
import logging
import math
import re

HEX6 = re.compile(r"#([0-9a-fA-F]{6})")
HEX8 = re.compile(r"#([0-9a-fA-F]{6})([0-9a-fA-F]{2})")
FUNC = re.compile(r"rgba?\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*(?:,\s*([-+0-9.eE]+)\s*)?\)")


log = logging.getLogger("skin_editor.colour")

# The legacy project-data boundaries. legacy_alpha() may be called from these and nowhere else.
# Bundle data is NOT one of them: a bundle colour outside 0..1 is a decode failure (ColourDecodeError)
# until diagnostics/ holds evidence for a scale. See diagnostics/README.md.
B_SCHEMA1 = "schema-1 project migration"
B_PRESET = "crimson preset conversion"


class ColourDecodeError(ValueError):
    """A bundle colour entry with a component outside 0..1. No scale is guessed."""
    def __init__(self, raw, context=""):
        self.raw = raw
        ValueError.__init__(self, "bundle colour outside 0..1, scale unproven: %r %s" % (raw, context))

LEGACY = []          # conversions made in this process: {boundary, context, original, stored}
_seen = set()


def legacy_alpha(a, boundary, context=""):
    """Alpha arriving at a legacy ingestion boundary. 0..1 passes through. A number above 1 and up to 100 is
    read as a percentage, divided by 100, and the original is logged with the boundary that converted it.
    Anything else raises. The canonical validator (from_obj) never calls this and stays strict."""
    if boundary not in (B_SCHEMA1, B_PRESET):
        raise ValueError("legacy_alpha is only for the ingestion boundaries, not %r" % (boundary,))
    if isinstance(a, bool) or not isinstance(a, (int, float)) or a != a:
        raise ValueError("alpha %r is not a number (%s, %s)" % (a, boundary, context))
    a = float(a)
    if 0.0 <= a <= 1.0:
        return a
    if 1.0 < a <= 100.0:
        new = a / 100.0
        if (boundary, context, a) not in _seen:
            _seen.add((boundary, context, a))
            if len(LEGACY) < 1000:
                LEGACY.append({"boundary": boundary, "context": context, "original": a, "stored": new})
            log.warning("percent alpha %r stored as %r at boundary: %s [%s]", a, new, boundary, context)
        return new
    raise ValueError("alpha %r is outside 0..1 and outside the percent range (%s, %s)" % (a, boundary, context))


def legacy(v, boundary, context=""):
    """Boundary version of canonical(): colour object or string -> canonical object, with legacy_alpha
    applied to the alpha. Non-colour values are returned unchanged."""
    if isinstance(v, dict) and set(v) == {"rgb", "a"}:
        if not isinstance(v["rgb"], str) or not HEX6.fullmatch(v["rgb"]):
            raise ValueError("bad colour %r" % (v,))
        return {"rgb": hex6(parse(v["rgb"])), "a": legacy_alpha(v["a"], boundary, context or v["rgb"])}
    if isinstance(v, str):
        m = FUNC.fullmatch(v.strip())
        if m and m.group(4):
            r, g, b = (int(m.group(i)) for i in (1, 2, 3))
            if max(r, g, b) > 255:
                raise ValueError("colour out of range: " + v)
            return to_obj((r, g, b, legacy_alpha(float(m.group(4)), boundary, context or v)))
    return canonical(v)


def clamp01(x):
    return min(1.0, max(0.0, float(x)))


def unit_to_byte(x):
    """0..1 float -> 0..255 byte, halves rounded up (same as the browser side)."""
    return int(math.floor(clamp01(x) * 255 + 0.5))


def byte_to_unit(b):
    if not 0 <= int(b) <= 255:
        raise ValueError("byte out of range: %r" % (b,))
    return int(b) / 255


def byte_to_hex(b):
    if not 0 <= int(b) <= 255:
        raise ValueError("byte out of range: %r" % (b,))
    return "%02X" % int(b)


def hex_to_byte(h):
    if not re.fullmatch(r"[0-9a-fA-F]{2}", h):
        raise ValueError("not two hex digits: %r" % (h,))
    return int(h, 16)


def hex6(c):
    return "#" + "".join(byte_to_hex(v) for v in c[:3])


def hex8(c):
    return hex6(c) + byte_to_hex(unit_to_byte(c[3]))


def text(c):
    """Display text: #RRGGBB when opaque, else #RRGGBBAA (alpha byte)."""
    return hex6(c) if unit_to_byte(c[3]) == 255 else hex8(c)


def parse(s):
    """'#RRGGBB', '#RRGGBBAA', 'rgb(r,g,b)', 'rgba(r,g,b,a)' -> tuple, or None when s is not a colour."""
    if not isinstance(s, str):
        return None
    s = s.strip()
    m = HEX8.fullmatch(s)
    if m:
        h = m.group(1)
        return tuple(hex_to_byte(h[i:i + 2]) for i in (0, 2, 4)) + (byte_to_unit(hex_to_byte(m.group(2))),)
    m = HEX6.fullmatch(s)
    if m:
        h = m.group(1)
        return tuple(hex_to_byte(h[i:i + 2]) for i in (0, 2, 4)) + (1.0,)
    m = FUNC.fullmatch(s)
    if m:
        r, g, b = (int(m.group(i)) for i in (1, 2, 3))
        a = float(m.group(4)) if m.group(4) else 1.0
        if max(r, g, b) > 255 or not 0.0 <= a <= 1.0:
            raise ValueError("colour out of range: " + s)
        return r, g, b, a
    return None


def is_obj(v):
    return isinstance(v, dict) and set(v) == {"rgb", "a"}


def from_obj(o):
    if not is_obj(o) or not isinstance(o["rgb"], str) or not HEX6.fullmatch(o["rgb"]) \
            or isinstance(o["a"], bool) or not isinstance(o["a"], (int, float)) or not 0.0 <= o["a"] <= 1.0:
        raise ValueError('bad colour %r (want {"rgb": "#RRGGBB", "a": 0..1})' % (o,))
    return parse(o["rgb"])[:3] + (float(o["a"]),)


def to_obj(c):
    return {"rgb": hex6(c), "a": float(c[3])}


def coerce(v):
    """Canonical object or colour string -> tuple; anything else -> None."""
    return from_obj(v) if is_obj(v) else parse(v)


def canonical(v):
    """Colour string or object -> canonical object; non-colour values are returned unchanged."""
    c = coerce(v) if (is_obj(v) or isinstance(v, str)) else None
    return to_obj(c) if c else v


def raw_floats(c):
    return [float(c.get(k, 1.0 if k == "a" else 0.0)) for k in "rgba"]


def in_range(c):
    """True when all four stored components of a bundle colour are within 0..1."""
    return all(0.0 <= v <= 1.0 for v in raw_floats(c))


BYTE_ALPHA, HDR, UNCLASSIFIED = "byte-alpha candidate", "hdr", "unclassified"


def classify_out_of_range(raw):
    """Class of a quarantined bundle colour (raw r, g, b, a floats), per diagnostics/README.md.
    Returns (class, display). display is a canonical object for showing the colour only; it is never
    written to a bundle and never used for matching.
      byte-alpha candidate: r, g, b within 0..1, alpha an integer in 2..255. Display alpha = alpha / 255.
      hdr: any of r, g, b above 1. No hex rendering, display is None.
      unclassified: anything else outside 0..1."""
    r, g, b, a = raw
    finite = all(v == v and abs(v) != float("inf") for v in raw)
    if finite and all(0.0 <= v <= 1.0 for v in (r, g, b)) and 1.0 < a <= 255.0 and a == int(a):
        return BYTE_ALPHA, {"rgb": hex6((unit_to_byte(r), unit_to_byte(g), unit_to_byte(b))), "a": byte_to_unit(int(a))}
    if finite and any(v > 1.0 for v in (r, g, b)) and all(v >= 0.0 for v in raw):
        return HDR, None
    return UNCLASSIFIED, None


def from_floats(c, context=""):
    """Bundle colour {r,g,b,a} (0..1 floats) -> tuple, alpha kept as the decoded float.
    Raises ColourDecodeError when any component is outside 0..1; nothing is rescaled or clamped here."""
    if not in_range(c):
        raise ColourDecodeError(raw_floats(c), context)
    return unit_to_byte(c["r"]), unit_to_byte(c["g"]), unit_to_byte(c["b"]), float(c.get("a", 1.0))


def to_floats(c):
    return {"r": byte_to_unit(c[0]), "g": byte_to_unit(c[1]), "b": byte_to_unit(c[2]), "a": float(c[3])}


def patch_value(c):
    """The string handed to token_patch: its rgba() branch keeps the alpha as a float."""
    return hex6(c) if c[3] == 1.0 else "rgba(%d, %d, %d, %r)" % (c[0], c[1], c[2], float(c[3]))


def same(c1, c2, eps=1e-6):
    return tuple(c1[:3]) == tuple(c2[:3]) and abs(c1[3] - c2[3]) <= eps


def key(c):
    """Index key for a full RGBA literal."""
    return "%s/%r" % (hex6(c), float(c[3]))


def composite(top, under):
    """Source-over of an RGBA colour on an opaque RGB colour -> opaque (r, g, b)."""
    a = top[3]
    return tuple(int(math.floor(top[i] * a + under[i] * (1 - a) + 0.5)) for i in range(3))
