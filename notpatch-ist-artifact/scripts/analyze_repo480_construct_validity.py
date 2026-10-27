#!/usr/bin/env python3
"""Derive the repo480 bidirectional construct-validity result from the audit panel."""

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
from scripts.selfcheck_repo480_construct_validity_adjudication_return import (  # noqa: E402
    validate_return,
)


BATCH_ID = "repo480_construct_validity_v1"
CONFIDENCE_LEVEL = 0.95
P01_AXIS = "p01_direction_match"
P23_AXIS = "p23_hindsight_uniqueness"
P01_FIELD = "predicted_direction_match"
P23_FIELDS = ("available_evidence_unique_in_hindsight", "oracle_direction_in_candidate_set")
AXIS_FIELDS = {P01_AXIS: (P01_FIELD,), P23_AXIS: P23_FIELDS}
REVIEWERS = ("repo480_cv_r1", "repo480_cv_r2", "repo480_cv_r3")
EXPECTED_AXIS_COUNTS = {P01_AXIS: 112, P23_AXIS: 26}
EXPECTED_LABEL_COUNTS = {"P0": 65, "P1": 47, "P2": 22, "P3": 4}

DEFAULT_PATHS = {
    "tasks": ROOT / "data/annotations/worklists/repo480_construct_validity_tasks_v1.jsonl",
    "r1": ROOT
    / "data/annotations/oracle_gap/repo480_construct_validity_panel/repo480_construct_validity_r1.jsonl",
    "r2": ROOT
    / "data/annotations/oracle_gap/repo480_construct_validity_panel/repo480_construct_validity_r2.jsonl",
    "r3": ROOT
    / "data/annotations/oracle_gap/repo480_construct_validity_panel/repo480_construct_validity_r3.jsonl",
    "returns_manifest": ROOT
    / "data/manifests/generated/repo480_construct_validity_returns_manifest_v1.json",
    "raw_agreement": ROOT / "results/pilot/repo480_construct_validity_raw_agreement_v1.json",
    "worklist": ROOT
    / "data/annotations/worklists/repo480_construct_validity_adjudication_worklist_v1.jsonl",
    "labels": ROOT / "data/annotations/adjudicated/repo480_available_v1.jsonl",
    "adjudication_return": ROOT
    / "data/annotations/oracle_gap/repo480_construct_validity_panel/repo480_construct_validity_adjudication.jsonl",
    "canonical_out": ROOT
    / "data/annotations/oracle_gap/repo480_construct_validity_panel/repo480_construct_validity_adjudication.jsonl",
    "manifest_out": ROOT
    / "data/manifests/generated/repo480_construct_validity_adjudication_manifest_v1.json",
    "json_out": ROOT / "results/pilot/repo480_construct_validity_analysis_v1.json",
    "markdown_out": ROOT / "results/pilot/repo480_construct_validity_analysis_v1.md",
    "rows_out": ROOT / "results/pilot/repo480_construct_validity_rows_v1.jsonl",
    "tex_out": ROOT / "paper/generated/repo480_construct_validity_summary.tex",
    "bounds_json_out": ROOT / "results/pilot/repo480_construct_validity_bounds_v1.json",
    "bounds_markdown_out": ROOT / "results/pilot/repo480_construct_validity_bounds_v1.md",
}

