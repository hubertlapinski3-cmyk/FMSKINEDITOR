# I3 Session G (MANUAL, owner at the PC), 2026-11-14

Order agreed: (1) one launch with the baseline DLL 0.2.2 and AllowActions false (clean inspector): if it stalls with the owner present the inspector is cleared and the cause is the machine's state (reboot next); (2) if it runs, install 0.5.1 under the standard round trip and run the I3 hover holds with the owner at the PC.

## Log
- 17:00:57  verify-stock before: STOCK: 67 of 67 UI bundles equal the stock reference hash; update status: same
- 17:00:57  installed DLL 1C698C3DB45DC59F (baseline 1C698C3D...); cfg 9231F4BB99C0B64B (baseline 9231F4BB...); AllowActions: AllowActions = false
- 17:00:57  overlay/recorder software running (unchanged from the F3 finding): Discordx6, SpotifyLauncherx1, SpotifyXboxGamebarWebViewx1, steamx1
- 17:00:57  launch requested (baseline DLL, AllowActions false, owner present)
- 17:02:00  READY after +60s: plugin 0.2.2 scene BootToInit roots 5
- 17:02:13  RESULT 1: the baseline DLL (0.2.2, AllowActions false) launched and became ready in about 60 s with the owner present. The inspector at baseline is not the cause of the stalls. Both stalled launches (F, F2) had the modified 0.5.1 DLL and a modified cfg installed.
- 17:02:13  OWNER (mid-session): the stalls were 'the anti-tamper thing once again'. Recorded as the owner's diagnosis: a launch with a modified plugin DLL or cfg after the reboot stalls in the game's start-up, which fits the evidence (baseline fine; F and F2 modified; the game never reached GAME_PLUGIN::initialise()). Not yet understood by me: what exactly trips it (DLL hash, file timestamp, the cfg, BepInEx folder state) and why 0.3.1 and 0.4.0 launched fine before the reboot. Game left running at the start screen, baseline, for the owner's instruction.
- 17:02:57  baseline get_styles check on the start-screen 'Preferences' text: fields [], pseudo=
- 17:03:57  rest reads taken (4 targets x 6 levels) in C:\Users\Admin\FMSKINNING\workspace\notes\ui-dumps\i3g-20261114
- 17:05:54  HOVER nav-TACTICS read (owner hovering): pseudo masks up0..5 = 0,0,2,2,2,2
- 17:08:19  AWAY nav-TACTICS read: pseudo masks = 0,0,0,0,0,0, label colour #EBEBEB (state returned to rest: True)
- 17:09:34  HOVER button-Filter read: pseudo masks up0..5 = 0,2,2,2,2,2
- 17:11:12  AWAY button-Filter: pseudo 0,0,0,0,0,0, widget bg #FFFFFF24; HOVER tile-LOANS-title: pseudo up0..5 = 0,0,0,0,0,0
- 17:11:22  HOVER tile-LOANS: tile container reads saved (g-tile-LOANS-*-hover.json)
- 17:12:49  HOVER Loans tile body read done (g-tile-LOANS2-*)
- 17:13:01  HOVER Loans tile (body, the tile not the title text): SIButton#layout-tile-interaction-button pseudo 0->2 and background #17223F->#2E3138; the tile host and its SIStyleSetter pseudo 0->2; the title text chain stays 0 (the title is not the hover target). Border_TIle child not re-read (path index fault, not retried).
- 17:17:52  Table row hover (Squad overview, row 6 of zebra list, owner hovering player-name icon): pseudo 0->2; background-color #FFFFFF00 (even-row rest) -> #FFFFFF1A (hover), odd rows rest #FFFFFF0F; classes unchanged (streamed-table__row ... streamed-list-view__row--interactable). Per-row playerreportTooltipPopup hosts exist for every row (SIVisible, visible=true).
- 17:19:54  row6 away: pseudo 0 bg #FFFFFF00
- 17:22:07  Filter button HELD (press, no release): a0: pseudo 0 bg #00000000 color #EBEBEB | sitext.margin-right-global-gap-regular || a1: pseudo 67 bg #FFFFFF24 color #EBEBEB | HasSIClickable.row-direction-normal.buttons-button-base-default.button-size-medium.navigatable-no-cursor || a2: pseudo 2 bg #00000000 color #EBEBEB |  || a3: pseudo 2 bg #00000000 color #EBEBEB | row-direction-normal.align-items-center.justify-content-space-between.align-self-stretch.flex-no-shrink-class
- 17:22:25  Filter button, dragged off (mouse still held): pseudo 64 bg #FFFFFF24
- 17:22:41  Filter button after release off-target: pseudo 0 bg #FFFFFF24
- 17:24:37  Team Instructions pitch markers at rest (index:pseudo:bg:size): 3:0:#00000000:80.1x38.1 4:0:#00000000:80.1x39.1 5:0:#00000000:80.1x38.1 6:0:#00000000:80.1x38.1 7:0:#00000000:80.1x38.1 8:0:#00000000:80.1x53.7 9:0:#00000000:80.1x52.7 10:0:#00000000:80.1x38.1 11:0:#00000000:80.1x38.1 12:0:#00000000:80.1x38.1 13:0:#00000000:80.1x36.1
- 17:26:44  Marker hover scan (owner on name 'gadou'): 3:0:#00000000 4:0:#00000000 5:2:#00000000 6:0:#00000000 7:0:#00000000 8:0:#00000000 9:0:#00000000 10:0:#00000000 11:0:#00000000 12:0:#00000000 13:0:#00000000
- 17:26:53  Marker 5 hovered, descendants: /0: pseudo 2 color #EBEBEB bg #00000000 op 1 |  || /0/0: pseudo 2 color #EBEBEB bg #00000000 op 1 |  || /0/0/0: pseudo 2 color #EBEBEB bg #00000000 op 1 |  || /0/0/0/0: pseudo 2 color #EBEBEB bg #00000000 op 1 | content-tactics-visualiser-player-indicator-simple.margin-ho
- 17:28:39  Marker 5 away: marker: pseudo 0 color #EBEBEB || /0/0/0/0: pseudo 0 color #EBEBEB
- 17:30:23  Instruction tile hover chain (pseudo!=0 descendants): /0|d1|pseudo 2|color #EBEBEB|bg #00000000|bc #00000000|height-100-percent || /0/0|d2|pseudo 2|color #EBEBEB|bg #00000000|bc #00000000|height-100-percent.flex-grow-class || /0/0/0|d3|pseudo 2|color #EBEBEB|bg #00000000|bc #00000000|height-100-percent.flex-grow-class || /0/0/0/0|d4|pseudo 2|color #EBEBEB|bg #00000000|bc #00000000|height-100-percent || /0/0/0/0/0|d5|pseudo 2|color #EBEBEB|bg #00000000|bc #00000000|height-100-percent
- 17:32:18  Instruction tile away: tile: pseudo 0 color #EBEBEB bg #00000000 || /0: pseudo 0 color #EBEBEB bg #00000000 || /0/0/0: pseudo 0 color #EBEBEB bg #00000000 || /0/0/0/0/0: pseudo 0 color #EBEBEB bg #00000000
- 17:34:24  Inbox rows at rest (index:pseudo:bg): 0:0:#FFFFFF00 1:0:#FFFFFF00 2:0:#FFFFFF00 3:0:#FFFFFF00 4:0:#FFFFFF00 5:0:#FFFFFF00
- 17:34:54  Inbox hover scan: 0:0:#FFFFFF00 1:0:#FFFFFF00 2:0:#FFFFFF00 3:0:#FFFFFF00 4:0:#FFFFFF00 5:0:#FFFFFF00 | chain: 
- 17:35:18  Inbox message row hover: SIButton#NewsItemButton (HasSIClickable) pseudo 2, background-color #FFFFFF14 hovered; list rows (TemplateContainer) stay pseudo 0 with bg #FFFFFF00; row children (message-tag, read-status icon) carry pseudo 32 (disabled) on every row, hovered or not; Messages tile background #17223F66 pseudo 2 (container hovered). Rest value for NewsItemButton pending 'away' read. Path: P2/0/4/0/0/0/0/0/1/0/0/0/0/0/0/1/0/0/0/0/0/0/0/0/0/0/1/2/0/0/0/0/0/0/0/0/0/0/0/0/2/0/0/1/1
- 18:11:47  NewsItemButton away: pseudo 0 bg #00000000 classes-unread-token: portal-messages-item-default-style-unread-property-1-message-property-2-default
- 18:12:50  Inbox after click scan, NewsItemButton signatures (pseudo|bg|token): 42 x 0|#00000000|portal-messages-item-default-style-unread-property-1-message-property-2-default
- 18:13:34  after click: last-selected idx 3,24 (before: 1,22)
- 18:13:41  Inbox select: clicked row's SIButton#NewsItemButton gains pseudo 64 (focus), bg unchanged #00000000, classes unchanged; selection is carried by the sibling SIStyleSetter_IsLastSelected which swaps message-not-last-selected -> message-last-selected (two setters flagged at any time: idx 1,22 -> 3,24); no colour measured on the setter itself. HOLDS COMPLETE: nav tab, Filter button (hover/press/drag-off/release), Loans tile, table row, pitch marker, instruction tile, Inbox row hover + select. No dropdown touched, no action sent, AllowActions false.

