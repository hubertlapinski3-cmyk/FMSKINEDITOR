"""Content hashes used to qualify serialized Unity asset locators and derived caches."""
import hashlib
from pathlib import Path


def sha256_file(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def bundle_manifest(folder, pattern="*.bundle"):
    """Content-addressed manifest. A same-size/same-mtime replacement cannot reuse its cache key."""
    root = Path(folder)
    entries = [(p.name, sha256_file(p)) for p in sorted(root.glob(pattern))]
    encoded = "\n".join("%s:%s" % row for row in entries).encode("utf-8")
    return {"sha256": hashlib.sha256(encoded).hexdigest(), "bundles": dict(entries)}
