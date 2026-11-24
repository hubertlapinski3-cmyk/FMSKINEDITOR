"""Phase 0: the engine behind a typed API. Schemas, the method table (parity with the first server's routes), JSON-RPC dispatch,
the job queue and its events, the HTTP transport (/rpc, /events) and the CLI."""
import base64, contextlib, io, json, logging, os, tempfile, threading, time, unittest, urllib.error, urllib.request
from pathlib import Path
from unittest import mock

from skin_editor import __main__ as cli, project, server
from skin_editor.api import rpc
from skin_editor.api.jobs import EventBus, JobQueue
from skin_editor.api.methods import methods
from skin_editor.api.schema import SchemaError, validate
from skin_editor.engine import Engine
from tests.test_preview import index


class Schema(unittest.TestCase):
    def test_types_optionals_and_unknowns(self):
        s = {"name": "str", "n": "int?", "f": "num?", "on": "bool?", "pid": "id?", "kind": ("opt", ("enum", ["a", "b"])), "xs": ("opt", ("list", "int"))}
        self.assertEqual(validate(s, {"name": "x", "n": None}), {"name": "x"})
        self.assertEqual(validate(s, {"name": "x", "pid": "-2872719585425638372", "xs": [1, 2], "kind": "b"})["xs"], [1, 2])
        for bad, needle in (({}, "missing parameter name"), ({"name": 1}, "name must be str"), ({"name": "x", "n": True}, "n must be int"),
                            ({"name": "x", "pid": 5}, "decimal string"), ({"name": "x", "pid": "1e3"}, "decimal string"),
                            ({"name": "x", "kind": "c"}, "one of a, b"), ({"name": "x", "xs": [1, "2"]}, "xs[1] must be int"),
                            ({"name": "x", "zz": 1}, "unknown parameter zz"), ("no", "params must be an object")):
            with self.assertRaises(SchemaError) as c: validate(s, bad)
            self.assertIn(needle, str(c.exception), bad)
        with self.assertRaises(SchemaError) as c: validate(s, {"n": "x", "zz": 1})
        self.assertEqual(len(c.exception.problems), 3)                     # every problem is reported, not just the first


class Table(unittest.TestCase):
    def test_every_route_of_the_first_server_has_a_method_and_back(self):
        routes = {m.route for m in methods().values() if m.route}
        self.assertEqual(routes, set(server.ROUTES))                       # parity both ways
        self.assertEqual(len(routes), len([m for m in methods().values() if m.route]))   # no route claimed twice

    def test_methods_point_at_real_engine_operations(self):
        for m in methods().values():
            if m.attr is not None:
                self.assertTrue(callable(getattr(Engine, m.attr, None)), m.name)
                if m.route: self.assertIs(server.ROUTES[m.route], getattr(Engine, m.attr), m.name)   # the same function both surfaces call (API-only methods have no route)
            self.assertRegex(m.name, r"^[a-z]+\.[a-z_]+$"); self.assertTrue(m.doc, m.name)
            self.assertIn(m.kind, ("call", "job", "binary"))
        raw = {m.route[1] for m in methods().values() if m.body == "data"}
        self.assertEqual(raw, set(server.RAW_ROUTES))                      # byte-body methods are exactly the raw routes


