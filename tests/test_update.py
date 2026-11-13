"""Phase 5: version profiles, update status, the diff and the per-item states, on synthetic sheets (the real two-build run is in docs)."""
import json, tempfile, unittest
from pathlib import Path

from skin_editor import config, index_styles, profile, project


def sheet(name, *rules, bundle="b"):
    """rules: (selectors, {prop: value}, is_token_rule)"""
    return {"bundle": bundle, "name": name, "failures": [], "rules": [
        {"i": i, "s": list(s), "t": t, "p": [[k, v, []] for k, v in p.items()]} for i, (s, p, t) in enumerate(rules)]}


def idx(*sheets):
    return index_styles.StyleIndex(list(sheets))


OLD = idx(sheet("S", ([":root"], {"--base": "#112233", "--gone": "#445566", "--same": "1px", "--tile-bg": "#010203"}, True),
                (["SIGradient.pitch > .inner"], {"color": "#FFFFFF", "padding": "4px"}, False),
                ([".vanishing"], {"color": "red"}, False),
                ([".mover"], {"color": "blue"}, False)),
          sheet("T", ([".other"], {"color": "green"}, False)))
NEW = idx(sheet("S", ([":root"], {"--base": "#AABBCC", "--same": "1px", "--tile-background": "#010203"}, True),
                (["SIGradient.pitch > .inner"], {"color": "#FFFFFF", "padding": "8px"}, False),
                ([".added"], {"color": "red"}, False)),
          sheet("T", ([".other"], {"color": "green"}, False), ([".mover"], {"color": "blue"}, False)))


def prof(pid, build, cat, **kw):
    return dict({"id": pid, "game_build": build, "catalog_hash": cat, "icon_classes": None, "layouts": None}, **kw)


class Diff(unittest.TestCase):
    def test_tokens_rules_sheets(self):
        d = profile.diff(prof("old", "1", "aa"), prof("new", "2", "bb"), OLD, NEW)
        t = d["tokens"]
        self.assertEqual((t["removed"], t["added"]), (["--gone", "--tile-bg"], ["--tile-background"]))
        self.assertEqual([c["token"] for c in t["changed"]], ["--base"]); self.assertEqual(t["changed"][0]["new"], "#AABBCC")
        self.assertEqual(t["renamed"], [{"old": "--tile-bg", "new": "--tile-background", "same_value": True}])
        r = d["rules"]
        self.assertEqual([x["selector"] for x in r["vanished"]], [".vanishing"])
        kinds = {(x["selector"], x["kind"]) for x in r["moved_or_changed"]}
        self.assertEqual(kinds, {(".mover", "moved"), ("SIGradient.pitch > .inner", "changed")})
        self.assertEqual(r["added_count"], 1)
        self.assertEqual(d["icons"]["available"], False); self.assertEqual(d["layouts"]["available"], False)

    def test_icons_and_layouts_when_both_profiles_have_them(self):
        a = prof("old", "1", "aa", icon_classes=["icon:star", "icon:gone"], layouts={"x": "1", "y": "1"})
        b = prof("new", "2", "bb", icon_classes=["icon:stars", "icon:new"], layouts={"x": "1", "y": "2", "z": "1"})
        d = profile.diff(a, b, OLD, NEW)
        self.assertEqual(d["icons"]["renamed"], [{"old": "icon:star", "new": "icon:stars"}]); self.assertEqual(d["icons"]["removed"], ["icon:gone", "icon:star"])
        self.assertEqual((d["layouts"]["changed"], d["layouts"]["added"]), (["y"], ["z"]))


