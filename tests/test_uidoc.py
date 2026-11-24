"""Gate B: the UiDocument adapter. Synthetic tests (always run) pin the identity rules; real-data acceptance tests (skipped when the game bundles are not on this machine) check Team Instructions at Large
on bundle set B, and against set C (set C verified against MANIFEST.json)."""
import json
import os
import tempfile
import unittest
from pathlib import Path

from skin_editor import layout_dump
from skin_editor.uidoc import Source, build_document, compare_documents, structural_keys
from skin_editor.uidoc.model import SCHEMA

G_TILE, G_PANEL, G_INC, G_LOOP = "11" * 16, "22" * 16, "33" * 16, "44" * 16


def n(i, type_="VisualElement", name="", classes=(), children=(), kind="element", template=None):
    d = {"id": i, "kind": kind, "type": type_, "name": name, "classes": list(classes), "inline": None, "attrs": {}, "has_bindings": False, "children": list(children)}
    if template:
        d["template"] = template
    return d


def rec(name, root, usings=None, cc=0):
    return {"v": 2, "bundle": "b.bundle", "path_id": "1", "name": name, "content_hash": 1, "usings": {a: {"guid": g} for a, g in (usings or {}).items()}, "content_container": cc, "root": root}


class FakeSource:
    """The five methods `Source` offers, over hand-written parse records."""

    def __init__(self, layouts):
        self.layouts = layouts                         # guid -> parse record
        self.order = list(layouts)

    def target(self, guid):
        return ("b.bundle", self.order.index(guid) + 100) if guid in self.layouts else None

    def parse(self, bundle, path_id):
        return self.layouts[self.order[int(path_id) - 100]]

    def guid_objects(self, guid):
        return []

    def guid_of(self, bundle, path_id):
        return self.order[int(path_id) - 100]

    def file_of(self, bundle, path_id):
        return "CAB-test"

    def name_rows(self, name):
        return 1


def dump():
    cell = {"composition": "C", "cell_index": 0, "element_id": "Tile", "x": 0, "y": 0, "w": 4, "h": 4, "min_w": 4, "min_h": 4, "max_w": 4, "max_h": 4, "flags": [], "h_align": "", "v_align": ""}
    return {"layouts": [{"id": 1, "name": "TileLayout", "guid": G_TILE, "bundle": "b"}, {"id": 2, "name": "PanelLayout", "guid": G_PANEL, "bundle": "b"}], "cells": [cell],
            "tiles": [{"panel_layout_id": 2, "set_name": "s", "breakpoint": 3, "variant_idx": 1, "composition": "C", "cell_index": 0, "cell_element_id": "Tile", "cfg_index": 0, "size": {"w": 4, "h": 4}, "tile_layout_id": 1}],
            "compositions": [{"name": "C", "layout_mode": "Standard", "preset_name": "", "preset_w": 4, "preset_h": 4, "instantiation_order": [0, 1], "conditions": [], "bundle": "cb", "path_id": 5}],
            "panels": [], "cell_configs": [], "elements": [], "includes": []}


def layouts(tile_children=None):
    inc = rec("Inc", n(300, "UXML", children=[n(301, name="slot"), n(302, "BindingRemapperComponent", name="remap")]), cc=301)
    kids = tile_children if tile_children is not None else [n(11, name="x"), n(12, name="x"), n(13, "TemplateContainer", kind="template", template="inc", children=[n(14, "SIText", name="slotted")])]
    tile = rec("TileLayout", n(10, "UXML", children=kids), usings={"inc": G_INC})
    panel = rec("PanelLayout", n(20, "UXML", children=[n(21, "Panel", name="p"), n(22, "TemplateContainer", kind="template", template="loop")]), usings={"loop": G_LOOP, "ghost": "99" * 16})
    loop = rec("Loop", n(40, "UXML", children=[n(41, "TemplateContainer", kind="template", template="self")]), usings={"self": G_LOOP})
    return {G_TILE: tile, G_PANEL: panel, G_INC: inc, G_LOOP: loop}


