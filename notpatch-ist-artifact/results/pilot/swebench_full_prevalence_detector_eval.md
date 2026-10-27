# Detector on the Prevalence Denominator (pipeline unification)

Closes prevalence -> detector on a single denominator: the available-only `gpt-5.5` judge is
evaluated as a patch-authorization detector on the SAME 120-row SWE-bench prevalence sample used
for prevalence (H2) and real-outcome utility (H4), against two-reviewer adjudicated labels.

- Tasks: 120; patch-decidable (P0/P1) 100, should-abstain (P2/P3) 20 (target patch-decidable rate 0.833).
- Positive class = patch-decidable. `false_safe` = predict patch on an actual P2/P3 task.
- Detector = cached available-only `gpt-5.5` judge (zero-shot; never trained on these labels).

## Default binary decision (judge's own patch/clarify call)

| Metric | Value | 95% bootstrap CI |
| --- | ---: | --- |
| Coverage (fraction authorized to patch) | 0.892 | [0.833, 0.942] |
| False-safe rate (patch on a should-abstain task) | 0.500 | [0.263, 0.714] |
| Recall (decidable tasks correctly authorized) | 0.970 | [0.932, 1.000] |
| Precision | 0.907 | n/a |
| Accuracy | 0.892 | n/a |

## Ranking quality

- AUROC: 0.882 (95% bootstrap CI [0.794, 0.950]; permutation p = 0.000 vs.\ chance 0.5).
- AUPRC: 0.975 (positive base rate 0.833).
- Brier: 0.087.

## Risk--coverage (post-hoc operating points on this denominator)

| Coverage budget | tasks authorized | false-safe rate |
| ---: | ---: | ---: |
| 0.10 | 12 | 0.000 |
| 0.20 | 24 | 0.000 |
| 0.30 | 36 | 0.000 |
| 0.40 | 48 | 0.050 |
| 0.50 | 60 | 0.050 |

| False-safe budget | min coverage meeting it | achieved false-safe |
| ---: | ---: | ---: |
| 0.00 | 0.392 | 0.000 |
| 0.05 | 0.500 | 0.050 |
| 0.10 | 0.658 | 0.100 |
| 0.20 | 0.692 | 0.200 |

## Reading and claim boundary

- Pipeline: prevalence (this denominator), detector (this report), and utility (H4) now share
  the 120-row sample, so the abstention argument can be read end-to-end on one denominator.
- On its default binary call the judge authorizes patches on 0.89 of tasks with a
  false-safe rate of 0.500: it still patches many should-abstain tasks, so it
  is not a safe automatic gate, consistent with the separate v6 pool result.
- Ranking is informative (AUROC above) and a conservative score threshold can cut false-safe at
  the cost of coverage, but those operating points are post-hoc, not preregistered.
- The repository-evidence static detector cannot be evaluated on this denominator: the prevalence
  sample carries issue-level available evidence only, not the repo-evidence features that detector
  consumes. The available-only judge is the detector that the unified denominator supports.
