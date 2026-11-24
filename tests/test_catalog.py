"""Stage 4E: the read-only catalog reader (catalog.py), the manifest.dat reader (fmmanifest.py), their inventory
integration and the build/manifest integrity sections.

Always-run tests use SYNTHETIC catalogs and manifests built byte by byte from the Stage 3B record layout, and the
committed synthetic bundle (data/selftest/roundtrip.unity3d) - no game file is read or written. The real-data tests
copy the archived set-C catalog, the live manifest.dat and archived bundles into temporary folders and skip when any
source is absent. A missing record is not a match, an ambiguous record is not a match, an unsupported parser is not a
match, and a successful parse is never a write: every parse is checked against the source file's hash."""
import json
import os
import shutil
import struct
import tempfile
import unittest
import zlib
from pathlib import Path
from unittest import mock

from skin_editor import bundles, catalog, config, fmmanifest, gameinstall, index_styles, inventory, registry
from skin_editor import project as project_mod
from skin_editor.api import rpc

from test_api import close_logs, engine
from test_inventory import FIXTURE, SETC, make_install, tree_hashes

# the live game folder is NEVER typed as a literal here (the guard test forbids it): it is built from pieces, and
# FM27SE_GAME can redirect the real-data tests to another copy of the game
GAME = Path(os.environ.get("FM27SE_GAME") or "\\".join([r"C:\Program Files (x86)", "Steam", "steamapps", "common", "Football Manager 27"]))
MANIFEST_DAT = GAME / "fm_Data" / "manifest.dat"
SETC_CATALOG = SETC.parent / "catalog.bin"

# Stage 3B/3C reference values (docs/rea/STAGE-3B-CATALOG-ANALYSIS.md, STAGE-3C-OFFLINE-CATALOG-PATCH.md)
TILES = "ui-tileslayouts_assets_all.bundle"
TILES_CRC = 0x3949995C
TILES_OFFSET = 411888
SETC_CATALOG_SHA = "7e83abcb289a0401504faf6a6f7dbe092c6663670155962a4576bcc1101ab12d"
GW = "ui-visualtreeassets_assets_gameworldvisualtreeassetpreload.bundle"
GW_CRC = 0x0F7B8FE4
FIXTURE_CRC = 0x43791720                     # tests/test_inventory.FIXTURE_CRC, computed independently of bundles.py


# ---------------------------------------------------------------- synthetic catalog construction
def _strlen(s):
    b = s.encode("utf-8")
    return struct.pack("<I", len(b)) + b


def mkcat(records, magic=0x0DE38942, version=2):
    """Build a small catalog from the Stage 3B layout: header, a string heap, then records placed at unaligned
    offsets AFTER the heap (each record's final offset is written back into r["at"]). `records`:
    [{file, crc, size, at (optional - bumped past the heap and misaligned on purpose)}]."""
    import hashlib
    head = struct.pack("<II", magic, version)
    parts, off = [head], 8

    def put(s):
        nonlocal off
        b = s.encode("utf-8")
        ptr = off + 4
        parts.append(struct.pack("<I", len(b)) + b)
        off += 4 + len(b)
        return ptr

    for r in records:
        r.setdefault("name32", hashlib.md5(r["file"].encode()).hexdigest())
    prepared = []
    for r in records:
        ptrs = dict(r, name32_ptr=put(r["name32"]), key_ptr=put(r.get("key", r["file"])),
                    iid_ptr=put(r.get("internal_id",
                                "{UnityEngine.AddressableAssets.Addressables.RuntimePath}\\StandaloneWindows64\\" + r["file"])))
        prepared.append(ptrs)
    for r in prepared:                                          # one loop: place, pad, write; the assigned offsets are
        r["at"] = max(r.get("at") or 0, off + 1)                # written back to the caller's dicts below the loop
        parts.append(b"\0" * (r["at"] - off))
        off = r["at"]
        rec_bytes = struct.pack("<IIIIIII", 0, r["name32_ptr"], r["crc"], r["size"], 0, 0, r["at"])   # +0x00..+0x1b
        rec_bytes += struct.pack("<II", r["key_ptr"], r["iid_ptr"])                                   # +0x1c, +0x20
        rec_bytes += struct.pack("<IIIIII", 0x40038ef1, 0xFFFFFFFF, 0, 0, 0, 0)                       # +0x24.. tail
        parts.append(rec_bytes)
        off += len(rec_bytes)
    for src, r in zip(records, prepared):
        src["at"] = r["at"]
    return b"".join(parts)


def rec(file, crc, size, at=None):
    return {"file": file, "crc": crc, "size": size, "at": at}


