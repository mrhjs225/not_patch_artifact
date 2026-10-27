#!/usr/bin/env python3
"""Analyze the accepted repo480 independent boundary-validation panel."""

from __future__ import annotations

import argparse
import collections
import json
import math
import random
import sys
from pathlib import Path
from statistics import NormalDist
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
for path in (ROOT, SRC):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from notpatch.canonical import canonical_json_bytes, sha256_file  # noqa: E402
from scripts.selfcheck_repo480_bv_adjudication_return import validate_return  # noqa: E402

FRAME_N = 480
CONSENSUS_POPULATION = 410
UNION_POPULATION = 70
BOOTSTRAP_SEED = 20260818
BOOTSTRAP_SAMPLES = 10_000
FROZEN_LABEL_SHA256 = "98b33aabbd10b34bd093c4590c2f6c42476f999dd0e60e64794dbb0544f4e63d"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--batch-manifest",
        type=Path,
        default=Path("data/manifests/generated/repo480_boundary_validation_manifest_v1.json"),
    )
    parser.add_argument(
        "--raw-returns-manifest",
        type=Path,
        default=Path(
            "data/manifests/generated/repo480_boundary_validation_returns_manifest_v1.json"
        ),
    )
    parser.add_argument(
        "--adjudication-returns-manifest",
        type=Path,
        default=Path(
            "data/manifests/generated/repo480_bv_adjudication_returns_manifest_v1.json"
        ),
    )
    parser.add_argument(
        "--selection",
        type=Path,
        default=Path(
            "data/annotations/worklists/repo480_boundary_validation_selection_v1.jsonl"
        ),
    )
    parser.add_argument(
        "--frozen-labels",
        type=Path,
        default=Path("data/annotations/adjudicated/repo480_available_v1.jsonl"),
    )
    parser.add_argument(
        "--panel-out",
        type=Path,
        default=Path(
            "data/annotations/oracle_gap/repo480_boundary_validation_panel/"
            "repo480_boundary_validation_adjudicated_v1.jsonl"
        ),
    )
    parser.add_argument(
        "--json-out",
        type=Path,
        default=Path("results/pilot/repo480_boundary_validation_analysis_v1.json"),
    )
    parser.add_argument(
        "--rows-out",
        type=Path,
        default=Path("results/pilot/repo480_boundary_validation_analysis_rows_v1.jsonl"),
    )
    parser.add_argument(
        "--markdown-out",
        type=Path,
        default=Path("results/pilot/repo480_boundary_validation_analysis_v1.md"),
    )
    args = parser.parse_args()
    try:
        analysis, panel, rows = analyze(args)
        _write_jsonl(args.panel_out, panel)
        analysis["canonical_panel"] = _artifact(args.panel_out)
        _write_json(args.json_out, analysis)
        _write_jsonl(args.rows_out, rows)
        _write_text(args.markdown_out, _markdown(analysis))
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1
    primary = analysis["independent_stratified_prevalence"]
    print(
        "OK: independent boundary estimate "
        f"{primary['proportion']:.6f} "
        f"(95% CI [{primary['interval_95']['lower']:.6f}, "
        f"{primary['interval_95']['upper']:.6f}])"
    )
    return 0


