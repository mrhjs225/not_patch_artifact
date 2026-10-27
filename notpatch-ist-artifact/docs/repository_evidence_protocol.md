# Repository Evidence Materialization Protocol v1.0

- **Status:** `frozen-for-materialization`
- **Authority:** 480-task repository-evidence estimand, cutoff, retrieval, packet, failure, and deviation contract
- **Protocol ID:** `swebench-repo480-v1`
- **Frozen:** 2026-07-14, before P0-2 materialization and P0-3 relabel
- **Last verified:** 2026-10-13 (2026-10-13 erratum: §2, §3.1, §5, §6, §8)

이 문서는 2026-07-14 리뷰 종합의 M1(evidence-contract closure)과 M6(provenance 보고)을 반영해
repository-level claim을 다시 열기 위한 evidence contract를 고정한다. 리뷰 종합 원문
`reviews/review_reviews-synthesis_2026-07-14.md`는 commit `51dbf20`(2026-08-18)에서 삭제되었으므로
`git show c00eb1c:reviews/review_reviews-synthesis_2026-07-14.md`로 읽고, 현재 evidence stateㆍclaim
boundary는 `docs/roadmap.md` §2를 따른다. 기존
`swebench_full_prevalence_random_480.jsonl`은 issue title/body만 materialize한
`issue-packet` baseline이다. 새 primary 분석은 같은 480-task random frame에 이 문서의
repository evidence를 추가한 별도 packet과 별도 label을 사용한다.

> **Post-freeze digest addendum (2026-08-18):** 이 protocol의 기존 packet/hash를 소급
> 변경하지 않는다. 다른 수집 시각의 독립 재materialization은
> `docs/repository_evidence_digest_protocol.md`의 `repo480-evidence-boundary-v1` projection으로
> evidence-semantic equality를 추가 검증한다.
>
> **External-frame addendum (2026-10-21):** RR-L은 이 contract의 규칙과 retrieval parameter를 그대로 다른
> frame에 적용하며 packet policy ID(`swebench-live-lite-ext120-v1`)와 frame ID만 바꾼다
> (`docs/rrl_external_frame_protocol.md`). Materializer의 기본 ID는 이 문서의 값이고, 기본값으로 실행한
> frozen repo480 packet의 hash가 그대로 재현됨을 `tests/test_repository_evidence.py`가 고정한다.

## 1. Primary estimand와 분석 단위

- **Population frame:** 기존 nested random frame의 480개 SWE-bench full test instance.
  Task membership, random rank, seed, structural exclusion은 바꾸지 않는다.
- **Unit:** 하나의 `(task_id, base_commit, packet_policy_id)`.
- **Primary evidence policy:** benchmark가 제공한 problem statement, `base_commit`의
  repository tree, 그 tree에서 oracle-free deterministic retrieval로 고른 code/tests/docs/
  config, cutoff-valid public comments와 직접 링크 artifact.
- **RQ1 estimand:** `swebench-repo480-v1` packet policy에서 adjudicated P2/P3가 되는 480-frame
  task의 비율. 이는 broad APR population prevalence나 unconstrained repository exploration의
  비율이 아니다.
- **RQ2 denominator:** 위 label 중 benchmark-solvable P2/P3. Solvability와 oracle evidence는
  available-only label이 동결된 뒤에만 결합한다.

Repository snapshot 전체를 임의로 탐색하게 두지 않고, exact tree inventory와 frozen
retrieval slice를 함께 제공한다. 따라서 paper-facing 표현은 **repository-level repair frame
under a frozen task-time retrieval policy**로 제한한다. 기존 seed label은 transition 분석의
left-hand baseline일 뿐 새 reviewer packet, retrieval query, adjudication 입력에 포함하지 않는다.

## 2. Composite evidence boundary

SWE-bench task는 하나의 timestamp만으로 issue와 repository를 동시에 표현할 수 없으므로
boundary를 다음 세 component로 분리한다.

