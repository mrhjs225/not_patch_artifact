# SWE-bench Full Prevalence Real Repair-Agent Utility Replay

This report joins REAL public `swe-bench/experiments` agent outcomes with available-only
patchability signals and replays AlwaysPatch vs abstain-on-risky utility over a cost sweep.
Outcomes are real and harness-validated; cost regimes are swept, not asserted. See
`docs/decisions/README.md` for the claim boundary.

## Inputs

- Agent runs: `data/processed/policy_utility/swebench_full_prevalence_agent_runs.jsonl` (24 real SWE-bench full submissions)
- Sample split: `data/processed/dataset_splits/swebench_full_prevalence_random_120.json` (120 tasks)
- Judge signal: `results/pilot/swebench_full_prevalence_random_llm_judge_triage_predictions.jsonl` (available-only `gpt-5.5`)
- Reviewer signal: `data/annotations/raw_labels/swebench_full_prevalence_random_available_only_a01.jsonl` (`prev01` available-only)
- Capable-agent pool: runs resolving >= 8 of 120 (17 runs)

## Resolve rate by available-only label (real outcomes, capable pool)

| Signal | P0/P1 resolve | P2/P3 resolve | Ratio |
| --- | ---: | ---: | ---: |
| judge | 428/1819 (0.235) | 5/221 (0.023) | 10.4x |
| reviewer | 383/1615 (0.237) | 50/425 (0.118) | 2.0x |

- Judge label split of the 120 tasks: P0/P1=107, P2/P3=13.
- Reviewer label split: P0/P1=95, P2/P3=25.
- Underspecified (P2/P3) tasks resolve far less often, so abstaining on them avoids
  near-certain non-resolving submissions.

## Utility sweep (capable pool, V_correct=1)

Pooled utility delta of AbstainPolicy minus AlwaysPatch, summed over the capable pool.
Positive means abstaining on available-only P2/P3 tasks improves expected utility.

### Signal: judge

| C_abstain \ C_wrong | 0.25 | 0.5 | 1 | 2 | 5 |
| --- | ---: | ---: | ---: | ---: | ---: |
| 0 | +49.0 | +103.0 | +211.0 | +427.0 | +1075.0 |
| 0.1 | +26.9 | +80.9 | +188.9 | +404.9 | +1052.9 |
| 0.25 | -6.2 | +47.8 | +155.8 | +371.8 | +1019.8 |
| 0.5 | -61.5 | -7.5 | +100.5 | +316.5 | +964.5 |

- Break-even C_wrong at C_abstain=0.1: **0.125** (abstaining helps when wrong-patch cost exceeds 0.125 of a correct patch).

### Signal: reviewer

| C_abstain \ C_wrong | 0.25 | 0.5 | 1 | 2 | 5 |
| --- | ---: | ---: | ---: | ---: | ---: |
| 0 | +43.8 | +137.5 | +325.0 | +700.0 | +1825.0 |
| 0.1 | +1.2 | +95.0 | +282.5 | +657.5 | +1782.5 |
| 0.25 | -62.5 | +31.2 | +218.8 | +593.8 | +1718.8 |
| 0.5 | -168.8 | -75.0 | +112.5 | +487.5 | +1612.5 |

- Break-even C_wrong at C_abstain=0.1: **0.247** (abstaining helps when wrong-patch cost exceeds 0.247 of a correct patch).

## Per-agent utility delta (representative regime C_wrong=1, C_abstain=0.1)

| Agent run | resolved/120 | judge P0/P1 | judge P2/P3 | judge delta | reviewer delta |
| --- | ---: | ---: | ---: | ---: | ---: |
| `20251219_sonar-foundation-agent_claude-opus-4-5` | 58 | 56/107 | 2/13 | +7.70 | +8.50 |
| `20251027_salesforce_SAGE` | 49 | 47/107 | 2/13 | +7.70 | +10.50 |
| `20250522_amazon-q-developer-agent-20250405-dev` | 41 | 40/107 | 1/13 | +9.70 | +14.50 |
| `20250605_atlassian-rovo-dev` | 40 | 40/107 | 0/13 | +11.70 | +14.50 |
| `20241103_OpenHands-CodeAct-2.1-sonnet-20241022` | 32 | 32/107 | 0/13 | +11.70 | +14.50 |
| `20250227_sweagent-claude-3-7-20250219` | 31 | 31/107 | 0/13 | +11.70 | +14.50 |
| `20250131_amazon-q-developer-agent-20241202-dev` | 29 | 29/107 | 0/13 | +11.70 | +12.50 |
| `20241121_autocoderover-v2.0-claude-3-5-sonnet-20241022` | 27 | 27/107 | 0/13 | +11.70 | +16.50 |
| `20240820_honeycomb` | 20 | 20/107 | 0/13 | +11.70 | +18.50 |
| `20240620_sweagent_claude3.5sonnet` | 18 | 18/107 | 0/13 | +11.70 | +18.50 |
| `20240628_autocoderover-v20240620` | 18 | 18/107 | 0/13 | +11.70 | +20.50 |
| `20240721_amazon-q-developer-agent-20240719-dev` | 15 | 15/107 | 0/13 | +11.70 | +22.50 |
| `20240615_appmap-navie_gpt4o` | 14 | 14/107 | 0/13 | +11.70 | +14.50 |
| `20240617_factory_code_droid` | 12 | 12/107 | 0/13 | +11.70 | +20.50 |
| `20240728_sweagent_gpt4o` | 12 | 12/107 | 0/13 | +11.70 | +20.50 |
| `20240509_amazon-q-developer-agent-20240430-dev` | 9 | 9/107 | 0/13 | +11.70 | +22.50 |
| `20240402_sweagent_gpt4` | 8 | 8/107 | 0/13 | +11.70 | +18.50 |
| `20240402_sweagent_claude3opus` | 7 | 7/107 | 0/13 | +11.70 | +22.50 |
| `20240402_rag_claude3opus` | 3 | 3/107 | 0/13 | +11.70 | +22.50 |
| `20240402_rag_gpt4` | 2 | 2/107 | 0/13 | +11.70 | +22.50 |
| `20231010_rag_claude2` | 1 | 1/107 | 0/13 | +11.70 | +22.50 |
| `20231010_rag_swellama13b` | 1 | 1/107 | 0/13 | +11.70 | +22.50 |
| `20231010_rag_gpt35` | 0 | 0/107 | 0/13 | +11.70 | +22.50 |
| `20231010_rag_swellama7b` | 0 | 0/107 | 0/13 | +11.70 | +22.50 |

- Agents with positive judge-abstain delta at the representative regime: 24/24.

## Claim Boundary

- Resolve/non-resolve outcomes are real, harness-validated public agent results; the
  resolve-rate-by-label gap is a real measurement across many agents.
- Cost regimes are assumed and swept; deltas are reported as a function of cost with
  break-even, not as a single asserted improvement.
- The abstention signal is an available-only task-time proxy (judge or reviewer label),
  not a tuned detector and not post-hoc oracle.
- `Attempted = all tasks` (leaderboard convention); a non-resolved task is a non-success
  cost and does not separate wrong-patch from no-patch.
