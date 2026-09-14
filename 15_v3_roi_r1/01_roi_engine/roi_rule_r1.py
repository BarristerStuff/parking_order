from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Iterable

from config_validator import validate_roi_config
from geometry import GeometryConfigError, Polygon, as_polygon, overlap_ratio, transform_polygon_homography


POSITIVE_LABELS = {"positive_road", "positive_two_bays"}
NEGATIVE_LABELS = {
    "negative_in_bay",
    "negative_line_touch_or_minor_overrun",
    "negative_nose_tail_overhang",
    "negative_gate_queue",
}
VALID_SPACES = {"image", "bev"}


@dataclass(frozen=True)
class VehicleDecision:
    media_id: str | None
    vehicle_id: str
    label: str
    confidence: float
    reason_code: str
    evidence: str
    coordinate_space: str | None
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

    config_errors = validate_roi_config(roi_config)
    if config_errors:
        return _decision(media_id, vehicle_id, "uncertain", 0.0, "CONFIG_VALIDATION_ERROR", ";".join(config_errors), None, "none")

    try:
        footprint, vehicle_space, footprint_source = _vehicle_footprint(vehicle)
    except GeometryConfigError as exc:
        return _decision(media_id, vehicle_id, "uncertain", 0.0, str(exc), "Vehicle footprint is invalid or unsupported.", None, "none")

    if vehicle_space not in VALID_SPACES:
        return _decision(media_id, vehicle_id, "uncertain", 0.0, "INVALID_COORDINATE_SPACE", "Vehicle coordinate_space must be image or bev.", vehicle_space, footprint_source)

    try:
        working_footprint, working_space, transform_note = _choose_working_space(footprint, vehicle_space, roi_config)
    except GeometryConfigError as exc:
        return _decision(media_id, vehicle_id, "uncertain", 0.0, str(exc), "Coordinate space could not be safely aligned.", vehicle_space, footprint_source)

    try:
        return _evaluate_aligned_vehicle(vehicle, media_id, vehicle_id, working_footprint, working_space, footprint_source, roi_config, transform_note)
    except GeometryConfigError as exc:
        return _decision(media_id, vehicle_id, "uncertain", 0.0, str(exc), "Geometry operation failed safely without producing a positive alert.", working_space, footprint_source)


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
    return ImageDecision(media_id, image_label, positive_vehicle_ids, negative_vehicle_ids, uncertain_vehicle_ids, ignored_vehicle_ids, [decision.to_dict() for decision in decisions])