| Component | Primary boundary | 포함 조건 |
| --- | --- | --- |
| Benchmark issue packet | `benchmark_defined` | source snapshot의 problem statement를 byte-preserving text로 저장 |
| Repository snapshot | `base_commit` | manifest SHA가 실제 commit object이고 tree를 읽을 수 있으며, 모든 repository item이 이 tree의 blob임 |
| Public conversation/link | `pre_fix_pr_opened` | fix PR open timestamp가 source metadata로 검증되고 artifact의 생성·마지막 수정 시각이 cutoff 이하임 |

현재 bundle의 `issue_created_at`은 원천 `created_at`을 복사한 필드이므로 실제 issue creation
time이라고 가정하지 않는다. P0-2는 `cutoff_source`, `cutoff_source_field`,
`cutoff_verified_at`, `cutoff_verification_status`를 기록한다. Fix PR open cutoff를 검증하지
못한 task는 public comment/link 본문을 primary packet에 넣지 않고 category를
`unavailable:cutoff_unverifiable`로 기록한다. 이 누락을 issue 없음이나 substantive
underspecification으로 자동 해석하지 않는다.

> **Erratum (2026-10-13):** v1 구현은 source issue identity를 해석하지 않으므로 public comment를
> 구조적으로 수집하지 않는다(`src/notpatch/evidence/repository.py`의 `_materialize_public_metadata`).
> Canonical 480 packet에서 fix-PR-open cutoff는 480/480 `verified`이지만
> `public_comments_until_cutoff`는 480/480 `unavailable:source_identity_unverified`이고 comment item은
> 0건이다. 위 `unavailable:cutoff_unverifiable` 규칙은 cutoff를 검증하지 못한 경우의 분기로 남아
> 있으나 v1에서는 발생하지 않았다(0/480). 따라서 annotator가 cutoff 이전 comment를 보았다고
> 서술하지 않는다. Link category의 `cutoff_unverifiable`은 다른 의미다(§3.1 erratum). 근거:
> `data/manifests/generated/swebench_repo480_materialization_manifest_v1.json`
> (`public_cutoff_verification_status`), `results/pilot/swebench_repo480_materialization_validation.md`.

`base_commit` tree는 benchmark가 agent에게 제공하는 immutable repository state이므로
conversation cutoff와 별도로 포함한다. Commit author/committer time으로 file-level cutoff를
추정하거나 working tree, default branch HEAD, fix commit의 file을 섞지 않는다.

## 3. Evidence allowlist와 oracle denylist

### 3.1 Available-only allowlist

- benchmark problem statement
- source issue의 cutoff-valid public comments; issue identity와 timestamp를 검증할 수 있을 때만
- `base_commit` tree의 tracked regular text blobs
- 위 blob에서 분류한 source code, visible tests, docs/examples, config/dependency manifests
- problem statement 또는 포함된 comment가 직접 가리킨 depth-1 public artifact
- 각 item의 source locator, commit/timestamp, retrieval reason, content hash, truncation metadata

Linked artifact는 public/no-login/no-secret이어야 한다. GitHub issue/PR 본문은
`created_at <= cutoff`와 `updated_at <= cutoff`를 모두 만족할 때만 포함하고, comment는 각
comment의 `created_at`과 `updated_at`을 같은 방식으로 검사한다. Edit history를 복원할 수
없고 `updated_at > cutoff`이면 현재 본문을 사용하지 않는다. Link traversal은 depth 1에서
끝내며 linked page 안의 추가 link를 재귀적으로 수집하지 않는다.

