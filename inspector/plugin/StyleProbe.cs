using System;
using System.Collections.Generic;
using UnityEngine;
using UnityEngine.UIElements;

namespace Crimson.Inspector
{
    // get_styles (spec 6): resolved values, inline values, attached sheets, component colours.
    internal static class StyleProbe
    {
        public static object Describe(VisualElement el)
        {
            IResolvedStyle r = el.resolvedStyle;
            var resolved = new Dictionary<string, object>
            {
                ["background-color"] = Ui.Hex(r.backgroundColor),
                ["color"] = Ui.Hex(r.color),
                ["border-top-color"] = Ui.Hex(r.borderTopColor),
                ["border-right-color"] = Ui.Hex(r.borderRightColor),
                ["border-bottom-color"] = Ui.Hex(r.borderBottomColor),
                ["border-left-color"] = Ui.Hex(r.borderLeftColor),
                ["border-widths"] = new[] { Ui.Num(r.borderTopWidth), Ui.Num(r.borderRightWidth), Ui.Num(r.borderBottomWidth), Ui.Num(r.borderLeftWidth) },
                ["-unity-background-image-tint-color"] = Ui.Hex(r.unityBackgroundImageTintColor),
                ["opacity"] = Ui.Num(r.opacity),
                ["display"] = r.display.ToString(),
                ["visibility"] = r.visibility.ToString(),
                ["width"] = Ui.Num(r.width),
                ["height"] = Ui.Num(r.height),
                ["font-size"] = Ui.Num(r.fontSize),
                // 0.2.2: layout properties for the Figma export (read-only, additive)
                ["flex-direction"] = r.flexDirection.ToString(),
                ["flex-wrap"] = r.flexWrap.ToString(),
                ["flex-grow"] = Ui.Num(r.flexGrow),
                ["flex-shrink"] = Ui.Num(r.flexShrink),
                ["align-items"] = r.alignItems.ToString(),
                ["align-self"] = r.alignSelf.ToString(),
                ["align-content"] = r.alignContent.ToString(),
                ["justify-content"] = r.justifyContent.ToString(),
                ["position"] = r.position.ToString(),
                ["padding"] = new[] { Ui.Num(r.paddingTop), Ui.Num(r.paddingRight), Ui.Num(r.paddingBottom), Ui.Num(r.paddingLeft) },
                ["margin"] = new[] { Ui.Num(r.marginTop), Ui.Num(r.marginRight), Ui.Num(r.marginBottom), Ui.Num(r.marginLeft) },
                ["border-radius"] = new[] { Ui.Num(r.borderTopLeftRadius), Ui.Num(r.borderTopRightRadius), Ui.Num(r.borderBottomRightRadius), Ui.Num(r.borderBottomLeftRadius) },
                ["offsets"] = new[] { Ui.Num(r.top), Ui.Num(r.right), Ui.Num(r.bottom), Ui.Num(r.left) },
                ["text-align"] = r.unityTextAlign.ToString(),
                ["font-style"] = r.unityFontStyleAndWeight.ToString(),
            };
            return new Dictionary<string, object>
            {
                ["label"] = Ui.Label(el),
                ["classes"] = Ui.Classes(el),
                ["pseudo"] = Pseudo(el),
                ["resolved"] = resolved,
                ["inline"] = Inline(el),
                ["sheets"] = SheetChain(el),
                ["component"] = Component(el),
            };
        }

        public static int Pseudo(VisualElement el) => (int)el.m_PseudoStates;

        // Inline style values set by code or UXML attributes (keyword Null = not set inline).
        public static Dictionary<string, object> Inline(VisualElement el)
        {
            IStyle s = el.style;
            var d = new Dictionary<string, object>();
            void C(string n, StyleColor v) { if (v.keyword != StyleKeyword.Null) d[n] = v.keyword == StyleKeyword.Undefined ? Ui.Hex(v.value) : v.keyword.ToString(); }
            C("background-color", s.backgroundColor);
            C("color", s.color);
            C("border-top-color", s.borderTopColor);
            C("border-right-color", s.borderRightColor);
            C("border-bottom-color", s.borderBottomColor);
            C("border-left-color", s.borderLeftColor);
            C("-unity-background-image-tint-color", s.unityBackgroundImageTintColor);
            if (s.opacity.keyword != StyleKeyword.Null) d["opacity"] = s.opacity.value;
            if (s.display.keyword != StyleKeyword.Null) d["display"] = s.display.value.ToString();
            if (s.visibility.keyword != StyleKeyword.Null) d["visibility"] = s.visibility.value.ToString();
            return d;
        }

        public static List<string> SheetNames(VisualElement el)
        {
            var names = new List<string>();
            var list = el.styleSheetList;
            if (list != null) for (int i = 0; i < list.Count; i++) names.Add(list[i] != null ? list[i].name : "(null)");
            return names;
        }

        // Nearest first: the element, then each ancestor that carries sheets.
        public static List<object> SheetChain(VisualElement el)
        {
            var chain = new List<object>();
            int up = 0;
            for (VisualElement a = el; a != null; a = a.hierarchy.parent, up++)
            {
                var names = SheetNames(a);
                if (names.Count > 0) chain.Add(new Dictionary<string, object> { ["owner"] = Ui.Label(a), ["levelsUp"] = up, ["sheets"] = names });
            }
            return chain;
        }

        public static Dictionary<string, object> Component(VisualElement el)
        {
            var d = new Dictionary<string, object> { ["type"] = Ui.TypeName(el) };
            var g = el.TryCast<SI.Bindable.SIGradient>();
            if (g != null)
            {
                d["startColour"] = Ui.Hex(g.m_startColour);
                d["endColour"] = Ui.Hex(g.m_endColour);
                d["useCustomStyles"] = g.m_useCustomStyles;
                d["bindingResolved"] = g.m_bindingResolved;
                d["direction"] = g.GradientDirection.ToString();
            }
            var t = el.TryCast<SI.Bindable.SIText>();
            if (t != null)
            {
                try { d["customStyleColour"] = t.m_customStyleColour.ToString(); } catch (Exception e) { d["customStyleColour"] = "unreadable: " + e.Message; }
            }
            return d;
        }
    }
}
