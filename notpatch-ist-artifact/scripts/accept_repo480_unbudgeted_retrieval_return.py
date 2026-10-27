#!/usr/bin/env python3
"""Accept the RR-F expanded-view return as a byte-identical canonical copy.

The package files other than the return must still match the setup manifest, the
frozen setup inputs and preserved archive must be unchanged, and the return must pass
the distributed package validator. An existing different canonical copy is never replaced.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from notpatch.canonical import canonical_json_bytes, sha256_file  # noqa: E402
from prepare_repo480_unbudgeted_retrieval_audit import BATCH, POLICY  # noqa: E402
from selfcheck_repo480_retrieval_audit import RETURN_NAME, ROLE, load_rows, validate  # noqa: E402


def accept(args: argparse.Namespace) -> dict:
    date.fromisoformat(args.accepted_on)
    setup = json.loads((ROOT / args.setup_manifest).read_text())
    if (setup["batch_id"], setup["policy_id"], setup["package_dir_name"]) != (BATCH, POLICY, ROLE):
        raise ValueError("unexpected setup batch/policy/role")
    for path, digest in setup["inputs"].items():
        if sha256_file(ROOT / path) != digest:
            raise ValueError(f"setup input changed: {path}")
    if sha256_file(ROOT / args.selection) != setup["selection_sha256"]:
        raise ValueError("selection changed")
    if sha256_file(ROOT / setup["archive_ref"]) != setup["archive_sha256"]:
        raise ValueError("preserved archive changed")
    package = ROOT / args.request_root / ROLE
    for name, digest in setup["package_files"].items():
        if name != RETURN_NAME and sha256_file(package / name) != digest:
            raise ValueError(f"package file changed: {name}")
    if sha256_file(ROOT / args.request_root / "README.md") != setup["coordinator_readme_sha256"]:
        raise ValueError("coordinator instructions changed")
    returned = package / RETURN_NAME
    audit = validate(package, returned)
    rows = load_rows(returned)
    expected = [(w["item_id"], w["task_id"]) for w in setup["work_items"]]
    if [(r["item_id"], r["task_id"]) for r in rows] != expected or len(rows) != setup["row_count"]:
        raise ValueError("return identity or order differs from the setup")
    result = {
        "schema_version": "repo480-expanded-retrieval-returns-manifest-v1",
        "batch_id": BATCH, "policy_id": POLICY, "annotator_id": ROLE,
        "accepted_on": args.accepted_on,
        "canonical_ref": str(args.canonical_out), "sha256": sha256_file(returned),
        "row_count": len(rows), "item_ids": [r["item_id"] for r in rows],
        "setup_manifest": {"ref": str(args.setup_manifest), "sha256": sha256_file(ROOT / args.setup_manifest)},
        "selection": {"ref": str(args.selection), "sha256": setup["selection_sha256"]},
        "archive": {"ref": setup["archive_ref"], "sha256": setup["archive_sha256"]},
        "annotation_status_counts": dict(sorted(Counter(r["annotation_status"] for r in rows).items())),
        "protocol_deviations": {r["item_id"]: r["protocol_deviation"] for r in rows if r["protocol_deviation"] is not None},
        "exposure_notes": {r["item_id"]: r["exposure_note"] for r in rows if r["exposure_note"] is not None},
        "not_assessable_items": [r["item_id"] for r in rows if r["annotation_status"] == "not_assessable"],
        "citation_audit": audit,
        "acceptance_notes": list(args.acceptance_note),
        "acceptance_script": {"ref": "scripts/accept_repo480_unbudgeted_retrieval_return.py",
                              "sha256": sha256_file(Path(__file__))},
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
    parser.add_argument("--acceptance-note", action="append", default=[],
                        help="coordinator provenance or limitation recorded at acceptance (repeatable)")
    for name, default in {
        "request-root": "request/repo480_unbudgeted_retrieval",
        "setup-manifest": "data/manifests/generated/repo480_unbudgeted_retrieval_manifest_v1.json",
        "selection": "data/annotations/worklists/repo480_unbudgeted_retrieval_selection_v1.jsonl",
        "canonical-out": "data/annotations/expanded_retrieval/repo480_retrieval_r1_v1.jsonl",
        "returns-manifest": "data/manifests/generated/repo480_unbudgeted_retrieval_returns_manifest_v1.json",
    }.items():
        parser.add_argument(f"--{name}", type=Path, default=Path(default))
    try:
        result = accept(parser.parse_args())
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1
    print(f"OK: accepted {result['row_count']} expanded-view rows ({result['sha256']})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
