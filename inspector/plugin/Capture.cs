using System;
using System.Collections;
using System.Collections.Generic;
using System.Diagnostics;
using System.Globalization;
using System.IO;
using System.Reflection;
using System.Text;
using System.Text.Json;
using BepInEx.Configuration;
using UnityEngine;
using UnityEngine.UIElements;

namespace Crimson.Inspector
{
    // Capture modes (docs/PHASE9-PLAN.md section 9b). Hard rules from the owner, enforced here:
    //   read-only (nothing in this file writes to the UI, clicks, focuses or binds);
    //   hook-free (modes 1 and 2 are property reads; nothing patches a game method);
    //   cfg-gated, all OFF by default: [Capture] Enabled plus one key per mode;
    //   session-scoped: one session at a time, started and stopped through the pipe, with a frame and a time limit, released on stop or unload;
    //   output only to DumpFolder (never inside the game folder), one JSON object per line, so an aborted session still leaves a valid partial file.
    // Mode 1 (styles) and mode 2 (sources) share one frame-chunked walk. Mode 3 (transitions) is not implemented here: it answers "not_implemented".
    // Mode 4 (0.4.0, READING ONLY): with `"bindings": true` on a styles or sources capture, every SIText also gets a `binding` object read from its Binder (IsBound, IsReady, ToString) and the
    //   delivered text is the element's `text` that mode 1 already records. No method is patched, no delegate is handed to the game, no generic member is read (the BindingMethod<SIText> and
    //   List<Record> members are deliberately NOT touched: FM26 crash map, open generics). A value that cannot be read is recorded as such, never filled in.
    internal static class Capture
    {
        internal static ConfigEntry<bool> Enabled, Styles, Sources, Transitions, Bindings;
        internal static ConfigEntry<int> FrameBudgetMs, MaxSeconds, MaxFrames;

        private static volatile bool _active;
        public static bool Active => _active;
        private static Session _s;

        public static void Bind(ConfigFile c)
        {
            Enabled = c.Bind("Capture", "Enabled", false, "Master switch for the capture modes. Off by default; read-only, session-scoped.");
            Styles = c.Bind("Capture", "Styles", false, "Mode 1: whole-tree resolved styles, classes, inline styles and bounds.");
            Sources = c.Bind("Capture", "Sources", false, "Mode 2: which VisualTreeAsset each subtree was instantiated from.");
            Transitions = c.Bind("Capture", "Transitions", false, "Mode 3 (reading only, polling): log every class and pseudo-state change of the watched elements.");
            Bindings = c.Bind("Capture", "Bindings", false, "Mode 4 (reading only): add a `binding` object (Binder state) to every SIText of a capture started with bindings=true.");
            FrameBudgetMs = c.Bind("Capture", "FrameBudgetMs", 8, "Main-thread milliseconds a capture may use per frame.");
            MaxSeconds = c.Bind("Capture", "MaxSeconds", 90, "A session stops by itself after this many seconds.");
            MaxFrames = c.Bind("Capture", "MaxFrames", 6000, "A session stops by itself after this many frames.");
            // Startup line (FM26 crash map rule): every launch states exactly what is live and the cfg state, so a crash pair always convicts the right suspect.
            // Modes 1 and 2 are property reads: no game method is patched, no delegate is handed to the game, no span or generic is touched.
            InspectorPlugin.Logger.LogInfo("[Capture] startup: hooks=none (property reads only); Enabled=" + Enabled.Value + " Styles=" + Styles.Value + " Sources=" + Sources.Value +
                " Transitions=" + Transitions.Value + "(polling, no hook) Bindings=" + Bindings.Value + "(reads Binder state only, no hook); FrameBudgetMs=" + FrameBudgetMs.Value +
                " MaxSeconds=" + MaxSeconds.Value + " MaxFrames=" + MaxFrames.Value);
        }

        public static void Abort() { if (_s != null && _active) Finish("aborted"); }

        private struct Open { public VisualElement El; public string Path; public int Depth, Next; }

        private sealed class Session
        {
            public string Id, Mode, Tag, File, State = "running", Error;
            public bool WithSource, WithStyles, WithBindings;
            public Stopwatch Clock = Stopwatch.StartNew();
            public int StartFrame, Count, Skipped, FramesUsed;
            public StreamWriter Out;
            public readonly HashSet<int> SheetsSeen = new HashSet<int>();
            public readonly List<Open> Stack = new List<Open>(256);
            // mode 3 (transitions)
            public readonly List<Tracked> Tracked = new List<Tracked>(8192);
            public readonly HashSet<long> Seen = new HashSet<long>();
            public int Cursor, Events, Rewalk, Over;
        }

