# NotPatch Task Schema v0.2

- **Status:** `active`
- **Authority:** task-level repository available/oracle evidence 분리의 canonical schema
- **Last verified:** 2026-10-13 (2026-10-13 erratum: §1, §3, §4, §6.1; 상태 표시: §7, §8; 추가: §6.7, §9, §10 annotation guideline erratum)
- **Evidence protocol:** `docs/repository_evidence_protocol.md`

이 문서는 NotPatch task packet과 oracle evidence를 분리하기 위한 canonical schema이다.
v0.2는 480-task repository-evidence relabel을 위해 issue, exact `base_commit`, deterministic
retrieval, public linked artifact, empty/failure state를 명시한다. 기존 v0.1 bundle은
pre-revision provenance로 보존하지만, `swebench-repo480-v1` primary analysis 입력으로
승격하지 않는다.

## 1. Component별 Evidence Boundary

하나의 timestamp로 issue packet과 repository snapshot을 동시에 표현하지 않는다.

| Field | Meaning |
| --- | --- |
| `component_boundaries.issue_packet` | benchmark가 정의한 problem statement source/snapshot |
| `component_boundaries.repository_snapshot` | exact `base_commit` object/tree |
| `component_boundaries.public_artifacts` | 검증된 fix-PR-open cutoff 이전 public comment/link |
| `cutoff_source` | timestamp를 얻은 source/API/cache locator |
| `cutoff_source_field` | source 안에서 timestamp가 있던 field |
| `cutoff_verification_status` | `verified`, `unverified`, `not_applicable` |
| `cutoff_verified_at` | collector가 source metadata를 확인한 시각 |

현재 v0.1의 `issue_created_at`은 SWE-bench 원천 `created_at`의 의미를 검증하지 않고 복사한
필드다. v0.2에서 이 값을 issue creation time이나 fix PR cutoff로 추정해 쓰지 않는다.
Public artifact cutoff를 검증할 수 없으면 본문을 넣지 않고
`unavailable:cutoff_unverifiable`로 기록한다. Repository evidence는 timestamp 추정이 아니라
exact `base_commit` tree membership으로 검증한다.

> **Erratum (2026-10-13):**
>
> - **Public comment는 구조적으로 배제된다.** v1은 source issue identity를 해석하지 않으므로
>   `public_comments_until_cutoff`가 480/480 `unavailable:source_identity_unverified`이고 comment item은
>   0건이다. `public_artifacts` cutoff 자체는 480/480 `verified`다
>   (`data/manifests/generated/swebench_repo480_materialization_manifest_v1.json`의
>   `public_cutoff_verification_status`). 위 `unavailable:cutoff_unverifiable`은 cutoff 미검증 분기이며
>   comment category에서는 0건이다. Link category의 `cutoff_unverifiable` 의미는 §4 erratum을 따른다.
> - **`evidence_cutoff_timestamp`, `evidence_cutoff_rule`은 v0.1 issue-packet legacy field다.**
>   v0.1 bundle(예: `scripts/build_evidence_bundles.py` 산출물)과 그 bundle에서 만든 worklistㆍannotation
>   record가 이 단일 timestamp field를 쓴다. Repo480 record에는 없다(canonical
>   `data/annotations/adjudicated/repo480_available_v1.jsonl`,
>   raw `data/annotations/raw_labels/repo480_available_v1_r1.jsonl`, `..._r2.jsonl` 모두 0/480). Repo480은 위
>   표와 `docs/repository_evidence_protocol.md` §2의 component별 boundary(issue packet
>   `benchmark_defined`, repository `base_commit`, public conversation/link `pre_fix_pr_opened`)를 쓰고,
>   record는 `packet_id`, `reviewer_view_hash`, `component_boundary_ref`로 boundary에 연결된다(§6.1).
>   Exporter(`scripts/export_annotations_from_worklist.py`)와 validator(`src/notpatch/schemas/validation.py`)도
>   `packet_policy_id`가 있는 record에는 legacy field 대신 이 linkage를 요구한다.

## 2. Repository Evidence Packet

다음 구조가 v0.2의 canonical logical schema다. Content-addressed 저장을 위해 큰 inventory와
excerpt를 별도 파일에 둘 수 있지만, reference path와 SHA-256은 packet에 남겨야 한다.

```json
{
  "schema_version": "evidence-packet-v0.2",
  "packet_policy_id": "swebench-repo480-v1",
  "packet_id": "django__django-14539@swebench-repo480-v1",
  "packet_revision": 1,
  "packet_status": "ready|ready_with_unavailable|failed",
  "task_id": "django__django-14539",
  "dataset": "swebench_full",
  "repo": "django/django",
  "base_commit": "sha",
  "sampling": {
    "frame_id": "swebench-full-test-random-480-seed-20260617",
    "random_rank": 1,
    "sampling_weight": 1.0,
    "source_manifest_ref": "path-or-uri",
    "source_manifest_sha256": "sha256"
  },
  "component_boundaries": {
    "issue_packet": {
      "rule": "benchmark_defined",
      "source_ref": "hf://...",
      "source_snapshot": "snapshot-id",
      "verification_status": "verified"
    },
    "repository_snapshot": {
      "rule": "base_commit",
      "commit_sha": "sha",
      "verification_status": "verified"
    },
    "public_artifacts": {
      "rule": "pre_fix_pr_opened",
      "cutoff_timestamp": "timestamp-or-null",
      "cutoff_source": "source-ref-or-null",
      "cutoff_source_field": "created_at-or-null",
      "cutoff_verification_status": "verified|unverified|not_applicable",
      "cutoff_verified_at": "timestamp",
      "cutoff_source_payload_sha256": "sha256-or-null"
    }
  },
  "repository_snapshot": {
    "remote": "https://github.com/django/django",
    "commit_object_verified": true,
    "tree_sha": "sha",
    "inventory_ref": "path",
    "inventory_sha256": "sha256",
    "regular_blob_count": 0,
    "text_corpus_count": 0
  },
  "retrieval": {
    "algorithm_id": "lexical-bm25-v1",
    "parameter_sha256": "sha256",
    "query_source_sha256": "sha256",
    "reviewer_query": null
  },
  "available_evidence": {
    "issue_title": "...",
    "issue_body": "...",
    "public_comments_until_cutoff": [],
    "retrieved_code": [],
    "visible_tests": [],
    "docs": [],
    "configs": [],
    "linked_artifacts": []
  },
  "category_status": {
    "issue_packet": {"status": "materialized", "reason": "source_snapshot_verified"},
    "repository_inventory": {"status": "materialized", "reason": "base_commit_tree_verified"},
    "public_comments_until_cutoff": {"status": "empty", "reason": "no_cutoff_valid_comment"},
    "retrieved_code": {"status": "materialized", "reason": "selected_by_lexical_bm25_v1"},
    "visible_tests": {"status": "materialized", "reason": "selected_by_lexical_bm25_v1"},
    "docs": {"status": "empty", "reason": "no_candidate_text_blob"},
    "configs": {"status": "materialized", "reason": "selected_by_lexical_bm25_v1"},
    "linked_artifacts": {"status": "unavailable", "reason": "cutoff_unverifiable"}
  },
  "excluded_evidence": [],
  "failure_audit": [],
  "materialization_provenance": {
    "run_id": "stable-run-id",
    "collector_git_sha": "sha"
  },
  "available_evidence_hash": "sha256",
  "repository_inventory_hash": "sha256",
  "reviewer_view_hash": "sha256",
  "packet_hash": "sha256"
}
```

