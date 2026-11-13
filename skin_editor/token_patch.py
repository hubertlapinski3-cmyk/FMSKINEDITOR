#!/usr/bin/env python3
"""token_patch.py TOKENS.json OUT_DIR BUNDLE... — FM27 Tactical Navy patcher.

Implements FM27_SKIN_BRIEF.md section 3 and NewTask.txt:
  * rewrites :root (and unity-theme-env-variables) custom properties from
    `tokens` in every stylesheet except `skip_sheets`;
  * recolours literal colours via `literal_map` (RGB triples, alpha kept);
  * flattens gradients: --end-colour := --start-colour per rule;
  * `rename_classes`: renames selector classes in EVERY sheet, including
    competition sheets (nav-on-light / nav-on-dark -> dead classes);
  * `append_rules_by_sheet`: appends new rules (mini-USS) to the named sheet.

Value syntax: "#RRGGBB" | "rgba(r, g, b, a)" | "var(--x)" | "<n>px|%" | number
| keyword. FM27 serialization notes (verified against vanilla data):
  m_ValueType: 1 keyword->strings, 2 float->floats, 3 dimension->dimensions
  (units: 1=px, 2=%), 4 colour->colors, 6 asset, 8 variable name->strings,
  10 function (1=var; encoded [10:1, 2:argc, 8:name]).
  Selector part m_Type: 1 wildcard, 2 element type, 3 class,
  4 pseudo-class, 6 id (#name). Bare words encode as element types (2).
  m_Specificity = 1 + 100*ids + 10*(classes + pseudo-classes) + 1*element types.
"""
import json
import os
import re
import sys

# skin_editor: vendored verbatim from tools/token_patch.py; only change: UnityPy is imported inside main()

VT_KEYWORD, VT_FLOAT, VT_DIM, VT_COLOR = 1, 2, 3, 4
VT_ASSET, VT_VARNAME, VT_FUNC = 6, 8, 10
# FM27 selector part types (verified, continue-skin.md section 4):
# 1 wildcard, 2 element type (SIGradient), 3 class, 4 pseudo-class, 6 id
P_WILDCARD, P_ELEMENT, P_CLASS, P_PSEUDO, P_ID = 1, 2, 3, 4, 6

UNITS = {"px": 1, "%": 2, "deg": 3, "em": 4, "rem": 5, "s": 6, "ms": 7}

# Built-in USS property ids (verified against vanilla FM27 data via
# scripts/prop_crosscheck.py: .clubcolours-border, .navigation-chip and
# .tile-mockups-navigation-core-primary-hi-res all decode correctly;
# width 131105 occurs 2694x, align-items 131073 2472x in vanilla)
PROP_TABLE = {
    "rotate": 327680, "scale": 327681, "transform-origin": 327682, "translate": 327683,
    "color": 65536, "font-size": 65537, "letter-spacing": 65538,
    "text-shadow": 65539, "-unity-font-definition": 65542,
    "-unity-font": 65542, "-unity-font-style": 65543,
    "-unity-text-align": 65546, "visibility": 65551, "white-space": 65552,
    "align-content": 131072, "align-items": 131073, "align-self": 131074,
    "border-bottom-width": 131076, "border-left-width": 131077,
    "border-right-width": 131078, "border-top-width": 131079,
    "bottom": 131080, "display": 131081, "flex-basis": 131082,
    "flex-direction": 131083, "flex-grow": 131084, "flex-shrink": 131085,
    "flex-wrap": 131086, "height": 131087, "justify-content": 131088,
    "left": 131089, "margin-bottom": 131090, "margin-left": 131091,
    "margin-right": 131092, "margin-top": 131093, "max-height": 131094,
    "max-width": 131095, "min-height": 131096, "min-width": 131097,
    "padding-bottom": 131098, "padding-left": 131099,
    "padding-right": 131100, "padding-top": 131101, "position": 131102,
    "right": 131103, "top": 131104, "width": 131105,
    "border-color": 262146, "border-radius": 262147, "border-width": 262148,
    "flex": 262149, "margin": 262150, "padding": 262151,
    "transition": 262152,
    "background-color": 458752, "background-image": 458753,
    "border-bottom-color": 458758, "border-left-color": 458761,
    "border-right-color": 458762, "border-top-color": 458763,
    "opacity": 458767, "overflow": 458768,
    "text-overflow": 196609, "-unity-background-image-tint-color": 196610,
}


