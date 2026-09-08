# parking_order_violation v1.1 — P0 DEV 独立错误复盘与定义迁移决策

日期：2026-09-07  
范围：冻结 DEV/train only  
最终决策：`FINAL_DECISION=INSUFFICIENT_EVIDENCE`  
决策置信度：`DECISION_CONFIDENCE=high`

这里的 high 表示“高置信确认现有证据不足以在 KEEP 和 MIGRATE 之间作出合规判断”，不表示已知迁移方向。迁移方向本身的置信度为 low。

## 结论先行

239 条 P0 prediction 与冻结 DEV manifest 的绑定完整可靠，但本线程无法通过任何可用视觉通道看到图像像素。152 条复核全集的 `parking_space_evidence`、`vehicle_visibility`、`violation_severity` 等视觉字段因此全部保持未填，`review_status=needs_human_review`。在 generation intent 明确不是 Human Gold 的前提下，不能把 89 个 intent-FN 自动叫作真正模型漏检，也不能据此推荐 v1.2。

因此：

- `GENUINE_MODEL_FN=UNDETERMINED`
- `DEFINITION_BOUNDARY_FN=UNDETERMINED`
- `GENERATION_INTENT_MISMATCH_FN=UNDETERMINED`
- `INSUFFICIENT_EVIDENCE_FN=UNDETERMINED`
- `NEEDS_HUMAN_REVIEW_FN=89`

## 已确认事实

### 绑定与冻结状态

- DEV manifest：239 条，全部 `split=train`。
- predictions：239 条，239 个唯一 media_id；0 重复、0 缺失、0 额外。
- 239 条逐项匹配 relative_path、GT intent、sample_role、generation_group、subtype、source_id 和 split。
- 239 张绑定图片存在，且图片 SHA-256 与 DEV manifest 一致。
- prediction 状态全部为 `ok`；冻结记录没有 parse/inference error。
- 既有最终审计记录 prediction 与 VAL/HOLDOUT 的交集均为 0。
- predictions、run summary、metrics 的 SHA-256 与冻结基线一致。

HTTP 数值状态码没有逐条持久化，无法事后重建；本轮核对了冻结的 `status`、`inference_error`、`parse_error` 与 schema。

### P0 算术结果

- binary eligible：214；GT uncertain：25。
- TP=5、FP=3、TN=117、FN=89。
- Precision=0.625，Recall=0.0531914894，F1=0.0980392157，Accuracy=0.570093458。
- 模型输出分布：negative=231、positive=8、uncertain=0。
- p01：3/39 intent-positive 被检出；36 条 intent-FN。
- p02：2/35 intent-positive 被检出；33 条 intent-FN。
- p05：0/20 intent-positive 被检出；20 条 intent-FN。
- 3 个 intent-FP：n02 两条、hn04 一条。
- 25 个 GT-intent uncertain 全部预测为 negative。

以上数字说明 P0 输出极度偏向 negative，但不能单独证明低 Recall 是模型能力、分辨率、定义边界还是生成未兑现造成的。

### Recall 低的候选成因拆分

| 候选成因 | 本轮可确认的证据 | 可归因数量 |
|---|---|---:|
| model capability | 输出 231/239 为 negative；但没有 Human Gold 视觉标签 | UNDETERMINED |
| input resolution | P0 使用冻结输入配置；本轮禁止重跑，且无视觉复核反事实 | UNDETERMINED |
| multi-vehicle localization | p05 在 intent 口径下 0/20；但最终图像是否清晰兑现违规未知 | UNDETERMINED |
| definition boundary | p02 有 33 个 intent-FN；但 C 类真实比例未知 | UNDETERMINED |
| generation-intent mismatch | GT 是未审核 generation intent；D 类数量未知 | UNDETERMINED |
| insufficient visual evidence | uncertain intent 有 25 条；FN 中 E 类数量未知 | UNDETERMINED |

这些类别可能重叠，只有逐图复核后才能用 `error_attribution` 做互斥主归因并给出数量。

