#!/usr/bin/env python3
"""Analyze the adjudicated repo480 RQ2 matched-control panel."""

from __future__ import annotations

import argparse
import itertools
import json
import math
import sys
from collections import Counter, defaultdict
from pathlib import Path
from statistics import NormalDist
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
for path in (ROOT, SRC):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from notpatch.canonical import canonical_json_bytes, sha256_file  # noqa: E402
from scripts.selfcheck_repo480_rq2_control_adjudication_return import (  # noqa: E402
    validate_return as validate_adjudication,
)
from scripts.selfcheck_repo480_rq2_control_phase2_return import (  # noqa: E402
    validate_return as validate_phase2,
)

BATCH_ID = "repo480_rq2_control_v1"
ARM_TREATED = "solved_p2p3_treated"
ARM_CONTROL = "solved_p01_control"
ROLES = ("repo480_nc_r1", "repo480_nc_r2")
CONTROLLED_FIELDS = (
    "oracle_direction_in_candidate_set",
    "oracle_revealed_missing_evidence",
    "oracle_alternative_fix_exists",
    "available_evidence_unique_in_hindsight",
    "behavior_target_space_size",
    "data_quality",
)
CONFIDENCE_LEVEL = 0.95

DEFAULTS = {
    "selection": Path("data/annotations/worklists/repo480_rq2_control_selection_v1.jsonl"),
    "batch_manifest": Path("data/manifests/generated/repo480_rq2_control_manifest_v1.json"),
    "phase2_manifest": Path(
        "data/manifests/generated/repo480_rq2_control_phase2_manifest_v1.json"
    ),
    "phase2_returns_manifest": Path(
        "data/manifests/generated/repo480_rq2_control_phase2_returns_manifest_v1.json"
    ),
    "r1": Path(
        "data/annotations/oracle_gap/repo480_rq2_control_panel/"
        "repo480_rq2_control_phase2_r1.jsonl"
    ),
    "r2": Path(
        "data/annotations/oracle_gap/repo480_rq2_control_panel/"
        "repo480_rq2_control_phase2_r2.jsonl"
    ),
    "raw_agreement": Path("results/pilot/repo480_rq2_control_phase2_raw_agreement_v1.json"),
    "adjudication_manifest": Path(
        "data/manifests/generated/repo480_rq2_control_adjudication_manifest_v1.json"
    ),
    "adjudication_returns_manifest": Path(
        "data/manifests/generated/repo480_rq2_control_adjudication_returns_manifest_v1.json"
    ),
    "worklist": Path(
        "data/annotations/worklists/"
        "repo480_rq2_control_phase2_adjudication_worklist_v1.jsonl"
    ),
    "adjudication": Path(
        "data/annotations/oracle_gap/repo480_rq2_control_panel/"
        "repo480_rq2_control_phase2_adjudication.jsonl"
    ),
    "masking_rows": Path("results/pilot/repo480_rq2_masking_rows_v1.jsonl"),
    "json_out": Path("results/pilot/repo480_rq2_control_analysis_v1.json"),
    "rows_out": Path("results/pilot/repo480_rq2_control_analysis_rows_v1.jsonl"),
    "markdown_out": Path("results/pilot/repo480_rq2_control_analysis_v1.md"),
    "tex_out": Path("paper/generated/repo480_rq2_control_summary.tex"),
}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    for name, default in DEFAULTS.items():
        parser.add_argument(f"--{name.replace('_', '-')}", type=Path, default=default)
    args = parser.parse_args()
    try:
        analysis, rows = analyze(args)
        outputs = {
            args.json_out: canonical_json_bytes(analysis),
            args.rows_out: b"".join(canonical_json_bytes(row) for row in rows),
            args.markdown_out: _markdown(analysis).encode(),
            args.tex_out: _tex(analysis).encode(),
        }
        for path, payload in outputs.items():
            target = _absolute(path)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(payload)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1
    treated = analysis["primary_strict_masking"][ARM_TREATED]
    control = analysis["primary_strict_masking"][ARM_CONTROL]
    contrast = analysis["treated_control_contrast"]
    print(
        "OK: wrote RQ2 matched-control analysis "
        f"(treated={treated['count']}/{treated['denominator']}, "
        f"control={control['count']}/{control['denominator']}, "
        f"control-minus-treated={contrast['estimate']:.3f})"
    )
    return 0


