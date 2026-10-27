#!/usr/bin/env python3
"""Validate one completed repo480 RQ2 control Phase 2 return."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

BATCH_ID = "repo480_rq2_control_v1"
PHASE = "oracle_diagnostic"
EXPECTED_ROWS = 36
ALLOWED_REVIEWERS = {"repo480_nc_r1", "repo480_nc_r2"}
ALLOWED_STATUS = {"complete", "unresolved", "protocol_deviation"}
ALLOWED_IN_SET = {"yes", "no", "unclear"}
ALLOWED_REVEALED = {"yes", "partial", "no", "unclear"}
ALLOWED_TRINARY = {"yes", "no", "unclear"}
ALLOWED_SPACE = {"1", "2-3", "many", "unclear"}
ALLOWED_DATA_QUALITY = {"Q0", "Q1", "Q2"}
ALLOWED_POINTERS = {
    "patch",
    "test_patch",
    "fail_to_pass",
    "pass_to_pass",
    "hints_text",
}
TASK_KEYS = {
    "schema_version",
    "annotation_batch_id",
    "phase",
    "ordinal",
    "task_id",
    "annotator_id",
    "phase1_task_sha256",
    "phase1_judgment_sha256",
    "locked_phase1_judgment",
    "oracle_evidence_sha256",
    "oracle_evidence",
    "blinding",
}
ORACLE_KEYS = {
    "source_snapshot",
    "raw_row_index",
    "source_row_sha256",
    "repo",
    "base_commit",
    "environment_setup_commit",
    "version",
    "hints_text",
    "patch",
    "test_patch",
    "fail_to_pass",
    "pass_to_pass",
}
JUDGMENT_KEYS = {
    "schema_version",
    "annotation_batch_id",
    "phase",
    "ordinal",
    "task_id",
    "annotator_id",
    "phase2_task_sha256",
    "annotation_status",
    "oracle_direction_summary",
    "oracle_direction_in_candidate_set",
    "oracle_revealed_missing_evidence",
    "oracle_alternative_fix_exists",
    "available_evidence_unique_in_hindsight",
    "behavior_target_space_size",
    "data_quality",
    "benchmark_artifact_note",
    "oracle_evidence_pointers",
    "rationale",
    "prohibited_evidence_used",
    "protocol_deviation",
}
EXPECTED_BLINDING = {
    "arm_membership_hidden": True,
    "peer_phase1_judgment_hidden": True,
    "prior_patchability_label_hidden": True,
    "agent_identity_and_outcome_hidden": True,
    "oracle_evidence_revealed": True,
}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tasks", required=True, type=Path)
    parser.add_argument("--return-file", required=True, type=Path)
    parser.add_argument("--annotator-id", required=True, choices=sorted(ALLOWED_REVIEWERS))
    args = parser.parse_args()

    try:
        tasks = load_jsonl(args.tasks)
        returned = load_jsonl(args.return_file)
        validate_return(tasks, returned, args.annotator_id)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1
    print(f"OK: {args.annotator_id} Phase 2 return has {len(returned)} complete linked rows")
    return 0


def validate_return(
    tasks: list[dict[str, Any]],
    returned: list[dict[str, Any]],
    annotator_id: str,
) -> None:
    if len(tasks) != EXPECTED_ROWS or len(returned) != EXPECTED_ROWS:
        raise ValueError(f"tasks and return must each contain {EXPECTED_ROWS} rows")
    if annotator_id not in ALLOWED_REVIEWERS:
        raise ValueError(f"unsupported annotator_id {annotator_id}")

    for ordinal, (task, judgment) in enumerate(zip(tasks, returned, strict=True), start=1):
        context = f"row {ordinal} ({task.get('task_id')})"
        if task.get("ordinal") != ordinal or judgment.get("ordinal") != ordinal:
            raise ValueError(f"{context}: ordinal mismatch")
        _validate_task(task, annotator_id, context)
        if judgment.get("schema_version") != "repo480-rq2-control-phase2-judgment-v1":
            raise ValueError(f"{context}: judgment schema mismatch")
        if judgment.get("annotation_batch_id") != BATCH_ID or judgment.get("phase") != PHASE:
            raise ValueError(f"{context}: judgment batch or phase mismatch")
        if judgment.get("task_id") != task.get("task_id"):
            raise ValueError(f"{context}: task_id mismatch")
        if judgment.get("annotator_id") != annotator_id:
            raise ValueError(f"{context}: annotator_id mismatch")
        if judgment.get("phase2_task_sha256") != sha256_json(task):
            raise ValueError(f"{context}: Phase 2 task hash mismatch")
        _validate_judgment(judgment, context)


def _validate_task(task: dict[str, Any], annotator_id: str, context: str) -> None:
    if set(task) != TASK_KEYS:
        missing = sorted(TASK_KEYS - set(task))
        extra = sorted(set(task) - TASK_KEYS)
        raise ValueError(f"{context}: Phase 2 task key mismatch missing={missing} extra={extra}")
    if task.get("schema_version") != "repo480-rq2-control-phase2-task-v1":
        raise ValueError(f"{context}: task schema mismatch")
    if task.get("annotation_batch_id") != BATCH_ID or task.get("phase") != PHASE:
        raise ValueError(f"{context}: task batch or phase mismatch")
    if task.get("annotator_id") != annotator_id:
        raise ValueError(f"{context}: task annotator mismatch")

    locked = task.get("locked_phase1_judgment")
    if not isinstance(locked, dict):
        raise ValueError(f"{context}: locked Phase 1 judgment must be an object")
    if locked.get("task_id") != task.get("task_id") or locked.get("annotator_id") != annotator_id:
        raise ValueError(f"{context}: locked Phase 1 judgment linkage mismatch")
    if locked.get("phase1_task_sha256") != task.get("phase1_task_sha256"):
        raise ValueError(f"{context}: locked Phase 1 judgment task hash mismatch")
    if task.get("phase1_judgment_sha256") != sha256_json(locked):
        raise ValueError(f"{context}: locked Phase 1 judgment hash mismatch")

    oracle = task.get("oracle_evidence")
    if not isinstance(oracle, dict) or set(oracle) != ORACLE_KEYS:
        raise ValueError(f"{context}: oracle evidence structure mismatch")
    if task.get("oracle_evidence_sha256") != sha256_json(oracle):
        raise ValueError(f"{context}: oracle evidence hash mismatch")
    for field in ("patch", "test_patch"):
        _require_text(oracle.get(field), context, f"oracle {field}")
    for field in ("fail_to_pass", "pass_to_pass"):
        if not _string_list(oracle.get(field)) or not oracle[field]:
            raise ValueError(f"{context}: oracle {field} must be a non-empty string list")
    if task.get("blinding") != EXPECTED_BLINDING:
        raise ValueError(f"{context}: Phase 2 blinding contract mismatch")


def _validate_judgment(judgment: dict[str, Any], context: str) -> None:
    if set(judgment) != JUDGMENT_KEYS:
        missing = sorted(JUDGMENT_KEYS - set(judgment))
        extra = sorted(set(judgment) - JUDGMENT_KEYS)
        raise ValueError(f"{context}: key mismatch missing={missing} extra={extra}")

    status = judgment.get("annotation_status")
    if status == "pending":
        raise ValueError(f"{context}: still pending")
    if status not in ALLOWED_STATUS:
        raise ValueError(f"{context}: invalid annotation_status {status}")
    if status == "protocol_deviation":
        if judgment.get("prohibited_evidence_used") is not True:
            raise ValueError(f"{context}: protocol deviation must mark prohibited evidence")
        _require_text(judgment.get("protocol_deviation"), context, "protocol_deviation")
        return

    if judgment.get("prohibited_evidence_used") is not False:
        raise ValueError(f"{context}: prohibited_evidence_used must be false")
    if judgment.get("protocol_deviation") is not None:
        raise ValueError(f"{context}: protocol_deviation must be null")
    _require_text(judgment.get("oracle_direction_summary"), context, "oracle_direction_summary")
    _require_text(judgment.get("benchmark_artifact_note"), context, "benchmark_artifact_note")
    _require_text(judgment.get("rationale"), context, "rationale")

    allowed_fields = {
        "oracle_direction_in_candidate_set": ALLOWED_IN_SET,
        "oracle_revealed_missing_evidence": ALLOWED_REVEALED,
        "oracle_alternative_fix_exists": ALLOWED_TRINARY,
        "available_evidence_unique_in_hindsight": ALLOWED_TRINARY,
        "behavior_target_space_size": ALLOWED_SPACE,
        "data_quality": ALLOWED_DATA_QUALITY,
    }
    for field, allowed in allowed_fields.items():
        if judgment.get(field) not in allowed:
            raise ValueError(f"{context}: invalid {field}")

    pointers = judgment.get("oracle_evidence_pointers")
    if not _string_list(pointers) or not pointers:
        raise ValueError(f"{context}: oracle_evidence_pointers must be a non-empty string list")
    invalid = sorted(set(pointers) - ALLOWED_POINTERS)
    if invalid:
        raise ValueError(f"{context}: invalid oracle evidence pointers {invalid}")


def _string_list(value: Any) -> bool:
    return isinstance(value, list) and all(
        isinstance(item, str) and item.strip() for item in value
    )


def _require_text(value: Any, context: str, field: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{context}: {field} must be non-empty text")


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = []
    with path.open("r", encoding="utf-8") as handle:
        for line_no, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            row = json.loads(line)
            if not isinstance(row, dict):
                raise ValueError(f"{path}:{line_no}: expected JSON object")
            rows.append(row)
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
