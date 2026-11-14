using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Linq;
using System.Text.Json;
using Il2CppInterop.Runtime;
using UnityEngine;
using UnityEngine.SceneManagement;
using UnityEngine.UIElements;
using UObject = UnityEngine.Object;

namespace Crimson.Inspector
{
    // Tool table (spec 6). Every tool is read-only.
    internal static class Tools
    {
        public static object Run(string tool, JsonElement p, Budget budget)
        {
            switch (tool)
            {
                case "status": return Status();
                case "diagnostics": return Diagnostics();
                case "screen": return Screen(p, budget);
                case "find": return Find(p, budget);
                case "get_styles": return StyleProbe.Describe(Ui.Resolve(Str(p, "path", null)));
                case "colour_source": return ColourTrace.Explain(Ui.Resolve(Str(p, "path", null)), Str(p, "property", "background-color"));
                case "dump_tree": return DumpTree(p, budget);
                case "screenshot": return Screenshot(p);
                case "capture_start": case "capture_status": case "capture_stop": return Capture.Handle(tool, p);     // 0.3.0, cfg-gated, off by default
                case "describe": return Actions.Describe(p);
                case "click": return Actions.Click(p);
                case "scroll": return Actions.Scroll(p);
                default: throw new ToolFault("unknown_tool", "no tool named '" + tool + "'");
            }
        }

        // ---- params -------------------------------------------------------------------------------------------
        internal static string Str(JsonElement p, string key, string fallback) =>
            p.ValueKind == JsonValueKind.Object && p.TryGetProperty(key, out var v) && v.ValueKind == JsonValueKind.String ? v.GetString() : fallback;
        internal static int Int(JsonElement p, string key, int fallback, int min, int max) =>
            p.ValueKind == JsonValueKind.Object && p.TryGetProperty(key, out var v) && v.ValueKind == JsonValueKind.Number ? Math.Clamp(v.GetInt32(), min, max) : fallback;
        internal static bool Bool(JsonElement p, string key, bool fallback) =>
            p.ValueKind == JsonValueKind.Object && p.TryGetProperty(key, out var v) && (v.ValueKind == JsonValueKind.True || v.ValueKind == JsonValueKind.False) ? v.GetBoolean() : fallback;

        private static object Status() => new Dictionary<string, object>
        {
            ["plugin"] = InspectorPlugin.Version,
            ["game"] = Application.version,
            ["unity"] = Application.unityVersion,
            ["scene"] = SceneManager.GetActiveScene().name,
            ["roots"] = Ui.Roots().Count,
            ["pid"] = System.Diagnostics.Process.GetCurrentProcess().Id,
        };

        private static object Diagnostics()
        {
            var roots = Ui.Roots();
            var list = new List<object>();
            for (int i = 0; i < roots.Count; i++)
            {
                var r = roots[i];
                list.Add(new Dictionary<string, object>
                {
                    ["path"] = "P" + i,
                    ["source"] = r.Source,
                    ["children"] = r.Element.hierarchy.childCount,
                    ["sheets"] = StyleProbe.SheetNames(r.Element),
                });
            }
            var asm = AppDomain.CurrentDomain.GetAssemblies().Select(a => a.GetName().Name)
                .Where(n => n.StartsWith("SI.") || n.StartsWith("FM.") || n.StartsWith("UnityEngine.UI")).OrderBy(n => n).ToList();
            return new Dictionary<string, object> { ["roots"] = list, ["assemblies"] = asm };
        }

        // 0.1.1: screen / find / dump_tree all serve from the per-frame flat snapshot (Snapshot.Get); the
        // reply adds "snapshot" (nodes captured so far) and "frame" so partial captures are visible.
        private static object Screen(JsonElement p, Budget budget)
        {
            bool visibleOnly = Bool(p, "visibleOnly", true), textOnly = Bool(p, "textOnly", false);
            int max = Int(p, "maxNodes", 1500, 1, 20000);   // 0.1.1: cap raised 5000 -> 20000 (reply checked against the 8 MiB contract)
            Snap snap = Snap.Get(budget);
            var nodes = new List<object>(Math.Min(max, snap.Nodes.Count));
            bool partial = snap.Partial;
            foreach (Snap.Node nd in snap.Nodes)
            {
                if (nodes.Count >= max) { partial = true; break; }
                if (visibleOnly && !nd.Visible) continue;
                if (textOnly && string.IsNullOrEmpty(nd.Text)) continue;
                nodes.Add(new Dictionary<string, object> { ["path"] = nd.Path, ["label"] = nd.Label, ["text"] = nd.Text, ["visible"] = nd.Visible,
                    ["x"] = Ui.Num(nd.X), ["y"] = Ui.Num(nd.Y), ["w"] = Ui.Num(nd.W), ["h"] = Ui.Num(nd.H) });
            }
            return new Dictionary<string, object> { ["nodes"] = nodes, ["count"] = nodes.Count, ["partial"] = partial,
                ["snapshot"] = snap.Nodes.Count, ["frame"] = snap.Frame };
        }

