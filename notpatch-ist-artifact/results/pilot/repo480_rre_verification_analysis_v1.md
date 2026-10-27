# RR-E 전문가 검증: 판정 전 코딩 비교

- **Status:** `raw-comparison-pending-adjudication`
- **Authority:** 수용된 c1ㆍc2 코딩의 일치와 불일치 목록; 최종 유형 분포가 아님
- **Last verified:** 2026-10-19

사전에 정한 Set A 6유형(anticipated 분할 포함), Set B 4유형을 비교한다. c1은 AI analytic coding, c2는 전문가 코딩이다. 제외 없이 두 set을 따로 분석한다.

| Set | 일치 | 비율 (Wilson 95% CI) | Cohen κ | 판정 대상 |
| --- | ---: | --- | ---: | ---: |
| seta | 13/23 | 0.565 [0.368, 0.744] | 0.444 | 10 |
| setb | 22/22 | 1.000 [0.851, 1.000] | 1.000 | 0 |

Wilson 구간은 행 단위 기술 통계이며 repository 군집성을 반영하지 않는다. Repository별 분모ㆍ일치는 JSON에 기록했다. 두 set은 5개 task를 공유하므로 합산하지 않는다.

## 코더별 분포와 field 일치

### seta

| 유형 | c1 | c2 |
| --- | ---: | ---: |
| a_same_contract | 1 | 1 |
| b_anticipated | 10 | 3 |
| b_unanticipated | 6 | 10 |
| c_evidence_reading | 0 | 2 |
| d_oracle_scope | 6 | 4 |
| u_undeterminable | 0 | 3 |

| 통제 field | 일치 | 비율 (Wilson 95% CI) | κ |
| --- | ---: | --- | ---: |
| divergence_kind | 21/23 | 0.913 [0.732, 0.976] | 0.758 |
| predicted_supported | 21/23 | 0.913 [0.732, 0.976] | 0.000 |
| oracle_basis | 18/23 | 0.783 [0.581, 0.903] | 0.569 |
| assumption_anticipated | 16/23 | 0.696 [0.491, 0.844] | 0.369 |

통제 field 전부 일치: 12/23. 유형이 같은 행의 field 차이는 판정 대상으로 추가하지 않는다.

### setb

| 유형 | c1 | c2 |
| --- | ---: | ---: |
| evidence_utilization | 4 | 4 |
| rule_threshold | 12 | 12 |
| case_judgment | 6 | 6 |
| undeterminable | 0 | 0 |

| 통제 field | 일치 | 비율 (Wilson 95% CI) | κ |
| --- | ---: | --- | ---: |
| alternative_relation | 21/22 | 0.955 [0.782, 0.992] | 0.837 |
| p01_side_treatment | 22/22 | 1.000 [0.851, 1.000] | 1.000 |
| p23_side_engages_p01_evidence | 22/22 | 1.000 [0.851, 1.000] | 1.000 |
| p23_side_cites_packet_for_alternative | 16/22 | 0.727 [0.518, 0.868] | 0.455 |

통제 field 전부 일치: 15/22. 유형이 같은 행의 field 차이는 판정 대상으로 추가하지 않는다.

## 제3 전문가 판정 대상

| Item | Task | c1 | c2 | 갈린 통제 field |
| --- | --- | --- | --- | --- |
| A03 | scikit-learn__scikit-learn-13313 | b_anticipated | u_undeterminable | predicted_supported, oracle_basis, assumption_anticipated |
| A05 | matplotlib__matplotlib-23563 | b_anticipated | b_unanticipated | assumption_anticipated |
| A08 | psf__requests-2466 | b_unanticipated | c_evidence_reading | oracle_basis |
| A09 | pydata__xarray-3114 | b_anticipated | b_unanticipated | assumption_anticipated |
| A10 | sympy__sympy-11870 | b_anticipated | b_unanticipated | assumption_anticipated |
| A13 | sympy__sympy-15241 | d_oracle_scope | u_undeterminable | oracle_basis |
| A18 | matplotlib__matplotlib-23516 | b_anticipated | b_unanticipated | assumption_anticipated |
| A20 | sphinx-doc__sphinx-9234 | b_anticipated | b_unanticipated | assumption_anticipated |
| A21 | sympy__sympy-12428 | b_anticipated | c_evidence_reading | predicted_supported |
| A23 | sympy__sympy-13840 | d_oracle_scope | u_undeterminable | divergence_kind, oracle_basis |

## 노출ㆍ근거 점검과 해석 한계

- setb: c2 노출 기록 15행; 근거 field 경로 159개 연결, 세부 qualifier 경고 0개.
- setb 수용 기록: Prior familiarity disclosed in 15 of 22 exposure_note fields: later upstream releases, code, documentation, or behavior were recalled. The expert states these sources were not consulted during coding and all fields use the supplied worklist. All 22 rows are retained; this is an exposure limitation, not evidence of a clean no-prior-exposure pass.
- setb 수용 기록: Owner-confirmed expert authorship and wording correction on 2026-10-19 are documented in docs/decisions/README.md. Only 15 exposure_note fields changed; codes, evidence_refs, coder_note, and row linkage are unchanged. The pre-correction return is preserved in commit 0d64d69 with SHA-256 5ba85ab471669c27d5dfdfcc5aec70cc90fa8cdf1a1caff9449f430e2becc212.
- seta: c2 노출 기록 4행; 근거 field 경로 238개 연결, 세부 qualifier 경고 1개.
- seta 수용 기록: Four exposure notes (A09, A10, A14, A18) disclose incidental exposure inside the supplied frozen worklist: construct-validity rationales paraphrase SWE-bench hints (three rows) or allude to post-hoc maintainer discussion (one row). The expert states these references were not used for coding. All 23 rows are retained; this is inherited worklist contamination, not a report of external retrieval during coding.
- seta 수용 기록: All 238 evidence field paths resolve to non-empty supplied worklist values. Of 34 test-qualified pointers, A22 oracle.test_patch:TestPandasIndex.test_from_variables has a matching test method but the class qualifier is absent from patch context; exact class attribution is unverified. The original pointer is preserved unchanged.

Set A의 예상된 가정/미예상 계약 선택 구분과 근거 판독ㆍ판별 불가 분류는 전문가 판정 전이다. Set B의 유형 일치만으로 Set A의 기존 분포를 검증 완료로 간주하지 않는다.
사전 기억과 제공 기록 안의 금지 자료 언급이 미친 영향은 확인되지 않았다. 기존 primary labelㆍprevalenceㆍconstruct-validity 수치는 변경하지 않는다.

## 재현

입력 SHA-256, 비교 행, 혼동행렬, field별 결과는 동명 JSONㆍrows JSONL에 있다.

```bash
uv run python scripts/analyze_repo480_rre_verification.py --analyzed-on 2026-10-19
```
