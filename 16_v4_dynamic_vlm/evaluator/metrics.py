#!/usr/bin/env python3
"""Reference-independent evaluation utilities for V4 development outputs.

The evaluator consumes frozen reference records and model/detector output records
but never changes the reference labels.  It reports two complementary views:

* alert metrics: every reviewed positive/negative sample remains in the alarm
  denominator, including uncertain, missing-target, and protocol-failed outputs;
* semantic metrics: only explicit positive/negative predictions with a clean
  protocol status enter the confusion matrix, with decisive coverage reported
  separately.

All rates are represented as ``{numerator, denominator, value, wilson_95}`` and
use ``null`` (Python ``None``) for a zero denominator.
"""

from __future__ import annotations

import math
from collections import Counter, defaultdict
from copy import deepcopy
from typing import Any, Iterable, Mapping, Sequence


REFERENCE_IMAGE_LABELS = {"positive", "negative", "uncertain", "disputed"}
REFERENCE_VEHICLE_LABELS = {
    "positive",
    "positive_road",
    "positive_two_bays",
    "negative",
    "negative_gate_queue",
    "negative_line_touch",
    "negative_minor_overrun",
    "negative_nose_tail_overrun",
    "negative_ordinary_bay",
    "uncertain",
    "disputed",
}
PREDICTION_DECISIONS = {
    "positive",
    "positive_road",
    "positive_two_bays",
    "negative",
    "negative_gate_queue",
    "uncertain",
    "ignore",
    "no_valid_target",
    "protocol_failure",
}
VISUAL_UNCERTAIN_REASONS = {
    "VEHICLE_IDENTITY_UNCLEAR",
    "INSUFFICIENT_EVIDENCE",
    "EVIDENCE_SUFFICIENCY_UNCLEAR",
    "CONTEXT_CROP_LOST_EVIDENCE",
    "INSUFFICIENT_SOURCE_PIXELS",
    "SOURCE_NOT_VISIBLE",
}
SEMANTIC_UNCERTAIN_REASONS = {
    "GATE_QUEUE_UNCLEAR",
    "SEMANTIC_CONFLICT",
    "PARKING_RELATION_UNCLEAR",
    "NO_UNAMBIGUOUS_NEGATIVE_RELATION",
}
ERROR_CATEGORIES = {
    "detector_miss",
    "duplicate_or_wrong_target",
    "context_crop_lost_evidence",
    "insufficient_source_pixels",
    "road_relation_error",
    "two_bay_relation_error",
    "gate_queue_error",
    "minor_overrun_false_alarm",
    "semantic_conflict",
    "protocol_failure",
    "reference_disputed",
    "reference_uncertain",
    "unprocessed_target",
    "prediction_target_missing",
}


def wilson_interval(successes: int, total: int, z: float = 1.959963984540054) -> list[float] | None:
    if total == 0:
        return None
    if successes < 0 or successes > total:
        raise ValueError(f"successes must be in [0, total], got {successes}/{total}")
    p = successes / total
    denominator = 1.0 + (z * z / total)
    centre = (p + z * z / (2.0 * total)) / denominator
    radius = z * math.sqrt((p * (1.0 - p) / total) + (z * z / (4.0 * total * total))) / denominator
    return [max(0.0, centre - radius), min(1.0, centre + radius)]


def rate(numerator: int, denominator: int) -> dict[str, Any]:
    """Return an auditable rate; value and CI are null when denominator is zero."""

    return {
        "numerator": int(numerator),
        "denominator": int(denominator),
        "value": (numerator / denominator) if denominator else None,
        "wilson_95": wilson_interval(numerator, denominator),
    }


def _confusion(tp: int, fp: int, tn: int, fn: int) -> dict[str, Any]:
    return {
        "tp": tp,
        "fp": fp,
        "tn": tn,
        "fn": fn,
        "support": tp + fp + tn + fn,
        "precision": rate(tp, tp + fp),
        "recall": rate(tp, tp + fn),
        "fpr": rate(fp, fp + tn),
    }


