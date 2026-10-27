"""Frozen constants and hash views for repository evidence protocol v1."""

from __future__ import annotations

import re
from collections import Counter
from pathlib import PurePosixPath
from typing import Any, Iterable

from notpatch.canonical import sha256_json


PACKET_POLICY_ID = "swebench-repo480-v1"
# RR-L external frame; same contract, new IDs (docs/rrl_external_frame_protocol.md).
SWEBENCH_LIVE_PACKET_POLICY_ID = "swebench-live-lite-ext120-v1"
PACKET_POLICY_IDS = (PACKET_POLICY_ID, SWEBENCH_LIVE_PACKET_POLICY_ID)
SCHEMA_VERSION = "evidence-packet-v0.2"
RETRIEVAL_ALGORITHM_ID = "lexical-bm25-v1"
EVIDENCE_BOUNDARY_DIGEST_ID = "repo480-evidence-boundary-v1"
BM25_K1 = 1.2
BM25_B = 0.75
MAX_BLOB_BYTES = 1024 * 1024
MAX_EXCERPT_BYTES = 64 * 1024
PACKET_REPOSITORY_BUDGET_BYTES = 1536 * 1024
CATEGORY_QUOTAS = {
    "retrieved_code": 12,
    "visible_tests": 8,
    "docs": 5,
    "configs": 5,
}

CONFIG_BASENAMES = frozenset(
    {
        ".babelrc",
        ".coveragerc",
        ".editorconfig",
        ".flake8",
        ".gitignore",
        ".pre-commit-config.yaml",
        ".pre-commit-config.yml",
        "cargo.toml",
        "cmakelists.txt",
        "dockerfile",
        "gemfile",
        "makefile",
        "manifest.in",
        "package-lock.json",
        "package.json",
        "pipfile",
        "poetry.lock",
        "pom.xml",
        "pyproject.toml",
        "pytest.ini",
        "requirements.txt",
        "setup.cfg",
        "setup.py",
        "tox.ini",
        "uv.lock",
    }
)
CONFIG_SUFFIXES = frozenset(
    {
        ".cfg",
        ".ini",
        ".lock",
        ".toml",
        ".yaml",
        ".yml",
    }
)
DOC_BASENAME_PREFIXES = (
    "changelog",
    "changes",
    "contributing",
    "history",
    "license",
    "readme",
)
DOC_SUFFIXES = frozenset({".md", ".mdx", ".rst", ".txt"})
SOURCE_SUFFIXES = frozenset(
    {
        ".c",
        ".cc",
        ".clj",
        ".cpp",
        ".cs",
        ".css",
        ".dart",
        ".ex",
        ".exs",
        ".go",
        ".h",
        ".hpp",
        ".hs",
        ".html",
        ".java",
        ".js",
        ".jsx",
        ".kt",
        ".kts",
        ".lua",
        ".m",
        ".php",
        ".pl",
        ".py",
        ".pyi",
        ".r",
        ".rb",
        ".rs",
        ".scala",
        ".sh",
        ".sql",
        ".swift",
        ".ts",
        ".tsx",
        ".vue",
        ".xml",
    }
)

TOKEN_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_./:-]*|[0-9]+")
CAMEL_RE = re.compile(r"[A-Z]+(?=[A-Z][a-z]|\d|$)|[A-Z]?[a-z]+|[A-Z]+|\d+")
PATH_SPLIT_RE = re.compile(r"[_./:-]+")

REVIEWER_EVIDENCE_CATEGORIES = (
    "public_comments_until_cutoff",
    "retrieved_code",
    "visible_tests",
    "docs",
    "configs",
    "linked_artifacts",
)
REVIEWER_ITEM_FIELDS = (
    "evidence_id",
    "kind",
    "source_locator",
    "path",
    "source_commit",
    "created_at",
    "updated_at",
    "cutoff_status",
    "selection_reason",
    "content",
    "content_sha256",
    "full_blob_sha",
    "size_bytes",
    "content_truncated",
    "included_line_ranges",
)
EVIDENCE_BOUNDARY_COMPONENT_FIELDS = {
    "issue_packet": ("rule", "source_ref", "verification_status"),
    "repository_snapshot": ("rule", "commit_sha", "verification_status"),
    "public_artifacts": (
        "rule",
        "cutoff_timestamp",
        "cutoff_source",
        "cutoff_source_field",
        "cutoff_verification_status",
    ),
}
EVIDENCE_BOUNDARY_REPOSITORY_FIELDS = (
    "remote",
    "commit_object_verified",
    "tree_sha",
    "inventory_sha256",
    "regular_blob_count",
    "text_corpus_count",
)
EVIDENCE_BOUNDARY_RETRIEVAL_FIELDS = (
    "algorithm_id",
    "parameter_sha256",
    "query_source_sha256",
    "reviewer_query",
)
EVIDENCE_BOUNDARY_STATUS_FIELDS = ("status", "reason", "attempted_source")

