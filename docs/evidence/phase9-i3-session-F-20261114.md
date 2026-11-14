# I3 Session F (SOLO, no human at the PC): hover and press dispatch, mode 3 transitions, 2026-11-14

Owner authorisation (2026-11-14): run solo; plugin extended with hover and press dispatch (0.5.1-capture); AllowActions true for this session only, logged before and after; one call at a time; abort and report on any anomaly, no retries without the owner; never touch an SIDropdown; validate the synthetic hover on each screen before trusting a hold; closing: quit, restore DLL and config by value, verify-stock 67 of 67, log pair preserved.

Hover and press are dispatched through the same machinery as the proven click fallback (pooled event, target set, SendEvent). press-release goes to the panel root so no click completes. Both refuse any target inside a dropdown.

## Log
- 15:47:09  game closed: True
- 15:47:10  verify-stock before: STOCK: 67 of 67 UI bundles equal the stock reference hash; update status: same
- 15:47:10  staged 0.5.1 DLL sha256 EBF1BE4B920AC020EA80389344A8E0C114885A0283520F7CF859490C5089F74A
- 15:47:10  backup C:\Users\Admin\AppData\Local\FM27SkinEditor\backups\inspector-sessionF-20261114T144710Z; DLL 1C698C3DB45DC59FCF01FDA0C4A8A64819DDC6185982237898FF29638FFD7C6F; cfg 9231F4BB99C0B64B67759FA331D43BBF7AF0D1B9DC7A46D0A313F8711886CE9B (equal the logged baselines)
- 15:47:10  installed 0.5.1 DLL EBF1BE4B920AC020EA80389344A8E0C114885A0283520F7CF859490C5089F74A
- 15:47:10  CONFIG FLIP: AllowActions false -> true for this session only (sha before 9231F4BB99C0B64B67759FA331D43BBF7AF0D1B9DC7A46D0A313F8711886CE9B)
- 15:47:10  cfg now: Enabled = true | DumpFolder = C:\Users\Admin\FMSKINNING\workspace\notes\ui-dumps | AllowActions = true | Enabled = true | Transitions = true; sha 2CF6FB9D19164BBE51A93E687C6E09C232F3028CBA314452BFCFCC6D5D6B4F13
- 15:47:10  log before launch: LogOutput 8707 bytes
- 15:47:10  launch requested
- 15:50:53  ready: False plugin  pid  after 200s
- 15:53:14  ANOMALY (environmental, not a game fault): after 5 minutes the inspector pipe answers 'game_busy: four requests already waiting' (the game's main loop is not draining requests); the game window is not the foreground window (Unity pauses its update loop unfocused). Action: bring the game window to the foreground once (OS call, not an inspector action) and re-read status once; if still busy, abort.
- 15:53:14  SetForegroundWindow returned True; foreground is game now: True
- 15:53:27  status after focus: {"v":1,"id":634426,"fault":{"kind":"game_busy","detail":"four requests already waiting"}}
- 15:54:12  status 40 s later: {"v":1,"id":618276,"fault":{"kind":"game_busy","detail":"four requests already waiting"}}
- 15:54:32  ABORT: the game's main loop produced no output since 15:48:01 (Player.log) and the inspector pipe has answered game_busy for 7 minutes (4 queued requests never drained) although the process shows CPU use and 'responding'. No action was dispatched, no capture started. Per the session rules: stop, restore, report. No retry without the owner.
- 15:54:34  game closed: True
- 15:54:34  log pair preserved: FM27Inspector-actions.log 17408; LogOutput.log 5975; Player.log 7587
- 15:54:35  RESTORED DLL 1C698C3DB45DC59FCF01FDA0C4A8A64819DDC6185982237898FF29638FFD7C6F ok=True; cfg 9231F4BB99C0B64B67759FA331D43BBF7AF0D1B9DC7A46D0A313F8711886CE9B ok=True
- 15:54:35  cfg values: Enabled = true | DumpFolder = C:\Users\Admin\FMSKINNING\workspace\notes\ui-dumps | AllowActions = false  (AllowActions flipped back to false)
- 15:54:35  verify-stock after: STOCK: 67 of 67 UI bundles equal the stock reference hash; update status: same

## Outcome (2026-11-14)
ABORTED at startup, nothing dispatched. Plugin 0.5.1 loaded normally (`[Inspector] 0.5.1-capture ready ... (actions: True)`, startup line hooks=none, Transitions=True) but the game never became ready: the pipe answered `game_busy: four requests already waiting` for 7 minutes (the four requests are the status polls of the first minutes; they were never drained), Player.log was silent from 15:48:01 (49 s after launch), the process showed rising CPU (222 s at 15:51, 415 s at 15:54) and `Responding = True`, and the game window was not the foreground window until I brought it forward once at 15:53 (an OS call, logged), after which nothing changed. No inspector action, hover, press or capture ran. Closed by CloseMainWindow (no kill needed). Restored by value: DLL 1C698C3D, cfg 9231F4BB (AllowActions false); verify-stock 67 of 67 before and after; log pair (LogOutput, Player, actions log) preserved.

**Not known:** why the main loop stalled. Hypotheses, none tested: (1) the window was not focused from the start (earlier sessions launched with the owner at the PC, the window in front; Unity can pause its update loop when unfocused); (2) a startup stall unrelated to the plugin (earlier launches of 0.3.1 to 0.4.0 were fine); (3) 0.5.1 itself (its startup code only logs; the new actions run only when called). Testing any of them needs a launch, which the rules forbid without the owner.
