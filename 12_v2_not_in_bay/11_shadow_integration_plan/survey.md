# Production read-only survey: v2.1 shadow integration

Date: 2026-09-15
Production source surveyed read-only: `/home/yanbo/net_vlm_yanboversion/vlm`
No production file was modified.

## 1. Structure and entry path

Relevant tree (depth 3; cache/venv omitted):

```text
vlm/
├── main.py
├── analysis_server.py
├── analysis_handler.py
├── mqtt_handler.py
├── pyproject.toml
├── script/
│   ├── net_vlm.py              # CLI/MQTT orchestration entry
│   ├── worker.py               # latest-frame inference worker
│   ├── frames.py               # I420 parsing and frame conversion
│   ├── ollama_vlm.py           # Ollama client
│   ├── alerts.py               # response normalization and alert keys
│   ├── backend_publisher.py    # robot event wrapper
│   ├── robot_event_publisher.py
│   ├── tts_publisher.py
│   ├── mqtt_utils.py
│   ├── server.py
│   └── prompts.py
├── w_v/
│   ├── realtime_yoloe_vlm.py
│   ├── realtime_worker.py
│   ├── realtime_processing.py
│   ├── realtime_vlm.py
│   └── yoloe_gate.py
└── ultralytics/                # vendored source tree, not a production weight
```

Primary parking/event path found in the source:

1. `script/net_vlm.py:main()` creates the MQTT client, latest-frame store, Ollama checker and inference worker.
2. MQTT `on_message()` parses payloads through `I420PayloadParser.parse()` in `script/frames.py:194`, with configured or inferred width/height, and stores only the newest frame.
3. `run_inference_worker()` in `script/worker.py:105` consumes the newest `I420FramePacket`.
4. `OllamaI420Checker.infer()` converts I420 to an image, selects the stereo view, optionally rotates 180 degrees, resizes to the configured VLM size, JPEG-encodes it and sends it to Ollama.
5. `alerts.normalize_model_result()` converts the model response into normalized alert keys.
6. Existing alerts are emitted to JSONL/TTS and optionally published to MQTT; robot backend events are published separately when alerts are present.

The inspected production path does not show an existing parking-specific YOLO detector call. The vendored `ultralytics/` tree is present, but no `yolo11n.pt`, ONNX, or TensorRT weight was found under the production project outside that source tree.

## 2. Ollama, concurrency and output schema

Existing Ollama client:

- File: `script/ollama_vlm.py`
- Class: `OllamaI420Checker`
- Default endpoint: `http://127.0.0.1:11434/api/generate`
- Default model: `qwen3.5:4b`
- HTTP library: `requests.Session`
- Request: synchronous `POST`, JSON payload, `stream=False`, `format="json"`, `think=false`.
- Options: `temperature=0`, `top_p=0.9`, configured `num_predict`.
- Timeout: `(2.0, timeout_sec)`, default total/read timeout setting 30 seconds.
- Retries: no retry loop was found in this client.
- Concurrency: the normal worker is a single latest-frame inference loop; no client-side request pool was found in this path.

Current normalized result and output fields include:

```text
seq, topic, packet_id, timestamp_ms, received_timestamp_ms,
inference_timestamp_ms, skipped_frames, width, height, source_format,
model, elapsed_sec, result, image_path (optional), error (optional)
```

The `result` is a normalized list of alert keys. Relevant alert key is `parking_order_violation` (`script/alerts.py`). JSONL output is written by `script/worker.py`; optional MQTT output is handled by `tts_publisher.py`, and robot event payloads by `robot_event_publisher.py`/`backend_publisher.py`. Existing alert publishing is not a database sink in the surveyed code; it is file output and MQTT publication.

## 3. Existing parking logic

Relevant signatures:

```python
# script/alerts.py
def extract_json(text: str) -> Any
def normalize_model_result(parsed: Any) -> list[str]
def parking_order_value_means_positive(value: Any) -> bool
def alert_yes_result(alerts: list[str]) -> bool

# script/worker.py
def run_inference_worker(
    latest_store: LatestFrameStore,
    checker: OllamaI420Checker,
    stop_event: threading.Event,
    output_path: Path | None,
    save_image_dir: Path | None,
    output_mode: str,
    ...,
) -> None

# script/ollama_vlm.py
def infer(self, packet: I420FramePacket) -> tuple[list[str], bytes, str]

# script/frames.py
class I420PayloadParser:
    @classmethod
    def parse(cls, seq: int, topic: str, payload: bytes, ...)
        -> I420FramePacket
```

