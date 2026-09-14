from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Iterable


Point = tuple[float, float]
Polygon = list[Point]


POSITIVE_LABELS = {"positive_road", "positive_two_bays"}
NEGATIVE_LABELS = {
    "negative_in_bay",
    "negative_line_touch_or_minor_overrun",
    "negative_nose_tail_overhang",
    "negative_gate_queue",
}


@dataclass(frozen=True)
class VehicleDecision:
    media_id: str | None
    vehicle_id: str
    label: str
    confidence: float
    reason_code: str
    evidence: str
    footprint_source: str
    area_ratios: dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ImageDecision:
    media_id: str | None
    image_label: str
    positive_vehicle_ids: list[str]
    negative_vehicle_ids: list[str]
    uncertain_vehicle_ids: list[str]
    ignored_vehicle_ids: list[str]
    vehicles: list[dict[str, Any]]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def evaluate_vehicle_in_roi(vehicle: dict[str, Any], roi_config: dict[str, Any]) -> VehicleDecision:
    media_id = vehicle.get("media_id")
    vehicle_id = str(vehicle.get("vehicle_id") or vehicle.get("id") or "vehicle")
    thresholds = roi_config.get("thresholds", {})
    footprint, footprint_source = _vehicle_footprint(vehicle)
    if not footprint or polygon_area(footprint) <= 0:
        return _decision(
            media_id,
            vehicle_id,
            "uncertain",
            0.0,
            "NO_USABLE_FOOTPRINT",
            "No segmentation, BEV footprint, or usable bbox lower footprint was provided.",
            footprint_source,
        )

    footprint_area = polygon_area(footprint)
    ignore_ratio = overlap_ratio(footprint, roi_config.get("ignore_area", []), footprint_area)
    gate_ratio = overlap_ratio(footprint, roi_config.get("gate_queue_area", []), footprint_area)
    road_ratio = overlap_ratio(footprint, roi_config.get("road_area", []), footprint_area)
    parking_ratio = overlap_ratio(footprint, roi_config.get("parking_area", []), footprint_area)
    bay_ratios = _bay_overlap_ratios(footprint, footprint_area, roi_config)
    best_bays = sorted(bay_ratios.items(), key=lambda item: item[1], reverse=True)
    best_bay_ratio = best_bays[0][1] if best_bays else 0.0
    second_bay_ratio = best_bays[1][1] if len(best_bays) > 1 else 0.0
    outside_parking_ratio = max(0.0, min(1.0, 1.0 - parking_ratio))
    area_ratios = {
        "ignore": round(ignore_ratio, 6),
        "gate_queue": round(gate_ratio, 6),
        "road": round(road_ratio, 6),
        "parking_area": round(parking_ratio, 6),
        "best_bay": round(best_bay_ratio, 6),
        "second_bay": round(second_bay_ratio, 6),
        "outside_parking": round(outside_parking_ratio, 6),
    }
    area_ratios.update({f"bay:{bay_id}": round(ratio, 6) for bay_id, ratio in bay_ratios.items()})

    if ignore_ratio >= thresholds.get("ignore_overlap_ratio", 0.6):
        return _decision(
            media_id,
            vehicle_id,
            "ignore",
            min(1.0, ignore_ratio),
            "IGNORE_AREA_OCCUPANCY",
            "Vehicle footprint is dominated by ignore_area.",
            footprint_source,
            area_ratios,
        )

    if gate_ratio >= thresholds.get("gate_queue_overlap_ratio", 0.5):
        return _decision(
            media_id,
            vehicle_id,
            "negative_gate_queue",
            min(1.0, gate_ratio),
            "GATE_QUEUE_AREA_OCCUPANCY",
            "Vehicle footprint is in the configured gate_queue_area; gate queues are non-alerts.",
            footprint_source,
            area_ratios,
        )

    if road_ratio >= thresholds.get("road_overlap_ratio", 0.65):
        if _weak_bbox_only(footprint_source) and not thresholds.get("allow_bbox_road_positive", False):
            return _decision(
                media_id,
                vehicle_id,
                "uncertain",
                min(0.69, road_ratio),
                "BBOX_ONLY_ROAD_EVIDENCE",
                "Only bbox lower-footprint evidence supports road occupancy; config forbids bbox-only positive road alerts.",
                footprint_source,
                area_ratios,
            )
        return _decision(
            media_id,
            vehicle_id,
            "positive_road",
            min(1.0, road_ratio),
            "ROAD_AREA_OCCUPANCY",
            "Vehicle footprint is clearly in the configured driving road/aisle area and outside gate queue context.",
            footprint_source,
            area_ratios,
        )

    if _occupies_two_adjacent_bays(best_bays, roi_config, thresholds):
        if _weak_bbox_only(footprint_source) and not thresholds.get("allow_bbox_two_bay_positive", False):
            return _decision(
                media_id,
                vehicle_id,
                "uncertain",
                min(0.69, best_bay_ratio + second_bay_ratio),
                "BBOX_ONLY_TWO_BAY_EVIDENCE",
                "Only bbox lower-footprint evidence supports two-bay occupancy; config forbids bbox-only positive two-bay alerts.",
                footprint_source,
                area_ratios,
            )
        return _decision(
            media_id,
            vehicle_id,
            "positive_two_bays",
            min(1.0, best_bay_ratio + second_bay_ratio),
            "TWO_ADJACENT_BAYS_OCCUPANCY",
            "Vehicle footprint clearly occupies two enabled adjacent parking bays.",
            footprint_source,
            area_ratios,
        )

    if vehicle.get("overhang_type") in {"nose_tail", "front", "rear"} and _mostly_one_bay_with_small_outside(
        best_bay_ratio, outside_parking_ratio, thresholds
    ):
        return _decision(
            media_id,
            vehicle_id,
            "negative_nose_tail_overhang",
            min(0.95, best_bay_ratio),
            "NOSE_TAIL_MINOR_OVERHANG",
            "Vehicle is mainly in one bay with a configured nose/tail overhang hint; this is a non-alert.",
            footprint_source,
            area_ratios,
        )

    if best_bay_ratio >= thresholds.get("minor_overrun_primary_bay_ratio", 0.65) and (
        0.0 < second_bay_ratio <= thresholds.get("minor_overrun_second_bay_max_ratio", 0.2)
        or 0.0 < outside_parking_ratio <= thresholds.get("nose_tail_overhang_max_outside_ratio", 0.2)
    ):
        return _decision(
            media_id,
            vehicle_id,
            "negative_line_touch_or_minor_overrun",
            min(0.9, best_bay_ratio),
            "ONE_BAY_WITH_MINOR_LINE_OR_BOUNDARY_OVERLAP",
            "Vehicle is still mainly attributable to one bay; line touch or minor side overrun is a non-alert.",
            footprint_source,
            area_ratios,
        )

    if best_bay_ratio >= thresholds.get("in_bay_overlap_ratio", 0.8):
        return _decision(
            media_id,
            vehicle_id,
            "negative_in_bay",
            min(0.95, best_bay_ratio),
            "SINGLE_BAY_DOMINANT_OCCUPANCY",
            "Vehicle footprint is dominated by one enabled parking bay.",
            footprint_source,
            area_ratios,
        )

    return _decision(
        media_id,
        vehicle_id,
        "uncertain",
        0.0,
        "INSUFFICIENT_SPATIAL_EVIDENCE",
        "ROI overlaps do not provide reliable positive or negative evidence under v3 rules.",
        footprint_source,
        area_ratios,
    )


