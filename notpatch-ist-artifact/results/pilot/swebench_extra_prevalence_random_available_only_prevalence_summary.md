# SWE-bench Full Prevalence Random Label Summary

This report summarizes the filled SWE-bench full/unfiltered row-level random sample.
It is a raw available-only annotation summary, not an oracle-corrected prevalence result.

## Inputs

- Labels: `data/annotations/raw_labels/swebench_extra_prevalence_random_available_only_r01.jsonl`
- Split: `data/processed/dataset_splits/swebench_extra_prevalence_random_120.json`
- Bootstrap seed: `20260617`
- Bootstrap samples: `10000`

## Sample

- Labeled eligible rows: 120
- Annotators: `codex_prevalence_reviewer`=120
- Adjudication status: `raw`=120
- Primary labels: `P0`=39, `P1`=49, `P2`=23, `P3`=9
- Data quality: `Q0`=120
- Task difficulty: `low`=17, `medium`=103
- Source rows: 6376
- Prior excluded task ids: 0
- Sampling frame rows: 6376
- Candidate draw rows: 150
- Structural exclusions in draw: 0
- Selected eligible rows: 120
- Selection rule: `prevalence_random_first_eligible`
- Split status: `PASS`

## Rates

| Metric | Definition | Count/N | Point | 95% bootstrap CI | Note |
| --- | --- | ---: | ---: | ---: | --- |
| Pure P2/P3 rate | `primary_label in {P2, P3}` | 32/120 | 0.267 | [0.192, 0.350] | Primary H1a prevalence hook; raw available-only estimate. |
| Patch-unsafe rate | `P2/P3 or data_quality == Q1` | 32/120 | 0.267 | [0.192, 0.350] | Separates decidability risk plus benchmark-invalid labels. |
| Q1/D1 rate | `data_quality == Q1` | 0/120 | 0.000 | [0.000, 0.000] | Benchmark-invalid/data-quality axis, not P2/P3 prevalence. |

## P2/P3 Blocker Counts

These are single-reviewer descriptive counts for the P2/P3 rows only. Do not use them as stable U-label prevalence without adjudication.

| Blocker | Count |
| --- | ---: |
| `U1` | 6 |
| `U2` | 17 |
| `U3` | 1 |
| `U5` | 3 |
| `U6` | 4 |
| `U7` | 1 |

## All-Label Blocker Counts

| Blocker | Count |
| --- | ---: |
| `U1` | 6 |
| `U2` | 18 |
| `U3` | 4 |
| `U5` | 35 |
| `U6` | 9 |
| `U7` | 9 |
| `none` | 39 |

## Interpretation Guardrails

- Raw P2/P3 point estimate is 0.267; preregistered theta_P is 0.150.
- Raw point estimate meets the theta_P point threshold. If this batch is used as the primary prevalence pass, Path B support also needs oracle-gap false-pessimism correction; if this batch is a relabel, use the corresponding comparison/adjudication report for claim wording.
- P2/P3 count is 32, so the next oracle-gap correction mode is: audit all available-only P2/P3 rows.
- Labels are single-reviewer raw available-only labels unless a later adjudication artifact says otherwise.
- External reliability or corroboration language depends on the relevant relabel/comparison report.
- Q1/D1 remains a separate data-quality axis; it is not mixed into pure P2/P3 prevalence.
