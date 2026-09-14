#!/usr/bin/env python3
"""Strict V4 response parsing and deterministic parking-order decisions.

This module intentionally contains no image, model, detector, or reference-label
logic.  It accepts the JSON emitted for one local target batch and converts it to
an auditable semantic decision.  Protocol failures are never converted to
``negative``.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Iterable, Mapping, Sequence


ENUM_VALUES = ("yes", "no", "unclear")
TARGET_FIELDS = (
    "target_id",
    "vehicle_valid",
    "evidence_sufficient",
    "road_or_drive_aisle",
    "occupies_two_bays",
    "in_one_bay_or_designated_area",
    "minor_line_or_nose_tail_only",
    "normal_gate_queue",
    "evidence",
)
TOP_LEVEL_FIELDS = ("targets",)
POSITIVE_DECISIONS = ("positive_road", "positive_two_bays")
NEGATIVE_DECISIONS = ("negative", "negative_gate_queue")
SEMANTIC_DECISIONS = POSITIVE_DECISIONS + NEGATIVE_DECISIONS


@dataclass(frozen=True)
class ParseResult:
    """Result of strict parsing.

    A failed parse deliberately returns no usable targets.  This prevents a
    partially valid response from silently becoming a valid batch prediction.
    """

    ok: bool
    targets: tuple[dict[str, Any], ...]
    issues: tuple[dict[str, str], ...]
    raw_type: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "targets": [dict(target) for target in self.targets],
            "issues": [dict(issue) for issue in self.issues],
            "raw_type": self.raw_type,
        }


def _issue(code: str, path: str, detail: str) -> dict[str, str]:
    return {"code": code, "path": path, "detail": detail}


def _strict_json_object(raw_response: Any) -> tuple[Mapping[str, Any] | None, list[dict[str, str]], str]:
    raw_type = type(raw_response).__name__
    if isinstance(raw_response, bytes):
        try:
            raw_response = raw_response.decode("utf-8")
        except UnicodeDecodeError as exc:
            return None, [_issue("INVALID_JSON", "$", f"UTF-8 decode failed: {exc}")], raw_type
    if isinstance(raw_response, str):
        try:
            value = json.loads(raw_response)
        except json.JSONDecodeError as exc:
            return None, [_issue("INVALID_JSON", "$", str(exc))], raw_type
    elif isinstance(raw_response, Mapping):
        value = raw_response
    else:
        return None, [_issue("TOP_LEVEL_NOT_OBJECT", "$", "response must be a JSON object or JSON object string")], raw_type
    if not isinstance(value, Mapping):
        return None, [_issue("TOP_LEVEL_NOT_OBJECT", "$", "response must decode to a JSON object")], raw_type
    return value, [], raw_type


def parse_model_response(raw_response: Any, expected_target_ids: Sequence[str]) -> ParseResult:
    """Strictly parse one V4 batch response.

    Required contract:

    ``{"targets": [{TARGET_FIELDS...}, ...]}``

    The target list must contain every expected local target exactly once.  The
    parser rejects missing targets, duplicate IDs, extra IDs, unknown fields,
    missing fields, invalid enum values, and malformed JSON.
    """

    expected = list(expected_target_ids)
    issues: list[dict[str, str]] = []
    if any(not isinstance(target_id, str) or not target_id for target_id in expected):
        issues.append(_issue("INVALID_EXPECTED_TARGET_ID", "expected_target_ids", "IDs must be non-empty strings"))
    if len(set(expected)) != len(expected):
        issues.append(_issue("DUPLICATE_EXPECTED_TARGET_ID", "expected_target_ids", "expected IDs must be unique"))

    obj, json_issues, raw_type = _strict_json_object(raw_response)
    issues.extend(json_issues)
    if obj is None:
        return ParseResult(False, (), tuple(issues), raw_type)

    actual_top = set(obj.keys())
    expected_top = set(TOP_LEVEL_FIELDS)
    for field in sorted(expected_top - actual_top):
        issues.append(_issue("MISSING_FIELD", field, "required top-level field is missing"))
    for field in sorted(actual_top - expected_top):
        issues.append(_issue("UNKNOWN_FIELD", field, "unknown top-level field is not permitted"))

    target_list = obj.get("targets")
    if not isinstance(target_list, list):
        issues.append(_issue("INVALID_TYPE", "targets", "targets must be a JSON array"))
        return ParseResult(False, (), tuple(issues), raw_type)

    if len(target_list) != len(expected):
        code = "MISSING_TARGET" if len(target_list) < len(expected) else "UNEXPECTED_TARGET_COUNT"
        issues.append(_issue(code, "targets", f"expected {len(expected)} target objects, received {len(target_list)}"))

    seen: list[str] = []
    parsed_targets: list[dict[str, Any]] = []
    expected_set = set(expected)
    for index, target in enumerate(target_list):
        path = f"targets[{index}]"
        if not isinstance(target, Mapping):
            issues.append(_issue("INVALID_TYPE", path, "target must be a JSON object"))
            continue
        actual_fields = set(target.keys())
        for field in sorted(set(TARGET_FIELDS) - actual_fields):
            issues.append(_issue("MISSING_FIELD", f"{path}.{field}", "required target field is missing"))
        for field in sorted(actual_fields - set(TARGET_FIELDS)):
            issues.append(_issue("UNKNOWN_FIELD", f"{path}.{field}", "unknown target field is not permitted"))

        target_id = target.get("target_id")
        if not isinstance(target_id, str) or not target_id:
            issues.append(_issue("INVALID_ENUM", f"{path}.target_id", "target_id must be a non-empty string"))
        else:
            if target_id in seen:
                issues.append(_issue("DUPLICATE_TARGET_ID", f"{path}.target_id", f"target_id {target_id!r} occurs more than once"))
            seen.append(target_id)
            if target_id not in expected_set:
                issues.append(_issue("UNEXPECTED_TARGET_ID", f"{path}.target_id", f"target_id {target_id!r} was not requested"))

        for field in TARGET_FIELDS[1:-1]:
            value = target.get(field)
            if not isinstance(value, str) or value not in ENUM_VALUES:
                issues.append(_issue("INVALID_ENUM", f"{path}.{field}", f"must be one of {ENUM_VALUES!r}"))
        evidence = target.get("evidence")
        if not isinstance(evidence, str) or not evidence.strip():
            issues.append(_issue("INVALID_TYPE", f"{path}.evidence", "evidence must be a non-empty string"))

        # Do not expose a partially valid target to the decision layer.
        if not any(issue["path"] == path or issue["path"].startswith(path + ".") for issue in issues):
            parsed_targets.append({field: target[field] for field in TARGET_FIELDS})

    if set(seen) != expected_set:
        missing = sorted(expected_set - set(seen))
        if missing:
            issues.append(_issue("MISSING_TARGET_ID", "targets", f"missing requested target IDs: {missing!r}"))

    if issues:
        return ParseResult(False, (), tuple(issues), raw_type)

    # Preserve the requested local order, not model output order.
    by_id = {target["target_id"]: target for target in parsed_targets}
    ordered = tuple(by_id[target_id] for target_id in expected)
    return ParseResult(True, ordered, (), raw_type)


def _semantic_conflicts(target: Mapping[str, str]) -> list[str]:
    """Return explicit contradictory semantic assertions.

    ``road`` and ``two bays`` are both positive business subtypes and are not
    contradictory; road takes precedence for the returned positive subtype.
    """

    conflicts: list[str] = []
    if target["occupies_two_bays"] == "yes" and target["minor_line_or_nose_tail_only"] == "yes":
        conflicts.append("TWO_BAYS_AND_MINOR_ONLY")
    if target["road_or_drive_aisle"] == "yes" and target["in_one_bay_or_designated_area"] == "yes":
        conflicts.append("ROAD_AND_IN_ONE_BAY")
    if target["road_or_drive_aisle"] == "yes" and target["minor_line_or_nose_tail_only"] == "yes":
        conflicts.append("ROAD_AND_MINOR_ONLY")
    if target["occupies_two_bays"] == "yes" and target["in_one_bay_or_designated_area"] == "yes":
        conflicts.append("TWO_BAYS_AND_IN_ONE_BAY")
    return conflicts


def decide_target(target: Mapping[str, str]) -> dict[str, Any]:
    """Apply the frozen, conservative V4 target decision rules."""

    missing = sorted(set(TARGET_FIELDS) - set(target.keys()))
    unknown = sorted(set(target.keys()) - set(TARGET_FIELDS))
    if missing or unknown or not isinstance(target.get("target_id"), str) or not target.get("target_id"):
        issues = [_issue("MISSING_FIELD", field, "decision input is missing required field") for field in missing]
        issues.extend(_issue("UNKNOWN_FIELD", field, "unknown decision field is not permitted") for field in unknown)
        if "target_id" not in missing and (not isinstance(target.get("target_id"), str) or not target.get("target_id")):
            issues.append(_issue("INVALID_ENUM", "target_id", "target_id must be a non-empty string"))
        return {
            "target_id": target.get("target_id"),
            "decision": "protocol_failure",
            "alert": False,
            "reason": "INVALID_SCHEMA",
            "protocol_status": "protocol_failure",
            "protocol_issues": issues,
        }
    invalid_enums = [field for field in TARGET_FIELDS[1:-1] if target.get(field) not in ENUM_VALUES]
    if invalid_enums:
        return {
            "target_id": target.get("target_id"),
            "decision": "protocol_failure",
            "alert": False,
            "reason": "INVALID_ENUM",
            "protocol_status": "protocol_failure",
            "protocol_issues": [_issue("INVALID_ENUM", field, "decision input has an invalid enum") for field in invalid_enums],
        }

    target_id = target["target_id"]
    base = {"target_id": target_id, "raw_fields": dict(target), "protocol_status": "ok", "protocol_issues": []}
    if target["vehicle_valid"] == "no":
        return {**base, "decision": "ignore", "alert": False, "reason": "INVALID_VEHICLE"}
    if target["vehicle_valid"] == "unclear":
        return {**base, "decision": "uncertain", "alert": False, "reason": "VEHICLE_IDENTITY_UNCLEAR"}
    if target["evidence_sufficient"] != "yes":
        reason = "INSUFFICIENT_EVIDENCE" if target["evidence_sufficient"] == "no" else "EVIDENCE_SUFFICIENCY_UNCLEAR"
        return {**base, "decision": "uncertain", "alert": False, "reason": reason}
    if target["normal_gate_queue"] == "yes":
        return {**base, "decision": "negative_gate_queue", "alert": False, "reason": "NORMAL_GATE_QUEUE"}
    if target["normal_gate_queue"] == "unclear":
        return {**base, "decision": "uncertain", "alert": False, "reason": "GATE_QUEUE_UNCLEAR"}

    conflicts = _semantic_conflicts(target)
    if conflicts:
        return {
            **base,
            "decision": "uncertain",
            "alert": False,
            "reason": "SEMANTIC_CONFLICT",
            "conflicts": conflicts,
        }

    # Explicitly require no contradictory positive/negative assertion before
    # raising an alert.  Road has precedence when both positive subtypes are yes.
    if target["road_or_drive_aisle"] == "yes":
        return {**base, "decision": "positive_road", "alert": True, "reason": "ROAD_OR_DRIVE_AISLE"}
    if target["occupies_two_bays"] == "yes":
        return {**base, "decision": "positive_two_bays", "alert": True, "reason": "OCCUPIES_TWO_BAYS"}

    if target["road_or_drive_aisle"] == "no" and target["occupies_two_bays"] == "no":
        if (
            target["in_one_bay_or_designated_area"] == "yes"
            or target["minor_line_or_nose_tail_only"] == "yes"
        ):
            return {**base, "decision": "negative", "alert": False, "reason": "WITHIN_ONE_BAY_OR_MINOR_ONLY"}

    return {**base, "decision": "uncertain", "alert": False, "reason": "PARKING_RELATION_UNCLEAR"}


def aggregate_image(
    target_decisions: Iterable[Mapping[str, Any]],
    *,
    protocol_status: str = "ok",
    detector_status: str | None = None,
) -> dict[str, Any]:
    """Aggregate target decisions using conservative image-level OR logic.

    The image decision follows the required order: any reliable positive wins;
    otherwise uncertain/incomplete work prevents a negative; only all valid
    explicit negatives yield image negative.  ``protocol_status`` remains a
    separate field so a positive alert cannot hide a malformed batch.
    """

    decisions = list(target_decisions)
    labels = [str(item.get("decision")) for item in decisions]
    protocol_failed = protocol_status == "protocol_failure" or any(
        item.get("protocol_status") == "protocol_failure" or item.get("decision") == "protocol_failure"
        for item in decisions
    )
    if any(label in POSITIVE_DECISIONS for label in labels):
        image_decision = "positive"
        aggregation_reason = "ANY_RELIABLE_POSITIVE"
    elif any(label == "uncertain" or label == "protocol_failure" for label in labels) or protocol_failed:
        image_decision = "uncertain"
        aggregation_reason = "UNCERTAIN_OR_INCOMPLETE_TARGET"
    else:
        valid_negative = [label for label in labels if label in NEGATIVE_DECISIONS]
        if valid_negative and len(valid_negative) == len(labels):
            image_decision = "negative"
            aggregation_reason = "ALL_VALID_TARGETS_NEGATIVE"
        else:
            image_decision = "no_valid_target"
            aggregation_reason = detector_status or "NO_VALID_TARGET"

    return {
        "image_decision": image_decision,
        "alert": image_decision == "positive",
        "protocol_status": "protocol_failure" if protocol_failed else "ok",
        "aggregation_reason": aggregation_reason,
        "target_count": len(decisions),
        "valid_target_count": sum(label in SEMANTIC_DECISIONS or label == "uncertain" for label in labels),
    }


def classify_response(raw_response: Any, expected_target_ids: Sequence[str], *, detector_status: str | None = None) -> dict[str, Any]:
    """Parse, deterministically classify, and aggregate one model response."""

    parsed = parse_model_response(raw_response, expected_target_ids)
    if not parsed.ok:
        image = aggregate_image([], protocol_status="protocol_failure", detector_status=detector_status)
        return {
            "protocol_status": "protocol_failure",
            "protocol_issues": [dict(issue) for issue in parsed.issues],
            "targets": [],
            **image,
            "parse": parsed.as_dict(),
        }
    targets = [decide_target(target) for target in parsed.targets]
    image = aggregate_image(targets, protocol_status="ok", detector_status=detector_status)
    return {
        "protocol_status": image["protocol_status"],
        "protocol_issues": [],
        "targets": targets,
        **image,
        "parse": parsed.as_dict(),
    }
