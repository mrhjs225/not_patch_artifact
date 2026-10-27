# RR-E 전문가 판정 후 유형 분포

- **Status:** `expert-adjudicated-types`
- **Authority:** 주 유형 분포, 원 코더별 sensitivity와 반환 검증
- **Last verified:** 2026-10-19

AI analytic coding(c1)과 독립 전문가(c2)의 유형이 일치한 행은 그 유형을 유지하고, 갈린 Set A 10행만 다른 전문가가 두 원문을 보고 판정했다. 제외 행은 없다.

## seta

| 유형 | 최종 | 비율 [Wilson 95% CI] | c1 | c2 |
| --- | ---: | --- | ---: | ---: |
| a_same_contract | 1/23 | 0.043 [0.008, 0.210] | 1 | 1 |
| b_anticipated | 4/23 | 0.174 [0.070, 0.371] | 10 | 3 |
| b_unanticipated | 9/23 | 0.391 [0.222, 0.592] | 6 | 10 |
| c_evidence_reading | 2/23 | 0.087 [0.024, 0.268] | 0 | 2 |
| d_oracle_scope | 5/23 | 0.217 [0.097, 0.419] | 6 | 4 |
| u_undeterminable | 2/23 | 0.087 [0.024, 0.268] | 0 | 3 |

판정 전 유형 일치: 13/23; κ 0.444. 판정 후 일치를 독립 재현성 지표로 계산하지 않는다.

## setb

| 유형 | 최종 | 비율 [Wilson 95% CI] | c1 | c2 |
| --- | ---: | --- | ---: | ---: |
| evidence_utilization | 4/22 | 0.182 [0.073, 0.385] | 4 | 4 |
| rule_threshold | 12/22 | 0.545 [0.347, 0.731] | 12 | 12 |
| case_judgment | 6/22 | 0.273 [0.132, 0.482] | 6 | 6 |
| undeterminable | 0/22 | 0.000 [0.000, 0.149] | 0 | 0 |

판정 전 유형 일치: 22/22; κ 1.000. 판정 후 일치를 독립 재현성 지표로 계산하지 않는다.

## 불일치 10행의 판정

| Item | c1 | c2 | 최종 |
| --- | --- | --- | --- |
| A03 | b_anticipated | u_undeterminable | u_undeterminable |
| A05 | b_anticipated | b_unanticipated | b_unanticipated |
| A08 | b_unanticipated | c_evidence_reading | c_evidence_reading |
| A09 | b_anticipated | b_unanticipated | b_anticipated |
| A10 | b_anticipated | b_unanticipated | b_unanticipated |
| A13 | d_oracle_scope | u_undeterminable | d_oracle_scope |
| A18 | b_anticipated | b_unanticipated | b_unanticipated |
| A20 | b_anticipated | b_unanticipated | b_unanticipated |
| A21 | b_anticipated | c_evidence_reading | c_evidence_reading |
| A23 | d_oracle_scope | u_undeterminable | u_undeterminable |

A03은 기록 간 packet 내용 서술 충돌, A23은 JavaScript 현재 동작 근거 부재로 판단 불가를 유지한다. 판정을 받지 못한 누락 행이 아니다. A09는 정당한 잔여 trade-off 해석의 경계 사례이며 원 코더 sensitivity를 함께 둔다.

## 해석과 what-if

Set A의 계약 선택은 13/23행이며, 이미 기록된 잔여 가정 4행과 미인지 계약 선택 9행으로 나뉜다. 근거 판독 문제 2행이 확인되어 기존 c1의 ‘근거 오독 없음’ 해석은 유지하지 않는다. Oracle 범위 문제 5행, 같은 계약 1행, 판단 불가 2행도 함께 보고한다.

- b_unanticipated: k=9; (26 + 185k/47)/480 = 0.127970.
- b_all: k=13; (26 + 185k/47)/480 = 0.160771.

이는 경계 이동 해석의 크기를 살피는 가정적 계산이며 수정 prevalence나 상ㆍ하한이 아니다.

## 검증ㆍ한계

근거 field 경로 121개와 qualifier 11개가 연결된다. 이 검사는 근거가 유일한 판정을 강제한다는 보증이 아니다.

- Owner confirms a different expert completed this adjudication. Distinctness from c2 is confirmed; overlap with underlying annotation roles is not independently established and remains part of RR-K disclosure.
- Initial return had empty exposure_note strings in all ten rows. The received original is preserved; only these fields were normalized to null after the owner relayed expert confirmation. This does not remove the known hints/post-hoc discussion mentions in supplied A09, A10 and A18 source rationales and c2 notes; their effect is unknown.
- Final types combine pre-adjudication c1/c2 type agreement and third-expert decisions on disagreements only.
- No final consensus is claimed for controlled fields or secondary types; raw coder summaries are sensitivities.
- Two undeterminable types remain in the denominator; completed adjudication is not forced type resolution.
- c1 is AI analytic coding, c2 is expert coding; adjudication is informed by both, not a third blinded pass.
- Wilson intervals are row-level descriptive intervals, not repository-clustered population inference; sets share five tasks.
- Inherited source hints/discussion and prior exposure remain limitations; null notes do not certify an exposure-free package.
- Frozen labels, 26/480, 0.094 and 76/112 are unchanged; displacement scenarios are neither estimates nor bounds.

입력 hash, 원문 보존ㆍnull 정정 이력, 판정별 교차표ㆍraw field/secondary sensitivity는 동명 JSON에 있다.

```bash
uv run python scripts/analyze_repo480_rre_adjudication.py --analyzed-on 2026-10-19
```