## Close-out (18:15)
- Owner quit the game by hand. Baseline restored by construction (nothing installed): DLL 1C698C3D, cfg 9231F4BB, AllowActions false. verify-stock: 67 of 67, update status same.
- Logs preserved in `phase9-i3-session-G-logs-20261114/` (LogOutput, ErrorLog, actions log, Player.log). Raw inspector replies: `workspace\notes\ui-dumps\i3g-20261114` (g-*.json).

## Hover and state findings (baseline get_styles, one call at a time, no actions sent, no dropdown touched)
Pseudo-state bits seen: 1 active, 2 hover, 32 disabled, 64 focus.

| Element | Rest | Hover | Other |
|---|---|---|---|
| Nav tab (TACTICS) | pseudo 0, label #EBEBEB | ancestors 2, label #FFFFFF | |
| Filter button (SIButton) | pseudo 0, bg #FFFFFF24 | pseudo 2, bg #FFFFFF33 | pressed 67 (1+2+64) bg #FFFFFF24; dragged off held 64; released 0 |
| Loans tile SIButton | bg #17223F | bg #2E3138 | tile title text is not a hover target |
| Table row (zebra, interactable) | even #FFFFFF00, odd #FFFFFF0F | pseudo 2, bg #FFFFFF1A | per-row player-report popup host also 0 to 2, no display change |
| Pitch marker (Team Instructions) | pseudo 0 | pseudo 2 on marker and descendants | no colour/background change |
| Instruction tile | pseudo 0 | pseudo 2 down 5 levels | no colour/background/border change |
| Inbox NewsItemButton | pseudo 0, bg #00000000 | pseudo 2, bg #FFFFFF14 | click: focus 64, no colour change; selection is a class swap on SIStyleSetter_IsLastSelected (message-not-last-selected to message-last-selected); message-tag/status icons carry 32 on every row |

Consequences for the render: hover is a pseudo-mask bit with colour deltas only on SIButton-class controls and list rows; pitch markers and instruction tiles have none to model. Press changes no colour.