"""Phase 9 I1: readers for the inspector's capture files (modes 1 and 2) on synthetic captures, and the layout content hash they are matched with."""
import json
import tempfile
import unittest
from pathlib import Path

from skin_editor.render import captures

AA = Path(r"C:\Program Files (x86)\Steam\steamapps\common\Football Manager 27\fm_Data\StreamingAssets\aa\StandaloneWindows64")

HEADER = {"schema": "fm-capture/1", "mode": "styles", "styles": True, "sources": True, "game": "27.0.1.2503222", "plugin": "0.3.0-capture", "source_property_available": True}
ROWS = [
    {"path": "P0", "depth": 0, "type": "PanelRootElement", "name": "Root", "classes": [], "world": [0, 0, 2500, 1406.2], "resolved": {"width": 2500, "color": "#EBEBEB", "fontSize": 14}},
    {"path": "P0/0", "depth": 1, "type": "TemplateContainer", "name": "tile-wide-4x2", "classes": ["tile-content"], "world": [2160.2, 1246.1, 311.5, 147.5],
     "resolved": {"width": 311.5, "fontSize": 14}, "source": {"name": "tile-figma-base-template", "instance": 5, "hash": 111}},
    {"path": "P0/0/0", "depth": 2, "type": "SIText", "name": "title-text", "classes": ["sitext", "heading-md"], "world": [2172, 1248, 40, 24.4], "resolved": {"fontSize": 16, "color": "#EBEBEB"}},
    {"path": "P0/1", "depth": 1, "type": "TemplateContainer", "name": "other", "classes": [], "world": [0, 0, 10, 10], "source": {"name": "Twin", "instance": 9, "hash": 222}},
]
FOOTER = {"end": True, "state": "done", "elements": 4, "skipped": 0, "unvisited": 0}


def write(rows, footer=FOOTER, header=HEADER):
    d = Path(tempfile.mkdtemp())
    f = d / "c.ndjson"
    f.write_text("\n".join(json.dumps(x) for x in [header, *rows] + ([footer] if footer else [])) + "\n", encoding="utf-8")
    return f


RULES_A = [{"s": [".a", ".b > .c"], "p": [["color", "red", []], ["width", "1px", []]]}, {"s": ["Label"], "p": [["opacity", "0", []]]}]
RULES_B = [{"s": [".a"], "p": [["color", "red", []]]}]
SHEETS = [{"name": "Alpha", "bundle": "x.bundle", "rules": RULES_A}, {"name": "AlphaTwin", "bundle": "y.bundle", "rules": RULES_A}, {"name": "Beta", "bundle": "x.bundle", "rules": RULES_B}]


class SheetContent(unittest.TestCase):
    """Plugin 0.3.1: sheet_content lines identify the empty-named sheets by content, never by guess."""

    def _write(self, lines):
        d = Path(tempfile.mkdtemp())
        f = d / "c.ndjson"
        f.write_text("\n".join(json.dumps(x) for x in [dict(HEADER, plugin="0.3.1-capture"), *lines, ROWS[0], FOOTER]) + "\n", encoding="utf-8")
        return f

    def test_signature_is_stable_and_order_and_property_count_sensitive(self):
        sig = captures.sheet_signature
        self.assertEqual(sig(RULES_A), sig([dict(r) for r in RULES_A]))
        self.assertNotEqual(sig(RULES_A), sig(list(reversed(RULES_A))))
        self.assertNotEqual(sig(RULES_B), sig([{"s": [".a"], "p": [["color", "red", []], ["x", "1", []]]}]))

    def test_identified_ambiguous_not_found_and_unreadable(self):
        line = lambda name, rules, **kw: dict({"sheet_content": True, "owner": "P1/0", "name": name, "instance": 1, "rules": len(rules), "signature": captures.sheet_signature(rules)}, **kw)
        c = captures.read_capture(self._write([line("", RULES_B), line("", RULES_A), line("", [{"s": [".zz"], "p": []}]),
                                               {"sheet_content": True, "owner": "P1/0", "name": "", "instance": 4, "error": "NullReferenceException: x"}]))
        self.assertEqual(len(c.elements), 1)                       # the sheet lines are not elements
        r = c.match_sheets(SHEETS)
        self.assertEqual([x["status"] for x in r], ["identified", "ambiguous", "not-found", "unreadable"])
        self.assertEqual(r[0]["candidates"][0]["name"], "Beta")
        self.assertEqual({k["name"] for k in r[1]["candidates"]}, {"Alpha", "AlphaTwin"})      # two sheets with the same content are both reported

    def test_a_signature_match_with_another_rule_count_is_not_a_match(self):
        bad = {"sheet_content": True, "owner": "P1/0", "name": "", "instance": 2, "rules": 99, "signature": captures.sheet_signature(RULES_B)}
        self.assertEqual(captures.read_capture(self._write([bad])).match_sheets(SHEETS)[0]["status"], "not-found")


