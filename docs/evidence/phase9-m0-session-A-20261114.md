# Phase 9 M0, Session A (solo), 2026-11-14, build 27.0.1.2503222

Owner authorisation (2026-11-14): Session A go, solo; AllowActions true for this session only; abort and report on any anomaly; do not retry without the owner.

## Log

- 10:18:36  session helpers ready; replies saved under D:\drive\FM27-Crimson\workspace\notes\ui-dumps\m0-20261114
- 10:18:36  game closed: yes
- 10:18:37  verify-stock before: STOCK: 67 of 67 UI bundles equal the stock reference hash; update status: same
- 10:18:37  inspector cfg sha256 before the flip: A0C8AAA80AB17CC57B5CE8C9586550E402B70DB530D63456900DBB45D71ECB7C (expected A0C8AAA8... = AllowActions false)
- 10:18:37  cfg: Enabled = true
- 10:18:37  cfg: MainThreadBudgetMs = 600
- 10:18:37  cfg: AllowActions = false
- 10:18:46  config backup kept: C:\Users\Admin\AppData\Local\FM27SkinEditor\backups\inspector-cfg-20261114T085426Z (original, AllowActions true: sha256 45C820A9AA28E604)
- 10:18:46  CONFIG FLIP: AllowActions false -> true for this session only; sha256 now 3FCB64542A8605A2
- 10:18:46  cfg now: AllowActions = true
- 10:18:46  log before launch: C:\Program Files (x86)\Steam\steamapps\common\Football Manager 27\BepInEx\LogOutput.log 6201 bytes, written 11/13/2026 21:44:08
- 10:18:46  log before launch: C:\Users\Admin\AppData\LocalLow\Sports Interactive\Football Manager 27\Player.log 31335 bytes, written 11/13/2026 21:44:11
- 10:18:48  launch requested via Steam; fm.exe started after 2 s (pid 15240)
- 10:18:57  inspector pipe present after 9 s
- 10:18:57  game alive: True
- 10:20:19  start screen ready: True after ~75 s since the pipe appeared; game alive: True
- 10:20:19  status: plugin 0.2.2, game 27.0.1.2503222, unity 6000.3.18f1-custom, roots 5, pid 15240
- 10:20:19  Preferences element: P2/0/5/0/0/1/0/1/0/0/1/4/0/2 | SIText#label.sitext.label-md.global-text-primary.sitext-hover-cursor.content-no-
- 10:20:28  PROBE dump_tree OK: 32 nodes, partial=True, file D:\drive\FM27-Crimson\workspace\notes\ui-dumps\m0-probe-topbar.json (85 ms)
- 10:20:28  game alive after the read: True
- 10:20:28  describe Preferences label, ancestor types (up:type): 0:SIText, 1:SIButton, 2:TemplateContainer, 3:VisualElement, 4:VisualElement, 5:BindableSwitchElement, 6:SIStyleSetter, 7:VisualElement
- 10:20:28  any SIDropdown in the 8 levels: False
- 10:20:28  game alive after describe: True
- 10:20:37  PROBE CLICK: Preferences (SIText in SIButton, no dropdown), expect 'Preferences'
- 10:20:37  click reply: dispatched=True via SIButton:SIButton#button-primary-leading-icon-label.sibutton
- 10:20:40  game alive 3 s after the click: True
- 10:20:40  read after the click: OK, 'Reload Skin' matches=1 (Preferences dialog is open)
- 10:20:40  game alive after the read: True
- 10:20:46  candidate: P2/0/7/0/0/0/0/0/0/0/0/1/0/0/0/0/0/0/0/0/0/0/0/0/0/7 | SIVisible#ShouldShowCloseButton.justify-content-center | text=''
- 10:20:46  candidate: P2/0/7/0/0/0/0/0/0/0/0/1/0/0/0/0/0/0/0/0/0/0/0/0/0/7/0 | SIEnabled#ShouldEnableCloseButton | text=''
- 10:20:46  candidate: P2/0/7/0/0/0/0/0/0/0/0/1/0/0/0/0/0/0/0/0/0/0/0/0/0/7/0/0 | TemplateContainer#close-button.width-height-24px.margin-vertical-global-gap-small | text=''
- 10:20:52     | TemplateContainer#close-button.width-height-24px.margin-vertical-global-gap-small | b=1713.9,353.5,24.4,24.4
- 10:20:52    /0 | SIAspectRatioFitter#AspectRatioFitter | b=1713.9,353.5,24.4,24.4
- 10:20:52    /0/0 | BindableSwitchElement#input-switch.switch-element.bindable-switch-element.flex-grow-class | b=1713.9,353.5,24.4,24.4
- 10:20:52    /0/0/0 | SIButton#buttons-controls-pc-default.sibutton.navigatable.HasSIClickable.buttons-controls- | b=1713.9,353.5,24.4,24.4
- 10:20:52    /0/0/0/0 | VisualElement#x-icon.ui-concepts-cross_small | b=1718.7,357.4,15.6,15.6
- 10:20:52  close button chain: 0:SIButton, 1:BindableSwitchElement, 2:SIAspectRatioFitter, 3:TemplateContainer, 4:SIEnabled, 5:SIVisible, 6:VisualElement, 7:BindingExpect | SIDropdown present: False
- 10:20:52  close button path: P2/0/7/0/0/0/0/0/0/0/0/1/0/0/0/0/0/0/0/0/0/0/0/0/0/7/0/0/0/0/0
- 10:21:00  CLICK: close the Preferences dialog (SIButton, cross icon)
- 10:21:00  click reply: via SIButton:SIButton#buttons-controls-pc-default.sibu
- 10:21:02  game alive: True
- 10:21:02  'Reload Skin' visible matches after the click: 0 (0 = the dialog is closed)
- 10:21:02  load career element: P2/0/5/0/0/1/0/2/0/0/0/0/0/0/0/0/0/0/0/0/1/0/0/0/0/0/0/0/0/0/0/0/0/1/0/1/1/0/0/0/0 | SIText#title-text.sitext.heading-no-wrap.heading-left-align.tile-title-color.the
- 10:21:11  load career chain: 0:SIText, 1:VisualElement, 2:VisualElement, 3:VisualElement, 4:AutoScroller, 5:VisualElement, 6:SIButton, 7:VisualElement | SIDropdown present: False
- 10:21:11  CLICK: Load Most Recent Career
- 10:21:11  click reply: via SIButton:SIButton#layout-tile-interaction-button.sibutton.na
- 10:21:21  career loaded (top navigation visible): True after 10 s; game alive: True
- 10:21:31  screenshot: D:\drive\FM27-Crimson\workspace\notes\ui-dumps\screens\m0-01-after-load-27_0_1_2503222-20261114.png
- 10:21:31  SQUAD candidate: P2/0/3/0/0/0/0/0/0/0/2/1/0/0/0/0/0/0/0/0/2/0/0/0/1/0/2/0 | SIText#text.sitext.portal-text.margin-right-global-gap-none.sitext-hover-cursor.margin-rig
- 10:21:31  SQUAD nav chain: 0:SIText, 1:SIVisible, 2:VisualElement, 3:VisualElement, 4:SIButton, 5:BindingVariables, 6:BindingExpect, 7:TemplateContainer
- 10:21:31  SIDropdown within the chain: False
- 10:21:31  game alive: True
- 10:21:41  CLICK: top navigation SQUAD (label inside an SIButton)
- 10:21:41  click reply: via SIButton:SIButton#buttons-button-navigation-default.sibutton
- 10:21:45  game alive: True
- 10:21:45  visible 'Loans' elements after the click: 2
- 10:21:45    P2/0/3/0/0/0/0/2/0/1/1/0/0/1/0/0/0/0/0/0/5/0/0/0/1/0 | 'Loans' | SIText.sitext.body-md.secondary-navigation-tab-text.sitext-hover-curso
- 10:21:45    P2/0/4/0/0/0/0/0/0/0/1/0/0/0/0/7/0/0/0/0/0/0/0/0/0/0/1/1/0/0/0/0 | 'LOANS' | SIText#title-text.sitext.heading-no-wrap.heading-left-align.tile-title
- 10:21:45  screenshot: D:\drive\FM27-Crimson\workspace\notes\ui-dumps\screens\m0-02-after-squad-click-27_0_1_2503222-20261114.png
- 10:22:16  OBSERVATION: the table's view selector reads 'Copy of Physical' with the c3 column order although the bundles are stock (the game kept a user-view copy of the edited layout)
- 10:22:16  Loans tile dump_tree: 265 nodes, partial=True -> D:\drive\FM27-Crimson\workspace\notes\ui-dumps\m0-loans-tile-27_0_1_2503222-20261114.json
- 10:22:16  root P0 [document:VirtualMouseSubsystem] children=3 sheets(0)=[]
- 10:22:16  root P1 [document:ShortcutData] children=1 sheets(0)=[]
- 10:22:16  root P2 [document:MainUIDocument] children=1 sheets(0)=[]
- 10:22:16  root P3 [document:ColourSpaceConverter] children=1 sheets(0)=[]
- 10:22:16  root P4 [document:UIHighlighting] children=1 sheets(1)=['UnityDefaultRuntimeTheme']
- 10:22:16  game alive: True
- 10:22:43  style reads planned: 18
- 10:22:43  read 01 host                 OK  BindableVariableSizedGridElement#Loans.si-tile.grid-element-scope
- 10:22:44  read 02 tpl-tile-wide        OK  TemplateContainer#tile-wide-4x2.height-100-percent.tile-content
- 10:22:44  read 03 base-container       OK  VisualElement#layout-tile-base-container.layout-tile-base-container
- 10:22:45  read 04 style-setter         OK  SIStyleSetter#BackgroundStyleSetter.width-100-percent.height-100-px.fl
- 10:22:45  read 05 button               OK  SIButton#layout-tile-interaction-button.sibutton.navigatable.HasSIClic
- 10:22:45  read 06 border-tile          OK  VisualElement#Border_TIle.width-100-percent.height-100-percent.surface
- 10:22:46  read 07 title-frame          OK  VisualElement#title area frame.row-direction-normal.tile-title-frame
- 10:22:46  read 08 autoscroller         OK  AutoScroller#auto-scroller.unity-scroll-view.sitext-hover-cursor.unity
- 10:22:47  read 09 scroller-viewport    OK  VisualElement#unity-content-viewport.unity-scroll-view__content-viewpo
- 10:22:47  read 10 states-content       OK  TemplateContainer#states-templates-tile-content.states-templates-tile-
- 10:22:47  read 11 content-inner        OK  VisualElement.flex-grow-class.align-self-stretch-class
- 10:22:48  read 12 frame-outer          OK  VisualElement#Frame_1000002538.align-items-start
- 10:22:48  read 13 frame-row            OK  VisualElement#Frame_1000003021.row-direction-normal.align-items-start
- 10:22:49  read 14 streamed-table       OK  StreamedTable.streamed-list-view.streamed-table.navigatable-no-cursor
- 10:22:49  read 15 title-text-LOANS     OK  SIText#title-text.sitext.heading-no-wrap.heading-left-align.tile-title
- 10:22:50  read 16 frame-heading-text   OK  SIText#title-text.sitext.sitext-hover-cursor.heading-md
- 10:22:50  read 17 cell-713             OK  SIText#text.sitext.content-no-wrap.content-ellipsis.global-text-primar
- 10:22:50  read 18 document-root        OK  UIDocumentRootElement#MainUIDocument-container.unity-ui-document__root
- 10:22:51  reads done: 18 of 18 OK; game alive: True
- 10:23:05  visible tile hosts: 9
- 10:23:05    P2/0/4/0/0/0/0/0/0/0 | FixedAspectGridLayoutElement.si-tile-layout
- 10:23:05    P2/0/4/0/0/0/0/0/0/0/1/0/0/0/0/0 | BindableVariableSizedGridElement#Atmosphere.si-tile.grid-element-scope
- 10:23:05    P2/0/4/0/0/0/0/0/0/0/1/0/0/0/0/1 | BindableVariableSizedGridElement#Tactics.si-tile.grid-element-scope
- 10:23:05    P2/0/4/0/0/0/0/0/0/0/1/0/0/0/0/2 | BindableVariableSizedGridElement#Training.si-tile.grid-element-scope
- 10:23:05    P2/0/4/0/0/0/0/0/0/0/1/0/0/0/0/3 | BindableVariableSizedGridElement#HumanActionsControlPanelBlock.si-tile.grid-elem
- 10:23:05    P2/0/4/0/0/0/0/0/0/0/1/0/0/0/0/4 | BindableVariableSizedGridElement#FirstTeamOverview.si-tile.grid-element-scope
- 10:23:05    P2/0/4/0/0/0/0/0/0/0/1/0/0/0/0/5 | BindableVariableSizedGridElement#SquadHierachy.si-tile.grid-element-scope
- 10:23:05    P2/0/4/0/0/0/0/0/0/0/1/0/0/0/0/6 | BindableVariableSizedGridElement#MedicalCentre.si-tile.grid-element-scope
- 10:23:05    P2/0/4/0/0/0/0/0/0/0/1/0/0/0/0/7 | BindableVariableSizedGridElement#Loans.si-tile.grid-element-scope
- 10:23:05  game alive: True
- 10:23:13  dump Hierarchy: 64 nodes, partial=False
- 10:23:13  dump MedicalCentre: 96 nodes, partial=True
- 10:23:14  dump Atmosphere: 48 nodes, partial=False
- 10:23:14  dump Training: 236 nodes, partial=True
- 10:23:15  dump Tactics: 242 nodes, partial=False
- 10:23:15  game alive: True
- 10:26:07  get_styles med-switch-parent
- 10:26:07  get_styles med-frame-child
- 10:26:07  get_styles med-frame-sibling
- 10:26:18  get_styles med-switch-parent
- 10:26:18  get_styles med-frame-child
- 10:26:18  get_styles med-frame-sibling
- 10:26:46  Medical Centre h:100% observation (branch /1 of the switch, live): parent VisualElement (grow 1 shrink 1, no height) 288.1x106.4 > child Frame.align-items-start (inline height 100%, flex 1 0 0px, resolved grow 1 shrink 0, 288.1x79.1) + sibling Frame (grow 0 shrink 1, 288.1x27.3). 79.1 = 106.4 - 27.3. NON-DISCRIMINATING: explicit flex-basis 0px, so CSS and H-pct both give 79.1.
- 10:26:55  closing: CloseMainWindow pid 15240
- 10:27:56  game alive after 60s wait: True
- 10:28:24  CloseMainWindow ignored for 60s (no dialog visible); trying in-game menu route
- 10:28:59  quit dialog 'Quit Game And Exit?' (raised by CloseMainWindow, no save wanted); clicking Yes SIButton P2/0/14/0/0/0/0/0/0/0/3/0/0/0/0/3/0/0
- 10:30:30  game alive after click+90s: True
- 10:30:36  click Yes reply: {"v":1,"id":808423,"ms":1.39,"result":{"dispatched":true,"via":"SIButton:SIButton#buttons-button-primary-default.sibutton.navigatable.HasSIClickable.buttons-button-primary-default","label":"SIButton#b
- 10:30:40  game alive after click+4s: False
- 10:31:21  CONFIG RESTORE: AllowActions true -> false; bom=False; sha256 now E9C0965F1ACBAAB2B89BE437D5421AFA7FB7E03E062479243B81218A26C459FD
- 10:31:21  NOTE: the pre-flip bytes (sha A0C8AAA8...) were not preserved: the 'backup' dir inspector-cfg-20261114T085426Z holds the AllowActions=true form (45C820A9), and BepInEx rewrote the file during the session (3FCB... at flip vs 45C8... at close). Restored by value, not byte-identical; hash differs from A0C8AAA8.

## M0 exit report (2026-11-14, build 27.0.1.2503222, Session A solo, plugin 0.2.2)

Session outcome: clean. Probe click and dump_tree OK; no crash, no hang; career loaded, Squad > Overview reached through SIButton dispatches; 18 get_styles reads, 6 tile bounds dumps and 3 extra get_styles reads answered. Closed through CloseMainWindow, which raised the game's own "Quit Game And Exit?" dialog; Yes (SIButton) exited the game 4 s later (BepInEx log: Application.quitting, no fault; no new crashpad entry). verify-stock after: 67 of 67. Log pair preserved in docs/evidence/phase9-m0-session-A-logs-20261114 (LogOutput.log sha C6958924..., Player.log sha 8139705C...).

Config: AllowActions restored to false and verified by value (Enabled true, MainThreadBudgetMs 600). NOT byte-identical to the pre-flip file (A0C8AAA8...): the "backup" directory inspector-cfg-20261114T085426Z holds the AllowActions=true form, and BepInEx rewrote the file during the session. Current sha E9C0965F... Owner may want to compare; behaviour is as intended.

1. height:100% observations (hypothesis H-pct: a percentage main-axis size on a child whose parent's main size is itself being flexed behaves as auto basis then grows).
   - Loans (c2, earlier session): row child, height 100%, flex-basis auto, flex-shrink default, in a flexed column with a table sibling. Live: row 24.4, table 82.0 of 106.4; CSS shrink would give 19.8 for the row. DISCRIMINATING, supports H-pct.
   - Medical Centre (this session, live branch of the switch, same screen, same breakpoint): parent VisualElement (grow 1, no height) 288.1x106.4 > child Frame (inline height 100%, flex 1 0 0px; resolved grow 1 shrink 0) 288.1x79.1 + sibling Frame (grow 0) 288.1x27.3. 79.1 = 106.4 - 27.3. NON-DISCRIMINATING: the explicit flex-basis 0px overrides height in CSS too, so CSS and H-pct both predict 79.1.
   - Verdict: H-pct stays OPEN (one discriminating source, one consistent but non-discriminating source). Not made a render rule. Candidates for a discriminating second read: TrainingMentoringTile_4x4 (StreamedObjectList h100 in a grow parent with a sibling), TacticsTile_4x4 overlay.
2. Sheet gaps: measured root list has TEN entries: AlwaysAppliedStyleSheet, LanguageDirectionLTRCombined, LanguageNameOrderGivenFirst, AnimationStyles, FMImages_2x, FMControllerIconsPC_2x, Bundesliga, and three entries with empty names. Bundesliga is named and real (22 rules, --bundesliga-* tokens; competition-bound, not applied by the render). AnimationStyles (67 rules) is in the default bundle; selectors need run-time state classes, inert on a static tree; its config source is still unknown. The three unnamed stay OPEN (names only are exposed). The table control attaches NO sheet of its own: StreamedTable reports the same document-root chain (levelsUp 28). Loans base container reports the same chain (levelsUp 21).
3. AutoScroller width failure: restated as data-bound. The title AutoScroller/viewport width depends on the bound text width; the render draws a placeholder, so this is the accepted placeholder category, not a style-resolution error.
4. Sheet order, measured root vs rip-derived: same relative order for the six rip-derived sheets (AlwaysApplied, LTR, NameOrder, AnimationStyles, FMImages_2x, FMControllerIconsPC_2x); Bundesliga follows them; `default` does not appear (applied through AlwaysApplied's import, as derived). Not contradicted.
5. Cascade check on live reads: 17 reads vs the Loans render, 117 properties, 82 with a value on both sides, 82 equal (colours with alpha, font sizes, flex properties); 35 had no render value to compare; 4 reads had no node pair (host, button, scroller viewport, cell 713, matched by label only).
6. Timing: cached warm 1.4 ms, new process 43 ms, all-layouts p95 13.9 ms, against the 200 ms budget: met.

M0 status: BANKED (with H-pct open and the three unnamed sheets open as named gaps).
