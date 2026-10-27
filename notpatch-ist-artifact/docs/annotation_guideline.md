# NotPatch Annotation Guideline v0.5

- **Status:** `active`
- **Authority:** available-only/oracle-gap annotation과 adjudication protocol
- **Last verified:** 2026-07-21

이 문서는 NotPatch annotation 운영 protocol입니다. 목표는 agent가 task 시점에 접근 가능한
artifact만으로 patch 방향을 결정할 수 있는지 평가하는 것입니다. Ground-truth patch를
맞혔는지, 특정 agent가 성공했는지, task가 일반적으로 어려운지는 primary label이 아닙니다.

Status (2026-07-14): v0.4는 기존 issue-packet/v6 결과의 provenance로 남는다. v0.5는
`swebench-repo480-v1` repository packet relabel 전에 고정한 protocol이며,
`docs/repository_evidence_protocol.md`와 `docs/task_schema.md` v0.2를 따른다. 현재 primary
label은 P0--P3이며 benchmark packaging 문제는 Q/D1 data-quality axis로 분리한다.

## 1. 핵심 질문

Annotator는 먼저 다음 질문에 답합니다.

> Frozen reviewer packet의 issue text, `base_commit` repository evidence, visible tests, docs,
> config, stack trace만 보고 ground-truth intent와 기능적으로 동등한 patch 방향을 과도한
> 추측 없이 결정할 수 있는가?

여기서 "기능적으로 동등한 patch 방향"은 exact diff가 아니라 behavior-level intent입니다. 함수 이름, internal refactoring, code style은 maintainer convention이나 hidden test가 강제하지 않는 한 exact match를 요구하지 않습니다. `decidability`는 계산이론적 의미가 아니라 available evidence에 상대적인 판단 가능성을 뜻합니다.

## 2. Evidence 규칙

### 2.1 Available evidence

Primary label을 붙일 때 볼 수 있는 정보입니다.

- issue title/body and public comments available at task creation time
- repository snapshot at the pre-fix commit
- deterministically retrieved source code from that exact snapshot
- visible tests already in the repository
- docs, examples, config files, dependency manifests
- stack traces, logs, reproduction commands included in the issue
- linked artifacts that an agent could reasonably access at task time

Available evidence에는 cutoff 이후 정보가 섞이면 안 됩니다. 각 task는 `evidence_cutoff_timestamp`와 `evidence_cutoff_rule`을 갖습니다. Fix PR 이후 comment, patch diff를 직접 암시하는 discussion, hidden test generation metadata, benchmark packaging note는 primary label 화면에서 제외합니다. "needs info" 같은 maintainer marker는 cutoff 이전 public comment일 때만 available evidence로 취급합니다.

Linked artifact는 task 시점에 public, no-login, no-secret 조건으로 접근 가능한 경우에만 available evidence입니다. 사라진 링크, private artifact, API key가 필요한 외부 서비스는 available evidence가 아니라 missing evidence로 기록합니다.

기존 benchmark seed-bundle label과 새 repository-packet label을 분리합니다. Problem statement
안의 URL, `#123` cross-reference, linked PR/issue는 materializer가 cutoff와 edit history를
검증해 `linked_artifacts`에 저장한 경우에만 근거로 사용합니다. Reviewer가 직접 link를
열거나 repository를 검색해 packet을 확장하지 않습니다. 새 primary pass는 issue-only seed
label을 보지 않으며, seed→repository transition은 adjudication 완료 뒤 분석 단계에서만
결합합니다.

### 2.2 Packet readiness와 retrieval sufficiency

Primary reviewer는 `packet_status = ready|ready_with_unavailable`이고 자신의
`reviewer_view_hash`가 batch manifest와 일치하는 packet만 판정합니다. `failed` packet은
labeling하지 않고 collector에게 반환합니다.

Category의 `empty`는 수집과 검색이 성공했지만 item이 없다는 관찰이고, `unavailable`은
private/404/cutoff/edit-history 문제로 task-time content를 복원하지 못한 상태이며, `failed`는
pipeline 오류입니다. Collector 실패를 P2/P3나 U-label로 바꾸지 않습니다.