class Bindings(unittest.TestCase):
    """Plugin 0.4.0 mode 4 (reading only): delivered text and Binder state, summarised without inference."""

    def _cap(self, header_extra, rows):
        d = Path(tempfile.mkdtemp())
        f = d / "c.ndjson"
        f.write_text("\n".join(json.dumps(x) for x in [dict(HEADER, plugin="0.4.0-capture", **header_extra), *rows, FOOTER]) + "\n", encoding="utf-8")
        return captures.read_capture(f)

    def test_delivered_texts_are_the_visible_sitext_values_as_read(self):
        rows = [{"path": "P0/0", "type": "SIText", "name": "title", "visible": True, "text": "LOANS", "world": [0, 0, 40, 18]},
                {"path": "P0/1", "type": "SIText", "name": "gone", "visible": False, "text": "hidden", "world": [0, 0, 5, 5]},
                {"path": "P0/2", "type": "SIText", "name": "empty", "visible": True, "text": "", "world": [0, 0, 5, 5]},
                {"path": "P1/0", "type": "SIText", "name": "other", "visible": True, "text": "x", "world": [0, 0, 9, 9]}]
        c = self._cap({"bindings": True}, rows)
        self.assertEqual(set(c.delivered_texts()), {"P0/0", "P1/0"})
        self.assertEqual(c.delivered_texts("P0")["P0/0"], {"text": "LOANS", "width": 40, "name": "title"})
        self.assertEqual(set(c.delivered_texts("P1")), {"P1/0"})

    def test_summary_counts_binder_state_and_never_fills_in_a_path(self):
        rows = [{"path": "a", "type": "SIText", "text": "1", "binding": {"isBound": True, "isReady": True, "binder": "Binder"}},
                {"path": "b", "type": "SIText", "text": "", "binding": {"isBound": False, "isReady": False, "binder": "Binder"}},
                {"path": "c", "type": "SIText", "text": "3", "binding": {"binder": None}},
                {"path": "d", "type": "SIText", "text": "4", "binding": {"isBound": "unreadable: NullReferenceException", "isReady": True, "binder": "Binder"}},
                {"path": "e", "type": "SIText", "text": "5"}]
        s = self._cap({"bindings": True}, rows).bindings_summary()
        self.assertEqual((s["sitext"], s["with_binding_object"], s["no_binder"], s["is_bound"], s["is_ready"], s["unreadable"], s["with_text"]), (5, 4, 1, 1, 2, 1, 4))
        self.assertEqual(s["top_binder_strings"], [("Binder", 3)])

    def test_a_capture_without_the_flag_says_so(self):
        s = self._cap({}, [{"path": "a", "type": "SIText", "text": "x"}]).bindings_summary()
        self.assertFalse(s["available"])
        self.assertIn("0.4.0", s["note"])


class Transitions(unittest.TestCase):
    """Plugin 0.5.0 mode 3 (polling): a hover session summarised without inference."""

    def test_the_summary_counts_classes_and_pseudo_changes_and_keeps_events_out_of_the_elements(self):
        hdr = dict(HEADER, mode="transitions", plugin="0.5.0-capture", watched=3)
        rows = [{"frame": 5, "t": 1.0, "path": "P1/0/3", "type": "SIButton", "name": "b", "pseudo": [0, 2], "added": ["hover-class"], "removed": []},
                {"frame": 9, "t": 1.5, "path": "P1/0/3", "type": "SIButton", "name": "b", "pseudo": [2, 0], "added": [], "removed": ["hover-class"]},
                {"frame": 12, "t": 2.0, "path": "P1/0/9", "type": "VisualElement", "name": "", "appeared": True, "pseudo": [0, 0], "classes": "tooltip"},
                {"frame": 14, "t": 2.1, "path": "P1/0/4", "type": "SIButton", "name": "c", "pseudo": [2, 2], "added": ["pressed"], "removed": []}]
        d = Path(tempfile.mkdtemp())
        f = d / "c.ndjson"
        f.write_text("\n".join(json.dumps(x) for x in [hdr, *rows, FOOTER]) + "\n", encoding="utf-8")
        c = captures.read_capture(f)
        self.assertEqual(len(c.elements), 0)                                 # the lines are events, not elements
        s = c.transition_summary()
        self.assertEqual((s["events"], s["appeared"]), (3, 1))
        self.assertEqual(s["classes"]["hover-class"], {"added": 1, "removed": 1, "types": {"SIButton": 2}})
        self.assertEqual(s["classes"]["pressed"]["added"], 1)
        self.assertEqual(s["pseudo_changes"]["0->2"]["classes_added"], {"hover-class": 1})
        self.assertNotIn("2->2", s["pseudo_changes"])                        # a class change with the same mask is not a pseudo-state change

    def test_another_mode_says_so(self):
        d = Path(tempfile.mkdtemp())
        f = d / "c.ndjson"
        f.write_text("\n".join(json.dumps(x) for x in [HEADER, *ROWS[:1], FOOTER]) + "\n", encoding="utf-8")
        self.assertFalse(captures.read_capture(f).transition_summary()["available"])


