# Stage B1 MQTT read-only input probe

Date: 2026-09-16
Topic: `agora/yuv/frame`

## Result

```text
FINAL_STATUS=STAGE_B1_BLOCKED_REAL_INPUT
OLLAMA_REQUESTS=0
MQTT_PUBLISH=0
IMAGE_SAVE=0
MESSAGES_RECEIVED=0
DECODE_SUCCESS=0
```

The probe did not establish an MQTT session and therefore did not read any production payload. The active Python environment has no `paho-mqtt` package and no `mosquitto_sub` executable is available. Direct socket checks produced:

```text
127.0.0.1:1883       ECONNREFUSED
192.168.20.62:1883   connection timeout
```

No broker, ACL, topic payload, frame resolution, stereo layout, rotation, or decode result can be confirmed from this run. No production configuration was changed.

## Input semantics

```text
REAL_FRAME_WIDTHS=UNCONFIRMED
REAL_FRAME_HEIGHTS=UNCONFIRMED
REAL_FRAME_FORMAT=UNCONFIRMED
STEREO_PRESENT=UNCONFIRMED
ROTATION_APPLIED=UNCONFIRMED
TOPIC_CONFIRMED=false
BROKER_CONFIRMED=false
```

The existing static survey remains the only source for the expected topic and parser design. It is not a substitute for this failed live probe. Consequently, the sidecar was not started, no model request was made for this Stage B1 run, and no canary frame was processed.

## Safety checks

- Production project was not modified.
- No MQTT publish was attempted.
- No alerts, TTS, backend publisher, or production result writer was called.
- No DEV, VAL, or HOLDOUT data was read or rerun.