def analyze(
    args: argparse.Namespace,
) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
    batch_manifest = _object(args.batch_manifest)
    raw_manifest = _object(args.raw_returns_manifest)
    adj_manifest = _object(args.adjudication_returns_manifest)
    _verify_manifests(batch_manifest, raw_manifest, adj_manifest, args)

    raw_paths = {
        role: ROOT / raw_manifest["returns"][role]["ref"]
        for role in ("repo480_bv_r1", "repo480_bv_r2")
    }
    raw = {role: _index(_jsonl(path), role) for role, path in raw_paths.items()}
    worklist_path = ROOT / adj_manifest["worklist"]["ref"]
    if not worklist_path.exists():
        adj_batch_ref = Path(adj_manifest["batch_manifest"]["ref"])
        if sha256_file(ROOT / adj_batch_ref) != adj_manifest["batch_manifest"]["sha256"]:
            raise ValueError("adjudication batch manifest hash mismatch")
        canonical_worklist = _object(adj_batch_ref).get("worklist", {})
        if canonical_worklist.get("sha256") != adj_manifest["worklist"].get("sha256"):
            raise ValueError("retired adjudication worklist does not match the canonical hash")
        worklist_path = ROOT / canonical_worklist.get("ref", "")
        if sha256_file(worklist_path) != canonical_worklist.get("sha256"):
            raise ValueError("canonical adjudication worklist hash mismatch")
    worklist = _jsonl(worklist_path)
    decisions_path = ROOT / adj_manifest["return"]["ref"]
    decisions = _jsonl(decisions_path)
    validate_return(worklist, decisions)
    decision_by_task = _index(decisions, "adjudication")
    selection = _jsonl(ROOT / args.selection)
    frozen = _index(_jsonl(ROOT / args.frozen_labels), "frozen labels")

    panel = []
    rows = []
    for selected in selection:
        task_id = selected["task_id"]
        left = raw["repo480_bv_r1"][task_id]
        right = raw["repo480_bv_r2"][task_id]
        if left["ordinal"] != selected["ordinal"] or right["ordinal"] != selected["ordinal"]:
            raise ValueError(f"{task_id}: selection/raw ordinal mismatch")
        decision = decision_by_task.get(task_id)
        if decision is None:
            if not _controlled_equal(left["annotation_fields"], right["annotation_fields"]):
                raise ValueError(f"{task_id}: missing adjudication for controlled-field dispute")
            base_role = "repo480_bv_r1"
            fields = dict(left["annotation_fields"])
            source = "exact_controlled_field_consensus"
            overrides: dict[str, Any] = {}
            notes = None
        else:
            if decision["adjudication_status"] != "adjudicated":
                raise ValueError(f"{task_id}: unresolved adjudication")
            base_role = decision["base_annotator"]
            fields = dict(raw[base_role][task_id]["annotation_fields"])
            overrides = decision["overrides"]
            fields.update(overrides)
            source = "third_expert_adjudication"
            notes = decision["resolution_notes"]
        if fields.get("primary_label") not in {"P0", "P1", "P2", "P3"}:
            raise ValueError(f"{task_id}: invalid final primary label")
        base = raw[base_role][task_id]
        panel_row = {
            "schema_version": "repo480-boundary-validation-adjudicated-v1",
            "annotation_batch_id": "repo480_boundary_validation_v1",
            "annotator_id": "repo480_bv_adj",
            "adjudication_status": "adjudicated",
            "ordinal": selected["ordinal"],
            "task_id": task_id,
            "repo": base["repo"],
            "stratum": selected["stratum"],
            "stratum_population": selected["stratum_population"],
            "prevalence_random_rank": selected["prevalence_random_rank"],
            "reviewer_view_hash": base["reviewer_view_hash"],
            "reviewer_view_ref": base["reviewer_view_ref"],
            "adjudication_source": source,
            "base_annotator": base_role,
            "overrides": overrides,
            "resolution_notes": notes,
            "annotation_fields": fields,
        }
        panel.append(panel_row)
        frozen_label = frozen[task_id]["primary_label"]
        weight = 1.0 if selected["stratum"] == "raw_union_p23" else 410 / 150
        rows.append(
            {
                "schema_version": "repo480-boundary-validation-analysis-row-v1",
                "ordinal": selected["ordinal"],
                "task_id": task_id,
                "repo": base["repo"],
                "stratum": selected["stratum"],
                "analysis_weight": round(weight, 12),
                "independent_primary_label": fields["primary_label"],
                "independent_binary_label": _binary(fields["primary_label"]),
                "independent_data_quality": fields["data_quality"],
                "frozen_primary_label": frozen_label,
                "frozen_binary_label": _binary(frozen_label),
                "binary_match": _binary(fields["primary_label"]) == _binary(frozen_label),
                "raw_r1_primary_label": left["annotation_fields"]["primary_label"],
                "raw_r2_primary_label": right["annotation_fields"]["primary_label"],
                "adjudication_source": source,
            }
        )

    if len(panel) != 220 or len({row["task_id"] for row in panel}) != 220:
        raise ValueError("final panel must contain 220 unique rows")
    primary = _stratified(rows, "independent_binary_label")
    incumbent = 26 / 480
    primary["covers_frozen_26_of_480"] = (
        primary["interval_95"]["lower"] <= incumbent <= primary["interval_95"]["upper"]
    )
    primary["comparison_value"] = incumbent
    decision = (
        "retain_adjudicated_26_of_480_as_preferred_estimate"
        if primary["covers_frozen_26_of_480"]
        else "demote_26_of_480_to_rule_sensitivity_member"
    )

    evidence_use = {
        role: _evidence_use(list(records.values())) for role, records in raw.items()
    }
    raw_sensitivity = _raw_sensitivities(rows)
    agreement = {
        "all_220": _agreement(rows),
        "by_stratum": {
            stratum: _agreement([row for row in rows if row["stratum"] == stratum])
            for stratum in ("raw_union_p23", "raw_consensus_p01")
        },
    }
    analysis = {
        "schema_version": "repo480-boundary-validation-analysis-v1",
        "analysis_id": "repo480-boundary-validation-analysis-v1",
        "annotation_batch_id": "repo480_boundary_validation_v1",
        "estimand": (
            "stratified P2/P3 prevalence in the frozen 480-task frame under the "
            "independent panel's adjudicated available-only judgments"
        ),
        "statistics": {
            "confidence_level": 0.95,
            "primary_interval": "Wilson score with consensus-stratum finite population correction",
            "bootstrap_seed": BOOTSTRAP_SEED,
            "bootstrap_samples": BOOTSTRAP_SAMPLES,
            "bootstrap_interval": "repository-cluster percentile interval on survey weights",
        },
        "inputs": {
            "batch_manifest": _artifact(args.batch_manifest),
            "raw_returns_manifest": _artifact(args.raw_returns_manifest),
            "adjudication_returns_manifest": _artifact(args.adjudication_returns_manifest),
            "selection": _artifact(args.selection),
            "frozen_labels": _artifact(args.frozen_labels),
            "raw_returns": {role: _artifact(path) for role, path in raw_paths.items()},
            "adjudication_return": _artifact(decisions_path),
        },
        "integrity": {
            "panel_rows": len(panel),
            "unique_task_ids": True,
            "raw_task_sets_match_selection": all(set(records) == {row["task_id"] for row in selection} for records in raw.values()),
            "adjudication_rows": len(decisions),
            "unresolved_rows": 0,
            "protocol_deviation_count": adj_manifest["acceptance_gate"][
                "protocol_deviation_count"
            ],
            "frozen_hashes_verified": True,
        },
        "independent_stratified_prevalence": primary,
        "decision_rule_outcome": decision,
        "agreement_with_frozen_adjudicated_boundary": agreement,
        "raw_panel_sensitivity": raw_sensitivity,
        "q0_only_sensitivity": _q0_sensitivity(rows),
        "union_stratum_census": _union_census(rows),
        "repository_cluster_sensitivity": _cluster_bootstrap(rows),
        "raw_evidence_use_audit": evidence_use,
        "claim_boundary": {
            "frozen_labels_unchanged": True,
            "independent_panel_is_separate_estimate": True,
            "preferred_estimate_decision": decision,
            "evidence_use_threat": (
                "The second raw pass recorded issue-title/body evidence only; the adjudicator "
                "used the frozen packet. Interpret panel reproducibility with this asymmetric "
                "evidence-utilization limitation."
            ),
        },
    }
    return analysis, panel, rows


