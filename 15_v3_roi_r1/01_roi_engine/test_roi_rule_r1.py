import copy

from roi_rule_r1 import aggregate_image_decision, evaluate_vehicle_in_roi


def base_config(space="image", homography=None):
    polygon_suffix = "polygon_image" if space == "image" else "polygon_bev"
    null_suffix = "polygon_bev" if space == "image" else "polygon_image"
    return {
        "schema_version": "vehicle_parked_on_road_v3_roi_r1_1.0",
        "camera_id": "synthetic_camera",
        "route_id": "synthetic_route",
        "image_size": {"width": 1000, "height": 600},
        "coordinate_space": space,
        "homography_image_to_bev": homography,
        "parking_bays": [
            {"bay_id": "bay_01", polygon_suffix: [[100, 100], [300, 100], [300, 500], [100, 500]], null_suffix: None, "adjacent_bay_ids": ["bay_02"], "enabled": True},
            {"bay_id": "bay_02", polygon_suffix: [[300, 100], [500, 100], [500, 500], [300, 500]], null_suffix: None, "adjacent_bay_ids": ["bay_01"], "enabled": True},
        ],
        "parking_area": {"coordinate_space": space, "polygons": [[[100, 100], [500, 100], [500, 500], [100, 500]]]},
        "road_area": {"coordinate_space": space, "polygons": [[[520, 80], [980, 80], [980, 540], [520, 540]]]},
        "gate_queue_area": {"coordinate_space": space, "polygons": [[[520, 420], [980, 420], [980, 540], [520, 540]]]},
        "ignore_area": {"coordinate_space": space, "polygons": [[[0, 0], [60, 0], [60, 600], [0, 600]]]},
        "thresholds": {
            "ignore_overlap_ratio": 0.60,
            "gate_queue_overlap_ratio": 0.50,
            "road_overlap_ratio": 0.65,
            "two_bay_each_overlap_ratio": 0.25,
            "two_bay_total_overlap_ratio": 0.70,
            "in_bay_overlap_ratio": 0.80,
            "minor_overrun_primary_bay_ratio": 0.65,
            "minor_overrun_second_bay_max_ratio": 0.20,
            "nose_tail_overhang_max_outside_ratio": 0.20,
            "allow_bbox_road_positive": False,
            "allow_bbox_two_bay_positive": False,
        },
    }


def vehicle(vehicle_id, footprint, coordinate_space="image", source="segmentation_mask", **extra):
    payload = {"media_id": "synthetic", "vehicle_id": vehicle_id, "footprint": footprint, "coordinate_space": coordinate_space, "footprint_source": source}
    payload.update(extra)
    return payload


def test_image_footprint_image_roi_road_positive():
    decision = evaluate_vehicle_in_roi(vehicle("road", [[600, 150], [850, 150], [850, 360], [600, 360]]), base_config("image"))
    assert decision.label == "positive_road"
    assert decision.coordinate_space == "image"


def test_image_footprint_image_roi_two_bay_positive():
    decision = evaluate_vehicle_in_roi(vehicle("two_bay", [[220, 150], [430, 150], [430, 450], [220, 450]]), base_config("image"))
    assert decision.label == "positive_two_bays"


def test_image_footprint_image_roi_line_touch_negative():
    decision = evaluate_vehicle_in_roi(vehicle("line_touch", [[120, 150], [325, 150], [325, 450], [120, 450]]), base_config("image"))
    assert decision.label == "negative_line_touch_or_minor_overrun"


def test_image_footprint_image_roi_nose_tail_overhang_negative():
    decision = evaluate_vehicle_in_roi(vehicle("overhang", [[120, 80], [280, 80], [280, 450], [120, 450]], overhang_evidence="runtime_geometry_nose_tail"), base_config("image"))
    assert decision.label == "negative_nose_tail_overhang"


def test_gate_queue_priority_over_road_positive():
    decision = evaluate_vehicle_in_roi(vehicle("queue", [[600, 440], [850, 440], [850, 530], [600, 530]]), base_config("image"))
    assert decision.label == "negative_gate_queue"


def test_ignore_priority():
    decision = evaluate_vehicle_in_roi(vehicle("ignore", [[10, 100], [50, 100], [50, 500], [10, 500]]), base_config("image"))
    assert decision.label == "ignore"


def test_bbox_only_road_default_uncertain():
    decision = evaluate_vehicle_in_roi({"media_id": "synthetic", "vehicle_id": "bbox_road", "bbox_xyxy": [600, 150, 850, 360]}, base_config("image"))
    assert decision.label == "uncertain"
    assert decision.reason_code == "BBOX_ONLY_ROAD_EVIDENCE"


