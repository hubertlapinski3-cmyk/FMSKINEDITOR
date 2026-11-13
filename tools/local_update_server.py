"""Serve a Tauri updater feed from a local folder, to test an app update before (or without) GitHub Releases.

    python tools/local_update_server.py --bundle studio/src-tauri/target/release/bundle/nsis --version 0.1.2 [--port 8899] [--notes TEXT]

Finds `*_<version>_x64-setup.exe` and its `.sig` in the folder, writes latest.json next to them (the same shape tauri-action publishes) and serves the folder on
127.0.0.1. Start the installed app with FM27SE_UPDATE_URL=http://127.0.0.1:8899/latest.json. The app still verifies the signature against the public key in its
config, so this server cannot install anything the updater key did not sign."""
import argparse
import datetime
import functools
import http.server
import json
import sys
import urllib.parse
from pathlib import Path


def make_latest(folder, version, base, notes):
    folder = Path(folder)
    exe = next((p for p in sorted(folder.glob("*_%s_x64-setup.exe" % version))), None)
    if exe is None:
        raise SystemExit("no *_%s_x64-setup.exe in %s" % (version, folder))
    sig = Path(str(exe) + ".sig")
    if not sig.is_file():
        raise SystemExit("missing signature file %s (build with TAURI_SIGNING_PRIVATE_KEY set and createUpdaterArtifacts on)" % sig)
    doc = {"version": version, "notes": notes, "pub_date": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
           "platforms": {"windows-x86_64": {"signature": sig.read_text(encoding="utf-8").strip(), "url": "%s/%s" % (base, urllib.parse.quote(exe.name))}}}
    (folder / "latest.json").write_text(json.dumps(doc, indent=2), encoding="utf-8")
    return doc


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bundle", required=True)
    ap.add_argument("--version", required=True)
    ap.add_argument("--port", type=int, default=8899)
    ap.add_argument("--notes", default="Local test update")
    a = ap.parse_args()
    base = "http://127.0.0.1:%d" % a.port
    doc = make_latest(a.bundle, a.version, base, a.notes)
    print("serving %s on %s (latest.json version %s)" % (a.bundle, base, doc["version"]), flush=True)
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(Path(a.bundle).resolve()))
    http.server.ThreadingHTTPServer(("127.0.0.1", a.port), handler).serve_forever()


if __name__ == "__main__":
    sys.exit(main())