`reviewer_query`는 v1 primary policy에서 항상 `null`이다. Reviewer가 ad hoc search로 packet을
바꾸지 않으며 retrieval insufficiency는 annotation record에 별도 표시한다.

실행마다 달라지는 `started_at`, `completed_at`, `clean|cached_replay` mode와 local output/cache
경로는 canonical packet이 아니라 별도 run report에 둔다. Packet의 `run_id`는 protocol,
source-manifest checksum, collector commit으로 결정한다. 이 분리는 clean materialization과
offline cached replay의 packet byte/hash가 같아야 한다는 determinism gate를 지킨다.

## 3. Evidence Item Schema

`available_evidence`의 배열 item은 source 종류에 따라 불필요한 field를 생략할 수 있지만
다음 provenance를 공통으로 유지한다.

```json
{
  "evidence_id": "stable-id",
  "kind": "repository_file|public_comment|linked_issue|linked_pr|attachment",
  "source_locator": "git:path@sha-or-public-url",
  "path": "tests/test_example.py",
  "source_commit": "sha-or-null",
  "created_at": "timestamp-or-null",
  "updated_at": "timestamp-or-null",
  "cutoff_status": "within_cutoff|not_applicable",
  "selection_reason": "exact_path|lexical_bm25_v1|direct_link",
  "retrieval_rank": 1,
  "score": 0.0,
  "content": "...",
  "content_sha256": "sha256",
  "full_blob_sha": "git-sha-or-null",
  "size_bytes": 0,
  "content_truncated": false,
  "included_line_ranges": []
}
```

Git blob은 `source_commit`과 `full_blob_sha`로 provenance를 고정한다. Public item은 source
payload hash, observed time, HTTP/API status를 추가한다. `score`는 paper metric이 아니라
retrieval 재현용 값이다.

> **Erratum (2026-10-13):** Canonical 480 packet의 `selection_reason` 실제 값은 `lexical-bm25-v1`
> (hyphen, `retrieval.algorithm_id`와 같은 문자열; 14,038 item), `exact_path`(316 item),
> `direct_link`(25 linked item)이다. 위 예시의 `lexical_bm25_v1`(underscore)은 쓰이지 않는다. 반면
> category status reason `selected_by_lexical_bm25_v1`(§4)은 underscore가 맞다.
> Linked item(`kind = linked_issue|linked_pr`)이 추가로 갖는 field 이름은 `source_payload_sha256`,
> `observed_at`, `http_status`다.

## 4. Empty, Unavailable, and Failure Schema

각 category는 배열이 비어 있어도 `category_status`를 반드시 갖는다.

| Status | Allowed reason examples |
| --- | --- |
| `materialized` | `source_snapshot_verified`, `selected_by_lexical_bm25_v1` |
| `empty` | `no_reference`, `no_cutoff_valid_comment`, `no_candidate_text_blob` |
| `unavailable` | `private`, `not_found`, `cutoff_unverifiable`, `edit_history_unavailable` |
| `failed` | `clone_failed`, `commit_missing`, `tree_read_failed`, `api_failed`, `parse_failed` |

Status object에는 `attempted_source`, `attempt_count`, `last_attempt_at`을 추가할 수 있다.
`failed` category가 issue packet, repository commit/tree, inventory에 있으면 task-level
`packet_status = failed`이며 primary annotation을 금지한다. `empty`는 유효한 관찰이고,
`unavailable`은 task-time artifact를 복원하지 못한 상태다. 둘 다 collector failure와 다르다.

> **Erratum (2026-10-13): canonical 480 packet 실측.** 위 표는 허용 예시이며 실제 값과 다르다.
> 아래는 category status 3,840건(480 packet × 8 category)의 집계다.
>
> | Status | 건수 | 실제 field | 실제 reason (건수, category) | 위 표에만 있는 값 |
> | --- | ---: | --- | --- | --- |
> | `materialized` | 2,903 | `status`, `reason` | `selected_by_lexical_bm25_v1` 1,920 (`retrieved_code`ㆍ`visible_tests`ㆍ`docs`ㆍ`configs` 각 480), `source_snapshot_verified` 480 (`issue_packet`), `base_commit_tree_verified` 480 (`repository_inventory`), `direct_link_cutoff_verified` 23 (`linked_artifacts`) | — |
> | `empty` | 262 | `status`, `reason` (attempt field 없음) | `no_reference` 262 (`linked_artifacts`) | `no_cutoff_valid_comment`(구현 없음), `no_candidate_text_blob`(구현만 있고 0건) |
> | `unavailable` | 675 | 위 둘 + `attempted_source`, `attempt_count`(항상 1), `last_attempt_at`(그 packet의 `cutoff_verified_at`) | `source_identity_unverified` 480 (`public_comments_until_cutoff`), `cutoff_unverifiable` 185, `edit_history_unavailable` 10 (둘 다 `linked_artifacts`) | `private`(구현 없음), `not_found`(link 단위 `failure_audit`에만 4건) |
> | `failed` | 0 | — | — | 모든 예시(구현 없음; v1은 pipeline 실패 시 실행을 중단) |
>
> - **`linked_artifacts`의 `cutoff_unverifiable`은 task cutoff 실패가 아니다.** URL이
>   `https?://github.com/<owner>/<repo>/(issues|pull)/<n>` 형식이 아니어서 timestamp를 검증할 경로가 없다는
>   뜻이다. Link 단위 378건과 packet 단위 185건 모두 이 경우이며, canonical 480 packet에서 task cutoff
>   미검증은 0건이다(`docs/repository_evidence_protocol.md` §3.1 erratum).
> - **Packet 단위 `linked_artifacts` 상태 규칙:** 포함된 linked item이 하나라도 있으면
>   `materialized:direct_link_cutoff_verified`, 없고 실패 link가 있으면 `unavailable`(실패 link 중
>   `cutoff_unverifiable`이 있으면 그 reason, 없으면 첫 실패 reason), link가 없으면 `empty:no_reference`다.
>   따라서 `materialized` 23 packet 중 9개에도 link 실패가 함께 있다.
> - **Link 단위 실패**는 별도 `failure_audit` 배열(key `category`, `reason`, `attempted_source`,
>   `attempt_count`, `last_attempt_at`)에 있다. 407건: `cutoff_unverifiable` 378, `edit_history_unavailable`
>   25, `not_found` 4.
> - **`excluded_evidence`**(key `kind`, `reason`, `source_locator`)는 `cutoff_metadata_only_oracle_denylist`
>   480건과 `solution_revealing_fix_pr_denylist` 4건이다. Budget 제외 reason은 구현상
>   `packet_budget_excluded`(protocol §5의 `budget_excluded`)이고 0건, `created_after_cutoff`도 0건이다.
> - **근거:** `src/notpatch/evidence/repository.py`(`_status`, `_materialize_public_metadata`,
>   `_apply_packet_budget`); gitignored canonical corpus
>   `external/notpatch_evidence/swebench-repo480-v1/clean/packets.jsonl`(복구본. 23 packet은 link item의
>   `observed_at`ㆍ`source_payload_sha256`만 원본과 다르다. `results/pilot/repo480_evidence_reproduction_check_2026-08-12.md`);
>   category별 합계는 `results/pilot/swebench_repo480_materialization_validation.md`; 원본
>   `category_status`의 tracked 사본 12행은 `data/annotations/worklists/repo480_rq2_phase1_tasks_v1.jsonl`.

