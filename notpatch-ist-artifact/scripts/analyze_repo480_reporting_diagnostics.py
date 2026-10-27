#!/usr/bin/env python3
"""Generate paper-facing diagnostics for the repo480 measurement report."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
LABELS = ("P0", "P1", "P2", "P3")
P23 = {"P2", "P3"}


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--raw-r1",
        type=Path,
        default=ROOT / "data/annotations/raw_labels/repo480_available_v1_r1.jsonl",
    )
    parser.add_argument(
        "--raw-r2",
        type=Path,
        default=ROOT / "data/annotations/raw_labels/repo480_available_v1_r2.jsonl",
    )
    parser.add_argument(
        "--adjudicated",
        type=Path,
        default=ROOT / "data/annotations/adjudicated/repo480_available_v1.jsonl",
    )
    parser.add_argument(
        "--split",
        type=Path,
        default=ROOT / "data/processed/dataset_splits/swebench_full_prevalence_random_480.json",
    )
    parser.add_argument(
        "--verified-membership",
        type=Path,
        default=ROOT / "data/manifests/generated/swebench_verified_test_membership.json",
    )
    parser.add_argument(
        "--prevalence-analysis",
        type=Path,
        default=ROOT / "results/pilot/repo480_available_v1_prevalence_analysis.json",
    )
    parser.add_argument(
        "--out-json",
        type=Path,
        default=ROOT / "results/pilot/repo480_reporting_diagnostics_v1.json",
    )
    parser.add_argument(
        "--out-md",
        type=Path,
        default=ROOT / "results/pilot/repo480_reporting_diagnostics_v1.md",
    )
    parser.add_argument(
        "--out-sampling-tex",
        type=Path,
        default=ROOT / "paper/generated/repo480_sampling_flow.tex",
    )
    parser.add_argument(
        "--out-diagnostics-tex",
        type=Path,
        default=ROOT / "paper/generated/repo480_reporting_diagnostics.tex",
    )
    return parser.parse_args(argv)


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_jsonl(path: Path) -> dict[str, dict[str, Any]]:
    rows: dict[str, dict[str, Any]] = {}
    for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        row = json.loads(line)
        task_id = row.get("task_id")
        if not isinstance(task_id, str) or not task_id:
            raise ValueError(f"{path}:{line_no}: missing task_id")
        if task_id in rows:
            raise ValueError(f"{path}:{line_no}: duplicate task_id {task_id}")
        if row.get("primary_label") not in LABELS:
            raise ValueError(f"{path}:{line_no}: invalid primary_label")
        rows[task_id] = row
    return rows


def file_ref(path: Path) -> dict[str, str]:
    data = path.read_bytes()
    try:
        ref = str(path.resolve().relative_to(ROOT))
    except ValueError:
        ref = str(path.resolve())
    return {"ref": ref, "sha256": hashlib.sha256(data).hexdigest()}


def agreement(values_a: list[str], values_b: list[str], categories: tuple[str, ...]) -> dict[str, Any]:
    if len(values_a) != len(values_b) or not values_a:
        raise ValueError("agreement inputs must have equal positive length")
    n = len(values_a)
    matrix = {
        left: {right: 0 for right in categories}
        for left in categories
    }
    for left, right in zip(values_a, values_b, strict=True):
        matrix[left][right] += 1
    agreement_count = sum(matrix[value][value] for value in categories)
    observed = agreement_count / n
    marg_a = Counter(values_a)
    marg_b = Counter(values_b)
    expected = sum(marg_a[value] * marg_b[value] for value in categories) / (n * n)
    kappa = (observed - expected) / (1 - expected) if expected != 1 else math.nan
    return {
        "n": n,
        "agreement_count": agreement_count,
        "observed_agreement": observed,
        "cohen_kappa": kappa,
        "matrix": matrix,
    }


def weighted_kappa(
    values_a: list[str], values_b: list[str], categories: tuple[str, ...], power: int
) -> float:
    positions = {value: index for index, value in enumerate(categories)}
    maximum = len(categories) - 1
    n = len(values_a)
    marg_a = Counter(values_a)
    marg_b = Counter(values_b)
    observed_disagreement = sum(
        (abs(positions[left] - positions[right]) / maximum) ** power
        for left, right in zip(values_a, values_b, strict=True)
    ) / n
    expected_disagreement = sum(
        marg_a[left]
        * marg_b[right]
        * (abs(positions[left] - positions[right]) / maximum) ** power
        for left in categories
        for right in categories
    ) / (n * n)
    if expected_disagreement == 0:
        return math.nan
    return 1 - observed_disagreement / expected_disagreement


def gwet_ac1(values_a: list[str], values_b: list[str], categories: tuple[str, ...]) -> float:
    n = len(values_a)
    observed = sum(left == right for left, right in zip(values_a, values_b, strict=True)) / n
    average_marginal = {
        value: (values_a.count(value) + values_b.count(value)) / (2 * n)
        for value in categories
    }
    expected = sum(p * (1 - p) for p in average_marginal.values()) / (len(categories) - 1)
    return (observed - expected) / (1 - expected) if expected != 1 else math.nan


def wilson(count: int, denominator: int, z: float = 1.959963984540054) -> dict[str, float]:
    if denominator <= 0:
        raise ValueError("Wilson denominator must be positive")
    proportion = count / denominator
    z2 = z * z
    center = (proportion + z2 / (2 * denominator)) / (1 + z2 / denominator)
    half = (
        z
        * math.sqrt(
            proportion * (1 - proportion) / denominator
            + z2 / (4 * denominator * denominator)
        )
        / (1 + z2 / denominator)
    )
    return {"count": count, "denominator": denominator, "proportion": proportion,
            "wilson_95_ci": {"lower": center - half, "upper": center + half}}


def fmt(value: float, digits: int = 3) -> str:
    return f"{value:.{digits}f}"


def rate_tex(item: dict[str, Any]) -> str:
    ci = item["wilson_95_ci"]
    return f"{fmt(item['proportion'])} [{fmt(ci['lower'])}, {fmt(ci['upper'])}]"


def build_report(args: argparse.Namespace) -> dict[str, Any]:
    raw_r1 = load_jsonl(args.raw_r1)
    raw_r2 = load_jsonl(args.raw_r2)
    adjudicated = load_jsonl(args.adjudicated)
    task_ids = sorted(adjudicated)
    if set(raw_r1) != set(task_ids) or set(raw_r2) != set(task_ids):
        raise ValueError("raw and adjudicated task-id sets differ")
    if len(task_ids) != 480:
        raise ValueError(f"expected 480 tasks, got {len(task_ids)}")

    split = load_json(args.split)
    split_ids = {row["task_id"] for row in split["tasks"]}
    if split_ids != set(task_ids):
        raise ValueError("split and adjudicated task-id sets differ")
    membership = load_json(args.verified_membership)
    verified_ids = set(membership["task_ids"])
    prevalence = load_json(args.prevalence_analysis)

    labels_r1 = [raw_r1[task_id]["primary_label"] for task_id in task_ids]
    labels_r2 = [raw_r2[task_id]["primary_label"] for task_id in task_ids]
    primary = agreement(labels_r1, labels_r2, LABELS)
    primary["linear_weighted_kappa"] = weighted_kappa(labels_r1, labels_r2, LABELS, 1)
    primary["quadratic_weighted_kappa"] = weighted_kappa(labels_r1, labels_r2, LABELS, 2)
    primary["gwet_ac1_nominal"] = gwet_ac1(labels_r1, labels_r2, LABELS)

    boundary_r1 = ["P2/P3" if value in P23 else "P0/P1" for value in labels_r1]
    boundary_r2 = ["P2/P3" if value in P23 else "P0/P1" for value in labels_r2]
    binary = agreement(boundary_r1, boundary_r2, ("P0/P1", "P2/P3"))
    binary["pabak"] = 2 * binary["observed_agreement"] - 1
    binary["gwet_ac1"] = gwet_ac1(boundary_r1, boundary_r2, ("P0/P1", "P2/P3"))

    blocker_ids = [
        task_id
        for task_id in task_ids
        if raw_r1[task_id].get("primary_blocker")
        or raw_r2[task_id].get("primary_blocker")
    ]
    blocker_agreement = sum(
        raw_r1[task_id].get("primary_blocker")
        == raw_r2[task_id].get("primary_blocker")
        for task_id in blocker_ids
    )

    disagreements = [
        task_id
        for task_id in task_ids
        if (raw_r1[task_id]["primary_label"] in P23)
        != (raw_r2[task_id]["primary_label"] in P23)
    ]
    disagreement_final = Counter(
        "P2/P3" if adjudicated[task_id]["primary_label"] in P23 else "P0/P1"
        for task_id in disagreements
    )
    consensus_p23 = sum(
        raw_r1[task_id]["primary_label"] in P23
        and raw_r2[task_id]["primary_label"] in P23
        for task_id in task_ids
    )

    retrieval_groups = {
        "sufficient": [row for row in adjudicated.values() if row["retrieval_sufficiency"] == "sufficient"],
        "insufficient_or_unclear": [
            row for row in adjudicated.values() if row["retrieval_sufficiency"] != "sufficient"
        ],
    }
    retrieval = {
        name: wilson(sum(row["primary_label"] in P23 for row in rows), len(rows))
        for name, rows in retrieval_groups.items()
    }
    verified_groups = {
        "verified": [row for task_id, row in adjudicated.items() if task_id in verified_ids],
        "not_verified": [row for task_id, row in adjudicated.items() if task_id not in verified_ids],
    }
    verified = {
        name: wilson(sum(row["primary_label"] in P23 for row in rows), len(rows))
        for name, rows in verified_groups.items()
    }
    data_quality = Counter(row["data_quality"] for row in adjudicated.values())

    bootstrap = prevalence["repository_cluster_sensitivity"]["repository_cluster_bootstrap_95_ci"]
    statistics = prevalence["statistics"]
    return {
        "schema_version": "repo480-reporting-diagnostics-v1",
        "analysis_id": "repo480-reporting-diagnostics-v1",
        "inputs": {
            name: file_ref(path)
            for name, path in {
                "raw_r1": args.raw_r1,
                "raw_r2": args.raw_r2,
                "adjudicated": args.adjudicated,
                "split": args.split,
                "verified_membership": args.verified_membership,
                "prevalence_analysis": args.prevalence_analysis,
            }.items()
        },
        "sampling_flow": {
            "source_rows": split["n_source_rows"],
            "prior_id_exclusions": split["n_excluded_prior"],
            "sampling_frame": split["n_sampling_frame"],
            "candidate_draw": split["n_candidate_draw"],
            "eligible_in_draw": split["n_eligible_in_draw"],
            "structural_exclusions": split["n_structural_excluded"],
            "selected_random_ranks": split["n_sampled"],
            "unused_eligible_reserve": split["n_eligible_in_draw"] - split["n_sampled"],
            "seed": split["seed"],
        },
        "raw_reliability": {
            "binary_boundary": binary,
            "primary_label": primary,
            "primary_blocker_any_recorded": {
                "agreement_count": blocker_agreement,
                "denominator": len(blocker_ids),
                "observed_agreement": blocker_agreement / len(blocker_ids),
            },
        },
        "boundary_disagreement_adjudication": {
            "disagreement_count": len(disagreements),
            "final_p01": disagreement_final["P0/P1"],
            "final_p23": disagreement_final["P2/P3"],
            "raw_consensus_p23": consensus_p23,
            "final_total_p23": consensus_p23 + disagreement_final["P2/P3"],
        },
        "retrieval_sensitivity": retrieval,
        "verified_membership": {
            "membership_source_rows": len(verified_ids),
            "within_frame": verified,
        },
        "data_quality_counts": dict(sorted(data_quality.items())),
        "repository_cluster_bootstrap": {
            "lower": bootstrap["lower"],
            "upper": bootstrap["upper"],
            "samples": statistics["bootstrap_samples"],
            "seed": statistics["bootstrap_seed"],
            "interval": statistics["bootstrap_interval"],
        },
        "claim_scope": [
            "Reliability coefficients describe the two original raw passes before adjudication.",
            "Verified membership and retrieval strata are construct/sensitivity diagnostics, not new prevalence estimands.",
            "The 120 unused eligible draw rows are reserve rows, not exclusions or attrition.",
        ],
    }


def render_markdown(report: dict[str, Any]) -> str:
    sampling = report["sampling_flow"]
    binary = report["raw_reliability"]["binary_boundary"]
    primary = report["raw_reliability"]["primary_label"]
    blocker = report["raw_reliability"]["primary_blocker_any_recorded"]
    disagreement = report["boundary_disagreement_adjudication"]
    retrieval = report["retrieval_sensitivity"]
    verified = report["verified_membership"]["within_frame"]
    cluster = report["repository_cluster_bootstrap"]
    qd = report["data_quality_counts"]
    return "\n".join([
        "# Repo480 Reporting Diagnostics",
        "",
        "- **Status:** `canonical`",
        "- **Authority:** paper-facing sampling, reliability, retrieval, and Verified diagnostics",
        "- **Packet policy:** `swebench-repo480-v1`",
        "",
        "## Sampling flow",
        "",
        "| Stage | Count |",
        "| --- | ---: |",
        f"| SWE-bench test rows | {sampling['source_rows']} |",
        f"| Prior labeled ids excluded | {sampling['prior_id_exclusions']} |",
        f"| Sampling frame | {sampling['sampling_frame']} |",
        f"| Seeded candidate draw | {sampling['candidate_draw']} |",
        f"| Structurally excluded within draw | {sampling['structural_exclusions']} |",
        f"| Selected random ranks 1--480 | {sampling['selected_random_ranks']} |",
        f"| Unused eligible reserve | {sampling['unused_eligible_reserve']} |",
        "",
        f"All {sampling['candidate_draw']} draw rows were eligible. The final 480 are ranks 1--480; the remaining 120 are unused reserve rows, not attrition.",
        "",
        "## Raw reliability before adjudication",
        "",
        "| Unit | Agreement | Cohen kappa | PABAK / weighted kappa | Gwet AC1 |",
        "| --- | ---: | ---: | ---: | ---: |",
        f"| Binary P0/P1 vs P2/P3 | {binary['agreement_count']}/{binary['n']} ({fmt(binary['observed_agreement'])}) | {fmt(binary['cohen_kappa'])} | PABAK {fmt(binary['pabak'])} | {fmt(binary['gwet_ac1'])} |",
        f"| Exact P0--P3 | {primary['agreement_count']}/{primary['n']} ({fmt(primary['observed_agreement'])}) | {fmt(primary['cohen_kappa'])} | linear {fmt(primary['linear_weighted_kappa'])}; quadratic {fmt(primary['quadratic_weighted_kappa'])} | {fmt(primary['gwet_ac1_nominal'])} |",
        f"| Primary blocker, at least one recorded | {blocker['agreement_count']}/{blocker['denominator']} ({fmt(blocker['observed_agreement'])}) | n/a | n/a | n/a |",
        "",
        f"Of {disagreement['disagreement_count']} binary disagreements, adjudication assigns {disagreement['final_p01']} to P0/P1 and {disagreement['final_p23']} to P2/P3. Together with {disagreement['raw_consensus_p23']} raw-consensus P2/P3 rows, this yields {disagreement['final_total_p23']}/480.",
        "",
        "## Paper-facing sensitivity checks",
        "",
        "| Diagnostic group | P2/P3 | Estimate / Wilson 95% CI |",
        "| --- | ---: | ---: |",
        f"| Retrieval sufficient | {retrieval['sufficient']['count']}/{retrieval['sufficient']['denominator']} | {rate_tex(retrieval['sufficient'])} |",
        f"| Retrieval insufficient or unclear | {retrieval['insufficient_or_unclear']['count']}/{retrieval['insufficient_or_unclear']['denominator']} | {rate_tex(retrieval['insufficient_or_unclear'])} |",
        f"| SWE-bench Verified member | {verified['verified']['count']}/{verified['verified']['denominator']} | {rate_tex(verified['verified'])} |",
        f"| Outside SWE-bench Verified | {verified['not_verified']['count']}/{verified['not_verified']['denominator']} | {rate_tex(verified['not_verified'])} |",
        "",
        f"The data-quality axis fires on {sum(value for key, value in qd.items() if key != 'Q0')}/480 rows (Q0 {qd.get('Q0', 0)}; Q2 {qd.get('Q2', 0)}).",
        f"The repository-cluster bootstrap uses {cluster['samples']} resamples with seed {cluster['seed']} and gives [{fmt(cluster['lower'])}, {fmt(cluster['upper'])}].",
        "",
        "## Interpretation guardrails",
        "",
        "- PABAK and Gwet AC1 quantify the low-prevalence effect on kappa; they do not erase the directional reviewer-threshold difference.",
        "- Zero P2/P3 among Verified members shows overlap with Verified curation, while 357/383 non-Verified rows remain P0/P1 under NotPatch, so the constructs are not equivalent.",
        "- Retrieval stratification changes the point estimate only slightly, but does not substitute for an unbudgeted review of the seven flagged numerator rows.",
        "",
    ])


def render_sampling_tex(report: dict[str, Any]) -> str:
    item = report["sampling_flow"]
    return "\n".join([
        "% Generated by scripts/analyze_repo480_reporting_diagnostics.py; do not edit manually.",
        "\\begin{table}[t]",
        "\\caption{Sampling flow for the frozen 480-task frame.}",
        "\\label{tab:repo480sampling}",
        "\\centering",
        "\\small",
        "\\begin{tabular}{@{}p{0.66\\linewidth}r@{}}",
        "\\hline",
        "Stage & Rows \\\\",
        "\\hline",
        f"SWE-bench public test split & {item['source_rows']:,} \\\\",
        f"Previously labeled ids removed & $-{item['prior_id_exclusions']}$ \\\\",
        f"Sampling frame & {item['sampling_frame']:,} \\\\",
        f"Seeded candidate draw & {item['candidate_draw']} \\\\",
        f"Structural exclusions in draw & {item['structural_exclusions']} \\\\",
        f"Selected random ranks 1--480 & {item['selected_random_ranks']} \\\\",
        f"Unused eligible reserve & {item['unused_eligible_reserve']} \\\\",
        "\\hline",
        "\\end{tabular}",
        "\\end{table}",
        "",
    ])


def render_diagnostics_tex(report: dict[str, Any]) -> str:
    binary = report["raw_reliability"]["binary_boundary"]
    primary = report["raw_reliability"]["primary_label"]
    blocker = report["raw_reliability"]["primary_blocker_any_recorded"]
    retrieval = report["retrieval_sensitivity"]
    verified = report["verified_membership"]["within_frame"]
    return "\n".join([
        "% Generated by scripts/analyze_repo480_reporting_diagnostics.py; do not edit manually.",
        "\\begin{table}[t]",
        "\\caption{Raw reliability before adjudication.}",
        "\\label{tab:repo480reliability}",
        "\\centering",
        "\\scriptsize",
        "\\begin{tabular}{@{}p{0.31\\linewidth}rrrr@{}}",
        "\\hline",
        "Unit & Agreement & $\\kappa$ & PABAK / weighted $\\kappa$ & AC1 \\\\",
        "\\hline",
        f"Binary boundary & {binary['agreement_count']}/{binary['n']} & {fmt(binary['cohen_kappa'])} & {fmt(binary['pabak'])} & {fmt(binary['gwet_ac1'])} \\\\",
        f"Exact P0--P3 & {primary['agreement_count']}/{primary['n']} & {fmt(primary['cohen_kappa'])} & {fmt(primary['linear_weighted_kappa'])} / {fmt(primary['quadratic_weighted_kappa'])} & {fmt(primary['gwet_ac1_nominal'])} \\\\",
        f"Primary blocker$^a$ & {blocker['agreement_count']}/{blocker['denominator']} & --- & --- & --- \\\\",
        "\\hline",
        "\\end{tabular}",
        "\\begin{minipage}{0.95\\linewidth}",
        "\\footnotesize $^a$Rows where at least one raw reviewer records a blocker. Exact-label weighted values are linear/quadratic.",
        "\\end{minipage}",
        "\\end{table}",
        "",
        "\\begin{table}[t]",
        "\\caption{Retrieval and Verified-membership diagnostics.}",
        "\\label{tab:repo480auxiliary}",
        "\\centering",
        "\\small",
        "\\begin{tabular}{@{}p{0.48\\linewidth}p{0.17\\linewidth}p{0.27\\linewidth}@{}}",
        "\\hline",
        "Group & P2/P3 & Estimate / Wilson 95\\% CI \\\\",
        "\\hline",
        f"Retrieval sufficient & {retrieval['sufficient']['count']}/{retrieval['sufficient']['denominator']} & {rate_tex(retrieval['sufficient'])} \\\\",
        f"Retrieval insufficient/unclear & {retrieval['insufficient_or_unclear']['count']}/{retrieval['insufficient_or_unclear']['denominator']} & {rate_tex(retrieval['insufficient_or_unclear'])} \\\\",
        f"SWE-bench Verified member & {verified['verified']['count']}/{verified['verified']['denominator']} & {rate_tex(verified['verified'])} \\\\",
        f"Outside SWE-bench Verified & {verified['not_verified']['count']}/{verified['not_verified']['denominator']} & {rate_tex(verified['not_verified'])} \\\\",
        "\\hline",
        "\\end{tabular}",
        "\\end{table}",
        "",
    ])


def write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def main() -> int:
    args = parse_args()
    report = build_report(args)
    write(args.out_json, json.dumps(report, indent=2, sort_keys=True) + "\n")
    write(args.out_md, render_markdown(report))
    write(args.out_sampling_tex, render_sampling_tex(report))
    write(args.out_diagnostics_tex, render_diagnostics_tex(report))
    print(f"OK: wrote {args.out_json}")
    print(f"OK: wrote {args.out_md}")
    print(f"OK: wrote {args.out_sampling_tex}")
    print(f"OK: wrote {args.out_diagnostics_tex}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
