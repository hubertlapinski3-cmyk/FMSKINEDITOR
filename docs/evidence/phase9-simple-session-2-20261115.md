# Session 2 record (the gallery gate), 2026-11-15: PREFLIGHT ONLY, the in-game part is not done yet

This file is the record the sessions checklist asks for. Right now it holds the preflight, measured before the owner's sitting. **Nothing in the game has been looked at yet**; the per-theme verdicts, the defender-badge answer, the 7 unchecked pairs and the 148 kept colours are added below as they are observed, and a failure is written as a failure.

## Preflight (rules 2, 3, 5, 6 of `docs/SESSIONS-simple-mode-checklist.md`)
- **verify-stock:** `STOCK: 67 of 67 UI bundles equal the stock reference hash; update status: same` (exit 0).
- **Plugin baseline 0.2.2:** DLL sha256 `1C698C3DB45DC59FCF01FDA0C4A8A64819DDC6185982237898FF29638FFD7C6F`; config sha256 `9231F4BB99C0B64B67759FA331D43BBF7AF0D1B9DC7A46D0A313F8711886CE9B`; `Enabled = true`, `MainThreadBudgetMs = 600`, `AllowActions = false`. All equal the checklist's baseline.
- **Game state:** no `fm` or `Football Manager 27` process running; the game was not launched by this work.
- **Boot-time list:** machine last boot 2026-11-15 18:17:12. Running: Steam (18:17:57), Spotify (18:17:40 to 18:18:12), Discord (18:18:01 to 18:18:07), Medal and MedalEncoder (18:18:07 to 18:19:27). Not compared with the F3 list in this record.
- **Offline theme check on this build** (`tools/check_s4_themes.py`): no mapped token missing; Forest, Ocean and Slate and amber pass with 0 failures, defender badge 4.76, 4.77 and 4.81; the export of Forest writes 83 tokens, no problems.
- **Skins folder backup:** `%LOCALAPPDATA%\FM27SkinEditor\backups\skins-20261115-175711` (86 files, hashes equal to the source; hash list `skins-20261115-175711.sha256.txt` beside it).
- **Additions:** three skins written by the Studio's own export into `Documents\Sports Interactive\Football Manager 27\skins`: `gallery-forest`, `gallery-ocean`, `gallery-slate-and-amber` (each 6 files, 83 tokens, no problems). The 86 files that were there are unchanged by hash. No game file was written.

## To do in the game (owner at the PC)
1. Start Football Manager, load the save (same save, same breakpoint, same window size for every theme; write them down).
2. For each of the three themes: Preferences, pick it in the drop-down next to "Reload Skin", Reload Skin, wait 10 s, Confirm.
3. **First, on every theme:** `fm_get_styles` on a defender position badge label (one call): which token or rule wins? That single answer decides whether the badge entry stays in the role map.
4. Then the eight screens (club, competition, portal, recruitment, squad, tactics, tactics-instructions, training): one `fm_screenshot` each, and the observations the checklist lists.

## Observations

### gallery-forest, Squad screen (game 27.0.1.2503222, plugin 0.2.2, Borussia Dortmund save, Squad > Overview > First Team; window 2500x1406 as the tool reports it)
Screenshot: `C:/Users/Admin/FMSKINNING/workspace/notes/ui-dumps/screens/s2-forest-current.png` (the game's `ui-dumps` folder; not copied into the repo).
- **Looked at, as seen in the screenshot:** the page background and the panels are dark green-black, the text is light and readable, the accent greens show on the badges; the top bar and club header are Dortmund yellow (club colours kept, as chosen). The position chips in the Picked column keep their own colours (teal, green, blue, purple, pink). Only the Squad screen was looked at for Forest so far: the other seven screens and the other two themes are NOT done.
- **THE DEFENDER BADGE QUESTION (one inspector call at a time):** the chip label is the `SIText#RoleName` "D (C)" in the Picked column.
  - `fm_get_styles`: resolved `color` **#FFFFFF**.
  - `fm_colour_source` (`color`): the winning rule is **`AlwaysAppliedStyleSheet` `.text-regular`, value `#FFFFFF`** (a literal), over `.sitext` (`var(--global-text-primary)`). **No `--data-player-position-defender-foreground` and no position token appears among the rules.**
  - So the label is NOT painted by the token the role-map entry sets, and it did not take the theme's text colour either (the theme's primary text is `#E6EFE9`).
  - The chip's fill was not located: `fm_colour_source` (`background-color`) on two ancestors (the SIStyleSetter six levels up and a SIVisible two levels above that) said `#00000000`, no rule. The ancestors include an `SIStyleSetter`, which sets colours from code (it has `SetElementBackgroundColor` and `BindColorToForeground`).
  - Limit: one chip, one screen, one theme. The chip's fill source is unresolved.
