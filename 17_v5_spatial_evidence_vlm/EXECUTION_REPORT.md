# V5 执行报告

**日期：2026-09-10。最终状态：V5_BLOCKED_FOOTPRINT。**

工作起点 `/home/yanbo/net_vlm_yanboversion`；唯一实验写入根目录 `/home/yanbo/net_vlm_parking_optimization/17_v5_spatial_evidence_vlm`。执行前该目录不存在。版本目标：车辆分割 → ground-contact → 空间证据 → 确定性规则 → 可选 VLM verifier。

## 1. 事实 / CONFIRMED_FACT

### 历史核验
已读取交接文档、14 V3 报告、15 ROI R1 报告、16 V4 报告/ADR/reference freeze/reference instances/reference images/error attribution，以及 V4 pilot manifest、input adapter 和 adapted inputs；读取 v2 split 元数据与 DEV detection cache。生产 `yolo_gate.py`、`yoloe_gate.py` 与 prompts/alerts 停车相关逻辑仅只读检查。

任务列出的 `/home/yanbo/net_vlm_parking_optimization/15_v3_parked_on_road/EXECUTION_REPORT.md` 不存在，实际对应目录是 `15_v3_roi_r1`；未虚构文件。V4 pilot 实际 60 张、240 个审核实例；历史 R0/R1 均已执行，报告记录总计 218 次 Qwen 请求，不计入本次。V4 reference freeze 8 个原始哈希全部验证通过。本次复制其中 3 个参考文件并在新推理之前冻结，无参考标签修改。参考没有 bbox 等 V5 完整字段，因此保持历史原件，在 evaluator 中另读历史 detector bbox 做关联；未伪装成完整新 V5 reference。

### 来源及边界
使用 60 张旧 v2 **DEV** 的 AIGC 图像，全部来自 V4 已审核 pilot，仅诊断，不是新验证集。每次读取原图前验证允许清单和 SHA；最终审计再次对这 60 张原图复算 SHA。只读取非 DEV split 的 ID/split 元数据建立禁用清单，**没有打开 VAL/HOLDOUT 图像或标签**。

参考依据 `AI_VISUAL_REVIEWED_PROVISIONAL`，`HUMAN_GOLD=false`。没有新生成 AIGC 图像或新视觉参考：因固定 pilot 的 P0 停止，未启动下一批生成；**并未确认生成工具不可用**。历史真实相机/ROI 清单报告为无可用 bundle；本次在指定旧实验范围仍未找到对应 pilot ROI，未搜索服务器、未据此断言所有外部位置不存在真实数据。

### 本地环境与真实推理 / NEW_EVIDENCE
系统 `/usr/bin/python3` 缺 torch/numpy/cv2/ultralytics；`python` 命令不存在。发现并使用已有独立环境：

`/home/yanbo/net_vlm_garbage_optimization/P3_detector_vlm/.venv_yoloe/bin/python`

实际 torch `2.13.0+cpu`、ultralytics `8.4.104`，CUDA false。cv2/PIL/numpy 实际导入/使用成功，具体 cv2/numpy 版本、Python路径记录在 runtime_preflight.json。无环境安装，无模型下载，无 GPU 固定。已有 YOLOE-26m-seg 与匹配 MobileCLIP2 encoder 来自其他本地实验只读 runtime snapshot；权重 SHA 已记录。仅在 V5 runtime 内放置 encoder 符号链接及缓存。Python socket 层拦截网络，不声称有系统级网络隔离或抓包证据。

固定类 car/truck/bus，conf=.25，imgsz=640，retina_masks=true；全部 60 张按顺序推理一次。新增模型检测与 V4 历史 cache **不是同一 detector**，不能直接比 target ID。

| P0 指标 | 实际值 | Wilson 95% CI / 限定 |
|---|---:|---|
| 图像推理成功 | 60/60 = 100% | [93.98%,100%]；是运行成功，不是所有车辆检出 |
| raw detection | 196 | 原始 polygon/bbox 已保存 |
| 保留目标 | 195 | 固定 GT-blind IoU>.80 去重，抑制 1 个 |
| 数值有效 mask / 保留目标 | 195/195 = 100% | [98.07%,100%]，并非像素分割准确率 |
| 与旧审核车辆 bbox 关联 | 155/240 = 64.58% | [58.35%,70.36%]，事后 IoU≥.50 贪心一对一诊断 |
| road 参考车辆 bbox 关联 | 5/14 = 35.71% | [16.34%,61.24%]，**不是 road Recall** |
| two-bay 参考车辆 bbox 关联 | 11/18 = 61.11% | [38.62%,79.69%]，**不是 two-bay Recall** |
| positive 参考车辆 bbox 关联 | 16/32 = 50% | [33.63%,66.37%] |
| 已验证 ground footprint / 已检测目标 | 0/195 = 0% | [0%,1.93%]，未产出经验证的 ground contact |
| 已验证 ground footprint / 旧参考 | 0/240 = 0% | [0%,1.58%]，资产可用率，不是物理误差概率 |
| clear road / bay / two-bay evidence | 各 0/240 | 各 [0%,1.58%]，ROI 缺失，不能算分类效果 |

