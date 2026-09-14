# Footprint 两方法诊断与视觉质量审计（2026-09-10）

## 事实 / 推理 / 风险

**事实**：仅实现两种方法，参数在实跑和读取 evaluation labels 前冻结。主明确指示使用 A 已完成的 R1（仅扩 classes 加 pickup truck/van）作为最终源。本阶段不是新 detector；本阶段对 A 新检测作两种固定几何派生。60 张 allowlist 图逐一核验 image_id、绝对路径、SHA256 后开图。最终 221 辆唯一车辆 / 442 条 method record；不以 442 充当车辆数。

**推理**：可见车身底带最多是局部可见 proxy；bbox 下带只是保守低部 ROI，二者都不提供物理车底投影、真实接地点或完整轮胎接地面。mask 轮廓来源没有保留 contour 数，不能断言单个干净 contour；因此 A 方法全部为 uncertain 或 failed，未因数值合法而宣称 clear。

**风险**：碎片、遮挡边界、透视、高底盘、暗光、截断、低分辨率、mask 与 bbox 目标归属不一致；下带虽数值合法仍可能落在车身/其他车上。固定 20% 并非由 GT 校准，也不应解释为精度最优。本次小样本视觉审核不能外推到未审 201 辆。参考标签为 AI_VISUAL_REVIEWED_PROVISIONAL，不是 human gold，更不是 geometry GT。

## 冻结方法

- `mask_bottom_contact_band`：从单一、数值有效可见 mask 的 y 范围取底部 20%，仅做半平面裁剪，不膨胀 mask。多 contour 不合并；多个底带进入区间可能导致断开时拒绝候选；裁剪后仍执行正面积/自交检查。输出 visible_mask_polygon、contact_band_polygon、ground_contact_candidate（仅 proxy）；ground_contact_polygon 永远 null。
- `bbox_lower_conservative_proxy`：bbox 高度底部 20% 矩形，字段 bbox_proxy_polygon；不冒充 mask、contact polygon 或 footprint。ground_contact_candidate 与 ground_contact_polygon 均 null。
- 固定参数：bbox/mask 2 px 容差、extent IoU 最低 0.8、mask/bbox 面积占比最低 0.1、边缘风险 1 px；仅合成与几何规则先验，不按 labels 修改。polygon 的 nonadjacent touch 按不安全拒绝；不会自动修补/合并 contour。
- frozen contract SHA256：`7348c009011602c45670946313873defb3166727b7da057b8951e6fc0bed16b0`
- frozen footprint.py SHA256：`fc8c4c7abeb586815ed29f001e54afc5088ff45c8af3d97ec4cb0d6e7cb42564`

## 最终输入与计数

最终源：`/home/yanbo/net_vlm_parking_optimization/18_v5_detector_footprint/01_detector_audit/r1_targets.jsonl`

SHA256：`76b2f0d1343c68ed32c2c4e608f17d8da27079bfa41bd30b5a39adfe53bd446d`

| method | 唯一车辆分母 | validated | proxy | uncertain | failed | available candidate/ROI |
|---|---:|---:|---:|---:|---:|---:|
| mask bottom contact band | 221 | 0 | 0 | 185 | 36 | 170 |
| bbox lower conservative proxy | 221 | 0 | 176 | 45 | 0 | 221 |

`proxy` 状态仅表示该方法未触发已实现几何风险，不表示实际视觉审核通过。所有输出都保留单独 visual_review。geometry status 不会因人工录入视觉观察而升级到 validated。

**221/221 个已导出单polygon均通过有限值、图像范围、正有限面积检查；numeric invalid/missing=0。** 严格的导出polygon拓扑检查185通过、36拒绝（36有self-touch/非相邻接触，其中2另有零长度边）。这里的36是本方法拒绝该单polygon表示，不是36个原始mask输出失败，更不是证明36个真实dense mask语义全错。原始dense masks与独立component provenance均未导出（221/221 unknown），扁平化/桥接表示可能引入这些拓扑问题。另15个导出polygon通过原拓扑检查但不能安全得到单底带；因此 uncertain185不能误读为available185。reason_counts是多标签计数：42个自交/非相邻触碰包含36个导出polygon和6个裁切后底带。mask/bbox extent 不一致 5；band 可能断开 9；mask edge 风险 40（此前已失败者不会重复进入风险计数）。bbox edge 风险 45。

## 实际视觉质量审核

实际调用 `view_image` 查看了 footprint_visuals 下 5 张编号 montage（每张4辆；原图 crop 与 overlay 并排）和 4 个风险个体图，另查看风险18的5倍插值放大。抽样为固定均匀索引16辆 + 首次出现不同风险的4辆；不是按 labels/GT 选样。详细观察在 visual_review_log.json，覆盖 20 辆 / 40 条 method record；201 辆 / 402 条记录保持 unreviewed。

- mask-derived 底带仅 **6** 个被实际看图认为“局部可见底带 proxy 视觉合理”；bbox ROI **11** 个。这些不是 groundvalidated，也不是未审总体通过率。
- 02、03、06、09、14、16：底带大致沿可见前轮/低保险杠，可能漏掉透视后轮或整车其余接地区域。09 顶部截断但底部局部可见；几何 uncertain 不变。
- 07、13：原mask在邻车/镜子附近有额外细片/环线，不能靠主体大致对齐忽略碎片问题。
- 17：底盘高于轮胎最低点，裁切会产生分离的低区；没有强制连成物理 footprint。
- **19 / IMG_007620 S004**：后方白车上半身 mask 与前方黑车区域的 bbox 下带不一致；橙带是遮挡边界而非接地面，两个 proxy 视觉均 poor。
- 05、10、11、15、18：遮挡/像素不足，无法确认；5倍插值放大并不创造额外证据。

