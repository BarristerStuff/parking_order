# parking_order 收窄定义后的算法优化路径 v2

约束（已确认）：只能用现有 Ollama `qwen3.5:4b`；不训练模型；本地可跑确定性 CV（F2 已经本地跑过 YOLO11n）；暂时忽略门岗排队；正例 = 完全停在车位外/通道上 + 跨两个车位。

## 1. 新定义 v2.0 与 GT 的推导（不需要全量人审）

图片与生成提示词一一对应，子组名就是意图，所以 GT 可以从 `group_key` 机械推导，只有 p05 需要看一眼：

| 子组 | v2.0 GT | 说明 |
|---|---|---|
| p01 outside-legal-bay-clear（39） | positive | 车在通道/空地，旁边有空车位 |
| p03 span-two-bays（30） | positive | 分隔线从车底中间穿过 |
| p05 multi-vehicle（20） | **需 20 张目检** | 意图只说"至少一辆违规"，没说是哪种。我抽看了 9 张：大多是跨线（→positive），个别只是车头出线（→negative）。5 分钟能标完，并顺手标出目标车是哪一辆 |
| p02 cross-single-line、p04 angled、p06 nose-intrudes（68） | negative | 新定义下都还在自己车位里 |
| n01–n06、hn02–hn06（180） | negative | |
| hn01 gate-queue（30） | 暂时移出 primary 指标，单独报 FPR | 你说先忽略 |
| u01–u05（40） | uncertain | 允许模型输出 uncertain，不计 TP/FP |

**必须重切 split**：现在按 group 切，DEV 正例只有 p01+p05，p03 全在 VAL。改为每个子组内 60/20/20 分层，DEV 才能覆盖两种正例形态。

## 2. 为什么 v2.0 对 4B 模型更友好

v1.2 让模型做的是"多条件 + 严重/轻微权衡"的**判断题**，4B 模型直接把 38/39 张 p01 说成"停在车位内"。v2.0 只剩两个可以**直接看见的**事实：

- **A. 车底中间有没有一条线穿过？**（跨两个车位）
- **B. 左右轮旁边有没有紧贴的车位线？**（有 → 在车位里；没有但画面里别处有车位线 → 在车位外）

这两个是**感知题**，不是判断题。策略：让 VLM 只回答感知题，违规与否由外部规则决定。

## 3. 推荐方案：感知题分解 + 高分辩率地面带 + 本地几何交叉验证

```
1920×1080 原图
   ↓ YOLO11n（本地，已有）车辆 bbox；只保留 bbox 高 ≥ 15% 画面、未被边缘截断的车，最多 3 辆
   ↓ 对每辆车裁"地面带"：宽 3×W，上界 = bbox 中线，下界 = min(画面底, bbox底 + 0.6H)，原分辩率，长边缩到 896
   ↓ 在裁图上用红框标出目标车（Set-of-Mark），bbox 底边向下画一条虚线标出"轮胎接地位置"
   ↓ VLM 感知题（1 次调用，结构化 JSON）
   ↓ 本地几何特征（颜色掩膜，非 LSD）
   ↓ 规则融合 → in_bay / outside / spanning / uncertain
   ↓ 任一车 outside 或 spanning → positive
```

### 3.1 VLM 感知题 prompt（草案，正式版要冻结）

```
The vehicle in the red box is parked. Look only at the pavement around its tires.
Answer each question with yes / no / unclear:
1. line_under_center: Is there a painted parking line passing UNDER the vehicle,
   between its left and right tires (visible in front of or behind the vehicle)?
2. line_left: Is there a painted parking line within about half a car width
   of the vehicle's LEFT tires, roughly parallel to the vehicle?
3. line_right: same for the RIGHT tires.
4. markings_visible: Are any painted parking-bay lines visible anywhere on the pavement?
5. on_aisle: Is the vehicle standing on an open driving lane / open pavement
   rather than inside a marked bay?
Return JSON only: {"line_under_center":..,"line_left":..,"line_right":..,"markings_visible":..,"on_aisle":..}
```