## 5. Hash Contract

- `available_evidence_hash`: issue와 허용된 evidence content/status의 canonical JSON hash
- `repository_inventory_hash`: path/mode/blob/size/category/corpus-status inventory hash
- `reviewer_view_hash`: reviewer가 실제 보는 allowlisted field만의 canonical JSON hash
- `packet_hash`: provenance와 failure audit까지 포함한 packet 전체 hash
- `evidence_boundary_sha256` (별도 manifest): exact treeㆍretrieval contractㆍannotator-visible
  evidence와 의미 있는 availability status만 포함한 cross-run normalized digest

Canonical JSON은 UTF-8, sorted key, compact separator, trailing newline 한 개를 사용한다.
Secret, local absolute cache path, access token은 hash input과 release artifact에 넣지 않는다.
Denylist field 변화는 `reviewer_view_hash`를 바꾸면 안 되고 issue content 또는
`base_commit` 변화는 반드시 hash를 바꿔야 한다.

기존 네 hash field는 packet v0.2 안에서 변경하지 않는다. 다른 수집 시각의 독립 재현은
`docs/repository_evidence_digest_protocol.md`가 정의한 별도
`swebench_repo480_evidence_boundary_manifest_v1.json`과 비교한다. 이 projection은
`last_attempt_at`, provider 전체 payload hash와 fetch 관측값을 제외하지만 cutoff, tree/inventory,
retrieval parameter, content/status/reason 변화는 포함한다.

## 6. Annotation Record Linkage

Available-only record는 v0.4 field에 다음 provenance를 추가한다.

```json
{
  "task_id": "django__django-14539",
  "annotator_id": "repo480_r1",
  "annotation_batch_id": "repo480_available_v1",
  "pass": "available_only",
  "packet_policy_id": "swebench-repo480-v1",
  "packet_id": "django__django-14539@swebench-repo480-v1",
  "packet_revision": 1,
  "reviewer_view_hash": "sha256",
  "registry_snapshot_sha256": "sha256",
  "retrieval_sufficiency": "sufficient|insufficient|unclear",
  "missing_repository_evidence": [],
  "primary_label": "P0|P1|P2|P3",
  "adjudication_status": "raw|adjudicated|unresolved"
}
```

`packet_status = failed`인 task에는 annotation record를 만들지 않는다. Packet revision이나
reviewer-view hash가 다르면 두 raw pass를 같은 batch의 independent label로 합치지 않는다.

### 6.1 Repository-480 Worklist Wrapper

`repo480-worklist-v1`은 large reviewer view와 reviewer 응답을 분리한다. 각 blank worklist row는
`ordinal`, `task_id`, `repo`, `annotator_id`, batch/pass/packet linkage,
`reviewer_view_ref`, `reviewer_view_hash`, `registry_snapshot_sha256`와
`annotation_fields`를 가진다. `reviewer_view_ref`는
`repo480_reviewer_views_v1_part01_of08.zip`부터
`repo480_reviewer_views_v1_part08_of08.zip`까지의 독립 archive 중 하나에 있는 task별
`reviewer-view-v0.2` JSON을 가리킨다. 각 archive는 연속된 ordinal 60개를 담으며, v2 request
manifest가 archive별 ordinal 범위ㆍentry 수ㆍSHA-256을 고정한다.

Reviewer는 식별ㆍlinkage field를 수정하지 않고 `annotation_fields`와
`annotation_status = labeled`만 반환한다. Exporter는 480행의 order, task/packet/hash, raw role,
registry checksum을 materialization/registry snapshot과 대조한 뒤에만 canonical annotation
record를 생성한다. Repository-boundary record는 단일 timestamp를 발명하지 않고
`packet_id`, exact-`base_commit` reviewer view, `component_boundary_ref`로 evidence boundary를
추적한다.

> **Erratum (2026-10-13):** `component_boundary_ref`는 JSON pointer가 아니라 고정 문자열
> `"frozen_reviewer_view"`다(raw `repo480_available_v1_r1.jsonl`, `..._r2.jsonl`와 canonical adjudicated
> 각 480/480). §6 예시 record에는 빠져 있지만 exporter와 validator(`_validate_repository_annotation_linkage`)가
> 필수 field로 요구한다. `available_evidence_used`의 값은 packet category 이름(`issue_title`, `issue_body`,
> `retrieved_code`, `visible_tests`, `docs`, `configs`, `linked_artifacts`)이며 `repo_docs` 같은 별칭은
> data에 없다.

