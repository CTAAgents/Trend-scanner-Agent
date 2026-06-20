---
name: quantnova
description: >
  推理重于规则的量化交易决策辅助系统（简化版 v2.1.0）。
  支持期货+证券双市场。
  核心闭环：扫描→推理→辩论→风控。
  数据源：TqSdk（期货首选）、通达信MCP（证券首选）。
---

# QuantNova

> 推理重于规则的量化交易决策辅助系统 - 简化版 v2.1.0
> 完整文档请查看 [README.md](README.md) 和 [系统架构](docs/system_architecture_overview.md)

## 核心原则（必须遵守）

1. **数据第一原则**：绝对禁止使用模拟数据，分析必须使用真实数据
2. **系统分析原则**：所有分析必须基于QuantNova系统开展
3. **推理重于规则**：规则动态生成，非硬编码
4. **辩论验证原则**：所有交易建议必须经过多方辩论才可以向用户提交
5. **自优化原则**：多空判断方法需要系统自优化

## 架构（简化后）

```
核心闭环：扫描 → 推理 → 辩论 → 风控
├── 期货子系统（TqSdk）
├── 证券子系统（通达信MCP）
├── 推理引擎 + 辩论引擎
├── 因子评估
├── 指标计算
├── 基本面分析
├── 风控模块
└── 记忆系统
```

## 快速开始

```bash
# 数据同步
python tools/core/sync_data.py sync --days 120

# 运行扫描
python tools/core/scan_opportunities.py --output text --save

# Reasoner深度分析
python tools/core/scan_opportunities.py --reasoner --output text --save

# 因子评估
python tools/core/scan_opportunities.py --evaluate-factors
```

## 核心能力

| 能力 | 模块 |
|------|------|
| 技术指标计算 | indicators/ |
| LLM推理 | reasoning/reasoner |
| 鹰鸽辩论 | reasoning/debate_engine |
| 基本面分析 | fundamental/ |
| 风控检查 | risk/ |
| 因子评估 | evolution/ |
| 经验记忆 | core/memory/ |
| 期货子系统 | futures/ |
| 证券子系统 | securities/ |

## 数据源

| 市场 | 首选 | 第二 |
|------|------|------|
| 期货 | TqSdk | 通达信MCP |
| 证券 | 通达信MCP | NeoData |
| 基本面 | AKShare | 通达信MCP |

## 触发词

扫描市场、分析品种、期货分析、证券分析、因子评估、Reasoner分析、辩论分析

---

**完整文档：[README.md](README.md)** | **架构总览：[docs/system_architecture_overview.md](docs/system_architecture_overview.md)** | **变更：[docs/CHANGELOG.md](docs/CHANGELOG.md)**
