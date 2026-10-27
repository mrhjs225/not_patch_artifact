#!/usr/bin/env python3
"""Compare accepted RR-E c2 returns with c1 without changing either coding pass."""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from datetime import date
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from notpatch.canonical import canonical_json_bytes, sha256_file
from analyze_repo480_p1_typology import (
    A_FIELDS, A_REPORT_TYPES, B_FIELDS, B_SOURCES, _validate_codes, _wilson,
    derive_a, derive_b,
)
from selfcheck_repo480_rre_verification_return import validate_codes

WORKLIST = Path("data/annotations/worklists/repo480_p1_typology_worklist_v1.jsonl")
WORKLIST_MANIFEST = Path("data/manifests/generated/repo480_p1_typology_worklist_manifest_v1.json")
C1_CODES = Path("data/annotations/typology/repo480_p1_typology_codes_c1_v1.jsonl")
C1_ANALYSIS = Path("results/pilot/repo480_p1_non_strict_typology_v1.json")
RETURNS = Path("data/manifests/generated/repo480_rre_verification_returns_manifest_v1.json")
STAGES = {"setb": ("boundary_discordant", 22), "seta": ("p1_non_strict", 23)}


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def report_type(row: dict) -> str:
    values = row["codes"]
    if row["set"] == "boundary_discordant":
        return derive_b(values)
    derived = derive_a(values)
    if derived == "b_contract_choice":
        return "b_anticipated" if values["assumption_anticipated"] == "yes" else "b_unanticipated"
    return derived


def agreement(left: list[str], right: list[str], categories: list[str]) -> dict:
    if not left or len(left) != len(right):
        raise ValueError("agreement requires equal, non-empty paired lists")
    if not set(left + right) <= set(categories):
        raise ValueError("agreement value outside the declared categories")
    n = len(left)
    matches = sum(a == b for a, b in zip(left, right))
    lc, rc = Counter(left), Counter(right)
    expected_numerator = sum(lc[c] * rc[c] for c in categories)
    denominator = n * n - expected_numerator
    lo, hi = _wilson(matches, n)
    return {
        "n": n, "matches": matches, "proportion": round(matches / n, 6),
        "wilson_95_ci": [round(lo, 6), round(hi, 6)],
        "cohen_kappa": round((matches * n - expected_numerator) / denominator, 6)
        if denominator else None,
        "kappa_note": None if denominator else "Undefined: both margins have one identical category.",
        "categories": categories,
        "c1_counts": {c: lc[c] for c in categories},
        "c2_counts": {c: rc[c] for c in categories},
        "confusion_c1_rows_c2_columns": {
            a: {b: sum(x == a and y == b for x, y in zip(left, right)) for b in categories}
            for a in categories
        },
    }


def pointer_audit(work: list[dict], codes: list[dict]) -> dict:
    count, qualified, warnings = 0, 0, []
    for row, code in zip(work, codes):
        for ref in code["evidence_refs"]:
            count += 1
            path, _, qualifier = ref.partition(":")
            value: Any = row
            try:
                for part in path.split("."):
                    value = value[int(part)] if isinstance(value, list) else value[part]
            except (KeyError, IndexError, ValueError, TypeError) as exc:
                raise ValueError(f"{code['item_id']}: missing evidence pointer {ref}") from exc
            if value is None or value == "" or value == [] or value == {}:
                raise ValueError(f"{code['item_id']}: empty evidence pointer {ref}")
            if qualifier:
                qualified += 1
                missing = [part for part in qualifier.split(".") if part not in str(value)]
                if missing:
                    warnings.append({"item_id": code["item_id"], "pointer": ref,
                                     "qualifier_tokens_absent_from_value": missing})
    return {"field_paths_checked": count, "missing_or_empty_field_paths": 0,
            "qualified_pointers": qualified, "qualifier_warnings": warnings,
            "scope": "Structural resolution and qualifier-token presence, not semantic evidence validation."}


