#!/usr/bin/env python3
"""Validate one RR-L external-frame raw return (batch rrl_ext120_available_v1)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

BATCH_ID = "rrl_ext120_available_v1"
PACKET_POLICY_ID = "swebench-live-lite-ext120-v1"
REVIEWER_IDS = {"rrl_ext120_r1", "rrl_ext120_r2"}
WORKLIST_SCHEMA = "rrl-ext120-worklist-v1"
EXPECTED_ROWS = 120
PRIMARY_LABELS = {"P0", "P1", "P2", "P3"}
BLOCKERS = {"U1", "U2", "U3", "U4", "U5", "U6", "U7"}
DATA_QUALITY = {"Q0", "Q1", "Q2"}
DIFFICULTY = {"low", "medium", "high"}
CLARIFICATION_TARGETS = {
    "reproduction",
    "expected_behavior",
    "environment",
    "convention",
    "tradeoff",
    "dependency",
    "benchmark_artifact",
}
RETRIEVAL = {"sufficient", "insufficient", "unclear"}
EVIDENCE_SOURCES = {
    "issue_title",
    "issue_body",
    "public_comments_until_cutoff",
    "linked_artifacts",
    "retrieved_code",
    "visible_tests",
    "docs",
    "configs",
}
TEMPLATE_KEYS = {
    "component_or_function",
    "input_condition_or_trigger",
    "observable_behavior_change",
}
ANNOTATION_KEYS = {
    "primary_label",
    "primary_blocker",
    "secondary_blockers",
    "data_quality_blocker",
    "data_quality",
    "task_difficulty",
    "clarification_target",
    "predicted_direction",
    "predicted_direction_template",
    "candidate_directions",
    "missing_evidence_needed",
    "available_evidence_used",
    "retrieval_sufficiency",
    "missing_repository_evidence",
    "rationale",
    "available_evidence_used_with_provenance",
    "adjudication_status",
}
LOCKED_KEYS = (
    "schema_version",
    "ordinal",
    "task_id",
    "repo",
    "annotator_id",
    "annotation_batch_id",
    "pass",
    "packet_policy_id",
    "packet_id",
    "packet_revision",
    "reviewer_view_hash",
    "reviewer_view_ref",
    "archive_ref",
    "component_boundary_ref",
)
FORBIDDEN_KEYS = {
    "patch",
    "test_patch",
    "fail_to_pass",
    "pass_to_pass",
    "hints_text",
    "all_hints_text",
    "commit_url",
    "commit_urls",
    "test_cmds",
    "log_parser",
    "pull_number",
    "issue_numbers",
    "fix_diff",
    "hidden_tests",
    "later_outcome",
    "seed_label",
    "oracle_evidence",
    "oracle_gap",
    "detector_score",
    "judge_score",
    "random_rank",
    "prevalence_random_rank",
    "stratum",
    "fix_pr",
    "fix_pr_number",
}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--worklist", required=True, type=Path)
    parser.add_argument("--annotator-id", required=True, choices=sorted(REVIEWER_IDS))
    parser.add_argument(
        "--rowkeys",
        type=Path,
        default=Path("rrl_ext120_rowkeys_v1.json"),
    )
    args = parser.parse_args()
    try:
        rows = _load_jsonl(args.worklist)
        rowkeys = _read_object(args.rowkeys)
        validate_return(rows, rowkeys, args.annotator_id)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1
    print(f"OK: {args.annotator_id} return has {len(rows)} labeled linked rows")
    return 0


def validate_return(
    rows: list[dict[str, Any]], rowkeys: dict[str, Any], annotator_id: str
) -> None:
    expected = rowkeys.get("rows")
    if rowkeys.get("annotation_batch_id") != BATCH_ID or not isinstance(expected, list):
        raise ValueError("rowkeys file does not match this batch")
    if len(rows) != EXPECTED_ROWS or len(expected) != EXPECTED_ROWS:
        raise ValueError(f"worklist must contain {EXPECTED_ROWS} rows")
    for ordinal, (row, key) in enumerate(zip(rows, expected, strict=True), start=1):
        context = f"row {ordinal} ({row.get('task_id')})"
        _validate_linkage(row, key, ordinal, annotator_id, context)
        _validate_annotation(row.get("annotation_fields"), context)
    findings = _find_forbidden(rows)
    if findings:
        raise ValueError(f"return contains forbidden field(s): {findings[:3]}")


def _validate_linkage(
    row: dict[str, Any],
    key: dict[str, Any],
    ordinal: int,
    annotator_id: str,
    context: str,
) -> None:
    if set(row) != {*LOCKED_KEYS, "annotation_status", "protocol_deviation", "annotation_fields"}:
        raise ValueError(f"{context}: worklist key set was modified")
    if row.get("schema_version") != WORKLIST_SCHEMA:
        raise ValueError(f"{context}: schema mismatch")
    if row.get("ordinal") != ordinal or row.get("task_id") != key.get("task_id"):
        raise ValueError(f"{context}: row order or task id was modified")
    if row.get("reviewer_view_hash") != key.get("reviewer_view_hash"):
        raise ValueError(f"{context}: reviewer view hash was modified")
    if row.get("annotator_id") != annotator_id:
        raise ValueError(f"{context}: annotator_id mismatch")
    if row.get("annotation_batch_id") != BATCH_ID or row.get("pass") != "available_only":
        raise ValueError(f"{context}: batch or pass was modified")
    if row.get("packet_policy_id") != PACKET_POLICY_ID:
        raise ValueError(f"{context}: packet policy was modified")
    if row.get("annotation_status") != "labeled":
        raise ValueError(f"{context}: annotation_status must be 'labeled'")
    deviation = row.get("protocol_deviation")
    if deviation is not None and not (isinstance(deviation, str) and deviation.strip()):
        raise ValueError(f"{context}: protocol_deviation must be null or a non-empty string")


def _validate_annotation(fields: Any, context: str) -> None:
    if not isinstance(fields, dict) or set(fields) != ANNOTATION_KEYS:
        raise ValueError(f"{context}: annotation_fields key set was modified")
    label = fields["primary_label"]
    if label not in PRIMARY_LABELS:
        raise ValueError(f"{context}: primary_label must be one of P0..P3")
    decidable = label in {"P0", "P1"}

    blocker = fields["primary_blocker"]
    if label == "P0":
        if blocker is not None or fields["secondary_blockers"]:
            raise ValueError(f"{context}: P0 must not record blockers")
    elif blocker not in BLOCKERS:
        raise ValueError(f"{context}: {label} needs a primary blocker in U1..U7")
    secondary = fields["secondary_blockers"]
    if not isinstance(secondary, list) or not set(secondary) <= BLOCKERS:
        raise ValueError(f"{context}: secondary_blockers must be U1..U7")
    if len(set(secondary)) != len(secondary) or blocker in secondary:
        raise ValueError(f"{context}: secondary_blockers must be distinct and exclude the primary")

    if fields["data_quality"] not in DATA_QUALITY:
        raise ValueError(f"{context}: data_quality must be Q0, Q1 or Q2")
    if fields["data_quality_blocker"] is not None:
        raise ValueError(f"{context}: the available-only pass does not confirm D1")
    if fields["task_difficulty"] not in DIFFICULTY:
        raise ValueError(f"{context}: task_difficulty must be low, medium or high")

    target = fields["clarification_target"]
    if target is not None and target not in CLARIFICATION_TARGETS:
        raise ValueError(f"{context}: unknown clarification_target")
    if not decidable and target is None:
        raise ValueError(f"{context}: {label} needs a clarification_target")

    template = fields["predicted_direction_template"]
    if not isinstance(template, dict) or set(template) != TEMPLATE_KEYS:
        raise ValueError(f"{context}: predicted_direction_template key set was modified")
    direction = fields["predicted_direction"]
    if decidable:
        if not _nonempty_text(direction):
            raise ValueError(f"{context}: {label} needs a predicted_direction")
        if not all(_nonempty_text(value) for value in template.values()):
            raise ValueError(f"{context}: {label} needs all three template elements")
        if fields["candidate_directions"] or fields["missing_evidence_needed"]:
            raise ValueError(f"{context}: {label} must not record candidates or missing evidence")
    else:
        if direction is not None or any(value is not None for value in template.values()):
            raise ValueError(f"{context}: {label} keeps predicted_direction fields null")
        minimum = 2 if label == "P2" else 1
        candidates = fields["candidate_directions"]
        if not _text_list(candidates) or len(candidates) < minimum:
            raise ValueError(f"{context}: {label} needs at least {minimum} candidate direction(s)")
        if not _text_list(fields["missing_evidence_needed"]):
            raise ValueError(f"{context}: {label} needs missing_evidence_needed")

    used = fields["available_evidence_used"]
    if not _text_list(used) or not set(used) <= EVIDENCE_SOURCES:
        raise ValueError(f"{context}: available_evidence_used must be non-empty and known")
    retrieval = fields["retrieval_sufficiency"]
    if retrieval not in RETRIEVAL:
        raise ValueError(f"{context}: retrieval_sufficiency must be sufficient, insufficient or unclear")
    missing_repo = fields["missing_repository_evidence"]
    if retrieval == "sufficient":
        if missing_repo:
            raise ValueError(f"{context}: sufficient retrieval must not list missing evidence")
    elif not _text_list(missing_repo):
        raise ValueError(f"{context}: {retrieval} retrieval needs missing_repository_evidence")

    if not _nonempty_text(fields["rationale"], minimum=20):
        raise ValueError(f"{context}: rationale must be at least 20 characters")
    provenance = fields["available_evidence_used_with_provenance"]
    if not isinstance(provenance, list) or not all(
        _nonempty_text(item) for item in provenance
    ):
        raise ValueError(f"{context}: provenance entries must be non-empty strings")
    if fields["adjudication_status"] != "raw":
        raise ValueError(f"{context}: adjudication_status must stay 'raw'")


def _nonempty_text(value: Any, minimum: int = 1) -> bool:
    return isinstance(value, str) and len(value.strip()) >= minimum


def _text_list(value: Any) -> bool:
    return isinstance(value, list) and bool(value) and all(_nonempty_text(item) for item in value)


def _find_forbidden(value: Any, prefix: str = "") -> list[str]:
    findings: list[str] = []
    if isinstance(value, dict):
        for key, item in value.items():
            path = f"{prefix}.{key}" if prefix else key
            if key.lower() in FORBIDDEN_KEYS:
                findings.append(path)
            findings.extend(_find_forbidden(item, path))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            findings.extend(_find_forbidden(item, f"{prefix}[{index}]"))
    return findings


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    if not all(isinstance(row, dict) for row in rows):
        raise ValueError(f"{path}: every line must be a JSON object")
    return rows


def _read_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


if __name__ == "__main__":
    raise SystemExit(main())