def parse_rgb255(s):
    s = s.strip().lstrip("#")
    if len(s) in (6, 8) and "," not in s:
        return int(s[0:2], 16), int(s[2:4], 16), int(s[4:6], 16)
    parts = [p.strip() for p in s.split(",")]
    return int(float(parts[0])), int(float(parts[1])), int(float(parts[2]))


# Crimson fix 2026-11-03: VT 1 is an index into Unity's fixed global-keyword
# list (CONTINUE-SKIN sec 4; vanilla: display none = vt1 6, width auto = vt1 2).
# Every other identifier (nowrap, ellipsis, center, middle-right, hidden,
# absolute, column ...) is an enum string, VT 7 (vanilla: 1612x align-items
# center as vt7). The TN version wrote all identifiers as VT 1 -> string index.
GLOBAL_KEYWORDS = {"inherit": 0, "initial": 1, "auto": 2, "unset": 3, "none": 6}
VT_ENUM = 7


def parse_token_value(v):
    v = v.strip()
    if v.startswith("var("):
        return ("var", v[4:-1].strip())
    if v.startswith("#"):
        h = v[1:]
        if len(h) == 8:  # Crimson fix: #RRGGBBAA (guide 2.7)
            r, g, b = parse_rgb255(h)
            return ("color", (r / 255, g / 255, b / 255, int(h[6:8], 16) / 255))
        r, g, b = parse_rgb255(v)
        return ("color", (r / 255, g / 255, b / 255, 1.0))
    m = re.match(r"rgba?\(([^)]+)\)", v)
    if m:
        parts = [p.strip() for p in m.group(1).split(",")]
        r, g, b = (int(float(x)) for x in parts[:3])
        a = float(parts[3]) if len(parts) > 3 else 1.0
        return ("color", (r / 255, g / 255, b / 255, a))
    m = re.match(r"^(-?[\d.]+)\s*(px|%|deg|em|rem|s|ms)$", v)
    if m:
        return ("dim", float(m.group(1)), UNITS[m.group(2)])
    if re.match(r"^-?[\d.]+$", v):
        return ("float", float(v))
    return ("keyword", v)


INV_PROP = {}
for _k, _v in PROP_TABLE.items():
    INV_PROP.setdefault(_v, _k)
INV_PROP[65542] = "-unity-font-definition"


def _sel_text(rule):
    out = []
    for cs in rule["m_ComplexSelectors"]:
        s = ""
        for sel in cs["m_Selectors"]:
            rel = sel.get("m_PreviousRelationship", 0)
            s += " > " if rel == 1 else " " if rel == 2 else ""
            for p in sel["m_Parts"]:
                t, v = p["m_Type"], p["m_Value"]
                s += {1: "*", 3: "." + v, 4: ":" + v, 6: "#" + v}.get(t, v)
        out.append(s.strip())
    return ", ".join(out)


def parse_selector(sel):
    """'A > B, C' -> [chain, ...]; chain = [(rel, [(partType, value), ...])].
    rel: 0 first part, 1 child ( > ), 2 descendant (space)."""
    branches = []
    for branch in sel.split(","):
        branch = branch.strip()
        if not branch:
            continue
        # tokenise into words / combinator markers
        toks = []
        i = 0
        while i < len(branch):
            c = branch[i]
            if c == ">":
                toks.append((">",))
                i += 1
                continue
            if c == " ":
                if toks and toks[-1] != (">",):
                    toks.append((" ",))
                i += 1
                continue
            j = i
            while j < len(branch) and branch[j] not in " >":
                j += 1
            toks.append(("w", branch[i:j]))
            i = j
        chain = []
        parts = []
        rel = 0
        for tok in toks:
            if tok[0] == "w":
                val = tok[1]
                k = 0
                while k < len(val):
                    c = val[k]
                    if c in ".#:":
                        stops = [val.find(ch, k + 1) for ch in ".#:"]
                        stops = [s for s in stops if s != -1]
                        end = min(stops) if stops else len(val)
                        ptype = {".": P_CLASS, "#": P_ID, ":": P_PSEUDO}[c]
                        parts.append((ptype, val[k + 1:end]))
                        k = end
                    else:
                        stops = [val.find(ch, k) for ch in ".#:"]
                        stops = [s for s in stops if s != -1]
                        end = min(stops) if stops else len(val)
                        word = val[k:end]
                        # Crimson: '*' is the wildcard part (m_Type 1, m_Value '*', as vanilla)
                        parts.append((P_WILDCARD, "*") if word == "*" else (P_ELEMENT, word))
                        k = end
            else:
                if parts:
                    chain.append((rel, parts))
                    parts = []
                    rel = 1 if tok[0] == ">" else 2
                elif tok[0] == ">" and chain:
                    # Crimson fix: "A > B" tokenises as A, ' ', '>' - the '>' after the
                    # space must still make the relationship child (TN made it descendant)
                    rel = 1
        if parts:
            chain.append((rel, parts))
        if chain:
            branches.append(chain)
    return branches


