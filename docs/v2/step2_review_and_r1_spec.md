# Step 2 R0 复盘与 R1 规格（vehicle_not_in_bay v2.0）

审阅对象：`12_v2_not_in_bay/04_vlm_dev_baseline/`（`V2_PERCEPTION_GROUND_BAND_BASELINE_R0`，DEV 238 张，qwen3.5:4b）。
本文只基于 `predictions.jsonl` + `v2_dev_evaluation_manifest.csv` 的逐条复算，未访问 VAL/HOLDOUT，未改 GT/split。

## 1. 结论先行

R0 的 47% recall / 27% FPR **不是 qwen3.5:4b 能力上限的证据，而是 R0 问题定义和融合规则的三处设计缺陷造成的**。用它触发"关闭单 RGB 路线"是过早的。建议在同一 DEV、同一 GT/split 上再跑一轮修正版 R1（下文 §4），R1 仍不达标再正式关闭。

## 2. 证据（逐条复算 predictions.jsonl）

### 2.1 全部 39 个 FP 都来自 `line_under_center=yes → spanning`，0 个来自 outside 规则

| 负例子组 | 车辆级 `line_under_center=yes` 比例 | 帧级误报 |
|---|---|---|
| n01 标准停放 | 5/27 | 5/18 |
| n04 平行车位 | 4/11 | 4/9 |
| n05 多车全合规 | 7/17 | 7/9 |
| n06 特殊车位 | 3/13 | 3/12 |
| hn06 阴影/裂缝 | 3/7 | 3/6 |
| p02 单边压线 | 5/33 | 5/21 |
| p04 斜停 | 4/18 | 4/14 |
| p06 车头出线 | 3/7 | 3/6 |

对**完全合规**的 n01/n04/n05 也有 20–40% 的 "yes"。抽看 n01 误报图：车正常停在车位内，车头前方有一条横向的车位前缘线，模型把这条**横线**当成了"passing under the vehicle between left and right tires"。R0 prompt 只说了 "passing UNDER, between its left and right tire positions"，没说必须**纵向（与车身同向）**——车位前缘横线在几何上确实"在左右轮之间穿过"。这是 prompt 规格 bug，不是感知失败。

p03 上该问题 13/21 答 yes（真跨线），所以信号有，但被横线污染。

### 2.2 p01 recall 17% 是 AND 规则 + "半个车宽"问法的必然结果

outside 规则要求 `markings=yes ∧ line_left=no ∧ line_right=no ∧ on_aisle=yes` 四项同时成立。p01 车辆级答案：

- `line_left=no` 18/27，`line_right=no` 7/27，`on_aisle=yes` 9/27，四项同时成立 3/27。

抽看 p01 图：车停在通道上，**旁边就是车位**，右侧半个车宽内确实有车位线——模型答 `line_right=yes` 并不算错，是问题本身不区分"车在两条线之间"和"车旁边有线"。只有约 1/3 的 p01 模型能答出 `on_aisle=yes`，说明 p01 确实是 4B 最弱的一类，但 R0 规则把这 1/3 又砍到了 1/9。

### 2.3 多车 OR 融合放大误报（F2 同样的教训）

39 个 FP 中 **13 个只由非最大车辆（rank>1）触发**。n05（多车全合规，平均 2.78 辆/图）FPR 7/9，是全部子组里最差的。只看 rank-1 车辆的反事实：TP 24→20，FP 39→26。

### 2.4 ground-band 裁图没有带来分辩率收益

横向宽度 = 3×bbox 宽，在本数据集上几乎总是被钳到整幅 1920，再缩到 896，缩放比 ≈0.48，与 F1 的 896×672 letterbox 一致（rendered 高度中位数 213–296 px）。"局部高分辩率"这一设计目标在 R0 里实际没有实现。

### 2.5 执行简报里的几何交叉验证路（HSV 颜色掩膜）没有运行

`12_v2_not_in_bay/` 下没有任何几何路产物。简报 Step 3/4 规定两路同跑、VLM 路 <0.4 时主次互换；R0 只跑了 VLM 单路就触发关闭，简报定义的 fallback 未被消费。

## 3. 对用户决策树的解读

