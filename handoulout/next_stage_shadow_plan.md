# 下一阶段：REAL_ROBOT_SHADOW_VALIDATION（仅计划）

本文件只描述下一阶段，不执行任何生产连接、broker 订阅或真实 shadow。

## 阶段

A. MQTT read-only probe：确认 broker、ACL、topic、payload 和进程部署位置；不修改生产 worker。

B. 20-frame canary：在确认可订阅同一 topic 且旁路不影响生产后运行，仍不触发现有告警。

C. collect >=300 vehicle frames：收集真实域车辆帧及独立 shadow JSONL 审计记录。

D. human review：审核全部 positive、全部 uncertain、随机 100 张 negative。

E. decide production integration：仅依据真实域人工审核、运行稳定性和误报风险决定是否进入生产集成。

## 预设真实域目标（待独立授权后验证）

- positive precision >=80%
- audited negative obvious-miss <=5%
- runtime error <=1%
- P95 <=8s
- gate_queue_false_alert_count=0

必须特别统计 `curb_single_line_parking`，因为 HOLDOUT 唯一 primary negative FP `IMG_007452` 属于合法路边平行停车、路缘加单侧停车线这一风险类型。