def chain_key(chain):
    """A parsed chain [(rel, [(type, value)])] as a hashable key."""
    return tuple((rel, tuple((t, v) for t, v in parts)) for rel, parts in chain)


def rule_key(rule):
    """The set of complex-selector keys of a decoded rule: two rules with the same key have the same selector list."""
    return frozenset(tuple((s.get("m_PreviousRelationship", 0), tuple((p["m_Type"], p["m_Value"]) for p in s["m_Parts"]))
                           for s in cs["m_Selectors"]) for cs in rule.get("m_ComplexSelectors", []))


def selector_key(text):
    return frozenset(chain_key(c) for c in parse_selector(text))


def prop_matches(p, name):
    """Does the decoded property p have the USS name `name`?"""
    if name.startswith("--"):
        return p.get("m_CustomName") == name
    pid = PROP_TABLE.get(name)
    return pid is not None and not p.get("m_CustomName") and p.get("m_Id") == pid


def specificity(chain):
    # continue-skin.md section 4: 1 + 100*ids + 10*(classes + pseudo-classes)
    # + 1*element types (wildcards add nothing)
    ids = classes = elements = 0
    for _rel, parts in chain:
        for t, _v in parts:
            if t == P_ID:
                ids += 1
            elif t in (P_CLASS, P_PSEUDO):
                classes += 1
            elif t == P_ELEMENT:
                elements += 1
    return 1 + 100 * ids + 10 * classes + elements


