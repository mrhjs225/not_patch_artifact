# Repo480 RQ1 Prevalence Recalculation

## Scope

This report estimates P2/P3 prevalence only for the frozen 480-task SWE-bench frame
under `swebench-repo480-v1`. The nested 120 rows are a reliability and row-audit
diagnostic, not a replacement estimate or an independent sample. RQ2 oracle masking
is not computed here.

## Frozen Adjudication-Rule Estimate (480 Tasks)

- Final labels: P0=269, P1=185, P2=22, P3=4.
- Adjudicated P2/P3: 26/480 = 0.054 (Wilson 95% CI [0.037, 0.078]).
- The Wilson interval quantifies row-level sampling uncertainty conditional on the
  frozen frame and annotation rule; it does not include reviewer or repository-policy
  uncertainty.
- Since the independent boundary-validation panel (RR-A), this frozen-rule estimate is
  one member of a rule-dependent sensitivity family, not the single preferred estimate.
  The independent-panel estimate is reported in
  `results/pilot/repo480_boundary_validation_analysis_v1.md`.

## Raw Reviewer Reliability

| Frame | Axis | Agreement | Cohen's kappa | Direction of binary disagreement |
| --- | --- | ---: | ---: | --- |
| 480 | P0--P3 | 342/480 (0.713) | 0.506 | --- |
| 480 | P0/P1 vs P2/P3 | 430/480 (0.896) | 0.403 | R1 safe/R2 unsafe=48; R1 unsafe/R2 safe=2 |
| nested 120 | P0--P3 | 85/120 (0.708) | 0.508 | --- |
| nested 120 | P0/P1 vs P2/P3 | 108/120 (0.900) | 0.459 | R1 safe/R2 unsafe=12; R1 unsafe/R2 safe=0 |

High observed binary agreement coexists with a directional marginal difference between
the two raw passes. Therefore, kappa and reviewer-rule sensitivity are reported rather
than treating agreement alone as prevalence stability.

## Reviewer-Rule Sensitivity

| Rule | 480 count/N (Wilson 95% CI) | Nested 120 count/N (Wilson 95% CI) |
| --- | ---: | ---: |
| Raw reviewer 1 | 22/480 = 0.046 (Wilson 95% CI [0.030, 0.068]) | 6/120 = 0.050 (Wilson 95% CI [0.023, 0.105]) |
| Raw reviewer 2 | 68/480 = 0.142 (Wilson 95% CI [0.113, 0.176]) | 18/120 = 0.150 (Wilson 95% CI [0.097, 0.225]) |
| Both raw reviewers (intersection) | 20/480 = 0.042 (Wilson 95% CI [0.027, 0.063]) | 6/120 = 0.050 (Wilson 95% CI [0.023, 0.105]) |
| Either raw reviewer (union) | 70/480 = 0.146 (Wilson 95% CI [0.117, 0.180]) | 18/120 = 0.150 (Wilson 95% CI [0.097, 0.225]) |
| Two of raw/raw/adjudicated | 26/480 = 0.054 (Wilson 95% CI [0.037, 0.078]) | 8/120 = 0.067 (Wilson 95% CI [0.034, 0.126]) |
| Adjudicated (frozen rule) | 26/480 = 0.054 (Wilson 95% CI [0.037, 0.078]) | 8/120 = 0.067 (Wilson 95% CI [0.034, 0.126]) |

The two-of-three row is descriptive because adjudication is derived from the raw
passes; it is not a third independent vote. The wide raw intersection--union range
is annotation-rule uncertainty and must not be presented as a confidence interval.

## Nested 120 Deep-Audit View

- Final labels: P0=65, P1=47, P2=8, P3=0.
- Repository-packet P2/P3 rows: 8/120 = 0.067 (Wilson 95% CI [0.034, 0.126]).
- Issue-packet baseline on the same rows: 20/120 = 0.167 (Wilson 95% CI [0.111, 0.243]).
- All repository-packet P2/P3 rows in this subset appear in the generated supplement
  table and the 480-row JSONL audit.
- Prior issue-packet external panels are not recast as reliability evidence for the
  new repository-packet labels.

## Evidence-Policy Sensitivity

- Issue-packet baseline: 57/480 = 0.119 (Wilson 95% CI [0.093, 0.151]).
- Repository packet, frozen adjudicated rule: 26/480 = 0.054 (Wilson 95% CI [0.037, 0.078]).
- Paired difference (repository minus issue packet): -6.458 percentage points (row bootstrap 95% CI [-9.167, -3.750]).
- Binary transitions: P0/P1_to_P0/P1=416, P0/P1_to_P2/P3=7, P2/P3_to_P0/P1=38, P2/P3_to_P2/P3=19.
- This is paired descriptive sensitivity, not a causal repository-evidence effect,
  because packet contents and reviewer/adjudication procedures changed together.

## Repository-Cluster Sensitivity

- Repositories: 12.
- Row-level frozen-rule estimate: 26/480 = 0.054 (Wilson 95% CI [0.037, 0.078]).
- Equal-repository-weighted mean: 0.044.
- Repository-cluster bootstrap 95% interval: [0.031, 0.087].
- Leave-one-repository-out row-rate range: [0.042, 0.069] (minimum excludes `sympy/sympy`; maximum excludes `django/django`).

| Repository | Tasks | P2/P3 | Rate |
| --- | ---: | ---: | ---: |
| `django/django` | 160 | 4 | 0.025 |
| `sympy/sympy` | 77 | 9 | 0.117 |
| `sphinx-doc/sphinx` | 49 | 2 | 0.041 |
| `scikit-learn/scikit-learn` | 46 | 4 | 0.087 |
| `matplotlib/matplotlib` | 44 | 2 | 0.045 |
| `pytest-dev/pytest` | 34 | 3 | 0.088 |
| `pydata/xarray` | 23 | 0 | 0.000 |
| `astropy/astropy` | 17 | 1 | 0.059 |
| `pylint-dev/pylint` | 15 | 1 | 0.067 |
| `psf/requests` | 7 | 0 | 0.000 |
| `mwaskom/seaborn` | 6 | 0 | 0.000 |
| `pallets/flask` | 2 | 0 | 0.000 |

Repository weighting and cluster resampling are within-sample concentration checks.
They do not redefine the row-sampled 480-task benchmark-frame estimand.

## Claim Boundary

- Report 26/480 and its Wilson interval as the frozen adjudication-rule member of the
  RQ1 rule-sensitivity family, beside the independent-panel estimate; do not present
  it as the single preferred estimate.
- Report nested 120 reliability and row audit separately from the 480 estimate.
- Report reviewer-rule and evidence-policy sensitivities as distinct uncertainty
  families, not as one heterogeneous envelope.
- Do not infer broad APR prevalence, a causal evidence effect, a validated automatic
  patch gate, or an RQ2 masking result from this artifact.
