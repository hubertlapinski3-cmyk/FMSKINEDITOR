"""Serialized USS (Unity StyleSheet typetree) decode helpers, after tools/uss_decompile.py.
Pure Python, works on typetree dicts. Encoding and selector parsing live in token_patch.py.

Two selector layouts are read: nested per rule (FM27, verified) and a top-level
m_ComplexSelectors list with ruleIndex (FM26 skins, per ctrl_dump.py).
"""
import re

from . import colour
from .token_patch import PROP_TABLE as PROP_IDS, INV_PROP

PROP_NAMES = dict(INV_PROP)

KEYWORDS = {0: "inherit", 1: "initial", 2: "auto", 3: "unset", 4: "true", 5: "false", 6: "none"}
WRITE_KEYWORDS = {"inherit": 0, "initial": 1, "auto": 2, "unset": 3, "none": 6}
# 1 and 2 are verified. uss_decompile.py and uss_dump.py disagree on 6/7, so 3+ follow Unity's Dimension.Unit enum.
UNITS = {0: "", 1: "px", 2: "%", 3: "s", 4: "ms", 5: "deg", 6: "grad", 7: "rad", 8: "turn"}
WRITE_UNITS = {"px": 1, "%": 2}
FUNCS = {1: "var", 2: "env", 3: "linear-gradient"}

T_KEYWORD, T_FLOAT, T_DIM, T_COLOR, T_RES, T_ASSET, T_ENUM, T_VAR, T_STR, T_FUNC, T_COMMA, T_IMG = range(1, 13)
P_WILD, P_TYPE, P_CLASS, P_PSEUDO, P_ID = 1, 2, 3, 4, 6


def prop_name(p):
    return p.get("m_CustomName") or p.get("m_Name") or PROP_NAMES.get(p.get("m_Id"), "-unity-id-%s" % p.get("m_Id"))


def selector_map(tree):
    """List (per rule index) of that rule's complex selectors."""
    rules = tree.get("m_Rules", [])
    out = [list(r.get("m_ComplexSelectors", [])) for r in rules]
    for c in tree.get("m_ComplexSelectors", []) or []:
        i = c.get("ruleIndex", -1)
        if 0 <= i < len(out):
            out[i].append(c)
    return out


def _part_text(p):
    t, v = p.get("m_Type"), p.get("m_Value", "")
    return {P_WILD: "*", P_TYPE: v, P_CLASS: "." + v, P_PSEUDO: ":" + v, P_ID: "#" + v}.get(t, "?%s(%s)" % (t, v))


def selector_text(complex_sel):
    out = ""
    for s in complex_sel.get("m_Selectors", []):
        rel = s.get("m_PreviousRelationship", 0)
        if out:
            out += " > " if rel == 1 else " "
        out += "".join(_part_text(p) for p in s.get("m_Parts", []))
    return out


def is_token_rule(complex_sels):
    for c in complex_sels:
        for s in c.get("m_Selectors", []):
            for p in s.get("m_Parts", []):
                if (p.get("m_Type") == P_PSEUDO and p.get("m_Value") == "root") or \
                   (p.get("m_Type") == P_CLASS and p.get("m_Value") == "unity-theme-env-variables"):
                    return True
    return False


def _num(x):
    return "%g" % x


def value_text(tree, handles, failures=None):
    """Handles -> (readable text, [[#RRGGBB, alpha float], ...] for every literal colour).
    The text shows alpha as a hex byte; the list keeps the decoded float.
    A colour entry outside 0..1 is not decoded: the text gets ?colour[index](raw r, g, b, a), the colour is
    left out of the list, and {index, raw} is appended to failures when a list is given."""
    out, cols, i = [], [], 0
    strings = tree.get("strings", [])

    def s(idx):
        return strings[idx] if 0 <= idx < len(strings) else "?str%d" % idx

    while i < len(handles):
        t, v = handles[i].get("m_ValueType"), handles[i].get("valueIndex")
        try:
            if t == T_FUNC:
                n = 0
                if i + 1 < len(handles) and handles[i + 1].get("m_ValueType") == T_FLOAT:
                    n = int(tree["floats"][handles[i + 1]["valueIndex"]])
                    i += 1
                txt, c = value_text(tree, handles[i + 1:i + 1 + n], failures)
                i += n
                cols += c
                out.append("%s(%s)" % (FUNCS.get(v, "func%s" % v), txt))
            elif t == T_KEYWORD:
                out.append(KEYWORDS.get(v, "keyword%s" % v))
            elif t == T_FLOAT:
                out.append(_num(tree["floats"][v]))
            elif t == T_DIM:
                d = tree["dimensions"][v]
                out.append(_num(d["value"]) + UNITS.get(d["unit"], "?unit%s" % d["unit"]))
            elif t == T_COLOR:
                try:
                    c = colour.from_floats(tree["colors"][v], tree.get("m_Name", ""))
                    cols.append([colour.hex6(c), c[3]])
                    out.append(colour.text(c))
                except colour.ColourDecodeError as e:
                    if failures is not None:
                        failures.append({"index": v, "raw": e.raw})
                    out.append("?colour[%d](%s)" % (v, ", ".join("%r" % x for x in e.raw)))
            elif t in (T_ENUM, T_VAR):
                out.append(s(v))
            elif t == T_STR:
                out.append('"%s"' % s(v))
            elif t == T_RES:
                out.append('resource("%s")' % s(v))
            elif t == T_ASSET:
                a = tree["assets"][v]
                out.append("asset(%s:%s)" % (a.get("m_FileID"), a.get("m_PathID")))
            elif t == T_COMMA:
                out.append(",")
            elif t == T_IMG:
                out.append("scalable-image(%s)" % v)
            else:
                out.append("?type%s(%s)" % (t, v))
        except (IndexError, KeyError, TypeError):
            out.append("?bad(%s,%s)" % (t, v))
        i += 1
    return " ".join(out).replace(" ,", ","), cols
