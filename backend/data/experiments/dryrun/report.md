# 实验结果

测试集: `pilot_candidates.csv`，样本数: 2

## 对比总表

| 配置 | 准确率 | macro-F1 | 引用有效率 | 证据覆盖率 | 平均耗时(s) |
|---|---|---|---|---|---|
| baseline | 1.000 | 0.333 | 0.000 | 0.000 | 2.0 |
| no_multi_agent | 0.500 | 0.222 | 1.000 | 1.000 | 6.3 |
| full | 0.500 | 0.222 | 1.000 | 1.000 | 7.8 |
| no_source_filter | 0.500 | 0.222 | 0.500 | 1.000 | 8.4 |
| no_rerank | 0.500 | 0.222 | 1.000 | 1.000 | 8.5 |


## 各类别 F1

### baseline
- 准确率 1.000，macro-F1 0.333
- 各类 F1: 支持=1.000，反驳=0.000，证据不足=0.000
- 混淆矩阵（行=真值, 列=预测）: {"support": {"support": 2, "refute": 0, "insufficient": 0}, "refute": {"support": 0, "refute": 0, "insufficient": 0}, "insufficient": {"support": 0, "refute": 0, "insufficient": 0}}

### no_multi_agent
- 准确率 0.500，macro-F1 0.222
- 各类 F1: 支持=0.667，反驳=0.000，证据不足=0.000
- 混淆矩阵（行=真值, 列=预测）: {"support": {"support": 1, "refute": 0, "insufficient": 1}, "refute": {"support": 0, "refute": 0, "insufficient": 0}, "insufficient": {"support": 0, "refute": 0, "insufficient": 0}}

### full
- 准确率 0.500，macro-F1 0.222
- 各类 F1: 支持=0.667，反驳=0.000，证据不足=0.000
- 混淆矩阵（行=真值, 列=预测）: {"support": {"support": 1, "refute": 0, "insufficient": 1}, "refute": {"support": 0, "refute": 0, "insufficient": 0}, "insufficient": {"support": 0, "refute": 0, "insufficient": 0}}

### no_source_filter
- 准确率 0.500，macro-F1 0.222
- 各类 F1: 支持=0.667，反驳=0.000，证据不足=0.000
- 混淆矩阵（行=真值, 列=预测）: {"support": {"support": 1, "refute": 0, "insufficient": 1}, "refute": {"support": 0, "refute": 0, "insufficient": 0}, "insufficient": {"support": 0, "refute": 0, "insufficient": 0}}

### no_rerank
- 准确率 0.500，macro-F1 0.222
- 各类 F1: 支持=0.667，反驳=0.000，证据不足=0.000
- 混淆矩阵（行=真值, 列=预测）: {"support": {"support": 1, "refute": 0, "insufficient": 1}, "refute": {"support": 0, "refute": 0, "insufficient": 0}, "insufficient": {"support": 0, "refute": 0, "insufficient": 0}}
