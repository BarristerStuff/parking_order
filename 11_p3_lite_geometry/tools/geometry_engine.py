#!/usr/bin/env python3
"""Deterministic local parking-geometry inference with no evaluation metadata.

The input schema intentionally excludes GT, role, group, source_id, media_id,
and evaluation scope. The engine uses only image pixels, content hash, and the
pre-existing vehicle detections.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import time
from pathlib import Path
from typing import Any, Iterable

import cv2
import numpy as np


FORBIDDEN_INPUT_KEYS = {
    "gt", "v1_2_gt", "sample_role", "group", "group_key", "group_id",
    "source_id", "evaluation_scope", "pilot_stratum", "media_id",
}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def clip(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def angle_difference(a: float, b: float) -> float:
    difference = abs(a - b) % 180.0
    return min(difference, 180.0 - difference)


def points_on_line(x1: float, y1: float, x2: float, y2: float, count: int = 31) -> np.ndarray:
    t = np.linspace(0.0, 1.0, count)
    return np.stack((x1 + (x2 - x1) * t, y1 + (y2 - y1) * t), axis=1)


def sample_image(image: np.ndarray, points: np.ndarray) -> np.ndarray:
    height, width = image.shape[:2]
    xs = np.clip(np.rint(points[:, 0]).astype(int), 0, width - 1)
    ys = np.clip(np.rint(points[:, 1]).astype(int), 0, height - 1)
    return image[ys, xs]


def line_scores(
    gray: np.ndarray,
    bright_mask: np.ndarray,
    line: tuple[float, float, float, float],
    vehicle_box_roi: tuple[float, float, float, float],
    minimum_length: float,
) -> dict[str, float]:
    x1, y1, x2, y2 = line
    dx, dy = x2 - x1, y2 - y1
    length = math.hypot(dx, dy)
    samples = points_on_line(x1, y1, x2, y2)
    values = sample_image(gray, samples).astype(float)
    brightness = float(values.mean())
    bright_fraction = float((sample_image(bright_mask, samples) > 0).mean())

    normal_x, normal_y = -dy / max(length, 1e-6), dx / max(length, 1e-6)
    side_a = sample_image(gray, samples + np.array([normal_x * 6.0, normal_y * 6.0])).astype(float)
    side_b = sample_image(gray, samples - np.array([normal_x * 6.0, normal_y * 6.0])).astype(float)
    local_contrast = float(np.maximum(values - side_a, values - side_b).mean())

    bx1, by1, bx2, by2 = vehicle_box_roi
    inside = (
        (samples[:, 0] >= bx1) & (samples[:, 0] <= bx2)
        & (samples[:, 1] >= by1) & (samples[:, 1] <= by2)
    )
    exposed_fraction = float((~inside).mean())
    length_score = clip(length / max(minimum_length * 2.8, 1.0))
    brightness_score = clip((brightness - 90.0) / 120.0)
    bright_score = clip(bright_fraction / 0.6)
    contrast_score = clip((local_contrast - 2.0) / 35.0)
    confidence = (
        0.25 * length_score + 0.24 * brightness_score + 0.20 * bright_score
        + 0.18 * contrast_score + 0.13 * exposed_fraction
    )
    return {
        "length": length,
        "brightness_score": brightness_score,
        "brightness_mean": brightness,
        "bright_tube_fraction": bright_fraction,
        "local_contrast": local_contrast,
        "exposed_fraction": exposed_fraction,
        "candidate_confidence": confidence,
    }


def x_at_y(line: dict[str, float], target_y: float) -> float | None:
    dy = line["y2"] - line["y1"]
    if abs(dy) < 1e-6:
        return None
    ratio = (target_y - line["y1"]) / dy
    # Allow limited extrapolation because markings are commonly occluded by cars.
    if ratio < -0.8 or ratio > 1.8:
        return None
    return line["x1"] + ratio * (line["x2"] - line["x1"])


def merge_separators(
    lines: list[dict[str, float]], anchor_y: float, merge_distance: float
) -> list[dict[str, Any]]:
    projected = []
    for line in lines:
        position = x_at_y(line, anchor_y)
        if position is not None:
            projected.append((position, line))
    projected.sort(key=lambda item: item[0])
    clusters: list[list[tuple[float, dict[str, float]]]] = []
    for position, line in projected:
        if not clusters or position - np.average(
            [item[0] for item in clusters[-1]],
            weights=[max(item[1]["candidate_confidence"], 0.01) for item in clusters[-1]],
        ) > merge_distance:
            clusters.append([(position, line)])
        else:
            clusters[-1].append((position, line))
    separators = []
    for cluster in clusters:
        weights = np.array([max(item[1]["candidate_confidence"], 0.01) for item in cluster])
        positions = np.array([item[0] for item in cluster])
        best = max((item[1] for item in cluster), key=lambda line: line["candidate_confidence"])
        separators.append({
            "x_at_anchor": float(np.average(positions, weights=weights)),
            "score": float(max(item[1]["candidate_confidence"] for item in cluster)),
            "support_count": len(cluster),
            "angle": float(best["angle"]),
            "best_line": best,
        })
    return separators


def analyze_vehicle(
    image: np.ndarray,
    detection: dict[str, Any],
    config: dict[str, Any],
) -> tuple[dict[str, Any], np.ndarray]:
    height, width = image.shape[:2]
    x1, y1, x2, y2 = [float(value) for value in detection["bbox"]]
    bbox_width, bbox_height = x2 - x1, y2 - y1
    center_x = (x1 + x2) / 2.0
    anchor_y = y2 - float(config["anchor_vertical_inset_fraction"]) * bbox_height
    horizontal_inset = float(config["anchor_horizontal_inset_fraction"]) * bbox_width
    left_anchor_x = x1 + horizontal_inset
    right_anchor_x = x2 - horizontal_inset

    context_width = bbox_width * float(config["context_width_scale"])
    roi_x1 = max(0, int(round(center_x - context_width / 2.0)))
    roi_x2 = min(width, int(round(center_x + context_width / 2.0)))
    roi_y1 = max(0, int(round(y1 + float(config["context_top_fraction_of_bbox"]) * bbox_height)))
    roi_y2 = min(height, int(round(y2 + float(config["context_bottom_extension_fraction"]) * bbox_height)))
    if roi_x2 - roi_x1 < 32 or roi_y2 - roi_y1 < 32:
        return ({
            "detection": detection,
            "geometry_state": "insufficient",
            "geometry_confidence": "none",
            "reason_code": "invalid_context_roi",
            "line_candidates": [],
            "separators": [],
        }, image.copy())

    roi = image[roi_y1:roi_y2, roi_x1:roi_x2]
    gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
    clahe = cv2.createCLAHE(
        clipLimit=float(config["clahe_clip_limit"]),
        tileGridSize=(int(config["clahe_tile_grid"]), int(config["clahe_tile_grid"])),
    )
    enhanced = clahe.apply(gray)
    hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
    white = (
        (hsv[:, :, 2] >= 150) & (hsv[:, :, 1] <= 105)
    )
    yellow = (
        (hsv[:, :, 0] >= 10) & (hsv[:, :, 0] <= 42)
        & (hsv[:, :, 1] >= 55) & (hsv[:, :, 2] >= 105)
    )
    bright_mask = ((white | yellow).astype(np.uint8) * 255)
    edges = cv2.Canny(enhanced, int(config["canny_low"]), int(config["canny_high"]))
    # Retain all Canny support plus a narrow bright-marking prior.
    bright_edges = cv2.Canny(bright_mask, 40, 120)
    line_input = cv2.bitwise_or(edges, bright_edges)
    refine = cv2.LSD_REFINE_STD if config["lsd_refine"] == "standard" else cv2.LSD_REFINE_NONE
    detector = cv2.createLineSegmentDetector(refine)
    detected = detector.detect(line_input)[0]

    roi_diagonal = math.hypot(roi.shape[1], roi.shape[0])
    minimum_length = max(
        float(config["minimum_line_length_pixels"]),
        float(config["minimum_line_length_roi_diagonal_fraction"]) * roi_diagonal,
    )
    vehicle_box_roi = (x1 - roi_x1, y1 - roi_y1, x2 - roi_x1, y2 - roi_y1)
    candidates: list[dict[str, float]] = []
    raw_line_count = 0 if detected is None else len(detected)
    if detected is not None:
        # OpenCV 4 commonly returns (N, 1, 4); OpenCV 5 may return (N, 4).
        for raw in np.asarray(detected).reshape(-1, 4):
            lx1, ly1, lx2, ly2 = [float(value) for value in raw]
            dx, dy = lx2 - lx1, ly2 - ly1
            length = math.hypot(dx, dy)
            angle = abs(math.degrees(math.atan2(dy, dx))) % 180.0
            angle_from_horizontal = min(angle, 180.0 - angle)
            midpoint_global_y = (ly1 + ly2) / 2.0 + roi_y1
            if length < minimum_length:
                continue
            if angle_from_horizontal < float(config["minimum_line_angle_from_horizontal_degrees"]):
                continue
            if midpoint_global_y < y1 + float(config["minimum_line_midpoint_vehicle_height_fraction"]) * bbox_height:
                continue
            scores = line_scores(
                enhanced, bright_mask, (lx1, ly1, lx2, ly2), vehicle_box_roi, minimum_length
            )
            appearance_ok = (
                scores["bright_tube_fraction"] >= float(config["minimum_bright_tube_fraction"])
                or (
                    scores["brightness_mean"] >= float(config["minimum_line_brightness"])
                    and scores["local_contrast"] >= float(config["minimum_local_contrast"])
                )
            )
            if not appearance_ok:
                continue
            if scores["exposed_fraction"] < float(config["minimum_line_exposed_fraction"]):
                continue
            if scores["candidate_confidence"] < float(config["minimum_candidate_confidence"]):
                continue
            candidates.append({
                "x1": lx1 + roi_x1, "y1": ly1 + roi_y1,
                "x2": lx2 + roi_x1, "y2": ly2 + roi_y1,
                "length": scores["length"], "angle": angle,
                "brightness_score": scores["brightness_score"],
                "brightness_mean": scores["brightness_mean"],
                "bright_tube_fraction": scores["bright_tube_fraction"],
                "local_contrast": scores["local_contrast"],
                "exposed_fraction": scores["exposed_fraction"],
                "candidate_confidence": scores["candidate_confidence"],
            })

    merge_distance = max(
        float(config["line_merge_minimum_pixels"]),
        float(config["line_merge_vehicle_width_fraction"]) * bbox_width,
    )
    separators = merge_separators(candidates, anchor_y, merge_distance)
    # Discard projections outside the local context; large extrapolations are unstable.
    separators = [
        item for item in separators
        if roi_x1 - 0.15 * bbox_width <= item["x_at_anchor"] <= roi_x2 + 0.15 * bbox_width
    ]

    slot_pairs = []
    for left, right in zip(separators, separators[1:]):
        width_ratio = (right["x_at_anchor"] - left["x_at_anchor"]) / max(bbox_width, 1.0)
        orientation_difference = angle_difference(left["angle"], right["angle"])
        if (
            float(config["minimum_slot_width_vehicle_fraction"]) <= width_ratio
            <= float(config["maximum_slot_width_vehicle_fraction"])
            and orientation_difference <= float(config["maximum_pair_orientation_difference_degrees"])
        ):
            pair_score = min(left["score"], right["score"]) * clip(
                1.0 - orientation_difference / 50.0, 0.5, 1.0
            )
            high = (
                float(config["high_slot_minimum_width_vehicle_fraction"]) <= width_ratio
                <= float(config["high_slot_maximum_width_vehicle_fraction"])
                and pair_score >= float(config["minimum_high_slot_pair_score"])
            )
            slot_pairs.append({
                "left_x": left["x_at_anchor"], "right_x": right["x_at_anchor"],
                "width_vehicle_fraction": width_ratio,
                "orientation_difference": orientation_difference,
                "pair_score": pair_score, "high": high,
            })

    containing_pairs = [
        pair for pair in slot_pairs
        if pair["left_x"] <= center_x <= pair["right_x"]
    ]
    best_pair = max(containing_pairs, key=lambda pair: pair["pair_score"], default=None)
    high_separators = [
        item for item in separators
        if item["score"] >= float(config["minimum_positive_separator_score"])
    ]
    internal = [
        item for item in high_separators
        if left_anchor_x + float(config["positive_internal_core_margin_vehicle_fraction"]) * bbox_width
        < item["x_at_anchor"]
        < right_anchor_x - float(config["positive_internal_core_margin_vehicle_fraction"]) * bbox_width
    ]

    positive_rule = None
    if len(high_separators) >= int(config["minimum_continuous_separator_count"]) and internal:
        for item in internal:
            left_neighbors = [other for other in high_separators if other["x_at_anchor"] < item["x_at_anchor"]]
            right_neighbors = [other for other in high_separators if other["x_at_anchor"] > item["x_at_anchor"]]
            if left_neighbors and right_neighbors:
                left_gap = (item["x_at_anchor"] - left_neighbors[-1]["x_at_anchor"]) / bbox_width
                right_gap = (right_neighbors[0]["x_at_anchor"] - item["x_at_anchor"]) / bbox_width
                if (
                    float(config["minimum_slot_width_vehicle_fraction"]) <= left_gap <= float(config["maximum_slot_width_vehicle_fraction"])
                    and float(config["minimum_slot_width_vehicle_fraction"]) <= right_gap <= float(config["maximum_slot_width_vehicle_fraction"])
                ):
                    positive_rule = "G2_crosses_complete_slot_interval"
                    break

    if positive_rule is None and len(high_separators) >= 2:
        high_positions = [item["x_at_anchor"] for item in high_separators]
        outside_margin = float(config["positive_outside_margin_vehicle_fraction"]) * bbox_width
        max_distance = float(config["positive_nearest_structure_max_vehicle_fraction"]) * bbox_width
        all_left = max(high_positions) < left_anchor_x - outside_margin
        all_right = min(high_positions) > right_anchor_x + outside_margin
        adjacent_plausible = any(pair["high"] for pair in slot_pairs)
        if all_left and left_anchor_x - max(high_positions) <= max_distance and adjacent_plausible:
            positive_rule = "G1_outside_adjacent_slot_structure_left"
        elif all_right and min(high_positions) - right_anchor_x <= max_distance and adjacent_plausible:
            positive_rule = "G1_outside_adjacent_slot_structure_right"

    tolerance = float(config["normal_boundary_tolerance_vehicle_fraction"]) * bbox_width
    normal = bool(
        best_pair
        and best_pair["high"]
        and best_pair["left_x"] <= left_anchor_x + tolerance
        and best_pair["right_x"] >= right_anchor_x - tolerance
        and not internal
    )
    if positive_rule:
        state, confidence, reason = "positive", "high", positive_rule
    elif normal:
        state, confidence, reason = "normal", "high", "slot_pair_contains_vehicle_contact_anchors"
    else:
        state, confidence = "insufficient", "low" if candidates else "none"
        if not candidates:
            reason = "no_reliable_line_candidates"
        elif len(separators) < 2:
            reason = "insufficient_distinct_boundaries"
        elif not slot_pairs:
            reason = "no_plausible_slot_pair"
        elif best_pair and not best_pair["high"]:
            reason = "slot_pair_not_high_confidence"
        else:
            reason = "geometry_not_decisive"

    result = {
        "detection": detection,
        "anchors": {
            "bottom_center": [center_x, anchor_y],
            "bottom_left": [left_anchor_x, anchor_y],
            "bottom_right": [right_anchor_x, anchor_y],
        },
        "context_roi": [roi_x1, roi_y1, roi_x2, roi_y2],
        "raw_line_count": raw_line_count,
        "line_candidates": candidates,
        "separators": separators,
        "slot_pairs": slot_pairs,
        "slot_geometry_confidence": "high" if any(pair["high"] for pair in slot_pairs) else (
            "medium" if slot_pairs else "none"
        ),
        "vehicle_center_between_slot_boundaries": best_pair is not None,
        "vehicle_bottom_center_between_boundaries": best_pair is not None,
        "left_boundary_distance_normalized": (
            (center_x - best_pair["left_x"]) / bbox_width if best_pair else None
        ),
        "right_boundary_distance_normalized": (
            (best_pair["right_x"] - center_x) / bbox_width if best_pair else None
        ),
        "vehicle_heading_vs_slot_heading": None,
        "crosses_multiple_slot_intervals": positive_rule == "G2_crosses_complete_slot_interval",
        "outside_nearest_slot_structure": bool(positive_rule and positive_rule.startswith("G1_")),
        "geometry_state": state,
        "geometry_confidence": confidence,
        "reason_code": reason,
    }

    overlay = image.copy()
    cv2.rectangle(overlay, (roi_x1, roi_y1), (roi_x2, roi_y2), (255, 170, 0), 2)
    cv2.rectangle(overlay, (round(x1), round(y1)), (round(x2), round(y2)), (0, 210, 0), 3)
    for candidate in candidates:
        color = (0, 0, 255) if candidate["candidate_confidence"] >= float(config["high_candidate_confidence"]) else (0, 150, 255)
        cv2.line(
            overlay,
            (round(candidate["x1"]), round(candidate["y1"])),
            (round(candidate["x2"]), round(candidate["y2"])),
            color,
            2,
        )
    for separator in separators:
        sx = round(separator["x_at_anchor"])
        cv2.circle(overlay, (sx, round(anchor_y)), 8, (255, 0, 255), -1)
    for ax in (left_anchor_x, center_x, right_anchor_x):
        cv2.circle(overlay, (round(ax), round(anchor_y)), 7, (255, 255, 0), -1)
    cv2.putText(
        overlay,
        f"{state}/{reason}",
        (max(10, round(x1)), max(35, round(y1) - 12)),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.72,
        (30, 30, 255) if state == "positive" else (30, 220, 30),
        2,
        cv2.LINE_AA,
    )
    return result, overlay


def analyze_sample(row: dict[str, Any], config: dict[str, Any]) -> tuple[dict[str, Any], np.ndarray]:
    forbidden = FORBIDDEN_INPUT_KEYS.intersection(row)
    if forbidden:
        raise RuntimeError(f"geometry input contains forbidden evaluation keys: {sorted(forbidden)}")
    expected_keys = {"sample_token", "image_path", "image_sha256", "detections", "detector_latency_seconds"}
    if set(row) != expected_keys:
        raise RuntimeError(f"unexpected geometry input schema: {sorted(set(row) - expected_keys)}")
    image_path = Path(row["image_path"])
    if sha256_file(image_path) != row["image_sha256"] or row["sample_token"] != row["image_sha256"]:
        raise RuntimeError("image binding/hash mismatch")
    image = cv2.imread(str(image_path), cv2.IMREAD_COLOR)
    if image is None:
        raise RuntimeError("failed to read image")
    height, width = image.shape[:2]
    image_area = height * width
    detections = []
    for detection in row["detections"]:
        x1, y1, x2, y2 = detection["bbox"]
        if detection["class_name"] not in {"car", "truck", "bus"}:
            continue
        if float(detection["confidence"]) < float(config["minimum_detection_confidence"]):
            continue
        if (x2 - x1) * (y2 - y1) / image_area < float(config["minimum_bbox_area_fraction"]):
            continue
        detections.append(detection)
    detections.sort(
        key=lambda det: (det["bbox"][2] - det["bbox"][0]) * (det["bbox"][3] - det["bbox"][1]) * det["confidence"],
        reverse=True,
    )
    detections = detections[: int(config["maximum_vehicle_detections"])]

    started = time.perf_counter()
    vehicle_results = []
    overlay = image.copy()
    for detection in detections:
        result, vehicle_overlay = analyze_vehicle(image, detection, config)
        vehicle_results.append(result)
        # Combine non-background annotations from each independently rendered overlay.
        difference = cv2.absdiff(vehicle_overlay, image)
        mask = cv2.cvtColor(difference, cv2.COLOR_BGR2GRAY) > 0
        overlay[mask] = vehicle_overlay[mask]
    elapsed = time.perf_counter() - started

    if any(item["geometry_state"] == "positive" for item in vehicle_results):
        state = "positive"
        reason = next(item["reason_code"] for item in vehicle_results if item["geometry_state"] == "positive")
    elif any(item["geometry_state"] == "normal" for item in vehicle_results):
        state = "normal"
        reason = "at_least_one_high_confidence_normal_no_positive"
    else:
        state = "insufficient"
        reason = "no_vehicle_level_decisive_geometry" if vehicle_results else "no_eligible_vehicle_detection"
    sample = {
        "sample_token": row["sample_token"],
        "image_sha256": row["image_sha256"],
        "geometry_state": state,
        "geometry_confidence": "high" if state in {"positive", "normal"} else "none",
        "reason_code": reason,
        "input_detection_count": len(row["detections"]),
        "eligible_detection_count": len(detections),
        "vehicle_results": vehicle_results,
        "detector_latency_seconds": float(row.get("detector_latency_seconds", 0.0)),
        "geometry_latency_seconds": elapsed,
        "total_logical_latency_seconds": float(row.get("detector_latency_seconds", 0.0)) + elapsed,
    }
    return sample, overlay


def write_contact_sheet(overlays: list[np.ndarray], labels: list[str], path: Path) -> None:
    cards = []
    for overlay, label in zip(overlays, labels):
        scale = min(640 / overlay.shape[1], 400 / overlay.shape[0])
        resized = cv2.resize(
            overlay,
            (max(1, round(overlay.shape[1] * scale)), max(1, round(overlay.shape[0] * scale))),
            interpolation=cv2.INTER_AREA,
        )
        card = np.full((440, 660, 3), 245, dtype=np.uint8)
        top = (400 - resized.shape[0]) // 2 + 10
        left = (640 - resized.shape[1]) // 2 + 10
        card[top : top + resized.shape[0], left : left + resized.shape[1]] = resized
        cv2.putText(card, label[:100], (12, 430), cv2.FONT_HERSHEY_SIMPLEX, 0.53, (20, 20, 20), 1, cv2.LINE_AA)
        cards.append(card)
    rows = []
    for index in range(0, len(cards), 2):
        pair = cards[index:index + 2]
        if len(pair) == 1:
            pair.append(np.full_like(pair[0], 245))
        rows.append(np.hstack(pair))
    sheet = np.vstack(rows)
    if not cv2.imwrite(str(path), sheet, [cv2.IMWRITE_JPEG_QUALITY, 90]):
        raise RuntimeError(f"failed to write {path}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--contact-sheet", type=Path)
    args = parser.parse_args()

    config = json.loads(args.config.read_text(encoding="utf-8"))
    if config.get("frozen") is not True:
        raise SystemExit("geometry configuration is not frozen")
    rows = read_jsonl(args.input)
    if args.output.exists():
        raise SystemExit(f"refusing to overwrite geometry evidence: {args.output}")
    results, overlays, labels = [], [], []
    for index, row in enumerate(rows, 1):
        result, overlay = analyze_sample(row, config)
        results.append(result)
        overlays.append(overlay)
        labels.append(f"{index:02d} {result['geometry_state']} {result['reason_code']}")
        print(
            f"GEOMETRY_PROGRESS completed={index}/{len(rows)} state={result['geometry_state']} "
            f"vehicles={result['eligible_detection_count']}",
            flush=True,
        )
    with args.output.open("x", encoding="utf-8") as handle:
        for result in results:
            handle.write(json.dumps(result, ensure_ascii=False, sort_keys=True) + "\n")
    if args.contact_sheet:
        if args.contact_sheet.exists():
            raise SystemExit(f"refusing to overwrite contact sheet: {args.contact_sheet}")
        write_contact_sheet(overlays, labels, args.contact_sheet)
    print(json.dumps({
        "status": "completed",
        "sample_count": len(results),
        "state_counts": {
            state: sum(result["geometry_state"] == state for result in results)
            for state in ("positive", "normal", "insufficient")
        },
        "config_sha256": sha256_file(args.config),
    }, sort_keys=True))


if __name__ == "__main__":
    main()
