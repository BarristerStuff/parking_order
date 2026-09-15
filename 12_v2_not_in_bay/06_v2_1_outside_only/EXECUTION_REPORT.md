# v2.1 outside-only VAL 一次性确认执行报告

## 事实

- 执行日期：2026-09-15
- 工作目录：`/home/yanbo/net_vlm_parking_optimization/12_v2_not_in_bay/06_v2_1_outside_only`
- 定义：`positive=p01`；`out_of_scope=p03,p05`；`secondary=hn01`；`uncertain=u01-u05`；其余为 negative。
- 数据来源：AIGC；`HUMAN_GOLD=false`。标签依据为既有 evaluator/group intent，不是人工逐图几何金标。
- VAL：80/80 张，且仅含 VAL；HOLDOUT 图片读取 0，HOLDOUT 推理 0。已存在历史 HOLDOUT metadata 暴露，故不声称 metadata 从未被读取。
- Detector：YOLO11n，car/bus/truck，conf=0.2，imgsz=640，CPU；80/80 完成，raw detections=396。一次性锁为 `COMPLETED_DO_NOT_RERUN`。
- Q1：`qwen3.5:4b`，并发 2；仅 Q1，Q2 请求 0。逻辑请求 95，物理 HTTP 请求 95，schema 成功 95/95，物理失败 0。一次性锁为 `COMPLETED_DO_NOT_RERUN`。

### VAL 与 DEV(a) 并排结果

| 指标 | VAL 一次性确认 | DEV(a) 历史冻结 Q1 离线复算 |
|---|---:|---:|
| 图像数 | 80 | 238 |
| v2.1 recall | 8/8 = 100.00%, Wilson 95% [67.56%, 100.00%] | 20/23 = 86.96%, Wilson 95% [67.87%, 95.46%] |
| negative FPR | 0/48 = 0.00%, Wilson 95% [0.00%, 7.41%] | 1/143 = 0.70%, Wilson 95% [0.12%, 3.85%] |
| hn01 单列告警率/FPR | 5/6 = 83.33%, Wilson 95% [43.65%, 96.99%] | 15/18 = 83.33%, Wilson 95% [60.78%, 94.16%] |
| p03 告警率 | 0/6 = 0.00%, Wilson 95% [0.00%, 39.03%] | 0/18 = 0.00%, Wilson 95% [0.00%, 17.59%] |
| p05 告警率 | 0/4 = 0.00%, Wilson 95% [0.00%, 48.99%] | 0/12 = 0.00%, Wilson 95% [0.00%, 24.25%] |
| p03+p05 告警率 | 0/10 = 0.00%, Wilson 95% [0.00%, 27.75%] | 0/30 = 0.00%, Wilson 95% [0.00%, 11.35%] |
| 全集 uncertain 率 | 0/80 = 0.00%, Wilson 95% [0.00%, 4.58%] | 1/238 = 0.42%, Wilson 95% [0.07%, 2.34%] |
| uncertain-scope 被判 uncertain | 0/8 = 0.00% | 1/24 = 4.17% |

### 延迟、请求和错误

- VAL 每图延迟：P50=1.752886s，P95(nearest-rank)=3.546746s，min=1.575753s，max=9.867195s。
- VAL primary FP：无；primary FN：无。因此 `errors.csv` 只有表头，`errors/false_positives/` 与 `errors/false_negatives/` 为空；不存在可附的 VAL 错误 View A，未伪造样本。
- 全部 VAL View A 在 `/home/yanbo/net_vlm_parking_optimization/12_v2_not_in_bay/06_v2_1_outside_only/view_a_all`。
- DEV(a) primary FP：`IMG_007433`；FN：`IMG_007531`, `IMG_007536`, `IMG_007548`。DEV(a) 是历史冻结 R1 Q1 的离线重解释，没有新增请求。

## 推理

1. VAL primary 指标表面良好：p01 8/8，普通 negative 0/48 告警。但 positive 分母只有 8，Recall 的 Wilson 95% 下界仅 67.56%；不能据此宣称稳定生产 Recall。
2. 当前首要业务缺陷是 hn01 门岗队列：VAL 5/6、DEV(a) 15/18 均告警，告警率均为 83.33%。虽然按冻结定义单列、不计 primary FPR，但真实部署若包含门岗队列，会产生显著误报。
3. uncertain-scope 在 VAL 中 0/8 被判 uncertain，模型没有表现出预期的保守拒答。全集 uncertain 率为 0 不是优势证据。
4. 本次仅确认冻结的 Q1 outside-only evaluator；没有证明 detector coverage、ground-contact footprint、可信 road/bay geometry 或 V5 空间证据已解决。
5. 不具备生产集成或继续 HOLDOUT 的依据。本窗口按授权在回报后停止，不调参、不重跑。

## 风险

- AIGC domain gap：结果不能外推为真实固定相机、机器人或生产表现。
- Reference 风险：不是 human gold；scope/group intent 不能替代逐图人工审核。
- 小样本不确定性：VAL positive 仅 8，negative 仅 48；0 FP/8 TP 均有宽置信区间。
- 门岗风险：hn01 的稳定高告警是明确反证，不能因其被排除 primary FPR 而忽略。
- 拒答风险：uncertain 场景未触发 uncertain，可能形成过度确定输出。
- Detector 未做车辆级人工覆盖审计，本报告不称 detector Recall。
- 本次无 footprint、可信 geometry、真实机器人验证或生产延迟验证。

## 冻结状态

```text
VAL_ONE_SHOT_COMPLETED=true
VAL_RERUN_ALLOWED=false
HOLDOUT_IMAGE_READS=0
HOLDOUT_INFERENCE=0
Q2_REQUESTS=0
PHYSICAL_MODEL_REQUESTS=95
PRODUCTION_INTEGRATION_READY=false
CURRENT_STATUS=V2_1_OUTSIDE_ONLY_VAL_ONE_SHOT_COMPLETED_STOP
```