def analyze(args: argparse.Namespace) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    paths = {name: _absolute(getattr(args, name)) for name in DEFAULTS}
    selection = _jsonl(paths["selection"])
    batch_manifest = _object(paths["batch_manifest"])
    phase2_manifest = _object(paths["phase2_manifest"])
    phase2_returns_manifest = _object(paths["phase2_returns_manifest"])
    raw_agreement = _object(paths["raw_agreement"])
    adjudication_manifest = _object(paths["adjudication_manifest"])
    adjudication_returns_manifest = _object(paths["adjudication_returns_manifest"])
    worklist = _jsonl(paths["worklist"])
    decisions = _jsonl(paths["adjudication"])
    masking_rows = _jsonl(paths["masking_rows"])
    raw = {
        ROLES[0]: _jsonl(paths["r1"]),
        ROLES[1]: _jsonl(paths["r2"]),
    }
    phase2_tasks = {
        role: _jsonl(ROOT / phase2_manifest["role_packages"][role]["tasks"]["ref"])
        for role in ROLES
    }
    _validate_inputs(
        paths,
        selection,
        batch_manifest,
        phase2_manifest,
        phase2_returns_manifest,
        raw_agreement,
        adjudication_manifest,
        adjudication_returns_manifest,
        worklist,
        decisions,
        masking_rows,
        raw,
        phase2_tasks,
    )
    rows = _combine(selection, raw, worklist, decisions)
    analysis = _summarize(paths, rows, masking_rows, worklist, decisions)
    _validate_analysis(analysis, rows)
    return analysis, rows


