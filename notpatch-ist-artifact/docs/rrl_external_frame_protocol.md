# RR-L External-Frame Sensitivity Protocol

- **Status:** `frozen-before-sampling` (v1, 2026-10-21)
- **Authority:** RR-L 실행의 frameㆍ표집ㆍevidence contract 적용ㆍ전문가 패널ㆍ사전 고정 분석 규칙(R1–R3). 후보 비교와 선택 근거는 `docs/external_validity_design.md`, 진행 상태는 `docs/status.md`, claim boundary는 `docs/roadmap.md`가 소유한다
- **Last verified:** 2026-10-21
- **Packet policy ID:** `swebench-live-lite-ext120-v1`
- **Frame ID:** `swebench-live-lite-b51a8642-random-120-seed-20261021`
- **Annotation batch:** `rrl_ext120_available_v1`

## 1. 지위

2026-10-21 owner가 설계 문서의 선택지 A를 승인했다(`docs/status.md` owner 결정 6). 이 문서는 그 실행
계약이며 표집, materialization, 전문가 반환보다 먼저 commit한다. 이후 이 파일은 고치지 않는다. 예상하지
못한 상황은 결과 문서와 `docs/status.md`에 deviation으로 기록한다. 이 문서의 SHA-256은 frame manifest와
패널 setup manifest에 남긴다. 로컬 git 기록이며 공개 registry가 아니므로 원고에서는 "prespecified"로 쓴다.

RR-L은 RQ1 측정 protocol의 sensitivity다. 같은 evidence contract가 다른 Python frame에서 (1) 그대로
materialize되는지, (2) 전문가가 retrieval을 불충분하다고 보는 비율이 크게 다른지, (3) 독립 raw pass의
boundary 일치가 크게 낮아지는지를 본다. 새 RQ나 contribution이 아니며, 이 frame의 P2/P3 비율은 보조
기술치다. Canonical repo480 label, `26/480`, `0.094`, RQ2 결과는 바꾸지 않는다.

## 2. Frame과 표집

- **Source.** `SWE-bench-Live/SWE-bench-Live`의 `lite` split, revision
  `b51a86422e10cfd403beb4773e5a2947953e36ec`의 `data/lite-00000-of-00001.parquet`. 이 revision에서 받은
  파일의 SHA-256이 Hub의 LFS object id와 같아야 한다. 다른 split과 이후 revision은 섞지 않는다.
- **적격 기준.** Repo480 sampler와 같이 `instance_id`, `repo`, `base_commit`, `problem_statement`,
  `created_at`이 비어 있지 않은 문자열이어야 한다. 부적격 행은 사유와 건수로 보고한다.
- **순위.** 전체 행을 `instance_id` 오름차순으로 정렬한 뒤 Python `random.Random(20261021).shuffle`로 섞고
  위치를 random rank(1부터)로 쓴다. Repo480 sampler(seed `20260617`)와 같은 알고리즘이며 seed는 동결일을
  따른다.
- **표본.** Rank 순서로 적격 행 첫 120개를 고른다(`prevalence_random_first_eligible`). 나머지 적격 행의
  rank는 reserve로 기록만 한다. 구조적 부적격 외의 이유(materialization 실패, 판정 불가)로 행을 대체하지
  않는다.
- **Coordinator 전용 확인.** `pull_number`가 `instance_id` 끝 번호와 같은지 확인한다. 다르면 행을 고치지
  않고 frame manifest에 기록한다. `pull_number`, `issue_numbers`, `created_at`은 확인용 metadata이며
  전문가에게 보이지 않는다.
- **층 표시.** SWE-bench의 12개 repository에서 온 행을 표시해 층별로 기술한다. 표집에는 쓰지 않는다.

## 3. Evidence contract와 materialization

- Component 경계는 `swebench-repo480-v1`과 같다. Issue packet은 `benchmark_defined`(비어 있지 않은 첫 줄이
  title), repository는 exact `base_commit`, public conversation/link는 fix PR(`instance_id` 끝 번호)이 열린
  시각을 경계로 하는 `pre_fix_pr_opened`이다. Public comment는 source issue identity를 검증하지 않으므로
  unavailable로 남고 link 처리도 repo480과 같다.
- Retrieval은 `lexical-bm25-v1`과 parameter SHA-256
  `5e3218e7b98bc44bbf3c15f7b312c124eadcacd0f35e2eaedcd861895d096c15`를 그대로 쓴다. Frozen path
  classifier, category quota 12/8/5/5, 1 MiB blob 제한, 64 KiB 발췌, 1.5 MiB packet budget을 바꾸지
  않는다. Materializer에는 위 packet policy IDㆍframe ID만 인자로 주며, 기본값으로 실행한 repo480 산출물이
  byte 단위로 같음을 test로 고정한다.
- Materializer는 row에서 `instance_id`, `repo`, `base_commit`, `problem_statement`만 읽는다. `patch`,
  `test_patch`, `FAIL_TO_PASS`, `PASS_TO_PASS`, `hints_text`, `all_hints_text`, `commit_url`, `commit_urls`,
  `test_cmds`, `log_parser`, `difficulty`, `pull_number`, `issue_numbers`, `created_at`은 packet, worklist,
  전문가 파일에 넣지 않는다.
- Gate는 repo480과 같다. 온라인 실행으로 Git과 GitHub metadata cache를 채우고, 그 metadata를 유지한 채 빈
  Git object cache에서 clean packet을 만든 뒤 offline replay와 byte 단위로 비교한다. Validator의 frame
  identity, schema, hash, leakage scan, denylist negative control, issue/base-commit positive control을 모두
  통과해야 manifest를 동결한다.
