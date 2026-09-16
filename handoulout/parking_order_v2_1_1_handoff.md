# parking_order_violation / vehicle_not_in_bay v2.1.1 工程交接

> 状态冻结日期：2026-09-16。本文是工程交接事实摘要，不是新的评测授权。

## 1. 当前事件与业务语义

原事件：`parking_order_violation`。当前工程语义：`vehicle_not_in_bay v2.1 outside-only`。

Positive：车辆明显完全停在停车位外、正常停车区域外或行车通道。Negative：正常位于停车位内、靠近停车线、轻微压线/越线、轻微斜停。当前不做厘米级压线判断。

Out-of-scope：`p03 span-two-bays`、`p05 multi-vehicle 跨位语义`；二者不触发正式 v2.1 outside-only 告警，仅单列观察。`hn01` 是 gate queue secondary，由 Q3 抑制。

## 2. 冻结模型与运行约束

```text
OLLAMA_BASE_URL=http://192.168.20.62:11434
MODEL=qwen3.5:4b
classes=car,bus,truck
conf=0.2
imgsz=640
device=cpu
YOLO checkpoint SHA256=0ebbc80d4a7680d14987a577cd21342b65ecfd94632bd9a8da63ae6417644ee1
```

使用直连 LAN；禁止 SSH tunnel、ControlMaster、`127.0.0.1:11444` 和 `CUDA_VISIBLE_DEVICES`；客户端最大并发 2；不修改服务器。

## 3. 最终算法

`RGB frame → YOLO11n car/bus/truck → vehicle selection → View A full-scene + red bbox → Q1 → only when Q1=C run Q3 → deterministic fusion → frame decision`。

实现入口：`12_v2_not_in_bay/08_v2_1_pipeline/vehicle_not_in_bay/`，其中 `infer_image` 是内存图像 API，`infer_path` 是薄封装。View A 使用 BytesIO，无共享 `tmp_view.jpg`；配置真实加载；prompt 做完整 SHA 校验；YOLO 模型对象复用；Ollama 有启动 preflight、重试和带 `attempt/question` 的 ledger。

Q1 原文与 SHA 位于 `08_v2_1_pipeline/prompts/q1.txt`，SHA256=`76151fc7f028c8274fd6c1a49158452a5b491d272b98effd463d8df2ba3b2eed`。Q3 原文与 SHA 位于 `08_v2_1_pipeline/prompts/q3.txt`，SHA256=`5cc5e33ac9e7a9f99b77100fcb4a83ad557d80901369e593f8cca7d7e2197cdc`。

## 4. Q1/Q3 融合

```text
Q1 != C: 不问 Q3
Q1=C,Q3=A: gate_queue → negative
Q1=C,Q3=B/C: outside → positive
Q1=C,Q3=D: uncertain
Q1=D: uncertain
Q1=A/B: in_bay → negative
```

帧级：任意 `outside` → `positive`；否则任意 `uncertain` → `uncertain`；否则 `negative`。无合格检测 → `uncertain`。`gate_queue` 单独记录，不触发告警。

## 5. AIGC DEV（冻结历史结果）

- p01 recall：`19/23 = 82.61%`
- negative FPR：`1/143 = 0.70%`
- negative FP：`IMG_007433`
- hn01：`0/18`
- uncertain：`1/238 = 0.42%`

不要写成历史错误的 `20/20` 或 `0/179`。

## 6. AIGC VAL（冻结、已消费）

p01 recall=`8/8=100%`；negative FPR=`0/48`；hn01=`0/6`；uncertain=`0/80`。Q3 gate PASS。VAL 不得再次用于调参。

## 7. AIGC HOLDOUT（永久不可重跑）

HOLDOUT 共 79 张，已完成且不得重跑：p01 recall=`8/8=100%`；negative FPR=`1/47=2.13%`；hn01=`0/6`；uncertain 全集=`0/79`。唯一 primary negative FP 为 `IMG_007452`，风险类型是合法路边平行停车（路缘 + 单侧停车线）。四项 gate PASS，状态为 `V2_1_HOLDOUT_PASS_READY_FOR_SHADOW_INTEGRATION`。

