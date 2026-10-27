#!/usr/bin/env python3
"""Analyze repo480 raw agreement, adjudication, and evidence-policy transitions."""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from notpatch.canonical import canonical_json_bytes, sha256_file  # noqa: E402
from notpatch.schemas import ValidationError, validate_record  # noqa: E402
from summarize_agreement import _cohen_kappa  # noqa: E402


EXPECTED_TASK_COUNT = 480
RAW_ROLES = ("repo480_r1", "repo480_r2")
PRIMARY_LABELS = ("P0", "P1", "P2", "P3")
BINARY_LABELS = ("P0/P1", "P2/P3")
BLOCKERS = ("none", "U1", "U2", "U3", "U4", "U5", "U6", "U7")
DATA_QUALITY = ("Q0", "Q1", "Q2")
DISAGREEMENT_CATEGORIES = (
    "binary_boundary",
    "within_binary_primary_label",
    "multi_axis",
    "blocker_only",
    "direction_wording_only",
    "data_quality_only",
)
DIRECTION_EQUIVALENCE = (
    "equivalent",
    "partially_equivalent",
    "different",
    "not_assessable",
    "not_applicable",
)
FINAL_CONTROLLED_FIELDS = (
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
    "available_evidence_used_with_provenance",
    "retrieval_sufficiency",
    "missing_repository_evidence",
    "rationale",
)

DEFAULT_PATHS = {
    "r1": ROOT / "data/annotations/raw_labels/repo480_available_v1_r1.jsonl",
    "r2": ROOT / "data/annotations/raw_labels/repo480_available_v1_r2.jsonl",
    "decisions": ROOT
    / "data/annotations/adjudication_decisions/repo480_available_v1.jsonl",
    "final": ROOT / "data/annotations/adjudicated/repo480_available_v1.jsonl",
    "seed": ROOT
    / "data/annotations/adjudicated/swebench_full_prevalence_random_480_adjudicated.jsonl",
    "json_out": ROOT / "results/pilot/repo480_available_v1_transition_analysis.json",
    "markdown_out": ROOT / "results/pilot/repo480_available_v1_transition_analysis.md",
    "rows_out": ROOT / "results/pilot/repo480_available_v1_transition_rows.jsonl",
}
EXPECTED_SHA256 = {
    "r1": "5318d907093d44ee6eeeb7938c68373a8430bbb7a9e6e488a68a6685592e5a34",
    "r2": "cfd7daaf1f1256d6827e60eba78837cf21ff8d51e52aacb2b1e82ec319aca390",
    "decisions": "44b0742ead4eded1d4a0ca88c48211752f16fbd2c0ac43f616c78bb7b95a2472",
    "final": "98b33aabbd10b34bd093c4590c2f6c42476f999dd0e60e64794dbb0544f4e63d",
    "seed": "3c745afa68d4b283ddc64f0dd09a1da2b0d4e2e994fca8cb154634cf6165f23f",
}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--r1", type=Path, default=DEFAULT_PATHS["r1"])
    parser.add_argument("--r2", type=Path, default=DEFAULT_PATHS["r2"])
    parser.add_argument("--decisions", type=Path, default=DEFAULT_PATHS["decisions"])
    parser.add_argument("--final", type=Path, default=DEFAULT_PATHS["final"])
    parser.add_argument("--seed", type=Path, default=DEFAULT_PATHS["seed"])
    parser.add_argument("--json-out", type=Path, default=DEFAULT_PATHS["json_out"])
    parser.add_argument(
        "--markdown-out", type=Path, default=DEFAULT_PATHS["markdown_out"]
    )
    parser.add_argument("--rows-out", type=Path, default=DEFAULT_PATHS["rows_out"])
    args = parser.parse_args()

    inputs = {
        "r1": args.r1,
        "r2": args.r2,
        "decisions": args.decisions,
        "final": args.final,
        "seed": args.seed,
    }
    try:
        analysis, rows = analyze(inputs)
        markdown = build_markdown(analysis)
        _write_outputs(args.json_out, args.markdown_out, args.rows_out, analysis, rows, markdown)
    except (OSError, json.JSONDecodeError, ValidationError, ValueError) as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1

    print(
        "OK: wrote repo480 transition analysis "
        f"({analysis['integrity']['task_count']} tasks, "
        f"{analysis['integrity']['decision_count']} decisions)"
    )
    return 0