所有 ground_contact_polygon=null，ground_validated=0，footprintIoU=null（无 geometry GT）。全部 **DIAGNOSTIC_ONLY**；未运行任何正式空间分类，无告警输出。

## Reference evaluation（geometric_association_only，不是 confirmed）

按主明确授权，使用已完成且固定的 `/home/yanbo/net_vlm_parking_optimization/18_v5_detector_footprint/01_detector_audit/r1_matching.jsonl`，不等待、不更改 A 的最终 reviewed association。R1 只是本次最新完整 diagnostic 输入，**不是 winner**。A 最终 review 由主05另行对照。

matching SHA256：`084c19acad6bc6afd2196a6868532f60383328652595afb22e828ccf96d433e8`。

只由 evaluation.py 读取 reference labels；方法模块和抽样器不读 labels。join 以 image_id + vehicle_id，一对一 association；finalize_audit.py 逐一核对 matching 中全部 detection 的 bbox/raw_detection_id/mask 与 R1 target 完全一致、车辆集合一致，并验证 target hash。

| Reference group | method | reference分母 | available | qualitatively_valid（仅已看图proxy） | unavailable | available但未审 |
|---|---|---:|---:|---:|---:|---:|
| road | mask bottom band | 14 | 9 | 2 | 5 | 7 |
| road | bbox lower proxy | 14 | 13 | 4 | 1 | 9 |
| two-bay | mask bottom band | 18 | 14 | 1 | 4 | 13 |
| two-bay | bbox lower proxy | 18 | 16 | 2 | 2 | 14 |

road有1个、two-bay有2个reference未匹配，均计unavailable。available包含uncertain但存在的候选，不代表可信地面几何；qualitatively_valid是available子集，仅说明已实际审核的**检测目标proxy局部视觉合理**，不确认与reference是同一实体，更绝非groundvalidated。未审不算视觉不合格也不算通过。不以reference分母替代221个检测车辆分母，不外推抽样结果。

## 开发数据隔离

旧17输出只写 development_footprint_outputs.jsonl / development_footprint_metrics.json：195辆 /390行 /58有检测图。它们明确标记 development_sanity_NOT_final，未复制为最终输出；最终源来自18的新R1，检测数为221。

## API / 测试 / 复现

- `/home/yanbo/net_vlm_parking_optimization/18_v5_detector_footprint/02_footprint_audit/footprint.py`
  - `process_target(target, width, height) -> list[dict]`，恰好两条，target 必需 image_id、vehicle_id、bbox_xyxy；可传 mask_contours_image（单 contour）或 mask_polygon_image。
  - `polygon_quality(points, width, height) -> (normalized_polygon_or_none, issues)`；issues 非空即未通过几何检查。
  - `bottom_contact_band(...)`、`bbox_lower_proxy(...)`、`freeze_contract()`。
- 初始14项合成测试先通过，然后实际开发/最终实跑；当前加8项完整性/序列化/reference检查共22项通过，日志 runtime/all_tests.log。主wrapper另有16项通过记录（只读核对其结果，未写主目录）。
- `audit_visuals.render(source)` 只渲染且默认 unreviewed，**不自动声称视觉审核**。重新渲染会重置 visual_index 的审核标记，不应在未重新核验情况下覆盖审核日志。
- `evaluation.apply_visual_reviews(review_path, matching_path)` 只应用已经通过 view_image 产生的显式观察，禁止失败/缺失候选被标 qualitatively_valid_proxy。
- 标准库方法；已有 Pillow 仅用于 allowlist 解码与审计可视化。不安装、不下载、不调用模型/VLM/API。所有本任务文件、runtime/cache 均在本目录，PYTHONDONTWRITEBYTECODE=1；旧目录只读。
- 当前方法自交检查最坏 O(n²)，本次221车可完成；后续如扩大输入规模，应在独立新版本评估性能，不在本冻结阶段修补轮廓/改阈值。更可靠下一步应保留原 contour provenance，并独立获取真实接地几何标注；不把本proxy接入正式告警。

## 序列化 schema 修订说明（不变更冻结方法）

按主集成要求新增 serialize_audit.py，仅为既有派生记录补齐 bbox_xyxy（原R1 target）、footprint_source（mask_bottom_band / bbox_lower_proxy）、ground_contact_status（原status）、quality（algorithmic 与 visual 明确分层）、evidence（reasons、实际审查、source hash）。原status/reasons/visual_review继续保留；不自动validated、不重跑detector、不改方法代码/参数或freeze hash。

新增 mask_numeric_validity 与 stricter_polygon_topology_validity，以及逐车 mask_representation_diagnostics.jsonl。本阶段的数据表示不足必须保留：无法从单polygon恢复真实独立component，下一阶段应保存原始dense masks/独立contours及映射。禁止为本轮补保真而再跑detector。

如主重新应用visual reviews或reference join，随后再执行 serialize_audit.enrich_artifacts() 同步quality/evidence别名；该步骤不读GT、不重跑detector。

## 最终交付与复现顺序

最终 `finalize_audit.py` 将既有几何输出、实际visual_review_log与固定r1_matching join，再执行schema适配；不调用detector，也不再次开图。重新完整生成时顺序为 footprint.run(R1) → audit_visuals.render(R1) → 实际view_image审核 → 明确review日志 → finalize_audit.finalize()；禁止把render当作已审核。全部B产物仅本目录。
