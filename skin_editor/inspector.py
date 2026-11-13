"""Client of the FM27 Crimson Inspector (BepInEx plugin FM27Inspector): a same-user named pipe, one JSON request line in, one reply line out.
The same pipe the `fm27` MCP server uses. Windows only; elsewhere, or with the game not running or the plugin not loaded, every call raises
Offline with the reason, and callers fall back to the static preview."""
import json
import os
import threading
import time

PIPE = r"\\.\pipe\fm27-crimson-inspector"


class Offline(Exception):
    """The pipe cannot be used: game not running, plugin not loaded, or not Windows. str() is the reason shown in the UI."""


class Fault(Exception):
    """The plugin answered with a fault (kind, detail), e.g. actions_disabled, expect_mismatch, not_found."""

    def __init__(self, kind, detail):
        super().__init__("%s: %s" % (kind, detail))
        self.kind, self.detail = kind, detail


_next = [1]


def _pipe_transport(line, timeout):
    if os.name != "nt":
        raise Offline("the inspector pipe is a Windows named pipe; this platform has no live preview yet")
    try:
        f = open(PIPE, "r+b", buffering=0)
    except FileNotFoundError:
        raise Offline("FM27 is not running with the inspector plugin (no %s pipe)" % PIPE)
    except OSError as ex:
        raise Offline("the inspector pipe cannot be opened (%s)" % ex)
    box = {}

    def work():
        try:
            f.write(line)
            buf = b""
            while b"\n" not in buf:
                chunk = f.read(65536)
                if not chunk:
                    break
                buf += chunk
            box["reply"] = buf.split(b"\n", 1)[0]
        except Exception as ex:                                  # a broken pipe: reported below
            box["error"] = ex

    t = threading.Thread(target=work, daemon=True)
    t.start()
    t.join(timeout)
    if t.is_alive():
        try:
            f.close()
        except Exception:
            pass
        raise Offline("the inspector did not answer within %.0f s (the game may be loading)" % timeout)
    f.close()
    if "error" in box:
        raise Offline("the inspector pipe broke (%s)" % box["error"])
    return box.get("reply", b"")


def call(tool, params=None, timeout=8.0, transport=None):
    """One tool call; returns the result dict (with 'ms'). Raises Offline or Fault."""
    rid = _next[0]
    _next[0] += 1
    line = (json.dumps({"id": rid, "tool": tool, "params": params or {}}) + "\n").encode("utf-8")
    raw = (transport or _pipe_transport)(line, timeout)
    try:
        reply = json.loads(raw.decode("utf-8"))
    except ValueError:
        raise Offline("the inspector sent something that is not JSON")
    if reply.get("fault"):
        f = reply["fault"]
        if f.get("kind") == "offline":
            raise Offline(f.get("detail", "offline"))
        raise Fault(f.get("kind", "fault"), f.get("detail", ""))
    out = dict(reply.get("result") or {})
    out["ms"] = reply.get("ms")
    return out


def status(transport=None, timeout=3.0):
    """Game and plugin versions when the pipe answers, else raises Offline."""
    return call("status", {}, timeout, transport)