FORBIDDEN_REVIEWER_KEYS = frozenset(
    {
        "patch",
        "test_patch",
        "fail_to_pass",
        "pass_to_pass",
        "hints_text",
        "changed_files",
        "fix_diff",
        "hidden_tests",
        "later_outcome",
        "primary_label",
        "seed_label",
        "oracle_evidence",
        "oracle_gap",
        "detector_score",
        "judge_score",
        "random_rank",
        "prevalence_random_rank",
        "fix_pr",
        "fix_pr_number",
    }
)


def tokenize(text: str) -> list[str]:
    """Apply the frozen ASCII lexical tokenizer, including boundary tokens."""

    tokens: list[str] = []
    for match in TOKEN_RE.finditer(text):
        raw = match.group(0)
        folded = raw.lower()
        tokens.append(folded)
        for segment in PATH_SPLIT_RE.split(raw):
            if not segment:
                continue
            segment_folded = segment.lower()
            if segment_folded != folded:
                tokens.append(segment_folded)
            for part in CAMEL_RE.findall(segment):
                part_folded = part.lower()
                if part_folded and part_folded != segment_folded:
                    tokens.append(part_folded)
    return tokens


def query_counter(
    title: str, body: str, linked_texts: Iterable[str] = ()
) -> Counter[str]:
    counter: Counter[str] = Counter()
    counter.update(tokenize(title) * 3)
    counter.update(tokenize(body))
    for text in linked_texts:
        counter.update(tokenize(text))
    return counter


def classify_path(path: str) -> str:
    """Classify one POSIX path using the frozen category priority."""

    pure = PurePosixPath(path)
    parts = [part.lower() for part in pure.parts]
    basename = pure.name.lower()
    stem = pure.stem.lower()
    suffix = pure.suffix.lower()

    if (
        any(part in {"test", "tests", "testing", "testdata"} for part in parts[:-1])
        or basename.startswith("test_")
        or stem.endswith("_test")
        or stem.endswith("_tests")
    ):
        return "visible_tests"

    if (
        any(
            part
            in {
                "doc",
                "docs",
                "documentation",
                "example",
                "examples",
                "tutorial",
                "tutorials",
            }
            for part in parts[:-1]
        )
        or basename.startswith(DOC_BASENAME_PREFIXES)
        or suffix in DOC_SUFFIXES
    ):
        return "docs"

    if (
        basename in CONFIG_BASENAMES
        or suffix in CONFIG_SUFFIXES
        or any(part in {".github", "ci", "config", "configs"} for part in parts[:-1])
    ):
        return "configs"

    if suffix in SOURCE_SUFFIXES or not suffix:
        return "retrieved_code"
    return "retrieved_code"


def parameter_contract() -> dict[str, Any]:
    return {
        "algorithm_id": RETRIEVAL_ALGORITHM_ID,
        "bm25": {"b": BM25_B, "k1": BM25_K1},
        "category_quotas": CATEGORY_QUOTAS,
        "config_basenames": sorted(CONFIG_BASENAMES),
        "config_suffixes": sorted(CONFIG_SUFFIXES),
        "doc_basename_prefixes": list(DOC_BASENAME_PREFIXES),
        "doc_suffixes": sorted(DOC_SUFFIXES),
        "source_suffixes": sorted(SOURCE_SUFFIXES),
        "max_blob_bytes": MAX_BLOB_BYTES,
        "max_excerpt_bytes": MAX_EXCERPT_BYTES,
        "packet_repository_budget_bytes": PACKET_REPOSITORY_BUDGET_BYTES,
        "token_pattern": TOKEN_RE.pattern,
        "path_token_weight": 3,
        "title_token_weight": 3,
        "stop_words": [],
    }


def parameter_sha256() -> str:
    return sha256_json(parameter_contract())


def build_reviewer_view(packet: dict[str, Any]) -> dict[str, Any]:
    """Return the exact allowlisted object exported to independent reviewers."""

    evidence = packet["available_evidence"]
    reviewer_evidence = {
        "issue_title": evidence["issue_title"],
        "issue_body": evidence["issue_body"],
    }
    for category in REVIEWER_EVIDENCE_CATEGORIES:
        reviewer_evidence[category] = [
            _reviewer_item(item) for item in evidence[category]
        ]

    return {
        "schema_version": "reviewer-view-v0.2",
        "packet_policy_id": packet["packet_policy_id"],
        "packet_id": packet["packet_id"],
        "packet_revision": packet["packet_revision"],
        "packet_status": packet["packet_status"],
        "task_id": packet["task_id"],
        "repo": packet["repo"],
        "base_commit": packet["base_commit"],
        "available_evidence": reviewer_evidence,
        "category_status": packet["category_status"],
    }


