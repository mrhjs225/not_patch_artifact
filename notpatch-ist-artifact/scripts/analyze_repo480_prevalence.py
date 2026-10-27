#!/usr/bin/env python3
"""Recalculate RQ1 prevalence and sensitivity for the frozen repo480 frame."""

from __future__ import annotations

import argparse
import json
import math
import random
import sys
from collections import Counter, defaultdict
from pathlib import Path
from statistics import NormalDist
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from notpatch.canonical import canonical_json_bytes, sha256_file  # noqa: E402
from notpatch.schemas import ValidationError, validate_record  # noqa: E402
from summarize_agreement import _cohen_kappa  # noqa: E402


EXPECTED_FULL_COUNT = 480
EXPECTED_NESTED_COUNT = 120
PRIMARY_LABELS = ("P0", "P1", "P2", "P3")
BOOTSTRAP_SEED = 20260720
BOOTSTRAP_SAMPLES = 10_000
CONFIDENCE_LEVEL = 0.95

DEFAULT_PATHS = {
    "r1": ROOT / "data/annotations/raw_labels/repo480_available_v1_r1.jsonl",
    "r2": ROOT / "data/annotations/raw_labels/repo480_available_v1_r2.jsonl",
    "final": ROOT / "data/annotations/adjudicated/repo480_available_v1.jsonl",
    "issue_seed": ROOT
    / "data/annotations/adjudicated/swebench_full_prevalence_random_480_adjudicated.jsonl",
    "split_120": ROOT
    / "data/processed/dataset_splits/swebench_full_prevalence_random_120.json",
    "split_480": ROOT
    / "data/processed/dataset_splits/swebench_full_prevalence_random_480.json",
    "json_out": ROOT
    / "results/pilot/repo480_available_v1_prevalence_analysis.json",
    "markdown_out": ROOT
    / "results/pilot/repo480_available_v1_prevalence_analysis.md",
    "rows_out": ROOT
    / "results/pilot/repo480_available_v1_prevalence_rows.jsonl",
    "main_tex_out": ROOT / "paper/generated/repo480_rq1_prevalence_summary.tex",
    "supplement_tex_out": ROOT
    / "paper/generated/repo480_rq1_nested120_audit.tex",
    "validation_analysis": ROOT
    / "results/pilot/repo480_boundary_validation_analysis_v1.json",
}

EXPECTED_SHA256 = {
    "r1": "5318d907093d44ee6eeeb7938c68373a8430bbb7a9e6e488a68a6685592e5a34",
    "r2": "cfd7daaf1f1256d6827e60eba78837cf21ff8d51e52aacb2b1e82ec319aca390",
    "final": "98b33aabbd10b34bd093c4590c2f6c42476f999dd0e60e64794dbb0544f4e63d",
    "issue_seed": "3c745afa68d4b283ddc64f0dd09a1da2b0d4e2e994fca8cb154634cf6165f23f",
    "split_120": "5775350f75541e0b84947e24c7da7030caacdb03319c2c0dc7711eab6b7e7ec4",
    "split_480": "02f47b8096979cbd6cb502eb6416ca25785d1400ecc906acce8fb29062c0d284",
}
# Read only for the main table; kept out of the frozen analysis JSON.
VALIDATION_ANALYSIS_SHA256 = (
    "9879635db928cd92637d36fafc72ed2cb8972267ff89a06d37025d31228fe605"
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    for role in ("r1", "r2", "final", "issue_seed", "split_120", "split_480"):
        parser.add_argument(
            f"--{role.replace('_', '-')}", type=Path, default=DEFAULT_PATHS[role]
        )
    parser.add_argument("--json-out", type=Path, default=DEFAULT_PATHS["json_out"])
    parser.add_argument(
        "--markdown-out", type=Path, default=DEFAULT_PATHS["markdown_out"]
    )
    parser.add_argument("--rows-out", type=Path, default=DEFAULT_PATHS["rows_out"])
    parser.add_argument(
        "--main-tex-out", type=Path, default=DEFAULT_PATHS["main_tex_out"]
    )
    parser.add_argument(
        "--supplement-tex-out",
        type=Path,
        default=DEFAULT_PATHS["supplement_tex_out"],
    )
    parser.add_argument(
        "--validation-analysis",
        type=Path,
        default=DEFAULT_PATHS["validation_analysis"],
    )
    args = parser.parse_args()

    inputs = {
        role: getattr(args, role)
        for role in ("r1", "r2", "final", "issue_seed", "split_120", "split_480")
    }
    try:
        analysis, rows = analyze(inputs)
        validation = load_validation_estimate(args.validation_analysis)
        outputs = {
            args.json_out: canonical_json_bytes(analysis),
            args.markdown_out: build_markdown(analysis).encode("utf-8"),
            args.rows_out: b"".join(canonical_json_bytes(row) for row in rows),
            args.main_tex_out: build_main_tex(analysis, validation).encode("utf-8"),
            args.supplement_tex_out: build_supplement_tex(analysis, rows).encode(
                "utf-8"
            ),
        }
        for path, content in outputs.items():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content)
    except (OSError, json.JSONDecodeError, ValidationError, ValueError) as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1

    primary = analysis["primary_480"]["p2p3"]
    print(
        "OK: wrote repo480 RQ1 prevalence analysis "
        f"({primary['count']}/{primary['denominator']} P2/P3)"
    )
    return 0