class TestCatalogParser(unittest.TestCase):
    """The structural parser on synthetic catalogs: known record, lookup, safe failure, isolation, no writes."""

    def mk(self, **kw):
        self.rs = [rec("a.bundle", 0x11223344, 100), rec("b.bundle", 0, 200)]
        return mkcat(self.rs, **kw), self.rs

    def test_known_record_offsets_fields_and_lookup(self):
        import hashlib
        data, rs = self.mk()
        h0 = hashlib.sha256(data).hexdigest()
        idx = catalog.parse_catalog_bytes(data)
        self.assertEqual((idx["status"], idx["header"]["version"], len(idx["records"])), ("ok", 2, 2))
        a, b = idx["records"]
        self.assertEqual((a["file"], a["offset"], a["crc_hex"], a["size"]), ("a.bundle", rs[0]["at"], "11223344", 100))
        self.assertTrue(a["offset"] % 4)                                   # any byte alignment, as in the real catalog
        self.assertEqual(a["bundle_name32"], rs[0]["name32"])
        self.assertEqual(b["crc_hex"], "00000000")                       # a stored zero is preserved as zero
        self.assertIn("+0x14 pointer", a["not_decoded"])                  # the unresolved fields are labelled, not invented
        self.assertEqual(hashlib.sha256(data).hexdigest(), h0)            # parsing never modified the bytes
        self.assertEqual(catalog.resolve(idx, "a.bundle")["status"], "found")
        self.assertEqual(catalog.resolve(idx, "nope.bundle")["status"], "missing")

    def test_the_record_anchor_is_structural_not_a_size_search(self):
        data, rs = self.mk()
        idx = catalog.parse_catalog_bytes(data)
        self.assertEqual(sorted(r["offset"] for r in idx["records"]), sorted(r["at"] for r in rs))

    def test_duplicate_filenames_are_ambiguous_never_one_picked(self):
        data = mkcat([rec("a.bundle", 1, 10), rec("a.bundle", 2, 10)])
        idx = catalog.parse_catalog_bytes(data)
        r = catalog.resolve(idx, "a.bundle")
        self.assertEqual((r["status"], len(r["records"])), ("ambiguous", 2))
        self.assertEqual(catalog.catalog_crc_status(r["status"], 1, 1), "catalog_record_ambiguous")   # never a match

    def test_unknown_header_or_version_is_unsupported_not_guessed(self):
        data, _rs = self.mk(magic=0x12345678)
        self.assertEqual(catalog.parse_catalog_bytes(data)["status"], "unsupported")
        data, _rs = self.mk(version=3)
        self.assertEqual(catalog.parse_catalog_bytes(data)["status"], "unsupported")
        self.assertIn("shorter than", catalog.parse_catalog_bytes(b"42\x89")["reason"])

    def test_bad_pointers_and_truncated_records_are_rejected_and_isolated(self):
        data, rs = self.mk()
        good = catalog.parse_catalog_bytes(data)
        self.assertEqual((good["status"], len(good["records"])), ("ok", 2))
        # break the b.bundle record's primary-key pointer (anchor still holds): rejected, a.bundle still decodes
        broken = bytearray(data)
        struct.pack_into("<I", broken, rs[1]["at"] + 0x1c, len(broken) - 2)
        idx = catalog.parse_catalog_bytes(bytes(broken))
        self.assertEqual((idx["status"], len(idx["records"]), idx["rejected"]), ("ok", 1, 1))
        self.assertEqual(idx["records"][0]["file"], "a.bundle")
        # break the a.bundle name32 string's length prefix: same isolation
        broken = bytearray(data)
        good_a = next(r for r in good["records"] if r["file"] == "a.bundle")
        struct.pack_into("<I", broken, good_a["raw"]["bundle_name_ptr"] - 4, 100000)
        idx = catalog.parse_catalog_bytes(bytes(broken))
        self.assertEqual((idx["status"], len(idx["records"]), idx["rejected"]), ("ok", 1, 1))
        self.assertEqual(idx["records"][0]["file"], "b.bundle")

    def test_crc_status_values_stay_separate(self):
        f = catalog.catalog_crc_status
        self.assertEqual(f("found", 10, 10), "catalog_crc_match")
        self.assertEqual(f("found", 10, 11), "catalog_crc_mismatch")
        self.assertEqual(f("found", 0, 10), "catalog_crc_stored_zero")       # 0 = no CRC stored (Stage 3B sets A/B)
        self.assertEqual(f("missing", None, 10), "catalog_record_missing")
        self.assertEqual(f("ambiguous", None, 10), "catalog_record_ambiguous")
        self.assertEqual(f("found", 10, None), "crc_not_calculated")

    def test_read_never_modifies_the_file(self):
        import hashlib
        tmp = Path(tempfile.mkdtemp(prefix="fm27se-cat-"))
        self.addCleanup(shutil.rmtree, tmp, ignore_errors=True)
        p = tmp / "catalog.bin"
        data, _rs = self.mk()
        p.write_bytes(data)
        h0 = hashlib.sha256(p.read_bytes()).hexdigest()
        idx = catalog.read(p)
        self.assertEqual((idx["status"], idx["sha256"][:8]), ("ok", h0[:8]))
        self.assertEqual(hashlib.sha256(p.read_bytes()).hexdigest(), h0)

    def test_unreadable_catalog_is_a_clean_failure(self):
        idx = catalog.read(Path(tempfile.mkdtemp(prefix="fm27se-cat-")) / "nope.bin")
        self.assertEqual(idx["status"], "failed")