> **Known provenance gap (2026-10-13):**
>
> - 위 v2 request manifest(`request/repo480_reviewer_request_manifest_v2.json`)는 git 이력 시작(`c00eb1c`,
>   2026-08-12) 이전 파일이라 어떤 버전도 남아 있지 않다. Archive별 ordinal 범위ㆍentry 수ㆍSHA-256의
>   원 기록은 복구할 수 없고, `data/manifests/generated/repo480_protocol_deviations_v1.jsonl` 5행의
>   `new_request_manifest_sha256`만 남는다(`docs/repository_evidence_protocol.md` §8). Annotator가 본
>   evidence(`reviewer_views.jsonl`)는 frozen `reviewer_view_hash` 480개로 검증한다.
> - Pre-revision rq5 enriched v1ㆍextension v2 panel의 raw 반환(`request/rq5_enriched_pool/`,
>   `request/rq5_oracle_masking_diagnostic/`, `request/rq5_extension_v2/`,
>   `request/rq5_extension_v2_oracle_masking/`)은 git 이력에도 디스크에도 없다. 파생 파일
>   `data/processed/policy_utility/rq5_enriched_panel_adjudicated.jsonl`,
>   `rq5_enriched_masking_adjudicated.jsonl`, `rq5_extension_v2_panel_adjudicated.jsonl`,
>   `rq5_extension_v2_masking_adjudicated.jsonl`에는 annotator별 label 또는 masked vote와 집계값만 남고,
>   raw record의 나머지 field(rationale, evidence pointer 등)는 복구할 수 없다. 이 파일들은 현재 claim의
>   근거가 아닌 provenance다.

### 6.2 Repository-480 Raw Metadata Correction Sidecar

`repo480-raw-metadata-correction-v1`은 제출된 raw annotation을 수정하지 않고 기계적으로
검증 가능한 metadata 누락만 overlay하는 append-only JSONL이다. 현재 허용하는 correction은
frozen reviewer view에 해석되는 provenance pointer의 category를
`/available_evidence_used`에 `add_if_absent`로 추가하는 것뿐이다. 각 row는 다음을 고정한다.

```json
{
  "schema_version": "repo480-raw-metadata-correction-v1",
  "correction_id": "repo480-evidence-category-repo480_r1-0035-visible_tests",
  "annotation_batch_id": "repo480_available_v1",
  "task_id": "pytest-dev__pytest-8422",
  "ordinal": 35,
  "annotator_id": "repo480_r1",
  "raw_artifact_ref": "data/annotations/raw_labels/repo480_available_v1_r1.jsonl",
  "raw_artifact_sha256": "sha256",
  "raw_record_sha256": "sha256",
  "packet_id": "pytest-dev__pytest-8422@swebench-repo480-v1",
  "reviewer_view_ref": "reviewer_views/0035_pytest-dev__pytest-8422.json",
  "reviewer_view_hash": "sha256",
  "field_path": "/available_evidence_used",
  "operation": "add_if_absent",
  "value": "visible_tests",
  "reason_code": "provenance_pointer_category_omission",
  "supporting_pointer": "testing/python/approx.py",
  "supporting_pointer_category": "visible_tests",
  "verified_against_frozen_reviewer_view": true,
  "scientific_judgment_unchanged": true
}
```

Label, blocker, direction, rationale, retrieval 판단을 바꾸는 수정은 이 sidecar에 넣지 않는다.
그 변경은 raw를 보존한 adjudication decision으로만 수행한다.

### 6.3 Repository-480 Adjudication Wrapper

`repo480-adjudication-worklist-v1`은 두 raw annotation의 non-exact decision 축을 한 row에
제시한다. Immutable linkage, `disagree_axes`, category/priority, `left`와 `right` raw view를
포함한다. Raw view에는 제출값 `available_evidence_used`, 적용 correction ID와 sidecar를 반영한
`effective_available_evidence_used`를 함께 둔다.

반환 파일은 `repo480-adjudication-decision-v1` JSONL이다. 식별ㆍpacketㆍreviewer-view linkage와
disagreement 축은 worklist에서 복사하며 다음 판정 field를 채운다.

```json
{
  "schema_version": "repo480-adjudication-decision-v1",
  "adjudication_status": "pending|adjudicated|unresolved",
  "ordinal": 1,
  "task_id": "django__django-14539",
  "repo": "django/django",
  "packet_id": "django__django-14539@swebench-repo480-v1",
  "packet_revision": 1,
  "reviewer_view_ref": "reviewer_views/0001_django__django-14539.json",
  "reviewer_view_hash": "sha256",
  "registry_snapshot_sha256": "sha256",
  "disagree_axes": ["predicted_direction_wording"],
  "disagreement_category": "direction_wording_only",
  "base_annotator": "repo480_r1|repo480_r2|null",
  "overrides": {},
  "direction_equivalence": "equivalent|partially_equivalent|different|not_assessable|not_applicable|null",
  "shared_evidence_pointers": [],
  "decisive_missing_or_conflicting_evidence_pointers": [],
  "calibration_only": false,
  "calibration_only_reason": null,
  "boundary_reason": null,
  "resolution_notes": null,
  "posthoc_or_detector_evidence_used": false
}
```

Completed decision은 `base_annotator`를 반드시 지정한다. `overrides`는 canonical annotation의
판단 field만 포함하며 packet/linkage나 oracle field를 바꿀 수 없다. Binary-boundary row는
shared evidence와 decisive missing/conflicting evidence pointer를 각각 하나 이상 기록한다.
Pointer를 특정할 수 없는 경우에만 `calibration_only = true`와 reason을 쓴다. Exact-agreement로
queue에서 제외된 row는 명시된 default raw record를 representative로 사용하되, raw 판단은 모두
별도 보존한다.

### 6.4 Repository-480 RQ2 Phase 1 Wrapper

`repo480-rq2-phase1-task-v1`은 public outcome join으로 선택된 solved P2/P3 denominator의
reviewer-facing available evidence를 담는다. Selection과 outcome의 상세는 coordinator-side
artifact에만 두고 task record에는 prior label, oracle와 outcome field를 넣지 않는다.

```json
{
  "schema_version": "repo480-rq2-phase1-task-v1",
  "annotation_batch_id": "repo480_rq2_masking_v1",
  "phase": "available_candidate_freeze",
  "ordinal": 1,
  "task_id": "sympy__sympy-15596",
  "random_rank": 41,
  "repo": "sympy/sympy",
  "packet_policy_id": "swebench-repo480-v1",
  "packet_id": "sympy__sympy-15596@swebench-repo480-v1",
  "packet_revision": 1,
  "reviewer_view_hash": "sha256",
  "available_evidence_hash": "sha256",
  "available_evidence": {},
  "category_status": {},
  "blinding": {
    "prior_judgment_hidden": true,
    "posthoc_evidence_hidden": true,
    "outcome_metadata_hidden": true,
    "peer_judgment_hidden": true
  }
}
```

