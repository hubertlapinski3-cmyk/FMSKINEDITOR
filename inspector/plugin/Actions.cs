using System;
using System.Collections.Generic;
using System.IO;
using System.Text.Json;
using Il2CppInterop.Runtime;
using UnityEngine;
using UnityEngine.UIElements;

namespace Crimson.Inspector
{
    // 0.2.0: the only write-capable part of the inspector. Off unless [Inspector] AllowActions = true.
    // Safety: the caller must pass `expect`, a fragment of the element's label or text, which is checked against
    // the live element so a stale path cannot hit a different control. At most one dispatch per call.
    internal static class Actions
    {
        private static VisualElement Target(JsonElement p, out string label, out string text)
        {
            if (!InspectorPlugin.AllowActions.Value)
                throw new ToolFault("actions_disabled", "set [Inspector] AllowActions = true in the plugin config and restart the game");
            string path = Tools.Str(p, "path", null);
            string expect = Tools.Str(p, "expect", null);
            if (string.IsNullOrWhiteSpace(expect)) throw new ToolFault("bad_request", "expect is required: a fragment of the element's label or text");
            VisualElement el = Ui.Resolve(path);
            label = Ui.Label(el);
            text = Ui.Text(el);
            if (label.IndexOf(expect, StringComparison.OrdinalIgnoreCase) < 0 && text.IndexOf(expect, StringComparison.OrdinalIgnoreCase) < 0)
                throw new ToolFault("expect_mismatch", "element is " + label + " text='" + text + "', which does not contain '" + expect + "'");
            if (!Ui.SelfVisible(el) || !Ui.AncestorsVisible(el)) throw new ToolFault("not_visible", "element is not visible");
            if (!el.enabledInHierarchy) throw new ToolFault("disabled", "element is disabled");
            return el;
        }

        // 0.2.1: every click and scroll attempt is appended (never truncated, survives relaunch) to BepInEx\FM27Inspector-actions.log
        // next to LogOutput.log: ISO timestamp | tool | path | expect | result.
        private static readonly object LogLock = new object();
        private static void ActionLog(string tool, string path, string expect, string result)
        {
            try
            {
                string file = Path.Combine(BepInEx.Paths.BepInExRootPath, "FM27Inspector-actions.log");
                string line = DateTimeOffset.Now.ToString("yyyy-MM-ddTHH:mm:ss.fffzzz") + " | " + tool + " | path=" + (path ?? "-") + " | expect=" + (expect ?? "-") + " | " + result.Replace('\r', ' ').Replace('\n', ' ') + Environment.NewLine;
                lock (LogLock) File.AppendAllText(file, line);
            }
            catch (Exception) { /* logging must never break a click */ }
        }

        private static string Summary(object r)
        {
            if (r is Dictionary<string, object> d)
                return "ok via=" + (d.TryGetValue("via", out var v) ? v : "-") + " label=" + (d.TryGetValue("label", out var l) ? l : "-") + " text='" + (d.TryGetValue("text", out var t) ? t : "") + "'";
            return "ok";
        }

        public static object Click(JsonElement p)
        {
            string path = Tools.Str(p, "path", null), expect = Tools.Str(p, "expect", null);
            try { object r = ClickCore(p); ActionLog("click", path, expect, Summary(r)); return r; }
            catch (ToolFault f) { ActionLog("click", path, expect, "fault " + f.Kind + ": " + f.Message); throw; }
            catch (Exception e) { ActionLog("click", path, expect, "error " + e.GetType().Name + ": " + e.Message); throw; }
        }

        private static object ClickCore(JsonElement p)
        {
            VisualElement el = Target(p, out string label, out string text);
            string how = null;
            for (VisualElement a = el; a != null && how == null; a = a.hierarchy.parent)
            {
                var fm = a.TryCast<SI.Bindable.SIButton>();
                if (fm != null)
                {
                    if (!fm.IsInteractable()) throw new ToolFault("disabled", "FM reports the button is not interactable");
                    fm.SimulateButtonClick();
                    how = "SIButton:" + Ui.Label(a);
                    break;
                }
                string tn = Ui.TypeName(a);
                if (tn.IndexOf("Radio", StringComparison.OrdinalIgnoreCase) >= 0 || tn.IndexOf("Toggle", StringComparison.OrdinalIgnoreCase) >= 0 || tn.IndexOf("Checkbox", StringComparison.OrdinalIgnoreCase) >= 0)
                {
                    Type wt = Wrapper(tn);
                    if (wt != null)
                    {
                        object obj = Activator.CreateInstance(wt, new object[] { a.Pointer });
                        var prop = wt.GetProperty("value");
                        if (prop != null && prop.PropertyType == typeof(bool) && prop.CanWrite)
                        {
                            bool isRadio = tn.IndexOf("Radio", StringComparison.OrdinalIgnoreCase) >= 0;
                            bool next = isRadio ? true : !(bool)prop.GetValue(obj);
                            prop.SetValue(obj, next);
                            how = tn + ".value=" + next;
                            break;
                        }
                    }
                }
            }
            if (how == null)
            {
                Rect b = el.worldBound;
                var evt = ClickEvent.GetPooled();
                try
                {
                    evt.target = el.Cast<IEventHandler>();
                    el.SendEvent(evt);
                    how = "ClickEvent (no SIButton ancestor)";
                }
                finally { evt.Dispose(); }
            }
            return new Dictionary<string, object> { ["dispatched"] = true, ["via"] = how, ["label"] = label, ["text"] = text,
                ["next"] = "read the screen again to verify; paths may have changed" };
        }