        private static object Find(JsonElement p, Budget budget)
        {
            string query = Str(p, "query", null);
            if (string.IsNullOrWhiteSpace(query)) throw new ToolFault("bad_request", "query is required");
            string field = Str(p, "field", "any");
            bool visibleOnly = Bool(p, "visibleOnly", false);
            int max = Int(p, "max", 200, 1, 1000);
            Snap snap = Snap.Get(budget);
            var hits = new List<object>();
            bool partial = snap.Partial;
            int scanned = 0;
            foreach (Snap.Node nd in snap.Nodes)
            {
                if (hits.Count >= max) { partial = true; break; }
                scanned++;
                if (visibleOnly && !nd.Visible) continue;
                if (MatchNode(nd, query, field))
                    hits.Add(new Dictionary<string, object> { ["path"] = nd.Path, ["label"] = nd.Label, ["text"] = nd.Text, ["visible"] = nd.Visible, ["depth"] = nd.Depth });
            }
            return new Dictionary<string, object> { ["matches"] = hits, ["scanned"] = scanned, ["partial"] = partial,
                ["snapshot"] = snap.Nodes.Count, ["frame"] = snap.Frame };
        }

        // Same semantics as the 0.1.0 Ui.Matches, but over the captured fields (no IL2CPP calls).
        private static bool MatchNode(Snap.Node nd, string q, string field)
        {
            bool any = field == "any";
            if ((any || field == "name") && nd.Name.IndexOf(q, StringComparison.OrdinalIgnoreCase) >= 0) return true;
            if ((any || field == "type") && nd.Type.IndexOf(q, StringComparison.OrdinalIgnoreCase) >= 0) return true;
            if ((any || field == "class") && nd.Classes.Exists(c => c.IndexOf(q, StringComparison.OrdinalIgnoreCase) >= 0)) return true;
            if ((any || field == "text") && nd.Text.IndexOf(q, StringComparison.OrdinalIgnoreCase) >= 0) return true;
            return false;
        }

        // 0.1.1: flattened dump, path as the key (System.Text.Json nests by depth; a flat map has none).
        private static object DumpTree(JsonElement p, Budget budget)
        {
            string start = Str(p, "path", "P0");
            int depth = Int(p, "depth", 8, 1, 40);
            Ui.Resolve(start);                                   // validates the path live (throws not_found)
            Snap snap = Snap.Get(budget);
            string prefix = start + "/";
            int startDepth = start.Split('/').Length - 1;
            var nodes = new Dictionary<string, object>();
            int count = 0;
            bool partial = snap.Partial;
            foreach (Snap.Node nd in snap.Nodes)
            {
                if (nd.Path != start && !nd.Path.StartsWith(prefix, StringComparison.Ordinal)) continue;
                if (nd.Depth - startDepth > depth) { partial = true; continue; }
                nodes[nd.Path] = new Dictionary<string, object> { ["label"] = nd.Label, ["text"] = nd.Text, ["visible"] = nd.Visible,
                    ["depth"] = nd.Depth, ["bounds"] = new[] { Ui.Num(nd.X), Ui.Num(nd.Y), Ui.Num(nd.W), Ui.Num(nd.H) } };
                count++;
            }
            string folder = InspectorPlugin.DumpFolder.Value;
            Directory.CreateDirectory(folder);
            string name = Str(p, "file", null) ?? ("tree-" + DateTime.Now.ToString("yyyyMMdd-HHmmss", CultureInfo.InvariantCulture));
            string file = Path.Combine(folder, Ui.SafeFile(name) + ".json");
            File.WriteAllText(file, JsonSerializer.Serialize(
                new Dictionary<string, object> { ["root"] = start, ["frame"] = snap.Frame, ["partial"] = partial, ["nodes"] = nodes },
                new JsonSerializerOptions { WriteIndented = false }));
            return new Dictionary<string, object> { ["file"] = file, ["nodes"] = count, ["partial"] = partial,
                ["snapshot"] = snap.Nodes.Count };
        }