Current behavior: the production worker sends the whole selected/encoded frame to the VLM, normalizes model output to alert keys, and emits/publishes existing alerts. No v2.1 outside-only rule, Q1/Q3 vehicle-level fusion, or vehicle detector integration was found in this production tree.

## 4. Environment and launch

Confirmed from `pyproject.toml` and the active interpreter:

```text
Python: 3.10.12
PIL/Pillow: 9.0.1
requests: 2.25.1
ultralytics import: available only as vendored source identity without a reported __version__ in this interpreter check
```

Declared project dependencies are `fastapi`, `requests`, and `uvicorn`. OpenCV/Paho are imported by runtime modules but are not declared in the shown `pyproject.toml`; exact installed versions were not asserted by this read-only survey.

No `yolo11n.pt`, ONNX, or TensorRT weight was found under `vlm/` outside the vendored source tree.

Documented run modes are direct scripts and Uvicorn, for example:

```text
.venv/bin/python script/net_vlm.py ...
.venv/bin/python -m uvicorn script.server:app --host 0.0.0.0 --port 8000
```

No project-local systemd unit or Dockerfile was found in the surveyed tree. A process listing did not show the production script currently running in this shell.

## 5. Robot parking image/event inventory

Read-only file inventory under the production project found **9 local image files** (sample/test assets only), with header dimensions:

```text
1707x1280: 3
1229x727: 1
1672x941: 1
3072x4096: 1
1280x480: 1
1280x1707: 1
640x480: 1
```

The files are project-root sample images such as `z1.jpg`–`z5.jpg`, `o1.jpg`, `stereo1.jpg`, and screenshots. No production robot image archive, parking-event image directory, or historical parking-event corpus was identified inside `/home/yanbo/net_vlm_yanboversion/vlm`.

This is an inventory only; image content was not used for model evaluation. Therefore the production project provides **no confirmed real-robot parking image count beyond these 9 local sample/test assets**, and no historical event count can be established from this tree.

## 6. Shadow integration recommendation

Recommended non-alerting hook:

- Hook immediately after `checker.infer(packet)` returns in `run_inference_worker()` and before `alerts` are emitted/published. This is the first point where the decoded frame, timestamp/sequence metadata, and current inference result are simultaneously available.
- Prefer a separate shadow worker/adapter that receives a copy of the decoded frame plus packet metadata. It should invoke the v2.1 pipeline asynchronously or through a bounded queue, never block or replace the existing alert path, and never call the existing alert publisher.
- Write only to an independent JSONL shadow log, for example:
  ```text
  outputs/v2_1_shadow_predictions.jsonl
  ```
  with a separate optional error/latency log. Do not write `parking_order_violation` into the existing `result` list and do not publish to the existing alert/event MQTT topics during shadow mode.

Suggested future change list (not applied):

1. New adapter module, e.g. `script/v2_1_shadow.py`: approximately 120–180 lines for frame materialization, invocation, schema validation, bounded queue, and JSONL append.
2. Small injection in `script/worker.py` after `checker.infer(packet)`: approximately 10–20 lines plus constructor/config plumbing.
3. CLI/config flags in `script/net_vlm.py` for shadow enablement, output path, queue size, and fail-open behavior: approximately 20–40 lines.
4. Packaging/config update for the detector checkpoint and the v2.1 package location: approximately 10–20 lines.
5. Tests for no-alert side effects, schema, queue overflow, and image-format conversion: approximately 100–160 lines.

Before implementation, the v2.1 module must be adapted to the production frame contract: its current interface expects an image path, while production supplies an in-memory I420 packet and the production path currently resizes to 448x336 JPEG after stereo selection/rotation. A direct call without an adapter would either fail or silently change the input semantics.

No production integration was performed by this survey.
