"""Lightweight schema checks for NotPatch JSON/JSONL artifacts."""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import Any

from notpatch.canonical import sha256_json
from notpatch.evidence.contracts import (
    PACKET_POLICY_IDS,
    RETRIEVAL_ALGORITHM_ID,
    build_reviewer_view,
    compute_available_evidence_hash,
    compute_packet_hash,
)


class ValidationError(ValueError):
    """Raised when a NotPatch artifact violates the current schema."""


CUTOFF_RULES = {
    "issue_created",
    "first_maintainer_response",
    "pre_fix_pr_opened",
    "benchmark_defined",
}

PRIMARY_LABELS = {"P0", "P1", "P2", "P3"}
BLOCKERS = {"U1", "U2", "U3", "U4", "U5", "U6", "U7"}
DATA_QUALITY = {"Q0", "Q1", "Q2"}
DATA_QUALITY_BLOCKERS = {"D1", "none", None}
ANNOTATION_PASSES = {"available_only", "oracle_gap"}
DIFFICULTY = {"low", "medium", "high"}
CLARIFICATION_TARGETS = {
    "reproduction",
    "expected_behavior",
    "environment",
    "convention",
    "tradeoff",
    "dependency",
    "benchmark_artifact",
    None,
}
ORACLE_GAPS = {
    "no_gap",
    "missing_info",
    "hidden_constraint",
    "test_mismatch",
    "maintainer_context",
    "external_dependency",
    None,
}
PREDICTED_DIRECTION_MATCH = {
    "match",
    "partial_match",
    "mismatch",
    "not_assessable",
    None,
}
YES_NO_UNCLEAR = {"yes", "no", "unclear", None}
YES_PARTIAL_NO_UNCLEAR_NA = {"yes", "partial", "no", "unclear", "not_applicable", None}
YES_NO_UNCLEAR_NA = {"yes", "no", "unclear", "not_applicable", None}
BEHAVIOR_TARGET_SPACE_SIZE = {"1", "2-3", "many", "unclear", None}
ADJUDICATION_STATUS = {"raw", "adjudicated", "unresolved"}
RETRIEVAL_SUFFICIENCY = {"sufficient", "insufficient", "unclear"}
TRACE_FINAL_STATUS = {
    "resolved",
    "unresolved",
    "compile_error",
    "test_error",
    "no_patch",
}
HIDDEN_TEST_STATUS = {"pass", "fail", "error", "not_run", "not_applicable"}
ORACLE_INTENT_STATUS = {
    "intent_match",
    "intent_mismatch",
    "no_known_gap",
    "unresolved",
    "not_applicable",
}
POLICY_UTILITY_CLASSES = {
    "correct",
    "wrong",
    "abstain",
    "failed_attempt",
    "benchmark_invalid_sensitivity",
}
LLM_JUDGE_MESSAGE_ROLES = {"system", "user", "assistant"}
LLM_JUDGE_CACHE_STATUS = {"api", "batch_api", "manual_import", "fixture", "replay"}
SOURCE_STRATA = {
    "risk_enriched",
    "prevalence_random",
    "decidable_contrast",
    "verified_control",
    "multiswebench_qualitative",
    "github_fixed_with_pr",
    "github_info_needed",
    "github_long_open",
    "github_invalid_or_wontfix",
    "data_quality_probe",
}
LICENSE_STATUS = {"public_ok", "needs_review", "exclude", None}
EXCLUSION_REASONS = {
    "private_artifact",
    "license_conflict",
    "missing_snapshot",
    "missing_issue_text",
    "unclear_cutoff",
    "language_coverage_gap",
    None,
}
PACKET_STATUSES = {"ready", "ready_with_unavailable", "failed"}
CATEGORY_STATUSES = {"materialized", "empty", "unavailable", "failed"}
CUTOFF_VERIFICATION_STATUSES = {"verified", "unverified", "not_applicable"}
CORPUS_STATUSES = {
    "text",
    "binary",
    "decode_failed",
    "oversize",
    "non_regular",
    "read_failed",
}
EVIDENCE_CATEGORIES = {"retrieved_code", "visible_tests", "docs", "configs"}


def validate_record(record: dict[str, Any], artifact_type: str) -> None:
    """Validate one record for the requested artifact type."""

    if artifact_type == "evidence_bundle":
        if record.get("schema_version") == "evidence-packet-v0.2":
            validate_repository_evidence_packet(record)
        else:
            validate_evidence_bundle(record)
    elif artifact_type == "repository_evidence_packet":
        validate_repository_evidence_packet(record)
    elif artifact_type == "repository_inventory":
        validate_repository_inventory_record(record)
    elif artifact_type == "reviewer_view":
        validate_reviewer_view(record)
    elif artifact_type == "annotation":
        validate_annotation_record(record)
    elif artifact_type == "feature_table":
        validate_feature_record(record)
    elif artifact_type == "trace":
        validate_trace_record(record)
    elif artifact_type == "policy_outcome":
        validate_policy_outcome_record(record)
    elif artifact_type == "llm_judge_request":
        validate_llm_judge_request(record)
    elif artifact_type == "llm_judge_output":
        validate_llm_judge_output(record)
    elif artifact_type == "source_manifest":
        validate_source_manifest(record)
    else:
        raise ValidationError(f"unknown artifact_type: {artifact_type}")


