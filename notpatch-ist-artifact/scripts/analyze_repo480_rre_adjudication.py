#!/usr/bin/env python3
"""Combine agreed RR-E types and accepted third-expert decisions; retain raw sensitivities."""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from notpatch.canonical import canonical_json_bytes, sha256_file
from analyze_repo480_p1_typology import A_REPORT_TYPES, B_SOURCES, _a_row, _b_row, _rate, _summarize_a, _summarize_b
from analyze_repo480_rre_verification import C1_ANALYSIS, C1_CODES, RETURNS, WORKLIST, pointer_audit, read_jsonl, report_type
from selfcheck_repo480_rre_adjudication_return import validate_return


def distribution(rows: list[dict], categories: tuple) -> dict:
    return {name: _rate(sum(r["final_type"] == name for r in rows), len(rows)) for name in categories}


def analyze(args: argparse.Namespace) -> tuple[dict, list[dict]]:
    date.fromisoformat(args.analyzed_on)
    inputs = {}

    def checked(path: str | Path, expected: str | None = None) -> Path:
        actual = sha256_file(ROOT / path)
        if expected is not None and actual != expected:
            raise ValueError(f"hash mismatch: {path}")
        inputs[str(path)] = actual
        return ROOT / path

    comparison = json.loads(checked(args.comparison).read_text())
    for path, digest in comparison["inputs"].items():
        checked(path, digest)
    accepted = json.loads(checked(args.returns_manifest).read_text())
    if accepted["coder_id"] != "repo480_rre_adj" or accepted["batch_id"] != "repo480_rre_adjudication_v1":
        raise ValueError("unexpected accepted adjudication role/batch")
    package_ref = accepted["package_manifest"]
    package = json.loads(checked(package_ref["ref"], package_ref["sha256"]).read_text())
    for path, digest in package["inputs"].items():
        checked(path, digest)
    checked(accepted["acceptance_script"]["ref"], accepted["acceptance_script"]["sha256"])
    if str(args.comparison) not in package["inputs"]:
        raise ValueError("comparison was not used for the adjudication package")
    work = read_jsonl(checked(WORKLIST))
    c1 = {r["item_id"]: r for r in read_jsonl(checked(C1_CODES))}
    c2_returns = json.loads(checked(RETURNS).read_text())
    c2 = {r["item_id"]: r for entry in c2_returns["stages"].values()
          for r in read_jsonl(checked(entry["canonical_ref"], entry["sha256"]))}
    selected = [r for r in work if report_type(c1[r["item_id"]]) != report_type(c2[r["item_id"]])]
    wanted = [r["item_id"] for r in selected]
    if wanted != package["item_ids"] or wanted != accepted["item_ids"] or len(wanted) != accepted["row_count"]:
        raise ValueError("accepted selection differs from the derived-type disagreements")
    codes = read_jsonl(checked(accepted["canonical_ref"], accepted["sha256"]))
    errors = validate_return(selected, codes)
    if errors:
        raise ValueError("; ".join(errors))
    audit = pointer_audit(selected, codes)
    if audit != accepted["pointer_audit"]:
        raise ValueError("accepted pointer audit does not reproduce")
    normalization = accepted["normalization"]
    if normalization:
        original = read_jsonl(checked(normalization["received_original"], normalization["sha256"]))
        if [dict(r, exposure_note=None) if r["exposure_note"] == "" else r for r in original] != codes:
            raise ValueError("normalization changed substantive coding")
    adj = {r["item_id"]: r for r in codes}
    prior = json.loads(checked(C1_ANALYSIS).read_text())
    denominators = prior["set_a"]["displacement_what_if"]
    for path, digest in prior["inputs"].items():
        checked(path, digest)
    rows = []
    for row in work:
        item = row["item_id"]
        first, second = report_type(c1[item]), report_type(c2[item])
        final = report_type(adj[item]) if item in adj else first
        result = {"item_id": item, "task_id": row["task_id"], "set": row["set"],
                  "c1_type": first, "c2_type": second, "final_type": final,
                  "type_source": "third_expert" if item in adj else "c1_c2_type_agreement",
                  "adjudicator_type": report_type(adj[item]) if item in adj else None}
        if row["set"] == "p1_non_strict":
            result.update(construct_validity_match=row["construct_validity"]["final_match"],
                          panel_binary_label=row["boundary_panel"]["independent_binary_label"] if row["boundary_panel"] else None)
        else:
            result.update({k: v for k, v in _b_row(row, c1[item]).items()
                           if k in {"direction", "label_pair", "p1_p2_boundary"}})
        rows.append(result)
    sets = {}
    for stage, set_name, categories in (("seta", "p1_non_strict", A_REPORT_TYPES),
                                        ("setb", "boundary_discordant", B_SOURCES)):
        members = [r for r in rows if r["set"] == set_name]
        if len(members) != comparison["sets"][stage]["type_agreement"]["n"]:
            raise ValueError("denominator changed")
        entry = {"n": len(members), "final_distribution": distribution(members, categories),
                 "raw_type_agreement": comparison["sets"][stage]["type_agreement"],
                 "by_repository": {repo: distribution([r for r in members if r["task_id"].rsplit("-", 1)[0] == repo], categories)
                                   for repo in sorted({r["task_id"].rsplit("-", 1)[0] for r in members})}}
        if stage == "seta":
            final_a = []
            for row in work:
                if row["set"] == set_name:
                    final_a.append(_a_row(row, adj.get(row["item_id"], c1[row["item_id"]])))
            summary = _summarize_a(final_a, denominators["prefix_p1_rows"], denominators["frame_p1_rows"],
                                   denominators["frame_p23_rows"], denominators["frame_rows"],
                                   denominators["reference_independent_panel"])
            for key in ("type_counts", "verdict_split", "panel_crosstab", "displacement_what_if"):
                entry[key] = summary[key]
            entry["undeterminable_items"] = [r["item_id"] for r in members if r["final_type"] == "u_undeterminable"]
        else:
            entry["by_direction"] = {d: dict(Counter(r["final_type"] for r in members if r["direction"] == d))
                                     for d in sorted({r["direction"] for r in members})}
            entry["label_pairs"] = dict(Counter(r["label_pair"] for r in members))
        entry["raw_coder_sensitivity"] = {}
        for name, coder in (("c1", c1), ("c2", c2)):
            raw = [(_a_row if stage == "seta" else _b_row)(r, coder[r["item_id"]]) for r in work if r["set"] == set_name]
            entry["raw_coder_sensitivity"][name] = _summarize_a(
                raw, denominators["prefix_p1_rows"], denominators["frame_p1_rows"], denominators["frame_p23_rows"],
                denominators["frame_rows"], denominators["reference_independent_panel"]) if stage == "seta" else _summarize_b(raw)
        sets[stage] = entry
    checked("scripts/analyze_repo480_rre_adjudication.py")
    result = {"schema_version": "repo480-rre-final-typology-v1", "status": "expert-adjudicated-types",
              "analyzed_on": args.analyzed_on, "inputs": inputs, "sets": sets, "excluded_rows": [],
              "adjudicated_item_ids": wanted, "adjudication_pointer_audit": audit,
              "adjudication_type_matches": {"c1": sum(report_type(c) == report_type(c1[c["item_id"]]) for c in codes),
                                            "c2": sum(report_type(c) == report_type(c2[c["item_id"]]) for c in codes)},
              "normalization": normalization, "acceptance_deviations": accepted["deviations"],
              "claim_boundary": [
                  "Final types combine pre-adjudication c1/c2 type agreement and third-expert decisions on disagreements only.",
                  "No final consensus is claimed for controlled fields or secondary types; raw coder summaries are sensitivities.",
                  "Two undeterminable types remain in the denominator; completed adjudication is not forced type resolution.",
                  "c1 is AI analytic coding, c2 is expert coding; adjudication is informed by both, not a third blinded pass.",
                  "Wilson intervals are row-level descriptive intervals, not repository-clustered population inference; sets share five tasks.",
                  "Inherited source hints/discussion and prior exposure remain limitations; null notes do not certify an exposure-free package.",
                  "Frozen labels, 26/480, 0.094 and 76/112 are unchanged; displacement scenarios are neither estimates nor bounds.",
              ]}
    return result, rows


