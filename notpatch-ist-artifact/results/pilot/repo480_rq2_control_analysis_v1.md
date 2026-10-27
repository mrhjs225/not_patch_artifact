# Repo480 RQ2 Matched-Control Analysis

- **Status:** `canonical-pilot`
- **Authority:** RQ2 strict masking rule의 matched negative-control 분석
- **Last verified:** 2026-08-20

## Primary result

| Arm | Strict count | Rate | Wilson 95% CI |
| --- | ---: | ---: | ---: |
| Solved P2/P3 treated | 10/12 | 0.833 | [0.552, 0.953] |
| Matched solved P0/P1 control | 5/24 | 0.208 | [0.092, 0.405] |

Control-minus-treated contrast는 **-0.625**이고, 7개 repository cluster의 모든 823,543개 ordered bootstrap resample을 열거한 percentile 95% interval은 `[-0.875, -0.143]`이다.

대조군 rate가 처리군보다 현저히 낮고 cluster interval이 0을 제외하므로, 사전 등록 판정 규칙에 따라 oracle-masking mechanism 해석은 유지한다. 다만 control 5/24도 strict positive이므로 규칙의 완전한 특이도를 주장하지 않으며, 같은 matched panel의 treated 재판정이 기존 별도 panel의 12/12가 아니라 10/12였다는 panel sensitivity를 함께 보고한다.

## Sensitivity

| Analysis | Treated | Control | Control minus treated |
| --- | ---: | ---: | ---: |
| Any raw dispute as non-masked | 5/12 | 2/24 | -0.333 |
| Q0 only | 10/11 | 5/23 | -0.692 |

Strict rule의 각 conjunct도 같은 방향으로 분리된다. Alternative-fix-exists=yes는 treated 11/12와 control 6/24이고, hindsight-nonunique는 treated 10/12와 control 5/24다.

## Claim boundary

이 결과는 7개 repository의 benchmark-solved 36행 matched frame 안에서 strict rule의 판별 타당도를 지지한다. 480행 전체의 masking prevalence, label이나 resolution의 인과 효과, 완전한 rule specificity 또는 broad APR population 일반화를 뜻하지 않는다.
