# Phase 5 evidence (2026-11-13)

## 1. Profile diff across two real builds

| | old | new |
|---|---|---|
| game build | 27.0.1.2494769 (label given by the user) | 27.0.1.2503222 (confirmed live: the inspector's `status` reported `game 27.0.1.2503222` on 2026-11-13) |
| profile id | `27.0.1.2494769-b3067d4518ba` | `27.0.1.2503222-dfa1892e861e` |
| catalog.hash | `b3067d4518bae634aa41883811b94345` | `dfa1892e861eef5fd9c26d5c909a552f` (live `catalog.hash`) |
| style bundles (sha256 prefix) | common `f8d2e274`, default `8afaf42e` | common `21a642f5`, default `28d4f719` |
| source | `...\FM Blog Classic Skin 112 Restore\original\game\...\StandaloneWindows64` (same hashes also in `D:\drive\FM27-Crimson\workspace\vanilla\2026-11-02`) | the vanilla snapshot of 2026-11-13 |
| tokens / sheets / rules | 2059 / 49 / 13020 | 2059 / 49 / 13028 |

Caveats, stated plainly: the old bundles carry no version stamp, so the build label is the user's. The old `catalog.hash` is the one that sits next to a byte-identical `catalog.bin` (md5 `071fc7e6...`) in `Downloads\FM VANILLA\aa`; the Restore folder has the `catalog.bin` but no `catalog.hash`. Only the two style bundles of the old build exist on disk, so icons and layouts could not be compared for this pair (the diff says so instead of guessing).

Result (`profiles/diffs/diff-27.0.1.2494769-b3067d4518ba__27.0.1.2503222-dfa1892e861e.json`):

- tokens: 0 added, 0 removed, 0 changed (the patch did not touch tokens);
- rules: 3 selectors vanished (`.news-team-site .site-header-container, .nation-site ...` in SIStyles, one `.height-auto` group and `.pot-list-wrap > ComponentElement` in AlwaysAppliedStyleSheet), 7 new, 10 moved or changed (for example the `.sicheckbox ... :checked ... __checkmark` background-image: the old bundle stores the value with value type 13, the new one as an asset reference; type 13 is not decoded, so it shows as a change to review);
- sheets: the same 49;
- icons and layouts: not compared (old icon bundles and layout dump are not on disk).

Per-item states on that real diff (throwaway project items): a token that exists = ok; a token that does not exist in the new build = target gone; a `replace:` on a selector that vanished = target gone; a `replace:` on the `.sicheckbox` rule = vanilla value changed; a `replace:` on a made-up selector = target gone; an appended rule = ok. The real projects `Mine` (58 items) and `jonukas-dark-paper` (1 item) are all ok on the new build. `target moved` and the auto-fix are covered by unit tests (tests/test_update.py) because this patch moved no token or rule.

The diff closes the exit criterion for style tokens and rules; icon and layout comparison close at the next FM patch, when both profiles can be scanned with icon classes (Scan game records them) and a layout dump.

## 2. Live preview loop (Windows)

Game 27.0.1.2503222, BepInEx plugin FM27 Crimson Inspector 0.2.2, `AllowActions = true`, Preferences screen of a throwaway session, 2026-11-13 ~16:11 local.

- `skin_editor/live.py` run against the real pipe: exported the skin, `status` (game 27.0.1.2503222), `find` "Reload Skin" (visible), `click` (dispatched through the SIButton), `screenshot` (written by the game a frame later, 4 MB file, waited for). Only `native.export` runs; bundles are never touched (a test patches `patcher.build` and `install.install` to fail if called).
- Visible proof: a temporary rule `#reload-skin-button, #skin-chooser { background-color: #FF00FF }` was written into the selected skin and the loop clicked Reload Skin. The user saw magenta in the game, and a screenshot taken through the pipe shows the Reload Skin button at pixel (1200,1050) = (243,155,243) and the skin chooser (255,36,255), against (167,168,172) and (65,68,77) in the baseline. The real Mine export was then restored (53 tokens, 190 rules, 3 images, 0 problems) and the loop reloaded it: the pixel went back to a non-magenta value.
- Measured reload latency: 3.0 s (restore) and 7.7 s (apply), so `live.run` waits 10 s after the click before the screenshot (a 1.5 s wait missed the change).
- Without the game: `preview.live` returns `mode: static` with the reason ("FM27 is not running with the inspector plugin (no \\.\pipe\fm27-crimson-inspector pipe)") and the UI shows the static repaint of a measured screen. Seen for real before the game was started. With the game on another screen (no Reload Skin button visible) the loop still screenshots and says "open Preferences (cog) > Skin ...".
- Not automated: choosing the `<name>-preview` skin in the Preferences drop-down. A plain click does not open the SI drop-down through the bridge, so the first time the user picks the skin once; after that the loop refreshes it. For the proof above the loop wrote into the skin that was already selected (`skin_id`).

## 3. Found and fixed on the way

- `native.export` removed an existing skin folder before it knew the new export would work; an exception half-way (a bad `aa_dir`) left the user's `skins\Mine` empty and without its marker. It now writes next to the target and swaps in only on success (test: a failing export leaves the old skin byte-identical). The Mine skin was restored from the project.
- The first version of the rule comparison flagged duplicates of one selector inside a sheet; it now compares what all rules with that selector add up to (20 -> 10 reported changes).