def _verify_manifests(
    batch: dict[str, Any], raw: dict[str, Any], adj: dict[str, Any], args: argparse.Namespace
) -> None:
    if batch.get("schema_version") != "repo480-boundary-validation-manifest-v1":
        raise ValueError("boundary-validation manifest schema mismatch")
    required_raw = (
        "all_rows_returned",
        "frozen_baseline_diff_verified",
        "immutable_linkage_passed",
        "next_stage_release_allowed",
        "selfcheck_passed",
    )
    if not all(raw.get("acceptance_gate", {}).get(key) is True for key in required_raw):
        raise ValueError("raw return acceptance gate is not closed")
    required_adj = (*required_raw, "all_rows_adjudicated")
    if not all(adj.get("acceptance_gate", {}).get(key) is True for key in required_adj):
        raise ValueError("adjudication acceptance gate is not closed")
    if raw["batch_manifest"]["sha256"] != sha256_file(ROOT / args.batch_manifest):
        raise ValueError("raw returns manifest does not link current batch manifest")
    if sha256_file(ROOT / args.selection) != batch["selection"]["sha256"]:
        raise ValueError("selection hash mismatch")
    if sha256_file(ROOT / args.frozen_labels) != FROZEN_LABEL_SHA256:
        raise ValueError("frozen label hash mismatch")
    for role, entry in raw["returns"].items():
        if sha256_file(ROOT / entry["ref"]) != entry["sha256"]:
            raise ValueError(f"{role}: raw return hash mismatch")
    if sha256_file(ROOT / adj["return"]["ref"]) != adj["return"]["sha256"]:
        raise ValueError("adjudication return hash mismatch")