def markdown(result: dict, rows: list[dict]) -> str:
    out = ["# RR-E 전문가 판정 후 유형 분포", "", "- **Status:** `expert-adjudicated-types`",
           "- **Authority:** 주 유형 분포, 원 코더별 sensitivity와 반환 검증", f"- **Last verified:** {result['analyzed_on']}", "",
           "AI analytic coding(c1)과 독립 전문가(c2)의 유형이 일치한 행은 그 유형을 유지하고, "
           "갈린 Set A 10행만 다른 전문가가 두 원문을 보고 판정했다. 제외 행은 없다.", ""]
    for stage, summary in result["sets"].items():
        out += [f"## {stage}", "", "| 유형 | 최종 | 비율 [Wilson 95% CI] | c1 | c2 |", "| --- | ---: | --- | ---: | ---: |"]
        raw = summary["raw_type_agreement"]
        for name, rate in summary["final_distribution"].items():
            lo, hi = rate["wilson_95_ci"]["lower"], rate["wilson_95_ci"]["upper"]
            out.append(f"| {name} | {rate['count']}/{summary['n']} | {rate['proportion']:.3f} [{lo:.3f}, {hi:.3f}] | {raw['c1_counts'][name]} | {raw['c2_counts'][name]} |")
        out += ["", f"판정 전 유형 일치: {raw['matches']}/{raw['n']}; κ {raw['cohen_kappa']:.3f}. "
                "판정 후 일치를 독립 재현성 지표로 계산하지 않는다.", ""]
    out += ["## 불일치 10행의 판정", "", "| Item | c1 | c2 | 최종 |", "| --- | --- | --- | --- |"]
    out += [f"| {r['item_id']} | {r['c1_type']} | {r['c2_type']} | {r['final_type']} |" for r in rows if r["type_source"] == "third_expert"]
    out += ["", "A03은 기록 간 packet 내용 서술 충돌, A23은 JavaScript 현재 동작 근거 부재로 판단 불가를 유지한다. "
            "판정을 받지 못한 누락 행이 아니다. A09는 정당한 잔여 trade-off 해석의 경계 사례이며 원 코더 sensitivity를 함께 둔다.",
            "", "## 해석과 what-if", "",
            "Set A의 계약 선택은 13/23행이며, 이미 기록된 잔여 가정 4행과 미인지 계약 선택 9행으로 나뉜다. "
            "근거 판독 문제 2행이 확인되어 기존 c1의 ‘근거 오독 없음’ 해석은 유지하지 않는다. "
            "Oracle 범위 문제 5행, 같은 계약 1행, 판단 불가 2행도 함께 보고한다.", ""]
    for scenario in result["sets"]["seta"]["displacement_what_if"]["scenarios"]:
        out.append(f"- {scenario['scenario']}: k={scenario['count_in_prefix_p1']}; (26 + 185k/47)/480 = {scenario['what_if_p23_proportion']:.6f}.")
    out += ["", "이는 경계 이동 해석의 크기를 살피는 가정적 계산이며 수정 prevalence나 상ㆍ하한이 아니다.",
            "", "## 검증ㆍ한계", "", "근거 field 경로 121개와 qualifier 11개가 연결된다. "
            "이 검사는 근거가 유일한 판정을 강제한다는 보증이 아니다.", ""]
    out.extend(f"- {note}" for note in result["acceptance_deviations"])
    out.extend(f"- {note}" for note in result["claim_boundary"])
    out += ["", "입력 hash, 원문 보존ㆍnull 정정 이력, 판정별 교차표ㆍraw field/secondary sensitivity는 동명 JSON에 있다.", "",
            "```bash", f"uv run python scripts/analyze_repo480_rre_adjudication.py --analyzed-on {result['analyzed_on']}", "```", ""]
    return "\n".join(out)


