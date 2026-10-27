# Repository-480 Agreement, Adjudication, and Transition Analysis

- **Status:** `canonical-pilot`
- **Analysis ID:** `repo480-available-v1-transition`
- **Packet policy:** `swebench-repo480-v1`
- **Rows:** 480

이 보고서는 같은 480-task frame에서 두 available-only raw pass의 재현성, stable third-reviewer adjudication의 구성, issue-packet seed label에서 repository-evidence final label로의 전이를 고정한다. Raw rationale나 disagreement 전문은 포함하지 않으며 task-level 추적은 별도 row supplement가 담당한다.

## Integrity and inputs

- Task set: 480 unique tasks across r1, r2, seed, and final (`task_sets_identical=true`).
- Final construction: 466 decisions + 14 exact-consensus rows = 480 final rows.
- Decision task set equals the recomputed raw-disagreement task set, and every final scientific field matches its selected base plus explicit overrides (or r1 for exact consensus).

| Input | Rows | SHA-256 |
| --- | ---: | --- |
| `data/annotations/raw_labels/repo480_available_v1_r1.jsonl` | 480 | `5318d907093d44ee6eeeb7938c68373a8430bbb7a9e6e488a68a6685592e5a34` |
| `data/annotations/raw_labels/repo480_available_v1_r2.jsonl` | 480 | `cfd7daaf1f1256d6827e60eba78837cf21ff8d51e52aacb2b1e82ec319aca390` |
| `data/annotations/adjudication_decisions/repo480_available_v1.jsonl` | 466 | `44b0742ead4eded1d4a0ca88c48211752f16fbd2c0ac43f616c78bb7b95a2472` |
| `data/annotations/adjudicated/repo480_available_v1.jsonl` | 480 | `98b33aabbd10b34bd093c4590c2f6c42476f999dd0e60e64794dbb0544f4e63d` |
| `data/annotations/adjudicated/swebench_full_prevalence_random_480_adjudicated.jsonl` | 480 | `3c745afa68d4b283ddc64f0dd09a1da2b0d4e2e994fca8cb154634cf6165f23f` |

## Raw r1-r2 agreement

Agreement and Cohen's kappa are computed over all 480 paired raw records. Primary-blocker agreement treats the P0 null blocker as one category, matching the existing agreement summarizer's exact-value calculation.

| Axis | Agree | Observed agreement | Cohen's kappa |
| --- | ---: | ---: | ---: |
| P0--P3 primary label | 342/480 | 0.713 | 0.506 |
| P0/P1 vs P2/P3 | 430/480 | 0.896 | 0.403 |
| Primary blocker | 327/480 | 0.681 | 0.497 |
| Data quality | 444/480 | 0.925 | 0.133 |

### P0--P3 matrix

Rows: `r1`; columns: `r2`.

| | `P0` | `P1` | `P2` | `P3` | Row total |
| --- | ---: | ---: | ---: | ---: | ---: |
| `P0` | 203 | 74 | 5 | 2 | 284 |
| `P1` | 11 | 122 | 35 | 6 | 174 |
| `P2` | 0 | 2 | 15 | 3 | 20 |
| `P3` | 0 | 0 | 0 | 2 | 2 |
| Column total | 214 | 198 | 55 | 13 | 480 |

### Binary matrix

Rows: `r1`; columns: `r2`.

| | `P0/P1` | `P2/P3` | Row total |
| --- | ---: | ---: | ---: |
| `P0/P1` | 410 | 48 | 458 |
| `P2/P3` | 2 | 20 | 22 |
| Column total | 412 | 68 | 480 |

## Raw disagreement and adjudication

| Raw pair category | Tasks |
| --- | ---: |
| `binary_boundary` | 50 |
| `within_binary_primary_label` | 88 |
| `multi_axis` | 51 |
| `blocker_only` | 1 |
| `direction_wording_only` | 274 |
| `data_quality_only` | 2 |
| `exact_consensus` | 14 |

The 466 non-consensus rows received explicit decisions; the remaining 14 rows use the exact-consensus default r1 record. Base selection was r1 for 107 decisions and r2 for 359. 48 decisions contain at least one override, including 12 primary-label overrides.

| Category | Decisions | Base r1 | Base r2 | Equivalent | Partial | Different | Not assessable | N/A |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `binary_boundary` | 50 | 42 | 8 | 0 | 50 | 0 | 0 | 0 |
| `within_binary_primary_label` | 88 | 49 | 39 | 77 | 8 | 0 | 0 | 3 |
| `multi_axis` | 51 | 9 | 42 | 46 | 5 | 0 | 0 | 0 |
| `blocker_only` | 1 | 0 | 1 | 0 | 0 | 0 | 0 | 1 |
| `direction_wording_only` | 274 | 6 | 268 | 265 | 8 | 1 | 0 | 0 |
| `data_quality_only` | 2 | 1 | 1 | 0 | 0 | 0 | 0 | 2 |

Direction equivalence describes whether the raw predicted-direction wording points to the same repair direction on rows where that axis was compared. It is not another P0--P3 agreement statistic; `not_applicable` is required where direction wording was not a disagreement axis.

## Issue-packet seed to repository-evidence final transition

### P0--P3 matrix

Rows: `seed`; columns: `final`.

| | `P0` | `P1` | `P2` | `P3` | Row total |
| --- | ---: | ---: | ---: | ---: | ---: |
| `P0` | 133 | 33 | 0 | 1 | 167 |
| `P1` | 131 | 119 | 5 | 1 | 256 |
| `P2` | 4 | 29 | 17 | 1 | 51 |
| `P3` | 1 | 4 | 0 | 1 | 6 |
| Column total | 269 | 185 | 22 | 4 | 480 |

### Binary matrix

Rows: `seed`; columns: `final`.

| | `P0/P1` | `P2/P3` | Row total |
| --- | ---: | ---: | ---: |
| `P0/P1` | 416 | 7 | 423 |
| `P2/P3` | 38 | 19 | 57 |
| Column total | 454 | 26 | 480 |

| Transition summary | Tasks |
| --- | ---: |
| Unchanged primary label | 270 |
| Changed within the same binary side | 165 |
| P2/P3 seed to P0/P1 final | 38 |
| P0/P1 seed to P2/P3 final | 7 |
| Any P0--P3 label change | 210 |
| Any binary-boundary change | 45 |

## Interpretation boundary

- 이 artifact는 evidence-policy transition과 annotation/adjudication reproducibility를 기술한다. P0-4의 repository-level prevalence estimate, confidence interval, nested-120 audit 또는 sensitivity result를 대신하지 않는다.
- Seed는 issue title/body에 기반한 pre-revision baseline이고 final은 frozen repository retrieval packet과 새 reviewer procedure에 기반한다. 따라서 전이는 evidence policy, reviewer 구성, adjudication procedure가 함께 달라진 관찰값이며 repository evidence만의 causal effect로 해석할 수 없다.
- 이 단계에서는 benchmark solvability나 post-hoc oracle를 결합하지 않았으므로 RQ2 masking numerator/denominator를 제시하지 않는다.
- Row supplement는 label, disagreement, transition, base-selection flag만 포함하며 raw rationale와 disagreement 전문은 복사하지 않는다.