# Frozen inputs. The adjudication return is excluded: its hash is unknown until returned.
EXPECTED_SHA256 = {
    "tasks": "1580a59cb9c284a0c3959aaba575072d04dc49f1f9ce1f6cb7a293af33bbdbd2",
    "r1": "2357a31d3ed65865e30c4310050b162ef8d727d583d92cf9fcbdbbbd5ab8343f",
    "r2": "3726e373e73f8ced07ce3c86360a80aed839e7e3de050390fa79526bd582f6a1",
    "r3": "d1c2e5c48b8c8774f3b657314e6e9c0649e9327a19192929a998e1cc64a62b54",
    "returns_manifest": "1f5631ac9b08478b8f32b73a76844d78d8fd049ed46463d5676259d8238c082b",
    "raw_agreement": "f76db79fd518718403ac1985e6df483b64329e416c9dfaeff1bdd74b4bc4c553",
    "worklist": "b5d592fc0ea8b2dcb97fbdada2c9794c18dce966f05deae338ca409ab62cf450",
    "labels": "98b33aabbd10b34bd093c4590c2f6c42476f999dd0e60e64794dbb0544f4e63d",
}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    for name in DEFAULT_PATHS:
        parser.add_argument(
            f"--{name.replace('_', '-')}", type=Path, default=DEFAULT_PATHS[name]
        )
    parser.add_argument(
        "--pre-adjudication",
        action="store_true",
        help="emit the determinacy envelope while the adjudication return is still pending",
    )
    args = parser.parse_args()
    inputs = {name: getattr(args, name) for name in EXPECTED_SHA256}

    try:
        input_metadata = _validate_frozen_inputs(inputs)
        tasks = _load_jsonl(inputs["tasks"])
        returns = {rid: _index(_load_jsonl(getattr(args, key)), rid) for rid, key in
                   zip(REVIEWERS, ("r1", "r2", "r3"), strict=True)}
        worklist = _load_jsonl(inputs["worklist"])
        raw_agreement = _read_object(inputs["raw_agreement"])
        returns_manifest = _read_object(inputs["returns_manifest"])
        labels = _index(_load_jsonl(inputs["labels"]), "labels")
        decisions = _load_jsonl(args.adjudication_return)
        _validate_inputs(tasks, returns, worklist, raw_agreement, returns_manifest, labels)

        pending = [row["task_id"] for row in decisions
                   if row.get("adjudication_status") == "pending"]
        if args.pre_adjudication:
            if not pending:
                raise ValueError(
                    "adjudication is complete; rerun without --pre-adjudication "
                    "to produce the final construct-validity result"
                )
        elif pending:
            raise ValueError(
                f"{len(pending)} of {len(decisions)} repo480_cv_adj rows are still pending "
                f"(first: {pending[0]}). The final construct-validity rate and CI are not "
                "computed until every disputed row is returned. Use --pre-adjudication "
                "for the determinacy envelope."
            )
        if not args.pre_adjudication:
            validate_return(worklist, decisions)
            if any(row["adjudication_status"] == "protocol_deviation" for row in decisions):
                raise ValueError("a protocol-deviation row must be resolved before analysis")

        rows = _derive_rows(tasks, returns, worklist, decisions, labels)
        if args.pre_adjudication:
            report = _build_bounds(rows, raw_agreement, input_metadata, len(pending))
            outputs = {
                args.bounds_json_out: canonical_json_bytes(report),
                args.bounds_markdown_out: _build_bounds_markdown(report).encode("utf-8"),
            }
        else:
            _preserve_exact(args.adjudication_return, args.canonical_out)
            manifest = _build_manifest(input_metadata, args.canonical_out, worklist, decisions)
            manifest_bytes = canonical_json_bytes(manifest)
            report = _build_analysis(
                rows, raw_agreement, input_metadata, decisions,
                _artifact_ref(args.manifest_out), sha256_bytes(manifest_bytes),
            )
            outputs = {
                args.manifest_out: manifest_bytes,
                args.json_out: canonical_json_bytes(report),
                args.markdown_out: _build_markdown(report).encode("utf-8"),
                args.rows_out: b"".join(canonical_json_bytes(row) for row in rows),
                args.tex_out: _build_tex(report).encode("utf-8"),
            }
        for path, content in outputs.items():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1

    if args.pre_adjudication:
        match = report["bounds"]["p01_direction_match"]
        pessimism = report["bounds"]["p23_false_pessimism"]
        print(
            "OK: wrote repo480 construct-validity determinacy envelope "
            f"(direction match {match['lower_count']}-{match['upper_count']}/"
            f"{match['denominator']}, false pessimism {pessimism['lower_count']}/"
            f"{pessimism['denominator']} closed={pessimism['closed']})"
        )
    else:
        match = report["primary"]["p01_direction_match"]
        pessimism = report["primary"]["p23_false_pessimism"]
        print(
            "OK: wrote repo480 construct-validity analysis "
            f"(direction match {match['count']}/{match['denominator']}, "
            f"false pessimism {pessimism['count']}/{pessimism['denominator']})"
        )
    return 0


