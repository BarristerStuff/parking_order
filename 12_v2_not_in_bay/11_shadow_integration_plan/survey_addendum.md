# Shadow sidecar supplemental survey

Date: 2026-09-15. Read-only survey of `/home/yanbo/net_vlm_yanboversion/vlm`; no production files changed.

## Confirmed transport facts

- Production CLI defaults: MQTT host `127.0.0.1`, port `1883`, topic `agora/yuv/frame`, QoS `0` (`script/net_vlm.py` constants and arguments).
- Username/password are optional CLI arguments; no hard-coded credentials were found.
- Payload is binary I420/YUV or base64/raw variants parsed by `I420PayloadParser`; JSON payloads may carry `width`/`height`, while CLI width/height can also be supplied or parser inference used. The parser supports common raw-frame byte sizes.
- The inspected production code does not declare a fixed production frame rate. It consumes only the latest MQTT frame and intentionally skips older frames when inference lags. Therefore FPS is **not established from source**.
- The source defaults to `448x336` for Ollama after stereo-view selection and optional 180-degree rotation. The original decoded I420 resolution is variable/configured or inferred; no single production resolution was established from the repository. The sidecar must avoid the `448x336` resize and preserve the selected/rotated full-resolution image.
- The production process is not confirmed to run on `192.168.20.62`; no running production process or deployment inventory was found in the repository/shell. Consequently, `127.0.0.1` and `192.168.20.62` cannot be assumed to be the same service.

## Sidecar decision

The source shows a broker/topic-based architecture and does not show an exclusive unicast subscription. A second MQTT client is therefore **architecturally possible**, but broker reachability, ACLs, authentication and whether the broker is local to `192.168.20.62` remain deployment facts to verify. No broker connection was made by this survey. The sidecar is prepared but must not be started until operator confirmation of broker reachability/ACL and process placement.

If that confirmation fails, do not modify `worker.py`; keep the sidecar stopped.