@unittest.skipUnless(SETC_CATALOG.is_file(), "archived set-C catalog not present")
class TestSetCCatalog(unittest.TestCase):
    """The parser against the real set-C catalog: 534 records, the known reference values, no writes."""

    def test_records_and_reference_values(self):
        import hashlib
        h0 = hashlib.sha256(SETC_CATALOG.read_bytes()).hexdigest()
        idx = catalog.read(SETC_CATALOG)
        self.assertEqual((idx["status"], idx["sha256"]), ("ok", SETC_CATALOG_SHA))
        self.assertEqual(len(idx["records"]), 534)
        self.assertLess(idx["rejected"], 200)                            # anchor hits that fail the record checks are counted, never silent
        tiles = catalog.resolve(idx, TILES)
        self.assertEqual(tiles["status"], "found")
        r = tiles["records"][0]
        self.assertEqual((r["offset"], r["crc_hex"], r["size"]), (TILES_OFFSET, "3949995c", 933527))
        gw = catalog.resolve(idx, GW)["records"][0]
        self.assertEqual(gw["crc_hex"], "0f7b8fe4")
        self.assertEqual(catalog.catalog_crc_status("found", r["crc"], TILES_CRC), "catalog_crc_match")
        self.assertEqual(hashlib.sha256(SETC_CATALOG.read_bytes()).hexdigest(), h0)      # never modified

    def test_the_record_crc_equals_the_bundle_uncompressed_crc_for_sampled_bundles(self):
        idx = catalog.read(SETC_CATALOG)
        by = catalog.by_file(idx)
        checked = 0
        for r in idx["records"]:
            p = SETC / r["file"]
            if not p.is_file() or checked >= 8:
                continue
            self.assertEqual("%08x" % bundles.crc32_uncompressed(p), r["crc_hex"], r["file"])
            self.assertEqual(p.stat().st_size, r["size"], r["file"])
            checked += 1


class TestCrc(unittest.TestCase):
    """The CRC definitions stay separate: uncompressed content (the catalog's value) is never the compressed file's
    CRC and never a re-saved object's hash."""

    def test_the_compressed_file_crc_is_not_the_uncompressed_crc(self):
        p = SETC / GW
        if not p.is_file():
            self.skipTest("archived set-C bundles not present")
        self.assertEqual("%08x" % bundles.crc32_uncompressed(p), "0f7b8fe4")
        self.assertNotEqual(zlib.crc32(p.read_bytes()) & 0xFFFFFFFF, 0x0F7B8FE4)         # file CRC differs (8f29c412 in 3B)
        self.assertNotEqual("%08x" % (zlib.crc32(p.read_bytes()) & 0xFFFFFFFF), "0f7b8fe4")

    @unittest.skipUnless((SETC / TILES).is_file(), "archived set-C bundles not present")
    def test_all_four_stage_3_reference_values_reproduce(self):
        stage3b = Path(r"__absent_fixture_path__") / TILES
        stage3f = Path(r"__absent_fixture_path__") / TILES
        self.assertEqual("%08x" % bundles.crc32_uncompressed(SETC / TILES), "3949995c")       # original
        self.assertEqual("%08x" % bundles.crc32_uncompressed(SETC / GW), "0f7b8fe4")          # original
        if stage3b.is_file():
            self.assertEqual("%08x" % bundles.crc32_uncompressed(stage3b), "71f3eb63")        # Stage 3B output
        if stage3f.is_file():
            self.assertEqual("%08x" % bundles.crc32_uncompressed(stage3f), "bb1e5719")         # Stage 3F output
        self.assertEqual("%08x" % bundles.crc32_uncompressed(FIXTURE), "%08x" % FIXTURE_CRC)  # synthetic fixture