def doc(ls=None, order="natural"):
    return build_document(FakeSource(ls or layouts()), dump(), "C", (400, 400), padding=0, label={"game_build": "test"}, order=order)


class Identity(unittest.TestCase):
    def test_roots_and_non_visual_nodes_are_kept_and_flagged_and_every_node_has_the_empty_fields(self):
        d = doc()
        kinds = {x.kind for x in d.all_nodes()}
        self.assertIn("root", kinds)
        nv = [x for x in d.all_nodes() if "non_visual" in x.flags]
        self.assertEqual([x.type for x in nv], ["BindingRemapperComponent"])
        self.assertEqual({(x.semantic_role, x.edit_safety) for x in d.all_nodes()}, {("", "unknown")})
        self.assertEqual((d.semantic_map, d.user_operations), ({}, []))
        self.assertTrue(all(x.sources and "logical_id" in x.sources and "locator" in x.sources for x in d.all_nodes()))
        self.assertEqual(d.to_dict()["schema"], SCHEMA)

    def test_identical_siblings_get_an_occurrence_mark_in_the_id_and_none_in_the_structural_key(self):
        d = doc()
        xs = [x for x in d.all_nodes() if x.name == "x"]
        self.assertEqual(len(xs), 2)
        self.assertEqual(len({x.logical_id for x in xs}), 2)
        self.assertTrue(all("~" in x.logical_id for x in xs))
        self.assertEqual(len({x.structural_key for x in xs}), 1)
        self.assertEqual(structural_keys(d)[xs[0].structural_key], 2)

    def test_m_id_is_only_a_locator_the_logical_id_does_not_change_when_it_does(self):
        a = doc()
        ls = layouts()
        ls[G_TILE]["root"]["children"][0]["id"] = 9999                       # an element re-minted between builds
        b = doc(ls)
        self.assertEqual({x.logical_id for x in a.all_nodes()}, {x.logical_id for x in b.all_nodes()})
        loc = lambda d: {x.locator["m_id"] for x in d.all_nodes() if "synthetic" not in x.flags}
        self.assertNotEqual(loc(a), loc(b))

    def test_one_identity_per_template_instance_and_slot_content_keeps_its_authored_path(self):
        d = doc()
        inst = [x for x in d.all_nodes() if "template_instance" in x.flags and x.locator.get("included_layout_guid") == G_INC]
        self.assertEqual(len(inst), 1)
        inc_root = inst[0].children[0]
        self.assertEqual(inc_root.kind, "root")
        self.assertIn("UXML@33333333", inc_root.logical_id)
        slotted = next(x for x in d.all_nodes() if x.name == "slotted")
        self.assertIn("slot_content", slotted.flags)
        container = next(x for x in d.all_nodes() if x.name == "slot")
        self.assertIn(slotted, container.children)                           # placed in the content container
        self.assertNotIn("UXML@33333333", slotted.logical_id)                # but identified by where the outer layout wrote it
        self.assertIn("Template:inc", slotted.logical_id)

    def test_an_include_cycle_and_an_unresolved_guid_become_gaps_not_errors(self):
        d = doc()
        codes = {g.code for g in d.diagnostics}
        self.assertIn("INCLUDE_CYCLE", codes)
        self.assertIn("PANEL_ID_UNRESOLVED", codes)
        self.assertIn("OPTIONAL_SLOTS_NOT_IN_DUMP", codes)
        self.assertIn("INSTANTIATION_ORDER_UNEXPLAINED", codes)

    def test_built_twice_and_in_another_order_gives_the_same_ids_and_the_same_tree(self):
        def shape(d):
            return [(x.logical_id, [c.logical_id for c in x.children]) for x in d.all_nodes()]
        a, b, c = doc(), doc(), doc(order="reversed")
        self.assertEqual(shape(a), shape(b))
        self.assertEqual(shape(a), shape(c))
        self.assertEqual(set(a.dependencies.nodes), set(c.dependencies.nodes))
        edge_shape = lambda d: sorted((e.frm, e.to, e.type, e.assumed) for e in d.dependencies.edges)
        self.assertEqual(edge_shape(a), edge_shape(c))
        ls = layouts()
        shuffled = FakeSource(ls)
        shuffled.order = list(reversed(shuffled.order))                       # the source hands out path ids in another order
        e = build_document(shuffled, dump(), "C", (400, 400), padding=0, label={})
        self.assertEqual({x.logical_id for x in a.all_nodes()}, {x.logical_id for x in e.all_nodes()})

    def test_compare_documents_counts_matched_unmatched_and_ambiguous_apart(self):
        a = doc()
        ls = layouts([n(11, name="x"), n(12, name="x"), n(13, name="only-in-b")])
        b = doc(ls)
        r = compare_documents(a, b)
        self.assertEqual(r["ambiguous_keys"], 1)                              # the two identical `x` siblings
        self.assertGreater(r["unmatched_a"], 0)
        self.assertGreater(r["unmatched_b"], 0)
        self.assertEqual(r["matched"] + r["ambiguous_keys"] + r["unmatched_a"], len(structural_keys(a)))
        self.assertEqual(compare_documents(a, a)["unmatched_a"], 0)

    def test_structural_template_expansion_has_no_renderer_depth_limit(self):
        chain = {}
        guids = [("%032x" % (0x1000 + i)) for i in range(70)]
        for i, guid in enumerate(guids):
            child = n(5000 + i, "TemplateContainer", name="step-%d" % i, kind="template", template="next") if i + 1 < len(guids) else n(9000, "SIText", name="leaf")
            chain[guid] = rec("Layout-%d" % i, n(4000 + i, "UXML", children=[child]), usings={"next": guids[i + 1]} if i + 1 < len(guids) else {})
        source_layouts = layouts()
        source_layouts[G_TILE] = rec("TileLayout", n(10, "UXML", children=[n(5000, "TemplateContainer", name="step-0", kind="template", template="first")]), usings={"first": guids[0]})
        source_layouts.update(chain)
        d = build_document(FakeSource(source_layouts), dump(), "C", (400, 400), padding=0)
        instances = [x for x in d.all_nodes() if "template_instance" in x.flags and x.locator.get("included_layout_guid") in guids]
        self.assertEqual(len(instances), 70)
        self.assertEqual(len({x.logical_id for x in instances}), 70)
        self.assertTrue(any(x.name == "leaf" for x in d.all_nodes()))


