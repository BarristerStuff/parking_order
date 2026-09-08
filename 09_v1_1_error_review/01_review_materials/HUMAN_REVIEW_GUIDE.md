# parking_order_violation v1.1 DEV 人工视觉复核指南

日期：2026-09-07  
范围：仅冻结 DEV/train；禁止打开 VAL/HOLDOUT 图片、prompt 或 GT。

## 复核顺序

1. 优先打开 `review_gallery.html` 或对应 queue 的 contact sheet。
2. 先看图像，再填写视觉字段；不要先展开冻结 P0 reason。
3. 必要时点击缩略图查看原始 DEV 图片。不要修改原图。
4. 编辑 `../02_review_tables/v1_1_error_review.csv`，每条只依据真实图像填写。
5. generation intent、subtype、文件名和 P0 reason 都不是 Human Gold。

## 必填字段与允许值

`parking_space_evidence`：

- `clear`
- `partial_but_sufficient`
- `insufficient`
- `none`

`vehicle_visibility`：

- `complete`
- `mostly_complete`
- `truncated`
- `heavily_occluded`

`queue_context`：

- `clear_gate_queue`
- `not_gate_queue`
- `ambiguous`

`violation_severity`：

- `A_clear_gross_violation`：明显位于车位外、明显横跨多个车位、主体严重斜跨、侵占通行区，或多车中有明显乱停车辆。
- `B_moderate_violation`：有明显但非极端的空间越界、侵占相邻空间或明显偏离停车关系。
- `C_minor_line_contact_or_slight_overrun`：车轮压线、轻微跨线、保险杠/车身边缘少量突出，或仅透视上疑似轻微越界。
- `D_visually_compliant`：实际看起来正常停车。
- `E_not_judgable`：停车空间或车辆边界证据不足，无法可靠判断。

`v1_1_visual_label` / `candidate_v1_2_label`：

- `positive`
- `negative`
- `uncertain`

`error_attribution`：

- `genuine_model_error`
- `generation_intent_mismatch`
- `definition_boundary_problem`
- `insufficient_visual_evidence`
- `mixed_model_and_definition`
- `correct_prediction_after_visual_review`
- `needs_human_review`

`definition_issue`、`generation_issue`、`model_issue` 建议只填 `true`、`false` 或 `uncertain`。

完成视觉判断后将 `review_status` 改为 `reviewed`。存在第二审核人分歧时使用 `needs_adjudication`，不要强行统一。

## 归因提示

- FN 且图像在 v1.1 下清晰为 positive：通常是 `genuine_model_error`；若主要争议来自 C 类边界，可用 `mixed_model_and_definition`。
- positive generation intent，但图像是 D：`generation_intent_mismatch`。
- C 在 v1.1 为 positive、候选 v1.2 为 negative：`definition_boundary_problem` 或 `mixed_model_and_definition`。
- E：`insufficient_visual_evidence`。
- FP 不能按 intent 自动认定；应先判断图像在 v1.1 和候选 v1.2 下的真实标签。

## DEV 覆盖限制

- DEV 不含 faded-line 组；该组在 VAL，本轮未访问。
- DEV 不含 perspective 组；该组在 HOLDOUT，本轮未访问。
- p05 多车是正类组，20 条已全部进入 FN 队列，不属于 TN 控制。

