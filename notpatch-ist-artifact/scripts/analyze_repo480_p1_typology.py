#!/usr/bin/env python3
"""Aggregate the RR-E typology codes for P1 non-strict and boundary-discordant rows.

Types are derived from the coded fields by the rules in
docs/repo480_p1_boundary_typology_codebook.md (sections 4.1 and 5.1); the coder
never enters a type directly. Frozen labels and estimates are read, never edited.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from collections import Counter
from pathlib import Path
from statistics import NormalDist
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from notpatch.canonical import canonical_json_bytes, sha256_file  # noqa: E402

CODE_SCHEMA = "repo480-p1-typology-code-v1"
CODER_ID = "repo480_rre_c1"
# Set B codes were committed before any Set A oracle material was opened.
SET_B_CODES_COMMIT = "30702cc"
ISSUE_ONLY = {"issue_title", "issue_body"}

A_FIELDS = {
    "divergence_kind": {"implementation_only", "added_behavior", "different_behavior", "unclear"},
    "predicted_supported": {"yes", "no", "unclear"},
    "oracle_basis": {
        "required_by_packet",
        "admissible_not_selected",
        "outside_issue_scope",
        "not_applicable",
        "unclear",
    },
    "assumption_anticipated": {"yes", "no", "not_applicable"},
}
B_FIELDS = {
    "alternative_relation": {
        "distinct_contract",
        "same_contract_variant",
        "no_executable_candidate",
        "unclear",
    },
    "p01_side_treatment": {
        "excluded_by_cited_evidence",
        "named_as_bounded_assumption",
        "not_addressed",
        "unclear",
    },
    "p23_side_engages_p01_evidence": {"yes", "no", "not_applicable", "unclear"},
    "p23_side_cites_packet_for_alternative": {"yes", "no", "unclear"},
}
A_TYPES = (
    "a_same_contract",
    "b_contract_choice",
    "c_evidence_reading",
    "d_oracle_scope",
    "u_undeterminable",
)
A_REPORT_TYPES = (
    "a_same_contract",
    "b_anticipated",
    "b_unanticipated",
    "c_evidence_reading",
    "d_oracle_scope",
    "u_undeterminable",
)
B_SOURCES = ("evidence_utilization", "rule_threshold", "case_judgment", "undeterminable")
DIRECTIONS = ("frozen_p01_to_panel_p23", "frozen_p23_to_panel_p01")
A_LABELS = {
    "a_same_contract": "(a) Same contract, implementation or scope detail",
    "b_anticipated": "(b) Contract choice named as a P1 bounded assumption",
    "b_unanticipated": "(b) Contract choice not named in the P1 record",
    "c_evidence_reading": "(c) Task-time evidence misread or omitted",
    "d_oracle_scope": "(d) Oracle or packaging beyond the issue",
    "u_undeterminable": "Undeterminable",
}
B_LABELS = {
    "evidence_utilization": "Evidence utilization",
    "rule_threshold": "Rule threshold",
    "case_judgment": "Case judgment",
    "undeterminable": "Undeterminable",
}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--worklist",
        type=Path,
        default=Path("data/annotations/worklists/repo480_p1_typology_worklist_v1.jsonl"),
    )
    parser.add_argument(
        "--worklist-manifest",
        type=Path,
        default=Path("data/manifests/generated/repo480_p1_typology_worklist_manifest_v1.json"),
    )
    parser.add_argument(
        "--codes",
        type=Path,
        default=Path("data/annotations/typology/repo480_p1_typology_codes_c1_v1.jsonl"),
    )
    parser.add_argument(
        "--construct-rows",
        type=Path,
        default=Path("results/pilot/repo480_construct_validity_rows_v1.jsonl"),
    )
    parser.add_argument(
        "--frozen-labels",
        type=Path,
        default=Path("data/annotations/adjudicated/repo480_available_v1.jsonl"),
    )
    parser.add_argument(
        "--boundary-analysis",
        type=Path,
        default=Path("results/pilot/repo480_boundary_validation_analysis_v1.json"),
    )
    parser.add_argument(
        "--json-out",
        type=Path,
        default=Path("results/pilot/repo480_p1_non_strict_typology_v1.json"),
    )
    parser.add_argument(
        "--markdown-out",
        type=Path,
        default=Path("results/pilot/repo480_p1_non_strict_typology_v1.md"),
    )
    parser.add_argument(
        "--a-rows-out",
        type=Path,
        default=Path("results/pilot/repo480_p1_non_strict_typology_rows_v1.jsonl"),
    )
    parser.add_argument(
        "--b-rows-out",
        type=Path,
        default=Path("results/pilot/repo480_boundary_discordance_typology_rows_v1.jsonl"),
    )
    parser.add_argument(
        "--tex-out",
        type=Path,
        default=Path("paper/generated/repo480_p1_typology_summary.tex"),
    )
    args = parser.parse_args()
    try:
        analysis, a_rows, b_rows = analyze(args)
        _write_json(args.json_out, analysis)
        _write_jsonl(args.a_rows_out, a_rows)
        _write_jsonl(args.b_rows_out, b_rows)
        _write_text(args.markdown_out, _markdown(analysis))
        _write_text(args.tex_out, _tex(analysis))
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1
    a, b = analysis["set_a"], analysis["set_b"]
    print(
        f"OK: Set A {a['n']} rows, b={a['type_counts']['b_contract_choice']['total']}; "
        f"Set B {b['n']} rows, rule_threshold={b['source_counts']['rule_threshold']['total']}"
    )
    return 0


def analyze(args: argparse.Namespace) -> tuple[dict[str, Any], list[dict], list[dict]]:
    manifest = json.loads((ROOT / args.worklist_manifest).read_text(encoding="utf-8"))
    if sha256_file(ROOT / args.worklist) != manifest["worklist"]["sha256"]:
        raise ValueError("worklist hash does not match its manifest")
    codebook = ROOT / manifest["codebook"]["ref"]
    if sha256_file(codebook) != manifest["codebook"]["sha256"]:
        raise ValueError("codebook changed after the worklist was frozen")
    worklist = _jsonl(args.worklist)
    codes = _validate_codes(worklist, _jsonl(args.codes))

    construct = _jsonl(args.construct_rows)
    prefix_p1 = sum(r["available_only_primary_label"] == "P1" for r in construct)
    frozen = _jsonl(args.frozen_labels)
    frame_p1 = sum(r["primary_label"] == "P1" for r in frozen)
    frame_p23 = sum(r["primary_label"] in {"P2", "P3"} for r in frozen)
    panel = json.loads((ROOT / args.boundary_analysis).read_text(encoding="utf-8"))
    panel_estimate = panel["independent_stratified_prevalence"]["proportion"]

    a_rows, b_rows = [], []
    for work in worklist:
        code = codes[work["item_id"]]
        if work["set"] == "p1_non_strict":
            a_rows.append(_a_row(work, code))
        else:
            b_rows.append(_b_row(work, code))
    a_ids = {r["task_id"] for r in a_rows}
    for row in b_rows:
        row["in_p1_non_strict"] = row["task_id"] in a_ids
    shared = sorted(a_ids & {r["task_id"] for r in b_rows})

    analysis = {
        "schema_version": "repo480-p1-boundary-typology-analysis-v1",
        "status": "agent-coded-pending-expert-verification",
        "coder_id": CODER_ID,
        "coder_disclosure": (
            "Single analytic coding pass by an AI agent (Claude Opus 5.5) over existing "
            "returned records; not an expert annotation and not counted as one."
        ),
        "set_b_codes_commit_before_set_a_oracle": SET_B_CODES_COMMIT,
        "codebook": manifest["codebook"],
        "inputs": {
            str(path): sha256_file(ROOT / path)
            for path in (
                args.worklist,
                args.worklist_manifest,
                args.codes,
                args.construct_rows,
                args.frozen_labels,
                args.boundary_analysis,
            )
        },
        "set_a": _summarize_a(a_rows, prefix_p1, frame_p1, frame_p23, len(frozen), panel_estimate),
        "set_b": _summarize_b(b_rows),
        "shared_tasks": [
            {
                "task_id": task_id,
                "set_a_type": next(r["report_type"] for r in a_rows if r["task_id"] == task_id),
                "set_b_source": next(
                    r["divergence_source"] for r in b_rows if r["task_id"] == task_id
                ),
            }
            for task_id in shared
        ],
        "claim_boundary": [
            "Frozen repo480_available_v1 labels, 26/480, 0.094 and 76/112 are unchanged.",
            "Type counts describe 23 and 22 audited rows; they are not population rates.",
            "The displacement what-if is not a corrected, upper or lower prevalence estimate.",
            "Coding was performed by an AI agent and awaits independent expert verification.",
        ],
    }
    return analysis, a_rows, b_rows


def derive_a(codes: dict[str, Any]) -> str:
    kind = codes["divergence_kind"]
    basis = codes["oracle_basis"]
    supported = codes["predicted_supported"]
    if basis == "outside_issue_scope":
        return "d_oracle_scope"
    if kind == "implementation_only":
        return "a_same_contract"
    if basis == "required_by_packet":
        return "c_evidence_reading"
    if kind == "added_behavior" and basis == "admissible_not_selected":
        return "a_same_contract"
    if kind == "different_behavior" and supported == "no":
        return "c_evidence_reading"
    if kind == "different_behavior" and basis == "admissible_not_selected" and supported == "yes":
        return "b_contract_choice"
    return "u_undeterminable"


def derive_b(codes: dict[str, Any]) -> str:
    treatment = codes["p01_side_treatment"]
    engages = codes["p23_side_engages_p01_evidence"]
    cites = codes["p23_side_cites_packet_for_alternative"]
    if (treatment == "excluded_by_cited_evidence" and engages == "no") or (
        treatment == "not_addressed" and cites == "yes"
    ):
        return "evidence_utilization"
    if (
        treatment == "named_as_bounded_assumption"
        or codes["alternative_relation"] == "same_contract_variant"
    ):
        return "rule_threshold"
    if (treatment == "excluded_by_cited_evidence" and engages == "yes") or (
        treatment == "not_addressed" and cites == "no"
    ):
        return "case_judgment"
    return "undeterminable"


def _a_row(work: dict[str, Any], code: dict[str, Any]) -> dict[str, Any]:
    codes = code["codes"]
    derived = derive_a(codes)
    report = derived
    if derived == "b_contract_choice":
        report = "b_anticipated" if codes["assumption_anticipated"] == "yes" else "b_unanticipated"
    panel = work["boundary_panel"]
    return {
        "schema_version": "repo480-p1-non-strict-typology-row-v1",
        "item_id": work["item_id"],
        "task_id": work["task_id"],
        "construct_validity_match": work["construct_validity"]["final_match"],
        "derived_type": derived,
        "report_type": report,
        "divergence_kind": codes["divergence_kind"],
        "predicted_supported": codes["predicted_supported"],
        "oracle_basis": codes["oracle_basis"],
        "assumption_anticipated": codes["assumption_anticipated"],
        "secondary_types": codes["secondary_types"],
        "panel_binary_label": panel["independent_binary_label"] if panel else None,
    }


def _b_row(work: dict[str, Any], code: dict[str, Any]) -> dict[str, Any]:
    codes = code["codes"]
    panel = work["boundary_panel"]
    frozen_label = work["frozen"]["canonical"]["primary_label"]
    panel_label = panel["final"]["primary_label"]
    frozen_p23 = frozen_label in {"P2", "P3"}
    return {
        "schema_version": "repo480-boundary-discordance-typology-row-v1",
        "item_id": work["item_id"],
        "task_id": work["task_id"],
        "stratum": panel["stratum"],
        "frozen_primary_label": frozen_label,
        "panel_primary_label": panel_label,
        "direction": DIRECTIONS[1] if frozen_p23 else DIRECTIONS[0],
        "label_pair": f"{frozen_label}->{panel_label}",
        "p1_p2_boundary": {frozen_label, panel_label} == {"P1", "P2"},
        "divergence_source": derive_b(codes),
        "alternative_relation": codes["alternative_relation"],
        "p01_side_treatment": codes["p01_side_treatment"],
        "p23_side_engages_p01_evidence": codes["p23_side_engages_p01_evidence"],
        "p23_side_cites_packet_for_alternative": codes["p23_side_cites_packet_for_alternative"],
        "evidence_omitting_outcome": _omitting_outcome(codes, frozen_p23),
        "frozen_final_uses_repository_evidence": _uses_repo(work["frozen"]["canonical"]),
        "panel_final_uses_repository_evidence": _uses_repo(panel["final"]),
    }


def _summarize_a(
    rows: list[dict], prefix_p1: int, frame_p1: int, frame_p23: int, frame_n: int, panel: float
) -> dict[str, Any]:
    n = len(rows)
    verdicts = Counter(r["construct_validity_match"] for r in rows)
    type_counts = {}
    for name in A_TYPES + A_REPORT_TYPES:
        if name in type_counts:
            continue
        key = "derived_type" if name in A_TYPES else "report_type"
        members = [r for r in rows if r[key] == name]
        type_counts[name] = {
            "partial_match": sum(r["construct_validity_match"] == "partial_match" for r in members),
            "mismatch": sum(r["construct_validity_match"] == "mismatch" for r in members),
            **_rate(len(members), n),
        }
    secondary = Counter(t for r in rows for t in r["secondary_types"])
    crosstab = {}
    for name in A_REPORT_TYPES:
        members = [r for r in rows if r["report_type"] == name]
        crosstab[name] = {
            "panel_p01": sum(r["panel_binary_label"] == "P0/P1" for r in members),
            "panel_p23": sum(r["panel_binary_label"] == "P2/P3" for r in members),
            "not_in_panel": sum(r["panel_binary_label"] is None for r in members),
        }
    scenarios = []
    for name, k in (
        ("b_unanticipated", type_counts["b_unanticipated"]["count"]),
        ("b_all", type_counts["b_contract_choice"]["count"]),
    ):
        implied = frame_p1 * k / prefix_p1
        scenarios.append(
            {
                "scenario": name,
                "count_in_prefix_p1": k,
                **_rate(k, prefix_p1),
                "implied_frame_p1_rows": _round(implied),
                "what_if_p23_proportion": _round((frame_p23 + implied) / frame_n),
            }
        )
    return {
        "n": n,
        "verdict_split": dict(sorted(verdicts.items())),
        "type_counts": type_counts,
        "secondary_any_mention": dict(sorted(secondary.items())),
        "field_counts": {
            field: dict(sorted(Counter(r[field] for r in rows).items()))
            for field in ("divergence_kind", "predicted_supported", "oracle_basis")
        },
        "panel_crosstab": crosstab,
        "displacement_what_if": {
            "prefix_p1_rows": prefix_p1,
            "frame_p1_rows": frame_p1,
            "frame_p23_rows": frame_p23,
            "frame_rows": frame_n,
            "reference_frozen_rule": _round(frame_p23 / frame_n),
            "reference_independent_panel": panel,
            "scenarios": scenarios,
            "note": (
                "Moves k/47 of the frame's P1 rows to P2/P3. Strict-match rows may also hide "
                "contract choices and P0 non-strict rows are not coded, so this is neither a "
                "bound nor a corrected estimate."
            ),
        },
    }


def _summarize_b(rows: list[dict]) -> dict[str, Any]:
    source_counts = {}
    for name in B_SOURCES:
        members = [r for r in rows if r["divergence_source"] == name]
        source_counts[name] = {
            **{d: sum(r["direction"] == d for r in members) for d in DIRECTIONS},
            "p1_p2_boundary": sum(r["p1_p2_boundary"] for r in members),
            "total": len(members),
        }
    return {
        "n": len(rows),
        "direction_counts": {d: sum(r["direction"] == d for r in rows) for d in DIRECTIONS},
        "label_pairs": dict(sorted(Counter(r["label_pair"] for r in rows).items())),
        "p1_p2_boundary_rows": sum(r["p1_p2_boundary"] for r in rows),
        "source_counts": source_counts,
        "alternative_relation": dict(
            sorted(Counter(r["alternative_relation"] for r in rows).items())
        ),
        "p01_side_treatment": dict(sorted(Counter(r["p01_side_treatment"] for r in rows).items())),
        "evidence_omitting_outcome": dict(
            sorted(Counter(r["evidence_omitting_outcome"] for r in rows if r[
                "evidence_omitting_outcome"
            ]).items())
        ),
        "repository_evidence_use": {
            "frozen_final": sum(r["frozen_final_uses_repository_evidence"] for r in rows),
            "panel_final": sum(r["panel_final_uses_repository_evidence"] for r in rows),
        },
    }


def _validate_codes(worklist: list[dict], codes: list[dict]) -> dict[str, dict]:
    by_item = {}
    for code in codes:
        item = code.get("item_id")
        if item in by_item:
            raise ValueError(f"duplicate code for {item}")
        by_item[item] = code
    expected = {w["item_id"]: w for w in worklist}
    if set(by_item) != set(expected):
        raise ValueError("codes do not cover exactly the worklist items")
    for item, code in by_item.items():
        work = expected[item]
        if code.get("schema_version") != CODE_SCHEMA or code.get("coder_id") != CODER_ID:
            raise ValueError(f"{item}: unexpected schema or coder")
        if code.get("task_id") != work["task_id"] or code.get("set") != work["set"]:
            raise ValueError(f"{item}: task or set linkage mismatch")
        if not code.get("coder_note") or not code.get("evidence_refs"):
            raise ValueError(f"{item}: coder_note and evidence_refs are required")
        values = code["codes"]
        fields = A_FIELDS if work["set"] == "p1_non_strict" else B_FIELDS
        for field, allowed in fields.items():
            if values.get(field) not in allowed:
                raise ValueError(f"{item}: invalid {field}={values.get(field)!r}")
        if work["set"] == "p1_non_strict":
            if not values.get("oracle_divergence"):
                raise ValueError(f"{item}: oracle_divergence is required")
            implementation = values["divergence_kind"] == "implementation_only"
            if implementation != (values["oracle_basis"] == "not_applicable"):
                raise ValueError(f"{item}: implementation_only must pair with not_applicable")
            if implementation != (values["assumption_anticipated"] == "not_applicable"):
                raise ValueError(f"{item}: assumption_anticipated not_applicable mismatch")
            if not set(values.get("secondary_types", [])) <= set(A_TYPES):
                raise ValueError(f"{item}: invalid secondary_types")
        else:
            if not values.get("disputed_alternative"):
                raise ValueError(f"{item}: disputed_alternative is required")
            excluded = values["p01_side_treatment"] == "excluded_by_cited_evidence"
            if excluded == (values["p23_side_engages_p01_evidence"] == "not_applicable"):
                raise ValueError(f"{item}: p23_side_engages_p01_evidence applicability mismatch")
    return by_item


def _omitting_outcome(codes: dict[str, Any], frozen_p23: bool) -> str | None:
    # Which adjudicated outcome left the decisive packet evidence unused.
    if derive_b(codes) != "evidence_utilization":
        return None
    p01_omits = codes["p01_side_treatment"] == "not_addressed"
    return "frozen" if p01_omits != frozen_p23 else "panel"


def _uses_repo(record: dict[str, Any]) -> bool:
    return bool(set(record.get("available_evidence_used") or []) - ISSUE_ONLY)


def _rate(count: int, denominator: int) -> dict[str, Any]:
    lower, upper = _wilson(count, denominator)
    return {
        "count": count,
        "total": count,
        "denominator": denominator,
        "proportion": _round(count / denominator),
        "wilson_95_ci": {"lower": _round(lower), "upper": _round(upper)},
    }


def _wilson(count: int, denominator: int) -> tuple[float, float]:
    z = NormalDist().inv_cdf(0.975)
    p = count / denominator
    z2 = z * z
    center = (p + z2 / (2 * denominator)) / (1 + z2 / denominator)
    margin = z * math.sqrt(p * (1 - p) / denominator + z2 / (4 * denominator**2))
    margin /= 1 + z2 / denominator
    return max(0.0, center - margin), min(1.0, center + margin)


def _round(value: float) -> float:
    return round(value, 6)


def _fmt_rate(rate: dict[str, Any]) -> str:
    ci = rate["wilson_95_ci"]
    return (
        f"{rate['count']}/{rate['denominator']} = {rate['proportion']:.3f} "
        f"[{ci['lower']:.3f}, {ci['upper']:.3f}]"
    )


def _markdown(analysis: dict[str, Any]) -> str:
    a, b = analysis["set_a"], analysis["set_b"]
    what_if = a["displacement_what_if"]
    lines = [
        "# Repo480 P1 Non-Strict and Boundary-Discordance Typology (RR-E)",
        "",
        "- **Status:** `agent-coded-pending-expert-verification`",
        "- **Authority:** RR-E typology counts derived from the frozen codebook",
        "- **Generated by:** `scripts/analyze_repo480_p1_typology.py`",
        "- **Codebook:** `docs/repo480_p1_boundary_typology_codebook.md`",
        "",
        "> " + analysis["coder_disclosure"] + " Set B codes were committed "
        f"(`{analysis['set_b_codes_commit_before_set_a_oracle']}`) before any Set A oracle "
        "material was opened.",
        "",
        "## Set A: P1 rows that did not strictly match the oracle",
        "",
        f"Observation: {a['n']} rows ({a['verdict_split'].get('partial_match', 0)} partial, "
        f"{a['verdict_split'].get('mismatch', 0)} mismatch). Types are derived from coded "
        "fields by codebook section 4.1.",
        "",
        "| Type | Partial | Mismatch | Total / Wilson 95% CI |",
        "| --- | ---: | ---: | --- |",
    ]
    for name in A_REPORT_TYPES:
        row = a["type_counts"][name]
        lines.append(
            f"| {A_LABELS[name]} | {row['partial_match']} | {row['mismatch']} | "
            f"{_fmt_rate(row)} |"
        )
    lines += [
        "",
        "Secondary types mentioned: "
        + (", ".join(f"`{k}` {v}" for k, v in a["secondary_any_mention"].items()) or "none")
        + ".",
        "",
        "| Type | Independent panel P0/P1 | Independent panel P2/P3 | Not in panel |",
        "| --- | ---: | ---: | ---: |",
    ]
    for name in A_REPORT_TYPES:
        row = a["panel_crosstab"][name]
        if sum(row.values()):
            lines.append(
                f"| {A_LABELS[name]} | {row['panel_p01']} | {row['panel_p23']} | "
                f"{row['not_in_panel']} |"
            )
    lines += [
        "",
        "### Displacement what-if",
        "",
        f"Among the {what_if['prefix_p1_rows']} P1 rows of the frozen 120-prefix, moving the "
        f"contract-choice rows to P2/P3 and scaling to the frame's {what_if['frame_p1_rows']} "
        "P1 rows gives:",
        "",
        "| Scenario | Prefix share | What-if P2/P3 proportion |",
        "| --- | --- | ---: |",
    ]
    for row in what_if["scenarios"]:
        lines.append(
            f"| `{row['scenario']}` | {_fmt_rate(row)} | {row['what_if_p23_proportion']:.3f} |"
        )
    lines += [
        "",
        f"References: frozen rule {what_if['reference_frozen_rule']:.3f}, independent panel "
        f"{what_if['reference_independent_panel']:.3f}. {what_if['note']}",
        "",
        "## Set B: rows where the frozen and independent-panel boundaries disagree",
        "",
        f"Observation: {b['n']} rows; frozen P0/P1 to panel P2/P3 "
        f"{b['direction_counts']['frozen_p01_to_panel_p23']}, reverse "
        f"{b['direction_counts']['frozen_p23_to_panel_p01']}; {b['p1_p2_boundary_rows']} rows "
        "lie on the P1/P2 boundary. Sources are derived by codebook section 5.1.",
        "",
        "| Source | Frozen P0/P1 to panel P2/P3 | Reverse | P1/P2 rows | Total |",
        "| --- | ---: | ---: | ---: | ---: |",
    ]
    for name in B_SOURCES:
        row = b["source_counts"][name]
        lines.append(
            f"| {B_LABELS[name]} | {row['frozen_p01_to_panel_p23']} | "
            f"{row['frozen_p23_to_panel_p01']} | {row['p1_p2_boundary']} | {row['total']} |"
        )
    lines += [
        "",
        "Alternative relation: "
        + ", ".join(f"`{k}` {v}" for k, v in b["alternative_relation"].items())
        + ". P0/P1-side treatment: "
        + ", ".join(f"`{k}` {v}" for k, v in b["p01_side_treatment"].items())
        + ".",
    ]
    b_in_panel = sum(
        a["panel_crosstab"][name][key]
        for name in ("b_anticipated", "b_unanticipated")
        for key in ("panel_p01", "panel_p23")
    )
    b_panel_p23 = sum(
        a["panel_crosstab"][name]["panel_p23"] for name in ("b_anticipated", "b_unanticipated")
    )
    omitted = b["evidence_omitting_outcome"]
    counts = a["type_counts"]
    lines += [
        "",
        "Evidence-utilization rows by the outcome that left the decisive evidence unused: "
        f"frozen {omitted.get('frozen', 0)}, panel {omitted.get('panel', 0)}.",
        "",
        "## Interpretation",
        "",
        "- Set A: no non-strict P1 row is explained by misread task-time evidence "
        f"({counts['c_evidence_reading']['count']}/{a['n']}). Most rows "
        f"({counts['b_contract_choice']['count']}/{a['n']}) involve observably different "
        "behaviors that the packet left open and the hidden test fixed. Where the P1 record "
        f"had named that choice as its bounded assumption ({counts['b_anticipated']['count']} "
        "rows), the hidden test selected within a residual the codebook admits in P1, which "
        "supports the reading that oracle selection also operates inside P1. The remaining "
        f"{counts['b_unanticipated']['count']} contract-choice rows are boundary-displacement "
        "candidates.",
        f"- The independent panel labeled {b_panel_p23} of the {b_in_panel} contract-choice "
        "rows it covered as P2/P3, so a second panel mostly did not recognize the competing "
        "behavior at task time either.",
        f"- Set B: {b['source_counts']['rule_threshold']['total']}/{b['n']} disagreements "
        "concern whether an alternative both outcomes acknowledge is a separate target, the "
        "same gray zone as the anticipated Set A rows. Evidence-use differences explain "
        f"{b['source_counts']['evidence_utilization']['total']} rows and occur in both "
        "outcomes.",
        "- Codebook clarification candidate (new version only): treat a residual choice that "
        "changes a tested observable (return value, success versus exception, default output, "
        "emitted text) as a separate target unless packet evidence selects one, and record "
        "such alternatives explicitly in P1 records.",
        "",
        "## Shared tasks",
        "",
        "| Task | Set A type | Set B source |",
        "| --- | --- | --- |",
    ]
    for row in analysis["shared_tasks"]:
        lines.append(f"| `{row['task_id']}` | `{row['set_a_type']}` | `{row['set_b_source']}` |")
    lines += ["", "## Claim boundary", ""]
    lines += [f"- {item}" for item in analysis["claim_boundary"]]
    return "\n".join(lines) + "\n"


def _tex(analysis: dict[str, Any]) -> str:
    a, b = analysis["set_a"], analysis["set_b"]
    lines = [
        "% Generated by scripts/analyze_repo480_p1_typology.py; do not edit manually.",
        "\\begin{table}[t]",
        "\\caption{Typology of the 23 non-strict P1 rows and the 22 boundary-discordant "
        "rows (single coding pass; diagnostic counts).}",
        "\\label{tab:repo480p1typology}",
        "\\centering",
        "\\small",
        "\\begin{tabular}{@{}p{0.56\\linewidth}rrr@{}}",
        "\\hline",
        "Non-strict P1 rows & Partial & Mismatch & Total \\\\",
        "\\hline",
    ]
    for name in A_REPORT_TYPES:
        row = a["type_counts"][name]
        lines.append(
            f"{A_LABELS[name]} & {row['partial_match']} & {row['mismatch']} & {row['count']} \\\\"
        )
    lines += [
        "\\hline",
        "\\end{tabular}",
        "",
        "\\smallskip",
        "\\begin{tabular}{@{}p{0.56\\linewidth}rrr@{}}",
        "\\hline",
        "Boundary-discordant rows & Frozen P0/P1 & Frozen P2/P3 & Total \\\\",
        "\\hline",
    ]
    for name in B_SOURCES:
        row = b["source_counts"][name]
        lines.append(
            f"{B_LABELS[name]} & {row['frozen_p01_to_panel_p23']} & "
            f"{row['frozen_p23_to_panel_p01']} & {row['total']} \\\\"
        )
    lines += ["\\hline", "\\end{tabular}", "\\end{table}", ""]
    return "\n".join(lines)


def _jsonl(path: Path) -> list[dict[str, Any]]:
    with (ROOT / path).open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def _write_json(path: Path, value: dict[str, Any]) -> None:
    target = ROOT / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    target = ROOT / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(b"".join(canonical_json_bytes(row) for row in rows))


def _write_text(path: Path, text: str) -> None:
    target = ROOT / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
