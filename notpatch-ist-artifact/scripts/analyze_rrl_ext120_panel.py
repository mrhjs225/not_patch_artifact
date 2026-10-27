#!/usr/bin/env python3
"""Analyze the accepted RR-L ext120 panel with the prespecified R1-R3 rules (protocol section 5)."""

from __future__ import annotations

import argparse
import json
import random
import sys
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from notpatch.canonical import canonical_json_bytes, sha256_file  # noqa: E402
import selfcheck_rrl_ext120_adjudication_return as adj_check  # noqa: E402
from analyze_repo480_prevalence import _rate  # noqa: E402

adj_check.RAW_SELFCHECK = ROOT / "scripts/selfcheck_rrl_ext120_return.py"

RAW_ROLES = ("rrl_ext120_r1", "rrl_ext120_r2")
SHORT = {"rrl_ext120_r1": "r1", "rrl_ext120_r2": "r2"}
P23 = {"P2", "P3"}
FLAGGED = {"insufficient", "unclear"}
REPOSITORY_EVIDENCE = {"retrieved_code", "visible_tests", "docs", "configs"}
CATEGORIES = ("issue_packet", "repository_inventory", "retrieved_code", "visible_tests", "docs", "configs",
              "linked_artifacts", "public_comments_until_cutoff")
# Protocol section 5 reference intervals (repo480 adjudicated retrieval flags and P0-3 raw binary agreement).
REPO480_R2 = {"count": 100, "denominator": 480, "lower": 0.1744, "upper": 0.2469}
REPO480_R3 = {"count": 430, "denominator": 480, "lower": 0.8653, "upper": 0.9201}
REPO480_LABEL_SHA256 = "98b33aabbd10b34bd093c4590c2f6c42476f999dd0e60e64794dbb0544f4e63d"
BOOTSTRAP_SEED = 20261021
BOOTSTRAP_SAMPLES = 10_000
CLAIM_BOUNDARY = [
    "One additional Python frame (SWE-bench-Live lite, revision b51a8642, 120 rows from 52 repositories) under the "
    "same evidence contract; no generalization to other benchmarks, languages, or APR at large.",
    "R2 and R3 are boundary checks for differences of roughly ten percentage points, not equivalence tests.",
    "retrieval_sufficiency is not a controlled field: the adjudicator never overrode it, so the post-adjudication "
    "value is the base annotator's raw value, and the raw passes differ in how often they flag retrieval.",
    "The post-adjudication P2/P3 share is a frame-specific descriptive value; it is not combined with 26/480 or 0.094 "
    "and is not an APR prevalence.",
    "SWE-bench-Live keeps its own buildability and test-executability selection, and 13 sampled rows come from "
    "SWE-bench repositories.",
    "Repo480 canonical labels, 26/480, 0.094, 12/12 and 10/12 are unchanged.",
]


def binary(label: str) -> str:
    return "P2/P3" if label in P23 else "P0/P1"


def interval(rate: dict[str, Any]) -> tuple[float, float]:
    return rate["wilson_95_ci"]["lower"], rate["wilson_95_ci"]["upper"]


