#!/usr/bin/env python3
"""Accept repo480 RQ2 adjudication and derive the final masking result."""

from __future__ import annotations

import argparse
import json
import math
import shutil
import sys
from collections import Counter
from pathlib import Path
from statistics import NormalDist
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from notpatch.canonical import (  # noqa: E402
    canonical_json_bytes,
    sha256_bytes,
    sha256_file,
)
from scripts.selfcheck_repo480_rq2_adjudication_return import (  # noqa: E402
    validate_return,
)


BATCH_ID = "repo480_rq2_masking_v1"
PACKET_POLICY_ID = "swebench-repo480-v1"
EXPECTED_ROWS = 12
CONFIDENCE_LEVEL = 0.95
CONTROLLED_FIELDS = (
    "oracle_direction_in_candidate_set",
    "oracle_revealed_missing_evidence",
    "oracle_alternative_fix_exists",
    "available_evidence_unique_in_hindsight",
    "behavior_target_space_size",
    "data_quality",
)

DEFAULT_PATHS = {
    "phase1_tasks": ROOT
    / "data/annotations/worklists/repo480_rq2_phase1_tasks_v1.jsonl",
    "r1": ROOT
    / "data/annotations/oracle_gap/repo480_rq2_panel/repo480_rq2_phase2_r1.jsonl",
    "r2": ROOT
    / "data/annotations/oracle_gap/repo480_rq2_panel/repo480_rq2_phase2_r2.jsonl",
    "returns_manifest": ROOT
    / "data/manifests/generated/repo480_rq2_phase2_returns_manifest_v1.json",
    "raw_agreement": ROOT
    / "results/pilot/repo480_rq2_phase2_raw_agreement_v1.json",
    "worklist": ROOT
    / "data/annotations/worklists/repo480_rq2_phase2_adjudication_worklist_v1.jsonl",
    "adjudication_return": ROOT
    / "data/annotations/oracle_gap/repo480_rq2_panel/repo480_rq2_phase2_adjudication.jsonl",
    "outcome_join": ROOT
    / "data/processed/oracle_masking/repo480_rq2_outcome_join_v1.json",
    "canonical_out": ROOT
    / "data/annotations/oracle_gap/repo480_rq2_panel/repo480_rq2_phase2_adjudication.jsonl",
    "manifest_out": ROOT
    / "data/manifests/generated/repo480_rq2_adjudication_manifest_v1.json",
    "json_out": ROOT / "results/pilot/repo480_rq2_masking_analysis_v1.json",
    "markdown_out": ROOT / "results/pilot/repo480_rq2_masking_analysis_v1.md",
    "rows_out": ROOT / "results/pilot/repo480_rq2_masking_rows_v1.jsonl",
    "tex_out": ROOT / "paper/generated/repo480_rq2_masking_summary.tex",
    "rows_tex_out": ROOT / "paper/generated/repo480_rq2_masking_rows.tex",
    "run_pool_tex_out": ROOT / "paper/generated/repo480_rq2_run_pool.tex",
}