class ItemStates(unittest.TestCase):
    def test_every_state(self):
        p = project.new("x")
        p["token_overrides"] = [{"token": t, "value": "#000000"} for t in ("--base", "--same", "--tile-bg", "--gone")]
        p["scoped_rules"] = [
            {"sheet": "S", "selector": "SIGradient.pitch > .inner", "props": {"padding": "2px"}, "op": "replace"},      # the game's padding changed
            {"sheet": "S", "selector": "SIGradient.pitch > .inner", "props": {"color": "#000000"}, "op": "replace"},    # colour unchanged
            {"sheet": "S", "selector": ".mover", "props": {}, "op": "remove", "remove": []},                              # moved to sheet T
            {"sheet": "S", "selector": ".vanishing", "props": {"color": "#000000"}, "op": "replace"},
            {"sheet": "Gone", "selector": ".a", "props": {"color": "#000000"}},
            {"sheet": "S", "selector": ".mine", "props": {"color": "#000000"}}]
        allrows = profile.project_states(p, OLD, NEW)
        rows = {(r["kind"], r["item"]): r for r in allrows}
        st = lambda k, i: rows[(k, i)]["state"]
        self.assertEqual(st("token", "--base"), "vanilla value changed"); self.assertEqual(st("token", "--same"), "ok")
        self.assertEqual(st("token", "--tile-bg"), "target moved"); self.assertEqual(rows[("token", "--tile-bg")]["fix"]["to"], "--tile-background")
        self.assertEqual(st("token", "--gone"), "target gone")
        by = {r["item"].split(" [")[0]: r["state"] for r in allrows if r["kind"] == "rule"}
        self.assertEqual(by["remove: .mover"], "target moved"); self.assertEqual(by["replace: .vanishing"], "target gone")
        self.assertEqual(by[".a"], "target gone"); self.assertEqual(by[".mine"], "ok")
        both = [r["state"] for r in allrows if r["item"].startswith("replace: SIGradient")]
        self.assertEqual(sorted(both), ["ok", "vanilla value changed"])      # padding changed, color did not

    def test_autofix_applies_only_the_moved_items(self):
        p = project.new("x")
        p["token_overrides"] = [{"token": "--tile-bg", "value": "#000000"}, {"token": "--gone", "value": "#000000"}]
        p["scoped_rules"] = [{"sheet": "S", "selector": ".mover", "props": {}, "op": "remove", "remove": []}]
        fixed, done = profile.autofix(p, profile.project_states(p, OLD, NEW))
        self.assertEqual([e["token"] for e in fixed["token_overrides"]], ["--tile-background", "--gone"])
        self.assertEqual(fixed["scoped_rules"][0]["sheet"], "T"); self.assertEqual(len(done), 2)
        project.validate(project.migrate(fixed))
        self.assertEqual(p["scoped_rules"][0]["sheet"], "S")                 # the input is not modified


class Listing(unittest.TestCase):
    def test_only_real_profiles_are_listed(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            ws = config.Workspace(Path(tmp) / "ws"); d = profile.profiles_dir(ws)
            (d / "ok.json").write_text(json.dumps({"id": "ok", "game_build": "1", "catalog_hash": "aa", "styles_file": "ok.styles.json", "tokens": 1}))
            (d / "ok.styles.json").write_text("{}")
            (d / "diff-a__b.json").write_text(json.dumps({"old": "a", "new": "b", "tokens": {"added": []}}))      # a saved diff is not a profile
            (d / "orphan.json").write_text(json.dumps({"id": "orphan", "styles_file": "gone.json"}))             # its index is missing
            (d / "broken.json").write_text("{not json")
            self.assertEqual([p["id"] for p in profile.list_profiles(ws)], ["ok"])


class Status(unittest.TestCase):
    def ws_with(self, tmp, cat="aaaa" * 8, with_profile=True):
        ws = config.Workspace(Path(tmp) / "ws")
        (ws.vanilla / "manifest.json").write_text(json.dumps({"files": {}, "reference": {"catalog_hash": cat, "bundles": {}, "platform_folder": "P"}}))
        if with_profile:
            (profile.profiles_dir(ws) / "p1.json").write_text(json.dumps({"id": "p1", "game_build": "1", "catalog_hash": cat, "styles_file": "p1.styles.json"}))
            (profile.profiles_dir(ws) / "p1.styles.json").write_text("{}")
        return ws

    def test_states(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            aa = Path(tmp) / "aa"; aa.mkdir()
            ws = config.Workspace(Path(tmp) / "empty")
            self.assertEqual(profile.status(ws, aa)["state"], "no_snapshot")
            ws = self.ws_with(tmp, with_profile=False)
            self.assertEqual(profile.status(ws, aa)["state"], "no_profile")
            ws = self.ws_with(tmp)
            (aa / "catalog.hash").write_text("bbbb" * 8)
            s = profile.status(ws, aa)
            self.assertEqual((s["state"], s["block_bundle_install"], s["next"]), ("catalog_changed", True, ["restore_check", "new_snapshot", "scan", "diff"]))
            (aa / "catalog.hash").write_text("aaaa" * 8)
            self.assertEqual(profile.status(ws, aa)["state"], "same")
            self.assertEqual(profile.active_profile(ws)["id"], "p1")
