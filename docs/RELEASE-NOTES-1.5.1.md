# FM Skin Studio 1.5.1

Maintenance release adding FM27 `27.1.1` compatibility and clearer game-update recovery:

- **Support for FM27 `27.1.1` (`27.1.1.2511875`):** verified custom layouts and carried-over layout measurements on the updated build.
- **"FM27 was updated" banner & flow:** shows a launch banner whenever FM27's catalog changes, with a one-click **Reread now** button and clear summary, plus plain-words guidance on why Restore stock refuses old-build backups until reread completes. **Game Layouts** remains usable throughout.
- **Build-tagged confidence labels:** measurements record their source build (e.g., `measured (27.1.0, carried over to 27.1.1)`).
- **Medium & Large Information Display profiles:** added `2560x1440 fullscreen, Medium, Larger` and `2560x1440 fullscreen, Large, Larger` to Game Layouts.

If you installed bundle edits (styles, tile sizes, allowed tiles) before the FM27 27.1.1 update: run Verify integrity of game files in Steam, click Reread now in Studio, then build and install your project again. Custom layouts made in Game Layouts are not affected and keep working.
