#!/usr/bin/env python3
"""Summarize annotation agreement for a NotPatch annotation batch."""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from itertools import combinations
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from notpatch.schemas import ValidationError, validate_record


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--labels", required=True, action="append", type=Path)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--pass-name", default="available_only")
    args = parser.parse_args()

    try:
        records = _load_annotation_records(args.labels, args.pass_name)
    except (OSError, json.JSONDecodeError, ValidationError, ValueError) as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1

    report = _build_report(records, args.labels, args.pass_name)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(report, encoding="utf-8")
    print(f"OK: wrote agreement summary to {args.out}")
    return 0


def _load_annotation_records(paths: list[Path], pass_name: str) -> list[dict[str, Any]]:
    records = []
    seen: set[tuple[str, str, str]] = set()
    for path in paths:
        with path.open("r", encoding="utf-8") as handle:
            for line_no, line in enumerate(handle, start=1):
                if not line.strip():
                    continue
                record = json.loads(line)
                if not isinstance(record, dict):
                    raise ValueError(f"{path}:{line_no}: record must be object")
                validate_record(record, "annotation")
                if record["pass"] != pass_name:
                    continue
                key = (record["task_id"], record["annotator_id"], record["pass"])
                if key in seen:
                    raise ValueError(f"{path}:{line_no}: duplicate annotation {key}")
                seen.add(key)
                records.append(record)
    if not records:
        raise ValueError(f"no annotation records with pass={pass_name}")
    return records


def _build_report(
    records: list[dict[str, Any]],
    paths: list[Path],
    pass_name: str,
) -> str:
    by_task: dict[str, list[dict[str, Any]]] = defaultdict(list)
    annotators = set()
    for record in records:
        by_task[record["task_id"]].append(record)
        annotators.add(record["annotator_id"])

    comparable = {
        task_id: task_records
        for task_id, task_records in by_task.items()
        if len(task_records) >= 2
    }

    pair_rows = []
    binary_pairs = []
    primary_pairs = []
    blocker_pairs = []
    data_quality_pairs = []
    disagreements = []

    for task_id, task_records in sorted(comparable.items()):
        for left, right in combinations(sorted(task_records, key=lambda r: r["annotator_id"]), 2):
            pair = _pair_summary(task_id, left, right)
            pair_rows.append(pair)
            binary_pairs.append((pair["left_binary"], pair["right_binary"]))
            primary_pairs.append((left["primary_label"], right["primary_label"]))
            blocker_pairs.append((left.get("primary_blocker"), right.get("primary_blocker")))
            data_quality_pairs.append((left["data_quality"], right["data_quality"]))
            if not all(
                [
                    pair["binary_agree"],
                    pair["primary_label_agree"],
                    pair["primary_blocker_agree"],
                    pair["data_quality_agree"],
                    pair["predicted_direction_agree"],
                ]
            ):
                disagreements.append(pair)

    lines = [
        "# Annotation Agreement Summary",
        "",
        "This report describes fixture or pilot annotation records. It is not an adjudicated result unless the input labels are adjudicated.",
        "",
        "## Inputs",
        "",
    ]
    lines.extend(f"- `{path}`" for path in paths)
    lines.extend(
        [
            "",
            "## Coverage",
            "",
            f"- Annotation pass: `{pass_name}`",
            f"- Records: {len(records)}",
            f"- Annotators: {len(annotators)}",
            f"- Tasks: {len(by_task)}",
            f"- Comparable tasks with at least 2 annotators: {len(comparable)}",
            f"- Pair comparisons: {len(pair_rows)}",
            "",
            "## Agreement",
            "",
            "| Axis | Agreement | Cohen kappa |",
            "| --- | ---: | ---: |",
            _metric_row("Binary P0/P1 vs P2/P3", binary_pairs),
            _metric_row("Primary label", primary_pairs),
            _metric_row("Primary blocker", blocker_pairs),
            _metric_row("Data quality", data_quality_pairs),
            "",
            "## Label Counts",
            "",
            "| Label | Count |",
            "| --- | ---: |",
        ]
    )
    label_counts = Counter(record["primary_label"] for record in records)
    lines.extend(f"| `{label}` | {count} |" for label, count in sorted(label_counts.items()))
    lines.extend(
        [
            "",
            "## Disagreements",
            "",
        ]
    )
    if not disagreements:
        lines.append("No disagreements found in comparable records.")
    else:
        for pair in disagreements:
            lines.extend(
                [
                    f"### `{pair['task_id']}`",
                    "",
                    "| Axis | Left | Right | Agree |",
                    "| --- | --- | --- | --- |",
                    f"| Annotator | `{pair['left_annotator']}` | `{pair['right_annotator']}` | n/a |",
                    f"| Binary | `{pair['left_binary']}` | `{pair['right_binary']}` | `{pair['binary_agree']}` |",
                    f"| Primary label | `{pair['left_primary_label']}` | `{pair['right_primary_label']}` | `{pair['primary_label_agree']}` |",
                    f"| Primary blocker | `{pair['left_primary_blocker']}` | `{pair['right_primary_blocker']}` | `{pair['primary_blocker_agree']}` |",
                    f"| Data quality | `{pair['left_data_quality']}` | `{pair['right_data_quality']}` | `{pair['data_quality_agree']}` |",
                    f"| Predicted direction | `{pair['left_predicted_direction']}` | `{pair['right_predicted_direction']}` | `{pair['predicted_direction_agree']}` |",
                    "",
                ]
            )
    lines.append("")
    return "\n".join(lines)