def _evaluate_aligned_vehicle(
    vehicle: dict[str, Any],
    media_id: str | None,
    vehicle_id: str,
    footprint: Polygon,
    working_space: str,
    footprint_source: str,
    roi_config: dict[str, Any],
    transform_note: str,
) -> VehicleDecision:
    thresholds = roi_config["thresholds"]
    ignore_ratio = overlap_ratio(footprint, _area_polygons(roi_config, "ignore_area", working_space))
    gate_ratio = overlap_ratio(footprint, _area_polygons(roi_config, "gate_queue_area", working_space))
    road_ratio = overlap_ratio(footprint, _area_polygons(roi_config, "road_area", working_space))
    parking_ratio = overlap_ratio(footprint, _area_polygons(roi_config, "parking_area", working_space))
    bay_ratios = _bay_overlap_ratios(footprint, working_space, roi_config)
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

    if ignore_ratio >= thresholds["ignore_overlap_ratio"]:
        return _decision(media_id, vehicle_id, "ignore", ignore_ratio, "IGNORE_AREA_OCCUPANCY", f"Vehicle is dominated by ignore_area. {transform_note}", working_space, footprint_source, area_ratios)
    if gate_ratio >= thresholds["gate_queue_overlap_ratio"]:
        return _decision(media_id, vehicle_id, "negative_gate_queue", gate_ratio, "GATE_QUEUE_AREA_OCCUPANCY", f"Gate queue area has priority over road positive. {transform_note}", working_space, footprint_source, area_ratios)
    if road_ratio >= thresholds["road_overlap_ratio"]:
        if footprint_source == "bbox_lower" and not thresholds["allow_bbox_road_positive"]:
            return _decision(media_id, vehicle_id, "uncertain", min(0.69, road_ratio), "BBOX_ONLY_ROAD_EVIDENCE", f"bbox_lower is weak evidence and cannot create road positive by default. {transform_note}", working_space, footprint_source, area_ratios)
        return _decision(media_id, vehicle_id, "positive_road", road_ratio, "ROAD_AREA_OCCUPANCY", f"Vehicle footprint is clearly in road/aisle. {transform_note}", working_space, footprint_source, area_ratios)
    if _occupies_two_adjacent_bays(best_bays, roi_config, thresholds):
        if footprint_source == "bbox_lower" and not thresholds["allow_bbox_two_bay_positive"]:
            return _decision(media_id, vehicle_id, "uncertain", min(0.69, best_bay_ratio + second_bay_ratio), "BBOX_ONLY_TWO_BAY_EVIDENCE", f"bbox_lower is weak evidence and cannot create two-bay positive by default. {transform_note}", working_space, footprint_source, area_ratios)
        return _decision(media_id, vehicle_id, "positive_two_bays", min(1.0, best_bay_ratio + second_bay_ratio), "TWO_ADJACENT_BAYS_OCCUPANCY", f"Vehicle footprint clearly occupies two adjacent bays. {transform_note}", working_space, footprint_source, area_ratios)
    if vehicle.get("overhang_evidence") == "runtime_geometry_nose_tail" and best_bay_ratio >= thresholds["minor_overrun_primary_bay_ratio"] and 0.0 < outside_parking_ratio <= thresholds["nose_tail_overhang_max_outside_ratio"] and second_bay_ratio == 0.0:
        return _decision(media_id, vehicle_id, "negative_nose_tail_overhang", best_bay_ratio, "NOSE_TAIL_MINOR_OVERHANG", f"Runtime geometry indicates nose/tail overhang while body remains in one bay. {transform_note}", working_space, footprint_source, area_ratios)
    if best_bay_ratio >= thresholds["in_bay_overlap_ratio"] and second_bay_ratio == 0.0 and outside_parking_ratio == 0.0:
        return _decision(media_id, vehicle_id, "negative_in_bay", best_bay_ratio, "SINGLE_BAY_DOMINANT_OCCUPANCY", f"Vehicle footprint is inside one bay. {transform_note}", working_space, footprint_source, area_ratios)
    if best_bay_ratio >= thresholds["minor_overrun_primary_bay_ratio"] and ((0.0 < second_bay_ratio <= thresholds["minor_overrun_second_bay_max_ratio"]) or (0.0 < outside_parking_ratio <= thresholds["nose_tail_overhang_max_outside_ratio"])):
        return _decision(media_id, vehicle_id, "negative_line_touch_or_minor_overrun", best_bay_ratio, "ONE_BAY_WITH_MINOR_LINE_OR_BOUNDARY_OVERLAP", f"Main body remains attributable to one bay; minor line/side overlap is non-alert. {transform_note}", working_space, footprint_source, area_ratios)
    return _decision(media_id, vehicle_id, "uncertain", 0.0, "INSUFFICIENT_SPATIAL_EVIDENCE", f"ROI evidence is not strong enough under v3. {transform_note}", working_space, footprint_source, area_ratios)


def _vehicle_footprint(vehicle: dict[str, Any]) -> tuple[Polygon, str, str]:
    if "footprint" in vehicle:
        if "coordinate_space" not in vehicle:
            raise GeometryConfigError("MISSING_COORDINATE_SPACE")
        source = str(vehicle.get("footprint_source") or "explicit_footprint")
        return as_polygon(vehicle["footprint"]), str(vehicle.get("coordinate_space")), source
    for key, space, source in [
        ("mask_polygon_image", "image", "segmentation_mask"),
        ("footprint_polygon_image", "image", "image_footprint"),
        ("footprint_polygon_bev", "bev", "bev_footprint"),
    ]:
        if vehicle.get(key):
            return as_polygon(vehicle[key]), space, source
    bbox = vehicle.get("bbox_xyxy") or vehicle.get("bbox")
    if bbox and len(bbox) == 4:
        left, top, right, bottom = [float(value) for value in bbox]
        lower_ratio = float(vehicle.get("bbox_lower_ratio", 0.5))
        return as_polygon([[left, top + (bottom - top) * (1.0 - lower_ratio)], [right, top + (bottom - top) * (1.0 - lower_ratio)], [right, bottom], [left, bottom]]), "image", "bbox_lower"
    raise GeometryConfigError("NO_USABLE_FOOTPRINT")