        // Mode 3: an element kept under watch: the pseudo-state mask and the class list as last seen.
        private sealed class Tracked { public VisualElement El; public string Path; public int Pseudo; public string Classes; }
        private const int MaxTracked = 40000;

        // ---- pipe tools: capture_start / capture_status / capture_stop (all run on the main thread through the request queue)
        public static object Handle(string tool, JsonElement p)
        {
            switch (tool)
            {
                case "capture_start": return Start(p);
                case "capture_status": return Status();
                case "capture_stop": { if (_s == null) return Status(); if (_active) Finish("stopped"); return Status(); }
                default: throw new ToolFault("unknown_tool", tool);
            }
        }

        private static object Start(JsonElement p)
        {
            if (Enabled == null || !Enabled.Value) throw new ToolFault("disabled", "captures are off: set [Capture] Enabled = true in the plugin config (default false)");
            string mode = Tools.Str(p, "mode", "styles");
            if (mode == "transitions") return StartTransitions(p);
            bool wantStyles = mode == "styles", wantSources = mode == "sources" || Tools.Bool(p, "sources", false);
            bool wantBindings = Tools.Bool(p, "bindings", false);
            if (wantBindings && !Bindings.Value) throw new ToolFault("disabled", "binding reads are off: set [Capture] Bindings = true (default false)");
            if (mode != "styles" && mode != "sources") throw new ToolFault("bad_request", "mode must be styles or sources");
            if (wantStyles && !Styles.Value) throw new ToolFault("disabled", "mode 'styles' is off: set [Capture] Styles = true (default false)");
            if (wantSources && !Sources.Value) throw new ToolFault("disabled", "source attribution is off: set [Capture] Sources = true (default false)");
            if (_active) throw new ToolFault("game_busy", "a capture session is already running (" + _s.Id + "); capture_stop it first");

            var roots = Ui.Roots();
            string startPath = Tools.Str(p, "path", null);
            var s = new Session { Id = DateTime.Now.ToString("yyyyMMdd-HHmmss", CultureInfo.InvariantCulture), Mode = mode, WithStyles = wantStyles, WithSource = wantSources, WithBindings = wantBindings,
                Tag = Ui.SafeFile(Tools.Str(p, "tag", "screen")), StartFrame = Time.frameCount };
            if (startPath != null)
            {
                VisualElement el = Ui.Resolve(startPath);                       // validates the path live (throws not_found)
                s.Stack.Add(new Open { El = el, Path = startPath, Depth = startPath.Split('/').Length - 1, Next = 0 });
            }
            else
                for (int i = roots.Count - 1; i >= 0; i--) s.Stack.Add(new Open { El = roots[i].Element, Path = "P" + i, Depth = 0, Next = 0 });

            string folder = InspectorPlugin.DumpFolder.Value;
            Directory.CreateDirectory(folder);
            s.File = Path.Combine(folder, (wantStyles ? "styles-" : "sources-") + s.Tag + "-" + s.Id + ".ndjson");
            s.Out = new StreamWriter(s.File, false, new UTF8Encoding(false));
            WriteLine(s, new Dictionary<string, object>
            {
                ["schema"] = "fm-capture/1", ["mode"] = mode, ["styles"] = wantStyles, ["sources"] = wantSources, ["bindings"] = wantBindings, ["tag"] = s.Tag, ["start_path"] = startPath,
                ["game"] = Application.version, ["unity"] = Application.unityVersion, ["plugin"] = InspectorPlugin.Version, ["frame"] = Time.frameCount,
                ["started"] = DateTime.Now.ToString("o", CultureInfo.InvariantCulture), ["roots"] = roots.Count,
                ["limits"] = new Dictionary<string, object> { ["frame_budget_ms"] = FrameBudgetMs.Value, ["max_seconds"] = MaxSeconds.Value, ["max_frames"] = MaxFrames.Value },
                ["source_property_available"] = SourceProbe.Available,
                ["note"] = "read-only capture; values are as the engine reports them this frame; resolved = IResolvedStyle, inline = IStyle entries that are set",
            });
            _s = s;
            _active = true;
            InspectorPlugin.Logger.LogInfo("[Capture] session " + s.Id + " started: mode " + mode + " -> " + s.File);
            return Status();
        }