def _binary_label(label: Any) -> str | None:
    if not isinstance(label, str):
        return None
    if label == "positive" or label.startswith("positive_"):
        return "positive"
    if label == "negative" or label.startswith("negative_"):
        return "negative"
    return None


def _prediction_binary(decision: Any) -> str | None:
    if decision in {"positive", "positive_road", "positive_two_bays"}:
        return "positive"
    if decision in {"negative", "negative_gate_queue"}:
        return "negative"
    return None


def _prediction_alert(decision: Any) -> bool:
    return decision in {"positive", "positive_road", "positive_two_bays"}


def _reference_category(vehicle: Mapping[str, Any]) -> str | None:
    category = vehicle.get("negative_category") or vehicle.get("category")
    if isinstance(category, str):
        aliases = {
            "gate": "gate_queue",
            "queue": "gate_queue",
            "gate_queue": "gate_queue",
            "line": "line_touch",
            "line_touch": "line_touch",
            "minor": "minor_overrun",
            "minor_overrun": "minor_overrun",
            "nose_tail": "nose_tail_overrun",
            "nose_tail_overrun": "nose_tail_overrun",
            "ordinary": "ordinary_bay",
            "ordinary_bay": "ordinary_bay",
        }
        return aliases.get(category, category)
    label = vehicle.get("label") or vehicle.get("reference_label")
    if label == "negative_gate_queue":
        return "gate_queue"
    if label == "negative_line_touch":
        return "line_touch"
    if label == "negative_minor_overrun":
        return "minor_overrun"
    if label == "negative_nose_tail_overrun":
        return "nose_tail_overrun"
    if label == "negative_ordinary_bay":
        return "ordinary_bay"
    return None


def _reference_label(vehicle: Mapping[str, Any]) -> str | None:
    label = vehicle.get("label") or vehicle.get("reference_label")
    if label in REFERENCE_VEHICLE_LABELS:
        return label
    return None


def _prediction_target_index(prediction: Mapping[str, Any]) -> tuple[dict[str, Mapping[str, Any]], set[str]]:
    by_id: dict[str, Mapping[str, Any]] = {}
    duplicates: set[str] = set()
    for target in prediction.get("targets", []) or []:
        if not isinstance(target, Mapping):
            continue
        target_id = target.get("target_id")
        if not isinstance(target_id, str):
            continue
        if target_id in by_id:
            duplicates.add(target_id)
        else:
            by_id[target_id] = target
    return by_id, duplicates


def cache_match_status(reference: Mapping[str, Any], prediction: Mapping[str, Any]) -> str:
    """Compare optional detector-cache hashes without silently accepting mismatch."""

    expected = (
        reference.get("detector_cache_sha256")
        or reference.get("cache_sha256")
        or reference.get("expected_cache_sha256")
    )
    actual = prediction.get("detector_cache_sha256") or prediction.get("cache_sha256")
    if expected is None and actual is None:
        return "not_applicable"
    if expected is None or actual is None:
        return "missing"
    return "matched" if expected == actual else "mismatch"