class TestFmManifest(unittest.TestCase):
    """The manifest.dat lookup: whole-file CRC-32, search-based and labelled as such, never a write."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="fm27se-man-"))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.f = self.tmp / "a.bundle"
        self.f.write_bytes(b"the whole physical file, exactly as on disk")
        self.wcrc = zlib.crc32(self.f.read_bytes()) & 0xFFFFFFFF

    def test_a_unique_whole_file_crc_is_a_match_and_says_how_it_was_found(self):
        m = self.tmp / "manifest.dat"
        m.write_bytes(b"header-ish" + struct.pack("<I", self.wcrc) + b"\0" * 21)         # a 25-byte entry, only the CRC established
        man = fmmanifest.read(m)
        self.assertEqual(man["status"], "ok")
        look = fmmanifest.lookup(man["data"], self.f.read_bytes())
        self.assertEqual((look["status"], look["crc32"], look["occurrences"]), ("manifest_match", "%08x" % self.wcrc, 1))
        self.assertIn("not a decoded record", look["note"])                              # the method is labelled, always

    def test_missing_and_ambiguous_entries_are_distinct_states(self):
        m = self.tmp / "manifest.dat"
        entry = struct.pack("<I", self.wcrc)
        m.write_bytes(entry + entry)                                                      # two occurrences
        man = fmmanifest.read(m)
        self.assertEqual(fmmanifest.lookup(man["data"], self.f.read_bytes())["status"], "manifest_entry_ambiguous")
        other = self.tmp / "b.bundle"
        other.write_bytes(b"different bytes entirely")
        self.assertEqual(fmmanifest.lookup(man["data"], other.read_bytes())["status"], "manifest_entry_missing")

    def test_the_uncompressed_bundle_crc_is_never_used_here(self):
        m = self.tmp / "manifest.dat"
        m.write_bytes(b"not the bundle at all")                                           # holds nothing of the bundle
        man = fmmanifest.read(m)
        self.assertEqual(fmmanifest.lookup(man["data"], self.f.read_bytes())["status"], "manifest_entry_missing")

    def test_missing_manifest_is_unsupported_and_a_failed_read_is_reported(self):
        self.assertEqual(fmmanifest.read(self.tmp / "gone.dat")["status"], "missing")
        self.assertEqual(fmmanifest.read(self.tmp)["status"], "failed")                    # unreadable: a clean failure

    def test_the_real_manifest_if_present_is_never_written(self):
        if not MANIFEST_DAT.is_file() or not (SETC / TILES).is_file():
            self.skipTest("manifest.dat or bundle archive not present")
        import hashlib
        h0 = hashlib.sha256(MANIFEST_DAT.read_bytes()).hexdigest()
        man = fmmanifest.read(MANIFEST_DAT)
        self.assertEqual((man["status"], man["size"], man["sha256"]),
                         ("ok", 31200, "bb4db720d237e81530fc424fe7c762b355227f9f59258c1682282f7dd474b3ab"))
        look = fmmanifest.lookup(man["data"], (SETC / TILES).read_bytes())
        self.assertEqual(look["status"], "manifest_match")                                # the stock bundle's whole-file CRC is present
        mod = Path(r"__absent_fixture_path__") / TILES
        if mod.is_file():
            self.assertEqual(fmmanifest.lookup(man["data"], mod.read_bytes())["status"], "manifest_entry_missing")
        self.assertEqual(hashlib.sha256(MANIFEST_DAT.read_bytes()).hexdigest(), h0)       # never modified


class TestInventoryIntegration(unittest.TestCase):
    """The annotation fills the 4B placeholders from a synthetic catalog and manifest, incrementally, without any
    bundle reparse, and the game tree never changes."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="fm27se-ann-"))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.game, self.plat = make_install(self.tmp)
        # the three bundles must have DISTINCT bytes, or their whole-file CRCs (and the manifest lookups built on
        # them) would be indistinguishable: b and c get one byte of the TextAsset's script text changed each
        self.b2 = self.variant(b"4E-test-variant-b")
        self.c2 = self.variant(b"4E-test-variant-c")
        (self.plat / "ui-styles_assets_default.bundle").write_bytes(self.b2)
        (self.plat / "ui-tileslayouts_assets_all.bundle").write_bytes(self.c2)
        # a catalog with: a MATCHING record for the first bundle, a stored-zero record for the second, nothing for the third;
        # a manifest.dat holding the first bundle's whole-file CRC once and the second's twice
        self.a = self.plat / "ui-styles_assets_common.bundle"
        self.b = self.plat / "ui-styles_assets_default.bundle"
        self.c = self.plat / "ui-tileslayouts_assets_all.bundle"
        self.crecs = [rec("ui-styles_assets_common.bundle", FIXTURE_CRC, self.a.stat().st_size),
                      rec("ui-styles_assets_default.bundle", 0, self.b.stat().st_size)]
        (self.plat.parent / "catalog.bin").write_bytes(mkcat(self.crecs))
        wa, wb = zlib.crc32(self.a.read_bytes()) & 0xFFFFFFFF, zlib.crc32(self.b.read_bytes()) & 0xFFFFFFFF
        (self.tmp / "game" / "Game_Data" / "manifest.dat").write_bytes(struct.pack("<I", wa) + struct.pack("<I", wb) * 2 + b"\0" * 21)
        # the profile is taken AFTER the synthetic catalog and manifest are in place, so its identity is current
        self.ws = config.Workspace(self.tmp / "ws")
        self.prof = gameinstall.describe_install(self.game, "test", "27.test")
        self.reg = registry.Registry.for_install(self.ws, self.prof["install_id"])
        inventory.scan(self.reg, self.prof["aa_roots"])

    @staticmethod
    def variant(text):
        """A second and third valid synthetic bundle: the committed fixture with its TextAsset's script text changed."""
        import UnityPy
        env = UnityPy.load(str(FIXTURE))
        obj = next(o for o in env.objects)
        t = obj.read_typetree()
        t["m_Script"] = text.decode("latin1")
        obj.save_typetree(t)
        return env.file.save(packer="original")

    def path_for(self, bundle):
        return "StandaloneWindows64/" + bundle if (self.plat / bundle).is_file() else bundle

    def rel(self, bundle):
        return bundle                                            # the profile's aa root is the platform folder: flat keys

    def test_annotation_fills_every_status_honestly(self):
        out = catalog.annotate(self.reg, self.prof["aa_roots"], self.prof)
        self.assertEqual(out["catalog"]["status"], "ok")
        self.assertEqual(out["catalog"]["records"], 2)
        a, b, c = (self.reg.get_bundle(self.rel(x)) for x in ("ui-styles_assets_common.bundle", "ui-styles_assets_default.bundle", "ui-tileslayouts_assets_all.bundle"))
        self.assertEqual((a["catalog_crc_status"], a["catalog"]["offset"], a["catalog"]["crc_hex"]),
                         ("catalog_crc_match", self.crecs[0]["at"], "%08x" % FIXTURE_CRC))
        self.assertEqual(b["catalog_crc_status"], "catalog_crc_stored_zero")
        self.assertEqual(c["catalog_crc_status"], "catalog_record_missing")
        self.assertEqual(a["manifest_status"], "manifest_match")
        self.assertEqual(b["manifest_status"], "manifest_entry_ambiguous")
        self.assertEqual(c["manifest_status"], "manifest_entry_missing")
        counts = self.reg.integrity_counts()
        self.assertEqual(counts["catalog_crc_status"], {"catalog_crc_match": 1, "catalog_crc_stored_zero": 1, "catalog_record_missing": 1})
        self.assertEqual(counts["manifest_status"], {"manifest_match": 1, "manifest_entry_ambiguous": 1, "manifest_entry_missing": 1})
        self.assertTrue(self.reg.get_integrity_meta()["annotated_utc"])

    def test_annotation_is_incremental_without_any_bundle_reparse(self):
        first = catalog.annotate(self.reg, self.prof["aa_roots"], self.prof)
        self.assertEqual(first["annotated"], 3)
        with mock.patch("skin_editor.bundles.open_readonly", side_effect=AssertionError("no bundle was parsed")):
            second = catalog.annotate(self.reg, self.prof["aa_roots"], self.prof)
        self.assertEqual((second["annotated"], second["skipped_fresh"]), (0, 3))

    def test_a_changed_bundle_is_reannotated(self):
        catalog.annotate(self.reg, self.prof["aa_roots"], self.prof)
        shutil.copyfile(self.b, self.b.with_suffix(".keep"))
        data = bytearray(self.b.read_bytes())
        data[-1] ^= 0xFF
        self.b.write_bytes(bytes(data))
        os.utime(self.b, ns=(1, 1))
        inventory.scan(self.reg, self.prof["aa_roots"])                      # the scan records the new hash and CRC
        out = catalog.annotate(self.reg, self.prof["aa_roots"], self.prof)
        self.assertEqual(out["annotated"], 1)                                # only the changed bundle
        row = self.reg.get_bundle(self.rel("ui-styles_assets_default.bundle"))
        self.assertEqual(row["sha256"], bundles.sha256(self.b))
        shutil.copyfile(self.b.with_suffix(".keep"), self.b)

    def test_a_changed_catalog_identity_reannotates_everything(self):
        catalog.annotate(self.reg, self.prof["aa_roots"], self.prof)
        (self.plat.parent / "catalog.bin").write_bytes(mkcat([
            rec("ui-styles_assets_common.bundle", 1, self.a.stat().st_size)]))
        out = catalog.annotate(self.reg, self.prof["aa_roots"], self.prof)
        self.assertEqual((out["annotated"], out["skipped_fresh"]), (3, 0))
        self.assertEqual(self.reg.get_bundle(self.rel("ui-styles_assets_default.bundle"))["catalog_crc_status"], "catalog_record_missing")

    def test_a_failed_or_absent_catalog_is_reported_not_faked(self):
        (self.plat.parent / "catalog.bin").write_bytes(b"nonsense that is not a catalog at all")
        (self.tmp / "game" / "Game_Data" / "manifest.dat").unlink()
        out = catalog.annotate(self.reg, self.prof["aa_roots"], self.prof)
        self.assertEqual(out["catalog"]["status"], "unsupported")
        a = self.reg.get_bundle(self.rel("ui-styles_assets_common.bundle"))
        self.assertEqual(a["catalog_crc_status"], "catalog_parse_unsupported")
        self.assertEqual(a["manifest_status"], "manifest_parse_unsupported")
        self.assertEqual(out["catalog_crc_status"].get("catalog_parse_unsupported"), 3)

    def test_annotation_can_be_cancelled_and_keeps_what_it_wrote(self):
        out = catalog.annotate(self.reg, self.prof["aa_roots"], self.prof, cancel=lambda: True)
        self.assertTrue(out["cancelled"])

    def test_integrity_bundle_names_every_hash_for_what_it_is(self):
        catalog.annotate(self.reg, self.prof["aa_roots"], self.prof)
        r = catalog.integrity_bundle(self.reg, self.rel("ui-styles_assets_common.bundle"), self.prof, self.prof["aa_roots"])
        self.assertEqual(r["catalog"]["comparison"], "catalog_crc_match")
        self.assertEqual(r["manifest_dat"]["entry_status"], "manifest_match")
        for k, v in r["hashes"]["names"].items():
            self.assertIn("SHA-256" if "sha256" in k else "CRC-32", v)
        self.assertEqual(r["hashes"]["source_uncompressed_crc32"], "%08x" % FIXTURE_CRC)
        self.assertEqual(r["hashes"]["catalog_stored_crc32"], "%08x" % FIXTURE_CRC)
        self.assertEqual(r["hashes"]["physical_file_crc32"], "%08x" % (zlib.crc32(self.a.read_bytes()) & 0xFFFFFFFF))
        self.assertFalse(r["diagnostics"])
        with self.assertRaises(KeyError):
            catalog.integrity_bundle(self.reg, "nope.bundle", self.prof, self.prof["aa_roots"])

    def test_a_stale_profile_catalog_is_said_out_loud(self):
        catalog.annotate(self.reg, self.prof["aa_roots"], self.prof)
        stale = dict(self.prof, catalog_sha256="0" * 64)
        r = catalog.integrity_bundle(self.reg, self.rel("ui-styles_assets_common.bundle"), stale, stale["aa_roots"])
        self.assertIn("not the one the installation profile recorded", " ".join(r["diagnostics"]))