def analyze(inputs: dict[str, Path]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    input_metadata = _validate_frozen_inputs(inputs)
    annotations = {
        "r1": _load_annotations(inputs["r1"], "repo480_r1"),
        "r2": _load_annotations(inputs["r2"], "repo480_r2"),
        "final": _load_annotations(inputs["final"], "adjudicated"),
        "issue_seed": _load_annotations(inputs["issue_seed"], "adjudicated"),
    }
    split_120 = _load_split(inputs["split_120"], EXPECTED_NESTED_COUNT)
    split_480 = _load_split(inputs["split_480"], EXPECTED_FULL_COUNT)
    for role, records in annotations.items():
        input_metadata[role]["row_count"] = len(records)
    input_metadata["split_120"]["row_count"] = len(split_120)
    input_metadata["split_480"]["row_count"] = len(split_480)

    indexed = {role: _index(records, role) for role, records in annotations.items()}
    full_ids = set(split_480)
    nested_ids = set(split_120)
    if not nested_ids < full_ids:
        raise ValueError("split_120 must be a proper subset of split_480")
    for role, records in indexed.items():
        if set(records) != full_ids:
            raise ValueError(f"{role} task set does not match split_480")
    _validate_nested_prefix(split_120, split_480)
    _validate_final_status(indexed["final"])

    ordered_ids = [row["task_id"] for row in split_480.values()]
    nested_ordered_ids = [row["task_id"] for row in split_120.values()]
    full = _summarize_frame(ordered_ids, indexed)
    nested = _summarize_frame(nested_ordered_ids, indexed)
    evidence_policy = _evidence_policy_sensitivity(ordered_ids, indexed)
    cluster = _repository_cluster_sensitivity(ordered_ids, indexed, split_480)
    rows = _build_rows(ordered_ids, nested_ids, indexed, split_480)

    analysis = {
        "schema_version": "repo480-prevalence-analysis-v1",
        "analysis_id": "repo480-available-v1-rq1-prevalence",
        "packet_policy_id": "swebench-repo480-v1",
        "estimand": (
            "proportion of the frozen 480-task SWE-bench frame adjudicated P2/P3 "
            "under the swebench-repo480-v1 task-time packet policy"
        ),
        "claim_scope": {
            "reports": [
                "480-row repository-packet P2/P3 precision estimate",
                "nested-120 reliability and deep-audit diagnostics",
                "reviewer-rule and issue-packet-to-repository-packet sensitivity",
                "within-frame repository-cluster sensitivity",
            ],
            "does_not_report": [
                "broad APR population prevalence",
                "causal effect of repository evidence alone",
                "external or institutional reviewer independence",
                "RQ2 oracle-masking numerator or denominator",
            ],
        },
        "statistics": {
            "confidence_level": CONFIDENCE_LEVEL,
            "row_interval": "Wilson score interval",
            "bootstrap_seed": BOOTSTRAP_SEED,
            "bootstrap_samples": BOOTSTRAP_SAMPLES,
            "bootstrap_interval": "linear-interpolated percentile interval",
        },
        "inputs": input_metadata,
        "integrity": {
            "full_task_count": len(full_ids),
            "nested_task_count": len(nested_ids),
            "unique_task_ids_per_input": True,
            "annotation_task_sets_equal_split_480": True,
            "nested_120_is_rank_prefix_of_480": True,
            "all_final_rows_adjudicated": True,
            "all_frozen_sha256_verified": True,
        },
        "primary_480": {
            # Kept byte-stable: downstream artifacts record this JSON's SHA-256.
            "role": "primary prevalence precision estimate",
            **full["adjudicated"],
            "retrieval_sufficiency_counts": full["retrieval_sufficiency_counts"],
            "p2p3_retrieval_sufficiency_counts": full[
                "p2p3_retrieval_sufficiency_counts"
            ],
        },
        "raw_reviewer_reliability": {
            "full_480": full["agreement"],
            "nested_120": nested["agreement"],
            "interpretation": (
                "raw agreement and kappa measure reproducibility before adjudication; "
                "marginal count differences are retained as reviewer-rule sensitivity"
            ),
        },
        "reviewer_rule_sensitivity": {
            "full_480": full["reviewer_rules"],
            "nested_120": nested["reviewer_rules"],
            "two_of_three_note": (
                "the adjudicated label is derived from the two raw passes, so this "
                "two-of-three view is descriptive and not a third independent vote"
            ),
        },
        "nested_120": {
            "role": (
                "nested reliability and row-audit diagnostic; not a replacement "
                "prevalence estimand or an independent second sample"
            ),
            **nested["adjudicated"],
            "retrieval_sufficiency_counts": nested["retrieval_sufficiency_counts"],
            "p2p3_retrieval_sufficiency_counts": nested[
                "p2p3_retrieval_sufficiency_counts"
            ],
            "repository_p2p3_row_count": nested["adjudicated"]["p2p3"]["count"],
        },
        "evidence_policy_sensitivity": evidence_policy,
        "repository_cluster_sensitivity": cluster,
    }
    _validate_analysis(analysis, rows)
    return analysis, rows


def _validate_frozen_inputs(inputs: dict[str, Path]) -> dict[str, dict[str, Any]]:
    if set(inputs) != set(EXPECTED_SHA256):
        raise ValueError("input roles do not match the frozen analysis contract")
    metadata = {}
    for role in ("r1", "r2", "final", "issue_seed", "split_120", "split_480"):
        actual = sha256_file(inputs[role])
        expected = EXPECTED_SHA256[role]
        if actual != expected:
            raise ValueError(
                f"{role} SHA-256 mismatch: expected {expected}, found {actual}"
            )
        metadata[role] = {
            "path": _display_path(inputs[role]),
            "sha256": actual,
            "frozen_sha256_verified": True,
        }
    return metadata


def _load_annotations(path: Path, expected_annotator: str) -> list[dict[str, Any]]:
    records = _load_jsonl(path)
    if len(records) != EXPECTED_FULL_COUNT:
        raise ValueError(
            f"{path}: expected {EXPECTED_FULL_COUNT} rows, found {len(records)}"
        )
    for line_no, record in enumerate(records, start=1):
        validate_record(record, "annotation")
        if record.get("annotator_id") != expected_annotator:
            raise ValueError(
                f"{path}:{line_no}: expected annotator_id={expected_annotator}"
            )
        if record.get("pass") != "available_only":
            raise ValueError(f"{path}:{line_no}: pass must be available_only")
        if record.get("primary_label") not in PRIMARY_LABELS:
            raise ValueError(f"{path}:{line_no}: unsupported primary_label")
    return records


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    records = []
    with path.open("r", encoding="utf-8") as handle:
        for line_no, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            value = json.loads(line)
            if not isinstance(value, dict):
                raise ValueError(f"{path}:{line_no}: expected object")
            records.append(value)
    return records


def _load_split(path: Path, expected_count: int) -> dict[str, dict[str, Any]]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict) or not isinstance(value.get("tasks"), list):
        raise ValueError(f"{path}: split.tasks must be a list")
    tasks = value["tasks"]
    if len(tasks) != expected_count or value.get("n_sampled") != expected_count:
        raise ValueError(f"{path}: expected {expected_count} sampled tasks")
    indexed = _index(tasks, str(path))
    ranks = [record.get("prevalence_random_rank") for record in tasks]
    if ranks != list(range(1, expected_count + 1)):
        raise ValueError(f"{path}: tasks must be ordered by consecutive random rank")
    return indexed


