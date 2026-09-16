# STAGE_B1_REAL_ROBOT_SHADOW_CANARY

Date: 2026-09-16

```text
FINAL_STATUS=STAGE_B1_BLOCKED_REAL_INPUT
READY_FOR_REAL_SHADOW_COLLECTION=false
```

Stage B1 stopped at the required read-only MQTT probe. The candidate broker endpoints were not reachable from this execution environment (`127.0.0.1:1883` refused; `192.168.20.62:1883` timed out), and the active environment has neither `paho-mqtt` nor `mosquitto_sub` available. No MQTT payload was read, so no input decode or real-frame semantic claim is made.

The 20-frame canary was **not started**. This is not a failed model evaluation and not a reason to modify v2.1.1. No Ollama request was made for the canary, no MQTT message was published, and the production project was not modified.

See `00_preflight/mqtt_probe_report.md` and `00_preflight/mqtt_probe_summary.json` for the auditable probe result. `01_canary/` remains empty except for the ignored `frames/` directory.

## Required final fields

```text
MQTT_BROKER=UNCONFIRMED
MQTT_TOPIC=agora/yuv/frame (static candidate only)
MQTT_MESSAGES_RECEIVED=0
MQTT_DECODE_SUCCESS=0
MQTT_DECODE_SUCCESS_RATE=null
REAL_FRAME_RESOLUTIONS=UNCONFIRMED
STEREO_PRESENT=UNCONFIRMED
ROTATION_APPLIED=UNCONFIRMED
OLLAMA_PREFLIGHT=PASS (tags contained qwen3.5:4b; no canary request followed)
MODEL=qwen3.5:4b
CANARY_PROCESSED_FRAMES=0
CANARY_VEHICLE_FRAMES=0
CANARY_POSITIVE=0
CANARY_NEGATIVE=0
CANARY_UNCERTAIN=0
CANARY_GATE_QUEUE=0
Q1_REQUESTS=0
Q3_REQUESTS=0
TOTAL_MODEL_REQUESTS=0
RUNTIME_ERRORS=0 (canary not started)
RUNTIME_ERROR_RATE=null
P50_TOTAL_LATENCY=null
P95_TOTAL_LATENCY=null
MAX_TOTAL_LATENCY=null
MQTT_PUBLISH_COUNT=0
PRODUCTION_ALERT_COUNT=0
PRODUCTION_TTS_COUNT=0
PRODUCTION_HEALTH_BEFORE=broker not reachable; production process not modified
PRODUCTION_HEALTH_AFTER=not applicable; canary not started
REAL_FRAME_IMAGES_COMMITTED_TO_GIT=false
READY_FOR_REAL_SHADOW_COLLECTION=false
```