def aggregate_image_decision(vehicle_decisions: Iterable[VehicleDecision | dict[str, Any]]) -> ImageDecision:
    decisions = [_as_vehicle_decision(decision) for decision in vehicle_decisions]
    media_id = next((decision.media_id for decision in decisions if decision.media_id), None)
    positive_vehicle_ids = [decision.vehicle_id for decision in decisions if decision.label in POSITIVE_LABELS]
    negative_vehicle_ids = [decision.vehicle_id for decision in decisions if decision.label in NEGATIVE_LABELS]
    uncertain_vehicle_ids = [decision.vehicle_id for decision in decisions if decision.label == "uncertain"]
    ignored_vehicle_ids = [decision.vehicle_id for decision in decisions if decision.label == "ignore"]

    if positive_vehicle_ids:
        image_label = "positive"
    elif decisions and len(ignored_vehicle_ids) == len(decisions):
        image_label = "ignore"
    elif uncertain_vehicle_ids:
        image_label = "uncertain"
    elif negative_vehicle_ids:
        image_label = "negative"
    else:
        image_label = "ignore"

    return ImageDecision(
        media_id=media_id,
        image_label=image_label,
        positive_vehicle_ids=positive_vehicle_ids,
        negative_vehicle_ids=negative_vehicle_ids,
        uncertain_vehicle_ids=uncertain_vehicle_ids,
        ignored_vehicle_ids=ignored_vehicle_ids,
        vehicles=[decision.to_dict() for decision in decisions],
    )