class Readers(unittest.TestCase):
    def test_reads_header_elements_footer_and_summarises(self):
        c = captures.read_capture(write(ROWS))
        s = c.summary()
        self.assertEqual((s["elements"], s["complete"], s["state"], s["mode"]), (4, True, "done", "styles"))
        self.assertEqual(c.box("P0/0/0"), [2172, 1248, 40, 24.4])
        self.assertEqual(c.resolved("P0/0/0")["fontSize"], 16)

    def test_an_aborted_capture_is_reported_not_repaired(self):
        c = captures.read_capture(write(ROWS, footer=None))
        self.assertFalse(c.complete)
        self.assertIn("no footer", c.summary()["state"])
        self.assertEqual(len(c.elements), 4)                              # what was written is kept, nothing is invented

    def test_a_truncated_line_and_a_foreign_file_are_refused(self):
        f = write(ROWS)
        f.write_text(f.read_text(encoding="utf-8") + '{"path": "P9", "ty', encoding="utf-8")
        with self.assertRaises(ValueError):
            captures.read_capture(f)
        g = Path(tempfile.mkdtemp()) / "x.ndjson"
        g.write_text('{"schema": "something-else"}\n', encoding="utf-8")
        with self.assertRaises(ValueError):
            captures.read_capture(g)

    def test_template_sources_with_subtree_sizes(self):
        c = captures.read_capture(write(ROWS))
        t = c.template_sources()
        self.assertEqual([(x["path"], x["source"]["name"], x["subtree"]) for x in t], [("P0/0", "tile-figma-base-template", 1), ("P0/1", "Twin", 0)])

    def test_expectations_are_exactly_what_was_measured(self):
        c = captures.read_capture(write(ROWS))
        e = c.expectations(["P0/0/0", "P9/9"], props=("fontSize", "color", "missing"))
        self.assertEqual(list(e), ["P0/0/0"])                             # an unknown path is dropped, not made up
        self.assertEqual(e["P0/0/0"]["resolved"], {"fontSize": 16, "color": "#EBEBEB"})
        self.assertEqual(e["P0/0/0"]["label"], "SIText#title-text.sitext.heading-md")


class Matching(unittest.TestCase):
    LAYOUTS = [{"name": "tile-figma-base-template", "bundle": "g.bundle", "path_id": "1", "content_hash": 111},
               {"name": "Twin", "bundle": "a.bundle", "path_id": "2", "content_hash": 1},
               {"name": "Twin", "bundle": "b.bundle", "path_id": "3", "content_hash": 222}]       # the capture's Twin carries hash 222: the second one

    def test_hash_name_ambiguity_and_missing_are_all_reported(self):
        c = captures.read_capture(write(ROWS + [{"path": "P0/2", "type": "X", "name": "", "classes": [], "source": {"name": "Nope"}}]))
        r = {m["path"]: m for m in captures.match_layouts(c, [dict(x) for x in self.LAYOUTS])}
        self.assertEqual(r["P0/0"]["status"], "matched by name and content hash")
        self.assertEqual(r["P0/0"]["layout"]["path_id"], "1")
        self.assertEqual(r["P0/1"]["layout"]["path_id"], "3")             # two layouts named Twin: the content hash picks the right one
        self.assertEqual(r["P0/2"]["status"], "no layout of that name in the bundles")

    def test_ambiguous_name_without_a_matching_hash_is_not_guessed(self):
        c = captures.read_capture(write([ROWS[3]]))                       # Twin with hash 222
        twins = [{"name": "Twin", "bundle": "a.bundle", "path_id": "2", "content_hash": 1}, {"name": "Twin", "bundle": "b.bundle", "path_id": "3", "content_hash": 2}]
        r = captures.match_layouts(c, twins)                              # neither hash is 222
        self.assertEqual(r[0]["status"], "ambiguous")
        self.assertEqual(r[0]["candidates"], [("a.bundle", "2"), ("b.bundle", "3")])

    def test_a_missing_hash_is_supplied_lazily_only_for_candidates(self):
        calls = []
        rows = [{"name": "Twin", "bundle": "a.bundle", "path_id": "2"}, {"name": "Other", "bundle": "o.bundle", "path_id": "9"}]
        c = captures.read_capture(write([{"path": "P0", "type": "T", "name": "", "classes": [], "source": {"name": "Twin", "hash": 77}}]))
        r = captures.match_layouts(c, rows, hash_of=lambda row: (calls.append(row["path_id"]) or 77))
        self.assertEqual(calls, ["2"])                                    # not computed for "Other"
        self.assertEqual(r[0]["status"], "matched by name and content hash")


@unittest.skipUnless(AA.is_dir(), "needs the game install")
class RealHash(unittest.TestCase):
    def test_parsed_layouts_carry_the_content_hash_used_for_matching(self):
        from skin_editor import config
        from skin_editor.render.layouts import LayoutStore
        ws = config.workspace(config.load())
        rec = LayoutStore(AA, ws.cache).parse("ui-visualtreeassets_assets_gameworldvisualtreeassetpreload.bundle", "-3957983696827071101")
        self.assertEqual(rec["name"], "LoansTile_4x2")
        self.assertIsInstance(rec["content_hash"], int)


if __name__ == "__main__":
    unittest.main()
