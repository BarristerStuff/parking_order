# parking_order v2.0 执行简报（给执行 AI）

> 阅读顺序：本文 → `docs/v2/parking_order_optimization_path_v2.md`（算法细节）→ 原 `codex-handoff.md`（位于 `/home/yanbo/net_vlm_yanboversion/docs/parking_order/codex-handoff.md`）（历史结论与硬约束）。三份文件有冲突时以本文为准；本文没写的以 v2 路径文档为准；历史 handoff 只用于"不要重复什么"和服务器/Git/评测隔离约束。

## 1. 已由用户拍板的决策（不要再问、不要改）

| 项 | 决定 |
|---|---|
| 事件新定义 v2.0 | positive = 车辆**完全停在车位外/通道上**，或**跨两个车位**（分隔线从车底穿过）。压线、车头/车尾略出、斜停 = negative |
| GT 来源 | 图片与生成提示词一一对应，GT 从 `group_key` 机械推导（见 §3），**不做全量人审**；只对 p05 的 20 张目检确认属于哪种形态并标出目标车 |
| 门岗排队 hn01 | 暂不处理；移出 primary 指标，FPR 单独报 |
| 模型 | **只能用 `qwen3.5:4b`**（`OLLAMA_BASE_URL=http://192.168.20.62:11434`），不得 pull 其他模型，不训练任何模型，≤ 2 并发 |
| 本地 CV | 允许（F2 已本地跑过 YOLO11n；可复用 `11_p3_lite_geometry/01_detector_cache/vehicle_detections.jsonl` 的 1,059 个 bbox） |
| 历史路线 | P0 / F0 / F1 / F2 / P3L-A 全部冻结，不重跑、不修改、不调参 |

## 2. 仓库与数据

- 仓库：`https://github.com/BarristerStuff/parking_order.git`（工作区快照，含 397 张 1920×1080 原图于 `01_staging/<group_key>/`）
- 关键已有产物：
  - `10_v1_2_fasttrack/01_shadow_gt/v1_2_dev_manifest.csv` —— 239 张 DEV 的 media_id / relative_path / group_key
  - `11_p3_lite_geometry/01_detector_cache/vehicle_detections.jsonl` —— YOLO11n car/bus/truck bbox 缓存
  - `10_v1_2_fasttrack/tools/run_fasttrack.py`、`fasttrack_common.py` —— Ollama 调用/JSON 解析/延迟统计可参考，但**不要修改原文件**，复制到新目录
- 新工作全部放在新目录 `12_v2_not_in_bay/`，结构建议：`00_definition/`、`01_gt_and_split/`、`02_tools/`、`03_debug/`、`04_pilot/`、`05_full_dev/`、`06_reports/`

## 3. 执行步骤与每步产出

### Step 1 — 定义冻结 + GT 推导 + 分层重切（先做，做完打第 1 个检查点）
1. 写 `00_definition/vehicle_not_in_bay_v2.0.md`，内容按 §1 定义；生成 sha256。
2. GT 映射（写进 `01_gt_and_split/v2_0_gt.csv`，字段 `media_id, group_key, v2_gt, target_bbox_hint, scope`）：
   - p01, p03 → positive
   - p05 → **逐张目检 20 张**，写 `positive`（跨线/在车位外）或 `negative`（只是出线/斜停），并记下目标车大致位置
   - p02, p04, p06, n01–n06, hn02–hn06 → negative
   - hn01 → negative，`scope=gate_queue_secondary`
   - u01–u05 → uncertain，`scope=gt_uncertain`
3. **重切 split**：抛弃原 group 级切分，在**每个子组内**按 60/20/20 随机（固定 seed）分 DEV/VAL/HOLDOUT，写 `01_gt_and_split/v2_split.csv` 并 sha256 冻结。VAL/HOLDOUT 本阶段不得读取图片。
4. 输出统计表：每子组在 DEV/VAL/HOLDOUT 的数量。

