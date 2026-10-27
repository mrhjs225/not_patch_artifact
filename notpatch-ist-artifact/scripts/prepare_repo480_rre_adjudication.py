#!/usr/bin/env python3
"""Package Set A derived-type disagreements for a third expert, after both c2 stages."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from notpatch.canonical import canonical_json_bytes, sha256_file
from analyze_repo480_rre_verification import read_jsonl, report_type
from prepare_repo480_rre_verification import GUIDELINE_SHA256, STAGES, _view

BATCH_ID = "repo480_rre_adjudication_v1"
ROLE = "repo480_rre_adj"
WORKLIST_NAME = "repo480_rre_adjudication_worklist.jsonl"
CODES_NAME = "repo480_rre_adj_codes.jsonl"


def build(args: argparse.Namespace) -> dict:
    analysis = json.loads((ROOT / args.analysis).read_text())
    if analysis["status"] != "raw-comparison-pending-adjudication":
        raise ValueError("expected raw c1/c2 comparison")
    for path, digest in analysis["inputs"].items():
        if sha256_file(ROOT / path) != digest:
            raise ValueError(f"comparison input changed: {path}; rerun analysis first")
    if analysis["sets"]["setb"]["disagreement_item_ids"]:
        raise ValueError("Set B disagreements require an available-only stage before this Set A package")
    wanted = analysis["sets"]["seta"]["disagreement_item_ids"]
    if not wanted:
        raise ValueError("no Set A disagreements to adjudicate")
    if str(args.worklist) not in analysis["inputs"] or str(args.c1_codes) not in analysis["inputs"]:
        raise ValueError("worklist and c1 codes must be inputs to the comparison")
    returns = json.loads((ROOT / args.returns_manifest).read_text())
    if str(args.returns_manifest) not in analysis["inputs"]:
        raise ValueError("returns manifest must be an input to the comparison")
    c1 = {r["item_id"]: r for r in read_jsonl(ROOT / args.c1_codes)}
    c2 = {r["item_id"]: r for r in read_jsonl(ROOT / returns["stages"]["seta"]["canonical_ref"])}
    if wanted != [item for item, row in c2.items() if report_type(c1[item]) != report_type(row)]:
        raise ValueError("comparison disagreement list does not reproduce from raw codes")
    work = [r for r in read_jsonl(ROOT / args.worklist) if r["item_id"] in wanted]
    if [r["item_id"] for r in work] != wanted or any(r["set"] != "p1_non_strict" for r in work):
        raise ValueError("adjudication selection does not match the frozen worklist")
    work_manifest = json.loads((ROOT / args.worklist_manifest).read_text())
    if str(args.worklist_manifest) not in analysis["inputs"]:
        raise ValueError("worklist manifest must be an input to the comparison")
    codebook = ROOT / work_manifest["codebook"]["ref"]
    if sha256_file(ROOT / args.guideline) != GUIDELINE_SHA256:
        raise ValueError("guideline differs from frozen v0.5")
    package = ROOT / args.request_root / ROLE
    if package.exists() or package.is_symlink() or (ROOT / args.manifest_out).exists():
        raise ValueError("package or manifest already exists; use fresh scratch paths for replay")
    enriched = [dict(row, coding_comparison={"c1": c1[row["item_id"]], "c2": c2[row["item_id"]]}) for row in work]
    template = [{"schema_version": "repo480-p1-typology-code-v1", "coder_id": ROLE,
                 "item_id": row["item_id"], "task_id": row["task_id"], "set": row["set"],
                 "codes": dict(STAGES["seta"]["template"]), "evidence_refs": [],
                 "coder_note": "", "exposure_note": None} for row in work]
    view = _view(enriched, "adjudication").replace("repo480_rre_adjudication_worklist.jsonl", WORKLIST_NAME)
    sources = {"typology_codebook.md": codebook,
               "annotation_guideline.md": ROOT / args.guideline,
               "selfcheck_repo480_rre_adjudication_return.py": ROOT / "scripts/selfcheck_repo480_rre_adjudication_return.py",
               "selfcheck_repo480_rre_verification_return.py": ROOT / "scripts/selfcheck_repo480_rre_verification_return.py"}
    files = {name: path.read_bytes() for name, path in sources.items()}
    files.update({"request.md": PROTOCOL.encode(), WORKLIST_NAME: b"".join(canonical_json_bytes(r) for r in enriched),
                  "repo480_rre_adjudication_worklist_view.md": view.encode(),
                  CODES_NAME: b"".join(canonical_json_bytes(r) for r in template)})
    package.mkdir(parents=True)
    for name, payload in files.items():
        (package / name).write_bytes(payload)
    package_manifest = {
        "schema_version": "repo480-rre-adjudication-package-v1", "batch_id": BATCH_ID,
        "coder_id": ROLE, "row_count": len(work), "item_ids": wanted,
        "selection": "Set A six-category derived type differs between accepted c1 and c2; no exclusions",
        "editable_file": CODES_NAME, "oracle_material_included": True,
        "coding_comparison": "Full c1/c2 fields, notes and exposure notes; aggregate results are not included.",
        "files": {name: sha256_file(package / name) for name in files},
    }
    manifest_name = "repo480_rre_adjudication_request_manifest_v1.json"
    (package / manifest_name).write_bytes(canonical_json_bytes(package_manifest))
    names = list(files) + [manifest_name]
    checksums = "".join(f"{sha256_file(package / name)}  {name}\n" for name in sorted(names))
    (package / "repo480_rre_adjudication_checksums_v1.sha256").write_text(checksums)
    (ROOT / args.request_root / "README.md").write_text(COORDINATOR)
    manifest = {
        **{k: v for k, v in package_manifest.items() if k != "files"},
        "package_dir_name": ROLE, "package_files": {p.name: sha256_file(p) for p in sorted(package.iterdir())},
        "batch_readme_sha256": sha256_file(ROOT / args.request_root / "README.md"),
        "inputs": {**analysis["inputs"], str(args.analysis): sha256_file(ROOT / args.analysis),
                   **{str(p.relative_to(ROOT)): sha256_file(p) for p in sources.values()},
                   "scripts/prepare_repo480_rre_adjudication.py": sha256_file(Path(__file__))},
    }
    target = ROOT / args.manifest_out
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(canonical_json_bytes(manifest))
    return manifest


PROTOCOL = """# RR-E 유형 불일치 판정 — `repo480_rre_adj`