def _validate_inputs(
    paths: dict[str, Path],
    selection: list[dict[str, Any]],
    batch: dict[str, Any],
    phase2: dict[str, Any],
    phase2_returns: dict[str, Any],
    raw_agreement: dict[str, Any],
    adjudication_manifest: dict[str, Any],
    adjudication_returns: dict[str, Any],
    worklist: list[dict[str, Any]],
    decisions: list[dict[str, Any]],
    masking_rows: list[dict[str, Any]],
    raw: dict[str, list[dict[str, Any]]],
    phase2_tasks: dict[str, list[dict[str, Any]]],
) -> None:
    if batch.get("schema_version") != "repo480-rq2-control-manifest-v1":
        raise ValueError("RQ2-control batch manifest schema mismatch")
    if batch.get("annotation_batch_id") != BATCH_ID:
        raise ValueError("RQ2-control batch ID mismatch")
    if batch.get("analysis_plan", {}).get("contrast") != (
        "control minus treated rate, with a repository-clustered bootstrap interval"
    ):
        raise ValueError("preregistered contrast changed")
    _require_hash(paths["selection"], batch["selection"]["sha256"], "selection")
    _require_hash(paths["masking_rows"], batch["inputs"]["masking_rows"]["sha256"], "masking rows")

    if phase2.get("schema_version") != "repo480-rq2-control-phase2-manifest-v1":
        raise ValueError("Phase 2 manifest schema mismatch")
    _require_hash(
        paths["batch_manifest"], phase2["batch_manifest"]["sha256"], "batch manifest"
    )
    if phase2_returns.get("schema_version") != "repo480-rq2-control-phase2-returns-manifest-v1":
        raise ValueError("Phase 2 returns manifest schema mismatch")
    gate = phase2_returns.get("acceptance_gate", {})
    for field in (
        "all_rows_returned",
        "frozen_baseline_diff_verified",
        "immutable_linkage_passed",
        "next_stage_release_allowed",
        "selfcheck_passed",
    ):
        if gate.get(field) is not True:
            raise ValueError(f"Phase 2 acceptance gate is open: {field}")
    if gate.get("protocol_deviation_count") != 0:
        raise ValueError("Phase 2 protocol deviation is nonzero")

    for role, path_key in zip(ROLES, ("r1", "r2"), strict=True):
        role_tasks = phase2["role_packages"][role]["tasks"]
        task_path = ROOT / role_tasks["ref"]
        _require_hash(task_path, role_tasks["sha256"], f"{role} tasks")
        returned = phase2_returns["returns"][role]
        _require_hash(paths[path_key], returned["sha256"], f"{role} return")
        validate_phase2(phase2_tasks[role], raw[role], role)

    if raw_agreement.get("schema_version") != "repo480-rq2-control-phase2-raw-agreement-v1":
        raise ValueError("raw agreement schema mismatch")
    if raw_agreement.get("disagreement_queue", {}).get("task_ids") != [
        row["task_id"] for row in worklist
    ]:
        raise ValueError("raw disagreement queue does not match the worklist")
    if adjudication_manifest.get("schema_version") != (
        "repo480-rq2-control-adjudication-manifest-v1"
    ):
        raise ValueError("adjudication manifest schema mismatch")
    _require_hash(
        paths["worklist"], adjudication_manifest["queue"]["sha256"], "adjudication worklist"
    )
    if adjudication_returns.get("schema_version") != (
        "repo480-rq2-control-adjudication-returns-manifest-v1"
    ):
        raise ValueError("adjudication returns manifest schema mismatch")
    adj_gate = adjudication_returns.get("acceptance_gate", {})
    for field in (
        "all_rows_adjudicated",
        "all_rows_returned",
        "frozen_baseline_diff_verified",
        "immutable_linkage_passed",
        "next_stage_release_allowed",
        "selfcheck_passed",
    ):
        if adj_gate.get(field) is not True:
            raise ValueError(f"adjudication acceptance gate is open: {field}")
    if adj_gate.get("protocol_deviation_count") != 0:
        raise ValueError("adjudication protocol deviation is nonzero")
    if adj_gate.get("prohibited_evidence_count") != 0:
        raise ValueError("adjudication prohibited-evidence count is nonzero")
    _require_hash(
        paths["adjudication"], adjudication_returns["return"]["sha256"], "adjudication return"
    )
    validate_adjudication(worklist, decisions)
    if any(row["adjudication_status"] != "adjudicated" for row in decisions):
        raise ValueError("every adjudication row must be adjudicated")

    orders = {
        "selection": [row["task_id"] for row in selection],
        **{role: [row["task_id"] for row in raw[role]] for role in ROLES},
        **{f"{role}_tasks": [row["task_id"] for row in phase2_tasks[role]] for role in ROLES},
    }
    if len(selection) != 36 or len(set(orders["selection"])) != 36:
        raise ValueError("selection must contain 36 unique tasks")
    if any(order != orders["selection"] for order in orders.values()):
        raise ValueError("selection, tasks, and return order differ")
    arms = Counter(row["arm"] for row in selection)
    if arms != Counter({ARM_TREATED: 12, ARM_CONTROL: 24}):
        raise ValueError("arm denominator changed")
    by_repo: dict[str, Counter[str]] = defaultdict(Counter)
    for row in selection:
        by_repo[row["repository"]][row["arm"]] += 1
    if any(counts[ARM_CONTROL] != 2 * counts[ARM_TREATED] for counts in by_repo.values()):
        raise ValueError("repository-level 1:2 matching ratio changed")
    treated_ids = {row["task_id"] for row in selection if row["arm"] == ARM_TREATED}
    if treated_ids != {row["task_id"] for row in masking_rows}:
        raise ValueError("treated arm no longer matches the frozen RQ2 denominator")
    if any(row["strict_masking_call"] != "yes" for row in masking_rows):
        raise ValueError("frozen original-panel strict result is no longer 12/12")


