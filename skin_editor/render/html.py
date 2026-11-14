"""Render tree -> static HTML (the M0 spike's drawing step, and a reference for the Studio's React renderer).

Each element becomes a `div` carrying `data-i` (its order in a depth-first walk) and the CSS of its `mapped` and `partial` computed properties as inline style.
The defaults mirror UI Toolkit's (Yoga) initial values, which differ from CSS: column direction, `align-items: stretch`, `align-content: flex-start`,
`flex-shrink: 1`, `position: relative`, `min-width/min-height: 0` instead of `auto`, border-box sizing. Text elements show their `text` attribute, or a placeholder
chip for bound text. Nothing here decides geometry: the browser's flexbox does."""
import html as _html
import json
from pathlib import Path

from .. import config

DEFAULTS = ("box-sizing:border-box;display:flex;flex-direction:column;flex-grow:0;flex-shrink:1;flex-basis:auto;align-items:stretch;align-self:auto;"
            "align-content:flex-start;justify-content:flex-start;flex-wrap:nowrap;position:relative;min-width:0;min-height:0;margin:0;padding:0;"
            "border:0 solid transparent;overflow:visible;white-space:normal;font-family:Arial,Helvetica,sans-serif;font-size:14px;color:#ebebeb")


def flatten(top_nodes):
    out = []

    def walk(n):
        out.append(n)
        for c in n.get("children", []):
            walk(c)
    for n in top_nodes:
        walk(n)
    return out


def load_text_metrics(path=None):
    """{font size px (text): line height px} measured from inspector dumps (tools/learn_text_metrics.py); {} when the file is missing."""
    p = Path(path) if path else config.resource_root() / "data" / "render" / "text-metrics.json"
    return json.loads(p.read_text(encoding="utf-8")).get("line_height_px", {}) if p.is_file() else {}


TEXT_TYPES = ("SIText", "Label", "TextElement")


def style_dict(node, metrics=None):
    """{css property: value} that draws one element: its mapped and partial computed properties (the only ones drawn), plus the measured text line height and a border
    style where a border width is set. The same dict feeds the static HTML and the Studio's renderer."""
    css = {}
    for prop, d in node["computed"].items():
        for k, v in d.get("css") or []:
            css[k] = v
    # text rows: the game's measured line height for this font size (the stand-in font's differs); sizes without a measured value keep the browser's
    if node.get("type") == "SIText" and metrics:
        fs = (css.get("font-size") or "").replace("px", "")
        if fs in metrics:
            css["line-height"] = "%spx" % metrics[fs]
    img = (node.get("assets") or {}).get("background-image") or {}
    if img.get("data_url"):                                                    # M4: a resolved sprite or texture, drawn (Unity's default scale mode stretches it)
        css["background-image"] = 'url("%s")' % img["data_url"]
        css.setdefault("background-size", "100% 100%")
        css.setdefault("background-repeat", "no-repeat")
    elif img.get("error") or (img and not img.get("data_url")):               # an unresolved image is a visible, labelled placeholder
        css["outline"] = "1px dashed #c0617a"
        css["outline-offset"] = "-1px"
    if "switch-branch-not-shown" in (node.get("layout_rules") or ()):
        css["display"] = "none"
    if "percent-main-axis-as-auto" in (node.get("layout_rules") or ()):       # set by percent_main_axis_rule: the game does not resolve this percentage
        css.pop("height", None)
    # a border with a width needs a style to show; USS draws it
    if any(k.startswith("border-") and k.endswith("-width") and v not in ("0", "0px") for k, v in css.items()):
        css["border-style"] = "solid"
    return css


def _declared(node, prop, default=None):
    d = node["computed"].get(prop)
    return d["value"] if d else default


SWITCH_TYPES = ("BindableSwitchElement", "SwitchElement")