def _index(
    records: Iterable[dict[str, Any]], name: str
) -> dict[str, dict[str, Any]]:
    indexed = {}
    for record in records:
        task_id = record.get("task_id")
        if not isinstance(task_id, str) or not task_id:
            raise ValueError(f"{name}: row without task_id")
        if task_id in indexed:
            raise ValueError(f"{name}: duplicate task_id {task_id}")
        indexed[task_id] = record
    return indexed


def _validate_nested_prefix(
    split_120: dict[str, dict[str, Any]], split_480: dict[str, dict[str, Any]]
) -> None:
    nested_ids = list(split_120)
    full_prefix = list(split_480)[:EXPECTED_NESTED_COUNT]
    if nested_ids != full_prefix:
        raise ValueError("split_120 task order must equal the first 120 split_480 tasks")
    for task_id in nested_ids:
        for field in ("task_id", "base_commit", "repo", "prevalence_random_rank"):
            if split_120[task_id].get(field) != split_480[task_id].get(field):
                raise ValueError(f"{task_id}: split linkage mismatch for {field}")


def _validate_final_status(final: dict[str, dict[str, Any]]) -> None:
    invalid = [
        task_id
        for task_id, record in final.items()
        if record.get("adjudication_status") != "adjudicated"
    ]
    if invalid:
        raise ValueError(f"final contains non-adjudicated rows: {invalid[:5]}")


def _summarize_frame(
    task_ids: list[str], indexed: dict[str, dict[str, dict[str, Any]]]
) -> dict[str, Any]:
    r1 = indexed["r1"]
    r2 = indexed["r2"]
    final = indexed["final"]
    issue_seed = indexed["issue_seed"]
    label_pairs = [(r1[item]["primary_label"], r2[item]["primary_label"]) for item in task_ids]
    binary_pairs = [(_binary(left), _binary(right)) for left, right in label_pairs]
    rules = {
        "raw_r1": _rate(sum(_is_p2p3(r1[item]) for item in task_ids), len(task_ids)),
        "raw_r2": _rate(sum(_is_p2p3(r2[item]) for item in task_ids), len(task_ids)),
        "raw_intersection": _rate(
            sum(_is_p2p3(r1[item]) and _is_p2p3(r2[item]) for item in task_ids),
            len(task_ids),
        ),
        "raw_union": _rate(
            sum(_is_p2p3(r1[item]) or _is_p2p3(r2[item]) for item in task_ids),
            len(task_ids),
        ),
        "two_of_three_with_adjudicated": _rate(
            sum(
                sum(
                    (
                        _is_p2p3(r1[item]),
                        _is_p2p3(r2[item]),
                        _is_p2p3(final[item]),
                    )
                )
                >= 2
                for item in task_ids
            ),
            len(task_ids),
        ),
        "adjudicated": _rate(
            sum(_is_p2p3(final[item]) for item in task_ids), len(task_ids)
        ),
    }
    return {
        "adjudicated": {
            "task_count": len(task_ids),
            "label_counts": _label_counts(final[item] for item in task_ids),
            "p2p3": rules["adjudicated"],
            "issue_packet_baseline_p2p3": _rate(
                sum(_is_p2p3(issue_seed[item]) for item in task_ids), len(task_ids)
            ),
        },
        "reviewer_rules": rules,
        "agreement": {
            "primary_label": _agreement(label_pairs),
            "binary_label": _agreement(binary_pairs),
            "binary_disagreement_direction_counts": {
                "r1_P0/P1_r2_P2/P3": sum(
                    left == "P0/P1" and right == "P2/P3"
                    for left, right in binary_pairs
                ),
                "r1_P2/P3_r2_P0/P1": sum(
                    left == "P2/P3" and right == "P0/P1"
                    for left, right in binary_pairs
                ),
            },
        },
        "retrieval_sufficiency_counts": dict(
            sorted(Counter(final[item]["retrieval_sufficiency"] for item in task_ids).items())
        ),
        "p2p3_retrieval_sufficiency_counts": dict(
            sorted(
                Counter(
                    final[item]["retrieval_sufficiency"]
                    for item in task_ids
                    if _is_p2p3(final[item])
                ).items()
            )
        ),
    }


def _rate(count: int, denominator: int) -> dict[str, Any]:
    lower, upper = _wilson(count, denominator)
    return {
        "count": count,
        "denominator": denominator,
        "proportion": _round(count / denominator),
        "wilson_95_ci": {"lower": _round(lower), "upper": _round(upper)},
    }


