#!/bin/sh
set -eu
exec python3 "$(dirname "$0")/shadow_sidecar.py" --host "${SHADOW_MQTT_HOST:-127.0.0.1}" --port "${SHADOW_MQTT_PORT:-1883}" --topic "${SHADOW_MQTT_TOPIC:-agora/yuv/frame}"
