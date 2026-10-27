#!/usr/bin/env python3
"""Standalone self-check for an RR-E typology verification coding return (repo480_rre_c2).

Checks row linkage, allowed values and the applicability rules of
the frozen codebook (sections 4 and 5). It never derives or prints types.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

CODE_SCHEMA = "repo480-p1-typology-code-v1"
CODER_ID = "repo480_rre_c2"
RECORD_KEYS = {
    "schema_version",
    "coder_id",
    "item_id",
    "task_id",
    "set",
    "codes",
    "evidence_refs",
    "coder_note",
    "exposure_note",
}
A_FIELDS = {
    "divergence_kind": {"implementation_only", "added_behavior", "different_behavior", "unclear"},
    "predicted_supported": {"yes", "no", "unclear"},
    "oracle_basis": {
        "required_by_packet",
        "admissible_not_selected",
        "outside_issue_scope",
        "not_applicable",
        "unclear",
    },
    "assumption_anticipated": {"yes", "no", "not_applicable"},
}
A_TEXT = ("oracle_divergence",)
A_TYPES = {
    "a_same_contract",
    "b_contract_choice",
    "c_evidence_reading",
    "d_oracle_scope",
    "u_undeterminable",
}
B_FIELDS = {
    "alternative_relation": {
        "distinct_contract",
        "same_contract_variant",
        "no_executable_candidate",
        "unclear",
    },
    "p01_side_treatment": {
        "excluded_by_cited_evidence",
        "named_as_bounded_assumption",
        "not_addressed",
        "unclear",
    },
    "p23_side_engages_p01_evidence": {"yes", "no", "not_applicable", "unclear"},
    "p23_side_cites_packet_for_alternative": {"yes", "no", "unclear"},
}
B_TEXT = ("disputed_alternative",)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--worklist", required=True, type=Path)
    parser.add_argument("--codes", required=True, type=Path)
    args = parser.parse_args()
    try:
        worklist = _load(args.worklist)
        codes = _load(args.codes)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1
    errors = validate_codes(worklist, codes)
    if errors:
        for error in errors[:40]:
            print(f"FAIL: {error}", file=sys.stderr)
        if len(errors) > 40:
            print(f"FAIL: ... {len(errors) - 40} more", file=sys.stderr)
        return 1
    print(f"OK: {len(codes)} complete {worklist[0]['set']} codes")
    return 0


def validate_codes(worklist: list[dict[str, Any]], codes: list[dict[str, Any]]) -> list[str]:
    """Return every problem found; an empty list means the return is complete."""
    sets = {row["set"] for row in worklist}
    if len(sets) != 1 or not sets <= {"p1_non_strict", "boundary_discordant"}:
        return ["worklist must hold exactly one known set"]
    if len(codes) != len(worklist):
        return [f"codes have {len(codes)} rows; the worklist has {len(worklist)}"]
    errors: list[str] = []
    for work, code in zip(worklist, codes):
        item = work["item_id"]
        if set(code) != RECORD_KEYS:
            errors.append(f"{item}: record keys must be exactly {sorted(RECORD_KEYS)}")
            continue
        for key in ("item_id", "task_id", "set"):
            if code[key] != work[key]:
                errors.append(f"{item}: {key} does not match the worklist row in the same position")
        if code["schema_version"] != CODE_SCHEMA or code["coder_id"] != CODER_ID:
            errors.append(f"{item}: schema_version and coder_id must stay as given")
        errors.extend(_check_common(item, code))
        if work["set"] == "p1_non_strict":
            errors.extend(_check_a(item, code["codes"]))
        else:
            errors.extend(_check_b(item, code["codes"]))
    return errors


def _check_common(item: str, code: dict[str, Any]) -> list[str]:
    errors = []
    refs = code["evidence_refs"]
    if not isinstance(refs, list) or not refs or not all(_text(ref) for ref in refs):
        errors.append(f"{item}: evidence_refs must list at least one non-empty pointer")
    if not _text(code["coder_note"]):
        errors.append(f"{item}: coder_note is empty")
    note = code["exposure_note"]
    if note is not None and not _text(note):
        errors.append(f"{item}: exposure_note must be null or a non-empty sentence")
    return errors


def _check_a(item: str, values: dict[str, Any]) -> list[str]:
    expected = set(A_FIELDS) | set(A_TEXT) | {"secondary_types"}
    if not isinstance(values, dict) or set(values) != expected:
        return [f"{item}: codes keys must be exactly {sorted(expected)}"]
    errors = _check_values(item, values, A_FIELDS, A_TEXT)
    secondary = values["secondary_types"]
    if (
        not isinstance(secondary, list)
        or not all(isinstance(value, str) for value in secondary)
        or not set(secondary) <= A_TYPES
        or len(set(secondary)) != len(secondary)
    ):
        errors.append(f"{item}: secondary_types must be a list of distinct {sorted(A_TYPES)}")
    if errors:
        return errors
    implementation = values["divergence_kind"] == "implementation_only"
    if implementation != (values["oracle_basis"] == "not_applicable"):
        errors.append(f"{item}: oracle_basis=not_applicable only and always with implementation_only")
    if implementation != (values["assumption_anticipated"] == "not_applicable"):
        errors.append(
            f"{item}: assumption_anticipated=not_applicable only and always with implementation_only"
        )
    return errors


def _check_b(item: str, values: dict[str, Any]) -> list[str]:
    expected = set(B_FIELDS) | set(B_TEXT)
    if not isinstance(values, dict) or set(values) != expected:
        return [f"{item}: codes keys must be exactly {sorted(expected)}"]
    errors = _check_values(item, values, B_FIELDS, B_TEXT)
    if errors:
        return errors
    excluded = values["p01_side_treatment"] == "excluded_by_cited_evidence"
    if excluded == (values["p23_side_engages_p01_evidence"] == "not_applicable"):
        errors.append(
            f"{item}: p23_side_engages_p01_evidence=not_applicable only and always when "
            "p01_side_treatment is not excluded_by_cited_evidence"
        )
    return errors


def _check_values(
    item: str, values: dict[str, Any], fields: dict[str, set[str]], text_fields: tuple[str, ...]
) -> list[str]:
    errors = []
    for field in text_fields:
        if not _text(values[field]):
            errors.append(f"{item}: {field} is empty")
    for field, allowed in fields.items():
        if not isinstance(values[field], str) or values[field] not in allowed:
            errors.append(f"{item}: {field}={values[field]!r} is not one of {sorted(allowed)}")
    return errors


def _text(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _load(path: Path) -> list[dict[str, Any]]:
    rows = []
    with path.open(encoding="utf-8") as handle:
        for number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            row = json.loads(line)
            if not isinstance(row, dict):
                raise ValueError(f"{path}:{number} is not a JSON object")
            rows.append(row)
    if not rows:
        raise ValueError(f"{path} is empty")
    return rows


if __name__ == "__main__":
    raise SystemExit(main())