def analyze(args: argparse.Namespace) -> tuple[dict, list[dict]]:
    date.fromisoformat(args.analyzed_on)
    provenance: dict[str, str] = {}

    def checked(path: Path, expected: str | None = None) -> Path:
        digest = sha256_file(ROOT / path)
        if expected is not None and digest != expected:
            raise ValueError(f"hash mismatch: {path}")
        provenance[path.as_posix()] = digest
        return ROOT / path

    manifest = json.loads(checked(args.worklist_manifest).read_text())
    work = read_jsonl(checked(args.worklist, manifest["worklist"]["sha256"]))
    checked(Path(manifest["codebook"]["ref"]), manifest["codebook"]["sha256"])
    prior = json.loads(checked(C1_ANALYSIS).read_text())
    c1 = _validate_codes(work, read_jsonl(checked(args.c1_codes, prior["inputs"][str(C1_CODES)])))
    returns = json.loads(checked(args.returns_manifest).read_text())
    if returns["coder_id"] != "repo480_rre_c2" or set(returns["stages"]) != set(STAGES):
        raise ValueError("both accepted c2 stages are required before comparison")
    summary, comparisons = {}, []
    for stage, (set_name, expected_n) in STAGES.items():
        entry = returns["stages"][stage]
        package = json.loads(checked(Path(entry["package_manifest"]["ref"]),
                                     entry["package_manifest"]["sha256"]).read_text())
        if package["stage"] != stage or package["coder_id"] != "repo480_rre_c2":
            raise ValueError("accepted package stage/coder mismatch")
        if stage == "seta":
            b = returns["stages"]["setb"]
            if package["accepted_setb_return"] != {"ref": b["canonical_ref"], "sha256": b["sha256"]}:
                raise ValueError("Set A lacks the accepted Set B prerequisite")
        selected = [row for row in work if row["set"] == set_name]
        second = read_jsonl(checked(Path(entry["canonical_ref"]), entry["sha256"]))
        if len(selected) != expected_n or entry["row_count"] != expected_n:
            raise ValueError(f"{stage}: denominator differs from frozen selection")
        if [row["item_id"] for row in selected] != package["item_ids"]:
            raise ValueError(f"{stage}: package selection differs from frozen worklist")
        for path, digest in package["inputs"].items():
            checked(Path(path), digest)
        errors = validate_codes(selected, second)
        if errors:
            raise ValueError(errors[0])
        fields = A_FIELDS if stage == "seta" else B_FIELDS
        first = [c1[row["item_id"]] for row in selected]
        left, right = [report_type(c) for c in first], [report_type(c) for c in second]
        items = []
        for row, one, two, a, b in zip(selected, first, second, left, right):
            item = {"item_id": row["item_id"], "task_id": row["task_id"], "set": set_name,
                    "repository": row["task_id"].rsplit("-", 1)[0],
                    "c1_type": a, "c2_type": b, "type_match": a == b,
                    "differing_controlled_fields": [f for f in fields if one["codes"][f] != two["codes"][f]],
                    "c1_exposure_note": one["exposure_note"], "c2_exposure_note": two["exposure_note"]}
            items.append(item)
        comparisons.extend(items)
        categories = list(A_REPORT_TYPES if stage == "seta" else B_SOURCES)
        summary[stage] = {
            "set": set_name, "type_agreement": agreement(left, right, categories),
            "controlled_field_agreement": {
                f: agreement([c["codes"][f] for c in first], [c["codes"][f] for c in second], sorted(allowed))
                for f, allowed in fields.items()
            },
            "all_controlled_fields_match": sum(not i["differing_controlled_fields"] for i in items),
            "disagreement_item_ids": [i["item_id"] for i in items if not i["type_match"]],
            "by_repository": {
                repo: {"n": sum(i["repository"] == repo for i in items),
                       "matches": sum(i["repository"] == repo and i["type_match"] for i in items)}
                for repo in sorted({i["repository"] for i in items})
            },
            "c2_pointer_audit": pointer_audit(selected, second),
            "acceptance_deviations": entry["deviations"],
            "exposure_note_counts": {"c1": sum(c["exposure_note"] is not None for c in first),
                                     "c2": sum(c["exposure_note"] is not None for c in second)},
        }
        if stage == "seta":
            summary[stage]["secondary_types_exact_set_agreement"] = agreement(
                ["|".join(sorted(c["codes"]["secondary_types"])) for c in first],
                ["|".join(sorted(c["codes"]["secondary_types"])) for c in second],
                sorted({"|".join(sorted(c["codes"]["secondary_types"])) for c in first + second}),
            )
    for script in ("analyze_repo480_rre_verification.py", "analyze_repo480_p1_typology.py",
                   "selfcheck_repo480_rre_verification_return.py"):
        checked(Path("scripts") / script)
    return {
        "schema_version": "repo480-rre-verification-analysis-v1",
        "status": "raw-comparison-pending-adjudication", "analyzed_on": args.analyzed_on,
        "inputs": provenance, "sets": summary,
        "comparison_plan": "docs/decisions/README.md: RR-E P1 경계 유형화 (fixed before c2 returns)",
        "excluded_rows": [],
        "shared_tasks": sorted({r["task_id"] for r in work if r["set"] == "p1_non_strict"}
                               & {r["task_id"] for r in work if r["set"] == "boundary_discordant"}),
        "claim_boundary": [
            "Agreement compares an AI analytic pass with one expert pass, not two expert annotators.",
            "All 23 Set A and 22 Set B rows are retained. Only derived-type disagreements enter adjudication.",
            "Wilson intervals are descriptive row-level intervals; within-repository dependence is not modeled.",
            "These selected sets are not random population samples. Five shared tasks preclude pooling the sets.",
            "Free-text wording is not scored. Secondary types are compared as unordered sets, separately from controlled fields.",
            "Exposure notes and pointer qualifications are retained; a clean exposure-free pass is not established.",
            "Frozen labels and 26/480, 0.094, 76/112 remain unchanged. Final typology awaits adjudication.",
        ],
    }, comparisons