class TieRule(unittest.TestCase):
    """The tie rule for ambiguous structural keys: the occurrence index `~k` among IDENTICAL siblings (same type and name), in source order."""

    def ids(self, kids):
        return {x.locator["m_id"]: x.logical_id for x in doc(layouts(kids)).all_nodes() if "synthetic" not in x.flags and x.locator["m_id"] in {n_["id"] for n_ in kids}}

    def test_moving_non_identical_siblings_changes_no_id(self):
        a = [n(11, name="x"), n(12, name="y"), n(13, name="x"), n(14, name="z")]
        b = [n(14, name="z"), n(11, name="x"), n(13, name="x"), n(12, name="y")]      # y and z moved, the two x keep their relative order
        self.assertEqual(self.ids(a), self.ids(b))

    def test_swapping_identical_siblings_with_different_subtrees_swaps_the_ids(self):
        a = [n(11, name="x", children=[n(21, "SIText", name="first")]), n(12, name="x", children=[n(22, "SIText", name="second")])]
        b = [a[1], a[0]]
        ia, ib = self.ids(a), self.ids(b)
        self.assertEqual({ia[11], ia[12]}, {ib[11], ib[12]})                          # the set of ids is the same
        self.assertEqual((ia[11], ia[12]), (ib[12], ib[11]))                          # but each id now belongs to the other node: the rule follows order, it does not look at content

    def test_identical_siblings_with_identical_subtrees_are_indistinguishable_and_stay_stable(self):
        a = [n(11, name="x"), n(12, name="x")]
        self.assertEqual(sorted(self.ids(a).values()), sorted(self.ids(list(reversed(a))).values()))