def validate_source_manifest(record: dict[str, Any]) -> None:
    _require(record, "schema_version", str)
    tasks = _require(record, "tasks", list)
    seen: set[str] = set()
    for index, task in enumerate(tasks):
        if not isinstance(task, dict):
            raise ValidationError(f"tasks[{index}] must be object")
        task_id = _require(task, "task_id", str, f"tasks[{index}]")
        if task_id in seen:
            raise ValidationError(f"duplicate task_id in source manifest: {task_id}")
        seen.add(task_id)

        _require(task, "dataset", str, f"tasks[{index}]")
        _require(task, "repo", str, f"tasks[{index}]")
        _require(task, "source_ref", str, f"tasks[{index}]")
        _require_one_of(task, "stratum", SOURCE_STRATA, f"tasks[{index}]")

        if "candidate_cutoff_rule" in task:
            _require_one_of(
                task,
                "candidate_cutoff_rule",
                CUTOFF_RULES,
                f"tasks[{index}]",
            )
        if "candidate_cutoff_timestamp" in task and task["candidate_cutoff_timestamp"]:
            _parse_time(
                task["candidate_cutoff_timestamp"],
                f"tasks[{index}].candidate_cutoff_timestamp",
            )
        if "license_status" in task:
            _require_one_of(task, "license_status", LICENSE_STATUS, f"tasks[{index}]")
        if "exclusion_reason" in task:
            _require_one_of(
                task,
                "exclusion_reason",
                EXCLUSION_REASONS,
                f"tasks[{index}]",
            )

        if (
            task.get("license_status") == "exclude"
            and task.get("exclusion_reason") is None
        ):
            raise ValidationError(
                f"tasks[{index}].exclusion_reason is required when license_status=exclude"
            )


def validate_evidence_bundle(record: dict[str, Any]) -> None:
    _require(record, "task_id", str)
    _require(record, "dataset", str)
    _require(record, "repo", str)
    _require(record, "base_commit", str)
    _require(record, "repo_license", str)
    _require(record, "data_source_license", str)
    issue_created_at = _require(record, "issue_created_at", str)
    cutoff = _require(record, "evidence_cutoff_timestamp", str)
    _require_one_of(record, "evidence_cutoff_rule", CUTOFF_RULES)
    _require(record, "is_primary_cutoff", bool)
    _require(record, "cutoff_rationale", str)
    _require(record, "available_evidence_hash", str)
    _require_number(record, "sampling_weight")

    _parse_time(issue_created_at, "issue_created_at")
    cutoff_time = _parse_time(cutoff, "evidence_cutoff_timestamp")

    available = _require(record, "available_evidence", dict)
    for key in [
        "issue_title",
        "issue_body",
        "public_comments_until_cutoff",
        "visible_tests",
        "docs",
        "configs",
        "linked_artifacts",
    ]:
        if key not in available:
            raise ValidationError(f"available_evidence.{key} is required")

    for key in ["issue_title", "issue_body"]:
        if not isinstance(available[key], str):
            raise ValidationError(f"available_evidence.{key} must be str")

    for key in [
        "public_comments_until_cutoff",
        "visible_tests",
        "docs",
        "configs",
        "linked_artifacts",
    ]:
        if not isinstance(available[key], list):
            raise ValidationError(f"available_evidence.{key} must be list")
        for index, item in enumerate(available[key]):
            _validate_optional_cutoff_time(
                item,
                cutoff_time,
                f"available_evidence.{key}[{index}]",
            )

    excluded = record.get("excluded_posthoc_evidence", [])
    if not isinstance(excluded, list):
        raise ValidationError("excluded_posthoc_evidence must be list")
    for index, item in enumerate(excluded):
        if not isinstance(item, dict):
            raise ValidationError(f"excluded_posthoc_evidence[{index}] must be object")
        _require(item, "kind", str, f"excluded_posthoc_evidence[{index}]")
        _require(item, "reason", str, f"excluded_posthoc_evidence[{index}]")


