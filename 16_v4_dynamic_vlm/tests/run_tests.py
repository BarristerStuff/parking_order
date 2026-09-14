#!/usr/bin/env python3
"""No-pytest regression tests for the V4 evaluator contract."""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
V4_ROOT = HERE.parent
sys.path.insert(0, str(V4_ROOT))

from evaluator.decision import classify_response, parse_model_response  # noqa: E402
from evaluator.metrics import cache_match_status, evaluate_dataset, rate, wilson_interval  # noqa: E402


class DecisionContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        with (HERE / "fixtures" / "decision_cases.json").open(encoding="utf-8") as handle:
            cls.cases = json.load(handle)

    def test_frozen_decision_fixtures(self) -> None:
        for case in self.cases:
            with self.subTest(case=case["name"]):
                result = classify_response(case["response"], case["expected_target_ids"])
                if "expected_decision" in case:
                    self.assertEqual(result["targets"][0]["decision"], case["expected_decision"])
                    self.assertEqual(result["targets"][0]["reason"], case["expected_reason"])
                if "expected_image_decision" in case:
                    self.assertEqual(result["image_decision"], case["expected_image_decision"])
                if "expected_protocol_status" in case:
                    self.assertEqual(result["protocol_status"], case["expected_protocol_status"])
                    issue_codes = {issue["code"] for issue in result["protocol_issues"]}
                    self.assertIn(case["expected_issue"], issue_codes)

    def test_unknown_top_level_field_is_protocol_failure(self) -> None:
        response = {"targets": [], "reasoning": "not allowed"}
        result = classify_response(response, [])
        self.assertEqual(result["protocol_status"], "protocol_failure")
        self.assertIn("UNKNOWN_FIELD", {issue["code"] for issue in result["protocol_issues"]})

    def test_protocol_failure_does_not_become_negative(self) -> None:
        result = classify_response("not-json", ["local_1"])
        self.assertEqual(result["protocol_status"], "protocol_failure")
        self.assertEqual(result["image_decision"], "uncertain")
        self.assertFalse(result["alert"])


class MetricContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        with (HERE / "fixtures" / "evaluation_case.json").open(encoding="utf-8") as handle:
            fixture = json.load(handle)
        cls.references = fixture["references"]
        cls.predictions = fixture["predictions"]
        cls.metrics = evaluate_dataset(cls.references, cls.predictions)

    def test_image_alert_denominator_keeps_uncertain_and_protocol_failure(self) -> None:
        confusion = self.metrics["image"]["alert_confusion"]
        self.assertEqual((confusion["tp"], confusion["fp"], confusion["tn"], confusion["fn"]), (1, 1, 2, 2))
        self.assertEqual(confusion["recall"]["denominator"], 3)
        self.assertEqual(confusion["fpr"]["denominator"], 3)

    def test_image_semantic_confusion_and_coverage_are_separate(self) -> None:
        semantic = self.metrics["image"]["semantic_confusion"]
        self.assertEqual((semantic["tp"], semantic["fp"], semantic["tn"], semantic["fn"]), (1, 1, 1, 1))
        coverage = self.metrics["image"]["decisive_coverage"]
        self.assertEqual((coverage["numerator"], coverage["denominator"]), (4, 6))

    def test_vehicle_subtypes_and_detector_diagnostics(self) -> None:
        vehicle = self.metrics["vehicle"]
        self.assertEqual(vehicle["road_positive_alert_recall"]["numerator"], 1)
        self.assertEqual(vehicle["road_positive_alert_recall"]["denominator"], 2)
        self.assertEqual(vehicle["two_bay_positive_alert_recall"]["numerator"], 0)
        self.assertEqual(vehicle["two_bay_positive_alert_recall"]["denominator"], 1)
        self.assertEqual(vehicle["line_minor_nose_tail_fpr"]["numerator"], 1)
        self.assertEqual(vehicle["gate_queue_fpr"]["numerator"], 0)
        self.assertEqual(self.metrics["detector"]["detector_miss"]["count"], 1)
        self.assertEqual(self.metrics["detector"]["duplicates"]["count"], 1)
        self.assertEqual(self.metrics["detector"]["false_detections"]["count"], 1)

    def test_protocol_failures_are_reported_and_stay_in_vehicle_denominator(self) -> None:
        self.assertEqual(self.metrics["image"]["protocol_failure_rate"]["numerator"], 2)
        self.assertEqual(self.metrics["image"]["protocol_failure_rate"]["denominator"], 8)
        self.assertEqual(self.metrics["vehicle"]["protocol_failure_rate"]["numerator"], 2)
        self.assertEqual(self.metrics["vehicle"]["protocol_failure_rate"]["denominator"], 10)
        self.assertTrue(any(error["category"] == "protocol_failure" for error in self.metrics["errors"]))

    def test_uncertain_and_disputed_gt_are_excluded_but_reported(self) -> None:
        image = self.metrics["image"]
        self.assertEqual(image["gt_uncertain_count"], 1)
        self.assertEqual(image["gt_disputed_count"], 1)
        self.assertEqual(image["gt_uncertain_alert_rate"]["numerator"], 1)
        self.assertEqual(image["gt_disputed_alert_rate"]["numerator"], 0)
        self.assertTrue(any(error["category"] == "reference_disputed" for error in self.metrics["errors"]))

    def test_cache_matching_is_explicit(self) -> None:
        ref = next(item for item in self.references if item["media_id"] == "img_cache_mismatch")
        pred = next(item for item in self.predictions if item["media_id"] == "img_cache_mismatch")
        self.assertEqual(cache_match_status(ref, pred), "mismatch")
        self.assertEqual(self.metrics["image"]["protocol_failure_rate"]["numerator"], 2)
        self.assertTrue(any(issue["code"] == "CACHE_MISMATCH" for issue in self.metrics["join_issues"]))

    def test_zero_denominator_is_null(self) -> None:
        empty = rate(0, 0)
        self.assertIsNone(empty["value"])
        self.assertIsNone(empty["wilson_95"])
        self.assertIsNone(wilson_interval(0, 0))
        no_positive = evaluate_dataset(
            [{"media_id": "only_negative", "group": "x", "label": "negative", "vehicles": [{"target_id": "v", "label": "negative_ordinary_bay", "negative_category": "ordinary_bay"}]}],
            [{"media_id": "only_negative", "image_decision": "negative", "protocol_status": "ok", "targets": [{"target_id": "v", "decision": "negative", "protocol_status": "ok"}]}],
        )
        self.assertIsNone(no_positive["vehicle"]["road_positive_alert_recall"]["value"])
        self.assertEqual(no_positive["vehicle"]["road_positive_alert_recall"]["denominator"], 0)


if __name__ == "__main__":
    suite = unittest.defaultTestLoader.loadTestsFromModule(sys.modules[__name__])
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    raise SystemExit(0 if result.wasSuccessful() else 1)
