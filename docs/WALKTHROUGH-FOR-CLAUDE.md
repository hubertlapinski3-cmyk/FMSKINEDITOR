# Walkthrough brief for a screen-driving Claude (sections D to I of the eyeball checklist)

**Paste this whole file to a Claude that can drive a screen** (Claude in Chrome, or computer use in the Claude desktop app). It follows the checklist in `docs/S1-EYEBALL-CHECKLIST.md` in the Studio's browser form and reports back what it saw. It decides nothing and fixes nothing.

## Who does what
- **The owner** starts the Studio (below) and gives you its address. Stay on that address; open nothing else.
- **You** open it, follow the steps, and write what you saw.
- **Two things only the owner can judge**, marked `OWNER ONLY`: just describe them exactly, do not say whether they are fine.

## Rules
1. Read-only on everything but the test Studio page. Do not start, close or touch Football Manager, the real skins folder, any file outside the test folder, or any settings of this computer. The Studio runs against a throwaway workspace; nothing you click there reaches the game.
2. The Studio's own words are the evidence. Copy on-screen text **exactly**, in quotes. Never paraphrase a message.
3. For each numbered line, answer one of: **MATCH**, **DIFFERENT** (say what you saw), or **COULD NOT CHECK** (say why). Do not write MATCH for a line you did not do.
4. Note anything you had to guess, any word that would confuse someone who has never skinned, and any place where you did not know what to click next. Those matter more than bugs.
5b. **Colour boxes** (Colours, the recolour panel, the three-colour theme) open the browser's own colour picker. If you cannot set an exact colour in it, write **COULD NOT CHECK: native colour picker** for the lines that need it and go on.
5. **Browser prompt boxes:** in this browser form, "Pick a file", "Save my skin as a file" and "Open a skin file" ask for a typed path in a small browser dialog (`prompt`). If you cannot operate such a dialog, stop at that line, write **COULD NOT CHECK: needs a browser prompt box**, and go on. Computer use can type into it; the Chrome extension usually cannot.
6. If something blocks you (page not loading, an error you can't get past), stop, write what you saw, and do not try to repair it.

## Start (the owner does this)
In a terminal in the project folder:

    .\.venv\Scripts\python.exe tools\run_studio_scratch.py --keep --open

It prints an address like `http://127.0.0.1:1420/?engine=...&token=...` (it also opens it). Open that exact address. If the setup screen shows, do lines A1 to A3; otherwise skip them.

Test files, ready in `C:\Users\Admin\Downloads\fm27-skin-editor\workspace\walkthrough\` (type these paths where a prompt asks):
- `wallpaper.jpg` : 1280x720, green with pink bars and a white circle in the middle (a stretch or a crop is easy to see)
- `icon.png` : a 64x64 pink square
- `sample-skin.zip` : a skin file made by the Studio
- `not-a-skin.zip` : a zip that is not a skin

## A1 to A3. Setup, once
1. The first screen is "Let's get set up". Click **Find my game and read it**. Copy each step's line (it should say "done in N s"). When it finishes the screen changes by itself: say to what.

## Screenshots (4, in this order; say what each shows)
- **S-start:** the start screen ("Make a skin for Football Manager") with its four choices.
- **S-colours:** the Colours view with the ready-made theme open and one group opened.
- **S-look:** Look at it, side by side, with the Crimson theme (the two sides must visibly differ).
- **S-put:** the "Put it in the game" screen after it has finished once.
Leave them uncropped, at a normal browser size (about 1400 px wide).

## D. Look at it
Make a skin first: Projects, then **Start from a ready-made theme**, keep the name, answer the club-colours question with the first choice, **Make it**. Then:
1. Click **Look at it**. List the layouts on the left (expect six: Loans tile, Atmosphere tile, Medical centre tile, Tactics tile, Training tile, Preferences card) and the search box. Copy the line about reading the game's styles, if one shows.
2. It starts side by side: left "The game as it ships", right "With my skin: ...". Do the colours visibly differ? Take **S-look**.
3. Click the three buttons: **The game as it ships**, **With my skin**, **Side by side**. Does each show what its name says?
4. How many times does the line saying it is an approximation appear, and where? Copy it.
5. Click each of the other layouts; then type `Squad` in the search box and open a result.
6. In Simple mode the bottom panel must have only PROBLEMS and OUTPUT. Write the tabs you see. Click **Advanced** (bottom of the left bar): which tabs appear? Click **S** at the bottom of that bar to come back. Does any screenshot of the game appear anywhere in Simple mode? (Say what you looked at.)
7. Close the project (Projects, **close**): open Look at it with none. Copy what it says.

## E. My colours
In **Colours**:
1. Find "My colours" and its count (expect 0/10). Add a colour with **Add to My colours**; say what appears. Add the same colour again: copy the refusal. Add ten different colours, then try an eleventh: copy the refusal and say whether the button is off.
2. Open a group: does every row have a star and a small arrow? Use the star on one row (it saves that row's colour); use the arrow and pick a saved colour; say what the row does. Click **put back** and say which colour returns (the game's own, or your previous pick).
3. Tick "Top bar and headers": do the same two controls sit beside its colour?
4. Reload the page: are the saved colours still there?

## F. Click it, recolour it
In **Look at it**, with a skin open:
1. Copy the line that says to click a part of the picture. Click a part: what does the panel on the right name, and which colours does it list (Background / Text / Border)?
2. For a colour that has a game colour name: copy what the panel says about how many other parts use it and "used on N of the 8 measured screens...". Pick a new colour with the colour box (rule 5b). Does only the "With my skin" side change? Click **Put it back**: does it return?
3. With saved colours present (section E), do they sit beside the picker, and does one click apply one?
4. Open the **Preferences card** and click a grey text. If the panel says a change copies game rules, copy the number it gives before you change anything. Pick a colour: does it change? Try clicking a white or transparent area: copy what it says.
5. Click a part you cannot change, if you find one: copy the reason it gives.

## G. A theme from three colours
From the start screen (close the project first to see it):
1. Count the ways to begin and copy their titles (expect four).
2. **Start from a ready-made theme** lists Crimson, Forest, Ocean, Slate and amber, each with three colour squares and "not yet checked in the game". Choose Ocean and **Make it**. Does Colours show changed colours?
3. Back at the start: **Make a theme from three colours**. Is there a Dark/Light choice? (There should not be.) Copy the line under the pickers (it should mention how many of the game's colours it sets and leaves; note the exact numbers) and whether it says "Readable".
4. Set the **Text** colour to a mid grey, for example `#A0A0A0` (the colour boxes are the browser's own colour picker, rule 5b; if you cannot operate it, write COULD NOT CHECK for lines 4 and 5). Copy the list of pairs it shows, including the defender badge line if present, and say whether **Make it** is off.
5. Set the text colour back to `#EDEDED`. Copy any small grey lines (they should talk about the defender badge, an unsuited rating, and pairs that can't be checked) with their numbers.
6. Click **Make it**. Does the skin open? Then **Put it in the game**: copy the steps and the result (a card in the middle of the screen).

## H. Pictures in three steps
With a skin open, click **Pictures**:
1. Describe step 1 (Wallpapers and Icons counts, the filter, thumbnails). Click Icons and copy the line about pictures left out.
2. Choose a wallpaper, then look at step 3: how many places, which are ticked? Untick them all: copy the message, say whether **Use my picture** is off.
3. Tick **Main screens**, click **Pick a file**, and type the path of `wallpaper.jpg` (needs a prompt box, rule 5). Click **Use my picture**. Copy what it says, then click **See it in Look at it (Squad screen)**.
   - **OWNER ONLY, describe only:** on the "With my skin" side, how does the picture sit in the Squad screen? Is the white circle round or oval? Are the pink bars cut off or all there? Take a screenshot of that view.
4. Choose an icon (filter `tick`), pick `icon.png`, use it, click **Open Look at it**, open the **Preferences card**: are the tick icons your pink square, on the skin side only?
5. At the top of Pictures, **Put it back** on each replaced picture: do they disappear from the list and from the picture?

## I. Share and undo
Click **Share and undo** (bottom of the left bar):
1. With a skin open, click **Save my skin as a file**; give a path like `C:\Users\Admin\Downloads\fm27-skin-editor\workspace\walkthrough\saved.zip`. Copy the "Saved: ..." line.
2. **Open a skin file**: type the path of `sample-skin.zip`. Before anything is made, copy everything it shows (name, "Made with ...", counts, a suggested name, anything "left out").
   - **OWNER ONLY, describe only:** the saved skin is the EXPORTED skin, not the editable project. After **Make my copy**, open Colours and write what you see there (is there a list of colour changes, or something else?) and copy any words on screen that explain the difference.
   - Click **Cancel** on a second try: did it make nothing?
3. Open `not-a-skin.zip`: copy the message.
4. **Start over ...**: copy the box (what it lists, where the old skin goes). Click **Keep my skin**: nothing changed? Open it again, click **Yes, start over**: copy the result and say what Colours shows now.
5. Back on the start screen (no skin open): click **Open a skin I downloaded**. Where does it take you?

## Report format (return this, nothing else)
```
SETUP: <what happened, with the step times>
D1 MATCH | D2 DIFFERENT: "<exact words>" ...      (one line per numbered step, all sections)
SCREENSHOTS: S-start, S-colours, S-look, S-put, S-wallpaper (attached or described)
OWNER ONLY (H3): <description>   (I2): <description>
GUESSED / CONFUSING WORDS / WHERE I DID NOT KNOW WHAT TO CLICK: <list>
COULD NOT CHECK: <lines and why>
```