def analyze(inputs: dict[str, Path]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    input_metadata = _validate_frozen_inputs(inputs)
    r1_rows = _load_annotations(inputs["r1"], expected_annotator="repo480_r1")
    r2_rows = _load_annotations(inputs["r2"], expected_annotator="repo480_r2")
    final_rows = _load_annotations(inputs["final"], expected_annotator="adjudicated")
    seed_rows = _load_annotations(inputs["seed"], expected_annotator="adjudicated")
    decision_rows = _load_decisions(inputs["decisions"])
    for role, count in (
        ("r1", len(r1_rows)),
        ("r2", len(r2_rows)),
        ("decisions", len(decision_rows)),
        ("final", len(final_rows)),
        ("seed", len(seed_rows)),
    ):
        input_metadata[role]["row_count"] = count

    r1 = _index(r1_rows, "r1")
    r2 = _index(r2_rows, "r2")
    final = _index(final_rows, "final")
    seed = _index(seed_rows, "seed")
    decisions = _index(decision_rows, "decisions")
    task_ids = set(r1)
    if len(task_ids) != EXPECTED_TASK_COUNT:
        raise ValueError(f"r1 must contain {EXPECTED_TASK_COUNT} tasks")
    for name, indexed in (("r2", r2), ("final", final), ("seed", seed)):
        if set(indexed) != task_ids:
            raise ValueError(f"{name} task_id set does not match r1")

    pairs: dict[str, dict[str, Any]] = {}
    disagreement_tasks = set()
    for ordinal, left in enumerate(r1_rows, start=1):
        task_id = left["task_id"]
        right = r2[task_id]
        _validate_raw_linkage(left, right, task_id)
        axes = _disagree_axes(left, right)
        category = _category(axes) if axes else "exact_consensus"
        if axes:
            disagreement_tasks.add(task_id)
        pairs[task_id] = {
            "ordinal": ordinal,
            "axes": axes,
            "category": category,
        }

    if set(decisions) != disagreement_tasks:
        missing = sorted(disagreement_tasks - set(decisions))
        extra = sorted(set(decisions) - disagreement_tasks)
        raise ValueError(
            "decision task set must equal raw disagreement tasks; "
            f"missing={missing[:5]}, extra={extra[:5]}"
        )
    if len(decisions) != 466 or len(task_ids - disagreement_tasks) != 14:
        raise ValueError("expected 466 decision tasks and 14 exact-consensus tasks")

    for task_id, decision in decisions.items():
        pair = pairs[task_id]
        _validate_decision(decision, r1[task_id], pair, task_id)

    supplement_rows = []
    for left in r1_rows:
        task_id = left["task_id"]
        right = r2[task_id]
        final_record = final[task_id]
        seed_record = seed[task_id]
        decision = decisions.get(task_id)
        _validate_final_derivation(left, right, final_record, decision, task_id)
        supplement_rows.append(
            _build_supplement_row(
                pair=pairs[task_id],
                seed=seed_record,
                left=left,
                right=right,
                final=final_record,
                decision=decision,
            )
        )

    agreement = _build_agreement(r1, r2, r1_rows)
    disagreement = _build_disagreement_summary(pairs)
    adjudication = _build_adjudication_summary(decision_rows, supplement_rows)
    transition = _build_transition(seed, final, r1_rows)
    analysis = {
        "schema_version": "repo480-transition-analysis-v1",
        "analysis_id": "repo480-available-v1-transition",
        "packet_policy_id": "swebench-repo480-v1",
        "claim_scope": {
            "reports": "raw agreement, adjudication mechanics, and issue-packet to repository-evidence label transitions",
            "does_not_report": [
                "repository-level prevalence confidence interval",
                "RQ2 oracle-masking numerator or denominator",
                "causal effect of repository evidence alone",
            ],
        },
        "inputs": input_metadata,
        "integrity": {
            "task_count": len(task_ids),
            "task_sets_identical": True,
            "unique_task_ids_per_input": True,
            "decision_count": len(decisions),
            "exact_consensus_count": len(task_ids - disagreement_tasks),
            "decision_plus_consensus_count": len(decisions)
            + len(task_ids - disagreement_tasks),
            "decision_tasks_equal_raw_disagreement_tasks": True,
            "final_task_coverage_matches": True,
            "final_derivation_matches_decisions_and_consensus": True,
        },
        "raw_agreement": agreement,
        "raw_disagreement": disagreement,
        "adjudication": adjudication,
        "seed_to_repository_transition": transition,
    }
    _validate_totals(analysis, supplement_rows)
    return analysis, supplement_rows


def _validate_frozen_inputs(inputs: dict[str, Path]) -> dict[str, dict[str, Any]]:
    metadata = {}
    if set(inputs) != set(EXPECTED_SHA256):
        raise ValueError("input roles do not match the frozen analysis contract")
    for role in ("r1", "r2", "decisions", "final", "seed"):
        path = inputs[role]
        actual = sha256_file(path)
        expected = EXPECTED_SHA256[role]
        if actual != expected:
            raise ValueError(
                f"{role} SHA-256 mismatch: expected {expected}, found {actual}"
            )
        metadata[role] = {
            "path": _display_path(path),
            "sha256": actual,
            "frozen_sha256_verified": True,
        }
    return metadata


def _load_annotations(path: Path, *, expected_annotator: str) -> list[dict[str, Any]]:
    rows = _load_jsonl(path)
    for line_no, row in enumerate(rows, start=1):
        validate_record(row, "annotation")
        if row.get("annotator_id") != expected_annotator:
            raise ValueError(
                f"{path}:{line_no}: expected annotator_id={expected_annotator}"
            )
        if row.get("pass") != "available_only":
            raise ValueError(f"{path}:{line_no}: pass must be available_only")
    if len(rows) != EXPECTED_TASK_COUNT:
        raise ValueError(f"{path}: expected {EXPECTED_TASK_COUNT} rows, found {len(rows)}")
    return rows


def _load_decisions(path: Path) -> list[dict[str, Any]]:
    rows = _load_jsonl(path)
    for line_no, row in enumerate(rows, start=1):
        if row.get("schema_version") != "repo480-adjudication-decision-v1":
            raise ValueError(f"{path}:{line_no}: decision schema mismatch")
        if row.get("base_annotator") not in RAW_ROLES:
            raise ValueError(f"{path}:{line_no}: invalid base_annotator")
        if row.get("adjudication_status") not in {"adjudicated", "unresolved"}:
            raise ValueError(f"{path}:{line_no}: invalid adjudication_status")
        if not isinstance(row.get("overrides"), dict):
            raise ValueError(f"{path}:{line_no}: overrides must be an object")
        if row.get("direction_equivalence") not in DIRECTION_EQUIVALENCE:
            raise ValueError(f"{path}:{line_no}: invalid direction_equivalence")
        if row.get("posthoc_or_detector_evidence_used") is not False:
            raise ValueError(f"{path}:{line_no}: forbidden evidence flag is not false")
    if len(rows) != 466:
        raise ValueError(f"{path}: expected 466 rows, found {len(rows)}")
    return rows


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = []
    with path.open("r", encoding="utf-8") as handle:
        for line_no, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            value = json.loads(line)
            if not isinstance(value, dict):
                raise ValueError(f"{path}:{line_no}: expected object")
            rows.append(value)
    return rows


def _index(rows: list[dict[str, Any]], name: str) -> dict[str, dict[str, Any]]:
    indexed = {}
    for row in rows:
        task_id = row.get("task_id")
        if not isinstance(task_id, str) or not task_id:
            raise ValueError(f"{name}: row without task_id")
        if task_id in indexed:
            raise ValueError(f"{name}: duplicate task_id {task_id}")
        indexed[task_id] = row
    return indexed


def _validate_raw_linkage(
    left: dict[str, Any], right: dict[str, Any], task_id: str
) -> None:
    fields = (
        "task_id",
        "annotation_batch_id",
        "pass",
        "packet_policy_id",
        "packet_id",
        "packet_revision",
        "reviewer_view_hash",
        "registry_snapshot_sha256",
    )
    mismatches = [field for field in fields if left.get(field) != right.get(field)]
    if mismatches:
        raise ValueError(f"{task_id}: raw linkage mismatch: {mismatches}")


def _validate_decision(
    decision: dict[str, Any],
    left: dict[str, Any],
    pair: dict[str, Any],
    task_id: str,
) -> None:
    linkage = (
        "task_id",
        "packet_id",
        "packet_revision",
        "reviewer_view_hash",
        "registry_snapshot_sha256",
    )
    mismatches = [field for field in linkage if decision.get(field) != left.get(field)]
    if mismatches:
        raise ValueError(f"{task_id}: decision linkage mismatch: {mismatches}")
    if decision.get("ordinal") != pair["ordinal"]:
        raise ValueError(f"{task_id}: decision ordinal mismatch")
    if decision.get("disagree_axes") != pair["axes"]:
        raise ValueError(f"{task_id}: decision axes do not match raw records")
    if decision.get("disagreement_category") != pair["category"]:
        raise ValueError(f"{task_id}: decision category does not match raw records")


def _validate_final_derivation(
    left: dict[str, Any],
    right: dict[str, Any],
    final: dict[str, Any],
    decision: dict[str, Any] | None,
    task_id: str,
) -> None:
    if final.get("packet_id") != left.get("packet_id"):
        raise ValueError(f"{task_id}: final packet linkage mismatch")
    if decision is None:
        base = left
        expected_status = "adjudicated"
    else:
        base = left if decision["base_annotator"] == "repo480_r1" else right
        expected_status = decision["adjudication_status"]
    overrides = decision.get("overrides", {}) if decision else {}
    for field in FINAL_CONTROLLED_FIELDS:
        expected = overrides.get(field, base.get(field))
        if final.get(field) != expected:
            raise ValueError(f"{task_id}: final {field} does not match base/override")
    if final.get("adjudication_status") != expected_status:
        raise ValueError(f"{task_id}: final adjudication status mismatch")


def _disagree_axes(left: dict[str, Any], right: dict[str, Any]) -> list[str]:
    axes = []
    if _binary(left["primary_label"]) != _binary(right["primary_label"]):
        axes.append("binary_boundary")
    if left["primary_label"] != right["primary_label"]:
        axes.append("primary_label")
    if left.get("primary_blocker") != right.get("primary_blocker"):
        axes.append("primary_blocker")
    if left["data_quality"] != right["data_quality"]:
        axes.append("data_quality")
    if left.get("predicted_direction") != right.get("predicted_direction"):
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


def _build_agreement(
    r1: dict[str, dict[str, Any]],
    r2: dict[str, dict[str, Any]],
    ordered_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    task_ids = [row["task_id"] for row in ordered_rows]
    label_pairs = [(r1[item]["primary_label"], r2[item]["primary_label"]) for item in task_ids]
    binary_pairs = [(_binary(left), _binary(right)) for left, right in label_pairs]
    blocker_pairs = [
        (r1[item].get("primary_blocker"), r2[item].get("primary_blocker"))
        for item in task_ids
    ]
    data_quality_pairs = [
        (r1[item]["data_quality"], r2[item]["data_quality"]) for item in task_ids
    ]
    return {
        "axes": {
            "primary_label": _agreement_metric(label_pairs, PRIMARY_LABELS),
            "binary_label": _agreement_metric(binary_pairs, BINARY_LABELS),
            "primary_blocker": _agreement_metric(blocker_pairs, BLOCKERS),
            "data_quality": _agreement_metric(data_quality_pairs, DATA_QUALITY),
        },
        "primary_label_matrix": _matrix(label_pairs, PRIMARY_LABELS, "r1", "r2"),
        "binary_label_matrix": _matrix(binary_pairs, BINARY_LABELS, "r1", "r2"),
    }


def _agreement_metric(
    pairs: list[tuple[Any, Any]], preferred_categories: tuple[str, ...]
) -> dict[str, Any]:
    agree = sum(left == right for left, right in pairs)
    present = {_value_key(value) for pair in pairs for value in pair}
    categories = [item for item in preferred_categories if item in present]
    categories.extend(sorted(present - set(categories)))
    left_counts = Counter(_value_key(left) for left, _ in pairs)
    right_counts = Counter(_value_key(right) for _, right in pairs)
    return {
        "n": len(pairs),
        "agreement_count": agree,
        "disagreement_count": len(pairs) - agree,
        "observed_agreement": _round(agree / len(pairs)),
        "cohen_kappa": _round(_cohen_kappa(pairs)),
        "categories": categories,
        "r1_counts": {item: left_counts[item] for item in categories},
        "r2_counts": {item: right_counts[item] for item in categories},
    }


def _matrix(
    pairs: list[tuple[str, str]],
    labels: tuple[str, ...],
    row_axis: str,
    column_axis: str,
) -> dict[str, Any]:
    counts = {
        left: {right: 0 for right in labels}
        for left in labels
    }
    for left, right in pairs:
        counts[left][right] += 1
    return {
        "row_axis": row_axis,
        "column_axis": column_axis,
        "labels": list(labels),
        "counts": counts,
        "total": len(pairs),
    }


def _build_disagreement_summary(pairs: dict[str, dict[str, Any]]) -> dict[str, Any]:
    category_counts = Counter(pair["category"] for pair in pairs.values())
    axis_counts = Counter(
        axis for pair in pairs.values() for axis in pair["axes"]
    )
    return {
        "any_disagreement_count": sum(
            count for category, count in category_counts.items() if category != "exact_consensus"
        ),
        "exact_consensus_count": category_counts["exact_consensus"],
        "category_counts": {
            category: category_counts[category]
            for category in (*DISAGREEMENT_CATEGORIES, "exact_consensus")
        },
        "axis_counts": dict(sorted(axis_counts.items())),
    }


def _build_adjudication_summary(
    decisions: list[dict[str, Any]], rows: list[dict[str, Any]]
) -> dict[str, Any]:
    base_counts = Counter(row["base_annotator"] for row in decisions)
    equivalence_counts = Counter(row["direction_equivalence"] for row in decisions)
    status_counts = Counter(row["adjudication_status"] for row in decisions)
    by_category = {}
    for category in DISAGREEMENT_CATEGORIES:
        selected = [row for row in decisions if row["disagreement_category"] == category]
        category_base = Counter(row["base_annotator"] for row in selected)
        category_equivalence = Counter(row["direction_equivalence"] for row in selected)
        by_category[category] = {
            "decision_count": len(selected),
            "base_annotator_counts": {
                role: category_base[role] for role in RAW_ROLES
            },
            "direction_equivalence_counts": {
                value: category_equivalence[value] for value in DIRECTION_EQUIVALENCE
            },
        }
    source_counts = Counter(row["final_label_source"] for row in rows)
    return {
        "decision_count": len(decisions),
        "consensus_default_count": sum(row["raw_exact_consensus"] for row in rows),
        "decision_status_counts": dict(sorted(status_counts.items())),
        "base_annotator_counts": {role: base_counts[role] for role in RAW_ROLES},
        "direction_equivalence_counts": {
            value: equivalence_counts[value] for value in DIRECTION_EQUIVALENCE
        },
        "any_override_decision_count": sum(bool(row["overrides"]) for row in decisions),
        "primary_label_override_decision_count": sum(
            "primary_label" in row["overrides"] for row in decisions
        ),
        "final_label_source_counts": dict(sorted(source_counts.items())),
        "by_disagreement_category": by_category,
    }


def _build_transition(
    seed: dict[str, dict[str, Any]],
    final: dict[str, dict[str, Any]],
    ordered_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    task_ids = [row["task_id"] for row in ordered_rows]
    label_pairs = [(seed[item]["primary_label"], final[item]["primary_label"]) for item in task_ids]
    binary_pairs = [(_binary(left), _binary(right)) for left, right in label_pairs]
    label_directions = Counter(f"{left}->{right}" for left, right in label_pairs)
    binary_directions = Counter(f"{left}->{right}" for left, right in binary_pairs)
    movement = Counter()
    for (seed_label, final_label), (seed_binary, final_binary) in zip(
        label_pairs, binary_pairs, strict=True
    ):
        if seed_label == final_label:
            movement["unchanged_primary_label"] += 1
        elif seed_binary == final_binary:
            movement["within_binary_label_change"] += 1
        elif seed_binary == "P2/P3":
            movement["toward_P0/P1"] += 1
        else:
            movement["toward_P2/P3"] += 1
    return {
        "primary_label_matrix": _matrix(label_pairs, PRIMARY_LABELS, "seed", "final"),
        "binary_label_matrix": _matrix(binary_pairs, BINARY_LABELS, "seed", "final"),
        "primary_label_direction_counts": {
            f"{left}->{right}": label_directions[f"{left}->{right}"]
            for left in PRIMARY_LABELS
            for right in PRIMARY_LABELS
            if label_directions[f"{left}->{right}"]
        },
        "binary_direction_counts": {
            f"{left}->{right}": binary_directions[f"{left}->{right}"]
            for left in BINARY_LABELS
            for right in BINARY_LABELS
        },
        "movement_counts": {
            key: movement[key]
            for key in (
                "unchanged_primary_label",
                "within_binary_label_change",
                "toward_P0/P1",
                "toward_P2/P3",
            )
        },
        "primary_label_changed_count": sum(left != right for left, right in label_pairs),
        "binary_label_changed_count": sum(left != right for left, right in binary_pairs),
    }


def _build_supplement_row(
    *,
    pair: dict[str, Any],
    seed: dict[str, Any],
    left: dict[str, Any],
    right: dict[str, Any],
    final: dict[str, Any],
    decision: dict[str, Any] | None,
) -> dict[str, Any]:
    if decision is None:
        final_label_source = "exact_consensus_default_r1"
    elif "primary_label" in decision["overrides"]:
        final_label_source = "adjudication_primary_label_override"
    elif decision["base_annotator"] == "repo480_r1":
        final_label_source = "adjudication_base_r1"
    else:
        final_label_source = "adjudication_base_r2"
    seed_label = seed["primary_label"]
    r1_label = left["primary_label"]
    r2_label = right["primary_label"]
    final_label = final["primary_label"]
    return {
        "schema_version": "repo480-transition-row-v1",
        "ordinal": pair["ordinal"],
        "task_id": left["task_id"],
        "seed_label": seed_label,
        "r1_label": r1_label,
        "r2_label": r2_label,
        "final_label": final_label,
        "seed_binary_label": _binary(seed_label),
        "r1_binary_label": _binary(r1_label),
        "r2_binary_label": _binary(r2_label),
        "final_binary_label": _binary(final_label),
        "raw_disagreement": bool(pair["axes"]),
        "raw_exact_consensus": not pair["axes"],
        "disagree_axes": pair["axes"],
        "disagreement_category": pair["category"],
        "decision_present": decision is not None,
        "base_annotator": decision.get("base_annotator") if decision else None,
        "base_selected_r1": bool(decision and decision["base_annotator"] == "repo480_r1"),
        "base_selected_r2": bool(decision and decision["base_annotator"] == "repo480_r2"),
        "consensus_default_r1": decision is None,
        "direction_equivalence": decision.get("direction_equivalence") if decision else None,
        "final_primary_label_overridden": bool(
            decision and "primary_label" in decision["overrides"]
        ),
        "final_label_source": final_label_source,
        "final_matches_r1_label": final_label == r1_label,
        "final_matches_r2_label": final_label == r2_label,
        "primary_label_transition": f"{seed_label}->{final_label}",
        "binary_label_transition": f"{_binary(seed_label)}->{_binary(final_label)}",
        "primary_label_changed": seed_label != final_label,
        "binary_label_changed": _binary(seed_label) != _binary(final_label),
    }


def _validate_totals(analysis: dict[str, Any], rows: list[dict[str, Any]]) -> None:
    if len(rows) != EXPECTED_TASK_COUNT:
        raise ValueError("row supplement total is not 480")
    if [row["ordinal"] for row in rows] != list(range(1, EXPECTED_TASK_COUNT + 1)):
        raise ValueError("row supplement ordinals are not 1..480")
    for section in (
        analysis["raw_agreement"]["primary_label_matrix"],
        analysis["raw_agreement"]["binary_label_matrix"],
        analysis["seed_to_repository_transition"]["primary_label_matrix"],
        analysis["seed_to_repository_transition"]["binary_label_matrix"],
    ):
        matrix_total = sum(sum(row.values()) for row in section["counts"].values())
        if matrix_total != EXPECTED_TASK_COUNT or section["total"] != EXPECTED_TASK_COUNT:
            raise ValueError("matrix total is not 480")
    if sum(analysis["raw_disagreement"]["category_counts"].values()) != EXPECTED_TASK_COUNT:
        raise ValueError("raw disagreement category total is not 480")
    if sum(analysis["adjudication"]["base_annotator_counts"].values()) != 466:
        raise ValueError("adjudication base count total is not 466")
    if sum(analysis["adjudication"]["direction_equivalence_counts"].values()) != 466:
        raise ValueError("direction-equivalence total is not 466")
    if sum(analysis["seed_to_repository_transition"]["movement_counts"].values()) != EXPECTED_TASK_COUNT:
        raise ValueError("transition movement total is not 480")


def build_markdown(analysis: dict[str, Any]) -> str:
    integrity = analysis["integrity"]
    agreement = analysis["raw_agreement"]
    disagreement = analysis["raw_disagreement"]
    adjudication = analysis["adjudication"]
    transition = analysis["seed_to_repository_transition"]
    lines = [
        "# Repository-480 Agreement, Adjudication, and Transition Analysis",
        "",
        "- **Status:** `canonical-pilot`",
        "- **Analysis ID:** `repo480-available-v1-transition`",
        "- **Packet policy:** `swebench-repo480-v1`",
        "- **Rows:** 480",
        "",
        "이 보고서는 같은 480-task frame에서 두 available-only raw pass의 재현성, stable third-reviewer adjudication의 구성, issue-packet seed label에서 repository-evidence final label로의 전이를 고정한다. Raw rationale나 disagreement 전문은 포함하지 않으며 task-level 추적은 별도 row supplement가 담당한다.",
        "",
        "## Integrity and inputs",
        "",
        f"- Task set: {integrity['task_count']} unique tasks across r1, r2, seed, and final (`task_sets_identical=true`).",
        f"- Final construction: {integrity['decision_count']} decisions + {integrity['exact_consensus_count']} exact-consensus rows = {integrity['decision_plus_consensus_count']} final rows.",
        "- Decision task set equals the recomputed raw-disagreement task set, and every final scientific field matches its selected base plus explicit overrides (or r1 for exact consensus).",
        "",
        "| Input | Rows | SHA-256 |",
        "| --- | ---: | --- |",
    ]
    for role in ("r1", "r2", "decisions", "final", "seed"):
        item = analysis["inputs"][role]
        lines.append(
            f"| `{item['path']}` | {item['row_count']} | `{item['sha256']}` |"
        )

    lines.extend(
        [
            "",
            "## Raw r1-r2 agreement",
            "",
            "Agreement and Cohen's kappa are computed over all 480 paired raw records. Primary-blocker agreement treats the P0 null blocker as one category, matching the existing agreement summarizer's exact-value calculation.",
            "",
            "| Axis | Agree | Observed agreement | Cohen's kappa |",
            "| --- | ---: | ---: | ---: |",
        ]
    )
    for key, label in (
        ("primary_label", "P0--P3 primary label"),
        ("binary_label", "P0/P1 vs P2/P3"),
        ("primary_blocker", "Primary blocker"),
        ("data_quality", "Data quality"),
    ):
        metric = agreement["axes"][key]
        lines.append(
            f"| {label} | {metric['agreement_count']}/{metric['n']} | "
            f"{metric['observed_agreement']:.3f} | {metric['cohen_kappa']:.3f} |"
        )
    lines.extend(["", "### P0--P3 matrix", ""])
    lines.extend(_markdown_matrix(agreement["primary_label_matrix"]))
    lines.extend(["", "### Binary matrix", ""])
    lines.extend(_markdown_matrix(agreement["binary_label_matrix"]))

    lines.extend(
        [
            "",
            "## Raw disagreement and adjudication",
            "",
            "| Raw pair category | Tasks |",
            "| --- | ---: |",
        ]
    )
    for category in (*DISAGREEMENT_CATEGORIES, "exact_consensus"):
        lines.append(f"| `{category}` | {disagreement['category_counts'][category]} |")
    lines.extend(
        [
            "",
            f"The 466 non-consensus rows received explicit decisions; the remaining {adjudication['consensus_default_count']} rows use the exact-consensus default r1 record. Base selection was r1 for {adjudication['base_annotator_counts']['repo480_r1']} decisions and r2 for {adjudication['base_annotator_counts']['repo480_r2']}. {adjudication['any_override_decision_count']} decisions contain at least one override, including {adjudication['primary_label_override_decision_count']} primary-label overrides.",
            "",
            "| Category | Decisions | Base r1 | Base r2 | Equivalent | Partial | Different | Not assessable | N/A |",
            "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for category in DISAGREEMENT_CATEGORIES:
        item = adjudication["by_disagreement_category"][category]
        base = item["base_annotator_counts"]
        equivalence = item["direction_equivalence_counts"]
        lines.append(
            f"| `{category}` | {item['decision_count']} | {base['repo480_r1']} | "
            f"{base['repo480_r2']} | {equivalence['equivalent']} | "
            f"{equivalence['partially_equivalent']} | {equivalence['different']} | "
            f"{equivalence['not_assessable']} | {equivalence['not_applicable']} |"
        )
    lines.extend(
        [
            "",
            "Direction equivalence describes whether the raw predicted-direction wording points to the same repair direction on rows where that axis was compared. It is not another P0--P3 agreement statistic; `not_applicable` is required where direction wording was not a disagreement axis.",
            "",
            "## Issue-packet seed to repository-evidence final transition",
            "",
            "### P0--P3 matrix",
            "",
        ]
    )
    lines.extend(_markdown_matrix(transition["primary_label_matrix"]))
    lines.extend(["", "### Binary matrix", ""])
    lines.extend(_markdown_matrix(transition["binary_label_matrix"]))
    movement = transition["movement_counts"]
    lines.extend(
        [
            "",
            "| Transition summary | Tasks |",
            "| --- | ---: |",
            f"| Unchanged primary label | {movement['unchanged_primary_label']} |",
            f"| Changed within the same binary side | {movement['within_binary_label_change']} |",
            f"| P2/P3 seed to P0/P1 final | {movement['toward_P0/P1']} |",
            f"| P0/P1 seed to P2/P3 final | {movement['toward_P2/P3']} |",
            f"| Any P0--P3 label change | {transition['primary_label_changed_count']} |",
            f"| Any binary-boundary change | {transition['binary_label_changed_count']} |",
            "",
            "## Interpretation boundary",
            "",
            "- 이 artifact는 evidence-policy transition과 annotation/adjudication reproducibility를 기술한다. P0-4의 repository-level prevalence estimate, confidence interval, nested-120 audit 또는 sensitivity result를 대신하지 않는다.",
            "- Seed는 issue title/body에 기반한 pre-revision baseline이고 final은 frozen repository retrieval packet과 새 reviewer procedure에 기반한다. 따라서 전이는 evidence policy, reviewer 구성, adjudication procedure가 함께 달라진 관찰값이며 repository evidence만의 causal effect로 해석할 수 없다.",
            "- 이 단계에서는 benchmark solvability나 post-hoc oracle를 결합하지 않았으므로 RQ2 masking numerator/denominator를 제시하지 않는다.",
            "- Row supplement는 label, disagreement, transition, base-selection flag만 포함하며 raw rationale와 disagreement 전문은 복사하지 않는다.",
        ]
    )
    return "\n".join(lines) + "\n"


def _markdown_matrix(matrix: dict[str, Any]) -> list[str]:
    labels = matrix["labels"]
    lines = [
        f"Rows: `{matrix['row_axis']}`; columns: `{matrix['column_axis']}`.",
        "",
        "| | " + " | ".join(f"`{label}`" for label in labels) + " | Row total |",
        "| --- | " + " | ".join("---:" for _ in labels) + " | ---: |",
    ]
    for left in labels:
        values = [matrix["counts"][left][right] for right in labels]
        lines.append(
            f"| `{left}` | " + " | ".join(str(value) for value in values) + f" | {sum(values)} |"
        )
    column_totals = [
        sum(matrix["counts"][left][right] for left in labels) for right in labels
    ]
    lines.append(
        "| Column total | "
        + " | ".join(str(value) for value in column_totals)
        + f" | {sum(column_totals)} |"
    )
    return lines


def _write_outputs(
    json_out: Path,
    markdown_out: Path,
    rows_out: Path,
    analysis: dict[str, Any],
    rows: list[dict[str, Any]],
    markdown: str,
) -> None:
    for path in (json_out, markdown_out, rows_out):
        path.parent.mkdir(parents=True, exist_ok=True)
    json_out.write_bytes(canonical_json_bytes(analysis))
    markdown_out.write_text(markdown, encoding="utf-8")
    rows_out.write_bytes(b"".join(canonical_json_bytes(row) for row in rows))


def _display_path(path: Path) -> str:
    resolved = path.resolve()
    try:
        return resolved.relative_to(ROOT).as_posix()
    except ValueError:
        return resolved.as_posix()


def _value_key(value: Any) -> str:
    return "none" if value is None else str(value)


def _round(value: float) -> float:
    return round(value, 6)


if __name__ == "__main__":
    raise SystemExit(main())
