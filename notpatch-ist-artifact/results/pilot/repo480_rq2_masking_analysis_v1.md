# Repo480 RQ2 Oracle-Masking Analysis

- **Status:** `canonical-pilot`
- **Batch:** `repo480_rq2_masking_v1`
- **Denominator:** 12 benchmark-solved repository-packet P2/P3 tasks

## Primary result

Strict oracle masking은 **12/12 = 1.000**이며 Wilson 95% CI는 `[0.758, 1.000]`이다. Strict call은 reviewer가 직접 입력하지 않고 `oracle_alternative_fix_exists=yes` AND `available_evidence_unique_in_hindsight=no`에서 유도했다.

이 결과의 분모는 480개 전체나 repository P2/P3 26개 전체가 아니다. Frozen public full-test run에서 benchmark-solved가 관찰된 repository P2/P3 12개에 한정된다.

## Sensitivity

| Analysis | Count / denominator | Proportion | Wilson 95% CI |
| --- | ---: | ---: | ---: |
| Primary strict | 12/12 | 1.000 | [0.758, 1.000] |
| Any field dispute as non-masked | 9/12 | 0.750 | [0.468, 0.911] |
| Q0 only | 11/11 | 1.000 | [0.741, 1.000] |

Dispute-as-nonmasked는 strict-call field가 일치했더라도 여섯 controlled field 중 하나라도 raw disagreement가 있었던 세 task를 모두 non-masked로 두는 보수적 stress test다. Q0-only는 final `data_quality=Q1`인 `django__django-15993` 한 행을 제외한다.

## Adjudication and mechanism diagnostics

두 raw pass는 9/12행에서 여섯 controlled field가 모두 일치했다. 나머지 3행의 5개 field는 제3 reviewer가 판정했으며 unresolved와 protocol deviation은 없다.

| Field | Final distribution |
| --- | --- |
| `oracle_direction_in_candidate_set` | `no`=1, `yes`=11 |
| `oracle_revealed_missing_evidence` | `no`=1, `partial`=2, `yes`=9 |
| `oracle_alternative_fix_exists` | `yes`=12 |
| `available_evidence_unique_in_hindsight` | `no`=12 |
| `behavior_target_space_size` | `2-3`=9, `many`=3 |
| `data_quality` | `Q0`=11, `Q1`=1 |

Capability threshold 0ㆍ8ㆍ32ㆍ50에서 solved denominator는 같은 12행이고 strict masking count도 12로 유지된다.

## Claim boundary

이 결과는 benchmark `resolved`가 task-time patchability와 동치가 아님을 보여 주는 oracle-masking mechanism 결과다. 480-task masking prevalence, broad APR 일반화, 특정 agent capability, abstention의 causal utility improvement를 의미하지 않는다.
