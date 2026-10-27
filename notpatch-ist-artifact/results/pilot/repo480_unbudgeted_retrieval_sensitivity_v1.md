# RR-F 확장 저장소 감사 sensitivity

- **Status:** `expanded-view-sensitivity`
- **Authority:** RR-F 7행의 원/확장 label 전이, 근거 범위, Q0ㆍ이탈 sensitivity와 부분 대체 what-if
- **Last verified:** 2026-10-21

Frozen P2/P3 중 retrieval이 insufficient/unclear로 표시된 7행 전수를 같은 base commit의 모든 regular UTF-8 text로 다시 판정한 단일 전문가(`repo480_retrieval_r1`) 반환을 분석했다. 원 labelㆍ선정 조건ㆍoracleㆍoutcome은 숨겼고 public comment/link의 원 unavailable 상태는 유지했다. 판정 불가 행과 제외 행은 없다. Frozen available-only label은 수정하지 않는다.

## 행별 결과

| Item | Task | 원 label / retrieval / Q | 확장 label / Q / retrieval | 확장 근거의 역할 | 원 packet 밖 인용 | 검증 패널 label | RQ2 |
| --- | --- | --- | --- | --- | ---: | --- | --- |
| R01 | `sympy__sympy-15596` | P2 / insufficient / Q0 | P1 / Q0 / sufficient | new_decisive_evidence | 7/9 | P2 | member; strict yes/yes |
| R02 | `sympy__sympy-13346` | P2 / insufficient / Q0 | P1 / Q0 / sufficient | corroboration_only | 11/14 | P2 | member; strict yes/yes |
| R03 | `sympy__sympy-18116` | P3 / unclear / Q0 | P1 / Q0 / sufficient | corroboration_only | 5/10 | P3 | — |
| R04 | `sympy__sympy-16052` | P3 / insufficient / Q2 | P3 / Q0 / insufficient | still_insufficient | 3/8 | P3 | member; strict yes/yes |
| R05 | `django__django-15993` | P3 / unclear / Q0 | P1 / Q2 / sufficient | corroboration_only | 3/9 | P0 | member; strict yes/no |
| R06 | `sympy__sympy-13988` | P2 / insufficient / Q0 | P2 / Q0 / sufficient | still_insufficient | 5/6 | P2 | — |
| R07 | `django__django-13207` | P2 / insufficient / Q0 | P2 / Q0 / sufficient | still_insufficient | 7/8 | P2 | — |

RQ2 열의 strict 값은 원 패널/matched 패널 treated arm의 호출이다. 검증 패널 label은 RR-A 독립 패널의 frozen-packet 판정이다. 두 열은 protocol 동결 뒤 추가한 사후 기술 대조다.

## 전이와 경계 변화

- 전이: P2→P1 2, P2→P2 2, P3→P1 2, P3→P3 1.
- P2/P3→P0/P1 경계 변화: 4/7 (0.571; Wilson 95% CI [0.250, 0.842]). 7행 전체 분모도 판정 불가가 없어 같은 값이다.
- Exact label 변화: 4/7 (0.571; Wilson 95% CI [0.250, 0.842]). P2/P3 유지: 3/7 (0.429; Wilson 95% CI [0.158, 0.750]).
- 원 retrieval 표시별 경계 변화: insufficient 2/5, unclear 2/2.
- Repository별 경계 변화: django/django 1/2, sympy/sympy 3/5.
- 확장 근거의 역할별 경계 변화: new_decisive_evidence 1/1, corroboration_only 3/3, still_insufficient 0/3, unclear 0/0.
- 확장 retrieval sufficiency: insufficient 1, sufficient 6.