def _validate_frozen_inputs(inputs: dict[str, Path]) -> dict[str, dict[str, Any]]:
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
    tasks: list[dict[str, Any]],
    returns: dict[str, dict[str, dict[str, Any]]],
    worklist: list[dict[str, Any]],
    raw_agreement: dict[str, Any],
    returns_manifest: dict[str, Any],
    labels: dict[str, dict[str, Any]],
) -> None:
    order = [row["task_id"] for row in tasks]
    if len(set(order)) != len(order):
        raise ValueError("audit task IDs must be unique")
    axis_counts = Counter(row["audit_axis"] for row in tasks)
    if dict(axis_counts) != EXPECTED_AXIS_COUNTS:
        raise ValueError(f"frozen axis counts changed: {dict(axis_counts)}")
    for rid, rows in returns.items():
        if list(rows) != order:
            raise ValueError(f"{rid} task set or order does not match the frozen tasks")
        for task_id, row in rows.items():
            if row.get("annotation_status") != "complete":
                raise ValueError(f"{rid}:{task_id} is not complete")
            if row.get("protocol_deviation") is not None:
                raise ValueError(f"{rid}:{task_id} reports a protocol deviation")
            if row.get("prohibited_evidence_used") is not False:
                raise ValueError(f"{rid}:{task_id} reports prohibited evidence")

    gate = returns_manifest.get("acceptance_gate", {})
    if not all(gate.get(field) is True for field in (
        "adjudication_release_allowed", "all_rows_complete",
        "immutable_linkage_passed", "raw_returns_preserved_exactly", "selfcheck_passed",
    )):
        raise ValueError("construct-validity acceptance gate is not closed")
    if raw_agreement.get("schema_version") != "repo480-construct-validity-raw-agreement-v1":
        raise ValueError("raw agreement schema mismatch")
    if raw_agreement["disagreement_queue"]["task_ids"] != [r["task_id"] for r in worklist]:
        raise ValueError("raw agreement disagreement queue does not match the worklist")

    missing = [task_id for task_id in order if task_id not in labels]
    if missing:
        raise ValueError(f"{len(missing)} audit tasks have no canonical label")
    label_counts = Counter(labels[task_id]["primary_label"] for task_id in order)
    if dict(label_counts) != EXPECTED_LABEL_COUNTS:
        raise ValueError(f"frozen label strata changed: {dict(label_counts)}")