def validate_repository_evidence_packet(record: dict[str, Any]) -> None:
    if _require(record, "schema_version", str) != "evidence-packet-v0.2":
        raise ValidationError("schema_version must be evidence-packet-v0.2")
    if _require(record, "packet_policy_id", str) not in PACKET_POLICY_IDS:
        raise ValidationError(f"packet_policy_id must be one of {PACKET_POLICY_IDS}")
    _require(record, "packet_id", str)
    revision = _require_number(record, "packet_revision")
    if revision < 1 or int(revision) != revision:
        raise ValidationError("packet_revision must be a positive integer")
    _require_one_of(record, "packet_status", PACKET_STATUSES)
    _require(record, "task_id", str)
    _require(record, "dataset", str)
    _require(record, "repo", str)
    base_commit = _require(record, "base_commit", str)
    _require_sha(base_commit, "base_commit", lengths={40, 64})

    sampling = _require(record, "sampling", dict)
    _require(sampling, "frame_id", str, "sampling")
    random_rank = _require_number(sampling, "random_rank", "sampling")
    if random_rank < 1 or int(random_rank) != random_rank:
        raise ValidationError("sampling.random_rank must be a positive integer")
    _require_number(sampling, "sampling_weight", "sampling")
    _require(sampling, "source_manifest_ref", str, "sampling")
    _require_sha(
        _require(sampling, "source_manifest_sha256", str, "sampling"),
        "sampling.source_manifest_sha256",
    )

    boundaries = _require(record, "component_boundaries", dict)
    _validate_component_boundaries(boundaries, base_commit)
    repository = _require(record, "repository_snapshot", dict)
    _require(repository, "remote", str, "repository_snapshot")
    if (
        _require(repository, "commit_object_verified", bool, "repository_snapshot")
        is not True
    ):
        raise ValidationError("repository_snapshot.commit_object_verified must be true")
    _require_sha(
        _require(repository, "tree_sha", str, "repository_snapshot"),
        "repository_snapshot.tree_sha",
        lengths={40, 64},
    )
    _require(repository, "inventory_ref", str, "repository_snapshot")
    inventory_sha = _require(repository, "inventory_sha256", str, "repository_snapshot")
    _require_sha(inventory_sha, "repository_snapshot.inventory_sha256")
    for key in ("regular_blob_count", "text_corpus_count"):
        value = _require_number(repository, key, "repository_snapshot")
        if value < 0 or int(value) != value:
            raise ValidationError(
                f"repository_snapshot.{key} must be nonnegative integer"
            )

    retrieval = _require(record, "retrieval", dict)
    if _require(retrieval, "algorithm_id", str, "retrieval") != RETRIEVAL_ALGORITHM_ID:
        raise ValidationError(
            f"retrieval.algorithm_id must be {RETRIEVAL_ALGORITHM_ID}"
        )
    for key in ("parameter_sha256", "query_source_sha256"):
        _require_sha(_require(retrieval, key, str, "retrieval"), f"retrieval.{key}")
    if retrieval.get("reviewer_query") is not None:
        raise ValidationError("retrieval.reviewer_query must be null")

    available = _require(record, "available_evidence", dict)
    for key in ("issue_title", "issue_body"):
        _require(available, key, str, "available_evidence")
    array_categories = (
        "public_comments_until_cutoff",
        "retrieved_code",
        "visible_tests",
        "docs",
        "configs",
        "linked_artifacts",
    )
    for category in array_categories:
        items = _require(available, category, list, "available_evidence")
        for index, item in enumerate(items):
            _validate_evidence_item(
                item,
                f"available_evidence.{category}[{index}]",
                repository_item=category in EVIDENCE_CATEGORIES,
            )

    statuses = _require(record, "category_status", dict)
    required_statuses = {"issue_packet", "repository_inventory", *array_categories}
    if set(statuses) != required_statuses:
        raise ValidationError(
            f"category_status keys must be {sorted(required_statuses)}"
        )
    for category, status in statuses.items():
        _validate_category_status(status, f"category_status.{category}")

    for key in ("excluded_evidence", "failure_audit"):
        values = _require(record, key, list)
        if not all(isinstance(value, dict) for value in values):
            raise ValidationError(f"{key} must contain objects")
    provenance = _require(record, "materialization_provenance", dict)
    _require(provenance, "run_id", str, "materialization_provenance")
    _require(provenance, "collector_git_sha", str, "materialization_provenance")

    for key in (
        "available_evidence_hash",
        "repository_inventory_hash",
        "reviewer_view_hash",
        "packet_hash",
    ):
        _require_sha(_require(record, key, str), key)
    if record["repository_inventory_hash"] != inventory_sha:
        raise ValidationError("repository inventory hash fields disagree")
    if record["available_evidence_hash"] != compute_available_evidence_hash(record):
        raise ValidationError("available_evidence_hash does not match packet content")
    if record["reviewer_view_hash"] != sha256_json(build_reviewer_view(record)):
        raise ValidationError("reviewer_view_hash does not match reviewer view")
    if record["packet_hash"] != compute_packet_hash(record):
        raise ValidationError("packet_hash does not match packet content")


def validate_repository_inventory_record(record: dict[str, Any]) -> None:
    _require(record, "path", str)
    _require(record, "path_encoding", str)
    _require(record, "git_mode", str)
    _require(record, "git_object_type", str)
    _require_sha(
        _require(record, "git_blob_sha", str),
        "git_blob_sha",
        lengths={40, 64},
    )
    size = record.get("size_bytes")
    if size is not None and (
        not isinstance(size, int) or isinstance(size, bool) or size < 0
    ):
        raise ValidationError("size_bytes must be nonnegative integer or null")
    _require(record, "media_class", str)
    _require_one_of(record, "evidence_category", EVIDENCE_CATEGORIES)
    _require_one_of(record, "corpus_status", CORPUS_STATUSES)


def validate_reviewer_view(record: dict[str, Any]) -> None:
    if _require(record, "schema_version", str) != "reviewer-view-v0.2":
        raise ValidationError("reviewer view schema_version must be reviewer-view-v0.2")
    if _require(record, "packet_policy_id", str) not in PACKET_POLICY_IDS:
        raise ValidationError(
            f"reviewer view packet_policy_id must be one of {PACKET_POLICY_IDS}"
        )
    for key in ("packet_id", "task_id", "repo", "base_commit"):
        _require(record, key, str)
    _require_number(record, "packet_revision")
    _require_one_of(record, "packet_status", PACKET_STATUSES)
    _require(record, "available_evidence", dict)
    _require(record, "category_status", dict)