def _wilson(count: int, denominator: int) -> tuple[float, float]:
    if denominator <= 0:
        raise ValueError("Wilson denominator must be positive")
    z = NormalDist().inv_cdf(0.5 + CONFIDENCE_LEVEL / 2)
    proportion = count / denominator
    divisor = 1 + z * z / denominator
    center = proportion + z * z / (2 * denominator)
    spread = z * math.sqrt(
        proportion * (1 - proportion) / denominator
        + z * z / (4 * denominator * denominator)
    )
    return (center - spread) / divisor, (center + spread) / divisor


def _agreement(pairs: list[tuple[str, str]]) -> dict[str, Any]:
    agreement_count = sum(left == right for left, right in pairs)
    return {
        "n": len(pairs),
        "agreement_count": agreement_count,
        "disagreement_count": len(pairs) - agreement_count,
        "observed_agreement": _round(agreement_count / len(pairs)),
        "cohen_kappa": _round(_cohen_kappa(pairs)),
    }


def _evidence_policy_sensitivity(
    task_ids: list[str], indexed: dict[str, dict[str, dict[str, Any]]]
) -> dict[str, Any]:
    issue_seed = indexed["issue_seed"]
    final = indexed["final"]
    pairs = [
        (int(_is_p2p3(issue_seed[item])), int(_is_p2p3(final[item])))
        for item in task_ids
    ]
    issue_count = sum(left for left, _ in pairs)
    repository_count = sum(right for _, right in pairs)
    differences = [right - left for left, right in pairs]
    bootstrap = _row_bootstrap_mean(differences)
    transitions = Counter((left, right) for left, right in pairs)
    return {
        "issue_packet_baseline": _rate(issue_count, len(task_ids)),
        "repository_packet_primary": _rate(repository_count, len(task_ids)),
        "paired_percentage_point_difference_repository_minus_issue": {
            "estimate": _round(100 * sum(differences) / len(differences)),
            "bootstrap_95_ci": {
                "lower": _round(100 * bootstrap[0]),
                "upper": _round(100 * bootstrap[1]),
            },
        },
        "binary_transition_counts": {
            "P0/P1_to_P0/P1": transitions[(0, 0)],
            "P0/P1_to_P2/P3": transitions[(0, 1)],
            "P2/P3_to_P0/P1": transitions[(1, 0)],
            "P2/P3_to_P2/P3": transitions[(1, 1)],
        },
        "interpretation": (
            "paired descriptive sensitivity; the packet evidence, reviewers, and "
            "adjudication procedure changed together, so the difference is not a "
            "causal effect of repository evidence alone"
        ),
    }


def _row_bootstrap_mean(values: list[int]) -> tuple[float, float]:
    rng = random.Random(BOOTSTRAP_SEED)
    estimates = []
    for _ in range(BOOTSTRAP_SAMPLES):
        estimates.append(sum(rng.choice(values) for _ in values) / len(values))
    estimates.sort()
    return _percentile_interval(estimates)