        // ---- mode 3 (0.5.0, READING ONLY, polling): which classes and pseudo-states change while the owner hovers or presses. No hook, no event registration, nothing is handed to the
        // game: every frame a budgeted slice of the watched elements is re-read (pseudo-state mask, class list) and a line is written for each change. New elements (popups, tooltips)
        // join the watch through a periodic re-walk of the tree. A session is bounded by the same seconds, frames and budget settings as every other.
        private static object StartTransitions(JsonElement p)
        {
            if (!Transitions.Value) throw new ToolFault("disabled", "mode 'transitions' is off: set [Capture] Transitions = true (default false)");
            if (_active) throw new ToolFault("game_busy", "a capture session is already running (" + _s.Id + "); capture_stop it first");
            var roots = Ui.Roots();
            string startPath = Tools.Str(p, "path", null);
            var s = new Session { Id = DateTime.Now.ToString("yyyyMMdd-HHmmss", CultureInfo.InvariantCulture), Mode = "transitions", Tag = Ui.SafeFile(Tools.Str(p, "tag", "hover")), StartFrame = Time.frameCount };
            var starts = new List<KeyValuePair<string, VisualElement>>();
            if (startPath != null) starts.Add(new KeyValuePair<string, VisualElement>(startPath, Ui.Resolve(startPath)));
            else for (int i = 0; i < roots.Count; i++) starts.Add(new KeyValuePair<string, VisualElement>("P" + i, roots[i].Element));
            s.Stack.Clear();
            foreach (var kv in starts) s.Stack.Add(new Open { El = kv.Value, Path = kv.Key, Depth = 0, Next = 0 });      // Stack is reused to remember where the re-walk starts
            string folder = InspectorPlugin.DumpFolder.Value;
            Directory.CreateDirectory(folder);
            s.File = Path.Combine(folder, "transitions-" + s.Tag + "-" + s.Id + ".ndjson");
            s.Out = new StreamWriter(s.File, false, new UTF8Encoding(false));
            WalkInto(s, starts, true);
            WriteLine(s, new Dictionary<string, object>
            {
                ["schema"] = "fm-capture/1", ["mode"] = "transitions", ["tag"] = s.Tag, ["start_path"] = startPath, ["game"] = Application.version, ["unity"] = Application.unityVersion,
                ["plugin"] = InspectorPlugin.Version, ["frame"] = Time.frameCount, ["started"] = DateTime.Now.ToString("o", CultureInfo.InvariantCulture), ["roots"] = roots.Count,
                ["watched"] = s.Tracked.Count, ["watch_cap"] = MaxTracked, ["limits"] = new Dictionary<string, object> { ["frame_budget_ms"] = FrameBudgetMs.Value, ["max_seconds"] = MaxSeconds.Value, ["max_frames"] = MaxFrames.Value },
                ["note"] = "read-only polling; one line per change: pseudo = [old, new] state masks, added / removed = class names; `appeared` = an element that joined the watch after the start",
            });
            s.Stack.Clear();
            s.Count = s.Tracked.Count;
            _s = s;
            _active = true;
            InspectorPlugin.Logger.LogInfo("[Capture] session " + s.Id + " started: mode transitions watching " + s.Tracked.Count + " elements -> " + s.File);
            return Status();
        }

