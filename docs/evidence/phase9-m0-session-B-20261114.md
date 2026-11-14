# Phase 9 Session B (solo), 2026-11-14: capture-0.3.0 install and modes 1 and 2

Owner approval: install granted for Session B after M0 banked; AllowActions false; read-only; abort on any anomaly.

## Log

- 10:33:36  game closed: True
- 10:33:37  verify-stock before: STOCK: 67 of 67 UI bundles equal the stock reference hash; update status: same
- 10:33:37  backup dir C:\Users\Admin\AppData\Local\FM27SkinEditor\backups\inspector-sessionB-20261114T093337Z
- 10:33:37  installed DLL sha256 1C698C3DB45DC59FCF01FDA0C4A8A64819DDC6185982237898FF29638FFD7C6F (backup copy 1C698C3DB45DC59FCF01FDA0C4A8A64819DDC6185982237898FF29638FFD7C6F); cfg sha256 E9C0965F1ACBAAB2B89BE437D5421AFA7FB7E03E062479243B81218A26C459FD (backup copy E9C0965F1ACBAAB2B89BE437D5421AFA7FB7E03E062479243B81218A26C459FD)
- 10:33:37  installed capture-0.3.0 DLL, sha256 445AD326FBDCBF1520140AA5B2FA819C8057CF3E605C484CB2E4988E367C44D9 (staged 445AD326FBDCBF1520140AA5B2FA819C8057CF3E605C484CB2E4988E367C44D9)
- 10:33:37  cfg for session B: Enabled = true | AllowActions = false | [Capture] | Enabled = true | Styles = true | Sources = true
- 10:33:37  cfg sha256 now 6A9FED11DCA89A50973762966902B2A9F069511437A606518BBA613E59A7A983
- 10:33:37  log before launch: 6111 bytes
- 10:33:37  launch requested via Steam
- 10:33:41  fm.exe up after 4s: True
- 10:33:44  pipe present after 3s: False
- 10:33:53  status after ~0s: {"v":1,"id":644083,"ms":7.83,"result":{"plugin":"0.3.0-capture","game":"27.0.1.2503222","unity":"6000.3.18f1-custom","scene":"BootToInit","roots":0,"pid":5284}}
- 10:34:41  start screen: True after ~40s; {"plugin":"0.3.0-capture","game":"27.0.1.2503222","unity":"6000.3.18f1-custom","scene":"4fcca581ce88cf84fa2ac5e34f54e7de","roots":5,"pid":5284}
- 10:34:49  probe dump_tree: {"v":1,"id":770532,"fault":{"kind":"not_found","detail":"path breaks at step 2 (UIDocumentRootElement#UIHighlighting-container.unity-ui-document__root has 2 children)"}}
- 10:34:49  capture_status idle: {"v":1,"id":683360,"ms":0.38,"result":{"state":"none"}}
- 10:34:57  capture_start: {"v":1,"id":674099,"ms":6.73,"result":{"id":"20261114-103457","mode":"styles","state":"running","elements":0,"skipped":0,"frames":0,"seconds":0,"file":"D:\\drive\\FM27-Crimson\\workspace\\notes\\ui-dumps\\styles-sessionB-start-screen-20261114-103457.ndjson","pending":5,"error":null}}
- 10:35:00  capture_status after ~3s: {"v":1,"id":786176,"ms":0.01,"result":{"id":"20261114-103457","mode":"styles","state":"done","elements":479,"skipped":0,"frames":9,"seconds":3,"file":"D:\\drive\\FM27-Crimson\\workspace\\notes\\ui-dumps\\styles-sessionB-start-screen-20261114-103457.ndjson","pending":0,"error":null}}
- 10:35:16  capture read offline: complete=True elements=479 skipped=0 unvisited=0, sources=5 subtrees (start screen), plugin 0.3.0-capture; file styles-sessionB-start-screen-20261114-103457.ndjson 1,381,603 bytes
- 10:35:56  CloseMainWindow; alive after 40s: True
- 10:35:56  find Exit: {"v":1,"id":450109,"ms":6.53,"result":{"matches":[{"path":"P3/0/14/0/0/0/0/0/0/0/0/0","label":"SIText#dialog-title.sitext.thematic-modal.modal-text-primary","text":"Exit Game?","visible":true,"depth":11},{"path":"P3/0/14/0/0/0/0/0/0/0/0/1","label":"SIText#dialog-description.sitext.body-md.text-middl
- 10:36:13  CloseMainWindow raised the game's 'Exit Game?' dialog (start screen, no career, nothing to save); AllowActions is false in Session B so it cannot be confirmed through the inspector; ending the process with Stop-Process instead (no save state involved).
- 10:36:18  game closed: True
- 10:36:31  log pair preserved: LogOutput.log 6428 bytes sha 5DB697AC3446F2F9; Player.log 24472 bytes sha 7EDCF95DA46BD75A
- 10:36:31  LogOutput capture/inspector lines: [Info   :   BepInEx] Loading [FM27 Crimson Inspector 0.3.0-capture] || [Info   :FM27 Crimson Inspector] [Capture] startup: hooks=none (property reads only); Enabled=True Styles=True Sources=True Transitions=False(not buil || [Info   :Il2CppInterop] Registered mono type Crimson.Inspector.InspectorTick in il2cpp domain || [Info   :FM27 Crimson Inspector] [Inspector] 0.3.0-capture ready on \\.\pipe\fm27-crimson-inspector (actions: False, same-user only) || [Warning:   AutoDev] [Startup] self-check FAILED: event capture: FM.GamePlugin.GameInteropSubsystem.SendEvent - type not found || [Info   :   AutoDev] [Apply] SendEvent capture installed || [Warning:FM27 Crimson Inspector] [Inspector] connection dropped: Pipe is broken. || [Info   :FM27 Crimson Inspector] [Capture] session 20261114-103457 started: mode styles -> D:\drive\FM27-Crimson\workspace\notes\ui-dumps\styles-sessi
- 10:36:31  restored DLL sha256 1C698C3DB45DC59FCF01FDA0C4A8A64819DDC6185982237898FF29638FFD7C6F (expected 1C698C3D...: True); cfg sha256 E9C0965F1ACBAAB2B89BE437D5421AFA7FB7E03E062479243B81218A26C459FD (expected E9C0965F...: True)
- 10:36:31  cfg values: Enabled = true | MainThreadBudgetMs = 600 | AllowActions = false
- 10:36:31  verify-stock after: STOCK: 67 of 67 UI bundles equal the stock reference hash; update status: same
- 10:36:31  Session B result: capture-0.3.0 ran clean on the start screen (modes 1+2, 479 elements, 0 skipped, complete, 3 s, 9 frames); no crash, no hang. A Squad-screen capture needs clicks (AllowActions true) or the owner navigating by hand; not done in this solo session.
- 10:37  the AutoDev self-check warning (SendEvent type not found) is also in Session A's log with the old DLL: pre-existing, unrelated to the capture build.
