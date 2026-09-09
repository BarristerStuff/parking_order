#!/usr/bin/env python3
"""Run the frozen v2 five-question VLM protocol on opaque DEV-only inputs."""

from __future__ import annotations

import argparse
import json
import os
import re
import statistics
import threading
import time
import urllib.request
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from pathlib import Path
from typing import Any

from crop_ground_band import (
    crop_ground_band,
    encode_jpeg_base64,
    eligible_detections,
    validate_image_binding,
)


ROOT = Path("/home/yanbo/net_vlm_parking_optimization")
V2 = ROOT / "12_v2_not_in_bay"
TOOLS = V2 / "02_tools"
DEBUG = V2 / "03_debug"
OUTPUT = V2 / "04_vlm_dev_baseline"
DATASET_ROOT = Path("/home/yanbo/net_vlm_xunjian_dataset").resolve()

CONFIG = TOOLS / "v2_dev_baseline_config.json"
PROMPT = TOOLS / "prompt_v2_perception.txt"
SELECTION_PROTOCOL = TOOLS / "crop_selection_protocol.json"
BINDING = DEBUG / "v2_step2_binding.json"
INFERENCE_INPUT = DEBUG / "v2_dev_inference_input.jsonl"
CACHE_VALIDATION = DEBUG / "v2_dev_detector_cache_validation.json"
TOOL_FREEZE = DEBUG / "v2_step2_tool_freeze.json"

PREFLIGHT = OUTPUT / "preflight.json"
PREDICTIONS = OUTPUT / "predictions.jsonl"
RUN_SUMMARY = OUTPUT / "run_summary.json"

EXPECTED_INPUT_FIELDS = {"sample_token", "image_path", "image_sha256", "detections"}
EXPECTED_RESPONSE_KEYS = {
    "line_under_center",
    "line_left",
    "line_right",
    "markings_visible",
    "on_aisle",
}
ANSWER_VALUES = {"yes", "no", "unclear"}


def sha256_file(path: Path) -> str:
    import hashlib

    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def assert_sidecar(path: Path) -> None:
    sidecar = path.with_name(path.name + ".sha256")
    expected = f"{sha256_file(path)}  {path.name}\n"
    if not sidecar.is_file() or sidecar.read_text(encoding="utf-8") != expected:
        raise SystemExit(f"SHA-256 sidecar mismatch: {path}")


def atomic_text(path: Path, content: str) -> None:
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(content, encoding="utf-8", newline="\n")
    os.replace(temporary, path)