        // Add every element under the given starts that is not watched yet; `first` = the start of the session (no `appeared` line).
        private static void WalkInto(Session s, List<KeyValuePair<string, VisualElement>> starts, bool first)
        {
            var stack = new List<Open>();
            foreach (var kv in starts) stack.Add(new Open { El = kv.Value, Path = kv.Key, Depth = 0, Next = 0 });
            while (stack.Count > 0)
            {
                int i = stack.Count - 1;
                Open top = stack[i];
                stack.RemoveAt(i);
                try
                {
                    long key = top.El.Pointer.ToInt64();
                    if (s.Seen.Add(key))
                    {
                        if (s.Tracked.Count >= MaxTracked) { s.Over++; }
                        else
                        {
                            var tr = new Tracked { El = top.El, Path = top.Path, Pseudo = StyleProbe.Pseudo(top.El), Classes = string.Join(" ", Ui.Classes(top.El)) };
                            s.Tracked.Add(tr);
                            if (!first) WriteLine(s, new Dictionary<string, object> { ["frame"] = Time.frameCount, ["t"] = Math.Round(s.Clock.Elapsed.TotalSeconds, 3), ["path"] = tr.Path, ["type"] = Ui.TypeName(top.El),
                                ["name"] = top.El.name ?? "", ["appeared"] = true, ["pseudo"] = new[] { 0, tr.Pseudo }, ["classes"] = tr.Classes });
                        }
                    }
                    int n = top.El.hierarchy.childCount;
                    for (int c = n - 1; c >= 0; c--)
                    {
                        VisualElement ch = null;
                        try { ch = top.El.hierarchy.ElementAt(c); } catch { }
                        if (ch != null) stack.Add(new Open { El = ch, Path = top.Path + "/" + c, Depth = top.Depth + 1, Next = 0 });
                    }
                }
                catch { s.Skipped++; }
            }
        }

        private static void TickTransitions(Session s)
        {
            var frame = Stopwatch.StartNew();
            double budget = Math.Max(2, FrameBudgetMs.Value);
            int n = s.Tracked.Count, done = 0;
            while (done < n && frame.Elapsed.TotalMilliseconds < budget)
            {
                if (s.Cursor >= n) s.Cursor = 0;
                Tracked tr = s.Tracked[s.Cursor++];
                done++;
                try
                {
                    int ps = StyleProbe.Pseudo(tr.El);
                    string cl = string.Join(" ", Ui.Classes(tr.El));
                    if (ps == tr.Pseudo && cl == tr.Classes) continue;
                    var added = new List<string>(); var removed = new List<string>();
                    var oldSet = new HashSet<string>(tr.Classes.Length == 0 ? new string[0] : tr.Classes.Split(' '));
                    var newSet = new HashSet<string>(cl.Length == 0 ? new string[0] : cl.Split(' '));
                    foreach (string c in newSet) if (!oldSet.Contains(c)) added.Add(c);
                    foreach (string c in oldSet) if (!newSet.Contains(c)) removed.Add(c);
                    WriteLine(s, new Dictionary<string, object> { ["frame"] = Time.frameCount, ["t"] = Math.Round(s.Clock.Elapsed.TotalSeconds, 3), ["path"] = tr.Path, ["type"] = Ui.TypeName(tr.El),
                        ["name"] = tr.El.name ?? "", ["pseudo"] = new[] { tr.Pseudo, ps }, ["added"] = added, ["removed"] = removed });
                    tr.Pseudo = ps; tr.Classes = cl; s.Events++;
                }
                catch { s.Skipped++; }                                   // an element removed mid-session: dropped on the next re-walk, never fatal
            }
            if (++s.Rewalk >= 45)                                        // popups and tooltips are new elements: look for them now and then
            {
                s.Rewalk = 0;
                var starts = new List<KeyValuePair<string, VisualElement>>();
                var roots = Ui.Roots();
                for (int i = 0; i < roots.Count; i++) starts.Add(new KeyValuePair<string, VisualElement>("P" + i, roots[i].Element));
                try { WalkInto(s, starts, false); } catch (Exception e) { s.Error = e.Message; }
                s.Count = s.Tracked.Count;
            }
        }

        private static object Status()
        {
            if (_s == null) return new Dictionary<string, object> { ["state"] = "none" };
            return new Dictionary<string, object> { ["id"] = _s.Id, ["mode"] = _s.Mode, ["state"] = _s.State, ["elements"] = _s.Count, ["skipped"] = _s.Skipped,
                ["frames"] = _s.FramesUsed, ["seconds"] = Math.Round(_s.Clock.Elapsed.TotalSeconds, 1), ["file"] = _s.File, ["pending"] = _s.Stack.Count, ["error"] = _s.Error };
        }