> **Erratum (2026-10-13):** v1의 link 처리 범위는 위 서술보다 좁다(`_materialize_public_metadata`).
>
> | v1 처리 | Link 단위 기록 (`failure_audit`, `excluded_evidence`) | Canonical 480 packet 건수 |
> | --- | --- | --- |
> | URL은 benchmark problem statement 전체 텍스트에서만 추출한다. 포함된 comment가 없으므로 comment 안의 link는 없다. | — | — |
> | `https?://github.com/<owner>/<repo>/(issues\|pull)/<n>` 형식이 아닌 URL(문서 page, `blob`ㆍcommit link, 이미지, 외부 site 등)은 timestamp를 검증할 경로가 없다. | `cutoff_unverifiable` | link 378건 전부; packet 단위 `linked_artifacts` 185건 |
> | GitHub issue/PR URL 중 API 응답이 200이 아닌 것 | `not_found` | link 4건 |
> | `updated_at > cutoff` | `edit_history_unavailable` | link 25건; packet 단위 10건 |
> | `created_at > cutoff` | `excluded_evidence: created_after_cutoff` | 0건 |
> | 같은 repository의 fix PR을 직접 가리키는 link | `excluded_evidence: solution_revealing_fix_pr_denylist` | 4건 |
> | 나머지 GitHub issue/PR은 title+body만 포함한다(comment는 수집하지 않음). | item `kind = linked_issue\|linked_pr` | 23 packet, 25 item |
>
> 따라서 link의 `cutoff_unverifiable`은 task cutoff 실패가 아니라 "GitHub issue/PR이 아닌 URL"을
> 뜻한다. Packet 단위 상태 집계 규칙은 `docs/task_schema.md` §4 erratum에 있다.

### 3.2 Available-only denylist

다음 값은 collector가 cutoff 검증 또는 별도 oracle artifact 생성에 사용할 수는 있지만,
available packet, retrieval query, rank feature, reviewer worklist에는 절대 넣지 않는다.

- `patch`, `test_patch`, `FAIL_TO_PASS`, `PASS_TO_PASS`, `hints_text`
- ground-truth changed-file path, fix commit diff, solution-revealing fix PR content
- hidden/generated test, benchmark packaging note, environment setup oracle
- post-cutoff maintainer discussion과 linked artifact revision
- public agent outcome, generated patch, detector/judge score
- 기존 raw/adjudicated label, oracle-gap field, broad-link recoding 결과

Fix PR identifier와 open timestamp는 cutoff enforcement metadata로만 별도 보관하고 reviewer
packet에서 숨긴다. Denylist field를 제거한 뒤 retrieval을 수행해야 하며, 나중에 결과에서
문자열을 지우는 방식은 허용하지 않는다.

## 4. Repository snapshot과 file inventory

각 task에서 materializer는 다음 순서를 따른다.

1. manifest의 `repo`와 `base_commit`을 읽고 pinned repository cache를 준비한다.
2. `base_commit^{commit}` object 존재와 expected repository remote를 검증한다.
3. `git ls-tree -r -z --full-tree <base_commit>`에 해당하는 tree inventory를 만든다.
4. mode `100644`/`100755` regular blob만 retrieval corpus 후보로 둔다. Symlink, submodule,
   binary blob은 inventory에는 남기되 본문 corpus에서 제외한다.
5. UTF-8 strict decode에 성공하고 NUL byte가 없으며 1 MiB 이하인 blob을 text corpus로 둔다.
   그 외 item은 `binary`, `decode_failed`, `oversize` reason과 blob hash/size만 기록한다.

Inventory item은 최소 `path`, `git_mode`, `git_blob_sha`, `size_bytes`, `media_class`,
`evidence_category`, `corpus_status`를 갖는다. Path는 POSIX form으로 정규화하고 bytewise
ascending order로 저장한다. Working tree checkout 결과나 file modification time은
provenance로 사용하지 않는다.

Category 분류 우선순위는 `visible_tests > docs > configs > retrieved_code`이다.

- `visible_tests`: path component `test`/`tests`, `test_*`, `*_test`, repository의 명시적 test tree
- `docs`: `doc`/`docs` tree, README, changelog, example/tutorial 문서
- `configs`: build/package/dependency/CI/tool config의 고정 basename 또는 config extension
- `retrieved_code`: 위 세 category가 아닌 regular text source

P0-2 구현은 고정 basename/extension 목록을 versioned constant로 노출하고 run artifact에
그 목록의 hash를 기록한다.

## 5. Deterministic retrieval policy