def profile(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """R2, R3 and auxiliary P2/P3 on one descriptive subset."""
    n = len(rows)
    r2 = _rate(sum(r["final_retrieval_sufficiency"] in FLAGGED for r in rows), n)
    r3 = _rate(sum(binary(r["raw_labels"]["r1"]) == binary(r["raw_labels"]["r2"]) for r in rows), n)
    return {
        "n": n,
        "r2_adjudicated_flagged": r2,
        "r2_rule_would_trigger": interval(r2)[0] > REPO480_R2["upper"],
        "r3_raw_binary_agreement": r3,
        "r3_rule_would_trigger": interval(r3)[1] < REPO480_R3["lower"],
        "adjudicated_p2p3": _rate(sum(r["final_label"] in P23 for r in rows), n),
    }


def cluster_bootstrap(rows: list[dict[str, Any]]) -> dict[str, Any]:
    clusters: dict[str, list[bool]] = defaultdict(list)
    for r in rows:
        clusters[r["repo"]].append(r["final_label"] in P23)
    repos = sorted(clusters)
    rng = random.Random(BOOTSTRAP_SEED)
    values = []
    for _ in range(BOOTSTRAP_SAMPLES):
        sampled = [clusters[rng.choice(repos)] for _ in repos]
        values.append(sum(sum(c) for c in sampled) / sum(len(c) for c in sampled))
    values.sort()
    return {"repository_count": len(repos), "samples": BOOTSTRAP_SAMPLES, "seed": BOOTSTRAP_SEED,
            "percentile_95_ci": {"lower": round(_percentile(values, 0.025), 6),
                                 "upper": round(_percentile(values, 0.975), 6)}}


def _percentile(values: list[float], q: float) -> float:
    position = q * (len(values) - 1)
    lower = int(position)
    upper = min(lower + 1, len(values) - 1)
    return values[lower] + (values[upper] - values[lower]) * (position - lower)


def agreement(pairs: list[tuple[str, str]]) -> dict[str, Any]:
    n = len(pairs)
    observed = sum(a == b for a, b in pairs) / n
    left, right = Counter(a for a, _ in pairs), Counter(b for _, b in pairs)
    expected = sum(left[k] * right[k] for k in set(left) | set(right)) / (n * n)
    return {"cohen_kappa": round((observed - expected) / (1 - expected), 6), "pabak": round(2 * observed - 1, 6)}


def analyze(args: argparse.Namespace) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    date.fromisoformat(args.analyzed_on)
    inputs: dict[str, str] = {}

    def checked(path: str | Path, expected: str | None = None) -> Path:
        actual = sha256_file(ROOT / path)
        if expected is not None and actual != expected:
            raise ValueError(f"hash mismatch: {path}")
        inputs[str(path)] = actual
        return ROOT / path

    accepted = json.loads(checked(args.returns_manifest).read_text())
    if accepted["annotation_batch_id"] != "rrl_ext120_available_v1":
        raise ValueError("unexpected accepted batch")
    panel = json.loads(checked(accepted["panel_manifest"]["ref"], accepted["panel_manifest"]["sha256"]).read_text())
    raw = {role: _jsonl(checked(accepted["raw_returns"][role]["ref"], accepted["raw_returns"][role]["sha256"]))
           for role in RAW_ROLES}
    adj = accepted["adjudication"]
    decisions = _jsonl(checked(adj["decisions"]["ref"], adj["decisions"]["sha256"]))
    labels = _jsonl(checked(adj["post_adjudication_labels"]["ref"], adj["post_adjudication_labels"]["sha256"]))
    checked(adj["validator"]["ref"], adj["validator"]["sha256"])
    checked(accepted["acceptance_script"]["ref"], accepted["acceptance_script"]["sha256"])
    if labels != adj_check.build_final(raw, decisions):
        raise ValueError("post-adjudication labels do not follow from the canonical raw returns and decisions")
    frozen = panel["inputs"]
    split = json.loads(checked(frozen["split"]["ref"], frozen["split"]["sha256"]).read_text())
    materialization = json.loads(checked(frozen["materialization"]["ref"], frozen["materialization"]["sha256"]).read_text())
    views = _jsonl(checked(frozen["reviewer_views"]["ref"], frozen["reviewer_views"]["sha256"]))
    checked(panel["analysis_plan"]["ref"], panel["analysis_plan"]["sha256"])
    probe = json.loads(checked(args.probe).read_text())
    repo480 = {
        "adjudicated": _jsonl(checked(args.repo480_labels, REPO480_LABEL_SHA256)),
        "r1": _jsonl(checked(args.repo480_raw_r1)),
        "r2": _jsonl(checked(args.repo480_raw_r2)),
    }
    if sum(r["retrieval_sufficiency"] in FLAGGED for r in repo480["adjudicated"]) != REPO480_R2["count"]:
        raise ValueError("repo480 adjudicated retrieval reference differs from the protocol")
    for name, ref in (("R2", REPO480_R2), ("R3", REPO480_R3)):
        lower, upper = interval(_rate(ref["count"], ref["denominator"]))
        if (round(lower, 4), round(upper, 4)) != (ref["lower"], ref["upper"]):
            raise ValueError(f"repo480 {name} reference interval differs from the protocol")

    split_tasks = {t["task_id"]: t for t in split["tasks"]}
    packets = {t["task_id"]: t for t in materialization["tasks"]}
    category_status = {v["task_id"]: v["category_status"] for v in views}
    decided = {d["task_id"]: d for d in decisions}
    rows = []
    for left, right, final in zip(raw[RAW_ROLES[0]], raw[RAW_ROLES[1]], labels, strict=True):
        task_id = final["task_id"]
        if not left["task_id"] == right["task_id"] == task_id:
            raise ValueError(f"row order differs at {task_id}")
        decision = decided.get(task_id)
        pair = {"r1": left, "r2": right}
        fields = {name: record["annotation_fields"] for name, record in pair.items()}
        rows.append({
            "schema_version": "rrl-ext120-analysis-row-v1",
            "ordinal": final["ordinal"], "task_id": task_id, "repo": final["repo"],
            "swebench_repository": split_tasks[task_id]["swebench_repository"],
            "packet_status": packets[task_id]["packet_status"],
            "fix_pr_time_verification": packets[task_id]["public_cutoff_verification_status"],
            "raw_labels": {name: f["primary_label"] for name, f in fields.items()},
            "raw_retrieval_sufficiency": {name: f["retrieval_sufficiency"] for name, f in fields.items()},
            "raw_data_quality": {name: f["data_quality"] for name, f in fields.items()},
            "raw_uses_repository_evidence": {name: bool(REPOSITORY_EVIDENCE & set(f["available_evidence_used"]))
                                             for name, f in fields.items()},
            "raw_protocol_deviation": {name: record["protocol_deviation"] is not None for name, record in pair.items()},
            "adjudicated": decision is not None,
            "disagreement_category": decision["disagreement_category"] if decision else None,
            "adjudicator_protocol_deviation": bool(decision and decision["protocol_deviation"] is not None),
            "base_annotator": SHORT[final["base_annotator"]],
            "override_fields": final["override_fields"],
            "final_label": final["annotation_fields"]["primary_label"],
            "final_retrieval_sufficiency": final["annotation_fields"]["retrieval_sufficiency"],
            "final_data_quality": final["annotation_fields"]["data_quality"],
        })

    sample_n = split["n_sampled"]
    panel_l = len(rows)
    flagged = sum(r["final_retrieval_sufficiency"] in FLAGGED for r in rows)
    r2_rate = _rate(flagged, panel_l)
    r2_triggered = r2_rate["wilson_95_ci"]["lower"] > REPO480_R2["upper"]
    pairs = [(binary(r["raw_labels"]["r1"]), binary(r["raw_labels"]["r2"])) for r in rows]
    r3_rate = _rate(sum(a == b for a, b in pairs), panel_l)
    r3_triggered = r3_rate["wilson_95_ci"]["upper"] < REPO480_R3["lower"]
    exact = [(r["raw_labels"]["r1"], r["raw_labels"]["r2"]) for r in rows]
    frame = next(f for f in probe["frames"]
                 if f["dataset"] == "SWE-bench-Live/SWE-bench-Live" and f["split"] == "lite")
    if not frame["revision_sha"].startswith("b51a8642"):
        raise ValueError("probe frame revision differs from the frozen frame")
    raw_dev = [r for r in rows if not any(r["raw_protocol_deviation"].values())]
    any_dev = [r for r in raw_dev if not r["adjudicator_protocol_deviation"]]
    retrieval_cells = Counter((r["raw_retrieval_sufficiency"]["r1"] in FLAGGED,
                               r["raw_retrieval_sufficiency"]["r2"] in FLAGGED) for r in rows)

    result = {
        "schema_version": "rrl-ext120-external-frame-analysis-v1",
        "status": "external-frame-sensitivity",
        "analyzed_on": args.analyzed_on,
        "annotation_batch_id": accepted["annotation_batch_id"],
        "packet_policy_id": accepted["packet_policy_id"],
        "frame_id": materialization["frame_id"],
        "inputs": inputs,
        "denominators": {"sample_rows_N": sample_n, "panel_rows_L": panel_l, "excluded_rows": []},
        "r1_applicability": {
            "materialization_failures": {"count": sample_n - len(materialization["tasks"]), "reasons": {}},
            "packet_status": dict(Counter(t["packet_status"] for t in materialization["tasks"])),
            "category_status": {c: dict(sorted(Counter(category_status[r["task_id"]][c]["status"] for r in rows).items()))
                                for c in CATEGORIES},
            "fix_pr_time_verification": dict(sorted(Counter(r["fix_pr_time_verification"] for r in rows).items())),
            "unverified_fix_pr_time_by_repository": dict(sorted(Counter(
                r["repo"] for r in rows if r["fix_pr_time_verification"] != "verified").items())),
            "repository_count": len({r["repo"] for r in rows}),
            "swebench_repository_rows": sum(r["swebench_repository"] for r in rows),
            "classifier_fit_frame_level": {"swebench_live_lite_300": frame["summary"]["classifier_fit"],
                                           "repo480_source_draw_600": probe["reference"]["summary"]["classifier_fit"]},
        },
        "r2_retrieval_failure": {
            "adjudicated": r2_rate,
            "raw": {SHORT[role]: _rate(sum(r["raw_retrieval_sufficiency"][SHORT[role]] in FLAGGED for r in rows),
                                       panel_l) for role in RAW_ROLES},
            "repo480_reference": REPO480_R2,
            "rule_triggered": r2_triggered,
            "reading": "frozen retrieval policy transfer is weak" if r2_triggered
            else "no large difference observed at this sample size",
        },
        "r3_reproducibility": {
            "raw_binary_agreement": r3_rate,
            **agreement(pairs),
            "exact_p0_p3_agreement": _rate(sum(a == b for a, b in exact), panel_l),
            "binary_disagreement_direction": {
                "r1_P2P3_r2_P0P1": sum(pair == ("P2/P3", "P0/P1") for pair in pairs),
                "r1_P0P1_r2_P2P3": sum(pair == ("P0/P1", "P2/P3") for pair in pairs),
            },
            "raw_label_crosstab_r1_by_r2": {a: {b: sum(pair == (a, b) for pair in exact) for b in ("P0", "P1", "P2", "P3")}
                                            for a in ("P0", "P1", "P2", "P3")},
            "repo480_reference": REPO480_R3,
            "rule_triggered": r3_triggered,
            "reading": "raw reproducibility is low in the external frame" if r3_triggered
            else "no large drop observed",
        },
        "auxiliary_p2p3": {
            "adjudicated": _rate(sum(r["final_label"] in P23 for r in rows), panel_l),
            "repository_cluster_bootstrap": cluster_bootstrap(rows),
            "raw_marginals": {name: _rate(sum(r["raw_labels"][name] in P23 for r in rows), panel_l) for name in ("r1", "r2")},
            "adjudicated_label_counts": dict(sorted(Counter(r["final_label"] for r in rows).items())),
            "adjudicated_data_quality_counts": dict(sorted(Counter(r["final_data_quality"] for r in rows).items())),
        },
        "sensitivity": {
            "r2_failures_as_retrieval_failure": _rate(flagged + sample_n - panel_l, sample_n),
            "exclude_raw_protocol_deviation_rows": profile(raw_dev),
            "exclude_raw_or_adjudicator_protocol_deviation_rows": profile(any_dev),
            "adjudicated_q0_only": profile([r for r in rows if r["final_data_quality"] == "Q0"]),
            "swebench_repository_stratum": profile([r for r in rows if r["swebench_repository"]]),
            "other_repository_stratum": profile([r for r in rows if not r["swebench_repository"]]),
        },
        "post_hoc_description": {
            "prespecified": False,
            "retrieval_sufficiency_overrides": sum("retrieval_sufficiency" in d["overrides"] for d in decisions),
            "base_annotator_counts": dict(sorted(Counter(r["base_annotator"] for r in rows).items())),
            "raw_retrieval_flag_cells": {f"r1_{'flagged' if a else 'sufficient'}|r2_{'flagged' if b else 'sufficient'}": n
                                         for (a, b), n in sorted(retrieval_cells.items())},
            "raw_retrieval_flag_intersection": _rate(retrieval_cells[(True, True)], panel_l),
            "raw_retrieval_flag_union": _rate(panel_l - retrieval_cells[(False, False)], panel_l),
            "adjudicated_flag_by_binary_label": {label: dict(sorted(Counter(
                r["final_retrieval_sufficiency"] for r in rows if binary(r["final_label"]) == label).items()))
                for label in ("P0/P1", "P2/P3")},
            "repo480_raw_retrieval_flags": {name: _rate(sum(r["annotation_fields"]["retrieval_sufficiency"] in FLAGGED
                                                            if "annotation_fields" in r else
                                                            r["retrieval_sufficiency"] in FLAGGED
                                                            for r in repo480[name]), len(repo480[name]))
                                            for name in ("r1", "r2")},
            "raw_rows_recording_repository_evidence": {name: sum(r["raw_uses_repository_evidence"][name] for r in rows)
                                                       for name in ("r1", "r2")},
            "protocol_deviation_rows": {"r1": sum(r["raw_protocol_deviation"]["r1"] for r in rows),
                                        "r2": sum(r["raw_protocol_deviation"]["r2"] for r in rows),
                                        "adjudicator": sum(r["adjudicator_protocol_deviation"] for r in rows),
                                        "raw_any": panel_l - len(raw_dev),
                                        "raw_or_adjudicator": panel_l - len(any_dev)},
        },
        "acceptance_notes": accepted["acceptance_notes"],
        "claim_boundary": CLAIM_BOUNDARY,
    }
    checked("scripts/analyze_rrl_ext120_panel.py")
    return result, rows


def markdown(result: dict[str, Any]) -> str:
    def ci(rate: dict[str, Any]) -> str:
        lower, upper = interval(rate)
        return f"{rate['count']}/{rate['denominator']} ({rate['proportion']:.3f}; Wilson 95% [{lower:.3f}, {upper:.3f}])"

    r1, r2, r3 = result["r1_applicability"], result["r2_retrieval_failure"], result["r3_reproducibility"]
    aux, sens, post = result["auxiliary_p2p3"], result["sensitivity"], result["post_hoc_description"]
    fit = r1["classifier_fit_frame_level"]
    boot = aux["repository_cluster_bootstrap"]
    cats = r1["category_status"]
    direction = r3["binary_disagreement_direction"]
    cells = post["raw_retrieval_flag_cells"]
    dev = post["protocol_deviation_rows"]
    panel_l = result["denominators"]["panel_rows_L"]
    crosstab = r3["raw_label_crosstab_r1_by_r2"]
    p0_p1 = crosstab["P0"]["P1"] + crosstab["P1"]["P0"]
    r2_raw_trigger = {name: interval(rate)[0] > REPO480_R2["upper"] for name, rate in r2["raw"].items()}
    intersection_trigger = interval(post["raw_retrieval_flag_intersection"])[0] > REPO480_R2["upper"]
    flagged_by_label = {label: sum(n for k, n in counts.items() if k in FLAGGED)
                        for label, counts in post["adjudicated_flag_by_binary_label"].items()}
    label_totals = {label: sum(counts.values()) for label, counts in post["adjudicated_flag_by_binary_label"].items()}
    r2_reading = ("**사전 규칙 충족: frozen retrieval policy의 전이가 약하다.**" if r2["rule_triggered"]
                  else "사전 규칙 미충족: 이 표본 크기에서 큰 차이는 관찰되지 않았다(동등성 주장 아님).")
    r3_reading = ("**사전 규칙 충족: 외부 frame에서 raw 재현성이 낮다.**" if r3["rule_triggered"]
                  else "사전 규칙 미충족: 큰 하락이 관찰되지 않았다(동등성 주장 아님).")
    out = [
        "# RR-L 외부 frame sensitivity 분석", "",
        "- **Status:** `external-frame-sensitivity`",
        "- **Authority:** RR-L(SWE-bench-Live lite 120행)의 사전 고정 R1–R3, 보조 P2/P3, sensitivity 결과. 규칙은 "
        "`docs/rrl_external_frame_protocol.md` §5, claim boundary는 `docs/roadmap.md`가 소유한다",
        f"- **Last verified:** {result['analyzed_on']}", "",
        "## 설계와 입력", "",
        f"SWE-bench-Live lite(revision `b51a8642`)에서 seed `20261021`로 뽑은 첫 적격 {result['denominators']['sample_rows_N']}행에 "
        "repo480과 같은 evidence contract(packet policy `swebench-live-lite-ext120-v1`)를 적용했다. 서로 다른 전문가 두 명이 "
        "같은 frozen reviewer view로 독립 available-only raw pass를 했고, 세 번째 전문가가 controlled field가 다른 119행을 "
        "판정했다. 판정 규칙과 아래 분석은 반환 전에 동결했다. 반환 수용 기록은 "
        "`data/manifests/generated/rrl_ext120_returns_manifest_v1.json`, 행별 값은 "
        "`results/pilot/rrl_ext120_external_frame_rows_v1.jsonl`이다. 제외한 행은 없다"
        f"(`N = {result['denominators']['sample_rows_N']}`, `L = {result['denominators']['panel_rows_L']}`).", "",
        "## 사전 고정 규칙 결과", "",
        "| 규칙 | RR-L 값 | Repo480 기준 | 판정 |",
        "| --- | --- | --- | --- |",
        f"| R1 applicability | materialization 실패 {r1['materialization_failures']['count']}/{result['denominators']['sample_rows_N']}, "
        f"packet {', '.join(f'{k} {v}' for k, v in r1['packet_status'].items())} | — | 기술 보고 |",
        f"| R2 판정 후 retrieval insufficient/unclear | {ci(r2['adjudicated'])} | 100/480 [0.1744, 0.2469] | "
        f"{'충족' if r2['rule_triggered'] else '미충족'} |",
        f"| R3 raw binary 일치 | {ci(r3['raw_binary_agreement'])} | 430/480 [0.8653, 0.9201] | "
        f"{'충족' if r3['rule_triggered'] else '미충족'} |", "",
        "### R1 applicability", "",
        f"- 120행 모두 materialize됐고 상태는 {', '.join(f'`{k}` {v}행' for k, v in r1['packet_status'].items())}이다. 대체한 행은 없다.",
        "- Evidence category 상태: " + "; ".join(
            f"`{c}` " + ", ".join(f"{k} {v}" for k, v in cats[c].items()) for c in CATEGORIES) + ".",
        f"- Fix PR 시각 검증: {', '.join(f'{k} {v}' for k, v in r1['fix_pr_time_verification'].items())}. Unverified 행은 "
        f"repository 조직 이관 때문이며({', '.join(f'`{k}` {v}' for k, v in r1['unverified_fix_pr_time_by_repository'].items())}) "
        "protocol대로 실패가 아니다.",
        f"- 표본은 {r1['repository_count']}개 repository에서 왔고 SWE-bench repository 행은 {r1['swebench_repository_rows']}개다.",
        f"- Frame 수준 classifier 적합성(probe): SWE-bench-Live lite 300행의 test 경로 "
        f"{fit['swebench_live_lite_300']['recognized_paths']}/{fit['swebench_live_lite_300']['test_paths']} "
        f"({fit['swebench_live_lite_300']['recognized_share']:.3f})를 인식했고 test 경로를 하나도 인식하지 못한 task는 "
        f"{fit['swebench_live_lite_300']['tasks_none_recognized']}/{fit['swebench_live_lite_300']['tasks_with_test_paths']}개다. "
        f"Repo480 원천 draw는 {fit['repo480_source_draw_600']['recognized_paths']}/{fit['repo480_source_draw_600']['test_paths']}이다.", "",
        "### R2 retrieval failure", "",
        f"- 판정 후: {ci(r2['adjudicated'])}. 하한이 repo480 구간 상한 0.2469보다 "
        f"{'크다' if r2['rule_triggered'] else '크지 않다'}. {r2_reading}",
        f"- Raw pass별: r1 {ci(r2['raw']['r1'])}, r2 {ci(r2['raw']['r2'])}.",
        f"- 해석상 주의: `retrieval_sufficiency`는 controlled field가 아니어서 판정자가 한 번도 override하지 않았다"
        f"(override {post['retrieval_sufficiency_overrides']}건). 판정 후 값은 base annotator의 raw 값이며 base는 r1 "
        f"{post['base_annotator_counts'].get('r1', 0)}행ㆍr2 {post['base_annotator_counts'].get('r2', 0)}행이다. 두 raw pass가 모두 "
        f"표시한 행은 {ci(post['raw_retrieval_flag_intersection'])}, 한쪽이라도 표시한 행은 "
        f"{ci(post['raw_retrieval_flag_union'])}다(사후 기술). R2는 전문가가 packet의 retrieval을 불충분하다고 판단한 "
        "비율이며 packet이 어떤 근거를 실제로 놓쳤는지 직접 측정한 값이 아니다.",
        f"- 경계 근접성: 사전 규칙을 r2 raw pass({'충족' if r2_raw_trigger['r2'] else '미충족'})나 두 pass 공통 표시"
        f"({'충족' if intersection_trigger else '미충족'})에 적용하면 결론이 달라진다. 아래 sensitivity 표의 "
        "\"R2 규칙\" 열도 함께 읽는다.", "",
        "### R3 reproducibility", "",
        f"- Raw binary 일치: {ci(r3['raw_binary_agreement'])}. 상한이 repo480 구간 하한 0.8653보다 "
        f"{'작다' if r3['rule_triggered'] else '작지 않다'}. {r3_reading}",
        f"- Cohen κ {r3['cohen_kappa']:.3f}(판정 통계 아님), PABAK {r3['pabak']:.3f}, exact P0–P3 일치 "
        f"{ci(r3['exact_p0_p3_agreement'])}.",
        f"- Binary 불일치 방향: r1만 P2/P3 {direction['r1_P2P3_r2_P0P1']}행, r2만 P2/P3 {direction['r1_P0P1_r2_P2P3']}행.", "",
        "| r1 \\ r2 | P0 | P1 | P2 | P3 |", "| --- | ---: | ---: | ---: | ---: |",
        *[f"| {a} | " + " | ".join(str(r3["raw_label_crosstab_r1_by_r2"][a][b]) for b in ("P0", "P1", "P2", "P3")) + " |"
          for a in ("P0", "P1", "P2", "P3")], "",
        "## 보조: 판정 후 P2/P3", "",
        f"- 판정 후 P2/P3: {ci(aux['adjudicated'])}; repository cluster bootstrap({boot['repository_count']}개 repository, "
        f"{boot['samples']:,}회, seed `{boot['seed']}`) 95% [{boot['percentile_95_ci']['lower']:.3f}, "
        f"{boot['percentile_95_ci']['upper']:.3f}].",
        f"- Raw marginal: r1 {ci(aux['raw_marginals']['r1'])}, r2 {ci(aux['raw_marginals']['r2'])}.",
        f"- 판정 후 label: {', '.join(f'{k} {v}' for k, v in aux['adjudicated_label_counts'].items())}; data quality: "
        f"{', '.join(f'{k} {v}' for k, v in aux['adjudicated_data_quality_counts'].items())}.",
        "- 이 비율은 이 frame의 고유 기술치다. `26/480`ㆍ`0.094`와 합치거나 비교 검정하지 않고 일반 APR prevalence로 읽지 않는다.", "",
        "## Sensitivity(기술치)", "",
        f"- 실패 task를 retrieval 실패로 센 R2(분모 `N`): {ci(sens['r2_failures_as_retrieval_failure'])}. 실패가 없어 주 결과와 같다.", "",
        "| Subset | n | R2 판정 후 flagged | R2 규칙 | R3 raw binary 일치 | R3 규칙 | 판정 후 P2/P3 |",
        "| --- | ---: | --- | --- | --- | --- | --- |",
    ]
    names = {
        "exclude_raw_protocol_deviation_rows": "raw `protocol_deviation` 행 제외",
        "exclude_raw_or_adjudicator_protocol_deviation_rows": "raw 또는 판정 `protocol_deviation` 행 제외",
        "adjudicated_q0_only": "판정 후 Q0만",
        "swebench_repository_stratum": "SWE-bench repository 층",
        "other_repository_stratum": "그 밖의 repository 층",
    }
    for key, label in names.items():
        p = sens[key]
        out.append(f"| {label} | {p['n']} | {ci(p['r2_adjudicated_flagged'])} | "
                   f"{'충족' if p['r2_rule_would_trigger'] else '미충족'} | {ci(p['r3_raw_binary_agreement'])} | "
                   f"{'충족' if p['r3_rule_would_trigger'] else '미충족'} | {ci(p['adjudicated_p2p3'])} |")
    out += [
        "", "층별 행은 분모가 작아(SWE-bench repository 층 13행) 규칙 열을 판정으로 읽지 않는다.",
    ]
    out += [
        "", f"`protocol_deviation`은 r1 {dev['r1']}행ㆍr2 {dev['r2']}행ㆍ판정 {dev['adjudicator']}행이며 모두 사전 노출(이슈의 이후 "
        "해결을 기억함) 기록이다. Protocol 문언이 raw 이탈만 뺄지 판정 이탈까지 뺄지 정하지 않으므로 두 변형을 모두 보고한다.", "",
        "## 사후 기술(사전 고정 아님)", "",
        f"- Raw retrieval 표시 교차: {', '.join(f'{k} {v}' for k, v in cells.items())}.",
        "- 판정 후 retrieval 표시와 binary label: " + "; ".join(
            f"{label} " + ", ".join(f"{k} {v}" for k, v in counts.items())
            for label, counts in post["adjudicated_flag_by_binary_label"].items()) + ".",
        f"- 참고로 repo480 raw pass의 retrieval 표시율은 r1 {ci(post['repo480_raw_retrieval_flags']['r1'])}, r2 "
        f"{ci(post['repo480_raw_retrieval_flags']['r2'])}였다. 두 frame의 raw role은 다른 전문가이므로 번호끼리 짝지어 "
        "비교하지 않는다.",
        f"- Repository evidence(code, test, docs, config)를 근거로 기록한 raw 행: r1 "
        f"{post['raw_rows_recording_repository_evidence']['r1']}/120, r2 {post['raw_rows_recording_repository_evidence']['r2']}/120. "
        "RR-A의 issue-text-only pass와 달리 두 pass 모두 repository evidence를 사용했다.", "",
        "## 해석", "",
        "- **Contract 적용 가능성(R1).** 같은 evidence contract가 52개 repository의 120 task 모두에서 실패 없이 packet을 "
        "만들었다. 다만 frozen classifier는 이 frame의 test 경로를 repo480보다 덜 인식했다"
        f"({fit['swebench_live_lite_300']['recognized_share']:.3f} 대 {fit['repo480_source_draw_600']['recognized_share']:.3f}).",
        f"- **Retrieval 전이(R2).** 사전 규칙상 frozen retrieval policy의 전이가 약하다는 결과가 나왔다"
        f"({r2['adjudicated']['proportion']:.3f} 대 repo480 {REPO480_R2['count'] / REPO480_R2['denominator']:.3f}). 그러나 이 판정은 경계에 가깝다. 하한과 기준 상한의 차이는 "
        f"{interval(r2['adjudicated'])[0] - REPO480_R2['upper']:.3f}에 그치고, raw pass 한쪽과 일부 sensitivity에서는 규칙이 "
        "성립하지 않는다. 또 retrieval 불충분 표시 "
        f"{flagged_by_label['P0/P1'] + flagged_by_label['P2/P3']}행 중 {flagged_by_label['P0/P1']}행은 P0/P1로 판정됐고, 표시율은 "
        f"P0/P1({flagged_by_label['P0/P1']}/{label_totals['P0/P1']})과 P2/P3({flagged_by_label['P2/P3']}/{label_totals['P2/P3']})에서 "
        "비슷했다(사후 기술). 즉 이 frame에서 전문가는 packet 밖 맥락을 더 자주 원했지만, 그 표시가 P2/P3 판정과 함께 "
        "움직이지는 않았다.",
        f"- **Raw 재현성(R3).** Binary 일치({r3['raw_binary_agreement']['proportion']:.3f})는 repo480 {REPO480_R3['count'] / REPO480_R3['denominator']:.3f}보다 낮지만 사전 "
        f"규칙이 정한 큰 하락은 아니다. κ({r3['cohen_kappa']:.3f})가 낮은 것은 P2/P3 비율이 낮을 때 κ가 작아지는 성질과 "
        f"함께 읽어야 한다(PABAK {r3['pabak']:.3f}). 불일치는 r1이 더 자주 P2/P3를 준 방향으로 기울었다"
        f"({direction['r1_P2P3_r2_P0P1']} 대 {direction['r1_P0P1_r2_P2P3']}). Exact P0–P3 일치는 "
        f"{r3['exact_p0_p3_agreement']['proportion']:.3f}이며, 4-class 불일치 "
        f"{panel_l - r3['exact_p0_p3_agreement']['count']}행 중 {p0_p1}행이 P0와 P1 사이에서 일어났다.",
        f"- **보조 P2/P3.** 이 frame의 판정 후 P2/P3는 {aux['adjudicated']['proportion']:.3f}이며 frame 고유 기술치다.", "",
        "## 수용 기록과 한계", "",
    ]
    out += [f"- {note}" for note in result["acceptance_notes"]]
    out += ["- 수용 뒤 owner가 세 role을 서로 다른 전문가가 확정했음을 확인했고, 두 raw 초안의 AI 분리 여부는 전문가 "
            "재검토를 거쳤으므로 R3에 영향이 없다고 판단했다(`docs/decisions/README.md`)."]
    out += [f"- {note}" for note in result["claim_boundary"]]
    out += ["", "입력 hash와 전체 수치는 동명 JSON에 있다.", "", "```bash",
            f"uv run python scripts/analyze_rrl_ext120_panel.py --analyzed-on {result['analyzed_on']}", "```", ""]
    return "\n".join(out)


def tex(result: dict[str, Any]) -> str:
    def ci(rate: dict[str, Any]) -> str:
        lower, upper = interval(rate)
        return f"{rate['count']}/{rate['denominator']} [{lower:.3f}, {upper:.3f}]"

    r1, r2, r3 = result["r1_applicability"], result["r2_retrieval_failure"], result["r3_reproducibility"]
    aux, sens = result["auxiliary_p2p3"], result["sensitivity"]
    boot = aux["repository_cluster_bootstrap"]["percentile_95_ci"]
    fit = r1["classifier_fit_frame_level"]["swebench_live_lite_300"]
    verified = r1["fix_pr_time_verification"].get("verified", 0)
    reading = lambda triggered, yes, no: yes if triggered else no
    rows = [
        ("R1 applicability", f"{result['denominators']['panel_rows_L']}/{result['denominators']['sample_rows_N']} packets; "
         f"fix-PR time verified {verified}; test paths recognized {fit['recognized_share']:.3f}", "--", "Descriptive"),
        ("R2 adjudicated retrieval insufficient/unclear", ci(r2["adjudicated"]), "100/480 [0.174, 0.247]",
         reading(r2["rule_triggered"], "Weak transfer", "No large difference")),
        (r"\quad raw passes r1 / r2", f"{ci(r2['raw']['r1'])} / {ci(r2['raw']['r2'])}", "--", "Descriptive"),
        ("R3 raw binary agreement", ci(r3["raw_binary_agreement"]), "430/480 [0.865, 0.920]",
         reading(r3["rule_triggered"], "Low reproducibility", "No large drop")),
        (r"\quad $\kappa$ / PABAK / exact P0--P3", f"{r3['cohen_kappa']:.3f} / {r3['pabak']:.3f} / "
         f"{r3['exact_p0_p3_agreement']['count']}/{r3['exact_p0_p3_agreement']['denominator']}", "--", "Descriptive"),
        ("Adjudicated P2/P3 (frame-specific)", f"{ci(aux['adjudicated'])}; cluster [{boot['lower']:.3f}, {boot['upper']:.3f}]",
         "not compared", "Descriptive"),
        (r"\quad excluding raw/adjudicator deviation rows",
         f"R2 {ci(sens['exclude_raw_or_adjudicator_protocol_deviation_rows']['r2_adjudicated_flagged'])}; "
         f"R3 {ci(sens['exclude_raw_or_adjudicator_protocol_deviation_rows']['r3_raw_binary_agreement'])}", "--", "Descriptive"),
    ]
    out = ["% Generated by analyze_rrl_ext120_panel.py", r"\begin{table}[htbp]", r"\centering\scriptsize",
           r"\caption{RR-L external-frame sensitivity: SWE-bench-Live lite, 120 rows under the frozen evidence contract "
           r"(prespecified rules; Wilson 95\% intervals).}",
           r"\label{tab:rrlexternal}", r"\setlength{\tabcolsep}{3pt}", r"\begin{tabular}{p{0.27\linewidth}p{0.36\linewidth}p{0.17\linewidth}l}",
           r"\toprule", r"Rule / metric & RR-L value & Repo480 reference & Reading \\", r"\midrule"]
    out += [f"{a} & {b} & {c} & {d} " + r"\\" for a, b, c, d in rows]
    out += [r"\bottomrule", r"\end{tabular}", r"\end{table}", ""]
    return "\n".join(out)


def _jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--analyzed-on", required=True, help="YYYY-MM-DD, deterministic replay date")
    for name, default in {
        "returns-manifest": "data/manifests/generated/rrl_ext120_returns_manifest_v1.json",
        "probe": "results/pilot/rrl_external_frame_probe_2026-10-21.json",
        "repo480-labels": "data/annotations/adjudicated/repo480_available_v1.jsonl",
        "repo480-raw-r1": "data/annotations/raw_labels/repo480_available_v1_r1.jsonl",
        "repo480-raw-r2": "data/annotations/raw_labels/repo480_available_v1_r2.jsonl",
        "json-out": "results/pilot/rrl_ext120_external_frame_analysis_v1.json",
        "rows-out": "results/pilot/rrl_ext120_external_frame_rows_v1.jsonl",
        "markdown-out": "results/pilot/rrl_ext120_external_frame_analysis_v1.md",
        "tex-out": "paper/generated/rrl_ext120_external_frame_summary.tex",
    }.items():
        parser.add_argument(f"--{name}", type=Path, default=Path(default))
    args = parser.parse_args()
    try:
        result, rows = analyze(args)
        for path, payload in ((args.json_out, canonical_json_bytes(result)),
                              (args.rows_out, b"".join(canonical_json_bytes(r) for r in rows)),
                              (args.markdown_out, markdown(result).encode()), (args.tex_out, tex(result).encode())):
            target = ROOT / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(payload)
    except (OSError, ValueError, KeyError, TypeError, StopIteration) as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1
    print(f"OK: R2 {'triggered' if result['r2_retrieval_failure']['rule_triggered'] else 'not triggered'}, "
          f"R3 {'triggered' if result['r3_reproducibility']['rule_triggered'] else 'not triggered'}; "
          f"{len(rows)} rows, no exclusions")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
