# S1 eyeball pass: what to look at and what it should say

Nothing here touches your real skins, workspace or game files. The page runs against a temporary workspace that is deleted when you stop. The game stays closed; the Studio only READS the game folder.

## Start it
In a terminal in the project folder:

    .\.venv\Scripts\python.exe tools/run_studio_scratch.py --open

It prints an address (also opened in your browser). **Add `--keep` to keep the test workspace between runs** (so the setup is done once, like a real install, and your test skin is still there next time); `--keep --reset` starts from a fresh install again. Without `--keep` every run is a brand-new empty workspace, so the setup screen comes back each time by design. If it says port 1420 is in use, close any other Studio or `npm run dev` window first. When you are done, press Enter in the terminal: it stops everything and deletes the temporary workspace.
(This is the browser form of the Studio. Only the "pick a folder" step differs from the installed app: here it asks you to type a path, there it opens the Windows folder picker.)

## A. A fresh install (the default run)
Tick each line; write down anything that reads wrong, looks odd, or that you would not understand if you had never skinned.

1. **The first thing you see** is a "Let's get set up" screen, not an editor, and the left side has words (Projects, Colours, Pictures, Look at it, Advanced), not single letters. Colours / Pictures / Look at it are greyed out.
2. The setup lists three steps ("Find the game", "Read the game files", "Read the game's colours and rules") and one button, **Find my game and read it**. Click it.
3. Each step shows **done in N s** as it finishes (all three together should take about a second or two). Afterwards the screen changes by itself.
4. **"Make a skin for Football Manager"** with three big choices:
   - Start from a ready-made theme (says it is *not yet checked in the game in this form*)
   - Open a skin I downloaded
   - Start from the game's look
5. Click **Start from a ready-made theme**: a name box (suggestion `my-first-skin`) and a question **The club's own colours** with two choices. Pick *one flat look for every club*: a paragraph appears saying what that does. Read it: is it clear? Does it say anything that sounds like a promise it can't keep?
6. Type a name that has a space or a `!`: it must say to use only letters, digits, dots, dashes and underscores, and **Make it** must be greyed out. Fix the name and click **Make it**.
7. You land on **Colours**. At the top, **Top bar and headers**: one checkbox ("One flat colour instead of each club's colours"); ticking it shows a colour box for the bar. Below, **What the game uses**: closed groups with counts (Page background, Text, Panels, cards and tiles, Buttons, Tables, ...). Open one: every colour in it with its swatch; click a swatch and pick a colour; a **put back** button appears. **Your changes** at the bottom lists what you changed. Type a word (e.g. `cards`) or a code (`#16181D`) in the search box: matching groups open. Does it read as "here is everything, click what to change"?
8. Click **Look at it**, pick any layout from the list. **The first time** a line says it is reading the game's styles for the first time and takes about ten seconds; the picture then appears. Pick a second layout: the line now just says "rendering ...", briefly.
9. Click **Advanced** (bottom of the left bar): the bar turns into single letters and more tools appear. Click **S** at the bottom of that bar: back to words. Reload the page (F5): it stays in the mode you left it in.
10. **A plain-words error:** in Advanced, open the bottom tab **BUILD** and click **Install build**. (The scratch workspace has no build, so nothing is installed; it must only refuse.) A red box at the top should say, in a sentence, that nothing has been built for this project yet, with a **details** line you can open that shows the technical text. Dismiss it with the ×.

11. **Close a project and see the start screen come back** (the explanation for what you saw before is a hypothesis, not yet observed): use `--keep`, open the project from Projects, click **close** next to it. The start choices must come back. Run the launcher again with `--keep`: the setup must NOT come back, and your project must still be listed.

## C. Put it in the game (S2)
The launcher sends "Put it in the game" to a folder INSIDE the scratch workspace, not to your real skins folder (add `--real-skins` only when you want the game to see it).
1. In a project that has a change (or the ready-made theme), the sidebar has **Put it in the game**, between Look at it and Advanced. With no project open it is greyed out.
2. A brand-new empty project: the page says you haven't changed anything and the button is off.
3. With a change: the page says what the skin carries. Click **Put it in the game**: a card appears in the middle of the screen naming each step in words with a bar, then the result with the steps left and the skin's name in them (two steps the first time).
4. Click it again: only **Press "Reload Skin"** is left.
5. Is the middle-of-the-screen card what you meant? Does anything read oddly?

## B. An existing install
Stop the first run (Enter), then:

    .\.venv\Scripts\python.exe tools/run_studio_scratch.py --existing --open

1. The Studio opens in **Advanced** (letters on the left), shows a project called `old-skin`, and does **not** show the start screen. (An install that already has projects must not be switched to Simple behind your back.)
2. Click **S** at the bottom of the bar: Simple, with words. The project is still listed under Projects.

## What to send back
For each numbered line that did not match: the line number and what you saw, in your own words. A screenshot of anything confusing is better than a description. Also: anything you had to guess, any word you did not understand, and any point where you did not know what to click next. Those matter more than bugs.

## What this pass cannot check
The installed desktop app (the folder picker, the window), a machine with no game, a game that is running (the setup should then say to close it), or a game in a second library. Those stay for the first-run test with the friend.
