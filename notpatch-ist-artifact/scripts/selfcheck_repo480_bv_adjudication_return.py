#!/usr/bin/env python3
"""Standalone structural self-check for a repo480 boundary-validation adjudication return."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


BATCH_ID = "repo480_boundary_validation_v1"
ADJUDICATOR_ID = "repo480_bv_adj"
RAW_ROLES = {"repo480_bv_r1", "repo480_bv_r2"}
LINKAGE_FIELDS = (
    "queue_position",
    "ordinal",
    "task_id",
    "repo",
    "packet_id",
    "packet_revision",
    "reviewer_view_ref",
    "reviewer_view_hash",
    "archive_ref",
    "disagree_axes",
    "disagreement_category",
)
DIRECTION_EQUIVALENCE = {
    "equivalent",
    "partially_equivalent",
    "different",
    "not_assessable",
    "not_applicable",
}
OVERRIDABLE_FIELDS = {
    "primary_label",
    "primary_blocker",
    "secondary_blockers",
    "data_quality",
    "data_quality_blocker",
    "task_difficulty",
    "clarification_target",
    "predicted_direction",
    "predicted_direction_template",
    "candidate_directions",
    "missing_evidence_needed",
    "available_evidence_used",
    "available_evidence_used_with_provenance",
    "retrieval_sufficiency",
    "missing_repository_evidence",
    "rationale",
}
PRIMARY_LABELS = {"P0", "P1", "P2", "P3"}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--worklist", default="repo480_bv_adjudication_worklist.jsonl", type=Path)
    parser.add_argument(
        "--decisions", default="repo480_bv_adjudication_decisions.jsonl", type=Path
    )
    args = parser.parse_args()
    try:
        worklist = _load(args.worklist)
        decisions = _load(args.decisions)
        validate_return(worklist, decisions)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1
    print(f"OK: {len(decisions)} completed adjudication decisions")
    return 0


def validate_return(worklist: list[dict[str, Any]], decisions: list[dict[str, Any]]) -> None:
    expected = _index(worklist, "worklist")
    returned = _index(decisions, "decisions")
    if set(expected) != set(returned):
        raise ValueError("decision task set does not match the worklist")
    if [row["task_id"] for row in worklist] != [row["task_id"] for row in decisions]:
        raise ValueError("decision row order does not match the worklist")
    for task_id, work_row in expected.items():
        decision = returned[task_id]
        _validate_row(work_row, decision, task_id)


def _validate_row(work_row: dict[str, Any], decision: dict[str, Any], task_id: str) -> None:
    if decision.get("schema_version") != "repo480-bv-adjudication-decision-v1":
        raise ValueError(f"{task_id}: schema_version changed")
    if decision.get("annotation_batch_id") != BATCH_ID:
        raise ValueError(f"{task_id}: annotation_batch_id changed")
    if decision.get("adjudicator_id") != ADJUDICATOR_ID:
        raise ValueError(f"{task_id}: adjudicator_id changed")
    changed = [field for field in LINKAGE_FIELDS if decision.get(field) != work_row.get(field)]
    if changed:
        raise ValueError(f"{task_id}: immutable field changed: {changed}")
    if decision.get("adjudication_status") not in {"adjudicated", "unresolved"}:
        raise ValueError(f"{task_id}: decision is still pending")
    if decision.get("base_annotator") not in RAW_ROLES:
        raise ValueError(f"{task_id}: base_annotator is invalid")
    if decision.get("posthoc_or_detector_evidence_used") is not False:
        raise ValueError(f"{task_id}: forbidden-evidence flag must be false")
    deviation = decision.get("protocol_deviation")
    if deviation is not None and not (isinstance(deviation, str) and deviation.strip()):
        raise ValueError(f"{task_id}: protocol_deviation must be null or a non-empty string")
    _validate_overrides(decision, task_id)
    _text(decision, "resolution_notes", task_id)

    equivalence = decision.get("direction_equivalence")
    if equivalence not in DIRECTION_EQUIVALENCE:
        raise ValueError(f"{task_id}: direction_equivalence is invalid")
    direction_axis = "predicted_direction_wording" in work_row["disagree_axes"]
    if direction_axis == (equivalence == "not_applicable"):
        raise ValueError(f"{task_id}: direction_equivalence does not match its axis")

    if "binary_boundary" in work_row["disagree_axes"]:
        _text(decision, "boundary_reason", task_id)
        if decision.get("calibration_only") is True:
            _text(decision, "calibration_only_reason", task_id)
        elif decision.get("calibration_only") is False:
            _strings(decision, "shared_evidence_pointers", task_id)
            _strings(decision, "decisive_missing_or_conflicting_evidence_pointers", task_id)
        else:
            raise ValueError(f"{task_id}: calibration_only must be boolean")
    elif decision.get("calibration_only") is not False:
        raise ValueError(f"{task_id}: calibration_only is only for binary rows")


def _validate_overrides(decision: dict[str, Any], task_id: str) -> None:
    overrides = decision.get("overrides")
    if not isinstance(overrides, dict):
        raise ValueError(f"{task_id}: overrides must be an object")
    unknown = sorted(set(overrides) - OVERRIDABLE_FIELDS)
    if unknown:
        raise ValueError(f"{task_id}: overrides contain unknown field(s) {unknown}")
    if "primary_label" in overrides and overrides["primary_label"] not in PRIMARY_LABELS:
        raise ValueError(f"{task_id}: overridden primary_label is invalid")


def _index(rows: list[dict[str, Any]], name: str) -> dict[str, dict[str, Any]]:
    index: dict[str, dict[str, Any]] = {}
    for row in rows:
        task_id = row.get("task_id")
        if not isinstance(task_id, str) or not task_id:
            raise ValueError(f"{name}: row without task_id")
        if task_id in index:
            raise ValueError(f"{name}: duplicate task_id {task_id}")
        index[task_id] = row
    return index


def _text(row: dict[str, Any], field: str, task_id: str) -> None:
    value = row.get(field)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{task_id}: {field} must be non-empty")


def _strings(row: dict[str, Any], field: str, task_id: str) -> None:
    value = row.get(field)
    if not isinstance(value, list) or not value:
        raise ValueError(f"{task_id}: {field} must be a non-empty list")
    if not all(isinstance(item, str) and item.strip() for item in value):
        raise ValueError(f"{task_id}: {field} must contain non-empty strings")


def _load(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as handle:
        rows = [json.loads(line) for line in handle if line.strip()]
    if not rows:
        raise ValueError(f"{path} is empty")
    return rows


if __name__ == "__main__":
    raise SystemExit(main())
