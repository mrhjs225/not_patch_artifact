# Repo480 Bidirectional Construct-Validity Audit Protocol

- **Status:** `frozen-before-review`
- **Authority:** repository-packet P0/P1 false-confidence와 P2/P3 false-pessimism audit
- **Last verified:** 2026-10-13 (결과 경로만 추가했다. protocol 본문은 반환 전 동결본 그대로다)
- **Result:** `results/pilot/repo480_construct_validity_analysis_v1.md`(최종 분석),
  `results/pilot/repo480_construct_validity_rows_v1.jsonl`(138행 row audit). 후속 RR-E는 이 결과의
  P1 non-strict 23행을 다룬다(`docs/status.md`).

## 1. 목적과 label freeze

이 audit은 available-only construct의 두 오류 방향을 대칭적으로 진단한다.

- **False confidence:** P0/P1에서 잠근 predicted direction이 post-hoc oracle behavior와 맞지 않음
- **False pessimism:** P2/P3로 판단했지만 hindsight에서 frozen available evidence가 실제로는
  oracle behavior를 유일하게 정했음

Oracle 판정은 `data/annotations/adjudicated/repo480_available_v1.jsonl`의 P-label을 수정하지
않는다. RQ1 prevalence와 RQ2 masking 결과도 소급 재라벨하지 않는다.

## 2. Frozen denominator

| Axis | Selection rule | N | 역할 |
| --- | --- | ---: | --- |
| P0/P1 direction match | 480 random frame에서 `prevalence_random_rank <= 120`인 P0/P1 전 행 | 112 | primary-frame random audit |
| P2/P3 hindsight uniqueness | 480 random frame의 P2/P3 전 행 | 26 | full-frame false-pessimism census |

P0/P1은 P0 65개와 P1 47개, P2/P3은 P2 22개와 P3 4개다. P0/P1 112개는 전체
P0/P1 454개의 census가 아니며, 사전에 동결된 random-rank prefix를 이용한 subset이다.
P2/P3 26개는 해당 480-task frame의 전수다. Selection은 새 oracle 판단 전에 frozen rank와
available-only label만으로 정한다.

## 3. Evidence와 review design

세 신규 role `repo480_cv_r1`, `repo480_cv_r2`, `repo480_cv_r3`가 동일한 138개를 독립적으로
판정한다. 세 role은 서로의 판단, 기존 RQ2/expert-panel oracle 진단, repair-agent
identityㆍpatchㆍscoreㆍoutcome, detector output을 보지 않는다. Package 밖 repository
checkout, GitHub와 web도 사용하지 않는다.

P0/P1 row는 locked predicted direction과 세 요소 template, available-only rationale, issue
title/body와 oracle patch/test를 제공한다. 이 axis는 available-evidence sufficiency를 다시
판정하지 않고 direction-to-oracle match만 측정하므로 대용량 repository packet을 반복 제공하지
않는다. 원본 reviewer-view hash는 row에 남긴다.

P2/P3 row는 hindsight uniqueness를 독립 판정할 수 있도록 frozen reviewer packet 전체,
locked candidate directions와 missing-evidence 기록, oracle patch/test를 제공한다.

## 4. Controlled fields

P0/P1의 `predicted_direction_match`는 다음 네 값이다.

- `match`: component, trigger, observable behavior가 기능적으로 동등함
- `partial_match`: 핵심 target은 같지만 중요한 condition/API surface/edge case가 빠짐
- `mismatch`: component 또는 observable behavior intent가 다름
- `not_assessable`: package의 oracle만으로 판단 불가

P2/P3의 `available_evidence_unique_in_hindsight`는 oracle을 task-time evidence로 소급하지 않은
상태에서 frozen evidence가 하나의 observable target만 허용했는지를 `yes|no|unclear`로
판정한다. `oracle_direction_in_candidate_set`도 `yes|no|unclear`로 기록한다. 같은 behavior의
구현 차이는 별도 target으로 세지 않는다.

## 5. Agreement, adjudication, analysis

세 반환이 모두 self-check를 통과해 canonical 원본으로 보존되기 전에는 중간 결과를 계산하지
않는다. Controlled field가 하나라도 다르면 별도 role `repo480_cv_adj`가 package-only 판정을
수행한다. Raw unanimous/majority distribution과 adjudicated 결과를 분리해 보고한다.

- P0/P1 primary support: `match`; 나머지 outcome은 strict non-match
- P0/P1 sensitivity: `match + partial_match`
- False-confidence diagnostic: `mismatch`
- P2/P3 false-pessimism diagnostic: `available_evidence_unique_in_hindsight=yes`
- Interval: two-sided Wilson 95% CI
- Sensitivity: Q0-only, P0/P1 strata, raw reviewer intersection/union, 모든 controlled-field
  dispute를 adverse로 처리한 결과

`not_assessable`, `unclear`, protocol deviation과 adjudication unresolved는 denominator와 처리
방식을 명시한다. Raw agreement와 category distribution을 보고하고, category가 퇴화하면
Cohen's kappa를 억지로 해석하지 않는다.

## 6. Claim boundary

P0/P1 결과는 frozen 120-prefix subset의 direction-match diagnostic이며 전체 454행의 census가
아니다. P2/P3 결과는 이 480-task frame 안의 false-pessimism diagnostic이다. 어느 결과도 broad
APR population, automatic patch authorization의 안전성, repair capability 또는 causal utility로
일반화하지 않는다.