`retrieval_algorithm_id = lexical-bm25-v1`로 고정한다.

1. Query는 problem statement와 cutoff-valid comment/link 본문에서만 만든다. Title token은
   3회, 나머지 text token은 1회 사용한다.
2. Tokenizer는 ASCII case-fold 후
   `[A-Za-z_][A-Za-z0-9_./:-]*|[0-9]+`를 추출하고 snake/camel/path separator 경계 token을
   추가한다. P0-2가 고정 stop-word list를 쓰면 그 list와 hash를 run artifact에 기록한다.
3. Corpus unit은 file이다. File path token을 content token에 3회 추가하고 BM25
   `k1=1.2`, `b=0.75`로 category 안에서 rank한다.
4. Problem statement에 literal repository path가 있으면 그 exact path를 category quota 안에
   강제 포함한다. Oracle changed-file path는 이 단계에 전달하지 않는다.
5. 각 category에서 `retrieved_code=12`, `visible_tests=8`, `docs=5`, `configs=5`까지 고른다.
   동점은 normalized path ascending으로 푼다. Candidate가 없으면 빈 배열을 만들고
   `empty:no_candidate_text_blob`를 기록한다.
6. Selected file이 64 KiB 이하면 전문을 저장한다. 더 크면 query-token hit가 많은 line을
   중심으로 겹치지 않는 ±80-line window를 path/line 순으로 선택해 64 KiB까지 저장한다.
   Hit가 없으면 앞 64 KiB를 사용한다. `content_truncated`, original byte size, line range,
   full blob hash를 반드시 기록한다.

Packet당 repository excerpt budget은 1.5 MiB이다. Category quota 선택 뒤 budget을 넘으면
category별 최소 1개를 보존한 상태에서 BM25 rank가 낮은 item부터 제거하고
`budget_excluded`로 기록한다. 같은 input/cache/implementation commit에서 canonical JSON
byte와 packet hash가 같아야 한다.

> **Erratum (2026-10-13):** 구현의 reason 값은 `budget_excluded`가 아니라 `packet_budget_excluded`이며
> packet의 `excluded_evidence` 배열에 기록된다(`src/notpatch/evidence/repository.py`의
> `_apply_packet_budget`). Canonical 480 packet에서 budget 제외는 0건이다. `excluded_evidence`에는
> `cutoff_metadata_only_oracle_denylist` 480건과 `solution_revealing_fix_pr_denylist` 4건만 있다.
> 위 5단계의 `empty:no_candidate_text_blob`도 구현 분기만 있고 0건이다(4개 repository category가
> 480/480 `materialized`). Evidence item의 `selection_reason` 값은 `docs/task_schema.md` §3 erratum을 따른다.

Reviewer는 primary pass 중 repository, web, 기존 label을 임의로 추가 탐색하지 않는다.
Retrieval이 불충분하다고 판단하면 label을 추측하지 말고 `retrieval_sufficiency`와
`missing_repository_evidence`에 기록한다.

## 6. Packet schema와 상태 의미

Canonical 구조는 `docs/task_schema.md` v0.2를 따른다. 모든 task packet은 최소 다음
top-level provenance를 갖는다.

- `schema_version`, `packet_policy_id`, `packet_id`, `packet_revision`
- source/sampling identity와 `task_id`, `repo`, `base_commit`, random rank
- component별 cutoff와 verification status
- repository inventory reference/hash와 retrieval algorithm/parameter hash
- `available_evidence`의 issue, comments, `retrieved_code`, `visible_tests`, `docs`, `configs`,
  `linked_artifacts`
- category별 상태, excluded-item summary, collector/run/git provenance
- content hash, packet hash, reviewer-view hash

Category status는 다음 네 가지를 구분한다.