Reviewer는 repository retrieval이 behavior target을 판단하기에 충분했는지를
`retrieval_sufficiency = sufficient|insufficient|unclear`로 별도 기록합니다. 불충분하면
필요한 path/symbol/evidence type을 `missing_repository_evidence`에 쓰되 임의 browsing으로
보충하지 않습니다. 이 field는 P-label을 자동 결정하지 않으며 retrieval-policy sensitivity와
false-pessimism audit에 사용합니다.

### 2.3 Hidden or post-hoc evidence

Primary label을 붙인 뒤에만 열 수 있습니다.

- ground-truth patch
- linked PR discussion after the fix
- maintainer comments after task creation
- hidden tests or generated test patch
- benchmark packaging metadata not visible to the agent
- baseline agent outcome or generated patch
- 기존 issue-packet/repository-packet label과 detector score

Post-hoc evidence는 primary label을 보정하는 데 쓰지 않습니다. 오직 oracle-gap label과 qualitative note를 기록하는 데만 사용합니다.

P0/P1 label이 단순한 annotator confidence로 붕괴하지 않도록, available-only pass에서 결정했다고 본 behavior-level patch direction을 별도 필드에 기록합니다. Oracle-gap pass에서는 이 예측 방향이 ground-truth intent와 맞았는지만 측정하고, primary label 자체는 사후 수정하지 않습니다.

## 3. Primary Label

| Label | 이름 | 판단 기준 |
| --- | --- | --- |
| P0 | Decidable | 합리적인 repair 방향이 명확하고, competent developer/agent가 같은 behavior target에 수렴할 가능성이 높음 |
| P1 | Decidable with bounded assumptions | 일부 빈칸은 있지만 가정이 좁고 검증 가능하며, behavior target이 하나로 수렴하거나 narrow variant가 local evidence로 선택/검증 가능함 |
| P2 | Clarification-needed | cutoff 이전 evidence로 배제할 수 없는 서로 다른 observable behavior target이 2개 이상이고, 추가 질문 없이는 하나를 고르기 어려움 |
| P3 | Not decidable from given artifacts | 핵심 재현 정보, 기대 동작, 환경, 외부 의존성, maintainer intent가 없어 실행 가능한 candidate patch direction 자체가 추측에 가까움 |

`P4`는 primary label로 사용하지 않습니다. Benchmark packaging이나 hidden test 문제가 있으면 data-quality label `Q1`을 사용합니다. 기존 schema와 호환이 필요할 때만 `Q1 -> legacy P4`로 export합니다.

Operational boundary:

- P0는 issue/docs/tests가 behavior target과 acceptance surface를 직접 지정하고, repo convention이 patch target을 바꾸지 않는 경우입니다.
- P1은 behavior target은 명확하지만 exact API contract, compatibility guard, serialization convention, UI layout convention, deployment environment 같은 bounded assumption이 남는 경우입니다. P1의 blocker는 "patch direction을 막는 blocker"가 아니라 bounded assumption source입니다.
- P1과 P2를 가를 때는 available evidence가 허용하는 behavior target 수를 먼저 봅니다. 같은 externally observable behavior로 수렴하거나, 1-2개의 좁은 variant가 남아도 local docs/tests/API convention으로 하나를 선택 또는 검증할 수 있으면 P1입니다. 외부 관찰 behavior, compatibility, security posture, user-facing semantics를 서로 다르게 바꾸는 후보가 2개 이상 남고 maintainer clarification 없이는 고를 수 없으면 P2입니다.
- P2와 P3를 가를 때는 plausible patch direction을 만들 수 있는지 봅니다. 후보는 만들 수 있지만 clarification이나 external artifact가 선택을 결정하면 P2입니다. core reproduction, workload, private data, external service schema, maintainer intent가 없어 narrow regression test나 실행 가능한 후보 자체를 책임 있게 만들 수 없으면 P3입니다.

## 4. Blocker Taxonomy

P1, P2, P3에는 하나 이상의 decidability blocker를 기록합니다. 다중 label을 허용하되 primary blocker를 하나 지정합니다.