def _choose_working_space(footprint: Polygon, vehicle_space: str, roi_config: dict[str, Any]) -> tuple[Polygon, str, str]:
    available_spaces = _available_roi_spaces(roi_config)
    if vehicle_space in available_spaces:
        return footprint, vehicle_space, f"coordinate_space={vehicle_space}."
    if vehicle_space == "image" and "bev" in available_spaces:
        homography = roi_config.get("homography_image_to_bev")
        if homography is None:
            raise GeometryConfigError("COORDINATE_SPACE_MISMATCH_NO_HOMOGRAPHY")
        return transform_polygon_homography(footprint, homography), "bev", "image footprint transformed to BEV by homography_image_to_bev."
    raise GeometryConfigError("COORDINATE_SPACE_MISMATCH")


def _available_roi_spaces(roi_config: dict[str, Any]) -> set[str]:
    spaces = set()
    for area_name in ["parking_area", "road_area", "gate_queue_area", "ignore_area"]:
        area = roi_config.get(area_name, {})
        if area.get("polygons"):
            spaces.add(area.get("coordinate_space"))
    for bay in roi_config.get("parking_bays", []):
        if bay.get("polygon_image") is not None:
            spaces.add("image")
        if bay.get("polygon_bev") is not None:
            spaces.add("bev")
    return spaces & VALID_SPACES


def _area_polygons(roi_config: dict[str, Any], area_name: str, working_space: str) -> list[Polygon]:
    area = roi_config[area_name]
    if area["coordinate_space"] != working_space:
        return []
    return [as_polygon(polygon) for polygon in area.get("polygons", [])]


def _bay_overlap_ratios(footprint: Polygon, working_space: str, roi_config: dict[str, Any]) -> dict[str, float]:
    ratios = {}
    polygon_key = "polygon_bev" if working_space == "bev" else "polygon_image"
    for bay in roi_config.get("parking_bays", []):
        if not bay.get("enabled", True) or bay.get(polygon_key) is None:
            continue
        ratios[str(bay["bay_id"])] = overlap_ratio(footprint, [as_polygon(bay[polygon_key])])
    return ratios


def _occupies_two_adjacent_bays(best_bays: list[tuple[str, float]], roi_config: dict[str, Any], thresholds: dict[str, Any]) -> bool:
    if len(best_bays) < 2:
        return False
    first_bay_id, first_ratio = best_bays[0]
    second_bay_id, second_ratio = best_bays[1]
    if first_ratio < thresholds["two_bay_each_overlap_ratio"] or second_ratio < thresholds["two_bay_each_overlap_ratio"]:
        return False
    if first_ratio + second_ratio < thresholds["two_bay_total_overlap_ratio"]:
        return False
    adjacency = {str(bay["bay_id"]): {str(adjacent_id) for adjacent_id in bay.get("adjacent_bay_ids", [])} for bay in roi_config.get("parking_bays", [])}
    return second_bay_id in adjacency.get(first_bay_id, set()) or first_bay_id in adjacency.get(second_bay_id, set())


def _decision(media_id: str | None, vehicle_id: str, label: str, confidence: float, reason_code: str, evidence: str, coordinate_space: str | None, footprint_source: str, area_ratios: dict[str, float] | None = None) -> VehicleDecision:
    return VehicleDecision(media_id, vehicle_id, label, round(max(0.0, min(1.0, confidence)), 6), reason_code, evidence.strip(), coordinate_space, footprint_source, area_ratios or {})


def _as_vehicle_decision(decision: VehicleDecision | dict[str, Any]) -> VehicleDecision:
    if isinstance(decision, VehicleDecision):
        return decision
    return VehicleDecision(**decision)
