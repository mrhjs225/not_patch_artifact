# Leakage-Resistant Detector Audit

This report addresses the detector memorization concern by comparing original judge runs,
identifier-redacted judge reruns, and transparent non-LLM feature baselines on the same
120-row SWE-bench full prevalence denominator.

## Inputs

- Adjudicated labels: `data/annotations/adjudicated/swebench_full_prevalence_random_adjudicated.jsonl`
- Evidence bundles: `data/processed/evidence_bundles/swebench_full_prevalence_random.jsonl`
- Tasks: 120
- Patch-decidable P0/P1: 100/120 (0.833)
- Should-clarify/abstain P2/P3/P4: 20/120
- Distinct repositories in local evaluation metadata: 11

## Detector Comparison

| Detector | Kind | AUROC [95% CI] | perm. p | AUPRC | Coverage | False-safe | Brier |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `gpt-5.5 original` | LLM judge | 0.882 [0.794, 0.950] | 0.000 | 0.975 | 0.892 | 0.500 | 0.087 |
| `gpt-5.5 anonymized` | LLM judge | 0.881 [0.780, 0.956] | 0.000 | 0.972 | 0.858 | 0.450 | 0.089 |
| `claude-opus-4-8 original` | LLM judge | 0.855 [0.771, 0.931] | 0.000 | 0.970 | 0.775 | 0.350 | 0.123 |
| `claude-opus-4-8 anonymized` | LLM judge | 0.853 [0.751, 0.941] | 0.000 | 0.968 | 0.733 | 0.200 | 0.123 |
| `feature::manual_issue_quality` | non-LLM feature baseline | 0.511 [0.341, 0.677] | 0.885 | 0.817 | 0.308 | 0.300 | 0.369 |
| `feature::logo_logistic` | non-LLM feature baseline | 0.350 [0.211, 0.494] | 0.037 | 0.763 | 0.975 | 1.000 | 0.168 |

## Sources

- `gpt-5.5 original`: results/pilot/swebench_full_prevalence_random_llm_judge_triage_predictions.jsonl
- `gpt-5.5 anonymized`: results/pilot/swebench_full_prevalence_random_llm_judge_triage_predictions_gpt-5.5_anon.jsonl
- `claude-opus-4-8 original`: results/pilot/swebench_full_prevalence_random_llm_judge_triage_predictions_claude.jsonl
- `claude-opus-4-8 anonymized`: results/pilot/swebench_full_prevalence_random_llm_judge_triage_predictions_claude_anon.jsonl
- `feature::manual_issue_quality`: deterministic issue-quality heuristic over identifier-free counts/markers
- `feature::logo_logistic`: leave-one-repository-out logistic regression over transparent non-LLM features

## Reading

- The anonymized judge rows remove direct task/repository/source URL/hash cues from the model-visible prompt.
- The non-LLM baselines use only transparent counts and lexical markers from available evidence; they do not use repository names, task ids, URLs as text, oracle patches, or public submission outcomes.
- A residual leakage risk remains because API names, class names, and error text can still reveal project context; this audit supports a leakage-resistant ranking claim, not a decontamination guarantee.
- Default binary decisions remain unsafe as automatic gates when false-safe is high; AUROC is reported as ranking evidence only.