def _effective_prediction(reference: Mapping[str, Any], prediction: Mapping[str, Any] | None) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    issues: list[dict[str, Any]] = []
    if prediction is None:
        return {
            "media_id": reference.get("media_id"),
            "image_decision": "uncertain",
            "protocol_status": "protocol_failure",
            "protocol_issues": [{"code": "MISSING_PREDICTION", "path": "$", "detail": "no prediction record matched this reference image"}],
            "targets": [],
            "detector": {},
        }, [{"code": "MISSING_PREDICTION", "media_id": reference.get("media_id")}]

    effective = deepcopy(dict(prediction))
    status = effective.get("protocol_status", "ok")
    if status not in {"ok", "protocol_failure"}:
        status = "protocol_failure"
        effective.setdefault("protocol_issues", []).append({"code": "INVALID_PROTOCOL_STATUS", "path": "protocol_status", "detail": "status must be ok or protocol_failure"})
    cache_status = cache_match_status(reference, effective)
    effective["cache_match_status"] = cache_status
    if cache_status in {"missing", "mismatch"}:
        status = "protocol_failure"
        issue = {"code": f"CACHE_{cache_status.upper()}", "path": "detector_cache_sha256", "detail": f"detector cache status is {cache_status}"}
        effective.setdefault("protocol_issues", []).append(issue)
        issues.append({"code": issue["code"], "media_id": reference.get("media_id")})
    effective["protocol_status"] = status
    if "image_decision" not in effective:
        effective["image_decision"] = "uncertain"
        effective["protocol_status"] = "protocol_failure"
        effective.setdefault("protocol_issues", []).append({"code": "MISSING_IMAGE_DECISION", "path": "image_decision", "detail": "image_decision is required"})
    return effective, issues


def _detector_info(reference: Mapping[str, Any], prediction: Mapping[str, Any], reference_ids: set[str], predicted_ids: set[str]) -> dict[str, Any]:
    raw = prediction.get("detector")
    detector = raw if isinstance(raw, Mapping) else {}
    missed_raw = detector.get("missed_target_ids")
    if isinstance(missed_raw, list):
        missed_ids = {item for item in missed_raw if isinstance(item, str)} & reference_ids
        detector_miss_count: int | None = len(missed_ids)
    elif isinstance(detector.get("detector_miss_count"), int) and not isinstance(detector.get("detector_miss_count"), bool):
        missed_ids = set()
        detector_miss_count = detector["detector_miss_count"]
    elif isinstance(detector.get("matched_target_ids"), list):
        matched_ids = {item for item in detector["matched_target_ids"] if isinstance(item, str)} & reference_ids
        missed_ids = reference_ids - matched_ids
        detector_miss_count = len(missed_ids)
    else:
        missed_ids = reference_ids - predicted_ids if detector else set()
        detector_miss_count = len(missed_ids) if detector else None

    unprocessed_raw = detector.get("unprocessed_target_ids")
    if isinstance(unprocessed_raw, list):
        unprocessed_ids = {item for item in unprocessed_raw if isinstance(item, str)} & reference_ids
        unprocessed_count: int | None = len(unprocessed_ids)
    elif isinstance(detector.get("unprocessed_target_count"), int) and not isinstance(detector.get("unprocessed_target_count"), bool):
        unprocessed_ids = set()
        unprocessed_count = detector["unprocessed_target_count"]
    else:
        unprocessed_ids = set()
        unprocessed_count = None

    extra_ids = (predicted_ids - reference_ids) | {
        item for item in (detector.get("false_detection_target_ids") or []) if isinstance(item, str)
    }
    duplicate_value = detector.get("duplicate_raw_detection_count", detector.get("duplicate_count"))
    false_value = detector.get("false_detection_count")
    raw_rows = detector.get("raw_detection_rows")
    unique_candidates = detector.get("unique_candidate_targets", detector.get("unique_target_count"))

    def nonnegative_int(value: Any) -> int | None:
        return value if isinstance(value, int) and not isinstance(value, bool) and value >= 0 else None

    return {
        "detector_present": bool(detector),
        "missed_target_ids": sorted(missed_ids),
        "detector_miss_count": nonnegative_int(detector_miss_count),
        "duplicate_count": nonnegative_int(duplicate_value),
        "false_detection_count": nonnegative_int(false_value),
        "unprocessed_target_ids": sorted(unprocessed_ids),
        "unprocessed_target_count": nonnegative_int(unprocessed_count),
        "extra_or_wrong_target_ids": sorted(extra_ids),
        "raw_detection_rows": nonnegative_int(raw_rows),
        "unique_candidate_targets": nonnegative_int(unique_candidates),
    }