class ContentAddressedCaches(unittest.TestCase):
    def test_layout_guid_and_asset_indexes_change_for_same_size_same_mtime_content(self):
        from skin_editor.render.layouts import LayoutStore
        from skin_editor.render.guids import GuidIndex
        from skin_editor.render.assets import AssetResolver
        with tempfile.TemporaryDirectory() as tmp:
            root, cache = Path(tmp) / "aa", Path(tmp) / "cache"
            root.mkdir()
            cache.mkdir()
            bundle = root / "ui-visualtreeassets_test.bundle"
            bundle.write_bytes(b"AAAA")
            original = bundle.stat()
            layouts = LayoutStore(root, cache)
            first_layout = layouts._disk(bundle.name, "7")
            first_guid = GuidIndex(root, cache)._key()
            first_assets = AssetResolver(root, cache)._index_file()
            bundle.write_bytes(b"BBBB")
            os.utime(bundle, ns=(original.st_atime_ns, original.st_mtime_ns))
            self.assertEqual(bundle.stat().st_size, original.st_size)
            self.assertEqual(bundle.stat().st_mtime_ns, original.st_mtime_ns)
            self.assertNotEqual(first_layout, LayoutStore(root, cache)._disk(bundle.name, "7"))
            self.assertNotEqual(first_guid, GuidIndex(root, cache)._key())
            self.assertNotEqual(first_assets, AssetResolver(root, cache)._index_file())


ARCHIVE = Path(os.environ.get("UIDOC_ARCHIVE", r"__absent_fixture_path__"))     # the archived bundle sets: the tests never read the live game folder


def archived(tag):
    hit = next(iter(sorted(ARCHIVE.glob("set-%s-*" % tag))), None)
    return (hit / "StandaloneWindows64") if hit else Path("missing")


B_AA = Path(os.environ.get("UIDOC_B_AA") or archived("B"))
C_AA = Path(os.environ.get("UIDOC_C_AA") or archived("C"))
C_DUMP = Path(os.environ.get("UIDOC_C_DUMP", r"__absent_fixture_path__"))
FIXTURE = Path(__file__).resolve().parent / "fixtures" / "render" / "screen-team-instructions-large" / "fixture.json"


def real_doc(aa, dump_, cache, order="natural", label=None):
    from skin_editor.render.service import Renderer
    s = json.loads(FIXTURE.read_text(encoding="utf-8"))["screen"]
    rd = Renderer(aa, str(cache), None)
    return build_document(Source(rd.layouts), dump_, s["composition"], s["area"], s.get("padding", 12), s.get("reserved_right", 0), renderer=rd, label=label or {}, order=order)


def b_dump():
    # the B build needs B's layout dump: the archived copy of the stored dump (the workspace's current.json now
    # holds the C dump since the Stage 5 re-import), with the workspace fallback for machines without the archive
    archived = Path(os.environ.get("UIDOC_B_DUMP", r"__absent_fixture_path__"))
    if archived.is_file():
        d, _raw = layout_dump.read_file(archived)
        return d
    from skin_editor import config
    return layout_dump.load(config.workspace(config.load()))