### Step 2 — 工具实现（`02_tools/`）
- `crop_ground_band.py`：按 bbox 裁地面带（宽 3W，上界 bbox 中线，下界 min(画面底, bbox 底+0.6H)），长边缩到 896，画红框 + 轮胎接地虚线。只处理 bbox 高 ≥ 15% 画面、未触边、最多 3 辆/图。
- `vlm_perception.py`：感知题 prompt（5 个 yes/no/unclear，见 v2 文档 §3.1），JSON 输出，失败重试 ≤ 2 次，记录延迟。prompt 定稿后 sha256 冻结。
- `geometry_color.py`：HSV 白/黄掩膜 + 三走廊（under / left / right / global）线像素密度 → 同样 5 个布尔值。**不用 LSD/Hough**。
- `fuse.py`：规则融合（v2 文档 §3.1 规则 + §3.3 一致性）。
- `evaluate.py`：只在所有预测写盘之后 join GT；输出 TP/FP/TN/FN、recall、FPR、按子组分组、hn01 FPR 单列、P50/P95 延迟。
- 隔离要求：推理代码不得读取 group_key / GT / split 以外的元数据，只能读图片路径与 bbox。

### Step 3 — Debug 定阈值（10 张，非 primary）
用 5 张 u* + 5 张 p02（都不在 pilot/DEV primary 内）跑几何路，定颜色掩膜和走廊密度阈值，一次冻结（`geometry_params_v2.json` + sha256）。之后不得再调。

### Step 4 — Pilot（60 张，DEV 内分层，冻结 manifest 后再跑）
- 配比：p01 15、p03 10、p05 5、n01 10、n02 10、p02 5、hn06 5。
- 两路（VLM 感知题、颜色几何）**分别**记录 5 个布尔值和各自的判定，再记录融合判定。
- 门槛：positive recall ≥ 0.7，negative FPR ≤ 0.10，p02 FPR ≤ 0.20。
- 停止规则：
  - VLM 路 recall < 0.4 → 主次互换（几何主判、VLM 只做 positive 否决），用同一批 pilot 数据直接评几何主路，不再发新请求。
  - 两路都 < 0.4 → **停下，回到用户**。
- 产出 `04_pilot/pilot_report.md`（**打第 2 个检查点**）。

### Step 5 — Full DEV（只有 pilot 通过才做）
重切后的 DEV 全量（约 240 张，含 hn01 单列）。产出 `05_full_dev/dev_report.md`（**打第 3 个检查点**）。VAL 需用户明确授权后才可运行一次。

## 4. 检查点：什么时候回来找规划方（Devin）确认

回来时带上对应产物文件即可：

1. **Step 1 完成后**：`v2_0_gt.csv` 统计表 + p05 目检结果 + 各子组 split 计数。确认 GT/切分无误后再写代码。
2. **Pilot 完成后**：`pilot_report.md` + 两路各自的 recall/FPR + 3–5 张失败样例的裁图。决定走主路、换主次、还是停。
3. **Full DEV 完成后**：`dev_report.md`。决定是否申请 VAL。
4. **任何时候**遇到以下情况立即停并回来：Ollama 不可达或 JSON 成功率 < 95%；YOLO 缓存与图片对不上；某子组 DEV 数量 < 5；发现 AIGC 图与子组意图明显不符的比例 > 10%。

## 5. 报告口径

- 所有指标标注 `source_type=AIGC`、`gt_basis=group_intent_v2.0`，不得表述为生产准确率。
- hn01 与 primary 分开报。
- 每份报告开头给固定字段块：`STAGE / PILOT_OR_DEV / TP FP TN FN / RECALL / FPR / P01_RECALL / P03_RECALL / P05_RECALL / HN01_FPR / P50 / P95 / OLLAMA_REQUESTS / GEOMETRY_ONLY_RECALL / VLM_ONLY_RECALL`。

## 6. 禁止事项（继承自历史 handoff）

不修改 `/home/yanbo/net_vlm_yanboversion/vlm`、服务器文件、Ollama 模型；不 `git add .` / commit / push / reset --hard；不读 VAL/HOLDOUT 图片；不重跑或改动 05–11 目录任何文件；不为提分改 GT。