        private static object Screenshot(JsonElement p)
        {
            string folder = Path.Combine(InspectorPlugin.DumpFolder.Value, "screens");
            Directory.CreateDirectory(folder);
            string name = Str(p, "file", null) ?? ("screen-" + DateTime.Now.ToString("yyyyMMdd-HHmmss", CultureInfo.InvariantCulture));
            string file = Path.Combine(folder, Ui.SafeFile(name) + ".png");
            ScreenCapture.CaptureScreenshot(file);
            return new Dictionary<string, object> { ["file"] = file, ["state"] = "pending (written at the end of this frame)" };
        }
    }

    // Roots, paths, labels, visibility (spec 5).
    internal static class Ui
    {
        internal sealed class Root { public VisualElement Element; public string Source; }

        public static List<Root> Roots()
        {
            var seen = new HashSet<long>();
            var roots = new List<Root>();
            foreach (UIDocument doc in UObject.FindObjectsByType<UIDocument>(FindObjectsSortMode.None))
            {
                VisualElement tree = doc?.rootVisualElement?.panel?.visualTree;
                if (tree != null && seen.Add(tree.Pointer.ToInt64())) roots.Add(new Root { Element = tree, Source = "document:" + doc.name });
            }
            var panels = UIElementsRuntimeUtility.GetSortedPlayerPanels();
            if (panels != null)
                for (int i = 0; i < panels.Count; i++)
                {
                    VisualElement tree = panels[i]?.visualTree;
                    if (tree != null && seen.Add(tree.Pointer.ToInt64())) roots.Add(new Root { Element = tree, Source = "runtime-panel:" + i });
                }
            return roots;
        }

        public static VisualElement Resolve(string path)
        {
            if (string.IsNullOrEmpty(path) || path[0] != 'P') throw new ToolFault("bad_request", "path must look like P<root>/<child>/...");
            string[] steps = path.Substring(1).Split('/');
            var roots = Roots();
            if (!int.TryParse(steps[0], out int r) || r < 0 || r >= roots.Count) throw new ToolFault("not_found", "no root " + steps[0]);
            VisualElement el = roots[r].Element;
            for (int i = 1; i < steps.Length; i++)
            {
                if (!int.TryParse(steps[i], out int c) || c < 0 || c >= el.hierarchy.childCount)
                    throw new ToolFault("not_found", "path breaks at step " + i + " (" + Label(el) + " has " + el.hierarchy.childCount + " children)");
                el = el.hierarchy.ElementAt(c);
            }
            return el;
        }

        // Depth-first walking lives in Snapshot (0.1.1): one flat capture per frame serves find / screen / dump_tree.

        public static bool SelfVisible(VisualElement el)
        {
            IResolvedStyle s = el.resolvedStyle;
            if (s.display == DisplayStyle.None || s.visibility != Visibility.Visible || s.opacity <= 0f) return false;
            Rect b = el.worldBound;
            return b.width > 0 && b.height > 0;
        }

        public static bool AncestorsVisible(VisualElement el)
        {
            for (VisualElement a = el.hierarchy.parent; a != null; a = a.hierarchy.parent) if (!SelfVisible(a)) return false;
            return true;
        }

        public static string TypeName(VisualElement el) => el.GetIl2CppType().Name;

        public static List<string> Classes(VisualElement el)
        {
            var list = new List<string>();
            var cl = el.m_ClassList;
            if (cl != null) for (int i = 0; i < cl.Count; i++) list.Add(cl[i]);
            return list;
        }

        public static string Label(VisualElement el) => Label(el, Classes(el));

        public static string Label(VisualElement el, List<string> classes)
        {
            string s = TypeName(el);
            if (!string.IsNullOrEmpty(el.name)) s += "#" + el.name;
            foreach (string c in classes) s += "." + c;
            return s;
        }

        public static string Text(VisualElement el)
        {
            string t = el.TryCast<TextElement>()?.text;
            if (string.IsNullOrEmpty(t)) return "";
            return t.Length <= 512 ? t : t.Substring(0, 512);
        }

        public static double Num(float f) => float.IsFinite(f) ? Math.Round(f, 1) : 0;
        public static string Hex(Color c)
        {
            int Ch(float x) => Mathf.Clamp(Mathf.RoundToInt(x * 255f), 0, 255);
            return "#" + Ch(c.r).ToString("X2") + Ch(c.g).ToString("X2") + Ch(c.b).ToString("X2") + (Ch(c.a) == 255 ? "" : Ch(c.a).ToString("X2"));
        }
        public static string SafeFile(string s) => string.Concat(s.Select(ch => char.IsLetterOrDigit(ch) || ch == '-' || ch == '_' ? ch : '_'));
    }
}