| ID | 그룹 | 이름 | Observable criterion |
| --- | --- | --- | --- |
| U1 | Missing task evidence | Missing reproduction | 재현 입력, 명령, 데이터, stack trace가 없어 failure를 특정하기 어려움 |
| U2 | Missing task evidence | Ambiguous expected behavior | expected behavior가 여러 해석을 허용함 |
| U3 | Missing task evidence | Missing environment | OS, version, config, dependency, service 상태가 핵심인데 없음 |
| U4 | Evidence conflict | Conflicting evidence | issue, docs, visible tests, existing behavior가 서로 다른 요구를 냄 |
| U5 | Repository convention | Maintainer convention required | compatibility, public API, style, architecture policy 등 repo-specific 판단이 필요함 |
| U6 | Decision blocker | Non-functional tradeoff | performance/security/compatibility/UX 등 tradeoff 선택이 필요함 |
| U7 | Cross-project dependency | Cross-repo or data dependency | 외부 repo, dataset, model, service, upstream API 상태가 patch 방향을 결정함 |

Benchmark artifact mismatch는 pure decidability blocker가 아니라 data-quality blocker로 분리합니다.

| ID | Axis | 이름 | Observable criterion |
| --- | --- | --- | --- |
| D1 | Data quality | Benchmark artifact mismatch | hidden test 또는 benchmark packaging이 available issue intent와 어긋남 |

`D1`은 oracle-gap pass에서 `data_quality = Q1` 또는 `Q2`일 때만 사용합니다. Available-only pass에서는 hidden test mismatch를 확정하지 않고 `data_quality = Q2` 후보 note만 남깁니다. D1/Q1은 P2/P3 pure decidability prevalence에 섞지 않고, benchmark-invalid 또는 uncertain data-quality axis에서 따로 보고합니다.

Primary blocker는 다음 hierarchy로 고릅니다.

1. `U1`: decisive missing artifact가 reproduction input, workload, failure metric, stack trace, concrete observation인 경우.
2. `U2`: decisive missing artifact가 expected behavior나 semantic interpretation인 경우.
3. `U4`: cutoff 이전 available evidence 안에서 issue, docs, visible tests, existing behavior가 서로 충돌하고 그 충돌이 behavior target 선택을 막는 경우.
4. `U3`: environment, version, deployment, config, dependency version, platform이 patch direction을 바꾸는 경우.
5. `U7`: external repository, service, upstream API, dataset, remote schema가 patch direction을 결정하는 경우.
6. `U5`: local maintainer convention, public API policy, architecture style, compatibility norm이 decisive한 경우.
7. `U6`: 남은 선택이 performance, security, UX, compatibility, product preference 같은 non-functional tradeoff인 경우.

여러 blocker가 동시에 적용되면 behavior target을 결정하지 못하게 만드는 가장 이른 blocker를 primary로 두고, 나머지는 secondary로 기록합니다.

## 5. Secondary Axes

| Axis | 값 | 설명 |
| --- | --- | --- |
| Data quality | Q0 valid, Q1 benchmark-invalid, Q2 uncertain | benchmark/test packaging 문제가 있는지 |
| Oracle gap | no_gap, missing_info, hidden_constraint, test_mismatch, maintainer_context, external_dependency | post-hoc evidence가 보여준 gap |
| Task difficulty | low, medium, high | available evidence가 충분해도 구현이 얼마나 어려운지 |
| Outcome risk | low, medium, high | 특정 patch 후보가 있을 때 wrong/overfit 위험 |
| Clarification target | reproduction, expected_behavior, environment, convention, tradeoff, dependency, benchmark_artifact | P2/P3에서 어떤 질문이 필요한지 |
| Oracle ambiguity | `oracle_alternative_fix_exists`, `behavior_target_space_size` | ground-truth patch가 유일한 behavior target인지 |
| P2/P3 false-pessimism diagnostic | `oracle_direction_in_candidate_set`, `oracle_revealed_missing_evidence`, `available_evidence_unique_in_hindsight` | P2/P3가 실제 missing evidence 때문인지, 보수적 라벨링 때문인지 진단 |
| External non-decidability explanation | low_priority, ownership_dispute, maintainer_absence, decidable_but_unfixed, unclear | long-open/non-patch external issue의 confound 분리 |

## 6. Predicted Direction Template

