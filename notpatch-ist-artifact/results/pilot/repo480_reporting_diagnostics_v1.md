# Repo480 Reporting Diagnostics

- **Status:** `canonical`
- **Authority:** paper-facing sampling, reliability, retrieval, and Verified diagnostics
- **Packet policy:** `swebench-repo480-v1`

## Sampling flow

| Stage | Count |
| --- | ---: |
| SWE-bench test rows | 2294 |
| Prior labeled ids excluded | 69 |
| Sampling frame | 2225 |
| Seeded candidate draw | 600 |
| Structurally excluded within draw | 0 |
| Selected random ranks 1--480 | 480 |
| Unused eligible reserve | 120 |

All 600 draw rows were eligible. The final 480 are ranks 1--480; the remaining 120 are unused reserve rows, not attrition.

## Raw reliability before adjudication

| Unit | Agreement | Cohen kappa | PABAK / weighted kappa | Gwet AC1 |
| --- | ---: | ---: | ---: | ---: |
| Binary P0/P1 vs P2/P3 | 430/480 (0.896) | 0.403 | PABAK 0.792 | 0.875 |
| Exact P0--P3 | 342/480 (0.713) | 0.506 | linear 0.554; quadratic 0.618 | 0.644 |
| Primary blocker, at least one recorded | 124/277 (0.448) | n/a | n/a | n/a |

Of 50 binary disagreements, adjudication assigns 44 to P0/P1 and 6 to P2/P3. Together with 20 raw-consensus P2/P3 rows, this yields 26/480.

## Paper-facing sensitivity checks

| Diagnostic group | P2/P3 | Estimate / Wilson 95% CI |
| --- | ---: | ---: |
| Retrieval sufficient | 19/380 | 0.050 [0.032, 0.077] |
| Retrieval insufficient or unclear | 7/100 | 0.070 [0.034, 0.137] |
| SWE-bench Verified member | 0/97 | 0.000 [0.000, 0.038] |
| Outside SWE-bench Verified | 26/383 | 0.068 [0.047, 0.098] |

The data-quality axis fires on 3/480 rows (Q0 477; Q2 3).
The repository-cluster bootstrap uses 10000 resamples with seed 20260720 and gives [0.031, 0.087].

## Interpretation guardrails

- PABAK and Gwet AC1 quantify the low-prevalence effect on kappa; they do not erase the directional reviewer-threshold difference.
- Zero P2/P3 among Verified members shows overlap with Verified curation, while 357/383 non-Verified rows remain P0/P1 under NotPatch, so the constructs are not equivalent.
- Retrieval stratification changes the point estimate only slightly, but does not substitute for an unbudgeted review of the seven flagged numerator rows.
