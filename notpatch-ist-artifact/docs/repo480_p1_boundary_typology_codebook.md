# Repo480 P1 Boundary Typology Codebook (RR-E)

- **Status:** `frozen-before-coding` (v1)
- **Authority:** RR-E의 P1 non-strict 23행 유형화와 경계 불일치 22행 비교의 코딩 규칙ㆍ유형 유도 규칙ㆍ보고 규칙
- **Last verified:** 2026-10-13

이 codebook은 코딩을 시작하기 전에 동결한다. 코딩 중 규칙이 행에 맞지 않으면 규칙을 고치지 않고
해당 field를 `unclear`로 두며 `coder_note`에 이유를 남긴다. 규칙 수정이 필요하면 v2를 따로 만들고 v1
코딩을 보존한다. Label 정의는 `docs/annotation_guideline.md` v0.5 §3ㆍ§7ㆍ§8과
`docs/task_schema.md` §10이 소유하며, 이 문서는 그 정의를 기존 기록에 적용하는 방법만 정한다.

## 1. 질문

- **Set A (2026-10-12 리뷰 M1, 2026-08-20 자체 리뷰 M3):** P1으로 잠근 예측 방향이 oracle과 strict하게
  맞지 않은 23행에서, 비일치가 (a) 같은 동작 계약의 구현 차이, (b) 서로 다른 동작 계약 사이의 미결정
  선택, (c) task-time 근거의 오독ㆍ누락, (d) oracle/packaging mismatch 중 무엇으로 설명되는가?
  (b)는 다시 "P1 기록이 그 선택을 bounded assumption으로 이미 적어 둔 경우"와 "적지 않은 경우"로
  나눈다. 앞의 것은 oracle이 P1 안의 잔여 가정을 고정한 사례(P1 수준의 oracle selection)이고, 뒤의
  것은 P1 기록이 다른 동작 계약을 인지하지 못한 사례(경계 이동 후보)다.
- **Set B (2026-10-12 리뷰 M2):** Frozen adjudicated boundary와 독립 패널(RR-A) boundary가 갈린 22행에서,
  차이가 규칙 해석, evidence 이용, 개별 사례 판단 중 무엇에서 생겼는가? 다툼의 대상인 대안이 별개의
  동작 계약인가?

## 2. 분석 단위와 denominator

| Set | 선택 규칙 | N | 원천 |
| --- | --- | ---: | --- |
| A `p1_non_strict` | Construct-validity row 중 `available_only_primary_label = P1`이고 최종 `predicted_direction_match`가 `partial_match` 또는 `mismatch`인 행 | 23 (partial 14, mismatch 9) | `results/pilot/repo480_construct_validity_rows_v1.jsonl` |
| B `boundary_discordant` | RR-A analysis row 중 `binary_match = false`인 행 | 22 | `results/pilot/repo480_boundary_validation_analysis_rows_v1.jsonl` |

두 set은 5개 task를 공유한다. 같은 task라도 Set A 코드와 Set B 코드는 서로 다른 질문에 답하므로 따로
기록한다. 선택은 frozen result 파일만으로 결정론적으로 정하며 worklist CLI가 행 수를 검사한다.

## 3. 입력과 evidence 경계

새 evidence를 만들지 않는다. 이미 반환ㆍ수용된 기록만 읽는다.

- **Set B는 available-only 기록만 쓴다.** Frozen canonical label, P0-3 raw pass(`repo480_r1`,
  `repo480_r2`), 판정자 `repo480_adj` 결정, RR-A raw pass(`repo480_bv_r1`, `repo480_bv_r2`), 판정자
  `repo480_bv_adj` 결정과 adjudicated panel record, frozen reviewer view의 issue title/body. Oracle
  patchㆍtest, construct-validity 판정, RQ2 기록, agent outcome은 Set B 코딩에 쓰지 않는다.
- **Set A는 위 available-only 기록에 더해** construct-validity audit의 oracle evidence(`patch`,
  `test_patch`, `FAIL_TO_PASS`)와 세 raw 판정(`repo480_cv_r1`--`r3`)ㆍ판정자 `repo480_cv_adj`의
  rationale을 쓴다.
- **쓰지 않는 것:** SWE-bench `hints_text`(frozen packet 밖이고 available-only annotator에게
  제공되지 않았다. Packet 밖 task-time 정보의 영향은 RR-F가 다룬다), repository checkoutㆍGitHubㆍweb
  탐색, agent outcome, detector output.
