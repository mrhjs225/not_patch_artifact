# RR-L 외부 frame sensitivity 분석

- **Status:** `external-frame-sensitivity`
- **Authority:** RR-L(SWE-bench-Live lite 120행)의 사전 고정 R1–R3, 보조 P2/P3, sensitivity 결과. 규칙은 `docs/rrl_external_frame_protocol.md` §5, claim boundary는 `docs/roadmap.md`가 소유한다
- **Last verified:** 2026-10-26

## 설계와 입력

SWE-bench-Live lite(revision `b51a8642`)에서 seed `20261021`로 뽑은 첫 적격 120행에 repo480과 같은 evidence contract(packet policy `swebench-live-lite-ext120-v1`)를 적용했다. 서로 다른 전문가 두 명이 같은 frozen reviewer view로 독립 available-only raw pass를 했고, 세 번째 전문가가 controlled field가 다른 119행을 판정했다. 판정 규칙과 아래 분석은 반환 전에 동결했다. 반환 수용 기록은 `data/manifests/generated/rrl_ext120_returns_manifest_v1.json`, 행별 값은 `results/pilot/rrl_ext120_external_frame_rows_v1.jsonl`이다. 제외한 행은 없다(`N = 120`, `L = 120`).

## 사전 고정 규칙 결과

| 규칙 | RR-L 값 | Repo480 기준 | 판정 |
| --- | --- | --- | --- |
| R1 applicability | materialization 실패 0/120, packet ready_with_unavailable 120 | — | 기술 보고 |
| R2 판정 후 retrieval insufficient/unclear | 41/120 (0.342; Wilson 95% [0.263, 0.430]) | 100/480 [0.1744, 0.2469] | 충족 |
| R3 raw binary 일치 | 104/120 (0.867; Wilson 95% [0.794, 0.916]) | 430/480 [0.8653, 0.9201] | 미충족 |

### R1 applicability

- 120행 모두 materialize됐고 상태는 `ready_with_unavailable` 120행이다. 대체한 행은 없다.
- Evidence category 상태: `issue_packet` materialized 120; `repository_inventory` materialized 120; `retrieved_code` materialized 120; `visible_tests` materialized 120; `docs` materialized 120; `configs` materialized 120; `linked_artifacts` empty 61, materialized 6, unavailable 53; `public_comments_until_cutoff` unavailable 120.
- Fix PR 시각 검증: unverified 10, verified 110. Unverified 행은 repository 조직 이관 때문이며(`iterative/dvc` 1, `koxudaxi/datamodel-code-generator` 3, `projectmesa/mesa` 3, `pytorch/torchtune` 3) protocol대로 실패가 아니다.
- 표본은 52개 repository에서 왔고 SWE-bench repository 행은 13개다.
- Frame 수준 classifier 적합성(probe): SWE-bench-Live lite 300행의 test 경로 577/617 (0.935)를 인식했고 test 경로를 하나도 인식하지 못한 task는 0/300개다. Repo480 원천 draw는 926/926이다.

### R2 retrieval failure

- 판정 후: 41/120 (0.342; Wilson 95% [0.263, 0.430]). 하한이 repo480 구간 상한 0.2469보다 크다. **사전 규칙 충족: frozen retrieval policy의 전이가 약하다.**
- Raw pass별: r1 44/120 (0.367; Wilson 95% [0.286, 0.456]), r2 28/120 (0.233; Wilson 95% [0.167, 0.317]).
- 해석상 주의: `retrieval_sufficiency`는 controlled field가 아니어서 판정자가 한 번도 override하지 않았다(override 0건). 판정 후 값은 base annotator의 raw 값이며 base는 r1 87행ㆍr2 33행이다. 두 raw pass가 모두 표시한 행은 27/120 (0.225; Wilson 95% [0.159, 0.308]), 한쪽이라도 표시한 행은 45/120 (0.375; Wilson 95% [0.294, 0.464])다(사후 기술). R2는 전문가가 packet의 retrieval을 불충분하다고 판단한 비율이며 packet이 어떤 근거를 실제로 놓쳤는지 직접 측정한 값이 아니다.
- 경계 근접성: 사전 규칙을 r2 raw pass(미충족)나 두 pass 공통 표시(미충족)에 적용하면 결론이 달라진다. 아래 sensitivity 표의 "R2 규칙" 열도 함께 읽는다.

### R3 reproducibility