## 목적과 담당자

첫 코딩(c1, AI analytic coding)과 독립 전문가 코딩(c2)을 비교했을 때 유도 유형이 갈린 Set A 10행을
판정합니다. c2 전문가와 다른 전문가가 직접 수행합니다. 기존 코딩을 고치는 작업이 아니라 별도 판정을
남기는 작업이며, c1이나 c2 중 반드시 하나를 선택해야 하는 것은 아닙니다.

## 자료와 경계

이 폴더만 사용합니다. `repo480_rre_adjudication_worklist.jsonl`은 원래 Set A worklist의 모든 값을 그대로
보존하고 `coding_comparison.c1`과 `.c2`에 두 코더의 원문을 추가했습니다. 읽기용 view도 같은 내용을
펼쳐 보여 줍니다. 집계 결과나 선호 판정은 제공하지 않습니다.

- `typology_codebook.md` §3, §4, §4.1의 동결 규칙을 적용합니다. `annotation_guideline.md`는 정의 참고용입니다.
- Issue, frozen 기록, boundary panel, construct-validity 판정, 제공된 oracle patch/test만 근거로 씁니다.
- 원 repository, 웹, SWE-bench hints, 추가 PR 논의, detector/agent 결과를 열지 않습니다.
- 기존 기록이 packet을 서로 다르게 서술하면 새 자료로 해소하지 않고 해당 field를 `unclear`로 둡니다.
- 제공된 일부 construct-validity rationale에는 hints나 사후 maintainer 논의 언급이 남아 있습니다.
  원본 보존을 위해 지우지 않았으며, 이를 새 판단 근거로 사용하지 않습니다. 읽게 된 내용과 판단에
  미친 영향은 `exposure_note`에 기록합니다. 원 코더의 노출 기록도 그대로 포함했습니다.

## 작성할 파일

`repo480_rre_adj_codes.jsonl`의 `codes`, `evidence_refs`, `coder_note`, `exposure_note`만 작성합니다.
행 순서ㆍ식별자ㆍschemaㆍcoder ID는 바꾸지 않습니다. 반환 template은 의도적으로 비어 있습니다.