def switch_branch_rule(top_nodes, choose=None):
    """A switch element shows ONE branch (plan section 7): the first, unless `choose` ({switch ordinal in depth-first order: branch index}) says otherwise (a capture tells which
    branch is live). The other branches are not drawn: they get `display:none` and `layout_rules: ["switch-branch-not-shown"]`, and the switch itself records `branches` and
    `shown`, so the render says what it left out. Returns the switches seen."""
    seen = []

    def walk(n):
        if n.get("type") in SWITCH_TYPES and len(n.get("children", [])) > 1:
            shown = (choose or {}).get(len(seen), 0)
            shown = shown if 0 <= shown < len(n["children"]) else 0
            n["branches"], n["shown"] = len(n["children"]), shown
            seen.append(n)
            for i, c in enumerate(n["children"]):
                if i != shown:
                    c["layout_rules"] = list(c.get("layout_rules", [])) + ["switch-branch-not-shown"]
        for c in n.get("children", []):
            walk(c)
    for t in top_nodes:
        walk(t)
    return seen


def _has_shrinkable_sibling(n, parent):
    """The two engines only differ when a sibling is in flow, content-sized (grow 0, no declared basis) and may shrink: CSS then takes pixels from it too."""
    for s in parent.get("children", []):
        if s is n or _declared(s, "position", "relative") == "absolute" or _declared(s, "display", "flex") == "none" or "switch-branch-not-shown" in (s.get("layout_rules") or ()):
            continue
        try:
            if float(_declared(s, "flex-grow", "0") or 0) == 0 and float(_declared(s, "flex-shrink", "1") or 0) > 0 and _declared(s, "flex-basis") in (None, "auto", ""):
                return True
        except ValueError:
            pass
    return False


def percent_main_axis_rule(top_nodes):
    """RENDER RULE (M0/M3, closed 2026-11-14 on two sources): a percentage main-axis size (`height: N%` in a column) on a child whose parent's height is not definite
    is treated as `auto`, so the child starts from its content (basis 0 once it grows) and takes what its siblings leave. It fires only where the two engines differ: a shrinkable, content-sized sibling is in flow. CSS would resolve the percentage against the
    flexed parent and then shrink the siblings; UI Toolkit (Yoga) does not.
    A parent is INDEFINITE (its height is still being flexed) when it grows inside a column (flex-grow > 0), or declares a percentage height and its own parent is
    indefinite. A parent with a px height, or with no declared height and no grow, resolves percentages as CSS does, so nothing changes there.
    A child with a declared flex-basis keeps its size (the basis wins in both engines).
    Sources (both read from the game, build 27.0.1.2503222): (1) LoansTile_4x2 `StreamedTable` (height 100%, grow 1) beside a shrinkable 24.4 px row in a 106.4 px column:
    the game gave the table 82.0 and the row 24.4, resolved flex-basis 0 (c2 in-game and capture styles-squad-overview-20261114-104418); CSS gave 19.8 for the row.
    (2) MessagesToolBlock `VisualElement#Messages` (height 100%, grow 1) beside a shrinkable `ButtonPanel` in the Inbox: resolved flex-basis 0 and 1213.9 high against
    CSS's basis of the whole parent (capture styles-d4-inbox-20261114-111746). Evidence: docs/evidence/phase9-m3-session-D-20261114.md.
    Returns the nodes changed; each gets `layout_rules: ["percent-main-axis-as-auto"]` and loses its `height` in `style`."""
    changed = []

    def grows(n, parent):
        try:
            return parent is not None and _declared(parent, "flex-direction", "column") in ("column", "column-reverse") and float(_declared(n, "flex-grow", "0") or 0) > 0
        except ValueError:
            return False

    def walk(n, parent, parent_indef):
        h = _declared(n, "height")
        if (parent is not None and parent_indef and _declared(parent, "flex-direction", "column") in ("column", "column-reverse")
                and h is not None and str(h).endswith("%") and _declared(n, "flex-basis") in (None, "auto", "") and _declared(n, "position", "relative") != "absolute"
                and _has_shrinkable_sibling(n, parent)):
            if "style" in n:
                n["style"].pop("height", None)                          # style_dict also honours layout_rules, so either order works
            n["layout_rules"] = ["percent-main-axis-as-auto"]
            changed.append(n)
        indef = grows(n, parent) or (h is not None and str(h).endswith("%") and parent_indef)
        for c in n.get("children", []):
            walk(c, n, indef)
    for t in top_nodes:
        walk(t, None, False)                                      # a top-level node sits in the stage, which has a definite size
    return changed


