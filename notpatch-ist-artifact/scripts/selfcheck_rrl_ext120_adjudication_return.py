#!/usr/bin/env python3
"""Validate the RR-L ext120 adjudication return and derive post-adjudication labels."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

sys.dont_write_bytecode = True

HERE = Path(__file__).resolve().parent
RAW = {
    "rrl_ext120_r1": HERE.parent / "rrl_ext120_r1" / "rrl_ext120_r1_worklist.jsonl",
    "rrl_ext120_r2": HERE.parent / "rrl_ext120_r2" / "rrl_ext120_r2_worklist.jsonl",
}
DEFAULT_ANNOTATOR = "rrl_ext120_r1"
RAW_SELFCHECK = HERE.parent / "rrl_ext120_r1" / "rrl_ext120_selfcheck.py"
ROWKEYS = HERE.parent / "rrl_ext120_r1" / "rrl_ext120_rowkeys_v1.json"
WORKLIST = HERE / "rrl_ext120_adj_worklist.jsonl"
DECISIONS = HERE / "rrl_ext120_adj_decisions.jsonl"
WORKLIST_SCHEMA = "rrl-ext120-adjudication-worklist-v1"
DECISION_SCHEMA = "rrl-ext120-adjudication-decision-v1"
FINAL_SCHEMA = "rrl-ext120-post-adjudication-label-v1"
ADJUDICATOR_ID = "rrl_ext120_adj"

CATEGORY_PRIORITY = {
    "binary_boundary": 1,
    "within_binary_primary_label": 2,
    "multi_axis": 3,
    "blocker_only": 4,
    "direction_wording_only": 5,
    "data_quality_only": 6,
}
LINKAGE = (
    "ordinal",
    "task_id",
    "repo",
    "packet_id",
    "packet_revision",
    "reviewer_view_ref",
    "reviewer_view_hash",
    "archive_ref",
)
PAIR_FIELDS = (
    "task_id",
    "annotation_batch_id",
    "pass",
    "packet_policy_id",
    "packet_id",
    "packet_revision",
    "reviewer_view_hash",
    "reviewer_view_ref",
    "archive_ref",
)
ALLOWED_OVERRIDES = {
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
DIRECTION_EQUIVALENCE = {
    "equivalent",
    "partially_equivalent",
    "different",
    "not_assessable",
    "not_applicable",
}
DECISION_KEYS = {
    "schema_version",
    "adjudicator_id",
    "adjudication_status",
    *LINKAGE,
    "disagree_axes",
    "disagreement_category",
    "base_annotator",
    "overrides",
    "direction_equivalence",
    "shared_evidence_pointers",
    "decisive_missing_or_conflicting_evidence_pointers",
    "calibration_only",
    "calibration_only_reason",
    "boundary_reason",
    "resolution_notes",
    "protocol_deviation",
    "posthoc_or_detector_evidence_used",
}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write-worklist", action="store_true")
    parser.add_argument("--final-out", type=Path)
    args = parser.parse_args()
    try:
        raw = {role: _load_jsonl(path) for role, path in RAW.items()}
        _validate_raw(raw)
        worklist = build_worklist(raw)
        if args.write_worklist:
            _write_jsonl(WORKLIST, worklist)
        if _load_jsonl(WORKLIST) != worklist:
            raise ValueError("worklist does not match the two raw returns")
        decisions = _load_jsonl(DECISIONS)
        status = validate_decisions(worklist, decisions)
        final = build_final(raw, decisions)
        if args.final_out:
            _write_jsonl(args.final_out, final)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1
    labels = Counter(row["annotation_fields"]["primary_label"] for row in final)
    print(
        f"OK: {len(decisions)} decisions ({dict(status)}); "
        f"post-adjudication labels {dict(sorted(labels.items()))}"
    )
    return 0


def build_worklist(raw: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    rows = []
    for left, right in zip(raw["rrl_ext120_r1"], raw["rrl_ext120_r2"], strict=True):
        axes = _disagree_axes(left["annotation_fields"], right["annotation_fields"])
        if not axes:
            continue
        category = _category(axes)
        rows.append(
            {
                "schema_version": WORKLIST_SCHEMA,
                **{field: left[field] for field in LINKAGE},
                "disagree_axes": axes,
                "disagreement_category": category,
                "priority": CATEGORY_PRIORITY[category],
                "left": _view(left),
                "right": _view(right),
            }
        )
    rows.sort(key=lambda row: (row["priority"], row["ordinal"]))
    return rows


def validate_decisions(
    worklist: list[dict[str, Any]], decisions: list[dict[str, Any]]
) -> Counter[str]:
    if [row.get("task_id") for row in decisions] != [row["task_id"] for row in worklist]:
        raise ValueError("decision rows must follow the worklist order one-to-one")
    status: Counter[str] = Counter()
    for work, decision in zip(worklist, decisions, strict=True):
        task_id = work["task_id"]
        if set(decision) != DECISION_KEYS:
            raise ValueError(f"{task_id}: decision key set mismatch")
        if decision["schema_version"] != DECISION_SCHEMA:
            raise ValueError(f"{task_id}: decision schema mismatch")
        if decision["adjudicator_id"] != ADJUDICATOR_ID:
            raise ValueError(f"{task_id}: adjudicator_id mismatch")
        for field in (*LINKAGE, "disagree_axes", "disagreement_category"):
            if decision[field] != work[field]:
                raise ValueError(f"{task_id}: linkage field {field} changed")
        if decision["adjudication_status"] not in {"adjudicated", "unresolved"}:
            raise ValueError(f"{task_id}: status must be adjudicated or unresolved")
        status[decision["adjudication_status"]] += 1
        if decision["base_annotator"] not in RAW:
            raise ValueError(f"{task_id}: invalid base_annotator")
        if decision["posthoc_or_detector_evidence_used"] is not False:
            raise ValueError(f"{task_id}: forbidden evidence flag must stay false")
        _require_text(decision, "resolution_notes", task_id)
        deviation = decision["protocol_deviation"]
        if deviation is not None and not (isinstance(deviation, str) and deviation.strip()):
            raise ValueError(f"{task_id}: protocol_deviation must be null or text")
        overrides = decision["overrides"]
        if not isinstance(overrides, dict) or set(overrides) - ALLOWED_OVERRIDES:
            raise ValueError(f"{task_id}: overrides must use allowed judgment fields only")
        equivalence = decision["direction_equivalence"]
        if equivalence not in DIRECTION_EQUIVALENCE:
            raise ValueError(f"{task_id}: invalid direction_equivalence")
        has_direction = "predicted_direction_wording" in work["disagree_axes"]
        if has_direction == (equivalence == "not_applicable"):
            raise ValueError(f"{task_id}: direction_equivalence does not fit the axes")
        if "binary_boundary" in work["disagree_axes"]:
            _require_text(decision, "boundary_reason", task_id)
            if decision["calibration_only"] is True:
                _require_text(decision, "calibration_only_reason", task_id)
            elif decision["calibration_only"] is False:
                _require_list(decision, "shared_evidence_pointers", task_id)
                _require_list(
                    decision, "decisive_missing_or_conflicting_evidence_pointers", task_id
                )
            else:
                raise ValueError(f"{task_id}: calibration_only must be boolean")
        elif decision["calibration_only"] is not False:
            raise ValueError(f"{task_id}: calibration_only is only for binary rows")
    return status


def build_final(
    raw: dict[str, list[dict[str, Any]]], decisions: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    checker = _load_raw_checker()
    by_task = {row["task_id"]: row for row in decisions}
    final = []
    for left, right in zip(raw["rrl_ext120_r1"], raw["rrl_ext120_r2"], strict=True):
        decision = by_task.get(left["task_id"])
        if decision is None:
            base, overrides, status = DEFAULT_ANNOTATOR, {}, "exact_agreement"
        else:
            base = decision["base_annotator"]
            overrides = decision["overrides"]
            status = decision["adjudication_status"]
        record = left if base == "rrl_ext120_r1" else right
        fields = {**record["annotation_fields"], **overrides}
        checker._validate_annotation({**fields, "adjudication_status": "raw"}, left["task_id"])
        fields["adjudication_status"] = status
        final.append(
            {
                "schema_version": FINAL_SCHEMA,
                **{field: left[field] for field in LINKAGE},
                "annotation_batch_id": left["annotation_batch_id"],
                "pass": left["pass"],
                "packet_policy_id": left["packet_policy_id"],
                "base_annotator": base,
                "override_fields": sorted(overrides),
                "annotation_fields": fields,
            }
        )
    return final


def _validate_raw(raw: dict[str, list[dict[str, Any]]]) -> None:
    checker = _load_raw_checker()
    rowkeys = json.loads(ROWKEYS.read_text(encoding="utf-8"))
    for role, rows in raw.items():
        checker.validate_return(rows, rowkeys, role)
    for left, right in zip(raw["rrl_ext120_r1"], raw["rrl_ext120_r2"], strict=True):
        mismatch = [field for field in PAIR_FIELDS if left[field] != right[field]]
        if mismatch:
            raise ValueError(f"row {left['ordinal']}: raw-pass linkage mismatch {mismatch}")


def _load_raw_checker() -> Any:
    spec = importlib.util.spec_from_file_location("rrl_raw_selfcheck", RAW_SELFCHECK)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _view(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "annotator_id": row["annotator_id"],
        "protocol_deviation": row["protocol_deviation"],
        "raw_record_sha256": _sha256_json(row),
        **row["annotation_fields"],
    }


def _disagree_axes(left: dict[str, Any], right: dict[str, Any]) -> list[str]:
    axes = []
    if _binary(left["primary_label"]) != _binary(right["primary_label"]):
        axes.append("binary_boundary")
    if left["primary_label"] != right["primary_label"]:
        axes.append("primary_label")
    if left["primary_blocker"] != right["primary_blocker"]:
        axes.append("primary_blocker")
    if left["data_quality"] != right["data_quality"]:
        axes.append("data_quality")
    if left["predicted_direction"] != right["predicted_direction"]:
        axes.append("predicted_direction_wording")
    return axes


def _category(axes: list[str]) -> str:
    if "binary_boundary" in axes:
        return "binary_boundary"
    if "primary_label" in axes:
        return "within_binary_primary_label"
    if axes == ["primary_blocker"]:
        return "blocker_only"
    if axes == ["predicted_direction_wording"]:
        return "direction_wording_only"
    if axes == ["data_quality"]:
        return "data_quality_only"
    return "multi_axis"


def _binary(label: str) -> str:
    return "P0/P1" if label in {"P0", "P1"} else "P2/P3"


def _sha256_json(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _require_text(record: dict[str, Any], field: str, task_id: str) -> None:
    value = record.get(field)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{task_id}: {field} must be non-empty text")


def _require_list(record: dict[str, Any], field: str, task_id: str) -> None:
    value = record.get(field)
    if not isinstance(value, list) or not value:
        raise ValueError(f"{task_id}: {field} must be a non-empty array")
    if any(not isinstance(item, str) or not item.strip() for item in value):
        raise ValueError(f"{task_id}: {field} must contain non-empty strings")


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    if not all(isinstance(row, dict) for row in rows):
        raise ValueError(f"{path}: every line must be a JSON object")
    return rows


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    text = "".join(
        json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
        for row in rows
    )
    path.write_text(text, encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
