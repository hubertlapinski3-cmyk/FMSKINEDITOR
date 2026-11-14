# FM27 Crimson Inspector: capture modes (work item of 2026-11-14)

Source of the inspector plugin (copied from `D:\drive\fm-mcp\fm27`, which stays untouched) with the new **capture modes** of docs/PHASE9-PLAN.md section 9b.
Everything here is **staging only**: the plugin has been compiled to `inspector\staging\capture-0.3.1\FM27Inspector.dll` and has **not** been installed into the game and
**not** run in game. **Owner approval (2026-11-14): install of capture-0.3.1 is granted for Session B**, which runs only after the M0 session (Session A, with the currently installed
inspector, DLL untouched) has been recorded. Before Session A the installed config was set to `AllowActions = false` (backup `backups\inspector-cfg-20261114T085426Z`).

## Status

| Mode | State |
|---|---|
| 1 `styles`: whole-tree resolved styles, classes, inline styles, bounds | **written, compiles**, not run in game |
| 2 `sources`: which VisualTreeAsset each subtree was instantiated from | **written, compiles**, not run in game; reads `VisualElement.visualTreeAssetSource` by name at run time and says in the capture header whether this engine build has it |
| 3 class transition log | not built (milestone I3); answers `not_implemented` |
| 4 binding value capture | not built (milestone I2); answers `not_implemented` |

Offline side, built and tested on synthetic captures: `skin_editor/render/captures.py` (`read_capture`, `template_sources`, `match_layouts`, `expectations`), tests `tests/test_captures.py`.

## Rules the code enforces (from the owner's work item)

Read-only (no click, scroll, focus or bind anywhere in `Capture.cs`); **hook-free** (property reads only: nothing patches a game method); **cfg-gated and off by default**
(`[Capture] Enabled` plus one key per mode, all `false`); session-scoped (one session at a time, started and stopped through the pipe, auto-stop after `MaxSeconds` /
`MaxFrames`, released on plugin unload); output only to `DumpFolder` (outside the game folder), one JSON object per line so an aborted session leaves a valid partial file;
per-frame main-thread use capped by `FrameBudgetMs` (default 8 ms); an element that disappears mid-session is skipped, never fatal; every read inside `try/catch`.

## Hook rules from the FM26 crash map (for modes 3 and 4 and any future observer)

Read from `E:\d\drive\autotraining\scratch\handover_section13.md` and `handover_section14.md` (FM26 project, run 6). Never backend-patch a method with a byref `ReadOnlySpan` parameter
(the generated detour proxy re-marshals through the broken wrapper regardless of the handler's signature; run 6 crashed at startup under `SI.Bindable.Bindings::Bind`); only span-free overloads
are patchable; open generics fail backend init (log and skip); the heaviest crash window is save load; every delegate handed to the game lives in a static field, created once, with no
managed-type parameters; never `TypedValue.TryGet<System.Object>` (uncatchable fatal); a reentrancy flag around the plugin's own calls is mandatory wherever a method is patched; every launch logs
the live overloads and the cfg state (this build logs `[Capture] startup: hooks=none ...`); everything cfg-gated, observers off by default, one cfg key disables them without a rebuild.
Modes 1 and 2 patch nothing, so none of this reaches them.

## Config keys added (`BepInEx\config\app.hubert.fm27inspector.cfg`)

`[Capture]` `Enabled`, `Styles`, `Sources`, `Transitions`, `Bindings` (all false), `FrameBudgetMs` (8), `MaxSeconds` (90), `MaxFrames` (6000).

**Found while preparing:** the installed config has `AllowActions = true` (the click and scroll tools that crashed the game on a dropdown) and `MainThreadBudgetMs = 600`.
The capture modes need neither; the install steps below set `AllowActions = false`.

## Tools (pipe `fm27-crimson-inspector`; `inspector\tools\inspect.ps1 <tool> <json>`)

- `capture_start {"mode": "styles" | "sources", "sources": true|false, "path": "P0/...", "tag": "squad-overview"}`: starts the session and returns its status. `styles` captures
  every element (`resolved`, `inline`, `world` and `layout` boxes, `pseudo`, `classes`, `text`, `sheets`); add `"sources": true` for mode 2 in the same walk; `"mode": "sources"` alone is the cheap
  template-source walk. Output: `ui-dumps\styles-<tag>-<timestamp>.ndjson` (or `sources-...`).
- `capture_status {}`: state (`running`, `done`, `limit`, `stopped`, `aborted`, `failed`), elements, skipped, frames, seconds, pending.
- `capture_stop {}`: ends the session at once; the file gets its footer.

## Install runbook (needs the owner's approval; the game must be closed)

1. Back up, to `%LOCALAPPDATA%\FM27SkinEditor\backups\inspector-<timestamp>\`: the installed `BepInEx\plugins\FM27Inspector\FM27Inspector.dll` (currently 48,640 bytes,
   sha256 `1C698C3DB45DC59F...`) and `BepInEx\config\app.hubert.fm27inspector.cfg`. Log both hashes.
2. Copy `staging\capture-0.3.1\FM27Inspector.dll` over the installed DLL; log its hash.
3. Config for the session only: `[Inspector] AllowActions = false`; `[Capture] Enabled = true`, `Styles = true`, `Sources = true`.
4. Start the game; `inspect.ps1 status` must report plugin `0.3.1-capture`; then one capture at a time, game state untouched (the owner navigates by hand, as in earlier sessions).
5. When the session is over, close the game, restore the backed-up DLL and config, verify both hashes equal the logged ones, and run `verify-stock` (the UI bundles are not
   touched by any of this).

## Offline use of a capture

```
from skin_editor.render import captures
c = captures.read_capture(r"C:\Users\Admin\FMSKINNING\workspace\notes\ui-dumps\styles-squad-overview-20261114-120000.ndjson")
c.summary()                         # complete? skipped? what the plugin and game versions were
c.template_sources()                # mode 2: every subtree and the layout it came from
captures.match_layouts(c, rows)     # resolve those names (and content hashes) to bundle + path id
c.expectations(paths)               # exact measured values for a calibration fixture
```

## Limits to remember

`IResolvedStyle` does not expose every USS property (transitions, cursor, the hidden ids appear only as inline values when set); a capture is one moment, not a recording;
mode 2 shows the template source only where the engine records one (elements created in code have none). Each capture says so in its header and footer; nothing is filled in.

## 0.3.1 (2026-11-14)

Adds the `sheet_content` capture line (rule content, signature and sample of every sheet attached to a captured element, so the three empty-named root sheets can be matched by content; Capture.match_sheets). DLL sha256 `7940B49F...C1665`, 61,440 bytes. Default `DumpFolder` is now `C:\Users\Admin\FMSKINNING\workspace\notes\ui-dumps`. Restore baselines after the C move: installed DLL `1C698C3D...`, installed cfg `9231F4BB...`. Staged 0.3.0 is kept in `staging\capture-0.3.0`.

## 0.5.0 (2026-11-14)

Adds mode `transitions` (polling, no hook): `capture_start {mode: transitions, tag, path?}`, gated by `[Capture] Transitions = true`; one line per class or pseudo-state change of the watched elements, re-walk every 45 frames for new elements, cap 40,000 watched. DLL sha256 `162C69A9...4423A`, 66,560 bytes; not yet run in game. Reader: `Capture.transition_summary()`.