class SheetPatcher:
    def __init__(self, tree, spec, font_ids=None):
        self.t = tree
        self.tokens = spec["tokens"]
        lit = {}
        for k, v in spec["literal_map"].items():
            lit[parse_rgb255(k.replace("#", ""))] = parse_rgb255(v.replace("#", ""))
        self.lit = lit
        self.skip = set(spec["skip_sheets"])
        self.flatten = spec.get("flatten_gradients", True)
        self.renames = spec.get("rename_classes", {})
        self.font_tokens = spec.get("font_tokens", {})
        self.font_ids = font_ids or {}
        self.count_tokens = 0
        self.count_literals = 0
        self.count_gradients = 0
        self.count_renames = 0
        self.count_appended = 0
        self.count_edited = 0
        self.found_tokens = set()
        self.literal_hits = []

    # -- array append helpers -------------------------------------------
    def _add_color(self, rgb01):
        self.t["colors"].append({"r": rgb01[0], "g": rgb01[1],
                                 "b": rgb01[2], "a": rgb01[3]})
        return len(self.t["colors"]) - 1

    def _add_dim(self, value, unit):
        self.t["dimensions"].append({"value": value, "unit": unit})
        return len(self.t["dimensions"]) - 1

    def _add_float(self, f):
        self.t["floats"].append(f)
        return len(self.t["floats"]) - 1

    def _add_string(self, s):
        # Crimson: reuse an identical existing string (vanilla shares them too),
        # so an encoded value is byte-identical to vanilla's own handle
        try:
            return self.t["strings"].index(s)
        except ValueError:
            self.t["strings"].append(s)
            return len(self.t["strings"]) - 1

    def _encode_keyword(self, word):
        if word in GLOBAL_KEYWORDS:
            return [{"m_ValueType": VT_KEYWORD, "valueIndex": GLOBAL_KEYWORDS[word]}]
        return [{"m_ValueType": VT_ENUM, "valueIndex": self._add_string(word)}]

    def _encode(self, v):
        # USS shorthand: a declaration can hold several space-separated values (scale: 0.88 0.88,
        # transform-origin: left top) -> one handle per token. Values with parentheses (rgba(...),
        # var(...)) are never split.
        if " " in v and "(" not in v:
            out = []
            for tok in v.split():
                out.extend(self._encode(tok))
            return out
        kind = parse_token_value(v)
        if kind[0] == "color":
            return [{"m_ValueType": VT_COLOR, "valueIndex": self._add_color(kind[1])}]
        if kind[0] == "dim":
            return [{"m_ValueType": VT_DIM, "valueIndex": self._add_dim(kind[1], kind[2])}]
        if kind[0] == "float":
            return [{"m_ValueType": VT_FLOAT, "valueIndex": self._add_float(kind[1])}]
        if kind[0] == "keyword":
            return self._encode_keyword(kind[1])
        if kind[0] == "var":
            return [
                {"m_ValueType": VT_FUNC, "valueIndex": 1},
                {"m_ValueType": VT_FLOAT, "valueIndex": self._add_float(1.0)},
                {"m_ValueType": VT_VARNAME, "valueIndex": self._add_string(kind[1])},
            ]
        raise ValueError(v)

    # -- passes ----------------------------------------------------------
    def _is_token_rule(self, rule):
        for cs in rule["m_ComplexSelectors"]:
            for sel in cs["m_Selectors"]:
                for p in sel["m_Parts"]:
                    if p["m_Type"] == 4 and p["m_Value"] == "root":
                        return True
                    if p["m_Type"] == P_CLASS and p["m_Value"] == "unity-theme-env-variables":
                        return True
        return False

    def _rename_selectors(self):
        for rule in self.t["m_Rules"]:
            for cs in rule["m_ComplexSelectors"]:
                for sel in cs["m_Selectors"]:
                    for p in sel["m_Parts"]:
                        if p["m_Type"] == P_CLASS and p["m_Value"] in self.renames:
                            p["m_Value"] = self.renames[p["m_Value"]]
                            self.count_renames += 1

    def patch(self):
        name = self.t.get("m_Name")
        self._rename_selectors()
        if name in self.skip:
            return "skipped"
        for rule in self.t["m_Rules"]:
            props = rule["m_Properties"]
            if self._is_token_rule(rule):
                for prop in props:
                    self._patch_font_token(prop)
                    self._patch_token(prop)
            for prop in props:
                self._patch_literals(prop, rule)
            if self.flatten:
                self._flatten_rule(props)
        return "patched"

    def _patch_font_token(self, prop):
        n = prop.get("m_CustomName")
        if n not in self.font_tokens:
            return
        target = self.font_ids.get(self.font_tokens[n])
        if target is None:
            return
        # find the external fileID this sheet uses for the fonts bundle:
        # any existing asset PPr whose pathID is one of the known SDF assets
        fid = None
        for rule in self.t["m_Rules"]:
            for p in rule["m_Properties"]:
                for h in p["m_Values"]:
                    if h.get("m_ValueType") == VT_ASSET:
                        a = self.t["assets"][h["valueIndex"]]
                        if a.get("m_PathID") in self.font_ids.values():
                            fid = a.get("m_FileID")
                            break
            if fid is not None:
                break
        if fid is None:
            print(f"  WARNING: no fonts-bundle reference found in "
                  f"{self.t.get('m_Name')} for {n}")
            return
        self.t["assets"].append({"m_FileID": fid, "m_PathID": target})
        prop["m_Values"] = [{"m_ValueType": VT_ASSET,
                             "valueIndex": len(self.t["assets"]) - 1}]
        self.count_fonts = getattr(self, "count_fonts", 0) + 1

    def _patch_token(self, prop):
        n = prop.get("m_CustomName")
        if n not in self.tokens:
            return
        target = self.tokens[n]
        kind = parse_token_value(target)
        self.found_tokens.add(n)
        if kind[0] == "color":
            idx = self._add_color(kind[1])
            prop["m_Values"] = [{"m_ValueType": VT_COLOR, "valueIndex": idx}]
        elif kind[0] == "dim":
            idx = self._add_dim(kind[1], kind[2])
            prop["m_Values"] = [{"m_ValueType": VT_DIM, "valueIndex": idx}]
        elif kind[0] == "float":
            idx = self._add_float(kind[1])
            prop["m_Values"] = [{"m_ValueType": VT_FLOAT, "valueIndex": idx}]
        elif kind[0] == "keyword":
            prop["m_Values"] = self._encode_keyword(kind[1])
        else:  # var
            fidx = self._add_float(1.0)
            sidx = self._add_string(kind[1])
            prop["m_Values"] = [
                {"m_ValueType": VT_FUNC, "valueIndex": 1},
                {"m_ValueType": VT_FLOAT, "valueIndex": fidx},
                {"m_ValueType": VT_VARNAME, "valueIndex": sidx},
            ]
        self.count_tokens += 1

    def _patch_literals(self, prop, rule=None):
        for h in prop["m_Values"]:
            if h["m_ValueType"] != VT_COLOR:
                continue
            c = self.t["colors"][h["valueIndex"]]
            key = tuple(round(max(0.0, min(1.0, float(c[k]))) * 255)
                        for k in ("r", "g", "b"))
            if key not in self.lit:
                continue
            new = self.lit[key]
            a = float(c["a"])
            h["valueIndex"] = self._add_color(
                (new[0] / 255, new[1] / 255, new[2] / 255, a))
            self.count_literals += 1
            # Crimson: per-hit record for the build report
            self.literal_hits.append({
                "sheet": self.t.get("m_Name"),
                "selector": _sel_text(rule) if rule else "?",
                "property": prop.get("m_CustomName") or INV_PROP.get(prop.get("m_Id"), f"prop-{prop.get('m_Id')}"),
                "from": "#%02X%02X%02X" % key, "to": "#%02X%02X%02X" % new,
                "alpha": round(a, 3)})

    def _flatten_rule(self, props):
        by_name = {}
        for p in props:
            n = p.get("m_CustomName")
            if n:
                by_name.setdefault(n, p)
        start = by_name.get("--start-colour")
        end = by_name.get("--end-colour")
        if start and end and start is not end:
            end["m_Values"] = [dict(h) for h in start["m_Values"]]
            self.count_gradients += 1

    # -- appended rules ---------------------------------------------------
    def append_rule(self, spec_rule):
        rule_idx = len(self.t["m_Rules"])
        props = []
        for pname, pval in spec_rule["props"].items():
            vals = self._encode(str(pval))
            if pname.startswith("--"):
                props.append({"m_Id": -1, "m_CustomName": pname, "m_Line": 0, "m_Values": vals})
            else:
                pid = PROP_TABLE.get(pname)
                if pid is None:
                    raise ValueError(f"unknown property: {pname}")
                props.append({"m_Id": pid, "m_CustomName": "", "m_Line": 0, "m_Values": vals})
        complexes = []
        for chain in parse_selector(spec_rule["selector"]):
            selectors = []
            for rel, parts in chain:
                selectors.append({
                    "m_Parts": [{"m_Type": t, "m_Value": v} for t, v in parts],
                    "m_PreviousRelationship": rel,
                })
            complexes.append({
                "m_Specificity": specificity(chain),
                "m_Selectors": selectors,
                "ruleIndex": rule_idx,
            })
        self.t["m_Rules"].append({"m_ComplexSelectors": complexes,
                                  "m_Properties": props, "line": 0})
        self.count_appended += 1

    # -- in-place edits of the game's own rules ---------------------------
    def edit_rule(self, e):
        """e: {op: replace|remove, selector, props (replace), remove (remove: property names; empty = every declaration)}.
        Acts on every rule whose selector list is exactly e['selector']. Replace sets the listed properties in place (adding
        the ones the rule lacks); remove drops them. The rule keeps its place, selectors and specificity, and the value pools
        only grow. Returns (rules hit, declarations changed)."""
        want = selector_key(e["selector"])
        hits = changed = 0
        for rule in self.t["m_Rules"]:
            if rule_key(rule) != want:
                continue
            hits += 1
            props = rule["m_Properties"]
            if e["op"] == "remove":
                names = e.get("remove") or []
                keep = [] if not names else [p for p in props if not any(prop_matches(p, n) for n in names)]
                changed += len(props) - len(keep)
                rule["m_Properties"] = keep
                continue
            changed += self.set_props(rule, e["props"])
        self.count_edited += changed
        return hits, changed

    def set_props(self, rule, new_props):
        """Set {property: value text} on one decoded rule in place (an existing declaration gets the new value, a missing one is added at
        the end). The value pools only grow. Returns the number of declarations set."""
        props = rule["m_Properties"]
        for pname, pval in new_props.items():
            if not pname.startswith("--") and pname not in PROP_TABLE:
                raise ValueError(f"unknown property: {pname}")
            vals = self._encode(str(pval))
            same = [p for p in props if prop_matches(p, pname)]
            for p in same:
                p["m_Values"] = [dict(h) for h in vals]
            if not same:
                props.append({"m_Id": -1 if pname.startswith("--") else PROP_TABLE[pname],
                              "m_CustomName": pname if pname.startswith("--") else "", "m_Line": 0, "m_Values": vals})
        return len(new_props)

    def append_props_rule(self, new_props):
        """A new rule without selectors (a layout's inline style) holding the properties; returns its index."""
        rule = {"m_ComplexSelectors": [], "m_Properties": [], "line": -1}
        self.t["m_Rules"].append(rule)
        self.set_props(rule, new_props)
        self.count_appended += 1
        return len(self.t["m_Rules"]) - 1


