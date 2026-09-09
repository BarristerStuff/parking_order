# SpatioLM successor feasibility gate — environment-blocked record

**Final status:** `SPATIOLM_SUCCESSOR_GATE_BLOCKED_NO_CUDA`  
**Model requested:** `xiaomi-research/SpatioLM-Understanding-InternVL3.5`  
**Formal gate started:** `false`  
**Current parking-vision route closed by this task:** `false`

## Confirmed facts

- The frozen v2.0 definition, GT, and split each passed their SHA-256 sidecar check. Their respective hashes are `0e9c6b0a…5847a6`, `321f0994…bd353`, and `f531aaff…db24`.
- The registered gate composition is feasible from the DEV partition alone: the required ten group/label strata all have at least their requested counts. No pilot manifest was generated because the hardware gate stopped earlier.
- The local preflight ran before any download or model load. `nvidia-smi` is absent (exit 127); `/dev/nvidia*`, `/proc/driver/nvidia/gpus`, NVIDIA kernel modules, and CUDA/NVIDIA container variables are absent; the visible display adapter is VMware SVGA II. System Python is 3.10.12 and has no installed PyTorch module.
- No checkpoint, source repository, isolated virtual environment, prompt, smoke image, pilot image, inference, or retry was attempted. No remote server, Ollama, SSH, or SCP was used.
- No VAL/HOLDOUT image was read; neither partition was selected, scored, or passed to inference. The input SHA validation bound the global frozen GT and split files without selecting non-DEV labels.
- The formal dataset and the formal `vlm` project were not modified by this gate. The formal project worktree was already dirty when observed, so this report does not claim it was globally clean.

## Reasoning and decision

The frozen protocol requires an NVIDIA CUDA GPU for the official BF16 `SpatioLM-Understanding-InternVL3.5` path and explicitly prohibits a CPU complete-gate run or an unauthorized quantized substitute. The local machine has no exposed CUDA hardware or driver. Therefore the experiment cannot form 60 valid model predictions, and calling this a model-capability failure would be false.

Accordingly, the only valid result is `SPATIOLM_SUCCESSOR_GATE_BLOCKED_NO_CUDA`. It is **not** `SPATIOLM_SUCCESSOR_GATE_FAILED`, does not consume the one formal pilot, and does not permanently close the current single-frame RGB route.

## Scope and risk boundary

This result says nothing about SpatioLM's spatial-understanding capability. It only establishes that the user-authorized local BF16 inference route was unavailable in this execution environment. The explicitly prohibited substitutions—CPU inference, 4/8-bit quantization, a different checkpoint, a different model, remote-GPU setup, or further qwen/geometry/prompt experiments—were not attempted.

To reopen this *specific* successor gate, a future user authorization would need to provide a local CUDA-capable environment (or explicitly authorize a different execution location) while preserving the already-frozen model, official implementation, prompt, 60-item pilot, and inference parameters. No such continuation is authorized by this blocked record.

## Evidence

- [Hardware preflight](00_preflight/hardware_preflight.json)
- [Frozen-input integrity report](00_preflight/input_integrity.json)
- [Environment decision record](01_environment/environment_freeze.json)
- [Checkpoint non-access record](01_environment/model_checkpoint_info.json)
- [Smoke non-run record](03_smoke/smoke_report.json)
- [Formal-gate non-start record](04_formal_gate/formal_gate_started.json)
- [Independent final audit](06_final_audit/final_audit.json)
- [Independent blocked-record validation](06_final_audit/independent_validation.json)
- [Terminal summary](terminal_summary.txt)