EXPECTED_SHA256 = {
    "phase1_tasks": "86d5cbe4a07e5f2c8f4f4c0b43dd7fdf4b030a7f61c691d9d5c174ed0714280d",
    "r1": "8401c18c6b2e28abe1725e3f02d6ee17ff88ea337b6f3832658811f988323237",
    "r2": "2c22b7c950ce6b38866cd9711b59f9137014839f8ca5f189515de7f54d80d4c7",
    "returns_manifest": "2f1b4c6f2176f2c22821fbb12d52ec4b4df5278da7d4fec2862e6ac57022811d",
    "raw_agreement": "f40cb775c791a41dea221fd9600ffcab475f0b9da09c8ada817d037fb2741f75",
    "worklist": "ef8b8b2b2bcdc8304a5f091353ea6bbda5957de3bad26ccdf284cc485c821057",
    "adjudication_return": "dd37f5c7933a43cf311835782963e783b0a4bbe347b0865fcb659439025532f5",
    "outcome_join": "cf64da3a0e5211c98af2b3e523f5846a14a6719c5ed054bd1d05a6bf4307c9ef",
}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    for name in (
        "phase1_tasks",
        "r1",
        "r2",
        "returns_manifest",
        "raw_agreement",
        "worklist",
        "adjudication_return",
        "outcome_join",
        "canonical_out",
        "manifest_out",
        "json_out",
        "markdown_out",
        "rows_out",
        "tex_out",
       "rows_tex_out",
        "run_pool_tex_out",
    ):
        parser.add_argument(
            f"--{name.replace('_', '-')}", type=Path, default=DEFAULT_PATHS[name]
        )
    args = parser.parse_args()
    inputs = {
        name: getattr(args, name)
        for name in (
            "phase1_tasks",
            "r1",
            "r2",
            "returns_manifest",
            "raw_agreement",
            "worklist",
            "adjudication_return",
            "outcome_join",
        )
    }

    try:
        input_metadata = _validate_frozen_inputs(inputs)
        phase1 = _load_jsonl(inputs["phase1_tasks"])
        r1 = _load_jsonl(inputs["r1"])
        r2 = _load_jsonl(inputs["r2"])
        worklist = _load_jsonl(inputs["worklist"])
        decisions = _load_jsonl(inputs["adjudication_return"])
        returns_manifest = _read_object(inputs["returns_manifest"])
        raw_agreement = _read_object(inputs["raw_agreement"])
        outcome_join = _read_object(inputs["outcome_join"])
        _validate_inputs(
            phase1,
            r1,
            r2,
            worklist,
            decisions,
            returns_manifest,
            raw_agreement,
            outcome_join,
        )
        _preserve_exact(
            inputs["adjudication_return"],
            args.canonical_out,
            EXPECTED_SHA256["adjudication_return"],
        )
        manifest = _build_manifest(
            input_metadata, args.canonical_out, worklist, decisions
        )
        manifest_bytes = canonical_json_bytes(manifest)
        analysis, rows = _analyze(
            phase1,
            r1,
            r2,
            worklist,
            decisions,
            outcome_join,
            input_metadata,
            args.manifest_out,
            sha256_bytes(manifest_bytes),
            args.canonical_out,
        )
        outputs = {
            args.manifest_out: manifest_bytes,
            args.json_out: canonical_json_bytes(analysis),
            args.markdown_out: _build_markdown(analysis).encode("utf-8"),
            args.rows_out: b"".join(canonical_json_bytes(row) for row in rows),
            args.tex_out: _build_tex(analysis).encode("utf-8"),
           args.rows_tex_out: _build_rows_tex(rows).encode("utf-8"),
            args.run_pool_tex_out: _build_run_pool_tex(outcome_join).encode("utf-8"),
        }
        for path, content in outputs.items():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1

    primary = analysis["primary_strict_masking"]
    conservative = analysis["sensitivity"]["dispute_as_nonmasked"]
    print(
        "OK: wrote repo480 RQ2 masking analysis "
        f"(primary={primary['count']}/{primary['denominator']}, "
        f"dispute-as-nonmasked={conservative['count']}/"
        f"{conservative['denominator']})"
    )
    return 0


def _validate_frozen_inputs(inputs: dict[str, Path]) -> dict[str, dict[str, Any]]:
    if set(inputs) != set(EXPECTED_SHA256):
        raise ValueError("input roles do not match the frozen RQ2 contract")
    metadata = {}
    for name, path in inputs.items():
        actual = sha256_file(path)
        expected = EXPECTED_SHA256[name]
        if actual != expected:
            raise ValueError(
                f"{name} SHA-256 mismatch: expected {expected}, found {actual}"
            )
        metadata[name] = {"ref": _artifact_ref(path), "sha256": actual}
    return metadata


