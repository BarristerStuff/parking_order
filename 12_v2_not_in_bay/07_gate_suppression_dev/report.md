# v2.1 outside-only Q3 门岗抑制实验报告

日期：2026-09-15

## 事实

- 这是 DEV-only 的 Q3 追加实验；没有重跑 Q1 或 detector。
- 第一次尝试因 `PIL.Image.Resampling` 兼容错误在产出结果前中断；原 lock 已保留为 `Q3_ATTEMPT1_FAILED.lock`。第一次尝试可能已发出 `0–N` 次请求，因没有 ledger，无法精确核实。
- 第二次尝试只修复 PIL 版本兼容判断；未修改 `q3_prompt.txt`、`q3_config.json` 或融合规则。
- 先串行完成 1 张 hn01，再并发完成其余 58 辆；正式结果共 **59/59** 次 Q3 请求。
- schema 成功：**59/59 = 100%**；失败：0。
- Q3 prompt SHA256：`5cc5e33ac9e7a9f99b77100fcb4a83ad557d80901369e593f8cca7d7e2197cdc`。
- Q3 请求 ledger：`q3_request_ledger.jsonl`。每次请求有 request_start 和 request_result 两行。
- 追加延迟：P50 **1.531812 s/request**；P95 nearest-rank **1.742730 s/request**；最大 **7.911386 s/request**。完整数值以 `q3_metrics.json` 和 ledger 为准。

### 抑制结果

- hn01：原 Q1=C 报警 **15 张**；Q3=A 压掉 **15/15**，抑制率 **100%**。Q3 分布：A=16（包含原 Q1 非报警的一张），B=0，C=0，D=0。
- u05：原 Q1=C **3 张**；Q3 分布 B=3；压掉 **0/3**，没有变成 uncertain。
- n02：Q1=C **1 张**；Q3 分布 B=1，仍为 positive。
- u01：Q1=C **9 张**；Q3 分布 B=9。
- u02：Q1=C **7 辆**；Q3 分布 B=7。
- p01：原 Q1 TP **20/23**；Q3 后仍 positive **19/20**，原 TP 保留率 **95.00%**。被压掉的原 TP：`IMG_007533`；View A 位于 `view_a_all/IMG_007533__v1.jpg`。

### 应用 Q3 后的 DEV v2.1 总表

| 指标 | Q3 后 DEV | 06_ DEV(a) 原 Q1 |
|---|---:|---:|
| Recall | 19/23 = **82.61%**, Wilson 95% [62.86%, 93.02%] | 20/23 = **86.96%**, [67.87%, 95.46%] |
| negative FPR | 1/143 = **0.70%**, [0.12%, 3.85%] | 1/143 = **0.70%**, [0.12%, 3.85%] |
| hn01 单列 FPR | 0/18 = **0.00%**, [0.00%, 17.59%] | 15/18 = **83.33%**, [60.78%, 94.16%] |
| 全集 uncertain 率 | 1/238 = **0.42%**, [0.07%, 2.34%] | 1/238 = **0.42%**, [0.07%, 2.34%] |

Q3 后预测计数：positive=38，negative=199，uncertain=1。

### 三个 DEV p01 漏检

- `IMG_007531`：R1 Q1=`A`；检测框数=1；不是 detector 没框到车，而是检测到车辆后 Q1 未答 C。
- `IMG_007536`：R1 Q1=`A`；检测框数=1；不是 detector 没框到车，而是检测到车辆后 Q1 未答 C。
- `IMG_007548`：R1 Q1=`A`；检测框数=1；不是 detector 没框到车，而是检测到车辆后 Q1 未答 C。

对应 View A：

- `view_a_all/IMG_007531__v1.jpg`
- `view_a_all/IMG_007536__v1.jpg`
- `view_a_all/IMG_007548__v1.jpg`

## 推理

Q3 对 hn01 门岗队列有明显抑制效果：15 张原 Q1=C 报警全部被压掉；但存在 1 张 p01 原 TP（`IMG_007533`）被 Q3=A 错误压掉，因此 Recall 从 86.96% 降至 82.61%。这说明 Q3 能抑制门岗误报，但当前版本不能作为无损抑制器。

u05、u01、u02 均被 Q3 判 B，没有增加 uncertain；Q3 没有改善不确定场景的保守拒答。

## 风险

- Q3 是 DEV-only、AIGC-only 实验，不能外推 VAL、真实相机、机器人或生产环境。
- 第一次尝试无 request ledger，实际请求数只能诚实记录为 0–N 未知；第二次正式尝试为 59/59。
- hn01 样本只有 18 张，0/18 的 Wilson 上界仍为 17.59%。
- Q3 误压 p01，表明“看到门岗元素”与“车辆属于门岗队列”仍可能混淆。
- 本实验不修改 Q1 主规则，不创建 Winner，不代表生产候选。

状态：`Q3_DEV_COMPLETED_NOT_PRODUCTION_READY`

> 更正说明（2026-09-15）：经复核 `/home/yanbo/net_vlm_parking_optimization/12_v2_not_in_bay/05_vlm_dev_r1/predictions.jsonl`，IMG_007531、IMG_007536、IMG_007548 的 R1 Q1 实际答案均为 A；此前报告写成 B 是记录错误。