P0/P1에는 `predicted_direction`을 반드시 다음 세 요소로 기록합니다.

```text
Component/function:
Input condition or trigger:
Observable behavior change:
```

좋은 예시는 "Component/function: metadata parser. Input condition or trigger: optional metadata key is absent. Observable behavior change: return an empty metadata object instead of crashing."처럼 behavior-level target을 드러냅니다. Exact diff, line number, refactoring style은 쓰지 않습니다. P1에서 남은 bounded assumption은 `rationale` 또는 `missing_evidence_needed`에 따로 쓰고, `predicted_direction`을 서로 배타적인 여러 behavior target처럼 부풀리지 않습니다. P2에는 같은 template으로 가능한 candidate direction을 2개 이상 쓰고, cutoff 이전 evidence가 왜 어느 후보도 배제하지 못하는지 기록합니다. P3는 후보가 여러 개인 경우뿐 아니라, 외부 API endpoint, private data, maintainer acceptance처럼 필수 evidence가 없어 단일 후보 방향조차 실행 가능한 patch로 만들 수 없는 경우도 포함하므로 blocked candidate direction을 1개 이상 기록합니다. 따라서 P3의 blocked candidate direction count는 "실행 가능한 behavior target 수"가 아니라 audit/provenance field입니다.

Predicted direction disagreement는 exact string이 아니라 template의 세 축으로 비교합니다. 같은 component/function, 같은 input condition/trigger, 같은 observable behavior change를 가리키면 wording-only disagreement입니다. 세 축 중 하나가 더 좁거나 빠져 있으면 `partial_match` 또는 direction-overlap note로 분리하고, primary label disagreement로 자동 승격하지 않습니다.

## 7. Decision Tree

0. Packet이 labelable한가?
   - `packet_status = failed`이거나 batch의 `reviewer_view_hash`와 다르면 판정하지 않고 반환합니다.
   - `ready_with_unavailable`이면 unavailable reason을 읽고, collector failure와 substantive
     missing evidence를 구분합니다.
1. Task artifact가 benchmark packaging 또는 hidden test mismatch로 왜곡되어 있는가?
   - Available evidence만으로 알 수 없으면 primary P0-P3를 먼저 붙이고, oracle pass에서 Q1/Q2와 D1을 기록합니다.
2. Issue가 어떤 behavior를 바꾸려는지 식별 가능한가?
   - 아니면 P3, U2 또는 U1.
3. Failure나 feature request를 재현하거나 관찰할 최소 artifact가 있는가?
   - 없지만 expected behavior가 매우 명확하면 P1.
   - 없고 여러 원인이 가능하면 P2/P3, U1.
4. Expected behavior가 하나의 behavior target으로 수렴하는가?
   - cutoff 이전 evidence가 서로 다른 observable behavior target 2개 이상을 모두 허용하고 어느 후보도 배제하지 못하면 P2, U2.
   - 1-2개의 narrow variant가 남아도 local docs/tests/API contract로 하나를 선택 또는 검증할 수 있거나 externally observable behavior가 같으면 P1로 둘 수 있습니다.
   - 후보가 많아 보이더라도 docs, visible tests, API contract, issue wording이 하나를 명확히 배제하면 P0/P1로 둘 수 있습니다.
   - missing reproduction만으로 P2로 내리지 않습니다. failure mode와 behavior target이 concrete enough해서 narrow regression test를 만들 수 있으면 P1을 유지합니다.
5. Environment/config/dependency가 patch 방향을 바꿀 수 있는가?
   - 그렇고 정보가 없으면 P2/P3, U3/U7.
6. Existing docs/tests/conventions가 issue와 충돌하는가?
   - 그렇다면 P2, U4. 충돌이 hidden test에서만 드러나면 oracle pass에서 Q1/D1.
7. Maintainer policy나 non-functional tradeoff 없이는 결정을 내릴 수 없는가?
   - repo convention이면 U5, tradeoff이면 U6.
8. 위 문제가 없고 patch direction이 좁게 정해지면 P0 또는 P1.
   - P0/P1이면 `predicted_direction` template을 채웁니다.
   - P2이면 가능한 후보 방향 2개 이상과 어느 evidence가 없어서 고를 수 없는지 기록합니다.
   - P3이면 blocked candidate direction 1개 이상과 patch를 실행 불가능하게 만드는 missing evidence를 기록합니다.