| Status | 의미 | Primary label 처리 |
| --- | --- | --- |
| `materialized` | 하나 이상의 cutoff-valid item을 포함 | 그대로 사용 |
| `empty` | 수집·검색은 성공했으나 해당 item이 없음 | 유효한 관찰값; 빈 배열 유지 |
| `unavailable` | private/404/edit-history/cutoff 문제로 task 시점 content를 복원할 수 없음 | 누락 reason을 보여주되 content를 추정하지 않음 |
| `failed` | clone/commit/tree/API/parser 같은 pipeline 실패 | label 금지; 재시도 또는 deviation 필요 |

Task-level `packet_status`는 `ready`, `ready_with_unavailable`, `failed` 중 하나다. Repository
commit/tree/inventory 또는 issue packet이 `failed`이면 task도 `failed`다. Public linked
artifact가 명시적 `unavailable`인 것은 `ready_with_unavailable`일 수 있다. Collector failure를
P2/P3나 U-label의 근거로 바꾸지 않는다.

`empty`, `unavailable`, `failed`는 모두 reason code, attempted source, attempt count,
last-attempt timestamp를 가진다. Secret/token은 provenance에 기록하지 않는다.

> **Erratum (2026-10-13):** 위 문장은 구현ㆍdata와 다르다. Materializer(`_status`)와 validator
> (`src/notpatch/schemas/validation.py`의 `_validate_category_status`)는 `attempted_source`,
> `attempt_count`, `last_attempt_at`을 `unavailable`/`failed`에만 붙인다. Canonical 480 packet의
> category status 3,840건(480 × 8) 중 `empty` 262건은 `materialized` 2,903건처럼 `{status, reason}`만
> 갖고, `unavailable` 675건만 attempt field를 갖는다(`attempt_count`는 항상 1, `last_attempt_at`은 그
> packet의 fix-PR cutoff 확인 시각 `cutoff_verified_at`). `failed`는 0건이다. v1 materializer는
> clone/commit/tree/API/parser 실패 시 `failed` packet을 쓰지 않고 실행 전체를 중단하므로(`FAIL`,
> exit 1) 위 표와 §9 gate의 `failed` 분기는 v1 data에 나타나지 않는다. Task-level `packet_status`는
> public comment가 항상 `unavailable`이므로 480/480 `ready_with_unavailable`이다. Reason별 실측 분포는
> `docs/task_schema.md` §4 erratum에 있다.

## 7. Reviewer와 adjudicator provenance freeze

P0-3 batch ID는 `repo480_available_v1`로 예약하고 stable artifact ID를 다음처럼 고정한다.

| Stable ID | 역할 | Frozen access rule |
| --- | --- | --- |
| `repo480_r1` | independent available-only pass 1 | 동일 reviewer-view packet; prior label/oracle/detector/outcome 비공개 |
| `repo480_r2` | independent available-only pass 2 | `repo480_r1` 결과 비공개; 그 밖의 조건 동일 |
| `repo480_adj` | third-reviewer adjudication | 두 raw pass와 available packet만 열람; oracle/outcome 비공개 |

이 ID는 role slot이며 현재 개인 identity를 발명하지 않는다. 공개ㆍ논문용 profile은
`peer researcher`와 `8 years of programming experience`로만 고정하고, 그 밖의 경력과
affiliation은 공개하지 않는다. Worklist export 전에는 서로 다른 reviewer라는 coordinator
attestation, Python repository 검토 capability, detector/guideline involvement, 같은
task/seed-label/oracle prior exposure와 role별 blinding을 registry snapshot에 고정한다.
이 metadata는 procedural independence를 추적하지만 institutional independence나 external
reliability를 뒷받침하지 않는다.

Reviewer-view packet은 `packet_id`, issue/repository evidence, category status만 포함한다.
Seed label, random rank, old rationale, oracle field, detector prediction은 숨긴다. Raw pass는
서로의 파일을 열지 않고 제출하며, adjudication은 raw record를 보존한 별도 artifact다.

Reviewer 선정은 coordinator가 담당하고, request의 accessㆍblinding 규칙을 준수하며 Python
repository를 검토할 수 있는 서로 다른 동료 연구자만 배정한다. Agent는 별도 배정
questionnaire를 반복하지 않으며, 실제 access deviation이 발생한 경우에만 deviation log에
남긴다.

