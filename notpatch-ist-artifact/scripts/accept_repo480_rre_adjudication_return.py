#!/usr/bin/env python3
"""Accept the RR-E third-expert return without replacing any earlier coding pass."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from notpatch.canonical import canonical_json_bytes, sha256_file
from analyze_repo480_rre_verification import pointer_audit, read_jsonl
from prepare_repo480_rre_adjudication import BATCH_ID, CODES_NAME, ROLE, WORKLIST_NAME
from selfcheck_repo480_rre_adjudication_return import validate_return


def accept(args: argparse.Namespace) -> dict:
    date.fromisoformat(args.accepted_on)
    manifest = json.loads((ROOT / args.package_manifest).read_text())
    if manifest["batch_id"] != BATCH_ID or manifest["coder_id"] != ROLE:
        raise ValueError("unexpected package batch/coder")
    package = ROOT / args.request_root / ROLE
    for name, digest in manifest["package_files"].items():
        if name != CODES_NAME and sha256_file(package / name) != digest:
            raise ValueError(f"package file changed: {name}")
    for path, digest in manifest["inputs"].items():
        if sha256_file(ROOT / path) != digest:
            raise ValueError(f"package source changed: {path}")
    if sha256_file(ROOT / args.request_root / "README.md") != manifest["batch_readme_sha256"]:
        raise ValueError("coordinator instructions changed")
    work = read_jsonl(package / WORKLIST_NAME)
    returned = package / CODES_NAME
    codes = read_jsonl(returned)
    errors = validate_return(work, codes)
    if errors:
        raise ValueError("; ".join(errors))
    if [r["item_id"] for r in codes] != manifest["item_ids"] or len(codes) != manifest["row_count"]:
        raise ValueError("selection or order differs from the package")
    normalization = None
    if args.received_original:
        if not args.normalization_note:
            raise ValueError("original return requires a normalization note recording expert confirmation")
        original = read_jsonl(ROOT / args.received_original)
        normalized = [dict(r, exposure_note=None) if r["exposure_note"] == "" else r for r in original]
        if normalized != codes:
            raise ValueError("only confirmed empty exposure_note to null normalization is allowed")
        normalization = {
            "received_original": str(args.received_original),
            "sha256": sha256_file(ROOT / args.received_original),
            "changed_items": [r["item_id"] for r in original if r["exposure_note"] == ""],
            "change": "exposure_note: empty string to null; all other values unchanged",
            "confirmation": args.normalization_note,
        }
    elif args.normalization_note:
        raise ValueError("normalization note requires the preserved original return")
    result = {
        "schema_version": "repo480-rre-adjudication-returns-manifest-v1",
        "batch_id": BATCH_ID, "coder_id": ROLE, "accepted_on": args.accepted_on,
        "canonical_ref": str(args.canonical_out), "sha256": sha256_file(returned),
        "row_count": len(codes), "item_ids": manifest["item_ids"],
        "package_manifest": {"ref": str(args.package_manifest), "sha256": sha256_file(ROOT / args.package_manifest)},
        "normalization": normalization, "deviations": args.deviation,
        "pointer_audit": pointer_audit(work, codes),
        "exposure_notes": {r["item_id"]: r["exposure_note"] for r in codes if r["exposure_note"] is not None},
        "acceptance_script": {"ref": "scripts/accept_repo480_rre_adjudication_return.py", "sha256": sha256_file(Path(__file__))},
    }
    outputs = [(ROOT / args.canonical_out, returned.read_bytes()),
               (ROOT / args.returns_manifest, canonical_json_bytes(result))]
    for path, payload in outputs:
        if path.exists() and path.read_bytes() != payload:
            raise ValueError(f"refusing to replace a different accepted artifact: {path}")
    for path, payload in outputs:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(payload)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--accepted-on", required=True, help="YYYY-MM-DD")
    parser.add_argument("--received-original", type=Path)
    parser.add_argument("--normalization-note")
    parser.add_argument("--deviation", action="append", default=[])
    for name, default in {
        "request-root": "request/repo480_rre_adjudication",
        "package-manifest": "data/manifests/generated/repo480_rre_adjudication_manifest_v1.json",
        "canonical-out": "data/annotations/typology/repo480_p1_typology_codes_adj_v1.jsonl",
        "returns-manifest": "data/manifests/generated/repo480_rre_adjudication_returns_manifest_v1.json",
    }.items():
        parser.add_argument(f"--{name}", type=Path, default=Path(default))
    try:
        result = accept(parser.parse_args())
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1
    print(f"OK: accepted {result['row_count']} adjudication rows ({result['sha256']})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