1. `coding_comparison`의 두 코더 field와 note를 읽고 갈림의 근거를 비교합니다.
2. 각 행의 결정적 차이는 codebook §4의 규칙(최종 construct-validity 판정이 먼저 든 차이)으로 정합니다.
3. `codes`의 여섯 field를 모두 작성합니다. 허용 값과 applicability는 codebook §4를 따릅니다.
   `implementation_only`일 때만 `oracle_basis`와 `assumption_anticipated`를 `not_applicable`로 둡니다.
4. `coder_note`에는 갈린 field를 어떻게 판정했는지, 어느 근거로 c1/c2 또는 다른 값을 채택했는지
   설명합니다. `unclear`도 유효한 판정이며 확신을 강요하지 않습니다. 원 코더와 협의하지 않습니다.
5. `evidence_refs`에는 원 worklist의 실제 key 경로를 적습니다(예: `frozen.canonical.rationale`,
   `construct_validity.adjudication.rationale`, `oracle.test_patch:test_name`). 코더의 결론만 인용하지 않습니다.
6. 새로운 사전 노출이나 제공 기록 속 금지 자료 언급을 읽었으면 `exposure_note`에 기록합니다.
   없으면 `null`입니다. 주 유형은 적지 않으며 분석기가 field에서 유도합니다.

## 검사와 반환

작성 전 `sha256sum -c repo480_rre_adjudication_checksums_v1.sha256`으로 검사합니다. 작성 뒤에는
codes 파일 하나의 checksum만 바뀌는 것이 정상입니다.

```bash
python3 selfcheck_repo480_rre_adjudication_return.py \\
  --worklist repo480_rre_adjudication_worklist.jsonl \\
  --codes repo480_rre_adj_codes.jsonl
```

`OK`가 나온 codes 파일 하나만 coordinator에게 반환합니다. Frozen P0--P3 label은 수정하지 않습니다.
"""

COORDINATOR = """# RR-E 불일치 판정 배포 안내

- **Status:** `active`
- **Authority:** coordinator용 배정ㆍ배포ㆍ회수 규칙
- **Batch:** `repo480_rre_adjudication_v1`
- **Role:** `repo480_rre_adj` (배정 대기)

반환 전 고정한 계획대로 유도 유형이 갈린 Set A 10행만 판정한다. Set B는 22행 모두 유형이 일치해
대상이 없다. 유형은 같고 field만 다른 행은 추가하지 않는다. 두 원 코딩과 exposure note는 보존한다.

`repo480_rre_adj/` 폴더만 c2와 다른 제3 전문가에게 전달한다. 코딩 대상의 원래 annotation을 작성한
role과도 다른 전문가를 배정하고, 불가피한 overlap이 있으면 수용 시 deviation으로 남긴다.
AI/LLM 출력으로 전문가 판정을 대신하지 않는다. 이 README나 root request 전체는 전달하지 않는다.

회수 시 package의 읽기 전용 hash, selfcheck, evidence pointer와 exposure 기록을 확인한다.
원문을 byte 그대로 `data/annotations/typology/repo480_p1_typology_codes_adj_v1.jsonl`에 보존하고 별도
returns manifest를 만든다. 현재 이 canonical 파일과 수용 CLI는 아직 없다. 자동으로 빈 template을
수용하거나 원 코더 코드를 덮어쓰지 않는다. 판정 뒤의 주 유형 분포와 c1/c2 단독 sensitivity를 함께
보고한다. 유형이 일치한 행의 fieldㆍsecondary type을 합의 결과로 간주하지 않는다.
"""


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    defaults = {
        "analysis": "results/pilot/repo480_rre_verification_analysis_v1.json",
        "worklist": "data/annotations/worklists/repo480_p1_typology_worklist_v1.jsonl",
        "worklist-manifest": "data/manifests/generated/repo480_p1_typology_worklist_manifest_v1.json",
        "c1-codes": "data/annotations/typology/repo480_p1_typology_codes_c1_v1.jsonl",
        "returns-manifest": "data/manifests/generated/repo480_rre_verification_returns_manifest_v1.json",
        "guideline": "docs/annotation_guideline.md",
        "request-root": "request/repo480_rre_adjudication",
        "manifest-out": "data/manifests/generated/repo480_rre_adjudication_manifest_v1.json",
    }
    for name, default in defaults.items():
        parser.add_argument(f"--{name}", type=Path, default=Path(default))
    args = parser.parse_args()
    try:
        manifest = build(args)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1
    print(f"OK: {manifest['row_count']} disagreements packaged for {ROLE}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