class Jobs(unittest.TestCase):
    def test_jobs_run_in_order_with_progress_events_and_errors(self):
        bus = EventBus(); q = JobQueue(bus); sub = bus.subscribe(); order = []; gate = threading.Event()
        def slow(prog): gate.wait(5); prog("half", 0.5); order.append("a"); return {"n": 1}
        def boom(prog): order.append("b"); raise RuntimeError("no")
        a, b, c = q.submit("first", slow), q.submit("second", boom), q.submit("third", lambda prog: order.append("c") or 3)
        self.assertEqual([j["state"] for j in q.list()][1:], ["queued", "queued"])
        self.assertTrue(q.cancel(c.id)); self.assertFalse(q.cancel(c.id) if q.get(c.id).state == "queued" else False)
        gate.set(); q.wait(b.id, 5)
        self.assertEqual(order, ["a", "b"])                                # one at a time, in order; the cancelled one never ran
        self.assertEqual((a.view()["state"], a.view()["result"], a.view()["title"]), ("done", {"n": 1}, "first"))
        self.assertEqual((b.view()["state"], b.view()["error"]), ("failed", "RuntimeError: no"))
        self.assertEqual(a.legacy()["running"], False); self.assertEqual(q.latest_legacy()["id"], c.id)
        types = []
        while not sub.empty(): types.append(sub.get()["type"])
        for t in ("job.queued", "job.started", "job.progress", "job.done", "job.failed", "job.cancelled"): self.assertIn(t, types)
        with self.assertRaises(KeyError): q.get("j999")

    def test_slow_subscribers_lose_old_events_and_never_block(self):
        bus = EventBus(backlog=3); sub = bus.subscribe()
        for i in range(10): bus.publish("x", i)
        got = [sub.get()["data"] for _ in range(3)]; self.assertEqual(got, [7, 8, 9])
        bus.unsubscribe(sub); bus.publish("x", 1); self.assertTrue(sub.empty())


def engine(tmp):
    with mock.patch.dict(os.environ, {"FM27SE_WORKSPACE": tmp}):
        e = Engine()
    e.index = index()
    return e


def close_logs():
    for h in list(logging.getLogger("skin_editor").handlers): logging.getLogger("skin_editor").removeHandler(h); h.close()