## 复核全集与材料

已创建 152 条、互斥的 DEV-only 复核全集：

- Queue A：89 FN，全量。
- Queue B：3 FP，全量。
- Queue C：25 GT uncertain，全量。
- Queue D：5 TP，全量。
- Queue E：30 TN control，seed=`20260907`；DEV 六个可用 TN subtype 各随机 5 条。

共生成 19 张 3×3 contact sheet，全部通过 Pillow 图片完整性校验；另有本地 gallery，P0 reason 默认折叠。

原需求希望 TN control 覆盖 faded-line 与 perspective，但二者分别属于 VAL 和 HOLDOUT，不存在于 DEV。遵守密封边界后无法覆盖；多车 p05 是正类组，20 条已在 FN 中全量覆盖。

## 为什么无法完成视觉 taxonomy

桌面 `view_image` 在打开首张 FN contact sheet 前失败：visualization sandbox 无法创建只读 `.git` 路径。独立 Node image emit 通道也在像素返回前失败：同一 sandbox 无法创建只读 `.agents` 路径。

这不是图片缺失：19 张 contact sheet 都存在并通过文件解码校验；问题是本线程没有可用的视觉显示通道。按照任务规则，不能用 subtype、generation intent、文件名、P0 reason 或另一个模型替代人工视觉判断。

## FN taxonomy

`null/UNDETERMINED` 表示尚未视觉复核，绝不表示 0。

| 指标 | 结果 |
|---|---:|
| FN_A_clear_gross_violation | UNDETERMINED |
| FN_B_moderate_violation | UNDETERMINED |
| FN_C_minor_line_contact | UNDETERMINED |
| FN_D_generation_intent_mismatch | UNDETERMINED |
| FN_E_not_judgable | UNDETERMINED |
| FN_A_rate | UNDETERMINED |
| FN_B_rate | UNDETERMINED |
| FN_C_rate | UNDETERMINED |
| FN_D_rate | UNDETERMINED |
| FN_E_rate | UNDETERMINED |
| MINOR_LINE_ONLY_COUNT | UNDETERMINED |
| MINOR_LINE_ONLY_RATE | UNDETERMINED |
| CLEAR_GROSS_VIOLATION_COUNT | UNDETERMINED |
| CLEAR_GROSS_VIOLATION_DETECTED | UNDETERMINED |
| CLEAR_GROSS_VIOLATION_RECALL | UNDETERMINED |
| P02_MINOR_LINE_RATE | UNDETERMINED |

## 专项组结论边界

### p01

39 条均进入复核包（36 FN + 3 TP），但尚不能判断所谓 outside-legal-bay 是否在最终图像中清晰兑现。

### p02

35 条均进入复核包（33 FN + 2 TP），但 A/B/C/D/E 分布和 C 类比例未知。p02 的 subgroup 名称不能替代视觉证据。

### p05

- `MULTI_VEHICLE_REVIEW_COUNT=20`
- `MULTI_VEHICLE_CLEAR_VIOLATION_COUNT=UNDETERMINED`
- `MULTI_VEHICLE_CLEAR_VIOLATION_DETECTED=UNDETERMINED`

模型在 generation-intent 口径下是 0/20，但无法判断每图是否真有明显违规车辆、目标大小、车位证据和遮挡程度。

### FP 与 GT uncertain

3 个 FP 和 25 个 GT uncertain 均已进入复核包。由于尚未视觉复核，不能把 FP 自动认定为模型错误，也不能统计 uncertain 中真正不可判断、应为 negative 或应为 positive 的数量。

## v1.1 与 v1.2 决策

KEEP 条件要求证明 A+B 占 FN 绝大多数；MIGRATE 条件要求证明 C+D+E 占较大比例，尤其 p02 多为轻微压线或视觉争议。当前两组关键比例都未知，所以任何方向性选择都会把 generation intent 或 subgroup 名称冒充视觉事实。

