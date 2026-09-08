#!/usr/bin/env python3
"""Run frozen parking_order_violation P0 on DEV/train only via Ollama HTTP."""
from __future__ import annotations

import argparse
import base64
import csv
import hashlib
import io
import json
import os
import re
import threading
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

from PIL import Image

ALLOWED_LABELS = {"1", "0", "uncertain"}
LANCZOS_RESAMPLE = getattr(getattr(Image, "Resampling", Image), "LANCZOS")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_manifest(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    if len(rows) != 239:
        raise SystemExit(f"P0 DEV manifest must contain exactly 239 rows, found {len(rows)}")
    if len({row["media_id"] for row in rows}) != 239:
        raise SystemExit("P0 DEV manifest contains duplicate media_id")
    forbidden = [row["media_id"] for row in rows if row.get("split") != "train"]
    if forbidden:
        raise SystemExit(f"P0 split guard rejected non-train rows: {forbidden[:5]}")
    return rows


def preprocess_image(path: Path, config: dict[str, Any]) -> str:
    prep = config["preprocess"]
    width, height = int(prep["canvas_width"]), int(prep["canvas_height"])
    color = tuple(prep["letterbox_color"])
    quality = int(prep["jpeg_quality"])
    with Image.open(path) as source:
        image = source.convert("RGB")
        image.thumbnail((width, height), LANCZOS_RESAMPLE)
        canvas = Image.new("RGB", (width, height), color)
        left = (width - image.width) // 2
        top = (height - image.height) // 2
        canvas.paste(image, (left, top))
        buffer = io.BytesIO()
        canvas.save(buffer, format="JPEG", quality=quality, optimize=True)
    return base64.b64encode(buffer.getvalue()).decode("ascii")


def parse_model_response(text: str) -> dict[str, str]:
    value = text.strip()
    fence = re.fullmatch(r"```(?:json)?\s*(.*?)\s*```", value, flags=re.I | re.S)
    if fence:
        value = fence.group(1).strip()
    obj = json.loads(value)
    if not isinstance(obj, dict):
        raise ValueError("response JSON must be an object")
    label = str(obj.get("label", "")).strip().lower()
    if label not in ALLOWED_LABELS:
        raise ValueError(f"invalid response label: {label!r}")
    reason = obj.get("reason", "")
    evidence = obj.get("evidence", "")
    if not isinstance(reason, str) or not isinstance(evidence, str):
        raise ValueError("reason and evidence must be strings")
    return {"model_label": label, "reason": reason.strip(), "evidence": evidence.strip()}


def post_json(url: str, payload: dict[str, Any], timeout: float) -> dict[str, Any]:
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(
        url, data=data, headers={"Content-Type": "application/json"}, method="POST"
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        body = response.read()
    obj = json.loads(body)
    if not isinstance(obj, dict):
        raise ValueError("Ollama HTTP response is not a JSON object")
    return obj


def infer_one(
    row: dict[str, str], config: dict[str, Any], prompt: str
) -> dict[str, Any]:
    dataset_root = Path(config["dataset_root"])
    image_path = dataset_root / row["relative_path"]
    started = time.perf_counter()
    base = {
        "source_id": row["source_id"],
        "media_id": row["media_id"],
        "split": row["split"],
        "group_key": row["group_key"],
        "group_id": row["group_id"],
        "sample_role": row["sample_role"],
        "gt_label": row["event_label"],
        "relative_path": row["relative_path"],
    }
    try:
        if not image_path.is_file():
            raise FileNotFoundError(image_path)
        actual_hash = sha256_file(image_path)
        if actual_hash != row["sha256"]:
            raise ValueError(f"DEV media SHA-256 mismatch: {row['media_id']}")
        image_b64 = preprocess_image(image_path, config)
        request_payload = {
            "model": config["model"],
            "prompt": prompt,
            "images": [image_b64],
            **config["ollama_request"],
        }
        last_error = None
        response_obj = None
        for attempt in range(int(config["max_retries"]) + 1):
            try:
                response_obj = post_json(
                    config["endpoint"], request_payload, float(config["timeout_seconds"])
                )
                break
            except Exception as exc:  # retain exact final transport error in audit output
                last_error = exc
                if attempt < int(config["max_retries"]):
                    time.sleep(1.0 * (attempt + 1))
        if response_obj is None:
            raise RuntimeError(f"Ollama request failed after retries: {last_error}")
        raw_response = response_obj.get("response", "")
        if not isinstance(raw_response, str):
            raise ValueError("Ollama response field must be a string")
        try:
            parsed = parse_model_response(raw_response)
            status = "ok"
            parse_error = ""
        except Exception as exc:
            parsed = {"model_label": "", "reason": "", "evidence": ""}
            status = "parse_failure"
            parse_error = f"{type(exc).__name__}: {exc}"
        return {
            **base,
            "status": status,
            **parsed,
            "parse_error": parse_error,
            "inference_error": "",
            "raw_response": raw_response,
            "latency_seconds": round(time.perf_counter() - started, 6),
            "ollama_total_duration_ns": response_obj.get("total_duration"),
            "ollama_load_duration_ns": response_obj.get("load_duration"),
            "ollama_prompt_eval_count": response_obj.get("prompt_eval_count"),
            "ollama_eval_count": response_obj.get("eval_count"),
        }
    except Exception as exc:
        return {
            **base,
            "status": "inference_failure",
            "model_label": "",
            "reason": "",
            "evidence": "",
            "parse_error": "",
            "inference_error": f"{type(exc).__name__}: {exc}",
            "raw_response": "",
            "latency_seconds": round(time.perf_counter() - started, 6),
            "ollama_total_duration_ns": None,
            "ollama_load_duration_ns": None,
            "ollama_prompt_eval_count": None,
            "ollama_eval_count": None,
        }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--prompt", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--check-only", action="store_true")
    parser.add_argument("--limit", type=int)
    args = parser.parse_args()

    config = json.loads(args.config.read_text(encoding="utf-8"))
    if config.get("stage") != "P0" or config.get("allowed_split") != "train":
        raise SystemExit("P0 config split/stage guard failed")
    if config.get("val_consumed") is not False or config.get("holdout_consumed") is not False:
        raise SystemExit("P0 config consumption guard failed")
    rows = read_manifest(args.manifest)
    prompt = args.prompt.read_text(encoding="utf-8")
    for row in rows:
        path = Path(config["dataset_root"]) / row["relative_path"]
        if not path.is_file() or sha256_file(path) != row["sha256"]:
            raise SystemExit(f"DEV preflight failed for {row['media_id']}")
    if args.check_only:
        print(json.dumps({
            "status": "check_ok", "dev_count": len(rows), "allowed_split": "train",
            "val_consumed": False, "holdout_consumed": False,
        }, sort_keys=True))
        return

    args.output_dir.mkdir(parents=True, exist_ok=True)
    results_path = args.output_dir / "predictions.jsonl"
    completed: set[str] = set()
    if results_path.exists():
        for line in results_path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                completed.add(json.loads(line)["media_id"])
    pending = [row for row in rows if row["media_id"] not in completed]
    if args.limit is not None:
        pending = pending[: args.limit]
    lock = threading.Lock()
    status_counts: dict[str, int] = {}
    with results_path.open("a", encoding="utf-8") as output:
        with ThreadPoolExecutor(max_workers=int(config["max_workers"])) as pool:
            futures = {pool.submit(infer_one, row, config, prompt): row for row in pending}
            for index, future in enumerate(as_completed(futures), start=1):
                result = future.result()
                with lock:
                    output.write(json.dumps(result, ensure_ascii=False, sort_keys=True) + "\n")
                    output.flush()
                    os.fsync(output.fileno())
                status_counts[result["status"]] = status_counts.get(result["status"], 0) + 1
                print(
                    f"P0_PROGRESS completed={index}/{len(pending)} media_id={result['media_id']} "
                    f"status={result['status']} label={result['model_label']}",
                    flush=True,
                )
    all_count = sum(1 for line in results_path.read_text(encoding="utf-8").splitlines() if line.strip())
    run_summary = {
        "status": "completed" if all_count == 239 else "partial",
        "manifest_count": 239,
        "result_count": all_count,
        "new_result_count": len(pending),
        "new_status_counts": status_counts,
        "allowed_split": "train",
        "val_consumed": False,
        "holdout_consumed": False,
    }
    (args.output_dir / "run_summary.json").write_text(
        json.dumps(run_summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(run_summary, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