Reviewer 반환은 `repo480-rq2-phase1-judgment-v1` JSONL이며 task의 canonical hash에 연결한다.

```json
{
  "schema_version": "repo480-rq2-phase1-judgment-v1",
  "annotation_batch_id": "repo480_rq2_masking_v1",
  "phase": "available_candidate_freeze",
  "ordinal": 1,
  "task_id": "sympy__sympy-15596",
  "annotator_id": "repo480_rq2_r1",
  "phase1_task_sha256": "sha256",
  "annotation_status": "pending|complete|unresolved|protocol_deviation",
  "candidate_directions": [
    {
      "candidate_id": "C1",
      "component_or_function": "component",
      "input_condition_or_trigger": "condition",
      "observable_behavior_change": "behavior"
    }
  ],
  "deciding_missing_evidence": [],
  "available_evidence_pointers": [],
  "phase1_behavior_determinate": "yes|no|unclear|null",
  "rationale": null,
  "prohibited_evidence_used": false,
  "protocol_deviation": null
}
```

정상 completed row는 candidate와 rationale, available evidence pointer를 비울 수 없습니다.
`determinate = no|unclear`이면 deciding missing evidence가 필요합니다. 금지 evidence 노출은
일반 판단으로 덮지 않고 `protocol_deviation` row로 반환합니다. 두 Phase 1 원본을 보존하기
전에는 post-hoc Phase 2 artifact를 만들지 않습니다.

### 6.5 Repository-480 RQ2 Phase 2 Wrapper

`repo480-rq2-phase2-task-v1`은 reviewer별로 분리된 oracle diagnostic task입니다. 각 row에는
동일 reviewer의 잠긴 Phase 1 task/judgment와 frozen SWE-bench oracle row에서 추출한 patch,
test patch, test lists와 hints만 포함합니다. 상대 reviewer의 판단, prior/canonical P-label과
repair-agent identityㆍpatchㆍscoreㆍoutcome은 포함하지 않습니다.

```json
{
  "schema_version": "repo480-rq2-phase2-task-v1",
  "annotation_batch_id": "repo480_rq2_masking_v1",
  "phase": "oracle_diagnostic",
  "ordinal": 1,
  "task_id": "sympy__sympy-15596",
  "annotator_id": "repo480_rq2_r1",
  "phase1_task_sha256": "sha256",
  "phase1_judgment_sha256": "sha256",
  "locked_phase1_judgment": {},
  "oracle_evidence_sha256": "sha256",
  "oracle_evidence": {
    "source_snapshot": "snapshot id",
    "raw_row_index": 2060,
    "source_row_sha256": "sha256",
    "repo": "sympy/sympy",
    "base_commit": "commit",
    "environment_setup_commit": "commit",
    "version": "1.4",
    "hints_text": "post-hoc hint",
    "patch": "diff",
    "test_patch": "diff",
    "fail_to_pass": ["test_Poly_degree"],
    "pass_to_pass": ["test_Poly_from_dict"]
  },
  "blinding": {
    "peer_phase1_judgment_hidden": true,
    "prior_patchability_label_hidden": true,
    "agent_identity_and_outcome_hidden": true,
    "oracle_evidence_revealed": true
  }
}
```

Phase 1 task 본문은 role package의 별도 `repo480_rq2_phase1_tasks.jsonl`에 한 번만 두며,
`phase1_task_sha256`와 동일 ordinal/task ID로 연결합니다. 이 구조는 두 role의 canonical Phase 2
row에 동일한 대용량 available evidence를 중복 삽입하지 않으면서 standalone 검토를 유지합니다.

Reviewer 반환은 `repo480-rq2-phase2-judgment-v1` JSONL이며 Phase 2 task의 canonical hash에
연결합니다.

```json
{
  "schema_version": "repo480-rq2-phase2-judgment-v1",
  "annotation_batch_id": "repo480_rq2_masking_v1",
  "phase": "oracle_diagnostic",
  "ordinal": 1,
  "task_id": "sympy__sympy-15596",
  "annotator_id": "repo480_rq2_r1",
  "phase2_task_sha256": "sha256",
  "annotation_status": "pending|complete|unresolved|protocol_deviation",
  "oracle_direction_summary": null,
  "oracle_direction_in_candidate_set": "yes|no|unclear|null",
  "oracle_revealed_missing_evidence": "yes|partial|no|unclear|null",
  "oracle_alternative_fix_exists": "yes|no|unclear|null",
  "available_evidence_unique_in_hindsight": "yes|no|unclear|null",
  "behavior_target_space_size": "1|2-3|many|unclear|null",
  "data_quality": "Q0|Q1|Q2|null",
  "benchmark_artifact_note": null,
  "oracle_evidence_pointers": [],
  "rationale": null,
  "prohibited_evidence_used": false,
  "protocol_deviation": null
}
```

`oracle_alternative_fix_exists`는 동일 behavior를 구현하는 다른 diff가 아니라 task-time evidence가
배제하지 못한 서로 다른 observable behavior target을 뜻합니다. `behavior_target_space_size`도
oracle을 task-time evidence로 소급하지 않고 available evidence가 허용한 target space를
기록합니다. Strict masking call은 반환 schema에 두지 않고
`oracle_alternative_fix_exists = yes`와 `available_evidence_unique_in_hindsight = no`의 conjunction으로
후속 분석에서 유도합니다.

### 6.6 Repository-480 RQ2 Phase 2 Adjudication Wrapper

두 Phase 2 반환을 hash-linked canonical 원본으로 보존한 뒤 categorical controlled field가 다른
row만 `repo480-rq2-phase2-adjudication-task-v1` worklist에 넣습니다. Narrative summary와 rationale의
wording 차이는 queue 조건이 아닙니다. Worklist는 Phase 1 task, 두 role별 Phase 2 task와 raw
judgment의 canonical hash를 연결하고 두 raw view와 derived strict call을 함께 보존합니다.

```json
{
  "schema_version": "repo480-rq2-phase2-adjudication-task-v1",
  "annotation_batch_id": "repo480_rq2_masking_v1",
  "phase": "oracle_diagnostic_adjudication",
  "ordinal": 3,
  "task_id": "sympy__sympy-13346",
  "repo": "sympy/sympy",
  "adjudicator_id": "repo480_rq2_adj",
  "phase1_task_sha256": "sha256",
  "phase2_r1_task_sha256": "sha256",
  "phase2_r2_task_sha256": "sha256",
  "phase2_r1_judgment_sha256": "sha256",
  "phase2_r2_judgment_sha256": "sha256",
  "disagree_axes": [
    "oracle_direction_in_candidate_set",
    "behavior_target_space_size"
  ],
  "strict_masking_call": {
    "repo480_rq2_r1": "yes",
    "repo480_rq2_r2": "yes"
  },
  "left": {},
  "right": {}
}
```