def polygon_area(polygon: Polygon) -> float:
    if len(polygon) < 3:
        return 0.0
    signed_area = 0.0
    for point_index, point in enumerate(polygon):
        next_point = polygon[(point_index + 1) % len(polygon)]
        signed_area += point[0] * next_point[1] - next_point[0] * point[1]
    return abs(signed_area) / 2.0


def overlap_ratio(subject_polygon: Polygon, roi_polygons: Iterable[list[list[float]]], subject_area: float | None = None) -> float:
    base_area = subject_area if subject_area is not None else polygon_area(subject_polygon)
    if base_area <= 0:
        return 0.0
    intersection_total = 0.0
    for roi_polygon in roi_polygons or []:
        clip_polygon_points = _as_polygon(roi_polygon)
        clipped_polygon = clip_polygon(subject_polygon, clip_polygon_points)
        intersection_total += polygon_area(clipped_polygon)
    return max(0.0, min(1.0, intersection_total / base_area))


def clip_polygon(subject_polygon: Polygon, clip_polygon_points: Polygon) -> Polygon:
    if len(subject_polygon) < 3 or len(clip_polygon_points) < 3:
        return []
    output_polygon = list(subject_polygon)
    orientation = _signed_polygon_area(clip_polygon_points)
    for edge_index, edge_start in enumerate(clip_polygon_points):
        edge_end = clip_polygon_points[(edge_index + 1) % len(clip_polygon_points)]
        input_polygon = output_polygon
        output_polygon = []
        if not input_polygon:
            break
        previous_point = input_polygon[-1]
        for current_point in input_polygon:
            current_inside = _inside_half_plane(current_point, edge_start, edge_end, orientation)
            previous_inside = _inside_half_plane(previous_point, edge_start, edge_end, orientation)
            if current_inside:
                if not previous_inside:
                    output_polygon.append(_line_intersection(previous_point, current_point, edge_start, edge_end))
                output_polygon.append(current_point)
            elif previous_inside:
                output_polygon.append(_line_intersection(previous_point, current_point, edge_start, edge_end))
            previous_point = current_point
    return output_polygon


def _vehicle_footprint(vehicle: dict[str, Any]) -> tuple[Polygon, str]:
    for key, source in (
        ("mask_polygon_image", "segmentation_mask"),
        ("footprint_polygon_bev", "bev_footprint"),
        ("footprint_polygon_image", "image_footprint"),
    ):
        if vehicle.get(key):
            return _as_polygon(vehicle[key]), source

    bbox = vehicle.get("bbox_xyxy") or vehicle.get("bbox")
    if bbox and len(bbox) == 4:
        left, top, right, bottom = [float(value) for value in bbox]
        lower_ratio = float(vehicle.get("bbox_lower_ratio", 0.5))
        lower_top = top + (bottom - top) * (1.0 - lower_ratio)
        return [(left, lower_top), (right, lower_top), (right, bottom), (left, bottom)], "bbox_lower"
    return [], "none"