        private static readonly Dictionary<string, Type> WrapperCache = new Dictionary<string, Type>();

        // The managed interop wrapper for an IL2CPP class name (hierarchy walks return the declared type, not the runtime one).
        internal static Type Wrapper(string name)
        {
            if (WrapperCache.TryGetValue(name, out Type hit)) return hit;
            Type found = null;
            foreach (var asm in AppDomain.CurrentDomain.GetAssemblies())
            {
                string an = asm.GetName().Name;
                if (!(an.StartsWith("SI.") || an.StartsWith("FM.") || an.StartsWith("UnityEngine"))) continue;
                Type[] ts;
                try { ts = asm.GetTypes(); } catch (System.Reflection.ReflectionTypeLoadException e) { ts = Array.FindAll(e.Types, t => t != null); }
                foreach (Type t in ts)
                    if (t.Name == name && !t.IsGenericTypeDefinition && t.GetConstructor(new[] { typeof(IntPtr) }) != null) { found = t; break; }
                if (found != null) break;
            }
            WrapperCache[name] = found;
            return found;
        }

        // Read-only: runtime wrapper type chain and public method / bool property names of the element and its ancestors.
        public static object Describe(JsonElement p)
        {
            VisualElement el = Ui.Resolve(Tools.Str(p, "path", null));
            var list = new List<object>();
            int up = 0;
            for (VisualElement a = el; a != null && up < 8; a = a.hierarchy.parent, up++)
            {
                string rt = Ui.TypeName(a);
                Type wt = Wrapper(rt);
                var chain = new List<string> { rt };
                for (Type t = wt?.BaseType; t != null; t = t.BaseType) chain.Add(t.Name);
                var methods = new List<string>();
                var props = new List<string>();
                if (wt != null)
                {
                    foreach (var m in wt.GetMethods(System.Reflection.BindingFlags.Public | System.Reflection.BindingFlags.Instance | System.Reflection.BindingFlags.DeclaredOnly))
                        if (!m.IsSpecialName && methods.Count < 40) methods.Add(m.Name);
                    foreach (var pr in wt.GetProperties(System.Reflection.BindingFlags.Public | System.Reflection.BindingFlags.Instance))
                        if (pr.PropertyType == typeof(bool) && props.Count < 30) props.Add(pr.Name);
                }
                list.Add(new Dictionary<string, object> { ["up"] = up, ["chain"] = chain, ["methods"] = methods, ["boolProps"] = props });
            }
            return new Dictionary<string, object> { ["elements"] = list };
        }

        public static object Scroll(JsonElement p)
        {
            string path = Tools.Str(p, "path", null), expect = Tools.Str(p, "expect", null);
            try { object r = ScrollCore(p); ActionLog("scroll", path, expect, "ok dx=" + Tools.Int(p, "dx", 0, -5000, 5000) + " dy=" + Tools.Int(p, "dy", 0, -5000, 5000)); return r; }
            catch (ToolFault f) { ActionLog("scroll", path, expect, "fault " + f.Kind + ": " + f.Message); throw; }
            catch (Exception e) { ActionLog("scroll", path, expect, "error " + e.GetType().Name + ": " + e.Message); throw; }
        }

        private static object ScrollCore(JsonElement p)
        {
            VisualElement el = Target(p, out string label, out _);
            ScrollView sv = null;
            for (VisualElement a = el; a != null && sv == null; a = a.hierarchy.parent) sv = a.TryCast<ScrollView>();
            if (sv == null) throw new ToolFault("unsupported", "no ScrollView at or above " + label);
            float dy = Math.Clamp((float)Tools.Int(p, "dy", 0, -5000, 5000), -5000, 5000);
            float dx = Math.Clamp((float)Tools.Int(p, "dx", 0, -5000, 5000), -5000, 5000);
            sv.scrollOffset = sv.scrollOffset + new Vector2(dx, dy);
            return new Dictionary<string, object> { ["dispatched"] = true, ["offsetX"] = sv.scrollOffset.x, ["offsetY"] = sv.scrollOffset.y };
        }
    }
}