제3 reviewer 반환은 worklist row의 canonical hash에 연결한
`repo480-rq2-phase2-adjudication-decision-v1` JSONL입니다.

```json
{
  "schema_version": "repo480-rq2-phase2-adjudication-decision-v1",
  "annotation_batch_id": "repo480_rq2_masking_v1",
  "phase": "oracle_diagnostic_adjudication",
  "ordinal": 3,
  "task_id": "sympy__sympy-13346",
  "adjudicator_id": "repo480_rq2_adj",
  "adjudication_task_sha256": "sha256",
  "adjudication_status": "pending|adjudicated|unresolved|protocol_deviation",
  "adjudicated_values": {
    "oracle_direction_in_candidate_set": "yes|no|unclear|unresolved",
    "behavior_target_space_size": "1|2-3|many|unclear|unresolved"
  },
  "evidence_pointers": [],
  "rationale": null,
  "prohibited_evidence_used": false,
  "protocol_deviation": null
}
```

`adjudicated_values` key는 해당 row의 `disagree_axes`와 정확히 같아야 합니다. `unresolved` 값이
하나라도 있으면 row status도 `unresolved`입니다. Strict masking call은 adjudicator가 직접
입력하지 않고 최종 controlled field에서 같은 conjunction으로 다시 유도합니다. Raw 판단과
available-only primary label은 덮어쓰지 않습니다.

### 6.7 CVㆍRR-AㆍRR-B Panel Schema Versions

추가(2026-10-13). Construct-validity audit(CV, `docs/construct_validity_audit_protocol.md`), 독립
boundary-validation panel(RR-A), matched-control RQ2 panel(RR-B)의 row schema는 아래 script가 정의하며,
이 문서는 field 정의를 복제하지 않는다. 반환 행의 field 계약은 괄호 안 selfcheck script가 검사한다.
경로는 수용된 canonical 사본이다(`{1,2}`는 role별 파일).

| Package | `schema_version` | 정의ㆍ생성 script (반환 검사) | Canonical path (행 수) |
| --- | --- | --- | --- |
| CV | `repo480-construct-validity-task-v1` | `scripts/prepare_repo480_construct_validity_audit.py` | `data/annotations/worklists/repo480_construct_validity_tasks_v1.jsonl` (138) |
| CV | `repo480-construct-validity-judgment-v1` | 위 script (`scripts/selfcheck_repo480_construct_validity_return.py`) | `data/annotations/oracle_gap/repo480_construct_validity_panel/repo480_construct_validity_r{1,2,3}.jsonl` (각 138) |
| CV | `repo480-construct-validity-adjudication-task-v1` | `scripts/prepare_repo480_construct_validity_adjudication.py` | `data/annotations/worklists/repo480_construct_validity_adjudication_worklist_v1.jsonl` (26) |
| CV | `repo480-construct-validity-adjudication-decision-v1` | 위 script (`scripts/selfcheck_repo480_construct_validity_adjudication_return.py`) | `data/annotations/oracle_gap/repo480_construct_validity_panel/repo480_construct_validity_adjudication.jsonl` (26) |
| RR-A | `repo480-boundary-validation-worklist-v1` (빈 worklist와 반환이 같은 schema) | `scripts/prepare_repo480_boundary_validation.py` (`scripts/selfcheck_repo480_boundary_validation_return.py`) | `data/annotations/oracle_gap/repo480_boundary_validation_panel/repo480_boundary_validation_r{1,2}.jsonl` (각 220) |
| RR-A | `repo480-bv-adjudication-worklist-v1` | `scripts/prepare_repo480_bv_adjudication.py` | `data/annotations/worklists/repo480_bv_adjudication_worklist_v1.jsonl` (210) |
| RR-A | `repo480-bv-adjudication-decision-v1` | 위 script (`scripts/selfcheck_repo480_bv_adjudication_return.py`) | `data/annotations/oracle_gap/repo480_boundary_validation_panel/repo480_boundary_validation_adjudication.jsonl` (210) |
| RR-A | `repo480-boundary-validation-adjudicated-v1` (파생) | `scripts/analyze_repo480_boundary_validation.py` | `data/annotations/oracle_gap/repo480_boundary_validation_panel/repo480_boundary_validation_adjudicated_v1.jsonl` (220) |
| RR-B | `repo480-rq2-control-phase1-task-v1` | `scripts/prepare_repo480_rq2_control_phase1.py` | Tracked 사본 없음. Archive `request/repo480_rq2_control/repo480_rq2_control_phase1_tasks_v1_part0{1,2}_of02.zip`은 git 미추적이며 현재 작업 사본에도 없다. SHA-256ㆍ재생성 명령은 `data/manifests/generated/repo480_rq2_control_manifest_v1.json`의 `phase1_task_archives`에 있다(재생성 byte 일치는 미확인) |
| RR-B | `repo480-rq2-control-phase1-judgment-v1` | 위 script (`scripts/selfcheck_repo480_rq2_control_phase1_return.py`) | `data/annotations/oracle_gap/repo480_rq2_control_panel/repo480_rq2_control_phase1_r{1,2}.jsonl` (각 36) |
| RR-B | `repo480-rq2-control-phase2-task-v1` | `scripts/prepare_repo480_rq2_control_phase2.py` | `data/annotations/worklists/repo480_rq2_control_phase2_r{1,2}_tasks_v1.jsonl` (각 36) |
| RR-B | `repo480-rq2-control-phase2-judgment-v1` | 위 script (`scripts/selfcheck_repo480_rq2_control_phase2_return.py`) | `data/annotations/oracle_gap/repo480_rq2_control_panel/repo480_rq2_control_phase2_r{1,2}.jsonl` (각 36) |
| RR-B | `repo480-rq2-control-adjudication-task-v1` | `scripts/prepare_repo480_rq2_control_adjudication.py` | `data/annotations/worklists/repo480_rq2_control_phase2_adjudication_worklist_v1.jsonl` (13) |
| RR-B | `repo480-rq2-control-adjudication-decision-v1` | 위 script (`scripts/selfcheck_repo480_rq2_control_adjudication_return.py`) | `data/annotations/oracle_gap/repo480_rq2_control_panel/repo480_rq2_control_phase2_adjudication.jsonl` (13) |

Package manifest(모두 `data/manifests/generated/`, `schema_version`은 파일명과 같은 `repo480-...-v1` 형식):

