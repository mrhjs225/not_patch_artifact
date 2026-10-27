#!/usr/bin/env python3
"""Accept the RR-L ext120 raw and adjudication returns as byte-identical canonical copies.

Each raw return must pass the distributed selfcheck and differ from the frozen blank worklist only in
writable fields. The adjudication worklist and post-adjudication labels must follow from the two raw
returns under the distributed adjudication validator, and every hash in the adjudicator manifest must
match. An existing different canonical copy or returns manifest is never replaced.
"""

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

from notpatch.canonical import canonical_json_bytes, sha256_bytes, sha256_file  # noqa: E402
import selfcheck_rrl_ext120_adjudication_return as adj_check  # noqa: E402
from prepare_rrl_ext120_panel import (  # noqa: E402
    ADJUDICATOR_ID,
    BATCH_ID,
    PACKET_POLICY_ID,
    RAW_ROLES,
    _worklist_row,
)
from selfcheck_rrl_ext120_return import validate_return  # noqa: E402

RAW_SELFCHECK = Path("scripts/selfcheck_rrl_ext120_return.py")
ADJ_SELFCHECK = Path("scripts/selfcheck_rrl_ext120_adjudication_return.py")
ROLE_MANIFEST = "rrl_ext120_request_manifest_v1.json"
ADJ_MANIFEST = "rrl_ext120_adj_manifest_v1.json"
ADJ_FILES = {
    "worklist": "rrl_ext120_adj_worklist.jsonl",
    "decisions": "rrl_ext120_adj_decisions.jsonl",
    "post_adjudication_labels": "rrl_ext120_post_adjudication_labels.jsonl",
    "summary": "rrl_ext120_adj_summary.md",
}
ROWKEYS_NAME = "rrl_ext120_rowkeys_v1.json"

# The distributed validator resolves the raw selfcheck by package layout; use the identical repo copy.
adj_check.RAW_SELFCHECK = ROOT / RAW_SELFCHECK


