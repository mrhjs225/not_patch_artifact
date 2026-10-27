#!/usr/bin/env python3
"""Inspect the standalone RR-F evidence archive and validate expert returns."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import zipfile
from pathlib import Path


ROLE = "repo480_retrieval_r1"
RETURN_NAME = "repo480_retrieval_r1_return.jsonl"
WORKLIST_NAME = "worklist.jsonl"
MANIFEST_NAME = "package_manifest.json"
ARCHIVE_NAME = "repo480_unbudgeted_sources_v1.zip"
SCHEMA = "repo480-expanded-retrieval-judgment-v1"


def canonical(value):
    return (json.dumps(value, ensure_ascii=False, sort_keys=True,
                       separators=(",", ":"), allow_nan=False) + "\n").encode()


def digest(path):
    with Path(path).open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def load_rows(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]


def template(row):
    return {
        "schema_version": SCHEMA, "annotator_id": ROLE,
        "item_id": row["item_id"], "task_id": row["task_id"],
        "work_item_sha256": hashlib.sha256(canonical(row)).hexdigest(),
        "annotation_status": "pending", "expanded_label": None, "data_quality": None,
        "expanded_retrieval_sufficiency": None,
        "candidate_directions": [], "bounded_assumptions": None,
        "evidence_assessment": None, "evidence_refs": [], "search_trace": [],
        "rationale": "", "missing_evidence": "",
        "exposure_note": None, "protocol_deviation": None,
    }


def require(condition, message):
    if not condition:
        raise ValueError(message)


def nonempty(value):
    return isinstance(value, str) and bool(value.strip())


def verify_package(directory):
    manifest = json.loads((directory / MANIFEST_NAME).read_text())
    for name, expected in manifest["readonly_sha256"].items():
        require(Path(name).name == name, "unsafe package filename")
        require(digest(directory / name) == expected, f"readonly hash mismatch: {name}")
    rows = load_rows(directory / WORKLIST_NAME)
    require(len(rows) == manifest["row_count"], "worklist count mismatch")
    require(len({r["task_id"] for r in rows}) == len(rows), "duplicate worklist task")
    return rows


def packet(archive, item):
    return json.loads(archive.read(f"{item}/frozen_packet.json"))


def resolve_text(archive, item, ref):
    source = ref["source"]
    if source == "repository":
        name = ref["path"]
        require(isinstance(name, str) and name and not name.startswith("/")
                and ".." not in name.split("/"), "unsafe evidence path")
        return archive.read(f"{item}/repository/{name}").decode("utf-8")
    require(source == "frozen_packet", "invalid evidence source")
    fields = ref["path"].split(".")
    require(fields[0] == "available_evidence", "packet reference must be available evidence")
    value = packet(archive, item)
    for field in fields:
        value = value[int(field)] if isinstance(value, list) else value[field]
    require(isinstance(value, str), "packet reference must point to text")
    return value


def reference_coverage(archive, item, ref):
    if ref["source"] != "repository":
        return "non_repository"
    selected = []
    for category in ("retrieved_code", "visible_tests", "docs", "configs"):
        selected += [v for v in packet(archive, item)["available_evidence"][category]
                     if v["path"] == ref["path"]]
    if not selected:
        return "file_not_in_frozen_packet"
    start, end = ref["line_start"], ref["line_end"]
    for value in selected:
        if not value["content_truncated"]:
            return "already_in_frozen_packet"
        if (all(any(lo <= line <= hi for lo, hi in value["included_line_ranges"])
                for line in range(start, end + 1))
                and ref["quote"] in "\n".join(value["content"].splitlines())):
            return "already_in_frozen_packet"
    return "lines_not_fully_in_frozen_packet"


def validate(directory, return_path):
    work = verify_package(directory)
    returned = load_rows(return_path)
    require(len(returned) == len(work), "return count mismatch")
    audit = []
    with zipfile.ZipFile(directory / ARCHIVE_NAME) as archive:
        for expected, row in zip(work, returned, strict=True):
            item = expected["item_id"]
            base = template(expected)
            require(set(row) == set(base), f"{item}: return keys changed")
            for key in ("schema_version", "annotator_id", "item_id", "task_id", "work_item_sha256"):
                require(row[key] == base[key], f"{item}: identity changed: {key}")
            status = row["annotation_status"]
            require(status in {"complete", "not_assessable", "protocol_deviation"},
                    f"{item}: incomplete annotation_status")
            for key in ("exposure_note", "protocol_deviation", "bounded_assumptions"):
                require(row[key] is None or nonempty(row[key]), f"{item}: {key} must be null or text")
            require((status == "protocol_deviation") == (row["protocol_deviation"] is not None),
                    f"{item}: deviation status/note mismatch")
            require(nonempty(row["rationale"]) and nonempty(row["missing_evidence"]),
                    f"{item}: rationale and missing_evidence are required (write none if absent)")
            label = row["expanded_label"]
            if status == "not_assessable":
                require(label is None, f"{item}: failure must not be a P-label")
            else:
                require(label in {"P0", "P1", "P2", "P3"}, f"{item}: invalid expanded label")
            require(row["data_quality"] in {"Q0", "Q1", "Q2", None}, f"{item}: invalid quality")
            require(status == "not_assessable" or row["data_quality"] is not None,
                    f"{item}: quality required")
            require(row["expanded_retrieval_sufficiency"] in {"sufficient", "insufficient", "unclear"},
                    f"{item}: invalid expanded retrieval sufficiency")
            require(isinstance(row["candidate_directions"], list), f"{item}: invalid candidates")
            candidates = row["candidate_directions"]
            require(label is None or len(candidates) >= (2 if label == "P2" else 1),
                    f"{item}: too few candidate directions")
            for candidate in candidates:
                require(set(candidate) == {"component", "trigger", "observable_behavior"}
                        and all(nonempty(v) for v in candidate.values()), f"{item}: invalid candidate")
            require(label != "P2" or len({c["observable_behavior"] for c in candidates}) >= 2,
                    f"{item}: P2 needs distinct observable behaviors")
            require(label != "P1" or nonempty(row["bounded_assumptions"]), f"{item}: P1 needs assumptions")
            require(row["evidence_assessment"] in {"new_decisive_evidence", "corroboration_only",
                    "still_insufficient", "unclear"}, f"{item}: invalid evidence assessment")
            trace = row["search_trace"]
            require(isinstance(trace, list) and (trace or status == "not_assessable"),
                    f"{item}: missing search trace")
            for step in trace:
                require(set(step) == {"query", "scope", "basis", "observation"}
                        and all(nonempty(v) for v in step.values()), f"{item}: invalid search step")
            refs = row["evidence_refs"]
            require(isinstance(refs, list) and (refs or status == "not_assessable"),
                    f"{item}: missing evidence references")
            coverage = []
            for ref in refs:
                require(set(ref) == {"source", "path", "line_start", "line_end", "quote"},
                        f"{item}: invalid reference keys")
                content = resolve_text(archive, item, ref).splitlines()
                lo, hi = ref["line_start"], ref["line_end"]
                require(type(lo) is int and type(hi) is int and 1 <= lo <= hi <= len(content),
                        f"{item}: invalid line range")
                require(nonempty(ref["quote"]) and ref["quote"] in "\n".join(content[lo-1:hi]),
                        f"{item}: quote not found at cited lines")
                coverage.append(reference_coverage(archive, item, ref))
            require(row["evidence_assessment"] != "new_decisive_evidence" or any(
                c in {"file_not_in_frozen_packet", "lines_not_fully_in_frozen_packet"} for c in coverage),
                f"{item}: new decisive evidence requires an outside-packet reference")
            audit.append({"item_id": item, "annotation_status": status,
                          "reference_coverage": coverage, "search_steps": len(trace)})
    return audit


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--package-dir", type=Path, default=Path(__file__).resolve().parent)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("verify", help="Verify all read-only files; editable return is excluded")
    check = sub.add_parser("check", help="Validate a completed return, including quotes and line ranges")
    check.add_argument("--return-file", type=Path)
    for name in ("list", "search", "show", "issue"):
        command = sub.add_parser(name)
        command.add_argument("--item", required=True)
        if name == "search":
            command.add_argument("--query", required=True, help="Case-insensitive literal text")
            command.add_argument("--path-prefix", default="")
        if name == "show":
            command.add_argument("--path", required=True)
            command.add_argument("--start", type=int, default=1)
            command.add_argument("--end", type=int, help="Default: through end of file")
    args = parser.parse_args()
    try:
        directory = args.package_dir
        if args.command == "verify":
            print(f"OK: {len(verify_package(directory))} work items; all read-only hashes match")
        elif args.command == "check":
            result = validate(directory, args.return_file or directory / RETURN_NAME)
            print(json.dumps({"status": "OK", "rows": result}, ensure_ascii=False, indent=2))
        else:
            work = load_rows(directory / WORKLIST_NAME)
            require(args.item in {r["item_id"] for r in work}, "unknown item")
            with zipfile.ZipFile(directory / ARCHIVE_NAME) as archive:
                prefix = f"{args.item}/repository/"
                if args.command == "issue":
                    values = packet(archive, args.item)["available_evidence"]
                    print(values["issue_title"])
                    for i, line in enumerate(values["issue_body"].splitlines(), 1):
                        print(f"{i}: {line}")
                elif args.command == "show":
                    value = resolve_text(archive, args.item, {"source": "repository", "path": args.path})
                    lines = value.splitlines()
                    end = len(lines) if args.end is None else args.end
                    require(1 <= args.start <= end <= len(lines), "invalid show range")
                    for i in range(args.start, end + 1):
                        print(f"{i}: {lines[i-1]}")
                else:
                    for name in archive.namelist():
                        if not name.startswith(prefix):
                            continue
                        path = name[len(prefix):]
                        if args.command == "list":
                            print(path)
                        elif path.startswith(args.path_prefix):
                            for i, line in enumerate(archive.read(name).decode().splitlines(), 1):
                                if args.query.casefold() in line.casefold():
                                    print(f"{path}:{i}:{line}")
        return 0
    except (OSError, ValueError, KeyError, TypeError, IndexError, zipfile.BadZipFile) as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
