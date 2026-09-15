# Independent Recheck

日期：2026-09-15

- PASS：allowlist 精确为 80 个 VAL 样本；没有 HOLDOUT 图片路径。
- PASS：预测精确为 80 个唯一样本；Q1 物理请求 95；Q2 请求 0。
- PASS：两项 one-shot lock 均为 `COMPLETED_DO_NOT_RERUN`。
- PASS：Q1 prompt SHA256 为 `76151fc7f028c8274fd6c1a49158452a5b491d272b98effd463d8df2ba3b2eed`。
- PASS：旧 GT、split、DEV detector cache、R1 predictions 的 SHA256 未变化。
- PASS：指标分母为 p01=8、negative=48、hn01=6、p03=6、p05=4。
- PASS：VAL FP/FN 均为空；空错误目录不是缺失产物。
- 边界：HOLDOUT 图片读取/推理为 0，但先前上下文存在 HOLDOUT metadata exposure。
- 结论：一次性运行完整，可报告；不得重跑，不构成 production-ready。
