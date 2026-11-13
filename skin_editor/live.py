"""Live preview loop (Windows): write the project as a native skin into skins/<id>-preview/, ask FM to reload skins, screenshot the game
window through the inspector pipe. It never touches the game's bundles (only native.export runs). When the pipe is unavailable it says
why and returns mode "static": the UI then shows the static repaint (preview.evaluate) instead."""
import re
import time
from pathlib import Path

from . import inspector, native
from . import project as project_mod

RELOAD_LABELS = ("Reload Skin", "Reload skin")


def preview_id(name):
    return (re.sub(r"[^\w.-]", "-", name).strip("-.") or "skin")[:50] + "-preview"


def run(ws, project, index, aa_dir, skins_root=None, transport=None, wait=0.25, settle=10.0, shot_wait=6.0, sleep=time.sleep, skin_id=None):
    """Returns {mode: live|static, exported, skin_id, steps: [...], reason?, reloaded, screenshot?}. Errors that are not about the pipe
    (a project that cannot be exported) are raised. skin_id: write into this skin folder instead of <name>-preview (it must be a folder
    this editor wrote; used to refresh the skin that is already selected in the game)."""
    p = project_mod.validate(project_mod.migrate(project))
    root = Path(skins_root) if skins_root else native.skins_root()
    if root is None:
        raise ValueError("no FM27 user folder found (Documents/Sports Interactive/Football Manager 27)")
    root.mkdir(parents=True, exist_ok=True)
    sid = skin_id or preview_id(p["name"])
    rep = native.export(ws, p, index, aa_dir, root, sid, p["name"] if skin_id else "%s (preview)" % p["name"])
    out = {"mode": "live", "skin_id": sid, "exported": rep["folder"], "problems": rep["problems"], "skipped": rep["skipped"], "steps": [], "reloaded": False}
    step = lambda s: out["steps"].append(s)
    step("exported %s (%d tokens, %d rules, %d images)" % (sid, rep["tokens"], rep["rules"], rep["images"]))
    try:
        st = inspector.status(transport)
        step("inspector online: game %s, scene %s" % (st.get("game"), st.get("scene")))
    except inspector.Offline as ex:
        return dict(out, mode="static", reason=str(ex), steps=out["steps"] + ["inspector offline: " + str(ex)])
    try:
        found = inspector.call("find", {"query": "Reload Skin", "visibleOnly": True, "max": 5}, 8.0, transport).get("matches", [])
        btn = next((m for m in found if any(l.lower() in ((m.get("label") or "") + " " + (m.get("text") or "")).lower() for l in RELOAD_LABELS)), None)
        if btn is None:
            out["reload_note"] = "No visible Reload Skin button: open Preferences (cog) > Skin, select \"%s (preview)\" once, then run the preview again." % p["name"]
            step(out["reload_note"])
        else:
            inspector.call("click", {"path": btn["path"], "expect": "Reload"}, 10.0, transport)
            out["reloaded"] = True
            step("clicked Reload Skin (%s)" % btn["path"])
            sleep(settle)
    except inspector.Fault as ex:
        out["reload_note"] = "Reload was not triggered (%s)%s" % (ex, " - set [Inspector] AllowActions = true in BepInEx/config/app.hubert.fm27inspector.cfg" if ex.kind in ("actions_disabled", "forbidden", "disabled") or "AllowActions" in ex.detail else "")
        step(out["reload_note"])
    except inspector.Offline as ex:
        return dict(out, mode="static", reason=str(ex), steps=out["steps"] + ["inspector went offline: " + str(ex)])
    name = "%s-%s" % (sid, time.strftime("%H%M%S"))
    try:
        shot = inspector.call("screenshot", {"file": name}, 8.0, transport)
    except inspector.Fault as ex:
        return dict(out, mode="static", reason="the screenshot failed: %s" % ex, steps=out["steps"] + ["screenshot failed: %s" % ex])
    except inspector.Offline as ex:
        return dict(out, mode="static", reason=str(ex), steps=out["steps"] + ["inspector went offline: " + str(ex)])
    f = Path(shot["file"])
    t0 = time.time()
    while not (f.is_file() and f.stat().st_size > 0) and time.time() - t0 < shot_wait:          # written at the end of the game's frame
        sleep(wait)
    if not f.is_file():
        return dict(out, mode="static", reason="the game did not write the screenshot within %.0f s" % shot_wait, steps=out["steps"] + ["no screenshot file appeared"])
    out["screenshot"] = str(f)
    out["bytes"] = f.stat().st_size
    step("screenshot %s (%d bytes)" % (f.name, out["bytes"]))
    return out