def _reviewer_item(item: dict[str, Any]) -> dict[str, Any]:
    return {key: item[key] for key in REVIEWER_ITEM_FIELDS if key in item}


def evidence_boundary_digest_contract() -> dict[str, Any]:
    """Return the versioned allowlist for cross-run evidence verification."""

    return {
        "digest_policy_id": EVIDENCE_BOUNDARY_DIGEST_ID,
        "canonical_json": "utf8-sorted-keys-compact-trailing-newline-v1",
        "top_level_fields": [
            "digest_policy_id",
            "packet_policy_id",
            "packet_id",
            "packet_revision",
            "packet_status",
            "task_id",
            "dataset",
            "repo",
            "base_commit",
        ],
        "component_boundary_fields": {
            key: list(fields)
            for key, fields in EVIDENCE_BOUNDARY_COMPONENT_FIELDS.items()
        },
        "repository_snapshot_fields": list(EVIDENCE_BOUNDARY_REPOSITORY_FIELDS),
        "retrieval_fields": list(EVIDENCE_BOUNDARY_RETRIEVAL_FIELDS),
        "evidence_scalar_fields": ["issue_title", "issue_body"],
        "evidence_categories": list(REVIEWER_EVIDENCE_CATEGORIES),
        "evidence_item_fields": list(REVIEWER_ITEM_FIELDS),
        "category_status_fields": list(EVIDENCE_BOUNDARY_STATUS_FIELDS),
    }


def build_evidence_boundary_projection(packet: dict[str, Any]) -> dict[str, Any]:
    """Project one packet onto evidence-semantic, cross-run stable fields."""

    evidence = packet["available_evidence"]
    projected_evidence = {
        "issue_title": evidence["issue_title"],
        "issue_body": evidence["issue_body"],
    }
    for category in REVIEWER_EVIDENCE_CATEGORIES:
        projected_evidence[category] = [
            _reviewer_item(item) for item in evidence[category]
        ]

    projected_boundaries = {}
    for component, fields in EVIDENCE_BOUNDARY_COMPONENT_FIELDS.items():
        source = packet["component_boundaries"][component]
        projected_boundaries[component] = {
            field: source[field] for field in fields if field in source
        }

    projected_status = {}
    for category, source in packet["category_status"].items():
        projected_status[category] = {
            field: source[field]
            for field in EVIDENCE_BOUNDARY_STATUS_FIELDS
            if field in source
        }

    return {
        "digest_policy_id": EVIDENCE_BOUNDARY_DIGEST_ID,
        "packet_policy_id": packet["packet_policy_id"],
        "packet_id": packet["packet_id"],
        "packet_revision": packet["packet_revision"],
        "packet_status": packet["packet_status"],
        "task_id": packet["task_id"],
        "dataset": packet["dataset"],
        "repo": packet["repo"],
        "base_commit": packet["base_commit"],
        "component_boundaries": projected_boundaries,
        "repository_snapshot": {
            field: packet["repository_snapshot"][field]
            for field in EVIDENCE_BOUNDARY_REPOSITORY_FIELDS
            if field in packet["repository_snapshot"]
        },
        "retrieval": {
            field: packet["retrieval"][field]
            for field in EVIDENCE_BOUNDARY_RETRIEVAL_FIELDS
            if field in packet["retrieval"]
        },
        "available_evidence": projected_evidence,
        "category_status": projected_status,
    }


def compute_evidence_boundary_hash(packet: dict[str, Any]) -> str:
    return sha256_json(build_evidence_boundary_projection(packet))


def compute_available_evidence_hash(packet: dict[str, Any]) -> str:
    return sha256_json(
        {
            "available_evidence": packet["available_evidence"],
            "category_status": packet["category_status"],
        }
    )


def compute_packet_hash(packet: dict[str, Any]) -> str:
    value = {key: item for key, item in packet.items() if key != "packet_hash"}
    return sha256_json(value)


def find_forbidden_reviewer_keys(value: Any, prefix: str = "") -> list[str]:
    findings: list[str] = []
    if isinstance(value, dict):
        for key, item in value.items():
            normalized = key.lower()
            path = f"{prefix}.{key}" if prefix else key
            if normalized in FORBIDDEN_REVIEWER_KEYS:
                findings.append(path)
            findings.extend(find_forbidden_reviewer_keys(item, path))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            findings.extend(find_forbidden_reviewer_keys(item, f"{prefix}[{index}]"))
    return findings