### gallery-forest, Club screen (Club > Overview), same save and window
Screenshot: `C:/Users/Admin/FMSKINNING/workspace/notes/ui-dumps/screens/s2-forest-club.png`. Observed from the screenshot only (no inspector call on this screen yet):
- Page background and panels are dark green-black; all body text (staff table, headings, finance figures, axis labels) is light and readable. Table links and the "Board Vision" / "Club Staff" headings take a light green accent.
- Club colours still visible: the yellow top bar and sub-bar, and the yellow-olive "The board are pleased..." feedback panel (club-coloured, kept).
- **A surface that stayed at the game's own colour and clashes with the theme:** the Finances chart fill is a dark purple (a game data colour not in the map), against the green theme. The chart's line is pale green. The "C+" icon and the olive feedback panel are club-coloured.
- No hard-to-read text seen. Verdict for this screen, Forest: **WORKS WITH LISTED EXCEPTIONS** (the purple chart fill; the olive club-coloured panel is the club's own and expected).

### gallery-forest, Portal screen (Portal > Overview), same save and window
Screenshot: `C:/Users/Admin/FMSKINNING/workspace/notes/ui-dumps/screens/s2-forest-portal.png`. Observed from the screenshot only (no inspector call on this screen):
- Page background and panels dark green-black; messages, news, league table, fixture list, player stats and the right-hand widgets all read well (light text). The accent greens show: the Data Hub radar, the budget bars, the Sat tab in the training week, the All tab of Messages, the "Performing much better" pill.
- Club colours still visible: the yellow top bars. The own club's row in the league table is orange-red (game highlight, not set by the map).
- **Colours that stayed at the game's own value, by design or not in the map:** the orange "BREAKING NEWS" banner, the blue/red/yellow position markers and league-zone bars in the league table, the colour clubs' crests. None clashes badly with the green theme; the orange banner and the red/blue zone bars are the most noticeable.
- **Something that looks wrong and is NOT attributed to the theme:** in the Player Recommendations card at the bottom right, the heading "No Recommendations" overlaps the line "Your scouting team is working hard to bring you more recommendations of this type soon." Not compared with the game's own skin; the cause is unknown.
- Verdict for this screen, Forest: **WORKS WITH LISTED EXCEPTIONS** (game-coloured banner and table markers; the text overlap is unattributed and needs a check against the default skin).

### gallery-forest, Tactics screen (Tactics > Overview > Team Shape), same save and window
Screenshot: `C:/Users/Admin/FMSKINNING/workspace/notes/ui-dumps/screens/s2-forest-tactics.png`. Observed from the screenshot only (no inspector call on this screen):
- Page background dark green-black; the tactics header strip, the pitch panel and the substitutes panel are a deeper teal-green than the page (the theme's accent family), and the player table reads well on the dark rows. Headings, column titles, names and figures are all legible.
- Club colours still visible: the yellow top bars and the yellow player shirts on the pitch.
- **Colours at the game's own values (not set by the map):** the position and role chips (teal D, green DM, blue M, purple AM and WFD, pink ST and CFD, grey GK), the ability and potential stars, the orange/red/green status badges (Inj, Wnt, BPR, FtT, Bid, A19), the rating pills, the Intensity and Complexity icons. They keep the game's palette; none is hard to read on the Forest background.
- Faintest text: "Style" and "Mentality" in the "Clean Slate Style" and "Positive Mentality" selectors (a dimmer green-grey than the other labels); legible, but the lowest-contrast text seen on this screen. Not measured.
- Verdict for this screen, Forest: **WORKS WITH LISTED EXCEPTIONS** (game-coloured chips and badges, unmeasured dim labels).

### gallery-forest, Tactics Instructions screen (Tactics > Overview > Team Instructions), same save and window
Screenshot: `C:/Users/Admin/FMSKINNING/workspace/notes/ui-dumps/screens/s2-forest-tactics-instructions.png`. Observed from the screenshot only (no inspector call on this screen):
- The instruction tiles, the Overview list, the Data Hub, Captains, Set Pieces and Penalties cards are dark green-black and all their text is legible. The left tactic panel and the header strip are a solid, saturated teal-green; the left panel runs the full height of the screen and is visually the heaviest area on this screen. The page behind the cards shows the game's own dark pattern wallpaper (not changed by the theme).
- Club colours still visible: yellow top bars. Penalty-taker ratings (19) are the game's yellow pills; the "Performing much better than average" bar is a bright green; the position chips on the pitch map (CFD, WFD, AP, CHM, DLP, WCB, CB, GK) keep the game's chip colours.
- Text overlap seen, not attributed to the theme: on the pitch map the label "N. Schlotterbeck" overlaps the DM / WCB chips near the centre circle (crowded labels; not compared with the default skin).
- Verdict for this screen, Forest: **WORKS WITH LISTED EXCEPTIONS** (game-coloured chips and pills; the full-height teal left panel is heavy but readable; label overlap unattributed).

### gallery-forest, Recruitment screen (Recruitment > Overview), same save and window
Screenshot: `C:/Users/Admin/FMSKINNING/workspace/notes/ui-dumps/screens/s2-forest-recruitment.png`. Observed from the screenshot only (no inspector call on this screen):
- Page background and cards dark green-black; all text legible (the "0 Recommended Players" panel is empty, with "No Recommendations" and its sentence centred and not overlapping). Green accents show on the section links (Scout Reports), the "Open" transfer-window status, the recruitment-team names and the progress slider; the green "Review Team Selection" button is the game's.
- Club colours still visible: the yellow top bars, and the club's yellow wallpaper streaks at the screen edges.
- Colours at the game's own values: the orange "D" and yellow-green "B-" recommendation rings in Agent Offers, the red and green transfer arrows in Transfer Activity.
- Relevant to the Portal note: here "No Recommendations" and its sentence do NOT overlap, so the overlap in the small Portal card is more likely that card's own layout than the theme; still not compared with the default skin.
- Verdict for this screen, Forest: **WORKS** (no exception beyond the game-coloured rings and arrows).

### gallery-forest, Training screen (Training > Overview), same save and window
Screenshot: `C:/Users/Admin/FMSKINNING/workspace/notes/ui-dumps/screens/s2-forest-training.png`. Observed from the screenshot only (no inspector call on this screen):
- All text legible: headings, calendar day numbers and activity labels, the right-hand cards (Next Opposition Report, Tactical Effectiveness, Coaching Team, Fixture Schedule, Coach Assignments, Training Intensity). The top cards and the right-hand cards are green-tinted dark like the other screens.
- **A surface that did NOT take the theme's tint, by eye:** the training calendar grid and its grey "Rest" and "Travel" tiles look neutral to cool black-grey, not the green-black of the cards around it, so the calendar reads as a separate dark panel. Not measured, and not traced to a token (no inspector call yet).
- Colours at the game's own values (by design, the training families and match tiles): the green, red and purple activity tiles, the dark-red league-fixture tiles, the blue Champions League tiles, the purple highlight of today (9), the orange and green intensity rings.
- Club colours still visible: yellow top bars.
- Verdict for this screen, Forest: **WORKS WITH LISTED EXCEPTIONS** (the calendar surface not tinted like the rest; the game-coloured tiles).

### gallery-forest, Competition screen (Portal > Competitions), same save and window
Screenshot: `C:/Users/Admin/FMSKINNING/workspace/notes/ui-dumps/screens/s2-forest-now.png` (taken when the owner said "right now"; the screen was already Portal > Competitions, so it is recorded as the Competition screen). Observed from the screenshot only (no inspector call on this screen):
- Page background and the league-table bodies dark green-black; table text, team names, form bars, top-performer lists and the footer buttons are legible.
- Competition-coloured headers kept by the game: Bundesliga dark green, UEFA Champions League blue, DFB-Pokal green, Supercup grey. The own club's row is orange-red (game highlight). Zone bars (UCL, UEL and the rest) and the green form bars keep the game's colours.
- Club colours still visible: yellow top bars and wallpaper streaks.
- Verdict for this screen, Forest: **WORKS WITH LISTED EXCEPTIONS** (the game's competition-coloured headers, the own-club highlight and zone bars).

### gallery-forest, summary after eight screens
Looked at (screenshots, by eye, no measurements): Squad, Club, Portal, Tactics, Tactics Instructions, Recruitment, Training, Competition. **Recruitment: WORKS. The other seven: WORKS WITH LISTED EXCEPTIONS.** No unreadable text was seen on any screen. Exceptions are game-coloured items (chips, badges, tiles, competition headers, zone bars) and two surfaces that did not look tinted like the rest: the Finances chart fill on Club (dark purple) and the calendar grid on Training (neutral black-grey). Neither was traced to a token. Overall Forest verdict: **WORKS WITH LISTED EXCEPTIONS.** Ocean and Slate and amber: not done.

### gallery-forest, Training calendar traced with the inspector (one call at a time; the owner navigated to Training)
- Elements found by class: `DateGrid.calendar-training-style-override`, day containers `calendar-training-day-standard-default-type-upcoming`, the events body `calendar-training-day-standard-events`, session buttons and `SIGradient.calendar-training-session-gradient-element`.
- **`fm_colour_source` (`background-color`) says `#00000000`, no inline value, no matching rule, on all of these:** the DateGrid, the day container, the events body, a `ComponentElement` above them, and (from the Rest tile's text up) a `DynamicItem`, a `ComponentElement.flex-grow-class` and a `BindingExpect`. **So the calendar grid has no background of its own along the path I walked;** it sits directly on whatever is behind it (the page layer), which is why it does not look green-tinted like the cards that do carry a fill. The Rest and Travel tile fills were NOT located (not found on those ancestors).
- **Activity tiles:** a `SIGradient` (component-set; "style rules are ignored" by the tool's verdict, `useCustomStyles` false) whose rules name `--colours-calendar-training-tactical-understanding-start` / `-end`; the resolved gradient colours are `#0E8B4B52` to `#0E8B4B3D`. These are the family tokens the Crimson preset overrides by family; the three-colour map keeps them at the game's colour (it does not derive them).
- Not done: the Finances chart on Club, and the Rest tile's own fill. Limit: only background-colour was asked for the ancestors, one tile each.

### gallery-forest, Tactics > Data Hub (the owner asked to be sure Data Hub colours can be changed), same save and window
Screenshot: `C:/Users/Admin/FMSKINNING/workspace/notes/ui-dumps/screens/s2-forest-datahub.png`.
- **By eye:** cards dark green-black, all labels and figures legible. The radar charts are filled with a bright green (a livelier green than Forest's muted accent), their stat values are lime, orange or white, the "Performing ..." pills are green, the scatter plot (Aerial) has white and purple dots. The club's yellow wallpaper shows behind the cards.
- **Inspector, one call at a time:**
  - The pill label's `color` is `#B8EAB3`, from `AlwaysAppliedStyleSheet` `.badges-text-color-green-soft` = `var(--theme-color-green-soft-soft)`. **That token is NOT in the role map** (neither an entry nor kept): the three-colour theme does not change it.
  - A `radar-content` element's resolved `color` is **`#E6EFE9`, Forest's own text colour** (the primary text input): this confirms in the game that the theme's text colour reaches Data Hub content.
  - The radar polygons and the scatter dots were not found as styled elements (no class or element named for them was found by `fm_find`), so **what paints the radar fill was NOT identified.** Chart tokens exist in the game's styles (`--colours-chart-*`), but that they paint the radar is not established.
- What can be said: Data Hub text and surfaces follow the theme; its green pills use a family token the theme leaves at the game's value. Whether the radar colour can be changed by a token is OPEN.

- **Owner decision on that answer (2026-11-15, in this session):** remove the badge entry from the role map AND the defender badge pair from the blocking check, the reason recorded (no rule paints that token in this build). Applied in the commit that follows; see the S4 amendment 2.