9. Repository retrieval이 판단에 충분했는가?
   - 충분/불충분/불명확을 primary label과 별도 field로 기록합니다.
   - 불충분해도 임의 file/web search를 하지 않고 필요한 evidence type을 기록합니다.

## 8. Oracle-Gap Pass

Primary label을 저장한 뒤 ground-truth patch, PR discussion, hidden tests를 확인합니다. 이 단계에서는 다음만 기록합니다.

- primary label이 사후 evidence와 어떻게 달라 보이는지에 대한 note
- issue에서 누락된 정보
- hidden test가 issue 밖 behavior를 요구했는지
- maintainer discussion이 tradeoff 또는 convention을 결정했는지
- data-quality label Q0/Q1/Q2
- data-quality blocker D1 여부
- P0/P1의 `predicted_direction`이 oracle evidence와 behavior-level로 일치하는지
- P2/P3의 candidate directions가 oracle direction을 포함했는지
- P2/P3에서 기록한 missing evidence가 oracle pass에서 실제로 드러났는지
- hindsight에서 available evidence만으로도 unique direction이 가능했다고 볼 수 있는지
- ground-truth 외 behavior-equivalent fix가 존재하는지
- behavior target space가 하나인지, 2-3개인지, 많은지

Primary label을 변경해야 할 정도로 available evidence를 잘못 읽었다면, raw label은 보존하고 adjudication log에 correction reason을 남깁니다. 단순히 ground-truth patch를 보고 "이제 명확해졌다"는 이유로 P2/P3를 P0/P1로 바꾸지 않습니다.

`predicted_direction_match` 값은 다음 중 하나입니다.

| 값 | 의미 |
| --- | --- |
| match | predicted direction이 ground-truth behavior intent와 기능적으로 동등함 |
| partial_match | 핵심 방향은 맞지만 중요한 condition, API surface, edge case가 빠짐 |
| mismatch | predicted direction이 ground-truth behavior intent와 다름 |
| not_assessable | oracle evidence 자체가 불충분하거나 benchmark artifact가 왜곡되어 판단 불가 |

`partial_match`는 다음 행동 기준으로 제한합니다.

- Ground-truth가 특정 함수 시그니처나 internal structure를 도입했지만, predicted direction이 같은 externally observable behavior를 다른 구현 구조로 기술한 경우.
- Predicted direction이 올바른 component와 behavior change를 잡았지만, oracle에서 드러난 minor edge case나 compatibility guard를 빠뜨린 경우.
- 다음은 `partial_match`가 아니라 `mismatch`입니다: ground-truth가 바꾼 condition을 반대로 기술한 경우, expected behavior를 다른 API contract로 해석한 경우, issue의 핵심 failure mode와 다른 component를 고친다고 예측한 경우.

Decidability label accuracy의 primary metric은 available-only P0/P1 중 `match` 비율로만 계산합니다. `match + partial_match`는 sensitivity metric입니다. 이 값은 construct validity diagnostic이지 primary label 보정 절차가 아닙니다.

Oracle ambiguity 필드는 다음처럼 기록합니다.

| 필드 | 값 | 의미 |
| --- | --- | --- |
| `oracle_alternative_fix_exists` | yes, no, unclear | ground-truth 외 behavior-equivalent fix가 plausible한지 |
| `behavior_target_space_size` | 1, 2-3, many, unclear | available + oracle evidence가 허용하는 behavior target 수 |

P2/P3 false-pessimism diagnostic은 다음처럼 기록합니다.

| 필드 | 값 | 의미 |
| --- | --- | --- |
| `oracle_direction_in_candidate_set` | yes, no, unclear, not_applicable | available-only pass의 candidate directions 중 oracle direction이 있었는지 |
| `oracle_revealed_missing_evidence` | yes, partial, no, unclear, not_applicable | oracle pass가 P2/P3 판단을 정당화하는 missing evidence를 실제로 드러냈는지 |
| `available_evidence_unique_in_hindsight` | yes, no, unclear, not_applicable | oracle을 본 뒤에도 cutoff 이전 evidence만으로 unique patch direction이 충분히 가능했다고 판단되는지 |

