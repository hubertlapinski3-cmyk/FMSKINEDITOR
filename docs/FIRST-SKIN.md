# Your first skin for Football Manager 27

One page, from installing FM Skin Studio to seeing your skin in the game. Every button named here in **bold** is the Studio's own label (a test checks that each one exists in the Studio; `tests/test_first_skin_guide.py`). Words in "quotes" are the game's.

**Before you start:** Football Manager 27 is installed through Steam and **closed**, and you have a save to load.

## 1. Install and let the Studio read the game (once)
1. Run the FM Skin Studio installer and start the Studio. A fresh install opens in Simple mode, with words on the left.
2. Click **Find my game and read it**. The Studio finds the game, reads its styles once and shows each step with its time. If it can't find the game, it asks you for the game's folder (the one that holds `fm.exe`).
   - If it says the game is running, close Football Manager and click again.

## 2. Choose how to begin
The start screen offers four ways:
- **Start from a ready-made theme:** Crimson (dark crimson) or Forest, Ocean, Slate and amber. All are marked "not yet checked in the game".
- **Make a theme from three colours:** a background, an accent and a text colour. The Studio checks straight away that text stays readable. A pair that fails is listed, and **Make it** stays off until you change a colour; nothing is adjusted for you.
- **Open a skin I downloaded:** a skin file (.zip) is read, shown to you first, then copied as your own skin.
- **Start from the game's look:** nothing changed yet.

Give your skin a name, answer the club-colour question (keep each club's colours, or one flat look for every club), then click **Make it**.

## 3. Change it
- **Colours:** every colour the game's styles use, in groups. Click a swatch, pick a colour; **put back** returns the game's own colour. Keep up to 10 favourite colours with **Add to My colours** or the star, and pick them with one click wherever a colour is chosen.
- **Look at it:** a game layout drawn by the Studio, **The game as it ships** next to **With my skin** (**Side by side**). It is an approximation, not the game; the notice above the pictures says what it cannot show. Click any part of a picture to change its colours there; **Put it back** undoes a change.
- **Pictures:** choose a wallpaper or an icon of the game, **Pick a file** of your own, tick where a wallpaper shows, then **Use my picture**. **See it in Look at it** opens a screen that shows it (the Squad screen for "Main screens").

## 4. Put it in the game
1. Click **Put it in the game**. It writes your skin into the game's skins folder; no game file is changed.
2. The first time, in Football Manager: open Preferences (the cog), pick your skin in the drop-down next to "Reload Skin", and press "Reload Skin". After later changes, only press "Reload Skin".

## 5. Share it, or start again
In **Share and undo**:
- **Save my skin as a file** writes one .zip you can send to a friend.
- **Open a skin file** shows what a .zip holds before anything is made; **Make my copy** turns it into your own skin.
- **Start over ...** lists what would go first; only **Yes, start over** does it, and your old skin goes to the trash folder, not erased.

## If something goes wrong
Every problem is said in a sentence, with the details under "details". The engine's log is `%LOCALAPPDATA%\FM27SkinEditor\logs\app.log`. If the game's files were changed by something else, Steam's "Verify integrity of game files" puts the originals back.

## What is not checked yet
The ready-made themes, the themes made from three colours, and Crimson in this form have **not yet been looked at in the game**; each one is labelled so. "Look at it" is the Studio's drawing, not a screenshot of the game.
