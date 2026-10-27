#!/usr/bin/env python3
"""Regenerate the NotPatch analysis outputs and check them against MANIFEST.json.

Standard library only. Run from any directory:

    python3 reproduce.py               # unpack, run every step, verify outputs
    python3 reproduce.py --check-only  # verify shipped files without running
"""

from __future__ import annotations

import argparse
import hashlib
import json
import lzma
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
MANIFEST = json.loads((ROOT / "MANIFEST.json").read_text(encoding="utf-8"))


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for block in iter(lambda: fh.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def unpack() -> None:
    # Large inputs ship as .xz; restore them at the paths the scripts expect.
    for item in MANIFEST["compressed"]:
        target = ROOT / item["path"]
        if target.exists() and sha256(target) == item["sha256"]:
            continue
        with lzma.open(ROOT / (item["path"] + ".xz")) as src, target.open("wb") as dst:
            shutil.copyfileobj(src, dst)
        if sha256(target) != item["sha256"]:
            sys.exit(f"checksum mismatch after unpacking {item['path']}")


def restore_assets() -> None:
    # Release assets sit in ../release-assets in the GitHub repository; restore any that are absent.
    shelf = ROOT.parent / "release-assets"
    for item in MANIFEST["release_assets"]:
        target, source = ROOT / item["place_at"], shelf / item["asset"]
        if target.exists() or not source.exists():
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        opener = lzma.open if item["asset"].endswith(".xz") else open
        with opener(source, "rb") as src, target.open("wb") as dst:
            shutil.copyfileobj(src, dst, 1 << 20)
        if sha256(target) != item["sha256"]:
            sys.exit(f"checksum mismatch after restoring {item['asset']}")


def check(paths: dict[str, str]) -> list[str]:
    return [p for p, h in paths.items() if not (ROOT / p).exists() or sha256(ROOT / p) != h]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--check-only", action="store_true", help="verify shipped files; run nothing")
    parser.add_argument("--skip", nargs="*", default=[], help="step names to skip")
    args = parser.parse_args()
    if sys.version_info < (3, 12):
        print("warning: Python 3.12+ is needed for byte-identical outputs (3.12 changed float summation)")

    bad = check(MANIFEST["files"])
    if bad:
        print("Shipped files that differ from MANIFEST.json:", *bad, sep="\n  ")
        return 1
    unpack()
    restore_assets()
    if args.check_only:
        print(f"OK: {len(MANIFEST['files'])} shipped files and {len(MANIFEST['compressed'])} unpacked inputs match")
        return 0

    ran, skipped = [], []
    for step in MANIFEST["commands"]:
        missing = [a for a in step["requires_assets"] if not (ROOT / a).exists()]
        if step["name"] in args.skip or missing:
            skipped.append((step["name"], "requested" if step["name"] in args.skip else f"missing {missing[0]}"))
            continue
        print(f"[run] {step['name']}: {step['description']}", flush=True)
        result = subprocess.run([sys.executable, *step["argv"]], cwd=ROOT, capture_output=True, text=True)
        if result.returncode:
            print(result.stdout, result.stderr, f"step {step['name']} failed", sep="\n")
            return 1
        ran.append(step["name"])

    bad = check(MANIFEST["outputs"])
    for name, why in skipped:
        print(f"[skip] {name}: {why}")
    if bad:
        print("Outputs that differ from MANIFEST.json:", *bad, sep="\n  ")
        return 1
    print(f"OK: ran {len(ran)} steps; all {len(MANIFEST['outputs'])} outputs match MANIFEST.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