def _bay_overlap_ratios(footprint: Polygon, footprint_area: float, roi_config: dict[str, Any]) -> dict[str, float]:
    ratios: dict[str, float] = {}
    for bay in roi_config.get("parking_bays", []):
        if not bay.get("enabled", True):
            continue
        ratios[str(bay["bay_id"])] = overlap_ratio(footprint, [bay["polygon_image"]], footprint_area)
    return ratios


def _occupies_two_adjacent_bays(
    best_bays: list[tuple[str, float]], roi_config: dict[str, Any], thresholds: dict[str, Any]
) -> bool:
    if len(best_bays) < 2:
        return False
    first_bay_id, first_ratio = best_bays[0]
    second_bay_id, second_ratio = best_bays[1]
    if first_ratio < thresholds.get("two_bay_each_overlap_ratio", 0.25):
        return False
    if second_ratio < thresholds.get("two_bay_each_overlap_ratio", 0.25):
        return False
    if first_ratio + second_ratio < thresholds.get("two_bay_total_overlap_ratio", 0.7):
        return False
    adjacency = {
        str(bay["bay_id"]): {str(adjacent_id) for adjacent_id in bay.get("adjacent_bay_ids", [])}
        for bay in roi_config.get("parking_bays", [])
    }
    return second_bay_id in adjacency.get(first_bay_id, set()) or first_bay_id in adjacency.get(second_bay_id, set())


def _mostly_one_bay_with_small_outside(best_bay_ratio: float, outside_parking_ratio: float, thresholds: dict[str, Any]) -> bool:
    return best_bay_ratio >= thresholds.get("minor_overrun_primary_bay_ratio", 0.65) and outside_parking_ratio <= thresholds.get(
        "nose_tail_overhang_max_outside_ratio", 0.2
    )


def _weak_bbox_only(footprint_source: str) -> bool:
    return footprint_source == "bbox_lower"


def _decision(
    media_id: str | None,
    vehicle_id: str,
    label: str,
    confidence: float,
    reason_code: str,
    evidence: str,
    footprint_source: str,
    area_ratios: dict[str, float] | None = None,
) -> VehicleDecision:
    return VehicleDecision(
        media_id=media_id,
        vehicle_id=vehicle_id,
        label=label,
        confidence=round(max(0.0, min(1.0, confidence)), 6),
        reason_code=reason_code,
        evidence=evidence,
        footprint_source=footprint_source,
        area_ratios=area_ratios or {},
    )


def _as_vehicle_decision(decision: VehicleDecision | dict[str, Any]) -> VehicleDecision:
    if isinstance(decision, VehicleDecision):
        return decision
    return VehicleDecision(**decision)


def _as_polygon(points: Iterable[Iterable[float]]) -> Polygon:
    return [(float(point[0]), float(point[1])) for point in points]


def _signed_polygon_area(polygon: Polygon) -> float:
    signed_area = 0.0
    for point_index, point in enumerate(polygon):
        next_point = polygon[(point_index + 1) % len(polygon)]
        signed_area += point[0] * next_point[1] - next_point[0] * point[1]
    return signed_area / 2.0


def _inside_half_plane(point: Point, edge_start: Point, edge_end: Point, orientation: float) -> bool:
    cross_product = (edge_end[0] - edge_start[0]) * (point[1] - edge_start[1]) - (edge_end[1] - edge_start[1]) * (
        point[0] - edge_start[0]
    )
    if orientation >= 0:
        return cross_product >= -1e-9
    return cross_product <= 1e-9


def _line_intersection(segment_start: Point, segment_end: Point, edge_start: Point, edge_end: Point) -> Point:
    segment_x_delta = segment_end[0] - segment_start[0]
    segment_y_delta = segment_end[1] - segment_start[1]
    edge_x_delta = edge_end[0] - edge_start[0]
    edge_y_delta = edge_end[1] - edge_start[1]
    denominator = segment_x_delta * edge_y_delta - segment_y_delta * edge_x_delta
    if abs(denominator) < 1e-12:
        return segment_end
    scale = ((edge_start[0] - segment_start[0]) * edge_y_delta - (edge_start[1] - segment_start[1]) * edge_x_delta) / denominator
    return (segment_start[0] + scale * segment_x_delta, segment_start[1] + scale * segment_y_delta)