def _controlled_equal(left: dict[str, Any], right: dict[str, Any]) -> bool:
    fields = ("primary_label", "primary_blocker", "data_quality", "predicted_direction")
    return all(left.get(field) == right.get(field) for field in fields)


def _stratified(rows: list[dict[str, Any]], field: str) -> dict[str, Any]:
    union = [row for row in rows if row["stratum"] == "raw_union_p23"]
    consensus = [row for row in rows if row["stratum"] == "raw_consensus_p01"]
    if len(union) != UNION_POPULATION or len(consensus) != 150:
        raise ValueError("stratum sample sizes do not match the frozen design")
    union_positive = sum(row[field] == "P2/P3" for row in union)
    consensus_positive = sum(row[field] == "P2/P3" for row in consensus)
    consensus_rate = consensus_positive / len(consensus)
    effective_numerator = union_positive + CONSENSUS_POPULATION * consensus_rate
    lower, upper = _wilson_fpc(consensus_positive, len(consensus), CONSENSUS_POPULATION)
    return {
        "effective_numerator": round(effective_numerator, 6),
        "denominator": FRAME_N,
        "proportion": round(effective_numerator / FRAME_N, 6),
        "interval_95": {
            "lower": round((union_positive + CONSENSUS_POPULATION * lower) / FRAME_N, 6),
            "upper": round((union_positive + CONSENSUS_POPULATION * upper) / FRAME_N, 6),
        },
        "strata": {
            "raw_union_p23": {
                "population": UNION_POPULATION,
                "sample": len(union),
                "positive": union_positive,
                "census": True,
            },
            "raw_consensus_p01": {
                "population": CONSENSUS_POPULATION,
                "sample": len(consensus),
                "positive": consensus_positive,
                "sample_proportion": round(consensus_rate, 6),
                "finite_population_fraction": round(len(consensus) / CONSENSUS_POPULATION, 6),
            },
        },
    }


def _wilson_fpc(positive: int, sample: int, population: int) -> tuple[float, float]:
    z = NormalDist().inv_cdf(0.975)
    p = positive / sample
    fpc = (population - sample) / (population - 1)
    denominator = 1 + z * z / sample
    center = (p + z * z / (2 * sample)) / denominator
    spread = z / denominator * math.sqrt(
        fpc * p * (1 - p) / sample + z * z / (4 * sample * sample)
    )
    return max(0.0, center - spread), min(1.0, center + spread)


