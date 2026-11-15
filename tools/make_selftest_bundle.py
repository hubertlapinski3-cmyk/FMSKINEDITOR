"""Write the committed fixture of the frozen engine's bundle round-trip self-test: data/selftest/roundtrip.unity3d.

    python tools/make_selftest_bundle.py

No game file is used or copied: the bundle is SYNTHETIC, written byte by byte here, so it can be committed. It is a UnityFS bundle (format 8, one LZ4-compressed block)
holding one SerializedFile (format 22, little-endian, with an embedded type tree) with ONE object, a TextAsset (class 49) named "fm-skin-studio-selftest". That is enough to
drive the same library path the bundle build uses (skin_editor/bundles.py): UnityPy loads the bundle, reads the object through its type tree, writes it back with
`save_typetree`, packs the bundle with `env.save(pack="original")` (LZ4 again) and loads the result. The self-test is skin_editor/frozen.py:bundle_roundtrip."""
import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "selftest" / "roundtrip.unity3d"
UNITY = b"2022.3.62f1"
NAME = b"fm-skin-studio-selftest"
SCRIPT = b"FM Skin Studio self-test fixture: synthetic, no game content."
CAB = b"CAB-fmskinstudioselftest0000000"


def _typetree():
    """TextAsset: m_Name (string), m_Script (string). Nodes as Unity writes them (format 19+ nodes with refTypeHash)."""
    strings = b""
    offs = {}

    def s(x):
        nonlocal strings
        if x not in offs:
            offs[x] = len(strings)
            strings += x + b"\0"
        return offs[x]
    nodes = []

    def node(level, typ, name, size, is_array=0, meta=0):
        nodes.append(struct.pack("<HBBIIiiiQ", 1, level, is_array, s(typ), s(name), size, len(nodes), meta, 0))
    node(0, b"TextAsset", b"Base", -1)
    for field in (b"m_Name", b"m_Script"):
        node(1, b"string", field, -1, 0, 0x8000)
        node(2, b"Array", b"Array", -1, 1, 0x4000)
        node(3, b"int", b"size", 4)
        node(3, b"char", b"data", 1)
    return struct.pack("<ii", len(nodes), len(strings)) + b"".join(nodes) + strings


def _aligned_string(b):
    out = struct.pack("<i", len(b)) + b
    return out + b"\0" * ((4 - len(out) % 4) % 4)


def serialized_file():
    obj = _aligned_string(NAME) + _aligned_string(SCRIPT)
    meta = bytearray()
    meta += UNITY + b"\0"                                    # unity version
    meta += struct.pack("<i", 19)                            # target platform: StandaloneWindows64
    meta += b"\x01"                                          # type tree enabled
    meta += struct.pack("<i", 1)                             # one type
    meta += struct.pack("<i", 49) + b"\x00" + struct.pack("<h", -1)   # class 49 TextAsset, not stripped, no script
    meta += b"\0" * 16                                       # old type hash (no script id for a non-MonoBehaviour)
    meta += _typetree()
    meta += struct.pack("<i", 0)                             # type dependencies (format >= 21)
    meta += struct.pack("<i", 1)                             # one object
    hdr_len = 48
    pad_to = lambda n: (4 - n % 4) % 4
    pre = hdr_len + len(meta)
    meta += b"\0" * pad_to(pre)                              # objects are 4-aligned (format >= 14)
    obj_entry_pos = len(meta)
    meta += struct.pack("<q", 1)                             # path id 1
    meta += struct.pack("<q", 0)                             # byte start (relative to data offset), int64 for format >= 22
    meta += struct.pack("<I", len(obj))                      # byte size
    meta += struct.pack("<i", 0)                             # type index 0
    meta += struct.pack("<i", 0)                             # script types
    meta += struct.pack("<i", 0)                             # externals
    meta += struct.pack("<i", 0)                             # ref types (format >= 20)
    meta += b"\0"                                            # user information
    data_offset = hdr_len + len(meta)
    data_offset += (16 - data_offset % 16) % 16
    file_size = data_offset + len(obj)
    header = struct.pack(">IIII", 0, 0, 22, 0) + b"\x00\x00\x00\x00" + struct.pack(">IqqQ", len(meta), file_size, data_offset, 0)
    assert len(header) == hdr_len, len(header)
    body = header + bytes(meta)
    body += b"\0" * (data_offset - len(body))
    return body + obj, obj_entry_pos


def bundle():
    import lz4.block
    sf, _ = serialized_file()
    block = lz4.block.compress(sf, store_size=False, mode="high_compression")
    dir_info = bytearray(b"\0" * 16)                         # uncompressed data hash
    dir_info += struct.pack(">i", 1) + struct.pack(">IIH", len(sf), len(block), 3)        # one block, LZ4HC (3)
    dir_info += struct.pack(">i", 1) + struct.pack(">qqI", 0, len(sf), 4) + CAB + b"\0"   # one node: the serialized file (flag 4)
    dir_info = bytes(dir_info)
    head = b"UnityFS\0" + struct.pack(">I", 8) + b"5.x.x\0" + UNITY + b"\0"
    flags = 0x40                                             # blocks and directory combined, right after the header (format >= 7 aligns that header to 16)
    size_fields = 8 + 4 + 4 + 4
    pre = len(head) + size_fields
    pad = (16 - pre % 16) % 16
    total = pre + pad + len(dir_info) + len(block)
    out = head + struct.pack(">qIII", total, len(dir_info), len(dir_info), flags) + b"\0" * pad + dir_info + block
    assert len(out) == total
    return out


def main():
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_bytes(bundle())
    print(OUT, OUT.stat().st_size, "bytes")


if __name__ == "__main__":
    sys.exit(main())