class TestEngineMethods(unittest.TestCase):
    """catalog.status / catalog.annotate / integrity.bundle through JSON-RPC, on a mock installation; the game tree
    never changes."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.addCleanup(self.tmp.cleanup)
        self.addCleanup(close_logs)
        self.e = engine(self.tmp.name)
        self.game, self.plat = make_install(Path(self.tmp.name) / "game")
        wa = zlib.crc32((self.plat / "ui-styles_assets_common.bundle").read_bytes()) & 0xFFFFFFFF
        (self.plat.parent / "catalog.bin").write_bytes(mkcat([rec("ui-styles_assets_common.bundle", FIXTURE_CRC, 483)]))
        (self.game / "Game_Data" / "manifest.dat").write_bytes(struct.pack("<I", wa) + b"\0" * 21)

    def call(self, method, params=None):
        r = json.loads(rpc.handle(self.e, json.dumps({"jsonrpc": "2.0", "method": method, "id": 1, "params": params or {}})))
        self.assertNotIn("error", r, r)
        return r["result"]

    def job(self, method, params=None):
        j = self.call(method, params)
        done = self.e.jobs.wait(j["job"], 60).view()
        self.assertEqual(done["state"], "done", done["error"])
        return done["result"]

    def test_status_annotate_and_bundle_through_the_engine_without_touching_the_game(self):
        before = tree_hashes(self.game)
        self.call("install.profile_select", {"game_dir": str(self.game)})
        out = self.job("inventory.scan", {})
        self.assertEqual(out["integrity"]["catalog"]["records"], 1)                       # the scan job filled the placeholders
        self.assertEqual(out["integrity"]["catalog_crc_status"], {"catalog_crc_match": 1, "catalog_record_missing": 2})
        st = self.call("catalog.status")
        self.assertEqual((st["catalog"]["status"], st["catalog"]["records"]), ("ok", 1))
        self.assertEqual(st["manifest_dat"]["size"], 25)
        self.assertIn("annotated_utc", st)
        self.assertFalse(st["identity_stale"])
        ann = self.job("catalog.annotate", {})
        self.assertEqual(ann["skipped_fresh"], 3)                                         # incremental: nothing new
        rel = "ui-styles_assets_common.bundle"
        one = self.call("integrity.bundle", {"path": rel})
        self.assertEqual((one["catalog"]["comparison"], one["manifest_dat"]["entry_status"]), ("catalog_crc_match", "manifest_match"))
        r = json.loads(rpc.handle(self.e, json.dumps({"jsonrpc": "2.0", "method": "integrity.bundle", "id": 1,
                                                      "params": {"path": "nope.bundle"}})))
        self.assertEqual(r["error"]["code"], -32004)
        self.assertEqual(before, tree_hashes(self.game))

    def test_the_scan_job_result_keeps_its_shape_and_the_annotation_is_cancellable(self):
        self.call("install.profile_select", {"game_dir": str(self.game)})
        out = self.job("inventory.scan", {})
        for k in ("files", "reused", "new", "states", "seconds"):
            self.assertIn(k, out)                                                          # the 4B summary is unchanged
        j = self.call("catalog.annotate", {})
        self.assertTrue(self.call("jobs.cancel", {"id": j["job"]})["cancelled"])


@unittest.skipUnless(SETC_CATALOG.is_file() and (SETC / "ui-styles_assets_common.bundle").is_file(),
                    "archived set-C catalog or style bundles not present")
class TestBuildIntegration(unittest.TestCase):
    """The full build path on COPIED real files: a real sheet edit, the output compared against the copied catalog
    record and the copied manifest.dat, the schema 2 manifest carrying the integrity section, and every source file
    unchanged afterwards. A mismatch is an installation warning, never a build failure."""

    NAME = "ui-styles_assets_common.bundle"

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="fm27se-build-"))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.game, self.plat = make_install(self.tmp)
        for n in bundles.STYLE_BUNDLES:
            shutil.copyfile(SETC / n, self.plat / n)
        shutil.copyfile(SETC_CATALOG, self.plat.parent / "catalog.bin")
        if MANIFEST_DAT.is_file():
            shutil.copyfile(MANIFEST_DAT, self.tmp / "game" / "Game_Data" / "manifest.dat")
        self.ws = config.Workspace(self.tmp / "ws")
        self.ws.vanilla.mkdir(parents=True, exist_ok=True)
        for n in bundles.STYLE_BUNDLES:
            shutil.copyfile(SETC / n, self.ws.vanilla / n)
        (self.ws.vanilla / "manifest.json").write_text(json.dumps(
            {"schema": 1, "game_build": "27.1.0.2505117", "source": "test",
             "files": {n: {"sha256": bundles.sha256(self.ws.vanilla / n)} for n in bundles.STYLE_BUNDLES},
             "image_files": {}, "reference": {"bundles": {}, "catalog_hash": "ccf4d25f06156f55e54a3548a6a2bb2d"}}), encoding="utf-8")
        self.prof = gameinstall.describe_install(self.game, "test", "27.1.0.2505117")
        self.ix = index_styles.build(self.ws, lambda m, f: None)
        # a real sheet of the real bundle, discovered (never a guessed name)
        self.sheet = next(name for _pid, name, _t in bundles.sheets(self.ws.vanilla / self.NAME) if name)
        self.p = project_mod.new("demo", "27.1.0.2505117")
        self.p["scoped_rules"] = [{"sheet": self.sheet, "selector": ".fm27se-4e-probe",
                                   "props": {"background-color": {"rgb": "#010203", "a": 1.0}}}]

    def hashes(self):
        return {p.name: bundles.sha256(p) for p in [SETC_CATALOG] + [SETC / n for n in bundles.STYLE_BUNDLES]}

    def test_a_real_sheet_edit_reports_its_catalog_and_manifest_integrity(self):
        from skin_editor import patcher
        before = self.hashes()
        rep = patcher.build(self.p, self.ws, self.ix, profile=self.prof)
        self.assertEqual(rep["gate"]["fail"], [])
        integ = rep["integrity"]["outputs"][self.NAME]
        self.assertEqual(integ["catalog_crc_status"], "catalog_crc_mismatch")
        self.assertEqual(integ["catalog_stored_crc32"], integ["source_crc32"])
        self.assertNotEqual(integ["output_crc32"], integ["catalog_stored_crc32"])
        self.assertLess(0, integ["catalog_record_offset"])
        m = json.loads((Path(rep["dir"]) / "build-manifest.json").read_text(encoding="utf-8"))
        o = m["outputs"][0]
        self.assertEqual(o["integrity"]["catalog"]["comparison"], "catalog_crc_mismatch")
        self.assertEqual(o["integrity"]["catalog"]["resolution"], "found")
        self.assertLess(0, o["integrity"]["catalog"]["record_offset"])
        self.assertIn("observed, not guaranteed", o["integrity"]["catalog"]["note"])       # the Stage 3G caveat travels with the mismatch
        if MANIFEST_DAT.is_file():
            self.assertEqual(integ["manifest_status"], "manifest_mismatch")
            self.assertEqual(o["integrity"]["manifest_dat"]["comparison"], "manifest_mismatch")
            self.assertIn("expected for any modified bundle", o["integrity"]["manifest_dat"]["mismatch_note"])
        self.assertEqual(m["integrity_sources"]["catalog"]["sha256"], SETC_CATALOG_SHA)
        self.assertFalse(m["integrity_sources"]["catalog"]["identity_stale"])
        self.assertIn("checked_utc", o["integrity"])
        self.assertEqual(m["target"]["install_id"], self.prof["install_id"])
        pkg = json.loads((Path(rep["dir"]) / "package.json").read_text(encoding="utf-8"))
        self.assertEqual(pkg["outputs"][0]["catalog_crc_status"], "catalog_crc_mismatch")    # schema 1 keys all still there
        self.assertIn("files", pkg)
        self.assertEqual(before, self.hashes())                                              # catalog and source bundles unchanged

    def test_without_a_profile_the_integrity_is_recorded_as_not_checked_never_faked(self):
        from skin_editor import patcher
        rep = patcher.build(self.p, self.ws, self.ix)
        self.assertEqual(rep["integrity"]["sources"], None)
        o = rep["integrity"]["outputs"][self.NAME]
        self.assertIsNone(o["catalog_crc_status"])
        m = json.loads((Path(rep["dir"]) / "build-manifest.json").read_text(encoding="utf-8"))
        self.assertIsNone(m["integrity_sources"])
        self.assertIsNone(m["outputs"][0]["integrity"])

    def test_a_stale_catalog_identity_is_its_own_status_not_a_silent_comparison(self):
        from skin_editor import patcher
        stale = dict(self.prof, catalog_sha256="0" * 64)
        rep = patcher.build(self.p, self.ws, self.ix, profile=stale)
        m = json.loads((Path(rep["dir"]) / "build-manifest.json").read_text(encoding="utf-8"))
        o = m["outputs"][0]
        self.assertEqual(o["integrity"]["catalog"]["comparison"], "catalog_identity_stale")
        self.assertIn("not the one the installation profile recorded", " ".join(o["integrity"]["diagnostics"]))


class TestSchemaCompat(unittest.TestCase):
    """Schema 1 packages still load; a 4D-era schema 2 manifest without integrity fields still loads; missing
    integrity data is never presented as a successful check."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="fm27se-sch-"))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)

    def test_schema1_and_integrityless_schema2_both_load(self):
        from skin_editor import manifest as m
        p1 = self.tmp / "p1.json"
        p1.write_text(json.dumps({"schema": 1, "id": "x", "files": {}, "gate": {"passed": True}}), encoding="utf-8")
        self.assertEqual(m.read_package(p1)["schema"], 1)
        p2 = self.tmp / "p2.json"
        p2.write_text(json.dumps({"schema": 2, "id": "x", "outputs": [{"rel_path": "a", "catalog_crc_status": None}]}), encoding="utf-8")
        d = m.read_package(p2)
        self.assertIsNone(d["outputs"][0]["catalog_crc_status"])                    # absent/None means not checked, not passed

    def test_a_new_package_carries_the_integrity_keys_optionally(self):
        from skin_editor import manifest as m
        pkg1 = {"schema": 1, "id": "t", "files": {}, "gate": {"passed": True}}
        man = {"target": {}, "edits": [], "outputs": [{"rel_path": "a.bundle", "source_sha256": "s", "output_sha256": "o",
                                                       "source_crc32": "00000001", "output_crc32": "00000002",
                                                       "catalog_crc_status": "catalog_crc_mismatch", "manifest_status": "manifest_mismatch",
                                                       "diff": None, "integrity": None}],
               "validation": [], "overrides": {}, "impact": {"buildable": True, "installation_readiness": "uncertain"},
               "tools": {}, "integrity_sources": {"catalog": {"sha256": "c"}}}
        pkg2 = m.schema2_package(pkg1, man)
        self.assertEqual(pkg2["schema"], 2)
        self.assertEqual(pkg2["outputs"][0]["catalog_crc_status"], "catalog_crc_mismatch")
        self.assertEqual(pkg2["outputs"][0]["manifest_status"], "manifest_mismatch")
        self.assertEqual(pkg2["integrity_sources"]["catalog"]["sha256"], "c")
        for k in pkg1:
            if k != "schema":
                self.assertEqual(pkg2[k], pkg1[k], k)


if __name__ == "__main__":
    unittest.main()