- Raw binary 일치: 104/120 (0.867; Wilson 95% [0.794, 0.916]). 상한이 repo480 구간 하한 0.8653보다 작지 않다. 사전 규칙 미충족: 큰 하락이 관찰되지 않았다(동등성 주장 아님).
- Cohen κ 0.457(판정 통계 아님), PABAK 0.733, exact P0–P3 일치 68/120 (0.567; Wilson 95% [0.477, 0.652]).
- Binary 불일치 방향: r1만 P2/P3 12행, r2만 P2/P3 4행.

| r1 \ r2 | P0 | P1 | P2 | P3 |
| --- | ---: | ---: | ---: | ---: |
| P0 | 23 | 6 | 0 | 0 |
| P1 | 29 | 37 | 4 | 0 |
| P2 | 1 | 11 | 5 | 0 |
| P3 | 0 | 0 | 1 | 3 |

## 보조: 판정 후 P2/P3

- 판정 후 P2/P3: 19/120 (0.158; Wilson 95% [0.104, 0.234]); repository cluster bootstrap(52개 repository, 10,000회, seed `20261021`) 95% [0.083, 0.240].
- Raw marginal: r1 21/120 (0.175; Wilson 95% [0.117, 0.253]), r2 13/120 (0.108; Wilson 95% [0.064, 0.177]).
- 판정 후 label: P0 42, P1 59, P2 15, P3 4; data quality: Q0 108, Q2 12.
- 이 비율은 이 frame의 고유 기술치다. `26/480`ㆍ`0.094`와 합치거나 비교 검정하지 않고 일반 APR prevalence로 읽지 않는다.

## Sensitivity(기술치)

- 실패 task를 retrieval 실패로 센 R2(분모 `N`): 41/120 (0.342; Wilson 95% [0.263, 0.430]). 실패가 없어 주 결과와 같다.

| Subset | n | R2 판정 후 flagged | R2 규칙 | R3 raw binary 일치 | R3 규칙 | 판정 후 P2/P3 |
| --- | ---: | --- | --- | --- | --- | --- |
| raw `protocol_deviation` 행 제외 | 107 | 36/107 (0.336; Wilson 95% [0.254, 0.430]) | 충족 | 93/107 (0.869; Wilson 95% [0.792, 0.920]) | 미충족 | 14/107 (0.131; Wilson 95% [0.080, 0.208]) |
| raw 또는 판정 `protocol_deviation` 행 제외 | 94 | 31/94 (0.330; Wilson 95% [0.243, 0.430]) | 미충족 | 85/94 (0.904; Wilson 95% [0.828, 0.949]) | 미충족 | 10/94 (0.106; Wilson 95% [0.059, 0.185]) |
| 판정 후 Q0만 | 108 | 36/108 (0.333; Wilson 95% [0.252, 0.427]) | 충족 | 98/108 (0.907; Wilson 95% [0.838, 0.949]) | 미충족 | 11/108 (0.102; Wilson 95% [0.058, 0.173]) |
| SWE-bench repository 층 | 13 | 7/13 (0.538; Wilson 95% [0.291, 0.768]) | 충족 | 11/13 (0.846; Wilson 95% [0.578, 0.957]) | 미충족 | 2/13 (0.154; Wilson 95% [0.043, 0.422]) |
| 그 밖의 repository 층 | 107 | 34/107 (0.318; Wilson 95% [0.237, 0.411]) | 미충족 | 93/107 (0.869; Wilson 95% [0.792, 0.920]) | 미충족 | 17/107 (0.159; Wilson 95% [0.102, 0.240]) |

층별 행은 분모가 작아(SWE-bench repository 층 13행) 규칙 열을 판정으로 읽지 않는다.

`protocol_deviation`은 r1 13행ㆍr2 0행ㆍ판정 25행이며 모두 사전 노출(이슈의 이후 해결을 기억함) 기록이다. Protocol 문언이 raw 이탈만 뺄지 판정 이탈까지 뺄지 정하지 않으므로 두 변형을 모두 보고한다.

## 사후 기술(사전 고정 아님)

- Raw retrieval 표시 교차: r1_sufficient|r2_sufficient 75, r1_sufficient|r2_flagged 1, r1_flagged|r2_sufficient 17, r1_flagged|r2_flagged 27.
- 판정 후 retrieval 표시와 binary label: P0/P1 insufficient 19, sufficient 67, unclear 15; P2/P3 insufficient 5, sufficient 12, unclear 2.
- 참고로 repo480 raw pass의 retrieval 표시율은 r1 68/480 (0.142; Wilson 95% [0.113, 0.176]), r2 117/480 (0.244; Wilson 95% [0.207, 0.284])였다. 두 frame의 raw role은 다른 전문가이므로 번호끼리 짝지어 비교하지 않는다.
- Repository evidence(code, test, docs, config)를 근거로 기록한 raw 행: r1 120/120, r2 119/120. RR-A의 issue-text-only pass와 달리 두 pass 모두 repository evidence를 사용했다.