def validate_annotation_record(record: dict[str, Any]) -> None:
    _require(record, "task_id", str)
    _require(record, "annotator_id", str)
    annotation_pass = _require_one_of(record, "pass", ANNOTATION_PASSES)
    primary_label = _require_one_of(record, "primary_label", PRIMARY_LABELS)
    primary_blocker = record.get("primary_blocker")
    secondary_blockers = record.get("secondary_blockers", [])
    data_quality_blocker = record.get("data_quality_blocker")

    if primary_label in {"P1", "P2", "P3"}:
        if primary_blocker not in BLOCKERS:
            raise ValidationError("P1/P2/P3 records require primary_blocker in U1-U7")
    elif primary_blocker is not None:
        raise ValidationError("P0 records should not set primary_blocker")

    if not isinstance(secondary_blockers, list):
        raise ValidationError("secondary_blockers must be list")
    unknown_blockers = set(secondary_blockers) - BLOCKERS
    if unknown_blockers:
        raise ValidationError(f"unknown secondary_blockers: {sorted(unknown_blockers)}")

    if data_quality_blocker not in DATA_QUALITY_BLOCKERS:
        raise ValidationError("data_quality_blocker must be D1, none, or null")
    _require_one_of(record, "data_quality", DATA_QUALITY)
    _require_one_of(record, "task_difficulty", DIFFICULTY)
    _require_one_of(record, "clarification_target", CLARIFICATION_TARGETS)
    rationale = _require(record, "rationale", str)
    if not rationale.strip():
        raise ValidationError("rationale must be non-empty")
    if "packet_policy_id" in record:
        _validate_repository_annotation_linkage(record, annotation_pass)
    else:
        _require_one_of(record, "evidence_cutoff_rule", CUTOFF_RULES)
        _parse_time(
            _require(record, "evidence_cutoff_timestamp", str),
            "evidence_cutoff_timestamp",
        )
    _require_one_of(record, "adjudication_status", ADJUDICATION_STATUS)

    if annotation_pass == "available_only":
        _validate_available_only_record(record, primary_label)
    else:
        _validate_oracle_gap_record(record, primary_label)


def _validate_repository_annotation_linkage(
    record: dict[str, Any], annotation_pass: str
) -> None:
    for key in [
        "annotation_batch_id",
        "packet_policy_id",
        "packet_id",
        "reviewer_view_hash",
        "registry_snapshot_sha256",
        "component_boundary_ref",
    ]:
        value = _require(record, key, str)
        if not value.strip():
            raise ValidationError(f"{key} must be non-empty")
    revision = _require_number(record, "packet_revision")
    if revision < 1 or int(revision) != revision:
        raise ValidationError("packet_revision must be a positive integer")
    _require_one_of(record, "retrieval_sufficiency", RETRIEVAL_SUFFICIENCY)
    for key in [
        "missing_repository_evidence",
        "available_evidence_used",
        "available_evidence_used_with_provenance",
    ]:
        values = _require(record, key, list)
        if not all(isinstance(item, str) and item.strip() for item in values):
            raise ValidationError(f"{key} must contain non-empty strings")
    if annotation_pass == "available_only":
        if record.get("data_quality") not in {"Q0", "Q2"}:
            raise ValidationError(
                "repository available_only records require data_quality Q0 or Q2"
            )
        if record.get("data_quality_blocker") is not None:
            raise ValidationError(
                "repository available_only records must keep data_quality_blocker null"
            )


def validate_feature_record(record: dict[str, Any]) -> None:
    _require(record, "task_id", str)
    _require(record, "feature_schema_version", str)
    _require(record, "extractor_git_sha", str)
    _require(record, "features", dict)
    provenance = _require(record, "feature_provenance", list)

    feature_names = set(record["features"].keys())
    provenance_names: set[str] = set()
    for index, item in enumerate(provenance):
        if not isinstance(item, dict):
            raise ValidationError(f"feature_provenance[{index}] must be object")
        feature = _require(item, "feature", str, f"feature_provenance[{index}]")
        provenance_names.add(feature)
        _require(item, "evidence_item", str, f"feature_provenance[{index}]")
        _require(item, "evidence_timestamp", str, f"feature_provenance[{index}]")
        _require(item, "extractor", str, f"feature_provenance[{index}]")
        _require(item, "extractor_git_sha", str, f"feature_provenance[{index}]")

    missing = feature_names - provenance_names
    if missing:
        raise ValidationError(f"features missing provenance: {sorted(missing)}")