class Rpc(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True); self.addCleanup(self.tmp.cleanup); self.addCleanup(close_logs)
        self.e = engine(self.tmp.name)

    def rpc(self, method, params=None, id_=1):
        req = {"jsonrpc": "2.0", "method": method, "id": id_}
        if params is not None: req["params"] = params
        return json.loads(rpc.handle(self.e, json.dumps(req)))

    def test_project_routing_choices_are_explicit_and_saved(self):
        self.rpc("project.create", {"name": "routing"})
        r = self.rpc("project.routing", {"project": "routing"})["result"]
        self.assertEqual(r["route_preference"], "bundle")                 # default, not stored
        self.assertFalse(r["route_preference_explicit"])
        self.assertFalse(r["edit_competition_sheets"])
        self.assertIn("changes the game files", r["tradeoffs"]["bundle"])
        self.assertIn("changes no game file", r["tradeoffs"]["skin_folder"])
        r = self.rpc("project.set_routing", {"project": "routing", "route_preference": "skin_folder",
                                             "edit_competition_sheets": True})["result"]
        self.assertEqual((r["route_preference"], r["route_preference_explicit"]), ("skin_folder", True))
        self.assertTrue(r["edit_competition_sheets"])
        self.assertTrue(r["edit_competition_sheets_explicit"])
        stored = self.rpc("project.get", {"name": "routing"})["result"]["options"]
        self.assertEqual(stored["route_preference"], "skin_folder")
        self.assertTrue(stored["route_preference_explicit"])
        self.assertTrue(stored["edit_competition_sheets_explicit"])

    def test_calls_errors_and_batches(self):
        self.assertEqual(self.rpc("project.list")["result"], [])
        r = self.rpc("project.create", {"name": "demo"}); self.assertEqual(r["result"]["project"]["name"], "demo")
        p = self.rpc("project.get", {"name": "demo"})["result"]; p["token_overrides"] = [{"token": "--base", "value": "#AA0000"}]
        self.assertEqual(self.rpc("project.save", {"project": p})["result"]["project"]["token_overrides"][0]["value"], {"rgb": "#AA0000", "a": 1.0})
        self.assertEqual(self.rpc("tokens.get", {"name": "--base"})["result"]["name"], "--base")
        every, coloured = self.rpc("tokens.list", {"colours": False})["result"]["total"], self.rpc("tokens.list", {"colours": True})["result"]["total"]
        self.assertEqual((every, coloured), (6, 4))                        # bool -> the flag the engine reads (the two looping tokens have no colour)
        for req, code in ((self.rpc("nope.nope"), -32601), (self.rpc("tokens.get", {}), -32602), (self.rpc("tokens.get", {"name": 1}), -32602),
                          (self.rpc("tokens.get", {"name": "--missing"}), -32004), (self.rpc("project.create", {"name": "demo"}), -32000)):
            self.assertEqual(req["error"]["code"], code, req)
        self.assertEqual(self.rpc("tokens.get", {"name": 1})["error"]["data"]["problems"], ["name must be str"])
        self.assertEqual(json.loads(rpc.handle(self.e, "{not json"))["error"]["code"], -32700)
        self.assertEqual(json.loads(rpc.handle(self.e, json.dumps({"method": "project.list", "id": 1})))["error"]["code"], -32600)
        self.assertEqual(json.loads(rpc.handle(self.e, json.dumps({"jsonrpc": "2.0", "method": "project.list", "params": [1], "id": 1})))["error"]["code"], -32602)
        self.assertIsNone(rpc.handle(self.e, json.dumps({"jsonrpc": "2.0", "method": "project.list"})))          # a notification: no reply
        batch = json.loads(rpc.handle(self.e, json.dumps([{"jsonrpc": "2.0", "method": "project.list", "id": "a"}, {"jsonrpc": "2.0", "method": "nope.x", "id": "b"},
                                                          {"jsonrpc": "2.0", "method": "project.list"}])))
        self.assertEqual([(x["id"], "result" in x) for x in batch], [("a", True), ("b", False)])
        self.assertEqual(json.loads(rpc.handle(self.e, "[]"))["error"]["code"], -32600)

    def test_typed_application_errors(self):
        self.rpc("project.create", {"name": "demo"})
        r = self.rpc("layout.import", {"data": base64.b64encode(b'{"meta": {"schema": "fmlayout-index/1"}}').decode()})
        self.assertEqual(r["error"]["code"], -32011); self.assertTrue(r["error"]["data"]["errors"])
        self.assertEqual(self.rpc("layout.import", {"data": "***"})["error"]["code"], -32602)                    # not base64
        self.assertEqual(self.rpc("backup.restore", {"backup": "vanilla"})["error"]["code"], -32000)             # no game selected
        self.assertEqual(self.rpc("images.remove", {"project": "demo", "bundle": "ui-x.bundle", "path_id": 5})["error"]["code"], -32602)   # ids are strings

    def test_jobs_through_rpc_and_introspection(self):
        self.e.start_job("probe", lambda prog: prog("x", 0.5) or {"ok": True})
        jid = self.rpc("jobs.list")["result"][-1]["id"]
        done = self.rpc("jobs.wait", {"id": jid, "timeout": 5})["result"]
        self.assertEqual((done["state"], done["result"]), ("done", {"ok": True}))
        self.assertEqual(self.rpc("jobs.latest")["result"]["running"], False)
        self.assertEqual(self.rpc("jobs.get", {"id": "j999"})["error"]["code"], -32004)
        ms = self.rpc("api.methods")["result"]
        self.assertEqual(len(ms), len(methods())); one = next(m for m in ms if m["name"] == "images.swap")
        self.assertEqual(one["params"]["path_id"], {"type": "id", "required": True}); self.assertEqual(one["params"]["fit"]["required"], False)


