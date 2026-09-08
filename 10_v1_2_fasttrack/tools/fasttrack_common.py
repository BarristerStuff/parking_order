#!/usr/bin/env python3
"""Shared frozen protocol implementation for parking_order_violation v1.2."""
from __future__ import annotations

import base64
import hashlib
import io
import json
import math
import os
import re
import threading
import time
import urllib.request
from pathlib import Path
from typing import Any

from PIL import Image

LABELS = {"positive", "negative", "uncertain"}
EVIDENCE_TYPES = {
    "outside_space", "multi_space", "severe_angle", "traffic_area",
    "normal", "gate_queue", "insufficient",
}
POSITIVE_EVIDENCE = {"outside_space", "multi_space", "severe_angle", "traffic_area"}
NEGATIVE_EVIDENCE = {"normal", "gate_queue"}
LANCZOS = getattr(getattr(Image, "Resampling", Image), "LANCZOS")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def encode_jpeg(image: Image.Image, quality: int) -> tuple[str, int]:
    buffer = io.BytesIO()
    image.save(buffer, format="JPEG", quality=quality, optimize=True)
    data = buffer.getvalue()
    return base64.b64encode(data).decode("ascii"), len(data)


def direct_resize(image: Image.Image, prep: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    width, height = int(prep["canvas_width"]), int(prep["canvas_height"])
    output = image.resize((width, height), LANCZOS)
    encoded, byte_count = encode_jpeg(output, int(prep["jpeg_quality"]))
    return encoded, {
        "mode": "direct_resize", "source_size": [image.width, image.height],
        "resized_size": [width, height], "canvas_size": [width, height],
        "padding": [0, 0, 0, 0], "jpeg_bytes": byte_count,
    }


def letterbox(image: Image.Image, prep: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    width, height = int(prep["canvas_width"]), int(prep["canvas_height"])
    scale = min(width / image.width, height / image.height)
    resized_width = max(1, min(width, int(round(image.width * scale))))
    resized_height = max(1, min(height, int(round(image.height * scale))))
    resized = image.resize((resized_width, resized_height), LANCZOS)
    color = tuple(int(x) for x in prep.get("letterbox_color", [0, 0, 0]))
    canvas = Image.new("RGB", (width, height), color)
    left = (width - resized_width) // 2
    top = (height - resized_height) // 2
    canvas.paste(resized, (left, top))
    encoded, byte_count = encode_jpeg(canvas, int(prep["jpeg_quality"]))
    return encoded, {
        "mode": "letterbox", "source_size": [image.width, image.height],
        "resized_size": [resized_width, resized_height], "canvas_size": [width, height],
        "padding": [left, top, width - resized_width - left, height - resized_height - top],
        "scale": scale, "jpeg_bytes": byte_count,
    }


def parse_model_response(text: str) -> dict[str, Any]:
    value = text.strip()
    fence = re.fullmatch(r"```(?:json)?\s*(.*?)\s*```", value, flags=re.I | re.S)
    if fence:
        value = fence.group(1).strip()
    obj = json.loads(value)
    if not isinstance(obj, dict):
        raise ValueError("response JSON must be an object")
    expected_keys = {"parking_order_violation", "evidence_type", "reason"}
    if set(obj) != expected_keys:
        raise ValueError(f"response keys do not exactly match schema: {sorted(obj)}")
    label = obj["parking_order_violation"]
    evidence = obj["evidence_type"]
    reason = obj["reason"]
    if label not in LABELS:
        raise ValueError(f"invalid label: {label!r}")
    if evidence not in EVIDENCE_TYPES:
        raise ValueError(f"invalid evidence_type: {evidence!r}")
    if not isinstance(reason, str):
        raise ValueError("reason must be a string")
    semantic_ok = (
        (label == "positive" and evidence in POSITIVE_EVIDENCE)
        or (label == "negative" and evidence in NEGATIVE_EVIDENCE)
        or (label == "uncertain" and evidence == "insufficient")
    )
    return {
        "label": label, "evidence_type": evidence, "reason": reason.strip(),
        "semantic_protocol_ok": semantic_ok,
    }


def post_json(url: str, payload: dict[str, Any], timeout: float) -> tuple[int, dict[str, Any]]:
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(request, timeout=timeout) as response:
        status = int(response.status)
        body = response.read()
    obj = json.loads(body)
    if not isinstance(obj, dict):
        raise ValueError("Ollama HTTP response is not an object")
    return status, obj


def run_view(image_b64: str, view_name: str, prompt: str, config: dict[str, Any]) -> dict[str, Any]:
    payload = {"model": config["model"], "prompt": prompt, "images": [image_b64], **config["ollama_request"]}
    started = time.perf_counter()
    attempt_errors: list[str] = []
    response_obj: dict[str, Any] | None = None
    http_status: int | None = None
    attempts = 0
    for attempt in range(int(config["max_retries"]) + 1):
        attempts += 1
        try:
            http_status, response_obj = post_json(config["endpoint"], payload, float(config["timeout_seconds"]))
            break
        except Exception as exc:
            attempt_errors.append(f"{type(exc).__name__}: {exc}")
            if attempt < int(config["max_retries"]):
                time.sleep(1.0)
    latency = round(time.perf_counter() - started, 6)
    if response_obj is None:
        return {
            "view_name": view_name, "status": "inference_failure", "http_status": http_status,
            "http_attempt_count": attempts, "http_errors": attempt_errors, "schema_success": False,
            "semantic_protocol_ok": False, "label": "", "evidence_type": "", "reason": "",
            "parse_error": "", "raw_response": "", "latency_seconds": latency,
        }
    raw_response = response_obj.get("response", "")
    try:
        parsed = parse_model_response(raw_response)
        status, parse_error, schema_success = "ok", "", True
    except Exception as exc:
        parsed = {"label": "", "evidence_type": "", "reason": "", "semantic_protocol_ok": False}
        status, parse_error, schema_success = "parse_failure", f"{type(exc).__name__}: {exc}", False
    return {
        "view_name": view_name, "status": status, "http_status": http_status,
        "http_attempt_count": attempts, "http_errors": attempt_errors, "schema_success": schema_success,
        **parsed, "parse_error": parse_error, "raw_response": raw_response,
        "latency_seconds": latency, "ollama_total_duration_ns": response_obj.get("total_duration"),
        "ollama_load_duration_ns": response_obj.get("load_duration"),
        "ollama_prompt_eval_count": response_obj.get("prompt_eval_count"),
        "ollama_eval_count": response_obj.get("eval_count"),
    }


def expand_box(box: list[float], factor: float, width: int, height: int) -> list[int]:
    x1, y1, x2, y2 = box
    cx, cy = (x1 + x2) / 2, (y1 + y2) / 2
    target_width, target_height = (x2 - x1) * factor, (y2 - y1) * factor
    left = max(0, int(math.floor(cx - target_width / 2)))
    top = max(0, int(math.floor(cy - target_height / 2)))
    right = min(width, int(math.ceil(cx + target_width / 2)))
    bottom = min(height, int(math.ceil(cy + target_height / 2)))
    if right <= left or bottom <= top:
        raise ValueError(f"invalid expanded crop: {[left, top, right, bottom]}")
    return [left, top, right, bottom]


class Detector:
    def __init__(self, config: dict[str, Any], output_dir: Path) -> None:
        detector_config = config["detector"]
        checkpoint = Path(detector_config["checkpoint"])
        actual_hash = sha256_file(checkpoint)
        if actual_hash != detector_config["checkpoint_sha256"]:
            raise SystemExit(f"detector checkpoint SHA-256 mismatch: {actual_hash}")
        os.environ.setdefault("YOLO_CONFIG_DIR", str(output_dir / ".ultralytics"))
        from ultralytics import YOLO
        self.model = YOLO(str(checkpoint))
        self.config = detector_config
        self.lock = threading.Lock()
        expected = {int(key): value for key, value in detector_config["classes"].items()}
        for class_id, name in expected.items():
            if self.model.names[class_id] != name:
                raise SystemExit(f"detector class mapping mismatch: {class_id}={self.model.names[class_id]!r}")

    def detect(self, image: Image.Image) -> tuple[list[dict[str, Any]], float]:
        started = time.perf_counter()
        with self.lock:
            result = self.model.predict(
                source=image, classes=[int(x) for x in self.config["classes"]],
                conf=float(self.config["confidence_threshold"]), imgsz=int(self.config["inference_size"]),
                device=self.config["device"], verbose=False, save=False,
            )[0]
        detections: list[dict[str, Any]] = []
        if result.boxes is not None:
            for xyxy, confidence, class_id in zip(
                result.boxes.xyxy.tolist(), result.boxes.conf.tolist(), result.boxes.cls.tolist()
            ):
                detections.append({
                    "bbox": [round(float(x), 3) for x in xyxy], "confidence": round(float(confidence), 6),
                    "class_id": int(class_id), "class_name": self.config["classes"][str(int(class_id))],
                })
        detections.sort(key=lambda item: item["confidence"], reverse=True)
        return detections, round(time.perf_counter() - started, 6)


def fuse_views(view_results: list[dict[str, Any]]) -> tuple[str, str, str, str]:
    if not all(view["status"] == "ok" for view in view_results):
        return "view_failure", "", "", ""
    valid_positives = [
        view for view in view_results
        if view["label"] == "positive" and view["evidence_type"] in POSITIVE_EVIDENCE
    ]
    if valid_positives:
        chosen = valid_positives[0]
        return "ok", "positive", chosen["evidence_type"], chosen["reason"]
    if all(view["label"] == "negative" and view["evidence_type"] in NEGATIVE_EVIDENCE for view in view_results):
        chosen = view_results[0]
        return "ok", "negative", chosen["evidence_type"], chosen["reason"]
    valid_uncertain = next(
        (view for view in view_results if view["label"] == "uncertain" and view["evidence_type"] == "insufficient"),
        None,
    )
    if valid_uncertain:
        return "ok", "uncertain", "insufficient", valid_uncertain["reason"]
    return "ok", "uncertain", "insufficient", "View outputs were semantically inconsistent with the frozen protocol."