def _validate_inputs(
    phase1: list[dict[str, Any]],
    r1: list[dict[str, Any]],
    r2: list[dict[str, Any]],
    worklist: list[dict[str, Any]],
    decisions: list[dict[str, Any]],
    returns_manifest: dict[str, Any],
    raw_agreement: dict[str, Any],
    outcome_join: dict[str, Any],
) -> None:
    if not all(len(rows) == EXPECTED_ROWS for rows in (phase1, r1, r2)):
        raise ValueError("Phase 1 and both Phase 2 returns must each contain 12 rows")
    validate_return(worklist, decisions)
    if any(row.get("adjudication_status") != "adjudicated" for row in decisions):
        raise ValueError("every adjudication row must be adjudicated")
    task_order = [row["task_id"] for row in phase1]
    if task_order != [row.get("task_id") for row in r1]:
        raise ValueError("r1 task order does not match Phase 1")
    if task_order != [row.get("task_id") for row in r2]:
        raise ValueError("r2 task order does not match Phase 1")
    if len(set(task_order)) != EXPECTED_ROWS:
        raise ValueError("Phase 1 task IDs must be unique")

    if returns_manifest.get("schema_version") != "repo480-rq2-phase2-returns-manifest-v1":
        raise ValueError("Phase 2 returns manifest schema mismatch")
    gate = returns_manifest.get("acceptance_gate", {})
    if not all(
        gate.get(field) is True
        for field in (
            "adjudication_release_allowed",
            "all_rows_complete",
            "immutable_linkage_passed",
            "raw_returns_preserved_exactly",
            "selfcheck_passed",
        )
    ):
        raise ValueError("Phase 2 acceptance gate is not closed")
    if raw_agreement.get("schema_version") != "repo480-rq2-phase2-raw-agreement-v1":
        raise ValueError("raw agreement schema mismatch")
    if raw_agreement.get("disagreement_queue", {}).get("task_ids") != [
        row["task_id"] for row in worklist
    ]:
        raise ValueError("raw agreement disagreement queue does not match worklist")
    if raw_agreement.get("strict_call_agreement", {}).get("both_yes_count") != 12:
        raise ValueError("expected both raw strict calls to be yes for all 12 rows")

    if outcome_join.get("schema_version") != "repo480-rq2-outcome-join-v1":
        raise ValueError("outcome join schema mismatch")
    if outcome_join.get("packet_policy_id") != PACKET_POLICY_ID:
        raise ValueError("outcome join packet policy mismatch")
    solved_ids = {
        row["task_id"]
        for row in outcome_join.get("rows", [])
        if row.get("benchmark_solved") is True
    }
    if solved_ids != set(task_order):
        raise ValueError("Phase 2 task set does not match the solved denominator")
    if outcome_join.get("counts", {}).get("benchmark_solved_p2p3") != EXPECTED_ROWS:
        raise ValueError("outcome join solved denominator is not 12")


def _build_manifest(
    input_metadata: dict[str, dict[str, Any]],
    canonical_out: Path,
    worklist: list[dict[str, Any]],
    decisions: list[dict[str, Any]],
) -> dict[str, Any]:
    axis_counts = Counter(
        field for row in worklist for field in row.get("disagree_axes", [])
    )
    return {
        "schema_version": "repo480-rq2-adjudication-manifest-v1",
        "annotation_batch_id": BATCH_ID,
        "phase": "oracle_diagnostic_adjudication",
        "inputs": input_metadata,
        "canonical_adjudication": {
            "ref": _artifact_ref(canonical_out),
            "sha256": sha256_file(canonical_out),
            "row_count": len(decisions),
            "status_counts": dict(
                sorted(Counter(row["adjudication_status"] for row in decisions).items())
            ),
            "adjudicated_axis_counts": dict(sorted(axis_counts.items())),
        },
        "acceptance_gate": {
            "frozen_input_hashes_verified": True,
            "standalone_selfcheck_replayed": True,
            "all_rows_adjudicated": True,
            "unresolved_count": 0,
            "protocol_deviation_count": 0,
            "raw_returns_unchanged": True,
            "strict_call_direct_entry_absent": True,
            "final_analysis_release_allowed": True,
        },
    }