def validate_trace_record(record: dict[str, Any]) -> None:
    _require(record, "task_id", str)
    _require(record, "agent", str)
    _require(record, "run_id", str)
    _require(record, "dataset", str)
    _require(record, "available_evidence_hash", str)
    events = _require(record, "events", list)
    final_artifact = _require(record, "final_artifact", dict)
    cost = _require(record, "cost", dict)

    for index, event in enumerate(events):
        if not isinstance(event, dict):
            raise ValidationError(f"events[{index}] must be object")
        _require(event, "phase", str, f"events[{index}]")
        for key in ["tool_calls", "retrieved_files", "tests_run", "test_results"]:
            if key not in event or not isinstance(event[key], list):
                raise ValidationError(f"events[{index}].{key} must be list")
        if "risk_signals" not in event or not isinstance(event["risk_signals"], dict):
            raise ValidationError(f"events[{index}].risk_signals must be object")

    _require(final_artifact, "patch_diff", str, "final_artifact")
    if "edited_files" not in final_artifact or not isinstance(
        final_artifact["edited_files"], list
    ):
        raise ValidationError("final_artifact.edited_files must be list")
    _require_one_of(
        final_artifact, "final_status", TRACE_FINAL_STATUS, "final_artifact"
    )

    for key in ["tokens", "wall_time_sec", "tool_runtime_sec"]:
        _require_number(cost, key, "cost")


def validate_policy_outcome_record(record: dict[str, Any]) -> None:
    _require(record, "task_id", str)
    _require(record, "dataset", str)
    _require(record, "run_id", str)
    _require_one_of(record, "primary_label", PRIMARY_LABELS)
    data_quality = _require_one_of(record, "data_quality", DATA_QUALITY)
    _require_one_of(record, "hidden_test_status", HIDDEN_TEST_STATUS)
    _require_one_of(record, "oracle_intent_status", ORACLE_INTENT_STATUS)
    _require(record, "patch_reviewable", bool)
    utility_class = _require_one_of(
        record,
        "utility_class",
        POLICY_UTILITY_CLASSES,
    )
    _require_nonnegative_number(record, "review_minutes")
    _require_nonnegative_number(record, "triage_minutes")
    _require_nonnegative_number(record, "compute_minutes")
    preflight_score = _require_nonnegative_number(record, "preflight_score")
    if preflight_score > 1:
        raise ValidationError("preflight_score must be between 0 and 1")

    if "agent_confidence" not in record:
        raise ValidationError("agent_confidence is required")
    confidence = record["agent_confidence"]
    if confidence is not None:
        if not isinstance(confidence, (int, float)) or isinstance(confidence, bool):
            raise ValidationError("agent_confidence must be number or null")
        if confidence < 0 or confidence > 1:
            raise ValidationError("agent_confidence must be between 0 and 1")

    if data_quality == "Q1" and utility_class != "benchmark_invalid_sensitivity":
        raise ValidationError("Q1 records must use benchmark_invalid_sensitivity")
    if utility_class == "benchmark_invalid_sensitivity" and data_quality != "Q1":
        raise ValidationError("benchmark_invalid_sensitivity requires data_quality=Q1")
    if not record["patch_reviewable"] and record["review_minutes"] != 0:
        raise ValidationError("non-reviewable records must set review_minutes=0")


def validate_llm_judge_request(record: dict[str, Any]) -> None:
    _require(record, "schema_version", str)
    _require(record, "request_id", str)
    _require(record, "task_id", str)
    _require(record, "dataset", str)
    _require(record, "repo", str)
    _require(record, "model_id", str)
    _require(record, "prompt_version", str)
    _require(record, "available_evidence_hash", str)
    _require_one_of(record, "evidence_cutoff_rule", CUTOFF_RULES)
    _parse_time(
        _require(record, "evidence_cutoff_timestamp", str),
        "evidence_cutoff_timestamp",
    )
    _validate_llm_sampling(_require(record, "sampling", dict))
    _validate_llm_messages(_require(record, "messages", list))
    _require(record, "response_format", dict)
    _require(record, "input_evidence_summary", dict)

    excluded_fields = _require(record, "excluded_fields", list)
    if not all(isinstance(item, str) and item for item in excluded_fields):
        raise ValidationError("excluded_fields must contain non-empty strings")
    if "excluded_posthoc_evidence" not in excluded_fields:
        raise ValidationError("llm judge requests must exclude post-hoc evidence")


def validate_llm_judge_output(record: dict[str, Any]) -> None:
    _require(record, "schema_version", str)
    _require(record, "request_id", str)
    _require(record, "task_id", str)
    _require(record, "dataset", str)
    _require(record, "repo", str)
    _require(record, "model_id", str)
    _require(record, "model_version", str)
    _require(record, "prompt_version", str)
    _require(record, "available_evidence_hash", str)
    _parse_time(_require(record, "created_at", str), "created_at")
    _validate_llm_sampling(_require(record, "sampling", dict))
    _require_one_of(record, "cache_status", LLM_JUDGE_CACHE_STATUS)
    _validate_llm_usage(_require(record, "usage", dict))
    _validate_llm_judgment(_require(record, "judgment", dict))


def _validate_available_only_record(record: dict[str, Any], primary_label: str) -> None:
    oracle_fields = [
        "oracle_gap",
        "predicted_direction_match",
        "oracle_direction_summary",
        "oracle_direction_in_candidate_set",
        "oracle_revealed_missing_evidence",
        "available_evidence_unique_in_hindsight",
        "oracle_alternative_fix_exists",
        "behavior_target_space_size",
        "non_decidability_explanation",
    ]
    filled = [field for field in oracle_fields if record.get(field) is not None]
    if filled:
        raise ValidationError(f"available_only record contains oracle fields: {filled}")

    _validate_direction_requirements(record, primary_label)


