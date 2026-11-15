## FM Skin Studio 1.1.1

A repair release. Nothing about what the render draws, or how it is measured, has changed.

### What was wrong
In the installed app (1.0.0 and 1.1.0) the **Images view could not draw the game's icons**, and any other screen that needed one of them showed an error mentioning `fmod.dll`. SVG pictures and most textures were not affected. The problem was in how the app's engine was packaged, not in your projects or your game, and nothing was written to your game files.

### What changed
- The engine now includes what its picture decoders need at run time, and no longer tries to load an audio library it never uses (so no audio library is shipped either).
- **A failed call now leaves its full error in the engine's log**, which used to stay empty: `%LOCALAPPDATA%\FM27SkinEditor\logs\app.log`. If something goes wrong, that file is what to send.
- Every build of the engine now checks itself before it can be released: the picture code must load, and a deliberately failing call must leave its error in that log.

### Updating
Installed copies update through **Check for updates**, then **Install and restart**. If the update does not work, this release also carries the full installer (`FM.Skin.Studio_1.1.1_x64-setup.exe`): download it from this page and run it over your current copy. Your projects and settings are kept.

### What this release does not cover
- The self-check covers reading pictures and the error log. **Writing changed game bundles** (the Advanced "Build bundles" route) is not covered by it yet; that is planned before the next feature release.
- **No calibration report is attached to this release, on purpose:** the render is unchanged, so the calibration report of 1.1.0 stands unchanged and lives on the **v1.1.0 release page** (`calibration-report-1.1.0.md` and `.json`).
- Everything in the notes of 1.1.0 about the approximation still applies: it is an approximation, never the game. Use the PREVIEW tab to see your skin in the running game.
