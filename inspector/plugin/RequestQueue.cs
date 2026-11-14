using System;
using System.Collections.Concurrent;
using System.Collections.Generic;
using System.Diagnostics;
using System.Text;
using System.Text.Json;
using System.Threading;
using System.Threading.Tasks;
using UnityEngine;

namespace Crimson.Inspector
{
    internal sealed class WorkItem
    {
        public readonly int Id;
        public readonly string Tool;
        public readonly string ParamsJson;
        public readonly TaskCompletionSource<string> Done = new TaskCompletionSource<string>(TaskCreationOptions.RunContinuationsAsynchronously);
        private int _abandoned;
        public WorkItem(int id, string tool, string paramsJson) { Id = id; Tool = tool; ParamsJson = paramsJson; }
        public void Abandon() => Interlocked.Exchange(ref _abandoned, 1);
        public bool Abandoned => Volatile.Read(ref _abandoned) == 1;
    }

    // Spec 3/4: depth 4, one item per frame on the main thread.
    internal sealed class RequestQueue
    {
        public static readonly RequestQueue Instance = new RequestQueue();
        private const int Depth = 4;
        private readonly ConcurrentQueue<WorkItem> _items = new ConcurrentQueue<WorkItem>();
        private int _pending;

        public bool TryAdd(WorkItem item)
        {
            if (Interlocked.Increment(ref _pending) > Depth) { Interlocked.Decrement(ref _pending); return false; }
            _items.Enqueue(item);
            return true;
        }

        public bool HasWork => Volatile.Read(ref _pending) > 0;

        public void RunOne()
        {
            if (!_items.TryDequeue(out WorkItem item)) return;
            Interlocked.Decrement(ref _pending);
            if (item.Abandoned) return;
            var clock = Stopwatch.StartNew();
            string reply;
            try
            {
                using (JsonDocument p = JsonDocument.Parse(item.ParamsJson))
                {
                    var budget = new Budget(clock, InspectorPlugin.BudgetMs.Value);
                    object result = Tools.Run(item.Tool, p.RootElement, budget);
                    reply = Reply.Ok(item.Id, clock.Elapsed.TotalMilliseconds, result);
                }
            }
            catch (ToolFault f) { reply = Reply.Fault(item.Id, f.Kind, f.Message); }
            catch (Exception e) { reply = Reply.Fault(item.Id, "internal", e.GetType().Name + ": " + e.Message); }
            // Spec 3: a reply is at most 8 MiB. The screen cap (0.1.1: 20000 nodes) is measured against
            // this budget live; an oversized reply is refused instead of silently breaking the contract.
            int bytes = Encoding.UTF8.GetByteCount(reply);
            if (bytes > 8 * 1024 * 1024)
                reply = Reply.Fault(item.Id, "reply_too_large",
                    "reply is " + bytes + " bytes, over the 8 MiB pipe contract; lower maxNodes");
            item.Done.TrySetResult(reply);
        }
    }

    internal sealed class Budget
    {
        private readonly Stopwatch _clock;
        private readonly double _limit;
        public Budget(Stopwatch clock, int ms) { _clock = clock; _limit = Math.Max(5, ms); }
        public bool Spent => _clock.Elapsed.TotalMilliseconds > _limit;
    }

    internal sealed class ToolFault : Exception
    {
        public readonly string Kind;
        public ToolFault(string kind, string detail) : base(detail) { Kind = kind; }
    }

    internal static class Reply
    {
        private static readonly JsonSerializerOptions Opts = new JsonSerializerOptions { WriteIndented = false };
        public static string Ok(int id, double ms, object result) =>
            JsonSerializer.Serialize(new Dictionary<string, object> { ["v"] = 1, ["id"] = id, ["ms"] = Math.Round(ms, 2), ["result"] = result }, Opts);
        public static string Fault(int id, string kind, string detail) =>
            JsonSerializer.Serialize(new Dictionary<string, object> { ["v"] = 1, ["id"] = id, ["fault"] = new Dictionary<string, object> { ["kind"] = kind, ["detail"] = detail } }, Opts);
    }

    // Spec 4: injected behaviour; idle frames cost one volatile read.
    public sealed class InspectorTick : MonoBehaviour
    {
        public InspectorTick(IntPtr ptr) : base(ptr) { }
        public void Update()
        {
            if (Capture.Active) Capture.Tick();           // a running capture session advances by its own small per-frame budget
            if (!RequestQueue.Instance.HasWork) return;
            RequestQueue.Instance.RunOne();
        }
    }
}