def _validate_oracle_gap_record(record: dict[str, Any], primary_label: str) -> None:
    _require_one_of(record, "oracle_gap", ORACLE_GAPS)
    _require_one_of(record, "predicted_direction_match", PREDICTED_DIRECTION_MATCH)
    _require_one_of(
        record,
        "oracle_direction_in_candidate_set",
        YES_NO_UNCLEAR_NA,
    )
    _require_one_of(
        record,
        "oracle_revealed_missing_evidence",
        YES_PARTIAL_NO_UNCLEAR_NA,
    )
    _require_one_of(
        record,
        "available_evidence_unique_in_hindsight",
        YES_NO_UNCLEAR_NA,
    )
    _require_one_of(record, "oracle_alternative_fix_exists", YES_NO_UNCLEAR)
    _require_one_of(
        record,
        "behavior_target_space_size",
        BEHAVIOR_TARGET_SPACE_SIZE,
    )
    _validate_direction_requirements(record, primary_label)


def _validate_direction_requirements(
    record: dict[str, Any], primary_label: str
) -> None:
    template = record.get("predicted_direction_template")
    candidates = record.get("candidate_directions", [])
    missing = record.get("missing_evidence_needed", [])

    if primary_label in {"P0", "P1"}:
        if (
            not isinstance(record.get("predicted_direction"), str)
            or not record["predicted_direction"].strip()
        ):
            raise ValidationError("P0/P1 records require predicted_direction")
        _validate_direction_template(template)
        if candidates:
            raise ValidationError("P0/P1 records should not set candidate_directions")
    else:
        if record.get("predicted_direction") is not None:
            raise ValidationError("P2/P3 records should not set predicted_direction")
        if not isinstance(candidates, list):
            raise ValidationError("candidate_directions must be list")
        if primary_label == "P2" and len(candidates) < 2:
            raise ValidationError(
                "P2 records require at least two candidate_directions"
            )
        if primary_label == "P3" and not candidates:
            raise ValidationError(
                "P3 records require at least one blocked candidate_direction"
            )
        if not all(isinstance(item, str) and item.strip() for item in candidates):
            raise ValidationError("candidate_directions must be non-empty strings")
        if not isinstance(missing, list) or not missing:
            raise ValidationError("P2/P3 records require missing_evidence_needed")


def _validate_direction_template(value: Any) -> None:
    if not isinstance(value, dict):
        raise ValidationError("predicted_direction_template must be object")
    for key in [
        "component_or_function",
        "input_condition_or_trigger",
        "observable_behavior_change",
    ]:
        if not isinstance(value.get(key), str) or not value[key].strip():
            raise ValidationError(f"predicted_direction_template.{key} is required")


def _validate_llm_sampling(sampling: dict[str, Any]) -> None:
    for key in ["temperature", "top_p"]:
        value = _require_number(sampling, key, "sampling")
        if value < 0 or value > 1:
            raise ValidationError(f"sampling.{key} must be between 0 and 1")
    n = _require_number(sampling, "n", "sampling")
    if n < 1 or int(n) != n:
        raise ValidationError("sampling.n must be a positive integer")
    seed = sampling.get("seed")
    if seed is not None and (not isinstance(seed, int) or isinstance(seed, bool)):
        raise ValidationError("sampling.seed must be integer or null")


def _validate_llm_messages(messages: list[Any]) -> None:
    if not messages:
        raise ValidationError("messages must be non-empty")
    for index, message in enumerate(messages):
        if not isinstance(message, dict):
            raise ValidationError(f"messages[{index}] must be object")
        _require_one_of(message, "role", LLM_JUDGE_MESSAGE_ROLES, f"messages[{index}]")
        content = _require(message, "content", str, f"messages[{index}]")
        if not content.strip():
            raise ValidationError(f"messages[{index}].content must be non-empty")


def _validate_llm_usage(usage: dict[str, Any]) -> None:
    for key in ["input_tokens", "output_tokens"]:
        value = _require_number(usage, key, "usage")
        if value < 0 or int(value) != value:
            raise ValidationError(f"usage.{key} must be a nonnegative integer")
    cost = usage.get("cost_usd")
    if cost is not None:
        if not isinstance(cost, (int, float)) or isinstance(cost, bool):
            raise ValidationError("usage.cost_usd must be number or null")
        if cost < 0:
            raise ValidationError("usage.cost_usd must be nonnegative")