def _derive_rows(
    tasks: list[dict[str, Any]],
    returns: dict[str, dict[str, dict[str, Any]]],
    worklist: list[dict[str, Any]],
    decisions: list[dict[str, Any]],
    labels: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    work_by_task = _index(worklist, "worklist")
    decision_by_task = _index(decisions, "adjudication")
    rows = []
    for task in tasks:
        task_id = task["task_id"]
        axis = task["audit_axis"]
        label = labels[task_id]
        raw = {rid: {f: returns[rid][task_id][f] for f in AXIS_FIELDS[axis]}
               for rid in REVIEWERS}
        final: dict[str, Any] = {}
        sources: dict[str, str] = {}
        disagree = []
        for field in AXIS_FIELDS[axis]:
            values = {raw[rid][field] for rid in REVIEWERS}
            if len(values) == 1:
                final[field] = values.pop()
                sources[field] = "raw_exact_consensus"
                continue
            disagree.append(field)
            work = work_by_task.get(task_id)
            if work is None or field not in work.get("disagree_axes", []):
                raise ValueError(f"{task_id}: {field} disagrees but is not in the worklist")
            decision = decision_by_task.get(task_id)
            if decision is None:
                raise ValueError(f"{task_id}: no adjudication row")
            value = None
            if decision.get("adjudication_status") in {"adjudicated", "unresolved"}:
                value = decision["adjudicated_values"].get(field)
            final[field] = value
            sources[field] = "third_reviewer_adjudication" if value else "undetermined"
        expected_axes = set(work_by_task.get(task_id, {}).get("disagree_axes", []))
        if set(disagree) != expected_axes:
            raise ValueError(f"{task_id}: derived disagreement axes do not match the worklist")
        rows.append({
            "schema_version": "repo480-construct-validity-row-v1",
            "annotation_batch_id": BATCH_ID,
            "ordinal": task["ordinal"],
            "task_id": task_id,
            "random_rank": task["random_rank"],
            "audit_axis": axis,
            "available_only_primary_label": label["primary_label"],
            "data_quality": label["data_quality"],
            "raw_controlled_fields": raw,
            "disagree_axes": disagree,
            "field_sources": sources,
            "final_controlled_fields": final,
        })
    return rows


def _count(
    rows: list[dict[str, Any]],
    field: str,
    accept: set[str],
    restrict=None,
) -> tuple[int, int, int]:
    """Return (determined hits, undetermined rows, denominator) for one predicate."""
    sub = [row for row in rows
           if field in row["final_controlled_fields"] and (restrict is None or restrict(row))]
    determined = sum(1 for row in sub
                     if row["field_sources"][field] != "undetermined"
                     and row["final_controlled_fields"][field] in accept)
    undetermined = sum(1 for row in sub if row["field_sources"][field] == "undetermined")
    return determined, undetermined, len(sub)


def _measure(rows, field, accept, restrict=None) -> dict[str, Any]:
    determined, undetermined, denominator = _count(rows, field, accept, restrict)
    if undetermined:
        raise ValueError(f"{field}: {undetermined} rows are still undetermined")
    return _rate(determined, denominator)


def _envelope(rows, field, accept, restrict=None) -> dict[str, Any]:
    determined, undetermined, denominator = _count(rows, field, accept, restrict)
    lower = _rate(determined, denominator)
    upper = _rate(determined + undetermined, denominator)
    return {
        "denominator": denominator,
        "undetermined": undetermined,
        "closed": undetermined == 0,
        "lower_count": determined,
        "upper_count": determined + undetermined,
        "lower": lower,
        "upper": upper,
    }


def _predicates(rows: list[dict[str, Any]]) -> dict[str, tuple]:
    """Named (field, accepted values, row filter) triples shared by both modes."""
    q0 = lambda row: row["data_quality"] == "Q0"  # noqa: E731
    strat = lambda name: (lambda row: row["available_only_primary_label"] == name)  # noqa: E731
    return {
        "p01_direction_match": (P01_FIELD, {"match"}, None),
        "p01_match_or_partial": (P01_FIELD, {"match", "partial_match"}, None),
        "p01_false_confidence": (P01_FIELD, {"mismatch"}, None),
        "p01_not_assessable": (P01_FIELD, {"not_assessable"}, None),
        "p23_false_pessimism": (P23_FIELDS[0], {"yes"}, None),
        "p23_oracle_in_candidate_set": (P23_FIELDS[1], {"yes"}, None),
        "p01_direction_match_q0_only": (P01_FIELD, {"match"}, q0),
        "p23_false_pessimism_q0_only": (P23_FIELDS[0], {"yes"}, q0),
        "p01_direction_match_p0": (P01_FIELD, {"match"}, strat("P0")),
        "p01_direction_match_p1": (P01_FIELD, {"match"}, strat("P1")),
        "p23_false_pessimism_p2": (P23_FIELDS[0], {"yes"}, strat("P2")),
        "p23_false_pessimism_p3": (P23_FIELDS[0], {"yes"}, strat("P3")),
    }


PRIMARY_KEYS = ("p01_direction_match", "p23_false_pessimism")
SENSITIVITY_KEYS = (
    "p01_match_or_partial", "p01_false_confidence", "p01_not_assessable",
    "p23_oracle_in_candidate_set", "p01_direction_match_q0_only",
    "p23_false_pessimism_q0_only", "p01_direction_match_p0", "p01_direction_match_p1",
    "p23_false_pessimism_p2", "p23_false_pessimism_p3",
)


def _raw_sensitivity(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Reviewer-level intersection and union, independent of any adjudication."""
    result = {}
    for name, (field, accept) in {
        "p01_match": (P01_FIELD, {"match"}),
        "p01_match_or_partial": (P01_FIELD, {"match", "partial_match"}),
        "p01_mismatch": (P01_FIELD, {"mismatch"}),
        "p23_false_pessimism": (P23_FIELDS[0], {"yes"}),
        "p23_oracle_in_candidate_set": (P23_FIELDS[1], {"yes"}),
    }.items():
        sub = [row for row in rows if field in row["final_controlled_fields"]]
        hits = {rid: {row["task_id"] for row in sub
                      if row["raw_controlled_fields"][rid][field] in accept}
                for rid in REVIEWERS}
        intersection = set.intersection(*hits.values())
        union = set.union(*hits.values())
        result[name] = {
            "n": len(sub),
            "reviewer_counts": {rid: len(hits[rid]) for rid in REVIEWERS},
            "intersection": _rate(len(intersection), len(sub)),
            "union": _rate(len(union), len(sub)),
        }
    return result


def _fisher_exact_two_sided(a: int, b: int, c: int, d: int) -> float:
    """Two-sided Fisher exact p-value for the 2x2 table [[a, b], [c, d]]."""
    row1, row2, col1 = a + b, c + d, a + c
    total = row1 + row2
    observed = math.comb(row1, a) * math.comb(row2, c) / math.comb(total, col1)
    p_value = 0.0
    for hit in range(max(0, col1 - row2), min(row1, col1) + 1):
        probability = (
            math.comb(row1, hit)
            * math.comb(row2, col1 - hit)
            / math.comb(total, col1)
        )
        if probability <= observed * (1 + 1e-9):
            p_value += probability
    return min(1.0, p_value)


def _stratum_separation(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Worst-case P0 vs P1 comparison over every admissible adjudication outcome."""
    p0_low, _, p0_n = _count(rows, P01_FIELD, {"match"},
                             lambda row: row["available_only_primary_label"] == "P0")
    p1_low, p1_open, p1_n = _count(rows, P01_FIELD, {"match"},
                                   lambda row: row["available_only_primary_label"] == "P1")
    p1_high = p1_low + p1_open
    adverse_p0 = _rate(p0_low, p0_n)
    favourable_p1 = _rate(p1_high, p1_n)
    return {
        "comparison": "adverse P0 direction match versus favourable P1 direction match",
        "adverse_p0": adverse_p0,
        "favourable_p1": favourable_p1,
        "point_estimates_separated": adverse_p0["proportion"] > favourable_p1["proportion"],
        "worst_case_difference": _round(
            adverse_p0["proportion"] - favourable_p1["proportion"]
        ),
        "wilson_intervals_disjoint": (
            adverse_p0["wilson_95_ci"]["lower"] > favourable_p1["wilson_95_ci"]["upper"]
        ),
        "worst_case_fisher_exact_p": _round(
            _fisher_exact_two_sided(p0_low, p0_n - p0_low, p1_high, p1_n - p1_high)
        ),
    }


def _distributions(rows: list[dict[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for axis, fields in AXIS_FIELDS.items():
        sub = [row for row in rows if row["audit_axis"] == axis]
        result[axis] = {
            field: dict(sorted(Counter(
                row["final_controlled_fields"][field] or "undetermined" for row in sub
            ).items()))
            for field in fields
        }
    return result


def _p01_label_strata_distributions(rows: list[dict[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for label in ("P0", "P1"):
        selected = [
            row for row in rows
            if row["audit_axis"] == P01_AXIS
            and row["available_only_primary_label"] == label
        ]
        counts = Counter(row["final_controlled_fields"][P01_FIELD] for row in selected)
        result[label] = {
            "n": len(selected),
            "match": counts["match"],
            "partial_match": counts["partial_match"],
            "mismatch": counts["mismatch"],
        }
    return result


def _provenance(rows: list[dict[str, Any]]) -> dict[str, Any]:
    counts = Counter(source for row in rows for source in row["field_sources"].values())
    return {
        "field_decisions": dict(sorted(counts.items())),
        "rows_with_dispute": sum(1 for row in rows if row["disagree_axes"]),
        "rows_exact_consensus": sum(1 for row in rows if not row["disagree_axes"]),
    }


def _cross_check(rows: list[dict[str, Any]], raw_agreement: dict[str, Any]) -> None:
    """Recomputed consensus counts must match the frozen raw-agreement artifact."""
    exact = sum(1 for row in rows if not row["disagree_axes"])
    frozen = raw_agreement["row_consensus"]["overall"]
    if exact != frozen["exact_count"] or len(rows) != frozen["n"]:
        raise ValueError(
            f"recomputed exact consensus {exact}/{len(rows)} differs from the frozen "
            f"{frozen['exact_count']}/{frozen['n']}"
        )


def _build_analysis(rows, raw_agreement, input_metadata, decisions, manifest_ref, manifest_sha):
    _cross_check(rows, raw_agreement)
    predicates = _predicates(rows)
    unresolved = [row["task_id"] for row in decisions
                  if row["adjudication_status"] == "unresolved"]
    if unresolved:
        raise ValueError(
            f"{len(unresolved)} adjudication rows are unresolved (first: {unresolved[0]}); "
            "handle them explicitly before releasing a final rate"
        )
    disputed_tasks = {row["task_id"] for row in rows if row["disagree_axes"]}
    adverse = _rate(
        sum(1 for row in rows
            if row["audit_axis"] == P01_AXIS
            and row["task_id"] not in disputed_tasks
            and row["final_controlled_fields"][P01_FIELD] == "match"),
        EXPECTED_AXIS_COUNTS[P01_AXIS],
    )
    return {
        "schema_version": "repo480-construct-validity-analysis-v1",
        "analysis_id": "repo480-construct-validity-analysis-v1",
        "annotation_batch_id": BATCH_ID,
        "status": "canonical-pilot",
        "inputs": input_metadata,
        "adjudication_manifest": {"ref": manifest_ref, "sha256": manifest_sha},
        "denominators": {
            "p01_direction_match": EXPECTED_AXIS_COUNTS[P01_AXIS],
            "p23_false_pessimism": EXPECTED_AXIS_COUNTS[P23_AXIS],
            "selection_rule": {
                "p01_direction_match": "frozen prevalence_random_rank <= 120 P0/P1 rows",
                "p23_false_pessimism": "all P2/P3 rows in the frozen 480 random frame",
            },
        },
        "primary": {key: _measure(rows, *predicates[key]) for key in PRIMARY_KEYS},
        "sensitivity": {
            **{key: _measure(rows, *predicates[key]) for key in SENSITIVITY_KEYS},
            "p01_dispute_as_adverse": adverse,
            "raw_reviewer": _raw_sensitivity(rows),
        },
        "final_distributions": _distributions(rows),
        "p01_label_strata_distributions": _p01_label_strata_distributions(rows),
        "decision_provenance": _provenance(rows),
        "claim_scope": {
            "reports": [
                "adjudicated P0/P1 predicted-direction match rate on the frozen 120-prefix subset",
                "adjudicated P2/P3 hindsight false-pessimism rate on the full 480-frame census",
                "Wilson 95% CI, label strata, Q0-only, adverse and raw intersection/union sensitivity",
            ],
            "does_not_report": [
                "revision of any available-only P-label",
                "census of all 454 P0/P1 rows",
                "generalization to broad APR populations or automatic patch authorization",
            ],
        },
    }


def _build_bounds(rows, raw_agreement, input_metadata, pending_count):
    _cross_check(rows, raw_agreement)
    predicates = _predicates(rows)
    bounds = {key: _envelope(rows, *predicates[key])
              for key in PRIMARY_KEYS + SENSITIVITY_KEYS}
    return {
        "schema_version": "repo480-construct-validity-bounds-v1",
        "analysis_id": "repo480-construct-validity-bounds-v1",
        "annotation_batch_id": BATCH_ID,
        "status": "pre-adjudication",
        "inputs": input_metadata,
        "pending_adjudication_rows": pending_count,
        "bounds": bounds,
        "closed_metrics": sorted(key for key, value in bounds.items() if value["closed"]),
        "open_metrics": sorted(key for key, value in bounds.items() if not value["closed"]),
        "stratum_separation": _stratum_separation(rows),
        "raw_reviewer": _raw_sensitivity(rows),
        "decision_provenance": _provenance(rows),
        "claim_scope": {
            "reports": [
                "which construct-validity metrics the three independent returns already close",
                "the P0 versus P1 direction-match ordering that holds under every adjudication",
                "the adverse and favourable envelope the pending adjudication can still move",
            ],
            "does_not_report": [
                "final construct-validity rates for metrics with pending disputes",
                "any point estimate inside an open envelope",
            ],
        },
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


def _build_manifest(input_metadata, canonical_out, worklist, decisions):
    axis_counts = Counter(field for row in worklist for field in row.get("disagree_axes", []))
    return {
        "schema_version": "repo480-construct-validity-adjudication-manifest-v1",
        "annotation_batch_id": BATCH_ID,
        "phase": "construct_validity_adjudication",
        "inputs": input_metadata,
        "canonical_adjudication": {
            "ref": _artifact_ref(canonical_out),
            "sha256": sha256_file(canonical_out),
            "row_count": len(decisions),
            "status_counts": dict(sorted(
                Counter(row["adjudication_status"] for row in decisions).items()
            )),
            "adjudicated_field_counts": dict(sorted(axis_counts.items())),
        },
        "acceptance_gate": {
            "frozen_input_hashes_verified": True,
            "standalone_selfcheck_replayed": True,
            "all_rows_adjudicated": True,
            "unresolved_count": 0,
            "protocol_deviation_count": 0,
            "raw_returns_unchanged": True,
            "available_only_labels_unchanged": True,
            "final_analysis_release_allowed": True,
        },
    }


def _build_markdown(analysis: dict[str, Any]) -> str:
    primary = analysis["primary"]
    sens = analysis["sensitivity"]
    lines = [
        "# Repo480 Bidirectional Construct-Validity Analysis",
        "",
        "- **Status:** `canonical-pilot`",
        "- **Batch:** `repo480_construct_validity_v1`",
        "- **Generated by:** `scripts/analyze_repo480_construct_validity.py`",
        "",
        "## Primary results",
        "",
        "| Axis | Metric | Rate | Wilson 95% CI |",
        "| --- | --- | ---: | --- |",
    ]
    for key, axis, name in (
        ("p01_direction_match", "P0/P1", "predicted direction match"),
        ("p23_false_pessimism", "P2/P3", "hindsight uniqueness (false pessimism)"),
    ):
        rate = primary[key]
        ci = rate["wilson_95_ci"]
        lines.append(
            f"| {axis} | {name} | {rate['count']}/{rate['denominator']} = "
            f"{rate['proportion']:.3f} | `[{ci['lower']:.3f}, {ci['upper']:.3f}]` |"
        )
    lines += [
        "",
        "P0/P1 denominator는 frozen random-rank 120 prefix의 P0/P1 전 행이며 454행 census가 아니다.",
        "P2/P3 denominator는 같은 480-task frame의 P2/P3 전수다.",
        "",
        "## Sensitivity",
        "",
        "| Analysis | Rate | Wilson 95% CI |",
        "| --- | ---: | --- |",
    ]
    for key in SENSITIVITY_KEYS + ("p01_dispute_as_adverse",):
        rate = sens[key]
        ci = rate["wilson_95_ci"]
        lines.append(
            f"| `{key}` | {rate['count']}/{rate['denominator']} = "
            f"{rate['proportion']:.3f} | `[{ci['lower']:.3f}, {ci['upper']:.3f}]` |"
        )
    lines += ["", "## Raw reviewer intersection and union", "",
              "| Predicate | Intersection | Union |", "| --- | ---: | ---: |"]
    for name, value in analysis["sensitivity"]["raw_reviewer"].items():
        lines.append(
            f"| `{name}` | {value['intersection']['count']}/{value['n']} | "
            f"{value['union']['count']}/{value['n']} |"
        )
    provenance = analysis["decision_provenance"]
    strata = analysis["p01_label_strata_distributions"]
    lines += [
        "",
        "## P0/P1 direction-match distribution",
        "",
        "| Label | N | Match | Partial | Mismatch |",
        "| --- | ---: | ---: | ---: | ---: |",
        f"| P0 | {strata['P0']['n']} | {strata['P0']['match']} | "
        f"{strata['P0']['partial_match']} | {strata['P0']['mismatch']} |",
        f"| P1 | {strata['P1']['n']} | {strata['P1']['match']} | "
        f"{strata['P1']['partial_match']} | {strata['P1']['mismatch']} |",
        "",
        "## Decision provenance",
        "",
        f"- Exact three-reviewer consensus rows: {provenance['rows_exact_consensus']}",
        f"- Rows resolved by `repo480_cv_adj`: {provenance['rows_with_dispute']}",
        "",
        "## Claim boundary",
        "",
    ]
    lines += [f"- 보고하지 않음: {item}" for item in analysis["claim_scope"]["does_not_report"]]
    lines.append("")
    return "\n".join(lines)


def _build_bounds_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Repo480 Construct-Validity Determinacy Envelope",
        "",
        "- **Status:** `pre-adjudication`",
        "- **Batch:** `repo480_construct_validity_v1`",
        "- **Generated by:** `scripts/analyze_repo480_construct_validity.py --pre-adjudication`",
        "",
        f"`repo480_cv_adj` 반환 {report['pending_adjudication_rows']}행이 아직 pending이다. "
        "아래 envelope는 세 독립 반환만으로 이미 확정된 부분과, 남은 adjudication이 움직일 수 "
        "있는 최대 범위다. 열린 구간 안의 점추정치는 보고하지 않는다.",
        "",
        "| Metric | Closed | Adverse | Favourable |",
        "| --- | :---: | ---: | ---: |",
    ]
    for key, value in report["bounds"].items():
        mark = "yes" if value["closed"] else "no"
        lines.append(
            f"| `{key}` | {mark} | {value['lower_count']}/{value['denominator']} = "
            f"{value['lower']['proportion']:.3f} | {value['upper_count']}/"
            f"{value['denominator']} = {value['upper']['proportion']:.3f} |"
        )
    closed = report["closed_metrics"]
    lines += [
        "",
        "## Already closed by the three independent returns",
        "",
    ]
    for key in closed:
        value = report["bounds"][key]
        ci = value["lower"]["wilson_95_ci"]
        lines.append(
            f"- `{key}`: {value['lower_count']}/{value['denominator']} = "
            f"{value['lower']['proportion']:.3f}, Wilson 95% CI "
            f"`[{ci['lower']:.3f}, {ci['upper']:.3f}]` — 이 metric에는 dispute가 없으므로 "
            "adjudication 결과와 무관하게 값이 바뀌지 않는다."
        )
    separation = report["stratum_separation"]
    if separation["point_estimates_separated"]:
        lines += [
            "",
            "## Label strata ordering (adjudication-independent)",
            "",
            f"P0의 adverse bound {separation['adverse_p0']['count']}/"
            f"{separation['adverse_p0']['denominator']} = "
            f"{separation['adverse_p0']['proportion']:.3f}가 P1의 favourable bound "
            f"{separation['favourable_p1']['count']}/"
            f"{separation['favourable_p1']['denominator']} = "
            f"{separation['favourable_p1']['proportion']:.3f}보다 크다. 남은 adjudication이 "
            "어떻게 결정되든 P0의 direction-match rate가 P1보다 높다는 순서는 뒤집히지 않는다. "
            f"Worst-case 차이는 {separation['worst_case_difference']:.3f}이다.",
            "",
            "이는 **점추정 순서**에 대한 진술이며 두 stratum이 통계적으로 구분된다는 뜻이 "
            f"아니다. Worst-case Fisher exact p = "
            f"{separation['worst_case_fisher_exact_p']:.3f}이고 두 Wilson 구간은 "
            f"{'겹치지 않는다' if separation['wilson_intervals_disjoint'] else '겹친다'}. "
            "현재 표본(P0 65, P1 47)은 차이의 유의성을 지지하지 않는다.",
        ]
    lines += ["", "## Still open", ""]
    for key in report["open_metrics"]:
        value = report["bounds"][key]
        lines.append(
            f"- `{key}`: {value['undetermined']}행이 미확정이므로 "
            f"{value['lower_count']}--{value['upper_count']}/{value['denominator']} 사이다."
        )
    lines.append("")
    return "\n".join(lines)


def _build_tex(analysis: dict[str, Any]) -> str:
    primary = analysis["primary"]
    sens = analysis["sensitivity"]
    rows = [
        ("P0/P1 predicted direction match", primary["p01_direction_match"]),
        ("\\quad match or partial", sens["p01_match_or_partial"]),
        ("\\quad mismatch (false confidence)", sens["p01_false_confidence"]),
        ("\\quad dispute as adverse", sens["p01_dispute_as_adverse"]),
        ("\\quad Q0 only", sens["p01_direction_match_q0_only"]),
        ("P2/P3 hindsight uniqueness (false pessimism)", primary["p23_false_pessimism"]),
        ("\\quad oracle direction in candidate set", sens["p23_oracle_in_candidate_set"]),
        ("\\quad Q0 only", sens["p23_false_pessimism_q0_only"]),
    ]
    lines = [
        "% Generated by scripts/analyze_repo480_construct_validity.py; do not edit manually.",
        "\\begin{table}[t]",
        "\\caption{Bidirectional construct-validity audit of the available-only labels.}",
        "\\label{tab:repo480constructvalidity}",
        "\\centering",
        "\\small",
        "\\begin{tabular}{@{}p{0.50\\linewidth}p{0.13\\linewidth}p{0.28\\linewidth}@{}}",
        "\\hline",
        "Analysis & Count & Estimate / Wilson 95\\% CI \\\\",
        "\\hline",
    ]
    for name, rate in rows:
        ci = rate["wilson_95_ci"]
        lines.append(
            f"{name} & {rate['count']}/{rate['denominator']} & "
            f"{rate['proportion']:.3f} [{ci['lower']:.3f}, {ci['upper']:.3f}] \\\\"
        )
    strata = analysis["p01_label_strata_distributions"]
    lines += [
        "\\hline", "\\end{tabular}", "\\end{table}", "",
        "\\begin{table}[t]",
        "\\caption{P0/P1 direction-match outcomes in the frozen 112-row subset.}",
        "\\label{tab:repo480constructstrata}",
        "\\centering",
        "\\small",
        "\\begin{tabular}{@{}lrrrr@{}}",
        "\\hline",
        "Label & $n$ & Match & Partial & Mismatch \\\\",
        "\\hline",
        f"P0 & {strata['P0']['n']} & {strata['P0']['match']} & "
        f"{strata['P0']['partial_match']} & {strata['P0']['mismatch']} \\\\",
        f"P1 & {strata['P1']['n']} & {strata['P1']['match']} & "
        f"{strata['P1']['partial_match']} & {strata['P1']['mismatch']} \\\\",
        "\\hline",
        "\\end{tabular}",
        "\\end{table}",
        "",
    ]
    return "\n".join(lines)


def _preserve_exact(source: Path, target: Path) -> None:
    digest = sha256_file(source)
    if target.exists():
        if sha256_file(target) != digest:
            raise ValueError(f"refusing to overwrite mismatched canonical file {target}")
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, target)
    if sha256_file(target) != digest:
        raise ValueError(f"canonical preservation hash mismatch for {target}")


def _index(rows: list[dict[str, Any]], name: str) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
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