def _pair_summary(
    task_id: str,
    left: dict[str, Any],
    right: dict[str, Any],
) -> dict[str, Any]:
    left_binary = _binary_label(left["primary_label"])
    right_binary = _binary_label(right["primary_label"])
    left_direction = left.get("predicted_direction")
    right_direction = right.get("predicted_direction")
    return {
        "task_id": task_id,
        "left_annotator": left["annotator_id"],
        "right_annotator": right["annotator_id"],
        "left_binary": left_binary,
        "right_binary": right_binary,
        "binary_agree": left_binary == right_binary,
        "left_primary_label": left["primary_label"],
        "right_primary_label": right["primary_label"],
        "primary_label_agree": left["primary_label"] == right["primary_label"],
        "left_primary_blocker": left.get("primary_blocker"),
        "right_primary_blocker": right.get("primary_blocker"),
        "primary_blocker_agree": left.get("primary_blocker") == right.get("primary_blocker"),
        "left_data_quality": left["data_quality"],
        "right_data_quality": right["data_quality"],
        "data_quality_agree": left["data_quality"] == right["data_quality"],
        "left_predicted_direction": left_direction,
        "right_predicted_direction": right_direction,
        "predicted_direction_agree": left_direction == right_direction,
    }


def _binary_label(label: str) -> str:
    return "P0/P1" if label in {"P0", "P1"} else "P2/P3"


def _metric_row(name: str, pairs: list[tuple[Any, Any]]) -> str:
    if not pairs:
        return f"| {name} | n/a | n/a |"
    agreement = sum(1 for left, right in pairs if left == right) / len(pairs)
    kappa = _cohen_kappa(pairs)
    return f"| {name} | {agreement:.3f} | {kappa:.3f} |"


def _cohen_kappa(pairs: list[tuple[Any, Any]]) -> float:
    if not pairs:
        return 0.0
    observed = sum(1 for left, right in pairs if left == right) / len(pairs)
    left_counts = Counter(left for left, _ in pairs)
    right_counts = Counter(right for _, right in pairs)
    labels = set(left_counts) | set(right_counts)
    expected = sum(
        (left_counts[label] / len(pairs)) * (right_counts[label] / len(pairs))
        for label in labels
    )
    if expected == 1.0:
        return 1.0 if observed == 1.0 else 0.0
    return (observed - expected) / (1.0 - expected)


if __name__ == "__main__":
    raise SystemExit(main())