경계 변화 4행 가운데 원 packet 밖의 결정적 근거를 전문가가 지목한 행은 R01 하나다. 나머지 3행(R02ㆍR03ㆍR05)은 결정적 근거가 이미 원 packet에 있었고 확장 자료는 보강일 뿐이라고 기록했다. 전문가 자신의 기록이 이 3행의 변화를 새 근거로 설명하지 않으므로 판정자 간 경계 해석 차이가 더 직접적인 경쟁 설명이다. P2/P3로 남은 3행 중 R06ㆍR07은 확장 retrieval이 충분했지만 maintainer의 호환성ㆍ기능 범위 선택이 여전히 필요하다고 기록했고, R04는 issue가 가리키는 재현 입력(#7842)을 저장소 검색으로 찾지 못해 retrieval이 여전히 insufficient였다.

## 근거 범위

인용 64개는 비repository 10개, 원 packet에 이미 포함 13개, 원 packet에 없던 파일 35개, 원 발췌에 전부 포함되지 않았던 행 6개다. 검색 기록은 118단계다. `new_decisive_evidence` 행은 원 packet 밖 인용을 하나 이상 가진다. 인용 위치 검사는 보존 archive에서 배포 validator를 다시 실행해 재현했으며 판단의 의미적 타당성이나 탐색의 완전성을 보증하지 않는다.

## Q0ㆍ이탈 sensitivity

- 원 Q0 membership R01ㆍR02ㆍR03ㆍR05ㆍR06ㆍR07: 경계 변화 4/6.
- 확장 Q0 membership R01ㆍR02ㆍR03ㆍR04ㆍR06ㆍR07: 3/6.
- 두 판정 모두 Q0인 R01ㆍR02ㆍR03ㆍR06ㆍR07: 3/5.
- R07 절차 이탈 제외(노출 note 행 없음): 4/6 (0.667; Wilson 95% CI [0.300, 0.903]). R07은 P2로 남아 what-if 분자는 바뀌지 않는다.

원 판정의 Q2는 R04, 확장 판정의 Q2는 R05라 두 Q0 subset은 같은 행 집합이 아니다.

## 부분 대체 what-if

- Frozen 기준: 26/480 = 0.054167.
- 평가된 7행에 확장 label 대입: 22/480 = 0.045833.
- 이탈ㆍ노출 행 제외 대입: 22/480 = 0.045833.
- Q0 frame(frozen Q 기준) 기준값 25/477 = 0.052411, 대입 21/477 = 0.044025; 감사 행에 확장 Q 사용 시 22/477 = 0.046122.

감사하지 않은 473행과 판정 불가 행은 원 값을 유지한다. P2/P3 행만 다시 보았으므로 대입은 분자를 줄이는 방향으로만 움직이며 수정 prevalence, 새 추정치, 상ㆍ하한이 아니다. 이 비율은 원 raw pass의 22/480과 다른 family이므로 합치지 않는다.

## 사후 대조(사전 고정 아님)

- RR-A 검증 패널은 경계가 바뀐 4행 중 3행을 P2/P3, 1행(R05)을 P0/P1로 판정했었다. P2/P3로 남은 3행은 검증 패널에서도 모두 P2/P3였다.
- RQ2 12행 중 4행(R01ㆍR02ㆍR04ㆍR05)이 RR-F 대상이었고, 그중 3행(R01ㆍR02ㆍR05)이 확장 판정에서 P1이었다. 원고의 두 RQ2 worked example(R01ㆍR05)이 모두 여기에 속한다. 나머지 8행은 retrieval 표시가 sufficient여서 다시 보지 않았다.
- 확장 P1 3행을 빼면 strict 호출은 원 패널 9/9, matched 패널 treated 8/9다. RQ2 masking 판정을 확장 view에서 다시 계산한 값이 아니며, RQ2는 frozen packet label에 상대적인 mechanism frame으로 남는다.

## 수용 기록과 한계

- Owner confirmation of expert authorship is recorded only in the message of commit dee9824 ('Correct retrieval r1 authorship per user confirmation'); the repository holds the blank template (commit f8c321a) and this filled return, so any wording before that correction is not preserved.
- Overlap between repo480_retrieval_r1 and earlier annotation roles is not established; it remains part of RR-K role disclosure.
- One expanded-only expert pass with no paired frozen-view pass by the same expert: label changes mix evidence widening with rule and case interpretation, so they are not causal retrieval effects.
- Evidence roles are the expert's explanatory self-assessment; only rows marked new_decisive_evidence cite decisive text outside the frozen packet.
- Only frozen P2/P3 rows flagged insufficient/unclear were re-examined, so the substitution can only lower the numerator; (26-k)/480 is a what-if, neither a corrected prevalence nor a bound.
- Wilson intervals over seven rows from two repositories are descriptive; no population reproducibility or significance claim.
- R07's self-reported search-derivation deviation stays in all-row results and is excluded only in the deviation sensitivity; null exposure notes are self-report, not verified absence of exposure.
- Validation-panel and RQ2 cross-references were added after the protocol was frozen; they are descriptive and do not recompute any RQ2 masking call.
- Frozen available-only labels, 26/480, 0.094, 12/12 and 10/12 are unchanged; public comments and links stay unavailable as in the frozen packet.

입력 hash, 행별 근거 범위, 층별 분모는 동명 JSON과 rows JSONL에 있다.

```bash
uv run python scripts/analyze_repo480_unbudgeted_retrieval.py --analyzed-on 2026-10-21
```