决策树 "Recall<70% → 关闭单 RGB" 的前提是 baseline 本身实现正确。§2.1–2.3 表明 R0 有可定位、可修复的实现缺陷（横线歧义、AND 规则、OR 融合），所以 R0 不构成合格的 baseline。修一次、再判一次，不算 "prompt sweep"。

## 4. R1 规格（一次性冻结，跑完即判，不迭代）

约束不变：qwen3.5:4b、同一 Ollama、并发 2、DEV 238、GT/split 不动、不碰 VAL/HOLDOUT、历史目录不动。产物放 `12_v2_not_in_bay/05_vlm_dev_r1/`。

### 4.1 目标车选择
- 只判 **rank-1（最大 bbox）**；第二辆仅在其 bbox 高 ≥ 0.25×图高时追加（覆盖 p05 多车正例），其余忽略。
- 帧级 positive = 任一被判车辆 positive；但被判车辆数上限 2（原来 3）。

### 4.2 两种视图（替代 ground-band）
- **视图 A（全幅上下文）**：整帧长边 896，红框标目标车。用于 Q1。
- **视图 B（底盘窄条，原生分辩率）**：x 范围 = bbox 宽 ×1.3 居中，y 范围 = bbox 顶 + 0.6H → min(图底, bbox 底 + 0.35H)，不缩放（或长边 ≤ 896 时不放大）。用于 Q2。

### 4.3 两问（替代五问）
Q1（视图 A，单选）：
```
The red-boxed vehicle is stationary. Judge only its relation to PAINTED parking-bay lines on the ground.
A) inside ONE bay: painted lines on both sides of the vehicle belong to the same bay and the vehicle sits between them
B) straddling: a painted separator line runs lengthwise (front-to-back) under the middle of the vehicle, so it occupies parts of TWO bays
C) not in any bay: the vehicle stands on open pavement / a driving lane; bays may be visible elsewhere but the vehicle is not between a bay's side lines
D) cannot tell (lines not visible, night/blur, vehicle cut off, heavy occlusion)
Answer with one letter.
```
Q2（视图 B，yes/no/unclear）：
```
Does a painted line run LENGTHWISE — in the same direction as the vehicle, front-to-back — under the MIDDLE of the vehicle's underbody, between the left and right tires?
A line running CROSSWISE in front of or behind the vehicle (the bay's front/rear edge) does NOT count. A line only touching an outer tire does NOT count.
```

### 4.4 融合规则
- Q1=C → **positive (outside)**
- Q1=B 且 Q2=yes → **positive (spanning)**
- Q1=B 且 Q2≠yes → uncertain（不计 FP/TP）
- Q1=A → negative
- Q1=D → uncertain
- 每车 2 次请求；视图 B 只在 Q1=B 时才发（节省约 60% 请求）。

### 4.5 同批运行几何路（简报 Step 3，补做）
用 HSV 白/黄掩膜在视图 B 的原生条带内，只算一件事：**是否存在一条纵向（与车身方向夹角 <25°）的长线穿过 bbox 中央 40% 宽度带**，输出 `geo_line_under_center ∈ {yes,no,unclear}`。参数用 5 张 u* + 5 张 p02 定一次并冻结。它只用于 spanning 的第二票：Q2=yes 且 geo=no → 降为 uncertain。

### 4.6 判定门槛（跑完只判一次）
- primary recall ≥ 0.70 且 primary FPR ≤ 0.10 → 进入简报 Step 5 后续；
- recall ≥ 0.70 但 FPR 在 0.10–0.20 → 只保留 spanning（p03/p05）子任务，p01 单独讨论；
- recall < 0.70 → 正式关闭单 RGB + qwen3.5:4b 路线，结论可信。
- 同时报：p01 recall、p03 recall、p05 recall、n05 FPR、p04/p06 FPR、hn01 单列。

### 4.7 预算
约 238×1.15 辆 × (1 + P(Q1=B)) ≈ 400 次请求，按 R0 的 2.3 s P50、并发 2，约 25–40 分钟。

## 5. 关于 SpatioLM successor gate
本机无 CUDA 的阻塞是环境事实，与模型能力无关，维持 `BLOCKED_NO_CUDA` 记录。在 R1 结果出来前不建议为它另找 GPU；若 R1 也失败，再决定是否为 successor gate 申请算力。