`available_evidence_unique_in_hindsight = yes`는 P2/P3 false-pessimistic candidate입니다. 이 값은 primary label을 자동으로 바꾸지 않지만, pilot go/no-go와 prevalence sensitivity에서 별도 보고합니다. H1a prevalence report에서는 raw P2/P3 rate와 함께 이 candidate를 P0/P1로 재분류한 observed corrected count와 직접 CI를 보고하고, preregistered conservative formula는 sensitivity note로만 유지합니다. 단순히 oracle patch가 candidate set 중 하나였다는 이유만으로 `yes`를 부여하지 않습니다. Cutoff 이전 evidence가 실제로 다른 plausible direction을 배제했는지 확인해야 합니다.

### 8.1 RQ2 Two-Phase Blind Masking Pass

RQ2 random-frame panel은 canonical repository P2/P3가 동결된 뒤 coordinator가 public outcome을
결합해 benchmark-solved denominator를 고정합니다. Outcome join은 reviewer package 밖에 두며,
denominator selection 뒤에도 reviewer에게 agent identity, patch, score 또는 resolved 횟수를
공개하지 않습니다.

Phase 1은 같은 frozen reviewer view만 사용하고 다음 evidence를 물리적으로 제외합니다.

- canonical/이전 P-label, blocker, rationale와 candidate directions
- ground-truth patch, `test_patch`, hidden test, hints와 fix PR discussion
- repair-agent outcome와 다른 Phase 1 reviewer의 판단

각 reviewer는 behavior-level `candidate_directions`, 후보 중 하나를 정하는
`deciding_missing_evidence`, available evidence pointer와 `phase1_behavior_determinate`를 먼저
고정합니다. Candidate는 component/function, input condition/trigger, observable behavior change의
세 요소로 기록합니다. `determinate = yes`이면 behavior target은 하나여야 합니다. `no` 또는
`unclear`이면 결정에 필요한 evidence를 비우지 않습니다. P3 성격의 row는 blocked candidate
하나와 decisive missing evidence를 기록할 수 있습니다.

두 independent Phase 1 return이 모두 hash-linked 원본으로 보존되고 completeness 검사를 통과한
뒤에만 Phase 2를 엽니다. Phase 2에서 각 reviewer는 자신의 잠긴 candidate set과 oracle evidence를
보고 다음을 판정합니다.

- `oracle_direction_summary`
- `oracle_direction_in_candidate_set = yes|no|unclear`
- `oracle_revealed_missing_evidence = yes|partial|no|unclear`
- `oracle_alternative_fix_exists = yes|no|unclear`
- `available_evidence_unique_in_hindsight = yes|no|unclear`
- `behavior_target_space_size = 1|2-3|many|unclear`
- data-quality/benchmark-artifact note

Phase 2 package는 reviewer별 standalone 디렉터리로 분리하고 상대 reviewer의 Phase 1 판단을
포함하지 않습니다. `oracle_alternative_fix_exists`의 alternative는 같은 observable behavior를
구현하는 다른 diff가 아니라 available evidence가 배제하지 못한 서로 다른 behavior target입니다.
`behavior_target_space_size` 역시 oracle을 task-time evidence로 소급하지 않고 frozen available
evidence가 허용한 target space를 기록합니다. Data quality는 mismatch 없음 `Q0`, benchmark-invalid
또는 mismatch `Q1`, 불확실 `Q2`로 기록하고 모든 row에 근거 note를 남깁니다.

Strict masking call은 reviewer가 별도 직관 label로 입력하지 않고
`oracle_alternative_fix_exists = yes`이면서
`available_evidence_unique_in_hindsight = no`일 때 결정론적으로 유도합니다.
`oracle_direction_in_candidate_set`은 hidden oracle가 Phase 1 candidate 중 하나를 선택했다는
mechanism audit로 별도 보고합니다. 두 pass의 field-level/strict-call agreement와 제3 reviewer
adjudication을 모두 보존하고, disagreement를 모두 non-masked로 두는 sensitivity를 함께
보고합니다. Phase 2 결과는 available-only primary label을 수정하지 않습니다.