class Transport(unittest.TestCase):
    def test_http_rpc_and_event_stream(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            e = engine(tmp)
            httpd = server.ThreadingHTTPServer(("127.0.0.1", 0), server.make_handler(e, "tok", 0)); port = httpd.server_address[1]
            th = threading.Thread(target=httpd.serve_forever, daemon=True); th.start()
            def post(body, token="tok"):
                req = urllib.request.Request("http://127.0.0.1:%d/rpc" % port, data=json.dumps(body).encode(), headers={"X-Token": token, "Host": "127.0.0.1:0"})
                try: r = urllib.request.urlopen(req); return r.status, r.read()
                except urllib.error.HTTPError as ex: return ex.code, ex.read()
            try:
                code, body = post({"jsonrpc": "2.0", "method": "project.list", "id": 7}); self.assertEqual((code, json.loads(body)), (200, {"jsonrpc": "2.0", "id": 7, "result": []}))
                self.assertEqual(post({"jsonrpc": "2.0", "method": "project.list"})[0], 204)                     # notification
                self.assertEqual(post({"jsonrpc": "2.0", "method": "project.list", "id": 1}, token="wrong")[0], 403)
                # the event stream delivers job events
                req = urllib.request.Request("http://127.0.0.1:%d/events" % port, headers={"X-Token": "tok", "Host": "127.0.0.1:0"})
                stream = urllib.request.urlopen(req, timeout=10)
                self.assertEqual(stream.headers.get("Content-Type"), "text/event-stream"); self.assertEqual(stream.readline(), b": connected\n")
                e.start_job("stream probe", lambda prog: 1)
                seen, deadline = [], time.time() + 8
                while time.time() < deadline and "job.done" not in seen:
                    line = stream.readline().decode().strip()
                    if line.startswith("event: "): seen.append(line[7:])
                    if line.startswith("data: ") and seen and seen[-1] == "job.done": self.assertEqual(json.loads(line[6:])["data"]["state"], "done")
                self.assertEqual(seen[:2], ["job.queued", "job.started"]); self.assertIn("job.done", seen)
                stream.close()
                # the first frontend's routes still work next to it
                r = urllib.request.urlopen(urllib.request.Request("http://127.0.0.1:%d/api/job" % port, headers={"X-Token": "tok", "Host": "127.0.0.1:0"}))
                self.assertEqual(json.loads(r.read())["running"], False)
            finally:
                httpd.shutdown(); httpd.server_close(); th.join(5); close_logs()


class Cli(unittest.TestCase):
    def run_cli(self, *argv):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = cli.main(list(argv))
        return code, out.getvalue(), err.getvalue()

    def test_rpc_and_methods_commands(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp, mock.patch.dict(os.environ, {"FM27SE_WORKSPACE": tmp}):
            try:
                code, out, _ = self.run_cli("methods"); self.assertEqual(code, 0); self.assertEqual(len(json.loads(out)), len(methods()))
                code, out, _ = self.run_cli("methods", "--markdown"); self.assertIn("| `project.save` | call | project: obj |", out)
                code, out, _ = self.run_cli("rpc", "project.create", '{"name": "cli"}'); self.assertEqual((code, json.loads(out)["project"]["name"]), (0, "cli"))
                code, out, _ = self.run_cli("rpc", "project.list"); self.assertEqual(json.loads(out), ["cli"])
                code, out, _ = self.run_cli("rpc", "tokens.get", "{}"); self.assertEqual((code, json.loads(out)["error"]["code"]), (1, -32602))
                code, _, err = self.run_cli("rpc", "nope.nope"); self.assertEqual(code, 2); self.assertIn("no such method", err)
                code, _, err = self.run_cli("rpc", "project.list", "{bad"); self.assertEqual(code, 2)
                d = Path(tmp) / "dump.json"; d.write_text('{"meta": {"schema": "fmlayout-index/1"}}')
                code, out, _ = self.run_cli("rpc", "layout.import", "--data-file", str(d)); self.assertEqual(json.loads(out)["error"]["code"], -32011)
            finally:
                close_logs()


if __name__ == "__main__":
    unittest.main()


class FolderProjects(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True); self.addCleanup(self.tmp.cleanup); self.addCleanup(close_logs)
        self.e = engine(self.tmp.name)

    def rpc(self, method, params=None):
        return json.loads(rpc.handle(self.e, json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": params or {}})))

    def legacy(self):
        p = project.new("demo")
        p["token_overrides"] = [{"token": "--base", "value": {"rgb": "#7694FE", "a": 0.0784313725490196}, "vanilla": "#DA71FE"}, {"token": "--alias", "value": "var(--lit)"}]
        p["scoped_rules"] = [{"sheet": "AlwaysAppliedStyleSheet", "selector": ".a .b", "props": {"color": {"rgb": "#FF0000", "a": 1.0}, "padding": "4px"}, "why": "test"},
                             {"sheet": "SIStyles", "selector": "#x", "props": {"opacity": "0"}}]
        p["literal_swaps"] = [{"from": {"rgb": "#DA0037", "a": 1.0}, "to": {"rgb": "#6C001C", "a": 0.5}, "mode": "rgba"}]
        p["options"]["club_colours"] = False; p["options"]["output"] = "native"; p["rename_classes"] = {"old": "new"}
        project.save(self.e.ws, p)
        d = self.e.ws.images / "demo"; d.mkdir(parents=True); (d / "bg.png").write_bytes(b"\x89PNG\r\n\x1a\nxx")
        p["image_swaps"] = [{"bundle": "ui-backgrounds_assets_.bundle", "path_id": "-5", "name": "wall", "kind": "texture", "source": "bg.png", "fit": "cover", "where": ["loading"]}]
        project.save(self.e.ws, p)
        return project.load(self.e.ws, "demo")

    def test_migration_is_an_exact_round_trip_and_keeps_the_old_file(self):
        before = self.legacy()
        r = self.rpc("project.migrate", {"project": "demo"})["result"]
        self.assertEqual(sorted(r["files"]), ["config/options.json", "images/bg.png", "mapping.json", "skin.project.json", "styles/AlwaysAppliedStyleSheet.uss", "styles/SIStyles.uss", "styles/tokens.uss"])
        self.assertTrue((self.e.ws.projects / "demo.skin.json.migrated").is_file()); self.assertFalse((self.e.ws.projects / "demo.skin.json").exists())
        after = project.load(self.e.ws, "demo")
        self.assertEqual(json.dumps(after, sort_keys=True), json.dumps(before, sort_keys=True))
        self.assertEqual(project.to_spec(after), project.to_spec(before)); self.assertEqual(project.names(self.e.ws), ["demo"])
        self.assertEqual(project.images_dir(self.e.ws, "demo"), self.e.ws.projects / "demo" / "images")
        self.assertIn(self.rpc("project.migrate", {"project": "demo"})["error"]["code"], (-32004, -32000))        # not twice
        tok = self.rpc("project.read_file", {"project": "demo", "path": "styles/tokens.uss"})["result"]["text"]
        self.assertIn("--base: rgba(118, 148, 254, 0.0784313725490196);", tok); self.assertIn('/* meta: {"vanilla": "#DA71FE"} */', tok)

    def test_text_edits_compile_and_report_problems_with_lines(self):
        self.legacy(); self.rpc("project.migrate", {"project": "demo"})
        ok = self.rpc("project.write_file", {"project": "demo", "path": "styles/tokens.uss", "text": "/* mine */\n:root {\n    --base: #112233;\n    --other: #445566AA;\n}\n"})["result"]
        self.assertEqual(ok["problems"], [])
        p = project.load(self.e.ws, "demo")
        self.assertEqual({o["token"]: o["value"] for o in p["token_overrides"]}, {"--base": {"rgb": "#112233", "a": 1.0}, "--other": {"rgb": "#445566", "a": 170 / 255}})
        self.assertIn("/* mine */", self.rpc("project.read_file", {"project": "demo", "path": "styles/tokens.uss"})["result"]["text"])    # the text API keeps comments
        bad = self.rpc("project.write_file", {"project": "demo", "path": "styles/tokens.uss", "text": ":root {\n    color: red;\n    --x #fff;\n"})["result"]["problems"]
        self.assertTrue(any(x["file"] == "styles/tokens.uss" and "without ':'" in x["message"] for x in bad)); self.assertTrue(any("not closed" in x["message"] for x in bad))
        self.assertTrue(all(isinstance(x["line"], int) for x in bad))
        with self.assertRaises(Exception): project.load(self.e.ws, "demo")                                    # a broken project does not build
        self.assertEqual(self.rpc("project.problems", {"project": "demo"})["result"]["problems"], bad)             # the same list the write returned
        closed = self.rpc("project.write_file", {"project": "demo", "path": "styles/tokens.uss", "text": ":root {\n    color: red;\n}\n"})["result"]["problems"]
        self.assertTrue(any("not a token" in x["message"] and x["line"] == 2 for x in closed))
        self.rpc("project.write_file", {"project": "demo", "path": "styles/tokens.uss", "text": ":root { --base: #000000; }\n"})
        orphan = self.rpc("project.write_file", {"project": "demo", "path": "styles/Extra.uss", "text": ".z { color: red; }\n"})["result"]["problems"]
        self.assertTrue(any("not in mapping.json" in x["message"] for x in orphan))
        for path in ("../x.txt", "styles/../../x.uss", "C:/x.uss", "styles/a.exe"):
            self.assertIn("error", self.rpc("project.write_file", {"project": "demo", "path": path, "text": "x"}), path)
        self.assertIn("error", self.rpc("project.delete_file", {"project": "demo", "path": "mapping.json"}))
        self.assertEqual(self.rpc("project.delete_file", {"project": "demo", "path": "styles/Extra.uss"})["result"]["problems"], [])

    def test_saving_a_model_keeps_a_folder_project_a_folder(self):
        self.legacy(); self.rpc("project.migrate", {"project": "demo"})
        p = project.load(self.e.ws, "demo"); p["token_overrides"].append({"token": "--new", "value": {"rgb": "#010203", "a": 1.0}})
        self.rpc("project.save", {"project": p})
        self.assertFalse((self.e.ws.projects / "demo.skin.json").exists())
        self.assertIn("--new: #010203;", (self.e.ws.projects / "demo" / "styles" / "tokens.uss").read_text())
        files = self.rpc("project.files", {"project": "demo"})["result"]; self.assertTrue(files["folder"]); self.assertEqual(self.rpc("project.files", {"project": "nope"})["result"]["folder"], False)


class Cors(unittest.TestCase):
    def test_shell_origins_only_and_token_still_required(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            e = engine(tmp)
            httpd = server.ThreadingHTTPServer(("127.0.0.1", 0), server.make_handler(e, "tok", 0)); port = httpd.server_address[1]
            th = threading.Thread(target=httpd.serve_forever, daemon=True); th.start()
            def call(method, headers, body=None):
                req = urllib.request.Request("http://127.0.0.1:%d/rpc" % port, data=body, method=method, headers=dict(headers, Host="127.0.0.1:0"))
                try: r = urllib.request.urlopen(req); return r.status, dict(r.headers), r.read()
                except urllib.error.HTTPError as ex: return ex.code, dict(ex.headers), ex.read()
            try:
                good = {"Origin": "tauri://localhost", "Access-Control-Request-Method": "POST"}
                code, h, _ = call("OPTIONS", good); self.assertEqual(code, 204); self.assertEqual(h["Access-Control-Allow-Origin"], "tauri://localhost"); self.assertIn("X-Token", h["Access-Control-Allow-Headers"])
                self.assertEqual(call("OPTIONS", {"Origin": "https://evil.example"})[0], 403)
                self.assertEqual(call("OPTIONS", {})[0], 403)
                body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": "project.list"}).encode()
                code, h, _ = call("POST", {"Origin": "http://localhost:1420", "X-Token": "tok"}, body); self.assertEqual((code, h["Access-Control-Allow-Origin"]), (200, "http://localhost:1420"))
                code, h, _ = call("POST", {"Origin": "http://localhost:1420", "X-Token": "wrong"}, body); self.assertEqual(code, 403)       # no token, no data
                code, h, _ = call("POST", {"Origin": "https://evil.example", "X-Token": "tok"}, body); self.assertNotIn("Access-Control-Allow-Origin", h)   # the browser would block the read
            finally:
                httpd.shutdown(); httpd.server_close(); th.join(5); close_logs()


class Search(unittest.TestCase):
    def test_project_wide_find(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            try:
                e = engine(tmp); call = lambda m, p: json.loads(rpc.handle(e, json.dumps({"jsonrpc": "2.0", "id": 1, "method": m, "params": p})))
                call("project.create_folder", {"name": "s"})
                call("project.write_file", {"project": "s", "path": "styles/tokens.uss", "text": ":root {\n    --Brand: #112233;\n    --other: var(--brand);\n}\n"})
                r = call("project.search", {"project": "s", "q": "brand"})["result"]
                self.assertEqual([(h["path"], h["line"]) for h in r["hits"]], [("styles/tokens.uss", 2), ("styles/tokens.uss", 3)])      # case-insensitive by default
                self.assertEqual(len(call("project.search", {"project": "s", "q": "brand", "case": True})["result"]["hits"]), 1)
                self.assertEqual(call("project.search", {"project": "s", "q": r"--\w+:", "regex": True})["result"]["hits"][0]["col"], 5)
                self.assertEqual(call("project.search", {"project": "s", "q": ""})["result"]["hits"], [])
                self.assertIn("error", call("project.search", {"project": "s", "q": "(", "regex": True}))
            finally:
                close_logs()
