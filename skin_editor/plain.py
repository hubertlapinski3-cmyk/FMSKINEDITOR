"""Plain words for the engine's own reasons (Simple mode, docs/SIMPLE-MODE-PLAN.md S1).

`plain(message)` turns the text of an engine error into a sentence a person who has never skinned can act on; the raw text stays available
as the details. The table is DATA: tests/test_plain.py reads every `raise` in the user-facing modules (engine, install, native, detect) and
fails when one has no specific sentence, so a new reason cannot ship without its words. A message no rule matches gets the generic sentence
at run time (never an empty one), and the test fails for it at build time."""
import re

GENERIC = "Something went wrong that this screen can't explain. Open Advanced mode to see the details."

# (regex searched in the message, case-insensitive, sentence). First match wins. Sentences say what happened and what to do, with no jargon.
RULES = [
    # -- the game and the one-time reading of it
    (r"no game install selected", "The Studio hasn't found your game yet. Use \"Find my game\" on the start screen."),
    (r"no style index", "The Studio hasn't read the game's styles yet. This is a one-time step: use \"Read the game\" on the start screen."),
    (r"no StreamingAssets/aa/Standalone", "That folder isn't a Football Manager 27 game folder. Pick the one that contains the game's fm.exe (in Steam: steamapps > common > Football Manager 27)."),
    (r"close the game before", "Close Football Manager first, then try again."),
    (r"the game is running or updating", "Close Football Manager, and let Steam finish any update, then try again."),
    (r"no vanilla snapshot yet|take the vanilla snapshot first", "The Studio hasn't read the game yet. Use \"Read the game\" first."),
    (r"the verified source has no", "The build is missing a game file it needs. Read the game again, then build again."),
    (r"does not match the installation identity", "The copy of the game the Studio would build from doesn't match the game it read. Read the game again, then build again."),
    (r"was not found in the serialized UI bundles", "The screen this edit belongs to isn't in the game files the Studio read. Read the game again."),
    (r"needs cell_index and geometry", "That change is missing the tile or its new position. Pick the tile and try the move again."),
    (r"layout bundle .* is not stock", "A game layout file isn't the original any more. In Steam: right-click the game > Properties > Installed files > Verify integrity of game files, then build again."),
    (r"unknown composition","The Studio doesn't know that screen. Read the game again, then pick the screen from the list."),
    (r"holds no custom-layout files", "This build has no layout files to put into the game. Make a layout change on the Playground and build again."),
    (r"vanilla snapshot exists", "The game has already been read; nothing to do."),
    (r"reference hashes already recorded", "The Studio already has its record of the original game files; nothing to do."),
    (r"catalog\.hash was not found", "The game folder doesn't look like a normal Steam install. Check that the game is installed and up to date."),
    (r"the index does not match", "The Studio's notes about the game are out of date. Read the game again (it takes about a second)."),
    (r"the vanilla snapshot was taken from", "The Studio read a different copy of the game than the one now in use. Read the game again."),
    (r"missing in the game folder", "A game file is missing. In Steam: right-click the game > Properties > Installed files > Verify integrity of game files."),
    (r"differs from the vanilla snapshot and from the last install", "The game looks updated since the Studio read it. Read the game again, then try again."),
    # Three different causes, three different sentences: the game was UPDATED (verify first, then the in-app Re-read button), a game FILE was changed (verify or restore), a layout NAME is unknown (a typo, never a reinstall).
    (r"the game has ui bundles the snapshot has no reference for", "The game has layout files the Studio hasn't recorded yet. Read the game again so it can read them together."),
    (r"catalog\.hash changed since the snapshot|was not done\.", "The game was updated since the Studio read it, so the Studio's notes about the game are out of date. Nothing was changed. FIRST verify in Steam "
                                                  "(right-click Football Manager 27 > Properties > Installed files > Verify integrity of game files, and let it finish, because an update leaves untouched files alone and a skin can still be in them). "
                                                  "THEN, with Football Manager closed, use the Re-read the game button on the Studio's Game updates screen (if the Studio will not start: open PowerShell and run "
                                                  "`& \"$env:LOCALAPPDATA\\FM Skin Studio\\fm-skin-engine\\fm-skin-engine.exe\" snapshot --force`, then the same with `index` in place of `snapshot --force`). "
                                                  "Verify alone does not read the game again for the Studio."),
    (r"not snapshotted|not re-read", "A game file is still a skin this Studio installed earlier, so it was not recorded as the game's own. In Steam, right-click Football Manager 27 > Properties > Installed files > Verify integrity of game files, let it finish, then use the Re-read the game button (or take the snapshot) again."),
    (r"would mix two game builds", "That backup was made for an older version of the game, so it was not put back: it would mix two versions. Nothing was changed. Take a new snapshot of the updated game instead."),
    (r"no layout named", "No layout with that name exists in this version of the game. Check the spelling, or pick one from the list."),
    (r"no layout index is configured|the layout index is not configured|the layout index .* does not exist", "The Tiles view needs a layout index, which comes from FM27_LayoutMCP, a developer-only tool that isn't shipped with the Studio. Set FM27_LAYOUT_INDEX (or \"layout_index\" in the workspace config.json) to use it."),
    (r"no such composition", "That screen layout isn't in the game data this Studio read. Pick a screen from the list, or read the game again if it was updated."),
    (r"no such node", "That element isn't in this screen's reconstruction. Reopen the screen and pick it again."),
    (r"address the node by", "Pick the element on the canvas or in the tree first, then edit it."),
    (r"no joined node at render position", "That element isn't drawn by the reconstruction, so it can't be edited here. Pick a drawn element."),
    (r"is shared by %d instances", "That element appears in more than one tile of this screen. Pick it in a specific tile, or edit it by name from the list."),
    (r"not drawn by the render", "That element isn't drawn by the reconstruction (it's a container or a background component), so it can't be edited here."),
    (r"no applied sheet", "That style sheet isn't in the game's styles of this build. Read the game again if it was updated."),
    (r"playground session lives in the project folder", "This project is in the older single-file format, which has no folder to keep Playground edits in. Re-save the project (any edit and save upgrades it), then try again."),
    (r"must be an fm-playop/1 record", "That edit record isn't in the form the Studio produces. Make the edit again in the Playground."),
    (r"redo names the operation", "Pick the edit to re-do from the Playground's history."),
    (r"add needs the new cell's", "Name the new tile (its element id) first, then place it on the grid."),
    (r"geometry needs integer x, y, w, h", "Place or size the tile on the grid again (whole grid steps only)."),
    (r"build_operation builds the screen-canvas kinds", "That kind of edit isn't made on the screen canvas. Make it in the element editor instead."),
    (r"not the stock file|are not stock|not the snapshot's stock file|tamper check", "A game file has been changed from the original (a test, or another skin). Put the originals back (in Steam: Verify integrity of game files), then try again."),
    (r"no reference hash", "The Studio needs a record of the original game files first. Close the game and use \"Read the game\"."),
    (r"not an image bundle", "That game file isn't one of the picture files."),
    # -- safety checks while copying
    (r"copy mismatch|verify mismatch|backup copy mismatch", "Copying a game file failed its safety check, so nothing was left half done. Try again; if it repeats, check your disk."),
    (r"install failed and the previous files were restored", "The install failed and your original game files were put back."),
    (r"structural gate", "This build didn't pass the Studio's safety check, so it was not put into the game."),
    (r"no bundles in", "That backup is empty."),
    (r"no verified stock backup", "A verified copy of the original game file is missing, so nothing was installed. Put the original game files back first (Restore stock, or Steam: Verify integrity of game files), then try again."),
    (r"older than the project's last change", "This build package is older than the latest changes in your project. Build again first, or confirm that you want to install the older package."),
    (r"not restored", "That backup belongs to a different game folder, so it was not restored."),
    # -- projects and skins
    (r"a project with that name exists", "A project with that name already exists. Choose another name."),
    (r"no project named", "There is no project with that name."),
    (r"fails the contrast check", "This theme would make some text hard to read, so it was not made. Change one of the three colours and try again."),
    (r"this game build does not have", "This version of the game has changed some of the colours a theme sets, so the theme was not made. Read the game again; if it repeats, update FM Skin Studio."),
    (r"a theme colour must be", "Each of the three colours must be a plain colour like #1A2B3C."),
    (r"light themes are not in this version", "Light themes aren't available in this version; themes made from three colours are dark."),
    (r"mode must be dark", "Themes made from three colours are dark in this version."),
    (r"no such inventory bundle|no such inventory asset", "That file or asset isn't in the Studio's list of the game's files. Scan the game's files again, then pick it from the list."),
    (r"no such token", "That colour name is not in the game's styles of this build."),
    (r"no such preset", "That ready-made theme isn't available."),
    (r"no build for this project", "Nothing has been built for this project yet."),
    (r"target must be one of", "That way of putting the skin into the game isn't available."),
    (r"skin folder name", "Use only letters, digits, dots, dashes and underscores in the skin's name."),
    (r"confirm is required to start over", "Please confirm first; nothing was changed."),
    (r"confirm is required", "Please confirm first; nothing was removed."),
    (r"a skin file must end in \.zip", "Save the skin file with a name that ends in .zip."),
    (r"that file exists; choose another name", "A file with that name is already there. Choose another name, or confirm replacing it."),
    (r"that is not a skin file", "That file isn't a skin file. A skin file is a .zip, for example one saved with \"Save my skin as a file\"."),
    (r"has no skin\.json", "That file doesn't hold a skin for the game's skins folder (there is no skin.json inside), so nothing was made from it."),
    (r"lists sheets it does not hold", "That skin file is incomplete (some of its style sheets are missing), so nothing was made from it."),
    (r"a path that leaves its folder", "That skin file tries to put files outside its own folder, so it was not opened. It may be damaged or unsafe."),
    (r"holds too many files|unpacks to more than", "That skin file is far larger than a skin, so it was not opened."),
    (r"skin\.json has no Sheets list", "That skin's skin.json lists no style sheets, so there is nothing to open."),
    (r"sheet listed in skin\.json is missing", "That skin is incomplete (a style sheet it lists is missing), so nothing was made from it."),
    (r"is not removed", "That folder wasn't made by this Studio, so it isn't touched. Remove it yourself if you are sure."),
    (r"was not written by this editor", "A skin with that name is already in your skins folder and was not made by this Studio. Choose another name."),
    (r"collides with a file this export writes|has the same name as a file this export writes", "A file of the skin you imported clashes with one this Studio writes. Rename it and try again."),
    (r"changes nothing yet", "You haven't changed anything yet, so there is nothing to put in the game. Open Colours and change something first."),
    (r"no skin folder to remove", "There is no skin of that name in your skins folder to take out."),
    (r"no FM27 user folder", "I couldn't find your Football Manager 27 documents folder. Start the game once so it creates it, or choose where to save the skin."),
    (r"only export folders can be opened|only a live-preview screenshot", "That file can't be opened from here."),
    # -- pictures and fonts
    (r"pick a PNG screenshot|a screenshot is at most 30 MB", "Pick a PNG screenshot (a picture of the game, up to 30 MB)."),
    (r"a screenshot with that name is already there", "A screenshot with that name is already there. Choose another name."),
    (r"bad screenshot name", "Use only letters, digits, spaces, dots, dashes, underscores and brackets in the name, ending in .png."),
    (r"no screenshot named", "That screenshot isn't in the list any more."),
    (r"pick an image file|send the image file|not an image|an image slot takes|an icon takes|an SVG slot takes", "Pick a picture file (PNG, JPG or WebP; an SVG only for an SVG slot), up to 40 MB."),
    (r"bad file name|bad bundle or path_id", "That file name isn't usable. Use only letters, digits, dots, dashes and underscores."),
    (r"no stored replacement", "Choose a picture for this slot first."),
    (r"no such image swap|no such image|no image with path id|no such asset|bundle not in the comparison", "That picture isn't in the list any more. Pick it again from the list."),
    (r"nothing matches the filter", "Nothing matches that filter; clear it to see everything."),
    (r"pick a \.ttf or \.otf|not a TrueType|font file name must", "Pick a font file (.ttf or .otf, up to 30 MB) whose name uses only letters, digits, dots, dashes and underscores."),
    (r"no font is assigned", "No font is set for that item yet."),
    (r"no comparison loaded", "Load a skin to compare with first."),
    (r"skin folder not found", "That skin folder was not found. Check the path and try again."),
    (r"no such composition in skin folder", "That composition was not found in the inspected skin folder."),
    (r"favourites must be a list of composition names", "Favourites must be saved as a list of screen names."),
    (r"unknown tile description", "That tile description was not found in the game's tile bundle."),
    (r"does not belong to .* never create a new GUID", "Adding a tile size must reuse an existing layout GUID of that tile description."),
    (r"action must be 'add' or 'remove'", "Choose whether to add or remove the tile from the element set."),
    (r"unknown GridElementSet", "That screen element set was not found in the game's tile bundle."),
    (r"ui-tileslayouts_assets_all\.bundle is not available", "The game's tile layouts bundle is not available in the game folder or snapshot."),
    (r"tile sizes is experimental", "Tile sizes is turned off by default as an experimental feature. Turn on 'experimental: tile sizes' in BUILD to use it."),
    # -- views that need data the game must provide
    (r"no layout dump", "This view needs a layout file exported from the game, which hasn't been set up. Simple mode doesn't need it."),
    (r"the imported layout dump is|re-export or re-import a dump", "The Studio's layout file doesn't match the game's files any more (an update, or modified files). Re-export the layout file for this game version, then try again."),
    (r"no such sheet|no rule .* in sheet|docs/INGAME-CHECKLIST\.md is missing", "That item isn't available in this install. If it should be, reinstall FM Skin Studio or read the game again."),
    # -- Stage 4D: the typed build plan's refusals and reads
    (r"the build is refused", "The build was stopped before anything was written, because of the problem in the details. Fix that problem, or - if you are sure - start the build with the matching allow option; the exception is then recorded in the build manifest."),
    (r"tiles would overlap|tile_overlap", "Two tiles would sit on top of each other, and the game has been seen to drop a tile when that happens. Move the tile so it does not overlap, or - if the overlap is deliberate - allow it and the build records the exception."),
    (r"impact is unresolved|impact_unresolved", "This edit changes more than a value inside one asset, and its effects on other files are not fully known. Resolve what it points at, or - if you are sure - allow it and the build records the exception."),
    (r"unknown_edit_kind|cannot be classified safely", "This edit is of a kind the Studio cannot judge safely, so the build was stopped. Nothing was written."),
    (r"no copy of .* exists|not in the vanilla snapshot and not in the game folder", "The Studio can't see that file. Read the game again, or pick the file from the list."),
    (r"no object with path id .* in", "That asset isn't in that file any more (the game may have updated). Pick it again from the list."),
    # -- Stage 4E: catalog and integrity reporting
    (r"no such installation profile", "The Studio hasn't got a record of that game folder yet. Use \"Find my game\" on the start screen, then try again."),
    (r"catalog parse failed|catalog_parse_failed", "The game's catalog file could not be read with the format this Studio knows. Nothing was changed; report the details if this keeps happening."),
    (r"catalog.*unsupported|unknown catalog magic|unsupported catalog version", "The game's catalog file is a version this Studio cannot read yet (it may belong to a newer game). Nothing was changed."),
    # -- Stage 4F: installation transactions
    (r"the installation was refused", "Nothing was installed. The details list what stopped it; some warnings can be confirmed explicitly, the blocked conditions cannot."),
    (r"needs explicit confirmation|confirmations required", "Installing this needs your explicit confirmation for the warnings in the details (a changed file or a checksum that will not match). Confirm each one to proceed; the confirmation is recorded."),
    (r"stale_game_build|the package was built for game build", "This package was built for a different version of the game. Read the game again and rebuild it; two game versions must not be mixed."),
    (r"stale_installation_identity", "The game folder no longer matches the record the Studio keeps of it (it was probably updated). Use \"Find my game\" again, then rebuild."),
    (r"incomplete_transaction", "An earlier installation was left unfinished. Recover or roll it back on the installation page before installing anything else."),
    (r"changed_target", "A file in the game folder changed since the package was built, and it was not changed by this Studio. Nothing was overwritten; restore the original (Steam: Verify integrity of game files) or confirm the change explicitly."),
    (r"missing_target|is not in the game folder", "A file the package would replace is missing from the game folder. Read the game again, then rebuild."),
    (r"unsafe_path|not a safe bundle name", "The package names a file that cannot be installed safely, so nothing was installed. This can never be confirmed away; rebuild the package."),
    (r"backup did not verify|backup is missing or corrupt", "The safety copy of a file could not be made or checked, so nothing was installed."),
    (r"no such transaction", "There is no installation record with that identity."),
    (r"manual_intervention|manual intervention required", "The installation (or its rollback) hit a state that needs a person to decide. Nothing conflicted was overwritten; see the transaction's details."),
    (r"no such variable in inspected skin", "That CSS variable is not defined in the inspected skin's stylesheet."),
    (r"no matching rule for class", "No rule in the inspected skin matches that class name."),
    (r"matched rule\(s\) use only unencodable", "The matched rule only contains properties or asset URLs that cannot be written safely into a bundle rule."),
]
_COMPILED = [(re.compile(rx, re.I), sentence) for rx, sentence in RULES]


def match(message):
    """The specific sentence for a message, or None."""
    for rx, sentence in _COMPILED:
        if rx.search(message or ""):
            return sentence
    return None


def plain(message):
    """{"plain": sentence, "details": the engine's own text}; the generic sentence when no rule matches."""
    return {"plain": match(message) or GENERIC, "details": message or ""}
