import json
import sqlite3
import unittest

from skin_editor import table_usage


def spell(guid):
    """The argument bytes of a visual-scripting asset reference: some header bytes, a type name, the GUID as text, a trailer."""
    return [1, 80, 0, 0, 0, 42] + list(b"SI.VisualScripting.AssetReferenceVisualArg " + guid.encode()) + [1, 0, 1]


G1, G2 = "0c30f4c126ac4c3478dabb74c43ad0cf", "96f7a751f33bb874c95c0c06587427eb"


class Decode(unittest.TestCase):
    def test_reads_the_guid_out_of_the_bytes_anywhere_in_the_tree(self):
        attrs = {"Binding": {"x": 1}, "InitFunction": {"m_inputs": {"m_variable": {"m_argumentBytes": spell(G1)}}}, "other": [{"m_argumentBytes": spell(G2)}]}
        self.assertEqual(sorted(table_usage.guids_in_arguments(attrs)), sorted([G1, G2]))

    def test_no_arguments_no_guids_and_junk_bytes_are_ignored(self):
        self.assertEqual(table_usage.guids_in_arguments({"a": 1}), [])
        self.assertEqual(table_usage.guids_in_arguments({"m_argumentBytes": [1, 2, "x", 999, None]}), [])


class Build(unittest.TestCase):
    def db(self):
        d = sqlite3.connect(":memory:")
        d.executescript("""
        create table data_guids(guid, bundle, path_id, name);
        create table assets(id, bundle_id, cab, path_id, class, name, guid, is_root);
        create table elements(id, asset_id, local_id, parent_local_id, ord, type, name, classes, inline_rule, attrs_json, scope_json);
        create table tile_descriptions(path_id, name, desc_id, tags, default_config, availability_path, conditional_translations_json);
        create table tile_description_configs(desc_path_id, cfg_index, size_w, size_h, guid, to_asset, type);
        create table compositions(path_id, name, bundle, version, breakpoint, layout_mode, preset_name, preset_w, preset_h, content_alignment, reflow_mode, is_custom);
        create table cell_configs(composition_path_id, cell_index, cfg_index, description_path_id, description_name, size_w, size_h, guid, to_asset, type);
        """)
        d.execute("insert into data_guids values(?,?,?,?)", (G1, "ui-tableviews_assets_all.bundle", 1, "SquadKeyPlayersTableSmall"))
        d.execute("insert into data_guids values(?,?,?,?)", ("f" * 32, "ui-other.bundle", 2, "NotATableView"))
        d.execute("insert into assets(id,name) values(10,'FirstTeamTile_4x4')")
        d.execute("insert into elements(id,asset_id,type,name,attrs_json) values(1,10,'SI.Bindable.StreamedTable','',?)",
                  (json.dumps({"InitFunction": {"m_inputs": {"m_variable": {"m_argumentBytes": spell(G1)}}}}),))
        d.execute("insert into tile_descriptions(path_id,name) values(7,'SquadFirstTeamTileDescription')")
        d.execute("insert into tile_description_configs(desc_path_id,cfg_index,size_w,size_h,to_asset) values(7,3,4,4,10)")
        d.execute("insert into compositions(path_id,name) values(100,'SquadCompositionFMC-Small')")
        d.execute("insert into cell_configs(composition_path_id,cell_index,description_name) values(100,0,'SquadFirstTeamTileDescription')")
        return d

    def test_layout_tile_and_screens_are_linked(self):
        u = table_usage.build(self.db())
        self.assertEqual(list(u), ["SquadKeyPlayersTableSmall"])
        r = u["SquadKeyPlayersTableSmall"][0]
        self.assertEqual(r["layout"], "FirstTeamTile_4x4")
        self.assertEqual(r["tiles"][0], {"description": "SquadFirstTeamTileDescription", "size": [4, 4], "screens": ["SquadCompositionFMC-Small"]})
        self.assertIn("FirstTeamTile_4x4 [SquadFirstTeamTileDescription 4x4 in 1 composition(s)]", table_usage.summary(u, "SquadKeyPlayersTableSmall"))

    def test_a_view_no_layout_names_says_so(self):
        self.assertIn("not referenced", table_usage.summary({}, "Whatever"))


if __name__ == "__main__":
    unittest.main()
