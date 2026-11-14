using System;
using System.Collections.Generic;
using System.Linq;
using UnityEngine;
using UnityEngine.UIElements;

namespace Crimson.Inspector
{
    // colour_source (spec 6): which declaration produces the element's colour.
    // Our own matcher: every sheet attached to the element or an ancestor, every complex selector tested right to left.
    internal static class ColourTrace
    {
        private sealed class Hit
        {
            public string Sheet, Selector, Value, Literal;
            public int Specificity, OwnerDepth, SheetIndex, Order;
        }

        public static object Explain(VisualElement el, string property)
        {
            if (property == "gradient")
                return new Dictionary<string, object> { ["label"] = Ui.Label(el), ["component"] = StyleProbe.Component(el),
                    ["rules"] = Rules(el, "--start-colour").Concat(Rules(el, "--end-colour")).Select(Shape).ToList(),
                    ["verdict"] = el.TryCast<SI.Bindable.SIGradient>() == null ? "not an SIGradient" :
                        (el.TryCast<SI.Bindable.SIGradient>().m_useCustomStyles ? "component reads --start/--end-colour from styles" : "component (code): useCustomStyles is false, style rules are ignored") };

            string resolved = ResolvedValue(el, property);
            var inline = StyleProbe.Inline(el);
            inline.TryGetValue(property, out object inlineValue);
            var hits = Rules(el, property);
            string verdict;
            if (inlineValue != null) verdict = "inline (set by code or a UXML style attribute)";
            else if (hits.Count > 0)
            {
                Hit w = hits[0];
                bool literalMatches = w.Literal != null && string.Equals(w.Literal, resolved, StringComparison.OrdinalIgnoreCase);
                verdict = "stylesheet:" + w.Sheet + " " + w.Selector + (w.Literal == null ? " (value is a variable)" : literalMatches ? "" : " (resolved value differs - something later overrides it)");
            }
            else if (IsInherited(property)) verdict = "inherited from an ancestor (no rule on this element)";
            else verdict = "default (no inline value, no matching rule)";
            return new Dictionary<string, object>
            {
                ["label"] = Ui.Label(el),
                ["property"] = property,
                ["resolved"] = resolved,
                ["inline"] = inlineValue,
                ["rules"] = hits.Select(Shape).ToList(),
                ["verdict"] = verdict,
                ["component"] = StyleProbe.Component(el),
            };
        }

        private static object Shape(Hit h) => new Dictionary<string, object>
            { ["sheet"] = h.Sheet, ["selector"] = h.Selector, ["specificity"] = h.Specificity, ["order"] = h.OwnerDepth + ":" + h.SheetIndex + ":" + h.Order, ["value"] = h.Value };

        private static bool IsInherited(string p) => p == "color";

        private static string ResolvedValue(VisualElement el, string p)
        {
            IResolvedStyle r = el.resolvedStyle;
            switch (p)
            {
                case "background-color": return Ui.Hex(r.backgroundColor);
                case "color": return Ui.Hex(r.color);
                case "border-top-color": return Ui.Hex(r.borderTopColor);
                case "border-right-color": return Ui.Hex(r.borderRightColor);
                case "border-bottom-color": return Ui.Hex(r.borderBottomColor);
                case "border-left-color": return Ui.Hex(r.borderLeftColor);
                case "-unity-background-image-tint-color": return Ui.Hex(r.unityBackgroundImageTintColor);
                default: return null;
            }
        }

        // All matching declarations of the property, winner first (higher specificity, then later sheet / rule).
        private static List<Hit> Rules(VisualElement el, string property)
        {
            var owners = new List<VisualElement>();
            for (VisualElement a = el; a != null; a = a.hierarchy.parent) owners.Add(a);
            owners.Reverse();                                  // root first: nearer sheets come later
            var hits = new List<Hit>();
            for (int depth = 0; depth < owners.Count; depth++)
            {
                var sheets = owners[depth].styleSheetList;
                if (sheets == null) continue;
                for (int si = 0; si < sheets.Count; si++)
                {
                    StyleSheet sheet = sheets[si];
                    if (sheet == null) continue;
                    foreach (StyleSheet s in Flatten(sheet)) Scan(s, el, property, depth, si, hits);
                }
            }
            return hits.OrderByDescending(h => h.Specificity).ThenByDescending(h => h.OwnerDepth).ThenByDescending(h => h.SheetIndex).ThenByDescending(h => h.Order).ToList();
        }

        private static IEnumerable<StyleSheet> Flatten(StyleSheet sheet)
        {
            var imports = sheet.flattenedRecursiveImports;
            if (imports != null) for (int i = 0; i < imports.Count; i++) if (imports[i] != null) yield return imports[i];
            yield return sheet;
        }