mask 是可见车身 polygon；bbox lower 是 bbox 最下方 20% 的矩形，字段明确分开，**没有冒充真实 footprint**。ground_contact_polygon_image 全部 null。195 个缺失 ROI 的 evidence 记录已实跑安全路径生成，overlap 为 null 而不是伪造 0；这不构成 P1 成功。

85 个历史参考未被一对一 bbox 匹配，40 个新检测未匹配旧参考；分别是漏检候选/多出目标，**不是已人工确认的 85 漏检或 40 误检**。两张图没有任何检测（IMG_007529、IMG_007702），仍保留在图像清单。部分前景皮卡漏检得到主执行者及独立审计视觉确认；visual_review_log 记录 5 个明确可见车辆未有框的实例，属于部分审核下界，不是全量审核漏检率。mask_failure_count=0 是数值/输出检查，不代表遮挡、分割质量全部合格。全部参考与新目标的空间像素对齐没有完成验收。

### 规则、VLM及指标状态
- 实现可执行 image-raster polygon overlap、union、显式邻接与 fail-closed 规则接口；抽象合成矩形测试覆盖 queue 优先、road、two-bay、非相邻拒绝、minor/nose-tail、冲突、bbox禁正、缺失ROI、坐标空间、非法polygon、NaN和图像聚合。
- 测试图形是 **ABSTRACT_SYNTHETIC_UNIT_FIXTURE**，不是新 AIGC 数据，也不是 GT-informed pilot geometry。
- P0 严格 gate 已实际运行，exit=2；verified ground footprint coverage=0 < .60，且全量对齐未验证。后续 pilot rules 与 VLM 禁止运行。

| 用户要求指标 | rules-only | rules + VLM |
|---|---|---|
| road Recall / two-bay Recall | null / NOT_EXECUTED | null / NOT_EXECUTED |
| 普通车位、压线/轻越线、头尾、门岗 FPR | 全部 null / NOT_EXECUTED | 全部 null / NOT_EXECUTED |
| 分类 uncertain rate / decisive coverage | null / NOT_EXECUTED | null / NOT_EXECUTED |
| 协议成功率 / semantic conflict | null / NOT_EXECUTED | null / NOT_EXECUTED |
| gate 开发门槛 | NOT_EVALUATED | NOT_EVALUATED |

“195 个 footprint 状态 uncertain”不是“运行分类器后 uncertain=100%”。没有生成伪规则预测或空 VLM 响应。类别 FPR 不填写 0。任何分母为 0 的计量函数输出 null；Wilson 区间亦 null。没有创建 Winner 或 development candidate。

### 请求、预检与成本
- 本次 Qwen/VLM 物理请求 **0**，重试 **0**，实际客户端并发 **0**（合同上限 2），VLM 延迟 null。
- `/api/tags` **NOT_EXECUTED_P0_STOP**：没有要进行的 VLM 正式调用，不宣称接口可用/不可达/缺模型。没有 smoke、prompt freeze、请求清单冻结或服务修改。
- 本地 YOLOE 图像推理调用 **60**；另有一次模型/文本类别 embedding 初始化，不与 Qwen 请求混算。
- 每图 predict + extraction + overlay 保存耗时 median **0.216s**，nearest-rank P95 **0.399s**，60 图合计 **14.599s**。不含模型/encoder 初始化与读取/解码，不是机器人端到端延迟。

### 审计
独立审计子代理只读复核了 allowlist/freeze、全部 raw/kept 关联与 mask 坐标/面积，另看了三个单图 overlay。发现 gate 未显式输出及 prepare 重入风险；已加 fail-closed P0 gate、拒绝覆盖初始基线与 self-hash 排除。未重跑模型。这些是推理后的工程修复，不追溯称为预注册。第二轮独立审计进一步发现 validated 状态可能伴随 mask fallback、ROI 跨图未绑定等缺陷；已增加实际 ground-contact polygon/source 的绑定、ROI image ID/SHA/size/status 检查及反例测试。当前 gate 明确为 rejection-only，**没有未来自动晋升 PASS 的权限**；完整可信放行链尚未实现，不能只填 VALIDATED 即恢复。未提供图像检测完整性证明时，空检测返回 uncertain；明确验证无有效车辆时才返回 ignore。

自动审计状态 `PASS_SCOPED_INTEGRITY`，能力状态 `BLOCKED_NOT_PASSED`。1005 项保护快照 SHA 与本次开始前一致；生产 Git dirty 状态一致（原本存在修改，未清理）。此快照有明确范围：不含旧图像/视频、绝大多数 v2 文件；不能据此声称每个禁改目录所有字节都已全量验证。操作记录中没有对旧目录、正式数据或生产项目的写入。没有 commit/push/reset/clean、服务器修改、代理或 SSH tunnel。