        // ---- the walk: called every frame from InspectorTick.Update while a session runs
        public static void Tick()
        {
            Session s = _s;
            if (!_active || s == null) return;
            try
            {
                s.FramesUsed++;
                if (Time.frameCount - s.StartFrame > MaxFrames.Value || s.Clock.Elapsed.TotalSeconds > MaxSeconds.Value) { Finish("limit"); return; }
                if (s.Mode == "transitions") { TickTransitions(s); return; }
                var frame = Stopwatch.StartNew();
                double budget = Math.Max(2, FrameBudgetMs.Value);
                while (s.Stack.Count > 0 && frame.Elapsed.TotalMilliseconds < budget)
                {
                    int i = s.Stack.Count - 1;
                    Open top = s.Stack[i];
                    if (top.Next == 0)
                    {
                        try { WriteLine(s, Record(top.El, top.Path, top.Depth, s)); s.Count++; }
                        catch (Exception e) { s.Skipped++; if (s.Skipped <= 5) InspectorPlugin.Logger.LogWarning("[Capture] skipped " + top.Path + ": " + e.GetType().Name + ": " + e.Message); }
                    }
                    int n;
                    try { n = top.El.hierarchy.childCount; } catch { n = 0; }          // an element removed mid-session: its subtree is skipped, never fatal
                    if (top.Next < n)
                    {
                        VisualElement child = null;
                        try { child = top.El.hierarchy.ElementAt(top.Next); } catch { s.Skipped++; }
                        top.Next++;
                        s.Stack[i] = top;
                        if (child != null) s.Stack.Add(new Open { El = child, Path = top.Path + "/" + (top.Next - 1), Depth = top.Depth + 1, Next = 0 });
                    }
                    else s.Stack.RemoveAt(i);
                }
                if (s.Stack.Count == 0) Finish("done");
            }
            catch (Exception e) { s.Error = e.GetType().Name + ": " + e.Message; Finish("failed"); }
        }

        private static void Finish(string state)
        {
            Session s = _s;
            _active = false;                                        // first: nothing else may start or continue
            if (s == null) return;
            s.State = state;
            try
            {
                WriteLine(s, new Dictionary<string, object> { ["end"] = true, ["state"] = state, ["elements"] = s.Count, ["skipped"] = s.Skipped, ["frames"] = s.FramesUsed,
                    ["seconds"] = Math.Round(s.Clock.Elapsed.TotalSeconds, 2), ["unvisited"] = s.Stack.Count, ["events"] = s.Events, ["watched"] = s.Tracked.Count, ["over_cap"] = s.Over });
                s.Out?.Flush(); s.Out?.Dispose(); s.Out = null;
            }
            catch (Exception e) { s.Error = e.Message; }
            s.Stack.Clear();
            InspectorPlugin.Logger.LogInfo("[Capture] session " + s.Id + " " + state + ": " + s.Count + " elements, " + s.Skipped + " skipped, " + s.FramesUsed + " frames -> " + s.File);
        }

        private static readonly JsonSerializerOptions Json = new JsonSerializerOptions { WriteIndented = false };
        private static void WriteLine(Session s, object o) => s.Out.WriteLine(JsonSerializer.Serialize(o, Json));

        // ---- sheet content (0.3.1): one `sheet_content` line per distinct StyleSheet instance attached to a captured element, written before that element's line.
        // Why: `sheets` is names only, and three entries on every document root have EMPTY names; their rules could not be matched against the style census.
        // Read-only property reads of the same members ColourTrace already uses (rules, properties, complexSelectors). A failure writes an `error` field and never skips the element.
        // `signature` = sha1 of the lines "<selectors of rule, joined ', '>#<property count>" in rule order: the offline reader computes the same from any indexed sheet.
        private static void EmitSheetContent(Session s, VisualElement el, string path)
        {
            try
            {
                var list = el.styleSheetList;
                if (list == null) return;
                for (int i = 0; i < list.Count; i++)
                {
                    StyleSheet sh = list[i];
                    if (sh == null) continue;
                    int id = sh.GetInstanceID();
                    if (!s.SheetsSeen.Add(id)) continue;
                    var d = new Dictionary<string, object> { ["sheet_content"] = true, ["owner"] = path, ["index"] = i, ["name"] = sh.name ?? "", ["instance"] = id };
                    try
                    {
                        var rules = sh.rules;
                        int n = rules == null ? 0 : rules.Length;
                        var sig = new StringBuilder();
                        var sample = new List<object>();
                        int cap = string.IsNullOrEmpty(sh.name) ? 80 : 6;           // unnamed sheets are the point: dump far more of them
                        int props = 0;
                        for (int r = 0; r < n; r++)
                        {
                            StyleRule rule = rules[r];
                            var ps = rule.properties;
                            int pc = ps == null ? 0 : ps.Length;
                            props += pc;
                            string sel = ColourTrace.RuleSelectors(rule);
                            sig.Append(sel).Append('#').Append(pc).Append('\n');
                            if (r < cap)
                            {
                                var pl = new List<string>();
                                for (int k = 0; k < pc && k < 12; k++) if (ps[k] != null) pl.Add(ps[k].name + ": " + ColourTrace.DeclText(sh, ps[k]));
                                sample.Add(new Dictionary<string, object> { ["s"] = sel, ["n"] = pc, ["p"] = pl });
                            }
                        }
                        d["rules"] = n; d["properties"] = props;
                        using (var sha = System.Security.Cryptography.SHA1.Create())
                            d["signature"] = BitConverter.ToString(sha.ComputeHash(Encoding.UTF8.GetBytes(sig.ToString()))).Replace("-", "").ToLowerInvariant();
                        d["sample"] = sample;
                        var imports = sh.flattenedRecursiveImports;
                        d["imports"] = imports == null ? 0 : imports.Count;
                    }
                    catch (Exception e) { d["error"] = e.GetType().Name + ": " + e.Message; }
                    WriteLine(s, d);
                }
            }
            catch (Exception e) { if (s.Skipped < 5) InspectorPlugin.Logger.LogWarning("[Capture] sheet content at " + path + ": " + e.GetType().Name + ": " + e.Message); }
        }

