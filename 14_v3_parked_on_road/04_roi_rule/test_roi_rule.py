import copy
import json
from pathlib import Path

from roi_rule import aggregate_image_decision, evaluate_vehicle_in_roi


ROOT = Path(__file__).resolve().parents[1]


def load_config():
    with open(ROOT / "02_roi_config" / "example_route_roi.json") as file_handle:
        return json.load(file_handle)


def vehicle(vehicle_id, polygon, **extra):
    payload = {"media_id": "synthetic", "vehicle_id": vehicle_id, "footprint_polygon_image": polygon}
    payload.update(extra)
    return payload


def test_positive_road_with_explicit_footprint():
    config = load_config()
    decision = evaluate_vehicle_in_roi(vehicle("road_car", [[600, 150], [850, 150], [850, 360], [600, 360]]), config)
    assert decision.label == "positive_road"
    assert decision.reason_code == "ROAD_AREA_OCCUPANCY"


def test_gate_queue_overrides_road_positive():
    config = load_config()
    decision = evaluate_vehicle_in_roi(vehicle("queue_car", [[600, 440], [850, 440], [850, 530], [600, 530]]), config)
    assert decision.label == "negative_gate_queue"


def test_positive_two_adjacent_bays():
    config = load_config()
    decision = evaluate_vehicle_in_roi(vehicle("two_bay_car", [[220, 150], [430, 150], [430, 450], [220, 450]]), config)
    assert decision.label == "positive_two_bays"
    assert decision.reason_code == "TWO_ADJACENT_BAYS_OCCUPANCY"


def test_single_line_touch_is_negative():
    config = load_config()
    decision = evaluate_vehicle_in_roi(vehicle("line_touch", [[120, 150], [325, 150], [325, 450], [120, 450]]), config)
    assert decision.label == "negative_line_touch_or_minor_overrun"


def test_nose_tail_overhang_is_negative_when_hint_present():
    config = load_config()
    decision = evaluate_vehicle_in_roi(
        vehicle("overhang", [[120, 80], [280, 80], [280, 450], [120, 450]], overhang_type="nose_tail"), config
    )
    assert decision.label == "negative_nose_tail_overhang"


def test_bbox_only_road_evidence_is_uncertain_by_default():
    config = load_config()
    payload = {"media_id": "synthetic", "vehicle_id": "bbox_only", "bbox_xyxy": [600, 150, 850, 360]}
    decision = evaluate_vehicle_in_roi(payload, config)
    assert decision.label == "uncertain"
    assert decision.reason_code == "BBOX_ONLY_ROAD_EVIDENCE"


def test_bbox_positive_can_be_explicitly_enabled_for_prototypes():
    config = load_config()
    enabled_config = copy.deepcopy(config)
    enabled_config["thresholds"]["allow_bbox_road_positive"] = True
    payload = {"media_id": "synthetic", "vehicle_id": "bbox_only", "bbox_xyxy": [600, 150, 850, 360]}
    decision = evaluate_vehicle_in_roi(payload, enabled_config)
    assert decision.label == "positive_road"


def test_image_aggregation_or_logic_and_uncertain_non_alert():
    config = load_config()
    positive = evaluate_vehicle_in_roi(vehicle("road_car", [[600, 150], [850, 150], [850, 360], [600, 360]]), config)
    negative = evaluate_vehicle_in_roi(vehicle("bay_car", [[120, 150], [280, 150], [280, 450], [120, 450]]), config)
    image_decision = aggregate_image_decision([negative, positive])
    assert image_decision.image_label == "positive"
    assert image_decision.positive_vehicle_ids == ["road_car"]

    uncertain = evaluate_vehicle_in_roi({"media_id": "synthetic", "vehicle_id": "unknown"}, config)
    uncertain_image_decision = aggregate_image_decision([negative, uncertain])
    assert uncertain_image_decision.image_label == "uncertain"