外部规则：
- `line_under_center=yes` → **spanning**（positive）
- `line_left=yes` 且 `line_right=yes` 且 `line_under_center≠yes` → **in_bay**
- `markings_visible=yes` 且 `line_left=no` 且 `line_right=no` 且 `on_aisle=yes` → **outside**（positive）
- `markings_visible=no/unclear` 或其他组合 → **uncertain**

### 3.2 本地几何特征（针对新问题重写，不是 P3L-A 的车位结构恢复）

P3 的 debug 图显示 LSD 几乎没检出线，但这批 AIGC 图的白/黄标线颜色非常干净，用颜色掩膜比 LSD 稳：

- HSV 白/黄掩膜 + 只保留 bbox 顶部以下的地面区域 + 形态学细化。
- 三个走廊统计线像素密度：
  - `under`：bbox 中心 ±0.15W，从 bbox 底边向下 0.5H（跨线时分隔线会在车前/车后露出来）
  - `left` / `right`：bbox 左/右边向外 0–0.35W，bbox 底边上下 ±0.15H
  - `global`：整个地面区域（判断标线是否可见）
- 输出同样的五个布尔值（阈值先用 10 张非 primary 的 debug 图定，之后冻结）。

### 3.3 融合

- VLM 与几何**两路一致** → 直接给结论。
- 不一致 → 再调 VLM 一次，用全图 896 letterbox 版本（换视角），三取二；仍不一致 → uncertain。
- 只有 positive 才会触发告警，所以 uncertain 是安全的。

### 3.4 延迟预算

F1 全图 896 单次约 6 s；地面带 crop 像素更少，预计 4–5 s/车。单车图 1 次调用 ≈ 5 s，不一致时 +5 s；多车图最多 3 辆 × 5 s，2 并发 ≈ 8–10 s。比 F2 的 22 s 好，比 F0 的 5 s 差；如果延迟上限要求更严，就把几何路当第一道、只对几何输出 uncertain 的车调 VLM。

## 4. 评测协议与 kill 条件

**Pilot（60 张，DEV 内分层）**：p01 15、p03 10、p05 5、n01 10、n02 10、p02 5、hn06 5。

- 通过门槛：positive recall ≥ 0.7，negative FPR ≤ 0.10，p02（现在是 negative）FPR ≤ 0.20。
- **VLM 路失败**（positive recall < 0.4）：说明 4B 模型连"车底有没有线"都答不了。已确认不能换模型，所以 fallback 是**主次互换**：3.2 的颜色掩膜几何做主判定（它天然只回答"车底有线 / 轮旁有线"这两个问题，正好是 v2.0 需要的），VLM 只在几何输出 positive 时调一次做否决（问"红框车是否明显停在车位里"，答 yes 则压掉）。pilot 里两路的五个布尔值都要单独记录，这样一次 pilot 就能同时评出 VLM 路和几何路各自的 recall/FPR，不用再跑第二轮。
- 两路都 < 0.4 → 在当前约束下没有可行路线，需要重新讨论约束（换模型或允许训练）。
- Pilot 通过 → full DEV（重切后的 ~240 张）→ 达标后申请一次 VAL。

## 5. 不做的事

- 不再用 v1.2 那种多条件判断 prompt；不再送车身 crop；不再把整图缩到 448。
- 不在 P3L-A 的 LSD 参数上做 sweep（改用颜色掩膜是换方法，不是调参）。
- 不做全量人审，只看 p05 的 20 张。
- 门岗排队先不处理，但 hn01 的 FPR 要单独报出来，别混进 primary。

## 6. 工作量

| 步骤 | 预计 |
|---|---|
| v2.0 定义冻结、GT 推导、p05 目检、分层重切 | 0.3 session |
| 地面带裁图 + Set-of-Mark + 感知题 prompt + 规则融合 runner | 0.5 session |
| 颜色掩膜几何特征 + 10 张 debug 图定阈值并冻结 | 0.3 session |
| 60 张 pilot（≤2 并发 Ollama）+ 报告 | 0.3 session |
| full DEV + 报告 | 0.5 session |

合计约 2 个 session；Ollama 请求全程 ≤ 2 并发，不修改服务器任何文件。