        // ---- one element
        private static Dictionary<string, object> Record(VisualElement el, string path, int depth, Session s)
        {
            var d = new Dictionary<string, object>();
            List<string> classes = Ui.Classes(el);
            d["path"] = path; d["depth"] = depth; d["type"] = Ui.TypeName(el); d["name"] = el.name ?? ""; d["classes"] = classes;
            if (s.WithStyles)
            {
                Rect wb = el.worldBound, lb = el.layout;
                d["pseudo"] = StyleProbe.Pseudo(el);
                d["visible"] = Ui.SelfVisible(el);
                d["text"] = Ui.Text(el);
                d["world"] = new[] { Ui.Num(wb.x), Ui.Num(wb.y), Ui.Num(wb.width), Ui.Num(wb.height) };
                d["layout"] = new[] { Ui.Num(lb.x), Ui.Num(lb.y), Ui.Num(lb.width), Ui.Num(lb.height) };
                d["resolved"] = Reflect.Resolved(el.resolvedStyle);
                d["inline"] = Reflect.Inline(el.style);
                var sheets = StyleProbe.SheetNames(el);
                if (sheets.Count > 0) { d["sheets"] = sheets; EmitSheetContent(s, el, path); }
            }
            if (s.WithBindings && d.ContainsKey("type") && (string)d["type"] == "SIText")
            {
                object b = BindingProbe.Of(el);
                if (b != null) d["binding"] = b;
            }
            if (s.WithSource)
            {
                object src = SourceProbe.Of(el);
                if (src != null) d["source"] = src;
            }
            return d;
        }
    }

    // Mode 4 reading: the Binder of an SIText (non-generic, three plain members). Everything is guarded; an unreadable member is named, not guessed.
    internal static class BindingProbe
    {
        public static object Of(VisualElement el)
        {
            var d = new Dictionary<string, object>();
            try
            {
                var t = el.TryCast<SI.Bindable.SIText>();
                if (t == null) return null;
                var b = t.m_binder;
                if (b == null) { d["binder"] = null; return d; }
                try { d["isBound"] = b.IsBound; } catch (Exception e) { d["isBound"] = "unreadable: " + e.GetType().Name; }
                try { d["isReady"] = b.IsReady; } catch (Exception e) { d["isReady"] = "unreadable: " + e.GetType().Name; }
                try { d["binder"] = b.ToString(); } catch (Exception e) { d["binder"] = "unreadable: " + e.GetType().Name; }
            }
            catch (Exception e) { d["error"] = e.GetType().Name + ": " + e.Message; }
            return d;
        }
    }

    // Mode 2: the VisualTreeAsset a subtree was instantiated from, read from the element (UI Toolkit sets it on the root of an instantiated asset). Looked up by name
    // at run time: if this engine build has no such member, the capture says so in its header and records nothing, instead of failing.
    internal static class SourceProbe
    {
        private static bool _looked;
        private static PropertyInfo _prop;
        private static MemberInfo _hash;
        public static bool Available { get { Look(); return _prop != null; } }