@unittest.skipUnless(B_AA.is_dir() and (B_AA / "ui-visualtreeassets_assets_gameworldvisualtreeassetpreload.bundle").is_file() and b_dump() is not None, "needs bundle set B and its layout dump")
class TeamInstructionsOnB(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.dump = b_dump()
        cls.a = real_doc(B_AA, cls.dump, Path(cls.tmp.name) / "c1")
        cls.b = real_doc(B_AA, cls.dump, Path(cls.tmp.name) / "c2", order="reversed")

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_reachability_both_ways_against_the_dump_collected_independently(self):
        d = self.dump
        lay = {l["id"]: l for l in d["layouts"]}
        comp = self.a.screen["composition"]
        tiles = [t for t in d["tiles"] if t["composition"] == comp]
        start = {t["panel_layout_id"] for t in tiles} | {t["tile_layout_id"] for t in tiles}
        closure, todo = set(), list(start)
        inc = {}
        for r in d["includes"]:
            inc.setdefault(r["from_layout_id"], []).append(r)
        while todo:
            x = todo.pop()
            if x in closure:
                continue
            closure.add(x)
            todo.extend(r["to_layout_id"] for r in inc.get(x, []))
        independent = {(lay[e["layout_id"]]["guid"], e["local_id"]) for e in d["elements"] if e["layout_id"] in closure}
        in_doc = {(x.locator["layout_guid"], x.locator["m_id"]) for x in self.a.all_nodes() if "synthetic" not in x.flags}
        self.assertEqual(in_doc - independent, set(), "nodes the document holds that the independent collection does not")
        self.assertEqual(independent - in_doc, set(), "objects the independent collection holds that the document does not reach")
        self.assertEqual(len(in_doc), 91)                                      # the audit's count
        tpl_dump = {(lay[r["from_layout_id"]]["guid"], r["element_local_id"], lay[r["to_layout_id"]]["guid"]) for r in d["includes"] if r["from_layout_id"] in closure}
        tpl_doc = {(x.locator["layout_guid"], x.locator["m_id"], x.locator["included_layout_guid"]) for x in self.a.all_nodes() if x.locator.get("included_layout_guid")}
        self.assertEqual(tpl_doc, tpl_dump)
        self.assertEqual(len({x.locator["element_id"] for x in self.a.all_nodes() if x.kind == "host"}), 3)
        self.assertEqual(sum(1 for x in self.a.all_nodes() if x.kind == "host"), len([c for c in d["cells"] if c["composition"] == comp]))

    def test_the_graph_answers_both_directions_and_every_edge_names_its_source(self):
        g = self.a.dependencies
        self.assertTrue(g.edges)
        self.assertTrue(all(e.read_from and "object" in e.read_from for e in g.edges))
        e = next(e for e in g.edges if e.type == "includes_layout")
        self.assertIn(e, g.uses(e.frm))
        self.assertIn(e, g.used_by(e.to))
        for e in g.edges:
            self.assertIn(e.frm, g.nodes, e.type)
            self.assertIn(e.to, g.nodes, e.type)
        types = {x["kind"] for x in g.nodes.values()}
        self.assertTrue({"layout", "ui_node", "stylesheet", "rule", "token", "font", "image", "bundle", "composition", "cell"} <= types, types)

    def test_physical_identity_composition_fields_and_independent_inventory_are_complete_for_target(self):
        from skin_editor.uidoc.inventory import collect
        from skin_editor.render.service import Renderer
        rd = Renderer(B_AA, str(Path(self.tmp.name) / "c4"), None)
        source = Source(rd.layouts)
        source.build_identity = self.a.identity_scheme["build_identity"]
        independent = collect(source, self.dump, self.a.screen["composition"], rd)
        self.assertEqual(independent, self.a.inventory)
        graph_kind = {"layouts": "layout", "tiles": "tile", "templates": "template", "stylesheets": ("stylesheet", "inline_sheet"), "rules": "rule", "tokens": "token",
                      "hard_coded_colours": "hard_coded_colour", "fonts": "font", "images": "image", "compositions": "composition", "bundles": "bundle",
                      "ui_elements": "physical_ui_element", "placement_bindings": "placement_binding", "serialized_references": "serialized_asset_reference"}
        for category, kind in graph_kind.items():
            expected = set(independent[category])
            kinds = kind if isinstance(kind, tuple) else (kind,)
            actual = {nid for nid, info in self.a.dependencies.nodes.items() if info.get("kind") in kinds}
            self.assertEqual(actual, expected, category)
        self.assertTrue(all(n.locator.get("physical", {}).get("bundle_sha256") for n in self.a.all_nodes() if n.kind in ("element", "template", "root")))
        self.assertTrue(all(n.locator["physical"].get("build_identity") != "unknown" for n in self.a.all_nodes() if n.kind in ("element", "template", "root")))
        serialized = self.a.composition["serialized"]
        self.assertIn("m_optionalSlices", serialized)
        self.assertIn("m_placementBindings", serialized)
        self.assertEqual(len(serialized["m_placementBindings"]), 5)
        self.assertTrue(self.a.composition["serialized_pointer_refs"])
        self.assertTrue(all(ref["resolved"] for ref in self.a.composition["serialized_pointer_refs"]))
        self.assertEqual((self.a.semantic_map, self.a.user_operations), ({}, []))
        self.assertTrue(all(n.edit_safety == "unknown" and not n.semantic_role for n in self.a.all_nodes()))
        self.assertFalse(any(g.code in ("INVENTORY_ITEM_UNREACHABLE", "GRAPH_ITEM_OUTSIDE_INVENTORY") for g in self.a.diagnostics))

    def test_every_drawn_node_holds_the_existing_cascade_result(self):
        drawn = [x for x in self.a.all_nodes() if x.computed_style is not None]
        self.assertEqual(len(drawn), 78)                                       # 91 elements - 8 roots - 5 non-visual; = the 59 + 19 nodes the existing render draws for the three layouts (audit section 6)
        self.assertTrue(all("computed" in x.computed_style and "matched" in x.computed_style for x in drawn))
        self.assertTrue(all(x.computed_style is None for x in self.a.all_nodes() if x.kind in ("root", "host", "screen") or "non_visual" in x.flags))

    def test_built_twice_and_in_a_different_order_gives_the_same_ids(self):
        shape = lambda d: [(x.logical_id, [c.logical_id for c in x.children]) for x in d.all_nodes()]
        self.assertEqual(shape(self.a), shape(self.b))
        self.assertEqual(sorted(self.a.rule_ids.values()), sorted(self.b.rule_ids.values()))

    def test_rules_are_named_by_sheet_selector_and_occurrence_not_by_index(self):
        self.assertTrue(self.a.rule_ids)
        for rid in self.a.rule_ids.values():
            self.assertRegex(rid, r"^rule:[^/]+/[^|]+\|.*\|#\d+$")

    def test_reachability_of_sheets_rules_tokens_fonts_images_colours_compositions_and_bundles(self):
        """Each kind of object against a collection made straight from the render results and the dump, aggregated apart from the model (the cascade itself is shared)."""
        from skin_editor.render.service import Renderer
        from skin_editor.render.html import flatten
        from skin_editor.render.sheets import ROOT_SHEETS
        rd = Renderer(B_AA, str(Path(self.tmp.name) / "c3"), None)
        d, doc = self.dump, self.a
        comp = doc.screen["composition"]
        tiles = [t for t in d["tiles"] if t["composition"] == comp]
        lay = {l["id"]: l for l in d["layouts"]}
        names = sorted({lay[t["panel_layout_id"]]["name"] for t in tiles} | {lay[t["tile_layout_id"]]["name"] for t in tiles})
        cat = {r["name"]: r for r in rd.layouts.catalog()}
        rules, tokens, assets, lits, includes, layout_bundles, asset_bundles = set(), set(), set(), set(), 0, set(), set()
        for nm in names:
            r = rd.layout(cat[nm]["bundle"], cat[nm]["path_id"], 64)
            layout_bundles.add(cat[nm]["bundle"])
            includes += len(r["includes"])
            for n in flatten(r["tree"]):
                for m in n.get("matched") or []:
                    rules.add((m["sheet"], m["rule"]))
                for p, cd in (n.get("computed") or {}).items():
                    tokens.update(t for t in (cd.get("tokens") or []) if isinstance(t, str))
                    v = str(cd.get("value"))
                    if v.startswith("#") and not cd.get("tokens"):
                        s = cd.get("source") or {}
                        s = s.get("from") or {} if s.get("inherited") else s
                        lits.add((("inline", n["layout"], n["id"]) if s.get("inline") else (s.get("sheet"), s.get("rule"))) + (p, v))
                for a in (n.get("assets") or {}).values():
                    if isinstance(a, dict) and "bundle" in a:
                        assets.add((a["bundle"], a["path_id"]))
                        asset_bundles.add(a["bundle"])
        layout_bundles |= {t[0] for t in rd.layouts._target.values() if t}                              # the bundles of the included layouts, as the store resolved them during the renders
        g = doc.dependencies
        kinds = lambda k: [nid for nid, v in g.nodes.items() if v["kind"] == k]
        self.assertEqual(set(doc.rule_ids), rules)                                                      # rules matched
        self.assertEqual({g.nodes[n]["name"] for n in kinds("token")}, tokens)                          # tokens named in var chains
        self.assertEqual({(g.nodes[n]["bundle"], g.nodes[n]["path_id"]) for n in kinds("font") + kinds("image")}, assets)   # fonts and images
        self.assertEqual(len(kinds("hard_coded_colour")), len(lits))                                    # hard-coded colours
        self.assertEqual(len(kinds("stylesheet")), len(ROOT_SHEETS))                                    # applied sheets
        self.assertEqual(sum(1 for x in doc.all_nodes() if x.locator.get("included_layout_guid")), includes)   # template instances
        self.assertEqual(len(doc.composition["cells"]), len([c for c in d["cells"] if c["composition"] == comp]))   # cells
        self.assertEqual(doc.composition["tiles_in_dump"], len(tiles))                                  # tiles
        comp_refs = {r.get("bundle") for r in doc.composition.get("serialized_pointer_refs", []) if r.get("resolved") and r.get("bundle")}
        want_bundles = layout_bundles | asset_bundles | {b for b, _n, _w in ROOT_SHEETS} | {doc.composition["bundle"]} | comp_refs
        self.assertEqual({g.nodes[n]["file"] for n in kinds("bundle")} - want_bundles, set())           # no bundle in the graph that the collection does not know
        self.assertEqual(want_bundles - {g.nodes[n]["file"] for n in kinds("bundle")}, set())
        print("\nREACHABILITY:", {"rules": len(rules), "tokens": len(tokens), "fonts_and_images": len(assets), "hard_coded_colours": len(lits), "sheets": len(ROOT_SHEETS), "template_instances": includes,
                                  "cells": len(doc.composition["cells"]), "tiles": len(tiles), "bundles": len(want_bundles)})

    def test_the_json_is_plain_data(self):
        text = json.dumps(self.a.to_dict("summary"), default=str)
        self.assertLess(len(text), 5_000_000)
        self.assertEqual(json.loads(text)["schema"], SCHEMA)


@unittest.skipUnless(B_AA.is_dir() and C_AA.is_dir() and C_DUMP.is_file() and b_dump() is not None, "needs bundle sets B and C and the dump made for C")
class CrossBuild(unittest.TestCase):
    def test_structural_keys_between_b_and_c_are_accounted_for_apart(self):
        with tempfile.TemporaryDirectory() as tmp:
            a = real_doc(B_AA, b_dump(), Path(tmp) / "b")
            dc, _raw = layout_dump.read_file(C_DUMP)
            c = real_doc(C_AA, dc, Path(tmp) / "c", label={"status": "set C verified against MANIFEST.json"})
            r = compare_documents(a, c)
            self.assertEqual(r["matched"] + r["ambiguous_keys"] + r["unmatched_a"], len(structural_keys(a)))
            self.assertEqual(r["matched"] + r["ambiguous_keys"] + r["unmatched_b"], len(structural_keys(c)))
            print("\nCROSS-BUILD B->C (set C verified against MANIFEST.json):", {k: v for k, v in r.items() if not k.endswith(("_keys", "_list"))})


if __name__ == "__main__":
    unittest.main()