## 해석

- **Contract 적용 가능성(R1).** 같은 evidence contract가 52개 repository의 120 task 모두에서 실패 없이 packet을 만들었다. 다만 frozen classifier는 이 frame의 test 경로를 repo480보다 덜 인식했다(0.935 대 1.000).
- **Retrieval 전이(R2).** 사전 규칙상 frozen retrieval policy의 전이가 약하다는 결과가 나왔다(0.342 대 repo480 0.208). 그러나 이 판정은 경계에 가깝다. 하한과 기준 상한의 차이는 0.016에 그치고, raw pass 한쪽과 일부 sensitivity에서는 규칙이 성립하지 않는다. 또 retrieval 불충분 표시 41행 중 34행은 P0/P1로 판정됐고, 표시율은 P0/P1(34/101)과 P2/P3(7/19)에서 비슷했다(사후 기술). 즉 이 frame에서 전문가는 packet 밖 맥락을 더 자주 원했지만, 그 표시가 P2/P3 판정과 함께 움직이지는 않았다.
- **Raw 재현성(R3).** Binary 일치(0.867)는 repo480 0.896보다 낮지만 사전 규칙이 정한 큰 하락은 아니다. κ(0.457)가 낮은 것은 P2/P3 비율이 낮을 때 κ가 작아지는 성질과 함께 읽어야 한다(PABAK 0.733). 불일치는 r1이 더 자주 P2/P3를 준 방향으로 기울었다(12 대 4). Exact P0–P3 일치는 0.567이며, 4-class 불일치 52행 중 35행이 P0와 P1 사이에서 일어났다.
- **보조 P2/P3.** 이 frame의 판정 후 P2/P3는 0.158이며 frame 고유 기술치다.

## 수용 기록과 한계

- Owner confirmation on 2026-10-26: each raw return (rrl_ext120_r1, rrl_ext120_r2) and the adjudication return (rrl_ext120_adj) was first drafted by an AI assistant and then reviewed and finalized by an expert; the owner confirms these are expert returns. The repository holds the blank packages (commit f78b45b) and the final returns (commit 74fc79e) only; pre-review AI drafts and the extent of expert edits are not preserved.
- Whether the three roles were finalized by three distinct experts, any overlap with earlier annotation roles, and whether the two raw drafts came from separate AI sessions or models are not yet recorded; they are RR-K inputs and bound the interpretation of R3 raw agreement.
- Order deviation from protocol section 4: the adjudication package was built from the request-folder copies before this canonical acceptance, with a worklist builder and validator written outside the repository generators. The adjudicator manifest pins both raw returns at the SHA-256 of the canonical copies accepted here, and acceptance recomputes the adjudication worklist and post-adjudication labels from those copies with the byte-identical validator scripts/selfcheck_rrl_ext120_adjudication_return.py.
- Prior-exposure protocol_deviation notes (rrl_ext120_r1 13 rows, rrl_ext120_r2 none, rrl_ext120_adj 25 decisions) are kept verbatim and are not exclusions at acceptance; protocol section 5 defines the protocol_deviation sensitivity.
- 수용 뒤 owner가 세 role을 서로 다른 전문가가 확정했음을 확인했고, 두 raw 초안의 AI 분리 여부는 전문가 재검토를 거쳤으므로 R3에 영향이 없다고 판단했다(`docs/decisions/README.md`).
- One additional Python frame (SWE-bench-Live lite, revision b51a8642, 120 rows from 52 repositories) under the same evidence contract; no generalization to other benchmarks, languages, or APR at large.
- R2 and R3 are boundary checks for differences of roughly ten percentage points, not equivalence tests.
- retrieval_sufficiency is not a controlled field: the adjudicator never overrode it, so the post-adjudication value is the base annotator's raw value, and the raw passes differ in how often they flag retrieval.
- The post-adjudication P2/P3 share is a frame-specific descriptive value; it is not combined with 26/480 or 0.094 and is not an APR prevalence.
- SWE-bench-Live keeps its own buildability and test-executability selection, and 13 sampled rows come from SWE-bench repositories.
- Repo480 canonical labels, 26/480, 0.094, 12/12 and 10/12 are unchanged.

입력 hash와 전체 수치는 동명 JSON에 있다.

```bash
uv run python scripts/analyze_rrl_ext120_panel.py --analyzed-on 2026-10-26
```
