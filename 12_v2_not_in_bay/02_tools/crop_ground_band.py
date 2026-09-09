#!/usr/bin/env python3
"""GT-blind v2 ground-band crop and Set-of-Mark implementation."""

from __future__ import annotations

import argparse
import base64
import io
import json
import math
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw


LANCZOS = getattr(getattr(Image, "Resampling", Image), "LANCZOS")


def validate_image_binding(path: Path, expected_sha256: str) -> Image.Image:
    import hashlib

    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    if digest.hexdigest() != expected_sha256:
        raise ValueError("image SHA-256 mismatch")
    with Image.open(path) as source:
        source.verify()
    with Image.open(path) as source:
        image = source.convert("RGB")
        image.load()
    return image


def eligible_detections(
    detections: list[dict[str, Any]],
    width: int,
    height: int,
    config: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    policy = config["eligible_detection"]
    allowed = set(policy["allowed_classes"])
    margin = float(policy["edge_margin_pixels"])
    minimum_height = float(policy["minimum_bbox_height_fraction"]) * height
    accepted: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    for detection in detections:
        try:
            x1, y1, x2, y2 = [float(value) for value in detection["bbox"]]
            bbox_height = y2 - y1
            bbox_width = x2 - x1
        except (KeyError, TypeError, ValueError):
            rejected.append({"detection": detection, "reason": "invalid_bbox"})
            continue
        if detection.get("class_name") not in allowed:
            rejected.append({"detection": detection, "reason": "unsupported_class"})
        elif not all(math.isfinite(value) for value in (x1, y1, x2, y2)):
            rejected.append({"detection": detection, "reason": "nonfinite_bbox"})
        elif bbox_width <= 0 or bbox_height <= 0:
            rejected.append({"detection": detection, "reason": "empty_bbox"})
        elif bbox_height < minimum_height:
            rejected.append({"detection": detection, "reason": "bbox_below_15pct_height"})
        elif x1 <= margin or y1 <= margin or x2 >= width - margin or y2 >= height - margin:
            rejected.append({"detection": detection, "reason": "bbox_touches_image_edge"})
        else:
            accepted.append(detection)
    accepted.sort(
        key=lambda item: (
            -((float(item["bbox"][2]) - float(item["bbox"][0])) * (float(item["bbox"][3]) - float(item["bbox"][1]))),
            -float(item["confidence"]),
            int(item["class_id"]),
            float(item["bbox"][0]),
            float(item["bbox"][1]),
            float(item["bbox"][2]),
            float(item["bbox"][3]),
        )
    )
    limit = int(policy["max_vehicles_per_image"])
    for detection in accepted[limit:]:
        rejected.append({"detection": detection, "reason": "beyond_top_three_gt_blind_order"})
    return accepted[:limit], rejected


def crop_ground_band(
    image: Image.Image,
    detection: dict[str, Any],
    config: dict[str, Any],
) -> tuple[Image.Image, dict[str, Any]]:
    x1, y1, x2, y2 = [float(value) for value in detection["bbox"]]
    width, height = image.width, image.height
    bbox_width = x2 - x1
    bbox_height = y2 - y1
    center_x = (x1 + x2) / 2.0
    desired_width = min(float(width), 3.0 * bbox_width)
    left = int(math.floor(center_x - desired_width / 2.0))
    right = left + int(round(desired_width))
    if left < 0:
        right -= left
        left = 0
    if right > width:
        left -= right - width
        right = width
    left = max(0, left)
    right = min(width, right)
    top = max(0, int(math.floor((y1 + y2) / 2.0)))
    bottom = min(height, int(math.ceil(y2 + 0.6 * bbox_height)))
    if right <= left or bottom <= top:
        raise ValueError("invalid ground-band crop")

    crop = image.crop((left, top, right, bottom))
    draw = ImageDraw.Draw(crop)
    red = tuple(int(value) for value in config["preprocess"]["target_box_color_rgb"])
    line_width = int(config["preprocess"]["target_box_width"])
    local_box = [x1 - left, y1 - top, x2 - left, y2 - top]
    clipped_box = [
        max(0, local_box[0]),
        max(0, local_box[1]),
        min(crop.width - 1, local_box[2]),
        min(crop.height - 1, local_box[3]),
    ]
    draw.rectangle(clipped_box, outline=red, width=line_width)
    tire_y = max(0, min(crop.height - 1, int(round(y2 - top))))
    dash = int(config["preprocess"]["tire_contact_dash_length"])
    gap = int(config["preprocess"]["tire_contact_dash_gap"])
    start = max(0, int(math.floor(x1 - left)))
    end = min(crop.width - 1, int(math.ceil(x2 - left)))
    for position in range(start, end + 1, dash + gap):
        draw.line((position, tire_y, min(end, position + dash), tire_y), fill=red, width=line_width)

    long_edge = max(crop.width, crop.height)
    scale = min(1.0, int(config["preprocess"]["max_long_edge"]) / long_edge)
    if scale < 1.0:
        resized = crop.resize(
            (max(1, int(round(crop.width * scale))), max(1, int(round(crop.height * scale)))),
            LANCZOS,
        )
    else:
        resized = crop
    metadata = {
        "bbox": [round(value, 3) for value in (x1, y1, x2, y2)],
        "detection_class": detection["class_name"],
        "detection_confidence": detection["confidence"],
        "crop_box": [left, top, right, bottom],
        "crop_source_size": [crop.width, crop.height],
        "rendered_size": [resized.width, resized.height],
        "resize_scale": round(scale, 8),
    }
    return resized, metadata


def encode_jpeg_base64(image: Image.Image, quality: int) -> tuple[str, int]:
    buffer = io.BytesIO()
    image.save(buffer, format="JPEG", quality=quality, optimize=True)
    value = buffer.getvalue()
    return base64.b64encode(value).decode("ascii"), len(value)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--image", type=Path, required=True)
    parser.add_argument("--image-sha256", required=True)
    parser.add_argument("--detection-json", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    config = json.loads(args.config.read_text(encoding="utf-8"))
    detection = json.loads(args.detection_json)
    image = validate_image_binding(args.image, args.image_sha256)
    crop, metadata = crop_ground_band(image, detection, config)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    crop.save(args.output, format="JPEG", quality=int(config["preprocess"]["jpeg_quality"]), optimize=True)
    print(json.dumps(metadata, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