def _validate_llm_judgment(judgment: dict[str, Any]) -> None:
    primary_label = _require_one_of(
        judgment, "primary_label", PRIMARY_LABELS, "judgment"
    )
    predicted = _require(judgment, "predicted_patch_decidable", bool, "judgment")
    if predicted != (primary_label in {"P0", "P1"}):
        raise ValidationError(
            "judgment.predicted_patch_decidable conflicts with primary_label"
        )

    probability = _require_number(judgment, "p_patch_decidable", "judgment")
    confidence = _require_number(judgment, "confidence", "judgment")
    if probability < 0 or probability > 1:
        raise ValidationError("judgment.p_patch_decidable must be between 0 and 1")
    if confidence < 0 or confidence > 1:
        raise ValidationError("judgment.confidence must be between 0 and 1")

    primary_blocker = judgment.get("primary_blocker")
    if primary_label in {"P1", "P2", "P3"}:
        if primary_blocker not in BLOCKERS:
            raise ValidationError("judgment P1/P2/P3 require primary_blocker in U1-U7")
    elif primary_blocker is not None:
        raise ValidationError("judgment P0 should not set primary_blocker")

    secondary_blockers = judgment.get("secondary_blockers", [])
    if not isinstance(secondary_blockers, list):
        raise ValidationError("judgment.secondary_blockers must be list")
    unknown = set(secondary_blockers) - BLOCKERS
    if unknown:
        raise ValidationError(f"unknown judgment.secondary_blockers: {sorted(unknown)}")

    _require_one_of(judgment, "clarification_target", CLARIFICATION_TARGETS, "judgment")
    _require(judgment, "rationale", str, "judgment")
    evidence_used = _require(judgment, "evidence_used", list, "judgment")
    if not all(isinstance(item, str) and item for item in evidence_used):
        raise ValidationError("judgment.evidence_used must contain non-empty strings")
    _validate_llm_direction_requirements(judgment, primary_label)


def _validate_llm_direction_requirements(
    judgment: dict[str, Any],
    primary_label: str,
) -> None:
    candidates = judgment.get("candidate_directions", [])
    missing = judgment.get("missing_evidence_needed", [])
    if not isinstance(candidates, list):
        raise ValidationError("judgment.candidate_directions must be list")
    if not isinstance(missing, list):
        raise ValidationError("judgment.missing_evidence_needed must be list")
    if not all(isinstance(item, str) and item.strip() for item in candidates):
        raise ValidationError("judgment.candidate_directions must contain strings")
    if not all(isinstance(item, str) and item.strip() for item in missing):
        raise ValidationError("judgment.missing_evidence_needed must contain strings")

    predicted_direction = judgment.get("predicted_direction")
    if primary_label in {"P0", "P1"}:
        if not isinstance(predicted_direction, str) or not predicted_direction.strip():
            raise ValidationError("judgment P0/P1 require predicted_direction")
    else:
        if predicted_direction is not None:
            raise ValidationError("judgment P2/P3 should not set predicted_direction")
        if primary_label == "P2" and len(candidates) < 2:
            raise ValidationError(
                "judgment P2 requires at least two candidate_directions"
            )
        if primary_label == "P3" and not candidates:
            raise ValidationError(
                "judgment P3 requires at least one candidate_direction"
            )
        if not missing:
            raise ValidationError("judgment P2/P3 require missing_evidence_needed")


def _validate_optional_cutoff_time(item: Any, cutoff: datetime, path: str) -> None:
    if not isinstance(item, dict):
        return
    timestamp = item.get("timestamp")
    if timestamp is None:
        return
    item_time = _parse_time(timestamp, f"{path}.timestamp")
    if item_time > cutoff:
        raise ValidationError(f"{path}.timestamp is after evidence_cutoff_timestamp")


def _validate_component_boundaries(
    boundaries: dict[str, Any], base_commit: str
) -> None:
    if set(boundaries) != {"issue_packet", "repository_snapshot", "public_artifacts"}:
        raise ValidationError(
            "component_boundaries must contain issue_packet, repository_snapshot, and public_artifacts"
        )
    issue = _require(boundaries, "issue_packet", dict, "component_boundaries")
    if (
        _require(issue, "rule", str, "component_boundaries.issue_packet")
        != "benchmark_defined"
    ):
        raise ValidationError(
            "component_boundaries.issue_packet.rule must be benchmark_defined"
        )
    for key in ("source_ref", "source_snapshot", "verification_status"):
        _require(issue, key, str, "component_boundaries.issue_packet")

    repository = _require(
        boundaries, "repository_snapshot", dict, "component_boundaries"
    )
    if (
        _require(repository, "rule", str, "component_boundaries.repository_snapshot")
        != "base_commit"
    ):
        raise ValidationError(
            "component_boundaries.repository_snapshot.rule must be base_commit"
        )
    if (
        _require(
            repository,
            "commit_sha",
            str,
            "component_boundaries.repository_snapshot",
        )
        != base_commit
    ):
        raise ValidationError("component repository commit differs from base_commit")
    if repository.get("verification_status") != "verified":
        raise ValidationError(
            "component repository verification_status must be verified"
        )

    public = _require(boundaries, "public_artifacts", dict, "component_boundaries")
    if (
        _require(public, "rule", str, "component_boundaries.public_artifacts")
        != "pre_fix_pr_opened"
    ):
        raise ValidationError(
            "component_boundaries.public_artifacts.rule must be pre_fix_pr_opened"
        )
    verification = _require_one_of(
        public,
        "cutoff_verification_status",
        CUTOFF_VERIFICATION_STATUSES,
        "component_boundaries.public_artifacts",
    )
    cutoff = public.get("cutoff_timestamp")
    if verification == "verified":
        if not isinstance(cutoff, str):
            raise ValidationError("verified public cutoff requires cutoff_timestamp")
        _parse_time(cutoff, "component_boundaries.public_artifacts.cutoff_timestamp")
        if public.get("cutoff_source_field") != "created_at":
            raise ValidationError(
                "verified public cutoff source field must be created_at"
            )
    elif cutoff is not None:
        raise ValidationError("unverified/not_applicable public cutoff must be null")
    verified_at = public.get("cutoff_verified_at")
    if verified_at is not None:
        if not isinstance(verified_at, str):
            raise ValidationError("cutoff_verified_at must be string or null")
        _parse_time(
            verified_at, "component_boundaries.public_artifacts.cutoff_verified_at"
        )
    payload_hash = public.get("cutoff_source_payload_sha256")
    if payload_hash is not None:
        if not isinstance(payload_hash, str):
            raise ValidationError("cutoff_source_payload_sha256 must be string or null")
        _require_sha(
            payload_hash,
            "component_boundaries.public_artifacts.cutoff_source_payload_sha256",
        )


