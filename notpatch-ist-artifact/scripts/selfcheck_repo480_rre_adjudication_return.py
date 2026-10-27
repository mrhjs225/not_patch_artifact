#!/usr/bin/env python3
"""Standalone RR-E adjudication return check; keep verification rules alongside this file."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from selfcheck_repo480_rre_verification_return import _load, validate_codes

CODER_ID = "repo480_rre_adj"


def validate_return(worklist: list[dict], codes: list[dict]) -> list[str]:
    if any(row.get("coder_id") != CODER_ID for row in codes):
        return [f"coder_id must be {CODER_ID}"]
    errors = validate_codes(worklist, [dict(row, coder_id="repo480_rre_c2") for row in codes])
    if errors:
        return errors
    for row, code in zip(worklist, codes):
        for ref in code["evidence_refs"]:
            path = ref.partition(":")[0]
            if path.split(".")[0] not in {"issue", "frozen", "boundary_panel", "construct_validity", "oracle"}:
                errors.append(f"{code['item_id']}: cite an evidence field, not a coder conclusion: {ref}")
                continue
            value = row
            try:
                for part in path.split("."):
                    value = value[int(part)] if isinstance(value, list) else value[part]
                if value is None or value == "" or value == [] or value == {}:
                    raise ValueError("empty value")
            except (KeyError, IndexError, TypeError, ValueError):
                errors.append(f"{code['item_id']}: missing or empty evidence field: {ref}")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--worklist", required=True, type=Path)
    parser.add_argument("--codes", required=True, type=Path)
    args = parser.parse_args()
    try:
        codes = _load(args.codes)
        errors = validate_return(_load(args.worklist), codes)
        if errors:
            raise ValueError("\n".join(errors))
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1
    print(f"OK: {len(codes)} complete adjudication codes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
