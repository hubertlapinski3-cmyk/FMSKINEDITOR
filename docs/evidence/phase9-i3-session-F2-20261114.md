# I3 Session F2 (SOLO retry, one authorised): hover and press dispatch, mode 3 transitions, 2026-11-14

Owner authorisation (2026-11-14): ONE solo retry of Session F with a single defined change: the game window is brought forward and given focus IMMEDIATELY at launch (the focus call and its result are logged). Same Session A rules otherwise: AllowActions true for this session only, one call at a time, abort and report on any anomaly, never touch an SIDropdown. Tightened abort: if the pipe answers game_busy, wait 90 s and then stop and restore exactly as in Session F; at a stall quote the BepInEx LogOutput lines around the silence. If it stalls again: no more solo attempts, the manual session with the owner at the PC follows.

## Log
- 16:45:10  game closed: True
- 16:45:11  verify-stock before: STOCK: 67 of 67 UI bundles equal the stock reference hash; update status: same
- 16:45:11  staged 0.5.1 DLL sha256 EBF1BE4B920AC020EA80389344A8E0C114885A0283520F7CF859490C5089F74A
- 16:45:11  backup C:\Users\Admin\AppData\Local\FM27SkinEditor\backups\inspector-sessionF2-20261114T154511Z; DLL 1C698C3DB45DC59FCF01FDA0C4A8A64819DDC6185982237898FF29638FFD7C6F; cfg 9231F4BB99C0B64B67759FA331D43BBF7AF0D1B9DC7A46D0A313F8711886CE9B (equal the logged baselines)
- 16:45:11  installed 0.5.1 DLL EBF1BE4B920AC020EA80389344A8E0C114885A0283520F7CF859490C5089F74A
- 16:45:11  CONFIG FLIP: AllowActions false -> true for this session only (sha before 9231F4BB99C0B64B67759FA331D43BBF7AF0D1B9DC7A46D0A313F8711886CE9B)
- 16:45:11  cfg now: Enabled = true | DumpFolder = C:\Users\Admin\FMSKINNING\workspace\notes\ui-dumps | AllowActions = true | Enabled = true | Transitions = true; sha 2CF6FB9D19164BBE51A93E687C6E09C232F3028CBA314452BFCFCC6D5D6B4F13
- 16:45:11  launch requested
- 16:45:13  FOCUS at +2s after launch: SetForegroundWindow returned True; game is foreground: True; title 'BepInEx 6.0.0-be.793 - fm'
- 16:45:13  focus established: True
- 16:45:24  NOTE: the first window of the process was the BepInEx console ('BepInEx 6.0.0-be.793 - fm'), not the game's window; focusing it does not satisfy the defined change. Focusing the game window itself as soon as it exists.
- 16:45:24  FOCUS GAME WINDOW at +0s after launch: title 'Football Manager 27', SetForegroundWindow returned False; game window is foreground: False
- 16:45:24  windows of the process seen: 'Football Manager 27', 'BepInEx 6.0.0-be.793+dbc82f05b8ea34833de5b6a723eb60dd8398e0b1 - fm'
- 16:45:35  game window handle 0 (FindWindow by title)
- 16:45:35  game window not found
- 16:45:48  windows of the game process now: 'Football Manager 27', 'BepInEx 6.0.0-be.793+dbc82f05b8ea34833de5b6a723eb60dd8398e0b1 - fm'
- 16:45:48  method 1 (AttachThreadInput + SetForegroundWindow) on 'Football Manager 27': returned False; game window is foreground: False
- 16:45:48  method 2 (ALT tap + SetForegroundWindow): returned True; game window is foreground: True
- 16:45:48  foreground window now: 'Football Manager 27'
- 16:45:48  status (one read): {"v":1,"id":730321,"ms":10.27,"result":{"plugin":"0.5.1-capture","game":"27.0.1.2503222","unity":"6000.3.18f1-custom","scene":"BootToInit","roots":0,"pid":28476}}
- 16:47:10  game_busy first seen: {"v":1,"id":833933,"fault":{"kind":"game_busy","detail":"four requests already waiting"}}
- 16:48:40  game_busy for 90 s: STOP (abort threshold)
- 16:48:56  STALL (second): game_busy for 90 s with the game window confirmed foreground from 16:45:48 and no foreground change logged since. Per the defined rules: stop and restore, no more solo attempts.
- 16:48:56  process: cpu 202 s, responding True, started 16:45:12
- 16:48:56  LogOutput.log last write 16:45:14, 6065 bytes; Player.log last write 16:45:55, 7282 bytes
- 16:48:56  BepInEx LogOutput.log, the last 26 lines at the stall (quoted):
    [Info   :   AutoDev] [Apply]   ctor(Object, IntPtr)
    [Info   :   AutoDev] [Apply]   ctor(IntPtr)
    [Info   :   AutoDev] [Apply]   Void Invoke(UInt32 id, InteropReference action, TypedValue data)
    [Info   :   AutoDev] [Apply]   ActionHandler op_Implicit(Action`3 )
    [Info   :   AutoDev] [Apply]   ActionHandler op_Addition(ActionHandler , ActionHandler )
    [Info   :   AutoDev] [Apply]   ActionHandler op_Subtraction(ActionHandler , ActionHandler )
    [Info   :   AutoDev] [Apply] type FM.GamePlugin.GameInteropSubsystem+ConditionalActionHandler : MulticastDelegate
    [Info   :   AutoDev] [Apply]   ctor(Object, IntPtr)
    [Info   :   AutoDev] [Apply]   ctor(IntPtr)
    [Info   :   AutoDev] [Apply]   Boolean Invoke(UInt32 id, InteropReference action, TypedValue data, VisualElement source)
    [Info   :   AutoDev] [Apply]   ConditionalActionHandler op_Implicit(Func`5 )
    [Info   :   AutoDev] [Apply]   ConditionalActionHandler op_Addition(ConditionalActionHandler , ConditionalActionHandler )
    [Info   :   AutoDev] [Apply]   ConditionalActionHandler op_Subtraction(ConditionalActionHandler , ConditionalActionHandler )
    [Info   :   AutoDev] [Apply] no GameInteropSubsystem yet
    [Info   :   AutoDev] [Apply] SendEvent capture installed
    [Warning:Il2CppInterop] Method System.Collections.IEnumerator Analyze() on type AutoDev.UI.AutoDevBehaviour has unsupported return type System.Collections.IEnumerator
    [Warning:Il2CppInterop] Method System.Collections.IEnumerator ApplyJob(System.String, System.Collections.Generic.IReadOnlyList`1[System.DateOnly]) on type AutoDev.UI.Auto
    [Warning:Il2CppInterop] Method System.Collections.Generic.List`1[System.String] TabNames() on type AutoDev.UI.AutoDevBehaviour has unsupported return type System.Collecti
    [Warning:Il2CppInterop] Method AutoDev.UI.TeamTab <ShowTabs>b__28_0(System.String) on type AutoDev.UI.AutoDevBehaviour has unsupported return type AutoDev.UI.TeamTab
    [Info   :Il2CppInterop] Registered mono type AutoDev.UI.AutoDevBehaviour in il2cpp domain
    [Info   :   AutoDev] [Startup] reader and button driver started
    [Info   :   BepInEx] Loading [AutoDev Probe 0.1.0]
    [Warning:AutoDev Probe] [Probe] Bindings observer disabled by the crash guard (see log).
    [Info   :Il2CppInterop] Registered mono type AutoDev.Probe.ProbeBehaviour in il2cpp domain
    [Info   :AutoDev Probe] [Probe] running; logs in C:\Users\Admin\Documents\AutoDev\probe
    [Message:   BepInEx] Chainloader startup complete
- 16:48:56  Player.log, last non-stack lines:
    [Physics::Module] Threading Mode: Multi-Threaded
    <RI> Initializing input.
    Using Windows.Gaming.Input
    UnloadTime: 0.265000 ms
    No Theme Style Sheet set to PanelSettings NavigationLayerSettings, UI will not render properly
    No Theme Style Sheet set to PanelSettings ColourSpaceConversionLayerSettings, UI will not render properly
    Backtrace native integration status: Cannot initialize Crashpad client
    Backtrace.Unity.Runtime.Native.Windows.NativeClient:HandleNativeCrashes(IDictionary`2, IEnumerable`1) (at ./Library/PackageCache/io.backtrace.unity@c3dc42f2505a/Runtime/Native/Windows/NativeClient.cs:
    Backtrace.Unity.Runtime.Native.Windows.NativeClient:.ctor(BacktraceConfiguration, BacktraceBreadcrumbs, IDictionary`2, IEnumerable`1) (at ./Library/PackageCache/io.backtrace.unity@c3dc42f2505a/Runtime
    Backtrace.Unity.Runtime.Native.NativeClientFactory:CreateNativeClient(BacktraceConfiguration, String, BacktraceBreadcrumbs, IDictionary`2, ICollection`1) (at ./Library/PackageCache/io.backtrace.unity@
    Backtrace.Unity.BacktraceClient:Refresh() (at ./Library/PackageCache/io.backtrace.unity@c3dc42f2505a/Runtime/BacktraceClient.cs:631)
    Backtrace.Unity.BacktraceClient:Initialize(BacktraceConfiguration, Dictionary`2, String) (at ./Library/PackageCache/io.backtrace.unity@c3dc42f2505a/Runtime/BacktraceClient.cs:469)
- 16:48:56  curl errors in Player.log: 2
- 16:49:17  closed by CloseMainWindow after 2s
- 16:49:17  game closed: True
- 16:49:17  log pair preserved: FM27Inspector-actions.log 17408; LogOutput.log 6065; Player.log 7282
- 16:49:17  RESTORED DLL 1C698C3DB45DC59FCF01FDA0C4A8A64819DDC6185982237898FF29638FFD7C6F ok=True; cfg 9231F4BB99C0B64B67759FA331D43BBF7AF0D1B9DC7A46D0A313F8711886CE9B ok=True
- 16:49:18  cfg values: Enabled = true | DumpFolder = C:\Users\Admin\FMSKINNING\workspace\notes\ui-dumps | AllowActions = false  (AllowActions back to false)
- 16:49:18  verify-stock after: STOCK: 67 of 67 UI bundles equal the stock reference hash; update status: same
- 16:49:18  leftover processes: crashpad_handler:16796, crashpad_handler:25092

## Outcome (2026-11-14): STALLED AGAIN, aborted at 90 s of game_busy, nothing dispatched
- Defined change done: the game's OWN window (not the BepInEx console, which is the process's first window) was brought forward; the first plain `SetForegroundWindow` was refused by Windows (returned False), an AttachThreadInput attempt also failed, an ALT-tap + `SetForegroundWindow` succeeded at 16:45:48 (about 37 s after launch, not at once: finding the right window and the failed first attempts cost that time) and the game window stayed in front for the rest of the session (no foreground change was logged).
- The pipe answered with `result` (roots 0, scene BootToInit) at 16:45:48, then `game_busy: four requests already waiting` from 16:47:10; at 90 s of game_busy (16:48:40) I stopped. Process: 202 s CPU, `Responding = True`. Closed by CloseMainWindow after 2 s. Restored by value (DLL 1C698C3D, cfg 9231F4BB, AllowActions false), verify-stock 67 of 67, log pair and the (unchanged, 17,408 bytes) actions log preserved. No hover, press or capture ran.
- **Focus is not the cause** (focused for ~3 minutes, same stall). No more solo attempts, as agreed; the manual session follows.

### The stall point, quoted and compared (all from the preserved log pairs)
- BepInEx `LogOutput.log` last write 16:45:14, 2 s after launch: every plugin loaded and "Chainloader startup complete" was the last line (quoted in the session log). So BepInEx and all plugins (the inspector 0.5.1 included) finished loading normally.
- The AutoDev Probe plugin's own log shows the main loop ALIVE after that: `f=3584` at 16:45:29 and `f=5976` at 16:45:39 (about 240 frames a second), then its last line (`SCHEMA ... 0 types`, 16:45:39). The game's `Player.log` last write is 16:45:55 (about 43 s after launch), ending in the Backtrace crash-reporter initialisation.
- **Working launches (Sessions D and E) show `GAME_PLUGIN::initialise() called` and `Football Manager 27 plugin version ...` in `Player.log` about 22 s after launch; both stalled launches (F and F2) never do.** Player.log has 71 to 73 lines when stalled and 207 to 212 when working; curl (DNS) errors 2 against 6. So the stall is in the game's own start-up, before its game plugin initialises, after the main loop was already running.
- Other differences noted, none shown to matter: this launch's Probe log says its bindings observer was DISABLED by its crash guard (the previous run, Session F, did not end cleanly with the observer on; Session D's launch has the same warning and was fine); two `crashpad_handler` processes from earlier launches are still running; the inspector DLL is 0.5.1 (previous good launches used 0.3.1 and 0.4.0).

### What is still not known, and the cheapest way to find out in the manual session
Whether the cause is 0.5.1, the AutoDev plugins, a leftover process or the machine's state at this hour. **Proposed order for the manual session:** (1) launch once with the restored baseline DLL (0.2.2) and AllowActions false: if it stalls too, the inspector is cleared and the cause is elsewhere (AutoDev, crashpad leftovers, Steam), and 0.5.1 can be tested next; (2) then 0.5.1 with the owner at the PC for the hover holds.