本轮仅保留一份未冻结的 v1.2 候选定义草案，没有创建 migration impact 目录，没有声称对 397 张完成迁移判断。VAL/HOLDOUT 未消费；未来即使确认升级，旧 v1.1 HOLDOUT 能否用于 v1.2 也必须另行作协议决策。

将 v1.1 positive 重标为 negative 确实可能机械提高 Accuracy、F1 或 FPR 等指标。因此新指标变好不能作为迁移理由；合法理由必须来自业务目标、机器人可观测性、标注一致性与真实视觉边界。

## 最多 10 条关键证据

1. 239/239 prediction 唯一、完整绑定冻结 DEV；0 missing、0 extra、0 duplicate。
2. P0 三个核心文件哈希与冻结基线完全一致。
3. GT 基础是 `generation_intent`，审核状态是 `unreviewed`，不是 Human Gold。
4. 模型 239 条只输出 8 个 positive、231 个 negative，低 Recall 的直接算术表现是强 negative 倾向。
5. 89 个 intent-FN 全量进入复核包：p01=36、p02=33、p05=20。
6. p02 共 35 条已全部纳入，但 C_minor_line_contact 比例尚无视觉证据。
7. p05 共 20 条已全部纳入，但明显违规数量和检出率尚无视觉证据。
8. 3 个 intent-FP 与 25 个 GT uncertain 已全部纳入，尚未被自动定性。
9. 两个独立图像显示通道均在显示任何像素前因 Codex visualization sandbox 失败。
10. 正式定义/标签/split、HOLDOUT seal、P0 输出与正式项目边界未变；正式数据集 validate 为 valid、0 error。

## 完成这项决策所需的最小下一步

由能实际看到图片的审核人打开本地 gallery/contact sheets，完成 `v1_1_error_review.csv` 中 152 条视觉字段。建议至少对 89 FN、3 FP、25 uncertain 采用双人独立复核，并对 B/C 与 gate-queue 分歧做裁决。只有随后计算出 FN A/B/C/D/E、p02 C 比例和 p05 明显违规检出率，才能应用 KEEP/MIGRATE 判断原则。

## 最终审计

```text
FINAL_STATUS=V1_1_ERROR_REVIEW_COMPLETE

DEV_REVIEW_ONLY=true
VAL_CONSUMED=false
HOLDOUT_CONSUMED=false

FN_TOTAL=89
FP_TOTAL=3
GT_UNCERTAIN_TOTAL=25
TP_CONTROL_TOTAL=5
TN_CONTROL_TOTAL=30

FN_A_CLEAR_GROSS=UNDETERMINED
FN_B_MODERATE=UNDETERMINED
FN_C_MINOR_LINE=UNDETERMINED
FN_D_INTENT_MISMATCH=UNDETERMINED
FN_E_NOT_JUDGABLE=UNDETERMINED

GENUINE_MODEL_FN=UNDETERMINED
DEFINITION_BOUNDARY_FN=UNDETERMINED
GENERATION_INTENT_MISMATCH_FN=UNDETERMINED
INSUFFICIENT_EVIDENCE_FN=UNDETERMINED
NEEDS_HUMAN_REVIEW_FN=89

MINOR_LINE_ONLY_COUNT=UNDETERMINED
MINOR_LINE_ONLY_RATE=UNDETERMINED

CLEAR_GROSS_VIOLATION_COUNT=UNDETERMINED
CLEAR_GROSS_VIOLATION_DETECTED=UNDETERMINED
CLEAR_GROSS_VIOLATION_RECALL=UNDETERMINED

P02_MINOR_LINE_RATE=UNDETERMINED

FINAL_DECISION=INSUFFICIENT_EVIDENCE
DECISION_CONFIDENCE=high

V1_1_LABELS_MODIFIED=false
P0_OUTPUT_MODIFIED=false
PROJECT_CODE_MODIFIED=false
SERVER_FILES_MODIFIED=false
OLLAMA_CALLED=false
```