- **실패.** Materialization 오류가 난 task는 단계와 오류 유형을 applicability 기록에 남기고 패널에서 빼되
  대체하지 않으며 R1 분모에 남긴다. Task를 통과시키려고 contract를 바꾸지 않는다. Fix PR 시각을 검증하지
  못한 packet은 실패가 아니라 repo480과 같은 `unverified` 상태다.

## 4. 전문가 패널

- `rrl_ext120_r1`, `rrl_ext120_r2`는 독립 available-only raw pass, `rrl_ext120_adj`는 판정자다. 세 role은
  서로 다른 전문가이고 Python repository 검토 가능성이 배정 조건이다. 기존 role과 겹치는 것은 금지하지 않고
  `docs/annotator_registry.md`에 기록한다(RR-K 입력).
- 각 raw role은 자기 폴더와 공유 reviewer-view archive만 받는다. Guideline v0.5 byte 사본과 RR-A
  (`repo480_boundary_validation_v1`)와 같은 worklist field 규칙ㆍselfcheck를 쓰고, 행마다 `protocol_deviation`에
  사전 기억이나 금지 자료 노출을 적는다. GitHubㆍweb 조회, repository checkout, fix PR, test, 상대 pass는
  금지한다. Task ID에 PR 번호가 남는 것은 repo480과 같으며 조회 금지 규칙으로 관리한다.
- 제시 순서는 표본의 random rank 순서다. SWE-bench repository 층 표시는 package에 넣지 않는다.
- 두 raw 반환을 원문 그대로 보존한 뒤 controlled field(binary boundary, `primary_label`, `primary_blocker`,
  `data_quality`, `predicted_direction` 문구. P0-3ㆍRR-A와 같은 축)가 하나라도 다른 행을 모두 판정자에게
  보낸다. 판정자는 두 raw label과 같은 reviewer view를 보고 base annotator와 override를 정한다. Controlled
  field가 모두 같은 행은 `rrl_ext120_r1` 값을 쓴다. 이 결과를 판정 후 label이라 부른다.
- 빈 template은 결과가 아니다. 반환은 byte 그대로 canonical 사본과 returns manifest로 받으며 AI 출력으로
  전문가 반환을 대신하지 않는다.

## 5. 사전 고정 분석

`N = 120`은 표본 행, `L`은 materialize되어 패널에 들어간 행이다. 두 raw pass는 `L`행을 모두 label해야
반환이 완료된다. 구간은 Wilson 95%(z = 1.959964)다.

| 규칙 | 지표 | 보고 판정 |
| --- | --- | --- |
| R1 applicability | 실패 task 수와 사유(분모 `N`), packet status, evidence category별 status, fix PR 시각 검증 상태, frame 수준 classifier 적합성(probe) | 기술 보고. 실패 행은 대체하지 않는다 |
| R2 retrieval failure | 판정 후 `retrieval_sufficiency`가 `insufficient` 또는 `unclear`인 비율(분모 `L`)과 raw pass별 비율 | 판정 후 구간의 하한이 repo480 `100/480` 구간 `[0.1744, 0.2469]`의 상한보다 크면 "frozen retrieval policy의 전이가 약하다"고 보고한다. 아니면 "이 표본 크기에서 큰 차이는 관찰되지 않았다"고만 쓰며 동등성을 주장하지 않는다 |
| R3 reproducibility | 두 raw pass의 binary(P0/P1 대 P2/P3) 일치 비율(분모 `L`), Cohen κ, PABAK, exact P0–P3 일치, binary 불일치 방향 | 일치 구간의 상한이 repo480 `430/480` 구간 `[0.8653, 0.9201]`의 하한보다 작으면 "외부 frame에서 raw 재현성이 낮다"고 보고한다. 아니면 큰 하락이 관찰되지 않았다고만 쓴다. κ는 보고하되 판정 통계로 쓰지 않는다 |

- **보조.** 판정 후 P2/P3 비율(분모 `L`)의 Wilson 구간과 repository cluster bootstrap(10,000회, seed
  `20261021`), raw pass별 P2/P3 marginal. 이 frame의 고유값으로만 보고하며 `26/480`ㆍ`0.094`와 합치거나
  일반 APR prevalence로 읽지 않는다.
- **Sensitivity.** 실패 task를 retrieval 실패로 센 R2(분모 `N`), `protocol_deviation` 행 제외, Q0 행만,
  SWE-bench repository 층과 그 밖의 층. 모두 기술치다.
- **정밀도.** `L = 120`이면 R2는 비율이 약 `40/120 = 0.333` 이상일 때, R3는 일치가 약
  `96/120 = 0.800` 이하일 때만 성립한다. 두 규칙은 약 10%p 이상의 큰 차이를 보는 경계 점검이며 동등성
  검정이 아니다.

## 6. Claim boundary

- 결과는 추가 Python frame 하나에서 본 RQ1 측정 protocol의 sensitivity다. 다른 benchmark, 다른 언어,
  APR 전반으로 일반화하지 않는다.
- SWE-bench-Live 자체의 build 가능성ㆍtest 실행 가능성 선택은 그대로 남는다. 표본 일부는 SWE-bench
  repository에서 왔다.
- 전문가 반환을 받지 못하면 R1만 보고하고 R2ㆍR3는 미측정으로 둔다. 그때는 설계 문서 §5의 D claim audit을
  적용한다.