def test_bbox_only_two_bay_default_uncertain():
    decision = evaluate_vehicle_in_roi({"media_id": "synthetic", "vehicle_id": "bbox_two_bay", "bbox_xyxy": [220, 150, 430, 450]}, base_config("image"))
    assert decision.label == "uncertain"
    assert decision.reason_code == "BBOX_ONLY_TWO_BAY_EVIDENCE"


def test_bev_footprint_bev_roi_road_positive():
    decision = evaluate_vehicle_in_roi(vehicle("bev_road", [[600, 150], [850, 150], [850, 360], [600, 360]], "bev", "bev_footprint"), base_config("bev"))
    assert decision.label == "positive_road"
    assert decision.coordinate_space == "bev"


def test_image_footprint_only_bev_roi_without_homography_uncertain():
    decision = evaluate_vehicle_in_roi(vehicle("needs_h", [[600, 150], [850, 150], [850, 360], [600, 360]], "image"), base_config("bev"))
    assert decision.label == "uncertain"
    assert decision.reason_code == "COORDINATE_SPACE_MISMATCH_NO_HOMOGRAPHY"


def test_image_footprint_bev_roi_with_homography_transforms_and_scores():
    matrix = [[0.5, 0, 0], [0, 0.5, 0], [0, 0, 1]]
    config = base_config("bev", homography=matrix)
    decision = evaluate_vehicle_in_roi(vehicle("h_road", [[1200, 300], [1700, 300], [1700, 720], [1200, 720]], "image"), config)
    assert decision.label == "positive_road"
    assert decision.coordinate_space == "bev"


def test_wrong_coordinate_space_uncertain():
    decision = evaluate_vehicle_in_roi(vehicle("bad_space", [[600, 150], [850, 150], [850, 360], [600, 360]], "world"), base_config("image"))
    assert decision.label == "uncertain"
    assert decision.reason_code == "INVALID_COORDINATE_SPACE"


def test_overlapping_road_polygons_do_not_double_count():
    config = base_config("image")
    config["road_area"] = {"coordinate_space": "image", "polygons": [[[520, 80], [800, 80], [800, 540], [520, 540]], [[700, 80], [980, 80], [980, 540], [700, 540]]]}
    decision = evaluate_vehicle_in_roi(vehicle("road", [[600, 150], [850, 150], [850, 360], [600, 360]]), config)
    assert decision.label == "positive_road"
    assert decision.area_ratios["road"] == 1.0


def test_non_convex_config_polygon_safe_uncertain():
    config = base_config("image")
    config["road_area"] = {"coordinate_space": "image", "polygons": [[[520, 80], [980, 80], [700, 200], [980, 540], [520, 540]]]}
    decision = evaluate_vehicle_in_roi(vehicle("road", [[600, 150], [850, 150], [850, 360], [600, 360]]), config)
    assert decision.label == "uncertain"
    assert decision.reason_code == "CONFIG_VALIDATION_ERROR"


def test_empty_polygon_safe_uncertain():
    config = base_config("image")
    config["ignore_area"] = {"coordinate_space": "image", "polygons": [[]]}
    decision = evaluate_vehicle_in_roi(vehicle("road", [[600, 150], [850, 150], [850, 360], [600, 360]]), config)
    assert decision.label == "uncertain"
    assert decision.reason_code == "CONFIG_VALIDATION_ERROR"


def test_multi_vehicle_or_logic():
    config = base_config("image")
    negative = evaluate_vehicle_in_roi(vehicle("bay", [[120, 150], [280, 150], [280, 450], [120, 450]]), config)
    positive = evaluate_vehicle_in_roi(vehicle("road", [[600, 150], [850, 150], [850, 360], [600, 360]]), config)
    image = aggregate_image_decision([negative, positive])
    assert image.image_label == "positive"
    assert image.positive_vehicle_ids == ["road"]


def test_only_uncertain_no_positive_image_uncertain():
    config = base_config("image")
    negative = evaluate_vehicle_in_roi(vehicle("bay", [[120, 150], [280, 150], [280, 450], [120, 450]]), config)
    uncertain = evaluate_vehicle_in_roi({"media_id": "synthetic", "vehicle_id": "unknown"}, config)
    image = aggregate_image_decision([negative, uncertain])
    assert image.image_label == "uncertain"


def test_legacy_bev_field_uses_bev_bay_polygons():
    config = base_config("bev")
    decision = evaluate_vehicle_in_roi({"media_id": "synthetic", "vehicle_id": "legacy_bev", "footprint_polygon_bev": [[220, 150], [430, 150], [430, 450], [220, 450]]}, config)
    assert decision.label == "positive_two_bays"
    assert decision.footprint_source == "bev_footprint"


def run_all_tests():
    count = 0
    for name, value in sorted(globals().items()):
        if name.startswith("test_") and callable(value):
            value()
            count += 1
    return count


if __name__ == "__main__":
    print(f"TEST_ROI_RULE_R1_PASSED={run_all_tests()}")
