---
name: trend-scanner-agent
description: >
  推理重于规则的期货趋势跟踪决策辅助系统 v5.0。
  闭环迭代因子进化引擎（Generate→Eval→Gate→Memory），
  截面 IC/ICIR 评估，贝叶斯参数优化，多因子组合模型。
  数据源：TqSdk（首选）+ 通达信 MCP（备选）+ 本地数据库缓存。
---

# Trend Scanner Agent v5.0

> 完整文档请查看 [README.md](README.md)

## 快速开始

```bash
# 数据同步
python tools/sync_data.py sync --days 120

# 运行扫描
python tools/scan_opportunities.py --output text --save

# 因子评估
python tools/scan_opportunities.py --evaluate-factors

# 因子进化
python tools/scan_opportunities.py --evolve --evolve-rounds 5
```

## 核心能力

| 能力 | 命令 |
|------|------|
| 全品种扫描 | `--output text --save` |
| 因子评估 | `--evaluate-factors` |
| 因子进化 | `--evolve` |
| 参数优化 | `--optimize-params` |
| 策略健康检查 | `--health-check` |
| 过拟合检测 | `--overfitting-check` |

## 触发词

趋势扫描、期货扫描、因子评估、因子进化、参数优化

---

**完整文档：[README.md](README.md)**