def markdown(analysis: dict, rows: list[dict]) -> str:
    out = ["# RR-E 전문가 검증: 판정 전 코딩 비교", "", "- **Status:** `raw-comparison-pending-adjudication`",
           "- **Authority:** 수용된 c1ㆍc2 코딩의 일치와 불일치 목록; 최종 유형 분포가 아님",
           f"- **Last verified:** {analysis['analyzed_on']}", "",
           "사전에 정한 Set A 6유형(anticipated 분할 포함), Set B 4유형을 비교한다. "
           "c1은 AI analytic coding, c2는 전문가 코딩이다. 제외 없이 두 set을 따로 분석한다.", "",
           "| Set | 일치 | 비율 (Wilson 95% CI) | Cohen κ | 판정 대상 |",
           "| --- | ---: | --- | ---: | ---: |"]
    for stage in ("seta", "setb"):
        s = analysis["sets"][stage]; a = s["type_agreement"]; lo, hi = a["wilson_95_ci"]
        out.append(f"| {stage} | {a['matches']}/{a['n']} | {a['proportion']:.3f} [{lo:.3f}, {hi:.3f}] | "
                   f"{a['cohen_kappa']:.3f} | {len(s['disagreement_item_ids'])} |")
    out += ["", "Wilson 구간은 행 단위 기술 통계이며 repository 군집성을 반영하지 않는다. "
            "Repository별 분모ㆍ일치는 JSON에 기록했다. 두 set은 5개 task를 공유하므로 합산하지 않는다.",
            "", "## 코더별 분포와 field 일치", ""]
    for stage in ("seta", "setb"):
        s = analysis["sets"][stage]; a = s["type_agreement"]
        out += [f"### {stage}", "", "| 유형 | c1 | c2 |", "| --- | ---: | ---: |"]
        out += [f"| {c} | {a['c1_counts'][c]} | {a['c2_counts'][c]} |" for c in a["categories"]]
        out += ["", "| 통제 field | 일치 | 비율 (Wilson 95% CI) | κ |", "| --- | ---: | --- | ---: |"]
        for field, metric in s["controlled_field_agreement"].items():
            lo, hi = metric["wilson_95_ci"]; k = metric["cohen_kappa"]
            k_text = "정의 불가" if k is None else f"{k:.3f}"
            out.append(f"| {field} | {metric['matches']}/{metric['n']} | {metric['proportion']:.3f} "
                       f"[{lo:.3f}, {hi:.3f}] | {k_text} |")
        out += ["", f"통제 field 전부 일치: {s['all_controlled_fields_match']}/{a['n']}. "
                "유형이 같은 행의 field 차이는 판정 대상으로 추가하지 않는다.", ""]
    out += ["## 제3 전문가 판정 대상", "", "| Item | Task | c1 | c2 | 갈린 통제 field |",
            "| --- | --- | --- | --- | --- |"]
    out += [f"| {r['item_id']} | {r['task_id']} | {r['c1_type']} | {r['c2_type']} | "
            f"{', '.join(r['differing_controlled_fields'])} |" for r in rows if not r["type_match"]]
    out += ["", "## 노출ㆍ근거 점검과 해석 한계", ""]
    for stage, s in analysis["sets"].items():
        audit = s["c2_pointer_audit"]
        out.append(f"- {stage}: c2 노출 기록 {s['exposure_note_counts']['c2']}행; "
                   f"근거 field 경로 {audit['field_paths_checked']}개 연결, "
                   f"세부 qualifier 경고 {len(audit['qualifier_warnings'])}개.")
        out.extend(f"- {stage} 수용 기록: {note}" for note in s["acceptance_deviations"])
    out += ["", "Set A의 예상된 가정/미예상 계약 선택 구분과 근거 판독ㆍ판별 불가 분류는 "
            "전문가 판정 전이다. Set B의 유형 일치만으로 Set A의 기존 분포를 검증 완료로 간주하지 않는다.",
            "사전 기억과 제공 기록 안의 금지 자료 언급이 미친 영향은 확인되지 않았다. "
            "기존 primary labelㆍprevalenceㆍconstruct-validity 수치는 변경하지 않는다.", "",
            "## 재현", "", "입력 SHA-256, 비교 행, 혼동행렬, field별 결과는 동명 JSONㆍrows JSONL에 있다.", "",
            "```bash", f"uv run python scripts/analyze_repo480_rre_verification.py --analyzed-on {analysis['analyzed_on']}",
            "```", ""]
    return "\n".join(out)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--analyzed-on", required=True, help="YYYY-MM-DD; preserved for deterministic replay")
    for name, default in (("worklist", WORKLIST), ("worklist-manifest", WORKLIST_MANIFEST),
                          ("c1-codes", C1_CODES), ("returns-manifest", RETURNS),
                          ("json-out", "results/pilot/repo480_rre_verification_analysis_v1.json"),
                          ("rows-out", "results/pilot/repo480_rre_verification_rows_v1.jsonl"),
                          ("markdown-out", "results/pilot/repo480_rre_verification_analysis_v1.md")):
        parser.add_argument(f"--{name}", type=Path, default=Path(default))
    args = parser.parse_args()
    try:
        result, rows = analyze(args)
        for path, payload in ((args.json_out, canonical_json_bytes(result)),
                              (args.rows_out, b"".join(canonical_json_bytes(r) for r in rows)),
                              (args.markdown_out, markdown(result, rows).encode())):
            target = ROOT / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(payload)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1
    print(f"OK: compared {len(rows)} rows; {sum(not r['type_match'] for r in rows)} type disagreements")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