第一次 HOLDOUT 因 `ENOSPC` 中断；随后进行 ledger-aware resume，不是重新开始实验，attempt2 new requests=`14`。HOLDOUT 永久不可重跑。

## 8. AIGC 优化已关闭

```text
AIGC_MODEL_OPTIMIZATION_CLOSED=true
```

DEV 是开发集结果；独立 VAL 为 8/8，独立 HOLDOUT 为 8/8，FPR 与 gate queue 均通过冻结门槛。因此禁止为了把 DEV Recall 从 82.61% 刷到 90% 而修改 prompt/rules。主要剩余风险是 `REAL_ROBOT_DOMAIN_GAP`。

## 9. 已关闭失败路线

`v1.1 strict parking geometry`、`v1.2 direct VLM/high-resolution/context`、traditional `P3-lite line geometry` 已关闭；`V2 R0 ground-band` 已被 supersede；`V3/V4/V5 spatial/geometry branches` 为 non-champion。新窗口不要自动返回这些路线。

## 10. v2.1.1 工程状态与回归

`08_v2_1_pipeline = v2.1.1`，行为不变重构。历史报告记录：DEV replay PASS；HOLDOUT replay `79/79`；select `98/98`，mismatched media IDs=`[]`；View A `3/3`，MSE<1。不得为了核对这些历史数字而重新读取 HOLDOUT 图片或发模型请求。

## 11. Shadow sidecar

实现位于 `12_v2_not_in_bay/12_shadow_sidecar`，是旁路独立进程：不修改生产 worker、不触发现有告警、不 publish MQTT，只记录 JSONL；默认 `MIN_INTERVAL=10s`、single worker、只处理最新帧；明确 endpoint 为 `http://192.168.20.62:11434`；存图磁盘下限 15GB、frames 上限 5GB，超限只删除自身 frames 目录最旧文件。

已有本地 selftest 历史：3 frames、1 positive、2 uncertain、2 physical model requests、0 errors。`PRODUCTION_SHADOW_STARTED=false`，本轮未连接生产 broker。

## 12. 生产项目只读勘察

生产路径：`/home/yanbo/net_vlm_yanboversion/vlm`。已知默认 MQTT frame topic=`agora/yuv/frame`，broker default=`127.0.0.1:1883`，输入为 I420/latest-frame；当前生产 VLM=`qwen3.5:4b`。补充勘察确认 broker 凭据为可选 CLI 参数，payload 可含 width/height，源码未确认固定 FPS、单一原始分辨率或生产进程位于 `192.168.20.62`；因此不能把两端地址视为同一服务。架构上第二客户端可订阅，但 broker reachability/ACL/部署位置仍待后续 read-only probe。

未确认真实机器人停车图集或历史事件图；`REAL_ROBOT_PARKING_IMAGES_CONFIRMED=0`。仓库内虽有少量本地 sample/test 资产，但不能据此宣称真实机器人数据。

## 13. 当前唯一下一步

`REAL_ROBOT_SHADOW_VALIDATION`。先做 broker/input preflight，再做 20-frame canary，收集真实图并人工审核，最后决定生产集成。禁止新窗口直接改 prompt、跑 DEV/VAL/HOLDOUT、修改生产 worker 或开启正式告警。

## 14. Git

v2.1.1 commit：`7b31daa24f95cf4b666fbe7ecb423e95bf42a815`。Stage A handoff commit 在文档首次提交前为 `HANDOFF_COMMIT_PENDING`，最终 SHA 见 `current_state.json` 的后续提交更新。


## 15. v2.2 successor status (2026-09-16)

- `v2_2_status=DEV_GATE_FAIL_R1_RECALL_ALLOWED`
- `v2_2_definition=vehicle_not_in_marked_bay_v2.2`
- `v2_2_champion=NONE`
- `v2_2_next_stage=R1_RECALL_REQUIRES_SEPARATE_EXECUTION_AUTHORIZATION`
- R0 DEV: TP=3, FP=0, TN=134, FN=59; recall=4.84%, FPR=0%.
- R0 failed the frozen Recall/F1/p01/p03 gates. R1 was not run.
- Existing v2.1.1 remains the historical active champion, but its outside-only semantics do not satisfy the current v2.2 business definition. No historical VAL/HOLDOUT was rerun.