def _sum_optional(values: Iterable[int | None]) -> int | None:
    materialized = list(values)
    return sum(value for value in materialized if value is not None) if any(value is not None for value in materialized) else None


def _target_error_category(reference_vehicle: Mapping[str, Any], predicted: Mapping[str, Any] | None) -> str:
    if predicted is None:
        return "prediction_target_missing"
    reason = predicted.get("reason")
    diagnostic_error = predicted.get("diagnostic_error")
    if diagnostic_error in ERROR_CATEGORIES:
        return diagnostic_error
    if reason == "SEMANTIC_CONFLICT":
        return "semantic_conflict"
    ref_label = _reference_label(reference_vehicle)
    ref_category = _reference_category(reference_vehicle)
    pred_decision = predicted.get("decision")
    if ref_category == "gate_queue" and _prediction_alert(pred_decision):
        return "gate_queue_error"
    if ref_category in {"line_touch", "minor_overrun", "nose_tail_overrun"} and _prediction_alert(pred_decision):
        return "minor_overrun_false_alarm"
    if ref_label == "positive_road" or pred_decision == "positive_road":
        return "road_relation_error"
    if ref_label == "positive_two_bays" or pred_decision == "positive_two_bays":
        return "two_bay_relation_error"
    if predicted.get("target_id") not in {None, reference_vehicle.get("target_id")}:
        return "duplicate_or_wrong_target"
    return "road_relation_error"


