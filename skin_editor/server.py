"""Localhost JSON API and static frontend. Binds to 127.0.0.1, per-session token, Host check."""
import hmac
import json
import subprocess
import time
import io
import os
import re
import secrets
import sys
import threading
import webbrowser
from pathlib import Path
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from . import bundles, colour, config, detect, images, native, preview, skins, index_styles, install, launcher, layout, layout_dump, layout_join, layout_view, patcher, placement, verify
from .presets import PRESETS
from . import project as project_mod


from .api import rpc
from .engine import Engine, PlacementRefused

App = Engine          # the name the first server and its tests use


ROUTES = {
    ("GET", "/api/state"): App.state, ("POST", "/api/detect"): App.do_detect, ("POST", "/api/config"): App.set_game,
    ("POST", "/api/snapshot"): App.snapshot, ("POST", "/api/reference-hashes"): App.reference_hashes, ("POST", "/api/index"): App.do_index,
    ("GET", "/api/job"): lambda a, q, b: a.job,
    ("GET", "/api/tokens"): App.tokens, ("GET", "/api/token"): App.token,
    ("GET", "/api/literals"): App.literals, ("GET", "/api/literal"): App.literal,
    ("GET", "/api/projects"): App.projects, ("GET", "/api/project"): App.get_project,
    ("POST", "/api/project"): App.save_project, ("POST", "/api/build"): App.build,
    ("POST", "/api/preset"): App.preset, ("POST", "/api/reach"): App.reach,
    ("POST", "/api/install"): App.do_install, ("GET", "/api/backups"): App.backups,
    ("POST", "/api/restore"): App.restore, ("POST", "/api/launcher"): App.make_launcher, ("POST", "/api/quit"): App.quit, ("GET", "/api/layout/state"): App.layout_state, ("POST", "/api/layout/import"): App.layout_import,
    ("GET", "/api/layout/screens"): App.view_screens, ("GET", "/api/layout/screen"): App.view_screen, ("GET", "/api/layout/outline"): App.view_outline,
    ("GET", "/api/placement/list"): App.placement_list, ("POST", "/api/placement/check"): App.placement_check,
    ("POST", "/api/placement/add"): App.placement_add, ("POST", "/api/placement/remove"): App.placement_remove,
    ("GET", "/api/where/token"): App.where_token, ("GET", "/api/where/literal"): App.where_literal, ("GET", "/api/where/search"): App.where_search, ("GET", "/api/models"): App.models, ("GET", "/api/preview/models"): App.preview_models, ("GET", "/api/preview/model"): App.preview_model,
    ("GET", "/api/images/catalog"): App.images_catalog, ("GET", "/api/images/thumb"): App.images_thumb,
    ("GET", "/api/images/source"): App.images_source, ("POST", "/api/images/swap"): App.images_swap, ("POST", "/api/images/remove"): App.images_remove,
    ("GET", "/api/images/export"): App.images_export, ("POST", "/api/images/export-all"): App.images_export_all, ("POST", "/api/open-folder"): App.open_folder,
    ("GET", "/api/native/info"): App.native_info, ("POST", "/api/images/where"): App.images_where, ("POST", "/api/native/export"): App.native_export,
    ("POST", "/api/compare/load"): App.compare_load, ("GET", "/api/compare/state"): App.compare_state, ("GET", "/api/compare/asset"): App.compare_asset,
    ("GET", "/api/compare/thumb"): App.compare_thumb, ("POST", "/api/compare/import"): App.compare_import,
    ("GET", "/api/preview/image"): App.preview_image, ("GET", "/api/preview/suggest"): App.preview_suggest, ("POST", "/api/verify"): App.do_verify,
}


# Origins of the desktop shell (Tauri webview, and its Vite dev server). The session token is still required on every request
# except the preflight, so another page in the browser cannot call the engine even if it knew the port.
SHELL_ORIGINS = ("tauri://localhost", "http://tauri.localhost", "https://tauri.localhost", "http://localhost:1420", "http://127.0.0.1:1420")

RAW_ROUTES = ("/api/verify", "/api/layout/import", "/api/images/swap")


