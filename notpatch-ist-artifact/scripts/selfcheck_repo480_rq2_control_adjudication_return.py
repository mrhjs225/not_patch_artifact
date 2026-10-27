#!/usr/bin/env python3
"""Validate a completed repo480 RQ2-control adjudication return."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any


BATCH_ID = "repo480_rq2_control_v1"
PHASE = "oracle_diagnostic_adjudication"
ADJUDICATOR_ID = "repo480_nc_adj"
EXPECTED_ROWS = 13
ALLOWED_VALUES = {
    "oracle_direction_in_candidate_set": {"yes", "no", "unclear"},
    "oracle_revealed_missing_evidence": {"yes", "partial", "no", "unclear"},
    "oracle_alternative_fix_exists": {"yes", "no", "unclear"},
    "available_evidence_unique_in_hindsight": {"yes", "no", "unclear"},
    "behavior_target_space_size": {"1", "2-3", "many", "unclear"},
    "data_quality": {"Q0", "Q1", "Q2"},
}
ALLOWED_POINTER_PREFIXES = {
    "phase2_r1_tasks",
    "phase2_r2_tasks",
    "phase2_r1_return",
    "phase2_r2_return",
}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--worklist", type=Path, default=Path("repo480_rq2_control_adjudication_worklist.jsonl")
    )
    parser.add_argument(
        "--return-file",
        type=Path,
        default=Path("repo480_rq2_control_adjudication_return.jsonl"),
    )
    args = parser.parse_args()
    try:
        validate_return(load_jsonl(args.worklist), load_jsonl(args.return_file))
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1
    print(f"OK: {EXPECTED_ROWS} completed RQ2-control adjudication decisions")
    return 0


def validate_return(
    worklist: list[dict[str, Any]], returned: list[dict[str, Any]]
) -> None:
    if len(worklist) != EXPECTED_ROWS or len(returned) != EXPECTED_ROWS:
        raise ValueError(f"worklist and return must each contain {EXPECTED_ROWS} rows")
    returned_by_task = _index(returned, "return")
    if set(_index(worklist, "worklist")) != set(returned_by_task):
        raise ValueError("return task set does not match worklist")
    for work in worklist:
        _validate_decision(returned_by_task[work["task_id"]], work)


def _validate_decision(decision: dict[str, Any], work: dict[str, Any]) -> None:
    task_id = work["task_id"]
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
        raise ValueError(f"{task_id}: decision key set changed")
    immutable = {
        "schema_version": "repo480-rq2-control-adjudication-decision-v1",
        "annotation_batch_id": BATCH_ID,
        "phase": PHASE,
        "ordinal": work["ordinal"],
        "task_id": task_id,
        "adjudicator_id": ADJUDICATOR_ID,
        "adjudication_task_sha256": sha256_json(work),
    }
    changed = [key for key, value in immutable.items() if decision.get(key) != value]
    if changed:
        raise ValueError(f"{task_id}: immutable field changed: {changed}")

    status = decision.get("adjudication_status")
    if status == "pending":
        raise ValueError(f"{task_id}: still pending")
    if status == "protocol_deviation":
        if decision.get("prohibited_evidence_used") is not True:
            raise ValueError(f"{task_id}: protocol deviation must mark prohibited evidence")
        _text(decision.get("protocol_deviation"), task_id, "protocol_deviation")
        return
    if status not in {"adjudicated", "unresolved"}:
        raise ValueError(f"{task_id}: invalid adjudication_status")
    if decision.get("prohibited_evidence_used") is not False:
        raise ValueError(f"{task_id}: prohibited_evidence_used must be false")
    if decision.get("protocol_deviation") is not None:
        raise ValueError(f"{task_id}: protocol_deviation must be null")

    axes = work["disagree_axes"]
    values = decision.get("adjudicated_values")
    if not isinstance(values, dict) or set(values) != set(axes):
        raise ValueError(f"{task_id}: adjudicated_values must match disagree_axes")
    unresolved = 0
    for field in axes:
        if field not in ALLOWED_VALUES:
            raise ValueError(f"{task_id}: unsupported disagreement field {field}")
        value = values[field]
        if value == "unresolved":
            unresolved += 1
        elif value not in ALLOWED_VALUES[field]:
            raise ValueError(f"{task_id}: invalid value for {field}: {value}")
    if status == "adjudicated" and unresolved:
        raise ValueError(f"{task_id}: adjudicated row contains unresolved value")
    if status == "unresolved" and not unresolved:
        raise ValueError(f"{task_id}: unresolved row has no unresolved value")

    pointers = decision.get("evidence_pointers")
    if not isinstance(pointers, list) or not pointers:
        raise ValueError(f"{task_id}: evidence_pointers must be non-empty")
    for pointer in pointers:
        if not isinstance(pointer, str) or ":" not in pointer:
            raise ValueError(f"{task_id}: invalid evidence pointer")
        prefix, locator = pointer.split(":", 1)
        if prefix not in ALLOWED_POINTER_PREFIXES or not locator.strip():
            raise ValueError(f"{task_id}: invalid evidence pointer {pointer!r}")
    _text(decision.get("rationale"), task_id, "rationale")


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


def _text(value: Any, task_id: str, field: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{task_id}: {field} must be non-empty text")


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as handle:
        rows = [json.loads(line) for line in handle if line.strip()]
    if not rows:
        raise ValueError(f"{path} is empty")
    return rows


def canonical_json_bytes(value: Any) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
    ).encode()


def sha256_json(value: Any) -> str:
    return hashlib.sha256(canonical_json_bytes(value)).hexdigest()


if __name__ == "__main__":
    raise SystemExit(main())
