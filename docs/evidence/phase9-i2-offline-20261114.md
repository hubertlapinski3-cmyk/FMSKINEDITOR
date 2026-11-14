# Phase 9 I2 (mode 4, binding values): offline part (2026-11-14)

Built and measured offline from the Session C and D captures and the interop member list; nothing was run in game. The plugin build is staged, not installed.

## What the existing captures already give (no new plugin)
Mode 1 records `text` for every element, so the DELIVERED value of a bound SIText is already in every capture: Squad overview 460 of 461 visible SIText with width hold text (1 empty), Team Instructions 204 of 204, Inbox 647 of 647. `Capture.delivered_texts()` returns them with widths, optionally for one subtree.

## What the layouts give
- In the five Squad tile layouts read (Loans, Medical Centre, Tactics, Atmosphere, Training: 27 SIText nodes) the uxml `bindingPath` attribute is EMPTY on all 27: the binding is wired from code, not named in the layout. So a binding PATH cannot be read from the bundles.
- Each SIText does carry the designer's sample string, `DebugDisplay` ("7 players injured", "Title", "5 Players") and `TextCase`. The render now uses it as the placeholder text where no text is set (TextCase 1 = upper case): it is the game's own data, a SAMPLE whose width approximates the delivered text, never the text itself.
- Effect on the bound-text width gap (LoansTile_4x2 vs the c2 dump): the title `AutoScroller` was 0 wide (expected 32.2, delta -32.2); with the sample it is 38.1 (delta +5.9). It still FAILS the strict tolerance (5 percent of 32.2 = 1.6 px) and is EXPLAINED rather than closed: the sample is "Title" where the game delivered another string, and the stand-in font is not the game's (M4). The spike stays 16 of 17; every other row unchanged.

## What reading can reach (interop member names; plugin source compiles against them)
`SI.Bindable.SIText` members: `m_binder` (type `Binder`: `m_target`, `m_section`, `IsBound`, `IsReady`, `ToString`), `m_textBinding` (a generic `BindingMethod<SIText>`, set-only property `TextBinding`), `m_bindingHandler`, `m_embeddedData` (generic list), `m_stylingKey`, `text`, `DebugDisplay`. Plugin 0.4.0 reads only the non-generic `Binder`: `IsBound`, `IsReady`, `ToString()`. It does NOT touch `BindingMethod<SIText>` or the embedded-data list (FM26 crash map: open generics fail) and patches nothing. A path may not be reachable by reading at all: that decision is made on the first run's data, then the observer is considered, with the crash-map check, only if the owner wants it.

## Built
- Plugin `0.4.0-capture`, `inspector/staging/capture-0.4.0/FM27Inspector.dll`, 62,464 bytes, sha256 `8722B30B8328E81081197B35E27714E2A1819BE29ED7E8F32BFA163F6F5BA00A`. Adds `bindings: true` to a styles/sources capture: each SIText gets `binding: {isBound, isReady, binder}` (unreadable members named, never filled). Gated by `[Capture] Bindings = true` (default false). Startup line says `hooks=none`.
- Readers: `Capture.delivered_texts()`, `Capture.bindings_summary()` (counts, distinct binder strings, says so when the flag is absent); tests in tests/test_captures.py (Bindings).

## I2 exit, honestly
Exit asked for: every SIText gets its binding path and delivered value, the render's placeholders use them, the width gap closes or is explained. Delivered value: done from mode 1. Placeholders: the layout's sample text now; the delivered text of a capture can replace it (reader ready, applying it to a render is the next offline step). Width gap: explained, not closed. **Binding path: NOT delivered**, open until the first in-game run of 0.4.0 shows what `Binder.ToString()` yields.

## Next game dependency
First run of 0.4.0 (reading): install-restore round trip as before (backup DLL 1C698C3D and cfg 9231F4BB, `[Capture] Bindings = true` for the session), read-only, owner navigates. Batch with it, as agreed, a windowed-mode resize attempt for the Standard composition.