# S1 eyeball pass: what to look at and what it should say

Nothing here touches your real skins, workspace or game files. The page runs against a temporary workspace that is deleted when you stop. The game stays closed; the Studio only READS the game folder.

## Start it
In a terminal in the project folder:

    .\.venv\Scripts\python.exe tools/run_studio_scratch.py --open

It prints an address (also opened in your browser). If it says port 1420 is in use, close any other Studio or `npm run dev` window first. When you are done, press Enter in the terminal: it stops everything and deletes the temporary workspace.
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
7. You land on **Colours** with a list of colour swatches (about 400). Change one colour with its picker; nothing should break.
8. Click **Look at it**, pick any layout from the list. **The first time** a line says it is reading the game's styles for the first time and takes about ten seconds; the picture then appears. Pick a second layout: the line now just says "rendering ...", briefly.
9. Click **Advanced** (bottom of the left bar): the bar turns into single letters and more tools appear. Click **S** at the bottom of that bar: back to words. Reload the page (F5): it stays in the mode you left it in.
10. **A plain-words error:** in Advanced, open the bottom tab **BUILD** and click **Install build**. (The scratch workspace has no build, so nothing is installed; it must only refuse.) A red box at the top should say, in a sentence, that nothing has been built for this project yet, with a **details** line you can open that shows the technical text. Dismiss it with the ×.

## B. An existing install
Stop the first run (Enter), then:

    .\.venv\Scripts\python.exe tools/run_studio_scratch.py --existing --open

1. The Studio opens in **Advanced** (letters on the left), shows a project called `old-skin`, and does **not** show the start screen. (An install that already has projects must not be switched to Simple behind your back.)
2. Click **S** at the bottom of the bar: Simple, with words. The project is still listed under Projects.

## What to send back
For each numbered line that did not match: the line number and what you saw, in your own words. A screenshot of anything confusing is better than a description. Also: anything you had to guess, any word you did not understand, and any point where you did not know what to click next. Those matter more than bugs.

## What this pass cannot check
The installed desktop app (the folder picker, the window), a machine with no game, a game that is running (the setup should then say to close it), or a game in a second library. Those stay for the first-run test with the friend.