제3 reviewer `repo480_rq2_adj`는 두 Phase 2 원본이 모두 hash 보존된 뒤에만 두 raw judgment,
각 reviewer의 locked Phase 1과 동일 oracle evidence를 봅니다. Worklist는 categorical controlled
field가 다른 row만 포함하고 narrative wording 차이는 queue에 넣지 않습니다. Adjudicator는
불일치 field별 값을 기록하며 raw return을 덮어쓰지 않고 strict masking call을 직접 입력하지
않습니다. 일부 field를 판정할 수 없으면 그 값을 `unresolved`로 보존하고 conservative
dispute-as-nonmasked sensitivity에서 non-masked로 처리합니다. Prior/canonical P-label,
repair-agent identityㆍpatchㆍscoreㆍoutcome과 package 밖 repository/web evidence는 계속 금지합니다.

## 9. Expert Reference Panel

Oracle-gap pass의 `predicted_direction_match`는 최소 3명의 expert reference panel이 독립 판정합니다. 공개 profile은 동료 연구자ㆍ프로그래밍 경력 8년으로만 기록하고 그 밖의 경력과 affiliation은 공개하지 않습니다. 필요한 task capability와 pass별 evidence access는 공개 profile이 아니라 registry attestation과 request의 access rule로 통제합니다. Panel은 raw available-only label을 볼 수 있지만 agent outcome은 보지 않습니다.

Expert는 `predicted_direction`과 oracle direction을 같은 template의 세 요소(component/function, input condition, observable behavior change)로 비교합니다. Agreement는 Krippendorff's alpha와 raw disagreement table로 보고합니다. Expert agreement가 preregistered threshold에 못 미치면 `predicted_direction_match` 기반 label accuracy claim을 primary에서 제외하고 qualitative diagnostic으로만 사용합니다.

Expert calibration에는 `partial_match`와 `mismatch`의 borderline example 10-15개를 별도 packet으로 포함합니다. 특히 "올바른 component와 behavior change를 잡았지만 minor edge case를 빠뜨린 경우"와 "ground-truth가 바꾼 condition을 반대로 기술한 경우"를 paired example로 넣어 panel disagreement가 가장 흔한 경계를 먼저 맞춥니다.

## 10. Adjudication

두 annotator의 label이 다르면 다음 순서로 조정합니다.

1. 서로 어떤 available evidence를 사용했는지 확인합니다.
2. Post-hoc evidence를 근거로 primary label을 바꾸려는 주장이 없는지 확인합니다.
3. P0/P1 vs P2/P3 불일치이면 "서로 다른 observable behavior target이 몇 개인가"를 중심으로 토론합니다.
4. U-label 불일치이면 primary blocker 하나와 secondary blockers를 분리합니다.
5. P0/P1 annotator가 서로 다른 `predicted_direction`을 기록했다면, label agreement와 direction agreement를 분리해 기록합니다.
6. Binary-boundary disagreement는 shared evidence pointer와 decisive missing/conflicting evidence pointer를 최소 하나씩 기록합니다. Evidence pointer는 cutoff 이전 available evidence를 지목해야 하며, post-hoc evidence는 pointer나 boundary reason으로 쓰지 않습니다. 특정 evidence pointer를 지목할 수 없으면 `calibration_only` note를 남깁니다.
7. 합의가 안 되면 `adjudication_status = unresolved`로 남기고 detector training에서 제외하는 sensitivity analysis를 수행합니다.

`repo480_available_v1`에서는 두 raw pass가 같은 `packet_id`, `packet_revision`,
`reviewer_view_hash`를 사용했는지 먼저 검사합니다. 다르면 label disagreement가 아니라 packet
provenance failure이며 adjudication하지 않습니다. `repo480_adj`는 두 raw pass와 frozen
available packet만 열고 oracle, agent outcome, detector score, 기존 seed label을 보지 않습니다.
Adjudication 뒤에도 raw record를 덮어쓰지 않습니다.

## 11. Annotation Record Schema

```json
{
  "task_id": "repo__issue_id",
  "annotator_id": "repo480_r1",
  "annotation_batch_id": "repo480_available_v1",
  "pass": "available_only",
  "packet_policy_id": "swebench-repo480-v1",
  "packet_id": "repo__issue_id@swebench-repo480-v1",
  "packet_revision": 1,
  "reviewer_view_hash": "sha256",
  "registry_snapshot_sha256": "sha256",
  "primary_label": "P2",
  "primary_blocker": "U2",
  "secondary_blockers": ["U5"],
  "data_quality_blocker": null,
  "data_quality": "Q0",
  "task_difficulty": "medium",
  "clarification_target": "expected_behavior",
  "predicted_direction": null,
  "predicted_direction_template": {
    "component_or_function": null,
    "input_condition_or_trigger": null,
    "observable_behavior_change": null
  },
  "candidate_directions": [
    "Return an empty list for missing optional metadata.",
    "Raise a validation error when optional metadata is absent."
  ],
  "missing_evidence_needed": [
    "expected behavior for absent optional metadata"
  ],
  "available_evidence_used": [
    "issue_body",
    "retrieved_code",
    "repo_docs",
    "visible_tests"
  ],
  "retrieval_sufficiency": "sufficient",
  "missing_repository_evidence": [],
  "rationale": "Expected behavior admits two plausible interpretations...",
  "oracle_gap": null,
  "predicted_direction_match": null,
  "oracle_direction_summary": null,
  "oracle_direction_in_candidate_set": null,
  "oracle_revealed_missing_evidence": null,
  "available_evidence_unique_in_hindsight": null,
  "oracle_alternative_fix_exists": null,
  "behavior_target_space_size": null,
  "non_decidability_explanation": null,
  "component_boundary_ref": "packet.component_boundaries",
  "available_evidence_used_with_provenance": [],
  "adjudication_status": "raw"
}
```

Oracle pass는 같은 `task_id`에 대해 `pass = "oracle_gap"`으로 별도 record를 남깁니다.
Repository packet revision이 바뀌면 `reviewer_view_hash` linkage를 다시 확인하고, 기존
available/oracle record의 재사용 여부를 deviation log에 남깁니다.

## 12. Repository Relabel Gates

P0-3 available-only relabel을 시작하기 전에 다음을 확인합니다.

- 480 task의 reviewer-view packet/hash list가 freeze됐고 `failed` packet이 분리됐는가?
- `repo480_r1`, `repo480_r2`, `repo480_adj`의 공개 profile 정책(동료 연구자ㆍ프로그래밍
  경력 8년ㆍ추가 경력/affiliation 비공개), 비식별 reference, prior exposure, Python review
  capability와 blinding 조건이 registry snapshot에 채워졌는가?
- 두 raw reviewer가 같은 packet revision을 받고 seed label, oracle, detector, outcome을 보지
  않는가?
- Calibration에서 P0/P1 `predicted_direction`, P2 candidate directions, P3 blocked direction,
  retrieval-sufficiency field를 일관되게 채울 수 있는가?

Reviewer 선정과 배정 적합성은 coordinator가 보증한다. Reviewer request는 위 수행 규칙과
반환 형식만 포함하며, reviewer 경력ㆍaffiliationㆍ자격ㆍ관여ㆍ사전 노출ㆍblinding에 관한
별도 배정 questionnaire를 요구하지 않는다. 실제 protocol deviation이 발생하면 숨기지 않고
반환 artifact와 deviation log에 기록한다.

Relabel과 adjudication 뒤에는 threshold 통과 여부만으로 결과를 숨기지 않고 다음을 모두
보고합니다.

- P0/P1 vs P2/P3 binary agreement, 4-class agreement, batch/repository별 disagreement
- seed issue-packet → repository-packet label transition matrix
- packet availability와 retrieval sufficiency에 따른 label/sensitivity
- P0/P1 match-only 및 match+partial direction diagnostic과 mismatch rate
- P2/P3 hindsight uniqueness와 dispute-as-conservative sensitivity
- raw/adjudicated numerator, denominator, effect size와 confidence interval

Agreement가 낮거나 retrieval-insufficient 비율이 높으면 label을 임의로 고치지 않고 protocol
deviation, calibration revision, claim 축소 중 어떤 조치를 택했는지 기록합니다.