def _agreement(rows: list[dict[str, Any]]) -> dict[str, Any]:
    pairs = [(row["independent_binary_label"], row["frozen_binary_label"]) for row in rows]
    observed = sum(left == right for left, right in pairs) / len(pairs)
    left = collections.Counter(left for left, _ in pairs)
    right = collections.Counter(right for _, right in pairs)
    expected = sum(
        left[label] / len(pairs) * right[label] / len(pairs) for label in set(left) | set(right)
    )
    kappa = None if math.isclose(expected, 1.0) else (observed - expected) / (1 - expected)
    cells = collections.Counter(pairs)
    return {
        "n": len(rows),
        "agreement_count": sum(left == right for left, right in pairs),
        "observed_agreement": round(observed, 6),
        "cohen_kappa": None if kappa is None else round(kappa, 6),
        "pabak": round(2 * observed - 1, 6),
        "cells": {f"{left}|{right}": cells[(left, right)] for left in ("P0/P1", "P2/P3") for right in ("P0/P1", "P2/P3")},
    }


def _raw_sensitivities(rows: list[dict[str, Any]]) -> dict[str, Any]:
    variants = {}
    for name in ("r1", "r2", "intersection", "union"):
        derived = []
        for row in rows:
            left = _binary(row["raw_r1_primary_label"])
            right = _binary(row["raw_r2_primary_label"])
            if name == "r1":
                value = left
            elif name == "r2":
                value = right
            elif name == "intersection":
                value = "P2/P3" if left == right == "P2/P3" else "P0/P1"
            else:
                value = "P2/P3" if "P2/P3" in (left, right) else "P0/P1"
            derived.append({**row, "raw_variant": value})
        variants[name] = _stratified(derived, "raw_variant")
    return variants


def _q0_sensitivity(rows: list[dict[str, Any]]) -> dict[str, Any]:
    weighted_q0 = sum(row["analysis_weight"] for row in rows if row["independent_data_quality"] == "Q0")
    weighted_positive = sum(
        row["analysis_weight"]
        for row in rows
        if row["independent_data_quality"] == "Q0"
        and row["independent_binary_label"] == "P2/P3"
    )
    return {
        "estimated_q0_denominator": round(weighted_q0, 6),
        "estimated_q0_p2p3": round(weighted_positive, 6),
        "proportion": round(weighted_positive / weighted_q0, 6),
        "interpretation": "survey-weighted ratio among Q0 rows; point sensitivity only",
    }


def _union_census(rows: list[dict[str, Any]]) -> dict[str, Any]:
    union = [row for row in rows if row["stratum"] == "raw_union_p23"]
    positive = sum(row["independent_binary_label"] == "P2/P3" for row in union)
    return {"positive": positive, "denominator": len(union), "proportion": round(positive / len(union), 6)}


def _cluster_bootstrap(rows: list[dict[str, Any]]) -> dict[str, Any]:
    clusters: dict[str, list[dict[str, Any]]] = collections.defaultdict(list)
    for row in rows:
        clusters[row["repo"]].append(row)
    repos = sorted(clusters)
    rng = random.Random(BOOTSTRAP_SEED)
    values = []
    for _ in range(BOOTSTRAP_SAMPLES):
        sampled = [rng.choice(repos) for _ in repos]
        numerator = sum(
            row["analysis_weight"]
            for repo in sampled
            for row in clusters[repo]
            if row["independent_binary_label"] == "P2/P3"
        )
        denominator = sum(row["analysis_weight"] for repo in sampled for row in clusters[repo])
        values.append(numerator / denominator)
    values.sort()
    return {
        "repository_count": len(repos),
        "bootstrap_95_ci": {
            "lower": round(_percentile(values, 0.025), 6),
            "upper": round(_percentile(values, 0.975), 6),
        },
    }


