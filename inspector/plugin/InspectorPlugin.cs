using System;
using BepInEx;
using BepInEx.Configuration;
using BepInEx.Unity.IL2CPP;
using System.Runtime.Versioning;

[assembly: SupportedOSPlatform("windows")]

namespace Crimson.Inspector
{
    // Entry point (spec 2). Starts the pipe thread and the main-thread tick; nothing else.
    [BepInPlugin(Guid, "FM27 Crimson Inspector", Version)]
    public sealed class InspectorPlugin : BasePlugin
    {
        public const string Guid = "app.hubert.fm27inspector";
        public const string Version = "0.5.0-capture";

        internal static BepInEx.Logging.ManualLogSource Logger;
        internal static ConfigEntry<string> DumpFolder;
        internal static ConfigEntry<int> BudgetMs;
        internal static ConfigEntry<bool> AllowActions;
        private ConfigEntry<bool> _enabled;
        private PipeHost _host;

        public override void Load()
        {
            Logger = Log;
            _enabled = Config.Bind("Inspector", "Enabled", true, "Run the read-only UI inspector (development only).");
            DumpFolder = Config.Bind("Inspector", "DumpFolder", @"C:\Users\Admin\FMSKINNING\workspace\notes\ui-dumps",
                "Folder for dump_tree JSON and screenshots. Never inside the game folder.");
            BudgetMs = Config.Bind("Inspector", "MainThreadBudgetMs", 40, "Main-thread time budget per request; walks stop when it is spent.");
            AllowActions = Config.Bind("Inspector", "AllowActions", false, "Allow click and scroll tools (writes to the UI). Use on a throwaway save only.");
            Capture.Bind(Config);                      // 0.3.0: capture modes, all off by default (docs/PHASE9-PLAN.md section 9b)
            if (!_enabled.Value)
            {
                Log.LogInfo("[Inspector] disabled by config");
                return;
            }
            AddComponent<InspectorTick>();
            _host = new PipeHost(RequestQueue.Instance);
            _host.Start();
            Log.LogInfo($"[Inspector] {Version} ready on \\\\.\\pipe\\{PipeHost.PipeName} (actions: {AllowActions.Value}, same-user only)");
        }

        public override bool Unload()
        {
            Capture.Abort();
            _host?.Stop();
            return true;
        }
    }
}