def tex(result: dict) -> str:
    out = ["% Generated by analyze_repo480_rre_adjudication.py", r"\begin{table}[htbp]", r"\centering\small",
           r"\caption{Final RR-E types and raw-coder sensitivity.}", r"\label{tab:rrefinal}",
           r"\begin{tabular}{lrrrl}", r"\toprule", r"Type & Final & c1 & c2 & Wilson 95\% CI \\", r"\midrule"]
    labels = {"a_same_contract": "Same contract", "b_anticipated": "Contract choice: anticipated",
              "b_unanticipated": "Contract choice: unanticipated", "c_evidence_reading": "Evidence reading",
              "d_oracle_scope": "Oracle scope", "u_undeterminable": "Undeterminable",
              "evidence_utilization": "Evidence utilization", "rule_threshold": "Rule threshold",
              "case_judgment": "Case judgment", "undeterminable": "Undeterminable"}
    for stage, summary in result["sets"].items():
        out += [f"\\multicolumn{{5}}{{l}}{{Set {stage[-1].upper()} ($n={summary['n']}$)}} " + r"\\"]
        raw = summary["raw_type_agreement"]
        for name, rate in summary["final_distribution"].items():
            lo, hi = rate["wilson_95_ci"]["lower"], rate["wilson_95_ci"]["upper"]
            out.append(f"{labels[name]} & {rate['count']} & {raw['c1_counts'][name]} & {raw['c2_counts'][name]} & [{lo:.3f}, {hi:.3f}] " + r"\\")
    out += [r"\bottomrule", r"\end{tabular}", r"\end{table}", ""]
    return "\n".join(out)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--analyzed-on", required=True, help="YYYY-MM-DD, deterministic replay date")
    for name, default in {
        "comparison": "results/pilot/repo480_rre_verification_analysis_v1.json",
        "returns-manifest": "data/manifests/generated/repo480_rre_adjudication_returns_manifest_v1.json",
        "json-out": "results/pilot/repo480_rre_final_typology_v1.json",
        "rows-out": "results/pilot/repo480_rre_final_typology_rows_v1.jsonl",
        "markdown-out": "results/pilot/repo480_rre_final_typology_v1.md",
        "tex-out": "paper/generated/repo480_rre_final_typology_summary.tex",
    }.items():
        parser.add_argument(f"--{name}", type=Path, default=Path(default))
    args = parser.parse_args()
    try:
        result, rows = analyze(args)
        for path, payload in ((args.json_out, canonical_json_bytes(result)),
                              (args.rows_out, b"".join(canonical_json_bytes(r) for r in rows)),
                              (args.markdown_out, markdown(result, rows).encode()), (args.tex_out, tex(result).encode())):
            target = ROOT / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(payload)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1
    print(f"OK: final types for {len(rows)} rows; no exclusions")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