def main():
    import UnityPy
    if len(sys.argv) < 4:
        print(__doc__)
        return 2
    spec_path, out_dir = sys.argv[1], sys.argv[2]
    # Crimson ground rule 2: never write into the FM27 install folder
    if "football manager 27" in os.path.abspath(out_dir).lower():
        print(f"REFUSED: output path is inside the FM27 install: {out_dir}")
        return 3
    spec = json.load(open(spec_path, encoding="utf-8"))
    os.makedirs(out_dir, exist_ok=True)
    literal_hits = []
    append_map = spec.get("append_rules_by_sheet", {})
    font_ids = {}
    fonts_bundle = spec.get("fonts_bundle")
    if spec.get("font_tokens") and fonts_bundle:
        fenv = UnityPy.load(fonts_bundle)
        for obj in fenv.objects:
            if obj.type.name == "MonoBehaviour" and obj.peek_name() and obj.peek_name().endswith(" SDF"):
                font_ids[obj.peek_name()] = obj.path_id
        print(f"font assets resolved: {len(font_ids)}")
    total = {"tokens": 0, "literals": 0, "gradients": 0,
             "renames": 0, "appended": 0, "fonts": 0}
    found_tokens = set()
    for bundle_path in sys.argv[3:]:
        env = UnityPy.load(bundle_path)
        for obj in env.objects:
            if obj.type.name != "MonoBehaviour":
                continue
            tree = obj.read_typetree()
            if "m_Rules" not in tree:
                continue
            sp = SheetPatcher(tree, spec, font_ids)
            status = sp.patch()
            name = tree.get("m_Name")
            if status == "skipped":
                if sp.count_renames:
                    print(f"  {name}: class renames={sp.count_renames} (sheet skipped otherwise)")
            elif append_map.get(name):
                for spec_rule in append_map[name]:
                    sp.append_rule(spec_rule)
            if sp.count_tokens or sp.count_literals or sp.count_gradients \
                    or sp.count_renames or sp.count_appended:
                print(f"  {name}: tokens={sp.count_tokens} literals={sp.count_literals} "
                      f"gradients={sp.count_gradients} renames={sp.count_renames} "
                      f"appended={sp.count_appended} font_tokens={getattr(sp, 'count_fonts', 0)}")
            obj.save_typetree(tree)
            total["tokens"] += sp.count_tokens
            total["literals"] += sp.count_literals
            total["gradients"] += sp.count_gradients
            total["renames"] += sp.count_renames
            total["appended"] += sp.count_appended
            total["fonts"] += getattr(sp, "count_fonts", 0)
            found_tokens |= sp.found_tokens
            literal_hits += sp.literal_hits
        base = re.sub(r"^[0-9a-f]{64}", "", os.path.basename(bundle_path))
        env.save(pack="original", out_path=out_dir)
        print(f"{os.path.basename(bundle_path)} -> {os.path.join(out_dir, base)}")
    missing = sorted(set(spec["tokens"]) - found_tokens)
    with open(os.path.join(out_dir, "token_patch-report.json"), "w", encoding="utf-8") as f:
        json.dump({"totals": total, "tokens_not_found": missing,
                   "literal_hits": literal_hits}, f, indent=1)
    print(f"TOTAL: token definitions rewritten={total['tokens']}, "
          f"literal colours recoloured={total['literals']}, "
          f"gradient pairs flattened={total['gradients']}, "
          f"class renames={total['renames']}, rules appended={total['appended']}, "
          f"font token repointed={total['fonts']}")
    if missing:
        print("TOKENS NOT FOUND:")
        for m in missing:
            print("  " + m)
    return 0


if __name__ == "__main__":
    sys.exit(main())