def make_handler(app, token, port, instance=""):
    hosts = {"127.0.0.1:%d" % port, "localhost:%d" % port}

    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def log_message(self, *a):
            pass

        def _send(self, code, body, ctype="application/json", download=None):
            data = body if isinstance(body, bytes) else json.dumps(body).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            if download:
                self.send_header("Content-Disposition", 'attachment; filename="%s"' % re.sub(r'[^\w.@-]', "_", download))
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self._cors()
            self.end_headers()
            self.wfile.write(data)

        def _cors(self):
            origin = self.headers.get("Origin")
            if origin in SHELL_ORIGINS:
                self.send_header("Access-Control-Allow-Origin", origin)
                self.send_header("Vary", "Origin")

        def do_OPTIONS(self):
            """CORS preflight from the shell: allowed origins only, no token needed (it carries no data)."""
            origin = self.headers.get("Origin")
            if self.headers.get("Host") not in hosts or origin not in SHELL_ORIGINS:
                self.send_response(403)
                self.send_header("Content-Length", "0")
                self.end_headers()
                return
            self.send_response(204)
            self.send_header("Access-Control-Allow-Origin", origin)
            self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "X-Token, Content-Type")
            self.send_header("Access-Control-Max-Age", "600")
            self.send_header("Vary", "Origin")
            self.send_header("Content-Length", "0")
            self.end_headers()

        def _handle(self, method):
            u = urlparse(self.path)
            q = {k: v[0] for k, v in parse_qs(u.query).items()}
            n = int(self.headers.get("Content-Length") or 0)
            raw = self.rfile.read(n) if n else b""
            if self.headers.get("Host") not in hosts:
                return self._send(403, {"error": "bad host"})
            if method == "GET" and u.path == "/ping":      # no token: lets the launcher identify this server
                return self._send(200, ("%s %s" % (launcher.APP_ID, instance)).encode(), "text/plain")
            given = self.headers.get("X-Token") or q.get("t", "")
            if not hmac.compare_digest(given.encode(), token.encode()):
                return self._send(403, {"error": "missing or wrong session token"})
            if method == "POST" and u.path == "/rpc":           # JSON-RPC 2.0: one request or a batch
                out = rpc.handle(app, raw.decode("utf-8", errors="replace"))
                if out is None:
                    self.send_response(204)
                    self.send_header("Content-Length", "0")
                    self.end_headers()
                    return
                return self._send(200, out.encode("utf-8"), "application/json")
            if method == "GET" and u.path == "/events":         # server-sent events: job.* and other engine events
                return self._events()
            if method == "GET" and u.path == "/":
                page = (config.resource_root() / "frontend" / "index.html").read_bytes()
                return self._send(200, page, "text/html; charset=utf-8")
            fn = ROUTES.get((method, u.path))
            if not fn:
                return self._send(404, {"error": "not found"})
            try:
                body = raw if u.path in RAW_ROUTES else (json.loads(raw.decode("utf-8")) if raw else {})
                res = fn(app, q, body)
                if isinstance(res, tuple) and len(res) in (2, 3) and isinstance(res[0], bytes):   # (bytes, type[, download name])
                    return self._send(200, res[0], res[1], res[2] if len(res) == 3 else None)
                self._send(200, res)
            except PlacementRefused as e:
                self._send(409 if e.err.requires_confirm else 400, {"error": str(e), "blocks": e.err.blocks, "warnings": e.err.warnings,
                                                                    "collisions": e.err.collisions, "requires_confirm": e.err.requires_confirm})
            except layout_dump.LayoutError as e:
                self._send(400, {"error": str(e), "errors": e.errors, "total_errors": e.total})
            except Exception as e:
                self._send(400, {"error": "%s: %s" % (type(e).__name__, e)})

        def _events(self):
            """Stream the engine's events as text/event-stream until the client goes away. A comment line every 15 s keeps
            proxies and the client's reconnect timer quiet."""
            import queue as _queue
            sub = app.events.subscribe()
            self.close_connection = True
            try:
                self.send_response(200)
                self.send_header("Content-Type", "text/event-stream")
                self.send_header("Cache-Control", "no-store")
                self.send_header("Connection", "close")
                self._cors()
                self.end_headers()
                self.wfile.write(b": connected\n\n")
                self.wfile.flush()
                while True:
                    try:
                        ev = sub.get(timeout=15)
                        self.wfile.write(("id: %d\nevent: %s\ndata: %s\n\n" % (ev["seq"], ev["type"], json.dumps(ev, default=str))).encode("utf-8"))
                    except _queue.Empty:
                        self.wfile.write(b": ping\n\n")
                    self.wfile.flush()
            except (BrokenPipeError, ConnectionError, OSError):
                pass
            finally:
                app.events.unsubscribe(sub)

        def do_GET(self):
            self._handle("GET")

        def do_POST(self):
            self._handle("POST")

    return Handler


def _write_state(ws, name, text):
    tmp = ws.state / (name + ".tmp")
    tmp.write_text(text + "\n", encoding="utf-8")
    os.replace(tmp, ws.state / name)


def serve(open_browser=None):
    app = App()
    port = app.cfg["server"]["port"]
    token = secrets.token_urlsafe(24)       # rotated on every server start
    instance = secrets.token_hex(8)
    httpd = ThreadingHTTPServer(("127.0.0.1", port), make_handler(app, token, port, instance))
    app.httpd = httpd
    url = "http://127.0.0.1:%d/?t=%s" % (port, token)
    _write_state(app.ws, "instance-id", instance)   # after a successful bind: a failed start never clobbers
    _write_state(app.ws, "last-url", url)           # the running server's state
    print(url, flush=True)
    if app.cfg["server"]["open_browser"] if open_browser is None else open_browser:
        webbrowser.open(url)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()
        try:
            if (app.ws.state / "instance-id").read_text(encoding="utf-8").strip() == instance:
                (app.ws.state / "instance-id").unlink()
                (app.ws.state / "last-url").unlink()
        except OSError:
            pass
    return httpd