def read_inference_input(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            row = json.loads(line)
            if not isinstance(row, dict) or set(row) != EXPECTED_INPUT_FIELDS:
                raise SystemExit(f"inference input schema/leakage violation on line {number}")
            rows.append(row)
    if len(rows) != 238 or len({row["sample_token"] for row in rows}) != 238:
        raise SystemExit("inference input must contain exactly 238 unique DEV opaque tokens")
    for row in rows:
        path = Path(row["image_path"]).resolve()
        if row["sample_token"] != row["image_sha256"] or DATASET_ROOT not in path.parents:
            raise SystemExit("inference input violates opaque-token or DEV-root binding")
        if not path.is_file() or sha256_file(path) != row["image_sha256"]:
            raise SystemExit(f"inference image binding mismatch: {path}")
        if not isinstance(row["detections"], list):
            raise SystemExit("detections must be a list")
    return rows


def parse_response(raw_response: str) -> dict[str, str]:
    value = raw_response.strip()
    fence = chr(96) * 3
    fenced = re.fullmatch(
        re.escape(fence) + r"(?:json)?\s*(.*?)\s*" + re.escape(fence),
        value,
        flags=re.I | re.S,
    )
    if fenced:
        value = fenced.group(1).strip()
    parsed = json.loads(value)
    if not isinstance(parsed, dict) or set(parsed) != EXPECTED_RESPONSE_KEYS:
        raise ValueError("response keys do not exactly match v2 perception schema")
    normalized = {key: str(parsed[key]).strip().lower() for key in EXPECTED_RESPONSE_KEYS}
    if any(answer not in ANSWER_VALUES for answer in normalized.values()):
        raise ValueError("response value outside yes/no/unclear")
    return normalized


def post_json(endpoint: str, payload: dict[str, Any], timeout: float) -> tuple[int, dict[str, Any]]:
    request = urllib.request.Request(
        endpoint,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        body = response.read()
        status = int(response.status)
    value = json.loads(body)
    if not isinstance(value, dict):
        raise ValueError("Ollama HTTP response must be a JSON object")
    return status, value


def ollama_tags(config: dict[str, Any]) -> list[str]:
    endpoint = str(config["endpoint"])
    if not endpoint.endswith("/api/generate"):
        raise SystemExit("unexpected Ollama endpoint")
    tags_endpoint = endpoint.removesuffix("/api/generate") + "/api/tags"
    request = urllib.request.Request(tags_endpoint, method="GET")
    with urllib.request.urlopen(request, timeout=15) as response:
        value = json.loads(response.read())
    names = [str(item.get("name", "")) for item in value.get("models", [])]
    if config["model"] not in names:
        raise SystemExit(f"required model unavailable from /api/tags: {config['model']}")
    return names


def crop_decision(perception: dict[str, str]) -> str:
    if perception["line_under_center"] == "yes":
        return "spanning"
    if (
        perception["markings_visible"] == "yes"
        and perception["line_left"] == "no"
        and perception["line_right"] == "no"
        and perception["on_aisle"] == "yes"
    ):
        return "outside"
    if (
        perception["line_under_center"] == "no"
        and perception["line_left"] == "yes"
        and perception["line_right"] == "yes"
    ):
        return "in_bay"
    return "uncertain"


def call_crop(image_b64: str, config: dict[str, Any], prompt: str) -> dict[str, Any]:
    payload = {
        "model": config["model"],
        "prompt": prompt,
        "images": [image_b64],
        **config["ollama_request"],
    }
    attempts: list[dict[str, Any]] = []
    max_attempts = int(config["max_retries"]) + 1
    for attempt_number in range(1, max_attempts + 1):
        started = time.perf_counter()
        try:
            http_status, response = post_json(
                config["endpoint"], payload, float(config["timeout_seconds"])
            )
            raw = response.get("response", "")
            if not isinstance(raw, str):
                raise ValueError("Ollama response field is not a string")
            perception = parse_response(raw)
            attempts.append(
                {
                    "attempt": attempt_number,
                    "http_status": http_status,
                    "http_success": True,
                    "schema_success": True,
                    "latency_seconds": round(time.perf_counter() - started, 6),
                    "raw_response": raw,
                    "error": "",
                    "ollama_total_duration_ns": response.get("total_duration"),
                    "ollama_load_duration_ns": response.get("load_duration"),
                    "ollama_prompt_eval_count": response.get("prompt_eval_count"),
                    "ollama_eval_count": response.get("eval_count"),
                }
            )
            return {
                "status": "ok",
                "perception": perception,
                "attempts": attempts,
                "final_attempt": attempt_number,
            }
        except Exception as exc:
            attempts.append(
                {
                    "attempt": attempt_number,
                    "http_status": None,
                    "http_success": False,
                    "schema_success": False,
                    "latency_seconds": round(time.perf_counter() - started, 6),
                    "raw_response": "",
                    "error": f"{type(exc).__name__}: {exc}",
                    "ollama_total_duration_ns": None,
                    "ollama_load_duration_ns": None,
                    "ollama_prompt_eval_count": None,
                    "ollama_eval_count": None,
                }
            )
            if attempt_number < max_attempts:
                time.sleep(float(attempt_number))
    return {
        "status": "protocol_failure",
        "perception": None,
        "attempts": attempts,
        "final_attempt": max_attempts,
    }


def infer_one(row: dict[str, Any], config: dict[str, Any], prompt: str) -> dict[str, Any]:
    started = time.perf_counter()
    image_path = Path(row["image_path"])
    try:
        image = validate_image_binding(image_path, row["image_sha256"])
        selected, rejected = eligible_detections(
            row["detections"], image.width, image.height, config
        )
        if not selected:
            return {
                "sample_token": row["sample_token"],
                "status": "no_eligible_detection",
                "model_label": "uncertain",
                "frame_decision": "uncertain",
                "logical_json_success": True,
                "eligible_detection_count": 0,
                "rejected_detection_count": len(rejected),
                "vehicle_results": [],
                "physical_request_count": 0,
                "logical_crop_request_count": 0,
                "latency_seconds": round(time.perf_counter() - started, 6),
                "error": "",
            }
        vehicle_results: list[dict[str, Any]] = []
        saw_protocol_failure = False
        for rank, detection in enumerate(selected, start=1):
            crop, crop_metadata = crop_ground_band(image, detection, config)
            encoded, jpeg_bytes = encode_jpeg_base64(
                crop, int(config["preprocess"]["jpeg_quality"])
            )
            call = call_crop(encoded, config, prompt)
            vehicle = {
                "candidate_rank": rank,
                "crop": crop_metadata,
                "jpeg_bytes": jpeg_bytes,
                "call": call,
                "vehicle_decision": (
                    crop_decision(call["perception"]) if call["status"] == "ok" else "uncertain"
                ),
            }
            vehicle_results.append(vehicle)
            if call["status"] != "ok":
                saw_protocol_failure = True
                continue
            if vehicle["vehicle_decision"] in {"spanning", "outside"}:
                return {
                    "sample_token": row["sample_token"],
                    "status": "ok",
                    "model_label": "positive",
                    "frame_decision": vehicle["vehicle_decision"],
                    "logical_json_success": not saw_protocol_failure,
                    "eligible_detection_count": len(selected),
                    "rejected_detection_count": len(rejected),
                    "vehicle_results": vehicle_results,
                    "physical_request_count": sum(
                        len(item["call"]["attempts"]) for item in vehicle_results
                    ),
                    "logical_crop_request_count": len(vehicle_results),
                    "latency_seconds": round(time.perf_counter() - started, 6),
                    "error": "",
                }
        if saw_protocol_failure:
            final_status, label, decision, error = (
                "protocol_failure",
                "uncertain",
                "uncertain",
                "at least one selected crop exhausted its JSON/transport retries",
            )
        elif all(item["vehicle_decision"] == "in_bay" for item in vehicle_results):
            final_status, label, decision, error = "ok", "negative", "in_bay", ""
        else:
            final_status, label, decision, error = "ok", "uncertain", "uncertain", ""
        return {
            "sample_token": row["sample_token"],
            "status": final_status,
            "model_label": label,
            "frame_decision": decision,
            "logical_json_success": not saw_protocol_failure,
            "eligible_detection_count": len(selected),
            "rejected_detection_count": len(rejected),
            "vehicle_results": vehicle_results,
            "physical_request_count": sum(len(item["call"]["attempts"]) for item in vehicle_results),
            "logical_crop_request_count": len(vehicle_results),
            "latency_seconds": round(time.perf_counter() - started, 6),
            "error": error,
        }
    except Exception as exc:
        return {
            "sample_token": row["sample_token"],
            "status": "inference_failure",
            "model_label": "uncertain",
            "frame_decision": "uncertain",
            "logical_json_success": False,
            "eligible_detection_count": 0,
            "rejected_detection_count": 0,
            "vehicle_results": [],
            "physical_request_count": 0,
            "logical_crop_request_count": 0,
            "latency_seconds": round(time.perf_counter() - started, 6),
            "error": f"{type(exc).__name__}: {exc}",
        }


def build_preflight(config: dict[str, Any], rows: list[dict[str, Any]], tags: list[str]) -> dict[str, Any]:
    cache_validation = json.loads(CACHE_VALIDATION.read_text(encoding="utf-8"))
    if cache_validation.get("status") != "valid" or cache_validation.get("error_count") != 0:
        raise SystemExit("detector cache validation gate failed")
    binding = json.loads(BINDING.read_text(encoding="utf-8"))
    if binding.get("config_sha256") != sha256_file(CONFIG):
        raise SystemExit("baseline binding/config hash mismatch")
    if binding.get("prompt_sha256") != sha256_file(PROMPT):
        raise SystemExit("baseline binding/prompt hash mismatch")
    if config.get("model") != "qwen3.5:4b" or int(config.get("max_workers", 0)) > 2:
        raise SystemExit("model/concurrency guard failed")
    if config.get("allowed_split") != "DEV":
        raise SystemExit("split guard failed")
    tool_freeze = json.loads(TOOL_FREEZE.read_text(encoding="utf-8"))
    expected_tools = {
        "vlm_perception.py": sha256_file(Path(__file__).resolve()),
        "crop_ground_band.py": sha256_file(TOOLS / "crop_ground_band.py"),
        "crop_selection_protocol.json": sha256_file(SELECTION_PROTOCOL),
        "evaluate.py": sha256_file(TOOLS / "evaluate.py"),
    }
    if tool_freeze.get("tool_sha256") != expected_tools:
        raise SystemExit("frozen Step 2 tool hash mismatch")
    return {
        "status": "valid",
        "error_count": 0,
        "stage": config["stage"],
        "model": config["model"],
        "ollama_tags_has_model": config["model"] in tags,
        "inference_input_count": len(rows),
        "inference_input_sha256": sha256_file(INFERENCE_INPUT),
        "config_sha256": sha256_file(CONFIG),
        "prompt_sha256": sha256_file(PROMPT),
        "crop_selection_protocol_sha256": sha256_file(SELECTION_PROTOCOL),
        "tool_freeze_sha256": sha256_file(TOOL_FREEZE),
        "detector_cache_validation_status": cache_validation["status"],
        "detector_cache_validation_error_count": cache_validation["error_count"],
        "max_ollama_concurrency": config["max_workers"],
        "model_requests_started": 0,
        "val_image_reads": 0,
        "holdout_image_reads": 0,
        "target_bbox_hint_present_in_inference_input": False,
    }


def physical_stats(result: dict[str, Any]) -> tuple[int, int]:
    attempts = [
        attempt
        for vehicle in result.get("vehicle_results", [])
        for attempt in vehicle["call"]["attempts"]
    ]
    return len(attempts), sum(bool(attempt["schema_success"]) for attempt in attempts)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check-only", action="store_true")
    args = parser.parse_args()

    required = [
        CONFIG, PROMPT, SELECTION_PROTOCOL, BINDING, INFERENCE_INPUT, CACHE_VALIDATION, TOOL_FREEZE,
    ]
    if not all(path.is_file() for path in required):
        raise SystemExit("required VLM input missing")
    for path in (CONFIG, PROMPT, SELECTION_PROTOCOL, INFERENCE_INPUT):
        assert_sidecar(path)
    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    rows = read_inference_input(INFERENCE_INPUT)
    tags = ollama_tags(config)
    preflight = build_preflight(config, rows, tags)
    OUTPUT.mkdir(parents=True, exist_ok=True)
    expected_preflight = json.dumps(preflight, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if PREFLIGHT.exists() and PREFLIGHT.read_text(encoding="utf-8") != expected_preflight:
        if PREDICTIONS.exists():
            raise SystemExit("refusing to replace differing VLM preflight after requests started")
        atomic_text(PREFLIGHT, expected_preflight)
    elif not PREFLIGHT.exists():
        atomic_text(PREFLIGHT, expected_preflight)
    if args.check_only:
        print(json.dumps({**preflight, "status": "check_ok"}, ensure_ascii=False, sort_keys=True))
        return

    if PREDICTIONS.exists() or RUN_SUMMARY.exists():
        raise SystemExit("refusing to rerun or overwrite an existing VLM baseline")

    lock = threading.Lock()
    completion: list[dict[str, Any]] = []
    logical_crop_requests = 0
    logical_crop_successes = 0
    physical_requests = 0
    physical_schema_successes = 0
    stop_reason = ""
    started = time.perf_counter()
    prompt = PROMPT.read_text(encoding="utf-8")
    iterator = iter(rows)
    with PREDICTIONS.open("x", encoding="utf-8", newline="\n") as output:
        with ThreadPoolExecutor(max_workers=int(config["max_workers"])) as pool:
            active: dict[Any, dict[str, Any]] = {}
            while len(active) < int(config["max_workers"]):
                try:
                    row = next(iterator)
                except StopIteration:
                    break
                active[pool.submit(infer_one, row, config, prompt)] = row
            while active:
                finished, _ = wait(active, return_when=FIRST_COMPLETED)
                for future in finished:
                    row = active.pop(future)
                    result = future.result()
                    if result["sample_token"] != row["sample_token"]:
                        raise SystemExit("runner returned an unexpected opaque token")
                    with lock:
                        output.write(json.dumps(result, ensure_ascii=False, sort_keys=True) + "\n")
                        output.flush()
                        os.fsync(output.fileno())
                    completion.append(result)
                    physical_count, physical_success = physical_stats(result)
                    physical_requests += physical_count
                    physical_schema_successes += physical_success
                    logical_crop_requests += int(result["logical_crop_request_count"])
                    if result["logical_json_success"]:
                        logical_crop_successes += int(result["logical_crop_request_count"])
                    elif int(result["logical_crop_request_count"]) > 0:
                        stop_reason = "LOGICAL_JSON_SCHEMA_SUCCESS_RATE_BELOW_95_PERCENT"
                    if result["status"] == "inference_failure":
                        stop_reason = "INFERENCE_INPUT_OR_OLLAMA_FAILURE"
                    if physical_requests and physical_schema_successes / physical_requests < 0.95:
                        stop_reason = "PHYSICAL_JSON_SCHEMA_SUCCESS_RATE_BELOW_95_PERCENT"
                    if logical_crop_requests and logical_crop_successes / logical_crop_requests < 0.95:
                        stop_reason = "LOGICAL_JSON_SCHEMA_SUCCESS_RATE_BELOW_95_PERCENT"
                    print(
                        f"V2_VLM_PROGRESS completed={len(completion)}/{len(rows)} "
                        f"token={result['sample_token'][:12]} status={result['status']} "
                        f"label={result['model_label']} physical={physical_count}",
                        flush=True,
                    )
                # When an immediate-stop condition fires, do not submit another
                # image.  Any request already in flight is allowed to finish and
                # is written to the audit JSONL rather than being silently lost.
                if not stop_reason:
                    while len(active) < int(config["max_workers"]):
                        try:
                            row = next(iterator)
                        except StopIteration:
                            break
                        active[pool.submit(infer_one, row, config, prompt)] = row

    completed_tokens = {result["sample_token"] for result in completion}
    if len(completed_tokens) != len(completion):
        raise SystemExit("duplicate opaque token in predictions")
    run_summary = {
        "status": "completed" if not stop_reason and len(completion) == len(rows) else "stopped",
        "stop_reason": stop_reason,
        "stage": config["stage"],
        "logical_image_count": len(rows),
        "completed_image_count": len(completion),
        "logical_crop_request_count": logical_crop_requests,
        "logical_crop_json_success_count": logical_crop_successes,
        "logical_crop_json_success_rate": (
            logical_crop_successes / logical_crop_requests if logical_crop_requests else None
        ),
        "physical_request_count": physical_requests,
        "physical_json_schema_success_count": physical_schema_successes,
        "physical_json_schema_success_rate": (
            physical_schema_successes / physical_requests if physical_requests else None
        ),
        "logical_latency_seconds": {
            "p50": statistics.median([result["latency_seconds"] for result in completion]) if completion else None,
            "p95": None,
        },
        "elapsed_seconds": round(time.perf_counter() - started, 6),
        "model": config["model"],
        "max_ollama_concurrency": config["max_workers"],
        "prompt_sha256": sha256_file(PROMPT),
        "config_sha256": sha256_file(CONFIG),
        "inference_input_sha256": sha256_file(INFERENCE_INPUT),
        "val_image_reads": 0,
        "holdout_image_reads": 0,
        "prompt_optimization": False,
        "preprocessing_optimization": False,
    }
    if completion:
        values = sorted(result["latency_seconds"] for result in completion)
        run_summary["logical_latency_seconds"]["p95"] = values[
            max(0, min(len(values) - 1, int((len(values) - 1) * 0.95 + 0.999999)))
        ]
    atomic_text(RUN_SUMMARY, json.dumps(run_summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    print(json.dumps(run_summary, ensure_ascii=False, sort_keys=True))
    if stop_reason:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
