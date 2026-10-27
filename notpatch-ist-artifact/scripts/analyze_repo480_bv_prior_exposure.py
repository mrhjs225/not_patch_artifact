#!/usr/bin/env python3
"""Sensitivity of the RR-A boundary estimate to its panel's earlier construct-validity exposure.

Owner staffing (2026-10-27, docs/annotator_registry.md) assigns the three RR-A roles to the same
experts as the construct-validity raw roles, which had already shown them the oracle patch/tests and
the locked frozen label for every audited row. This script only re-reads frozen result rows.
"""

from __future__ import annotations

import argparse
import collections
import json
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for path in (ROOT, ROOT / "src"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from notpatch.canonical import sha256_file  # noqa: E402
from scripts.analyze_repo480_boundary_validation import _agreement, _stratified  # noqa: E402

FROZEN_POINT = 26 / 480
CLAIM_BOUNDARY = [
    "Exposure is inferred from staffing and row membership; no RR-A raw row recorded a protocol_deviation, so row-level recall is unknown.",
    "The reverted estimate assigns every exposed row its frozen label: it removes any exposure-driven disagreement but also any genuine one, so it is a sensitivity, not a corrected estimate.",
    "The exposure split is not randomized; exposed rows include every frozen P2/P3 row, so agreement differences mix exposure with row difficulty.",
    "Frozen labels, 26/480 and the primary 0.094 estimate are unchanged.",
]


def _jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def analyze(args: argparse.Namespace) -> dict:
    date.fromisoformat(args.analyzed_on)
    paths = {
        "validation_rows": args.validation_rows,
        "validation_analysis": args.validation_analysis,
        "construct_rows": args.construct_rows,
        "discordance_rows": args.discordance_rows,
        "validation_raw_r1": args.raw_r1,
        "validation_raw_r2": args.raw_r2,
    }
    rows = _jsonl(ROOT / args.validation_rows)
    construct = {row["task_id"]: row for row in _jsonl(ROOT / args.construct_rows)}
    discordant = {row["task_id"] for row in _jsonl(ROOT / args.discordance_rows)}
    raw = _jsonl(ROOT / args.raw_r1) + _jsonl(ROOT / args.raw_r2)
    frozen_analysis = json.loads((ROOT / args.validation_analysis).read_text())

    primary = _stratified(rows, "independent_binary_label")
    if primary != {k: v for k, v in frozen_analysis["independent_stratified_prevalence"].items()
                   if k in primary}:
        raise ValueError("primary estimate does not reproduce the frozen RR-A analysis")
    exposed = [row for row in rows if row["task_id"] in construct]
    unexposed = [row for row in rows if row["task_id"] not in construct]
    reverted = _stratified(
        [{**row, "reverted": row["frozen_binary_label"] if row["task_id"] in construct
          else row["independent_binary_label"]} for row in rows],
        "reverted",
    )

    # Validation boundary on exposed rows, split by what the earlier audit showed.
    by_audit = collections.defaultdict(lambda: {"n": 0, "validation_p2p3": 0})
    for row in exposed:
        fields = construct[row["task_id"]]["final_controlled_fields"]
        key = (f"frozen_p01|direction_{fields['predicted_direction_match']}"
               if row["frozen_binary_label"] == "P0/P1"
               else f"frozen_p23|oracle_in_candidates_{fields['oracle_direction_in_candidate_set']}")
        by_audit[key]["n"] += 1
        by_audit[key]["validation_p2p3"] += row["independent_binary_label"] == "P2/P3"

    return {
        "schema_version": "repo480-bv-prior-exposure-v1",
        "analyzed_on": args.analyzed_on,
        "staffing": {
            "source": "owner staffing report 2026-10-27 recorded in docs/annotator_registry.md",
            "validation_roles": ["repo480_bv_r1", "repo480_bv_r2", "repo480_bv_adj"],
            "construct_raw_roles": ["repo480_cv_r1", "repo480_cv_r2", "repo480_cv_r3"],
            "relation": "same three experts; construct-validity raw returns preceded the RR-A package (2026-08-18)",
        },
        "inputs": {name: {"ref": str(path), "sha256": sha256_file(ROOT / path)}
                   for name, path in paths.items()},
        "exposed_rows": {
            "count": len(exposed),
            "denominator": len(rows),
            "by_stratum": dict(collections.Counter(row["stratum"] for row in exposed)),
            "by_frozen_binary": dict(collections.Counter(row["frozen_binary_label"] for row in exposed)),
        },
        "raw_rows_with_protocol_deviation": sum(row["protocol_deviation"] is not None for row in raw),
        "agreement_with_frozen": {"exposed": _agreement(exposed), "unexposed": _agreement(unexposed)},
        "primary_estimate": primary,
        "exposed_rows_reverted_to_frozen": {
            **reverted,
            "covers_frozen_26_of_480": reverted["interval_95"]["lower"] <= FROZEN_POINT
            <= reverted["interval_95"]["upper"],
        },
        "exposed_validation_boundary_by_audit_result": dict(sorted(by_audit.items())),
        "rre_set_b_exposed": {"count": len(discordant & set(construct)), "denominator": len(discordant)},
        "claim_boundary": CLAIM_BOUNDARY,
    }


def markdown(result: dict) -> str:
    agree = result["agreement_with_frozen"]
    rev = result["exposed_rows_reverted_to_frozen"]
    prim = result["primary_estimate"]
    exp = result["exposed_rows"]
    lines = [
        "# RR-A Prior-Exposure Sensitivity",
        "",
        f"- Generated by `scripts/analyze_repo480_bv_prior_exposure.py` on {result['analyzed_on']}.",
        "- Staffing source: owner report of 2026-10-27 (`docs/annotator_registry.md`). The three RR-A roles",
        "  are the same experts as the three construct-validity raw roles, whose packages showed the oracle",
        "  patch/tests and the locked frozen label or candidate set for every audited row.",
        "",
        "## Observation",
        "",
        f"- Exposed rows: {exp['count']}/{exp['denominator']} "
        f"(strata {exp['by_stratum']}; frozen boundary {exp['by_frozen_binary']}).",
        f"- RR-A raw rows recording a `protocol_deviation`: {result['raw_rows_with_protocol_deviation']}/440.",
        f"- Binary agreement with the frozen boundary: exposed {agree['exposed']['agreement_count']}/"
        f"{agree['exposed']['n']}, unexposed {agree['unexposed']['agreement_count']}/{agree['unexposed']['n']}.",
        f"- Primary estimate (reproduced): {prim['proportion']:.3f} "
        f"[{prim['interval_95']['lower']:.3f}, {prim['interval_95']['upper']:.3f}].",
        f"- Exposed rows reverted to frozen labels: {rev['proportion']:.3f} "
        f"[{rev['interval_95']['lower']:.3f}, {rev['interval_95']['upper']:.3f}]; "
        f"{'covers' if rev['covers_frozen_26_of_480'] else 'still excludes'} 26/480 = 0.054.",
        f"- RR-E Set B rows among exposed rows: {result['rre_set_b_exposed']['count']}/"
        f"{result['rre_set_b_exposed']['denominator']}.",
        "",
        "Validation P2/P3 calls on exposed rows by the earlier audit result:",
        "",
        "| Frozen boundary and audit result | Rows | Validation P2/P3 |",
        "| --- | ---: | ---: |",
    ]
    cells = result["exposed_validation_boundary_by_audit_result"]
    for key, cell in cells.items():
        lines.append(f"| `{key}` | {cell['n']} | {cell['validation_p2p3']} |")
    match = cells["frozen_p01|direction_match"]
    other = [cells[k] for k in ("frozen_p01|direction_partial_match", "frozen_p01|direction_mismatch")]
    lines += [
        "",
        "## Interpretation",
        "",
        "The prespecified RR-A decision (0.054 lies outside the validation interval) does not depend on the",
        "exposed rows. Among exposed frozen-P0/P1 rows, the validation panel gave P2/P3 more often where the",
        f"audit had judged the locked direction partial or mismatch ({sum(c['validation_p2p3'] for c in other)}/"
        f"{sum(c['n'] for c in other)}) than where it matched ({match['validation_p2p3']}/{match['n']}).",
        "This is consistent with exposure influence and with genuine ambiguity; the data cannot separate the two.",
        "",
        "## Claim boundary",
        "",
        *[f"- {item}" for item in result["claim_boundary"]],
        "",
    ]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--validation-rows", type=Path,
                        default=Path("results/pilot/repo480_boundary_validation_analysis_rows_v1.jsonl"))
    parser.add_argument("--validation-analysis", type=Path,
                        default=Path("results/pilot/repo480_boundary_validation_analysis_v1.json"))
    parser.add_argument("--construct-rows", type=Path,
                        default=Path("results/pilot/repo480_construct_validity_rows_v1.jsonl"))
    parser.add_argument("--discordance-rows", type=Path,
                        default=Path("results/pilot/repo480_boundary_discordance_typology_rows_v1.jsonl"))
    panel = "data/annotations/oracle_gap/repo480_boundary_validation_panel"
    parser.add_argument("--raw-r1", type=Path, default=Path(f"{panel}/repo480_boundary_validation_r1.jsonl"))
    parser.add_argument("--raw-r2", type=Path, default=Path(f"{panel}/repo480_boundary_validation_r2.jsonl"))
    parser.add_argument("--analyzed-on", default="2026-10-27")
    parser.add_argument("--out-json", type=Path,
                        default=Path("results/pilot/repo480_bv_prior_exposure_sensitivity_v1.json"))
    parser.add_argument("--out-md", type=Path,
                        default=Path("results/pilot/repo480_bv_prior_exposure_sensitivity_v1.md"))
    args = parser.parse_args()
    result = analyze(args)
    (ROOT / args.out_json).write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    (ROOT / args.out_md).write_text(markdown(result))
    rev = result["exposed_rows_reverted_to_frozen"]
    print(f"exposed {result['exposed_rows']['count']}/220; reverted {rev['proportion']:.6f} "
          f"[{rev['interval_95']['lower']:.6f}, {rev['interval_95']['upper']:.6f}]")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