def _evidence_use(records: list[dict[str, Any]]) -> dict[str, Any]:
    repository_fields = {"retrieved_code", "visible_tests", "docs", "config"}
    repository_rows = sum(
        bool(repository_fields & set(row["annotation_fields"]["available_evidence_used"]))
        for row in records
    )
    issue_only = sum(
        set(row["annotation_fields"]["available_evidence_used"])
        <= {"issue_title", "issue_body"}
        for row in records
    )
    return {
        "row_count": len(records),
        "rows_recording_repository_evidence": repository_rows,
        "rows_recording_issue_text_only": issue_only,
    }


def _binary(label: str) -> str:
    return "P2/P3" if label in {"P2", "P3"} else "P0/P1"


def _percentile(values: list[float], q: float) -> float:
    position = q * (len(values) - 1)
    lower = int(position)
    upper = min(lower + 1, len(values) - 1)
    fraction = position - lower
    return values[lower] * (1 - fraction) + values[upper] * fraction


def _markdown(analysis: dict[str, Any]) -> str:
    primary = analysis["independent_stratified_prevalence"]
    agreement = analysis["agreement_with_frozen_adjudicated_boundary"]["all_220"]
    evidence = analysis["raw_evidence_use_audit"]
    return f"""# Repo480 independent boundary-validation analysis

- **Status:** `final`
- **Authority:** RR-A independent panel estimate and preferred-rule decision

## Observation

The adjudicated independent panel yields a stratified P2/P3 estimate of
`{primary['proportion']:.3f}` with a finite-population-adjusted 95% interval
`[{primary['interval_95']['lower']:.3f}, {primary['interval_95']['upper']:.3f}]`.
The union census contributes `{primary['strata']['raw_union_p23']['positive']}/70` positives and
the consensus sample contributes `{primary['strata']['raw_consensus_p01']['positive']}/150`.

Binary agreement with the frozen adjudicated boundary is `{agreement['agreement_count']}/220`
(Cohen kappa `{agreement['cohen_kappa']:.3f}`, PABAK `{agreement['pabak']:.3f}`).

## Interpretation

The interval {'contains' if primary['covers_frozen_26_of_480'] else 'does not contain'} the frozen
`26/480=0.054` estimate. The prespecified decision is
`{analysis['decision_rule_outcome']}`. The frozen labels remain unchanged; this panel is a separate
estimate.

## Evidence-use limitation

R1 recorded repository evidence on `{evidence['repo480_bv_r1']['rows_recording_repository_evidence']}/220`
rows, whereas R2 recorded it on `{evidence['repo480_bv_r2']['rows_recording_repository_evidence']}/220`
rows and recorded issue text only on `{evidence['repo480_bv_r2']['rows_recording_issue_text_only']}/220`.
The adjudicator used the frozen packet, but this asymmetric utilization limits the interpretation
of raw-panel reproducibility.
"""


def _artifact(path: Path) -> dict[str, Any]:
    full = ROOT / path if not path.is_absolute() else path
    return {"ref": str(full.relative_to(ROOT)), "sha256": sha256_file(full)}


def _object(path: Path) -> dict[str, Any]:
    with (ROOT / path).open(encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain an object")
    return value


def _jsonl(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def _index(rows: list[dict[str, Any]], name: str) -> dict[str, dict[str, Any]]:
    result = {}
    for row in rows:
        task_id = row.get("task_id")
        if not isinstance(task_id, str) or not task_id or task_id in result:
            raise ValueError(f"{name}: invalid or duplicate task_id")
        result[task_id] = row
    return result


def _write_json(path: Path, value: Any) -> None:
    full = ROOT / path if not path.is_absolute() else path
    full.parent.mkdir(parents=True, exist_ok=True)
    full.write_bytes(canonical_json_bytes(value))


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    full = ROOT / path if not path.is_absolute() else path
    full.parent.mkdir(parents=True, exist_ok=True)
    full.write_bytes(b"".join(canonical_json_bytes(row) for row in rows))


def _write_text(path: Path, value: str) -> None:
    full = ROOT / path if not path.is_absolute() else path
    full.parent.mkdir(parents=True, exist_ok=True)
    full.write_text(value, encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