- **CV:** `repo480_construct_validity_manifest_v1.json`, `repo480_construct_validity_returns_manifest_v1.json`
  (생성 `scripts/prepare_repo480_construct_validity_adjudication.py`),
  `repo480_construct_validity_adjudication_request_manifest_v1.json`,
  `repo480_construct_validity_adjudication_manifest_v1.json`(생성 `scripts/analyze_repo480_construct_validity.py`).
- **RR-A:** `repo480_boundary_validation_manifest_v1.json`(view archive 4개의 SHA-256ㆍ재생성 명령 포함. Archive는
  git 미추적이며 현재 작업 사본에도 없다),
  `repo480_boundary_validation_returns_manifest_v1.json`, `repo480_bv_adjudication_manifest_v1.json`,
  `repo480_bv_adjudication_returns_manifest_v1.json`. 선택 행은
  `data/annotations/worklists/repo480_boundary_validation_selection_v1.jsonl`(`repo480-boundary-validation-selection-v1`).
  `repo480_bv_adjudication_returns_manifest_v1.json`의 `worklist.ref`는 회수된 `request/` 경로를 가리키지만,
  기록된 SHA-256은 위 tracked worklist와 같다.
- **RR-B:** `repo480_rq2_control_manifest_v1.json`, `repo480_rq2_control_phase1_returns_manifest_v1.json`,
  `repo480_rq2_control_phase2_manifest_v1.json`, `repo480_rq2_control_phase2_returns_manifest_v1.json`,
  `repo480_rq2_control_adjudication_manifest_v1.json`, `repo480_rq2_control_adjudication_returns_manifest_v1.json`.
  선택 행은 `data/annotations/worklists/repo480_rq2_control_selection_v1.jsonl`(`repo480-rq2-control-selection-v1`).
- RR-AㆍRR-B의 returns manifest 5개는 `scripts/accept_repo480_panel_returns.py`가 반환 수용 시 쓴다.

## 7. Feature Provenance

> **현재 상태(2026-10-13):** 이 절은 repo480에서 구현되지 않은 설계(design-only)다. Repo480 packet에
> 연결된 feature table은 없다. 저장소의 feature row(`data/processed/feature_tables/`)는
> `feature_schema_version`이 `v0.1` 또는 `v5_static_0.2`인 pre-revision issue-packet 계열이며
> `packet_id`ㆍ`reviewer_view_hash`를 갖지 않는다. Validator(`validate_feature_record`)도 packet linkage를
> 검사하지 않고, repo480 reporting diagnostic(`scripts/analyze_repo480_reporting_diagnostics.py`)은 feature
> table을 읽지 않는다. 미완료 작업이 아니라 미채택 설계로 읽는다.

Feature row는 task ID뿐 아니라 packet identity에 연결한다.

```json
{
  "task_id": "django__django-14539",
  "packet_id": "django__django-14539@swebench-repo480-v1",
  "reviewer_view_hash": "sha256",
  "feature_schema_version": "v0.2",
  "extractor_git_sha": "sha",
  "features": {},
  "feature_provenance": []
}
```

Feature extractor는 oracle patch file name, post-hoc modified-file list, hidden tests,
solution-revealing comments를 사용할 수 없다. LLM feature는 model, prompt, sampling, cache key,
input hash를 기록한다.

## 8. Oracle and Later Evidence

> **현재 상태(2026-10-13):** 이 절의 `oracle-evidence-v0.2` record는 repo480에서 구현되지 않은
> 설계(design-only)다. 이 schema를 만드는 script가 없고 저장소에 해당 record가 0건이다. Repo480의 oracle
> evidence는 RQ2 Phase 2 task row 안에만 있다(§6.5 `repo480-rq2-phase2-task-v1`, §6.7
> `repo480-rq2-control-phase2-task-v1`). Available-only label의 oracle field(`oracle_gap` 등)는 raw r1ㆍr2와
> canonical adjudicated 모두 480/480 `null`이다. 아래 분리 원칙은 유지되지만 record 형식은 위 wrapper가
> 대신한다.

Oracle evidence는 available-only artifact와 물리적으로 분리하고 primary label 동결 뒤에만
연다.

```json
{
  "schema_version": "oracle-evidence-v0.2",
  "task_id": "django__django-14539",
  "available_packet_id": "django__django-14539@swebench-repo480-v1",
  "available_reviewer_view_hash": "sha256",
  "oracle_evidence": {
    "ground_truth_patch": "...",
    "linked_pr_discussion_after_cutoff": [],
    "hidden_tests": [],
    "benchmark_packaging_metadata": []
  },
  "oracle_gap": "no_gap|missing_info|hidden_constraint|test_mismatch|maintainer_context|external_dependency",
  "data_quality": "Q0|Q1|Q2",
  "data_quality_blocker": "D1|none",
  "later_outcome": {}
}
```

Oracle pass는 primary label을 바꾸는 절차가 아니다. Available packet의 content/hash가 바뀌면
기존 oracle record를 자동 재사용하지 않고 linkage와 재검토 범위를 deviation log에 남긴다.

## 9. Canonical 480 Frame Split

추가(2026-10-13). Packet `sampling.source_manifest_ref`가 가리키는
`data/processed/dataset_splits/swebench_full_prevalence_random_480.json`의 field다. 생성 script는
`scripts/make_swebench_prevalence_sample.py`
(`--seed 20260617 --candidate-draw-size 600 --target-eligible 480`, `--exclude-file` 4개)이며 실행 기록은
`results/pilot/swebench_full_prevalence_random_480_sample_report.md`에 있다. 이 split 파일의
`schema_version`은 `v0.1`이고 packet v0.2와 별개다. 같은 행은
`data/manifests/generated/swebench_full_prevalence_random_480_manifest.json`(`tasks` 480행)에, 선택되지 않은
120행을 포함한 candidate draw 600행은 `data/raw/collector_candidates/swebench_full_prevalence_random_480_candidates.jsonl`에
있다.