        private static void Look()
        {
            if (_looked) return;
            _looked = true;
            const BindingFlags all = BindingFlags.Public | BindingFlags.NonPublic | BindingFlags.Instance;
            _prop = typeof(VisualElement).GetProperty("visualTreeAssetSource", all);
            foreach (MemberInfo m in typeof(VisualTreeAsset).GetMembers(all))
                if ((m is PropertyInfo || m is FieldInfo) && m.Name.IndexOf("contenthash", StringComparison.OrdinalIgnoreCase) >= 0) { _hash = m; break; }
        }

        public static object Of(VisualElement el)
        {
            Look();
            if (_prop == null) return null;
            object o = _prop.GetValue(el);
            if (o == null) return null;
            var d = new Dictionary<string, object>();
            var u = o as UnityEngine.Object;
            if (u != null) { d["name"] = u.name; d["instance"] = u.GetInstanceID(); }
            else d["name"] = o.ToString();
            if (_hash != null)
            {
                try { d["hash"] = Reflect.Conv(_hash is PropertyInfo pi ? pi.GetValue(o) : ((FieldInfo)_hash).GetValue(o)); } catch { /* optional */ }
            }
            return d;
        }
    }

    // Reflection over IResolvedStyle and IStyle: every property the engine exposes is captured, so none is forgotten when the engine changes.
    internal static class Reflect
    {
        private static PropertyInfo[] _resolved, _style;
        private static readonly Dictionary<Type, (PropertyInfo kw, PropertyInfo val)> _styleValue = new Dictionary<Type, (PropertyInfo, PropertyInfo)>();

        private static PropertyInfo[] Props(Type t)
        {
            var list = new List<PropertyInfo>();
            foreach (PropertyInfo p in t.GetProperties(BindingFlags.Public | BindingFlags.Instance)) if (p.CanRead && p.GetIndexParameters().Length == 0) list.Add(p);
            return list.ToArray();
        }

        public static Dictionary<string, object> Resolved(IResolvedStyle r)
        {
            _resolved ??= Props(typeof(IResolvedStyle));
            var d = new Dictionary<string, object>();
            foreach (PropertyInfo p in _resolved)
            {
                try { d[p.Name] = Conv(p.GetValue(r)); }
                catch (Exception e) { d[p.Name] = "!" + e.GetType().Name; }
            }
            return d;
        }

        // Only the inline properties that are set: StyleKeyword.Null means "not set" (the convention StyleProbe.Inline already uses).
        public static Dictionary<string, object> Inline(IStyle st)
        {
            _style ??= Props(typeof(IStyle));
            var d = new Dictionary<string, object>();
            foreach (PropertyInfo p in _style)
            {
                try
                {
                    object v = p.GetValue(st);
                    if (v == null) continue;
                    Type t = v.GetType();
                    if (!_styleValue.TryGetValue(t, out var acc)) _styleValue[t] = acc = (t.GetProperty("keyword"), t.GetProperty("value"));
                    if (acc.kw == null) continue;
                    var kw = (StyleKeyword)acc.kw.GetValue(v);
                    if (kw == StyleKeyword.Null) continue;
                    d[p.Name] = kw == StyleKeyword.Undefined && acc.val != null ? Conv(acc.val.GetValue(v)) : (object)kw.ToString();
                }
                catch (Exception e) { d[p.Name] = "!" + e.GetType().Name; }
            }
            return d;
        }

        public static object Conv(object v)
        {
            switch (v)
            {
                case null: return null;
                case bool or int or long or string: return v;
                case float f: return float.IsFinite(f) ? Math.Round(f, 3) : 0;
                case double dd: return double.IsFinite(dd) ? Math.Round(dd, 3) : 0;
                case Color c: return Ui.Hex(c);
                case Enum: return v.ToString();
                case Vector2 v2: return new[] { Ui.Num(v2.x), Ui.Num(v2.y) };
                case IEnumerable e when v is not string:
                    {
                        var list = new List<object>();
                        foreach (object x in e) { list.Add(Conv(x)); if (list.Count >= 16) break; }
                        return list;
                    }
                default:
                    {
                        string s = v.ToString() ?? "";
                        return s.Length <= 120 ? s : s.Substring(0, 120);
                    }
            }
        }
    }
}