def _validate_evidence_item(item: Any, path: str, *, repository_item: bool) -> None:
    if not isinstance(item, dict):
        raise ValidationError(f"{path} must be object")
    for key in ("evidence_id", "kind", "source_locator", "selection_reason", "content"):
        _require(item, key, str, path)
    _require_sha(_require(item, "content_sha256", str, path), f"{path}.content_sha256")
    size = _require_number(item, "size_bytes", path)
    if size < 0 or int(size) != size:
        raise ValidationError(f"{path}.size_bytes must be nonnegative integer")
    _require(item, "content_truncated", bool, path)
    ranges = _require(item, "included_line_ranges", list, path)
    for index, line_range in enumerate(ranges):
        if (
            not isinstance(line_range, list)
            or len(line_range) != 2
            or not all(isinstance(value, int) and value >= 1 for value in line_range)
            or line_range[0] > line_range[1]
        ):
            raise ValidationError(f"{path}.included_line_ranges[{index}] is invalid")
    content_hash = hashlib.sha256(item["content"].encode("utf-8")).hexdigest()
    if content_hash != item["content_sha256"]:
        raise ValidationError(f"{path}.content_sha256 does not match content")
    if repository_item:
        _require(item, "path", str, path)
        _require_sha(
            _require(item, "source_commit", str, path),
            f"{path}.source_commit",
            lengths={40, 64},
        )
        _require_sha(
            _require(item, "full_blob_sha", str, path),
            f"{path}.full_blob_sha",
            lengths={40, 64},
        )
        rank = _require_number(item, "retrieval_rank", path)
        if rank < 1 or int(rank) != rank:
            raise ValidationError(f"{path}.retrieval_rank must be positive integer")
        _require_number(item, "score", path)


def _validate_category_status(value: Any, path: str) -> None:
    if not isinstance(value, dict):
        raise ValidationError(f"{path} must be object")
    status = _require_one_of(value, "status", CATEGORY_STATUSES, path)
    _require(value, "reason", str, path)
    if status in {"unavailable", "failed"}:
        if "attempted_source" not in value:
            raise ValidationError(f"{path}.attempted_source is required")
        attempt_count = _require_number(value, "attempt_count", path)
        if attempt_count < 1 or int(attempt_count) != attempt_count:
            raise ValidationError(f"{path}.attempt_count must be positive integer")
        last_attempt_at = value.get("last_attempt_at")
        if last_attempt_at is not None:
            if not isinstance(last_attempt_at, str):
                raise ValidationError(f"{path}.last_attempt_at must be string or null")
            _parse_time(last_attempt_at, f"{path}.last_attempt_at")


def _require_sha(value: str, path: str, lengths: set[int] | None = None) -> None:
    allowed_lengths = lengths or {64}
    if len(value) not in allowed_lengths or any(
        character not in "0123456789abcdef" for character in value.lower()
    ):
        raise ValidationError(
            f"{path} must be lowercase hexadecimal with length in {sorted(allowed_lengths)}"
        )


def _require(
    record: dict[str, Any],
    key: str,
    expected_type: type,
    path: str | None = None,
) -> Any:
    if key not in record:
        prefix = f"{path}." if path else ""
        raise ValidationError(f"{prefix}{key} is required")
    value = record[key]
    if not isinstance(value, expected_type):
        prefix = f"{path}." if path else ""
        raise ValidationError(f"{prefix}{key} must be {expected_type.__name__}")
    return value


def _require_one_of(
    record: dict[str, Any],
    key: str,
    allowed: set[Any],
    path: str | None = None,
) -> Any:
    if key not in record:
        prefix = f"{path}." if path else ""
        raise ValidationError(f"{prefix}{key} is required")
    value = record[key]
    if value not in allowed:
        prefix = f"{path}." if path else ""
        raise ValidationError(f"{prefix}{key} has invalid value: {value!r}")
    return value


def _require_number(record: dict[str, Any], key: str, path: str | None = None) -> float:
    if key not in record:
        prefix = f"{path}." if path else ""
        raise ValidationError(f"{prefix}{key} is required")
    value = record[key]
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        prefix = f"{path}." if path else ""
        raise ValidationError(f"{prefix}{key} must be number")
    return float(value)


def _require_nonnegative_number(
    record: dict[str, Any], key: str, path: str | None = None
) -> float:
    value = _require_number(record, key, path)
    if value < 0:
        prefix = f"{path}." if path else ""
        raise ValidationError(f"{prefix}{key} must be nonnegative")
    return value


def _parse_time(value: str, path: str) -> datetime:
    normalized = value.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise ValidationError(f"{path} must be ISO-8601 timestamp") from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed
