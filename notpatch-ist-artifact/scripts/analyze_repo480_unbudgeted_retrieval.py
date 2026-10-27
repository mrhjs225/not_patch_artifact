#!/usr/bin/env python3
"""Analyze the accepted RR-F expanded-view audit as a seven-row sensitivity (protocol section 4)."""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from collections import Counter
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from notpatch.canonical import canonical_json_bytes, sha256_file  # noqa: E402
from analyze_repo480_prevalence import _rate  # noqa: E402
from selfcheck_repo480_retrieval_audit import (  # noqa: E402
    ARCHIVE_NAME, MANIFEST_NAME, WORKLIST_NAME, load_rows, validate,
)

P23 = {"P2", "P3"}
COVERAGE = ("non_repository", "already_in_frozen_packet", "file_not_in_frozen_packet",
            "lines_not_fully_in_frozen_packet")
ROLES = ("new_decisive_evidence", "corroboration_only", "still_insufficient", "unclear")
CLAIM_BOUNDARY = [
    "One expanded-only expert pass with no paired frozen-view pass by the same expert: label changes mix evidence widening with rule and case interpretation, so they are not causal retrieval effects.",
    "Evidence roles are the expert's explanatory self-assessment; only rows marked new_decisive_evidence cite decisive text outside the frozen packet.",
    "Only frozen P2/P3 rows flagged insufficient/unclear were re-examined, so the substitution can only lower the numerator; (26-k)/480 is a what-if, neither a corrected prevalence nor a bound.",
    "Wilson intervals over seven rows from two repositories are descriptive; no population reproducibility or significance claim.",
    "R07's self-reported search-derivation deviation stays in all-row results and is excluded only in the deviation sensitivity; null exposure notes are self-report, not verified absence of exposure.",
    "Validation-panel and RQ2 cross-references were added after the protocol was frozen; they are descriptive and do not recompute any RQ2 masking call.",
    "Frozen available-only labels, 26/480, 0.094, 12/12 and 10/12 are unchanged; public comments and links stay unavailable as in the frozen packet.",
]


def binary(label: str | None) -> str | None:
    return None if label is None else ("P2/P3" if label in P23 else "P0/P1")


def subset(rows: list[dict]) -> dict:
    return {"n": len(rows), "items": [r["item_id"] for r in rows],
            "boundary_changes": sum(r["boundary_change"] for r in rows),
            "exact_label_changes": sum(r["exact_label_change"] for r in rows)}


def strata(rows: list[dict], key) -> dict:
    return {name: subset([r for r in rows if key(r) == name]) for name in sorted({key(r) for r in rows})}


def what_if(frame: list[dict], audited: dict, use: set, q0: str | None = None) -> dict:
    """Substitute expanded labels for used audited rows; q0 picks the Q0 membership source."""
    numerator = denominator = 0
    for row in frame:
        hit = audited.get(row["task_id"])
        expanded = hit is not None and hit["item_id"] in use
        label = hit["expanded_label"] if expanded else row["final_label"]
        quality = hit["expanded_data_quality"] if expanded and q0 == "expanded" else row["data_quality"]
        if q0 is not None and quality != "Q0":
            continue
        denominator += 1
        numerator += label in P23
    return {"count": numerator, "denominator": denominator, "proportion": round(numerator / denominator, 6)}


def revalidate(setup: dict, archive: Path, canonical: Path) -> list[dict]:
    """Re-run the frozen package validator on a minimal package rebuilt from tracked records."""
    worklist = b"".join(canonical_json_bytes(w) for w in setup["work_items"])
    with tempfile.TemporaryDirectory(prefix="rrf-analysis-") as raw:
        package = Path(raw)
        (package / WORKLIST_NAME).write_bytes(worklist)
        if sha256_file(package / WORKLIST_NAME) != setup["package_files"][WORKLIST_NAME]:
            raise ValueError("worklist rebuilt from the setup manifest differs from the package")
        os.symlink(archive, package / ARCHIVE_NAME)
        (package / MANIFEST_NAME).write_bytes(canonical_json_bytes({"row_count": setup["row_count"], "readonly_sha256": {
            WORKLIST_NAME: setup["package_files"][WORKLIST_NAME], ARCHIVE_NAME: setup["archive_sha256"]}}))
        return validate(package, canonical)


def analyze(args: argparse.Namespace) -> tuple[dict, list[dict]]:
    date.fromisoformat(args.analyzed_on)
    inputs = {}

    def checked(path: str | Path, expected: str | None = None) -> Path:
        actual = sha256_file(ROOT / path)
        if expected is not None and actual != expected:
            raise ValueError(f"hash mismatch: {path}")
        inputs[str(path)] = actual
        return ROOT / path

    accepted = json.loads(checked(args.returns_manifest).read_text())
    if (accepted["batch_id"], accepted["annotator_id"]) != ("repo480_unbudgeted_retrieval_v1", "repo480_retrieval_r1"):
        raise ValueError("unexpected accepted batch/annotator")
    setup = json.loads(checked(accepted["setup_manifest"]["ref"], accepted["setup_manifest"]["sha256"]).read_text())
    selection = load_rows(checked(accepted["selection"]["ref"], setup["selection_sha256"]))
    archive = checked(setup["archive_ref"], setup["archive_sha256"])
    checked(accepted["acceptance_script"]["ref"], accepted["acceptance_script"]["sha256"])
    canonical = checked(accepted["canonical_ref"], accepted["sha256"])
    returned = load_rows(canonical)
    audit = revalidate(setup, archive, canonical)
    if audit != accepted["citation_audit"]:
        raise ValueError("accepted citation audit does not reproduce")
    prevalence_ref = "results/pilot/repo480_available_v1_prevalence_rows.jsonl"
    frame = load_rows(checked(prevalence_ref, setup["inputs"][prevalence_ref]))
    if [(r["item_id"], r["task_id"]) for r in selection] != [(r["item_id"], r["task_id"]) for r in returned]:
        raise ValueError("selection and return identities differ")
    frozen = {r["task_id"]: r for r in frame}
    if any(frozen[r["task_id"]]["final_label"] != r["final_label"] for r in selection):
        raise ValueError("selection labels differ from the frozen frame")
    panel = {r["task_id"]: r for r in load_rows(checked(args.validation_rows))}
    rq2 = {r["task_id"]: r for r in load_rows(checked(args.rq2_rows))}
    control = {r["task_id"]: r for r in load_rows(checked(args.control_rows))
               if r["arm"] == "solved_p2p3_treated"}
    if set(rq2) != set(control):
        raise ValueError("RQ2 frame and matched treated arm differ")

    rows = []
    for sel, ret, check in zip(selection, returned, audit, strict=True):
        assessable = ret["annotation_status"] != "not_assessable"
        coverage = Counter(check["reference_coverage"])
        member = sel["task_id"] in rq2
        rows.append({
            "schema_version": "repo480-expanded-retrieval-audit-row-v1",
            "item_id": sel["item_id"], "task_id": sel["task_id"], "repository": sel["repository"],
            "ordinal": sel["ordinal"], "in_nested_120": sel["in_nested_120"],
            "original_label": sel["final_label"], "original_raw_labels": [sel["r1_label"], sel["r2_label"]],
            "original_retrieval_sufficiency": sel["retrieval_sufficiency"],
            "original_data_quality": sel["data_quality"],
            "annotation_status": ret["annotation_status"], "assessable": assessable,
            "expanded_label": ret["expanded_label"], "expanded_data_quality": ret["data_quality"],
            "expanded_retrieval_sufficiency": ret["expanded_retrieval_sufficiency"],
            "evidence_assessment": ret["evidence_assessment"],
            "transition": f"{sel['final_label']}->{ret['expanded_label'] if assessable else 'not_assessable'}",
            "exact_label_change": assessable and ret["expanded_label"] != sel["final_label"],
            "boundary_change": assessable and ret["expanded_label"] not in P23,
            "candidate_directions": len(ret["candidate_directions"]),
            "reference_count": len(check["reference_coverage"]),
            "reference_coverage": {name: coverage[name] for name in COVERAGE},
            "outside_packet_references": coverage["file_not_in_frozen_packet"] + coverage["lines_not_fully_in_frozen_packet"],
            "search_steps": check["search_steps"],
            "protocol_deviation": ret["protocol_deviation"] is not None,
            "exposure_note": ret["exposure_note"] is not None,
            "post_hoc_cross_reference": {
                "validation_panel_label": panel[sel["task_id"]]["independent_primary_label"] if sel["task_id"] in panel else None,
                "rq2_frame_member": member,
                "rq2_original_strict_call": rq2[sel["task_id"]]["strict_masking_call"] if member else None,
                "rq2_matched_treated_strict_call": control[sel["task_id"]]["strict_masking_call"] if member else None,
            },
        })

    assessed = [r for r in rows if r["assessable"]]
    clean = [r for r in assessed if not r["protocol_deviation"] and not r["exposure_note"]]
    audited = {r["task_id"]: r for r in rows}
    changed = sum(r["boundary_change"] for r in assessed)
    transitions = {}
    for r in rows:
        source, target = r["transition"].split("->")
        transitions.setdefault(source, Counter())[target] += 1
    new_decisive = [r for r in rows if r["evidence_assessment"] == "new_decisive_evidence"]
    if any(r["outside_packet_references"] == 0 for r in new_decisive):
        raise ValueError("new decisive evidence without an outside-packet citation")
    expanded_p01 = [r for r in rows if r["post_hoc_cross_reference"]["rq2_frame_member"] and r["boundary_change"]]
    remaining = [t for t in rq2 if t not in {r["task_id"] for r in expanded_p01}]
    result = {
        "schema_version": "repo480-expanded-retrieval-sensitivity-v1", "status": "expanded-view-sensitivity",
        "analyzed_on": args.analyzed_on, "policy_id": setup["policy_id"], "batch_id": setup["batch_id"],
        "inputs": inputs,
        "denominators": {"selected_rows": len(selection), "returned_rows": len(returned),
                         "assessable_rows": len(assessed), "not_assessable_items": [r["item_id"] for r in rows if not r["assessable"]],
                         "excluded_rows": []},
        "transition_counts": {source: dict(sorted(target.items())) for source, target in sorted(transitions.items())},
        "boundary_change_p23_to_p01": {"assessable": _rate(changed, len(assessed)),
                                       "all_selected_unassessable_as_unchanged": _rate(changed, len(rows))},
        "exact_label_change": _rate(sum(r["exact_label_change"] for r in assessed), len(assessed)),
        "retained_p23": _rate(sum(not r["boundary_change"] for r in assessed), len(assessed)),
        "strata": {
            "original_retrieval_sufficiency": strata(rows, lambda r: r["original_retrieval_sufficiency"]),
            "original_data_quality": strata(rows, lambda r: r["original_data_quality"]),
            "expanded_data_quality": strata(rows, lambda r: r["expanded_data_quality"]),
            "repository": strata(rows, lambda r: r["repository"]),
            "evidence_assessment": {role: subset([r for r in rows if r["evidence_assessment"] == role]) for role in ROLES},
            "expanded_retrieval_sufficiency": strata(rows, lambda r: r["expanded_retrieval_sufficiency"]),
        },
        "reference_coverage": {name: sum(r["reference_coverage"][name] for r in rows) for name in COVERAGE},
        "reference_count": sum(r["reference_count"] for r in rows),
        "search_steps": sum(r["search_steps"] for r in rows),
        "new_decisive_rows_cite_outside_packet": True,
        "deviation_and_exposure": {
            "protocol_deviation_items": [r["item_id"] for r in rows if r["protocol_deviation"]],
            "exposure_note_items": [r["item_id"] for r in rows if r["exposure_note"]],
            "excluded_sensitivity": {**subset(clean), "boundary_change": _rate(sum(r["boundary_change"] for r in clean), len(clean))},
        },
        "q0_sensitivity": {
            "original_q0_membership": subset([r for r in rows if r["original_data_quality"] == "Q0"]),
            "expanded_q0_membership": subset([r for r in rows if r["expanded_data_quality"] == "Q0"]),
            "both_q0": subset([r for r in rows if r["original_data_quality"] == r["expanded_data_quality"] == "Q0"]),
        },
        "partial_substitution_what_if": {
            "frozen_reference": what_if(frame, audited, set()),
            "all_assessable_rows": what_if(frame, audited, {r["item_id"] for r in assessed}),
            "excluding_deviation_and_exposure_rows": what_if(frame, audited, {r["item_id"] for r in clean}),
            "q0_frame_frozen_reference": what_if(frame, audited, set(), q0="frozen"),
            "q0_frame_frozen_membership": what_if(frame, audited, {r["item_id"] for r in assessed}, q0="frozen"),
            "q0_frame_expanded_membership": what_if(frame, audited, {r["item_id"] for r in assessed}, q0="expanded"),
            "note": "Unaudited and not-assessable rows keep frozen values. Not a corrected prevalence, estimate, or bound.",
        },
        "post_hoc_cross_reference": {
            "prespecified": False,
            "validation_panel_labels": dict(Counter(r["post_hoc_cross_reference"]["validation_panel_label"] for r in rows)),
            "validation_panel_on_boundary_changes": dict(Counter(binary(r["post_hoc_cross_reference"]["validation_panel_label"])
                                                                 for r in assessed if r["boundary_change"])),
            "validation_panel_on_retained_rows": dict(Counter(binary(r["post_hoc_cross_reference"]["validation_panel_label"])
                                                              for r in assessed if not r["boundary_change"])),
            "rq2_frame_size": len(rq2),
            "rq2_members_audited": [r["item_id"] for r in rows if r["post_hoc_cross_reference"]["rq2_frame_member"]],
            "rq2_members_expanded_p01": [r["item_id"] for r in expanded_p01],
            "rq2_rows_not_reexamined": len([t for t in rq2 if t not in audited]),
            "rq2_strict_calls_without_expanded_p01_rows": {
                "original_panel": f"{sum(rq2[t]['strict_masking_call'] == 'yes' for t in remaining)}/{len(remaining)}",
                "matched_panel_treated": f"{sum(control[t]['strict_masking_call'] == 'yes' for t in remaining)}/{len(remaining)}"},
        },
        "acceptance_notes": accepted["acceptance_notes"],
        "claim_boundary": CLAIM_BOUNDARY,
    }
    checked("scripts/analyze_repo480_unbudgeted_retrieval.py")
    return result, rows


def markdown(result: dict, rows: list[dict]) -> str:
    whatif = result["partial_substitution_what_if"]
    boundary = result["boundary_change_p23_to_p01"]["assessable"]
    cross = result["post_hoc_cross_reference"]
    dev = result["deviation_and_exposure"]["excluded_sensitivity"]
    q0 = result["q0_sensitivity"]
    ci = lambda rate: f"{rate['count']}/{rate['denominator']} ({rate['proportion']:.3f}; Wilson 95% CI [{rate['wilson_95_ci']['lower']:.3f}, {rate['wilson_95_ci']['upper']:.3f}])"
    ratio = lambda part: f"{part['count']}/{part['denominator']} = {part['proportion']:.6f}"
    out = ["# RR-F 확장 저장소 감사 sensitivity", "", "- **Status:** `expanded-view-sensitivity`",
           "- **Authority:** RR-F 7행의 원/확장 label 전이, 근거 범위, Q0ㆍ이탈 sensitivity와 부분 대체 what-if",
           f"- **Last verified:** {result['analyzed_on']}", "",
           "Frozen P2/P3 중 retrieval이 insufficient/unclear로 표시된 7행 전수를 같은 base commit의 모든 regular UTF-8 "
           "text로 다시 판정한 단일 전문가(`repo480_retrieval_r1`) 반환을 분석했다. 원 labelㆍ선정 조건ㆍoracleㆍoutcome은 "
           "숨겼고 public comment/link의 원 unavailable 상태는 유지했다. 판정 불가 행과 제외 행은 없다. "
           "Frozen available-only label은 수정하지 않는다.", "",
           "## 행별 결과", "",
           "| Item | Task | 원 label / retrieval / Q | 확장 label / Q / retrieval | 확장 근거의 역할 | 원 packet 밖 인용 | 검증 패널 label | RQ2 |",
           "| --- | --- | --- | --- | --- | ---: | --- | --- |"]
    for r in rows:
        x = r["post_hoc_cross_reference"]
        rq2 = (f"member; strict {x['rq2_original_strict_call']}/{x['rq2_matched_treated_strict_call']}"
               if x["rq2_frame_member"] else "—")
        label = r["expanded_label"] or "not_assessable"
        out.append(f"| {r['item_id']} | `{r['task_id']}` | {r['original_label']} / {r['original_retrieval_sufficiency']} / "
                   f"{r['original_data_quality']} | {label} / {r['expanded_data_quality']} / {r['expanded_retrieval_sufficiency']} | "
                   f"{r['evidence_assessment']} | {r['outside_packet_references']}/{r['reference_count']} | "
                   f"{x['validation_panel_label']} | {rq2} |")
    out += ["", "RQ2 열의 strict 값은 원 패널/matched 패널 treated arm의 호출이다. 검증 패널 label은 RR-A 독립 패널의 "
            "frozen-packet 판정이다. 두 열은 protocol 동결 뒤 추가한 사후 기술 대조다.", "",
            "## 전이와 경계 변화", "",
            f"- 전이: {', '.join(f'{s}→{t} {n}' for s, targets in result['transition_counts'].items() for t, n in targets.items())}.",
            f"- P2/P3→P0/P1 경계 변화: {ci(boundary)}. 7행 전체 분모도 판정 불가가 없어 같은 값이다.",
            f"- Exact label 변화: {ci(result['exact_label_change'])}. P2/P3 유지: {ci(result['retained_p23'])}.",
            "- 원 retrieval 표시별 경계 변화: " + ", ".join(
                f"{k} {v['boundary_changes']}/{v['n']}" for k, v in result["strata"]["original_retrieval_sufficiency"].items()) + ".",
            "- Repository별 경계 변화: " + ", ".join(
                f"{k} {v['boundary_changes']}/{v['n']}" for k, v in result["strata"]["repository"].items()) + ".",
            "- 확장 근거의 역할별 경계 변화: " + ", ".join(
                f"{k} {v['boundary_changes']}/{v['n']}" for k, v in result["strata"]["evidence_assessment"].items()) + ".",
            "- 확장 retrieval sufficiency: " + ", ".join(
                f"{k} {v['n']}" for k, v in result["strata"]["expanded_retrieval_sufficiency"].items()) + ".", "",
            "경계 변화 4행 가운데 원 packet 밖의 결정적 근거를 전문가가 지목한 행은 R01 하나다. 나머지 3행(R02ㆍR03ㆍR05)은 "
            "결정적 근거가 이미 원 packet에 있었고 확장 자료는 보강일 뿐이라고 기록했다. 전문가 자신의 기록이 이 3행의 "
            "변화를 새 근거로 설명하지 않으므로 판정자 간 경계 해석 차이가 더 직접적인 경쟁 설명이다. "
            "P2/P3로 남은 3행 중 R06ㆍR07은 확장 retrieval이 "
            "충분했지만 maintainer의 호환성ㆍ기능 범위 선택이 여전히 필요하다고 기록했고, R04는 issue가 가리키는 재현 "
            "입력(#7842)을 저장소 검색으로 찾지 못해 retrieval이 여전히 insufficient였다.", "",
            "## 근거 범위", "",
            f"인용 {result['reference_count']}개는 비repository {result['reference_coverage']['non_repository']}개, 원 packet에 이미 포함 "
            f"{result['reference_coverage']['already_in_frozen_packet']}개, 원 packet에 없던 파일 "
            f"{result['reference_coverage']['file_not_in_frozen_packet']}개, 원 발췌에 전부 포함되지 않았던 행 "
            f"{result['reference_coverage']['lines_not_fully_in_frozen_packet']}개다. 검색 기록은 {result['search_steps']}단계다. "
            "`new_decisive_evidence` 행은 원 packet 밖 인용을 하나 이상 가진다. 인용 위치 검사는 보존 archive에서 배포 "
            "validator를 다시 실행해 재현했으며 판단의 의미적 타당성이나 탐색의 완전성을 보증하지 않는다.", "",
            "## Q0ㆍ이탈 sensitivity", "",
            f"- 원 Q0 membership {'ㆍ'.join(q0['original_q0_membership']['items'])}: 경계 변화 "
            f"{q0['original_q0_membership']['boundary_changes']}/{q0['original_q0_membership']['n']}.",
            f"- 확장 Q0 membership {'ㆍ'.join(q0['expanded_q0_membership']['items'])}: "
            f"{q0['expanded_q0_membership']['boundary_changes']}/{q0['expanded_q0_membership']['n']}.",
            f"- 두 판정 모두 Q0인 {'ㆍ'.join(q0['both_q0']['items'])}: {q0['both_q0']['boundary_changes']}/{q0['both_q0']['n']}.",
            f"- R07 절차 이탈 제외(노출 note 행 없음): {ci(dev['boundary_change'])}. R07은 P2로 남아 what-if 분자는 바뀌지 않는다.",
            "", "원 판정의 Q2는 R04, 확장 판정의 Q2는 R05라 두 Q0 subset은 같은 행 집합이 아니다.", "",
            "## 부분 대체 what-if", "",
            f"- Frozen 기준: {ratio(whatif['frozen_reference'])}.",
            f"- 평가된 7행에 확장 label 대입: {ratio(whatif['all_assessable_rows'])}.",
            f"- 이탈ㆍ노출 행 제외 대입: {ratio(whatif['excluding_deviation_and_exposure_rows'])}.",
            f"- Q0 frame(frozen Q 기준) 기준값 {ratio(whatif['q0_frame_frozen_reference'])}, 대입 "
            f"{ratio(whatif['q0_frame_frozen_membership'])}; 감사 행에 확장 Q 사용 시 {ratio(whatif['q0_frame_expanded_membership'])}.",
            "", "감사하지 않은 473행과 판정 불가 행은 원 값을 유지한다. P2/P3 행만 다시 보았으므로 대입은 분자를 줄이는 "
            "방향으로만 움직이며 수정 prevalence, 새 추정치, 상ㆍ하한이 아니다. 이 비율은 원 raw pass의 22/480과 다른 "
            "family이므로 합치지 않는다.", "",
            "## 사후 대조(사전 고정 아님)", "",
            f"- RR-A 검증 패널은 경계가 바뀐 4행 중 {cross['validation_panel_on_boundary_changes'].get('P2/P3', 0)}행을 P2/P3, "
            f"{cross['validation_panel_on_boundary_changes'].get('P0/P1', 0)}행(R05)을 P0/P1로 판정했었다. P2/P3로 남은 3행은 "
            f"검증 패널에서도 모두 P2/P3였다.",
            f"- RQ2 {cross['rq2_frame_size']}행 중 {len(cross['rq2_members_audited'])}행({'ㆍ'.join(cross['rq2_members_audited'])})이 "
            f"RR-F 대상이었고, 그중 {len(cross['rq2_members_expanded_p01'])}행({'ㆍ'.join(cross['rq2_members_expanded_p01'])})이 "
            f"확장 판정에서 P1이었다. 원고의 두 RQ2 worked example(R01ㆍR05)이 모두 여기에 속한다. 나머지 "
            f"{cross['rq2_rows_not_reexamined']}행은 retrieval 표시가 sufficient여서 다시 보지 않았다.",
            f"- 확장 P1 3행을 빼면 strict 호출은 원 패널 {cross['rq2_strict_calls_without_expanded_p01_rows']['original_panel']}, "
            f"matched 패널 treated {cross['rq2_strict_calls_without_expanded_p01_rows']['matched_panel_treated']}다. "
            "RQ2 masking 판정을 확장 view에서 다시 계산한 값이 아니며, RQ2는 frozen packet label에 상대적인 mechanism frame으로 남는다.",
            "", "## 수용 기록과 한계", ""]
    out.extend(f"- {note}" for note in result["acceptance_notes"])
    out.extend(f"- {note}" for note in result["claim_boundary"])
    out += ["", "입력 hash, 행별 근거 범위, 층별 분모는 동명 JSON과 rows JSONL에 있다.", "",
            "```bash", f"uv run python scripts/analyze_repo480_unbudgeted_retrieval.py --analyzed-on {result['analyzed_on']}", "```", ""]
    return "\n".join(out)


def tex(rows: list[dict]) -> str:
    roles = {"new_decisive_evidence": "New decisive", "corroboration_only": "Corroboration",
             "still_insufficient": "Still insufficient", "unclear": "Unclear"}
    out = ["% Generated by analyze_repo480_unbudgeted_retrieval.py", r"\begin{table}[htbp]", r"\centering\scriptsize",
           r"\caption{Expanded-view audit of the seven retrieval-flagged P2/P3 rows.}", r"\label{tab:rrfexpanded}",
           r"\setlength{\tabcolsep}{3pt}", r"\begin{tabular}{llllrlll}", r"\toprule",
           r"Item & Task & Frozen, retrieval & Expanded, Q & Outside/all refs & Evidence role & Validation & RQ2 strict \\", r"\midrule"]
    for r in rows:
        x = r["post_hoc_cross_reference"]
        rq2 = f"{x['rq2_original_strict_call']}/{x['rq2_matched_treated_strict_call']}" if x["rq2_frame_member"] else "--"
        label = r["expanded_label"] or "n/a"
        out.append(f"{r['item_id']} & \\texttt{{{r['task_id'].replace('_', chr(92) + '_')}}} & "
                   f"{r['original_label']}, {r['original_retrieval_sufficiency']} & {label}, {r['expanded_data_quality']} & "
                   f"{r['outside_packet_references']}/{r['reference_count']} & {roles[r['evidence_assessment']]} & "
                   f"{x['validation_panel_label']} & {rq2} " + r"\\")
    out += [r"\bottomrule", r"\end{tabular}", r"\end{table}", ""]
    return "\n".join(out)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--analyzed-on", required=True, help="YYYY-MM-DD, deterministic replay date")
    for name, default in {
        "returns-manifest": "data/manifests/generated/repo480_unbudgeted_retrieval_returns_manifest_v1.json",
        "validation-rows": "results/pilot/repo480_boundary_validation_analysis_rows_v1.jsonl",
        "rq2-rows": "results/pilot/repo480_rq2_masking_rows_v1.jsonl",
        "control-rows": "results/pilot/repo480_rq2_control_analysis_rows_v1.jsonl",
        "json-out": "results/pilot/repo480_unbudgeted_retrieval_sensitivity_v1.json",
        "rows-out": "results/pilot/repo480_unbudgeted_retrieval_audit_rows_v1.jsonl",
        "markdown-out": "results/pilot/repo480_unbudgeted_retrieval_sensitivity_v1.md",
        "tex-out": "paper/generated/repo480_unbudgeted_retrieval_summary.tex",
    }.items():
        parser.add_argument(f"--{name}", type=Path, default=Path(default))
    args = parser.parse_args()
    try:
        result, rows = analyze(args)
        for path, payload in ((args.json_out, canonical_json_bytes(result)),
                              (args.rows_out, b"".join(canonical_json_bytes(r) for r in rows)),
                              (args.markdown_out, markdown(result, rows).encode()), (args.tex_out, tex(rows).encode())):
            target = ROOT / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(payload)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1
    print(f"OK: expanded-view sensitivity for {len(rows)} rows; no exclusions")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
