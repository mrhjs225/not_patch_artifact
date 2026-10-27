#!/usr/bin/env python3
"""Validate a completed repo480 RQ2 Phase 2 adjudication return."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any


BATCH_ID = "repo480_rq2_masking_v1"
PHASE = "oracle_diagnostic_adjudication"
ADJUDICATOR_ID = "repo480_rq2_adj"
EXPECTED_ROWS = 3
ALLOWED_VALUES = {
    "oracle_direction_in_candidate_set": {"yes", "no", "unclear"},
    "oracle_revealed_missing_evidence": {"yes", "partial", "no", "unclear"},
    "oracle_alternative_fix_exists": {"yes", "no", "unclear"},
    "available_evidence_unique_in_hindsight": {"yes", "no", "unclear"},
    "behavior_target_space_size": {"1", "2-3", "many", "unclear"},
    "data_quality": {"Q0", "Q1", "Q2"},
}
ALLOWED_POINTER_PREFIXES = {
    "phase1_tasks",
    "phase2_r1_tasks",
    "phase2_r2_tasks",
    "phase2_r1_return",
    "phase2_r2_return",
}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--worklist",
        type=Path,
        default=Path("repo480_rq2_adjudication_worklist.jsonl"),
    )
    parser.add_argument(
        "--return-file",
        type=Path,
        default=Path("repo480_rq2_adjudication_return.jsonl"),
    )
    args = parser.parse_args()

    try:
        worklist = load_jsonl(args.worklist)
        returned = load_jsonl(args.return_file)
        validate_return(worklist, returned)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1
    print(f"OK: {len(returned)} completed RQ2 adjudication decisions")
    return 0


def validate_return(
    worklist: list[dict[str, Any]], returned: list[dict[str, Any]]
) -> None:
    if len(worklist) != EXPECTED_ROWS or len(returned) != EXPECTED_ROWS:
        raise ValueError("worklist and return must each contain 3 rows")
    work_by_task = _index(worklist, "worklist")
    return_by_task = _index(returned, "return")
    if set(work_by_task) != set(return_by_task):
        raise ValueError("return task set does not match worklist")

    for work in worklist:
        task_id = work["task_id"]
        decision = return_by_task[task_id]
        context = f"{task_id}"
        if work.get("schema_version") != "repo480-rq2-phase2-adjudication-task-v1":
            raise ValueError(f"{context}: worklist schema mismatch")
        if work.get("annotation_batch_id") != BATCH_ID or work.get("phase") != PHASE:
            raise ValueError(f"{context}: worklist batch or phase mismatch")
        if work.get("adjudicator_id") != ADJUDICATOR_ID:
            raise ValueError(f"{context}: worklist adjudicator mismatch")
        _validate_decision(decision, work, context)


def _validate_decision(
    decision: dict[str, Any], work: dict[str, Any], context: str
) -> None:
    expected_keys = {
        "schema_version",
        "annotation_batch_id",
        "phase",
        "ordinal",
        "task_id",
        "adjudicator_id",
        "adjudication_task_sha256",
        "adjudication_status",
        "adjudicated_values",
        "evidence_pointers",
        "rationale",
        "prohibited_evidence_used",
        "protocol_deviation",
    }
    if set(decision) != expected_keys:
        missing = sorted(expected_keys - set(decision))
        extra = sorted(set(decision) - expected_keys)
        raise ValueError(f"{context}: key mismatch missing={missing} extra={extra}")
    immutable = {
        "schema_version": "repo480-rq2-phase2-adjudication-decision-v1",
        "annotation_batch_id": BATCH_ID,
        "phase": PHASE,
        "ordinal": work.get("ordinal"),
        "task_id": work.get("task_id"),
        "adjudicator_id": ADJUDICATOR_ID,
        "adjudication_task_sha256": sha256_json(work),
    }
    changed = [key for key, value in immutable.items() if decision.get(key) != value]
    if changed:
        raise ValueError(f"{context}: immutable field changed: {changed}")

    status = decision.get("adjudication_status")
    if status == "pending":
        raise ValueError(f"{context}: still pending")
    if status == "protocol_deviation":
        if decision.get("prohibited_evidence_used") is not True:
            raise ValueError(f"{context}: protocol deviation must mark prohibited evidence")
        _require_text(decision.get("protocol_deviation"), context, "protocol_deviation")
        return
    if status not in {"adjudicated", "unresolved"}:
        raise ValueError(f"{context}: invalid adjudication_status {status}")
    if decision.get("prohibited_evidence_used") is not False:
        raise ValueError(f"{context}: prohibited_evidence_used must be false")
    if decision.get("protocol_deviation") is not None:
        raise ValueError(f"{context}: protocol_deviation must be null")

    axes = work.get("disagree_axes")
    values = decision.get("adjudicated_values")
    if not isinstance(axes, list) or not axes:
        raise ValueError(f"{context}: worklist disagree_axes must be non-empty")
    if not isinstance(values, dict) or set(values) != set(axes):
        raise ValueError(f"{context}: adjudicated_values must match disagree_axes exactly")
    unresolved_count = 0
    for field in axes:
        if field not in ALLOWED_VALUES:
            raise ValueError(f"{context}: unsupported disagreement field {field}")
        value = values[field]
        if value == "unresolved":
            unresolved_count += 1
        elif value not in ALLOWED_VALUES[field]:
            raise ValueError(f"{context}: invalid value for {field}: {value}")
    if status == "adjudicated" and unresolved_count:
        raise ValueError(f"{context}: adjudicated row contains unresolved value")
    if status == "unresolved" and not unresolved_count:
        raise ValueError(f"{context}: unresolved row has no unresolved value")

    pointers = decision.get("evidence_pointers")
    if not isinstance(pointers, list) or not pointers:
        raise ValueError(f"{context}: evidence_pointers must be a non-empty list")
    for pointer in pointers:
        if not isinstance(pointer, str) or not pointer.strip():
            raise ValueError(f"{context}: evidence pointer must be non-empty text")
        if ":" not in pointer:
            raise ValueError(f"{context}: invalid evidence pointer {pointer!r}")
        prefix, locator = pointer.split(":", 1)
        if prefix not in ALLOWED_POINTER_PREFIXES or not locator.strip():
            raise ValueError(f"{context}: invalid evidence pointer {pointer!r}")
    _require_text(decision.get("rationale"), context, "rationale")


def _index(rows: list[dict[str, Any]], name: str) -> dict[str, dict[str, Any]]:
    result = {}
    for row in rows:
        task_id = row.get("task_id")
        if not isinstance(task_id, str) or not task_id:
            raise ValueError(f"{name}: row without task_id")
        if task_id in result:
            raise ValueError(f"{name}: duplicate task_id {task_id}")
        result[task_id] = row
    return result


def _require_text(value: Any, context: str, field: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{context}: {field} must be non-empty text")


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = []
    with path.open("r", encoding="utf-8") as handle:
        for line_no, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            value = json.loads(line)
            if not isinstance(value, dict):
                raise ValueError(f"{path}:{line_no}: expected JSON object")
            rows.append(value)
    return rows


def canonical_json_bytes(value: Any) -> bytes:
    return (
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
        + "\n"
    ).encode("utf-8")


def sha256_json(value: Any) -> str:
    return hashlib.sha256(canonical_json_bytes(value)).hexdigest()


if __name__ == "__main__":
    raise SystemExit(main())