def _analyze(
    phase1: list[dict[str, Any]],
    r1: list[dict[str, Any]],
    r2: list[dict[str, Any]],
    worklist: list[dict[str, Any]],
    decisions: list[dict[str, Any]],
    outcome_join: dict[str, Any],
    input_metadata: dict[str, dict[str, Any]],
    manifest_path: Path,
    manifest_sha256: str,
    canonical_path: Path,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    work_by_task = _index(worklist, "worklist")
    decision_by_task = _index(decisions, "adjudication")
    rows = []
    for available, left, right in zip(phase1, r1, r2, strict=True):
        task_id = available["task_id"]
        final = {}
        sources = {}
        disagree_axes = []
        for field in CONTROLLED_FIELDS:
            if left[field] == right[field]:
                final[field] = left[field]
                sources[field] = "raw_exact_consensus"
            else:
                disagree_axes.append(field)
                work = work_by_task.get(task_id)
                decision = decision_by_task.get(task_id)
                if work is None or decision is None or field not in work["disagree_axes"]:
                    raise ValueError(f"{task_id}: missing adjudication for {field}")
                final[field] = decision["adjudicated_values"][field]
                sources[field] = "third_reviewer_adjudication"
        if set(disagree_axes) != set(work_by_task.get(task_id, {}).get("disagree_axes", [])):
            raise ValueError(f"{task_id}: derived disagreement axes do not match worklist")

        strict = _strict_call(final)
        disputed = bool(disagree_axes)
        rows.append(
            {
                "schema_version": "repo480-rq2-masking-row-v1",
                "annotation_batch_id": BATCH_ID,
                "ordinal": available["ordinal"],
                "task_id": task_id,
                "repo": available["repo"],
                "benchmark_solved": True,
                "raw_controlled_fields": {
                    "repo480_rq2_r1": {field: left[field] for field in CONTROLLED_FIELDS},
                    "repo480_rq2_r2": {field: right[field] for field in CONTROLLED_FIELDS},
                },
                "disagree_axes": disagree_axes,
                "field_sources": sources,
                "final_controlled_fields": final,
                "strict_masking_call": strict,
                "dispute_as_nonmasked_call": "no" if disputed else strict,
                "q0_only_included": final["data_quality"] == "Q0",
            }
        )

    primary = _rate(sum(row["strict_masking_call"] == "yes" for row in rows), len(rows))
    conservative = _rate(
        sum(row["dispute_as_nonmasked_call"] == "yes" for row in rows), len(rows)
    )
    q0_rows = [row for row in rows if row["q0_only_included"]]
    q0 = _rate(
        sum(row["strict_masking_call"] == "yes" for row in q0_rows), len(q0_rows)
    )
    field_distributions = {
        field: dict(sorted(Counter(row["final_controlled_fields"][field] for row in rows).items()))
        for field in CONTROLLED_FIELDS
    }
    capability = outcome_join.get("capability_sensitivity", [])
    if any(item.get("solved_p2p3_count") != EXPECTED_ROWS for item in capability):
        raise ValueError("capability sensitivity does not preserve the 12-row denominator")

    analysis = {
        "schema_version": "repo480-rq2-masking-analysis-v1",
        "analysis_id": "repo480-rq2-masking-v1",
        "annotation_batch_id": BATCH_ID,
        "packet_policy_id": PACKET_POLICY_ID,
        "estimand": (
            "proportion of the 12 benchmark-solved repository-packet P2/P3 tasks "
            "that meet the prespecified strict oracle-masking rule"
        ),
        "strict_rule": (
            "oracle_alternative_fix_exists=yes AND "
            "available_evidence_unique_in_hindsight=no"
        ),
        "claim_scope": {
            "reports": [
                "strict oracle masking within the frozen 12-task solved P2/P3 denominator",
                "field-level adjudicated mechanism diagnostics",
                "dispute-as-nonmasked and Q0-only sensitivity",
            ],
            "does_not_report": [
                "masking prevalence over all 480 tasks",
                "broad APR or GitHub issue population prevalence",
                "causal agent capability or deployment utility",
                "equivalence between benchmark resolution and task-time patchability",
            ],
        },
        "statistics": {
            "confidence_level": CONFIDENCE_LEVEL,
            "interval": "Wilson score interval",
        },
        "inputs": {
            **input_metadata,
            "canonical_adjudication": {
                "ref": _artifact_ref(canonical_path),
                "sha256": sha256_file(canonical_path),
                "row_count": len(decisions),
            },
            "adjudication_manifest": {
                "ref": _artifact_ref(manifest_path),
                "sha256": manifest_sha256,
            },
        },
        "integrity": {
            "denominator_task_count": len(rows),
            "task_ids_unique": len({row["task_id"] for row in rows}) == len(rows),
            "task_set_matches_solved_outcome_join": True,
            "raw_phase2_rows_per_reviewer": EXPECTED_ROWS,
            "raw_exact_controlled_field_consensus_count": sum(
                not row["disagree_axes"] for row in rows
            ),
            "third_reviewer_adjudicated_task_count": len(worklist),
            "third_reviewer_adjudicated_field_count": sum(
                len(row["disagree_axes"]) for row in worklist
            ),
            "unresolved_count": 0,
            "protocol_deviation_count": 0,
            "all_frozen_sha256_verified": True,
        },
        "primary_strict_masking": {
            **primary,
            "interpretation": (
                "benchmark resolution selected one oracle-compatible behavior target "
                "although task-time evidence allowed an alternative and was non-unique"
            ),
        },
        "sensitivity": {
            "dispute_as_nonmasked": {
                **conservative,
                "definition": (
                    "treat every task with any raw controlled-field disagreement as non-masked"
                ),
                "excluded_task_ids": [
                    row["task_id"] for row in rows if row["disagree_axes"]
                ],
            },
            "q0_only": {
                **q0,
                "definition": "restrict the denominator to final data_quality=Q0",
                "excluded_task_ids": [
                    row["task_id"] for row in rows if not row["q0_only_included"]
                ],
            },
        },
        "field_distributions": field_distributions,
        "capability_threshold_sensitivity": [
            {
                "minimum_resolved_in_frame": item["minimum_resolved_in_frame"],
                "eligible_run_count": item["eligible_run_count"],
                "denominator_task_count": item["solved_p2p3_count"],
                "strict_masking_count": primary["count"],
            }
            for item in capability
        ],
    }
    _validate_analysis(analysis, rows)
    return analysis, rows


def _validate_analysis(analysis: dict[str, Any], rows: list[dict[str, Any]]) -> None:
    if len(rows) != EXPECTED_ROWS:
        raise ValueError("final RQ2 row artifact must contain 12 rows")
    if analysis["integrity"]["raw_exact_controlled_field_consensus_count"] != 9:
        raise ValueError("expected 9 exact controlled-field consensus rows")
    if analysis["integrity"]["third_reviewer_adjudicated_field_count"] != 5:
        raise ValueError("expected five adjudicated controlled fields")
    if analysis["primary_strict_masking"]["count"] != 12:
        raise ValueError("expected final strict masking count 12")
    conservative = analysis["sensitivity"]["dispute_as_nonmasked"]
    if (conservative["count"], conservative["denominator"]) != (9, 12):
        raise ValueError("expected dispute-as-nonmasked sensitivity 9/12")
    q0 = analysis["sensitivity"]["q0_only"]
    if (q0["count"], q0["denominator"]) != (11, 11):
        raise ValueError("expected Q0-only sensitivity 11/11")
    if analysis["field_distributions"]["data_quality"] != {"Q0": 11, "Q1": 1}:
        raise ValueError("unexpected final data-quality distribution")


def _strict_call(fields: dict[str, str]) -> str:
    return (
        "yes"
        if fields["oracle_alternative_fix_exists"] == "yes"
        and fields["available_evidence_unique_in_hindsight"] == "no"
        else "no"
    )


def _rate(count: int, denominator: int) -> dict[str, Any]:
    if denominator <= 0 or not 0 <= count <= denominator:
        raise ValueError("invalid rate numerator or denominator")
    lower, upper = _wilson(count, denominator)
    return {
        "count": count,
        "denominator": denominator,
        "proportion": _round(count / denominator),
        "wilson_95_ci": {"lower": _round(lower), "upper": _round(upper)},
    }


def _wilson(count: int, denominator: int) -> tuple[float, float]:
    z = NormalDist().inv_cdf(0.5 + CONFIDENCE_LEVEL / 2)
    proportion = count / denominator
    z2 = z * z
    center = (proportion + z2 / (2 * denominator)) / (1 + z2 / denominator)
    margin = (
        z
        * math.sqrt(
            proportion * (1 - proportion) / denominator
            + z2 / (4 * denominator * denominator)
        )
        / (1 + z2 / denominator)
    )
    return max(0.0, center - margin), min(1.0, center + margin)


def _build_markdown(analysis: dict[str, Any]) -> str:
    primary = analysis["primary_strict_masking"]
    conservative = analysis["sensitivity"]["dispute_as_nonmasked"]
    q0 = analysis["sensitivity"]["q0_only"]
    lines = [
        "# Repo480 RQ2 Oracle-Masking Analysis",
        "",
        "- **Status:** `canonical-pilot`",
        "- **Batch:** `repo480_rq2_masking_v1`",
        "- **Denominator:** 12 benchmark-solved repository-packet P2/P3 tasks",
        "",
        "## Primary result",
        "",
        f"Strict oracle masking은 **{primary['count']}/{primary['denominator']} = "
        f"{primary['proportion']:.3f}**이며 Wilson 95% CI는 "
        f"`[{primary['wilson_95_ci']['lower']:.3f}, "
        f"{primary['wilson_95_ci']['upper']:.3f}]`이다. Strict call은 reviewer가 직접 입력하지 "
        "않고 `oracle_alternative_fix_exists=yes` AND "
        "`available_evidence_unique_in_hindsight=no`에서 유도했다.",
        "",
        "이 결과의 분모는 480개 전체나 repository P2/P3 26개 전체가 아니다. Frozen public "
        "full-test run에서 benchmark-solved가 관찰된 repository P2/P3 12개에 한정된다.",
        "",
        "## Sensitivity",
        "",
        "| Analysis | Count / denominator | Proportion | Wilson 95% CI |",
        "| --- | ---: | ---: | ---: |",
        f"| Primary strict | {primary['count']}/{primary['denominator']} | "
        f"{primary['proportion']:.3f} | [{primary['wilson_95_ci']['lower']:.3f}, "
        f"{primary['wilson_95_ci']['upper']:.3f}] |",
        f"| Any field dispute as non-masked | {conservative['count']}/"
        f"{conservative['denominator']} | {conservative['proportion']:.3f} | "
        f"[{conservative['wilson_95_ci']['lower']:.3f}, "
        f"{conservative['wilson_95_ci']['upper']:.3f}] |",
        f"| Q0 only | {q0['count']}/{q0['denominator']} | {q0['proportion']:.3f} | "
        f"[{q0['wilson_95_ci']['lower']:.3f}, {q0['wilson_95_ci']['upper']:.3f}] |",
        "",
        "Dispute-as-nonmasked는 strict-call field가 일치했더라도 여섯 controlled field 중 하나라도 "
        "raw disagreement가 있었던 세 task를 모두 non-masked로 두는 보수적 stress test다. "
        "Q0-only는 final `data_quality=Q1`인 `django__django-15993` 한 행을 제외한다.",
        "",
        "## Adjudication and mechanism diagnostics",
        "",
        f"두 raw pass는 9/12행에서 여섯 controlled field가 모두 일치했다. 나머지 3행의 5개 "
        "field는 제3 reviewer가 판정했으며 unresolved와 protocol deviation은 없다.",
        "",
        "| Field | Final distribution |",
        "| --- | --- |",
    ]
    for field in CONTROLLED_FIELDS:
        values = ", ".join(
            f"`{value}`={count}"
            for value, count in analysis["field_distributions"][field].items()
        )
        lines.append(f"| `{field}` | {values} |")
    lines.extend(
        [
            "",
            "Capability threshold 0ㆍ8ㆍ32ㆍ50에서 solved denominator는 같은 12행이고 strict "
            "masking count도 12로 유지된다.",
            "",
            "## Claim boundary",
            "",
            "이 결과는 benchmark `resolved`가 task-time patchability와 동치가 아님을 보여 주는 "
            "oracle-masking mechanism 결과다. 480-task masking prevalence, broad APR 일반화, 특정 "
            "agent capability, abstention의 causal utility improvement를 의미하지 않는다.",
            "",
        ]
    )
    return "\n".join(lines)


def _build_tex(analysis: dict[str, Any]) -> str:
    primary = analysis["primary_strict_masking"]
    conservative = analysis["sensitivity"]["dispute_as_nonmasked"]
    q0 = analysis["sensitivity"]["q0_only"]
    return "\n".join(
        [
            "% Generated by scripts/analyze_repo480_rq2_masking.py; do not edit manually.",
            "\\begin{table}[t]",
            "\\caption{RQ2 strict oracle masking and sensitivity.}",
            "\\label{tab:repo480rq2masking}",
            "\\centering",
            "\\small",
            "\\begin{tabular}{@{}p{0.43\\linewidth}p{0.20\\linewidth}p{0.28\\linewidth}@{}}",
            "\\hline",
            "Analysis & Masked & Estimate / Wilson 95\\% CI \\\\",
            "\\hline",
            f"Primary strict & {primary['count']}/{primary['denominator']} & "
            f"{primary['proportion']:.3f} "
            f"[{primary['wilson_95_ci']['lower']:.3f}, "
            f"{primary['wilson_95_ci']['upper']:.3f}] \\\\",
            f"Any field dispute as non-masked & {conservative['count']}/"
            f"{conservative['denominator']} & {conservative['proportion']:.3f} "
            f"[{conservative['wilson_95_ci']['lower']:.3f}, "
            f"{conservative['wilson_95_ci']['upper']:.3f}] \\\\",
            f"Q0 only & {q0['count']}/{q0['denominator']} & {q0['proportion']:.3f} "
            f"[{q0['wilson_95_ci']['lower']:.3f}, {q0['wilson_95_ci']['upper']:.3f}] \\\\",
            "\\hline",
            "\\end{tabular}",
            "\\end{table}",
            "",
        ]
    )


def _build_rows_tex(rows: list[dict[str, Any]]) -> str:
    lines = [
        "% Generated by scripts/analyze_repo480_rq2_masking.py; do not edit manually.",
        "\\begin{table*}[t]",
        "\\caption{All benchmark-solved repository P2/P3 rows in the RQ2 panel.}",
        "\\label{tab:repo480rq2rows}",
        "\\centering",
        "\\scriptsize",
        "\\begin{tabular}{@{}p{0.23\\textwidth}cccccccc@{}}",
        "\\hline",
        "Task & In set & Gap & Alt. & Unique & Targets & Q & Strict & Conserv. \\\\",
        "\\hline",
    ]
    for row in rows:
        fields = row["final_controlled_fields"]
        task = row["task_id"]
        lines.append(
            f"\\path{{{task}}} & "
            f"{fields['oracle_direction_in_candidate_set']} & "
            f"{fields['oracle_revealed_missing_evidence']} & "
            f"{fields['oracle_alternative_fix_exists']} & "
            f"{fields['available_evidence_unique_in_hindsight']} & "
            f"{fields['behavior_target_space_size']} & "
            f"{fields['data_quality']} & "
            f"{row['strict_masking_call']} & "
            f"{row['dispute_as_nonmasked_call']} \\\\"
        )
    lines.extend(["\\hline", "\\end{tabular}", "\\end{table*}", ""])
    return "\n".join(lines)


def _build_run_pool_tex(outcome_join: dict[str, Any]) -> str:
    run_ids = outcome_join["run_pool"]["run_ids"]
    if len(run_ids) != 24:
        raise ValueError(f"expected 24 frozen public runs, found {len(run_ids)}")
    lines = [
        "% Generated by scripts/analyze_repo480_rq2_masking.py; do not edit manually.",
        "\\begin{table*}[t]",
        "\\caption{Public SWE-bench full-test run pool frozen for the RQ2 outcome join.}",
        "\\label{tab:repo480rq2runs}",
        "\\centering",
        "\\scriptsize",
        "\\setlength{\\tabcolsep}{3pt}",
        "\\begin{tabular}{@{}rllrll@{}}",
        "\\hline",
        "No. & Run identifier & & No. & Run identifier & \\\\",
        "\\hline",
    ]
    for index in range(12):
        left = run_ids[index]
        right = run_ids[index + 12]
        lines.append(
            f"{index + 1} & \\path{{{left}}} & & {index + 13} & \\path{{{right}}} & \\\\"
        )
    lines.extend(["\\hline", "\\end{tabular}", "\\end{table*}", ""])
    return "\n".join(lines)


def _preserve_exact(source: Path, target: Path, expected_hash: str) -> None:
    if target.exists():
        if sha256_file(target) != expected_hash:
            raise ValueError(f"refusing to overwrite mismatched canonical file {target}")
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, target)
    if sha256_file(target) != expected_hash:
        raise ValueError(f"canonical preservation hash mismatch for {target}")


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


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = []
    with path.open("r", encoding="utf-8") as handle:
        for line_no, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            value = json.loads(line)
            if not isinstance(value, dict):
                raise ValueError(f"{path}:{line_no}: expected JSON object")
            rows.append(value)
    if not rows:
        raise ValueError(f"{path}: no JSONL rows")
    return rows


def _read_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path}: expected JSON object")
    return value


def _artifact_ref(path: Path) -> str:
    resolved = path.resolve()
    try:
        return resolved.relative_to(ROOT).as_posix()
    except ValueError:
        return path.name


def _round(value: float) -> float:
    return round(value, 6)


if __name__ == "__main__":
    raise SystemExit(main())
