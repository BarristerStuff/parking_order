from __future__ import annotations

import math
from typing import Any

from geometry import GeometryConfigError, as_polygon, validate_homography


VALID_SPACES = {"image", "bev"}


def validate_roi_config(config: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    try:
        _require(config, "camera_id")
        _require(config, "route_id")
        coordinate_space = config.get("coordinate_space")
        if coordinate_space not in VALID_SPACES | {"mixed"}:
            errors.append("CONFIG_COORDINATE_SPACE_INVALID")
        _validate_image_size(config, errors)
        homography = config.get("homography_image_to_bev")
        if homography is not None:
            try:
                validate_homography(homography)
            except GeometryConfigError as exc:
                errors.append(str(exc))
        for area_name in ["parking_area", "road_area", "gate_queue_area", "ignore_area"]:
            _validate_area(config, area_name, errors)
        _validate_bays(config, errors)
        _validate_thresholds(config, errors)
    except KeyError as exc:
        errors.append(f"MISSING_REQUIRED_FIELD:{exc.args[0]}")
    return errors


def assert_valid_roi_config(config: dict[str, Any]) -> None:
    errors = validate_roi_config(config)
    if errors:
        raise GeometryConfigError(";".join(errors))


def _require(config: dict[str, Any], key: str) -> None:
    if key not in config or config[key] in {None, ""}:
        raise KeyError(key)


def _validate_image_size(config: dict[str, Any], errors: list[str]) -> None:
    image_size = config.get("image_size")
    if not isinstance(image_size, dict):
        errors.append("IMAGE_SIZE_MISSING_OR_INVALID")
        return
    for key in ["width", "height"]:
        value = image_size.get(key)
        if not isinstance(value, (int, float)) or not math.isfinite(float(value)) or float(value) <= 0:
            errors.append(f"IMAGE_SIZE_{key.upper()}_INVALID")


def _validate_area(config: dict[str, Any], area_name: str, errors: list[str]) -> None:
    area = config.get(area_name)
    if not isinstance(area, dict):
        errors.append(f"{area_name.upper()}_MISSING_OR_INVALID")
        return
    if area.get("coordinate_space") not in VALID_SPACES:
        errors.append(f"{area_name.upper()}_COORDINATE_SPACE_INVALID")
    polygons = area.get("polygons")
    if not isinstance(polygons, list):
        errors.append(f"{area_name.upper()}_POLYGONS_INVALID")
        return
    for index, polygon in enumerate(polygons):
        try:
            as_polygon(polygon)
        except GeometryConfigError as exc:
            errors.append(f"{area_name.upper()}_POLYGON_{index}_{exc}")


def _validate_bays(config: dict[str, Any], errors: list[str]) -> None:
    bays = config.get("parking_bays")
    if not isinstance(bays, list):
        errors.append("PARKING_BAYS_MISSING_OR_INVALID")
        return
    seen_bay_ids = set()
    for index, bay in enumerate(bays):
        if not isinstance(bay, dict):
            errors.append(f"PARKING_BAY_{index}_INVALID")
            continue
        bay_id = bay.get("bay_id")
        if not bay_id:
            errors.append(f"PARKING_BAY_{index}_MISSING_ID")
        elif bay_id in seen_bay_ids:
            errors.append(f"PARKING_BAY_{index}_DUPLICATE_ID")
        seen_bay_ids.add(bay_id)
        if "enabled" in bay and not isinstance(bay.get("enabled"), bool):
            errors.append(f"PARKING_BAY_{index}_ENABLED_INVALID")
        for polygon_key in ["polygon_image", "polygon_bev"]:
            if bay.get(polygon_key) is None:
                continue
            try:
                as_polygon(bay[polygon_key])
            except GeometryConfigError as exc:
                errors.append(f"PARKING_BAY_{index}_{polygon_key.upper()}_{exc}")
        if bay.get("polygon_image") is None and bay.get("polygon_bev") is None:
            errors.append(f"PARKING_BAY_{index}_NO_POLYGON")
        if not isinstance(bay.get("adjacent_bay_ids", []), list):
            errors.append(f"PARKING_BAY_{index}_ADJACENCY_INVALID")


def _validate_thresholds(config: dict[str, Any], errors: list[str]) -> None:
    thresholds = config.get("thresholds")
    if not isinstance(thresholds, dict):
        errors.append("THRESHOLDS_MISSING_OR_INVALID")
        return
    required = [
        "ignore_overlap_ratio",
        "gate_queue_overlap_ratio",
        "road_overlap_ratio",
        "two_bay_each_overlap_ratio",
        "two_bay_total_overlap_ratio",
        "in_bay_overlap_ratio",
        "minor_overrun_primary_bay_ratio",
        "minor_overrun_second_bay_max_ratio",
        "nose_tail_overhang_max_outside_ratio",
        "allow_bbox_road_positive",
        "allow_bbox_two_bay_positive",
    ]
    for key in required:
        if key not in thresholds:
            errors.append(f"THRESHOLD_{key}_MISSING")
            continue
        value = thresholds[key]
        if key.startswith("allow_bbox"):
            if not isinstance(value, bool):
                errors.append(f"THRESHOLD_{key}_INVALID")
        elif not isinstance(value, (int, float)) or not math.isfinite(float(value)) or not 0 <= float(value) <= 1:
            errors.append(f"THRESHOLD_{key}_INVALID")
