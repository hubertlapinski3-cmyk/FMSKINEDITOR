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
    (r"vanilla snapshot exists", "The game has already been read; nothing to do."),
    (r"reference hashes already recorded", "The Studio already has its record of the original game files; nothing to do."),
    (r"catalog\.hash was not found", "The game folder doesn't look like a normal Steam install. Check that the game is installed and up to date."),
    (r"the index does not match", "The Studio's notes about the game are out of date. Read the game again (it takes about a second)."),
    (r"the vanilla snapshot was taken from", "The Studio read a different copy of the game than the one now in use. Read the game again."),
    (r"missing in the game folder", "A game file is missing. In Steam: right-click the game > Properties > Installed files > Verify integrity of game files."),
    (r"differs from the vanilla snapshot and from the last install", "The game looks updated since the Studio read it. Read the game again, then try again."),
    (r"not the stock file|are not stock|not the snapshot's stock file|tamper check", "A game file has been changed from the original (a test, or another skin). Put the originals back (in Steam: Verify integrity of game files), then try again."),
    (r"no reference hash", "The Studio needs a record of the original game files first. Close the game and use \"Read the game\"."),
    (r"not an image bundle", "That game file isn't one of the picture files."),
    # -- safety checks while copying
    (r"copy mismatch|verify mismatch|backup copy mismatch", "Copying a game file failed its safety check, so nothing was left half done. Try again; if it repeats, check your disk."),
    (r"install failed and the previous files were restored", "The install failed and your original game files were put back."),
    (r"structural gate", "This build didn't pass the Studio's safety check, so it was not put into the game."),
    (r"no bundles in", "That backup is empty."),
    (r"not restored", "That backup belongs to a different game folder, so it was not restored."),
    # -- projects and skins
    (r"a project with that name exists", "A project with that name already exists. Choose another name."),
    (r"no project named", "There is no project with that name."),
    (r"no such preset", "That ready-made theme isn't available."),
    (r"no build for this project", "Nothing has been built for this project yet."),
    (r"target must be one of", "That way of putting the skin into the game isn't available."),
    (r"skin folder name", "Use only letters, digits, dots, dashes and underscores in the skin's name."),
    (r"was not written by this editor", "A skin with that name is already in your skins folder and was not made by this Studio. Choose another name."),
    (r"collides with a file this export writes|has the same name as a file this export writes", "A file of the skin you imported clashes with one this Studio writes. Rename it and try again."),
    (r"no FM27 user folder", "I couldn't find your Football Manager 27 documents folder. Start the game once so it creates it, or choose where to save the skin."),
    (r"only export folders can be opened|only a live-preview screenshot", "That file can't be opened from here."),
    # -- pictures and fonts
    (r"pick an image file|send the image file|not an image|an image slot takes|an icon takes|an SVG slot takes", "Pick a picture file (PNG, JPG or WebP; an SVG only for an SVG slot), up to 40 MB."),
    (r"bad file name|bad bundle or path_id", "That file name isn't usable. Use only letters, digits, dots, dashes and underscores."),
    (r"no stored replacement", "Choose a picture for this slot first."),
    (r"no such image swap|no such image|no image with path id|no such asset|bundle not in the comparison", "That picture isn't in the list any more. Pick it again from the list."),
    (r"nothing matches the filter", "Nothing matches that filter; clear it to see everything."),
    (r"pick a \.ttf or \.otf|not a TrueType|font file name must", "Pick a font file (.ttf or .otf, up to 30 MB) whose name uses only letters, digits, dots, dashes and underscores."),
    (r"no font is assigned", "No font is set for that item yet."),
    (r"no comparison loaded", "Load a skin to compare with first."),
    # -- views that need data the game must provide
    (r"no layout dump", "This view needs a layout file exported from the game, which hasn't been set up. Simple mode doesn't need it."),
    (r"no such sheet|no rule .* in sheet|no layout named|docs/INGAME-CHECKLIST\.md is missing", "That item isn't available in this install. If it should be, reinstall FM Skin Studio or read the game again."),
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