规则与合同测试 **25/25** 实跑通过（19 条规则测试、6 条合同测试），详细结果在 tests/test_results.json。独立审计及完整性通过不等同于完整 V5 独立验证通过。

## 2. 推理 / REASONED_INFERENCE

- **two-bay**：当前不是“two-bay 规则已失败”，而是已审核正例的 bbox 关联仅 11/18，随后没有可信 ground footprint/bay/adjacency 可供验证；不能把主因归为阈值或 VLM veto。
- **road**：14 个参考正例只关联 5 个，抽样可见前景皮卡漏检。即使 detector 有 mask，缺 road ROI 与可靠接地证据仍阻塞。不能通过统计现有 mask 数量来解释 road Recall。
- **VLM 价值**：未测，无法声称改善或无价值。根据合同，它不能挽救无 footprint 的未检出车辆，因此本轮不花 Qwen 请求是合理停止，不是证明永远不值得用 VLM。
- **与 V4 差异**：V4 依赖旧 cache 并让 Qwen判断图像关系；V5 真实跑了新 segmentation，暴露了 detector 替换后的覆盖问题，并在 evidence 前拒绝继续。两个阶段指标不能直接排列成准确率提升/退步。
- 继续值得投入的对象是 ground-contact/ROI 的可信建立和 detector miss，而不是 prompt sweep 或无依据阈值调参。当前既不是分类成功，也不是“所有可能 V5 路线均失败”。

## 3. 风险 / UNVERIFIED_ASSUMPTION / BLOCKER

1. AIGC 画面、遮挡与车型分布存在域差距，AI provisional reference 不是 human gold；V4 复用不是独立新验证。
2. 不知道实际机器人/固定相机视角、标定、bay/road/gate polygon 和队列语义。历史不存在的记录不证明所有外部数据均不存在。
3. 车身 mask 泛化和目标完整性尚未被像素GT验证；可见轮胎/底部边界不能自然变成被遮挡的四轮地面多边形。本次严格不作此假设。
4. 若后续按标签补画 synthetic/diagnostic ROI，会产生循环证据。本轮未这样做。
5. 所有检出目标可能触发多个 crop/请求；VLM 上限300不代表延迟可接受。未检出目标不会进入 verifier，多车费用与队列调度仍未测。
6. GT-blind 规则在业务上还需要可验证的 normal queue、boundary direction；当前抽象单测不能替代场景证据。BEV刻意未实现，混合空间 fail closed。
7. 复用其他本地 runtime 有依赖漂移维护成本；所有后续实验应新冻结而不是覆盖当前结果。真实机器人验证仍未执行。

## 4. 状态标识

```text
BUSINESS_DEFINITION=v3.0_user_confirmed
ALGORITHM_REVISION=V5_SPATIAL_EVIDENCE_VLM
SOURCE_TYPE=AIGC
REFERENCE_BASIS=AI_VISUAL_REVIEWED_PROVISIONAL
HUMAN_GOLD=false
V4_PILOT_REUSED=true
NEW_V5_REFERENCE_CREATED=false
V5_NEW_REFERENCE_DATA=false
V5_REFERENCE_REUSED_FROM_V4=true
INDEPENDENT_VALIDATION=false
RULE_ONLY_EXECUTED=false
RULE_ENGINE_SYNTHETIC_TESTS_EXECUTED=true
VLM_VERIFIER_EXECUTED=false
PHYSICAL_MODEL_REQUESTS=0
PHYSICAL_MODEL_REQUESTS_SCOPE=QWEN_VLM_HTTP_REQUESTS
LOCAL_SEGMENTATION_IMAGE_CALLS=60
MAX_CLIENT_CONCURRENCY=0
MAX_CLIENT_CONCURRENCY_LIMIT=2
CURRENT_DEVELOPMENT_CANDIDATE=NONE
V5_INDEPENDENT_VALIDATION=NOT_EXECUTED
REAL_ROBOT_VALIDATION=NOT_EXECUTED
OLD_V2_VAL_HOLDOUT_CONSUMED=false
PRODUCTION_INTEGRATION_READY=false
FINAL_STATUS=V5_BLOCKED_FOOTPRINT
```

## 5. 下一步（最多三项）

1. 独立审核遗漏前景车辆和完整 mask，定义并验证 ground-contact 的生成方法及误差容限；新合同下再测，不在本轮继续阈值/类名 sweep。
2. 提供与图像对应、独立于标签制作的 road/bay/gate/adjacency 标定；有条件时优先少量真实固定相机数据，再建立新冻结参考。
3. 仅在 P0/P1 达标后执行新 pilot rules-only，再按同一冻结样本衡量 conservative VLM verifier 的增量价值。
