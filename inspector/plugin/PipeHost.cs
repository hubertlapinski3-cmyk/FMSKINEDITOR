using System;
using System.IO;
using System.IO.Pipes;
using System.Security.AccessControl;
using System.Security.Principal;
using System.Text;
using System.Text.Json;
using System.Threading;
using System.Threading.Tasks;

namespace Crimson.Inspector
{
    // Transport (spec 3): same-user named pipe, one request line in, one reply line out, never touches Unity.
    internal sealed class PipeHost
    {
        public const string PipeName = "fm27-crimson-inspector";
        private const int MaxRequestBytes = 32 * 1024;
        private static readonly TimeSpan ReplyWait = TimeSpan.FromSeconds(8);

        private readonly RequestQueue _queue;
        private readonly CancellationTokenSource _cts = new CancellationTokenSource();

        public PipeHost(RequestQueue queue) { _queue = queue; }

        public void Start() => Task.Run(ServeForever);
        public void Stop() => _cts.Cancel();

        private static PipeSecurity BuildSecurity()
        {
            var security = new PipeSecurity();
            SecurityIdentifier me = WindowsIdentity.GetCurrent().User;
            security.AddAccessRule(new PipeAccessRule(me, PipeAccessRights.FullControl, AccessControlType.Allow));
            security.AddAccessRule(new PipeAccessRule(new SecurityIdentifier(WellKnownSidType.NetworkSid, null),
                PipeAccessRights.FullControl, AccessControlType.Deny));
            return security;
        }

        private async Task ServeForever()
        {
            PipeSecurity security;
            try { security = BuildSecurity(); }
            catch (Exception e) { InspectorPlugin.Logger.LogError("[Inspector] pipe security failed: " + e.Message); return; }
            while (!_cts.IsCancellationRequested)
            {
                try
                {
                    using (var server = NamedPipeServerStreamAcl.Create(PipeName, PipeDirection.InOut, 1,
                               PipeTransmissionMode.Byte, PipeOptions.Asynchronous, 0, 0, security))
                    {
                        await server.WaitForConnectionAsync(_cts.Token).ConfigureAwait(false);
                        string line = await ReadLine(server).ConfigureAwait(false);
                        string reply = await Handle(line).ConfigureAwait(false);
                        byte[] bytes = Encoding.UTF8.GetBytes(reply + "\n");
                        await server.WriteAsync(bytes, 0, bytes.Length, _cts.Token).ConfigureAwait(false);
                        await server.FlushAsync(_cts.Token).ConfigureAwait(false);
                    }
                }
                catch (OperationCanceledException) { break; }
                catch (Exception e) { InspectorPlugin.Logger.LogWarning("[Inspector] connection dropped: " + e.Message); }
            }
        }

        private async Task<string> ReadLine(Stream s)
        {
            var buffer = new MemoryStream();
            var chunk = new byte[4096];
            while (buffer.Length <= MaxRequestBytes)
            {
                int n = await s.ReadAsync(chunk, 0, chunk.Length, _cts.Token).ConfigureAwait(false);
                if (n <= 0) break;
                int nl = Array.IndexOf(chunk, (byte)'\n', 0, n);
                buffer.Write(chunk, 0, nl >= 0 ? nl : n);
                if (nl >= 0) break;
            }
            return buffer.Length > MaxRequestBytes ? null : Encoding.UTF8.GetString(buffer.ToArray());
        }

        private async Task<string> Handle(string line)
        {
            if (line == null) return Reply.Fault(0, "too_large", "request exceeds 32 KiB");
            int id = 0;
            try
            {
                using (var doc = JsonDocument.Parse(line))
                {
                    JsonElement root = doc.RootElement;
                    if (root.TryGetProperty("id", out var idEl) && idEl.ValueKind == JsonValueKind.Number) id = idEl.GetInt32();
                    if (!root.TryGetProperty("tool", out var toolEl) || toolEl.ValueKind != JsonValueKind.String)
                        return Reply.Fault(id, "bad_request", "missing tool");
                    string paramsJson = root.TryGetProperty("params", out var p) && p.ValueKind == JsonValueKind.Object ? p.GetRawText() : "{}";
                    var item = new WorkItem(id, toolEl.GetString(), paramsJson);
                    if (!_queue.TryAdd(item)) return Reply.Fault(id, "game_busy", "four requests already waiting");
                    Task done = await Task.WhenAny(item.Done.Task, Task.Delay(ReplyWait, _cts.Token)).ConfigureAwait(false);
                    if (done != item.Done.Task)
                    {
                        item.Abandon();
                        return Reply.Fault(id, "timeout", "the game did not run the request within 8 s");
                    }
                    return item.Done.Task.Result;
                }
            }
            catch (JsonException e) { return Reply.Fault(id, "bad_request", "invalid JSON: " + e.Message); }
        }
    }
}