def placeholder_text(node):
    """The text a text element shows: its set text, else a zero-width space (no content known: bound or set from code). It gives the row its real line height without
    inventing a width; the width stays unknown. None for elements that show no text."""
    if node.get("type") not in TEXT_TYPES:
        return None
    a = node.get("attrs") or {}
    t = a.get("text")
    if t not in (None, ""):
        return str(t)
    # no text set: bound or set from code. The layout's own designer sample (`DebugDisplay`, e.g. "7 players injured") stands in, with the element's TextCase applied
    # (1 = upper case). It is the game's data, not invented, but it is a SAMPLE: its width approximates the delivered text's, it is not that text.
    s = a.get("DebugDisplay")
    if s not in (None, ""):
        return str(s).upper() if a.get("TextCase") == 1 else str(s)
    return "​"


def placeholder_kind(node):
    """How the element's text is labelled: "set" (the layout sets it), "sample" (the layout's designer sample stands in for bound text) or "empty" (nothing known, a zero-width
    space); None for elements that show no text. Every bound or unknown text is therefore labelled in the render, never passed off as data."""
    if node.get("type") not in TEXT_TYPES:
        return None
    a = node.get("attrs") or {}
    if node.get("delivered"):
        return "delivered"                                   # the text a capture recorded the game delivering to this element
    if a.get("text") not in (None, ""):
        return "set"
    return "sample" if a.get("DebugDisplay") not in (None, "") else "empty"


def font_label(node):
    """'ABCSocial Regular' for a node whose font definition resolved (M4): the family is named, the stand-in font draws it."""
    f = ((node.get("assets") or {}).get("-unity-font-definition")) or {}
    return ("%s %s" % (f.get("family"), f.get("weight"))) if f.get("family") else None


def _style(node, metrics=None):
    return ";".join("%s:%s" % kv for kv in style_dict(node, metrics).items())


def to_html(top_nodes, width, height, title="render"):
    nodes = flatten(top_nodes)
    index = {id(n): i for i, n in enumerate(nodes)}
    metrics = load_text_metrics()

    def draw(n):
        pt = placeholder_text(n)
        text = _html.escape(pt) if pt is not None else ""
        inner = text + "".join(draw(c) for c in n.get("children", []))
        kind, font = placeholder_kind(n), font_label(n)
        extra = ""
        if kind in ("sample", "empty"):
            extra += ' data-placeholder="%s" title="%s"' % (kind, "sample text from the layout (the designer's), not the delivered value" if kind == "sample" else "no text known: bound or set from code")
        if font and kind:
            extra += ' data-font="%s"' % _html.escape(font, quote=True)
        return '<div data-i="%d"%s style="%s">%s</div>' % (index[id(n)], extra, _html.escape(_style(n, metrics), quote=True), inner)

    body = "".join(draw(n) for n in top_nodes)
    script = ("<script>window.addEventListener('load',()=>{const r={};document.querySelectorAll('[data-i]').forEach(e=>{const b=e.getBoundingClientRect();"
              "r[e.dataset.i]=[b.left,b.top,b.width,b.height]});document.body.setAttribute('data-rects',JSON.stringify(r))})</script>")
    return ('<!doctype html><html><head><meta charset="utf-8"><title>%s</title><style>html,body{margin:0;padding:0;background:#fff}'
            'div{%s}[data-placeholder="sample"]{text-decoration:underline dotted #8a93a6;text-underline-offset:3px}#stage{position:relative;display:flex;flex-direction:column;width:%spx;height:%spx;overflow:hidden}</style></head>'
            '<body><div id="stage">%s</div>%s</body></html>' % (_html.escape(title), DEFAULTS, width, height, body, script)), nodes