def accept(args: argparse.Namespace) -> dict[str, Any]:
    date.fromisoformat(args.accepted_on)
    request = ROOT / args.request_dir
    panel = _read_json(ROOT / args.panel_manifest)
    identity = (panel["annotation_batch_id"], panel["packet_policy_id"], tuple(panel["raw_roles"]),
                panel["adjudicator_role"])
    if identity != (BATCH_ID, PACKET_POLICY_ID, RAW_ROLES, ADJUDICATOR_ID):
        raise ValueError("unexpected panel batch, policy or roles")
    archives = [entry["sha256"] for entry in panel["reviewer_view_archives"]]
    for entry in panel["reviewer_view_archives"]:
        if sha256_file(request / Path(entry["ref"]).name) != entry["sha256"]:
            raise ValueError(f"reviewer-view archive changed: {entry['ref']}")

    outputs: dict[str, bytes] = {}
    raw: dict[str, list[dict[str, Any]]] = {}
    raw_entries: dict[str, dict[str, Any]] = {}
    for role in RAW_ROLES:
        package = request / role
        manifest_path = package / ROLE_MANIFEST
        if sha256_file(manifest_path) != panel["role_packages"][role]["request_manifest"]["sha256"]:
            raise ValueError(f"{role}: request manifest changed")
        files = _read_json(manifest_path)["files"]
        for name, entry in files.items():
            if name != "worklist" and sha256_file(package / entry["ref"]) != entry["sha256"]:
                raise ValueError(f"{role}: package file changed: {entry['ref']}")
        if sha256_file(ROOT / RAW_SELFCHECK) != files["selfcheck"]["sha256"]:
            raise ValueError("repository raw selfcheck differs from the distributed copy")
        rowkeys = (package / files["rowkeys"]["ref"]).read_bytes()
        if outputs.setdefault(ROWKEYS_NAME, rowkeys) != rowkeys:
            raise ValueError("raw role packages carry different rowkeys")
        payload = (package / files["worklist"]["ref"]).read_bytes()
        rows = _load_jsonl(payload)
        validate_return(rows, json.loads(rowkeys), role)
        # Resetting writable fields must reproduce the shipped blank worklist byte for byte.
        blank = b"".join(canonical_json_bytes(_worklist_row(row, role)) for row in rows)
        if sha256_bytes(blank) != files["worklist"]["sha256"]:
            raise ValueError(f"{role}: a locked field differs from the frozen blank worklist")
        raw[role] = rows
        outputs[f"{role}_v1.jsonl"] = payload
        raw_entries[role] = {
            "ref": str(args.canonical_dir / f"{role}_v1.jsonl"),
            "sha256": sha256_bytes(payload),
            "row_count": len(rows),
            "annotation_status_counts": dict(sorted(Counter(r["annotation_status"] for r in rows).items())),
            "frozen_baseline": {"diff_verified": True, "package_sha256": files["worklist"]["sha256"],
                                "source": "reconstructed_blank_worklist"},
            "protocol_deviations": {r["task_id"]: r["protocol_deviation"] for r in rows
                                    if r["protocol_deviation"] is not None},
        }

    adj_dir = request / ADJUDICATOR_ID
    adj_manifest_bytes = (adj_dir / ADJ_MANIFEST).read_bytes()
    adj_manifest = json.loads(adj_manifest_bytes)
    if (adj_manifest["annotation_batch_id"], adj_manifest["adjudicator_id"]) != (BATCH_ID, ADJUDICATOR_ID):
        raise ValueError("unexpected adjudicator manifest batch or role")
    inputs = adj_manifest["inputs"]
    expected_inputs = {
        **{role: sha256_bytes(outputs[f"{role}_v1.jsonl"]) for role in RAW_ROLES},
        "annotation_guideline": panel["inputs"]["annotation_guideline"]["sha256"],
        "rowkeys": sha256_bytes(outputs[ROWKEYS_NAME]),
        "raw_selfcheck": sha256_file(ROOT / RAW_SELFCHECK),
    }
    for name, digest in expected_inputs.items():
        if inputs[name]["sha256"] != digest:
            raise ValueError(f"adjudicator input {name} differs from the accepted bytes")
    if [entry["sha256"] for entry in inputs["reviewer_view_archives"]] != archives:
        raise ValueError("adjudicator reviewer-view archives differ from the panel manifest")
    for name, source in adj_manifest["rule_sources"].items():
        if sha256_file(ROOT / source["ref"].split("#")[0]) != source["sha256"]:
            raise ValueError(f"adjudication rule source changed: {name}")
    for name, filename in {**ADJ_FILES, "selfcheck": "rrl_ext120_adj_selfcheck.py"}.items():
        entry = adj_manifest["outputs"][name]
        if entry["ref"] != filename or sha256_file(adj_dir / filename) != entry["sha256"]:
            raise ValueError(f"adjudicator output {name} does not match its manifest hash")
    if sha256_file(ROOT / ADJ_SELFCHECK) != adj_manifest["outputs"]["selfcheck"]["sha256"]:
        raise ValueError("repository adjudication validator differs from the distributed copy")

    adj_bytes = {name: (adj_dir / filename).read_bytes() for name, filename in ADJ_FILES.items()}
    worklist = _load_jsonl(adj_bytes["worklist"])
    if worklist != adj_check.build_worklist(raw):
        raise ValueError("adjudication worklist does not follow from the two raw returns")
    decisions = _load_jsonl(adj_bytes["decisions"])
    status = adj_check.validate_decisions(worklist, decisions)
    if _load_jsonl(adj_bytes["post_adjudication_labels"]) != adj_check.build_final(raw, decisions):
        raise ValueError("post-adjudication labels do not follow from the raw returns and decisions")
    adjudicated = {row["task_id"] for row in worklist}
    outputs.update({f"rrl_ext120_adj_{name}_v1.jsonl": adj_bytes[name] for name in ("worklist", "decisions")})
    outputs["rrl_ext120_post_adjudication_labels_v1.jsonl"] = adj_bytes["post_adjudication_labels"]
    outputs["rrl_ext120_adj_summary_v1.md"] = adj_bytes["summary"]
    outputs["rrl_ext120_adj_return_manifest_v1.json"] = adj_manifest_bytes

    def canonical(name: str) -> dict[str, str]:
        return {"ref": str(args.canonical_dir / name), "sha256": sha256_bytes(outputs[name])}

    result = {
        "schema_version": "rrl-ext120-returns-manifest-v1",
        "annotation_batch_id": BATCH_ID,
        "packet_policy_id": PACKET_POLICY_ID,
        "accepted_on": args.accepted_on,
        "panel_manifest": {"ref": str(args.panel_manifest), "sha256": sha256_file(ROOT / args.panel_manifest)},
        "rowkeys": canonical(ROWKEYS_NAME),
        "raw_returns": raw_entries,
        "adjudication": {
            "adjudicator_id": ADJUDICATOR_ID,
            "returned_on": adj_manifest["returned_on"],
            "worklist": {**canonical("rrl_ext120_adj_worklist_v1.jsonl"), "row_count": len(worklist)},
            "decisions": {**canonical("rrl_ext120_adj_decisions_v1.jsonl"), "row_count": len(decisions)},
            "post_adjudication_labels": {**canonical("rrl_ext120_post_adjudication_labels_v1.jsonl"),
                                         "row_count": len(raw[RAW_ROLES[0]])},
            "summary": canonical("rrl_ext120_adj_summary_v1.md"),
            "return_manifest": canonical("rrl_ext120_adj_return_manifest_v1.json"),
            "validator": {"ref": str(ADJ_SELFCHECK), "sha256": sha256_file(ROOT / ADJ_SELFCHECK)},
            "adjudication_status_counts": dict(sorted(status.items())),
            "exact_agreement_task_ids": [r["task_id"] for r in raw[RAW_ROLES[0]] if r["task_id"] not in adjudicated],
            "protocol_deviations": {d["task_id"]: d["protocol_deviation"] for d in decisions
                                    if d["protocol_deviation"] is not None},
        },
        "acceptance_gate": {
            "raw_package_files_unchanged": True,
            "raw_selfcheck_passed": True,
            "raw_frozen_baseline_diff_verified": True,
            "reviewer_view_archives_unchanged": True,
            "adjudicator_manifest_hashes_verified": True,
            "adjudication_worklist_recomputed_from_raw": True,
            "adjudication_selfcheck_passed": True,
            "post_adjudication_labels_recomputed": True,
            "all_rows_adjudicated": status.get("unresolved", 0) == 0,
        },
        "acceptance_notes": list(args.acceptance_note),
        "acceptance_script": {"ref": "scripts/accept_rrl_ext120_returns.py", "sha256": sha256_file(Path(__file__))},
        "next_stage": "R1-R3 and auxiliary analysis fixed in docs/rrl_external_frame_protocol.md section 5",
    }

    writes = [(ROOT / args.canonical_dir / name, payload) for name, payload in outputs.items()]
    writes.append((ROOT / args.returns_manifest, canonical_json_bytes(result)))
    for path, payload in writes:
        if path.exists() and path.read_bytes() != payload:
            raise ValueError(f"refusing to replace a different accepted artifact: {path}")
    for path, payload in writes:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(payload)
    return result


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _load_jsonl(payload: bytes) -> list[dict[str, Any]]:
    return [json.loads(line) for line in payload.decode("utf-8").splitlines() if line.strip()]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--accepted-on", required=True, help="YYYY-MM-DD")
    parser.add_argument("--acceptance-note", action="append", default=[],
                        help="coordinator provenance or limitation recorded at acceptance (repeatable)")
    for name, default in {
        "request-dir": "request/rrl_ext120_panel",
        "panel-manifest": "data/manifests/generated/rrl_ext120_panel_manifest_v1.json",
        "canonical-dir": "data/annotations/external_frame",
        "returns-manifest": "data/manifests/generated/rrl_ext120_returns_manifest_v1.json",
    }.items():
        parser.add_argument(f"--{name}", type=Path, default=Path(default))
    try:
        result = accept(parser.parse_args())
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1
    rows = {role: entry["row_count"] for role, entry in result["raw_returns"].items()}
    print(f"OK: accepted raw returns {rows} and "
          f"{result['adjudication']['decisions']['row_count']} adjudication decisions")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