## 8. Freeze, deviation, and evidence-widening rule

- P0-2는 이 protocol ID로 480 packet을 모두 생성하고 two-run determinism을 통과한 뒤
  reviewer-view hash list를 freeze한다.
- Materialized content, category status, retrieval parameter가 바뀌면 `packet_revision`을
  올리고 영향 task의 기존 label을 primary 분석에서 무효화한다. 두 raw pass 모두 같은 새
  packet으로 다시 수행해야 한다.
- Metadata-only 수정이라도 reviewer-view hash가 바뀌면 re-review 여부와 이유를 deviation
  log에 기록한다.
- Reviewer의 임의 web/repository browsing이나 task별 수동 file 추가는 primary policy에서
  허용하지 않는다. Systematic retrieval defect를 발견하면 disjoint calibration task에서
  policy를 수정하고 480행 전체 또는 영향 범위를 재생성한다.
- Task-specific evidence widening은 별도 packet policy와 sensitivity로만 허용하며 primary
  prevalence label을 조용히 덮어쓰지 않는다.
- 모든 deviation은 발견 시각, 영향 task, old/new hash, reason, 결정자, aggregate result
  열람 여부, rerun/relabel 범위를 append-only log에 남긴다. Aggregate result를 본 뒤의
  변경은 post-analysis deviation으로 명시한다.
- P0-3의 append-only log는
  `data/manifests/generated/repo480_protocol_deviations_v1.jsonl`이며, 작업 시작 전 전달 실패도
  reviewer-view 내용 변경과 구분해 기록한다.
- 2026-08-18 이후 독립 재materialization은 frozen hash를 갱신하지 않는다. Legacy byte/hash
  비교와 `repo480-evidence-boundary-v1` normalized 비교를 분리하며, normalized PASS는
  provider 원본 byte identity가 아니라 evidence boundary equality만 뜻한다.

> **Known provenance gap (2026-10-13):** Deviation log 5행(`repo480-dev-20260714-001`–
> `repo480-dev-20260715-005`)의 `new_request_manifest_ref`인
> `request/repo480_reviewer_request_manifest_v2.json`은 git 이력 시작(`c00eb1c`, 2026-08-12) 이전 파일이다.
> 어떤 버전도 저장소나 git 이력에 없고(`git log --all`에서 0건), 행마다 기록된
> `new_request_manifest_sha256`만 남는다. 현재 `scripts/make_repo480_reviewer_request.py`로 다시
> 만든 manifest가 이 hash와 일치하는지는 확인하지 않았다(미확인). Annotator가 본 evidence의
> 동일성은 frozen `reviewer_view_hash` 480개로 검증한다
> (`results/pilot/repo480_evidence_reproduction_check_2026-08-12.md`). Frozen log는 수정하지 않는다.

## 9. P0-2 validation gate

P0-2는 다음을 모두 검사해야 한다.

1. 기존 480 frame과 task ID, random rank, `base_commit`이 1:1로 일치한다.
2. 480행 모두 `ready`/`ready_with_unavailable` 또는 구체적 `failed` reason을 가진다.
3. 모든 `base_commit` object와 tree/inventory hash가 검증된다.
4. 모든 category가 materialized/empty/unavailable/failed 중 하나이며 빈 배열과 실패가
   구분된다.
5. Denylist를 바꿔도 reviewer-view hash가 변하지 않는 negative control, issue/base-commit을
   바꾸면 hash가 변하는 positive control을 통과한다.
6. Clean-cache와 cached replay의 canonical packet/hash list가 같다.
7. Reviewer worklist에 seed label, oracle, changed-file path, test oracle, outcome, detector field가
   없다는 leakage scan을 통과한다.

이 gate는 materialization readiness만 뜻한다. Repository-level prevalence와 oracle-masking
claim은 P0-3 relabel, P0-4 재산정, P0-5 two-phase blind 검증 뒤에만 다시 연다.