def _image_metrics(records: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    alert_tp = alert_fp = alert_tn = alert_fn = 0
    semantic_tp = semantic_fp = semantic_tn = semantic_fn = 0
    semantic_eligible = 0
    binary_gt = 0
    protocol_failures = 0
    uncertain_or_incomplete = 0
    gt_uncertain = gt_disputed = 0
    gt_uncertain_alerts = gt_disputed_alerts = 0

    for record in records:
        reference = record["reference"]
        prediction = record["prediction"]
        gt = reference.get("label")
        pred_decision = prediction.get("image_decision")
        pred_alert = _prediction_alert(pred_decision)
        pred_binary = _prediction_binary(pred_decision)
        protocol_ok = prediction.get("protocol_status") == "ok"
        if prediction.get("protocol_status") == "protocol_failure":
            protocol_failures += 1
        if pred_binary is None:
            uncertain_or_incomplete += 1

        if gt == "uncertain":
            gt_uncertain += 1
            gt_uncertain_alerts += int(pred_alert)
        elif gt == "disputed":
            gt_disputed += 1
            gt_disputed_alerts += int(pred_alert)
        elif gt in {"positive", "negative"}:
            binary_gt += 1
            if gt == "positive":
                if pred_alert:
                    alert_tp += 1
                else:
                    alert_fn += 1
            else:
                if pred_alert:
                    alert_fp += 1
                else:
                    alert_tn += 1
            if protocol_ok and pred_binary in {"positive", "negative"}:
                semantic_eligible += 1
                if gt == "positive":
                    if pred_binary == "positive":
                        semantic_tp += 1
                    else:
                        semantic_fn += 1
                else:
                    if pred_binary == "positive":
                        semantic_fp += 1
                    else:
                        semantic_tn += 1

    return {
        "reviewed_image_count": len(records),
        "binary_gt_image_count": binary_gt,
        "alert_confusion": _confusion(alert_tp, alert_fp, alert_tn, alert_fn),
        "semantic_confusion": _confusion(semantic_tp, semantic_fp, semantic_tn, semantic_fn),
        "decisive_coverage": rate(semantic_eligible, binary_gt),
        "protocol_failure_rate": rate(protocol_failures, len(records)),
        "uncertain_or_incomplete_rate": rate(uncertain_or_incomplete, len(records)),
        "gt_uncertain_count": gt_uncertain,
        "gt_uncertain_alert_rate": rate(gt_uncertain_alerts, gt_uncertain),
        "gt_disputed_count": gt_disputed,
        "gt_disputed_alert_rate": rate(gt_disputed_alerts, gt_disputed),
    }


def _vehicle_metrics(vehicle_rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    alert_tp = alert_fp = alert_tn = alert_fn = 0
    semantic_tp = semantic_fp = semantic_tn = semantic_fn = 0
    semantic_eligible = 0
    binary_gt = 0
    protocol_failures = visual_uncertain = semantic_uncertain = 0
    road_pos_total = road_alert_hits = road_subtype_hits = 0
    two_bay_total = two_bay_alert_hits = two_bay_subtype_hits = 0
    ordinary_total = ordinary_fp = 0
    line_minor_total = line_minor_fp = 0
    gate_total = gate_fp = 0
    uncertain_gt = disputed_gt = 0
    uncertain_gt_alerts = disputed_gt_alerts = 0

    for row in vehicle_rows:
        ref = row["reference"]
        pred = row.get("prediction")
        label = _reference_label(ref)
        gt_binary = _binary_label(label)
        decision = pred.get("decision") if pred else None
        pred_alert = _prediction_alert(decision)
        pred_binary = _prediction_binary(decision)
        protocol_ok = row.get("protocol_status") == "ok"
        if row.get("protocol_status") == "protocol_failure":
            protocol_failures += 1
        if decision == "uncertain":
            reason = pred.get("reason") if pred else None
            if reason in VISUAL_UNCERTAIN_REASONS:
                visual_uncertain += 1
            else:
                semantic_uncertain += 1

        if label == "uncertain":
            uncertain_gt += 1
            uncertain_gt_alerts += int(pred_alert)
            continue
        if label == "disputed" or label is None:
            disputed_gt += 1
            disputed_gt_alerts += int(pred_alert)
            continue
        if gt_binary not in {"positive", "negative"}:
            continue

        binary_gt += 1
        if gt_binary == "positive":
            if pred_alert:
                alert_tp += 1
            else:
                alert_fn += 1
        else:
            if pred_alert:
                alert_fp += 1
            else:
                alert_tn += 1

        if protocol_ok and pred_binary in {"positive", "negative"}:
            semantic_eligible += 1
            if gt_binary == "positive":
                if pred_binary == "positive":
                    semantic_tp += 1
                else:
                    semantic_fn += 1
            elif pred_binary == "positive":
                semantic_fp += 1
            else:
                semantic_tn += 1

        if label == "positive_road":
            road_pos_total += 1
            road_alert_hits += int(pred_alert)
            road_subtype_hits += int(decision == "positive_road" and protocol_ok)
        if label == "positive_two_bays":
            two_bay_total += 1
            two_bay_alert_hits += int(pred_alert)
            two_bay_subtype_hits += int(decision == "positive_two_bays" and protocol_ok)

        category = _reference_category(ref)
        if category == "ordinary_bay":
            ordinary_total += 1
            ordinary_fp += int(pred_alert)
        if category in {"line_touch", "minor_overrun", "nose_tail_overrun"}:
            line_minor_total += 1
            line_minor_fp += int(pred_alert)
        if category == "gate_queue":
            gate_total += 1
            gate_fp += int(pred_alert)

    return {
        "reviewed_vehicle_count": len(vehicle_rows),
        "binary_gt_vehicle_count": binary_gt,
        "alert_confusion": _confusion(alert_tp, alert_fp, alert_tn, alert_fn),
        "semantic_confusion": _confusion(semantic_tp, semantic_fp, semantic_tn, semantic_fn),
        "decisive_coverage": rate(semantic_eligible, binary_gt),
        "road_positive_alert_recall": rate(road_alert_hits, road_pos_total),
        "road_positive_subtype_accuracy": rate(road_subtype_hits, road_pos_total),
        "two_bay_positive_alert_recall": rate(two_bay_alert_hits, two_bay_total),
        "two_bay_positive_subtype_accuracy": rate(two_bay_subtype_hits, two_bay_total),
        "ordinary_parking_fpr": rate(ordinary_fp, ordinary_total),
        "line_minor_nose_tail_fpr": rate(line_minor_fp, line_minor_total),
        "gate_queue_fpr": rate(gate_fp, gate_total),
        "protocol_failure_rate": rate(protocol_failures, len(vehicle_rows)),
        "visual_uncertain_rate": rate(visual_uncertain, len(vehicle_rows)),
        "semantic_uncertain_rate": rate(semantic_uncertain, len(vehicle_rows)),
        "gt_uncertain_count": uncertain_gt,
        "gt_uncertain_alert_rate": rate(uncertain_gt_alerts, uncertain_gt),
        "gt_disputed_count": disputed_gt,
        "gt_disputed_alert_rate": rate(disputed_gt_alerts, disputed_gt),
    }


def _group_metrics(records: Sequence[Mapping[str, Any]], vehicle_rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    image_groups: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    vehicle_groups: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for record in records:
        image_groups[str(record["reference"].get("group", "UNSPECIFIED"))].append(record)
    for row in vehicle_rows:
        vehicle_groups[str(row["reference_image"].get("group", "UNSPECIFIED"))].append(row)
    return {
        "image": {group: _image_metrics(rows) for group, rows in sorted(image_groups.items())},
        "vehicle": {group: _vehicle_metrics(rows) for group, rows in sorted(vehicle_groups.items())},
    }


def _make_errors(records: Sequence[Mapping[str, Any]], vehicle_rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    errors: list[dict[str, Any]] = []
    for row in vehicle_rows:
        ref = row["reference"]
        pred = row.get("prediction")
        label = _reference_label(ref)
        if label == "disputed":
            errors.append({"media_id": row["media_id"], "group": row["group"], "target_id": ref.get("target_id"), "category": "reference_disputed", "detail": "reference vehicle is disputed and excluded from primary binary metrics"})
            continue
        if label == "uncertain":
            errors.append({"media_id": row["media_id"], "group": row["group"], "target_id": ref.get("target_id"), "category": "reference_uncertain", "detail": "reference vehicle is uncertain and excluded from primary binary metrics"})
            continue
        if row.get("protocol_status") == "protocol_failure":
            category = row.get("error_category", "protocol_failure")
            errors.append({"media_id": row["media_id"], "group": row["group"], "target_id": ref.get("target_id"), "reference_label": label, "prediction_decision": pred.get("decision") if pred else None, "category": category, "detail": "prediction is not protocol-clean; retained in alert denominator"})
            continue
        if pred is None:
            errors.append({"media_id": row["media_id"], "group": row["group"], "target_id": ref.get("target_id"), "reference_label": label, "prediction_decision": None, "category": row.get("error_category", "prediction_target_missing"), "detail": "required reference target has no prediction"})
            continue
        gt_binary = _binary_label(label)
        pred_binary = _prediction_binary(pred.get("decision"))
        if gt_binary in {"positive", "negative"} and pred_binary in {"positive", "negative"} and gt_binary != pred_binary:
            errors.append({"media_id": row["media_id"], "group": row["group"], "target_id": ref.get("target_id"), "reference_label": label, "prediction_decision": pred.get("decision"), "category": _target_error_category(ref, pred), "detail": "explicit semantic polarity disagrees"})
        elif gt_binary == "positive" and pred_binary is None:
            errors.append({"media_id": row["media_id"], "group": row["group"], "target_id": ref.get("target_id"), "reference_label": label, "prediction_decision": pred.get("decision"), "category": _target_error_category(ref, pred), "detail": "positive reference was uncertain, ignored, or not alerted"})
        elif gt_binary == "negative" and pred_binary == "positive":
            errors.append({"media_id": row["media_id"], "group": row["group"], "target_id": ref.get("target_id"), "reference_label": label, "prediction_decision": pred.get("decision"), "category": _target_error_category(ref, pred), "detail": "negative reference generated an alert"})
        if pred.get("reason") == "SEMANTIC_CONFLICT":
            errors.append({"media_id": row["media_id"], "group": row["group"], "target_id": ref.get("target_id"), "reference_label": label, "prediction_decision": pred.get("decision"), "category": "semantic_conflict", "detail": "deterministic decision rejected contradictory model fields"})

    for record in records:
        det = record.get("detector", {})
        for target_id in det.get("extra_or_wrong_target_ids", []):
            errors.append({"media_id": record["media_id"], "group": record["group"], "target_id": target_id, "category": "duplicate_or_wrong_target", "detail": "detector/model target is not a reviewed reference vehicle"})
    return errors


def join_reference_predictions(
    reference_images: Sequence[Mapping[str, Any]],
    prediction_images: Sequence[Mapping[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Join by media ID and preserve duplicate/missing/cache issues explicitly."""

    ref_by_id: dict[str, Mapping[str, Any]] = {}
    issues: list[dict[str, Any]] = []
    for reference in reference_images:
        media_id = reference.get("media_id")
        if not isinstance(media_id, str) or not media_id:
            issues.append({"code": "INVALID_REFERENCE_MEDIA_ID", "media_id": media_id})
            continue
        if media_id in ref_by_id:
            issues.append({"code": "DUPLICATE_REFERENCE_MEDIA_ID", "media_id": media_id})
        else:
            ref_by_id[media_id] = reference

    pred_by_id: dict[str, Mapping[str, Any]] = {}
    duplicate_predictions: set[str] = set()
    for prediction in prediction_images:
        media_id = prediction.get("media_id")
        if not isinstance(media_id, str) or not media_id:
            issues.append({"code": "INVALID_PREDICTION_MEDIA_ID", "media_id": media_id})
            continue
        if media_id in pred_by_id:
            duplicate_predictions.add(media_id)
            issues.append({"code": "DUPLICATE_PREDICTION_MEDIA_ID", "media_id": media_id})
        else:
            pred_by_id[media_id] = prediction

    records: list[dict[str, Any]] = []
    for media_id, reference in ref_by_id.items():
        prediction = pred_by_id.get(media_id)
        effective, join_issues = _effective_prediction(reference, prediction)
        issues.extend(join_issues)
        if media_id in duplicate_predictions:
            effective["protocol_status"] = "protocol_failure"
            effective.setdefault("protocol_issues", []).append({"code": "DUPLICATE_PREDICTION_MEDIA_ID", "path": "media_id", "detail": "multiple prediction records matched one image"})
        records.append({
            "media_id": media_id,
            "group": reference.get("group", "UNSPECIFIED"),
            "reference": reference,
            "prediction": effective,
        })
    for media_id in sorted(set(pred_by_id) - set(ref_by_id)):
        issues.append({"code": "ORPHAN_PREDICTION", "media_id": media_id})
    return records, issues


def evaluate_dataset(
    reference_images: Sequence[Mapping[str, Any]],
    prediction_images: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Evaluate image and vehicle outputs with auditable denominators."""

    records, join_issues = join_reference_predictions(reference_images, prediction_images)
    vehicle_rows: list[dict[str, Any]] = []
    detector_rows: list[dict[str, Any]] = []
    for record in records:
        reference = record["reference"]
        prediction = record["prediction"]
        ref_vehicles = reference.get("vehicles", []) or []
        ref_ids = {
            vehicle.get("target_id")
            for vehicle in ref_vehicles
            if isinstance(vehicle, Mapping) and isinstance(vehicle.get("target_id"), str)
        }
        pred_index, duplicate_ids = _prediction_target_index(prediction)
        detector = _detector_info(reference, prediction, ref_ids, set(pred_index))
        record["detector"] = detector
        detector_rows.append(detector)
        for target_id in sorted(duplicate_ids):
            join_issues.append({"code": "DUPLICATE_PREDICTION_TARGET_ID", "media_id": record["media_id"], "target_id": target_id})
        for vehicle in ref_vehicles:
            if not isinstance(vehicle, Mapping):
                join_issues.append({"code": "INVALID_REFERENCE_VEHICLE", "media_id": record["media_id"]})
                continue
            target_id = vehicle.get("target_id")
            pred = pred_index.get(target_id) if isinstance(target_id, str) else None
            error_category = None
            if target_id in detector["missed_target_ids"]:
                error_category = "detector_miss"
            elif target_id in detector["unprocessed_target_ids"]:
                error_category = "unprocessed_target"
            elif pred is None and prediction.get("protocol_status") == "protocol_failure":
                error_category = "protocol_failure"
            vehicle_rows.append({
                "media_id": record["media_id"],
                "group": record["group"],
                "reference_image": reference,
                "reference": vehicle,
                "prediction": pred,
                "protocol_status": "protocol_failure" if prediction.get("protocol_status") == "protocol_failure" or target_id in duplicate_ids else "ok",
                "error_category": error_category,
            })

    image = _image_metrics(records)
    vehicle = _vehicle_metrics(vehicle_rows)
    detector_miss = _sum_optional(row["detector_miss_count"] for row in detector_rows)
    duplicate_count = _sum_optional(row["duplicate_count"] for row in detector_rows)
    false_detection_count = _sum_optional(row["false_detection_count"] for row in detector_rows)
    unprocessed_count = _sum_optional(row["unprocessed_target_count"] for row in detector_rows)
    raw_rows = _sum_optional(row["raw_detection_rows"] for row in detector_rows)
    unique_candidates = _sum_optional(row["unique_candidate_targets"] for row in detector_rows)
    reference_vehicle_count = len(vehicle_rows)
    detector = {
        "image_count": len(detector_rows),
        "images_with_detector_record": sum(row["detector_present"] for row in detector_rows),
        "raw_detection_rows": raw_rows,
        "unique_candidate_targets": unique_candidates,
        "detector_miss": {
            "count": detector_miss,
            "rate": rate(detector_miss, reference_vehicle_count) if detector_miss is not None else None,
        },
        "duplicates": {
            "count": duplicate_count,
            "rate_over_raw_detection_rows": rate(duplicate_count, raw_rows) if duplicate_count is not None and raw_rows is not None else None,
        },
        "false_detections": {
            "count": false_detection_count,
            "rate_over_unique_candidates": rate(false_detection_count, unique_candidates) if false_detection_count is not None and unique_candidates is not None else None,
        },
        "unprocessed_targets": {
            "count": unprocessed_count,
            "rate": rate(unprocessed_count, reference_vehicle_count) if unprocessed_count is not None else None,
        },
    }
    errors = _make_errors(records, vehicle_rows)
    return {
        "status": "completed",
        "metric_contract": {
            "source_type": "AIGC",
            "reference_basis": "caller_supplied_frozen_reference",
            "human_gold": "caller_supplied_status",
            "primary_binary_labels": ["positive", "negative"],
            "gt_uncertain_and_disputed_excluded_from_primary_binary": True,
            "alert_denominator_includes_predicted_uncertain_and_protocol_failure": True,
            "semantic_confusion_requires_clean_explicit_positive_or_negative": True,
            "confidence_interval": "Wilson 95%",
            "zero_denominator": None,
        },
        "counts": {
            "reference_images": len(records),
            "reference_vehicles": reference_vehicle_count,
            "join_issues": len(join_issues),
            "error_rows": len(errors),
        },
        "image": image,
        "vehicle": vehicle,
        "detector": detector,
        "subgroups": _group_metrics(records, vehicle_rows),
        "errors": errors,
        "join_issues": join_issues,
    }