- Frozen packet 내용에 대한 판단은 기존 기록이 인용한 pointer와 서술을 따른다. 기록끼리 packet 내용을
  다르게 서술하면 새로 packet을 열어 해소하지 않고 해당 field를 `unclear`로 둔다.
- **코딩 순서:** Set B 22행을 모두 코딩해 저장한 뒤 Set A의 oracle 자료를 연다. Set B 코딩이 oracle에
  오염되지 않게 하기 위한 순서다. 다만 codebook 설계 중 coder가 `psf__requests-2466`의 construct
  adjudication rationale과 `pydata__xarray-4248`의 oracle patch 일부를 이미 보았으므로 이 두 행은
  `exposure_note`에 그 사실을 남긴다.

## 4. Set A field

| Field | 값 | 정의 |
| --- | --- | --- |
| `oracle_divergence` | 문장 | Oracle이 잠긴 예측 방향과 다르게 하는 일(또는 예측 방향이 하고 oracle은 하지 않는 일)을 한두 문장으로 쓴다 |
| `divergence_kind` | `implementation_only` | 예측 방향을 충실히 구현하면 oracle의 `FAIL_TO_PASS` 동작에서 같은 관찰 결과가 나온다. 차이는 파일ㆍ함수 위치, 내부 구조, 이름, 문서처럼 관찰 동작이 아닌 부분이다 |
| | `added_behavior` | Oracle은 issue의 trigger에서 예측한 관찰 변화를 그대로 만들고, 예측 방향이 빠뜨렸지만 반박하지 않는 다른 trigger, 조건, edge case, API surface의 관찰 동작을 추가로 바꾼다 |
| | `different_behavior` | Issue의 trigger 또는 test가 검사하는 trigger에서 oracle의 관찰 동작이 예측과 다르거나 반대다(다른 반환값ㆍ예외ㆍ출력, 뒤집힌 조건, 다른 API 계약). 또는 oracle이 다른 component를 고쳐 예측한 변화로는 test가 기대하는 동작이 나오지 않는다 |
| | `unclear` | 위 셋 중 하나를 고를 근거가 기록에 없다 |
| `predicted_supported` | `yes` / `no` / `unclear` | `yes`: 기존 available-only 기록이 예측한 관찰 변화를 뒷받침하는 packet 근거를 인용하고, 어떤 available-only 기록도 그 변화를 배제하는 packet 근거를 인용하지 않는다. `no`: 어떤 available-only 기록(다른 패널 포함)이 예측 변화와 모순되는 packet 근거를 인용하거나, frozen rationale이 인용한 근거를 다른 기록이 사실과 다르다고 지적한다 |
| `oracle_basis` | `required_by_packet` | 갈린 부분의 oracle 동작을 issue 본문이 직접 말하거나, 기존 available-only 기록이 인용한 packet 근거(docs, visible test, 기존 code convention)가 그 동작을 요구한다 |
| | `admissible_not_selected` | 갈린 부분의 oracle 동작이 issue 의도와 인용된 근거에 부합하지만, 인용된 어떤 근거도 그것을 예측(또는 생략된) 대안보다 우선해 고르지 않는다 |
| | `outside_issue_scope` | Oracle을 보고 나서도 issue 의도에서 그 동작을 끌어낼 수 없다. Test가 issue와 무관한 동작을 검사하거나, oracle이 issue가 다루지 않는 의미를 바꾼다(packaging mismatch 포함) |
| | `not_applicable` | `divergence_kind = implementation_only`일 때만 쓴다 |
| | `unclear` | 판단 근거가 기록에 없다 |
| `assumption_anticipated` | `yes` / `no` / `not_applicable` | Frozen canonical record의 `rationale`, `missing_evidence_needed`, blocker가 oracle이 갈라진 바로 그 차원을 잔여 가정이나 열린 질문으로 적었는지. `implementation_only`이면 `not_applicable` |
| `secondary_types` | 유형 code 목록 | 결정적이지 않은 다른 차이가 다른 유형에 해당하면 적는다. 없으면 빈 목록 |
| `evidence_refs` | pointer 목록 | 판단에 쓴 기록 field. 예: `frozen.rationale`, `cv.adjudication.rationale`, `oracle.test_patch:test_name`, `bv_adj.overrides.rationale` |
| `coder_note` | 1--3문장 | 결정적 차이와 판단 근거 |

"결정적 차이"는 construct-validity 최종 판정(판정자 rationale 또는 세 raw rationale의 공통 근거)이
non-strict 판정의 이유로 든 차이다. 차이가 여러 개면 그 판정이 가장 먼저 든 차이를 결정적 차이로 하고
나머지는 `secondary_types`에 적는다.

### 4.1 Set A 유형 유도 규칙

유형은 coder가 직접 고르지 않고 analyzer가 위 field에서 다음 순서로 유도한다. 앞 규칙이 우선한다.

1. `oracle_basis = outside_issue_scope` → `d_oracle_scope`
2. `divergence_kind = implementation_only` → `a_same_contract`
3. `oracle_basis = required_by_packet` → `c_evidence_reading`
4. `divergence_kind = added_behavior`이고 `oracle_basis = admissible_not_selected` → `a_same_contract`
5. `divergence_kind = different_behavior`이고 `predicted_supported = no` → `c_evidence_reading`
6. `divergence_kind = different_behavior`이고 `oracle_basis = admissible_not_selected`이고
   `predicted_supported = yes` → `b_contract_choice`
7. 그 밖 → `u_undeterminable`

우선순위는 guideline §7의 순서(data quality를 먼저 보고, 그다음 evidence 판독, 그다음 behavior target
수)를 따른다. `implementation_only`와 `oracle_basis = not_applicable`은 서로를 함의해야 하며 analyzer가
검사한다. `b_contract_choice`는 `assumption_anticipated`로 `b_anticipated`(P1 기록이 그 선택을 잔여
가정으로 적음)와 `b_unanticipated`로 나눈다.

### 4.2 Set A 해석 대응

| 유형 | 해석 | Frozen P1 label과의 관계 |
| --- | --- | --- |
| `a_same_contract` | Strict match 기준이 P1 정의보다 촘촘해서 생긴 non-strict | P1 정의와 양립한다 |
| `b_anticipated` | P1 기록이 bounded assumption으로 남긴 선택을 oracle이 하나로 고정했다(P1 수준의 oracle selection) | P1 정의("exact API contract, UI layout convention 같은 bounded assumption")와 P2 정의("서로 다른 observable behavior target")가 겹치는 회색 지대 |
| `b_unanticipated` | P1 기록이 인지하지 못한 다른 동작 계약을 oracle이 골랐다 | 사후 기록상 P2 정의에 가깝다. 경계 이동 후보 |
| `c_evidence_reading` | Task-time 근거가 oracle 동작을 가리켰는데 예측 방향이 놓치거나 잘못 읽었다 | 방향의 false confidence. 그 자체로 P2를 뜻하지 않는다 |
| `d_oracle_scope` | Benchmark oracle/test가 issue 범위 밖 동작을 요구한다 | Label이 아니라 benchmark artifact의 문제 |
| `u_undeterminable` | 기존 기록으로 판별할 수 없다 | 판단 보류 |

## 5. Set B field

| Field | 값 | 정의 |
| --- | --- | --- |
| `disputed_alternative` | 문장 | P2/P3 쪽 판정이 근거로 삼는 대안 동작(또는 P3의 경우 빠졌다고 본 핵심 evidence)을 한두 문장으로 쓴다 |
| `alternative_relation` | `distinct_contract` | 대안이 P0/P1 쪽 예측 방향과 다른 관찰 동작ㆍcompatibilityㆍuser-facing semantics를 만든다(guideline §3 P2 문구) |
| | `same_contract_variant` | 대안이 같은 외부 관찰 동작의 구현ㆍ위치 변형이거나 local evidence로 고를 수 있는 좁은 변형이다 |
| | `no_executable_candidate` | P2/P3 쪽 판정이 책임 있는 후보 자체가 없다는 P3 기준에 근거하므로 대안 계약이 쟁점이 아니다 |
| | `unclear` | 판단 근거가 기록에 없다 |
| `p01_side_treatment` | `excluded_by_cited_evidence` | P0/P1 쪽 기록이 그 대안(또는 P3 쪽이 없다고 본 evidence)을 배제하거나 보충하는 packet 근거를 인용한다 |
| | `named_as_bounded_assumption` | P0/P1 쪽 기록이 그 대안이나 잔여 질문을 언급하지만 배제 근거 없이 좁은 가정으로 둔다 |
| | `not_addressed` | P0/P1 쪽 기록이 그 대안을 언급하지 않는다 |
| | `unclear` | 판단 근거가 기록에 없다 |
| `p23_side_engages_p01_evidence` | `yes` / `no` / `not_applicable` / `unclear` | P0/P1 쪽이 인용한 배제 근거를 P2/P3 쪽 기록이 다루는지(예: 그 근거가 대안을 배제하지 못한다고 논증). `p01_side_treatment`가 `excluded_by_cited_evidence`가 아니면 `not_applicable` |
| `p23_side_cites_packet_for_alternative` | `yes` / `no` / `unclear` | P2/P3 쪽 기록이 issue 본문 밖의 packet 근거(code, docs, visible test, config)를 들어 대안이 살아 있다고 논증하는지 |
| `evidence_refs` | pointer 목록 | 판단에 쓴 기록 field. 예: `frozen.adjudication.boundary_reason`, `bv_adj.resolution_notes`, `bv_r2.rationale` |
| `coder_note` | 1--3문장 | 갈림의 핵심 |

"P0/P1 쪽"과 "P2/P3 쪽"은 두 adjudicated outcome(frozen과 panel) 중 각 binary class를 낸 쪽이다. 각
쪽의 기록에는 그 outcome에 이른 raw pass와 판정자 기록을 모두 포함한다.

### 5.1 Set B 유형 유도 규칙

1. (`p01_side_treatment = excluded_by_cited_evidence`이고 `p23_side_engages_p01_evidence = no`) 또는
   (`p01_side_treatment = not_addressed`이고 `p23_side_cites_packet_for_alternative = yes`)
   → `evidence_utilization`: 한쪽이 결정적이라고 본 packet 근거를 다른 쪽이 쓰지 않았다
2. `p01_side_treatment = named_as_bounded_assumption` 또는 `alternative_relation = same_contract_variant`
   → `rule_threshold`: 양쪽이 같은 대안을 보고, 그것이 별개 target인지 bounded assumption인지에서 갈렸다
3. (`p01_side_treatment = excluded_by_cited_evidence`이고 `p23_side_engages_p01_evidence = yes`) 또는
   (`p01_side_treatment = not_addressed`이고 `p23_side_cites_packet_for_alternative = no`)
   → `case_judgment`: 같은 근거를 두고 사실 판독이 갈렸거나, 같은 issue 수준 정보에서 한쪽만 대안을
   떠올렸다
4. 그 밖 → `undeterminable`

Evidence 이용 차이를 먼저 보는 이유는 그것이 protocol로 고칠 수 있는 원인이기 때문이다. 다음으로 규칙
해석, 마지막으로 개별 판단을 둔다.

## 6. 집계와 보고

- Set A: 유형 분포(최종 판정 partial/mismatch별), `b`의 anticipated 분할, `secondary_types` 언급 기준
  분포, 23행 중 RR-A 패널에 포함된 행의 패널 label 교차표. 비율에는 Wilson 95% CI를 붙이되 23행의
  기술 통계로만 쓴다.
- Set A displacement what-if: `b` 행 수 k를 120-prefix의 P1 47행에 대한 비율로 보고 frame P1 185행에
  옮겼을 때의 P2/P3 비율 `(26 + 185k/47)/480`을 k = `b` 전체와 `b_unanticipated` 두 경우로 계산한다.
  이 값은 경계 이동 해석의 크기를 가늠하는 what-if이며 수정 추정치, 상한, 하한이 아니다(strict match
  행에도 oracle이 같은 방향을 고른 다중 계약 task가 있을 수 있고, P0 non-strict 13행은 코딩하지
  않는다).
- Set B: `divergence_source`와 `alternative_relation` 분포, 불일치 방향(frozen P0/P1 → panel P2/P3와
  반대)별 분포, P1↔P2 경계와 그 밖 경계의 구분, 각 쪽의 repository evidence 인용 여부, Set A와의
  공유 행.
- Coder가 한 명이므로 agreement 통계를 계산하지 않는다.

## 7. Claim boundary

- `repo480_available_v1` label, `26/480`, `0.094`, `76/112`는 바뀌지 않는다. 이 분석은 sensitivity와
  진단이다.
- 이 codebook의 첫 코딩(`repo480_rre_c1`)은 AI agent(Claude Opus 5.5)가 수행한 analytic coding pass다.
  전문가 annotation으로 세지 않고, 전문가 검증 전에는 원고에서 그 사실을 밝힌다.
- `b` 행 수를 수정된 prevalence나 preferred estimate로 쓰지 않는다.

## 8. Codebook 정밀화 산출물

분석 결과로 P1/P2 회색 지대와 evidence 이용 요건에 대한 codebook 정밀화 후보를 정리한다. 후보는 새
version의 validation에서만 적용하며 기존 label에 소급하지 않는다.

## 9. 검증

독립 전문가 한 명이 c1 코드를 보지 않고 같은 worklist에 이 codebook을 적용하면 field별 일치와 유도
유형 일치를 보고하고 불일치를 판정한다. 실행 여부와 원고의 coder 서술은 owner가 정한다
(`docs/status.md`).