def _repository_cluster_sensitivity(
    task_ids: list[str],
    indexed: dict[str, dict[str, dict[str, Any]]],
    split_480: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    final = indexed["final"]
    clusters: dict[str, list[int]] = defaultdict(list)
    for task_id in task_ids:
        repository = split_480[task_id].get("repo")
        if not isinstance(repository, str) or not repository:
            raise ValueError(f"{task_id}: missing repository in split_480")
        clusters[repository].append(int(_is_p2p3(final[task_id])))

    repositories = sorted(clusters)
    repository_rates = [sum(clusters[repo]) / len(clusters[repo]) for repo in repositories]
    repository_weighted = sum(repository_rates) / len(repository_rates)
    rng = random.Random(BOOTSTRAP_SEED)
    bootstrap = []
    for _ in range(BOOTSTRAP_SAMPLES):
        sampled = [rng.choice(repositories) for _ in repositories]
        numerator = sum(sum(clusters[repo]) for repo in sampled)
        denominator = sum(len(clusters[repo]) for repo in sampled)
        bootstrap.append(numerator / denominator)
    bootstrap.sort()
    bootstrap_lower, bootstrap_upper = _percentile_interval(bootstrap)

    total_positive = sum(sum(values) for values in clusters.values())
    total_tasks = sum(len(values) for values in clusters.values())
    leave_one_out = {}
    for repository in repositories:
        numerator = total_positive - sum(clusters[repository])
        denominator = total_tasks - len(clusters[repository])
        leave_one_out[repository] = numerator / denominator
    minimum_repo = min(leave_one_out, key=leave_one_out.get)
    maximum_repo = max(leave_one_out, key=leave_one_out.get)

    per_repository = []
    for repository in sorted(repositories, key=lambda item: (-len(clusters[item]), item)):
        values = clusters[repository]
        per_repository.append(
            {
                "repository": repository,
                "task_count": len(values),
                "p2p3_count": sum(values),
                "proportion": _round(sum(values) / len(values)),
            }
        )
    return {
        "repository_count": len(repositories),
        "row_level": _rate(total_positive, total_tasks),
        "repository_weighted_mean": _round(repository_weighted),
        "repository_cluster_bootstrap_95_ci": {
            "lower": _round(bootstrap_lower),
            "upper": _round(bootstrap_upper),
        },
        "leave_one_repository_out": {
            "minimum": _round(leave_one_out[minimum_repo]),
            "minimum_when_excluding": minimum_repo,
            "maximum": _round(leave_one_out[maximum_repo]),
            "maximum_when_excluding": maximum_repo,
        },
        "per_repository": per_repository,
        "interpretation": (
            "within-sample concentration sensitivity; repository reweighting and "
            "cluster bootstrap do not redefine the row-sampled benchmark-frame estimand"
        ),
    }


def _percentile_interval(values: list[float]) -> tuple[float, float]:
    return _percentile(values, 0.025), _percentile(values, 0.975)


def _percentile(values: list[float], quantile: float) -> float:
    position = quantile * (len(values) - 1)
    lower = int(position)
    upper = min(lower + 1, len(values) - 1)
    fraction = position - lower
    return values[lower] * (1 - fraction) + values[upper] * fraction


def _build_rows(
    ordered_ids: list[str],
    nested_ids: set[str],
    indexed: dict[str, dict[str, dict[str, Any]]],
    split_480: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    rows = []
    for task_id in ordered_ids:
        r1 = indexed["r1"][task_id]
        r2 = indexed["r2"][task_id]
        final = indexed["final"][task_id]
        issue_seed = indexed["issue_seed"][task_id]
        raw_votes = int(_is_p2p3(r1)) + int(_is_p2p3(r2))
        rows.append(
            {
                "schema_version": "repo480-prevalence-row-v1",
                "ordinal": split_480[task_id]["prevalence_random_rank"],
                "task_id": task_id,
                "repository": split_480[task_id]["repo"],
                "in_nested_120": task_id in nested_ids,
                "issue_seed_label": issue_seed["primary_label"],
                "r1_label": r1["primary_label"],
                "r2_label": r2["primary_label"],
                "final_label": final["primary_label"],
                "issue_seed_binary": _binary(issue_seed["primary_label"]),
                "r1_binary": _binary(r1["primary_label"]),
                "r2_binary": _binary(r2["primary_label"]),
                "final_binary": _binary(final["primary_label"]),
                "raw_binary_agreement": _binary(r1["primary_label"])
                == _binary(r2["primary_label"]),
                "raw_intersection_p2p3": raw_votes == 2,
                "raw_union_p2p3": raw_votes >= 1,
                "two_of_three_with_adjudicated_p2p3": raw_votes
                + int(_is_p2p3(final))
                >= 2,
                "primary_blocker": final.get("primary_blocker"),
                "data_quality": final["data_quality"],
                "retrieval_sufficiency": final["retrieval_sufficiency"],
            }
        )
    return rows


def _validate_analysis(analysis: dict[str, Any], rows: list[dict[str, Any]]) -> None:
    if len(rows) != EXPECTED_FULL_COUNT:
        raise ValueError("prevalence row supplement must contain 480 rows")
    if [row["ordinal"] for row in rows] != list(range(1, EXPECTED_FULL_COUNT + 1)):
        raise ValueError("prevalence row supplement ordinal mismatch")
    if sum(row["in_nested_120"] for row in rows) != EXPECTED_NESTED_COUNT:
        raise ValueError("prevalence row supplement nested count mismatch")
    primary = analysis["primary_480"]["p2p3"]
    if primary["count"] != sum(row["final_binary"] == "P2/P3" for row in rows):
        raise ValueError("primary numerator does not match row supplement")
    rules = analysis["reviewer_rule_sensitivity"]["full_480"]
    for key, row_key in (
        ("raw_intersection", "raw_intersection_p2p3"),
        ("raw_union", "raw_union_p2p3"),
        ("two_of_three_with_adjudicated", "two_of_three_with_adjudicated_p2p3"),
    ):
        if rules[key]["count"] != sum(row[row_key] for row in rows):
            raise ValueError(f"{key} numerator does not match row supplement")
    transition_total = sum(
        analysis["evidence_policy_sensitivity"]["binary_transition_counts"].values()
    )
    if transition_total != EXPECTED_FULL_COUNT:
        raise ValueError("evidence-policy transition total must be 480")
    if sum(
        row["task_count"]
        for row in analysis["repository_cluster_sensitivity"]["per_repository"]
    ) != EXPECTED_FULL_COUNT:
        raise ValueError("repository task counts must sum to 480")


def build_markdown(analysis: dict[str, Any]) -> str:
    primary = analysis["primary_480"]
    nested = analysis["nested_120"]
    full_agreement = analysis["raw_reviewer_reliability"]["full_480"]
    nested_agreement = analysis["raw_reviewer_reliability"]["nested_120"]
    evidence = analysis["evidence_policy_sensitivity"]
    cluster = analysis["repository_cluster_sensitivity"]
    full_rules = analysis["reviewer_rule_sensitivity"]["full_480"]
    nested_rules = analysis["reviewer_rule_sensitivity"]["nested_120"]
    lines = [
        "# Repo480 RQ1 Prevalence Recalculation",
        "",
        "## Scope",
        "",
        "This report estimates P2/P3 prevalence only for the frozen 480-task SWE-bench frame",
        "under `swebench-repo480-v1`. The nested 120 rows are a reliability and row-audit",
        "diagnostic, not a replacement estimate or an independent sample. RQ2 oracle masking",
        "is not computed here.",
        "",
        "## Frozen Adjudication-Rule Estimate (480 Tasks)",
        "",
        f"- Final labels: {_counts_inline(primary['label_counts'])}.",
        f"- Adjudicated P2/P3: {_format_rate(primary['p2p3'])}.",
        "- The Wilson interval quantifies row-level sampling uncertainty conditional on the",
        "  frozen frame and annotation rule; it does not include reviewer or repository-policy",
        "  uncertainty.",
        "- Since the independent boundary-validation panel (RR-A), this frozen-rule estimate is",
        "  one member of a rule-dependent sensitivity family, not the single preferred estimate.",
        "  The independent-panel estimate is reported in",
        "  `results/pilot/repo480_boundary_validation_analysis_v1.md`.",
        "",
        "## Raw Reviewer Reliability",
        "",
        "| Frame | Axis | Agreement | Cohen's kappa | Direction of binary disagreement |",
        "| --- | --- | ---: | ---: | --- |",
        _agreement_markdown_row("480", "P0--P3", full_agreement["primary_label"], None),
        _agreement_markdown_row(
            "480",
            "P0/P1 vs P2/P3",
            full_agreement["binary_label"],
            full_agreement["binary_disagreement_direction_counts"],
        ),
        _agreement_markdown_row("nested 120", "P0--P3", nested_agreement["primary_label"], None),
        _agreement_markdown_row(
            "nested 120",
            "P0/P1 vs P2/P3",
            nested_agreement["binary_label"],
            nested_agreement["binary_disagreement_direction_counts"],
        ),
        "",
        "High observed binary agreement coexists with a directional marginal difference between",
        "the two raw passes. Therefore, kappa and reviewer-rule sensitivity are reported rather",
        "than treating agreement alone as prevalence stability.",
        "",
        "## Reviewer-Rule Sensitivity",
        "",
        "| Rule | 480 count/N (Wilson 95% CI) | Nested 120 count/N (Wilson 95% CI) |",
        "| --- | ---: | ---: |",
    ]
    for key, label in (
        ("raw_r1", "Raw reviewer 1"),
        ("raw_r2", "Raw reviewer 2"),
        ("raw_intersection", "Both raw reviewers (intersection)"),
        ("raw_union", "Either raw reviewer (union)"),
        ("two_of_three_with_adjudicated", "Two of raw/raw/adjudicated"),
        ("adjudicated", "Adjudicated (frozen rule)"),
    ):
        lines.append(
            f"| {label} | {_format_rate(full_rules[key])} | {_format_rate(nested_rules[key])} |"
        )
    lines.extend(
        [
            "",
            "The two-of-three row is descriptive because adjudication is derived from the raw",
            "passes; it is not a third independent vote. The wide raw intersection--union range",
            "is annotation-rule uncertainty and must not be presented as a confidence interval.",
            "",
            "## Nested 120 Deep-Audit View",
            "",
            f"- Final labels: {_counts_inline(nested['label_counts'])}.",
            f"- Repository-packet P2/P3 rows: {_format_rate(nested['p2p3'])}.",
            f"- Issue-packet baseline on the same rows: {_format_rate(nested['issue_packet_baseline_p2p3'])}.",
            "- All repository-packet P2/P3 rows in this subset appear in the generated supplement",
            "  table and the 480-row JSONL audit.",
            "- Prior issue-packet external panels are not recast as reliability evidence for the",
            "  new repository-packet labels.",
            "",
            "## Evidence-Policy Sensitivity",
            "",
            f"- Issue-packet baseline: {_format_rate(evidence['issue_packet_baseline'])}.",
            f"- Repository packet, frozen adjudicated rule: {_format_rate(evidence['repository_packet_primary'])}.",
            "- Paired difference (repository minus issue packet): "
            f"{evidence['paired_percentage_point_difference_repository_minus_issue']['estimate']:.3f} "
            "percentage points (row bootstrap 95% CI "
            f"[{evidence['paired_percentage_point_difference_repository_minus_issue']['bootstrap_95_ci']['lower']:.3f}, "
            f"{evidence['paired_percentage_point_difference_repository_minus_issue']['bootstrap_95_ci']['upper']:.3f}]).",
            "- Binary transitions: "
            + ", ".join(
                f"{key}={value}"
                for key, value in evidence["binary_transition_counts"].items()
            )
            + ".",
            "- This is paired descriptive sensitivity, not a causal repository-evidence effect,",
            "  because packet contents and reviewer/adjudication procedures changed together.",
            "",
            "## Repository-Cluster Sensitivity",
            "",
            f"- Repositories: {cluster['repository_count']}.",
            f"- Row-level frozen-rule estimate: {_format_rate(cluster['row_level'])}.",
            f"- Equal-repository-weighted mean: {cluster['repository_weighted_mean']:.3f}.",
            "- Repository-cluster bootstrap 95% interval: "
            f"[{cluster['repository_cluster_bootstrap_95_ci']['lower']:.3f}, "
            f"{cluster['repository_cluster_bootstrap_95_ci']['upper']:.3f}].",
            "- Leave-one-repository-out row-rate range: "
            f"[{cluster['leave_one_repository_out']['minimum']:.3f}, "
            f"{cluster['leave_one_repository_out']['maximum']:.3f}] "
            f"(minimum excludes `{cluster['leave_one_repository_out']['minimum_when_excluding']}`; "
            f"maximum excludes `{cluster['leave_one_repository_out']['maximum_when_excluding']}`).",
            "",
            "| Repository | Tasks | P2/P3 | Rate |",
            "| --- | ---: | ---: | ---: |",
        ]
    )
    for row in cluster["per_repository"]:
        lines.append(
            f"| `{row['repository']}` | {row['task_count']} | {row['p2p3_count']} | "
            f"{row['proportion']:.3f} |"
        )
    lines.extend(
        [
            "",
            "Repository weighting and cluster resampling are within-sample concentration checks.",
            "They do not redefine the row-sampled 480-task benchmark-frame estimand.",
            "",
            "## Claim Boundary",
            "",
            "- Report 26/480 and its Wilson interval as the frozen adjudication-rule member of the",
            "  RQ1 rule-sensitivity family, beside the independent-panel estimate; do not present",
            "  it as the single preferred estimate.",
            "- Report nested 120 reliability and row audit separately from the 480 estimate.",
            "- Report reviewer-rule and evidence-policy sensitivities as distinct uncertainty",
            "  families, not as one heterogeneous envelope.",
            "- Do not infer broad APR prevalence, a causal evidence effect, a validated automatic",
            "  patch gate, or an RQ2 masking result from this artifact.",
            "",
        ]
    )
    return "\n".join(lines)


def load_validation_estimate(path: Path) -> dict[str, Any]:
    actual = sha256_file(path)
    if actual != VALIDATION_ANALYSIS_SHA256:
        raise ValueError(
            "validation analysis SHA-256 mismatch: "
            f"expected {VALIDATION_ANALYSIS_SHA256}, found {actual}"
        )
    value = json.loads(path.read_text(encoding="utf-8"))
    estimate = value["independent_stratified_prevalence"]
    strata = estimate["strata"]
    if estimate["denominator"] != EXPECTED_FULL_COUNT or not strata["raw_union_p23"]["census"]:
        raise ValueError("validation analysis does not match the stratified 480 design")
    if value["statistics"]["bootstrap_samples"] != BOOTSTRAP_SAMPLES:
        raise ValueError("validation bootstrap size differs from the table footnote")
    return {
        "estimate": estimate,
        "raw": value["raw_panel_sensitivity"],
        "cluster": value["repository_cluster_sensitivity"],
        "statistics": value["statistics"],
    }


def build_main_tex(analysis: dict[str, Any], validation: dict[str, Any]) -> str:
    primary = analysis["primary_480"]["p2p3"]
    full_rules = analysis["reviewer_rule_sensitivity"]["full_480"]
    nested_rules = analysis["reviewer_rule_sensitivity"]["nested_120"]
    evidence = analysis["evidence_policy_sensitivity"]
    cluster = analysis["repository_cluster_sensitivity"]
    estimate = validation["estimate"]
    union = estimate["strata"]["raw_union_p23"]
    consensus = estimate["strata"]["raw_consensus_p01"]
    raw = validation["raw"]
    vcluster = validation["cluster"]
    vstats = validation["statistics"]
    lines = [
        "% Generated by scripts/analyze_repo480_prevalence.py; do not edit manually.",
        "% Validation-panel rows are read from results/pilot/repo480_boundary_validation_analysis_v1.json.",
        "\\begin{table}[t]",
        "\\caption{RQ1 prevalence estimates and sensitivities under the frozen repository packet.}",
        "\\label{tab:repo480prevalence}",
        "\\centering",
        "\\small",
        "\\begin{tabular}{@{}p{0.48\\linewidth}p{0.18\\linewidth}p{0.26\\linewidth}@{}}",
        "\\hline",
        "Analysis & P2/P3 & Estimate / 95\\% interval \\\\",
        "\\hline",
        "\\multicolumn{3}{@{}l}{\\emph{Frozen adjudication rule (row-level random sample)}} \\\\",
        f"Adjudicated repository packet (480) & {primary['count']}/{primary['denominator']} & "
        f"{primary['proportion']:.3f} [{primary['wilson_95_ci']['lower']:.3f}, "
        f"{primary['wilson_95_ci']['upper']:.3f}] Wilson \\\\",
        "\\multicolumn{3}{@{}l}{\\emph{Separately staffed validation panel "
        f"(census {union['sample']} + sample {consensus['sample']}/{consensus['population']})}}}} \\\\",
        f"Adjudicated stratified estimate & {union['positive']}/{union['sample']}; "
        f"{consensus['positive']}/{consensus['sample']} & "
        f"{estimate['proportion']:.3f} [{estimate['interval_95']['lower']:.3f}, "
        f"{estimate['interval_95']['upper']:.3f}] FPC$^a$ \\\\",
        f"Repository-cluster bootstrap$^b$ & --- & "
        f"[{vcluster['bootstrap_95_ci']['lower']:.3f}, "
        f"{vcluster['bootstrap_95_ci']['upper']:.3f}] \\\\",
        f"Raw validation intersection / union & --- & {raw['intersection']['proportion']:.3f} / "
        f"{raw['union']['proportion']:.3f} stratified \\\\",
        "\\multicolumn{3}{@{}l}{\\emph{Reviewer-rule sensitivity on the same 480 rows}} \\\\",
        _tex_single_rate_row("Raw reviewer 1", full_rules["raw_r1"]),
        _tex_single_rate_row("Raw reviewer 2", full_rules["raw_r2"]),
        _tex_single_rate_row("Raw intersection", full_rules["raw_intersection"]),
        _tex_single_rate_row("Raw union", full_rules["raw_union"]),
        "\\multicolumn{3}{@{}l}{\\emph{Nested audit and evidence-policy sensitivity}} \\\\",
        f"Nested 120 adjudicated audit & {nested_rules['adjudicated']['count']}/120 & "
        f"{nested_rules['adjudicated']['proportion']:.3f} "
        f"[{nested_rules['adjudicated']['wilson_95_ci']['lower']:.3f}, "
        f"{nested_rules['adjudicated']['wilson_95_ci']['upper']:.3f}]; audit only \\\\",
        _tex_single_rate_row(
            "Issue-packet baseline (same 480)", evidence["issue_packet_baseline"]
        ),
        "\\multicolumn{3}{@{}l}{\\emph{Repository concentration sensitivity}} \\\\",
        f"Equal-repository weighted / cluster bootstrap$^b$ & --- & "
        f"{cluster['repository_weighted_mean']:.3f}; "
        f"[{cluster['repository_cluster_bootstrap_95_ci']['lower']:.3f}, "
        f"{cluster['repository_cluster_bootstrap_95_ci']['upper']:.3f}] \\\\",
        "\\hline",
        "\\end{tabular}",
        "\\begin{minipage}{0.95\\linewidth}",
        "\\footnotesize $^a$Wilson score with finite-population correction in the sampled "
        "original raw-consensus P0/P1 stratum; the original raw-union P2/P3 stratum is a census. "
        f"$^b$Repository percentile bootstrap with {BOOTSTRAP_SAMPLES:,} resamples "
        f"({cluster['repository_count']} repositories and seed {BOOTSTRAP_SEED} for the frozen frame; "
        f"{vcluster['repository_count']} repositories and seed {vstats['bootstrap_seed']} "
        "for the validation panel). Families are reported separately, not combined into one interval.",
        "\\end{minipage}",
        "\\end{table}",
        "",
    ]
    return "\n".join(lines)


def build_supplement_tex(
    analysis: dict[str, Any], rows: list[dict[str, Any]]
) -> str:
    nested = analysis["nested_120"]
    agreement = analysis["raw_reviewer_reliability"]["nested_120"]
    rules = analysis["reviewer_rule_sensitivity"]["nested_120"]
    selected = [
        row for row in rows if row["in_nested_120"] and row["final_binary"] == "P2/P3"
    ]
    lines = [
        "% Generated by scripts/analyze_repo480_prevalence.py; do not edit manually.",
        "\\begin{table}[t]",
        "\\caption{Reliability of the nested 120-row repository-packet audit.}",
        "\\label{tab:repo480nestedreliability}",
        "\\centering",
        "\\small",
        "\\begin{tabular}{@{}p{0.38\\linewidth}p{0.24\\linewidth}p{0.27\\linewidth}@{}}",
        "\\hline",
        "Measure & Count & Estimate \\\\",
        "\\hline",
        _tex_single_rate_row("Adjudicated P2/P3", nested["p2p3"]),
        _tex_single_rate_row("Raw reviewer 1 P2/P3", rules["raw_r1"]),
        _tex_single_rate_row("Raw reviewer 2 P2/P3", rules["raw_r2"]),
        _tex_single_rate_row("Raw intersection P2/P3", rules["raw_intersection"]),
        _tex_single_rate_row("Raw union P2/P3", rules["raw_union"]),
        f"Raw binary agreement & {agreement['binary_label']['agreement_count']}/120 & "
        f"{agreement['binary_label']['observed_agreement']:.3f}; "
        f"$\\kappa={agreement['binary_label']['cohen_kappa']:.3f}$ \\\\",
        f"Raw exact-label agreement & {agreement['primary_label']['agreement_count']}/120 & "
        f"{agreement['primary_label']['observed_agreement']:.3f}; "
        f"$\\kappa={agreement['primary_label']['cohen_kappa']:.3f}$ \\\\",
        "\\hline",
        "\\end{tabular}",
        "\\end{table}",
        "",
        "\\begin{table*}[t]",
        "\\caption{All adjudicated P2/P3 rows in the nested 120-task repository-packet audit.}",
        "\\label{tab:repo480nestedrows}",
        "\\centering",
        "\\scriptsize",
        "\\begin{tabular}{@{}p{0.26\\textwidth}ccccp{0.12\\textwidth}p{0.13\\textwidth}@{}}",
        "\\hline",
        "Task & Issue baseline & R1 & R2 & Final & Blocker & Retrieval \\\\",
        "\\hline",
    ]
    for row in selected:
        lines.append(
            f"\\texttt{{{_latex_escape(row['task_id'])}}} & "
            f"{row['issue_seed_label']} & {row['r1_label']} & {row['r2_label']} & "
            f"{row['final_label']} & {_latex_escape(row['primary_blocker'] or 'none')} & "
            f"{_latex_escape(row['retrieval_sufficiency'])} \\\\"
        )
    lines.extend(
        [
            "\\hline",
            "\\end{tabular}",
            "\\end{table*}",
            "",
        ]
    )
    return "\n".join(lines)


def _tex_single_rate_row(label: str, rate: dict[str, Any]) -> str:
    return (
        f"{label} & {rate['count']}/{rate['denominator']} & "
        f"{rate['proportion']:.3f} [{rate['wilson_95_ci']['lower']:.3f}, "
        f"{rate['wilson_95_ci']['upper']:.3f}] Wilson \\\\"
    )


def _agreement_markdown_row(
    frame: str,
    axis: str,
    metric: dict[str, Any],
    directions: dict[str, int] | None,
) -> str:
    direction_text = "---"
    if directions is not None:
        direction_text = (
            f"R1 safe/R2 unsafe={directions['r1_P0/P1_r2_P2/P3']}; "
            f"R1 unsafe/R2 safe={directions['r1_P2/P3_r2_P0/P1']}"
        )
    return (
        f"| {frame} | {axis} | {metric['agreement_count']}/{metric['n']} "
        f"({metric['observed_agreement']:.3f}) | {metric['cohen_kappa']:.3f} | "
        f"{direction_text} |"
    )


def _format_rate(rate: dict[str, Any]) -> str:
    return (
        f"{rate['count']}/{rate['denominator']} = {rate['proportion']:.3f} "
        f"(Wilson 95% CI [{rate['wilson_95_ci']['lower']:.3f}, "
        f"{rate['wilson_95_ci']['upper']:.3f}])"
    )


def _label_counts(records: Iterable[dict[str, Any]]) -> dict[str, int]:
    counts = Counter(record["primary_label"] for record in records)
    return {label: counts[label] for label in PRIMARY_LABELS}


def _counts_inline(counts: dict[str, int]) -> str:
    return ", ".join(f"{label}={counts[label]}" for label in PRIMARY_LABELS)


def _binary(label: str) -> str:
    return "P2/P3" if label in {"P2", "P3"} else "P0/P1"


def _is_p2p3(record: dict[str, Any]) -> bool:
    return record["primary_label"] in {"P2", "P3"}


def _round(value: float) -> float:
    return round(value, 6)


def _display_path(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def _latex_escape(value: str) -> str:
    return value.replace("_", "\\_").replace("%", "\\%")


if __name__ == "__main__":
    raise SystemExit(main())