| Top-level field | 관측값 | 의미 |
| --- | --- | --- |
| `seed`, `selection_rule` | `20260617`, `prevalence_random_first_eligible` | Seed shuffle 순서에서 구조적 제외가 없는 앞쪽 `target_eligible`개를 고른다 |
| `n_source_rows` | 2294 | SWE-bench full `test` split 행 수 |
| `n_excluded_prior`, `n_sampling_frame` | 69, 2225 | 이전 NotPatch label task를 `--exclude-file`로 뺀 수와 남은 frame |
| `candidate_draw_size`, `n_candidate_draw` | 600, 600 | Shuffle 앞쪽 candidate draw 크기 |
| `n_structural_excluded`, `n_eligible_in_draw` | 0, 600 | 필수 field(`instance_id`, `repo`, `base_commit`, `problem_statement`, `created_at`) 누락 제외 수와 그 나머지 |
| `target_eligible`, `n_sampled`, `minimum_eligible` | 480, 480, 100 | `status` gate: target 이상 `PASS`, minimum 이상 `CHECK`, 그 외 `FAIL` |
| `status` | `PASS` | |
| `strata` | `{"prevalence_random": {"n_candidates": 2294, "n_sampled": 480}}` | Sampling 목적이며 label이 아니다 |
| `source_manifest`, `description`, `tasks` | 위 source manifest 경로, 설명 문자열, 480행 | |

| Row field (480행 모두 같은 25개 key) | 관측값 | 의미ㆍ주의 |
| --- | --- | --- |
| `task_id`, `instance_id` | 같은 값, 480개 고유 | |
| `prevalence_random_rank` | 1–480, 빈틈 없음 | Seed shuffle 순위. Packet `sampling.random_rank`와 같다 |
| `prevalence_seed`, `candidate_draw_size`, `target_eligible` | 모든 행 `20260617`, `600`, `480` | Top-level 값의 행별 복사 |
| `selection_status`, `structural_exclusion_reason` | 모든 행 `selected_eligible`, `null` | 가능한 값은 `selected_eligible`, `eligible_not_selected`, `structural_excluded`이며 split에는 선택 행만 있다 |
| `stratum`, `stratum_rationale` | 모든 행 `prevalence_random`, 고정 문장 | Sampling 목적이며 label이 아니다 |
| `dataset`, `source_type`, `source_split` | `swebench_full`, `swebench`, `test` | |
| `repo`, `repo_url`, `base_commit` | 12개 repository, 477개 고유 commit | `base_commit`은 repository snapshot boundary다 |
| `source_ref`, `source_row_index`, `source_snapshot`, `raw_rows_path` | `hf://datasets/princeton-nlp/SWE-bench/test/<instance_id>`; 문자열 index; `downloaded_at=2026-06-27T07:52:48.689662+00:00`을 포함한 고정 문자열; gitignored `external/notpatch_benchmarks/princeton-nlp__SWE-bench__test/rows_test_prevalence_seed20260617_draw600.json` | Raw row provenance |
| `candidate_cutoff_rule` | 모든 행 `benchmark_defined` | Issue packet boundary만 뜻한다. Public artifact boundary는 packet의 `pre_fix_pr_opened`다(§1) |
| `issue_id`, `issue_url` | `instance_id`의 숫자 suffix와 `https://github.com/<repo>/issues/<issue_id>` | 검증된 source issue 번호가 아니다. Materializer는 같은 번호를 fix PR 번호로 써서 `pulls/<n>` metadata로 cutoff를 검증한다(480/480 `verified`). v1은 source issue identity를 해석하지 않는다(§1 erratum) |
| `issue_created_at` | SWE-bench `created_at` 복사 | Issue 생성 시각으로 해석하지 않는다(§1) |
| `license_status` | 모든 행 `needs_review` | |

## 10. Annotation Guideline v0.5 Erratum

`docs/annotation_guideline.md` v0.5는 RR-A 패키지 생성기(`scripts/prepare_repo480_boundary_validation.py`)와
두 frozen manifest(`data/manifests/generated/repo480_boundary_validation_manifest_v1.json`,
`data/manifests/generated/repo480_bv_adjudication_manifest_v1.json`)가 SHA-256으로 검사하는 frozen
원본이며 annotator 패키지에 byte-identical 사본으로 배포됐다. 본문을 고치면 닫힌 패키지의 replay가
깨지므로, repo480에 적용할 때의 정정은 아래 표가 소유한다(2026-10-13 기록). Codebook의 label 정의와
판단 규칙 자체는 바뀌지 않는다.

| Guideline 위치 | Frozen 문구 | Repo480에서의 올바른 해석 | Canonical 근거 |
| --- | --- | --- | --- |
| §2.1 available evidence 목록과 cutoff 문장 | "public comments available at task creation time", 각 task가 `evidence_cutoff_timestamp`와 `evidence_cutoff_rule`을 가짐 | Task 단위 cutoff field가 없다(canonical 480행 중 0행). 경계는 component별이다: issue packet `benchmark_defined`, repository `base_commit`, public conversation/link `pre_fix_pr_opened`. v1은 source-issue identity를 해석하지 않아 public comment는 480행 모두 `unavailable`(`source_identity_unverified`)이며 annotator에게 제공되지 않았다 | `docs/repository_evidence_protocol.md` §2, 이 문서 §1 |
| §2.3 "maintainer comments after task creation" | Task creation 시각 기준 | `pre_fix_pr_opened` 이후 discussion으로 읽는다 | `docs/repository_evidence_protocol.md` §2 |
| §8 oracle-gap bullet과 oracle ambiguity 표 | `oracle_alternative_fix_exists` = ground-truth 외 behavior-equivalent fix의 plausibility, `behavior_target_space_size` = available + oracle evidence가 허용하는 target 수 | 이것은 legacy issue-packet oracle-gap pass의 의미다. Repo480 RQ2 Phase 2(guideline §8.1), RR-B control Phase 2, 원고 Method는 §8.1의 의미를 쓴다: alternative는 같은 behavior의 다른 diff가 아니라 frozen available evidence가 배제하지 못한 서로 다른 behavior target이고, target space는 oracle을 소급하지 않고 frozen available evidence가 허용한 수다. 두 의미의 값을 pooling하지 않으며, 앞으로의 repo480 oracle pass(예: RR-E, RR-F)는 §8.1 정의를 따른다 | guideline §8.1, 이 문서 §6.5 |
| §9 Expert Reference Panel | 최소 3인 expert panel, Krippendorff's alpha와 preregistered threshold gate | Legacy issue-packet `ep01`--`ep03` panel(`docs/expert_panel_plan.md`)의 규칙이다. 원고의 repo480 construct-validity 결과(`76/112`, `0/26`)는 세 독립 raw pass와 판정자 `repo480_cv_adj`의 consensus + adjudication을 썼고 alpha gate를 적용하지 않았다 | `docs/construct_validity_audit_protocol.md`, `results/pilot/repo480_construct_validity_analysis_v1.md` |
| §11 record 예시 | `"available_evidence_used"`의 `"repo_docs"`, `"component_boundary_ref": "packet.component_boundaries"` | 실제 값은 `docs`(canonical 34행)와 `"frozen_reviewer_view"`(480/480)다 | 이 문서 §6.1 |