        private static void Scan(StyleSheet sheet, VisualElement el, string property, int depth, int sheetIndex, List<Hit> hits)
        {
            var rules = sheet.rules;
            if (rules == null) return;
            for (int ri = 0; ri < rules.Length; ri++)
            {
                StyleRule rule = rules[ri];
                StyleProperty decl = null;
                var props = rule.properties;
                if (props == null) continue;
                for (int k = 0; k < props.Length; k++) if (props[k] != null && props[k].name == property) decl = props[k];
                if (decl == null) continue;
                var complexes = rule.complexSelectors;
                if (complexes == null) continue;
                for (int ci = 0; ci < complexes.Length; ci++)
                {
                    StyleComplexSelector cx = complexes[ci];
                    if (cx == null || !Matches(cx, el)) continue;
                    string literal;
                    hits.Add(new Hit { Sheet = sheet.name, Selector = SelectorText(cx), Specificity = cx.specificity, OwnerDepth = depth,
                        SheetIndex = sheetIndex, Order = cx.orderInStyleSheet, Value = ValueText(sheet, decl, out literal), Literal = literal });
                }
            }
        }

        // Right-to-left: the last compound must match the element, earlier ones its parent / an ancestor.
        private static bool Matches(StyleComplexSelector cx, VisualElement el)
        {
            var sels = cx.selectors;
            if (sels == null || sels.Length == 0) return false;
            int i = sels.Length - 1;
            if (!Compound(sels[i], el)) return false;
            VisualElement cur = el;
            while (i > 0)
            {
                string rel = sels[i].previousRelationship.ToString();
                StyleSelector want = sels[i - 1];
                if (rel == "Child")
                {
                    cur = cur.hierarchy.parent;
                    if (cur == null || !Compound(want, cur)) return false;
                }
                else
                {
                    cur = cur.hierarchy.parent;
                    while (cur != null && !Compound(want, cur)) cur = cur.hierarchy.parent;
                    if (cur == null) return false;
                }
                i--;
            }
            return true;
        }

        private static bool Compound(StyleSelector sel, VisualElement el)
        {
            int states = StyleProbe.Pseudo(el);
            int need = sel.pseudoStateMask, forbid = sel.negatedPseudoStateMask;
            if (need != -1 && need != 0 && (states & need) != need) return false;
            if (forbid != -1 && forbid != 0 && (states & forbid) != 0) return false;
            var parts = sel.parts;
            for (int i = 0; i < parts.Length; i++)
            {
                StyleSelectorPart part = parts[i];
                string kind = part.type.ToString();
                string v = part.value;
                switch (kind)
                {
                    case "Wildcard": break;
                    case "Type": if (Ui.TypeName(el) != v) return false; break;
                    case "Class": if (!el.ClassListContains(v)) return false; break;
                    case "ID": if (el.name != v) return false; break;
                    case "PseudoClass": break;          // covered by the masks above
                    default: return false;              // predicates / unknown: be strict
                }
            }
            return true;
        }

        // Capture sheet content (0.3.1): the selector texts of one rule, joined the way skin_editor.index_styles stores them (", ").
        internal static string RuleSelectors(StyleRule rule)
        {
            var cs = rule.complexSelectors;
            if (cs == null) return "";
            var l = new List<string>();
            for (int i = 0; i < cs.Length; i++) if (cs[i] != null) l.Add(SelectorText(cs[i]));
            return string.Join(", ", l);
        }

        internal static string DeclText(StyleSheet sheet, StyleProperty decl) { string lit; return ValueText(sheet, decl, out lit); }

        private static string SelectorText(StyleComplexSelector cx)
        {
            var sels = cx.selectors;
            var sb = new System.Text.StringBuilder();
            for (int i = 0; i < sels.Length; i++)
            {
                if (i > 0) sb.Append(sels[i].previousRelationship.ToString() == "Child" ? " > " : " ");
                var parts = sels[i].parts;
                for (int k = 0; k < parts.Length; k++)
                {
                    string kind = parts[k].type.ToString(), v = parts[k].value;
                    sb.Append(kind == "Class" ? "." + v : kind == "ID" ? "#" + v : kind == "PseudoClass" ? ":" + v : kind == "Wildcard" ? "*" : v);
                }
            }
            return sb.ToString();
        }

        private static string ValueText(StyleSheet sheet, StyleProperty decl, out string literal)
        {
            literal = null;
            var parts = new List<string>();
            var vals = decl.values;
            for (int i = 0; i < vals.Length; i++)
            {
                StyleValueHandle h = vals[i];
                string t = h.valueType.ToString();
                try
                {
                    if (t == "Color") { string c = Ui.Hex(sheet.ReadColor(h)); parts.Add(c); literal ??= c; }
                    else if (t == "Variable") parts.Add("var(" + sheet.ReadVariable(h) + ")");
                    else if (t == "Function") { i++; }                       // var( argc ) - the name follows
                    else if (t == "Keyword") parts.Add(sheet.ReadKeyword(h).ToString().ToLowerInvariant());
                    else if (t == "Float") parts.Add(sheet.ReadFloat(h).ToString(System.Globalization.CultureInfo.InvariantCulture));
                    else parts.Add("<" + t + ">");
                }
                catch (Exception e) { parts.Add("<" + t + ": " + e.Message + ">"); }
            }
            return string.Join(" ", parts);
        }
    }
}
