"""One-off download of the SRD 5.1 (2014) data the GM tools read (planning/06 → `gm.py
srd`; 03 → Legal note; plan.md Phase 4 item 5). The only tool that touches the network;
`gm.py` never does.

    python tools/fetch_srd.py [--force] [--only Monsters Spells ...]

Lists the 5e-bits `5e-database` directory first (never a hard-coded file list), then
downloads the wanted `5e-SRD-<Thing>.json` files into `data/srd/` and writes
`data/srd/LICENSE.md` with the attribution. Existing files are kept unless `--force`.
"""
import argparse
import json
import os
import sys
import urllib.request
from pathlib import Path

REPO = "5e-bits/5e-database"
DIR = "src/2014/en"
LISTING = f"https://api.github.com/repos/{REPO}/contents/{DIR}"
# Phase 4 needs these; Phase 6 adds Classes, Subclasses, Levels, Features, Races,
# Subraces, Traits, Equipment, Backgrounds (pass them with --only).
WANTED = ("Monsters", "Spells", "Conditions")
OUT = Path(__file__).resolve().parents[1] / "data" / "srd"

LICENSE = """# SRD data — license and attribution

The JSON files in this folder are taken from the **5e-bits `5e-database`** project
(https://github.com/5e-bits/5e-database, directory `{dir}`), which is MIT-licensed
(Copyright (c) 2018-2020 Adrian Padua, Christopher Ward).

The game content in them is from the **System Reference Document 5.1** ("SRD 5.1") by
Wizards of the Coast LLC, available at https://dnd.wizards.com/resources/systems-reference-document.
The SRD 5.1 is licensed under the Creative Commons Attribution 4.0 International License,
available at https://creativecommons.org/licenses/by/4.0/legalcode.

Files: {files}
Downloaded by `tools/fetch_srd.py`; not edited by hand.
"""


def _get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "dnd-adventure-fetch-srd"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read()


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--force", action="store_true", help="re-download files that exist")
    ap.add_argument("--only", nargs="+", metavar="THING", help="e.g. Monsters Classes")
    args = ap.parse_args(argv)
    wanted = args.only or WANTED
    listing = json.loads(_get(LISTING))
    files = {item["name"]: item["download_url"] for item in listing if item.get("type") == "file"}
    OUT.mkdir(parents=True, exist_ok=True)
    missing = [t for t in wanted if f"5e-SRD-{t}.json" not in files]
    if missing:
        print("not in the listing: " + ", ".join(missing) + f"\navailable: {', '.join(sorted(files))}")
        return 1
    for thing in wanted:
        name = f"5e-SRD-{thing}.json"
        dest = OUT / name
        if dest.exists() and not args.force:
            print(f"[kept] {name}")
            continue
        data = _get(files[name])
        json.loads(data)  # refuse to save something that isn't JSON
        tmp = dest.with_suffix(".tmp")
        tmp.write_bytes(data)
        os.replace(tmp, dest)
        print(f"[downloaded] {name} ({len(data):,} bytes)")
    have = sorted(p.name for p in OUT.glob("5e-SRD-*.json"))
    (OUT / "LICENSE.md").write_text(LICENSE.format(dir=DIR, files=", ".join(have)), encoding="utf-8")
    print(f"[wrote] {OUT / 'LICENSE.md'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