def _combine(
    selection: list[dict[str, Any]],
    raw: dict[str, list[dict[str, Any]]],
    worklist: list[dict[str, Any]],
    decisions: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    raw_by_role = {role: _index(rows, role) for role, rows in raw.items()}
    work_by_task = _index(worklist, "worklist")
    decision_by_task = _index(decisions, "adjudication")
    rows = []
    for selected in selection:
        task_id = selected["task_id"]
        left = raw_by_role[ROLES[0]][task_id]
        right = raw_by_role[ROLES[1]][task_id]
        final: dict[str, str] = {}
        sources: dict[str, str] = {}
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
                sources[field] = "third_expert_adjudication"
        expected_axes = work_by_task.get(task_id, {}).get("disagree_axes", [])
        if set(disagree_axes) != set(expected_axes):
            raise ValueError(f"{task_id}: derived disagreement axes do not match worklist")
        strict = _strict(final)
        rows.append(
            {
                "schema_version": "repo480-rq2-control-analysis-row-v1",
                "annotation_batch_id": BATCH_ID,
                "ordinal": selected["ordinal"],
                "task_id": task_id,
                "repository": selected["repository"],
                "arm": selected["arm"],
                "matched_to": selected["matched_to"],
                "resolving_runs": selected["resolving_runs"],
                "run_gap": selected["run_gap"],
                "raw_controlled_fields": {
                    role: {field: raw_by_role[role][task_id][field] for field in CONTROLLED_FIELDS}
                    for role in ROLES
                },
                "disagree_axes": disagree_axes,
                "field_sources": sources,
                "final_controlled_fields": final,
                "strict_masking_call": "yes" if strict else "no",
                "dispute_as_nonmasked_call": "no" if disagree_axes else ("yes" if strict else "no"),
                "q0_only_included": final["data_quality"] == "Q0",
            }
        )
    return rows


def _summarize(
    paths: dict[str, Path],
    rows: list[dict[str, Any]],
    masking_rows: list[dict[str, Any]],
    worklist: list[dict[str, Any]],
    decisions: list[dict[str, Any]],
) -> dict[str, Any]:
    primary = _arm_rates(rows, "strict_masking_call")
    conservative = _arm_rates(rows, "dispute_as_nonmasked_call")
    q0 = {
        arm: _rate(
            sum(row["strict_masking_call"] == "yes" for row in rows if row["arm"] == arm and row["q0_only_included"]),
            sum(row["arm"] == arm and row["q0_only_included"] for row in rows),
        )
        for arm in (ARM_TREATED, ARM_CONTROL)
    }
    conjuncts = {
        "oracle_alternative_fix_exists_yes": {
            arm: _rate(
                sum(
                    row["final_controlled_fields"]["oracle_alternative_fix_exists"] == "yes"
                    for row in rows
                    if row["arm"] == arm
                ),
                sum(row["arm"] == arm for row in rows),
            )
            for arm in (ARM_TREATED, ARM_CONTROL)
        },
        "available_evidence_unique_in_hindsight_no": {
            arm: _rate(
                sum(
                    row["final_controlled_fields"]["available_evidence_unique_in_hindsight"] == "no"
                    for row in rows
                    if row["arm"] == arm
                ),
                sum(row["arm"] == arm for row in rows),
            )
            for arm in (ARM_TREATED, ARM_CONTROL)
        },
    }
    contrast = _proportion(primary[ARM_CONTROL]) - _proportion(primary[ARM_TREATED])
    cluster_interval = _cluster_bootstrap(rows)
    return {
        "schema_version": "repo480-rq2-control-analysis-v1",
        "analysis_id": "repo480-rq2-control-v1",
        "annotation_batch_id": BATCH_ID,
        "estimand": (
            "strict oracle-masking rate in the benchmark-solved P2/P3 treated arm and "
            "repository-and-resolving-run-matched benchmark-solved P0/P1 control arm"
        ),
        "strict_rule": (
            "oracle_alternative_fix_exists=yes AND "
            "available_evidence_unique_in_hindsight=no"
        ),
        "statistics": {
            "arm_intervals": "Wilson score two-sided 95% intervals",
            "contrast": "control minus treated proportion",
            "contrast_interval": (
                "exhaustive percentile nonparametric bootstrap over repository clusters"
            ),
        },
        "inputs": {
            name: _artifact(path)
            for name, path in paths.items()
            if name not in {"json_out", "rows_out", "markdown_out", "tex_out"}
        },
        "integrity": {
            "panel_task_count": len(rows),
            "treated_task_count": sum(row["arm"] == ARM_TREATED for row in rows),
            "control_task_count": sum(row["arm"] == ARM_CONTROL for row in rows),
            "repository_cluster_count": len({row["repository"] for row in rows}),
            "raw_exact_controlled_field_consensus_count": sum(not row["disagree_axes"] for row in rows),
            "third_expert_adjudicated_task_count": len(worklist),
            "third_expert_adjudicated_field_count": sum(len(row["disagree_axes"]) for row in worklist),
            "adjudication_return_sha256": sha256_file(paths["adjudication"]),
            "unresolved_count": sum(row["adjudication_status"] == "unresolved" for row in decisions),
            "protocol_deviation_count": sum(row.get("protocol_deviation") is not None for row in decisions),
            "prohibited_evidence_count": sum(row.get("prohibited_evidence_used") is True for row in decisions),
            "all_linked_hashes_verified": True,
        },
        "frozen_original_panel_reference": {
            "strict_masking_count": sum(row["strict_masking_call"] == "yes" for row in masking_rows),
            "denominator": len(masking_rows),
            "interpretation": "separately staffed original RQ2 panel; not pooled with the matched panel",
        },
        "primary_strict_masking": primary,
        "treated_control_contrast": {
            "scale": "control_minus_treated",
            "estimate": _round(contrast),
            "repository_clustered_bootstrap_95_ci": cluster_interval,
        },
        "sensitivity": {
            "dispute_as_nonmasked": {
                "definition": "treat every row with any raw controlled-field disagreement as non-masked",
                "arms": conservative,
                "control_minus_treated": _round(
                    _proportion(conservative[ARM_CONTROL])
                    - _proportion(conservative[ARM_TREATED])
                ),
            },
            "q0_only": {
                "definition": "restrict each arm to final data_quality=Q0",
                "arms": q0,
                "control_minus_treated": _round(
                    _proportion(q0[ARM_CONTROL]) - _proportion(q0[ARM_TREATED])
                ),
            },
            "strict_rule_conjuncts": conjuncts,
        },
        "field_distributions_by_arm": {
            arm: {
                field: dict(
                    sorted(
                        Counter(
                            row["final_controlled_fields"][field]
                            for row in rows
                            if row["arm"] == arm
                        ).items()
                    )
                )
                for field in CONTROLLED_FIELDS
            }
            for arm in (ARM_TREATED, ARM_CONTROL)
        },
        "preregistered_claim_decision": {
            "decision": "retain_oracle_masking_mechanism_with_qualified_discrimination",
            "basis": (
                "the control rate is substantially lower than the treated rate and the "
                "repository-clustered interval for control minus treated excludes zero"
            ),
            "qualifications": [
                "the strict rule is positive for some matched P0/P1 controls",
                "the matched panel reproduces 10/12 rather than the original panel's 12/12",
                "the comparison is conditional on 36 benchmark-solved matched tasks in seven repositories",
            ],
        },
        "claim_scope": {
            "reports": [
                "within-panel discriminant validity of the strict masking rule in the matched frame",
                "panel sensitivity of the treated-arm strict call",
                "prespecified conservative, Q0-only, and conjunct-level sensitivities",
            ],
            "does_not_report": [
                "masking prevalence over the 480-task frame",
                "causal effect of benchmark resolution or patchability label",
                "perfect specificity of the strict rule",
                "broad APR population generalization",
            ],
        },
    }


def _cluster_bootstrap(rows: list[dict[str, Any]]) -> dict[str, Any]:
    clusters: dict[str, dict[str, tuple[int, int]]] = {}
    for repository in sorted({row["repository"] for row in rows}):
        repo_rows = [row for row in rows if row["repository"] == repository]
        clusters[repository] = {
            arm: (
                sum(row["strict_masking_call"] == "yes" for row in repo_rows if row["arm"] == arm),
                sum(row["arm"] == arm for row in repo_rows),
            )
            for arm in (ARM_TREATED, ARM_CONTROL)
        }
    repositories = sorted(clusters)
    distribution = []
    for sample in itertools.product(range(len(repositories)), repeat=len(repositories)):
        totals = {arm: [0, 0] for arm in (ARM_TREATED, ARM_CONTROL)}
        for index in sample:
            cluster = clusters[repositories[index]]
            for arm in totals:
                totals[arm][0] += cluster[arm][0]
                totals[arm][1] += cluster[arm][1]
        distribution.append(
            totals[ARM_CONTROL][0] / totals[ARM_CONTROL][1]
            - totals[ARM_TREATED][0] / totals[ARM_TREATED][1]
        )
    distribution.sort()
    return {
        "lower": _round(_percentile(distribution, 0.025)),
        "upper": _round(_percentile(distribution, 0.975)),
        "cluster_count": len(repositories),
        "resample_count": len(distribution),
        "enumeration": "all ordered cluster resamples with replacement",
    }


def _arm_rates(rows: list[dict[str, Any]], field: str) -> dict[str, dict[str, Any]]:
    return {
        arm: _rate(
            sum(row[field] == "yes" for row in rows if row["arm"] == arm),
            sum(row["arm"] == arm for row in rows),
        )
        for arm in (ARM_TREATED, ARM_CONTROL)
    }


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


def _proportion(rate: dict[str, Any]) -> float:
    return rate["count"] / rate["denominator"]


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


def _percentile(values: list[float], probability: float) -> float:
    position = (len(values) - 1) * probability
    lower = math.floor(position)
    upper = math.ceil(position)
    return values[lower] + (position - lower) * (values[upper] - values[lower])


def _validate_analysis(analysis: dict[str, Any], rows: list[dict[str, Any]]) -> None:
    treated = analysis["primary_strict_masking"][ARM_TREATED]
    control = analysis["primary_strict_masking"][ARM_CONTROL]
    if (treated["count"], treated["denominator"]) != (10, 12):
        raise ValueError("unexpected treated-arm strict result")
    if (control["count"], control["denominator"]) != (5, 24):
        raise ValueError("unexpected control-arm strict result")
    contrast = analysis["treated_control_contrast"]
    if contrast["estimate"] != -0.625:
        raise ValueError("unexpected treated-control contrast")
    interval = contrast["repository_clustered_bootstrap_95_ci"]
    if (interval["lower"], interval["upper"]) != (-0.875, -0.142857):
        raise ValueError("unexpected repository-clustered interval")
    conservative = analysis["sensitivity"]["dispute_as_nonmasked"]["arms"]
    if (conservative[ARM_TREATED]["count"], conservative[ARM_CONTROL]["count"]) != (5, 2):
        raise ValueError("unexpected dispute-as-nonmasked result")
    q0 = analysis["sensitivity"]["q0_only"]["arms"]
    if (q0[ARM_TREATED]["count"], q0[ARM_TREATED]["denominator"]) != (10, 11):
        raise ValueError("unexpected treated Q0-only result")
    if (q0[ARM_CONTROL]["count"], q0[ARM_CONTROL]["denominator"]) != (5, 23):
        raise ValueError("unexpected control Q0-only result")
    if len(rows) != 36 or sum(bool(row["disagree_axes"]) for row in rows) != 13:
        raise ValueError("final row audit shape changed")


def _strict(fields: dict[str, str]) -> bool:
    return (
        fields["oracle_alternative_fix_exists"] == "yes"
        and fields["available_evidence_unique_in_hindsight"] == "no"
    )


def _markdown(analysis: dict[str, Any]) -> str:
    treated = analysis["primary_strict_masking"][ARM_TREATED]
    control = analysis["primary_strict_masking"][ARM_CONTROL]
    contrast = analysis["treated_control_contrast"]
    interval = contrast["repository_clustered_bootstrap_95_ci"]
    conservative = analysis["sensitivity"]["dispute_as_nonmasked"]["arms"]
    q0 = analysis["sensitivity"]["q0_only"]["arms"]
    return "\n".join(
        [
            "# Repo480 RQ2 Matched-Control Analysis",
            "",
            "- **Status:** `canonical-pilot`",
            "- **Authority:** RQ2 strict masking rule의 matched negative-control 분석",
            "- **Last verified:** 2026-08-20",
            "",
            "## Primary result",
            "",
            "| Arm | Strict count | Rate | Wilson 95% CI |",
            "| --- | ---: | ---: | ---: |",
            f"| Solved P2/P3 treated | {treated['count']}/{treated['denominator']} | {treated['proportion']:.3f} | [{treated['wilson_95_ci']['lower']:.3f}, {treated['wilson_95_ci']['upper']:.3f}] |",
            f"| Matched solved P0/P1 control | {control['count']}/{control['denominator']} | {control['proportion']:.3f} | [{control['wilson_95_ci']['lower']:.3f}, {control['wilson_95_ci']['upper']:.3f}] |",
            "",
            f"Control-minus-treated contrast는 **{contrast['estimate']:.3f}**이고, 7개 repository cluster의 "
            f"모든 {interval['resample_count']:,}개 ordered bootstrap resample을 열거한 percentile "
            f"95% interval은 `[{interval['lower']:.3f}, {interval['upper']:.3f}]`이다.",
            "",
            "대조군 rate가 처리군보다 현저히 낮고 cluster interval이 0을 제외하므로, 사전 등록 "
            "판정 규칙에 따라 oracle-masking mechanism 해석은 유지한다. 다만 control 5/24도 strict "
            "positive이므로 규칙의 완전한 특이도를 주장하지 않으며, 같은 matched panel의 treated "
            "재판정이 기존 별도 panel의 12/12가 아니라 10/12였다는 panel sensitivity를 함께 보고한다.",
            "",
            "## Sensitivity",
            "",
            "| Analysis | Treated | Control | Control minus treated |",
            "| --- | ---: | ---: | ---: |",
            f"| Any raw dispute as non-masked | {conservative[ARM_TREATED]['count']}/{conservative[ARM_TREATED]['denominator']} | {conservative[ARM_CONTROL]['count']}/{conservative[ARM_CONTROL]['denominator']} | {analysis['sensitivity']['dispute_as_nonmasked']['control_minus_treated']:.3f} |",
            f"| Q0 only | {q0[ARM_TREATED]['count']}/{q0[ARM_TREATED]['denominator']} | {q0[ARM_CONTROL]['count']}/{q0[ARM_CONTROL]['denominator']} | {analysis['sensitivity']['q0_only']['control_minus_treated']:.3f} |",
            "",
            "Strict rule의 각 conjunct도 같은 방향으로 분리된다. Alternative-fix-exists=yes는 treated "
            "11/12와 control 6/24이고, hindsight-nonunique는 treated 10/12와 control 5/24다.",
            "",
            "## Claim boundary",
            "",
            "이 결과는 7개 repository의 benchmark-solved 36행 matched frame 안에서 strict rule의 "
            "판별 타당도를 지지한다. 480행 전체의 masking prevalence, label이나 resolution의 인과 효과, "
            "완전한 rule specificity 또는 broad APR population 일반화를 뜻하지 않는다.",
            "",
        ]
    )


def _tex(analysis: dict[str, Any]) -> str:
    treated = analysis["primary_strict_masking"][ARM_TREATED]
    control = analysis["primary_strict_masking"][ARM_CONTROL]
    contrast = analysis["treated_control_contrast"]
    interval = contrast["repository_clustered_bootstrap_95_ci"]
    return "\n".join(
        [
            "% Generated by scripts/analyze_repo480_rq2_control.py; do not edit manually.",
            "\\begin{table}[t]",
            "\\caption{Matched negative-control validation of the RQ2 strict masking rule.}",
            "\\label{tab:repo480rq2control}",
            "\\centering",
            "\\small",
            "\\begin{tabular}{@{}p{0.42\\linewidth}p{0.18\\linewidth}p{0.31\\linewidth}@{}}",
            "\\hline",
            "Analysis & Masked & Estimate / 95\\% interval \\\\",
            "\\hline",
            f"Solved P2/P3 treated & {treated['count']}/{treated['denominator']} & {treated['proportion']:.3f} [{treated['wilson_95_ci']['lower']:.3f}, {treated['wilson_95_ci']['upper']:.3f}] Wilson \\\\",
            f"Matched solved P0/P1 control & {control['count']}/{control['denominator']} & {control['proportion']:.3f} [{control['wilson_95_ci']['lower']:.3f}, {control['wilson_95_ci']['upper']:.3f}] Wilson \\\\",
            f"Control minus treated & --- & {contrast['estimate']:.3f} [{interval['lower']:.3f}, {interval['upper']:.3f}] cluster bootstrap \\\\",
            "\\hline",
            "\\end{tabular}",
            "\\begin{minipage}{0.94\\linewidth}",
            "\\footnotesize",
            "\\emph{Notes:} The same blinded panel labels both arms. The contrast interval exhaustively enumerates all ordered resamples of seven repository clusters. The separately staffed original RQ2 panel remains 12/12 and is not pooled with this matched-panel replication.",
            "\\end{minipage}",
            "\\end{table}",
            "",
        ]
    )


def _index(rows: list[dict[str, Any]], name: str) -> dict[str, dict[str, Any]]:
    result = {}
    for row in rows:
        task_id = row.get("task_id")
        if not isinstance(task_id, str) or not task_id or task_id in result:
            raise ValueError(f"{name}: invalid or duplicate task_id")
        result[task_id] = row
    return result


def _require_hash(path: Path, expected: str, label: str) -> None:
    actual = sha256_file(path)
    if actual != expected:
        raise ValueError(f"{label} SHA-256 mismatch: expected {expected}, found {actual}")


def _artifact(path: Path) -> dict[str, str]:
    return {"ref": _ref(path), "sha256": sha256_file(path)}


def _ref(path: Path) -> str:
    absolute = path.resolve()
    try:
        return str(absolute.relative_to(ROOT))
    except ValueError:
        return str(absolute)


def _absolute(path: Path) -> Path:
    return path if path.is_absolute() else ROOT / path


def _jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def _object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text())
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def _round(value: float) -> float:
    return round(value, 6)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
